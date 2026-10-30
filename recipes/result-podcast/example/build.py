#!/usr/bin/env python3
"""RESULT worked example: "keep the paper" (script.txt) -> index.html (HyperFrames 1080x1920).

A storytelling talking head about keeping one paper thing from every day of a trip. One/two-word centred captions in
Inter Tight, two-tier emphasis (small line + big bold word), Caveat key words, film-burn light leaks at the three turns,
navy and kraft surfaces, artifacts from the story's world that move like paper (a train ticket that gets stamped, a
thermal receipt that prints and gets circled, a notebook page that closes over a pressed leaf, a paper stack whose
pictures swap stop-motion, a polaroid with a ticket on top, a sticky note), comic props over the speaker (a photo count
notification, a storage dialog a cursor dismisses, two emoji stickers with the only two punch-ins), dust + grain.

Inputs (in $P): build/takes.json + build/rough.mp4 (takes.py), build/rough.words.json (transcribe.py on the rough cut,
--lang en), assets/talk.mp4, assets/broll/{train,cafe,park,harbour,box,leaf}.png (gen_broll.sh), fonts:
    python3 $S/recipes/clean-os/fetch_fonts.py $P "Inter Tight:ital,wght@0,400..800;1,400..800" "Caveat:wght@400..700"
Every beat is keyed to the spoken words: W("word", n) is the n-th occurrence, "a|b" accepts either spelling.
"""
import json, os, re, shutil, subprocess

FPS = 30
S = os.path.expanduser(os.environ.get("S", "~/.claude/skills/ghost-editor"))
T = json.load(open("build/takes.json"))

# ---------------------------------------------------------------- timeline of parts
clips, t = [], 0.0
for li, tk in enumerate(T):
    for a, b in tk["parts"]:
        clips.append({"a": a, "b": b, "s": round(t, 3), "line": li})
        t += b - a
SPEECH_END = round(t, 3)
OUTRO = 2.2
TOTAL = round(SPEECH_END + OUTRO, 3)

# ---------------------------------------------------------------- words (edit time = rough-cut time)
raw = json.load(open("build/rough.words.json"))
words = []
for w in (w for s in raw["segments"] for w in s["words"]):
    txt = w["word"].strip()
    # glue fragments whisper splits off ("3" + ",000", "half" + "-written")
    if words and txt[:1] in "-.,":
        words[-1]["w"] += txt; words[-1]["e"] = round(w["end"], 3); continue
    words.append({"w": txt, "s": round(w["start"], 3), "e": round(w["end"], 3)})
words[-1]["e"] = min(words[-1]["e"], SPEECH_END)


def norm(x):
    return re.sub(r"[^a-z0-9]", "", x.lower())


def W(text, n=1, end=False):
    keys = {norm(k) for k in text.split("|")}
    k = 0
    for w in words:
        if norm(w["w"]) in keys:
            k += 1
            if k == n:
                return w["e"] if end else w["s"]
    raise SystemExit(f"word not found: {text} #{n}")


# ---------------------------------------------------------------- timeline helpers
tl, based = [], set()


def tw(sel, frm, to, at):
    if sel not in based:
        based.add(sel); tl.append(f'tl.set("{sel}", {json.dumps(frm)}, 0);')
    tl.append(f'tl.fromTo("{sel}", {json.dumps(frm)}, {json.dumps({**to, "immediateRender": False})}, {max(0, at):.3f});')


def st(sel, props, at):
    tl.append(f'tl.set("{sel}", {json.dumps(props)}, {max(0, at):.3f});')


sfx = []  # (id, at, vol)


def sound(sid, at, vol):
    sfx.append((sid, max(0, round(at, 3)), vol))


# ---------------------------------------------------------------- speaker clips
# Picture: each clip overlaps the previous by XF and dissolves in (a "morph cut"), so the
# small head-position jumps between takes read as a soft transition. Sound stays hard-cut.
XF = 0.2
clip_html = []
for i, c in enumerate(clips):
    d = round(c["b"] - c["a"], 3)
    pre = XF if i else 0.0
    op = ';opacity:0' if i else ''          # (Python 3.11: no reused quotes inside an f-string)
    clip_html.append(f'<video id="v{i}" class="clip fill" style="z-index:{i + 1}{op}" src="assets/talk.mp4" data-start="{round(c["s"] - pre, 3)}" data-duration="{round(d + pre, 3)}" data-media-start="{round(c["a"] - pre, 3)}" data-track-index="{i % 2}" muted playsinline></video>')
    clip_html.append(f'<audio id="a{i}" src="assets/talk.mp4" data-start="{c["s"]}" data-duration="{d}" data-media-start="{c["a"]}" data-track-index="{10 + i % 2}" data-volume="1"></audio>')
    if i:
        tw(f"#v{i}", {"opacity": 0}, {"opacity": 1, "duration": XF, "ease": "none"}, c["s"] - pre)

# ---------------------------------------------------------------- scenes
scenes_html, hide_caps, low_caps, leaks = [], [], [], []
NAVY, KRAFT = "#141A26", "#B98E5E"


