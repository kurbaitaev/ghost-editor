"""Halftone Dossier: a talking-head reel read out as a retro print case file on its subject. Cream archive paper,
overprinted halftone dots in four flat inks, heavy black-serif headlines with a misregistered shadow that pop in glyph by
glyph, rubber stamps that slam, thick-outlined drawn exhibits (with line boil), a case-file HUD and a caption bar that
carries every spoken word. The speaker's face, as shot, sits between the pages: on the speaker's face only the HUD, the caption bar under
the speaker's chin, headlines BEHIND the speaker's head (matte) and a stamp below the speaker's face. Adapted from LemoLab's MIT-licensed style
"Halftone Dossier" (github.com/lemomo-ai/lemo-opuscar, styles/halftone-dossier; see CREDITS.txt).

    import sys; sys.path.insert(0, "<skill>/recipes/halftone-dossier"); from dossier import *
    # an example reel (a case file on the 2 a.m. scroll); times are word onsets in build/words.cut.json
    D = Dossier("$P", dur=31.97, title="Late Scroll Halftone Dossier", case="CASE NO. 001 · THE 2 A.M. SCROLL",
                date="2026.10", lang="en")                    # words: $P/build/words.cut.json (edit s); fixes={i: "Name"} = display fixes
    D.captions([0, 2, 5, 8, ...], keys=[1, 12, ...])          # chunk starts (word indices) + keyword words (yellow)
    D.face("F0", 0.00, 2.70, hud=False)                       # the speaker's plate as shot (alt cut), nothing on the speaker's face
    D.behind("SCROLLING", 0.0, 2.70, y=640, size=124)         # a headline BEHIND the speaker's head (needs the matte at that time)
    D.card("C1", 2.70, 4.48)                                  # open a paper page (dot wipe in/out is set by wipes())
    D.ht("C1", color=D.C["blue"], field=("radial", 540, 1010, 560, 1.0), step=24, angle=45)   # a halftone dot layer
    D.headline("C1", "SUSPECT", 2.80, y=470)                  # black serif, misregistered shadow, glyph pop
    D.mugshot("C1", t_in=2.75, flash=3.86, plate_name="PHONE", plate_sub="CASE NO. 001")   # height chart, the phone suspect, plate, flash
    D.stamp("C4", "OFF.", 12.00, x=540, y=1000, rot=-10)      # rubber stamp slam + shake (on a card) / no shake on the speaker's face
    D.chips([(2.70, "PROFILE"), ...]); D.wipes([(2.70, "navy"), ...]); D.sfx("impact-2", 12.0, 0.6); D.build()

The worlds: face(), card() (+ the generators below), each card a <section> clip; wipes() decide the joins: a dot wipe
grows over the outgoing PAGE and shrinks off the incoming PAGE; a cut that touches the speaker's face only gets the page half (no
dot ever crosses the speaker's face), a page-to-page cut gets the full wipe or "hard".
Card generators (each draws one exhibit, all flat inks + 7 px navy outline, drawn props boil at 10 fps by swapping three
jittered copies; no SVG filters): mugshot(), photo_exhibit(), notifications(), board(), task_verdict(), space_grid().
Primitives for new scenes: ht() (halftone PNG layer), numeral() (giant halftone-filled numeral), headline(), text(),
svg() (raw SVG, boil=True for props), stamp(), shake(), flash(), pop(), rise().
Motion: one paused GSAP timeline; everything enters with overshoot (back.out 1.9); glyph pop with squash; stamp 0.09 s
2.6x -> 1x, damped bounce, quadratic-decay shake; flash <= 0.5; grain re-seeded every 2 frames on pages only.

Needs in $P: assets/alt.mp4 (or any plate) + its matte webm (alpha) for behind(); assets/voice.wav; build/words.cut.json;
pictures the speaker names (e.g. assets/cover.jpg). Fonts (Playfair Display, Unbounded, JetBrains Mono, Inter: Cyrillic + Latin, OFL)
and SFX are copied from the skill; paper, grain, stamp-ink mask and halftone layers are generated into assets/gen/.
"""
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
HOUSE = json.load(open(os.path.join(HERE, "house.json"), encoding="utf-8"))
C = HOUSE["palette"]
TY = HOUSE["type"]
FPS = 30
F1 = 1 / FPS
SFXM = json.load(open(f"{SKILL}/library/sfx/manifest.json"))


def fr(t):
    return round(round(t * FPS) / FPS, 4)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def est_w(s, size, fam):
    """rough advance width (the woff2s cannot be measured here without brotli); errs wide; check on the snapshot"""
    em = {"serif": 0.80, "display": 0.95, "mono": 0.60, "sans": 0.64}[fam]
    caps = sum(1 for c in s if c.isupper())
    return size * sum((em * (1.0 if c.isupper() or not c.isalpha() else 0.86)) if c != " " else 0.3 for c in s) + 0 * caps


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


