#!/usr/bin/env python3
"""cutout_fx.py: reel effects driven by one BiRefNet alpha pass.

One matting pass per clip window is cached (FFV1 grey alpha at the source size + meta.json); every effect reuses it.

  alpha    SRC --ss 15.6 --t 5.4 [--model lite@768]        compute / reuse the cached alpha, print its folder
  webm     SRC --ss .. --t .. -o talk-matte.webm             VP9+alpha cut-out (decontaminated edges) for HyperFrames
  bg-swap  SRC --ss .. --t .. --bg walk.png [--bg2 rays.mp4 --switch 18.57] -o out.mp4   new background, light wrap, colour match
  bg-blur  ... --radius 28                                   portrait-mode bokeh that racks in
  selective ... --look bw|noir|film                          speaker in colour, the world graded
  spotlight ... --dim 0.3                                    background dims, a light pool behind the head
  sticker  ... --freeze 16.4                                 freeze, die-cut white outline + shadow, pops and wiggles
  neon     ... --colors "#38f6ff,#ff3df2"                    neon outline traced around the silhouette
  clones   ... --offsets 0,0.4,0.8                           three matted copies, time-offset, side by side
  pop      ... --frame phone|card                            the speaker breaks out of a phone / card frame
  sandwich ... --behind "FEED@16.32" --front "ANXIOUS@17.44" --through "EVERYWHERE@20.04"   words behind, in front, walked through
  thumb    ... --headline "THE FEED|MAKES US|*ANGRIER*" -o cover   1080x1920 + 1280x720 covers
  still    IMG --model dis|cod|general|hr-matting|... --result white|checker|highlight|product|color -o out   input | alpha | result
  bench    SRC --ss .. --frames 30 --configs portrait@1024,lite@1024,lite@768,lite@512
  compare  SRC --ss .. --t .. --configs ... -o grid.mp4      the same window matted by several configs, 2x2

Times (--ss, --freeze, word@time, --switch) are SOURCE seconds, like reel.json. Output = the window's frame count
and fps (clones: minus the largest offset), H.264 yuv420p bt709, the source's audio (or --audio) for the same window.
--release S eases the effect back into the untouched source over the window's last S seconds (the last frame is the
source frame itself), so a window laid over a take hands back to it without a pop; sticker has its own drop-back.
build.mjs passes --ss as an exact source-frame time and --t half a frame short of the window, so ffmpeg's input seek
returns exactly the frames the take shows (see the cutout block in build.mjs).

Models (all MIT, huggingface.co/ZhengPeng7): portrait, general, lite, lite-2k, dis, cod, hrsod, hr, matting, hr-matting,
lite-matting, dynamic, dynamic-matting. A model spec is NAME[@SIZE], SIZE = 768 or 576x1024 (multiples of 32).
Weights: $CUTOUT_FX_CACHE/hf (or ~/.cache/ghost-matte/hf, shared with matte.py), downloaded on first use.
Refinement (temporal median3 + deadband EMA, guided upsample, blur-fusion decontamination) comes from matte.py.
"""
from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from x264 import THREADS as X264_THREADS  # noqa: E402  (scripts/X264_THREADS)
CACHE = Path(os.environ.get("CUTOUT_FX_CACHE") or os.environ.get("GHOST_MATTE_CACHE") or "~/.cache/ghost-matte").expanduser()
WEIGHT_DIRS = [CACHE / "hf", Path("~/.cache/ghost-matte/hf").expanduser()]
os.environ.setdefault("HF_MODULES_CACHE", str(CACHE / "hf-modules"))  # trust_remote_code copies birefnet.py here
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import cv2  # noqa: E402
import numpy as np  # noqa: E402


def _import_matte():
    for d in [os.environ.get("GHOST_SCRIPTS"), str(HERE), str(Path("~/.claude/skills/ghost-editor/scripts").expanduser())]:
        if d and (Path(d) / "matte.py").exists():
            sys.path.insert(0, d)
            import matte  # noqa: F401
            return matte
    raise SystemExit("matte.py (ghost-editor scripts) not found; set GHOST_SCRIPTS")


M = _import_matte()
VERSION = "0.1.0"
IMAGENET = (np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32))

# name: (Hugging Face repo, default input size, what it is for)
MODELS = {
    "portrait": ("ZhengPeng7/BiRefNet-portrait", (1024, 1024), "swin-L, people matting (P3M-10k + humans)"),
    "general": ("ZhengPeng7/BiRefNet", (1024, 1024), "swin-L, general use: objects, people, products"),
    "lite": ("ZhengPeng7/BiRefNet_lite", (1024, 1024), "swin-T (tiny backbone), general use, fast"),
    "lite-2k": ("ZhengPeng7/BiRefNet_lite-2K", (2560, 1440), "swin-T trained at 2560x1440"),
    "dis": ("ZhengPeng7/BiRefNet-DIS5K", (1024, 1024), "dichotomous segmentation: ultra-fine structures (spokes, wires, leaves)"),
    "cod": ("ZhengPeng7/BiRefNet-COD", (1024, 1024), "camouflaged object detection"),
    "hrsod": ("ZhengPeng7/BiRefNet-HRSOD", (1024, 1024), "high-resolution salient object detection"),
    "hr": ("ZhengPeng7/BiRefNet_HR", (2048, 2048), "general use trained at 2048x2048"),
    "matting": ("ZhengPeng7/BiRefNet-matting", (1024, 1024), "general trimap-free matting (soft alpha)"),
    "hr-matting": ("ZhengPeng7/BiRefNet_HR-matting", (2048, 2048), "matting trained at 2048x2048: hair, fur"),
    "lite-matting": ("ZhengPeng7/BiRefNet_lite-matting", (1024, 1024), "swin-T matting"),
    "dynamic": ("ZhengPeng7/BiRefNet_dynamic", None, "trained on 256..2304 px: any size / aspect"),
    "dynamic-matting": ("ZhengPeng7/BiRefNet_dynamic-matting", None, "matting at any size / aspect"),
}
HF_FILES = ["birefnet.py", "BiRefNet_config.py", "config.json", "model.safetensors"]
FONT_DIRS = [HERE / ".." / "templates" / "fonts", Path("~/.claude/skills/ghost-editor/templates/fonts").expanduser()]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ models
def parse_model(spec: str, frame_wh=None):
    """'lite@768' -> ('lite', (768, 768)); 'dynamic@576x1024'; 'dynamic' keeps the frame's aspect, long side 1024."""
    name, _, sz = spec.partition("@")
    if name not in MODELS:
        raise SystemExit(f"unknown model {name}; choose from {', '.join(MODELS)}")
    if sz:
        w, _, h = sz.lower().partition("x")
        size = (int(w), int(h or w))
    elif MODELS[name][1]:
        size = MODELS[name][1]
    else:
        fw, fh = frame_wh or (1024, 1024)
        k = 1024 / max(fw, fh)
        size = (max(256, round(fw * k / 32) * 32), max(256, round(fh * k / 32) * 32))
    if size[0] % 32 or size[1] % 32:
        raise SystemExit(f"model input {size} must be multiples of 32")
    return name, size


def weights_dir(name: str) -> Path:
    repo = MODELS[name][0]
    leaf = repo.split("/")[-1]
    for d in WEIGHT_DIRS:
        if all((d / leaf / f).exists() for f in HF_FILES):
            return d / leaf
    d = WEIGHT_DIRS[0] / leaf
    d.mkdir(parents=True, exist_ok=True)
    for f in HF_FILES:
        if not (d / f).exists():
            log(f"downloading {repo}/{f}")
            subprocess.run(["curl", "-fsSL", "--retry", "3", "-o", str(d / f) + ".part", f"https://huggingface.co/{repo}/resolve/main/{f}"], check=True)
            os.replace(str(d / f) + ".part", d / f)
    return d


class Net:
    """One BiRefNet session (torch; fp16 on Apple MPS). __call__(list of RGB uint8 at the model size) -> (B, h, w) alpha."""

    def __init__(self, name: str):
        import torch
        import transformers
        transformers.logging.set_verbosity_error()
        from transformers import AutoModelForImageSegmentation
        t0 = time.time()
        self.name, self.torch = name, torch
        m = AutoModelForImageSegmentation.from_pretrained(str(weights_dir(name)), trust_remote_code=True)
        self.dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.dtype = torch.float16 if self.dev.type == "mps" else torch.float32
        self.net = m.eval().to(self.dev).to(self.dtype)
        self.big = "lite" not in name
        self.load_s = time.time() - t0
        self.peak_gb = 0.0

    def __call__(self, imgs):
        t = self.torch
        x = np.stack([(im.astype(np.float32) / 255.0 - IMAGENET[0]) / IMAGENET[1] for im in imgs]).transpose(0, 3, 1, 2)
        with t.inference_mode():
            y = self.net(t.from_numpy(np.ascontiguousarray(x)).to(self.dev, self.dtype))[-1]
            y = y.float().sigmoid()[:, 0].cpu().numpy()
        if self.dev.type == "mps":
            self.peak_gb = max(self.peak_gb, t.mps.driver_allocated_memory() / 2**30)
            if self.big:  # see matte.py: without this a swin-L session keeps ~6 GB resident on a 16 GB Mac
                t.mps.empty_cache()
        return y

    def sync(self):
        if self.dev.type == "mps":
            self.torch.mps.synchronize()

    def predict(self, rgb: np.ndarray, size) -> np.ndarray:
        """Alpha (float32 0..1) for one RGB uint8 image of any size, inferred at `size` (w, h)."""
        h, w = rgb.shape[:2]
        small = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA if size[0] < w else cv2.INTER_CUBIC)
        a = self([small])[0]
        return np.clip(cv2.resize(a, (w, h), interpolation=cv2.INTER_CUBIC), 0, 1)


# ------------------------------------------------------------------ the cached alpha pass
def src_sig(src: str):
    st = os.stat(src)
    return dict(source=os.path.realpath(src), size=st.st_size, mtime=int(st.st_mtime))


def alpha_dir(src, ss, t, model, temporal="median3+ema", refine=True) -> Path:
    info = M.probe(src)
    name, size = parse_model(model, (info["w"], info["h"]))
    sig = dict(src_sig(src), ss=round(ss, 3), t=round(t, 3), model=name, infer=list(size), temporal=temporal, refine=refine, v=VERSION)
    key = hashlib.sha1(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:12]
    return CACHE / "alpha" / f"{Path(src).stem}-{name}-{size[0]}x{size[1]}-{key}", sig, info, name, size


