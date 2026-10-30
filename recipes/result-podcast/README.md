# RESULT: a warm podcast-style edit with paper, film and handwriting

Call it with: **"edit this in RESULT style"**, **"loompixual style"**.

The look comes from @loompixual's "RESULT" edit. Libraries and licences behind it: STYLE-LIBRARIES.md in this folder.

**When to use:** storytelling or nostalgic talking heads, podcast-style monologues, lists of memories or examples where a photo per
idea helps. Warmer and more tactile than Clean OS.

**Two ways to build it:**
- **Face RESULT** (the default for a talking head): the speaker's face stays on screen as shot and the paper props sit
  beside, above or below it, never on it. Section "Face RESULT" below; `faceresult.py`.
- **Paper-led RESULT**: full-screen paper scenes between lines (`example/` in the private edition). On a talking head it
  breaks the budgets (face >= 65 %, a full-screen card <= 2.5 s): use it only for a narrated or footage-free reel.

## The grammar

1. **Captions:** one or two words at a time, centred, Inter Tight. Two-tier emphasis: a small line, then one big bold word.
   Key words in Caveat handwriting.
2. **Cards:** navy text cards with film dust; polaroid photo cards; a paper stack whose pictures swap stop-motion; framed B-roll.
3. **Texture:** dust and grain drawn on a canvas seeded per frame (deterministic in render); film-burn light leaks at section turns.
4. **Props for the funny beats:** comic emoji stickers, a REC frame, an incoming-call card with a finger tapping "decline",
   a cursor clicking a dialog, a chat-bubble card.
5. **Cuts:** hide jump cuts with a 0.2 s picture morph-dissolve between lines while the audio hard-cuts. No zoom on every cut:
   at most three comic punch-ins per reel (per-cut zooms were rejected as annoying).

## Pipeline

```bash
S=~/.claude/skills/ghost-editor; P=~/reels/<name>
# 1. attempt log: Gemini 2.5 Pro over the WHOLE raw take (every attempt, restart and filler, verbatim)
# 2. takes: best take per line, cut only pauses > 0.7 s inside a line, start each line at the voice onset (RMS > -30 dB, no breaths)
cp $S/recipes/result-podcast/example/{takes.py,build.py,gen_broll.sh} $P/ && cd $P && python3 takes.py      # -> build/takes.json + build/rough.mp4
# 3. the rough cut: transcribe it (build/rough.words.json), audit it verbatim with Gemini 2.5 Pro; fix and re-audit until clean
python3 $S/scripts/transcribe.py build/rough.mp4 --out build/rough.words.json --lang <code>
# 4. B-roll stills / photos for the polaroids and stack (gen_broll.sh: AI stills with $S/scripts/broll_gen.py), the fonts,
#    then adapt build.py's beats to the new script (every beat is keyed to the spoken words)
bash gen_broll.sh && python3 $S/recipes/clean-os/fetch_fonts.py $P "Inter Tight:ital,wght@0,400..800;1,400..800" "Caveat:wght@400..700"
python3 build.py && $S/scripts/hf.sh lint && $S/scripts/hf.sh snapshot --at <every beat>
$S/scripts/hf.sh render -o renders/<name>.mp4
```

## Checks that caught real problems

- Whisper merges restarts ("millennials alw- millennials") into a clean sentence and can even invent a script word that was never
  said. The take picker left 6 restarts in until two Gemini 2.5 Pro audits found them all.
- Hide each caption with an explicit `fromTo` placed AFTER its fade-in; a bare `set` inside the fade gets overridden and the caption
  stays on screen.
- Seed the per-frame dust/grain canvas by frame number, never by wall-clock time, or renders won't match previews.

## Worked example

`example/` holds an English storytelling reel, "keep the paper" (12 lines, about 32 s of speech + a 2.2 s outro), with
`script.txt`: on every trip the speaker keeps one paper thing a day. `takes.py` picks the best take of each line (two of
them follow a false start) and writes the rough cut; `build.py` lays the takes with the morph dissolve and keys every
beat to the rough cut's words: a train ticket stamped "day 1" on kraft, a thermal receipt that prints out of its slot and
gets its missing address circled, a notebook page closing over a pressed leaf, a photo-count notification and a storage
dialog a cursor dismisses over the speaker (with the only two punch-ins and two emoji stickers), a paper stack whose
pictures swap stop-motion, a polaroid with the ticket landing on it and handwriting on both, a sticky note, the final navy
card held through the outro; film-burn leaks at the three turns only, `chillax` as the bed. `gen_broll.sh` makes its six
stills (no people in any of them). It is for reading and copying: the recording is yours to supply. Re-time `LINES` in
takes.py from your own attempt log, transcribe the rough cut with `--lang en`, and fix any word key the build stops on
(keys accept spellings like `"thousand|3000"`). A dry run (a test-pattern recording with a synthetic voice and two false
starts, the six stills from gen_broll.sh) builds and lints with 0 errors; it has not been rendered with real footage.

## Face RESULT (talking head: props beside the face, never on it)

Call it with: **"Face RESULT"**, **"RESULT on my face"**, or **"RESULT style"** on a talking head.

`faceresult.py`, on the shared base `scripts/lib/facereel.py`. It shares this folder's house.json and catalog.json, so a
new reel cannot repeat a RESULT prop by accident.

**House (never changes):**
- the speaker's plate AS SHOT: no grade, no filter, no vignette on the face; a slow 4 % drift; at most 3 punch-ins (they
  pivot on the mouth line so the chin barely moves); film grain + per-frame dust over everything (texture only);
- two-tier captions on a navy card under the chin: a small Inter Tight line (62 px) over one big word (132 px) or a
  Caveat key word (150 px), sized to fit; one text layer at a time (a chest prop or a card that carries the words drops them);
