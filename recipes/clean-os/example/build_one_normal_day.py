#!/usr/bin/env python3
"""'Один обычный день' (C007) -> index.html (HyperFrames 1080x1920).

Edit grammar copied from the @yashmotions 'Apple-style clean edit' (see BREAKDOWN.md):
tight/wide shot alternation, 1-3 word cards resolving from blur, literal phone-UI scenes on white,
a red Figma-style selection box with a cursor, perspective text, a draining ring, a small sound on
every graphic entrance. Footage colour stays dusk (graded in assemble.py).
Every time is keyed to WORDS of the clean cut (build/words.cut.json), so a re-cut only needs a rebuild.
"""
import json, re, subprocess

FPS = 30
words = [w for s in json.load(open("build/words.cut.json"))["segments"] for w in s["words"]]
for w in words:
    w["w"] = w["word"].strip()
FIX = {"все": "всё", "еще": "ещё", "живешь.": "живёшь."}
for w in words:
    if w["w"].lower() in FIX:
        w["w"] = FIX[w["w"].lower()]
TOTAL = round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", "assets/wide.mp4"],
                                   capture_output=True, text=True).stdout), 3)


def norm(s):
    return re.sub(r"[^а-яёa-z0-9]", "", s.lower())


def W(text, n=1, end=False):
    k = 0
    for w in words:
        if norm(w["w"]) == norm(text):
            k += 1
            if k == n:
                return round(w["end"] if end else w["start"], 3)
    raise SystemExit(f"word not found: {text} #{n}")


tl, based = [], set()


def ft(sel, frm, to, at):
    if sel not in based:
        based.add(sel)
        tl.append(f'tl.set("{sel}", {json.dumps(frm)}, 0);')
    tl.append(f'tl.fromTo("{sel}", {json.dumps(frm)}, {json.dumps({**to, "immediateRender": False})}, {max(0, at):.3f});')


def st(sel, props, at):
    tl.append(f'tl.set("{sel}", {json.dumps(props)}, {max(0, at):.3f});')


sfx = []  # (id, at, vol)


def sound(sid, at, vol):
    sfx.append((sid, max(0, round(at, 3)), vol))


# ------------------------------------------------------------------ shots (wide / tight + slow push)
UI = {  # full-screen phone scenes: (in, out)
    "picker": (W("вернуться") - 0.08, W("не", 1) - 0.12),
    "lock": (W("ты", 2) - 0.1, W("и", 3) - 0.1),
    "search": (W("мне") - 0.06, W("поэтому") - 0.12),
    "photos": (W("однажды") - 0.1, W("но") - 0.1),
}
shots = [  # (start, kind, push_from, push_to)
    (0.0, "tight", 1.0, 1.05),
    (W("и", 1) - 0.04, "wide", 1.0, 1.03),
    (UI["picker"][1], "tight", 1.0, 1.04),
    (UI["lock"][1], "tight", 1.02, 1.06),
    (W("ощущалось") - 0.04, "wide", 1.04, 1.0),
    (W("потому") - 0.04, "tight", 1.0, 1.04),
    (W("ничто") - 0.04, "wide", 1.0, 1.06),
    (UI["search"][1], "wide", 1.14, 1.0),
    (W("почувствуй") - 0.04, "tight", 1.0, 1.05),
    (UI["photos"][1], "tight", 1.0, 1.07),
]
for i, (t0, kind, z0, z1) in enumerate(shots):
    t1 = shots[i + 1][0] if i + 1 < len(shots) else TOTAL
    st("#vw", {"autoAlpha": 1 if kind == "wide" else 0}, t0)
    st("#vt", {"autoAlpha": 1 if kind == "tight" else 0}, t0)
    ft("#cam", {"scale": z0}, {"scale": z1, "duration": round(t1 - t0, 3), "ease": "none"}, t0)
    if i and kind == "wide" and shots[i - 1][1] == "tight":
        sound("whoosh-2", t0 - 0.05, 0.05)

