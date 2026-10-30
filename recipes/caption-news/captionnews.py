"""Caption News: social-video news that reads with the sound off, on a talking head. The speaker's face as shot is the ground;
huge captions are the lead actor, slammed in 2-3 chunks on the onsets of their first words, one keyword per
caption on a honey block that wipes left to right; the hook lands on frame 4; a title sting (a honey ruled page over the
bottom band) becomes the channel bug; when the speaker names a source, a document beat: the source on a dark desk, highlighter
sweeps on the words the speaker says, the title re-set in a honey block and a source tag under the bug; lists become a lit grid
or a ruled list on the ledger sheet. Ported from lemo-opuscar styles/caption-news (MIT, (c) 2026 LemoLab,
https://github.com/lemomo-ai/lemo-opuscar), demo/main.js capCard(), hook(), shotSting(), bug(), sourceTag(), paper(),
shotGrid(), ledger(), num(); see CREDITS.txt.

    import sys; sys.path.insert(0, "<skill>/recipes/caption-news"); from captionnews import News
    # an example reel (a tip about a cluttered desk); every time is the onset of a word in build/words.cut.json
    N = News("$P", dur=31.97, title="Desk Reset Caption News")       # plates: assets/tight.mp4 + wide.mp4 (as shot)
    N.plates([(0, "t"), (12.5, "w")])                                 # the speaker's own framing switches, hard
    N.cap(0.13, 2.6, [[("Your desk is stealing", 0.13)], [("your {focus}.", 0.40, 1.6)]], hook=True)   # frame-4 hook
    N.sting(2.56, 4.40, [("YOUR", 3.08), ("DESK", 3.36), ("AND FOCUS", 3.76)], chip=("ONE SIMPLE RULE", 3.95),
            bug=("DESK", "AND FOCUS"))                                # page over the bottom band -> the channel bug
    N.doc(4.40, 8.30, "assets/source.jpg", marks=[(4.90, 85, 88, 585, 142, .4)], block=("CLEAR DESK", 6.10),
          source=("SOURCE", "the guide the speaker names", 4.55))     # the real document, shown at <= 1:1
    N.cap(8.36, 10.2, [[("Put away everything", 8.40)], [("you {won't}", 9.04)], [("use today.", 9.48)]])
    N.grid(10.20, 12.50, [("Mail", "mail", 10.34), ("Chat", "chat", 11.00), ("Feeds", "feed", 11.58)])
    N.ruled_list(19.55, 22.50, "The basics", [("Sleep", 19.74), ...])
    N.sfx("impact-2", 0.13, 0.5); N.build()

Captions: N.cap(t0, t1, lines, size=None, hook=False). lines = [[chunk, ...], ...] (one list per line, stacked upward
from y 1680); chunk = (text, t[, size multiplier]); text may hold one {keyword}. A chunk slams at t (use the onset of its
first word: on a talking head no word shows before it is said; only the frame-4 hook runs ahead). A line shrinks to fit
916 px, never under 60 px. Captions use the words exactly as spoken, in the speaker's language (Inter Tight has
Latin and Cyrillic). Cards: doc(), grid(), ruled_list() are full-screen cutaways (class clip sections) that slide
in from the right with honey streaks; build() writes index.html, build/beats.json, build/coverage.txt and checks that
every spoken word is on screen in order (said= on cards lists the words a card carries).

Needs in $P: assets/tight.mp4 (+ wide.mp4) as shot, assets/voice.wav, build/words.cut.json (edit seconds); the
document image for doc(). No matte needed: the captions sit under the speaker's chin, never on the speaker's face. Fonts and SFX are copied
from the skill (templates/fonts, library/sfx). Measuring needs a Python with fontTools + brotli once (it falls back to
~/.venvs/ghost-captions/bin/python to write build/ttf/*.ttf), then PIL.
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
HOUSE = json.load(open(os.path.join(HERE, "house.json"), encoding="utf-8"))
PAL = HOUSE["palette"]
LP = HOUSE["layout_px"]
TY = HOUSE["type"]
FPS = HOUSE["motion"]["fps"]
F1 = 1 / FPS
TRACK = TY["tracking_em"]
KIT = HOUSE["sound"]["kit"]
FONT = "'Inter Tight'"


def fr(t):
    return round(round(t * FPS) / FPS, 4)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def is_cyr(ch):
    return 0x0400 <= ord(ch) <= 0x04FF


def norm(s):
    return re.sub(r"[^\w]", "", s.lower().replace("ё", "е"))


# ---------------------------------------------------------------- fonts + measuring
_TTF = [None]
_fc = {}


def ensure_fonts(P):
    os.makedirs(f"{P}/assets/fonts", exist_ok=True)
    for _, stem, _, _ in TY["font_faces"]:
        for sub in ("cyrillic", "latin"):
            dst = f"{P}/assets/fonts/{stem}-{sub}.woff2"
            if not os.path.exists(dst):
                shutil.copy(f"{SKILL}/templates/fonts/{stem}-{sub}.woff2", dst)
    lic = f"{P}/assets/fonts/LICENSE-InterTight.txt"
    if not os.path.exists(lic):
        shutil.copy(f"{SKILL}/templates/fonts/LICENSE-InterTight.txt", lic)


_CONV = r'''
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
src, dst, w = sys.argv[1], sys.argv[2], int(sys.argv[3])
g = TTFont(src)
if "fvar" in g:
    g = instancer.instantiateVariableFont(g, {"wght": w})
g.flavor = None
g.save(dst)
'''


def ensure_ttf(P, weights=(900, 600)):
    """static TTF instances of the variable woff2 for PIL measuring -> build/ttf/inter-tight-<sub>-<w>.ttf"""
    out = f"{P}/build/ttf"
    os.makedirs(out, exist_ok=True)
    for w in weights:
        for sub in ("cyrillic", "latin"):
            dst = f"{out}/inter-tight-{sub}-{w}.ttf"
            if os.path.exists(dst):
                continue
            src = f"{P}/assets/fonts/inter-tight-{sub}.woff2"
            try:
                import brotli  # noqa: F401
                import fontTools  # noqa: F401
                py = sys.executable
            except ImportError:                      # the media venv has no brotli: any venv with fontTools + brotli
                py = os.path.expanduser("~/.venvs/ghost-captions/bin/python")
            subprocess.run([py, "-c", _CONV, src, dst, str(w)], check=True)
    _TTF[0] = out
    return out


def _font(sub, size, w=900):
    from PIL import ImageFont
    k = (sub, size, w)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(f"{_TTF[0]}/inter-tight-{sub}-{w}.ttf", size)
    return _fc[k]


def adv(s, size, w=900):
    """advance width with tracking, per char from the subset that has it (kerning ignored -> errs wide)"""
    if not s:
        return 0.0
    a = sum(_font("cyrillic" if is_cyr(c) else "latin", 200, w).getlength(c) * size / 200 for c in s)
    return a + TRACK * size * max(len(s) - 1, 0)


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


KW = re.compile(r"\{([^}]*)\}")


# ---------------------------------------------------------------- icons for the lit grid (line art, stroke only)
ICONS = {
    "mail": '<rect x="14" y="34" width="172" height="124" rx="14"/><polyline points="18,42 100,108 182,42"/>',
    "chat": '<path d="M28 30 h144 a18 18 0 0 1 18 18 v76 a18 18 0 0 1 -18 18 h-84 l-40 32 v-32 h-20 a18 18 0 0 1 -18 -18 v-76 a18 18 0 0 1 18 -18 z"/>'
            '<circle cx="62" cy="86" r="6"/><circle cx="100" cy="86" r="6"/><circle cx="138" cy="86" r="6"/>',
    "feed": '<rect x="34" y="18" width="132" height="164" rx="16"/><rect x="54" y="42" width="92" height="58" rx="6"/>'
            '<line x1="54" y1="122" x2="146" y2="122"/><line x1="54" y1="146" x2="118" y2="146"/>',
}


class News:
    """One Caption News reel. Calls: plates(), cap(), sting(), doc(), grid(), ruled_list(), sfx(), build();
    helpers: set(), tween(), beat()."""

    def __init__(self, project, dur, title, words="build/words.cut.json", plates=None, voice="assets/voice.wav", lang="ru",
                 aliases=None):
        self.P = os.path.abspath(os.path.expanduser(project))
        self.dur, self.page_title, self.lang = dur, title, lang
        d = json.load(open(f"{self.P}/{words}", encoding="utf-8"))
        raw = [w for s in d["segments"] for w in s["words"]] if "segments" in d else d["words"]
        self.W = [(w["word"].strip(), w["start"], w["end"]) for w in raw]
        self.aliases = {norm(k): norm(v) for k, v in (aliases or {}).items()}   # whisper spelling -> on-screen spelling
        self.plates_ = plates or {"t": "assets/tight.mp4", "w": "assets/wide.mp4"}
        self.voice = voice
        self.voice_dur = round(probe_dur(f"{self.P}/{voice}"), 2)
        ensure_fonts(self.P)
        ensure_ttf(self.P)
        self.H, self.JS, self.BEATS, self.SECTIONS, self.SFX, self.SAID = [], [], [], [], [], []
        self.FACE = []
        self._id, self._track = 0, 10
        self.switches = []

    # ------------------------------------------------------------ timeline primitives
    def nid(self, p="e"):
        self._id += 1
        return f"{p}{self._id}"

    def track(self):
        self._track += 1
        return self._track

    def set(self, sel, props, t):
        self.JS.append(f'tl.set("{sel}", {json.dumps(props, ensure_ascii=False)}, {fr(t):.4f});')

    def tween(self, sel, frm, to, t):
        self.JS.append(f'tl.fromTo("{sel}", {json.dumps(frm, ensure_ascii=False)}, '
                       f'{json.dumps({**to, "immediateRender": False}, ensure_ascii=False)}, {fr(t):.4f});')

    def beat(self, bid, keys):
        keys = sorted(round(k, 3) for k in keys)
        self.BEATS.append({"id": bid, "type": "beat", "label": bid, "t0": keys[0], "t1": keys[-1], "keys": keys})

    def slam(self, sel, t, s0=1.3):
        """capCard(): scale 1.3 -> 1 in 0.13 s (back, overshoot 1.6), opacity full in 0.04 s"""
        self.tween(sel, {"scale": s0}, {"scale": 1, "duration": 0.13, "ease": "back.out(1.6)"}, t)
        self.tween(sel, {"opacity": 0}, {"opacity": 1, "duration": 0.04, "ease": "none"}, t)

    def wipe(self, kb, kt, t):
        """the honey keyword block wipes left -> right in 0.12 s, the word turns ink"""
        self.tween(kb, {"scaleX": 0}, {"scaleX": 1, "duration": 0.12, "ease": "power2.out"}, t)
        self.set(kt, {"color": PAL["ink"]}, t + 0.03)

    # ------------------------------------------------------------ captions (the caption IS the graphic)
    def _chunk_w(self, text, size, first, last):
        c = LP["cap"]
        plain = KW.sub(r"\1", text)
        w = adv(plain, size)
        if KW.search(text):
            w += 2 * c["kw_pad"] * size / 84
        return w + (c["pad_x"] if first else 0) + (c["pad_x"] if last else 0)

    def cap(self, t0, t1, lines, size=None, hook=False, z=30):
        """a caption card in the lower band: lines stacked upward from y 1680, each a dark slab; every chunk slams at its
        time, its {keyword} wipes in honey 0.05 s later. hook=True: the frame-4 hook (chunks may run ahead of the voice)."""
        c = LP["cap"]
        base = size or c["size"]
        cid = self.nid("c")
        self.SECTIONS.append((cid, t0, t1, "cap"))
        self.H.append(f'<div id="{cid}" class="clip cap" data-start="{fr(t0):.4f}" data-duration="{fr(t1) - fr(t0):.4f}" '
                      f'data-track-index="{self.track()}" style="z-index:{z};bottom:{1920 - c["bottom"]}px">')
        keys = []
        for li, line in enumerate(lines):
            chunks = [(ch[0], ch[1], ch[2] if len(ch) > 2 else 1.0) for ch in line]
            want = base * max(m for _, _, m in chunks)
            texts = [tx + ("" if i == len(chunks) - 1 else " ") for i, (tx, _, _) in enumerate(chunks)]
            sizes = [base * m for _, _, m in chunks]
            wid = sum(self._chunk_w(tx, s, i == 0, i == len(chunks) - 1) for i, (tx, s) in enumerate(zip(texts, sizes)))
            k = min(1.0, c["maxw"] / wid)
            if want * k < c["min_size"]:
                raise ValueError(f"caption line too long even at {c['min_size']} px: {texts}")
            self.H.append('<div class="ln">')
            for i, (tx, t, s) in enumerate(zip(texts, [x[1] for x in chunks], sizes)):
                s = s * k
                chid = f"{cid}_{li}_{i}"
                pl = c["pad_x"] if i == 0 else 0
                pr = c["pad_x"] if i == len(chunks) - 1 else 0
                m = KW.search(tx)
                if m:
                    kp = c["kw_pad"] * s / 84
                    inner = (esc(tx[:m.start()]) + f'<span class="kw" style="padding:0 {kp:.1f}px"><i id="{chid}_kb" class="kb"></i>'
                             f'<b id="{chid}_kt">{esc(m.group(1))}</b></span>' + esc(tx[m.end():]))
                    self.wipe(f"#{chid}_kb", f"#{chid}_kt", t + 0.05)
                    self.SFX.append((KIT["keyword"], t + 0.05, 0.22, 0.0, None))
                else:
                    inner = esc(tx)
                self.H.append(f'<span id="{chid}" class="ch" style="font-size:{s:.1f}px;padding:0 {pr}px 0 {pl}px">{inner}</span>')
                self.slam(f"#{chid}", t)
                keys.append(t + 0.3)
                self.SAID.append((t, KW.sub(r"\1", tx)))
            self.H.append("</div>")
        self.H.append("</div>")
        self.beat(cid, keys + [t1 - 0.05])
        return cid

    # ------------------------------------------------------------ chrome: bug + source tag
    def bug(self, t, a, b):
        """bug(): honey block + dark chip, top left, 48 px caps; stays to the end"""
        L = LP["bug"]
        self.H.append(f'<div id="bug" class="clip" data-start="{fr(t):.4f}" data-duration="{self.dur - fr(t):.4f}" '
                      f'data-track-index="{self.track()}" style="z-index:40;left:{L["x"]}px;top:{L["y"]}px;height:{L["h"]}px;'
                      f'display:flex;opacity:0"><span class="bg1">{esc(a)}</span><span class="bg2">{esc(b)}</span></div>')
        self.tween("#bug", {"opacity": 0}, {"opacity": 1, "duration": 0.25, "ease": "power2.out"}, t)
        w = adv(a, L["size"]) + adv(b, L["size"]) + 4 * 22
        if L["x"] + w > 980:
            raise ValueError(f"bug too wide: {w:.0f} px")

    def source(self, t0, t1, label, text):
        """sourceTag(): a white label block + a dark label, slides in from the left in 0.2 s under the bug"""
        S = LP["source"]
        sid = self.nid("src")
        if 64 + adv(text, S["size"], 600) + 44 > 980:
            raise ValueError(f"source label too wide: {text}")
        self.H.append(f'<div id="{sid}" class="clip" data-start="{fr(t0):.4f}" data-duration="{fr(t1) - fr(t0):.4f}" '
                      f'data-track-index="{self.track()}" style="z-index:40;left:64px;top:{S["y1"]}px;opacity:0">'
                      f'<div class="sl1">{esc(label)}</div><div class="sl2">{esc(text)}</div></div>')
        self.tween(f"#{sid}", {"x": -40, "opacity": 0}, {"x": 0, "opacity": 1, "duration": 0.2, "ease": "power2.out"}, t0)
        self.SFX.append((KIT["source_tag"], t0, 0.3, 0.0, None))

    # ------------------------------------------------------------ title sting -> bug
    def sting(self, t0, t1, title, chip=None, bug=None):
        """shotSting() for 9:16: a honey ruled page wipes over the bottom band (y >= 1140, under the speaker's chin) while the speaker's plate
        stays live above; the title slams word by word (title = [(text, t)], one line each, ink caps; a {word} gets an
        ink block); a chip follows; the page wipes off left and the title becomes the bug (bug = (honey part, dark part))."""
        S = LP["sting"]
        sid = self.nid("sting")
        top = S["top"]
        hgt = 1920 - top
        self.SECTIONS.append((sid, t0, t1, "sting"))
        self.H.append(f'<section id="{sid}" class="clip" data-start="{fr(t0):.4f}" data-duration="{fr(t1) - fr(t0):.4f}" '
                      f'data-track-index="{self.track()}" style="z-index:20;left:0;top:{top}px;width:1080px;height:{hgt}px;overflow:hidden">'
                      f'<div id="{sid}_pg" class="page" style="width:1080px;height:{hgt}px;clip-path:inset(0% 100% 0% 0%)">')
        for i in range(hgt // S["rule_every"]):
            self.H.append(f'<i id="{sid}_r{i}" class="rule" style="top:{40 + i * S["rule_every"]}px"></i>')
            self.tween(f"#{sid}_r{i}", {"scaleX": 0}, {"scaleX": 1, "duration": 0.3, "ease": "power2.out"}, t0 + 0.12 + i * 0.025)
        for j, x in enumerate(S["margin_x"]):
            self.H.append(f'<i id="{sid}_m{j}" class="marg" style="left:{x}px;height:{hgt}px"></i>')
            self.tween(f"#{sid}_m{j}", {"scaleY": 0}, {"scaleY": 1, "duration": 0.4, "ease": "power2.out"}, t0 + 0.15)
        n = len(title)
        px = S["title_px"]
        for tx, _ in title:
            px = min(px, (1080 - S["title_x"] - 100) / max(adv(KW.sub(r"\1", tx), 1) + 0.3, 1e-3))
        if px < 60:
            raise ValueError("sting title too long")
        y = 70
        keys = []
        for i, (tx, t) in enumerate(title):
            m = KW.search(tx)
            inner = esc(tx) if not m else (esc(tx[:m.start()]) + f'<span class="inv">{esc(m.group(1))}</span>' + esc(tx[m.end():]))
            self.H.append(f'<div id="{sid}_t{i}" class="stt" style="left:{S["title_x"]}px;top:{y:.0f}px;font-size:{px:.1f}px">{inner}</div>')
            self.slam(f"#{sid}_t{i}", t, 1.35)
            self.SAID.append((t, KW.sub(r"\1", tx)))
            keys.append(t + 0.25)
            y += px * 1.02
        if chip:
            self.H.append(f'<div id="{sid}_chip" class="chip" style="left:{S["title_x"]}px;top:{y + 24:.0f}px">'
                          f'<i class="dot"></i>{esc(chip[0])}</div>')
            self.tween(f"#{sid}_chip", {"opacity": 0, "x": 30}, {"opacity": 1, "x": 0, "duration": 0.2, "ease": "power2.out"}, chip[1])
            keys.append(chip[1] + 0.25)
        self.H.append("</div></section>")
        self.tween(f"#{sid}_pg", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.2,
                                                                         "ease": "power2.out"}, t0)
        self.tween(f"#{sid}_pg", {"x": 0}, {"x": -1080, "duration": 0.18, "ease": "power2.in"}, t1 - 0.18)
        self.SFX.append((KIT["sting_in"], t0, 0.5, 0.0, None))
        self.SFX.append((KIT["sting_out"], t1 - 0.3, 0.3, 0.0, None))
        if bug:
            self.bug(t1 - 0.1, *bug)
        self.beat(sid, keys + [t0 + 0.25])

    # ------------------------------------------------------------ cutaway cards on the ledger
    def _card(self, cid, t0, t1, bg, ledger=True, slide=True, push=(1.0, 1.03)):
        self.SECTIONS.append((cid, t0, t1, "card"))
        self.H.append(f'<section id="{cid}" class="clip full" data-start="{fr(t0):.4f}" data-duration="{fr(t1) - fr(t0):.4f}" '
                      f'data-track-index="{self.track()}" style="z-index:10;background:{bg};overflow:hidden">'
                      f'<div id="{cid}_in" class="full">')
        if ledger:
            for i, y in enumerate(range(120, 1920, 54)):
                self.H.append(f'<i class="lrule" style="top:{y}px"></i>')
            self.H.append('<i class="lmarg" style="left:40px"></i><i class="lmarg" style="left:48px"></i>')
        self.H.append(f'<div id="{cid}_push" class="full">')
        if slide:
            self.tween(f"#{cid}_in", {"x": 1080}, {"x": 0, "duration": 0.18, "ease": "power2.out"}, t0)
            for i in range(6):
                self.H.append(f'<i id="{cid}_sk{i}" class="streak" style="top:{300 + i * 230}px"></i>')
            self.tween(f"#{cid}_push .streak", {"x": 300, "opacity": 0.5}, {"x": -1400, "opacity": 0, "duration": 0.26,
                                                                           "ease": "power2.out"}, t0)
            self.SFX.append((KIT["card_in"], t0 - 0.05, 0.4, 0.0, None))
        if push:
            self.tween(f"#{cid}_push", {"scale": push[0]}, {"scale": push[1], "duration": t1 - t0, "ease": "sine.inOut"}, t0)

    def _card_close(self):
        self.H.append("</div></div></section>")

    def doc(self, t0, t1, img, marks, block=None, source=None, img_px=(666, 1000), vignette=True):
        """paper() + shotDoc6(): the source (a cover, a page) on a dark desk, tilted, pushed in slowly (never past 1:1 of
        img); highlighter rectangles marks = [(t, x0, y0, x1, y1, sweep s)] in img px, multiply, swept left -> right; then
        block = (text, t[, said words]) re-set in a honey block beside it; source = (label, text, t) the tag under the bug."""
        cid = self.nid("doc")
        D = LP["doc"]
        self._card(cid, t0, t1, PAL["desk"], ledger=False, slide=False, push=None)
        bx = D["cover_box"]
        sc = min((bx[2] - bx[0]) / img_px[0], (bx[3] - bx[1]) / img_px[1], 1.0)
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        self.H.append(f'<div id="{cid}_pp" class="paper" style="left:{cx - img_px[0] / 2:.0f}px;top:{cy - img_px[1] / 2:.0f}px;'
                      f'width:{img_px[0]}px;height:{img_px[1]}px;transform:rotate({D["tilt_deg"]}deg) scale({sc * D["push"][0]:.4f})">'
                      f'<img src="{img}" width="{img_px[0]}" height="{img_px[1]}" style="display:block">')
        keys = [t0 + 0.1]
        for i, (t, x0, y0, x1, y1, sw) in enumerate(marks):
            self.H.append(f'<i id="{cid}_hl{i}" class="hl" style="left:{x0 - 8}px;top:{y0 - 5}px;width:{x1 - x0 + 16}px;height:{y1 - y0 + 10}px"></i>')
            self.tween(f"#{cid}_hl{i}", {"scaleX": 0}, {"scaleX": 1, "duration": sw, "ease": "power1.inOut"}, t)
            self.SFX.append((KIT["highlighter"], t, 0.35, 0.0, None))
            keys.append(t + sw + 0.05)
        self.H.append("</div>")
        self.tween(f"#{cid}_pp", {"scale": sc * D["push"][0]}, {"scale": sc * D["push"][1], "duration": t1 - t0, "ease": "sine.inOut"}, t0)
        if vignette:
            self.H.append('<i class="vig"></i>')
        if block:
            txt, tb = block[0], block[1]
            px = D["block_px"]
            w = adv(txt, px) + 2 * 28
            if w > 916:
                px = px * 916 / w
                w = 916
            self.H.append(f'<div id="{cid}_blk" class="blk" style="left:{max(64, 980 - w):.0f}px;top:{bx[3] - 40}px;font-size:{px:.1f}px">{esc(txt)}</div>')
            self.slam(f"#{cid}_blk", tb, 1.4)
            self.SFX.append((KIT["keyword"], tb, 0.35, 0.0, None))
            keys.append(tb + 0.3)
            for wt in block[2] if len(block) > 2 else []:
                self.SAID.append(wt)
        self._card_close()
        self.SFX.append((KIT["doc"], t0, 0.45, 0.0, None))
        if source:
            self.source(source[2], t1, source[0], source[1])
            keys.append(source[2] + 0.3)
        self.beat(cid, keys + [t1 - 0.05])
        return cid

    def grid(self, t0, t1, panels):
        """shotGrid() stacked for 9:16: panels = [(label, icon, t)] rise staggered 0.1 s; each lights on its word (honey
        border, honey label, the icon turns ivory, a red notification dot pops); numbered 1-2-3."""
        cid = self.nid("grid")
        G = LP["grid"]
        self._card(cid, t0, t1, PAL["sheet"])
        keys = []
        for i, (label, icon, t) in enumerate(panels):
            y = G["top"] + i * (G["h"] + G["gap"])
            pid = f"{cid}_p{i}"
            px = min(G["label_px"], (G["w"] - 80 - 240) / max(adv(label, 1), 1e-3))
            self.H.append(f'<div id="{pid}" class="gp" style="left:{G["x"]}px;top:{y}px;width:{G["w"]}px;height:{G["h"]}px">'
                          f'<div class="gn" style="font-size:{G["num_px"]}px">{i + 1}</div>'
                          f'<div id="{pid}_l" class="gl" style="font-size:{px:.1f}px">{esc(label)}</div>'
                          f'<svg id="{pid}_ic" class="gi" viewBox="0 0 200 200" width="220" height="220">{ICONS[icon]}</svg>'
                          f'<i id="{pid}_dot" class="gdot"></i></div>')
            self.tween(f"#{pid}", {"y": 80, "opacity": 0}, {"y": 0, "opacity": 1, "duration": 0.25, "ease": "power3.out"}, t0 + 0.05 + i * 0.1)
            self.set(f"#{pid}", {"borderColor": PAL["honey"]}, t)
            self.set(f"#{pid}_l", {"color": PAL["honey"]}, t)
            self.set(f"#{pid}_ic", {"color": PAL["ivory"]}, t)
            self.tween(f"#{pid}_l", {"scale": 1.25}, {"scale": 1, "duration": 0.13, "ease": "back.out(1.6)"}, t)
            self.tween(f"#{pid}_dot", {"scale": 0}, {"scale": 1, "duration": 0.18, "ease": "back.out(2)"}, t + 0.06)
            self.SFX.append((KIT["grid_light"], t, 0.35, 0.0, None))
            self.SAID.append((t, label))
            keys.append(t + 0.3)
        self._card_close()
        self.beat(cid, keys + [t0 + 0.4])
        return cid

    def ruled_list(self, t0, t1, title, rows, said_title=False):
        """the ledger card as a list (the bar chart's grammar without numbers): a title top left, then rows = [(label, t)]:
        the numeral slams, a honey bar grows from the left with the label on it; the previous bar turns ivory."""
        cid = self.nid("list")
        Lr = LP["list"]
        self._card(cid, t0, t1, PAL["sheet"])
        self.H.append(f'<div id="{cid}_ti" class="lt" style="top:{Lr["title_y"] - 90}px">{esc(title)}</div>'
                      f'<i class="lrl" style="top:{Lr["title_y"] + 24}px"></i>')
        self.tween(f"#{cid}_ti", {"opacity": 0, "y": 10}, {"opacity": 1, "y": 0, "duration": 0.18, "ease": "power2.out"}, t0 + 0.12)
        if said_title:
            self.SAID.append((t0, title))
        keys = [t0 + 0.4]
        for i, (label, t) in enumerate(rows):
            y = Lr["row_y"][i]
            rid = f"{cid}_r{i}"
            px = min(Lr["label_px"], (Lr["bar_maxw"] - 60) / max(adv(label, 1), 1e-3))
            w = Lr["bar_maxw"]                      # no data -> every bar the same length (no invented proportion)
            self.H.append(f'<div id="{rid}_n" class="ln_n" style="top:{y}px;font-size:{Lr["num_px"]}px;opacity:0">{i + 1}</div>'
                          f'<div id="{rid}_b" class="lbar" style="left:{Lr["bar_x"]}px;top:{y}px;width:{w:.0f}px;height:{Lr["bar_h"]}px">'
                          f'<span id="{rid}_t" style="font-size:{px:.1f}px">{esc(label)}</span></div>')
            self.slam(f"#{rid}_n", t - 0.02, 1.4)
            self.tween(f"#{rid}_b", {"scaleX": 0}, {"scaleX": 1, "duration": 0.3, "ease": "power2.out"}, t)
            self.tween(f"#{rid}_t", {"opacity": 0}, {"opacity": 1, "duration": 0.1}, t + 0.12)
            if i:
                self.set(f"#{cid}_r{i - 1}_b", {"backgroundColor": PAL["ivory"]}, t)
            self.SFX.append((KIT["list_row"], t, 0.4, 0.0, None))
            self.SAID.append((t, label))
            keys.append(t + 0.35)
        self._card_close()
        self.beat(cid, keys + [t1 - 0.05])
        return cid

    # ------------------------------------------------------------ plates + sound
    def plates(self, switches):
        """the speaker's own framing switches: [(t, plate key)], hard; the speaker's face is never graded, filtered or covered"""
        self.switches = switches
        for t, p in switches:
            for k in self.plates_:
                self.set(f"#v{k}", {"autoAlpha": 1 if k == p else 0}, t)

    def sfx(self, name, t, vol, ms=0.0, dur=None):
        self.SFX.append((name, t, vol, ms, dur))

    # ------------------------------------------------------------ write
    def _check_words(self):
        shown = []
        for _, s in sorted(self.SAID, key=lambda x: x[0]):
            shown += [norm(w) for w in s.split() if norm(w)]
        spoken = [self.aliases.get(norm(w), norm(w)) for w, _, _ in self.W if norm(w)]
        if shown != spoken:
            import difflib
            diff = [d for d in difflib.ndiff(spoken, shown) if d[0] in "+-"]
            return f"words on screen differ from the speaker's words: {diff[:20]}"
        return f"every spoken word on screen in order: {len(spoken)} words"

    def build(self):
        P, DUR = self.P, self.dur
        sfx_lens = {}
        aud = [f'<audio id="vo" src="{self.voice}" data-start="0" data-duration="{self.voice_dur:.2f}" data-track-index="200" data-volume="1"></audio>']
        for i, (f, t, v, ms, dur) in enumerate(sorted(self.SFX, key=lambda s: s[1])):
            os.makedirs(f"{P}/assets/sfx", exist_ok=True)
            dst = f"{P}/assets/sfx/{f}.wav"
            if not os.path.exists(dst):
                man = json.load(open(f"{SKILL}/library/sfx/manifest.json"))
                if man.get(f, {}).get("licensed") is False:
                    raise ValueError(f"{f}: not licensed (a rip); never in a port")
                shutil.copy(f"{SKILL}/library/sfx/{man[f]['file']}", dst)
            if f not in sfx_lens:
                sfx_lens[f] = round(probe_dur(dst), 3)
            t = max(0.0, t)
            dd = min(dur or sfx_lens[f], DUR - t)
            aud.append(f'<audio id="sfx{i}" src="assets/sfx/{f}.wav" data-start="{fr(t):.4f}" data-duration="{dd:.4f}" '
                       f'data-media-start="{ms:.3f}" data-track-index="{201 + i}" data-volume="{v}"></audio>')
        faces = "".join(f"@font-face {{ font-family: '{fam}'; src: url('assets/fonts/{fn}-{sub}.woff2') format('woff2'); "
                        f"font-weight: {wt}; font-style: {sty}; unicode-range: {rng}; }}\n"
                        for fam, fn, wt, sty in TY["font_faces"] for sub, rng in TY["unicode_ranges"])
        vids = "\n".join(f'<video id="v{k}" class="full" src="{v}" data-start="0" data-duration="{DUR:.2f}" data-track-index="{i}" '
                         f'muted playsinline></video>' for i, (k, v) in enumerate(self.plates_.items()))
        c = LP["cap"]
        css = f"""
{faces}html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; font-family: {FONT}; }}
.full {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }}
video.full {{ object-fit: cover; }}
.clip {{ position: absolute; }}
i {{ font-style: normal; }}
.cap {{ left: {c['x']}px; display: flex; flex-direction: column; align-items: flex-start; gap: {c['line_gap']}px; }}
.ln {{ display: flex; white-space: pre; }}
.ch {{ display: inline-block; font-weight: 900; letter-spacing: {TRACK}em; line-height: {c['lh']}; color: {PAL['ivory']};
       background: {PAL['slab']}; transform-origin: 0% 70%; opacity: 0; white-space: pre; }}
