#!/usr/bin/env python3
"""Gemini 2.5 Pro audits of a talking-head recording or cut. The key (GEMINI_API_KEY or the skill .env, broll_gen.key())
is checked with one cheap Flash call before any upload.

    gem_audit.py check
    gem_audit.py attempts <video> <script.txt> --out build/attempts.md   every attempt of every script line (takes.py reads it)
    gem_audit.py gaze <video> --out build/gaze.md                        eye contact / head, video sampled at 5 fps
    gem_audit.py audit <video> --out build/audit.md                      strict raw-cut audit + verbatim transcript
    gem_audit.py ask <video> <prompt-file> --out answer.md

attempts uploads a 540x960 copy when the video is bigger (a whole recording; made in a temp dir).
Caveats: the 5 fps pass reads blinks and wide/tight switches as glances, and the audio pass reads crisp word onsets after
silence as clicks; its sub-second timestamps are loose. Verify every flag against frames (eyestrip.py) and energy before
acting on it. It does catch real restarts that whisper merged."""
import argparse, json, os, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from broll_gen import key
from x264 import THREADS as X264_THREADS  # scripts/X264_THREADS

ATTEMPTS = """This is a raw phone recording of one man reading a Russian script to the camera, with many retakes.
The speaker reads from a prompter/phone placed near the lens. The script (numbered lines):

{script}

Watch and listen to the WHOLE video, start to end. For EVERY attempt at every script line (including aborted ones and
partial re-reads of a line), output one row of a markdown table:
| line # | start mm:ss.s | end mm:ss.s | verbatim Russian of what the speaker actually said (every word, including repeats and fillers) | verdict | problems |
verdict is one of: CLEAN, STUMBLE, RESTART (aborted), WORDING (deviates from script), VISUAL (audio fine but visual problem).
problems: be specific and strict about BOTH audio (stumble, filler ээ/мм, swallowed or slurred word, wrong word, repeated word,
long pause inside the sentence, breath, laugh, throat clear, lip smack) and VISUAL (eyes leave the lens even briefly, eyes drop
to read, head turns or tilts, looks down, eyes closed long, smirks, adjusts, moves out of frame).
Also list non-script stretches (setup, talking to someone, checking phone, silence) as line '-'.
After the table, give 'BEST TAKE PER LINE': for each script line the best attempt's start-end and why; if no attempt is fully
clean, say which is least bad and what is wrong with it. Timestamps must come from the video timeline. Do not skip any part."""

GAZE = """You are checking a raw talking-head cut (one man speaking Russian to the camera) for EYE CONTACT and HEAD MOVEMENT only.
The video is sampled at 5 frames per second. Go through it frame by frame. List every moment, with timestamp mm:ss.s and duration,
where: (a) the speaker's eyes leave the camera lens (look down at notes, to the side, up) even briefly; (b) the head turns or drops noticeably;
(c) the eyes stay closed longer than a normal blink. A normal quick blink is NOT a problem; a natural small nod while talking with the
eyes still on the lens is NOT a problem; cuts between a wide and a close shot are intentional and NOT a problem.
For each item say how noticeable it is to a normal viewer on a phone: obvious / subtle. If the eye contact is steady throughout, say so."""

AUDIT = """This is a RAW talking-head cut in Russian: one man speaking to the camera, assembled from several takes with hard cuts
(no music, no graphics on purpose). Audit it like a strict video editor before it goes to the client. List EVERY problem
with its timestamp (mm:ss.s):
- AUDIO: a word clipped at a cut (start or end cut off), a repeated word or phrase, a false start, a stumble or slurred word,
  a filler (ээ, мм, э-э), an audible pause inside a sentence (longer than a natural comma), an audible breath/click/lip smack
  right at a cut, a sudden level or room-tone change at a cut, a sentence that sounds unfinished.
- VISUAL: the eyes leave the lens even for a moment (looking down at notes, to the side, up), the head turns or drops,
  a long eye closure, a smirk or odd face, the speaker moving out of position, a jarring jump at a cut.
- FLOW: sentences that do not connect logically, missing words that change meaning.
Also write out the full verbatim transcript of what is said, sentence by sentence, with start times.
Be concrete and honest; if a category has no problems, say "none". Do not invent problems."""


