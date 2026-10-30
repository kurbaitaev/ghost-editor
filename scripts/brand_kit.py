#!/usr/bin/env python3
"""A brand kit for the named tool, app or company a reel talks about, pulled from its own website (idea from Kino's
"brand matching", kino.ai/docs/brand-matching): the real logo and app icon, the brand colour, the
nearest Google font WITH Cyrillic, and the site's product shots, so the cards look like the thing at a glance.

    brand_kit.py pull URL --dir $P/brand [--name "Figma"] [--slug figma] [--no-shots]
    brand_kit.py show $P/brand                     # the kit in one screen + how to use it in a reel
    brand_kit.py sheet $P/brand                    # rebuild brand/sheet.jpg (logos on light + dark, colours, font, shots)

What lands in $P/brand/:
  kit.json        name, url, accent (+ accent_on_white for text on #FDFDFD pages, contrast >= 3:1), palette, ink,
                  logo / logo_white / logo_black / icon files, font {site, google, cyrillic, css}, shots [{file, w, h,
                  people, source}] and where each value came from (accent_source, logo_source)
  logo.*          the main logo as the site serves it (Gemini picks it among every candidate on the page);
                  logo_white.* / logo_black.* one-colour versions for dark and light grounds (SVG, or PNG with alpha)
  icon.*          the app icon (apple-touch-icon / manifest icon / simple-icons)
  fonts/          woff2 files (latin + cyrillic, 400 / 600 / 800) + fonts.css with relative urls
  shots/          og:image and large page pictures, each people-checked (broll_vision.py check); FAILs go to shots/rejected/
  sheet.jpg       one look at all of it. LOOK at it before a card uses the kit.

Order of trust: the accent comes from simple-icons' official hex, else a --brand/--primary CSS variable, else the
logo's own colour, else theme-color, else the commonest saturated CSS colour. A licensed site font (Söhne, Circular,
SF Pro...) maps to the nearest Google font that has Cyrillic (so Russian captions keep the look); the site's own name is kept.
Product shots follow the B-roll people rules like any picture: a FAIL never reaches a card. Logos are the brand's own
marks, shown to name the thing being reviewed (references/broll.md 3).

In a reel: product-page accent=kit["accent_on_white"]; a reel.json logo chip "src": "brand/logo.svg"; fonts.css next to
the composition's own fonts; shots go through insert_prep.py like any other picture.
"""
import argparse, collections, colorsys, html, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.expanduser("~/.venvs/media/bin/python")
try:
    import requests
    from PIL import Image, ImageDraw, ImageFont
except ImportError:                                           # PIL + google-genai may live in the media venv (~/.venvs/media)
    if os.path.exists(MEDIA) and os.path.realpath(sys.executable) != os.path.realpath(MEDIA):
        os.execv(MEDIA, [MEDIA] + sys.argv)
    sys.exit("needs requests + pillow + google-genai (MEDIA_PY or ~/.venvs/media)")
sys.path.insert(0, HERE)
import image_sources as I  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MODEL = os.environ.get("BRAND_KIT_MODEL", "gemini-2.5-flash")
CACHE = os.path.expanduser("~/.cache/brand_kit")
PAGE_BG = "#FDFDFD"                                           # product-page white (recipes/product-page/house.json)
GENERIC = {"sans-serif", "serif", "monospace", "system-ui", "-apple-system", "blinkmacsystemfont", "ui-sans-serif",
           "ui-serif", "ui-monospace", "inherit", "initial", "unset", "segoe ui", "apple color emoji",
           "segoe ui emoji", "segoe ui symbol", "noto color emoji", "emoji", "math", "cursive", "fantasy"}
# licensed site fonts -> the nearest Google font with Cyrillic (substring of the lower-cased family name)
NEAREST = [(("mono", "menlo", "consolas", "courier"), "JetBrains Mono"),
           (("tiempos", "times", "georgia", "sectra", "canela", "editorial new", "freight", "lyon", "publico",
             "serif"), "PT Serif"),
           (("gt america", "founders grotesk", "diatype", "neue montreal", "pp neue"), "Inter Tight"),
           (("circular", "walsheim", "cereal", "airbnb", "manrope"), "Manrope"),
           (("avenir", "proxima", "gotham", "montserrat", "nunito"), "Montserrat"),
           (("gilroy", "cera", "sofia", "tt norms", "tt commons", "satoshi", "general sans", "geist"), "Onest"),
           (("futura", "eurostile", "jost"), "Jost")]
