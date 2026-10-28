#!/usr/bin/env python3
"""Rebuild the cut at frame level: drop every pause inside a take, mark every frame where the face is not on the lens.
In: cut.json segments (raw seconds), build/facescan_raw.json, build/voice-clean.wav
Out: build/plan.json {"pieces": [[a, b], ...] raw seconds in edit order, "cover": [[t0, t1, why], ...] EDIT seconds,
"keep": [[t0, t1, why], ...] EDIT seconds}
A piece boundary inside a take is a pause cut (lead 0.06 / tail 0.10). Off-lens frames inside speech can't be cut away
without losing words. A blink, a glance or a small nod (<= 0.5 s, head within 12 deg, eyes back within 0.5 s) is KEPT on
screen; only a real look-away becomes a cover window (references/broll.md 1: trim, tight-crop punch, hold the graphic,
framed insert, full-screen stock last). --strict: every off-lens window is a cover window (the pre-Oct-13 rule)."""
import json, subprocess, sys, numpy as np
LOOKAWAY_S, ANGLE_DEG, STRICT = 0.5, 12.0, "--strict" in sys.argv
c = json.load(open("cut.json", encoding="utf-8")); F = [x for x in json.load(open("build/facescan_raw.json", encoding="utf-8"))]
T = np.array([x[0] for x in F]); ok = np.array([x[1] is not None for x in F])
V = np.array([[np.nan] * 8 if x[1] is None else x[1:] for x in F], float)
inside = np.zeros(len(T), bool)
for a, b, _ in c["segments"]: inside |= (T >= a) & (T <= b)
med = np.nanmedian(V[inside & ok], 0)          # the speaker's own on-camera baseline, from the chosen takes
bad = (~ok) | (np.abs(V[:, 0] - med[0]) > 3) | (np.abs(V[:, 1] - med[1]) > 5.5) | (np.abs(V[:, 2] - med[2]) > 3) \
      | (V[:, 3] > 0.22) | (V[:, 5] > 0.42) | (V[:, 6] > 0.42) | (V[:, 7] > 0.42)
# a normal blink (<= 5 frames) is fine; a closure longer than that is not
cl = V[:, 7] > 0.42
run = np.zeros(len(cl), int)
for i in range(len(cl)): run[i] = run[i - 1] + 1 if cl[i] and i else (1 if cl[i] else 0)
for i in range(len(cl) - 1, 0, -1):
    if cl[i] and cl[i - 1]: run[i - 1] = max(run[i - 1], run[i])
bad &= ~(cl & (run <= 5) & ~((np.abs(V[:, 0] - med[0]) > 3) | (V[:, 3] > 0.22) | (V[:, 5] > 0.42) | (V[:, 6] > 0.42)))
# speech energy (10 ms) on the denoised voice
sr = 16000
x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", "build/voice-clean.wav", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                                 capture_output=True).stdout, np.float32)
hop = sr // 100
db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop * 3) / (hop * 3), "same"))[::hop] + 1e-9)
TH, MINP = -37.0, 0.24
WR = json.load(open("build/words_raw.json", encoding="utf-8")) if __import__("os").path.exists("build/words_raw.json") else []
def in_word(g0, g1):  # a "pause" that sits inside a spoken word (e.g. the unvoiced 'ст' in "десять") is not a pause
    return any(w["a"] + 0.03 < g1 and w["b"] - 0.03 > g0 for w in WR)
DROP = c.get("drop", [])
pieces, cover, keep, E = [], [], [], 0.0
OFF = (V[:, 3] > 0.22) | (V[:, 5] > 0.42) | (V[:, 6] > 0.42) | (V[:, 7] > 0.42) | ~ok   # eyes off the lens, closed, or no face
ANG = np.maximum(np.abs(V[:, 0] - med[0]), np.abs(V[:, 1] - med[1]))
FPS_SCAN = 1 / np.median(np.diff(T)) if len(T) > 1 else 30.0


