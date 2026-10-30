#!/usr/bin/env python3
"""Clean OS recipe, step 1: clean cut -> assets/{wide,tight}.mp4 (+ alt.mp4) + assets/voice.wav + build/edl_map.json

    python3 $S/recipes/clean-os/assemble.py <project> [--plan build/plan.json] [--alt] [--facescan build/facescan.json]

cut.json:
  {"source": "~/Downloads/clip.MOV",            # 4K vertical (2160x3840 after rotation) is ideal
   "denoised": "audio/df20/raw_DeepFilterNet3.wav",  # DeepFilterNet3 --atten-lim 20 output (see README); with --plan the
                                                 # default is the audio the plan was made on
   "segments": [[15.60, 17.35, "line text"], ...],   # best COMPLETE take of each line, original seconds (not with --plan)
   "eyes": [0.47, 0.455],                        # face position (fraction of frame) from face_track.py median; without it
                                                 # the tight crop centres on the median nose in build/facescan.json
   "tight": 1.6,                                 # tight-shot zoom (<= source_width/1080, no upscaling; 1.3 = a camera change)
   "framings": ["wide", "tight", "alt"],         # default wide + tight; alt (or --alt) = one plate, wide/tight switching at
                                                 # take changes only (plan pieces with "same" keep the framing)
   "grade": ""}                                  # none by default: the speaker's face is never regraded (references/broll.md 1)

--plan: plan_cut.py pieces: the picture is cut at va/vb and the voice at a/b, so split edits (vearly) work and the total
stays frame-exact. With alt the script also writes build/rawcut.mp4 (alt + voice): the raw cut to review / qa_cut.py.
One cut list, one decode, every framing; 1080x1920. A plate is rebuilt when build/plates.json says it was made from a
different cut, crop or grade (delete it to force a rebuild).
Voice: same ranges, 15 ms fades at joins, warmth EQ, -16 LUFS (voice_smooth.py <project> --plan ... for the smooth chain).
Then re-transcribe assets/voice.wav for caption timing (whisper smears words across false starts in the raw file).

Lip sync: every segment edge is snapped to the 30 fps frame grid and the SAME snapped times cut the picture and the voice,
so each piece is a whole number of frames in both. (Unsnapped, each video piece rounded to whole frames while the voice was
cut at the exact times: over a 23-piece cut the picture ran ~2 frames long and the voice ended 43-54 ms early.) After
fps=30 every frame sits on the grid and select keeps [va, vb) with half-frame tolerance: exactly round((vb - va) x 30)
frames per piece. The script checks the result: frames of every plate == round(voice duration x 30), else it exits 1.
"""
import argparse, hashlib, json, os, statistics, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("project", nargs="?", default=".")
ap.add_argument("--plan", help="plan_cut.py output (pieces with a/b voice, va/vb picture)")
ap.add_argument("--alt", action="store_true", help="also build assets/alt.mp4 (wide/tight switching at take changes)")
ap.add_argument("--facescan", help="facescan.py rows for the tight crop centre (default build/facescan.json)")
A = ap.parse_args()
HERE = os.path.abspath(A.project)
C = json.load(open(os.path.join(HERE, "cut.json")))
SRC = os.path.expanduser(C["source"])
PLAN = json.load(open(os.path.join(HERE, A.plan))) if A.plan else None
DF = os.path.join(HERE, os.path.expanduser(C["denoised"])) if C.get("denoised") else (PLAN or {}).get("audio") or sys.exit("cut.json needs \"denoised\"")
FPS = 30
FRAMINGS = list(dict.fromkeys(C.get("framings", ["wide", "tight"]) + (["alt"] if A.alt else [])))


def snap(t):
    """original seconds -> the nearest frame boundary (both the picture and the voice are cut there)"""
    return round(t * FPS) / FPS


# pieces: voice a/b, picture va/vb (equal unless a split edit), note, same (sub-piece of the previous take)
if PLAN:
    SEGS = [(snap(q["a"]), snap(q["b"]), snap(q.get("va", q["a"])), snap(q.get("vb", q["b"])), q.get("note", ""), bool(q.get("same")))
            for q in PLAN["pieces"]]
else:
    SEGS = [(snap(s[0]), snap(s[1]), snap(s[0]), snap(s[1]), s[2] if len(s) > 2 else "", False) for s in C["segments"]]
FRAMES = [round((b - a) * FPS) for a, b, *_ in SEGS]
VFRAMES = [round((vb - va) * FPS) for _, _, va, vb, _, _ in SEGS]
if min(FRAMES + VFRAMES) < 1:
    sys.exit(f"piece {(FRAMES + VFRAMES).index(min(FRAMES + VFRAMES)) % len(SEGS)} is shorter than one frame after snapping")
if sum(FRAMES) != sum(VFRAMES):
    sys.exit(f"picture {sum(VFRAMES)} frames vs voice {sum(FRAMES)}: a split edit (vearly) on the last piece has no next piece")