.kw {{ position: relative; display: inline-block; }}
.kb {{ position: absolute; left: 0; right: 0; top: 0.08em; bottom: 0.06em; background: {PAL['honey']}; transform-origin: 0% 50%; transform: scaleX(0); }}
.kw b {{ position: relative; font-weight: 900; color: {PAL['ivory']}; }}
.bg1, .bg2 {{ display: flex; align-items: center; font-weight: 900; font-size: {LP['bug']['size']}px; letter-spacing: 0.01em; padding: 0 22px; }}
.bg1 {{ background: {PAL['honey']}; color: {PAL['ink']}; }}
.bg2 {{ background: rgba(14,14,12,.72); color: {PAL['ivory']}; }}
.sl1, .sl2 {{ height: {LP['source']['h']}px; display: inline-flex; align-items: center; padding: 0 22px; font-size: {LP['source']['size']}px; }}
.sl1 {{ background: {PAL['ivory']}; color: {PAL['ink']}; font-weight: 900; letter-spacing: 0.01em; }}
.sl2 {{ display: flex; width: max-content; margin-top: 8px; background: rgba(14,14,12,.84); color: {PAL['ivory']}; font-weight: 600; }}
.page {{ position: absolute; left: 0; top: 0; background: {PAL['honey']}; }}
.rule {{ position: absolute; left: 0; width: 1080px; height: 2px; background: rgba(14,14,12,.13); transform-origin: 0 50%; }}
.marg {{ position: absolute; top: 0; width: 2px; background: rgba(200,40,30,.5); transform-origin: 50% 0; }}
.stt {{ position: absolute; font-weight: 900; color: {PAL['ink']}; letter-spacing: -0.01em; line-height: 1; white-space: pre; transform-origin: 0% 70%; opacity: 0; }}
.inv {{ background: {PAL['ink']}; color: {PAL['honey']}; padding: 0 0.12em; }}
.chip {{ position: absolute; display: flex; align-items: center; gap: 18px; height: 72px; padding: 0 28px; background: {PAL['ink']};
        color: {PAL['honey']}; font-weight: 900; font-size: 48px; letter-spacing: 0.02em; opacity: 0; }}