# ------------------------------------------------------------------ caption cards
# (text, start, end, style) style: s = small, m = medium, xl = hero, it = italic hero, stack = two lines (2nd italic)
cards = [
    ("представь,", W("представь"), W("что") - 0.02, "m"),
    ("что тебе", W("что"), W("80") - 0.02, "s"),
    ("80|лет", W("80"), W("и", 1) - 0.03, "xl-sub"),
    ("и каким-то образом", W("и", 1), UI["picker"][0], "s"),
    ("не какое-то", W("не", 1), W("важное") - 0.02, "s"),
    ("не", W("не", 2), W("день", 2) - 0.02, "s"),
    ("а просто", W("а"), W("сегодня") - 0.02, "s"),
    ("сегодня", W("сегодня"), UI["lock"][0], "it"),
    ("и даже то,", W("и", 3), W("что", 2) - 0.02, "s"),
    ("что сейчас тебя", W("что", 2), W("раздражает") - 0.02, "s"),
    ("ощущалось бы", W("ощущалось"), W("совсем") - 0.02, "m"),
    ("совсем|иначе", W("совсем"), W("потому") - 0.08, "stack"),
    ("потому что", W("потому"), W("ты", 3) - 0.02, "s"),
    ("ты знаешь,", W("ты", 3), W("ничто") - 0.06, "m"),
    ("поэтому иногда", W("поэтому"), W("просто", 2) - 0.02, "s"),
    ("просто", W("просто", 2), W("оглянись") - 0.02, "m"),
    ("оглянись|вокруг", W("оглянись"), W("почувствуй") - 0.08, "stack"),
    ("почувствуй", W("почувствуй"), W("жизнь") - 0.02, "m"),
    ("но прямо сейчас", W("но"), W("ты", 5) - 0.02, "s"),
    ("ты всё ещё", W("ты", 5), W("здесь") - 0.02, "m"),
    ("здесь", W("здесь"), TOTAL, "xl"),
]
cap_html = []
for i, (txt, a, b, style) in enumerate(cards):
    cid = f"c{i}"
    if style in ("stack", "xl-sub"):
        top, bot = txt.split("|")
        inner = (f'<div class="l1">{top}</div><div class="l2">{bot}</div>' if style == "stack"
                 else f'<div class="hero">{top}</div><div class="sub">{bot}</div>')
    else:
        inner = txt
    cap_html.append(f'<div id="{cid}" class="card {style}">{inner}</div>')
    ft(f"#{cid}", {"autoAlpha": 0, "scale": 0.82, "filter": "blur(14px)"},
       {"autoAlpha": 1, "scale": 1, "filter": "blur(0px)", "duration": 0.22, "ease": "power3.out"}, a - 0.03)
    tl.append(f'tl.fromTo("#{cid}", {{autoAlpha: 1, filter: "blur(0px)"}}, {{autoAlpha: 0, filter: "blur(10px)", duration: 0.12, immediateRender: false}}, {max(a + 0.2, b - 0.1):.3f});')
    sound(["pop-1", "pop-2", "pop-3"][i % 3], a - 0.02, 0.05 if style == "s" else 0.07)
    if style == "stack":
        ft(f"#{cid} .l2", {"autoAlpha": 0, "y": 30, "filter": "blur(10px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.25, "ease": "power3.out"}, W(txt.split("|")[1]) - 0.03)
    if style == "xl-sub":
        ft(f"#{cid} .sub", {"autoAlpha": 0, "y": 18}, {"autoAlpha": 1, "y": 0, "duration": 0.22}, W("лет") - 0.03)

# ------------------------------------------------------------------ red Figma selection box (+ cursor)
def figma(fid, text, t_in, t_click, t_out, delete):
    ft(f"#{fid}", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.08}, t_in - 0.04)
    ft(f"#{fid} .fbox", {"scaleX": 0.6, "autoAlpha": 0}, {"scaleX": 1, "autoAlpha": 1, "duration": 0.18, "ease": "power3.out"}, t_in - 0.04)
    ft(f"#{fid} .fguide", {"scaleX": 0}, {"scaleX": 1, "duration": 0.3, "ease": "power2.out"}, t_in)
    ft(f"#{fid} .ftext", {"autoAlpha": 0, "filter": "blur(10px)"}, {"autoAlpha": 1, "filter": "blur(0px)", "duration": 0.18}, t_in)
    ft(f"#{fid} .cursor", {"x": 260, "y": 260, "autoAlpha": 0}, {"x": 0, "y": 0, "autoAlpha": 1, "duration": max(0.18, t_click - t_in - 0.05), "ease": "power3.out"}, t_in)
    ft(f"#{fid} .cursor", {"scale": 1}, {"scale": 0.82, "duration": 0.06, "yoyo": True, "repeat": 1}, t_click)
    sound("click-1", t_click, 0.22)
    if delete:
        ft(f"#{fid} .strike", {"scaleX": 0}, {"scaleX": 1, "duration": 0.16, "ease": "power2.out"}, t_click + 0.05)
        ft(f"#{fid} .ftext", {"autoAlpha": 1}, {"autoAlpha": 0.35, "duration": 0.15}, t_click + 0.12)
        sound("tick-1", t_click + 0.06, 0.12)
    tl.append(f'tl.fromTo("#{fid}", {{autoAlpha: 1, scale: 1}}, {{autoAlpha: 0, scale: 0.96, duration: 0.12, immediateRender: false}}, {t_out - 0.1:.3f});')
    sound("tick-1", t_in, 0.08)
    return f'''<div id="{fid}" class="figma">
  <div class="fguide top"></div><div class="fguide bot"></div>
  <div class="fbox"><span class="flabel">Text</span><i class="h tl"></i><i class="h tr"></i><i class="h bl"></i><i class="h br"></i>
   <span class="ftext">{text}{'<b class="strike"></b>' if delete else ''}</span></div>
  <svg class="cursor" viewBox="0 0 28 28" width="64" height="64"><path d="M4 2 L4 22 L9.5 17 L13 25 L16.5 23.5 L13 15.8 L20.5 15.8 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>
</div>'''


figma_html = [
    figma("fg1", "важное событие", W("важное"), W("событие") + 0.2, W("не", 2), True),
    figma("fg2", "день свадьбы", W("день", 2), W("свадьбы") + 0.25, W("а"), True),
    figma("fg3", "раздражает", W("раздражает"), W("раздражает") + 0.35, W("ощущалось"), False),
]

# ------------------------------------------------------------------ UI scene: date picker (2086 -> today)
p0, p1 = UI["picker"]
years = list(range(2026, 2087))
ft("#picker", {"autoAlpha": 0, "y": 80, "scale": 0.96}, {"autoAlpha": 1, "y": 0, "scale": 1, "duration": 0.28, "ease": "power3.out"}, p0)
tl.append(f'tl.fromTo("#picker", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.18, immediateRender: false}}, {p1 - 0.16:.3f});')
sound("tech-digital-whoosh", p0 - 0.05, 0.10)
ROW = 86
ft("#yearcol", {"y": -(len(years) - 1) * ROW}, {"y": 0, "duration": round(W("прожить") - p0 - 0.1, 3), "ease": "power3.inOut"}, p0 + 0.15)
for k in range(6):
    sound("tick-1", p0 + 0.3 + k * (W("прожить") - p0 - 0.5) / 6, 0.07)
ft("#pickbtn", {"scale": 1, "backgroundColor": "#0A84FF"}, {"scale": 0.94, "duration": 0.08, "yoyo": True, "repeat": 1}, W("прожить"))
sound("click-1", W("прожить"), 0.18)
ft("#pickline", {"autoAlpha": 0, "y": 24, "filter": "blur(10px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.3, "ease": "power3.out"}, W("один") - 0.03)
ft("#todaypill", {"autoAlpha": 0, "scale": 0.6}, {"autoAlpha": 1, "scale": 1, "duration": 0.25, "ease": "back.out(2)"}, W("сегодняшней") - 0.03)
sound("tech-ui-confirm", W("сегодняшней") - 0.03, 0.12)
year_html = "".join(f'<div class="yr">{y}</div>' for y in years)

# ------------------------------------------------------------------ UI scene: lock screen notifications
l0, l1 = UI["lock"]
ft("#lock", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.22}, l0)
tl.append(f'tl.fromTo("#lock", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.2, immediateRender: false}}, {l1 - 0.18:.3f});')
sound("whoosh-1", l0 - 0.05, 0.07)
notes = [("⏰", "Будильник", "Пора вставать", "просыпаешься"), ("☕️", "Кофе", "Готово", "готовишь"),
         ("🚗", "Карты", "До работы 18 мин", "едешь"), ("💬", "Сообщения", "Доброе утро!", "людей"),
         ("💬", "Команда", "Видимся в 10", "которых")]
note_html = []
for i, (ic, app, msg, key) in enumerate(notes):
    t = W(key) - 0.06
    note_html.append(f'<div id="n{i}" class="note"><span class="ic">{ic}</span><div><b>{app}</b><span>{msg}</span></div><em>сейчас</em></div>')
    ft(f"#n{i}", {"autoAlpha": 0, "y": -40, "scale": 0.94}, {"autoAlpha": 1, "y": 0, "scale": 1, "duration": 0.32, "ease": "back.out(1.6)"}, t)
    sound("tech-notification-2" if i % 2 == 0 else "ding-1", t, 0.10)
ft("#lockcap", {"autoAlpha": 0, "filter": "blur(12px)", "scale": 0.85}, {"autoAlpha": 1, "filter": "blur(0px)", "scale": 1, "duration": 0.24, "ease": "power3.out"}, W("каждый") - 0.03)

# ------------------------------------------------------------------ wide: perspective text over the horizon + draining ring
w0 = W("ничто") - 0.04
ft("#persp", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.2}, w0)
for i, (key, ln) in enumerate((("ничто", "pl1"), ("не", "pl2"), ("навсегда", "pl3"))):
    t = W(key) if key != "не" else W("не", 3)
    ft(f"#{ln}", {"autoAlpha": 0, "y": 40, "filter": "blur(12px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.3, "ease": "power3.out"}, t - 0.03)
    sound("whoosh-cine" if i < 2 else "cinematic-cine-hit", t - 0.05, 0.08 if i < 2 else 0.07)
tl.append(f'tl.fromTo("#persp", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.15, immediateRender: false}}, {UI["search"][0] - 0.12:.3f});')
ft("#ring", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.25}, w0 + 0.1)
ft("#ringarc", {"strokeDashoffset": 0}, {"strokeDashoffset": 1, "duration": round(UI["search"][0] - w0 - 0.3, 3), "ease": "power1.in"}, w0 + 0.2)
ft("#ringpct", {"textContent": 100}, {"textContent": 0, "duration": round(UI["search"][0] - w0 - 0.3, 3), "ease": "power1.in", "snap": {"textContent": 1}}, w0 + 0.2)
tl.append(f'tl.fromTo("#ring", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.15, immediateRender: false}}, {UI["search"][0] - 0.12:.3f});')

# ------------------------------------------------------------------ UI scene: search + the loading bar that never finishes
s0, s1 = UI["search"]
ft("#search", {"autoAlpha": 0, "y": 80}, {"autoAlpha": 1, "y": 0, "duration": 0.26, "ease": "power3.out"}, s0)
tl.append(f'tl.fromTo("#search", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.18, immediateRender: false}}, {s1 - 0.16:.3f});')
sound("tech-digital-whoosh", s0 - 0.05, 0.10)
ft("#shead", {"autoAlpha": 0, "filter": "blur(10px)"}, {"autoAlpha": 1, "filter": "blur(0px)", "duration": 0.25}, W("мы") - 0.03)
q = "что дальше?"
ty0, ty1 = W("когда") - 0.05, W("торопимся", end=True)
for k in range(1, len(q) + 1):
    st("#qtext", {"textContent": q[:k]}, ty0 + (ty1 - ty0) * k / len(q))
st("#qtext", {"textContent": ""}, 0)
sound("tech-keyboard-burst", ty0, 0.12)
ft("#loadwrap", {"autoAlpha": 0, "y": 30}, {"autoAlpha": 1, "y": 0, "duration": 0.22}, W("к", 1) - 0.05)
ft("#loadfill", {"scaleX": 0}, {"scaleX": 0.97, "duration": round(s1 - W("к", 1) - 0.3, 3), "ease": "expo.out"}, W("к", 1))
ft("#loadpct", {"textContent": 0}, {"textContent": 97, "duration": round(s1 - W("к", 1) - 0.3, 3), "ease": "expo.out", "snap": {"textContent": 1}}, W("к", 1))

# ------------------------------------------------------------------ UI scene: Photos memory (the moment becomes a memory)
m0, m1 = UI["photos"]
ft("#photos", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.12}, m0)
tl.append(f'tl.fromTo("#photos", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.2, immediateRender: false}}, {m1 - 0.18:.3f});')
ft("#memcard", {"scale": 2.02, "y": -58, "borderRadius": 0}, {"scale": 1, "y": 0, "borderRadius": 46, "duration": 0.7, "ease": "power3.inOut"}, m0 + 0.12)
sound("shutter-1", m0 + 0.05, 0.22)
ft("#memhead", {"autoAlpha": 0, "y": -20}, {"autoAlpha": 1, "y": 0, "duration": 0.3}, m0 + 0.55)
ft("#memtitle", {"autoAlpha": 0, "y": 16}, {"autoAlpha": 1, "y": 0, "duration": 0.3}, W("момент") - 0.03)
ft("#memcap", {"autoAlpha": 0, "filter": "blur(12px)"}, {"autoAlpha": 1, "filter": "blur(0px)", "duration": 0.26}, W("станет") - 0.03)
sound("tech-ui-confirm", W("воспоминанием") - 0.03, 0.1)

# ------------------------------------------------------------------ script "жизнь" (tight)
j0 = W("жизнь")
ft("#script", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.05}, j0 - 0.05)
ft("#script .sw", {"clipPath": "inset(0 100% 0 0)"}, {"clipPath": "inset(0 0% 0 0)", "duration": 0.7, "ease": "power2.out"}, j0 - 0.05)
ft("#script .ssub", {"autoAlpha": 0, "y": 16}, {"autoAlpha": 1, "y": 0, "duration": 0.25}, W("которой") - 0.03)
tl.append(f'tl.fromTo("#script", {{autoAlpha: 1}}, {{autoAlpha: 0, filter: "blur(10px)", duration: 0.15, immediateRender: false}}, {UI["photos"][0] - 0.15:.3f});')
sound("whoosh-1", j0 - 0.1, 0.06)

