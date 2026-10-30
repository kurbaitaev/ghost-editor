#!/usr/bin/env python3
"""Kinetic doc, format B (a voice-over, designed pictures and pages): a worked example in English, "attention residue"
(~35 s), the voice over black-and-white "archive" stills. For reading and copying: the recording is yours, so re-time
every word ref against your own build/words.json.

    python3 b_voiceover.py <project>   # $P: assets/voice.wav, build/words.json, assets/pics/*.png (broll_gen.py stills
                                       # with the prompt prefix below, every one through broll_vision.py check)

The script it expects, word for word:
  You sit down for one task. Then the emails, the tabs, the messages. An hour later you feel more tired than when you
  started. There is a name for this. Attention residue. Part of your mind stays with the last task, and part of it
  waits for the next one. The old fix still works. 25 minutes, one task. A timer on the desk, and the work gets
  lighter, one step at a time. But the pressure stays, even with the phone face down. And here a closed door helps
  more than willpower, better than one more focus app. Mail, news, calls, games. Anything that lets you switch off
  the noise. Pick one block of time you can really protect. Sometimes, to get more done, you have to give one thing
  your whole attention.

Stills (Gemini, 4:3): "Black-and-white archival documentary photograph, 1960s, shot on film, natural light, real photo
(not an illustration), fine film grain, no people, no text, no logos, no watermark: <the object>". Objects, never people.

1. hook: an empty desk with one notebook as a print, pushing in; the one burst: an envelope, a row of open folders, a
   ringing telephone on "emails, tabs, messages";
2. a wall clock in a window on black; a red box MORE TIRED over it;
3. the term on warm paper: "there is a name for this / attention / residue" in the serif;
4. two polaroids on the grey page: a finished stack of papers "last", a blank page "next" (the camera slides);
5. a kitchen timer with 25 counting up in red, a tick per value; the desk again under LIGHTER / "one step at a time";
6. a pressure gauge (a punch-in on "pressure"), a phone lying face down on "face down";
7. the turn on the grey page: "and here a / CLOSED / DOOR / helps more than willpower", then a grid of app icons in a
   window, struck through in red on "app";
8. four polaroids, one per word: an envelope, a newspaper, a telephone, chess pieces;
9. a light switch flipping on "switch", an hourglass on "protect";
10. the payoff: the desk returns (the bookend), no sound effects, ATTENTION in red; hard end.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from kdoc import *  # noqa: E402,F403

P = sys.argv[1] if len(sys.argv) > 1 else "."
K = KineticDoc(P, fmt="B", fixes={"twenty-five": "25"},          # fixes: whisper's spellings -> the words on screen
               music={"id": "silent-descent", "db": -19, "duck": 0.0, "fade_in": 0.3, "fade_out": 0.5})
t = K.t
pic = lambda n: f"assets/pics/{n}.png"

# 1 · hook: the desk, then the one burst on the listed things
b0 = t("emails") - 0.04
K.picture("desk", pic("desk"), 0.0, b0, "You sit down for one task", frame="print", push=1.14, sfx=None)
K.burst("rush", [(pic("envelope"), b0), (pic("folders"), t("tabs") - 0.04), (pic("telephone"), t("messages") - 0.04, t("an") - 0.06)],
        "Then the emails, the tabs, the messages")

# 2 · an hour later: a window on black, the red box
s0 = t("an") - 0.06
K.picture("clock", pic("clock"), s0, t("there") - 0.06, "An hour later you feel more tired than when you started", frame="window")
K.label("tired", s0, t("there") - 0.06, "more tired", at=t("more tired"), host="clock", caps=False)

# 3 · the term on warm paper
K.page("term", t("there") - 0.06, t("part") - 0.06, "paper", [
    [("there", "there", "s"), ("is", "is", "s"), ("a", "a", "s"), ("name", "name", "s")],
    [("for", "for", "s"), ("this", "this", "s")],
    [("attention", "attention", "serif", 124)],
    [("residue", "residue", "serif", 124)]])

# 4 · the last task and the next one: two polaroids
p0 = t("part") - 0.06
K.polaroids("tasks", p0, t("the old") - 0.12, [(pic("papers"), "last", "last"), (pic("blank"), "next", "next")],
            "Part of your mind stays with the last task, and part of it waits for the next one")

# 5 · the old fix: 25 counting up on the timer, then the desk under the result
j0 = t("the old") - 0.12
K.picture("timer", pic("timer"), j0, t("a timer") - 0.06, "The old fix still works. 25 minutes, one task")
K.counter("n25", j0, t("a timer") - 0.06, 25, at=t("25"), dur=1.0, unit="minutes", y=560, host="timer", caps=False)
K.picture("desk2", pic("desk"), t("a timer") - 0.06, t("but") - 0.06, "A timer on the desk, and the work gets lighter, one step at a time")
K.label("light", t("lighter"), t("but") - 0.06, "lighter", at=t("lighter"), sub="one step at a time", sub_at=t("step"),
        host="desk2", caps=False)

# 6 · the pressure that stays: a gauge (punch-in on the word), then the phone face down
g0 = t("but") - 0.06
K.picture("gauge", pic("gauge"), g0, t("even") - 0.06, "But the pressure stays")
K.punch(t("pressure"), hold=0.8, scale=1.12, target="gauge")
K.picture("phone", pic("phone"), t("even") - 0.06, t("and here") - 0.06, "even with the phone face down")

# 7 · the turn on the grey page, then the app grid struck through
K.page("turn", t("and here") - 0.06, t("better") - 0.04, "grey", [
    [("and", "and here", "s"), ("here", "here", "s"), ("a", "a", "s")],
    [("closed", "closed", "big", 170)],
    [("door", "door", "red", 170)],
    [("helps", "helps", "s"), ("more", "more", "s"), ("than", "than", "s"), ("willpower", "willpower", "s")]])
K.picture("apps", pic("apps"), t("better") - 0.04, t("mail") - 0.04, "better than one more focus app", frame="window")
K.strike("apps-x", t("app"), y=700, host="apps")

# 8 · four polaroids, one per word
K.polaroids("feeds", t("mail") - 0.04, t("anything") - 0.06,
            [(pic("envelope"), "mail", "mail"), (pic("newspaper"), "news", "news"), (pic("telephone"), "calls", "calls"),
             (pic("chess"), "games", "games")], "Mail, news, calls, games", caps=False)

# 9 · the switch flips on "switch"; the hourglass
K.picture("switch", pic("switch"), t("anything") - 0.06, t("pick") - 0.06, "Anything that lets you switch off the noise")
K.swap("switch-off", "switch", pic("switch_off"), t("switch") + 0.1, "switch off the noise")
K.picture("hourglass", pic("hourglass"), t("pick") - 0.06, t("sometimes") - 0.06, "Pick one block of time you can really protect")

# 10 · the payoff: the desk again, nothing else
K.quiet(t("sometimes") - 0.1)
K.picture("desk3", pic("desk"), t("sometimes") - 0.06, K.T, "Sometimes, to get more done, you have to give one thing your whole attention",
          frame="print", push=1.05, sfx=None, tag="outro-bookend")
K.build(BIG={"task", "emails", "tabs", "messages", "tired", "last", "next", "minutes", "pressure", "down", "willpower",
             "app", "noise", "protect", "done", "attention#2"},
        RED={"attention#2"})
