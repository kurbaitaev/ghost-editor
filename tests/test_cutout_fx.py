#!/usr/bin/env python3
"""Pipeline test for scripts/cutout_fx.py with a fake model (no GPU, no weights): alpha cache, every effect, thumb,
still, webm, plus the frame grid build.mjs relies on.

    ~/.venvs/ghost-matte/bin/python tests/test_cutout_fx.py      # KEEP=1 keeps the outputs (TEST_DIR=... to choose where)

Frame grid: a source whose every frame carries its own number (luma) is cut with the window math build.mjs uses
(--ss = an exact source-frame time with 6 decimals, --t = the window minus half a frame). The window must start on
exactly that frame and hold exactly the beat's frame count at every phase of the 1/30 grid, and --release must hand
back the untouched source frame on the last frame.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="cutoutfx-test-", dir=os.environ.get("TEST_DIR")))
os.environ["CUTOUT_FX_CACHE"] = str(tmp / "cache")
sys.path.insert(0, str(REPO / "scripts"))
import numpy as np  # noqa: E402

import cutout_fx as C  # noqa: E402
from x264 import THREADS as X264_THREADS  # noqa: E402


class FakeNet:
    """A head-and-shoulders silhouette that sways, at the model size."""

    def __init__(self, name):
        self.name, self.load_s, self.big, self.peak_gb, self.k = name, 0.0, False, 0.0, 0
        self.dev = type("D", (), {"type": "cpu"})()

    def __call__(self, imgs):
        out = []
        for im in imgs:
            h, w = im.shape[:2]
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            cx = w / 2 + 0.03 * w * np.sin(self.k / 5)
            head = ((xx - cx) / (0.17 * w)) ** 2 + ((yy - 0.33 * h) / (0.12 * h)) ** 2 < 1
            body = (yy > 0.45 * h) & (np.abs(xx - cx) < 0.42 * w)
            out.append((head | body).astype(np.float32))
            self.k += 1
        return np.stack(out)

    def sync(self):
        pass

    def predict(self, rgb, size):
        return C.cv2.resize(self([C.cv2.resize(rgb, size)])[0], (rgb.shape[1], rgb.shape[0]))


def count_frames(p):
    return int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                               "stream=nb_read_frames", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip())


def frame_numbers(p, w, h):
    """Mean Y (video range, read straight from the yuv420p planes) of each frame of a numbered clip -> its frame
    number (Y = 40 + 3 n)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"], capture_output=True).stdout
    fs = w * h * 3 // 2
    return [round((np.frombuffer(raw[i * fs:i * fs + w * h], np.uint8).astype(np.float32).mean() - 40) / 3)
            for i in range(len(raw) // fs)]


C.Net = FakeNet
src = tmp / "src.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=540x960:rate=30:duration=2.5", "-f", "lavfi", "-i",
                "sine=f=440:d=2.5", "-shortest", "-c:v", "libx264", "-threads", X264_THREADS, "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
bgimg = tmp / "bg.png"
C.cv2.imwrite(str(bgimg), (np.random.default_rng(0).random((400, 300, 3)) * 255).astype(np.uint8))

d = C.ensure_alpha(str(src), 0.5, 1.5, "lite@512")
meta = json.loads((d / "meta.json").read_text())
assert meta["n"] == 45, meta["n"]
assert C.ensure_alpha(str(src), 0.5, 1.5, "lite@512") == d  # cached
c = C.Clip(str(src), 0.5, 1.5, "lite@512", 1.0)
assert c.n == 45 and c.w == 540 and c.h == 960, (c.n, c.w, c.h)
a = c.a(10)
assert a.max() > 0.9 and a.min() < 0.1

runs = {
    "bg-swap": ["--bg", str(bgimg), "--bg2", "#112233,#445566", "--switch", "1.2"],
    "bg-blur": [], "selective": ["--look", "film"], "spotlight": [], "sticker": ["--freeze", "0.7", "--hold", "0.6"],
    "neon": [], "clones": ["--offsets", "0,0.2,0.4"], "pop": ["--frame", "card"],
    "sandwich": ["--behind", "BEHIND@0.6-1.4", "--front", "ФРОНТ@0.8", "--through", "THRU@1.3"],
}
for fx, extra in runs.items():
    out = tmp / f"{fx}.mp4"
    C.main([fx, str(src), "--ss", "0.5", "--t", "1.5", "--model", "lite@512", "-o", str(out), "--size", "270x480"] + extra)
    n = count_frames(out)
    want = 45 - (12 if fx == "clones" else 0)
    assert n == want, (fx, n, want)
    au = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(out)],
                        capture_output=True, text=True).stdout.strip()
    assert au == "aac", (fx, au)
    print(f"ok {fx}: {n} frames + audio")
