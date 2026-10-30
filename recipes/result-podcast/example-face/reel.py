#!/usr/bin/env python3
"""Face RESULT worked example: "the doorway effect" (script.txt, about 42 s), an everyday-psychology talking head.

    python3 reel.py <project>      # $P: assets/plate.mp4 (the approved raw cut, video only, as shot), assets/voice.wav,
                                   # build/words.json (words of the cut, transcribe.py --lang en), build/face.json
                                   # (face_track.py on the plate)

Every component is new against the catalog (components.py plan --style result-podcast), each keyed to its spoken words:
- hook: a paper door is already beside the speaker on frame 1; it swings open on "kitchen" and a red "?" pops in the
  empty doorway on "forget" (hook-door-swing-open)
- "You just stand there, staring at the fridge" -> a paper fridge on the other side, magnet letters W / H / Y / ? land
  one per word (fridge-magnet-letters)
- "Your memory is fine. Blame the door." -> a ticket beside the speaker: "memory: fine" written on "fine", THE DOOR
  stamped under "culprit" on "door", with a punch-in on "blame" (ticket-fine-culprit-stamp)
- "Psychologists call it the doorway effect" -> on the chest, an embossed label tape prints DOORWAY EFFECT letter by
  letter as it is said (label-tape-print)
- "Your brain saves the day in scenes, like a film" -> a film slate beside the speaker: "your brain", "today", scene 1
  chalked on their words, the clapper claps on "film"; on "doorway" the 1 is struck through and a 2 chalked
  (clapper-slate-scene-count)
- "new scene, file the old one away" -> full screen (2.44 s, wiped in): "new scene" written, an index card "scene 1:
  the plan" drops into an OLD SCENES drawer that shuts on "away"; it also hides the look-away (file-drawer-shut)
- "In experiments, people forgot more ... in one room" -> a graph-paper card in the top band: "who forgot more?", a
  red bar for "through a door" grows on "door", a short blue one for "in one room" on "room" (graph-paper-bars)
- "say the task out loud: scissors, scissors, scissors" -> on the chest, a paper megaphone, the words of the tip, three
  "scissors" growing one per word, with a punch-in on "out loud" (paper-megaphone-echo)
- outro: the door comes back open, a paper pair of scissors walks through it on "walks through", the door shuts on
  "close", then a doorstop wedge props it open on "don't" and "plans" is written inside (door-wedge-outro)
No stock or AI pictures (0 inserts): every prop is drawn in the composition. Punch-ins on "blame" and "out loud".
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from faceresult import FaceResult, INK, RED, BLUE, GOLD, KRAFT, PAPER  # noqa: E402

P = sys.argv[1] if len(sys.argv) > 1 else "."
R = FaceResult(P, fixes={},                         # whisper's misspellings in YOUR cut: {"heard": "said"}
               cover=[(17.55, 18.35)],              # the look-aways of YOUR cut: leave cover out to read build/cover_windows.json
               music={"id": "lo-fi-02", "db": -22})
t = R.t
GREEN = "#2F8F4E"

# punch-ins first, so every prop's zone is measured with the face as it sits under them
R.punch(t("blame") - 0.03, hold=0.8)
R.punch(t("out loud") - 0.03, hold=0.75)


def door(p, sign, beyond):
    """a paper doorway: tiles and a floor beyond, a cream leaf hinged on its left edge (rotationY > 0 opens it inward)"""
    return f'''<div class="dfr"><div class="dby"><i class="dflr"></i>{beyond}</div>
  <div class="d3d"><div id="{p}leaf" class="dleaf"><i class="dpn dp1"></i><i class="dpn dp2"></i><i class="dknob"></i>
    <div class="hand dsign">{sign}</div></div></div></div>'''


# ---------------------------------------------------------------- 1. hook: the door swings open on an empty doorway
a, b = 0.0, t("you just") - 0.2
R.prop("hook", a, b, "right", door("h", "kitchen", '<div id="hq" class="hand dq">?</div>'), w=270, h=470, dy=10,
       what="paper door, already there on frame 1: opens on «kitchen», a red «?» pops in the doorway on «forget»", rot=-2,
       enter="none", cls="fr-door-hook")
R.ft("#hleaf", {"rotationY": 0, "transformOrigin": "0% 50%"}, {"rotationY": 80, "duration": 0.5, "ease": "power2.inOut"},
     t("kitchen") - 0.06)
R.sound("whoosh-cine", t("kitchen") - 0.08, "door swings open")
R.pop("#hq", t("forget"), rot=-6, snd="pop-1", scale=2.0)
R.tween("#hq", {"rotation": -6}, {"rotation": 8, "duration": 0.12, "ease": "sine.inOut", "yoyo": True, "repeat": 3}, t("why"))

# ---------------------------------------------------------------- 2. the fridge: W / H / Y / ? one per word
a, b = t("you just") - 0.1, t("your memory") - 0.15
MAG = [("W", "stand", RED, 26, 186, -8), ("H", "there", BLUE, 112, 204, 6), ("Y", "staring", GOLD, 30, 300, 4),
       ("?", "fridge", GREEN, 128, 316, -10)]
mags = "".join(f'<b id="mg{k}" class="mag" style="left:{x}px;top:{y}px;background:{c}">{ch}</b>'
               for k, (ch, w, c, x, y, r) in enumerate(MAG))
R.prop("fridge", a, b, "left", f'''<div class="frg"><div class="frz"><div class="frn hand">eggs<br>milk</div><i class="fh fh1"></i></div>
  <i class="fh fh2"></i>{mags}</div>''', w=270, h=460, dy=30,
       what="paper fridge: magnet letters W / H / Y / ? land one per word, the last on «fridge»", rot=3, enter="slap",
       sfx=None, cls="fr-fridge-magnets")
for k, (ch, w, c, x, y, r) in enumerate(MAG):
    R.pop(f"#mg{k}", t(w) - 0.03, rot=r, scale=1.8)

# ---------------------------------------------------------------- 3. the ticket: memory fine, culprit the door
a, b = t("your memory") - 0.1, t("psychologists") - 0.2
R.prop("tkt", a, b, "right", '''<div class="tkt"><div class="tkh">TICKET</div><div class="mono tkn">No. 0412</div>
  <div class="mono tkl" style="top:142px">MEMORY</div><div id="tkf" class="hand tkv" style="top:172px">fine ✓</div>
  <div class="mono tkl" style="top:262px">CULPRIT</div><div id="tks" class="stamp tkst">THE DOOR</div><i class="tkbc"></i></div>''',
       w=270, h=440, dy=20, what="ticket: «memory: fine ✓» on «fine», THE DOOR stamped under «culprit» on «door»", rot=-3,
       enter="toss", sfx=None, cls="fr-ticket-fine")
R.write("#tkf", t("fine") - 0.04, 0.4)
R.stamp("#tks", t("door") - 0.08, rot=-8)

# ---------------------------------------------------------------- 4. the term, printed on label tape (chest)
a, b = t("psychologists") - 0.1, t("^effect") + 0.8         # the finished term holds a beat
TERM = "DOORWAY EFFECT"
lead = R.words_in("lw", "psychologists call it the", t("psychologists") - 0.04, t("doorway") - 0.1)
letters = "".join('<span class="ltsp"></span>' if ch == " " else f'<span id="lt{k}" class="ltc">{ch}</span>'
                  for k, ch in enumerate(TERM))
R.prop("label", a, b, "chest", f'''<div class="lbl"><div class="lbh">{lead}</div>
  <i class="ltrk"></i><div id="ltp" class="ltp">{letters}</div></div>''', w=900, h=230, dy=6,
       what="label tape on the chest: DOORWAY EFFECT printed letter by letter as it is said", rot=-1, enter="fade",
       sfx=None, cls="fr-label-tape")
t0, t1 = t("doorway") - 0.05, t("^effect") - 0.1
R.ft("#ltp", {"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)", "duration": round(t1 - t0 + 0.1, 3),
                                                     "ease": "none"}, t0)
for k, ch in enumerate(TERM):
    if ch != " ":
        R.show(f"#lt{k}", t0 + (t1 - t0) * k / len(TERM), 0.05)
R.sound("typing-1", t0, "label printer", maxlen=1.0, db=-2)

# ---------------------------------------------------------------- 5. the slate: the day in scenes, clapped on "film"
a, b = t("your brain") - 0.1, t("new") + 0.2           # leaves under the drawer card's wipe
R.prop("slate", a, b, "left", '''<div class="clap"><div class="clbar"></div><div id="clt" class="clt"></div>
  <div class="clbd"><div class="mono cll" style="left:18px;top:14px">DAY</div><div class="mono cll" style="left:150px;top:14px">SCENE</div>
    <div id="cday" class="hand clv" style="left:12px;top:40px">today</div>
    <div class="clsn"><span class="cnum"><b id="cs1" class="hand cln">1</b><i id="csx" class="csx"></i></span><b id="cs2" class="hand cln">2</b></div>
    <i class="clhr"></i><div class="mono cll" style="left:18px;top:168px">PROD.</div>
    <div id="cbr" class="hand clv" style="left:12px;top:192px">your brain</div></div></div>''',
       w=270, h=400, dy=30, what="film slate: «your brain», «today», scene 1 chalked; claps on «film»; 1 struck, 2 on «doorway»",
       rot=2, enter="swing", sfx=None, cls="fr-clapper-slate")
R.ft("#clt", {"rotation": -24, "transformOrigin": "2% 100%"}, {"rotation": 0, "duration": 0.09, "ease": "power4.in"}, t("film") - 0.1)
R.sound("wood-hit", t("film") - 0.02, "clapper claps", db=2)
R.write("#cbr", t("brain") - 0.04, 0.4)
R.write("#cday", t("day") - 0.04, 0.3)
R.write("#cs1", t("scenes") - 0.04, 0.25)
R.ft("#csx", {"scaleX": 0, "rotation": -60}, {"scaleX": 1, "rotation": -60, "duration": 0.2, "ease": "power2.out"}, t("doorway tells") - 0.04)
R.write("#cs2", t("tells") - 0.02, 0.25)

# ---------------------------------------------------------------- 6. full screen: file the old scene away
a, b = t("new") - 0.12, t("^away")                     # 2.44 s; fully in from a + 0.24 to b - 0.22 (the look-away: 17.55-18.35)
R.scene("drawer", a, b, "kraft", '''<div id="fdh" class="hand fdh">new scene</div>
  <div class="fdbk"></div><div id="fdc" class="fdc"><div class="mono fdk">SCENE 1</div><div class="hand fdp">the plan</div></div>
  <div id="fdd" class="fdd"><div class="mono fdl">OLD SCENES</div><i class="fdhd"></i></div>''',
        what="«new scene» written; an index card «scene 1: the plan» drops into an OLD SCENES drawer that shuts on «away» "
             "(hides the look-away 17.55-18.35)", enter="wipe", cls="fr-file-drawer")
R.write("#fdh", t("new") - 0.02, 0.45)
R.ft("#fdc", {"y": 0, "rotation": -3}, {"y": 470, "rotation": 1, "duration": 0.42, "ease": "power2.in"}, t("file") - 0.02)
R.tween("#fdd", {"y": 0, "scale": 1}, {"y": -16, "scale": 0.95, "duration": 0.14, "ease": "power3.in"}, t("away") - 0.06)
R.sound("impact-2", t("away") + 0.06, "drawer shuts", db=-4, maxlen=0.6)

# ---------------------------------------------------------------- 7. the experiment: graph paper in the top band
a, b = t("in experiments") - 0.1, t("^room") + 0.4
R.prop("graph", a, b, "top", f'''<div class="gp"><div id="gph" class="gph">EXPERIMENT</div><div id="gpq" class="hand gpq">who forgot more?</div>
  <div class="gpr" style="top:92px"><div id="gl0" class="hand gpl">through a door</div><div class="gtr"><i id="gb0" class="gbr" style="width:430px;background:{RED}"></i></div></div>
  <div class="gpr" style="top:200px"><div id="gl1" class="hand gpl">in one room</div><div class="gtr"><i id="gb1" class="gbr" style="width:190px;background:{BLUE}"></i></div></div></div>''',
       w=900, h=320, what="graph paper: «who forgot more?», a long red bar for «through a door», a short blue one for «in one room»",
       rot=0.8, enter="unfold", cls="fr-graph-bars")
R.pop("#gph", t("experiments") - 0.03, rot=-3)
R.write("#gpq", t("forgot") - 0.04, 0.5)
R.write("#gl0", t("through") - 0.04, 0.45)
R.ft("#gb0", {"scaleX": 0, "transformOrigin": "0% 50%"}, {"scaleX": 1, "duration": 0.45, "ease": "power3.out"}, t("door", after=25) - 0.04)
R.sound("tick-1", t("door", after=25), "red bar grows")
R.write("#gl1", t("same") - 0.04, 0.45)
R.ft("#gb1", {"scaleX": 0, "transformOrigin": "0% 50%"}, {"scaleX": 1, "duration": 0.35, "ease": "power3.out"}, t("one room") - 0.04)

# ---------------------------------------------------------------- 8. the tip: say it out loud (chest)
a, b = t("say") - 0.1, t("^scissors#3") + 0.3
tip = R.words_in("mw", "say the task out loud:", t("say") - 0.04, t("^loud") - 0.1)
ECHO = [(236, 78, 64, "scissors,"), (376, 138, 74, "scissors,"), (530, 196, 86, "scissors!")]
echo = "".join(f'<div id="ms{k}" class="hand msw" style="left:{x}px;top:{y}px;font-size:{fs}px">{w}</div>'
               for k, (x, y, fs, w) in enumerate(ECHO))
R.prop("mega", a, b, "chest", f'''<div class="mgp"><svg class="mgc" viewBox="0 0 200 200">
    <path d="M30 78 L168 18 L168 182 L30 122 Z" class="mgb"/><rect x="6" y="76" width="30" height="48" rx="7" class="mgm"/>
    <path d="M168 18 L168 182" class="mgr"/></svg>
  <svg class="ink" viewBox="0 0 70 200" style="left:160px;top:56px;width:62px;height:178px">
    <path id="mga0" d="M10 76 Q26 100 10 124" pathLength="1"/><path id="mga1" d="M28 56 Q54 100 28 144" pathLength="1"/>
    <path id="mga2" d="M46 36 Q82 100 46 164" pathLength="1"/></svg>
  <div class="mgh">{tip}</div>{echo}</div>''', w=900, h=290, dy=4,
       what="paper megaphone on the chest: the tip word by word, three «scissors» growing one per word", rot=-0.8, enter="fade",
       sfx=None, cls="fr-paper-megaphone")
for k in range(3):
    at = t(f"scissors#{k + 1}") - 0.03
    R.pop(f"#ms{k}", at, rot=(-4, 2, -3)[k], snd="pop-3" if k == 2 else None, scale=1.5)
    R.draw(f"#mga{k}", at, 0.2)

# ---------------------------------------------------------------- 9. outro: the plan walks through, the door shuts, a wedge keeps it open
SCIS = f'''<svg id="osc" class="osc" viewBox="0 0 120 130"><path d="M54 74 L98 8 L108 15 L64 80 Z" class="bl"/>
  <path d="M66 74 L22 8 L12 15 L56 80 Z" class="bl"/><circle cx="42" cy="104" r="17" class="hl"/><circle cx="78" cy="104" r="17" class="hl"/>
  <circle cx="60" cy="77" r="5" fill="{INK}"/></svg><div id="opl" class="hand opl">plans ✓</div>'''
a = t("now") - 0.1
R.prop("outro", a, None, "right", door("o", "next room", SCIS) + f'<svg id="owg" class="owg" viewBox="0 0 140 56"><path d="M2 54 L138 54 L138 6 Z" fill="{GOLD}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/></svg>', w=270, h=470, dy=10,
       what="the door again: paper scissors walk through on «walks through», it shuts on «close», a wedge props it open on «don't», "
            "«plans ✓» written inside", rot=2, enter="slap", sfx="whoosh-2", nocap=(t("plans") - 0.08, R.T), cls="fr-door-wedge")
R.st("#oleaf", {"rotationY": 80, "transformOrigin": "0% 50%"}, 0)
R.ft("#osc", {"x": 0, "y": 0, "scale": 1}, {"x": 66, "y": -60, "scale": 0.7, "duration": 0.7, "ease": "power1.inOut"}, t("walks") - 0.04)
R.tween("#oleaf", {"rotationY": 80}, {"rotationY": 0, "duration": 0.22, "ease": "power3.in"}, t("close") - 0.2)
R.sound("wood-hit", t("close") + 0.01, "door shuts", db=2)
R.ft("#owg", {"autoAlpha": 0, "x": -70}, {"autoAlpha": 1, "x": 0, "duration": 0.22, "ease": "power3.out"}, t("don't") - 0.05)
R.tween("#oleaf", {"rotationY": 0}, {"rotationY": 80, "duration": 0.35, "ease": "power2.out"}, t("don't") + 0.08)
R.write("#opl", t("plans") - 0.04, 0.5, snd="pencil-write")

BIG = {"kitchen", "fridge", "fine", "door", "film", "plan", "file", "experiments", "more", "room", "go"}
SCRIPT = {"forget", "distance", "scenes"}
css = f"""
/* 1 + 9 the paper doorway (270 x 470) */
.dfr {{ position: absolute; inset: 0; background: #6B4A2E; border-radius: 10px 10px 2px 2px; box-shadow: 0 20px 44px rgba(0,0,0,.5); }}
.dby {{ position: absolute; left: 18px; right: 18px; top: 18px; bottom: 0; overflow: hidden;
  background: linear-gradient(90deg, rgba(60,80,90,.16) 2px, transparent 2px) 0 0 / 39px 39px,
              linear-gradient(rgba(60,80,90,.16) 2px, transparent 2px) 0 0 / 39px 39px, #E4EEEF; }}
.dflr {{ position: absolute; left: 0; right: 0; bottom: 0; height: 24%; background: repeating-conic-gradient(#2E2B28 0 25%, #F1EBDD 0 50%) 0 0 / 46px 46px; }}
.d3d {{ position: absolute; left: 18px; right: 18px; top: 18px; bottom: 0; perspective: 1400px; }}
.dleaf {{ position: absolute; inset: 0; background: #EFE4CC; border: 4px solid #8A6A48; box-sizing: border-box; backface-visibility: hidden;
  box-shadow: inset -10px 0 18px rgba(0,0,0,.12); }}
.dpn {{ position: absolute; left: 24px; right: 24px; border: 4px solid rgba(138,106,72,.5); border-radius: 6px; }}
.dp1 {{ top: 28px; height: 150px; }} .dp2 {{ top: 212px; height: 196px; }}
.dknob {{ position: absolute; right: 18px; top: 220px; width: 26px; height: 26px; border-radius: 50%; background: {GOLD}; box-shadow: 0 3px 5px rgba(0,0,0,.35); }}
.dsign {{ position: absolute; left: 0; right: 0; top: 72px; text-align: center; font-size: 52px; color: {INK}; transform: rotate(-4deg); }}
.dq {{ position: absolute; left: 60px; top: 30px; font-size: 250px; line-height: 1; color: {RED}; opacity: 0; padding: 0 8px; }}
.osc {{ position: absolute; left: 30px; top: 250px; width: 110px; height: 120px; overflow: visible; }}
.osc .bl {{ fill: #CDD3DA; stroke: {INK}; stroke-width: 4; stroke-linejoin: round; }}
.osc .hl {{ fill: none; stroke: {RED}; stroke-width: 9; }}
.opl {{ position: absolute; right: 6px; top: 36px; font-size: 58px; line-height: 1; color: {BLUE}; padding: 0 6px; white-space: nowrap; }}
.owg {{ position: absolute; left: 30px; bottom: 0; width: 140px; height: 56px; overflow: visible; opacity: 0; visibility: hidden; }}
/* 2 the fridge (270 x 460) */
.frg {{ position: absolute; inset: 0; background: linear-gradient(90deg, #F8F5EE, #E6E0D2); border: 4px solid #D3CCBC; border-radius: 28px;
  box-sizing: border-box; box-shadow: 0 20px 44px rgba(0,0,0,.5); }}
.frz {{ position: absolute; left: 0; right: 0; top: 0; height: 150px; border-bottom: 6px solid #CFC7B5; }}
.frn {{ position: absolute; left: 26px; top: 26px; width: 110px; height: 96px; background: #FFE680; font-size: 38px; line-height: .95; color: {INK};
  text-align: center; padding-top: 6px; box-sizing: border-box; transform: rotate(-5deg); box-shadow: 0 4px 8px rgba(0,0,0,.25); }}
.fh {{ position: absolute; right: 18px; width: 14px; border-radius: 7px; background: #B7AF9D; }}
.fh1 {{ top: 40px; height: 70px; }} .fh2 {{ top: 186px; height: 130px; }}
.mag {{ position: absolute; width: 80px; height: 92px; border-radius: 14px; font-family: Oswald; font-weight: 700; font-size: 70px; line-height: 92px;
  color: #FFFDF8; text-align: center; box-shadow: 0 6px 10px rgba(0,0,0,.35); opacity: 0; }}
/* 3 the ticket (270 x 440) */
.tkt {{ position: absolute; inset: 0; background: #FFF6DC; border-radius: 6px; box-shadow: 0 18px 40px rgba(0,0,0,.45); }}
.tkh {{ position: absolute; left: 0; right: 0; top: 0; height: 84px; background: {RED}; color: {PAPER}; border-radius: 6px 6px 0 0;
  font-family: Oswald; font-weight: 700; font-size: 56px; letter-spacing: 6px; line-height: 84px; text-align: center; }}
.tkn {{ position: absolute; left: 0; right: 0; top: 96px; text-align: center; font-size: 26px; color: #7A6440; }}
.tkl {{ position: absolute; left: 22px; font-size: 30px; font-weight: 700; color: #7A6440; }}
.tkv {{ position: absolute; left: 16px; font-size: 72px; line-height: 1; color: {BLUE}; padding: 0 6px; white-space: nowrap; }}
.tkst {{ left: 20px; top: 300px; font-size: 38px; }}
.tkbc {{ position: absolute; left: 22px; right: 22px; bottom: 18px; height: 40px; opacity: .75;
  background: repeating-linear-gradient(90deg, {INK} 0 3px, transparent 3px 6px, {INK} 6px 10px, transparent 10px 13px); }}
/* 4 the label tape (chest, 900 x 230) */
.lbl {{ position: absolute; inset: 0; background: {PAPER}; border-radius: 10px; box-shadow: 0 22px 50px rgba(0,0,0,.5); }}
.lbh {{ position: absolute; left: 40px; top: 14px; font-family: "Inter Tight"; font-weight: 800; font-size: 46px; letter-spacing: -1px; color: {INK}; white-space: nowrap; }}
.ltrk {{ position: absolute; left: 40px; right: 40px; top: 84px; height: 120px; border: 4px dashed #CDBF9F; border-radius: 8px; box-sizing: border-box; }}
.ltp {{ position: absolute; left: 40px; right: 40px; top: 84px; height: 120px; background: {RED}; border-radius: 8px; display: flex;
  align-items: center; padding-left: 44px; box-sizing: border-box; box-shadow: 0 6px 12px rgba(0,0,0,.3); }}
.ltc {{ font-family: Oswald; font-weight: 700; font-size: 92px; letter-spacing: 6px; color: #FFFDF8; opacity: 0;
  text-shadow: 0 2px 0 rgba(0,0,0,.28), 0 -1px 0 rgba(255,255,255,.35); }}
.ltsp {{ display: inline-block; width: 34px; }}
/* 5 the slate (270 x 400) */
.clap {{ position: absolute; inset: 0; filter: drop-shadow(0 18px 30px rgba(0,0,0,.5)); }}
.clt, .clbar {{ position: absolute; left: 0; width: 270px; height: 44px; border-radius: 4px;
  background: repeating-linear-gradient(-45deg, #F4F0E6 0 22px, #1F1F1F 22px 44px); }}
.clt {{ top: 8px; }} .clbar {{ top: 56px; }}
.clbd {{ position: absolute; left: 0; right: 0; top: 102px; bottom: 0; background: #262626; border-radius: 0 0 10px 10px; }}
.cll {{ position: absolute; font-size: 26px; color: #CFC8B6; }}
.clv {{ position: absolute; font-size: 54px; line-height: 1.1; color: #F4F0E6; padding: 0 6px; white-space: nowrap; }}
.clsn {{ position: absolute; left: 138px; top: 34px; display: flex; gap: 8px; align-items: flex-start; }}
.cnum {{ position: relative; display: inline-block; }}
.cln {{ display: inline-block; font-size: 100px; line-height: 1; font-weight: 700; color: #F4F0E6; padding: 0 6px; }}
.csx {{ position: absolute; left: 2px; right: -22px; top: 54%; height: 10px; margin-top: -5px; border-radius: 5px; background: #F2C94C; }}
.clhr {{ position: absolute; left: 12px; right: 12px; top: 152px; height: 3px; background: rgba(244,240,230,.45); }}
/* 6 the drawer (full screen, kraft) */
.fdh {{ position: absolute; left: 50%; top: 270px; transform: translateX(-50%) rotate(-3deg); font-size: 210px; line-height: 1; color: {PAPER};
  white-space: nowrap; padding: 0 12px; text-shadow: 0 4px 14px rgba(0,0,0,.3); }}
.fdbk {{ position: absolute; left: 150px; width: 780px; top: 1000px; height: 520px; background: #474D3E; border-radius: 18px; }}
.fdc {{ position: absolute; left: 260px; width: 560px; top: 620px; height: 330px; padding: 30px 40px; box-sizing: border-box; border-radius: 10px;
  background: {PAPER} repeating-linear-gradient({PAPER} 0 78px, #B9CDE8 78px 80px); box-shadow: 0 24px 50px rgba(0,0,0,.4); color: {INK}; }}
.fdk {{ font-size: 36px; color: #5A4320; border-bottom: 4px solid {RED}; padding-bottom: 10px; }}
.fdp {{ font-size: 120px; line-height: 1.2; color: {BLUE}; }}
.fdd {{ position: absolute; left: 180px; width: 720px; top: 1060px; height: 400px; border-radius: 16px; background: linear-gradient(#7C846F, #636A57);
  box-shadow: 0 30px 60px rgba(0,0,0,.45), inset 0 4px 0 rgba(255,255,255,.18); }}
.fdl {{ position: absolute; left: 50%; top: 70px; width: 380px; margin-left: -190px; height: 92px; box-sizing: border-box; background: #F4EEDF;
  border: 6px solid #3E4336; border-radius: 6px; font-size: 40px; line-height: 80px; text-align: center; color: {INK}; }}
.fdhd {{ position: absolute; left: 50%; top: 214px; width: 240px; margin-left: -120px; height: 46px; border-radius: 23px; background: #3E4336;
  box-shadow: inset 0 -6px 0 rgba(0,0,0,.3); }}
/* 7 the graph paper (top band, 900 x 320) */
.gp {{ position: absolute; inset: 0; border-radius: 8px; box-shadow: 0 20px 44px rgba(0,0,0,.45);
  background: linear-gradient(rgba(31,59,140,.12) 1px, transparent 1px) 0 0 / 24px 24px,
              linear-gradient(90deg, rgba(31,59,140,.12) 1px, transparent 1px) 0 0 / 24px 24px, {PAPER}; }}
.gph {{ position: absolute; left: 24px; top: 16px; padding: 4px 14px; border: 5px solid {INK}; font-family: Oswald; font-weight: 700; font-size: 40px;
  letter-spacing: 4px; line-height: 1; color: {INK}; opacity: 0; }}
.gpq {{ position: absolute; right: 30px; top: 6px; font-size: 62px; line-height: 1; color: {RED}; padding: 0 6px; white-space: nowrap; }}
.gpr {{ position: absolute; left: 30px; right: 30px; height: 96px; display: flex; align-items: center; }}
.gpl {{ flex: none; width: 330px; font-size: 56px; line-height: 1; color: {INK}; padding: 0 6px; white-space: nowrap; box-sizing: border-box; }}
.gtr {{ position: relative; flex: 1; height: 72px; border-left: 4px solid {INK}; }}
.gbr {{ position: absolute; left: 0; top: 10px; height: 52px; border-radius: 0 8px 8px 0; display: block; }}
/* 8 the megaphone (chest, 900 x 250) */
.mgp {{ position: absolute; inset: 0; background: {PAPER}; border-radius: 10px; box-shadow: 0 22px 50px rgba(0,0,0,.5); }}
.mgc {{ position: absolute; left: 10px; top: 60px; width: 160px; height: 160px; overflow: visible; }}
.mgb {{ fill: {KRAFT}; stroke: {INK}; stroke-width: 6; stroke-linejoin: round; }}
.mgm {{ fill: {INK}; }} .mgr {{ stroke: #7A5A34; stroke-width: 10; }}
#mga0, #mga1, #mga2 {{ stroke: {RED}; stroke-width: 7; }}
.mgh {{ position: absolute; left: 240px; top: 14px; font-family: "Inter Tight"; font-weight: 800; font-size: 44px; letter-spacing: -1px; color: {INK}; white-space: nowrap; }}
.msw {{ position: absolute; line-height: 1; color: {BLUE}; padding: 0 6px; white-space: nowrap; opacity: 0; }}
"""
R.build(BIG=BIG, SCRIPT=SCRIPT, css=css)
