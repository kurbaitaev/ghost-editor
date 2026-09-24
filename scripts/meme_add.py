#!/usr/bin/env python3
"""Add a reaction meme to the library: a transparent video clip (with its own
sound) or a still image.

    meme_add.py <id> <url-or-file> [--in 3.2] [--out 5.0] [--key green|blue|none|auto]
                [--w 360] [--tags "disbelief,fail"] [--use "when the plan fails"]
                [--triggers "no way,what"] [--sfx vine-boom] [--trend hot|evergreen|dying]
                [--no-audio] [--name "Surprised Pikachu"]

url: anything yt-dlp reads (YouTube green-screen meme uploads work well);
file: a local mp4/mov/webm/gif/png/jpg.

A video is trimmed to [in, out], keyed (green/blue screen -> alpha; auto
samples the corner pixels), scaled to --w px wide (default 360; the reaction
slot is ~320-380 px), and written as VP9-with-alpha WebM, audio peak-normalized
to -1 dBFS in Opus. HyperFrames renders its alpha (verified). A still is
saved as PNG and gets --sfx as its sound (default: vine-boom if your kit has it, else a licensed boom).

Writes library/memes/<id>/{clip.webm|image.png, preview.png, meta.json}.
ALWAYS look at preview.png before using a new meme: a bad key (green fringe,
holes in the face) is obvious there.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "library", "memes")
STILL = (".png", ".jpg", ".jpeg", ".webp")


def sh(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def fetch(src, td):
    if os.path.exists(src):
        return os.path.abspath(src), src
    r = subprocess.run(["yt-dlp", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
                        "--no-playlist", "-o", os.path.join(td, "src.%(ext)s"), "--print", "after_move:filepath", src],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"yt-dlp failed: {r.stderr.strip()[-400:]}")
    return r.stdout.strip().splitlines()[-1], src


def corner_color(path, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-vf", "scale=64:64",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    px = [raw[(y * 64 + x) * 3:(y * 64 + x) * 3 + 3] for x, y in ((1, 1), (62, 1), (1, 62), (62, 62))]
    r, g, b = (sum(p[i] for p in px) / 4 for i in range(3))
    return r, g, b


def alpha_bbox(path, t_in, t_out, vf):
    w, h = map(int, sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path]).stdout.strip().split(","))
    if vf and vf[0].startswith("crop="):
        w, h = map(int, vf[0][5:].split(":")[:2])
    q = 4
    sw, sh_ = w // q, h // q
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t_in), "-to", str(t_out), "-i", path, "-vf",
                          ",".join(vf + ["fps=5", "format=rgba", "alphaextract", f"scale={sw}:{sh_}"]), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    n = sw * sh_
    xs, ys = [], []
    for f in range(len(raw) // n):
        fr = raw[f * n:(f + 1) * n]
        for y in range(0, sh_, 2):
            row = fr[y * sw:(y + 1) * sw]
            hit = [x for x in range(0, sw, 2) if row[x] > 128]
            if hit:
                xs += [hit[0], hit[-1]]
                ys.append(y)
    if not xs:
        return None
    x0, x1, y0, y1 = max(0, min(xs) * q - q), min(w, max(xs) * q + 2 * q), max(0, min(ys) * q - q), min(h, max(ys) * q + 2 * q)
    x0, y0 = x0 // 2 * 2, y0 // 2 * 2
    return x0, y0, (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("src")
    ap.add_argument("--in", dest="t_in", type=float, default=0.0)
    ap.add_argument("--out", dest="t_out", type=float)
    ap.add_argument("--key", default="auto", choices=["auto", "green", "blue", "none"])
    ap.add_argument("--similarity", type=float, default=0.16)
    ap.add_argument("--w", type=int, default=360)
    ap.add_argument("--tags", default="")
    ap.add_argument("--use", default="")
    ap.add_argument("--triggers", default="")
    ap.add_argument("--sfx", default=None)
    ap.add_argument("--trend", default="evergreen", choices=["hot", "evergreen", "dying"])
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--name", default="")
    ap.add_argument("--crop", default=None, help="w:h:x:y in source pixels, applied before keying (e.g. a caption band)")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", a.id):
        sys.exit("id: lowercase, digits and dashes only")
    out = os.path.join(LIB, a.id)
    os.makedirs(out, exist_ok=True)
    meta = {"id": a.id, "name": a.name or a.id.replace("-", " "), "emotion": [t.strip() for t in a.tags.split(",") if t.strip()],
            "use_case": a.use, "trigger_phrases": [t.strip() for t in a.triggers.split(",") if t.strip()],
            "trend_status": a.trend, "added": datetime.date.today().isoformat(), "w": a.w}
    with tempfile.TemporaryDirectory() as td:
        path, origin = fetch(a.src, td)
        meta["source_url"] = origin
        if path.lower().endswith(STILL):
            sh(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", ",".join(([f"crop={a.crop}"] if a.crop else []) + [f"scale={a.w * 2}:-2"]), "-update", "1", os.path.join(out, "image.png")])
            sh(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(out, "image.png"), "-vf", "scale=360:-2", "-update", "1", os.path.join(out, "preview.png")])
            meta.update(image="image.png", has_alpha=False, has_audio=False, **({"sfx": a.sfx} if a.sfx else {}))
        else:
            dur_src = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout)
            t_out = min(a.t_out or dur_src, dur_src)
            key = a.key
            if key == "auto":
                r, g, b = corner_color(path, a.t_in + 0.1)
                key = "green" if g > 150 and g > r * 1.5 and g > b * 1.5 else "blue" if b > 150 and b > r * 1.5 and b > g * 1.2 else "none"
                print(f"corner colour rgb({r:.0f},{g:.0f},{b:.0f}) -> key {key}")
            vf = [f"crop={a.crop}"] if a.crop else []
            if key == "green":
                vf += [f"chromakey=0x00d000:{a.similarity}:0.08", "despill=type=green"]
            elif key == "blue":
                vf += [f"chromakey=0x0047bb:{a.similarity}:0.08", "despill=type=blue"]
            if key != "none":
                # crop to the subject: union of the alpha bounding box over the clip (5 fps, quarter size), plus a margin
                box = alpha_bbox(path, a.t_in, t_out, vf)
                if box:
                    cx, cy, cw, ch = box
                    m = 12
                    vf += ["format=yuva420p", f"pad=iw+{2 * m}:ih+{2 * m}:{m}:{m}:color=black@0", f"crop={cw + 2 * m}:{ch + 2 * m}:{cx}:{cy}"]
                    print(f"subject box {cw}x{ch} at {cx},{cy}")
            vf += [f"scale={a.w * 2}:-2", "format=yuva420p"]
            has_audio = not a.no_audio and "audio" in sh(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path]).stdout
            vcodec = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2.5M", "-auto-alt-ref", "0"]
            dst = os.path.join(out, "clip.webm")
            if has_audio:
                tmp = os.path.join(td, "a.wav")
                sh(["ffmpeg", "-v", "error", "-y", "-ss", str(a.t_in), "-to", str(t_out), "-i", path, "-vn", "-ac", "2", "-ar", "48000", tmp])
                peak = float(re.search(r"max_volume: (-?[\d.]+) dB", sh(["ffmpeg", "-hide_banner", "-nostats", "-i", tmp, "-af", "volumedetect", "-f", "null", "-"]).stderr).group(1))
                sh(["ffmpeg", "-v", "error", "-y", "-ss", str(a.t_in), "-to", str(t_out), "-i", path, "-i", tmp,
                    "-map", "0:v", "-map", "1:a", "-vf", ",".join(vf), *vcodec,
                    "-af", f"volume={-1 - peak}dB", "-c:a", "libopus", "-b:a", "128k", "-shortest", dst])
            else:
                sh(["ffmpeg", "-v", "error", "-y", "-ss", str(a.t_in), "-to", str(t_out), "-i", path, "-vf", ",".join(vf), *vcodec, "-an", dst])
            # preview: a mid frame over a checkerboard so holes and fringes show
            mid = (t_out - a.t_in) / 2
            frame = os.path.join(td, "frame.png")
            sh(["ffmpeg", "-v", "error", "-y", "-c:v", "libvpx-vp9", "-ss", str(mid), "-i", os.path.join(out, "clip.webm"),
                "-frames:v", "1", "-pix_fmt", "rgba", "-update", "1", frame])
            sh(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=720x1280", "-i", frame, "-filter_complex",
                "[1:v]scale=720:-2[m];[0:v][m]overlay=(W-w)/2:(H-h)/2,scale=360:-2", "-frames:v", "1", "-update", "1",
                os.path.join(out, "preview.png")])
            meta.update(clip="clip.webm", duration=round(t_out - a.t_in, 3), has_alpha=key != "none", key=key, has_audio=has_audio)
            if a.sfx:
                meta["sfx"] = a.sfx
    # everything needed to rebuild this entry from its source (library_restore.py)
    meta["args"] = {k: v for k, v in {"in": a.t_in, "out": a.t_out, "key": a.key, "similarity": a.similarity, "w": a.w,
                                      "crop": a.crop, "no_audio": a.no_audio}.items() if v not in (None, False)}
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=2)
    print(json.dumps(meta, indent=2))
    print(f"\nlook at {os.path.join(out, 'preview.png')} (magenta = transparent) before using it")


if __name__ == "__main__":
    main()
