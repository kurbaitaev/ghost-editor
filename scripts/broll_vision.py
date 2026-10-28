#!/usr/bin/env python3
"""Vision checks on every B-roll shot and stock image (references/broll.md section 0):

- People: the rules in people-rules.json (each one a question the model answers true/false per shot, optionally an
  attribute asked of every visible person, e.g. "not clearly male counts"). No rules = nothing to break.
- Match: the shot shows what the line it sits on says (yes / partly / no).

    broll_vision.py check CLIP [--in 3.5 --dur 2.0] [--line "..."]          # one clip or still; exit 1 = rule broken, 2 = unchecked
    broll_vision.py picks --project $P [--words build/words.cut.json]       # the pick sheet the user confirms BEFORE the render
                                                                            #   -> build/broll-picks.jpg + .json
    broll_vision.py confirm CLIP --note "their words"                       # the user looked at a flagged shot and said it's fine:
                                                                            #   the QA and insert_prep then pass it (recorded)

Gemini (GEMINI_API_KEY, or the skill's .env) reads a sheet of 6 frames from the window the reel uses. Answers are
cached in library/vision-cache/ by file, window, line and prompt version, so broll_qa.py (which runs the same check on
the render's composition: checks `people` and `match`) costs nothing for shots already checked. A failed call is
retried; if it still fails the shot is UNCHECKED, never passed. Model: BROLL_VISION_MODEL (default gemini-2.5-flash).
Rules: BROLL_PEOPLE_RULES (default people-rules.json next to SKILL.md); a change to the rules re-asks every shot.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade_lib as G  # noqa: E402

CACHE = os.path.join(HERE, "..", "library", "vision-cache")
PROMPT_V = 2
MODEL = os.environ.get("BROLL_VISION_MODEL", "gemini-2.5-flash")
STILL = re.compile(r"\.(jpe?g|png|webp|heic)$", re.I)

RULES_PATH = os.environ.get("BROLL_PEOPLE_RULES") or os.path.join(HERE, "..", "people-rules.json")
LEGACY_SIG = "ff4ae4d488c0"     # the v2 prompt from before the rules were a file: its cached answers stay valid


def load_rules(path=RULES_PATH):
    """people-rules.json -> dict; a missing file = no people rules (the match check still runs)"""
    cfg = {"title": "B-roll people rules", "summary": "no people rules set", "fix": "Replace the shot.",
           "context": "a short talking-head video", "language": "", "rules": []}
    if os.path.exists(path):
        cfg.update(json.load(open(path, encoding="utf8")))
    for r in cfg["rules"]:
        r.setdefault("label", r["id"].upper())
        r.setdefault("where", "which frames and what (empty string if none).")
    return cfg


RULES = load_rules()


def build_prompt(cfg):
    """the prompt template ({n}, {line_part}) and the line part ({line}) for these rules"""
    keys = "".join(f'"{r["id"]}": {r["ask"]}\n"{r["id"]}_where": {r["where"]}\n' for r in cfg["rules"])
    attrs = "".join(f', "{r["person"]["key"]}": {r["person"]["values"]}' for r in cfg["rules"] if r.get("person"))
    prompt = ("These are {n} frames, left to right and top to bottom, from ONE B-roll shot in " + cfg["context"] + ". "
              "Reply as JSON only, with these keys:\n" + keys.replace("{", "{{").replace("}", "}}") +
              '"people": a list with one entry per person or body part visible (an empty list if none):\n'
              '  {{"what": briefly, e.g. "hands planing wood"' + attrs.replace("{", "{{").replace("}", "}}") + '}}.\n'
              '"shows": one plain sentence: what the shot shows (place, objects, action, light).\n{line_part}')
    lang = f' ({cfg["language"]})' if cfg.get("language") else ""
    line_part = ('"matches": does the shot show what this spoken line is about: "yes", "partly" or "no". '
                 'The line' + lang + ': «{line}».\n"why": one short sentence.')
    return prompt, line_part


PROMPT, LINE_PART = build_prompt(RULES)
RULES_SIG = hashlib.sha1(" ".join((PROMPT + "\n" + LINE_PART).split()).encode()).hexdigest()[:12]

_client = None
_lock = threading.Lock()


def client():
    global _client
    with _lock:
        if _client is None:
            from google import genai
            key = os.environ.get("GEMINI_API_KEY")
            envp = os.path.join(HERE, "..", ".env")
            if not key and os.path.exists(envp):
                m = re.search(r"GEMINI_API_KEY\s*=\s*['\"]?([^'\"\n]+)", open(envp, encoding="utf-8").read())
                key = m.group(1).strip() if m else None
            if not key:
                raise RuntimeError("no GEMINI_API_KEY (env or the skill's .env)")
            c = genai.Client(api_key=key)
            c.models.generate_content(model=MODEL, contents="Reply with the single word ok.")   # key check, one call
            _client = c
        return _client


def frames(path, tin=0.0, dur=None, n=6, short=540):
    """BGR frames over the window the reel uses (a still: the image itself)"""
    if STILL.search(path):
        im = cv2.imread(path, cv2.IMREAD_COLOR)
        if im is None:
            raise RuntimeError(f"unreadable image {path}")
        s = 1280 / max(im.shape[:2])
        return [cv2.resize(im, (int(im.shape[1] * s), int(im.shape[0] * s)), interpolation=cv2.INTER_AREA) if s < 1 else im]
    info = G.probe(path)
    dur = max(0.1, min(dur if dur else info["dur"], info["dur"] - tin))
    w, h = G.fit(info, short)
    out = []
    for i in range(n):
        t = tin + dur * (i + 0.5) / n
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf",
                            f"scale={w}:{h}:flags={G.SCALE_FLAGS}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True)
        if len(r.stdout) >= w * h * 3:
            out.append(np.frombuffer(r.stdout[:w * h * 3], np.uint8).reshape(h, w, 3))
    if not out:
        raise RuntimeError(f"no frames decoded from {path}")
    return out


def grid(fr, cols=3):
    h = max(f.shape[0] for f in fr)
    fr = [cv2.resize(f, (int(f.shape[1] * h / f.shape[0]), h)) for f in fr]
    w = max(f.shape[1] for f in fr)
    rows = [fr[i:i + cols] for i in range(0, len(fr), cols)]
    canvas = np.full((h * len(rows) + 6 * (len(rows) - 1), w * min(cols, len(fr)) + 6 * (min(cols, len(fr)) - 1), 3), 255, np.uint8)
    for r, row in enumerate(rows):
        for c, f in enumerate(row):
            canvas[r * (h + 6):r * (h + 6) + h, c * (w + 6):c * (w + 6) + f.shape[1]] = f
    return canvas


def key_of(path, tin, dur, line):
    st = os.stat(path)
    s = f"{os.path.realpath(path)}|{st.st_size}|{st.st_mtime_ns}|{tin:.2f}|{(dur or 0):.2f}|{line or ''}|{PROMPT_V}|{MODEL}"
    if RULES_SIG != LEGACY_SIG:
        s += "|" + RULES_SIG
    return hashlib.sha1(s.encode()).hexdigest()


def confirm_path(path):
    st = os.stat(path)
    return os.path.join(CACHE, "ok-" + hashlib.sha1(f"{os.path.realpath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest() + ".json")


def confirmed(r, path):
    """the user's recorded OK on a flagged shot (broll_vision.py confirm): kept next to the verdict, never instead of it"""
    try:
        cp = confirm_path(path)
    except OSError:
        return r
    if os.path.exists(cp):
        try:
            r = dict(r, confirmed=json.load(open(cp, encoding="utf-8")).get("note", "yes"))
        except (OSError, json.JSONDecodeError):
            pass
    return r


