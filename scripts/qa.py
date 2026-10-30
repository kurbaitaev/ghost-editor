#!/usr/bin/env python3
"""QA a rendered reel against its build.

    qa.py <project> <render.mp4> [--fix out.mp4]

Checks, with numbers:
  - streams, 1080x1920, duration matches the build
  - integrated loudness and true peak (target -14 to -16 LUFS, TP <= -1 dBTP)
  - every SFX hit vs the voice, on stems: a second render with the take audio
    stripped gives each hit's real peak; compared with the voice p95 peak the
    build measured and with the role target. Flags > +1.5 dB over the voice,
    < -22 dB (inaudible) and > 4 dB off target
  - silences > 0.8 s inside the speech (a pause that should have been cut)
  - a contact sheet (build/contact.jpg, 2 s tiles)
  - cutout windows (build/cutouts.json): each clip holds exactly its beat's frames, cut from the plate the takes play
  - lip-sync lengths: the render's video frames vs its audio duration x fps, and for a pre-cut source
    (assets/voice.wav next to assets/{wide,tight,cut}.mp4, the Clean OS layout) every picture file's frame
    count vs round(voice duration x fps): a mismatch is the per-piece rounding drift (voice early at the end).
    `--av-only` runs just this check (no build.mjs files needed).
--fix writes a copy with only a gentle true-peak limiter if TP is over -1;
it never adds gain (gain would re-break the SFX/voice balance).
"""
import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hf_version import hf  # noqa: E402  (scripts/HF_VERSION)

SR = 48000


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def db(x):
    return 20 * np.log10(max(float(x), 1e-9))


def render_sfx_stem(project):
    """Render the composition with the take audio and music bed removed; returns the stem path."""
    import shutil
    import tempfile
    project = os.path.abspath(project)
    td = tempfile.mkdtemp(prefix="sfxstem-")
    for f in os.listdir(project):
        if f in ("index.html", "assets"):
            src = os.path.join(project, f)
            (shutil.copytree if os.path.isdir(src) else shutil.copy)(src, os.path.join(td, f))
    html = open(os.path.join(td, "index.html")).read()
    html = re.sub(r'<audio id="take-\d+-audio"[^>]*></audio>', "", html)
    html = re.sub(r'<audio id="music-bed"[^>]*></audio>', "", html)  # the bed would read as loud SFX where it isn't ducked
    open(os.path.join(td, "index.html"), "w").write(html)
    out = os.path.abspath(os.path.join(project, "build", "sfx_stem.mp4"))
    print("rendering the SFX-only stem for the level check...")
    r = subprocess.run(hf("render", "-o", out, "--quiet"), cwd=td, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("stem render failed: " + r.stderr[-500:])
    shutil.rmtree(td, ignore_errors=True)
    return out


def count_frames(f):
    r = sh(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
            "-of", "csv=p=0", f]).stdout.strip()
    # ffmpeg 8 lists a stream twice when the file has a stream group (iPhone MOV/MP4): "1935\n\n1935"
    n = next((x for x in r.split() if x.isdigit()), None)
    return int(n) if n else 0


def stream_dur(f, kind):
    r = sh(["ffprobe", "-v", "error", "-select_streams", f"{kind}:0", "-show_entries", "stream=duration:format=duration",
            "-of", "json", f]).stdout
    j = json.loads(r or "{}")
    d = (j.get("streams") or [{}])[0].get("duration") or j.get("format", {}).get("duration")
    return float(d) if d not in (None, "N/A") else None