def scene(sid, a, b, inner, bg=NAVY, caps=True):
    scenes_html.append(f'<div id="{sid}" class="scene{" kraft" if bg == KRAFT else ""}" style="background:{bg}">{inner}</div>')
    tw(f"#{sid}", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.12}, a)
    tw(f"#{sid}", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.06}, b - 0.06)
    (low_caps if caps else hide_caps).append((a, b) if caps else (a, b - 0.32))


def ticket(tid, extra=""):
    return (f'<div id="{tid}" class="ticket"><div class="tk-l"><span class="tk-sm">regional rail</span><b>07:12 → 09:48</b>'
            f'<span class="tk-sm">platform 4 · coach 2</span></div><div class="tk-r"><span>seat</span><b>31</b></div>{extra}</div>')


# S2 kraft: the train ticket slides in, "DAY 1" is stamped on «first»
a2, b2 = W("ticket") - 0.25, min(W("train", end=True) + 0.35, W("receipt") - 0.1)
scene("s2", a2, b2, ticket("s2t", '<div id="s2s" class="stamp">day 1</div>'), bg=KRAFT)
tw("#s2t", {"x": 520, "rotation": 14, "autoAlpha": 0}, {"x": 0, "rotation": -4, "autoAlpha": 1, "duration": 0.45, "ease": "power3.out"}, a2)
tw("#s2s", {"autoAlpha": 0, "scale": 1.7, "rotation": -4}, {"autoAlpha": 0.92, "scale": 1, "rotation": -14, "duration": 0.14, "ease": "power4.in"}, W("first") - 0.1)
sound("pop-1", a2 + 0.05, 0.07)
sound("impact-2", W("first") + 0.03, 0.10)

# S3 navy: the receipt prints out of the slot; the missing address is circled on «never»
a3, b3 = W("receipt") - 0.2, min(W("again", end=True) + 0.4, W("leaf") - 0.1)
scene("s3", a3, b3, """
 <div class="rcwrap"><div class="rcclip"><div id="s3r" class="receipt">
  <div class="rc-h">café</div><div class="rc-s">table 6 · 08:31</div>
  <div class="rc-row"><span>1 flat white</span><span>3.40</span></div>
  <div class="rc-row"><span>1 almond croissant</span><span>2.90</span></div>
  <div class="rc-row tot"><span>total</span><span>6.30</span></div>
  <div class="rc-addr">rua ▇▇▇▇▇▇▇ 1▇<svg class="mark" viewBox="0 0 600 130" preserveAspectRatio="none"><ellipse id="s3m" cx="300" cy="65" rx="285" ry="56" pathLength="1"/></svg></div>
  <div class="rc-thx">thank you · come again</div></div></div><div class="slot"></div>
  <div id="s3n" class="hand note">where was this?</div></div>""")
tw("#s3r", {"yPercent": 101}, {"yPercent": 0, "duration": round(W("never") - 0.15 - (a3 + 0.15), 3), "ease": "steps(16)"}, a3 + 0.15)
sound("typing-1", a3 + 0.15, 0.06)
tw("#s3m", {"strokeDashoffset": 1}, {"strokeDashoffset": 0, "duration": 0.45, "ease": "power1.inOut"}, W("never") - 0.05)
sound("marker-scribble", W("never") - 0.05, 0.10)
tw("#s3n", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.5, "ease": "power1.inOut"}, W("find") - 0.02)

# S4 kraft: a notebook spread, the pressed leaf; the right page closes over it on «between»
a4, b4 = W("leaf") - 0.2, min(W("pages", end=True) + 0.45, W("phone") - 0.15)
scene("s4", a4, b4, """
 <div id="s4b" class="nb"><div class="pg l"><img src="assets/broll/leaf.png"/><div id="s4n" class="hand">day 3 · the park</div></div>
  <div id="s4p" class="pg r"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div></div>""", bg=KRAFT)
tw("#s4b", {"y": 140, "rotation": -6, "autoAlpha": 0}, {"y": 0, "rotation": -1.5, "autoAlpha": 1, "duration": 0.45, "ease": "power3.out"}, a4)
tw("#s4n", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.55, "ease": "power1.inOut"}, W("park") - 0.05)
sound("pencil-write", W("park") - 0.05, 0.08)
tw("#s4p", {"rotationY": 0}, {"rotationY": -178, "duration": 0.5, "ease": "power2.inOut"}, W("between") - 0.1)
sound("whoosh-1", W("between") - 0.05, 0.07)

# S5 over the speaker: the photo count notification, 3000 on «thousand»
a5 = W("phone") - 0.1
scenes_html.append("""<div id="s5" class="notif"><div class="nhead"><span class="nico">📷</span>PHOTOS<span class="nnow">now</span></div>
 <div class="nt"><span id="s5c">0</span> photos</div><div class="nb2">from the same trips</div></div>""")
