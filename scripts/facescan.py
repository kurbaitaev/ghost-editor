#!/usr/bin/env python3
"""Per-frame on-camera quality of a whole recording (MediaPipe FaceLandmarker, IMAGE mode: no tracking lag).
Rows: [t, yaw, pitch, roll, lookDown, lookUp, lookOut (max L/R), lookIn (max L/R), blink, nose_x, nose_y, eye_dist, jawOpen]
(degrees; blendshapes 0..1; nose / eye distance in pixels of a 1080-wide frame; 12 Nones when there is no face).
Scans made before Oct 2026 have 9 columns (no nose/eyes/jaw): read rows with matrix(), which pads them to one width.

    facescan.py <video> <out.json> [step=1] [--pts SRC]

--pts SRC: row times = the TRUE presentation times of SRC's video frames (SRC = the recording the audio and words come
from; <video> is usually its 1080 proxy, same frames). Phone cameras run slow (e.g. 29.9935 fps): index/30 drifts up to
0.16 s over 12 min. Warns when the scan and SRC differ in frame count.
Importable with numpy only: matrix(rows), runs(mask, n), badframes(V, med) (the take-relative visual rules)."""
import argparse, json, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = next((p for p in (os.path.join(HERE, "..", "library", "models", "face_landmarker.task"),
                          os.path.expanduser("~/.claude/skills/ghost-editor/library/models/face_landmarker.task")) if os.path.exists(p)),
             os.path.join(HERE, "..", "library", "models", "face_landmarker.task"))


def matrix(F, cols=None):
    """facescan rows -> (T, V): frame times and an (n, cols) float matrix, NaN for no-face rows; any row width"""
    cols = cols or max([len(r) for r in F if r[1] is not None] or [13]) - 1
    T = np.array([r[0] for r in F], float)
    V = np.array([[np.nan] * cols if r[1] is None else (list(r[1:]) + [np.nan] * cols)[:cols] for r in F], float).reshape(len(F), cols)
    return T, V


def runs(m, minlen):
    """keep only True runs of at least minlen frames"""
    o = np.zeros_like(m); k = 0
    while k < len(m):
        if m[k]:
            j = k
            while j + 1 < len(m) and m[j + 1]: j += 1
            if j - k + 1 >= minlen: o[k:j + 1] = True
            k = j + 1
        else: k += 1
    return o


def badframes(V, med):
    """per-frame problems inside one take against the take's own speech baseline `med`:
    turn  = head yaw off its take median by > 4 deg (looking away); a nod (pitch) alone is natural speech
    glance= eyes drop (lookDown up > 0.18, not a blink): reading the script
    side  = eyes move sideways while the head holds still (a head move with the eyes held on the lens is compensation)
    closed= eyes shut >= 7 frames; tilt = roll > 5 deg; big = pitch > 9 deg (a real head drop)"""
    yaw, pit, rol, dn, out_, in_, bl = V[:, 0], V[:, 1], V[:, 2], V[:, 3], V[:, 5], V[:, 6], V[:, 7]
    side = np.maximum(out_, in_); mside = np.nanmax([med[5], med[6]])
    blink = bl > 0.35
    still = (np.abs(yaw - med[0]) < 2) & (np.abs(pit - med[1]) < 4)
    K = {"noface": np.isnan(yaw),
         "turn": runs(np.abs(yaw - med[0]) > 4, 3),
         "glance": runs((dn - med[3] > 0.18) & ~blink, 2),
         "side": runs((np.abs(side - mside) > 0.15) & still, 3),
         "closed": runs(blink, 7),
         "tilt": runs(np.abs(rol - med[2]) > 5, 3),
         "big": runs(np.abs(pit - med[1]) > 9, 3)}
    return K


def pts_times(src):
    """true presentation times (s) of src's video frames, in the audio's time base (the file's start time subtracted)"""
    q = lambda *a: subprocess.run(["ffprobe", "-v", "error", *a, "-of", "csv=p=0", src], capture_output=True, text=True).stdout
    num, den = map(int, q("-select_streams", "v:0", "-show_entries", "stream=time_base").split()[0].strip(",").split("/"))
    st = (q("-show_entries", "format=start_time").split() or ["0"])[0].strip(",")
    start = float(st) if st.lstrip("-").replace(".", "", 1).isdigit() else 0.0
    pk = [x.strip(",") for x in q("-select_streams", "v:0", "-show_entries", "packet=pts").split()]
    return [p - start for p in sorted(int(x) * num / den for x in pk if x.lstrip("-").isdigit())]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("out"); ap.add_argument("step", nargs="?", type=int, default=1)
    ap.add_argument("--pts", help="rewrite row times to the true frame times of this file (the source recording)")
    a = ap.parse_args()
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=MODEL),
         running_mode=vision.RunningMode.IMAGE, output_facial_transformation_matrixes=True, output_face_blendshapes=True, num_faces=1))
    cap = cv2.VideoCapture(a.video); fps = cap.get(cv2.CAP_PROP_FPS); rows, idx = [], []; i = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        if i % a.step == 0:
            h, w = f.shape[:2]; f = cv2.resize(f, (540, int(540 * h / w)))
            r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
            if r.facial_transformation_matrixes:
                R = np.array(r.facial_transformation_matrixes[0])[:3, :3]
                b = {c.category_name: c.score for c in r.face_blendshapes[0]}
                L = r.face_landmarks[0]; W, H = 1080, 1080 * h / w
                ed = np.hypot((L[33].x - L[263].x) * W, (L[33].y - L[263].y) * H)
                rows.append([round(i / fps, 3),
                             round(float(np.degrees(np.arctan2(-R[2, 0], np.hypot(R[2, 1], R[2, 2])))), 2),
                             round(float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))), 2),
                             round(float(np.degrees(np.arctan2(R[1, 0], R[0, 0]))), 2),
                             round((b["eyeLookDownLeft"] + b["eyeLookDownRight"]) / 2, 3), round((b["eyeLookUpLeft"] + b["eyeLookUpRight"]) / 2, 3),
                             round(max(b["eyeLookOutLeft"], b["eyeLookOutRight"]), 3), round(max(b["eyeLookInLeft"], b["eyeLookInRight"]), 3),
                             round((b["eyeBlinkLeft"] + b["eyeBlinkRight"]) / 2, 3),
                             round(L[1].x * W, 1), round(L[1].y * H, 1), round(float(ed), 1), round(b["jawOpen"], 3)])
            else:
                rows.append([round(i / fps, 3)] + [None] * 12)
            idx.append(i)
        i += 1
        if i % 1800 == 0: print(f"{i} frames", flush=True)
    if a.pts:
        pts = pts_times(a.pts)
        if len(pts) != i: print(f"WARNING: {a.video} has {i} frames, {a.pts} has {len(pts)}: row times past the shorter one are index/fps")
        for r, k in zip(rows, idx):
            if k < len(pts): r[0] = round(pts[k], 4)
        print(f"true frame times from {a.pts}: drift at the last frame {pts[-1] - (len(pts) - 1) / 30:+.3f} s vs index/30")
    json.dump(rows, open(a.out, "w"))
    print(f"{len(rows)} frames -> {a.out}")


if __name__ == "__main__":
    main()
