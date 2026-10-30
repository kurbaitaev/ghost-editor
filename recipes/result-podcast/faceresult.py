"""Face RESULT: the RESULT house over a talking head (props beside the face, never on it).

    import sys; sys.path.insert(0, "<skill>/recipes/result-podcast"); from faceresult import *
    R = FaceResult("$P", fixes={...}, cover=[...], music={"id": "lo-fi-02", "db": -22})
    a, b = R.t("beach"), R.t("^work+0.4")
    R.prop("note", a, b, "right", '<div class="sheet">...</div>', w=330, h=400, what="a note", enter="toss")
    R.write("#note .line1", R.t("tasks")) ; R.stamp("#note .st", R.t("deadlines")) ; R.punch(R.t("better"))
    R.scene("gauge", a2, b2, "kraft", '<svg>...</svg>', what="the gauge, big", enter="iris", caps=True)
    R.build(BIG={"work", ...}, SCRIPT={"breather"}, css="...")

The house (house.json; never changes reel to reel):
- the speaker's plate AS SHOT: no grade, no sepia, no CSS filter, no vignette on the face; a slow 4 % drift; at most 3 punch-ins;
- film grain + per-frame-seeded dust over everything (texture only, never a colour change);
- two-tier captions under the chin on a navy card: a small Inter Tight line (62 px) over one big bold word (132 px), key
  words in Caveat (150 px); one text layer at a time (a chest prop or a scene that shows the words drops the caption);
- paper objects from the line's world that sit BESIDE (left / right column), ABOVE (top band) or BELOW (chest band) the
  face, measured from build/face.json per prop window, and never on it (the build fails if a box touches the face, also
  under a punch-in or the drift); navy / kraft / cork surfaces; polaroids and paper as the only insert frame;
- full-screen cards <= 2.5 s, the face on screen >= 65 %, <= 3 stock / AI inserts a minute (each through insert_prep.py),
  every look-away in build/cover_windows.json hidden under a full-screen card.
What changes every reel (components.py plan --style result-podcast): the props, the polaroid / card treatments, the
entrances (`enter=`), the hook and the outro. Register each new one with `components.py add` and a sig before the build.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "lib"))
from facereel import Reel, BuildError, SAFE, esc, norm, r3, W, H  # noqa: E402,F401

NAVY, INK, RED, BLUE, GOLD, CREAM, KRAFT, PAPER = "#14213A", "#22252B", "#C8372D", "#1F3B8C", "#C9A24A", "#FFF3D6", "#B98E5E", "#FBF7EC"
DRIFT_ORIGIN = (0.5, 0.32)      # #drift transform-origin (fraction of the frame); #zoom pivots on the mouth line
DRIFT = 1.04                    # slow push over the whole reel
# prop entrances (data-in="<name>" is each one's catalog sig). side / drop / rise are the oldest ones (avoid while recent).
ENTER = {
    "side":  lambda zone: ({"autoAlpha": 0, "x": 260 if zone != "left" else -260, "rotation": 9}, {"duration": 0.42, "ease": "back.out(1.3)"}),
    "drop":  lambda zone: ({"autoAlpha": 0, "y": -420, "rotation": -14}, {"duration": 0.5, "ease": "back.out(1.4)"}),
    "rise":  lambda zone: ({"autoAlpha": 0, "y": 520, "rotation": 5}, {"duration": 0.42, "ease": "back.out(1.3)"}),
    "toss":  lambda zone: ({"autoAlpha": 0, "x": 340 if zone != "left" else -340, "y": -260, "rotation": 38, "scale": 0.7},
                           {"duration": 0.46, "ease": "power3.out"}),
    "slap":  lambda zone: ({"autoAlpha": 0, "scale": 1.28, "rotation": -4}, {"duration": 0.14, "ease": "power4.in"}),
    "unfold": lambda zone: ({"autoAlpha": 0, "rotationX": -88, "transformOrigin": "50% 0%"}, {"duration": 0.48, "ease": "power2.out"}),
    "swing": lambda zone: ({"autoAlpha": 0, "rotation": 34, "transformOrigin": "50% -6%"}, {"duration": 1.1, "ease": "elastic.out(1, 0.35)"}),
    "fade":  lambda zone: ({"autoAlpha": 0}, {"duration": 0.2, "ease": "power1.out"}),
    "none":  None,              # on screen from frame 1 (a hook object that is already there)
}
# full-screen card entrances: the card's in and out (data-in on the scene)
SCENE_IN = {
    "fade":  ({"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.14}),
    "iris":  ({"autoAlpha": 0, "clipPath": "circle(0% at 50% 45%)"}, {"autoAlpha": 1, "clipPath": "circle(75% at 50% 45%)", "duration": 0.3, "ease": "power2.in"}),
    "push":  ({"autoAlpha": 0, "y": 1920}, {"autoAlpha": 1, "y": 0, "duration": 0.26, "ease": "power3.out"}),
    "wipe":  ({"autoAlpha": 0, "clipPath": "inset(0% 100% 0% 0%)"}, {"autoAlpha": 1, "clipPath": "inset(0% 0% 0% 0%)", "duration": 0.24, "ease": "power2.inOut"}),
}
SCENE_OUT = {
    "fade": ({"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.14}),
    "iris": ({"clipPath": "circle(75% at 50% 45%)"}, {"clipPath": "circle(0% at 50% 45%)", "duration": 0.24, "ease": "power2.out"}),
    "push": ({"y": 0}, {"y": -1920, "duration": 0.24, "ease": "power3.in"}),
    "wipe": ({"clipPath": "inset(0% 0% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 100%)", "duration": 0.22, "ease": "power2.inOut"}),
}
PRE = {"в", "во", "с", "со", "из", "на", "о", "об", "у", "к", "ко", "по", "за", "не", "ни", "и", "а", "но", "от", "до", "для", "то",
       "a", "an", "the", "to", "of", "in", "on", "at", "and", "but", "not", "no", "for", "with"}


class FaceResult(Reel):
    def __init__(self, project, cap_top=None, **kw):
        super().__init__(project, **kw)
        self.props, self.punches, self.nocap = [], [], []
        self.cap_top = cap_top
        self._ids = set()
        ms = sorted(x[6] for x in self.face if len(x) > 6 and x[6] is not None)
        self.zoom_y = round(ms[len(ms) // 2]) if ms else int(H * 0.5)

    # ---------------------------------------------------------------- where the face is on screen at t
    def view(self, t):
        """(drift scale, punch scale) at t"""
        d = 1.0 + (DRIFT - 1.0) * min(1.0, max(0.0, t / self.TV))
        p = 1.0
        for at, hold, sc in self.punches:
            if at - 0.02 <= t <= at + hold + 0.25:
                p = sc
        return d, p

    def xf(self, t, box):
        """a plate box as it sits on screen at t: #drift (origin 50 % 32 %) inside #zoom (origin at the mouth line, so a
        punch-in grows the face up and out and barely moves the chin into the captions)"""
        d, p = self.view(t)
        ox, oy, zy = W * DRIFT_ORIGIN[0], H * DRIFT_ORIGIN[1], self.zoom_y
        f = lambda x, y: (W / 2 + (ox + (x - ox) * d - W / 2) * p, zy + (oy + (y - oy) * d - zy) * p)
        (l2, t2), (r2, b2) = f(box[0], box[1]), f(box[2], box[3])
        return [l2, t2, r2, b2]

    def _id(self, i):
        if i in self._ids or (i[:1] == "c" and i[1:].isdigit()):
            raise BuildError(f"id {i!r} is taken (caption ids are c0, c1, ...: never name an element c<n>)")
        self._ids.add(i)
        return i

    # ---------------------------------------------------------------- layers
    def prop(self, pid, a, b, zone, html, w, h, what, dx=0, dy=0, rot=0.0, enter="side", leave="fade", nocap=None, cls="", sfx="whoosh-2"):
        """a paper object beside / above / below the face from a to b (b=None: to the end). Its box (w x h) is placed in
        the zone's free rectangle (left/right: centred in the column, `dy` from its top; top: sitting on the band's
        bottom; chest: centred under the chin) and checked against the face over [a, b]."""
        self._id(pid)
        b = self.T if b is None else b
        z = self.zones(a, b)[zone]
        if zone in ("left", "right"):
            x = z[0] + (z[2] - w) / 2 + dx
            y = z[1] + dy
        elif zone == "top":
            x = (W - w) / 2 + dx
            y = z[1] + z[3] - h + dy
        else:
            x = (W - w) / 2 + dx
            y = z[1] + dy
        if zone in ("left", "right") and w > z[2] + 12:
            raise BuildError(f"{pid}: {w} px does not fit the {zone} column ({z[2]} px free between the face and the edge "
                             f"in {a:.2f}-{b:.2f} s): make it narrower, or use the top / chest band")
        if (zone == "top" and z[3] < h * 0.6) or (zone == "chest" and z[3] < h * 0.6):
            raise BuildError(f"{pid}: the {zone} band is {z[3]} px high in {a:.2f}-{b:.2f} s, the prop is {h} px")
        self.guard(f"prop {pid} ({what})", (x, y, w, h), a, b)
        self.props.append({"id": pid, "a": r3(a), "b": r3(b), "zone": zone, "box": [int(x), int(y), w, h], "what": what})
        if zone == "chest" and nocap is None:
            nocap = (a, b)
        if nocap:
            self.nocap.append(tuple(nocap))
        style = f"left:{x:.0f}px;top:{y:.0f}px;width:{w}px;height:{h}px"
        self.html.append(f'<div id="{pid}" class="prop {cls}" data-in="{enter}" style="{style}"><div class="pw" style="transform:rotate({rot}deg)">{html}</div></div>')
        sel = f"#{pid}"
        if ENTER.get(enter) is None:
            if enter != "none":
                raise BuildError(f"{pid}: enter {enter!r} unknown ({', '.join(ENTER)})")
            self.st(sel, {"autoAlpha": 1}, 0)
        else:
            frm, how = ENTER[enter](zone)
            to = {k: (1 if k in ("autoAlpha", "scale") else 0) for k in frm if k != "transformOrigin"}
            self.ft(sel, frm, {**to, **how}, a)
            if sfx:
                self.sound(sfx, a - 0.03, f"{pid} in", db=-2)
        if b < self.T - 0.05:
            if leave == "fly":
                self.tween(sel, {"autoAlpha": 1, "x": 0, "rotation": 0}, {"autoAlpha": 0, "x": 900 if zone != "left" else -900, "rotation": 18,
                                                                      "duration": 0.35, "ease": "power2.in"}, b - 0.35)
            elif leave == "drop":
                self.tween(sel, {"autoAlpha": 1, "y": 0}, {"autoAlpha": 0, "y": 700, "duration": 0.32, "ease": "power2.in"}, b - 0.32)
            else:
                self.tween(sel, {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.22}, b - 0.22)
        self.beat(pid, zone, a, b, what)
        return (x, y, w, h)

    def scene(self, sid, a, b, bg, html, what, caps=False, enter="fade", leave=None, sfx="whoosh-1", cls=""):
        """a full-screen card (navy / kraft / cork / paper) over the face: <= 2.5 s. caps=True keeps the captions on it."""
        self._id(sid)
        leave = leave or enter
        self.full_screen(sid, a, b, what, din=SCENE_IN[enter][1]["duration"], dout=SCENE_OUT[leave][1]["duration"])
        self.html.append(f'<div id="{sid}" class="scene {bg}{" " + cls if cls else ""}" data-in="{enter}"><div class="sp">{html}</div></div>')
        # a full-screen card never sits still (broll_qa: graphic scenes move): its content pushes in slowly
        self.ft(f"#{sid} > .sp", {"scale": 1.0}, {"scale": 1.05, "duration": round(b - a, 3), "ease": "none"}, a)
        frm, to = SCENE_IN[enter]
        self.ft(f"#{sid}", frm, to, a)
        f2, t2 = SCENE_OUT[leave]
        self.tween(f"#{sid}", f2, {**t2, "immediateRender": False}, b - t2["duration"])
        self.st(f"#{sid}", {"autoAlpha": 0}, b + 0.001)
        if not caps:
            self.capoff.append((a, b))
        if sfx:
            self.sound(sfx, a - 0.04, f"{sid} in")
        self.beat(sid, "full", a, b, what)

    def still(self, iid, src, a, b, line, frame="polaroid", kind="ai"):
        """a stock / AI / own still (prepared by insert_prep.py, conformed to the plate as shot) for a polaroid"""
        self.insert(iid, src, a, b, line, frame, kind)
        return f'<img id="{self._id(iid)}" class="phimg" src="{src}">'

    def video(self, iid, src, a, b, line, frame="polaroid", kind="stock", media_start=0.0):
        self.insert(iid, src, a, b, line, frame, kind)
        self._track += 1
        return (f'<video id="{self._id(iid)}" class="clip phvid" src="{src}" data-start="{a:.3f}" data-duration="{b - a:.3f}" '
                f'data-media-start="{media_start:.3f}" data-track-index="{self._track}" muted playsinline></video>')

    def polaroid(self, pid, media_html, label, w, ph, label_at=None, label_px=58):
        """a polaroid: the photo (w x ph) + a thick margin with a Caveat label written in at label_at"""
        if label_at is not None:
            self.write(f"#{pid} .plab", label_at, 0.5)
        return (f'<div id="{self._id(pid)}" class="pol" style="width:{w}px"><div class="ph" style="height:{ph}px">{media_html}</div>'
                f'<div class="plab" style="font-size:{label_px}px">{label}</div></div>')

    # ---------------------------------------------------------------- motion on the words
    def write(self, sel, at, dur=0.5, snd=None):
        """handwriting / print wipe-in, left to right (padded so the Caveat overhang is not cut). Silent by default: a
        sound goes on a prop's entrance and its key moment (a flip, a stamp, a punch), not on every written word"""
        self.ft(sel, {"clipPath": "inset(-30% 100% -30% -4%)"}, {"clipPath": "inset(-30% -4% -30% -4%)", "duration": dur, "ease": "power1.out"}, at)
        if snd:
            self.sound(snd, at, f"write {sel}", maxlen=min(0.9, dur + 0.3))

    def stamp(self, sel, at, rot=-10):
        self.ft(sel, {"autoAlpha": 0, "scale": 2.3, "rotation": rot - 8}, {"autoAlpha": 0.92, "scale": 1, "rotation": rot, "duration": 0.18, "ease": "power4.in"}, at)
        self.sound("impact-1", at + 0.15, f"stamp {sel}", db=-3)

    def pop(self, sel, at, rot=0, snd=None, scale=1.6):
        self.ft(sel, {"autoAlpha": 0, "scale": scale, "rotation": rot + 8}, {"autoAlpha": 1, "scale": 1, "rotation": rot, "duration": 0.2, "ease": "back.out(2)"}, at)
        if snd:
            self.sound(snd, at, f"pop {sel}")

    def draw(self, sel, at, dur=0.45, snd=None):
        """an SVG path / line with pathLength="1" and stroke-dasharray 1 1 draws on"""
        self.ft(sel, {"strokeDashoffset": 1}, {"strokeDashoffset": 0, "duration": dur, "ease": "power1.inOut"}, at)
        if snd:
            self.sound(snd, at, f"draw {sel}", maxlen=0.7)

    def show(self, sel, at, dur=0.12):
        self.ft(sel, {"autoAlpha": 0}, {"autoAlpha": 1, "duration": dur}, at)

    def hide(self, sel, at, dur=0.12):
        self.tween(sel, {"autoAlpha": 1}, {"autoAlpha": 0, "duration": dur}, at)

    def words_in(self, qid, text, t0, t1):
        """a phrase revealed word by word over [t0, t1] (proportional to characters, never slower than reading speed)"""
        ws = text.split(" ")
        tot = sum(len(x) + 1 for x in ws)
        acc, spans = 0, []
        for k, x in enumerate(ws):
            t = t0 + (t1 - t0) * acc / tot
            acc += len(x) + 1
            spans.append(f'<span id="{qid}w{k}" class="qw">{esc(x)}</span>')
            self.ft(f"#{qid}w{k}", {"autoAlpha": 0, "y": 8}, {"autoAlpha": 1, "y": 0, "duration": 0.12}, t)
        if len(text) / max(0.01, t1 - t0) < 12:
            self.notes.append(f"{qid}: {len(text) / max(0.01, t1 - t0):.1f} chars/s, slower than reading: shorten the window")
        return " ".join(spans)

    def punch(self, at, hold=0.85, scale=1.1):
        """a snap punch-in on the face (at most three a reel)"""
        if len(self.punches) >= 3:
            raise BuildError("RESULT: at most three punch-ins")
        self.punches.append((r3(at), hold, scale))
        self.ft("#zoom", {"scale": 1.0}, {"scale": scale, "duration": 0.12, "ease": "power3.out"}, at)
        self.tween("#zoom", {"scale": scale}, {"scale": 1.0, "duration": 0.22, "ease": "power2.inOut"}, at + hold)
        self.sound("whoosh-3", at - 0.03, "punch-in", db=-4)

    # ---------------------------------------------------------------- captions: two-tier on a navy card
    def captions(self, BIG, SCRIPT, first_on_frame1=False):
        BIGN, SCRN = {norm(x) for x in BIG}, {norm(x) for x in SCRIPT}
        hide = [(a, b) for a, b in self.capoff] + list(self.nocap)
        def hidden(t):
            return any(a - 0.05 <= t < b for a, b in hide)
        starts = sorted(a for a, b in hide)
        def cut_off(w):          # starts before a hidden window and would show for < 0.3 s
            nxt = [h for h in starts if h > w["s"] - 0.05]
            return bool(nxt) and nxt[0] - 0.02 - w["s"] < 0.3
        ws = self.words
        isbig = lambda w: w["n2"] in BIGN | SCRN or w["n"] in BIGN | SCRN
        def brk(cur, nxw):
            last = cur[-1]["text"]
            if isbig(cur[-1]) or cur[-1]["raw"][-1] in ".,?!:»–" or len(last) > 11 or len(cur) >= 3 or nxw is None:
                return True
            if len(cur) < 2:
                return False
            nx = nxw["text"]
            n = sum(len(x["text"]) for x in cur)
            if isbig(nxw) and n <= 14:
                return False
            if last in PRE and len(nx) <= 11:
                return False
            return not (n + len(nx) <= 11 and len(nx) <= 4 and nx not in PRE)
        chunks, cur = [], []
        for i, w in enumerate(ws):
            if hidden(w["s"]) or cut_off(w):
                if cur:
                    chunks.append(cur)
                    cur = []
                continue
            cur.append(w)
            nxw = ws[i + 1] if i + 1 < len(ws) and not hidden(ws[i + 1]["s"]) and not cut_off(ws[i + 1]) else None
            if brk(cur, nxw):
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        saved, self.punches = self.punches, []            # the caption line sits under the drifted chin; punch-ins are checked
        B = self.face_box(0, self.T, q=0.03)[3]
        self.punches = saved
        top = self.cap_top or int(min(1260, max(1120, B + 40)))
        fit = lambda s, base, k: int(min(base, 900 / max(1, k * len(s))))
        out, self.caps = [], []
        for ci, ch in enumerate(chunks):
            a = max(0.0, ch[0]["s"] - 0.04)
            nxt = chunks[ci + 1][0]["s"] - 0.04 if ci + 1 < len(chunks) else ch[-1]["e"] + 0.6
            b = min(nxt, ch[-1]["e"] + 0.45, self.T)
            b = min([b] + [h - 0.02 for h in starts if h > a])
            b = max(b, a + 0.18)
            lw = ch[-1]
            small = " ".join(x["text"] for x in ch[:-1])
            sm = f'<div class="csm" style="font-size:{fit(small, 62, 0.55)}px">{esc(small)}</div>' if small else ""
            if lw["n2"] in BIGN or lw["n"] in BIGN:
                inner = sm + f'<div class="cbig" style="font-size:{fit(lw["text"], 132, 0.62)}px">{esc(lw["text"])}</div>'
                hgt = 70 + 132
            elif lw["n2"] in SCRN or lw["n"] in SCRN:
                inner = sm + f'<div class="cscript" style="font-size:{fit(lw["text"], 150, 0.44)}px">{esc(lw["text"])}</div>'
                hgt = 70 + 140
            else:
                line = " ".join(x["text"] for x in ch)
                inner = f'<div class="cpl" style="font-size:{fit(line, 80, 0.56)}px">{esc(line)}</div>'
                hgt = 100
            out.append(f'<div id="c{ci}" class="cap" style="top:{top}px"><div class="cd">{inner}</div></div>')
            self.guard(f"caption «{small + ' ' + lw['text']}»", (70, top, 940, hgt + 30), a, b)
            if first_on_frame1 and a <= 0.05:
                self.st(f"#c{ci}", {"autoAlpha": 1}, 0)
            else:
                self.ft(f"#c{ci}", {"autoAlpha": 0, "y": 12, "scale": 0.96}, {"autoAlpha": 1, "y": 0, "scale": 1, "duration": 0.12, "ease": "power2.out"}, a)
            self.tween(f"#c{ci}", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.01}, max(b, a + 0.15))
            self.caps.append((r3(a), r3(b), " ".join(x["text"] for x in ch)))
        return "".join(out)

    # ---------------------------------------------------------------- the page
    def build(self, BIG=(), SCRIPT=(), css="", first_on_frame1=False, components=True):
        caps = self.captions(BIG, SCRIPT, first_on_frame1)
        self.ft("#drift", {"scale": 1.0}, {"scale": DRIFT, "duration": self.TV, "ease": "none"}, 0)
        self.dust_painter()
        plate = self.held_plate()
        grain = self.grain()
        audio = self._audio()
        body = f"""
 <div id="zoom"><div id="drift"><video id="vw" src="{plate}" data-start="0" data-duration="{self.T}" data-track-index="0" muted playsinline></video></div></div>
 {chr(10).join(self.html)}
 {caps}
 <canvas id="dust" width="{W}" height="{H}"></canvas><div id="grain"></div>
 {chr(10).join(audio)}
"""
        css = BASE_CSS.replace("assets/grain.png", grain) + f"\n#zoom {{ transform-origin: 540px {self.zoom_y}px; }}\n" + css
        self.write_page(css, body, ["Inter Tight", "Caveat", "Oswald", "JetBrains Mono", "Playfair Display", "Playfair Display:italic"])
        m = self.finish("result-podcast (Face RESULT)", {"props": self.props, "punch_ins": self.punches, "captions": self.caps})
        if components:
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
                import components as C
                rep = C.check("result-podcast", self.P)
                print("components: " + " | ".join(C.report("result-podcast", rep)))
            except Exception as e:              # the catalog check is a warning, never a build failure
                print(f"components: not checked ({e})")
        return m


