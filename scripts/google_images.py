#!/usr/bin/env python3
"""Google Images through Apify (actor hooli/google-images-scraper, APIFY_TOKEN) into a project's broll/ folder.

    google_images.py search <words> [--other "<same in the other language>"] [--n 10]
                                          list hits (EN + RU searched, merged; free-licence hosts first)
    google_images.py search <words> --dir $P/broll --beat NAME [--n 6] [--min-image 1080] [--no-check]
                                          ... and download them + manifest rows, people-checked

The second source, after Wikimedia Commons (image_sources.py has the order). Checked 2026-10-27: the
actor (6.9k users, the most used) returns image url, size, source page and domain, but no actor in the store takes
Google's usage-rights filter, so licences are unknown. Hits from free-licence hosts (Commons, Pexels, Unsplash,
Pixabay, rawpixel, Flickr) are ranked first and marked; for a Commons hit prefer `wikimedia_fetch.py get <page>`
(it records the real licence and author). Everything else is the creator's work: FRAMED only (print, cut-out, page),
never full screen. The actor bills per result (pay per event): keep --n small; one run per query and language.
Rows join $P/broll/manifest.json (broll_fetch.py's manifest):
  {"id": "g_3f9a1c2b7d", "source": "google", "kind": "image", "page": "<the page the image sits on>",
   "original": "<image url>", "host": "www.pexels.com", "free_host": true, "file": "broll/g_3f9a1c2b7d.jpg",
   "w": .., "h": .., "full_screen_ok": .., "small_frame_only": .., "may_go_big": false,
   "licence": "unknown (Google result: the creator's rights; framed only)" | "free-licence host: check the page",
   "title": "...", "people": "pass" | "FAIL" | "unchecked" | "skipped", "frames": [...], "query": "...", "beat": ""}
"""
import argparse, datetime, hashlib, json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from broll_fetch import download, find, load, save  # noqa: E402
import image_sources as I  # noqa: E402

ACTOR = "hooli~google-images-scraper"
UNKNOWN = "unknown (Google result: the creator's rights; framed only)"
FREE = "free-licence host: check the page (framed unless the page's licence allows more)"


def run_actor(queries, n):
    tok = os.environ.get("APIFY_TOKEN")
    if not tok:
        sys.exit("no APIFY_TOKEN in the environment")
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?timeout=240&token={tok}"
    req = urllib.request.Request(url, data=json.dumps({"queries": queries, "maxResultsPerQuery": n}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        items = json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        sys.exit(f"Apify {ACTOR}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}")
    if not isinstance(items, list):
        sys.exit(f"Apify {ACTOR}: unexpected answer {str(items)[:300]}")
    return items


def search(q, n, other=None):
    runs = I.both(q, other)
    items = run_actor([qq for _, qq in runs], n)
    lists = [[it for it in items if it.get("query") == qq and it.get("imageUrl")] for _, qq in runs]
    for (lang, qq), l in zip(runs, lists):
        print(f"({lang}) {qq!r}: {len(l)} hits")
    merged = I.interleave(*lists, key=lambda it: it["imageUrl"])
    merged.sort(key=lambda it: not I.free_host(it.get("contentUrl") or it.get("origin")))   # stable: free hosts first
    return merged, " | ".join(qq for _, qq in runs)


def rid(url):
    return "g_" + hashlib.sha1(url.encode()).hexdigest()[:10]


def fetch(it, d, rows, A, query):
    proj = os.path.dirname(d)
    rel = lambda p: os.path.relpath(p, proj)
    url = it["imageUrl"].split("?utm_source")[0]
    i = rid(url)
    w0, h0 = it.get("imageWidth"), it.get("imageHeight")
    if w0 and h0 and min(w0, h0) < A.min_image:
        print(f"{i}: {w0}x{h0} below --min-image {A.min_image}: skipped"); return 0
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    f = os.path.join(d, i + (ext if ext in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"))
    try:
        size, fresh = download(url, f)
        info = I.probe_image(f)
    except (Exception, SystemExit) as e:                    # a host refusing hotlinks: skip the hit, keep the rest
        print(f"{i}: download failed ({str(e)[:80]}): skipped {url[:80]}")
        for p in (f, f + ".part"):
            if os.path.exists(p):
                os.remove(p)
        return 0
    ok, small = I.size_verdict(info, A.min_image)
    if not ok:
        print(f"{i}: {info['w']}x{info['h']} below --min-image {A.min_image}: removed"); os.remove(f); return 0
    frames = I.thumb(f, os.path.join(d, i))
    row = find(rows, i)
    people, why = ("skipped", "") if A.no_check else I.people_check(f)
    if row is None:
        row = {"id": i, "beat": A.beat or "", "desc": "", "best_in": None, "best_out": None}
        rows.append(row)
    elif A.beat:
        row["beat"] = A.beat
    page = it.get("contentUrl") or ""
    fh = I.free_host(page or it.get("origin"))
    row.update({"source": "google", "kind": "image", "page": page, "original": url, "host": it.get("origin"),
                "free_host": fh, "file": rel(f), **info, "small_frame_only": small, "may_go_big": False,
                "licence": FREE if fh else UNKNOWN, "title": (it.get("title") or "")[:200], "people": people,
                "frames": [rel(x) for x in frames], "query": query, "fetched": datetime.date.today().isoformat()})
    save(d, rows)
    flag = "" if people in ("pass", "skipped") else f"  PEOPLE {people}: {why[:120]}"
    print(f"{i}: {info['w']}x{info['h']} {size / 1e6:.1f} MB -> {rel(f)}  [{it.get('origin')}{' FREE' if fh else ''}] "
          f"{(it.get('title') or '')[:60]}{'  (framed small only)' if small else ''}{flag}")
    return 1


def cmd_search(A):
    hits, q = search(" ".join(A.words), A.n, A.other)
    for it in hits:
        fh = "FREE" if I.free_host(it.get("contentUrl") or it.get("origin")) else "    "
        print(f"{rid(it['imageUrl'].split('?utm_source')[0])}  {it.get('imageWidth')}x{it.get('imageHeight'):<6} {fh} "
              f"{(it.get('origin') or '')[:24]:<24} {(it.get('title') or '')[:60]}")
    print(f"{len(hits)} Google images for {q!r}")
    if A.dir:
        d = os.path.abspath(A.dir); os.makedirs(d, exist_ok=True)
        rows = load(d)
        big = [it for it in hits if min(it.get("imageWidth") or 0, it.get("imageHeight") or 0) >= A.min_image]
        print(f"{len(big)} of {len(hits)} hits are >= {A.min_image} px on the short side")
        got = sum(fetch(it, d, rows, A, q) for it in big[:A.take or len(big)])
        print(f"{got} files -> {os.path.join(d, 'manifest.json')}. Look at the _a frames; PEOPLE FAIL/unchecked rows stay out.")
        sys.exit(0 if got or not hits else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("words", nargs="+"); s.add_argument("--other")
    s.add_argument("--n", type=int, default=10, help="results per query and language (billed per result)")
    s.add_argument("--take", type=int, help="download only the first N merged hits")
    s.add_argument("--dir"); s.add_argument("--beat"); s.add_argument("--no-check", action="store_true")
    s.add_argument("--min-image", type=int, default=I.MIN_SHORT, help="smallest short side (default 1080; lower = framed small)")
    A = ap.parse_args()
    cmd_search(A)


if __name__ == "__main__":
    main()
