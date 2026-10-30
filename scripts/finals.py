#!/usr/bin/env python3
"""Finish built reels: low-quality previews the user watches -> final render -> QA -> optional delivery into the user's
library of finished videos (CONTENT).
Works on any HyperFrames project (reel.json builds and custom index.html generators alike), one reel or a batch.

    finals.py preview  <project> [<project> ...] --out DIR [--style "Seoul list"] [--code R01] [--title "..."]
    finals.py render   ...      (refuses a reel whose preview is missing or older than its index.html; --force)
    finals.py qa       ...
    finals.py nomusic  ...      (the no-music version of an existing final; render makes it by itself)
    finals.py deliver  ...      [--collection "Trial reels"] [--date 2026-10-14] [--allow "R01 - Seoul list"] [--rounds 2] [--dry]
    finals.py <step> --batch reels.json                       (every reel in the manifest; CLI flags fill missing fields)

The order (low-quality previews before any final render):
  1. build each reel (its recipe / build.mjs), approval sheet or snapshots for your own look
  2. preview: a 1080x1920 render ("looks", CRF 16) -> 720x1280 phone copy at ~4.5 Mbit/s "<name> (preview).mp4" (~15-20 MB
     for 30 s; sharpness is judged on it, so not smaller: 540x960 at ~0.4 Mbit/s read as blur). Send them with a
     frame-0 still; WAIT for the user's OK.
  3. render: delivery-quality master -> Instagram H.264 "<name>.mp4": 1080x1920, 30 fps CFR, High@4.2, yuv420p, BT.709
     tags, CRF 16 capped at 20 Mbit/s (buffer 40M), AAC 256k 48 kHz, faststart. Log: "<name>.log".
     Then the no-music version "<name> (no music).mp4" (voice + SFX + meme sounds, no bed) for posting with in-app music:
     the same picture (video stream copied) with a mix that leaves out the music bed, lossless ALAC until deliver makes
     its one AAC pass (see nomusic()). --no-nomusic skips it.
  4. qa: render_report.py (streams, A/V, loudness, black, frozen, hook) + broll_qa.py (people, match, as_shot, freeze,
     faces, models, ...) -> "<name>.qa.json" + .html, "<name>.broll-qa.json" + timeline png; one summary line per reel.
  5. deliver (optional; needs CONTENT): two-pass loudnorm to -14 LUFS / -1.5 dBTP (video copied), filed in the library:
       NOT POSTED/<collection>/<date> <title> (<code>)/<code> – <style>.mp4   (with --collection)
       NOT POSTED/<date> <title> (<code>, <style>).mp4                         (without)
     logs _moves.tsv, adds one TRACKER.csv + tracker_data.json row per video once all its reels are in, rebuilds
     TRACKER.html (make_html.py). A reel with a hard QA fail (HARD below) is held unless --allow names it.
     The no-music version is filed next to its final as "<final name> – no music.mp4" (same loudness pass).
     TRACKER v2 (a "version" column): one row per reel version instead of one per video, with reel, version,
     lang, style, project, no_music_file, render_minutes and change_rounds filled in.
When CONTENT is set, every preview / render / nomusic / deliver also adds a line to $CONTENT/LEDGER.tsv (step, seconds,
file), the machine's own speed log: render_minutes = all preview + render + nomusic time of that reel, change_rounds =
previews after the first one (--rounds / "rounds" overrides). The reel id comes from the nearest intake.json above the
project (e.g. ~/reels/<shoot date>_<code>/intake.json), else "reel" in the manifest, else the code.
Run it as a tracked background job: a HyperFrames render cancels itself when its parent shell exits.

reels.json: {"out": "~/reels/x/finals", "date": "2026-10-14", "collection": "Trial reels", "language": "EN",
             "reels": [{"project": "~/reels/x/r01/edit/v1", "code": "R01", "title": "Keep the paper",
                        "title_ru": "<the title in the script's language>", "style": "Seoul list"}, ...]}
  per reel (or top level as a default): name (default "<code> - <style>"), recipe / profile (default from the style),
  allow ("why the hard fail is OK"), how / notes (TRACKER text), reel / version (tracker v2 ids), rounds,
  music_ids (the <audio> ids of the music bed when they are not called bed / music-bed / bgm).
Env: HF_VERSION (overrides the pinned HyperFrames CLI in scripts/HF_VERSION), MEDIA_PY (python with numpy + opencv),
     CONTENT (deliver: your library folder, with NOT POSTED/ inside; no default), TRACKER_WORK (tracker_data.json + make_html.py;
     default CONTENT).
"""
import argparse
import contextlib
import csv
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hf_version import VERSION as HF_VERSION, hf  # noqa: E402  (scripts/HF_VERSION)
from x264 import THREADS as X264_THREADS  # noqa: E402  (scripts/X264_THREADS)
HOME = os.path.expanduser("~")
# style name -> (recipe dir, broll_qa profile)
STYLES = {"clean os": ("clean-os", "talking-head"), "face result": ("result-podcast", "talking-head"),
          "result": ("result-podcast", "talking-head"), "seoul list": ("seoul-list", "broll-led"),
          "stan": ("stan-style", "tutorial"), "stan style": ("stan-style", "tutorial"),
          "pov montage": ("pov-montage", "broll-led"), "vector explainer": ("explainer-vector", "graphics"),
          "whiteboard": ("whiteboard", "talking-head"),
          "kinetic doc": ("kinetic-doc", "talking-head")}       # format B / C reels: "profile": "graphics" / "broll-led" per reel
