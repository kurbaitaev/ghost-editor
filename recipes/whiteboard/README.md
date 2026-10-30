# Whiteboard: a marker board draws each thought over the speaker's talking head

Call it with: **"Whiteboard"**, **"edit this as a whiteboard"**, **"a marker board edit"**.

A split screen: a white marker board on the top half, the speaker's face on the bottom half, as shot. Each sentence is
drawn live in rough marker strokes, and a visible marker follows every stroke and every handwritten word. An eraser
wipes between pages. White pill captions sit on the seam with the spoken word swept in yellow.

**When to use:** a talking head that explains one idea per sentence: psychology, advice, how something works, a
paradox. 25-60 s. Not for a list of places (Seoul list) or a tool tutorial with screen recordings (stan style).
**Read SYSTEM.md before planning a reel**: what stays, what must be new.

## Footage
- The talking head only; no B-roll (0 inserts). The **wide plate** works best: the face is scaled up to x1.15 into the
  bottom half. A plate where the face cannot fit under the seam fails the build ("use the wide plate").
- Look-aways that must be hidden (`build/cover_windows.json` from `cover_windows.py`, or `cover=[...]`) get the board
  full screen, <= 2.5 s each. Small glances stay (references/broll.md 1).

## Anatomy

| part | look | timing |
|---|---|---|
| hook | the face full screen, the first words in a white pill under it | frame 1 until the board drops on the 2nd word (`split_at=` to change) |
| the drop | the board falls over the top half (0-960, 0.42 s, power3.inOut); the face slides down and scales (pivot and scale measured from face.json, the whole face under the seam) | once |
| strokes | seeded rough lines, rects, ellipses, arrows, figures (board.py helpers), 6-9 px, ink / blue / red / green / orange | each draws on over 0.2-1 s, on the word that names it |
| the marker | a white dry-erase marker, its cap in the stroke colour, the nib on the line being drawn; glides between close strokes, lifts off the board when idle | follows every stroke and word (points sampled at build time, no DOM measurement) |
| handwriting | Caveat 700, revealed left to right as the marker writes it | on its spoken word |
| pages | one per thought; an eraser sweeps left to right before the next | the next page starts 0.26 s after the wipe |
| captions | white Inter pills on the seam (y 914), up to 3 words, each word swept yellow as it is said | words outside the hook and full-board windows |
| full board | the board grows to full screen, the drawing moves to its centre (unscaled, so nothing near the edges is cut) | only over a look-away, <= 2.5 s |
| sound | a quiet bed (-22 dB, ducked under speech), marker scribbles as texture (>= 1.6 s apart), an eraser whoosh per page, a whoosh on the drop | |

## Pipeline

```bash
S=<skill>; P=<project>
# the raw cut (references/take-selection.md): $P/assets/plate.mp4 (the WIDE plate, video only, as shot),
# $P/assets/voice.wav, $P/build/words.json (words of the cut, edit seconds)
python3 $S/scripts/face_track.py $P/assets/plate.mp4 --out $P/build/face.json     # on the plate: its seconds are edit seconds
python3 $S/scripts/components.py plan --style whiteboard                          # what the last reels drew: avoid it
# write $P/reel.py (below): the pages for this script
python3 $P/reel.py $P              # -> index.html, build/{plan,beats,sfx_events}.json; FAILS on a broken rule (below)
$S/scripts/hf.sh lint              # in $P: 0 errors (the file-size warning is fine)
python3 $S/recipes/seoul-list/snap.py beats $P      # one strip per page -> build/snaps/: look at every page
python3 $S/scripts/finals.py preview $P --out $P/finals --style "Whiteboard" --code W01 --title "..."   # WAIT for the user's OK
python3 $S/scripts/finals.py render $P ... ; python3 $S/scripts/finals.py qa $P ...
python3 $S/scripts/components.py record --style whiteboard --project $P --reel W01     # after the user's yes
```

## reel.py (a generator per reel, keyed to words)

