#!/usr/bin/env python3
"""Clean OS worked example: "one thing at a time" (script.txt) -> index.html (HyperFrames 1080x1920).

Copy to $P/build.py after assemble.py and the transcript of the cut voice exist:
    python3 $S/recipes/clean-os/assemble.py $P            # cut.json -> assets/{wide,tight}.mp4, assets/voice.wav, build/edl_map.json
    python3 $S/scripts/transcribe.py $P/assets/voice.wav --out $P/build/words.cut.json --lang en --model turbo
    python3 $S/recipes/clean-os/fetch_fonts.py $P "Marck Script"
    cd $P && python3 build.py && $S/scripts/hf.sh lint

The house look (house.json): Inter lowercase word cards resolving from blur on the chest, the red Figma selection box
(reject = strike, focus = select only), QuickType suggestions tapped up into the card on choice words, the Markup pen
writing the signature word in Marck Script, one accent (green #30D158: finishing things), the speaker's plate as shot.
This reel's components (SYSTEM.md slots; a new reel picks new ones):
  S1 OS scenes   home screen whose badges count up on the numbers (attention), the app switcher flicking every card
                 away but one (decision), a chest window with a timer wheel and a notifications toggle (time),
                 a checklist with one item done and ten started (progress: the resolution)
  S2 transition  the scene grows out of the Dynamic Island (clip-path, 0.24 s, content from frame one) and shrinks back
  S4 data        an "attention" battery beside the head draining 100 -> 9 % across the sentence
Every time is keyed to WORDS of the cut (W("word", n): the n-th occurrence; "a|b" accepts either spelling), so a re-cut
only needs a re-transcribe and a rebuild. A missing word stops the build: fix the key, not the transcript.
"""
import json, os, re, shutil, subprocess

FPS = 30
S = os.path.expanduser(os.environ.get("S", "~/.claude/skills/ghost-editor"))
raw = [w for s in json.load(open("build/words.cut.json"))["segments"] for w in s["words"]]
words = []
for w in raw:
    txt = w["word"].strip()
    if words and txt.startswith("-"):          # whisper splits "half-written" into "half" + "-written"
        words[-1]["w"] += txt; words[-1]["end"] = w["end"]; continue
    words.append({"w": txt, "start": w["start"], "end": w["end"]})
SEG = json.load(open("build/edl_map.json"))
TOTAL = round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", "assets/wide.mp4"],
                                   capture_output=True, text=True).stdout), 3)
ACCENT = "#30D158"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def W(text, n=1, end=False):
    keys = {norm(k) for k in text.split("|")}
    k = 0
    for w in words:
        if norm(w["w"]) in keys:
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


def base(sel, props):
    """the state at time 0 for an element whose first tween starts from another state"""
    based.add(sel)
    st(sel, props, 0)


sfx = []  # (id, at, vol)


def sound(sid, at, vol):
    sfx.append((sid, max(0, round(at, 3)), vol))


# ------------------------------------------------------------------ scene windows and shots (wide / tight + slow push)
UI = {  # full-screen OS scenes: (in, out)
    "home": (W("counted") - 0.06, W("every") - 0.1),
    "switch": (W("close") - 0.06, W("set") - 0.1),
    "list": (W("one", 3) - 0.1, SEG[8]["start"] + 0.15),  # out over the next take: cover the tail of this one
}
CW = (W("set") - 0.04, W("not") - 0.12)                    # the chest window (timer + toggle): the face stays on screen
shots = [  # (start, kind, push_from, push_to)
    (0.0, "tight", 1.0, 1.05),                            # frame 1 is the speaker
    (W("you", 2) - 0.04, "wide", 1.0, 1.03),
    (UI["home"][1], "tight", 1.0, 1.04),
    (W("and", 2) - 0.04, "wide", 1.0, 1.04),               # the attention battery sits beside the head
    (W("so") - 0.04, "tight", 1.02, 1.06),
    (UI["switch"][1], "wide", 1.04, 1.0),                  # the chest window needs the chest
    (W("not") - 0.04, "tight", 1.0, 1.04),
    (W("just") - 0.04, "wide", 1.0, 1.03),
    (UI["list"][1], "tight", 1.0, 1.07),
]
for i, (t0, kind, z0, z1) in enumerate(shots):
    t1 = shots[i + 1][0] if i + 1 < len(shots) else TOTAL
    st("#vw", {"autoAlpha": 1 if kind == "wide" else 0}, t0)
    st("#vt", {"autoAlpha": 1 if kind == "tight" else 0}, t0)
    ft("#cam", {"scale": z0}, {"scale": z1, "duration": round(t1 - t0, 3), "ease": "none"}, t0)
    if i and kind == "wide" and shots[i - 1][1] == "tight":
        sound("whoosh-2", t0 - 0.05, 0.05)

