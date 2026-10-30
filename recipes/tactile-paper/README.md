# Tactile paper

A talk told on printed paper: newspaper and archive pages that turn with a real page fold, stepped 8 fps motion like
stop-motion, zoom-blur pushes, small hand-drawn labels that rise from a mask, paper foley; from @chrismoran__

What it looks like: frame 0 is maroon paper with half the first line in a near-black grotesque and the object that
finishes it already unfurling from a corner; a zoom-blur push on the next word; pages, prints and cards land on their
nouns and turn with a WebGL page fold, all stepped on twos (the payoff on threes); white arrows and one crimson marker
point; black condensed pill captions of 1-3 words; the paper turns away like a page to reveal the speaker's face (as
shot) on the personal lines; the payoff replays the hook object on 8 fps and the reel ends flat on the face.

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog);
house.json is the fixed look, catalog.json what each reel used.

## Build

- `tactile.py`: the builder (Tactile on scripts/lib/facereel.py; stdlib). Scenes (`paper_scene`, `face_scene`) take
  grounds, sheets (`sheet`, `unfurl`, `turn`, `slide`), marks (`underline`, `ellipse`), `label`, `title`, `rise`,
  `arrow`, `gobo`, `blur`, `reveal`; cameras (`push_camera`, `close_camera`, `camera`); `captions`, `sound`,
  `build`. Its docstring has the usage block.
- `tactile.js`: the runtime inlined into index.html (the replica's page fold, brush, marker, gobo, captions + the
  scene loop); seek-safe.
- `props.py`: paper props per reel (ground, essay_page, notebook_page, ticket, photo_print, paper, apply_ink,
  halftone); numpy + Pillow + OpenCV, so run generators with a python that has them (e.g. `~/.venvs/media/bin/python`).

The public edition has no worked example for this recipe yet: write the reel's generator (an argparse script taking --project) from the usage block in
tactile.py's docstring, SYSTEM.md (slots, planning procedure) and the catalog, then

    ~/.venvs/media/bin/python <generator> --project $P          # draws missing props, writes index.html + build/*.json
    $S/scripts/hf.sh lint $P                                    # 0 errors
    python3 $S/scripts/components.py check --style tactile-paper --project $P
    python3 $S/scripts/finals.py preview $P --style "Tactile paper" --code <CODE> --title "..."   # then WAIT for the user's OK
    python3 $S/scripts/finals.py render ...                     # only after the user's OK

## Where things are

- The reference: a page-turn tutorial reel by @chrismoran__ (After Effects CC Page Turn + Posterize Time), studied
  frame by frame; its measured motion (unfurl, fold, gobo, arrow) lives in tactile.py (`REPLICA`, `REF_ARROW1`).

## Calls

- "Tactile paper"
- "like the @chrismoran__ page-turn reel"
- "paper page turn"
