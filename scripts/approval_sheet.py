#!/usr/bin/env python3
"""Approval gate before the slow render: one self-contained HTML page per build.

    approval_sheet.py <project> [--upstream build/edl_map.json] [--frames snapshot|draft|video:<file>]
                      [--out build/approval.html] [--no-build] [--no-lint] [--taste taste.json] [--open]
    approval_sheet.py <project> --mark-approved        # record the user's yes for the current build

It (re)builds the project with build.mjs (fast, keeps stdout as build/build.log), lints it, runs the
taste checks, then captures a frame at every moment the user has to judge:
  the opening frame, the 1.5 s hook frame, just after every visible cut (take boundaries and, with an
  upstream cut list, the cuts inside a pre-cut source), each beat as it lands and when it is fully built,
  and the end frame.
Frames come from `npx hyperframes snapshot --at ...` (default, no render needed), from a fast draft render
(`--frames draft`), or from any existing video (`--frames video:build/reel.mp4`).

The page holds: the contact sheet (edit time, original time, caption on screen, beat text, sounds), the
edit timeline (takes with original times, beats, captions, SFX, zoom), the caption text and fixes, the SFX
table, and every warning (build, lint, taste, sheet checks). Flag frames and type notes on the page; "Copy
change list" puts a ready-to-paste message on the clipboard. Writes build/approval.html and
build/approval.json (frame plan, warnings, build hash).
"""
import argparse
import base64
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from plat import npx, venv_python, open_path  # noqa: E402
from reelproj import (beats_timeline, caption_at, caption_groups, fmt_t, load_project,  # noqa: E402
                      parse_build_log, predicted_silences, run_build, sh, take_words, taste_mjs)

esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def build_hash(proj):
    h = hashlib.sha1()
    for f in ("reel.json", "index.html"):
        p = os.path.join(proj, f)
        if os.path.exists(p):
            h.update(open(p, "rb").read())
    return h.hexdigest()[:10]


# ---------------------------------------------------------------- frame plan
def plan_frames(pr, beats, max_frames=60):
    # build.mjs hides captions under scenes and textfx blocks (unless captions: true); B-roll keeps them on top
    hidden = [(b["t0"], b["t1"]) for b in beats if b["t0"] is not None and b["type"] in ("scene", "textfx") and not b.get("captions_on")]
    full = [(b["t0"], b["t1"], b) for b in beats if b["t0"] is not None and b["full"]]
    ms = [{"t": 0.05, "tags": ["open"], "prio": 0}, {"t": 1.5, "tags": ["hook 1.5 s"], "prio": 0}]
    under = []
    for n, c in enumerate(pr.cuts(), 1):
        cover = next((b for a, z, b in full if a - 0.05 <= c["t"] <= z + 0.05), None)
        if cover:
            under.append((n, c, cover))
            continue
        lab = f"cut {n}" + (" (in source)" if c["kind"] == "upstream" else "")
        ms.append({"t": round(c["t"] + 0.12, 3), "tags": [lab], "prio": 2, "cut": c})
    for b in beats:
        if b["t0"] is None:
            continue
        t0, t1 = b["t0"], b["t1"]
        d = t1 - t0
        first = [m for m in b["moments"] if m > t0 + 0.05]
        land = min(first[0] + 0.3, t1 - 0.1) if first else t0 + min(0.5, 0.4 * d)
        ms.append({"t": round(land, 3), "tags": [f"#{b['i']} {b['label']}"], "prio": 1, "beat": b["i"]})
        if b["moments"]:
            built = min(max(b["moments"]) + 0.35, t1 - 0.12)
        else:
            built = t1 - 0.3
        if d > 1.6 and built - land > 0.6:
            ms.append({"t": round(built, 3), "tags": [f"#{b['i']} {b['label']} built"], "prio": 1, "beat": b["i"]})
    ms.append({"t": round(max(0.0, pr.total - 0.06), 3), "tags": ["end"], "prio": 0})
    ms = [m for m in ms if 0 <= m["t"] <= pr.total]
    ms.sort(key=lambda m: m["t"])
    merged = []
    for m in ms:
        if merged and m["t"] - merged[-1]["t"] < 0.3:
            merged[-1]["tags"] += m["tags"]
            merged[-1]["prio"] = min(merged[-1]["prio"], m["prio"])
            continue
        merged.append(dict(m))
    if len(merged) > max_frames:  # keep opens/ends and beats, thin the cuts evenly
        keep = [m for m in merged if m["prio"] < 2]
        cuts = [m for m in merged if m["prio"] == 2]
        room = max(0, max_frames - len(keep))
        step = len(cuts) / room if room else 1e9
        keep += [cuts[int(i * step)] for i in range(room)] if room else []
        merged = sorted(keep, key=lambda m: m["t"])
    return merged, hidden, under


