"""Tactile paper: a talk told on printed paper. Full-frame paper scenes (a maroon textured ground or a flat one,
newsprint, archive pages, maps, prints, tickets) that unfurl, curl in and turn with a real WebGL page fold, all designed
motion stepped like stop-motion (12 fps = twos, 8 fps = threes on the payoff), a zoom-blur push, a soft gobo shadow on
close-ups, white / black hand-drawn arrows and one crimson marker that only steer the eye, black condensed pill captions
of 1-3 words; the speaker's face as shot is the pattern break, and a whole-frame page turn reveals them under the paper.

    import sys; sys.path.insert(0, "<skill>/recipes/tactile-paper"); from tactile import *
    tp = Tactile("$P", music={"id": "silent-descent", "db": -18.0, "duck": -4.0}, title="my-reel tactile paper")
    t, F = tp.t, tp.f                                              # word refs (facereel grammar); F(n) = frame n at 30 fps
    tp.image("map", "assets/map.jpg")                              # props drawn per reel with props.py (2x page textures)
    tp.push_camera("hook", t("lighter") - 0.05, 1.217, (637, 1570), upto=t("who") - 0.001)
    s1 = tp.paper_scene("S1", 0, F(103), "hook: map + title, push, page turn -> face")
    s1.ground(CAM("hook"))                                         # the maroon ground moves with the camera
    s1.unfurl("map", 0.0, CAM("hook") + T(0, 88), F0=6)            # the replica unfurl, already curling on frame 0
    s1.title([["Some", "cities"], ["feel"]], 96, [420, 552], rise=[RISE0, RISE1, RISE2], until=1.30 + 2 / 24)
    s1.arrow(REF_ARROW1, 0.0, REF_ARROW1_STEPS, until=1.30 + 2 / 24)
    s1.blur(1.30); s1.gobo(1.47, 0.85, fade_end=t("who") - 0.05)
    tp.comp("hook", ground=CAM("hook", t("who") - 0.001), sheets=[("map", CAM("hook", t("who") - 0.001) + T(0, 88) + T(35, 522), 0.5)])
    s1.reveal(t("who"), "hook")                                    # the whole frame turns away: the speaker's face is under it
    tp.face_scene("S2", F(103), F(163))                            # the plate as shot (a sheet may sit below the face)
    ...
    tp.sound("whoosh-2", 1.30 + 2 / 24 - 0.86, "low whoosh, peaks on the zoom-blur push")
    tp.build(keys=[0.0, 1.0, 3.1], named=K)

Scene parts (each returns nothing, except the sheets: their index, for marks and labels glued to them):
  ground(M) / ground(flat=True)       maroon textured ground under a camera / the flat #6A2947 ground
  sheet(tex, M)                       a page at rest under a camera (static)
  unfurl(tex, t0, M, F0=1, fps=12)    enters from the bottom-right corner (CC Page Turn backwards, measured from the ref)
  turn(tex, t0, M, frames=13)         a page that turns away right to left, revealing the sheet drawn before it
  slide(tex, t0, size, cy, scale, steps)  a print / card that curls in from the right edge and settles tilted
  underline(on, rows, t0) / ellipse(on, (cx, cy), (rx, ry), t0)   crimson marker, glued to sheet `on`
  label(on, text, t0)                 a charcoal word label (plain fact only), glued to sheet `on`, boiling at 8 fps
  title(lines, x, ys, rise=..., until=...)   near-black grotesque title words rising on twos (the hook writes half the line)
  rise(text, t0)                      a word whose letters rise from behind a page's top edge (the "Flat" label)
  arrow(shape, t0, steps, ...)        a tapered brush arrow drawing on, head last (white on paper, black on the flat ground)
  gobo(t0, k) / blur(t)               the soft window shadow on close-ups / the zoom-blur of a push camera
  reveal(t0, comp, fps=12)            the whole frame turns like a page (FAST on twos, EIGHT on threes) onto the speaker's face
Matrix expressions are op lists, folded left like the runtime's chain(): T(x, y) + R(deg) + S(s) + CAM(name[, at]).

The house (house.json; the runtime tactile.js reads its colours and caption numbers from it) never changes; the props,
the hook object, the transitions' objects and the outro are new every reel (components.py plan --style tactile-paper).
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts", "lib"))
from facereel import Reel, BuildError, r3, W, H, GSAP  # noqa: E402,F401

HOUSE = json.load(open(os.path.join(HERE, "house.json")))
PAL = HOUSE["palette"]
CAP = HOUSE["captions"]
BUD = HOUSE["budgets"]
PAGE = [35, 522, 1013, 1478]      # the replica's page space: every sheet's rect (x, y, w, h); textures are 2x of it
TEX_K = 2                         # texture px per page px (props.py draws 2026 x 2956 pages)

# ---------------------------------------------------------------- measured from the reference (replica data, not media)
REPLICA = {
    # unfurl C2: [ref frame, scale, rot deg, tx, ty] of the page while it enters; fold [frame, angle deg, offset, radius]
    "unfurl": [[1, 1.41793, 9.921, 248.08, 425.65], [2, 1.40865, 9.718, 237.23, 402.19], [4, 1.37069, 8.575, 191.8, 318.56],
               [6, 1.28963, 6.546, 121.41, 185.43], [8, 1.20261, 4.384, 63.55, 88.67], [10, 1.1365, 2.884, 32.85, 40.27],
               [12, 1.09036, 1.811, 15.38, 16.68], [14, 1.05854, 1.102, 5.76, 3.89], [16, 1.0356, 0.592, 0.67, -1.76],
               [18, 1.01989, 0.296, -1.26, -4.4], [20, 1.00926, 0.092, -1.97, -3.9], [22, 1.00297, 0.01, -1.29, -2.33],
               [24, 1.00008, 0.0, -0.03, -0.06]],
    "unfurlFold": [[1, 221.85, 414, 90], [2, 221.81, 413, 88], [4, 223.0, 270, 30], [6, 228.25, 130, 23], [8, 227.25, 128, 25],
                   [10, 228.75, 51.5, 15], [12, 220.0, 7, 3]],
    # gobo C8: [ref frame, normal deg, edge px, feather px, darkening] (the runtime reads frame 89 + 3 a step)
    "gobo": [[89, 319.8, 91.0, 30.4, 0.445], [93, 319.8, 99.9, 31.9, 0.447], [99, 319.9, 120.3, 31.8, 0.443],
             [126, 319.5, 179.6, 48.5, 0.513], [133, 319.9, 209.9, 47.0, 0.517], [139, 319.3, 222.5, 42.3, 0.499],
             [145, 320.2, 255.8, 39.6, 0.498], [151, 319.3, 263.9, 37.0, 0.485], [157, 320.6, 303.5, 34.2, 0.485],
             [163, 319.7, 309.9, 31.2, 0.464], [167, 320.8, 340.7, 30.5, 0.466], [180, 320.8, 340.7, 30.5, 0.466]],
}
# the reference's white arrow #1 (C4): its measured centre-line, title -> the page's right-hand column
REF_ARROW1 = {"shaft": [[952.0, 470.0], [980.0, 534.0], [985.0, 559.0], [988.0, 565.0], [991.0, 586.0], [993.0, 588.0], [993.0, 598.0],
                        [995.0, 603.0], [997.0, 641.0], [996.0, 665.0], [994.0, 669.0], [994.0, 687.0], [990.0, 711.0], [987.0, 717.0],
                        [987.0, 723.0], [984.0, 729.0], [982.0, 741.0], [968.0, 780.0], [964.0, 785.0], [955.0, 805.0], [950.0, 811.0],
                        [936.0, 836.0], [927.0, 847.0], [925.0, 852.0], [904.0, 878.0], [861.0, 922.0], [840.0, 940.0], [838.0, 948.0],
                        [847.0, 954.0], [849.0, 960.0], [843.0, 963.0], [810.0, 963.0]],
              "arms": [[[811, 964], [840, 962], [867, 963]], [[811, 964], [815, 945], [819, 926]]]}
REF_ARROW1_STEPS = [[0.3, 0], [0.64, 0], [0.85, 0], [0.98, 0.3], [1, 0.8], [1, 1]]   # [shaft, head] per twos step (ref f2-f12)
REF_ARROWB_STEPS = [[0.45, 0], [0.75, 0], [0.93, 0.3], [1, 1]]                      # the black arrow (ref f193-f199)
ARROW2_STEPS = [[0.55, 0], [0.92, 0], [1, 0.6], [1, 1]]                             # drawn while a slow turn is half-way
FAST = [0.08, 0.2, 0.42, 0.63, 0.9]   # whole-frame turn on twos (ref C7a f63-f73)
EIGHT = [0.1, 0.55, 0.85]             # whole-frame turn on threes, the payoff (ref C7d f832-f841)
BLUR = [[0, 5], [1 / 24, 15], [2 / 24, 17], [4 / 24, 12], [6 / 24, 9], [9 / 24, 6], [11 / 24, 3], [13 / 24, 0]]  # zoom-blur px (T2)
RISE_LETTER = [100, 40, 12, 1, 0]     # the "Flat" letters: px under their rest, one value a twos step (ref C10)
MAROON_BACK = [0.33, 0.14, 0.2]       # the back of a whole-frame sheet painted on the maroon ground
DEFAULT_BACK = [0.93, 0.93, 0.92]     # the back of a sheet when it curls (set per prop: the colour of its paper)


def T(x, y):
    return [["T", x, y]]


def R(d):
    return [["R", d]]


def S(s):
    return [["S", s]]


def CAM(name, at=None):
    return [["cam", name] + ([at] if at is not None else [])]


# ---------------------------------------------------------------- hand-drawn arrow geometry (page / screen px)
def curve(pts, n=40):
    """Catmull-Rom through control points"""
    out = []
    P_ = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        for k in range(n):
            u = k / n
            out.append([0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * u + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * u * u
                               + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * u ** 3) for j in (0, 1)])
    out.append(pts[-1])
    return [[round(x, 1), round(y, 1)] for x, y in out]


def arms(tip, prev, L=46, ang=34):
    a = math.atan2(prev[1] - tip[1], prev[0] - tip[0])
    out = []
    for s in (-1, 1):
        b = a + s * math.radians(ang)
        out.append([[tip[0], tip[1]], [tip[0] + L * 0.5 * math.cos(b), tip[1] + L * 0.5 * math.sin(b)], [tip[0] + L * math.cos(b), tip[1] + L * math.sin(b)]])
    return out


def arrow_shape(pts, head=46, ang=34):
    """a brush arrow through control points [[x, y], ...] (screen px), the open V head at the last point"""
    sh = curve(pts)
    return {"shaft": sh, "arms": arms(sh[-1], sh[-6], head, ang)}


def _mat(ops, cams, t=0.0):
    """the runtime's mx() in Python (guards only; the picture is computed in the browser)"""
    def mul(A, B):
        return [A[0] * B[0] + A[1] * B[3], A[0] * B[1] + A[1] * B[4], A[0] * B[2] + A[1] * B[5] + A[2],
                A[3] * B[0] + A[4] * B[3], A[3] * B[1] + A[4] * B[4], A[3] * B[2] + A[4] * B[5] + A[5]]
    A = None
    for op in ops:
        if op[0] == "T":
            B = [1, 0, op[1], 0, 1, op[2]]
        elif op[0] == "R":
            c, s = math.cos(math.radians(op[1])), math.sin(math.radians(op[1]))
            B = [c, -s, 0, s, c, 0]
        elif op[0] == "S":
            B = [op[1], 0, 0, 0, op[1], 0]
        else:
            c = cams[op[1]]
            B = _mat(T(*c["a"]) + R(c["rot"]) + S(c["s"]) + T(-c["p"][0], -c["p"][1]), cams)
        A = mul(A, B) if A else B
    return A or [1, 0, 0, 0, 1, 0]


