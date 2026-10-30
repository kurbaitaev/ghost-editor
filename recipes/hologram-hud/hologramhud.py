"""Hologram HUD: a talking-head reel cut between the speaker's face as shot and full-screen HUD scenes, where the thing the speaker talks about
is scanned into a glowing wireframe on a projector pad, target boxes lock onto its parts, values roll in from garbage
glyphs and turn amber the frame they become true, and finished values dock as chips in a rail that stays to the end.
Adapted from Lemo-Opuscar "Sci-fi Hologram HUD" (styles/hologram-hud, MIT, Copyright (c) 2026 LemoLab; CREDITS.txt).

    import sys; sys.path.insert(0, "<skill>/recipes/hologram-hud"); from hologramhud import Hud
    # an example reel (the phone as the first thing you touch every morning); times are word onsets in words.cut.json
    H = Hud("$P", dur=31.97, title="Morning Phone Hologram HUD", subject="PHONE // SCAN")   # words: build/words.cut.json
    H.face("F1", 0.00, 2.70, "t")                                     # the speaker's plate as shot; HUD subtitle + edge chrome only
    A = H.scene("A", 2.70, 4.48)                                      # a full-screen HUD scene (opaque stage)
    A.obj("phone", scan=(2.70, 3.75))                                 # models: phone, book, basics (engine/holohud.js)
    A.cam(2.70, yaw=.9, pitch=.45, dist=4.3, ty=.9, cy=860); A.cam(3.9, yaw=.45, pitch=.18, dist=3.8)
    A.lock(4.90, 6.40, ["book"], "SOURCE"); A.card(5.26, 6.40, "AUTHOR", "BOOK TITLE", y=1180, roll=(5.64, 6.10))
    A.marker(10.34, 12.58, "n1", "ALARM"); A.title(3.86, "PHONE"); A.status(2.70, "SCAN {pct}%", pct=(2.70, 3.75))
    H.chip(10.34, "Alerts", on=False)                                 # docks in the rail, stays in every later HUD scene
    H.sub(0.0, 2.70, "Your phone is the first thing ...")             # HUD subtitle (the speaker's words, exactly; one chunk per line)
    H.glitch(29.66); H.sfx("click-1", 5.12, 0.45); H.build()

Scene calls (A = H.scene(...)): obj(model, scan, erase, explode, spin, solid, dims, focus, flash, cover), cam(t, **params),
lock(t, t1, parts, tag), card(t, t1, label, value, y, roll, frm, dock, unit, detail, index, big), marker(t, t1, part, label),
title(t, text), status(t, text, pct), beam(t), pad_spin(keys). Camera params: yaw, pitch, dist, fov, tx/ty/tz (target),
cx/cy (where the target sits on screen); keys between are eased cubic in-out (the camera follows the box).

The house (house.json; never changes reel to reel): one cold hue + one warm accent spent only on locked values, the stage,
pad, wireframe engine, HUD furniture (corner brackets, rulers, subject // mode, live status), plates behind every text,
Exo 2 + JetBrains Mono (Latin + Cyrillic) at >= 48 px, the HUD subtitle, the 3-frame power-on into a HUD scene, the speaker's face as shot.
What changes every reel (catalog.json, components.py plan --style hologram-hud): the objects (models), what is locked and
in which order, the camera route, the opening and ending devices, the rail's chips.

Needs in $P: assets/{wide,tight,alt}.mp4 plates (any subset: plates={"t": "assets/tight.mp4"}), assets/voice.wav,
build/words.cut.json. No matte: nothing ever sits over the speaker's face, the HUD scenes replace the frame. Fonts and the engine are
copied / inlined by build(); SFX from the skill library (licensed sounds only).
"""
import json
import os
import re
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
HOUSE = json.load(open(os.path.join(HERE, "house.json"), encoding="utf-8"))
FPS = HOUSE["motion"]["fps"]
F1 = 1 / FPS


def fr(t):
    return round(round(t * FPS) / FPS, 4)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


