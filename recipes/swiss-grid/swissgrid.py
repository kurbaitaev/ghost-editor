#!/usr/bin/env python3
"""Swiss Grid: International Typographic Style in motion around a talking head. The 9:16 frame is a modular page
(6 columns, one typeface, one signal colour); the speaker's face, as shot, lives in one band of it between a paper header
(caption row + chapter counter) and a paper page where their words are set flush left on the grid, each word rising out of a clip
rect on its spoken onset; between face worlds the page grows up over the frame into short poster cards (giant numeral
chapter cards, a grid being built, a grid that means something). Every move is the precise ease cubic-bezier(.7,0,.2,1)
or linear; deletions are knife cuts; the one red thing (the reel's protagonist, e.g. a cup) is the only thing allowed off the grid.
Ported from LemoLab's MIT-licensed Swiss Motion Graphics style (CREDITS.txt); built on scripts/lib/facereel.py.

    import sys; sys.path.insert(0, "<skill>/recipes/swiss-grid"); from swissgrid import Grid
    G = Grid(P, plate="assets/wide.mp4", faces={"assets/wide.mp4": "build/face_wide.json",
             "assets/tight.mp4": "build/face_tight.json"}, fixes={"cafeine": "caffeine"},
             title="How much coffee is too much", chapters=3)
    w = G.face_world("w1", 0.0, 2.62)                                    # the face as shot + the page under the chin
    G.text(w, "w1l", "Your third coffee", G.X[0], w.y(0), "lead")    # words rise on their spoken onsets
    G.text(w, "w1s", "is doing less / than you think.", G.X[0], w.y(1), "face")
    c = G.card("c2", 2.62, 4.70, enter_from=w.top)                 # the page wipes up into a poster card
    G.slab(c, "cup", (534, 620, 438, 940), at=G.t("coffee"))        # the signal-colour block (the cup)
    G.numeral(c, "1", bottom=1560, at=9.0)                         # a giant numeral climbing in 4 eased steps
    G.knife(w, "#row1", y_mid, at)                                 # a line crosses, the row collapses to its midline
    G.counter([(8.30, "01"), ...]); G.build()

The calls (every time is edit seconds or a word ref, G.t("word"), "word#2", "^word" = its end):
  worlds   face_world(wid, t0, t1, plate=None, prev_top=None) -> World (.top, .y(i) = baseline of row i on the page)
           card(cid, t0, t1, enter_from, exit_up, what) -> World (full screen, <= house card_max_s, wipes in / out)
  type     text(world, tid, phrase, x, base, voice, ...) the spoken words (or a label with spoken=False); " / " breaks lines
           note_row(world, left, right, at) the 48 px caption row with its rule; counter([(t, "01"), ...]) in the header
  graphic  numeral(world, ch, bottom, at), rule(world, rid, x, y, w, at), slab(world, sid, box, at, color),
           bar(world, bid, box, at, moves=[(t, box)], label), modules(world, boxes, at, labels), guides(world, at),
           knife(world, sel, y_mid, x0, x1, at), minute_grid(world, ...), exception(world, eid, box, leave_at, ...),
           picture(world, pid, src, box, at, line) (greyscale, an insert), dot(world, did, cx, cy, r, at)
  sound    sfx(id, at, why, db, maxlen) (facereel.sound: levelled by role, no bed ever)
  output   build() -> index.html, build/beats.json, plan.json, sfx_events.json, build/holds.txt (caption hold report)

Needs in the project: the approved cut's plates as shot (assets/*.mp4, same timeline), assets/voice.wav,
build/words.cut.json (edit seconds), a face file per plate (scripts/face_track.py <plate> --out build/face_<name>.json).
No matte, no stock: the page and header never touch the speaker's head box, so no word needs to sit behind the head.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(SKILL, "scripts", "lib"))
import facereel as FR  # noqa: E402
from facereel import BuildError, esc, norm, r3  # noqa: E402,F401

HOUSE = json.load(open(os.path.join(HERE, "house.json")))
FRM, PAL, TYPE, BUD = HOUSE["frame"], HOUSE["palette"], HOUSE["type"], HOUSE["budgets"]
W, H, FPS = FRM["w"], FRM["h"], FRM["fps"]
X = FRM["col_x"]
RIGHT = FRM["right_edge"]
COLW, GUT = FRM["col_w"], FRM["gutter"]
E16, E8 = 4 / FPS, 8 / FPS
ASC = TYPE["ascent_em"]
MET = json.load(open(os.path.join(SKILL, "scripts", "lib", "metrics.json")))["Inter"]
VOICES = {"lead": TYPE["lead"], "face": TYPE["statement_face"], "card": TYPE["statement_card"], "note": TYPE["note"]}
SW_JS = ("const SW = (() => { const x1 = .7, y1 = 0, x2 = .2, y2 = 1; "
         "const bx = u => 3 * (1 - u) * (1 - u) * u * x1 + 3 * (1 - u) * u * u * x2 + u * u * u; "
         "const by = u => 3 * (1 - u) * (1 - u) * u * y1 + 3 * (1 - u) * u * u * y2 + u * u * u; "
         "return t => { if (t <= 0) return 0; if (t >= 1) return 1; let lo = 0, hi = 1, u = t; "
         "for (let i = 0; i < 30; i++) { const x = bx(u); if (Math.abs(x - t) < 1e-6) break; if (x < t) lo = u; else hi = u; u = (lo + hi) / 2; } "
         "return by(u); }; })();  // cubic-bezier(.7,0,.2,1): the only ease (lemo swiss-motion ease.js)")


def fr(t):
    """a time on a whole frame (visual onsets between frames flicker)"""
    return round(round(t * FPS) / FPS, 4)


def col(c, span=1):
    """x and width of `span` columns starting at column c (0-5)"""
    return X[c], span * COLW + (span - 1) * GUT


class World:
    def __init__(s, wid, t0, t1, kind, top, plate=None):
        s.id, s.t0, s.t1, s.kind, s.top, s.plate, s.kids = wid, t0, t1, kind, top, plate, []
        s.enter = t0
        s.tail = 0.0

    def y(s, row, first=64, step=96):
        """baseline of text row `row` on this world's page (rows of 96 px = 4 baselines, from the page top)"""
        return s.top + first + row * step


