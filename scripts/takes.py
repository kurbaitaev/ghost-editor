#!/usr/bin/env python3
"""Find every attempt at every script sentence in a whole-recording transcript and score it (words + face).

    takes.py --script script.txt --words build/islands.json [--facescan build/facescan.json]
             [--attempts build/attempts.md] --out build/takes.json

script: numbered lines ("1. text"); an unnumbered line takes the next number (a plain file = lines 1..N).
words: islands_tx.py output (best: each VAD island transcribed on its own) or any whisper words json.
Units: script lines split into sentences; sentences under 4 words merge forward (lists stay one unit).
Matching: Smith-Waterman on normalised word tokens with fuzzy (inflection-tolerant) word equality; repeated best-alignment
extraction with masking finds every attempt, including partial ones.
Face (facescan.py rows with true frame times): problems from 0.30 s before the first word to 0.30 s after the last one,
against the take's own median (facescan.badframes), the clean lead/tail, pose and face position.
attempts.md: gem_audit.py attempts table rows overlapping the attempt (verdict: problems).
Writes takes.json and prints the take table (original seconds)."""
import argparse, json, os, re, sys, difflib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from facescan import badframes, matrix
from transcribe import load_words


def norm(t):
    t = t.lower().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я\-]+", "", t).strip("-")


def toks(s):
    return [x for x in (norm(w) for w in re.split(r"[\s ]+", s)) if x]


def wsim(a, b):
    if a == b: return 1.0
    if len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]: return 0.8
    r = difflib.SequenceMatcher(None, a, b).ratio()
    return r if r >= 0.72 else 0.0


def units_of(script_path):
    U = []; n = 0
    for line in open(script_path):
        line = line.strip()
        if not line: continue
        m = re.match(r"(\d+)\.\s*(.*)", line)
        n, body = (int(m.group(1)), m.group(2)) if m else (n + 1, line)
        parts = re.split(r"(?<=[.!?…»])\s+(?=[А-ЯЁA-Z«])", body)
        merged = []
        for p in parts:
            if merged and len(toks(merged[-1])) < 4: merged[-1] += " " + p
            else: merged.append(p)
        if len(merged) > 1 and len(toks(merged[-1])) < 4: merged[-2] += " " + merged.pop()
        for k, p in enumerate(merged):
            U.append({"id": f"{n}" + ("" if len(merged) == 1 else "abcdefgh"[k]), "line": n, "text": p, "toks": toks(p)})
    return U


def sw(u, w, mask):
    n, m = len(u), len(w)
    H = np.zeros((n + 1, m + 1)); T = np.zeros((n + 1, m + 1), np.int8)
    S = np.array([[0.0 if mask[j] else wsim(u[i], w[j]) for j in range(m)] for i in range(n)])
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = S[i - 1, j - 1]
            d = H[i - 1, j - 1] + (2.0 * s if s > 0 else -1.0)
            up = H[i - 1, j] - 0.8          # unit word missing in speech
            lf = H[i, j - 1] - 0.6          # extra spoken word (stumble, repeat, filler)
            best = max(0.0, d, up, lf); H[i, j] = best
            T[i, j] = 0 if best == 0 else (1 if best == d else (2 if best == up else 3))
    i, j = np.unravel_index(np.argmax(H), H.shape); score = H[i, j]
    path = []
    while i > 0 and j > 0 and T[i, j] != 0:
        t = T[i, j]
        if t == 1: path.append((i - 1, j - 1, S[i - 1, j - 1] > 0)); i -= 1; j -= 1
        elif t == 2: path.append((i - 1, None, False)); i -= 1
        else: path.append((None, j - 1, False)); j -= 1
    return score, path[::-1]


def mmss(x):
    m = re.match(r"(\d+):(\d+(?:\.\d+)?)", x.strip())
    return int(m.group(1)) * 60 + float(m.group(2)) if m else None


def gemini_rows(p):
    R = []
    if not p or not os.path.exists(p): return R
    for line in open(p):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 6 and mmss(c[1]) is not None and mmss(c[2]) is not None:
            R.append({"line": c[0], "a": mmss(c[1]), "b": mmss(c[2]), "said": c[3], "verdict": c[4].upper(), "problems": c[5]})
    return R


