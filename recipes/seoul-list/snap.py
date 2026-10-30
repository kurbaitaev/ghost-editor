#!/usr/bin/env python3
"""Seoul list: look at every block before and after the render.

    snap.py beats   $P [--ids b2,b3] [--shots]      snapshot each beat's key times (build/beats.json) -> build/snaps/
    snap.py strips  $P RENDER.mp4 [--ids ...]       the same frames from a render -> build/strips/<id>-<type>.jpg
    snap.py compare REF.mp4 RENDER.mp4 --pairs "label=refT:ourT[,ourT2];..." -o DIR   side-by-side sheets per block
    snap.py cuts    $P RENDER.mp4                    PSNR of the render vs the proxy at the first frame of every shot

beats/strips write one labelled strip per beat (all its key times) plus overview.jpg (one frame per beat). Look at the
strips: text clipped or wrapped, stickers off the frame, a card landing on a face, a white page with nothing on it.
compare: for each pair one image, reference frame(s) left, ours right, plus all.jpg stacking every pair.
cuts: every shot's first frame in the render must match the proxy frame its in-point names (the frame-exact check;
under ~30 dB means a wrong frame or something covering the shot, which a scene does on purpose).
Snapshots go through the pinned HyperFrames CLI (scripts/HF_VERSION; an HF_VERSION env var overrides it), no Gemini description.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from hf_version import hf  # noqa: E402


def font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def label(im, text, size=26):
    d = ImageDraw.Draw(im)
    f = font(size)
    w = d.textlength(text, font=f)
    d.rectangle([0, 0, w + 16, size + 12], fill=(0, 0, 0))
    d.text((8, 5), text, fill=(255, 220, 0), font=f)
    return im


def strip(frames, title, h=640):
    ims = [label(Image.open(p).convert("RGB").resize((h * 9 // 16, h)), f"{t:.2f}s") for t, p in frames]
    out = Image.new("RGB", (sum(i.width for i in ims) + 6 * (len(ims) - 1), h + 44), (24, 24, 24))
    label(out, title, 28)
    x = 0
    for i in ims:
        out.paste(i, (x, 44))
        x += i.width + 6
    return out


def grid(ims, cols, bg=(24, 24, 24)):
    w = max(i.width for i in ims)
    rows = [ims[k:k + cols] for k in range(0, len(ims), cols)]
    hs = [max(i.height for i in r) for r in rows]
    out = Image.new("RGB", (w * cols, sum(hs)), bg)
    y = 0
    for r, hh in zip(rows, hs):
        for c, i in enumerate(r):
            out.paste(i, (c * w, y))
        y += hh
    return out


def load(P, ids):
    b = json.load(open(os.path.join(P, "build", "beats.json")))
    beats = [x for x in b["beats"] if not ids or x["id"] in ids]
    return b, beats


def snapshot(P, times, out):
    os.makedirs(out, exist_ok=True)
    at = ",".join(f"{t:.3f}" for t in times)
    r = subprocess.run(hf("snapshot", "--at", at, "--no-end", "--describe", "false", "-o", out),
                       cwd=P, capture_output=True, text=True)
    if r.returncode:
        sys.exit("snapshot failed: " + (r.stderr or r.stdout)[-800:])
    files = sorted(f for f in os.listdir(out) if f.startswith("frame-") and f.endswith(".png"))
    got = {}
    for f in files:  # frame-NN-at-T s.png
        t = float(f.split("-at-")[1][:-5])
        got[round(t, 3)] = os.path.join(out, f)
    return got


def extract(video, times, out):
    os.makedirs(out, exist_ok=True)
    got = {}
    for t in times:
        p = os.path.join(out, f"f-{t:07.3f}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-update", "1", p], check=True)
        got[round(t, 3)] = p
    return got


def sheets(beats, frames, out_dir, shots=None):
    os.makedirs(out_dir, exist_ok=True)
    over = []
    for b in beats:
        fr = [(t, frames[round(t, 3)]) for t in b["keys"] if round(t, 3) in frames]
        if not fr:
            continue
        s = strip(fr, f"{b['id']} {b['type']}  {b['t0']:.2f}-{b['t1']:.2f}s  {b['label'][:40]}")
        p = os.path.join(out_dir, f"{b['id']}-{b['type']}.jpg")
        s.save(p, quality=86)
        mid = fr[len(fr) // 2]
        over.append(label(Image.open(mid[1]).convert("RGB").resize((270, 480)), f"{b['id']} {b['type']}", 20))
        print(f"  {p}")
    if shots:
        for s in shots:
            t = round((s["t0"] + s["t1"]) / 2, 3)
            if t in frames:
                over.append(label(Image.open(frames[t]).convert("RGB").resize((270, 480)), f"shot {s['i']} {s['clip']}", 20))
    if over:
        grid(over, 8).save(os.path.join(out_dir, "overview.jpg"), quality=86)
        print(f"  {os.path.join(out_dir, 'overview.jpg')}")


def cmd_beats(a):
    P = os.path.abspath(a.project)
    b, beats = load(P, a.ids)
    times = sorted({round(t, 3) for x in beats for t in x["keys"]} | ({round((s["t0"] + s["t1"]) / 2, 3) for s in b["shots"]} if a.shots else set()))
    print(f"snapshotting {len(times)} times for {len(beats)} beats...")
    frames = snapshot(P, times, os.path.join(P, "build", "snaps", "raw"))
    sheets(beats, frames, os.path.join(P, "build", "snaps"), b["shots"] if a.shots else None)


def cmd_strips(a):
    P = os.path.abspath(a.project)
    b, beats = load(P, a.ids)
    times = sorted({round(t, 3) for x in beats for t in x["keys"]} | {round((s["t0"] + s["t1"]) / 2, 3) for s in b["shots"]})
    frames = extract(os.path.abspath(a.video), times, os.path.join(P, "build", "strips", "raw"))
    sheets(beats, frames, os.path.join(P, "build", "strips"), b["shots"])


def cmd_compare(a):
    os.makedirs(a.out, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory() as td:
        for k, pair in enumerate(p for p in a.pairs.split(";") if p.strip()):
            name, spec = pair.split("=", 1)
            ref, ours = spec.split(":", 1)
            rt = [float(x) for x in ref.split(",")]
            ot = [float(x) for x in ours.split(",")]
            fr = extract(a.ref, rt, os.path.join(td, f"r{k}"))
            fo = extract(a.render, ot, os.path.join(td, f"o{k}"))
            h = 640
            L = [label(Image.open(fr[round(t, 3)]).convert("RGB").resize((h * 9 // 16, h)), f"reference {t:.2f}s") for t in rt]
            R = [label(Image.open(fo[round(t, 3)]).convert("RGB").resize((h * 9 // 16, h)), f"smoke {t:.2f}s") for t in ot]
            n = len(L) + len(R)
            out = Image.new("RGB", (n * (h * 9 // 16) + 40 + 6 * n, h + 48), (24, 24, 24))
            label(out, name.strip(), 30)
            x = 0
            for i, im in enumerate(L + R):
                if i == len(L):
                    x += 40
                out.paste(im, (x, 48))
                x += im.width + 6
            p = os.path.join(a.out, f"{k:02d}-{name.strip().split()[0].lower()}.jpg")
            out.save(p, quality=86)
            rows.append(out)
            print(f"  {p}")
    w = max(r.width for r in rows)
    allim = Image.new("RGB", (w, sum(r.height for r in rows)), (24, 24, 24))
    y = 0
    for r in rows:
        allim.paste(r, (0, y))
        y += r.height
    allim.save(os.path.join(a.out, "all.jpg"), quality=82)
    print(f"  {os.path.join(a.out, 'all.jpg')}")


def cmd_cuts(a):
    import numpy as np
    P = os.path.abspath(a.project)
    b = json.load(open(os.path.join(P, "build", "beats.json")))
    fps = b["fps"]
    spec = json.load(open(os.path.join(P, "list.json")))
    clips = spec.get("clips", "clips")
    rd = lambda f, t: np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.6f}", "-i", f, "-frames:v", "1", "-vf", "scale=270:480",
                                                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout, np.uint8).astype(float)
    print(" shot  edit t   clip       in      PSNR (render frame vs proxy frame; also +-1 frame)")
    for s in b["shots"]:
        cp = next((os.path.join(P, clips, s["clip"] + e) for e in (".mp4", ".mov", "") if os.path.exists(os.path.join(P, clips, s["clip"] + e))), None)
        t = s["t0"] + 0.5 / fps  # the middle of the shot's first frame
        o = rd(a.video, t)
        res = []
        for d in (0, -1, 1):
            p = rd(cp, s["in"] + (d + 0.5) / fps)
            mse = ((o - p) ** 2).mean() if len(o) == len(p) and len(o) else 1e9
            res.append(10 * np.log10(255 ** 2 / max(mse, 1e-9)))
        best = ["0", "-1", "+1"][int(np.argmax(res))]
        print(f" {s['i']:4d} {s['t0']:7.3f}   {s['clip']:10s} {s['in']:6.2f}   {res[0]:5.1f} dB  (-1: {res[1]:5.1f}, +1: {res[2]:5.1f})  best {best}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("beats"); p.add_argument("project"); p.add_argument("--ids", type=lambda s: set(s.split(","))); p.add_argument("--shots", action="store_true")
    p = sub.add_parser("strips"); p.add_argument("project"); p.add_argument("video"); p.add_argument("--ids", type=lambda s: set(s.split(",")))
    p = sub.add_parser("compare"); p.add_argument("ref"); p.add_argument("render"); p.add_argument("--pairs", required=True); p.add_argument("-o", "--out", required=True)
    p = sub.add_parser("cuts"); p.add_argument("project"); p.add_argument("video")
    a = ap.parse_args()
    {"beats": cmd_beats, "strips": cmd_strips, "compare": cmd_compare, "cuts": cmd_cuts}[a.cmd](a)


if __name__ == "__main__":
    main()