```python
import sys; sys.path.insert(0, "<skill>/recipes/whiteboard")
from board import *
B = Board(sys.argv[1], music={"id": "forest-mist-whispers", "db": -22}, cover=None, split_at=None)
t = B.t                                 # word refs: "word", "word#2", "^word" (its end), "word+0.1", "two words", a number
B.page(t("relationship") - 0.2)         # a new page; the previous one is erased 0.26 s before
B.draw(stick(230, 380, 1.5), t("there"), INK, 8, shape="stick")     # paths draw on from the time; shape = catalog name
B.write("you", 230, 700, t("you"), 88, INK, "middle")              # Caveat, the marker writes it
B.draw(link(520, 380, 1.4), t("relationship"), RED, 8, shape="link")
B.build()                               # prints the timeline, the numbers and components.py check
```
- Board coordinates: 1080 x 960; keep everything above y 900 (the seam pills cover the bottom; the build fails below).
- Helpers (each returns a list of path strings): `rline rrect rellipse poly arrow stick runner crown check cross phone
  phone_apps envelope clock bulb bubble shield cloud underline heart crack bell book bed zz mountain pair link wrench key
  plane wheel house day`. Pick shapes the last reels did not draw, or add a helper.
- `draw(..., snd=False)` for small follow-up marks; `write(..., snd=True)` for a written word that should be heard.
- Colours: `INK BLUE RED GREEN GOLD ORANGE`.

## The build refuses (fix the generator, never the check)
- a look-away in the cover windows not hidden by a full board, or a full board longer than 2.5 s;
- the face over the seam in split mode (the scale is measured; pass `scale=` lower only if needed);
- a stroke or a word below y 900 (under the seam captions);
- the face on screen under 65 % (full boards add up).

## Checks that caught real problems
- A CSS `filter: contrast() saturate()` on the speaker's video is a colour change on the face: the plate has no filter,
  and broll_qa `as_shot` fails one.
- `getPointAtLength()` inside a timeline callback is seek-order dependent in the renderer (hyperframes lint
  gsap_callback_dom_measurement): the marker follows points sampled from each path at build time.
- A label under the seam pill is unreadable: the build fails any stroke or word below y 900.
- A scribble sound on every stroke was 29 sounds in 30 s: scribbles are texture, >= 1.6 s apart, 4 dB lower.

## Worked example

`example/` holds an English talking head, "willpower is a battery" (7 thoughts, 91 words, about 38 s), with
`script.txt`: small choices drain willpower like a battery, so decide the small things once. `reel.py` draws one page
per thought, keyed to the spoken words: a battery that charges four green cells; the same battery drained cell by cell
while a T-shirt, a bowl and a TV are drawn on "wear", "eat", "watch"; a crescent moon over a battery with one red cell;
a tired brain at a fork in the road, a red dotted route down the easy branch with a stop per temptation and a sad face
where it ends; a balance tipping from "more discipline" (struck out) to "fewer choices"; a week as a timeline with one
arrow per habit; a target hit by an arrow and a full battery. Its drawings are helpers in reel.py (`battery charge
slash shirt bowl tv moon sparkle brain fork dotted frown stand balance timeline target`), plus board.py's arrow, check,
underline, zz and runner. The one look-away (on "wear ... eat") gets the board full screen; when
`build/cover_windows.json` exists, its windows are used instead. Bed: `digital-clouds` at -22 dB. It is for reading
and copying: the recording is yours to supply. Put the cut in `$P`, transcribe it with `--lang en` into
`build/words.json`, run face_track.py on the plate, then `python3 $S/recipes/whiteboard/example/reel.py $P` (or copy it
to `$P/reel.py` with its `sys.path` line pointing at `$S/recipes/whiteboard`), and fix any word key the build stops on
(`fixes=` corrects a misheard word: whisper heard "drains" as "trains"). A dry run (a synthetic voice, a stand-in wide
plate, the look-away keyed to the words) builds with 7 pages, 139 strokes, split at 0.06 s, the face x1.15 under the
seam and on screen 95.3 %, one full board of 1.82 s, and lints with 0 errors; it has not been rendered with real footage.
