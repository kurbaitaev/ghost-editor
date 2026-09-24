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

SR = 48000


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def db(x):
    return 20 * np.log10(max(float(x), 1e-9))


def render_sfx_stem(project):
    """Render the composition with the take audio removed; returns the stem path."""
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
    open(os.path.join(td, "index.html"), "w").write(html)
    out = os.path.abspath(os.path.join(project, "build", "sfx_stem.mp4"))
    print("rendering the SFX-only stem for the level check...")
    r = subprocess.run(["npx", "hyperframes", "render", "-o", out, "--quiet"], cwd=td, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("stem render failed: " + r.stderr[-500:])
    shutil.rmtree(td, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("video")
    ap.add_argument("--fix")
    ap.add_argument("--no-stem", action="store_true", help="skip the SFX stem render (no level check)")
    a = ap.parse_args()
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

    sil = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", a.video, "-t", str(ev["speech"]), "-af", "silencedetect=noise=-38dB:d=0.8", "-f", "null", "-"]).stderr
    gaps = re.findall(r"silence_start: ([\d.]+)[\s\S]*?silence_duration: ([\d.]+)", sil)
    for s, d in gaps:
        probs.append(f"silence {float(d):.2f}s at {float(s):.2f}s inside the speech")
    os.makedirs(os.path.join(a.project, "build"), exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf", "fps=1/2,scale=216:384,tile=6x4", "-frames:v", "1", "-update", "1",
        os.path.join(a.project, "build", "contact.jpg")])
    print(f"\ncontact sheet: {os.path.join(a.project, 'build', 'contact.jpg')}")
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