for k in range(1, len(SEGS)):
    if SEGS[k][2] < SEGS[k - 1][3] - 1e-6:
        sys.exit(f"piece {k} ({SEGS[k][4]}) starts at {SEGS[k][2]:.3f} before piece {k - 1} ends ({SEGS[k - 1][3]:.3f}): the select-based "
                 "decode keeps source order, so pieces must run forward in the recording")
_wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", SRC],
                     capture_output=True, text=True).stdout
W4, H4 = (lambda s: (s["width"], s["height"]))(json.loads(_wh)["streams"][0])
rot = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_side_data=rotation", "-of", "csv=p=0", SRC], capture_output=True, text=True).stdout
if any(r.strip(", ") in ("90", "-90", "270", "-270") for r in rot.split()):
    W4, H4 = H4, W4
TW, TH = int(W4 / C.get("tight", 1.6)) // 2 * 2, int(H4 / C.get("tight", 1.6)) // 2 * 2
fsp = A.facescan or (os.path.join(HERE, C["facescan"]) if C.get("facescan") else os.path.join(HERE, "build/facescan.json"))
NOSE = None
if "eyes" not in C and os.path.exists(fsp):   # median nose over the frames the cut shows (facescan px of a 1080-wide frame)
    rows = [r for r in json.load(open(fsp)) if r[1] is not None and len(r) > 10 and any(va <= r[0] < vb for _, _, va, vb, _, _ in SEGS)]
    if rows:
        NOSE = (statistics.median(r[9] for r in rows) * W4 / 1080, statistics.median(r[10] for r in rows) * W4 / 1080)
if NOSE:   # render_cut.py's crop: nose centred across, at the same relative height as in the full frame
    TX = int(min(max(NOSE[0] - TW / 2, 0), W4 - TW)) // 2 * 2
    TY = int(min(max(NOSE[1] - (NOSE[1] / H4) * TH, 0), H4 - TH)) // 2 * 2
else:
    EYES_X, EYES_Y = C.get("eyes", [0.5, 0.42])[0] * W4, C.get("eyes", [0.5, 0.42])[1] * H4
    TX = int(min(max(EYES_X - TW / 2, 0), W4 - TW)) // 2 * 2
    TY = int(min(max(EYES_Y - 0.38 * TH, 0), H4 - TH)) // 2 * 2
GRADE = C.get("grade", "")

os.makedirs(os.path.join(HERE, "build/segs"), exist_ok=True)
os.makedirs(os.path.join(HERE, "assets"), exist_ok=True)


def run(cmd):
    subprocess.run(cmd, check=True)


# --- video: one decode, a plate per framing (select by time on the 30 fps grid, exact, re-encoded once).
# fps=30 first, so every frame sits on the grid; then each range keeps the frames in [va, vb) (half-frame tolerance):
# exactly round((vb - va) * 30) frames per piece, the same length as its voice piece below (split edits shift the
# picture/voice boundary inside the cut, never the total).
H = 0.5 / FPS
sel = "+".join(f"between(t,{va - H:.6f},{vb - H:.6f})" for _, _, va, vb, _, _ in SEGS)
SHOT = []                                           # alt: 0 wide / 1 tight per piece; flips only at take changes
for k, s in enumerate(SEGS):
    SHOT.append(0 if k == 0 else (SHOT[-1] if s[5] else 1 - SHOT[-1]))
starts = [sum(VFRAMES[:k]) for k in range(len(SEGS))]
tight_on = "+".join(f"between(t,{(starts[k] - 0.5) / FPS:.6f},{(starts[k] + VFRAMES[k] - 0.5) / FPS:.6f})" for k in range(len(SEGS)) if SHOT[k]) or "0"
# An HDR source (iPhone HLG / PQ) is tone-mapped to SDR BT.709 first (one HDR plate turns the whole render HDR);
# plates get a keyframe every 1 s (HyperFrames seeks them on every frame; x264's default 250 left 8 s gaps).
for p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"), os.path.expanduser("~/.claude/skills/ghost-editor/scripts")):
    sys.path.insert(len(sys.path), p)
from x264 import THREADS as X264_THREADS  # noqa: E402  (scripts/X264_THREADS)
try:
    import grade_lib
    SDR = grade_lib.sdr_vf(SRC, os.path.join(HERE, "build/sdr.cube"))
except ImportError:
    SDR = ""