tw("#s5", {"y": -260, "autoAlpha": 0}, {"y": 0, "autoAlpha": 1, "duration": 0.45, "ease": "back.out(1.6)"}, a5)
tw("#s5c", {"textContent": 0}, {"textContent": 3000, "duration": 0.7, "ease": "power2.out", "snap": {"textContent": 10}}, W("thousand|3000") - 0.35)
tw("#s5", {"y": 0, "autoAlpha": 1}, {"y": -260, "autoAlpha": 0, "duration": 0.35, "ease": "power2.in"}, W("them", end=True) + 0.1)
sound("pop-2", a5, 0.1)

# S7 over the speaker: the storage dialog; a cursor clicks «later» on «again»
a7 = W("storage") - 0.2
d7 = min(W("again", 2, end=True) + 0.45, W("but") - 0.1)
scenes_html.append("""<div id="s7" class="dialog"><div class="dico">⚠️</div><div class="dt">Storage almost full</div><div class="db">You can free up space in Settings.</div>
 <div class="dbtns"><span id="s7l">Later</span><span class="pri">Manage</span></div></div><div id="cur" class="cursor">➤</div>""")
tw("#s7", {"scale": 0.7, "autoAlpha": 0}, {"scale": 1, "autoAlpha": 1, "duration": 0.35, "ease": "back.out(1.8)"}, a7)
tw("#s7", {"scale": 1, "autoAlpha": 1}, {"scale": 0.9, "autoAlpha": 0, "duration": 0.25}, d7 - 0.25)
sound("tech-ui-error", a7, 0.08)
tw("#cur", {"x": 300, "y": 260, "autoAlpha": 0}, {"x": 0, "y": 0, "autoAlpha": 1, "duration": 0.45, "ease": "power2.out"}, W("again", 2) - 0.45)
tw("#cur", {"scale": 1}, {"scale": 0.8, "duration": 0.08, "yoyo": True, "repeat": 1}, W("again", 2) + 0.02)
tw("#s7l", {"backgroundColor": "rgba(10,99,216,0)"}, {"backgroundColor": "rgba(10,99,216,0.14)", "duration": 0.08}, W("again", 2) + 0.02)
tw("#cur", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.2}, d7 - 0.25)
sound("click-1", W("again", 2) + 0.02, 0.16)

# S8 kraft (the turn: a light leak): the paper stack, its pictures swap stop-motion «every winter»
a8, b8 = W("box") - 0.1, min(W("winter", end=True) + 0.35, W("because") - 0.08)
stack_imgs = ["train", "cafe", "park", "box"]
pics = "".join(f'<img id="s8i{i}" src="assets/broll/{n}.png"/>' for i, n in enumerate(stack_imgs))
scene("s8", a8, b8, f"""
 <div class="stack" style="top:190px"><div id="s8h1" class="script xl ink">the box</div><div id="s8h2" class="sm ink">every winter</div></div>
 <div id="s8s" class="paper" style="left:240px;top:560px;width:600px;height:740px"><div class="sheet s2"></div><div class="sheet s1"></div><div class="sheet top">{pics}<div class="clip-pin"></div></div></div>""", bg=KRAFT, caps=False)
leaks.append(a8 - 0.1)
tw("#s8h1", {"autoAlpha": 0, "y": 14}, {"autoAlpha": 1, "y": 0, "duration": 0.3}, W("box") - 0.05)
tw("#s8h2", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.2}, W("every", 2) - 0.05)
tw("#s8s", {"y": 120, "rotation": 8, "autoAlpha": 0}, {"y": 0, "rotation": -2, "autoAlpha": 1, "duration": 0.45, "ease": "back.out(1.4)"}, a8)
step = (b8 - a8 - 0.3) / len(stack_imgs)
for i in range(len(stack_imgs)):
    st(f"#s8i{i}", {"autoAlpha": 0}, 0); based.add(f"#s8i{i}")
    st(f"#s8i{i}", {"autoAlpha": 1}, a8 + i * step)
    if i < len(stack_imgs) - 1:
        st(f"#s8i{i}", {"autoAlpha": 0}, a8 + (i + 1) * step)
    st("#s8s", {"rotation": [-2, 1.5, -1, 2][i]}, a8 + i * step)
    sound("shutter-1", a8 + i * step, 0.04)

# S9 navy: the polaroid «where you were», then the ticket lands on it «who you were»
a9, b9 = W("photo") - 0.25, min(W("there", end=True) + 0.4, W("so") - 0.1)
scene("s9", a9, b9, f"""
 <div id="s9p" class="polaroid" style="left:150px;top:230px;width:700px;transform:rotate(-3deg)">
  <img src="assets/broll/harbour.png"/><div id="s9c" class="pcap">where you were</div></div><div id="s9f" class="flash"></div>
 {ticket("s9t", '<div id="s9w" class="hand onticket">who you were</div>')}""")