DEFAULT_FONT = "Inter"
S = requests.Session()
S.headers["User-Agent"] = UA


# ---------- fetching ----------
def get(url, binary=False, timeout=20):
    try:
        r = S.get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.content if binary else r.text
    except requests.RequestException:
        return None


def absu(base, u):
    u = html.unescape((u or "").strip())
    return urllib.parse.urljoin(base, u) if u and not u.startswith("data:") else None


def attrs(tag):
    return {k.lower(): v for k, v in re.findall(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']', tag)}


def tags(page, name):
    return [attrs(m) for m in re.findall(rf"<{name}\b[^>]*>", page, re.I)]


def largest_src(a, base):
    best, bw = absu(base, a.get("src")), int(re.sub(r"\D", "", a.get("width", "") or "0") or 0)
    for part in (a.get("srcset") or "").split(","):
        bits = part.strip().split()
        if len(bits) == 2 and bits[1].endswith("w") and bits[1][:-1].isdigit() and int(bits[1][:-1]) > bw:
            best, bw = absu(base, bits[0]), int(bits[1][:-1])
    return best, bw


def ext_of(url, data):
    if data[:5] == b"<?xml" or b"<svg" in data[:600]:
        return ".svg"
    for magic, e in ((b"\x89PNG", ".png"), (b"\xff\xd8", ".jpg"), (b"RIFF", ".webp"), (b"GIF8", ".gif")):
        if data.startswith(magic):
            return e
    if data[4:12] in (b"ftypavif", b"ftypheic"):
        return ".avif"
    return os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() or ".bin"


def save(data, stem, url=""):
    e = ext_of(url, data)
    open(stem + e, "wb").write(data)
    return stem + e


# ---------- colours ----------
def hex6(c):
    c = c.strip().lower()
    m = re.match(r"#([0-9a-f]{3,8})$", c)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h[:3])
        return "#" + h[:6] if len(h) >= 6 else None
    m = re.match(r"rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)", c)
    if m:
        return "#%02x%02x%02x" % tuple(min(255, int(x)) for x in m.groups())
    return None


def hls(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


def chromatic(h):
    hh, ll, ss = hls(h)
    return ss > 0.3 and 0.18 < ll < 0.82


def lum(h):
    def ch(v):
        v = int(v, 16) / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(h[1:3]) + 0.7152 * ch(h[3:5]) + 0.0722 * ch(h[5:7])


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def darken_to(h, bg, ratio=3.0):
    hh, ll, ss = hls(h)
    while contrast(h, bg) < ratio and ll > 0.05:
        ll -= 0.02
        h = "#%02x%02x%02x" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(hh, ll, ss))
    return h