SDR = SDR + "," if SDR else ""
G = f",{GRADE}" if GRADE else ""
CROP = f"crop={TW}:{TH}:{TX}:{TY},"
SC = f"scale=1080:1920:flags=lanczos{G},format=yuv420p"
sig = lambda name: hashlib.sha1(json.dumps([SRC, sel, SDR, G, CROP if name != "wide" else "", tight_on if name == "alt" else ""]).encode()).hexdigest()
stp = os.path.join(HERE, "build/plates.json"); stamps = json.load(open(stp)) if os.path.exists(stp) else {}
todo = [n for n in FRAMINGS if not (os.path.exists(os.path.join(HERE, f"assets/{n}.mp4")) and stamps.get(n) == sig(n))]
if todo:
    br = {"wide": 1, "tight": 1, "alt": 2}; nb = sum(br[n] for n in todo); fc = [f"[0:v]{SDR}fps={FPS},select='{sel}',setpts=N/{FPS}/TB,split={nb}" + "".join(f"[b{i}]" for i in range(nb))]
    i = 0
    for n in todo:
        if n == "wide": fc.append(f"[b{i}]{SC}[wide]")
        elif n == "tight": fc.append(f"[b{i}]{CROP}{SC}[tight]")
        else: fc.append(f"[b{i}]{SC}[aw];[b{i + 1}]{CROP}{SC}[at];[aw][at]overlay=0:0:enable='{tight_on}',format=yuv420p[alt]")
        i += br[n]
    outs = []
    for n in todo:
        outs += ["-map", f"[{n}]", "-frames:v", str(sum(VFRAMES)), "-c:v", "libx264", "-threads", X264_THREADS, "-preset", "medium", "-crf", "17", "-g", str(FPS), "-keyint_min", str(FPS),
                 "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart",
                 os.path.join(HERE, f"assets/{n}.mp4")]
    run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-an", "-filter_complex", ";".join(fc)] + outs)
    stamps.update({n: sig(n) for n in todo}); json.dump(stamps, open(stp, "w"), indent=1)

# --- voice: the same snapped ranges from the denoised track, sample-exact, 15 ms fades at joins
SR = 48000
parts = []
for i, (a, b, *_) in enumerate(SEGS):
    p = os.path.join(HERE, f"build/segs/v{i:02d}.wav")
    n = FRAMES[i] * SR // FPS                      # whole frames of audio: 1600 samples per frame at 48 kHz
    d = n / SR
    run(["ffmpeg", "-v", "error", "-y", "-i", DF, "-af",
         f"aresample={SR},atrim=start_sample={round(a * SR)}:end_sample={round(a * SR) + n},asetpts=N/SR/TB,apad=whole_len={n},"
         f"afade=t=in:d=0.015,afade=t=out:st={d - 0.015:.6f}:d=0.015", "-ar", str(SR), "-ac", "1", p])
    parts.append(p)
lst = os.path.join(HERE, "build/segs/v.txt")
open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
raw = os.path.join(HERE, "build/voice_raw.wav")
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-af",
     "highpass=f=70,equalizer=f=180:t=q:w=1.2:g=2.5,equalizer=f=3200:t=q:w=1.5:g=1", raw])
m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True).stderr
j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af",
     f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000",
     "-ar", "48000", os.path.join(HERE, "assets/voice.wav")])

# --- map in edit time (whole frames, so edit times are exact frame boundaries); a/b/start/end = the voice, va/vb/vstart
# = the picture (they differ only around a split edit)
mp, acc = [], 0
for i, (a, b, va, vb, note, same) in enumerate(SEGS):
    mp.append({"i": i, "a": round(a, 4), "b": round(b, 4), "start": round(acc / FPS, 4), "end": round((acc + FRAMES[i]) / FPS, 4),
               "frames": FRAMES[i], "note": note, "va": round(va, 4), "vb": round(vb, 4), "vstart": round(starts[i] / FPS, 4),
               "same": same, "shot": "tight" if SHOT[i] else "wide"})
    acc += FRAMES[i]
json.dump(mp, open(os.path.join(HERE, "build/edl_map.json"), "w"), ensure_ascii=False, indent=1)


# --- check: the picture and the voice have the same length (the lip-sync regression check)
def frames(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                        "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip()
    return int(r or 0)


vdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", os.path.join(HERE, "assets/voice.wav")],
                            capture_output=True, text=True).stdout)
bad = []
for name in FRAMINGS:
    nf = frames(os.path.join(HERE, f"assets/{name}.mp4"))
    print(f"{name}.mp4: {nf} frames; voice {vdur:.4f}s = {vdur * FPS:.2f} frames; cut list {acc} frames")
    if nf != acc or abs(vdur * FPS - acc) > 0.5:
        bad.append(name)
crop = f"tight crop {TW}x{TH}+{TX}+{TY}" + (f" (nose {NOSE[0]:.0f},{NOSE[1]:.0f})" if NOSE else "")
print(f"cut {acc / FPS:.3f}s ({acc} frames), {len(SEGS)} pieces; {crop}" + (f"; alt: {sum(SHOT)} of {len(SEGS)} pieces tight" if "alt" in FRAMINGS else "")
      + ". Next: transcribe assets/voice.wav")
if bad:
    sys.exit(f"LIP SYNC: {', '.join(bad)} length differs from the voice (delete assets/{{wide,tight,alt}}.mp4 made by an older assemble.py and rerun)")
if "alt" in FRAMINGS:   # the raw cut: alt picture + voice, one file to watch / qa_cut.py
    rc = os.path.join(HERE, "build/rawcut.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(HERE, "assets/alt.mp4"), "-i", os.path.join(HERE, "assets/voice.wav"), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", rc])
    print(f"raw cut -> {rc} ({frames(rc)} frames)")
