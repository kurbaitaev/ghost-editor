#!/usr/bin/env python3
"""Pick each reel picture on evidence: brief -> pull candidates -> score them -> pick (or flag) -> contact sheet.
Pictures should represent what the line says: review them and score them before choosing.

    image_pick.py brief $P --line harbour="The old harbour fed the whole town…" [--line ...] --frame "colour print ~800 px wide"
                                     draft $P/build/picture-brief.json with Gemini; READ AND FIX it before pulling:
                                     per line the concrete subject it names (place, object, person type, era),
                                     2-3 search phrases in EN and RU, and what would be wrong
    image_pick.py pull $P [--dir $P/broll] [--per 3] [--only ID]
                                     6-10 candidates per line: Wikimedia (each EN/RU pair), Google (first pair);
                                     each download people-checked and >= 1080 px (the fetchers' rules); rows get beat=<line id>
    image_pick.py tag $P <line id> <row id> [...]     add rows already in the manifest as candidates of a line
    image_pick.py score $P [--only ID] [--again]      vision scores per candidate (cached by file + brief line)
    image_pick.py pick $P                              top per line, or FLAG the line (no picture beats a weak one)
    image_pick.py sheet $P [-o file.jpg]               contact sheet: every candidate, its scores, the pick (default
                                                       $P/build/picture-picks.jpg; copy it next to the preview)

Scores (0-5, Gemini on the full still plus a phone-size copy of it, as it will sit in the frame the brief names):
  line     says the line at a glance at phone size: a stranger names the subject in under a second
  specific the subject the line names (that place, that object, that era), not a generic mood
  quality  sharp, well exposed, enough resolution for the frame
  frame    still readable after the style's treatment (B&W / sepia / tint, print size)
  clash    pass/fail: text, watermarks or logos that clash (a shop's watermark, a brand that is not the line's)
  people   pass/fail: the people rules (broll_vision.py check, already in the row)
Pick: people pass, clash pass, line >= 4; ranked by line, specific, frame, quality; when the top scores tie, the tied
ones (up to 4) are shown side by side at phone size and the model picks the fastest read (brief "final"), else free
licence and size. Below 4: the line is FLAGGED and
gets no picture unless the user says otherwise. Rows keep "scores": {<line id>: {...}} and the brief keeps "pick"/"flag".
"""
import argparse, glob, hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import image_sources as I  # noqa: E402
from broll_fetch import load, save  # noqa: E402

MODEL = os.environ.get("IMAGE_PICK_MODEL", "gemini-2.5-pro")
PY = sys.executable
_client = None


def client():
    global _client
    if _client is None:
        from google import genai
        key = I.gemini_key()
        if not key:
            sys.exit("no GEMINI_API_KEY (env or the skill's .env)")
        _client = genai.Client(api_key=key)
    return _client