class Scene:
    def __init__(self, tp, sid, a, b, what, paper):
        self.tp, self.id, self.a, self.b, self.what, self.paper = tp, sid, a, b, what, paper
        self.d = {"id": sid, "t0": a, "t1": b, "ground": None, "sheets": [], "marks": None, "labels": [], "titles": [],
                  "rises": [], "arrows": [], "gobo": None, "blur": None, "reveal": None}
        self.guards = []

    # -------------------------------------------------------- grounds and sheets
    def ground(self, M=None, flat=False):
        """the maroon textured ground under the matrix M (a camera), or the flat ground (flat=True)"""
        self.d["ground"] = {"flat": True} if flat else {"flat": False, "M": M or []}

    def _sheet(self, sp, guard):
        self.tp._use(sp["tex"])
        self.d["sheets"].append(sp)
        if not self.paper:          # a sheet over the plate: keep it clear of the speaker's face (a box, or its rest box)
            box = guard or self.tp._rest_box(sp)
            self.guards.append((f"{sp['tex']} sheet ({self.id})", box))
        return len(self.d["sheets"]) - 1

    def sheet(self, tex, M, z=0, shade=0.3, back=None, back_op=0.85, rect=None, guard=None):
        return self._sheet({"kind": "static", "tex": tex, "M": M, "rect": rect or PAGE, "z": z, "backOp": back_op,
                            "paper": back or DEFAULT_BACK, "shade": shade}, guard)

    def unfurl(self, tex, t0, M, F0=1, fps=12, shade=0.3, curl_shade=0.45, back=None, back_op=0.85, z=0, guard=None):
        """enters from the bottom-right corner with the measured unfurl (24 ref frames); F0 = the ref frame it starts
        on (6: already curling on frame 0 of the hook), fps 12 on twos / 8 on threes (the bookend replay)"""
        return self._sheet({"kind": "unfurl", "tex": tex, "M": M, "rect": PAGE, "z": z, "backOp": back_op, "paper": back or DEFAULT_BACK,
                            "shade": shade, "curlShade": curl_shade, "t0": t0, "F0": F0, "fps": fps, "step": 24 // fps}, guard)

    def turn(self, tex, t0, M, frames=13, fps=12, shade=0.3, back=None, back_op=0.35, z=0, guard=None):
        """a page that turns away right to left from t0, linear, `frames` drawings on its clock; draw the page under it first"""
        return self._sheet({"kind": "turn", "tex": tex, "M": M, "rect": PAGE, "z": z, "backOp": back_op, "paper": back or DEFAULT_BACK,
                            "shade": shade, "t0": t0, "n": frames, "fps": fps, "phi": -4.55, "c0": 1010, "span": 980, "R": 7}, guard)

    def slide(self, tex, t0, size, cy, scale, steps, fps=12, R=34, z=120, shade=0.35, back=None, back_op=0, guard=None):
        """a print / card (texture `size` px, 2x) curling in from the right edge: steps [[cx, rot, fold x or None], ...]"""
        return self._sheet({"kind": "slide", "tex": tex, "rect": [0, 0, size[0] / 2, size[1] / 2], "cy": cy, "s": scale,
                            "steps": steps, "fps": fps, "R": R, "z": z, "backOp": back_op, "paper": back or DEFAULT_BACK,
                            "shade": shade, "t0": t0}, guard)

    # -------------------------------------------------------- marks glued to a sheet
    def _mark(self, on, m):
        if self.d["marks"] is None:
            self.d["marks"] = {"on": on, "items": []}
        if self.d["marks"]["on"] != on:
            raise BuildError(f"{self.id}: every mark of a scene is glued to one sheet (got {on} and {self.d['marks']['on']})")
        self.d["marks"]["items"].append(m)

    def underline(self, on, rows, t0, w=13):
        """crimson marker under word boxes [[x0, y0, x1, y1], ...] in page px (props.essay_page marks), 80 % on the first drawing"""
        self._mark(on, {"kind": "ul", "rows": rows, "t0": t0, "w": w})

    def ellipse(self, on, c, r, t0, tilt=-8, seed=0.7, w=8):
        """a hand ellipse (1.6 turns, stepped drawings, head last, then a boil) round (cx, cy), radii (rx, ry), sheet space"""
        self._mark(on, {"kind": "ell", "cx": c[0], "cy": c[1], "rx": r[0], "ry": r[1], "tilt": tilt, "seed": seed, "t0": t0, "w": w})

    def label(self, on, text, t0, at=(99, 538), rot=-1.5):
        """a charcoal box label (plain fact: a name, a year), page space `at` (99, 538 = the page's top-left + air)"""
        i = sum(len(s.d["labels"]) for s in self.tp.scenes)
        self.d["labels"].append({"id": f"lbl{i}", "text": text, "on": on, "x": at[0], "y": at[1], "rot": rot, "t0": t0})
        self.tp._text.append(text)

    # -------------------------------------------------------- type and arrows
    def title(self, lines, x, ys, rise, size=None, t0=0.0, until=None, fps=12, ls=None, fill=None):
        """near-black grotesque title words (lines of words, left aligned at x, baselines ys); rise = one table per word
        [[step, px under rest], ...] on twos from t0 (whole and opaque, no fade); gone hard at `until`"""
        ty = HOUSE["type"]["title"]
        size, ls, fill = size or ty["size"], ty["tracking_px"] if ls is None else ls, fill or PAL["title"]
        words, k = [], 0
        for li, ws in enumerate(lines):
            for j, w in enumerate(ws):
                words.append({"w": w, "x": x, "y": ys[li], "prefix": (" ".join(ws[:j]) + " ") if j else None, "rise": rise[k]})
                k += 1
        i = sum(len(s.d["titles"]) for s in self.tp.scenes)
        self.d["titles"].append({"id": f"ttl{i}", "words": words, "size": size, "ls": ls, "fill": fill, "t0": t0, "until": until, "fps": fps})
        self.tp._text.append(" ".join(w["w"] for w in words))

    def rise(self, text, t0, y=430, size=None, cx=540, per=12, fps=12, ls=-3, fill=None, tab=RISE_LETTER):
        """the letters of `text` rise one by one (`per` a second) from behind the top edge of the page under them"""
        i = sum(len(s.d["rises"]) for s in self.tp.scenes)
        self.d["rises"].append({"id": f"rise{i}", "text": text, "t0": t0, "y": y, "size": size or HOUSE["type"]["label"]["size"],
                                "cx": cx, "per": per, "fps": fps, "ls": ls, "fill": fill or PAL["label"], "tab": list(tab)})
        self.tp._text.append(text)

    def arrow(self, shape, t0, steps, w=10, arm=9, color="white", until=None, fps=12):
        """a tapered brush arrow (shape: arrow_shape() or REF_ARROW1), steps [[shaft, head], ...] on twos from t0"""
        i = sum(len(s.d["arrows"]) for s in self.tp.scenes)
        self.d["arrows"].append({"id": f"arw{i}", "shaft": shape["shaft"], "arms": shape["arms"], "t0": t0, "until": until, "fps": fps,
                                 "steps": steps, "w": w, "armW": arm, "fill": PAL["arrow_white"] if color == "white" else PAL["label"]})

    # -------------------------------------------------------- light, camera, reveal
    def gobo(self, t0, k=0.85, fade_end=None):
        """the soft window shadow drifting on a close-up (stepped on twos); fade_end: fades out over the 0.5 s before it"""
        self.d["gobo"] = {"t0": t0, "k": k, "fadeEnd": fade_end}

    def blur(self, t, tab=None):
        """the zoom-blur of a push camera whose scale jumps 2 frames after t (5/15/17 px -> sharp over 13 frames)"""
        self.d["blur"] = {"t": t, "tab": tab or BLUR}

    def reveal(self, t0, comp, fps=12, steps=None, back=None):
        """from t0 the whole frame (tp.comp `comp`, painted at that state) turns away like a page onto the plate"""
        if comp not in self.tp.comps:
            raise BuildError(f"{self.id}: reveal needs tp.comp({comp!r}, ...) first")
        self.d["reveal"] = {"t0": t0, "fps": fps, "fr": steps or (FAST if fps == 12 else EIGHT), "comp": comp, "back": back or MAROON_BACK}


class Tactile(Reel):
    def __init__(self, project, plate=None, music=None, title=None, **kw):
        super().__init__(project, plate=plate, music=music, **kw)
        self.title_ = title or f"{os.path.basename(self.P)} tactile paper"
        self.scenes, self.cams, self.comps, self.bakes, self.imgs = [], {}, {}, {}, {}
        self.caps, self._text = None, []
        self.ground_src = "assets/paper-texture-ground.png"

    def f(self, n):
        """frame n of the 30 fps comp in seconds (scene bounds are frame-exact)"""
        return round(n / self.fps, 4)

    # -------------------------------------------------------- pictures
    def image(self, name, src):
        """a prop texture in the project (assets/...); 2x of page space for pages, any size for slides"""
        if not os.path.exists(os.path.join(self.P, src)):
            raise BuildError(f"{src} is missing in {self.P} (draw the props first: props.py helpers, see example/)")
        self.imgs[name] = src

    def _use(self, tex):
        if tex not in self.imgs and tex not in self.bakes:
            raise BuildError(f"texture {tex!r}: register it with tp.image() or tp.bake() first")

    def bake(self, name, img, inks):
        """a copy of image `img` with marks drawn in at full length (a marked page that later turns keeps its ink)"""
        self.bakes[name] = {"img": img, "A": [TEX_K, 0, -TEX_K * PAGE[0], 0, TEX_K, -TEX_K * PAGE[1]], "inks": inks}

    @staticmethod
    def ul(rows, w=13):
        return {"kind": "ul", "rows": rows, "w": w}

    @staticmethod
    def ell(c, r, tilt=-8, seed=0.7):
        return {"kind": "ell", "cx": c[0], "cy": c[1], "rx": r[0], "ry": r[1], "tilt": tilt, "seed": seed}

    def comp(self, name, ground=None, sheets=(), inks=()):
        """the still a whole-frame reveal turns: ground matrix (None = no ground), sheets [(img, M, scale)], inks [(M, mark, ev, w)]"""
        self.comps[name] = {"ground": ground, "sheets": [{"img": i, "M": m, "k": k} for i, m, k in sheets],
                            "inks": [{"M": m, "mark": mk, "ev": ev, "w": w} for m, mk, ev, w in inks]}

    # -------------------------------------------------------- cameras
    def camera(self, name, at, pivot, scale=1.0, rot=0.0, rate=0.0012, t0=0.0, fps=12, jump=None, upto=None):
        """T(at) R(rot) S(scale * (1 + rate * k)) T(-pivot), k = steps on twos from t0: the slow push on every hold"""
        self.cams[name] = {"a": list(at), "p": list(pivot), "rot": rot, "s": scale, "rate": rate, "fps": fps, "t0": t0,
                           "jump": jump, "upto": upto}
        return name

    def push_camera(self, name, t, scale, pivot, rate=0.0024, upto=None):
        """the zoom-blur push (ref T2): identity until t + 2 frames, then `scale` about `pivot`, then a slow push on twos"""
        tj = t + 2 / 24
        return self.camera(name, pivot, pivot, scale, 0.0, rate, tj, 12, tj, upto)

    def close_camera(self, name, t0, at=(540, 250), pivot=(541.5, 682), scale=1.12, rot=-2.0, rate=0.001):
        """the tilted page close-up (ground strip on top): the page 1.12x, -2 deg, pushing +0.1 % a twos step"""
        return self.camera(name, at, pivot, scale, rot, rate, t0)

    # -------------------------------------------------------- scenes
    def paper_scene(self, sid, a, b, what):
        """a full-frame paper scene (the speaker's face off screen; <= house budget seconds)"""
        self.full_screen(sid, a, b, what, cap=BUD["paper_scene_max_s"])
        s = Scene(self, sid, a, b, what, True)
        self.scenes.append(s)
        return s

    def face_scene(self, sid, a, b, what="the speaker's face as shot"):
        """the plate as shot; a sheet may sit below the speaker's face (guarded), nothing on it"""
        s = Scene(self, sid, a, b, what, False)
        self.scenes.append(s)
        return s

    def _rest_box(self, sp):
        if sp["kind"] == "slide":
            cx, rot, _ = sp["steps"][-1]
            M = T(cx, sp["cy"]) + R(rot) + S(sp["s"]) + T(-sp["rect"][2] / 2, -sp["rect"][3] / 2)
        else:
            M = sp["M"]
        A = _mat(M, self.cams)
        x, y, w, h = sp["rect"] if sp["kind"] != "slide" else [0, 0, sp["rect"][2], sp["rect"][3]]
        pts = [(A[0] * px + A[1] * py + A[2], A[3] * px + A[4] * py + A[5]) for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h))]
        l_, t_ = max(0, min(p[0] for p in pts)), max(0, min(p[1] for p in pts))
        r_, b_ = min(W, max(p[0] for p in pts)), min(H, max(p[1] for p in pts))
        return [l_, t_ - 35, r_ - l_, b_ - t_ + 35]

    # -------------------------------------------------------- captions (ref C5: 1-3 words, hard swaps)
    def captions(self, fixes=None, hide=None, max_words=3, max_chars=17):
        """chunks of <= max_words words / max_chars characters, broken at punctuation, a 1-2 letter word carried to the
        next chunk; hide(t0, end, TEXT) -> True blanks a chunk (a title on screen says the same words, ref R9)"""
        fixes = fixes or {}
        ws = []
        for w in self.words:
            raw = w["raw"].strip()
            core_ = re.sub(r"[^\w]", "", raw.lower())
            if core_ in fixes:
                raw = raw.lower().replace(core_, fixes[core_])
            ws.append([w["s"], w["e"], raw])
        chunks, cur = [], []
        punct = lambda x: bool(re.search(r"[,.;:!?»]$", x))  # noqa: E731
        short = lambda x: len(re.sub(r"\W", "", x)) <= 2 and not punct(x)  # noqa: E731
        for w in ws:
            if cur and (len(cur) >= max_words or len(" ".join(c[2] for c in cur + [w])) > max_chars):
                carry = [cur.pop()] if len(cur) > 1 and short(cur[-1][2]) else []
                chunks.append(cur)
                cur = carry
            cur.append(w)
            if punct(w[2]):
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        caps = []
        for j, c in enumerate(chunks):
            t0 = c[0][0] - 0.03
            t1 = chunks[j + 1][0][0] - 0.03 if j + 1 < len(chunks) else c[-1][1] + 0.3
            if t1 - c[-1][1] > 0.6:
                t1 = c[-1][1] + 0.3
            txt = " ".join(x for _, _, x in c).upper()
            caps.append([r3(max(0, t0)), r3(t1), "" if hide and hide(t0, c[-1][1], txt) else txt])
        self.caps = caps
        return caps

    # -------------------------------------------------------- build
    def _page(self, data, plate, audio):
        css_fonts = self.font_css(["Inter Tight"])
        cp, lb = CAP, HOUSE["type"]["label_box"]
        picks = "\n".join(f'  <img id="pick-{x["id"]}" src="{x["file"]}" alt="" style="display:none" />' for x in self.inserts)
        js = open(os.path.join(HERE, "tactile.js")).read()
        return f"""<!doctype html>
<html lang="{"ru" if self.RU else "en"}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{self.title_}</title>
<script src="{GSAP}"></script>
<style>
{css_fonts}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
.full {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }}
#plate {{ object-fit: cover; z-index: 0; }}
#world {{ z-index: 1; }}
#ground {{ position: absolute; left: 0; top: 0; width: 1280px; height: 2120px; transform-origin: 0 0; z-index: 1; display: none; }}
#flatground {{ background: {PAL["flat_ground"]}; z-index: 1; display: none; }}
#underSvg {{ z-index: 2; }}
#gl {{ z-index: 3; }}
#marks {{ z-index: 4; mix-blend-mode: multiply; }}
.label {{ position: absolute; left: 0; top: 0; transform-origin: 0 0; z-index: 5; display: none; white-space: nowrap;
  font-family: "Inter Tight"; font-weight: 700; font-size: {lb["size"]}px; line-height: 1; letter-spacing: {lb["tracking_px"]}px; color: {PAL["label_box_text"]};
  background: {PAL["label_box"]}; padding: 20px 24px 18px 24px; }}
#titleSvg {{ z-index: 6; }}
#gobo {{ z-index: 7; display: none; }}
#overSvg {{ z-index: 8; }}
#cap {{ position: absolute; left: 0; top: {cp["top"]}px; width: 1080px; height: {cp["height"]}px; display: none; justify-content: center; z-index: 9; }}
#pill {{ height: {cp["height"]}px; overflow: hidden; box-sizing: border-box; padding: 0 {cp["pad"]}px; border-radius: {cp["radius"]}px; background: {PAL["pill"]};
  color: {PAL["caption"]}; font-family: "Inter Tight"; font-weight: 700; font-size: {cp["size"]}px; line-height: {cp["line_height"]}px; white-space: nowrap; }}
#pillTxt {{ display: inline-block; transform-origin: 0 50%; white-space: nowrap; }}
.t {{ font-family: "Inter Tight"; font-weight: 700; }}
svg.full {{ overflow: visible; pointer-events: none; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-fps="{self.fps}" data-duration="{self.T:.3f}">
  <video id="plate" class="full" src="{plate}" data-start="0" data-duration="{self.T:.3f}" data-media-start="0" data-track-index="0" muted playsinline></video>
{picks}
  <div id="world" class="full">
    <img id="ground" src="{self.ground_src}" alt="" />
    <div id="flatground" class="full"></div>
    <svg id="underSvg" class="full" viewBox="0 0 1080 1920"><g id="underG"></g></svg>
    <canvas id="gl" class="full" width="1080" height="1920"></canvas>
    <svg id="marks" class="full" viewBox="0 0 1080 1920"><g id="mkG"></g></svg>
    <svg id="titleSvg" class="full" viewBox="0 0 1080 1920"><g id="titleG"></g></svg>
  </div>
  <div id="gobo" class="full"></div>
  <svg id="overSvg" class="full" viewBox="0 0 1080 1920"></svg>
  <div id="cap"><div id="pill"><span id="pillTxt"></span></div></div>
{audio}
</div>
<script>
const D = {json.dumps(data, ensure_ascii=False)};
{js}</script>
</body>
</html>"""

    def build(self, keys=None, named=None, components=True):
        """write index.html + build/{plan,beats,sfx_events}.json; fails on the face / scene / guard budgets"""
        if not os.path.exists(os.path.join(self.P, self.ground_src)):
            raise BuildError(f"{self.ground_src} is missing: props.ground('{os.path.join(self.P, self.ground_src)}') draws it")
        caps = self.caps if self.caps is not None else self.captions()
        SC = {s.id: (s.a, s.b) for s in self.scenes}
        if keys is None:      # one key at each scene's start, middle and end
            keys = sorted({r3(k) for s in self.scenes for k in (s.a + 0.1, (s.a + s.b) / 2, s.b - 0.1)})
        for i, k in enumerate(keys):
            sc = next((n for n, (a, b) in SC.items() if a <= k < b + 1e-6), self.scenes[-1].id)
            self.beat(f"k{i:02d}", sc, k, k + 0.001, f"{sc} {k:.2f}", keys=[k])
        for b in self.beats:
            b["keys"] = [b["t0"]]
        for s in self.scenes:
            for what, box in s.guards:
                self.guard(what, box, s.a, s.b)
        self.guard("caption pill", CAP["guard_box"], 0, self.T)
        plate = self.held_plate()
        audio = "\n".join(self._audio())
        data = {"T": self.T, "fps": self.fps, "page": PAGE, "R": REPLICA, "cams": self.cams,
                "scenes": [s.d for s in self.scenes],
                "comps": self.comps, "bakes": self.bakes, "imgs": self.imgs, "groundSrc": self.ground_src, "caps": caps,
                "fontText": " ".join(self._text) + " Aa0",
                "house": {"marker": PAL["marker"], "sheetShadow": HOUSE["sheet_shadow"], "glShadow": HOUSE["gl_shadow"],
                          "cap": {"size": CAP["size"], "condense": CAP["condense"], "pad": CAP["pad"]}}}
        open(os.path.join(self.P, "index.html"), "w").write(self._page(data, plate, audio))
        m = self.write_side_files("tactile-paper", {"scenes": SC, "keys": named or {}, "captions": caps})
        errs = self._run_guards()
        print(f"tactile: {self.T:.2f} s | face on screen {m['face_on_screen_pct']} % | full screen {m['full_screen_s']} s in {m['full_screens']} "
              f"(longest {m['longest_full_s']} s) | inserts {m['inserts']} ({m['inserts_per_min']}/min) | sfx {m['sfx']} ({m['sfx_per_10s']}/10 s)")
        for n in self.notes:
            print("  " + n)
        for c in caps:
            print(f"  cap {c[0]:6.2f}-{c[1]:6.2f} {c[2]}")
        lo, hi = BUD["face_on_screen_pct"]
        bad = []
        if not lo <= m["face_on_screen_pct"] <= hi:
            bad.append(f"face on screen {m['face_on_screen_pct']} % outside {lo}-{hi} %")
        if m["longest_full_s"] > BUD["paper_scene_max_s"] + 0.02:
            bad.append(f"a paper scene runs {m['longest_full_s']} s > {BUD['paper_scene_max_s']} s")
        if m["inserts_per_min"] > BUD["inserts_per_min"]:
            bad.append(f"{m['inserts_per_min']} stock inserts a minute (> {BUD['inserts_per_min']})")
        if errs or bad:
            raise BuildError("BUILD FAILED:\n  " + "\n  ".join(errs + bad))
        if components:
            try:
                sys.path.insert(0, os.path.join(SKILL, "scripts"))
                import components as C
                rep = C.check("tactile-paper", self.P)
                print("components: " + " | ".join(C.report("tactile-paper", rep)))
            except Exception as e:              # the catalog check is a warning, never a build failure
                print(f"components: not checked ({e})")
        print("index.html written; next: hf.sh lint, snap.py beats, finals.py preview (WAIT for the user's OK)")
        return m
