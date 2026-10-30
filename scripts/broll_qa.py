#!/usr/bin/env python3
"""B-roll and motion QA on a finished render: the 2026-10-13 audit's faults as pass/fail checks (references/broll.md).

    broll_qa.py <render.mp4> [--project DIR] [--profile talking-head|broll-led|graphics] [--words build/words.cut.json]
                [--allow-hold 12.0-13.5,...] [--out DIR/build/broll-qa.json] [--no-ocr] [--no-match]
    (render_report.py runs it too; exit code 1 when a check fails)

With --project (a HyperFrames project: index.html) the QA reads the composition: which <video> is the speaker plate,
which <video>/<img> are inserts. It matches render frames against every layer (ORB features + a similarity transform),
so it knows which layer is on screen, how much of the frame it fills (full-screen vs framed), and where every face of
every layer lands: a card or blur on a face shows up as a face region that lost its source's detail. Without a project
it falls back to the audit's frame classifier (93 % on held-out frames).

Checks (profile talking-head unless noted; broll-led = Seoul list / POV montage; graphics = explainer / motion):
  broll_full     full-screen B-roll share of the runtime <= 25 %                              (talking-head)
  speaker        speaker's face on screen >= 65 %                                              (talking-head)
  inserts        <= 3 inserts per minute (shots back to back = one insert; framed inserts count) (talking-head;
                 profile tutorial = stan style: its screen-recording panels are the content, not inserts)
  grade          every insert vs the speaker plate: |white balance b*| <= 8, |median L*| <= 15, saturation x0.5-2.0;
                 the reel's median insert saturation x0.8-1.2 (grade_lib.py)
  graphics       full-screen graphic scenes: median length <= 2.5 s; scenes of 1 s or more have >= 50 % of their
                 frames moving (a 0.5 s word flash is a beat, not a slide)
  captions       spoken-word text on screen (OCR: macOS Vision via scripts/ocr_text.js), per caption event: >= 48 px and
                 >= 3:1 contrast between the letters and the pixels right around them (an outline or shadow counts)
  language       Latin words in a Cyrillic reel (decor text), the speaker's clothing excluded           (warning)
  faces          no card, panel or blur over a face, in the plate or in any insert
  stock          stock is a last resort and only inside a frame (polaroid, phone, card): a stock insert full screen for
                 0.4 s or more fails (talking-head styles). B-roll-led formats (Seoul list, POV montage) are full-screen
                 B-roll by design: there stock may fill the screen, and these checks guard the look instead:
  world          (broll-led) one coherent world: the inserts' brightness and white balance agree (sd L* <= 14, sd b* <= 5;
                 the reference Seoul reel 11.8 / 2.5, a mismatched stock reel 21.2 / 7.7)
  models         no posed stock models: a stranger's face >= 8 % of the frame width in a stock / AI / unknown-source insert
                 fails in broll-led formats (beach and office models), warns elsewhere. A face the detector finds in a shot
                 the vision check says has nobody in it is a false detection and doesn't count (a football's panels, a bust)
  pace           (broll-led) median shot 0.9-2.2 s (warning outside 1.1-1.8; the reference Seoul reel 1.30 s)
  resolution     every video insert's source is 1080p or better (short side)
  Provenance: the insert's insert_prep / proxy.sh sidecar (<clip>.json "kind"), else its path/name
  people         the B-roll people rules (people-rules.json) on every B-roll shot, stock image and backdrop; skipped when
                 no rules are set. Gemini on 6 frames of the window used (broll_vision.py, cached); an unchecked shot
                 fails too. --no-vision skips it (then it warns)
  match          every timed B-roll shot shows what the words under it say: "no" fails, "partly" warns (needs --words)
  components     --style + --project: no phone-UI scene, prop, frame, transition, hook or outro repeats from the style's
                 last 7 reels (scripts/components.py, recipes/<style>/catalog.json; a warning)
  as_shot        the speaker's face keeps its natural, as-shot colour: a plate written by house_look.py apply fails, and so does a
                 render whose face box differs from the plate's (CSS filter, overlay): |L*| > 5, |b*| > 4, |a*| > 4 or
                 saturation outside x0.85-1.18 (median over up to 16 full-frame speaker samples; a caption shade or a
                 vignette at the edges doesn't count)
  own_people     own footage shows only the speaker: a face that is not theirs (SFace < 0.40 vs the plate's faces and
                 library/me/face_ref.npz) in an own-footage insert fails (other people have ended up in cuts before)
  freeze         no frozen picture > 0.2 s over the speaker's face or inside a moving insert; no clip played past its
                 source's end; no frozen run inside an insert's source window (a padded cut). A clip that never moves at all
                 (a photo written out as a clip) is a still, not a stall: fine framed, as a blurred backdrop or full screen with
                 a slow push. It fails full screen (>= 0.5 s) when it shows a person, animal or vehicle caught mid-movement
                 (a frozen runner reads as a stuck video; Gemini, cached) and warns full screen >= 1 s without any push
  hdr            the render is SDR BT.709 (one HDR source switches a HyperFrames render to HDR)
  keyframes      plates have a keyframe at least every 1 s (inserts: warning); source fps = the reel's fps (warning)
Writes broll-qa.json (checks in render_report's format + a metrics row comparable to the audit's metrics.csv) and
broll-qa-timeline.png (S speaker / B full-screen B-roll / F framed insert / G graphics / P plate without a face).
"""
import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

import numpy as np
import cv2

try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except AttributeError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade_lib as G  # noqa: E402

MODELS = os.path.join(HERE, "..", "library", "models")
YUNET = ("face_detection_yunet_2023mar.onnx", "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx")
SFACE = ("face_recognition_sface_2021dec.onnx", "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx")
PROFILES = {
    "talking-head": {"broll_full_max": 25.0, "speaker_min": 65.0, "inserts_per_min_max": 3.0},    # fewer B-rolls, each on its line
    "tutorial": {"broll_full_max": 25.0, "speaker_min": 65.0, "inserts_per_min_max": None},     # stan: screen panels are the content
    "broll-led": {"broll_full_max": None, "speaker_min": None, "inserts_per_min_max": None},
    "graphics": {"broll_full_max": None, "speaker_min": None, "inserts_per_min_max": None},
}
GFX_MEDIAN_MAX, GFX_ANIM_MIN = 2.5, 50.0
CAP_PX_MIN, CAP_CONTRAST_MIN = 48, 3.0
CAP_RATIO = 0.93     # Vision line-box height / CSS font-size: 0.85-1.06 on renders with known sizes (54 px -> 50, 92 -> 98)
FREEZE_MAX = 0.2
KEYINT_MAX = 1.0
SPK_TH, MINW = 0.40, 0.05          # SFace cosine to the speaker; faces under 5 % of the frame width are UI avatars
COVER_MIN = 0.15                   # share of a face's 4x4 cells that lost their source (a box on the mouth = 3 cells)
DT = 0.2                           # labels / stats grid (5 fps)
DTM = 0.1                          # layer matching / face-cover grid (10 fps)
PLATE_RE = re.compile(r"(^|/)(talk|wide|tight|plate[^/]*|face|speaker|cut|cam)[^/]*\.(mp4|mov|m4v)$", re.I)
STICKER_RE = re.compile(r"(\.webm$|/memes?/|/emoji/|/stickers?/|/icons?/|/fonts?/|matte|grain|noise|texture)", re.I)
STILL_RE = re.compile(r"\.(jpe?g|png|webp)$", re.I)


def chk(cid, title, status, value=None, target=None, details=None, fix=None, auto=False, times=None):
    return {"id": cid, "title": title, "status": status, "value": value, "target": target, "details": details or [],
            "fix": fix, "fix_auto": auto, "times": times or []}


def model(name_url):
    name, url = name_url
    p = os.path.join(MODELS, name)
    if not os.path.exists(p):
        os.makedirs(MODELS, exist_ok=True)
        print(f"downloading {name} (opencv_zoo)...", file=sys.stderr)
        urllib.request.urlretrieve(url, p)
    return p


def decode(path, w, h, fps=None, gray=False, start=None, dur=None):
    """frames as uint8 arrays (BGR or gray), optionally resampled to fps"""
    vf = ([f"fps={fps}"] if fps else []) + [f"scale={w}:{h}:flags=area+{G.SCALE_FLAGS}"]
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{start:.3f}"] if start is not None else []) + ["-i", path] + \
          (["-t", f"{dur:.3f}"] if dur is not None else []) + ["-an", "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "gray" if gray else "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 8)
    ch = 1 if gray else 3
    sz = w * h * ch
    out = []
    while True:
        b = p.stdout.read(sz)
        if len(b) < sz:
            break
        out.append(np.frombuffer(b, np.uint8).reshape((h, w) if gray else (h, w, 3)))
    p.wait()
    return out


def runs(L, dt=DT):
    res, k0 = [], 0
    for k in range(1, len(L) + 1):
        if k == len(L) or L[k] != L[k0]:
            res.append((L[k0], k0 * dt, k * dt, k0, k))
            k0 = k
    return res


# ------------------------------------------------------------------ audit features (classify.py, extract2.py)
def nb_features(small):
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    q = (small >> 3).astype(np.int32)
    codes = (q[..., 0] << 10) | (q[..., 1] << 5) | q[..., 2]
    _, cnt = np.unique(codes, return_counts=True)
    f = {"uniq": int(len(cnt)), "top8": float(np.sort(cnt)[-8:].sum() / codes.size), "black": float((g < 20).mean())}
    m = g >= 28
    if m.sum() >= 500:
        sx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        sy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        gm = np.abs(sx) + np.abs(sy)
        c2 = codes[m]
        _, cn = np.unique(c2, return_counts=True)
        f.update(top8_nb=float(np.sort(cn)[-8:].sum() / c2.size), flat_nb=float((gm[m] < 4).mean()))
    else:
        f.update(top8_nb=1.0, flat_nb=1.0)
    return f


def is_graphic(f):
    if f["uniq"] < 220:
        return True
    if f["top8"] >= 0.75 and (f["black"] < 0.5 or f["top8_nb"] >= 0.75):
        return True
    return f["flat_nb"] >= 0.55 and f["top8_nb"] >= 0.60


# ------------------------------------------------------------------ composition
def attr(tag, name):
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return m.group(1) if m else None


TL_CALL = re.compile(r"""\.(set|to|from|fromTo)\(\s*["'](#[\w-]+)["']\s*,\s*(\{[^{}]*\})\s*(?:,\s*(\{[^{}]*\}))?\s*,\s*([\d.]+)\s*\)""")
ALPHA = re.compile(r"""["']?(?:autoAlpha|opacity)["']?\s*:\s*([\d.]+)""")
DUR = re.compile(r"""["']?duration["']?\s*:\s*([\d.]+)""")