def check_av(project, video, fps=30):
    """Picture length vs voice length, in frames: the render, and a pre-cut source's picture files vs assets/voice.wav."""
    probs = []
    nf, ad = count_frames(video), stream_dur(video, "a")
    if ad:
        diff = nf - ad * fps
        print(f"a/v length: {nf} video frames, audio {ad:.3f}s = {ad * fps:.1f} frames ({diff:+.1f})")
        if abs(diff) > 1.0:  # AAC pads to 1024-sample packets (< 0.7 frame); more is a real length mismatch
            probs.append(f"render: {nf} video frames but {ad:.3f}s of audio ({diff:+.1f} frames): picture and sound lengths differ")
    voice = os.path.join(project, "assets", "voice.wav")
    if os.path.exists(voice):
        vd = stream_dur(voice, "a")
        for name in ("wide", "tight", "cut"):
            f = os.path.join(project, "assets", f"{name}.mp4")
            if not (vd and os.path.exists(f)):
                continue
            n = count_frames(f)
            want = round(vd * fps)
            print(f"a/v length: assets/{name}.mp4 {n} frames, assets/voice.wav {vd:.3f}s = {want} frames")
            if n != want:  # a frame-snapped assembly is exact; one frame off already means per-piece rounding
                probs.append(f"assets/{name}.mp4 has {n} frames for {vd:.3f}s of voice ({n - want:+d}): the cut drifts; "
                             "re-run the assembly with frame-snapped segments (recipes/clean-os/assemble.py)")
    return probs


def plate_of(spec):
    """The file the takes play: the source, the look.film plate, or the look.cutout plate (made from the film plate)."""
    look = spec.get("look") or {}
    src = (look.get("plate") or "assets/talk.film.mp4") if look.get("film") else spec["source"]
    if look.get("cutout"):
        lc = look["cutout"] if isinstance(look["cutout"], dict) else {"fx": look["cutout"]}
        src = lc.get("plate") or f"assets/talk.{lc.get('fx')}.mp4"
    return src


def check_cutouts(project):
    """Each cutout window (build/cutouts.json from build.mjs) must hold exactly the frames of its beat window, cut from
    the source the takes play; a stale clip (re-cut takes, a changed look) shows as a wrong count or source."""
    probs = []
    cp = os.path.join(project, "build", "cutouts.json")
    if not os.path.exists(cp):
        return probs
    wins = json.load(open(cp))
    spec = json.load(open(os.path.join(project, "reel.json")))
    src = plate_of(spec)
    for w in wins:
        f = os.path.join(project, w["src"])
        if not os.path.exists(f):
            probs.append(f"{w['id']}: {w['src']} missing (rebuild)")
            continue
        n = count_frames(f)
        side = os.path.join(project, w["src"] + ".json")
        sf = json.load(open(side)).get("frames") if os.path.exists(side) else None
        print(f"cutout {w['id']} {w['fx']} at {w['at']}: {n} frames (window {w['srcFrames']}), edit {w['start']} s, source {w['ss']} s")
        if n != w["srcFrames"] or (sf is not None and sf != n):
            probs.append(f"{w['id']}: {n} frames, the window needs {w['srcFrames']} (sidecar {sf}): rebuild")
        if w.get("source") != src:
            probs.append(f"{w['id']}: cut from {w.get('source')}, the takes play {src}: rebuild")
    return probs