# freeze still for the memory card: the tight shot just before "однажды"
still_t = UI["photos"][0] - 0.05

# ------------------------------------------------------------------ audio
ui_windows = [UI[k] for k in UI]
audio = [f'<audio id="vo" src="assets/voice.wav" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-volume="1"></audio>']
for i, (sid, at, vol) in enumerate(sorted(sfx, key=lambda s: s[1])):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"assets/sfx/{sid}.wav"], capture_output=True, text=True).stdout)
    audio.append(f'<audio id="sfx{i}" src="assets/sfx/{sid}.wav" data-start="{at:.3f}" data-duration="{min(dur, TOTAL - at):.3f}" data-track-index="{14 + i % 5}" data-volume="{vol}"></audio>')
bed = 0.16
lane = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": [{"t": 0, "v": 0}, {"t": 1.0, "v": bed}, {"t": TOTAL - 2.0, "v": bed}, {"t": TOTAL, "v": 0}]}]})
audio.append(f"<audio id=\"bed\" src=\"assets/music/bed.mp3\" data-start=\"0\" data-duration=\"{TOTAL}\" data-media-start=\"0\" data-track-index=\"20\" data-automation='{lane}'></audio>")
ft("#fadeout", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.6}, TOTAL - 0.6)

fonts_css = open("assets/fonts/fonts-local.css").read().replace("url(", "url(assets/fonts/")
html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{fonts_css}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; font-family: Inter; }}
#cam {{ position: absolute; inset: 0; transform-origin: 50% 40%; }}
#cam video {{ position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; }}
#shade {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,.42) 100%); pointer-events: none; }}
.card {{ position: absolute; left: 50%; top: 1250px; transform: translate(-50%, -50%); white-space: nowrap; color: #fff; text-align: center;
        font-weight: 700; letter-spacing: -0.03em; line-height: .95; opacity: 0; font-variation-settings: "opsz" 32;
        text-shadow: 0 2px 2px rgba(0,0,0,.25), 0 8px 40px rgba(0,0,0,.45); }}
