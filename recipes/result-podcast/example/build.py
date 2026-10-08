#!/usr/bin/env python3
"""«Почему миллениалы ностальгируют» -> index.html (HyperFrames 1080x1920).

Style reference: @loompixual "RESULT" edit (DZr7QYDTwQG). One/two-word centred
captions in a tight sans, two-tier emphasis (small line + big bold word),
handwritten key words, film-burn light leaks, navy dust cards, polaroids,
a paper stack whose pictures swap stop-motion, framed B-roll, dust + grain.

Inputs: build/takes.json (takes.py: best take per line, pauses removed),
build/rough.words.json (word times on the rough cut = this edit minus the hold).
"""
import json, math, random, re

FPS = 30
T = json.load(open("build/takes.json"))
HOLD_AFTER_LINE, HOLD = 3, 0.0           # no hold: the 2nd take of line 4 has «контентом»

# ---------------------------------------------------------------- timeline of parts
clips, t = [], 0.0
for li, tk in enumerate(T):
    for a, b in tk["parts"]:
        clips.append({"a": a, "b": b, "s": round(t, 3), "line": li})
        t += b - a
    if li == HOLD_AFTER_LINE:
        HOLD_AT = round(t, 3)
        t += HOLD
SPEECH_END = round(t, 3)
OUTRO = 2.2
TOTAL = round(SPEECH_END + OUTRO, 3)

# ---------------------------------------------------------------- words (edit time)
raw = json.load(open("build/rough.words.json"))
ws = [w for s in raw["segments"] for w in s["words"]]
FIX = {"Майл": "Mail", ".ру,": ".ru,", "Инстаграм,": "Instagram,", "ТикТок.": "TikTok."}
words = []
for w in ws:
    txt = w["word"].strip()
    if txt.startswith("Продолжение") or txt.startswith("следует"):
        continue
    txt = FIX.get(txt, txt)
    s, e = w["start"], w["end"]
    if s >= HOLD_AT - 0.05:
        s, e = s + HOLD, e + HOLD
    # glue fragments whisper splits off (-то, -Fi, .ru)
    if words and (txt.startswith("-") or txt.startswith(".")):
        words[-1]["w"] += txt; words[-1]["e"] = e; continue
    words.append({"w": txt, "s": round(s, 3), "e": round(e, 3)})
words[-1]["e"] = min(words[-1]["e"], SPEECH_END)


def norm(x):
    return re.sub(r"[^a-zа-яё0-9]", "", x.lower())


def W(text, n=1, end=False):
    k = 0
    for w in words:
        if norm(w["w"]) == norm(text):
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


def show(sel, a, b, fin=None, fout=None):
    """visible from a to b with a soft fade (explicit values, seek-safe)"""
    fin = fin or {"autoAlpha": 0}
    tw(sel, fin, {**{k: (1 if k == "autoAlpha" else 0 if k in ("x", "y") else 1 if k == "scale" else "blur(0px)" if k == "filter" else 0) for k in fin}, "duration": 0.28, "ease": "power3.out"}, a)
    tw(sel, {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.22, "ease": "power2.in"}, b - 0.22)


# ---------------------------------------------------------------- speaker clips
# Picture: each clip overlaps the previous by XF and dissolves in (a "morph cut"), so the
# small head-position jumps between takes read as a soft transition. Sound stays hard-cut.
XF = 0.2
clip_html = []
for i, c in enumerate(clips):
    d = round(c["b"] - c["a"], 3)
    pre = XF if i else 0.0
    clip_html.append(f'<video id="v{i}" class="clip fill" style="z-index:{i + 1}" src="assets/talk.mp4" data-start="{round(c["s"] - pre, 3)}" data-duration="{round(d + pre, 3)}" data-media-start="{round(c["a"] - pre, 3)}" data-track-index="{i % 2}" muted playsinline></video>')
    clip_html.append(f'<audio id="a{i}" src="assets/talk.mp4" data-start="{c["s"]}" data-duration="{d}" data-media-start="{c["a"]}" data-track-index="{10 + i % 2}" data-volume="1"></audio>')
    if i:
        tw(f"#v{i}", {"opacity": 0}, {"opacity": 1, "duration": XF, "ease": "none"}, c["s"] - pre)

# ---------------------------------------------------------------- scenes
scenes_html, hide_caps, low_caps, yellow_caps = [], [], [], []
NAVY = "#141A26"


def scene(sid, a, b, inner, bg=NAVY, leak=True, caps=True):
    scenes_html.append(f'<div id="{sid}" class="scene" style="background:{bg}">{inner}</div>')
    tw(f"#{sid}", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.12}, a)
    tw(f"#{sid}", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.06}, b - 0.06)
    if leak:
        leaks.append(a - 0.12)
    if not caps:
        hide_caps.append((a, b - 0.32))
    else:
        low_caps.append((a, b))


leaks = []

