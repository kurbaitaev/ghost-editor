"""The shared base of the custom talking-head builders (recipes/result-podcast/faceresult.py, recipes/whiteboard/board.py).

A reel generator in the project imports a recipe module, which builds on this:
  - the speaker's plate AS SHOT (no grade, no filter, no vignette) with the last frame held for the tail, 1 s keyframes;
  - the voice of the same cut, the words of the cut in edit seconds and word refs to key every beat to a spoken word;
  - a GSAP timeline (ft / st / tween, baselines set at load), SFX levelled by role against THIS voice (like build.mjs),
    a ducked music bed, build/sfx_events.json for qa.py;
  - the face box from face.json: free zones beside / above / below the face, and a guard that fails the build when a
    graphic box touches the face while it is on screen;
  - the talking-head budgets (references/broll.md): the face on screen >= 65 %, a full-screen scene <= 2.5 s,
    <= 3 inserts a minute, every cover window hidden. A broken budget fails the build, it never just warns;
  - build/beats.json (key times for recipes/seoul-list/snap.py beats / strips) and build/plan.json (the numbers).
Pure stdlib (no numpy needed).

Project layout ($P; one cut = one reel; `python3 facereel.py --new $P --from <cut dir>` makes it from an approved cut):
  assets/plate.mp4          the speaker's picture as shot (the approved raw cut; video only). Any name: Reel(plate=...)
  assets/voice.wav          the voice of the same cut (-16 LUFS after prep.sh / voice_smooth.py)
  build/words.json          words of the cut in edit seconds: a whisper json (segments[].words) or a list
                            (also found as words.edit.json / words.cut.json, like render_report reads a bare project)
  build/face.json           scripts/face_track.py run ON THE PLATE (so its seconds are edit seconds)
  build/cover_windows.json  optional: scripts/cover_windows.py look-aways ([[t0, t1], ...]) that must be hidden

Word refs (the same grammar as recipes/seoul-list list.json): "word" (its first occurrence at or after `after`), "word#2"
(2nd occurrence), "^word" (its end), "word+0.12" / "word-0.1" (offset), a phrase "give it" (the start of the first
word where the words follow each other; "^give it" = the end of the last), a number (seconds, unless it is a
spoken word: "38" is the word when it is said).
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import shutil
import struct
import subprocess
import zlib

SKILL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
X264_THREADS = open(os.path.join(SKILL, "scripts", "X264_THREADS")).read().strip()  # every libx264 encode (scripts/x264.py)
LIB = os.path.join(SKILL, "library")
FONTS = os.path.join(SKILL, "templates", "fonts")
GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
W, H = 1080, 1920
# SFX level per role, dB under this voice's p95 50 ms peak (build.mjs ROLE_DB)
ROLE_DB = {"ui": -14, "whoosh": -12, "impact": -8, "meme": -3, "foley": -14}
RANGES = {"latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2191, "
                   "U+2193, U+2212, U+2215, U+FEFF, U+FFFD",
          "cyrillic": "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116"}
# family (":italic" for the italic face) -> (file stem in templates/fonts, weight range)
FACES = {"Inter Tight": ("inter-tight", "100 900"), "Inter": ("inter", "100 900"), "Oswald": ("oswald", "200 700"),
         "Caveat": ("caveat", "400 700"), "JetBrains Mono": ("jetbrains-mono", "100 800"),
         "Playfair Display": ("playfair-display", "400 900"), "Playfair Display:italic": ("playfair-display-italic", "400 900")}
# typed text (faceresult.py .mono) is JetBrains Mono
FACE_MARGIN = 18            # px of air a graphic keeps from the face box
# Instagram Reels safe area (scripts/lib/safezone.mjs): the top bar ends at 220, the bottom UI starts at 1920 - 420;
# the action buttons (x > 950) start around y 1100, so a side column stops there
SAFE = {"top": 220, "bottom": 1500, "side_bottom": 1100}


class BuildError(SystemExit):
    pass


def norm(s):
    return re.sub(r"[^\w]+", "", str(s).lower().replace("ё", "е")).replace("_", "")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def r3(x):
    return round(float(x), 3)


def probe_duration(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def probe_color(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=color_space,color_transfer,color_primaries,color_range", "-of", "json", p],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out)["streams"][0]
    except (KeyError, IndexError, ValueError):
        return {}


def grain_png(path, size=480, seed=11):
    """a seeded mid-grey noise tile (PNG, 8-bit grey), so renders match previews and nothing binary ships"""
    rnd = random.Random(seed)
    rows = b"".join(b"\x00" + bytes(max(0, min(255, int(128 + rnd.gauss(0, 38)))) for _ in range(size)) for _ in range(size))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)


def core(s):
    """the face itself in a face.json sample [t, top, bottom, left, right, ...] -> [left, top, right, bottom].
    face_track.py grows YuNet's box (hair 0.35 h above, chin 0.12 h below, ears 0.08 w at the sides); YuNet's own box
    already runs from the forehead (the cap brim) into the beard. The core is that box, 5 % wider at each side (ears)
    and 8 % longer (the beard). Nothing may touch it. broll_qa's "nothing over a face" check uses the bare box."""
    t, b, l, r = s[1], s[2], s[3], s[4]
    h, w = (b - t) / 1.47, (r - l) / 1.16
    y, x = t + 0.35 * h, l + 0.08 * w
    return [x - 0.05 * w, y, x + 1.05 * w, y + 1.08 * h]