def raster_colours(f):
    try:
        im = Image.open(f).convert("RGBA")
    except Exception:
        return []
    im.thumbnail((200, 200))
    cnt, px = collections.Counter(), im.tobytes()
    for i in range(0, len(px), 4):
        r, g, b, a = px[i:i + 4]
        if a > 200:
            h = "#%02x%02x%02x" % (r // 16 * 16, g // 16 * 16, b // 16 * 16)
            cnt[h] += 1
    return [h for h, _ in cnt.most_common(40) if chromatic(h)]


def distinct(cols, gap=48):
    out = []
    for c in cols:
        rgb = [int(c[i:i + 2], 16) for i in (1, 3, 5)]
        if all(sum(abs(x - y) for x, y in zip(rgb, [int(o[i:i + 2], 16) for i in (1, 3, 5)])) >= gap for o in out):
            out.append(c)
    return out


def tone(png, ground=(0x8a, 0x8a, 0x8a)):
    """light / dark / colour: the logo's ink as rendered on the grey test ground"""
    im = Image.open(png).convert("RGB")
    im.thumbnail((320, 160))
    px, ls, sat = im.tobytes(), [], 0
    for i in range(0, len(px), 3):
        r, g, b = px[i:i + 3]
        if abs(r - ground[0]) + abs(g - ground[1]) + abs(b - ground[2]) > 60:
            h, l, s_ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            ls.append(l)
            sat += s_ > 0.35 and 0.15 < l < 0.85
    if not ls:
        return "unknown"
    if sat > 0.25 * len(ls):
        return "colour"
    return "light" if sum(ls) / len(ls) > 0.54 else "dark"


def svg_colours(text):
    found = re.findall(r'(?:fill|stroke|stop-color|color)\s*[:=]\s*["\']?\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))', text)
    return [h for h in (hex6(c) for c in found) if h and chromatic(h)]


# ---------- fonts ----------
def clean_family(f):
    f = f.strip().strip("'\"").strip()
    m = re.match(r"^__(.+?)_[0-9a-f]{5,8}$", f)                 # next/font: __Inter_d65c78
    if m:
        f = m.group(1).replace("_", " ")
    if (not f or re.search(r"fallback", f, re.I) or f.lower() in GENERIC or f.startswith("var(")
            or not re.match(r"[A-Za-z]", f) or re.search(r"\d(px|rem|em|%)|^(normal|bold|italic)$", f)
            or re.search(r"\b(arabic|hebrew|jp|kr|sc|tc|hk|thai|devanagari|bengali|emoji|symbols?|math)\b", f, re.I)):
        return None
    return f


def site_fonts(css):
    cnt = collections.Counter()
    for decl in re.findall(r"font-family\s*:\s*([^;}]+)", css, re.I):
        first = next((x for x in (clean_family(p) for p in decl.split(",")) if x), None)
        if first:
            cnt[first] += 1
    for decl in re.findall(r"--[\w-]*(?:family|font-(?:sans|serif|display|heading|body|primary|text|title|brand))"
                           r"[\w-]*\s*:\s*([^;}]+)", css, re.I):
        first = next((x for x in (clean_family(p) for p in decl.split(",")) if x), None)
        if first:
            cnt[first] += 2
    loaded = {clean_family(f) for f in re.findall(r"@font-face\s*{[^}]*font-family\s*:\s*([^;}]+)", css, re.I)}
    return sorted((f for f, _ in cnt.most_common(8)), key=lambda f: f not in loaded)   # web fonts the site loads first


def google_css(family, weights="400;600;800"):
    q = urllib.parse.quote_plus(family)
    for w in (f":wght@{weights}", ""):
        t = get(f"https://fonts.googleapis.com/css2?family={q}{w}&display=swap")
        if t and "@font-face" in t:
            return t
    return None


def nearest(site):
    low = (site or "").lower()
    for keys, g in NEAREST:
        if any(k in low for k in keys):
            return g
    return DEFAULT_FONT


def pick_font(families):
    """(site family, google family, cyrillic?, css, reason)"""
    for fam in families[:4]:
        css = google_css(fam)
        if css and "/* cyrillic */" in css:
            return fam, fam, True, css, "the site's own font is on Google Fonts with Cyrillic"
        if css:
            g = nearest(fam)
            css2 = google_css(g)
            if css2:
                return fam, g, "/* cyrillic */" in css2, css2, f"{fam} is on Google Fonts but has no Cyrillic -> nearest {g}"
    site = families[0] if families else None
    g = nearest(site)
    css = google_css(g)
    why = f"{site} is not a Google font -> nearest {g}" if site else f"no site font found -> {g}"
    return site, g, bool(css and "/* cyrillic */" in css), css, why


def download_fonts(css, family, out):
    os.makedirs(out, exist_ok=True)
    faces = []
    for subset, block in re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*{[^}]+})", css):
        if subset not in ("latin", "cyrillic", "latin-ext", "cyrillic-ext"):
            continue
        url = re.search(r"url\((https://[^)]+)\)\s*format\(['\"]woff2", block)
        wt = re.search(r"font-weight:\s*([\d ]+);", block)
        st = re.search(r"font-style:\s*(\w+);", block)
        ur = re.search(r"unicode-range:\s*([^;]+);", block)
        if not url:
            continue
        w = (wt.group(1).strip() if wt else "400").replace(" ", "-")
        name = f"{family.replace(' ', '')}-{w}-{subset}.woff2"
        data = get(url.group(1), binary=True)
        if not data:
            continue
        open(os.path.join(out, name), "wb").write(data)
        faces.append(f"@font-face {{ font-family: '{family}'; font-style: {st.group(1) if st else 'normal'}; "
                     f"font-weight: {wt.group(1).strip() if wt else '400'}; font-display: block; "
                     f"src: url('{name}') format('woff2'); unicode-range: {ur.group(1).strip() if ur else 'U+0-FFFF'}; }}")
    if faces:
        open(os.path.join(out, "fonts.css"), "w").write("\n".join(faces) + "\n")
    return len(faces)