# S1 navy card: «мы застали мир до того, как всё стало / подпиской, / алгоритмом / или ежемесячным платежом.»
a1, b1 = W("мы") - 0.15, min(W("платежом", end=True) + 0.35, W("над") - 0.08)
scene("s1", a1, b1, f"""
 <div class="stack" style="top:640px">
  <div id="s1l1" class="sm">мы застали мир до того,</div>
  <div id="s1l2" class="sm">как всё стало</div>
  <div id="s1w1" class="bg">подпиской,</div>
  <div id="s1w2" class="bg">алгоритмом</div>
  <div id="s1w3" class="sm" style="margin-top:6px">или ежемесячным</div>
  <div id="s1w4" class="bg">платежом.</div>
 </div>""", caps=False)
for el, key in (("s1l1", "мы"), ("s1l2", "как"), ("s1w1", "подпиской"), ("s1w2", "алгоритмом"), ("s1w3", "или"), ("s1w4", "платежом")):
    tw(f"#{el}", {"autoAlpha": 0, "y": 18, "filter": "blur(8px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.32, "ease": "power3.out"}, W(key) - 0.05)

# S3 polaroid: friends, «на память»
a3, b3 = W("фотографии") - 0.25, W("был", end=True) + 0.15
scene("s3", a3, b3, """
 <div id="s3p" class="polaroid" style="left:190px;top:260px;width:700px;transform:rotate(-3deg)">
  <img src="assets/broll/friends.png"/><div class="pcap">на память ♡</div></div><div id="s3f" class="flash"></div>""")
tw("#s3p", {"y": 140, "rotation": -10, "autoAlpha": 0}, {"y": 0, "rotation": -3, "autoAlpha": 1, "duration": 0.4, "ease": "power3.out"}, a3)
tw("#s3f", {"autoAlpha": 0}, {"autoAlpha": 0.9, "duration": 0.05}, a3 + 0.5)
tw("#s3f", {"autoAlpha": 0.9}, {"autoAlpha": 0, "duration": 0.3}, a3 + 0.56)

# S4 framed B-roll: CRT, «в интернет заходили»
a4, b4 = W("интернет") - 0.45, W("нём", end=True) + 0.2
scene("s4", a4, b4, """<div id="s4f" class="frame" style="left:110px;top:300px;width:860px;height:1000px"><img src="assets/broll/crt.png"/></div>""")
tw("#s4f img", {"scale": 1.0}, {"scale": 1.1, "duration": b4 - a4, "ease": "none"}, a4)

# S5 paper stack: pictures swap stop-motion, «в нескольких разных версиях мира»
a5, b5 = W("пожить") - 0.1, W("мира", end=True) + 0.3
stack_imgs = ["friends", "yard", "crt", "map", "copybook"]
pics = "".join(f'<img id="s5i{i}" src="assets/broll/{n}.png"/>' for i, n in enumerate(stack_imgs))
scene("s5", a5, b5, f"""
 <div class="stack" style="top:230px"><div id="s5h1" class="sm">в нескольких</div><div id="s5h2" class="bg">разных версиях мира</div></div>
 <div id="s5s" class="paper" style="left:240px;top:560px;width:600px;height:700px"><div class="sheet s2"></div><div class="sheet s1"></div><div class="sheet top">{pics}<div class="clip-pin"></div></div></div>""", caps=False)
tw("#s5h1", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.2}, W("нескольких") - 0.05)
tw("#s5h2", {"autoAlpha": 0, "y": 14}, {"autoAlpha": 1, "y": 0, "duration": 0.3}, W("разных") - 0.05)
tw("#s5s", {"y": 120, "rotation": 8, "autoAlpha": 0}, {"y": 0, "rotation": -2, "autoAlpha": 1, "duration": 0.45, "ease": "back.out(1.4)"}, a5)
step = (b5 - a5 - 0.3) / len(stack_imgs)
for i in range(len(stack_imgs)):
    st(f"#s5i{i}", {"autoAlpha": 0}, 0); based.add(f"#s5i{i}")
    st(f"#s5i{i}", {"autoAlpha": 1}, a5 + i * step)
    if i < len(stack_imgs) - 1:
        st(f"#s5i{i}", {"autoAlpha": 0}, a5 + (i + 1) * step)
    st("#s5s", {"rotation": [-2, 1.5, -1, 2, -2.5][i]}, a5 + i * step)

# S6 yellow-washed polaroid: courtyard at dusk, «пойти гулять … когда стемнеет»
a6, b6 = W("гулять") - 0.5, W("стемнеет", end=True) + 0.2
scene("s6", a6, b6, """
 <div id="s6p" class="polaroid" style="left:170px;top:240px;width:740px;transform:rotate(2deg)">
  <img src="assets/broll/yard.png"/><div class="pcap">когда стемнеет</div></div><div class="ywash"></div>""", bg="#F2C14E")
yellow_caps.append((a6, b6))
tw("#s6p", {"scale": 1.12, "autoAlpha": 0}, {"scale": 1, "autoAlpha": 1, "duration": 0.5, "ease": "power3.out"}, a6)

# S7 list: почта / ВК / Mail.ru / Instagram / TikTok
a7, b7 = W("электронной") - 0.2, W("tiktok", end=True) + 0.35
items = [("эл. почта", "электронной"), ("ВК", "вк"), ("Mail.ru", "mailru"), ("Instagram", "instagram"), ("TikTok", "tiktok")]
scene("s7", a7, b7, '<div class="list">' + "".join(f'<div id="s7i{i}" class="{"bg" if i == 4 else "md"}">{t}</div>' for i, (t, k) in enumerate(items)) + "</div>", caps=False)
for i, (txt, key) in enumerate(items):
    tw(f"#s7i{i}", {"autoAlpha": 0, "x": -40, "filter": "blur(6px)"}, {"autoAlpha": 1, "x": 0, "filter": "blur(0px)", "duration": 0.25, "ease": "power3.out"}, W(key) - 0.05)
    if i < 4:
        tw(f"#s7i{i}", {"opacity": 1}, {"opacity": 0.35, "duration": 0.2}, W(items[i + 1][1]) - 0.05)

# S8 framed B-roll: fridge with Wi-Fi
a8, b8 = W("холодильнику") - 0.3, W("wifi", end=True) + 0.35
scene("s8", a8, b8, """<div id="s8f" class="frame" style="left:150px;top:290px;width:780px;height:975px"><img src="assets/broll/fridge.png"/></div>""")
tw("#s8f img", {"scale": 1.12}, {"scale": 1.0, "duration": b8 - a8, "ease": "none"}, a8)

# S9 paper card with phone stickers: домашний телефон -> раскладушка -> смартфон
a9, b9 = W("домашний") - 0.25, W("смартфон", end=True) + 0.4
scene("s9", a9, b9, """
 <div id="s9s" class="paper" style="left:190px;top:420px;width:700px;height:760px"><div class="sheet s2"></div><div class="sheet s1"></div>
  <div class="sheet top white"><img id="s9i0" src="assets/broll/phone_home.png"/><img id="s9i1" src="assets/broll/phone_flip.png"/><img id="s9i2" src="assets/broll/phone_smart.png"/><div class="clip-pin"></div></div></div>""")
tw("#s9s", {"y": 140, "rotation": -9, "autoAlpha": 0}, {"y": 0, "rotation": 2, "autoAlpha": 1, "duration": 0.45, "ease": "back.out(1.4)"}, a9)
for i, key in enumerate([("домашний", 1), ("раскладушка", 1), ("смартфон", 1)]):
    st(f"#s9i{i}", {"autoAlpha": 0}, 0); based.add(f"#s9i{i}")
    st(f"#s9i{i}", {"autoAlpha": 1}, W(*key) - 0.05 if i else a9)
    if i < 2:
        st(f"#s9i{i}", {"autoAlpha": 0}, W(["раскладушка", "смартфон"][i]) - 0.05)
    st("#s9s", {"rotation": [2, -2.5, 1.5][i]}, (W(*key) - 0.05) if i else a9 + 0.45)

# S10 screen-time notification over the speaker
a10 = W("сколько") - 0.1
scenes_html.append("""<div id="s10" class="notif"><div class="nhead"><span class="nico">⌛</span>ЭКРАННОЕ ВРЕМЯ<span class="nnow">сейчас</span></div>
 <div class="nt">В среднем 7 ч 12 мин в день</div><div class="nb">На 18% больше, чем на прошлой неделе</div></div>""")
tw("#s10", {"y": -260, "autoAlpha": 0}, {"y": 0, "autoAlpha": 1, "duration": 0.45, "ease": "back.out(1.6)"}, a10)
tw("#s10", {"y": 0, "autoAlpha": 1}, {"y": -260, "autoAlpha": 0, "duration": 0.35, "ease": "power2.in"}, W("нём", 2, end=True) + 0.6)

# S11 framed B-roll: copybook, «красиво писать от руки»
a11, b11 = W("красиво") - 0.35, W("руки", end=True) + 0.25
scene("s11", a11, b11, """<div id="s11f" class="frame" style="left:130px;top:300px;width:820px;height:1025px"><img src="assets/broll/copybook.png"/></div>""")
tw("#s11f img", {"scale": 1.0, "y": 0}, {"scale": 1.08, "y": -20, "duration": b11 - a11, "ease": "none"}, a11)

# S12 framed B-roll: printed map + hand-drawn wrong turn
a12, b12 = W("таксисты") - 0.3, W("разбираться", 2, end=True) + 0.2
scene("s12", a12, b12, """<div id="s12f" class="frame" style="left:110px;top:270px;width:860px;height:1075px"><img src="assets/broll/map.png"/>
 <svg viewBox="0 0 860 1075" class="ink"><path id="s12a" d="M200,900 C260,760 300,640 420,560 C520,500 560,470 600,380" pathLength="1"/>
 <path id="s12b" d="M600,380 C640,330 700,330 760,300" pathLength="1"/><path id="s12h" d="M735,282 L770,298 L742,328" pathLength="1"/>
 <path id="s12x" d="M560,250 L660,350 M660,250 L560,350" pathLength="1" class="red"/></svg></div>""")
for el, at, dur in (("s12a", W("маршрут") - 0.1, 1.2), ("s12b", W("поворот") - 0.1, 0.35), ("s12h", W("поворот") + 0.25, 0.15), ("s12x", W("всё", 3) - 0.05, 0.3)):
    tw(f"#{el}", {"strokeDashoffset": 1}, {"strokeDashoffset": 0, "duration": dur, "ease": "power1.inOut"}, at)

# S13 update dialog over the speaker
a13 = W("новая") - 0.2
scenes_html.append("""<div id="s13" class="dialog"><div class="dico">✨</div><div class="dt">У нас новая функция</div><div class="db">Мы всё переделали. Опять.</div>
 <div class="dbtns"><span>Позже</span><span class="pri">Обновить</span></div></div>""")
tw("#s13", {"scale": 0.7, "autoAlpha": 0}, {"scale": 1, "autoAlpha": 1, "duration": 0.35, "ease": "back.out(1.8)"}, a13)
tw("#s13", {"scale": 1, "autoAlpha": 1}, {"scale": 0.9, "autoAlpha": 0, "duration": 0.25}, W("слышится", end=True) + 0.5)

# S14 final navy card
a14 = W("ностальгируем") - 0.35
scene("s14", a14, TOTAL + 0.2, """
 <div class="stack" style="top:600px">
  <div id="f1" class="sm">мы ностальгируем не потому,</div><div id="f2" class="bg">что состарились,</div>
  <div id="f3" class="sm" style="margin-top:46px">а потому, что каждые несколько лет</div><div id="f4" class="sm">нам приходится заново</div>
  <div id="f5" class="script xl">учиться жить.</div></div>""", caps=False)
for el, key in (("f1", "ностальгируем"), ("f2", "состарились"), ("f3", "каждые"), ("f4", "приходится"), ("f5", "учиться")):
    tw(f"#{el}", {"autoAlpha": 0, "y": 18, "filter": "blur(8px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.35, "ease": "power3.out"}, W(key) - 0.08)
tw("#f1", {"opacity": 1}, {"opacity": 0.4, "duration": 0.3}, W("каждые") - 0.1)
tw("#f2", {"opacity": 1}, {"opacity": 0.4, "duration": 0.3}, W("каждые") - 0.1)

# ---------------------------------------------------------------- comic punch-ins (only three) + fun overlays
for word, back, z in (("конечно", W("мы") - 0.1, 1.2), ("иначе", W("помним") - 0.35, 1.16), ("надо", W("помню") - 0.08, 1.16)):
    tw("#zoom", {"scale": 1}, {"scale": z, "duration": 0.12, "ease": "power3.out"}, W(word) - 0.04)
    tw("#zoom", {"scale": z}, {"scale": 1, "duration": 0.01}, back)


def sticker(sid, emoji, a, b, x=700, y=430, size=170, rot=12):
    scenes_html.append(f'<div id="{sid}" class="sticker" style="left:{x}px;top:{y}px;font-size:{size}px">{emoji}</div>')
    tw(f"#{sid}", {"autoAlpha": 0, "scale": 0.3, "rotation": -rot}, {"autoAlpha": 1, "scale": 1, "rotation": rot, "duration": 0.35, "ease": "back.out(2.6)"}, a)
    tw(f"#{sid}", {"autoAlpha": 1, "scale": 1}, {"autoAlpha": 0, "scale": 0.6, "duration": 0.18, "ease": "power2.in"}, b - 0.18)


sticker("st1", "🙄", W("конечно") - 0.02, W("мы") - 0.12, x=690, y=360)
sticker("st2", "🤷", W("иначе") - 0.02, W("помним") - 0.3, x=660, y=380, rot=-8)
sticker("st3", "🙃", W("надо") - 0.02, W("помню") - 0.1, x=690, y=380)

# phone-camera REC frame on «контентом»
ra, rb = W("контентом") - 0.55, W("контентом", end=True) + 0.55
scenes_html.append(f"""<div id="rec" class="rec"><div class="corner tl"></div><div class="corner tr"></div><div class="corner bl"></div><div class="corner br"></div>
 <div class="rectag"><span class="dot"></span>REC 00:{int(ra):02d}</div><div class="grid"></div></div>""")
tw("#rec", {"autoAlpha": 0, "scale": 1.08}, {"autoAlpha": 1, "scale": 1, "duration": 0.22, "ease": "power3.out"}, ra)
tw("#rec", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.2}, rb - 0.2)
tl.append(f'tl.fromTo("#rec .dot", {{opacity: 1}}, {{opacity: 0.15, duration: 0.3, repeat: {int((rb - ra) / 0.3)}, yoyo: true, ease: "steps(1)", immediateRender: false}}, {ra:.3f});')

# fridge: «подключение к Wi-Fi…» pill
wa = W("нужен") - 0.15
scenes_html.append('<div id="wifi" class="pill-ui"><span class="spin"></span>Подключение к Wi‑Fi…</div>')
tw("#wifi", {"autoAlpha": 0, "y": -30}, {"autoAlpha": 1, "y": 0, "duration": 0.3, "ease": "back.out(2)"}, wa)
tw("#wifi", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.18}, b8 - 0.2)
tl.append(f'tl.fromTo("#wifi .spin", {{rotation: 0}}, {{rotation: 720, duration: {b8 - wa:.2f}, ease: "none", immediateRender: false}}, {wa:.3f});')

# «трубку не хотим поднимать»: incoming call, finger taps decline
ca, cb = W("трубку") - 0.35, W("поднимать", end=True) + 0.7
scenes_html.append("""<div id="call" class="call"><div class="cwho">Неизвестный номер</div><div class="csub">мобильный · входящий вызов…</div>
 <div class="cbtns"><div id="decl" class="cbtn red">✕</div><div class="cbtn green">✆</div></div><div id="finger" class="finger">👆</div></div>""")
tw("#call", {"autoAlpha": 0, "y": -80}, {"autoAlpha": 1, "y": 0, "duration": 0.35, "ease": "back.out(1.8)"}, ca)
tl.append(f'tl.fromTo("#call", {{x: 0}}, {{x: 10, duration: 0.06, repeat: 7, yoyo: true, ease: "none", immediateRender: false}}, {ca + 0.35:.3f});')
tw("#finger", {"x": 420, "y": -40, "autoAlpha": 0}, {"x": 0, "y": 0, "autoAlpha": 1, "duration": 0.45, "ease": "power2.out"}, W("поднимать") - 0.45)
tw("#decl", {"scale": 1}, {"scale": 0.82, "duration": 0.08, "yoyo": True, "repeat": 1}, W("поднимать") + 0.02)
tw("#call", {"autoAlpha": 1, "y": 0}, {"autoAlpha": 0, "y": -120, "duration": 0.3, "ease": "power2.in"}, cb - 0.3)

# «объяснять другим»: the family chat
ka, kb = W("объяснять") - 0.35, W("другим", end=True) + 1.0
scenes_html.append("""<div id="chat" class="chat"><div class="chead">Мама ❤️</div>
 <div id="m1" class="msg">Сын, как отправить фото?</div><div id="m2" class="msg">А где эта кнопка?? 🙈</div></div>""")
tw("#chat", {"autoAlpha": 0, "y": -60}, {"autoAlpha": 1, "y": 0, "duration": 0.3, "ease": "back.out(1.6)"}, ka)
for i, at in enumerate((ka + 0.15, ka + 0.6)):
    tw(f"#m{i + 1}", {"autoAlpha": 0, "scale": 0.6}, {"autoAlpha": 1, "scale": 1, "duration": 0.25, "ease": "back.out(2.4)"}, at)
tw("#chat", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.2}, min(kb, W("ностальгируем") - 0.4) - 0.2)