# the music bed's <audio> element: id "bed", "music-bed", "bgm2" ... (every recipe so far uses one of these), or a src
# under a music/ folder; "music_ids" in the manifest overrides
MUSIC_ID = re.compile(r"(^|[-_])(bed|music|bgm)([-_\d]|$)", re.I)
LEDGER_COLS = ["at", "machine", "reel", "version", "name", "project", "step", "seconds", "value", "file", "note"]
# QA failures that hold a delivery: wrong format, broken picture or sound, and the hard rules (people rules, face as shot)
HARD = {"streams", "av_sync", "black", "frozen", "bq_people", "bq_as_shot", "bq_freeze", "bq_faces", "bq_hdr"}
H264 = ["-c:v", "libx264", "-threads", X264_THREADS, "-preset", "slow", "-crf", "16", "-maxrate", "20M", "-bufsize", "40M",
        "-profile:v", "high", "-level", "4.2", "-g", "60",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]


def media_py():
    for p in (os.environ.get("MEDIA_PY"), os.path.join(HOME, ".venvs/media/bin/python"), sys.executable):
        if p and os.path.exists(p) and subprocess.run([p, "-c", "import numpy, cv2"], capture_output=True).returncode == 0:
            return p
    return sys.executable


def run(cmd, log=None, cwd=None):
    if log:
        with open(log, "a") as f:
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            return subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=cwd).returncode
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def content_dir():
    """the user's library of finished videos ($CONTENT), or "" when it is not set (ledger and deliver are then off)"""
    return os.path.expanduser(os.environ.get("CONTENT", ""))


def tilde(p):
    return "~" + p[len(HOME):] if p and p.startswith(HOME + "/") else p


def reel_of(r):
    """the reel id: nearest intake.json above the project (~/reels/2026-10-25_R11/...), else the manifest's, else the code"""
    d = r["project"]
    while d not in ("/", HOME) and len(d) > len(HOME):
        j = os.path.join(d, "intake.json")
        if os.path.exists(j):
            try:
                return json.load(open(j)).get("reel") or os.path.basename(d)
            except (OSError, json.JSONDecodeError):
                return os.path.basename(d)
        d = os.path.dirname(d)
    return r.get("reel") or r.get("code") or ""


def ledger(step, r, seconds="", file="", value="", note=""):
    """one line per step in $CONTENT/LEDGER.tsv; nothing when CONTENT is not set, a note when it is set but missing"""
    if not content_dir():
        return
    path = os.path.join(content_dir(), "LEDGER.tsv")
    if not os.path.isdir(content_dir()):
        return print(f"ledger skipped: no library at {content_dir()}")
    new = not os.path.exists(path)
    vals = [dt.datetime.now().astimezone().isoformat(timespec="seconds"), socket.gethostname().split(".")[0], reel_of(r),
            r.get("version") or r.get("style") or "", r.get("name", ""), tilde(r["project"]), step,
            f"{seconds:.1f}" if isinstance(seconds, float) else str(seconds), str(value), tilde(file), note]
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write("\t".join(LEDGER_COLS) + "\n")
        f.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in vals) + "\n")