# ------------------------------------------------------------------ word cards (one text element at a time)
# (text, start, end, style, second-line key) style: s, m, it, xl, stack (2nd line italic light), xl-sub
cards = [
    ("you don't need", W("you"), W("more") - 0.02, "s", None),
    ("you need", W("you", 2), W("fewer") - 0.02, "s", None),
    ("fewer tabs", W("fewer"), W("this") - 0.06, "it", None),
    ("this morning", W("this"), UI["home"][0], "m", None),
    ("every one of them is", W("every"), W("small") - 0.02, "s", None),
    ("to come back", W("to"), W("later") - 0.02, "s", None),
    ("later", W("later"), W("and", 2) - 0.06, "it", None),
    ("and every promise", W("and", 2), W("takes") - 0.02, "s", None),
    ("takes a little piece", W("takes"), W("of", 2) - 0.02, "s", None),
    ("of your|attention", W("of", 2), W("so") - 0.08, "stack", "attention"),
    ("so try this", W("so"), W("pick") - 0.02, "m", None),
    ("pick", W("pick"), W("one", 2) - 0.02, "s", None),
    ("one thing", W("one", 2), UI["switch"][0], "it", None),
    ("just until", W("just"), W("the") - 0.02, "m", None),
    ("the timer rings", W("the"), W("then") - 0.06, "m", None),
    ("then you'll have", W("then"), UI["list"][0], "s", None),
    ("any app", W("any"), TOTAL, "it", None),
]
cap_html = []
for i, (txt, a, b, style, l2) in enumerate(cards):
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
    if b < TOTAL:
        tl.append(f'tl.fromTo("#{cid}", {{autoAlpha: 1, filter: "blur(0px)"}}, {{autoAlpha: 0, filter: "blur(10px)", duration: 0.12, immediateRender: false}}, {max(a + 0.2, b - 0.1):.3f});')
    sound(["pop-1", "pop-2", "pop-3"][i % 3], a - 0.02, 0.05 if style == "s" else 0.07)
    if l2:
        ft(f"#{cid} .l2", {"autoAlpha": 0, "y": 30, "filter": "blur(10px)"},
           {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.25, "ease": "power3.out"}, W(l2) - 0.03)


# ------------------------------------------------------------------ S3 red Figma selection box (+ cursor): reject / focus
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
    figma("fg1", "more time", W("more"), W("time") + 0.15, W("you", 2), True),            # rejected
    figma("fg2", "a small promise", W("small"), W("promise") + 0.2, W("to"), False),      # focus
    figma("fg3", "not forever", W("not"), W("forever") + 0.2, W("just"), True),           # rejected
]


# ------------------------------------------------------------------ S7 QuickType: the spoken choice word tapped up into the card
def quicktype(qid, three, t_up, t_tap):
    ft(f"#{qid}", {"autoAlpha": 0, "y": 70}, {"autoAlpha": 1, "y": 0, "duration": 0.22, "ease": "power3.out"}, t_up)
    ft(f"#{qid} .pick", {"backgroundColor": "rgba(255,255,255,0)", "color": "#ffffff"},
       {"backgroundColor": "rgba(255,255,255,1)", "color": "#111111", "duration": 0.08}, t_tap - 0.14)
    base(f"#{qid} .fly", {"autoAlpha": 0})
    ft(f"#{qid} .fly", {"autoAlpha": 1, "y": 0, "scale": 1}, {"autoAlpha": 0, "y": -170, "scale": 1.7, "duration": 0.2, "ease": "power2.in"}, t_tap - 0.06)
    tl.append(f'tl.fromTo("#{qid}", {{autoAlpha: 1, y: 0}}, {{autoAlpha: 0, y: 50, duration: 0.14, immediateRender: false}}, {t_tap + 0.12:.3f});')
    sound("tick-1", t_up, 0.06)
    sound("tick-1", t_tap - 0.12, 0.12)
    a, m, b = three
    return f'<div id="{qid}" class="qt"><span>{a}</span><span class="pick">{m}</span><span>{b}</span><b class="fly">{m}</b></div>'


qt_html = [
    quicktype("qt1", ("more", "fewer", "new"), W("you", 2) + 0.12, W("fewer")),
    quicktype("qt2", ("all", "one", "two"), W("pick") + 0.08, W("one", 2)),
]

# ------------------------------------------------------------------ S2: scenes grow out of the Dynamic Island and shrink back
ISLAND = "inset(38px 405px 1808px 405px round 37px)"      # the island: 270 x 74 at the top centre
FULL = "inset(0px 0px 0px 0px round 0px)"


