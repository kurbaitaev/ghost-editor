#!/usr/bin/env python3
"""matte.py: person matte for text-behind-the-speaker (VP9 + alpha WebM).

Replaces `npx hyperframes remove-background` (u2net_human_seg, 2020) in ghost-editor.

  pass 1  ffmpeg decode at model size -> cut detection -> BiRefNet-portrait on every wanted frame
          (one session for the whole run; torch-MPS or ONNX Runtime via rembg)
  pass 2  ffmpeg decode at full size -> temporal filter on the model alpha (median of 3 +
          deadband EMA, reset on cuts) -> fast guided filter: low-res alpha upsampled against the
          full-res colour frame -> colour decontamination (blur-fusion foreground estimate) ->
          ffmpeg libvpx-vp9 yuva420p, same frame count / fps / size as the source

Usage:
  matte.py SRC.mp4 -o talk-matte.webm                        # whole file
  matte.py SRC.mp4 -o talk-matte.webm --ranges 17.0-18.6      # only matte these SRC seconds
  matte.py SRC.mp4 -o test.webm --ss 14 --t 6 --backend ort --provider cpu

Frames outside --ranges are written fully transparent (cheap), so the WebM always lines up
frame-for-frame with SRC. A sidecar OUT.json records what was computed; a later call whose
ranges are already covered (same source, same settings) is a no-op.

Models (weights MIT; rembg's default `bria-rmbg` is refused: it needs a paid licence):
  birefnet-portrait (default), birefnet-hrsod, birefnet-general-lite, ben2-base (ONNX only)
Backends:
  torch  BiRefNet code + safetensors from huggingface.co/ZhengPeng7/<repo>, fp16 on Apple MPS
  ort    rembg session (ONNX Runtime), provider cpu (coreml never finished compiling BiRefNet on an M3)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # torchvision deform_conv2d has no MPS kernel

import cv2
import numpy as np

VERSION = "0.3.0"
CACHE = Path(os.environ.get("GHOST_MATTE_CACHE", "~/.cache/ghost-matte")).expanduser()
IMAGENET = ((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))

MODELS = {
    "birefnet-portrait": dict(hf="ZhengPeng7/BiRefNet-portrait", norm=IMAGENET, logits=True),
    "birefnet-hrsod": dict(hf="ZhengPeng7/BiRefNet-HRSOD", norm=IMAGENET, logits=True),
    "birefnet-general-lite": dict(hf="ZhengPeng7/BiRefNet_lite", norm=IMAGENET, logits=True),
    "ben2-base": dict(onnx="~/.rembg/models/ben2-base/BEN2_Base.onnx",
                      url="https://huggingface.co/PramaLLC/BEN2/resolve/main/BEN2_Base.onnx",
                      norm=((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)), logits=None),
}
HF_FILES = ["birefnet.py", "BiRefNet_config.py", "config.json", "model.safetensors"]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- probing / io
def probe(src: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,color_space,color_range:stream_side_data=rotation:format=duration",
         "-of", "json", src], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = int(s["width"]), int(s["height"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = (int(x) for x in s["r_frame_rate"].split("/"))
    return dict(w=w, h=h, fps_str=f"{num}/{den}", fps=num / den, duration=float(j["format"]["duration"]),
                color_space=s.get("color_space", ""), color_range=s.get("color_range", ""))


def decode(src, info, ss, t, size, q: queue.Queue):
    """Decode SRC (from ss, for t seconds) to RGB24 frames of `size` (w, h) into q, then None."""
    w, h = size
    matrix = {"bt709": "bt709", "bt470bg": "bt601", "smpte170m": "bt601", "bt2020nc": "bt2020"}.get(info["color_space"], "auto")
    rng = "pc" if info["color_range"] == "pc" else "tv"
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if ss:
        cmd += ["-ss", f"{ss:.6f}"]
    cmd += ["-i", src]
    if t:
        cmd += ["-t", f"{t:.6f}"]
    # accurate_rnd+full_chroma_int: swscale's default yuv->rgb path (ffmpeg 8.1, arm64) reads tv-range footage 1-2 levels
    # dark, and every cutout/matte pass wrote that back into the clip; with them the decode matches BT.709 (tests/test_decode_levels.py)
    cmd += ["-map", "0:v:0", "-vf",
            f"scale={w}:{h}:flags=area+accurate_rnd+full_chroma_int:in_color_matrix={matrix}:in_range={rng}:out_range=pc,format=rgb24",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            q.put(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
    finally:
        q.put(None)
        p.stdout.close()
        p.wait()


def frames(src, info, ss, t, size):
    q: queue.Queue = queue.Queue(maxsize=8)
    threading.Thread(target=decode, args=(src, info, ss, t, size, q), daemon=True).start()
    while True:
        f = q.get()
        if f is None:
            return
        yield f


def encoder(out, info, crf):
    w, h = info["w"], info["h"]
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", info["fps_str"], "-i", "-",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuva420p",
           "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", str(crf), "-b:v", "0",
           "-deadline", "good", "-cpu-used", "4", "-row-mt", "1", "-auto-alt-ref", "0", "-g", str(int(round(info["fps"] * 2))),
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-metadata:s:v:0", "alpha_mode=1", "-metadata", f"comment=ghost-matte {VERSION}", "-f", "webm", out]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


# ---------------------------------------------------------------- model backends
def ort_providers(name: str):
    import onnxruntime as ort
    avail = ort.get_available_providers()
    if name == "auto":
        name = "cpu"  # CoreML compiles BiRefNet into ~70 partitions and takes >20 min to load; opt in explicitly
    if name == "cpu":
        return name, ["CPUExecutionProvider"]
    if name.startswith("coreml"):
        if "CoreMLExecutionProvider" not in avail:
            raise SystemExit("CoreML execution provider is not available in this onnxruntime build")
        (CACHE / "coreml").mkdir(parents=True, exist_ok=True)
        units = {"coreml": "ALL", "coreml-gpu": "CPUAndGPU", "coreml-ane": "CPUAndNeuralEngine"}[name]
        return name, [("CoreMLExecutionProvider", {"ModelFormat": "MLProgram", "MLComputeUnits": units,
                                                   "ModelCacheDirectory": str(CACHE / "coreml")}), "CPUExecutionProvider"]
    raise SystemExit(f"unknown provider {name}")


def hf_dir(repo: str) -> Path:
    d = CACHE / "hf" / repo.split("/")[-1]
    d.mkdir(parents=True, exist_ok=True)
    for f in HF_FILES:
        if not (d / f).exists():
            log(f"downloading {repo}/{f}")
            subprocess.run(["curl", "-fsSL", "-o", str(d / f) + ".part", f"https://huggingface.co/{repo}/resolve/main/{f}"], check=True)
            os.replace(str(d / f) + ".part", d / f)
    return d


class Matter:
    """Loads one model session and reuses it for every frame. __call__: RGB uint8 at `self.size`
    (w, h) -> alpha float32 0..1 at the same size."""

    def __init__(self, model: str, backend: str, provider: str, size: tuple[int, int], threads: int = 0):
        if "bria" in model.lower():
            raise SystemExit("refusing bria models: BRIA RMBG weights need a paid commercial licence")
        if model not in MODELS:
            raise SystemExit(f"unknown model {model}; choose from {', '.join(MODELS)}")
        self.model, self.cfg = model, dict(MODELS[model])
        mean, std = self.cfg["norm"]
        self.mean = np.array(mean, np.float32).reshape(1, 1, 3)
        self.std = np.array(std, np.float32).reshape(1, 1, 3)
        if backend == "auto":
            backend = "ort"
            if "hf" in self.cfg:
                try:
                    import torch
                    if torch.backends.mps.is_available():
                        backend = "torch"
                except ImportError:
                    pass
        self.backend = backend
        t0 = time.time()
        if backend == "torch":
            self._load_torch()
            self.size = size
            self.device_name = "torch-mps-fp16"
        else:
            self._load_ort(provider, threads)
            self.size = (1024, 1024)  # the ONNX exports have a fixed 1024x1024 input
        self.load_s = time.time() - t0
        log(f"model {model} on {self.device_name}, input {self.size[0]}x{self.size[1]} (load {self.load_s:.1f}s)")

    def _load_torch(self):
        import torch
        import transformers
        transformers.logging.set_verbosity_error()
        from transformers import AutoModelForImageSegmentation
        if "hf" not in self.cfg:
            raise SystemExit(f"{self.model} has no torch weights here; use --backend ort")
        d = hf_dir(self.cfg["hf"])
        m = AutoModelForImageSegmentation.from_pretrained(str(d), trust_remote_code=True)
        self.torch = torch
        self.dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.dtype = torch.float16 if self.dev.type == "mps" else torch.float32
        self.net = m.eval().to(self.dev).to(self.dtype)

    def _load_ort(self, provider, threads):
        import onnxruntime as ort
        ort.set_default_logger_severity(3)
        self.provider, provs = ort_providers(provider)
        so = ort.SessionOptions()
        so.log_severity_level = 3
        if threads:
            so.intra_op_num_threads = threads
        if "onnx" in self.cfg:
            path = Path(self.cfg["onnx"]).expanduser()
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                log(f"downloading {self.cfg['url']}")
                subprocess.run(["curl", "-fL", "-o", str(path) + ".part", self.cfg["url"]], check=True)
                os.replace(str(path) + ".part", path)
            self.sess = ort.InferenceSession(str(path), so, providers=provs)
        else:
            from rembg import new_session  # fetches ~/.rembg/models/<name>/<name>.onnx on first use
            self.sess = new_session(self.model, sess_opts=so, providers=provs).inner_session
        self.inp = self.sess.get_inputs()[0].name
        self.device_name = f"onnxruntime-{self.sess.get_providers()[0].replace('ExecutionProvider', '').lower()}"

    def __call__(self, rgb_small: np.ndarray) -> np.ndarray:
        # straight /255 + mean/std, no per-frame max stretch and no min/max stretch of the output:
        # rembg does both, and both make the alpha level pump from frame to frame
        x = (rgb_small.astype(np.float32) / 255.0 - self.mean) / self.std
        x = np.ascontiguousarray(x.transpose(2, 0, 1)[None])
        if self.backend == "torch":
            t = self.torch
            with t.inference_mode():
                y = self.net(t.from_numpy(x).to(self.dev, self.dtype))[-1]
                y = y.float().sigmoid()[0, 0].cpu().numpy()
            if self.dev.type == "mps":
                # BiRefNet at 1024^2 peaks at several GB of unified memory; without this the MPS
                # cache keeps ~6 GB resident and a 16 GB Mac starts swapping GPU buffers
                self.peak_gb = max(getattr(self, "peak_gb", 0.0), t.mps.driver_allocated_memory() / 2**30)
                t.mps.empty_cache()
            return y
        y = self.sess.run(None, {self.inp: x})[0][0, 0].astype(np.float32)
        if self.cfg["logits"] is None:  # BEN2 export: decide once from the value range
            self.cfg["logits"] = bool(y.min() < -0.01 or y.max() > 1.01)
        if self.cfg["logits"]:
            y = 1.0 / (1.0 + np.exp(-y))
        return np.clip(y, 0.0, 1.0)


# ---------------------------------------------------------------- refinement
def _box(x, r):
    return cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1), normalize=True, borderType=cv2.BORDER_REFLECT)


def fast_guided_upsample(guide_full: np.ndarray, p_low: np.ndarray, r: int, eps: float, s: int) -> np.ndarray:
    """Colour-guide fast guided filter (He, Sun & Tang 2010; He & Sun 2015, arXiv:1505.00996).
    guide_full: HxWx3 float32 0..1; p_low: alpha at any resolution. Statistics at 1/s resolution,
    the linear coefficients are upsampled and applied to the full-res guide, so the edge follows the
    real frame instead of the blocky model output."""
    H, W = guide_full.shape[:2]
    h, w = H // s, W // s
    I = cv2.resize(guide_full, (w, h), interpolation=cv2.INTER_AREA)
    p = cv2.resize(p_low, (w, h), interpolation=cv2.INTER_LINEAR)
    rl = max(1, r // s)
    mI = _box(I, rl)
    mp = _box(p, rl)
    cov = _box(I * p[..., None], rl) - mI * mp[..., None]
    r_, g_, b_ = I[..., 0], I[..., 1], I[..., 2]
    vrr = _box(r_ * r_, rl) - mI[..., 0] ** 2 + eps
    vrg = _box(r_ * g_, rl) - mI[..., 0] * mI[..., 1]
    vrb = _box(r_ * b_, rl) - mI[..., 0] * mI[..., 2]
    vgg = _box(g_ * g_, rl) - mI[..., 1] ** 2 + eps
    vgb = _box(g_ * b_, rl) - mI[..., 1] * mI[..., 2]
    vbb = _box(b_ * b_, rl) - mI[..., 2] ** 2 + eps
    irr = vgg * vbb - vgb * vgb  # adjugate of the symmetric 3x3 covariance
    irg = vgb * vrb - vrg * vbb
    irb = vrg * vgb - vgg * vrb
    igg = vrr * vbb - vrb * vrb
    igb = vrb * vrg - vrr * vgb
    ibb = vrr * vgg - vrg * vrg
    det = vrr * irr + vrg * irg + vrb * irb
    c0, c1, c2 = cov[..., 0], cov[..., 1], cov[..., 2]
    a = np.stack([(irr * c0 + irg * c1 + irb * c2) / det,
                  (irg * c0 + igg * c1 + igb * c2) / det,
                  (irb * c0 + igb * c1 + ibb * c2) / det], -1)
    b = mp - (a * mI).sum(-1)
    ma = cv2.resize(_box(a, rl), (W, H), interpolation=cv2.INTER_LINEAR)
    mb = cv2.resize(_box(b, rl), (W, H), interpolation=cv2.INTER_LINEAR)
    return (ma * guide_full).sum(-1) + mb


def blur_fusion_fields(I: np.ndarray, a: np.ndarray, s: int = 2):
    """Foreground / background colour fields for decontamination (Forte & Pitie 2021, 'Approximate
    Fast Foreground Colour Estimation', ICIP, arXiv:2006.14970): two blur-fusion passes, r=90 then
    r=6 (full-res pixels). Own code from the published equations. The fields are smooth, so they are
    computed at 1/s resolution; the caller applies the final per-pixel step at full resolution."""
    h, w = I.shape[0] // s, I.shape[1] // s
    Is = cv2.resize(I, (w, h), interpolation=cv2.INTER_AREA)
    As = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
    a3 = As[..., None]

    def blurred(F, B, r):
        ba = cv2.blur(As, (r, r))[..., None]
        bF = cv2.blur(F * a3, (r, r)) / (ba + 1e-5)
        bB = cv2.blur(B * (1 - a3), (r, r)) / ((1 - ba) + 1e-5)
        return bF, bB

    bF, bB = blurred(Is, Is, max(3, 90 // s))
    F1 = np.clip(bF + a3 * (Is - a3 * bF - (1 - a3) * bB), 0, 1)
    bF, bB = blurred(F1, bB, max(3, 6 // s))
    return bF, bB


class Refiner:
    def __init__(self, W, H, guided=True, decontam=True, r=8, eps=1e-3, s=2, lo=0.03, hi=0.97, band=3):
        self.guided, self.decontam, self.r, self.eps, self.s, self.lo, self.hi = guided, decontam, r, eps, s, lo, hi
        self.W, self.H = W, H
        self.blank = np.zeros((H, W, 4), np.uint8)
        self.band = band
        self.kband = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1)) if band else None

    def __call__(self, rgb: np.ndarray, a_low: np.ndarray | None) -> np.ndarray:
        if a_low is None:
            return self.blank
        I = rgb.astype(np.float32) / 255.0
        coarse = cv2.resize(a_low, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        if self.guided:
            a = fast_guided_upsample(I, a_low, self.r, self.eps, self.s)
            if self.kband is not None:
                # the guide may only move the edge near the model's own 50% contour; away from it
                # (soft, unsure plateaus over a dark shirt / dark rail gaps) it would invent blocks
                m = (coarse > 0.5).astype(np.uint8)
                band = (cv2.dilate(m, self.kband) - cv2.erode(m, self.kband)).astype(np.float32)
                w = cv2.blur(band, (self.band + 1, self.band + 1))
                a = coarse + w * (a - coarse)
        else:
            a = coarse
        # gentle levels: drop the faint haze the model leaves on the background and the pin-holes
        # inside the body, keep the soft ramp in between
        a = np.clip((a - self.lo) / (self.hi - self.lo), 0.0, 1.0).astype(np.float32)
        out = np.empty((self.H, self.W, 4), np.uint8)
        out[..., :3] = rgb
        if self.decontam:
            soft = (a > 0.002) & (a < 0.998)
            ys, xs = np.nonzero(soft)
            if len(ys):
                pad = 100  # pass-1 blur radius + margin
                y0, y1 = max(0, ys.min() - pad), min(self.H, ys.max() + pad + 1)
                x0, x1 = max(0, xs.min() - pad), min(self.W, xs.max() + pad + 1)
                bF, bB = blur_fusion_fields(I[y0:y1, x0:x1], a[y0:y1, x0:x1])
                size = (x1 - x0, y1 - y0)
                bF = cv2.resize(bF, size, interpolation=cv2.INTER_LINEAR)
                bB = cv2.resize(bB, size, interpolation=cv2.INTER_LINEAR)
                yy, xx = ys - y0, xs - x0
                av = a[ys, xs][:, None]
                f = bF[yy, xx]
                iv = I[ys, xs]
                F = f + av * (iv - av * f - (1 - av) * bB[yy, xx])
                # no overshoot: the estimate stays between the observed pixel and the local foreground
                # colour (dark shirt over a bright rail otherwise turns teal)
                F = np.clip(F, np.minimum(iv, f), np.maximum(iv, f))
                out[ys, xs, :3] = np.clip(F * 255.0 + 0.5, 0, 255).astype(np.uint8)
        out[..., 3] = np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return out


# ---------------------------------------------------------------- temporal
def median3(a, b, c):
    return np.maximum(np.minimum(a, b), np.minimum(np.maximum(a, b), c))


class DeadbandEMA:
    """Damps small frame-to-frame alpha changes (edge shimmer); a change bigger than `tau` passes
    straight through, so a moving hand does not leave a ghost."""

    def __init__(self, kmin=0.4, tau=0.2):
        self.kmin, self.tau, self.prev = kmin, tau, None

    def reset(self):
        self.prev = None

    def __call__(self, a):
        if self.prev is not None:
            d = a - self.prev
            a = self.prev + np.clip(np.abs(d) / self.tau, self.kmin, 1.0) * d
        self.prev = a
        return a


# ---------------------------------------------------------------- ranges / cache
def parse_ranges(s: str | None):
    if not s:
        return None
    out = []
    for part in s.split(","):
        a, b = part.split("-")
        out.append((float(a), float(b)))
    return merge(out)


def merge(rs):
    out = []
    for a, b in sorted(rs):
        if out and a <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def covered(have, want):
    if have is None:
        return True  # the whole clip was done
    if want is None:
        return False
    return all(any(ha <= a + 1e-6 and b <= hb + 1e-6 for ha, hb in have) for a, b in want)


def signature(src, args, size):
    st = os.stat(src)
    return dict(source=os.path.realpath(src), size=st.st_size, mtime=int(st.st_mtime), ss=args.ss, t=args.t,
                model=args.model, infer=list(size), refine=not args.no_refine, decontam=not args.no_decontam, gf=[args.gf_r, args.gf_eps, args.gf_band],
                temporal=args.temporal, stride=args.stride, version=VERSION)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--model", default="birefnet-portrait", choices=list(MODELS))
    ap.add_argument("--backend", default="auto", choices=["auto", "torch", "ort"], help="auto = torch on Apple MPS if present, else ort")
    ap.add_argument("--provider", default="auto", help="ort only: auto(=cpu) | cpu | coreml | coreml-gpu | coreml-ane")
    ap.add_argument("--infer-size", default="1024x1024", help="torch only: model input WxH, multiples of 32 (ort is fixed 1024x1024)")
    ap.add_argument("--threads", type=int, default=0, help="ort intra-op threads (0 = default)")
    ap.add_argument("--ss", type=float, default=0.0, help="start (s) in SRC; the output starts here")
    ap.add_argument("--t", type=float, default=0.0, help="duration (s); 0 = to the end")
    ap.add_argument("--ranges", help="only matte these SRC seconds, e.g. 17.0-18.6,40-41.5 (the rest is transparent)")
    ap.add_argument("--pad", type=float, default=0.25, help="seconds added around each range")
    ap.add_argument("--stride", type=int, default=1, help="run the model on every Nth frame, interpolate between (speed)")
    ap.add_argument("--temporal", default="median3+ema", choices=["median3+ema", "median3", "ema", "none"])
    ap.add_argument("--no-refine", action="store_true", help="plain bilinear upscale instead of the guided filter")
    ap.add_argument("--no-decontam", action="store_true", help="keep the raw source colour on edge pixels")
    ap.add_argument("--gf-r", type=int, default=8, help="guided filter radius at full res (px)")
    ap.add_argument("--gf-eps", type=float, default=1e-3)
    ap.add_argument("--gf-band", type=int, default=3, help="px around the model's 50%% contour the guided filter may move (0 = anywhere)")
    ap.add_argument("--cut-thresh", type=float, default=1.5, help="mean abs luma diff (0-255, 64x64 thumbs) that counts as a cut; jump cuts in one talking-head take measure 2-4, normal motion 0.2-0.5")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--save-raw", help="also write the raw model alpha (no temporal/refine) as a grey mp4, for comparisons")
    ap.add_argument("--keep-raw", help="keep the pass-1 model alpha in this dir (raw.u8 + meta.json) to re-run pass 2 later")
    ap.add_argument("--from-raw", help="skip the model: reuse a --keep-raw dir and only redo pass 2 (temporal/refine/encode)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    src = args.src
    info = probe(src)
    fps = info["fps"]
    W, H = info["w"], info["h"]
    req = parse_ranges(args.ranges)
    ranges = merge([(max(0.0, a - args.pad), b + args.pad) for a, b in req]) if req else None
    size = tuple(int(v) for v in args.infer_size.lower().split("x"))
    sig = signature(src, args, size)
    side = Path(args.out).with_suffix(".json")
    if not args.force and not args.from_raw and Path(args.out).exists() and side.exists():
        try:
            old = json.loads(side.read_text())
            have = [tuple(r) for r in old["ranges"]] if old["ranges"] is not None else None
            if old.get("sig") == sig and covered(have, ranges):
                log(f"cached: {args.out} already covers {ranges or 'the whole clip'}")
                return
            if old.get("sig") == sig and ranges is not None and have is not None:
                ranges = merge(have + ranges)  # recompute the union once
        except Exception:
            pass

    T0 = time.time()
    t_inf, n_inf, load_s, device = 0.0, 0, 0.0, "from-raw"
    if args.from_raw:
        rd = Path(args.from_raw)
        meta = json.loads((rd / "meta.json").read_text())
        n, sw, sh, nmax = meta["n"], meta["sw"], meta["sh"], meta["nmax"]
        raw = np.memmap(rd / "raw.u8", np.uint8, "r", shape=(nmax, sh, sw))
        wanted = np.array(meta["wanted"] + [False] * (nmax - n), bool)
        diffs = np.array(meta["diffs"] + [0.0] * (nmax - n), np.float32)
        cut_before = diffs > args.cut_thresh
        ranges = [tuple(r) for r in meta["ranges"]] if meta["ranges"] is not None else None
        n_inf, t_inf, load_s, device = meta["inferred"], meta["infer_s"], meta["load_s"], meta["device"] + " (from-raw)"
        mm_path = None
        log(f"pass 1 skipped: {n} frames from {rd}")
    else:
        matter = Matter(args.model, args.backend, args.provider, size, args.threads)
        load_s, device = matter.load_s, matter.device_name
        sw, sh = matter.size

        def want(i):
            if ranges is None:
                return True
            ts = args.ss + i / fps
            return any(a <= ts < b for a, b in ranges)

        # ---- pass 1: cuts + model alpha (uint8 at model size, memmapped so a whole reel fits) ----
        nmax = int(round((args.t or (info["duration"] - args.ss)) * fps)) + 2
        work = CACHE / "work"
        work.mkdir(parents=True, exist_ok=True)
        mm_path = work / (hashlib.md5(f"{args.out}{time.time()}".encode()).hexdigest() + ".u8")
        raw = np.memmap(mm_path, np.uint8, "w+", shape=(nmax, sh, sw))
        have = np.zeros(nmax, bool)
        diffs = np.zeros(nmax, np.float32)
        cut_before = np.zeros(nmax, bool)
        wanted = np.zeros(nmax, bool)
        thumbs_prev = None
        small_frames: dict[int, np.ndarray] = {}
        n = 0

        def infer(k, img):
            nonlocal t_inf, n_inf
            t1 = time.time()
            raw[k] = (matter(img) * 255 + 0.5).astype(np.uint8)
            t_inf += time.time() - t1
            n_inf += 1
            have[k] = True

        for i, rgb in enumerate(frames(src, info, args.ss, args.t, (sw, sh))):
            if i >= nmax:
                break
            n = i + 1
            th = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
            if thumbs_prev is not None:
                diffs[i] = float(np.mean(np.abs(th - thumbs_prev)))
                cut_before[i] = diffs[i] > args.cut_thresh
            thumbs_prev = th
            wanted[i] = want(i)
            if not wanted[i]:
                if i > 0 and wanted[i - 1] and not have[i - 1] and i - 1 in small_frames:  # close the run with a key frame
                    infer(i - 1, small_frames[i - 1])
                continue
            key = args.stride <= 1 or i % args.stride == 0 or cut_before[i] or (i > 0 and not wanted[i - 1])
            if not key:
                small_frames[i] = rgb  # may be needed if a cut shows up right after it
                continue
            if cut_before[i] and i - 1 in small_frames and not have[i - 1]:  # frame i-1 closes the previous shot
                infer(i - 1, small_frames[i - 1])
            infer(i, rgb)
            small_frames = {k: v for k, v in small_frames.items() if k > i - 2}
            if n_inf % 10 == 0:
                log(f"  pass 1: frame {i + 1}  inferred {n_inf}  {t_inf / n_inf:.2f} s/frame")
        for i in sorted(small_frames):  # the last wanted frame of each run must be a key frame
            if wanted[i] and not have[i] and (i + 1 >= n or not wanted[i + 1] or cut_before[i + 1]):
                infer(i, small_frames[i])
        small_frames.clear()
        if args.stride > 1:  # interpolate skipped frames inside a shot
            idx = np.nonzero(have[:n])[0]
            for i in range(n):
                if wanted[i] and not have[i]:
                    lo = idx[idx < i].max(initial=-1)
                    hi = idx[idx > i].min(initial=n)
                    if lo >= 0 and hi < n and not cut_before[lo + 1:hi + 1].any():
                        w = (i - lo) / (hi - lo)
                        raw[i] = (raw[lo] * (1 - w) + raw[hi] * w + 0.5).astype(np.uint8)
                    else:
                        raw[i] = raw[lo if lo >= 0 and not cut_before[lo + 1:i + 1].any() else hi]
        raw.flush()
        if args.keep_raw:
            rd = Path(args.keep_raw)
            rd.mkdir(parents=True, exist_ok=True)
            raw = None  # drop the memmap before moving or deleting its file
            os.replace(mm_path, rd / "raw.u8")
            mm_path = None
            raw = np.memmap(rd / "raw.u8", np.uint8, "r", shape=(nmax, sh, sw))
            (rd / "meta.json").write_text(json.dumps(dict(
                src=os.path.abspath(src), ss=args.ss, t=args.t, n=n, nmax=nmax, sw=sw, sh=sh, ranges=ranges,
                wanted=wanted[:n].tolist(), diffs=[round(float(x), 3) for x in diffs[:n]], inferred=n_inf,
                infer_s=round(t_inf, 2), load_s=round(load_s, 1), device=device, model=args.model, stride=args.stride)))
    t_pass1 = time.time() - T0
    cuts = [round(float(args.ss + i / fps), 3) for i in np.nonzero(cut_before[:n])[0]]
    log(f"pass 1 done: {n} frames, {int(wanted[:n].sum())} wanted, {n_inf} inferred, cuts at {cuts}")

    # ---- pass 2: temporal filter, guided upsample, decontaminate, encode ----
    refiner = Refiner(W, H, guided=not args.no_refine, decontam=not args.no_decontam, r=args.gf_r, eps=args.gf_eps, band=args.gf_band)
    ema = DeadbandEMA()
    tmp_out = args.out + ".part"
    enc = encoder(tmp_out, info, args.crf)
    raw_enc = None
    if args.save_raw:
        raw_enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                                    "-r", info["fps_str"], "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                                    "-color_range", "pc", args.save_raw], stdin=subprocess.PIPE)
    t_ref = t_enc = 0.0
    T1 = time.time()
    fq: queue.Queue = queue.Queue(maxsize=4)

    def writer():
        nonlocal t_enc
        while True:
            b = fq.get()
            if b is None:
                return
            t = time.time()
            enc.stdin.write(b)
            t_enc += time.time() - t

    wt = threading.Thread(target=writer, daemon=True)
    wt.start()

    def same_shot(i, j):
        if j < 0 or j >= n or not wanted[j]:
            return False
        a, b = min(i, j), max(i, j)
        return not cut_before[a + 1:b + 1].any()

    count = 0
    for i, rgb in enumerate(frames(src, info, args.ss, args.t, (W, H))):
        if i >= n:
            break
        count += 1
        t = time.time()
        a_low = None
        if wanted[i]:
            cur = raw[i].astype(np.float32) / 255.0
            a_low = cur
            if "median3" in args.temporal:
                p = raw[i - 1].astype(np.float32) / 255.0 if same_shot(i, i - 1) else cur
                q_ = raw[i + 1].astype(np.float32) / 255.0 if same_shot(i, i + 1) else cur
                a_low = median3(p, cur, q_)
            if "ema" in args.temporal:
                if not same_shot(i, i - 1):
                    ema.reset()
                a_low = ema(a_low)
        else:
            ema.reset()
        rgba = refiner(rgb, a_low)
        t_ref += time.time() - t
        fq.put(rgba.tobytes())
        if raw_enc:
            g = cv2.resize(raw[i], (W, H), interpolation=cv2.INTER_LINEAR) if wanted[i] else np.zeros((H, W), np.uint8)
            raw_enc.stdin.write(g.tobytes())
        if count % 60 == 0:
            log(f"  pass 2: frame {count}/{n}")
    fq.put(None)
    wt.join()
    enc.stdin.close()
    enc.wait()
    if raw_enc:
        raw_enc.stdin.close()
        raw_enc.wait()
    raw = None  # drop the memmap before moving or deleting its file
    if mm_path is not None:
        mm_path.unlink(missing_ok=True)
    if enc.returncode != 0:
        raise SystemExit("ffmpeg encode failed")
    os.replace(tmp_out, args.out)
    wall = time.time() - T0
    report = dict(out=args.out, frames=count, wanted=int(wanted[:n].sum()), inferred=n_inf, fps_src=info["fps_str"], size=f"{W}x{H}",
                  model=args.model, device=device, infer_size=f"{sw}x{sh}", stride=args.stride, load_s=round(load_s, 1),
                  infer_s_per_frame=round(t_inf / max(1, n_inf), 3), infer_fps=round(n_inf / max(1e-6, t_inf), 2),
                  pass1_s=round(t_pass1, 1), pass2_s=round(time.time() - T1, 1),
                  refine_s_per_frame=round(t_ref / max(1, count), 3), wall_s=round(wall, 1), overall_fps=round(count / wall, 2), cuts=cuts)
    side.write_text(json.dumps(dict(sig=sig, ranges=ranges, report=report), indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
