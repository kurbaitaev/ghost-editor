#!/usr/bin/env python3
"""Taste ledger: record the user's corrections across reels; build.mjs applies them as defaults and warnings.

    taste.py list [--all]                       active rules (--all: forgotten/superseded too)
    taste.py show <id>
    taste.py add "<what the user said>" [--id ID] [--reel NAME] [--source TEXT]
                 [--set path=value ...]          a default build.mjs fills when reel.json leaves it unset
                 [--metric NAME --max N | --min N] a measured check (see `taste.py metrics`)
                 [--ban-sfx ID] [--ban-meme ID] [--ban-text S] [--ban-transition K] [--ban-style S]
                 [--when-style S ...] [--severity warn|info] [--kind process|prefer|note] [--supersedes ID]
                 [--from user|skill]            user (default) = the user's own words, quoted as "you said: ..."
                 Saying the same thing again (same --id) bumps `times` and keeps both wordings.
    taste.py tag <id> user|skill                where a rule came from: only the user's own feedback is "you said"
    taste.py forget <id> [--reason TEXT]        deactivate, keep the history (the user can undo with restore)
    taste.py restore <id> | remove <id>
    taste.py prompt [--style S]                 the active rules as plain lines for the planning step
    taste.py check <project>                    measure a reel.json against the rules (node taste.mjs check)
    taste.py apply <project>                    the defaults taste would fill for this project (dry run)
    taste.py log-reel <project> [--verdict T]   remember a shipped reel (style, accent, music) for freshness checks
    taste.py metrics                            the checks a rule can use

The file: --taste > $GHOST_TASTE > <skill>/taste.json (private; the public edition ships an empty one).
Taste is a PRIOR, not evidence: reel.json always wins; nothing here silently changes an explicit choice.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.expanduser(os.environ.get("GHOST_EDITOR_SKILL") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

METRICS = {
    "punch_ins": "snap zooms that punch in (zoom.snaps with z > 1)",
    "cut_zoom_share": "share of cuts that also get a snap or push within 0.15 s (minCuts, default 4)",
    "flashy_transitions": "scene transitions that are expand, wipe or glitch",
    "sfx_on_cuts": "sounds on bare cuts (snap whooshes)",
    "short_pause_cuts": "cuts that remove a pause shorter than `gap` (0.7 s) inside a sentence",
    "light_accent_on_white": "white scenes while the accent is a light colour (lime, yellow)",
    "lowres_broll": "B-roll / image sources whose short side is below `minSide` (1080)",
    "same_music_as_last_reel": "the music bed of the last logged reel",
}


def taste_path(explicit=None):
    for c in (explicit, os.environ.get("GHOST_TASTE"), os.path.join(SKILL, "taste.json"), os.path.join(HERE, "taste.json")):
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return os.path.abspath(explicit or os.path.join(SKILL, "taste.json"))


def load(p):
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {"version": 1, "about": "What the user corrected or approved across reels. A prior, not evidence: reel.json always wins.", "rules": [], "reels": []}


def save(p, t):
    t["updated"] = dt.date.today().isoformat()
    tmp = p + ".tmp"
    json.dump(t, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, p)


def slug(s):
    w = re.findall(r"[a-zа-яё0-9]+", s.lower())[:5]
    return "-".join(w) or "rule"


def val(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def node(args):
    mjs = next((p for p in (os.path.join(HERE, "taste.mjs"), os.path.join(HERE, "lib", "taste.mjs")) if os.path.exists(p)), "taste.mjs")
    r = subprocess.run(["node", mjs] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode


def line(r):
    flag = "" if r.get("active", True) else "  (forgotten)" if not r.get("supersededBy") else f"  (superseded by {r['supersededBy']})"
    mach = []
    if r.get("set"):
        mach.append("set " + ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in r["set"].items()))
    if r.get("check"):
        c = r["check"]
        mach.append(f"check {c.get('metric')} " + " ".join(f"{k} {v}" for k, v in c.items() if k in ("max", "min")))
    if r.get("ban"):
        mach.append("ban " + ", ".join(f"{k}:{'/'.join(v)}" for k, v in r["ban"].items() if v))
    if r.get("enforcedBy"):
        mach.append(f"enforced by {r['enforcedBy']}")
    return f"{r['id']:32s} {r.get('kind', 'note'):8s} {r.get('from', 'skill'):5s} x{r.get('times', 1)}  {r['say']}{flag}" + (f"\n{'':44s}{'; '.join(mach)}" if mach else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "show", "add", "tag", "forget", "restore", "remove", "prompt", "check", "apply", "log-reel", "metrics"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("value", nargs="?", help="tag: user | skill")
    ap.add_argument("--from", dest="from_", choices=["user", "skill"], default="user",
                    help="add: user = the user's own words (quoted as 'you said'), skill = a rule the skill learned")
    ap.add_argument("--taste")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--kind", choices=["check", "default", "ban", "prefer", "process", "note"])
    ap.add_argument("--set", action="append", default=[], metavar="PATH=VALUE")
    ap.add_argument("--metric", choices=sorted(METRICS))
    ap.add_argument("--max", type=float)
    ap.add_argument("--min", type=float)
    ap.add_argument("--ban-sfx", action="append", default=[])
    ap.add_argument("--ban-meme", action="append", default=[])
    ap.add_argument("--ban-text", action="append", default=[])
    ap.add_argument("--ban-transition", action="append", default=[])
    ap.add_argument("--ban-style", action="append", default=[])
    ap.add_argument("--when-style", action="append", default=[])
    ap.add_argument("--severity", choices=["warn", "info"])
    ap.add_argument("--reel")
    ap.add_argument("--source")
    ap.add_argument("--supersedes")
    ap.add_argument("--reason")
    ap.add_argument("--verdict")
    ap.add_argument("--style")
    a = ap.parse_args()
    p = taste_path(a.taste)
    t = load(p)
    rules = t.setdefault("rules", [])
    by = {r["id"]: r for r in rules}
    today = dt.date.today().isoformat()

    if a.cmd == "metrics":
        for k, v in METRICS.items():
            print(f"{k:26s} {v}")
    elif a.cmd == "list":
        print(f"{p}  ({sum(1 for r in rules if r.get('active', True))} active of {len(rules)})")
        for r in rules:
            if a.all or r.get("active", True):
                print(line(r))
    elif a.cmd == "show":
        r = by.get(a.arg) or sys.exit(f"no rule '{a.arg}'")
        print(json.dumps(r, indent=1, ensure_ascii=False))
    elif a.cmd == "add":
        if not a.arg:
            sys.exit('taste.py add "<what the user said>" ...')
        rid = a.id or slug(a.arg)
        r = by.get(rid)
        new = r is None
        if new:
            r = {"id": rid, "say": a.arg, "from": a.from_, "kind": a.kind or "note", "origin": "correction" if a.from_ == "user" else "skill-rule", "source": [], "reels": [],
                 "first": today, "last": today, "times": 1, "active": True}
            rules.append(r)
        else:
            r["times"] = r.get("times", 1) + 1
            r["last"] = today
            r["active"] = True
            if a.arg != r["say"]:  # the newest wording leads; earlier wordings stay in the history
                r.setdefault("said", []).append({"until": today, "say": r["say"]})
                r["say"] = a.arg
        if a.set:
            r.setdefault("set", {}).update({k: val(v) for k, v in (s.split("=", 1) for s in a.set)})
            r["kind"] = a.kind or ("check" if r.get("check") else "default")
        if a.metric:
            num = lambda x: int(x) if float(x).is_integer() else x  # noqa: E731
            r["check"] = {"metric": a.metric, **({"max": num(a.max)} if a.max is not None else {}), **({"min": num(a.min)} if a.min is not None else {})}
            if a.max is None and a.min is None:
                r["check"]["max"] = 0
            r["kind"] = a.kind or "check"
            r.setdefault("severity", "warn")
        bans = {"sfx": a.ban_sfx, "memes": a.ban_meme, "text": a.ban_text, "transitions": a.ban_transition, "styles": a.ban_style}
        if any(bans.values()):
            b = r.setdefault("ban", {})
            for k, v in bans.items():
                if v:
                    b[k] = sorted(set(b.get(k, [])) | set(v))
            r["kind"] = a.kind or "ban"
            r.setdefault("severity", "warn")
        if a.when_style:
            r["when"] = {"style": a.when_style}
        if a.severity:
            r["severity"] = a.severity
        if a.kind and not (a.set or a.metric or any(bans.values())):
            r["kind"] = a.kind
        if a.reel and a.reel not in r.setdefault("reels", []):
            r["reels"].append(a.reel)
        if a.source:
            r.setdefault("source", []).append(a.source)
        if a.supersedes and a.supersedes in by:
            r["supersedes"] = a.supersedes
            by[a.supersedes].update({"active": False, "supersededBy": rid})
        save(p, t)
        print(("added " if new else f"again (x{r['times']}) ") + line(r))
    elif a.cmd == "tag":
        r = by.get(a.arg) or sys.exit(f"no rule '{a.arg}'")
        if a.value not in ("user", "skill"):
            sys.exit("taste.py tag <id> user|skill")
        r["from"] = a.value
        save(p, t)
        print(line(r))
    elif a.cmd in ("forget", "restore", "remove"):
        r = by.get(a.arg) or sys.exit(f"no rule '{a.arg}'")
        if a.cmd == "remove":
            rules.remove(r)
        else:
            r["active"] = a.cmd == "restore"
            if a.cmd == "forget":
                r["forgotten"] = {"date": today, **({"reason": a.reason} if a.reason else {})}
            else:
                r.pop("forgotten", None)
        save(p, t)
        print(f"{a.cmd} {a.arg}")
    elif a.cmd == "prompt":
        sys.exit(node(["brief", "--taste", p] + (["--style", a.style] if a.style else [])))
    elif a.cmd in ("check", "apply"):
        if not a.arg:
            sys.exit(f"taste.py {a.cmd} <project>")
        sys.exit(node([a.cmd, a.arg, "--taste", p, "--skill", SKILL]))
    elif a.cmd == "log-reel":
        proj = os.path.abspath(a.arg or ".")
        raw = json.load(open(os.path.join(proj, "reel.json"), encoding="utf-8"))
        stp = os.path.join(SKILL, "styles", f"{raw.get('style')}.json")
        preset = json.load(open(stp, encoding="utf-8")) if raw.get("style") and os.path.exists(stp) else {}
        brand = {**(preset.get("brand") or {}), **(raw.get("brand") or {})}
        music = raw.get("music", preset.get("music")) or {}
        e = {"name": os.path.basename(proj), "title": raw.get("title"), "project": proj, "date": today, "style": raw.get("style"),
             "accent": brand.get("accent"), "music": music.get("id") if isinstance(music, dict) else None, "verdict": a.verdict or "shipped"}
        t.setdefault("reels", [])
        t["reels"] = [x for x in t["reels"] if os.path.abspath(os.path.expanduser(x.get("project", "/-"))) != proj] + [e]
        save(p, t)
        print("logged", json.dumps(e, ensure_ascii=False))


if __name__ == "__main__":
    main()
