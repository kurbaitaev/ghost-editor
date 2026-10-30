#!/usr/bin/env python3
"""Shared parts of the still-image fetchers (wikimedia_fetch.py, google_images.py).

    image_sources.py both <words>          the query in English and in Russian (what every image search runs)

The order of image sources and their rules (references/broll.md 3, "Pictures"):
  1. Wikimedia Commons (wikimedia_fetch.py): archival / historical pictures first; public domain or CC, so they may go
     big (full screen when the 9:16 crop is >= 1080 wide). Licence, author and source page go into the manifest.
  2. Google Images (google_images.py, Apify actor hooli/google-images-scraper): what Commons misses. Free-licence
     hosts (Commons, Pexels, Unsplash, Pixabay) are ranked first; anything else is the creator's: FRAMED only.
A picture must say its line at a glance on a phone: a named, iconic subject (landmark, logo-free product, known place)
beats a generic mood; no dim/flat B&W that hides the subject.
Every search runs in English AND Russian (Russian finds things English misses), results merged.
Every download: no image under 1080 px on the short side (--min-image lower only for a picture shown framed small;
the row then says "small_frame_only"), and the people check (broll_vision.py check against people-rules.json; tiny
background figures count). A FAIL or unchecked row stays out of the edit.
"""
import json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_SHORT = 1080
FREE_HOSTS = ("wikimedia.org", "pexels.com", "unsplash.com", "pixabay.com", "rawpixel.com", "flickr.com")


def gemini_key():
    key = os.environ.get("GEMINI_API_KEY")
    envp = os.path.join(HERE, "..", ".env")
    if not key and os.path.exists(envp):
        m = re.search(r"GEMINI_API_KEY\s*=\s*['\"]?([^'\"\n]+)", open(envp).read())
        key = m and m.group(1).strip()
    return key


def is_ru(s):
    return bool(re.search(r"[а-яё]", s, re.I))


def translate(q, to):
    """one Gemini Flash call: a short image-search query in the other language ('ru' or 'en'); None if it fails"""
    key = gemini_key()
    if not key:
        return None
    lang = {"ru": "Russian", "en": "English"}[to]
    body = {"contents": [{"parts": [{"text": f"Translate this image-search query into {lang} as a natural search query "
                                              f"a native speaker would type. Proper names (villages, peoples, languages, people) are transliterated exactly, "
                                              f"never swapped for a similar-sounding name. Answer with the query only.\n\n{q}"}]}],
            "generationConfig": {"temperature": 0, "thinkingConfig": {"thinkingBudget": 0}}}
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        j = json.load(urllib.request.urlopen(req, timeout=60))
        return j["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"').splitlines()[0]
    except Exception as e:                                  # a missing translation only narrows the search
        print(f"(translation to {lang} failed: {str(e)[:80]}; searching one language)")
        return None


def both(q, other=None):
    """[(lang, query)]: the given query plus its other-language version (--ru / --en wins over the translation)"""
    first = ("ru" if is_ru(q) else "en", q)
    to = "en" if first[0] == "ru" else "ru"
    second = other or translate(q, to)
    return [first] + ([(to, second)] if second and second.strip().lower() != q.strip().lower() else [])


def interleave(*lists, key=lambda x: x):
    """merge result lists alternately (en, ru, en, ru ...), dropping repeats"""
    out, seen = [], set()
    for i in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if i < len(l) and key(l[i]) not in seen:
                seen.add(key(l[i])); out.append(l[i])
    return out


def probe_image(f):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                   "-of", "json", f], capture_output=True, text=True, check=True).stdout)
    w, h = j["streams"][0]["width"], j["streams"][0]["height"]
    return {"w": w, "h": h, "full_screen_ok": min(w, round(h * 9 / 16)) >= 1080}


def thumb(f, stem):
    jpg = f"{stem}_a.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", jpg], check=True)
    return [jpg]


def people_check(f):
    """broll_vision.py check: pass / FAIL / unchecked, plus its last line"""
    r = subprocess.run([sys.executable, os.path.join(HERE, "broll_vision.py"), "check", f], capture_output=True, text=True)
    return {0: "pass", 1: "FAIL"}.get(r.returncode, "unchecked"), ((r.stdout + r.stderr).strip().splitlines() or [""])[-1]


def size_verdict(info, min_image):
    """(ok, small_frame_only): under min_image -> refused; between min_image and 1080 -> framed small only"""
    short = min(info["w"], info["h"])
    return short >= min_image, short < MIN_SHORT


def free_host(url):
    return any(h in (url or "") for h in FREE_HOSTS)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "both":
        sys.exit(__doc__)
    for lang, q in both(" ".join(sys.argv[2:])):
        print(f"{lang}: {q}")
