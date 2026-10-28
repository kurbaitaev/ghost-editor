#!/usr/bin/env python3
"""Clean OS recipe, step 1: clean cut -> assets/{wide,tight}.mp4 + assets/voice.wav + build/edl_map.json

    python3 $S/recipes/clean-os/assemble.py <project>      (reads <project>/cut.json)

cut.json:
  {"source": "~/Downloads/clip.MOV",            # 4K vertical (2160x3840 after rotation) is ideal
   "denoised": "audio/df20/raw_DeepFilterNet3.wav",  # DeepFilterNet3 --atten-lim 20 output (see README)
   "segments": [[15.60, 17.35, "line text"], ...],   # best COMPLETE take of each line, original seconds
   "eyes": [0.47, 0.455],                        # face position (fraction of frame) from face_track.py median
   "tight": 1.6,                                 # tight-shot zoom (<= source_width/1080, no upscaling)
   "grade": "eq=contrast=1.05:saturation=0.92:gamma=1.02,colorbalance=rs=-0.02:bs=0.03"}

One cut list, two framings: wide = full frame, tight = crop around the face; both 1080x1920.
Voice: same ranges, 15 ms fades at joins, warmth EQ, -16 LUFS. Then re-transcribe assets/voice.wav for caption timing
(whisper smears words across false starts in the raw file).

Lip sync: every segment edge is snapped to the 30 fps frame grid and the SAME snapped times cut the picture and the voice,
so each piece is a whole number of frames in both. (Unsnapped, each video piece rounded to whole frames while the voice was
cut at the exact times: over a 23-piece cut the picture ran ~2 frames long and the voice ended 43-54 ms early.) The
script checks the result: frames of wide/tight == round(voice duration x 30), else it exits 1.
"""
import json, os, subprocess, sys

HERE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
C = json.load(open(os.path.join(HERE, "cut.json"), encoding="utf-8"))
SRC = os.path.expanduser(C["source"])
DF = os.path.join(HERE, os.path.expanduser(C["denoised"]))
FPS = 30


def snap(t):
    """original seconds -> the nearest frame boundary (both the picture and the voice are cut there)"""
    return round(t * FPS) / FPS


SEGS = [(snap(s[0]), snap(s[1]), s[2] if len(s) > 2 else "") for s in C["segments"]]
FRAMES = [round((b - a) * FPS) for a, b, _ in SEGS]
if min(FRAMES) < 1:
    sys.exit(f"segment {FRAMES.index(min(FRAMES))} is shorter than one frame after snapping")
_wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", SRC],
                     capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
W4, H4 = (lambda s: (s["width"], s["height"]))(json.loads(_wh)["streams"][0])
rot = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_side_data=rotation", "-of", "csv=p=0", SRC], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
if any(r.strip(", ") in ("90", "-90", "270", "-270") for r in rot.split()):
    W4, H4 = H4, W4
EYES_X, EYES_Y = C.get("eyes", [0.5, 0.42])[0] * W4, C.get("eyes", [0.5, 0.42])[1] * H4
TW, TH = int(W4 / C.get("tight", 1.6)) // 2 * 2, int(H4 / C.get("tight", 1.6)) // 2 * 2
TX = int(min(max(EYES_X - TW / 2, 0), W4 - TW)) // 2 * 2
TY = int(min(max(EYES_Y - 0.38 * TH, 0), H4 - TH)) // 2 * 2
GRADE = C.get("grade", "eq=contrast=1.05:saturation=0.92:gamma=1.02,colorbalance=rs=-0.02:bs=0.03")

os.makedirs(os.path.join(HERE, "build/segs"), exist_ok=True)
os.makedirs(os.path.join(HERE, "assets"), exist_ok=True)


def run(cmd):
    subprocess.run(cmd, check=True)