tw("#s9p", {"y": 140, "rotation": -10, "autoAlpha": 0}, {"y": 0, "rotation": -3, "autoAlpha": 1, "duration": 0.4, "ease": "power3.out"}, a9)
tw("#s9f", {"autoAlpha": 0}, {"autoAlpha": 0.9, "duration": 0.05}, W("photo") + 0.1)
tw("#s9f", {"autoAlpha": 0.9}, {"autoAlpha": 0, "duration": 0.3}, W("photo") + 0.16)
sound("shutter-1", W("photo") + 0.08, 0.14)
tw("#s9c", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.55, "ease": "power1.inOut"}, W("where") - 0.05)
tw("#s9t", {"x": 560, "y": 980, "rotation": 22, "autoAlpha": 0}, {"x": 180, "y": 1010, "rotation": 7, "autoAlpha": 1, "duration": 0.45, "ease": "power3.out"}, W("ticket", 2) - 0.2)
sound("pop-3", W("ticket", 2) - 0.15, 0.07)
tw("#s9w", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.5, "ease": "power1.inOut"}, W("who") - 0.05)
sound("pencil-write", W("who") - 0.05, 0.08)

# S11 over the speaker (a light leak): a sticky note slaps on «keep»
a11, b11 = W("keep", 2) - 0.08, W("your", 2) - 0.3
scenes_html.append('<div id="s11" class="sticky"><div class="hand">keep the paper ✓</div></div>')
leaks.append(W("so") - 0.1)
tw("#s11", {"autoAlpha": 0, "scale": 1.35, "rotation": -6}, {"autoAlpha": 1, "scale": 1, "rotation": 5, "duration": 0.22, "ease": "power4.in"}, a11)
tw("#s11", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.18}, b11 - 0.18)
sound("pop-3", a11 + 0.2, 0.09)

# S12 final navy card, held through the outro
a12 = W("your", 2) - 0.3
scene("s12", a12, TOTAL + 0.2, """
 <div class="stack" style="top:690px">
  <div id="f1" class="sm">your phone will</div><div id="f2" class="bg">forget.</div>
  <div id="f3" class="script xl" style="margin-top:40px">the box won't.</div></div>""", caps=False)
