#!/usr/bin/env python3
"""Trend radar: what meme formats are new right now, and which are not in the
library yet.

    trends.py            # print fresh names from imgflip + Know Your Meme
    trends.py --json     # machine-readable

Sources (both plain HTML, no key):
  - imgflip.com/memetemplates?sort=top-new   new templates people are captioning
  - knowyourmeme.com (homepage)              entries the editors are covering now
It only finds NAMES. Sourcing a clip is a human call: search YouTube for
"<name> green screen", check it, then meme_add.py. Nothing is downloaded here.
"""
import argparse
import html
import json
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "library", "memes")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/126 Safari/537.36"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf8", "replace")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    have = set(os.listdir(LIB)) if os.path.isdir(LIB) else set()
    have_names = set()
    for d in have:
        p = os.path.join(LIB, d, "meta.json")
        if os.path.exists(p):
            have_names.add(slug(json.load(open(p)).get("name", d)))
    out = {"imgflip_new": [], "knowyourmeme": [], "errors": []}
    try:
        h = get("https://imgflip.com/memetemplates?sort=top-new")
        names = re.findall(r'alt="([^"]+?) Meme Template"', h)
        out["imgflip_new"] = list(dict.fromkeys(html.unescape(n) for n in names))[:30]
    except Exception as e:
        out["errors"].append(f"imgflip: {e}")
    try:
        h = get("https://knowyourmeme.com/")
        ents = re.findall(r'href="/memes/([a-z0-9-]+)"', h)
        skip = {"memes", "popular", "trending", "all", "new", "submissions", "researching", "confirmed", "deadpool", "page"}
        out["knowyourmeme"] = [e for e in dict.fromkeys(ents) if e not in skip and not e.startswith("sort")][:30]
    except Exception as e:
        out["errors"].append(f"knowyourmeme: {e}")
    for k in ("imgflip_new", "knowyourmeme"):
        out[k] = [{"name": n, "in_library": slug(n) in have or slug(n) in have_names} for n in out[k]]
    if a.json:
        print(json.dumps(out, indent=2))
        return
    for k, title in (("imgflip_new", "imgflip, newest templates"), ("knowyourmeme", "Know Your Meme, on the homepage now")):
        print(f"\n{title}:")
        for it in out[k]:
            print(f"  {'[have] ' if it['in_library'] else '       '}{it['name']}")
    for e in out["errors"]:
        print("ERROR", e)
    print('\nTo add one: yt-dlp "ytsearch5:<name> green screen" --flat-playlist --print "%(id)s %(duration)s %(title)s"\n'
          "then meme_add.py <id> <url> --in/--out ... and look at preview.png")


if __name__ == "__main__":
    main()