def check(path, tin=0.0, dur=None, line=None):
    return confirmed(_check(path, tin, dur, line), path)


def _check(path, tin=0.0, dur=None, line=None):
    """{<rule id>: broken?, <rule id>_where, 'people', 'shows', 'matches'?, 'why'?, 'ok': rules kept} or {'error': ...} (= unchecked)"""
    line = re.sub(r"\s+", " ", line or "").strip() or None
    try:
        k = key_of(path, tin, dur, line)
    except OSError as e:
        return {"error": str(e)}
    cp = os.path.join(CACHE, k + ".json")
    if os.path.exists(cp):
        try:
            return json.load(open(cp, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    try:
        fr = frames(path, tin, dur)
        ok, buf = cv2.imencode(".jpg", grid(fr), [cv2.IMWRITE_JPEG_QUALITY, 88])
    except Exception as e:      # noqa: BLE001
        return {"error": f"frames: {e}"}
    prompt = PROMPT.format(n=len(fr), line_part=LINE_PART.format(line=line) if line else "")
    err = None
    models = [MODEL] + [m for m in ("gemini-2.5-pro",) if m != MODEL]
    for wait in (0, 3, 8, 20):
        time.sleep(wait)
        model = models[0]
        try:
            from google.genai import types
            safe = [types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in
                    ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")]
            r = client().models.generate_content(model=model, contents=[types.Part.from_bytes(data=buf.tobytes(), mime_type="image/jpeg"), prompt],
                                                 config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0,
                                                                                    safety_settings=safe))
            if not r.text:          # blocked: try the other model once, then give the reason (no retry loop)
                fb = getattr(r, "prompt_feedback", None)
                fr = getattr(r.candidates[0], "finish_reason", None) if getattr(r, "candidates", None) else None
                models.pop(0)
                if models:
                    continue
                return {"error": f"no answer (blocked: {getattr(fb, 'block_reason', None) or fr}); unchecked = fails: drop the shot"}
            j = json.loads(r.text)
            if isinstance(j, list) and j:
                j = j[0]
            if not isinstance(j, dict) or not isinstance(j.get("people"), list) \
                    or any(not isinstance(j.get(ru["id"]), bool) for ru in RULES["rules"]):
                raise ValueError(f"bad answer: {r.text[:200]}")
            ppl = [p for p in j["people"] if isinstance(p, dict)]
            if line and str(j.get("matches", "")).lower() not in ("yes", "partly", "no"):
                raise ValueError(f"no match verdict: {r.text[:200]}")
            res = {}
            for ru in RULES["rules"]:
                pa = ru.get("person")      # a person whose attribute is outside `pass` (or can't be told) breaks the rule
                odd = [str(p.get("what", "")) for p in ppl if pa and str(p.get(pa["key"], "unclear")).lower() not in pa["pass"]]
                res[ru["id"]] = j[ru["id"]] or bool(odd)
                res[ru["id"] + "_where"] = (str(j.get(ru["id"] + "_where", "")) or
                                            (pa.get("note", pa["key"]) + ": " + "; ".join(odd) if odd else ""))[:200]
            keys = [ru["person"]["key"] for ru in RULES["rules"] if ru.get("person")]
            res.update({"people": "; ".join(str(p.get("what", "")) + (f" ({', '.join(str(p.get(k, '?')) for k in keys)})" if keys else "")
                                            for p in ppl)[:240] or "none",
                        "shows": str(j.get("shows", ""))[:240], "model": model})
            if line:
                res.update({"line": line, "matches": str(j["matches"]).lower(), "why": str(j.get("why", ""))[:200]})
            res["ok"] = not any(res[ru["id"]] for ru in RULES["rules"])
            os.makedirs(CACHE, exist_ok=True)
            tmp = cp + f".{os.getpid()}.tmp"
            json.dump(res, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, cp)
            return res
        except RuntimeError as e:          # no key: no point retrying
            return {"error": str(e)}
        except Exception as e:             # noqa: BLE001  transient: retry
            err = f"{type(e).__name__}: {str(e)[:200]}"
    return {"error": err}


def check_many(jobs, workers=4):
    """jobs: [(path, tin, dur, line)] -> results in the same order"""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda j: check(*j), jobs))