def island(sid, t_in, t_out):
    ft(f"#{sid}", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.01}, t_in)
    ft(f"#{sid} .iclip", {"clipPath": ISLAND}, {"clipPath": FULL, "duration": 0.24, "ease": "power2.in"}, t_in)
    ft(f"#{sid} .isl", {"autoAlpha": 1}, {"autoAlpha": 0, "duration": 0.12}, t_in + 0.1)
    tl.append(f'tl.fromTo("#{sid} .iclip", {{clipPath: "{FULL}"}}, {{clipPath: "{ISLAND}", duration: 0.2, ease: "power2.in", immediateRender: false}}, {t_out - 0.2:.3f});')
    tl.append(f'tl.fromTo("#{sid} .isl", {{autoAlpha: 0}}, {{autoAlpha: 1, duration: 0.08, immediateRender: false}}, {t_out - 0.1:.3f});')
    tl.append(f'tl.fromTo("#{sid}", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.01, immediateRender: false}}, {t_out:.3f});')
    sound("tech-digital-whoosh", t_in - 0.05, 0.10)
    sound("whoosh-1", t_out - 0.22, 0.05)


# ------------------------------------------------------------------ S1 scene 1: the home screen, badges land on the numbers
h0, h1 = UI["home"]
island("home", h0, h1)
APPS = [("🧭", "browser", "#E8F1FF", "32"), ("💬", "chats", "#E6F9EC", "11"), ("📝", "notes", "#FFF6D6", "3"), ("✉️", "mail", "#E8F1FF", None),
        ("📷", "camera", "#EEEEF0", None), ("🎵", "music", "#FFE8EC", None), ("🗺️", "maps", "#E6F9EC", None), ("📅", "calendar", "#FFFFFF", None),
        ("☀️", "weather", "#E3F2FF", None), ("⏱️", "clock", "#1C1C1E", None), ("🎧", "podcasts", "#F3E8FF", None), ("📚", "books", "#FFF0E0", None)]
app_html = []
for i, (ic, name, bg, badge) in enumerate(APPS):
    b = f'<b id="bd{i}" class="badge">{badge}</b>' if badge else ""
    app_html.append(f'<div class="app"><div class="ico" style="background:{bg}">{ic}{b}</div><span>{name}</span></div>')
    if badge:
        t = W(badge) - 0.05
        ft(f"#bd{i}", {"autoAlpha": 0, "scale": 0.3}, {"autoAlpha": 1, "scale": 1, "duration": 0.26, "ease": "back.out(2.4)"}, t)
        ft(f"#bd{i}", {"textContent": 0}, {"textContent": int(badge), "duration": 0.32, "ease": "power2.out", "snap": {"textContent": 1}}, t)
        sound("tech-notification-2" if badge != "11" else "ding-1", t, 0.09)
ft("#hhead", {"autoAlpha": 0, "y": 20, "filter": "blur(10px)"}, {"autoAlpha": 1, "y": 0, "filter": "blur(0px)", "duration": 0.26, "ease": "power3.out"}, h0 + 0.1)
ft("#hsum", {"autoAlpha": 0, "scale": 0.7}, {"autoAlpha": 1, "scale": 1, "duration": 0.26, "ease": "back.out(2)"}, W("drafts") - 0.03)
sound("tech-ui-confirm", W("drafts") - 0.03, 0.10)

# ------------------------------------------------------------------ S4 data: the attention battery beside the head
d0, d1 = W("and", 2) + 0.1, W("so") - 0.12
ft("#attn", {"autoAlpha": 0, "scale": 0.85}, {"autoAlpha": 1, "scale": 1, "duration": 0.28, "ease": "back.out(1.7)"}, d0)
sound("pop-2", d0, 0.07)
drain = round(W("attention", end=True) - W("promise", 2), 3)
ft("#battfill", {"scaleX": 1}, {"scaleX": 0.09, "duration": drain, "ease": "power1.in"}, W("promise", 2))
ft("#attnpct", {"textContent": 100}, {"textContent": 9, "duration": drain, "ease": "power1.in", "snap": {"textContent": 1}}, W("promise", 2))
ft("#battfill", {"backgroundColor": ACCENT}, {"backgroundColor": "#FF9F0A", "duration": 0.3}, W("little") - 0.1)
tl.append(f'tl.fromTo("#battfill", {{backgroundColor: "#FF9F0A"}}, {{backgroundColor: "#FF453A", duration: 0.3, immediateRender: false}}, {W("your") - 0.1:.3f});')
ft("#attnlab", {"autoAlpha": 0.45}, {"autoAlpha": 1, "duration": 0.2}, W("attention") - 0.03)
sound("tech-ui-error", W("attention") + 0.1, 0.06)
tl.append(f'tl.fromTo("#attn", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.15, immediateRender: false}}, {d1:.3f});')

# ------------------------------------------------------------------ S1 scene 2: the app switcher, every card but one flicks away
s0, s1 = UI["switch"]
island("switch", s0, s1)
CARDS = [("🧭", "browser", '<div class="tabs">' + "<i></i>" * 12 + "</div>"),
         ("💬", "chats", '<div class="bub l">see you at 6?</div><div class="bub r">running late</div><div class="bub l">ok</div>'),
         ("📝", "notes", '<div class="note1"><b>one thing</b><i></i><i></i><i class="short"></i></div>'),
         ("✉️", "mail", '<div class="mrow"></div><div class="mrow"></div><div class="mrow"></div><div class="mrow"></div>'),
         ("📄", "drafts", '<div class="doc"><i></i><i></i><i class="short"></i></div>')]
