#!/usr/bin/env python3
"""Per-frame on-camera quality of a whole recording: head yaw/pitch/roll (deg) + gaze/blink blendshapes (0..1)
from MediaPipe FaceLandmarker (IMAGE mode, no tracking lag). Writes build/facescan.json rows:
[t, yaw, pitch, roll, lookDown, lookUp, lookOutL/R max, lookIn max, blink] (None when no face).
usage: facescan.py <video> <out.json> [step=1]"""
import cv2, numpy as np, json, sys, os
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
MODEL = os.path.expanduser("~/.claude/skills/ghost-editor/library/models/face_landmarker.task")
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=MODEL),
     running_mode=vision.RunningMode.IMAGE, output_facial_transformation_matrixes=True, output_face_blendshapes=True, num_faces=1))
src, out = sys.argv[1], sys.argv[2]; step = int(sys.argv[3]) if len(sys.argv) > 3 else 1
cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS); rows = []; i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    if i % step == 0:
        h, w = f.shape[:2]; f = cv2.resize(f, (540, int(540 * h / w)))
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
        if r.facial_transformation_matrixes:
            R = np.array(r.facial_transformation_matrixes[0])[:3, :3]
            b = {c.category_name: c.score for c in r.face_blendshapes[0]}
            rows.append([round(i / fps, 3),
                         round(float(np.degrees(np.arctan2(-R[2, 0], np.hypot(R[2, 1], R[2, 2])))), 2),
                         round(float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))), 2),
                         round(float(np.degrees(np.arctan2(R[1, 0], R[0, 0]))), 2),
                         round((b["eyeLookDownLeft"] + b["eyeLookDownRight"]) / 2, 3), round((b["eyeLookUpLeft"] + b["eyeLookUpRight"]) / 2, 3),
                         round(max(b["eyeLookOutLeft"], b["eyeLookOutRight"]), 3), round(max(b["eyeLookInLeft"], b["eyeLookInRight"]), 3),
                         round((b["eyeBlinkLeft"] + b["eyeBlinkRight"]) / 2, 3)])
        else:
            rows.append([round(i / fps, 3)] + [None] * 8)
    i += 1
json.dump(rows, open(out, "w", encoding="utf-8"))
print(f"{len(rows)} frames -> {out}")