def words_in(words, t0, t1, before=1.0, after=0.3):
    """the spoken words under a shot (B-roll lands a beat after the word, so look a second back)"""
    if not words:
        return None
    return " ".join(w["w"] for w in words if w.get("s") is not None and w["e"] > t0 - before and w["s"] < t1 + after) or None


def layer_job(l, words):
    """(path, in, dur, line) for a composition layer (broll_qa.composition): the window the reel uses and the words under it.
    Stills and blurred backdrops carry no timing in the composition: people rules only."""
    if l["kind"] == "backdrop":
        return (l["src"], 0.0, None, None) if l["still"] else (l["src"], l["ms"], l["dur"], None)
    if l["still"]:     # timed by the timeline (broll_qa.still_windows) or, in the QA, by where it shows in the render
        lines = [words_in(words, a, min(b, a + 2.5)) for a, b in l.get("windows") or []]   # a card lands on its word
        return (l["src"], 0.0, None, " / ".join(x for x in lines if x) or None)
    return (l["src"], l["ms"], l["dur"], words_in(words, l["start"], l["start"] + l["dur"]))


def bad(r):
    """breaks the rules and the user has not confirmed it"""
    return "error" not in r and not r.get("confirmed") and (not r["ok"] or r.get("matches") == "no")


def verdict(r):
    if "error" in r:
        return "UNCHECKED"
    v = []
    for ru in RULES["rules"]:
        if r.get(ru["id"]):
            v.append(ru["label"] + ": " + (r.get(ru["id"] + "_where") or r["people"]))
    if r.get("matches") == "no":
        v.append("DOESN'T MATCH THE LINE")
    elif r.get("matches") == "partly":
        v.append("matches partly")
    if r.get("confirmed") and v:
        v.append(f"CONFIRMED by the user: {r['confirmed']}")
    return "; ".join(v) or "ok"


