#!/usr/bin/env python3
"""Clean cut of 'Один обычный день' (C007) -> assets/{wide,tight}.mp4 + assets/voice.wav + build/edl_map.json + build/words.edit.json

One cut list, two framings rendered from the 4K source (2160x3840 after rotation):
  wide  = full frame -> 1080x1920
  tight = 1.6x crop (1350x2400) around the face -> 1080x1920 (downscale only, no upscaling)
Voice: DeepFilterNet3 (attenuation capped at 20 dB, so it does not go thin/watery) + light warmth EQ,
cut on the same list with 15 ms fades at every join, normalised to -16 LUFS.
Take choice: the best COMPLETE take of each line; pause boundaries from silencedetect on the denoised track.
"""
import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Downloads/iPhone 001_10071923_C007.MOV")
DF = os.path.join(HERE, "audio/df20/raw_DeepFilterNet3.wav")
SEGS = [  # (a, b, note)  original seconds
    (15.60, 17.35, "Представь, что тебе 80 лет."),
    (28.60, 33.30, "И каким-то образом ты можешь вернуться и прожить один обычный день из твоей сегодняшней жизни."),
    (42.75, 46.40, "Не какое-то важное событие, не день свадьбы, а просто сегодня."),
    (64.45, 69.50, "Ты просыпаешься… видишь людей, которых видишь каждый день."),
    (85.99, 89.30, "сейчас тебя раздражает, ощущалось бы совсем иначе."),
    (91.85, 95.65, "Потому что ты знаешь, ничто из этого не останется с тобой навсегда."),
    (111.70, 115.34, "Мне кажется, мы забываем об этом, когда каждый раз торопимся к чему-то следующему."),
    (129.15, 131.16, "Поэтому иногда просто оглянись вокруг."),
    (135.20, 137.35, "Почувствуй жизнь, которую ты сейчас живёшь."),
    (139.75, 142.25, "Однажды этот момент станет воспоминанием."),
    (147.50, 150.30, "Но прямо сейчас ты всё ещё здесь."),
]
W4, H4 = 2160, 3840
EYES_X, EYES_Y = 0.47 * W4, 0.455 * H4          # from build/face.json (median over the takes)
TW, TH = 1350, 2400                               # 1.6x tight window
TX = int(min(max(EYES_X - TW / 2, 0), W4 - TW)) // 2 * 2
TY = int(min(max(EYES_Y - 0.38 * TH, 0), H4 - TH)) // 2 * 2
GRADE = "eq=contrast=1.05:saturation=0.92:gamma=1.02,colorbalance=rs=-0.02:gs=0.0:bs=0.03"

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
FIX = {"все": "всё", "еще": "ещё", "живешь": "живёшь"}
d = json.load(open(os.path.join(HERE, "build/words.whisper.json")))
words = []
for w in (w for s in d["segments"] for w in s["words"]):
    for s in mp:
        if min(w["end"], s["b"]) - max(w["start"], s["a"]) > min(0.5 * (w["end"] - w["start"]), 0.09) and w["start"] < s["b"] - 0.15:
            txt = w["word"].strip()
            key = txt.strip(",.").lower()
            if key in FIX:
                txt = txt.lower().replace(key, FIX[key])
            ws = max(w["start"], s["a"] + 0.02, w["end"] - 0.6)   # whisper stretches first words over silence
            words.append({"w": txt, "s": round(s["start"] + ws - s["a"], 3),
                          "e": round(s["start"] + min(w["end"], s["b"]) - s["a"], 3)})
            break
for s in mp:  # sentence case at each line start
    first = next((w for w in words if s["start"] <= w["s"] < s["end"]), None)
    if first:
        first["w"] = first["w"][:1].upper() + first["w"][1:]
json.dump(words, open(os.path.join(HERE, "build/words.edit.json"), "w"), ensure_ascii=False, indent=0)
print(f"cut {t:.2f}s, {len(SEGS)} segments, {len(words)} words; tight crop {TW}x{TH}+{TX}+{TY}")
print(" ".join(w["w"] for w in words))
