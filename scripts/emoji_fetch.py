#!/usr/bin/env python3
"""Fetch the curated reel-reaction emoji set and convert it for HyperFrames.

Sources (both MIT, Microsoft):
  animated  github.com/microsoft/fluentui-emoji-animated  APNG 256x256 (~24 fps, ~2 s loop), Git LFS
  static    github.com/microsoft/fluentui-emoji           3D PNG 256x256 (symbols with no animated version)

Output, in library/emoji/ (unless --out; gitignored media, synced like the rest of library/):
  <slug>.webm         VP9 + alpha (yuva420p), the APNG looped to >= --min-seconds (6), CFR 30 fps  [animated]
  <slug>.png          poster / still (first frame for animated; the 3D PNG for static)
  <slug>.apng         original APNG, only with --keep-apng (re-downloaded on --force)      [animated]
  manifest.json       one entry per emoji: slug, glyph, kind, files, frames, loop seconds,
                      sha256, source URL, licence. Written after EVERY item (resumable ledger).

Why webm: an <img> APNG animates on the browser's wall clock, so it is not seek-safe in a
HyperFrames render (tests/apng_vs_webm shows it). A <video> is frame-extracted by the renderer.
HyperFrames does the same for .gif (VP9 alpha) but not for APNG.

Integrity: the APNG's sha256 must equal the oid in its Git LFS pointer; the static PNG's git
blob sha1 must equal the tree entry. Mismatch = the item fails, nothing is written for it.

Usage:
  python3 -I scripts/emoji_fetch.py                 # all 50
  python3 -I scripts/emoji_fetch.py --only fire,skull --force
  python3 -I scripts/emoji_fetch.py --force --min-seconds 8   # re-encode longer loops (cached APNGs are reused)
Stdlib only; needs ffmpeg with libvpx-vp9 on PATH.
"""
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EMOJI = os.path.join(HERE, "..", "library", "emoji")
REPOS = {
    "animated": "microsoft/fluentui-emoji-animated",
    "static": "microsoft/fluentui-emoji",
}
UA = {"User-Agent": "ghost-editor-emoji-fetch/0.3"}


def get(url, retries=4, binary=True):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else data.decode("utf-8")
        except Exception as e:  # transient: retry with backoff
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url}: {last}")


def tree(repo):
    url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    data = json.loads(get(url, binary=False))
    if data.get("truncated"):
        print(f"warning: tree for {repo} truncated", file=sys.stderr)
    return {t["path"]: t for t in data["tree"] if t["type"] == "blob"}


def q(path):
    return urllib.parse.quote(path)


def pick(paths, folder, kind):
    pre = f"assets/{folder}/"
    if kind == "animated":
        pats = [re.compile(re.escape(pre) + r"animated/[^/]+\.png$"), re.compile(re.escape(pre) + r"Default/animated/[^/]+\.png$")]
    else:
        pats = [re.compile(re.escape(pre) + r"3D/[^/]+\.png$"), re.compile(re.escape(pre) + r"Default/3D/[^/]+\.png$")]
    for p in pats:
        hits = sorted(x for x in paths if p.match(x))
        if hits:
            return hits[0]
    return None


def ffprobe_frames(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time,duration_time",
                          "-of", "csv=p=0", path], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.strip().splitlines()
    rows = [r.split(",") for r in out if r]
    n = len(rows)
    dur = 0.0
    if rows:
        last = rows[-1]
        try:
            dur = float(last[0]) + float(last[1])
        except (ValueError, IndexError):
            dur = 0.0
    return n, round(dur, 3)


