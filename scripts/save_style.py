#!/usr/bin/env python3
"""Save a finished edit as a reusable style preset (references/styles.md "Saving a new style").

    save_style.py <project> <style-name> [--about "one line"] [--best-for "..."] [--base <preset>]
                  [--skill DIR] [--out-skill DIR] [--music-auto] [--force] [--dry-run]
                  [--verify-on <other project> [--verify-dir DIR] [--render]]

1. Starts from the closest preset (the reel's own `style`, or --base) and copies it.
2. Fills the look from what actually rendered (preset merged with reel.json): brand, the caption look
   (style, group, size, case, keyword style; never the per-recording fixes/tags/highlight words),
   sfxProfile, music (the bed and level; --music-auto tags the bed's manifest entry with the new style
   and sets music.id "auto"), look, scene defaults (the most used transition and the background per
   scene kind), zoom.snapSfx/base, layout.compact, platform, mix.roleDb, matte. Writes `_about` (one line)
   and `_source` (where it came from).
3. Writes styles/<name>.json, adds a row to the table in references/styles.md, and saves the reel.json
   that defined it as examples/gallery/<name>.reel.json (style: <name>, the look keys moved to the preset).
4. Checks the round trip: the example + the new preset must build to the same composition as the original
   reel.json (same index.html modulo paths, same SFX events). --verify-on builds another project in the new
   style and snapshots it next to its own look (--render for a full render), the "does it read as its own
   look" step.
It refuses a reel that has no render (build/reel.mp4) or whose render report failed, unless --force.
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hf_version import hf  # noqa: E402  (the pinned HyperFrames CLI, scripts/HF_VERSION)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from reelproj import DEFAULT_SKILL, beats_timeline, load_project, sh  # noqa: E402

CAPTION_LOOK = ["style", "group", "y", "size", "upper", "lowercase", "keywordStyle", "font", "weight", "tracking", "stroke", "splitY"]
SCENE_LOOK = ["bg", "in", "out"]


def most_common(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    # values can be objects (a shader bg {"look": ...}): count them by their JSON
    keys = [json.dumps(x, sort_keys=True) if isinstance(x, (dict, list)) else x for x in xs]
    k = collections.Counter(keys).most_common(1)[0][0]
    return xs[keys.index(k)]


def derive_preset(pr, base, name, about, project_rel):
    spec = pr.spec
    p = json.loads(json.dumps(base))  # deep copy of the closest preset
    for k in ("_about", "_name", "_source"):
        p.pop(k, None)
    if spec.get("brand"):
        p["brand"] = dict(spec["brand"])
    cap = spec.get("captions") or {}
    look = {k: cap[k] for k in CAPTION_LOOK if k in cap}
    if isinstance(cap.get("highlight"), str):  # a colour, not a list of words
        look["highlight"] = cap["highlight"]
    p["captions"] = look
    for k in ("sfxProfile", "look", "platform", "matte"):
        if k in spec:
            p[k] = spec[k]
    m = spec.get("music")
    p["music"] = {k: m[k] for k in ("id", "src", "db", "fadeIn", "fadeOut") if k in m} if isinstance(m, dict) else m
    if (spec.get("mix") or {}).get("roleDb"):
        p["mix"] = {"roleDb": spec["mix"]["roleDb"]}
    z = spec.get("zoom") or {}
    zl = {k: z[k] for k in ("snapSfx", "base") if k in z and not (k == "base" and z[k] == 1)}
    if zl:
        p["zoom"] = zl
    if (spec.get("layout") or {}).get("compact"):
        p["layout"] = {"compact": True}
    scenes = [b for b in spec.get("beats") or [] if b.get("type") == "scene"]
    sd = dict(base.get("scenes") or {})
    if len(scenes) >= 2:
        di = most_common([b.get("in", sd.get("default_in", "blur")) for b in scenes])
        if di:
            sd["default_in"] = di
    for kind in sorted({b.get("kind") for b in scenes}):
        ks = [b for b in scenes if b.get("kind") == kind]
        d = dict(sd.get(kind) or {})
        for f in ("bg", "out"):
            v = most_common([b.get(f) for b in ks])
            if v is not None:
                d[f] = v
        if d:
            sd[kind] = d
    if sd:
        p["scenes"] = sd
    # signature numbers for the one-liner and the table row
    beats = beats_timeline(pr)
    cov = sum(b["t1"] - b["t0"] for b in beats if b["t0"] is not None and b["full"])
    kinds = collections.Counter(b["raw"].get("kind") if b["type"] == "scene" else b["type"] for b in beats)
    ev = (pr.sfx or {}).get("events", [])
    sig = {"kinds": dict(kinds), "coverage": round(100 * cov / max(pr.total, 1)), "sfx_per_min": round(60 * len(ev) / max(pr.total, 1), 1),
           "accent": (spec.get("brand") or {}).get("accent"), "captions": cap.get("style", "house"), "music": (m or {}).get("id") if isinstance(m, dict) else None}
    if not about:
        ks = ", ".join(f"{k}" + (f" x{v}" if v > 1 else "") for k, v in kinds.most_common())
        about = (f"{sig['captions']} captions, accent {sig['accent']}, {ks or 'no beats'} ({sig['coverage']}% full-screen), "
                 f"{spec.get('sfxProfile', 'standard')} sound ({sig['sfx_per_min']}/min), bed {sig['music'] or 'none'}; saved from \"{spec.get('title', pr.path)}\".")
    p = {"_about": about, "_source": {"project": project_rel, "title": spec.get("title"), "saved": dt.date.today().isoformat(), "base": base.get("_name")}, **p}
    return p, sig


def example_from(raw, preset, name):
    """reel.json with the look keys moved into the preset: what remains is the recording (takes, beats, fixes)."""
    ex = json.loads(json.dumps(raw))
    ex["style"] = name
    for k in ("brand", "sfxProfile", "look", "music", "platform", "matte", "mix"):
        if k in ex and k in preset and json.dumps(ex[k], sort_keys=True) == json.dumps(preset[k], sort_keys=True):
            del ex[k]
    cap = ex.get("captions") or {}
    for k in CAPTION_LOOK:
        if k in cap and preset.get("captions", {}).get(k) == cap[k]:
            del cap[k]
    if isinstance(cap.get("highlight"), str) and preset.get("captions", {}).get("highlight") == cap["highlight"]:
        del cap["highlight"]
    if cap:
        ex["captions"] = cap
    else:
        ex.pop("captions", None)
    z = ex.get("zoom") or {}
    for k in ("snapSfx", "base"):
        if k in z and (preset.get("zoom") or {}).get(k) == z[k]:
            del z[k]
    if (ex.get("layout") or {}).get("compact") and (preset.get("layout") or {}).get("compact"):
        del ex["layout"]["compact"]
        if not ex["layout"]:
            del ex["layout"]
    order = ["title", "style"] + [k for k in ex if k not in ("title", "style")]
    return {k: ex[k] for k in order if k in ex}


def styles_row(name, preset, sig, best_for):
    kinds = ", ".join(f"`{k}`" for k in sig["kinds"]) or "none"
    cap = preset.get("captions", {}).get("style", "house")
    look = f"{cap} captions, accent {sig['accent']}, {sig['coverage']}% full-screen scenes"
    m = preset.get("music")
    music = "none" if not m else (m.get("id") or "custom") if isinstance(m, dict) else str(m)
    return f"| `{name}` | {look} | {best_for or 'like the reel it came from'} | {kinds} | {preset.get('sfxProfile', 'standard')} | {music} |"


def add_row(md_path, row, name):
    lines = open(md_path).read().split("\n")
    if any(l.startswith(f"| `{name}` |") for l in lines):
        lines = [row if l.startswith(f"| `{name}` |") else l for l in lines]
    else:
        idx = [i for i, l in enumerate(lines) if l.startswith("| `")]
        if not idx:
            raise SystemExit(f"no style table rows in {md_path}")
        # the first table: the last consecutive row after the first one
        last = idx[0]
        while last + 1 < len(lines) and lines[last + 1].startswith("| `"):
            last += 1
        lines.insert(last + 1, row)
    open(md_path, "w").write("\n".join(lines))


def copy_project(src, dst, reel):
    """A buildable copy: reel.json replaced, big media symlinked, small build inputs copied."""
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.join(dst, "assets"))
    os.makedirs(os.path.join(dst, "build"))
    json.dump(reel, open(os.path.join(dst, "reel.json"), "w"), indent=1, ensure_ascii=False)
    for f in os.listdir(os.path.join(src, "assets")):
        p = os.path.join(src, "assets", f)
        if f in ("fonts", "sfx", "memes", "icons", "music") or f.startswith(("hold-", "outro")):
            continue  # build.mjs copies these itself
        if os.path.isdir(p):
            shutil.copytree(p, os.path.join(dst, "assets", f), symlinks=True)
        else:
            os.symlink(os.path.realpath(p), os.path.join(dst, "assets", f))
    # build inputs made by other tools: words, face track, pre-rendered transition windows, AI caption tags
    for f in ("words.whisper.json", "face.json", "transitions.json", "ai-tags.json"):
        if os.path.exists(os.path.join(src, "build", f)):
            shutil.copy(os.path.join(src, "build", f), os.path.join(dst, "build", f))
    return dst


def build(skill, proj):
    r = sh(["node", os.path.join(skill, "scripts", "build.mjs"), proj])
    return r.returncode, r.stdout + r.stderr


def normalise(html):
    return re.sub(r"<title>.*?</title>", "", html)


def restyle(raw, preset, name):
    """Another project's reel.json with its look stripped so the new style shows."""
    r = json.loads(json.dumps(raw))
    r["style"] = name
    for k in ("brand", "sfxProfile", "look", "music", "mix"):
        r.pop(k, None)
    cap = r.get("captions") or {}
    for k in CAPTION_LOOK:
        cap.pop(k, None)
    if isinstance(cap.get("highlight"), str):
        cap.pop("highlight")
    sd = preset.get("scenes") or {}
    for b in r.get("beats") or []:
        if b.get("type") == "scene":
            for f in SCENE_LOOK:
                if f in (sd.get(b.get("kind")) or {}) or (f == "in" and "default_in" in sd):
                    b.pop(f, None)
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("name")
    ap.add_argument("--about")
    ap.add_argument("--best-for")
    ap.add_argument("--base", help="closest preset to start from (default: the reel's style, else clean)")
    ap.add_argument("--skill", default=DEFAULT_SKILL, help="skill to read presets from")
    ap.add_argument("--out-skill", help="skill dir to write into (default: --skill)")
    ap.add_argument("--music-auto", action="store_true", help="tag the bed in library/music/manifest.json and use music.id auto")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify-on", help="another project to build (and snapshot) in the new style")
    ap.add_argument("--verify-dir", help="where the verify copies go (default <out-skill>/../style-verify)")
    ap.add_argument("--render", action="store_true", help="with --verify-on: full render instead of snapshots")
    a = ap.parse_args()

    name = a.name
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", name):
        sys.exit("style name: lowercase letters, digits and dashes")
    skill = os.path.abspath(os.path.expanduser(a.skill))
    out_skill = os.path.abspath(os.path.expanduser(a.out_skill or a.skill))
    builtin = {"clean", "editorial", "meme", "cinematic", "launch", "kinetic", "pop"}
    target = os.path.join(out_skill, "styles", f"{name}.json")
    if name in builtin or (os.path.exists(target) and not a.force):
        sys.exit(f"style '{name}' already exists ({target}); pick another name or --force")
    pr = load_project(a.project, skill)
    # did it work?
    rp = os.path.join(pr.path, "build", "render-report.json")
    if not os.path.exists(os.path.join(pr.path, "build", "reel.mp4")) and not a.force:
        sys.exit("no build/reel.mp4: save a style from a reel that rendered and worked (or --force)")
    if os.path.exists(rp) and json.load(open(rp)).get("summary", {}).get("status") == "fail" and not a.force:
        sys.exit("the last render report failed; fix the reel first (or --force)")
    # the reel's own preset is the closest one; a reel with no style ran on build.mjs defaults, so it
    # starts from nothing (a base it never used would leak keys such as sfxProfile into the look)
    base_name = a.base or pr.raw.get("style")
    bp = os.path.join(skill, "styles", f"{base_name}.json") if base_name else ""
    base = json.load(open(bp)) if bp and os.path.exists(bp) else {}
    base["_name"] = base_name
    proj_rel = pr.path.replace(os.path.expanduser("~"), "~")
    preset, sig = derive_preset(pr, base, name, a.about, proj_rel)
    if a.music_auto and isinstance(preset.get("music"), dict) and preset["music"].get("id") not in (None, "auto"):
        bed = preset["music"]["id"]
        preset["music"] = {**preset["music"], "id": "auto"}
    else:
        bed = None
    example = example_from(pr.raw, preset, name)
    row = styles_row(name, preset, sig, a.best_for)
    print(json.dumps(preset, indent=1, ensure_ascii=False))
    print("\nstyles.md row:\n" + row)
    if a.dry_run:
        return

    os.makedirs(os.path.dirname(target), exist_ok=True)
    json.dump(preset, open(target, "w"), indent=1, ensure_ascii=False)
    ex_path = os.path.join(out_skill, "examples", "gallery", f"{name}.reel.json")
    os.makedirs(os.path.dirname(ex_path), exist_ok=True)
    json.dump(example, open(ex_path, "w"), indent=1, ensure_ascii=False)
    md = os.path.join(out_skill, "references", "styles.md")
    if os.path.exists(md):
        add_row(md, row, name)
    if bed:
        mp = os.path.join(out_skill, "library", "music", "manifest.json")
        man = json.load(open(mp))
        st = man[bed].setdefault("styles", [])
        if name not in st:
            st.append(name)
        json.dump(man, open(mp, "w"), indent=1, ensure_ascii=False)
        print(f"tagged music '{bed}' with style '{name}' in {mp}")
    print(f"\n-> {target}\n-> {ex_path}\n-> {md} (row added)")

    # round trip: example + new preset == original reel
    vdir = os.path.abspath(a.verify_dir or os.path.join(out_skill, "..", "style-verify"))
    os.makedirs(vdir, exist_ok=True)
    orig = copy_project(pr.path, os.path.join(vdir, f"{name}-orig"), pr.raw)
    rt = copy_project(pr.path, os.path.join(vdir, f"{name}-roundtrip"), example)
    c1, l1 = build(out_skill, orig)
    c2, l2 = build(out_skill, rt)
    same_html = c1 == 0 and c2 == 0 and normalise(open(os.path.join(orig, "index.html")).read()) == normalise(open(os.path.join(rt, "index.html")).read())
    e1 = json.load(open(os.path.join(orig, "build", "sfx_events.json")))["events"] if c1 == 0 else None
    e2 = json.load(open(os.path.join(rt, "build", "sfx_events.json")))["events"] if c2 == 0 else None
    same_sfx = e1 == e2 and e1 is not None
    if bed:  # music auto picks the first bed tagged with the style; equal when the tag is the only one
        same_html = same_html or (c2 == 0 and "music-bed" in open(os.path.join(rt, "index.html")).read())
    print(f"round trip (example + preset vs the original reel.json): index.html {'identical' if same_html else 'DIFFERENT'}, "
          f"SFX events {'identical' if same_sfx else 'DIFFERENT'}")
    if not (same_html and same_sfx):
        print((l2 if c2 else l1)[-1500:])
        sys.exit(1)

    if a.verify_on:
        other = load_project(a.verify_on, out_skill)
        rs = restyle(other.raw, preset, name)
        vp = copy_project(other.path, os.path.join(vdir, f"{name}-on-{os.path.basename(other.path)}"), rs)
        code, log = build(out_skill, vp)
        warn = re.search(r"\nWARNINGS:\n((?:  .*\n?)+)", log)
        print(f"\nverify: {os.path.basename(other.path)} in '{name}' built {'OK' if code == 0 else 'FAILED'}" + (f"; warnings:\n{warn.group(1)}" if warn else ""))
        if code:
            print(log[-1500:])
            sys.exit(1)
        lint = sh(hf("lint", "--json"), cwd=vp)
        try:
            lj = json.loads(lint.stdout[lint.stdout.index("{"):])
            print(f"lint: {lj.get('errorCount')} errors")
        except ValueError:
            pass
        vb = load_project(vp, out_skill)
        bts = [b for b in beats_timeline(vb) if b["t0"] is not None]
        # one frame of the speaker with captions (outside any full-screen beat), then three beats fully built
        full = [(b["t0"], b["t1"]) for b in bts if b["full"]]
        spk = next((t / 2 for t in range(2, int(vb.total * 2)) if not any(x - 0.3 <= t / 2 <= y + 0.5 for x, y in full)), 1.0)
        built = lambda b: min((b["moments"][-1] + 0.45) if b["moments"] else b["t0"] + 0.8, b["t1"] - 0.15)  # noqa: E731
        times = sorted({round(spk + 0.4, 2)} | {round(built(b), 2) for b in bts[:3]})
        if a.render:
            r = sh(hf("render", "-o", "build/reel.mp4", "--quiet"), cwd=vp, timeout=7200)
            print("render", "OK" if r.returncode == 0 else "FAILED", os.path.join(vp, "build", "reel.mp4"))
        else:
            for label, proj in (("own look", other.path), (name, vp)):
                outd = os.path.join(vdir, f"{name}-on-{os.path.basename(other.path)}-frames", label.replace(" ", "-"))
                os.makedirs(outd, exist_ok=True)
                r = sh(hf("snapshot", proj, "--at", ",".join(map(str, times)), "-o", outd, "--describe", "false", "--no-end"), cwd=proj, timeout=1800)
                print(f"snapshots ({label}): {outd}" + ("" if r.returncode == 0 else " FAILED " + r.stderr[-300:]))


if __name__ == "__main__":
    main()