# ---------------------------------------------------------------- generated print materials (PIL + numpy, seeded)
def gen_paper(path, w=1080, h=1920, seed=3):
    """STYLE 2 'paper layer': upscaled random tile (mottling) + per-pixel noise with a warm bias + radial vignette + a
    faint centre fold; used with mix-blend-mode multiply over a page (never over the speaker's face)"""
    import numpy as np
    from PIL import Image
    if os.path.exists(path):
        return
    rng = np.random.default_rng(seed)
    tile = Image.fromarray((242 + rng.random((h // 20, w // 20)) * 13).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    base = np.array(tile).astype(np.float32)
    rgb = np.stack([base, base, base], -1) + rng.normal(0, 6.5, (h, w, 1))
    rgb[..., 2] -= 4                                            # warmth
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / 1.414
    vig = 1 - 0.30 * np.clip(d - 0.25, 0, 1) ** 1.4
    rgb *= vig[..., None]
    rgb[h // 2 - 1:h // 2 + 2, :, :] *= 0.965                  # the fold (horizontal on a portrait page)
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(path)


def gen_grain(path, w=1200, h=2040, seed=5):
    """STYLE 2 'grain layer': paper-coloured specks + fewer ink specks (dust on the print), moved every 2 frames"""
    from PIL import Image, ImageDraw
    if os.path.exists(path):
        return
    r = random.Random(seed)
    im = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(1300):
        x, y, s = r.uniform(0, w * 2), r.uniform(0, h * 2), r.uniform(1.2, 4.8)
        col = (*hexrgb(C["cream"]), 190) if i < 1100 else (*hexrgb(C["navy"]), 150)
        d.ellipse((x - s, y - s, x + s, y + s), fill=col)
    im.resize((w, h), Image.LANCZOS).save(path)


def gen_inkmask(path, w=1100, h=420, seed=11):
    """stamp ink: a coarse mottled alpha mask with holes (replaces the source's feTurbulence #stampInk filter, which
    HyperFrames 0.8.159 cannot take: an SVG filter blacks out other clips)"""
    import numpy as np
    from PIL import Image
    if os.path.exists(path):
        return
    rng = np.random.default_rng(seed)
    lo = np.array(Image.fromarray((rng.random((h // 14, w // 14)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)).astype(np.float32)
    hi = rng.random((h, w)) * 255
    v = 0.72 * lo + 0.28 * hi
    a = np.clip((v - 42) * 5.0, 0, 255)
    a = np.where(rng.random((h, w)) < 0.015, 0, a)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = a.astype(np.uint8)
    Image.fromarray(rgba).save(path)


def field_fn(spec):
    """density fields from the source engine: radial(cx, cy, R, pw), edge(R, pw) around the frame centre, linear
    (y0, y1, a, b) for 'lit from above' ramps, const(v)"""
    import numpy as np
    k = spec[0]
    if k == "radial":
        _, cx, cy, R, pw = spec
        return lambda x, y: np.clip(1 - np.hypot(x - cx, y - cy) / R, 0, 1) ** pw
    if k == "edge":
        _, R, pw = spec[:3]
        cx, cy = (spec[3], spec[4]) if len(spec) > 3 else (540, 960)
        return lambda x, y: np.clip(np.clip(np.hypot(x - cx, y - cy) / R - 0.35, 0, 1) ** pw * 1.3, 0, 1)
    if k == "linear":
        _, y0, y1, a, b = spec
        return lambda x, y: np.clip(a + (b - a) * np.clip((y - y0) / (y1 - y0), 0, 1), 0, 1)
    if k == "const":
        return lambda x, y: np.full_like(x, spec[1], dtype=float)
    raise ValueError(spec)


def gen_halftone(path, w, h, step, angle, color, field, maxk=0.66, ss=3):
    """STYLE 2 'halftone': a rotated grid of circles, radius = density x step x maxk (about 0.7 merges into solid ink),
    rendered supersampled to a transparent PNG in one ink"""
    import numpy as np
    from PIL import Image, ImageDraw
    if os.path.exists(path):
        return
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    n = int(math.hypot(w, h) / step / 2) + 2
    I, J = np.meshgrid(np.arange(-n, n + 1), np.arange(-n, n + 1))
    u, v = I.ravel() * step, J.ravel() * step
    x = w / 2 + u * ca - v * sa
    y = h / 2 + u * sa + v * ca
    keep = (x > -step) & (x < w + step) & (y > -step) & (y < h + step)
    x, y = x[keep], y[keep]
    s = np.clip(field_fn(field)(x, y), 0, 1)
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    for xi, yi, si in zip(x, y, s):
        if si < 0.05:
            continue
        r = si * step * maxk * ss
        d.ellipse((xi * ss - r, yi * ss - r, xi * ss + r, yi * ss + r), fill=255)
    m = im.resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (*hexrgb(color), 0))
    out.putalpha(m)
    out.save(path)


# ---------------------------------------------------------------- drawn props (flat fill + navy outline, jittered = boil)
class Pen:
    """SVG for drawn props; j = jitter amplitude in px (each boil copy gets its own seed)"""
    def __init__(self, seed, j=2.4):
        self.r = random.Random(seed)
        self.j = j

    def q(self, v):
        return v + self.r.uniform(-self.j, self.j)

    def style(self, fill, sw=7, stroke=None):
        return f'fill="{fill}" stroke="{stroke or C["navy"]}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"'

    def rrect(self, x, y, w, h, r, fill, sw=7, stroke=None, extra=""):
        q = self.q
        pts = [(x + r, y), (x + w - r, y), (x + w, y + r), (x + w, y + h - r), (x + w - r, y + h), (x + r, y + h), (x, y + h - r), (x, y + r)]
        p = [(q(a), q(b)) for a, b in pts]
        d = (f"M{p[0][0]:.1f} {p[0][1]:.1f}L{p[1][0]:.1f} {p[1][1]:.1f}Q{x + w:.1f} {y:.1f} {p[2][0]:.1f} {p[2][1]:.1f}"
             f"L{p[3][0]:.1f} {p[3][1]:.1f}Q{x + w:.1f} {y + h:.1f} {p[4][0]:.1f} {p[4][1]:.1f}L{p[5][0]:.1f} {p[5][1]:.1f}"
             f"Q{x:.1f} {y + h:.1f} {p[6][0]:.1f} {p[6][1]:.1f}L{p[7][0]:.1f} {p[7][1]:.1f}Q{x:.1f} {y:.1f} {p[0][0]:.1f} {p[0][1]:.1f}Z")
        return f'<path d="{d}" {self.style(fill, sw, stroke)} {extra}/>'

    def ell(self, cx, cy, rx, ry, fill, sw=7, stroke=None, extra=""):
        return (f'<ellipse cx="{self.q(cx):.1f}" cy="{self.q(cy):.1f}" rx="{rx + self.r.uniform(-self.j, self.j) * 0.6:.1f}" '
                f'ry="{ry + self.r.uniform(-self.j, self.j) * 0.6:.1f}" {self.style(fill, sw, stroke)} {extra}/>')

    def poly(self, pts, fill, sw=7, closed=True, stroke=None, extra=""):
        p = " ".join(f"{self.q(a):.1f},{self.q(b):.1f}" for a, b in pts)
        tag = "polygon" if closed else "polyline"
        return f'<{tag} points="{p}" {self.style(fill if closed else "none", sw, stroke)} {extra}/>'

    def path(self, d, fill, sw=7, stroke=None):
        """free path; boil by a tiny translate / rotate of the whole shape"""
        tx, ty, rot = self.q(0), self.q(0), self.r.uniform(-0.6, 0.6)
        return f'<path transform="translate({tx:.1f} {ty:.1f}) rotate({rot:.2f})" d="{d}" {self.style(fill, sw, stroke)}/>'


def heart_d(cx, cy, s):
    """heart outline (the source engine's heartPath, re-centred)"""
    P = lambda a, b: f"{cx + a * s:.1f} {cy + b * s:.1f}"
    return f"M{P(0, 30)}C{P(-40, 0)} {P(-50, -30)} {P(-25, -45)}C{P(-10, -52)} {P(0, -40)} {P(0, -30)}C{P(0, -40)} {P(10, -52)} {P(25, -45)}C{P(50, -30)} {P(40, 0)} {P(0, 30)}Z"


def moon_d(cx, cy, r):
    return (f"M{cx + r * 0.35:.1f} {cy - r:.1f}A{r:.1f} {r:.1f} 0 1 0 {cx + r * 0.35:.1f} {cy + r:.1f}"
            f"A{r * 0.78:.1f} {r * 0.78:.1f} 0 1 1 {cx + r * 0.35:.1f} {cy - r:.1f}Z")


def envelope(p, x, y, w, h, fill):
    return p.rrect(x, y, w, h, 8, fill, 6) + p.poly([(x + 6, y + 8), (x + w / 2, y + h * 0.58), (x + w - 6, y + 8)], "none", 6, closed=False)


def bubble(p, x, y, w, h, fill):
    return p.rrect(x, y, w, h * 0.78, 18, fill, 6) + p.poly([(x + w * 0.22, y + h * 0.76), (x + w * 0.16, y + h), (x + w * 0.44, y + h * 0.76)], fill, 6)


def dumbbell(p, cx, cy, s, fill):
    return (p.rrect(cx - 70 * s, cy - 10 * s, 140 * s, 20 * s, 8 * s, C["cream"], 6) +
            p.rrect(cx - 92 * s, cy - 42 * s, 34 * s, 84 * s, 10 * s, fill, 6) + p.rrect(cx + 58 * s, cy - 42 * s, 34 * s, 84 * s, 10 * s, fill, 6) +
            p.rrect(cx - 116 * s, cy - 28 * s, 26 * s, 56 * s, 8 * s, fill, 6) + p.rrect(cx + 90 * s, cy - 28 * s, 26 * s, 56 * s, 8 * s, fill, 6))


def eyes(p, cx, cy, gap, rx, ry, gid):
    """glossy eyes (ink ellipse + two highlights) in a group that can blink / squint (scaleY)"""
    out = [f'<g id="{gid}">']
    for ex in (cx - gap / 2, cx + gap / 2):
        out.append(p.ell(ex, cy, rx, ry, C["navy"], 0))
        out.append(f'<circle cx="{ex - rx * 0.32:.1f}" cy="{cy - ry * 0.35:.1f}" r="{rx * 0.34:.1f}" fill="{C["cream"]}"/>')
        out.append(f'<circle cx="{ex + rx * 0.3:.1f}" cy="{cy + ry * 0.3:.1f}" r="{rx * 0.15:.1f}" fill="{C["cream"]}"/>')
    out.append("</g>")
    return "".join(out)


# ---------------------------------------------------------------- the dossier
class Dossier:
    C = C

    def __init__(self, project, dur, title, case, date, plate=("assets/alt.mp4", "assets/alt_matte.webm"),
                 words="build/words.cut.json", voice="assets/voice.wav", fixes=None, lang="ru"):
        self.P = os.path.abspath(os.path.expanduser(project))
        self.dur, self.page_title, self.case, self.date, self.lang = dur, title, case, date, lang
        d = json.load(open(f"{self.P}/{words}", encoding="utf-8"))
        raw = [w for s in d["segments"] for w in s["words"]] if "segments" in d else d["words"]
        self.W = [(w["word"].strip(), w["start"], w["end"]) for w in raw]
        for i, s in (fixes or {}).items():                  # display fixes (a misheard name), never new words
            self.W[i] = (re.sub(r"[\w-]+", s, self.W[i][0], count=1), self.W[i][1], self.W[i][2])
        self.plate, self.voice = plate, voice
        self.voice_dur = round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                                     f"{self.P}/{voice}"], capture_output=True, text=True).stdout), 2)
        os.makedirs(f"{self.P}/assets/gen", exist_ok=True)
        os.makedirs(f"{self.P}/build", exist_ok=True)
        self._fonts()
        gen_paper(f"{self.P}/assets/gen/paper.png")
        gen_grain(f"{self.P}/assets/gen/grain.png")
        gen_inkmask(f"{self.P}/assets/gen/ink.png")
        self.cards = {}                                     # name -> dict(t0, t1, dark, html list)
        self.order = []
        self.FACES, self.BEHIND, self.FRONT, self.JS, self.SFX, self.BEATS = [], [], [], [], [], []
        self.caps_html, self.chips_ = [], []
        self._id = 0
        self.hud_hidden = []
        self.wipes_ = []

    # ------------------------------------------------------------ basics
    def _fonts(self):
        os.makedirs(f"{self.P}/assets/fonts", exist_ok=True)
        for _, stem, _, _ in TY["font_faces"]:
            for sub in ("cyrillic", "latin"):
                dst = f"{self.P}/assets/fonts/{stem}-{sub}.woff2"
                if not os.path.exists(dst):
                    shutil.copy(f"{SKILL}/templates/fonts/{stem}-{sub}.woff2", dst)

    def nid(self, p="e"):
        self._id += 1
        return f"{p}{self._id}"

    def tset(self, sel, props, t):
        self.JS.append(f'tl.set("{sel}", {json.dumps(props)}, {fr(t):.4f});')

    def tween(self, sel, frm, to, t):
        self.JS.append(f'tl.fromTo("{sel}", {json.dumps(frm)}, {json.dumps({**to, "immediateRender": False})}, {fr(t):.4f});')

    def beat(self, bid, t0, t1, keys):
        self.BEATS.append({"id": bid, "type": "beat", "label": bid, "t0": round(t0, 3), "t1": round(t1, 3),
                           "keys": sorted(round(k, 3) for k in keys)})

    def word_t(self, i):
        return self.W[i][1]

    def sfx(self, name, t, vol, dur=None):
        """a library sound where something enters (never on caption swaps); names from library/sfx/manifest.json"""
        m = SFXM[name]
        assert m.get("licensed", True), f"{name} is not licensed for a port"
        os.makedirs(f"{self.P}/assets/sfx", exist_ok=True)
        dst = f"{self.P}/assets/sfx/{m['file']}"
        if not os.path.exists(dst):
            shutil.copy(f"{SKILL}/library/sfx/{m['file']}", dst)
        self.SFX.append((m["file"], max(0.0, t), vol, dur or m["duration"]))

    # ------------------------------------------------------------ worlds
    def face(self, name, t0, t1, hud=True):
        """the speaker's plate as shot between the pages: no grade, no effect; only the HUD (top corners), the caption bar (under the
        chin), behind() headlines and a face_stamp() below the speaker's face"""
        self.FACES.append((name, t0, t1))
        if not hud:
            self.hud_hidden.append((t0, t1))
        self.beat(name, t0, t1, [t0 + 0.1, (t0 + t1) / 2])

    def card(self, name, t0, t1, bg=None, dark=False):
        """a paper page (a <section> clip): bg ink, paper multiply + grain on top, its own camera group for shakes"""
        bg = bg or (C["night"] if dark else C["paper"])
        self.cards[name] = {"t0": t0, "t1": t1, "dark": dark, "bg": bg, "h": [], "boil": False}
        self.order.append(name)
        self.beat(name, t0, t1, [t0 + 0.1, t1 - 0.1])
        return name

    def add(self, name, html):
        self.cards[name]["h"].append(html)

    def keys(self, name, *ts):
        for b in self.BEATS:
            if b["id"] == name:
                b["keys"] = sorted(set(b["keys"] + [round(t, 3) for t in ts]))

    # ------------------------------------------------------------ primitives
    def ht(self, name, color, field, step=24, angle=15, maxk=0.66, mul=True, box=(0, 0, 1080, 1920), extra=""):
        """a halftone dot layer (PNG in one ink); mul=True overprints (multiply). step >= 20 px (finer aliases into moire)"""
        x, y, w, h = box
        key = hashlib.md5(json.dumps([w, h, step, angle, color, field, maxk]).encode()).hexdigest()[:10]
        fn = f"assets/gen/ht_{key}.png"
        gen_halftone(f"{self.P}/{fn}", w, h, step, angle, color, field, maxk)
        bl = "mix-blend-mode:multiply;" if mul else ""
        eid = self.nid("ht")
        self.add(name, f'<img id="{eid}" src="{fn}" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;{bl}{extra}">')
        return eid

    def ht_png(self, w, h, step, angle, color, field, maxk=0.66):
        key = hashlib.md5(json.dumps([w, h, step, angle, color, field, maxk]).encode()).hexdigest()[:10]
        fn = f"assets/gen/ht_{key}.png"
        gen_halftone(f"{self.P}/{fn}", w, h, step, angle, color, field, maxk)
        return fn

    def font(self, fam):
        return {"serif": "'Playfair Display'", "display": "'Unbounded'", "mono": "'JetBrains Mono'", "sans": "'Inter'"}[fam]

    def weight(self, fam):
        return {"serif": 900, "display": 900, "mono": 800, "sans": 900}[fam]

    def headline(self, name, text, t0, y, x=80, size=None, fill=None, shadow=None, fam="serif", maxw=900, stagger=None,
                 layer=None, hide_at=None, eid=None):
        """STYLE 4 headline: black serif, left on the margin, a misregistration shadow (+8/+8 in the overprint ink), each
        glyph drops and squashes in (stagger 0.03-0.06 s for Cyrillic, which runs long like Latin); y = baseline.
        layer: a card name, or 'behind' (the speaker's face world, behind the speaker's head) / 'front'"""
        size = size or 140
        while est_w(text, size, fam) > maxw and size > 60:
            size -= 2
        fill = fill or C["navy"]
        shadow = C["pink"] if shadow is None else shadow
        st = stagger if stagger is not None else max(0.025, min(0.06, 0.5 / max(len(text), 1)))
        eid = eid or self.nid("hl")
        sh = f"text-shadow:{round(size * 0.055)}px {round(size * 0.055)}px 0 {shadow};" if shadow else ""
        spans = []
        k = 0
        for ch in text:
            if ch == " ":
                spans.append('<span class="sp"> </span>')
                continue
            spans.append(f'<span id="{eid}_{k}" class="ch" style="opacity:{1 if t0 <= 0 else 0}">{esc(ch)}</span>')
            k += 1
        html = (f'<div id="{eid}" class="hl" style="left:{x}px;top:{y - size * 0.80:.0f}px;font-family:{self.font(fam)};'
                f'font-weight:{self.weight(fam)};font-size:{size}px;color:{fill};{sh}">{"".join(spans)}</div>')
        self._place(name if layer is None else layer, html)
        for i in range(k if t0 > 0 else 0):
            self.tset(f"#{eid}_{i}", {"opacity": 1}, t0 + i * st)
        if t0 <= 0:                                         # frame 0 (the hook) is fully set: readable on the first frame
            if hide_at:
                self.tset(f"#{eid}", {"opacity": 0}, hide_at)
            return eid
        self.JS.append(f'tl.fromTo("#{eid} .ch", {{y: {round(size * 0.45)}, scaleX: 0.7, scaleY: 1.35}}, {{y: 0, scaleX: 1, scaleY: 1, '
                       f'duration: 0.38, ease: "back.out(1.9)", stagger: {st}, immediateRender: false}}, {fr(t0):.4f});')
        if hide_at:
            self.tset(f"#{eid}", {"opacity": 0}, hide_at)
        return eid

    def _place(self, layer, html):
        if layer == "behind":
            self.BEHIND.append(html)
        elif layer == "front":
            self.FRONT.append(html)
        else:
            self.add(layer, html)

    def text(self, name, html_text, x, y, size, fam="sans", fill=None, extra="", eid=None, anchor="left", w=None):
        """a static text block (labels, plates); y = top"""
        eid = eid or self.nid("tx")
        al = f"text-align:{anchor};" + (f"width:{w}px;" if w else "")
        self._place(name, f'<div id="{eid}" class="tx" style="left:{x}px;top:{y}px;font-family:{self.font(fam)};font-weight:{self.weight(fam)};'
                          f'font-size:{size}px;color:{fill or C["navy"]};{al}{extra}">{html_text}</div>')
        return eid

    def svg(self, name, body, boil=False, eid=None, origin=None, extra=""):
        """raw SVG on the 1080x1920 page; body = str or a function(Pen) -> str; boil=True draws three jittered copies that
        swap at 10 fps (STYLE 5 line boil on props only, never on text, dots, HUD or captions)"""
        eid = eid or self.nid("sv")
        o = f'style="transform-origin:{origin[0]}px {origin[1]}px;{extra}"' if origin else f'style="{extra}"'
        if boil:
            self.cards[name]["boil"] = True if name in self.cards else False
            base = int(hashlib.md5(eid.encode()).hexdigest()[:6], 16)
            parts = "".join(f'<g class="bv bv{i}">{body(Pen(seed=base + i * 7))}</g>' for i in range(3))
        else:
            parts = body(Pen(seed=1, j=0)) if callable(body) else body
        self._place(name, f'<svg id="{eid}" class="full" viewBox="0 0 1080 1920" {o}>{parts}</svg>')
        return eid

    def pop(self, sel, t, d=0.38, frm=None):
        """enter with overshoot: scale from 0 (back.out 1.9); hidden until t"""
        self.tset(sel, {"opacity": 1}, t)
        self.tween(sel, frm or {"scale": 0.0}, {"scale": 1, "ease": "back.out(1.9)", "duration": d}, t)

    def rise(self, sel, t, dy=1100, d=0.42):
        """enter rising from below the frame with overshoot"""
        self.tset(sel, {"opacity": 1}, t)
        self.tween(sel, {"y": dy}, {"y": 0, "ease": "back.out(1.6)", "duration": d}, t)

    def shake(self, name, t, amp=16, dur=0.35):
        """STYLE 6 shake with quadratic decay on a PAGE's camera group (never on the speaker's plate)"""
        n = int(dur * FPS)
        for i in range(n + 1):
            p = i / n
            a = amp * (1 - p) ** 2
            self.tset(f"#{name}_cam", {"x": round(a * math.sin(i * 2.1), 2), "y": round(a * math.cos(i * 2.9), 2)}, t + i * F1)

    def flash(self, name, t, peak=0.5, dur=0.3):
        """STYLE 6 flash frame on a page, capped at 0.5"""
        self.tset(f"#{name}_flash", {"opacity": peak}, t)
        self.tween(f"#{name}_flash", {"opacity": peak}, {"opacity": 0, "duration": dur, "ease": "power1.out"}, t)

    def pushin(self, name, t0, t1, to=1.05):
        """STYLE 6 slow push-in on a page"""
        self.tween(f"#{name}_cam", {"scale": 1}, {"scale": to, "ease": "none", "duration": t1 - t0}, t0)

    def stamp(self, name, word, t, x, y, rot=-8, size=150, color=None, shake=16):
        """STYLE 2/5 rubber stamp: double rounded rectangle + black sans, rough mottled ink (PNG mask, no SVG filter),
        0.93 opacity, slams 2.6x -> 1x in 0.09 s, damped bounce; on a page the camera shakes. name = a card, or 'front'
        (the speaker's face world: no shake, keep it below the speaker's face)"""
        color = color or C["red"]
        eid = self.nid("st")
        b = max(8, round(size * 0.075))
        html = (f'<div id="{eid}" class="stamp" style="left:{x}px;top:{y}px;opacity:0">'
                f'<div class="stin" style="border:{b}px solid {color};color:{color};font-size:{size}px;border-radius:{round(size * 0.16)}px;'
                f'padding:{round(size * 0.10)}px {round(size * 0.30)}px;">'
                f'<div style="border:{max(3, b // 3)}px solid {color};border-radius:{round(size * 0.09)}px;padding:{round(size * 0.04)}px {round(size * 0.18)}px">{esc(word)}</div></div></div>')
        self._place(name, html)
        self.JS.append(f'gsap.set("#{eid}", {{xPercent: -50, yPercent: -50, rotation: {rot}}});')
        self.tset(f"#{eid}", {"opacity": 0.3}, t - 0.09)
        self.tween(f"#{eid}", {"scale": 2.6}, {"scale": 1, "ease": "power3.in", "duration": 0.09}, t - 0.09)
        self.tset(f"#{eid}", {"opacity": 0.93}, t)
        self.tween(f"#{eid}", {"scale": 1.06}, {"scale": 1, "ease": "elastic.out(1, 0.35)", "duration": 0.5}, t)
        if shake and name in self.cards:
            self.shake(name, t, shake)
        return eid

    def numeral(self, name, s, x, y, size, fill=None, dots=None, t=None):
        """STYLE 2 halftone-filled numeral: a flat ink numeral overprinted with a darker halftone clipped to the glyph
        (CSS background-clip:text instead of an SVG clipPath); may bleed off the page; y = top"""
        fill, dots = fill or C["yellow"], dots or C["orange"]
        w, h = int(est_w(s, size, "display") * 1.15), int(size * 1.25)
        png = self.ht_png(w, h, 22, 15, dots, ("linear", h * 0.1, h * 0.95, 0.15, 0.95), 0.7)
        eid = self.nid("nu")
        st = f"position:absolute;left:0;top:0;font-family:'Unbounded';font-weight:900;font-size:{size}px;line-height:1.1;white-space:nowrap;"
        self.add(name, f'<div id="{eid}" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;">'
                       f'<div style="{st}color:{fill}">{s}</div>'
                       f'<div style="{st}color:transparent;background:url({png}) 0 0/{w}px {h}px no-repeat;-webkit-background-clip:text;background-clip:text">{s}</div></div>')
        if t is not None:
            self.rise(f"#{eid}", t, dy=900, d=0.45)
            self.JS.append(f'gsap.set("#{eid}", {{opacity: 0}});')
        return eid

    def behind(self, text, t0, t1, y, size=124, x=80, fill=None, shadow=None, stagger=None):
        """a headline on the speaker's face world BEHIND the speaker's head: between the speaker's plate and its matte (the matte must exist at t0-t1)"""
        return self.headline(None, text, t0, y=y, x=x, size=size, fill=fill or C["navy"], shadow=shadow, layer="behind",
                             hide_at=t1, stagger=stagger)

    def face_stamp(self, word, t, x=540, y=1330, rot=-7, size=96):
        """the closing stamp on the speaker's face world: below the speaker's face (over clothing / hands), no shake of the plate"""
        return self.stamp("front", word, t, x, y, rot=rot, size=size, shake=0)

    # ------------------------------------------------------------ card generators (each a new exhibit; see catalog.json)
    def mugshot(self, name, t_in, flash, plate_name, plate_sub, blinks=()):
        """the suspect: a height chart (mono labels), a blue halftone halo, the subject drawn as a kawaii prop with glossy
        eyes (here: a phone), a name plate; flash frame + squint on `flash`; slow push-in"""
        c = self.cards[name]
        self.ht(name, C["blue"], ("radial", 540, 1000, 600, 0.9), step=24, angle=45, maxk=0.62)
        self.ht(name, C["pink"], ("edge", 900, 1.6, 540, 960), step=22, angle=70, maxk=0.6)
        lines = "".join(f'<line x1="150" y1="{560 + k * 180}" x2="930" y2="{560 + k * 180}" stroke="{C["navy"]}" stroke-width="4" opacity=".55"/>' for k in range(6))
        self.svg(name, lines)
        for k, v in enumerate(("25", "20", "15", "10", "5", "0")):
            self.text(name, v, 60, 560 + k * 180 - 30, 48, "mono", extra="opacity:.8")
            self.text(name, v, 940, 560 + k * 180 - 30, 48, "mono", extra="opacity:.8", anchor="left")
        self.text(name, "см", 940, 470, 48, "mono", extra="opacity:.8")

        def phone(p):
            s = [p.rrect(340, 640, 400, 720, 64, C["blue"]),
                 p.rrect(372, 712, 336, 560, 26, C["cream"], 6),
                 p.rrect(490, 668, 100, 18, 9, C["navy"], 0),
                 p.ell(470, 1000, 30, 18, C["pink"], 0, extra='opacity=".7"'), p.ell(610, 1000, 30, 18, C["pink"], 0, extra='opacity=".7"'),
                 p.poly([(520, 1040), (540, 1056), (560, 1040)], "none", 6, closed=False),
                 p.ell(722, 660, 34, 34, C["red"]), p.ell(380, 1300, 26, 26, C["red"]),
                 p.rrect(470, 1300, 140, 26, 13, C["navy"], 0)]
            return "".join(s)
        ph = self.svg(name, phone, boil=True, extra="opacity:0")
        ey = self.svg(name, lambda p: eyes(Pen(3, 0), 540, 930, 140, 34, 44, f"{name}_eyes"), extra="opacity:0")
        self.rise(f"#{ph}", t_in)
        self.rise(f"#{ey}", t_in)
        pl = self.nid("pl")
        self.add(name, f'<div id="{pl}" class="plate" style="left:250px;top:1290px;width:580px;opacity:0">'
                       f'<div style="font:900 80px Inter;color:{C["cream"]};letter-spacing:2px">{esc(plate_name)}</div>'
                       f'<div style="font:800 48px \'JetBrains Mono\';color:{C["yellow"]}">{esc(plate_sub)}</div></div>')
        self.rise(f"#{pl}", t_in + 0.25, dy=700)
        self.flash(name, flash)
        self.JS.append(f'gsap.set("#{name}_eyes", {{svgOrigin: "540 930"}});')
        self.tset(f"#{name}_eyes", {"scaleY": 0.15}, flash)
        self.tset(f"#{name}_eyes", {"scaleY": 1}, flash + 0.27)
        for b in blinks:
            self.tset(f"#{name}_eyes", {"scaleY": 0.1}, b)
            self.tset(f"#{name}_eyes", {"scaleY": 1}, b + 0.1)
        self.pushin(name, c["t0"], c["t1"])
        self.keys(name, flash + 0.03, t_in + 0.6)

    def photo_exhibit(self, name, img, t_drop, label_lines, t_label, w=540, x=120, y=560, rot=-3):
        """a real picture the speaker names, pinned as an exhibit: a white-bordered print with tape, dropping in with overshoot,
        and a typed evidence label (mono). The picture stays as it is (no halftone over a cover or a person)"""
        eid = self.nid("ph")
        self.add(name, f'<div id="{eid}" class="print" style="left:{x}px;top:{y}px;width:{w}px;opacity:0">'
                       f'<img src="{img}" style="display:block;width:{w}px">'
                       f'<div class="tape" style="left:-40px;top:-22px;transform:rotate(-24deg)"></div>'
                       f'<div class="tape" style="right:-40px;top:-22px;transform:rotate(22deg)"></div></div>')
        self.JS.append(f'gsap.set("#{eid}", {{rotation: {rot}}});')
        self.tset(f"#{eid}", {"opacity": 1}, t_drop)
        self.tween(f"#{eid}", {"y": -1400, "rotation": rot - 14}, {"y": 0, "rotation": rot, "ease": "back.out(1.5)", "duration": 0.45}, t_drop)
        lb = self.nid("lb")
        inner = "<br>".join(esc(s) for s in label_lines)
        self.add(name, f'<div id="{lb}" class="label" style="left:420px;top:1270px;opacity:0">{inner}</div>')
        self.JS.append(f'gsap.set("#{lb}", {{rotation: 2}});')
        self.pop(f"#{lb}", t_label)
        self.keys(name, t_drop + 0.5, t_label + 0.4)

    def notifications(self, name, t_phone, items, x0=150, w=780, y0=760, gap=170):
        """the phone's lock screen on a dark page with notification banners that pop out of it on their words; items =
        [(t, label, icon in envelope / bubble / heart, ink)]"""
        def phone(p):
            return (p.rrect(300, 620, 480, 900, 70, C["blue"]) + p.rrect(334, 700, 412, 760, 30, C["yellow"], 6) +
                    p.rrect(490, 648, 100, 20, 10, C["navy"], 0))
        ph = self.svg(name, phone, boil=True, extra="opacity:0")
        self.rise(f"#{ph}", t_phone)
        for k, (t, label, icon, ink) in enumerate(items):
            y = y0 + k * gap

            def card(p, y=y, icon=icon, ink=ink):
                s = p.rrect(x0, y, w, 140, 26, C["cream"], 6) + p.rrect(x0 + 22, y + 22, 96, 96, 20, ink, 5)
                ix, iy = x0 + 22, y + 22
                if icon == "envelope":
                    s += envelope(p, ix + 16, iy + 26, 64, 46, C["cream"])
                elif icon == "bubble":
                    s += bubble(p, ix + 14, iy + 18, 68, 60, C["cream"])
                else:
                    s += p.path(heart_d(ix + 48, iy + 52, 0.75), C["cream"], 5)
                return s
            cid = self.svg(name, card, boil=True, extra=f"opacity:0;transform-origin:{x0 + w / 2}px {y + 70}px")
            tid = self.text(name, esc(label), x0 + 140, y + 38, 54, "sans", extra=f"opacity:0;transform-origin:{w / 2 - 140}px 35px")
            self.pop(f"#{cid}", t)
            self.pop(f"#{tid}", t)
            self.keys(name, t + 0.4)

    def board(self, name, items, x=120, w=840, y0=530, gap=330, string_t=None):
        """evidence board: numbered exhibit cards pinned on the page, each with a halftone swatch + a drawn icon and the speaker's
        word, landing with overshoot on its word; a red string joins the pins. items = [(t, num, label, icon, ink)]"""
        pins = []
        at = len(self.cards[name]["h"])                     # the string goes in here, under the cards
        for k, (t, num, label, icon, ink) in enumerate(items):
            y = y0 + k * gap
            rot = (-2.2, 1.6, -1.2, 2.0)[k % 4]
            gid = self.nid("ex")
            sw = self.ht_png(230, 230, 20, 30 + k * 20, C["navy"], ("radial", 0, 0, 260, 1.6), 0.5)
            ic = {"moon": lambda p, ink=ink: p.ell(108, 118, 72, 72, C["cream"], 6) + p.ell(146, 88, 62, 62, ink, 0),
                  "dumbbell": lambda p: dumbbell(p, 115, 115, 0.85, C["pink"] if ink != C["pink"] else C["yellow"]),
                  "heart": lambda p: p.path(heart_d(115, 120, 1.7), C["red"] if ink != C["red"] else C["cream"], 6),
                  "mountain": lambda p: p.poly([(20, 200), (100, 50), (210, 200)], C["blue"], 6)}[icon]
            icon_svg = "".join(f'<g class="bv bv{i}">{ic(Pen(seed=k * 31 + i * 7))}</g>' for i in range(3))
            self.add(name, f'<div id="{gid}" class="excard" style="left:{x}px;top:{y}px;width:{w}px;opacity:0">'
                           f'<div class="swatch" style="background:{ink} url({sw}) 0 0/230px 230px"><svg viewBox="0 0 230 230" width="230" height="230">{icon_svg}</svg></div>'
                           f'<div class="exnum">{esc(num)}</div><div class="exlab">{esc(label)}</div>'
                           f'<div class="pin"></div></div>')
            self.cards[name]["boil"] = True
            self.JS.append(f'gsap.set("#{gid}", {{rotation: {rot}}});')
            self.tset(f"#{gid}", {"opacity": 1}, t)
            self.tween(f"#{gid}", {"y": 900, "scale": 0.6}, {"y": 0, "scale": 1, "ease": "back.out(1.7)", "duration": 0.4}, t)
            self.shake(name, t + 0.3, 6, 0.2)
            pins.append((x + w / 2, y + 6))
            self.keys(name, t + 0.45)
        if string_t is not None and len(pins) > 1:
            d = "M" + " L".join(f"{a:.0f} {b:.0f}" for a, b in [(pins[0][0] - 330, pins[0][1])] + pins + [(pins[-1][0] + 300, pins[-1][1] + 120)])
            L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pins, pins[1:])) + 800
            sid = self.nid("str")
            self.svg(name, f'<path id="{sid}_p" d="{d}" fill="none" stroke="{C["red"]}" stroke-width="7" stroke-linecap="round" '
                           f'stroke-dasharray="{L:.0f}" stroke-dashoffset="{L:.0f}"/>', eid=sid)
            self.cards[name]["h"].insert(at, self.cards[name]["h"].pop())
            self.tween(f"#{sid}_p", {"strokeDashoffset": L}, {"strokeDashoffset": 0, "duration": 0.5, "ease": "power2.out"}, string_t)
            self.keys(name, string_t + 0.6)

    def task_verdict(self, name, t_in):
        """the hard task drawn as a mountain with a flag (blue + cream cap + pink flag, navy halftone shadow), rising in"""
        self.ht(name, C["navy"], ("linear", 900, 1500, 0.0, 0.85), step=22, angle=20, maxk=0.6, box=(0, 0, 1080, 1920))

        def mountain(p):
            return (p.poly([(110, 1460), (470, 760), (620, 1010), (720, 880), (980, 1460)], C["blue"]) +
                    p.poly([(470, 760), (410, 880), (470, 860), (520, 900), (545, 860)], C["cream"], 6) +
                    p.poly([(470, 760), (470, 600)], "none", 7, closed=False) + p.poly([(470, 600), (580, 640), (470, 680)], C["pink"], 6))
        mid = self.svg(name, mountain, boil=True, extra="opacity:0")
        self.rise(f"#{mid}", t_in)
        self.keys(name, t_in + 0.5)

    def space_grid(self, name, t_phone, t_free, cols=6, rows=6, cell=120, gap=18, x0=None, y0=560, label=None):
        """'how much room is left': a page of empty day cells covered by one big phone; on `t_free` the phone shrinks away
        and a yellow halftone bloom swells over the freed cells (dot density = joy)"""
        W = cols * cell + (cols - 1) * gap
        H = rows * cell + (rows - 1) * gap
        x0 = x0 if x0 is not None else (1080 - W) // 2
        bl = self.ht(name, C["yellow"], ("radial", 540, y0 + H / 2, 620, 0.8), step=26, angle=15, maxk=0.7, mul=True,
                     extra=f"opacity:0;transform-origin:540px {y0 + H / 2}px")
        cells = "".join(f'<rect x="{x0 + c * (cell + gap)}" y="{y0 + r * (cell + gap)}" width="{cell}" height="{cell}" rx="16" fill="none" '
                        f'stroke="{C["navy"]}" stroke-width="6"/>' for r in range(rows) for c in range(cols))
        self.svg(name, cells)
        if label:
            self.text(name, esc(label), x0, y0 - 80, 48, "mono")

        def phone(p):
            return (p.rrect(x0 - 20, y0 - 20, W + 40, H + 40, 70, C["navy"]) + p.rrect(x0 + 24, y0 + 60, W - 48, H - 120, 34, C["blue"], 6) +
                    p.rrect(540 - 60, y0 + 14, 120, 22, 11, C["cream"], 0))
        ph = self.svg(name, phone, boil=True, origin=(980, y0 + H), extra="opacity:0")
        self.rise(f"#{ph}", t_phone, dy=1300)
        self.tween(f"#{ph}", {"scale": 1, "x": 0}, {"scale": 0.0, "x": 200, "ease": "back.in(1.6)", "duration": 0.35}, t_free)
        self.tset(f"#{bl}", {"opacity": 1}, t_free + 0.2)
        self.tween(f"#{bl}", {"scale": 0.2}, {"scale": 1.0, "ease": "back.out(1.6)", "duration": 0.6}, t_free + 0.2)
        self.keys(name, t_phone + 0.5, t_free + 0.85)

    # ------------------------------------------------------------ captions, HUD, wipes
    def captions(self, starts, keys=(), pop_after=(".", "?", "!")):
        """STYLE 4 'cards are the subtitles': the caption bar carries every spoken word, chunk by chunk (hard swaps), a
        navy pill with a pink offset shadow, cream Inter 900 54 px, keywords in yellow; it pops in on a new sentence and
        on every cut. starts = word index where each chunk begins (all words covered); keys = word indices in yellow"""
        assert starts[0] == 0
        b = starts + [len(self.W)]
        keys = set(keys)
        cuts = sorted([c["t0"] for c in self.cards.values()] + [f[1] for f in self.FACES])
        for k in range(len(starts)):
            i0, i1 = b[k], b[k + 1]
            t0 = self.W[i0][1] if k else 0.0
            t1 = self.W[i1][1] if i1 < len(self.W) else self.dur
            if t1 - self.W[i1 - 1][2] > 0.7:
                t1 = self.W[i1 - 1][2] + 0.5
            words = []
            for i in range(i0, i1):
                w = esc(self.W[i][0])
                words.append(f'<span class="kw">{w}</span>' if i in keys else w)
            n = len(" ".join(self.W[i][0] for i in range(i0, i1)))
            assert n <= 25, f"caption chunk too long ({n} chars): {[self.W[i][0] for i in range(i0, i1)]}"
            cid = f"cap{k}"
            self.caps_html.append(f'<div class="caprow"><div id="{cid}" class="cap" style="opacity:0">{" ".join(words)}</div></div>')
            self.tset(f"#{cid}", {"opacity": 1}, t0)
            self.tset(f"#{cid}", {"opacity": 0}, t1)
            new_sent = k == 0 or self.W[i0 - 1][0].endswith(pop_after) or any(abs(c - t0) < 0.25 for c in cuts)
            if new_sent:
                self.tween(f"#{cid}", {"scale": 0.8, "y": 40, "rotation": -2.4}, {"scale": 1, "y": 0, "rotation": -0.6, "ease": "back.out(1.9)", "duration": 0.4}, t0)
            else:
                self.tset(f"#{cid}", {"rotation": -0.6}, t0)

    def chips(self, rows):
        """HUD chapter chip under the case number: [(t0, text)] (each holds until the next)"""
        self.chips_ = rows

    def wipes(self, rows):
        """STYLE 5 dot wipe at each cut: [(t, ink key or hex, mode)], mode = 'full' (page to page), 'out' (grows over the
        outgoing page, hard cut to the speaker's face), 'in' (hard cut from the speaker's face, shrinks off the incoming page), 'hard'"""
        self.wipes_ = rows

    # ------------------------------------------------------------ write
    def build(self):
        P, DUR = self.P, self.dur
        cream, navy = C["cream"], C["navy"]
        faces = "".join(f"@font-face {{ font-family: '{fam}'; src: url('assets/fonts/{fn}-{sub}.woff2') format('woff2'); font-weight: {wt}; "
                        f"font-style: {sty}; font-display: block; unicode-range: {rng}; }}\n"
                        for fam, fn, wt, sty in TY["font_faces"] for sub, rng in TY["unicode_ranges"])
        css = f"""{faces}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
.full {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }}
svg.full {{ overflow: visible; }}
video.full {{ object-fit: cover; }}
.card {{ overflow: hidden; }}
.hl, .tx, .stamp, .plate, .print, .label, .excard {{ position: absolute; white-space: nowrap; }}
.hl {{ line-height: 1; }}
.hl .ch {{ display: inline-block; transform-origin: 50% 100%; }}
.hl .sp {{ display: inline-block; width: 0.28em; }}
.tx {{ line-height: 1.15; }}
.stamp {{ font-family: 'Inter'; font-weight: 900; letter-spacing: 2px; transform-origin: 50% 50%; }}
.stin {{ -webkit-mask-image: url(assets/gen/ink.png); mask-image: url(assets/gen/ink.png); -webkit-mask-size: 100% 100%; mask-size: 100% 100%; line-height: 1; }}
.plate {{ background: {navy}; border-radius: 22px; padding: 22px 30px 26px; text-align: center; box-shadow: 10px 10px 0 {C["pink"]}; }}
.print {{ background: #FFFDF6; padding: 16px; border: 6px solid {navy}; box-shadow: 14px 14px 0 {navy}; }}
.tape {{ position: absolute; width: 170px; height: 52px; background: {C["yellow"]}; border: 5px solid {navy}; opacity: .92; }}
.label {{ background: {cream}; border: 6px solid {navy}; border-radius: 10px; padding: 18px 26px; font: 800 48px 'JetBrains Mono'; color: {navy}; line-height: 1.25; box-shadow: 10px 10px 0 {C["pink"]}; }}
.excard {{ background: {cream}; border: 7px solid {navy}; border-radius: 20px; height: 270px; box-shadow: 12px 12px 0 {navy}; }}
.swatch {{ position: absolute; left: 20px; top: 20px; width: 230px; height: 230px; border: 6px solid {navy}; border-radius: 14px; box-sizing: border-box; overflow: hidden; }}
.swatch svg {{ position: absolute; left: -6px; top: -6px; }}
.exnum {{ position: absolute; left: 290px; top: 34px; font: 900 64px 'Unbounded'; color: {C["pink"]}; }}
.exlab {{ position: absolute; left: 290px; top: 130px; font: 900 62px 'Inter'; color: {navy}; }}
.pin {{ position: absolute; left: 50%; top: -22px; width: 40px; height: 40px; margin-left: -20px; border-radius: 50%; background: {C["red"]}; border: 6px solid {navy}; }}
.bv {{ display: none; }}
.card[data-b="0"] .bv0, .card[data-b="1"] .bv1, .card[data-b="2"] .bv2 {{ display: inline; }}
.paper {{ mix-blend-mode: multiply; pointer-events: none; }}
.grain {{ position: absolute; left: -60px; top: -60px; width: 1200px; height: 2040px; pointer-events: none; }}
#hud {{ position: absolute; left: 0; top: 0; width: 1080px; height: 300px; z-index: 30; }}
#hud .case, #hud .chip, #hud .rec {{ position: absolute; background: {navy}; color: {cream}; border-radius: 12px; white-space: nowrap; }}
#hud .case {{ left: 60px; top: 130px; font: 800 48px 'JetBrains Mono'; padding: 6px 18px; }}
#hud .chip {{ left: 60px; top: 214px; font: 900 48px 'Inter'; padding: 4px 18px; color: {C["yellow"]}; }}
#hud .rec {{ right: 100px; top: 130px; font: 800 48px 'JetBrains Mono'; padding: 6px 18px 6px 64px; }}
#hud .dot {{ position: absolute; left: 20px; top: 22px; width: 30px; height: 30px; border-radius: 50%; background: {C["red"]}; }}
#hud[data-dark="1"] .case, #hud[data-dark="1"] .chip, #hud[data-dark="1"] .rec {{ background: {cream}; color: {navy}; }}
#hud[data-dark="1"] .chip {{ color: {C["red"]}; }}
#caps {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; z-index: 31; pointer-events: none; }}
.caprow {{ position: absolute; left: 0; width: 1020px; top: 1560px; display: flex; justify-content: center; }}
.cap {{ background: {navy}; color: {cream}; font: 900 54px 'Inter'; padding: 20px 34px 24px; border-radius: 14px; box-shadow: 10px 10px 0 {C["pink"]}; white-space: nowrap; line-height: 1.1; }}
.cap .kw {{ color: {C["yellow"]}; }}
#wipe {{ z-index: 40; pointer-events: none; }}
"""
        H = []
        H.append(f'<div id="cam" class="full" style="z-index:1"><video id="vplate" class="full" src="{self.plate[0]}" data-start="0" '
                 f'data-duration="{DUR:.2f}" data-track-index="0" muted playsinline></video></div>')
        H.append('<div id="behind" class="full" style="z-index:2">' + "\n".join(self.BEHIND) + "</div>")
        H.append(f'<div id="mcam" class="full" style="z-index:3"><video id="vmatte" class="full" src="{self.plate[1]}" data-start="0" '
                 f'data-duration="{DUR:.2f}" data-track-index="1" muted playsinline></video></div>')
        # pages
        grain_sets = []
        for k, name in enumerate(self.order):
            c = self.cards[name]
            t0, t1 = fr(c["t0"]), fr(c["t1"])
            H.append(f'<section id="{name}" class="clip full card" data-b="0" data-start="{t0:.4f}" data-duration="{t1 - t0:.4f}" '
                     f'data-track-index="{10 + k}" style="z-index:{10 + k};background:{c["bg"]}">')
            H.append(f'<div id="{name}_cam" class="full" style="transform-origin:540px 960px">')
            H += c["h"]
            H.append("</div>")
            H.append(f'<img class="full paper" src="assets/gen/paper.png">')
            H.append(f'<img class="grain" src="assets/gen/grain.png">')
            H.append(f'<div id="{name}_flash" class="full" style="background:#FFFFFF;opacity:0"></div>')
            H.append("</section>")
            if c["boil"]:
                for i, t in enumerate(range(int(t0 * 10), int(t1 * 10) + 1)):
                    self.tset(f"#{name}", {"attr": {"data-b": str(i % 3)}}, t / 10)
            r = random.Random(k * 101)
            for f in range(int(t0 * FPS), int(t1 * FPS), 2):
                grain_sets.append((f / FPS, r.uniform(-55, 55), r.uniform(-55, 55)))
        for t, x, y in grain_sets:
            self.tset(".grain", {"x": round(x, 1), "y": round(y, 1)}, t)
        H.append('<div id="front" class="full" style="z-index:29">' + "\n".join(self.FRONT) + "</div>")
        # HUD
        chips = "".join(f'<div id="chip{i}" class="chip" style="opacity:0">{esc(s)}</div>' for i, (_, s) in enumerate(self.chips_))
        H.append(f'<div id="hud"><div class="case">{esc(self.case)}</div>{chips}<div class="rec"><div id="recdot" class="dot"></div>{esc(self.date)}</div></div>')
        for i, (t, _) in enumerate(self.chips_):
            t1 = self.chips_[i + 1][0] if i + 1 < len(self.chips_) else DUR
            self.tset(f"#chip{i}", {"opacity": 1}, t)
            self.tset(f"#chip{i}", {"opacity": 0}, t1)
            self.tween(f"#chip{i}", {"scale": 0.6}, {"scale": 1, "ease": "back.out(1.9)", "duration": 0.3}, t)
        for a, b in self.hud_hidden:
            self.tset("#hud", {"opacity": 0}, a)
            self.tset("#hud", {"opacity": 1}, b)
        for name in self.order:
            c = self.cards[name]
            if c["dark"]:
                self.tset("#hud", {"attr": {"data-dark": "1"}}, c["t0"])
                self.tset("#hud", {"attr": {"data-dark": "0"}}, c["t1"])
        for i in range(int(DUR * 2)):                        # REC dot blinks at 1 Hz
            self.tset("#recdot", {"opacity": 1 if i % 2 == 0 else 0.15}, i * 0.5)
        H.append('<div id="caps">' + "\n".join(self.caps_html) + "</div>")
        # dot wipe: 90 px grid, circles grow to full cover with a diagonal delay (0.22 s per half)
        G, R = 90, 66
        cols, rows = 12, 22
        circles = []
        for j in range(rows):
            for i in range(cols):
                circles.append(f'<circle class="wc wd{i + j}" cx="{i * G + G / 2}" cy="{j * G + G / 2}" r="0"/>')
        H.append(f'<svg id="wipe" class="full" viewBox="0 0 1080 1920"><g id="wipeg" fill="{navy}">{"".join(circles)}</g></svg>')
        K = cols + rows - 1
        for t, ink, mode in self.wipes_:
            col = C.get(ink, ink)
            if mode == "hard":
                continue
            self.tset("#wipeg", {"attr": {"fill": col}}, t - 0.24)
            for k in range(K):
                dk = 0.10 * k / (K - 1)
                if mode in ("full", "out"):
                    s0 = fr(t - 0.22 + dk)
                    self.tween(f".wd{k}", {"attr": {"r": 0}}, {"attr": {"r": R}, "duration": round(fr(t) - s0, 4), "ease": "power2.in"}, s0)
                if mode in ("full", "in"):
                    s0 = fr(t + dk) + (F1 if mode == "full" and fr(t + dk) <= fr(t) else 0)
                    self.tween(f".wd{k}", {"attr": {"r": R}}, {"attr": {"r": 0}, "duration": round(max(F1, fr(t + 0.22) - s0), 4), "ease": "power2.out"}, s0)
            if mode == "out":
                self.tset(".wc", {"attr": {"r": 0}}, t)
        # audio
        aud = [f'<audio id="vo" src="{self.voice}" data-start="0" data-duration="{self.voice_dur:.2f}" data-track-index="40" data-volume="1"></audio>']
        for i, (f, t, v, dd) in enumerate(self.SFX):
            dd = min(dd, DUR - t)
            aud.append(f'<audio id="sfx{i}" src="assets/sfx/{f}" data-start="{fr(t):.4f}" data-duration="{dd:.4f}" data-track-index="{50 + i}" data-volume="{v}"></audio>')
        html = f"""<!doctype html>
<html lang="{self.lang}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{esc(self.page_title)}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{css}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{DUR:.2f}" data-fps="{FPS}">
{chr(10).join(H)}
{chr(10).join(aud)}
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(self.JS)}
tl.set({{}}, {{}}, {DUR:.2f});
window.__timelines["main"] = tl;
</script>
</div>
</body>
</html>
"""
        open(f"{P}/index.html", "w").write(html)
        shots = [{"t0": self.cards[n]["t0"], "t1": self.cards[n]["t1"]} for n in self.order]
        json.dump({"fps": FPS, "beats": sorted(self.BEATS, key=lambda b: b["t0"]), "shots": shots}, open(f"{P}/build/beats.json", "w"), indent=1)
        face_s = sum(b - a for _, a, b in self.FACES)
        lines = [f"face on screen: {face_s:.2f} s of {DUR:.2f} s = {100 * face_s / DUR:.1f} %",
                 f"pages: {len(self.order)}; sfx: {len(self.SFX)} ({10 * len(self.SFX) / DUR:.1f} per 10 s); html {len(html) // 1024} KB",
                 "snapshot keys: " + " ".join(f"{k:.2f}" for b in sorted(self.BEATS, key=lambda b: b["t0"]) for k in b["keys"])]
        open(f"{P}/build/coverage.txt", "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return lines


if __name__ == "__main__":
    print(__doc__)