# update dialog: a cursor clicks «Позже»
scenes_html.append('<div id="cur" class="cursor">➤</div>')
tw("#cur", {"x": 300, "y": 260, "autoAlpha": 0}, {"x": 0, "y": 0, "autoAlpha": 1, "duration": 0.5, "ease": "power2.out"}, W("слышится") - 0.5)
tw("#cur", {"scale": 1}, {"scale": 0.8, "duration": 0.08, "yoyo": True, "repeat": 1}, W("слышится") + 0.05)
tw("#cur", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.2}, W("слышится", end=True) + 0.5)

# hook light leak on «Конечно»
leaks.append(W("конечно") - 0.1)

# ---------------------------------------------------------------- captions
BIG = {"ностальгируют", "прошлому", "доказательство", "холодильнику", "номера", "обновлений", "функция", "разбираться",
       "фотографии", "поднимать", "друзьями", "помним"}
SCRIPT = {"конечно", "иначе", "надо", "ладно", "трубку", "другим", "вопросы"}
hidden = lambda t: any(a - 0.05 <= t < b for a, b in hide_caps)
chunks, cur = [], []
for w in words:
    if hidden(w["s"]):
        if cur: chunks.append(cur); cur = []
        continue
    k = norm(w["w"])
    cur.append(w)
    if k in BIG or k in SCRIPT or len(cur) >= 2 or w["w"][-1] in ".,?!:»" or len(w["w"]) > 11:
        chunks.append(cur); cur = []
