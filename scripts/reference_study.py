#!/usr/bin/env python3
"""Reverse-engineer a reference edit you want to match.

    reference_study.py <edited.mp4> --out <dir> [--model gemini-2.5-pro] [--raw raw.mp4]

Writes into <dir>:
  sheet.jpg          1 frame per second, timestamped (look at it first)
  frames/f_<t>.png   full-resolution frames every 2 s (check Gemini's claims here)
  raw_sheet.jpg      the raw take, 1 frame per 4 s (with --raw)
  edit-log.md        Gemini's second-by-second edit log (prompt:
                     references/reference-study-prompt.md), with a header
Gemini gets styles wrong (it called light lowercase captions "ExtraBold"),
so the edit log is a draft: verify type, sizes and framing against frames/
before building. Then map every scene to a word time of the raw transcript.

Needs GEMINI_API_KEY (env or <skill>/.env) and google-genai. The key is
validated with one cheap call first; transient errors retry twice; an error
is never written as if it were analysis.
"""
import argparse
import datetime
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from broll_gen import key  # noqa: E402  (same key resolution)


def sh(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--raw")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video],
                               capture_output=True, text=True).stdout)
    cols = 10
    rows = int(dur) // cols + 1
    sh(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf",
        f"fps=1,scale=180:-2,drawtext=text='%{{pts\\:hms}}':x=4:y=4:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.6,tile={cols}x{rows}",
        "-frames:v", "1", "-update", "1", os.path.join(a.out, "sheet.jpg")])
    for t in range(0, int(dur), 2):
        sh(["ffmpeg", "-v", "error", "-y", "-ss", str(t + 0.5), "-i", a.video, "-frames:v", "1", "-update", "1",
            os.path.join(a.out, "frames", f"f_{t + 0.5:05.1f}.png")])
    if a.raw:
        sh(["ffmpeg", "-v", "error", "-y", "-i", a.raw, "-vf", "fps=1/4,scale=180:-2,tile=8x3", "-frames:v", "1", "-update", "1",
            os.path.join(a.out, "raw_sheet.jpg")])
    print(f"sheet.jpg, {int(dur) // 2} frames -> {a.out}")

    from google import genai
    client = genai.Client(api_key=key())
    ping = client.models.generate_content(model="gemini-2.5-flash", contents="Reply with the single word: ok")
    if not (ping.text or "").strip():
        sys.exit("Gemini key check failed (empty reply); not running the analysis")
    prompt = open(os.path.join(SKILL, "references", "reference-study-prompt.md")).read()
    f = client.files.upload(file=a.video)
    for _ in range(60):
        f = client.files.get(name=f.name)
        if str(f.state).endswith("ACTIVE"):
            break
        time.sleep(3)
    else:
        sys.exit(f"upload never became ACTIVE: {f.state}")
    last = None
    for attempt in range(3):
        try:
            r = client.models.generate_content(model=a.model, contents=[f, prompt])
            text = r.text or ""
            if len(text) < 500:
                raise RuntimeError(f"suspiciously short reply ({len(text)} chars)")
            break
        except Exception as e:  # transient: retry, never save the error as analysis
            last = e
            time.sleep(5 * (attempt + 1))
    else:
        sys.exit(f"analysis failed after 3 tries: {last}")
    hdr = (f"# Reference study: {os.path.basename(a.video)}\n\n"
           f"- analysed {datetime.date.today().isoformat()} with {a.model}, {dur:.1f} s\n"
           f"- DRAFT: verify fonts, sizes and framing against frames/ before building\n\n")
    open(os.path.join(a.out, "edit-log.md"), "w").write(hdr + text)
    print(f"edit-log.md ({len(text)} chars) -> {a.out}")


if __name__ == "__main__":
    main()
