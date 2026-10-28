#!/usr/bin/env python3
"""Fresh components every reel, so reels in one style don't look the same every time.

The HOUSE LOOK stays fixed (house.json: type, captions, accent palette, insert framing, the speaker's face as shot). The COMPONENTS
change every reel: phone-UI scenes, paper props, polaroid / card / collage treatments, transitions, hook devices, outro
devices (kinds below). recipes/<style>/catalog.json records every component: its kind and slot, the reels that used it,
the order of the reels ("history") and a detection pattern ("sig": regexes that match the built index.html).

    components.py plan   --style clean-os [--last 7]                  # BEFORE planning: what to avoid, what is free, ideas
    components.py check  --style clean-os --project $P [--last 7]     # what the build uses; WARNS on a recent repeat
    components.py add    --style clean-os --id phone-alarm-snooze --kind scene --slot S1 --sig 'class="alarm-snooze' \\
                         --desc "alarm rings, snooze tapped on the word"                    # register a NEW component first
    components.py record --style clean-os --project $P --reel my-reel-12 --title "..."   # after the user approves: log the usage

"Recent" = the style's last --last reels (default 7, one batch of trial reels). broll_qa.py --style runs `check` on the
render's project (check "components", a warning). A component without a sig cannot be detected: give every new one a sig.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RECIPES = os.path.join(HERE, "..", "recipes")
NOVEL = ("hook", "scene", "prop", "frame", "transition", "outro")      # must be new each reel
KIND_NOTE = {"hook": "hook devices (the first 3 s)", "scene": "phone-UI / app scenes", "prop": "paper and physical props",
             "frame": "polaroid, card, collage and insert-frame treatments", "transition": "scene transitions (in / out)",
             "outro": "outro devices", "emphasis": "emphasis devices (may stay house)", "signature": "signature-word tools",
             "house": "house look (fixed)"}
LAST = 7


def path_of(style):
    p = os.path.join(RECIPES, style, "catalog.json")
    if not os.path.exists(p):
        sys.exit(f"no catalog for {style} ({p})")
    return p


def load(style):
    c = json.load(open(path_of(style), encoding="utf-8"))
    c.setdefault("reels", {})
    c.setdefault("elements", [])
    c.setdefault("history", list(c["reels"].keys()))
    c.setdefault("projects", {})
    return c


def save(style, c):
    json.dump(c, open(path_of(style), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def recent(c, last, exclude=()):
    h = [r for r in c["history"] if r not in exclude]
    return h[-last:] if last else h


def same_project(a, b):
    try:
        return os.path.realpath(os.path.expanduser(a)) == os.path.realpath(os.path.expanduser(b))
    except OSError:
        return False


def detect(c, project, extra=()):
    """ids of catalog elements whose sig matches the project's index.html (and any extra source files)"""
    texts = []
    for p in [os.path.join(project, "index.html")] + list(extra):
        if os.path.exists(p):
            texts.append(open(p, encoding="utf-8", errors="replace").read())
    if not texts:
        raise FileNotFoundError(f"no index.html in {project}")
    src = "\n".join(texts)
    used = []
    for e in c["elements"]:
        for s in e.get("sig") or []:
            try:
                if re.search(s, src):
                    used.append(e["id"])
                    break
            except re.error:
                pass
    return used


def check(style, project, last=LAST, extra=()):
    """{'used', 'repeats': [(id, kind, recent reels)], 'fresh': [...], 'unsigned': n, 'recent': [...], 'self': reel}"""
    c = load(style)
    me = [r for r, p in c["projects"].items() if same_project(p, project)]
    rec = recent(c, last, exclude=me)
    used = detect(c, project, extra)
    by = {e["id"]: e for e in c["elements"]}
    reps, fresh = [], []
    for i in used:
        e = by[i]
        if e.get("kind") not in NOVEL:
            continue
        hit = [r for r in e.get("reels", []) if r in rec]
        (reps if hit else fresh).append((i, e.get("kind"), hit))
    return {"used": used, "repeats": reps, "fresh": fresh, "recent": rec, "self": me,
            "unsigned": sum(1 for e in c["elements"] if e.get("kind") in NOVEL and not e.get("sig"))}


