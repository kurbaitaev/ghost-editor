"""Kinetic doc: the narration made visible, in a black-and-white archive world with one red accent.

    import sys; sys.path.insert(0, "<skill>/recipes/kinetic-doc"); from kdoc import *
    K = KineticDoc("$P", fmt="A", fixes={...}, music={"id": "staring-at-the-night-sky", "db": -19})   # A / B / C
    K.picture("tray", "assets/pics/tray.jpg", K.t("there is a rule"), K.t("^done") + 0.3, "...", frame="print")
    K.page("turn", a, b, "grey", [[("small", "small", "big")], [("enough to", "enough", "s")]])
    K.label("lab", a, b, "TIRED", sub="by the evening", at=K.t("tired"))
    K.counter("n25", a, b, 25, at=K.t("25"), host="timer")
    K.build(BIG={"tomorrow", ...}, RED={"now"}, SERIF={"getting"})

Formats (the same house look in all three; recipes/kinetic-doc/SYSTEM.md):
  A  the speaker's talking head: the plate AS SHOT (no grade, no filter, no grain, no dim, nothing on the face), the facereel
     budgets (face on screen >= 65 %, full-screen <= 2.5 s each, <= 3 inserts a minute, every look-away covered);
  B  a voice-over over designed pages and pictures (no plate): every moment is a scene;
  C  B-roll only + a voice-over (no plate): the same, the pictures are footage.
The house (house.json): one centred caption line in which every word pops on, in one frame, at its spoken start; one
big heavy word per idea in Oswald caps, the small words in Inter Medium, quotes and coined terms in Playfair italic;
pictures in black and white as prints on their own blurred copy, windows on black, polaroids on a grey page; turn lines
on a grey page with a black block cursor that runs ahead of each word; one red accent (#D63A2F); hard cuts only (no
dissolves, no flashes, no glitches, no fade at the end); print texture and a falloff on pages and pictures only; a flat
bed ~19 dB under the voice, SFX only under picture events (scene cuts, camera moves, counters), never under text.
What changes every reel (components.py plan --style kinetic-doc): the pictures, the hook device, the page treatments,
the hidden-cut transition, the number device and the ending.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "lib"))
from facereel import (Reel, BuildError, SAFE, LIB, X264_THREADS, esc, norm, r3, W, H, load_words, probe_duration)  # noqa: E402,F401

HOUSE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "house.json")))
PAL = HOUSE["palette"]
INK, WHITE, RED, BLACK = PAL["ink"], PAL["white"], PAL["red"], PAL["black"]
CAP_SMALL, CAP_BIG, CAP_W = 62, 168, 940      # px: small words, the big word (max), the line's width
EM_SMALL, EM_BIG = 0.56, 0.6                  # average advance per character (Inter 500 / Oswald 700 caps, Cyrillic)
HOOK_PUSH = (1.05, 1.1)                       # A: the plate pushes in to x1.05 over the first 1.1 s (ease out)
PRE = {"в", "во", "с", "со", "из", "на", "о", "об", "у", "к", "ко", "по", "за", "не", "ни", "и", "а", "но", "от", "до", "для",
       "то", "что", "как", "a", "an", "the", "to", "of", "in", "on", "at", "and", "but", "not", "no", "for", "with"}
FRAMES = ("print", "window", "full")
PRINT_CY = 700                                # the print / window centre (the caption block starts at ~1130-1240)


def media_size(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", p],
                         capture_output=True, text=True).stdout.strip().split(",")
    return int(out[0]), int(out[1])


class KineticDoc(Reel):
    def __init__(self, project, fmt="A", cap_top=None, budget="talking-head", **kw):
        """budget (format A): "talking-head" = facereel's (face on screen >= 65 %, <= 3 inserts a minute); "hybrid" = the
        face for the hook, the turns and the payoff, the middle at the references' pace (face >= 40 %, no insert cap);
        every full-screen moment still <= 2.5 s, every look-away covered, nothing on the face"""
        if budget not in ("talking-head", "hybrid"):
            raise BuildError(f"budget {budget!r}: talking-head or hybrid")
        self.budget = budget
        fmt = fmt.upper()
        if fmt not in ("A", "B", "C"):
            raise BuildError(f"fmt {fmt!r}: A (talking head), B (voice-over + visuals) or C (B-roll only + voice-over)")
        self.fmt = fmt
        if fmt == "A":
            super().__init__(project, **kw)
        else:
            self._voice_only(project, **kw)
        self.cap_top = cap_top
        self.scenes, self.punches, self.labels, self.nocap = [], [], [], []
        self.marks = []                       # visual events that land inside a scene (pace)
        self.light = []                       # scenes on a light ground: captions over them are set in ink
        self.quiet_after = None
        self._ids, self._burst = set(), None
        self._effects = {}
        if fmt == "A":
            ms = sorted(x[6] for x in self.face if len(x) > 6 and x[6] is not None)
            self.zoom_y = round(ms[len(ms) // 2]) if ms else int(H * 0.5)

    def _voice_only(self, project, voice="assets/voice.wav", words=None, fixes=None, tail=0.45, fps=30, music=None, vcut=None,
                    plate=None, cover=None):
        """B and C have no plate and no face: the voice and its words carry the timeline"""
        self.P = os.path.abspath(os.path.expanduser(project))
        self.fps = fps
        os.makedirs(os.path.join(self.P, "assets"), exist_ok=True)
        os.makedirs(os.path.join(self.P, "build"), exist_ok=True)
        self.plate_src = None
        self.voice = self._find(voice, [], "the voice")
        wp = self._find(words, ["build/words.json", "build/words.edit.json", "build/words.cut.json"], "the words")
        self.words = load_words(wp, fixes)
        if not self.words:
            raise BuildError(f"no words in {wp}")
        self.TV = r3(probe_duration(self.voice) if not vcut else min(probe_duration(self.voice), vcut))
        self.tail = tail
        self.T = r3(self.TV + tail)
        self.RU = sum(1 for x in self.words if re.search("[Ѐ-ӿ]", x["raw"])) * 2 > len(self.words)
        self.tl, self.base, self.based, self.css, self.html = [], [], set(), [], []
        self.events, self.beats, self._guards, self.notes = [], [], [], []
        self.full, self.inserts, self.capoff = [], [], []
        self.face, self.cover = [], []
        self.music = music
        self._voice_p95 = None
        self._sfx_man = json.load(open(os.path.join(LIB, "sfx", "manifest.json")))
        self._track = 30

    # ---------------------------------------------------------------- helpers
    def _id(self, i):
        if i in self._ids or (i[:1] == "c" and i[1:].isdigit()):
            raise BuildError(f"id {i!r} is taken (caption ids are c0, c1, ...: never name an element c<n>)")
        self._ids.add(i)
        return i

    def mark(self, tag):
        """name a slot component that is not a scene of its own (an ending held on the face): catalog sigs read it"""
        self.html.append(f"<!-- kd-tag: {tag} -->")

    def quiet(self, t):
        """no SFX from t on: the payoff runs on the voice and the bed alone"""
        self.quiet_after = t

    def sound(self, sid, at, why="", db=0.0, maxlen=None, gap=0.3, foley_gap=0.9):
        if self.quiet_after is not None and at >= self.quiet_after - 0.02:
            return None
        return super().sound(sid, at, why, db, maxlen, gap, foley_gap)

    # where the face is on screen at t (A): the hook push, then punch-ins on top
    def view(self, t):
        k = min(1.0, max(0.0, t / HOOK_PUSH[1]))
        d = 1.0 + (HOOK_PUSH[0] - 1.0) * (1 - (1 - k) ** 2)
        p = 1.0
        for at, hold, sc in self.punches:
            if at - 0.02 <= t <= at + hold + 0.25:
                p = sc
        return d, p

    def xf(self, t, box):
        if self.fmt != "A":
            return box
        d, p = self.view(t)
        ox, oy, zy = W * 0.5, H * 0.36, self.zoom_y
        f = lambda x, y: (W / 2 + (ox + (x - ox) * d - W / 2) * p, zy + (oy + (y - oy) * d - zy) * p)
        (l2, t2), (r2, b2) = f(box[0], box[1]), f(box[2], box[3])
        return [l2, t2, r2, b2]

    # ---------------------------------------------------------------- baked looks (no CSS blur / filter / gradient)
    def _kd(self, src, tag, ext, make):
        """a derived file in assets/kd/, rebuilt when its source changes (B&W copies, blurred backdrops, page grounds):
        HyperFrames' capture turns black when a page carries many CSS blurs, filters and gradients, so they are baked"""
        os.makedirs(os.path.join(self.P, "assets", "kd"), exist_ok=True)
        p = src if os.path.isabs(src) else os.path.join(self.P, src)
        key = hashlib.md5(f"{p}|{os.path.getmtime(p) if os.path.exists(p) else 0}|{tag}".encode()).hexdigest()[:10]
        rel = os.path.join("assets", "kd", f"{os.path.splitext(os.path.basename(src))[0]}-{tag}-{key}.{ext}")
        if not os.path.exists(os.path.join(self.P, rel)):
            make(p, os.path.join(self.P, rel))
        return rel

    def _bw(self, src):
        """the house black and white: desaturated, a touch more contrast (stills -> jpg, footage -> H.264)"""
        if src.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
            return self._kd(src, "bw", "mp4", lambda i, o: subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", i, "-an", "-vf", "hue=s=0,eq=contrast=1.08:brightness=-0.01",
                 "-c:v", "libx264", "-threads", X264_THREADS, "-crf", "14", "-preset", "medium", "-g", "30", "-pix_fmt", "yuv420p",
                 "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", o], check=True))
        return self._kd(src, "bw", "jpg", lambda i, o: subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", i, "-vf", "hue=s=0,eq=contrast=1.08:brightness=-0.01", "-q:v", "2", o],
            check=True))

    def _blur(self, src, at=0.0, bw=True):
        """the print's backdrop: the picture (or one frame of the footage) small, blurred, darkened"""
        vf = ("hue=s=0," if bw else "") + "scale=360:-2,gblur=sigma=14,eq=brightness=-0.30:contrast=0.92"
        def make(i, o):
            pre = ["-ss", f"{at:.3f}"] if i.lower().endswith((".mp4", ".mov", ".m4v", ".webm")) else []
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *pre, "-i", i, "-frames:v", "1", "-vf", vf, "-q:v", "3", o], check=True)
        return self._kd(src, f"blur{'' if bw else 'c'}{int(at * 10)}", "jpg", make)

    def _ground(self, kind):
        """a page ground, 1080x1920: grey (#DDDDDD -> #A1A1A1) or warm paper (#E6E1D6 -> #A9A49B), radial falloff + grain"""
        c, e = {"grey": ((221, 221, 221), (161, 161, 161)), "paper": ((230, 225, 214), (169, 164, 155)),
                "type": ((230, 225, 214), (169, 164, 155)), "dark": ((46, 46, 46), (12, 12, 12))}[kind]
        f = "min(1,pow(hypot((X-540)/640,(Y-860)/1080),1.7))"
        expr = ":".join(f"{ch}='{c[k]}-{c[k] - e[k]}*{f}'" for k, ch in enumerate("rgb"))
        def make(_i, o):
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:d=1", "-vf",
                            f"format=rgb24,geq={expr},noise=alls=6:allf=u", "-frames:v", "1", "-q:v", "2", o], check=True)
        return self._kd(__file__, f"ground-{kind}", "jpg", make)

    # ---------------------------------------------------------------- scenes (full screen)
    def _scene(self, sid, a, b, cls, inner, what, kd, caps=True, sfx="whoosh-cine", sfx_db=-2.0, tag=None):
        """a full-screen scene from a to b: hard cut in, hard cut out (no dissolve, no flash)"""
        self._id(sid)
        if self.fmt == "A":
            self.full_screen(sid, a, b, what)
        self.scenes.append((r3(a), r3(b), sid, what))
        tg = f' data-tag="{tag}"' if tag else ""          # a slot component's name (catalog.json sigs read it)
        self.html.append(f'<div id="{sid}" class="scene {cls}" data-kd="{kd}"{tg}>{inner}</div>')
        self.st(f"#{sid}", {"autoAlpha": 0}, 0)
        self.st(f"#{sid}", {"autoAlpha": 1}, a)
        if b < self.T - 0.02:
            self.st(f"#{sid}", {"autoAlpha": 0}, b)
        if not caps:
            self.capoff.append((a, b))
        if sfx:
            self.sound(sfx, a - 0.12, f"{sid} in", db=sfx_db)
        self.beat(sid, kd, a, b, what)

    def _media(self, iid, src, a, b, cls, media_start=0.0):
        """an <img> or a muted <video> (footage keeps its own timing: data-start = the scene's a)"""
        if src.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
            self._track += 1
            return (f'<video id="{iid}" class="clip {cls}" src="{src}" data-start="{a:.3f}" data-duration="{b - a:.3f}" '
                    f'data-media-start="{media_start:.3f}" data-track-index="{self._track}" muted playsinline></video>')
        return f'<img id="{iid}" class="{cls}" src="{src}">'

    def picture(self, pid, src, a, b, line, frame="print", kind="ai", bw=True, push=1.06, media_start=0.0, label=None,
                label_at=None, caps=True, sfx="whoosh-cine", his_face=False, focus=(0.5, 0.5), tag=None, person=False):
        """one picture as an object, full screen from a to b:
          print   the sharp picture over its own blurred, darkened copy (the 16:9 -> 9:16 bridge), slow push;
          window  the picture in a frame on black that steps up in three sizes (4 frames apart), then a slow push;
          full    the picture full bleed (cover), slow push.
        bw=True turns the picture black and white (the house world). his_face=True (footage where the speaker is on screen) keeps
        it in colour: the speaker's face is never regraded. `label` = a serif name line under the picture, on at label_at.
        person=True (a portrait): the print sits on a dark ground, not on its blurred copy (a blurred figure is a person
        the people check cannot read)."""
        if frame not in FRAMES:
            raise BuildError(f"{pid}: frame {frame!r} ({', '.join(FRAMES)})")
        p = src if os.path.isabs(src) else os.path.join(self.P, src)
        if not os.path.exists(p):
            raise BuildError(f"{pid}: {src} not found")
        iw, ih = media_size(p)
        self.insert(pid, src, a, b, line, frame, kind)
        grey = bw and not his_face                        # the speaker's face is never regraded: footage with them stays in colour
        fx, fy = focus
        img = self._bw(src) if grey else src
        media = self._media(pid + "-im", img, a, b, "fill", media_start)
        if frame == "print":
            s = min(980 / iw, 800 / ih)
            w, h = int(iw * s), int(ih * s)
            x, y = (W - w) // 2, int(PRINT_CY - h / 2)
            if person:
                bgimg = f'<div class="ground" style="background-image:url({self._ground("dark")})"></div>'
            else:
                bgimg = f'<img class="blurbg" src="{self._blur(src, media_start + (b - a) / 2, bw=grey)}">'
            inner = (bgimg +
                     f'<div class="pr" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><div class="pz">{media}</div></div>')
        elif frame == "window":
            s = min(900 / iw, 760 / ih)
            w, h = int(iw * s), int(ih * s)
            x, y = (W - w) // 2, int(PRINT_CY - h / 2)
            inner = f'<div class="pr win" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><div class="pz">{media}</div></div>'
        else:
            x, y, w, h = 0, 0, W, H
            inner = f'<div class="pr fullpr" style="left:0;top:0;width:{W}px;height:{H}px"><div class="pz">{media}</div></div>'
        if label:            # a museum line inside the picture's lower edge, on a dark band (a baked look: no gradient)
            inner += (f'<div class="plabel" id="{pid}-lab" style="left:{x}px;top:{y + h - 96}px;width:{w}px">'
                      f'<span>{esc(label)}</span></div>')
        inner += '<div class="dim"></div>'
        self._scene(pid, a, b, f"pic {frame}", inner, f"{frame}: {line}", f"pic-{frame}", caps=caps, sfx=sfx, tag=tag)
        if frame != "full":
            self.st(f"#{pid} .pz img, #{pid} .pz video", {"objectPosition": f"{fx * 100:.0f}% {fy * 100:.0f}%"}, 0)
        sel = f"#{pid} > .pr"
        t0 = a
        if frame == "window":
            for k, sc in enumerate((0.62, 0.8, 1.0)):
                self.st(sel, {"scale": sc}, a + k * 0.134 if k else a)
            t0 = a + 0.27
            self.st(sel, {"scale": 0.62}, 0)
        if push and push != 1.0:
            self.ft(sel, {"scale": 1.0}, {"scale": push, "duration": round(max(0.2, b - t0), 3), "ease": "power1.inOut"}, t0)
        if label:
            self.st(f"#{pid}-lab", {"autoAlpha": 0}, 0)
            self.st(f"#{pid}-lab", {"autoAlpha": 1}, label_at if label_at is not None else a + 0.3)
        return (x, y, w, h)

    def burst(self, bid, items, line, kind="ai"):
        """the ONE montage burst a reel may have, in the hook only: [(src, at), ...] full-bleed B&W pictures cut on their
        words (objects, places or single men, never crowds). Each holds to the next; the last holds to `items[-1][2]`."""
        if self._burst:
            raise BuildError(f"{bid}: one burst per reel (already {self._burst})")
        if items[0][1] > 3.5:
            raise BuildError(f"{bid}: a burst belongs to the hook (first 3.5 s), not at {items[0][1]:.2f} s")
        self._burst = bid
        for k, it in enumerate(items):
            src, at = it[0], it[1]
            end = items[k + 1][1] if k + 1 < len(items) else it[2]
            self.picture(f"{bid}{k}", src, at, end, line, frame="full", kind=kind, push=1.04,
                         sfx="whoosh-cine" if k == 0 else None)

    def page(self, pid, a, b, kind, lines, cursor=True, what="", sfx="whoosh-2", tag=None):
        """a type-only page for a turn line, full screen from a to b, the captions off (the page shows the words).
          kind: grey (black type on a grey page with a vignette), black (white caps with a soft glow on black),
                paper (ink on warm paper), type (a typewriter line on warm paper, ~1 character a frame + a bar cursor)
          lines: [[(text, word_ref, style[, px]), ...], ...]; style s (Inter 600), big (Oswald caps), serif (Playfair italic),
                 red (Oswald caps in the accent). Each token pops on at its word; with cursor=True a black block the size
                 of the token stands in its place 3 frames before (grey / paper pages)."""
        if kind not in ("grey", "black", "paper", "type"):
            raise BuildError(f"{pid}: page kind {kind!r}")
        toks, rows = [], []
        k = 0
        for line in lines:
            row = []
            for tok in line:
                text, ref, style = tok[:3]
                size = tok[3] if len(tok) > 3 and tok[3] else None
                if style in ("big", "red"):          # a big word never runs off the page
                    size = int(min(size or 210, 900 / max(1, EM_BIG * len(text))))
                px = f' style="font-size:{size}px"' if size else ""
                at = self.t(ref, after=a - 0.5, what=f"page {pid}") if isinstance(ref, str) else float(ref)
                tid = f"{pid}t{k}"
                k += 1
                toks.append((tid, text, at, style))
                if kind == "type":
                    chars = "".join(f'<i id="{tid}c{j}" class="ch">{esc(c) if c != " " else "&nbsp;"}</i>' for j, c in enumerate(text))
                    row.append(f'<span class="tk {style}"{px}>{chars}</span>')
                else:
                    row.append(f'<span class="tk {style}" id="{tid}"{px}><span class="cur"></span><span class="tx">{esc(text)}</span></span>')
            rows.append('<div class="pl">' + " ".join(row) + "</div>")
        if kind == "type":          # the caret rides at the end of the typed text
            rows[-1] = rows[-1][:-len("</div>")] + f'<span class="caret" id="{pid}-caret"></span></div>'
        caret = ""
        ground = f'<div class="ground" style="background-image:url({self._ground(kind)})"></div>' if kind != "black" else ""
        inner = f'{ground}<div class="pagebox">{"".join(rows)}{caret}</div>'
        self._scene(pid, a, b, f"page {kind}", inner, what or "page: " + " / ".join(t[1] for t in toks), f"page-{kind}",
                    caps=False, sfx=sfx, sfx_db=-4, tag=tag)
        for tid, text, at, style in toks:
            at = max(a, at)
            if kind == "type":
                for j in range(len(text)):
                    self.st(f"#{tid}c{j}", {"autoAlpha": 0}, 0)
                    self.st(f"#{tid}c{j}", {"autoAlpha": 1}, r3(at + j / self.fps))
            else:
                self.st(f"#{tid} .tx", {"autoAlpha": 0}, 0)
                self.st(f"#{tid} .cur", {"autoAlpha": 0}, 0)
                if cursor and kind != "black":
                    self.st(f"#{tid} .cur", {"autoAlpha": 1}, r3(max(a, at - 3 / self.fps)))
                    self.st(f"#{tid} .cur", {"autoAlpha": 0}, r3(max(a, at) + 0.001))
                self.st(f"#{tid} .tx", {"autoAlpha": 1}, r3(at))
        if kind == "type":
            self.st(f"#{pid}-caret", {"visibility": "hidden"}, 0)
            self.st(f"#{pid}-caret", {"visibility": "visible"}, r3(max(a, toks[-1][2])))
            self.js(f'tl.fromTo("#{pid}-caret", {{opacity: 1}}, {{opacity: 0, duration: 0.5, ease: "steps(1)", repeat: '
                    f'{max(1, int((b - a) / 0.5))}, yoyo: true, immediateRender: false}}, {a:.3f});')
        return toks

    def polaroids(self, pid, a, b, items, line, kind="ai", page="grey", sfx="shutter-1", caps=True):
        """polaroids on a page: [(src, label, word_ref), ...]; each one lands on its word and the camera slides so the
        newest is centred (0.35 s, eased). Captions stay on under them."""
        n = len(items)
        pw, gap = 600, 90
        cards = []
        for k, (src, lab, ref) in enumerate(items):
            p = src if os.path.isabs(src) else os.path.join(self.P, src)
            if not os.path.exists(p):
                raise BuildError(f"{pid}: {src} not found")
            self.insert(f"{pid}{k}", src, a, b, line, "polaroid", kind)
            rot = (-3.5, 2.8, -1.6, 3.4, -2.4)[k % 5]
            x = k * (pw + gap)
            cards.append(f'<div class="pol" id="{pid}p{k}" style="left:{x}px;transform:rotate({rot}deg)"><div class="ph">'
                         f'{self._media(pid + "i" + str(k), self._bw(src), a, b, "fill")}</div><div class="polab">{esc(lab)}</div></div>')
        inner = f'<div class="ground" style="background-image:url({self._ground(page)})"></div><div class="track" id="{pid}-track">{"".join(cards)}</div>'
        self._scene(pid, a, b, "pols", inner, f"polaroids: {line}", "polaroids", caps=caps, sfx=None)
        self.light.append((a, b))
        cx = (W - pw) / 2
        self.st(f"#{pid}-track", {"x": cx}, 0)
        for k, (src, lab, ref) in enumerate(items):
            at = self.t(ref, after=a - 0.5, what=f"polaroid {pid}{k}") if isinstance(ref, str) else float(ref)
            at = max(a, at)
            self.st(f"#{pid}p{k}", {"autoAlpha": 0}, 0)
            self.st(f"#{pid}p{k}", {"autoAlpha": 1}, at)
            self.marks.append(r3(at))
            if k:
                self.tween(f"#{pid}-track", {"x": cx - (k - 1) * (pw + gap)}, {"x": cx - k * (pw + gap), "duration": 0.35, "ease": "power2.inOut"}, at - 0.05)
            if sfx:
                self.sound(sfx, at - 0.02, f"{pid} polaroid {k}", db=-6, gap=0.2)

    # ---------------------------------------------------------------- labels, numbers, camera
    def label(self, lid, a, b, text, at=None, sub=None, sub_at=None, y=None, host=None, dim=True, caps=None):
        """a red box that wipes on left to right and reveals its text (Oswald caps, white), with an optional sub-line
        strip (white, ink). In A it sits in the chest band, clear of the face; over a picture (host = its id) the picture
        dims to x0.6 under it. No exit: it leaves with its scene."""
        self._id(lid)
        at = a if at is None else at
        fs = int(min(130, 860 / max(1, EM_BIG * len(text))))
        if y is None:
            y = self._cap_top() - 40 if self.fmt == "A" else 980
        h = fs + 54 + ((70 if sub else 0))
        if self.fmt == "A" and not host:
            self.guard(f"label {lid} «{text}»", (60, y, 960, h), at, b)
        sfs = int(min(48, 880 / max(1, EM_SMALL * len(sub)))) if sub else 48
        sub_html = f'<div class="lsub" id="{lid}-sub" style="font-size:{sfs}px"><span>{esc(sub)}</span></div>' if sub else ""
        self.html.append(f'<div class="lab" id="{lid}" data-kd="label" style="top:{y}px"><div class="lbox" id="{lid}-box" '
                         f'style="font-size:{fs}px"><span>{esc(text)}</span></div>{sub_html}</div>')
        self.st(f"#{lid}", {"autoAlpha": 0}, 0)
        self.st(f"#{lid}", {"autoAlpha": 1}, at)
        if b < self.T - 0.02:
            self.st(f"#{lid}", {"autoAlpha": 0}, b)
        self.ft(f"#{lid}-box", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.5, "ease": "power3.out"}, at)
        if sub:
            sa = sub_at if sub_at is not None else at + 0.45
            self.ft(f"#{lid}-sub", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.4, "ease": "power2.inOut"}, sa)
        if host and dim:
            self.ft(f"#{host} .dim", {"opacity": 0}, {"opacity": 0.42, "duration": 0.4, "ease": "power1.out"}, at)
        if caps is None:
            caps = self.fmt != "A"          # A: the label sits in the chest band, where the captions are
        if not caps:
            self.capoff.append((at, b))
        self.labels.append({"id": lid, "a": r3(at), "b": r3(b), "text": text, "sub": sub})
        self.sound("send-swoosh", at - 0.02, f"label {lid}", db=-8)
        self.beat(lid, "label", at, b, text)

    def counter(self, cid, a, b, to, at, dur=1.4, frm=0, steps=20, unit="", y=760, host=None, size=260, caps=None):
        """a number that counts frm -> to over dur s (steps shrink: ease out), Playfair italic in the accent, one tick per
        value; holds to b. On a picture (host) or a page."""
        self._id(cid)
        vals = []
        for k in range(1, steps + 1):
            u = k / steps
            v = frm + (to - frm) * (1 - (1 - u) ** 2.2)
            vals.append(int(round(v)))
        vals[-1] = to
        fmt = lambda v: f"{v:,}".replace(",", " ")
        spans = "".join(f'<span id="{cid}v{k}" class="cv">{fmt(v)}</span>' for k, v in enumerate(vals))
        un = f'<div class="cunit" style="top:{int(size * 1.02)}px">{esc(unit)}</div>' if unit else ""
        if self.fmt == "A" and not host:      # on the plate: the number and its unit stay clear of the face
            self.guard(f"counter {cid}", (60, y, 960, int(size * 1.02) + (80 if unit else 0)), at, b)
        self.html.append(f'<div class="ctr" id="{cid}" data-kd="counter" style="top:{y}px;font-size:{size}px">{spans}{un}</div>')
        self.st(f"#{cid}", {"autoAlpha": 0}, 0)
        self.st(f"#{cid}", {"autoAlpha": 1}, at)
        if b < self.T - 0.02:
            self.st(f"#{cid}", {"autoAlpha": 0}, b)
        times = [at + dur * (k / steps) ** 1.25 for k in range(steps)]      # the ticks slow down (1 frame -> ~3 frames)
        for k in range(steps):
            self.st(f"#{cid}v{k}", {"autoAlpha": 0}, 0)
            self.st(f"#{cid}v{k}", {"autoAlpha": 1}, r3(times[k]))
            if k + 1 < steps:
                self.st(f"#{cid}v{k}", {"autoAlpha": 0}, r3(times[k + 1]))
            self.sound("tick-1", times[k], f"{cid} tick {k}", db=-6, gap=0.03)
        if host:
            self.ft(f"#{host} .dim", {"opacity": 0}, {"opacity": 0.5, "duration": 0.3}, at)
        if caps is None:
            caps = self.fmt != "A"
        if not caps:
            self.capoff.append((at, b))
        self.beat(cid, "counter", at, b, f"{frm} -> {to}")

    def punch(self, at, hold=0.8, scale=1.1, target=None):
        """a snap punch-in (2 frames) on the stressed word: on the plate (A) or on a picture (target = its id)"""
        if target is None:
            if self.fmt != "A":
                raise BuildError("punch without a target needs the plate (format A)")
            if len(self.punches) >= 3:
                raise BuildError("at most three punch-ins on the face")
            self.punches.append((r3(at), hold, scale))
            sel = "#zoom"
        else:
            sel = f"#{target} .pz"
        self.marks.append(r3(at))
        self.tween(sel, {"scale": 1.0}, {"scale": scale, "duration": 0.07, "ease": "power3.out"}, at)
        self.tween(sel, {"scale": scale}, {"scale": 1.0, "duration": 0.2, "ease": "power2.inOut"}, at + hold)
        self.sound("whoosh-3", at - 0.03, "punch-in", db=-6)

    def swap(self, sid, host, src, at, line, kind="ai", snd="wood-hit"):
        """an in-place swap gag on a literal word: the host picture's image is replaced in ONE frame (+ a thud)"""
        self._id(sid)
        p = src if os.path.isabs(src) else os.path.join(self.P, src)
        if not os.path.exists(p):
            raise BuildError(f"{sid}: {src} not found")
        self.insert(sid, src, at, at + 1, line, "swap", kind)
        self.html.append(f'<img id="{sid}-im" class="swapimg" data-kd="swap" src="{self._bw(src)}">')
        self.js(f'(() => {{ const s = document.getElementById("{sid}-im"), h = document.getElementById("{host}-im");'
                f' if (s && h && h.parentElement) {{ s.className = h.className; h.parentElement.appendChild(s); }} }})();')
        self.st(f"#{sid}-im", {"autoAlpha": 0}, 0)
        self.st(f"#{sid}-im", {"autoAlpha": 1}, at)
        self.marks.append(r3(at))
        if snd:
            self.sound(snd, at, f"swap {sid}", db=-4)

    def strike(self, sid, at, y=None, host=None, dur=0.35):
        """a red line drawn through (left to right) on a literal word: over a picture (host) or the caption band"""
        self._id(sid)
        y = y if y is not None else 745
        parent = f'#{host}' if host else None
        html = f'<div class="strike" id="{sid}" data-kd="strike" style="top:{y}px"></div>'
        if parent:
            self.js(f'(() => {{ const s = document.getElementById("{sid}"), h = document.querySelector("{parent}"); if (s && h) h.appendChild(s); }})();')
        self.html.append(html)
        self.ft(f"#{sid}", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": dur, "ease": "power2.out"}, at)
        self.marks.append(r3(at))

    def erase(self, word, at):
        """the caption's big word loses its letters right to left, one a frame, from `at` (a literal 'disappears')"""
        self._effects[norm(word)] = ("erase", at)

    # ---------------------------------------------------------------- captions: one centred line, words pop on
    def _cap_top(self):
        if self.cap_top:
            return self.cap_top
        if self.fmt != "A":
            return 1240
        saved, self.punches = self.punches, []
        B = self.face_box(0, self.T, q=0.03)[3]
        self.punches = saved
        return int(min(1250, max(1130, B + 60)))

    def captions(self, BIG=(), RED=(), SERIF=()):
        """BIG / RED / SERIF: words ("more" = every time it is said) or one occurrence ("now#2" = the second time)"""
        ws = self.words
        seen = {}
        for w in ws:
            seen[w["n2"]] = seen.get(w["n2"], 0) + 1
            w["occ"] = seen[w["n2"]]
        def matcher(S):
            any_, one = set(), set()
            for x in S:
                m = re.match(r"^(.+?)#(\d+)$", x)
                (one.add((norm(m.group(1)), int(m.group(2)))) if m else any_.add(norm(x)))
            return lambda w: w["n2"] in any_ or w["n"] in any_ or (w["n2"], w["occ"]) in one
        isbig, isred, isser = matcher(BIG), matcher(RED), matcher(SERIF)
        hide = list(self.capoff) + list(self.nocap)
        hidden = lambda t: any(a - 0.05 <= t < b for a, b in hide)
        starts = sorted(a for a, b in hide)
        hasfx = lambda w: w["n2"] in self._effects or w["n"] in self._effects
        endp = lambda w: w["raw"][-1] in ".,?!:;»–"
        def brk(cur, nxw):
            """one phrase per line: <= 4 words / ~22 characters of small words, then the big word under them; a big word
            ends the line (two short big words in a row share it); the phrase's last word is never left alone"""
            last = cur[-1]
            if nxw is None or nxw["s"] - last["e"] > 0.6:
                return True
            if any(hasfx(x) for x in cur):
                return endp(last)                              # a big word with an effect keeps its phrase together
            if any(x["raw"].startswith("«") for x in cur) and not any(x["raw"].rstrip(".,?!").endswith("»") for x in cur):
                return False                                   # a quote stays on one line until it closes
            if nxw["raw"].startswith("«"):
                return True                                    # a quote starts its own line
            if endp(last):
                return True
            bigs = [x for x in cur if isbig(x)]
            if isbig(last):
                return not (isbig(nxw) and len(bigs) == 1)        # a pair of big words shares the block (stacked if long)
            n = sum(len(x["text"]) + 1 for x in cur if not isbig(x))
            if isbig(nxw):
                return n > 26 or bool(bigs)
            nl = len(nxw["text"])
            if endp(nxw) and n + nl <= 26 and len(cur) < 5:
                return False                                   # take the phrase's last word along
            if len(cur) >= 4 or n + nl > 22:
                return not (last["text"] in PRE and n + nl <= 30)
            return False
        chunks, cur = [], []
        for i, w in enumerate(ws):
            if hidden(w["s"]):
                if cur:
                    chunks.append(cur)
                    cur = []
                continue
            cur.append(w)
            nxw = ws[i + 1] if i + 1 < len(ws) and not hidden(ws[i + 1]["s"]) else None
            if brk(cur, nxw):
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        top = self._cap_top()
        out, self.caps = [], []
        for ci, ch in enumerate(chunks):
            a = max(0.0, ch[0]["s"] - 0.02)
            nxt = chunks[ci + 1][0]["s"] - 0.02 if ci + 1 < len(chunks) else ch[-1]["e"] + 0.8
            b = min(nxt, ch[-1]["e"] + 0.5, self.T)
            b = min([b] + [h - 0.01 for h in starts if h > a])
            big = [w for w in ch if isbig(w)]
            small = [w for w in ch if not isbig(w)]
            eff = None
            for w in big:
                if w["n2"] in self._effects or w["n"] in self._effects:
                    eff = (w, self._effects.get(w["n2"]) or self._effects.get(w["n"]))
            if eff:
                b = max(b, eff[1][1] + 0.45)
            stxt = " ".join(x["text"] for x in small)
            sfs = int(min(CAP_SMALL, CAP_W / max(1, EM_SMALL * len(stxt))))
            spans_s, spans_b = [], []
            for k, w in enumerate(ch):
                wid = f"c{ci}w{k}"
                cls = "w" + (" red" if isred(w) else "") + (" serif" if isser(w) else "")
                if isbig(w):
                    t = w["text"].upper()
                    if eff and eff[0] is w:
                        inner = "".join(f'<i id="{wid}l{j}" class="lt">{esc(c)}</i>' for j, c in enumerate(t))
                    else:
                        inner = esc(t)
                    spans_b.append(f'<span id="{wid}" class="{cls}">{inner}</span>')
                else:
                    spans_s.append(f'<span id="{wid}" class="{cls}">{esc(w["text"])}</span>')
                self.st(f"#{wid}", {"autoAlpha": 0}, 0)
                self.st(f"#{wid}", {"autoAlpha": 1}, r3(max(a, w["s"] - 0.02)))
                if eff and eff[0] is w:
                    t = w["text"].upper()
                    for j in range(len(t)):
                        self.st(f"#{wid}l{j}", {"autoAlpha": 0}, r3(eff[1][1] + (len(t) - 1 - j) / self.fps))
            small_html = f'<div class="csm" style="font-size:{sfs}px">{" ".join(spans_s)}</div>' if spans_s else ""
            bline = " ".join(x["text"] for x in big)                  # big words share one line, sized together; the
            bfs = int(min(CAP_BIG, CAP_W / max(1, EM_BIG * len(bline))))     # size sits on the line so the space scales too
            stack = len(big) > 1 and bfs < 100                            # a long pair stacks, one word a line
            if stack:
                bfs = int(min(124, CAP_W / max(1, EM_BIG * max(len(x["text"]) for x in big))))
                spans_b = [x.replace('class="w', 'class="w blk', 1) for x in spans_b]
            big_html = f'<div class="cbig" style="font-size:{bfs}px">{" ".join(spans_b)}</div>' if spans_b else ""
            ink = " ink" if any(la - 0.01 <= a < lb for la, lb in self.light) else ""
            out.append(f'<div id="c{ci}" class="cap{ink}" style="top:{top}px">{small_html}{big_html}</div>')
            hgt = (sfs + 20 if spans_s else 0) + ((bfs * (2 if stack else 1) + 14) if spans_b else 0)
            if self.fmt == "A":
                self.guard(f"caption «{' '.join(x['text'] for x in ch)}»", (70, top, 940, hgt), a, b)
            if top + hgt > SAFE["bottom"] + 40:
                raise BuildError(f"caption c{ci} runs to y {top + hgt} (Instagram's bottom UI starts at {SAFE['bottom']})")
            self.st(f"#c{ci}", {"autoAlpha": 0}, 0)
            self.st(f"#c{ci}", {"autoAlpha": 1}, r3(a))
            self.st(f"#c{ci}", {"autoAlpha": 0}, r3(max(b, a + 0.15)))
            self.caps.append((r3(a), r3(b), " ".join(x["text"] for x in ch)))
        return "".join(out)

    # ---------------------------------------------------------------- checks
    def check_budgets(self, extra_cover=()):
        if self.fmt == "A" and self.budget == "hybrid":
            m, errs = super().check_budgets(extra_cover)
            errs = [e for e in errs if "(< 65 %)" not in e and "inserts a minute" not in e]
            if m["face_on_screen_pct"] < 40:
                errs.append(f"hybrid: the face is on screen {m['face_on_screen_pct']} % (< 40 %)")
            return m, errs
        if self.fmt == "A":
            return super().check_budgets(extra_cover)
        m = self.metrics()
        errs = []
        iv = sorted((a, b) for a, b, *_ in self.scenes)
        t = 0.0
        for a, b in iv:
            if a > t + 0.04:
                errs.append(f"nothing on screen {t:.2f}-{a:.2f} s (format {self.fmt}: every moment is a scene)")
            t = max(t, b)
        if t < self.T - 0.04:
            errs.append(f"nothing on screen {t:.2f}-{self.T:.2f} s (the last scene ends early)")
        return m, errs

    def metrics(self):
        m = super().metrics()
        if self.fmt != "A":
            for k in ("face_on_screen_pct", "full_screen_s", "full_screen_pct", "full_screens", "longest_full_s"):
                m[k] = None
            m["scenes"] = len(self.scenes)
        return m

    def pace(self):
        """visual events (scene cuts, labels, counters, polaroids, punches; caption words not counted) and the longest
        stretch without one: the house wants something new every ~1.25 s outside the payoff"""
        ev = sorted({a for a, *_ in self.scenes} | {x["a"] for x in self.labels} | set(self.marks) | {b["t0"] for b in self.beats}
                    | {r3(at) for at in (v[1] for v in self._effects.values())})
        gaps, prev = [], 0.0
        for e in ev + [self.TV]:
            gaps.append((r3(e - prev), r3(prev), r3(e)))
            prev = e
        gaps.sort(reverse=True)
        return {"visual_events": len(ev), "per_min": round(len(ev) / (self.T / 60), 1), "longest_gaps": gaps[:3]}

    # ---------------------------------------------------------------- the page
    def build(self, BIG=(), RED=(), SERIF=(), css="", components=True):
        caps = self.captions(BIG, RED, SERIF)
        audio = self._audio()
        if self.fmt == "A":
            plate = self.held_plate()
            self.ft("#drift", {"scale": 1.0}, {"scale": HOOK_PUSH[0], "duration": HOOK_PUSH[1], "ease": "power2.out"}, 0)
            under = (f'<div id="zoom"><div id="drift"><video id="vw" src="{plate}" data-start="0" data-duration="{self.T}" '
                     f'data-track-index="0" muted playsinline></video></div></div>')
        else:
            under = '<div id="ground"></div>'
        body = f"""
 {under}
 {chr(10).join(self.html)}
 {caps}
 {chr(10).join(audio)}
"""
        grain = self.grain()
        zoom = f"\n#zoom {{ transform-origin: 540px {self.zoom_y}px; }}\n" if self.fmt == "A" else ""
        if self.fmt == "A":     # over clothes a red word reads at ~2:1: on the plate it is white on a red box
            zoom += (f".cap .w.red {{ color: #FFFFFF; background: {PAL['red']}; padding: 0 .14em .04em; text-shadow: none; "
                     f"box-shadow: 0 10px 30px rgba(0,0,0,.35); }}\n.cap .w.red.blk {{ display: table; margin: .1em auto 0; }}\n")
        self.write_page(BASE_CSS.replace("assets/grain.png", grain) + zoom + css, body,
                        ["Inter", "Oswald", "Playfair Display", "Playfair Display:italic", "JetBrains Mono"])
        pc = self.pace()
        self.notes.append(f"pace: {pc['visual_events']} visual events ({pc['per_min']}/min); longest stretches without one: "
                          + ", ".join(f"{g:.1f} s at {s:.1f}" for g, s, e in pc["longest_gaps"]))
        m = self.finish(f"kinetic-doc ({self.fmt}{', hybrid' if self.fmt == 'A' and self.budget == 'hybrid' else ''})", {"format": self.fmt, "scenes": self.scenes, "labels": self.labels,
                                                       "punch_ins": self.punches, "captions": self.caps, "pace": pc})
        if components:
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
                import components as C
                rep = C.check("kinetic-doc", self.P)
                print("components: " + " | ".join(C.report("kinetic-doc", rep)))
            except Exception as e:              # the catalog check is a warning, never a build failure
                print(f"components: not checked ({e})")
        return m


BASE_CSS = f"""
#root {{ background: {BLACK}; font-family: Inter; }}
#zoom, #drift {{ position: absolute; inset: 0; transform-origin: 50% 36%; }}
#zoom video {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; }}
#ground {{ position: absolute; inset: 0; background: {BLACK}; }}
.scene {{ position: absolute; inset: 0; overflow: hidden; background: {BLACK}; }}
.scene .fill {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
.blurbg {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
.ground {{ position: absolute; inset: 0; background-size: cover; }}
.pz {{ position: absolute; inset: 0; transform-origin: 50% 50%; }}
.pr {{ position: absolute; overflow: hidden; background: #111; box-shadow: 0 34px 90px rgba(0,0,0,.65); transform-origin: 50% 50%; }}
.pr.win {{ box-shadow: none; }}
.pr.fullpr {{ box-shadow: none; }}
.plabel {{ position: absolute; height: 96px; display: flex; align-items: center; justify-content: center;
  box-sizing: border-box; background: rgba(10,10,10,.58); font-family: "Playfair Display";
  font-style: italic; font-weight: 600; font-size: 52px; color: {WHITE}; text-shadow: 0 2px 10px rgba(0,0,0,.6); }}
.dim {{ position: absolute; inset: 0; background: #000; opacity: 0; pointer-events: none; }}
.page.black {{ background: {BLACK}; }}
.pagebox {{ position: absolute; left: 70px; right: 70px; top: 50%; transform: translateY(-58%); text-align: center; color: {INK}; }}
.pl {{ line-height: 1.12; margin: 6px 0; }}
.tk {{ position: relative; display: inline-block; margin: 0 .13em; }}
.tk .cur {{ position: absolute; left: 2%; right: 2%; top: 16%; bottom: 12%; background: {INK}; }}
.tk.s {{ font-family: Inter; font-weight: 600; font-size: 78px; letter-spacing: -1px; }}
.tk.big {{ font-family: Oswald; font-weight: 700; font-size: 210px; letter-spacing: 1px; text-transform: uppercase; line-height: 1.02; }}
.tk.red {{ font-family: Oswald; font-weight: 700; font-size: 210px; letter-spacing: 1px; text-transform: uppercase; color: {RED}; line-height: 1.02; }}
.tk.serif {{ font-family: "Playfair Display"; font-style: italic; font-weight: 600; font-size: 96px; }}
.page.black .tk {{ color: #E8E9EC; text-shadow: 0 0 14px rgba(255,255,255,.55), 0 0 40px rgba(255,255,255,.25); }}
.page.type .pagebox {{ font-family: "JetBrains Mono", monospace; color: #2A2A2E; }}
.page.type .tk {{ font-family: "JetBrains Mono", monospace; font-size: 76px; font-weight: 400; margin: 0 .08em; }}
.page.type .pagebox {{ left: 90px; right: 90px; }}
.page.type .ch {{ font-style: normal; }}
.caret {{ display: inline-block; width: 6px; height: 72px; margin-left: 4px; background: #2A2A2E; vertical-align: -10px; }}
.pols {{ background: {BLACK}; }}
.track {{ position: absolute; left: 0; top: 330px; height: 900px; width: 6000px; }}
.pol {{ position: absolute; top: 0; width: 600px; background: #F7F6F2; padding: 26px 26px 0; box-sizing: border-box;
  box-shadow: 0 30px 70px rgba(0,0,0,.45); }}
.pol .ph {{ position: relative; width: 548px; height: 548px; overflow: hidden; background: #222; }}
.polab {{ font-family: "Playfair Display"; font-style: italic; font-weight: 600; font-size: 52px; color: {INK}; text-align: center;
  padding: 18px 10px 30px; white-space: nowrap; }}
.cap {{ position: absolute; left: 70px; right: 70px; text-align: center; color: {WHITE}; pointer-events: none;
  text-shadow: 0 2px 6px rgba(0,0,0,.45), 0 6px 26px rgba(0,0,0,.5); }}
.csm {{ font-family: Inter; font-weight: 500; letter-spacing: -0.5px; word-spacing: 0.32em; line-height: 1.15; }}
.cbig {{ font-family: Oswald; font-weight: 700; line-height: 1.04; letter-spacing: 1px; margin-top: 2px; }}
.cap .w {{ display: inline-block; }}
.cap .w.blk {{ display: block; margin-top: .08em; }}
.cap.ink {{ color: {INK}; text-shadow: none; }}
.cap .lt {{ font-style: normal; display: inline-block; }}
.cap .red {{ color: {RED}; text-shadow: 0 2px 5px rgba(0,0,0,.6), 0 6px 22px rgba(0,0,0,.75), 0 0 2px rgba(0,0,0,.5); }}
.cap .serif {{ font-family: "Playfair Display"; font-style: italic; font-weight: 700; text-transform: none; letter-spacing: 0; font-size: 1.16em; }}
.lab {{ position: absolute; left: 0; right: 0; display: flex; flex-direction: column; align-items: center; pointer-events: none; }}
.lbox {{ background: {RED}; color: #FFFFFF; font-family: Oswald; font-weight: 700; letter-spacing: 1px; line-height: 1.0;
  padding: 18px 34px 22px; text-transform: uppercase; box-shadow: 0 18px 40px rgba(0,0,0,.35); }}
.lsub {{ margin-top: 10px; background: #F4F3EF; color: {INK}; font-family: Inter; font-weight: 600; font-size: 48px;
  padding: 10px 26px 14px; }}
.ctr {{ position: absolute; left: 0; right: 0; text-align: center; font-family: "Playfair Display"; font-style: normal;
  font-weight: 900; color: {RED}; line-height: 1; font-variant-numeric: lining-nums; font-feature-settings: "lnum" 1;
  text-shadow: 0 10px 40px rgba(0,0,0,.35); }}
.ctr .cv {{ position: absolute; left: 0; right: 0; }}
.cunit {{ position: absolute; left: 0; right: 0; top: 1.05em; font-family: Inter; font-style: normal; font-weight: 600;
  font-size: 64px; color: {WHITE}; text-shadow: 0 3px 18px rgba(0,0,0,.6); }}
.strike {{ position: absolute; left: 110px; right: 110px; height: 16px; margin-top: -8px; background: {RED}; }}
.swapimg {{ opacity: 0; }}
"""