- paper objects from the line's world BESIDE (left / right column), ABOVE (top band) or BELOW (chest band) the face,
  placed in zones measured from build/face.json per prop window, inside the Instagram safe area (top 220, bottom 1500);
- full-screen cards (navy / kraft / cork / paper) <= 2.5 s, pushing in slowly; the face on screen >= 65 %; <= 3 stock / AI
  inserts a minute, each in a polaroid or paper frame, prepared by insert_prep.py.

**New every reel** (`components.py plan --style result-podcast`): the props, the card treatments, the entrances
(`enter=`: none / slap / toss / unfold / swing / fade / side / drop / rise), the full-screen card entrances
(fade / iris / push / wipe), the hook and the outro.

```bash
S=<skill>; P=<project>
# $P/assets/plate.mp4 (the approved raw cut, video only, as shot), $P/assets/voice.wav, $P/build/words.json (edit seconds)
python3 $S/scripts/face_track.py $P/assets/plate.mp4 --out $P/build/face.json
python3 $S/scripts/components.py plan --style result-podcast        # avoid the recent reels' components
# write $P/reel.py (below): this reel's beats, keyed to words; example-face/reel.py is a whole one to start from
# (copied into $P, point its sys.path line at $S/recipes/result-podcast)
python3 $P/reel.py $P                 # -> index.html + build/{plan,beats,sfx_events}.json; FAILS on a broken rule (below)
$S/scripts/hf.sh lint ; python3 $S/recipes/seoul-list/snap.py beats $P      # look at every beat's strip
python3 $S/scripts/finals.py preview $P --out $P/finals --style "Face RESULT" --code R01 --title "..."   # WAIT for the user's OK
python3 $S/scripts/components.py add --style result-podcast --id <new> --kind prop --sig 'class="prop fr-<new>"' --desc "..."
python3 $S/scripts/components.py record --style result-podcast --project $P --reel R01              # after the user's yes
```

```python
import sys; sys.path.insert(0, "<skill>/recipes/result-podcast")
from faceresult import *
R = FaceResult(sys.argv[1], cover=[(23.5, 24.2)], music={"id": "chillax", "db": -21})
t = R.t                                   # word refs: "word", "word#2", "^word" (its end), "word+0.1", "two words", a number
a, b = t("beach") - 0.1, t("^work") + 0.4
R.prop("card", a, b, "right", '<div class="sheet"><div class="hand l1">tasks</div></div>', w=260, h=380, what="a note",
       enter="slap", cls="fr-note")
R.write("#card .l1", t("tasks"))          # handwriting on its word; also R.stamp, R.pop, R.draw, R.words_in, R.show / R.hide
R.scene("big", t("even"), t("even") + 2.0, "kraft", "<div>...</div>", what="a full-screen card", enter="iris", caps=True)
R.punch(t("better"))
R.build(BIG={"work", "better"}, SCRIPT={"breather"}, css=".l1 { position: absolute; left: 20px; top: 40px; font-size: 52px; }")
```
- `R.prop(id, a, b, zone, html, w, h, what, dx=0, dy=0, rot=0, enter=..., leave="fade", nocap=None, cls="fr-<name>")`:
  `zone` = `left` / `right` / `top` / `chest`; it fails when it does not fit the zone or touches the face; `cls` is the
  catalog sig (`class="prop fr-<name>"`).
- `R.scene(id, a, b, "navy"|"kraft"|"cork"|"paperbg", html, what, caps=False, enter="fade"|"iris"|"push"|"wipe", cls=...)`
- `R.polaroid(...)`, `R.still(...)` / `R.video(...)` (an insert: counted, picked up by broll_vision picks from index.html)
- `R.build(BIG={...}, SCRIPT={...}, css="...")`: captions, plate, grain, dust, audio; prints the numbers and `components.py check`.

**The build refuses** (fix the generator): a prop that touches the face (also under a punch-in or the drift) or does not
fit its zone; a caption card the chin reaches; a full-screen card > 2.5 s; a look-away (`cover` / build/cover_windows.json)
not hidden while a card is fully in; the face on screen < 65 %; > 3 inserts a minute; a 4th punch-in; an id named c<n>
(caption ids).

**Worked example:** `example-face/` holds an English talking head, "the doorway effect" (11 sentences, about 42 s), with
`script.txt`: you walk into a room and forget why, because a doorway tells the brain the scene is over. `reel.py` keys
every beat to the words: a paper door already beside the speaker on frame 1 that opens on an empty doorway, a paper
fridge whose magnet letters spell WHY, a ticket ("memory: fine ✓", THE DOOR stamped) with the first punch-in, a label
tape printing DOORWAY EFFECT on the chest, a film slate that claps on "film" and changes scene on "doorway", the one
full-screen card (2.44 s, wiped in: an index card drops into an OLD SCENES drawer) over the look-away, a graph-paper card
in the top band whose bars grow on "door" and "room", a paper megaphone on the chest with the second punch-in, and the
door again as the outro (it shuts on "close", a wedge props it open on "don't"). Every prop is drawn (0 inserts), 15
sounds from the kit, `lo-fi-02` as the bed. It is for reading and copying: the recording is yours to supply. Transcribe
your cut with `--lang en`, take its look-aways from `scripts/cover_windows.py` (leave `cover=` out to read
build/cover_windows.json), and fix any word key the build stops on (`fixes=` maps a misheard word to the spoken one).
A dry run (a synthetic voice, a stand-in talking-head plate tracked by face_track.py) builds with the face on screen
94.3 %, one full-screen card covering the look-away and 2 punch-ins, lints with 0 errors and was checked beat by beat
with snap.py; it has not been rendered.
