#!/usr/bin/env python3
"""Fetch stock B-roll originals (Pexels, Mixkit) into a project's broll/ folder with a manifest the edit reads.

    broll_fetch.py search <words> [--n 12]                      Mixkit ids for a tag (keyless; mixkit.co search pages)
    broll_fetch.py get <url|id> [...] --dir $P/broll [--beat NAME] [--min 1080]
                                                                download the ORIGINAL, probe it, 3 look frames, manifest row
    broll_fetch.py note <id|file> --dir $P/broll [--desc TEXT] [--in S] [--out S] [--beat NAME]
                                                                after looking at the frames: what it shows, the usable window
    broll_fetch.py list --dir $P/broll                          the manifest as a table; rows still missing desc/in/out

Sources (no API key needed for either):
- Pexels: a video page URL (https://www.pexels.com/video/<slug>-<id>/), its id, or "pexels:<id>". The original comes from
  the public download link https://www.pexels.com/download/video/<id>/ (a redirect to the uploaded file, often 4K).
  Pexels search pages and the API need a browser or a key, so find clips with a web search for
  "site:pexels.com/video <what the line shows>" and pass the result URLs here. Pexels License: free, no attribution.
- Mixkit: a page URL (https://mixkit.co/free-stock-video/<slug>-<id>/), or "mixkit:<id>". Only clips offered in 2160p
  are under the Mixkit Stock Video Free License (commercial use OK); a clip without a 2160p file is personal-use only
  and is refused. mixkit.co pages rate-limit (HTTP 429) after ~20 quick requests; the asset CDN does not.

Manifest: <dir>/manifest.json, a list of rows (one per clip; `get` on an existing id refreshes the probe, keeps the notes):
  {"id": "p5852479", "source": "pexels", "page": "<page url>", "pexels_url" | "mixkit_url": "<page url>",
   "file": "broll/p5852479.mp4",              # relative to the project (the parent of --dir)
   "w": 2160, "h": 4096, "fps": 25.0, "duration": 5.08, "hdr": false,
   "full_screen_ok": true,                    # a 9:16 crop is at least 1080 px wide (no upscaling at 1080x1920)
   "frames": ["broll/p5852479_a.jpg", "_b", "_c"],   # 15 %, 50 %, 85 % of the clip, 360 px wide: look before using it
   "beat": "sleep", "desc": "", "best_in": null, "best_out": null,   # filled by `note` after looking at the frames
   "licence": "Pexels License", "fetched": "2026-10-14"}
Then every insert goes through insert_prep.py (cut, people and line check, SDR, fps conform, grade onto the speaker's
plate): `insert_prep.py <file> <out> --in <best_in> --dur <s> --ref assets/plate.mp4`. Stock is the last source in
talking-head styles (references/broll.md 3): own footage first, then stills, then stock video inside a frame.
"""
import argparse, datetime, json, os, re, subprocess, sys, urllib.error, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
LICENCE = {"pexels": "Pexels License", "mixkit": "Mixkit Stock Video Free License"}


def http(url, method="GET"):
    return urllib.request.urlopen(urllib.request.Request(url, method=method, headers={"User-Agent": UA}), timeout=60)


def parse(ref):
    """url | id | pexels:<id> | mixkit:<id> -> (source, numeric id, page url or None)"""
    ref = ref.strip()
    m = re.match(r"(pexels|mixkit):(\d+)$", ref)
    if m:
        return m.group(1), m.group(2), None
    if re.match(r"\d+$", ref):
        return "pexels", ref, None
    m = re.search(r"pexels\.com/(?:[a-z-]+/)?video/(?:[^/]*?-)?(\d+)/?", ref) or re.search(r"videos\.pexels\.com/video-files/(\d+)/", ref)
    if m:
        return "pexels", m.group(1), ref if "/video/" in ref and "video-files" not in ref else None
    m = re.search(r"mixkit\.co/free-stock-video/[^/]*?-(\d+)/?", ref) or re.search(r"assets\.mixkit\.co/videos/(\d+)/", ref)
    if m:
        return "mixkit", m.group(1), ref if "free-stock-video" in ref else None
    sys.exit(f"not a Pexels or Mixkit clip: {ref}")


def original_url(src, vid):
    """the largest original file; Mixkit: the 2160p asset or nothing (no free licence below it)"""
    if src == "pexels":
        r = http(f"https://www.pexels.com/download/video/{vid}/", "HEAD")
        return r.geturl()
    url = f"https://assets.mixkit.co/videos/{vid}/{vid}-2160.mp4"
    try:
        http(url, "HEAD")
        return url
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return None
        raise