def ensure_alpha(src, ss, t, model="lite@768", temporal="median3+ema", refine=True, batch=1, force=False) -> Path:
    """Matte SRC[ss, ss+t] once; cache alpha.mkv (FFV1 grey, source size, same frame count) + meta.json."""
    d, sig, info, name, size = alpha_dir(src, ss, t, model, temporal, refine)
    if not force and (d / "meta.json").exists() and (d / "alpha.mkv").exists():
        if json.loads((d / "meta.json").read_text()).get("sig") == sig:
            log(f"alpha cached: {d}")
            return d
    d.mkdir(parents=True, exist_ok=True)
    W, H, fps = info["w"], info["h"], info["fps"]
    T0 = time.time()
    net = Net(name)
    sw, sh = size
    log(f"matting {Path(src).name} {ss:.2f}+{t:.2f}s with {name} at {sw}x{sh} on {net.dev.type} (load {net.load_s:.1f}s)")
    raws, diffs, buf, prev = [], [], [], None
    t_inf = 0.0

    def flush():
        nonlocal t_inf, buf
        if buf:
            t1 = time.time()
            for a in net(buf):
                raws.append((a * 255 + 0.5).astype(np.uint8))
            t_inf += time.time() - t1
            buf = []

    for rgb in M.frames(src, info, ss, t, (sw, sh)):
        th = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
        diffs.append(0.0 if prev is None else float(np.mean(np.abs(th - prev))))
        prev = th
        buf.append(rgb)
        if len(buf) >= batch:
            flush()
        if len(raws) and len(raws) % 30 == 0 and not buf:
            log(f"  pass 1: {len(raws)} frames, {t_inf / len(raws):.2f} s/frame")
    flush()
    n = len(raws)
    cut = [d_ > 1.5 for d_ in diffs]
    t_pass1 = time.time() - T0
    del net
    # pass 2: temporal (median of 3 + deadband EMA, reset on cuts) -> guided upsample against the full-res frame
    refiner = M.Refiner(W, H, guided=refine, decontam=False)
    ema = M.DeadbandEMA()
    tmp = d / "alpha.mkv.part"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", info["fps_str"],
                            "-i", "-", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "gray", "-f", "matroska", str(tmp)], stdin=subprocess.PIPE)

    def same(i, j):
        if j < 0 or j >= n:
            return False
        a, b = min(i, j), max(i, j)
        return not any(cut[a + 1:b + 1])

    T1 = time.time()
    for i, rgb in enumerate(M.frames(src, info, ss, t, (W, H))):
        if i >= n:
            break
        cur = raws[i].astype(np.float32) / 255.0
        a = cur
        if "median3" in temporal:
            p = raws[i - 1].astype(np.float32) / 255.0 if same(i, i - 1) else cur
            q = raws[i + 1].astype(np.float32) / 255.0 if same(i, i + 1) else cur
            a = M.median3(p, cur, q)
        if "ema" in temporal:
            if not same(i, i - 1):
                ema.reset()
            a = ema(a)
        enc.stdin.write(np.ascontiguousarray(refiner(rgb, a)[..., 3]).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit("ffmpeg alpha encode failed")
    os.replace(tmp, d / "alpha.mkv")
    meta = dict(sig=sig, fps=fps, fps_str=info["fps_str"], n=n, w=W, h=H, ss=ss, t=t, model=name, infer=[sw, sh],
                cuts=[i for i, c in enumerate(cut) if c], infer_s_per_frame=round(t_inf / max(1, n), 3),
                pass1_s=round(t_pass1, 1), pass2_s=round(time.time() - T1, 1), wall_s=round(time.time() - T0, 1))
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    log(f"alpha done: {n} frames, {meta['infer_s_per_frame']} s/frame model, wall {meta['wall_s']} s -> {d}")
    return d


_TMP = []


def _tmpdir():
    base = CACHE / "work"
    base.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="cutoutfx-", dir=str(base)))
    _TMP.append(d)
    return d


atexit.register(lambda: [shutil.rmtree(d, ignore_errors=True) for d in _TMP])


def decode_gray(path, w, h, n):
    out = np.empty((n, h, w), np.uint8)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vf", f"scale={w}:{h}:flags=area", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    k = 0
    while k < n:
        b = p.stdout.read(w * h)
        if len(b) < w * h:
            break
        out[k] = np.frombuffer(b, np.uint8).reshape(h, w)
        k += 1
    p.stdout.close()
    p.wait()
    return out[:k]


class Clip:
    """A matted window of SRC at a working scale: rgb(i) uint8, f(i) float RGB, a(i) float alpha, fg(i) decontaminated
    foreground colour. Frames live in memmaps (random access for clones / freezes, little RAM)."""

    def __init__(self, src, ss, t, model="lite@768", scale=1.0, batch=1, fill_bottom=True):
        self.src, self.ss = src, ss
        self.dir = ensure_alpha(src, ss, t, model, batch=batch)
        meta = json.loads((self.dir / "meta.json").read_text())
        self.meta = meta
        self.fps, self.n = meta["fps"], meta["n"]
        self.W0, self.H0 = meta["w"], meta["h"]
        self.w, self.h = int(round(self.W0 * scale / 2) * 2), int(round(self.H0 * scale / 2) * 2)
        self.s = self.w / 1080.0  # pixel parameters are written for a 1080-wide frame
        self.cuts = set(meta["cuts"])
        info = M.probe(src)
        tmp = _tmpdir()
        self._rgb = np.memmap(tmp / "rgb.u8", np.uint8, "w+", shape=(self.n, self.h, self.w, 3))
        k = 0
        for fr in M.frames(src, info, ss, t, (self.w, self.h)):
            if k >= self.n:
                break
            self._rgb[k] = fr
            k += 1
        self.n = min(self.n, k)
        self._a = decode_gray(self.dir / "alpha.mkv", self.w, self.h, self.n)
        self.n = min(self.n, len(self._a))
        if fill_bottom:
            for k in range(self.n):
                fill_bottom_holes(self._a[k])
        self._fg = {}

    def rgb(self, i):
        return np.asarray(self._rgb[min(max(i, 0), self.n - 1)])

    def f(self, i):
        return self.rgb(i).astype(np.float32) / 255.0

    def a(self, i):
        return self._a[min(max(i, 0), self.n - 1)].astype(np.float32) / 255.0

    def fg(self, i):
        """Foreground colour with the old background unmixed from the soft edge (blur-fusion, matte.py)."""
        i = min(max(i, 0), self.n - 1)
        if i not in self._fg:
            if len(self._fg) > 8:
                self._fg.pop(next(iter(self._fg)))
            self._fg[i] = decontam(self.f(i), self.a(i))
        return self._fg[i]

    def t(self, i):
        return i / self.fps

    def src_t(self, i):
        return self.ss + i / self.fps

    def frame_at(self, src_seconds):
        return int(round((src_seconds - self.ss) * self.fps))

    def head(self, i):
        """(cx, top, width) of the head from the alpha: top row of the silhouette and the mean x of the top band."""
        a = self._a[min(max(i, 0), self.n - 1)]
        rows = np.nonzero((a > 128).sum(1) > 8 * self.s)[0]
        if not len(rows):
            return self.w / 2, self.h * 0.2, self.w * 0.3
        top = int(rows[0])
        band = a[top:top + int(0.12 * self.h)] > 128
        xs = np.nonzero(band.any(0))[0]
        cx = float(np.mean(np.nonzero(band)[1])) if band.any() else self.w / 2
        return cx, float(top), float(xs[-1] - xs[0] + 1) if len(xs) else self.w * 0.3


