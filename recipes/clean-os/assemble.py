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
"""
import json, os, subprocess, sys

HERE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
C = json.load(open(os.path.join(HERE, "cut.json")))
SRC = os.path.expanduser(C["source"])
DF = os.path.join(HERE, C["denoised"])
SEGS = [tuple(s) for s in C["segments"]]
_wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", SRC],
                     capture_output=True, text=True).stdout
W4, H4 = (lambda s: (s["width"], s["height"]))(json.loads(_wh)["streams"][0])
rot = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_side_data=rotation", "-of", "csv=p=0", SRC], capture_output=True, text=True).stdout
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


# --- video: one file per framing, concat of trimmed ranges (select by time, exact, re-encoded once)
sel = "+".join(f"between(t,{a},{b})" for a, b, _ in SEGS)
for name, crop in (("wide", ""), ("tight", f"crop={TW}:{TH}:{TX}:{TY},")):
    out = os.path.join(HERE, f"assets/{name}.mp4")
    if os.path.exists(out):
        continue
    run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-an", "-vf",
         f"select='{sel}',setpts=N/30/TB,{crop}scale=1080:1920:flags=lanczos,{GRADE},fps=30,format=yuv420p",
         "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-movflags", "+faststart", out])

# --- voice: same ranges from the denoised track, 15 ms fades at joins
parts = []
for i, (a, b, _) in enumerate(SEGS):
    p = os.path.join(HERE, f"build/segs/v{i:02d}.wav")
    d = b - a
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-t", f"{d:.3f}", "-i", DF, "-af",
         f"afade=t=in:d=0.015,afade=t=out:st={d - 0.015:.3f}:d=0.015", "-ar", "48000", "-ac", "1", p])
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

# --- map + words in edit time
mp, t = [], 0.0
for i, (a, b, note) in enumerate(SEGS):
    mp.append({"i": i, "a": a, "b": b, "start": round(t, 3), "end": round(t + b - a, 3), "note": note})
    t += b - a
json.dump(mp, open(os.path.join(HERE, "build/edl_map.json"), "w"), ensure_ascii=False, indent=1)
print(f"cut {t:.2f}s, {len(SEGS)} segments; tight crop {TW}x{TH}+{TX}+{TY}. Next: transcribe assets/voice.wav")
