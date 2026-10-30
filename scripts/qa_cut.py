#!/usr/bin/env python3
"""QA of a rendered raw cut against its plan: (1) face problems on every output frame (raw facescan rows mapped through
the plan, each piece against its own baseline: facescan.badframes), (2) pauses > 0.30 s inside speech from the cut's own
audio, (3) the silence at every join, (4) a cut sheet: the 3 frames before / after every cut (face crop).

    qa_cut.py <cut.mp4> --plan build/plan.json --facescan build/facescan.json [--out build/qa.json] [--sheet build/cutsheet.jpg]

<cut.mp4> = assemble.py's build/rawcut.mp4 (or any render of exactly this plan, with its voice)."""
import argparse, json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from facescan import badframes, matrix
FPS = 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cut"); ap.add_argument("--plan", required=True); ap.add_argument("--facescan", required=True)
    ap.add_argument("--out"); ap.add_argument("--sheet")
    A = ap.parse_args()
    import cv2
    out = A.out or os.path.join(os.path.dirname(os.path.abspath(A.plan)), "qa.json")
    sheetp = A.sheet or os.path.join(os.path.dirname(os.path.abspath(out)), "cutsheet.jpg")
    P = json.load(open(A.plan))["pieces"]
    FT, V = matrix(json.load(open(A.facescan)))
    report = {"cut": os.path.abspath(A.cut), "pieces": []}
    sr = 16000
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", A.cut, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                                     capture_output=True, check=True).stdout, np.float32)
    hop = sr // 100; db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop * 2) / (hop * 2), "same"))[::hop] + 1e-9)
    TH = np.percentile(db, 10) + 14
    print(f"{A.cut}: {len(P)} pieces, {P[-1]['edit'] + P[-1]['b'] - P[-1]['a']:.2f} s")
    nbad = 0
    for k, p in enumerate(P):
        va, vb = p.get("va", p["a"]), p.get("vb", p["b"])
        m = (FT >= va - 1e-3) & (FT < vb - 1e-3); sp = (FT >= p["s0"]) & (FT <= p["s1"])
        K = badframes(V[m], np.nanmedian(V[sp], 0)) if m.any() else {}
        ve = p["edit"] - (P[k - 1].get("vearly", 0) / FPS if k else 0)     # edit time of this piece's first video frame
        ev = sorted({(n, round(float(FT[m][i] - va + ve), 2)) for n, v in K.items() for i in np.where(v)[0]}, key=lambda e: e[1])
        e0, e1 = p["edit"], p["edit"] + p["b"] - p["a"]
        seg = db[int(e0 * 100):int(e1 * 100)]; on = seg > TH
        idx = np.where(on)[0]; pauses = []
        if len(idx):
            g = np.diff(idx)
            for j in np.where(g > 30)[0]: pauses.append((round(e0 + idx[j] / 100, 2), round((g[j] - 1) / 100, 2)))
        report["pieces"].append({"k": k, "edit": [round(e0, 2), round(e1, 2)], "events": ev, "pauses": pauses, "note": p["note"]})
        msg = []
        if ev: msg.append("FACE " + ", ".join(f"{n}@{t}" for n, t in ev[:8]) + (" ..." if len(ev) > 8 else ""))
        if pauses: msg.append("PAUSE " + ", ".join(f"{d:.2f}s@{t}" for t, d in pauses))
        nbad += bool(msg)
        print(f"  [{k:2d}] {e0:6.2f}-{e1:6.2f} {p['note']:6s} {'OK' if not msg else ' | '.join(msg)}")
    # silence at every join (speech-free time either side of the cut, within 0.6 s)
    report["joins"] = []
    for k in range(len(P) - 1):
        t = P[k + 1]["edit"]; w = db[max(int((t - 0.6) * 100), 0):int((t + 0.6) * 100)] > TH
        left = np.where(w[:60])[0]; right = np.where(w[60:])[0]
        gap = (60 - left[-1] if len(left) else 60) + (right[0] if len(right) else 60)
        report["joins"].append({"t": round(t, 2), "silence": round(gap / 100, 2)})
    print("  join silences:", " ".join(f"{j['t']:.1f}:{j['silence']:.2f}" for j in report["joins"]))
    # cut sheet: 3 frames before / 3 after each picture cut (face crop), from the rendered file
    cap = cv2.VideoCapture(A.cut); rows = []
    for k in range(1, len(P)):
        fi = round(P[k]["edit"] * FPS) - P[k - 1].get("vearly", 0); tiles = []
        for f in range(fi - 3, fi + 3):
            cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
            if not ok: im = np.zeros((1920, 1080, 3), np.uint8)
            im = cv2.resize(im, (1080, 1920)) if im.shape[:2] != (1920, 1080) else im
            crop = cv2.resize(im[560:1240, 140:940], (240, 204))
            cv2.putText(crop, f"{f / FPS:.2f}{' |' if f == fi else ''}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255) if f >= fi else (255, 255, 255), 1)
            tiles.append(crop)
        rows.append(np.hstack(tiles))
    if rows:
        sheet = np.vstack([np.hstack(rows[i:i + 2]) if i + 1 < len(rows) else np.hstack([rows[i], np.zeros_like(rows[i])]) for i in range(0, len(rows), 2)])
        cv2.imwrite(sheetp, sheet, [cv2.IMWRITE_JPEG_QUALITY, 80]); print("  cut sheet ->", sheetp)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(report, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"{nbad} of {len(P)} pieces flagged -> {out}")


if __name__ == "__main__":
    main()
