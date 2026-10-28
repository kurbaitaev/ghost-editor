#!/usr/bin/env python3
"""Lip-sync regression test for cut assembly (recipes/clean-os/assemble.py).

    python3 tests/test_assemble_sync.py [--script recipes/clean-os/assemble.py] [--keep DIR]

Builds a synthetic 30 fps source where a white flash (picture) and a 1 kHz beep (sound) mark the same instant
inside each of 20 segments, cuts it with deliberately off-grid segment times, runs the assembler, then checks:
  1. wide.mp4 and tight.mp4 have exactly round(voice duration x 30) frames;
  2. in every segment the flash frame and the beep onset are within half a frame of each other (no drift).
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
FPS, SR = 30, 48000


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


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
    src = os.path.join(work, "src.mp4")
    sh(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=270x480:r={FPS}:d={dur}",
        "-f", "lavfi", "-i", f"aevalsrc='0.5*({beep})*sin(2*PI*1000*t)':s={SR}:d={dur}",
        "-vf", f"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='{flash}'",
        "-c:v", "libx264", "-g", "15", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-shortest", src.replace(".mp4", ".mov")])
    src = src.replace(".mp4", ".mov")
    sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", str(SR), os.path.join(work, "build", "voice-clean.wav")])
    json.dump({"source": src, "denoised": "build/voice-clean.wav", "segments": segs, "eyes": [0.5, 0.45], "tight": 1.0},
              open(os.path.join(work, "cut.json"), "w", encoding="utf-8"), indent=1)
    for f in ("wide.mp4", "tight.mp4", "voice.wav"):
        p = os.path.join(work, "assets", f)
        if os.path.exists(p):
            os.remove(p)
    r = subprocess.run([sys.executable, a.script, work], capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode not in (0, 1):
        sys.exit("assembler crashed:\n" + r.stderr[-2000:])

    fails = []
    # 1. lengths
    vd = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                   os.path.join(work, "assets", "voice.wav")], text=True).stdout)
    want = round(vd * FPS)
    for name in ("wide", "tight"):
        n = int(sh(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                    "stream=nb_read_packets", "-of", "csv=p=0", os.path.join(work, "assets", f"{name}.mp4")], text=True).stdout)
        print(f"{name}.mp4: {n} frames, voice {vd:.4f}s = {vd * FPS:.2f} frames")
        if n != want:
            fails.append(f"{name}.mp4 has {n} frames, voice wants {want}")
    # 2. per-segment alignment: flash frame vs beep onset
    raw = sh(["ffmpeg", "-v", "error", "-i", os.path.join(work, "assets", "wide.mp4"), "-vf", "scale=1:1,format=gray",
              "-f", "rawvideo", "-"]).stdout
    flashes = [i for i, v in enumerate(raw) if v > 128]
    flashes = [f for k, f in enumerate(flashes) if k == 0 or f - flashes[k - 1] > 3]
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
    print(f"marks: {len(flashes)} flashes, {len(onsets)} beeps (want {len(segs)} each)")
    if len(flashes) != len(segs) or len(onsets) != len(segs):
        fails.append(f"found {len(flashes)} flashes and {len(onsets)} beeps, want {len(segs)}")
    offs = [round((o - f / FPS) * 1000, 1) for f, o in zip(flashes, onsets)]
    print("beep - flash per segment (ms):", offs)
    # the flash frame covers [f/30, (f+1)/30); the beep starts at the frame's start: allow half a frame
    bad = [(i, d) for i, d in enumerate(offs) if abs(d) > 1000 / FPS / 2]
    if bad:
        fails.append(f"{len(bad)} segments out of sync: " + ", ".join(f"#{i} {d:+.0f} ms" for i, d in bad[:8]))
    if not a.keep:
        shutil.rmtree(work, ignore_errors=True)
    if fails:
        print("FAIL\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("PASS: picture and voice stay in sync across all segments")


if __name__ == "__main__":
    main()