# --- video: one file per framing, concat of trimmed ranges (select by time, exact, re-encoded once).
# fps=30 first, so every frame sits on the grid; then each range keeps the frames in [a, b) (half-frame tolerance):
# exactly round((b - a) * 30) frames per piece, the same length as its voice piece below.
H = 0.5 / FPS
sel = "+".join(f"between(t,{a - H:.6f},{b - H:.6f})" for a, b, _ in SEGS)
# An HDR source (iPhone HLG / PQ) is tone-mapped to SDR BT.709 first (one HDR plate turns the whole render HDR);
# plates get a keyframe every 1 s (HyperFrames seeks them on every frame; x264's default 250 left 8 s gaps).
sys.path.insert(0, os.path.expanduser("~/.claude/skills/ghost-editor/scripts"))
try:
    import grade_lib
    SDR = grade_lib.sdr_vf(SRC, os.path.join(HERE, "build/sdr.cube"))
except ImportError:
    SDR = ""
SDR = SDR + "," if SDR else ""
for name, crop in (("wide", ""), ("tight", f"crop={TW}:{TH}:{TX}:{TY},")):
    out = os.path.join(HERE, f"assets/{name}.mp4")
    if os.path.exists(out):
        continue
    run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-an", "-vf",
         f"{SDR}fps={FPS},select='{sel}',setpts=N/{FPS}/TB,{crop}scale=1080:1920:flags=lanczos,{GRADE},format=yuv420p",
         "-frames:v", str(sum(FRAMES)), "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-g", str(FPS), "-keyint_min", str(FPS),
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", out])

# --- voice: the same snapped ranges from the denoised track, sample-exact, 15 ms fades at joins
SR = 48000
parts = []
for i, (a, b, _) in enumerate(SEGS):
    p = os.path.join(HERE, f"build/segs/v{i:02d}.wav")
    n = FRAMES[i] * SR // FPS                      # whole frames of audio: 1600 samples per frame at 48 kHz
    d = n / SR
    run(["ffmpeg", "-v", "error", "-y", "-i", DF, "-af",
         f"aresample={SR},atrim=start_sample={round(a * SR)}:end_sample={round(a * SR) + n},asetpts=N/SR/TB,apad=whole_len={n},"
         f"afade=t=in:d=0.015,afade=t=out:st={d - 0.015:.6f}:d=0.015", "-ar", str(SR), "-ac", "1", p])
    parts.append(p)
lst = os.path.join(HERE, "build/segs/v.txt")
open(lst, "w", encoding="utf-8").write("".join(f"file '{p}'\n" for p in parts))
raw = os.path.join(HERE, "build/voice_raw.wav")
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-af",
     "highpass=f=70,equalizer=f=180:t=q:w=1.2:g=2.5,equalizer=f=3200:t=q:w=1.5:g=1", raw])
m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af",
     f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000",
     "-ar", "48000", os.path.join(HERE, "assets/voice.wav")])

# --- map in edit time (whole frames, so edit times are exact frame boundaries)
mp, acc = [], 0
for i, (a, b, note) in enumerate(SEGS):
    mp.append({"i": i, "a": round(a, 4), "b": round(b, 4), "start": round(acc / FPS, 4), "end": round((acc + FRAMES[i]) / FPS, 4),
               "frames": FRAMES[i], "note": note})
    acc += FRAMES[i]
json.dump(mp, open(os.path.join(HERE, "build/edl_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# --- check: the picture and the voice have the same length (the lip-sync regression check)
def frames(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                        "-of", "csv=p=0", f], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    return int(r or 0)


vdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", os.path.join(HERE, "assets/voice.wav")],
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout)
bad = []
for name in ("wide", "tight"):
    nf = frames(os.path.join(HERE, f"assets/{name}.mp4"))
    print(f"{name}.mp4: {nf} frames; voice {vdur:.4f}s = {vdur * FPS:.2f} frames; cut list {acc} frames")
    if nf != acc or abs(vdur * FPS - acc) > 0.5:
        bad.append(name)
print(f"cut {acc / FPS:.3f}s ({acc} frames), {len(SEGS)} segments; tight crop {TW}x{TH}+{TX}+{TY}. Next: transcribe assets/voice.wav")
if bad:
    sys.exit(f"LIP SYNC: {', '.join(bad)} length differs from the voice (delete assets/{{wide,tight}}.mp4 made by an older assemble.py and rerun)")
