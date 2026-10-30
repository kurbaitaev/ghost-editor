"""News Package: the speaker's talking head as the anchor of a one-story TV news segment. A sting whose plate flies to the
corner and becomes the channel bug; a lower-third strap on the speaker's chest (lemon category tab, paper headline, ink end
block) that stays from the first story to the recap and flips its words; a rundown of the reel's points that opens the
segment and comes back ticked off at the end; between face shots, full-frame package cards on ink that carry one fact each (a document, a
split-flap board, check rows, accent-edged cards, a schematic threshold line, proportion bars), joined by the lemon band
wipe between parts and hard cuts inside a part. Ported from the MIT-licensed lemo-opuscar style 'Broadcast News Package'
(styles/news-package; CREDITS.txt) and adapted to 9:16 and a talking head.

    import sys; sys.path.insert(0, "<skill>/recipes/news-package"); from newspackage import *
    B = Bulletin("$P", dur=30.0, title="Coffee News Package", plates={"a": "assets/wide.mp4", "t": "assets/tight.mp4"},
                 lang="en")
    B.plates([(0, "a"), (14.2, "t"), (19.5, "a")])           # the speaker's framings, as shot (switch on the jump cuts)
    S1 = Strap("TODAY", "Your morning coffee", "HOW MUCH IS TOO MUCH")
    B.sting(0.0, 1.02, "ON AIR", "YOU AND COFFEE", "ONE SEGMENT · ONE STORY")   # the plate becomes the bug at 1.02
    B.face(0.72, 2.45); B.face_strap(1.0, S1, "enter")       # the face as shot; the strap enters on the chest
    c = B.card("rundown", 2.45, 4.52); B.rundown(c, ROWS, ...) # full-frame package card (studio background on ink)
    B.wipe(2.45, into="rundown")                               # band wipe: the new picture is revealed left of the band
    ...
    B.sfx("whoosh-2", 2.40, 0.3); B.build()

Cards: B.card(name, t0, t1, strap=Strap|None, tag="SCHEMATIC"|None) -> Card; scenes draw into it: rundown(), document(),
flap_board(), check_rows(), accent_cards(), threshold(), proportion(), stamp(), title(), eyebrow(). Transitions: wipe()
(band; into / out_of = card name or "face") and plain hard cuts (adjacent windows; add an impact SFX). The face strap:
face_strap(t, Strap, mode) with mode "enter" (slides in), "set" (instant, under a card or a cut) or "flip" (on the face).
Words: B.t("coffee") / B.t("coffee", 2) = onset of that word (edit seconds) in build/words.cut.json.

House (house.json): the palette (ink, lemon, gold, paper, olive), the type (Fira Sans 800 headlines, Fira Sans Extra
Condensed 800/600 for plate, tabs, numbers, IBM Plex Mono 500 for eyebrows and sources; every word >= 48 px and checked
against the font's glyphs), the plate / bug / strap / tab / rundown / band wipe / stamp / corner tag, the speaker's face as shot.
New every reel: which cards carry which point (components.py plan --style news-package).
"""
import json
import math
import os
import re
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
HOUSE = json.load(open(os.path.join(HERE, "house.json"), encoding="utf-8"))
PAL = HOUSE["palette"]
TY = HOUSE["type"]
FAM = {k: tuple(v) for k, v in TY["families"].items()}       # key -> (family, weight, style, file stem)
FLOOR = TY["floor_px"]
LP = HOUSE["layout_px"]
FPS = HOUSE["motion"]["fps"]
F1 = 1 / FPS
HID = ' opacity="0"'
HIDV = ' style="visibility:hidden;opacity:0"'
W, H = 1080, 1920
SFX_LEN = {}
UNI = {"cyrillic": "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116",
       "latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"}


def fr(t):
    """snap to the frame grid"""
    return round(round(t * FPS) / FPS, 4)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def is_cyr(ch):
    return 0x0400 <= ord(ch) <= 0x04FF or ch == "№"


# ---------------------------------------------------------------- fonts: copy, convert for measuring, glyph check
_TTF = {}
_CMAP = {}
_fc = {}


def _ranges(spec):
    out = []
    for part in spec.split(","):
        a = part.strip()[2:].split("-")
        out.append((int(a[0], 16), int(a[-1], 16)))
    return out


RANGES = {sub: _ranges(spec) for sub, spec in UNI.items()}


# IBM Plex Mono carries the Reserved Font Name "Plex": a subset is a Modified Version, so it is served as the unmodified
# TTF from fonts/ttf (same unicode-ranges, same glyph check); the other families are Google's woff2 subsets
WHOLE = {"plex-mono-500"}


def ensure_fonts(P):
    """copy the woff2 subsets (the page) into assets/fonts; measure and check glyphs with the full TTFs in fonts/ttf
    (the woff2 subsets need brotli to read): a glyph must be in the TTF and inside its subset's unicode-range"""
    os.makedirs(f"{P}/assets/fonts", exist_ok=True)
    from fontTools.ttLib import TTFont
    for key, (_, _, _, stem) in FAM.items():
        if stem in WHOLE:
            dst = f"{P}/assets/fonts/{stem}.ttf"
            if not os.path.exists(dst):
                shutil.copy(f"{HERE}/fonts/ttf/{stem}.ttf", dst)
        for sub in ("cyrillic", "latin") if stem not in WHOLE else ():
            dst = f"{P}/assets/fonts/{stem}-{sub}.woff2"
            if not os.path.exists(dst):
                shutil.copy(f"{HERE}/fonts/{stem}-{sub}.woff2", dst)
        ttf = f"{HERE}/fonts/ttf/{stem}.ttf"
        cmap = set(TTFont(ttf).getBestCmap())
        for sub in ("cyrillic", "latin"):
            _TTF[(key, sub)] = ttf
            _CMAP[(key, sub)] = {c for c in cmap if any(a <= c <= b for a, b in RANGES[sub])}


def _font(key, sub):
    from PIL import ImageFont
    k = (key, sub)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(_TTF[k], 200)
    return _fc[k]


def check_glyphs(s, key):
    for ch in s:
        if ch == " ":
            continue
        sub = "cyrillic" if is_cyr(ch) else "latin"
        if ord(ch) not in _CMAP[(key, sub)]:
            raise ValueError(f"{FAM[key][0]} {sub} subset has no glyph for {ch!r} in {s!r}")


def adv(s, key, size, ls=0.0):
    """advance width in px (per char from the subset that has it; kerning ignored -> errs wide) + tracking"""
    w = sum(_font(key, "cyrillic" if is_cyr(c) else "latin").getlength(c) * size / 200 for c in s)
    return w + ls * max(len(s) - 1, 0)


def fit(s, key, size, maxw, ls=0.0, floor=FLOOR):
    """the largest size <= size at which s fits maxw; raises when it would go under the floor (the 48 px floor)"""
    w = adv(s, key, size, ls)
    if w <= maxw:
        return size
    k = size * maxw / w
    if k < floor - 0.01:
        raise ValueError(f"{s!r} needs {k:.1f} px to fit {maxw} px (< {floor}): shorten it")
    return math.floor(k * 10) / 10


def tstyle(key, size, fill, ls=0.0, extra=""):
    f = FAM[key]
    return (f"font-family:'{f[0]}';font-weight:{f[1]};font-style:{f[2]};font-size:{size:.1f}px;"
            f"letter-spacing:{ls:.2f}px;fill:{fill};{extra}")