BASE_CSS = f"""
#root {{ background: #000; font-family: "Inter Tight"; }}
#zoom, #drift {{ position: absolute; inset: 0; transform-origin: {DRIFT_ORIGIN[0] * 100:.0f}% {DRIFT_ORIGIN[1] * 100:.0f}%; }}
#zoom video {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; }}
.scene {{ position: absolute; inset: 0; opacity: 0; visibility: hidden; overflow: hidden; perspective: 1400px; }}
.navy {{ background: radial-gradient(circle at 50% 40%, #1E3052, {NAVY} 72%); }}
.kraft {{ background: {KRAFT} radial-gradient(circle at 30% 20%, rgba(255,255,255,.14), transparent 60%); }}
.cork {{ background: #B4885A radial-gradient(rgba(0,0,0,.12) 1.2px, transparent 1.6px) 0 0 / 14px 14px; }}
.paperbg {{ background: #F4EEDF radial-gradient(circle at 25% 15%, rgba(255,255,255,.5), transparent 55%); }}
.scene > .sp {{ position: absolute; inset: 0; transform-origin: 50% 45%; }}
.scene::after {{ content: ""; position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,.4) 100%); pointer-events: none; }}
.prop {{ position: absolute; opacity: 0; visibility: hidden; perspective: 1200px; }}
.prop > .pw {{ position: absolute; inset: 0; }}
.hand {{ font-family: Caveat; font-weight: 700; color: {BLUE}; }}
.red {{ color: {RED}; }}
.mono {{ font-family: "JetBrains Mono", monospace; letter-spacing: 2px; }}
.sheet {{ position: absolute; inset: 0; background: {PAPER}; box-shadow: 0 22px 50px rgba(0,0,0,.5); border-radius: 6px; color: {INK}; box-sizing: border-box; }}
.lined {{ background: {PAPER} repeating-linear-gradient({PAPER} 0 78px, #B9CDE8 78px 80px); }}
.tape {{ position: absolute; top: -22px; left: 50%; width: 150px; height: 44px; margin-left: -75px; background: rgba(238,222,186,.88); transform: rotate(-4deg); box-shadow: 0 2px 4px rgba(0,0,0,.18); }}
.stamp {{ position: absolute; padding: 10px 24px; border: 8px solid {RED}; border-radius: 14px; color: {RED}; font-family: Oswald; font-weight: 700; letter-spacing: 3px;
  line-height: 1; opacity: 0; mix-blend-mode: multiply; text-align: center; white-space: nowrap; }}
.pol {{ position: relative; background: #FBF8F0; padding: 18px 18px 0; box-sizing: border-box; box-shadow: 0 26px 60px rgba(0,0,0,.55); }}
.pol .ph {{ position: relative; overflow: hidden; background: #222; }}
.pol .phimg, .pol .phvid {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
.plab {{ font-family: Caveat; font-weight: 700; color: {INK}; text-align: center; padding: 10px 10px 16px; line-height: 1.0; white-space: nowrap; }}
.qw {{ display: inline-block; opacity: 0; }}
svg.ink {{ position: absolute; overflow: visible; }}
svg.ink path, svg.ink line, svg.ink ellipse, svg.ink circle {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 1 1; stroke-dashoffset: 1; }}
.cap {{ position: absolute; left: 40px; right: 40px; display: flex; justify-content: center; opacity: 0; visibility: hidden; }}
.cap .cd {{ background: rgba(18,29,50,.86); border-radius: 26px; padding: 12px 36px 18px; text-align: center; color: #FFFDF8;
  box-shadow: 0 16px 36px rgba(0,0,0,.32); max-width: 960px; }}
.csm {{ font-weight: 700; letter-spacing: -1.5px; line-height: 1.08; opacity: .96; }}
.cbig {{ font-weight: 900; letter-spacing: -4px; line-height: .98; }}
.cpl {{ font-weight: 800; letter-spacing: -2px; line-height: 1.04; }}
.cscript {{ font-family: Caveat; font-weight: 700; line-height: .9; color: #FFE2A0; padding: 0 6px; }}
#dust {{ position: absolute; inset: 0; pointer-events: none; mix-blend-mode: screen; }}
#grain {{ position: absolute; inset: 0; background: url(assets/grain.png); background-size: 480px; opacity: .07; mix-blend-mode: overlay; pointer-events: none; }}
"""
