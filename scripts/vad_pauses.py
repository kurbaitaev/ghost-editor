#!/usr/bin/env python3
"""Speech islands and pauses with silero-vad v6 (MIT): a noise-robust replacement for dB thresholds.

    vad_pauses.py AUDIO [--min-pause 0.7] [--threshold 0.5] [--lead 0.10 --tail 0.10] [--ss S --t T]
                        [--out pauses.json] [--probs]

AUDIO is any audio or video file (ffmpeg -> 16 kHz mono). Times in the JSON are seconds of AUDIO
(plus --ss, so they stay in original-recording seconds).

Why: `silencedetect=noise=-30..-38dB` decides "speech" by loudness, so it depends on gain, mic distance
and the noise floor: crickets, wind or traffic above the threshold glue the whole recording into one
island, and a soft first word below it gets clipped. silero-vad scores each 32 ms window for SPEECH
(a neural classifier), so the same settings work on raw and denoised audio.

Output JSON:
  islands  [{a, b, dur}]   speech, gaps shorter than --min-pause bridged (the speaker's rhythm stays)
  pauses   [{a, b, dur, kind}]  gaps >= --min-pause; kind = "silent" or "sound" (a breath, click or
                           noise burst inside the pause, from a 10 ms RMS envelope; VAD calls it non-speech)
  takes    [{a, b}]        islands with --lead / --tail kept: the `takes` array for reel.json
                           (drop-in for scripts/autocut.py output)
  probs    [p, ...]        per-32 ms speech probability (only with --probs; for charts)
Runs ~100-300x real time on one CPU core (the model is 2 MB); no GPU needed.
"""
import argparse
import json
import subprocess
import sys
import time

import numpy as np

SR = 16000
WIN = 512  # silero v6 window at 16 kHz (32 ms)


