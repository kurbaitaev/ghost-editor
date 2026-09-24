You are a senior motion designer reverse-engineering this vertical reel (1080x1920) so it can be rebuilt EXACTLY in HTML/GSAP. Be literal and precise; watch frame by frame.

Output markdown:
1. TRANSCRIPT: word for word with [ss.s] timestamps per phrase.
2. EDIT LOG, as a table, one row per shot/scene/graphic event, in time order: start–end (s, 0.1 s precision) | layer (speaker / full-screen graphic scene / B-roll / caption / overlay) | exactly what is visible (every text string verbatim, colours as hex estimates, font style: family guess, weight, case, size relative to frame width) | how it animates IN (type, direction, duration, easing, blur, scale %, stagger per word/letter) | what it does while held (drift, camera move, parallax, 3D) | how it animates OUT / transition to next | sound effect heard at that moment (type) | speaker framing when the speaker is visible (scale vs a wide shot, crop, position, any punch-in/zoom move).
3. CAPTIONS SYSTEM: exact style (font, size, case, colour, position y as % of height, words per caption, how each word enters), keyword treatments (pills, highlight boxes, colour changes: shape, rotation, colour, how they pop), when captions are hidden.
4. GRAPHIC SCENES: for each full-screen scene, a precise build description: background (colour/gradient hex), element positions (x,y as % of frame), animation order with timings relative to scene start, cursor/hand icons and what they do, badges/rings (stroke, glow, pulse), 3D camera behaviour (perspective, z-depth, blur by depth, direction of travel).
5. TRANSITIONS between speaker and scenes and between scenes: type and duration for each.
6. SOUND: music (genre, tempo, level vs voice, where it starts/stops/changes), every SFX with timestamp and type.
7. PALETTE and TYPE SYSTEM summary (hex values, fonts, sizes) and the 5 things that most define this style.
8. MAPPING: for each scene or effect, the closest ghost-editor beat (`scene` kinds card / stats / fly3d / image / sentence, captions style editorial, zoom.base / pushes, transitions blur / expand / wipe) or "NEW: <what would need building>".
Never invent values; mark estimates (est.).