.dot {{ width: 18px; height: 18px; border-radius: 50%; background: {PAL['loss']}; display: inline-block; }}
.lrule {{ position: absolute; left: 0; width: 1080px; height: 2px; background: {PAL['rule']}; }}
.lmarg {{ position: absolute; top: 0; width: 2px; height: 1920px; background: {PAL['margin']}; }}
.streak {{ position: absolute; left: 0; width: 900px; height: 4px; background: {PAL['honey']}; opacity: 0; }}
.paper {{ position: absolute; transform-origin: 50% 50%; box-shadow: 0 30px 80px rgba(0,0,0,.6); background: #fff; }}
.hl {{ position: absolute; background: rgba(255,200,30,.88); mix-blend-mode: multiply; transform-origin: 0 50%; transform: scaleX(0); }}
.vig {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; background: radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 40%, rgba(0,0,0,.55) 100%); }}
.blk {{ position: absolute; background: {PAL['honey']}; color: {PAL['ink']}; font-weight: 900; padding: 6px 28px 10px; line-height: 1.1;
       letter-spacing: -0.01em; white-space: pre; transform: rotate(-3deg); transform-origin: 0% 70%; opacity: 0; box-shadow: 0 16px 40px rgba(0,0,0,.45); }}
.gp {{ position: absolute; box-sizing: border-box; background: {PAL['panel']}; border: 6px solid {PAL['panel_edge']}; opacity: 0; }}
.gn {{ position: absolute; left: 30px; top: 22px; font-weight: 900; color: {PAL['honey']}; font-variant-numeric: tabular-nums; line-height: 1; }}
.gl {{ position: absolute; left: 30px; bottom: 34px; font-weight: 900; color: {PAL['grey']}; letter-spacing: -0.02em; line-height: 1;
      white-space: pre; transform-origin: 0% 70%; }}
