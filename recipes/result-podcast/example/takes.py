#!/usr/bin/env python3
"""RESULT worked example ("keep the paper", script.txt): the best take per script line (source seconds), then the
pauses inside each take removed using the audio (silencedetect), keeping small pads. -> build/takes.json

Also writes build/rough.mp4, the rough cut (the kept parts back to back, no graphics): transcribe it for the caption
and beat timing and audit it verbatim before building:
    python3 takes.py
    python3 $S/scripts/transcribe.py build/rough.mp4 --out build/rough.words.json --lang en
"""
import array, json, math, os, re, subprocess

X264_THREADS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts", "X264_THREADS")).read().strip()  # every libx264 encode (scripts/x264.py)

SRC = "build/proxy.mp4"
LINES = [  # (a, b, text) - the last clean take of each line, source seconds (a stand-in recording: re-time from yours)
    (0.45, 4.05, "On every trip, I keep one paper thing from each day."),
    (4.6, 6.65, "A ticket from the first train."),
    (9.67, 12.84, "A receipt from a café I could never find again."),          # 7.35-9.0: a false start
    (13.39, 16.77, "A leaf from a park, pressed between two pages."),
    (17.32, 20.79, "My phone has three thousand photos from the same trips."),
    (21.33, 22.98, "I never open them."),
    (25.72, 28.28, "Storage almost full. Again."),                              # 23.7-25.0: a false start
    (28.83, 31.6, "But the box? I open it every winter."),
    (32.15, 34.75, "Because a photo shows you where you were."),
    (35.3, 37.65, "A ticket reminds you who you were there."),
    (38.2, 41.14, "So on your next trip, keep the paper."),
    (41.69, 44.42, "Your phone will forget. The box won't."),
]
NOISE, MIN_SIL, PAD = -34, 0.7, 0.12
takes = []
for a, b, text in LINES:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", SRC, "-vn",
                          "-af", f"silencedetect=noise={NOISE}dB:d={MIN_SIL}", "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    sil = list(zip(st, en + [b - a] * (len(st) - len(en))))
    # speech = complement of silences
    keep, t = [], 0.0
    for s0, s1 in sil:
        if s0 > t: keep.append((t, s0))
        t = max(t, s1)
    if t < b - a: keep.append((t, b - a))
    parts = [(round(a + max(0, k0 - PAD), 3), round(a + min(b - a, k1 + PAD), 3)) for k0, k1 in keep if k1 - k0 > 0.12]
    # merge parts closer than 2*PAD
    merged = []
    for p in parts:
        if merged and p[0] - merged[-1][1] < 0.06: merged[-1] = (merged[-1][0], p[1])
        else: merged.append(p)
    # breaths before a line: start the line at the voice onset (RMS > -30 dB for 30 ms), not at the padded edge
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(merged[0][0]), "-t", "2.2", "-i", SRC, "-vn", "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    smp = array.array("h", raw); win = 80; run = 0; onset = None
    for i in range(0, len(smp) - win, win):
        rms = math.sqrt(sum(x * x for x in smp[i:i + win]) / win) or 1
        run = run + 1 if 20 * math.log10(rms / 32768) > -30 else 0
        if run >= 3: onset = (i - 2 * win) / 8000; break
    if onset is not None and 0.08 < onset < min(1.8, merged[0][1] - merged[0][0] - 0.25):
        merged[0] = (round(merged[0][0] + onset - 0.07, 3), merged[0][1])
    # quiet word endings sit under the threshold: give the last part of a line a longer tail
    merged[-1] = (merged[-1][0], round(min(b, merged[-1][1] + 0.12), 3))
    takes.append({"text": text, "parts": merged, "dur": round(sum(q - p for p, q in merged), 2)})
    print(f"{a:6.1f}-{b:6.1f}  {len(merged)} parts {takes[-1]['dur']:5.2f}s  {text[:60]}")
json.dump(takes, open("build/takes.json", "w"), ensure_ascii=False, indent=1)
print("total speech", round(sum(t['dur'] for t in takes), 1), "s,", sum(len(t['parts']) for t in takes), "cuts")

# the rough cut: every kept part back to back, the same timeline build.py lays the clips on
parts = [p for t in takes for p in t["parts"]]
fc = "".join(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}];[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}];"
             for i, (a, b) in enumerate(parts))
fc += "".join(f"[v{i}][a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-r", "30",
                "-c:v", "libx264", "-threads", X264_THREADS, "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k", "build/rough.mp4"], check=True)
print("rough cut -> build/rough.mp4 (transcribe it: build/rough.words.json)")