.card.s {{ font-size: 64px; font-weight: 600; }}
.card.m {{ font-size: 96px; }}
.card.xl {{ font-size: 230px; font-weight: 800; letter-spacing: -0.05em; }}
.card.it {{ font-size: 170px; font-style: italic; font-weight: 700; letter-spacing: -0.045em; }}
.card.stack {{ font-size: 130px; }}
.card.stack .l2 {{ font-style: italic; font-weight: 300; letter-spacing: -0.04em; }}
.card.xl-sub .hero {{ font-size: 300px; font-weight: 800; letter-spacing: -0.06em; }}
.card.xl-sub .sub {{ font-size: 46px; font-style: italic; font-weight: 300; letter-spacing: 0; margin-top: 6px; opacity: .9; }}
.figma {{ position: absolute; left: 0; right: 0; top: 1250px; height: 0; opacity: 0; }}
.fguide {{ position: absolute; left: 0; right: 0; height: 0; border-top: 2px dashed rgba(239,68,68,.75); transform-origin: 50% 50%; }}
.fguide.top {{ top: -72px; }} .fguide.bot {{ top: 72px; }}
.fbox {{ position: absolute; left: 50%; top: -72px; height: 144px; transform: translateX(-50%); display: flex; align-items: center; padding: 0 44px;
        background: rgba(239,68,68,.38); border: 3px solid #EF4444; white-space: nowrap; }}
.fbox .h {{ position: absolute; width: 16px; height: 16px; background: #fff; border: 3px solid #EF4444; }}
.h.tl {{ left: -11px; top: -11px; }} .h.tr {{ right: -11px; top: -11px; }} .h.bl {{ left: -11px; bottom: -11px; }} .h.br {{ right: -11px; bottom: -11px; }}
.flabel {{ position: absolute; left: -3px; top: -44px; background: #EF4444; color: #fff; font-size: 22px; font-weight: 600; padding: 4px 10px; border-radius: 4px 4px 4px 0; }}
.ftext {{ position: relative; color: #fff; font-size: 88px; font-weight: 700; letter-spacing: -0.035em; }}
.strike {{ position: absolute; left: -6px; right: -6px; top: 54%; height: 7px; background: #fff; transform-origin: 0 50%; }}
.cursor {{ position: absolute; left: 60%; top: 30px; filter: drop-shadow(0 4px 8px rgba(0,0,0,.35)); }}
.ui {{ position: absolute; inset: 0; background: #FAFAFA; color: #111; opacity: 0; }}
.status {{ position: absolute; left: 70px; right: 70px; top: 54px; display: flex; justify-content: space-between; font-size: 30px; font-weight: 600; }}
#picker h2 {{ position: absolute; left: 0; right: 0; top: 330px; text-align: center; font-size: 58px; font-weight: 700; letter-spacing: -0.03em; margin: 0; }}
.wheel {{ position: absolute; left: 90px; right: 90px; top: 520px; height: 430px; border-radius: 34px; background: #fff; box-shadow: 0 20px 60px rgba(0,0,0,.08); overflow: hidden; display: flex; justify-content: center; gap: 40px; font-size: 56px; font-weight: 500; }}
.wheel .sel {{ position: absolute; left: 24px; right: 24px; top: 172px; height: {ROW}px; border-radius: 18px; background: #EEF0F3; }}
.col {{ position: relative; height: 100%; overflow: hidden; -webkit-mask-image: linear-gradient(180deg, transparent, #000 35%, #000 65%, transparent); }}
.col .inner {{ position: absolute; left: 0; right: 0; top: 172px; text-align: center; }}
.col .inner div {{ height: {ROW}px; line-height: {ROW}px; }}
#yearcol {{ width: 190px; }}
#pickbtn {{ position: absolute; left: 50%; top: 1010px; transform: translateX(-50%); background: #0A84FF; color: #fff; font-size: 40px; font-weight: 600; padding: 26px 60px; border-radius: 40px; }}
#pickline {{ position: absolute; left: 0; right: 0; top: 1200px; text-align: center; font-size: 92px; font-weight: 700; letter-spacing: -0.04em; line-height: 1; opacity: 0; }}
#pickline em {{ font-weight: 300; }}
#todaypill {{ position: absolute; left: 50%; top: 1380px; transform: translateX(-50%); background: #111; color: #fff; font-size: 38px; font-weight: 600; padding: 14px 34px; border-radius: 30px; opacity: 0; }}
#lock {{ background: #000; }}
#lock video {{ position: absolute; inset: -60px; width: 1200px; height: 2040px; object-fit: cover; filter: blur(36px) brightness(.55) saturate(1.2); }}
.ltime {{ position: absolute; left: 0; right: 0; top: 230px; text-align: center; color: #fff; font-size: 230px; font-weight: 300; letter-spacing: -0.04em; }}
.ldate {{ position: absolute; left: 0; right: 0; top: 190px; text-align: center; color: rgba(255,255,255,.85); font-size: 40px; font-weight: 500; }}
.notes {{ position: absolute; left: 50px; right: 50px; top: 560px; display: flex; flex-direction: column; gap: 18px; }}
.note {{ display: flex; align-items: center; gap: 22px; padding: 26px 30px; border-radius: 36px; background: rgba(245,245,245,.72); color: #111; font-size: 36px; opacity: 0;
        box-shadow: 0 10px 30px rgba(0,0,0,.18); }}
.note .ic {{ font-size: 56px; width: 74px; height: 74px; border-radius: 18px; background: #fff; display: flex; align-items: center; justify-content: center; }}
.note div {{ flex: 1; display: flex; flex-direction: column; }}
.note b {{ font-weight: 700; }} .note span {{ color: #333; }} .note em {{ font-style: normal; color: #666; font-size: 28px; align-self: flex-start; }}
#lockcap {{ position: absolute; left: 0; right: 0; top: 1520px; text-align: center; color: #fff; font-size: 110px; font-weight: 700; font-style: italic; letter-spacing: -0.045em; opacity: 0; }}
#persp {{ position: absolute; left: 0; right: 0; top: 150px; height: 640px; perspective: 900px; opacity: 0; }}
#persp .plane {{ position: absolute; left: 0; right: 0; top: 0; transform: rotateX(28deg); transform-origin: 50% 100%; text-align: center; color: #fff; }}
#pl1, #pl2 {{ font-size: 92px; font-weight: 700; letter-spacing: -0.035em; line-height: 1.05; opacity: 0; text-shadow: 0 6px 40px rgba(0,0,0,.4); }}
#pl3 {{ font-size: 190px; font-weight: 800; font-style: italic; letter-spacing: -0.05em; opacity: 0; text-shadow: 0 6px 40px rgba(0,0,0,.4); }}
#ring {{ position: absolute; left: 850px; top: 820px; width: 0; height: 0; opacity: 0; }}
#ring svg {{ position: absolute; left: -110px; top: -110px; }}
#ringpct {{ position: absolute; left: -110px; width: 220px; top: -34px; text-align: center; color: #fff; font-size: 56px; font-weight: 700; letter-spacing: -0.03em; }}
#ringpct::after {{ content: "%"; font-weight: 300; }}
#search h2 {{ position: absolute; left: 80px; right: 80px; top: 380px; font-size: 92px; font-weight: 700; letter-spacing: -0.04em; line-height: 1; margin: 0; opacity: 0; }}
#search h2 em {{ font-weight: 300; }}
.sbar {{ position: absolute; left: 80px; right: 80px; top: 720px; height: 120px; border-radius: 60px; background: #EDEEF0; display: flex; align-items: center; padding: 0 44px; font-size: 52px; color: #111; }}
.sbar svg {{ margin-right: 24px; }}
#qtext::after {{ content: ""; display: inline-block; width: 4px; height: 56px; background: #0A84FF; margin-left: 4px; vertical-align: -8px; }}
#loadwrap {{ position: absolute; left: 80px; right: 80px; top: 960px; opacity: 0; }}
#loadwrap .lab {{ display: flex; justify-content: space-between; font-size: 40px; font-weight: 600; margin-bottom: 22px; color: #111; }}
#loadwrap .lab span:last-child::after {{ content: "%"; }}
.track {{ height: 26px; border-radius: 13px; background: #E3E5E8; overflow: hidden; }}
#loadfill {{ height: 100%; background: #0A84FF; transform-origin: 0 50%; border-radius: 13px; }}
#photos {{ background: #fff; }}
#memhead {{ position: absolute; left: 80px; top: 150px; font-size: 76px; font-weight: 800; letter-spacing: -0.04em; opacity: 0; }}
#memhead span {{ display: block; font-size: 34px; font-weight: 500; color: #8E8E93; letter-spacing: 0; margin-bottom: 8px; }}
#memcard {{ position: absolute; left: 80px; top: 330px; width: 920px; height: 1180px; overflow: hidden; border-radius: 46px; transform-origin: 50% 40%; box-shadow: 0 30px 80px rgba(0,0,0,.25); }}
#memcard img {{ width: 100%; height: 100%; object-fit: cover; }}
#memtitle {{ position: absolute; left: 60px; bottom: 70px; color: #fff; opacity: 0; text-shadow: 0 4px 30px rgba(0,0,0,.5); }}
#memtitle b {{ display: block; font-size: 84px; font-weight: 800; letter-spacing: -0.04em; line-height: 1; }}
#memtitle span {{ font-size: 36px; font-weight: 500; opacity: .9; }}
#memcap {{ position: absolute; left: 0; right: 0; top: 1580px; text-align: center; font-size: 84px; font-weight: 700; font-style: italic; letter-spacing: -0.04em; color: #111; opacity: 0; }}
#script {{ position: absolute; left: 0; right: 0; top: 1050px; text-align: center; opacity: 0; }}
#script .sw {{ display: inline-block; font-family: "Great Vibes"; font-size: 300px; color: #fff; line-height: 1; padding: 0 30px; text-shadow: 0 8px 50px rgba(0,0,0,.45); }}
#script .ssub {{ font-size: 46px; font-style: italic; font-weight: 300; color: #fff; margin-top: -10px; opacity: 0; }}
#fadeout {{ position: absolute; inset: 0; background: #000; opacity: 0; }}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{TOTAL}" data-fps="{FPS}">
 <div id="cam">
  <video id="vw" src="assets/wide.mp4" data-start="0" data-duration="{TOTAL}" data-track-index="0" muted playsinline></video>
  <video id="vt" src="assets/tight.mp4" data-start="0" data-duration="{TOTAL}" data-track-index="1" muted playsinline></video>
 </div>
 <div id="shade"></div>
 <div id="persp"><div class="plane"><div id="pl1">ничто из этого</div><div id="pl2">не останется</div><div id="pl3">навсегда</div></div></div>
 <div id="ring"><svg width="220" height="220" viewBox="0 0 220 220"><circle cx="110" cy="110" r="96" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="10"/><circle id="ringarc" cx="110" cy="110" r="96" fill="none" stroke="#fff" stroke-width="10" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="0" transform="rotate(-90 110 110)"/></svg><div id="ringpct">100</div></div>
 {''.join(cap_html)}
 {''.join(figma_html)}
 <div id="script"><div class="sw">жизнь</div><div class="ssub">которой ты сейчас живёшь</div></div>
 <div id="picker" class="ui"><div class="status"><span>19:24</span><span>●●●</span></div>
  <h2>Вернуться в день</h2>
  <div class="wheel"><div class="sel"></div>
   <div class="col" style="width:90px"><div class="inner"><div>7</div></div></div>
   <div class="col" style="width:280px"><div class="inner"><div>октября</div></div></div>
   <div class="col" style="width:190px"><div class="inner" id="yearcol">{year_html}</div></div>
  </div>
  <div id="pickbtn">Прожить ещё раз</div>
  <div id="pickline">один <em>обычный</em> день</div>
  <div id="todaypill">Сегодня</div>
 </div>
 <div id="lock" class="ui"><video id="vlock" src="assets/wide.mp4" data-start="0" data-duration="{TOTAL}" data-track-index="2" muted playsinline></video>
  <div class="ldate">вторник, 7 октября</div><div class="ltime">7:00</div>
  <div class="notes">{''.join(note_html)}</div>
  <div id="lockcap">каждый день</div>
 </div>
 <div id="search" class="ui"><div class="status"><span>19:24</span><span>●●●</span></div>
  <h2 id="shead">мы забываем<br><em>об этом</em></h2>
  <div class="sbar"><svg width="44" height="44" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="#8E8E93" stroke-width="2.4"/><path d="M15.5 15.5 L21 21" stroke="#8E8E93" stroke-width="2.4" stroke-linecap="round"/></svg><span id="qtext"></span></div>
  <div id="loadwrap"><div class="lab"><span>к чему-то следующему…</span><span id="loadpct">0</span></div><div class="track"><div id="loadfill"></div></div></div>
 </div>
 <div id="photos" class="ui">
  <div id="memhead"><span>Воспоминания</span>Сегодня</div>
  <div id="memcard"><img src="assets/memory-photo.jpg"><div id="memtitle"><b>Один обычный день</b></div></div>
  <div id="memcap">станет воспоминанием</div>
 </div>
 <div id="fadeout"></div>
 {''.join(audio)}
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
{chr(10).join('  ' + l for l in tl)}
  window.__timelines["main"] = tl;
</script>
</body></html>
"""
open("index.html", "w").write(html)
print(f"index.html {TOTAL}s: {len(cards)} cards, {len(sfx)} sfx, {len(tl)} timeline lines")
for k, (a, b) in UI.items():
    print(f"  {k}: {a:.2f}-{b:.2f}")
