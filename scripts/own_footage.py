#!/usr/bin/env python3
"""The user's own footage as B-roll, automatically, with a face check so only they appear (references/broll.md 3).
Wrong people have ended up in cuts before. So every clip is face-checked (YuNet + SFace against the user's own face),
and the picked clips go to the user on a confirmation sheet BEFORE the render.

    own_footage.py me PLATE.mp4 [PLATE2.mp4 IMG.jpg ...] [--add]    # your face reference (library/me/face_ref.npz + refs.jpg: LOOK at it)
    own_footage.py index [--root DIR ...] [--describe] [--max N]    # scan your libraries -> library/me/footage_index.json (incremental)
    own_footage.py find WORD [WORD ...] [--people none|me|any] [--min 1.5]   # ranked clean windows for a line
    own_footage.py check CLIP --in 3.0 --dur 2.0                    # 5 fps over the window: none / only you / SOMEONE ELSE at t
    own_footage.py sheet --project DIR | --picks picks.json -o confirm.jpg   # the confirmation sheet to show the user before rendering
                                                                 # (frames of the PREPARED clips: exactly what the reel shows;
                                                                 #  a person with no visible face is for the user's eyes, not the detector)

Default roots (a Mac without one skips it): the Photos library originals (~/Pictures/Photos Library.photoslibrary/
originals: read only, never modified) and ~/Movies. Add more (GoPro, DJI, iPhone folders) with --root or
library/me/roots.json.
Cloud-only files (Google Drive placeholders) are skipped, never downloaded.
People per sample (1 fps, <= 30 samples a clip): faces under 4 % of the frame width count as "tiny" (crowds, far
figures); a face of 4 % or more is YOU when SFace cosine to any of your references is >= 0.40 (the audit's threshold),
else SOMEONE ELSE. A clip's clean windows are runs of samples with no one else in them.
--describe adds a one-line description + tags per clip from Gemini 2.5 Flash on its 6-frame sheet (GEMINI_API_KEY; the
key is checked with one call first; resumable: the index is the ledger, failures are retried next run, never stored).
library/me/ is gitignored (your face embeddings and your library's index stay on your Mac).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade_lib as G  # noqa: E402
from broll_qa import Faces, decode, cover_size  # noqa: E402

ME = os.path.join(HERE, "..", "library", "me")
REF = os.path.join(ME, "face_ref.npz")
INDEX = os.path.join(ME, "footage_index.json")
ROOTS = [os.path.expanduser(p) for p in ("~/Pictures/Photos Library.photoslibrary/originals", "~/Movies",
                                         "~/Videos", "~/Pictures")]  # macOS Photos + Movies; Windows / Linux Videos + Pictures
VIDEO = re.compile(r"\.(mov|mp4|m4v)$", re.I)
SKIP = re.compile(r"(/\.|/Telegram|/CapCut/|/renders?/|/proxies|/\.Trash)", re.I)
TH, MINW, TINY = 0.40, 0.04, 0.04
VERSION = 2          # 2: rotation-aware decode (v1 squashed portrait phone clips and missed faces: IMG_7701)
PERSON = re.compile(r"\b(person|people|man|men|woman|women|girl|boy|child|children|kid|someone|snorkel\w*|diver|hiker|swimmer|rider|crowd|"
                    r"человек|люди|мужчин\w*|женщин\w*|девушк\w*|ребен\w*|дет\w*)\b", re.I)
# the B-roll people rules (people-rules.json): `find` never offers a clip whose description matches a rule's
# description_words (broll_vision.py then checks the picked window itself)
_bw = [ru["description_words"] for ru in __import__("broll_vision").RULES["rules"] if ru.get("description_words")]
BANNED = re.compile(r"\b(" + "|".join(_bw) + r")\b", re.I) if _bw else None
F = None


def faces():
    global F
    if F is None:
        F = Faces()
    return F


def load_ref():
    if not os.path.exists(REF):
        sys.exit(f"no face reference: run `own_footage.py me <one of your plates>` first ({REF})")
    return np.load(REF)["emb"]


def who(img, ref, thr=0.6):
    """faces in a BGR frame -> [(x, y, w, h, label, cos)]: label me / other / tiny"""
    out = []
    w = img.shape[1]
    for f in faces().detect(img, thr):
        if f[2] < TINY * w:
            out.append((*f[:4], "tiny", 0.0))
            continue
        e = faces().feature(img, f)
        cos = float((ref @ e).max())
        out.append((*f[:4], "me" if cos >= TH else "other", cos))
    return out


# ------------------------------------------------------------------ me
def cmd_me(a):
    os.makedirs(ME, exist_ok=True)
    embs, crops = [], []
    if a.add and os.path.exists(REF):
        embs = list(np.load(REF)["emb"])
    for src in a.src:
        if G.STILL_EXT(src):
            frames = [cv2.imread(src)]
        else:
            info = G.probe(src)
            w, h = G.fit(info, 540)
            frames = [x[0] for x in (decode(src, w, h, start=info["dur"] * (i + .5) / 12, dur=0.05) for i in range(12)) if x]
        for im in frames:
            fs = [f for f in faces().detect(im, 0.85) if f[2] >= 0.09 * im.shape[1]]
            if len(fs) != 1:                    # exactly one big face: no second person can sneak into the reference
                continue
            f = fs[0]
            embs.append(faces().feature(im, f))
            x, y, w_, h_ = [int(v) for v in f[:4]]
            crops.append(cv2.resize(im[max(0, y):y + h_, max(0, x):x + w_], (120, 120)))
    if not embs:
        sys.exit("no single clear face found in the sources")
    E = np.stack(embs)
    m = E.mean(0) / np.linalg.norm(E.mean(0))
    keep = E @ m >= 0.45                         # drop an outlier pick (a wrong face) against the consensus
    E = E[keep]
    np.savez(REF, emb=E)
    if crops:
        cv2.imwrite(os.path.join(ME, "refs.jpg"), np.hstack(crops[:16]))
    print(f"{len(E)} reference embeddings of you -> {REF}; LOOK at {os.path.join(ME, 'refs.jpg')}: every crop must be you")


# ------------------------------------------------------------------ index
def sheet6(path, info, out):
    w, h = G.fit(info, 200)
    tiles = []
    for i in range(6):
        fr = decode(path, w, h, start=info["dur"] * (i + .5) / 6, dur=0.05)
        if fr:
            tiles.append(fr[0])
    if tiles:
        cv2.imwrite(out, np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 80])
    return out if tiles else None


def scan(path, ref):
    info = G.probe(path)
    if info["dur"] < 1.0:
        return None
    w, h = G.fit(info, 360)
    n = int(min(30, max(2, info["dur"])))
    samples = []
    for i in range(n):
        t = info["dur"] * (i + .5) / n
        fr = decode(path, w, h, start=t, dur=0.05)
        if not fr:
            continue
        fs = who(fr[0], ref)
        samples.append({"t": round(t, 2), "me": sum(1 for f in fs if f[4] == "me"), "other": sum(1 for f in fs if f[4] == "other"),
                        "tiny": sum(1 for f in fs if f[4] == "tiny"), "cos": [round(f[5], 2) for f in fs if f[4] != "tiny"]})
    people = "others" if any(s["other"] for s in samples) else "me" if any(s["me"] for s in samples) else \
        "tiny" if any(s["tiny"] for s in samples) else "none"
    clean, cur = [], None                        # runs of samples with no one else (tiny far figures allowed, flagged)
    step = info["dur"] / max(1, n)
    for s in samples:
        if s["other"] == 0:
            cur = [max(0, s["t"] - step / 2), s["t"] + step / 2] if cur is None else [cur[0], s["t"] + step / 2]
        else:
            if cur:
                clean.append(cur)
            cur = None
    if cur:
        clean.append(cur)
    return {"w": info["w"], "h": info["h"], "fps": round(info["fps"], 3), "dur": round(info["dur"], 2), "hdr": G.is_hdr(info),
            "rotation": info.get("rotation", 0), "people": people, "clean": [[round(a, 2), round(min(b, info["dur"]), 2)] for a, b in clean],
            "samples": samples}


def describe_init():
    from google import genai
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        envp = os.path.join(HERE, "..", ".env")
        if os.path.exists(envp):
            m = re.search(r"GEMINI_API_KEY\s*=\s*['\"]?([^'\"\n]+)", open(envp, encoding="utf-8").read())
            key = m.group(1).strip() if m else None
    if not key:
        sys.exit("--describe needs GEMINI_API_KEY")
    client = genai.Client(api_key=key)
    client.models.generate_content(model="gemini-2.5-flash", contents="Reply with the single word ok.")   # key check, one call
    return client


def describe(client, sheet):
    from google.genai import types
    prompt = ("Six frames of one video clip, left to right. Reply as JSON only: {\"desc\": one plain sentence of what is in the "
              "clip (place, light, action), \"tags\": 5-12 lowercase English and Russian nouns/verbs a video editor would search for "
              "(e.g. beach, пляж, mountains, горы, laptop, ноутбук, swimming, плавание, night, ночь)}. Do not guess who people are.")
    r = client.models.generate_content(model="gemini-2.5-flash", contents=[types.Part.from_bytes(data=open(sheet, "rb").read(), mime_type="image/jpeg"), prompt],
                                       config=types.GenerateContentConfig(response_mime_type="application/json"))
    j = json.loads(r.text)
    if not isinstance(j, dict) or "desc" not in j:
        raise ValueError("bad answer")
    return {"desc": str(j["desc"])[:300], "tags": [str(t).lower() for t in j.get("tags", [])][:16]}


def cmd_index(a):
    ref = load_ref()
    roots = a.root or (json.load(open(os.path.join(ME, "roots.json"), encoding="utf-8")) if os.path.exists(os.path.join(ME, "roots.json")) else ROOTS)
    idx = json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {}
    os.makedirs(os.path.join(ME, "sheets"), exist_ok=True)
    files = []
    for r in roots:
        r = os.path.expanduser(r)
        if not os.path.isdir(r):
            print(f"skip {r} (not on this Mac)")
            continue
        for dp, _, fn in os.walk(r):
            if SKIP.search(dp + "/"):
                continue
            for f in fn:
                if VIDEO.search(f):
                    files.append(os.path.join(dp, f))
    client = describe_init() if a.describe else None
    done = 0
    for p in sorted(files):
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_size < 50_000 or getattr(st, "st_blocks", 1) == 0:      # cloud placeholder: never trigger a download
            continue
        key = f"{st.st_size}:{int(st.st_mtime)}"
        e = idx.get(p)
        if e and e.get("v") != VERSION and e.get("rotation") not in (90, -90, 270, -270):
            e["v"] = VERSION                     # unrotated clips were decoded right by v1
        if not e or e.get("key") != key or e.get("v") != VERSION:
            if a.max and done >= a.max:
                continue
            try:
                s = scan(p, ref)
            except (subprocess.CalledProcessError, KeyError, ValueError, IndexError) as ex:
                print(f"skip {p}: {ex}")
                continue
            if not s:
                continue
            sh = os.path.join(ME, "sheets", hashlib.md5(p.encode()).hexdigest()[:16] + ".jpg")
            s["sheet"] = sheet6(p, G.probe(p), sh)
            e = {"key": key, "v": VERSION, **s}
            idx[p] = e
            done += 1
            if done % 10 == 0:
                json.dump(idx, open(INDEX, "w", encoding="utf-8"))
                print(f"  {done} scanned", flush=True)
        if client and e and not e.get("desc") and e.get("sheet"):
            for attempt in range(3):
                try:
                    e.update(describe(client, e["sheet"]))
                    e["person_in_desc"] = bool(PERSON.search(e["desc"] + " " + " ".join(e.get("tags", []))))
                    break
                except Exception as ex:   # transient: retried now, and next run if it still fails (never stored as a result)
                    if attempt == 2:
                        print(f"  describe failed for {os.path.basename(p)}: {ex}")
                    time.sleep(2 * (attempt + 1))
    json.dump(idx, open(INDEX, "w", encoding="utf-8"))
    n = len(idx)
    by = {k: sum(1 for e in idx.values() if e["people"] == k) for k in ("none", "tiny", "me", "others")}
    print(f"{n} clips indexed ({done} new): no people {by['none']}, far figures only {by['tiny']}, only you {by['me']}, "
          f"someone else {by['others']} -> {INDEX}")


# ------------------------------------------------------------------ find / check / sheet
def cmd_find(a):
    idx = json.load(open(INDEX, encoding="utf-8"))
    words = [w.lower() for w in a.words]
    rows, banned = [], 0
    for p, e in idx.items():
        if BANNED and BANNED.search(e.get("desc", "") + " " + " ".join(e.get("tags", []))):
            banned += 1
            continue
        pd = e.get("person_in_desc") or bool(PERSON.search(e.get("desc", "") + " " + " ".join(e.get("tags", []))))
        if a.people == "none" and (e["people"] not in ("none",) or pd):
            continue
        if a.people == "me" and e["people"] not in ("none", "me"):
            continue
        text = (e.get("desc", "") + " " + " ".join(e.get("tags", []))).lower()
        score = sum(text.count(w) for w in words)
        wins = [w for w in e["clean"] if w[1] - w[0] >= a.min]
        if score and wins and min(e["w"], e["h"]) >= 1080:
            rows.append((score, p, e, wins))
    if banned:
        print(f"({banned} clip(s) never offered: the description names something the people rules exclude)")
    for score, p, e, wins in sorted(rows, key=lambda r: -r[0])[:a.n]:
        pd = e.get("person_in_desc") or bool(PERSON.search(e.get("desc", "") + " " + " ".join(e.get("tags", []))))
        print(f"{score:2d}  {p}\n    {e['w']}x{e['h']} {e['fps']:g} fps {e['dur']} s{' HDR' if e['hdr'] else ''}  people: {e['people']}"
              f"{' + a person in the description (no face seen: confirm on the sheet)' if pd and e['people'] in ('none', 'tiny') else ''}  "
              f"clean: {wins[:3]}\n    {e.get('desc', '')}")


def check_window(path, tin, dur, ref):
    info = G.probe(path)
    w, h = G.fit(info, 360)
    frames = decode(path, w, h, fps=5, start=tin, dur=dur)
    hits = []
    for k, im in enumerate(frames):
        for f in who(im, ref, 0.55):
            hits.append((round(tin + k / 5, 2), f[4], round(f[5], 2), [int(v) for v in f[:4]]))
    others = [x for x in hits if x[1] == "other"]
    verdict = "SOMEONE ELSE" if others else "only you" if any(x[1] == "me" for x in hits) else \
        "far figures only" if any(x[1] == "tiny" for x in hits) else "no people"
    return verdict, hits, frames


def cmd_check(a):
    v, hits, _ = check_window(a.clip, a.tin, a.dur, load_ref())
    print(f"{v}: {os.path.basename(a.clip)} {a.tin:.2f}+{a.dur:.2f} s")
    for t, lab, cos, box in hits:
        if lab == "other":
            print(f"  {t:.2f} s: a face that is not you (cosine {cos}) at {box}")
    sys.exit(1 if v == "SOMEONE ELSE" else 0)


def picks_from_project(project):
    """own-footage inserts of a project: insert_prep sidecars (<clip>.json, kind own) of every clip the project uses"""
    out = []
    for dp, _, fn in os.walk(project):
        for f in fn:
            if f.endswith(".mp4.json") or f.endswith(".jpg.json"):
                j = json.load(open(os.path.join(dp, f), encoding="utf-8"))
                if (j.get("kind") or G.guess_kind(j.get("src", ""))) == "own":
                    out.append({"src": j["src"], "in": j.get("in", 0), "dur": j.get("source_span", 2.0), "clip": os.path.join(dp, f[:-5])})
    return out


def cmd_sheet(a):
    ref = load_ref()
    picks = picks_from_project(a.project) if a.project else json.load(open(a.picks, encoding="utf-8"))
    rows, report = [], []
    for pk in picks:
        if G.STILL_EXT(pk["src"]):
            im = cv2.imread(pk["src"])
            frames = [cv2.resize(im, (200, int(200 * im.shape[0] / im.shape[1])))]
            fs = [(pk["src"], who(frames[0], ref))]
            v = "SOMEONE ELSE" if any(f[4] == "other" for f in fs[0][1]) else "ok"
        elif pk.get("clip") and os.path.exists(pk["clip"]):     # what the reel shows: the prepared (cropped, graded) clip
            v, hits, frames = check_window(pk["clip"], 0.0, G.probe(pk["clip"])["dur"], ref)
        else:
            v, hits, frames = check_window(pk["src"], float(pk["in"]), float(pk["dur"]), ref)
        n = len(frames)
        pick = [frames[int(i * (n - 1) / 4)] for i in range(5)] if n >= 5 else frames
        tiles = []
        for im in pick:
            im = im.copy()
            for f in who(im, ref, 0.55):
                col = (0, 200, 0) if f[4] == "me" else (0, 0, 255) if f[4] == "other" else (0, 200, 255)
                x, y, w, h = [int(v_) for v_ in f[:4]]
                cv2.rectangle(im, (x, y), (x + w, y + h), col, 2)
                cv2.putText(im, {"me": "you", "other": "NOT YOU?", "tiny": "far"}[f[4]], (x, max(12, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
            tiles.append(cv2.resize(im, (160, int(160 * im.shape[0] / im.shape[1]))))
        hh = max(t.shape[0] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, hh - t.shape[0], 0, 3, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles]
        row = np.hstack(tiles)
        head = np.full((26, row.shape[1], 3), 255, np.uint8)
        cv2.putText(head, f"{os.path.basename(pk['src'])} {float(pk['in']):.1f}+{float(pk['dur']):.1f}s  {v}", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 0, 200) if v == "SOMEONE ELSE" else (30, 30, 30), 1)
        rows.append(np.vstack([head, row]))
        report.append((pk["src"], v))
    W = max(r.shape[1] for r in rows)
    sheet = np.vstack([cv2.copyMakeBorder(r, 0, 6, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows])
    cv2.imwrite(a.o, sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    for s, v in report:
        print(f"  {v:16s} {s}")
    print(f"-> {a.o}: show it to the user and wait for their yes before rendering")
    sys.exit(1 if any(v == "SOMEONE ELSE" for _, v in report) else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("me"); p.add_argument("src", nargs="+"); p.add_argument("--add", action="store_true")
    p = sp.add_parser("index"); p.add_argument("--root", action="append"); p.add_argument("--describe", action="store_true"); p.add_argument("--max", type=int)
    p = sp.add_parser("find"); p.add_argument("words", nargs="+"); p.add_argument("--people", choices=["none", "me", "any"], default="me")
    p.add_argument("--min", type=float, default=1.5); p.add_argument("-n", type=int, default=12)
    p = sp.add_parser("check"); p.add_argument("clip"); p.add_argument("--in", dest="tin", type=float, default=0.0); p.add_argument("--dur", type=float, default=3.0)
    p = sp.add_parser("sheet"); p.add_argument("--project"); p.add_argument("--picks"); p.add_argument("-o", default="build/own-footage-confirm.jpg")
    a = ap.parse_args()
    {"me": cmd_me, "index": cmd_index, "find": cmd_find, "check": cmd_check, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    main()
