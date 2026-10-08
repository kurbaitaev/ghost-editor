#!/usr/bin/env python3
"""'Two directions' explainer -> index.html (HyperFrames, 1080x1920).

One continuous world (sky above a mid-frame horizon, soil below) with a
procedurally grown tree: branches draw upward while roots draw downward.
A camera (#cam: translate + scale, origin 0 0) moves over the world.
Every beat is keyed to WORDS of the voiceover (voice/words.json), not to
fixed seconds, so a new voice take only needs `python3 build.py`.
"""
import json, math, random, re

W_, H_ = 1080, 1920
HZ = 1400                      # horizon, world y
WORLD_H = 3600
words = json.load(open("voice/words.json"))
VO_END = words[-1]["e"]
TOTAL = round(VO_END + 2.8, 3)


def norm(s):
    return re.sub(r"[^a-z']", "", s.lower())


def W(text, n=1, end=False):
    """start (or end) time of the n-th occurrence of a word"""
    k = 0
    for w in words:
        if norm(w["w"]) == norm(text):
            k += 1
            if k == n:
                return w["e"] if end else w["s"]
    raise SystemExit(f"word not found: {text} #{n}")


rng = random.Random(4)

# ---------------------------------------------------------------- tree geometry
branches, roots, tips, root_tips = [], [], [], []   # (d, depth, width)


def grow(x, y, ang, length, depth, maxd, out, up, tips_out):
    if depth > maxd or length < 14:
        tips_out.append((x, y, depth))
        return
    wob = (0.18 if up else 0.42)
    a = ang + rng.uniform(-wob, wob) * 0.5
    x2, y2 = x + math.cos(a) * length, y + math.sin(a) * length
    # quadratic curve with a sideways bow; roots bow more (they wander)
    mx, my = (x + x2) / 2, (y + y2) / 2
    bow = rng.uniform(-1, 1) * length * (0.12 if up else 0.28)
    cx, cy = mx + math.cos(a + math.pi / 2) * bow, my + math.sin(a + math.pi / 2) * bow
    width = max(1.6, (26 if up else 20) * (0.66 ** depth))
    out.append((f"M{x:.1f},{y:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}", depth, width))
    kids = 2 if depth < 2 else rng.choice([2, 2, 3])
    spread = (0.52 if up else 0.62)
    for i in range(kids):
        off = (i - (kids - 1) / 2) * spread * 2 / max(1, kids - 1) + rng.uniform(-0.12, 0.12)
        grow(x2, y2, a + off, length * rng.uniform(0.68, 0.8), depth + 1, maxd, out, up, tips_out)


grow(540, HZ, -math.pi / 2, 250, 0, 6, branches, True, tips)
grow(540, HZ, math.pi / 2, 210, 0, 6, roots, False, root_tips)
# the tap root keeps going down: the path the camera follows underground
tap = []
x, y = 540, HZ + 330
for i in range(9):
    x2, y2 = x + rng.uniform(-60, 60), y + 205
    tap.append(f"M{x:.1f},{y:.1f} Q{x + rng.uniform(-70, 70):.1f},{(y + y2) / 2:.1f} {x2:.1f},{y2:.1f}")
    x, y = x2, y2
TAP_END = (x, y)
# extra deep roots for the seasons beat
deep = []
dtips = []
for sx in (380, 700):
    grow(sx, HZ + 520, math.pi / 2 + (0.3 if sx < 540 else -0.3), 170, 3, 7, deep, False, dtips)

leaf_tips = [t for t in tips if t[2] >= 4]
leaves = []
for (lx, ly, d) in leaf_tips:
    for _ in range(3):
        leaves.append((lx + rng.uniform(-26, 26), ly + rng.uniform(-26, 18), rng.uniform(12, 24), rng.choice(["#6E8B3D", "#7FA048", "#5C7A33", "#8DAE52"])))