.gi {{ position: absolute; right: 40px; top: 70px; color: {PAL['muted']}; fill: none; stroke: currentColor; stroke-width: 10;
      stroke-linecap: round; stroke-linejoin: round; }}
.gi circle {{ fill: currentColor; stroke: none; }}
.gdot {{ position: absolute; right: 44px; top: 60px; width: 54px; height: 54px; border-radius: 50%; background: {PAL['loss']};
        border: 6px solid {PAL['panel']}; transform: scale(0); }}
.lt {{ position: absolute; left: 64px; font-weight: 900; font-size: 84px; color: {PAL['ivory']}; letter-spacing: -0.02em; opacity: 0; }}
.lrl {{ position: absolute; left: 64px; width: 916px; height: 4px; background: {PAL['honey']}; }}
.ln_n {{ position: absolute; left: 64px; width: 120px; font-weight: 900; color: {PAL['honey']}; line-height: 150px;
        font-variant-numeric: tabular-nums; transform-origin: 0% 70%; }}
.lbar {{ position: absolute; box-sizing: border-box; background: {PAL['honey']}; transform-origin: 0 50%; transform: scaleX(0);
        display: flex; align-items: center; padding-left: 30px; }}
.lbar span {{ font-weight: 900; color: {PAL['ink']}; letter-spacing: -0.02em; white-space: pre; opacity: 0; }}
"""
        html = (f"""<!doctype html>
