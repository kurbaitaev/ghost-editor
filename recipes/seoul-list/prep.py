#!/usr/bin/env python3
"""Seoul list: prepare a reel project's inputs (everything build.mjs reads besides list.json).

    prep.py voice  IN  $P/assets/voice.wav [--keep 0-21.23,24.57-26.43] [--gap 0.2]
    prep.py words  $P/assets/voice.wav $P/build/words.json [--lang ru] [--model turbo]
    prep.py still  CLIP T OUT.jpg                    one proxy frame (photo cards, outro cards)
    prep.py cutout CLIP T OUT.png [--model general]  BiRefNet cut-out, cropped to the object (window items)
    prep.py avatar CLIP T OUT.jpg [--size 360]       square face crop for the comment card (YuNet face detector)

voice: the user's read (any audio or video file) -> 48 kHz mono 24-bit wav at -16 LUFS (two-pass loudnorm, the
level every SFX role in the build is set against). --keep cuts pieces out of it first: each edge is snapped to the
30 fps frame grid (so picture and voice can never drift), 8 ms fades, joined with --gap seconds of silence.
words: whisper (PATH binary) with word timestamps -> the json build.mjs and list.json word refs read. Re-run it
whenever the voice file changes: every beat is keyed to these times.
still / cutout / avatar take CLIP as a proxy path (or a name in ./clips) and T in clip seconds. The frame is
taken at floor(T x fps), the same frame the reel shows at that clip time.
cutout runs scripts/cutout_fx.py still in the matte venv (~/.venvs/ghost-matte, or $MATTE_VENV) and crops the RGBA
result to its alpha bounding box plus a margin; look at the PNG before using it (busy scenes cut messily).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts", "lib"))
from plat import venv_python  # noqa: E402
FPS = 30
SR = 48000


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1200:]}")
    return r


def dur(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout)


def clip_path(c):
    if os.path.exists(c):
        return c
    for cand in (os.path.join("clips", c), os.path.join("clips", c + ".mp4")):
        if os.path.exists(cand):
            return cand
    sys.exit(f"clip not found: {c}")


# ---------------------------------------------------------------- voice
def cmd_voice(a):
    import numpy as np
    raw = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", a.src, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                       capture_output=True, check=True).stdout, np.float32).copy()
    total = len(raw) / SR
    pieces = []
    if a.keep:
        for part in a.keep.split(","):
            s, e = (float(v) for v in part.split("-"))
            f0, f1 = round(s * FPS), round(min(e, total) * FPS)
            if f1 <= f0:
                sys.exit(f"bad piece {part}")
            pieces.append((f0, f1))
    else:
        pieces = [(0, int(total * FPS))]
    fade = int(0.008 * SR)
    gap = np.zeros(round(a.gap * FPS) * SR // FPS, np.float32)
    out, report = [], []
    for i, (f0, f1) in enumerate(pieces):
        x = raw[f0 * SR // FPS: f1 * SR // FPS].copy()
        if len(pieces) > 1 or a.keep:
            ramp = np.linspace(0, 1, fade, dtype=np.float32)
            x[:fade] *= ramp
            x[-fade:] *= ramp[::-1]
        if i:
            out.append(gap)
        report.append(f"{f0 / FPS:.3f}-{f1 / FPS:.3f} ({f1 - f0} frames)")
        out.append(x)
    y = np.concatenate(out)
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "cut.wav")
        import wave
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
        st = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", tmp, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                 "-f", "null", "-"]).stderr
        m = json.loads(st[st.rindex("{"):st.rindex("}") + 1])
        af = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
              f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample={SR}")
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        sh(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", af, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s24le", a.out])
    lo = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", a.out, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", lo)[-1]
    print(f"pieces: {', '.join(report)}; gap {a.gap}s")
    print(f"-> {a.out}: {dur(a.out):.3f}s, {I} LUFS (input {m['input_i']} LUFS). Now: prep.py words {a.out} build/words.json")


# ---------------------------------------------------------------- words
def cmd_words(a):
    w = os.environ.get("WHISPER") or shutil.which("whisper")
    if not w:
        sys.exit("whisper not on PATH (pip install openai-whisper, or set WHISPER=/path)")
    with tempfile.TemporaryDirectory() as td:
        sh([w, a.voice, "--model", a.model, "--language", a.lang, "--word_timestamps", "True", "--output_format", "json",
            "--output_dir", td, "--fp16", "False"])
        src = os.path.join(td, os.path.splitext(os.path.basename(a.voice))[0] + ".json")
        d = json.load(open(src, encoding="utf-8"))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(d, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    words = [x for s in d["segments"] for x in s.get("words", [])]
    print(f"-> {a.out}: {len(words)} words, {words[0]['start']:.2f}-{words[-1]['end']:.2f}s")
    for s in d["segments"]:
        print(f"  [{s['start']:6.2f} {s['end']:6.2f}] {s['text'].strip()}")


# ---------------------------------------------------------------- frames
def frame(clip, t, out):
    f = int(t * FPS + 1e-6)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{f / FPS:.6f}", "-i", clip_path(clip), "-frames:v", "1", "-update", "1",
        "-q:v", "2", out])
    return out


def cmd_still(a):
    frame(a.clip, a.t, a.out)
    print(f"-> {a.out}")


def cmd_cutout(a):
    import numpy as np
    from PIL import Image
    py = venv_python(os.environ.get("MATTE_VENV", "~/.venvs/ghost-matte"))
    if not os.path.exists(py):
        sys.exit("matte venv missing: bash $S/scripts/setup_matte.sh")
    with tempfile.TemporaryDirectory() as td:
        src = frame(a.clip, a.t, os.path.join(td, "in.png"))
        sh([py, os.path.join(SKILL, "scripts", "cutout_fx.py"), "still", src, "--model", a.model, "--result", "white",
            "-o", os.path.join(td, "c")])
        im = Image.open(os.path.join(td, "c-cutout.png")).convert("RGBA")
        if a.sheet:
            shutil.copy(os.path.join(td, "c.jpg"), a.sheet)
    al = np.asarray(im)[:, :, 3]
    ys, xs = np.where(al > 24)
    if not len(xs):
        sys.exit("empty cut-out: nothing salient in that frame")
    m = int(a.margin * max(np.ptp(xs), np.ptp(ys)))
    box = (max(0, xs.min() - m), max(0, ys.min() - m), min(im.width, xs.max() + m + 1), min(im.height, ys.max() + m + 1))
    im.crop(box).save(a.out)
    print(f"-> {a.out}: {box[2] - box[0]}x{box[3] - box[1]} (box {box} of {im.width}x{im.height}); LOOK at it before use")


def cmd_avatar(a):
    import cv2
    tmp = frame(a.clip, a.t, os.path.join(tempfile.mkdtemp(), "f.png"))
    img = cv2.imread(tmp)
    H, W = img.shape[:2]
    model = os.path.join(SKILL, "library", "models", "face_detection_yunet_2023mar.onnx")
    if not os.path.exists(model):
        sys.exit(f"face model missing: run python3 {SKILL}/scripts/face_track.py once (it downloads it)")
    q = 2
    det = cv2.FaceDetectorYN.create(model, "", (W // q, H // q), 0.6)
    _, faces = det.detect(cv2.resize(img, (W // q, H // q)))
    if faces is None or not len(faces):
        sys.exit("no face in that frame; pick another T")
    x, y, w, h = (v * q for v in max(faces, key=lambda f: f[2] * f[3])[:4])
    cx, cy, s = x + w / 2, y + h * 0.48, max(w, h) * a.pad
    x0, y0 = int(max(0, cx - s / 2)), int(max(0, cy - s / 2))
    s = int(min(s, W - x0, H - y0))
    crop = cv2.resize(img[y0:y0 + s, x0:x0 + s], (a.size, a.size), interpolation=cv2.INTER_AREA)
    cv2.imwrite(a.out, crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"-> {a.out}: face {int(w)}x{int(h)} at ({int(x)},{int(y)}); crop {s}px -> {a.size}px. Confirm it is the right person.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("voice"); p.add_argument("src"); p.add_argument("out")
    p.add_argument("--keep", help="pieces to keep, source seconds: a-b,a-b (frame-snapped)")
    p.add_argument("--gap", type=float, default=0.2, help="silence between kept pieces (s)")
    p = sub.add_parser("words"); p.add_argument("voice"); p.add_argument("out")
    p.add_argument("--lang", default="ru"); p.add_argument("--model", default="turbo")
    p = sub.add_parser("still"); p.add_argument("clip"); p.add_argument("t", type=float); p.add_argument("out")
    p = sub.add_parser("cutout"); p.add_argument("clip"); p.add_argument("t", type=float); p.add_argument("out")
    p.add_argument("--model", default="general"); p.add_argument("--margin", type=float, default=0.03)
    p.add_argument("--sheet", help="also save cutout_fx's input|alpha|result sheet here")
    p = sub.add_parser("avatar"); p.add_argument("clip"); p.add_argument("t", type=float); p.add_argument("out")
    p.add_argument("--size", type=int, default=360); p.add_argument("--pad", type=float, default=1.9)
    a = ap.parse_args()
    {"voice": cmd_voice, "words": cmd_words, "still": cmd_still, "cutout": cmd_cutout, "avatar": cmd_avatar}[a.cmd](a)


if __name__ == "__main__":
    main()