rng.shuffle(leaves)
fruit_pts = sorted(leaf_tips, key=lambda t: t[0])[:: max(1, len(leaf_tips) // 7)][:7]
FRUIT_ZOOM = fruit_pts[3][:2]
blossoms = [(lx + rng.uniform(-20, 20), ly + rng.uniform(-20, 12)) for (lx, ly, d) in leaf_tips[::2]]
rocks = []
for i in range(46):
    ry = rng.uniform(HZ + 120, WORLD_H - 60)
    rocks.append((rng.uniform(40, 1040), ry, rng.uniform(10, 46), rng.uniform(8, 30), rng.uniform(0, 180), rng.choice(["#3A2C22", "#45352A", "#2F241C"])))
# big rocks around the tap-root tip (the resistance)
tip_rocks = [(TAP_END[0] - 190, TAP_END[1] - 330, 120, 70, 20), (TAP_END[0] + 170, TAP_END[1] - 150, 140, 80, -15),
             (TAP_END[0] - 150, TAP_END[1] + 60, 110, 64, 8), (TAP_END[0] + 150, TAP_END[1] + 200, 130, 72, -24)]
pebbles = [(rng.uniform(0, 1080), rng.uniform(HZ + 20, WORLD_H), rng.uniform(1.5, 4.5)) for _ in range(420)]
snow = [(rng.uniform(0, 1080), rng.uniform(-200, 0), rng.uniform(3, 7), rng.uniform(0, 0.5)) for _ in range(70)]
fall = [(rng.choice(leaves)[0], rng.choice(leaves)[1], rng.uniform(8, 14)) for _ in range(26)]

# ---------------------------------------------------------------- camera
def cam(cx, cy, s=1.0):
    """world point (cx, cy) at screen centre, scale s"""
    return {"x": round(540 - s * cx, 1), "y": round(960 - s * cy, 1), "scale": s}


# ---------------------------------------------------------------- beats (word-keyed)
T = {
    "split": W("tree") + 0.1, "two": W("two"), "down": W("down"), "up": W("up"), "interesting": W("interesting"),
    "mirror": W("mirror"), "crown": W("crown"), "gravi": W("gravitropic"), "photo": W("phototropic"),
    "away": W("away"), "gravity": W("gravity"), "before": W("before"), "down2": W("down", 2),
    "darkness": W("darkness"), "resistance": W("resistance"), "pressure": W("pressure"), "dirt": W("dirt"),
    "fight": W("fight"), "deeper_e": W("deeper", end=True), "but": W("but"), "surface": W("surface"),
    "less": W("less"), "resistance2e": W("resistance", 2, end=True), "and_that": W("that"), "works_e": W("works", end=True),
    "work": W("work"), "dark": W("dark"), "nobody": W("nobody"), "heavy": W("heavy"), "grows": W("grows", 2),
    "success": W("success"), "admire": W("admire"), "light2": W("light", 2), "everybody": W("everybody"),
    "fruit": W("fruit"), "very": W("very"), "lonely": W("lonely"), "seasons": W("seasons"), "that_create": W("create"),
}

tl = []            # JS timeline lines
based = set()


def ft(sel, frm, to, at):
    fr = json.dumps(frm)
    if sel not in based:
        based.add(sel)
        tl.append(f'tl.set("{sel}", {fr}, 0);')
    tl.append(f'tl.fromTo("{sel}", {fr}, {json.dumps({**to, "immediateRender": False})}, {max(0, at):.3f});')


def tw(sel, frm, props, at):
    """fromTo with explicit start values: seek-safe in any render order"""
    if sel not in based:
        based.add(sel)
        tl.append(f'tl.set("{sel}", {json.dumps(frm)}, 0);')
    tl.append(f'tl.fromTo("{sel}", {json.dumps(frm)}, {json.dumps({**props, "immediateRender": False})}, {max(0, at):.3f});')


def to(sel, props, at):
    tl.append(f'tl.to("{sel}", {json.dumps(props)}, {max(0, at):.3f});')


def st(sel, props, at):
    tl.append(f'tl.set("{sel}", {json.dumps(props)}, {max(0, at):.3f});')


# camera path
CAM0 = cam(540, HZ)
st("#cam", CAM0, 0)
moves = [
    (T["down"] - 0.1, 0.9, cam(540, HZ + 170), "power2.inOut"),
    (T["up"] - 0.15, 0.9, cam(540, HZ - 150), "power2.inOut"),
    (T["interesting"], 1.0, cam(540, HZ), "power2.inOut"),
    (T["gravi"] - 0.4, 1.2, cam(540, HZ - 60, 0.96), "power2.inOut"),
    (T["before"] + 0.2, 2.2, cam(540, HZ + 600, 1.0), "power2.inOut"),
    (T["darkness"] - 0.6, 1.4, cam(TAP_END[0], TAP_END[1] - 260, 1.12), "power3.inOut"),
    (T["fight"], T["deeper_e"] - T["fight"] + 1.0, cam(TAP_END[0], TAP_END[1] - 120, 1.2), "sine.inOut"),
    (T["but"], T["surface"] - T["but"] + 0.25, cam(540, HZ - 260, 1.0), "power3.inOut"),
    (T["and_that"], 2.6, cam(540, HZ, 0.86), "power2.inOut"),
    (T["work"] - 0.3, 1.4, cam(540, HZ + 330, 0.95), "power2.inOut"),
    (T["grows"] - 0.2, 1.6, cam(540, HZ - 380, 0.95), "power2.inOut"),
    (T["everybody"] - 0.1, 1.2, cam(FRUIT_ZOOM[0], FRUIT_ZOOM[1] + 60, 2.3), "power3.inOut"),
    (T["very"] - 0.2, 1.6, cam(540, HZ - 60, 0.84), "power2.inOut"),
]
for at, dur, c, ease in moves:
    tl.append(f'tl.to("#cam", {{...{json.dumps(c)}, duration: {dur:.2f}, ease: "{ease}"}}, {at:.3f});')

# small shakes on the three heavy words
for key in ("resistance", "pressure", "dirt"):
    t0 = T[key]
    tl.append(f'tl.to("#shake", {{keyframes: [{{x: -14, y: 8, duration: 0.05}}, {{x: 11, y: -9, duration: 0.05}}, {{x: -6, y: 4, duration: 0.05}}, {{x: 0, y: 0, duration: 0.08}}]}}, {t0:.3f});')

# ---------------------------------------------------------------- tree growth (stroke draw)
def draw_group(items, cls, t0, t1, reverse=False):
    maxd = max(d for _, d, _ in items)
    out = []
    for i, (d, depth, w) in enumerate(items):
        el = f"{cls}{i}"
        out.append((el, d, depth, w))
        a = t0 + (t1 - t0) * depth / (maxd + 1)
        b = a + (t1 - t0) / (maxd + 1) * 1.6
        ft(f"#{el}", {"strokeDashoffset": 1}, {"strokeDashoffset": 0, "duration": round(b - a, 3), "ease": "power1.out"}, a)
    return out


# seed splits on "tree", first levels by "time?", the rest on "down" / "up"
lvl = lambda items, lo, hi: [it for it in items if lo <= it[1] <= hi]
B = draw_group(branches, "b", T["split"], T["up"] + 1.4)
R = draw_group(roots, "r", T["split"], T["down"] + 1.6)
TAPS = [(f"tp{i}", d) for i, d in enumerate(tap)]
for i, (el, d) in enumerate(TAPS):
    a = T["before"] + 1.2 + i * (T["deeper_e"] - T["before"] - 1.2) / len(TAPS)
    ft(f"#{el}", {"strokeDashoffset": 1}, {"strokeDashoffset": 0, "duration": 1.1, "ease": "sine.inOut"}, a)
DEEP = [(f"dr{i}", d, depth, w) for i, (d, depth, w) in enumerate(deep)]
for (el, d, depth, w) in DEEP:
    a = T["lonely"] - 0.6 + (depth - 3) * 0.55
    ft(f"#{el}", {"strokeDashoffset": 1}, {"strokeDashoffset": 0, "duration": 0.9, "ease": "power1.out"}, a)

# seed
ft("#seed", {"scale": 0, "autoAlpha": 0, "transformOrigin": "50% 50%"}, {"scale": 1, "autoAlpha": 1, "duration": 0.5, "ease": "back.out(2)"}, 0.15)
tw("#seed", {"scale": 1}, {"scale": 1.25, "duration": 0.18, "yoyo": True, "repeat": 1}, T["split"] - 0.3)
tw("#seed", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.6}, T["up"])

# leaves: pop in after "up"
for i, (lx, ly, r, c) in enumerate(leaves):
    ft(f"#lf{i}", {"attr": {"r": 0}}, {"attr": {"r": round(r, 1)}, "duration": 0.45, "ease": "back.out(2.2)"}, T["up"] + 0.3 + (i / len(leaves)) * 1.4)

# mirror: the root system folds up over the crown
ft("#mirror", {"autoAlpha": 0, "scaleY": 1, "svgOrigin": f"540 {HZ}"}, {"autoAlpha": 0.85, "scaleY": -1, "duration": 1.3, "ease": "power2.inOut"}, T["mirror"] - 0.2)
tw("#mirror", {"autoAlpha": 0.85}, {"autoAlpha": 0, "duration": 0.7}, T["crown"] + 1.0)
ft("#hzline", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.4}, T["mirror"] - 0.2)
tw("#hzline", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.5}, T["crown"] + 1.2)