<html lang="{self.lang}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{esc(self.page_title)}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>{css}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{DUR:.2f}" data-fps="{FPS}">
<div id="cam" class="full" style="z-index:1">
{vids}
</div>
""" + "\n".join(self.H) + "\n" + "\n".join(aud) +
                '\n<script>\nwindow.__timelines = window.__timelines || {};\nconst tl = gsap.timeline({ paused: true });\n' +
                "\n".join(self.JS) + f'\ntl.set({{}}, {{}}, {DUR:.2f});\nwindow.__timelines["main"] = tl;\n</script>\n</div>\n</body>\n</html>\n')
        open(f"{P}/index.html", "w").write(html)
        cards = [(a, b) for _, a, b, k in self.SECTIONS if k == "card"]
        shots = [{"t0": a, "t1": b} for a, b in sorted(cards)]
        os.makedirs(f"{P}/build", exist_ok=True)
        json.dump({"fps": FPS, "beats": sorted(self.BEATS, key=lambda b: b["t0"]), "shots": shots},
                  open(f"{P}/build/beats.json", "w"), indent=1, ensure_ascii=False)
        away = sum(b - a for a, b in cards)
        lines = [f"the speaker's face on screen: {DUR - away:.2f} s of {DUR:.2f} s = {100 * (DUR - away) / DUR:.1f} % (cards {away:.2f} s)",
                 self._check_words(),
                 f"captions: {sum(1 for s in self.SECTIONS if s[3] == 'cap')}; cards: {len(cards)}; sfx: {len(self.SFX)}; html {len(html) // 1024} KB"]
        open(f"{P}/build/coverage.txt", "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return lines


if __name__ == "__main__":
    print(__doc__)
