#!/usr/bin/env python3
"""cut.json -> build/plan.json: frame-exact pieces, pauses trimmed, every off-lens window labelled keep or cover.

    plan_cut.py [<project>] [--audio build/full.wav] [--facescan build/facescan.json] [--words build/islands.json]
                [--out build/plan.json] [--strict]
    plan_cut.py [<project>] --where T [T ...]      edit seconds of the cut -> raw seconds + piece note (reads --out)

cut.json: "pieces" [[t0, t1, note, lead, tail], {"t0", "t1", "note", "lead", "tail", "tailmax", "a", "b", "vearly"}, ...]
or "segments" [[a, b, note], ...] (approximate raw seconds of the best take of each line), in edit order; optional
"drop" [[d0, d1, note], ...] (raw intervals cut out of a piece: a stray word or stumble; the halves keep one framing) and
"trim_pauses" (s, default 0.26; 0 = off). Defaults: --audio build/voice-clean.wav or build/full.wav, --facescan
build/facescan.json or build/facescan_raw.json (optional), --words build/islands.json or build/words_raw.json (optional).
Per piece: speech onset/offset from the 10 ms energy envelope (threshold = 8th-percentile floor + 14 dB) near t0/t1,
lead 0.10 / tail 0.18, pulled in so no flagged frame (facescan.badframes against the piece's own baseline: turn, glance,
side-eye, closure, tilt, big pitch, no face) sits in the lead/tail, never into a word (lead >= 0.03, tail >= 0.06).
A given lead/tail is final (may be negative); tailmax = a longer tail, still pulled in; a/b = absolute edges; vearly =
split edit (the picture cuts N frames before the sound; the next piece's picture starts that much earlier). 30 fps grid.
A piece < 0.6 s from another one in raw time (a take split at a stumble) stays inside its own t0/t1 on that side.
Drop: the half before ends at d0 (tail <= 0.18 after its last speech), the half after starts at d1 (lead <= 0.10).
Pause trim: a silence > trim_pauses (energy under floor + 20 dB, clicks <= 50 ms bridged) inside a piece is cut to
~0.18 s (tail 0.11 + lead 0.07), stopping short of any click; never a gap inside a word (the unvoiced 'ст' in "десять":
a word with >= 0.10 s of itself on both sides); sub-pieces keep the take's framing ("same"). Blink-safe edges: no cut opens or
closes mid-blink (edge slid 1-6 frames, else a picture-only split edit <= 4 frames).
Off-lens windows (flagged picture frames, gaps <= 0.15 s joined), EDIT seconds: keep = a blink, glance or small nod
(<= 0.5 s flagged, eyes back within 0.5 s, head within 12 deg of the piece's median: it reads as a person talking);
cover = a real look-away (references/broll.md 1). --strict: every window is cover.
Out: {"pieces": [{a, b, s0, s1, va, vb, vearly, same, note, words, edit, bad_inside}], "cover": [[t0, t1, why]],
"keep": [[t0, t1, why]], "total", "floor_db", "audio"}; a/b cut the voice, va/vb the picture (raw seconds)."""
import argparse, json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from facescan import badframes, matrix
from transcribe import load_words

FPS, SR = 30, 16000
LOOKAWAY_S, ANGLE_DEG = 0.5, 12.0


def first(P, *names):
    return next((os.path.join(P, n) for n in names if os.path.exists(os.path.join(P, n))), None)


def in_word(W, p0, p1):
    """a gap inside one word (the unvoiced 'ст' in "десять"): the word has >= 0.10 s of itself on both sides of the gap.
    Whisper stretches a short word over the pause next to it (a one-letter word lasting 0.42 s over a 0.31 s pause), so a
    mere overlap is not enough: that word reaches only 0.04-0.08 s beyond the gap"""
    return any(w["a"] <= p0 - 0.10 and w["b"] >= p1 + 0.10 for w in W)


