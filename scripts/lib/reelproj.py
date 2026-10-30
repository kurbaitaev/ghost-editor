"""Shared helpers for the ghost-editor workflow tools.

Reads a reel project the same way build.mjs does: reel.json merged over its
style preset, the take list turned into an edit timeline (frame-rounded, with
holds and the outro), and E(t) mapping an ORIGINAL-recording second to an edit
second. Also reads the build's side files (words.edit.json, sfx_events.json,
caption_layout.json, build.log) and an optional upstream cut list, for projects
whose source is itself a pre-cut of a longer raw take (reel-c009).

Pure stdlib; numpy is only needed by render_report.py.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

# the skill this file belongs to (scripts/lib/ -> repo root); $GHOST_EDITOR_SKILL points the tools at another copy
DEFAULT_SKILL = os.path.expanduser(os.environ.get("GHOST_EDITOR_SKILL") or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)


def taste_mjs():
    """taste.mjs sits next to the tools here, and in scripts/lib/ once merged into the skill."""
    for p in (os.path.join(TOOLS, "taste.mjs"), os.path.join(HERE, "taste.mjs")):
        if os.path.exists(p):
            return p
    return os.path.join(TOOLS, "taste.mjs")


def sh(cmd, cwd=None, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)


def deep_merge(a, b):
    """Same semantics as build.mjs deepMerge: objects merge, everything else (arrays too) is replaced."""
    if b is None:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        o = dict(a)
        for k, v in b.items():
            o[k] = deep_merge(a.get(k), v)
        return o
    return b


def get_path(obj, dotted):
    cur = obj
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def fmt_t(t):
    """Edit seconds -> m:ss.ss"""
    if t is None:
        return "-"
    m, s = divmod(max(0.0, float(t)), 60)
    return f"{int(m)}:{s:05.2f}"


@dataclass
class Take:
    i: int
    a: float
    b: float
    start: float
    dur: float
    hold: float
    hold_start: float
    note: str = ""


@dataclass
class Project:
    path: str
    skill: str
    raw: dict
    preset: dict
    spec: dict
    fps: int
    takes: list
    speech: float
    outro: float
    total: float
    words_edit: list = field(default_factory=list)
    words_orig: list = field(default_factory=list)
    sfx: dict = field(default_factory=dict)
    layout: dict = field(default_factory=dict)
    upstream: list = field(default_factory=list)  # [{a, b, start, end, note}] raw-take times of the source
    upstream_src: str = ""

    # ---- time mapping (port of build.mjs E) ----
    def E(self, t, what=""):
        if t == "end":
            return self.total
        if isinstance(t, str) and t.startswith("outro+"):
            return round(self.speech + float(t[6:]), 3)
        if isinstance(t, str) and t.startswith("hold:"):
            i, _, off = t[5:].partition("+")
            k = self.takes[int(i)]
            return round(k.hold_start + (float(off) if off else 0.0), 3)
        if isinstance(t, (int, float)):
            for k in self.takes:
                if k.a - 1e-6 <= t <= k.b + 1e-6:
                    return round(k.start + (t - k.a), 3)
            for k0, k1 in zip(self.takes, self.takes[1:]):
                if k0.b < t < k1.a and k1.a - k0.b < 1.2:
                    return round(k1.start, 3)
        raise ValueError(f"E({t}){' for ' + what if what else ''}: not inside any take")

    def E_safe(self, t, what=""):
        try:
            return self.E(t, what)
        except (ValueError, TypeError, IndexError):
            return None

    def to_orig(self, te):
        """Edit seconds -> (original seconds, take index, kind) ; kind = take | hold | outro"""
        for k in self.takes:
            if k.start - 1e-6 <= te < k.start + k.dur:
                return round(k.a + (te - k.start), 3), k.i, "take"
            if k.hold and k.hold_start - 1e-6 <= te < k.hold_start + k.hold:
                return round(k.b, 3), k.i, "hold"
        return round(self.takes[-1].b, 3), self.takes[-1].i, "outro"

    def to_raw(self, orig):
        """Original (source) seconds -> raw-take seconds via the upstream cut list, or None."""
        for u in self.upstream:
            if u["start"] - 1e-6 <= orig <= u["end"] + 1e-6:
                return round(u["a"] + (orig - u["start"]), 2), u
        return None, None

    def cuts(self):
        """Every visible cut in edit time: take boundaries and upstream boundaries inside a take."""
        out = []
        for k in self.takes[1:]:
            prev = self.takes[k.i - 1]
            out.append({"t": round(k.start, 3), "kind": "take", "take": k.i,
                        "orig_from": prev.b, "orig_to": k.a, "gap": round(k.a - prev.b, 3)})
        for j, u in enumerate(self.upstream[1:], 1):
            te = self.E_safe(u["start"])
            if te is None or any(abs(te - c["t"]) < 0.05 for c in out):
                continue
            out.append({"t": te, "kind": "upstream", "seg": j, "raw_from": self.upstream[j - 1]["b"], "raw_to": u["a"]})
        return sorted(out, key=lambda c: c["t"])


def load_upstream(p):
    """Accept build/edl_map.json ([{a,b,start,end,note}]) or a cut.json ({segments: [[a,b,text]...]})."""
    if not p or not os.path.exists(p):
        return [], ""
    d = json.load(open(p))
    if isinstance(d, list):
        return [{"a": x["a"], "b": x["b"], "start": x["start"], "end": x["end"], "note": x.get("note", "")} for x in d], ""
    segs, acc = [], 0.0
    for a, b, *rest in d.get("segments", []):
        segs.append({"a": a, "b": b, "start": round(acc, 3), "end": round(acc + b - a, 3), "note": rest[0] if rest else ""})
        acc += b - a
    return segs, d.get("source", "")


def load_project(path, skill=None, upstream=None):
    path = os.path.abspath(path)
    skill = os.path.abspath(os.path.expanduser(skill or DEFAULT_SKILL))
    raw = json.load(open(os.path.join(path, "reel.json")))
    preset = {}
    if raw.get("style"):
        sp = os.path.join(skill, "styles", f"{raw['style']}.json")
        if os.path.exists(sp):
            preset = json.load(open(sp))
            preset.pop("_about", None)
    spec = deep_merge(preset, raw)
    fps = spec.get("fps", 30)
    takes, acc = [], 0
    for i, t in enumerate(spec["takes"]):
        frames = round((t["b"] - t["a"]) * fps)
        start = acc / fps
        acc += frames
        hf = round((t.get("hold") or 0) * fps)
        hold_start = acc / fps
        acc += hf
        takes.append(Take(i, t["a"], t["b"], start, frames / fps, hf / fps, hold_start, t.get("note", "")))
    speech = acc / fps
    outro = spec.get("outro", 3)
    total = round(speech + outro, 3)
    pr = Project(path, skill, raw, preset, spec, fps, takes, speech, outro, total)

    b = os.path.join(path, "build")
    if os.path.exists(os.path.join(b, "words.edit.json")):
        pr.words_edit = json.load(open(os.path.join(b, "words.edit.json")))
    wp = os.path.join(path, spec.get("words", "build/words.whisper.json"))
    if os.path.exists(wp):
        w = json.load(open(wp))
        pr.words_orig = [{"word": x["word"].strip(), "start": x["start"], "end": x["end"]}
                         for s in w.get("segments", []) for x in s.get("words", [])]
    if os.path.exists(os.path.join(b, "sfx_events.json")):
        pr.sfx = json.load(open(os.path.join(b, "sfx_events.json")))
    if os.path.exists(os.path.join(b, "caption_layout.json")):
        pr.layout = json.load(open(os.path.join(b, "caption_layout.json")))
    up = upstream or spec.get("upstream")
    if up:
        up = up if os.path.isabs(up) else os.path.join(path, up)
        pr.upstream, pr.upstream_src = load_upstream(os.path.expanduser(up))
    return pr


def bare_project(path, skill=None, recipe=None):
    """A HyperFrames project with no reel.json (its index.html was written by a custom generator, e.g. a recipe's
    build.py): one 'take' spanning the main composition, so edit time = composition time. spec["bare"] tells the
    tools to skip what needs the build (take mapping, caption layout, SFX table). Words (edit time): the first of
    build/words.edit.json, words.cut.json, words.json, words.smooth.json (a list or a whisper json), as broll_qa reads them."""
    path = os.path.abspath(path)
    skill = os.path.abspath(os.path.expanduser(skill or DEFAULT_SKILL))
    total, fps = 0.0, 30
    idx = os.path.join(path, "index.html")
    if os.path.exists(idx):
        m = re.search(r'<div[^>]*data-composition-id="main"[^>]*>', open(idx, encoding="utf-8", errors="replace").read())
        d = re.search(r'data-duration="([\d.]+)"', m.group(0)) if m else None
        f = re.search(r'data-fps="([\d.]+)"', m.group(0)) if m else None
        total = float(d.group(1)) if d else 0.0
        fps = int(round(float(f.group(1)))) if f else 30
    spec = {"bare": True, **({"recipe": recipe} if recipe else {})}
    pr = Project(path, skill, {}, {}, spec, fps, [Take(0, 0.0, total, 0.0, total, 0.0, total, "composition")], total, 0, round(total, 3))
    b = os.path.join(path, "build")
    for name in ("words.edit.json", "words.cut.json", "words.json", "words.smooth.json"):
        p = os.path.join(b, name)
        if not os.path.exists(p):
            continue
        w = json.load(open(p))
        if isinstance(w, dict):
            w = [x for s in w.get("segments", []) for x in s.get("words", [])] if "segments" in w else w.get("words", [])
        pr.words_edit = [{"word": str(x.get("word") or x.get("w") or x.get("text") or "").strip(), "start": x.get("start", x.get("s")),
                          "end": x.get("end", x.get("e"))} for x in w if isinstance(x, dict)]
        pr.words_edit = [x for x in pr.words_edit if x["start"] is not None]
        break
    return pr


# ---- beats ----------------------------------------------------------------

TEXT_KEYS = {"text", "value", "label", "title", "line", "header", "stamp", "emoji", "url"}
TIME_KEYS = {"at", "labelAt", "strikeAt", "stampAt", "clickAt", "crossAt"}


def beat_texts(b):
    """Every on-screen string in a beat, in reading order (markdown ** stripped)."""
    out = []

    def walk(x, key=None):
        if isinstance(x, str):
            if key in TEXT_KEYS or key in ("lines", "sub", "words"):
                out.append(x.replace("**", "").replace("*", "").replace("_", " ").strip())
        elif isinstance(x, dict):
            for k, v in x.items():
                if k in ("sfx", "src", "bg", "color", "in", "out", "grade", "font", "kind", "type"):
                    continue
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)

    walk(b)
    seen, res = set(), []
    for s in out:
        if s and s not in seen:
            seen.add(s)
            res.append(s)
    return res


def beat_moments(b):
    """Every original-time key moment inside a beat (word landings, clicks, labels)."""
    ts = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in TIME_KEYS and isinstance(v, (int, float)):
                    ts.append(v)
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(b)
    return sorted(set(ts))


def beat_label(b):
    if b.get("type") == "scene":
        return f"scene · {b.get('kind', '?')}"
    if b.get("type") == "cutout":
        return f"cutout · {b.get('fx', '?')}"
    if b.get("type") == "behind" and (b.get("through") or b.get("front")):
        return "behind · through" if b.get("through") else "behind · front"
    return b.get("type", "?")


FULLSCREEN = {"scene", "broll", "diagram"}  # diagram: the stan-style white frame (lib/stan.mjs)


def beats_timeline(pr):
    """Beats with edit times: [{i, label, type, t0, t1, at, texts, moments(edit), full, raw}]"""
    out = []
    for i, b in enumerate(pr.spec.get("beats") or []):
        t0 = pr.E_safe(b.get("at"), "beat")
        if t0 is None:
            out.append({"i": i, "label": beat_label(b), "type": b.get("type"), "t0": None, "t1": None, "at": b.get("at"),
                        "texts": beat_texts(b), "moments": [], "full": False, "raw": b, "error": f"at {b.get('at')} is not inside any take"})
            continue
        if b.get("to") is None:
            t1 = pr.total if b.get("type") == "endcard" else t0 + (1.8 if b.get("type") == "meme" else 2.5)
        else:
            t1 = pr.E_safe(b["to"], "beat to") or t0 + 2.5
        ms = [m for m in (pr.E_safe(x) for x in beat_moments(b)) if m is not None and t0 - 0.01 <= m <= t1 + 0.01]
        full = (b.get("type") in FULLSCREEN and not (b.get("type") == "broll" and b.get("mode") == "split")) or (b.get("type") == "textfx" and bool(b.get("bg")))
        out.append({"i": i, "label": beat_label(b), "type": b.get("type"), "t0": round(t0, 3), "t1": round(min(t1, pr.total), 3),
                    "at": b.get("at"), "texts": beat_texts(b), "moments": sorted(set(round(m, 3) for m in ms)), "full": full,
                    "captions_on": b.get("captions") is True, "raw": b})
    return out


# ---- captions ---------------------------------------------------------------

def caption_groups(pr):
    """Caption blocks as shown on screen: from caption_layout.json when present, else 3-word groups."""
    words = pr.words_edit
    blocks = (pr.layout or {}).get("blocks") or []
    if blocks:
        res = []
        starts = sorted(bl["t0"] for bl in blocks)
        owner = {}
        for wi, w in enumerate(words):  # each word belongs to the last block that started before it
            cand = [t for t in starts if t <= w["start"] + 0.06]
            owner[wi] = cand[-1] if cand else None
        for bl in blocks:
            ws = [w for wi, w in enumerate(words) if owner[wi] == bl["t0"] and w["start"] < bl["t1"] + 0.3]
            res.append({"t0": bl["t0"], "t1": bl["t1"], "y": bl["y"], "mode": bl["mode"], "scale": bl.get("scale", 1),
                        "text": " ".join(w["word"] for w in ws), "words": ws})
        return res
    res, cur = [], []
    for w in words:
        if cur and w["start"] - cur[-1]["end"] > 0.6:
            res.append(cur)
            cur = []
        cur.append(w)
        if len(cur) >= 3 or re.search(r"[.?!,]$", w["word"]):
            res.append(cur)
            cur = []
    if cur:
        res.append(cur)
    return [{"t0": g[0]["start"], "t1": g[-1]["end"] + 0.3, "y": None, "mode": "?", "scale": 1,
             "text": " ".join(w["word"] for w in g), "words": g} for g in res]


def caption_at(groups, t):
    """The caption words visible at edit time t (a block reveals its words as they are spoken)."""
    for g in groups:
        if g["t0"] - 0.05 <= t <= g["t1"]:
            ws = [w["word"] for w in g.get("words", []) if w["start"] <= t + 0.05]
            return " ".join(ws) if ws else g["text"]
    return ""


def take_words(pr, k):
    """Words spoken inside take k (edit-time words of the build)."""
    return " ".join(w["word"] for w in pr.words_edit if k.start - 0.02 <= w["start"] < k.start + k.dur)


# ---- silences predicted before the render ------------------------------------

def predicted_silences(pr, noise="-38dB", min_len=0.8):
    """Silences the cut will contain, from the source audio alone (no render): raw silences intersected with
    each take, joined across cuts, holds excluded. Returns [(edit_start, edit_end)] longer than min_len."""
    src = os.path.join(pr.path, pr.spec.get("source", "assets/talk.mp4"))
    if not os.path.exists(src):
        return []
    e = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-af", f"silencedetect=noise={noise}:d=0.15", "-f", "null", "-"]).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", e)]
    raw = [(max(0.0, a), en[i] if i < len(en) else 1e9) for i, a in enumerate(st)]
    spans = []
    for k in pr.takes:
        for a, b in raw:
            lo, hi = max(a, k.a), min(b, k.b)
            if hi > lo:
                spans.append([k.start + lo - k.a, k.start + hi - k.a])
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a - merged[-1][1] < 1.5 / pr.fps:  # touching across a cut: one pause to the ear
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in merged if b - a > min_len and a < pr.speech]


# ---- build.log --------------------------------------------------------------

def parse_build_log(text):
    """Pull the timeline, warnings and errors out of build.mjs stdout."""
    warnings, errors = [], []
    m = re.search(r"\nWARNINGS:\n((?:  .*\n?)+)", text)
    if m:
        warnings = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
    for ln in text.splitlines():
        if ln.startswith("ERROR:"):
            errors.append(ln[6:].strip())
    info = {}
    m = re.search(r"(\d+) takes, ([\d.]+)s speech \+ ([\d.]+)s outro = ([\d.]+)s", text)
    if m:
        info["summary"] = m.group(0)
    m = re.search(r"^music: .*$", text, re.M)
    if m:
        info["music"] = m.group(0)[7:]
    m = re.search(r"^caption placement .*$", text, re.M)
    if m:
        info["placement"] = m.group(0)
    m = re.search(r"^voice p95 peak .*$", text, re.M)
    if m:
        info["voice"] = m.group(0)
    return {"warnings": warnings, "errors": errors, "info": info}


def run_build(pr, log_path=None):
    """Run the skill's build.mjs on the project and keep its stdout as build/build.log."""
    r = sh(["node", os.path.join(pr.skill, "scripts", "build.mjs"), pr.path])
    text = (r.stdout or "") + (r.stderr or "")
    log_path = log_path or os.path.join(pr.path, "build", "build.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    open(log_path, "w").write(text)
    return r.returncode, text


def ffprobe_json(p):
    r = sh(["ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels,start_time,duration:format=duration",
            "-of", "json", p])
    return json.loads(r.stdout or "{}")


def have(cmd):
    return shutil.which(cmd) is not None
