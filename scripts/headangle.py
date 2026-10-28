#!/usr/bin/env python3
"""Per-frame head angles (yaw/pitch/roll, degrees) with MediaPipe FaceLandmarker's transformation matrix.
Flags frames visible in the final edit where the head leaves the speaker's own band, or rotates fast.
usage: headangle.py <cut.mp4> <edl_map.json> [hidden.json]"""
import cv2, numpy as np, json, sys, os
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
MODEL = os.path.expanduser("~/.claude/skills/ghost-editor/library/models/face_landmarker.task")
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL), running_mode=vision.RunningMode.VIDEO,
    output_facial_transformation_matrixes=True, num_faces=1))
src, edl = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8")); hidden = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else []
cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS); rows = []; i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    f = cv2.resize(f, (540, 960))
    r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)), int(i * 1000 / fps))
    if r.facial_transformation_matrixes:
        R = np.array(r.facial_transformation_matrixes[0])[:3, :3]
        yaw = np.degrees(np.arctan2(-R[2, 0], np.hypot(R[2, 1], R[2, 2])))
        pitch = np.degrees(np.arctan2(R[2, 1], R[2, 2])); roll = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
        rows.append([i / fps, float(yaw), float(pitch), float(roll)])
    else:
        rows.append([i / fps, None, None, None])
    i += 1
json.dump(rows, open("build/headangle.json", "w", encoding="utf-8"))
A = np.array([[r[1], r[2], r[3]] for r in rows if r[1] is not None])
med = np.median(A, 0); sd = 1.4826 * np.median(np.abs(A - med), 0)
print(f"{len(rows)} frames; median yaw {med[0]:.1f} pitch {med[1]:.1f} roll {med[2]:.1f}; robust sd {sd[0]:.1f} {sd[1]:.1f} {sd[2]:.1f} deg")
