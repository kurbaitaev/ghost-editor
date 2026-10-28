#!/usr/bin/env python3
"""Rebuild assets/voice.wav as smooth as possible WITHOUT moving anything in time.
- every join: equal-power crossfade (default 35 ms) centred on the original edit point, using real audio handles from
  the denoised source (pieces extended by h on both sides; total length stays sum(b - a) exactly)
- per-piece speech level matched to the median (clamped +-3 dB), applied as a constant gain per piece
- one constant room-tone floor (a quiet stretch of the same recording, looped with crossfades) under the whole voice
- gentle de-ess + 2:1 compression + warmth EQ, then two-pass loudnorm to -16 LUFS, TP -1.5
usage: voice_smooth.py <project> [xfade_ms=35]"""
import json, os, subprocess, sys, numpy as np
P = sys.argv[1]; XF = (float(sys.argv[2]) if len(sys.argv) > 2 else 35) / 1000
c = json.load(open(os.path.join(P, "cut.json"), encoding="utf-8")); SEG = [(a, b) for a, b, _ in c["segments"]]
SR = 48000
src = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(P, c["denoised"]), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                   capture_output=True, check=True).stdout, np.float32).astype(np.float64)
h = XF / 2
def take(a, b):
    i0, i1 = int(round(a * SR)), int(round(b * SR))
    out = np.zeros(i1 - i0); s0, s1 = max(0, i0), min(len(src), i1)
    out[s0 - i0:s1 - i0] = src[s0:s1]; return out
def speech_db(x):
    f = x[:len(x) // 480 * 480].reshape(-1, 480); e = 20 * np.log10(np.sqrt((f ** 2).mean(1)) + 1e-12)
    return np.percentile(e[e > -40], 70) if (e > -40).sum() > 5 else None
lv = [speech_db(take(a, b)) for a, b in SEG]
med = np.median([x for x in lv if x is not None])
gain = [1.0 if x is None else 10 ** (np.clip(med - x, -3, 3) / 20) for x in lv]
# a join between two raw-contiguous pieces (b_i == a_{i+1}) needs no crossfade at all
L = [b - a for a, b in SEG]; N = int(round(sum(L) * SR)); out = np.zeros(N + int(SR * 0.2))
pos = 0.0
n = int(round(h * SR)); ramp = np.sin(np.linspace(0, np.pi / 2, 2 * n)) if n else np.ones(0)
for k, (a, b) in enumerate(SEG):
    piece = take(a - h, b + h) * gain[k]
    # equal-power fade-in/out over the handles (2h) so neighbours sum smoothly around the edit point
    if 2 * n:
        piece[:2 * n] *= ramp; piece[-2 * n:] *= ramp[::-1]
    i = int(round((pos - h) * SR)); j0 = max(0, -i)
    out[i + j0:i + len(piece)] += piece[j0:len(piece) - max(0, i + len(piece) - len(out))]
    pos += b - a
out = out[:N]
# room-tone floor: the quietest 1.5 s inside the chosen takes, looped with 200 ms crossfades
best, bt = None, 1e9
step = int(0.1 * SR); W15 = int(1.5 * SR)
fr = src[:len(src) // step * step].reshape(-1, step); fr_r = np.sqrt((fr ** 2).mean(1)); fr_p = np.abs(fr).max(1)
lo, hi = int(SEG[0][0] * 10), int(SEG[-1][1] * 10)      # the recording session that the takes come from
for s0 in range(lo, hi - 15):
    r = np.sqrt(np.mean(fr_r[s0:s0 + 15] ** 2))
    if 1e-5 < r < bt and fr_p[s0:s0 + 15].max() < 0.06 and fr_r[s0:s0 + 15].max() < 3 * np.median(fr_r[s0:s0 + 15]):
        bt, best = r, src[s0 * step:s0 * step + W15].copy()
if best is not None:
    cf = int(0.2 * SR); loop = best.copy(); fade = np.linspace(0, 1, cf)
    tone = np.zeros(N); p = 0
    while p < N:
        seg = loop.copy(); seg[:cf] *= fade; seg[-cf:] *= fade[::-1]
        e = min(N, p + len(seg)); tone[p:e] += seg[:e - p]; p += len(seg) - cf
    out += tone * 0.7
raw = os.path.join(P, "build", "voice_smooth_raw.wav")
open(raw + ".f64", "wb").write(out.astype(np.float32).tobytes())
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", raw + ".f64", raw], check=True); os.remove(raw + ".f64")
chain = ("highpass=f=70,deesser=i=0.35:m=0.5:f=0.5:s=o,acompressor=threshold=-22dB:ratio=2:attack=12:release=160:knee=6:makeup=1,agate=threshold=0.006:ratio=1.8:range=0.4:attack=8:release=300:knee=4,"
         "equalizer=f=180:t=q:w=1.2:g=2,equalizer=f=3200:t=q:w=1.5:g=0.8")
m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", raw, "-af", chain + ",loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
outp = os.path.join(P, "assets", "voice.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", chain + f",loudnorm=I=-16:TP=-1.5:LRA=9:measured_I={j['input_i']}:measured_TP={j['input_tp']}"
                f":measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000",
                "-ar", "48000", "-ac", "1", outp], check=True)
print(f"{len(SEG)} pieces, xfade {XF * 1000:.0f} ms, level spread {np.nanmax([x for x in lv if x]) - np.nanmin([x for x in lv if x]):.1f} dB -> matched;"
      f" room tone {20 * np.log10(bt + 1e-12):.1f} dBFS; {N / SR:.3f} s -> {outp}")
