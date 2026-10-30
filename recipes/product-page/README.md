# Product page

a review or demo of a named tool laid out like a product page: the speaker's cut-out over a rounded footage card on a
gradient page, two-tier headlines (heavy sans + italic serif), one spoken word at a time in a pill, zoomed screen crops
on the verb, camera moves between sections; from @adrien.ninet

What it looks like: white pages carry the thing (its real picture, the rebuilt UI state, hairline line-art drawings of
the nouns) and a virtual camera moves inside them on the speaker's words; the speaker's face, as shot, comes in full
frame for the lines said to the viewer (white two-tier chest captions) and as a cut-out over a rounded footage card in
the hook and the splits; the grey word pill runs over pages; black two-tier titles land on the page; a ducked plucky bed
that drops out under the hook payoff; a flat ending.

The accent and the logo come from the product itself: run `scripts/brand_kit.py pull <its URL> --dir $P/brand` and
pass `accent=kit["accent_on_white"]`; its logo, icon and people-checked product shots are in `$P/brand/` (see `brand_kit.py show`).

Read SYSTEM.md first (thesis, invariants, house look, slots and generators, planning procedure, changelog);
house.json is the fixed look, catalog.json what each reel used.

## Build

A Python builder on scripts/lib/facereel.py: `productpage.py` (class `ProductPage`; usage block in its docstring). A reel
is a short generator in the project that calls it. The public edition has no worked example for this recipe yet (the
founding reel's generator holds a private script): write `reel.py` from the usage block in productpage.py's docstring,
SYSTEM.md (slots, planning procedure) and the component definitions in catalog.json. What a reel needs in $P:
the plate(s) as shot (assets/*.mp4), assets/<plate>_matte.webm (matte.py on the hook + split windows),
assets/voice.wav, build/words.cut.json, build/face.json per plate (face_track.py), the real picture of the named thing
through insert_prep.py (+ a 2x copy for the hook badge).

```bash
S=~/.claude/skills/ghost-editor
~/.venvs/media/bin/python reel.py --project $P          # index.html + build/beats.json, plan.json, sfx_events.json, capboxes.json
bash $S/scripts/hf.sh lint $P                           # 0 errors
python3 $S/recipes/seoul-list/snap.py beats $P          # look at every beat
python3 $S/scripts/components.py check --style product-page --project $P
python3 $S/scripts/finals.py preview $P --out $P/finals --style "Product page" --code R01 --title "..."   # WAIT for the user's OK, then render
```

The building blocks (times are edit seconds or word refs, `R.t("word")`, `"word#2"`):
- scenes: `R.hook(end, file_card(...), headline)`, `R.art_page(...)`, `R.rise_page(...)`, `R.split(...)`,
  `R.ui_page(...)` + `R.rows_off(...)`, `R.face_beat(...)`, `R.whip_pages(...)`, `R.gallery(...)` + `R.shrink_tile` +
  `R.veil`, `R.page_title(...)`, `R.pills(windows)`, `R.build()`
- moves: `R.camera`, `R.app_icon`, `R.press`, `R.fade_in` / `fade_out`, `R.draw_on`, `R.loop`, `R.hop` / `falter`,
  `R.phone_hops`; budgets: `R.full_page`, `R.insert`, `R.sound`, `R.beat`
- props and UI (the founding reel's set: draw new ones per reel): `Art`, `iso`, `box`, `line`, `cyl`, `phone_art`,
  `bed_art`, `shoe_art`, `mugs_art`, `stairs_art`, `book_art`, `ios_alert`, `ios_list`, `bell_glyph`, `tile`, `full`, `place`
- `fontwidths.py`: advance widths for fitting (run by the builder when build/metrics.json lacks a voice)

## Calls

- "Product page"
- "tool review page"
