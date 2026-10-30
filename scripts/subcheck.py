#!/usr/bin/env python3
"""Hidden-restart check of a planned cut: split each plan piece at internal silences >= 0.15 s (10 ms energy, the
planner's floor + 14 dB) and transcribe every part on its own; a restart shows as a repeated start
("the one who doesn't fe" | "the one who doesn't feel"), whole-file whisper merges it into one clean sentence.

    subcheck.py <project | plan.json> [--audio build/full.wav] [--words build/islands.json] [--lang ru] [piece ...]

Flags: REPEAT (two parts of a piece open with the same two words), REPEATS PREVIOUS PIECE (a restart split across
pieces), long words (whisper words > 0.7 s inside the piece: a stretched or swallowed word). Defaults: the plan's
"audio", else build/voice-clean.wav or build/full.wav; words build/islands.json or build/words_raw.json (optional).
mlx_whisper (re-runs itself in $MLXW_PY or ~/.venvs/mlxw/bin/python), else openai-whisper."""
import argparse, json, os, re, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcribe

SR = 16000


def norm(t): return re.sub(r"[^а-яёa-z0-9 ]", "", t.lower().replace("ё", "е")).split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", help="project dir (build/plan.json) or a plan.json"); ap.add_argument("pieces", nargs="*", type=int)
    ap.add_argument("--audio"); ap.add_argument("--words"); ap.add_argument("--lang", default="ru")
    ap.add_argument("--mlx-model", default=transcribe.MLX_MODEL)
    A = ap.parse_args()
    transcribe.ensure_mlx(__file__)
    pp = os.path.join(A.plan, "build", "plan.json") if os.path.isdir(A.plan) else A.plan
    proj = os.path.dirname(os.path.dirname(os.path.abspath(pp)))
    first = lambda *n: next((os.path.join(proj, x) for x in n if os.path.exists(os.path.join(proj, x))), None)
    plan = json.load(open(pp)); P = plan["pieces"]
    audio = A.audio or plan.get("audio") or first("build/voice-clean.wav", "build/full.wav") or sys.exit("no audio: --audio")
    wp = A.words or first("build/islands.json", "build/words_raw.json")
    backend, asr = transcribe.asr(A.lang, A.mlx_model)
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                     capture_output=True, check=True).stdout, np.float32)
    hop = SR // 100; db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop * 2) / (hop * 2), "same"))[::hop] + 1e-9)
    TH = np.percentile(db, 8) + 14
    W = transcribe.load_words(wp) if wp else []
    only = set(A.pieces); prev_first = None; nflag = 0
    print(f"{len(P)} pieces, audio {audio} ({backend})")
    for k, p in enumerate(P):
        if only and k not in only: continue
        e = db[int(p["a"] * 100):int(p["b"] * 100)] > TH; idx = np.where(e)[0]
        subs = []; s = idx[0] if len(idx) else 0; prev = s
        for i in idx[1:]:
            if i - prev > 15: subs.append((s, prev)); s = i
            prev = i
        if len(idx): subs.append((s, prev))
        texts = []
        for s0, s1 in subs:
            a0 = p["a"] + s0 / 100 - 0.05; b0 = p["a"] + s1 / 100 + 0.08
            r = asr(x[int(a0 * SR):int(b0 * SR)].copy(), condition_on_previous_text=False, temperature=0.0, verbose=None)
            texts.append((round(a0, 2), r["text"].strip()))
        long = [(w["w"], round(w["b"] - w["a"], 2)) for w in W if w["a"] >= p["a"] - 0.05 and w["b"] <= p["b"] + 0.05 and w["b"] - w["a"] > 0.7]
        # repeated opening: a part starting with the same first two words as an earlier one in this piece
        starts = [tuple(norm(t)[:2]) for _, t in texts if len(norm(t)) >= 2]
        rep = len(starts) != len(set(starts))
        # a restart split across pieces: this piece opens with the same two words as the previous piece
        fw = tuple(norm(texts[0][1])[:2]) if texts and len(norm(texts[0][1])) >= 2 else None
        xrep = fw is not None and fw == prev_first; prev_first = fw
        flag = ("  !! REPEAT" if rep else "") + ("  !! REPEATS PREVIOUS PIECE" if xrep else "") + (f"  !! long words {long}" if long else "")
        nflag += bool(flag)
        print(f"[{k:2d}] {p['note']:5s} {p['a']:8.2f}-{p['b']:8.2f}{flag}")
        for t, s in texts: print(f"        {t:8.2f} | {s}")
    print(f"{nflag} flagged piece(s)")


if __name__ == "__main__":
    main()
