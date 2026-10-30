"""Shared grade maths for insert_prep.py (conform) and broll_qa.py (check): the same stats on both sides.

Stats are taken on a small 8-bit BGR frame with OpenCV's Lab (the 2026-10-13 B-roll audit's definitions):
  L      median L* (exposure)
  Lstd   std of L* (contrast)
  C      mean chroma sqrt(a*^2 + b*^2) (the "saturation" the QA compares as a ratio)
  b, a   mean b* / a* (kept for reference: they mix the grade with the content, a blue sea reads "cold")
  wb_b, wb_a  white balance: median b* / a* over the 40 % least chromatic pixels (8 < L* < 97). Sand, clouds, walls and
         skin highlights carry the light's colour; a blue sea or a red wall does not move it. On the audit reels this
         separated mismatched stock (10-18 b* colder than the warm plate) from a well-graded Seoul list (0 b*, 0 of 15
         shots off), where the mean b* failed 3 of its 15 shots.
The conform is a per-pixel transform in CIE Lab (sRGB/D65) baked into a .cube LUT, so ffmpeg applies it in one pass:
  L' = 100 (L/100)^g, then x k around the median     exposure as a gamma (black/white stay), contrast toward the plate
  a', b' = n + (a + da - n_a, b + db - n_b) * s  white point moved onto the plate's, chroma scaled around it
HDR (HLG / PQ, BT.2020) inputs are tone-mapped to SDR BT.709 inside the same LUT (ffmpeg here has no zscale).
"""
import json
import os
import re
import subprocess

import numpy as np

try:
    import cv2
except ImportError:  # the QA venv has it; insert_prep prints a clear error
    cv2 = None

# ------------------------------------------------------------------ thresholds (FINDINGS.md fix list 2 + 4)
WB_MAX = 8.0        # |delta white-balance b*| per insert
L_MAX = 15.0        # |delta median L*| per insert
SAT_LO, SAT_HI = 0.8, 1.2     # chroma ratio insert / plate (reel median; per insert this band is a warning)
SAT_HARD = (0.5, 2.0)         # per insert: outside this the shot is from another world -> fail
NEUTRAL_MAX = 15.0            # median chroma of a shot's "least chromatic 40 %" above this = no neutral areas (all sky and
                              # sea, all reef): its white balance can't be measured (a lagoon read 25 b* "cold" and the
                              # full conform turned the sky magenta); the conform moves it at most WB_SAFE, the QA warns


# ------------------------------------------------------------------ stats
def frame_stats(bgr):
    """grade stats of one 8-bit BGR frame (any size; ~270x480 is plenty). mask: optional bool array (framed insert)"""
    return region_stats(bgr, None)


def region_stats(bgr, mask=None):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0] * 100 / 255
    A = lab[..., 1] - 128
    B = lab[..., 2] - 128
    if mask is not None:
        L, A, B = L[mask], A[mask], B[mask]
    else:
        L, A, B = L.ravel(), A.ravel(), B.ravel()
    if L.size < 50:
        return None
    C = np.hypot(A, B)
    m = (L > 8) & (L < 97)
    if m.sum() > 50:
        thr = np.percentile(C[m], 40)
        n = m & (C <= thr)
    else:
        n = np.ones_like(m)
    return {"L": float(np.median(L)), "Lstd": float(L.std()), "C": float(C.mean()), "a": float(A.mean()), "b": float(B.mean()),
            "wb_a": float(np.median(A[n])), "wb_b": float(np.median(B[n])), "nC": float(np.median(C[n]))}


def median_stats(rows):
    rows = [r for r in rows if r]
    if not rows:
        return None
    return {k: float(np.median([r[k] for r in rows])) for k in rows[0]}