def cmd_plan(a):
    c = load(a.style)
    rec = recent(c, a.last)
    print(f"{a.style}: {len(c['elements'])} components in the catalog; recent reels ({len(rec)}): {', '.join(rec)}")
    print("Fill every slot of these kinds with a component NOT used in the recent reels (never used is best). The house")
    print("look (house.json) stays. Register each new component with `components.py add` (with a sig) before the build.\n")
    for k in NOVEL:
        els = [e for e in c["elements"] if e.get("kind") == k]
        avoid = [e for e in els if set(e.get("reels", [])) & set(rec)]
        free = [e for e in els if e not in avoid]
        print(f"== {k}: {KIND_NOTE[k]}")
        if avoid:
            print("   AVOID (recent): " + ", ".join(f"{e['id']} [{e.get('slot') or '-'}]" for e in avoid))
        if free:
            print("   free (older):   " + ", ".join(f"{e['id']} [{e.get('slot') or '-'}]" for e in free))
    ideas = c.get("ideas_not_built_yet")
    if ideas:
        print("\n== ideas not built yet")
        for i in (ideas if isinstance(ideas, list) else [ideas]):
            print("   " + str(i))
    untyped = [e["id"] for e in c["elements"] if not e.get("kind")]
    if untyped:
        print(f"\n({len(untyped)} older entries have no kind yet: {', '.join(untyped[:12])}{' ...' if len(untyped) > 12 else ''})")


def report(style, r):
    lines = []
    if r["repeats"]:
        lines.append(f"{len(r['repeats'])} component(s) repeat from the last {len(r['recent'])} {style} reels:")
        lines += [f"  {i} ({k}) used in {', '.join(h)}" for i, k, h in r["repeats"]]
    lines.append(f"{len(r['fresh'])} fresh: " + (", ".join(i for i, _, _ in r["fresh"]) or "none detected (register new ones with a sig)"))
    return lines


def cmd_check(a):
    r = check(a.style, a.project, a.last, a.src or ())
    print("\n".join(report(a.style, r)))
    if r["self"]:
        print(f"(this project is recorded as {', '.join(r['self'])}; it is not compared with itself)")
    sys.exit(1 if a.strict and r["repeats"] else 0)


def cmd_add(a):
    c = load(a.style)
    if any(e["id"] == a.id for e in c["elements"]):
        sys.exit(f"{a.id} is already in the catalog")
    for s in a.sig:
        re.compile(s)
    c["elements"].append({"id": a.id, "kind": a.kind, "slot": a.slot, "desc": a.desc, "sig": a.sig, "reels": [], "where": a.where})
    save(a.style, c)
    print(f"added {a.id} ({a.kind}) to {a.style}")


def cmd_record(a):
    c = load(a.style)
    used = detect(c, a.project, a.src or ())
    if a.reel not in c["reels"]:
        c["reels"][a.reel] = a.title or a.project
    if a.reel not in c["history"]:
        c["history"].append(a.reel)
    c["projects"][a.reel] = a.project.replace(os.path.expanduser("~"), "~")
    for e in c["elements"]:
        if e["id"] in used and a.reel not in e.setdefault("reels", []):
            e["reels"].append(a.reel)
    save(a.style, c)
    print(f"recorded {a.reel}: {len(used)} component(s): {', '.join(used)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("--style", required=True); p.add_argument("--last", type=int, default=LAST)
    p = sp.add_parser("check"); p.add_argument("--style", required=True); p.add_argument("--project", required=True)
    p.add_argument("--last", type=int, default=LAST); p.add_argument("--src", nargs="*", help="generator files to scan too")
    p.add_argument("--strict", action="store_true", help="exit 1 on a repeat")
    p = sp.add_parser("add"); p.add_argument("--style", required=True); p.add_argument("--id", required=True)
    p.add_argument("--kind", required=True, choices=list(KIND_NOTE)); p.add_argument("--slot"); p.add_argument("--desc", required=True)
    p.add_argument("--sig", nargs="+", required=True, help="regex(es) that match the built index.html"); p.add_argument("--where")
    p = sp.add_parser("record"); p.add_argument("--style", required=True); p.add_argument("--project", required=True)
    p.add_argument("--reel", required=True); p.add_argument("--title"); p.add_argument("--src", nargs="*")
    a = ap.parse_args()
    {"plan": cmd_plan, "check": cmd_check, "add": cmd_add, "record": cmd_record}[a.cmd](a)


if __name__ == "__main__":
    main()