sw_html = []
for k, (ic, name, body) in enumerate(CARDS):
    sw_html.append(f'<div id="sw{k}" class="swc" style="left:{-330 + k * 310}px;z-index:{10 - abs(k - 2)}">'
                   f'<div class="swl"><span class="sico">{ic}</span>{name}</div><div class="swb">{body}</div></div>')
order = [0, 4, 1, 3]                                    # outer cards first
for j, k in enumerate(order):
    ft(f"#sw{k}", {"y": 0, "rotation": 0, "autoAlpha": 1}, {"y": -1500, "rotation": (-6 if k < 2 else 6), "autoAlpha": 0, "duration": 0.26, "ease": "power2.in"},
       W("everything") - 0.08 + j * 0.07)
sound("whoosh-3", W("everything") - 0.1, 0.06)
sound("whoosh-2", W("everything") + 0.1, 0.05)
ft("#sw2", {"scale": 1, "x": 0}, {"scale": 1.1, "x": 0, "duration": 0.3, "ease": "power3.out"}, W("else") - 0.06)
ft("#swpill", {"autoAlpha": 0, "y": 20}, {"autoAlpha": 1, "y": 0, "duration": 0.22, "ease": "back.out(2)"}, W("else") - 0.02)
sound("tech-ui-confirm", W("else") - 0.02, 0.09)

# ------------------------------------------------------------------ S1 scene 3: chest window, timer wheel to 25, notifications off
c0, c1 = CW
ft("#cwin", {"autoAlpha": 0, "y": 90, "scale": 0.94, "filter": "blur(8px)"}, {"autoAlpha": 1, "y": 0, "scale": 1, "filter": "blur(0px)", "duration": 0.26, "ease": "power3.out"}, c0)
tl.append(f'tl.fromTo("#cwin", {{autoAlpha: 1, y: 0}}, {{autoAlpha: 0, y: 60, duration: 0.16, ease: "power2.in", immediateRender: false}}, {c1 - 0.16:.3f});')
sound("pop-3", c0, 0.07)
ROW = 150
spin = round(W("25") + 0.08 - (c0 + 0.2), 3)
ft("#mincol", {"y": 0}, {"y": -25 * ROW, "duration": spin, "ease": "power3.out"}, c0 + 0.2)
for k in range(5):
    sound("tick-1", c0 + 0.25 + k * spin / 6, 0.06)
ft("#tstart", {"scale": 1}, {"scale": 0.92, "duration": 0.08, "yoyo": True, "repeat": 1}, W("minutes"))
ft("#tstart", {"backgroundColor": "rgba(255,255,255,0.14)", "color": "#ffffff"}, {"backgroundColor": ACCENT, "color": "#0B2E16", "duration": 0.12}, W("minutes"))
st("#tstart", {"textContent": "started"}, W("minutes") + 0.08)
st("#tstart", {"textContent": "start"}, 0)
sound("click-1", W("minutes"), 0.16)
ft("#tog", {"backgroundColor": ACCENT}, {"backgroundColor": "#48484A", "duration": 0.16}, W("off") - 0.04)
ft("#togk", {"x": 0}, {"x": -56, "duration": 0.16, "ease": "power2.out"}, W("off") - 0.04)
ft("#trow span", {"opacity": 1}, {"opacity": 0.5, "duration": 0.16}, W("off") - 0.04)
sound("tick-1", W("off") - 0.04, 0.12)

# ------------------------------------------------------------------ S1 scene 4: the checklist (the resolution)
l0, l1 = UI["list"]
island("list", l0, l1)
TEN = ["reply to the group chat", "read that long article", "clear the inbox", "second draft", "plan the week",
       "back up the photos", "learn the new chords", "sort the downloads", "fix the shelf", "call the bank back"]
ten_html = "".join(f'<div class="row s"><svg class="ring" viewBox="0 0 44 44"><circle cx="22" cy="22" r="18" class="rbg"/>'
                   f'<circle cx="22" cy="22" r="18" class="rfg" pathLength="1" stroke-dasharray="{0.18 + (k % 4) * 0.08:.2f} 1"/></svg><span>{t}</span></div>'
                   for k, t in enumerate(TEN))
ft("#chk", {"backgroundColor": "rgba(48,209,88,0)", "borderColor": "#C7C7CC"}, {"backgroundColor": ACCENT, "borderColor": ACCENT, "duration": 0.16}, W("finished") - 0.05)
ft("#chkp", {"strokeDashoffset": 1}, {"strokeDashoffset": 0, "duration": 0.22, "ease": "power2.out"}, W("finished"))
sound("tech-ui-confirm", W("finished") - 0.05, 0.12)
ft("#ten", {"autoAlpha": 0, "y": 40}, {"autoAlpha": 1, "y": 0, "duration": 0.26, "ease": "power3.out"}, W("ten|10") - 0.05)
sound("pop-1", W("ten|10") - 0.05, 0.07)
ft("#ten", {"opacity": 1}, {"opacity": 0.42, "duration": 0.25}, W("started") - 0.03)
ft("#lsum", {"autoAlpha": 0, "scale": 0.7}, {"autoAlpha": 1, "scale": 1, "duration": 0.24, "ease": "back.out(2)"}, W("started") - 0.03)
sound("tick-1", W("started") - 0.03, 0.08)