def compare(ins, ref):
    """insert stats vs reference stats -> deltas + flags (fail / warn lists of strings)"""
    d = {"dL": ins["L"] - ref["L"], "dwb": ins["wb_b"] - ref["wb_b"], "dwa": ins["wb_a"] - ref["wb_a"],
         "sat": ins["C"] / max(1e-6, ref["C"]), "contrast": ins["Lstd"] / max(1e-6, ref["Lstd"]), "db_mean": ins["b"] - ref["b"]}
    fail, warn = [], []
    if abs(d["dwb"]) > WB_MAX:
        msg = f"white balance {d['dwb']:+.0f} b* ({'colder' if d['dwb'] < 0 else 'warmer'} than the plate)"
        (warn if ins.get("nC", 0) > NEUTRAL_MAX else fail).append(msg + (" [no neutral areas in the shot: not measurable]" if ins.get("nC", 0) > NEUTRAL_MAX else ""))
    if abs(d["dL"]) > L_MAX:
        fail.append(f"exposure {d['dL']:+.0f} L*")
    if not (SAT_HARD[0] <= d["sat"] <= SAT_HARD[1]):
        fail.append(f"saturation x{d['sat']:.2f}")
    elif not (SAT_LO <= d["sat"] <= SAT_HI):
        warn.append(f"saturation x{d['sat']:.2f}")
    return {k: round(v, 2) for k, v in d.items()}, fail, warn


# ------------------------------------------------------------------ colour science (numpy, float in [0, 1])
_M_RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
_M_XYZ2RGB = np.linalg.inv(_M_RGB2XYZ)
_WHITE = np.array([0.95047, 1.0, 1.08883])
_M_2020_709 = np.array([[1.660491, -0.587641, -0.072850], [-0.124550, 1.132900, -0.008349], [-0.018151, -0.100579, 1.118730]])


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, None)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def rgb_to_lab(rgb):
    xyz = srgb_to_lin(rgb) @ _M_RGB2XYZ.T / _WHITE
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab_to_rgb(lab):
    fy = (lab[..., 0] + 16) / 116
    fx = fy + lab[..., 1] / 500
    fz = fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 216 / 24389, f ** 3, (116 * f - 16) / (24389 / 27)) * _WHITE
    return np.clip(lin_to_srgb(xyz @ _M_XYZ2RGB.T), 0, 1)


def _tonemap(rgb_rel):
    """display-relative linear BT.709 (1.0 = SDR reference white) -> [0, 1]: soft shoulder on luminance above 0.8"""
    Y = rgb_rel @ np.array([0.2126, 0.7152, 0.0722])
    k = 0.8
    Yt = np.where(Y <= k, Y, k + (1 - k) * (1 - np.exp(-(Y - k) / (1 - k))))
    scale = np.where(Y > 1e-6, Yt / np.maximum(Y, 1e-6), 1.0)
    out = rgb_rel * scale[..., None]
    return np.clip(out, 0, 1)


def hdr_to_sdr(rgb, transfer):
    """BT.2020 R'G'B' (HLG 'arib-std-b67' or PQ 'smpte2084') in [0, 1] -> SDR BT.709 R'G'B' (gamma 2.4) in [0, 1]"""
    e = np.clip(rgb, 0, 1)
    if transfer == "arib-std-b67":
        a, b, c = 0.17883277, 0.28466892, 0.55991073
        E = np.where(e <= 0.5, e * e / 3, (np.exp((e - c) / a) + b) / 12)       # scene linear [0, 1]
        Ys = E @ np.array([0.2627, 0.6780, 0.0593])
        nits = 1000.0 * np.power(np.maximum(Ys, 1e-9), 0.2)[..., None] * E    # OOTF, 1000-nit display, gamma 1.2
    elif transfer == "smpte2084":
        m1, m2, c1, c2, c3 = 0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875
        p = np.power(e, 1 / m2)
        nits = 10000.0 * np.power(np.maximum(p - c1, 0) / (c2 - c3 * p), 1 / m1)
    else:
        return e
    lin709 = (nits / 203.0) @ _M_2020_709.T                                    # 203 nits = SDR reference white
    return np.power(_tonemap(lin709), 1 / 2.4)


# ------------------------------------------------------------------ the conform transform
IDENT = {"g": 1.0, "k": 1.0, "da": 0.0, "db": 0.0, "s": 1.0, "Lmed": 50.0, "na": 0.0, "nb": 0.0}
TOL = {"L": 7.0, "wb": 2.5, "sat": (0.9, 1.1)}      # the solver moves a stat just inside these bands, not onto the plate
WB_SAFE = 8.0                                       # max white-balance move for a shot with no neutral areas


