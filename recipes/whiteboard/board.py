"""Whiteboard: the thought is drawn while it is said. A marker board fills the top half, the speaker's face the bottom
half (as shot), and each sentence is drawn live in rough marker strokes with a visible marker following the stroke; white pill
captions sit on the seam with the spoken word swept in yellow.

    import sys; sys.path.insert(0, "<skill>/recipes/whiteboard"); from board import *
    B = Board("$P", music={"id": "forest-mist-whispers", "db": -22})
    t = B.t
    B.page(t("relationship") - 0.2)                                # a new page (the previous one is erased first)
    B.draw(stick(260, 470, 1.5), t("there"), shape="stick")       # rough strokes draw on, the marker follows them
    B.write("you", 260, 700, t("you"), 80)                         # Caveat handwriting, the marker writes it
    B.draw(link(540, 420, 1.4), t("relationship"), RED, shape="link")
    B.build()

The house (house.json; never changes reel to reel):
- frame 1 is the speaker's face full screen with the hook line in a pill; the board drops over the top half on the
  first words and the face slides into the bottom half (pivot and scale measured from build/face.json, so the whole face sits under
  the seam); the plate AS SHOT (no grade, no filter);
- hand-drawn strokes (seeded rough geometry) that draw on, never pop; 2-4 marker colours on a white board; a visible
  marker that follows every stroke and every handwritten word, lifts off between ideas; an eraser wipe between pages;
- one page per thought; captions on the seam as white pills, the spoken word swept in yellow;
- the board goes full screen only to hide a look-away (build/cover_windows.json), <= 2.5 s each; a quiet bed.
What changes every reel: the drawings (each draw() names its shape; components.py plan --style whiteboard lists what the
last reels drew), the page metaphors, the hook and the outro page.
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "lib"))
from facereel import Reel, BuildError, SAFE, core, esc, norm, r3, W, H  # noqa: E402,F401

INK, BLUE, RED, GREEN, GOLD, ORANGE = "#1E1F24", "#1F5FD1", "#D7342B", "#128A4F", "#B8892B", "#E0A100"
SEAM = 960                      # board height in split mode (board on top, the face below)
DROP = 0.42                     # the board drops / the face slides down in this many seconds
REST = (1190.0, 1010.0)         # where the marker waits off the board (the board clips it)

# ---------------------------------------------------------------- rough marker geometry (seeded, repeatable)
rng = random.Random(7)


def seed(n):
    rng.seed(n)


def j(a=1.0):
    return rng.uniform(-a, a)


def rline(x1, y1, x2, y2, bow=1.0):
    L = math.hypot(x2 - x1, y2 - y1) or 1
    nx, ny = -(y2 - y1) / L, (x2 - x1) / L
    o = j(min(7, L * 0.025)) * bow
    cx, cy = (x1 + x2) / 2 + nx * o, (y1 + y2) / 2 + ny * o
    return f"M{x1 + j(1.5):.1f} {y1 + j(1.5):.1f} Q{cx:.1f} {cy:.1f} {x2 + j(1.5):.1f} {y2 + j(1.5):.1f}"


def rrect(x, y, w, h):
    p = [(x - 4, y + 3), (x + w + 3, y - 2), (x + w + 1, y + h + 3), (x - 2, y + h - 1), (x + 6, y - 1)]
    d = f"M{p[0][0]:.1f} {p[0][1]:.1f}"
    for (ax, ay), (bx, by) in zip(p, p[1:]):
        L = math.hypot(bx - ax, by - ay)
        nx, ny = -(by - ay) / L, (bx - ax) / L
        o = j(4)
        d += f" Q{(ax + bx) / 2 + nx * o:.1f} {(ay + by) / 2 + ny * o:.1f} {bx:.1f} {by:.1f}"
    return d


def rellipse(cx, cy, rx, ry, turns=1.12, start=None):
    a0 = rng.uniform(0, 2 * math.pi) if start is None else start
    n = 36
    pts = [(cx + rx * (1 + 0.03 * math.sin(3 * t + a0)) * math.cos(a0 + 2 * math.pi * turns * t),
            cy + ry * (1 + 0.04 * math.cos(2 * t)) * math.sin(a0 + 2 * math.pi * turns * t)) for t in [i / n for i in range(n + 1)]]
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for a, b in zip(pts[1:], pts[2:]):
        d += f" Q{a[0]:.1f} {a[1]:.1f} {(a[0] + b[0]) / 2:.1f} {(a[1] + b[1]) / 2:.1f}"
    return d


def poly(pts):
    return "M" + " L".join(f"{x + j(1):.1f} {y + j(1):.1f}" for x, y in pts)


def arrow(x1, y1, x2, y2, head=26):
    a = math.atan2(y2 - y1, x2 - x1)
    h1 = (x2 - head * math.cos(a - 0.45), y2 - head * math.sin(a - 0.45))
    h2 = (x2 - head * math.cos(a + 0.45), y2 - head * math.sin(a + 0.45))
    return [rline(x1, y1, x2, y2), poly([h1, (x2, y2), h2])]


def stick(x, y, s=1.0, arms="down"):
    """a stick figure, head centre at (x, y); arms: down / up / phone / wave"""
    r = 24 * s
    ps = [rellipse(x, y, r, r * 1.05), rline(x, y + r, x + j(2), y + r + 70 * s, 0.4)]
    ay = y + r + 22 * s
    if arms == "up":
        ps += [rline(x, ay, x - 38 * s, ay - 34 * s), rline(x, ay, x + 38 * s, ay - 34 * s)]
    elif arms == "phone":
        ps += [rline(x, ay, x - 36 * s, ay + 34 * s), poly([(x, ay), (x + 30 * s, ay + 24 * s), (x + 14 * s, ay - 6 * s)])]
    elif arms == "wave":
        ps += [rline(x, ay, x - 36 * s, ay + 36 * s), poly([(x, ay), (x + 34 * s, ay - 10 * s), (x + 46 * s, ay - 44 * s)])]
    else:
        ps += [rline(x, ay, x - 36 * s, ay + 36 * s), rline(x, ay, x + 36 * s, ay + 36 * s)]
    by = y + r + 70 * s
    ps += [rline(x, by, x - 30 * s, by + 56 * s), rline(x, by, x + 30 * s, by + 56 * s)]
    return ps


def runner(x, y, s=1.0):
    """a stick figure running to the right, head at (x, y)"""
    r = 24 * s
    hip = (x - 14 * s, y + r + 64 * s)
    return [rellipse(x, y, r, r * 1.05), rline(x - 2 * s, y + r, hip[0], hip[1], 0.4),
            poly([(x - 40 * s, y + r + 46 * s), (x - 18 * s, y + r + 20 * s), (x + 18 * s, y + r + 38 * s), (x + 40 * s, y + r + 18 * s)]),
            poly([(hip[0] - 46 * s, hip[1] + 34 * s), (hip[0] - 20 * s, hip[1] + 20 * s), hip, (hip[0] + 30 * s, hip[1] + 26 * s), (hip[0] + 30 * s, hip[1] + 60 * s)])]


def crown(x, y, s=1.0):
    return [poly([(x - 30 * s, y), (x - 30 * s, y - 34 * s), (x - 14 * s, y - 16 * s), (x, y - 40 * s), (x + 14 * s, y - 16 * s), (x + 30 * s, y - 34 * s), (x + 30 * s, y), (x - 30 * s, y)])]


def check(x, y, s=1.0):
    return [poly([(x - 22 * s, y), (x - 6 * s, y + 18 * s), (x + 26 * s, y - 22 * s)])]


def cross(x, y, s=1.0):
    return [rline(x - 26 * s, y - 26 * s, x + 26 * s, y + 26 * s), rline(x + 26 * s, y - 26 * s, x - 26 * s, y + 26 * s)]


def phone(x, y, w=110, h=200):
    return [rrect(x, y, w, h), rline(x + w * 0.38, y + h - 18, x + w * 0.62, y + h - 18, 0.2)]


def envelope(x, y, w=86, h=58):
    return [rrect(x, y, w, h), poly([(x, y + 4), (x + w / 2, y + h * 0.55), (x + w, y + 4)])]


def clock(x, y, r=40):
    return [rellipse(x, y, r, r), poly([(x, y - r * 0.6), (x, y), (x + r * 0.45, y + r * 0.2)])]


def bulb(x, y, r=52):
    return [rellipse(x, y, r, r * 1.06, turns=0.86, start=math.pi * 0.62), rline(x - r * 0.42, y + r * 1.02, x + r * 0.42, y + r * 1.02, 0.2),
            rline(x - r * 0.34, y + r * 1.28, x + r * 0.34, y + r * 1.28, 0.2)] + \
        [rline(x + (r + 16) * math.cos(a), y + (r + 16) * math.sin(a), x + (r + 40) * math.cos(a), y + (r + 40) * math.sin(a), 0.2)
         for a in (-2.6, -2.0, -1.57, -1.14, -0.54)]


def bubble(x, y, w, h, tail="left"):
    tx = x + 60 if tail == "left" else x + w - 60
    return [rrect(x, y, w, h), poly([(tx - 22, y + h + 2), (tx - 40 if tail == "left" else tx + 40, y + h + 46), (tx + 12, y + h + 2)])]


def shield(x, y, s=1.0):
    return [f"M{x:.0f} {y - 60 * s:.0f} Q{x + 34 * s:.0f} {y - 44 * s:.0f} {x + 52 * s:.0f} {y - 48 * s:.0f} Q{x + 54 * s:.0f} {y + 20 * s:.0f} {x:.0f} {y + 62 * s:.0f} "
            f"Q{x - 54 * s:.0f} {y + 20 * s:.0f} {x - 52 * s:.0f} {y - 48 * s:.0f} Q{x - 34 * s:.0f} {y - 44 * s:.0f} {x:.0f} {y - 60 * s:.0f}"]


def cloud(x, y, w=300, h=190):
    pts = [(x + w * px, y + h * py) for px, py in [(0.1, 0.6), (0.05, 0.3), (0.28, 0.05), (0.55, 0.0), (0.82, 0.1), (0.98, 0.42), (0.86, 0.78), (0.55, 0.95), (0.25, 0.9), (0.1, 0.6)]]
    d = f"M{pts[0][0]:.0f} {pts[0][1]:.0f}"
    for a, b in zip(pts, pts[1:]):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        d += f" Q{mx + (mx - x - w / 2) * 0.35:.0f} {my + (my - y - h / 2) * 0.35:.0f} {b[0]:.0f} {b[1]:.0f}"
    return [d]


def underline(x, y, w, n=1):
    return [rline(x, y + 10 * i, x + w, y + 10 * i - 3, 0.6) for i in range(n)]


def heart(x, y, s=1.0):
    """a heart centred at (x, y), one stroke"""
    return [f"M{x:.0f} {y + 46 * s:.0f} C{x - 70 * s:.0f} {y + 2 * s:.0f} {x - 66 * s:.0f} {y - 58 * s:.0f} {x - 20 * s:.0f} {y - 50 * s:.0f} "
            f"Q{x - 4 * s:.0f} {y - 46 * s:.0f} {x:.0f} {y - 24 * s:.0f} Q{x + 4 * s:.0f} {y - 46 * s:.0f} {x + 20 * s:.0f} {y - 50 * s:.0f} "
            f"C{x + 66 * s:.0f} {y - 58 * s:.0f} {x + 70 * s:.0f} {y + 2 * s:.0f} {x:.0f} {y + 46 * s:.0f}"]


def crack(x, y, s=1.0):
    return [poly([(x, y - 30 * s), (x - 12 * s, y - 8 * s), (x + 10 * s, y + 6 * s), (x - 6 * s, y + 30 * s)])]


def bell(x, y, s=1.0):
    return [f"M{x - 50 * s:.0f} {y + 40 * s:.0f} Q{x - 36 * s:.0f} {y + 24 * s:.0f} {x - 36 * s:.0f} {y - 6 * s:.0f} Q{x - 34 * s:.0f} {y - 52 * s:.0f} {x:.0f} {y - 56 * s:.0f} "
            f"Q{x + 34 * s:.0f} {y - 52 * s:.0f} {x + 36 * s:.0f} {y - 6 * s:.0f} Q{x + 36 * s:.0f} {y + 24 * s:.0f} {x + 50 * s:.0f} {y + 40 * s:.0f} Z",
            rellipse(x, y + 52 * s, 11 * s, 9 * s), rline(x, y - 56 * s, x, y - 70 * s, 0.2)]


def book(x, y, w=220, h=280):
    return [rrect(x, y, w, h), rline(x + 22, y + 4, x + 22, y + h - 2, 0.2), rline(x + w * 0.28, y + h * 0.3, x + w * 0.86, y + h * 0.3, 0.3)]


def bed(x, y, w=200):
    return [rline(x, y, x + w, y, 0.3), rline(x, y - 50, x, y + 30, 0.2), rline(x + w, y - 20, x + w, y + 30, 0.2),
            rrect(x + 14, y - 44, 56, 34), f"M{x + 76:.0f} {y - 8:.0f} Q{x + 130:.0f} {y - 48:.0f} {x + w - 6:.0f} {y - 10:.0f}"]


def zz(x, y, s=1.0):
    return [poly([(x, y), (x + 26 * s, y), (x, y + 26 * s), (x + 26 * s, y + 26 * s)]),
            poly([(x + 34 * s, y - 34 * s), (x + 52 * s, y - 34 * s), (x + 34 * s, y - 16 * s), (x + 52 * s, y - 16 * s)])]


def mountain(x, y, w=260, h=170):
    return [poly([(x, y), (x + w * 0.38, y - h), (x + w * 0.56, y - h * 0.6), (x + w * 0.7, y - h * 0.82), (x + w, y)]),
            rline(x + w * 0.38, y - h, x + w * 0.38, y - h - 66, 0.2), poly([(x + w * 0.38, y - h - 66), (x + w * 0.38 + 46, y - h - 52), (x + w * 0.38, y - h - 38)])]


def pair(x, y, s=1.0):
    """two stick figures side by side holding hands"""
    return stick(x - 46 * s, y, s) + stick(x + 46 * s, y, s)


def link(x, y, s=1.0):
    """two chain links: a relationship"""
    return [rellipse(x - 44 * s, y, 66 * s, 34 * s), rellipse(x + 44 * s, y, 66 * s, 34 * s)]


def wrench(x, y, s=1.0):
    """a wrench, handle down-left, open jaw up-right"""
    return [rline(x - 70 * s, y + 70 * s, x + 14 * s, y - 14 * s, 0.2), rline(x - 56 * s, y + 84 * s, x + 28 * s, y, 0.2),
            rellipse(x + 40 * s, y - 40 * s, 34 * s, 34 * s, turns=0.78, start=math.pi * 0.95)]


def phone_apps(x, y, w=150, h=260):
    """a phone with a 3 x 3 app grid (draw a red badge on its corner with rellipse)"""
    g = [rrect(x, y, w, h)]
    cw, gap = (w - 48) / 3, 12
    for r_ in range(3):
        for c_ in range(3):
            g.append(rrect(x + 18 + c_ * (cw + gap) - gap / 2, y + 30 + r_ * (cw + gap + 4), cw - 6, cw - 6))
    return g + [rline(x + w * 0.38, y + h - 18, x + w * 0.62, y + h - 18, 0.2)]


def key(x, y, s=1.0):
    """a key: the advice that opens it"""
    return [rellipse(x - 60 * s, y, 34 * s, 34 * s), rline(x - 26 * s, y, x + 90 * s, y, 0.2),
            poly([(x + 52 * s, y), (x + 52 * s, y + 30 * s)]), poly([(x + 78 * s, y), (x + 78 * s, y + 22 * s)])]


def plane(x, y, s=1.0):
    """a paper plane: messages flying"""
    A, B, C, D = (x - 80 * s, y), (x + 80 * s, y - 56 * s), (x - 12 * s, y + 26 * s), (x - 28 * s, y + 62 * s)
    return [poly([A, B, C, A]), poly([B, D, C])]


def wheel(x, y, r=90):
    """a steering wheel: you steer"""
    return [rellipse(x, y, r, r), rellipse(x, y, r * 0.24, r * 0.24), rline(x - r * 0.24, y, x - r * 0.96, y, 0.2),
            rline(x + r * 0.24, y, x + r * 0.96, y, 0.2), rline(x, y + r * 0.24, x, y + r * 0.96, 0.2)]


def house(x, y, w=200, h=150):
    """a house: the people close to you (x, y = bottom left)"""
    return [rrect(x, y - h, w, h), poly([(x - 20, y - h + 4), (x + w / 2, y - h - 90), (x + w + 20, y - h + 4)]), rrect(x + w * 0.4, y - h * 0.55, w * 0.22, h * 0.55)]


def day(x, y, w, h):
    """a big box with hour ticks along the top: a day"""
    return [rrect(x, y, w, h)] + [rline(x + w * k / 6, y - 16, x + w * k / 6, y + 8, 0.1) for k in range(1, 6)]


def sample_path(d, n=40):
    """n points evenly spaced along an SVG path made of M / L / Q / C / Z commands (what the shape helpers write), so the
    marker can follow a stroke from precomputed points: no getPointAtLength() in a timeline callback (the renderer
    seeks in any order)"""
    import re as _re
    toks = _re.findall(r"[MLQCZmlqcz]|-?\d*\.?\d+(?:e-?\d+)?", d)
    pts, cur, start, i, cmd = [], (0.0, 0.0), (0.0, 0.0), 0, "M"
    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v
    while i < len(toks):
        if toks[i] in "MLQCZmlqcz":
            cmd = toks[i].upper(); i += 1
            if cmd == "Z":
                for k in range(1, 11):
                    pts.append((cur[0] + (start[0] - cur[0]) * k / 10, cur[1] + (start[1] - cur[1]) * k / 10))
                cur = start
                continue
        if cmd == "M":
            cur = start = (num(), num()); pts.append(cur); cmd = "L"
        elif cmd == "L":
            nx = (num(), num())
            for k in range(1, 11):
                pts.append((cur[0] + (nx[0] - cur[0]) * k / 10, cur[1] + (nx[1] - cur[1]) * k / 10))
            cur = nx
        elif cmd == "Q":
            c, nx = (num(), num()), (num(), num())
            for k in range(1, 17):
                u = k / 16
                pts.append(((1 - u) ** 2 * cur[0] + 2 * (1 - u) * u * c[0] + u * u * nx[0], (1 - u) ** 2 * cur[1] + 2 * (1 - u) * u * c[1] + u * u * nx[1]))
            cur = nx
        elif cmd == "C":
            c1, c2, nx = (num(), num()), (num(), num()), (num(), num())
            for k in range(1, 21):
                u = k / 20
                a, b, c_, e = (1 - u) ** 3, 3 * (1 - u) ** 2 * u, 3 * (1 - u) * u * u, u ** 3
                pts.append((a * cur[0] + b * c1[0] + c_ * c2[0] + e * nx[0], a * cur[1] + b * c1[1] + c_ * c2[1] + e * nx[1]))
            cur = nx
        else:
            i += 1
    if len(pts) < 2:
        return [[round(pts[0][0], 1), round(pts[0][1], 1)]] * 2 if pts else [[0, 0], [0, 0]]
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    out, k = [], 0
    for m in range(n):
        target = acc[-1] * m / (n - 1)
        while k < len(acc) - 2 and acc[k + 1] < target:
            k += 1
        seg = acc[k + 1] - acc[k] or 1
        u = (target - acc[k]) / seg
        out.append([round(pts[k][0] + (pts[k + 1][0] - pts[k][0]) * u, 1), round(pts[k][1] + (pts[k + 1][1] - pts[k][1]) * u, 1)])
    return out


SHAPES = sorted(n for n, f in list(globals().items()) if callable(f) and n not in {"seed", "j", "Reel", "BuildError", "esc", "norm", "r3", "core", "sample_path"}
                and not n.startswith("_") and f.__module__ == __name__)


class Board(Reel):
    def __init__(self, project, split_at=None, seed_n=7, scale=None, **kw):
        kw.setdefault("tail", 0.3)
        super().__init__(project, **kw)
        seed(seed_n)
        self.pages, self.cur, self.strokes, self.shapes = [], None, [], []
        self.n = 0
        self.split0 = r3(split_at if split_at is not None else (self.words[1]["s"] - 0.06 if len(self.words) > 1 else 0.3))
        self.fullb = []                          # (a, c) full-board windows
        # where the face goes: the whole face core under the seam, centred in [SEAM + 40, 1600]
        cs = [core(s) for s in self.face]          # on the plate, before any move
        top_rel = sorted(c[1] for c in cs)[len(cs) // 20]
        bot_rel = sorted(c[3] for c in cs)[-(len(cs) // 20) - 1]
        self.pivot = (W / 2, (top_rel + bot_rel) / 2)
        hmax = max(c[3] - c[1] for c in cs)
        room = 1600 - (SEAM + 40)
        self.sc = scale or round(min(1.15, room / hmax), 3)
        self.target_y = (SEAM + 40 + 1600) / 2
        if self.sc < 0.9:
            raise BuildError(f"the face is {hmax:.0f} px tall on the plate: it cannot fit under the seam (use the wide plate)")

    # ---------------------------------------------------------------- where the face sits on screen
    def split_k(self, t):
        """0 = full screen, 1 = split, in between while the board drops (power3.inOut like the tweens)"""
        u = 0.0 if t <= self.split0 else (1.0 if t >= self.split0 + DROP else (t - self.split0) / DROP)
        return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2

    def xf(self, t, box):
        k = self.split_k(t)
        push = 1.0 + 0.05 * min(1.0, max(0.0, (t - self.split0) / max(0.1, self.TV - self.split0)))
        s = 1.0 + (self.sc * push - 1.0) * k
        py = self.pivot[1]
        dy = (self.target_y - py) * k
        f = lambda x, y: (W / 2 + (x - W / 2) * s, py + dy + (y - py) * s)
        (l2, t2), (r2, b2) = f(box[0], box[1]), f(box[2], box[3])
        return [l2, t2, r2, b2]

    # ---------------------------------------------------------------- pages and strokes
    def page(self, at, erase=None):
        """start a new page at `at` (the previous page is erased just before, unless it set its own erase time)"""
        if self.cur is not None and self.cur["erase"] is None:
            self.cur["erase"] = r3(at - 0.26)
        self.cur = {"id": f"pg{len(self.pages)}", "start": r3(at), "erase": erase, "items": []}
        self.pages.append(self.cur)
        return self.cur

    def draw(self, paths, at, color=INK, w=7, dur=None, snd=True, shape="line", label=None):
        """rough strokes that draw on from `at` (the marker follows each one); `shape` names the drawing for the catalog"""
        if self.cur is None:
            raise BuildError("draw() before page()")
        paths = paths if isinstance(paths, list) else [paths]
        total = dur or min(1.0, 0.22 + 0.12 * len(paths))
        each = total / len(paths)
        g = []
        for k, d in enumerate(paths):
            self.n += 1
            pid = f"s{self.n}"
            g.append(f'<path id="{pid}" d="{d}" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" stroke-opacity="0" fill="none" '
                     f'stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')
            t0 = at + k * each
            # hidden until its stroke starts: a round cap on an undrawn path would leave a dot on the board
            self.st(f"#{pid}", {"attr": {"stroke-opacity": 1}}, t0)
            self.ft(f"#{pid}", {"attr": {"stroke-dashoffset": 1}}, {"attr": {"stroke-dashoffset": 0}, "duration": round(max(0.08, each), 3), "ease": "power1.inOut"}, t0)
            self.strokes.append({"pts": sample_path(d), "t0": r3(t0), "t1": r3(t0 + max(0.08, each)), "c": color})
        self.cur["items"].append(f'<g data-shape="{shape}">{"".join(g)}</g>')
        self.shapes.append((r3(at), shape, label or shape))
        if snd:          # texture, not a soundboard: one quiet scribble every 1.6 s at most
            self.sound("marker-scribble", at, f"draw {shape}", db=-4, maxlen=0.7, foley_gap=1.6)

    def write(self, text, x, y, at, size=64, color=INK, anchor="start", dur=None, snd=False, rot=0.0):
        """Caveat handwriting revealed left to right at `at`; the marker writes along it"""
        if self.cur is None:
            raise BuildError("write() before page()")
        self.n += 1
        tid = f"t{self.n}"
        wdt = 0.5 * size * len(text) + 20
        x0 = x if anchor == "start" else (x - wdt / 2 if anchor == "middle" else x - wdt)
        d = dur or min(1.1, max(0.3, 0.055 * len(text)))
        self.cur["items"].append(
            f'<clipPath id="{tid}c" clipPathUnits="userSpaceOnUse"><rect id="{tid}r" x="{x0 - 20:.0f}" y="{y - size * 1.2:.0f}" width="0" height="{size * 1.7:.0f}"/></clipPath>'
            f'<text clip-path="url(#{tid}c)" x="{x}" y="{y}" text-anchor="{anchor}" font-family="Caveat" font-weight="700" font-size="{size}" fill="{color}" '
            f'stroke="{color}" stroke-width="{size / 40:.1f}" paint-order="stroke" transform="rotate({rot} {x} {y})">{esc(text)}</text>')
        self.ft(f"#{tid}r", {"attr": {"width": 0}}, {"attr": {"width": round(wdt + 40)}, "duration": round(d, 3), "ease": "none"}, at)
        self.strokes.append({"text": [r3(x0), r3(x0 + wdt), r3(y), size], "t0": r3(at), "t1": r3(at + d), "c": color})
        if snd:
            self.sound("pencil-write", at, f"write {text}", db=-4, maxlen=0.7, foley_gap=1.6)

    # ---------------------------------------------------------------- full board over a look-away
    def _full_boards(self):
        hide = []
        for c0, c1 in self.cover:
            a, c = max(c0 - 0.3, self.split0 + DROP + 0.1), c1 + 0.3
            if hide and a <= hide[-1][1] + 0.4:
                hide[-1][1] = c
            else:
                hide.append([a, c])
        for a, c in hide:
            self.full_screen(f"board{len(self.fullb)}", a, c, "the board full screen over a look-away", din=0.28, dout=0.0)
            self.fullb.append((r3(a), r3(c)))
            self.ft("#board", {"height": SEAM}, {"height": H, "duration": 0.28, "ease": "power3.inOut"}, a - 0.28)
            # the drawing moves to the centre of the full board, unscaled: x1.3 pushed labels near the edges off the frame
            self.ft("#board svg", {"y": 0}, {"y": 480, "duration": 0.28, "ease": "power3.inOut"}, a - 0.28)
            self.tween("#board", {"height": H}, {"height": SEAM, "duration": 0.3, "ease": "power3.inOut"}, c)
            self.tween("#board svg", {"y": 480}, {"y": 0, "duration": 0.3, "ease": "power3.inOut"}, c)
            self.sound("whoosh-3", a - 0.28, "full board", db=-4)
        # full_screen() counts [a, c]; the board is fully over the face from a (it starts growing at a - 0.28)

    # ---------------------------------------------------------------- captions: pills on the seam, the word swept in yellow
    def _captions(self):
        hide = [(a - 0.3, c + 0.3) for a, c in self.fullb] + [(0.0, self.split0 + 0.45)]
        def hidden(t):
            return any(a - 0.05 <= t < b for a, b in hide)
        lines, cur = [], []
        for w in self.words:
            if hidden(w["s"]):
                if cur:
                    lines.append(cur)
                    cur = []
                continue
            cur.append(w)
            if len(cur) >= 3 or w["raw"][-1] in ".,?!:»–":
                lines.append(cur)
                cur = []
        if cur:
            lines.append(cur)
        out = []
        for li, ln in enumerate(lines):
            a = ln[0]["s"] - 0.04
            c = (lines[li + 1][0]["s"] - 0.04) if li + 1 < len(lines) else ln[-1]["e"] + 0.5
            c = min(c, ln[-1]["e"] + 0.5, self.T)
            c = min([c] + [x - 0.02 for x, _ in hide if x > a])
            c = max(c, a + 0.2)
            spans = " ".join(f'<span id="c{li}w{wi}">{esc(w["text"])}</span>' for wi, w in enumerate(ln))
            out.append(f'<div id="cl{li}" class="cap"><div class="pill">{spans}</div></div>')
            self.ft(f"#cl{li}", {"autoAlpha": 0, "scale": 0.92}, {"autoAlpha": 1, "scale": 1, "duration": 0.14, "ease": "back.out(2)"}, a)
            self.tween(f"#cl{li}", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.06}, c)
            for wi, w in enumerate(ln):
                self.ft(f"#c{li}w{wi}", {"backgroundSize": "0% 100%"}, {"backgroundSize": "100% 100%", "duration": 0.14, "ease": "power2.out"}, w["s"] - 0.02)
        pre = [w for w in self.words if w["s"] < self.split0 + 0.3]
        if pre:            # the hook: the first words in a pill under the face, on frame 1
            out.append(f'<div id="hk" class="cap hk"><div class="pill">{esc(" ".join(w["text"] for w in pre))}</div></div>')
            self.st("#hk", {"autoAlpha": 1}, 0)
            self.tween("#hk", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.12}, self.split0 + 0.2)
        self.caption_lines = [(r3(lines[i][0]["s"]), " ".join(w["text"] for w in lines[i])) for i in range(len(lines))]
        return "".join(out)

    # ---------------------------------------------------------------- the marker
    def _marker_js(self):
        S = sorted(self.strokes, key=lambda s: s["t0"])
        pages = [{"t": p["start"], "e": p["erase"]} for p in self.pages]
        return f"""(() => {{ const S = {json.dumps(S)}; const R = [{REST[0]}, {REST[1]}];
  const mk = document.getElementById("mk"), cap = document.getElementById("mkc"); const P = {{u: 0}};
  const io = (u) => u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
  const at = (s, u, t) => {{
    if (s.text) {{ const [x0, x1, y, sz] = s.text; return [x0 + (x1 - x0) * u, y - sz * 0.32 + Math.sin(t * 46) * sz * 0.12]; }}
    const q = s.pts, f = Math.min(q.length - 1.0001, Math.max(0, io(u) * (q.length - 1))), k = Math.floor(f), r = f - k;
    return [q[k][0] + (q[k + 1][0] - q[k][0]) * r, q[k][1] + (q[k + 1][1] - q[k][1]) * r]; }};
  const mix = (a, b, u) => [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u];
  const paint = () => {{ const t = tl.time(); let pos = R, c = null;
    let i = S.findIndex((s) => s.t0 <= t && t <= s.t1);
    if (i >= 0) {{ const s = S[i]; pos = at(s, (t - s.t0) / Math.max(0.001, s.t1 - s.t0), t); c = s.c; }}
    else {{ const nx = S.findIndex((s) => s.t0 > t); const pv = nx < 0 ? S.length - 1 : nx - 1;
      const pe = pv >= 0 ? at(S[pv], 1, S[pv].t1) : R, ps = nx >= 0 ? at(S[nx], 0, S[nx].t0) : R;
      const te = pv >= 0 ? S[pv].t1 : -9, ts = nx >= 0 ? S[nx].t0 : 1e9;
      if (ts - te <= 0.6) {{ pos = mix(pe, ps, io((t - te) / Math.max(0.001, ts - te))); c = (S[nx] || S[pv]).c; }}
      else if (t - te < 0.28) {{ pos = mix(pe, R, io((t - te) / 0.28)); c = S[pv].c; }}
      else if (ts - t < 0.28) {{ pos = mix(R, ps, io(1 - (ts - t) / 0.28)); c = S[nx].c; }} }}
    mk.setAttribute("transform", "translate(" + pos[0].toFixed(1) + " " + pos[1].toFixed(1) + ") rotate(" + (-24 + Math.sin(t * 5.3) * 3).toFixed(2) + ")");
    if (c) cap.setAttribute("fill", c); }};
  tl.fromTo(P, {{u: 0}}, {{u: 1, duration: {self.T}, ease: "none", onUpdate: paint, immediateRender: false}}, 0); }})();"""

    # ---------------------------------------------------------------- the page
    def build(self, components=True):
        if self.cur is not None and self.cur["erase"] is None:
            self.cur["erase"] = self.T + 1
        # the split: the board drops over the top half, the face slides into the bottom half (as shot). These come
        # first: the first tween on #board sets its load-time baseline, and a full board added before them made
        # frame 1 open with the board already down over the face
        py = self.pivot[1]
        self.ft("#board", {"height": 0}, {"height": SEAM, "duration": DROP, "ease": "power3.inOut"}, self.split0)
        self.ft("#vid", {"y": 0}, {"y": round(self.target_y - py, 1), "duration": DROP, "ease": "power3.inOut"}, self.split0)
        self.ft("#vidz", {"scale": 1.0}, {"scale": self.sc, "duration": DROP, "ease": "power3.inOut"}, self.split0)
        self.ft("#vidp", {"scale": 1.0}, {"scale": 1.05, "duration": round(self.TV - self.split0, 3), "ease": "none"}, self.split0)
        self.sound("whoosh-1", self.split0 - 0.05, "the board drops", db=-2)
        self._full_boards()
        caps = self._captions()
        er_html = []
        for pg in self.pages:
            e = pg["erase"]
            if e >= self.T:
                continue
            self.ft(f"#{pg['id']}r", {"attr": {"x": -40}}, {"attr": {"x": 1120}, "duration": 0.32, "ease": "power2.inOut"}, e)
            self.ft(f"#{pg['id']}e", {"x": -260, "autoAlpha": 1}, {"x": 1180, "autoAlpha": 1, "duration": 0.32, "ease": "power2.inOut"}, e)
            self.st(f"#{pg['id']}e", {"autoAlpha": 0}, e + 0.33)
            self.sound("whoosh-2", e, "eraser", db=-4)
            er_html.append(f'<div id="{pg["id"]}e" class="eraser"></div>')
            self.beat(pg["id"], "page", pg["start"], e, f"page {pg['id'][2:]}",
                      [pg["start"] + 0.5, (pg["start"] + e) / 2, e - 0.08])
        last = self.pages[-1] if self.pages else None
        if last and last["erase"] >= self.T:
            self.beat(last["id"], "page", last["start"], self.T, f"page {last['id'][2:]}", [last["start"] + 0.5, (last["start"] + self.T) / 2, self.T - 0.1])
        svg_pages = "".join(f'<clipPath id="{pg["id"]}c" clipPathUnits="userSpaceOnUse"><rect id="{pg["id"]}r" x="-40" y="0" width="1200" height="{SEAM}"/></clipPath>'
                            f'<g id="{pg["id"]}" clip-path="url(#{pg["id"]}c)">{"".join(pg["items"])}</g>' for pg in self.pages)
        self.js(self._marker_js())
        plate = self.held_plate()
        grain = self.grain()
        audio = self._audio()
        css = BASE_CSS.replace("{PY}", f"{py:.0f}").replace("assets/grain.png", grain)
        body = f"""
 <div id="spk"><div id="vid"><div id="vidz"><div id="vidp"><video id="vw" src="{plate}" data-start="0" data-duration="{self.T}" data-track-index="0" muted playsinline></video></div></div></div></div>
 <div id="board"><div id="ghost"></div>
  <svg viewBox="0 0 {W} {SEAM}"><defs><filter id="boil"><feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="4"/>
   <feDisplacementMap in="SourceGraphic" scale="3"/></filter></defs><g filter="url(#boil)">{svg_pages}</g>
   <g id="mk" transform="translate({REST[0]} {REST[1]})"><g transform="translate(6 -6)"><rect x="-6" y="-196" width="44" height="150" rx="10" fill="#F4F2EE" stroke="#3A3A3A" stroke-width="3"/>
    <rect id="mkc" x="-6" y="-92" width="44" height="46" rx="6" fill="{INK}"/><path d="M2 -46 L30 -46 L22 -16 L10 -16 Z" fill="#3A3A3A"/><path d="M12 -16 L20 -16 L17 0 L15 0 Z" fill="#1A1A1A"/></g>
   </g></svg>
  {''.join(er_html)}<div id="tray"></div></div>
 {caps}
 {chr(10).join(audio)}