def visibility(src, total):
    """id -> [(t0, t1)] when the element is shown, from the GSAP timeline (autoAlpha / opacity in tl.set / to / from /
    fromTo) and from data-start / data-duration. An element with neither is shown all the time (None)."""
    ev = {}
    for m in TL_CALL.finditer(src):
        fn, sel, a, b, t = m.group(1), m.group(2)[1:], m.group(3), m.group(4), float(m.group(5))
        end = b if fn == "fromTo" else a
        am = ALPHA.search(end or "")
        if fn == "from":
            am0 = ALPHA.search(a)
            if am0 and float(am0.group(1)) == 0:
                ev.setdefault(sel, []).append((t, True))
            continue
        if am:
            on = float(am.group(1)) > 0.01
            dm = DUR.search(end)
            ev.setdefault(sel, []).append((t + (float(dm.group(1)) if dm and not on else 0.0), on))
    win = {}
    for sel, es in ev.items():
        cur, out = None, []
        for t, on in sorted(es):
            if on and cur is None:
                cur = t
            elif not on and cur is not None:
                if t - cur > 0.05:
                    out.append((round(cur, 3), round(t, 3)))
                cur = None
        if cur is not None and total:
            out.append((round(cur, 3), round(total, 3)))
        win[sel] = out
    for tag in re.findall(r"<[a-zA-Z][^>]*\bdata-start=[^>]*>", src):
        i, st, du = attr(tag, "id"), attr(tag, "data-start"), attr(tag, "data-duration")
        if i and st and du:
            w = [(float(st), float(st) + float(du))]
            win[i] = [(max(a, w[0][0]), min(b, w[0][1])) for a, b in win[i] if min(b, w[0][1]) > max(a, w[0][0])] if i in win else w
    return win


def still_windows(src, total):
    """img src -> [(t0, t1)] it is on screen: the intersection of its own and its ancestors' windows (visibility())"""
    from html.parser import HTMLParser
    win = visibility(src, total)
    VOID = {"img", "br", "hr", "input", "meta", "link", "source", "area", "base", "col", "embed", "param", "track", "wbr"}

    def inter(A, B):
        return [(max(a, c), min(b, d)) for a, b in A for c, d in B if min(b, d) > max(a, c)]

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack, self.out = [], {}

        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            if tag == "img" and d.get("src"):
                ids = [i for _, i in self.stack if i] + ([d["id"]] if d.get("id") else [])
                ws = [win[i] for i in ids if i in win]
                if ws:
                    cur = ws[0]
                    for w in ws[1:]:
                        cur = inter(cur, w)
                    self.out.setdefault(d["src"], []).extend(cur)
            if tag not in VOID:
                self.stack.append((tag, d.get("id")))

        def handle_endtag(self, tag):
            for k in range(len(self.stack) - 1, -1, -1):
                if self.stack[k][0] == tag:
                    del self.stack[k:]
                    break

    p = P()
    try:
        p.feed(src)
    except Exception:            # noqa: BLE001  malformed markup: no timing, the QA falls back to the render
        return {}
    return {k: sorted(set(v)) for k, v in p.out.items()}


def composition(project):
    p = os.path.join(project, "index.html")
    if not os.path.exists(p):
        return None
    src = open(p, encoding="utf-8", errors="replace").read()
    index_sidecars(project)
    root = re.search(r'<div[^>]*data-composition-id="main"[^>]*>', src)
    total = float(attr(root.group(0), "data-duration")) if root and attr(root.group(0), "data-duration") else None
    fps = float(attr(root.group(0), "data-fps")) if root and attr(root.group(0), "data-fps") else 30.0
    layers, notes = [], []
    for tag in re.findall(r"<video\b[^>]*>", src):
        s = attr(tag, "src")
        if not s:
            continue
        path = os.path.normpath(os.path.join(project, s))
        if not os.path.exists(path):
            notes.append(f"missing source {s}")
            continue
        info = G.probe(path)
        start = float(attr(tag, "data-start") or 0)
        ms = float(attr(tag, "data-media-start") or attr(tag, "data-offset") or 0)
        dur = float(attr(tag, "data-duration")) if attr(tag, "data-duration") else max(0.0, info["dur"] - ms)
        kind = "sticker" if STICKER_RE.search(s) else "plate" if (PLATE_RE.search(s) or (start <= 0.05 and total and dur >= 0.5 * total)) else "insert"
        blurred = bool(re.search(r"blur\(\s*[1-9]", attr(tag, "style") or "")) or "blur" in (attr(tag, "class") or "").split()
        layers.append({"id": attr(tag, "id") or os.path.basename(s), "src": path, "rel": s, "start": start, "dur": dur, "ms": ms,
                       "kind": kind, "info": info, "still": False, "origin": provenance(path), "blurred": blurred})
    seen = set()
    sw_ = still_windows(src, total)
    for tag in re.findall(r"<img\b[^>]*>", src):
        s = attr(tag, "src")
        if not s or not STILL_RE.search(s) or STICKER_RE.search(s) or s in seen:
            continue
        path = os.path.normpath(os.path.join(project, s))
        im = cv2.imread(path) if os.path.exists(path) else None
        if im is None or min(im.shape[:2]) < 300:
            continue
        seen.add(s)
        blurred = "blur" in (attr(tag, "class") or "") or "blur(" in (attr(tag, "style") or "")
        layers.append({"id": attr(tag, "id") or os.path.basename(s), "src": path, "rel": s, "start": 0.0, "dur": total or 1e9, "ms": 0.0,
                       "kind": "backdrop" if blurred else "insert", "info": {"w": im.shape[1], "h": im.shape[0], "fps": 0, "dur": 0, "rotation": 0},
                       "still": True, "origin": provenance(path), "windows": sw_.get(s, [])})
    if "data-composition-src" in src:
        notes.append("sub-compositions (data-composition-src) are not inspected; their videos fall back to the frame classifier")
    return {"total": total, "fps": fps, "layers": layers, "notes": notes}


SIDECARS = {}       # (dev, inode) of a prepared clip -> its insert_prep sidecar (builds hard-link clips into assets/)


def index_sidecars(project):
    for dp, _, fn in os.walk(project):
        for f in fn:
            if f.endswith((".mp4.json", ".jpg.json", ".png.json", ".mov.json")) and os.path.exists(os.path.join(dp, f[:-5])):
                st = os.stat(os.path.join(dp, f[:-5]))
                SIDECARS[(st.st_dev, st.st_ino)] = os.path.join(dp, f)


def sidecar_of(path):
    """the JSON written next to a clip (insert_prep / proxy.sh / house_look), also through a hard link (inode index)"""
    real = os.path.realpath(path)
    cands = [path + ".json", real + ".json"]
    try:
        st = os.stat(real)
        if SIDECARS.get((st.st_dev, st.st_ino)):
            cands.append(SIDECARS[(st.st_dev, st.st_ino)])
    except OSError:
        pass
    for c in cands:
        if os.path.exists(c):
            try:
                return json.load(open(c))
            except (OSError, json.JSONDecodeError):
                pass
    return {}


def provenance(path):
    """own | ai | stock | unknown, and the original source: insert_prep's sidecar (<clip>.json) first, then the path"""
    real = os.path.realpath(path)
    try:
        st = os.stat(real)
        hard = SIDECARS.get((st.st_dev, st.st_ino))
    except OSError:
        hard = None
    for side in (path + ".json", real + ".json") + ((hard,) if hard else ()):
        if os.path.exists(side):
            try:
                j = json.load(open(side))
                return {"kind": j.get("kind") or G.guess_kind(j.get("src", path)), "src": j.get("src", path),
                        "in": j.get("in", 0.0), "span": j.get("source_span")}
            except (json.JSONDecodeError, OSError):
                pass
    return {"kind": G.guess_kind(real), "src": real, "in": None, "span": None}


_STILL_SRC = {}


def source_still(path):
    """True when a video file never moves: a photo written out as a clip (ffmpeg -loop 1), frozen from its first frame
    to its last. A clip that moves and then holds is a stall (a padded or held cut), not a still."""
    if path not in _STILL_SRC:
        info = G.probe(path)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-an", "-vf", f"scale=270:-2,freezedetect=n=-60dB:d={FREEZE_MAX}", "-f", "null", "-"],
                           capture_output=True, text=True)
        st = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
        en = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", r.stderr)]
        fr = 2.0 / (info["fps"] or 30)
        _STILL_SRC[path] = len(st) == 1 and st[0] <= fr and (not en or en[-1] >= info["dur"] - fr)
    return _STILL_SRC[path]


def cover_size(info, wm, hm):
    """decode size at which the layer, shown object-fit: cover in wm x hm, sits at scale ~1 (ORB matches best there)"""
    sw0, sh0 = info["w"], info["h"]
    if info.get("rotation") in (90, -90, 270, -270):
        sw0, sh0 = sh0, sw0
    s = max(wm / sw0, hm / sh0)
    return max(16, int(round(sw0 * s / 2)) * 2), max(16, int(round(sh0 * s / 2)) * 2)


# ------------------------------------------------------------------ faces
class Faces:
    def __init__(self):
        self.det = None
        self.rec = cv2.FaceRecognizerSF.create(model(SFACE), "")
        self.size = None

    def detect(self, img, thr=0.6):
        h, w = img.shape[:2]
        if self.det is None or self.size != (w, h):
            self.det = cv2.FaceDetectorYN.create(model(YUNET), "", (w, h), thr, 0.3, 50)
            self.size = (w, h)
        self.det.setScoreThreshold(thr)
        _, fs = self.det.detect(img)
        return [] if fs is None else [f for f in fs if f[2] >= 0.03 * w]

    def feature(self, img, f):
        fe = self.rec.feature(self.rec.alignCrop(img, f)).flatten()
        return fe / (np.linalg.norm(fe) + 1e-9)


