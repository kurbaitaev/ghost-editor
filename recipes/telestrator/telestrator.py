"""Telestrator: a TV football-analysis segment over a talking head. The speaker's footage is the match: it plays live,
freezes (a still of the exact frame under the speaker's own cutout), and gets drawn on - rings under the hand, marker
arrows, red space zones behind the speaker, label cards - always in the space around the face, never on it. Between face
shots the reel wipes (a yellow slanted band) to dark tactics boards where the line's object is played, frozen, rewound
and drawn on. A studio show's packaging sits on every frame: corner bug with three modes, a source clock, a matchup bar,
a subtitle bar.
Ported from the MIT style "Sports Telestrator" of lemo-opuscar (https://github.com/lemomo-ai/lemo-opuscar,
styles/telestrator; see CREDITS.txt): grammar, colour roles and drawing rules adapted, no media copied.

    import sys; sys.path.insert(0, "<skill>/recipes/telestrator"); from telestrator import *
    S = Show("$P", dur=30.0, title="Coffee Telestrator")                # words: $P/build/words.cut.json (edit s)
    S.mode(0, "live"); S.clock(0, "play")                                # packaging state changes
    F = S.freeze("F1", 3.867, 5.20, plate="alt", matte="build/freeze/alt_fz-matte.webm", face=(330, 540, 760, 1040))
    F.spot(640, 1200, 420, 330); F.ring(640, 1330, 150, "yellow", 3.95)  # who
    F.marker([(640, 1300), (820, 1180), (900, 1000)], "yellow", 4.2, 0.4, dashed=True)   # what
    F.label(600, 1340, "THE CUP", "ALWAYS IN HAND", "yellow", 4.45)       # the finding
    S.close(F)
    B = S.board("B1", 5.20, 8.40); B.html(...); B.stamp(...); S.close(B)  # a tactics board (own scenes via B.svg / B.html)
    A, Bw = S.split("SP", 22.60, 24.633, 26.84, a=("alt", 270, "<alt matte>"), b=("tight", 330, "<tight matte>"))
    S.wipe(5.20); S.flip(29.66); S.sfx("shutter-1", 3.867, 0.5); S.build()

Calls (all times in edit seconds; S.at("word") is a word's onset, S.n(t) its frame):
  Show(project, dur, title, plates={"alt": "assets/alt.mp4", ...}, fixes={"cafeine": "caffeine"})
  S.mode(t, "live" | "analysis" | "replay")      corner bug mode line (● LIVE red / ANALYSIS yellow / REPLAY cyan)
  S.clock(t, "play" | "pause" | "hide" | ("rewind", from_t, to_t, dur))   the source clock (true reel time + frame)
  S.freeze(name, t0, t1, plate, matte, face=box, at=None)   -> Scene over a still of the plate frame at `at` (default t0)
  S.board(name, t0, t1, flash_at=None)            -> Scene: dark board #0C1411 with the 60 px chalk grid
  S.live_scene(name, t0, t1)                      -> Scene over the live plate (drawings that move with the play)
  S.split(name, t0, t_freeze, t1, a=(plate, slice_x, matte), b=...)   -> (Scene A, Scene B): dual-angle split + freeze
  S.wipe(t)  S.flip(t)  S.subs(breaks=None)  S.sfx(name, t, vol, dur=None)  S.close(scene)  S.build()
Scene primitives (screen px; each returns its element id): ring, marker, zone, spot, label, stamp, chalk (SVG markup on
the front layer), html (HTML on the front layer), back_svg; motion helpers on S: tset, tween, flicker.
Faces: every Scene on the speaker's footage carries the face boxes of its plate frame; ring / marker / zone / label raise
FaceError when their box enters a face box (zones and spots are behind the cutout, so they are checked only for labels).

Needs in $P: the plates (assets/*.mp4, 1080x1920, the framing switches already in the cut), a matte per freeze frame
(scripts/matte.py --ranges around each freeze; only the frozen frames are needed), assets/voice.wav, build/words.cut.json.
Fonts and SFX are copied from the skill. Writes index.html, build/beats.json, build/coverage.txt, assets/freeze/*.
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
LP = HOUSE["layout_px"]
PK = HOUSE["packaging"]
FPS = HOUSE["motion"]["fps"]
F1 = 1 / FPS
FLOOR = TY["floor_px"]
SFX_LEN = HOUSE["sound"]["sfx_len_s"]
ROLE = {"yellow": PAL["yellow"], "cyan": PAL["cyan"], "red": PAL["red"], "chalk": PAL["chalk"]}


class FaceError(ValueError):
    pass


def fr(t):
    return round(round(t * FPS) / FPS, 4)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def col(c):
    return ROLE.get(c, c)


def rgba(c, a):
    c = col(c)
    return f"rgba({int(c[1:3], 16)},{int(c[3:5], 16)},{int(c[5:7], 16)},{a})"


# ---------------------------------------------------------------- fonts + measuring (PIL reads the woff2 directly)
_fc = {}


def _font(fam, sub, size):
    from PIL import ImageFont
    f = TY["families"][fam]
    k = (fam, sub, size)
    if k not in _fc:
        ft = ImageFont.truetype(f"{SKILL}/templates/fonts/{f[3]}-{sub}.woff2", size)
        try:
            ft.set_variation_by_axes([f[1]])
        except Exception:
            pass
        _fc[k] = ft
    return _fc[k]


def width(s, fam, size, spacing=0.0):
    """advance width of s in px (per char from the subset that has it), incl. letter-spacing"""
    w = 0.0
    for c in s:
        sub = "cyrillic" if 0x0400 <= ord(c) <= 0x04FF else "latin"
        w += _font(fam, sub, 200).getlength(c) * size / 200
    return w + spacing * max(len(s) - 1, 0)


def fit(s, fam, size, maxw, spacing=0.0):
    """the largest size <= size that fits maxw; raises when it would go under the 48 px floor"""
    while width(s, fam, size, spacing) > maxw:
        size -= 1
        if size < FLOOR:
            raise ValueError(f"{s!r} does not fit {maxw} px at {FLOOR} px: shorten it")
    return size


def ensure_fonts(P):
    os.makedirs(f"{P}/assets/fonts", exist_ok=True)
    for _, stem, _, _ in TY["font_faces"]:
        for sub in ("cyrillic", "latin"):
            dst = f"{P}/assets/fonts/{stem}-{sub}.woff2"
            if not os.path.exists(dst):
                shutil.copy(f"{SKILL}/templates/fonts/{stem}-{sub}.woff2", dst)


def ensure_sfx(P, name):
    os.makedirs(f"{P}/assets/sfx", exist_ok=True)
    dst = f"{P}/assets/sfx/{name}.wav"
    if not os.path.exists(dst):
        shutil.copy(f"{SKILL}/library/sfx/{name}.wav", dst)
    return dst


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def freeze_still(P, plate, matte, n, stem):
    """assets/freeze/<stem>.jpg (the exact plate frame n) + <stem>-cut.png (that frame with the speaker's matte as alpha).
    Decoded with accurate_rnd + full_chroma_int so the still matches the live frame's levels."""
    import numpy as np
    from PIL import Image
    out = f"{P}/assets/freeze"
    os.makedirs(out, exist_ok=True)
    bg, cut = f"{out}/{stem}.jpg", f"{out}/{stem}-cut.png"
    if os.path.exists(bg) and os.path.exists(cut):
        return f"assets/freeze/{stem}.jpg", f"assets/freeze/{stem}-cut.png"
    sel = f"select=eq(n\\,{n})"
    rgb = subprocess.run(["ffmpeg", "-v", "error", "-i", f"{P}/{plate}", "-vf",
                          f"{sel},scale=1080:1920:flags=bicubic+accurate_rnd+full_chroma_int,format=rgb24",
                          "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True).stdout
    al = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", f"{P}/{matte}", "-vf",
                         f"{sel},alphaextract", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                        capture_output=True).stdout
    if len(rgb) != 1080 * 1920 * 3 or len(al) != 1080 * 1920:
        raise RuntimeError(f"freeze still {stem}: frame {n} not decoded from {plate} / {matte}")
    a = np.frombuffer(al, np.uint8).reshape(1920, 1080)
    if (a > 128).mean() < 0.05:
        raise RuntimeError(f"freeze still {stem}: the matte is empty at frame {n} (matte.py --ranges must cover it)")
    im = np.frombuffer(rgb, np.uint8).reshape(1920, 1080, 3)
    Image.fromarray(im).save(bg, quality=95)
    Image.fromarray(np.dstack([im, a])).save(cut)
    return f"assets/freeze/{stem}.jpg", f"assets/freeze/{stem}-cut.png"


# ---------------------------------------------------------------- geometry for marker lines
def bez(pts, k=28):
    """control points -> samples: 2 = straight, 3 = quadratic, 4 = cubic bezier"""
    if len(pts) == 2:
        (x0, y0), (x1, y1) = pts
        return [(x0 + (x1 - x0) * i / k, y0 + (y1 - y0) * i / k) for i in range(k + 1)]
    out = []
    for i in range(k + 1):
        u = i / k
        p = list(pts)
        while len(p) > 1:
            p = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u) for a, b in zip(p, p[1:])]
        out.append(p[0])
    return out