def font(px):
    from PIL import ImageFont
    for p in ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def cmd_picks(a):
    from PIL import Image, ImageDraw
    import broll_qa as Q
    comp = Q.composition(a.project)
    if not comp:
        sys.exit(f"no composition in {a.project}")
    words = Q.load_words(a.words, a.project)
    lay = [l for l in comp["layers"] if l["kind"] in ("insert", "backdrop")]
    if not lay:
        sys.exit("no B-roll layers in the composition")
    jobs = [layer_job(l, words) for l in lay]
    res = check_many(jobs)
    W, TH, F = 1100, 230, font(22)
    rows, out = [], []
    for l, j, r in zip(lay, jobs, res):
        try:
            fr = frames(j[0], j[1], j[2], n=4, short=360)
        except Exception:                  # noqa: BLE001
            fr = [np.zeros((360, 360, 3), np.uint8)]
        strip = cv2.cvtColor(grid(fr, cols=4), cv2.COLOR_BGR2RGB)
        s = min(1.0, W / strip.shape[1], 260 / strip.shape[0])
        strip = cv2.resize(strip, (int(strip.shape[1] * s), int(strip.shape[0] * s)))
        v = verdict(r)
        bad_ = bad(r) or "error" in r
        img = Image.new("RGB", (W, strip.shape[0] + TH), (255, 235, 235) if bad_ else (255, 255, 255))
        img.paste(Image.fromarray(strip), (0, 0))
        d = ImageDraw.Draw(img)
        when = (", ".join(f"{a:.1f}-{b:.1f} s" for a, b in l["windows"][:3]) if l.get("windows") else "untimed still") if l["still"] \
            else f"{l['start']:.1f}-{l['start'] + l['dur']:.1f} s"
        txt = [f"{l['id']}  ·  {when}  ·  {l['origin']['kind']}: {os.path.basename(l['origin']['src'] or l['src'])}",
               f"line: {j[3] or '(no words found under it)'}",
               f"shows: {r.get('shows', '')}",
               f"people: {r.get('people', '')}",
               f"check: {v}" + (f"  ({r.get('why', '')})" if r.get("why") else "") + (f"  {r['error']}" if "error" in r else "")]
        y = strip.shape[0] + 8
        for t in txt:
            d.text((10, y), t[:95], fill=(170, 0, 0) if t.startswith("check") and bad_ else (20, 20, 20), font=F)
            y += 34
        rows.append(img)
        out.append({"layer": l["id"], "src": l["src"], "kind": l["origin"]["kind"], "start": l["start"], "dur": l["dur"],
                    "windows": l.get("windows"), "line": j[3],
                    "verdict": v, "flagged": bad(r) or "error" in r,
                    **{k: r.get(k) for k in [ru["id"] for ru in RULES["rules"]] + ["people", "shows", "matches", "why", "error", "confirmed"]}})
    pairs = [rows[i:i + 2] for i in range(0, len(rows), 2)]
    sheet = Image.new("RGB", (2 * W + 10, sum(max(r.height for r in p) + 10 for p in pairs)), (120, 120, 120))
    y = 0
    for p in pairs:
        for c, r in enumerate(p):
            sheet.paste(r, (c * (W + 10), y))
        y += max(r.height for r in p) + 10
    o = a.out or os.path.join(a.project, "build", "broll-picks.jpg")
    os.makedirs(os.path.dirname(os.path.abspath(o)), exist_ok=True)
    sheet.save(o, quality=85)
    json.dump(out, open(os.path.splitext(o)[0] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_bad = sum(1 for x in out if x["flagged"])
    print(f"{len(out)} B-roll shot(s), {n_bad} flagged -> {o}")
    for x in out:
        if x["verdict"] != "ok":
            print(f"  {x['layer']}: {x['verdict']}")
    print("Show the user this sheet and WAIT for their yes before rendering (people rules + one shot per line).")
    sys.exit(1 if n_bad else 0)


def confirm(path, note):
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"src": os.path.realpath(path), "note": note, "at": time.strftime("%Y-%m-%d %H:%M")}, open(confirm_path(path), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def cmd_confirm(a):
    if not a.note.strip():
        sys.exit("--note: the user's words (who checked, what they said)")
    confirm(a.clip, a.note.strip())
    print(f"recorded: {a.clip} confirmed ({a.note.strip()})")


def cmd_check(a):
    r = check(a.clip, a.tin, a.dur, a.line)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    print(verdict(r))
    sys.exit(2 if "error" in r else (1 if bad(r) else 0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("check"); p.add_argument("clip"); p.add_argument("--in", dest="tin", type=float, default=0.0)
    p.add_argument("--dur", type=float); p.add_argument("--line")
    p = sp.add_parser("picks"); p.add_argument("--project", required=True); p.add_argument("--words"); p.add_argument("--out")
    p = sp.add_parser("confirm"); p.add_argument("clip"); p.add_argument("--note", required=True)
    a = ap.parse_args()
    {"check": cmd_check, "picks": cmd_picks, "confirm": cmd_confirm}[a.cmd](a)


if __name__ == "__main__":
    main()