def read16k(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss:
        cmd += ["-ss", str(ss)]
    if t:
        cmd += ["-t", str(t)]
    cmd += ["-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()
    if not len(x):
        sys.exit(f"no audio in {path}")
    return x


def speech_probs(x, onnx=False):
    import torch
    from silero_vad import load_silero_vad
    torch.set_num_threads(1)
    model = load_silero_vad(onnx=onnx)
    model.reset_states()
    xt = torch.from_numpy(x)
    out = []
    with torch.no_grad():
        for i in range(0, len(xt), WIN):
            ch = xt[i:i + WIN]
            if len(ch) < WIN:
                ch = torch.nn.functional.pad(ch, (0, WIN - len(ch)))
            out.append(float(model(ch, SR)))
    return np.array(out, np.float32)


def islands_from_probs(p, n_samples, threshold=0.5, min_speech=0.12):
    """Raw speech regions (no padding, gaps >= 0.1 s split) using silero's own hysteresis logic."""
    from silero_vad.utils_vad import get_speech_timestamps_from_probs
    ts = get_speech_timestamps_from_probs(list(map(float, p)), sampling_rate=SR, threshold=threshold,
                                          min_speech_duration_ms=int(min_speech * 1000), min_silence_duration_ms=100,
                                          speech_pad_ms=0, return_seconds=False, audio_length_samples=n_samples)
    return [[t["start"] / SR, t["end"] / SR] for t in ts]


def merge(isl, min_pause):
    out = []
    for a, b in isl:
        if out and a - out[-1][1] < min_pause:
            out[-1][1] = b
        else:
            out.append([a, b])
    return out


def rms_db(x, hop=160):
    n = len(x) // hop
    r = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9
    return 20 * np.log10(r)


def pause_kind(env, a, b, floor, rise=12.0, min_len=0.08):
    """'sound' if the pause holds >= min_len of energy rise dB above the non-speech floor (breath, click, noise)."""
    seg = env[int(a * 100):int(b * 100)]
    if not len(seg):
        return "silent", None
    loud = seg > floor + rise
    if loud.sum() * 0.01 >= min_len:
        i = np.argmax(seg)
        return "sound", round(a + i / 100, 2)
    return "silent", None


def analyse(x, min_pause=0.7, threshold=0.5, lead=0.10, tail=0.10, min_speech=0.12, onnx=False, offset=0.0):
    t0 = time.time()
    p = speech_probs(x, onnx)
    t_vad = time.time() - t0
    dur = len(x) / SR
    raw = islands_from_probs(p, len(x), threshold, min_speech)
    isl = merge(raw, min_pause)
    env = rms_db(x)
    frame_speech = np.zeros(len(env), bool)
    for a, b in raw:
        frame_speech[int(a * 100):int(b * 100) + 1] = True
    ns = env[~frame_speech[: len(env)]]
    floor = float(np.percentile(ns, 30)) if len(ns) else float(env.min())
    pauses = []
    edges = [0.0] + [v for ab in isl for v in ab] + [dur]
    for i in range(0, len(edges), 2):
        a, b = edges[i], edges[i + 1]
        if b - a >= min_pause or (b - a > 0.05 and (i == 0 or i == len(edges) - 2)):
            kind, at = pause_kind(env, a, b, floor)
            pauses.append({"a": round(a + offset, 3), "b": round(b + offset, 3), "dur": round(b - a, 3), "kind": kind,
                           **({"sound_at": round(at + offset, 2)} if at is not None else {}),
                           **({"edge": "start" if i == 0 else "end"} if i in (0, len(edges) - 2) else {})})
    tk = []
    for a, b in isl:
        ta, tb = max(0.0, a - lead), min(dur, b + tail)
        if tk and ta <= tk[-1][1]:
            tk[-1][1] = tb
        else:
            tk.append([ta, tb])
    takes = [{"a": round(a + offset, 2), "b": round(b + offset, 2)} for a, b in tk]
    res = {
        "duration": round(dur, 3),
        "params": {"min_pause": min_pause, "threshold": threshold, "lead": lead, "tail": tail, "min_speech": min_speech,
                   "model": "silero-vad v6 (" + ("onnx" if onnx else "jit") + ")"},
        "noise_floor_db": round(floor, 1),
        "speech_s": round(sum(b - a for a, b in isl), 2),
        "islands": [{"a": round(a + offset, 3), "b": round(b + offset, 3), "dur": round(b - a, 3)} for a, b in isl],
        "pauses": pauses,
        "takes": takes,
        "vad_seconds": round(t_vad, 2),
        "x_realtime": round(dur / max(t_vad, 1e-6), 1),
    }
    return res, p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--min-pause", type=float, default=0.7, help="gaps shorter than this stay inside an island (s)")
    ap.add_argument("--threshold", type=float, default=0.5, help="speech probability threshold (silero default 0.5)")
    ap.add_argument("--lead", type=float, default=0.10, help="kept before each island in `takes` (s)")
    ap.add_argument("--tail", type=float, default=0.10, help="kept after each island in `takes` (s)")
    ap.add_argument("--min-speech", type=float, default=0.12, help="shorter speech blips are dropped (s)")
    ap.add_argument("--ss", type=float, default=None)
    ap.add_argument("--t", type=float, default=None)
    ap.add_argument("--onnx", action="store_true", help="use the ONNX model (needs onnxruntime)")
    ap.add_argument("--probs", action="store_true", help="include per-32 ms speech probabilities")
    ap.add_argument("--out", help="write JSON here (default: stdout)")
    a = ap.parse_args()
    x = read16k(a.src, a.ss, a.t)
    res, p = analyse(x, a.min_pause, a.threshold, a.lead, a.tail, a.min_speech, a.onnx, offset=a.ss or 0.0)
    res = {"src": a.src, **res}
    if a.probs:
        res["probs_hop_s"] = WIN / SR
        res["probs"] = [round(float(v), 3) for v in p]
    s = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(s)
        kinds = {}
        for q in res["pauses"]:
            kinds[q["kind"]] = kinds.get(q["kind"], 0) + 1
        print(f"{len(res['islands'])} islands, {len(res['pauses'])} pauses >= {a.min_pause}s {kinds}, "
              f"speech {res['speech_s']}s of {res['duration']}s; VAD {res['vad_seconds']}s ({res['x_realtime']}x real time)"
              f"\n-> {a.out}")
    else:
        print(s)


if __name__ == "__main__":
    main()
