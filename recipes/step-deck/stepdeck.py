"""Step Deck: a tips reel as a numbered deck over a talking head. Every spoken word lands on screen on its onset, sized by
how much it matters, set BEHIND the speaker's head on their face (a caption layer between the plate and its matte); between face shots
the reel cuts to full-screen word cards and pictures every 1-2 s; each step opens on a card with a giant italic numeral
that shrinks into place. From a reel by @ant.lon, replicated frame by frame (the study's element and transition labels E1-E29, X1-X9 are kept
in the comments) and applied to a founding talking-head reel.

    import sys; sys.path.insert(0, "<skill>/recipes/step-deck"); from stepdeck import *
    D = Deck("$P", dur=63.10, title="my-reel Step Deck")                    # words: $P/build/words.cut.json (edit s)
    D.face("W01", 0.00, 1.02, "t", "B T +T", push=True, fade=False)      # frame 0: the face, the first word behind the head
    D.navy("W02", 1.02, 2.04, "M /M +M")                                 # navy word card, the phrase appends
    D.page("W03", 2.04, 3.84, "T +T +T +T B Sf")                         # white word page; f = the word flickers on (E8)
    D.montage("W05", 5.60, 10.18, [(5.60, ["lap_a", "lap_b"]), ...], "B B M B")   # hook 2: B&W print flicker + red words
    D.disk("W06", 10.18, 12.14, 6)                                       # hook 3: tiny words around a disk (moon empties)
    D.title("W14", 29.58, 31.46, n_small=4)                              # promise: caps serif block, RGB split
    D.step("W16", 32.48, 35.92, "1", "M T +T M T +T +T B /ST +ST +ST")   # step card: giant italic numeral shrinks in
    D.push_out("W26", 57.05); D.face("W27", 57.05, 59.10, "t", "...", pushin=True, fade=False)   # X4 whip across a cut
    D.face("W29", 61.24, 63.10, "t", "T +T +T"); D.keyword("W29")         # flat outro: the one gradient word
    D.plates([(0.0, "t"), (1.68, "w"), ...]); D.sfx("whoosh-1", 1.02 - 3 * F1, 0.32); D.build()

Spec strings (one token per caption state, in word order; each world consumes its words from the cursor):
  `B`  a new state with the next word in tier B      `+B`  append the next word to the last line (phrase append, E5)
  `/ST` the next word on a new line under it (sub-line, E7)     suffix `f`: the word flickers on (E8)     `*3`: three words
  tiers: T tiny (64-68 px, the floor is 56 px: the rule is >= 48), M mid, B big, S serif italic (the voice / payoff word, about
  1 in 6), ST serif sub-line, L serif label (cards), G gradient keyword (outro).
Worlds run in word order: face() / navy() / page() / card_words() take their words from the cursor; D.take(n) for your own
scenes; D.when("word") is the onset of that word inside the last world. A scene of your own (a diagram, a prop) is written
with the primitives: card_open / svg_open / text_line / tset / tween / card_close, and the motion helpers pop_in, jump,
rack, box_grow, blur_out (e.g. a diagram whose parts pop in on their words, then a jump onto one part with rack focus).

The house (house.json; never changes reel to reel): the palette, the type (Inter Tight 600/700, Playfair Display + Italic for
the serif voice and the numerals, Montserrat 800 for the one gradient word: Cyrillic substitutes for Instrument Serif and
Plus Jakarta Sans), the tiers, the captions behind the speaker's head on face shots, the word cards, the step cards with the rotating
colour field (navy, off-white, electric blue), hard cuts on word onsets with the motion in the elements, the speaker's face as shot.
What changes every reel (components.py plan --style step-deck): the hook devices, the promise card, the step pictures and
scenes, the transitions used, the outro device.

Needs in $P: assets/{wide,tight}.mp4 plates (one is fine: plates={"t": (...)}) + assets/<plate>-matte.webm (alpha, from
scripts/matte.py: the captions hide behind the speaker's head), assets/voice.wav, build/words.cut.json, build/cover_windows.json (look-aways
to hide under cards). Fonts, SFX and the bed are copied from the skill when missing (ensure_*); crowns (the top of the speaker's head per
face world) are measured from the mattes and cached in build/crowns.json; prints for a montage come from make_prints().
"""
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
PAL = HOUSE["palette"]
TY = HOUSE["type"]
FAM = {k: tuple(v) for k, v in TY["families"].items()}       # key -> (family, weight, style, file stem, ttf weight)
TRACK = TY["tracking_em"]
XH = TY["x_height_em"]
TIERS = TY["tiers"]                                           # context -> tier -> [family key, nominal px]
SPACE = TY["space_em"]
FLOOR = TY["floor_px"]                                        # no caption word below this (the rule: >= 48 px)
FACE_OFF = TY["face_offset_px"]                               # baseline = crown of the head + this, by the line's biggest tier
MOTION = HOUSE["motion"]
FPS = MOTION["fps"]
F1 = 1 / FPS
FLICK_DARK = MOTION["flicker_dark"]                           # E8 on footage / dark cards (measured)
FLICK_LIGHT = MOTION["flicker_light"]                         # E8 on light pages
FLICK_KEY = MOTION["flicker_keyword"]                         # E29 the gradient word
HOLDS = MOTION["montage_holds"]                               # E1 ~10 fps stop-motion clock (25 -> 30 fps)
SFX_LEN = HOUSE["sound"]["sfx_len_s"]                         # library lengths (s); others are probed


def fr(t):
    """snap to the frame grid"""
    return round(round(t * FPS) / FPS, 4)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def is_cyr(ch):
    return 0x0400 <= ord(ch) <= 0x04FF


# ---------------------------------------------------------------- fonts + measuring (static TTF instances of the woff2s)
_TTF = [None]
_fc = {}


def font(fam, sub, size):
    from PIL import ImageFont
    k = (fam, sub, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(f"{_TTF[0]}/{FAM[fam][3]}-{sub}-{FAM[fam][4]}.ttf", size)
    return _fc[k]


def adv(s, fam, size):
    """advance width incl. tracking, per char from the subset that has it (kerning ignored -> errs wide)"""
    w = sum(font(fam, "cyrillic" if is_cyr(c) else "latin", 200).getlength(c) * size / 200 for c in s)
    return w + TRACK[fam] * size * max(len(s) - 1, 0)


def ink(s, fam, size):
    """ink top/bottom/left/right relative to the baseline origin (neg = above), from the letters only"""
    core = "".join(c for c in s if is_cyr(c) or c.isalnum()) or s
    sub = "cyrillic" if any(is_cyr(c) for c in core) else "latin"
    b = font(fam, sub, 200).getbbox(core, anchor="ls")
    return b[1] * size / 200, b[3] * size / 200, b[0] * size / 200, b[2] * size / 200


def style(fam, size, fill, extra=""):
    f = FAM[fam]
    return (f"font-family:'{f[0]}';font-weight:{f[1]};font-style:{f[2]};font-size:{size:.1f}px;"
            f"letter-spacing:{TRACK[fam]*size:.2f}px;fill:{fill};{extra}")


def mix(a, b, q):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * q):02X}" for x, y in zip(a, b))


def _ms(t):
    return "0" if not t else f"{fr(t):.4f}"


TOKEN = re.compile(r"^([+/]?)(ST|[TMBSGL])(f?)(?:\*(\d+))?$")