def speaker_ref(F, comp, frames5, speaker_ref_path=None):
    """mean SFace embedding of the speaker: from the plate layer(s), else the render's first 40 % (frame 1 is the speaker)"""
    imgs = []
    if speaker_ref_path:
        if STILL_RE.search(speaker_ref_path):
            imgs = [cv2.imread(speaker_ref_path)]
        else:
            info = G.probe(speaker_ref_path)
            w, h = cover_size(info, 540, 960)
            imgs = [x[0] for x in (decode(speaker_ref_path, w, h, start=info["dur"] * (i + .5) / 10, dur=0.05) for i in range(10)) if x]
    elif comp and any(l["kind"] == "plate" for l in comp["layers"]):
        for l in [l for l in comp["layers"] if l["kind"] == "plate"][:2]:
            w, h = cover_size(l["info"], 540, 960)
            for i in range(8):
                fr = decode(l["src"], w, h, start=l["ms"] + l["dur"] * (i + .5) / 8, dur=0.05)
                if fr:
                    imgs.append(fr[0])
    else:
        imgs = frames5[: max(1, int(len(frames5) * 0.4))]
    feats = []
    for im in imgs:
        fs = [f for f in F.detect(im, 0.8) if f[2] >= 0.09 * im.shape[1]]
        if fs:
            feats.append(F.feature(im, max(fs, key=lambda f: f[2])))
        if len(feats) >= 12:
            break
    if not feats:
        return None
    E = np.stack(feats)
    m = E.mean(0)
    m /= np.linalg.norm(m)
    keep = E @ m >= 0.5
    if keep.sum() >= 3:
        m = E[keep].mean(0)
        m /= np.linalg.norm(m)
    return m


# ------------------------------------------------------------------ layer matching
ORB = cv2.ORB_create(1200, fastThreshold=10)
BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


def kp(gray):
    return ORB.detectAndCompute(gray, None)


def match(src_kd, ren_kd):
    (ks, ds), (kr, dr) = src_kd, ren_kd
    if ds is None or dr is None or len(ks) < 12 or len(kr) < 12:
        return None
    m = BF.match(ds, dr)
    if len(m) < 15:
        return None
    a = np.float32([ks[x.queryIdx].pt for x in m])
    b = np.float32([kr[x.trainIdx].pt for x in m])
    A, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=4.0, maxIters=2000)
    if A is None:
        return None
    n = int(inl.sum())
    sc = math.hypot(A[0, 0], A[1, 0])
    if n < 20 or n / len(m) < 0.25 or not (0.2 <= sc <= 6):
        return None
    return A, n


def region(A, sw, sh, rw, rh):
    pts = cv2.transform(np.float32([[[0, 0], [sw, 0], [sw, sh], [0, sh]]]), A)[0]
    mask = np.zeros((rh, rw), np.uint8)
    cv2.fillConvexPoly(mask, pts.astype(np.int32), 1)
    return mask.astype(bool)


def detail(x):
    return float(np.abs(cv2.Laplacian(x, cv2.CV_32F)).mean())


