#!/usr/bin/env python3
"""Stitch edl.json into one 1080x1920 30 fps source (assets/talk.mp4) for the ghost-editor build.

Glasses clips (3:4) are centre-cropped to 9:16; the iPhone clip is already 9:16.
Speed-ups are baked in. Audio: voice segments are cleaned (high-pass + light
denoise) at full level, ambience sits 14 dB down, speed-ups are silent. The
whole program is then normalised to -16 LUFS on the voice segments' level.
Writes build/edl_map.json: each segment's edit start/end and source range.
"""
import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = {n: os.path.expanduser(f"~/Downloads/video-{n}_singular_display.MOV") for n in ["5851", "5857", "5863", "5869", "5875", "5885", "5887"]}
SRC["5026"] = os.path.expanduser("~/Downloads/IMG_5026.MOV")
edl = json.load(open(os.path.join(HERE, "edl.json")))["segments"]
os.makedirs(os.path.join(HERE, "build", "segs"), exist_ok=True)
os.makedirs(os.path.join(HERE, "assets"), exist_ok=True)

parts, t, mp = [], 0.0, []
for i, s in enumerate(edl):
    out = os.path.join(HERE, "build", "segs", f"{i:02d}.mov")
    if "freeze" in s:  # a held still frame, silent (the reel adds the scratch/meme on top)
        dur = s["dur"]
        vf0 = ("crop=ih*9/16:ih," if s["clip"] != "5026" else "") + "scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["freeze"]), "-i", SRC[s["clip"]], "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                        "-filter_complex", f"[0:v]trim=end_frame=1,{vf0},loop=loop=-1:size=1,trim=duration={dur},setpts=N/30/TB[v]",
                        "-map", "[v]", "-map", "1:a", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-c:a", "pcm_s16le", out], check=True)
        real = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
        mp.append({"i": i, "clip": s["clip"], "src_a": s["freeze"], "src_b": s["freeze"], "speed": 0, "edit_start": round(t, 3), "edit_end": round(t + real, 3), "note": s["note"]})
        print(f"{i:02d} {s['clip']} FREEZE {s['freeze']:.2f} {dur}s -> {mp[-1]['edit_start']:6.2f}-{mp[-1]['edit_end']:6.2f}  {s['note']}")
        t += real; parts.append(out); continue
    dur = (s["b"] - s["a"]) / s["speed"]
    vf = ("crop=ih*9/16:ih," if s["clip"] != "5026" else "") + f"scale=1080:1920:flags=lanczos,setpts=(PTS-STARTPTS)/{s['speed']},fps=30,setsar=1,format=yuv420p"
    if s["audio"] == "voice":
        af = "highpass=f=110,afftdn=nr=8:nf=-35,volume=1.0"
    elif s["audio"] == "amb":
        af = "highpass=f=110,volume=-14dB"
    else:
        af = "volume=0"
    af += f",atempo={s['speed']}" if s["speed"] != 1 and s["speed"] <= 2 else (f",atempo=2,atempo={s['speed'] / 2}" if s["speed"] > 2 else "")
    af += ",aresample=48000,aformat=channel_layouts=stereo"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["a"]), "-t", str(s["b"] - s["a"]), "-i", SRC[s["clip"]],
                    "-vf", vf, "-af", af, "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-c:a", "pcm_s16le", out], check=True)
    real = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
    mp.append({"i": i, "clip": s["clip"], "src_a": s["a"], "src_b": s["b"], "speed": s["speed"], "edit_start": round(t, 3), "edit_end": round(t + real, 3), "note": s["note"]})
    t += real
    parts.append(out)
    print(f"{i:02d} {s['clip']} {s['a']:7.2f}-{s['b']:7.2f} x{s['speed']} -> {mp[-1]['edit_start']:6.2f}-{mp[-1]['edit_end']:6.2f}  {s['note']}")

lst = os.path.join(HERE, "build", "segs", "list.txt")
open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
raw = os.path.join(HERE, "build", "assembled.mov")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", raw], check=True)
# normalise: two-pass loudnorm to -16 LUFS, true peak -1.5
m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
ln = f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-c:v", "copy", "-af", ln + ",aresample=48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                os.path.join(HERE, "assets", "talk.mp4")], check=True)
json.dump(mp, open(os.path.join(HERE, "build", "edl_map.json"), "w"), indent=1)
print(f"total {t:.2f}s -> assets/talk.mp4")
