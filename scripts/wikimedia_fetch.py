#!/usr/bin/env python3
"""Wikimedia Commons pictures (free API, no key) into a project's broll/ folder: first stop for archival / historical.

    wikimedia_fetch.py search <words> [--other "<same in the other language>"] [--n 12]
                                          list hits (EN + RU searched, merged): title, size, licence, author
    wikimedia_fetch.py search <words> --dir $P/broll --beat NAME [--n 6] [--min-image 1080] [--no-check]
                                          ... and download them (original file) + manifest rows, people-checked
    wikimedia_fetch.py get "File:Name.jpg" | <commons url> [...] --dir $P/broll [--beat NAME]
                                          one file you already picked
    wikimedia_fetch.py category "Photographs by Alexander Roinashvili" [--n 200] [--grep WORD]
                                          the files of a category (no download); `cats <words>` finds categories.
                                          Commons search is literal (long queries find nothing): for archives, a
                                          category is the better index (e.g. "History of Lisbon", "Fishing in Portugal")

Each search runs twice, in English and in Russian (--other gives the second query; else Gemini translates), and the
hits are merged alternately. Only bitmaps (photos, scans, engravings, manuscripts); SVG drawings are skipped.
The original upload is taken; a TIFF or a file over 40 MB comes as Commons' own 4000 px JPEG of it (row "via_thumb").
Rows join $P/broll/manifest.json (broll_fetch.py's manifest):
  {"id": "wm_3f9a1c2b7d", "source": "wikimedia", "kind": "image", "title": "File:...", "page": "<commons file page>",
   "original": "<upload url>", "file": "broll/wm_3f9a1c2b7d.jpg", "w": 2400, "h": 1700, "full_screen_ok": false,
   "small_frame_only": false, "licence": "Public domain" | "CC BY-SA 4.0" | ..., "licence_url": "...",
   "author": "...", "credit": "...", "date": "...", "description": "...", "restrictions": "...",
   "may_go_big": true,          # a free licence: it may fill more of the screen (full screen only if full_screen_ok)
   "people": "pass" | "FAIL" | "unchecked" | "skipped", "frames": ["broll/wm_..._a.jpg"], "query": "...", "beat": ""}
CC BY / BY-SA need the author credited where the reel is posted (the caption): keep the row's author + licence.
"""
import argparse, datetime, hashlib, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from broll_fetch import find, load, save  # noqa: E402
import image_sources as I  # noqa: E402

API = "https://commons.wikimedia.org/w/api.php"
UA = "ghost-editor-image-fetch/1.0 (personal short-video editing; python urllib)"   # Wikimedia asks for a descriptive UA
BIG = 40e6


def call(**params):
    params.update(format="json", formatversion=2)
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:              # Commons answers 429 to a quick burst of searches
            if e.code not in (429, 503) or attempt == 4:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 5 * 2 ** attempt)


def download(url, dest):
    """upload.wikimedia.org throttles generic browser UAs (HTTP 429, 2026-10-27): its own UA, backoff, a pause per file"""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return os.path.getsize(dest), False
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r, \
                    open(dest + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            os.replace(dest + ".part", dest)
            time.sleep(1.5)
            return os.path.getsize(dest), True
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == 5:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 10 * 2 ** attempt)


def plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def norm(p):
    ii = (p.get("imageinfo") or [{}])[0]
    md = ii.get("extmetadata") or {}
    v = lambda k: plain((md.get(k) or {}).get("value"))
    return {"title": p["title"], "page": ii.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(p['title'])}",
            "url": ii.get("url"), "thumb": ii.get("thumburl"), "w": ii.get("width"), "h": ii.get("height"),
            "bytes": ii.get("size") or 0, "mime": ii.get("mime", ""), "licence": v("LicenseShortName") or v("UsageTerms"),
            "licence_url": v("LicenseUrl"), "author": v("Artist")[:200], "credit": v("Credit")[:200],
            "date": v("DateTimeOriginal")[:60], "description": v("ImageDescription")[:300], "restrictions": v("Restrictions")}


INFO = dict(prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=4000,
            iiextmetadatafilter="LicenseShortName|UsageTerms|LicenseUrl|Artist|Credit|DateTimeOriginal|ImageDescription|Restrictions")


