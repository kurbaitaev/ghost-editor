"""Seoul list generator plumbing: the Seoul list house over an approved cut, for a Python generator (a reel's own short script).
A Seoul reel imports it instead of writing a lib of its own.

    import sys; sys.path.insert(0, "<skill>/recipes/seoul-list"); import seoul as L; from seoul import *
    P = setup("$P", cut="<clip>/edit", tag="seoul5")      # the project folder + the approved cut it reads; chdirs into $P
    spec = {"title": "...", "fps": 30, "clips": "clips", "tail": 0.7, "music": {"id": "silent-descent", "db": -20, "duck": -6},
            "sfx": "restrained", "shots": [{"clip": "face", "in": 0.0}],
            "beats": [{"type": "word", "at": W("same", 2.78), "to": W("thing", 3.9) - 0.04, "big": "the same thing"}]}
    vid("rain", src, tin, dur, line, why)       # a stock clip conformed to the plate (insert_prep.py), people + line check
    card("temple", src, line, why, box=(...))   # a stock image as framed -> stills/temple.jpg (graded, checked)
    write(spec)                                 # list.json -> node build.mjs -> index.html (+ every still's on-screen window)
    measure(spec)                               # the speaker's on-screen %, full-screen stock %, cutaways/min -> build/measure.json

    python3 <skill>/recipes/seoul-list/seoul.py --api      prints this API on one screen: read it instead of the source

Project ($P, one folder per reel; the generator lives in it or beside it). The approved cut ("cut", a folder, default $P itself)
holds assets/plate_alt.mp4 (or plate.mp4), assets/plate_wide.mp4 (the reference grade; default: the plate), assets/voice.wav and
build/words.cut.json (or words.json). setup() makes clips/ stills/ build/ review/ work/ in $P and puts there:
  clips/face.mp4             the approved plate as shot: re-encoded for 1 s keyframes only (no filter, never regraded) + a 1 s
                             held last frame (only ever under the black iMessage outro page)
  build/words.json           the cut's words (W() reads them)
  build/plate_stats.json     the plate's reference grade, computed here (no cache file beside the shared plate)
  assets/voice.wav           a symlink to the cut's voice: leave "voice" out of the spec (build.mjs reads assets/voice.wav)
write() also saves build/inserts_manifest.json: every stock insert (source, licence, the line it sits on, why, the people check).
Environment: the python for insert_prep.py / prep.py is $MEDIA_PY, else the running interpreter (run the generator under the
media venv: PIL, opencv, ffmpeg and node on PATH). The skill folder is found from this file; nothing here knows ~/reels.

House: the speaker's face is never regraded; every stock insert goes through insert_prep.py (grade conform to
the plate + the people / line gate: your people-rules.json, no posed faces); vid / card / still_clip(..., optional=True) return None
and log to REFUSED instead of stopping the build when the gate refuses; every insert is logged in INSERTS. Extra CSS (readable
notification / comment text, a halo on white words) and the per-still opacity windows (broll_vision / broll_qa read them) are
added to the built page by write().
"""
import functools
import inspect
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = HERE                                            # this recipe: build.mjs, prep.py
SK = os.path.abspath(os.path.join(HERE, "..", ".."))  # the skill: scripts/, library/
PY = os.environ.get("MEDIA_PY") or sys.executable
TAG = "seoul"       # the reel's label in the manifest; setup(tag=...) or `seoul.TAG = ...` sets it
REFUSED = []        # inserts the people / line gate refused (the reel falls back to the speaker's face or to type there)
FPS = 30
G = {}              # the reel's state: clip, P (project), cut, B (manifest folder), words, plate_frames, stats
INSERTS = []


def sh(cmd, **kw):
    """run a command; stop the build with its output tail if it fails"""
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(map(str, cmd))[:400]}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r


def norm(s):
    """a word as matched against the voice: lower case, Russian ё = е, punctuation dropped"""
    return re.sub(r"[^\w]+", "", str(s).lower().replace("ё", "е"))


def _first(folder, *names):
    return next((f"{folder}/{n}" for n in names if os.path.exists(f"{folder}/{n}")), f"{folder}/{names[0]}")