def parse_spec(spec):
    """'B T +T /ST Sf' -> [("new","B",1), ("new","T",1), ("+","T",1), ("/","ST",1), ("new","S",1,"f")]; lists pass through"""
    if not isinstance(spec, str):
        return list(spec)
    out = []
    for tok in spec.split():
        m = TOKEN.match(tok)
        if not m:
            raise ValueError(f"bad spec token {tok!r} (op + tier [+ f] [*n]: B, +T, /ST, Sf, T*3)")
        op = {"": "new", "+": "+", "/": "/"}[m.group(1)]
        e = (op, m.group(2), int(m.group(4) or 1))
        out.append(e + (("f",) if m.group(3) else ()))
    return out


# ---------------------------------------------------------------- per-reel media (made per reel, never stored in the recipe)
def ensure_fonts(P):
    os.makedirs(f"{P}/assets/fonts", exist_ok=True)
    for _, stem, _, _ in TY["font_faces"]:
        for sub in ("cyrillic", "latin"):
            dst = f"{P}/assets/fonts/{stem}-{sub}.woff2"
            if not os.path.exists(dst):
                shutil.copy(f"{SKILL}/templates/fonts/{stem}-{sub}.woff2", dst)


def ensure_ttf(P):
    """static TTF instances of the variable woff2s for PIL measuring -> build/ttf/<stem>-<sub>-<weight>.ttf"""
    out = f"{P}/build/ttf"
    os.makedirs(out, exist_ok=True)
    need = sorted({(f[3], f[4]) for f in FAM.values()})
    for stem, w in need:
        for sub in ("cyrillic", "latin"):
            dst = f"{out}/{stem}-{sub}-{w}.ttf"
            if os.path.exists(dst):
                continue
            from fontTools.ttLib import TTFont
            from fontTools.varLib import instancer
            g = TTFont(f"{P}/assets/fonts/{stem}-{sub}.woff2")
            if "fvar" in g:
                g = instancer.instantiateVariableFont(g, {"wght": w})
            g.flavor = None
            g.save(dst)
    return out


def ensure_sfx(P, name):
    os.makedirs(f"{P}/assets/sfx", exist_ok=True)
    dst = f"{P}/assets/sfx/{name}.wav"
    if not os.path.exists(dst):
        shutil.copy(f"{SKILL}/library/sfx/{name}.wav", dst)
    return dst


def ensure_bed(P, track, dur, fade=1.5):
    """assets/music/bed.wav = library/music/<track>.mp3 from 0 s, unity gain, cut to the reel with a linear fade-out
    (how the founding reel's bed was made: lo-fi-02, 1.5 s fade, measured); the level is set by bed_vol on the audio tag"""
    dst = f"{P}/assets/music/bed.wav"
    if os.path.exists(dst):
        return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{SKILL}/library/music/{track}.mp3", "-t", f"{dur:.3f}",
                    "-af", f"afade=t=out:st={dur - fade:.3f}:d={fade}", "-ar", "48000", "-ac", "2", dst], check=True)
    return dst


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def measure_crown(matte, t0, t1, cols=(470, 610)):
    """top of the speaker's head (y px) over columns x 470-610, median of 6 frames of the matte's alpha (libvpx-vp9 keeps alpha)"""
    import numpy as np
    ys = []
    for t in np.linspace(t0 + 0.05, t1 - 0.05, 6):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-ss", f"{t:.3f}", "-i", matte, "-frames:v", "1",
                              "-vf", "alphaextract", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
        if len(raw) != 1080 * 1920:
            continue
        al = np.frombuffer(raw, np.uint8).reshape(1920, 1080)[:, cols[0]:cols[1]]
        rows = np.where((al > 128).mean(axis=1) > 0.2)[0]
        if len(rows):
            ys.append(int(rows[0]))
    if not ys:
        raise RuntimeError(f"no head found in {matte} {t0:.2f}-{t1:.2f} (is the matte's alpha there?)")
    return int(np.median(ys))


def make_prints(P, spec, seed=7, src="assets/ins", out="assets/prints"):
    """B&W paper prints for the stop-motion montage (SPEC E1): hard B&W (photocopy curve, crushed blacks, paper white),
    the card on #FAFAFA paper, 70-90 % wide (sources are ~768 px: <= 1.25x upscale), tilt / keystone, an occasional black
    bar. spec rows: (name, source stem in assets/ins, crop fractions (x0, y0, x1, y1), card width px, tilt deg,
    bar edge or None, curve midpoint). Writes <out>/<name>.jpg and stats.json (mid-tone share behind the red words: where
    #D30B20 drops under 3:1 contrast)."""
    import numpy as np
    from PIL import Image
    os.makedirs(f"{P}/{out}", exist_ok=True)
    random.seed(seed)

    def photocopy(a, mid):
        lo, hi = np.percentile(a, 1), np.percentile(a, 99.5)
        a = np.clip((a - lo) / max(hi - lo, 1), 0, 1)
        a = 1 / (1 + np.exp(-(a - mid) * 14))            # steep sigmoid: few mid-tones left
        a = (a - a.min()) / max(a.max() - a.min(), 1e-6)
        return (a * 255).astype(np.uint8)
    stats = {}
    for name, s, cf, W, tilt, bar, mid in spec:
        im = Image.open(f"{P}/{src}/{s}.jpg").convert("L")
        w0, h0 = im.size
        im = im.crop((int(cf[0] * w0), int(cf[1] * h0), int(cf[2] * w0), int(cf[3] * h0)))
        H = int(W * im.height / im.width)
        g = im.resize((W, H), Image.LANCZOS)
        a = photocopy(np.array(g).astype(np.float32), mid).astype(np.int16)
        a = np.clip(a + np.random.default_rng(len(name) * 3).normal(0, 7, a.shape), 0, 255).astype(np.uint8)  # grain
        card = Image.fromarray(a).convert("RGB")
        if bar:
            b = Image.new("RGB", (W, 22) if bar in ("top", "bottom") else (22, H), (10, 10, 10))
            card.paste(b, {"top": (0, 0), "bottom": (0, H - 22), "left": (0, 0), "right": (W - 22, 0)}[bar])
        k = random.uniform(0.015, 0.03) * W
        quad = (0, 0, 0, H, W, H, W, 0) if random.random() < 0.5 else (-k, 0, 0, H, W, H, W + k, 0)
        card = card.transform((W, H), Image.QUAD, quad, Image.BICUBIC, fillcolor=(250, 250, 250))
        card = card.rotate(tilt, Image.BICUBIC, expand=True, fillcolor=(250, 250, 250))
        paper = np.full((1920, 1080, 3), 250, np.int16) + np.random.default_rng(len(name)).normal(0, 3, (1920, 1080, 1)).astype(np.int16)
        paper = Image.fromarray(np.clip(paper, 0, 255).astype(np.uint8))
        ox = (1080 - card.width) // 2 + random.randint(-14, 14)
        oy = 900 - card.height // 2 + random.randint(-30, 30)
        paper.paste(card, (ox, oy))
        paper.save(f"{P}/{out}/{name}.jpg", quality=92)
        L = np.array(paper.convert("L"))[840:1110, 120:960].astype(np.float32)
        stats[name] = {"band_mid_frac": round(float(((L > 32) & (L < 190)).mean()), 3), "card": [card.width, card.height]}
    json.dump(stats, open(f"{P}/{out}/stats.json", "w"), indent=1)
    return stats