class Grid(FR.Reel):
    """One Swiss Grid reel on facereel.Reel (plates as shot, voice, word refs, SFX levelled by role, side files)."""

    def __init__(self, project, plate="assets/wide.mp4", faces=None, words=None, fixes=None, tail=0.35,
                 title="", chapters=5):
        self._plate_rel = plate
        self._face_files = faces or {plate: "build/face.json"}
        super().__init__(project, plate=plate, words=words, fixes=fixes, tail=tail, fps=FPS, music=None)
        self.title, self.chapters = title, chapters
        self.BODY, self.CSS, self.worlds, self.boxes, self.holds = [], [], [], [], []
        self._trk = 100
        self._faces = {}
        self._based = set()
        self.base.insert(0, SW_JS)
        self._header()

    # ---------------------------------------------------------------- faces
    def _load_face(self):
        f = os.path.join(self.P, self._face_files[self._plate_rel])
        if not os.path.exists(f):
            raise BuildError(f"no {f}: python3 {SKILL}/scripts/face_track.py {self._plate_rel} --out {f}")
        return [s for s in json.load(open(f))["samples"] if len(s) > 4 and s[1] is not None]

    def samples(self, plate):
        if plate not in self._faces:
            f = self._face_files.get(plate)
            if not f:
                raise BuildError(f"no face file for {plate}: faces={{'{plate}': 'build/face_<name>.json'}}")
            self._faces[plate] = [s for s in json.load(open(os.path.join(self.P, f)))["samples"] if s[1] is not None]
        return self._faces[plate]

    def head_span(self, plate, a, b):
        """(highest head top, lowest head bottom) of the grown head box over [a, b]"""
        ss = [s for s in self.samples(plate) if a - 0.3 <= s[0] <= b + 0.3] or self.samples(plate)
        return min(s[1] for s in ss), max(s[2] for s in ss)

    # ---------------------------------------------------------------- timeline
    def trk(self):
        self._trk += 1
        return self._trk

    def tw(self, sel, frm, to, at, dur, ease="SW"):
        """fromTo on the paused timeline; the first tween of a selector sets `frm` at load"""
        if sel not in self._based:
            self._based.add(sel)
            self.base.append(f"gsap.set({json.dumps(sel)}, {json.dumps(frm)});")
        props = {**to, "duration": round(dur, 4), "ease": "__E__", "immediateRender": False}
        s = json.dumps(props).replace('"__E__"', "SW" if ease == "SW" else json.dumps(ease))
        self.tl.append(f"tl.fromTo({json.dumps(sel)}, {json.dumps(frm)}, {s}, {max(0.0, at):.4f});")

    def bset(self, sel, props):
        self._based.add(sel)
        self.base.append(f"gsap.set({json.dumps(sel)}, {json.dumps(props)});")

    def tset(self, sel, props, at):
        self.tl.append(f"tl.set({json.dumps(sel)}, {json.dumps(props)}, {max(0.0, at):.4f});")

    def sfx(self, sid, at, why="", db=0.0, maxlen=None, fade=None):
        return self.sound(sid, at, why, db=db, maxlen=maxlen, fade=fade)

    # ---------------------------------------------------------------- type
    def width(self, text, wt, size):
        tab = MET[str(wt)]
        miss = sorted({c for c in text if c not in tab})
        if miss:
            raise BuildError(f"Inter {wt} has no glyph for {miss} in {text!r}")
        track = TYPE["tracking_em_at_90_up"] * size if size >= 90 else 0.0
        return sum(tab[c] for c in text) / 1000 * size + track * len(text)

    def said(self, phrase, after):
        """[(shown word, onset)] for a phrase the speaker says (tokens must be their words in order, from `after` on)"""
        toks = [x for x in phrase.replace(" / ", " ").split(" ") if x]
        nt = [norm(x) for x in toks]
        for i in range(len(self.words) - len(nt) + 1):
            if self.words[i]["s"] < after - 0.3:
                continue
            if all(nt[k] in (self.words[i + k]["n"], self.words[i + k]["n2"]) for k in range(len(nt))):
                return [(toks[k], self.words[i + k]["s"], self.words[i + k]["e"]) for k in range(len(nt))]
        raise BuildError(f"{phrase!r} is not said after {after:.2f} s (the speaker's words only)")

    def _box(self, what, x, top, w, h):
        self.boxes.append((what, x, top, w, h))
        s = FRM["safe"]
        if x + w > s["right"] + 0.5 or top < s["top"] - 0.5 or top + h > s["bottom"] + 0.5 or x < 0:
            raise BuildError(f"{what} [{x:.0f},{top:.0f} {w:.0f}x{h:.0f}] leaves the safe area {s}")

    def text(self, w, tid, phrase, x, base, voice="face", after=None, exit=None, maxw=None, spoken=True, at=None,
             color=None, size=None, wt=None, lh=None, right=False, stagger=E16 / 2, preset=False, exit_dur=E8):
        """Set a phrase flush left at column x, first baseline `base`; " / " breaks lines. Spoken words rise out of
        their clip on their onset (a sixteenth, precise ease; words said before the world lands rise as it lands);
        labels (spoken=False) rise from `at`, staggered. exit: the words leave upward in the eighth that ends there.
        The size shrinks to fit maxw (never under 48 px). preset: already set at load (frame 0 must read).
        Returns the last baseline."""
        v = VOICES[voice]
        size, wt = size or v["size"], wt or v["weight"]
        color = PAL[color or v["color"]] if (color or v["color"]) in PAL else color
        maxw = maxw or ((x - X[0]) if right else (RIGHT - x))
        lines = [ln.split(" ") for ln in phrase.split(" / ")]
        sp = TYPE.get("space_em", 0.28)

        def line_w(ln, sz):
            tr = TYPE["tracking_em_at_90_up"] * sz if sz >= 90 else 0.0
            return sum(self.width(x, wt, sz) for x in ln) + (len(ln) - 1) * (sp * sz + tr)
        for _ in range(4):
            widest = max(line_w(ln, size) for ln in lines)
            if widest <= maxw:
                break
            size = math.floor(size * maxw / widest)
        if size < TYPE["floor_px"]:
            raise BuildError(f"{tid}: {phrase!r} needs {size} px to fit {maxw:.0f} px (< {TYPE['floor_px']})")
        lh = lh or TYPE["line_height"]
        if spoken:
            sw = self.said(phrase, after if after is not None else w.t0 - 0.6)
            times = [max(s, w.enter) for _, s, _ in sw]
            sp0, sp1 = sw[0][1], sw[-1][2]
        else:
            n = sum(len(ln) for ln in lines)
            times = [(at if at is not None else w.enter) + i * stagger for i in range(n)]
        track = TYPE["tracking_em_at_90_up"] * size if size >= 90 else 0.0
        bh = size * 1.24
        k, y = 0, base
        first_on, last_box = None, None
        for li, ln in enumerate(lines):
            y = base + li * size * lh
            lw = line_w(ln, size)
            cx = (x - lw) if right else x
            for word in ln:
                ww = self.width(word, wt, size)
                eid = f"{tid}_{k}"
                pad = size * 0.06
                top = y - ASC * size - 0.0145 * size
                self._box(f"{tid} «{word}»", cx, top, ww, bh)
                w.kids.append(f'<div class="wc" id="{eid}" style="left:{cx - pad:.1f}px;top:{top:.1f}px;width:{ww + 2 * pad:.1f}px;'
                              f'height:{bh:.1f}px"><div class="wi" style="left:{pad:.1f}px;font-size:{size}px;font-weight:{wt};'
                              f'color:{color};letter-spacing:{track:.2f}px;line-height:{bh:.1f}px">{esc(word)}</div></div>')
                on = fr(times[k])
                first_on = on if first_on is None else first_on
                sel = f"#{eid} .wi"
                if preset or (on <= w.t0 + 0.0001 and w.enter <= w.t0 + 0.0001):
                    self.bset(sel, {"yPercent": 0})
                else:
                    self.tw(sel, {"yPercent": 108}, {"yPercent": 0}, on, E16)
                if exit is not None:
                    t_out = max(fr(exit - exit_dur), fr(on + E16))
                    self.tw(sel, {"yPercent": 0}, {"yPercent": -112}, t_out, min(exit_dur, max(E16 / 2, exit - t_out)))
                cx += ww + sp * size + track
                k += 1
        end = exit if exit is not None else w.t1
        if spoken:
            need = max(1.8, (sp1 - sp0) + 0.6)
            self.holds.append((tid, phrase.replace(" / ", " "), r3(first_on), r3(end), r3(end - first_on), r3(need)))
        return y

    def note_row(self, w, left="", right="", at=None, rule=True):
        """the caption row: a 1 px ink rule over 48 px Medium notes (left flush, right flush right at the grid edge)"""
        at = w.enter if at is None else at
        y = FRM["notes_rule_y"]
        if rule:
            self.rule(w, f"{w.id}_nr", X[0], y, RIGHT - X[0], at)
        if left:
            self.text(w, f"{w.id}_nl", left, X[0], FRM["notes_base"], "note", spoken=False, at=at + E16)
        if right:
            self.text(w, f"{w.id}_nrt", right, RIGHT, FRM["notes_base"], "note", spoken=False, at=at + E16, right=True)

    # ---------------------------------------------------------------- the header (whole reel)
    def _header(self):
        hh = FRM["header_h"]
        kids = [self._guides_html("hd", 0, hh)]
        kids.append(f'<div id="hd_rule" class="ln" style="left:{X[0]}px;top:{FRM["header_rule_y"]}px;width:{RIGHT - X[0]}px;height:2px;background:{PAL["ink"]}"></div>')
        kids.append(f'<div id="hd_sig" class="ln" style="left:0;top:{hh - 4}px;width:{W}px;height:4px;background:{PAL["signal"]}"></div>')
        self._hdr = World("hd", 0.0, None, "header", 0)
        self._hdr.kids = kids
        self.bset("#hd_sig", {"scaleX": 0, "transformOrigin": "0% 50%"})
        self.tw("#hd_sig", {"scaleX": 0}, {"scaleX": 1}, 0.0, E8, "none")      # the opening strike (linear)
        self.sound("pencil-write", 0.0, "the red line strikes under the header (ruling pen)", db=-4, maxlen=0.35, fade=0.1)

    def counter(self, steps, start="00"):
        """the chapter counter in the header, «00 / 05»: the number swaps by clip (old leaves up, new rises) at each step"""
        v = VOICES["note"]
        tail = f"/ {self.chapters:02d}"
        wn = self.width("00", v["weight"], v["size"])
        x0 = RIGHT - self.width(tail, v["weight"], v["size"]) - 0.28 * v["size"] - wn
        base = FRM["header_note_base"]
        hdr = self._hdr
        hdr.t1 = self.T
        hdr.enter = 0.0
        hdr.kind = "label"
        self.text(hdr, "hd_tail", tail, RIGHT, base, "note", spoken=False, at=0.0, right=True, stagger=0)
        vals = [(0.0, start)] + list(steps)
        for i, (t, val) in enumerate(vals):
            nxt = vals[i + 1][0] if i + 1 < len(vals) else None
            self.text(hdr, f"hd_n{i}", val, x0, base, "note", spoken=False, at=fr(t) if i else 0.0,
                      exit=fr(nxt) if nxt is not None else None, exit_dur=E16)   # old leaves up, then the new rises
        if self.title:
            self.text(hdr, "hd_title", self.title, X[0], base, "note", spoken=False, at=0.0, maxw=X[4] - X[0], stagger=0)

    # ---------------------------------------------------------------- worlds
    def _guides_html(self, gid, y0, y1, color=None, grow=False):
        c = color or PAL["guide"]
        xs = X + [RIGHT]
        return "".join(f'<div id="{gid}_g{i}" class="ln" style="left:{x}px;top:{y0}px;width:1px;height:{y1 - y0}px;background:{c}"></div>'
                       for i, x in enumerate(xs))

    def face_world(self, wid, t0, t1, plate=None, prev_top=None, gap=None):
        """the speaker's face as shot (the plate, full frame, untouched) + the page under the chin (its top 40 px under
        the head box, on the 24 px baseline) carrying the column guides. prev_top: the page top of the previous face
        world; a different top re-flows to the new one in an eighth."""
        plate = plate or self._plate_rel
        top_h, bot_h = self.head_span(plate, t0, t1)
        gap = FRM["page_gap_px"] if gap is None else gap
        top = int(math.ceil((bot_h + gap) / FRM["baseline"]) * FRM["baseline"])
        if top_h - 16 < FRM["header_h"]:
            raise BuildError(f"{wid}: the head top {top_h:.0f} px is under the header ({FRM['header_h']} px) on {plate}")
        w = World(wid, t0, t1, "face", top, plate)
        w.kids.append(f'<div class="pg" id="{wid}_pg" style="background:{PAL["page"]}"></div>')
        w.kids.append(self._guides_html(wid, top, H))
        self.worlds.append(w)
        if prev_top is not None and prev_top != top:
            self.bset(f"#{wid}_pg", {"clipPath": f"inset({prev_top}px 0px 0px 0px)"})
            self.tw(f"#{wid}_pg", {"clipPath": f"inset({prev_top}px 0px 0px 0px)"}, {"clipPath": f"inset({top}px 0px 0px 0px)"}, t0, E8)
        else:
            self.bset(f"#{wid}_pg", {"clipPath": f"inset({top}px 0px 0px 0px)"})
        return w

    def card(self, cid, t0, t1, enter_from, exit_up=True, what="poster card", bg=None):
        """a full-screen poster card: the page's top edge wipes up from `enter_from` (the page top of the face world
        before it) to the top of the frame (an eighth, precise ease, from t0); at the end the card rolls up into the
        header (its bottom edge wipes up in the last eighth), uncovering the next world from the bottom. The header
        stays on top. The roll-up runs in the eighth AFTER t1, over the next world (which starts at t1), so nothing
        black shows; the card counts as full screen from t0 to t1 + an eighth (<= house card_max_s)."""
        w = World(cid, t0, t1, "card", FRM["header_h"])
        w.enter = fr(t0 + E8)
        w.kids.append(f'<div class="pg" id="{cid}_pg" style="background:{bg or PAL["page"]}"></div>')
        self.worlds.append(w)
        sel = f"#{cid}"
        self.tw(sel, {"clipPath": f"inset({enter_from}px 0px 0px 0px)"}, {"clipPath": "inset(0px 0px 0px 0px)"}, fr(t0), E8)
        if exit_up:
            w.tail = E8
            self.tw(sel, {"clipPath": "inset(0px 0px 0px 0px)"}, {"clipPath": f"inset(0px 0px {H - FRM['header_h']}px 0px)"}, fr(t1), E8)
        self.full_screen(cid, t0, t1 + w.tail, what, cap=BUD["card_max_s"], din=E8, dout=w.tail)
        self.sound("paper-flip", t0, f"{cid}: the page wipes up into a card", db=-2)
        return w

    def guides(self, w, at, y0=None, y1=H, step=E16 / 2):
        """the column guides of a card, growing down from y0 one after another (linear: lines are drawn)"""
        y0 = FRM["header_h"] if y0 is None else y0
        w.kids.append(self._guides_html(f"{w.id}gd", y0, y1))
        for i in range(len(X) + 1):
            sel = f"#{w.id}gd_g{i}"
            self.bset(sel, {"scaleY": 0, "transformOrigin": "50% 0%"})
            self.tw(sel, {"scaleY": 0}, {"scaleY": 1}, fr(at + i * step), E8, "none")

    # ---------------------------------------------------------------- graphic elements
    def rule(self, w, rid, x, y, width, at, h=1, color=None, grow=True):
        """a ruled line that grows along its length (linear, an eighth)"""
        w.kids.append(f'<div id="{rid}" class="ln" style="left:{x}px;top:{y}px;width:{width}px;height:{h}px;background:{PAL[color or "ink"]}"></div>')
        if grow:
            self.bset(f"#{rid}", {"scaleX": 0, "transformOrigin": "0% 50%"})
            self.tw(f"#{rid}", {"scaleX": 0}, {"scaleX": 1}, fr(at), E8, "none")

    def numeral(self, w, ch, bottom, at, x=None, size=None, color="ink"):
        """a giant numeral (house numeral: ~700 px figure), optically flush left on column 1, bottom on `bottom`;
        it climbs into its clip in 4 eased steps (one module at a time) and lands on `at`"""
        size = size or TYPE["numeral"]["size"]
        x = X[0] if x is None else x
        lsb = TYPE["numeral_lsb_em"].get(ch, 0.04) * size
        cap = 0.7275 * size
        wid = self.width(ch, TYPE["numeral"]["weight"], size)
        top = bottom - cap - 6
        hh = cap + 0.03 * size
        nid = f"{w.id}_num"
        self._box(f"numeral {ch}", x, top, wid - lsb, hh)
        w.kids.append(f'<div class="wc" id="{nid}" style="left:{x - lsb:.1f}px;top:{top:.1f}px;width:{wid + 4:.0f}px;height:{hh:.0f}px">'
                      f'<div class="wi" style="left:0;top:{(bottom - 0.8633 * size) - top:.1f}px;font-size:{size}px;font-weight:{TYPE["numeral"]["weight"]};'
                      f'line-height:{size}px;color:{PAL[color]};letter-spacing:{TYPE["tracking_em_at_90_up"] * size:.1f}px">{ch}</div></div>')
        sel = f"#{nid} .wi"
        t0 = fr(at - 4 * E16)
        for k in range(4):
            self.tw(sel, {"y": hh * (1 - k / 4)}, {"y": hh * (1 - (k + 1) / 4)}, fr(t0 + k * E16), E16)
        self.sound("wood-hit", at, f"numeral {ch} lands (thunk)", db=-2)

    def slab(self, w, sid, box, at, color="signal", origin="50% 100%"):
        """a flat block that wipes in along its height (precise ease, lands on `at`)"""
        x, y, bw, bh = box
        w.kids.append(f'<div id="{sid}" class="blk" style="left:{x}px;top:{y}px;width:{bw}px;height:{bh}px;background:{PAL.get(color, color)}"></div>')
        self.bset(f"#{sid}", {"scaleY": 0, "transformOrigin": origin})
        self.tw(f"#{sid}", {"scaleY": 0}, {"scaleY": 1}, fr(at - E8), E8)

    def dot(self, w, did, cx, cy, r, at, color="signal"):
        w.kids.append(f'<div id="{did}" class="blk" style="left:{cx - r}px;top:{cy - r}px;width:{2 * r}px;height:{2 * r}px;'
                      f'border-radius:50%;background:{PAL.get(color, color)}"></div>')
        self.bset(f"#{did}", {"scale": 0})
        self.tw(f"#{did}", {"scale": 0}, {"scale": 1}, fr(at), E16)

    def bar(self, w, bid, box, at, moves=(), label=None, label_size=56, color="ink", text_color="paper", grow_from="0% 50%",
            start_w=None):
        """a black bar with mass (merged cells), wiping in along its length to land on `at`; moves: [(t, (x, y, w, h))]
        snap it to a new length (precise ease, lands on t; x, y and height stay: the element is as long as `box`, moves
        are scaleX so they stay sub-pixel smooth). start_w: the length it lands with (default the box's). label: white
        words inside, 56 px Bold"""
        x, y, bw, bh = box
        inner = ""
        if label:
            lw = self.width(label, 700, label_size)
            inner = (f'<div class="lbl" style="left:24px;top:{(bh - label_size * 1.2) / 2:.0f}px;font-size:{label_size}px;'
                     f'line-height:{label_size * 1.2:.0f}px;color:{PAL[text_color]}">{esc(label)}</div>')
            self._box(f"{bid} label", x + 24, y, lw, bh)
        w.kids.append(f'<div id="{bid}" class="blk" style="left:{x}px;top:{y}px;width:{bw}px;height:{bh}px;background:{PAL.get(color, color)}">{inner}</div>')
        self.bset(f"#{bid}", {"scaleX": 0, "transformOrigin": grow_from})
        cur = (start_w / bw) if start_w else 1.0
        self.tw(f"#{bid}", {"scaleX": 0}, {"scaleX": cur}, fr(at - E8), E8)
        for t, (nx, ny, nw, nh) in moves:
            if (nx, ny, nh) != (x, y, bh):
                raise BuildError(f"{bid}: a bar move changes only its length (x, y and height stay): {(nx, ny, nh)}")
            new = nw / bw
            self.tw(f"#{bid}", {"scaleX": cur}, {"scaleX": new}, fr(t - E8), E8)
            cur = new

    def modules(self, w, boxes, at, labels=(), step=E16, lw=2):
        """outlined grid modules, each drawn as four lines (top and left grow, then right and bottom; linear), one
        module per `step`; a 48 px label rises in each one's top-left corner"""
        for i, (x, y, bw, bh) in enumerate(boxes):
            t = fr(at + i * step)
            parts = [("t", x, y, bw, lw, "0% 50%", "scaleX", 0), ("l", x, y, lw, bh, "50% 0%", "scaleY", 0),
                     ("r", x + bw - lw, y, lw, bh, "50% 0%", "scaleY", 1), ("b", x, y + bh - lw, bw, lw, "0% 50%", "scaleX", 1)]
            for nm, lx, ly, lww, lhh, org, prop, ph in parts:
                mid = f"{w.id}_m{i}{nm}"
                w.kids.append(f'<div id="{mid}" class="ln" style="left:{lx}px;top:{ly}px;width:{lww}px;height:{lhh}px;background:{PAL["ink"]}"></div>')
                self.bset(f"#{mid}", {prop: 0, "transformOrigin": org})
                self.tw(f"#{mid}", {prop: 0}, {prop: 1}, fr(t + ph * E8), E8, "none")
            if i < len(labels) and labels[i]:
                self.text(w, f"{w.id}_ml{i}", labels[i], x + 24, y + 72, "note", spoken=False, at=t + E8)

    def knife(self, w, sel, y_mid, x0, x1, at, h=3):
        """a knife cut: a 3 px ink line crosses [x0, x1] at y_mid in the sixteenth before `at` (linear), then the
        element `sel` collapses to its midline in an eighth (and the line with it)"""
        nk = sum(1 for k in w.kids if 'class="knife"' in k)
        kid = f"{w.id}_k{nk}"
        w.kids.append(f'<div id="{kid}" class="knife" style="left:{x0}px;top:{y_mid - h / 2:.1f}px;width:{x1 - x0}px;height:{h}px;background:{PAL["ink"]}"></div>')
        self.bset(f"#{kid}", {"scaleX": 0, "scaleY": 1, "transformOrigin": "0% 50%"})
        self.tw(f"#{kid}", {"scaleX": 0}, {"scaleX": 1}, fr(at - E16), E16, "none")
        self.bset(sel, {"scaleY": 1, "transformOrigin": f"50% {y_mid}px"})
        self.tw(sel, {"scaleY": 1}, {"scaleY": 0}, fr(at), E8)
        self.tw(f"#{kid}", {"scaleY": 1}, {"scaleY": 0}, fr(at), E8)
        self.sound("shutter-1", at - E16, "knife cut (guillotine snick)", db=-6)

    def group(self, w, gid, inner_from):
        """wrap the kids added since index `inner_from` into one full-frame group div (a knife target)"""
        kids = w.kids[inner_from:]
        del w.kids[inner_from:]
        w.kids.append(f'<div id="{gid}" class="grp">' + "".join(kids) + "</div>")
        return f"#{gid}"

    def minute_grid(self, w, gid, box, cols, rows, draw_at, fill_at, cut_at, keep=(), bars=(), fill_step=1 / FPS,
                    cut_row=None):
        """the grid that means something: a white paper sheet of cols x rows cells. The guides draw (linear), every cell
        fills with the signal colour in a ripple from the top-left (`fill_at`), a knife crosses at `cut_row` and the
        red cells collapse, nearest rows first, two rows per sixteenth (`cut_at`), except `keep` [(r, c)]; then
        `bars` [(r, c, len, h, label, at)] snap in as merged black cells with white labels."""
        x, y, bw, bh = box
        cw, ch = bw / cols, bh / rows
        w.kids.append(f'<div id="{gid}_sh" class="blk" style="left:{x}px;top:{y}px;width:{bw}px;height:{bh}px;background:{PAL["paper"]}"></div>')
        self.bset(f"#{gid}_sh", {"scaleY": 0, "transformOrigin": "50% 0%"})
        self.tw(f"#{gid}_sh", {"scaleY": 0}, {"scaleY": 1}, fr(draw_at), E8)
        for c in range(cols + 1):
            lid = f"{gid}_v{c}"
            w.kids.append(f'<div id="{lid}" class="ln" style="left:{x + c * cw - (1 if c == cols else 0):.1f}px;top:{y}px;width:1px;height:{bh}px;background:{PAL["guide"]}"></div>')
            self.bset(f"#{lid}", {"scaleY": 0, "transformOrigin": "50% 0%"})
            self.tw(f"#{lid}", {"scaleY": 0}, {"scaleY": 1}, fr(draw_at + E8 + c * E16 / 4), E8, "none")
        for r in range(rows + 1):
            lid = f"{gid}_h{r}"
            w.kids.append(f'<div id="{lid}" class="ln" style="left:{x}px;top:{y + r * ch - (1 if r == rows else 0):.1f}px;width:{bw}px;height:1px;background:{PAL["guide"]}"></div>')
            self.bset(f"#{lid}", {"scaleX": 0, "transformOrigin": "0% 50%"})
            self.tw(f"#{lid}", {"scaleX": 0}, {"scaleX": 1}, fr(draw_at + E8 + r * E16 / 4), E8, "none")
        cut_row = rows / 2 - 0.5 if cut_row is None else cut_row
        for r in range(rows):
            for c in range(cols):
                cid = f"{gid}_c{r}_{c}"
                w.kids.append(f'<div id="{cid}" class="blk" style="left:{x + c * cw + 3:.1f}px;top:{y + r * ch + 3:.1f}px;'
                              f'width:{cw - 6:.1f}px;height:{ch - 6:.1f}px;background:{PAL["signal"]}"></div>')
                self.bset(f"#{cid}", {"scaleY": 0, "transformOrigin": "50% 50%"})
                self.tw(f"#{cid}", {"scaleY": 0}, {"scaleY": 1}, fr(fill_at + (r + c) * fill_step), E16)
                if (r, c) not in keep:
                    d = abs(r - cut_row)
                    self.tw(f"#{cid}", {"scaleY": 1}, {"scaleY": 0}, fr(cut_at + math.floor(d / 2) * E16 + E16), E8)
        kid = f"{gid}_knife"
        ky = y + (cut_row + 0.5) * ch
        w.kids.append(f'<div id="{kid}" class="knife" style="left:{x - 24}px;top:{ky - 1.5:.1f}px;width:{bw + 48}px;height:3px;background:{PAL["ink"]}"></div>')
        self.bset(f"#{kid}", {"scaleX": 0, "scaleY": 1, "transformOrigin": "0% 50%"})
        self.tw(f"#{kid}", {"scaleX": 0}, {"scaleX": 1}, fr(cut_at), E16, "none")
        self.tw(f"#{kid}", {"scaleY": 1}, {"scaleY": 0}, fr(cut_at + E16), E8)
        self.sound("tick-1", fill_at, "the minutes fill red", db=-4)
        self.sound("shutter-1", cut_at, "knife through the red minutes", db=-6)
        for i, (r, c, n, hh, label, at) in enumerate(bars):
            self.bar(w, f"{gid}_b{i}", (x + c * cw + 3, y + r * ch + 3, n * cw - 6, hh * ch - 6), at, label=label)
        return cw, ch

    def exception(self, w, eid, box, leave_at, to_x, readout=None, pause=E8, travel=0.9, enter_at=None):
        """the one element that breaks the grid (signal colour): it sits on the grid, then leaves LINEARLY and unsnapped,
        pausing for an eighth after 40 % of the way; readout = (x, base) of a 48 px note that turns from "on grid" to
        a red "off grid" when it leaves"""
        x, y, bw, bh = box
        w.kids.append(f'<div id="{eid}" class="blk" style="left:{x}px;top:{y}px;width:{bw}px;height:{bh}px;background:{PAL["signal"]}"></div>')
        self.bset(f"#{eid}", {"x": 0, "scaleY": 0 if enter_at else 1, "transformOrigin": "50% 100%"})
        if enter_at:
            self.tw(f"#{eid}", {"scaleY": 0}, {"scaleY": 1}, fr(enter_at - E8), E8)
        d = to_x - x
        a = fr(leave_at)
        t1 = a + travel * 0.4
        self.tw(f"#{eid}", {"x": 0}, {"x": d * 0.4}, a, travel * 0.4, "none")
        self.tw(f"#{eid}", {"x": d * 0.4}, {"x": d}, t1 + pause, travel * 0.6, "none")
        self.sound("whoosh-1", a, "the exception leaves the grid (linear, the only unsnapped move)", db=-8, maxlen=0.8, fade=0.3)
        if readout:
            rx, rb = readout
            self.text(w, f"{eid}_r0", "on grid", rx, rb, "note", spoken=False, at=w.enter, exit=a + E8, right=True)
            self.text(w, f"{eid}_r1", "off grid", rx, rb, "note", spoken=False, at=a + E8, color=PAL["signal"], right=True)
        return a + travel + pause

    def picture(self, w, pid, src, box, at, line, grey=True):
        """a real picture of a thing the speaker names, placed on the grid like an artifact (greyscale: one signal colour),
        wiped in from the bottom; counted as an insert"""
        x, y, bw, bh = box
        flt = "filter:grayscale(1) contrast(1.06);" if grey else ""
        w.kids.append(f'<div id="{pid}" class="blk" style="left:{x}px;top:{y}px;width:{bw}px;height:{bh}px;overflow:hidden">'
                      f'<img src="{src}" style="position:absolute;left:0;top:0;width:{bw}px;height:{bh}px;object-fit:cover;{flt}"></div>')
        self.bset(f"#{pid}", {"clipPath": f"inset({bh}px 0px 0px 0px)"})
        self.tw(f"#{pid}", {"clipPath": f"inset({bh}px 0px 0px 0px)"}, {"clipPath": "inset(0px 0px 0px 0px)"}, fr(at), E8)
        self.insert(pid, src, at, w.t1, line, "on the grid, greyscale", "picture")
        self.sound("click-1", at + E8, f"{pid} lands on the grid", db=-4)

    # ---------------------------------------------------------------- output
    def _emit(self, w, z):
        if w.kind == "face":
            self.BODY.append(f'<video id="{w.id}_v" class="clip vid" src="{w.plate}" muted playsinline data-start="{w.t0:.3f}" '
                             f'data-duration="{w.t1 - w.t0:.3f}" data-media-start="{w.t0:.3f}" data-track-index="{self.trk()}"></video>')
        style = f"z-index:{z};"
        self.BODY.append(f'<div id="{w.id}" class="clip full" data-start="{w.t0:.3f}" data-duration="{min(self.T, w.t1 + w.tail) - w.t0:.3f}" '
                         f'data-track-index="{self.trk()}" style="{style}">' + "".join(w.kids) + "</div>")

    def build(self, recipe="swiss-grid (lemo swiss-motion)", extra=None):
        """index.html + build/{beats,plan,sfx_events}.json + build/holds.txt; fails on a broken budget"""
        ws = sorted(self.worlds, key=lambda w: w.t0)
        for a, b in zip(ws, ws[1:]):
            if b.t0 > a.t1 + 0.001:
                raise BuildError(f"gap between {a.id} (ends {a.t1}) and {b.id} (starts {b.t0}): nothing would be on screen")
        if ws[0].t0 > 0.001 or ws[-1].t1 < self.T - 0.001:
            raise BuildError(f"the worlds run {ws[0].t0}-{ws[-1].t1}, the reel {self.T}")
        have = {b["id"] for b in self.beats}
        for w in ws:
            self._emit(w, 20 if w.kind == "card" else 5)
            if w.id not in have:
                self.beat(w.id, w.kind, w.t0, w.t1, f"{w.kind} {os.path.basename(w.plate or '')} page from y {w.top}")
        self._hdr.t1 = self.T
        self.BODY.append(f'<div id="hd" class="clip full" data-start="0" data-duration="{self.T:.3f}" data-track-index="{self.trk()}" '
                         f'style="z-index:50;clip-path:inset(0px 0px {H - FRM["header_h"]}px 0px)">'
                         f'<div class="pg" style="background:{PAL["page"]}"></div>' + "".join(self._hdr.kids) + "</div>")
        css = f"""
.full {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; overflow:hidden; }}
.vid {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; object-fit:cover; z-index:1; }}
.pg {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; }}
.grp {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; }}
.ln, .blk, .knife {{ position:absolute; }}
.wc {{ position:absolute; overflow:hidden; }}
.wi {{ position:absolute; top:0; white-space:nowrap; font-family:"Inter"; font-kerning:normal; }}
.lbl {{ position:absolute; white-space:nowrap; font-family:"Inter"; font-weight:700; }}
"""
        body = "\n".join(self.BODY) + "\n" + "\n".join(self._audio())
        self.write_page(css, body, ["Inter"])
        rep = ["caption holds (source rule: on screen >= max(1.8 s, speech + 0.6 s)); id | from | to | held | needed | ok"]
        short = 0
        for tid, ph, a, b, held, need in self.holds:
            ok = held + 0.001 >= need
            short += 0 if ok else 1
            rep.append(f"{tid:8} {a:6.2f} {b:6.2f} {held:5.2f} {need:5.2f} {'ok' if ok else 'SHORT'}  {ph}")
        open(os.path.join(self.P, "build", "holds.txt"), "w").write("\n".join(rep) + "\n")
        self.notes.append(f"caption holds: {len(self.holds) - short}/{len(self.holds)} meet the source's hold rule (build/holds.txt)")
        self.notes.append(f"{len(self.boxes)} text / graphic boxes inside the safe area; fonts: Inter only (glyphs checked)")
        return self.finish(recipe, {"worlds": [(w.id, w.kind, w.t0, w.t1, w.top) for w in ws], **(extra or {})})