def txt(s, x, y, key, size, fill, anchor="start", ls=0.0, tid=None, extra="", attrs=""):
    """one SVG text line; refuses words under 48 px and glyphs the font lacks"""
    if size < FLOOR - 0.01:
        raise ValueError(f"{s!r} at {size} px (< {FLOOR} px)")
    check_glyphs(s, key)
    i = f' id="{tid}"' if tid else ""
    return (f'<text{i} x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" {attrs} style="white-space:pre;{tstyle(key, size, fill, ls, extra)}">'
            f'{esc(s)}</text>')


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def studio_png(P):
    """the studio background (STYLE.md: ink, a radial lemon glow, a faint dot grid) as one PNG per project; the diagonal
    light bands are SVG and drift"""
    out = f"{P}/assets/np/studio.png"
    if os.path.exists(out):
        return "assets/np/studio.png"
    import numpy as np
    from PIL import Image
    os.makedirs(os.path.dirname(out), exist_ok=True)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ink = np.array([0x12, 0x14, 0x17], np.float32)
    lem = np.array([0xF2, 0xCF, 0x1D], np.float32)
    d = np.sqrt((xx - 760) ** 2 + (yy - 620) ** 2)
    a = np.clip(1 - (d - 60) / 1250, 0, 1) * 0.16
    img = ink[None, None, :] * (1 - a[..., None]) + lem[None, None, :] * a[..., None]
    dots = ((xx.astype(int) - 40) % 48 < 2) & ((yy.astype(int) - 24) % 48 < 2)
    img[dots] = img[dots] * 0.95 + np.array([0xF4, 0xF1, 0xE8], np.float32) * 0.05
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out)
    return "assets/np/studio.png"


class Strap:
    """one state of the lower-third strap: the category tab, the headline (s8, fit to 736 px, >= 48), an optional sub-line
    (c6 caps, olive) and an optional source line (mono, right-aligned under the strap)"""

    def __init__(self, tab, head, sub=None, source=None):
        self.tab, self.head, self.sub, self.source = tab, head, sub, source

    def key(self):
        return (self.tab, self.head, self.sub, self.source)


class Card:
    def __init__(self, B, name, t0, t1, z, strap, tag, bg):
        self.B, self.name, self.t0, self.t1, self.z, self.strap, self.tag, self.bg = B, name, t0, t1, z, strap, tag, bg
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def id(self, s):
        return f"{self.name}_{s}"