def client():
    from google import genai
    from google.genai import types
    return genai.Client(api_key=key(), http_options=types.HttpOptions(timeout=600_000)), types


def check(cl):
    r = cl.models.generate_content(model="gemini-2.5-flash", contents="Reply with the single word: ok")
    if not (r.text or "").strip(): sys.exit("Gemini key check failed")
    print("key ok:", r.text.strip(), flush=True)


def upload(cl, path):
    f = cl.files.upload(file=path)
    for _ in range(200):
        f = cl.files.get(name=f.name)
        if str(f.state).endswith("ACTIVE"): return f
        if str(f.state).endswith("FAILED"): sys.exit(f"upload failed: {path}")
        time.sleep(3)
    sys.exit(f"upload never ACTIVE: {path}")


def small_copy(video, td):
    """a 540x960 (or smaller) H.264 copy for the upload when the video is bigger"""
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation",
                                   "-of", "json", video], capture_output=True, text=True).stdout)["streams"][0]
    w, h = s["width"], s["height"]
    if any(abs(d.get("rotation", 0)) in (90, 270) for d in s.get("side_data_list", [])): w, h = h, w
    if max(w, h) <= 960: return video
    out = os.path.join(td, "upload.mp4"); vf = "scale=540:960" if h >= w else "scale=960:540"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", vf,
                    "-c:v", "libx264", "-threads", X264_THREADS, "-preset", "veryfast", "-b:v", "1000k",
                    "-c:a", "aac", "-b:a", "96k", "-ac", "1", "-movflags", "+faststart", out], check=True)
    print(f"upload copy {os.path.getsize(out) / 1e6:.0f} MB ({vf})", flush=True)
    return out


def generate(cl, types, contents, minlen, temperature=0.2, max_tokens=60000):
    last = None
    for attempt in range(4):
        try:
            r = cl.models.generate_content(model="gemini-2.5-pro", contents=contents,
                                           config=types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens))
            text = r.text or ""
            if len(text) < minlen: raise RuntimeError(f"short reply ({len(text)} chars)")
            return text
        except Exception as e:
            last = e; print("retry:", e, flush=True); time.sleep(15 * (attempt + 1))
    sys.exit(f"failed after 4 tries: {last}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p = sub.add_parser("attempts"); p.add_argument("video"); p.add_argument("script"); p.add_argument("--out", required=True)
    p = sub.add_parser("gaze"); p.add_argument("video"); p.add_argument("--out", required=True)
    p = sub.add_parser("audit"); p.add_argument("video"); p.add_argument("--out", required=True)
    p = sub.add_parser("ask"); p.add_argument("video"); p.add_argument("prompt"); p.add_argument("--out", required=True)
    A = ap.parse_args()
    cl, types = client()
    check(cl)
    if A.cmd == "check": return
    with tempfile.TemporaryDirectory() as td:
        f = upload(cl, small_copy(A.video, td) if A.cmd == "attempts" else A.video)
    print("uploaded", f.name, flush=True)
    if A.cmd == "attempts":
        text = generate(cl, types, [f, ATTEMPTS.format(script=open(A.script).read())], minlen=1500)
    elif A.cmd == "gaze":   # dense visual audit: the video sampled at 5 fps instead of the default 1 fps
        part = types.Part(file_data=types.FileData(file_uri=f.uri, mime_type=f.mime_type), video_metadata=types.VideoMetadata(fps=5))
        text = generate(cl, types, [types.Content(parts=[part, types.Part(text=GAZE)])], minlen=30, temperature=0.1, max_tokens=30000)
    elif A.cmd == "audit":
        text = generate(cl, types, [f, AUDIT], minlen=200)
    else:
        text = generate(cl, types, [f, open(A.prompt).read()], minlen=50)
    os.makedirs(os.path.dirname(os.path.abspath(A.out)), exist_ok=True)
    open(A.out, "w").write(text); print(f"wrote {A.out} ({len(text)} chars)")


if __name__ == "__main__":
    main()
