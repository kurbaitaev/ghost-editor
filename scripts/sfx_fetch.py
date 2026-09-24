#!/usr/bin/env python3
"""Build the SFX kit: real recorded sounds, normalized once, with a manifest.

    sfx_fetch.py [--only id1,id2] [--force] [--licensed-only]

Two sources, both scriptable:
  mixkit:<category>:<title regex>   editing layer (whoosh, pop, impact...),
                                     Mixkit free licence, commercial use OK
  yt:<search query>                  meme layer (vine boom, bruh...), pulled
                                     with yt-dlp from YouTube uploads; these
                                     are unlicensed rips, fine on IG/TikTok

Every KIT entry carries a 6th field, its licence class:
  "mixkit"  licensed (Mixkit free licence), ships in the public build
  "rip"     YouTube meme rip, private build only
LICENSED / RIPS below are derived from it; --licensed-only fetches only
LICENSED ids, which is what the public build restores.

Once an entry has a mixkit_id in manifest.json that id is fetched directly
(pinned), so restores reproduce the exact sound; the title regex only picks
the sound the first time. Titles in the manifest come from parsing each
Mixkit card as a whole (an older parser paired ids with the previous card's
title, so a few early entries' regexes describe a different sound than the
pinned one; the manifest "source" shows the real title).

Every file is trimmed of leading/trailing silence, cut to its max length,
faded out, converted to 48 kHz stereo WAV and peak-normalized to -1 dBFS,
so the composition sets level by role, not by whatever the file shipped at.
Results go to library/sfx/<id>.wav and library/sfx/manifest.json (merged,
so a partial run keeps earlier entries). Failures are reported, never
written as fake entries.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "library", "sfx")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/126 Safari/537.36"

# id, role, source, max seconds, tags, licence ("mixkit" | "rip")
# role decides mix level in build.mjs: ui < whoosh < impact < meme
KIT = [
    # editing layer
    ("whoosh-1", "whoosh", r"mixkit:whoosh:^Fast whoosh transition$", 0.9, ["zoom", "transition", "card-in"], "mixkit"),
    ("whoosh-2", "whoosh", r"mixkit:whoosh:^Air woosh$", 0.9, ["zoom", "transition", "card-in"], "mixkit"),
    ("whoosh-3", "whoosh", r"mixkit:whoosh:^Arrow whoosh$", 0.9, ["zoom", "transition", "card-in"], "mixkit"),
    ("whoosh-cine", "whoosh", r"mixkit:whoosh:^Cinematic whoosh fast transition$", 1.5, ["text-slam", "reveal"], "mixkit"),
    ("pop-1", "ui", r"mixkit:pop:(?i)bubble pop", 0.4, ["chip", "emoji", "list-item"], "mixkit"),
    ("pop-2", "ui", r"mixkit:pop:^Hard pop click$", 0.4, ["chip", "emoji", "list-item"], "mixkit"),
    ("pop-3", "ui", r"mixkit:pop:(?i)pop", 0.4, ["chip", "emoji", "list-item"], "mixkit"),
    ("click-1", "ui", r"mixkit:click:(?i)mouse", 0.25, ["ui", "cursor"], "mixkit"),
    ("tick-1", "ui", r"mixkit:typing:(?i)single key|key", 0.2, ["typing"], "mixkit"),
    ("typing-1", "ui", r"mixkit:typing:(?i)typing", 2.5, ["typing", "prompt"], "mixkit"),
    ("impact-1", "impact", r"mixkit:impact:(?i)cinematic.*(hit|impact|boom)", 1.6, ["text-slam", "number", "stamp"], "mixkit"),
    ("impact-2", "impact", r"mixkit:impact:(?i)(hit|impact|thud)", 1.2, ["text-slam", "number", "stamp"], "mixkit"),
    ("riser-1", "whoosh", r"mixkit:cinematic:(?i)riser|rising|build", 2.0, ["build-up"], "mixkit"),
    ("ding-1", "ui", r"mixkit:notification:(?i)correct|success|positive", 1.0, ["win", "check"], "mixkit"),
    ("buzzer-1", "meme", r"mixkit:game-show:(?i)wrong|fail|buzzer", 1.2, ["wrong", "dismiss", "myth"], "mixkit"),
    ("kaching-1", "impact", r"mixkit:cash:(?i)cash register|register|coins", 1.4, ["money", "price", "win"], "mixkit"),
    ("shutter-1", "ui", r"mixkit:camera:(?i)shutter", 0.6, ["screenshot", "save", "freeze"], "mixkit"),
    # meme layer: YouTube rips, private build only (public build uses the reaction family below)
    # --- licensed families (Mixkit free licence, commercial OK, no attribution) ---
    # reaction: licensed stand-ins for the meme rips (crowd-ooh and record-scratch
    # have no Mixkit equivalent; crowd-boo and tape-rewind are the nearest)
    ("reaction-boing", "meme", r"mixkit:cartoon:^Boing hit sound$", 1.2, ["absurd", "bounce", "flex"], "mixkit"),
    ("reaction-rimshot", "meme", r"mixkit:drum:^Drum joke accent$", 2.0, ["punchline", "bad-joke"], "mixkit"),
    ("reaction-fail-trombone", "meme", r"mixkit:funny:^Sad game over trombone$", 3.0, ["fail", "sad", "pity"], "mixkit"),
    ("reaction-drum-roll", "meme", r"mixkit:drum:^Drum Roll$", 3.0, ["build-up", "reveal", "suspense"], "mixkit"),
    ("reaction-crowd-laugh", "meme", r"mixkit:crowd:^Crowd laugh$", 3.0, ["punchline", "roast", "dumb"], "mixkit"),
    ("reaction-crowd-boo", "meme", r"mixkit:crowd:^Crowd disappointment long boo$", 2.5, ["bad-take", "myth", "wrong"], "mixkit"),
    ("reaction-applause-short", "meme", r"mixkit:applause:^Small group clapping$", 3.0, ["win", "flex", "sarcastic"], "mixkit"),
    ("reaction-tape-rewind", "meme", r"mixkit:cinematic:^Tape rewind cinematic transition$", 1.5, ["wait", "freeze-frame", "twist"], "mixkit"),
    ("reaction-cartoon-pop", "meme", r"mixkit:cartoon:^Cartoon bubbles pop$", 0.6, ["emoji", "idea", "light"], "mixkit"),
    ("reaction-slide-whistle", "meme", r"mixkit:cartoon:^Cartoon falling whistle$", 2.0, ["fail", "drop", "falling"], "mixkit"),
    ("reaction-gasp", "meme", r"mixkit:gasp:^Male astonished gasp$", 1.2, ["shock", "disbelief", "claim"], "mixkit"),
    ("reaction-ding-ding", "meme", r"mixkit:bell:^Service bell double ding$", 1.2, ["correct", "idea", "win"], "mixkit"),
    # cinematic
    ("cinematic-deep-boom", "impact", r"mixkit:drum:^Blockbuster trailer bass drum$", 2.5, ["text-slam", "reveal", "number"], "mixkit"),
    ("cinematic-cine-hit", "impact", r"mixkit:impact:^Epic movie impact$", 2.0, ["title", "stamp", "reveal"], "mixkit"),
    ("cinematic-rumble-riser", "whoosh", r"mixkit:riser:^Cinematic drama riser$", 3.0, ["build-up", "tension"], "mixkit"),
    ("cinematic-drone-swell", "whoosh", r"mixkit:cinematic:^Trailer cinematic suspense swell$", 4.0, ["tension", "bed", "reveal"], "mixkit"),
    ("cinematic-heartbeat", "impact", r"mixkit:boom:^Human single heart beat$", 1.5, ["tension", "pause", "stakes"], "mixkit"),
    ("cinematic-film-flash", "whoosh", r"mixkit:impact:^Short impact static$", 1.0, ["flash", "cut", "transition"], "mixkit"),
    # tech
    ("tech-glitch-1", "ui", r"mixkit:glitch:^Glitch short$", 0.8, ["glitch", "cut", "error"], "mixkit"),
    ("tech-glitch-2", "whoosh", r"mixkit:glitch:^Digital glitch break$", 1.2, ["glitch", "transition"], "mixkit"),
    ("tech-digital-whoosh", "whoosh", r"mixkit:whoosh:^Electric whoosh$", 1.2, ["zoom", "transition", "tech"], "mixkit"),
    ("tech-ui-confirm", "ui", r"mixkit:notification:^Success software tone$", 1.0, ["check", "win", "done"], "mixkit"),
    ("tech-ui-error", "ui", r"mixkit:interface:^Click error$", 0.8, ["wrong", "myth", "reject"], "mixkit"),
    ("tech-keyboard-burst", "ui", r"mixkit:typing:^Fast keyboard typing$", 2.0, ["typing", "prompt", "code"], "mixkit"),
    ("tech-notification-2", "ui", r"mixkit:technology:^High tech notification bleep$", 1.0, ["notification", "chip", "alert"], "mixkit"),
    ("tech-camera-flash", "ui", r"mixkit:camera:^Camera digital shutter$", 0.8, ["screenshot", "flash", "freeze"], "mixkit"),
]

LICENSED = {e[0] for e in KIT if e[5] == "mixkit"}  # public build: safe to ship
RIPS = {e[0] for e in KIT if e[5] == "rip"}  # private build only


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


_mixkit_cache = {}


def _mixkit_page(category, page):
    url = f"https://mixkit.co/free-sound-effects/{category}/" + (f"?page={page}" if page > 1 else "")
    html = fetch(url).decode("utf8", "replace")
    # parse card by card: the title sits AFTER the preview URL inside the same
    # card, so scanning backwards from the URL pairs each id with the previous
    # card's title (the bug that mislabelled the first kit)
    items = []
    for card in html.split('class="item-grid-card ')[1:]:
        pid = re.search(r"sfx/(\d+)/\1-preview\.mp3", card)
        title = re.search(r'item-grid-card__title">\s*([^<]+?)\s*</h2>', card)
        if pid and title:
            items.append((pid.group(1), title.group(1).strip()))
    return items


def mixkit_candidates(category, pages=2):
    if category not in _mixkit_cache:
        seen, uniq = set(), []
        for page in range(1, pages + 1):
            try:
                items = _mixkit_page(category, page)
            except Exception:
                break  # a missing page 2 just means a short category
            for i, t in items:
                if i not in seen:
                    seen.add(i)
                    uniq.append((i, t))
        _mixkit_cache[category] = uniq
    return _mixkit_cache[category]


def mixkit_preview(sid, dst):
    open(dst, "wb").write(fetch(f"https://assets.mixkit.co/active_storage/sfx/{sid}/{sid}-preview.mp3"))


def get_mixkit(category, pattern, used, dst, pinned=None):
    # an id already recorded in manifest.json is fetched as-is, so a restore
    # reproduces the exact sound the reels were built with; title search is
    # only for entries that have never been fetched
    cands = mixkit_candidates(category)
    if pinned:
        mixkit_preview(pinned, dst)
        title = dict(cands).get(pinned, "(title not on category page)")
        return f"https://mixkit.co/free-sound-effects/{category}/ #{pinned} {title}"
    for sid, title in cands:
        if sid in used or not re.search(pattern, title):
            continue
        mixkit_preview(sid, dst)
        used.add(sid)
        return f"https://mixkit.co/free-sound-effects/{category}/ #{sid} {title}"
    raise RuntimeError(f"no mixkit '{category}' title matches /{pattern}/; have: {[t for _, t in cands][:12]}")


def get_yt(query, dst_base):
    # short uploads only; the first hit under 20 s wins (skips compilations and songs)
    r = subprocess.run([
        "yt-dlp", f"ytsearch5:{query}", "--match-filter", "duration < 20",
        "--max-downloads", "1", "-x", "--audio-format", "wav", "--no-playlist",
        "-o", dst_base + ".%(ext)s", "--print", "after_move:%(webpage_url)s %(title)s",
    ], capture_output=True, text=True)
    # --max-downloads exits 101 when it stops early; that is success
    if not os.path.exists(dst_base + ".wav"):
        raise RuntimeError(f"yt-dlp got nothing for '{query}': {r.stderr.strip()[-300:]}")
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else f"ytsearch:{query}"


def normalize(src, dst, max_s):
    # trim silence at both ends, cap length, 20 ms fade out, 48k stereo
    trim = (
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.01,"
        "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,areverse,"
        f"atrim=0:{max_s},afade=t=out:st={max(0.0, max_s - 0.02)}:d=0.02"
    )
    tmp = dst + ".tmp.wav"
    sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", trim, "-ar", "48000", "-ac", "2", tmp])
    peak = float(re.search(r"max_volume: (-?[\d.]+) dB", sh(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", tmp, "-af", "volumedetect", "-f", "null", "-"]
    ).stderr).group(1))
    gain = -1.0 - peak
    sh(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", f"volume={gain}dB", "-ar", "48000", "-c:a", "pcm_s16le", dst])
    os.remove(tmp)
    dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", dst]).stdout)
    return dur, gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--licensed-only", action="store_true", help="fetch only Mixkit (LICENSED) entries")
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))
    os.makedirs(OUT, exist_ok=True)
    mpath = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    todo = [e for e in KIT if (not only or e[0] in only) and (not args.licensed_only or e[0] in LICENSED)]
    # every recorded id is reserved so a new entry never grabs another's sound;
    # an entry's own recorded id is fetched directly (pinned) and skips this check
    used = {e.get("mixkit_id") for e in manifest.values() if e.get("mixkit_id")}
    failed = []
    for sid, role, source, max_s, tags, lic_class in todo:
        dst = os.path.join(OUT, f"{sid}.wav")
        if os.path.exists(dst) and sid in manifest and not args.force:
            continue
        with tempfile.TemporaryDirectory() as td:
            try:
                kind, rest = source.split(":", 1)
                if kind == "mixkit":
                    cat, pat = rest.split(":", 1)
                    raw = os.path.join(td, "raw.mp3")
                    origin = get_mixkit(cat, pat, used, raw, pinned=manifest.get(sid, {}).get("mixkit_id"))
                    licence = "Mixkit Free SFX licence (commercial OK, no redistribution as-is)"
                else:
                    base = os.path.join(td, "raw")
                    origin = get_yt(rest, base)
                    raw = base + ".wav"
                    licence = "unlicensed meme rip: IG/TikTok only"
                dur, gain = normalize(raw, dst, max_s)
            except Exception as e:  # report and keep going; never write a stub
                failed.append((sid, str(e)[:300]))
                print(f"FAIL {sid}: {str(e)[:300]}", file=sys.stderr)
                continue
        entry = {"file": f"{sid}.wav", "role": role, "tags": tags, "duration": round(dur, 3),
                 "peak_db": -1.0, "source": origin, "licence": licence, "licensed": lic_class == "mixkit"}
        m = re.search(r"#(\d+)", origin)
        if kind == "mixkit" and m:
            entry["mixkit_id"] = m.group(1)
        manifest[sid] = entry
        json.dump(manifest, open(mpath, "w"), indent=2)
        print(f"ok   {sid:18s} {role:7s} {dur:5.2f}s  {origin[:90]}")
    print(f"\n{len(manifest)} in manifest, {len(failed)} failed")
    for sid, e in failed:
        print(f"  {sid}: {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