def apply_lab(rgb, p):
    lab = rgb_to_lab(rgb)
    L1 = 100 * np.power(np.clip(lab[..., 0], 0, 100) / 100, p["g"])          # exposure as a gamma: black and white stay put
    Lt = 100 * (max(p["Lmed"], 0.5) / 100) ** p["g"]
    L = (L1 - Lt) * p["k"] + Lt                                                 # contrast around the new median
    a = p["na"] + (lab[..., 1] + p["da"] - p["na"]) * p["s"]
    b = p["nb"] + (lab[..., 2] + p["db"] - p["nb"]) * p["s"]
    return lab_to_rgb(np.stack([np.clip(L, 0, 100), a, b], -1))


def transform(rgb, p, transfer=None):
    if transfer in ("arib-std-b67", "smpte2084"):
        rgb = hdr_to_sdr(rgb, transfer)
    return apply_lab(rgb, p)


def _bgr8(rgb):
    return (np.clip(rgb, 0, 1)[..., ::-1] * 255 + 0.5).astype(np.uint8)


def _band(v, lo, hi):
    return min(max(v, lo), hi)


def solve(frames_rgb, ref, strength=1.0, transfer=None, iters=8, g_range=(0.45, 2.2), wb_clamp=40.0, s_range=(0.55, 1.8), k_range=(0.8, 1.25),
          sat_target=None, neutral_guard=True):
    """frames_rgb: insert frames (float RGB [0,1], HDR-encoded if transfer) -> params p so transform() lands inside the
    QA bands around ref (TOL), changing the shot as little as that needs"""
    base = [hdr_to_sdr(f, transfer) if transfer in ("arib-std-b67", "smpte2084") else f for f in frames_rgb]
    st0 = median_stats([frame_stats(_bgr8(f)) for f in base])
    tL = _band(st0["L"], ref["L"] - TOL["L"], ref["L"] + TOL["L"])
    twa = _band(st0["wb_a"], ref["wb_a"] - TOL["wb"], ref["wb_a"] + TOL["wb"])
    twb = _band(st0["wb_b"], ref["wb_b"] - TOL["wb"], ref["wb_b"] + TOL["wb"])
    tC = ref["C"] * (sat_target if sat_target else _band(st0["C"] / max(ref["C"], 1e-6), *TOL["sat"]))
    if neutral_guard and st0.get("nC", 0) > NEUTRAL_MAX:   # no neutral areas: a gentle warm/cool shift only, no tint, no extra saturation
        # (off for a speaker plate: a strong tungsten cast also makes every pixel chromatic, and there the cast IS the light)
        twa = st0["wb_a"]                       # (a magenta push on a blue sky turns it violet)
        twb = _band(twb, st0["wb_b"] - WB_SAFE, st0["wb_b"] + WB_SAFE)
        tC = min(tC, st0["C"])
    p = dict(IDENT)
    p["Lmed"] = st0["L"]
    p["na"], p["nb"] = twa, twb
    p["k"] = float(np.clip((ref["Lstd"] / max(st0["Lstd"], 1e-6)) ** 0.5, *k_range))   # half-way toward the plate's contrast
    if 1 < st0["L"] < 99 and 1 < tL < 99:
        p["g"] = float(np.clip(np.log(tL / 100) / np.log(st0["L"] / 100), *g_range))
    p["da"] = float(np.clip(twa - st0["wb_a"], -wb_clamp, wb_clamp))
    p["db"] = float(np.clip(twb - st0["wb_b"], -wb_clamp, wb_clamp))
    p["s"] = float(np.clip(tC / max(st0["C"], 1e-6), *s_range))
    for _ in range(iters):
        m = median_stats([frame_stats(_bgr8(apply_lab(f, p))) for f in base])
        if 1 < m["L"] < 99 and 1 < tL < 99:
            p["g"] = float(np.clip(p["g"] * np.log(tL / 100) / np.log(m["L"] / 100), *g_range))
        p["da"] = float(np.clip(p["da"] + (twa - m["wb_a"]), -wb_clamp, wb_clamp))
        p["db"] = float(np.clip(p["db"] + (twb - m["wb_b"]), -wb_clamp, wb_clamp))
        p["s"] = float(np.clip(p["s"] * tC / max(m["C"], 1e-6), *s_range))
    if strength != 1.0:
        for key in ("da", "db"):
            p[key] *= strength
        for key in ("g", "k", "s"):
            p[key] = 1 + (p[key] - 1) * strength
    after = median_stats([frame_stats(_bgr8(apply_lab(f, p))) for f in base])
    return p, st0, after


