#!/usr/bin/env python3
"""Kinetic doc, format A (a talking head): a worked example in English, "the two-minute rule" (~30 s). For reading
and copying: the recording is yours, so re-time every word ref against your own build/words.json.

    python3 a_talking_head.py <project>   # $P: assets/plate.mp4 (the WIDE plate as shot), assets/voice.wav,
                                          # build/words.json (words of the cut), build/face.json (face_track.py on the plate),
                                          # build/cover_windows.json (look-aways to hide; [] when there are none),
                                          # assets/pics/tray.png (an AI still of an office in-tray; broll_vision checked)

The script it expects, word for word:
  Most of your to-do list is not hard. It is small. Small tasks you keep moving to tomorrow. And every time you move
  one, your energy just disappears. There is a rule for this in Getting Things Done. If it takes less than two
  minutes, do it now. Reply to the message. Book the appointment. It is done, and you never think about it again. The
  list is not long. It is old. Most days you are not tired from the work. You are tired from carrying it. Start with
  two minutes.

Frame 1: the speaker's face, the plate pushing in, "most of your to-do list" popping on word by word, HARD big.
1. the turn of the hook on a grey page: "small tasks you keep / MOVING / TO TOMORROW", a black block running ahead of
   every word (it would also hide a look-away there);
2. the face: "your ENERGY just disappears", the big word losing its letters on "disappears";
3. the one picture: an office in-tray as a print on its own blurred copy, "Getting Things Done" in the serif;
4. the face: NOW (a snap punch-in), a red label DONE + "you never think about it again";
5. the turn line on a grey page: "the list is not / LONG / it is / OLD" (red);
6. "tired from CARRYING it" with a punch-in that comes too close;
7. the payoff on the face, no sound effects, TWO MINUTES in red; hard end.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from kdoc import *  # noqa: E402,F403

P = sys.argv[1] if len(sys.argv) > 1 else "."
# fixes: whisper's spellings -> the words on screen (captions are lower case: titles are set here)
K = KineticDoc(P, fmt="A", fixes={"todo": "to-do", "getting": "Getting", "things": "Things"},
               music={"id": "staring-at-the-night-sky", "db": -19, "duck": 0.0, "fade_in": 0.3, "fade_out": 0.5})
t = K.t

# 1 · the turn of the hook on a grey page (it also hides a look-away there, if the take has one)
p0 = t("small tasks") - 0.04
K.page("turn1", p0, t("and every") - 0.04, "grey", [
    [("small", "small tasks", "s", 64), ("tasks", "tasks", "s", 64), ("you", "you keep", "s", 64), ("keep", "keep", "s", 64)],
    [("moving", "moving", "big", 150)],
    [("to tomorrow", "to tomorrow", "big", 150)]])

# 2 · the big word loses its letters while the speaker says it disappears
K.erase("energy", t("disappears") + 0.08)

# 3 · the one picture: the in-tray, a print on its own blurred copy
s0 = t("rule") - 0.06
K.picture("tray", "assets/pics/tray.png", s0, t("if it") - 0.06, "There is a rule for this in Getting Things Done",
          frame="print", kind="ai", label="Getting Things Done", label_at=t("getting"), push=1.07)

# 4 · on the face: a punch-in on the word the speaker leans on, a red label for the task that is gone
K.punch(t("now"), hold=0.75, scale=1.1)
K.label("done", t("done#2"), t("the list") - 0.06, "done", at=t("done#2"), sub="you never think about it again",
        sub_at=t("never"))

# 5 · the turn line on its own page
q0 = t("the list") - 0.05
K.page("turn2", q0, t("most days") - 0.05, "grey", [
    [("the list", "the list", "s"), ("is not", "is not", "s")],
    [("long", "long", "big", 190)],
    [("it is", "it is old", "s")],
    [("old", "old", "red", 190)]])

# 6 · "carrying it": the camera comes too close
K.punch(t("carrying"), hold=1.1, scale=1.16)

# 7 · the payoff: nothing but the face, the words and the bed
K.quiet(t("start") - 0.1)
K.mark("outro-red-word-face")
K.build(BIG={"hard", "small", "energy", "rule", "now", "message", "appointment", "done#2", "tired#2", "carrying",
             "two#2", "minutes#2"},
        RED={"two#2", "minutes#2"}, SERIF={"getting", "things", "done#1"})