# a second call with the same inputs is a no-op (build.mjs calls it on every build)
side = json.loads((tmp / "bg-blur.mp4.json").read_text())
assert side["frames"] == 45, side
mt = (tmp / "bg-blur.mp4").stat().st_mtime
C.main(["bg-blur", str(src), "--ss", "0.5", "--t", "1.5", "--model", "lite@512", "-o", str(tmp / "bg-blur.mp4"), "--size", "270x480"])
assert (tmp / "bg-blur.mp4").stat().st_mtime == mt, "the cached render was redone"
# ramp 0 = full effect from the first frame (plate mode)
C.main(["bg-blur", str(src), "--ss", "0.5", "--t", "1.5", "--model", "lite@512", "-o", str(tmp / "steady.mp4"), "--ramp", "0", "--at", "0.5"])
C.main(["thumb", str(src), "--ss", "0.5", "--t", "1.5", "--model", "lite@512", "-o", str(tmp / "cover"), "--headline", "ОДИН|*TWO*"])
assert (tmp / "cover-9x16.jpg").exists() and (tmp / "cover-16x9.jpg").exists()
im = C.cv2.imread(str(tmp / "cover-16x9.jpg"))
assert im.shape[:2] == (720, 1280), im.shape
C.main(["webm", str(src), "--ss", "0.5", "--t", "1.5", "--model", "lite@512", "-o", str(tmp / "m.webm")])
assert (tmp / "m.webm").exists()
for r in ("checker", "white", "color", "highlight", "product"):
    C.main(["still", str(bgimg), "--model", "lite@512", "--result", r, "-o", str(tmp / f"still-{r}"), "--zoom", "0.1,0.1,0.5,0.4"])
    assert (tmp / f"still-{r}.jpg").exists() and (tmp / f"still-{r}-cutout.png").exists()
print("ok thumb, webm, stills")

# ---- the frame grid build.mjs relies on ----
num = tmp / "num.mp4"  # frame n has luma 40 + 3 n (flat grey), 15360 timebase like prep.sh output
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "nullsrc=s=96x160:r=30:d=2.6,format=yuv420p,geq=lum='40+3*N':cb=128:cr=128",
                "-c:v", "libx264", "-threads", X264_THREADS, "-crf", "0", "-g", "250", "-pix_fmt", "yuv420p", "-video_track_timescale", "15360", str(num)], check=True)
for f0 in range(3, 9):  # every phase of the 1/30 grid (6-decimal ss rounds up on some, down on others)
    for nf in (17, 18):
        ss, t = f0 / 30, (nf - 0.5) / 30
        out = tmp / f"grid-{f0}-{nf}.mp4"
        C.main(["bg-blur", str(num), "--ss", f"{ss:.6f}", "--t", f"{t:.6f}", "--at", f"{ss:.6f}", "--no-audio", "--model", "lite@512",
                "-o", str(out), "--release", "0.2"])
        got = frame_numbers(out, 96, 160)
        # a flat grey frame has no background to blur, so every output frame is the source frame it was cut from
        assert got == list(range(f0, f0 + nf)), (f0, nf, got)
        assert json.loads(Path(str(out) + ".json").read_text())["frames"] == nf
print("ok frame grid: windows start on the exact source frame and hold the exact frame count")
# --release: the last frame is the source frame itself, the effect is unchanged before the release
full = tmp / "rel-0.mp4"
rel = tmp / "rel-1.mp4"
for o, r in ((full, "0"), (rel, "0.3")):
    C.main(["spotlight", str(src), "--ss", "0.5", "--t", "1.5", "--at", "0.5", "--ramp", "0.1", "--no-audio", "--model", "lite@512",
            "-o", str(o), "--release", r, "--crf", "0"])


def gray_frames(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 960, 540).astype(np.float32)


gf, gr = gray_frames(full), gray_frames(rel)
srcg = np.stack([C.cv2.cvtColor((c.f(i) * 255 + 0.5).astype(np.uint8), C.cv2.COLOR_RGB2GRAY) for i in range(c.n)]).astype(np.float32)
assert len(gf) == len(gr) == 45
assert np.abs(gr[30] - gf[30]).mean() < 0.5, "release changed frames before the release window"
assert np.abs(gr[-1] - srcg[-1]).mean() < 1.5, np.abs(gr[-1] - srcg[-1]).mean()
assert np.abs(gf[-1] - srcg[-1]).mean() > 5, "spotlight should differ from the source without --release"
print("ok release: last frame = source frame")
print("ALL OK", tmp)
if not os.environ.get("KEEP"):
    shutil.rmtree(tmp, ignore_errors=True)