def write_cube(path, p, transfer=None, n=None):
    n = n or (65 if transfer in ("arib-std-b67", "smpte2084") else 33)
    g = np.linspace(0, 1, n)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")          # .cube order: R fastest, then G, then B
    rgb = np.stack([r, gg, b], -1).reshape(-1, 3)
    out = transform(rgb, p, transfer)
    with open(path, "w") as f:
        f.write(f"TITLE \"ghost-editor conform\"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
        np.savetxt(f, out, fmt="%.6f")
    return path


# ------------------------------------------------------------------ media helpers
def probe(path):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate,avg_frame_rate,color_transfer,color_primaries,color_space,pix_fmt,codec_name"
                                   ":stream_side_data=rotation,side_data_type,crop_left,crop_right,crop_top,crop_bottom:format=duration",
                                   "-of", "json", path],
                                  capture_output=True, text=True, check=True).stdout)
    s = j["streams"][0]
    n, d = s.get("avg_frame_rate", "0/1").split("/")
    fps = float(n) / float(d) if float(d) and float(n) else 0.0
    if not fps:
        n, d = s["r_frame_rate"].split("/")
        fps = float(n) / float(d)
    rot, crop = 0, (0, 0, 0, 0)
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
        if sd.get("side_data_type") == "Frame Cropping":
            crop = tuple(int(sd.get(k, 0) or 0) for k in ("crop_left", "crop_right", "crop_top", "crop_bottom"))
    return {"w": int(s["width"]), "h": int(s["height"]), "fps": fps, "dur": float(j["format"].get("duration", 0) or 0),
            "transfer": s.get("color_transfer"), "primaries": s.get("color_primaries"), "space": s.get("color_space"),
            "pix_fmt": s.get("pix_fmt"), "codec": s.get("codec_name"), "rotation": rot, "frame_crop": crop}


def shown_size(info):
    """(w, h) as ffmpeg decodes it. w/h from ffprobe are the STORED size; ffmpeg first cuts off the container crop
    (frame_crop, the clap box: iPhone Live Photo .movs store 1920x1440 and crop 88/66 px), then turns files stored
    landscape with a rotation flag upright: Live Photo 1920x1440 rotation -90 decodes 1308x1744."""
    l, r, t, b = info.get("frame_crop") or (0, 0, 0, 0)
    w, h = info["w"] - l - r, info["h"] - t - b
    return (h, w) if info.get("rotation") in (90, -90, 270, -270) else (w, h)


def decoded_size(path, t=0.0):
    """(w, h) of one frame ffmpeg actually decodes at t (rotation and container crop applied), or None when none
    decodes: the ground truth for crop maths, whatever this ffmpeg build does with side data"""
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", path, "-frames:v", "1", "-an",
                        "-pix_fmt", "gray", "-c:v", "pgm", "-f", "image2pipe", "-"], capture_output=True).stdout
    m = re.match(rb"P5\s+(\d+)\s+(\d+)\s", b)
    return (int(m.group(1)), int(m.group(2))) if m else None


