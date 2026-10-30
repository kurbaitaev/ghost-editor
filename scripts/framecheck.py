#!/usr/bin/env python3
"""Seek-safety + flicker check for a HyperFrames project.

  python3 $S/scripts/framecheck.py <project> [--render build/reel.mp4] [--times 0.7,1.5,3.1] [--flicker-only]

1. Seek order: snapshot the same times twice in different orders (forward, then reversed with
   a far seek first) and compare the PNGs. A seek-safe layer gives identical (or ~identical)
   pixels. Reports max / mean abs diff per time.
2. Render vs snapshot: the render frame at round(t*fps) must match the snapshot at t
   (PSNR; the render is H.264 so it is not bit-exact).
3. Flicker: consecutive-frame mean abs diff d[i] over the whole render. A frame i that flickers
   differs from BOTH neighbours while the neighbours agree with each other:
       ratio[i] = (d(i-1,i) + d(i,i+1)) / 2 / max(d(i-1,i+1), floor)
   smooth motion gives ~0.5, a held frame 0..1, a one-frame flash/blank >> 1 (flag > 2.5).
   Also flags frames whose mean luma jumps away from both neighbours (blank / missed draw).
Writes <project>/build/framecheck.json and framecheck.png (the d[i] series).
"""
import argparse, json, os, re, subprocess, sys
import numpy as np
try:
    from PIL import Image, ImageDraw  # only for snapshots + the chart; --flicker-only works without it
except ImportError:  # pragma: no cover
    Image = ImageDraw = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hf_version import hf  # noqa: E402  (scripts/HF_VERSION)
HF = hf()


def snapshot(proj, times, out):
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        os.remove(os.path.join(out, f))
    subprocess.run([*HF, "snapshot", proj, "--at", ",".join(f"{t:g}" for t in times), "--no-end", "--describe", "false", "-o", out],
                   check=True, capture_output=True, text=True)
    res = {}
    for f in os.listdir(out):
        m = re.match(r"frame-\d+-at-([\d.]+)s\.png$", f)
        if m:
            ft = float(m.group(1))
            key = min(times, key=lambda t: abs(t - ft))  # file names round the time (e.g. 0.733s)
            if abs(key - ft) < 0.006:
                res[key] = np.asarray(Image.open(os.path.join(out, f)).convert("RGB"), dtype=np.int16)
    return res


def scan(video, w=540, h=960):
    """Stream the video once (constant memory): per-frame mean luma, d(i-1,i) and d(i-1,i+1)."""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
                         stdout=subprocess.PIPE)
    n = w * h
    prev2 = prev = None
    luma, d, d2 = [], [], []
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        f = np.frombuffer(buf, np.uint8).reshape(h, w).astype(np.float32)
        luma.append(float(f.mean()))
        if prev is not None:
            d.append(float(np.mean(np.abs(f - prev))))
        if prev2 is not None:
            d2.append(float(np.mean(np.abs(f - prev2))))
        prev2, prev = prev, f
    p.wait()
    return len(luma), np.array(d), np.array(d2), np.array(luma)


def frame_rgb(video, idx):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"select=eq(n\\,{idx})", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", video],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    return np.frombuffer(p.stdout, np.uint8).reshape(h, w, 3).astype(np.int16)