# ------------------------------------------------------------------ S5 signature word: the Markup pen writes "feeling"
p0, p1 = W("feeling") - 0.25, W("any") - 0.06               # the word is written as it is said, then holds under its sub-line
ft("#mkbar", {"autoAlpha": 0, "y": 220}, {"autoAlpha": 1, "y": 0, "duration": 0.24, "ease": "power3.out"}, p0 - 0.2)
tl.append(f'tl.fromTo("#mkbar", {{autoAlpha: 1, y: 0}}, {{autoAlpha: 0, y: 220, duration: 0.2, ease: "power2.in", immediateRender: false}}, {W("better") - 0.05:.3f});')
ft("#pen", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.05}, p0 - 0.02)
ft("#pen .pw", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": 0.6, "ease": "power1.inOut"}, p0)
ft("#pen .track", {"xPercent": -100, "y": 0}, {"xPercent": 0, "y": -10, "duration": 0.6, "ease": "power1.inOut"}, p0)   # the nib rides the wipe edge
tl.append(f'tl.fromTo("#pen .nib", {{autoAlpha: 1}}, {{autoAlpha: 0, duration: 0.15, immediateRender: false}}, {p0 + 0.6:.3f});')
ft("#pen .psub", {"autoAlpha": 0, "y": 16}, {"autoAlpha": 1, "y": 0, "duration": 0.25}, W("better") - 0.03)
tl.append(f'tl.fromTo("#pen", {{autoAlpha: 1}}, {{autoAlpha: 0, filter: "blur(10px)", duration: 0.15, immediateRender: false}}, {p1 - 0.08:.3f});')
sound("pencil-write", p0, 0.14)

# ------------------------------------------------------------------ audio: voice, one small sound per graphic entrance, a quiet bed


def need(src, dst):
    """copy a library file into the project (sound effects and music are fetched into the skill's library at setup)"""
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(S, src), dst)


audio = [f'<audio id="vo" src="assets/voice.wav" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-volume="1"></audio>']
lanes = []                                          # one track per sound at a time: the first free lane from 14
for i, (sid, at, vol) in enumerate(sorted(sfx, key=lambda s: s[1])):
    need(f"library/sfx/{sid}.wav", f"assets/sfx/{sid}.wav")
    dur = min(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"assets/sfx/{sid}.wav"],
                                   capture_output=True, text=True).stdout), TOTAL - at)
    k = next((j for j, e in enumerate(lanes) if e <= at), None)
    if k is None:
        k = len(lanes); lanes.append(0.0)
    lanes[k] = at + dur
    audio.append(f'<audio id="sfx{i}" src="assets/sfx/{sid}.wav" data-start="{at:.3f}" data-duration="{dur:.3f}" data-track-index="{30 + k}" data-volume="{vol}"></audio>')
need("library/music/vastness.mp3", "assets/music/bed.mp3")
bed = 0.10
lane = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": [{"t": 0, "v": 0}, {"t": 1.0, "v": bed}, {"t": TOTAL - 2.0, "v": bed}, {"t": TOTAL, "v": 0}]}]})
audio.append(f"<audio id=\"bed\" src=\"assets/music/bed.mp3\" data-start=\"0\" data-duration=\"{TOTAL}\" data-media-start=\"0\" data-track-index=\"20\" data-automation='{lane}'></audio>")
ft("#fadeout", {"autoAlpha": 0}, {"autoAlpha": 1, "duration": 0.6}, TOTAL - 0.6)

fonts_css = open("assets/fonts/fonts-local.css").read().replace("url(", "url(assets/fonts/")
BLUR = '<video id="{id}" class="blurbg" src="assets/wide.mp4" data-start="{a:.3f}" data-duration="{d:.3f}" data-media-start="{a:.3f}" data-track-index="{k}" muted playsinline></video>'
STATUS = '<div class="status"><span>7:40</span><span class="isig">●●● ▮</span></div>'
html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{fonts_css}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #000; font-family: Inter; }}
#cam {{ position: absolute; inset: 0; transform-origin: 50% 40%; }}
#cam video {{ position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; }}
#vw {{ opacity: 0; visibility: hidden; }}
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
.qt {{ position: absolute; left: 70px; right: 70px; top: 1420px; height: 104px; display: flex; gap: 10px; padding: 10px; box-sizing: border-box; opacity: 0;
      border-radius: 26px; background: rgba(60,60,67,.62); -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); }}