def fit(info, short=360):
    """an even decode size with the short side = short, upright"""
    w, h = shown_size(info)
    return (short, int(short * h / w) // 2 * 2) if h >= w else (int(short * w / h) // 2 * 2, short)


def is_hdr(info):
    return info.get("transfer") in ("arib-std-b67", "smpte2084") or info.get("primaries") == "bt2020"


SCALE_FLAGS = "accurate_rnd+full_chroma_int"
STILL_EXT = lambda p: os.path.splitext(p)[1].lower() in (".jpg", ".jpeg", ".png", ".webp")

OWN_ROOTS = [os.path.expanduser(r) for r in ("~/Pictures/Photos Library.photoslibrary", "~/Movies",
                                             "~/Library/CloudStorage")]


def guess_kind(path):
    """where an insert comes from: own (your libraries, camera file names) | ai | stock (Pexels/Mixkit/...) | unknown"""
    import re
    p, base = os.path.abspath(path).lower(), os.path.basename(path).lower()
    if re.search(r"(pexels|mixkit|pixabay|shutterstock|storyblocks|envato|artgrid|/stock/|/broll_dl/)", p) or re.match(r"p\d{5,}", base):
        return "stock"
    if re.search(r"(broll_gen|/ai/|ai[_-]|_ai\.|gemini|minimax|runpod)", p):
        return "ai"
    if any(p.startswith(r.lower()) for r in OWN_ROOTS) or re.match(r"(gx\d|gh\d|gopr|dji_|img_\d|vid_\d|pxl_)", base):
        return "own"
    return "unknown"   # side-session finding 2026-10-12: swscale's default yuv->rgb is 1-2 levels dark


def sample_frames(path, times, w=270, h=480, rgb48=False, crop=None, transfer=None):
    """frames at the given source times (float RGB [0,1]; HDR stays HDR-encoded, so pass it through transform())"""
    out = []
    info = probe(path)
    matrix = ":in_color_matrix=bt2020" if is_hdr(info) else ""
    for t in times:
        vf = (f"{crop}," if crop else "") + f"scale={w}:{h}:flags=area+{SCALE_FLAGS}{matrix}"
        cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", path, "-frames:v", "1", "-vf", vf + ",format=rgb48le",
               "-f", "rawvideo", "-"]
        b = subprocess.run(cmd, capture_output=True).stdout
        if len(b) == w * h * 6:
            out.append(np.frombuffer(b, np.uint16).reshape(h, w, 3).astype(np.float32) / 65535.0)
    return out


def plate_stats(path, n=12, cache=True):
    """reference stats of a speaker plate: n frames spread over it, cached next to the file"""
    side = path + ".gradestats.json"
    key = f"{os.path.getsize(path)}:{os.path.getmtime(path):.0f}"
    if cache and os.path.exists(side):
        j = json.load(open(side))
        if j.get("key") == key:
            return j["stats"]
    info = probe(path)
    ts = [info["dur"] * (i + 0.5) / n for i in range(n)]
    fr = sample_frames(path, ts)
    tr = info["transfer"] if is_hdr(info) else None
    st = median_stats([frame_stats(_bgr8(hdr_to_sdr(f, tr) if tr else f)) for f in fr])
    if cache:
        try:
            json.dump({"key": key, "stats": st}, open(side, "w"))
        except OSError:
            pass
    return st


def sdr_vf(src, cube):
    """ffmpeg filter prefix that tone-maps an HDR (HLG/PQ BT.2020) source to SDR BT.709 RGB->YUV through a LUT; '' for SDR"""
    info = probe(src)
    tr = info["transfer"] if info["transfer"] in ("arib-std-b67", "smpte2084") else None
    if not tr:
        return ""
    write_cube(cube, dict(IDENT), tr)
    return (f"scale=in_color_matrix=bt2020:flags={SCALE_FLAGS},format=rgb48le,lut3d=file={cube}:interp=tetrahedral,"
            f"scale=out_color_matrix=bt709:out_range=tv:flags={SCALE_FLAGS},format=yuv420p,"
            f"setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv")   # frame tags win over -color_trc


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "sdr-vf":
        # prep.sh / proxy.sh: print the HDR -> SDR filter prefix for SRC (empty for an SDR source), writing the LUT to CUBE
        print(sdr_vf(sys.argv[2], sys.argv[3]))
    elif len(sys.argv) == 3 and sys.argv[1] == "plate-stats":
        print(json.dumps(plate_stats(sys.argv[2]), indent=1))
    else:
        sys.exit("usage: grade_lib.py sdr-vf SRC OUT.cube | grade_lib.py plate-stats PLATE.mp4")