# ---------- simple-icons ----------
def simple_icons():
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, "simple-icons.json")
    if not os.path.exists(f) or time.time() - os.path.getmtime(f) > 7 * 86400:
        for path in ("data/simple-icons.json", "_data/simple-icons.json"):
            t = get(f"https://cdn.jsdelivr.net/npm/simple-icons@latest/{path}")
            if t:
                open(f, "w").write(t)
                break
    try:
        d = json.load(open(f))
    except Exception:
        return []
    return d.get("icons", d) if isinstance(d, dict) else d


def si_slug(title):
    t = title.lower().replace("+", "plus").replace(".", "dot").replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", t)


def find_si(name, slug=None):
    want = (slug or si_slug(name or "")).lower()
    for ic in simple_icons():
        s = ic.get("slug") or si_slug(ic.get("title", ""))
        if s == want or ic.get("title", "").lower() == (name or "").lower():
            return {"title": ic.get("title"), "slug": s, "hex": "#" + ic["hex"].lower()}
    return None


# ---------- rendering (Chrome headless; no rsvg / cairo needed) ----------
def render(src, png, w=640, h=320, bg="#8a8a8a"):
    """any image (svg included) contained in a w x h box on bg -> png"""
    with tempfile.TemporaryDirectory() as td:
        page = os.path.join(td, "r.html")
        local = os.path.join(td, os.path.basename(src))
        shutil.copy(src, local)
        open(page, "w").write(f'<html><body style="margin:0;background:{bg};width:{w}px;height:{h}px;display:flex;'
                              f'align-items:center;justify-content:center"><img src="{os.path.basename(src)}" '
                              f'style="max-width:{w - 40}px;max-height:{h - 40}px;width:auto;height:auto;min-width:40px"></body></html>')
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
                        f"--screenshot={os.path.abspath(png)}", "file://" + page],
                       capture_output=True, timeout=60)
    return os.path.exists(png)


def mono(src, dst_stem, colour):
    """a one-colour version: svg -> every fill/stroke in the colour; png with alpha -> alpha kept, rgb = colour"""
    if src.endswith(".svg"):
        t = open(src, encoding="utf-8", errors="ignore").read()
        t = re.sub(r"(<svg\b[^>]*>)", r'\1<style>*{fill:%s !important;stroke:%s !important}</style>' % (colour, colour),
                   t, count=1)
        t = re.sub(r'(fill|stroke)="none"', r'\1="none" style="\1:none !important"', t)
        open(dst_stem + ".svg", "w").write(t)
        return dst_stem + ".svg"
    try:
        im = Image.open(src).convert("RGBA")
    except Exception:
        return None
    a = im.getchannel("A")
    if a.getextrema()[0] == 255:                              # no transparency: a one-colour version would be a box
        return None
    rgb = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    out = Image.new("RGBA", im.size, rgb + (0,))
    out.putalpha(a)
    out.save(dst_stem + ".png")
    return dst_stem + ".png"