def where(plan, ts):
    ve = 0.0; V = []
    for p in plan["pieces"]:
        va, vb = p.get("va", p["a"]), p.get("vb", p["b"]); V.append((ve, ve + vb - va, va, p["note"])); ve += vb - va
    for t in ts:
        hit = next(((e0, va, note) for e0, e1, va, note in V if e0 <= t < e1), None)
        print(f"edit {t:7.2f} -> " + (f"raw {hit[1] + t - hit[0]:8.2f}  ({hit[2]})" if hit else "past the end"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--audio"); ap.add_argument("--facescan"); ap.add_argument("--words"); ap.add_argument("--out")
    ap.add_argument("--strict", action="store_true", help="every off-lens window is a cover window")
    ap.add_argument("--where", nargs="+", type=float, metavar="T", help="map edit seconds of the cut to raw seconds")
    A = ap.parse_args()
    P = os.path.abspath(A.project)
    outp = A.out or os.path.join(P, "build", "plan.json")
    if A.where:
        return where(json.load(open(outp)), A.where)
    cut = json.load(open(os.path.join(P, "cut.json")))
    audio = A.audio or first(P, "build/voice-clean.wav", "build/full.wav") or sys.exit("no audio: pass --audio")
    fsp = A.facescan or first(P, "build/facescan.json", "build/facescan_raw.json")
    wp = A.words or first(P, "build/islands.json", "build/words_raw.json")

    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                     capture_output=True, check=True).stdout, np.float32)
    hop = SR // 100
    db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop * 2) / (hop * 2), "same"))[::hop] + 1e-9)
    floor = np.percentile(db, 8)
    TH = floor + 14
    F = json.load(open(fsp)) if fsp else []
    if not F: print("no facescan: no face pull-in, blink-safe edges or off-lens windows")
    FT, V = matrix(F) if F else (np.zeros(0), np.zeros((0, 8)))
    W = load_words(wp) if wp else []
    DROP = [d[:2] for d in cut.get("drop", [])]

    def onset(lo, hi, dflt):
        """first 10 ms frame in [lo, hi) starting 30 ms above TH"""
        lo, hi = max(int(lo * 100), 0), min(int(hi * 100), len(db) - 3)
        return next((k for k in range(lo, hi) if (db[k:k + 3] > TH).all()), int(dflt * 100))

    def offset(lo, hi, dflt):
        """last 10 ms frame in (lo, hi] ending 30 ms above TH"""
        lo, hi = max(int(lo * 100), 2), min(int(hi * 100), len(db) - 1)
        return next((k for k in range(hi, lo, -1) if (db[k - 2:k + 1] > TH).all()), int(dflt * 100))

    def flagged(m, sp):
        """badframes on the frames m against the speech frames sp as baseline -> (dict, any-flag mask)"""
        if not m.any(): return {}, np.zeros(0, bool)
        K = badframes(V[m], np.nanmedian(V[sp], 0)); bad = np.zeros(m.sum(), bool)
        for v in K.values(): bad |= v
        return K, bad

    def words_in(a, b):
        return " ".join(w["w"] for w in W if w["a"] < b - 0.05 and w["b"] > a + 0.05)

    plan = []; E = 0.0
    PCS = [(p["t0"], p["t1"]) if isinstance(p, dict) else (p[0], p[1]) for p in cut.get("pieces") or cut["segments"]]
    for n_, p in enumerate(cut.get("pieces") or cut["segments"]):
        if isinstance(p, dict):   # {"t0", "t1", "note", "lead", "tail", "a", "b"}: a/b are absolute final edges
            D = p; p = [D["t0"], D["t1"], D.get("note", ""), D.get("lead"), D.get("tail")]
            if "tailmax" in D: p[4] = None
        else: D = {}
        t0, t1, note = p[0], p[1], p[2] if len(p) > 2 else ""
        lead_t = p[3] if len(p) > 3 and p[3] is not None else 0.10   # explicit lead/tail (s, may be negative) are final
        tail_t = p[4] if len(p) > 4 and p[4] is not None else D.get("tailmax", 0.18)   # tailmax: longer tail, still pulled in
        # another piece right next to this one in raw time (a take split at a stumble): the given edge on that side is a
        # deliberate cut point, so the search and the edge stay inside it (else both pieces play the gap between them)
        lo = "a" not in D and any(j != n_ and t0 - 0.6 < e <= t0 + 0.05 for j, (_, e) in enumerate(PCS))
        hi = "b" not in D and any(j != n_ and t1 - 0.05 <= s < t1 + 0.6 for j, (s, _) in enumerate(PCS))
        s0 = onset(t0 if lo else t0 - 0.25, t0 + 0.35, t0) / 100
        s1 = offset(t1 - 0.35, t1 if hi else t1 + 0.35, t1) / 100
        a, b = s0 - lead_t, s1 + tail_t
        if lo: a = max(a, t0)
        if hi: b = min(b, t1)
        # face problems in the window, against this piece's own baseline
        m = (FT >= a - 0.05) & (FT <= b + 0.05); sp = (FT >= s0) & (FT <= s1)
        K, bad = flagged(m, sp)
        tt = FT[m]
        pre = tt[(tt < s0) & bad]; post = tt[(tt > s1) & bad]
        fixed_a = len(p) > 3 and p[3] is not None; fixed_b = len(p) > 4 and p[4] is not None
        if len(pre) and not fixed_a: a = max(a, min(pre[-1] + 1 / FPS, s0 - 0.03))
        if len(post) and not fixed_b: b = min(b, max(post[0] - 1 / FPS, s1 + 0.06))
        if "a" in D: a = D["a"]
        if "b" in D: b = D["b"]
        a = np.ceil(a * FPS - 1e-6) / FPS; b = np.floor(b * FPS + 1e-6) / FPS
        inside = [(round(float(tt[k]), 2), n) for n, v in K.items() for k in np.where(v & (tt >= a) & (tt <= b))[0]]
        q = {"a": round(a, 6), "b": round(b, 6), "s0": s0, "s1": s1, "note": note, "words": words_in(a, b), "vearly": int(D.get("vearly", 0)),
             "edit": round(E, 3), "bad_inside": inside[:40], "same": False}
        # drop: cut a stray word / stumble out by raw interval; the halves get the normal tail/lead clamped to the drop
        for d0, d1 in sorted(d for d in DROP if d[1] > q["s0"] and d[0] < q["s1"]):
            head, rest, h = d0 > q["s0"] + 0.03, d1 < q["s1"] - 0.03, None
            if head:
                e1 = offset(q["s0"], d0, d0) / 100
                h = dict(q, s1=e1, b=round(min(round(d0 * FPS), np.floor((e1 + tail_t) * FPS + 1e-6)) / FPS, 6), vearly=q["vearly"] if not rest else 0)
                h["words"] = words_in(h["a"], h["b"])
            print(f"  drop in {note}: {d0:.2f}-{d1:.2f}")
            if not rest: q = h; break
            if h: plan.append(h)
            e0 = onset(d1, q["s1"], d1) / 100
            a2 = round(max(round(d1 * FPS), np.ceil((e0 - lead_t) * FPS - 1e-6)) / FPS, 6)
            q = dict(q, s0=e0, a=a2, note=q["note"] + ("~" if head else ""), same=head or q["same"])
            q["words"] = words_in(q["a"], q["b"])
        if q: plan.append(q)
        E += b - a

    # pause trim: inside each piece, a silence longer than MAXP (energy under THP) is cut down to KEEP (tail 0.11 + lead 0.07);
    # the sub-pieces keep the take's framing ("same": True) so only real take changes switch wide/tight
    MAXP = cut.get("trim_pauses", 0.26); THP = floor + 20      # a pause = energy under floor+20 dB (breath/room tone)

    out = []; guarded = []
    for q in plan:
        if not MAXP: out.append(q); continue
        k0, k1 = int(round(q["s0"] * 100)), int(round(q["s1"] * 100))
        low = db[k0:k1] <= THP; cuts = []
        # bridge clicks/lip smacks (<= 50 ms above the line) inside a silence so they don't hide the pause
        k = 0
        while k < len(low):
            if not low[k]:
                j = k
                while j + 1 < len(low) and not low[j + 1]: j += 1
                if k > 0 and j + 1 < len(low) and j - k + 1 <= 5: low[k:j + 1] = True
                k = j + 1
            else: k += 1
        k = 0
        while k < len(low):
            if low[k]:
                j = k
                while j + 1 < len(low) and low[j + 1]: j += 1
                if (j - k + 1) / 100 > MAXP:
                    c = ((k0 + k) / 100, (k0 + j + 1) / 100)
                    if in_word(W, *c): guarded.append(f"{c[1] - c[0]:.2f}s@{c[0]:.2f} ({q['note']})")
                    else: cuts.append(c)
                k = j + 1
            else: k += 1
        # a click/breath island at the very start or end of a piece is not speech: drop it instead of keeping it as a piece
        while cuts and cuts[0][0] - q["s0"] < 0.25: q = dict(q, s0=round(cuts[0][1], 2), a=round(float(np.ceil((cuts[0][1] - 0.08) * FPS) / FPS), 6)); cuts = cuts[1:]
        while cuts and q["s1"] - cuts[-1][1] < 0.25: q = dict(q, s1=round(cuts[-1][0], 2), b=round(float(np.floor((cuts[-1][0] + 0.15) * FPS) / FPS), 6)); cuts = cuts[:-1]
        if not cuts: out.append(q); continue

        def pause_edges(p0, p1):
            """tail of the speech before the pause / lead into the speech after it, both stopping short of any click or
            lip smack (a 10 ms frame above the pause line) inside the pause"""
            seg = db[int(round(p0 * 100)):int(round(p1 * 100))]; blips = np.where(seg > THP)[0]
            blips = blips[(blips >= 5) & (blips <= len(seg) - 6)]   # within 50 ms of an edge it is the word's decay/onset, not a click
            t_end = p0 + 0.11; t_start = p1 - 0.07
            if len(blips):   # keep up to 0.12 s of clean lead after the last click so a sentence break still breathes
                t_end = min(t_end, p0 + max(blips[0] / 100 - 0.01, 0.04)); t_start = max(p1 - 0.12, p0 + blips[-1] / 100 + 0.02)
            return np.floor(t_end * FPS) / FPS, np.ceil(t_start * FPS) / FPS
        edges = [q["a"]] + [e for p0, p1 in cuts for e in pause_edges(p0, p1)] + [q["b"]]
        for i in range(0, len(edges), 2):
            r = dict(q); r["a"], r["b"] = round(float(edges[i]), 6), round(float(edges[i + 1]), 6)
            r["note"] = q["note"] + ("" if i == 0 else "~"); r["same"] = i > 0 or q["same"]
            r["vearly"] = q.get("vearly", 0) if i == len(edges) - 2 else 0   # a split edit belongs to the take's last sub-piece
            r["s0"] = q["s0"] if i == 0 else round(float(cuts[i // 2 - 1][1]), 2); r["s1"] = q["s1"] if i == len(edges) - 2 else round(float(cuts[i // 2][0]), 2)
            out.append(r)
        print(f"  pause trim in {q['note']}: " + ", ".join(f"{p1 - p0:.2f}s@{p0:.2f}" for p0, p1 in cuts))
    if guarded: print("  kept (gap inside a word): " + ", ".join(guarded))
    plan = out

    def place():
        E = 0.0
        for k, q in enumerate(plan):
            q["edit"] = round(E, 3); E += q["b"] - q["a"]
            prev = plan[k - 1]["vearly"] if k else 0
            q["va"] = round(q["a"] - prev / FPS, 6); q["vb"] = round(q["b"] - q["vearly"] / FPS, 6)
        return E
    place()
    # split edits: piece k's picture ends `vearly` frames before its sound; piece k+1's picture starts that much earlier
    for q in plan:
        m = (FT >= q["va"] - 1e-3) & (FT < q["vb"] - 1e-3); sp = (FT >= q["s0"]) & (FT <= q["s1"])
        K, _ = flagged(m, sp); tt = FT[m]
        q["bad_inside"] = [(round(float(tt[i]), 2), n) for n, v in K.items() for i in np.where(v)[0]][:40]
    # blink-safe edges: a cut must not open or close on a frame mid-blink. Slide the start later (lead >= 0.03 s) or earlier
    # (more lead, clean frames only), the end earlier (tail >= 0.04 s), else move only the picture (split edit, <= 4 frames).
    BL = V[:, 7] if len(FT) else np.zeros(0)
    def fidx(t): return int(np.searchsorted(FT, t - 1e-3))
    def is_open(i, j): return all(0 <= k < len(BL) and not np.isnan(BL[k]) and BL[k] < 0.25 for k in range(i, j))
    def clean_lead(i0, i1):
        m = np.zeros(len(FT), bool); m[max(i0, 0):max(i1, 0)] = True
        if not m.any(): return True
        K = badframes(V[m], np.nanmedian(V[m], 0)); return not any(v.any() for v in K.values())
    fixes = []
    for k, q in enumerate(plan if len(FT) else []):
        prev_split = plan[k - 1]["vearly"] if k else 0
        i0 = fidx(q["va"])
        if not is_open(i0, i0 + 2) and prev_split == 0:
            for d in list(range(1, 7)) + [-x for x in range(1, 5)]:
                na = q["a"] + d / FPS
                if d > 0 and na > q["s0"] - 0.03: continue
                if is_open(i0 + d, i0 + d + 2) and (d > 0 or clean_lead(i0 + d, i0)):
                    q["a"] = round(na, 6); q["va"] = q["a"]; fixes.append(f"{q['note']} start {d:+d}f"); break
        i1 = fidx(q["vb"]) - 1
        if not is_open(i1 - 1, i1 + 1):
            done = False
            for d in range(1, 7):
                nb = q["b"] - d / FPS
                if nb < q["s1"] + 0.04: break
                if is_open(i1 - 1 - d, i1 + 1 - d):
                    q["b"] = round(nb, 6); q["vb"] = round(q["b"] - q["vearly"] / FPS, 6); fixes.append(f"{q['note']} end -{d}f"); done = True; break
            if not done and k + 1 < len(plan):
                for d in range(1, 5):
                    if is_open(i1 - 1 - d, i1 + 1 - d) and clean_lead(fidx(plan[k + 1]["a"]) - (q["vearly"] + d), fidx(plan[k + 1]["a"])):
                        q["vearly"] += d; q["vb"] = round(q["b"] - q["vearly"] / FPS, 6); plan[k + 1]["va"] = round(plan[k + 1]["a"] - q["vearly"] / FPS, 6)
                        fixes.append(f"{q['note']} picture-only end -{d}f"); break
    E = place()
    if fixes: print("  blink-safe edges:", ", ".join(fixes))

    # off-lens windows on the picture of each piece, in edit seconds: keep (blink / glance / small nod) or cover (look-away)
    cover, keep = [], []
    for k, q in enumerate(plan):
        m = (FT >= q["va"] - 1e-3) & (FT < q["vb"] - 1e-3); sp = (FT >= q["s0"]) & (FT <= q["s1"])
        K, bad = flagged(m, sp)
        if not bad.any(): continue
        tt = FT[m]; v = V[m]; med = np.nanmedian(V[sp], 0)
        off = K["glance"] | K["side"] | K["closed"] | K["noface"]                 # eyes off the lens, shut, or no face
        ang = np.maximum(np.abs(v[:, 0] - med[0]), np.abs(v[:, 1] - med[1]))
        ve = q["edit"] - (plan[k - 1]["vearly"] / FPS if k else 0)                 # edit time of the piece's first picture frame
        idx = np.where(bad)[0]; groups = [[idx[0], idx[0]]]
        for i in idx[1:]:
            if tt[i] - tt[groups[-1][1]] <= 0.15: groups[-1][1] = i
            else: groups.append([i, i])
        for i0, i1 in groups:
            span = float(tt[i1] - tt[i0] + 1 / FPS)
            r = mx = 0
            for g in off[i0:i1 + 1]:
                r = r + 1 if g else 0; mx = max(mx, r)
            a_ = float(np.nanmax(ang[i0:i1 + 1])) if np.isfinite(ang[i0:i1 + 1]).any() else 99.0
            why = [w for w, c in ((f"flagged {span:.2f} s", span > LOOKAWAY_S), (f"eyes off {mx / FPS:.2f} s", mx / FPS > LOOKAWAY_S),
                                  (f"head {a_:.0f} deg", a_ > ANGLE_DEG)) if c]
            kinds = sorted({n for n, x in K.items() if x[i0:i1 + 1].any()})
            win = [round(max(ve + tt[i0] - q["va"] - 0.05, 0.0), 3), round(min(ve + tt[i1] - q["va"] + 0.08, E), 3),
                   f"{q['note']} | {'/'.join(kinds)} | {', '.join(why) or 'blink / glance / small nod'}"]
            (cover if why or A.strict else keep).append(win)

    os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
    json.dump({"pieces": plan, "cover": cover, "keep": keep, "total": round(E, 3), "floor_db": round(float(floor), 1), "audio": os.path.abspath(audio)},
              open(outp, "w"), ensure_ascii=False, indent=1)
    print(f"{len(plan)} pieces, {E:.2f} s (noise floor {floor:.1f} dB, speech threshold {TH:.1f}) -> {outp}")
    for p in plan:
        flag = f"  !! {len(p['bad_inside'])} flagged frames inside: {sorted(set(n for _, n in p['bad_inside']))} first@{p['bad_inside'][0][0]}" if p["bad_inside"] else ""
        print(f"  {p['edit']:6.2f} | {p['a']:8.3f}-{p['b']:8.3f} ({p['b'] - p['a']:5.2f}) lead {p['s0'] - p['a']:.2f} tail {p['b'] - p['s1']:.2f} | {p['note']:8s} | {p['words'][:90]}{flag}")
    print(f"{len(cover) + len(keep)} off-lens windows: {len(keep)} kept on screen (blinks, glances, small nods), {len(cover)} need cover (edit s):")
    for w in cover: print(f"  {w[0]:6.2f}-{w[1]:6.2f} ({(w[1] - w[0]) * 1000:4.0f} ms)  {w[2]}")


if __name__ == "__main__":
    main()