.qt span {{ flex: 1; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 42px; font-weight: 500; border-radius: 16px; letter-spacing: -0.02em; }}
.qt .fly {{ position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); color: #fff; font-size: 42px; font-weight: 600; pointer-events: none; }}
.ui {{ position: absolute; inset: 0; opacity: 0; }}
.iclip {{ position: absolute; inset: 0; overflow: hidden; clip-path: {ISLAND}; background: #000; }}
.iclip.white {{ background: #FAFAFA; color: #111; }}
.isl {{ position: absolute; left: 405px; top: 38px; width: 270px; height: 74px; border-radius: 37px; background: #000; }}
.blurbg {{ position: absolute; inset: -60px; width: 1200px; height: 2040px; object-fit: cover; filter: blur(36px) brightness(.5) saturate(1.2); }}
.status {{ position: absolute; left: 80px; right: 80px; top: 52px; display: flex; justify-content: space-between; font-size: 32px; font-weight: 600; color: #fff; }}
.white .status {{ color: #111; }}
.hhead {{ position: absolute; left: 0; right: 0; top: 250px; text-align: center; color: #fff; font-size: 92px; font-weight: 700; letter-spacing: -0.04em; opacity: 0; }}
.grid {{ position: absolute; left: 90px; right: 90px; top: 520px; display: grid; grid-template-columns: repeat(4, 1fr); row-gap: 64px; }}
.app {{ display: flex; flex-direction: column; align-items: center; gap: 14px; color: #fff; font-size: 26px; font-weight: 500; }}
.ico {{ position: relative; width: 170px; height: 170px; border-radius: 40px; display: flex; align-items: center; justify-content: center; font-size: 96px;
       box-shadow: 0 10px 30px rgba(0,0,0,.25); }}
.badge {{ position: absolute; right: -16px; top: -16px; min-width: 64px; height: 64px; padding: 0 14px; box-sizing: border-box; border-radius: 32px; background: #FF3B30;
         color: #fff; font-size: 36px; font-weight: 700; display: flex; align-items: center; justify-content: center; opacity: 0; box-shadow: 0 4px 12px rgba(0,0,0,.3); }}
.hsum {{ position: absolute; left: 0; right: 0; margin: 0 auto; width: fit-content; top: 1540px; white-space: nowrap; background: #fff; color: #111; font-size: 52px; font-weight: 500;
        letter-spacing: -0.03em; padding: 22px 48px; border-radius: 60px; opacity: 0; }}
.hsum b {{ font-weight: 800; }}
#attn {{ position: absolute; left: 760px; top: 430px; width: 260px; padding: 26px 0 22px; border-radius: 40px; background: rgba(30,30,32,.55); opacity: 0;
        -webkit-backdrop-filter: blur(18px); backdrop-filter: blur(18px); display: flex; flex-direction: column; align-items: center; gap: 12px; color: #fff; }}
.batt {{ position: relative; width: 170px; height: 78px; border: 5px solid rgba(255,255,255,.9); border-radius: 20px; padding: 6px; box-sizing: border-box; }}
.batt .cap {{ position: absolute; right: -16px; top: 22px; width: 9px; height: 24px; border-radius: 0 5px 5px 0; background: rgba(255,255,255,.9); }}
#battfill {{ width: 100%; height: 100%; border-radius: 10px; background: {ACCENT}; transform-origin: 0 50%; }}
#attnpct {{ font-size: 64px; font-weight: 700; letter-spacing: -0.03em; }}
#attnpct::after {{ content: "%"; font-weight: 300; }}
#attnlab {{ font-size: 34px; font-weight: 500; font-style: italic; opacity: .45; }}
.swc {{ position: absolute; top: 470px; width: 520px; height: 960px; }}
.swl {{ display: flex; align-items: center; gap: 14px; color: #fff; font-size: 32px; font-weight: 600; margin: 0 0 18px 10px; }}
.sico {{ width: 56px; height: 56px; border-radius: 14px; background: rgba(255,255,255,.9); display: flex; align-items: center; justify-content: center; font-size: 34px; }}
.swb {{ height: 880px; border-radius: 48px; background: #FAFAFA; box-shadow: 0 30px 70px rgba(0,0,0,.45); overflow: hidden; padding: 50px 40px; box-sizing: border-box; }}
.tabs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }}
.tabs i {{ height: 150px; border-radius: 18px; background: #E5E7EB; }}
.bub {{ display: table; font-size: 34px; padding: 16px 26px; border-radius: 30px; margin: 16px 0; background: #E9E9EB; color: #111; }}
.bub.r {{ margin-left: auto; background: #34C759; color: #fff; }}
.note1 b {{ display: block; font-size: 64px; font-weight: 800; letter-spacing: -0.04em; color: #111; margin: 20px 0 40px; }}
.note1 i, .doc i {{ display: block; height: 26px; border-radius: 13px; background: #E5E7EB; margin: 0 0 26px; }}
.note1 i.short, .doc i.short {{ width: 55%; }}
.mrow {{ height: 120px; border-bottom: 2px solid #E5E5EA; background: linear-gradient(90deg, #D1D5DB 0 36%, transparent 36%) 0 30px / 100% 22px no-repeat,
        linear-gradient(90deg, #E5E7EB 0 80%, transparent 80%) 0 70px / 100% 18px no-repeat; }}
#swpill {{ position: absolute; left: 0; right: 0; margin: 0 auto; width: fit-content; top: 1520px; background: {ACCENT}; color: #0B2E16; font-size: 48px; font-weight: 700;
          letter-spacing: -0.03em; padding: 18px 44px; border-radius: 50px; opacity: 0; white-space: nowrap; }}
#cwin {{ position: absolute; left: 60px; right: 60px; top: 1090px; height: 590px; border-radius: 44px; background: rgba(28,28,30,.78); opacity: 0;
        -webkit-backdrop-filter: blur(24px); backdrop-filter: blur(24px); box-shadow: 0 30px 80px rgba(0,0,0,.45); color: #fff; }}
.twl {{ position: absolute; left: 56px; top: 40px; font-size: 32px; font-weight: 600; color: rgba(255,255,255,.6); }}
.tdig {{ position: absolute; left: 0; right: 0; top: 96px; display: flex; justify-content: center; align-items: center; font-size: 150px; font-weight: 300;
        letter-spacing: -0.04em; font-variant-numeric: tabular-nums; line-height: {ROW}px; }}
.wcol {{ height: {ROW}px; overflow: hidden; -webkit-mask-image: linear-gradient(180deg, transparent, #000 25%, #000 75%, transparent); }}
.wcol div {{ height: {ROW}px; text-align: right; }}
#tstart {{ position: absolute; right: 56px; top: 290px; font-size: 38px; font-weight: 600; padding: 18px 40px; border-radius: 40px; background: rgba(255,255,255,.14); }}
#trow {{ position: absolute; left: 56px; right: 56px; bottom: 50px; height: 110px; border-top: 2px solid rgba(255,255,255,.12); display: flex; align-items: center;
        justify-content: space-between; font-size: 42px; font-weight: 500; }}
#tog {{ position: relative; width: 132px; height: 76px; border-radius: 38px; background: {ACCENT}; }}
#togk {{ position: absolute; right: 6px; top: 6px; width: 64px; height: 64px; border-radius: 50%; background: #fff; box-shadow: 0 3px 8px rgba(0,0,0,.25); }}
.lh {{ position: absolute; left: 80px; top: 200px; margin: 0; font-size: 110px; font-weight: 800; letter-spacing: -0.045em; }}
.lh span {{ display: block; font-size: 36px; font-weight: 500; letter-spacing: 0; color: #8E8E93; margin-bottom: 6px; }}
.row {{ display: flex; align-items: center; gap: 28px; font-size: 44px; letter-spacing: -0.02em; }}
.row.one {{ position: absolute; left: 80px; right: 80px; top: 470px; font-size: 64px; font-weight: 700; letter-spacing: -0.035em; }}
#chk {{ width: 74px; height: 74px; border-radius: 50%; border: 5px solid #C7C7CC; box-sizing: border-box; display: flex; align-items: center; justify-content: center; }}
#chk svg path {{ fill: none; stroke: #fff; stroke-width: 6; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 1 1; }}
#ten {{ position: absolute; left: 80px; right: 80px; top: 640px; display: flex; flex-direction: column; gap: 24px; opacity: 0; }}
.row.s {{ color: #3A3A3C; }}
.ring {{ width: 52px; height: 52px; transform: rotate(-90deg); }}
.rbg {{ fill: none; stroke: #E5E5EA; stroke-width: 6; }} .rfg {{ fill: none; stroke: #8E8E93; stroke-width: 6; stroke-linecap: round; }}
#lsum {{ position: absolute; left: 0; right: 0; margin: 0 auto; width: fit-content; top: 1660px; white-space: nowrap; font-size: 46px; font-weight: 600; letter-spacing: -0.03em;
        padding: 20px 44px; border-radius: 50px; background: #fff; box-shadow: 0 12px 40px rgba(0,0,0,.12); opacity: 0; }}
#lsum b {{ color: {ACCENT}; }} #lsum em {{ font-style: normal; color: #8E8E93; }}
#pen {{ position: absolute; left: 0; right: 0; top: 1060px; text-align: center; opacity: 0; }}
#pen .pwrap {{ position: relative; display: inline-block; }}
#pen .pw {{ font-family: "Marck Script"; font-size: 230px; color: #fff; line-height: 1.1; padding: 0 30px; text-shadow: 0 8px 50px rgba(0,0,0,.45); }}
#pen .psub {{ font-size: 50px; font-style: italic; font-weight: 300; color: #fff; margin-top: -6px; opacity: 0; text-shadow: 0 4px 30px rgba(0,0,0,.45); }}
#pen .track {{ position: absolute; left: 0; top: 150px; width: 100%; height: 0; }}
#pen .nib {{ position: absolute; right: 0; top: 0; width: 0; height: 0; }}
#pen .nib svg {{ position: absolute; left: -6px; top: -118px; filter: drop-shadow(0 6px 10px rgba(0,0,0,.35)); }}
#mkbar {{ position: absolute; left: 110px; right: 110px; top: 1600px; height: 150px; border-radius: 40px; background: rgba(250,250,250,.92); opacity: 0;
         display: flex; align-items: flex-end; justify-content: space-around; padding: 0 30px 0; box-sizing: border-box; overflow: hidden; }}
#mkbar .tool {{ width: 54px; height: 120px; border-radius: 12px 12px 0 0; background: #fff; box-shadow: 0 0 0 2px #E5E5EA inset; position: relative; }}
#mkbar .tool::before {{ content: ""; position: absolute; left: 13px; top: -2px; width: 28px; height: 30px; border-radius: 14px 14px 4px 4px; background: var(--tip); }}
#mkbar .tool.on {{ height: 140px; }}
#mkbar .sw {{ width: 66px; height: 66px; border-radius: 50%; background: conic-gradient(#FF453A, #FF9F0A, #FFD60A, {ACCENT}, #0A84FF, #BF5AF2, #FF453A); margin-bottom: 40px; }}
#fadeout {{ position: absolute; inset: 0; background: #000; opacity: 0; }}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{TOTAL}" data-fps="{FPS}">
 <div id="cam">
  <video id="vw" src="assets/wide.mp4" data-start="0" data-duration="{TOTAL}" data-track-index="0" muted playsinline></video>
  <video id="vt" src="assets/tight.mp4" data-start="0" data-duration="{TOTAL}" data-track-index="1" muted playsinline></video>
 </div>
 <div id="shade"></div>
 <div id="attn"><div class="batt"><div id="battfill"></div><i class="cap"></i></div><div id="attnpct">100</div><div id="attnlab">attention</div></div>
 {''.join(cap_html)}
 {''.join(figma_html)}
 {''.join(qt_html)}
 <div id="cwin"><div class="twl">timer</div>
  <div class="tdig"><div class="wcol"><div id="mincol">{''.join(f'<div>{m:02d}</div>' for m in range(26))}</div></div><span>:00</span></div>
  <div id="tstart">start</div>
  <div id="trow"><span>notifications</span><div id="tog"><i id="togk"></i></div></div>
 </div>
 <div id="pen"><div class="pwrap"><div class="pw">feeling</div>
  <div class="track"><div class="nib"><svg width="44" height="130" viewBox="0 0 44 130"><path d="M22 128 L8 92 L8 8 Q8 2 14 2 L30 2 Q36 2 36 8 L36 92 Z" fill="#fff" stroke="#D1D1D6" stroke-width="2"/><path d="M22 128 L14 108 L30 108 Z" fill="{ACCENT}"/></svg></div></div></div><div class="psub">is better than</div></div>
 <div id="mkbar"><div class="tool on" style="--tip:{ACCENT}"></div><div class="tool" style="--tip:#FFD60A"></div><div class="tool" style="--tip:#111"></div>
  <div class="tool" style="--tip:#F2F2F7"></div><div class="tool" style="--tip:#8E8E93"></div><div class="sw"></div></div>
 <div id="home" class="ui"><div class="iclip">{BLUR.format(id="vhome", a=h0, d=h1 - h0, k=2)}{STATUS}
  <div id="hhead" class="hhead">7:40 am</div>
  <div class="grid">{''.join(app_html)}</div>
  <div id="hsum" class="hsum"><b>46</b> things waiting</div></div><div class="isl"></div></div>
 <div id="switch" class="ui"><div class="iclip">{BLUR.format(id="vswitch", a=s0, d=s1 - s0, k=3)}{STATUS}
  {''.join(sw_html)}
  <div id="swpill">one thing</div></div><div class="isl"></div></div>
 <div id="list" class="ui"><div class="iclip white">{STATUS}
  <h2 class="lh"><span>reminders</span>today</h2>
  <div class="row one"><div id="chk"><svg width="40" height="40" viewBox="0 0 40 40"><path id="chkp" d="M9 21 L17 29 L31 12" pathLength="1"/></svg></div><span>the one thing</span></div>
  <div id="ten">{ten_html}</div>
  <div id="lsum"><b>1 finished</b> <em>· 10 started</em></div></div><div class="isl"></div></div>
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
print(f"index.html {TOTAL}s: {len(cards)} cards, {len(figma_html)} selections, {len(qt_html)} quicktype, {len(sfx)} sfx, {len(tl)} timeline lines")
for k, (a, b) in UI.items():
    print(f"  {k}: {a:.2f}-{b:.2f}")
print(f"  chest window: {CW[0]:.2f}-{CW[1]:.2f}; os time {sum(b - a for a, b in UI.values()) / TOTAL:.0%} of the reel")