def check_matte(project):
    """assets/talk-matte.webm must line up frame for frame with the source it was cut from, and carry matted frames."""
    probs = []
    rp = os.path.join(project, "reel.json")
    if not os.path.exists(rp):  # recipe projects (seoul-list, clean-os) have no reel.json and no matte
        return probs
    spec = json.load(open(rp))
    mp = os.path.join(project, "assets", "talk-matte.webm")
    panels = any(b.get("type") == "panel" and b.get("behind", True) for b in spec.get("beats") or [])  # stan style
    if not (spec.get("matte") or panels) or not os.path.exists(mp):
        return probs
    src = plate_of(spec)
    nm, ns = count_frames(mp), count_frames(os.path.join(project, src))
    side = os.path.join(project, "assets", "talk-matte.json")
    rep = json.load(open(side)).get("report", {}) if os.path.exists(side) else {}
    print(f"matte: {nm} frames (source {ns}), {rep.get('wanted', '?')} matted, {rep.get('model', 'hyperframes u2net')} on {rep.get('device', '?')}")
    if nm != ns:
        probs.append(f"matte has {nm} frames, the source {ns}: delete assets/talk-matte.* and rebuild")
    if rep and rep.get("wanted", 1) == 0:
        probs.append("matte: no matted frames (are there behind beats?)")
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("video")
    ap.add_argument("--fix")
    ap.add_argument("--no-stem", action="store_true", help="skip the SFX stem render (no level check)")
    ap.add_argument("--av-only", action="store_true", help="only the picture-vs-voice length check (any project layout)")
    a = ap.parse_args()
    if a.av_only:
        probs = check_av(a.project, a.video)
        print("\nPROBLEMS:\n  " + "\n  ".join(probs) if probs else "\na/v lengths match")
        sys.exit(1 if probs else 0)
    ev = json.load(open(os.path.join(a.project, "build", "sfx_events.json")))
    probs = []

    info = json.loads(sh(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", a.video]).stdout)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    has_a = any(s["codec_type"] == "audio" for s in info["streams"])
    dur = float(info["format"]["duration"])
    print(f"video {v[0]['width']}x{v[0]['height']}, audio {'yes' if has_a else 'NO'}, {dur:.2f}s (build {ev['total']}s)")
    if (v[0]["width"], v[0]["height"]) != (1080, 1920):
        probs.append("not 1080x1920")
    if not has_a:
        probs.append("no audio stream")
    if abs(dur - ev["total"]) > 0.2:
        probs.append(f"duration {dur:.2f} != build {ev['total']}")
    probs += check_av(a.project, a.video)

    lo = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", a.video, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", lo)[-1])
    TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo)[-1])
    print(f"loudness {I} LUFS, true peak {TP} dBTP")
    if not -17.5 <= I <= -12.5:
        probs.append(f"integrated {I} LUFS outside -17.5..-12.5 (voice should be prepped to -16)")
    if TP > -0.5:
        probs.append(f"true peak {TP} dBTP > -0.5")

    # SFX vs voice, on stems: the voice level build.mjs measured on the kept
    # words, the SFX from a second render with the take audio stripped.
    # Measuring hits inside the finished mix is useless: most overlap speech.
    print(f"voice p95 peak {ev['voiceP95']:.1f} dBFS (from build); role targets vs voice {ev['roleDb']}")
    if not a.no_stem:
        stem = render_sfx_stem(a.project)
        sx = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", stem, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                          capture_output=True).stdout, np.float32)
        print("\n   time  sfx                    role    peak   vs voice  target")
        for e in ev["events"]:
            i = int(e["t"] * SR)
            seg = sx[i:i + int((min(e["dur"], 3.0) + 0.1) * SR)]
            p = db(np.abs(seg).max()) if len(seg) else -120
            rel = p - ev["voiceP95"]
            tgt = ev["roleDb"][e["role"]]
            flag = ""
            if rel > 1.5:
                flag = "  <- louder than the voice"
            elif rel < -22:
                flag = "  <- probably inaudible"
            elif abs(rel - tgt) > 4:
                flag = f"  <- {rel - tgt:+.1f} dB off target (overlapping hits?)"
            if "louder" in flag or "inaudible" in flag:
                probs.append(f"sfx {e['id']} at {e['t']}s {rel:+.1f} dB vs voice")
            print(f"{e['t']:7.2f}  {e['id']:22s} {e['role']:7s} {p:6.1f}  {rel:+7.1f}  {tgt:+4d}{flag}")

    probs += check_matte(a.project)
    probs += check_cutouts(a.project)
    # captions vs the face (build/caption_layout.json from the face-aware placer)
    lay_p = os.path.join(a.project, "build", "caption_layout.json")
    if os.path.exists(lay_p):
        lay = json.load(open(lay_p))
        modes = {}
        for b in lay["blocks"]:
            modes[b["mode"]] = modes.get(b["mode"], 0) + 1
        print(f"captions ({lay['platform']['name']}, safe y {lay['safeTop']}-{lay['safeBottom']}): {modes}")
        off = [b for b in lay["blocks"] if b["y"] < lay["safeTop"] or b["y"] + b["h"] * b.get("scale", 1) > lay["safeBottom"] + 1]
        if off:
            probs.append(f"{len(off)} caption block(s) outside the platform safe area")
    else:
        print("captions: no build/caption_layout.json (run face_track.py and rebuild for face-aware placement)")

    tfx_p = os.path.join(a.project, "build", "textfx.json")
    tfx = json.load(open(tfx_p)) if os.path.exists(tfx_p) else []
    # transitions (scripts/transitions.py reel): count, punchy budget, and each window clip holds exactly its frames
    tp = os.path.join(a.project, "build", "transitions.json")
    if os.path.exists(tp):
        txs = json.load(open(tp))
        punchy = [t for t in txs if t["type"] in ("whip", "scaled_push", "flash", "static_wipe")]
        per_min = len(txs) / max(ev["speech"] / 60, 1e-6)
        print(f"transitions: {len(txs)} ({len(punchy)} punchy), {per_min:.1f}/min")
        if len(punchy) > 2:
            probs.append(f"{len(punchy)} punchy transitions (keep it to 2 per reel, at section changes)")
        if len(txs) > 3 and per_min > 6:  # a rate means nothing on a 10 s reel; the punchy budget covers that
            probs.append(f"{per_min:.1f} transitions/min (top reels: ~95% hard cuts)")
        for t in txs:
            n = count_frames(os.path.join(a.project, t["src"]))
            if n != t["frames"]:
                probs.append(f"{t['id']}: {n} frames, expected {t['frames']} (re-run transitions.py reel)")
    # Paper shader layers (look.shader, scene bg looks): scan the render for one-frame flicker (a missed GL draw, a seek glitch)
    html_p = os.path.join(a.project, "index.html")
    if os.path.exists(html_p) and "data-shader=" in open(html_p).read():
        fc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "framecheck.py")
        r = sh([sys.executable, fc, a.project, "--render", os.path.abspath(a.video), "--flicker-only"])
        rp = os.path.join(a.project, "build", "framecheck.json")
        if r.returncode == 0 and os.path.exists(rp):
            rep = json.load(open(rp))
            print(f"shader flicker scan: {rep['frames']} frames, ratio_max {rep['ratio_max']} (smooth ~0.5, a one-frame flash > 2.5)")
            # a textfx block's lock shake jitters the text every frame on purpose: not a shader glitch
            shake = [(b["t0"], b["t1"] or b["t0"] + 2.5) for b in tfx]
            for f in rep["flicker_frames"]:
                if any(a0 <= f["t"] <= a1 for a0, a1 in shake):
                    print(f"  {f['t']}s: inside a textfx block (its shake), ignored")
                else:
                    probs.append(f"one-frame flicker at {f['t']}s (frame {f['frame']}, ratio {f['ratio']}, luma spike {f['luma_jump']})")
        else:
            probs.append("shader flicker scan failed: " + (r.stderr or r.stdout)[-300:])
    sil = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", a.video, "-t", str(ev["speech"]), "-af", "silencedetect=noise=-38dB:d=0.8", "-f", "null", "-"]).stderr
    gaps = re.findall(r"silence_start: ([\d.]+)[\s\S]*?silence_duration: ([\d.]+)", sil)
    for s, d in gaps:
        probs.append(f"silence {float(d):.2f}s at {float(s):.2f}s inside the speech")
    os.makedirs(os.path.join(a.project, "build"), exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf", "fps=1/2,scale=216:384,tile=6x4", "-frames:v", "1", "-update", "1",
        os.path.join(a.project, "build", "contact.jpg")])
    print(f"\ncontact sheet: {os.path.join(a.project, 'build', 'contact.jpg')}")
    # kinetic type: one settled frame per textfx block (70 % in: text landed, before the exit), so the look covers them
    for i, b in enumerate(tfx):
        t = b["t0"] + 0.7 * ((b["t1"] or b["t0"] + 2.5) - b["t0"])
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", a.video, "-frames:v", "1", "-vf", "scale=360:640", "-update", "1",
            os.path.join(a.project, "build", f"textfx-{i:02d}-{b['kind']}.jpg")])
    if tfx:
        print(f"textfx: {len(tfx)} block(s), a settled frame of each in build/textfx-*.jpg")
    if a.fix:
        if TP > -1:
            sh(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-c:v", "copy", "-af", "alimiter=limit=0.89:level=false", "-c:a", "aac", "-b:a", "192k", a.fix])
        else:
            sh(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-c", "copy", a.fix])
        print(f"-> {a.fix}")
    print("\nPROBLEMS:\n  " + "\n  ".join(probs) if probs else "\nall checks passed")
    sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
