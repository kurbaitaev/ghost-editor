#!/usr/bin/env python3
"""Close-up strip of the eyes for a time window, every frame (or every k-th), with the face-scan numbers on each tile
(red = off the median: eyes down / out / in, yaw or pitch moved). The frames to check a flag against before acting on it.

    eyestrip.py <video> <facescan.json> <t0> <t1> [--step 1] [--cols 10] [--out strips/eyes_<t0>-<t1>.jpg]

<video> = the video the scan was made of (same frames, row i = frame i; build/proxy.mp4); t0/t1 in the scan's times
(true frame times with --pts). Needs a 13-column scan (nose / eye distance locate the eyes)."""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from facescan import matrix


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("facescan"); ap.add_argument("t0", type=float); ap.add_argument("t1", type=float)
    ap.add_argument("--step", type=int, default=1); ap.add_argument("--cols", type=int, default=10); ap.add_argument("--out")
    A = ap.parse_args()
    import cv2
    T, V = matrix(json.load(open(A.facescan)))
    if V.shape[1] < 11: sys.exit("eyestrip needs a facescan with nose / eye-distance columns (facescan.py, 13-column rows)")
    med = np.nanmedian(V, 0)
    cap = cv2.VideoCapture(A.video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if abs(n - len(T)) > 1: print(f"WARNING: {A.video} has {n} frames, the scan {len(T)} rows: tiles may not match their numbers")
    i0, i1 = int(np.searchsorted(T, A.t0)), int(np.searchsorted(T, A.t1)); cap.set(cv2.CAP_PROP_POS_FRAMES, i0)
    tiles = []
    for i in range(i0, i1 + 1):
        ok, f = cap.read()
        if not ok: break
        if (i - i0) % A.step: continue
        sc = f.shape[1] / 1080                       # scan pixels are of a 1080-wide frame
        v = V[i] if i < len(V) else np.full(V.shape[1], np.nan)
        nx, ny, ed = (v[8], v[9], v[10]) if not np.isnan(v[8]) else (med[8], med[9], med[10])
        cx, cy, w, h = int(nx * sc), int((ny - 0.42 * ed) * sc), int(1.9 * ed * sc), int(0.75 * ed * sc)
        crop = f[max(0, cy - h // 2):cy + h // 2, max(0, cx - w // 2):cx + w // 2]
        crop = cv2.resize(crop, (300, 118))
        pad = np.zeros((crop.shape[0] + 46, 300, 3), np.uint8); pad[46:] = crop
        bad = (v[3] > 0.22) or (v[5] > 0.42) or (v[6] > 0.42) or abs(v[0] - med[0]) > 3 or abs(v[1] - med[1]) > 5.5
        col = (60, 60, 255) if bad else (200, 255, 200)
        cv2.putText(pad, f"{T[i]:.2f} y{v[0]:.0f} p{v[1]:.0f} b{v[7]:.2f}", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
        cv2.putText(pad, f"dn{v[3]:.2f} up{v[4]:.2f} o{v[5]:.2f} i{v[6]:.2f}", (4, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
        tiles.append(pad)
    if not tiles: sys.exit(f"no frames between {A.t0} and {A.t1}")
    rows = [np.hstack(tiles[k:k + A.cols] + [np.zeros_like(tiles[0])] * (A.cols - len(tiles[k:k + A.cols]))) for k in range(0, len(tiles), A.cols)]
    out = A.out or os.path.join(os.path.dirname(os.path.abspath(A.facescan)), "strips", f"eyes_{A.t0:.2f}-{A.t1:.2f}.jpg")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82]); print(out, len(tiles), "tiles")


if __name__ == "__main__":
    main()