# ---------------------------------------------------------------- the bulletin
class Bulletin:
    def __init__(self, project, dur, title, plates, words="build/words.cut.json", voice="assets/voice.wav", lang="ru",
                 fixes=None):
        self.P = os.path.abspath(os.path.expanduser(project))
        self.dur, self.page_title, self.lang = dur, title, lang
        d = json.load(open(f"{self.P}/{words}", encoding="utf-8"))
        raw = [w for s in d["segments"] for w in s["words"]] if "segments" in d else d["words"]
        fixes = fixes or {}
        self.W = [(fixes.get(w["word"].strip(), w["word"].strip()), w["start"], w["end"]) for w in raw]
        self.plates_ = plates                                   # key -> path (the speaker's framings as shot)
        self.voice = voice
        self.voice_dur = round(probe_dur(f"{self.P}/{voice}"), 3)
        ensure_fonts(self.P)
        self.bgpng = studio_png(self.P)
        self.JS, self.PRE, self.CARDS, self.FACE, self.BEATS, self.SFX = [], [], [], [], [], []
        self.TOP, self.FS = [], []                              # top layer (plate / bug, band), face strap layer
        self.fs_states = []                                     # [(t, Strap, mode)]
        self.switches = []
        self._ids = {}

    # ------------------------------------------------------------ words / timeline primitives
    def t(self, word, n=1):
        """onset of the n-th word equal to `word` (punctuation and case ignored)"""
        k = lambda s: re.sub(r"[^\w-]", "", s.lower())
        c = 0
        for w, a, _ in self.W:
            if k(w) == k(word):
                c += 1
                if c == n:
                    return a
        raise KeyError(f"{word!r} #{n} not in the words")

    def tset(self, sel, props, t):
        self.JS.append(f'tl.set("{sel}", {json.dumps(props, ensure_ascii=False)}, {fr(t):.4f});')

    def tween(self, sel, frm, to, t):
        self.JS.append(f'tl.fromTo("{sel}", {json.dumps(frm, ensure_ascii=False)}, '
                       f'{json.dumps({**to, "immediateRender": False}, ensure_ascii=False)}, {fr(t):.4f});')

    def origin(self, sel, ox, oy):
        """GSAP svgOrigin (parent coordinates) for scale / rotation of an SVG group"""
        self.PRE.append(f"gsap.set('{sel}', {{svgOrigin: '{ox:.1f} {oy:.1f}'}});")

    def beat(self, bid, kind, t0, t1, label, keys):
        self.BEATS.append({"id": bid, "type": kind, "label": label, "t0": round(t0, 3), "t1": round(t1, 3),
                           "keys": [round(k, 3) for k in keys]})

    def sfx(self, name, t, vol, dur=None):
        """a library sound where something enters (library/sfx/<name>.wav); never a music bed"""
        man = json.load(open(f"{SKILL}/library/sfx/manifest.json", encoding="utf-8"))
        e = man.get(name)
        if e is None or e.get("licensed") is False:
            raise ValueError(f"{name}: not a licensed library sound (no YouTube rips in this recipe)")
        os.makedirs(f"{self.P}/assets/sfx", exist_ok=True)
        dst = f"{self.P}/assets/sfx/{name}.wav"
        if not os.path.exists(dst):
            shutil.copy(f"{SKILL}/library/sfx/{e.get('file', name + '.wav')}", dst)
        self.SFX.append((name, max(0.0, t), vol, dur))

    # ------------------------------------------------------------ the speaker's face (as shot)
    def plates(self, switches):
        """[(t, key)]: which of the speaker's framings shows from t (switch on their own jump cuts: a shot-size change)"""
        self.switches = switches
        for t, p in switches:
            for k in self.plates_:
                self.tset(f"#v{k}", {"autoAlpha": 1 if k == p else 0}, t)

    def face(self, t0, t1):
        """a window where the speaker's face shows (cards are off); used for the face share and the beats"""
        self.FACE.append((t0, t1))
        self.beat(f"face{len(self.FACE)}", "face", t0, t1, "the face as shot + strap", [t0 + 0.35, (t0 + t1) / 2])

    # ------------------------------------------------------------ the strap (package part, per picture)
    def strap_svg(self, st, pid, vis=True):
        """-> (static body svg, tab svg, text svg (inside the clip), source svg) for one strap state"""
        S = LP["strap"]
        x0, x1, ew = S["x0"], S["x1"], S["end_w"]
        by, bh, ty, th = S["body_y"], S["body_h"], S["tab_y"], S["tab_h"]
        body = (f'<rect x="{x0 + 8}" y="{by + 8}" width="{x1 + ew - x0}" height="{bh}" fill="rgba(0,0,0,.3)"/>'
                f'<rect x="{x0}" y="{by}" width="{x1 - x0}" height="{bh}" fill="{PAL["paper"]}"/>'
                f'<rect x="{x0}" y="{by}" width="14" height="{bh}" fill="{PAL["lemon"]}"/>'
                f'<rect x="{x1}" y="{by}" width="{ew}" height="{bh}" fill="{PAL["ink"]}"/>'
                f'<rect x="{x1}" y="{by}" width="{ew}" height="6" fill="{PAL["lemon"]}"/>'
                + txt(self.channel, x1 + ew / 2, by + bh / 2 + 17, "c8", 48, PAL["lemon"], "middle", 1))
        tw_ = adv(st.tab, "c8", 48, 2) + 40
        tab = (f'<g id="{pid}_tab"{"" if vis else HID}><rect id="{pid}_tabr" x="{x0}" y="{ty}" width="{tw_:.0f}" height="{th}" fill="{PAL["lemon"]}"/>'
               + txt(st.tab, x0 + 20, ty + th / 2 + 17, "c8", 48, PAL["ink"], ls=2) + "</g>")
        hx = S["text_x"] - (x0 + 14)                          # inside the clip viewport (origin x0 + 14, by)
        if st.sub:
            hs = fit(st.head, "s8", TY["sizes"]["strap_head"], S["text_w"], floor=50)
            ss = fit(st.sub, "c6", TY["sizes"]["strap_sub"], S["text_w"], 1.5)
            tx = (txt(st.head, hx, S["head_y"] - by, "s8", hs, PAL["ink"]) +
                  txt(st.sub, hx + 2, S["sub_y"] - by, "c6", ss, PAL["olive"], ls=1.5))
        else:
            hs = fit(st.head, "s8", 64, S["text_w"], floor=50)
            tx = txt(st.head, hx, S["head_y_solo"] - by, "s8", hs, PAL["ink"])
        src = ""
        if st.source:
            sw = adv(st.source, "mono", 48, 3) + 46
            rx = S["x1"] + ew - sw
            src = (f'<g id="{pid}_src"{"" if vis else HID}><rect x="{rx:.0f}" y="{S["src_y"] - 52}" width="{sw:.0f}" height="72" fill="rgba(18,20,23,.82)"/>'
                   f'<rect x="{rx:.0f}" y="{S["src_y"] - 52}" width="8" height="72" fill="{PAL["gold"]}"/>'
                   + txt(st.source, S["x1"] + ew - 16, S["src_y"], "mono", 48, PAL["gold"], "end", 3) + "</g>")
        return body, tab, tx, src

    def strap_clip(self, inner):
        S = LP["strap"]
        x = S["x0"] + 14
        return (f'<svg x="{x}" y="{S["body_y"]}" width="{S["x1"] - x}" height="{S["body_h"]}" viewBox="0 0 {S["x1"] - x} {S["body_h"]}" '
                f'overflow="hidden">{inner}</svg>')

    def face_strap(self, t, st, mode="set"):
        """the strap on the face layer changes to `st` at t: "enter" (slides in from the left, the first story),
        "set" (instant: under a card or on a hard cut / wipe start, so the new picture brings its own words),
        "flip" (on the face: new words up from below, old up and out, 0.32 s; the tab flashes white on a new category)"""
        self.fs_states.append((t, st, mode))

    def _face_strap_build(self):
        if not self.fs_states:
            return
        body = None
        tabs, texts, srcs = [], [], []
        for i, (t, st, mode) in enumerate(self.fs_states):
            b, tab, tx, src = self.strap_svg(st, f"fs{i}", vis=False)
            body = body or b
            tabs.append(tab)
            texts.append(f'<g id="fs{i}_tx" opacity="0">{tx}</g>')
            srcs.append(src)
        self.FS.append(f'<g id="fs" opacity="0">{body}{"".join(tabs)}{self.strap_clip("".join(texts))}{"".join(srcs)}</g>')
        bh = LP["strap"]["body_h"]
        for i, (t, st, mode) in enumerate(self.fs_states):
            prev = self.fs_states[i - 1][1] if i else None
            p = f"#fs{i - 1}" if i else None
            if mode == "enter":
                self.tset("#fs", {"opacity": 1}, t)
                self.tween("#fs", {"x": -1000}, {"x": 0, "ease": "power3.out", "duration": 0.35}, t)
            new_tab = prev is None or prev.tab != st.tab
            if mode == "flip":
                self.tset(f"#fs{i}_tx", {"opacity": 1}, t)
                self.tween(f"#fs{i}_tx", {"y": bh}, {"y": 0, "ease": "power3.out", "duration": 0.32}, t)
                if p:
                    self.tween(f"{p}_tx", {"y": 0}, {"y": -bh, "ease": "power2.in", "duration": 0.32}, t)
                    self.tset(f"{p}_tx", {"opacity": 0}, t + 0.32)
            else:
                self.tset(f"#fs{i}_tx", {"opacity": 1, "y": 0}, t)
                if p:
                    self.tset(f"{p}_tx", {"opacity": 0}, t)
            if p:
                self.tset(f"{p}_tab", {"opacity": 0}, t)
                if prev.source:
                    self.tset(f"{p}_src", {"opacity": 0}, t)
            self.tset(f"#fs{i}_tab", {"opacity": 1}, t)
            if st.source:
                self.tset(f"#fs{i}_src", {"opacity": 1}, t)
            if mode == "flip" and new_tab:
                self.tset(f"#fs{i}_tabr", {"attr": {"fill": "#FFFFFF"}}, t)
                self.tset(f"#fs{i}_tabr", {"attr": {"fill": PAL["lemon"]}}, t + 3 * F1)

    # ------------------------------------------------------------ the sting and the bug (one object)
    def plate_svg(self, pid, w, h, word, glint=True, hide_letters=False):
        """the brand plate centred on (0, 0): parallelogram, lemon gradient, ink + gold bars, the channel word in c8"""
        k = h * 0.28
        gx = -w / 2 - k
        pts = lambda P: " ".join(f"{x:.1f},{y:.1f}" for x, y in P)
        s = [f'<linearGradient id="{pid}_g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PAL["lemonL"]}"/>'
             f'<stop offset="1" stop-color="{PAL["lemonD"]}"/></linearGradient>',
             f'<polygon points="{pts([(-w / 2 + k, -h / 2), (w / 2 + k, -h / 2), (w / 2 - k, h / 2), (-w / 2 - k, h / 2)])}" fill="url(#{pid}_g)"/>',
             f'<polygon points="{pts([(gx + 2 * k, -h / 2), (gx + 2 * k + w * .085, -h / 2), (gx + w * .085, h / 2), (gx, h / 2)])}" fill="{PAL["ink"]}"/>',
             f'<polygon points="{pts([(gx + 2 * k + w * .085, -h / 2), (gx + 2 * k + w * .11, -h / 2), (gx + w * .11, h / 2), (gx + w * .085, h / 2)])}" fill="{PAL["gold"]}"/>']
        size = h * TY["sizes"]["plate_letter_k"]
        size = min(size, size * (w * 0.70) / adv(word, "c8", size))
        x = -adv(word, "c8", size) / 2 + w * 0.05
        for i, L in enumerate(word):
            s.append(f'<g id="{pid}_L{i}"{HID if hide_letters else ""}>' + txt(L, x, h * 0.29, "c8", size, PAL["ink"]) + "</g>")
            x += adv(L, "c8", size) - h * 0.01
        if glint:
            g = 46
            s.append(f'<polygon id="{pid}_gl" opacity="0" points="{pts([(k, -h / 2), (k + g, -h / 2), (-k + g, h / 2), (-k, h / 2)])}" fill="rgba(255,255,255,.55)"/>')
        return "".join(s), size

    def sting(self, t0, t1, word, wordmark, dateline, hi=None):
        """S1 sting -> bug (native move 1): slashes, the plate slams in with a ring, letters drop one by one, the wordmark
        opens from the centre, a glint, then the plate flies to the top right and stays there as the bug. Its card is
        [t0, t1]; wipe(t1 - 0.30, out_of=...) reveals the next picture while the plate flies."""
        self.channel = word
        sp, bug = LP["sting_plate"], LP["bug"]
        c = self.card("sting", t0, t1, strap=None)
        for j, (a, hh, dy) in enumerate([(0.0, 26, -70), (0.04, 10, 46)]):
            c.add(f'<g transform="rotate(-8 540 {sp["cy"] + dy})"><rect id="sting_sl{j}" x="-700" y="{sp["cy"] + dy - hh / 2}" '
                  f'width="1400" height="{hh}" fill="{PAL["lemon"]}"/></g>')
            self.tween(f"#sting_sl{j}", {"x": -1400}, {"x": 1900, "ease": "power2.inOut", "duration": 0.26}, t0 + a)
        c.add(f'<ellipse id="sting_ring" cx="540" cy="{sp["cy"]}" rx="300" ry="120" fill="none" stroke="{PAL["lemon"]}" stroke-width="6" opacity="0"/>')
        self.tween("#sting_ring", {"attr": {"rx": 320, "ry": 130, "stroke-width": 7}, "opacity": 1},
                   {"attr": {"rx": 1000, "ry": 420, "stroke-width": 1}, "opacity": 0, "ease": "power2.out", "duration": 0.4}, t0 + 0.16)
        # wordmark + dateline open from the centre (a nested viewport whose width grows)
        wm_y = sp["cy"] + sp["h"] / 2 + 150
        parts = []
        x = 540 - adv(wordmark, "c8", 96, 13) / 2
        hi = hi or []
        for wd in wordmark.split(" "):
            parts.append(txt(wd, x, wm_y, "c8", 96, PAL["lemon"] if wd in hi else PAL["white"], ls=13))
            x += adv(wd + " ", "c8", 96, 13)
        parts.append(txt(dateline, 540, wm_y + 90, "mono", 48, PAL["gold"], "middle", 3))
        c.add(f'<svg id="sting_wm" x="540" y="{wm_y - 110}" width="0" height="240" viewBox="0 0 0 240" overflow="hidden" '
              f'preserveAspectRatio="none"><g id="sting_wmi">' + "".join(parts) + "</g></svg>")
        # the nested viewport is in its own coordinates: shift the content by -x, -y with the viewport
        self.tween("#sting_wm", {"attr": {"x": 540, "width": 0, "viewBox": f"540 {wm_y - 110} 0 240"}},
                   {"attr": {"x": 0, "width": 1080, "viewBox": f"0 {wm_y - 110} 1080 240"}, "ease": "power3.out", "duration": 0.22}, t0 + 0.26)
        self.tween("#sting_wm", {"opacity": 1}, {"opacity": 0, "duration": 0.1}, t0 + 0.62)
        # the plate: one object from the sting to the bug (top layer)
        svg, lsize = self.plate_svg("plt", sp["w"], sp["h"], word, hide_letters=True)
        self.TOP.append(f'<g id="plt">{svg}</g>')
        self.origin("#plt", 0, 0)
        self.tset("#plt", {"x": sp["cx"], "y": sp["cy"], "scale": 1.35, "rotation": -3}, t0)
        self.tween("#plt", {"scale": 1.35, "rotation": -3}, {"scale": 1, "rotation": 0, "ease": "back.out(2.2)", "duration": 0.22}, t0)
        for i in range(len(word)):
            self.tween(f"#plt_L{i}", {"y": -sp["h"] * 1.1, "opacity": 0},
                       {"y": 0, "opacity": 1, "ease": "power3.out", "duration": 0.14}, t0 + 0.02 + 0.05 * i)
        self.tset("#plt_gl", {"opacity": 1}, t0 + 0.45)
        self.tween("#plt_gl", {"x": -sp["w"] / 2 + sp["w"] * 0.11}, {"x": sp["w"] / 2 - 46, "ease": "power1.inOut", "duration": 0.23}, t0 + 0.45)
        self.tset("#plt_gl", {"opacity": 0}, t0 + 0.68)
        fly = t1 - 0.30
        self.tween("#plt", {"x": sp["cx"], "y": sp["cy"], "scale": 1},
                   {"x": bug["cx"], "y": bug["cy"], "scale": bug["scale"], "ease": "power2.inOut", "duration": 0.30}, fly)
        if lsize * bug["scale"] < FLOOR:
            raise ValueError(f"bug letters {lsize * bug['scale']:.0f} px < {FLOOR}: raise the bug scale or shorten the word")
        self.beat("sting", "sting", t0, t1, "sting: plate slam, letters, wordmark, flies to the bug",
                  [t0, t0 + 0.12, t0 + 0.4, t0 + 0.6, fly + 0.15])
        return c

    # ------------------------------------------------------------ cards and the band wipe
    def card(self, name, t0, t1, strap=None, tag=None, bg=True):
        """a full-frame package card [t0, t1] (edit s) on the studio background, with its own strap state (the package
        layer travels with its picture) and an optional corner tag (SCHEMATIC for schematic graphics)"""
        c = Card(self, name, t0, t1, 10 + len(self.CARDS), strap, tag, bg)
        self.CARDS.append(c)
        return c

    def wipe(self, t, into=None, out_of=None, dur=0.30):
        """the band wipe (lemon 84 + ink 5 + gold 14 px) left to right in `dur`; `into` (a card) is revealed left of the
        band; `out_of` (a card) is hidden left of the band, uncovering what lies under it (the face or a lower card)"""
        e = {"ease": "power2.inOut", "duration": dur}
        self.tset("#band", {"opacity": 1}, t)
        self.tween("#band", {"x": -140}, {"x": 1220, **e}, t)
        self.tset("#band", {"opacity": 0}, t + dur)
        poly_l = lambda b: f"polygon(-200px 0px, {b}px 0px, {b}px 1920px, -200px 1920px)"
        poly_r = lambda b: f"polygon({b}px 0px, 1300px 0px, 1300px 1920px, {b}px 1920px)"
        if into:
            self.tween(f"#{into}", {"clipPath": poly_l(-140)}, {"clipPath": poly_l(1220), **e}, t)
        if out_of:
            self.tween(f"#{out_of}", {"clipPath": poly_r(-140)}, {"clipPath": poly_r(1220), **e}, t)

    # ------------------------------------------------------------ package parts used inside cards
    def corner_tag(self, c, label):
        T = LP["corner_tag"]
        w = adv(label, "mono", 48, 3) + 60
        c.add(f'<rect x="{T["x"]}" y="{T["y"]}" width="{w:.0f}" height="{T["h"]}" fill="rgba(18,20,23,.82)"/>'
              f'<rect x="{T["x"]}" y="{T["y"]}" width="8" height="{T["h"]}" fill="{PAL["gold"]}"/>'
              + txt(label, T["x"] + 30, T["y"] + T["h"] / 2 + 17, "mono", 48, PAL["gold"], ls=3))

    def eyebrow(self, c, s, y, t=None, x=60):
        """mono caps gold line (source / date / label) above a graphic"""
        tid = c.id(f"eb{len(c.parts)}")
        c.add(txt(s, x, y, "mono", 48, PAL["gold"], ls=3, tid=tid))
        if t is not None:
            self.tween(f"#{tid}", {"opacity": 0}, {"opacity": 1, "duration": 0.2}, t)

    def push_text(self, c, s, x, y, key, size, fill, t, maxw=None, anchor="start", ls=0.0):
        """a title pushed up from a mask (nested viewport): starts fully below, 0.32 s power3.out"""
        if maxw:
            size = fit(s, key, size, maxw, ls)
        gid = c.id(f"pt{len(c.parts)}")
        top = y - size * 1.05
        hh = size * 1.35
        c.add(f'<svg x="0" y="{top:.1f}" width="1080" height="{hh:.1f}" viewBox="0 {top:.1f} 1080 {hh:.1f}" overflow="hidden">'
              f'<g id="{gid}" opacity="0">' + txt(s, x, y, key, size, fill, anchor, ls) + "</g></svg>")
        self.tset(f"#{gid}", {"opacity": 1}, t)
        self.tween(f"#{gid}", {"y": hh}, {"y": 0, "ease": "power3.out", "duration": 0.32}, t)
        return size

    def stamp(self, c, words, cx, cy, t, rot=-8, size=None):
        """the verdict stamp (one per story at most): ink fill with a double lemon frame, c8 caps (first word lemon, the
        rest paper), lands from x1.9 in 0.16 s with an expanding ellipse"""
        size = size or TY["sizes"]["stamp"]
        a, b = words
        wa, wb = adv(a, "c8", size, 1), adv(b, "c8", size, 3) if b else 0
        gap = 22 if b else 0
        tw_ = wa + gap + wb
        w2, h2 = tw_ / 2 + 44, size * 0.95
        sid = c.id(f"st{len(c.parts)}")
        s = (f'<g id="{sid}" opacity="0"><g transform="rotate({rot} {cx} {cy})">'
             f'<rect x="{cx - w2}" y="{cy - h2}" width="{2 * w2}" height="{2 * h2}" fill="rgba(18,20,23,.94)"/>'
             f'<rect x="{cx - w2 + 10}" y="{cy - h2 + 10}" width="{2 * w2 - 20}" height="{2 * h2 - 20}" fill="none" stroke="{PAL["lemon"]}" stroke-width="4"/>'
             f'<rect x="{cx - w2 + 18}" y="{cy - h2 + 18}" width="{2 * w2 - 36}" height="{2 * h2 - 36}" fill="none" stroke="{PAL["lemon"]}" stroke-width="1.5"/>'
             + txt(a, cx - tw_ / 2, cy + size * 0.35, "c8", size, PAL["lemon"], ls=1)
             + (txt(b, cx - tw_ / 2 + wa + gap, cy + size * 0.35, "c8", size, PAL["paper"], ls=3) if b else "")
             + "</g></g>"
             f'<ellipse id="{sid}_r" cx="{cx}" cy="{cy}" rx="{w2}" ry="{h2 * 1.3:.0f}" fill="none" stroke="{PAL["lemon"]}" stroke-width="3" opacity="0" transform="rotate({rot} {cx} {cy})"/>')
        c.add(s)
        self.origin(f"#{sid}", cx, cy)
        self.tween(f"#{sid}", {"scale": 1.9, "opacity": 0}, {"scale": 1, "opacity": 1, "ease": "power3.out", "duration": 0.16}, t)
        self.tween(f"#{sid}_r", {"attr": {"rx": w2, "ry": h2 * 1.3}, "opacity": 0.8},
                   {"attr": {"rx": w2 + 160, "ry": h2 * 1.3 + 60}, "opacity": 0, "ease": "power2.out", "duration": 0.45}, t + 0.05)

    # ------------------------------------------------------------ the rundown (opens, and comes back ticked off)
    def rundown(self, c, rows, tab, big, unit, mono, title, t_in, close=False, ticks=None, highlight=None):
        """native move 3. rows: [(num, title, timecode)] (the timecode = when that point airs in the reel, mono). Open: the
        tab, the big number, the unit, the mono line and the title push up, then the rows flip in on their times
        (t_in: [row times]); highlight: time the first row gets its outline. close=True: everything is there, each row
        is ticked on its time (ticks)."""
        R = LP["rundown"]
        x = 60
        tw_ = adv(tab, "c8", 48, 2) + 40
        tid = c.id("rtab")
        c.add(f'<g id="{tid}"><rect x="{x}" y="{R["tab_y"]}" width="{tw_:.0f}" height="68" fill="{PAL["lemon"]}"/>'
              + txt(tab, x + 20, R["tab_y"] + 51, "c8", 48, PAL["ink"], ls=2) + "</g>")
        if close:
            c.add(txt(big, x - 6, R["big_y"], "c8", 280, PAL["white"], ls=2))
            c.add(txt(unit, x + adv(big, "c8", 280, 2) + 24, R["big_y"], "c8", 110, PAL["lemon"], ls=4))
            c.add(txt(mono, x, R["mono_y"], "mono", 48, PAL["gold"], ls=3))
            c.add(txt(title, x, R["title_y"], "s8", fit(title, "s8", 64, 920), PAL["white"]))
        else:
            t0 = c.t0
            self.tween(f"#{tid}", {"scaleX": 0}, {"scaleX": 1, "ease": "power3.out", "duration": 0.25}, t0 + 0.05)
            self.origin(f"#{tid}", x, R["tab_y"])
            self.push_text(c, big, x - 6, R["big_y"], "c8", 280, PAL["white"], t0 + 0.12, ls=2)
            self.push_text(c, unit, x + adv(big, "c8", 280, 2) + 24, R["big_y"], "c8", 110, PAL["lemon"], t0 + 0.2, ls=4)
            self.eyebrow(c, mono, R["mono_y"], t0 + 0.3)
            self.push_text(c, title, x, R["title_y"], "s8", 64, PAL["white"], t0 + 0.3, maxw=920)
        rw, nw, rh = R["row_w"], R["num_w"], R["row_h"]
        tsize = min(fit(r[1], "c8", TY["sizes"]["row_title"], rw - nw - 30 - 120 - 96 - 14) for r in rows)
        for i, (num, ttl, tc) in enumerate(rows):
            y = R["rows_y"] + i * (rh + R["row_gap"])
            gid = c.id(f"row{i}")
            s = (f'<g id="{gid}"{"" if close else HID}>'
                 f'<rect x="{x + 10}" y="{y + 10}" width="{rw}" height="{rh}" fill="rgba(0,0,0,.35)"/>'
                 f'<rect x="{x}" y="{y}" width="{rw}" height="{rh}" fill="{PAL["ink2"]}"/>'
                 f'<rect x="{x}" y="{y}" width="{nw}" height="{rh}" fill="{PAL["lemon"]}"/>'
                 + txt(num, x + nw / 2, y + rh / 2 + 29, "c8", 84, PAL["ink"], "middle")
                 + txt(ttl, x + nw + 30, y + rh / 2 + tsize * 0.35, "c8", tsize, PAL["white"])
                 + txt(tc, x + rw - (96 if close else 26), y + rh / 2 + 17, "mono", 48, PAL["grey2"], "end"))
            if not close:
                s += (f'<linearGradient id="{gid}_sg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{PAL["lemon"]}" stop-opacity="0"/>'
                      f'<stop offset="1" stop-color="{PAL["lemon"]}" stop-opacity=".3"/></linearGradient>'
                      f'<rect id="{gid}_sw" x="{x + nw}" y="{y}" width="160" height="{rh}" fill="url(#{gid}_sg)" opacity="0"/>')
            s += "</g>"
            c.add(s)
            if close:
                cx, cy = x + rw - 46, y + rh / 2
                kid = c.id(f"tick{i}")
                c.add(f'<g id="{kid}" opacity="0"><circle cx="{cx}" cy="{cy}" r="32" fill="{PAL["lemon"]}"/>'
                      f'<polyline points="{cx - 14},{cy + 1} {cx - 3},{cy + 12} {cx + 16},{cy - 11}" fill="none" stroke="{PAL["ink"]}" '
                      f'stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></g>')
                self.origin(f"#{kid}", cx, cy)
                self.tween(f"#{kid}", {"scale": 0, "opacity": 1}, {"scale": 1, "opacity": 1, "ease": "back.out(2.6)", "duration": 0.22}, ticks[i])
            else:
                a = t_in[i]
                self.origin(f"#{gid}", x, y)
                self.tset(f"#{gid}", {"opacity": 1}, a)
                self.tween(f"#{gid}", {"scaleY": 0.02}, {"scaleY": 1, "ease": "back.out(2)", "duration": 0.3}, a)
                self.tset(f"#{gid}_sw", {"opacity": 1}, a + 0.05)
                self.tween(f"#{gid}_sw", {"x": 0}, {"x": rw - nw - 160, "ease": "power2.inOut", "duration": 0.4}, a + 0.05)
                self.tset(f"#{gid}_sw", {"opacity": 0}, a + 0.45)
        if highlight is not None and not close:
            y = R["rows_y"]
            hid = c.id("hl")
            c.add(f'<rect id="{hid}" x="{x - 4}" y="{y - 4}" width="{rw + 8}" height="{rh + 8}" fill="none" stroke="{PAL["lemon"]}" stroke-width="5" opacity="0"/>')
            self.origin(f"#{hid}", x - 4, y)
            self.tset(f"#{hid}", {"opacity": 1}, highlight)
            self.tween(f"#{hid}", {"scaleX": 0}, {"scaleX": 1, "ease": "power3.out", "duration": 0.25}, highlight)

    # ------------------------------------------------------------ full-frame graphics (the slots: new every reel)
    def document(self, c, href, box, t, src_xy=(540, 1300), rot=(-14, -3)):
        """a real document (the book the speaker names) flies out on an arc: scale 0.08 -> 1, rotation settles; box = (x, y, w, h)"""
        x, y, w, h = box
        did = c.id("doc")
        cx, cy = x + w / 2, y + h / 2
        c.add(f'<g id="{did}"><rect x="{x + 14}" y="{y + 16}" width="{w}" height="{h}" fill="rgba(0,0,0,.45)"/>'
              f'<image href="{href}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice"/>'
              f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{PAL["paper"]}" stroke-width="4"/></g>')
        self.origin(f"#{did}", cx, cy)
        self.tween(f"#{did}", {"x": src_xy[0] - cx}, {"x": 0, "ease": "power1.out", "duration": 0.5}, t)
        self.tween(f"#{did}", {"y": src_xy[1] - cy}, {"y": 0, "ease": "power3.out", "duration": 0.5}, t)
        self.tween(f"#{did}", {"scale": 0.08, "rotation": rot[0]}, {"scale": 1, "rotation": rot[1], "ease": "power2.out", "duration": 0.5}, t)
        return did

    def flap_board(self, c, old, new, x, y, tw_, th, t, gap=14, size=None):
        """native move 6: a split-flap board, old value and new value on the same tiles; every tile flips (top half folds
        down, bottom half unfolds), 0.05 s apart from t. old / new: strings of equal length (spaces = blank tiles)"""
        size = size or th * 0.72
        n = len(new)
        assert len(old) == n
        for i in range(n):
            tx_ = x + i * (tw_ + gap)
            hy = y + th / 2
            pid = c.id(f"fl{i}")

            def half(ch, top, extra_id=""):
                hh = th / 2
                vy = y if top else hy
                base = (hh + size * 0.35) if top else size * 0.35
                ii = f' id="{extra_id}"' if extra_id else ""
                ch_s = txt(ch, tw_ / 2, base, "c8", size, PAL["white"], "middle") if ch.strip() else ""
                return (f'<svg{ii} x="{tx_:.1f}" y="{vy:.1f}" width="{tw_}" height="{hh:.1f}" viewBox="0 0 {tw_} {hh:.1f}" overflow="hidden">'
                        f'<rect x="0" y="0" width="{tw_}" height="{hh:.1f}" rx="6" fill="{PAL["ink3"] if top else PAL["ink2"]}"/>{ch_s}</svg>')
            c.add(f'<rect x="{tx_ + 6:.1f}" y="{y + 8}" width="{tw_}" height="{th}" fill="rgba(0,0,0,.4)"/>')
            c.add(half(new[i], True))
            c.add(half(old[i], False))
            c.add(f'<g id="{pid}_bn" opacity="0">' + half(new[i], False) + "</g>")
            c.add(f'<g id="{pid}_ft">' + half(old[i], True) + "</g>")
            c.add(f'<g id="{pid}_fb" opacity="0">' + half(new[i], False) + "</g>")
            c.add(f'<rect x="{tx_:.1f}" y="{hy - 2:.1f}" width="{tw_}" height="4" fill="{PAL["ink"]}"/>')
            a = t + 0.05 * i
            self.origin(f"#{pid}_ft", tx_ + tw_ / 2, hy)
            self.origin(f"#{pid}_fb", tx_ + tw_ / 2, hy)
            self.tween(f"#{pid}_ft", {"scaleY": 1}, {"scaleY": 0, "ease": "power1.in", "duration": 0.08}, a)
            self.tset(f"#{pid}_fb", {"opacity": 1}, a + 0.08)
            self.tween(f"#{pid}_fb", {"scaleY": 0}, {"scaleY": 1, "ease": "power1.out", "duration": 0.08}, a + 0.08)
            self.tset(f"#{pid}_bn", {"opacity": 1}, a + 0.16)

    def check_rows(self, c, rows, y0, rh=110, gap=18, label="OFF"):
        """check rows (the source's documents with check boxes ticking on the voice's key words): ink2 rows with a lemon
        top edge flip in on their word; the box ticks 0.25 s later and the mono label lands. rows: [(text, t)]"""
        x, rw = 60, 920
        size = min(fit(s, "c8", 64, rw - 260) for s, _ in rows)
        for i, (s, t) in enumerate(rows):
            y = y0 + i * (rh + gap)
            gid = c.id(f"ck{i}")
            bx, by = x + rw - 100, y + (rh - 64) / 2 + 3
            c.add(f'<g id="{gid}" opacity="0"><rect x="{x + 8}" y="{y + 8}" width="{rw}" height="{rh}" fill="rgba(0,0,0,.35)"/>'
                  f'<rect x="{x}" y="{y}" width="{rw}" height="{rh}" fill="{PAL["ink2"]}"/>'
                  f'<rect x="{x}" y="{y}" width="{rw}" height="6" fill="{PAL["lemon"]}"/>'
                  + txt(s, x + 34, y + rh / 2 + size * 0.38, "c8", size, PAL["white"])
                  + f'<rect x="{bx}" y="{by}" width="64" height="64" fill="none" stroke="{PAL["lemon"]}" stroke-width="4"/></g>'
                  f'<g id="{gid}_k" opacity="0"><rect x="{bx}" y="{by}" width="64" height="64" fill="{PAL["lemon"]}"/>'
                  f'<polyline points="{bx + 15},{by + 33} {bx + 27},{by + 46} {bx + 50},{by + 18}" fill="none" stroke="{PAL["ink"]}" stroke-width="8" '
                  f'stroke-linecap="round" stroke-linejoin="round"/>'
                  + txt(label, bx - 24, y + rh / 2 + 17, "mono", 48, PAL["gold"], "end", 3) + "</g>")
            self.origin(f"#{gid}", x, y)
            self.tset(f"#{gid}", {"opacity": 1}, t)
            self.tween(f"#{gid}", {"scaleY": 0.02}, {"scaleY": 1, "ease": "back.out(2)", "duration": 0.28}, t)
            self.origin(f"#{gid}_k", bx + 32, by + 32)
            self.tset(f"#{gid}_k", {"opacity": 1}, t + 0.25)
            self.tween(f"#{gid}_k", {"scale": 1.6}, {"scale": 1, "ease": "back.out(2.6)", "duration": 0.2}, t + 0.25)

    def accent_cards(self, c, items, y0, ch=200, gap=30, w=820):
        """accent-edged ink cards (ink2, 6 px lemon top edge), each pushed up from its own mask on its word, a mono
        index, one big word (c8) and a line icon drawn in lemon. items: [(index, word, icon svg (local 0..120 box), t)]"""
        x = 60
        size = min(fit(wd, "c8", TY["sizes"]["card_word"], w - 70 - 170) for _, wd, _, _ in items)
        for i, (idx, wd, icon, t) in enumerate(items):
            y = y0 + i * (ch + gap)
            gid = c.id(f"ac{i}")
            c.add(f'<svg x="{x}" y="{y}" width="{w + 12}" height="{ch + 12}" viewBox="0 0 {w + 12} {ch + 12}" overflow="hidden">'
                  f'<g id="{gid}" opacity="0"><rect x="10" y="10" width="{w}" height="{ch}" fill="rgba(0,0,0,.35)"/>'
                  f'<rect x="0" y="0" width="{w}" height="{ch}" fill="{PAL["ink2"]}"/><rect x="0" y="0" width="{w}" height="6" fill="{PAL["lemon"]}"/>'
                  + txt(idx, 34, 74, "mono", 48, PAL["gold"], ls=3)
                  + txt(wd, 34, ch - 38, "c8", size, PAL["white"])
                  + f'<g transform="translate({w - 160},{(ch - 120) / 2 + 6})">{icon}</g></g></svg>')
            self.tset(f"#{gid}", {"opacity": 1}, t)
            self.tween(f"#{gid}", {"y": ch + 12}, {"y": 0, "ease": "power3.out", "duration": 0.32}, t)

    def bracket(self, c, x, y0, y1, t, reach=36):
        """a gold bracket joining a group to its total (spec-card move), drawn on in 0.3 s"""
        bid = c.id(f"br{len(c.parts)}")
        L = 2 * reach + (y1 - y0) + reach / 2
        ym = (y0 + y1) / 2
        c.add(f'<path id="{bid}" d="M{x - reach},{y0} H{x} V{y1} H{x - reach} M{x},{ym} H{x + reach / 2}" fill="none" stroke="{PAL["gold"]}" '
              f'stroke-width="5" stroke-dasharray="{L:.0f}" stroke-dashoffset="{L:.0f}"/>')
        self.tween(f"#{bid}", {"attr": {"stroke-dashoffset": L}}, {"attr": {"stroke-dashoffset": 0}, "ease": "power2.out", "duration": 0.3}, t)

    def threshold(self, c, pts, steps, thr_y, thr_label, box, cross_t, readout=None, readout_t=None):
        """native move 7 (schematic: no numbers): a line advances one step per word towards a dashed gold threshold; the
        last step crosses it in lemon with a shake and a ring. pts: [(x, y)]; steps: time each segment i -> i+1 draws
        (the last one is the crossing, at cross_t). box = (x0, y0, x1, y1) of the axes. readout: (line1, line2) lemon
        panel sliding in at readout_t."""
        x0, y0, x1, y1 = box
        gid = c.id("thr")
        s = [f'<g id="{gid}">',
             f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{PAL["line"]}" stroke-width="3"/>',
             f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{PAL["line"]}" stroke-width="3"/>',
             f'<line x1="{x0}" y1="{thr_y}" x2="{x1}" y2="{thr_y}" stroke="{PAL["gold"]}" stroke-width="4" stroke-dasharray="18 12"/>',
             txt(thr_label, x0 + 14, thr_y - 24, "mono", 48, PAL["gold"], "start", 3)]
        n = len(pts) - 1
        for i in range(n):
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            last = i == n - 1
            s.append(f'<line id="{gid}_s{i}" x1="{ax}" y1="{ay}" x2="{ax}" y2="{ay}" stroke="{PAL["lemon"] if last else PAL["paper"]}" '
                     f'stroke-width="{9 if last else 6}" stroke-linecap="round" opacity="0"/>')
        hx, hy = pts[0]
        s.append(f'<circle id="{gid}_hd" cx="{hx}" cy="{hy}" r="12" fill="{PAL["paper"]}"/>')
        s.append(f'<ellipse id="{gid}_rg" cx="{pts[-1][0]}" cy="{pts[-1][1]}" rx="20" ry="20" fill="none" stroke="{PAL["lemon"]}" stroke-width="5" opacity="0"/>')
        s.append("</g>")
        c.add("".join(s))
        for i in range(n):
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            t = steps[i]
            d = min(0.12, fr(steps[i + 1]) - fr(t) - F1) if i < n - 1 else 0.10
            self.tset(f"#{gid}_s{i}", {"opacity": 1}, t)
            self.tween(f"#{gid}_s{i}", {"attr": {"x2": ax, "y2": ay}}, {"attr": {"x2": bx, "y2": by}, "ease": "power1.out", "duration": d}, t)
            self.tween(f"#{gid}_hd", {"attr": {"cx": ax, "cy": ay}}, {"attr": {"cx": bx, "cy": by}, "ease": "power1.out", "duration": d}, t)
        self.tset(f"#{gid}_hd", {"attr": {"fill": PAL["lemon"]}}, cross_t)
        for j, dx in enumerate([16, -13, 10, -8, 6, -4, 3, -1, 0]):
            self.tset(f"#{gid}", {"x": dx}, cross_t + j * F1)
        self.tween(f"#{gid}_rg", {"attr": {"rx": 20, "ry": 20}, "opacity": 1},
                   {"attr": {"rx": 220, "ry": 140}, "opacity": 0, "ease": "power2.out", "duration": 0.45}, cross_t + 0.05)
        if readout:
            rx, ry, rw, rh = readout["box"]
            rid = c.id("ro")
            size = min(fit(l, "c8", 84, rw - 90) for l in readout["lines"])
            c.add(f'<svg x="{rx}" y="{ry}" width="{rw + 12}" height="{rh + 12}" viewBox="0 0 {rw + 12} {rh + 12}" overflow="hidden">'
                  f'<g id="{rid}" opacity="0"><rect x="0" y="0" width="{rw}" height="{rh}" fill="{PAL["ink2"]}"/>'
                  f'<rect x="0" y="0" width="{rw}" height="6" fill="{PAL["lemon"]}"/>'
                  + "".join(txt(l, 30, 3 + (rh - len(readout["lines"]) * size * 0.98) / 2 + size * 0.78 + j * size * 0.98, "c8", size, PAL["lemon"]) for j, l in enumerate(readout["lines"]))
                  + "</g></svg>")
            self.tset(f"#{rid}", {"opacity": 1}, readout_t)
            self.tween(f"#{rid}", {"x": rw + 12}, {"x": 0, "ease": "power3.out", "duration": 0.3}, readout_t)

    def proportion(self, c, label, part, rest, box, frac0, frac1, t_draw, t_shrink, flash_t=None, rest_t=None):
        """the spec card's one-scale bar (schematic, no numbers): a whole (label) split into `part` (ink3, the thing that
        takes the space) and `rest` (lemon, what is left); draws at t_draw with the part at frac0, the part shrinks to
        frac1 at t_shrink (0.4 s) and the rest label lands. Returns the x centre of the rest at the end (for a bracket)."""
        x, y, w, h = box
        gid = c.id("pr")
        self.eyebrow(c, label, y - 30, t_draw)
        p0, p1 = w * frac0, w * frac1
        psize = fit(part, "c8", 64, p1 - 40)
        rsize = fit(rest, "c8", 60, w - p1 - 40)
        c.add(f'<rect id="{gid}_bg" x="{x}" y="{y}" width="0" height="{h}" fill="{PAL["lemon"]}"/>'
              f'<rect id="{gid}_p" x="{x}" y="{y}" width="0" height="{h}" fill="{PAL["ink3"]}" stroke="{PAL["line"]}" stroke-width="2"/>'
              + f'<g id="{gid}_pl" opacity="0">' + txt(part, x + 24, y + h / 2 + psize * 0.35, "c8", psize, PAL["white"]) + "</g>"
              + f'<g id="{gid}_rl" opacity="0">' + txt(rest, x + w - 24, y + h / 2 + rsize * 0.35, "c8", rsize, PAL["ink"], "end") + "</g>")
        self.tween(f"#{gid}_bg", {"attr": {"width": 0}}, {"attr": {"width": w}, "ease": "power3.out", "duration": 0.45}, t_draw)
        self.tween(f"#{gid}_p", {"attr": {"width": 0}}, {"attr": {"width": p0}, "ease": "power3.out", "duration": 0.45}, t_draw)
        self.tset(f"#{gid}_pl", {"opacity": 1}, t_draw + 0.3)
        if flash_t is not None:
            self.tset(f"#{gid}_p", {"attr": {"fill": "#4A505A"}}, flash_t)
            self.tset(f"#{gid}_p", {"attr": {"fill": PAL["ink3"]}}, flash_t + 3 * F1)
        self.tween(f"#{gid}_p", {"attr": {"width": p0}}, {"attr": {"width": p1}, "ease": "power2.inOut", "duration": 0.4}, t_shrink)
        self.tset(f"#{gid}_rl", {"opacity": 1}, rest_t if rest_t is not None else t_shrink + 0.3)
        return gid, x + p0 + (w - p0) / 2, x + p1 + (w - p1) / 2

    def cells(self, c, words, x, y, cw, ch, cols, t0, every=0.12, gap=20):
        """a group filling cell by cell (spec card): ink2 cells with a lemon top edge, one c8 word each, popping in"""
        size = min(fit(wd, "c8", 72, cw - 60) for wd in words)
        for i, wd in enumerate(words):
            cx_, cy_ = x + (i % cols) * (cw + gap), y + (i // cols) * (ch + gap)
            gid = c.id(f"cl{i}")
            c.add(f'<g id="{gid}" opacity="0"><rect x="{cx_}" y="{cy_}" width="{cw}" height="{ch}" fill="{PAL["ink2"]}"/>'
                  f'<rect x="{cx_}" y="{cy_}" width="{cw}" height="6" fill="{PAL["lemon"]}"/>'
                  + txt(wd, cx_ + 30, cy_ + ch / 2 + size * 0.38, "c8", size, PAL["white"]) + "</g>")
            self.origin(f"#{gid}", cx_ + cw / 2, cy_ + ch / 2)
            self.tset(f"#{gid}", {"opacity": 1}, t0 + i * every)
            self.tween(f"#{gid}", {"scale": 0.6}, {"scale": 1, "ease": "back.out(2)", "duration": 0.22}, t0 + i * every)

    # ------------------------------------------------------------ write
    def _card_html(self, c):
        S = []
        if c.bg:
            S.append(f'<image href="{self.bgpng}" x="0" y="0" width="1080" height="1920"/>')
            bands = []
            for i in range(7):
                h1 = ((i * 127.1 + 311.7) * 43758.5453) % 1
                h2 = (((i + 9) * 127.1 + 311.7) * 43758.5453) % 1
                bx, bw = i * 260 - 300, 40 + h1 * 120
                bands.append(f'<polygon points="{bx},0 {bx + bw:.0f},0 {bx + bw - 900:.0f},1920 {bx - 900},1920" fill="{PAL["lemon"]}" opacity="{0.025 + h2 * 0.035:.3f}"/>')
            S.append(f'<g id="{c.name}_bands">' + "".join(bands) + "</g>")
            self.tween(f"#{c.name}_bands", {"x": 0}, {"x": 40 * (c.t1 - c.t0), "ease": "none", "duration": c.t1 - c.t0}, c.t0)
        if c.tag:
            self.corner_tag(c, c.tag)
        S += c.parts
        if c.strap:
            body, tab, tx, src = self.strap_svg(c.strap, f"{c.name}_sp")
            S.append(body + tab + self.strap_clip(tx) + src)
        return (f'<section id="{c.name}" class="clip full" data-start="{fr(c.t0):.4f}" data-duration="{fr(c.t1) - fr(c.t0):.4f}" '
                f'data-track-index="{c.z}" style="z-index:{c.z}">'
                f'<svg class="full" viewBox="0 0 1080 1920" width="1080" height="1920">{"".join(S)}</svg></section>')

    def build(self):
        """-> index.html, build/beats.json, build/coverage.txt"""
        P, DUR = self.P, self.dur
        self._face_strap_build()
        cards = [self._card_html(c) for c in self.CARDS]       # after the face strap (its JS) and before writing
        faces = "".join(f"@font-face {{ font-family: '{f[0]}'; src: "
                        + (f"url('assets/fonts/{f[3]}.ttf') format('truetype'); " if f[3] in WHOLE
                           else f"url('assets/fonts/{f[3]}-{sub}.woff2') format('woff2'); ")
                        + f"font-weight: {f[1]}; font-style: {f[2]}; font-display: block; unicode-range: {UNI[sub]}; }}\n"
                        for f in FAM.values() for sub in ("cyrillic", "latin"))
        first = self.switches[0][1] if self.switches else next(iter(self.plates_))
        vids = "\n".join(f'<video id="v{k}" class="full" src="{v}" data-start="0" data-duration="{DUR:.3f}" data-track-index="{i}" muted playsinline'
                         f'{"" if k == first else HIDV}></video>'
                         for i, (k, v) in enumerate(self.plates_.items()))
        aud = [f'<audio id="vo" src="{self.voice}" data-start="0" data-duration="{min(self.voice_dur, DUR):.3f}" data-track-index="40" data-volume="1"></audio>']
        for i, (f, t, v, dur) in enumerate(self.SFX):
            dd = dur or SFX_LEN.get(f) or round(probe_dur(f"{P}/assets/sfx/{f}.wav"), 3)
            SFX_LEN[f] = dd
            dd = min(dd, DUR - t)
            aud.append(f'<audio id="sfx{i}" src="assets/sfx/{f}.wav" data-start="{fr(t):.4f}" data-duration="{dd:.4f}" '
                       f'data-track-index="{50 + i}" data-volume="{v}"></audio>')
        html = f"""<!doctype html>
<html lang="{self.lang}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{esc(self.page_title)}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{faces}html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
.full {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }}
svg.full {{ overflow: visible; }}
video.full {{ object-fit: cover; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{DUR:.3f}" data-fps="{FPS}">
<div id="cam" class="full" style="z-index:1">
{vids}
</div>
<div id="fsl" class="full" style="z-index:5"><svg class="full" viewBox="0 0 1080 1920" width="1080" height="1920">{"".join(self.FS)}</svg></div>
{chr(10).join(cards)}
<div id="bandl" class="full" style="z-index:90"><svg class="full" viewBox="0 0 1080 1920" width="1080" height="1920">
<g id="band" opacity="0"><rect x="-84" y="0" width="84" height="1920" fill="{PAL["lemon"]}"/><rect x="0" y="0" width="5" height="1920" fill="{PAL["ink"]}"/><rect x="5" y="0" width="14" height="1920" fill="{PAL["gold"]}"/></g>
</svg></div>
<div id="topl" class="full" style="z-index:95"><svg class="full" viewBox="0 0 1080 1920" width="1080" height="1920">{"".join(self.TOP)}</svg></div>
{chr(10).join(aud)}
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(self.PRE)}
{chr(10).join(self.JS)}
tl.set({{}}, {{}}, {DUR:.3f});
window.__timelines["main"] = tl;
</script>
</div>
</body>
</html>
"""
        open(f"{P}/index.html", "w").write(html)
        shots = [{"t0": c.t0, "t1": c.t1, "name": c.name} for c in self.CARDS]
        json.dump({"fps": FPS, "beats": self.BEATS, "shots": shots}, open(f"{P}/build/beats.json", "w"), indent=1, ensure_ascii=False)
        # the face share: the time no card covers the frame
        cover = sorted((c.t0, c.t1) for c in self.CARDS)
        n = int(DUR * FPS)
        vis = sum(1 for i in range(n) if not any(a <= i / FPS < b for a, b in cover))
        lines = [f"face on screen (no card): {vis / FPS:.2f} s of {DUR:.2f} s = {100 * vis / n:.1f} %",
                 f"cards: {len(self.CARDS)}; sfx: {len(self.SFX)} ({len(self.SFX) / DUR * 10:.1f} per 10 s); html {len(html) // 1024} KB"]
        open(f"{P}/build/coverage.txt", "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return lines


# ---------------------------------------------------------------- line icons (lemon strokes in a 120x120 box): draw new ones per reel
def icon_moon(col=PAL["lemon"]):
    return f'<path d="M78,14 A48,48 0 1 0 106,86 A38,38 0 1 1 78,14 Z" fill="none" stroke="{col}" stroke-width="8" stroke-linejoin="round"/>'


def icon_motion(col=PAL["lemon"]):
    return "".join(f'<polyline points="{x},24 {x + 30},60 {x},96" fill="none" stroke="{col}" stroke-width="10" stroke-linecap="round" '
                   f'stroke-linejoin="round" opacity="{o}"/>' for x, o in [(14, 0.4), (44, 0.7), (74, 1)])


def icon_heart(col=PAL["lemon"]):
    return (f'<path d="M60,102 C20,74 8,52 14,34 C20,16 44,12 60,32 C76,12 100,16 106,34 C112,52 100,74 60,102 Z" fill="none" '
            f'stroke="{col}" stroke-width="8" stroke-linejoin="round"/>')


if __name__ == "__main__":
    print(__doc__)