if cur: chunks.append(cur)
# merge flash-length chunks (< 0.32 s on screen) into the next one, so every caption is readable
merged = []
for ch in chunks:
    if merged:
        prev = merged[-1]
        on = ch[0]["s"] - prev[0]["s"]
        pk = norm(prev[-1]["w"])
        if on < 0.32 and prev[-1]["w"][-1] not in ".?!:»" and len(prev) + len(ch) <= 3 and pk not in BIG and pk not in SCRIPT and ch[0]["s"] - prev[-1]["e"] < 0.25:
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
    clean = lambda x: x.lower().strip("«».,?!:;")
    last = norm(ch[-1]["w"])
    if last in BIG or last in SCRIPT:
        small = " ".join(clean(w["w"]) for w in ch[:-1])
        cls = "cbig" if last in BIG else "cscript"
        inner = (f'<div class="csm">{small}</div>' if small else "") + f'<div class="{cls}">{clean(ch[-1]["w"])}</div>'
    else:
        inner = f'<div class="cpl">{" ".join(clean(w["w"]) for w in ch)}</div>'
    low = any(a < y - 0.3 and b > x + 0.05 for x, y in low_caps)
    dark = any(x - 0.05 <= a < y - 0.3 for x, y in yellow_caps)
    cap_html.append(f'<div id="c{ci}" class="cap{" low" if low else ""}{" dark" if dark else ""}">{inner}</div>')
    st(f"#c{ci}", {"autoAlpha": 0}, 0); based.add(f"#c{ci}")
    tl.append(f'tl.fromTo("#c{ci}", {{autoAlpha: 0, y: 10, filter: "blur(6px)"}}, {{autoAlpha: 1, y: 0, filter: "blur(0px)", duration: 0.14, ease: "power2.out", immediateRender: false}}, {a:.3f});')
    # explicit hide AFTER the fade-in has finished (a bare set inside the fade gets overridden)
    tl.append(f'tl.fromTo("#c{ci}", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.01, immediateRender: false}}, {max(b, a + 0.15):.3f});')
