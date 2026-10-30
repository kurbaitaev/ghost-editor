#!/usr/bin/env python3
"""Lip-sync regression test for cut assembly (recipes/clean-os/assemble.py).

    python3 tests/test_assemble_sync.py [--script recipes/clean-os/assemble.py] [--keep DIR]

Builds a synthetic 30 fps source where a white flash (picture) and a 1 kHz beep (sound) mark the same instant
inside each of 20 segments, cuts it with deliberately off-grid segment times, runs the assembler, then checks:
  1. wide.mp4 and tight.mp4 have exactly round(voice duration x 30) frames;
  2. in every segment the flash frame and the beep onset are within half a frame of each other (no drift).
Then the same cut as a plan_cut.py plan (--plan): split edits (vearly 2 frames on every other piece: the picture cuts
before the sound, the next picture starts early), "same" sub-pieces and the alt framing; checks 1-2 on wide, tight and alt,
that build/rawcut.mp4 has the same frame count, and 3: the 2 source frames before each early-starting piece (dark grey)
appear exactly at its first two picture frames (and never in the segments cut).
The old assembler (select by time on unsnapped edges, voice cut at the exact times) fails both: its picture
gains frames piece by piece and the voice ends up early. Needs only ffmpeg/ffprobe and python3 (stdlib).
"""
import argparse
import array
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
X264_THREADS = open(os.path.join(REPO, "scripts", "X264_THREADS")).read().strip()  # every libx264 encode (scripts/x264.py)
FPS, SR = 30, 48000


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def frames(path):
    return int(sh(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                   "stream=nb_read_packets", "-of", "csv=p=0", path], text=True).stdout)