for el, key in (("f1", ("your", 2)), ("f2", ("forget", 1)), ("f3", ("box", 2))):
    tw(f"#{el}", {"autoAlpha": 0, "y": 18, "filter": "blur(8px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.35, "ease": "power3.out"}, W(*key) - 0.08)
tw("#f1", {"opacity": 1}, {"opacity": 0.4, "duration": 0.3}, W("box", 2) - 0.1)
tw("#f2", {"opacity": 1}, {"opacity": 0.4, "duration": 0.3}, W("box", 2) - 0.1)

# ---------------------------------------------------------------- comic punch-ins (two of the three allowed) + stickers
for word, back, z in ((("never", 2), W("storage") - 0.25, 1.18), (("again", 2), W("but") - 0.1, 1.16)):
    tw("#zoom", {"scale": 1}, {"scale": z, "duration": 0.12, "ease": "power3.out"}, W(*word) - 0.04)
    tw("#zoom", {"scale": z}, {"scale": 1, "duration": 0.01}, back)


def sticker(sid, emoji, a, b, x=700, y=560, size=170, rot=12):
    scenes_html.append(f'<div id="{sid}" class="sticker" style="left:{x}px;top:{y}px;font-size:{size}px">{emoji}</div>')
    tw(f"#{sid}", {"autoAlpha": 0, "scale": 0.3, "rotation": -rot}, {"autoAlpha": 1, "scale": 1, "rotation": rot, "duration": 0.35, "ease": "back.out(2.6)"}, a)
    tw(f"#{sid}", {"autoAlpha": 1, "scale": 1}, {"autoAlpha": 0, "scale": 0.6, "duration": 0.18, "ease": "power2.in"}, b - 0.18)
    sound("reaction-cartoon-pop", a, 0.06)


sticker("st1", "🙈", W("never", 2) - 0.02, W("storage") - 0.25, x=690, y=560)
sticker("st2", "🙄", W("again", 2) - 0.02, W("but") - 0.12, x=110, y=560, rot=-10)

# hook light leak on «trip»
leaks.append(W("trip") - 0.1)

# ---------------------------------------------------------------- captions
BIG = {"paper", "ticket", "receipt", "leaf", "3000", "thousand", "full", "box", "winter", "photo", "trip"}
SCRIPT = {"never", "again", "pages", "them", "there", "forget"}
hidden = lambda t: any(a - 0.05 <= t < b for a, b in hide_caps)
chunks, cur = [], []
for w in words:
    if hidden(w["s"]):
        if cur: chunks.append(cur); cur = []
        continue
    k = norm(w["w"])
    cur.append(w)
    if k in BIG or k in SCRIPT or len(cur) >= 2 or w["w"][-1] in ".,?!:" or len(w["w"]) > 11:
        chunks.append(cur); cur = []
if cur: chunks.append(cur)
# merge flash-length chunks (< 0.32 s on screen) into the next one, so every caption is readable
merged = []
for ch in chunks:
    if merged:
        prev = merged[-1]
        on = ch[0]["s"] - prev[0]["s"]
        pk = norm(prev[-1]["w"])
        if on < 0.32 and prev[-1]["w"][-1] not in ".?!:" and len(prev) + len(ch) <= 3 and pk not in BIG and pk not in SCRIPT and ch[0]["s"] - prev[-1]["e"] < 0.25:
            merged[-1] = prev + ch; continue
    merged.append(ch)
chunks = merged
hide_starts = sorted(x for x, y in hide_caps)
cap_html = []
for ci, ch in enumerate(chunks):
    a = ch[0]["s"] - 0.04
    nxt = chunks[ci + 1][0]["s"] - 0.04 if ci + 1 < len(chunks) else ch[-1]["e"] + 0.5
    b = min(nxt, ch[-1]["e"] + 0.45)
    b = min([b] + [h - 0.02 for h in hide_starts if h > a])   # never run into a full-screen text card
    b = max(b, a + 0.18)
    if hidden(a):
        continue
    clean = lambda x: x.lower().strip(".,?!:;")
    last = norm(ch[-1]["w"])
    if last in BIG or last in SCRIPT:
        small = " ".join(clean(w["w"]) for w in ch[:-1])
        cls = "cbig" if last in BIG else "cscript"
        inner = (f'<div class="csm">{small}</div>' if small else "") + f'<div class="{cls}">{clean(ch[-1]["w"])}</div>'
    else:
        inner = f'<div class="cpl">{" ".join(clean(w["w"]) for w in ch)}</div>'
    low = any(a < y - 0.3 and b > x + 0.05 for x, y in low_caps)
    cap_html.append(f'<div id="c{ci}" class="cap{" low" if low else ""}">{inner}</div>')
    st(f"#c{ci}", {"autoAlpha": 0}, 0); based.add(f"#c{ci}")
    tl.append(f'tl.fromTo("#c{ci}", {{autoAlpha: 0, y: 10, filter: "blur(6px)"}}, {{autoAlpha: 1, y: 0, filter: "blur(0px)", duration: 0.14, ease: "power2.out", immediateRender: false}}, {a:.3f});')
    # explicit hide AFTER the fade-in has finished (a bare set inside the fade gets overridden)
    tl.append(f'tl.fromTo("#c{ci}", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.01, immediateRender: false}}, {max(b, a + 0.15):.3f});')

# ---------------------------------------------------------------- light leaks (the turns only)
for i, at in enumerate(sorted(set(round(x, 2) for x in leaks))):
    tw("#leak", {"autoAlpha": 0, "x": -300}, {"autoAlpha": 0.95, "x": 0, "duration": 0.22, "ease": "power2.out"}, at) if i == 0 else \
        tl.append(f'tl.fromTo("#leak", {{autoAlpha: 0, x: {-300 if i % 2 else 300}}}, {{autoAlpha: 0.95, x: 0, duration: 0.22, ease: "power2.out", immediateRender: false}}, {at:.3f});')
    tl.append(f'tl.fromTo("#leak", {{autoAlpha: 0.95}}, {{autoAlpha: 0, duration: 0.38, ease: "power2.in", immediateRender: false}}, {at + 0.24:.3f});')
    sound("whoosh-1", at - 0.05, 0.09)

# ---------------------------------------------------------------- dust + grain painter (seeded per frame)
tl.append(f"""(() => {{ const cv = document.getElementById("dust"), cx = cv.getContext("2d"), gr = document.getElementById("grain"); const P = {{u: 0}};
  const rnd = (s) => {{ let x = Math.sin(s * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }};
  const paint = () => {{ const f = Math.floor(tl.time() * {FPS}); cx.clearRect(0, 0, 1080, 1920);
    const n = 3 + Math.floor(rnd(f) * 7);
    for (let i = 0; i < n; i++) {{ const x = rnd(f * 13 + i) * 1080, y = rnd(f * 29 + i * 7) * 1920, r = 1 + rnd(f * 3 + i) * 3.2;
      cx.fillStyle = "rgba(235,228,214," + (0.35 + rnd(f + i * 5) * 0.5).toFixed(2) + ")"; cx.beginPath();
      if (rnd(f * 7 + i) > 0.82) {{ cx.lineWidth = 1.2; cx.strokeStyle = cx.fillStyle; cx.moveTo(x, y); cx.quadraticCurveTo(x + 14, y + 8, x + 6 + rnd(i) * 30, y + 26); cx.stroke(); }}
      else {{ cx.arc(x, y, r, 0, Math.PI * 2); cx.fill(); }} }}
    if (rnd(Math.floor(f / 3) * 91) > 0.9) {{ const sx = rnd(Math.floor(f / 3)) * 1080; cx.fillStyle = "rgba(240,235,220,.18)"; cx.fillRect(sx, 0, 1.4, 1920); }}
    gr.style.backgroundPosition = Math.floor(rnd(f) * 480) + "px " + Math.floor(rnd(f + 9) * 480) + "px"; }};
  tl.fromTo(P, {{u: 0}}, {{u: 1, duration: {TOTAL}, ease: "none", onUpdate: paint, immediateRender: false}}, 0); }})();""")


# ---------------------------------------------------------------- audio: a warm bed + light SFX
def need(src, dst):
    """copy a library file into the project (sound effects and music are fetched into the skill's library at setup)"""
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(S, src), dst)


need("library/music/chillax.mp3", "assets/music/bed.mp3")
bed = """<audio id="bed" src="assets/music/bed.mp3" data-start="0" data-duration="%s" data-media-start="0" data-track-index="20" data-automation='%s'></audio>""" % (
    TOTAL, json.dumps({"version": 1, "lanes": [{"target": "volume", "points": [{"t": 0, "v": 0}, {"t": 0.6, "v": 0.16}, {"t": SPEECH_END, "v": 0.16}, {"t": SPEECH_END + 0.4, "v": 0.32}, {"t": TOTAL - 0.8, "v": 0.32}, {"t": TOTAL, "v": 0}]}]}))
sfx_html, lanes = [], []                                # one track per sound at a time: the first free lane
for i, (sid, at, vol) in enumerate(sorted(sfx, key=lambda s: s[1])):
    need(f"library/sfx/{sid}.wav", f"assets/sfx/{sid}.wav")
    dur = min(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"assets/sfx/{sid}.wav"],
                                   capture_output=True, text=True).stdout), 1.2, TOTAL - at)
    k = next((j for j, e in enumerate(lanes) if e <= at), None)
    if k is None:
        k = len(lanes); lanes.append(0.0)
    lanes[k] = at + dur
    sfx_html.append(f'<audio id="sx{i}" src="assets/sfx/{sid}.wav" data-start="{at:.3f}" data-duration="{dur:.3f}" data-track-index="{30 + k}" data-volume="{vol}"></audio>')
