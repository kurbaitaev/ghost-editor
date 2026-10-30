#!/usr/bin/env bash
# RESULT worked example ("keep the paper"): the AI B-roll stills build.py uses (Gemini). Resumable: skips files that
# already exist. Run in $P. No people in any of them, so no people rules come into play; look at each one before using it.
G=~/.claude/skills/ghost-editor/scripts/broll_gen.py
mkdir -p assets/broll
gen() { [ -f "assets/broll/$1.png" ] && return; python3 $G "$2" "assets/broll/$1.png" --aspect "$3" 2>&1 | tail -n 1; }
gen train "View from a window seat of an early-morning regional train, a paper ticket and a paper coffee cup on the small table, soft dawn light over fields outside, 35mm film photo, grain, no people, no readable text, no logos" 4:5 &
gen cafe "A small corner cafe table by a window, a flat white and an almond croissant on a plate, a folded paper receipt beside the saucer, warm morning light, 35mm film photo, grain, no people, no readable text, no logos" 4:5 &
gen park "An autumn park path covered in fallen yellow and orange leaves, an empty wooden bench, soft afternoon light, 35mm film photo, grain, no people, no text" 4:5 &
wait
gen harbour "A quiet old harbour at golden hour, small fishing boats and pastel houses on the hill behind, a souvenir-photo feel, 35mm film photo, grain, no people, no readable text" 4:5 &
gen box "Top-down photo of an open cardboard shoebox on a wooden table filled with travel paper keepsakes: train ticket stubs, cafe receipts, a pressed leaf, postcards, a folded map, warm lamp light, film photo, no people, the paper text is illegible, no logos" 4:5 &
gen leaf "A single dried pressed autumn maple leaf, flat, isolated on a plain off-white paper background, soft even light, centered, top-down, no text" 1:1 &
wait