class Scene:
    """one full-screen HUD scene; every call appends data the engine reads (engine/holohud.js drawHolo)"""

    def __init__(self, hud, name, t0, t1):
        self.hud, self.name = hud, name
        self.d = {"kind": "holo", "name": name, "t0": fr(t0), "t1": fr(t1), "objs": [], "cam": [], "locks": [], "cards": [],
                  "markers": [], "status": []}
        self.keys = [t0 + 0.12]

    def obj(self, model, scan=None, erase=None, explode=None, spin=None, solid=None, dims=None, focus=None, flash=None,
            cover=None, plane_r=None, box_exploded=False):
        """a model on the pad: scan=(t0, t1) grows it under the scan plane, erase=(t0, t1) scan-erases it top-down,
        explode=[{id, t0, t1, to, from}], spin=[(t, rad)] turntable keys, solid=(t0, t1) ignites the solid hologram,
        dims=[{id, t, to}] cools a part (switched off), focus=[{t0, t1, parts, dim}], flash=[{id, t}], cover={img, t}"""
        o = {"model": model}
        for k, v in (("scan", scan), ("erase", erase), ("explode", explode), ("solid", solid), ("dims", dims),
                     ("focus", focus), ("flash", flash), ("cover", cover), ("planeR", plane_r)):
            if v is not None:
                o[k] = v
        if spin:
            o["spin"] = [[fr(t), v] for t, v in spin]
        if box_exploded:
            o["boxExploded"] = True
        self.d["objs"].append(o)
        for v in (scan, erase, solid):
            if v:
                self.keys.append(v[1] + 0.05)
        return len(self.d["objs"]) - 1

    def cam(self, t, **kw):
        self.d["cam"].append([fr(t), kw])

    def lock(self, t, t1, parts, tag=None, obj=0, pad=None):
        """target box: oversized + rotated 45 deg, snaps to the parts in 0.22 s, a 3-frame white flash on the lock"""
        L = {"t": fr(t), "t1": fr(t1), "parts": parts, "obj": obj}
        if tag:
            L["tag"] = tag
        if pad is not None:
            L["pad"] = pad
        self.d["locks"].append(L)
        self.keys.append(t + 0.4)

    def card(self, t, t1, label, value, y, roll=None, frm=None, dock=None, unit=None, detail=None, index=None, big=None, x=130, w=820):
        """spec card: label rolls in, the value rolls from glyphs over roll=(t0, t1) and turns accent on t1 (one-frame flash);
        frm=(obj, part) draws the leader from that part; dock=t fades the card (it went to the rail as a chip)"""
        c = {"t": fr(t), "t1": fr(t1), "label": label, "value": value, "y": y, "x": x, "w": w}
        for k, v in (("roll", roll), ("dock", dock), ("unit", unit), ("detail", detail), ("index", index), ("big", big)):
            if v is not None:
                c[k] = v
        if frm:
            c["from"] = {"obj": frm[0], "part": frm[1]}
        self.d["cards"].append(c)
        self.keys += [t + 0.4, (roll[1] if roll else t) + 0.15]

    def marker(self, t, t1, part, label, obj=0, dir=1, dy=0, acc=False, gap=None):
        """hotspot ring on a part with its label on a dark plate (rolls in; acc=True turns the label accent once rolled)"""
        m = {"t": fr(t), "t1": fr(t1), "part": part, "label": label, "obj": obj, "dir": dir, "dy": dy, "acc": acc}
        if gap is not None:
            m["gap"] = gap
        self.d["markers"].append(m)
        self.keys.append(t + 0.45)

    def title(self, t, text, sub=None, x=96, y=400, size=140, track=18):
        self.d["title"] = {"t": fr(t), "text": text, "sub": sub, "x": x, "y": y, "size": size, "track": track}
        self.keys.append(t + 0.7)

    def status(self, t, text, pct=None):
        """top-right live status; '{pct}' counts 000-100 over pct=(t0, t1) (a real progress, e.g. the scan)"""
        self.d["status"].append([fr(t), text] + (list(pct) if pct else []))

    def beam(self, t, y1=1.3):
        self.d["beam"] = [fr(t), 0, y1]
        self.keys.append(t + 0.4)

    def pad_spin(self, keys):
        self.d["padSpin"] = [[fr(t), v] for t, v in keys]