def setup(project, cut=None, tag=None, clip=None):
    """start a reel: project folder, the face plate from the approved cut, its words, the voice link, the reference grade; chdir in"""
    global TAG
    if tag:
        TAG = tag
    P = os.path.abspath(os.path.expanduser(project))
    cut = os.path.abspath(os.path.expanduser(cut)) if cut else P
    for d in ("clips", "stills", "build", "review", "work"):
        os.makedirs(f"{P}/{d}", exist_ok=True)
    G.update(clip=clip or os.path.basename(P), P=P, cut=cut, B=f"{P}/build")
    plate = _first(f"{cut}/assets", "plate_alt.mp4", "plate.mp4")
    wide = _first(f"{cut}/assets", "plate_wide.mp4", os.path.basename(plate))
    face = f"{P}/clips/face.mp4"
    # the approved cut, as shot: re-encoded only for 1 s keyframes (no filter, same colour tags), never regraded
    if not os.path.exists(face) or os.path.getmtime(face) < os.path.getmtime(plate) or not os.path.exists(face + '.held'):
        # + 1 s held last frame: only ever under the black iMessage outro page (the outro card's own video stops before it)
        sh(["ffmpeg", "-v", "error", "-y", "-i", plate, "-an", "-vf", "tpad=stop_mode=clone:stop_duration=1.0", "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-g", "30",
            "-keyint_min", "30", "-bf", "2", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
            "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", face])
        open(face + ".held", "w").write("plate_alt + 1.0 s cloned last frame, 1 s keyframes, no grade")
    wsrc = _first(f"{cut}/build", "words.cut.json", "words.json")
    if os.path.abspath(wsrc) != os.path.abspath(f"{P}/build/words.json"):
        shutil.copy(wsrc, f"{P}/build/words.json")
    ws = [w for s in json.load(open(wsrc))["segments"] for w in s["words"]]
    G["words"] = [{"w": w["word"].strip(), "n": norm(w["word"]), "s": w["start"], "e": w["end"]} for w in ws]
    G["plate_frames"] = int(round(float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", face]).stdout) * FPS))
    vsrc = f"{cut}/assets/voice.wav"
    if os.path.exists(vsrc) and not os.path.lexists(f"{P}/assets/voice.wav"):
        os.makedirs(f"{P}/assets", exist_ok=True)
        os.symlink(vsrc, f"{P}/assets/voice.wav")
    st = f"{P}/build/plate_stats.json"
    if not os.path.exists(st):          # reference grade of the plate as shot (wide), computed here: no cache file beside the shared plate
        sh([PY, "-c", f"import sys, json; sys.path.insert(0, '{SK}/scripts'); import grade_lib as g; "
            f"json.dump(g.plate_stats('{wide}', cache=False), open('{st}', 'w'))"])
    G["stats"] = st
    os.chdir(P)
    return P


def W(word, near, end=False):
    """start (or end) of the spoken word nearest to `near` (VO seconds); stops the build if it is not in the voice"""
    k = norm(word)
    c = [w for w in G["words"] if w["n"] == k]
    if not c:
        sys.exit(f"word {word!r} not in the voice")
    w = min(c, key=lambda x: abs(x["s"] - near))
    if abs(w["s"] - near) > 3:
        sys.exit(f"word {word!r} nearest to {near} is at {w['s']}")
    return round(w["e"] if end else w["s"], 3)


def fr(t):
    """a time snapped to the frame grid"""
    return round(t * FPS) / FPS


def _side(path):
    return json.load(open(path + ".json")) if os.path.exists(path + ".json") else {}


def _log(name, kind, src, line, why, used, extra=None):
    meta = {}
    sj = os.path.splitext(src)[0] + ".src.json"
    if os.path.exists(sj):
        meta = json.load(open(sj))
    INSERTS.append({"name": name, "kind": kind, "file": used, "src": src, "line": line, "why": why,
                    "source": meta.get("source") or extra.get("source") if extra else meta.get("source"),
                    "url": meta.get("page") or (extra or {}).get("url"), "author": meta.get("author") or (extra or {}).get("author"),
                    "licence": meta.get("licence") or (extra or {}).get("licence"), **({k: v for k, v in (extra or {}).items() if k not in ("source", "url", "author", "licence")})})


def _rule_ids():
    """the ids of the B-roll people rules (people-rules.json, or $BROLL_PEOPLE_RULES): the keys broll_vision answers"""
    p = os.environ.get("BROLL_PEOPLE_RULES") or f"{SK}/people-rules.json"
    try:
        return [r["id"] for r in json.load(open(p)).get("rules", []) if isinstance(r, dict) and r.get("id")]
    except (OSError, ValueError):
        return []


def _vision_of(path):
    s = _side(path)
    v = s.get("vision") or {}
    return {k: v.get(k) for k in (*_rule_ids(), "people", "shows", "matches", "why")} if isinstance(v, dict) else {"vision": v}


def optional(fn):
    """vid/card/still_clip(..., optional=True): a refused insert returns None (logged in REFUSED) instead of stopping the build"""
    @functools.wraps(fn)
    def w(*a, optional=False, **k):
        try:
            return fn(*a, **k)
        except SystemExit as e:
            if not optional:
                raise
            msg = str(e)
            REFUSED.append({"name": a[0], "src": a[1], "reason": msg[msg.rfind("\n\n") + 2:][:400] if "\n\n" in msg else msg[-400:]})
            print(f"REFUSED {a[0]}: {REFUSED[-1]['reason'][:200]}")
            return None
    return w


@optional
def vid(name, src, tin, dur, line, why, focus="0.5,0.5", crop=None, sat=1.1, extra=None):
    """a stock video insert for one slot: cut, conform to the plate, 9:16 1080x1920, people + line check"""
    out = f"{G['P']}/clips/{name}.mp4"
    key = json.dumps([src, tin, dur, line, focus, crop, sat])
    s = _side(out)
    if not (os.path.exists(out) and s.get("_key") == key):
        cmd = [PY, f"{SK}/scripts/insert_prep.py", src, out, "--in", str(tin), "--dur", f"{dur:.3f}", "--ref-stats", G["stats"],
               "--line", line, "--kind", "stock", "--focus", focus, "--sat-target", str(sat)]
        if crop:
            cmd += ["--crop", crop]
        r = sh(cmd)
        s = _side(out)
        s["_key"] = key
        json.dump(s, open(out + ".json", "w"), ensure_ascii=False, indent=1)
    _log(name, "video", src, line, why, out, {**(extra or {}), "in": tin, "dur": dur, "vision": _vision_of(out),
                                             "grade": (s.get("grade") or {}).get("verdict")})
    return name


def _crop(src, box, size, out):
    from PIL import Image
    im = Image.open(src).convert("RGB")
    W0, H0 = im.size
    if box:
        x0, y0, x1, y1 = box
        im = im.crop((int(x0 * W0), int(y0 * H0), int(x1 * W0), int(y1 * H0)))
    if size:                          # cover-crop to the aspect, centred, then scale to size
        tw, th = size
        ar = tw / th
        w, h = im.size
        if w / h > ar:
            nw = int(h * ar); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / ar); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        if im.size[0] < tw:
            print(f"WARNING {os.path.basename(src)}: crop {im.size} smaller than {size}", file=sys.stderr)
        im = im.resize((tw, th), Image.LANCZOS)
    im.save(out, quality=95)
    return out


@optional
def card(name, src, line, why, box=None, size=(1584, 892), sat=1.0, extra=None):
    """a stock image as framed in the reel (crop -> grade onto the plate -> people + line check) -> stills/<name>.jpg"""
    work = _crop(src, box, size, f"{G['P']}/work/{name}.jpg")
    out = f"{G['P']}/stills/{name}.jpg"
    key = json.dumps([src, os.path.getmtime(src), box, size, line, sat])
    s = _side(out)
    if not (os.path.exists(out) and s.get("_key") == key):
        sh([PY, f"{SK}/scripts/insert_prep.py", work, out, "--ref-stats", G["stats"], "--line", line, "--kind", "stock", "--sat-target", str(sat)])
        s = _side(out)
        s["_key"] = key
        s["orig"] = src
        json.dump(s, open(out + ".json", "w"), ensure_ascii=False, indent=1)
    _log(name, "image card", src, line, why, out, {**(extra or {}), "box": box, "vision": _vision_of(out), "grade": (s.get("grade") or {}).get("verdict")})
    return f"stills/{name}.jpg"


@optional
def still_clip(name, src, line, why, box=None, dur=3.0, sat=1.1, extra=None):
    """a full-screen stock still: framed 9:16 (1080x1920), graded and checked as a still, then a clip the montage can cut to
    (list.json gives it a slow push with zoom)"""
    st = card(name + "_full", src, line, why, box=box, size=(1080, 1920), sat=sat, extra={**(extra or {}), "fullscreen": True})
    INSERTS[-1]["kind"] = "image full-screen"
    out = f"{G['P']}/clips/{name}.mp4"
    n = int(round(dur * FPS)) + 2
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(f"{G['P']}/{st}"):
        sh(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", f"{G['P']}/{st}", "-frames:v", str(n), "-r", "30", "-c:v", "libx264", "-crf", "14",
            "-g", "30", "-pix_fmt", "yuv420p", "-vf", "scale=1080:1920:out_range=tv,format=yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
            "-color_trc", "bt709", "-color_range", "tv", out])
    s = _side(f"{G['P']}/{st}")
    json.dump({**s, "src": src, "kind": "stock", "made_from_still": st}, open(out + ".json", "w"), ensure_ascii=False, indent=1)
    INSERTS[-1]["file"] = out
    return name


