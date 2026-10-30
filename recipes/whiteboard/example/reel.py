#!/usr/bin/env python3
"""Whiteboard worked example: "willpower is a battery" (an English talking head, about 38 s), script.txt.

    python3 reel.py <project>      # $P: assets/plate.mp4 (your raw cut of script.txt, the WIDE plate, as shot), assets/voice.wav,
                                   # build/words.json (words of the cut), build/face.json (face_track.py on the plate)

Frame 1: the face full screen, "your willpower" in a pill; the board drops on "willpower". One page per thought:
1. "Your willpower works like a battery." (willpower, an arrow down to a battery that charges in four green cells)
2. "Every small choice drains it a little: what to wear, what to eat, what to watch tonight." (the battery, a red drain
   arrow, a cell slashed; a T-shirt, a bowl, a TV, each written as said; two more cells slashed). The one look-away of
   the cut ("wear ... eat") is covered by the board full screen.
3. "By evening it's almost empty, and that's when we make our worst decisions." (a crescent moon and two stars, the
   battery with one red cell, 'almost empty', 'worst decisions' underlined)
4. "A tired brain takes the easy road: the snack, the scroll, the yes you regret." (a brain with zz, a road that forks,
   a red dotted route down the easy branch with a stop per temptation, a sad face where it ends)
5. "So the fix isn't more discipline. It's fewer choices." (a balance: 'more discipline' on the high pan, struck
   out; 'fewer choices' on the low pan, ticked)
6. "Decide the small things once: the same breakfast, the same clothes, the same time to train." (a week as a
   timeline, 'once' circled, a row per habit: a bowl, a T-shirt, a runner, each with one arrow across the week)
7. "Then the one choice that really matters gets a full battery." (a target hit by an arrow, 'matters', a battery
   charged full, 'full')
One look-away, covered by the board full screen (<= 2.5 s; 1.8 s in the dry run). Quiet bed.
Shapes this reel adds (helpers below): battery, charge, slash, shirt, bowl, tv, moon, sparkle, brain, fork-road,
dotted-route, frown, balance, timeline, target. From board.py: arrow, check, underline, zz, runner.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from board import *  # noqa: E402,F403


# ---------------------------------------------------------------- this reel's drawings (rough, seeded like board.py's)
def battery(x, y, w=420, h=170):
    """a battery on its side: the body ((x, y) = top left) and the nub on the right"""
    return [rrect(x, y, w, h), rrect(x + w + 6, y + h * 0.32, 24, h * 0.36)]


def cell(x, y, w, h, k, of=4):
    """[x0, y0, x1, y1] of cell k (0 = left) inside battery(x, y, w, h)"""
    pad, gap = 20, 14
    cw = (w - 2 * pad - gap * (of - 1)) / of
    x0 = x + pad + k * (cw + gap)
    return x0, y + pad, x0 + cw, y + h - pad


def charge(x, y, w, h, cells, of=4):
    """the given cells of battery(x, y, w, h) filled with a marker zigzag"""
    out = []
    for k in cells:
        x0, y0, x1, y1 = cell(x, y, w, h, k, of)
        m = max(3, int((y1 - y0) / 7))
        out.append(poly([(x0 + 5 if i % 2 == 0 else x1 - 5, y0 + 5 + (y1 - y0 - 10) * i / m) for i in range(m + 1)]))
    return out


def slash(x, y, w, h, cells, of=4):
    """one slash through each given cell of battery(x, y, w, h): drained"""
    out = []
    for k in cells:
        x0, y0, x1, y1 = cell(x, y, w, h, k, of)
        out.append(rline(x1 + 12, y0 - 16, x0 - 12, y1 + 16, 0.3))
    return out


def shirt(x, y, s=1.0):
    """a T-shirt, (x, y) = the middle of the collar"""
    pts = [(-28, 0), (-78, 16), (-112, 64), (-82, 92), (-58, 72), (-58, 196), (58, 196), (58, 72), (82, 92), (112, 64), (78, 16), (28, 0)]
    return [poly([(x + a * s, y + b * s) for a, b in pts]), f"M{x - 28 * s:.1f} {y:.1f} Q{x:.1f} {y + 36 * s:.1f} {x + 28 * s:.1f} {y:.1f}"]


def bowl(x, y, s=1.0):
    """a bowl with three wisps of steam, (x, y) = the middle of the rim"""
    r = 100 * s
    out = [rellipse(x, y, r, 18 * s, turns=1.0),
           f"M{x - r:.1f} {y:.1f} Q{x - r:.1f} {y + 112 * s:.1f} {x:.1f} {y + 112 * s:.1f} Q{x + r:.1f} {y + 112 * s:.1f} {x + r:.1f} {y:.1f}"]
    for dx in (-34, 6, 46):
        x0, y0 = x + dx * s, y - 28 * s
        out.append(f"M{x0:.1f} {y0:.1f} Q{x0 - 16 * s:.1f} {y0 - 22 * s:.1f} {x0:.1f} {y0 - 44 * s:.1f} "
                   f"Q{x0 + 16 * s:.1f} {y0 - 66 * s:.1f} {x0:.1f} {y0 - 88 * s:.1f}")
    return out


def tv(x, y, w=190, h=140):
    """an old TV with a knob, an antenna and two legs, (x, y) = top left"""
    cx = x + w / 2
    return [rrect(x, y, w, h), rrect(x + 18, y + 18, w - 64, h - 36), rellipse(x + w - 24, y + h * 0.36, 9, 9),
            rline(cx, y - 2, cx - 46, y - 60, 0.3), rline(cx, y - 2, cx + 42, y - 56, 0.3),
            rline(x + 30, y + h, x + 18, y + h + 26, 0.2), rline(x + w - 30, y + h, x + w - 18, y + h + 26, 0.2)]


def moon(x, y, r=80):
    """a crescent moon opening to the right, (x, y) = the middle of its straight side"""
    k = 1.33 * r
    return [f"M{x:.1f} {y - r:.1f} C{x - k:.1f} {y - r:.1f} {x - k:.1f} {y + r:.1f} {x:.1f} {y + r:.1f} "
            f"C{x - 0.55 * k:.1f} {y + 0.6 * r:.1f} {x - 0.55 * k:.1f} {y - 0.6 * r:.1f} {x:.1f} {y - r:.1f}"]


def sparkle(x, y, s=1.0):
    """a small four-point star"""
    return [rline(x, y - 22 * s, x, y + 22 * s, 0.2), rline(x - 22 * s, y, x + 22 * s, y, 0.2)]


def brain(x, y, w=220, h=140):
    """a brain from the side: a scalloped outline, the middle fold, two curls and the stem; (x, y) = centre"""
    n = 60
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n + 0.3
        k = 1 + 0.09 * abs(math.sin(6 * a))
        pts.append((x + w / 2 * k * math.cos(a), y + h / 2 * k * math.sin(a)))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for p, q in zip(pts[1:], pts[2:]):
        d += f" Q{p[0]:.1f} {p[1]:.1f} {(p[0] + q[0]) / 2:.1f} {(p[1] + q[1]) / 2:.1f}"
    return [d,
            f"M{x - w * 0.02:.1f} {y - h * 0.46:.1f} Q{x + w * 0.14:.1f} {y - h * 0.2:.1f} {x:.1f} {y:.1f} "
            f"Q{x - w * 0.14:.1f} {y + h * 0.2:.1f} {x + w * 0.04:.1f} {y + h * 0.42:.1f}",
            f"M{x - w * 0.38:.1f} {y - h * 0.02:.1f} Q{x - w * 0.27:.1f} {y - h * 0.34:.1f} {x - w * 0.14:.1f} {y - h * 0.12:.1f}",
            f"M{x + w * 0.16:.1f} {y + h * 0.14:.1f} Q{x + w * 0.28:.1f} {y - h * 0.22:.1f} {x + w * 0.38:.1f} {y + h * 0.04:.1f}",
            rline(x + w * 0.16, y + h * 0.48, x + w * 0.24, y + h * 0.8, 0.3)]


def qpt(p0, c, p1, u):
    """the point at u (0..1) on the quadratic curve p0 -> p1 (control c)"""
    return ((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * c[0] + u * u * p1[0], (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * c[1] + u * u * p1[1])


def fork(base, top, left, right):
    """a road from `base` up to a fork at `top`, then two branches: left / right = (control, end); draw it wide, in grey"""
    (lc, le), (rc, re_) = left, right
    return [rline(base[0], base[1], top[0], top[1], 0.3),
            f"M{top[0]:.1f} {top[1]:.1f} Q{lc[0]:.1f} {lc[1]:.1f} {le[0]:.1f} {le[1]:.1f}",
            f"M{top[0]:.1f} {top[1]:.1f} Q{rc[0]:.1f} {rc[1]:.1f} {re_[0]:.1f} {re_[1]:.1f}"]


def dotted(p0, c, p1, n=9, a=0.04, b=0.96):
    """a dotted route along the quadratic p0 -> p1: n short dashes"""
    out, step = [], (b - a) / n
    for k in range(n):
        u0 = a + k * step
        (x0, y0), (x1, y1) = qpt(p0, c, p1, u0), qpt(p0, c, p1, u0 + step * 0.5)
        out.append(rline(x0, y0, x1, y1, 0.1))
    return out


def frown(x, y, r=50):
    """a sad face: the regret at the end of the road"""
    return [rellipse(x, y, r, r), rline(x - r * 0.36, y - r * 0.32, x - r * 0.36, y - r * 0.08, 0.1),
            rline(x + r * 0.36, y - r * 0.32, x + r * 0.36, y - r * 0.08, 0.1),
            f"M{x - r * 0.44:.1f} {y + r * 0.5:.1f} Q{x:.1f} {y + r * 0.12:.1f} {x + r * 0.44:.1f} {y + r * 0.5:.1f}"]


def stand(x, y, top):
    """the post and the foot of a balance: (x, y) = the foot, `top` = the height of the pivot"""
    return [rline(x, y, x, top, 0.2), rline(x - 120, y + 6, x + 120, y + 2, 0.3),
            poly([(x - 24, top + 8), (x, top - 24), (x + 24, top + 8), (x - 24, top + 8)])]


def balance(x1, y1, x2, y2, drop=110, half=78):
    """the tilted beam of a balance from (x1, y1) to (x2, y2) and a pan hanging `drop` below each end"""
    out = [rline(x1, y1, x2, y2, 0.3)]
    for ex, ey in ((x1, y1), (x2, y2)):
        py = ey + drop
        out += [rline(ex, ey, ex - half, py, 0.2), rline(ex, ey, ex + half, py, 0.2),
                f"M{ex - half - 10:.1f} {py:.1f} Q{ex:.1f} {py + 58:.1f} {ex + half + 10:.1f} {py:.1f}"]
    return out


def ticks(x1, x2, n=5):
    """the x of n evenly spaced ticks on an axis from x1 to x2"""
    return [x1 + 50 + (x2 - x1 - 100) * k / (n - 1) for k in range(n)]


def timeline(x1, x2, y, n=5):
    """a time axis from x1 to x2 at y with n ticks (the days of a week)"""
    return [rline(x1, y, x2, y, 0.3)] + [rline(tx, y - 16, tx, y + 16, 0.1) for tx in ticks(x1, x2, n)]


def target(x, y, r=160):
    """a target: two rings and the bullseye"""
    return [rellipse(x, y, r, r), rellipse(x, y, r * 0.64, r * 0.64), rellipse(x, y, r * 0.28, r * 0.28)]


# ---------------------------------------------------------------- the reel
P = sys.argv[1] if len(sys.argv) > 1 else "."
B = Board(P, fixes={"trains": "drains"}, music={"id": "digital-clouds", "db": -22})
t = B.t
s0 = B.split0 + DROP            # the board is down
# the one look-away of this cut: the speaker glances off camera while listing "wear ... eat". cover_windows.py finds the
# look-aways of your own plate (build/cover_windows.json, used when it exists); without one, this keys it to the words
if not B.cover:
    B.cover = [(t("wear") - 0.1, t("^eat"))]

# 1 · willpower is a battery
B.page(B.split0)
B.write("willpower", 540, 290, s0 - 0.05, 120, INK, "middle")
B.draw(arrow(540, 330, 540, 420, 24), t("like"), INK, 7, dur=0.3, snd=False, shape="arrow")
BX = (300, 450, 460, 200)
B.draw(battery(*BX), t("battery") - 0.15, INK, 8, dur=0.36, shape="battery")
B.draw(charge(*BX, range(4)), t("^battery") - 0.25, GREEN, 10, dur=0.45, shape="charge")

# 2 · every small choice drains it: wear, eat, watch (the board goes full screen over the look-away)
B.page(t("every") - 0.05)
BX = (310, 190, 420, 170)
B.draw(battery(*BX), t("every"), INK, 8, dur=0.4, shape="battery")
B.draw(charge(*BX, range(4)), t("small"), GREEN, 10, dur=0.45, snd=False, shape="charge")
B.draw(arrow(830, 200, 830, 350, 24), t("drains"), RED, 7, dur=0.3, shape="arrow")
B.draw(slash(*BX, [3]), t("little"), RED, 8, dur=0.2, snd=False, shape="slash")
B.write("wear", 200, 800, t("wear") - 0.04, 72, BLUE, "middle", dur=0.3)
B.draw(shirt(200, 500, 0.95), t("wear") + 0.28, INK, 7, dur=0.42, shape="shirt")
B.write("eat", 540, 800, t("eat") - 0.04, 72, BLUE, "middle", dur=0.3)
B.draw(bowl(540, 600, 1.0), t("eat") + 0.28, INK, 7, dur=0.45, shape="bowl")
B.write("watch", 880, 800, t("watch") - 0.04, 72, BLUE, "middle", dur=0.3)
B.draw(tv(785, 520, 190, 140), t("watch") + 0.28, INK, 7, dur=0.56, shape="tv")
B.draw(slash(*BX, [2, 1]), t("^tonight") + 0.22, RED, 8, dur=0.2, snd=False, shape="slash")

# 3 · by evening it's almost empty: the worst decisions
B.page(t("by") - 0.05)
B.draw(moon(230, 300, 90), t("evening") - 0.1, BLUE, 8, dur=0.4, shape="moon")
B.draw(sparkle(300, 200, 0.8) + sparkle(330, 370, 0.6), t("evening") + 0.32, BLUE, 6, dur=0.32, snd=False, shape="sparkle")
BX = (440, 230, 420, 170)
B.draw(battery(*BX), t("almost"), INK, 8, dur=0.38, shape="battery")
B.draw(charge(*BX, [0]), t("empty"), RED, 10, dur=0.25, snd=False, shape="charge")
B.write("almost empty", 650, 490, t("empty") + 0.28, 68, RED, "middle", dur=0.45)
B.write("worst decisions", 540, 700, t("worst") - 0.05, 100, INK, "middle", dur=0.7, snd=True)
B.draw(underline(170, 728, 740, 2), t("^decisions") - 0.05, RED, 6, dur=0.3, snd=False, shape="underline")

# 4 · a tired brain takes the easy road: snack, scroll, yes, regret
B.page(t("a tired") - 0.05)
FORK, BASE = (600, 585), (600, 690)
LEFT, RIGHT = ((520, 405), (140, 405)), ((640, 405), (910, 215))
B.draw(brain(600, 770, 250, 150), t("tired"), INK, 7, dur=0.5, shape="brain")
B.draw(zz(752, 676, 1.2), t("tired") + 0.52, BLUE, 6, dur=0.22, snd=False, shape="zz")
B.draw(fork(BASE, FORK, LEFT, RIGHT), t("takes") + 0.1, "#B4B8C0", 30, dur=0.45, shape="fork-road")
B.draw(dotted(FORK, *LEFT), t("easy"), RED, 7, dur=0.72, shape="dotted-route")
B.write("easy road", 360, 335, t("easy") + 0.74, 76, RED, "middle", dur=0.4)
for word, u, (lx, ly) in (("snack", 0.3, (470, 600)), ("scroll", 0.6, (370, 532)), ("yes", 0.88, (215, 502))):
    px, py = qpt(FORK, *LEFT, u)
    B.draw([rellipse(px, py, 11, 11)], t(word) - 0.04, RED, 9, dur=0.1, snd=False, shape="dotted-route")
    B.write(word, lx, ly, t(word) + 0.08, 72, INK, "middle", dur=0.3)
B.draw(frown(95, 310, 52), t("regret") + 0.04, RED, 7, dur=0.4, shape="frown")

# 5 · not more discipline: fewer choices (a balance that tips)
B.page(t("so") - 0.05)
B.draw(stand(540, 830, 350), t("so") + 0.1, INK, 8, dur=0.4, shape="balance")
B.draw(balance(230, 300, 850, 400), t("so") + 0.55, INK, 7, dur=0.58, snd=False, shape="balance")
B.write("more", 230, 540, t("more"), 64, INK, "middle", dur=0.25)
B.write("discipline", 230, 610, t("discipline"), 64, INK, "middle", dur=0.4)
B.draw([rline(80, 628, 380, 502, 0.4)], t("^discipline"), RED, 8, dur=0.22, snd=False, shape="slash")
B.write("fewer", 820, 650, t("fewer") - 0.05, 80, GREEN, "middle", dur=0.3, snd=True)
B.write("choices", 820, 730, t("choices"), 80, GREEN, "middle", dur=0.35)
B.draw(check(1000, 715, 1.4), t("^choices") + 0.05, GREEN, 9, dur=0.22, snd=False, shape="check")

# 6 · decide once: the same every day (a week as a timeline, a row per habit)
B.page(t("decide") - 0.05)
B.write("decide", 400, 225, t("decide"), 100, INK, "middle", dur=0.4)
XS = ticks(250, 1010)
B.draw(timeline(250, 1010, 340), t("small things") - 0.1, INK, 6, dur=0.48, shape="timeline")
for k, (d, x) in enumerate(zip("MTWTF", XS)):
    B.write(d, x, 305, t("^things") - 0.3 + k * 0.1, 44, "#6B707A", "middle", dur=0.1)
B.write("once", 760, 225, t("once") + 0.22, 100, RED, "middle", dur=0.3)
B.draw([rellipse(760, 192, 120, 62)], t("^once") + 0.2, RED, 6, dur=0.25, snd=False, shape="circle")
B.draw(bowl(130, 482, 0.6), t("same"), INK, 6, dur=0.4, shape="bowl")
B.draw(arrow(250, 490, 1010, 490, 24), t("breakfast") + 0.1, BLUE, 6, dur=0.3, snd=False, shape="arrow")
B.draw(shirt(130, 578, 0.6), t("same#2"), INK, 6, dur=0.35, shape="shirt")
B.draw(arrow(250, 636, 1010, 636, 24), t("clothes") + 0.1, BLUE, 6, dur=0.3, snd=False, shape="arrow")
B.draw(runner(130, 728, 0.7), t("time"), INK, 6, dur=0.35, shape="runner")
B.draw(arrow(250, 786, 1010, 786, 24), t("train") - 0.05, BLUE, 6, dur=0.3, snd=False, shape="arrow")

# 7 · the one choice that matters gets a full battery
B.page(t("then") - 0.05)
B.draw(target(300, 450, 170), t("one"), RED, 8, dur=0.5, shape="target")
B.draw(arrow(620, 235, 320, 440, 30), t("really"), INK, 7, dur=0.3, shape="arrow")
B.write("matters", 300, 760, t("matters"), 96, INK, "middle", dur=0.4)
BX = (590, 380, 380, 170)
B.draw(battery(*BX), t("gets") - 0.05, INK, 8, dur=0.36, shape="battery")
B.draw(charge(*BX, range(4)), t("full"), GREEN, 10, dur=0.5, snd=False, shape="charge")
B.write("full", 780, 700, t("^battery#2") + 0.05, 100, GREEN, "middle", dur=0.3, snd=True)

B.build()
