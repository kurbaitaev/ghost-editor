#!/usr/bin/env bash
# AI B-roll stills (Gemini). Resumable: skips files that already exist.
G=~/.claude/skills/ghost-editor/scripts/broll_gen.py
gen() { [ -f "assets/broll/$1.png" ] && return; python3 $G "$2" "assets/broll/$1.png" --aspect "$3" 2>&1 | tail -n 1; }
gen crt "An old beige CRT computer monitor and keyboard on a wooden desk in a 2003 teenager's bedroom at night, a dial-up connection window on the screen, warm desk lamp, posters slightly out of focus, film photo, grain, no readable text, no logos" 4:5 &
gen yard "Children riding bicycles in the courtyard of Soviet-era apartment blocks at dusk in the early 2000s, warm sunset light, swings and a sandbox, nostalgic 35mm film photograph, grain, no text" 4:5 &
gen phone_home "A beige 1990s corded landline home telephone with a coiled cord, isolated product photo on a plain off-white background, soft studio light, centered, no text, no logos" 1:1 &
gen phone_flip "A generic silver flip mobile phone from 2005, opened, isolated product photo on a plain off-white background, soft studio light, centered, no brand, no logos, no text" 1:1 &
gen phone_smart "A generic modern black smartphone seen at a slight angle, blank dark screen, isolated product photo on a plain off-white background, soft studio light, centered, no brand, no logos" 1:1 &
wait
gen copybook "Close-up of neat cursive handwriting in a lined school copybook, a fountain pen resting on the page, warm daylight, 1990s school desk, shallow depth of field, film photo, the handwriting is decorative and illegible" 4:5 &
gen map "A taxi driver's hands holding a folded printed paper road map over the steering wheel at night, city lights blurred through the windshield, early 2000s, film photo, grain, no readable text" 4:5 &
gen fridge "A modern stainless steel smart refrigerator in a kitchen with a glowing Wi-Fi symbol on its small display, slightly absurd and funny, warm light, photo, no brand, no other text" 4:5 &
wait