def download(url, dest):
    head = http(url, "HEAD")
    size = int(head.headers.get("Content-Length") or 0)
    if os.path.exists(dest) and size and os.path.getsize(dest) == size:
        return size, False
    tmp = dest + ".part"
    with http(url) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    if size and os.path.getsize(tmp) != size:
        os.remove(tmp)
        sys.exit(f"download incomplete: {url}")
    os.replace(tmp, dest)
    return os.path.getsize(dest), True


def probe(f):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate,avg_frame_rate,color_transfer"
                                   ":stream_side_data=rotation,side_data_type,crop_left,crop_right,crop_top,crop_bottom:format=duration",
                                   "-of", "json", f], capture_output=True, text=True, check=True).stdout)
    s = j["streams"][0]
    w, h = s["width"], s["height"]
    sds = s.get("side_data_list", []) or []
    for d in sds:                       # the size ffmpeg decodes: container crop off first (grade_lib.shown_size), then upright
        if d.get("side_data_type") == "Frame Cropping":
            w -= int(d.get("crop_left", 0) or 0) + int(d.get("crop_right", 0) or 0)
            h -= int(d.get("crop_top", 0) or 0) + int(d.get("crop_bottom", 0) or 0)
    rot = next((abs(int(d.get("rotation", 0))) for d in sds if "rotation" in d), 0)
    if rot in (90, 270):
        w, h = h, w
    n, d = (s.get("avg_frame_rate") or s["r_frame_rate"]).split("/")
    fps = round(float(n) / float(d), 3) if float(d) else 0.0
    return {"w": w, "h": h, "fps": fps, "duration": round(float(j["format"]["duration"]), 3),
            "hdr": s.get("color_transfer") in ("arib-std-b67", "smpte2084"),
            "full_screen_ok": min(w, round(h * 9 / 16)) >= 1080}


def look_frames(f, stem, dur):
    out = []
    for tag, q in (("a", 0.15), ("b", 0.5), ("c", 0.85)):
        jpg = f"{stem}_{tag}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * q:.3f}", "-i", f, "-frames:v", "1", "-vf", "scale=360:-2",
                        "-q:v", "4", jpg], check=True)
        out.append(jpg)
    return out


def load(d):
    p = os.path.join(d, "manifest.json")
    return json.load(open(p)) if os.path.exists(p) else []


def save(d, rows):
    json.dump(rows, open(os.path.join(d, "manifest.json"), "w"), ensure_ascii=False, indent=1)


def find(rows, ref):
    """a row by id (p123 / m456), bare number, or file name; rows from older manifests have no id, only a file"""
    k = os.path.splitext(os.path.basename(ref))[0]
    keys = {k, "p" + k, "m" + k}
    for r in rows:
        if keys & {r.get("id"), os.path.splitext(os.path.basename(r.get("file", "")))[0]}:
            return r
    return None


def cmd_get(A):
    d = os.path.abspath(A.dir); os.makedirs(d, exist_ok=True)
    proj = os.path.dirname(d)
    rel = lambda p: os.path.relpath(p, proj)
    rows = load(d); bad = 0
    for ref in A.refs:
        src, vid, page = parse(ref)
        rid = ("p" if src == "pexels" else "m") + vid
        url = original_url(src, vid)
        if not url:
            print(f"{rid}: no 2160p file on Mixkit, so no free licence (personal use only): skipped"); bad += 1; continue
        f = os.path.join(d, rid + ".mp4")
        size, fresh = download(url, f)
        info = probe(f)
        if min(info["w"], info["h"]) < A.min:
            print(f"{rid}: {info['w']}x{info['h']} is below --min {A.min}: removed"); os.remove(f); bad += 1; continue
        frames = look_frames(f, os.path.join(d, rid), info["duration"])
        row = find(rows, rid)
        if row is None:
            row = {"id": rid, "beat": A.beat or "", "desc": "", "best_in": None, "best_out": None}
            rows.append(row)
        elif A.beat:
            row["beat"] = A.beat
        page = page or row.get("page") or (f"https://www.pexels.com/video/{vid}/" if src == "pexels" else f"https://mixkit.co/free-stock-video/{vid}/")
        row.update({"source": src, "page": page, f"{src}_url": page, "original": url, "file": rel(f), **info,
                    "frames": [rel(x) for x in frames], "licence": LICENCE[src], "fetched": datetime.date.today().isoformat()})
        save(d, rows)
        note = "" if info["full_screen_ok"] else "  (a 9:16 crop is under 1080 wide: framed inserts only)"
        print(f"{rid}: {info['w']}x{info['h']} {info['fps']:g} fps {info['duration']:.1f} s{' HDR' if info['hdr'] else ''}, "
              f"{size / 1e6:.0f} MB {'downloaded' if fresh else 'already here'} -> {rel(f)}{note}")
    print(f"manifest: {os.path.join(d, 'manifest.json')} ({len(rows)} clips). Look at the _a/_b/_c frames, then `note` each one.")
    sys.exit(1 if bad and bad == len(A.refs) else 0)