# captions sit lower while a card/photo fills the centre
for sid in ("s3", "s4", "s5", "s6", "s8", "s9", "s11", "s12"):
    pass

# ---------------------------------------------------------------- light leaks
for i, at in enumerate(sorted(set(round(x, 2) for x in leaks))):
    tw(f"#leak", {"autoAlpha": 0, "x": -300}, {"autoAlpha": 0.95, "x": 0, "duration": 0.22, "ease": "power2.out"}, at) if i == 0 else \
        tl.append(f'tl.fromTo("#leak", {{autoAlpha: 0, x: {-300 if i % 2 else 300}}}, {{autoAlpha: 0.95, x: 0, duration: 0.22, ease: "power2.out", immediateRender: false}}, {at:.3f});')
    tl.append(f'tl.fromTo("#leak", {{autoAlpha: 0.95}}, {{autoAlpha: 0, duration: 0.38, ease: "power2.in", immediateRender: false}}, {at + 0.24:.3f});')

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

# ---------------------------------------------------------------- audio: music bed + light SFX
bed = """<audio id="bed" src="assets/music/bed.mp3" data-start="0" data-duration="%s" data-media-start="0" data-track-index="20" data-automation='%s'></audio>""" % (
    TOTAL, json.dumps({"version": 1, "lanes": [{"target": "volume", "points": [{"t": 0, "v": 0}, {"t": 0.6, "v": 0.16}, {"t": SPEECH_END, "v": 0.16}, {"t": SPEECH_END + 0.4, "v": 0.32}, {"t": TOTAL - 0.8, "v": 0.32}, {"t": TOTAL, "v": 0}]}]}))