def run_and_check(script, work, args, names, nseg, rawcut=False, preroll=()):
    for f in ("wide.mp4", "tight.mp4", "alt.mp4", "voice.wav"):
        p = os.path.join(work, "assets", f)
        if os.path.exists(p):
            os.remove(p)
    r = subprocess.run([sys.executable, script, work] + args, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode not in (0, 1):
        sys.exit("assembler crashed:\n" + r.stderr[-2000:])
    fails = []
    # 1. lengths
    vd = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                   os.path.join(work, "assets", "voice.wav")], text=True).stdout)
    want = round(vd * FPS)
    for name in names + (("../build/rawcut",) if rawcut else ()):
        n = frames(os.path.join(work, "assets", f"{name}.mp4"))
        print(f"{os.path.basename(name)}.mp4: {n} frames, voice {vd:.4f}s = {vd * FPS:.2f} frames")
        if n != want:
            fails.append(f"{name}.mp4 has {n} frames, voice wants {want}")
    # 2. per-segment alignment: flash frame vs beep onset
    pcm = array.array("h", sh(["ffmpeg", "-v", "error", "-i", os.path.join(work, "assets", "voice.wav"), "-ac", "1", "-ar", str(SR),
                               "-f", "s16le", "-"]).stdout)
    win = SR // 1000  # 1 ms
    peak = max(abs(x) for x in pcm) or 1
    onsets, last = [], -1e9
    for i in range(0, len(pcm) - win, win):
        rms = math.sqrt(sum(x * x for x in pcm[i:i + win]) / win)
        t = i / SR
        if rms > 0.2 * peak and t - last > 0.5:
            onsets.append(t)
            last = t
        elif rms > 0.2 * peak:
            last = t
    for name in names:
        raw = sh(["ffmpeg", "-v", "error", "-i", os.path.join(work, "assets", f"{name}.mp4"), "-vf", "scale=1:1,format=gray",
                  "-f", "rawvideo", "-"]).stdout
        grey = [i for i, v in enumerate(raw) if 40 < v < 120]       # 3. split edits: pre-roll frames exactly where the plan puts them
        if grey != list(preroll):
            fails.append(f"{name}: pre-roll frames at {grey[:12]}, the plan puts them at {list(preroll)[:12]}")
        flashes = [i for i, v in enumerate(raw) if v > 128]
        flashes = [f for k, f in enumerate(flashes) if k == 0 or f - flashes[k - 1] > 3]
        print(f"{name} marks: {len(flashes)} flashes, {len(onsets)} beeps (want {nseg} each)")
        if len(flashes) != nseg or len(onsets) != nseg:
            fails.append(f"{name}: found {len(flashes)} flashes and {len(onsets)} beeps, want {nseg}")
        offs = [round((o - f / FPS) * 1000, 1) for f, o in zip(flashes, onsets)]
        print(f"{name} beep - flash per segment (ms):", offs)
        # the flash frame covers [f/30, (f+1)/30); the beep starts at the frame's start: allow half a frame
        bad = [(i, d) for i, d in enumerate(offs) if abs(d) > 1000 / FPS / 2]
        if bad:
            fails.append(f"{name}: {len(bad)} segments out of sync: " + ", ".join(f"#{i} {d:+.0f} ms" for i, d in bad[:8]))
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default=os.path.join(REPO, "recipes", "clean-os", "assemble.py"))
    ap.add_argument("--keep", help="work in this directory and keep it")
    a = ap.parse_args()
    work = os.path.abspath(a.keep) if a.keep else tempfile.mkdtemp(prefix="avsync-")
    os.makedirs(os.path.join(work, "build"), exist_ok=True)

    # 20 segments with off-grid edges; the mark sits on a frame 0.6 s into each one
    segs, marks = [], []
    for i in range(20):
        sa = 1.013 + i * 1.937
        sb = sa + 1.217 + 0.011 * (i % 5)
        segs.append([round(sa, 3), round(sb, 3), f"seg {i}"])
        marks.append(round((sa + 0.6) * FPS) / FPS)
    dur = segs[-1][1] + 2
    flash = "+".join(f"between(t,{m - 0.001:.4f},{m + 0.5 / FPS:.4f})" for m in marks)
    beep = "+".join(f"between(t,{m:.4f},{m + 0.06:.4f})" for m in marks)
    # the 2 frames before every odd segment's (snapped) start: only a split edit (the picture starting 2 frames early) shows them
    pre = "+".join(f"between(t,{(round(sa * FPS) - 2.4) / FPS:.4f},{(round(sa * FPS) - 0.6) / FPS:.4f})" for i, (sa, _, _) in enumerate(segs) if i % 2)
    src = os.path.join(work, "src.mp4")
    sh(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=270x480:r={FPS}:d={dur}",
        "-f", "lavfi", "-i", f"aevalsrc='0.5*({beep})*sin(2*PI*1000*t)':s={SR}:d={dur}",
        "-vf", f"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='{flash}',drawbox=x=0:y=0:w=iw:h=ih:color=0x505050:t=fill:enable='{pre}'",
        "-c:v", "libx264", "-threads", X264_THREADS, "-g", "15", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-shortest", src.replace(".mp4", ".mov")])
    src = src.replace(".mp4", ".mov")
    sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", str(SR), os.path.join(work, "build", "voice-clean.wav")])
    fails = []
    json.dump({"source": src, "denoised": "build/voice-clean.wav", "segments": segs, "eyes": [0.5, 0.45], "tight": 1.0},
              open(os.path.join(work, "cut.json"), "w"), indent=1)
    fails += run_and_check(a.script, work, [], ("wide", "tight"), len(segs), preroll=[])
    # the same cut as plan pieces: split edits + alt framing
    pieces, prev = [], 0
    for i, (sa, sb, note) in enumerate(segs):
        qa, qb = round(sa * FPS) / FPS, round(sb * FPS) / FPS
        ve = 2 if i % 2 == 0 and i < len(segs) - 1 else 0
        pieces.append({"a": qa, "b": qb, "va": qa - prev / FPS, "vb": qb - ve / FPS, "vearly": ve, "same": i % 3 == 2, "note": note})
        prev = ve
    json.dump({"pieces": pieces}, open(os.path.join(work, "build", "plan.json"), "w"), indent=1)
    json.dump({"source": src, "denoised": "build/voice-clean.wav", "eyes": [0.5, 0.45], "tight": 2.0, "framings": ["wide", "tight", "alt"]},
              open(os.path.join(work, "cut.json"), "w"), indent=1)
    starts = [sum(round((q["vb"] - q["va"]) * FPS) for q in pieces[:k]) for k in range(len(pieces))]
    pre_at = [f for k in range(1, len(pieces), 2) for f in (starts[k], starts[k] + 1)]
    fails += run_and_check(a.script, work, ["--plan", "build/plan.json"], ("wide", "tight", "alt"), len(segs), rawcut=True, preroll=pre_at)
    if not a.keep:
        shutil.rmtree(work, ignore_errors=True)
    if fails:
        print("FAIL\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("PASS: picture and voice stay in sync across all segments")


if __name__ == "__main__":
    main()