def covered_share(ren_g, src_g, A, box):
    """share of a mapped face box's 4x4 cells whose render pixels lost their source: no correlation AND (lost the
    detail or changed brightness). A card or blur does both; a one-frame timing offset on a moving shot does neither."""
    rh, rw = ren_g.shape
    x, y, w, h = box
    x0, y0, x1, y1 = int(max(0, x)), int(max(0, y)), int(min(rw, x + w)), int(min(rh, y + h))
    if w < 14 or (x1 - x0) * (y1 - y0) < 0.6 * w * h:
        return None
    warped = cv2.warpAffine(src_g, A, (rw, rh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    R = ren_g[y0:y1, x0:x1].astype(np.float32)
    S = warped[y0:y1, x0:x1].astype(np.float32)
    bad, n = 0, 4
    for j in range(n):
        for i in range(n):
            sl = (slice(j * R.shape[0] // n, (j + 1) * R.shape[0] // n), slice(i * R.shape[1] // n, (i + 1) * R.shape[1] // n))
            r, s = R[sl], S[sl]
            if r.size < 9:
                continue
            shift = abs(r.mean() - s.mean()) > 35
            rs, ss = r.std(), s.std()
            if ss < 3:
                bad += shift
                continue
            z = float(((r - r.mean()) * (s - s.mean())).mean() / (rs * ss + 1e-6))
            lost = detail(r) < 0.5 * detail(s)
            bad += z < 0.3 and (lost or shift)
    return bad / (n * n)


def context_visible(ren_g, src_g, A, box):
    """share of the textured 8x8-px cells AROUND a face box (shoulders, room) that still match the source: the layer
    is on screen even though ORB lost it (a panel over the middle of the frame)"""
    rh, rw = ren_g.shape
    warped = cv2.warpAffine(src_g, A, (rw, rh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    x, y, w, h = box
    ok = tot = 0
    for cy in range(0, rh - 8, 8):
        for cx in range(0, rw - 8, 8):
            if x - 0.5 * w <= cx + 4 <= x + 1.5 * w and y - 0.5 * h <= cy + 4 <= y + 1.5 * h:
                continue
            s = warped[cy:cy + 8, cx:cx + 8].astype(np.float32)
            if s.std() < 4:
                continue
            r = ren_g[cy:cy + 8, cx:cx + 8].astype(np.float32)
            tot += 1
            ok += float(((r - r.mean()) * (s - s.mean())).mean() / (r.std() * s.std() + 1e-6)) >= 0.5
    return ok / tot if tot >= 30 else 0.0


# ------------------------------------------------------------------ OCR
def ocr(paths):
    if sys.platform != "darwin" or not shutil.which("osascript"):
        return None
    out = {}
    for i in range(0, len(paths), 40):
        r = subprocess.run(["osascript", "-l", "JavaScript", os.path.join(HERE, "ocr_text.js")] + paths[i:i + 40], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            try:
                j = json.loads(line)
                out[j["img"]] = j
            except (json.JSONDecodeError, KeyError):
                pass
    return out


def norm(s):
    return re.sub(r"[^а-яёa-z0-9]", "", s.lower().replace("ё", "е"))


def same_word(x, w):
    return x == w or (len(x) >= 5 and len(w) >= 5 and x[:5] == w[:5])


def rel_lum(bgr):
    c = bgr / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 2] + 0.7152 * c[..., 1] + 0.0722 * c[..., 0]


def text_contrast(img, box):
    """WCAG contrast between the letters and the pixels 2-6 px around them (an outline, a shadow or a pill counts).
    Letters vs background are split (Otsu) INSIDE the text box only: around a pill the frame is often bimodal (a white
    board above, dark footage below), which would flip the classes."""
    x, y, w, h = [int(round(v)) for v in box]
    pad = max(6, h // 4)
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(img.shape[1], x + w + pad), min(img.shape[0], y + h + pad)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0 or w < 4 or h < 4:
        return None
    lum = rel_lum(crop.astype(np.float32))
    g8 = (np.clip(lum, 0, 1) * 255).astype(np.uint8)
    ib = (slice(max(0, y - y0), max(0, y - y0) + h), slice(max(0, x - x0), max(0, x - x0) + w))
    inner = g8[ib]
    if inner.size < 50:
        return None
    thr, _ = cv2.threshold(inner, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    m_in = np.zeros(g8.shape, bool)
    m_in[ib] = True
    hi = (g8 > thr) & m_in
    lo = (g8 <= thr) & m_in
    text = hi if hi.sum() < lo.sum() else lo          # letters are the minority class inside their box
    if text.sum() < 20:
        return None
    t8 = text.astype(np.uint8)
    ring = (cv2.dilate(t8, np.ones((13, 13), np.uint8)) > 0) & ~(cv2.dilate(t8, np.ones((5, 5), np.uint8)) > 0)
    if ring.sum() < 20:
        return None
    lt, lb = float(np.median(lum[text])), float(np.median(lum[ring]))
    if not (np.isfinite(lt) and np.isfinite(lb)):
        return None
    return (max(lt, lb) + 0.05) / (min(lt, lb) + 0.05)


# ------------------------------------------------------------------ main analysis
def analyse(video, project=None, profile="talking-head", words=None, allow_hold=(), use_ocr=True, use_match=True, speaker_ref_path=None, log=print,
            style=None, use_vision=True):
    info = G.probe(video)
    W, H, fps, dur = info["w"], info["h"], info["fps"], info["dur"]
    comp = composition(project) if (project and use_match) else None
    P = PROFILES[profile]
    C, notes = [], []
    if comp:
        notes += comp["notes"]
    ar = H / W
    w5, h5 = 540, int(540 * ar) // 2 * 2
    wm, hm = 360, int(360 * ar) // 2 * 2
    log(f"decoding {os.path.basename(video)}: {W}x{H} {fps:g} fps {dur:.1f} s")
    F5 = decode(video, w5, h5, fps=1 / DT)
    N = len(F5)
    FM = decode(video, wm, hm, fps=1 / DTM, gray=True) if comp else []
    tw, th_ = 180, int(180 * ar) // 20 * 20
    TG = decode(video, tw, th_, gray=True)                           # native fps: motion and freezes
    T = np.array([np.abs(TG[i].astype(np.float32) - TG[i - 1]).reshape(th_ // 20, 20, tw // 20, 20).mean(axis=(1, 3))
                  for i in range(1, len(TG))]) if len(TG) > 1 else np.zeros((0, th_ // 20, tw // 20))
    del TG
    Fc = Faces()
    ref = speaker_ref(Fc, comp, F5, speaker_ref_path)
    if ref is None and profile == "talking-head":
        notes.append("no speaker face found for the reference embedding")

    # ---------- per 5 fps sample: faces, speaker, stats, classifier
    faces5, spk, boxes, stats, gfx = [], [], [], [], []
    for im in F5:
        fs = Fc.detect(im)
        best = None
        for f in fs:
            if f[2] >= MINW * w5 and ref is not None and float(Fc.feature(im, f) @ ref) >= SPK_TH and (best is None or f[2] > best[2]):
                best = f
        faces5.append(fs)
        spk.append(best is not None)
        boxes.append(None if best is None else (best[0] / w5, best[1] / h5, best[2] / w5, best[3] / h5))
        small = cv2.resize(im, (270, int(270 * ar) // 2 * 2), interpolation=cv2.INTER_AREA)
        stats.append(G.frame_stats(small))
        gfx.append(is_graphic(nb_features(small)))

    # ---------- layers on screen (10 fps): coverage, transform, covered faces
    vis = {}           # layer id -> {k10: (coverage, A, mask)}
    occl = []          # (t, layer, covered, box)
    lay = {l["id"]: l for l in comp["layers"]} if comp else {}
    if comp:
        rkd = [kp(g) for g in FM]

        def faces_cover(lid, k, src_g, A, sfaces):
            for f in sfaces:
                c = cv2.transform(np.float32([[[f[0], f[1]], [f[0] + f[2], f[1] + f[3]]]]), A)[0]
                bx = (c[0][0], c[0][1], c[1][0] - c[0][0], c[1][1] - c[0][1])
                cv_ = covered_share(FM[k], src_g, A, bx)
                if cv_ is not None and cv_ >= COVER_MIN:
                    occl.append((round(k * DTM, 2), lid, round(cv_, 2), [round(float(v) * W / wm) for v in bx]))

        for l in comp["layers"]:
            if l["kind"] in ("sticker", "backdrop") or l["still"]:
                continue
            sw, sh = cover_size(l["info"], wm, hm)
            k0 = max(0, int(math.ceil(l["start"] / DTM - 1e-6)))
            k1 = min(len(FM), int(math.floor((l["start"] + l["dur"]) / DTM - 1e-6)) + 1)
            if k1 <= k0:
                continue
            SF = decode(l["src"], sw, sh, fps=1 / DTM, gray=True, start=l["ms"] + k0 * DTM - l["start"], dur=(k1 - k0) * DTM + 0.05)
            vis[l["id"]] = {}
            sfaces, lastA = [], None
            small_ok = l["kind"] == "insert"            # a framed insert (PiP, card) can sit at 1/4 of the cover scale
            for j, k in enumerate(range(k0, k1)):
                if j >= len(SF):
                    break
                m = match(kp(SF[j]), rkd[k])
                if not m and small_ok:
                    sc = 0.35
                    sm = cv2.resize(SF[j], (max(16, int(sw * sc)), max(16, int(sh * sc))), interpolation=cv2.INTER_AREA)
                    m2 = match(kp(sm), rkd[k])
                    if m2:
                        A2 = m2[0].copy()
                        A2[:, :2] *= sc                         # transform of the full-size source frame
                        m = (A2, m2[1])
                if not m:
                    # ORB lost the layer: a panel may cover the middle of the frame. Keep the transform of the last
                    # 0.2 s and look at the face only if the layer's surroundings are still on screen.
                    if lastA is not None and k - lastA[1] <= 2 and sfaces:
                        A = lastA[0]
                        f = max(sfaces, key=lambda f: f[2])
                        c = cv2.transform(np.float32([[[f[0], f[1]], [f[0] + f[2], f[1] + f[3]]]]), A)[0]
                        if context_visible(FM[k], SF[j], A, (c[0][0], c[0][1], c[1][0] - c[0][0], c[1][1] - c[0][1])) >= 0.5:
                            faces_cover(l["id"], k, SF[j], A, sfaces)
                    continue
                A, _ = m
                lastA = (A, k)
                mask = region(A, sw, sh, wm, hm)
                vis[l["id"]][k] = (float(mask.mean()), A, mask)
                if j % 2 == 0 or not sfaces:
                    sfaces = [f for f in Fc.detect(cv2.cvtColor(SF[j], cv2.COLOR_GRAY2BGR), 0.7) if f[2] >= 0.04 * sw]
                faces_cover(l["id"], k, SF[j], A, sfaces)
            log(f"  layer {l['id']:>14s} ({l['kind']}): on screen in {len(vis[l['id']])} of {k1 - k0} samples")
        # stills: matched on the samples nothing else explains (no speaker, no video layer)
        stills = [l for l in comp["layers"] if l["still"] and l["kind"] == "insert"]
        if stills:
            open_k = [k for k in range(len(FM)) if not spk[min(N - 1, int(round(k * DTM / DT)))] and not any(k in v for v in vis.values())]
            for l in stills:
                im = cv2.imread(l["src"], cv2.IMREAD_GRAYSCALE)
                sw, sh = cover_size(l["info"], wm, hm)
                sg = cv2.resize(im, (sw, sh), interpolation=cv2.INTER_AREA)
                skd = kp(sg)
                sfaces = [f for f in Fc.detect(cv2.cvtColor(sg, cv2.COLOR_GRAY2BGR), 0.7) if f[2] >= 0.04 * sw]
                vis[l["id"]] = {}
                for k in open_k[::1]:
                    m = match(skd, rkd[k])
                    if m:
                        A, _ = m
                        mask = region(A, sw, sh, wm, hm)
                        vis[l["id"]][k] = (float(mask.mean()), A, mask)
                        faces_cover(l["id"], k, sg, A, sfaces)
                if vis[l["id"]]:
                    log(f"  still {l['id']:>14s}: on screen in {len(vis[l['id']])} samples")

    def ins_at(k5):
        """(layer id, coverage, A, mask) of the biggest insert on screen at a 5 fps sample"""
        best = None
        for kk in (int(round(k5 * DT / DTM)), int(round(k5 * DT / DTM)) + 1):
            for lid, v in vis.items():
                if lay[lid]["kind"] == "insert" and kk in v and (best is None or v[kk][0] > best[1]):
                    best = (lid, *v[kk])
        return best

    def scheduled(t):
        return [l["id"] for l in (comp["layers"] if comp else []) if l["kind"] == "insert" and not l["still"] and l["start"] <= t < l["start"] + l["dur"]]

    # ---------- labels
    L, INS = [], []
    for k in range(N):
        li = ins_at(k) if comp else None
        INS.append(li)
        t = k * DT
        if spk[k]:
            L.append("S")
        elif li and li[1] >= 0.6:
            L.append("B")
        elif li:
            L.append("F")
        elif comp and any(int(round(t / DTM)) in vis.get(l["id"], {}) for l in comp["layers"] if l["kind"] == "plate"):
            L.append("P")
        elif comp:
            L.append("B" if (not gfx[k] and scheduled(t)) else "G")    # an insert ORB could not lock on (dark, blurred)
        else:
            L.append("G" if gfx[k] else "B")
    for k in range(1, N - 1):
        if L[k - 1] == L[k + 1] != L[k]:
            L[k] = L[k - 1]
    n = {c: L.count(c) for c in "SBFGP"}
    pct = {c: round(100 * n[c] / max(1, N), 1) for c in "SBFGP"}
    R = runs(L)

    # ---------- inserts: runs where an insert is on screen (shots back to back = one insert)
    on = [(INS[k] is not None) or (comp is not None and L[k] == "B") or (comp is None and L[k] == "B") for k in range(N)]
    segs, k = [], 0
    while k < N:
        if on[k]:
            j = k
            while j + 1 < N and (on[j + 1] or (j + 2 < N and on[j + 2])):
                j += 1
            if j > k or comp is None:
                ids = sorted({INS[q][0] for q in range(k, j + 1) if INS[q]}) or ["?"]
                segs.append((round(k * DT, 2), round((j + 1) * DT, 2), ids, any(spk[q] for q in range(k, j + 1))))
            k = j + 1
        else:
            k += 1
    ipm = len(segs) / (dur / 60) if dur else 0

    # ---------- grade per insert, vs the speaker
    Sidx = [k for k in range(N) if L[k] == "S" and not INS[k]]
    ref_st = G.median_stats([stats[k] for k in Sidx]) if len(Sidx) >= 10 else None
    ref_from = "speaker frames in the render"
    if ref_st is None and comp and any(l["kind"] == "plate" for l in comp["layers"]):
        ref_st = G.plate_stats(next(l["src"] for l in comp["layers"] if l["kind"] == "plate"))
        ref_from = "the plate file"
    if ref_st is None:
        ref_st = G.median_stats([stats[k] for k in range(N) if L[k] in "BF"])
        ref_from = "the reel's footage median (no speaker)"
    looks = []
    if comp and ref_st:
        for lid in [l["id"] for l in comp["layers"] if l["kind"] == "insert"]:
            rows = []
            for k5 in range(N):
                li = INS[k5]
                if not li or li[0] != lid:
                    continue
                small = cv2.resize(F5[k5], (wm, hm), interpolation=cv2.INTER_AREA)
                rows.append(G.frame_stats(small) if li[1] >= 0.95 else G.region_stats(small, li[3]))
            rows = [r for r in rows if r]
            if len(rows) >= 2:
                d, fl, wa = G.compare(G.median_stats(rows), ref_st)
                looks.append({"layer": lid, "src": lay[lid]["rel"], "samples": len(rows), **d, "fail": fl, "warn": wa})
    elif ref_st:
        for l_, s, e, _, _ in R:
            if l_ != "B" or e - s < 0.4:
                continue
            d, fl, wa = G.compare(G.median_stats([stats[k] for k in range(int(round(s / DT)), min(N, int(round(e / DT))))]), ref_st)
            looks.append({"layer": f"B {s:.1f}-{e:.1f}", "src": "", "samples": int(round((e - s) / DT)), **d, "fail": fl, "warn": wa})

    # ---------- graphics: length and motion
    gseg = [e - s for l_, s, e, _, _ in R if l_ == "G"]
    glong = [(s, e) for l_, s, e, _, _ in R if l_ == "G" and e - s >= 1.0]
    gact = [float((T[i] > 2.0).mean() >= 0.02) for i in range(len(T)) if any(s <= (i + 1) / fps < e for s, e in glong)]

    # ---------- freezes (native fps): inside the speaker's face box, inside a moving video insert's region
    tail = min(dur, comp["total"]) if comp and comp.get("total") else dur      # the plate's held last frame under the music fade
    holds = [(tail - 0.5 - 2.0 / fps, dur + 1)] + [tuple(h) for h in allow_hold]
    vh, vw = T.shape[1:] if len(T) else (0, 0)
    ident = np.zeros(len(T), bool)
    where = np.array([""] * len(T), dtype=object)
    dval = np.full(len(T), np.nan)
    for i in range(len(T)):
        t = (i + 1) / fps
        k = min(int(round(t / DT)), N - 1)
        if not (L[max(0, k - 1)] == L[k] == L[min(N - 1, k + 1)]):
            continue
        d = None
        plate_vis = (not comp) or any(int(round(t / DTM)) in vis.get(l["id"], {}) or int(round(t / DTM)) - 1 in vis.get(l["id"], {})
                                      for l in comp["layers"] if l["kind"] == "plate")
        if L[k] == "S" and boxes[k] and plate_vis:      # (a face in a still photo card is still by design)
            x, y, w, h = boxes[k]
            x0, x1 = int(max(0, (x - .1 * w) * vw)), int(min(vw, np.ceil((x + 1.1 * w) * vw)))
            y0, y1 = int(max(0, (y - .1 * h) * vh)), int(min(vh, np.ceil((y + 1.1 * h) * vh)))
            d, wtag = float(T[i, y0:y1, x0:x1].mean()), "S"
        elif comp and INS[k] and not lay[INS[k][0]]["still"]:
            tm = cv2.resize(INS[k][3].astype(np.float32), (vw, vh), interpolation=cv2.INTER_AREA) >= 0.9
            if tm.sum() >= 4:
                d, wtag = float(np.median(T[i][tm])), "I:" + INS[k][0]
        elif not comp and L[k] == "B":
            d, wtag = float(np.median(T[i])), "B"
        if d is None:
            continue
        ident[i], where[i], dval[i] = d < 0.05, wtag, d

    def moving_before(i, kind, thr):
        a0 = max(0, i - 12)
        return int(((where[a0:i] == kind) & (dval[a0:i] >= thr)).sum()) >= 9

    freezes, i = [], 0
    while i < len(T):
        if ident[i]:
            j = i
            while j + 1 < len(T) and ident[j + 1] and where[j + 1] == where[i]:
                j += 1
            t0, t1 = (i + 1) / fps, (j + 2) / fps
            if (j - i + 1) / fps > FREEZE_MAX and moving_before(i, where[i], 0.05 if where[i] == "S" else 0.15) \
                    and not any(a <= t0 and t1 <= b for a, b in holds):
                freezes.append((round(t0, 2), round(t1 - t0, 2), "speaker" if where[i] == "S" else where[i].replace("I:", "insert ")))
            i = j + 1
        else:
            i += 1
    src_issues, still_warn, still_ok = [], [], []
    if comp:
        for l in comp["layers"]:
            if l["kind"] in ("sticker", "backdrop") or l["still"]:
                continue
            li = l["info"]
            over = l["ms"] + l["dur"] - li["dur"]
            tail_hold = l["kind"] == "plate" and l["start"] + l["dur"] >= dur - 2.0 and over < 2.0
            photo = l["kind"] == "insert" and source_still(l["src"])
            if over > 1.5 / fps and not tail_hold and not photo:
                src_issues.append(f"{l['id']}: plays {over:.2f} s past the end of {l['rel']} (a held last frame)")
            if photo:
                # a photo shown as a clip: judge how the reel shows it, not the file
                name = f"{l['id']} ({os.path.basename(l['rel'])})"
                full = sorted(k for k, v in vis.get(l["id"], {}).items() if v[0] >= 0.6)
                runs_, cur = [], []
                for k in full:
                    if cur and k - cur[-1] > 2:
                        runs_.append(cur)
                        cur = []
                    cur.append(k)
                if cur:
                    runs_.append(cur)
                long_ = [r for r in runs_ if (r[-1] - r[0] + 1) * DTM >= 0.5]
                if l.get("blurred"):
                    still_ok.append(f"{name}: a still clip as a blurred backdrop (by design)")
                    continue
                if not long_:
                    still_ok.append(f"{name}: a still clip, framed or under 0.5 s full screen (a photo; by design)")
                    continue
                if use_vision:
                    import broll_vision as BV
                    mv = BV.still_motion(l["src"])
                else:
                    mv = {"error": "--no-vision"}
                for r in long_:
                    t0_, d_ = r[0] * DTM, (r[-1] - r[0] + 1) * DTM
                    As = [vis[l["id"]][k][1] for k in r]
                    sc = [float(np.hypot(A[0, 0], A[1, 0])) for A in As]
                    drift = max(float(np.ptp([A[0, 2] for A in As])), float(np.ptp([A[1, 2] for A in As]))) / wm
                    zoom = max(sc) / max(min(sc), 1e-6)
                    push = zoom - 1 >= 0.005 or drift >= 0.01
                    how = f"scale x{zoom:.3f}, drift {drift * 100:.1f} % of the width"
                    if mv.get("moving"):
                        src_issues.append(f"{name}: a still of {mv.get('what') or 'a subject caught mid-movement'}, full screen {d_:.1f} s at "
                                          f"{t0_:.1f} s, reads as a frozen video ({how})")
                    elif "error" in mv:
                        still_warn.append(f"{name}: a still full screen {d_:.1f} s at {t0_:.1f} s, not checked for a subject caught "
                                          f"mid-movement ({mv['error']})")
                    elif not push and d_ >= 1.0:
                        still_warn.append(f"{name}: a still held full screen {d_:.1f} s at {t0_:.1f} s without a push ({how})")
                    else:
                        still_ok.append(f"{name}: a still full screen {d_:.1f} s at {t0_:.1f} s, {'pushed' if push else 'short'} "
                                        f"({how}; {mv.get('what', '')})")
                continue
            if l["kind"] == "insert":
                r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{l['ms']:.3f}", "-t", f"{max(0.05, min(l['dur'], li['dur'] - l['ms'])):.3f}", "-i", l["src"],
                                    "-an", "-vf", f"scale=270:-2,freezedetect=n=-60dB:d={FREEZE_MAX}", "-f", "null", "-"], capture_output=True, text=True)
                win = max(0.05, min(l["dur"], li["dur"] - l["ms"]))
                starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
                durs = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", r.stderr)]
                for q, s_ in enumerate(starts):
                    d_ = durs[q] if q < len(durs) else win - s_          # still frozen when the window ends
                    if d_ > FREEZE_MAX:
                        src_issues.append(f"{l['id']}: {d_:.2f} s frozen inside {l['rel']} at {l['ms'] + s_:.2f} s (a padded or held cut)")

    # ---------- captions (OCR), grouped into events; the best read of an event counts (blur-ins don't)
    caps, latin, ocr_note = [], set(), None
    if use_ocr:
        tmp = tempfile.mkdtemp(prefix="brollqa-")
        subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", "fps=2.5", "-q:v", "2", os.path.join(tmp, "f%05d.jpg")], check=True)
        imgs = sorted(glob.glob(os.path.join(tmp, "f*.jpg")))
        log(f"  OCR on {len(imgs)} frames...")
        res = ocr(imgs)
        if res is None:
            ocr_note = "OCR unavailable (needs macOS osascript): captions not checked"
        else:
            spoken = [(w["s"], w["e"], norm(w["w"])) for w in (words or []) if norm(w["w"])]
            cyr = sum(bool(re.search("[а-яё]", w[2])) for w in spoken) > 0.5 * max(1, len(spoken))
            reads, latin_reads = [], {}
            for idx, p in enumerate(imgs):
                t = idx / 2.5 + 0.2
                j = res.get(p)
                if not j or "lines" not in j:
                    continue
                k5 = min(N - 1, int(round(t / DT)))
                plate_on = comp is not None and any(int(round(t / DTM)) in vis.get(l["id"], {}) for l in comp["layers"] if l["kind"] == "plate")
                body = None
                if spk[k5] and boxes[k5]:
                    x, y, w, h = boxes[k5]
                    body = ((x - 3 * w) * W, (x + 4 * w) * W, (y + h) * H)
                elif plate_on:
                    body = (0, W, 0.4 * H)
                img = None
                near = [w[2] for w in spoken if t - 1.6 <= w[0] <= t + 0.8]
                over_footage = L[k5] in "SPBF"
                for ln in j["lines"]:
                    bx = [float(v) for v in ln["box"]]
                    cx, cy = bx[0] + bx[2] / 2, bx[1] + bx[3] / 2
                    on_body = body is not None and body[0] <= cx <= body[1] and cy >= body[2]
                    if cyr and not on_body and float(ln.get("conf", 1)) >= 0.5:
                        for x in ln["text"].split():
                            x = x.strip(".,!?:;«»\"'()")
                            if re.fullmatch(r"[A-Za-z]{3,}", x):
                                latin_reads[x.upper()] = latin_reads.get(x.upper(), 0) + 1
                    toks = [norm(x) for x in ln["text"].split() if norm(x)]
                    if not toks or not spoken or not over_footage:
                        continue
                    hit = sum(1 for x in toks if any(same_word(x, w) for w in near))
                    if hit < max(1, 0.6 * len(toks)):
                        continue
                    if img is None:
                        img = cv2.imread(p)
                    reads.append({"t": round(t, 2), "text": ln["text"], "key": " ".join(toks), "px": bx[3] / CAP_RATIO, "contrast": text_contrast(img, bx), "y": round(bx[1])})
            latin = {x for x, n in latin_reads.items() if n >= 2}
            for r in sorted(reads, key=lambda r: r["t"]):          # one event = the same text on consecutive reads
                e = next((e for e in caps if e["key"] == r["key"] and r["t"] - e["t1"] <= 0.45), None)
                if e:
                    e["t1"] = r["t"]
                    e["px"].append(r["px"])
                    e["contrast"].append(r["contrast"])
                else:
                    caps.append({"t0": r["t"], "t1": r["t"], "text": r["text"], "key": r["key"], "px": [r["px"]], "contrast": [r["contrast"]], "y": r["y"], "reads": 0})
            for e in caps:
                e["reads"] = len(e["px"])
                e["px"] = round(float(np.median(e["px"])))
                cs = [c for c in e["contrast"] if c is not None]
                e["contrast"] = round(max(cs), 1) if cs else None
        shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------ checks
    if P["broll_full_max"] is not None:
        st = "fail" if pct["B"] > P["broll_full_max"] else "pass"
        C.append(chk("broll_full", "Full-screen B-roll", st, f"{pct['B']} %", f"<= {P['broll_full_max']:g} %",
                     [f"{s:.1f}-{e:.1f} s" for l_, s, e, _, _ in R if l_ == "B"][:12],
                     None if st == "pass" else "Cut inserts (a spoken list becomes typography), or frame them (PiP, polaroid, split) so the face stays on screen."))
    if P["speaker_min"] is not None:
        st = "fail" if pct["S"] < P["speaker_min"] else "pass"
        gaps = sorted([(e - s, s, e) for l_, s, e, _, _ in R if l_ != "S"], reverse=True)[:6]
        C.append(chk("speaker", "Speaker on screen", st, f"{pct['S']} %", f">= {P['speaker_min']:g} %",
                     ["longest stretches without the speaker's face: " + ", ".join(f"{s:.1f}-{e:.1f} s" for _, s, e in gaps)],
                     None if st == "pass" else "Keep small glances on screen (cover only look-aways > 0.5 s or > 12 deg); shorten full-screen scenes; frame the inserts."))
    if P["inserts_per_min_max"] is not None:
        st = "fail" if ipm > P["inserts_per_min_max"] else "pass"
        C.append(chk("inserts", "Inserts per minute", st, round(ipm, 1), f"<= {P['inserts_per_min_max']:g}",
                     [f"{s:.1f}-{e:.1f} s {'+'.join(ids)}{' (framed, face on screen)' if f else ''}" for s, e, ids, f in segs][:14],
                     None if st == "pass" else "One insert per idea, not per noun: drop the weakest, merge neighbours into one shot."))
    if looks:
        bad = [x for x in looks if x["fail"]]
        med_sat = float(np.median([x["sat"] for x in looks]))
        reel_bad = not (G.SAT_LO <= med_sat <= G.SAT_HI)
        st = "fail" if bad or reel_bad else ("warn" if any(x["warn"] for x in looks) else "pass")
        det = [f"reference: {ref_from} (L* {ref_st['L']:.0f}, wb b* {ref_st['wb_b']:+.0f}, chroma {ref_st['C']:.1f}); reel median saturation x{med_sat:.2f}"]
        det += [f"{x['layer']}: wb {x['dwb']:+.0f} b*, L* {x['dL']:+.0f}, sat x{x['sat']:.2f}" + (f"  FAIL {'; '.join(x['fail'])}" if x["fail"] else "") for x in looks][:16]
        C.append(chk("grade", "Insert grade vs the plate", st, f"{len(bad)} of {len(looks)} inserts off; median sat x{med_sat:.2f}",
                     f"|wb| <= {G.WB_MAX:g}, |L*| <= {G.L_MAX:g}, sat x{G.SAT_HARD[0]}-{G.SAT_HARD[1]} each, reel x{G.SAT_LO}-{G.SAT_HI}", det,
                     None if st != "fail" else "Conform the inserts: scripts/insert_prep.py SRC OUT --ref <plate>; a shot that still fails is from another world: replace it."))
    else:
        C.append(chk("grade", "Insert grade vs the plate", "skip", "no inserts"))
    if gseg:
        med = float(np.median(gseg))
        anim = 100 * float(np.mean(gact)) if gact else 100.0
        st = "fail" if med > GFX_MEDIAN_MAX or anim < GFX_ANIM_MIN else "pass"
        C.append(chk("graphics", "Graphic scenes: length and motion", st, f"median {med:.1f} s, {anim:.0f} % moving",
                     f"median <= {GFX_MEDIAN_MAX} s, >= {GFX_ANIM_MIN:g} % moving",
                     [f"{s:.1f}-{e:.1f} s ({e - s:.1f} s)" for l_, s, e, _, _ in R if l_ == "G"][:12],
                     None if st == "pass" else "Split long scenes; land a state change every 1-1.5 s (count, fill, swap); a held static card is a slide."))
    else:
        C.append(chk("graphics", "Graphic scenes: length and motion", "skip", "no full-screen graphics"))
    if use_ocr and ocr_note is None and words:
        small = [c for c in caps if c["px"] < CAP_PX_MIN]
        low = [c for c in caps if c["contrast"] is not None and c["contrast"] < CAP_CONTRAST_MIN]
        badc = {id(c) for c in small + low}
        steady = [c for c in caps if c["reads"] >= 2]          # a single read can be a blur-in or a half-typed line
        share = len([c for c in steady if id(c) in badc]) / len(steady) if steady else 0
        st = "fail" if caps and share > 0.15 else ("warn" if badc or not caps else "pass")
        det = []
        if caps:
            cons = [c["contrast"] for c in caps if c["contrast"] is not None]
            det.append(f"{len(caps)} caption events ({len(steady)} read twice or more); size median {np.median([c['px'] for c in caps]):.0f} px; contrast median {np.median(cons) if cons else 0:.1f}:1")
            det += [f"{c['t0']:.1f} s «{c['text']}» ~{c['px']} px, {c['contrast']}:1" for c in sorted([c for c in caps if id(c) in badc], key=lambda c: (c['contrast'] or 99, c['px']))[:8]]
        else:
            det.append("no spoken-word text read on screen")
        C.append(chk("captions", "Captions: size and contrast", st, f"{share * 100:.0f} % of caption events small or low-contrast" if caps else "none read",
                     f">= {CAP_PX_MIN} px, >= {CAP_CONTRAST_MIN:g}:1 against the letters' surroundings", det,
                     None if st != "fail" else "Bigger type (>= 48 px for phrases); on light clothing or bright footage a dark outline, shadow or pill behind the words."))
    elif use_ocr:
        C.append(chk("captions", "Captions: size and contrast", "skip", ocr_note or "no transcript (--words) to tell captions from UI text"))
    if latin:
        C.append(chk("language", "Latin text in a Cyrillic reel", "warn", ", ".join(sorted(latin)[:12]), "Russian on screen",
                     ["decor text (sticky notes, calendars, app names) should be in the reel's language"], "Translate the decor text."))
    if comp:
        # events: consecutive 10 fps samples per layer. A cover that lasts >= 0.2 s, or one frame hiding half a face that is
        # not part of a full-screen change, is a card / panel / blur sitting on the face (a panel growing from an icon on
        # the chin). One frame of a scene wiping in over the whole frame is motion: a warning.
        ev = []
        for t, lid, cvr, bx in sorted(occl):
            e = next((e for e in ev if e["layer"] == lid and t - e["t1"] <= DTM + 1e-6), None)
            if e:
                e["t1"], e["max"], e["n"] = t, max(e["max"], cvr), e["n"] + 1
            else:
                ev.append({"t0": t, "t1": t, "layer": lid, "max": cvr, "box": bx, "n": 1})
        for e in ev:
            v = vis.get(e["layer"], {})
            k0, k1 = int(round(e["t0"] / DTM)), int(round(e["t1"] / DTM))
            gone = any(kk not in v for kk in (k1 + 1, k1 + 2)) or any(kk not in v for kk in (k0 - 1, k0 - 2))
            e["transition"] = gone
            e["fail"] = e["n"] >= 2 or (e["max"] >= 0.5 and not gone)
        bad = [e for e in ev if e["fail"]]
        st = "fail" if bad else ("warn" if ev else "pass")
        C.append(chk("faces", "Nothing over a face", st, f"{len(bad)} event(s), {len(ev) - len(bad)} one-frame transition(s)", "no card, panel or blur over any face",
                     [f"{e['t0']:.1f}-{e['t1'] + DTM:.1f} s: a face in {e['layer']} is {e['max'] * 100:.0f} % covered for {e['n'] * DTM:.1f} s"
                      f"{' (one frame of a full-screen change)' if not e['fail'] else ''} (box {e['box']})" for e in sorted(ev, key=lambda e: not e['fail'])][:10],
                     None if st != "fail" else "Keep cards on the chest band (y >= 990) and off stock faces; a scene that opens from an icon starts it below the chin and opens fast (power2.in, <= 0.25 s), with its content in from the first frame.",
                     times=[e["t0"] for e in bad]))
    else:
        C.append(chk("faces", "Nothing over a face", "skip", "needs --project (the composition's layers)"))
    if comp:
        ins_layers = [l for l in comp["layers"] if l["kind"] == "insert"]
        # stock: never full screen (polaroid, phone or card only)
        bad_stock = []
        for l in ins_layers:
            if l["origin"]["kind"] != "stock":
                continue
            full = sorted(k for k, v in vis.get(l["id"], {}).items() if v[0] >= 0.6)
            runs_, cur = [], []
            for k in full:
                if cur and k - cur[-1] > 2:
                    runs_.append(cur); cur = []
                cur.append(k)
            if cur:
                runs_.append(cur)
            for r in runs_:
                if (r[-1] - r[0] + 1) * DTM >= 0.4:
                    bad_stock.append(f"{l['id']} ({os.path.basename(l['origin']['src'])}): full screen {r[0] * DTM:.1f}-{(r[-1] + 1) * DTM:.1f} s")
        unknown_full = []
        for l in ins_layers:
            if l["origin"]["kind"] == "unknown" and not l["still"]:
                full = [k for k, v in vis.get(l["id"], {}).items() if v[0] >= 0.6]
                if len(full) * DTM >= 0.4:
                    unknown_full.append(l["id"])
        kinds = {}
        for l in ins_layers:
            kinds[l["origin"]["kind"]] = kinds.get(l["origin"]["kind"], 0) + 1
        if unknown_full and not bad_stock:
            bad_stock_note = [f"{len(unknown_full)} full-screen insert(s) of unknown source ({', '.join(unknown_full[:6])}): prepare clips with "
                              "insert_prep.py / proxy.sh so their source is recorded; stock must be framed"]
        else:
            bad_stock_note = []
        if profile == "broll-led":                  # full-screen B-roll IS the format (user, 2026-10-14): world/models/pace guard it
            bad_stock, bad_stock_note = [], ([f"{sum(1 for l in ins_layers if l['origin']['kind'] == 'stock')} stock insert(s); full screen is the format here"]
                                              if any(l["origin"]["kind"] == "stock" for l in ins_layers) else [])
        C.append(chk("stock", "Stock only inside a frame", "fail" if bad_stock else ("warn" if bad_stock_note and profile != "broll-led" else "pass"),
                     f"{len(bad_stock)} full-screen stock shot(s); inserts by source: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())),
                     "stock is the last resort, framed (polaroid, phone, card), never full screen", bad_stock[:8] + bad_stock_note,
                     "Put the stock shot in a frame (PiP, polaroid, phone card) or replace it with the user's own footage / an AI still." if bad_stock else None))
        # own footage: only the speaker
        meref = [ref] if ref is not None else []
        mp = os.path.join(MODELS, "..", "me", "face_ref.npz")
        if os.path.exists(mp):
            meref += list(np.load(mp)["emb"])
        others = []
        if meref:
            R_ = np.stack(meref)
            for l in ins_layers:
                if l["origin"]["kind"] != "own":
                    continue
                if l["still"]:
                    frames_ = [(0.0, cv2.imread(l["src"]))]
                else:
                    li = l["info"]
                    w_, h_ = G.fit(li, 360)
                    frames_ = [(l["start"] + q / 5, im) for q, im in enumerate(decode(l["src"], w_, h_, fps=5, start=l["ms"], dur=min(l["dur"], li["dur"] - l["ms"])))]
                for t, im in frames_:
                    for f in Fc.detect(im, 0.6):
                        if f[2] < 0.04 * im.shape[1]:
                            continue
                        cos = float((R_ @ Fc.feature(im, f)).max())
                        if cos < SPK_TH:
                            others.append(f"{l['id']} ({os.path.basename(l['origin']['src'])}) at {t:.1f} s: a face that is not the speaker's (cosine {cos:.2f})")
                            break
        C.append(chk("own_people", "Own footage shows only the speaker", "fail" if others else "pass", f"{len(others)} frame(s) with someone else",
                     "only the speaker (or nobody) in their own footage", others[:8],
                     "Pick another window (own_footage.py find / check), or get the user's yes on own_footage.py sheet first." if others else None))
        # the vision check (Gemini on the window each layer uses, broll_vision.py, cached) runs first: `models` drops a
        # detector face in a shot it says has nobody in it; `people` and `match` report it below
        vl = [l for l in comp["layers"] if l["kind"] in ("insert", "backdrop")]
        for l in vl:
            if l["still"] and not l.get("windows") and vis.get(l["id"]):
                ks, w_ = sorted(vis[l["id"]]), []
                for k in ks:
                    if w_ and k * DTM - w_[-1][1] <= 0.3:
                        w_[-1][1] = (k + 1) * DTM
                    else:
                        w_.append([k * DTM, (k + 1) * DTM])
                l["windows"] = [tuple(x) for x in w_]
        res_v = None
        if vl and use_vision:
            import broll_vision as BV
            log(f"  vision: people rules + line match on {len(vl)} B-roll layer(s)")
            res_v = BV.check_many([BV.layer_job(l, words) for l in vl])
        nobody = {l["id"] for l, r in zip(vl, res_v or []) if "error" not in r and r.get("people") == "none"}
        # no posed stock models: a stranger's face big in a stock / AI / unknown insert
        models, ignored = [], []
        if meref:
            for l in ins_layers:
                if l["origin"]["kind"] == "own":
                    continue
                if l["still"]:
                    frames_ = [(0.0, cv2.imread(l["src"]))]
                else:
                    li = l["info"]
                    frames_ = [(l["start"] + q / 2, im) for q, im in enumerate(decode(l["src"], *G.fit(li, 360), fps=2, start=l["ms"], dur=min(l["dur"], li["dur"] - l["ms"])))]
                for t, im in frames_:
                    hit = None
                    for f in Fc.detect(im, 0.7):
                        if f[2] >= 0.08 * im.shape[1] and float((R_ @ Fc.feature(im, f)).max()) < SPK_TH:
                            hit = (f"{l['id']} ({os.path.basename(l['origin']['src'])}) at {t:.1f} s: a stranger's face, {f[2] / im.shape[1] * 100:.0f} % "
                                   f"of the width (detector score {f[14]:.2f})")
                            break
                    if hit and l["id"] in nobody:
                        ignored.append(hit.replace("a stranger's face", "a detector face") + "; the vision check sees nobody: not counted")
                        break
                    if hit:
                        models.append(hit)
                        break
        st_m = ("fail" if profile == "broll-led" else "warn") if models else "pass"
        C.append(chk("models", "No posed stock models", st_m, f"{len(models)} insert(s) with a stranger's face" + (f", {len(ignored)} false detection(s)" if ignored else ""),
                     "places, objects, the speaker's world; no stock faces", models[:8] + ignored[:4], "Replace the shot with the user's footage, a place or an object, or an AI still in the reel's frame language." if models else None))
        # 1080p or better
        lowres = []
        for l in ins_layers:
            if l["still"]:
                continue
            o = l["origin"]["src"]
            try:
                oi = G.probe(o) if o and os.path.exists(o) else l["info"]
            except Exception:
                oi = l["info"]
            if min(G.shown_size(oi)) < 1080:
                lowres.append(f"{l['id']}: {os.path.basename(o)} is {oi['w']}x{oi['h']}")
        C.append(chk("resolution", "B-roll 1080p or better", "fail" if lowres else "pass", f"{len(lowres)} low-res insert(s)", "short side >= 1080",
                     lowres[:8], "Use a 2160p/1080p source (no 720p B-roll; Mixkit only where 2160p is offered)." if lowres else None))
        # the people rules (people-rules.json) and every B-roll shot shows what its line says. Gemini on the window each
        # layer uses (broll_vision.py, cached).
        if vl and use_vision:
            name = lambda l: f"{l['id']} ({os.path.basename(l['origin']['src'] or l['src'])})"   # noqa: E731
            ppl = [f"{name(l)}: {BV.verdict(r)}" for l, r in zip(vl, res_v) if "error" not in r and not r["ok"] and not r.get("confirmed")]
            okd = [f"{name(l)}: {BV.verdict(r)}" for l, r in zip(vl, res_v) if "error" not in r and not r["ok"] and r.get("confirmed")]
            unk = [f"{name(l)}: UNCHECKED, {r['error']}" for l, r in zip(vl, res_v) if "error" in r]
            if not BV.RULES["rules"]:
                C.append(chk("people", BV.RULES["title"], "skip", f"no people rules set ({os.path.basename(BV.RULES_PATH)})"))
            else:
                C.append(chk("people", BV.RULES["title"], "fail" if ppl or unk else "pass",
                             f"{len(ppl)} shot(s) break the rule, {len(unk)} unchecked, of {len(vl)}", BV.RULES["summary"],
                             ppl[:10] + unk[:6] + okd[:6],
                             BV.RULES["fix"] + " An unchecked shot fails too: rerun once the key / network works, or drop it. "
                             "Only if the user looked and said it's fine: broll_vision.py confirm <clip> --note '<their words>'."
                             if ppl or unk else None))
            got = [(l, r) for l, r in zip(vl, res_v) if r.get("matches")]
            off = [(l, r) for l, r in got if r["matches"] == "no" and not r.get("confirmed")]
            part = [(l, r) for l, r in got if r["matches"] == "partly"]
            if got:
                C.append(chk("match", "B-roll matches its line", "fail" if off else ("warn" if part else "pass"),
                             f"{len(off)} off, {len(part)} partly, of {len(got)} timed shot(s)", "each shot shows what the line under it says",
                             [f"{name(l)} {l['start']:.1f} s, «{r['line'][:70]}»: {r['matches']}. {r.get('why', '')}" for l, r in off + part][:12],
                             "Replace an off shot with one that shows the line, or drop it (fewer B-rolls is the default)." if off else None))
            else:
                C.append(chk("match", "B-roll matches its line", "skip", "no transcript (--words) or no timed video inserts"))
        elif vl:
            C.append(chk("people", "B-roll people rules", "warn", "not run (--no-vision)", "run it before delivery"))
        if profile == "broll-led":
            # one coherent world: the inserts agree in brightness and white balance
            if len(looks) >= 3:
                sdL = float(np.std([x["dL"] for x in looks]))
                sdW = float(np.std([x["dwb"] for x in looks]))
                bad_w = sdL > 14 or sdW > 5
                C.append(chk("world", "One coherent world", "fail" if bad_w else "pass", f"sd L* {sdL:.1f}, sd wb b* {sdW:.1f}", "sd L* <= 14, sd b* <= 5",
                             [f"brightest {max(looks, key=lambda x: x['dL'])['layer']}, darkest {min(looks, key=lambda x: x['dL'])['layer']}"] if bad_w else [],
                             "Conform every clip to the speaker's as-shot footage (insert_prep.py --ref); drop shots from another light." if bad_w else None))
            # pace: median shot vs the reference
            r = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-an", "-vf", "scale=270:-2,scdet=threshold=10:sc_pass=0", "-f", "null", "-"],
                               capture_output=True, text=True)
            cuts = sorted(float(x) for x in re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", r.stderr))
            bnd = [0.0] + [c for c in cuts if 0.05 < c < dur - 0.05] + [dur]
            shots = [bnd[i + 1] - bnd[i] for i in range(len(bnd) - 1)]
            med_shot = float(np.median(shots)) if shots else dur
            st_p = "fail" if not 0.9 <= med_shot <= 2.2 else ("warn" if not 1.1 <= med_shot <= 1.8 else "pass")
            C.append(chk("pace", "Shot pace", st_p, f"median shot {med_shot:.2f} s ({len(cuts)} cuts)", "0.9-2.2 s (reference 1.30 s)", [],
                         "Cut on the spoken words: one shot per 1.2-1.6 s; split long holds." if st_p == "fail" else None))
    # the speaker's face keeps its natural, as-shot colour: no house grade, no filter on the plate.
    # Inserts are conformed TO the speaker (insert_prep.py --ref); a style sets the look of its graphics only.
    plates = [l for l in comp["layers"] if l["kind"] == "plate"] if comp else []
    if comp and comp["layers"]:
        regraded, diffs, seen_src = [], [], set()
        for l in comp["layers"]:            # any clip of the speaker written by house_look.py apply (a plate or a face shot)
            if l["still"] or os.path.realpath(l["src"]) in seen_src:
                continue
            seen_src.add(os.path.realpath(l["src"]))
            j = sidecar_of(l["src"])
            if j.get("style") and j.get("params") and j.get("plate"):
                regraded.append(f"{l['rel']}: graded to the {j['style']} house look (house_look.py apply)")
        for l in plates:
            ks = [k for k, v in sorted(vis.get(l["id"], {}).items()) if v[0] >= 0.95 and spk[min(N - 1, int(round(k * DTM / DT)))]]
            sw, sh = cover_size(l["info"], wm, hm)
            ks = [k for k in ks if boxes[min(N - 1, int(round(k * DTM / DT)))] is not None]
            for k in ks[::max(1, len(ks) // 16)][:16]:
                pf = decode(l["src"], sw, sh, start=l["ms"] + k * DTM - l["start"], dur=0.06)
                if not pf:
                    continue
                cov, A, mask = vis[l["id"]][k]
                k5 = min(N - 1, int(round(k * DTM / DT)))
                warped = cv2.warpAffine(pf[0], A, (wm, hm))
                rf = cv2.resize(F5[k5], (wm, hm), interpolation=cv2.INTER_AREA)
                # the face box only: a caption shade or a vignette at the frame's edges is not a regrade of the face
                bx, by, bw, bh = boxes[k5]
                fm = np.zeros((hm, wm), bool)
                fm[max(0, int(by * hm)):int((by + bh) * hm), max(0, int(bx * wm)):int((bx + bw) * wm)] = True
                er = cv2.erode(mask.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & fm
                a_, b_ = G.region_stats(rf, er), G.region_stats(warped, er)
                if a_ and b_:
                    diffs.append((a_["L"] - b_["L"], a_["wb_b"] - b_["wb_b"], a_["wb_a"] - b_["wb_a"], a_["C"] / max(b_["C"], 1e-6)))
        off = []
        if diffs:
            dL, dB, dA, sR = (float(np.median([d[i] for d in diffs])) for i in range(4))
            if abs(dL) > 5 or abs(dB) > 4 or abs(dA) > 4 or not 0.85 <= sR <= 1.18:
                off.append(f"the speaker's face in the render vs the plate: L* {dL:+.1f}, wb b* {dB:+.1f}, a* {dA:+.1f}, saturation x{sR:.2f} "
                           f"(a CSS filter, an overlay or a grade on the plate)")
            val = f"the speaker's face, render vs plate, over {len(diffs)} frame(s): L* {dL:+.1f}, b* {dB:+.1f}, sat x{sR:.2f}"
        else:
            val = "no full-frame speaker samples to compare"
        C.append(chk("as_shot", "Speaker's face as shot (no regrade)", "fail" if regraded or off else "pass", ("; ".join(regraded) + "; " if regraded else "") + val,
                     "the plate's natural colour; |L*| <= 5, |b*| <= 4, saturation x0.85-1.18 vs the plate", regraded + off,
                     "Use the plate as shot (prep.sh only tone-maps HDR); conform the inserts to it with insert_prep.py --ref. "
                     "A film look (look.film) only when the user asks for it." if regraded or off else None))
    elif style:
        C.append(chk("as_shot", "Speaker's face as shot (no regrade)", "skip", "needs --project (the composition's plate)"))
    # fresh components every reel: a scene / prop / frame / transition / hook / outro from the
    # style's last reels repeats -> warning (scripts/components.py, recipes/<style>/catalog.json)
    if style and project and comp:
        try:
            import components as CP
            r = CP.check(style, project)
            C.append(chk("components", f"Fresh {style} components", "warn" if r["repeats"] else "pass",
                         f"{len(r['repeats'])} repeat(s) from the last {len(r['recent'])} reels, {len(r['fresh'])} fresh",
                         "no scene, prop, frame, transition, hook or outro from the style's recent reels", CP.report(style, r)[:14],
                         "Swap the repeats for unused components (components.py plan --style " + style + "); register new ones "
                         "with components.py add, then components.py record after the user approves." if r["repeats"] else None))
        except (SystemExit, FileNotFoundError) as e:
            C.append(chk("components", f"Fresh {style} components", "skip", str(e)))
    st = "fail" if freezes or src_issues else "warn" if still_warn else "pass"
    C.append(chk("freeze", "Frozen picture", st, f"{len(freezes)} freeze(s), {len(src_issues)} source issue(s), {len(still_ok) + len(still_warn)} still clip(s)",
                 f"none > {FREEZE_MAX} s; no clip past its end; no frozen action",
                 [f"{t:.2f} s: {d:.2f} s frozen ({w})" for t, d, w in freezes][:8] + src_issues[:8] + still_warn[:6] + still_ok[:6],
                 None if st == "pass" else "Never pad a clip past its end (insert_prep.py refuses to); shorten the slot or move the in-point; a stalled "
                 "speaker under stickers needs the plate re-rendered. A photo of someone mid-movement full screen: use a moving clip, or frame the "
                 "photo (card, polaroid). A photo held full screen: give it a slow push (scale 1 -> 1.05).",
                 times=[t for t, _, _ in freezes]))
    hdr = G.is_hdr(info)
    C.append(chk("hdr", "SDR BT.709 output", "fail" if hdr else "pass", f"{info['transfer']}/{info['primaries']}", "bt709",
                 [], "An HDR source switched the render to HDR: run every insert through insert_prep.py (tone-maps HLG/PQ to SDR) and re-render." if hdr else None))
    if comp:
        det, worst_plate, warn_ins = [], 0.0, []
        for l in comp["layers"]:
            if l["kind"] in ("sticker", "backdrop") or l["still"]:
                continue
            r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
                                "-of", "csv=p=0", l["src"]], capture_output=True, text=True)
            kt = sorted(float(x.strip(",")) for x in r.stdout.split() if x.strip(","))
            gap = max(np.diff(kt + [l["info"]["dur"]])) if kt else l["info"]["dur"]
            if l["kind"] == "plate":
                worst_plate = max(worst_plate, gap)
            elif gap > KEYINT_MAX + 1.5 / fps:
                warn_ins.append(f"{l['id']}: {gap:.1f} s")
            det.append(f"{l['id']} ({l['kind']}): keyframe every <= {gap:.2f} s, {l['info']['fps']:g} fps" + (", HDR" if G.is_hdr(l["info"]) else ""))
        vids = [l for l in comp["layers"] if l["kind"] not in ("sticker", "backdrop") and not l["still"]]
        fpsbad = [f"{l['id']} {l['info']['fps']:g} fps" for l in vids if abs(l["info"]["fps"] - comp["fps"]) > 0.05 and abs(l["info"]["fps"] - 2 * comp["fps"]) > 0.1]
        hdrsrc = [l["id"] for l in vids if G.is_hdr(l["info"])]
        st = "fail" if worst_plate > KEYINT_MAX + 1.5 / fps else ("warn" if warn_ins or fpsbad or hdrsrc else "pass")
        C.append(chk("keyframes", "Sources: keyframes, fps, HDR", st, f"plates {worst_plate:.2f} s; {len(warn_ins)} sparse inserts; {len(fpsbad)} off-fps; {len(hdrsrc)} HDR",
                     f"plates <= {KEYINT_MAX:g} s", (["inserts with sparse keyframes: " + ", ".join(warn_ins)] if warn_ins else []) +
                     (["off-fps sources (judder): " + ", ".join(fpsbad)] if fpsbad else []) + (["HDR sources: " + ", ".join(hdrsrc)] if hdrsrc else []) + det[:10],
                     None if st == "pass" else "Re-encode plates with -g 30 (prep.sh does); run inserts through insert_prep.py (1 s keyframes, fps conform, SDR)."))
    cons = [c["contrast"] for c in caps if c["contrast"] is not None]
    metrics = {"duration_s": round(dur, 1), "speaker_pct": pct["S"], "broll_full_pct": pct["B"], "framed_insert_pct": pct["F"], "graphics_pct": pct["G"],
               "plate_noface_pct": pct["P"], "inserts": len(segs), "inserts_per_min": round(ipm, 1),
               "graphics_seg_median_s": round(float(np.median(gseg)), 2) if gseg else None,
               "graphics_animated_pct": round(100 * float(np.mean(gact)), 1) if gact else None,
               "inserts_grade_fail": sum(1 for x in looks if x["fail"]),
               "insert_wb_gap_med": round(float(np.median([x["dwb"] for x in looks])), 1) if looks else None,
               "insert_sat_ratio_med": round(float(np.median([x["sat"] for x in looks])), 2) if looks else None,
               "caption_px_med": int(np.median([c["px"] for c in caps])) if caps else None,
               "caption_contrast_med": round(float(np.median(cons)), 1) if cons else None,
               "face_cover_events": next((int(c["value"].split()[0]) for c in C if c["id"] == "faces" and c["status"] != "skip"), None),
               "face_cover_transitions": next((int(c["value"].split()[2]) for c in C if c["id"] == "faces" and c["status"] != "skip"), None),
               "freezes": len(freezes) + len(src_issues), "hdr": hdr}
    return {"checks": C, "metrics": metrics, "labels": "".join(L), "inserts": segs, "looks": looks, "occlusions": occl, "captions": caps,
            "freezes": freezes, "source_issues": src_issues, "notes": notes, "profile": profile, "render": os.path.abspath(video),
            "project": project and os.path.abspath(project)}


def timeline_png(res, path):
    L = res["labels"]
    col = {"S": (232, 131, 58), "B": (47, 111, 214), "F": (242, 192, 143), "G": (154, 163, 173), "P": (160, 90, 90)}   # BGR (OpenCV)
    Wd, Hd = 1200, 76
    img = np.full((Hd, Wd, 3), 255, np.uint8)
    n = max(1, len(L))
    for k, c in enumerate(L):
        x0, x1 = int(k * Wd / n), int((k + 1) * Wd / n)
        img[10:40, x0:max(x1, x0 + 1)] = col.get(c, (0, 0, 0))
    dur = res["metrics"]["duration_s"] or 1
    for s, e, _, framed in res["inserts"]:
        img[44:50, int(s / dur * Wd):max(int(e / dur * Wd), int(s / dur * Wd) + 2)] = (150, 150, 150) if framed else (40, 40, 40)
    for t, *_ in res["occlusions"]:
        cv2.circle(img, (int(t / dur * Wd), 56), 4, (40, 40, 220), -1)
    for t, *_ in res["freezes"]:
        cv2.circle(img, (int(t / dur * Wd), 56), 4, (220, 40, 160), -1)
    m = res["metrics"]
    cv2.putText(img, f"S {m['speaker_pct']}%  B {m['broll_full_pct']}%  F {m['framed_insert_pct']}%  G {m['graphics_pct']}%  P {m['plate_noface_pct']}%  inserts/min {m['inserts_per_min']}",
                (6, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
    cv2.imwrite(path, img)


def load_words(path, project):
    cands = [path] if path else ([os.path.join(project, "build", n) for n in ("words.cut.json", "words.json", "words.smooth.json")] if project else [])
    for p in cands:
        if p and os.path.exists(p):
            j = json.load(open(p))
            if isinstance(j, dict) and "segments" in j:
                return [{"w": w.get("word", w.get("text", "")).strip(), "s": w["start"], "e": w["end"]} for s in j["segments"] for w in s.get("words", [])]
            if isinstance(j, dict) and "words" in j:
                j = j["words"]
            if isinstance(j, list):
                return [{"w": (w.get("w") or w.get("word") or w.get("text") or "").strip(), "s": w.get("s", w.get("start")), "e": w.get("e", w.get("end"))} for w in j]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--project")
    ap.add_argument("--profile", choices=list(PROFILES), default="talking-head")
    ap.add_argument("--words", help="edit-time words json (whisper segments, or a list of {w|word, s|start, e|end})")
    ap.add_argument("--speaker-ref", help="an image or video of the speaker (default: the plate, else the render's first frames)")
    ap.add_argument("--allow-hold", default="", help="designed holds, e.g. 28.4-29.3,40-41")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--no-match", action="store_true", help="ignore the composition (classifier only)")
    ap.add_argument("--style", help="recipe name (clean-os, seoul-list, stan-style, result-podcast, whiteboard); the speaker's face is checked as shot either way")
    ap.add_argument("--no-vision", action="store_true", help="skip the Gemini people / line-match check (offline); it then warns")
    ap.add_argument("--out")
    a = ap.parse_args()
    words = load_words(a.words, a.project)
    holds = [tuple(float(x) for x in h.split("-")) for h in a.allow_hold.split(",") if h.strip()]
    res = analyse(a.video, a.project, a.profile, words, holds, not a.no_ocr, not a.no_match, a.speaker_ref, style=a.style, use_vision=not a.no_vision)
    out = a.out or (os.path.join(a.project, "build", "broll-qa.json") if a.project else os.path.splitext(a.video)[0] + ".broll-qa.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    timeline_png(res, os.path.splitext(out)[0] + "-timeline.png")
    fails = [c for c in res["checks"] if c["status"] == "fail"]
    for c in res["checks"]:
        print(f"  {c['status'].upper():5s} {c['title']}: {c['value']}")
        if c["status"] in ("fail", "warn"):
            for d in c["details"][:6]:
                print(f"         {d}")
    for nt in res["notes"]:
        print(f"  note: {nt}")
    print(f"\n{'FAIL' if fails else 'PASS'} ({len(fails)} failing) -> {out}")
    print("metrics:", json.dumps(res["metrics"], ensure_ascii=False))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
