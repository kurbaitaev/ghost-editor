#!/usr/bin/env python3
"""build/facescan_cut.json -> edit-time windows where the speaker is not clean on the lens, each labelled (references/broll.md 1):
  keep   a blink, a glance or a small nod: up to 0.5 s, head within 12 deg of the speaker's median, eyes back within 0.5 s.
         It stays on screen; it reads as a person talking (in one audited reel 29 of 31 windows were 0.03-0.4 s blips within 4 deg).
  cover  a real look-away: flagged for more than 0.5 s, eyes off the lens or closed for more than 0.5 s in a row, the head
         turned or bowed more than 12 deg, or the face lost for more than 0.5 s.
Writes build/cover_windows.json = the COVER windows only, as [[t0, t1], ...] (what generators hide; cheapest fix first:
trim, tight-crop punch, hold the current graphic, framed/split insert, full-screen stock last), and build/look_windows.json
= every window with its verdict and numbers. --strict restores the old behaviour (every window is a cover window)."""
import json
import sys

import numpy as np

LOOKAWAY_S, ANGLE_DEG = 0.5, 12.0


def windows(F, strict=False):
    T = np.array([x[0] for x in F])
    ok = np.array([x[1] is not None for x in F])
    V = np.array([[np.nan] * 8 if x[1] is None else x[1:] for x in F], float)
    med = np.nanmedian(V, 0)
    fps = 1 / np.median(np.diff(T)) if len(T) > 1 else 30.0
    cl = V[:, 7] > 0.42
    run = np.zeros(len(cl), int)
    for i in range(len(cl)):
        if cl[i]:
            run[i] = run[i - 1] + 1 if i else 1
    for i in range(len(cl) - 2, -1, -1):
        if cl[i] and cl[i + 1]:
            run[i] = run[i + 1]
    dyaw, dpitch = np.abs(V[:, 0] - med[0]), np.abs(V[:, 1] - med[1])
    look = (dyaw > 3) | (dpitch > 5.5) | (np.abs(V[:, 2] - med[2]) > 3) | (V[:, 3] > 0.22) | (V[:, 5] > 0.42) | (V[:, 6] > 0.42)
    bad = (~ok) | look | (cl & (run > 5))
    off = (V[:, 3] > 0.22) | (V[:, 5] > 0.42) | (V[:, 6] > 0.42) | cl | ~ok      # eyes off the lens, closed, or no face
    out, k = [], 0
    while k < len(T):
        if bad[k]:
            j = k
            while j + 1 < len(T) and (bad[j + 1] or (j + 3 < len(T) and bad[j + 2:j + 4].any())):
                j += 1
            sl = slice(k, j + 1)
            span = float(T[j] - T[k] + 1 / fps)
            r = mx = 0
            for g in off[sl]:
                r = r + 1 if g else 0
                mx = max(mx, r)
            gaze = mx / fps
            ang = float(np.nanmax(np.maximum(dyaw[sl], dpitch[sl]))) if np.isfinite(dyaw[sl]).any() else 99.0
            why = [w for w, c in (("flagged %.2f s" % span, span > LOOKAWAY_S), ("eyes off %.2f s" % gaze, gaze > LOOKAWAY_S),
                                  ("head %.0f deg" % ang, ang > ANGLE_DEG)) if c]
            out.append({"t0": round(float(T[k]) - 0.05, 2), "t1": round(float(T[j]) + 0.08, 2), "verdict": "cover" if (why or strict) else "keep",
                        "why": ", ".join(why) or "a blink / glance / small nod", "span_s": round(span, 2), "eyes_off_s": round(gaze, 2),
                        "max_angle_deg": round(ang, 1)})
            k = j + 1
        else:
            k += 1
    return out


if __name__ == "__main__":
    strict = "--strict" in sys.argv
    W = windows(json.load(open("build/facescan_cut.json", encoding="utf-8")), strict)
    json.dump(W, open("build/look_windows.json", "w", encoding="utf-8"), indent=1)
    cover = [[w["t0"], w["t1"]] for w in W if w["verdict"] == "cover"]
    json.dump(cover, open("build/cover_windows.json", "w", encoding="utf-8"))
    print(f"{len(W)} off-lens windows: {len(cover)} to cover, {len(W) - len(cover)} kept on screen")
    for w in W:
        if w["verdict"] == "cover":
            print(f"  COVER {w['t0']:6.2f}-{w['t1']:6.2f}  {w['why']}")