# sun + tropism arrows
ft("#sun", {"autoAlpha": 0, "scale": 0.6, "transformOrigin": "50% 50%"}, {"autoAlpha": 1, "scale": 1, "duration": 1.2, "ease": "power2.out"}, T["gravi"] - 0.6)
tl.append(f'tl.to("#rays", {{rotation: 60, svgOrigin: "0 0", duration: {TOTAL:.2f}, ease: "none"}}, 0);')
ft("#arrUp", {"autoAlpha": 0, "y": 40}, {"autoAlpha": 1, "y": 0, "duration": 0.6, "ease": "power3.out"}, T["photo"] - 0.1)
ft("#arrDn", {"autoAlpha": 0, "y": -40}, {"autoAlpha": 1, "y": 0, "duration": 0.6, "ease": "power3.out"}, T["gravi"] - 0.1)
tw("#arrUp", {"autoAlpha": 1, "y": 0}, {"autoAlpha": 0, "duration": 0.5}, T["before"] - 0.2)
tw("#arrDn", {"autoAlpha": 1, "y": 0}, {"autoAlpha": 0, "duration": 0.5}, T["before"] - 0.2)
# roots glow when "roots grow away from the light"
ft("#rootsG", {"filter": "drop-shadow(0 0 0px rgba(242,181,68,0))"}, {"filter": "drop-shadow(0 0 14px rgba(242,181,68,.85))", "duration": 0.8}, T["away"] - 0.2)
tw("#rootsG", {"filter": "drop-shadow(0 0 14px rgba(242,181,68,.85))"}, {"filter": "drop-shadow(0 0 0px rgba(242,181,68,0))", "duration": 1.0}, T["before"])

# underground: dark vignette, heavy words, rock cracks
ft("#deepdark", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 1.4}, T["darkness"] - 0.6)
tw("#deepdark", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.9}, T["but"] + 0.2)
for key, el in (("resistance", "#hw1"), ("pressure", "#hw2"), ("dirt", "#hw3")):
    ft(el, {"autoAlpha": 0, "scale": 1.9, "filter": "blur(10px)"}, {"autoAlpha": 1, "scale": 1, "filter": "blur(0px)", "duration": 0.32, "ease": "power4.in"}, T[key] - 0.2)