def search_one(q, n):
    j = call(action="query", generator="search", gsrsearch=f"{q} filetype:bitmap", gsrnamespace=6, gsrlimit=min(50, n), **INFO)
    pages = sorted((j.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
    return [norm(p) for p in pages if p.get("imageinfo")]


def search(q, n, other=None):
    runs = I.both(q, other)
    lists = [search_one(qq, n) for _, qq in runs]
    for (lang, qq), l in zip(runs, lists):
        print(f"({lang}) {qq!r}: {len(l)} hits")
    return I.interleave(*lists, key=lambda h: h["title"])[:n], " | ".join(qq for _, qq in runs)


def by_titles(titles):
    j = call(action="query", titles="|".join(titles), **INFO)
    return [norm(p) for p in (j.get("query") or {}).get("pages") or [] if p.get("imageinfo")]


def category(name, n):
    name = name if name.startswith("Category:") else "Category:" + name
    out, cont = [], {}
    while len(out) < n:
        j = call(action="query", generator="categorymembers", gcmtitle=name, gcmtype="file", gcmlimit=50, **INFO, **cont)
        out += [norm(p) for p in (j.get("query") or {}).get("pages") or [] if p.get("imageinfo")]
        if "continue" not in j:
            break
        cont = j["continue"]
    return out[:n]


def rid(title):
    return "wm_" + hashlib.sha1(title.encode()).hexdigest()[:10]


def free(lic):
    l = (lic or "").lower()
    return "public domain" in l or l.startswith("pd") or "cc" in l or "no restrictions" in l


def fetch(h, d, rows, A, query=""):
    proj = os.path.dirname(d)
    rel = lambda p: os.path.relpath(p, proj)
    i = rid(h["title"])
    if (h["w"] and h["h"]) and min(h["w"], h["h"]) < A.min_image:
        print(f"{i}: {h['w']}x{h['h']} is below --min-image {A.min_image}: skipped ({h['title'][:60]})"); return 0
    thumb_ok = h["thumb"] and h["thumb"] != h["url"]
    via_thumb = thumb_ok and (h["mime"] == "image/tiff" or h["bytes"] > BIG)
    url = h["thumb"] if via_thumb else h["url"]
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() or ".jpg"
    if ext in (".tif", ".tiff"):
        print(f"{i}: a TIFF with no JPEG copy: skipped"); return 0
    f = os.path.join(d, i + ext)
    size, fresh = download(url, f)
    info = I.probe_image(f)
    ok, small = I.size_verdict(info, A.min_image)
    if not ok:
        print(f"{i}: {info['w']}x{info['h']} below --min-image {A.min_image}: removed"); os.remove(f); return 0
    frames = I.thumb(f, os.path.join(d, i))
    row = find(rows, i)
    people, why = ("skipped", "") if A.no_check else I.people_check(f)
    if people == "skipped" and row and row.get("people") not in (None, "skipped"):
        people = row["people"]
    if row is None:
        row = {"id": i, "beat": A.beat or "", "desc": "", "best_in": None, "best_out": None}
        rows.append(row)
    elif A.beat:
        row["beat"] = A.beat
    row.update({"source": "wikimedia", "kind": "image", "title": h["title"], "page": h["page"], "original": h["url"],
                "via_thumb": bool(via_thumb), "file": rel(f), **info, "small_frame_only": small,
                "licence": h["licence"] or "see the Commons page", "licence_url": h["licence_url"], "author": h["author"],
                "credit": h["credit"], "date": h["date"], "description": h["description"], "restrictions": h["restrictions"],
                "may_go_big": free(h["licence"]) and not small, "frames": [rel(x) for x in frames], "people": people,
                "query": query, "fetched": datetime.date.today().isoformat()})
    save(d, rows)
    flag = "" if people in ("pass", "skipped") else f"  PEOPLE {people}: {why[:120]}"
    note = "  (framed small only)" if small else ("" if info["full_screen_ok"] else "  (framed / part of the screen)")
    print(f"{i}: {info['w']}x{info['h']} {size / 1e6:.1f} MB {'downloaded' if fresh else 'already here'} -> {rel(f)}  "
          f"[{h['licence'] or '?'}; {h['author'][:40]}] {h['title'][5:70]}{note}{flag}")
    return 1


def show(hits):
    for h in hits:
        print(f"{rid(h['title'])}  {h['w']}x{h['h']:<6} {(h['licence'] or '?')[:16]:<16} {h['author'][:24]:<24} {h['title'][5:80]}")


def cmd_search(A):
    hits, q = search(" ".join(A.words), A.n, A.other)
    show(hits)
    print(f"{len(hits)} Commons pictures for {q!r}")
    if A.dir:
        d = os.path.abspath(A.dir); os.makedirs(d, exist_ok=True)
        rows = load(d)
        got = sum(fetch(h, d, rows, A, q) for h in hits)
        print(f"{got} files -> {os.path.join(d, 'manifest.json')}. Look at the _a frames; PEOPLE FAIL/unchecked rows stay out.")
        sys.exit(0 if got or not hits else 1)


def cmd_category(A):
    hits = [h for h in category(A.name, A.n) if not A.grep or A.grep.lower() in (h["title"] + h["description"]).lower()]
    show(hits)
    print(f"{len(hits)} files in {A.name!r}")


def cmd_cats(A):
    j = call(action="query", list="search", srsearch=" ".join(A.words), srnamespace=14, srlimit=20)
    for x in j["query"]["search"]:
        print(x["title"])


def cmd_get(A):
    titles = []
    for r in A.refs:
        m = re.search(r"(File:[^?#]+)", urllib.parse.unquote(r))
        titles.append(m.group(1).replace("_", " ") if m else "File:" + r)
    d = os.path.abspath(A.dir); os.makedirs(d, exist_ok=True)
    rows = load(d)
    got = sum(fetch(h, d, rows, A, "get") for h in by_titles(titles))
    sys.exit(0 if got else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--beat"); p.add_argument("--no-check", action="store_true")
        p.add_argument("--min-image", type=int, default=I.MIN_SHORT, help="smallest short side (default 1080; lower = framed small)")

    s = sub.add_parser("search"); s.add_argument("words", nargs="+"); s.add_argument("--other"); s.add_argument("--n", type=int, default=12)
    s.add_argument("--dir"); common(s)
    g = sub.add_parser("get"); g.add_argument("refs", nargs="+"); g.add_argument("--dir", required=True); common(g)
    c = sub.add_parser("category"); c.add_argument("name"); c.add_argument("--n", type=int, default=200); c.add_argument("--grep")
    k = sub.add_parser("cats"); k.add_argument("words", nargs="+")
    A = ap.parse_args()
    {"search": cmd_search, "get": cmd_get, "category": cmd_category, "cats": cmd_cats}[A.cmd](A)


if __name__ == "__main__":
    main()