def fill_bottom_holes(a, max_frac=0.02):
    """In place: background specks that touch the bottom edge but not the top (the body runs out of the frame there,
    so they are holes in a dark shirt, not real background) are filled. Real background beside the body reaches the
    top of the frame and is kept."""
    h, w = a.shape
    n, lab, st, _ = cv2.connectedComponentsWithStats((a < 128).astype(np.uint8), connectivity=4)
    for k in range(1, n):
        x, y, bw, bh, area = st[k]
        if y + bh >= h and y > 0 and area < max_frac * h * w:
            m = cv2.dilate((lab == k).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
            a[m] = 255
    return a


def decontam(I, a):
    F = I.copy()
    soft = (a > 0.004) & (a < 0.996)
    ys, xs = np.nonzero(soft)
    if not len(ys):
        return F
    H, W = a.shape
    pad = 100
    y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
    bF, bB = M.blur_fusion_fields(I[y0:y1, x0:x1], a[y0:y1, x0:x1], s=2 if W > 700 else 1)
    size = (x1 - x0, y1 - y0)
    bF = cv2.resize(bF, size, interpolation=cv2.INTER_LINEAR)
    bB = cv2.resize(bB, size, interpolation=cv2.INTER_LINEAR)
    yy, xx = ys - y0, xs - x0
    av = a[ys, xs][:, None]
    f = bF[yy, xx]
    iv = I[ys, xs]
    est = f + av * (iv - av * f - (1 - av) * bB[yy, xx])
    F[ys, xs] = np.clip(est, np.minimum(iv, f), np.maximum(iv, f))
    return F


# ------------------------------------------------------------------ output
class Writer:
    def __init__(self, out, w, h, fps, audio=None, a_ss=0.0, a_t=0.0, crf=17, size=None):
        self.out = str(out)
        Path(self.out).parent.mkdir(parents=True, exist_ok=True)
        vf = "scale=out_color_matrix=bt709:out_range=tv" + (f",scale={size[0]}:{size[1]}:flags=lanczos" if size else "") + ",format=yuv420p"
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-"]
        if audio:
            cmd += ["-ss", f"{a_ss:.3f}", "-t", f"{a_t:.3f}", "-i", audio]
        cmd += ["-map", "0:v:0"] + (["-map", "1:a:0", "-c:a", "aac", "-b:a", "128k", "-shortest"] if audio else []) + [
            # a key frame every second: HyperFrames previews and snapshots seek the clip in a browser
            "-vf", vf, "-c:v", "libx264", "-threads", X264_THREADS, "-preset", "medium", "-crf", str(crf), "-g", str(max(1, int(round(fps)))), "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", self.out]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self.k = 0

    def write(self, img):
        if img.dtype != np.uint8:
            img = np.clip(img * 255.0 + 0.5, 0, 255).astype(np.uint8)
        self.p.stdin.write(np.ascontiguousarray(img).tobytes())
        self.k += 1

    def close(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise SystemExit(f"ffmpeg failed writing {self.out}")
        log(f"wrote {self.out} ({self.k} frames)")


# ------------------------------------------------------------------ speed
def bench(src, ss, nframes=30, configs=("portrait@1024", "lite@1024", "lite@768", "lite@512"), batches=(1,), out=None):
    import gc
    info = M.probe(src)
    W, H = info["w"], info["h"]
    full = []
    for fr in M.frames(src, info, ss, nframes / info["fps"] + 1.0, (W, H)):
        full.append(fr)
        if len(full) >= nframes:
            break
    groups = {}
    for c in configs:
        name, size = parse_model(c, (W, H))
        groups.setdefault(name, []).append(size)
    rows = []
    for name, sizes in groups.items():
        net = Net(name)
        log(f"{name}: loaded in {net.load_s:.1f} s on {net.dev.type}")
        for size in sizes:
            smalls = [cv2.resize(f, size, interpolation=cv2.INTER_AREA) for f in full]
            for b in batches:
                if b > 1 and net.big and size[0] * size[1] > 800 * 800:
                    continue  # swin-L at 1024 with batch 4 does not fit a 16 GB Mac comfortably
                net.peak_gb = 0.0
                for _ in range(2):
                    net(smalls[:b])
                net.sync()
                t0 = time.time()
                for k in range(0, len(smalls) - b + 1, b):
                    net(smalls[k:k + b])
                net.sync()
                done = (len(smalls) // b) * b
                dt = time.time() - t0
                row = dict(config=f"{name}@{size[0]}x{size[1]}", batch=b, frames=done, s_per_frame=round(dt / done, 3),
                           fps=round(done / dt, 2), load_s=round(net.load_s, 1), peak_gb=round(net.peak_gb, 2),
                           load_avg=round(os.getloadavg()[0], 1))
                log(json.dumps(row))
                rows.append(row)
        del net
        gc.collect()
        try:
            import torch
            torch.mps.empty_cache()
        except Exception:
            pass
    # the CPU side of the alpha pass (same for every model) and of the effects
    ref = M.Refiner(W, H, guided=True, decontam=False)
    lo = (np.ones((768, 768), np.float32) * 0.5)
    t0 = time.time()
    for f in full[:10]:
        ref(f, lo)
    refine_s = (time.time() - t0) / 10
    a = cv2.resize(cv2.GaussianBlur((np.indices((H, W))[1] > W // 2).astype(np.float32), (0, 0), 3), (W, H))
    t0 = time.time()
    for f in full[:5]:
        decontam(f.astype(np.float32) / 255, a)
    dec_s = (time.time() - t0) / 5
    res = dict(machine=platform_name(), src=os.path.basename(src), ss=ss, rows=rows, refine_s_per_frame=round(refine_s, 3),
               decontam_s_per_frame=round(dec_s, 3), when=time.strftime("%Y-%m-%d %H:%M"))
    if out:
        Path(out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return res


def platform_name():
    try:
        chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30
        return f"{chip}, {mem:.0f} GB"
    except Exception:
        return sys.platform


# ------------------------------------------------------------------ helpers
def clamp01(x):
    return min(1.0, max(0.0, x))


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ramp_w(t, t0, dur):
    """0 before t0, eased 0..1 over dur seconds; dur <= 0 = full strength from t0 (plate mode: no intro)."""
    return float(t >= t0) if dur <= 0 else smooth((t - t0) / dur)


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x, k=1.9):
    x = clamp01(x)
    return 1 + (k + 1) * (x - 1) ** 3 + k * (x - 1) ** 2


def ease_out_expo(x):
    x = clamp01(x)
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def hexrgb(h):
    h = h.strip().lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def blur(x, sigma):
    """Gaussian blur; large sigmas run on a downscaled copy (same look, a fraction of the time)."""
    if sigma < 0.3:
        return x
    k = max(1, int(sigma // 6))
    if k == 1:
        return cv2.GaussianBlur(x, (0, 0), sigma)
    h, w = x.shape[:2]
    sm = cv2.resize(x, (max(1, w // k), max(1, h // k)), interpolation=cv2.INTER_AREA)
    sm = cv2.GaussianBlur(sm, (0, 0), sigma / k)
    return cv2.resize(sm, (w, h), interpolation=cv2.INTER_LINEAR)


def over(dst, rgb, a, opacity=1.0):
    """Straight-alpha `rgb` (array or colour) over dst, alpha a (HxW)."""
    a3 = (a * opacity)[..., None]
    return rgb * a3 + dst * (1 - a3)


def over_pm(dst, pm, a):
    return pm + dst * (1 - a[..., None])


def lum(I):
    return I[..., 0] * 0.2126 + I[..., 1] * 0.7152 + I[..., 2] * 0.0722


def cover(img, w, h):
    ih, iw = img.shape[:2]
    k = max(w / iw, h / ih)
    nw, nh = max(w, int(round(iw * k))), max(h, int(round(ih * k)))
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC)
    x, y = (nw - w) // 2, (nh - h) // 2
    return r[y:y + h, x:x + w]


def load_rgb(path):
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"cannot read {path}")
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    if im.shape[2] == 4:
        im = im[..., :3]
    if im.dtype == np.uint16:
        im = (im / 257).astype(np.uint8)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def rrect_mask(w, h, x0, y0, x1, y1, r, grid=None):
    """Anti-aliased rounded rectangle (signed distance), float HxW."""
    yy, xx = grid if grid is not None else np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
    qx = np.abs(xx - cx) - hx
    qy = np.abs(yy - cy) - hy
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r
    return np.clip(0.5 - d, 0, 1).astype(np.float32)


def gradient(w, h, c0, c1, kind="radial", cx=0.5, cy=0.4):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if kind == "radial":
        d = np.sqrt(((xx / w - cx) * (w / h)) ** 2 + (yy / h - cy) ** 2) / 0.75
    else:
        d = yy / h
    d = np.clip(d, 0, 1)[..., None]
    return (hexrgb(c0) * (1 - d) + hexrgb(c1) * d).astype(np.float32)


class Background:
    """A background for every frame: an image (slow push-in), a video (cover-cropped, ping-pong looped),
    '#hex' or '#hex1,#hex2' (radial gradient)."""

    def __init__(self, spec, w, h, n, fps, push=1.06):
        self.w, self.h, self.n, self.push = w, h, n, push
        self.kind = "image"
        if spec.startswith("#"):
            cs = spec.split(",")
            self.img = gradient(w, h, cs[0], cs[-1]) if len(cs) > 1 else np.broadcast_to(hexrgb(cs[0]), (h, w, 3)).copy()
            self.push = 1.0
        elif Path(spec).suffix.lower() in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
            self.kind = "video"
            p = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-i", spec, "-vf",
                                  f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd+full_chroma_int,crop={w}:{h},format=rgb24",
                                  "-frames:v", str(n), "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
            fr = []
            while True:
                b = p.stdout.read(w * h * 3)
                if len(b) < w * h * 3:
                    break
                fr.append(np.frombuffer(b, np.uint8).reshape(h, w, 3))
            p.wait()
            if not fr:
                raise SystemExit(f"no frames in {spec}")
            self.frames = fr
        else:
            self.img = cover(load_rgb(spec), int(w * push) + 2, int(h * push) + 2).astype(np.float32) / 255.0

    def __call__(self, i):
        if self.kind == "video":
            m = len(self.frames)
            k = i % (2 * m - 2) if m > 1 else 0
            return self.frames[k if k < m else 2 * m - 2 - k].astype(np.float32) / 255.0
        if self.push <= 1.0:
            return self.img[:self.h, :self.w].copy() if self.img.shape[0] >= self.h else cv2.resize(self.img, (self.w, self.h))
        z = 1.0 + (self.push - 1.0) * (i / max(1, self.n - 1))  # 1 -> push, centred
        ih, iw = self.img.shape[:2]
        k = z / self.push
        cw, ch = iw * k, ih * k
        x0, y0 = (iw - cw) / 2, (ih - ch) / 2
        Mx = np.float32([[self.w / cw, 0, -x0 * self.w / cw], [0, self.h / ch, -y0 * self.h / ch]])
        return cv2.warpAffine(self.img, Mx, (self.w, self.h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


# ------------------------------------------------------------------ type
_FONT_CACHE = {}


def _font(script, size, family="montserrat", weight="Black"):
    key = (family, script, size, weight)
    if key not in _FONT_CACHE:
        from PIL import ImageFont
        for d in FONT_DIRS:
            p = d / f"{family}-{script}.woff2"
            if p.exists():
                f = ImageFont.truetype(str(p), size)
                try:
                    f.set_variation_by_name(weight)
                except Exception:
                    pass
                _FONT_CACHE[key] = f
                break
        else:
            raise SystemExit(f"font {family}-{script}.woff2 not found in {FONT_DIRS}")
    return _FONT_CACHE[key]


def text_layer(text, size, color="#ffffff", stroke=0, stroke_color="#000000", family="montserrat", weight="Black", tracking=-0.02):
    """Straight-alpha RGB + alpha of one line of display type. Cyrillic letters use the font's cyrillic subset,
    everything else the latin subset (the bundled woff2 files are split by script)."""
    from PIL import Image, ImageDraw
    size = int(size)
    fc, fl = _font("cyrillic", size, family, weight), _font("latin", size, family, weight)
    pick = lambda ch: fc if "Ѐ" <= ch <= "ӿ" else fl  # noqa: E731
    asc, desc = fl.getmetrics()
    xs, x = [], 0.0
    for ch in text:
        xs.append(x)
        x += pick(ch).getlength(ch) + tracking * size
    pad = int(stroke + size * 0.12)
    W, H = int(x - tracking * size) + 2 * pad + 2, asc + desc + 2 * pad
    im = Image.new("RGBA", (max(W, 4), H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    rgb = tuple(int(v * 255) for v in hexrgb(color))
    if stroke:
        srgb = tuple(int(v * 255) for v in hexrgb(stroke_color))
        for ch, cx in zip(text, xs):
            dr.text((pad + cx, pad), ch, font=pick(ch), fill=srgb + (255,), stroke_width=stroke, stroke_fill=srgb + (255,))
    for ch, cx in zip(text, xs):
        dr.text((pad + cx, pad), ch, font=pick(ch), fill=rgb + (255,))
    arr = np.asarray(im).astype(np.float32) / 255.0
    a = arr[..., 3]
    ys = np.nonzero(a.max(1) > 0.01)[0]
    if len(ys):  # trim the empty rows (the latin metrics leave room for accents)
        arr = arr[max(0, ys[0] - pad // 2): ys[-1] + pad // 2 + 1]
    return arr[..., :3].copy(), arr[..., 3].copy()


def warp_layer(shape, rgb, a, cx, cy, scale=1.0, angle=0.0, sx=1.0, sy=1.0):
    """A straight-alpha layer centred at (cx, cy) with scale / rotation (degrees) on a canvas of `shape` (H, W):
    returns premultiplied colour (H, W, 3) and alpha (H, W)."""
    h, w = a.shape
    Hd, Wd = shape[:2]
    Mt = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    Mt[:, 0] *= scale * sx
    Mt[:, 1] *= scale * sy
    Mt[0, 2] = cx - (Mt[0, 0] * w / 2 + Mt[0, 1] * h / 2)
    Mt[1, 2] = cy - (Mt[1, 0] * w / 2 + Mt[1, 1] * h / 2)
    pm = cv2.warpAffine(rgb * a[..., None], Mt, (Wd, Hd), flags=cv2.INTER_LINEAR, borderValue=0)
    aw = cv2.warpAffine(a, Mt, (Wd, Hd), flags=cv2.INTER_LINEAR, borderValue=0)
    return pm, aw


def place(dst, rgb, a, cx, cy, scale=1.0, angle=0.0, opacity=1.0, sx=1.0, sy=1.0):
    """Draw a straight-alpha layer centred at (cx, cy) onto dst (returns the new image)."""
    pm, aw = warp_layer(dst.shape, rgb, a, cx, cy, scale, angle, sx, sy)
    return pm * opacity + dst * (1 - (aw * opacity)[..., None])


def paste_scaled(dst, F, a, scale, cx, bottom, mirror=False, shade=1.0):
    """Resize a full-frame cut-out (F, a) by `scale`, centre it at x=cx with its bottom edge at y=bottom; returns
    (dst, alpha in dst coordinates)."""
    Hd, Wd = dst.shape[:2]
    h, w = a.shape
    nw, nh = max(2, int(w * scale)), max(2, int(h * scale))
    Fs = cv2.resize(F, (nw, nh), interpolation=cv2.INTER_AREA)
    As = cv2.resize(a, (nw, nh), interpolation=cv2.INTER_AREA)
    if mirror:
        Fs, As = Fs[:, ::-1], As[:, ::-1]
    x0, y0 = int(round(cx - nw / 2)), int(round(bottom - nh))
    ax0, ay0, ax1, ay1 = max(0, x0), max(0, y0), min(Wd, x0 + nw), min(Hd, y0 + nh)
    full = np.zeros((Hd, Wd), np.float32)
    if ax1 <= ax0 or ay1 <= ay0:
        return dst, full
    sub_a = As[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
    sub_f = Fs[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0] * shade
    dst[ay0:ay1, ax0:ax1] = over(dst[ay0:ay1, ax0:ax1], sub_f, sub_a)
    full[ay0:ay1, ax0:ax1] = sub_a
    return dst, full


# ------------------------------------------------------------------ effects
# Each effect: fx_<name>(clip, o) yields float RGB frames at the clip's working size. `o` holds the CLI options;
# o.at = source second where the effect starts (default: 0.4 s into the window). Pixel sizes are for a 1080-wide frame.

def _t0(c, o, default=0.4):
    return (o.at - c.ss) if getattr(o, "at", None) is not None else default


def fx_bg_swap(c, o):
    """New background behind the speaker: decontaminated edges, light wrap from the new background onto the
    rim, and the speaker's mean colour pulled toward the new scene (Lab), revealed by a soft top-down wipe."""
    bg1 = Background(o.bg, c.w, c.h, c.n, c.fps, push=o.push)
    bg2 = Background(o.bg2, c.w, c.h, c.n, c.fps, push=o.push) if o.bg2 else None
    i_sw = c.frame_at(o.switch) if (o.bg2 and o.switch is not None) else (c.n // 2 if o.bg2 else c.n + 1)
    t0 = _t0(c, o)
    yy = np.mgrid[0:c.h, 0:c.w][0].astype(np.float32)
    delta, last_bg = None, None
    for i in range(c.n):
        t = c.t(i)
        I, a, F = c.f(i), c.a(i), c.fg(i)
        bgo = bg2 if (bg2 is not None and i >= i_sw) else bg1
        if bgo is not last_bg:
            delta, last_bg = None, bgo
        B = bgo(i - (i_sw if bgo is bg2 else 0))
        if o.defocus > 0:
            B = blur(B, o.defocus * c.s)
        if o.match > 0:  # colour match: shift the speaker's mean Lab toward the scene's
            step = 4
            lf = cv2.cvtColor(F[::step, ::step], cv2.COLOR_RGB2Lab)
            lb = cv2.cvtColor(cv2.resize(B, (c.w // 8, c.h // 8), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2Lab)
            m = a[::step, ::step] > 0.95
            if m.sum() > 50:
                d = lb.reshape(-1, 3).mean(0) - lf[m].mean(0)
                d = np.clip(d * np.array([0.3, 1.0, 1.0], np.float32), [-10, -12, -12], [10, 12, 12]) * o.match
                delta = d if delta is None else delta * 0.85 + d * 0.15
            if delta is not None:
                lab = cv2.cvtColor(F, cv2.COLOR_RGB2Lab) + delta.astype(np.float32)
                F = np.clip(cv2.cvtColor(lab, cv2.COLOR_Lab2RGB), 0, 1)
        if o.wrap > 0:  # light wrap: blurred background light bleeds over the speaker's rim
            Bb = blur(B, 22 * c.s)
            inner = a * blur(1 - a, 9 * c.s)
            k = np.clip(inner * 2.2 * o.wrap, 0, 0.85)[..., None]
            F = F + (Bb - F) * k
        comp = over(B, F, a)
        # reveal: the new world wipes in top-down behind the speaker
        p = smooth((t - t0) / o.wipe) if o.wipe > 0 else float(t >= t0)
        if p <= 0:
            yield I
            continue
        if p < 1:
            edge = p * (c.h + 160 * c.s) - 80 * c.s
            m = np.clip((edge - yy) / (60 * c.s), 0, 1)
            glint = np.exp(-((yy - edge) / (10 * c.s)) ** 2) * 0.35 * (1 - a)
            comp = comp * m[..., None] + I * (1 - m[..., None]) + glint[..., None]
        yield comp


def lens_blur(x, r, bokeh=1.0):
    """Disc (lens) blur in linear light; highlights are boosted first so they bloom into bokeh discs."""
    if r < 0.6:
        return x
    k = max(1, int(r / 5))
    h, w = x.shape[:2]
    sm = cv2.resize(x, (w // k, h // k), interpolation=cv2.INTER_AREA) if k > 1 else x
    lin = np.power(np.clip(sm, 0, 1), 2.2)
    if bokeh:
        hi = np.clip((lin.max(-1, keepdims=True) - 0.45) / 0.5, 0, 1)
        lin = lin * (1 + 3.0 * bokeh * hi * hi)
    rr = max(1.0, r / k)
    ks = int(math.ceil(rr)) * 2 + 1
    yy, xx = np.mgrid[0:ks, 0:ks].astype(np.float32) - ks // 2
    disc = np.clip(rr + 0.5 - np.sqrt(xx * xx + yy * yy), 0, 1)
    disc /= disc.sum()
    out = cv2.filter2D(lin, -1, disc, borderType=cv2.BORDER_REFLECT)
    out = np.power(np.clip(out, 0, 1), 1 / 2.2)
    return cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR) if k > 1 else out


def clean_plate(I, a, s, grow=8, sigma=30):
    """The background with the speaker removed (normalised convolution fill), so a blurred background does not
    smear the speaker's colours into a halo around them."""
    kk = max(1, int(grow * s)) * 2 + 1
    ad = cv2.dilate(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kk, kk)))
    hole = 1 - ad
    fill = blur(I * hole[..., None], sigma * s) / (blur(hole, sigma * s)[..., None] + 1e-3)
    return I * hole[..., None] + np.clip(fill, 0, 1) * ad[..., None]


def fx_bg_blur(c, o):
    """Portrait mode: the background racks out of focus (lens blur, radius ramps 0 -> --radius) while the speaker stays sharp."""
    t0 = _t0(c, o)
    for i in range(c.n):
        t = c.t(i)
        w = ramp_w(t, t0, o.ramp)
        I = c.f(i)
        if w <= 0:
            yield I
            continue
        a, F = c.a(i), c.fg(i)
        bg = lens_blur(clean_plate(I, a, c.s), o.radius * c.s * w, o.bokeh)
        if o.dim:
            bg = bg * (1 - o.dim * w)
        yield over(bg, F, a)


def grade(I, look):
    if look == "bw":
        g = lum(I)
        g = np.clip((g - 0.5) * 1.15 + 0.5, 0, 1)
        return np.repeat(g[..., None], 3, -1)
    if look == "noir":
        g = lum(I)
        g = np.clip((g - 0.42) * 1.6 + 0.42, 0, 1) ** 1.1
        return np.repeat(g[..., None], 3, -1)
    if look == "film":  # muted teal-orange: desaturate, split-tone, lift the blacks
        g = lum(I)[..., None]
        x = I * 0.45 + g * 0.55
        sh = np.clip(1 - g * 2, 0, 1)
        hi = np.clip(g * 2 - 1, 0, 1)
        x = x + sh * np.array([-0.02, 0.05, 0.08], np.float32) + hi * np.array([0.08, 0.03, -0.04], np.float32)
        return np.clip(0.04 + x * 0.94, 0, 1)
    raise SystemExit(f"unknown look {look}")


def fx_selective(c, o):
    """Selective colour: the speaker keeps (slightly richer) colour, the world drains to black-and-white / noir / film."""
    t0 = _t0(c, o)
    for i in range(c.n):
        t = c.t(i)
        w = ramp_w(t, t0, o.ramp)
        I = c.f(i)
        if w <= 0:
            yield I
            continue
        a, F = c.a(i), c.fg(i)
        g = lum(F)[..., None]
        Fp = np.clip(g + (F - g) * (1 + 0.18 * w), 0, 1)
        out = over(grade(I, o.look), Fp, a)
        yield I + (out - I) * w


def fx_spotlight(c, o):
    """Spotlight: the background dims to --dim with a soft vignette, a warm pool of light stays behind the head."""
    t0 = _t0(c, o)
    yy, xx = np.mgrid[0:c.h, 0:c.w].astype(np.float32)
    warm = hexrgb(o.color)
    hc = None
    for i in range(c.n):
        t = c.t(i)
        w = ramp_w(t, t0, o.ramp)
        I = c.f(i)
        cx, top, hw = c.head(i)
        cur = np.array([cx, top + 0.55 * hw, hw], np.float32)
        hc = cur if hc is None else hc * 0.8 + cur * 0.2
        if w <= 0:
            yield I
            continue
        a, F = c.a(i), c.fg(i)
        d = np.sqrt(((xx - hc[0]) / (1.25 * hc[2])) ** 2 + ((yy - hc[1]) / (1.5 * hc[2])) ** 2)
        pool = np.exp(-d * d * 1.3)[..., None]
        vig = 1 - 0.7 * np.clip((np.sqrt(((xx / c.w - 0.5) * 1.2) ** 2 + (yy / c.h - 0.42) ** 2) - 0.2) / 0.5, 0, 1)[..., None]
        bg = I * (o.dim + (1 - o.dim) * pool * 0.9) * vig + pool * warm * 0.07
        # the key light: full on the face, the body falls off into shadow toward the bottom of the frame
        df = np.sqrt(((xx - hc[0]) / (2.4 * hc[2])) ** 2 + ((yy - hc[1]) / (2.6 * hc[2])) ** 2)
        key = (0.42 + 0.66 * np.exp(-df * df * 1.2))[..., None]
        Fl = np.clip(F * key, 0, 1)
        out = over(bg, Fl, a)
        yield I + (out - I) * w


def sticker_layer(F, a, s, stroke=22, color="#ffffff", pad=None, open_edges=False):
    """Die-cut sticker: the cut-out padded on every side (so the stroke also closes where the body leaves the frame),
    a round white outline from a distance transform. Returns premultiplied rgb, alpha, the hard mask distance, pad."""
    P = pad or int(80 * s)
    ap = np.pad(a, P)
    Fp = np.pad(F, ((P, P), (P, P), (0, 0)))
    if open_edges:  # where the body leaves the frame the outline stays open (the body continues past the edge)
        hard = np.pad((a < 0.5).astype(np.uint8), P, mode="edge")
        dist = cv2.distanceTransform(hard, cv2.DIST_L2, 5)
    else:
        dist = cv2.distanceTransform((ap < 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    st = stroke * s
    sa = np.maximum(ap, np.clip(st + 0.5 - dist, 0, 1))
    rgb = Fp * ap[..., None] + hexrgb(color) * (1 - ap[..., None])
    return rgb, sa, ap, dist, P


def fx_sticker(c, o):
    """Freeze frame -> the speaker peels off as a die-cut sticker (white outline, drop shadow), pops toward the
    camera with an overshoot, wiggles and settles; after --hold it drops back and the video resumes."""
    f0 = c.frame_at(o.freeze) if o.freeze is not None else int(0.8 * c.fps)
    f0 = min(max(f0, 0), c.n - 1)
    I0, a0, F0 = c.f(f0), c.a(f0), c.fg(f0)
    rgb, sa, ap, dist, P = sticker_layer(F0, a0, c.s, o.stroke)
    st = o.stroke * c.s
    m = cv2.moments((sa > 0.5).astype(np.uint8))
    gx, gy = m["m10"] / m["m00"], m["m01"] / m["m00"]
    # behind the sticker: the frozen frame WITHOUT the speaker (clean plate), blurred and dimmed, so no ghost of the
    # speaker shows where the sticker has moved away
    bgk = blur(clean_plate(I0, a0, c.s, grow=16, sigma=70) if o.bg == "plate" else I0, 8 * c.s)
    gk = lum(bgk)[..., None]
    bg_frozen = (gk + (bgk - gk) * 0.4) * 0.45
    if o.bg and o.bg not in ("dim", "plate"):
        bg_frozen = Background(o.bg, c.w, c.h, 1, c.fps, push=1.0)(0)
    t_f = f0 / c.fps
    for i in range(c.n):
        t = c.t(i)
        tau = t - t_f
        back = tau - o.hold  # > 0: returning
        if tau < 0 or back > 0.35:
            yield c.f(i)
            continue
        k_in = smooth(tau / 0.22)
        p = ease_out_back(tau / 0.42, 2.2)
        if back > 0:
            r = smooth(back / 0.35)
            p, k_in = p * (1 - r), k_in * (1 - r)
        scale = 1 + (o.sticker_scale - 1) * p
        wig = 7.0 * math.sin(2 * math.pi * 2.6 * tau) * math.exp(-2.3 * tau) * min(1, tau / 0.08)
        ang = (-3.5 * p + wig * (1 if back <= 0 else 0) + 1.3 * math.sin(2 * math.pi * 0.55 * tau)) * (1 if back <= 0 else (1 - smooth(back / 0.35)))
        lift = -60 * c.s * p
        sa_t = np.maximum(ap, np.clip(st * k_in + 0.5 - dist, 0, 1)) if k_in < 1 else sa
        Mt = cv2.getRotationMatrix2D((gx, gy), ang, scale)
        Mt[0, 2] += -P
        Mt[1, 2] += -P + lift
        pm = cv2.warpAffine(rgb * sa_t[..., None], Mt, (c.w, c.h), flags=cv2.INTER_LINEAR)
        aw = cv2.warpAffine(sa_t, Mt, (c.w, c.h), flags=cv2.INTER_LINEAR)
        Ms = Mt.copy()
        Ms[0, 2] += 18 * c.s * p
        Ms[1, 2] += 30 * c.s * p
        sh = blur(cv2.warpAffine(sa_t, Ms, (c.w, c.h), flags=cv2.INTER_LINEAR), (6 + 14 * p) * c.s) * 0.55 * min(1, p)
        bg = I0 + (bg_frozen - I0) * k_in
        bg = bg * (1 - sh[..., None])
        out = over_pm(bg, pm, aw)
        if 0 <= tau < 0.1:
            out = out + (1 - out) * 0.45 * (1 - tau / 0.1)
        yield np.clip(out, 0, 1)


def _contour(a, s, grow):
    m = (a > 0.5).astype(np.uint8)
    if grow > 0:
        kk = int(grow * s) * 2 + 1
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kk, kk)))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return None
    pts = max(cs, key=cv2.contourArea)[:, 0, :].astype(np.float32)
    h, w = a.shape
    border = (pts[:, 0] <= 2) | (pts[:, 0] >= w - 3) | (pts[:, 1] >= h - 3) | (pts[:, 1] <= 1)
    k = max(2, int(4 * s))  # smooth the pixel stairs along the curve (circular), keep frame-border points where they are
    ker = np.exp(-0.5 * (np.arange(-3 * k, 3 * k + 1) / k) ** 2)
    ker /= ker.sum()
    sm = np.stack([np.convolve(np.concatenate([pts[-3 * k:, j], pts[:, j], pts[:3 * k, j]]), ker, "valid") for j in (0, 1)], 1)
    if len(sm) == len(pts):
        pts = np.where(border[:, None], pts, sm.astype(np.float32))
    return pts


def trace_outline(pts, w, h, p, thick, cx):
    """Draw the part of a closed contour within p * L / 2 of its top point (both directions), skipping points on the
    frame border (where the body is cut by the frame). Returns the line layer and the two trace heads."""
    layer = np.zeros((h, w), np.float32)
    if pts is None or p <= 0:
        return layer, []
    n = len(pts)
    start = int(np.argmin(pts[:, 1] + 0.002 * np.abs(pts[:, 0] - cx)))
    pts = np.roll(pts, -start, axis=0)
    seg = np.sqrt((np.diff(np.vstack([pts, pts[:1]]), axis=0) ** 2).sum(1))
    cum = np.concatenate([[0], np.cumsum(seg)[:-1]])
    L = seg.sum()
    dd = np.minimum(cum, L - cum)
    lim = p * L / 2
    border = (pts[:, 0] <= 2) | (pts[:, 0] >= w - 3) | (pts[:, 1] >= h - 3) | (pts[:, 1] <= 1)
    vis = (dd <= lim) & ~border
    runs, cur = [], []
    for k in range(n):
        if vis[k]:
            cur.append(pts[k])
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        if runs and vis[0]:
            runs[0] = cur + runs[0]
        else:
            runs.append(cur)
    polys = [np.round(np.array(r) * 4).astype(np.int32) for r in runs if len(r) > 1]
    if polys:
        cv2.polylines(layer, polys, False, 1.0, max(1, int(round(thick))), cv2.LINE_AA, shift=2)
    heads = []
    if p < 1:
        for target in (lim, L - lim):
            k = int(np.argmin(np.abs(cum - target)))
            if not border[k]:
                heads.append(pts[k])
    return layer, heads


def fx_neon(c, o):
    """Neon outline: the world dims, a glowing tube traces the silhouette from the top of the head down both sides,
    an outer echo line follows, then the colour breathes between the two --colors."""
    t0 = _t0(c, o)
    cols = [hexrgb(x) for x in o.colors.split(",")]
    c0, c1 = cols[0], cols[-1]
    for i in range(c.n):
        t = c.t(i)
        I = c.f(i)
        tau = t - t0
        w = smooth(tau / 0.35)
        if w <= 0:
            yield I
            continue
        a, F = c.a(i), c.fg(i)
        base = over(I * (1 - (1 - o.dim) * w), F, a)
        cx = c.head(i)[0]
        p1 = ramp_w(tau, 0.0, o.trace)
        p2 = ramp_w(tau, 0.3 if o.trace > 0 else 0.0, o.trace)
        l1, heads = trace_outline(_contour(a, c.s, 12), c.w, c.h, p1, 7 * c.s, cx)
        l2, _ = trace_outline(_contour(a, c.s, 40), c.w, c.h, p2, 3.5 * c.s, cx)
        breathe = 0.5 + 0.5 * math.sin(2 * math.pi * 0.45 * max(0.0, tau - o.trace))
        col1 = c0 * (1 - breathe * 0.6) + c1 * breathe * 0.6 if tau > o.trace else c0
        col2 = c1 * (1 - breathe * 0.6) + c0 * breathe * 0.6 if tau > o.trace else c1
        for hx, hy in heads:
            cv2.circle(l1, (int(hx), int(hy)), int(9 * c.s), 1.0, -1, cv2.LINE_AA)
        flick = 1.0 if tau > 0.25 else (0.55 + 0.45 * (int(tau * 40) % 2))
        g1 = blur(l1, 5 * c.s) * 1.0 + blur(l1, 16 * c.s) * 1.2 + blur(l1, 46 * c.s) * 1.0
        g2 = blur(l2, 6 * c.s) * 0.7 + blur(l2, 22 * c.s) * 0.5
        core = cv2.GaussianBlur(l1, (0, 0), 1.2 * c.s)
        out = base + (g1[..., None] * col1 + g2[..., None] * col2 + l2[..., None] * col2 * 0.8) * flick
        out = out + core[..., None] * (col1 * 0.35 + 0.65) * flick
        yield np.clip(out, 0, 1)


def _rect_warp(src_rect, dst_rect):
    """Affine map (no rotation) taking src_rect (x0, y0, x1, y1) onto dst_rect."""
    sx0, sy0, sx1, sy1 = src_rect
    dx0, dy0, dx1, dy1 = dst_rect
    kx, ky = (dx1 - dx0) / (sx1 - sx0), (dy1 - dy0) / (sy1 - sy0)
    return np.float32([[kx, 0, dx0 - sx0 * kx], [0, ky, dy0 - sy0 * ky]])


def fx_clones(c, o):
    """Three matted copies of the speaker from the same clip at different time offsets, side by side on a studio
    backdrop: the frame shrinks into the middle bust, then the two others slide out from behind it (smaller and a
    little higher, so they read as standing further back). Busts fade out at the bottom into the floor."""
    offs = [int(round(float(x) * c.fps)) for x in o.offsets.split(",")]
    mid_off, left_off, right_off = (offs + [0, 0, 0])[:3]
    n_out = c.n - max(offs)
    t0 = _t0(c, o, 0.35)
    W, H, s = c.w, c.h, c.s
    cs = [x.strip() for x in o.backdrop.split(",")]
    studio = gradient(W, H, cs[0], cs[-1], "radial", 0.5, 0.38)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    bx0, by0, bw, bh = (float(v) for v in o.bust.split(","))
    box = (bx0 * W, by0 * H, (bx0 + bw) * W, (by0 + bh) * H)  # the bust in source pixels
    asp = (box[3] - box[1]) / (box[2] - box[0])
    slots = {}
    for key, cx, width, bottom in (("m", 0.5, o.mid_scale, 0.89), ("l", 0.215, o.side_scale, 0.81), ("r", 0.785, o.side_scale, 0.81)):
        ww = width * W
        slots[key] = (cx * W - ww / 2, bottom * H - ww * asp, cx * W + ww / 2, bottom * H)
    for key in ("l", "m", "r"):  # a soft light pool behind each copy
        x0, y0, x1, y1 = slots[key]
        d = np.sqrt(((xx - (x0 + x1) / 2) / (0.24 * W)) ** 2 + ((yy - (y0 + 0.3 * (y1 - y0))) / (0.22 * H)) ** 2)
        studio = studio + np.exp(-d * d)[..., None] * hexrgb(o.light) * 0.20
    floor = np.clip((yy - 0.70 * H) / (0.3 * H), 0, 1)[..., None]
    studio = np.clip(studio * (1 - 0.55 * floor), 0, 1)
    fade_src = np.clip((box[3] - yy) / (0.30 * (box[3] - box[1])), 0, 1)  # bust bottom fades out (source coords)
    fade_src = fade_src * fade_src * (3 - 2 * fade_src)
    full = (0.0, 0.0, float(W), float(H))
    for i in range(n_out):
        tau = c.t(i) - t0
        if tau <= 0:
            yield c.f(i + mid_off)
            continue
        k = ease_out_cubic(tau / 0.5)
        if k < 1:  # the old background (speaker removed, so no ghost) dissolves into the studio
            out = clean_plate(c.f(i + mid_off), c.a(i + mid_off), s, grow=16, sigma=60) * (1 - k) + studio * k
        else:
            out = studio.copy()
        q = ease_out_back((tau - 0.35) / 0.5, 1.5)
        fade = 1 - k + k * fade_src
        for key, off, mirror in (("l", left_off, True), ("r", right_off, False)):
            if tau <= 0.35:
                break
            F, a = c.fg(i + off), c.a(i + off) * fade * clamp01((tau - 0.35) / 0.12)
            if mirror:
                F, a = F[:, ::-1], a[:, ::-1]
                src = (W - box[2], box[1], W - box[0], box[3])
            else:
                src = box
            m0, d0 = slots["m"], slots[key]
            dst = tuple(m0[j] + (d0[j] - m0[j]) * q for j in range(4))
            Mt = _rect_warp(src, dst)
            pm = cv2.warpAffine(F * a[..., None] * 0.86, Mt, (W, H), flags=cv2.INTER_AREA)
            aw = cv2.warpAffine(np.ascontiguousarray(a), Mt, (W, H), flags=cv2.INTER_AREA)
            out = over_pm(out, pm, aw)
        F, a = c.fg(i + mid_off), c.a(i + mid_off) * fade
        src = tuple(full[j] + (box[j] - full[j]) * k for j in range(4))
        dst = tuple(full[j] + (slots["m"][j] - full[j]) * k for j in range(4))
        Mt = _rect_warp(src, dst)
        aw = cv2.warpAffine(a, Mt, (W, H), flags=cv2.INTER_AREA)
        pm = cv2.warpAffine(F * a[..., None], Mt, (W, H), flags=cv2.INTER_AREA)
        sh = blur(np.roll(aw, int(14 * s), axis=1), 24 * s) * 0.5 * k  # the middle copy shades the two behind it
        out = out * (1 - sh[..., None])
        yield over_pm(out, pm, aw)


def fx_pop(c, o):
    """Out-of-frame pop: the video shrinks into a phone (or card) frame on a bold background, then the frame's top
    edge slides down and the speaker's head breaks out over the bezel."""
    W, H, s = c.w, c.h, c.s
    t0 = _t0(c, o, 0.3)
    bg = Background(o.bg, W, H, c.n, c.fps, push=1.0)(0) if o.bg != "blur" else None
    grid = np.mgrid[0:H, 0:W].astype(np.float32)
    sp = o.plate
    pw, ph = int(W * sp), int(H * sp)
    fx0 = (W - pw) / 2
    fy1 = H - o.bottom * s
    fy0 = fy1 - ph
    bz = (22 if o.frame == "phone" else 14) * s
    R = (78 if o.frame == "phone" else 46) * s
    heads = [c.head(j) for j in range(0, c.n, 5)]
    top = float(np.median([h[1] for h in heads]))
    hw = float(np.median([h[2] for h in heads]))
    y_break = fy0 + (top + o.brk * hw) * sp
    for i in range(c.n):
        t = c.t(i)
        tau = t - t0
        I = c.f(i)
        if tau <= 0:
            yield I
            continue
        a, F = c.a(i), c.fg(i)
        k = ease_out_cubic(tau / 0.45)
        x0, x1 = fx0 * k, W - fx0 * k
        y1 = H + (fy1 - H) * k
        y0 = y1 - (H + (ph - H) * k)
        sc = (x1 - x0) / W
        q = ease_out_back((tau - 0.6) / 0.42, 1.4)
        ytop = y0 + (y_break - fy0) * q if tau > 0.6 else y0
        back = bg if bg is not None else np.clip(blur(I, 40 * s) * 0.55, 0, 1)
        out = I * (1 - k) + back * k
        # the phone body: soft shadow, bezel, thin rim
        shadow = blur(rrect_mask(W, H, x0 - bz, ytop - bz + 30 * s, x1 + bz, y1 + bz + 30 * s, R + bz, grid), 30 * s) * 0.5 * k
        out = out * (1 - shadow[..., None])
        body = rrect_mask(W, H, x0 - bz, ytop - bz, x1 + bz, y1 + bz, R + bz, grid) * k
        rim = body - rrect_mask(W, H, x0 - bz + 3 * s, ytop - bz + 3 * s, x1 + bz - 3 * s, y1 + bz - 3 * s, R + bz - 3 * s, grid) * k
        out = over(out, hexrgb("#0c0c0e" if o.frame == "phone" else "#ffffff"), body)
        out = over(out, hexrgb("#4a4a50" if o.frame == "phone" else "#e8e8e8"), np.clip(rim, 0, 1))
        # the screen shows the (scaled) video
        Ms = np.float32([[sc, 0, x0], [0, sc, y0]])
        plate = cv2.warpAffine(I, Ms, (W, H), flags=cv2.INTER_AREA)
        screen = rrect_mask(W, H, x0, ytop, x1, y1, R, grid)
        out = over(out, plate, screen)
        if o.frame == "phone":
            isl = rrect_mask(W, H, W / 2 - 110 * s, ytop + 22 * s, W / 2 + 110 * s, ytop + 86 * s, 32 * s, grid)
            out = over(out, hexrgb("#000000"), isl * k)
        # the cut-out on top: identical to the screen inside it, so only the part above the frame shows as new
        As = cv2.warpAffine(a, Ms, (W, H), flags=cv2.INTER_AREA)
        Fs = cv2.warpAffine(F, Ms, (W, H), flags=cv2.INTER_AREA)
        above = np.clip((ytop + bz * 0.5 - grid[0]) / (4 * s), 0, 1) * As
        hs = blur(np.roll(above, int(16 * s), axis=0), 10 * s) * 0.5
        out = out * (1 - (hs * np.clip(body + screen, 0, 1))[..., None])
        out = over(out, Fs, As * (screen + (1 - screen) * (grid[0] < ytop + bz) * k))
        yield np.clip(out, 0, 1)


def _word_spec(s):
    """'TEXT@16.32' or 'TEXT@16.32-17.40' (source seconds)."""
    text, _, tm = s.rpartition("@")
    a, _, b = tm.partition("-")
    return text, float(a), (float(b) if b else None)


def fx_sandwich(c, o):
    """Layered type: --behind words sit between the plate and the speaker, --front words sit over everything,
    a --through word slides across and passes THROUGH the speaker (in front on one side of the body, behind on
    the other), crossing the body on its spoken time."""
    W, H, s = c.w, c.h, c.s
    heads = [c.head(j) for j in range(0, c.n, 5)]
    hx = float(np.median([h[0] for h in heads]))
    top = float(np.median([h[1] for h in heads]))
    hw = float(np.median([h[2] for h in heads]))
    layers = []
    for spec in o.behind or []:
        text, ta, tb = _word_spec(spec)
        rgb, al = text_layer(text, o.word_size * s, o.behind_color)
        if al.shape[1] > 0.94 * W:  # fit the frame width
            rgb, al = text_layer(text, o.word_size * s * 0.94 * W / al.shape[1], o.behind_color)
        layers.append(("behind", rgb, al, ta - c.ss, (tb - c.ss) if tb else ta - c.ss + 1.6, hx, top + 0.33 * hw))
    for k, spec in enumerate(o.front or []):
        text, ta, tb = _word_spec(spec)
        rgb, al = text_layer(text, o.front_size * s, o.front_color, stroke=int(7 * s), stroke_color="#000000")
        if al.shape[1] > 0.94 * W:
            rgb, al = text_layer(text, o.front_size * s * 0.94 * W / al.shape[1], o.front_color, stroke=int(7 * s), stroke_color="#000000")
        layers.append(("front", rgb, al, ta - c.ss, (tb - c.ss) if tb else ta - c.ss + 1.5, W / 2, o.front_y * s + k * 0 * s))
    for spec in o.through or []:
        text, ta, _ = _word_spec(spec)
        rgb, al = text_layer(text, o.through_size * s, o.through_color, stroke=int(5 * s), stroke_color="#0b1020")
        layers.append(("through", rgb, al, ta - c.ss, None, hx, top + 0.62 * hw))
    xs = np.arange(W, dtype=np.float32)[None, :]
    for i in range(c.n):
        t = c.t(i)
        I, a, F = c.f(i), c.a(i), c.fg(i)
        hxi = c.head(i)[0]
        back, front = I.copy(), None
        fl = []
        for kind, rgb, al, ta, tb, cx, cy in layers:
            if kind == "through":
                vw = al.shape[1] + W  # crosses the frame in --through-dur seconds, centred on the spoken time
                x = hxi - (t - ta) / o.through_dur * vw
                if abs(x - hxi) > vw / 2 + 10:
                    continue
                lay, la = warp_layer((H, W), rgb, al, x, cy)
                side = (xs >= hxi).astype(np.float32)  # right of the body centre: in front; left: behind
                back = lay * (1 - side)[..., None] + back * (1 - (la * (1 - side))[..., None])
                fl.append((lay * side[..., None], la * side))
                continue
            if t < ta or t > tb:
                continue
            if kind == "behind":
                p = ease_out_expo((t - ta) / 0.45)
                out_p = smooth((t - (tb - 0.22)) / 0.22)
                back = place(back, rgb, al, cx, cy + 80 * s * (1 - p) - 40 * s * out_p, sy=1.6 - 0.6 * p, opacity=p * (1 - out_p))
            else:
                p = ease_out_back((t - ta) / 0.38, 2.2)
                out_p = smooth((t - (tb - 0.2)) / 0.2)
                lay, la = warp_layer((H, W), rgb, al, cx, cy, scale=max(0.01, 0.55 + 0.45 * p) * (1 - 0.1 * out_p))
                op = clamp01((t - ta) / 0.08) * (1 - out_p)
                fl.append((lay * op, la * op))
        out = over(back, F, a)
        for pm, la in fl:
            out = over_pm(out, pm, la)
        yield out


def best_frame(c, step=3):
    """A sharp, still frame: Laplacian variance in the head box minus motion against the neighbours."""
    best, bi = -1e9, 0
    for i in range(1, c.n - 1, step):
        cx, top, hw = c.head(i)
        x0, x1 = int(max(0, cx - hw / 2)), int(min(c.w, cx + hw / 2))
        y0, y1 = int(top), int(min(c.h, top + 1.2 * hw))
        g = cv2.cvtColor(c.rgb(i)[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY).astype(np.float32)
        if g.size < 100:
            continue
        sharp = cv2.Laplacian(g, cv2.CV_32F).var()
        mot = float(np.mean(np.abs(c.f(i + 1)[y0:y1, x0:x1] - c.f(i - 1)[y0:y1, x0:x1]))) * 255
        if i - 1 in c.cuts or i in c.cuts or i + 1 in c.cuts:
            continue
        sc = sharp - 40 * mot
        if sc > best:
            best, bi = sc, i
    return bi


def headline_block(lines, max_w, max_size, color="#ffffff", accent="#ffe14d", accent_ink="#111111", stroke=10, lh=0.98):
    """Stacked display lines; a line wrapped in *...* gets an accent box. Returns (rgb, a) of the block."""
    size = max_size
    while True:
        rows = []
        for ln in lines:
            hot = ln.startswith("*") and ln.endswith("*")
            txt = ln.strip("*")
            rows.append((hot, text_layer(txt, size, accent_ink if hot else color, stroke=0 if hot else stroke)))
        if max(r[1][1].shape[1] for r in rows) + (0.25 * size) <= max_w or size < 30:
            break
        size = int(size * 0.94)
    bw = int(max(r[1][1].shape[1] for r in rows) + 0.4 * size)
    gap = int(size * (lh - 0.86))
    bh = sum(r[1][1].shape[0] for r in rows) + gap * (len(rows) - 1) + int(0.3 * size)
    out = np.zeros((bh, bw, 3), np.float32)
    oa = np.zeros((bh, bw), np.float32)
    y = int(0.15 * size)
    for hot, (rgb, al) in rows:
        h, w = al.shape
        x = (bw - w) // 2
        if hot:
            box = np.zeros((h + int(0.16 * size), w + int(0.36 * size)), np.float32) + 1
            bx, ba = warp_layer((bh, bw), np.broadcast_to(hexrgb(accent), box.shape + (3,)).copy(), box, bw / 2, y + h / 2, angle=2.5)
            out = over_pm(out, bx, ba)
            oa = ba + oa * (1 - ba)
        pm, aw = warp_layer((bh, bw), rgb, al, bw / 2, y + h / 2, angle=2.5 if hot else 0)
        out = over_pm(out, pm, aw)
        oa = aw + oa * (1 - aw)
        y += h + gap
    return np.clip(out / np.maximum(oa[..., None], 1e-4), 0, 1), oa


def rays(w, h, cx, cy, n=18, amp=0.07, rot=0.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = np.arctan2(yy - cy, xx - cx) + rot
    return (np.cos(ang * n) > 0).astype(np.float32) * amp


def thumb(c, o):
    """Cover / thumbnail stills: the speaker cut out with a white outline on a bold gradient with rays, plus a big
    headline. Writes OUT-9x16.jpg (1080x1920) and OUT-16x9.jpg (1280x720) (+ .png with --png)."""
    i = c.frame_at(o.at) if o.at is not None else best_frame(c)
    log(f"thumbnail frame {i} (source {c.src_t(i):.2f} s)")
    F, a = c.fg(i), c.a(i)
    s = c.s
    cx, top, hw = c.head(i)
    lines = o.headline.split("|")
    cols = o.colors.split(",")
    outs = []
    for (Wt, Ht, tag) in ((1080, 1920, "9x16"), (1280, 720, "16x9")):
        if tag == "9x16":
            sc = o.cover_scale * 1080 / c.w
            hx_t, htop_t = Wt / 2, Ht * 0.40
        else:
            sc = (Ht * 0.62) / (1.25 * hw)
            hx_t, htop_t = Wt * 0.74, Ht * 0.10
        # place the frame so the head lands at (hx_t, htop_t)
        ox, oy = hx_t - cx * sc, htop_t - top * sc
        bg = gradient(Wt, Ht, cols[0], cols[-1], "radial", hx_t / Wt, (htop_t + 0.5 * hw * sc) / Ht)
        bg = np.clip(bg * (1 + rays(Wt, Ht, hx_t, htop_t + 0.5 * hw * sc, 16, 0.10)[..., None]), 0, 1)
        # fade the body out where the source frame cuts it (sides / bottom), so no hard frame edge shows on the cover
        H0, W0 = a.shape
        yy0, xx0 = np.mgrid[0:H0, 0:W0].astype(np.float32)
        edge = np.minimum(np.minimum(xx0, W0 - 1 - xx0), H0 - 1 - yy0)
        fade = np.clip(edge / (90 * s), 0, 1) ** 1.5
        rgb, sa, ap, dist, P = sticker_layer(F, a, s, o.stroke, open_edges=True)
        sa = sa * np.pad(fade, P)
        Mt = np.float32([[sc, 0, ox - P * sc], [0, sc, oy - P * sc]])
        pm = cv2.warpAffine(rgb * sa[..., None], Mt, (Wt, Ht), flags=cv2.INTER_AREA)
        aw = cv2.warpAffine(sa, Mt, (Wt, Ht), flags=cv2.INTER_AREA)
        Ms = Mt.copy()
        Ms[0, 2] += 14 * Wt / 1080
        Ms[1, 2] += 22 * Wt / 1080
        sh = blur(cv2.warpAffine(sa, Ms, (Wt, Ht), flags=cv2.INTER_AREA), 16 * Wt / 1080) * 0.5
        out = over_pm(bg * (1 - sh[..., None]), pm, aw)
        if tag == "9x16":
            brgb, ba = headline_block(lines, Wt - 110, 210, accent=o.accent)
            bh = ba.shape[0]
            cyb = max(bh / 2 + 110, htop_t - bh / 2 - 40)
            out = place(out, brgb, ba, Wt / 2, cyb)
        else:
            brgb, ba = headline_block(lines, int(Wt * 0.52), 128, accent=o.accent, stroke=7)
            out = place(out, brgb, ba, Wt * 0.30, Ht / 2)
        img = np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)
        p = f"{o.out}-{tag}.jpg"
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(p, cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
        if o.png:
            cv2.imwrite(f"{o.out}-{tag}.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        outs.append(p)
        log(f"wrote {p}")
    return outs


# ------------------------------------------------------------------ stills: what each model can do
def _label(img, text, x=18, y=18, size=26):
    rgb, al = text_layer(text, size, "#ffffff", family="montserrat", weight="SemiBold", tracking=0.0)
    h, w = al.shape
    box = np.zeros((h + 16, w + 28), np.float32) + 1
    img = place(img, np.zeros(box.shape + (3,), np.float32), box * 0.62, x + box.shape[1] / 2, y + box.shape[0] / 2)
    return place(img, rgb, al, x + box.shape[1] / 2, y + box.shape[0] / 2)


def checker(w, h, k=24):
    yy, xx = np.mgrid[0:h, 0:w]
    v = (((yy // k) + (xx // k)) % 2).astype(np.float32) * 0.18 + 0.72
    return np.repeat(v[..., None], 3, -1)


def still_result(I, a, F, kind, color="#2a5bff", glow="#38f6ff"):
    h, w = a.shape
    s = w / 1080
    if kind == "checker":
        return over(checker(w, h, max(8, int(24 * s))), F, a)
    if kind == "white":
        return over(np.ones_like(I), F, a)
    if kind == "color":
        return over(np.broadcast_to(hexrgb(color), I.shape).copy(), F, a)
    if kind == "highlight":  # camouflage: dim + desaturate the world, outline what the model found
        g = lum(I)[..., None]
        base = over((g * 0.7 + I * 0.3) * 0.38, I, a)
        m = (a > 0.5).astype(np.uint8)
        line = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))).astype(np.float32)
        gl = blur(line, 4 * s) * 1.2 + blur(line, 14 * s) * 0.9
        return np.clip(base + (gl + line)[..., None] * hexrgb(glow), 0, 1)
    if kind == "product":  # e-commerce: object re-framed on white with a soft contact shadow
        ys, xs = np.nonzero(a > 0.5)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        bw, bh = x1 - x0, y1 - y0
        side = int(max(bw, bh) * 1.3)
        out = np.ones((side, side, 3), np.float32)
        ox, oy = (side - bw) // 2 - x0, int((side - bh) * 0.42) - y0
        Mt = np.float32([[1, 0, ox], [0, 1, oy]])
        aw = cv2.warpAffine(a, Mt, (side, side))
        Fw = cv2.warpAffine(F, Mt, (side, side))
        yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
        gy = oy + y1
        ell = np.exp(-(((xx - side / 2) / (bw * 0.5)) ** 2 + ((yy - gy) / (bh * 0.05 + 6)) ** 2) * 1.5) * 0.35
        out = out * (1 - ell[..., None])
        out = over(out, Fw, aw)
        return cv2.resize(out, (int(w * h / side) if False else side, side))
    raise SystemExit(f"unknown result {kind}")


def still(img, model, result="checker", out="still", zoom=None, panel_h=720, color="#2a5bff", net=None, title=None):
    """input | alpha | result for one image. zoom = 'x,y,w,h' (fractions): a second row with 2x crops of the three."""
    rgb = load_rgb(img)
    h, w = rgb.shape[:2]
    name, size = parse_model(model, (w, h))
    net = net if (net is not None and net.name == name) else Net(name)
    t0 = time.time()
    a = net.predict(rgb, size)
    net.sync()
    dt = time.time() - t0
    I = rgb.astype(np.float32) / 255.0
    F = decontam(I, a)
    res = still_result(I, a, F, result, color)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(f"{out}-alpha.png", np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8))
    rgba = np.dstack([np.clip(F * 255 + 0.5, 0, 255), np.clip(a * 255 + 0.5, 0, 255)]).astype(np.uint8)
    cv2.imwrite(f"{out}-cutout.png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    A3 = np.repeat(a[..., None], 3, -1)

    def fit(x):
        return cv2.resize(x, (int(x.shape[1] * panel_h / x.shape[0]), panel_h), interpolation=cv2.INTER_AREA)

    rlab = {"checker": "cut-out", "white": "cut-out on white", "color": "cut-out on colour", "highlight": "found it",
            "product": "product shot"}[result]
    sz = f"{size[0]}x{size[1]}" if size[0] != size[1] else str(size[0])
    panels = [_label(fit(I), "input"), _label(fit(A3), f"alpha: {MODELS[name][0].split('/')[-1]} @{sz}"), _label(fit(res), rlab)]
    gap = np.ones((panel_h, 8, 3), np.float32) * 0.07
    row = np.hstack([panels[0], gap, panels[1], gap, panels[2]])
    if zoom:
        fx, fy, fw, fh = (float(v) for v in zoom.split(","))
        x0, y0, cw, ch = int(fx * w), int(fy * h), int(fw * w), int(fh * h)
        res_full = res if res.shape[:2] == (h, w) else over(np.ones_like(I) * hexrgb(color), F, a)
        crops = [I[y0:y0 + ch, x0:x0 + cw], A3[y0:y0 + ch, x0:x0 + cw], res_full[y0:y0 + ch, x0:x0 + cw]]
        cw_t = (row.shape[1] - 16) // 3
        ch_t = int(cw_t * ch / cw)
        cr = [_label(cv2.resize(x, (cw_t, ch_t), interpolation=cv2.INTER_CUBIC), f"{cw_t / cw:.1f}x crop") for x in crops]
        g2 = np.ones((ch_t, 8, 3), np.float32) * 0.07
        r2 = np.hstack([cr[0], g2, cr[1], g2, cr[2]])
        r2 = cv2.resize(r2, (row.shape[1], r2.shape[0])) if r2.shape[1] != row.shape[1] else r2
        row = np.vstack([row, np.ones((8, row.shape[1], 3), np.float32) * 0.07, r2])
    img8 = np.clip(row * 255 + 0.5, 0, 255).astype(np.uint8)
    cv2.imwrite(f"{out}.jpg", cv2.cvtColor(img8, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
    info = dict(image=str(img), model=name, infer=list(size), seconds=round(dt, 2), out=f"{out}.jpg", size=[w, h])
    log(json.dumps(info))
    return info, net


# ------------------------------------------------------------------ quality comparison clip
def compare(src, ss, t, configs, out, crop="0.17,0.13,0.66,0.66", bgc="#2ecc71", fps_from=None, size=(540, 960), audio=None):
    """The same window matted by up to 4 configs, composited over a flat colour, 2x2 grid of the head-and-hands crop."""
    bench = {}
    if fps_from and Path(fps_from).exists():
        for r in json.loads(Path(fps_from).read_text())["rows"]:
            if r["batch"] == 1:
                bench[r["config"]] = r["fps"]
    base = Clip(src, ss, t, configs[0], 1.0)
    alphas = [base._a]
    names = [configs[0]]
    for cfg in configs[1:]:
        d = ensure_alpha(src, ss, t, cfg)
        al = decode_gray(d / "alpha.mkv", base.w, base.h, base.n)
        for k in range(len(al)):
            fill_bottom_holes(al[k])
        alphas.append(al)
        names.append(cfg)
    n = min(len(x) for x in alphas)
    fx, fy, fw, fh = (float(v) for v in crop.split(","))
    x0, y0, cw, ch = int(fx * base.w), int(fy * base.h), int(fw * base.w), int(fh * base.h)
    pw, ph = size[0] // 2, size[1] // 2
    col = hexrgb(bgc)
    wr = Writer(out, size[0], size[1], base.fps, audio, ss, n / base.fps)
    labels = []
    for nm in names:
        name, sz = parse_model(nm, (base.W0, base.H0))
        key = f"{name}@{sz[0]}x{sz[1]}"
        labels.append(f"{name} {sz[0]}" + (f"  {bench[key]:.2f} fps" if key in bench else ""))
    for i in range(n):
        I = base.f(i)
        grid = np.zeros((size[1], size[0], 3), np.float32)
        for k, A in enumerate(alphas):
            a = A[i].astype(np.float32) / 255.0
            F = decontam(I[y0:y0 + ch, x0:x0 + cw], a[y0:y0 + ch, x0:x0 + cw])
            comp = over(np.broadcast_to(col, F.shape).copy(), F, a[y0:y0 + ch, x0:x0 + cw])
            p = cv2.resize(comp, (pw, ph), interpolation=cv2.INTER_AREA)
            p = _label(p, labels[k], 10, 10, 17)
            r, cc = divmod(k, 2)
            grid[r * ph:(r + 1) * ph, cc * pw:(cc + 1) * pw] = p
        grid[ph - 1:ph + 1, :] = 0.05
        grid[:, pw - 1:pw + 1] = 0.05
        wr.write(grid)
    wr.close()
    return names


def compare_crops(src, ss, t, configs, frame, out, box="0.30,0.33,0.36,0.20", fps_from=None):
    """One frame, 100% crops of a hard region for each config, side by side (over the flat colour)."""
    base = Clip(src, ss, t, configs[0], 1.0)
    fx, fy, fw, fh = (float(v) for v in box.split(","))
    x0, y0, cw, ch = int(fx * base.w), int(fy * base.h), int(fw * base.w), int(fh * base.h)
    I = base.f(frame)[y0:y0 + ch, x0:x0 + cw]
    bench = {}
    if fps_from and Path(fps_from).exists():
        for r in json.loads(Path(fps_from).read_text())["rows"]:
            if r["batch"] == 1:
                bench[r["config"]] = r["fps"]
    tiles = [_label(I.copy(), "source", 10, 10, 18)]
    for cfg in configs:
        d = ensure_alpha(src, ss, t, cfg)
        a = fill_bottom_holes(decode_gray(d / "alpha.mkv", base.w, base.h, frame + 1)[frame]).astype(np.float32)[y0:y0 + ch, x0:x0 + cw] / 255.0
        name, sz = parse_model(cfg, (base.W0, base.H0))
        key = f"{name}@{sz[0]}x{sz[1]}"
        F = decontam(I, a)
        tiles.append(_label(over(np.broadcast_to(hexrgb("#2ecc71"), F.shape).copy(), F, a), f"{name} {sz[0]}" + (f" {bench[key]:.2f} fps" if key in bench else ""), 10, 10, 18))
    gap = np.ones((ch, 6, 3), np.float32) * 0.07
    row = tiles[0]
    for tl in tiles[1:]:
        row = np.hstack([row, gap, tl])
    cv2.imwrite(out, cv2.cvtColor(np.clip(row * 255 + 0.5, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    log(f"wrote {out}")


def export_webm(c, out, crf=18):
    """VP9 + alpha cut-out (decontaminated edge colour) for HyperFrames, same frames as the window."""
    info = dict(w=c.w, h=c.h, fps=c.fps, fps_str=c.meta["fps_str"])
    enc = M.encoder(out + ".part", info, crf)
    for i in range(c.n):
        F, a = c.fg(i), c.a(i)
        rgba = np.dstack([np.clip(F * 255 + 0.5, 0, 255), np.clip(a * 255 + 0.5, 0, 255)]).astype(np.uint8)
        enc.stdin.write(rgba.tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit("ffmpeg webm encode failed")
    os.replace(out + ".part", out)
    log(f"wrote {out}")


# ------------------------------------------------------------------ CLI
FX = {"bg-swap": fx_bg_swap, "bg-blur": fx_bg_blur, "selective": fx_selective, "spotlight": fx_spotlight,
      "sticker": fx_sticker, "neon": fx_neon, "clones": fx_clones, "pop": fx_pop, "sandwich": fx_sandwich}
DEFAULT_MODEL = os.environ.get("CUTOUT_FX_MODEL", "lite@1024")


def has_audio(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", src],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def clip_args(p, out=True):
        p.add_argument("src")
        p.add_argument("--ss", type=float, default=0.0, help="window start (source seconds)")
        p.add_argument("--t", type=float, default=5.0, help="window length (s)")
        p.add_argument("--model", default=DEFAULT_MODEL, help=f"NAME[@SIZE] (default {DEFAULT_MODEL})")
        p.add_argument("--batch", type=int, default=1, help="frames per model call (lite: 4 is faster on MPS)")
        p.add_argument("--scale", type=float, default=1.0, help="work at this fraction of the source size (0.5 = preview)")
        if out:
            p.add_argument("-o", "--out", required=True)
            p.add_argument("--size", help="final WxH (e.g. 540x960)")
            p.add_argument("--audio", help="audio file for the same window (default: the source's own audio)")
            p.add_argument("--no-audio", action="store_true")
            p.add_argument("--crf", type=int, default=17)
            p.add_argument("--at", type=float, help="effect start, source seconds (default: 0.4 s into the window)")
            p.add_argument("--release", type=float, default=0.0,
                           help="ease back into the source over the last N seconds (0 = the effect runs to the last frame)")

    p = sub.add_parser("alpha", help="compute / reuse the cached alpha")
    clip_args(p, out=False)
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("webm", help="VP9+alpha cut-out for HyperFrames")
    clip_args(p, out=False)
    p.add_argument("-o", "--out", required=True)

    p = sub.add_parser("bg-swap"); clip_args(p)
    p.add_argument("--bg", required=True, help="image, video, #hex or #hex1,#hex2")
    p.add_argument("--bg2", help="second background (switches at --switch, default mid-window)")
    p.add_argument("--switch", type=float, help="source second of the switch to --bg2 (put it on a cut)")
    p.add_argument("--wrap", type=float, default=0.55, help="light wrap strength 0..1")
    p.add_argument("--match", type=float, default=0.5, help="pull the speaker's colour toward the scene 0..1")
    p.add_argument("--defocus", type=float, default=2.0, help="background blur px (depth)")
    p.add_argument("--push", type=float, default=1.06, help="slow push-in on a still background")
    p.add_argument("--wipe", type=float, default=0.5, help="reveal wipe seconds (0 = cut)")
    p = sub.add_parser("bg-blur"); clip_args(p)
    p.add_argument("--radius", type=float, default=26.0, help="lens blur radius px at full strength")
    p.add_argument("--ramp", type=float, default=0.9, help="seconds to rack focus")
    p.add_argument("--bokeh", type=float, default=1.0, help="highlight bloom 0..1")
    p.add_argument("--dim", type=float, default=0.0, help="also darken the background 0..1")
    p = sub.add_parser("selective"); clip_args(p)
    p.add_argument("--look", default="bw", choices=["bw", "noir", "film"])
    p.add_argument("--ramp", type=float, default=0.6)
    p = sub.add_parser("spotlight"); clip_args(p)
    p.add_argument("--dim", type=float, default=0.18, help="background brightness outside the pool")
    p.add_argument("--ramp", type=float, default=0.6)
    p.add_argument("--color", default="#ffb46b", help="tint of the light pool")
    p = sub.add_parser("sticker"); clip_args(p)
    p.add_argument("--freeze", type=float, help="source second of the frozen frame (default 0.8 s into the window)")
    p.add_argument("--hold", type=float, default=2.6, help="seconds the sticker stays before the video resumes")
    p.add_argument("--stroke", type=float, default=22, help="white outline px")
    p.add_argument("--sticker-scale", type=float, default=0.84, help="sticker size after the pop")
    p.add_argument("--bg", default="plate", help="plate (frozen frame without the speaker, dimmed), dim (frozen frame, dimmed) or a background spec")
    p = sub.add_parser("neon"); clip_args(p)
    p.add_argument("--colors", default="#38f6ff,#ff3df2")
    p.add_argument("--trace", type=float, default=1.3, help="seconds to trace the outline")
    p.add_argument("--dim", type=float, default=0.32, help="background brightness under the neon")
    p = sub.add_parser("clones"); clip_args(p)
    p.add_argument("--offsets", default="0,0.4,0.8", help="seconds: middle, left, right copy")
    p.add_argument("--bust", default="0.10,0.12,0.80,0.62", help="x,y,w,h (fractions): the part of the frame each copy shows")
    p.add_argument("--mid-scale", type=float, default=0.72, help="middle bust width, fraction of the frame")
    p.add_argument("--side-scale", type=float, default=0.54, help="side bust width")
    p.add_argument("--backdrop", default="#3a2a1c,#0c0c10")
    p.add_argument("--light", default="#ffb46b")
    p = sub.add_parser("pop"); clip_args(p)
    p.add_argument("--frame", default="phone", choices=["phone", "card"])
    p.add_argument("--bg", default="#ff7a18,#7a0b2e", help="background spec or 'blur'")
    p.add_argument("--plate", type=float, default=0.78, help="video size inside the frame")
    p.add_argument("--bottom", type=float, default=150, help="px from the frame's bottom to the canvas bottom")
    p.add_argument("--brk", type=float, default=0.62, help="frame top after the pop, in head widths below the top of the head")
    p = sub.add_parser("sandwich"); clip_args(p)
    p.add_argument("--behind", action="append", help="TEXT@start[-end] (source s), between plate and speaker")
    p.add_argument("--front", action="append", help="TEXT@start[-end], over everything")
    p.add_argument("--through", action="append", help="TEXT@time: slides across, crossing the speaker at that time")
    p.add_argument("--word-size", type=float, default=300, help="max px size of a behind word (auto-fits the width)")
    p.add_argument("--behind-color", default="#ffd23f")
    p.add_argument("--front-size", type=float, default=170)
    p.add_argument("--front-color", default="#ffffff")
    p.add_argument("--front-y", type=float, default=1010, help="px from the top (1080-wide frame): over the chin / hand")
    p.add_argument("--through-size", type=float, default=200)
    p.add_argument("--through-color", default="#38f6ff")
    p.add_argument("--through-dur", type=float, default=1.9, help="seconds to cross the whole frame")
    p = sub.add_parser("thumb", help="cover stills 1080x1920 + 1280x720"); clip_args(p, out=False)
    p.add_argument("-o", "--out", required=True, help="prefix: writes PREFIX-9x16.jpg and PREFIX-16x9.jpg")
    p.add_argument("--headline", required=True, help="lines split by |, *line* = accent box")
    p.add_argument("--at", type=float, help="source second of the frame (default: the sharpest still frame)")
    p.add_argument("--colors", default="#ff6a1a,#5a0a26")
    p.add_argument("--accent", default="#ffe14d")
    p.add_argument("--stroke", type=float, default=16)
    p.add_argument("--cover-scale", type=float, default=1.0, help="speaker size on the 9x16 cover")
    p.add_argument("--png", action="store_true")

    p = sub.add_parser("still", help="input | alpha | result for one image")
    p.add_argument("img")
    p.add_argument("--model", default="general")
    p.add_argument("--result", default="checker", choices=["checker", "white", "color", "highlight", "product"])
    p.add_argument("--color", default="#2a5bff")
    p.add_argument("--zoom", help="x,y,w,h fractions: add a row of crops")
    p.add_argument("-o", "--out", required=True, help="prefix: PREFIX.jpg, PREFIX-alpha.png, PREFIX-cutout.png")
    p = sub.add_parser("bench")
    p.add_argument("src")
    p.add_argument("--ss", type=float, default=0.0)
    p.add_argument("--frames", type=int, default=30)
    p.add_argument("--configs", default="portrait@1024,lite@1024,lite@768,lite@512")
    p.add_argument("--batches", default="1,4")
    p.add_argument("-o", "--out")
    p = sub.add_parser("compare"); clip_args(p, out=False)
    p.add_argument("--configs", default="portrait@1024,lite@1024,lite@768,lite@512")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--bench", help="bench json for the fps labels")
    p.add_argument("--crops", help="also write 100%% crops of this frame index to OUT.crops.jpg", type=int)

    o = ap.parse_args(argv)
    if o.cmd == "alpha":
        print(ensure_alpha(o.src, o.ss, o.t, o.model, batch=o.batch, force=o.force))
        return
    if o.cmd == "bench":
        bench(o.src, o.ss, o.frames, o.configs.split(","), tuple(int(x) for x in o.batches.split(",")), o.out)
        return
    if o.cmd == "still":
        still(o.img, o.model, o.result, o.out, o.zoom, color=o.color)
        return
    if o.cmd == "compare":
        cf = o.configs.split(",")
        compare(o.src, o.ss, o.t, cf, o.out, fps_from=o.bench)
        if o.crops is not None:
            compare_crops(o.src, o.ss, o.t, cf, o.crops, o.out.rsplit(".", 1)[0] + ".crops.jpg", fps_from=o.bench)
        return
    # a render whose inputs and options have not changed is reused (build.mjs calls this on every build)
    code = hashlib.sha1(Path(__file__).read_bytes() + Path(M.__file__).read_bytes()).hexdigest()[:10]  # a code change re-renders
    sig = dict(vars(o), v=VERSION, code=code, srcsig=src_sig(o.src))
    for k in ("bg", "bg2", "audio"):
        if isinstance(sig.get(k), str) and Path(sig[k]).exists():
            sig[k + "sig"] = src_sig(sig[k])
    sig = json.loads(json.dumps(sig, default=str))
    side = Path(str(o.out) + ".json")
    done = [Path(o.out)] if o.cmd != "thumb" else [Path(f"{o.out}-9x16.jpg"), Path(f"{o.out}-16x9.jpg")]
    if all(p.exists() for p in done) and side.exists() and json.loads(side.read_text()).get("sig") == sig:
        log(f"cached: {o.out}")
        return
    c = Clip(o.src, o.ss, o.t, o.model, o.scale, o.batch)
    if o.cmd == "webm":
        export_webm(c, o.out)
        side.write_text(json.dumps(dict(sig=sig), indent=1))
        return
    if o.cmd == "thumb":
        thumb(c, o)
        side.write_text(json.dumps(dict(sig=sig), indent=1))
        return
    audio = None if o.no_audio else (o.audio or (o.src if has_audio(o.src) else None))
    size = tuple(int(v) for v in o.size.lower().split("x")) if getattr(o, "size", None) and isinstance(o.size, str) else None
    T0 = time.time()
    wr = Writer(o.out, c.w, c.h, c.fps, audio, o.ss, c.n / c.fps, o.crf, size)
    # --release: blend back to the source frame the effect is drawn over (clones: the middle copy's offset)
    off, n_out = 0, c.n
    if o.cmd == "clones":
        offs = [int(round(float(x) * c.fps)) for x in o.offsets.split(",")]
        off, n_out = (offs + [0])[0], c.n - max(offs)
    rel_n = 0 if o.cmd == "sticker" else int(round(max(0.0, o.release) * c.fps))
    for i, fr in enumerate(FX[o.cmd](c, o)):
        left = n_out - 1 - i  # frames after this one
        if rel_n and left < rel_n:
            if fr.dtype == np.uint8:
                fr = fr.astype(np.float32) / 255.0
            raw = c.f(i + off)
            fr = raw + (fr - raw) * smooth(left / rel_n)  # the last frame is the source frame itself
        wr.write(fr)
    wr.close()
    side.write_text(json.dumps(dict(sig=sig, frames=wr.k, fps=c.fps, seconds=round(time.time() - T0, 1)), indent=1))
    log(f"{o.cmd}: {wr.k} frames in {time.time() - T0:.1f} s ({wr.k / max(1e-6, time.time() - T0):.2f} fps effect + encode)")


if __name__ == "__main__":
    main()