def frame_of(src_clip, t, out_name):
    """one frame of a prepared clip (outro cards)"""
    out = f"{G['P']}/stills/{out_name}.jpg"
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", f"{G['P']}/clips/{src_clip}.mp4", "-frames:v", "1", "-q:v", "2", out])
    return f"stills/{out_name}.jpg"


def copy_still(rel, name):
    """a second file of a still (an outro card that repeats a collage photo: one src per <img>)"""
    out = f"stills/{name}.jpg"
    shutil.copy(f"{G['P']}/{rel}", f"{G['P']}/{out}")
    if os.path.exists(f"{G['P']}/{rel}.json"):
        shutil.copy(f"{G['P']}/{rel}.json", f"{G['P']}/{out}.json")
    return out


def avatar(t, out="stills/avatar.jpg"):
    """the speaker's own face as a small round avatar (240 px, under the QA's 300 px insert size; it is not stock): clips/face.mp4 at t -> stills/avatar.jpg"""
    sh([PY, f"{R}/prep.py", "avatar", f"{G['P']}/clips/face.mp4", str(t), f"{G['P']}/{out}", "--size", "240"])
    return out


EXTRA_CSS = """
/* seoul3 additions */
.on-foot { text-shadow: 0 0 2px rgba(0,0,0,.9), 0 0 6px rgba(0,0,0,.7), 0 0 14px rgba(0,0,0,.45), 0 3px 6px rgba(0,0,0,.4), 0 8px 40px rgba(0,0,0,.5); }
.nt { width: 990px; padding: 34px 40px 38px 32px; border-radius: 50px; }
.nt-ic { flex: 0 0 108px; width: 108px; height: 108px; border-radius: 26px; }
.nt-hd { font-size: 32px; } .nt-hd b { font-size: 30px; }
.nt-title { font-size: 60px; } .nt-text { font-size: 50px; line-height: 1.18; }
.cm { width: 880px; } .cm-text { font-size: 52px; } .cm-reply { font-size: 32px; }
"""


