#!/usr/bin/env python3
"""Tighten a single clean take: cut the pauses, keep every word.

    autocut.py <project>/assets/talk.mp4 [--noise -35] [--min 0.28] [--keep 0.10] [--from 0] [--to END]

For a recording that is already one good take (no retakes to choose), the
edit is mostly pause removal. Whisper stretches words over the pauses, so the
pauses come from the AUDIO: silencedetect at --noise dB, silences longer than
--min seconds are removed except --keep seconds on each side (the breath that
keeps it natural). Prints a "takes" array for reel.json and the new length.
"""
import argparse
import json
import re
import subprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--noise", type=float, default=-35)
    ap.add_argument("--min", type=float, default=0.28)
    ap.add_argument("--keep", type=float, default=0.10)
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    a = ap.parse_args()
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.src],
                               capture_output=True, text=True).stdout)
    t1 = a.t1 or dur
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.src, "-af", f"silencedetect=noise={a.noise}dB:d={a.min}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    sil = list(zip(starts, ends + [dur] * (len(starts) - len(ends))))
    takes, cur = [], a.t0
    for s, e in sil:
        if e <= a.t0 or s >= t1:
            continue
        if s <= a.t0:  # leading silence
            cur = max(cur, e - a.keep)
            continue
        takes.append({"a": round(cur, 2), "b": round(min(s + a.keep, t1), 2)})
        cur = e - a.keep
    if cur < t1 - 0.05:
        takes.append({"a": round(cur, 2), "b": round(t1, 2)})
    takes = [t for t in takes if t["b"] - t["a"] > 0.15]
    kept = sum(t["b"] - t["a"] for t in takes)
    print(json.dumps(takes))
    print(f"\n{len(takes)} takes, {kept:.2f}s kept of {t1 - a.t0:.2f}s ({t1 - a.t0 - kept:.2f}s of pauses removed)")


if __name__ == "__main__":
    main()
