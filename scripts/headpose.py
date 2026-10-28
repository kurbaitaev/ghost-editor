#!/usr/bin/env python3
"""Per-frame head pose proxies from YuNet landmarks on a cut (every frame).
yaw = (nose_x - eye_mid_x) / eye_dist ; pitch = (nose_y - eye_y) / eye_dist ; roll = eye-line angle.
Flags runs where yaw/pitch leave the speaker's own median band. usage: headpose.py <video> <edl_map.json>"""
import cv2, numpy as np, json, sys, os
MODEL = os.path.expanduser("~/.claude/skills/ghost-editor/library/models/face_detection_yunet_2023mar.onnx")
cap = cv2.VideoCapture(sys.argv[1]); fps = cap.get(cv2.CAP_PROP_FPS)
det = None; rows = []
i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    f = cv2.resize(f, (360, 640))
    if det is None: det = cv2.FaceDetectorYN.create(MODEL, "", (360, 640), 0.5)
    _, faces = det.detect(f)
    t = i / fps; i += 1
    if faces is None: rows.append((t, None, None, None)); continue
    x = faces[0]; re_, le, no = x[4:6], x[6:8], x[8:10]
    mid = (re_ + le) / 2; d = np.linalg.norm(le - re_)
    rows.append((t, (no[0] - mid[0]) / d, (no[1] - mid[1]) / d, np.degrees(np.arctan2(le[1] - re_[1], le[0] - re_[0]))))
y = np.array([r[1] for r in rows if r[1] is not None]); p = np.array([r[2] for r in rows if r[2] is not None])
ym, ys = np.median(y), 1.4826 * np.median(np.abs(y - np.median(y))); pm, ps = np.median(p), 1.4826 * np.median(np.abs(p - np.median(p)))
print(f"yaw median {ym:.3f} mad-sd {ys:.3f} | pitch median {pm:.3f} mad-sd {ps:.3f} | {len(rows)} frames")
edl = json.load(open(sys.argv[2], encoding="utf-8"))
def seg(t):
    for s in edl:
        if s["start"] <= t < s["end"]: return s
bad = [(t, a, b) for t, a, b, _ in rows if a is None or abs(a - ym) > max(0.05, 2.5 * ys) or abs(b - pm) > max(0.07, 2.5 * ps)]
runs = []
for t, a, b in bad:
    if runs and t - runs[-1][1] <= 0.15: runs[-1][1] = t; runs[-1][2].append((a, b))
    else: runs.append([t, t, [(a, b)]])
for r0, r1, v in runs:
    if r1 - r0 < 0.1: continue
    s = seg(r0); ya = [a for a, b in v if a is not None]; pa = [b for a, b in v if b is not None]
    print(f"{r0:6.2f}-{r1:6.2f} ({r1-r0:.2f}s) seg {s['i']} orig {s['a'] + r0 - s['start']:.2f}  yaw {max(ya, key=lambda q: abs(q-ym)) if ya else 'LOST':.3}  pitch {max(pa, key=lambda q: abs(q-pm)) if pa else 0:.3}")
json.dump([[float(v) if v is not None else None for v in r] for r in rows], open("build/headpose.json", "w", encoding="utf-8"))
