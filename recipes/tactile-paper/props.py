"""Tactile paper props: the paper a reel is told on, drawn per reel (nothing downloaded, nothing stored in the recipe).
Needs numpy + Pillow (+ OpenCV for ground()): run with ~/.venvs/media/bin/python.

    import sys; sys.path.insert(0, "<skill>/recipes/tactile-paper"); import props as pp
    pp.ground(f"{P}/assets/paper-texture-ground.png")             # the maroon ground (the reference's colours, seeded)
    lay = pp.essay_page(f"{P}/assets/page.jpg", TEXT, head="RUNNING HEAD", targets={"key": ["two", "words"]})
    pp.notebook_page(f"{P}/assets/notebook.jpg", ["the speaker's own words", "on that line"], blank=f"{P}/assets/blank.jpg")
    pp.ticket(f"{P}/assets/ticket.png", "TICKET", "PASSENGER TRAIN", rows, "PRICE")
    pp.photo_print(f"{P}/assets/city_prepped.jpg", f"{P}/assets/print.jpg")   # a stock / own still as a B&W print
    img = pp.paper(pp.PW, pp.PH, (226, 215, 188), seed=11)        # any page of your own; ink with apply_ink / halftone

Pages are 2x of the replica's page space (PAGE rect 1013 x 1478 page px -> PW x PH = 2026 x 2956 texture px), so a
page fills the frame width at rest and stays sharp in the 1.12x close-up. Marks come back in page px (the boxes the
crimson underline goes under). Text: the latin and cyrillic subsets of the house fonts in templates/fonts (Playfair
Display for printed pages, Caveat for handwriting, JetBrains Mono for fields, Inter Tight for headings). Only the speaker's words or
plain facts go on a page in a size a viewer can read (>= 48 px on screen); a page of printed text in another language (a
quote's source) is texture, the caption carries the meaning.
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.abspath(os.path.join(HERE, "..", "..", "templates", "fonts"))
K = 2                      # texture px per page px
PW, PH = 1013 * K, 1478 * K

# the maroon ground: a cubic colour surface (BGR, x/1080, y/1920) fitted to the reference's first frame + seeded fibre
# noise with its measured high-pass deviation (replica/tools/prep_plates.py); regenerated pixel-identical, no file kept
GROUND_COEF = [[29.00250357128763, 42.32283974297392, 127.78608262216729, -81.76655363966792, -16.252907743397955,
                -196.33617531725275, 10.695967003613482, 52.4626069709357, 32.35067716379652, 60.521884169057515],
               [18.461236344230183, 31.757105935876183, 109.73367705224551, -57.200698340610586, -42.502532025143175,
                -190.76307834963004, 7.397865545309819, 44.83399721879237, 56.479156792368016, 78.44579539693247],
               [47.21184114916305, 64.45280721459339, 194.88999157829033, -122.33271121698378, -14.204396895941427,
                -284.6390720307811, 11.057350097883095, 81.70083754090659, 39.61457596538602, 77.04030468680781]]
GROUND_SD = [4.086792945861816, 4.099277973175049, 4.08526611328125]


def ground(dst, seed=7):
    """the maroon textured ground, 1280 x 2120 (100 px margin round the frame for the camera moves)"""
    import cv2
    coef = [np.array(c) for c in GROUND_COEF]
    sd = np.array(GROUND_SD, np.float32)

    def feats(x, y):
        return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y, x ** 3, x * x * y, x * y * y, y ** 3], -1)
    Y, X = np.mgrid[-100:2020, -100:1180]
    FF = feats(X / 1080.0, Y / 1920.0)
    base = np.stack([FF @ coef[c] for c in range(3)], -1)
    rng = np.random.default_rng(seed)
    GS = X.shape
    n1 = cv2.GaussianBlur(rng.standard_normal(GS).astype(np.float32), (0, 0), 0.8)
    n2 = cv2.GaussianBlur(rng.standard_normal(GS).astype(np.float32), (0, 0), 2.5)
    fib = cv2.GaussianBlur(rng.standard_normal(GS).astype(np.float32), (0, 0), sigmaX=0.6, sigmaY=4.0)
    noise_ = n1 / n1.std() * 0.75 + n2 / n2.std() * 0.35 + fib / fib.std() * 0.35
    g = base + noise_[..., None] * (sd / 1.0)[None, None, :] * 0.8
    cv2.imwrite(dst, np.clip(g, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- text with the latin + cyrillic subset files
def font(stem, size, wght=None):
    f = ImageFont.truetype(os.path.join(FD, stem + ".woff2"), size)
    if wght is not None:
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
    return f


def is_cyr(ch):
    return "\u0400" <= ch <= "\u04ff"


def runs(text):
    out = []
    for ch in text:
        c = is_cyr(ch)
        if out and out[-1][0] == c:
            out[-1][1] += ch
        else:
            out.append([c, ch])
    return out


def mixed(draw, xy, text, fam, size, fill, wght=None, spacing=0):
    """draw text mixing the latin and cyrillic subset files; returns the end x"""
    x, y = xy
    fl, fc = font(fam + "-latin", size, wght), font(fam + "-cyrillic", size, wght)
    for c, s in runs(text):
        f = fc if c else fl
        for ch in (s if spacing else [s]):
            draw.text((x, y), ch, font=f, fill=fill)
            x += draw.textlength(ch, font=f) + spacing
    return x


def mixed_len(draw, text, fam, size, wght=None, spacing=0):
    fl, fc = font(fam + "-latin", size, wght), font(fam + "-cyrillic", size, wght)
    return sum(draw.textlength(ch, font=(fc if is_cyr(ch) else fl)) + spacing for ch in text) - (spacing if text else 0)


# ---------------------------------------------------------------- paper and ink
def noise(h, w, cell, rng):
    g = rng.random((h // cell + 3, w // cell + 3)).astype(np.float32)
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((w + 3 * cell, h + 3 * cell), Image.BICUBIC)
    return np.asarray(im, np.float32)[:h, :w] / 255.0


def paper(w, h, rgb, seed, mottle=0.05, grain=0.035, fibres=900, edge=0.10, spots=0):
    """a sheet of paper: mottle, grain, fibres, a darker edge, foxing spots"""
    rng = np.random.default_rng(seed)
    base = np.ones((h, w, 3), np.float32) * np.array(rgb, np.float32)[None, None] / 255.0
    m = (noise(h, w, 180, rng) - 0.5) * 2 * mottle + (noise(h, w, 45, rng) - 0.5) * mottle
    g = rng.normal(0, grain, (h, w)).astype(np.float32)
    g = np.asarray(Image.fromarray(((g + 0.5) * 255).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255 - 0.5
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy]) / (0.06 * min(w, h))
    e = -edge * np.exp(-d)
    lum = 1 + m + g + e
    im = (base * lum[..., None]).clip(0, 1)
    img = Image.fromarray((im * 255).astype(np.uint8))
    dr = ImageDraw.Draw(img, "RGBA")
    r = random.Random(seed)
    for _ in range(fibres):
        x, y = r.uniform(0, w), r.uniform(0, h)
        a, L = r.uniform(0, math.pi), r.uniform(6, 28)
        c = r.choice([(255, 255, 255, 40), (90, 70, 50, 26)])
        dr.line([(x, y), (x + L * math.cos(a), y + L * math.sin(a))], fill=c, width=1)
    for _ in range(spots):    # foxing
        x, y, rr = r.uniform(0, w), r.uniform(0, h), r.uniform(3, 16)
        dr.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(150, 110, 60, r.randint(14, 40)))
    return img


def ink_layer(w, h):
    return Image.new("L", (w, h), 0)


def apply_ink(img, mask, rgb, blur=0.6, rough=0.18, seed=3):
    """multiply printed ink into paper: slight spread + uneven density"""
    rng = np.random.default_rng(seed)
    m = np.asarray(mask.filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255
    dens = 1 - rough * noise(img.height, img.width, 6, rng)
    a = (m * dens).clip(0, 1)[..., None]
    base = np.asarray(img, np.float32) / 255
    ink = np.array(rgb, np.float32)[None, None] / 255
    out = base * (1 - a) + base * ink * a
    return Image.fromarray((out * 255).clip(0, 255).astype(np.uint8))


def halftone(gray, pitch=5.0 * K, blur_in=1.2, blur_out=0.8, gain=1.05):
    """a 45-degree halftone screen of a greyscale picture (PIL L): ink coverage 0..1 (newsprint photos, crowds from above)"""
    g = np.asarray(gray.filter(ImageFilter.GaussianBlur(blur_in)), np.float32) / 255
    h, w = g.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = (xx + yy) / math.sqrt(2), (xx - yy) / math.sqrt(2)
    cu, cv = (u / pitch) % 1 - 0.5, (v / pitch) % 1 - 0.5
    dist = np.sqrt(cu ** 2 + cv ** 2)
    rad = np.sqrt((1 - g).clip(0, 1) / math.pi) * gain
    inkm = (dist < rad).astype(np.float32)
    return np.asarray(Image.fromarray((inkm * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur_out)), np.float32) / 255


# ---------------------------------------------------------------- a printed page of justified text
def typeset(draw, words, f, x0, x1, y0, lead, indent, hyph, measure=None):
    """greedy justified lines with hyphenation (hyph: {"word": "syl|la|bles"}, extended as words split);
    returns ([(x, y, text, word index)], number of lines)"""
    tl = measure or (lambda s: draw.textlength(s, font=f))
    sp = tl(" ")
    toks = list(words)
    lines, cur, i = [], [], 0
    width = lambda ws: sum(tl(t) for t, _ in ws) + sp * (len(ws) - 1)  # noqa: E731
    while i < len(toks):
        t, wi = toks[i]
        avail = x1 - x0 - (indent if not lines else 0)
        if width(cur + [(t, wi)]) <= avail:
            cur.append((t, wi))
            i += 1
            continue
        parts = hyph.get(t, "").split("|") if t in hyph else []
        done = False
        for k in range(len(parts) - 1, 0, -1):
            head = "".join(parts[:k]) + "-"
            if width(cur + [(head, wi)]) <= avail:
                cur.append((head, wi))
                toks[i] = ("".join(parts[k:]), wi)
                hyph["".join(parts[k:])] = "|".join(parts[k:])
                done = True
                break
        lines.append(cur)
        cur = []
        if not done and not lines[-1]:
            lines[-1] = [(t, wi)]
            i += 1
    if cur:
        lines.append(cur)
    out = []
    for li, ln in enumerate(lines):
        xs = x0 + (indent if li == 0 else 0)
        nat = width(ln)
        gap = sp if li == len(lines) - 1 or len(ln) < 2 else sp + (x1 - xs - nat) / (len(ln) - 1)
        x = xs
        for t, wi in ln:
            out.append((x, y0 + li * lead, t, wi))
            x += tl(t) + gap
    return out, len(lines)


def essay_page(dst, text, head="", hyph=None, targets=None, rgb=(222, 213, 192), seed=21, family="playfair-display",
               size=46, head_size=24, lead=68, top=160, margin=104, indent=46, ink=(30, 26, 22)):
    """an old book / journal page: a letter-spaced running head, a rule, justified serif text (Cyrillic words use the
    cyrillic subset). targets {"key": ["word", "sequence"]} -> layout["marks"][key] = word boxes per line (page px)"""
    w, h = PW, PH
    img = paper(w, h, rgb, seed, mottle=0.04, spots=70, edge=0.16)
    mask = ink_layer(w, h)
    d = ImageDraw.Draw(mask)
    fh, fhc = font(family + "-latin", head_size * K, 500), font(family + "-cyrillic", head_size * K, 500)
    hf = lambda c: fhc if is_cyr(c) else fh  # noqa: E731
    tl = sum(d.textlength(c, font=hf(c)) + 6 * K for c in head) - 6 * K
    x = (w - tl) / 2
    for c in head:
        d.text((x, 62 * K), c, font=hf(c), fill=255)
        x += d.textlength(c, font=hf(c)) + 6 * K
    d.line([(110 * K, 112 * K), (w - 110 * K, 112 * K)], fill=200, width=2)
    fb = font(family + "-latin", size * K, 400)
    cyr = lambda s: any(is_cyr(c) for c in s)  # noqa: E731
    meas = lambda s: mixed_len(d, s, family, size * K, 400) if cyr(s) else d.textlength(s, font=fb)  # noqa: E731
    words = [(t, i) for i, t in enumerate(text.split())]
    boxes, nl = typeset(d, words, fb, margin * K, w - margin * K, top * K, lead * K, indent * K, dict(hyph or {}), meas)
    for x, y, t, wi in boxes:
        if cyr(t):
            mixed(d, (x, y), t, family, size * K, 255, 400)
        else:
            d.text((x, y), t, font=fb, fill=255)
    img = apply_ink(img, mask, ink, blur=0.7)
    asc = fb.getbbox("Hg")
    tw = text.split()
    marks = {}
    for k, seq in (targets or {}).items():
        for j in range(len(tw) - len(seq) + 1):
            if tw[j:j + len(seq)] == seq:
                idx = set(range(j, j + len(seq)))
                bs = [(x, y, t) for x, y, t, wi in boxes if wi in idx]
                rows = {}
                for x, y, t in bs:
                    rows.setdefault(y, []).append((x, x + meas(t)))
                marks[k] = [[min(a for a, _ in v) / K, (y + asc[1]) / K, max(b for _, b in v) / K, (y + asc[3]) / K] for y, v in sorted(rows.items())]
                break
    img.save(dst, quality=90)
    return {"lines": nl, "marks": marks, "text_top": top, "lead": lead}


# ---------------------------------------------------------------- a school notebook page (grid) + its blank twin
def grid_page(seed):
    w, h = PW, PH
    img = paper(w, h, (243, 241, 233), seed, mottle=0.025, grain=0.02, fibres=500, edge=0.06)
    d = ImageDraw.Draw(img, "RGBA")
    cell = 34 * K
    for x in range(int(28 * K), w, cell):
        d.line([(x, 0), (x, h)], fill=(120, 150, 185, 120), width=2)
    for y in range(int(30 * K), h, cell):
        d.line([(0, y), (w, y)], fill=(120, 150, 185, 120), width=2)
    d.line([(w - 92 * K, 0), (w - 92 * K, h)], fill=(214, 92, 96, 200), width=3)
    return img, cell


def notebook_page(dst, lines, blank=None, seed=41, hand_seed=9, size=76, ink=(34, 62, 150)):
    """the speaker's own words of that line handwritten (Caveat 600) in blue ink on grid paper, baselines on the grid 3 cells
    apart; `blank` also writes the same page empty (the new page a turn reveals). size >= 48 px on screen at scale 1"""
    img, cell = grid_page(seed)
    if blank:
        img.save(blank, quality=90)
    w, h = img.size
    sz = size * K
    lay = Image.new("L", (w, h), 0)
    r = random.Random(hand_seed)
    y = 30 * K + cell * 5 - sz * 0.78
    for i, ln in enumerate(lines):
        strip = Image.new("L", (w, int(sz * 1.8)), 0)
        sd = ImageDraw.Draw(strip)
        x = 96 * K + r.uniform(-6, 18) * K + (24 * K if i % 2 else 0)
        for word in ln.split(" "):
            dy = r.uniform(-4, 4) * K
            x = mixed(sd, (x, sz * 0.25 + dy), word, "caveat", int(sz * r.uniform(0.97, 1.04)), 255, 600)
            x += r.uniform(18, 30) * K
        strip = strip.rotate(r.uniform(-1.6, 1.2), resample=Image.BICUBIC, center=(96 * K, sz * 0.9))
        lay.paste(strip, (0, int(y - sz * 0.25)), strip)
        y += cell * 3
    img = apply_ink(img, lay, ink, blur=0.8, rough=0.3)
    img.save(dst, quality=90)
    return {"lines": list(lines), "size_page_px": sz / K}


# ---------------------------------------------------------------- a ticket / stub card
def ticket(dst, title, sub, rows, stub, seed=51, size=(1640, 780)):
    """a ticket on guilloche paper: a title, a sub line, field rows [(label, value, x, y)], a stub with `stub` over a
    punched-out field, perforation; returns {"size", "stub": its box in card px} (circle the stub word with ellipse())"""
    w, h = size
    card = paper(w, h, (226, 230, 212), seed, mottle=0.03, grain=0.025, fibres=300, edge=0.08)
    d = ImageDraw.Draw(card, "RGBA")
    for k in range(0, 60):
        pts = [(x, 60 + k * 11 + 18 * math.sin(x / 47.0 + k * 0.4)) for x in range(0, w, 6)]
        d.line(pts, fill=(120, 150, 120, 46), width=2)
    d.rectangle([30, 30, w - 30, h - 30], outline=(70, 90, 70, 255), width=4)
    d.line([(1180, 30), (1180, h - 30)], fill=(70, 90, 70, 200), width=3)
    ink = (28, 30, 26, 255)
    mixed(d, (70, 60), title, "inter-tight", 118, ink, 700)
    mixed(d, (74, 196), sub, "jetbrains-mono", 40, (60, 70, 60, 255))
    for lab, val, x, y in rows:
        mixed(d, (x, y), lab, "jetbrains-mono", 34, (70, 80, 70, 255))
        mixed(d, (x, y + 46), val, "jetbrains-mono", 84, ink)
    mixed(d, (1236, 270), stub, "inter-tight", 100, ink, 700)
    d.rectangle([1236, 420, 1580, 570], outline=(70, 90, 70, 255), width=3)
    alpha = Image.new("L", (w, h), 0)
    ImageDraw.Draw(alpha).rounded_rectangle([0, 0, w - 1, h - 1], radius=26, fill=255)
    ad = ImageDraw.Draw(alpha)
    ad.ellipse([1360, 447, 1456, 543], fill=0)                        # punched hole
    for y in range(40, h - 30, 36):                                    # perforation at the stub line
        ad.ellipse([1172, y, 1188, y + 16], fill=0)
    card.putalpha(alpha)
    card.save(dst)
    return {"size": [w, h], "stub": [1222, 270, 1594, 580]}


# ---------------------------------------------------------------- a B&W photo print (a stock / own still)
def photo_print(src, dst, width=1500, border=54, seed=61):
    """the still (already through insert_prep.py) as a black-and-white print with a paper border"""
    im = Image.open(src).convert("L")
    tw = width
    im = im.resize((tw, int(im.height * tw / im.width)), Image.LANCZOS)
    g = np.asarray(im, np.float32) / 255
    g = ((g - 0.5) * 1.15 + 0.52).clip(0, 1) ** 0.95
    b = border
    w, h = tw + 2 * b, im.height + 2 * b + 30
    card = paper(w, h, (236, 233, 224), seed, mottle=0.02, grain=0.02, fibres=200, edge=0.05)
    arr = np.asarray(card, np.float32)
    tone = np.stack([g * 238 + 6, g * 234 + 8, g * 224 + 12], -1)
    arr[b:b + im.height, b:b + tw] = tone
    Image.fromarray(arr.clip(0, 255).astype(np.uint8)).save(dst, quality=90)
    return {"size": [w, h]}