def machine_numbers(r):
    """(render minutes, change rounds) of this reel from the ledger: preview + render + nomusic time; previews - 1"""
    path = os.path.join(content_dir(), "LEDGER.tsv") if content_dir() else ""
    secs, previews, rendered = 0.0, 0, False
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            x = line.rstrip("\n").split("\t")
            if len(x) >= 8 and x[4] == r.get("name", "") and x[5] == tilde(r["project"]):
                if x[6] in ("preview", "render", "nomusic") and x[7]:
                    secs += float(x[7])
                previews += x[6] == "preview"
                rendered |= x[6] == "render"
    rounds = r.get("rounds")
    # a reel rendered before the ledger existed (2026-10-24) has only part of its time in it: leave the minutes empty
    return (f"{secs / 60:.1f}" if secs and rendered else ""), (str(rounds) if rounds is not None else str(max(previews - 1, 0)) if previews else "")


def reels_from(a):
    """the reels to work on: the manifest's, else one per project argument; CLI flags fill what is missing"""
    top, items = {}, []
    if a.batch:
        man = json.load(open(os.path.expanduser(a.batch)))
        top = {k: v for k, v in man.items() if k != "reels"}
        items = man["reels"]
    items += [{"project": p} for p in a.projects]
    cli = {k: getattr(a, k) for k in ("out", "date", "collection", "style", "code", "title", "language", "rounds")
           if getattr(a, k, None) is not None}
    out = []
    for it in items:
        r = {**top, **cli, **it}             # the reel's own fields, then the command line, then the manifest's defaults
        r["project"] = os.path.abspath(os.path.expanduser(r["project"]))
        r.setdefault("out", os.path.join(r["project"], "finals"))
        r["out"] = os.path.abspath(os.path.expanduser(r["out"]))
        r.setdefault("date", dt.date.today().isoformat())
        rec, prof = STYLES.get(str(r.get("style", "")).lower(), (None, None))
        r.setdefault("recipe", rec)
        r.setdefault("profile", prof)
        r.setdefault("name", f"{r['code']} - {r['style']}" if r.get("code") and r.get("style") else os.path.basename(r["project"]))
        if not os.path.exists(os.path.join(r["project"], "index.html")):
            sys.exit(f"{r['project']}: no index.html (build the reel first)")
        out.append(r)
    if not out:
        sys.exit("no reels: give project directories or --batch reels.json")
    return out


def hf_render(r, quality, dst, log):
    cmd = hf("render", "--quality", quality, "--workers", str(r.get("workers", 4)), "--sdr", "--quiet", "-o", dst, ".")
    return run(cmd, log, cwd=r["project"]) == 0 and os.path.exists(dst)


def preview(r):
    os.makedirs(r["out"], exist_ok=True)
    out = os.path.join(r["out"], f"{r['name']} (preview).mp4")
    log = os.path.join(r["out"], f"{r['name']} (preview).log")
    t0, tmp = time.time(), os.path.join(r["out"], f".draft-{r['name']}.mp4")
    if not hf_render(r, "looks", tmp, log):      # not "draft": a draft master (~3 Mbit/s) made the phone copy look soft
        return print(f"FAILED preview render {r['name']} (see {log})")
    if run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-vf", "scale=720:-2:flags=lanczos",
            "-c:v", "libx264", "-threads", X264_THREADS, "-preset", "medium", "-b:v", "4500k", "-maxrate", "5M", "-bufsize", "10M",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], log):
        return print(f"FAILED preview encode {r['name']} (see {log})")
    os.remove(tmp)
    ledger("preview", r, time.time() - t0, out)
    print(f"{time.strftime('%H:%M:%S')} preview {r['name']} in {time.time() - t0:.0f} s ({os.path.getsize(out) / 2**20:.1f} MB) -> {out}")