tw("#heavy", {"autoAlpha": 1, "y": 0}, {"autoAlpha": 0, "y": 60, "duration": 0.6}, T["fight"] + 0.3)
for i in range(len(tip_rocks)):
    ft(f"#crack{i}", {"strokeDashoffset": 1}, {"strokeDashoffset": 0, "duration": 0.25}, T[["resistance", "pressure", "dirt", "dirt"][i]] + 0.05 + (0.15 if i == 3 else 0))

# breakthrough: light burst + warm grade
ft("#burst", {"autoAlpha": 0, "scale": 0.2}, {"autoAlpha": 1, "scale": 1.6, "duration": 0.55, "ease": "expo.out"}, T["surface"] + 0.15)
tw("#burst", {"autoAlpha": 1, "scale": 1.6}, {"autoAlpha": 0, "scale": 2.4, "duration": 1.6, "ease": "power2.out"}, T["surface"] + 0.7)
ft("#warm", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 1.2}, T["surface"] + 0.2)
tw("#warm", {"autoAlpha": 1}, {"autoAlpha": 0.55, "duration": 2.0}, T["less"] + 2.0)
tl.append(f'tl.to("#crown", {{rotation: 1.2, duration: 1.6, ease: "sine.inOut", yoyo: true, repeat: 5, svgOrigin: "540 {HZ}"}}, {T["less"]:.3f});')

# labels: roots (the dark), fruit (the light)
root_labels = [("the work in the dark", "dark", (260, HZ + 250)), ("when nobody sees you", "nobody", (790, HZ + 420)), ("when life feels heavy", "heavy", (330, HZ + 590))]
for i, (_, key, _) in enumerate(root_labels):
    ft(f"#rl{i}", {"autoAlpha": 0, "scale": 0.7}, {"autoAlpha": 1, "scale": 1, "duration": 0.45, "ease": "back.out(2)"}, T[key] - 0.15)
    tw(f"#rl{i}", {"autoAlpha": 1, "scale": 1}, {"autoAlpha": 0, "duration": 0.5}, T["grows"] - 0.3)
for i, (fx, fy, _) in enumerate(fruit_pts):
    ft(f"#fr{i}", {"scale": 0, "transformOrigin": "50% 50%"}, {"scale": 1, "duration": 0.5, "ease": "back.out(2.4)"}, T["grows"] + 0.1 + i * 0.12)
fruit_labels = [("success", "success", (fruit_pts[1][0], fruit_pts[1][1] - 70)), ("recognition", "admire", (fruit_pts[3][0], fruit_pts[3][1] - 90)), ("results", "light2", (fruit_pts[5][0], fruit_pts[5][1] - 70))]
for i, (_, key, _) in enumerate(fruit_labels):
    ft(f"#fl{i}", {"autoAlpha": 0, "y": 20}, {"autoAlpha": 1, "y": 0, "duration": 0.45, "ease": "back.out(2)"}, T[key] - 0.1)
    tw(f"#fl{i}", {"autoAlpha": 1, "y": 0}, {"autoAlpha": 0, "duration": 0.4}, T["everybody"] - 0.2)
ft(f"#fr3", {"filter": "drop-shadow(0 0 0px #F2B544)"}, {"filter": "drop-shadow(0 0 22px #F2B544)", "duration": 0.8}, T["fruit"] - 0.4)
tw(f"#fr3", {"filter": "drop-shadow(0 0 22px #F2B544)"}, {"filter": "drop-shadow(0 0 0px #F2B544)", "duration": 0.8}, T["very"])

# seasons: winter -> spring -> summer -> autumn -> summer
s0 = T["lonely"] - 0.1
for sel, v in (("#leaves", 1), ("#fruits", 1), ("#skyW", 0), ("#snow", 1), ("#seasonTag", 0)):
    st(sel, {"autoAlpha": v}, 0); based.add(sel)
seg = max(0.55, (T["that_create"] - s0) / 4)
tw("#leaves", {"autoAlpha": 1}, {"autoAlpha": 0.05, "duration": 0.35}, s0)
tw("#fruits", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.3}, s0)
tw("#skyW", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.35}, s0)
for i, (sx, sy, r, dl) in enumerate(snow):
    ft(f"#sn{i}", {"y": 0}, {"y": 1250 + rng.uniform(0, 300), "duration": seg * 1.4, "ease": "none"}, s0 + dl * seg)
tw("#snow", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.3}, s0 + seg * 1.1)
tw("#skyW", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.35}, s0 + seg)
ft("#blossom", {"autoAlpha": 0, "scale": 0.4, "transformOrigin": "50% 50%"}, {"autoAlpha": 1, "scale": 1, "duration": 0.35, "ease": "back.out(2)"}, s0 + seg)
tw("#leaves", {"autoAlpha": 0.05}, {"autoAlpha": 1, "duration": 0.35}, s0 + seg * 1.2)
tw("#blossom", {"autoAlpha": 1, "scale": 1}, {"autoAlpha": 0, "duration": 0.3}, s0 + seg * 2)
tw("#fruits", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.3}, s0 + seg * 2)
ft("#leaves", {"filter": "hue-rotate(0deg) saturate(1)"}, {"filter": "hue-rotate(-55deg) saturate(1.4)", "duration": 0.4}, s0 + seg * 3)
for i, (fx, fy, r) in enumerate(fall):
    ft(f"#fa{i}", {"x": 0, "y": 0, "autoAlpha": 1, "rotation": 0, "transformOrigin": "50% 50%"}, {"x": rng.uniform(-120, 120), "y": HZ - fy + rng.uniform(-10, 20), "rotation": rng.uniform(-200, 200), "autoAlpha": 1, "duration": seg * 1.3, "ease": "power1.in"}, s0 + seg * 3 + i * 0.02)