def visual(FT, V, a, b):
    """problems from 0.30 s before the first word to 0.30 s after the last one; 'speech' = between first and last word"""
    if not len(FT): return {}
    m = (FT >= a - 0.30) & (FT <= b + 0.30); t = FT[m]; v = V[m]
    sp = (t >= a - 0.05) & (t <= b + 0.05)
    med = np.nanmedian(v[sp], 0) if sp.any() else np.nanmedian(v, 0)
    K = badframes(v, med); bad = np.zeros(len(t), bool)
    for x in K.values(): bad |= x
    ev = []
    for name, x in K.items():
        k = 0
        while k < len(x):
            if x[k]:
                j = k
                while j + 1 < len(x) and x[j + 1]: j += 1
                ev.append((round(float(t[k]), 2), round(float(t[j]), 2), name)); k = j + 1
            else: k += 1
    # clean lead: frames just before the first word, counting back until the first bad one (cap 0.30 s)
    pre = np.where((t < a) & bad)[0]; lead = round(a - (t[pre[-1]] + 1 / 30) if len(pre) else 0.30, 2)
    post = np.where((t > b) & bad)[0]; tail = round((t[post[0]] - 1 / 30) - b if len(post) else 0.30, 2)
    return {"vbad": int((bad & sp).sum()), "vev": sorted(e for e in ev if e[1] >= a - 0.05 and e[0] <= b + 0.05),
            "lead": max(lead, 0.0), "tail": max(tail, 0.0), "pose": [round(float(x), 1) for x in med[:3]],
            "pos": [round(float(np.nanmedian(v[sp][:, k])), 1) for k in (8, 9, 10)] if sp.any() and V.shape[1] > 10 else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True); ap.add_argument("--words", required=True)
    ap.add_argument("--facescan"); ap.add_argument("--attempts"); ap.add_argument("--out", required=True)
    A = ap.parse_args()
    U = units_of(A.script)
    W = [{"w": x["w"], "n": norm(x["w"]), "a": x["a"], "b": x["b"], "p": x["p"]} for x in load_words(A.words) if norm(x["w"])]
    wt = [x["n"] for x in W]
    G = gemini_rows(A.attempts)
    F = json.load(open(A.facescan)) if A.facescan and os.path.exists(A.facescan) else []
    FT, V = matrix(F) if F else (np.zeros(0), np.zeros((0, 12)))
    out = []
    for u in U:
        mask = [False] * len(W); found = []
        n = len(u["toks"])
        while True:
            score, path = sw(u["toks"], wt, mask)
            matched = [p for p in path if p[2]]
            if score < max(3.0, 0.9 * n) or len(matched) < max(2, 0.3 * n): break
            js = [p[1] for p in path if p[1] is not None]
            j0, j1 = min(js), max(js)
            for j in range(j0, j1 + 1): mask[j] = True
            ui = [p[0] for p in matched]
            extra = [W[p[1]]["w"] for p in path if p[0] is None]
            missing = [u["toks"][p[0]] for p in path if p[1] is None and p[0] is not None]
            gaps = [round(W[j + 1]["a"] - W[j]["b"], 2) for j in range(j0, j1)]
            g = [x for x in G if x["a"] < W[j1]["b"] + 1.0 and x["b"] > W[j0]["a"] - 1.0]
            found.append({"j0": j0, "j1": j1, "a": round(W[j0]["a"], 2), "b": round(W[j1]["b"], 2),
                          "cov": round(len(matched) / n, 2), "first": min(ui) == 0, "last": max(ui) == n - 1,
                          "extra": extra, "missing": missing, "maxgap": max(gaps) if gaps else 0,
                          "said": " ".join(W[j]["w"] for j in range(j0, j1 + 1)),
                          "minp": round(min(W[j]["p"] for j in range(j0, j1 + 1)), 2),
                          "gem": [f"{x['verdict']}: {x['problems'][:80]}" for x in g],
                          **visual(FT, V, W[j0]["a"], W[j1]["b"])})
        found.sort(key=lambda x: x["a"])
        out.append({**{k: u[k] for k in ("id", "line", "text")}, "n": n, "attempts": found})
    os.makedirs(os.path.dirname(os.path.abspath(A.out)), exist_ok=True)
    json.dump({"script": os.path.abspath(A.script), "units": out, "words": W}, open(A.out, "w"), ensure_ascii=False, indent=1,
              default=lambda o: o.item() if hasattr(o, "item") else str(o))
    for u in out:
        print(f"\n[{u['id']}] {u['text']}")
        for k, x in enumerate(u["attempts"]):
            flag = "FULL" if x["cov"] >= 0.9 and x["first"] and x["last"] else "part"
            print(f"  {k:2d} {x['a']:7.2f}-{x['b']:7.2f} {flag} cov {x['cov']:.2f} gap {x['maxgap']:.2f} p {x['minp']:.2f}"
                  f" +{len(x['extra'])} -{len(x['missing'])} | {x['said'][:150]}")
            if x["extra"]: print(f"       extra: {' '.join(x['extra'])[:120]}")
            if "vbad" in x: print(f"       vis bad {x['vbad']}f lead {x['lead']:.2f} tail {x['tail']:.2f} pose {x['pose']} | {' '.join(f'{e[2]}@{e[0]:.2f}-{e[1]:.2f}' for e in x['vev'])[:150]}")
            for gg in x["gem"][:2]: print(f"       gem {gg}")
    print(f"\n{len(out)} units, {sum(len(u['attempts']) for u in out)} attempts -> {A.out}")


if __name__ == "__main__":
    main()
