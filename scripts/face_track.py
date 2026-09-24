#!/usr/bin/env python3
"""Track the speaker's face so captions never cover it.

    face_track.py <project>/assets/talk.mp4 --out <project>/build/face.json [--fps 5]

Runs OpenCV's YuNet detector (library/models/face_detection_yunet_2023mar.onnx,
fetched on first use, MIT licence) on a downscaled copy at --fps and writes,
in ORIGINAL-recording seconds and 1080x1920 frame pixels:

    {"fps": 5, "w": 1080, "h": 1920, "samples": [[t, top, bottom, left, right, eyes_y, mouth_y] | [t, null], ...]}

top/bottom/left/right is the face box grown to cover hair and chin (the raw
detector box stops at the brow and the mouth line). When several faces are in
frame the largest wins. Frames with no face are null; build.mjs holds the last
known box for short gaps. Needs python opencv (pip install opencv-python).
"""
import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "..", "library", "models", "face_detection_yunet_2023mar.onnx")
MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=5)
    a = ap.parse_args()
    try:
        import cv2
    except ImportError:
        sys.exit("opencv missing: pip install opencv-python")
    if not os.path.exists(MODEL):
        os.makedirs(os.path.dirname(MODEL), exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    cap = cv2.VideoCapture(a.src)
    fps, n = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    q = 4  # detect on a quarter-size frame: fast, and plenty for a talking head
    det = cv2.FaceDetectorYN.create(MODEL, "", (W // q, H // q), 0.6)
    step = max(1, round(fps / a.fps))
    samples, found = [], 0
    f = 0
    while f < n:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, fr = cap.read()
        if not ok:
            break
        _, faces = det.detect(cv2.resize(fr, (W // q, H // q)))
        t = round(f / fps, 3)
        if faces is None or not len(faces):
            samples.append([t, None])
        else:
            best = max(faces, key=lambda r: r[2] * r[3])
            x, y, w, h = best[:4] * q
            # YuNet landmarks: right eye, left eye, nose, right mouth corner, left mouth corner
            eyes_y = (best[5] + best[7]) / 2 * q
            mouth_y = (best[11] + best[13]) / 2 * q
            # grow: hair above the detector box, chin/beard below, ears at the sides
            top, bottom = y - 0.35 * h, y + h * 1.12
            left, right = x - 0.08 * w, x + w * 1.08
            samples.append([t, round(max(0, top)), round(min(H, bottom)), round(max(0, left)), round(min(W, right)), round(eyes_y), round(mouth_y)])
            found += 1
        f += step
    json.dump({"fps": a.fps, "w": W, "h": H, "samples": samples}, open(a.out, "w"))
    tops = [s[1] for s in samples if s[1] is not None]
    bots = [s[2] for s in samples if s[1] is not None]
    print(f"face in {found}/{len(samples)} samples; top {min(tops) if tops else '-'}-{max(tops) if tops else '-'}, "
          f"bottom {min(bots) if bots else '-'}-{max(bots) if bots else '-'} -> {a.out}")


if __name__ == "__main__":
    main()
