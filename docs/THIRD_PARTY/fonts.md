# Fonts (`templates/fonts/`)

Every bundled font is under the SIL Open Font License 1.1; each family's licence text sits next to it as `LICENSE-<family>.txt`.

| family | files | source | reserved font name |
|---|---|---|---|
| Geist, Geist Mono | `geist-latin`, `geist-mono-latin` | Google Fonts (Vercel's Geist) | none |
| Inter | `inter-latin`, `inter-cyrillic` | Google Fonts | none |
| Inter Tight | `inter-tight-*` (4, incl. italic) | Google Fonts | none |
| JetBrains Mono | `jetbrains-mono-*` | Google Fonts | none |
| Montserrat | `montserrat-*` | Google Fonts | none |
| Oswald | `oswald-*` | Google Fonts | none |
| Unbounded | `unbounded-*` | Google Fonts | none |
| Caveat | `caveat-latin`, `caveat-cyrillic` | Google Fonts (the variable 400-700 font, one file per `unicode-range`) | none |
| Playfair Display | `playfair-display-{latin,cyrillic}`, `playfair-display-italic-{latin,cyrillic}` | google/fonts `ofl/playfairdisplay/PlayfairDisplay[wght].ttf` and `PlayfairDisplay-Italic[wght].ttf`, **unmodified**: only the container changed (TTF to WOFF2, fontTools; every table except `head`'s WOFF2 flag and checksum is byte-identical) | **"Playfair Display"**. A subset or any other change would be a Modified Version that may not use the name, so the full fonts ship; the `latin` and `cyrillic` files are the same full font, picked by `unicode-range`. |

If you add a font, prefer one without a Reserved Font Name, or ship its upstream files unchanged. (PT Mono, used for typed
paper in Face RESULT, has Reserved Font Names and Google serves it as subsets, so it is not bundled: the builds fall back to
JetBrains Mono.)
`recipes/clean-os/fetch_fonts.py` downloads Inter and Great Vibes (OFL) from Google Fonts into a project at build time; they are not bundled.