sfx = []
for i, at in enumerate(sorted(set(round(x, 2) for x in leaks))):
    sfx.append(f'<audio id="sx{i}" src="assets/sfx/whoosh-1.wav" data-start="{max(0, at - 0.05):.3f}" data-duration="0.9" data-track-index="{14 + i % 3}" data-volume="0.09"></audio>')
for i, (txt, key) in enumerate(items):
    sfx.append(f'<audio id="sp{i}" src="assets/sfx/pop-1.wav" data-start="{W(key) - 0.05:.3f}" data-duration="0.4" data-track-index="{17 + i % 2}" data-volume="0.08"></audio>')
sfx.append(f'<audio id="sn1" src="assets/sfx/pop-2.wav" data-start="{a10:.3f}" data-duration="0.4" data-track-index="19" data-volume="0.1"></audio>')
sfx.append(f'<audio id="sn2" src="assets/sfx/pop-2.wav" data-start="{a13:.3f}" data-duration="0.4" data-track-index="19" data-volume="0.1"></audio>')

html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{open("assets/fonts/fonts.inc.css").read()}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; font-family: "Inter Tight"; }}
#zoom, #drift {{ position: absolute; inset: 0; transform-origin: 50% 36%; }}
.fill {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
.scene {{ position: absolute; inset: 0; opacity: 0; overflow: hidden; }}
.stack {{ position: absolute; left: 70px; right: 70px; text-align: center; color: #EFE9DD; }}
.sm {{ font-weight: 600; font-size: 50px; letter-spacing: -1.5px; line-height: 1.12; opacity: .92; }}
.md {{ font-weight: 800; font-size: 76px; letter-spacing: -3px; line-height: 1.12; }}
.bg {{ font-weight: 800; font-size: 104px; letter-spacing: -5px; line-height: 1.0; }}
.xl {{ font-size: 132px; }}
.script {{ font-family: Caveat; font-weight: 700; font-size: 120px; letter-spacing: 0; color: #F4E7C6; line-height: 1.05; }}
.list {{ position: absolute; left: 0; right: 0; top: 560px; text-align: center; color: #EFE9DD; }}
.list .md {{ margin: 6px 0; }} .list .bg {{ margin-top: 14px; }}
.polaroid {{ position: absolute; background: #F5F1E8; padding: 26px 26px 0; box-shadow: 0 30px 60px rgba(0,0,0,.45); }}
.polaroid img {{ display: block; width: 100%; aspect-ratio: 4/5; object-fit: cover; filter: saturate(.9) contrast(1.02); }}
.pcap {{ font-family: Caveat; font-weight: 700; font-size: 64px; color: #2B2B2B; text-align: center; padding: 14px 0 22px; }}
.flash {{ position: absolute; inset: 0; background: #fff; opacity: 0; }}
.ywash {{ position: absolute; inset: 0; background: rgba(255,214,90,.28); mix-blend-mode: multiply; pointer-events: none; }}
.frame {{ position: absolute; border-radius: 34px; overflow: hidden; box-shadow: 0 30px 70px rgba(0,0,0,.5); }}
.frame img {{ width: 100%; height: 100%; object-fit: cover; transform-origin: 50% 50%; }}
.paper {{ position: absolute; }}
.sheet {{ position: absolute; inset: 0; background: #ECE6DA; border-radius: 6px; box-shadow: 0 18px 40px rgba(0,0,0,.35); }}
.sheet.s2 {{ transform: rotate(-6deg) translate(-18px, 10px); background: #E2DBCC; }}
.sheet.s1 {{ transform: rotate(4deg) translate(14px, -6px); background: #E8E1D3; }}
.sheet.top {{ padding: 40px; box-sizing: border-box; }}
.sheet.top img {{ position: absolute; left: 40px; top: 40px; width: calc(100% - 80px); height: calc(100% - 80px); object-fit: cover; }}
.sheet.white img {{ object-fit: contain; mix-blend-mode: multiply; }}
.clip-pin {{ position: absolute; right: 70px; top: -26px; width: 38px; height: 92px; border: 6px solid #8C8C8C; border-radius: 20px; }}
svg.ink {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
svg.ink path {{ fill: none; stroke: #F7F3EA; stroke-width: 9; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 1 1; stroke-dashoffset: 1; filter: drop-shadow(0 2px 3px rgba(0,0,0,.6)); }}
svg.ink path.red {{ stroke: #E2462F; stroke-width: 12; }}
.notif {{ position: absolute; left: 60px; right: 60px; top: 150px; background: rgba(245,245,247,.92); border-radius: 44px; padding: 30px 38px; color: #111; box-shadow: 0 20px 50px rgba(0,0,0,.35); opacity: 0; }}
.nhead {{ font-weight: 600; font-size: 28px; letter-spacing: 1px; color: #6B6B70; display: flex; align-items: center; gap: 14px; }}
.nico {{ font-size: 34px; }} .nnow {{ margin-left: auto; letter-spacing: 0; }}
.nt {{ font-weight: 800; font-size: 46px; margin-top: 10px; letter-spacing: -1px; }} .nb {{ font-size: 34px; color: #3A3A3C; margin-top: 4px; }}
.dialog {{ position: absolute; left: 150px; right: 150px; top: 130px; background: rgba(246,246,248,.96); border-radius: 46px; padding: 46px 40px 0; text-align: center; color: #111; box-shadow: 0 30px 70px rgba(0,0,0,.45); opacity: 0; overflow: hidden; }}
.dico {{ font-size: 76px; }} .dt {{ font-weight: 800; font-size: 54px; letter-spacing: -1.5px; margin-top: 8px; }} .db {{ font-size: 36px; color: #3A3A3C; margin: 10px 0 34px; }}
.dbtns {{ display: flex; border-top: 2px solid #D1D1D6; margin: 0 -40px; }} .dbtns span {{ flex: 1; padding: 26px 0; font-size: 38px; color: #0A63D8; }} .dbtns span.pri {{ font-weight: 700; border-left: 2px solid #D1D1D6; }}
.sticker {{ position: absolute; opacity: 0; line-height: 1; filter: drop-shadow(0 10px 20px rgba(0,0,0,.45)); z-index: 60; }}
.rec {{ position: absolute; inset: 70px 50px 260px; opacity: 0; z-index: 55; pointer-events: none; }}
.rec .corner {{ position: absolute; width: 90px; height: 90px; border: 0 solid rgba(255,255,255,.92); }}
.rec .tl {{ left: 0; top: 0; border-top-width: 7px; border-left-width: 7px; }} .rec .tr {{ right: 0; top: 0; border-top-width: 7px; border-right-width: 7px; }}
.rec .bl {{ left: 0; bottom: 0; border-bottom-width: 7px; border-left-width: 7px; }} .rec .br {{ right: 0; bottom: 0; border-bottom-width: 7px; border-right-width: 7px; }}
.rectag {{ position: absolute; left: 40px; top: 40px; font-weight: 700; font-size: 40px; color: #fff; letter-spacing: 2px; display: flex; align-items: center; gap: 14px; }}
.rectag .dot {{ width: 26px; height: 26px; border-radius: 50%; background: #FF3B30; }}
.rec .grid {{ position: absolute; inset: 0; background: linear-gradient(90deg, transparent 33.1%, rgba(255,255,255,.25) 33.3%, transparent 33.5%, transparent 66.5%, rgba(255,255,255,.25) 66.7%, transparent 66.9%), linear-gradient(0deg, transparent 33.1%, rgba(255,255,255,.25) 33.3%, transparent 33.5%, transparent 66.5%, rgba(255,255,255,.25) 66.7%, transparent 66.9%); }}
.pill-ui {{ position: absolute; left: 50%; top: 210px; transform: translateX(-50%); background: rgba(20,20,24,.86); color: #fff; font-weight: 600; font-size: 40px; padding: 18px 36px; border-radius: 60px; display: flex; gap: 18px; align-items: center; opacity: 0; z-index: 56; white-space: nowrap; }}
.pill-ui .spin {{ width: 34px; height: 34px; border-radius: 50%; border: 5px solid rgba(255,255,255,.25); border-top-color: #fff; }}
.call {{ position: absolute; left: 90px; right: 90px; top: 120px; background: rgba(28,28,32,.92); border-radius: 50px; padding: 44px 40px 40px; color: #fff; text-align: center; opacity: 0; z-index: 56; box-shadow: 0 30px 60px rgba(0,0,0,.5); }}
.cwho {{ font-weight: 800; font-size: 56px; letter-spacing: -1.5px; }} .csub {{ font-size: 34px; color: #AEAEB2; margin-top: 6px; }}
.cbtns {{ display: flex; justify-content: space-around; margin-top: 36px; }}
.cbtn {{ width: 128px; height: 128px; border-radius: 50%; font-size: 60px; display: flex; align-items: center; justify-content: center; }}
.cbtn.red {{ background: #FF3B30; }} .cbtn.green {{ background: #34C759; }}
.finger {{ position: absolute; left: 175px; top: 300px; font-size: 110px; opacity: 0; }}
.chat {{ position: absolute; left: 90px; right: 90px; top: 110px; background: rgba(242,242,247,.96); border-radius: 46px; padding: 30px 34px 36px; opacity: 0; z-index: 56; box-shadow: 0 30px 60px rgba(0,0,0,.45); }}
.chead {{ font-weight: 800; font-size: 40px; color: #111; text-align: center; margin-bottom: 18px; }}
.msg {{ display: table; background: #E5E5EA; color: #111; font-size: 42px; padding: 16px 28px; border-radius: 34px; margin: 12px 0; opacity: 0; transform-origin: 0 50%; }}
.cursor {{ position: absolute; left: 330px; top: 395px; font-size: 76px; color: #fff; transform: rotate(-110deg); opacity: 0; z-index: 70; filter: drop-shadow(0 4px 8px rgba(0,0,0,.6)); }}
#leak {{ position: absolute; inset: -200px; opacity: 0; mix-blend-mode: screen; pointer-events: none;
  background: radial-gradient(ellipse 60% 45% at 18% 40%, rgba(255,90,30,.95), rgba(255,90,30,0) 70%), radial-gradient(ellipse 50% 60% at 75% 60%, rgba(255,190,60,.9), rgba(255,190,60,0) 70%), radial-gradient(ellipse 40% 30% at 50% 15%, rgba(255,240,200,.8), rgba(255,240,200,0) 70%); filter: blur(30px); }}
.cap {{ position: absolute; left: 60px; right: 60px; top: 1150px; text-align: center; color: #FFFDF8; opacity: 0;
  text-shadow: 0 2px 4px rgba(0,0,0,.55), 0 0 22px rgba(0,0,0,.45); }}
.cap.low {{ top: 1395px; }}
.cap.dark {{ color: #1E1A14; text-shadow: 0 1px 0 rgba(255,240,200,.35); }}
.cap.dark .cscript {{ color: #1E1A14; }}
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
 
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
{chr(10).join('  ' + l for l in tl)}
  window.__timelines["main"] = tl;
</script>
</body></html>"""
open("index.html", "w").write(html)
print(f"index.html {TOTAL}s: {len(clips)} clips, hold at {HOLD_AT}, {len(chunks)} caption chunks, {len(set(round(x,2) for x in leaks))} leaks, {len(tl)} timeline lines")