def head(s):
    """the whole head (face_track's grown box: hair or cap, ears, chin) -> [left, top, right, bottom]"""
    return [s[3], s[1], s[4], s[2]]


def load_words(path, fixes=None):
    w = json.load(open(path))
    if isinstance(w, dict):
        w = [x for s in w.get("segments", []) for x in s.get("words", [])] if "segments" in w else w.get("words", [])
    fx = {norm(k): v for k, v in (fixes or {}).items()}
    out = []
    for x in w:
        raw = str(x.get("word") or x.get("w") or x.get("text") or "").strip()
        s, e = x.get("start", x.get("s")), x.get("end", x.get("e"))
        if not raw or s is None:
            continue
        if raw.startswith("-") and out:                       # whisper splits a hyphenated word ("word -suffix"): glue it back
            out[-1]["raw"] += raw
            out[-1]["e"] = float(e)
            out[-1]["n"] = norm(out[-1]["raw"])
            continue
        out.append({"raw": raw, "n": norm(raw), "s": float(s), "e": float(e)})
    for x in out:
        x["text"] = fx.get(x["n"], x["raw"].strip("«».,?!:;–—\"'").lower())
        x["n2"] = norm(x["text"])
    return out


class Reel:
    """One reel. Recipes subclass it; a generator calls the recipe's helpers, then build()."""

    def __init__(self, project, plate=None, voice="assets/voice.wav", words=None, fixes=None, tail=0.45, cover=None,
                 fps=30, vcut=None, music=None):
        self.P = os.path.abspath(os.path.expanduser(project))
        self.fps = fps
        os.makedirs(os.path.join(self.P, "assets"), exist_ok=True)
        os.makedirs(os.path.join(self.P, "build"), exist_ok=True)
        self.plate_src = self._find(plate, ["assets/plate.mp4", "assets/plate_alt.mp4", "assets/talk.mp4"], "the plate")
        self.voice = self._find(voice, [], "the voice")
        wp = self._find(words, ["build/words.json", "build/words.edit.json", "build/words.cut.json"], "the words")
        self.words = load_words(wp, fixes)
        if not self.words:
            raise BuildError(f"no words in {wp}")
        self.TV = r3(min(probe_duration(self.plate_src), probe_duration(self.voice)))
        if vcut:
            self.TV = r3(min(self.TV, vcut))
        self.tail = tail
        self.T = r3(self.TV + tail)
        self.RU = sum(1 for x in self.words if re.search("[\u0400-\u04FF]", x["raw"])) * 2 > len(self.words)
        self.tl, self.base, self.based, self.css, self.html = [], [], set(), [], []
        self.events, self.beats, self._guards, self.notes = [], [], [], []
        self.full, self.inserts, self.capoff = [], [], []
        self.face = self._load_face()
        cw = os.path.join(self.P, "build", "cover_windows.json")
        self.cover = [tuple(map(float, c)) for c in (cover if cover is not None else (json.load(open(cw)) if os.path.exists(cw) else []))]
        self.music = music
        self._voice_p95 = None
        self._sfx_man = json.load(open(os.path.join(LIB, "sfx", "manifest.json")))
        self._track = 30

    # ---------------------------------------------------------------- files
    def _find(self, rel, cands, what):
        for c in ([rel] if rel else []) + cands:
            p = c if os.path.isabs(c) else os.path.join(self.P, c)
            if os.path.exists(p):
                return p
        raise BuildError(f"{what} not found in {self.P} (tried {', '.join(([rel] if rel else []) + cands)})")

    def rel(self, p):
        return os.path.relpath(p, self.P)

    # ---------------------------------------------------------------- words
    def t(self, ref, after=0.0, what=""):
        """a word ref -> edit seconds (module docstring)"""
        if isinstance(ref, (int, float)):
            return float(ref)
        m = re.match(r"^(\^)?(.+?)(?:#(\d+))?([+-]\d*\.?\d+)?$", str(ref).strip())
        if not m:
            raise BuildError(f"bad word ref {ref!r} ({what})")
        end, body, nth, off = m.groups()
        toks = [norm(x) for x in body.split() if norm(x)]
        if re.fullmatch(r"-?\d*\.?\d+", body) and not any(x["n"] == toks[0] or x["n2"] == toks[0] for x in self.words):
            return float(body) + (float(off) if off else 0.0)    # seconds, unless the number is a spoken word ("38")
        hits = []
        for i in range(len(self.words) - len(toks) + 1):
            if all(self.words[i + k]["n"] == toks[k] or self.words[i + k]["n2"] == toks[k] for k in range(len(toks))):
                hits.append((self.words[i], self.words[i + len(toks) - 1]))
        if not hits:
            raise BuildError(f"{body!r} is not in the voice ({what}). Words: " + " ".join(x["raw"] for x in self.words))
        if nth:
            if int(nth) > len(hits):
                raise BuildError(f"{body!r} is said {len(hits)} time(s), not #{nth} ({what})")
            a, b = hits[int(nth) - 1]
        else:
            a, b = next((h for h in hits if h[0]["s"] >= after - 0.3), hits[0])
        return r3((b["e"] if end else a["s"]) + (float(off) if off else 0.0))

    def said(self, a, b):
        """the on-screen text of the words spoken in [a, b)"""
        return " ".join(x["text"] for x in self.words if a - 0.02 <= x["s"] < b)

    # ---------------------------------------------------------------- timeline
    def ft(self, sel, frm, to, at):
        """fromTo at `at`; the first call per selector also sets `frm` at load (a gsap.set, not a tl.set at 0)"""
        if sel not in self.based:
            self.based.add(sel)
            self.base.append(f'gsap.set("{sel}", {json.dumps(frm)});')
        self.tl.append(f'tl.fromTo("{sel}", {json.dumps(frm)}, {json.dumps({**to, "immediateRender": False})}, {max(0.0, at):.3f});')

    def tween(self, sel, frm, to, at):
        self.tl.append(f'tl.fromTo("{sel}", {json.dumps(frm)}, {json.dumps({**to, "immediateRender": False})}, {max(0.0, at):.3f});')

    def st(self, sel, props, at):
        if at <= 0.0005:
            self.base.append(f'gsap.set("{sel}", {json.dumps(props)});')
            self.based.add(sel)
        else:
            self.tl.append(f'tl.set("{sel}", {json.dumps(props)}, {at:.3f});')

    def js(self, code):
        self.tl.append(code)

    def beat(self, bid, kind, t0, t1, label, keys=()):
        ks = sorted({r3(min(max(k, t0 + 0.04), t1 - 0.04)) for k in (list(keys) or [t0 + 0.3, (t0 + t1) / 2, t1 - 0.1])})
        self.beats.append({"id": bid, "type": kind, "label": label, "t0": r3(t0), "t1": r3(t1), "keys": ks})

    # ---------------------------------------------------------------- sound
    def voice_p95(self):
        if self._voice_p95 is None:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", self.voice, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                 capture_output=True).stdout
            n = len(raw) // 4
            x = struct.unpack(f"<{n}f", raw[:n * 4])
            pk, win = [], 800
            for w in self.words:
                i = int(w["s"] * 16000)
                while i + win <= w["e"] * 16000 and i + win <= n:
                    pk.append(max(abs(v) for v in x[i:i + win]))
                    i += win
            pk.sort()
            p = pk[int(len(pk) * 0.95)] if pk else 0.3
            self._voice_p95 = 20 * math.log10(max(p, 1e-6))
        return self._voice_p95

    def sound(self, sid, at, why="", db=0.0, maxlen=None, gap=0.3, foley_gap=0.9, fade=None):
        """a kit sound at `at`, levelled by its role against this voice; a second sound within `gap` s is dropped,
        and foley (marker, pencil) keeps `foley_gap` s between hits (texture, not a soundboard).
        fade=s (with maxlen): a trimmed copy that fades out over its last s seconds (assets/sfx/<id>-<ms>.wav); the meme
        rips are cut while still loud (vine-boom ends at -13 dB), so a bare maxlen stops them with a click"""
        m = self._sfx_man.get(sid)
        if not m:
            raise BuildError(f"sfx {sid!r} is not in library/sfx/manifest.json ({why})")
        role = m.get("role") if m.get("role") in ROLE_DB else "ui"
        at = max(0.0, at)
        for e in self.events:
            if abs(e["t"] - at) < gap or (role == "foley" and e["role"] == "foley" and abs(e["t"] - at) < foley_gap):
                return None
        if at >= self.T - 0.05:
            return None
        d = min(float(m.get("duration", 1.0)), maxlen or 99, self.T - at)
        vol = min(1.0, 10 ** ((self.voice_p95() + ROLE_DB[role] + db + 1) / 20))
        ev = {"t": r3(at), "id": sid, "role": role, "vol": r3(vol), "dur": r3(d), "src": f"assets/sfx/{m['file']}", "why": why}
        if fade and maxlen:
            stem, ext = os.path.splitext(m["file"])
            ev["src"], ev["fade"] = f"assets/sfx/{stem}-{round(d * 1000)}{ext}", r3(min(fade, d))
            os.makedirs(os.path.join(self.P, "assets", "sfx"), exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(LIB, "sfx", m["file"]), "-t", f"{d:.3f}", "-af",
                            f"afade=t=out:st={d - ev['fade']:.3f}:d={ev['fade']:.3f}", os.path.join(self.P, ev["src"])], check=True)
        self.events.append(ev)
        return ev

    def _audio(self):
        os.makedirs(os.path.join(self.P, "assets", "sfx"), exist_ok=True)
        v = self.rel(self.voice)
        tags = [f'<audio id="vo" src="{v}" data-start="0" data-duration="{self.TV:.3f}" data-track-index="10" data-volume="1"></audio>']
        busy = {}
        for i, e in enumerate(sorted(self.events, key=lambda x: x["t"])):
            if not e.get("fade"):                          # a faded copy is already in the project
                shutil.copy(os.path.join(LIB, "sfx", os.path.basename(e["src"])), os.path.join(self.P, e["src"]))
            tr = next(k for k in range(40, 90) if busy.get(k, -1.0) <= e["t"])
            busy[tr] = e["t"] + e["dur"] + 0.01
            tags.append(f'<audio id="sfx{i}" src="{e["src"]}" data-start="{e["t"]:.3f}" data-duration="{e["dur"]:.3f}" '
                        f'data-track-index="{tr}" data-volume="{e["vol"]}"></audio>')
        if self.music:
            tags.append(self._music(**self.music))
        return tags

    def _music(self, id, db=-20.0, duck=-8.0, start=0.0, fade_in=0.6, fade_out=1.2):
        """a bed from library/music, `db` under the voice's -16 LUFS, ducked under every speech island (motion.mjs buildMusic)"""
        man = json.load(open(os.path.join(LIB, "music", "manifest.json")))
        if id not in man:
            raise BuildError(f"music {id!r} is not in library/music/manifest.json")
        os.makedirs(os.path.join(self.P, "assets", "music"), exist_ok=True)
        src = f"assets/music/{man[id]['file']}"
        shutil.copy(os.path.join(LIB, "music", man[id]["file"]), os.path.join(self.P, src))
        err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", os.path.join(self.P, src), "-t", "60", "-af", "ebur128",
                              "-f", "null", "-"], capture_output=True, text=True).stderr
        I = float((re.findall(r"I:\s+(-?[\d.]+) LUFS", err) or ["-14"])[-1])
        vol = r3(min(3.98, 10 ** ((-16 + db - I) / 20)))
        isl = []
        for w in self.words:
            if isl and w["s"] - isl[-1][1] < 0.6:
                isl[-1][1] = w["e"]
            else:
                isl.append([w["s"], w["e"]])
        pts = [(0.0, 0.0), (fade_in, vol)]
        dv = r3(vol * 10 ** (duck / 20))
        for a, b in isl:
            a0, b0 = max(fade_in, a - 0.25), min(self.T - fade_out, b + 0.4)
            if b0 <= a0 + 0.25:
                continue
            if a0 > pts[-1][0]:
                pts.append((r3(a0), vol))
            pts += [(r3(max(a0, a)), dv), (r3(max(a0, b)), dv), (r3(b0), vol)]
        pts += [(r3(self.T - fade_out), vol), (r3(self.T), 0.0)]
        pts = [p for i, p in enumerate(pts) if i == 0 or p[0] > pts[i - 1][0]]
        lane = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": [{"t": t, "v": v} for t, v in pts]}]})
        self.notes.append(f"music {id}: {db} dB under the voice ({I:.1f} LUFS file, volume {vol}), ducked {duck} dB under {len(isl)} speech islands")
        return (f"<audio id=\"bed\" src=\"{src}\" data-start=\"0\" data-duration=\"{self.T:.3f}\" data-media-start=\"{start}\" "
                f"data-track-index=\"20\" data-automation='{lane}'></audio>")

    # ---------------------------------------------------------------- the face
    def _load_face(self):
        p = os.path.join(self.P, "build", "face.json")
        if not os.path.exists(p):
            raise BuildError(f"no build/face.json: run  python3 {SKILL}/scripts/face_track.py {self.rel(self.plate_src)} "
                             f"--out {p}  (on the plate, so its seconds are edit seconds)")
        f = json.load(open(p))
        return [s for s in f["samples"] if len(s) > 4 and s[1] is not None]

    def face_box(self, a=0.0, b=None, q=0.0):
        """[left, top, right, bottom] covering the face core on screen in [a, b] (q > 0 drops that share of outliers)"""
        b = self.T if b is None else b
        ss = [self.face_at(s) for s in self.face if a - 0.25 <= s[0] <= b + 0.25] or [self.face_at(s) for s in self.face]
        def pick(vals, hi):
            vals = sorted(vals)
            k = min(len(vals) - 1, max(0, int(round((1 - q if hi else q) * (len(vals) - 1)))))
            return vals[k]
        return [pick([c[0] for c in ss], False), pick([c[1] for c in ss], False), pick([c[2] for c in ss], True), pick([c[3] for c in ss], True)]

    def face_mid(self, a=0.0, b=None):
        """median (eyes_y + mouth_y) / 2 and median face centre x over [a, b]: the point a zoom pivots on"""
        b = self.T if b is None else b
        ss = [s for s in self.face if a - 0.25 <= s[0] <= b + 0.25 and len(s) > 6 and s[5] is not None] or self.face
        ys = sorted((s[5] + s[6]) / 2 for s in ss)
        xs = sorted((s[3] + s[4]) / 2 for s in ss)
        return xs[len(xs) // 2], ys[len(ys) // 2]

    def zones(self, a=0.0, b=None):
        """free rectangles [x, y, w, h] around the speaker on screen in [a, b], inside the Instagram safe area (SAFE): the
        top band from the top bar down to the head (hair / cap), the left and right columns from the frame edge to the
        ears, the chest band from the chin down to the bottom UI. A prop in a zone never touches the face core."""
        b = self.T if b is None else b
        ss = [s for s in self.face if a - 0.25 <= s[0] <= b + 0.25] or self.face
        F = [self.face_at(s) for s in ss]
        Hd = [self.head_at(s) for s in ss]
        L, R, B = min(f[0] for f in F), max(f[2] for f in F), max(f[3] for f in F)
        HT = min(h[1] for h in Hd)
        m = FACE_MARGIN
        side_top, side_bot = max(SAFE["top"], HT - 40), min(SAFE["side_bottom"], B + 200)
        return {"top": [60, SAFE["top"], 960, max(0, int(HT - m - SAFE["top"]))],
                "left": [24, int(side_top), max(0, int(L - m - 24)), int(side_bot - side_top)],
                "right": [int(R + m), int(side_top), max(0, int(W - 24 - (R + m))), int(side_bot - side_top)],
                "chest": [60, int(B + m), 960, max(0, int(SAFE["bottom"] - (B + m)))]}

    def guard(self, what, box, a, b):
        """box [x, y, w, h] (reel pixels, as it finally sits) must stay clear of the face core over [a, b]; checked at
        build time, after every punch-in and move is known (recipes with a moving plate override face_at)"""
        self._guards.append((what, tuple(box), a, b))

    def _run_guards(self):
        out, m = [], FACE_MARGIN * 0.5
        for what, (x, y, w, h), a, b in self._guards:
            for s in self.face:
                if a + 0.05 <= s[0] <= b - 0.05:
                    l_, t_, r_, b_ = self.face_at(s)
                    if x < r_ + m and x + w > l_ - m and y < b_ + m and y + h > t_ - m:
                        out.append(f"{what} [{x:.0f},{y:.0f} {w:.0f}x{h:.0f}] touches the face [{l_:.0f}-{r_:.0f} x {t_:.0f}-{b_:.0f}] at {s[0]:.2f} s")
                        break
        return out

    def xf(self, t, box):
        """where a plate box [l, t, r, b] sits on screen at time t (identity here; a recipe that moves the plate overrides it)"""
        return box

    def face_at(self, s):
        """the face core of a face.json sample where it sits on screen at its time"""
        return self.xf(s[0], core(s))

    def head_at(self, s):
        """the whole head (hair / cap) of a sample where it sits on screen"""
        return self.xf(s[0], head(s))

    # ---------------------------------------------------------------- budgets
    def full_screen(self, sid, a, b, what, cap=2.5, din=0.0, dout=0.0):
        """register a full-screen window (the face off screen); it hides a look-away only while fully in: [a + din, b - dout]"""
        if b - a > cap + 0.02:
            raise BuildError(f"{sid}: full screen {b - a:.2f} s > {cap} s ({what})")
        self.full.append((r3(a), r3(b), sid, what, r3(a + din), r3(b - dout)))

    def insert(self, iid, src, a, b, line, frame, kind):
        """a stock / AI / own-footage picture on screen (counted against <= 3 a minute; broll_vision picks reads index.html)"""
        self.inserts.append({"id": iid, "file": src, "a": r3(a), "b": r3(b), "line": line, "frame": frame, "kind": kind})

    def metrics(self):
        def union(iv, gap=0.05):
            out = []
            for a, b in sorted(iv):
                if out and a <= out[-1][1] + gap:
                    out[-1][1] = max(out[-1][1], b)
                else:
                    out.append([a, b])
            return out
        fu = union([(a, b) for a, b, *_ in self.full])
        off = sum(b - a for a, b in fu)
        ins = union([(x["a"], x["b"]) for x in self.inserts], 0.3)
        mins = self.T / 60
        return {"duration": self.T, "face_on_screen_pct": round(100 * (self.T - off) / self.T, 1), "full_screen_s": round(off, 2),
                "full_screen_pct": round(100 * off / self.T, 1), "full_screens": len(fu),
                "longest_full_s": round(max([b - a for a, b in fu] or [0]), 2), "inserts": len(self.inserts),
                "inserts_per_min": round(len(ins) / mins, 2), "sfx": len(self.events),
                "sfx_per_10s": round(10 * len(self.events) / self.T, 2)}

    def check_budgets(self, extra_cover=()):
        m = self.metrics()
        errs = []
        if m["face_on_screen_pct"] < 65:
            errs.append(f"the face is on screen {m['face_on_screen_pct']} % (< 65 %)")
        if m["inserts_per_min"] > 3.0:
            errs.append(f"{m['inserts_per_min']} inserts a minute (> 3)")
        hide = [(f[4], f[5]) if len(f) > 5 else (f[0], f[1]) for f in self.full] + list(extra_cover)
        for c0, c1 in self.cover:
            if c1 <= 0.0 or c0 >= self.TV:
                continue
            ok = all(any(a - 0.001 <= c0 + (c1 - c0) * k / 10 <= b + 0.001 for a, b in hide) for k in range(11))
            if not ok:
                errs.append(f"look-away {c0:.2f}-{c1:.2f} s is not hidden (cover it with a full-screen scene)")
        errs += self._run_guards()
        return m, errs

    # ---------------------------------------------------------------- page
    def held_plate(self):
        """assets/plate_hold.mp4: the plate cut at TV with its last frame held for the tail, 1 s keyframes, colours
        untouched (the same YUV, the source's colour tags); rebuilt when the plate or the length changes"""
        dst = os.path.join(self.P, "assets", "plate_hold.mp4")
        prm = f"{self.rel(self.plate_src)}|{os.path.getmtime(self.plate_src)}|{self.TV}|{self.tail}"
        pf = dst + ".params"
        if not os.path.exists(dst) or not os.path.exists(pf) or open(pf).read() != prm:
            c = probe_color(self.plate_src)
            tags = []
            for k, opt in (("color_primaries", "-color_primaries"), ("color_transfer", "-color_trc"), ("color_space", "-colorspace")):
                if c.get(k) and c[k] != "unknown":
                    tags += [opt, c[k]]
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", self.plate_src, "-t", f"{self.TV}", "-an", "-vf",
                            f"tpad=stop_mode=clone:stop_duration={self.tail + 0.1:.2f}", "-c:v", "libx264", "-threads", X264_THREADS, "-crf", "12",
                            "-preset", "medium", "-g", str(self.fps), "-pix_fmt", "yuv420p", *tags, "-r", str(self.fps), dst], check=True)
            open(pf, "w").write(prm)
        return "assets/plate_hold.mp4"

    def font_css(self, families):
        os.makedirs(os.path.join(self.P, "assets", "fonts"), exist_ok=True)
        out = []
        for key in families:
            stem, wt = FACES[key]
            fam, style = (key.split(":") + ["normal"])[:2]
            for r in ("latin", "cyrillic"):
                f = f"{stem}-{r}.woff2"
                src = os.path.join(FONTS, f)
                if not os.path.exists(src):
                    continue
                shutil.copy(src, os.path.join(self.P, "assets", "fonts", f))
                out.append(f'@font-face {{ font-family: "{fam}"; font-style: {style}; font-weight: {wt}; '
                           f'src: url(assets/fonts/{f}) format("woff2"); unicode-range: {RANGES[r]}; }}')
        return "\n".join(out)

    def grain(self):
        p = os.path.join(self.P, "assets", "grain.png")
        if not os.path.exists(p):
            grain_png(p)
        return "assets/grain.png"

    def dust_painter(self, canvas="dust", grain="grain", n=(2, 5)):
        """film dust + grain jitter, seeded by frame number (never wall-clock time), drawn on a canvas over everything"""
        self.js(f"""(() => {{ const cv = document.getElementById("{canvas}"), cx = cv.getContext("2d"), gr = document.getElementById("{grain}"); const P = {{u: 0}};
  const rnd = (s) => {{ let x = Math.sin(s * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }};
  const paint = () => {{ const f = Math.floor(tl.time() * {self.fps} + 1e-6); cx.clearRect(0, 0, {W}, {H}); const n = {n[0]} + Math.floor(rnd(f) * {n[1]});
    for (let i = 0; i < n; i++) {{ const x = rnd(f * 13 + i) * {W}, y = rnd(f * 29 + i * 7) * {H}, r = 1 + rnd(f * 3 + i) * 2.6;
      cx.fillStyle = "rgba(235,228,214," + (0.3 + rnd(f + i * 5) * 0.4).toFixed(2) + ")"; cx.beginPath();
      if (rnd(f * 7 + i) > 0.85) {{ cx.lineWidth = 1.2; cx.strokeStyle = cx.fillStyle; cx.moveTo(x, y); cx.quadraticCurveTo(x + 14, y + 8, x + 6 + rnd(i) * 30, y + 26); cx.stroke(); }}
      else {{ cx.arc(x, y, r, 0, Math.PI * 2); cx.fill(); }} }}
    if (gr) gr.style.backgroundPosition = Math.floor(rnd(f) * 480) + "px " + Math.floor(rnd(f + 9) * 480) + "px"; }};
  tl.fromTo(P, {{u: 0}}, {{u: 1, duration: {self.T}, ease: "none", onUpdate: paint, immediateRender: false}}, 0); }})();""")

    def write_page(self, css, body, fonts, lang=None):
        lang = lang or ("ru" if self.RU else "en")
        html = f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<script src="{GSAP}"></script>
