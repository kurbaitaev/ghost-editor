#!/usr/bin/env python3
"""What one reel cost in Claude usage: sum the usage fields of its helper transcripts (.jsonl).

    reel_usage.py LABEL=path.jsonl [LABEL=path.jsonl ...] [--reels N]      per reel = totals / N

A helper's transcript is ~/.claude/projects/<project>/<session id>/subagents/agent-<id>.jsonl (the Agent tool's output
file links to it); a whole session is ~/.claude/projects/<project>/<session id>.jsonl.
The method of the 2026-10-19 baseline (docs/PLAYBOOK.md "Cost"): a turn = an assistant line with usage; fresh input =
input + cache_creation tokens; cache-read; output; tool calls = tool_use blocks; images = image blocks in tool results.
Claude Code writes one line per content block with the message's usage repeated, so these sums run high; the "dedup"
columns count each API call once (compare like with like: line method to line method)."""
import json, sys

def measure(path):
    r = dict(turns=0, tools=0, img=0, fresh=0, cr=0, out=0, models={})
    seen = {}
    for line in open(path, errors="ignore"):
        try: m = json.loads(line)
        except Exception: continue
        msg = m.get("message") or {}
        if not isinstance(msg, dict): continue
        u = msg.get("usage")
        if u and m.get("type") == "assistant":
            r["turns"] += 1
            r["fresh"] += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            r["cr"] += u.get("cache_read_input_tokens", 0); r["out"] += u.get("output_tokens", 0)
            mid = msg.get("id") or line[:80]
            seen[mid] = (u, msg.get("model", "?"))
        c = msg.get("content")
        if isinstance(c, list):
            for b in c:
                if not isinstance(b, dict): continue
                if b.get("type") == "tool_use": r["tools"] += 1
                if b.get("type") == "tool_result" and isinstance(b.get("content"), list):
                    r["img"] += sum(1 for x in b["content"] if isinstance(x, dict) and x.get("type") == "image")
    d = dict(calls=len(seen), fresh=0, cr=0, out=0)
    for u, model in seen.values():
        d["fresh"] += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        d["cr"] += u.get("cache_read_input_tokens", 0); d["out"] += u.get("output_tokens", 0)
        r["models"][model] = r["models"].get(model, 0) + 1
    r["dedup"] = d
    return r

if __name__ == "__main__":
    argv = sys.argv[1:]; n = 1
    if "--reels" in argv:
        i = argv.index("--reels"); n = float(argv[i + 1]); del argv[i:i + 2]
    args = argv
    tot = dict(turns=0, tools=0, img=0, fresh=0, cr=0, out=0)
    for a in args:
        label, path = a.split("=", 1) if "=" in a else (a.rsplit("/", 1)[-1][:24], a)
        r = measure(path)
        print(f"{label:24} turns {r['turns']:5} tools {r['tools']:5} img {r['img']:4} fresh {r['fresh']:>11,} cache-read {r['cr']:>13,} out {r['out']:>9,}"
              f"  | dedup calls {r['dedup']['calls']:4} cr {r['dedup']['cr']:>12,}  models {r['models']}")
        for k in tot: tot[k] += r[k]
    print("TOTAL", {k: f"{v:,}" for k, v in tot.items()})
    if n != 1: print(f"PER REEL (/{n:g})", {k: f"{v / n:,.0f}" for k, v in tot.items()})
