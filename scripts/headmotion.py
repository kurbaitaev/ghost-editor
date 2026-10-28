#!/usr/bin/env python3
"""Frame-accurate head-motion scan of a cut (every frame, 33 ms at 30 fps).
Dense optical flow on the UPPER head (forehead + eyes; the jaw is excluded so talking doesn't count), mean vector per
frame, then net displacement over sliding 0.2 / 0.4 s windows. A head turn = sustained, same-direction motion.
Only frames visible in the final edit are reported (windows covered by full-screen scenes are skipped).
usage: headmotion.py <cut.mp4> <edl_map.json> [hidden.json]   (hidden.json: [[t0,t1],...] scene windows)"""
import cv2, numpy as np, json, sys, os
MODEL = os.path.expanduser("~/.claude/skills/ghost-editor/library/models/face_detection_yunet_2023mar.onnx")
src, edl = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
hidden = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else []
cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS)
W, H = 540, 960
det = cv2.FaceDetectorYN.create(MODEL, "", (W, H), 0.5)
prev, rows, box = None, [], None
i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    f = cv2.resize(f, (W, H)); g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    _, faces = det.detect(f)
    if faces is not None:
        x, y, w, h = faces[0][:4]; ey = (faces[0][5] + faces[0][7]) / 2
        box = (int(x), int(y - 0.15 * h), int(w), int(ey + 0.12 * h - (y - 0.15 * h)))   # forehead .. just under the eyes
    seg = next((s for s in edl if s["start"] <= i / fps < s["end"]), None)
    newtake = seg is not None and abs(i / fps - seg["start"]) < 0.5 / fps
    if prev is not None and box is not None and not newtake:
        x, y, w, h = box
        a, b = prev[max(0, y):y + h, max(0, x):x + w], g[max(0, y):y + h, max(0, x):x + w]
        fl = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        dx, dy = float(np.median(fl[..., 0])), float(np.median(fl[..., 1]))
    else:
        dx = dy = 0.0
    rows.append((i / fps, dx, dy, seg["i"] if seg else -1)); prev = g; i += 1
t = np.array([r[0] for r in rows]); dx = np.array([r[1] for r in rows]); dy = np.array([r[2] for r in rows]); sg = [r[3] for r in rows]
def net(v, n): return np.convolve(v, np.ones(n), "same")
nx6, ny6, nx12, ny12 = net(dx, 6), net(dy, 6), net(dx, 12), net(dy, 12)
mag = np.maximum(np.hypot(nx6, ny6), np.hypot(nx12, ny12))
vis = np.array([not any(a <= tt <= b for a, b in hidden) for tt in t])
base = np.percentile(mag[vis], 50); thr = max(2.0, 4 * base)
print(f"{len(t)} frames @ {fps:.0f} fps; median 0.4 s head displacement {base:.2f}px (540w); flag > {thr:.2f}px")
flag = (mag > thr) & vis
runs, k = [], 0
while k < len(t):
    if flag[k]:
        j = k
        while j + 1 < len(t) and flag[j + 1]: j += 1
        pk = k + int(np.argmax(mag[k:j + 1]))
        runs.append((t[k], t[j], mag[pk], nx12[pk], ny12[pk], sg[pk]))
        k = j + 1
    else: k += 1
for a, b, m, x, y, s in sorted(runs, key=lambda r: -r[2]):
    seg = edl[s]; d = ("right" if x > 0 else "left") if abs(x) > abs(y) else ("down" if y > 0 else "up")
    print(f"{a:6.2f}-{b:6.2f} ({(b - a) * 1000:4.0f} ms) peak {m:5.1f}px {d:5s} seg {s:2d} orig {seg['a'] + a - seg['start']:.2f}  [{seg['note'][:28]}]")
json.dump({"t": t.tolist(), "mag": mag.tolist()}, open("build/headmotion.json", "w", encoding="utf-8"))