# ---------- Gemini: which candidate is the logo ----------
def gem_pick(name, cands, renders):
    from google import genai
    from google.genai import types
    key = I.gemini_key()
    if not key:
        return None, "no GEMINI_API_KEY: first logo candidate kept, unchecked"
    cl = genai.Client(api_key=key)
    parts = [f"These are {len(renders)} images found on the website of «{name}». Each sits on a grey test ground. "
             "Pick the brand's MAIN logo (the wordmark or full lockup used in the site header; a symbol-only mark only "
             "if there is no wordmark) and its app icon (square symbol). Reject logos of OTHER companies (customer "
             "logos, partners, badges, payment or app-store marks), illustrations, avatars and UI icons. Answer with "
             "the 0-based indexes, -1 when none fits."]
    for i, r in enumerate(renders):
        parts += [f"Image {i}: {cands[i]['kind']}", types.Part.from_bytes(data=open(r, "rb").read(), mime_type="image/png")]
    schema = {"type": "object", "properties": {"logo": {"type": "integer"}, "icon": {"type": "integer"},
                                                "wordmark_text": {"type": "string"}, "reason": {"type": "string"}},
              "required": ["logo", "icon", "reason"]}
    for attempt in range(3):
        try:
            r = cl.models.generate_content(model=MODEL, contents=parts, config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json", response_schema=schema))
            return json.loads(r.text), None
        except Exception as e:
            if attempt == 2:
                return None, f"Gemini failed ({str(e)[:80]}): first logo candidate kept, unchecked"
            time.sleep(2)


# ---------- pull ----------
def cmd_pull(a):
    url = a.url if a.url.startswith("http") else "https://" + a.url
    out = os.path.abspath(a.dir)
    os.makedirs(os.path.join(out, "cand"), exist_ok=True)
    base, page = url, None
    try:
        r = S.get(url, timeout=25)
        r.raise_for_status()
        base, page = r.url, r.text
    except requests.RequestException as e:
        c = subprocess.run(["curl", "-sL", "--compressed", "-A", UA, "-H", "Accept: text/html,application/xhtml+xml",
                            "-H", "Accept-Language: en-US,en;q=0.9", "-w", "\n%{http_code} %{url_effective}", url],
                           capture_output=True, text=True)
        body, _, tail = c.stdout.rpartition("\n")
        if tail.startswith("200"):
            base, page = tail.split(" ", 1)[1], body
        else:
            print(f"  {url} refuses scripts ({e.__class__.__name__}: {str(e)[:60]}); kit from simple-icons only")
            page = ""
    open(os.path.join(out, "page.html"), "w").write(page)
    metas = {(m.get("property") or m.get("name") or "").lower(): m.get("content", "") for m in tags(page, "meta")}
    title = re.search(r"<title[^>]*>([^<]+)", page, re.I)
    name = a.name or metas.get("og:site_name") or (re.split(r"\s[|\-–—:·]\s", html.unescape(title.group(1)).strip())[0]
                                                    if title else urllib.parse.urlparse(base).netloc)
    print(f"{name}  ({base})")

    # candidates: header logos (img / inline svg), icons, manifest icons, simple-icons
    cands, seen = [], set()

    def add(kind, src_url=None, data=None):
        if src_url and src_url in seen:
            return
        if src_url:
            seen.add(src_url)
            data = get(src_url, binary=True)
        if not data or len(data) < 120:
            return
        f = save(data, os.path.join(out, "cand", f"c{len(cands):02d}"), src_url or "")
        if f.endswith((".bin", ".avif")):
            return
        cands.append({"kind": kind, "file": f, "source": src_url or "inline svg"})

    nm = (name or "").lower()
    for img in tags(page, "img"):
        blob = " ".join(img.get(k, "") for k in ("src", "alt", "class", "id")).lower()
        if ("logo" in blob or (nm and img.get("alt", "").lower().strip() == nm)) and len(cands) < 10:
            src, _ = largest_src(img, base)
            if src:
                add("img with 'logo'", src)
    for m in re.finditer(r"<svg\b[^>]*>.*?</svg>", page, re.S | re.I):
        ctx = page[max(0, m.start() - 400):m.start() + 300].lower()
        home = re.search(r'<a\b[^>]*href=["\'](/|/[a-z]{2}(-[a-z]{2})?/?|%s)["\'][^>]*>\s*(<[^>]+>\s*){0,3}$'
                         % re.escape(base), page[max(0, m.start() - 400):m.start()], re.I)
        named = nm and re.search(r'(aria-label|title)=["\'][^"\']*%s' % re.escape(nm), ctx)
        if ("logo" in ctx or home or named) and len(m.group(0)) < 80000 and len(cands) < 16:
            svg = m.group(0)
            if "xmlns" not in svg[:200]:
                svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            add("inline svg near 'logo'", data=svg.encode())
    links = tags(page, "link")
    for ln in links:
        rel = ln.get("rel", "").lower()
        if "apple-touch-icon" in rel or ("icon" in rel and (ln.get("type", "").endswith("svg") or
                                                           re.search(r"(192|256|512)", ln.get("sizes", "")))):
            add(f"site icon ({rel})", absu(base, ln.get("href")))
        if "manifest" in rel:
            mt = get(absu(base, ln.get("href")) or "")
            try:
                icons = json.loads(mt or "{}").get("icons", [])
                big = max(icons, key=lambda i: int((i.get("sizes", "0x0").split("x") + ["0"])[0] or 0)) if icons else None
                if big:
                    add("manifest icon", absu(absu(base, ln.get("href")), big.get("src")))
            except (ValueError, TypeError):
                pass
    si = find_si(name, a.slug)
    if si:
        add(f"simple-icons '{si['slug']}' (official mark, one colour)",
            f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{si['slug']}.svg")
    print(f"  {len(cands)} logo/icon candidates" + (f"; simple-icons {si['slug']} {si['hex']}" if si else "; not in simple-icons"))

    # Gemini picks the logo and the icon
    rdir = os.path.join(out, "cand", "renders")
    os.makedirs(rdir, exist_ok=True)
    keep, renders = [], []
    for c in cands:
        png = os.path.join(rdir, os.path.basename(c["file"]) + ".png")
        if render(c["file"], png):
            keep.append(c)
            renders.append(png)
    cands = keep
    pick, note = (gem_pick(name, cands, renders) if cands else (None, "no logo candidates on the page"))
    note = note or ""
    li = pick["logo"] if pick and 0 <= pick.get("logo", -1) < len(cands) else (0 if cands and not pick else -1)
    if li < 0:                                                # no wordmark on the page: the official one-colour mark
        li = next((i for i, c in enumerate(cands) if c["kind"].startswith("simple-icons")), -1)
        if li >= 0:
            note = "no wordmark on the page: simple-icons mark used"
    ii = pick["icon"] if pick and 0 <= pick.get("icon", -1) < len(cands) else -1
    kit = {"name": name, "url": base, "fetched": time.strftime("%Y-%m-%d %H:%M"), "candidates": [
        {"file": os.path.relpath(c["file"], out), "kind": c["kind"], "source": c["source"]} for c in cands],
        "logo_pick": pick or {"note": note}}
    if li >= 0:
        lf = cands[li]["file"]
        dst = os.path.join(out, "logo" + os.path.splitext(lf)[1])
        shutil.copy(lf, dst)
        kit["logo"] = os.path.basename(dst)
        kit["logo_source"] = cands[li]["source"]
        kit["logo_tone"] = tone(renders[li])
        for colour, nm in (("#FFFFFF", "logo_white"), ("#0F0E0E", "logo_black")):
            m = mono(dst, os.path.join(out, nm), colour)
            if m:
                kit[nm] = os.path.basename(m)
        t = kit["logo_tone"]                                  # which file to put on a white page / a dark card
        kit["logo_on_white"] = kit["logo"] if t in ("dark", "colour") else kit.get("logo_black", kit["logo"])
        kit["logo_on_dark"] = kit["logo"] if t in ("light", "colour") else kit.get("logo_white", kit["logo"])
    if ii >= 0:
        dst = os.path.join(out, "icon" + os.path.splitext(cands[ii]["file"])[1])
        shutil.copy(cands[ii]["file"], dst)
        kit["icon"] = os.path.basename(dst)
    print(f"  logo: {kit.get('logo', 'NONE')}  icon: {kit.get('icon', 'none')}  ({note or (pick or {}).get('reason', '')})")

    # colours + fonts from the CSS
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", page, re.S | re.I))
    sheets = [absu(base, ln.get("href")) for ln in links if "stylesheet" in ln.get("rel", "").lower()]
    for s in [x for x in sheets if x][:8]:
        css += "\n" + (get(s) or "")
    css += "\n" + " ".join(re.findall(r'style="([^"]*)"', page))
    allc = collections.Counter(h for h in (hex6(c) for c in re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", css)) if h)
    chrom = [h for h, _ in allc.most_common(200) if chromatic(h)]
    brandvar = [hex6(v) for _, _, v in re.findall(
        r"--([\w-]*(brand|primary|accent)[\w-]*)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))", css, re.I)]
    brandvar = [h for h in brandvar if h and chromatic(h)]
    logo_c = []
    if kit.get("logo"):
        lp = os.path.join(out, kit["logo"])
        logo_c = svg_colours(open(lp, errors="ignore").read()) if lp.endswith(".svg") else raster_colours(lp)
        if not logo_c and kit.get("icon"):
            ip = os.path.join(out, kit["icon"])
            logo_c = svg_colours(open(ip, errors="ignore").read()) if ip.endswith(".svg") else raster_colours(ip)
    theme = hex6(metas.get("theme-color", "") or "")
    order = [(si["hex"] if si and chromatic(si["hex"]) else None, "simple-icons official hex"),
             (brandvar[0] if brandvar else None, "a --brand/--primary/--accent CSS variable"),
             (logo_c[0] if logo_c else None, "the logo's own colour"),
             (theme if theme and chromatic(theme) else None, "the page's theme-color"),
             (chrom[0] if chrom else None, "the commonest saturated CSS colour")]
    accent, src = next(((c, s) for c, s in order if c), ("#0F0E0E", "nothing saturated found: ink"))
    darks = [h for h, _ in allc.most_common(60) if hls(h)[1] < 0.2]
    palette = distinct(list(dict.fromkeys([accent] + logo_c[:3] + brandvar[:2] + chrom[:12])))[:6]
    kit.update({"accent": accent, "accent_source": src, "accent_on_white": darken_to(accent, PAGE_BG),
                "palette": palette, "ink": darks[0] if darks else "#0F0E0E", "theme_color": theme})
    print(f"  accent {accent} ({src}); on white {kit['accent_on_white']}; palette {' '.join(palette)}")

    fams = site_fonts(css)
    site, g, cyr, gcss, why = pick_font(fams)
    n = download_fonts(gcss, g, os.path.join(out, "fonts")) if gcss else 0
    kit["font"] = {"site": site, "site_all": fams[:5], "google": g, "cyrillic": cyr, "css": "fonts/fonts.css" if n else None,
                   "files": n, "reason": why}
    print(f"  font: site {site or '?'} -> {g}{' (Cyrillic)' if cyr else ' (NO Cyrillic)'}; {n} woff2 files")

    # product shots: og / twitter image + big page pictures, people-checked
    shots = []
    if not a.no_shots:
        sd, rej = os.path.join(out, "shots"), os.path.join(out, "shots", "rejected")
        os.makedirs(rej, exist_ok=True)
        urls = [(absu(base, metas.get(k)), k) for k in ("og:image", "twitter:image") if metas.get(k)]
        for img in tags(page, "img"):
            blob = " ".join(img.get(k, "") for k in ("src", "alt", "class", "id")).lower()
            src, w = largest_src(img, base)
            if src and w >= 800 and "logo" not in blob and "avatar" not in blob:
                urls.append((src, "page picture"))
        got = set()
        for u, kind in urls:
            if not u or u in got or len(shots) >= 8:
                continue
            got.add(u)
            data = get(u, binary=True)
            if not data:
                continue
            f = save(data, os.path.join(sd, f"shot{len(shots) + 1:02d}"), u)
            try:
                im = Image.open(f)
                w, h = im.size
                if f.endswith((".webp", ".gif", ".avif")) or im.mode not in ("RGB", "RGBA", "L"):
                    nf = os.path.splitext(f)[0] + ".png"
                    im.convert("RGBA").save(nf)
                    if nf != f:
                        os.remove(f)
                    f = nf
            except Exception:
                os.remove(f)
                continue
            if min(w, h) < 400:
                os.remove(f)
                continue
            verdict, line = I.people_check(f)
            if verdict != "pass":
                nf = os.path.join(rej, os.path.basename(f))
                shutil.move(f, nf)
                f = nf
            shots.append({"file": os.path.relpath(f, out), "w": w, "h": h, "kind": kind, "source": u, "people": verdict,
                          "people_note": line[:160], "use": ("full screen ok" if min(w, round(h * 9 / 16)) >= 1080
                                                             else "framed only")})
        ok = sum(s["people"] == "pass" for s in shots)
        print(f"  shots: {ok} pass, {len(shots) - ok} rejected or unchecked (people rules)")
    kit["shots"] = shots
    json.dump(kit, open(os.path.join(out, "kit.json"), "w"), indent=1, ensure_ascii=False)
    sheet(out)
    print(f"  -> {out}/kit.json + sheet.jpg (LOOK at the sheet before a card uses the kit)")
    return 0 if kit.get("logo") else 1


# ---------- sheet ----------
def font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def sheet(out):
    kit = json.load(open(os.path.join(out, "kit.json")))
    W = 1600
    cv = Image.new("RGB", (W, 1500), "#f2f2f2")
    d = ImageDraw.Draw(cv)
    d.text((30, 20), f"{kit['name']}  ·  {kit['url']}  ·  logo tone {kit.get('logo_tone', '?')}", fill="#111", font=font(34))
    y = 80
    with tempfile.TemporaryDirectory() as td:
        tiles = [("as served (grey)", kit.get("logo"), "#8a8a8a"), ("on white", kit.get("logo_on_white"), PAGE_BG),
                 ("on dark", kit.get("logo_on_dark"), "#111111"), ("icon", kit.get("icon"), "#d9d9d9")]
        x = 30
        for label, f, bg in tiles:
            box = Image.new("RGB", (370, 190), bg)
            if f:
                png = os.path.join(td, label.replace(" ", "_") + ".png")
                if render(os.path.join(out, f), png, 370, 190, bg):
                    box = Image.open(png).convert("RGB")
            cv.paste(box, (x, y))
            d.text((x, y + 196), f"{label}: {f or '—'}", fill="#333", font=font(20))
            x += 385
    y += 250
    d.text((30, y), f"accent {kit['accent']} ({kit['accent_source']})   on white {kit['accent_on_white']}", fill="#111", font=font(24))
    y += 40
    for i, c in enumerate(kit.get("palette", []) + [kit.get("ink")]):
        if not c:
            continue
        d.rectangle([30 + i * 160, y, 170 + i * 160, y + 90], fill=c)
        d.text((30 + i * 160, y + 96), c, fill="#333", font=font(20))
    y += 140
    fo = kit.get("font", {})
    d.text((30, y), f"font: site {fo.get('site')} -> Google {fo.get('google')} "
                    f"({'Cyrillic' if fo.get('cyrillic') else 'NO Cyrillic'}); {fo.get('reason')}", fill="#111", font=font(24))
    y += 50
    x = 30
    for s in kit.get("shots", [])[:8]:
        try:
            im = Image.open(os.path.join(out, s["file"])).convert("RGB")
        except Exception:
            continue
        im.thumbnail((360, 250))
        if x + 370 > W:
            x, y = 30, y + 320
        cv.paste(im, (x, y))
        col = "#1d7a4a" if s["people"] == "pass" else "#b3261e"
        d.text((x, y + im.height + 6), f"{os.path.basename(s['file'])}  {s['w']}x{s['h']}", fill="#333", font=font(18))
        d.text((x, y + im.height + 28), f"people {s['people']}", fill=col, font=font(18))
        x += 385
    cv = cv.crop((0, 0, W, min(1500, y + 320)))
    cv.save(os.path.join(out, "sheet.jpg"), quality=88)


def cmd_show(a):
    kit = json.load(open(os.path.join(a.dir, "kit.json")))
    fo = kit.get("font", {})
    print(f"{kit['name']}  {kit['url']}  (pulled {kit['fetched']})")
    print(f"  logo {kit.get('logo')} ({kit.get('logo_tone')})  on white {kit.get('logo_on_white')}  on dark "
          f"{kit.get('logo_on_dark')}  icon {kit.get('icon')}")
    print(f"  accent {kit['accent']} ({kit['accent_source']}), on white {kit['accent_on_white']}, ink {kit['ink']}")
    print(f"  font {fo.get('google')} (site: {fo.get('site')}; {'Cyrillic' if fo.get('cyrillic') else 'NO Cyrillic'})")
    print(f"  shots: " + ", ".join(f"{os.path.basename(s['file'])} {s['people']}" for s in kit.get("shots", [])))
    rel = os.path.basename(os.path.abspath(a.dir))
    print(f"\nproduct-page:  ProductPage(P, ..., accent=\"{kit['accent_on_white']}\")")
    if kit.get("logo"):
        print(f"reel.json chip: {{\"src\": \"{rel}/{kit['logo_on_white']}\"}}   (on a dark card: \"{rel}/{kit['logo_on_dark']}\")")
    if fo.get("css"):
        print(f"fonts:         <link rel=\"stylesheet\" href=\"{rel}/fonts/fonts.css\">  font-family: '{fo['google']}'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("pull")
    p.add_argument("url")
    p.add_argument("--dir", required=True)
    p.add_argument("--name")
    p.add_argument("--slug", help="simple-icons slug when the name does not match it")
    p.add_argument("--no-shots", action="store_true")
    for c in ("show", "sheet"):
        q = sp.add_parser(c)
        q.add_argument("dir")
    a = ap.parse_args()
    if a.cmd == "pull":
        sys.exit(cmd_pull(a))
    if a.cmd == "sheet":
        sheet(os.path.abspath(a.dir))
        print(os.path.join(a.dir, "sheet.jpg"))
    else:
        cmd_show(a)


if __name__ == "__main__":
    main()
