#!/usr/bin/env python3
"""Kinetic doc, format C (B-roll only + a voice-over): a worked example in English, "walking without headphones"
(~32 s), the voice over the user's own clips first, then stills. For reading and copying: the recording and the
footage are yours, so re-time every word ref against your own build/words.json.

    python3 c_broll.py <project>   # $P: assets/voice.wav, build/words.json,
                                   # assets/clips/{skyline,path,hills}.mp4: the user's own footage (own_footage.py find,
                                   #   no people in them), each through insert_prep.py --no-grade (rotated phone clips:
                                   #   --crop / --size); every clip through the people / line check
                                   # assets/pics/thoreau.jpg: a public-domain archive portrait (Wikimedia Commons: note the
                                   #   file and its licence) + AI stills (broll_gen.py, the B&W archive prefix of
                                   #   b_voiceover.py): headphones, notebook, bench, road, shoes, door

The script it expects, word for word:
  Some walks clear your head better than any app. Because out there nothing asks you for anything. Henry David Thoreau
  wrote: I went to the woods because I wished to live deliberately. But we walk with our ears full. Podcasts, calls,
  playlists, all the way. You never hear your own thoughts catch up. You keep busy in the one hour that could be empty.
  There is freedom in a walk with nothing in your ears. But there is boredom too. The first ten minutes feel slow.
  Then the quiet starts to work. Maybe that is the whole trick. Leave the headphones at home once, and see what you
  were too busy to hear.

1. hook: the user's night skyline as a print, pushing in; then an empty park path on "nothing asks you for anything";
2. Thoreau, an archive portrait as a print with "Henry David Thoreau" in the serif; the line typed on warm paper,
   word by word as it is spoken;
3. the turn on the grey page: "but we walk with / OUR EARS / FULL"; headphones on a table (a punch-in on "way");
4. a notebook with a pen on "thoughts"; an empty bench in a window on black on "empty";
5. the user's hills on "freedom"; the grey page "but there is / BOREDOM / too"; a straight road (a punch-in on "slow");
6. the notebook again under a red box QUIET / "starts to work";
7. walking shoes by the door on "the whole trick";
8. the payoff: a door opening onto light, HEAR in red, no sound effects; hard end.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from kdoc import *  # noqa: E402,F403

P = sys.argv[1] if len(sys.argv) > 1 else "."
# fixes: whisper's spellings -> the words on screen (captions are lower case: names and "I" are set here)
K = KineticDoc(P, fmt="C", fixes={"thoro": "Thoreau", "henry": "Henry", "david": "David", "thoreau": "Thoreau", "i": "I"},
               music={"id": "sleepy-cat", "db": -19, "duck": 0.0, "fade_in": 0.3, "fade_out": 0.5})
t = K.t
pic = lambda n: f"assets/pics/{n}.png"

# 1 · hook: the skyline at night, then the empty path
a1 = t("because") - 0.04
K.picture("skyline", "assets/clips/skyline.mp4", 0.0, a1, "Some walks clear your head better than any app", frame="print",
          kind="own", push=1.1, sfx=None, tag="hook-own-clip-print")
a2 = t("henry") - 0.06
K.picture("path", "assets/clips/path.mp4", a1, a2, "Because out there nothing asks you for anything", frame="print", kind="own")

# 2 · the writer and the line, typed on paper as it is spoken
a3 = t("i went") - 0.08
K.picture("thoreau", "assets/pics/thoreau.jpg", a2, a3, "Henry David Thoreau wrote", frame="print", kind="archive",
          label="Henry David Thoreau", label_at=t("henry"), push=1.06, person=True)
a4 = t("but we") - 0.06
K.page("quote", a3, a4, "type", [
    [("“I", "i went", "s"), ("went", "went", "s")],
    [("to", "to the", "s"), ("the", "the woods", "s"), ("woods", "woods", "s")],
    [("because", "because i", "s"), ("I", "i wished", "s")],
    [("wished", "wished", "s"), ("to", "to live", "s")],
    [("live", "live", "s")],
    [("deliberately”", "deliberately", "s")]], cursor=False)

# 3 · the turn, then the headphones
a5 = t("podcasts") - 0.06
K.page("turn", a4, a5, "grey", [
    [("but", "but we", "s"), ("we", "we", "s"), ("walk", "walk with", "s"), ("with", "with", "s")],
    [("our ears", "our", "big", 170)],
    [("full", "full", "red", 170)]])
a6 = t("you never") - 0.06
K.picture("headphones", pic("headphones"), a5, a6, "Podcasts, calls, playlists, all the way")
K.punch(t("way"), hold=0.6, scale=1.12, target="headphones")

# 4 · your own thoughts; the hour that could be empty
a7 = t("you keep") - 0.06
K.picture("notebook", pic("notebook"), a6, a7, "You never hear your own thoughts catch up")
a8 = t("there is freedom") - 0.06
K.picture("bench", pic("bench"), a7, a8, "You keep busy in the one hour that could be empty", frame="window")

# 5 · the user's hills; the second turn; the road
a9 = t("but there") - 0.06
K.picture("hills", "assets/clips/hills.mp4", a8, a9, "There is freedom in a walk with nothing in your ears", kind="own")
a10 = t("the first") - 0.06
K.page("bored", a9, a10, "grey", [[("but", "but there", "s"), ("there", "there", "s"), ("is", "is", "s")],
                                  [("boredom", "boredom", "big", 190)], [("too", "too", "s")]])
a11 = t("then the") - 0.06
K.picture("road", pic("road"), a10, a11, "The first ten minutes feel slow")
K.punch(t("slow"), hold=0.5, scale=1.1, target="road")

# 6 · the notebook again, the red box on the word
a12 = t("maybe") - 0.06
K.picture("notebook2", pic("notebook"), a11, a12, "Then the quiet starts to work", push=1.04, sfx=None)
K.label("quiet", t("quiet"), a12, "quiet", at=t("quiet"), sub="starts to work", sub_at=t("starts"), host="notebook2", caps=False)

# 7 · the whole trick
a13 = t("leave") - 0.08
K.picture("shoes", pic("shoes"), a12, a13, "Maybe that is the whole trick")

# 8 · the payoff: the door onto light, nothing else
K.quiet(a13 - 0.05)
K.picture("door", pic("door"), a13, K.T, "Leave the headphones at home once, and see what you were too busy to hear",
          push=1.06, sfx=None, tag="outro-open-door")
K.build(BIG={"head", "anything", "way", "thoughts", "empty", "freedom", "slow", "trick", "home", "hear#2"},
        RED={"hear#2"}, SERIF={"henry", "david", "thoreau"})