def write(spec):
    """spec -> list.json, node build.mjs, then the readability CSS + every still's on-screen window; saves build/inserts_manifest.json"""
    P = G["P"]
    json.dump(spec, open(f"{P}/list.json", "w"), ensure_ascii=False, indent=1)
    r = subprocess.run(["node", f"{R}/build.mjs", P], capture_output=True, text=True)
    print(r.stdout[-6000:])
    if r.returncode:
        sys.exit("build failed:\n" + r.stderr[-3000:])
    # readability on light clothing and phone-size UI text (captions >= 48 px, readable on a light top):
    # a stronger dark halo on white words, bigger notification / comment text. Appended to the built page only.
    html = open(f"{P}/index.html", encoding="utf-8").read()
    html = html.replace("</style>", EXTRA_CSS + "</style>", 1)
    # give every still its real on-screen window in the timeline (an id + an opacity set at its start and end, inside the
    # page that already shows / hides it): broll_vision picks and broll_qa match read windows from opacity sets, and
    # build.mjs's pages use visibility, so without this every still was checked against the reel's first words
    bj = json.load(open(f"{P}/build/beats.json"))
    win = {k["id"]: (k["t0"], k["t1"]) for k in bj["beats"]}
    sets, k = [], 0
    for i, b in enumerate(spec["beats"]):
        t0, t1 = win.get(f"b{i}", (None, None))
        if t0 is None:
            continue
        used = []
        if b.get("type") == "collage" and b.get("photo"):
            ph = b["photo"]
            used.append((ph["src"] if isinstance(ph, dict) else ph, t0, t1))
        if b.get("type") == "window":
            its = b["items"]
            for j, it in enumerate(its):
                used.append((it["img"], it["at"], its[j + 1]["at"] if j + 1 < len(its) else t1))
        if b.get("type") == "imessage":
            used += [(c, t0, t1) for c in b.get("cards", [])]
        if b.get("type") == "comment" and b.get("avatar"):
            used.append((b["avatar"], t0, t1))
        for src, a, e in used:
            rel = "assets/stills/" + os.path.basename(src)
            tag = f'<img src="{rel}"'
            if tag in html:
                k += 1
                html = html.replace(tag, f'<img id="st{k}" src="{rel}"', 1)
                sets.append(f'tl.set("#st{k}", {{"opacity": 1}}, {a:.3f}); tl.set("#st{k}", {{"opacity": 0}}, {e:.3f});')
    if sets:
        html = html.replace('window.__timelines["main"] = tl;', " ".join(sets) + '\n    window.__timelines["main"] = tl;', 1)
    open(f"{P}/index.html", "w", encoding="utf-8").write(html)
    man = {"clip": G["clip"], "tag": TAG, "note": "every stock insert of this reel: source, licence, the line it sits on, why, the vision (people) check",
           "inserts": INSERTS, "refused": REFUSED}
    json.dump(man, open(f"{G['B']}/inserts_manifest.json", "w"), ensure_ascii=False, indent=1)
    return P