def wobble(samples, seed, amp=2.0):
    rnd = random.Random(seed)
    return [(x + (rnd.uniform(-amp, amp) if 0 < i < len(samples) - 1 else 0),
             y + (rnd.uniform(-amp, amp) if 0 < i < len(samples) - 1 else 0)) for i, (x, y) in enumerate(samples)]


def plen(s):
    return sum(math.dist(a, b) for a, b in zip(s, s[1:]))


def dpath(s):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in s)


def ellipse_pts(cx, cy, rx, ry, k=64):
    """clockwise on screen from the left"""
    return [(cx - rx * math.cos(2 * math.pi * i / k), cy - ry * math.sin(2 * math.pi * i / k)) for i in range(k + 1)]


def overlaps(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


# ---------------------------------------------------------------- a scene: one freeze, board or live overlay
class Scene:
    def __init__(self, show, name, t0, t1, faces=(), clip=None):
        self.S, self.name, self.t0, self.t1 = show, name, t0, t1
        self.faces = list(faces)              # face boxes (x0, y0, x1, y1) in screen px
        self.clip = clip                      # (x0, x1) window for split scenes
        self.back, self.under, self.front, self.top = [], [], [], []
        self.keys = [t0 + 0.05]

    def _check(self, box, what):
        if self.clip and (box[0] < self.clip[0] - 2 or box[2] > self.clip[1] + 2):
            raise FaceError(f"{self.name}: {what} {box} leaves its window {self.clip}")
        for f in self.faces:
            if overlaps(box, f):
                raise FaceError(f"{self.name}: {what} {tuple(round(v) for v in box)} enters the face box {f}")

    def _id(self, p):
        return self.S.nid(f"{self.name.lower()}_{p}")

    # ---- the drawing grammar
    def ring(self, cx, cy, r, c, t, until=None, back=False):
        """perspective ellipse (ry = 0.36 r) drawn clockwise in 0.3 s with a pop; outer dashed ring creeping at 60 px/s"""
        S, rid = self.S, self._id("ring")
        ry = r * 0.36
        self._check((cx - r * 1.22, cy - ry * 1.22, cx + r * 1.22, cy + ry * 1.22), "ring")
        pts = ellipse_pts(cx, cy, r, ry)
        L = plen(pts)
        cc = col(c)
        tgt = self.back if back else self.front
        tgt.append(f'<g id="{rid}" opacity="0">'
                   f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{ry:.1f}" fill="{rgba(c, .16)}"/>'
                   f'<ellipse id="{rid}_o" cx="{cx}" cy="{cy}" rx="{r*1.22:.1f}" ry="{ry*1.22:.1f}" fill="none" stroke="{cc}" '
                   f'stroke-width="3" stroke-dasharray="18 12" opacity=".8"/>'
                   f'<path id="{rid}_a" d="{dpath(pts)}" fill="none" stroke="rgba(0,0,0,.55)" stroke-width="13" '
                   f'stroke-dasharray="{L:.1f}" stroke-dashoffset="{L:.1f}"/>'
                   f'<g style="filter:drop-shadow(0 0 9px {cc})"><path id="{rid}_b" d="{dpath(pts)}" fill="none" stroke="{cc}" '
                   f'stroke-width="7" stroke-dasharray="{L:.1f}" stroke-dashoffset="{L:.1f}"/></g>'
                   f'<path id="{rid}_c" d="{dpath(pts)}" fill="none" stroke="rgba(255,255,255,.75)" stroke-width="2" '
                   f'stroke-dasharray="{L:.1f}" stroke-dashoffset="{L:.1f}"/></g>')
        S.tset(f"#{rid}", {"opacity": 1}, t)
        if t <= self.S.t_start + 1e-6:      # on the first frame: already drawn (a hook that reads on frame 0)
            for p in "abc":
                S.tset(f"#{rid}_{p}", {"strokeDashoffset": 0}, t)
        else:
            S.JS.append(f"gsap.set('#{rid}', {{svgOrigin: '{cx} {cy}'}});")
            S.tween(f"#{rid}", {"scale": 0.6}, {"scale": 1, "ease": "back.out(2)", "duration": 0.25}, t)
            for p in "abc":
                S.tween(f"#{rid}_{p}", {"strokeDashoffset": L}, {"strokeDashoffset": 0, "ease": "power2.out", "duration": 0.3}, t)
        end = until or self.t1
        S.tween(f"#{rid}_o", {"strokeDashoffset": 0}, {"strokeDashoffset": -60 * (end - t), "ease": "none", "duration": end - t}, t)
        self.keys.append(t + 0.35)
        return rid

    def marker(self, pts, c, t, dur=0.4, dashed=False, arrow=True, w=7, seed=None):
        """a marker line along control points (2-4); solid = what happened, dashed = intended / future path"""
        S, mid = self.S, self._id("mk")
        s = wobble(bez(pts), seed if seed is not None else len(S.JS))
        for x, y in s:                        # every sample (a curve's bounding box would be too coarse)
            self._check((x - w - 3, y - w - 3, x + w + 3, y + w + 3), "marker")
        cc = col(c)
        L = plen(s)
        out = [f'<g id="{mid}" opacity="0">']
        S.tset(f"#{mid}", {"opacity": 1}, t)
        if not dashed:
            for sub, stroke, sw in (("a", "rgba(0,0,0,.55)", w + 6), ("b", cc, w), ("c", "rgba(255,255,255,.7)", w * 0.28)):
                g0, g1 = (f'<g style="filter:drop-shadow(0 0 9px {cc})">', "</g>") if sub == "b" else ("", "")
                out.append(f'{g0}<path id="{mid}_{sub}" d="{dpath(s)}" fill="none" stroke="{stroke}" stroke-width="{sw:.1f}" '
                           f'stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{L:.1f}" stroke-dashoffset="{L:.1f}"/>{g1}')
                S.tween(f"#{mid}_{sub}", {"strokeDashoffset": L}, {"strokeDashoffset": 0, "ease": "power1.inOut", "duration": dur}, t)
        else:
            # dashes 26 / gap 16, each its own short stroke, revealed in order along the line
            acc, seg, segs, on = 0.0, [s[0]], [], True
            dash, gap = 26.0, 16.0
            for a, b in zip(s, s[1:]):
                d = math.dist(a, b)
                pos = 0.0
                while pos < d:
                    lim = dash if on else gap
                    step = min(lim - acc, d - pos)
                    pos += step
                    acc += step
                    q = (a[0] + (b[0] - a[0]) * pos / d, a[1] + (b[1] - a[1]) * pos / d)
                    if on:
                        seg.append(q)
                    if acc >= lim - 1e-6:
                        if on:
                            segs.append(seg)
                        seg, acc, on = [q], 0.0, not on
            if on and len(seg) > 1:
                segs.append(seg)
            done = 0.0
            for i, g in enumerate(segs):
                did = f"{mid}_d{i}"
                out.append(f'<g id="{did}" opacity="0"><path d="{dpath(g)}" fill="none" stroke="rgba(0,0,0,.55)" stroke-width="{w+6}" stroke-linecap="round"/>'
                           f'<path d="{dpath(g)}" fill="none" stroke="{cc}" stroke-width="{w}" stroke-linecap="round" style="filter:drop-shadow(0 0 7px {cc})"/></g>')
                S.tset(f"#{did}", {"opacity": 1}, t + dur * done / max(L, 1))
                done += plen(g) + gap
        if arrow:
            (x0, y0), (x1, y1) = s[-3], s[-1]
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
            hl = 15 + w * 2
            out.append(f'<g id="{mid}_h" opacity="0" transform="translate({x1:.1f},{y1:.1f}) rotate({ang:.1f})">'
                       f'<polygon points="4,0 {-hl},{-hl*0.62:.1f} {-hl},{hl*0.62:.1f}" fill="{cc}" stroke="rgba(0,0,0,.55)" '
                       f'stroke-width="3" style="filter:drop-shadow(0 0 7px {cc})"/></g>')
            S.tset(f"#{mid}_h", {"opacity": 1}, t + dur * 0.9)
        out.append("</g>")
        self.front.append("".join(out))
        self.keys.append(t + dur + 0.05)
        return mid

    def zone(self, cx, cy, rx, ry, t, c="red"):
        """space: a red patch (fill 0.36 + dashed edge) BEHIND the speaker's cutout, so it can only cover the background"""
        S, zid = self.S, self._id("zone")
        cc = col(c)
        self.back.append(f'<g id="{zid}" opacity="0"><ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{rgba(c, .36)}" '
                         f'stroke="{cc}" stroke-width="6" stroke-dasharray="22 14"/></g>')
        S.JS.append(f"gsap.set('#{zid}', {{svgOrigin: '{cx} {cy}'}});")
        S.tset(f"#{zid}", {"opacity": 1}, t)
        S.tween(f"#{zid}", {"scale": 0.82, "opacity": 0}, {"scale": 1, "opacity": 1, "ease": "power2.out", "duration": 0.4}, t)
        self.keys.append(t + 0.45)
        return zid

    def spot(self, cx, cy, rx, ry, t=None, dim=0.42):
        """spotlight behind the speaker's cutout: the background outside the focus ellipse darkens to `dim` in 0.3 s"""
        S, sid = self.S, self._id("spot")
        t = self.t0 if t is None else t
        d = (f"M0,0 H1080 V1920 H0 Z M{cx-rx},{cy} a{rx},{ry} 0 1,0 {2*rx},0 a{rx},{ry} 0 1,0 {-2*rx},0 Z")
        self.back.insert(0, f'<path id="{sid}" d="{d}" fill="rgba(0,0,0,{dim})" fill-rule="evenodd" opacity="0"/>')
        S.tween(f"#{sid}", {"opacity": 0}, {"opacity": 1, "ease": "power1.out", "duration": 0.3}, t)
        return sid

    def label(self, x, y, big, small, c, t, anchor="left", big_px=None, maxw=None):
        """the one-line finding: black card, a 10 px bar in the role colour, big Inter Tight 900 + small spaced Oswald 600;
        (x, y) is the card's top-left (anchor left) or top-right (anchor right); clip reveal in 0.25 s"""
        S, lid = self.S, self._id("lab")
        lo = self.clip or (LP["safe"]["left"], LP["safe"]["right"])
        right = min(lo[1], LP["safe"]["right"])
        maxw = maxw or ((right - x) if anchor == "left" else (x - max(lo[0], LP["safe"]["left"])))
        bp = fit(big, "label", big_px or LP["label"]["big_px"], maxw - 44)
        sp = LP["label"]["small_px"]
        if small:
            sp = fit(small, "cond", sp, maxw - 44, 3)
        w = max(width(big, "label", bp), width(small, "cond", sp, 3) if small else 0) + 44
        h = bp * 1.12 + (sp * 1.2 if small else 0) + 22
        x0 = x if anchor == "left" else x - w
        self._check((x0, y, x0 + w, y + h), "label")
        if x0 < LP["safe"]["left"] - 1 or x0 + w > LP["safe"]["right"] + 1 or y < LP["safe"]["top"] or y + h > LP["safe"]["bottom"]:
            raise ValueError(f"{self.name}: label {big!r} leaves the safe area ({x0:.0f},{y},{x0+w:.0f},{y+h:.0f})")
        cc = col(c)
        sm = (f'<div style="font-family:Oswald;font-weight:600;font-size:{sp}px;line-height:{sp*1.2:.0f}px;letter-spacing:3px;'
              f'color:{cc}">{esc(small)}</div>') if small else ""
        self.top.append(
            f'<div id="{lid}" style="position:absolute;left:{x0:.0f}px;top:{y:.0f}px;width:{w:.0f}px;height:{h:.0f}px;'
            f'background:{PAL["card"]};border-left:{LP["label"]["bar_px"]}px solid {cc};box-sizing:border-box;padding:9px 0 0 22px;'
            f'clip-path:inset(0 100% 0 0)"><div style="font-family:\'Inter Tight\';font-weight:900;font-size:{bp}px;'
            f'line-height:{bp*1.12:.0f}px;color:{PAL["chalk"]};white-space:nowrap">{esc(big)}</div>{sm}</div>')
        S.tween(f"#{lid}", {"clipPath": "inset(0 100% 0 0)"}, {"clipPath": "inset(0 0% 0 0)", "ease": "power2.out", "duration": 0.25}, t)
        S.TEXTS.append((t, self.t1, big + (" / " + small if small else "")))
        self.keys.append(t + 0.3)
        return lid

    def stamp(self, cx, cy, text, small, t, rot=-5):
        """once per reel: a framed card dropping from 1.7x to 1x with overshoot, slightly rotated, with a small flash"""
        S, sid = self.S, self._id("stamp")
        if S._stamped:
            raise ValueError("one stamp per reel (house.motion.stamp)")
        S._stamped = True
        bp = fit(text, "label", 66, 760)
        w = width(text, "label", bp) + 70
        h = bp * 1.15 + (60 if small else 0) + 40
        box = (cx - w / 2 - 30, cy - h / 2 - 30, cx + w / 2 + 30, cy + h / 2 + 30)
        self._check(box, "stamp")
        sm = (f'<div style="font-family:Oswald;font-weight:600;font-size:48px;letter-spacing:4px;color:{PAL["chalk"]}">'
              f'{esc(small)}</div>') if small else ""
        self.top.append(f'<div id="{sid}" style="position:absolute;left:{cx-w/2:.0f}px;top:{cy-h/2:.0f}px;width:{w:.0f}px;height:{h:.0f}px;'
                        f'box-sizing:border-box;border:7px solid {PAL["chalk"]};outline:3px solid {PAL["card_opaque"]};background:{PAL["card"]};'
                        f'text-align:center;padding-top:14px;opacity:0;transform:rotate({rot}deg)">'
                        f'<div style="font-family:\'Inter Tight\';font-weight:900;font-size:{bp}px;line-height:{bp*1.15:.0f}px;color:{PAL["yellow"]}">{esc(text)}</div>{sm}'
                        f'<div id="{sid}_f" style="position:absolute;inset:-7px;background:#fff;opacity:0"></div></div>')
        S.tset(f"#{sid}", {"opacity": 1}, t)
        S.tween(f"#{sid}", {"scale": 1.7, "rotation": rot - 6}, {"scale": 1, "rotation": rot, "ease": "back.out(2.2)", "duration": 0.32}, t)
        S.tset(f"#{sid}_f", {"opacity": 0.6}, t + 0.3)
        S.tween(f"#{sid}_f", {"opacity": 0.6}, {"opacity": 0, "duration": 0.12, "ease": "none"}, t + 0.3)
        S.TEXTS.append((t, self.t1, text))
        self.keys.append(t + 0.45)
        return sid

    def chalk(self, markup, back=False):
        (self.back if back else self.front).append(markup)

    def html(self, markup, under=False):
        """HTML on the scene: on top of the drawings, or under=True between the back layer and the drawings (a picture
        or a UI the rings and marker lines are drawn on)"""
        (self.under if under else self.top).append(markup)


# ---------------------------------------------------------------- the show
class Show:
    def __init__(self, project, dur, title, words="build/words.cut.json", plates=None, voice="assets/voice.wav", fixes=None,
                 lang="ru"):
        self.P = os.path.abspath(os.path.expanduser(project))
        self.dur, self.page_title, self.lang = dur, title, lang
        d = json.load(open(f"{self.P}/{words}", encoding="utf-8"))
        raw = [w for s in d["segments"] for w in s["words"]] if "segments" in d else d["words"]
        fixes = fixes or {}
        self.W = []
        for w in raw:
            t = w["word"].strip()
            for a, b in fixes.items():
                t = t.replace(a, b)
            self.W.append((t, w["start"], w["end"]))
        self.plates = plates or {"alt": "assets/alt.mp4"}
        self.main = list(self.plates)[0]
        self.voice = voice
        self.voice_dur = round(probe_dur(f"{self.P}/{voice}"), 2)
        ensure_fonts(self.P)
        self.H, self.JS, self.SFX, self.BEATS, self.TEXTS = [], [], [], [], []
        self.SECTIONS, self.FACE = [], []
        self.MODES, self.CLOCK, self.WIPES, self.FLIPS, self.BOARDS = [], [], [], [], []
        self._id, self._track, self._stamped = 0, 10, False
        self.t_start = 0.0
        self.breaks = None

    # ---- words + ids
    def at(self, word, after=0.0):
        k = lambda s: re.sub(r"[^\w-]", "", s.lower())
        for w, s, _ in self.W:
            if s >= after - 1e-6 and k(w) == k(word):
                return s
        raise KeyError(f"{word!r} not found after {after}")

    @staticmethod
    def n(t):
        return int(round(t * FPS))

    def nid(self, p="e"):
        self._id += 1
        return f"{p}{self._id}"

    def tset(self, sel, props, t):
        self.JS.append(f'tl.set("{sel}", {json.dumps(props, ensure_ascii=False)}, {fr(t):.4f});')

    def tween(self, sel, frm, to, t):
        self.JS.append(f'tl.fromTo("{sel}", {json.dumps(frm)}, {json.dumps({**to, "immediateRender": False})}, {fr(t):.4f});')

    def beat(self, bid, keys):
        self.BEATS.append({"id": bid, "type": "beat", "label": bid, "t0": round(min(keys), 3), "t1": round(max(keys), 3),
                           "keys": sorted(round(k, 3) for k in keys)})

    # ---- packaging state
    def mode(self, t, m):
        if m not in PK["modes"]:
            raise ValueError(m)
        self.MODES.append((t, m))

    def clock(self, t, state):
        self.CLOCK.append((t, state))

    def face_on(self, t0, t1, kind="live"):
        self.FACE.append((t0, t1, kind))

    # ---- scenes
    def _open(self, name, t0, t1, z, bg="transparent", extra=""):
        self.SECTIONS.append((name, t0, t1))
        self._track += 1
        return (f'<section id="{name}" class="clip full" data-start="{fr(t0):.4f}" data-duration="{fr(t1)-fr(t0):.4f}" '
                f'data-track-index="{self._track}" style="z-index:{z};background:{bg};{extra}">')

    def freeze(self, name, t0, t1, plate, matte, face, at=None):
        """the speaker's footage frozen on the frame at `at` (default t0): the still, the flash + spotlight + zones behind the
        cutout, the cutout (same frame, exact pixels), then rings / markers / labels on top. face = the face box in that frame."""
        n = self.n(at if at is not None else t0)
        bg, cut = freeze_still(self.P, self.plates[plate], matte, n, f"{name.lower()}_{plate}_{n}")
        sc = Scene(self, name, t0, t1, faces=[face])
        sc.kind, sc.bg, sc.cut, sc.frame = "freeze", bg, cut, n
        self.face_on(t0, t1, "freeze")
        return sc

    def board(self, name, t0, t1, flash_at=None):
        sc = Scene(self, name, t0, t1)
        sc.kind, sc.flash_at = "board", flash_at
        self.BOARDS.append((t0, t1))
        return sc

    def live_scene(self, name, t0, t1, face):
        sc = Scene(self, name, t0, t1, faces=[face])
        sc.kind = "live"
        return sc

    def split(self, name, t0, tf, t1, a, b):
        """dual-angle: two 537 px windows, each a 1:1 slice of a plate (slice_x = the slice's left edge in the plate),
        a 6 px yellow divider; both play from t0 and freeze together at tf (each on its own frame, its own cutout).
        a / b = (plate key, slice_x, matte path, face box in plate px). Returns (Scene A, Scene B) in screen px."""
        W, D = LP["split"]["win_w"], LP["split"]["divider"]
        wins = []
        for i, (pk, sx, matte, fbox) in enumerate((a, b)):
            ox = 0 if i == 0 else W + D
            n = self.n(tf)
            bg, cut = freeze_still(self.P, self.plates[pk], matte, n, f"{name.lower()}_{pk}_{n}")
            face = (fbox[0] - sx + ox, fbox[1], fbox[2] - sx + ox, fbox[3])
            sc = Scene(self, f"{name}{'AB'[i]}", t0, t1, faces=[face], clip=(ox, ox + W))
            sc.kind, sc.plate, sc.sx, sc.ox, sc.bg, sc.cut, sc.tf = "window", pk, sx, ox, bg, cut, tf
            wins.append(sc)
        self.face_on(t0, t1, "split")
        self._split = (name, t0, tf, t1, wins)
        return wins

    def close(self, sc):
        """write a scene into the page"""
        name, t0, t1 = sc.name, sc.t0, sc.t1
        svg = lambda items, i: (f'<svg id="{name.lower()}_{i}" class="full" viewBox="0 0 1080 1920" width="1080" height="1920">'
                                + "".join(items) + "</svg>")
        if sc.kind == "freeze":
            fid = f"{name.lower()}_flash"
            self.H.append(self._open(name, t0, t1, 5))
            self.H.append(f'<img class="full" src="{sc.bg}" alt="">')
            self.H.append(svg(sc.back, "back"))
            self.H.append(f'<div id="{fid}" class="full" style="background:#fff;opacity:0"></div>')
            self.H.append(f'<img class="full" src="{sc.cut}" alt="">')
            self.H.append("".join(sc.under))
            self.H.append(svg(sc.front, "front"))
            self.H.append("".join(sc.top))
            self.H.append("</section>")
            self.tset(f"#{fid}", {"opacity": 0.55}, t0)
            self.tween(f"#{fid}", {"opacity": 0.55}, {"opacity": 0, "ease": "none", "duration": 0.1}, t0)
        elif sc.kind == "board":
            grid = ("background-color:%s;background-image:linear-gradient(rgba(244,241,232,.06) 2px,transparent 2px),"
                    "linear-gradient(90deg,rgba(244,241,232,.06) 2px,transparent 2px);background-size:60px 60px;"
                    "background-position:0 0" % PAL["board"])
            self.H.append(self._open(name, t0, t1, 6, extra=grid))
            self.H.append(svg(sc.back, "back"))
            self.H.append("".join(sc.under))
            self.H.append(svg(sc.front, "front"))
            self.H.append("".join(sc.top))
            if sc.flash_at is not None:
                fid = f"{name.lower()}_flash"
                self.H.append(f'<div id="{fid}" class="full" style="background:#fff;opacity:0"></div>')
                for ft in (sc.flash_at if isinstance(sc.flash_at, (list, tuple)) else [sc.flash_at]):
                    self.tset(f"#{fid}", {"opacity": 0.5}, ft)
                    self.tween(f"#{fid}", {"opacity": 0.5}, {"opacity": 0, "ease": "none", "duration": 0.1}, ft)
            self.H.append("</section>")
        elif sc.kind == "live":
            self.H.append(self._open(name, t0, t1, 5))
            self.H.append("".join(sc.under))
            self.H.append(svg(sc.front, "front"))
            self.H.append("".join(sc.top))
            self.H.append("</section>")
        elif sc.kind == "window":
            nm, s0, tf, s1, wins = self._split
            W = LP["split"]["win_w"]
            if sc is wins[0]:          # a plain wrapper (not a clip): the window videos nest in plain divs, like step-deck's panel
                self.SECTIONS.append((nm, s0, s1))
                self.H.append(f'<div id="{nm.lower()}_wrap" class="full" style="z-index:6;background:{PAL["card_opaque"]};opacity:0;visibility:hidden">')
                self.tset(f"#{nm.lower()}_wrap", {"autoAlpha": 1}, s0)
                self.tset(f"#{nm.lower()}_wrap", {"autoAlpha": 0}, s1)
            vid = f"{name.lower()}_v"
            self._track += 1
            fid = f"{name.lower()}_flash"
            sx, ox = sc.sx, sc.ox
            self.H.append(f'<div id="{name.lower()}_win" style="position:absolute;left:{ox}px;top:0;width:{W}px;height:1920px;overflow:hidden">'
                          f'<div style="position:absolute;left:{-ox}px;top:0;width:1080px;height:1920px">'
                          f'<video id="{vid}" src="{self.plates[sc.plate]}" data-start="{fr(s0):.4f}" data-duration="{fr(tf)-fr(s0)+F1:.4f}" '
                          f'data-media-start="{fr(s0):.4f}" data-track-index="{self._track}" muted playsinline '
                          f'style="position:absolute;left:{ox-sx}px;top:0;width:1080px;height:1920px;object-fit:cover"></video>'
                          f'<div id="{name.lower()}_fz" style="position:absolute;left:0;top:0;width:1080px;height:1920px;opacity:0">'
                          f'<img src="{sc.bg}" alt="" style="position:absolute;left:{ox-sx}px;top:0;width:1080px;height:1920px">'
                          + svg(sc.back, "back") +
                          f'<div id="{fid}" class="full" style="background:#fff;opacity:0"></div>'
                          f'<img src="{sc.cut}" alt="" style="position:absolute;left:{ox-sx}px;top:0;width:1080px;height:1920px">'
                          + "".join(sc.under) + svg(sc.front, "front") + "".join(sc.top) + "</div></div></div>")
            self.tset(f"#{name.lower()}_fz", {"opacity": 1}, tf)
            self.tset(f"#{fid}", {"opacity": 0.55}, tf)
            self.tween(f"#{fid}", {"opacity": 0.55}, {"opacity": 0, "ease": "none", "duration": 0.1}, tf)
            if sc is wins[1]:
                self.H.append(f'<div style="position:absolute;left:{W}px;top:0;width:{LP["split"]["divider"]}px;height:1920px;background:{PAL["yellow"]}"></div>')
                self.H.append("</div>")
        else:
            raise ValueError(sc.kind)
        self.beat(name, sc.keys)

    # ---- transitions + packaging moves
    def wipe(self, t):
        """the packaging wipe between segments: a yellow slanted band crossing in 0.34 s, the cut on its midpoint"""
        self.WIPES.append(t)

    def flip(self, t):
        """the matchup bar's leader block flips to the other side, with a yellow flash"""
        self.FLIPS.append(t)

    def sfx(self, name, t, vol, dur=None, ms=0.0):
        ensure_sfx(self.P, name)
        self.SFX.append((name, max(0.0, t), vol, ms, dur))

    def subs(self, breaks=None):
        """subtitle chunks: `breaks` = word indices that start a new chunk (default: sentence / comma ends, <= maxw)"""
        self.breaks = breaks

    def _chunks(self):
        px, maxw = LP["subtitle"]["px"], LP["subtitle"]["maxw"]
        out, cur = [], []
        for i, (w, s, e) in enumerate(self.W):
            if self.breaks is not None:
                if i in self.breaks and cur:
                    out.append(cur)
                    cur = []
            elif cur and width(" ".join(x[0] for x in cur + [(w,)]), "sub", px) > maxw:
                out.append(cur)
                cur = []
            cur.append((w, s, e))
            if self.breaks is None and w[-1] in ".?!" :
                out.append(cur)
                cur = []
            elif self.breaks is None and w[-1] in ",:" and len(" ".join(x[0] for x in cur)) >= 14:
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
        for c in out:
            txt = " ".join(x[0] for x in c)
            if width(txt, "sub", px) > maxw:
                raise ValueError(f"subtitle chunk too long (shorten via breaks): {txt!r}")
        return out

    # ---- write
    def _packaging(self):
        P = []
        L = LP
        # corner bug
        b = L["bug"]
        bw = max(width(PK["show"], "label", b["block_px"]) + 40,
                 max(width(v[0], "cond", b["mode_px"], 3) + (50 if v[2] else 0) for v in PK["modes"].values()) + 30)
        P.append(f'<div id="bug" style="position:absolute;left:{b["right"]-bw:.0f}px;top:{b["top"]}px;width:{bw:.0f}px;z-index:40">'
                 f'<div style="background:{PAL["yellow"]};color:{PAL["card_opaque"]};font-family:\'Inter Tight\';font-weight:900;'
                 f'font-size:{b["block_px"]}px;line-height:{b["block_px"]*1.3:.0f}px;padding:0 20px;white-space:nowrap">{PK["show"]}</div>'
                 f'<div style="background:{PAL["card_opaque"]};height:{b["mode_px"]*1.3:.0f}px;position:relative">')
        for k, (txt, c, dot) in PK["modes"].items():
            d = (f'<span style="display:inline-block;width:22px;height:22px;border-radius:11px;background:{c};margin-right:16px;'
                 f'vertical-align:3px"></span>') if dot else ""
            P.append(f'<div id="bug_{k}" style="position:absolute;left:20px;top:0;opacity:0;font-family:Oswald;font-weight:600;'
                     f'font-size:{b["mode_px"]}px;line-height:{b["mode_px"]*1.3:.0f}px;letter-spacing:3px;color:{c};white-space:nowrap">{d}{txt}</div>')
        P.append("</div></div>")
        # clock
        c = L["clock"]
        icons = {"play": f'<polygon points="6,6 38,25 6,44" fill="{PAL["chalk"]}"/>',
                 "pause": f'<rect x="6" y="6" width="11" height="38" fill="{PAL["yellow"]}"/><rect x="25" y="6" width="11" height="38" fill="{PAL["yellow"]}"/>',
                 "rewind": f'<polygon points="22,6 2,25 22,44" fill="{PAL["chalk"]}"/><polygon points="44,6 24,25 44,44" fill="{PAL["chalk"]}"/>'}
        P.append(f'<div id="clk" style="position:absolute;left:{c["x"]}px;top:{c["y"]}px;height:{c["h"]}px;z-index:40;opacity:0;'
                 f'background:rgba(8,12,14,.78);padding:0 22px 0 16px;display:flex;align-items:center;gap:16px;white-space:nowrap">'
                 f'<svg width="46" height="50" viewBox="0 0 46 50">'
                 + "".join(f'<g id="clk_{k}" opacity="0">{v}</g>' for k, v in icons.items()) +
                 f'</svg><span id="clkd" style="font-family:\'JetBrains Mono\';font-weight:500;font-size:{c["px"]}px;color:{PAL["chalk"]}">00.00 s · F000</span></div>')
        # matchup bar
        s = L["score"]
        a, bnm = PK["matchup"]
        wa, wb = width(a, "cond", s["px"], 2) + 44, width(bnm, "cond", s["px"], 2) + 44
        gap = 70
        tw = wa + gap + wb
        P.append(f'<div id="score" style="position:absolute;left:{s["right"]-tw:.0f}px;top:{s["top"]}px;width:{tw:.0f}px;height:{s["px"]*1.7:.0f}px;'
                 f'background:{PAL["card_opaque"]};z-index:40;font-family:Oswald;font-weight:600;font-size:{s["px"]}px;letter-spacing:2px">'
                 f'<div id="score_blk" style="position:absolute;left:{wa+gap:.0f}px;top:0;width:{wb:.0f}px;height:100%;background:{PAL["yellow"]}"></div>'
                 f'<div id="score_a" style="position:absolute;left:0;width:{wa:.0f}px;text-align:center;line-height:{s["px"]*1.7:.0f}px;color:{PAL["chalk"]}">{a}</div>'
                 f'<div style="position:absolute;left:{wa:.0f}px;width:{gap}px;text-align:center;line-height:{s["px"]*1.7:.0f}px;color:{PAL["grey"]};font-style:italic">VS</div>'
                 f'<div id="score_b" style="position:absolute;left:{wa+gap:.0f}px;width:{wb:.0f}px;text-align:center;line-height:{s["px"]*1.7:.0f}px;color:{PAL["card_opaque"]}">{bnm}</div>'
                 f'<div id="score_f" style="position:absolute;inset:0;background:{PAL["yellow"]};opacity:0"></div></div>')
        for t in self.FLIPS:
            self.tween("#score_blk", {"x": 0}, {"x": -(wa + gap), "width": wa, "ease": "power3.inOut", "duration": 0.5}, t)
            self.tset("#score_a", {"color": PAL["card_opaque"]}, t + 0.25)
            self.tset("#score_b", {"color": PAL["chalk"]}, t + 0.25)
            self.tset("#score_f", {"opacity": 0.85}, t)
            self.tween("#score_f", {"opacity": 0.85}, {"opacity": 0, "ease": "none", "duration": 0.5}, t)
            self.TEXTS.append((t, self.dur, f"{a} leads"))
        # subtitles
        sb = L["subtitle"]
        for i, ch in enumerate(self._chunks()):
            txt = " ".join(x[0] for x in ch)
            t0 = ch[0][1]
            nxt = self._chunks_cache[i + 1][0][1] if i + 1 < len(self._chunks_cache) else self.dur
            t1 = min(nxt, ch[-1][2] + 0.9) if i + 1 < len(self._chunks_cache) else self.dur
            w = width(txt, "sub", sb["px"]) + 56
            P.append(f'<div id="sub{i}" style="position:absolute;left:{540-w/2:.0f}px;top:{sb["yc"]-sb["px"]*0.85:.0f}px;width:{w:.0f}px;'
                     f'height:{sb["px"]*1.7:.0f}px;background:rgba(0,0,0,.64);border-left:4px solid {PAL["yellow"]};box-sizing:border-box;'
                     f'text-align:center;font-family:\'Inter Tight\';font-weight:600;font-size:{sb["px"]}px;line-height:{sb["px"]*1.7:.0f}px;'
                     f'color:#fff;white-space:nowrap;z-index:40;opacity:0">{esc(txt)}</div>')
            self.tset(f"#sub{i}", {"opacity": 1}, t0)
            self.tset(f"#sub{i}", {"opacity": 0}, t1)
            self.TEXTS.append((t0, t1, txt))
        # wipes
        for i, t in enumerate(self.WIPES):
            wid = f"wipe{i}"
            P.append(f'<div id="{wid}" style="position:absolute;left:0;top:-300px;width:420px;height:2520px;z-index:50;'
                     f'background:{PAL["yellow"]};border-left:14px solid {PAL["card_opaque"]};border-right:14px solid {PAL["card_opaque"]};'
                     f'transform:translateX(-800px) skewX(-14deg)"></div>')
            self.tween(f"#{wid}", {"x": -800, "skewX": -14}, {"x": 1460, "skewX": -14, "ease": "none", "duration": 0.34}, t - 0.17)
        return "\n".join(P)

    def _states(self):
        # bug modes
        for t, m in sorted(self.MODES):
            for k in PK["modes"]:
                self.tset(f"#bug_{k}", {"opacity": 1 if k == m else 0}, t)
        # clock: per-frame text only when it changes
        ev = sorted(self.CLOCK, key=lambda e: e[0])
        last_txt, last_icon, last_vis = None, None, None
        held = 0.0
        for f in range(int(round(self.dur * FPS)) + 1):
            t = f / FPS
            cur = None
            for e in ev:
                if e[0] <= t + 1e-6:
                    cur = e
            if cur is None:
                continue
            t0, st = cur
            if st == "hide":
                vis, icon, show = 0, last_icon, None
            elif st == "play":
                vis, icon, show = 1, "play", t
            elif st == "pause":
                vis, icon, show = 1, "pause", t0
            else:                                  # ("rewind", from_t, to_t, dur)
                _, a, b, d = st
                u = min(1.0, (t - t0) / d)
                u = u * u * (3 - 2 * u)
                vis, icon, show = 1, "rewind" if u < 1 else "pause", a + (b - a) * u
            if vis != last_vis:
                self.tset("#clk", {"opacity": vis}, t)
                last_vis = vis
            if vis and icon != last_icon:
                for k in ("play", "pause", "rewind"):
                    self.tset(f"#clk_{k}", {"opacity": 1 if k == icon else 0}, t)
                self.tset("#clkd", {"color": PAL["yellow"] if icon == "pause" else PAL["chalk"]}, t)
                last_icon = icon
            if vis:
                fn = int(round(show * FPS))
                txt = f"{fn / FPS:05.2f} s · F{fn:03d}"
                if txt != last_txt:
                    self.tset("#clkd", {"textContent": txt}, t)
                    last_txt = txt
            held = t

    def build(self):
        DUR, P = self.dur, self.P
        self._chunks_cache = self._chunks()
        pk = self._packaging()
        self._states()
        faces = "".join(f"@font-face {{ font-family: '{fam}'; src: url('assets/fonts/{fn}-{sub}.woff2') format('woff2'); "
                        f"font-weight: {wt}; font-style: {sty}; unicode-range: {rng}; }}\n"
                        for fam, fn, wt, sty in TY["font_faces"] for sub, rng in TY["unicode_ranges"])
        vids = "\n".join(f'<video id="v_{k}" class="full" src="{v}" data-start="0" data-duration="{DUR:.2f}" data-track-index="{i}" muted playsinline></video>'
                         for i, (k, v) in enumerate(self.plates.items()) if k == self.main)
        aud = [f'<audio id="vo" src="{self.voice}" data-start="0" data-duration="{self.voice_dur:.2f}" data-track-index="80" data-volume="1"></audio>']
        for i, (f, t, v, ms, dur) in enumerate(self.SFX):
            dd = dur or SFX_LEN.get(f) or round(probe_dur(f"{P}/assets/sfx/{f}.wav"), 3)
            dd = min(dd, DUR - t)
            aud.append(f'<audio id="sfx{i}" src="assets/sfx/{f}.wav" data-start="{fr(t):.4f}" data-duration="{dd:.4f}" data-media-start="{ms:.3f}" '
                       f'data-track-index="{100 + i}" data-volume="{v}"></audio>')
        html = f"""<!doctype html>
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
<div id="cam" class="full" style="z-index:1">
{vids}
</div>
""" + "\n".join(self.H) + "\n" + pk + "\n" + "\n".join(aud) + (
            '\n<script>\nwindow.__timelines = window.__timelines || {};\nconst tl = gsap.timeline({ paused: true });\n'
            + "\n".join(self.JS) + f'\ntl.set({{}}, {{}}, {DUR:.2f});\nwindow.__timelines["main"] = tl;\n</script>\n</div>\n</body>\n</html>\n')
        open(f"{P}/index.html", "w").write(html)
        shots = [{"t0": a, "t1": b} for _, a, b in sorted(self.SECTIONS, key=lambda s: s[1])]
        json.dump({"fps": FPS, "beats": sorted(self.BEATS, key=lambda b: b["t0"]), "shots": shots,
                   "texts": [{"t0": round(a, 3), "t1": round(b, 3), "text": x} for a, b, x in sorted(self.TEXTS)]},
                  open(f"{P}/build/beats.json", "w"), indent=1, ensure_ascii=False)
        # face coverage: live = not inside a board section
        boards = self.BOARDS
        board_s = sum(b - a for a, b in boards)
        lines = [f"face on screen (live, frozen or split): {DUR - board_s:.2f} s of {DUR:.2f} s = {100*(DUR-board_s)/DUR:.1f} %",
                 f"freezes: {sum(1 for f in self.FACE if f[2] == 'freeze')} + split {sum(1 for f in self.FACE if f[2] == 'split')}; "
                 f"boards: {len(boards)}; wipes: {len(self.WIPES)}; sfx: {len(self.SFX)}; texts: {len(self.TEXTS)}; html {len(html)//1024} KB"]
        open(f"{P}/build/coverage.txt", "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return lines


if __name__ == "__main__":
    print(__doc__)
