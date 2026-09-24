#!/usr/bin/env python3
"""Search the meme + meme-SFX library for a moment in the transcript.

    meme_find.py "they said it was guaranteed"          # rank memes for a line
    meme_find.py --emotion disbelief                     # filter by tag
    meme_find.py --list                                  # everything, with status

Scores tag, trigger-phrase and use-case word overlap and prefers `hot` over
`evergreen` over `dying`. It is a shortlist, not a decision: read the top
three against the line and the speaker's tone, and never reuse a meme
inside one reel (build.mjs warns on repeated meme sounds).
"""
import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "library")
TREND = {"hot": 1.0, "evergreen": 0.5, "dying": -1.0}
WORD = re.compile(r"[a-z']+")


def words(s):
    return set(WORD.findall(s.lower()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("line", nargs="?", default="")
    ap.add_argument("--emotion", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("-n", type=int, default=5)
    a = ap.parse_args()

    memes = []
    mdir = os.path.join(LIB, "memes")
    for d in sorted(os.listdir(mdir)):
        p = os.path.join(mdir, d, "meta.json")
        if os.path.exists(p):
            memes.append(json.load(open(p)))
    sfx = json.load(open(os.path.join(LIB, "sfx", "manifest.json")))

    if a.list:
        print(f"{len(memes)} memes")
        for m in memes:
            kind = "clip+alpha" if m.get("has_alpha") else "clip" if m.get("clip") else "image"
            snd = "own audio" if m.get("has_audio") else f"sfx {m.get('sfx', '-')}"
            print(f"  {m['id']:22s} {m['trend_status']:9s} {kind:10s} {snd:18s} {','.join(m['emotion'])}  | {m['use_case']}")
        print(f"\n{sum(1 for v in sfx.values() if v['role'] == 'meme')} meme sounds")
        for k, v in sfx.items():
            if v["role"] == "meme":
                print(f"  {k:18s} {v['duration']:4.1f}s  {','.join(v['tags'])}")
        return

    q = words(a.line) | words(a.emotion)
    scored = []
    for m in memes:
        tags = set(m["emotion"])
        trig = set().union(*[words(t) for t in m["trigger_phrases"]]) if m["trigger_phrases"] else set()
        s = 3 * len(q & tags) + 2 * len(q & trig) + len(q & words(m["use_case"]))
        if any(t.lower() in a.line.lower() for t in m["trigger_phrases"]):
            s += 4
        if a.emotion and a.emotion not in tags:
            continue
        scored.append((s + TREND.get(m["trend_status"], 0), m))
    scored.sort(key=lambda x: -x[0])
    print(f"memes for: {a.line or a.emotion!r}")
    for s, m in scored[: a.n]:
        print(f"  {s:4.1f}  {m['id']:22s} [{','.join(m['emotion'])}] {m['use_case']}")
    snd = sorted(((3 * len(q & set(v["tags"])), k) for k, v in sfx.items() if v["role"] == "meme"), reverse=True)
    print("meme sounds:", ", ".join(k for s, k in snd[:5] if s > 0) or "(no tag match; pick by ear)")


if __name__ == "__main__":
    main()
