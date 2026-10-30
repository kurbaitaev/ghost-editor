"""Product page: a review or demo of a named thing, laid out like a product page. White pages carry the content (a real
picture of the thing, rebuilt phone UI, hairline line-art drawings) and every move is a virtual camera inside the page;
the speaker's face comes in as a cut-out over a rounded footage card (hook, splits) and full frame for the lines they say
to the viewer; the spoken word rides in a grey pill over pages, two-tier captions (heavy sans + italic serif) sit on the
chest. From @adrien.ninet; the builder was generalised from the founding reel (2026-10-24).

    import sys; sys.path.insert(0, "<skill>/recipes/product-page"); from productpage import *
    R = ProductPage(P, plate="assets/alt.mp4", matte="assets/alt_matte.webm", fixes={"focusbook": "Focus Book"},
                    accent="#D94C5F", music={"id": "infinity", "db": -22.0, "duck": -8.0, "drops": [(3.86, 4.46)]})
    t = R.t
    R.hook(2.62, file_card("The Focus Book", "The Author", "assets/book2x.jpg"),
           [("One book changed", "sans", 80), ("how I", "sans", 80), ("plan my day.", "serif", 108)])
    R.art_page("s2", "cam1", 2.54, 4.44, place(phone_art("ph1").svg("ph1", 800, 744), 140, 340, 800, 744), 9,
               zoom_at=t("your"))                                      # the measured push, then room for the title
    R.page_title("s2t", 3.04, 4.44, 880, "your mornings", [t("your"), t("mornings")],
                 "without a phone.", [t("without", 3.5), t("phone")], 11)
    R.rise_page("s3", "cam3", "bk", 4.44, 8.36, "assets/book2x.jpg", (330, 300, 420, 630), 20,
                push_at=t("focus"), exit_at=t("rule"))                  # a real picture rises, pushes to its detail
    ty = R.split("s4", 8.36, 10.30, 30, ios_alert(...))                # the speaker's cut-out + a panel from the right
    R.face_beat("fc6", "assets/alt.mp4", 12.60, 15.267, 1.048, 50, [(12.60, 13.82, [("So you decide", "sans"), ("when,", "serif")])])
    R.whip_pages("s8", 19.367, 22.60, 60, page_a, page_b, land=t("walk"), cam_a="cam8a", cam_b="cam8b")
    R.gallery("s11", "cam11", 26.80, R.T, 85, [tile(...), ...], empty=[(0, 1)])
    R.pills([(2.70, 3.04), (4.48, 5.64), ...])                         # the windows where the word pill runs
    R.build()

The house (house.json; productpage.py reads palette, sizes, geometry and budgets from it):
- white #FDFDFD pages, black #0F0E0E titles, ONE accent = the named product's colour, soft shadows on objects only;
- two type voices: Inter Tight 800 + Playfair Display Italic 600 (the reference's Instrument Serif has no Cyrillic);
  page titles in black on pages, white chest captions on the face, the one-word grey pill over pages / splits / UI;
- hard cuts on sentence starts; all motion is a camera inside the page (measured push, zoom-out for the title,
  push-to-detail, accelerate into the cut), expo.out entrances with no overshoot, every UI action on its word;
- the speaker's plate as shot (no grade, no filter): full frame on face beats, a cut-out over a rounded card in the hook and splits;
- a ducked plucky bed that drops out under the hook payoff; SFX only where something enters or a UI action happens.
What changes every reel (catalog.json; components.py plan --style product-page): the hook device, the drawings, the UI
scenes, the transitions between pages, the outro. The drawings and UI builders below are the founding reel's set: reuse the kit
(Art, iso, box, line, cyl), draw NEW props for a new script.

Needs in the project: the approved cut's plate(s) as shot (assets/*.mp4), assets/voice.wav, build/words.cut.json (or
words.json), build/face.json per plate (scripts/face_track.py on that plate), a BiRefNet matte of the plate over the hook
and split windows (scripts/matte.py <plate> -o assets/<plate>_matte.webm --ranges ...), the real pictures through
insert_prep.py. build/metrics.json (advance widths) is made on the first build by fontwidths.py.
"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts", "lib"))
import facereel as FR  # noqa: E402
from facereel import BuildError, esc, norm, r3  # noqa: E402,F401

HOUSE = json.load(open(os.path.join(HERE, "house.json")))
PAL, GEO, BUD = HOUSE["palette"], HOUSE["geometry"], HOUSE["budgets"]
INK, PAGE, CAPTION = PAL["ink"], PAL["page"], PAL["caption"]
G0, G1, G2 = PAL["line_art"]
REF = 25                               # reference frames: n / REF s (DerovIOhToi is 25 fps)
PILL_BOTTOM = GEO["pill_top"] + GEO["pill_h"]
GHOST_PY = os.path.expanduser("~/.venvs/ghost-captions/bin/python")

VOICE = {"sans": ("Inter Tight", 800, "normal", "Inter Tight"), "serif": ("Playfair Display Italic", 600, "italic", "Playfair Display"),
         "reg": ("Playfair Display", 400, "normal", "Playfair Display")}
FONTS = ["Inter Tight", "Inter", "Playfair Display", "Playfair Display:italic"]

# measured curves (DerovIOhToi SPEC C5 / D2, replica REPORT): the phone push of f27-f38 in 0.04 s steps, the whip strip
CAM_PUSH = [.654, .654, .666, .683, .709, .784, .922, .951, .967, .981, .988, .993, 1.0]
WHIP_A = [(0, 0), (.04, -70), (.08, -180), (.12, -400), (.16, -1100)]          # outgoing page x
WHIP_B = [(.12, 1100), (.16, 950), (.20, 448), (.24, 148), (.28, 28), (.32, 0)]  # incoming page x (lands at +0.32)
WHIP_BLUR = [(.04, 8), (.08, 95), (.12, 140), (.16, 140), (.20, 140), (.24, 95), (.28, 12)]
KX = 10                                # x-only blur: scaleX KX around a blur / KX, then back


def head_top(fs, a, b):
    return min(s[1] for s in fs if a - 0.2 <= s[0] <= b + 0.2)


def core_bottom(fs, a, b):
    return max(FR.core(s)[3] for s in fs if a - 0.2 <= s[0] <= b + 0.2)


def letters(text, cls):
    return "".join('<span class="sp"> </span>' if ch == " " else f'<span class="ch {cls}">{esc(ch)}</span>' for ch in text)


def tier_style(voice, size, top, color=INK, extra=""):
    fam, wt, style, css_fam = VOICE[voice]
    return (f'top:{top:.1f}px;font-family:\'{css_fam}\';font-style:{style};font-weight:{wt};font-size:{size}px;line-height:{size}px;'
            f'color:{color};{extra}')


def place(svg, left, top, w, h, cid=None, extra=""):
    """a drawing (or any html) in an absolute box on the page"""
    idp = f'id="{cid}" ' if cid else ""
    return f'<div {idp}class="abs" style="left:{left}px;top:{top}px;width:{w}px;height:{h}px{";" + extra if extra else ""}">{svg}</div>'


# ================================================================== the hook file card (C2)
BOOK_GLYPH = ('<path d="M44 9 h16 a3 3 0 0 1 3 3 v22 a3 3 0 0 1 -3 3 h-16 a5 5 0 0 1 -5 -5 v-18 a5 5 0 0 1 5 -5 z M39 31 a5 5 0 0 1 5 -5 h19" '
              f'fill="none" stroke="{PAL["card_glyph"]}" stroke-width="3" stroke-linejoin="round"/>')


def file_card(title, sub, badge=None, glyph=BOOK_GLYPH, badge_box=(760, 196, 124, 186, 5)):
    """the dark file card of the hook: the thing's name, a grey '> [glyph] second row', the real picture as its corner
    badge (a cover: 124 x 186; an app icon: pass a square badge_box)"""
    html = (f'<div id="hk_cd" class="abs" style="left:230px;top:262px;width:620px;height:210px;background:{PAL["card"]};border-radius:16px;">'
            f'<p class="abs" style="left:0;top:46px;width:620px;text-align:center;margin:0;font-family:Inter;font-weight:600;font-size:48px;line-height:56px;color:#fff;letter-spacing:0.3px;">{esc(title)}</p>'
            f'<svg class="abs" style="left:30px;top:134px" width="96" height="44" viewBox="0 0 96 44">'
            f'<polyline points="4,10 16,22 4,34" fill="none" stroke="{PAL["card_glyph"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            f'{glyph}</svg>'
            f'<p class="abs" style="left:112px;top:128px;margin:0;font-family:\'Inter Tight\';font-weight:600;font-size:48px;line-height:56px;color:{PAL["card_sub"]};">{esc(sub)}</p></div>')
    if badge:
        l, t, w, h, r = badge_box
        html += (f'<img id="hk_badge" class="abs" src="{badge}" style="left:{l}px;top:{t}px;width:{w}px;height:{h}px;border-radius:{r}px;'
                 f'box-shadow:{PAL["shadows"]["badge"]};" alt="">')
    return html


# ================================================================== hairline line art (C5): the kit + the founding reel's drawings
C30 = math.cos(math.pi / 6)
NS = 'vector-effect="non-scaling-stroke"'


class Art:
    """an SVG drawing that tracks its own bounding box; .svg() fits it into a w x h box"""
    def __init__(s):
        s.el, s.bb = [], [1e9, 1e9, -1e9, -1e9]

    def pts(s, ps):
        for x, y in ps:
            s.bb = [min(s.bb[0], x), min(s.bb[1], y), max(s.bb[2], x), max(s.bb[3], y)]

    def add(s, svg, ps=()):
        s.pts(ps)
        s.el.append(svg)

    def svg(s, sid, w, h, pad=14, style=""):
        x0, y0, x1, y1 = s.bb[0] - pad, s.bb[1] - pad, s.bb[2] + pad, s.bb[3] + pad
        return (f'<svg id="{sid}" width="{w}" height="{h}" viewBox="{x0:.1f} {y0:.1f} {x1 - x0:.1f} {y1 - y0:.1f}" '
                f'preserveAspectRatio="xMidYMid meet" style="overflow:visible;{style}">' + "".join(s.el) + "</svg>")


def iso(x, y, z, k):
    return ((x - y) * C30 * k, (x + y) * 0.5 * k - z * k)


def poly(ps, fill="#fff", stroke=G1, sw=2.4, extra=""):
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in ps)
    return f'<polygon points="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" {NS} {extra}/>'


def box(a, x0, y0, z0, w, d, h, k, stroke=G1, fill="#fff", top=None, sw=2.4, extra=""):
    """an isometric box (three visible faces) added to Art a"""
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    p = lambda x, y, z: iso(x, y, z, k)  # noqa: E731
    faces_ = [[p(x1, y0, z0), p(x1, y1, z0), p(x1, y1, z1), p(x1, y0, z1)],
              [p(x0, y1, z0), p(x1, y1, z0), p(x1, y1, z1), p(x0, y1, z1)],
              [p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)]]
    for i, f in enumerate(faces_):
        a.add(poly(f, top if (i == 2 and top) else fill, stroke, sw, extra), f)


def line(a, x0, y0, x1, y1, stroke=G2, sw=2.2, dash=None, extra=""):
    da = f'stroke-dasharray="{dash}"' if dash else ""
    a.add(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" {da} {NS} {extra}/>',
          [(x0, y0), (x1, y1)])


def cyl(a, cx, cy, z0, r, h, k, stroke=G1, rim=True):
    """an isometric cylinder (a mug, a pot); returns (X, Y0, Y1, rx, ry)"""
    X, Y0 = iso(cx, cy, z0, k)
    _, Y1 = iso(cx, cy, z0 + h, k)
    rx, ry = 1.2247 * r * k, 0.7071 * r * k
    a.add(f'<path d="M {X - rx:.1f} {Y1:.1f} L {X - rx:.1f} {Y0:.1f} A {rx:.1f} {ry:.1f} 0 0 0 {X + rx:.1f} {Y0:.1f} L {X + rx:.1f} {Y1:.1f} Z" '
          f'fill="#fff" stroke="{stroke}" stroke-width="2.4" {NS}/>', [(X - rx, Y1 - ry), (X + rx, Y0 + ry)])
    a.add(f'<ellipse cx="{X:.1f}" cy="{Y1:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#fff" stroke="{stroke}" stroke-width="2.4" {NS}/>')
    if rim:
        a.add(f'<ellipse cx="{X:.1f}" cy="{Y1:.1f}" rx="{rx * 0.82:.1f}" ry="{ry * 0.82:.1f}" fill="#F2F2F2" stroke="{G2}" stroke-width="2" {NS}/>')
    return X, Y0, Y1, rx, ry


def phone_art(idp):
    """exploded hairline phone (reference page 1): back shell, board + battery, glass with an app grid; the black tile
    (#<idp>_act, bead #<idp>_bd) hops with ProductPage.phone_hops"""
    a, k = Art(), 0.82
    c, s = 0.866 * k, 0.5 * k
    W_, L_ = 280, 560

    def corners(ey):
        return [(c * (x - y), s * (x + y) + ey) for x, y in [(0, 0), (W_, 0), (W_, L_), (0, L_)]]

    def g(ey, inner):
        a.add(f'<g transform="matrix({c:.4f},{s:.4f},{-c:.4f},{s:.4f},0,{ey})">{inner}</g>', corners(ey))

    def rr(x, y, w, h, rx, stroke=G1, fill="#fff", sw=2.4, extra=""):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {NS} {extra}/>'
    g(206, rr(0, 0, W_, L_, 40, G2))
    g(190, rr(0, 0, W_, L_, 40, G1) + rr(22, 22, 112, 112, 30, G2) +
      "".join(f'<circle cx="{x}" cy="{y}" r="19" fill="#fff" stroke="{G2}" stroke-width="2.2" {NS}/>' for x, y in [(56, 56), (100, 56), (56, 100)]))
    tc, bc = corners(0), corners(190)
    for i in (1, 2, 3):
        line(a, tc[i][0], tc[i][1], bc[i][0], bc[i][1], G2, 2, "3 7")
    for i in (1, 3):
        a.add(f'<circle cx="{tc[i][0]:.1f}" cy="{(tc[i][1] + bc[i][1]) / 2 + 20:.1f}" r="5.5" fill="#111"/>')
    g(95, rr(14, 14, 252, 532, 32, G2) + rr(50, 196, 180, 300, 16, G1) + rr(40, 40, 200, 112, 12, G2) +
      rr(62, 62, 48, 48, 6, G2) + rr(128, 66, 84, 24, 5, G2) + rr(128, 104, 50, 30, 5, G2))
    g(10, rr(0, 0, W_, L_, 40, G2))
    tiles = "".join(rr(30 + i * 58, 82 + j * 68, 44, 44, 11, G2, "none", 2) for i in range(4) for j in range(5))
    dock = "".join(rr(30 + i * 58, 474, 44, 44, 11, G2, "none", 2) for i in range(4))
    g(0, rr(0, 0, W_, L_, 40, G0) + rr(14, 14, 252, 532, 30, G2, "none") + rr(104, 30, 72, 20, 10, G1, "none") + tiles + dock +
      f'<rect id="{idp}_act" x="88" y="150" width="44" height="44" rx="11" fill="#111"/>' +
      f'<circle id="{idp}_bd" cx="110" cy="214" r="5" fill="#111"/>')
    return a


PH_POS = [(1, 1), (2, 3), (0, 2), (3, 0), (1, 4), (2, 1), (0, 4), (3, 2), (1, 0), (2, 2)]


def bed_art(idp):
    """a bed in isometric hairline with a black moon (#<idp>_moon) that bobs"""
    a, k = Art(), 0.85
    p = lambda x, y, z: iso(x, y, z, k)  # noqa: E731
    box(a, 0, -26, 0, 300, 26, 230, k, G1)
    for x, y in [(6, 6), (278, 6)]:
        box(a, x, y, 0, 16, 16, 40, k, G2)
    box(a, 0, 0, 40, 300, 520, 40, k, G1)
    for x, y in [(6, 498), (278, 498)]:
        box(a, x, y, 0, 16, 16, 40, k, G2)
    box(a, 8, 8, 80, 284, 504, 44, k, G2)
    box(a, 36, 22, 124, 228, 92, 26, k, G1)
    box(a, 2, 196, 112, 296, 330, 22, k, G1)
    x0, y0 = p(2, 236, 134)
    x1, y1 = p(298, 236, 134)
    line(a, x0, y0, x1, y1, G2, 2)
    mx, my = p(150, -13, 330)
    r = 54
    a.add(f'<g id="{idp}_moon"><path d="M {mx:.1f} {my - r:.1f} A {r} {r} 0 1 0 {mx:.1f} {my + r:.1f} A {r * 1.3:.1f} {r * 1.3:.1f} 0 0 1 {mx:.1f} {my - r:.1f} Z" fill="#111"/>'
          + "".join(f'<circle cx="{mx + dx:.1f}" cy="{my + dy:.1f}" r="{rr}" fill="#111"/>' for dx, dy, rr in [(96, -40, 7), (128, 24, 5.5), (-84, 34, 6)])
          + "</g>", [(mx - r - 92, my - r - 10), (mx + 136, my + r)])
    return a


def shoe_art(idp):
    """a running shoe in profile (#<idp>_shoe rocks), black laces and speed lines"""
    a = Art()
    a.pts([(0, 120), (640, 370)])
    body = (f'<path d="M 60 300 C 52 322 70 342 104 342 L 530 342 C 578 342 604 324 598 300 Z" fill="#fff" stroke="{G1}" stroke-width="2.4" {NS}/>'
            f'<path d="M 66 300 L 64 196 C 64 160 86 140 118 142 L 186 150 C 214 154 238 166 258 182 L 286 150 C 300 128 330 124 346 142 L 372 186 '
            f'C 430 206 510 236 556 258 C 588 274 600 290 598 300 Z" fill="#fff" stroke="{G0}" stroke-width="2.4" stroke-linejoin="round" {NS}/>'
            f'<path d="M 70 318 L 590 318" stroke="{G2}" stroke-width="2" {NS}/>'
            f'<path d="M 470 300 C 500 270 540 262 572 268" fill="none" stroke="{G2}" stroke-width="2" {NS}/>'
            f'<path d="M 64 196 L 50 188 L 50 238 L 64 244" fill="none" stroke="{G1}" stroke-width="2.2" {NS}/>'
            f'<path d="M 118 142 C 140 176 196 186 258 182" fill="none" stroke="{G2}" stroke-width="2" {NS}/>'
            f'<path d="M 92 286 C 200 278 330 268 452 250" fill="none" stroke="{G2}" stroke-width="2" stroke-dasharray="3 7" {NS}/>'
            f'<path d="M 286 150 C 300 175 320 192 372 186" fill="none" stroke="{G2}" stroke-width="2" {NS}/>')
    lace = "".join(f'<path d="M {266 + i * 26} {190 + i * 2} L {286 + i * 26} {160 + i * 4}" stroke="#111" stroke-width="3.4" stroke-linecap="round"/>'
                   f'<circle cx="{266 + i * 26}" cy="{190 + i * 2}" r="4.6" fill="#111"/>' for i in range(4))
    a.add(f'<g id="{idp}_shoe">{body}{lace}</g>')
    for y, x0, x1 in [(226, 0, 34), (256, -14, 26), (286, 6, 38)]:
        line(a, x0, y, x1, y, "#111", 3.2)
    line(a, 30, 362, 640, 362, G2, 2, "4 9")
    return a


def mugs_art(idp):
    """two mugs and a teapot on a small table, black steam (#<idp>_steam) rising"""
    a, k = Art(), 0.9
    for x, y in [(12, 12), (352, 12), (12, 232), (352, 232)]:
        box(a, x, y, 0, 16, 16, 150, k, G2)
    box(a, 0, 0, 150, 380, 260, 16, k, G1)
    steam = []

    def mug(cx, cy):
        X, Y0, Y1, rx, ry = cyl(a, cx, cy, 166, 34, 72, k)
        hy0, hy1 = Y1 + (Y0 - Y1) * 0.25, Y1 + (Y0 - Y1) * 0.78
        a.add(f'<path d="M {X + rx - 1:.1f} {hy0:.1f} C {X + rx + 40:.1f} {hy0 - 6:.1f} {X + rx + 40:.1f} {hy1 + 6:.1f} {X + rx - 1:.1f} {hy1:.1f}" '
              f'fill="none" stroke="{G1}" stroke-width="2.4" {NS}/>', [(X + rx + 36, hy0)])
        for dx in (-11, 11):
            sx, sy = X + dx, Y1 - 10
            steam.append(f'<path d="M {sx:.1f} {sy:.1f} c -13 -15 13 -27 0 -42 c -13 -15 13 -27 0 -42" fill="none" stroke="#111" stroke-width="3" stroke-linecap="round"/>'
                         f'<circle cx="{sx:.1f}" cy="{sy - 90:.1f}" r="4.6" fill="#111"/>')
            a.pts([(sx - 14, sy - 96)])
    mug(96, 116)
    X, Y0, Y1, rx, ry = cyl(a, 286, 70, 166, 52, 56, k, G1, rim=False)
    a.add(f'<path d="M {X - rx * 0.72:.1f} {Y1:.1f} A {rx * 0.72:.1f} {ry * 1.9:.1f} 0 0 1 {X + rx * 0.72:.1f} {Y1:.1f}" fill="#fff" stroke="{G1}" stroke-width="2.4" {NS}/>'
          f'<circle cx="{X:.1f}" cy="{Y1 - ry * 1.9 - 6:.1f}" r="7" fill="#fff" stroke="{G1}" stroke-width="2.2" {NS}/>'
          f'<path d="M {X - rx + 3:.1f} {Y0 - 22:.1f} C {X - rx - 26:.1f} {Y0 - 30:.1f} {X - rx - 34:.1f} {Y1 + 2:.1f} {X - rx - 52:.1f} {Y1 - 18:.1f} '
          f'L {X - rx - 42:.1f} {Y1 - 24:.1f} C {X - rx - 26:.1f} {Y1 - 8:.1f} {X - rx - 18:.1f} {Y0 - 46:.1f} {X - rx + 3:.1f} {Y0 - 44:.1f}" '
          f'fill="#fff" stroke="{G1}" stroke-width="2.4" stroke-linejoin="round" {NS}/>'
          f'<path d="M {X + rx - 2:.1f} {Y1 + 8:.1f} C {X + rx + 44:.1f} {Y1:.1f} {X + rx + 40:.1f} {Y0 - 8:.1f} {X + rx - 6:.1f} {Y0 - 14:.1f}" '
          f'fill="none" stroke="{G1}" stroke-width="2.4" {NS}/>', [(X - rx - 56, Y1 - ry * 1.9 - 16), (X + rx + 44, Y0)])
    mug(206, 196)
    a.add(f'<g id="{idp}_steam">{"".join(steam)}</g>')
    return a


STEP_H = [44, 104, 176, 262, 362]


def stairs_art(idp):
    """a staircase of growing steps with a flag on top and a black bead (#<idp>_bead); returns (Art, the step tops as
    offsets from the bead's rest, for ProductPage.hop / falter)"""
    a, k = Art(), 0.8
    p = lambda x, y, z: iso(x, y, z, k)  # noqa: E731
    for i in range(4, -1, -1):
        box(a, 0, (4 - i) * 90, 0, 240, 90, STEP_H[i], k, G0 if i == 4 else G1)
    fx, fy = p(150, 45, STEP_H[4])
    a.add(f'<line x1="{fx:.1f}" y1="{fy:.1f}" x2="{fx:.1f}" y2="{fy - 120:.1f}" stroke="#111" stroke-width="3.4" stroke-linecap="round"/>'
          f'<path d="M {fx:.1f} {fy - 120:.1f} L {fx + 66:.1f} {fy - 100:.1f} L {fx:.1f} {fy - 80:.1f} Z" fill="#111"/>', [(fx, fy - 124), (fx + 70, fy)])
    for i in range(4):
        x0, y0 = p(240, (4 - i) * 90 + 45, STEP_H[i])
        x1, y1 = p(240, (4 - i - 1) * 90 + 45, STEP_H[i + 1])
        line(a, x0 + 18, y0, x1 + 18, y1, G2, 2, "3 7")
    bx, by = p(120, 4 * 90 + 45, STEP_H[0])
    a.add(f'<circle id="{idp}_bead" cx="{bx:.1f}" cy="{by - 17:.1f}" r="17" fill="#111"/>')
    tops = [p(120, (4 - i) * 90 + 45, STEP_H[i]) for i in range(5)]
    return a, [(x - bx, y - by) for x, y in tops]


def book_art(idp):
    """a closed book with a black ribbon (gallery tile)"""
    a, k = Art(), 0.9
    box(a, 0, 0, 0, 200, 290, 34, k, G1)
    p = lambda x, y, z: iso(x, y, z, k)  # noqa: E731
    for z in (9, 17, 25):
        x0, y0 = p(200, 8, z)
        x1, y1 = p(200, 282, z)
        line(a, x0, y0, x1, y1, G2, 1.8)
        x0, y0 = p(8, 290, z)
        x1, y1 = p(192, 290, z)
        line(a, x0, y0, x1, y1, G2, 1.8)
    a.add(poly([p(30, 40, 34), p(170, 40, 34), p(170, 140, 34), p(30, 140, 34)], "none", G2, 2))
    for i, w_ in enumerate((120, 90, 104)):
        x0, y0 = p(40, 170 + i * 26, 34)
        x1, y1 = p(40 + w_, 170 + i * 26, 34)
        line(a, x0, y0, x1, y1, G2, 2)
    r1, r2, r3_ = p(140, 290, 34), p(164, 290, 34), p(164, 290, -40)
    r4 = p(152, 290, -26)
    r5 = p(140, 290, -40)
    a.add(poly([r1, r2, r3_, r4, r5], "#111", "#111", 1))
    x0, y0 = p(40, 170, 34)
    a.add(f'<circle cx="{x0:.1f}" cy="{y0:.1f}" r="5" fill="#111"/>')
    return a


ARTS = {"phone": phone_art, "bed": bed_art, "shoe": shoe_art, "mugs": mugs_art, "stairs": stairs_art, "book": book_art}


# ================================================================== rebuilt phone UI (the founding reel's scenes; build NEW ones per reel)
def bell_glyph(accent):
    """a white bell for an app icon, with a slash (#sl_a in the accent under #sl_b in white) drawn on by draw_on"""
    return ('<svg viewBox="0 0 24 24" width="128" height="128" style="position:absolute;left:46px;top:46px;overflow:visible">'
            '<path d="M12 3.2c-3.1 0-5.4 2.4-5.4 5.5v3.6L5 15.4c-.3.6.1 1.3.8 1.3h12.4c.7 0 1.1-.7.8-1.3l-1.6-3.1V8.7c0-3.1-2.3-5.5-5.4-5.5z" fill="#fff"/>'
            '<path d="M9.6 18.2a2.4 2.4 0 0 0 4.8 0z" fill="#fff"/>'
            f'<line id="sl_a" x1="3.4" y1="3.4" x2="20.6" y2="20.6" stroke="{accent}" stroke-width="3.8" stroke-linecap="round" stroke-dasharray="24.4" stroke-dashoffset="24.4"/>'
            '<line id="sl_b" x1="3.4" y1="3.4" x2="20.6" y2="20.6" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-dasharray="24.4" stroke-dashoffset="24.4"/></svg>')


def ios_alert(title, body, no, yes, accent, aid="s4_alert", no_id="btn_no"):
    """an iOS system alert (title, body, two buttons in the accent); press #<no_id> on its word"""
    return (f'<div id="{aid}" class="abs" style="left:120px;top:540px;width:690px;border-radius:38px;background:#F2F2F2;border:1.5px solid #E2E2E4;'
            f'box-shadow:{PAL["shadows"]["alert"]};overflow:hidden;text-align:center;font-family:Inter;">'
            '<div style="padding:46px 44px 36px;"><div style="font-weight:600;font-size:44px;line-height:56px;color:#000;">'
            f'{esc(title)}</div>'
            '<div style="font-weight:400;font-size:32px;line-height:43px;color:#1C1C1E;margin-top:16px;">'
            f'{esc(body)}</div></div>'
            '<div style="display:flex;border-top:1.5px solid #C8C8CC;height:114px;">'
            f'<div id="{no_id}" style="flex:1;border-right:1.5px solid #C8C8CC;font-size:40px;line-height:114px;color:{accent};">{esc(no)}</div>'
            f'<div style="flex:1;font-size:40px;line-height:114px;color:{accent};font-weight:600;">{esc(yes)}</div></div></div>')


GLY = {"mail": '<rect x="3" y="5.5" width="18" height="13" rx="2.2"/><path d="M3.8 7 L12 13 L20.2 7"/>',
       "chat": '<path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H11l-4.5 3.5V17H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/>',
       "heart": '<path d="M12 19.5s-7.5-4.6-7.5-10A4.2 4.2 0 0 1 12 7a4.2 4.2 0 0 1 7.5 2.5c0 5.4-7.5 10-7.5 10z"/>',
       "phone": '<path d="M6.5 3.5h3l1.6 4.2-2 1.5a11 11 0 0 0 5.7 5.7l1.5-2 4.2 1.6v3a1.8 1.8 0 0 1-2 1.8A16.5 16.5 0 0 1 4.7 5.5a1.8 1.8 0 0 1 1.8-2z"/>',
       "cal": '<rect x="3.5" y="5" width="17" height="15" rx="2.2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>'}
RH = 156


def ios_list(sid, rows, title, back, section, accent, accent45, rh=RH, glyphs=GLY):
    """an iOS Settings list (rows = [(label, glyph key), ...], every toggle on); the highlight #<sid>_hl and the toggles
    #tg<i> / knobs #kn<i> are driven by ProductPage.rows_off on the spoken words"""
    out = ""
    for i, (lab, g) in enumerate(rows):
        y0 = i * rh
        out += (f'<div class="abs" style="left:30px;top:{y0 + 33}px;width:90px;height:90px;border-radius:22px;background:#1C1C1E;">'
                f'<svg viewBox="0 0 24 24" width="58" height="58" style="position:absolute;left:16px;top:16px" fill="none" stroke="#fff" stroke-width="1.7" '
                f'stroke-linejoin="round" stroke-linecap="round">{glyphs[g]}</svg></div>'
                f'<p class="abs" style="left:150px;top:{y0}px;margin:0;font-family:Inter;font-size:50px;line-height:{rh}px;color:#000;">{esc(lab)}</p>'
                f'<div id="tg{i}" class="abs" style="left:846px;top:{y0 + 38}px;width:132px;height:80px;border-radius:40px;background:{accent};">'
                f'<div id="kn{i}" class="abs" style="left:56px;top:4px;width:72px;height:72px;border-radius:36px;background:#fff;box-shadow:0 3px 8px rgba(0,0,0,0.18);"></div></div>')
        if i < len(rows) - 1:
            out += f'<div class="abs" style="left:150px;top:{y0 + rh - 1}px;width:858px;height:1.5px;background:#C6C6C8;"></div>'
    return (f'<p class="abs" style="left:40px;top:236px;margin:0;font-family:Inter;font-size:46px;line-height:56px;color:{accent};">{esc(back)}</p>'
            f'<p class="abs" style="left:44px;top:312px;margin:0;font-family:Inter;font-weight:700;font-size:92px;line-height:110px;color:#000;letter-spacing:-1.5px;">{esc(title)}</p>'
            f'<p class="abs" style="left:84px;top:494px;margin:0;font-family:Inter;font-size:34px;line-height:44px;color:#6D6D72;">{esc(section)}</p>'
            f'<div class="abs" style="left:36px;top:556px;width:1008px;height:{len(rows) * rh}px;background:#fff;border-radius:30px;overflow:hidden;">'
            f'<div id="{sid}_hl" class="abs" style="left:0;top:0;width:1008px;height:{rh}px;background:{accent45};opacity:0;"></div>{out}</div>')


# ================================================================== gallery tiles (C13)
COLX, ROWY = GEO["gallery"]["cols"], GEO["gallery"]["rows"]
TWD, THT = GEO["gallery"]["cell"]
GAP = GEO["gallery"]["gap"]


def tile(tid, c, r, art_svg, label="", cw=1, ch=1, extra=""):
    """a gallery cell at column c, row r spanning cw x ch cells; `label` is the word it stands for (recorded in the
    plan; the founding reel drew no label)"""
    w, h = TWD * cw + GAP * (cw - 1), THT * ch + GAP * (ch - 1)
    return (f'<div id="{tid}" class="abs" style="left:{COLX[c]}px;top:{ROWY[r]}px;width:{w}px;height:{h}px;border:2px solid {PAL["tile_border"]};border-radius:22px;'
            f'background:#fff;box-sizing:border-box;{extra}"><div class="abs" style="left:26px;top:26px;right:26px;bottom:26px;">{art_svg}</div></div>')


def full(svg):
    """an Art.svg() that fills its box (for tiles)"""
    return svg.replace('width="', 'data-w="', 1).replace('height="', 'data-h="', 1).replace("style=\"overflow:visible;", "style=\"overflow:visible;width:100%;height:100%;", 1)


BASE_CSS = f"""
#root {{ background:{PAGE}; }}
.abs {{ position:absolute; }}
.wrap {{ position:absolute; left:0; top:0; width:1080px; height:1920px; }}
.page {{ position:absolute; left:0; top:0; width:1080px; height:1920px; background:{PAGE}; }}
.vid {{ position:absolute; left:0; top:0; width:1080px; height:1920px; object-fit:fill; }}
.ch, .cw {{ display:inline-block; }}
.sp {{ display:inline-block; white-space:pre; }}
.tier {{ position:absolute; left:0; width:1080px; margin:0; text-align:center; white-space:nowrap; }}
.pillrow {{ position:absolute; left:0; top:{GEO["pill_top"]}px; width:1080px; height:{GEO["pill_h"]}px; display:flex; justify-content:center; z-index:90; }}
.pill {{ display:block; height:{GEO["pill_h"]}px; padding:0 16px; border-radius:10px; background:{PAL["pill"]}; color:#fff; font-family:"Inter Tight";
        font-weight:700; font-size:{GEO["pill_font"]}px; line-height:{GEO["pill_h"]}px; letter-spacing:-0.6px; white-space:nowrap; }}
"""


class ProductPage(FR.Reel):
    """One Product page reel on facereel.Reel (plate as shot, voice, words, SFX levelled by role, ducked bed, side files).
    plate: the full-frame plate (the hook and splits use it and its matte); faces: {plate: face json} for every plate
    used (default {plate: build/face.json}); fixes: {raw word: shown spelling} for the pill; accent / accent45: the named
    product's colour and its 45 % tint; music: facereel's dict plus "drops": [(t0, t1), ...] (bed out under the pivot)."""

    def __init__(self, project, plate="assets/plate.mp4", matte=None, words=None, fixes=None, tail=0.35, fps=30, music=None,
                 accent=None, accent45=None, faces=None):
        super().__init__(project, plate=plate, words=words, fixes=fixes, tail=tail, fps=fps, music=music)
        self.plate = self.rel(self.plate_src)
        self.matte = matte
        if matte and not os.path.exists(os.path.join(self.P, matte)):
            raise BuildError(f"the matte {matte} is not in {self.P} (scripts/matte.py {self.plate} -o {matte} --ranges <hook + splits>)")
        self.accent = accent or PAL["accent_c004"]
        self.accent45 = accent45 or PAL["accent45_c004"]
        fx = fixes or {}
        for w in self.words:
            key = w["raw"].strip(".,")
            w["show"] = w["raw"].replace(key, fx[key]) if key in fx else w["raw"]
        self.WD = self.words
        self._faces = {}
        self._face_files = faces or {self.plate: "build/face.json"}
        self.BODY, self.CSS, self.GUARD, self.CAPBOX = [], [], [], []
        self._trk = 100
        self.hook_ty, self.split_ty, self.n_pills = None, [], 0
        self.MET = self._metrics()

    # ---------------------------------------------------------------- fonts
    def _metrics(self):
        p = os.path.join(self.P, "build", "metrics.json")
        need = sorted({f"{fam}|{wt}" for fam, wt, _, _ in VOICE.values()})
        met = json.load(open(p)) if os.path.exists(p) else {}
        miss = [k for k in need if k not in met]
        if miss:
            if not os.path.exists(GHOST_PY):
                raise BuildError(f"build/metrics.json lacks {miss} and {GHOST_PY} is missing (bash scripts/setup_captions.sh)")
            subprocess.run([GHOST_PY, os.path.join(HERE, "fontwidths.py"), p, *miss], check=True)
            met = json.load(open(p))
        return met

    def tw(self, text, fam, wt, size):
        tab = self.MET[f"{fam}|{wt}"]
        return sum(tab.get(c, 560) for c in text) / 1000 * size

    def fit(self, text, voice, size, maxw):
        fam, wt = VOICE[voice][:2]
        w = self.tw(text, fam, wt, size)
        return round(size if w <= maxw else size * maxw / w, 1)

    # ---------------------------------------------------------------- the bed: facereel's ducked bed + drop-outs
    def _music(self, id, db=-20.0, duck=-8.0, start=0.0, fade_in=0.6, fade_out=1.2, drops=()):
        tag = super()._music(id, db=db, duck=duck, start=start, fade_in=fade_in, fade_out=fade_out)
        a0 = tag.index("data-automation='") + len("data-automation='")
        lane = json.loads(tag[a0:tag.index("'", a0)])
        pts = [(p["t"], p["v"]) for p in lane["lanes"][0]["points"]]

        def v(t):
            for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
                if t0 <= t <= t1:
                    return v0 + (v1 - v0) * (t - t0) / max(1e-6, t1 - t0)
            return pts[-1][1]

        def g(t):
            for a, b in drops:
                if a - 0.06 <= t <= b + 0.25:
                    return max(0.0, (a - t) / 0.06) if t < a else (0.0 if t <= b else (t - b) / 0.25)
            return 1.0
        ks = sorted({p[0] for p in pts} | {round(k, 3) for a, b in drops for k in (a - 0.06, a, b, b + 0.25)})
        new = [{"t": k, "v": round(v(k) * g(k), 4)} for k in ks if 0 <= k <= self.T]
        lane["lanes"][0]["points"] = new
        self.notes.append(f"music drop-outs {list(drops)}")
        return tag[:a0] + json.dumps(lane) + tag[tag.index("'", a0):]

    # ---------------------------------------------------------------- timeline + html primitives
    def trk(self):
        self._trk += 1
        return self._trk

    def J(self, s):
        self.js(s)

    def bset(self, sel, props):
        """a load-time gsap.set (the baseline)"""
        self.base.append(f'gsap.set({sel if sel.startswith("[") else json.dumps(sel)}, {json.dumps(props)});')

    def fromto(self, sel, frm, to, at, dur, ease="none"):
        self.J(f'tl.fromTo({json.dumps(sel)}, {json.dumps(frm)}, {json.dumps({**to, "duration": round(dur, 4), "ease": ease, "immediateRender": False})}, {max(0.0, at):.4f});')

    def tset(self, sel, props, at):
        self.J(f'tl.set({json.dumps(sel)}, {json.dumps(props)}, {max(0.0, at):.4f});')

    def lut(self, sel, keys, fn, ease="none"):
        """piecewise tweens through measured (t, value) keys; the first value is the load baseline"""
        self.bset(sel, fn(keys[0][1]))
        for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
            if v0 != v1:
                self.fromto(sel, fn(v0), fn(v1), t0, t1 - t0, ease)
            else:
                self.tset(sel, fn(v1), t1)

    def camera(self, sel, origin, start, moves):
        """the virtual camera: a baseline scale, then [(at, to, dur, ease), ...] chained"""
        self.bset(sel, {"transformOrigin": origin, "scale": start})
        cur = start
        for at, to, dur, ease in moves:
            self.fromto(sel, {"scale": cur}, {"scale": to}, at, dur, ease)
            cur = to

    def clip(self, tag, cid, t0, t1, cls="", style="", inner="", attrs="", track=None):
        tr = track if track is not None else self.trk()
        return (f'<{tag} id="{cid}" class="clip {cls}" data-start="{t0:.3f}" data-duration="{t1 - t0:.3f}" data-track-index="{tr}" '
                f'style="{style}" {attrs}>{inner}</{tag}>')

    def video(self, cid, src, t0, t1, style=""):
        return (f'<video id="{cid}" class="clip vid" src="{src}" muted playsinline data-start="{t0:.3f}" data-duration="{t1 - t0:.3f}" '
                f'data-media-start="{t0:.3f}" data-track-index="{self.trk()}" style="{style}"></video>')

    def wtimes(self, a, b, tokens):
        ws = [w for w in self.WD if a - 0.1 <= w["s"] < b]
        ok = len(ws) == len(tokens) and all(norm(t) in (w["n"], w["n2"]) for w, t in zip(ws, tokens))
        if not ok:
            raise BuildError(f"caption words {tokens} are not the words spoken in {a:.2f}-{b:.2f}: {[w['raw'] for w in ws]}")
        return [w["s"] for w in ws]

    def samples(self, plate=None):
        """face.json samples [t, top, bottom, left, right, ...] of a plate (its face file from `faces`)"""
        plate = plate or self.plate
        if plate not in self._faces:
            f = self._face_files.get(plate)
            if not f:
                raise BuildError(f"no face file for {plate}: pass faces={{'{plate}': 'build/face_<name>.json'}} (scripts/face_track.py on it)")
            self._faces[plate] = [s for s in json.load(open(os.path.join(self.P, f)))["samples"] if s[1] is not None]
        return self._faces[plate]

    def full_page(self, sid, a, b, what):
        """a full-screen page (the face off screen), capped by house budgets.page_max_s"""
        self.full_screen(sid, a, b, what, cap=BUD["page_max_s"])

    # ---------------------------------------------------------------- type (C3 page titles)
    def page_title(self, tid, t0, t1, top, a_text, a_times, b_text, b_times, z, a_size=None, b_size=None):
        """C3: tier A heavy sans rises from ~280 px below (expo.out 14.5 f) with a per-letter fade/blur (3.5 f, 0.6 f stagger);
        tier B serif italic soft L->R: letters ghost at .1 -> solid (5 f each, 0.6 f stagger) from its spoken word.
        a_times / b_times: the onset of each word of the tier. Returns the bottom of tier B."""
        a_size = a_size or GEO["title_sizes"][0]
        b_size = b_size or GEO["title_sizes"][1]
        sa = self.fit(a_text, "sans", a_size, GEO["fit_px"]["title_a"])
        sb = self.fit(b_text, "serif", b_size, GEO["fit_px"]["title_b"])
        yb = top + sa * 0.98
        html = (f'<p id="{tid}_a" class="tier" style="{tier_style("sans", sa, top, extra="letter-spacing:-1px;")}">{letters(a_text, tid + "a")}</p>'
                f'<p id="{tid}_b" class="tier" style="{tier_style("serif", sb, yb - sb * 0.12)}">{letters(b_text, tid + "b")}</p>')
        self.BODY.append(self.clip("div", tid, t0, t1, "wrap", f"z-index:{z}", html))
        self.bset(f"#{tid}_a", {"y": 280})
        self.fromto(f"#{tid}_a", {"y": 280}, {"y": 0}, a_times[0], 14.5 / REF, "expo.out")
        for cls, text, times, frm, dur in [(tid + "a", a_text, a_times, {"opacity": 0, "filter": "blur(8px)"}, 3.5 / REF),
                                           (tid + "b", b_text, b_times, {"opacity": 0.1, "filter": "blur(3px)"}, 5 / REF)]:
            T_ = []
            for wi, word in enumerate(text.split(" ")):
                T_ += [round(times[wi] + j * 0.6 / REF, 4) for j in range(len(word))]
            self.J(f'(() => {{ const els = gsap.utils.toArray(".{cls}"); const T = {json.dumps(T_)}; gsap.set(els, {json.dumps(frm)}); '
                   f'els.forEach((el, i) => tl.fromTo(el, {json.dumps(frm)}, {{opacity: 1, filter: "blur(0px)", duration: {dur:.3f}, ease: "power2.out", immediateRender: false}}, T[i])); }})();')
        return yb + sb

    # ---------------------------------------------------------------- S1 hook (C1 + C2 + C3, D1)
    def hook(self, end, card, headline, keys=None, label="file card + headline + matted face", pop="pop-1", whoosh="tech-digital-whoosh"):
        """frame 0 reads on its own: the gradient page, the plate in a rounded card with the cut-out in front (head
        breaking out of the card top under the headline), the file card (file_card()) settling, the headline
        [(text, "sans"|"serif"|"reg", size), ...] already in. Exit D1 at `end`: the card grows and fades, the footage
        washes to white, the headline cuts; start the next page at end - 0.08 so it pre-rolls behind the card."""
        fs = self.samples()
        y, hl_html = GEO["hook_headline_top"], ""
        for text, voice, size in headline:
            sz = self.fit(text, voice, size, GEO["fit_px"]["hook"])
            hl_html += (f'<p class="tier" style="{tier_style(voice, sz, y - (sz * 0.1 if voice == "serif" else 0), extra="letter-spacing:-1px;" if voice == "sans" else "")}">'
                        f'{esc(text)}</p>')
            y += sz * (0.98 if voice == "sans" else 1.0)
        hl_bottom = y + headline[-1][2] * 0.16
        ty = math.ceil(max(GEO["hook_ty_min"], hl_bottom + 20 - head_top(fs, 0, end)))
        self.GUARD.append(("hook headline vs head", hl_bottom, head_top(fs, 0, end) + ty))
        self.BODY.append(self.clip("div", "hk_page", 0, end, "wrap", f"z-index:5;background:{PAL['hook_page']}"))
        self.BODY.append(f'<div id="hk_cc" class="wrap" style="z-index:6;clip-path:{GEO["hook_card_clip"]}">'
                         + self.video("hk_v", self.plate, 0, end, f"transform:translate(0px,{ty}px)") + "</div>")
        if self.matte:
            self.BODY.append(f'<div id="hk_mt" class="wrap" style="z-index:7">' + self.video("hk_m", self.matte, 0, end, f"transform:translate(0px,{ty}px)") + "</div>")
        self.BODY.append(self.clip("div", "hk_wash", end - 0.22, end, "wrap", f"z-index:8;background:{PAGE};opacity:0"))
        self.bset("#hk_wash", {"opacity": 0})
        self.fromto("#hk_wash", {"opacity": 0}, {"opacity": 1}, end - 0.16, 4 / REF, "quad.in")
        self.BODY.append(self.clip("div", "hk_card", 0, end + 0.20, "wrap", "z-index:15", card))
        self.BODY.append(self.clip("div", "hk_head", 0, end, "wrap", "z-index:16", hl_html))
        self.bset("#hk_card", {"y": -13, "transformOrigin": "540px 367px"})
        self.fromto("#hk_card", {"y": -13}, {"y": -20}, 0.0, 0.08, "power1.out")
        self.fromto("#hk_card", {"y": -20}, {"y": 0}, 0.08, 0.36, "sine.inOut")
        self.fromto("#hk_card", {"scale": 1, "y": 0}, {"scale": 1.14, "y": 73}, end - 0.32, 11 / REF, "power2.in")
        self.fromto("#hk_card", {"opacity": 1}, {"opacity": 0}, end - 0.12, 7 / REF, "none")
        self.sound(pop, 0.0, "hook card in (C2 pop f1)", db=-4)
        self.sound(whoosh, end - 0.26, "D1 wash / card exit (soft whoosh leads 2-3 f)", db=-5)
        self.beat("hook", "hook", 0, end, label, keys or [0.0, end / 2, end - 0.22])
        self.hook_ty = ty
        return ty

    # ---------------------------------------------------------------- pages
    def art_page(self, sid, cam, t0, t1, inner, z, zoom_at=None, zoom_to=0.78, origin="499px 48px", pre=0.04):
        """a white page with a drawing (inner = place(art.svg(...), ...)); the camera runs the measured push from
        t0 + pre, then on zoom_at zooms out (power3.inOut 0.9 s) to make room for the page title. The camera starts at
        t0 (pre-roll behind the hook card)."""
        a = t0 + pre
        self.BODY.append(self.clip("div", f"{sid}_page", a, t1, "page", f"z-index:{z}"))
        self.BODY.append(self.clip("div", cam, t0, t1, "wrap", f"z-index:{z + 1}", inner))
        self.bset(f"#{cam}", {"transformOrigin": origin})
        self.lut(f"#{cam}", [(round(a + i * 0.04, 3), v) for i, v in enumerate(CAM_PUSH)], lambda v: {"scale": v})
        if zoom_at is not None:
            self.fromto(f"#{cam}", {"scale": 1.0}, {"scale": zoom_to}, zoom_at, 0.9, "power3.inOut")
        return a

    def rise_page(self, sid, cam, img, t0, t1, src, box_, z, push_at, exit_at, origin="500px 560px", radius=6,
                  insert=None, swell=("cinematic-drone-swell", -8, 1.1)):
        """C7 + C8: a real picture on a white page rises from below (expo.out 24 f), pushes to its detail x1.23 on
        push_at (expo.out 13 f, a swell 0.04 s ahead), drifts to x1.25, accelerates into the cut from exit_at (x0.87,
        power2.in). insert = (id, file, line): registers the picture for the budgets and broll_vision picks."""
        l, t, w, h = box_
        self.BODY.append(self.clip("div", f"{sid}_page", t0, t1, "page", f"z-index:{z}"))
        self.BODY.append(self.clip("div", cam, t0, t1, "wrap", f"z-index:{z + 1}",
                                   f'<img id="{img}" class="abs" src="{src}" alt="" style="left:{l}px;top:{t}px;width:{w}px;height:{h}px;border-radius:{radius}px;'
                                   f'box-shadow:{PAL["shadows"]["picture"]};">'))
        self.bset(f"#{img}", {"y": 1350})
        self.fromto(f"#{img}", {"y": 1350}, {"y": 0}, t0 + 0.03, 24 / REF, "expo.out")
        p1 = push_at + 13 / REF
        self.camera(f"#{cam}", origin, 1, [(push_at, 1.23, 13 / REF, "expo.out"), (p1, 1.25, exit_at - p1, "none"),
                                           (exit_at, 1.25 * 0.87, t1 - exit_at, "power2.in")])
        if insert:
            self.insert(insert[0], insert[1], t0, t1, insert[2], "card", insert[3] if len(insert) > 3 else "stock")
        if swell:
            self.sound(swell[0], push_at - 0.04, "push-to-detail (H f143 swell)", db=swell[1], maxlen=swell[2])

    def ui_page(self, sid, cam, t0, t1, z, inner, bg=None):
        """a rebuilt UI page (iOS grey); the UI camera zooms out x0.94 then pushes in to x1.04 (sine.inOut)"""
        self.BODY.append(self.clip("div", f"{sid}_page", t0, t1, "wrap", f"z-index:{z};background:{bg or PAL['ios_grey']}"))
        self.BODY.append(self.clip("div", cam, t0, t1, "wrap", f"z-index:{z + 1}", inner))
        self.camera(f"#{cam}", "540px 760px", 1, [(t0, 0.94, 0.62, "sine.inOut"), (t0 + 0.62, 1.04, t1 - t0 - 0.62, "sine.inOut")])

    def rows_off(self, sid, words, after=0.0, rh=RH, tick="tick-1"):
        """on each spoken word (one per row, from row 0) the accent highlight lands on its row (8 frames linear, scale
        .95 -> 1) and its toggle flips off 4 frames later, with a tick"""
        self.bset(f"#{sid}_hl", {"opacity": 0, "transformOrigin": f"504px {rh // 2}px"})
        for i, word in enumerate(words):
            t = self.t(word, after)
            self.tset(f"#{sid}_hl", {"top": i * rh}, t)
            self.fromto(f"#{sid}_hl", {"opacity": 0, "scale": 0.95}, {"opacity": 1, "scale": 1}, t, 8 / self.fps, "none")
            self.fromto(f"#kn{i}", {"x": 0}, {"x": -52}, t + 4 / self.fps, 0.2, "power2.inOut")
            self.fromto(f"#tg{i}", {"backgroundColor": self.accent}, {"backgroundColor": PAL["toggle_off"]}, t + 4 / self.fps, 0.2, "power2.inOut")
            self.sound(tick, t + 4 / self.fps, f"toggle {i} off on '{word}'", db=-4)

    def split(self, sid, t0, t1, z, panel_inner, ty=None):
        """C1/C10: the split page, the plate scaled 0.87 in a rounded card with the cut-out in front (head top under the
        pill), a white panel with panel_inner sliding in from the right (expo.out 45 f). Returns ty."""
        fs = self.samples()
        k, x = GEO["split_scale"], GEO["split_x"]
        ty = ty or math.ceil(PILL_BOTTOM + 20 - k * head_top(fs, t0, t1))
        self.GUARD.append((f"{sid} pill vs head", PILL_BOTTOM, head_top(fs, t0, t1) * k + ty))
        tf = f"transform-origin:0 0;transform:translate({x}px,{ty}px) scale({k})"
        self.BODY.append(self.clip("div", f"{sid}_page", t0, t1, "wrap", f"z-index:{z};background:{PAL['split_page']}"))
        self.BODY.append(f'<div id="{sid}_cc" class="wrap" style="z-index:{z + 1};clip-path:{GEO["split_card_clip"]}">'
                         + self.video(f"{sid}_v", self.plate, t0, t1, tf) + "</div>")
        if self.matte:
            self.BODY.append(f'<div id="{sid}_mt" class="wrap" style="z-index:{z + 2}">' + self.video(f"{sid}_m", self.matte, t0, t1, tf) + "</div>")
        self.BODY.append(self.clip("div", f"{sid}_panel", t0, t1, "abs",
                                   f"z-index:{z + 3};left:150px;top:-60px;width:1000px;height:1125px;background:{PAL['panel']};border-radius:0 0 0 64px;"
                                   f"box-shadow:{PAL['shadows']['panel']};", panel_inner))
        self.bset(f"#{sid}_panel", {"x": 1000})
        self.fromto(f"#{sid}_panel", {"x": 1000}, {"x": 0}, t0 + 0.034, 45 / REF, "expo.out")
        self.split_ty.append(ty)
        return ty

    def app_icon(self, cid, t0, t1, z, glyph, at, left=505, top=150, size=220, radius=52, color=None):
        """an app icon (rounded square in the accent, soft shadow) that drops from the top edge on `at` (expo.out 22 f)"""
        self.BODY.append(self.clip("div", cid, t0, t1, "abs",
                                   f"z-index:{z};left:{left}px;top:{top}px;width:{size}px;height:{size}px;border-radius:{radius}px;"
                                   f"background:{color or self.accent};box-shadow:{PAL['shadows']['icon']};", glyph))
        self.bset(f"#{cid}", {"y": -560})
        self.fromto(f"#{cid}", {"y": -560}, {"y": 0}, at, 22 / REF, "expo.out")

    def press(self, sel, at):
        self.tset(sel, {"backgroundColor": PAL["pressed"]}, at)

    def fade_out(self, sel, at, frames=7, scale=0.96):
        self.fromto(sel, {"opacity": 1, "scale": 1}, {"opacity": 0, "scale": scale}, at, frames / REF, "none")

    def fade_in(self, sel, at, frames=3):
        self.fromto(sel, {"opacity": 0}, {"opacity": 1}, at, frames / REF, "none")

    def draw_on(self, sels, at, length=24.4, dur=0.22):
        for s_ in sels:
            self.fromto(s_, {"attr": {"stroke-dashoffset": length}}, {"attr": {"stroke-dashoffset": 0}}, at, dur, "power2.out")

    # ---------------------------------------------------------------- face beats (C6 captions)
    def face_beat(self, fid, plate, t0, t1, push, z, phrases):
        """the plate full frame as shot with a slow linear push; phrases = [(a, b, [(tier text, voice), ...]), ...]
        (the tier words must be the words spoken in [a, b)); a cut to another plate is a reframe cut (D5)"""
        fs = self.samples(plate)
        self.BODY.append(f'<div id="{fid}" class="wrap" style="z-index:{z}">' + self.video(f"{fid}_v", plate, t0, t1)
                         + self.clip("div", f"{fid}_s", t0, t1, "wrap", PAL["scrim"]) + "".join(self.cap_html(f"{fid}c{n}", *ph) for n, ph in enumerate(phrases)) + "</div>")
        self.camera(f"#{fid}", "540px 760px", 1, [(t0, push, t1 - t0, "none")])
        cb = 760 + (core_bottom(fs, t0, t1) - 760) * push
        self.GUARD.append((f"{fid} caption vs chin", cb, GEO["caption_top"]))

    def cap_html(self, cid, a, b, tiers):
        toks = [w for text, _ in tiers for w in text.split(" ")]
        times = self.wtimes(a, b, toks)
        y, html, k = GEO["caption_top"], "", 0
        boxes = []
        for text, voice in tiers:
            sz = self.fit(text, voice, GEO["caption_sizes"][voice], GEO["fit_px"]["caption"])
            spans = []
            for w in text.split(" "):
                spans.append(f'<span class="cw" id="{cid}w{k}">{esc(w)}</span>')
                t = max(times[k] - 0.02, a - 2 / self.fps) if times[k] > a + 0.02 else a - 2 / self.fps
                sel = f"#{cid}w{k}"
                self.bset(sel, {"opacity": 0, "y": 18, "filter": "blur(6px)"})
                self.fromto(sel, {"opacity": 0, "y": 18, "filter": "blur(6px)"}, {"opacity": 1, "y": 0, "filter": "blur(0px)"}, t, 4 / REF, "power2.out")
                k += 1
            off = sz * 0.06 if voice != "sans" else 0
            wpx = self.tw(text, VOICE[voice][0], VOICE[voice][1], sz)
            boxes.append([540 - wpx / 2, y + sz * 0.12, 540 + wpx / 2, y + sz * 0.88, sz])
            html += (f'<p class="tier" style="{tier_style(voice, sz, y - off, CAPTION, "letter-spacing:-1px;" if voice == "sans" else "")}">'
                     + '<span class="sp"> </span>'.join(spans) + "</p>")
            y += sz * (0.98 if voice == "sans" else 0.92)
        self.GUARD.append((f"{cid} caption bottom vs IG UI", y + 20, FR.SAFE["bottom"]))
        self.CAPBOX.append({"id": cid, "t": round(b - 0.06, 3), "tiers": boxes})
        return self.clip("div", cid, a, b, "wrap", "", html, track=95)

    # ---------------------------------------------------------------- the whip between two drawings (C5 sequence, D2)
    def whip_pages(self, sid, t0, t1, z, inner_a, inner_b, land, cam_a, cam_b, push_from=0.78):
        """page A (pushes in from x0.78, expo.out 0.5 s) whips to page B, landing on `land` (the incoming word): one
        strip, a blank frame between, x-only motion blur. Anything that joins page B later goes in inner_b (opacity 0)."""
        self.BODY.append(self.clip("div", f"{sid}_page", t0, t1, "page", f"z-index:{z}"))
        self.BODY.append(self.clip("div", f"{sid}_wo", t0, t1, "wrap", f"z-index:{z + 1}",
                                   f'<div id="{sid}_wm" class="wrap"><div id="{sid}_wi" class="wrap">'
                                   f'<div id="{sid}_pa" class="wrap"><div id="{cam_a}" class="wrap">{inner_a}</div></div>'
                                   f'<div id="{sid}_pb" class="wrap"><div id="{cam_b}" class="wrap">{inner_b}</div></div>'
                                   '</div></div>'))
        self.camera(f"#{cam_a}", "540px 100px", push_from, [(t0 + 0.02, 1.0, 0.5, "expo.out")])
        fw = land - 0.32
        self.lut(f"#{sid}_pa", [(fw + dt, v) for dt, v in WHIP_A], lambda v: {"x": v})
        self.lut(f"#{sid}_pb", [(fw + dt, v) for dt, v in WHIP_B], lambda v: {"x": v})
        sig = [(fw + dt, v) for dt, v in WHIP_BLUR]
        self.bset(f"#{sid}_wo", {"transformOrigin": "540px 0px", "scaleX": 1})
        self.bset(f"#{sid}_wi", {"transformOrigin": "540px 0px", "scaleX": 1})
        self.bset(f"#{sid}_wm", {"filter": "none"})
        self.tset(f"#{sid}_wo", {"scaleX": KX}, sig[0][0])
        self.tset(f"#{sid}_wi", {"scaleX": 1 / KX}, sig[0][0])
        for t, sg in sig:
            self.tset(f"#{sid}_wm", {"filter": f"blur({sg / KX:.2f}px)"}, t)
        self.tset(f"#{sid}_wo", {"scaleX": 1}, fw + .32)
        self.tset(f"#{sid}_wi", {"scaleX": 1}, fw + .32)
        self.tset(f"#{sid}_wm", {"filter": "none"}, fw + .32)
        self.sound("whoosh-cine", fw + 0.24, "whip lands with the incoming page (D2: onset lags the midpoint)", db=-3)
        return fw

    # ---------------------------------------------------------------- the gallery (C13)
    def gallery(self, sid, cam, t0, t1, z, tiles, empty=()):
        """a 3-column grid of the reel's own drawings (tile()), dashed empty cells under them, a white veil #<sid>_veil
        (veil()), the camera zooming out linearly x0.9977 a reference frame for the whole shot"""
        slots = "".join(f'<div class="abs" style="left:{COLX[c]}px;top:{ROWY[r]}px;width:{TWD}px;height:{THT}px;border:2.5px dashed {PAL["empty_cell"]};'
                        f'border-radius:22px;box-sizing:border-box;"></div>' for c, r in empty)
        gal = slots + "".join(tiles) + f'<div id="{sid}_veil" class="wrap" style="background:{PAGE};opacity:0;z-index:5"></div>'
        self.BODY.append(self.clip("div", f"{sid}_page", t0, t1, "page", f"z-index:{z}"))
        self.BODY.append(self.clip("div", cam, t0, t1, "wrap", f"z-index:{z + 1}", gal))
        self.camera(f"#{cam}", "540px 900px", 1, [(t0, 0.9977 ** ((t1 - t0) * REF), t1 - t0, "none")])

    def shrink_tile(self, sel, at, cells=(2, 2)):
        """a big tile shrinks to one cell toward its bottom-left (expo.out 0.5 s) and fades, showing what is under it"""
        w, h = TWD * cells[0] + GAP * (cells[0] - 1), THT * cells[1] + GAP * (cells[1] - 1)
        self.bset(sel, {"transformOrigin": f"0px {h}px", "scale": 1})
        self.fromto(sel, {"scaleX": 1, "scaleY": 1}, {"scaleX": TWD / w, "scaleY": THT / h}, at, 0.5, "expo.out")
        self.fromto(sel, {"opacity": 1}, {"opacity": 0}, at + 0.22, 0.2, "none")

    def veil(self, sel, t_a, t_b):
        """C13: a white veil over a busy page in two ramps, one per title tier (.04 -> .27 in 10 f, -> .6 in 18 f)"""
        self.bset(sel, {"opacity": 0})
        self.fromto(sel, {"opacity": 0.04}, {"opacity": 0.27}, t_a, 10 / REF, "none")
        self.fromto(sel, {"opacity": 0.27}, {"opacity": 0.6}, t_b, 18 / REF, "none")

    # ---------------------------------------------------------------- live loops on the drawings
    def phone_hops(self, idp, t0, t1, step=0.3):
        """phone_art's black tile hops cell to cell every `step` s"""
        t, i = t0, 0
        while t < t1:
            cx, cy = PH_POS[i % len(PH_POS)]
            self.tset(f"#{idp}_act", {"attr": {"x": 30 + cx * 58, "y": 82 + cy * 68}}, t)
            self.tset(f"#{idp}_bd", {"attr": {"cx": 52 + cx * 58, "cy": 146 + cy * 68}}, t)
            t += step
            i += 1

    def loop(self, sel, t0, t1, period, a, b, ease="sine.inOut"):
        """a to b and back every `period` s (a moon bobs, a shoe rocks, steam rises)"""
        for n in range(int((t1 - t0) / period)):
            t = t0 + n * period
            self.fromto(sel, a if n % 2 == 0 else b, b if n % 2 == 0 else a, t, period, ease)

    def hop(self, sel, p0, p1, at, dur=0.3, lift=70):
        """a bead hops from p0 to p1 (offsets) on `at`"""
        (x0, y0), (x1, y1) = p0, p1
        self.fromto(sel, {"x": x0}, {"x": x1}, at, dur, "none")
        self.fromto(sel, {"y": y0}, {"y": min(y0, y1) - lift}, at, dur / 2, "power2.out")
        self.fromto(sel, {"y": min(y0, y1) - lift}, {"y": y1}, at + dur / 2, dur / 2, "power2.in")

    def falter(self, sel, p0, p1, at, frac=0.35, lift=60):
        """a hop toward p1 that falls back to p0 (the step that scares)"""
        (x3, y3), (x4, _) = p0, p1
        xm = x3 + (x4 - x3) * frac
        self.fromto(sel, {"x": x3}, {"x": xm}, at, 0.18, "power1.out")
        self.fromto(sel, {"y": y3}, {"y": y3 - lift}, at, 0.18, "power2.out")
        self.fromto(sel, {"x": xm}, {"x": x3}, at + 0.18, 0.22, "power1.in")
        self.fromto(sel, {"y": y3 - lift}, {"y": y3}, at + 0.18, 0.22, "bounce.out")

    # ---------------------------------------------------------------- the word pill (C4) + the build
    def pills(self, windows):
        """C4: inside each (a, b) window, every spoken word in the fixed pill slot, 1 frame after its onset, held to the
        next word; leave the pill out while a title or caption is up and while the words are on screen as UI text"""
        for a, b in windows:
            ws = [w for w in self.WD if a - 0.05 <= w["s"] < b]
            for i, w in enumerate(ws):
                s0 = max(a, w["s"] + 1 / self.fps)
                s1 = min(b, ws[i + 1]["s"] + 1 / self.fps) if i + 1 < len(ws) else b
                if s1 - s0 > 0.02:
                    self.BODY.append(self.clip("div", f"pl{self.n_pills}", s0, s1, "pillrow", "", f'<span class="pill">{esc(w["show"])}</span>', track=90))
                    self.n_pills += 1

    def build(self, recipe="product-page (DerovIOhToi)", fonts=FONTS, extra=None):
        """index.html, build/capboxes.json, build/sfx_events.json, beats.json, plan.json; prints the guards and the
        numbers; fails on a broken guard or budget"""
        self.CSS.append(BASE_CSS)
        body = "\n".join(self.BODY) + "\n" + "\n".join(self._audio())
        self.write_page("\n".join(self.CSS), body, list(fonts))
        json.dump(self.CAPBOX, open(os.path.join(self.P, "build", "capboxes.json"), "w"))
        m = self.write_side_files(recipe, {"hook_ty": self.hook_ty, "split_ty": self.split_ty, **(extra or {})})
        bad = []
        for what, a_, b_ in self.GUARD:
            ok = a_ + 18 <= b_ if "IG UI" not in what else a_ <= b_
            print(f"  guard {'OK ' if ok else 'BAD'} {what}: {a_:.0f} vs {b_:.0f}")
            if not ok:
                bad.append(what)
        if m["face_on_screen_pct"] < BUD["face_min_pct"]:
            bad.append(f"face on screen {m['face_on_screen_pct']} % < {BUD['face_min_pct']} % (house budgets)")
        if m["inserts_per_min"] > BUD["inserts_per_min_max"]:
            bad.append(f"{m['inserts_per_min']} inserts a minute > {BUD['inserts_per_min_max']}")
        print(f"T {self.T:.2f} s | face on screen {m['face_on_screen_pct']} % | full screen {m['full_screen_s']} s | sfx {m['sfx']} "
              f"({m['sfx_per_10s']} per 10 s) | pills {self.n_pills} | hook ty {self.hook_ty} | split ty {', '.join(map(str, self.split_ty))}")
        for x in self.notes:
            print("  " + x)
        if bad:
            raise BuildError("GUARD FAILED: " + ", ".join(bad))
        print("index.html written; next: hf.sh lint, snap.py beats, components.py check, finals.py preview (WAIT for the user's OK)")
        return m