def ask_json(parts, schema):
    from google.genai import types
    for attempt in range(3):
        try:
            r = client().models.generate_content(model=MODEL, contents=parts, config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json", response_schema=schema))
            return json.loads(r.text)
        except Exception as e:                                # retried; a failure leaves the row unscored, never passed
            if attempt == 2:
                raise
            print(f"  (retry: {str(e)[:80]})")


def paths(P):
    return os.path.join(P, "build", "picture-brief.json"), os.path.join(P, "broll")


def load_brief(P):
    bp, _ = paths(P)
    if not os.path.exists(bp):
        sys.exit(f"no brief yet: image_pick.py brief {P} --line id=\"…\"")
    return json.load(open(bp))


def save_brief(P, b):
    bp, _ = paths(P)
    os.makedirs(os.path.dirname(bp), exist_ok=True)
    json.dump(b, open(bp, "w"), ensure_ascii=False, indent=1)


# --- brief -----------------------------------------------------------------------------------------------------------

BRIEF_SCHEMA = {"type": "OBJECT", "properties": {
    "subject": {"type": "STRING"}, "era": {"type": "STRING"}, "wrong": {"type": "STRING"},
    "en": {"type": "ARRAY", "items": {"type": "STRING"}}, "ru": {"type": "ARRAY", "items": {"type": "STRING"}}},
    "required": ["subject", "era", "wrong", "en", "ru"]}


def cmd_brief(A):
    P = os.path.abspath(A.project)
    old = json.load(open(paths(P)[0])) if os.path.exists(paths(P)[0]) else {"lines": []}
    b = {"reel": A.context or old.get("reel", ""), "frame": A.frame or old.get("frame", ""), "lines": old["lines"]}
    for spec in A.line:
        lid, text = spec.split("=", 1)
        prompt = (f"A short talking-head reel ({b['reel']}). One line of it gets ONE picture, shown as: {b['frame']}.\n"
                  f"Line: «{text}»\n\nSay what the picture must show so a viewer gets the line at a glance on a "
                  "phone: the concrete subject the speaker names (that place, object, kind of person, era), never a "
                  "generic mood. 'wrong': what a weak or wrong picture would be. 'en' and 'ru': 2-3 image-search phrases "
                  "each, 1-4 words, the named subject first (Wikimedia search is literal, so short). Prefer no people "
                  "in the picture at all.")
        j = ask_json([prompt], BRIEF_SCHEMA)
        row = {"id": lid, "line": text, **{k: j[k] for k in ("subject", "era", "wrong")},
               "en": j["en"][:3], "ru": j["ru"][:3]}
        b["lines"] = [x for x in b["lines"] if x["id"] != lid] + [row]
        print(f"{lid}: {row['subject']} | wrong: {row['wrong']}\n   en {row['en']}\n   ru {row['ru']}")
    save_brief(P, b)
    print(f"-> {paths(P)[0]}  (read it and fix subject / phrases before `pull`)")


# --- pull ------------------------------------------------------------------------------------------------------------

def run(args):
    r = subprocess.run([PY] + args, capture_output=True, text=True)
    for ln in (r.stdout + r.stderr).splitlines():
        if ln.startswith(("wm_", "pin", "g_")) and ("->" in ln or "FAIL" in ln):
            print("   " + ln[:150])
    return r.returncode


def cmd_pull(A):
    P = os.path.abspath(A.project)
    b = load_brief(P)
    d = os.path.abspath(A.dir or paths(P)[1])
    for ln in b["lines"]:
        if A.only and ln["id"] != A.only:
            continue
        print(f"{ln['id']}: {ln['subject']}")
        pairs = list(zip(ln["en"], ln["ru"])) or [(ln["en"][0], None)]
        for en, ru in pairs[:2]:
            run([os.path.join(HERE, "wikimedia_fetch.py"), "search", *en.split(), *(["--other", ru] if ru else []),
                 "--n", str(A.per), "--dir", d, "--beat", ln["id"]])
        en, ru = pairs[0]
        extra = ["--other", ru] if ru else []
        run([os.path.join(HERE, "google_images.py"), "search", *en.split(), *extra, "--n", "10", "--take", str(A.per),
             "--dir", d, "--beat", ln["id"]])
        n = sum(1 for r in load(d) if ln["id"] in cands_of(r))
        print(f"  {n} candidates for {ln['id']}")


def cands_of(r):
    return set([r.get("beat") or ""] + r.get("lines", []))


def cmd_tag(A):
    d = paths(os.path.abspath(A.project))[1]
    rows = load(d)
    for r in rows:
        if r["id"] in A.rows:
            r["lines"] = sorted(set(r.get("lines", []) + [A.line_id]))
    save(d, rows)
    print(f"tagged {sum(r['id'] in A.rows for r in rows)} rows as candidates of {A.line_id}")


# --- score -----------------------------------------------------------------------------------------------------------

SCORE_SCHEMA = {"type": "OBJECT", "properties": {
    "shows": {"type": "STRING"}, "line": {"type": "INTEGER"}, "specific": {"type": "INTEGER"},
    "quality": {"type": "INTEGER"}, "frame": {"type": "INTEGER"}, "clash": {"type": "BOOLEAN"},
    "reason": {"type": "STRING"}}, "required": ["shows", "line", "specific", "quality", "frame", "clash", "reason"]}


def still_bytes(f, long_side):
    from PIL import Image
    import io
    im = Image.open(f).convert("RGB")
    im.thumbnail((long_side, long_side))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def score_one(row, ln, frame, proj):
    from google.genai import types
    f = os.path.join(proj, row["file"])
    prompt = (f"You judge ONE candidate picture for one line of a talking-head reel, shown as: {frame}.\n"
              f"Line: «{ln['line']}»\nWhat it must show: {ln['subject']} ({ln.get('era', '')}). Wrong would be: {ln['wrong']}.\n"
              f"Image 1 is the full still ({row['w']}x{row['h']} px); image 2 is the same still at the size a phone shows it.\n"
              "Score 0-5 each, strictly; use the whole range and keep 5 for the best picture this line could get "
              "(4 = good, 3 = usable but weak, 1-2 = wrong or unreadable):\n"
              "- line: from image 2 alone, does a stranger get the line's subject in under a second?\n"
              "- specific: is it the named subject (that place, object, era), not a generic mood or look-alike? A "
              "neighbouring or proxy subject (San Francisco for Silicon Valley, any city for a named one) scores 3 at most.\n"
              "- quality: sharp, well exposed, enough resolution for the frame; penalise watermarks, upscaling, clutter.\n"
              "- frame: still readable after the frame's treatment (e.g. B&W, sepia, small print), and does it belong "
              "in that frame: a drawing, icon or clip-art in a photo-print frame scores 2 at most; a product cut-out on "
              "white in a photo frame 3 at most.\n"
              "- clash: true if text, a watermark or a logo in it clashes with the reel (shop watermark, wrong brand).\n"
              "'shows': what it shows in a few words. 'reason': one line on the line score.")
    parts = [prompt, types.Part.from_bytes(data=still_bytes(f, 1536), mime_type="image/jpeg"),
             types.Part.from_bytes(data=still_bytes(f, 420), mime_type="image/jpeg")]
    return ask_json(parts, SCORE_SCHEMA)


def sig(row, ln, frame, proj):
    st = os.stat(os.path.join(proj, row["file"]))
    return hashlib.sha1(f"{row['file']}|{st.st_size}|{ln['line']}|{ln['subject']}|{ln['wrong']}|{frame}|{MODEL}".encode()).hexdigest()[:12]


def cmd_score(A):
    P = os.path.abspath(A.project)
    b = load_brief(P)
    d = paths(P)[1]
    rows = load(d)
    for ln in b["lines"]:
        if A.only and ln["id"] != A.only:
            continue
        for r in rows:
            if ln["id"] not in cands_of(r) or r.get("kind", "image") != "image":
                continue
            s = sig(r, ln, b["frame"], P)
            old = (r.get("scores") or {}).get(ln["id"])
            if old and old.get("sig") == s and not A.again:
                continue
            try:
                j = score_one(r, ln, b["frame"], P)
            except Exception as e:
                print(f"{ln['id']} {r['id']}: UNSCORED ({str(e)[:80]})"); continue
            j = {k: (max(0, min(5, v)) if isinstance(v, int) and not isinstance(v, bool) else v) for k, v in j.items()}
            r.setdefault("scores", {})[ln["id"]] = {**j, "sig": s, "model": MODEL}
            save(d, rows)
            print(f"{ln['id']} {r['id']}: line {j['line']} spec {j['specific']} qual {j['quality']} frame {j['frame']}"
                  f"{' CLASH' if j['clash'] else ''} people {r.get('people')} | {j['shows'][:50]} | {j['reason'][:90]}")


# --- pick + sheet ----------------------------------------------------------------------------------------------------

def ranked(rows, lid):
    c = [r for r in rows if lid in cands_of(r) and (r.get("scores") or {}).get(lid)]
    key = lambda r: tuple(r["scores"][lid][k] for k in ("line", "specific", "frame", "quality")) + (
        r.get("source") == "wikimedia" or r.get("free_host", False), min(r.get("w", 0), r.get("h", 0)))  # ties: free licence, size
    ok = lambda r: r.get("people") == "pass" and not r["scores"][lid]["clash"]
    return sorted(c, key=lambda r: (ok(r), key(r)), reverse=True), ok


FINAL_SCHEMA = {"type": "OBJECT", "properties": {"best": {"type": "INTEGER"}, "reason": {"type": "STRING"}},
                "required": ["best", "reason"]}


def final(c, ln, frame, P):
    """tied top candidates side by side at phone size: which one does a stranger read fastest?"""
    from google.genai import types
    parts = [f"Line of a reel: «{ln['line']}». It must show: {ln['subject']}. Shown as: {frame}.\n"
             f"Here are {len(c)} candidate pictures (1..{len(c)}) at the size a phone shows them. Which ONE does a "
             "stranger read as the subject fastest (subject large and clear, no haze, nothing distracting)? "
             "'best' is its number; 'reason' one line."]
    for r in c:
        parts.append(types.Part.from_bytes(data=still_bytes(os.path.join(P, r["file"]), 420), mime_type="image/jpeg"))
    j = ask_json(parts, FINAL_SCHEMA)
    return c[max(1, min(len(c), j["best"])) - 1], j["reason"]


def cmd_pick(A):
    P = os.path.abspath(A.project)
    b = load_brief(P)
    rows = load(paths(P)[1])
    for ln in b["lines"]:
        c, ok = ranked(rows, ln["id"])
        top = c[0] if c and ok(c[0]) else None
        four = lambda r: tuple(r["scores"][ln["id"]][k] for k in ("line", "specific", "frame", "quality"))
        tied = [r for r in c if ok(r) and top and four(r) == four(top)][:4]
        if len(tied) > 1:                                 # scores tie: a side-by-side look at phone size decides
            top, why = final(tied, ln, b["frame"], P)
            ln["final"] = {"among": [r["id"] for r in tied], "chose": top["id"], "reason": why}
            print(f"{ln['id']}: {len(tied)} tied at {four(tied[0])}; side by side -> {top['id']}: {why[:110]}")
        if top and top["scores"][ln["id"]]["line"] >= 4:
            ln["pick"], ln["flag"] = top["id"], ""
            s = top["scores"][ln["id"]]
            print(f"{ln['id']}: PICK {top['id']} (line {s['line']} spec {s['specific']} qual {s['quality']} frame {s['frame']}) "
                  f"{s['shows'][:60]} [{top.get('licence', '')[:40]}]")
        else:
            best = top["scores"][ln["id"]]["line"] if top else None
            ln["pick"], ln["flag"] = "", f"no candidate says the line (best line score {best}): no picture, or pull again"
            print(f"{ln['id']}: FLAG - {ln['flag']} ({len(c)} scored)")
    save_brief(P, b)


def cmd_sheet(A):
    from PIL import Image, ImageDraw, ImageFont
    P = os.path.abspath(A.project)
    b = load_brief(P)
    rows = load(paths(P)[1])
    font = lambda n: ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", n)
    TH, TW, COLS = 230, 250, 8
    bands = []
    for ln in b["lines"]:
        c, ok = ranked(rows, ln["id"])
        c = c[:COLS * 2]
        nrow = max(1, (len(c) + COLS - 1) // COLS)
        band = Image.new("RGB", (TW * COLS, 70 + nrow * (TH + 92)), "white")
        d = ImageDraw.Draw(band)
        status = f"PICK {ln.get('pick')}" if ln.get("pick") else f"FLAGGED: {ln.get('flag', 'not picked yet')}"
        d.text((10, 6), f"{ln['id']}: «{ln['line'][:95]}»", fill="black", font=font(22))
        d.text((10, 38), f"must show: {ln['subject'][:110]}   |   {status}", fill="#0a6" if ln.get("pick") else "#c00", font=font(18))
        for i, r in enumerate(c):
            x, y = (i % COLS) * TW, 70 + (i // COLS) * (TH + 92)
            im = Image.open(os.path.join(P, r["file"])).convert("RGB"); im.thumbnail((TW - 12, TH))
            band.paste(im, (x + 6 + (TW - 12 - im.width) // 2, y))
            s = r["scores"][ln["id"]]
            col = "#0a6" if r["id"] == ln.get("pick") else ("#c00" if not ok(r) else "#333")
            if r["id"] == ln.get("pick"):
                d.rectangle((x + 2, y - 4, x + TW - 3, y + TH + 88), outline="#0a6", width=6)
            d.text((x + 8, y + TH + 4), f"L{s['line']} S{s['specific']} Q{s['quality']} F{s['frame']}"
                   + (" CLASH" if s["clash"] else "") + ("" if r.get("people") == "pass" else f" people {r.get('people')}"),
                   fill=col, font=font(20))
            d.text((x + 8, y + TH + 30), f"{r['source'][:9]}: {s['shows'][:20]}", fill="#333", font=font(15))
            d.text((x + 8, y + TH + 50), (r.get("licence") or "")[:30], fill="#777", font=font(13))
        bands.append(band)
    if not bands:
        sys.exit("no lines in the brief")
    W = max(x.width for x in bands)
    out = Image.new("RGB", (W, sum(x.height + 12 for x in bands)), "#ddd")
    y = 0
    for x in bands:
        out.paste(x, (0, y)); y += x.height + 12
    o = A.o or os.path.join(P, "build", "picture-picks.jpg")
    out.save(o, quality=88)
    print(f"-> {o}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("brief"); s.add_argument("project"); s.add_argument("--line", action="append", default=[])
    s.add_argument("--frame"); s.add_argument("--context")
    s = sub.add_parser("pull"); s.add_argument("project"); s.add_argument("--dir"); s.add_argument("--per", type=int, default=3)
    s.add_argument("--only")
    s = sub.add_parser("tag"); s.add_argument("project"); s.add_argument("line_id"); s.add_argument("rows", nargs="+")
    s = sub.add_parser("score"); s.add_argument("project"); s.add_argument("--only"); s.add_argument("--again", action="store_true")
    s = sub.add_parser("pick"); s.add_argument("project")
    s = sub.add_parser("sheet"); s.add_argument("project"); s.add_argument("-o")
    A = ap.parse_args()
    {"brief": cmd_brief, "pull": cmd_pull, "tag": cmd_tag, "score": cmd_score, "pick": cmd_pick, "sheet": cmd_sheet}[A.cmd](A)


if __name__ == "__main__":
    main()