st("#falling", {"autoAlpha": 0}, 0); based.add("#falling")
st("#falling", {"autoAlpha": 1}, s0 + seg * 3)
tw("#falling", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.4}, s0 + seg * 4.4)
tw("#leaves", {"filter": "hue-rotate(-55deg) saturate(1.4)"}, {"filter": "hue-rotate(0deg) saturate(1)", "duration": 0.6}, s0 + seg * 4.2)
ft("#seasonTag", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.2}, s0)
for i, name in enumerate(["winter", "spring", "summer", "autumn"]):
    st("#seasonTag", {"textContent": name}, s0 + seg * i)
tw("#seasonTag", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.3}, s0 + seg * 4)

# ---------------------------------------------------------------- hero serif lines
heroes = [
    ("h1", "a tree grows in<br><em>two directions</em>", W("a"), T["down"] - 0.2, "top"),
    ("h4", "the roots <em>mirror</em><br>the crown", T["mirror"] - 0.3, T["crown"] + 1.3, "top"),
    ("h5", "before it can rise,<br>it goes <em>down</em>", T["before"], T["darkness"] - 0.5, "top"),
    ("h6", "<em>less</em> resistance", T["less"] - 0.1, T["resistance2e"] + 1.2, "top"),
    ("h7", "everybody wants<br><em>the fruit</em>", T["everybody"], T["very"] - 0.2, "top"),
    ("h8", "very few go through<br><em>the lonely seasons</em><br>that create it", T["very"], TOTAL, "top"),
]
for hid, _, a, b, _ in heroes:
    ft(f"#{hid}", {"autoAlpha": 0, "y": 30, "filter": "blur(8px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.6, "ease": "power3.out"}, a)
    if b < TOTAL:
        tw(f"#{hid}", {"autoAlpha": 1, "y": 0, "filter": "blur(0px)"}, {"autoAlpha": 0, "y": -20, "filter": "blur(6px)", "duration": 0.45}, b)

# ---------------------------------------------------------------- captions
# Editorial reveal: each word rises out of a blur exactly when it is spoken; lowercase
# sans, key words in the gold serif italic of the headlines. No box: a soft dark glow
# keeps them readable. Block sits in the lower third, bottom edge at y=1490 (above the
# Reels UI), over the dark soil that is always at the bottom of the frame.
KEYWORDS = {"two", "directions", "mirror", "crown", "gravitropic", "phototropic", "light", "gravity", "down", "darkness",
            "deeper", "surface", "less", "beautiful", "dark", "nobody", "heavy", "success", "fruit", "lonely", "seasons", "up"}
groups, cur = [], []
for i, w in enumerate(words):
    cur.append(w)
    nxt = words[i + 1] if i + 1 < len(words) else None
    end_sent = w["w"][-1] in ".?:" or w["w"].endswith("...")
    if len(cur) >= 5 or end_sent or (w["w"][-1] == "," and len(cur) >= 2) or (nxt and nxt["s"] - w["e"] > 0.55 and len(cur) >= 3):
        groups.append(cur); cur = []
if cur: groups.append(cur)
# no lonely one-word captions: fold them into a neighbour
merged = []
for g in groups:
    ends = lambda grp: grp[-1]["w"][-1] in ".?:" or grp[-1]["w"].endswith("...")
    if merged and not ends(merged[-1]) and (len(g) == 1 or len(merged[-1]) == 1) and len(merged[-1]) + len(g) <= 6:
        merged[-1] = merged[-1] + g
    else:
        merged.append(g)
groups = merged
hide = [(T["resistance"] - 0.25, W("dirt", end=True) + 0.3), (T["everybody"] - 0.2, TOTAL)]
cap_html = []
for gi, g in enumerate(groups):
    a = g[0]["s"] - 0.06
    b = groups[gi + 1][0]["s"] - 0.08 if gi + 1 < len(groups) else g[-1]["e"] + 0.7
    b = min(b, g[-1]["e"] + 1.1)
    if any(h0 <= a < h1 for h0, h1 in hide):
        continue
    spans = []
    for k, w in enumerate(g):
        txt = w["w"].lower().rstrip(".,:?").replace("...", "")
        kw = norm(w["w"]) in KEYWORDS
        spans.append(f'<span id="cw{gi}_{k}" class="{"kw" if kw else ""}">{txt}</span>')
    cap_html.append(f'<div id="cg{gi}" class="cap">{" ".join(spans)}</div>')
    st(f"#cg{gi}", {"autoAlpha": 0}, 0); based.add(f"#cg{gi}")
    st(f"#cg{gi}", {"autoAlpha": 1, "y": 0, "filter": "blur(0px)"}, a)
    tw(f"#cg{gi}", {"autoAlpha": 1, "y": 0, "filter": "blur(0px)"}, {"autoAlpha": 0, "y": -18, "filter": "blur(6px)", "duration": 0.22, "ease": "power2.in"}, b - 0.22)
    for k, w in enumerate(g):
        ft(f"#cw{gi}_{k}", {"autoAlpha": 0, "y": 22, "filter": "blur(10px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.3, "ease": "power3.out"}, w["s"] - 0.05)

# ---------------------------------------------------------------- audio
def peakvol(db):
    return round(10 ** (db / 20), 3)


sfx = [
    ("whoosh-1", T["split"] - 0.2, -20), ("whoosh-2", T["down"] - 0.15, -22), ("whoosh-1", T["up"] - 0.2, -22),
    ("riser-1", T["mirror"] - 0.9, -24), ("whoosh-cine", T["before"] + 0.2, -18),
    ("cinematic-deep-boom", T["resistance"] - 0.05, -12), ("impact-1", T["pressure"] - 0.05, -14), ("impact-2", T["dirt"] - 0.05, -13),
    ("cinematic-rumble-riser", T["surface"] - 2.4, -16), ("cinematic-cine-hit", T["surface"] + 0.1, -13),
    ("cinematic-drone-swell", T["grows"] - 1.0, -22), ("whoosh-cine", T["everybody"] - 0.15, -18),
    ("cinematic-drone-swell", T["lonely"] - 1.2, -20),
]
dur = {"whoosh-1": .9, "whoosh-2": .9, "riser-1": 1.7, "whoosh-cine": .31, "cinematic-deep-boom": 2.5, "impact-1": 1.6,
       "impact-2": 1.2, "cinematic-rumble-riser": 3.0, "cinematic-cine-hit": 2.0, "cinematic-drone-swell": 4.0}
audio = [f'<audio id="vo" src="assets/voice.m4a" data-start="0" data-duration="{VO_END + 0.4:.3f}" data-track-index="10" data-volume="1"></audio>']
for i, (sid, at, db) in enumerate(sfx):
    audio.append(f'<audio id="sfx{i}" src="assets/sfx/{sid}.wav" data-start="{max(0, at):.3f}" data-duration="{dur[sid]}" data-track-index="{14 + i % 4}" data-volume="{peakvol(db)}"></audio>')
# music bed: gentle under the voice, swells at the breakthrough and the end
bed_hi, bed_lo = 0.34, 0.2
pts = [(0, 0), (1.2, bed_lo), (T["surface"] - 0.5, bed_lo), (T["surface"] + 0.4, bed_hi), (T["and_that"] + 1.0, bed_lo),
       (T["lonely"] - 0.8, bed_lo), (VO_END + 0.2, bed_hi), (TOTAL - 1.2, bed_hi), (TOTAL, 0)]
lane = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": [{"t": round(t, 3), "v": v} for t, v in pts]}]})
audio.append(f"<audio id=\"bed\" src=\"assets/music/bed.mp3\" data-start=\"0\" data-duration=\"{TOTAL}\" data-media-start=\"0\" data-track-index=\"20\" data-automation='{lane}'></audio>")

# ---------------------------------------------------------------- SVG
def path(el, d, w, col, cls=""):
    return f'<path id="{el}" class="{cls}" d="{d}" pathLength="1" stroke="{col}" stroke-width="{w:.1f}" fill="none" stroke-linecap="round" stroke-dasharray="1 1" stroke-dashoffset="1"/>'


bark, gold = "#3B2A20", "#C9A15B"
svg_branches = "".join(path(el, d, w, bark) for el, d, depth, w in B)
svg_roots = "".join(path(el, d, w * 0.9, gold) for el, d, depth, w in R)
svg_tap = "".join(path(el, d, 7, gold) for el, d in TAPS)
svg_deep = "".join(path(el, d, w * 0.8, "#B08A48") for el, d, depth, w in DEEP)
svg_leaves = "".join(f'<circle id="lf{i}" cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{c}" style="transform-box:fill-box;transform-origin:center"/>' for i, (x, y, r, c) in enumerate(leaves))
svg_fruits = "".join(f'<g id="fr{i}" style="transform-box:fill-box;transform-origin:center"><circle cx="{x:.1f}" cy="{y + 22:.1f}" r="17" fill="#C0392B"/><circle cx="{x - 5:.1f}" cy="{y + 16:.1f}" r="5" fill="#E8705F"/><path d="M{x:.1f},{y + 5:.1f} q4,-9 10,-10" stroke="#3B2A20" stroke-width="3" fill="none"/></g>' for i, (x, y, d) in enumerate(fruit_pts))
svg_blossom = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="#F4B6C2"/><circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#F2B544"/>' for x, y in blossoms)
svg_rocks = "".join(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{a:.1f}" ry="{b:.1f}" transform="rotate({r:.0f} {x:.1f} {y:.1f})" fill="{c}"/>' for x, y, a, b, r, c in rocks)
svg_tiprocks = ""
for i, (x, y, a, b, r) in enumerate(tip_rocks):
    svg_tiprocks += f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{a}" ry="{b}" transform="rotate({r} {x:.1f} {y:.1f})" fill="#4A3A2E" stroke="#241A13" stroke-width="4"/>'
    svg_tiprocks += f'<path id="crack{i}" d="M{x - a * 0.6:.1f},{y - 10:.1f} l{a * 0.3:.1f},{b * 0.35:.1f} l{a * 0.25:.1f},{-b * 0.5:.1f} l{a * 0.35:.1f},{b * 0.4:.1f}" pathLength="1" stroke="#E7C27A" stroke-width="4" fill="none" stroke-dasharray="1 1" stroke-dashoffset="1"/>'
svg_pebbles = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#5A4636" opacity=".55"/>' for x, y, r in pebbles)
svg_snow = "".join(f'<circle id="sn{i}" cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#fff" opacity=".9"/>' for i, (x, y, r, d) in enumerate(snow))
svg_fall = "".join(f'<ellipse id="fa{i}" cx="{x:.0f}" cy="{y:.0f}" rx="{r:.0f}" ry="{r * 0.6:.0f}" fill="#D9822B" style="transform-box:fill-box;transform-origin:center"/>' for i, (x, y, r) in enumerate(fall))
rl_html = "".join(f'<div id="rl{i}" class="tag troot" style="left:{x}px;top:{y}px">{t}</div>' for i, (t, _, (x, y)) in enumerate(root_labels))
fl_html = "".join(f'<div id="fl{i}" class="tag tfruit" style="left:{x}px;top:{y}px">{t}</div>' for i, (t, _, (x, y)) in enumerate(fruit_labels))
hero_html = "".join(f'<div id="{hid}" class="hero {pos}">{txt}</div>' for hid, txt, a, b, pos in heroes)
rays = "".join(f'<rect x="-6" y="-520" width="12" height="380" rx="6" fill="#F2B544" opacity=".22" transform="rotate({i * 30})"/>' for i in range(12))

html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
@font-face {{ font-family: "Playfair Display Italic"; src: url(assets/fonts/playfair-display-italic-latin.woff2) format("woff2"); font-weight: 100 900; }}
@font-face {{ font-family: "Playfair Display"; src: url(assets/fonts/playfair-display-latin.woff2) format("woff2"); font-weight: 100 900; }}
@font-face {{ font-family: Geist; src: url(assets/fonts/geist-latin.woff2) format("woff2"); font-weight: 100 900; }}
@font-face {{ font-family: Montserrat; src: url(assets/fonts/montserrat-latin.woff2) format("woff2"); font-weight: 100 900; }}
html, body {{ margin: 0; background: #120D0A; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #120D0A; }}
#shake, #cam {{ position: absolute; left: 0; top: 0; width: 1080px; height: {WORLD_H}px; transform-origin: 0 0; }}
.sky {{ position: absolute; left: -600px; right: -600px; top: -1400px; height: {HZ + 1400}px; background: linear-gradient(180deg, #E9D9BD 0%, #F4EAD8 55%, #F7E3B8 100%); }}
#skyW {{ position: absolute; left: -600px; right: -600px; top: -1400px; height: {HZ + 1400}px; background: linear-gradient(180deg, #B9C3C9, #DDE3E6); opacity: 0; }}
.soil {{ position: absolute; left: -600px; right: -600px; top: {HZ}px; height: {WORLD_H - HZ + 1200}px; background: linear-gradient(180deg, #3A2B20 0%, #2A1F18 18%, #1B1410 60%, #100B08 100%); }}
svg.world {{ position: absolute; left: 0; top: 0; overflow: visible; }}
#warm {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 30%, rgba(247,190,90,.45), rgba(247,190,90,0) 60%); opacity: 0; pointer-events: none; }}
#deepdark {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 55%, rgba(0,0,0,0) 20%, rgba(0,0,0,.78) 75%); opacity: 0; }}
#grain {{ position: absolute; inset: 0; background: url(assets/grain.png); background-size: 480px; opacity: .07; mix-blend-mode: overlay; pointer-events: none; }}
#vig {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,.35) 100%); pointer-events: none; }}
#burst {{ position: absolute; left: 540px; top: 960px; width: 900px; height: 900px; margin: -450px 0 0 -450px; border-radius: 50%; background: radial-gradient(circle, rgba(255,245,210,1) 0%, rgba(255,214,120,.7) 30%, rgba(255,214,120,0) 70%); opacity: 0; }}
.hero {{ position: absolute; left: 50%; transform: translateX(-50%); width: max-content; max-width: 940px; padding: 18px 44px 28px; border-radius: 36px; background: rgba(244,234,216,.86); box-shadow: 0 12px 50px rgba(42,31,24,.18); text-align: center; font-family: "Playfair Display"; font-weight: 500; font-size: 84px; line-height: 1.08; color: #2A1F18; opacity: 0; letter-spacing: -1px; }}
.hero em {{ font-family: "Playfair Display Italic"; font-style: normal; color: #8A5A1E; }}
.hero.top {{ top: 250px; }}
.hero.low {{ top: 1180px; color: #F4EAD8; }}
.hero.low em {{ color: #E7C27A; }}
#h5 {{ color: #F4EAD8; background: rgba(16,11,8,.55); }}
#h5 em, #h8 em, #h7 em {{ color: #E7C27A; }}
#h7, #h8 {{ color: #FFF8EC; background: rgba(26,19,14,.72); }}
#heavy {{ position: absolute; left: 0; right: 0; top: 560px; text-align: center; }}
#heavy div {{ font-family: Montserrat; font-weight: 900; font-size: 128px; letter-spacing: 6px; color: #F4EAD8; line-height: 1.15; opacity: 0; text-shadow: 0 8px 40px rgba(0,0,0,.8); }}
#heavy div:nth-child(2) {{ color: #E7C27A; }}
.tag {{ position: absolute; transform: translate(-50%, -50%); font-family: "Playfair Display Italic"; font-size: 46px; white-space: nowrap; padding: 6px 26px 12px; border-radius: 40px; opacity: 0; }}
.troot {{ color: #F7DFA6; background: rgba(16,11,8,.72); border: 2px solid rgba(201,161,91,.7); }}
.tfruit {{ color: #FFF8EC; background: #C0392B; box-shadow: 0 10px 30px rgba(0,0,0,.25); }}
.arr {{ position: absolute; font-family: Montserrat; font-weight: 800; font-size: 34px; letter-spacing: 3px; opacity: 0; text-align: center; }}
.arr b {{ display: block; font-family: "Playfair Display Italic"; font-weight: 400; font-size: 44px; letter-spacing: 0; text-transform: none; }}
#arrUp {{ left: 620px; top: 560px; color: #8A5A1E; }}
#arrDn {{ left: 80px; top: 1500px; color: #E7C27A; }}
#seasonTag {{ position: absolute; left: 0; right: 0; top: 1470px; text-align: center; font-family: Montserrat; font-weight: 800; font-size: 40px; letter-spacing: 12px; text-transform: uppercase; color: #E7C27A; opacity: 0; }}
.cap {{ position: absolute; left: 60px; right: 60px; bottom: 430px; text-align: center; font-family: Geist; font-weight: 600; font-size: 60px; line-height: 1.12; letter-spacing: -1.2px; color: #FFF8EC; opacity: 0; text-shadow: 0 2px 3px rgba(0,0,0,.5), 0 0 18px rgba(12,8,5,.75), 0 0 46px rgba(12,8,5,.5); }}
.cap span {{ display: inline-block; opacity: 0; }}
.cap .kw {{ font-family: "Playfair Display Italic"; font-weight: 400; font-size: 70px; letter-spacing: -0.5px; color: #F2C66B; }}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{TOTAL}" data-fps="30">
 <div id="shake"><div id="cam">
  <div class="sky"></div><div id="skyW"></div><div class="soil"></div>
  <svg class="world" width="1080" height="{WORLD_H}" viewBox="0 0 1080 {WORLD_H}">
   <g id="sun" style="transform-box:fill-box;transform-origin:center"><g transform="translate(830 {HZ - 900})"><g id="rays">{rays}</g><circle r="120" fill="#F2B544"/><circle r="160" fill="#F2B544" opacity=".18"/></g></g>
   {svg_pebbles}{svg_rocks}
   <line id="hzline" x1="-200" y1="{HZ}" x2="1280" y2="{HZ}" stroke="#8A5A1E" stroke-width="3" stroke-dasharray="14 12" opacity="0"/>
   <g id="rootsG">{svg_roots}{svg_tap}{svg_deep}</g>
   <use id="mirror" href="#rootsG" opacity="0" style="filter: brightness(.5) saturate(1.4)"/>
   {svg_tiprocks}
   <g id="crown">{svg_branches}<g id="leaves">{svg_leaves}</g><g id="blossom" style="transform-box:fill-box;transform-origin:center" opacity="0">{svg_blossom}</g><g id="fruits">{svg_fruits}</g></g>
   <ellipse id="seed" cx="540" cy="{HZ}" rx="26" ry="18" fill="#8A5A1E" style="transform-box:fill-box;transform-origin:center"/>
   <line x1="-600" y1="{HZ}" x2="1680" y2="{HZ}" stroke="#5B4330" stroke-width="5"/>
   <g id="falling">{svg_fall}</g>
  </svg>
  {rl_html}{fl_html}
  <div id="arrUp" class="arr">↑ PHOTOTROPIC<b>toward the light</b></div>
  <div id="arrDn" class="arr">↓ GRAVITROPIC<b>toward gravity</b></div>
 </div></div>
 <svg id="snow" width="1080" height="1920" style="position:absolute;left:0;top:0">{svg_snow}</svg>
 <div id="warm"></div><div id="deepdark"></div><div id="burst"></div>
 <div id="heavy"><div id="hw1">RESISTANCE</div><div id="hw2">PRESSURE</div><div id="hw3">DIRT</div></div>
 {hero_html}
 <div id="seasonTag">winter</div>
 {''.join(cap_html)}
 <div id="grain"></div><div id="vig"></div>
 {''.join(audio)}
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
  {chr(10).join('  ' + l for l in tl)}
  window.__timelines["main"] = tl;
</script>
</body></html>
"""
open("index.html", "w").write(html)
print(f"index.html: {TOTAL}s, {len(B)} branches, {len(R)} roots, {len(leaves)} leaves, {len(fruit_pts)} fruits, {len(groups)} caption groups, {len(tl)} timeline lines")