def psnr(a, b):
    mse = float(np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def chart(d, flags, path, fps):
    W, H, pad = 900, 260, 30
    img = Image.new("RGB", (W, H), (18, 18, 22))
    g = ImageDraw.Draw(img)
    mx = max(float(np.max(d)) if len(d) else 1, 1e-6)
    pts = [(pad + i * (W - 2 * pad) / max(1, len(d) - 1), H - pad - v / mx * (H - 2 * pad)) for i, v in enumerate(d)]
    g.line([(pad, H - pad), (W - pad, H - pad)], fill=(70, 70, 80))
    if len(pts) > 1:
        g.line(pts, fill=(255, 170, 60), width=2)
    for i in flags:
        x = pad + i * (W - 2 * pad) / max(1, len(d) - 1)
        g.line([(x, pad), (x, H - pad)], fill=(255, 60, 60), width=1)
    g.text((pad, 8), f"consecutive-frame mean abs diff (max {mx:.2f}), {len(d) + 1} frames @ {fps} fps; red = flagged", fill=(220, 220, 220))
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--render", default="renders/out.mp4")
    ap.add_argument("--times", default="0.7,1.5,3.1")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--flicker-only", action="store_true", help="skip the snapshot seek tests; only scan --render for flicker (for qa.py on a finished reel)")
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    # snap to the frame grid: a snapshot "at t" between two frames is not comparable to either
    times = [round(round(float(x) * a.fps) / a.fps, 4) for x in a.times.split(",")]
    build = os.path.join(proj, "build")
    os.makedirs(build, exist_ok=True)
    rep = {"project": proj}

    # 1. seek order
    A = {}
    if a.flicker_only:
        times = []
    A = snapshot(proj, times, os.path.join(build, "seekA")) if times else {}
    rev = ([max(times) + 0.5] + list(reversed(times))) if times else []
    B = snapshot(proj, rev, os.path.join(build, "seekB")) if times else {}
    seek = []
    for t in times:
        if t in A and t in B:
            diff = np.abs(A[t] - B[t])
            seek.append({"t": t, "max": int(diff.max()), "mean": round(float(diff.mean()), 4)})
    rep["seek_order"] = seek
    rep["seek_safe"] = (all(s["mean"] < 0.5 for s in seek) and len(seek) == len(times)) if times else None

    # 2 + 3. render
    video = a.render if os.path.isabs(a.render) else os.path.join(proj, a.render)
    if os.path.exists(video):
        cmp = []
        for t in times:
            idx = int(round(t * a.fps + 1e-6))
            if t not in A:
                continue
            ps = {}
            for k in (idx - 1, idx, idx + 1):
                fr = frame_rgb(video, k)
                if fr.shape == A[t].shape:
                    ps[k - idx] = round(psnr(fr, A[t]), 2)
            if ps:
                best = max(ps, key=ps.get)
                if 0 in ps and ps[best] - ps[0] < 0.2:
                    best = 0  # neighbours within 0.2 dB: motion too slow to tell, count as aligned
                cmp.append({"t": t, "frame": idx, "psnr": ps.get(0), "psnr_prev": ps.get(-1), "psnr_next": ps.get(1), "best_offset": best})
        rep["render_vs_snapshot"] = cmp
        rep["render_aligned"] = all(c["best_offset"] == 0 for c in cmp) if cmp else None
        n, d, d2, luma = scan(video, *((270, 480) if a.flicker_only else (540, 960)))
        floor = max(0.05, float(np.median(d)) * 0.25)
        flags = []
        ratios = []
        for i in range(1, n - 1):
            r = (d[i - 1] + d[i]) / 2 / max(d2[i - 1], floor)
            ratios.append(r)
            up, dn = luma[i] - luma[i - 1], luma[i] - luma[i + 1]
            # a one-frame spike: brighter (or darker) than BOTH neighbours; a fade/transition is monotonic
            jump = min(abs(up), abs(dn)) if up * dn > 0 else 0.0
            if (r > 2.5 and (d[i - 1] + d[i]) / 2 > 0.5) or jump > 6:
                flags.append({"frame": i, "t": round(i / a.fps, 3), "ratio": round(r, 2), "luma_jump": round(float(jump), 2)})
        rep["frames"] = n
        rep["diff_mean"] = round(float(d.mean()), 3)
        rep["diff_max"] = round(float(d.max()), 3)
        rep["ratio_max"] = round(float(max(ratios)) if ratios else 0, 2)
        rep["flicker_frames"] = flags
        rep["flicker_free"] = len(flags) == 0
        if ImageDraw is not None:
            chart(d, [f["frame"] for f in flags], os.path.join(build, "framecheck.png"), a.fps)
    json.dump(rep, open(os.path.join(build, "framecheck.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