# ---------------------------------------------------------------- capture
def capture_snapshot(pr, times, tmp, jobs=3):
    """`hyperframes snapshot --at` in `jobs` parallel browser sessions (frames interleaved so each job seeks forward)."""
    jobs = max(1, min(jobs, len(times)))
    parts = [list(range(j, len(times), jobs)) for j in range(jobs)]
    procs = []
    for j, idx in enumerate(parts):
        d = os.path.join(tmp, f"j{j}")
        os.makedirs(d)
        at = ",".join(f"{times[i]:.3f}" for i in idx)
        procs.append((idx, d, subprocess.Popen(npx("hyperframes", "snapshot", pr.path, "--at", at, "-o", d, "--describe", "false", "--no-end"),
                                               cwd=pr.path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")))
    out = [None] * len(times)
    for idx, d, p in procs:
        log = p.communicate(timeout=1800)[0]
        files = sorted(f for f in os.listdir(d) if re.match(r"frame-\d+-at-.*\.png$", f))
        if len(files) != len(idx):  # a busy machine can time out a browser session: retry this part alone
            print(f"  snapshot part {d[-2:]} failed ({log.strip().splitlines()[-1][:120] if log.strip() else '?'}); retrying alone")
            shutil.rmtree(d)
            os.makedirs(d)
            at = ",".join(f"{times[i]:.3f}" for i in idx)
            r = sh(npx("hyperframes", "snapshot", pr.path, "--at", at, "-o", d, "--describe", "false", "--no-end", "--timeout", "20000"), cwd=pr.path, timeout=1800)
            files = sorted(f for f in os.listdir(d) if re.match(r"frame-\d+-at-.*\.png$", f))
            if len(files) != len(idx):
                raise RuntimeError(f"snapshot returned {len(files)} of {len(idx)} frames; try --jobs 1 or --frames video:<render>\n{(r.stdout + r.stderr)[-600:]}")
        for f in files:
            out[idx[int(re.match(r"frame-(\d+)-", f).group(1))]] = os.path.join(d, f)
    return out


def capture_video(video, times, tmp):
    out = []
    for i, t in enumerate(times):
        p = os.path.join(tmp, f"v{i:03d}.png")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-update", "1", p])
        out.append(p)
    return out


def to_b64_jpeg(png, w=450):
    jp = png + ".jpg"
    sh(["ffmpeg", "-v", "error", "-y", "-i", png, "-vf", f"scale={w}:-2", "-q:v", "4", "-update", "1", jp])
    if not os.path.exists(jp):
        return None
    return base64.b64encode(open(jp, "rb").read()).decode()


# ---------------------------------------------------------------- cover
def make_cover(pr, tmp):
    """reel.json `cover`: {"headline": "A|B|*C*", "at": <original s>, "colors", "accent", "stroke", "coverScale", "model"}
    -> build/cover-9x16.jpg (Reels cover) + build/cover-16x9.jpg (YouTube) via scripts/cutout_fx.py thumb (matte venv;
    cached by its sidecar build/cover.json). `at` omitted = the sharpest still frame of the first 4 s of take 0.
    Returns ([(label, base64 jpeg)], warning or None)."""
    cv = pr.spec.get("cover")
    if not cv:
        return [], None
    cv = {"headline": cv} if isinstance(cv, str) else cv
    if not cv.get("headline"):
        return [], "cover: needs a headline (words the speaker says; 'A|B|*C*', *line* = accent box)"
    py = venv_python(os.environ.get("MATTE_VENV") or "~/.venvs/ghost-matte")
    if not os.path.exists(py):
        return [], f"cover: the matte venv is missing (bash {os.path.join(pr.skill, 'scripts', 'setup_matte.sh')}); no cover made"
    look = pr.spec.get("look") or {}
    src = (look.get("plate") or "assets/talk.film.mp4") if look.get("film") else pr.spec["source"]
    if cv.get("at") is not None:
        at = float(cv["at"])
        ss, t = max(0.0, at - 1.0), 2.0
    else:
        k = pr.spec["takes"][0]
        at, ss, t = None, float(k["a"]), min(4.0, float(k["b"]) - float(k["a"]))
    args = [py, os.path.join(pr.skill, "scripts", "cutout_fx.py"), "thumb", os.path.join(pr.path, src), "--ss", f"{ss:.3f}", "--t", f"{t:.3f}",
            "--headline", str(cv["headline"]), "-o", os.path.join(pr.path, "build", "cover"), "--model", cv.get("model", "lite@1024")]
    if at is not None:
        args += ["--at", f"{at:.3f}"]
    for k, flag in (("colors", "--colors"), ("accent", "--accent"), ("stroke", "--stroke"), ("coverScale", "--cover-scale")):
        if cv.get(k) is not None:
            args += [flag, str(cv[k])]
    print("cover (cutout_fx.py thumb)...")
    r = sh(args, timeout=1800)
    out = []
    for tag in ("9x16", "16x9"):
        f = os.path.join(pr.path, "build", f"cover-{tag}.jpg")
        if r.returncode == 0 and os.path.exists(f):
            jp = os.path.join(tmp, f"cover-{tag}.jpg")
            sh(["ffmpeg", "-v", "error", "-y", "-i", f, "-vf", "scale=-2:420", "-q:v", "3", "-update", "1", jp])
            if os.path.exists(jp):
                out.append((f"build/cover-{tag}.jpg", base64.b64encode(open(jp, "rb").read()).decode()))
    if r.returncode != 0 or len(out) < 2:
        return out, "cover: cutout_fx.py thumb failed: " + (r.stderr or r.stdout or "")[-300:]
    return out, None


# ---------------------------------------------------------------- checks
def lint(pr):
    r = sh(npx("hyperframes", "lint", "--json"), cwd=pr.path, timeout=300)
    try:
        j = json.loads(r.stdout[r.stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return {"ok": False, "errorCount": None, "warningCount": None, "findings": [], "raw": (r.stdout + r.stderr)[-600:]}
    return j


BENIGN_LINT = {"composition_file_too_large", "timeline_track_too_dense", "nested_structure_needs_subcomposition"}


def taste_check(pr, taste_path):
    cmd = ["node", taste_mjs(), "check", pr.path, "--skill", pr.skill, "--json"]
    if taste_path:
        cmd += ["--taste", taste_path]
    r = sh(cmd)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def taste_process_rules(taste_file):
    if not taste_file or not os.path.exists(taste_file):
        return []
    t = json.load(open(taste_file, encoding="utf-8"))
    return [r for r in t.get("rules", []) if r.get("active", True) and r.get("kind") == "process"]


def sheet_checks(pr, beats, groups, hidden):
    out = []
    for b in beats:
        if b.get("error"):
            out.append(("error", f"beat #{b['i']} {b['label']}: {b['error']}"))
    first_word = pr.words_edit[0]["start"] if pr.words_edit else None
    first_cap = min((g["t0"] for g in groups), default=None)
    first_beat = min((b["t0"] for b in beats if b["t0"] is not None and b["texts"]), default=None)
    first_text = min([x for x in (first_cap, first_beat) if x is not None], default=None)
    if first_text is None or first_text > 1.5:
        out.append(("warn", f"no text on screen in the first 1.5 s (first text at {fmt_t(first_text)}); start captions at 0 or open on a hook card"))
    else:
        out.append(("ok", f"text on screen at {first_text:.2f} s (hook check: by 1.5 s)"))
    if first_word is not None and first_word > 0.5:
        out.append(("warn", f"the voice starts at {first_word:.2f} s; trim take 0 'a' to about {pr.takes[0].a + first_word - 0.1:.2f}"))
    for a, b in predicted_silences(pr):
        orig, ti, _ = pr.to_orig(a)
        out.append(("warn", f"a {b - a:.2f} s pause at {fmt_t(a)} (take {ti}, orig {orig:.2f} s) will play as dead air; "
                            f"cut pauses over 0.7 s inside a line, or leave it as a hold on purpose"))
    modes = {}
    for g in (pr.layout or {}).get("blocks", []):
        modes[g["mode"]] = modes.get(g["mode"], 0) + 1
    if modes.get("lower-face"):
        out.append(("warn", f"{modes['lower-face']} caption block(s) in the close-up fallback (on a backing under the mouth)"))
    if pr.layout:
        st, sb = pr.layout.get("safeTop", 0), pr.layout.get("safeBottom", 1920)
        off = [g for g in pr.layout.get("blocks", []) if g["y"] < st or g["y"] + g["h"] * g.get("scale", 1) > sb + 1]
        if off:
            out.append(("error", f"{len(off)} caption block(s) outside the platform safe area ({st}-{sb})"))
    cov = sum(min(b["t1"], pr.total) - b["t0"] for b in beats if b["t0"] is not None and b["full"])
    out.append(("ok", f"full-screen scenes cover {100 * cov / max(pr.total, 1):.0f}% of the runtime"))
    return out


# ---------------------------------------------------------------- page
ROLE_COL = {"ui": "#9aa3b2", "whoosh": "#5aa9ff", "impact": "#ff9f43", "meme": "#ff5c9a"}
TYPE_COL = {"scene": "accent", "broll": "#a78bfa", "big": "#2dd4bf", "chips": "#2dd4bf", "strike": "#2dd4bf", "quote": "#2dd4bf",
            "list": "#2dd4bf", "emoji": "#fbbf24", "logo": "#fbbf24", "meme": "#fb7185", "endcard": "#e5e7eb", "title": "#38bdf8", "behind": "#f472b6"}


def timeline_svg(pr, beats, groups, frames, hidden, accent):
    W, L = 1000.0, 46.0
    T = max(pr.total, 0.1)
    X = lambda t: L + (W - L - 8) * (t / T)  # noqa: E731
    rows = {"takes": 22, "beats": 62, "caps": 98, "sfx": 124, "zoom": 156, "music": 180}
    s = [f'<svg viewBox="0 0 {W:.0f} 200" class="tl" role="img" aria-label="edit timeline">']
    for name, y in rows.items():
        s.append(f'<text x="4" y="{y + 12}" class="lane">{name}</text>')
    step = 5 if T <= 75 else 10
    t = 0
    while t <= T + 1e-6:
        s.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="14" y2="196" class="grid"/><text x="{X(t) + 2:.1f}" y="11" class="tick">{int(t)}s</text>')
        t += step
    for k in pr.takes:
        cls = "take0" if k.i % 2 == 0 else "take1"
        s.append(f'<rect x="{X(k.start):.1f}" y="{rows["takes"]}" width="{max(1, X(k.start + k.dur) - X(k.start)):.1f}" height="18" class="{cls}"><title>take {k.i}: orig {k.a:.2f}-{k.b:.2f} s</title></rect>')
        if k.hold:
            s.append(f'<rect x="{X(k.hold_start):.1f}" y="{rows["takes"]}" width="{X(k.hold_start + k.hold) - X(k.hold_start):.1f}" height="18" class="hold"><title>hold {k.hold:.2f} s</title></rect>')
    if pr.outro:
        s.append(f'<rect x="{X(pr.speech):.1f}" y="{rows["takes"]}" width="{X(pr.total) - X(pr.speech):.1f}" height="18" class="hold"><title>outro {pr.outro} s</title></rect>')
    for j, u in enumerate(pr.upstream):
        te = pr.E_safe(u["start"])
        if te is not None and j:
            s.append(f'<line x1="{X(te):.1f}" x2="{X(te):.1f}" y1="{rows["takes"] - 2}" y2="{rows["takes"] + 20}" class="ucut"><title>cut in source: raw {u["a"]:.2f} s</title></line>')
    for i, b in enumerate([b for b in beats if b["t0"] is not None]):
        col = TYPE_COL.get(b["type"], "#9ca3af")
        col = accent if col == "accent" else col
        y = rows["beats"] + (i % 2) * 12
        w = max(2, X(b["t1"]) - X(b["t0"]))
        s.append(f'<a href="#beat{b["i"]}"><rect x="{X(b["t0"]):.1f}" y="{y}" width="{w:.1f}" height="11" rx="2" fill="{col}" opacity=".9"><title>#{b["i"]} {esc(b["label"])} {b["t0"]:.2f}-{b["t1"]:.2f} s: {esc(" / ".join(b["texts"])[:120])}</title></rect></a>')
        if w > 46:
            s.append(f'<text x="{X(b["t0"]) + 3:.1f}" y="{y + 9}" class="blab">{esc(b["label"].replace("scene · ", ""))}</text>')
    for g in groups:
        dim = any(a <= g["t0"] < z for a, z in hidden)
        s.append(f'<rect x="{X(g["t0"]):.1f}" y="{rows["caps"]}" width="{max(1, X(g["t1"]) - X(g["t0"]) - 0.6):.1f}" height="14" class="cap{" capdim" if dim else ""}"><title>{fmt_t(g["t0"])} {esc(g["text"])}</title></rect>')
    for e in (pr.sfx or {}).get("events", []):
        h = 6 + 18 * min(1.0, e.get("vol", 0.2) / 0.5)
        s.append(f'<line x1="{X(e["t"]):.1f}" x2="{X(e["t"]):.1f}" y1="{rows["sfx"] + 24 - h:.1f}" y2="{rows["sfx"] + 24}" stroke="{ROLE_COL.get(e["role"], "#ccc")}" stroke-width="2"><title>{e["t"]:.2f} s {esc(e["id"])} ({esc(e["role"])}, {esc(e["why"])})</title></line>')
    z = pr.spec.get("zoom") or {}
    for t_, zz in z.get("snaps", []) or []:
        te = pr.E_safe(t_)
        if te is not None:
            s.append(f'<path d="M{X(te):.1f} {rows["zoom"]} l5 7 l-5 7 l-5 -7z" class="snap"><title>snap x{zz} at {te:.2f} s</title></path>')
    for p in z.get("pushes", []) or []:
        a = pr.E_safe(p.get("at"))
        bb = pr.total if p.get("until") == "end" else pr.E_safe(p.get("until"))
        if a is not None and bb is not None:
            s.append(f'<path d="M{X(a):.1f} {rows["zoom"] + 14} L{X(a + p.get("up", 0.4)):.1f} {rows["zoom"] + 2} L{X(bb):.1f} {rows["zoom"] + 2} L{X(bb + p.get("down", 0)):.1f} {rows["zoom"] + 14}" class="push"><title>push x{p.get("z")} {a:.2f}-{bb:.2f} s</title></path>')
    m = pr.spec.get("music")
    if m:
        s.append(f'<rect x="{X(0):.1f}" y="{rows["music"]}" width="{X(T) - X(0):.1f}" height="10" rx="5" class="music"><title>music {esc(m.get("id") or m.get("src"))} at {m.get("db", -20)} dB under the voice</title></rect>')
        s.append(f'<text x="{X(0) + 6:.1f}" y="{rows["music"] + 8}" class="blab">{esc(m.get("id") or os.path.basename(str(m.get("src"))))} · {m.get("db", -20)} dB</text>')
    for n, f in enumerate(frames):
        s.append(f'<a href="#f{n}"><circle cx="{X(f["t"]):.1f}" cy="{rows["caps"] - 6}" r="3.2" class="fdot"><title>frame {n + 1} at {fmt_t(f["t"])}</title></circle></a>')
    s.append("</svg>")
    return "".join(s)


CSS = """
:root{--bg:#0d0f13;--panel:#151820;--panel2:#1b1f29;--line:#272c38;--ink:#e9ebf0;--mute:#9aa1b0;--faint:#6b7280;
--ok:#34d399;--warn:#fbbf24;--err:#f87171;--info:#60a5fa;--acc:ACCENT}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Inter","Segoe UI",Roboto,sans-serif}
a{color:inherit}main{max-width:1240px;margin:0 auto;padding:28px 16px 80px}
h1{font-size:26px;line-height:1.2;margin:0 0 4px;letter-spacing:-.3px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.12em;color:var(--mute);margin:40px 0 12px;font-weight:600}
.sub{color:var(--mute);font-size:13px}.mono{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:12.5px}
.top{display:grid;grid-template-columns:1fr 340px;gap:20px;align-items:start}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
.stat b{display:block;font-size:18px;font-weight:650}.stat span{color:var(--mute);font-size:12px}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:6px;background:var(--acc)}
.gate{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
.gate h3{margin:0 0 6px;font-size:16px}.gate p{margin:0 0 12px;color:var(--mute);font-size:13px}
.btn{appearance:none;border:1px solid var(--line);background:var(--panel2);color:var(--ink);border-radius:10px;padding:9px 14px;font:inherit;font-weight:600;cursor:pointer;margin:0 6px 6px 0}
.btn.go{background:var(--ok);color:#06281b;border-color:transparent}.btn:hover{filter:brightness(1.12)}
textarea{width:100%;min-height:64px;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:8px;font:inherit;font-size:13px;resize:vertical}
.warns{display:grid;gap:6px}.w{display:grid;grid-template-columns:62px 1fr;gap:10px;background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--faint);border-radius:8px;padding:8px 12px;font-size:13.5px}
.w .k{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);padding-top:2px}
.w.error{border-left-color:var(--err)}.w.error .k{color:var(--err)}.w.warn{border-left-color:var(--warn)}.w.warn .k{color:var(--warn)}
.w.ok{border-left-color:var(--ok)}.w.ok .k{color:var(--ok)}.w.info{border-left-color:var(--info)}.w.info .k{color:var(--info)}
.w .said{color:var(--mute);font-size:12.5px;margin-top:2px}.w .src{color:var(--faint);font-size:11.5px}
.check{display:flex;gap:10px;align-items:flex-start;padding:6px 0;font-size:13.5px}.check input{margin-top:3px;accent-color:var(--ok)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(212px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card.flag{border-color:var(--err);box-shadow:0 0 0 1px var(--err)}
.shot{position:relative;aspect-ratio:9/16;background:#000;cursor:zoom-in}.shot img{width:100%;height:100%;object-fit:cover;display:block}
.tc{position:absolute;left:8px;top:8px;background:rgba(0,0,0,.72);border-radius:6px;padding:2px 7px;font:600 12px ui-monospace,Menlo,monospace}
.num{position:absolute;right:8px;top:8px;background:rgba(0,0,0,.72);border-radius:6px;padding:2px 7px;font-size:11px;color:var(--mute)}
.meta{padding:9px 11px 11px;font-size:12.5px;display:grid;gap:5px}.tags{display:flex;flex-wrap:wrap;gap:4px}
.tag{font-size:11px;font-weight:600;padding:1px 7px;border-radius:999px;background:var(--panel2);border:1px solid var(--line)}
.tag.cut{color:#fca5a5}.tag.beat{color:#93c5fd}.tag.open{color:#86efac}
.cap{color:var(--ink)}.cap:before{content:"CC ";color:var(--faint);font-size:10px;font-weight:700}
.bt{color:#c7d2fe}.sx{color:var(--mute)}.orig{color:var(--faint)}
.fl{display:flex;gap:6px;align-items:center;margin-top:3px}.fl input[type=text]{flex:1;min-width:0;background:var(--bg);border:1px solid var(--line);color:var(--ink);border-radius:7px;padding:4px 7px;font:inherit;font-size:12px}
.fl label{font-size:11.5px;color:var(--mute);display:flex;gap:4px;align-items:center;white-space:nowrap}
.tlwrap{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;overflow-x:auto}
.tl{width:100%;min-width:860px;display:block}.tl .lane{fill:var(--faint);font-size:10px}.tl .tick{fill:var(--faint);font-size:9px}
.tl .grid{stroke:#232836;stroke-width:1}.tl .take0{fill:#2b3242}.tl .take1{fill:#3a4357}.tl .hold{fill:#5b4a2a}.tl .ucut{stroke:#fca5a5;stroke-width:1}
.tl .blab{fill:#0b0d12;font-size:8.5px;font-weight:700}.tl .cap{fill:#4b5563}.tl .capdim{fill:#2a2f3a}.tl .snap{fill:#fbbf24}.tl .push{fill:none;stroke:#fbbf24;stroke-width:1.5}
.tl .music{fill:#334155}.tl .music+text{fill:#cbd5e1}.tl .fdot{fill:var(--ink);opacity:.8}
.legend{display:flex;flex-wrap:wrap;gap:12px;color:var(--mute);font-size:12px;margin-top:8px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--mute);font-weight:600;font-size:12px;background:var(--panel2)}
tr.sub td{color:var(--mute);font-size:12px;padding-top:4px;padding-bottom:4px}tr.sub td:first-child{padding-left:22px}
.t{white-space:nowrap;font-family:ui-monospace,Menlo,monospace;font-size:12px}
.capflow{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;line-height:2}
.cb{display:inline;padding:2px 4px;border-radius:5px}.cb small{color:var(--faint);font:11px ui-monospace,Menlo,monospace;margin-right:4px}
.cb.hid{opacity:.45}.fix{display:inline-block;background:var(--panel2);border:1px solid var(--line);border-radius:7px;padding:2px 8px;margin:0 6px 6px 0;font-size:12.5px}
details{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 14px}details summary{cursor:pointer;color:var(--mute)}
details table{border:0;margin-top:8px}
.lb{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;align-items:center;justify-content:center;z-index:9;cursor:zoom-out}.lb img{max-height:94vh;max-width:94vw;border-radius:8px}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--ok);color:#06281b;font-weight:700;padding:10px 16px;border-radius:10px;display:none;z-index:10}
footer{color:var(--faint);font-size:12px;margin-top:40px}
@media (max-width:820px){.top{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}}
"""

JS = """
const KEY='approval:'+document.body.dataset.hash;
const st=(()=>{try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){return {}}})();
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};
document.querySelectorAll('.card').forEach(c=>{const id=c.id,f=c.querySelector('input[type=checkbox]'),n=c.querySelector('input[type=text]');
 if(st[id]){f.checked=!!st[id].f;n.value=st[id].n||'';c.classList.toggle('flag',f.checked)}
 const up=()=>{st[id]={f:f.checked,n:n.value};c.classList.toggle('flag',f.checked||!!n.value);save()};f.onchange=up;n.oninput=up;});
const g=document.getElementById('gnote');if(st._g)g.value=st._g;g.oninput=()=>{st._g=g.value;save()};
document.querySelectorAll('.shot').forEach(s=>s.onclick=()=>{const lb=document.getElementById('lb');lb.querySelector('img').src=s.querySelector('img').src;lb.style.display='flex'});
document.getElementById('lb').onclick=e=>e.currentTarget.style.display='none';
function copy(t){const done=()=>{const x=document.getElementById('toast');x.style.display='block';setTimeout(()=>x.style.display='none',1800)};
 if(navigator.clipboard&&window.isSecureContext!==false){navigator.clipboard.writeText(t).then(done,()=>fb(t,done))}else fb(t,done)}
function fb(t,done){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();try{document.execCommand('copy')}catch(e){}a.remove();done()}
const head=document.body.dataset.title+' (build '+document.body.dataset.hash+')';
document.getElementById('approve').onclick=()=>copy('APPROVED: '+head+'. Render it.'+(g.value?'\\nNote: '+g.value:''));
document.getElementById('changes').onclick=()=>{const L=['CHANGES for '+head+':'];
 document.querySelectorAll('.card').forEach(c=>{const f=c.querySelector('input[type=checkbox]').checked,n=c.querySelector('input[type=text]').value;
  if(f||n)L.push('- '+c.dataset.ref+': '+(n||'(flagged)'))});if(g.value)L.push('- general: '+g.value);
 if(L.length==1)L.push('- (nothing flagged; type a note or flag a frame)');copy(L.join('\\n'))};
"""


def page(pr, frames, imgs, beats, groups, hidden, under, warns, lint_j, taste_j, process, info, hsh, method, took, covers=()):
    spec = pr.spec
    accent = (spec.get("brand") or {}).get("accent", "#D13F34")
    title = spec.get("title") or os.path.basename(pr.path)
    sfx = (pr.sfx or {}).get("events", [])
    by_role = {}
    for e in sfx:
        by_role[e["role"]] = by_role.get(e["role"], 0) + 1
    cuts = pr.cuts()
    ncov = sum(min(b["t1"], pr.total) - b["t0"] for b in beats if b["t0"] is not None and b["full"])
    errs = [w for w in warns if w[0] == "error"]
    o = []
    o.append(f'<main><div class="top"><div><div class="sub">approval sheet · {esc(os.path.basename(pr.path))} · build {hsh}</div><h1>{esc(title)}</h1>')
    o.append(f'<div class="sub mono">{esc(pr.path)}</div><div class="stats">')
    stats = [(fmt_t(pr.total), "duration"), (str(len(pr.takes)), "takes"), (str(len(cuts)), "visible cuts"),
             (str(len([b for b in beats if b["t0"] is not None])), "beats"), (f"{100 * ncov / max(pr.total, 1):.0f}%", "full-screen scenes"),
             (f"{len(sfx)}", f"SFX · {60 * len(sfx) / max(pr.total, 1):.0f}/min"), (str(len(groups)), "caption blocks")]
    for v, k in stats:
        o.append(f'<div class="stat"><b>{esc(v)}</b><span>{esc(k)}</span></div>')
    o.append(f'<div class="stat"><b><i class="sw"></i>{esc(spec.get("style") or "custom")}</b><span>style · {esc(accent)}</span></div>')
    m = spec.get("music")
    o.append(f'<div class="stat"><b>{esc((m or {}).get("id") or (m or {}).get("src") or "none")}</b><span>music bed</span></div></div></div>')
    verdict = "Fix the errors before rendering." if errs else "Looks renderable. Check every frame, then approve."
    o.append(f'<div class="gate"><h3>{"Blocked" if errs else "Ready for your yes"}</h3><p>{esc(verdict)} Flag a frame or type a note on it, then copy the change list into chat. Nothing renders until you approve.</p>'
             f'<button class="btn go" id="approve">Approve and copy</button><button class="btn" id="changes">Copy change list</button>'
             f'<textarea id="gnote" placeholder="General note (optional)"></textarea></div></div>')
    if covers:  # reel.json `cover` (cutout_fx.py thumb): the Reels cover and the YouTube thumbnail, approved with the frames
        o.append("<h2>Cover</h2><div style='display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap'>")
        for label, b64 in covers:
            o.append(f'<figure style="margin:0"><img alt="{esc(label)}" style="height:420px;border-radius:10px;display:block" src="data:image/jpeg;base64,{b64}">'
                     f'<figcaption class="sub mono">{esc(label)}</figcaption></figure>')
        o.append("</div>")

    # warnings
    o.append("<h2>Warnings</h2><div class='warns'>")
    order = {"error": 0, "warn": 1, "info": 2, "ok": 3}
    for sev, msg, *extra in sorted(warns, key=lambda w: order.get(w[0], 9)):
        said = f'<div class="said">{esc(extra[0])}</div>' if extra and extra[0] else ""  # "you said: ..." or "skill rule: ..."
        src = f'<div class="src">{esc(extra[1])}</div>' if len(extra) > 1 and extra[1] else ""
        o.append(f'<div class="w {sev}"><div class="k">{ {"ok": "ok", "warn": "warn", "error": "error", "info": "info"}[sev] }</div><div>{esc(msg)}{said}{src}</div></div>')
    o.append("</div>")
    if lint_j and lint_j.get("findings"):
        benign = [f for f in lint_j["findings"] if f.get("code") in BENIGN_LINT]
        other = [f for f in lint_j["findings"] if f.get("code") not in BENIGN_LINT and f.get("severity") != "error"]
        if benign or other:
            o.append(f'<details style="margin-top:8px"><summary>lint: {lint_j.get("errorCount")} errors, {lint_j.get("warningCount")} warnings ({len(benign)} are the known sub-composition/track-density ones)</summary><table>')
            for f in other + benign:
                o.append(f'<tr><td class="mono">{esc(f.get("code"))}</td><td>{esc(f.get("message"))}</td></tr>')
            o.append("</table></details>")

    # checklist
    o.append("<h2>Before you approve</h2><div class='gate' style='padding:10px 16px'>")
    items = [r["say"] for r in process] + ["Every card and scene lands on the word it shows.", "Nothing covers the eyes or mouth; captions sit inside the safe area.",
                                            "Names and numbers in captions are spelled right.", "The first frame and the 1.5 s frame would stop the scroll."]
    for i, s in enumerate(items):
        o.append(f'<label class="check"><input type="checkbox" class="ck" id="ck{i}"><span>{esc(s)}</span></label>')
    o.append("</div>")

    # contact sheet
    o.append(f"<h2>Contact sheet · {len(frames)} frames</h2><div class='grid'>")
    for n, (f, img) in enumerate(zip(frames, imgs)):
        orig, ti, kind = pr.to_orig(f["t"])
        raw, useg = pr.to_raw(orig) if kind == "take" else (None, None)
        on_scene = any(a <= f["t"] < z for a, z in hidden)
        cap = "" if on_scene else caption_at(groups, f["t"])
        act = [b for b in beats if b["t0"] is not None and b["t0"] - 0.01 <= f["t"] <= b["t1"]]
        near = [e for e in sfx if f["t"] - 0.6 <= e["t"] <= f["t"] + 0.15]
        ref = f"frame {n + 1} at {fmt_t(f['t'])} (orig {orig:.2f} s{', raw ' + format(raw, '.2f') + ' s' if raw is not None else ''})"
        tags = "".join(f'<span class="tag {"cut" if t.startswith("cut") else "beat" if t.startswith("#") else "open"}">{esc(t)}</span>' for t in f["tags"])
        o.append(f'<div class="card" id="f{n}" data-ref="{esc(ref)}"><div class="shot">' + (f'<img loading="lazy" alt="frame at {fmt_t(f["t"])}" src="data:image/jpeg;base64,{img}">' if img else "")
                 + f'<span class="tc">{fmt_t(f["t"])}</span><span class="num">{n + 1}</span></div><div class="meta"><div class="tags">{tags}</div>')
        o.append(f'<div class="orig mono">orig {orig:.2f} s · take {ti}{" · " + kind if kind != "take" else ""}{" · raw " + format(raw, ".2f") + " s" if raw is not None else ""}</div>')
        if cap:
            o.append(f'<div class="cap">{esc(cap)}</div>')
        for b in act:
            o.append(f'<div class="bt">#{b["i"]} {esc(b["label"])}{": " + esc(" / ".join(b["texts"])[:90]) if b["texts"] else ""}</div>')
        if near:
            o.append(f'<div class="sx">♪ {esc(", ".join(e["id"] for e in near))}</div>')
        o.append('<div class="fl"><label><input type="checkbox">flag</label><input type="text" placeholder="note"></div></div></div>')
    o.append("</div>")
    if under:
        o.append(f'<p class="sub">{len(under)} cut(s) sit under full-screen scenes and are not shown: ' + ", ".join(f"cut {n} at {fmt_t(c['t'])} (under #{b['i']} {esc(b['label'])})" for n, c, b in under[:12]) + ("…" if len(under) > 12 else "") + "</p>")

    # timeline
    o.append("<h2>Edit timeline</h2><div class='tlwrap'>" + timeline_svg(pr, beats, groups, frames, hidden, accent) + "</div>")
    o.append('<div class="legend"><span><i style="background:#3a4357"></i>take</span><span><i style="background:#5b4a2a"></i>hold/outro</span><span><i style="background:#fca5a5"></i>cut inside the source</span>'
             f'<span><i style="background:{accent}"></i>scene</span><span><i style="background:#2dd4bf"></i>card</span><span><i style="background:#fbbf24"></i>reaction / zoom</span>'
             + "".join(f'<span><i style="background:{c}"></i>{r}</span>' for r, c in ROLE_COL.items()) + '<span><i style="background:#2a2f3a"></i>caption hidden under a scene</span></div>')

    # takes
    o.append("<h2>Takes (original times)</h2><table><tr><th>#</th><th>edit</th><th>original</th><th>dur</th><th>what is said</th></tr>")
    for k in pr.takes:
        words = take_words(pr, k)
        hold = f" + hold {k.hold:.2f}" if k.hold else ""
        o.append(f'<tr><td>{k.i}</td><td class="t">{fmt_t(k.start)} to {fmt_t(k.start + k.dur)}</td><td class="t">{k.a:.2f} to {k.b:.2f}</td><td class="t">{k.dur:.2f}{hold}</td><td>{esc(words[:220])}{"…" if len(words) > 220 else ""}{"<div class=sub>" + esc(k.note) + "</div>" if k.note else ""}</td></tr>')
        for u in pr.upstream:
            if u["end"] > k.a and u["start"] < k.b:
                te = pr.E_safe(max(u["start"], k.a))
                o.append(f'<tr class="sub"><td></td><td class="t">{fmt_t(te)}</td><td class="t">raw {u["a"]:.2f} to {u["b"]:.2f}</td><td class="t">{u["b"] - u["a"]:.2f}</td><td>{esc(u["note"])}</td></tr>')
    o.append("</table>")
    if pr.upstream:
        o.append(f'<p class="sub">Source is a pre-cut of {esc(pr.upstream_src or "a longer raw take")}: {len(pr.upstream)} segments; raw times are seconds in that file.</p>')

    # beats
    o.append("<h2>Beats</h2><table><tr><th>#</th><th>beat</th><th>edit</th><th>orig at</th><th>on screen</th><th>sound</th></tr>")
    for b in beats:
        if b["t0"] is None:
            o.append(f'<tr id="beat{b["i"]}"><td>{b["i"]}</td><td>{esc(b["label"])}</td><td colspan="4" style="color:var(--err)">{esc(b["error"])}</td></tr>')
            continue
        snd = [e for e in sfx if b["t0"] - 0.12 <= e["t"] <= b["t1"]]
        sn = ", ".join(f'{e["id"]}' for e in snd[:6]) + (f" +{len(snd) - 6}" if len(snd) > 6 else "")
        trans = f' <span class="sub">{esc(b["raw"].get("in", ""))}→{esc(b["raw"].get("out", ""))}</span>' if b["type"] == "scene" else ""
        o.append(f'<tr id="beat{b["i"]}"><td>{b["i"]}</td><td>{esc(b["label"])}{trans}</td><td class="t">{fmt_t(b["t0"])} to {fmt_t(b["t1"])}</td><td class="t">{esc(b["at"])}</td><td>{esc(" / ".join(b["texts"]))}</td><td class="sx">{esc(sn)}</td></tr>')
    o.append("</table>")

    # captions
    cap = spec.get("captions") or {}
    o.append(f"<h2>Captions · {esc(cap.get('style', 'house'))}</h2>")
    fixes = list((cap.get("fixes") or {}).items()) + list((cap.get("phrases") or {}).items())
    if fixes:
        o.append("<div style='margin-bottom:10px'>" + "".join(f'<span class="fix">{esc(a)} → <b>{esc(b)}</b></span>' for a, b in fixes) + "</div>")
    if cap.get("tags") or (isinstance(cap.get("highlight"), list) and cap.get("highlight")):
        o.append(f'<p class="sub">tags: {esc(", ".join(cap.get("tags") or []))} · highlights: {esc(", ".join(cap.get("highlight") or []) if isinstance(cap.get("highlight"), list) else cap.get("highlight") or "")}</p>')
    o.append("<div class='capflow'>")
    for g in groups:
        hid = any(a <= g["t0"] < z for a, z in hidden)
        o.append(f'<span class="cb{" hid" if hid else ""}" title="{esc(g["mode"])} y {g["y"]}"><small>{fmt_t(g["t0"])}</small>{esc(g["text"])}</span> ')
    o.append("</div><p class='sub'>Faded blocks sit under a full-screen scene that hides captions.</p>")

    # sfx
    o.append(f"<h2>Sound effects · {len(sfx)}</h2><details><summary>{esc(', '.join(f'{k} {v}' for k, v in by_role.items()) or 'none')} · voice p95 {(pr.sfx or {}).get('voiceP95', '?')} dBFS · {esc(info.get('music', ''))}</summary>"
             "<table><tr><th>time</th><th>sound</th><th>role</th><th>vol</th><th>why</th></tr>")
    for e in sfx:
        o.append(f'<tr><td class="t">{fmt_t(e["t"])}</td><td class="mono">{esc(e["id"])}</td><td><span style="color:{ROLE_COL.get(e["role"], "#ccc")}">{esc(e["role"])}</span></td><td class="t">{e.get("vol")}</td><td>{esc(e.get("why"))}</td></tr>')
    o.append("</table></details>")
    o.append(f'<footer>approval_sheet.py · frames from {esc(method)} in {took:.0f} s · {dt.datetime.now().strftime("%Y-%m-%d %H:%M")} · '
             f'{esc(info.get("summary", ""))}</footer></main>')
    o.append('<div class="lb" id="lb"><img alt=""></div><div class="toast" id="toast">Copied. Paste it in chat.</div>')
    body = "".join(o)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Approval: {esc(title)}</title><style>{CSS.replace("ACCENT", accent)}</style></head>'
            f'<body data-hash="{hsh}" data-title="{esc(title)}">{body}<script>{JS}</script></body></html>')


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--skill", help="skill dir (default: the one this script belongs to, or $GHOST_EDITOR_SKILL)")
    ap.add_argument("--upstream", help="cut list of a pre-cut source: build/edl_map.json or cut.json (or reel.json 'upstream')")
    ap.add_argument("--frames", default="snapshot", help="snapshot (default) | draft | video:<file>")
    ap.add_argument("--out", help="output html (default <project>/build/approval.html)")
    ap.add_argument("--no-build", action="store_true", help="use the existing build (index.html + build/build.log)")
    ap.add_argument("--no-lint", action="store_true")
    ap.add_argument("--taste", help="taste.json (default: the taste.mjs lookup)")
    ap.add_argument("--max-frames", type=int, default=60)
    ap.add_argument("--jobs", type=int, default=3, help="parallel snapshot sessions (default 3)")
    ap.add_argument("--open", action="store_true", help="open the page in the browser")
    ap.add_argument("--mark-approved", action="store_true", help="record the user's yes for the current build hash and exit")
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    os.makedirs(os.path.join(proj, "build"), exist_ok=True)
    jpath = os.path.join(proj, "build", "approval.json")

    if a.mark_approved:
        j = json.load(open(jpath, encoding="utf-8")) if os.path.exists(jpath) else {}
        h = build_hash(proj)
        if j.get("hash") != h:
            sys.exit(f"the build changed since the sheet was made (sheet {j.get('hash')}, now {h}); make a new sheet first")
        j.update({"approved": True, "approved_at": dt.datetime.now().isoformat(timespec="seconds")})
        json.dump(j, open(jpath, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"approved build {h}")
        return

    t_start = dt.datetime.now()
    pr = load_project(proj, a.skill, a.upstream)
    log_path = os.path.join(proj, "build", "build.log")
    if not a.no_build:
        print("building (build.mjs)...")
        code, text = run_build(pr, log_path)
        if code != 0:
            print(text[-1500:])
        pr = load_project(proj, a.skill, a.upstream)
    text = open(log_path, encoding="utf-8").read() if os.path.exists(log_path) else ""
    bl = parse_build_log(text)
    hsh = build_hash(proj)

    beats = beats_timeline(pr)
    groups = caption_groups(pr)
    frames, hidden, under = plan_frames(pr, beats, a.max_frames)
    # build/build_report.json (written by build.mjs once the INTEGRATION patch is in) beats parsing stdout
    brp = os.path.join(proj, "build", "build_report.json")
    idx = os.path.join(proj, "index.html")
    fresh = os.path.exists(brp) and os.path.exists(idx) and os.path.getmtime(brp) >= os.path.getmtime(idx) >= os.path.getmtime(os.path.join(proj, "reel.json"))
    br = json.load(open(brp, encoding="utf-8")) if fresh else None  # same build run as index.html, else ignore it
    warns = [("error", f"build.mjs: {e}") for e in bl["errors"]]
    sev_of = {}
    tp = (br or {}).get("taste", {}) and br["taste"].get("file")
    if tp and os.path.exists(tp):
        sev_of = {r["id"]: r.get("severity", "warn") for r in json.load(open(tp, encoding="utf-8")).get("rules", [])}
    for w in (br["warnings"] if br else bl["warnings"]):
        if w.startswith("taste ["):
            cut = w.find("; you said: ") if "; you said: " in w else w.find("; skill rule: ")
            msg, said = (w[:cut], w[cut + 2:]) if cut >= 0 else (w, "")
            rid = msg[7:msg.index("]")] if "]" in msg else ""
            warns.append((sev_of.get(rid, "warn"), msg, said))
        else:
            warns.append(("warn", f"build.mjs: {w}"))
    lint_j = None
    if not a.no_lint and os.path.exists(os.path.join(proj, "index.html")):
        print("linting...")
        lint_j = lint(pr)
        if lint_j.get("errorCount"):
            for f in lint_j.get("findings", []):
                if f.get("severity") == "error":
                    warns.append(("error", f"lint {f.get('code')}: {f.get('message')}"))
        elif lint_j.get("errorCount") is None:
            warns.append(("warn", "lint did not run: " + lint_j.get("raw", "")[-200:]))
    taste_j = taste_check(pr, a.taste)
    if taste_j and br and br.get("taste"):  # the build already ran the taste checks and applied the defaults
        taste_j = {"taste": br["taste"]["file"], "applied": [], "warnings": []}
        for d in br["taste"].get("applied") or []:
            warns.append(("info", f"taste default filled by the build: {d['path']} = {json.dumps(d['value'])} [{d['id']}]", d.get("quote") or d.get("say")))
    if taste_j:
        for w in taste_j.get("warnings") or []:
            warns.append((w["severity"] if w["severity"] in ("warn", "info") else "warn", f"taste [{w['id']}] {w['msg']}", w.get("quote") or w.get("say")))
        for d in taste_j.get("applied") or []:
            warns.append(("info", f"taste default (not yet in build.mjs): {d['path']} = {json.dumps(d['value'])} [{d['id']}]", d.get("quote") or d.get("say")))
    warns += sheet_checks(pr, beats, groups, hidden)
    process = taste_process_rules((taste_j or {}).get("taste"))

    print(f"capturing {len(frames)} frames ({a.frames})...")
    t0 = dt.datetime.now()
    tmp = tempfile.mkdtemp(prefix="approval-")
    times = [f["t"] for f in frames]
    try:
        if a.frames == "snapshot":
            pngs = capture_snapshot(pr, times, tmp, a.jobs)
        elif a.frames == "draft":
            draft = os.path.join(proj, "build", "draft.mp4")
            r = sh(npx("hyperframes", "render", "-q", "draft", "-o", draft, "--quiet"), cwd=proj, timeout=7200)
            if r.returncode != 0:
                sys.exit("draft render failed: " + (r.stderr or r.stdout)[-600:])
            pngs = capture_video(draft, times, tmp)
        elif a.frames.startswith("video:"):
            v = a.frames[6:]
            pngs = capture_video(v if os.path.isabs(v) else os.path.join(proj, v), times, tmp)
        else:
            sys.exit("--frames must be snapshot, draft or video:<file>")
        imgs = [to_b64_jpeg(p) for p in pngs]
    finally:
        took = (dt.datetime.now() - t0).total_seconds()
    covers, cw = make_cover(pr, tmp)
    if cw:
        warns.append(("warn", cw))
    shutil.rmtree(tmp, ignore_errors=True)

    out = a.out or os.path.join(proj, "build", "approval.html")
    doc = page(pr, frames, imgs, beats, groups, hidden, under, warns, lint_j, taste_j, process, bl["info"], hsh, a.frames, took, covers)
    open(out, "w", encoding="utf-8").write(doc)
    json.dump({"hash": hsh, "approved": False, "created": t_start.isoformat(timespec="seconds"), "html": out,
               "frames": [{"t": f["t"], "tags": f["tags"]} for f in frames],
               "warnings": [{"severity": w[0], "msg": w[1]} for w in warns], "total": pr.total},
              open(jpath, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    n_err = sum(1 for w in warns if w[0] == "error")
    n_warn = sum(1 for w in warns if w[0] == "warn")
    print(f"{len(frames)} frames in {took:.0f} s; {n_err} errors, {n_warn} warnings")
    print(f"-> {out}  ({os.path.getsize(out) / 1e6:.1f} MB)")
    if a.open:
        open_path(out)


if __name__ == "__main__":
    main()
