# Sound effects and music (Mixkit + a CC0 pack)

Two kinds of sound, with different rules:

- **The CC0 pack ships in this repo**: `library/sfx/cc0-*.wav`, 27 sounds (reaction sounds such as a deep boom,
  a record scratch, an air horn, crickets, a gong, a sad violin, huh / wow / oof voices, plus paper and wood foley).
  Each comes from Freesound under CC0 1.0 (public domain: use, change and share them, commercial included, no credit
  needed), and each was checked by hand: the sound page shows CC0 and the uploader recorded or made the sound
  themselves. The manifest entry of each (`"pack": "cc0"`) links its Freesound page and says what was trimmed.
  `scripts/cc0_pack.py list` shows the pack; `cc0_pack.py build` re-downloads and re-trims it.
- **Mixkit items don't ship**: `library/sfx/manifest.json` and `library/music/manifest.json` list them by id and
  source page; `scripts/library_restore.py` and `scripts/sfx_fetch.py` download them onto your machine.

- **Sound effects:** Mixkit Sound Effects Free License. Use them in your videos, commercial included, no attribution.
  You may not redistribute an item on its own, as stock, or inside a tool or template, which is why only the list ships.
- **Music:** Mixkit Stock Music Free License. Fine for web and social video, podcasts, ads and YouTube. Not allowed:
  CDs/DVDs, video games, TV or radio, remixing into a music-only track, or registering a track with Content ID or any
  other rights service.
- **The download script:** Mixkit's User Terms (mixkit.co/terms/) say not to "use scripts or bots to mass download
  Items". The restore fetches about 70 items, once, from your own machine. If you'd rather not, download the items by
  hand from the `source` pages in the manifests and save them under the manifest's `file` names
  (`library/sfx/<id>.wav`, `library/music/<file>`); `doctor.sh` checks the files, not how they arrived.
- Full terms: https://mixkit.co/license/

Memes are not included. Clips and sounds you add with `scripts/meme_add.py` are your responsibility.