def render(r, force=False, no_music=True):
    os.makedirs(r["out"], exist_ok=True)
    pv = os.path.join(r["out"], f"{r['name']} (preview).mp4")
    idx = os.path.join(r["project"], "index.html")
    if not force and (not os.path.exists(pv) or os.path.getmtime(pv) < os.path.getmtime(idx)):
        return print(f"HELD {r['name']}: no preview of the current build ({os.path.basename(pv)}); run `finals.py preview`, send it, "
                     "and render after the user's OK (--force skips this)")
    out, log = os.path.join(r["out"], f"{r['name']}.mp4"), os.path.join(r["out"], f"{r['name']}.log")
    master = os.path.join(r["out"], f".master-{r['name']}.mp4")
    t0 = time.time()
    if not hf_render(r, "delivery", master, log):
        return print(f"FAILED render {r['name']} (see {log})")
    vf = "fps=30,format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
    if run(["ffmpeg", "-v", "error", "-y", "-i", master, "-vf", vf, *H264, out + ".part.mp4"], log):
        return print(f"FAILED encode {r['name']} (see {log})")
    os.replace(out + ".part.mp4", out)
    os.remove(master)
    ledger("render", r, time.time() - t0, out)
    print(f"{time.strftime('%H:%M:%S')} render {r['name']} in {time.time() - t0:.0f} s ({os.path.getsize(out) / 2**20:.0f} MB) -> {out}")
    if no_music and r.get("no_music", True):
        nomusic(r)


def music_tags(html, ids=None):
    """the music bed's <audio ...></audio> elements in a composition: (start, end, id)"""
    out = []
    for m in re.finditer(r"<audio\b[^>]*>(?:.*?</audio>)?", html, re.S):
        tag = m.group(0)[:m.group(0).index(">") + 1]
        i, src = re.search(r'\bid="([^"]*)"', tag), re.search(r'\bsrc="([^"]*)"', tag)
        iid = i.group(1) if i else ""
        hit = iid in ids if ids is not None else bool(MUSIC_ID.search(iid) or (src and "/music/" in "/" + src.group(1)))
        if hit:
            out.append((m.start(), m.end(), iid))
    return out


def nomusic(r):
    """the no-music version of <name>.mp4: same picture, mix = voice + SFX + meme sounds without the music bed.
    HyperFrames mixes the audio itself (fades, automation lanes, meme clips' own sound), so instead of rebuilding that mix
    we render a copy of index.html without the bed's <audio> element (removed: the beds carry volume automation, so a
    volume of 0 would not mute them) as a 1 fps draft, and hf_mix_pcm.sh keeps HyperFrames' mix as PCM before its AAC
    encode. Proven on a test reel: the 1 fps and 30 fps mixes are bit-identical, and music mix minus this mix is
    exactly the bed at its volume (correlation 1.00000, residual -137 dB). The PCM goes onto the final's video stream
    (copied, so the picture is bit-identical) as lossless ALAC; deliver makes the one AAC pass. 20 s - 3 min per reel."""
    f = os.path.join(r["out"], f"{r['name']}.mp4")
    out = os.path.join(r["out"], f"{r['name']} (no music).mp4")
    idx = os.path.join(r["project"], "index.html")
    if not os.path.exists(f):
        return print(f"MISSING {f}: render the final first")
    if os.path.getmtime(idx) > os.path.getmtime(f):
        return print(f"HELD no-music {r['name']}: index.html changed after the final was rendered (re-render the final)")
    html = open(idx, encoding="utf-8").read()
    tags = music_tags(html, r.get("music_ids"))
    if not tags:
        subs = re.findall(r'data-composition-src="([^"]+)"', html)
        hidden = [x for x in subs if os.path.exists(os.path.join(r["project"], x)) and music_tags(open(os.path.join(r["project"], x), encoding="utf-8").read())]
        if hidden:
            return print(f"HELD no-music {r['name']}: the bed is inside {hidden}; name its ids in \"music_ids\" or mute it there by hand")
        return print(f"no music bed in {r['name']}: the final itself has no music, so it is its own no-music version")
    for a, b, _ in reversed(tags):
        html = html[:a] + html[b:]
    comp = os.path.join(r["project"], "index.nomusic.html")
    tmp = os.path.join(r["out"], f".nomusic-{r['name']}.mp4")
    pcm = os.path.join(r["out"], f".nomusic-{r['name']}.wav")
    log = os.path.join(r["out"], f"{r['name']} (no music).log")
    env = dict(os.environ, HYPERFRAMES_FFMPEG_PATH=os.path.join(HERE, "hf_mix_pcm.sh"), HF_MIX_PCM=pcm)
    t0 = time.time()
    for x in (tmp, pcm):
        if os.path.exists(x):
            os.remove(x)
    try:
        open(comp, "w", encoding="utf-8").write(html)
        cmd = hf("render", "--quality", "draft", "--fps", "1", "--workers", str(r.get("workers", 4)), "--sdr", "--quiet",
                 "-c", os.path.basename(comp), "-o", tmp, ".")
        with open(log, "a") as lf:
            lf.write(f"\n$ {' '.join(cmd)}\n")
            lf.flush()
            ok = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=r["project"], env=env).returncode == 0
    finally:
        if os.path.exists(comp):
            os.remove(comp)
    if not ok or not os.path.exists(pcm):
        return print(f"FAILED no-music render {r['name']} (see {log}): " + ("no PCM mix captured" if ok else "render failed"))
    d = duration(f)
    if run(["ffmpeg", "-v", "error", "-y", "-i", f, "-i", pcm, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "alac", "-sample_fmt", "s32p", "-ar", "48000", "-ac", "2", "-t", f"{d:.3f}", "-movflags", "+faststart",
            out + ".part.mp4"], log):
        return print(f"FAILED no-music mux {r['name']} (see {log})")
    os.replace(out + ".part.mp4", out)
    for x in (tmp, pcm):
        if os.path.exists(x):
            os.remove(x)
    if abs(duration(out) - d) > 0.05:
        raise SystemExit(f"no-music duration {duration(out):.3f} s != final {d:.3f} s: {out}")
    ledger("nomusic", r, time.time() - t0, out, note="removed " + ",".join(i for _, _, i in tags))
    print(f"{time.strftime('%H:%M:%S')} no-music {r['name']} in {time.time() - t0:.0f} s (without {', '.join(i for _, _, i in tags)}) -> {out}")