def verdict(g0, g1):
    """keep (blink / glance / small nod) or cover (a real look-away) for the flagged frames between raw g0 and g1"""
    m = (T >= g0) & (T <= g1)
    r = mx = 0
    for g in OFF[m]:
        r = r + 1 if g else 0
        mx = max(mx, r)
    ang = float(np.nanmax(ANG[m])) if np.isfinite(ANG[m]).any() else 99.0
    why = [w for w, c in ((f"flagged {g1 - g0 + 1 / FPS_SCAN:.2f} s", g1 - g0 + 1 / FPS_SCAN > LOOKAWAY_S), (f"eyes off {mx / FPS_SCAN:.2f} s", mx / FPS_SCAN > LOOKAWAY_S),
                                  (f"head {ang:.0f} deg", ang > ANGLE_DEG)) if c]
    return ("cover" if why or STRICT else "keep"), ", ".join(why) or "blink / glance / small nod"
for a, b, note in c["segments"]:
    e = db[int(a * 100):int(b * 100)]; on = e > TH
    # speech islands, bridging gaps shorter than MINP
    isl, k = [], 0
    while k < len(on):
        if on[k]:
            j = k
            while j + 1 < len(on) and on[j + 1]: j += 1
            if isl and ((k - isl[-1][1]) / 100 < MINP or in_word(a + isl[-1][1] / 100, a + k / 100)): isl[-1][1] = j
            else: isl.append([k, j])
            k = j + 1
        else: k += 1
    isl = [s for s in isl if (s[1] - s[0]) >= 4]          # drop clicks < 40 ms
    for d0, d1, _ in DROP:                                  # cut out a stray word / stumble by raw interval
        out = []
        for s0, s1 in isl:
            r0, r1 = a + s0 / 100, a + s1 / 100
            if r0 < d0 < r1 or r0 < d1 < r1:
                if d0 - r0 > 0.04: out.append([s0, int((d0 - a) * 100) - 1])
                if r1 - d1 > 0.04: out.append([int((d1 - a) * 100) + 1, s1])
            else: out.append([s0, s1])
        isl = out
    first, last = 0, len(isl) - 1
    for n, (s0, s1) in enumerate(isl):
        lead = 0.08 if n == first else 0.04 if any(abs(a + s0 / 100 - d1) < 0.03 for _, d1, _ in DROP) else 0.06
        tail = 0.16 if n == last else 0.03 if any(abs(a + s1 / 100 - d0) < 0.03 for d0, _, _ in DROP) else 0.10
        pa = round(max(a, a + s0 / 100 - lead), 3); pb = round(min(b, a + s1 / 100 + tail), 3)
        pieces.append([pa, pb, note[:24]])
        fr = (T >= pa) & (T <= pb); bt = T[fr & bad]
        if len(bt):
            # group bad frames into windows (gap <= 0.15 s), convert to edit time
            g0 = g1 = bt[0]
            for t in list(bt[1:]) + [None]:
                if t is not None and t - g1 <= 0.15: g1 = t; continue
                v, why = verdict(g0, g1)
                (cover if v == "cover" else keep).append([round(E + g0 - pa - 0.05, 3), round(E + g1 - pa + 0.08, 3), f"{note[:24]} | {why}"])
                if t is not None: g0 = g1 = t
        E += pb - pa
crit = {"yaw": np.abs(V[:, 0] - med[0]) > 3, "pitch": np.abs(V[:, 1] - med[1]) > 5.5, "roll": np.abs(V[:, 2] - med[2]) > 3,
        "eyesDown": V[:, 3] > 0.22, "eyesOut": V[:, 5] > 0.42, "eyesIn": V[:, 6] > 0.42, "closed": V[:, 7] > 0.42}
print("flagged frames inside takes by test:", {k: int((v & inside).sum()) for k, v in crit.items()}, "| bad total", int((bad & inside).sum()), "of", int(inside.sum()))
json.dump({"pieces": pieces, "cover": cover, "keep": keep, "total": round(E, 3)}, open("build/plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
old = sum(s[1] - s[0] for s in c["segments"])
print(f"{len(c['segments'])} takes -> {len(pieces)} pieces; {old:.2f}s -> {E:.2f}s ({old - E:.2f}s of pauses removed)")
print(f"{len(cover) + len(keep)} off-lens windows: {len(keep)} kept on screen (blinks, glances), {len(cover)} need cover (edit s):")
for w in cover: print(f"  {w[0]:6.2f}-{w[1]:6.2f} ({(w[1]-w[0])*1000:4.0f} ms)  {w[2]}")