def convert(apng, webm, poster, loops, crf):
    tmp = webm + ".tmp.webm"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if loops > 1:
        cmd += ["-stream_loop", str(loops - 1)]
    cmd += ["-ignore_loop", "1", "-i", apng, "-an", "-vf", "fps=30,format=yuva420p",
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-row-mt", "1",
            "-deadline", "good", "-cpu-used", "2", "-crf", str(crf), "-b:v", "0", "-f", "webm", tmp]
    subprocess.run(cmd, check=True)
    os.replace(tmp, webm)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", apng, "-frames:v", "1", "-update", "1", poster], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=os.path.join(EMOJI, "set.json"))
    ap.add_argument("--out", default=EMOJI)
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--loops", type=int, default=1, help="minimum APNG loops baked into the webm")
    ap.add_argument("--min-seconds", type=float, default=6.0, help="loop the APNG until the webm is at least this long (default 6 s)")
    ap.add_argument("--crf", type=int, default=24)
    ap.add_argument("--keep-apng", action="store_true", help="keep the 80 MB of APNG originals (default: delete after encoding)")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    if "libvpx-vp9" not in enc:
        sys.exit("ffmpeg lacks libvpx-vp9 (needed for alpha webm)")

    items = json.load(open(a.set, encoding="utf-8"))["emoji"]
    only = {s.strip() for s in a.only.split(",") if s.strip()}
    if only:
        items = [e for e in items if e["slug"] in only]
    os.makedirs(a.out, exist_ok=True)
    man_path = os.path.join(a.out, "manifest.json")
    manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {"source": REPOS, "licence": "MIT (Microsoft Fluent Emoji)", "items": {}}

    for kind, repo in REPOS.items():
        lic = os.path.join(a.out, f"LICENSE-{repo.split('/')[1]}.txt")
        if not os.path.exists(lic):
            with open(lic, "wb") as f:
                f.write(get(f"https://raw.githubusercontent.com/{repo}/main/LICENSE"))
    trees = {}
    ok = fail = skip = 0
    t_start = time.time()
    for e in items:
        slug, folder, kind = e["slug"], e["folder"], e["kind"]
        have = manifest["items"].get(slug)
        if have and not a.force and all(os.path.exists(os.path.join(a.out, f)) for f in have["files"] if not f.endswith(".apng")):
            skip += 1
            continue
        try:
            repo = REPOS[kind]
            if repo not in trees:
                trees[repo] = tree(repo)
            paths = trees[repo]
            path = pick(paths, folder, kind)
            if not path:
                raise RuntimeError(f"no {kind} asset for folder '{folder}'")
            meta = {}
            mp = f"assets/{folder}/metadata.json"
            if mp in paths:
                meta = json.loads(get(f"https://raw.githubusercontent.com/{repo}/main/{q(mp)}", binary=False))
            poster = os.path.join(a.out, f"{slug}.png")
            if kind == "animated":
                pointer = get(f"https://raw.githubusercontent.com/{repo}/main/{q(path)}", binary=False)
                m = re.search(r"oid sha256:([0-9a-f]{64})", pointer)
                media_url = f"https://media.githubusercontent.com/media/{repo}/main/{q(path)}"
                apng = os.path.join(a.out, f"{slug}.apng")
                cached = open(apng, "rb").read() if os.path.exists(apng) else b""
                if m and cached and hashlib.sha256(cached).hexdigest() == m.group(1):
                    data = cached  # re-encode only, no re-download
                else:
                    data = get(media_url)
                sha = hashlib.sha256(data).hexdigest()
                if m and m.group(1) != sha:
                    raise RuntimeError(f"sha256 mismatch vs LFS pointer ({sha[:12]} != {m.group(1)[:12]})")
                with open(apng, "wb") as f:
                    f.write(data)
                frames, loop_s = ffprobe_frames(apng)
                loops = max(a.loops, math.ceil(a.min_seconds / loop_s)) if loop_s > 0 else a.loops
                webm = os.path.join(a.out, f"{slug}.webm")
                convert(apng, webm, poster, loops, a.crf)
                files = [f"{slug}.webm", f"{slug}.png"] + ([f"{slug}.apng"] if a.keep_apng else [])
                if not a.keep_apng:
                    os.remove(apng)  # the originals re-download on --force; library/ is synced, keep it small
                extra = {"frames": frames, "loopSeconds": loop_s, "loops": loops, "webmSeconds": round(loop_s * loops, 3),
                         "webmBytes": os.path.getsize(webm)}
                src = media_url
            else:
                url = f"https://raw.githubusercontent.com/{repo}/main/{q(path)}"
                data = get(url)
                blob = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
                if blob != paths[path]["sha"]:
                    raise RuntimeError(f"git blob sha mismatch ({blob[:12]} != {paths[path]['sha'][:12]})")
                sha = hashlib.sha256(data).hexdigest()
                with open(poster, "wb") as f:
                    f.write(data)
                files = [f"{slug}.png"]
                extra = {}
                src = url
            manifest["items"][slug] = {"slug": slug, "glyph": meta.get("glyph", ""), "cldr": meta.get("cldr", folder.lower()),
                                       "kind": kind, "folder": folder, "use": e.get("use", ""), "files": files, "sha256": sha,
                                       "source": src, "repo": f"https://github.com/{repo}", "licence": "MIT", **extra}
            with open(man_path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=1)
            os.replace(man_path + ".tmp", man_path)
            ok += 1
            print(f"ok   {slug:15s} {kind:8s} {meta.get('glyph','')}  {extra.get('frames','')} {extra.get('webmBytes','')}")
        except Exception as ex:
            fail += 1
            print(f"FAIL {slug:15s} {ex}", file=sys.stderr)
    print(f"done: {ok} fetched, {skip} already there, {fail} failed, {time.time() - t_start:.0f}s -> {a.out}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