def qa(r):
    f = os.path.join(r["out"], f"{r['name']}.mp4")
    if not os.path.exists(f):
        return print(f"MISSING {f}")
    rep = os.path.join(r["out"], f"{r['name']}.qa.json")
    cmd = [media_py(), os.path.join(HERE, "render_report.py"), r["project"], f, "--out", rep, "--broll-out", os.path.join(r["out"], f"{r['name']}.broll-qa.json")]
    cmd += ["--broll-profile", r["profile"]] if r.get("profile") else []
    cmd += ["--style", r["recipe"]] if r.get("recipe") else []
    run(cmd, os.path.join(r["out"], f"{r['name']}.qa.log"))
    print(f"QA {r['name']} | " + (summary(rep) if current(rep, f) else f"QA did not finish (see {r['name']}.qa.log)"))


def current(rep, f):
    """the report exists and is about this file as it is now (a re-render makes it stale)"""
    try:
        d = json.load(open(rep))
    except (OSError, json.JSONDecodeError):
        return False
    return d.get("render") == os.path.abspath(f) and abs(d.get("render_mtime", 0) - os.path.getmtime(f)) < 1e-3


def summary(rep):
    """one line: stream facts, loudness, the failing and warning checks with their values"""
    try:
        d = json.load(open(rep))
    except (OSError, json.JSONDecodeError) as e:
        return f"no report ({e})"
    fx = d.get("facts", {})
    bad = [f"{c['id']}:{c['status']}({c['value']})" for c in d["checks"] if c["status"] in ("fail", "warn")]
    return (f"{d['summary']['status'].upper()} | {fx.get('width')}x{fx.get('height')} {fx.get('fps', 0):g} fps {fx.get('duration')} s, "
            f"{fx.get('I')} LUFS TP {fx.get('TP')} | " + (" ".join(bad) or "all pass"))


def hard_fails(rep):
    try:
        return [c["id"] for c in json.load(open(rep))["checks"] if c["status"] == "fail" and c["id"] in HARD]
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def loudnorm(src, dst):
    m = run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    tmp = dst + ".part.mp4"
    # -t: the re-encoded AAC loses the master's trim (edit list), so without a cap the audio stream reads ~2 frames longer
    # than the video and the duration check below stops the delivery (seen once: 33.733 -> 33.800 s)
    r = run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-af", af, "-ar", "48000",
             "-c:a", "aac", "-b:a", "256k", "-t", f"{duration(src):.3f}", "-movflags", "+faststart", tmp])
    if r.returncode:
        raise SystemExit(f"loudnorm failed {src}: {r.stderr[-400:]}")
    os.replace(tmp, dst)
    return j["input_i"]