# ---------------------------------------------------------------- the deck
class Deck:
    def __init__(self, project, dur, title, n_words=None, words="build/words.cut.json", plates=None, voice="assets/voice.wav",
                 voice_dur=None, bed="assets/music/bed.wav", bed_track=None, bed_vol=None, lang="ru"):
        self.P = os.path.abspath(os.path.expanduser(project))
        self.dur, self.page_title, self.lang = dur, title, lang
        d = json.load(open(f"{self.P}/{words}", encoding="utf-8"))
        raw = [w for s in d["segments"] for w in s["words"]] if "segments" in d else d["words"]
        self.W = []
        for w in raw:                                  # merge Russian hyphenated particles ("-to") into the word before
            t = w["word"].strip()
            if t.startswith("-") and self.W:
                self.W[-1] = (self.W[-1][0] + t, self.W[-1][1], w["end"])
            else:
                self.W.append((t, w["start"], w["end"]))
        if n_words is not None:
            assert len(self.W) == n_words, (len(self.W), n_words)
        self.plates_ = plates or {"w": ("assets/wide.mp4", "assets/wide-matte.webm"),
                                  "t": ("assets/tight.mp4", "assets/tight-matte.webm")}
        self.voice = voice
        self.voice_dur = voice_dur if voice_dur is not None else round(probe_dur(f"{self.P}/{voice}"), 2)
        self.bed, self.bed_vol = bed, HOUSE["sound"]["bed_volume"] if bed_vol is None else bed_vol
        if bed_track:
            ensure_bed(self.P, bed_track, dur)
        ensure_fonts(self.P)
        _TTF[0] = ensure_ttf(self.P)
        cp = f"{self.P}/build/crowns.json"
        self.crowns = json.load(open(cp)) if os.path.exists(cp) else {}
        self.H, self.FC, self.FC2, self.JS = [], [], [], []
        self.SECTIONS, self.FACE, self.BEATS, self.SFX = [], [], [], []
        self.cur, self._id, self._n, self._w0 = 0, 0, {}, 0
        self.cam_y = None                              # the punch-in origin (one punch-in per reel, X8)
        self._track = 60                               # inserted clips get tracks 60, 61, ...
        self.switches = []

    # ------------------------------------------------------------ words
    def take(self, n):
        toks = self.W[self.cur:self.cur + n]
        self.cur += n
        return toks

    def when(self, word, after=None):
        """onset of the first word equal to `word` (punctuation ignored) from index `after` (default: the last world's start)"""
        k = lambda s: re.sub(r"[^\w-]", "", s.lower())
        i0 = self._w0 if after is None else after
        for i in range(i0, len(self.W)):
            if k(self.W[i][0]) == k(word):
                return self.W[i][1]
        raise KeyError(f"{word!r} not found after word {i0}")

    def states(self, spec, t0, t1):
        """-> [start, end, lines=[[(word, tier)]], newest=(line, idx), flags] per caption state"""
        self._w0 = self.cur
        out = []
        for e in parse_spec(spec):
            op, tier, n = e[0], e[1], e[2]
            flags = e[3] if len(e) > 3 else ""
            toks = self.take(n)
            word = " ".join(t[0] for t in toks)
            ts = max(t0, toks[0][1])
            if op == "new" or not out:
                lines = [[(word, tier)]]
            elif op == "+":
                lines = [l[:] for l in out[-1][2]]
                lines[-1].append((word, tier))
            else:
                lines = [l[:] for l in out[-1][2]] + [[(word, tier)]]
            out.append([ts, None, lines, (len(lines) - 1, len(lines[-1]) - 1), flags])
        for i, s in enumerate(out):
            s[1] = out[i + 1][0] if i + 1 < len(out) else t1
        return [s for s in out if s[1] - s[0] > 0.001]

    # ------------------------------------------------------------ html / js primitives
    def nid(self, p="e"):
        self._id += 1
        return f"{p}{self._id}"

    def once(self, kind):
        """'' for the first element of a kind in the reel, '2', '3' ... after (keeps ids unique)"""
        self._n[kind] = self._n.get(kind, 0) + 1
        return "" if self._n[kind] == 1 else str(self._n[kind])

    def tset(self, sel, props, t):
        self.JS.append(f'tl.set("{sel}", {json.dumps(props)}, {fr(t):.4f});')

    def tween(self, sel, frm, to, t):
        self.JS.append(f'tl.fromTo("{sel}", {json.dumps(frm)}, {json.dumps({**to, "immediateRender": False})}, {fr(t):.4f});')

    def flicker(self, sel, t0, keys, prop="opacity"):
        for i, v in enumerate(keys):
            self.tset(sel, {prop: v}, t0 + i * F1)

    def beat(self, bid, keys):
        self.BEATS.append({"id": bid, "type": "beat", "label": bid, "t0": round(min(keys), 3), "t1": round(max(keys), 3),
                           "keys": [round(k, 3) for k in keys]})

    def add_keys(self, *ts):
        self.BEATS[-1]["keys"] += [round(t, 3) for t in ts]

    def layout(self, line, ctx, maxw=930):
        """line = [(word, tier)] -> [(word, fam, size)] scaled to fit maxw, never under FLOOR"""
        items = [[w, *TIERS[ctx][t]] for w, t in line]
        tot = lambda: sum(adv(w, f, s) for w, f, s in items) + sum(SPACE * s for _, _, s in items[1:])
        for _ in range(40):
            if tot() <= maxw:
                break
            big = [it for it in items if it[2] > FLOOR + 0.5]
            if not big:
                break
            k = max(0.9, maxw / tot())
            for it in big:
                it[2] = max(FLOOR, it[2] * k)
        assert all(s >= FLOOR - 0.01 for _, _, s in items), line
        return [tuple(it) for it in items]

    def text_line(self, items, y, fill, x=540, anchor="middle", extra="", tid=None, hidden=False):
        tid = tid or self.nid("t")
        spans = []
        for i, (w, f, s) in enumerate(items):
            spans.append(f'<tspan id="{tid}_{i}" style="{style(f, s, fill)}">{" " if i else ""}{esc(w)}</tspan>')
        op = 'opacity="0" ' if hidden else ""
        self.H.append(f'<text {op}id="{tid}" x="{x}" y="{y:.1f}" text-anchor="{anchor}" style="white-space:pre;{extra}">'
                      f'{"".join(spans)}</text>')
        return tid, [f"{tid}_{i}" for i in range(len(items))]

    def card_open(self, name, t0, t1, bg, z=10, extra=""):
        self.SECTIONS.append((name, t0, t1))
        self.H.append(f'<section id="{name}" class="clip full" data-start="{fr(t0):.4f}" data-duration="{fr(t1)-fr(t0):.4f}" '
                      f'data-track-index="{10 + len(self.SECTIONS)}" style="z-index:{z};background:{bg};{extra}">')

    def card_close(self):
        self.H.append("</section>")

    def svg_open(self, extra=""):
        self.H.append(f'<svg class="full" viewBox="0 0 1080 1920" width="1080" height="1920" style="{extra}">')

    def svg_close(self):
        self.H.append("</svg>")

    # ------------------------------------------------------------ face worlds: captions behind the head (E6)
    def crown(self, name, t0, t1, plate):
        if name not in self.crowns:
            self.crowns[name] = measure_crown(f"{self.P}/{self.plates_[plate][1]}", t0, t1)
            json.dump(self.crowns, open(f"{self.P}/build/crowns.json", "w"), indent=1)
        return self.crowns[name]

    def face(self, name, t0, t1, plate, spec, push=False, fade=True, pushin=False, punch=None, maxw=930):
        """the plate as shot, the caption states on a layer between the plate and its matte (the head hides them), the
        baseline on the crown of the head + FACE_OFF. push: the E2 opening push-back (frame 0); fade: the first word fades
        + rises over 6 f (E6); pushin: the layer continues an X4 whip from the right; punch=(t, origin y, scale): the one
        X8 punch-in of the reel (scale only)."""
        self.FACE.append((t0, t1, plate))
        crown0 = self.crown(name, t0, t1, plate)
        sts = self.states(spec, t0, t1)
        keep, self.H = self.H, self.FC
        gid = f"fc_{name}"
        self.H.append(f'<g id="{gid}_drift"><g id="{gid}_push"><g id="{gid}_x">')
        keys = []
        for k, (ts, te, lines, newest, flags) in enumerate(sts):
            crown = crown0
            if punch and ts >= punch[0] - 1e-6:
                crown = punch[1] + (crown - punch[1]) * punch[2]
            sid = f"{gid}_s{k}"
            self.H.append(f'<g id="{sid}" opacity="0">')
            y = None
            for li, line in enumerate(reversed(lines)):     # last line lowest; earlier lines stack above
                items = self.layout(line, "face", maxw)
                big = max(line, key=lambda wt: FACE_OFF[wt[1]])[1]
                base = crown + FACE_OFF[big] if li == 0 else y - max(s for _, _, s in items) * 0.95
                tid, spans = self.text_line(items, base, PAL["caption"], extra="filter:drop-shadow(0 0 24px rgba(0,0,0,.35));")
                if li == 0 and "f" in flags:
                    self.flicker(f"#{spans[newest[1]]}", ts, FLICK_DARK, "fillOpacity")
                y = base
            self.H.append("</g>")
            self.tset(f"#{sid}", {"opacity": 1}, ts)
            keys.append(ts + 0.1)
            if k == 0 and fade and not push and not pushin:
                for i, v in enumerate(MOTION["first_word_fade"]):
                    if ts + i * F1 < te - F1 / 2:
                        self.tset(f"#{sid}", {"opacity": v}, ts + i * F1)
                self.tween(f"#{sid}", {"y": 30}, {"y": 0, "ease": "power2.out", "duration": min(0.6, te - ts)}, ts)
            self.tset(f"#{sid}", {"opacity": 0}, te)
        self.H.append("</g></g></g>")
        self.H = keep
        o = f"540 {crown0}"
        if push:      # E2 red-hook curve on the opening layer
            self.JS.append(f"gsap.set('#{gid}_push', {{svgOrigin: '{o}'}}); gsap.set('#{gid}_drift', {{svgOrigin: '{o}'}});")
            self.tween(f"#{gid}_push", {"scale": 1.36}, {"scale": 1, "ease": "circ.out", "duration": 0.6}, t0)
            self.tween(f"#{gid}_drift", {"scale": 1.057}, {"scale": 1, "ease": "none", "duration": t1 - t0}, t0)
        if pushin:    # X4 in: the caption layer continues the whip from the right, circ.out ~31 f
            self.tween(f"#{gid}_x", {"x": 400}, {"x": 0, "ease": "circ.out", "duration": 1.24}, t0)
        self.beat(name, keys)
        if punch:     # X8: the same take x1.20, hard on, hard off at the world's end (plate and matte together)
            if self.cam_y not in (None, punch[1]):
                raise ValueError("one punch-in origin per reel (house: one punch-in)")
            self.cam_y = punch[1]
            self.tset("#cam", {"scale": punch[2]}, punch[0])
            self.tset("#mcam", {"scale": punch[2]}, punch[0])
            self.tset("#cam", {"scale": 1}, t1)
            self.tset("#mcam", {"scale": 1}, t1)

    def keyword(self, name, colours=None):
        """the outro (E29 look, no CTA): the next word = the one gradient word of the reel, Montserrat 800, behind the head
        on the crown of the face world `name` (call right after its face()); the clause steps aside, flicker-on + rise"""
        toks = self.take(1)
        gw = toks[0][0]
        K = HOUSE["layout_px"]["keyword"]
        gsize = min(K["max_px"], K["maxw"] / adv(gw, "mo8", 1))
        gbase = self.crowns[name] + FACE_OFF["G"]
        sx = self.once("keyword")
        stops = colours or PAL["gradient"]
        self.FC2.append(f'<defs><linearGradient id="grad{sx}" x1="0" x2="1" y1="0" y2="0">' + "".join(
            f'<stop offset="{i/(len(stops)-1):.3f}" stop-color="{c}"/>' for i, c in enumerate(stops)) + "</linearGradient></defs>")
        self.FC2.append(f'<g id="gword{sx}_g" opacity="0"><text id="gword{sx}" x="540" y="{gbase:.1f}" text-anchor="middle" '
                        f'style="{style("mo8", gsize, f"url(#grad{sx})")}">{esc(gw)}</text></g>')
        tg = toks[0][1]
        self.tset(f"[id^=fc_{name}_s]", {"opacity": 0}, tg)          # the tiny clause steps aside for the keyword (E29)
        self.flicker(f"#gword{sx}_g", tg - 2 * F1, FLICK_KEY)
        self.tween(f"#gword{sx}", {"y": 100}, {"y": 0, "ease": "expo.out", "duration": 0.55}, tg - 2 * F1)
        self.add_keys(tg + 0.05, tg + 0.4)
        return tg

    # ------------------------------------------------------------ card worlds: the words ARE the graphic
    def card_words(self, name, t0, t1, spec, fill, ctx="card", yc=960, flick=FLICK_DARK, push=None, maxw=930, gap=1.05, extra=""):
        """centred caption states on a card; two-line stacks grow downward from yc. push=(from scale, s, drift scale)"""
        sts = self.states(spec, t0, t1)
        gid = f"cw_{name}"
        self.H.append(f'<g id="{gid}_drift"><g id="{gid}_push">')
        keys, ids = [], []
        for k, (ts, te, lines, newest, flags) in enumerate(sts):
            sid = f"{gid}_s{k}"
            ids.append(sid)
            self.H.append(f'<g id="{sid}" opacity="0">')
            laid = [self.layout(l, ctx, maxw) for l in lines]
            heights = [max(s for _, _, s in it) for it in laid]
            y = yc + XH["it6"] * heights[0] / 2 - (sum(heights[1:]) * gap) / 2
            for li, items in enumerate(laid):
                if li:
                    y += heights[li] * gap
                tid, spans = self.text_line(items, y, fill, extra=extra)
                if li == newest[0] and "f" in flags:
                    self.flicker(f"#{spans[newest[1]]}", ts, flick, "fillOpacity")
            self.H.append("</g>")
            self.tset(f"#{sid}", {"opacity": 1}, ts)
            self.tset(f"#{sid}", {"opacity": 0}, te)
            keys.append(ts + 0.1)
        self.H.append("</g></g>")
        if push:
            a, dur, drift = push
            self.JS.append(f"gsap.set('#{gid}_push', {{svgOrigin: '540 {yc}'}}); gsap.set('#{gid}_drift', {{svgOrigin: '540 {yc}'}});")
            self.tween(f"#{gid}_push", {"scale": a}, {"scale": 1, "ease": "circ.out", "duration": dur}, t0)
            self.tween(f"#{gid}_drift", {"scale": drift}, {"scale": 1, "ease": "none", "duration": t1 - t0}, t0)
        self.beat(name, keys)
        return ids, sts

    def navy(self, name, t0, t1, spec, bg=None, fill=None):
        """E5 navy word card: warm off-white words, the phrase appends in place (questions, doubts, a turn)"""
        self.card_open(name, t0, t1, bg or PAL["navy"])
        self.svg_open()
        r = self.card_words(name, t0, t1, spec, fill or PAL["warm"])
        self.svg_close()
        self.card_close()
        return r

    def page(self, name, t0, t1, spec, exit_white=False, bg=None, fill=None):
        """E20 white word page: near-black words; f words flicker on (light keys); exit_white: X3 brighten + blur to white
        over the last 7 frames"""
        lo = name.lower()
        self.card_open(name, t0, t1, bg or PAL["page"])
        self.svg_open()
        if exit_white:
            self.H.append(f'<g id="{lo}_all">')
        r = self.card_words(name, t0, t1, spec, fill or PAL["ink"], flick=FLICK_LIGHT)
        if exit_white:
            self.H.append("</g>")
        self.svg_close()
        if exit_white:
            self.H.append(f'<div id="{lo}_white" class="full" style="background:#FFFFFF;opacity:0"></div>')
        self.card_close()
        if exit_white:
            for i, (wo, bl) in enumerate(zip(MOTION["white_exit_opacity"], MOTION["white_exit_blur_px"])):
                t = t1 - len(MOTION["white_exit_opacity"]) * F1 + i * F1
                self.tset(f"#{lo}_white", {"opacity": wo}, t)
                self.tset(f"#{lo}_all text", {"filter": f"blur({bl}px)"}, t)
        return r

    # ------------------------------------------------------------ hook devices (S1; new every reel: these are the founding ones)
    def montage(self, name, t0, t1, groups, tiers, push=None, seed=11, holds=None):
        """E1 + E2: B&W paper prints of the line's objects swapped on their own ~10 fps clock (holds 2-4 f, 1-3 px jitter,
        a squash glitch on frame 2), the spoken words one at a time in red Inter Tight 700 over them, the layer pushed back
        (circ.out 0.6 s) at each time in `push` (1.36 at the first, 1.22 after) and drifting. groups = [(time, [print
        names in assets/prints])]: the prints follow the words. tiers: 'B M B ...' per word (300 / 200 px)."""
        sx = self.once("montage")
        pr, red = f"pr{sx}", f"red{sx}"
        holds = holds or HOLDS
        tiers = tiers.split() if isinstance(tiers, str) else list(tiers)
        self.card_open(name, t0, t1, PAL["paper"])
        for n in sorted({n for _, g in groups for n in g}):
            self.H.append(f'<img id="{pr}_{n}" class="full" src="assets/prints/{n}.jpg" style="opacity:0">')
        rnd = random.Random(seed)
        f = round(t0 * FPS)
        hi = gi = idx = 0
        last = None
        while f < round(t1 * FPS):
            t = f / FPS
            while gi + 1 < len(groups) and f >= round(groups[gi + 1][0] * FPS):
                gi += 1
                idx = 0
            g = groups[gi][1]
            n = g[idx % len(g)]
            idx += 1
            h = holds[hi % len(holds)]
            hi += 1
            nxt = min(f + h, round(t1 * FPS))
            if gi + 1 < len(groups):
                nxt = min(nxt, round(groups[gi + 1][0] * FPS))
            if last and last != n:
                self.tset(f"#{pr}_{last}", {"opacity": 0}, t)
            self.tset(f"#{pr}_{n}", {"opacity": 1, "x": 0, "y": 0, "scale": 1, "scaleY": 1, "filter": "blur(0px)"}, t)
            for j in range(f + 1, nxt):          # held-frame jitter 1-3 px, 0.5 % scale
                self.tset(f"#{pr}_{n}", {"x": rnd.randint(-2, 2), "y": rnd.randint(-2, 2),
                                         "scale": round(1 + rnd.uniform(-.004, .004), 4)}, j / FPS)
            last = n
            f = nxt
        self.tset(f"#{pr}_{last}", {"opacity": 0}, t1)
        g0 = f"#{pr}_{groups[0][1][0]}"           # f2-f3 glitch print: squash + vertical smear on the 2nd / 3rd frame
        self.tset(g0, {"scaleY": 0.6, "filter": "blur(6px)"}, t0 + F1)
        self.tset(g0, {"scaleY": 1, "filter": "blur(0px)"}, t0 + 3 * F1)
        self.svg_open()
        self.H.append(f'<g id="{red}_drift"><g id="{red}_push">')
        M = HOUSE["layout_px"]["montage"]
        toks = self.take(len(tiers))
        self._w0 = self.cur - len(tiers)
        rk = []
        for i, ((w, s, e), tier) in enumerate(zip(toks, tiers)):
            size = M["big_px"] if tier == "B" else M["mid_px"]
            size = min(size, M["maxw"] / adv(w, "it7", 1))
            base = M["y"] + XH["it7"] * size / 2
            self.text_line([(w, "it7", size)], base, PAL["red"], tid=f"{red}_{i}", hidden=True)
            ts = max(t0, s)
            te = toks[i + 1][1] if i + 1 < len(toks) else t1
            self.tset(f"#{red}_{i}", {"opacity": 1}, ts)
            self.tset(f"#{red}_{i}", {"opacity": 0}, te)
            rk.append(ts + 0.07)
        self.H.append("</g></g>")
        self.svg_close()
        self.JS.append(f"gsap.set('#{red}_push', {{svgOrigin: '540 {M['y']}'}}); gsap.set('#{red}_drift', {{svgOrigin: '540 {M['y']}'}});")
        for gt in (push if push is not None else [g[0] for g in groups]):
            self.tween(f"#{red}_push", {"scale": 1.36 if gt == t0 else 1.22}, {"scale": 1, "ease": "circ.out", "duration": 0.6}, gt)
        self.tween(f"#{red}_drift", {"scale": 1.057}, {"scale": 1, "ease": "none", "duration": t1 - t0}, t0)
        self.card_close()
        self.beat(name, rk)

    def disk(self, name, t0, t1, n, icon="moon"):
        """E4: a quiet cream card after the loud ones (scale inversion): a black disk with one icon in the centre, the next n
        words tiny (60 px) hugging it left / right in turn, each until the word two later. icon="moon": a crescent that
        wanders on twos and is swallowed by the shadow on the last word; or any SVG string drawn inside the disk (static)."""
        sx = self.once("disk")
        cx, cy, r = 541, 960, 113
        self.card_open(name, t0, t1, PAL["cream"])
        self.svg_open()
        self.H.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PAL["disk"]}"/>')
        if icon == "moon":
            self.H.append(f'<g id="moon{sx}"><circle cx="{cx}" cy="{cy}" r="58" fill="{PAL["cream"]}"/>'
                          f'<circle id="moon{sx}_sh" cx="566" cy="944" r="54" fill="{PAL["disk"]}"/></g>')
        else:
            self.H.append(icon)
        toks = self.take(n)
        self._w0 = self.cur - n
        ck = []
        for i, (w, s, e) in enumerate(toks):
            left = i % 2 == 0
            size = HOUSE["layout_px"]["disk_word_px"]
            self.text_line([(w, "it6", size)], cy + XH["it6"] * size / 2, PAL["ink_tiny"], x=(cx - r - 22) if left else (cx + r + 22),
                           anchor="end" if left else "start", tid=f"cr{sx}_{i}", hidden=True)
            ts = max(t0, s)
            self.tset(f"#cr{sx}_{i}", {"opacity": 1}, ts)
            self.tset(f"#cr{sx}_{i}", {"opacity": 0}, toks[i + 2][1] if i + 2 < len(toks) else t1)
            ck.append(ts + 0.07)
        self.svg_close()
        self.card_close()
        empty = toks[-1][1]
        if icon == "moon":                        # on twos (12.5 -> 15 fps), the shadow swallows the moon on the last word
            f = round(t0 * FPS)
            k = 0
            while f < round(t1 * FPS):
                t = f / FPS
                if t < empty:
                    mx, my = 566 + 4 * math.sin(k * 0.9), 944 + 3 * math.cos(k * 0.7)
                else:
                    q = min(1, (t - empty) / 0.30)
                    mx, my = 566 - 25 * q, 944 + 16 * q
                self.tset(f"#moon{sx}_sh", {"attr": {"cx": round(mx, 1), "cy": round(my, 1),
                                                     "r": round(54 + 8 * (1 if t >= empty + 0.3 else 0), 1)}}, t)
                f += 2
                k += 1
        self.beat(name, ck + [empty + 0.4])

    # ------------------------------------------------------------ inserts (the speaker's own footage first; one stock clip in a frame)
    def panel(self, name, t0, t1, clip, n_tiny=3, media_start=0.0, vid_id=None):
        """E18 replay card: navy, a white paper panel playing `clip` (assets/...), fade-up from dark in one frame (X7); the
        next n_tiny words build a tiny line above it, then the next word lands as a Playfair label"""
        vid = vid_id or f"{name.lower()}_panel"
        lo = name.lower()
        L = HOUSE["layout_px"]["panel"]
        self.card_open(name, t0, t1, PAL["navy"])
        x, y, w, h = L["paper"]
        self.H.append(f'<div class="full" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{PAL["panel_paper"]}"></div>')
        self.svg_open()
        toks = self.take(n_tiny + 1)
        self._w0 = self.cur - n_tiny - 1
        for i in range(n_tiny):
            txt = " ".join(t[0] for t in toks[:i + 1])
            self.text_line([(txt, "it6", L["tiny_px"])], L["tiny_y"], PAL["warm"], tid=f"{lo}_t{i}", hidden=True)
            self.tset(f"#{lo}_t{i}", {"opacity": 1}, max(t0, toks[i][1]))
            self.tset(f"#{lo}_t{i}", {"opacity": 0}, toks[i + 1][1])
        lab = toks[n_tiny]
        lsize = min(L["label_px"], 860 / adv(lab[0], "pf", 1))
        self.text_line([(lab[0], "pf", lsize)], L["label_y"], PAL["warm_label"], tid=f"{lo}_label", hidden=True)
        self.tset(f"#{lo}_label", {"opacity": 1}, lab[1])
        self.svg_close()
        self.card_close()
        self.tset(f"#{name}", {"opacity": 0.35}, t0)
        self.tset(f"#{name}", {"opacity": 1}, t0 + F1)          # X7 fade-up from dark
        vx, vy, vw, vh = L["window"]
        ox, oy, ow, oh = L["video"]
        self.H.append(f'<div id="{vid}_wrap" style="position:absolute;left:{vx}px;top:{vy}px;width:{vw}px;height:{vh}px;overflow:hidden;z-index:11">'
                      f'<video id="{vid}" src="{clip}" data-start="{fr(t0):.4f}" data-duration="{fr(t1)-fr(t0):.4f}" data-media-start="{_ms(media_start)}" '
                      f'data-track-index="{self._track}" muted playsinline style="position:absolute;left:{ox}px;top:{oy}px;width:{ow}px;height:{oh}px;object-fit:cover"></video></div>')
        self._track += 1
        self.tset(f"#{vid}_wrap", {"opacity": 0.35}, t0)
        self.tset(f"#{vid}_wrap", {"opacity": 1}, t0 + F1)
        self.beat(name, [t0 + 0.05, toks[n_tiny - 1][1] + 0.1, lab[1] + 0.2])

    def broll(self, name, t0, t1, clip, spec, media_start=0.0, yc=1500, vid_id=None, fill=None, push=(1.47, 1.24, 1.0), maxw=820):
        """E22: a clip full screen with scene-tinted captions (the scene's light colour + a glow of the same hue), pushed
        back on entry; yc = where the empty space is (1500 = the lower third over a bench, ~650 over a wall)"""
        vid = vid_id or f"{name.lower()}_full"
        fill = fill or PAL["broll_cream"]
        rgb = ",".join(str(int(fill[i:i + 2], 16)) for i in (1, 3, 5))
        self.H.append(f'<video id="{vid}" class="full" src="{clip}" data-start="{fr(t0):.4f}" data-duration="{fr(t1)-fr(t0):.4f}" '
                      f'data-media-start="{_ms(media_start)}" data-track-index="{self._track}" muted playsinline style="z-index:11;object-fit:cover"></video>')
        self._track += 1
        self.card_open(name, t0, t1, "transparent", z=12)
        self.svg_open()
        r = self.card_words(name, t0, t1, spec, fill, ctx="broll", yc=yc, push=push, maxw=maxw,
                            extra=f"filter:drop-shadow(0 0 18px rgba({rgb},.45)) drop-shadow(0 2px 10px rgba(0,0,0,.55));")
        self.svg_close()
        self.card_close()
        self.SECTIONS.append((vid, t0, t1))
        return r

    # ------------------------------------------------------------ chapter cards
    def title(self, name, t0, t1, n_small=4):
        """E3 promise title: the next n_small words build a small caps Playfair line word by word, the next word lands as
        the big caps line; the block shrinks 1/0.855 -> 1 (circ.out 0.76 s) and kicks again on the big word; RGB split as
        three channel copies blended with screen (no SVG filters: HF 0.8.159 bug)"""
        sx = self.once("title")
        c = f"ttl{sx}"
        self.card_open(name, t0, t1, PAL["navy"])
        toks = self.take(n_small + 1)
        self._w0 = self.cur - n_small - 1
        small = [t[0].upper() for t in toks[:n_small]]
        bigw = toks[n_small][0].upper()
        SQ = HOUSE["layout_px"]["title"]["squeeze_x"]
        ss = min(84, 900 / SQ / adv(" ".join(small), "pf", 1))
        bs = min(200, 930 / SQ / adv(bigw, "pf", 1))
        ytop_small = HOUSE["layout_px"]["title"]["small_y"]
        ybig = ytop_small + 30 + 0.708 * bs
        bg, fg = PAL["navy"], PAL["title"]
        chans = []
        for k in range(3):
            pick = lambda col: "#" + "".join(col[1 + 2 * j:3 + 2 * j] if j == k else "00" for j in range(3))
            chans.append((pick(bg), pick(fg), (-1.5, 0, 1.5)[k], "" if k == 0 else "mix-blend-mode:screen;"))
        for rect, fill, off, blend in chans:
            self.svg_open(blend)
            self.H.append(f'<rect x="-40" y="-40" width="1160" height="2000" fill="{rect}"/><g transform="translate({off} {off})">'
                          f'<g class="{c}_drift"><g class="{c}_push">')
            sq = f"translate(540 0) scale({SQ} 1) translate(-540 0)"
            for i in range(n_small):
                self.H.append(f'<text class="{c}_s{i}" x="540" y="{ytop_small:.1f}" text-anchor="middle" transform="{sq}" opacity="0" '
                              f'style="white-space:pre;{style("pf", ss, fill)}">{esc(" ".join(small[:i + 1]))}</text>')
            self.H.append(f'<text class="{c}_b" x="540" y="{ybig:.1f}" text-anchor="middle" transform="{sq}" opacity="0" '
                          f'style="{style("pf", bs, fill)}">{esc(bigw)}</text>')
            self.H.append("</g></g></g>")
            self.svg_close()
        self.card_close()
        for i in range(n_small):
            self.tset(f".{c}_s{i}", {"opacity": 1}, max(t0, toks[i][1]))
            self.tset(f".{c}_s{i}", {"opacity": 0}, toks[i + 1][1] if i < n_small - 1 else t1)
        self.tset(f".{c}_s{n_small - 1}", {"opacity": 1}, toks[n_small - 1][1])
        self.tset(f".{c}_b", {"opacity": 1}, toks[n_small][1])
        self.JS.append(f"gsap.set('.{c}_push', {{svgOrigin: '540 1020'}}); gsap.set('.{c}_drift', {{svgOrigin: '540 1020'}});")
        self.tween(f".{c}_push", {"scale": 1 / 0.855}, {"scale": 1, "ease": "circ.out", "duration": 0.76}, t0)
        self.tween(f".{c}_drift", {"scale": 1.12}, {"scale": 1, "ease": "circ.out", "duration": 0.48}, toks[n_small][1])
        self.beat(name, [t0 + 0.05, toks[min(1, n_small - 1)][1] + 0.1, toks[n_small][1] + 0.05, toks[n_small][1] + 0.5])
        return toks[n_small][1]

    def step(self, name, t0, t1, num, spec, look=None):
        """E21 step card: a full-screen colour field rotating per step (house.json steps: navy, off-white, electric blue),
        the giant Playfair italic numeral (960 px tall, centre 523,946) enters at x1.48 with a 4-frame blur and shrinks
        circ.out 0.88 s, then drifts; a 10-frame entrance glow on the field and numeral steps down hard; the spoken
        words on top, pushed back, the first word sharpening over 4 frames"""
        k = look if look is not None else ((int(num) - 1) % len(HOUSE["steps"]) if str(num).isdigit() else 0)
        L = HOUSE["steps"][k]
        bg0, bg1, n0, n1 = L["bg0"], L["bg1"], L["n0"], L["n1"]
        self.card_open(name, t0, t1, bg1)
        self.H.append(f'<div id="{name}_bg" class="full" style="background:{bg0}"></div>')
        self.svg_open()
        top, bot, l, r = ink(num, "pfi", 1000)
        size = 960 / ((bot - top) / 1000)
        base = 946 - (top + bot) / 2 * size / 1000
        x = 523 - (l + r) / 2 * size / 1000
        self.H.append(f'<g id="{name}_nd"><g id="{name}_np"><text id="{name}_num" x="{x:.1f}" y="{base:.1f}" '
                      f'style="{style("pfi", size, n0)}">{num}</text></g></g>')
        sh = L["shadow"]
        ids, sts = self.card_words(name, t0, t1, spec, L["words"], push=(1.25, 1.04, 1.0975),
                                   extra=f"filter:drop-shadow(0 4px 20px rgba(0,0,0,{sh}));" if sh else "")
        self.svg_close()
        self.H.append(f'<div id="{name}_flash" class="full" style="background:#FFFFFF;opacity:0"></div>')
        self.card_close()
        for i in range(10):                       # 8-f (25 fps) entrance glow -> 10 frames at 30 fps, then a hard step down
            q = 0.35 * (i / 9) ** 1.4
            self.tset(f"#{name}_bg", {"backgroundColor": mix(bg0, bg1, q)}, t0 + i * F1)
            self.tset(f"#{name}_num", {"fill": mix(n0, n1, q * 0.6)}, t0 + i * F1)
        self.tset(f"#{name}_bg", {"backgroundColor": bg1}, t0 + 10 * F1)
        self.tset(f"#{name}_num", {"fill": n1}, t0 + 10 * F1)
        for i, bl in enumerate([14, 6, 3, 0]):
            self.tset(f"#{name}_num", {"filter": f"blur({bl}px)"}, t0 + i * F1)
        self.JS.append(f"gsap.set('#{name}_np', {{svgOrigin: '523 946'}}); gsap.set('#{name}_nd', {{svgOrigin: '523 946'}});")
        self.tween(f"#{name}_np", {"scale": 1.48}, {"scale": 1, "ease": "circ.out", "duration": 0.88}, t0)
        self.tween(f"#{name}_nd", {"scale": 1.156}, {"scale": 1, "ease": "none", "duration": t1 - t0}, t0)
        for i, bl in enumerate([3, 2, 1, 0]):
            self.tset(f"#{ids[0]} text", {"filter": f"blur({bl}px)"}, sts[0][0] + i * F1)
        return ids, sts

    def counter(self, name, t0, t1, to=10, lines=("M", "S"), page=None):
        """E15 counter: on the next word the numeral counts 1 -> `to`, one value per frame (Inter Tight 520 px), then the
        following words land one per line under it (tiers in `lines`)"""
        sx = self.once("counter")
        lo = name.lower()
        self.card_open(name, t0, t1, page or PAL["page_counter"])
        self.svg_open()
        toks = self.take(1 + len(lines))
        self._w0 = self.cur - 1 - len(lines)
        csize = HOUSE["layout_px"]["counter"]["num_px"]
        for n in range(1, to + 1):
            top, bot, l, r = ink(str(n), "it6", csize)
            self.H.append(f'<text id="cnt{sx}{n}" x="540" y="{HOUSE["layout_px"]["counter"]["num_y"] - (top + bot) / 2:.1f}" '
                          f'text-anchor="middle" opacity="0" style="{style("it6", csize, PAL["ink"])}">{n}</text>')
            ts = toks[0][1] + (n - 1) * F1
            self.tset(f"#cnt{sx}{n}", {"opacity": 1}, ts)
            if n < to:
                self.tset(f"#cnt{sx}{n}", {"opacity": 0}, ts + F1)
        tags = "abcdefgh"
        for j, (tier, y) in enumerate(zip(lines, HOUSE["layout_px"]["counter"]["line_y"])):
            fam, size = TIERS["card"][tier]
            w = toks[1 + j][0]
            self.text_line([(w, fam, min(size, 900 / adv(w, fam, 1)))], y, PAL["ink"], tid=f"{lo}_{tags[j]}", hidden=True)
        for j in range(len(lines)):
            self.tset(f"#{lo}_{tags[j]}", {"opacity": 1}, toks[1 + j][1])
        self.svg_close()
        self.card_close()
        self.beat(name, [toks[0][1] + 0.12, toks[0][1] + 0.4, toks[-1][1] + 0.2])

    # ------------------------------------------------------------ transitions + motion helpers (X1-X8)
    def push_out(self, name, t_cut, dur=0.75):
        """X4 out: the step card's numeral and words leave to the left (power2.in), the blur growing with the speed; the
        next face world takes it over with face(..., pushin=True)"""
        t = t_cut - dur
        self.tween(f"#{name}_nd, #cw_{name}_drift", {"x": 0}, {"x": -1100, "ease": "power2.in", "duration": dur}, t)
        for i, bl in enumerate(MOTION["push_out_blur_px"]):
            self.tset(f"#{name}_num, #cw_{name}_drift text", {"filter": f"blur({bl}px)"}, t + i * F1)
        self.add_keys(t + 0.5)

    def blur_out(self, sel, t_cut):
        """X1: the whole card blurs over the last 6 frames before a hard cut (1, 2, 4, 7, 11, 16 px; expo.in)"""
        ramp = MOTION["blur_out_px"]
        for i, bl in enumerate(ramp):
            self.tset(sel, {"filter": f"blur({bl}px)"}, t_cut - len(ramp) * F1 + i * F1)

    def pop_in(self, sels, t, every=2, hide_at=None):
        """items pop in one after another, `every` frames apart (opacity + 30 px rise, expo.out 0.3 s)"""
        for i, s in enumerate(sels):
            if hide_at is not None:
                self.tset(s, {"opacity": 0}, hide_at)
            self.tween(s, {"opacity": 0, "y": 30}, {"opacity": 1, "y": 0, "ease": "expo.out", "duration": 0.3}, t + i * every * F1)

    def jump(self, cam, lift, t, scale):
        """X5: a 1-frame scale jump of the page under a brightness lift (+8 % to white, settling in 3 frames)"""
        self.tset(lift, {"opacity": 0.08}, t - 2 * F1)
        self.tset(lift, {"opacity": 0.05}, t + F1)
        self.tset(lift, {"opacity": 0}, t + 3 * F1)
        self.tset(cam, {"scale": scale}, t)

    def rack(self, sels, t, blur=7, opacity=0.6):
        """E24 rack focus: everything but the item being said goes soft and lighter"""
        for s in sels:
            self.tset(s, {"filter": f"blur({blur}px)", "opacity": opacity}, t)

    def box_grow(self, sel, t, lead=5, dur=0.30):
        """E10 / E25: an electric-blue box grows centre-out under a word, starting `lead` frames before it (power1.inOut)"""
        self.tset(sel, {"opacity": 1}, t - lead * F1)
        self.tween(sel, {"scaleX": 0.0125}, {"scaleX": 1, "ease": "power1.inOut", "duration": dur}, t - lead * F1)

    # ------------------------------------------------------------ plates + sound
    def plates(self, switches):
        """the wide / tight switch times from the approved cut: [(t, plate key)]; the mattes follow their plate"""
        self.switches = switches
        keys = list(self.plates_)
        for t, p in switches:
            for v in [p] + [k for k in keys if k != p]:
                self.tset(f"#v{v}", {"autoAlpha": 1 if v == p else 0}, t)
            for v in [p] + [k for k in keys if k != p]:
                self.tset(f"#m{v}", {"autoAlpha": 1 if v == p else 0}, t)

    def sfx(self, name, t, vol, ms=0.0, dur=None):
        """a library sound (library/sfx/<name>.wav) where a world changes or something enters; never on caption words"""
        ensure_sfx(self.P, name)
        self.SFX.append((name, max(0.0, t), vol, ms, dur))

    # ------------------------------------------------------------ write
    def build(self, check_words=True):
        """-> index.html, build/beats.json, build/coverage.txt; returns the coverage lines"""
        if check_words:
            assert self.cur == len(self.W), f"{self.cur} of {len(self.W)} words placed"
        DUR, P = self.dur, self.P
        cam_y = self.cam_y if self.cam_y is not None else 960
        faces = "".join(f'''@font-face {{ font-family: '{fam}'; src: url('assets/fonts/{fn}-{sub}.woff2') format('woff2'); font-weight: {wt}; font-style: {sty}; unicode-range: {rng}; }}
''' for fam, fn, wt, sty in TY["font_faces"] for sub, rng in TY["unicode_ranges"])
        vids = "\n".join(f'<video id="v{k}" class="full" src="{v[0]}" data-start="0" data-duration="{DUR:.2f}" data-track-index="{i}" muted playsinline></video>'
                         for i, (k, v) in enumerate(self.plates_.items()))
        mats = "\n".join(f'<video id="m{k}" class="full" src="{v[1]}" data-start="0" data-duration="{DUR:.2f}" data-track-index="{len(self.plates_) + i}" muted playsinline></video>'
                         for i, (k, v) in enumerate(self.plates_.items()))
        head = f"""<!doctype html>
<html lang="{self.lang}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{esc(self.page_title)}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{faces}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
.full {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }}
svg.full {{ overflow: visible; }}
video.full {{ object-fit: cover; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{DUR:.2f}" data-fps="{FPS}">
<div id="cam" class="full" style="z-index:1;transform-origin:540px {cam_y}px">
{vids}
</div>
<div id="fcap" class="full" style="z-index:2"><svg class="full" viewBox="0 0 1080 1920" width="1080" height="1920">
"""
        mid = f"""</svg></div>
<div id="mcam" class="full" style="z-index:3;transform-origin:540px {cam_y}px">
{mats}
</div>
"""
        aud = [f'<audio id="vo" src="{self.voice}" data-start="0" data-duration="{self.voice_dur:.2f}" data-track-index="40" data-volume="1"></audio>']
        if self.bed and os.path.exists(f"{P}/{self.bed}"):
            aud.append(f'<audio id="bed" src="{self.bed}" data-start="0" data-duration="{DUR:.2f}" data-track-index="41" data-volume="{self.bed_vol}"></audio>')
        for i, (f, t, v, ms, dur) in enumerate(self.SFX):
            dd = dur or SFX_LEN.get(f) or round(probe_dur(f"{P}/assets/sfx/{f}.wav"), 3)
            dd = min(dd, DUR - t)
            aud.append(f'<audio id="sfx{i}" src="assets/sfx/{f}.wav" data-start="{fr(t):.4f}" data-duration="{dd:.4f}" data-media-start="{ms:.3f}" '
                       f'data-track-index="{50 + i}" data-volume="{v}"></audio>')
        html = (head + "\n".join(self.FC + self.FC2) + mid + "\n".join(self.H) + "\n" + "\n".join(aud) +
                '\n<script>\nwindow.__timelines = window.__timelines || {};\nconst tl = gsap.timeline({ paused: true });\n' +
                "\n".join(self.JS) + f'\ntl.set({{}}, {{}}, {DUR:.2f});\nwindow.__timelines["main"] = tl;\n</script>\n</div>\n</body>\n</html>\n')
        open(f"{P}/index.html", "w").write(html)
        # beats (snap.py beats / finals) + face coverage against the look-aways
        shots = [{"t0": a, "t1": b} for _, a, b in sorted(self.SECTIONS, key=lambda s: s[1])]
        json.dump({"fps": FPS, "beats": self.BEATS, "shots": shots}, open(f"{P}/build/beats.json", "w"), indent=1)
        face_at = lambda t: any(a <= t < b for a, b, _ in self.FACE)
        face_s = sum(b - a for a, b, _ in self.FACE)
        lines = [f"face on screen: {face_s:.2f} s of {DUR:.2f} s = {100*face_s/DUR:.1f} %"]
        cw = f"{P}/build/cover_windows.json"
        bad = []
        for a, b in (json.load(open(cw)) if os.path.exists(cw) else []):
            ts = [a + i * F1 for i in range(int((b - a) * FPS) + 1)]
            vis = [t for t in ts if t >= 0 and face_at(t)]
            if vis:
                bad.append((a, b, round(vis[0], 3), round(vis[-1], 3)))
        lines.append(f"cover windows with the face visible: {bad}")
        lines.append(f"display words placed: {self.cur}/{len(self.W)}; sections: {len(self.SECTIONS)}; sfx: {len(self.SFX)}; html {len(html)//1024} KB")
        open(f"{P}/build/coverage.txt", "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return lines


if __name__ == "__main__":
    print(__doc__)