def cmd_note(A):
    d = os.path.abspath(A.dir); rows = load(d)
    row = find(rows, A.ref) or sys.exit(f"{A.ref} is not in {d}/manifest.json")
    for k, v in (("desc", A.desc), ("best_in", A.in_), ("best_out", A.out), ("beat", A.beat)):
        if v is not None:
            row[k] = v
    if row.get("best_in") is not None and row.get("best_out") is not None:
        if not 0 <= row["best_in"] < row["best_out"] <= row.get("duration", 1e9) + 0.01:
            sys.exit(f"window {row['best_in']}-{row['best_out']} is outside the clip (0-{row.get('duration')})")
    save(d, rows)
    print(json.dumps(row, ensure_ascii=False, indent=1))


def cmd_list(A):
    d = os.path.abspath(A.dir); rows = load(d)
    for r in rows:
        todo = [k for k in ("desc", "best_in", "best_out") if r.get(k) in (None, "")]
        win = f"{r['best_in']:.1f}-{r['best_out']:.1f}" if r.get("best_in") is not None and r.get("best_out") is not None else "?"
        print(f"{r.get('id', '?'):>11} {r.get('beat', ''):>10} {r.get('w')}x{r.get('h')} {r.get('fps', 0):g}fps {r.get('duration', 0):5.1f}s "
              f"win {win:>9}  {(r.get('desc') or '')[:70]}{'  TODO ' + ','.join(todo) if todo else ''}")
    print(f"{len(rows)} clips in {d}/manifest.json")


def cmd_search(A):
    tag = re.sub(r"[^a-z0-9]+", "-", " ".join(A.words).lower()).strip("-")
    try:
        html = http(f"https://mixkit.co/free-stock-video/{tag}/").read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        sys.exit(f"mixkit.co/free-stock-video/{tag}/: HTTP {e.code}" + (" (rate limit: wait a minute)" if e.code == 429 else
                 " (no such tag: try one word, e.g. 'office', 'sleep', 'city')" if e.code == 404 else ""))
    seen = []
    for slug, vid in re.findall(r'href="/free-stock-video/([a-z0-9-]+?)-(\d+)/"', html):
        if vid not in [v for v, _ in seen]:
            seen.append((vid, slug))
    for vid, slug in seen[:A.n]:
        print(f"mixkit:{vid:<7} https://mixkit.co/free-stock-video/{slug}-{vid}/")
    print(f"{len(seen)} clips on mixkit.co/free-stock-video/{tag}/ (shown {min(A.n, len(seen))}); `get` keeps only those with a 2160p file")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="Mixkit ids for a tag"); s.add_argument("words", nargs="+"); s.add_argument("--n", type=int, default=12)
    g = sub.add_parser("get", help="download originals + manifest rows"); g.add_argument("refs", nargs="+"); g.add_argument("--dir", required=True)
    g.add_argument("--beat"); g.add_argument("--min", type=int, default=1080, help="smallest short side kept (px; default 1080, no 720p)")
    n = sub.add_parser("note", help="desc and best window after looking"); n.add_argument("ref"); n.add_argument("--dir", required=True)
    n.add_argument("--desc"); n.add_argument("--in", dest="in_", type=float); n.add_argument("--out", type=float); n.add_argument("--beat")
    li = sub.add_parser("list", help="the manifest as a table"); li.add_argument("--dir", required=True)
    A = ap.parse_args()
    {"search": cmd_search, "get": cmd_get, "note": cmd_note, "list": cmd_list}[A.cmd](A)


if __name__ == "__main__":
    main()