def measured(p):
    e = run(["ffmpeg", "-nostats", "-hide_banner", "-i", p, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    i, tp = re.findall(r"I:\s+(-?[\d.]+) LUFS", e), re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)
    return (float(i[-1]) if i else None), (float(tp[-1]) if tp else None)


def duration(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def video_key(r):
    return r.get("code") or r["title"]


def dest(r, content):
    if r.get("collection"):
        folder = os.path.join(content, "NOT POSTED", r["collection"], f"{r['date']} {r['title']} ({r['code']})")
        return folder, os.path.join(folder, f"{r['code']} – {r['style']}.mp4")
    tag = ", ".join(x for x in (r.get("code"), r.get("style")) if x)
    return None, os.path.join(content, "NOT POSTED", f"{r['date']} {r['title']}{f' ({tag})' if tag else ''}.mp4")


def deliver(reels, allow, dry):
    content = os.path.expanduser(os.environ.get("CONTENT", ""))
    work = os.path.expanduser(os.environ.get("TRACKER_WORK", content))
    if not content or not os.path.isdir(os.path.join(content, "NOT POSTED")):
        sys.exit(f"deliver needs CONTENT: your finished-videos library, a folder with a NOT POSTED/ subfolder (now: {content or 'unset'})")
    for r in reels:
        for k in ("title", "code", "style"):
            if not r.get(k) and not (k == "code" and not r.get("collection")):
                sys.exit(f"{r['name']}: deliver needs '{k}' (manifest or --{k})")
    done = {}
    for r in reels:
        src, rep = os.path.join(r["out"], f"{r['name']}.mp4"), os.path.join(r["out"], f"{r['name']}.qa.json")
        folder, dst = dest(r, content)
        if os.path.exists(dst):
            print("already", dst)
            done.setdefault(video_key(r), []).append((r, dst))
            deliver_nomusic(r, dst, content, dry)
            continue
        if not os.path.exists(src):
            print("MISSING", src)
            continue
        hard = hard_fails(rep) if current(rep, src) else None
        if hard is None:
            print(f"NOT QA'D {r['name']}: no QA report for this render; run `finals.py qa` first")
            continue
        why = r.get("allow") or next((x for x in allow if x == r["name"]), None)
        if hard and not why:
            print(f"HELD {r['name']}: hard QA fail {hard} (see {rep.replace('.json', '.html')}); --allow \"{r['name']}\" once it is judged fine")
            continue
        if dry:
            print(f"would deliver {src} -> {dst}" + (f" (allowed: {hard})" if hard else ""))
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        before = loudnorm(src, dst)
        i, tp = measured(dst)
        d0, d1 = duration(src), duration(dst)
        if abs(d0 - d1) > 0.05:
            raise SystemExit(f"duration changed {dst}: {d0} -> {d1}")
        with open(os.path.join(content, "_moves.tsv"), "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\treel-final\t{socket.gethostname().split('.')[0]}\t{src}\t{dst}\t{md5(dst)}\t{os.path.getsize(dst)}\n")
        print(f"delivered {r['name']}: {before} -> {i} LUFS, TP {tp} dBFS, {d1:.2f} s, {os.path.getsize(dst) // 2**20} MB"
              + (f" (hard fail allowed: {hard}, {why})" if hard else "") + f" -> {dst}")
        ledger("deliver", r, file=dst, value=i, note=f"TP {tp}")
        done.setdefault(video_key(r), []).append((r, dst))
        deliver_nomusic(r, dst, content, dry)
    if dry:
        return
    tracker(reels, done, content, work)


def deliver_nomusic(r, dst, content, dry):
    """file "<name> (no music).mp4" next to its final as "<final> – no music.mp4", same loudness pass"""
    src = os.path.join(r["out"], f"{r['name']} (no music).mp4")
    nd = dst[:-4] + " – no music.mp4"
    if os.path.exists(nd):
        r["no_music_file"] = os.path.relpath(nd, content)
        return print("already", nd)
    if not os.path.exists(src):
        return print(f"no no-music version of {r['name']} in {r['out']} (`finals.py nomusic` makes one; a final without a bed needs none)")
    fin = os.path.join(r["out"], f"{r['name']}.mp4")
    if os.path.exists(fin) and os.path.getmtime(src) < os.path.getmtime(fin):
        return print(f"HELD no-music {r['name']}: older than its final (run `finals.py nomusic` again)")
    if dry:
        return print(f"would deliver {src} -> {nd}")
    before = loudnorm(src, nd)
    i, tp = measured(nd)
    d0, d1 = duration(dst), duration(nd)
    if abs(d0 - d1) > 0.05:
        raise SystemExit(f"no-music duration {d1} s != final {d0} s: {nd}")
    with open(os.path.join(content, "_moves.tsv"), "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\treel-final\t{socket.gethostname().split('.')[0]}\t{src}\t{nd}\t{md5(nd)}\t{os.path.getsize(nd)}\n")
    ledger("deliver", r, file=nd, value=i, note=f"no music, TP {tp}")
    r["no_music_file"] = os.path.relpath(nd, content)
    print(f"delivered no-music {r['name']}: {before} -> {i} LUFS, TP {tp} dBFS, {d1:.2f} s -> {nd}")


@contextlib.contextmanager
def tracker_lock(content):
    """the lock every tracker writer takes (this file and any other tool of yours that writes TRACKER.csv)"""
    f = open(os.path.join(content, ".tracker.lock"), "a")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() - t0 > 120:
                raise SystemExit("TRACKER.csv is locked by another writer for 120 s")
            time.sleep(0.5)
    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def tracker(reels, done, content, work):
    with tracker_lock(content):
        tracker_rows(reels, done, content, work)


def tracker_v2(rows, hdr, done, content):
    """v2: one row per delivered version; an existing row (same final file) gets its machine numbers and no-music file"""
    by_file = {x[hdr.index("final file")]: x for x in rows[1:]}
    added = changed = 0
    for key, items in done.items():
        for r, dst in items:
            rel = os.path.relpath(dst, content)
            mins, rounds = machine_numbers(r)
            fill = {"reel": reel_of(r), "version": r.get("version") or r.get("style") or r["name"], "style": r.get("style", ""),
                    "lang": (r.get("language") or "")[:2].upper(), "project": tilde(r["project"]),
                    "no_music_file": r.get("no_music_file", ""), "render_minutes": mins, "change_rounds": rounds}
            if rel in by_file:
                x = by_file[rel]
                for k in ("no_music_file", "render_minutes", "change_rounds", "project", "reel", "version", "style", "lang"):
                    if fill[k] and (k in ("no_music_file", "render_minutes", "change_rounds") or not x[hdr.index(k)]):
                        if x[hdr.index(k)] != fill[k]:
                            x[hdr.index(k)] = fill[k]
                            changed += 1
                continue
            coll = r.get("collection")
            tag = ", ".join(x for x in (r.get("code"), r.get("style")) if x)
            row = {k: "" for k in hdr}
            row.update(fill)
            row.update({"status": "NOT POSTED", "date": r["date"], "title": f"{r['title']} ({tag})" if tag else r["title"],
                        "language": r.get("language", ""), "final file": rel,
                        "how the final was chosen": r.get("how") or f"{r.get('style') or 'the'} edit; the user approved its preview.",
                        "missing platforms (cross-post to-do)": "all (not posted yet)",
                        "notes": " ".join(x for x in ((f"Script: «{r['title_ru']}»." if r.get("title_ru") else ""), r.get("notes", "")) if x),
                        "post_type": "trial" if coll and "trial" in coll.lower() else ""})
            rows.append([row.get(k, "") for k in hdr])
            by_file[rel] = rows[-1]
            added += 1
    return added, changed


def tracker_rows(reels, done, content, work):
    """one TRACKER row per video once every reel of it in this batch is in the library"""
    want = {}
    for r in reels:
        want.setdefault(video_key(r), []).append(r)
    tp, dp = os.path.join(content, "TRACKER.csv"), os.path.join(work, "tracker_data.json")
    if not os.path.exists(tp):
        return print(f"no {tp}: tracker not updated")
    rows = list(csv.reader(open(tp, newline="", encoding="utf-8")))
    hdr = rows[0]
    data = json.load(open(dp, encoding="utf-8")) if os.path.exists(dp) else None
    have = {x[hdr.index("title")] for x in rows[1:]}
    added = changed = 0
    if "version" in hdr:
        added, changed = tracker_v2(rows, hdr, done, content)
        want = {}
    for key, rs in want.items():
        if len(done.get(key, [])) < len(rs):
            continue
        r = rs[0]
        coll = r.get("collection")
        title = f"{r['title']} ({', '.join(x for x in (r.get('code'), coll.lower() if coll else None) if x)})" if r.get("code") or coll else r["title"]
        if title in have:
            continue
        files = [d for _, d in done[key]]
        rel = os.path.relpath(os.path.dirname(files[0]) if coll else files[0], content)
        styles = [x.get("style") for x in rs if x.get("style")]
        row = {k: "" for k in hdr}
        row.update({"status": "NOT POSTED", "date": r["date"], "title": title, "language": r.get("language", ""), "final file": rel,
                    "how the final was chosen": r.get("how") or (f"{len(rs)} version(s) in this folder: {', '.join(styles)}." if coll else
                                                                 f"{r.get('style') or 'the'} edit; the user approved its preview."),
                    "missing platforms (cross-post to-do)": "all (not posted yet)",
                    "notes": " ".join(x for x in ((f"Script: «{r['title_ru']}»." if r.get("title_ru") else ""), r.get("notes", "")) if x)})
        rows.append([row.get(k, "") for k in hdr])
        if data is not None:
            data["tracker"].append(row)
        added += 1
    if not added and not changed:
        return print("tracker: nothing new")
    eol = "\r\n" if b"\r\n" in open(tp, "rb").read() else "\n"          # keep the file's own line endings
    with open(tp + ".tmp", "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator=eol).writerows(rows)
    os.replace(tp + ".tmp", tp)
    if data is not None:
        if "version" in hdr:                                               # v2: the JSON twin is the CSV, row for row
            data["tracker"] = [dict(zip(hdr, x + [""] * (len(hdr) - len(x)))) for x in rows[1:]]
            data["updated"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        with open(dp + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(dp + ".tmp", dp)
    mh = os.path.join(work, "make_html.py")
    if os.path.exists(mh):
        # a make_html.py in TRACKER_WORK (your own tracker page builder) runs with HOME at this library's parent
        env = dict(os.environ, HOME=os.path.dirname(content)) if os.path.dirname(content) != HOME else None
        res = subprocess.run([sys.executable, mh], capture_output=True, text=True, env=env, cwd=work)
        print(f"tracker rows added: {added}, fields updated: {changed} | TRACKER.html " + ("rebuilt" if res.returncode == 0 else f"FAILED {res.stderr[-300:]}"))
    else:
        print(f"tracker rows added: {added}, fields updated: {changed} (no make_html.py in {work}: TRACKER.html not rebuilt)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["preview", "render", "nomusic", "qa", "deliver"])
    ap.add_argument("projects", nargs="*")
    ap.add_argument("--batch", help="reels.json manifest")
    ap.add_argument("--out", help="where previews, finals and QA go (default <project>/finals)")
    ap.add_argument("--style"), ap.add_argument("--code"), ap.add_argument("--title"), ap.add_argument("--language")
    ap.add_argument("--date"), ap.add_argument("--collection")
    ap.add_argument("--only", help="comma-separated reel names from the manifest")
    ap.add_argument("--allow", action="append", default=[], help="deliver this reel despite a hard QA fail (its name)")
    ap.add_argument("--force", action="store_true", help="render without a current preview")
    ap.add_argument("--no-nomusic", action="store_true", help="render: skip the no-music version")
    ap.add_argument("--rounds", type=int, help="deliver: change rounds for the tracker (default: previews after the first)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)          # one line per reel as it finishes, also through ssh or a log
    reels = reels_from(a)
    if a.only:
        keep = {x.strip() for x in a.only.split(",")}
        reels = [r for r in reels if r["name"] in keep]
    print(f"{a.step}: {len(reels)} reel(s), HyperFrames {HF_VERSION}")
    if a.step == "deliver":
        return deliver(reels, a.allow, a.dry)
    for r in reels:
        {"preview": preview, "render": lambda r: render(r, a.force, not a.no_nomusic), "nomusic": nomusic, "qa": qa}[a.step](r)


if __name__ == "__main__":
    main()