"""
        self.write_page(css, body, ["Inter", "Caveat"])
        m = self.finish("whiteboard", {"split_at": self.split0, "scale": self.sc, "pivot_y": round(py), "pages": [(p["id"], p["start"], p["erase"]) for p in self.pages],
                                       "shapes": self.shapes, "strokes": len(self.strokes), "full_board": self.fullb})
        if components:
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
                import components as C
                rep = C.check("whiteboard", self.P)
                print("components: " + " | ".join(C.report("whiteboard", rep)))
            except Exception as e:              # the catalog check is a warning, never a build failure
                print(f"components: not checked ({e})")
        print(f"  {len(self.pages)} pages, {len(self.strokes)} strokes, split at {self.split0:.2f} s, face x{self.sc} under the seam")
        return m

    def check_budgets(self, extra_cover=()):
        m, errs = super().check_budgets(extra_cover)
        # the seam captions cover the board's bottom (SEAM - 46 ..): nothing may be drawn or written there
        low = [s for s in self.strokes if (max(p[1] for p in s["pts"]) if "pts" in s else s["text"][2] + s["text"][3] * 0.25) > SEAM - 58]
        if low:
            errs.append(f"{len(low)} stroke(s) / word(s) below y {SEAM - 58}, under the seam captions (first at {low[0]['t0']:.2f} s): move them up")
        # in split mode the whole face must sit under the seam (the board never cuts the forehead)
        for s in self.face:
            if s[0] >= self.split0 + DROP and not any(a - 0.3 <= s[0] <= c + 0.3 for a, c in self.fullb):
                f = self.face_at(s)
                if f[1] < SEAM + 8:
                    errs.append(f"the face reaches y {f[1]:.0f} at {s[0]:.2f} s, over the seam ({SEAM}): lower the scale")
                    break
        return m, errs


BASE_CSS = f"""
#spk {{ position: absolute; inset: 0; overflow: hidden; background: #111; }}
#vid {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
#vidz, #vidp {{ position: absolute; inset: 0; transform-origin: 540px {{PY}}px; }}
#vid video {{ width: {W}px; height: {H}px; object-fit: cover; }}
#board {{ position: absolute; left: 0; top: 0; width: {W}px; height: 0px; overflow: hidden; z-index: 5;
  background: radial-gradient(ellipse at 30% 15%, #FFFFFF 0%, #FAFAF8 50%, #EFF0EC 100%); box-shadow: 0 10px 30px rgba(0,0,0,.35); }}
#board svg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {SEAM}px; transform-origin: 540px {SEAM // 2}px; overflow: visible; }}
#ghost {{ position: absolute; inset: 0; opacity: .14; background: url(assets/grain.png); background-size: 600px; mix-blend-mode: multiply; filter: grayscale(1) contrast(.4) brightness(1.5); }}
#tray {{ position: absolute; left: 0; right: 0; bottom: 0; height: 20px; background: linear-gradient(#d9dbe0, #9da1aa 60%, #7d828c); box-shadow: 0 -2px 6px rgba(0,0,0,.15); }}
.eraser {{ position: absolute; top: 0; left: 0; width: 230px; height: 100%; opacity: 0; visibility: hidden; z-index: 6;
  background: linear-gradient(90deg, rgba(246,246,242,0), rgba(246,246,242,.95) 30%, rgba(246,246,242,.95) 70%, rgba(246,246,242,0)); }}
.cap {{ position: absolute; left: 0; right: 0; top: {SEAM - 46}px; display: flex; justify-content: center; opacity: 0; visibility: hidden; z-index: 8; }}
.cap.hk {{ top: 1480px; }}
.pill {{ background: #fff; color: #111; font-family: Inter; font-weight: 750; font-size: 52px; letter-spacing: -0.02em; padding: 14px 30px 16px; border-radius: 22px;
  box-shadow: 0 8px 28px rgba(0,0,0,.28); white-space: nowrap; }}
.cap.hk .pill {{ white-space: normal; max-width: 880px; text-align: center; line-height: 1.15; }}
.pill span {{ background-image: linear-gradient(#FFE14D, #FFE14D); background-repeat: no-repeat; background-position: 0 85%; background-size: 0% 100%; border-radius: 6px; padding: 0 2px; }}
"""
