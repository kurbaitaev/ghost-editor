#!/usr/bin/env python3
"""Voice enhancement / super-resolution with ClearerVoice-Studio (MossFormer2, 48 kHz).

    voice_enhance.py IN OUT.wav [--mode enhance|superres|both] [--ss 0 --t 10] [--device auto|cpu|mps]
                                [--cutoff HZ] [--json report.json]

IN is any audio or video file (ffmpeg reads the first audio stream, mono, 48 kHz). OUT is a 48 kHz mono
24-bit wav of the same length, never clipped. Loudness is NOT changed beyond what the model does; the
cut sets loudness later (prep.sh / loudnorm).

  enhance   MossFormer2_SE_48K  speech enhancement: noise and reverb out, full band kept.
  superres  MossFormer2_SR_48K  speech super-resolution: a mel->HiFi-GAN model resynthesises the voice
                                from its 0-8 kHz content; we keep the ORIGINAL below the input's real
                                cutoff and take the generated band only above it.
  both      SE, then SR         noisy AND band-limited sources (Bluetooth / call / low-bitrate audio).

Inputs longer than 16 s are processed in 15 s pieces with 1 s crossfades (ClearVoice's own long-input path
crashes on MPS for SR and is slower).

Cutoff: ClearVoice's own merge cuts at the 99 %-energy frequency (~5 kHz for speech), so on a
full-band phone recording it throws away the real 5-16 kHz and pastes weaker synthetic top end in
(measured: -6 dB at 10-16 kHz on an iPhone voice). This wrapper instead looks for a brick-wall cutoff
in the long-term spectrum; when the input is already full band (>= --full-band, default 15 kHz) SR is
skipped and the input passes through. --cutoff forces a cutoff.

Weights (Apache-2.0, huggingface.co/alibabasglab/*) download at setup (scripts/setup_audioqa.sh runs --fetch-only) or on
first use into --models (default ~/.cache/ghost-audioqa/clearvoice, or $GHOST_AUDIOQA_MODELS); only inference files,
~0.45 GB SR + ~0.2 GB SE. Never into the repo. Venv: ~/.venvs/ghost-audioqa.
Prints device, wall time and real-time factor for every step.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
import soundfile as sf

SR = 48000
HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = {"enhance": ["MossFormer2_SE_48K"], "superres": ["MossFormer2_SR_48K"],
          "both": ["MossFormer2_SE_48K", "MossFormer2_SR_48K"]}
TASK = {"MossFormer2_SE_48K": "speech_enhancement", "MossFormer2_SR_48K": "speech_super_resolution"}


def read_audio(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss:
        cmd += ["-ss", str(ss)]
    if t:
        cmd += ["-t", str(t)]
    cmd += ["-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()
    if not len(x):
        sys.exit(f"no audio read from {path}")
    return x


def ltas_db(x, fs=SR, n=2048):
    """Long-term average spectrum (dB) over the louder half of the frames (speech, not pauses)."""
    from scipy.signal import stft
    f, _, Z = stft(x, fs, nperseg=n, noverlap=n * 3 // 4)
    P = np.abs(Z) ** 2
    e = P.sum(0)
    keep = e >= np.percentile(e, 50)
    L = 10 * np.log10(P[:, keep].mean(1) + 1e-20)
    k = 9  # ~200 Hz smoothing
    L = np.convolve(np.pad(L, k // 2, mode="edge"), np.ones(k) / k, "valid")
    return f, L


def detect_cutoff(x, fs=SR, drop_db=25.0):
    """Highest frequency with a brick-wall drop (>= drop_db across ~1 kHz, staying down to Nyquist).
    Natural speech rolls off a few dB per kHz; a resampled / low-passed source falls 30-80 dB at once."""
    f, L = ltas_db(x, fs)
    best = None
    for fc in np.arange(2000, fs / 2 - 1500, 125.0):
        below = np.median(L[(f > fc - 1500) & (f < fc - 250)])
        above_band = L[(f > fc + 250) & (f < fc + 1500)]
        rest = L[f > fc + 250]
        if below - np.median(above_band) >= drop_db and rest.max() < below - drop_db * 0.6:
            best = float(fc)
            break  # the lowest qualifying edge is the real one (everything above it is down)
    return best


def merge_bands(orig, gen, fc, fs=SR, order=6):
    """Original below fc, generated above, zero-phase Butterworth pair (power-complementary, flat sum)."""
    from scipy.signal import butter, sosfiltfilt
    n = min(len(orig), len(gen))
    lo = sosfiltfilt(butter(order, fc, "low", fs=fs, output="sos"), orig[:n])
    hi = sosfiltfilt(butter(order, fc, "high", fs=fs, output="sos"), gen[:n])
    return (lo + hi).astype(np.float32)


def fetch(name, models_dir):
    ck = os.path.join(models_dir, "checkpoints", name)
    if not os.path.isfile(os.path.join(ck, "last_best_checkpoint")):
        # fetch only what inference needs: the SR repo also holds a 1.7 GB training checkpoint (do_*)
        from huggingface_hub import snapshot_download
        print(f"downloading {name} weights (Apache-2.0, huggingface.co/alibabasglab/{name}) ...")
        os.makedirs(ck, exist_ok=True)
        snapshot_download(repo_id=f"alibabasglab/{name}", local_dir=ck, ignore_patterns=["do_*", "*.disc.pt"])
    return ck


def load(name, device, models_dir):
    import torch
    if device == "cpu":  # clearvoice picks MPS on its own when it exists; hide it to force the CPU
        torch.backends.mps.is_available = lambda: False
    ck = os.path.join(models_dir, "checkpoints", name)
    if not os.path.isfile(os.path.join(ck, "last_best_checkpoint")):
        # fetch only what inference needs: the SR repo also holds a 1.7 GB training checkpoint (do_*)
        from huggingface_hub import snapshot_download
        print(f"downloading {name} weights (Apache-2.0, huggingface.co/alibabasglab/{name}) ...")
        os.makedirs(ck, exist_ok=True)
        snapshot_download(repo_id=f"alibabasglab/{name}", local_dir=ck, ignore_patterns=["do_*", "*.disc.pt"])
    cwd = os.getcwd()
    os.chdir(models_dir)  # clearvoice resolves checkpoints/<model> relative to the cwd
    try:
        from clearvoice import ClearVoice
        cv = ClearVoice(task=TASK[name], model_names=[name])
    finally:
        os.chdir(cwd)
    return cv


def run_model(cv, x, td, tag, own_merge=False):
    """Run one ClearVoice model on x (48 kHz float). own_merge: SR returns the raw vocoder output (ClearVoice's
    99 %-energy band merge switched off) so main() can merge at the real cutoff."""
    import clearvoice.utils.decode as dec
    orig_sub = dec.bandwidth_sub
    if own_merge:
        dec.bandwidth_sub = lambda inp, out, fs=SR: out
    try:
        p = os.path.join(td, f"{tag}.wav")
        sf.write(p, x, SR, subtype="FLOAT")
        y = cv(input_path=p, online_write=False)
    finally:
        dec.bandwidth_sub = orig_sub
    y = np.asarray(y, np.float32).reshape(-1)[: len(x)]
    if len(y) < len(x):
        y = np.pad(y, (0, len(x) - len(y)))
    return y


def run_chunked(cv, x, td, tag, own_merge, chunk=15.0, overlap=1.0):
    """Long inputs in <= chunk-second pieces with a linear crossfade over the overlap. ClearVoice's own long-input
    path (> 20 s) breaks on MPS for SR (it writes MPS float32 into a float64 CPU tensor) and re-decodes 4 s windows
    with 25 % overlap; one-pass pieces avoid both."""
    n, c, o = len(x), int(chunk * SR), int(overlap * SR)
    if n <= c + o:
        return run_model(cv, x, td, tag, own_merge)
    out = np.zeros(n, np.float32)
    wsum = np.zeros(n, np.float32)
    starts = list(range(0, n - o, c - o))
    for k, s0 in enumerate(starts):
        s1 = min(n, s0 + c)
        y = run_model(cv, x[s0:s1], td, f"{tag}_{k}", own_merge)
        w = np.ones(s1 - s0, np.float32)
        if k > 0:
            w[:o] = np.linspace(0, 1, o, dtype=np.float32)
        if s1 < n:
            w[-o:] = np.linspace(1, 0, o, dtype=np.float32)
        out[s0:s1] += y * w
        wsum[s0:s1] += w
        if s1 >= n:
            break
    return out / np.maximum(wsum, 1e-6)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--fetch-only", action="store_true", help="download the SE and SR weights into --models and exit (setup)")
    ap.add_argument("--mode", choices=list(MODELS), default="enhance")
    ap.add_argument("--ss", type=float, default=None, help="start (s) inside IN")
    ap.add_argument("--t", type=float, default=None, help="duration (s)")
    ap.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto",
                    help="auto = clearvoice's choice (MPS on Apple Silicon)")
    ap.add_argument("--cutoff", type=float, default=None, help="force the SR crossover (Hz) instead of detecting it")
    ap.add_argument("--full-band", type=float, default=15000, help="detected cutoff at/above this = full band, SR skipped")
    ap.add_argument("--clearvoice-merge", action="store_true", help="use ClearVoice's own 99%%-energy merge (for A/B)")
    ap.add_argument("--models", default=os.environ.get("GHOST_AUDIOQA_MODELS", os.path.expanduser("~/.cache/ghost-audioqa/clearvoice")))
    ap.add_argument("--json", help="write a timing/metadata report here")
    a = ap.parse_args()
    if a.fetch_only:
        for name in MODELS["both"]:
            print(f"{name}: {fetch(name, a.models)}")
        return
    if not (a.src and a.out):
        ap.error("src and out are required")

    x = read_audio(a.src, a.ss, a.t)
    dur = len(x) / SR
    import torch
    torch.set_num_threads(os.cpu_count() or 8)
    fc = a.cutoff or detect_cutoff(x)
    rep = {"src": a.src, "mode": a.mode, "seconds": round(dur, 3), "detected_cutoff_hz": fc, "steps": []}
    print(f"input {dur:.2f}s; brick-wall cutoff: {f'{fc:.0f} Hz' if fc else 'none (full band)'}")
    with tempfile.TemporaryDirectory(prefix="venh-") as td:
        y = x
        for i, name in enumerate(MODELS[a.mode]):
            if name.startswith("MossFormer2_SR") and not a.clearvoice_merge and (fc is None or fc >= a.full_band):
                why = f"input is full band (cutoff {'none' if fc is None else f'{fc:.0f} Hz'}); nothing to restore"
                print(f"{name:20s} skipped: {why}")
                rep["steps"].append({"model": name, "skipped": why})
                continue
            t0 = time.time()
            cv = load(name, a.device, a.models)
            t_load = time.time() - t0
            dev = str(cv.models[0].device)
            own = name.startswith("MossFormer2_SR") and not a.clearvoice_merge
            t0 = time.time()
            out = run_chunked(cv, y, td, f"s{i}", own)
            if own:  # original below the cutoff, generated above (out is already de-normalised by clearvoice)
                out = merge_bands(y, out, fc)
            y = out
            t_run = time.time() - t0
            st = {"model": name, "device": dev, "load_s": round(t_load, 2), "run_s": round(t_run, 2),
                  "rtf": round(t_run / dur, 3)}
            if own:
                st["crossover_hz"] = fc
            rep["steps"].append(st)
            print(f"{name:20s} device={dev:4s} load {t_load:5.1f}s  run {t_run:6.1f}s for {dur:.1f}s audio  "
                  f"(RTF {t_run / dur:.2f}, {dur / t_run:.1f}x real time)" + (f"  crossover {fc:.0f} Hz" if own else ""))
            del cv
    peak = float(np.abs(y).max())
    if peak > 0.999:  # never clip the file
        y = y * (0.999 / peak)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sf.write(a.out, y, SR, subtype="PCM_24")
    rep["out"] = a.out
    rep["total_run_s"] = round(sum(s.get("run_s", 0) for s in rep["steps"]), 2)
    print(f"-> {a.out}  ({dur:.2f}s, 48 kHz mono)")
    if a.json:
        json.dump(rep, open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