def measure(spec):
    """the speaker's on-screen %, full-screen stock %, cutaways/min from the built beats.json (face base shots minus full-page scenes)"""
    P = G["P"]
    bj = json.load(open(f"{P}/build/beats.json"))
    T = bj["total"]
    n = int(round(T * FPS))
    face = [False] * n
    stock = [False] * n
    for s in bj["shots"]:
        for f in range(int(round(s["t0"] * FPS)), int(round(s["t1"] * FPS))):
            if f < n:
                face[f] = s["clip"] == "face"
                stock[f] = s["clip"] != "face"
    for b in bj["beats"]:
        if b["type"] in ("collage", "flash", "imessage", "triptych", "window"):
            for f in range(int(round(b["t0"] * FPS)), min(n, int(round(b["t1"] * FPS)))):
                face[f] = False
                stock[f] = b["type"] == "triptych"
    runs, prev = 0, True
    for f in range(n):
        if prev and not face[f]:
            runs += 1
        prev = face[f]
    pages = n - sum(face) - sum(stock)
    m = {"total_s": round(T, 2), "face_pct": round(100 * sum(face) / n, 1), "fullscreen_stock_pct": round(100 * sum(stock) / n, 1),
         "pages_pct": round(100 * pages / n, 1), "cutaways": runs, "cutaways_per_min": round(runs / (T / 60), 1),
         "stock_items": len({i["src"] for i in INSERTS})}
    json.dump(m, open(f"{P}/build/measure.json", "w"), indent=1)
    print("MEASURE", m)
    return m


def api():
    """print the API: signatures and the first line of each docstring"""
    print(__doc__.split("\n\nProject")[0])
    print("\n== functions (vid / card / still_clip also take optional=False)")
    for name, fn in list(globals().items()):
        if name.startswith("_") or name in ("api", "functools", "inspect") or not inspect.isfunction(fn) or fn.__module__ != __name__:
            continue
        sig = inspect.signature(fn)          # follows functools.wraps to the real signature
        if hasattr(fn, "__wrapped__"):
            sig = sig.replace(parameters=[*sig.parameters.values(), inspect.Parameter("optional", inspect.Parameter.KEYWORD_ONLY, default=False)])
        doc = (inspect.getdoc(fn) or "").split("\n")[0]
        print(f"  {name}{sig}\n      {doc}")
    print("\n== state\n  G (clip, P, cut, B, words, plate_frames, stats), INSERTS, REFUSED, FPS, TAG, PY, SK (skill dir), R (this recipe), EXTRA_CSS")


if __name__ == "__main__":
    if "--api" in sys.argv:
        api()
    else:
        print(__doc__)