if not os.path.exists("assets/grain.png"):                # a tileable monochrome noise tile for the grain layer
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x808080:s=480x480,format=gray,noise=alls=90:allf=u",
                    "-frames:v", "1", "assets/grain.png"], check=True)

fonts_css = open("assets/fonts/fonts-local.css").read().replace("url(", "url(assets/fonts/")
html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{fonts_css}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; font-family: "Inter Tight"; }}
#zoom, #drift {{ position: absolute; inset: 0; transform-origin: 50% 36%; }}
.fill {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
.scene {{ position: absolute; inset: 0; opacity: 0; overflow: hidden; }}
.scene.kraft {{ background-image: radial-gradient(ellipse at 30% 20%, rgba(255,240,210,.25), rgba(0,0,0,0) 60%), radial-gradient(ellipse at 80% 90%, rgba(60,30,10,.35), rgba(0,0,0,0) 55%) !important; }}
.stack {{ position: absolute; left: 70px; right: 70px; text-align: center; color: #EFE9DD; }}
.sm {{ font-weight: 600; font-size: 50px; letter-spacing: -1.5px; line-height: 1.12; opacity: .92; }}
.bg {{ font-weight: 800; font-size: 104px; letter-spacing: -5px; line-height: 1.0; }}
.xl {{ font-size: 132px; }}
.script {{ font-family: Caveat; font-weight: 700; font-size: 120px; letter-spacing: 0; color: #F4E7C6; line-height: 1.05; }}
.ink {{ color: #2A1E12; }} .script.ink {{ color: #2A1E12; }}
.hand {{ font-family: Caveat; font-weight: 700; color: #2B2B2B; }}
.ticket {{ position: absolute; left: 150px; top: 690px; width: 780px; height: 330px; display: flex; background: #F3EBDD; border-radius: 10px;
          box-shadow: 0 24px 50px rgba(0,0,0,.35); color: #2A2A2A; overflow: hidden;
          -webkit-mask: radial-gradient(circle 16px at 0 50%, transparent 15px, #000 16px) left / 51% 100% no-repeat, radial-gradient(circle 16px at 100% 50%, transparent 15px, #000 16px) right / 51% 100% no-repeat; }}
.tk-l {{ flex: 1; padding: 40px 50px; display: flex; flex-direction: column; gap: 14px; border-right: 4px dashed rgba(0,0,0,.25); }}
.tk-l b {{ font-size: 72px; font-weight: 800; letter-spacing: -2.5px; }}
.tk-sm {{ font-size: 30px; font-weight: 600; letter-spacing: 3px; text-transform: uppercase; color: #6B5B45; }}
.tk-r {{ width: 190px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; font-size: 28px; letter-spacing: 3px; text-transform: uppercase; color: #6B5B45; }}
.tk-r b {{ font-size: 96px; color: #2A2A2A; letter-spacing: -3px; }}
.stamp {{ position: absolute; left: 330px; top: 214px; padding: 4px 24px; border: 7px solid #C0392B; border-radius: 12px; color: #C0392B; font-weight: 800;
         font-size: 58px; letter-spacing: 5px; text-transform: uppercase; mix-blend-mode: multiply; opacity: 0; }}
.rcwrap {{ position: absolute; left: 190px; top: 170px; width: 700px; height: 1250px; }}
.slot {{ position: absolute; left: -30px; right: -30px; top: 950px; height: 52px; border-radius: 26px; background: #05070B; box-shadow: inset 0 6px 12px rgba(255,255,255,.08); }}
.rcclip {{ position: absolute; left: 0; right: 0; top: -40px; height: 1016px; overflow: hidden; display: flex; flex-direction: column; justify-content: flex-end; }}
.receipt {{ background: #FBFAF6; color: #222; padding: 70px 56px 90px; font-family: "Inter Tight"; font-size: 38px; box-shadow: 0 20px 40px rgba(0,0,0,.35);
           -webkit-mask: linear-gradient(#000, #000) top / 100% calc(100% - 22px) no-repeat, conic-gradient(from -45deg at 50% 100%, #000 90deg, transparent 0) bottom / 44px 22px repeat-x; }}
.rc-h {{ text-align: center; font-size: 72px; font-weight: 800; letter-spacing: 10px; text-transform: uppercase; }}
.rc-s {{ text-align: center; color: #777; margin: 8px 0 40px; letter-spacing: 2px; }}
.rc-row {{ display: flex; justify-content: space-between; padding: 14px 0; border-bottom: 3px dotted #CCC; }}
.rc-row.tot {{ font-weight: 800; font-size: 46px; border-bottom: 0; margin-top: 20px; }}
.rc-addr {{ position: relative; margin-top: 60px; text-align: center; color: #555; letter-spacing: 2px; }}
.rc-thx {{ margin-top: 40px; text-align: center; color: #888; font-size: 32px; letter-spacing: 4px; text-transform: uppercase; }}
svg.mark {{ position: absolute; left: -10px; right: -10px; top: -42px; width: calc(100% + 20px); height: 130px; overflow: visible; }}
svg.mark ellipse {{ fill: none; stroke: #E2462F; stroke-width: 9; stroke-linecap: round; stroke-dasharray: 1 1; stroke-dashoffset: 1; }}
.hand.note {{ position: absolute; left: 330px; top: 1010px; font-size: 76px; color: #F4E7C6; transform: rotate(-6deg); white-space: nowrap; }}
.nb {{ position: absolute; left: 70px; top: 470px; width: 940px; height: 760px; display: flex; perspective: 2200px; }}
.pg {{ position: relative; flex: 1; background: #F5F0E4; box-shadow: 0 20px 45px rgba(0,0,0,.35); }}
.pg.l {{ border-radius: 14px 0 0 14px; background: linear-gradient(90deg, #F5F0E4 88%, #E2DACA); }}
.pg.r {{ border-radius: 0 14px 14px 0; transform-origin: 0 50%; background: linear-gradient(90deg, #E2DACA, #F5F0E4 12%); padding: 90px 40px 0; box-sizing: border-box; }}
.pg.r i {{ display: block; height: 0; border-bottom: 3px solid rgba(80,110,160,.25); margin-bottom: 78px; }}
.pg.l img {{ position: absolute; left: 50px; top: 60px; width: 370px; height: 470px; object-fit: contain; mix-blend-mode: multiply; transform: rotate(-8deg); }}
.pg.l .hand {{ position: absolute; left: 50px; bottom: 60px; font-size: 64px; transform: rotate(-3deg); }}
.polaroid {{ position: absolute; background: #F5F1E8; padding: 26px 26px 0; box-shadow: 0 30px 60px rgba(0,0,0,.45); }}
.polaroid img {{ display: block; width: 100%; aspect-ratio: 4/5; object-fit: cover; filter: saturate(.9) contrast(1.02); }}
.pcap {{ font-family: Caveat; font-weight: 700; font-size: 64px; color: #2B2B2B; text-align: center; padding: 14px 0 22px; }}
#s9t {{ left: 0; top: 0; transform-origin: 50% 50%; }}
.hand.onticket {{ position: absolute; left: 60px; top: 236px; font-size: 64px; color: #1F3A8A; transform: rotate(-4deg); white-space: nowrap; }}
.flash {{ position: absolute; inset: 0; background: #fff; opacity: 0; }}
.paper {{ position: absolute; }}
.sheet {{ position: absolute; inset: 0; background: #ECE6DA; border-radius: 6px; box-shadow: 0 18px 40px rgba(0,0,0,.35); }}
.sheet.s2 {{ transform: rotate(-6deg) translate(-18px, 10px); background: #E2DBCC; }}
.sheet.s1 {{ transform: rotate(4deg) translate(14px, -6px); background: #E8E1D3; }}
.sheet.top {{ padding: 40px; box-sizing: border-box; }}
.sheet.top img {{ position: absolute; left: 40px; top: 40px; width: calc(100% - 80px); height: calc(100% - 80px); object-fit: cover; }}
.clip-pin {{ position: absolute; right: 70px; top: -26px; width: 38px; height: 92px; border: 6px solid #8C8C8C; border-radius: 20px; }}
.notif {{ position: absolute; left: 60px; right: 60px; top: 150px; background: rgba(245,245,247,.92); border-radius: 44px; padding: 30px 38px; color: #111; box-shadow: 0 20px 50px rgba(0,0,0,.35); opacity: 0; z-index: 56; }}
.nhead {{ font-weight: 600; font-size: 28px; letter-spacing: 1px; color: #6B6B70; display: flex; align-items: center; gap: 14px; }}
.nico {{ font-size: 34px; }} .nnow {{ margin-left: auto; letter-spacing: 0; }}
.nt {{ font-weight: 800; font-size: 56px; margin-top: 10px; letter-spacing: -1px; font-variant-numeric: tabular-nums; }} .nb2 {{ font-size: 34px; color: #3A3A3C; margin-top: 4px; }}
.dialog {{ position: absolute; left: 150px; right: 150px; top: 130px; background: rgba(246,246,248,.96); border-radius: 46px; padding: 46px 40px 0; text-align: center; color: #111; box-shadow: 0 30px 70px rgba(0,0,0,.45); opacity: 0; overflow: hidden; z-index: 56; }}
.dico {{ font-size: 76px; }} .dt {{ font-weight: 800; font-size: 54px; letter-spacing: -1.5px; margin-top: 8px; }} .db {{ font-size: 36px; color: #3A3A3C; margin: 10px 0 34px; }}
.dbtns {{ display: flex; border-top: 2px solid #D1D1D6; margin: 0 -40px; }} .dbtns span {{ flex: 1; padding: 26px 0; font-size: 38px; color: #0A63D8; }} .dbtns span.pri {{ font-weight: 700; border-left: 2px solid #D1D1D6; }}
.cursor {{ position: absolute; left: 300px; top: 470px; font-size: 76px; color: #fff; transform: rotate(-110deg); opacity: 0; z-index: 70; filter: drop-shadow(0 4px 8px rgba(0,0,0,.6)); }}
.sticker {{ position: absolute; opacity: 0; line-height: 1; filter: drop-shadow(0 10px 20px rgba(0,0,0,.45)); z-index: 60; }}
.sticky {{ position: absolute; left: 640px; top: 170px; width: 360px; height: 340px; background: #FFE58F; box-shadow: 0 18px 30px rgba(0,0,0,.35); opacity: 0; z-index: 56;
          display: flex; align-items: center; justify-content: center; text-align: center; }}
.sticky .hand {{ font-size: 72px; line-height: 1; padding: 20px; }}
#leak {{ position: absolute; inset: -200px; opacity: 0; mix-blend-mode: screen; pointer-events: none;
  background: radial-gradient(ellipse 60% 45% at 18% 40%, rgba(255,90,30,.95), rgba(255,90,30,0) 70%), radial-gradient(ellipse 50% 60% at 75% 60%, rgba(255,190,60,.9), rgba(255,190,60,0) 70%), radial-gradient(ellipse 40% 30% at 50% 15%, rgba(255,240,200,.8), rgba(255,240,200,0) 70%); filter: blur(30px); }}
.cap {{ position: absolute; left: 60px; right: 60px; top: 1150px; text-align: center; color: #FFFDF8; opacity: 0;
  text-shadow: 0 2px 4px rgba(0,0,0,.55), 0 0 22px rgba(0,0,0,.45); }}
.cap.low {{ top: 1395px; }}
.cpl {{ font-weight: 700; font-size: 62px; letter-spacing: -2px; line-height: 1.05; }}
.csm {{ font-weight: 600; font-size: 46px; letter-spacing: -1.4px; line-height: 1.05; opacity: .95; }}
.cbig {{ font-weight: 800; font-size: 96px; letter-spacing: -4.5px; line-height: 1.0; }}
.cscript {{ font-family: Caveat; font-weight: 700; font-size: 104px; line-height: 0.95; color: #FFF6DF; }}
#dust {{ position: absolute; inset: 0; pointer-events: none; mix-blend-mode: screen; }}
#grain {{ position: absolute; inset: 0; background: url(assets/grain.png); background-size: 480px; opacity: .085; mix-blend-mode: overlay; pointer-events: none; }}
#vig {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,.42) 100%); pointer-events: none; }}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{TOTAL}" data-fps="{FPS}">
 <div id="zoom"><div id="drift">{''.join(c for c in clip_html if c.startswith('<video'))}</div></div>
 {''.join(scenes_html)}
 <div id="leak"></div>
 {''.join(cap_html)}
 <div id="vig"></div><canvas id="dust" width="1080" height="1920"></canvas><div id="grain"></div>
 {''.join(c for c in clip_html if c.startswith('<audio'))}
 {bed}
 {''.join(sfx_html)}
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
{chr(10).join('  ' + l for l in tl)}
  window.__timelines["main"] = tl;
</script>
</body></html>"""
open("index.html", "w").write(html)
print(f"index.html {TOTAL}s: {len(clips)} clips, {len(chunks)} caption chunks, {len(set(round(x, 2) for x in leaks))} leaks, {len(sfx)} sfx, {len(tl)} timeline lines")
