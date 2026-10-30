"""Data Story: when the speaker's line carries a quantity, a chart draws itself on cream paper with a red-blue pencil,
handwritten notes pinned to its marks; between the pages the face as shot with the figure caption on a paper band and
pencil notes above the head. Ported from lemo-opuscar styles/dataviz (MIT, (c) 2026 LemoLab, https://github.com/lemomo-ai/lemo-opuscar);
engine.js is the source's Canvas engine adapted to 1080x1920 + a stateless painter on one paused GSAP timeline.

    import sys; sys.path.insert(0, "<skill>/recipes/data-story"); from datastory import DataStory, BLUE, RED
    # An English reel about caffeine. Every number is real and sourced: FDA Consumer Update "Spilling the Beans: How
    # Much Caffeine is Too Much?" (content current as of 2024-08-28): typical caffeine in a 12 fl oz drink, green tea
    # 37 mg, black tea 71 mg; 400 mg a day cited for most adults as not generally associated with negative effects.
    R = DataStory(P, plate="assets/alt.mp4", faces={"assets/alt.mp4": "build/face.json"}, fixes={"cafeine": "caffeine"})
    t = R.t                                                  # word refs, scripts/lib/facereel.py grammar
    R.talk("assets/alt.mp4", 0, 2.62)                        # the plate full frame, as shot (the caption band rides on it)
    R.note("too much?", 64, 320, t("much"), 0.6)             # a pencil note above the head (guarded against the face)
    pg = R.page("p1", 2.62, 4.44, push=1.06)                 # a full-screen paper page (budget: house page_max_s)
    pg.title("Caffeine per 12 oz", t("caffeine"))            # the chart's own headline, typeset
    pg.bars([("green tea", 37, t("green"), None), ("black tea", 71, t("black"), None)],
            x0=80, y0=560, row_h=220, bar_h=90, scale_max=400, width=820)   # from zero, on the 400 mg scale
    pg.mono("FDA 2024", 980, 1150, t("black") + 0.4, align="right")  # the source on the page
    # generators: bars(), day_grid(), plot_frame(), print_()
    R.captions(["your", "green", ...], kickers={0: "FIG. 1 · FDA 2024"})  # the figure caption: chunk starts as word refs
    R.sound("paper-flip", 2.62, "page in")
    R.build()                                                # index.html, build/beats.json, plan.json, sfx_events.json

Calls (each documented below): DataStory(...), talk(), page() -> Page, note(), captions(), sound() (facereel), beat(),
build(); Page: title(), sub(), mono(), hand(), stroke(), ring(), leader(), under(), strike(), wave(), heart(), dot(),
bar(), cell(), box(), fill(), hatch(), img(); generators on Page: plot_frame(), bars(), day_grid(), print_().
Times are edit seconds; every element has a window [a, b] (drawn by the pencil while a < t < b) and an optional `out`.
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts", "lib"))
import facereel as FR  # noqa: E402
from facereel import BuildError, esc, r3  # noqa: E402

HOUSE = json.load(open(os.path.join(HERE, "house.json")))
PAL = HOUSE["palette"]
LAY = HOUSE["layout_px"]
BUD = HOUSE["budgets"]
BLUE, RED, INK, SOFT, ZERO = PAL["blue_pencil"], PAL["red_pencil"], PAL["ink"], PAL["ink_soft"], PAL["zero"]
FLOOR = HOUSE["type"]["floor_px"]
# rough advance widths (em) for fitting and guards; snapshots are the real check
EM = {"hand": 0.40, "serif": 0.50, "mono": 0.60}


def text_w(text, size, kind):
    return len(text) * size * EM[kind]


def ramp(v, vmax, stops=None):
    """a value on the sequential ramp (counts: no natural centre), 0 -> first stop, vmax -> last"""
    stops = stops or PAL["ramp_seq"]
    u = max(0.0, min(1.0, v / vmax)) * (len(stops) - 1)
    i = min(len(stops) - 2, int(u))
    f = u - i
    a = [int(stops[i][k:k + 2], 16) for k in (1, 3, 5)]
    b = [int(stops[i + 1][k:k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * f):02X}" for x, y in zip(a, b))


class Layer:
    """one painter layer: a page on paper (paper=True) or the notes over a face world (paper=False)"""

    def __init__(self, R, lid, t0, t1, paper, ang, cam=None):
        self.R, self.id, self.t0, self.t1, self.paper, self.ang = R, lid, r3(t0), r3(t1), paper, ang
        self.els, self.cam = [], cam or [[r3(t0), 1, 540, 960]]
        self.boxes = []                      # text boxes (x0, y0, x1, y1, what) for the edge checks

    def _el(self, **kw):
        kw = {k: (r3(v) if isinstance(v, float) else v) for k, v in kw.items() if v is not None}
        self.els.append(kw)
        return kw

    def _text_check(self, text, x, y, size, kind, align="left"):
        if size < FLOOR:
            raise BuildError(f"{self.id}: {text!r} at {size} px is under the {FLOOR} px floor")
        w = text_w(text, size, kind)
        x0 = x - w if align == "right" else x - w / 2 if align == "center" else x
        self.boxes.append((x0, y - size * 0.8, x0 + w, y + size * 0.3, text))
        if True:
            if x0 + w > LAY["page"]["right"] + 6 or x0 < 40:
                self.R.warn.append(f"{self.id}: {text!r} may cross the side edge (x {x0:.0f}-{x0 + w:.0f})")
        return (x0, y - size * 0.8, x0 + w, y + size * 0.3)

    # ---------------- elements
    def hand(self, text, x, y, a, dur=None, color=BLUE, size=64, align="left", out=None, pen=True):
        """a handwritten pencil note (Caveat), written on left to right over [a, a + dur] (dur from its length)"""
        dur = dur if dur is not None else max(0.35, min(1.0, 0.045 * len(text)))
        box = self._text_check(text, x, y, size, "hand", align)
        self._el(k="hand", text=text, x=x, y=y, a=a, b=a + dur, color=color, size=size, align=align, out=out, pen=pen)
        return box

    def type(self, text, x, y, a, dur=0.5, font="serif", size=84, color=INK, align="left", weight=400, out=None):
        box = self._text_check(text, x, y, size, "serif" if font == "serif" else "mono", align)
        self._el(k="type", text=text, x=x, y=y, a=a, b=a + dur, font=font, size=size, color=color, align=align, weight=weight, out=out)
        return box

    def title(self, text, a, y=None, size=None, dur=0.55, x=None):
        """the chart's own headline (Playfair Display), typeset letter by letter"""
        return self.type(text, x if x is not None else LAY["page"]["left"], y or LAY["page"]["title_y"], a, dur, "serif",
                         size or LAY["page"]["title_px"])

    def sub(self, text, a, y=None, dur=0.5):
        """the unit / subtitle line under the headline (mono 48)"""
        return self.type(text, LAY["page"]["left"], y or LAY["page"]["sub_y"], a, dur, "mono", 48, SOFT)

    def mono(self, text, x, y, a, dur=0.3, size=48, color=SOFT, align="left", out=None):
        return self.type(text, x, y, a, dur, "mono", size, color, align, out=out)

    def stroke(self, pts, a, dur, color=INK, width=3.0, passes=2, wobble=0.5, seed=1, out=None, pen=True):
        return self._el(k="stroke", pts=[[r3(x), r3(y)] for x, y in pts], a=a, b=a + dur, color=color, width=width,
                        passes=passes, wobble=wobble, seed=seed, out=out, pen=pen)

    def _shape(self, shape, args, a, dur, color, width, seed=1, out=None, pen=True):
        return self._el(k="stroke", shape=shape, args=[r3(v) for v in args], a=a, b=a + dur, color=color, width=width,
                        seed=seed, passes=2, wobble=0.4, out=out, pen=pen)

    def ring(self, x, y, r, a, dur=0.4, color=BLUE, width=3.2, seed=1, out=None):
        """an un-closed hand ring around a mark"""
        return self._shape("ring", [x, y, r], a, dur, color, width, seed, out)

    def leader(self, x0, y0, x1, y1, a, dur=0.3, color=BLUE, bend=0.22, out=None):
        """a wobbly curved leader from a note (x0, y0) to its mark (x1, y1)"""
        return self._shape("leader", [x0, y0, x1, y1, bend], a, dur, color, 2.4, 2, out)

    def under(self, x0, x1, y, a, dur=0.3, color=BLUE, width=3.4, out=None):
        return self._shape("under", [x0, x1, y], a, dur, color, width, 3, out)

    def strike(self, x0, x1, y, a, dur=0.25, color=RED, width=4.0, out=None):
        return self._shape("strike", [x0, x1, y], a, dur, color, width, 4, out)

    def wave(self, x, y, w, a, dur=0.4, color=RED, width=3.2, out=None):
        return self._shape("wave", [x, y, w], a, dur, color, width, 5, out)

    def heart(self, x, y, s, a, dur=0.45, color=BLUE, width=3.2, out=None):
        return self._shape("heart", [x, y, s], a, dur, color, width, 6, out)

    def dot(self, x, y, a, r=16, fill=BLUE):
        return self._el(k="dot", x=x, y=y, a=a, b=a, r=r, fill=fill)

    def bar(self, x0, y0, x1, y1, a, dur=0.45, fill=None, seed=3):
        """a horizontal bar grown from its zero line (x0) to x1, then outlined in pencil"""
        return self._el(k="bar", x0=x0, y0=y0, x1=x1, y1=y1, a=a, b=a + dur, fill=fill, seed=seed)

    def cell(self, x0, y0, x1, y1, a, dur=0.5, color=RED, width=2.6, out=None, pen=True):
        """the dashed empty cell, drawn on"""
        return self._el(k="cell", x0=x0, y0=y0, x1=x1, y1=y1, a=a, b=a + dur, color=color, width=width, out=out, pen=pen)

    def box(self, x0, y0, x1, y1, a, dur=0.2, color=ZERO, width=2.0):
        return self._el(k="box", x0=x0, y0=y0, x1=x1, y1=y1, a=a, b=a + dur, color=color, width=width)

    def fill(self, x0, y0, x1, y1, a, dur=0.25, fill=BLUE, erase=None, pen=True):
        return self._el(k="fill", x0=x0, y0=y0, x1=x1, y1=y1, a=a, b=a + dur, fill=fill, erase=erase, pen=pen)

    def hatch(self, x0, y0, x1, y1, a, dur=0.3, erase=None, color=None, seed=5, pen=True):
        """graphite hatching filling a cell; erase=[t0, t1] sweeps it away left to right"""
        return self._el(k="hatch", x0=x0, y0=y0, x1=x1, y1=y1, a=a, b=a + dur, erase=erase, color=color, seed=seed, pen=pen)

    def img(self, iid, x, y, w, h, a, rot=0.0):
        """a real picture pinned on the paper (registered with R.picture())"""
        return self._el(k="img", id=iid, x=x, y=y, w=w, h=h, a=a, b=a, rot=rot)

    def push(self, t0, t1, zoom, cx=540, cy=960, ease=None):
        """a camera move on the sheet: to `zoom` around world (cx, cy) over [t0, t1]"""
        last = self.cam[-1]
        if t0 > last[0]:
            self.cam.append([r3(t0)] + last[1:4])
        self.cam.append([r3(t1), zoom, cx, cy] + ([ease] if ease else []))

    # ---------------- generators (components fill these per reel; see catalog.json)
    def plot_frame(self, x0, y0, x1, y1, a, ylabel=None, xlabel=None, dur=0.5):
        """an empty plot: y and x axes drawn by the pencil (the axes grow with the story), unit labels in mono"""
        self.stroke([[x0, y0], [x0, y1]], a, dur * 0.5, INK, 3.0, seed=11)
        self.stroke([[x0, y1], [x1, y1]], a + dur * 0.5, dur * 0.5, INK, 3.0, seed=12)
        if ylabel:
            self.mono(ylabel, x0 + 16, y0 + 40, a + dur * 0.3, 0.4)
        if xlabel:
            self.mono(xlabel, x1, y1 + 70, a + dur * 0.8, 0.4, align="right")

    def bars(self, rows, x0, y0, row_h, bar_h, scale_max, width, label_size=56, value_size=48, zero_at=None):
        """a horizontal bar chart from zero (honest scale): rows = [(label, value, t_land, colour or None), ...] drawn in
        that order (the order the speaker names them); each bar lands on its time with its label (Playfair) above and its value
        (mono) at its end. Returns the bars' boxes [(x0, y0, x1, y1), ...]."""
        out = []
        if zero_at is not None:
            self.stroke([[x0, y0 + (row_h - bar_h) - 70], [x0, y0 + row_h * len(rows) + 16]], zero_at, 0.3, INK, 3.0, seed=21)
        for i, (label, v, at, col) in enumerate(rows):
            top = y0 + i * row_h + (row_h - bar_h)
            x1 = x0 + width * v / scale_max
            self.type(label, x0 + 16, top - 18, at - 0.15, 0.3, "serif", label_size, INK)
            self.bar(x0, top, x1, top + bar_h, at, 0.45, fill=col or ramp(v, scale_max))
            self.mono(f"{v:,}".replace(",", " "), x1 + 18, top + bar_h * 0.68, at + 0.3, 0.25, value_size, INK)
            out.append((x0, top, x1, top + bar_h))
        return out

    def day_grid(self, x0, y0, cols, rows, cell, gap, a, dur=0.5):
        """a unit chart of the day: cols x rows cells (one cell = one unit, e.g. an hour), outlines popping in row by row;
        returns cell(i) -> (x0, y0, x1, y1)"""
        n = cols * rows
        for i in range(n):
            c, r = i % cols, i // cols
            cx, cy = x0 + c * (cell + gap), y0 + r * (cell + gap)
            self.box(cx, cy, cx + cell, cy + cell, a + dur * i / n, 0.12)
        return lambda i: (x0 + (i % cols) * (cell + gap), y0 + (i // cols) * (cell + gap),
                          x0 + (i % cols) * (cell + gap) + cell, y0 + (i // cols) * (cell + gap) + cell)

    def print_(self, iid, x, y, w, h, a, rot=-1.5):
        """a real object as a print on the paper (the one accent that bypasses the ramp)"""
        return self.img(iid, x, y, w, h, a, rot)


class DataStory(FR.Reel):
    """One Data Story reel on facereel.Reel (voice, words, SFX levelled by role, budgets, side files).
    plate: the default plate; faces: {plate: face json} for every plate used (face_track.py on that plate)."""

    def __init__(self, project, plate="assets/alt.mp4", faces=None, words=None, fixes=None, tail=0.35, fps=30):
        super().__init__(project, plate=plate, words=words, fixes=fixes, tail=tail, fps=fps, music=None)
        self.fixes = fixes or {}
        self.faces = {}
        for pl, fj in (faces or {self.rel(self.plate_src): "build/face.json"}).items():
            self.faces[pl] = [s for s in json.load(open(os.path.join(self.P, fj)))["samples"] if len(s) > 4 and s[1] is not None]
        self.layers, self.worlds, self.caps, self.pics, self.warn = [], [], [], {}, []
        self.vids = []

    # ---------------- worlds
    def talk(self, plate, t0, t1):
        """the speaker's plate full frame as shot over [t0, t1] (a <video> on the same timeline, no grade); the caption
        band and the pencil notes ride on it"""
        if plate not in self.faces:
            raise BuildError(f"no face file for {plate}: faces={{'{plate}': 'build/face_<x>.json'}} (scripts/face_track.py)")
        L = Layer(self, f"notes{len(self.worlds)}", t0, t1, False, LAY["pencil"]["face_angle"])
        self.worlds.append({"plate": plate, "t0": r3(t0), "t1": r3(t1), "layer": L})
        self.layers.append(L)
        self.vids.append((plate, r3(t0), r3(t1)))
        return L

    def page(self, pid, t0, t1, push=1.05, label="chart page", cx=540, cy=960):
        """a full-screen page of the paper sheet over [t0, t1] with a slow push (x1 -> x`push`); returns the Page"""
        cam = [[r3(t0), 1, 540, 960]] + ([[r3(t1), push, cx, cy, "lin"]] if push != 1 else [])
        L = Layer(self, pid, t0, t1, True, LAY["pencil"]["page_angle"], cam)
        self.layers.append(L)
        self.full_screen(pid, t0, t1, label, cap=BUD["page_max_s"])
        return L

    def note(self, text, x, y, a, dur=None, color=BLUE, size=None, align="left", deco=None):
        """a pencil note above the speaker's head in the face world that holds `a`; it stays until the next note there.
        deco: 'under' | 'ring' | 'strike' | 'wave' (drawn right after the words)"""
        size = size or LAY["note"]["size"]
        w = next((w for w in self.worlds if w["t0"] - 0.01 <= a < w["t1"]), None)
        if not w:
            raise BuildError(f"note {text!r} at {a:.2f} s is not inside a face world")
        L = w["layer"]
        prev = [e for e in L.els if e["k"] == "hand"]
        if prev:
            for e in L.els:
                if "out" not in e:
                    e["out"] = r3(a - 0.15)
        pad = LAY["note"]["pad"]
        w_ = text_w(text, size, "hand")
        sx0 = x - w_ - pad if align == "right" else x - pad
        slip = L._el(k="slip", x0=sx0, y0=y - size * 0.85 - pad * 0.6, x1=sx0 + w_ + 2 * pad,
                     y1=y + size * 0.32 + (size * 0.25 if deco in ("under", "wave") else 0) + pad * 0.6, a=a - 0.15,
                     rot=(-1.2 if len(self.worlds) % 2 else 1.0) * (1 if len(prev) % 2 else -1), seed=len(L.els) + 3)
        box = L.hand(text, x, y, a, dur, color, size, align)
        b = L.els[-1]["b"]
        x0, y0, x1, y1 = box
        y0 = slip["y0"]
        if deco == "under":
            L.under(x0, x1, y + size * 0.22, b + 0.02, 0.28, color)
        elif deco == "ring":
            L.ring((x0 + x1) / 2, y - size * 0.3, max(x1 - x0, 60) * 0.56, b + 0.02, 0.4, color)
        elif deco == "strike":
            L.strike(x0, x1, y - size * 0.3, b + 0.02, 0.25, color)
        elif deco == "wave":
            L.wave(x0, y + size * 0.3, x1 - x0, b + 0.02, 0.45, color)
        if y0 < LAY["note"]["top_limit"]:
            raise BuildError(f"note {text!r} reaches y {y0:.0f} (< {LAY['note']['top_limit']}, Instagram top bar)")
        self._guards.append((f"note {text!r}", (x0, y0, x1 - x0, y1 - y0 + size * 0.3), a, w["t1"], w["plate"]))
        return box

    def picture(self, iid, src, line, a, b):
        """a real picture used on a page (<img> preloaded, counted as an insert)"""
        self.pics[iid] = src
        self.insert(iid, src, a, b, line, "print on the paper", "own")

    # ---------------- captions
    def captions(self, starts, kickers=None, end=None):
        """the figure caption: chunks start at the given word refs (each runs to the next start, the last to `end` or T);
        kickers: {chunk index: mono kicker (figure / source)}; a kicker carries on to the next chunks until replaced"""
        kickers = kickers or {}
        ts = [self.t(s, 0 if i == 0 else self.t(starts[i - 1]) + 0.01) for i, s in enumerate(starts)]
        kick = None
        for i, a in enumerate(ts):
            b = ts[i + 1] if i + 1 < len(ts) else (end or self.T)
            ws = [w for w in self.words if a - 0.02 <= w["s"] < b - 0.02]
            text = []
            for w in ws:
                raw = w["raw"]
                key = raw.strip("«».,?!:;")
                fx = {FR.norm(k): v for k, v in (self.fixes or {}).items()}
                if FR.norm(key) in fx:
                    raw = raw.replace(key, fx[FR.norm(key)])
                text.append({"w": raw, "t": r3(w["s"] - 0.1)})
            new = i in kickers
            if new:
                kick = kickers[i]
            if kick and len(kick) * LAY["cap"]["kicker"] * EM["mono"] > LAY["cap"]["maxW"]:
                self.warn.append(f"kicker {kick!r} may be too wide")
            hard = i + 1 < len(ts) and ts[i + 1] - b < 0.35
            self.caps.append({"t0": r3(a), "t1": r3(b - 0.02), "kicker": kick, "kickerIn": new and a > 0, "hard": hard, "words": text})
            chars = sum(len(x["w"]) + 1 for x in text)
            if chars * LAY["cap"]["size"] * EM["serif"] > 2 * LAY["cap"]["maxW"]:
                self.warn.append(f"caption {i} ({chars} chars) may need 3 lines: split it")

    # ---------------- guards: notes vs the face core of the plate on screen
    def _run_guards(self):
        out, m = [], FR.FACE_MARGIN * 0.5
        for what, (x, y, w, h), a, b, plate in self._guards:
            for s in self.faces[plate]:
                if a + 0.05 <= s[0] <= b - 0.05:
                    l_, t_, r_, b_ = FR.core(s)
                    if x < r_ + m and x + w > l_ - m and y < b_ + m and y + h > t_ - m:
                        out.append(f"{what} touches the face at {s[0]:.2f} s")
                        break
        return out

    def check_budgets(self, extra_cover=()):
        m = self.metrics()
        errs = []
        if m["face_on_screen_pct"] < BUD["face_min_pct"]:
            errs.append(f"the face is on screen {m['face_on_screen_pct']} % (< {BUD['face_min_pct']} %)")
        if m["inserts_per_min"] > BUD["inserts_per_min_max"]:
            errs.append(f"{m['inserts_per_min']} inserts a minute (> {BUD['inserts_per_min_max']})")
        cover = [(w["t0"], w["t1"]) for w in self.worlds]
        span = sorted(cover + [(f[0], f[1]) for f in self.full])
        t = 0.0
        for a, b in span:
            if a > t + 0.02:
                errs.append(f"nothing on screen {t:.2f}-{a:.2f} s")
            t = max(t, b)
        if t < self.T - 0.02:
            errs.append(f"nothing on screen {t:.2f}-{self.T:.2f} s")
        errs += self._run_guards()
        return m, errs

    # ---------------- page
    def build(self, recipe="data-story (lemo-opuscar dataviz)"):
        cap = dict(LAY["cap"])
        spec = {"T": self.T, "cap": cap, "captions": self.caps,
                "layers": [{"id": L.id, "t0": L.t0, "t1": L.t1, "paper": L.paper, "ang": L.ang, "cam": L.cam,
                            "pencilScale": LAY["pencil"]["scale"], "els": L.els} for L in self.layers]}
        engine = open(os.path.join(HERE, "engine.js")).read()
        vids = []
        for i, (pl, a, b) in enumerate(self.vids):
            vids.append(f'<video id="v{i}" class="clip vid" src="{pl}" muted playsinline data-start="{a:.3f}" '
                        f'data-duration="{b - a:.3f}" data-media-start="{a:.3f}" data-track-index="{1 + i % 2}"></video>')
        imgs = "".join(f'<img id="{k}" src="{v}" alt="" style="display:none">' for k, v in self.pics.items())
        body = ("\n".join(vids) + f'\n<canvas id="ds" width="{FR.W}" height="{FR.H}" style="position:absolute;left:0;top:0;z-index:10"></canvas>\n'
                + imgs + "\n" + "\n".join(self._audio()))
        css = ".vid { position:absolute; left:0; top:0; width:1080px; height:1920px; object-fit:cover; z-index:1; }\n#root { background:#F6F3EC; }"
        self.js("(() => { const cv = document.getElementById('ds'), g = cv.getContext('2d'); const S = window.DS_SPEC; const U = {u: 0};\n"
                "  const draw = () => DS.paint(g, S, tl.time());\n"
                "  ['500 64px Caveat', '400 58px \"Playfair Display\"', '400 48px \"JetBrains Mono\"'].forEach(f => { try { document.fonts.load(f); } catch (e) {} });\n"
                "  document.fonts.ready.then(() => { DS.clearCache(); S._ready = false; draw(); });\n"
                f"  tl.fromTo(U, {{u: 0}}, {{u: 1, duration: {self.T}, ease: 'none', onUpdate: draw, immediateRender: false}}, 0);\n"
                "  draw(); })();")
        self.base.insert(0, "window.DS_SPEC = " + json.dumps(spec, ensure_ascii=False) + ";")
        self.write_page(css, body, ["Caveat", "Playfair Display", "JetBrains Mono"])
        # inline the engine before the timeline script
        p = os.path.join(self.P, "index.html")
        html = open(p).read().replace("<script>\n  window.__timelines", "<script>\n" + engine + "\n</script>\n<script>\n  window.__timelines", 1)
        open(p, "w").write(html)
        json.dump(spec, open(os.path.join(self.P, "build", "spec.json"), "w"), ensure_ascii=False, indent=1)
        for w_ in self.warn:
            print("  WARN " + w_)
        return self.finish(recipe, {"pages": [L.id for L in self.layers if L.paper], "captions": len(self.caps)})


FR.FACES.setdefault("JetBrains Mono", ("jetbrains-mono", "100 800"))