class Hud:
    def __init__(self, project, dur, title, subject=None, plates=None, words="build/words.cut.json", voice="assets/voice.wav",
                 hue=None, accent=None, lang="ru"):
        self.P = os.path.abspath(os.path.expanduser(project))
        self.dur, self.page_title, self.lang = dur, title, lang
        self.subject = subject or HOUSE["chrome"]["subject_default"]
        d = json.load(open(f"{self.P}/{words}", encoding="utf-8"))
        raw = [w for s in d["segments"] for w in s["words"]] if "segments" in d else d["words"]
        self.W = [(w["word"].strip(), w["start"], w["end"]) for w in raw]
        self.plates_ = plates or {"w": "assets/wide.mp4", "t": "assets/tight.mp4", "a": "assets/alt.mp4"}
        self.voice = voice
        self.voice_dur = round(probe_dur(f"{self.P}/{voice}"), 2)
        self.hue = HOUSE["palette"]["hue"] if hue is None else hue
        self.accent = HOUSE["palette"]["accent"] if accent is None else accent
        self.scenes, self.subs, self.chips, self.glitches, self.SFX, self.BEATS = [], [], [], [], [], []
        self.images = {}

    def when(self, word, after=0.0):
        """onset of the first word equal to `word` (punctuation ignored) at or after `after` seconds"""
        k = lambda s: re.sub(r"[^\w-]", "", s.lower())
        for w, s, e in self.W:
            if s >= after - 1e-6 and k(w) == k(word):
                return s
        raise KeyError(word)

    def face(self, name, t0, t1, plate, status=None):
        """the speaker's plate as shot: no grade, nothing over the speaker's face; the HUD subtitle sits low (y <= 1690) and the edge chrome
        frames it, so the face worlds and the HUD worlds read as one interface"""
        sc = {"kind": "face", "name": name, "t0": fr(t0), "t1": fr(t1), "plate": plate}
        if status:
            sc["status"] = [[fr(t0), status]]
        self.scenes.append(sc)
        self.BEATS.append({"id": name, "type": "face", "label": name, "t0": round(t0, 3), "t1": round(t1, 3), "keys": [round(t0 + 0.3, 3)]})

    def scene(self, name, t0, t1):
        s = Scene(self, name, t0, t1)
        self.scenes.append(s)
        return s

    def chip(self, t, label, on=True):
        self.chips.append({"t": fr(t), "label": label, "on": on})

    def sub(self, t0, t1, text):
        self.subs.append({"t0": fr(t0), "t1": fr(t1), "text": text})

    def glitch(self, t):
        """the one 3-frame glitch of the reel (on the biggest change)"""
        self.glitches.append(fr(t))

    def image(self, el_id, src):
        """an <img> the engine can draw (the book cover); src relative to the project"""
        self.images[el_id] = src

    def sfx(self, name, t, vol, ms=0.0, dur=None):
        man = json.load(open(f"{SKILL}/library/sfx/manifest.json", encoding="utf-8"))
        items = man if isinstance(man, list) else man.get("sounds", man)
        row = next((s for s in items if (s.get("name") or s.get("id")) == name), None) if isinstance(items, list) else items.get(name)
        if row is None or row.get("licensed") is False:
            raise ValueError(f"{name}: not a licensed sound in library/sfx/manifest.json")
        os.makedirs(f"{self.P}/assets/sfx", exist_ok=True)
        dst = f"{self.P}/assets/sfx/{name}.wav"
        if not os.path.exists(dst):
            shutil.copy(f"{SKILL}/library/sfx/{row.get('file', name + '.wav')}", dst)
        self.SFX.append((name, max(0.0, t), vol, ms, dur))

    # ------------------------------------------------------------ write
    def _fonts(self):
        os.makedirs(f"{self.P}/assets/fonts", exist_ok=True)
        shutil.copy(f"{HERE}/fonts/exo2.woff2", f"{self.P}/assets/fonts/exo2.woff2")
        for sub in ("cyrillic", "latin"):
            shutil.copy(f"{SKILL}/templates/fonts/jetbrains-mono-{sub}.woff2", f"{self.P}/assets/fonts/jetbrains-mono-{sub}.woff2")
        cyr = "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116"
        lat = "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2212, U+FEFF, U+FFFD"
        return (f"@font-face {{ font-family: 'Exo 2'; src: url('assets/fonts/exo2.woff2') format('woff2'); font-weight: 100 900; font-style: normal; }}\n"
                f"@font-face {{ font-family: 'JetBrains Mono'; src: url('assets/fonts/jetbrains-mono-cyrillic.woff2') format('woff2'); font-weight: 100 800; unicode-range: {cyr}; }}\n"
                f"@font-face {{ font-family: 'JetBrains Mono'; src: url('assets/fonts/jetbrains-mono-latin.woff2') format('woff2'); font-weight: 100 800; unicode-range: {lat}; }}\n")

    def build(self):
        """-> index.html (plates + one HUD canvas painted from a paused GSAP timeline), build/beats.json, build/coverage.txt"""
        DUR, P = self.dur, self.P
        scenes = []
        for s in self.scenes:
            if isinstance(s, Scene):
                scenes.append(s.d)
                self.BEATS.append({"id": s.name, "type": "holo", "label": s.name, "t0": s.d["t0"], "t1": s.d["t1"],
                                   "keys": sorted({round(min(max(k, s.d["t0"] + 0.05), s.d["t1"] - 0.05), 3) for k in s.keys})})
            else:
                scenes.append(s)
        scenes.sort(key=lambda s: s["t0"])
        for a, b in zip(scenes, scenes[1:]):
            assert abs(a["t1"] - b["t0"]) < 1e-3, f"gap or overlap between {a['name']} and {b['name']}"
        assert scenes[0]["t0"] == 0 and abs(scenes[-1]["t1"] - fr(DUR)) < 0.04, "scenes must cover 0 .. dur"
        SC = {"hue": self.hue, "accent": self.accent, "subject": self.subject, "scenes": scenes, "subs": self.subs,
              "chips": self.chips, "glitch": self.glitches, "words": [[round(s, 3), round(e, 3)] for _, s, e in self.W]}
        faces = self._fonts()
        engine = open(f"{HERE}/engine/holohud.js", encoding="utf-8").read()
        vids = "\n".join(f'<video id="v{k}" class="full" src="{v}" data-start="0" data-duration="{DUR:.2f}" data-track-index="{i}" muted playsinline style="opacity:0"></video>'
                         for i, (k, v) in enumerate(self.plates_.items()))
        imgs = "\n".join(f'<img id="{k}" src="{v}" alt="" style="display:none">' for k, v in self.images.items())
        js = []
        for s in scenes:            # the plate of each face world shows; the HUD canvas covers everything in HUD worlds
            if s["kind"] == "face":
                for k in self.plates_:
                    js.append(f'tl.set("#v{k}", {{opacity: {1 if k == s["plate"] else 0}}}, {s["t0"]:.4f});')
        aud = [f'<audio id="vo" src="{self.voice}" data-start="0" data-duration="{self.voice_dur:.2f}" data-track-index="40" data-volume="1"></audio>']
        for i, (f, t, v, ms, dur) in enumerate(self.SFX):
            dd = min(dur or round(probe_dur(f"{P}/assets/sfx/{f}.wav"), 3), DUR - t)
            aud.append(f'<audio id="sfx{i}" src="assets/sfx/{f}.wav" data-start="{fr(t):.4f}" data-duration="{dd:.4f}" data-media-start="{ms:.3f}" '
                       f'data-track-index="{50 + i}" data-volume="{v}"></audio>')
        html = f"""<!doctype html>
<html lang="{self.lang}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{esc(self.page_title)}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{faces}html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
.full {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }}
video.full {{ object-fit: cover; }}
#fontwarm {{ position: absolute; left: -4000px; top: 0; font-size: 48px; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{DUR:.2f}" data-fps="{FPS}">
<div id="fontwarm"><span style="font-family:'Exo 2';font-weight:300">Жж 0</span><span style="font-family:'Exo 2';font-weight:500">Жж 0</span><span style="font-family:'Exo 2';font-weight:600">Жж 0</span><span style="font-family:'Exo 2';font-weight:700">Жж 0</span><span style="font-family:'JetBrains Mono';font-weight:500">Жж 0 A</span></div>
{vids}
{imgs}
<canvas id="hud" class="full" width="1080" height="1920" style="z-index:5"></canvas>
{chr(10).join(aud)}
<script>
{engine}
</script>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
const SC = {json.dumps(SC, ensure_ascii=False)};
const hudCtx = document.getElementById("hud").getContext("2d");
const paint = () => window.HH.render(hudCtx, tl.time(), SC);
{chr(10).join(js)}
const PX = {{u: 0}};
tl.fromTo(PX, {{u: 0}}, {{u: 1, duration: {DUR:.2f}, ease: "none", onUpdate: paint, immediateRender: false}}, 0);
tl.set({{}}, {{}}, {DUR:.2f});
window.__timelines["main"] = tl;
paint();
document.fonts.ready.then(paint);
document.querySelectorAll("#root img").forEach((im) => im.addEventListener("load", paint));
</script>
</div>
</body>
</html>
"""
        open(f"{P}/index.html", "w", encoding="utf-8").write(html)
        shots = [{"t0": s["t0"], "t1": s["t1"]} for s in scenes if s["kind"] == "holo"]
        json.dump({"fps": FPS, "beats": sorted(self.BEATS, key=lambda b: b["t0"]), "shots": shots}, open(f"{P}/build/beats.json", "w"), indent=1)
        face_s = sum(s["t1"] - s["t0"] for s in scenes if s["kind"] == "face")
        lines = [f"face on screen: {face_s:.2f} s of {DUR:.2f} s = {100 * face_s / DUR:.1f} %",
                 f"scenes: {len(scenes)} ({sum(s['kind'] == 'holo' for s in scenes)} HUD); subtitles: {len(self.subs)}; chips: {len(self.chips)}; "
                 f"sfx: {len(self.SFX)} ({10 * len(self.SFX) / DUR:.1f} per 10 s); html {len(html) // 1024} KB"]
        open(f"{P}/build/coverage.txt", "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return lines


if __name__ == "__main__":
    print(__doc__)