<style>
{self.font_css(fonts)}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; }}
{css}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-width="{W}" data-height="{H}" data-duration="{self.T}" data-fps="{self.fps}">
{body}
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
{chr(10).join('  ' + x for x in self.base)}
{chr(10).join('  ' + x for x in self.tl)}
  window.__timelines["main"] = tl;
</script>
</body></html>
"""
        open(os.path.join(self.P, "index.html"), "w").write(html)

    def write_side_files(self, recipe, extra=None):
        b = os.path.join(self.P, "build")
        evs = sorted(self.events, key=lambda e: e["t"])
        json.dump({"total": self.T, "speech": r3(self.words[-1]["e"]), "voiceP95": r3(self.voice_p95()), "roleDb": ROLE_DB, "events": evs},
                  open(os.path.join(b, "sfx_events.json"), "w"), ensure_ascii=False, indent=1)
        json.dump({"total": self.T, "fps": self.fps, "shots": [], "beats": sorted(self.beats, key=lambda x: x["t0"])},
                  open(os.path.join(b, "beats.json"), "w"), ensure_ascii=False, indent=1)
        m, _ = self.check_budgets()
        plan = {"recipe": recipe, "metrics": m, "full": self.full, "inserts": self.inserts, "cover": self.cover,
                "beats": sorted(self.beats, key=lambda x: x["t0"]), **(extra or {})}
        json.dump(plan, open(os.path.join(b, "plan.json"), "w"), ensure_ascii=False, indent=1)
        return m

    def finish(self, recipe, extra=None, extra_cover=()):
        """write the side files, print the numbers, fail on a broken budget"""
        m = self.write_side_files(recipe, extra)
        _, errs = self.check_budgets(extra_cover)
        print(f"{recipe}: {self.T:.2f} s | face on screen {m['face_on_screen_pct']} % | full screen {m['full_screen_s']} s in "
              f"{m['full_screens']} (longest {m['longest_full_s']} s) | inserts {m['inserts']} ({m['inserts_per_min']}/min) | "
              f"sfx {m['sfx']} ({m['sfx_per_10s']} per 10 s) | voice p95 {self.voice_p95():.1f} dBFS")
        for n in self.notes:
            print("  " + n)
        for bt in sorted(self.beats, key=lambda x: x["t0"]):
            print(f"  {bt['t0']:6.2f}-{bt['t1']:<6.2f} {bt['type']:<8} {bt['id']:<10} {bt['label']}")
        if errs:
            raise BuildError("BUILD FAILED (fix the generator):\n  " + "\n  ".join(errs))
        print("index.html written; next: hf.sh lint, snap.py beats, finals.py preview")
        return m


def new_project(P, src, plate=None):
    """make a reel project P from an approved cut in `src` (a folder with assets/plate_alt.mp4 or plate.mp4, assets/voice.wav,
    build/words.cut.json or words.json and the cut's build/plan.json): symlinks to the picture (`plate` picks another one,
    e.g. plate_wide.mp4) and the voice, the words, build/cut_plan.json, build/cover_windows.json if the cut has one, and
    build/face.json tracked on the plate. Re-running it keeps what is there. Used by every builder on this base."""
    P, src = os.path.abspath(os.path.expanduser(P)), os.path.abspath(os.path.expanduser(src))
    for d in ("assets", "build"):
        os.makedirs(os.path.join(P, d), exist_ok=True)
    plate = plate or next((f for f in ("plate_alt.mp4", "plate.mp4") if os.path.exists(os.path.join(src, "assets", f))), None)
    if not plate or not os.path.exists(os.path.join(src, "assets", plate)):
        raise BuildError(f"no assets/{plate or 'plate_alt.mp4 or plate.mp4'} in {src}")
    for f in (plate, "voice.wav"):
        dst = os.path.join(P, "assets", f)
        if not os.path.lexists(dst):
            os.symlink(os.path.join(src, "assets", f), dst)
    for f, g in (("words.cut.json", "words.cut.json"), ("words.json", "words.json"), ("plan.json", "cut_plan.json"),
                 ("cover_windows.json", "cover_windows.json")):
        s_, d_ = os.path.join(src, "build", f), os.path.join(P, "build", g)
        if os.path.exists(s_) and not os.path.exists(d_):
            shutil.copy(s_, d_)
    fj = os.path.join(P, "build", "face.json")
    if not os.path.exists(fj):
        import sys
        subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "face_track.py"), os.path.join(P, "assets", plate), "--out", fj], check=True)
    print(f"{P}: assets/{plate}, voice.wav, build/{', '.join(sorted(os.listdir(os.path.join(P, 'build'))))}")
    return P


if __name__ == "__main__":
    import sys
    if "--new" in sys.argv:
        a = sys.argv
        new_project(a[a.index("--new") + 1], a[a.index("--from") + 1], a[a.index("--plate") + 1] if "--plate" in a else None)
    else:
        print("facereel.py --new $P --from <approved cut dir> [--plate plate_wide.mp4]   the project for any builder on this base")

