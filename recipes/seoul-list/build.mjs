#!/usr/bin/env node
// Seoul list: list.json + B-roll proxies + the voice-over -> a HyperFrames project (index.html, 1080x1920, 30 fps).
//
//   node build.mjs <project>            reads <project>/list.json (schema: README.md "list.json")
//
// Blocks (README "Anatomy"): base B-roll montage (hard cuts, optional transitions.py window on a cut), word beats
// (italic serif / heavy grotesk, big word + subline), stacked lists, white word flashes, white collage pages (shot
// shrinks into a card, glitch word, photo card, Fluent stickers), triptychs, Instagram comment card, macOS frosted
// window with swapping cut-outs, blue highlight words, iMessage outro. Sound: the VO, an optional ducked bed
// (lib/motion.mjs buildMusic) and kit SFX by role, levelled against this voice like build.mjs.
//
// Every time in list.json is a VO second or a word ref ("Lisbon", "in#2", "^life+0.1": see README). Footage clip
// times are frame counts / fps truncated to 6 decimals (fgrid), never rounded (SKILL.md). Writes index.html,
// build/sfx_events.json + build/transitions.json (for qa.py) and build/beats.json (key times for snap.py).
import fs from "node:fs";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { buildMusic } from "../../scripts/lib/motion.mjs";
import { loadManifest as emojiManifest, installEmoji, emojiPopHtml, emojiPopJs, EMOJI_POP_CSS } from "../../scripts/lib/emoji-pop.mjs";
import { FT_HELPER } from "../../scripts/lib/caption-templates.mjs";
import { pySpawnSync } from "../../scripts/lib/plat.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SKILL = path.resolve(HERE, "../..");
const LIB = path.join(SKILL, "library");
const proj = path.resolve(process.argv[2] || ".");
const spec = JSON.parse(fs.readFileSync(path.join(proj, "list.json"), "utf8"));
const FPS = spec.fps ?? 30;
const W = 1080, H = 1920;
const BLUE = spec.blue || "#0B84FE";
const warn = [];
const die = (m) => { console.error("ERROR: " + m); process.exit(1); };
const r3 = (x) => Math.round(x * 1000) / 1000;
const F = (t) => Math.round(t * FPS);
const fgrid = (frames) => (Math.floor((frames / FPS) * 1e6) / 1e6).toFixed(6);
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const A = path.join(proj, "assets");
for (const d of ["", "clips", "fonts", "sfx", "stills", "tx"]) fs.mkdirSync(path.join(A, d), { recursive: true });
fs.mkdirSync(path.join(proj, "build"), { recursive: true });

// ---------------------------------------------------------------- words and time refs
const norm = (s) => String(s).toLowerCase().replace(/ё/g, "е").replace(/[^\p{L}\p{N}]+/gu, "");
const fixes = Object.fromEntries(Object.entries(spec.fixes || {}).map(([k, v]) => [norm(k), v]));
const wj = JSON.parse(fs.readFileSync(path.resolve(proj, spec.words || "build/words.json"), "utf8"));
const WORDS = wj.segments.flatMap((s) => s.words || []).map((w) => {
  const raw = w.word.trim();
  const fixed = fixes[norm(raw)] ?? raw;
  return { word: fixed, n: norm(fixed), start: w.start, end: w.end };
});
if (!WORDS.length) die("no words in " + (spec.words || "build/words.json"));
// built-in UI labels follow the voice-over's language (Russian when the words are Cyrillic, else English)
const RU = WORDS.filter((w) => /[\u0400-\u04FF]/.test(w.word)).length * 2 > WORDS.length;
const UI = RU ? { reply: "Ответить", now: "сейчас", lang: "ru" } : { reply: "Reply", now: "now", lang: "en" };
const LAST_END = WORDS.at(-1).end;

// "word", "word#2" (2nd occurrence), "^word" (its end), "word+0.12" / "word-0.1" (offset), a number (VO seconds).
// Without #n a word matches its first occurrence at or after `after` (the previous ref in list order, minus 0.3 s).
function T(ref, after = 0, what = "") {
  if (ref === undefined || ref === null) return undefined;
  if (typeof ref === "number") return ref;
  const m = String(ref).match(/^(\^)?(.+?)(?:#(\d+))?([+-]\d*\.?\d+)?$/u);
  if (!m) die(`bad time ref "${ref}" (${what})`);
  const [, end, w, n, off] = m;
  if (/^-?\d*\.?\d+$/.test(w) && !WORDS.some((x) => x.n === norm(w))) return parseFloat(w) + (off ? parseFloat(off) : 0);
  const key = norm(w);
  let hit;
  if (n) hit = WORDS.filter((x) => x.n === key)[parseInt(n, 10) - 1];
  else hit = WORDS.find((x) => x.n === key && x.start >= after - 0.3) || WORDS.find((x) => x.n === key);
  if (!hit) die(`word "${w}"${n ? " #" + n : ""} not in the voice (${what}); words: ${WORDS.map((x) => x.word).join(" ")}`);
  return (end ? hit.end : hit.start) + (off ? parseFloat(off) : 0);
}
// the spoken time of an on-screen text's first word, searched in [from - 0.3, from + span]
function spoken(text, from, span = 4, what = "") {
  const k = norm(String(text).split(/\s+/)[0]);
  const hit = WORDS.find((x) => x.n === k && x.start >= from - 0.3 && x.start <= from + span);
  if (!hit) { warn.push(`${what}: "${text}" not spoken within ${span}s of ${from.toFixed(2)}; shown at ${from.toFixed(2)} (give it an "at")`); return from; }
  return hit.start;
}
// a big word's first segment lands on its own spoken time inside the block, never before the block start; if it is
// not spoken there (a paraphrase) it keeps the block start. It used to take the block start always, so a block keyed
// to a small word said first ("every street" -> "uphill") showed the big word 0.2-0.56 s before the voice said it.
function firstSpoken(text, t, t1) {
  const k = norm(String(text).split(/\s+/)[0]);
  const hit = WORDS.find((x) => x.n === k && x.start >= t - 0.3 && x.start <= t + 2.5 && (t1 === undefined || x.start < t1 - 0.1));
  return hit ? Math.max(t, hit.start) : t;
}

// ---------------------------------------------------------------- assets
const copyIn = (rel, sub) => {
  const src = path.resolve(proj, rel);
  if (!fs.existsSync(src)) die(`asset not found: ${rel}`);
  const dst = path.join(A, sub, path.basename(src));
  const out = sub ? `assets/${sub}/${path.basename(src)}` : `assets/${path.basename(src)}`;
  if (path.resolve(src) !== path.resolve(dst)) {
    try { if (fs.existsSync(dst)) fs.unlinkSync(dst); fs.linkSync(src, dst); } catch { fs.copyFileSync(src, dst); }
  }
  return out;
};
const probeDur = (p) => parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).toString());
const clipCache = {};
function clip(name) {
  if (clipCache[name]) return clipCache[name];
  const dir = spec.clips || "clips";
  const cands = [name, path.join(dir, name), path.join(dir, name + ".mp4"), path.join(dir, name + ".mov")];
  const rel = cands.find((c) => fs.existsSync(path.resolve(proj, c)));
  if (!rel) die(`clip "${name}" not found in ${dir}/`);
  const src = copyIn(rel, "clips");
  return (clipCache[name] = { src, frames: Math.floor(probeDur(path.resolve(proj, rel)) * FPS + 1e-6) });
}
const checkRange = (c, inF, n, what) => {
  if (inF < 0 || inF + n > c.frames) die(`${what}: needs frames ${inF}-${inF + n} of ${c.src} but it has ${c.frames}`);
};
const still = (rel) => copyIn(rel, "stills");

// fonts: Playfair Display (upright + italic), Inter Tight (roman + italic), Inter (comment card), latin + cyrillic
const RANGES = { latin: "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD", cyrillic: "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116" };
const FACES = [["Playfair Display", "normal", "playfair-display"], ["Playfair Display", "italic", "playfair-display-italic"],
  ["Inter Tight", "normal", "inter-tight"], ["Inter Tight", "italic", "inter-tight-italic"], ["Inter", "normal", "inter"]];
const fontCss = FACES.flatMap(([fam, style, stem]) => ["latin", "cyrillic"].map((r) => {
  const f = `${stem}-${r}.woff2`;
  fs.copyFileSync(path.join(SKILL, "templates", "fonts", f), path.join(A, "fonts", f));
  return `@font-face { font-family: "${fam}"; font-style: ${style}; font-weight: 100 900; src: url(assets/fonts/${f}) format("woff2"); unicode-range: ${RANGES[r]}; }`;
})).join("\n");

// ---------------------------------------------------------------- SFX by role, levelled against this voice (as build.mjs)
const sfxMan = JSON.parse(fs.readFileSync(path.join(LIB, "sfx", "manifest.json"), "utf8"));
const ROLE_DB = { ui: -14, whoosh: -12, impact: -8, meme: -3, ...(spec.mix?.roleDb || {}) };
const voiceRel = spec.voice || "assets/voice.wav";
const voicePath = path.resolve(proj, voiceRel);
if (!fs.existsSync(voicePath)) die(`voice not found: ${voiceRel} (prep.py voice)`);
const VO_DUR = probeDur(voicePath);
const voiceP95 = (() => {
  const raw = execFileSync("ffmpeg", ["-v", "error", "-i", voicePath, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], { maxBuffer: 1 << 30 });
  const x = new Float32Array(raw.buffer, raw.byteOffset, Math.floor(raw.length / 4));
  const win = 800, pk = [];
  for (const w of WORDS) for (let i = Math.floor(w.start * 16000); i + win <= w.end * 16000; i += win) {
    let m = 0;
    for (let j = i; j < i + win; j++) m = Math.max(m, Math.abs(x[j]));
    pk.push(m);
  }
  pk.sort((a, b) => a - b);
  return 20 * Math.log10(Math.max(pk[Math.floor(pk.length * 0.95)] || 0.3, 1e-6));
})();
const PROFILE = spec.sfx || "restrained"; // reference | restrained | standard | none
const LEVEL = { reference: 0, restrained: 1, standard: 2, none: -1 }[PROFILE];
if (LEVEL === undefined) die(`sfx profile "${PROFILE}": use reference | restrained | standard | none`);
const sfxEvents = [];
// lvl: 0 = the reference's own hits (hook, photo fly-in, outro send), 1 = one per block, 2 = every sticker / swap / item
function sfx(t, id, why, lvl, db = 0, explicit) {
  if (explicit === false || explicit === "none") return;
  if (explicit) { for (const e of [].concat(explicit)) sfx(t, e, why + " (list.json)", -1, db); return; }
  if (lvl > LEVEL) return;
  const m = sfxMan[id];
  if (!m) die(`sfx "${id}" not in library/sfx/manifest.json (${why})`);
  const role = ROLE_DB[m.role] !== undefined ? m.role : "ui";
  const near = sfxEvents.find((e) => Math.abs(e.t - t) < 0.3);
  if (near && lvl >= 0) { warn.push(`sfx ${id} at ${t.toFixed(2)} (${why}) dropped: ${near.id} at ${near.t} is within 0.3 s`); return; }
  fs.copyFileSync(path.join(LIB, "sfx", m.file), path.join(A, "sfx", m.file));
  const vol = r3(Math.min(1, Math.pow(10, (voiceP95 + ROLE_DB[role] + db + 1) / 20)));
  sfxEvents.push({ t: r3(Math.max(0, t)), id, role, vol, dur: m.duration, src: `assets/sfx/${m.file}`, why });
  if (m.review) warn.push(`sfx ${id}: ${m.review}`);
}

// ---------------------------------------------------------------- timeline collection
const L = []; // {at, code}
const ft = (sel, from, to, at) => L.push({ at, code: `ft(${JSON.stringify(sel)}, ${JSON.stringify(from)}, ${JSON.stringify(to)}, ${r3(at)});` });
const st = (sel, props, at) => L.push({ at, code: `tl.set(${JSON.stringify(sel)}, ${JSON.stringify(props)}, ${r3(at)});` });
const raw = (at, code) => L.push({ at, code });
// a hard visibility window for an untimed block (inline hidden; a set at 0 would not render frame 0)
const windowed = (id, t0, t1) => {
  if (t0 > 0.5 / FPS) st(`#${id}`, { visibility: "visible" }, t0);
  st(`#${id}`, { visibility: "hidden" }, t1);
  return t0 > 0.5 / FPS ? "visibility:hidden;" : "";
};
const BLUR_IN = (t, sel, d = 0.22, y = 10) => ft(sel, { opacity: 0, filter: "blur(16px)", y }, { opacity: 1, filter: "blur(0px)", y: 0, duration: d, ease: "power2.out" }, t);
const FADE_OUT = (t, sel, d = 0.12) => ft(sel, { opacity: 1 }, { opacity: 0, duration: d, ease: "power1.in" }, t - d);

const EMO = (() => { try { return emojiManifest(); } catch { return {}; } })();
const emojiUsed = new Set();
const emojiItem = (slug, what) => {
  const it = EMO[slug];
  if (!it) die(`emoji "${slug}" not in library/emoji (${what}); have: ${Object.keys(EMO).join(", ")}. Add it to set.json and run emoji_fetch.py`);
  emojiUsed.add(slug);
  return it;
};
// an inline Fluent emoji inside text (comment card, highlight): a timed WebM in an untimed span
const inlineEmoji = (id, slug, t0, t1, size, what) => {
  const it = emojiItem(slug, what);
  const media = it.kind === "animated"
    ? `<video id="${id}-v" src="assets/emoji/${slug}.webm" data-start="${fgrid(F(t0))}" data-duration="${fgrid(Math.max(1, Math.min(F(t1) - F(t0), Math.floor((it.webmSeconds || 6) * FPS))))}" data-track-index="5" muted playsinline></video>`
    : `<img id="${id}-v" src="assets/emoji/${slug}.png" alt="${esc(it.glyph || slug)}">`;
  return `<span class="iemo" id="${id}" style="width:${size}px;height:${size}px">${media}</span>`;
};
const sticker = (pid, s, i, t0, t1, cursor, what, anchor) => {
  const id = `${pid}-st${i}`;
  // default: just after the big word lands (anchor), else just after the page opens; 0.12 s apart
  const at = s.at !== undefined ? T(s.at, cursor, what) : (anchor ?? t0 + 0.17) + 0.08 + 0.12 * i;
  const size = s.size || 150;
  const end = Math.min(t1, s.to !== undefined ? T(s.to, at, what) : t1) - at;
  const item = emojiItem(s.emoji, what);
  const html = emojiPopHtml({ id, slug: s.emoji, item, x: s.x - size / 2, y: s.y - size / 2, size, at: r3(at), dur: r3(end) });
  raw(at, emojiPopJs({ id, at: r3(at), dur: r3(end), side: s.x > 540 ? "right" : "left", kind: item.kind }));
  sfx(at, "pop-1", `${what} sticker ${s.emoji}`, i === 0 ? 1 : 2, -2, s.sfx);
  return html;
};

// ---------------------------------------------------------------- the base montage
const TOTAL_F = F(LAST_END + (spec.tail ?? 1.0));
const TOTAL = TOTAL_F / FPS;
if (!spec.shots?.length) die("list.json has no shots");
let cur = 0;
const shots = spec.shots.map((s, i) => {
  const t = i === 0 ? 0 : T(s.at, cur, `shot ${i}`);
  cur = t;
  return { ...s, i, f0: i === 0 ? 0 : F(t), c: clip(s.clip), inF: F(s.in ?? 0) };
});
shots.forEach((s, i) => { s.f1 = i + 1 < shots.length ? shots[i + 1].f0 : TOTAL_F; s.n = s.f1 - s.f0; });
for (const s of shots) {
  if (s.n <= 0) die(`shot ${s.i} (${s.clip}) has no frames: check the order of shot times`);
  checkRange(s.c, s.inF, s.n, `shot ${s.i} ${s.clip}`);
}
const shotAt = (f) => shots.find((s) => f >= s.f0 && f < s.f1) || shots.at(-1);
let baseHtml = shots.map((s) => {
  if (s.zoom) ft(`#s${s.i}w`, { scale: s.zoom[0] }, { scale: s.zoom[1], duration: r3(s.n / FPS), ease: "none" }, s.f0 / FPS);
  return `<div class="shot" id="s${s.i}w"><video id="s${s.i}" src="${s.c.src}" data-start="${fgrid(s.f0)}" data-duration="${fgrid(s.n)}" data-media-start="${fgrid(s.inF)}" data-track-index="0" muted playsinline></video></div>`;
}).join("\n  ");

// transitions INTO a shot ("tx": "zoom_blur" | any transitions.py curated name): an ffmpeg window clip over the cut
const txOut = [];
for (const s of shots) {
  if (!s.tx || s.i === 0) continue;
  const p = shots[s.i - 1];
  const tout = (p.inF + p.n) / FPS, tin = s.inF / FPS;
  const key = `${p.clip}@${tout.toFixed(6)}|${s.clip}@${tin.toFixed(6)}|${s.tx}|${s.txDur ?? ""}`;
  const out = path.join(A, "tx", `tx-${s.i}.mp4`), side = out + ".json";
  let r = fs.existsSync(side) && fs.existsSync(out) ? JSON.parse(fs.readFileSync(side, "utf8")) : null;
  if (!r || r.key !== key) {
    const py = `import sys, json; sys.path.insert(0, ${JSON.stringify(path.join(SKILL, "scripts"))}); import transitions as T
r = T.render_junction(sys.argv[1], float(sys.argv[2]), sys.argv[3], float(sys.argv[4]), sys.argv[5], None, (float(sys.argv[7]) if sys.argv[7] else None), sys.argv[6], fps=${FPS})
print(json.dumps({k: r[k] for k in ("L", "R", "d", "engine", "spec")}))`;
    const res = pySpawnSync(["-c", py, path.resolve(proj, p.c.src), String(tout), path.resolve(proj, s.c.src), String(tin), s.tx, out, String(s.txDur ?? "")], { encoding: "utf8" });
    if (res.status) die(`transitions.py ${s.tx} into shot ${s.i} failed: ${res.stderr.slice(-600)}`);
    r = { ...JSON.parse(res.stdout.trim().split("\n").at(-1)), key };
    fs.writeFileSync(side, JSON.stringify(r));
  }
  const Lf = Math.round(r.L * FPS), nf = Math.round(r.d * FPS);
  const start = s.f0 - Lf;
  baseHtml += `\n  <div class="shot"><video id="tx-${s.i}" src="assets/tx/tx-${s.i}.mp4" data-start="${fgrid(start)}" data-duration="${fgrid(nf)}" data-media-start="0" data-track-index="1" muted playsinline></video></div>`;
  txOut.push({ id: `tx-${s.i}`, src: `assets/tx/tx-${s.i}.mp4`, start: r3(start / FPS), duration: r3(nf / FPS), frames: nf, after: s.i - 1, type: s.tx, engine: r.engine });
  sfx(s.f0 / FPS - 0.12, s.txSfx || "whoosh-3", `${s.tx} into shot ${s.i}`, 1, -2);
}
fs.writeFileSync(path.join(proj, "build", "transitions.json"), JSON.stringify(txOut, null, 1));

// ---------------------------------------------------------------- beats
const SCENES = new Set(["collage", "triptych", "window", "flash", "imessage"]);
const TEXTS = new Set(["word", "list", "highlight"]);
let bc = 0;
const beats = (spec.beats || []).map((b, i) => {
  const at = b.type === "imessage" && b.at === undefined ? T(b.word, bc, `beat ${i} imessage`) - (b.lead ?? 1.05)
    : T(b.at ?? (typeof b.big === "string" ? b.big : undefined) ?? b.word, bc, `beat ${i} ${b.type}`);
  if (at === undefined) die(`beat ${i} (${b.type}) has no "at"`);
  bc = at;
  return { ...b, i, t0: at };
});
beats.sort((a, b) => a.t0 - b.t0);
for (const b of beats) {
  if (b.to !== undefined) { b.t1 = T(b.to, b.t0, `beat ${b.i} to`); continue; }
  const same = TEXTS.has(b.type) ? TEXTS : SCENES.has(b.type) ? SCENES : new Set([b.type]);
  const nxt = beats.find((x) => x.t0 > b.t0 + 0.05 && (same.has(x.type) || (TEXTS.has(b.type) && SCENES.has(x.type))));
  const cap = b.type === "imessage" ? TOTAL : b.t0 + (SCENES.has(b.type) ? 6 : 2.4);
  b.t1 = Math.min(nxt ? nxt.t0 - 0.02 : TOTAL, cap);
}
for (const b of beats) {
  if (SCENES.has(b.type)) { b.t0 = F(b.t0) / FPS; b.t1 = Math.min(TOTAL, F(b.t1) / FPS); }
  if (!(b.t1 > b.t0)) die(`beat ${b.i} (${b.type}) ends before it starts (${b.t0.toFixed(2)} -> ${b.t1.toFixed(2)})`);
}
const keyTimes = []; // for snap.py: {id, type, label, t0, t1, keys:[...]}
const html = { scene: [], text: [], over: [], top: [] };

// big + sub text, shared by word beats, flashes and collage pages
const FAM = { serif: "serif", "serif-up": "serif-up", sans: "sans", "sans-it": "sans-it" };
function bigHtml(id, b, t, onPaper, what) {
  const fam = FAM[b.family || "serif"] || die(`${what}: family "${b.family}" (serif | serif-up | sans | sans-it)`);
  const size = b.size || (fam.startsWith("serif") ? 150 : 140) * (b.caps ? 0.9 : 1);
  const segs = Array.isArray(b.big) ? b.big : String(b.big).split(/\s+/).map((text) => ({ text }));
  let cursor = t;
  const spans = segs.map((sg, k) => {
    const sid = `${id}-b${k}`;
    const at = sg.at !== undefined ? T(sg.at, cursor, what) : b.together ? t + 0.1 * k : k === 0 ? firstSpoken(sg.text, t, b.t1) : spoken(sg.text, cursor, 2.5, what);
    cursor = Math.max(cursor, at);
    BLUR_IN(at, `#${sid}`);
    const f2 = FAM[sg.family || fam] || fam;
    return `<span id="${sid}" class="${f2}" style="font-size:${sg.size || size}px${sg.color || b.color ? `;color:${sg.color || b.color}` : ""}">${esc(b.caps ? sg.text.toUpperCase() : sg.text)}</span>`;
  });
  const subs = [].concat(b.sub || []).map((x) => (typeof x === "string" ? { text: x } : x));
  const subHtml = subs.map((sb, k) => {
    const sid = `${id}-u${k}`;
    const pos = sb.pos || b.subPos || "below-right";
    const ss = sb.size || b.subSize || 54;
    const at = sb.at !== undefined ? T(sb.at, t - 1, what) : sb.together || b.together ? t + 0.1 * (segs.length + k) : spoken(sb.text, t - 1.2, 4, what);
    BLUR_IN(at, `#${sid}`, 0.2, 6);
    // offsets in units of the big word's size (--bs, rescaled by the page's fit()), so a sub stays tucked under / over
    // the big word whatever size it ends up at
    const v = pos.startsWith("above") ? "bottom:calc(100% - var(--bs) * 0.1)" : "top:calc(100% - var(--bs) * 0.17)";
    const h = pos.endsWith("left") ? "left:calc(var(--bs) * 0.03)" : pos.endsWith("right") ? "right:calc(var(--bs) * 0.03)" : "left:-400px;right:-400px;text-align:center";
    const fam2 = FAM[sb.family || "sans"] || "sans";
    return `<div class="subpos" style="${v};${h}"><span id="${sid}" class="sub ${fam2 === "sans" ? "" : fam2}" style="font-size:${ss}px${sb.color ? `;color:${sb.color}` : ""}">${esc(sb.caps ? sb.text.toUpperCase() : sb.text)}</span></div>`;
  }).join("");
  // width target: the reference sizes every big word to roughly the same on-screen width (short words get bigger);
  // fit() in the page scales the big spans to it (x0.6-1.7). width: 0 keeps "size" exactly.
  const target = b.width ?? (fam.startsWith("serif") ? 660 : 620);
  return `<div class="wb-fit" data-max="${b.maxWidth || 960}"><div class="wb-in ${onPaper ? "on-paper" : "on-foot"}" data-fit="${target}" style="gap:${Math.round(size * 0.2)}px;--bs:${size}px">${spans.join("")}${subHtml}</div></div>`;
}

for (const b of beats) {
  const id = `b${b.i}`;
  const what = `beat ${b.i} ${b.type}`;
  const keys = [b.t0 + 0.3, Math.min(b.t1 - 0.1, b.t0 + 1.0)];
  if (b.type === "word") {
    const y = Math.round((b.y ?? 0.5) * H);
    const vis = windowed(id, b.t0, b.t1);
    html.text.push(`<div id="${id}" class="wb" style="${vis}top:${y}px">${bigHtml(id, b, b.t0, false, what)}</div>`);
    FADE_OUT(b.t1, `#${id}`);
    sfx(b.t0, b.sfxId || "whoosh-cine", what, b.i === beats[0].i ? 0 : 2, -3, b.sfx);
  } else if (b.type === "list") {
    const size = b.size || 104, gap = Math.round(size * (b.lineGap ?? 0.92));
    const items = b.items.map((x) => (typeof x === "string" ? { text: x } : x));
    const y0 = Math.round((b.y ?? 0.5) * H - ((items.length - 1) * gap) / 2);
    const vis = windowed(id, b.t0, b.t1);
    let c = b.t0;
    const rows = items.map((it, k) => {
      const at = it.at !== undefined ? T(it.at, c, what) : k === 0 ? b.t0 : spoken(it.text, c, 3, what);
      c = at;
      BLUR_IN(at, `#${id}-i${k}`);
      sfx(at, "tick-1", `${what} item`, 2, -4, it.sfx);
      keys.push(at + 0.3);
      return `<div class="wb" style="top:${y0 + k * gap}px"><div class="wb-fit" data-max="980"><div class="wb-in on-foot"><span id="${id}-i${k}" class="${FAM[b.family || "sans"]}" style="font-size:${size}px">${esc(b.caps ? it.text.toUpperCase() : it.text)}</span></div></div></div>`;
    });
    html.text.push(`<div id="${id}" class="layer" style="${vis}">${rows.join("")}</div>`);
    FADE_OUT(b.t1, `#${id}`);
  } else if (b.type === "highlight") {
    const size = b.size || 84, gap = Math.round(size * 1.04);
    const items = b.items.map((x) => (typeof x === "string" ? { text: x } : x));
    const y0 = Math.round((b.y ?? 0.47) * H - ((items.length - 1) * gap) / 2 - size * 0.6);
    const vis = windowed(id, b.t0, b.t1);
    let c = b.t0;
    const rows = items.map((it, k) => {
      const at = it.at !== undefined ? T(it.at, c, what) : k === 0 ? b.t0 : spoken(it.text, c, 3, what);
      c = at;
      ft(`#${id}-i${k}`, { clipPath: "inset(0% 100% 0% 0% round 16px)", opacity: 0 }, { clipPath: "inset(0% 0% 0% 0% round 16px)", opacity: 1, duration: 0.2, ease: "power2.out" }, at);
      sfx(at, "pop-3", `${what} item`, k === 0 ? 1 : 2, -2, it.sfx);
      keys.push(at + 0.3);
      const emo = it.emoji ? inlineEmoji(`${id}-e${k}`, it.emoji, at, b.t1, Math.round(size * 0.95), what) : "";
      const align = b.align === "center" ? "left:0;right:0;justify-content:center" : `left:${b.x ?? 96}px`;
      return `<div class="hlrow" style="top:${y0 + k * gap}px;${align}"><div id="${id}-i${k}" class="hl" style="font-size:${size}px;background:${BLUE}"><span>${esc(it.text)}</span>${emo}</div></div>`;
    });
    html.text.push(`<div id="${id}" class="layer" style="${vis}">${rows.join("")}</div>`);
    FADE_OUT(b.t1, `#${id}`);
  } else if (b.type === "flash") {
    const vis = windowed(id, b.t0, b.t1);
    const fb = { ...b, big: b.text, family: b.family || "sans", size: b.size || 92, width: b.width ?? 0 };
    html.scene.push(`<div id="${id}" class="page white" style="${vis}"><div class="wb" style="top:${Math.round((b.y ?? 0.48) * H)}px">${bigHtml(id, { ...fb, together: true }, b.t0 - 0.2, true, what)}</div></div>`);
    sfx(b.t0, "pop-2", what, 2, -6, b.sfx);
  } else if (b.type === "collage") {
    const vis = windowed(id, b.t0, b.t1);
    const parts = [];
    let cursor = b.t0;
    const bigT = b.big ? (b.big.at !== undefined ? T(b.big.at, b.t0, what) : spoken(typeof b.big === "string" ? b.big : b.big.text, b.t0, 4, what)) : null;
    // 1. the current shot shrinks into a card on white, then dissolves when the big word lands
    if (b.shrink) {
      const P = F(b.t0), s = shotAt(P);
      const endT = b.shrink.until !== undefined ? T(b.shrink.until, b.t0, what) : bigT ?? b.t1;
      const endF = Math.min(F(endT + 0.3), F(b.t1));
      const mf = s.inF + (P - s.f0);
      checkRange(s.c, mf, endF - P, `${what} shrink card`);
      const sc = b.shrink.scale || 0.63;
      parts.push(`<div class="cardshot" id="${id}-card"><video id="${id}-cv" src="${s.c.src}" data-start="${fgrid(P)}" data-duration="${fgrid(endF - P)}" data-media-start="${fgrid(mf)}" data-track-index="2" muted playsinline></video></div>`);
      ft(`#${id}-card`, { scale: 1, borderRadius: 0 }, { scale: sc, borderRadius: Math.round(22 / sc), duration: 0.32, ease: "power3.inOut" }, P / FPS);
      ft(`#${id}-card`, { opacity: 1, filter: "blur(0px)" }, { opacity: 0, filter: "blur(18px)", duration: 0.28, ease: "power1.in" }, endT - 0.04);
      keys.push(P / FPS + 0.4);
    }
    // 2. the small line (word by word): above the shrinking card, then (with a big word) it drops under it
    const line = b.line ? (typeof b.line === "string" ? { text: b.line } : b.line) : null;
    const photo = b.photo ? (typeof b.photo === "string" ? { src: b.photo } : b.photo) : null;
    const PH = photo ? { w: photo.w || 792, h: photo.h || 446, y: Math.round((photo.y ?? 0.5) * H) } : null;
    if (line) {
      const lsize = line.size || (photo ? 88 : 58);
      const ly = photo ? PH.y - PH.h / 2 - Math.round(lsize * 0.72) : b.shrink ? Math.round(H / 2 - (H * (b.shrink.scale || 0.63)) / 2 - 58) : Math.round(0.46 * H) + 96;
      const ws = line.text.split(/\s+/);
      let c = line.at !== undefined ? T(line.at, cursor, what) : spoken(ws[0], cursor, 4, what);
      const spans = ws.map((w, k) => {
        const at = k === 0 ? c : (c = spoken(w, c, 2, what));
        BLUR_IN(at, `#${id}-l${k}`, 0.18, 6);
        return `<span id="${id}-l${k}" class="${FAM[line.family || "sans"]}" style="font-size:${lsize}px">${esc(w)}</span>`;
      });
      parts.push(`<div class="wb" id="${id}-line" style="top:${ly}px"><div class="wb-fit" data-max="980"><div class="wb-in on-paper" style="gap:${Math.round(lsize * 0.24)}px">${spans.join("")}</div></div></div>`);
      if (bigT !== null && !photo) ft(`#${id}-line`, { opacity: 1, y: 0, filter: "blur(0px)" }, { opacity: 0, y: 70, filter: "blur(10px)", duration: 0.2, ease: "power2.in" }, bigT - 0.06);
    }
    // 3. the photo card flies in tilted and lands straight
    if (photo) {
      const pt = photo.at !== undefined ? T(photo.at, b.t0, what) : b.t0 + 0.05;
      const src = photo.src ? still(photo.src) : (() => { die(`${what}: photo needs "src" (prep.py still CLIP T stills/x.jpg)`); })();
      parts.push(`<div class="photo" id="${id}-ph" style="left:${(W - PH.w) / 2}px;top:${PH.y - PH.h / 2}px;width:${PH.w}px;height:${PH.h}px"><img src="${src}" alt=""></div>`);
      ft(`#${id}-ph`, { x: 380, y: 160, rotation: photo.tilt ?? 16, scale: 0.78, opacity: 0 }, { x: 0, y: 0, rotation: 0, scale: 1, opacity: 1, duration: 0.5, ease: "back.out(1.3)" }, pt);
      sfx(pt - 0.05, "whoosh-1", `${what} photo card`, 0, -2, photo.sfx);
      keys.push(pt + 0.6);
    }
    // 4. the big word: a red glitch entrance (ghost copies snap in on a stepped ease) or a plain blur-in
    if (b.big) {
      const bg = typeof b.big === "string" ? { text: b.big } : b.big;
      const by = photo ? PH.y + PH.h / 2 + Math.round((bg.size || 112) * 0.62) : Math.round((bg.y ?? 0.46) * H);
      const sub = bg.sub ?? (line && !photo ? { text: line.text, pos: "below-right", size: 44, family: "sans", at: bigT + 0.12 } : undefined);
      const beat = { big: [{ text: bg.text, at: bigT }], family: bg.family || "serif", size: bg.size || (photo ? 112 : 128), color: bg.color, caps: bg.caps, sub, subSize: 44 };
      const inner = bigHtml(`${id}-g`, beat, bigT, true, what);
      let ghosts = "";
      if (bg.glitch) {
        const col = bg.color || "#FF3B30";
        ghosts = [["gh1", "#FF8A80", -34], ["gh2", "#FF1744", 28]].map(([g, c2, dx], k) => {
          ft(`#${id}-${g}`, { x: dx, opacity: 0, filter: "blur(6px)" }, { x: dx, opacity: 0.85, filter: "blur(6px)", duration: 0.02, ease: "none" }, bigT - 0.02 + 0.02 * k);
          ft(`#${id}-${g}`, { x: dx, opacity: 0.85, filter: "blur(6px)" }, { x: 0, opacity: 0, filter: "blur(0px)", duration: 0.32, ease: "steps(6)" }, bigT + 0.02 * k);
          return `<div class="wb ghost" id="${id}-${g}" style="top:${by}px"><div class="wb-fit" data-max="${bg.maxWidth || 960}"><div class="wb-in"><span class="${FAM[beat.family]}" style="font-size:${beat.size}px;color:${c2}">${esc(bg.caps ? bg.text.toUpperCase() : bg.text)}</span></div></div></div>`;
        }).join("");
        beat.glow = col;
        sfx(bigT, "tech-glitch-1", `${what} glitch word`, 1, -4, bg.sfx);
      }
      parts.push(`${ghosts}<div class="wb${bg.glitch ? " glow" : ""}" id="${id}-big" style="top:${by}px${bg.glitch ? `;--glow:${bg.color || "#FF3B30"}` : ""}">${inner}</div>`);
      keys.push(bigT + 0.4);
    }
    // 5. stickers (Fluent emoji)
    (b.stickers || []).forEach((s, k) => { parts.push(sticker(id, s, k, b.t0, b.t1, b.t0, what, bigT ?? undefined)); keys.push((s.at !== undefined ? T(s.at, b.t0, what) : (bigT ?? b.t0 + 0.17) + 0.08) + 0.5); });
    html.scene.push(`<div id="${id}" class="page white" style="${vis}">${parts.join("")}</div>`);
  } else if (b.type === "triptych") {
    const vis = windowed(id, b.t0, b.t1);
    const P = F(b.t0), n = F(b.t1) - P;
    const bands = b.clips.map((cl, k) => {
      const c = clip(cl.clip), inF = F(cl.in ?? 0);
      checkRange(c, inF, n, `${what} band ${k}`);
      if (b.stagger) ft(`#${id}-k${k}`, { yPercent: k % 2 ? 100 : -100 }, { yPercent: 0, duration: 0.25, ease: "power3.out" }, b.t0 + b.stagger * k);
      return `<div class="band" id="${id}-k${k}" style="top:${k * 640}px"><video id="${id}-v${k}" src="${c.src}" data-start="${fgrid(P)}" data-duration="${fgrid(n)}" data-media-start="${fgrid(inF)}" data-track-index="2" muted playsinline style="object-position:50% ${cl.pos ?? 50}%"></video></div>`;
    });
    html.scene.push(`<div id="${id}" class="page black" style="${vis}">${bands.join("")}</div>`);
  } else if (b.type === "comment") {
    const vis = windowed(id, b.t0, b.t1);
    const ws = b.text.split(/\s+/);
    let c = b.t0;
    const spans = ws.map((w, k) => {
      const at = k === 0 ? (b.at !== undefined ? b.t0 : spoken(w, b.t0, 2, what)) : (c = spoken(w, c, 2.5, what));
      if (k === 0) c = at;
      ft(`#${id}-w${k}`, { opacity: 0 }, { opacity: 1, duration: 0.1, ease: "none" }, at);
      return `<span id="${id}-w${k}">${esc(w)}</span>`;
    });
    const et = Math.min(c + 0.12, b.t1 - 0.3);
    const emo = b.emoji ? inlineEmoji(`${id}-emo`, b.emoji, et, b.t1, 64, what) : "";
    if (b.emoji) ft(`#${id}-emo`, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.3, ease: "back.out(2.5)" }, et);
    const av = b.avatar ? `<img class="cm-av" src="${still(b.avatar)}" alt="">` : `<div class="cm-av"></div>`;
    const y = Math.round((b.y ?? 0.5) * H);
    html.over.push(`<div id="${id}" class="cmrow" style="${vis}top:${y}px"><div class="cm" id="${id}-card">${av}<div class="cm-body"><div class="cm-text">${spans.join(" ")} ${emo}</div><div class="cm-reply" id="${id}-r">${esc(b.reply ?? UI.reply)}</div></div></div></div>`);
    ft(`#${id}-card`, { scale: 0.86, opacity: 0, y: 30 }, { scale: 1, opacity: 1, y: 0, duration: 0.32, ease: "back.out(1.7)" }, b.t0 - 0.08);
    ft(`#${id}-r`, { opacity: 0 }, { opacity: 1, duration: 0.2 }, c + 0.3);
    FADE_OUT(b.t1, `#${id}`, 0.15);
    sfx(b.t0 - 0.08, b.sfxId || "tech-notification-2", `${what} card`, 1, 0, b.sfx);
    keys.push(c + 0.6);
  } else if (b.type === "notify") {
    // an iOS notification banner (a number or a fact and where it comes from): dark frosted card that drops in from the
    // top, an app tile (Fluent emoji), app name + time, a bold title, the body typed word by word on the voice
    const vis = windowed(id, b.t0, b.t1);
    const ws = (b.text || "").split(/\s+/).filter(Boolean);
    let c = b.t0;
    const spans = ws.map((w, k) => {
      const at = k === 0 ? (b.textAt !== undefined ? T(b.textAt, b.t0, what) : spoken(w, b.t0, 3, what)) : (c = spoken(w, c, 2.5, what));
      if (k === 0) c = at;
      ft(`#${id}-w${k}`, { opacity: 0 }, { opacity: 1, duration: 0.1, ease: "none" }, at);
      return `<span id="${id}-w${k}">${esc(w)}</span>`;
    });
    const ta = b.titleAt !== undefined ? T(b.titleAt, b.t0, what) : b.t0;
    const icon = b.emoji ? inlineEmoji(`${id}-ic`, b.emoji, b.t0 - 0.1, b.t1, 70, what) : "";
    const y = Math.round((b.y ?? 0.19) * H);
    html.over.push(`<div id="${id}" class="ntrow" style="${vis}top:${y}px"><div class="nt" id="${id}-card"><div class="nt-ic"${b.tile ? ` style="background:${b.tile}"` : ""}>${icon}</div><div class="nt-body"><div class="nt-hd"><b>${esc(b.app || "")}</b><span>${esc(b.time ?? UI.now)}</span></div><div class="nt-title" id="${id}-t">${esc(b.title || "")}</div><div class="nt-text">${spans.join(" ")}</div></div></div></div>`);
    ft(`#${id}-card`, { y: -300, opacity: 0, scale: 0.96 }, { y: 0, opacity: 1, scale: 1, duration: 0.42, ease: "back.out(1.25)" }, b.t0 - 0.1);
    ft(`#${id}-t`, { opacity: 0, filter: "blur(6px)" }, { opacity: 1, filter: "blur(0px)", duration: 0.18, ease: "power2.out" }, ta);
    ft(`#${id}-card`, { y: 0, opacity: 1 }, { y: -260, opacity: 0, duration: 0.28, ease: "power2.in", immediateRender: false }, b.t1 - 0.28);
    sfx(b.t0 - 0.1, b.sfxId || "tech-notification-2", `${what} banner`, 1, 0, b.sfx);
    keys.push(c + 0.5);
  } else if (b.type === "window") {
    const vis = windowed(id, b.t0, b.t1);
    const P = F(b.t0), n = F(b.t1) - P;
    const c = clip(b.bg.clip), inF = F(b.bg.in ?? 0);
    checkRange(c, inF, n, `${what} background`);
    const WW = b.w || 720, WH = b.h || 520, wx = (W - WW) / 2, wy = Math.round((b.y ?? 0.5) * H - WH / 2);
    // the glass is a blurred second copy of the background, one frame later (the window is invisible on frame 0 of its
    // fade-in): identical src/start/duration pairs trip hyperframes' duplicate_media_discovery_risk
    const v = (vid, cls, style = "", d = 0) => `<video id="${vid}" class="${cls}" src="${c.src}" data-start="${fgrid(P + d)}" data-duration="${fgrid(n - d)}" data-media-start="${fgrid(inF + d)}" data-track-index="${2 + d}" muted playsinline${style}></video>`;
    let ci = b.t0;
    const items = b.items.map((it, k) => {
      const at = it.at !== undefined ? T(it.at, ci, what) : k === 0 ? b.t0 : ci + 1;
      ci = at;
      return { ...it, at };
    });
    const itemsHtml = items.map((it, k) => {
      const tIn = k === 0 ? b.t0 + 0.12 : it.at;
      ft(`#${id}-i${k}`, { opacity: 0, scale: 0.9, filter: "blur(12px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.24, ease: "power3.out" }, tIn);
      ft(`#${id}-g${k}`, { opacity: 0, filter: "blur(8px)" }, { opacity: 1, filter: "blur(0px)", duration: 0.2 }, tIn);
      if (k + 1 < items.length) {
        const tOut = items[k + 1].at - 0.06;
        ft(`#${id}-i${k}`, { opacity: 1, filter: "blur(0px)" }, { opacity: 0, filter: "blur(12px)", duration: 0.12 }, tOut);
        ft(`#${id}-g${k}`, { opacity: 1 }, { opacity: 0, duration: 0.1 }, tOut);
      }
      if (k) sfx(it.at, "click-1", `${what} swap`, 2, -4, it.sfx);
      keys.push(tIn + 0.35);
      const label = it.logo ? `<img src="${still(it.logo)}" alt="">` : esc(it.label || "");
      return `<div class="mw-label" id="${id}-g${k}">${label}</div><div class="mw-item" id="${id}-i${k}"><img src="${still(it.img)}" alt=""></div>`;
    }).join("");
    html.scene.push(`<div id="${id}" class="page" style="${vis}">
    <div class="mw-bg">${v(`${id}-bg`, "fillv", ` style="filter:brightness(${b.dim ?? 0.58}) saturate(.9) blur(${b.bgBlur ?? 3}px);transform:scale(1.05)"`)}</div>
    <div class="mw" id="${id}-win" style="left:${wx}px;top:${wy}px;width:${WW}px;height:${WH}px">
      <div class="mw-glass">${v(`${id}-gl`, "", ` style="left:${-wx}px;top:${-wy}px;width:${W}px;height:${H}px;transform:scale(1.05)"`, 1)}</div>
      <div class="mw-tint"></div><div class="mw-dots"><i></i><i></i><i></i></div>${itemsHtml}
    </div></div>`);
    ft(`#${id}-win`, { opacity: 0, scale: 0.9, y: 40 }, { opacity: 1, scale: 1, y: 0, duration: 0.3, ease: "power3.out" }, b.t0);
    ft(`#${id}-win`, { opacity: 1, scale: 1 }, { opacity: 0, scale: 0.96, duration: 0.14 }, b.t1 - 0.14);
    sfx(b.t0, "whoosh-2", `${what} window`, 1, -4, b.sfx);
  } else if (b.type === "imessage") {
    const vis = windowed(id, b.t0, b.t1);
    const bub = T(b.at_word ?? b.word, b.t0, what);
    const typing = b.typing ?? 0.42;
    if (bub - typing < b.t0 + 0.58) warn.push(`${what}: the outro starts ${(bub - b.t0).toFixed(2)} s before "${b.word}"; give it >= ${(0.58 + typing).toFixed(2)} s (at: an earlier word) so the card can fly off before the typing bubble`);
    const tt = Math.max(bub - typing, b.t0 + 0.58);
    const parts = [];
    // the current shot shrinks into a card on black, then floats away in 3D
    const P = F(b.t0), s = shotAt(P);
    const t0 = b.t0;
    const K = [ // x, y (px from centre), scale, rotationY, rotation, blur, opacity, duration to reach it
      [0, 0, 1, 0, 0, 0, 1],
      [0, 0, 0.9, 0, 0, 0, 1, 0.22],
      [250, -560, 0.2, -26, 8, 0, 1, 0.36],
      [-170, -230, 0.22, 22, -6, 0, 1, Math.max(0.3, bub + 0.2 - (t0 + 0.58))],
      [40, -760, 0.24, -10, 4, 14, 0, 0.7],
    ];
    let tk = t0;
    for (let k = 1; k < K.length; k++) {
      const [x0, y0, s0, ry0, r0, bl0, o0] = K[k - 1], [x1, y1, s1, ry1, r1, bl1, o1, d] = K[k];
      ft(`#${id}-c0`, { x: x0, y: y0, scale: s0, rotationY: ry0, rotation: r0, filter: `blur(${bl0}px)`, opacity: o0, borderRadius: k === 1 ? 0 : 40 },
        { x: x1, y: y1, scale: s1, rotationY: ry1, rotation: r1, filter: `blur(${bl1}px)`, opacity: o1, borderRadius: 40, duration: r3(d), ease: k === 1 ? "power2.out" : "power2.inOut" }, tk);
      tk += d;
    }
    // the card's footage runs until the card has faded away (a video that ends early leaves an empty box)
    const endF = Math.min(F(tk) + 1, F(b.t1)), mf = s.inF + (P - s.f0);
    checkRange(s.c, mf, endF - P, `${what} shrink card`);
    parts.unshift(`<div class="ocard big" id="${id}-c0"><video id="${id}-cv" src="${s.c.src}" data-start="${fgrid(P)}" data-duration="${fgrid(endF - P)}" data-media-start="${fgrid(mf)}" data-track-index="2" muted playsinline></video></div>`);
    keys.push(t0 + 0.15, t0 + 0.5);
    // more photo cards from the reel, tilted, drifting in 3D
    const slots = [[790, 430, 8, -20], [250, 330, -9, 22], [840, 1420, -6, -16], [210, 1520, 7, 18]];
    (b.cards || []).forEach((cd, k) => {
      const [cx, cy, rz, ry] = slots[k % slots.length];
      const a = t0 + 0.32 + 0.14 * k, z = bub + 0.55 + 0.1 * k;
      parts.push(`<div class="ocard small" id="${id}-c${k + 1}" style="left:${cx - 140}px;top:${cy - 180}px"><img src="${still(cd.src || cd)}" alt=""></div>`);
      ft(`#${id}-c${k + 1}`, { scale: 0, opacity: 0, rotationY: ry * 2, rotation: rz * 2 }, { scale: 1, opacity: 1, rotationY: ry, rotation: rz, duration: 0.42, ease: "back.out(1.6)" }, a);
      ft(`#${id}-c${k + 1}`, { y: 0, x: 0 }, { y: -60, x: k % 2 ? 30 : -30, duration: r3(z - a), ease: "sine.inOut" }, a);
      ft(`#${id}-c${k + 1}`, { opacity: 1, filter: "blur(0px)" }, { opacity: 0, filter: "blur(14px)", duration: 0.35 }, z);
      sfx(a, "pop-2", `${what} card`, 2, -6);
    });
    // typing bubble -> the blue word bubble -> emoji tapback
    const bx = b.x ?? 150, by = Math.round((b.y ?? 0.5) * H);
    const dots = [0, 1, 2].map((k) => `<i id="${id}-d${k}"></i>`).join("");
    parts.push(`<div class="obub" id="${id}-typ" style="left:${bx}px;top:${by - 46}px;background:${b.typingColor || BLUE}"><div class="dots">${dots}</div>${tail(b.typingColor || BLUE)}</div>`);
    ft(`#${id}-typ`, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.22, ease: "back.out(2.2)" }, tt);
    ft(`#${id}-typ`, { scale: 1, opacity: 1 }, { scale: 0.6, opacity: 0, duration: 0.1, ease: "power1.in" }, bub - 0.04);
    const reps = Math.max(0, Math.floor((bub - tt) / 0.36) - 1);
    [0, 1, 2].forEach((k) => ft(`#${id}-d${k}`, { y: 0, opacity: 0.55 }, { y: -9, opacity: 1, duration: 0.18, ease: "sine.inOut", repeat: reps * 2 + 1, yoyo: true }, tt + 0.08 + 0.09 * k));
    const ex = b.emoji ? (() => {
      const it = emojiItem(b.emoji, what), at = bub + (b.tapback ?? 0.38);
      raw(at, emojiPopJs({ id: `${id}-tb`, at: r3(at), dur: r3(TOTAL - at - 0.05), side: "right", out: false, kind: it.kind }));
      sfx(at, "pop-1", `${what} tapback`, 1, -2);
      keys.push(at + 0.45);
      return `<div class="otap">${emojiPopHtml({ id: `${id}-tb`, slug: b.emoji, item: it, x: 0, y: 0, size: b.emojiSize || 124, at: r3(at), dur: r3(TOTAL - at - 0.05) })}</div>`;
    })() : "";
    parts.push(`<div class="obwrap" id="${id}-bw" style="left:${bx}px;top:${by - 85}px"><div class="obub word" style="background:${BLUE}"><span>${esc(b.word)}</span>${tail(BLUE)}</div>${ex}</div>`);
    ft(`#${id}-bw`, { scale: 0.35, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.34, ease: "back.out(2)" }, bub);
    ft(`#${id}-bw`, { opacity: 1, filter: "blur(0px)", scale: 1 }, { opacity: 0, filter: "blur(10px)", scale: 0.94, duration: 0.3 }, TOTAL - 0.32);
    sfx(bub - 0.02, b.sendSfx || "send-swoosh", `${what} send`, 0, 0, b.sfx);
    keys.push(tt + 0.25, bub + 0.4, TOTAL - 0.4);
    html.top.push(`<div id="${id}" class="page black" style="${vis}"><div class="ostage">${parts.join("")}</div></div>`);
  } else {
    die(`unknown beat type "${b.type}" (word | list | highlight | flash | collage | triptych | comment | notify | window | imessage)`);
  }
  keyTimes.push({ id, type: b.type, label: b.label || (b.big ? (typeof b.big === "string" ? b.big : b.big.text || "") : b.word || b.text || b.type), t0: r3(b.t0), t1: r3(b.t1), keys: [...new Set(keys.map((k) => r3(Math.min(Math.max(k, b.t0 + 0.04), b.t1 - 0.04))))].sort((a, c) => a - c) });
}
function tail(col) {
  return `<svg class="otail" width="46" height="40" viewBox="0 0 46 40"><path d="M30 0 C31 14 26 26 2 38 C20 40 36 34 46 22 L46 0 Z" fill="${col}"/></svg>`;
}

// ---------------------------------------------------------------- audio
if (emojiUsed.size) installEmoji(proj, [...emojiUsed], EMO);
const voiceSrc = copyIn(voiceRel, "");
const audio = [`<audio id="take-0-audio" src="${voiceSrc}" data-start="0" data-duration="${fgrid(Math.min(TOTAL_F, Math.floor(VO_DUR * FPS)))}" data-track-index="10" data-volume="1"></audio>`];
sfxEvents.sort((a, b) => a.t - b.t);
sfxEvents.forEach((e, i) => audio.push(`<audio id="sfx-${i}" src="${e.src}" data-start="${e.t}" data-duration="${r3(Math.min(e.dur, TOTAL - e.t))}" data-track-index="${12 + (i % 4)}" data-volume="${e.vol}"></audio>`));
// speech islands (gaps > 0.6 s split) for the music duck and qa.py's silence check
const islands = [];
for (const w of WORDS) {
  if (islands.length && w.start - islands.at(-1).to < 0.6) islands.at(-1).to = w.end;
  else islands.push({ from: w.start, to: w.end });
}
let musicInfo = "none";
if (spec.music) {
  const m = { db: -14, ...spec.music, duck: islands.map((x) => ({ from: r3(x.from), to: r3(x.to), db: spec.music.duck ?? -6 })) };
  const res = buildMusic(m, { r3, proj, LIB, TOTAL }, execFileSync, path, fs);
  audio.push(res.html);
  musicInfo = `${spec.music.id || spec.music.src} at ${m.db} dB vs voice (${res.I.toFixed(1)} LUFS file, volume ${res.vol}), ducked ${m.duck[0]?.db ?? -6} dB under ${islands.length} speech islands`;
}
fs.writeFileSync(path.join(proj, "build", "sfx_events.json"), JSON.stringify({ total: r3(TOTAL), speech: r3(LAST_END), voiceP95: r3(voiceP95), roleDb: ROLE_DB, events: sfxEvents }, null, 2));
fs.writeFileSync(path.join(proj, "build", "beats.json"), JSON.stringify({ total: r3(TOTAL), fps: FPS, shots: shots.map((s) => ({ i: s.i, clip: s.clip, in: r3(s.inF / FPS), t0: r3(s.f0 / FPS), t1: r3(s.f1 / FPS), tx: s.tx || null })), beats: keyTimes }, null, 1));

// ---------------------------------------------------------------- page
const CSS = `
${fontCss}
html, body { margin: 0; background: #000; }
#root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #000; font-family: "Inter Tight", sans-serif; }
.layer, .page, .shot { position: absolute; inset: 0; }
.shot { overflow: hidden; }
.shot video, .fillv, .band video, .cardshot video, .ocard video, .ocard img, .photo img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }
.page.white { background: #fff; } .page.black { background: #000; }
.wb { position: absolute; left: 0; right: 0; height: 0; display: flex; justify-content: center; align-items: center; pointer-events: none; }
.wb-fit { display: flex; justify-content: center; transform-origin: 50% 50%; }
.wb-in { position: relative; display: inline-flex; align-items: baseline; white-space: nowrap; gap: 0.2em; line-height: 1; }
.wb-in > span, .sub { display: inline-block; }
.serif { font-family: "Playfair Display"; font-style: italic; font-weight: 500; letter-spacing: -0.02em; }
.serif-up { font-family: "Playfair Display"; font-style: normal; font-weight: 500; letter-spacing: -0.04em; }
.sans { font-family: "Inter Tight"; font-style: normal; font-weight: 800; letter-spacing: -0.055em; }
.sans-it { font-family: "Inter Tight"; font-style: italic; font-weight: 800; letter-spacing: -0.05em; }
.subpos { position: absolute; white-space: nowrap; }
.sub { font-family: "Inter Tight"; font-weight: 700; letter-spacing: -0.035em; line-height: 1; }
.sub.serif { font-family: "Playfair Display"; font-style: italic; font-weight: 500; }
.on-foot { color: #fff; text-shadow: 0 0 2px rgba(0,0,0,.75), 0 0 7px rgba(0,0,0,.5), 0 2px 3px rgba(0,0,0,.26), 0 6px 34px rgba(0,0,0,.42); }
/* the tight dark halo (first two shadows) carries white words over bright footage and light clothing: a test reel's words
   over bright stock read 2.3-2.6:1 against their surroundings (broll_qa.py captions >= 3:1); the soft wide glow stays */
.on-paper { color: #0b0b0b; }
.glow .wb-in > span:first-child { text-shadow: 0 0 18px var(--glow), 0 0 42px var(--glow); }
.ghost .wb-in { mix-blend-mode: multiply; }
.cardshot { position: absolute; inset: 0; overflow: hidden; transform-origin: 50% 50%; box-shadow: 0 30px 70px rgba(0,0,0,.22); }
.photo { position: absolute; overflow: hidden; border-radius: 10px; box-shadow: 0 18px 50px rgba(0,0,0,.22); }
.band { position: absolute; left: 0; width: 1080px; height: 640px; overflow: hidden; }
.hlrow { position: absolute; display: flex; }
.hl { display: inline-flex; align-items: center; gap: 0.16em; padding: 0.02em 0.22em 0.1em; border-radius: 16px; color: #fff; font-family: "Inter Tight"; font-weight: 800; letter-spacing: -0.045em; line-height: 1; }
.iemo { position: relative; display: inline-block; vertical-align: middle; }
.iemo video, .iemo img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }
.cmrow { position: absolute; left: 0; right: 0; height: 0; display: flex; justify-content: center; align-items: center; }
.cm { display: flex; gap: 26px; align-items: flex-start; width: 760px; padding: 34px 40px 28px 34px; background: #fff; border-radius: 46px; box-shadow: 0 22px 60px rgba(0,0,0,.35); }
.cm-av { flex: 0 0 96px; width: 96px; height: 96px; border-radius: 50%; object-fit: cover; background: #ddd; }
.cm-body { flex: 1; font-family: "Inter"; }
.cm-text { font-size: 44px; line-height: 1.22; color: #111; letter-spacing: -0.01em; }
.cm-text > span:not(.iemo) { display: inline; }
.cm-text .iemo { display: inline-block; margin-left: 4px; vertical-align: -12px; }
.cm-reply { margin-top: 14px; font-size: 30px; color: #9a9aa0; font-weight: 500; }
.ntrow { position: absolute; left: 0; right: 0; height: 0; display: flex; justify-content: center; align-items: flex-start; }
.nt { display: flex; gap: 24px; align-items: flex-start; width: 940px; padding: 28px 34px 30px 28px; border-radius: 44px; background: rgba(36,36,42,.86); backdrop-filter: blur(30px) saturate(1.6); -webkit-backdrop-filter: blur(30px) saturate(1.6); box-shadow: 0 24px 70px rgba(0,0,0,.45), inset 0 0 0 1px rgba(255,255,255,.08); font-family: "Inter"; color: #fff; }
.nt-ic { flex: 0 0 92px; width: 92px; height: 92px; border-radius: 22px; background: linear-gradient(160deg, #3A3A42, #1C1C22); display: flex; align-items: center; justify-content: center; }
.nt-ic .iemo { display: block; }
.nt-body { flex: 1; min-width: 0; }
.nt-hd { display: flex; justify-content: space-between; align-items: baseline; font-size: 30px; color: rgba(255,255,255,.62); }
.nt-hd b { font-weight: 600; color: rgba(255,255,255,.78); letter-spacing: .01em; text-transform: uppercase; font-size: 26px; }
.nt-title { margin-top: 8px; font-size: 46px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1; }
.nt-text { margin-top: 6px; font-size: 38px; line-height: 1.22; color: rgba(255,255,255,.88); letter-spacing: -0.01em; }
.mw-bg { position: absolute; inset: 0; overflow: hidden; }
.mw { position: absolute; border-radius: 44px; overflow: hidden; box-shadow: 0 34px 90px rgba(0,0,0,.5), inset 0 0 0 1px rgba(255,255,255,.14); }
.mw-glass { position: absolute; inset: 0; overflow: hidden; }
.mw-glass video { position: absolute; object-fit: cover; filter: blur(34px) brightness(.55) saturate(1.35); }
.mw-tint { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(60,60,64,.38), rgba(24,24,26,.5)); }
.mw-dots { position: absolute; left: 34px; top: 32px; display: flex; gap: 14px; }
.mw-dots i { width: 26px; height: 26px; border-radius: 50%; display: block; box-shadow: inset 0 0 0 1px rgba(0,0,0,.18); }
.mw-dots i:nth-child(1) { background: #FF5F57; } .mw-dots i:nth-child(2) { background: #FEBC2E; } .mw-dots i:nth-child(3) { background: #28C840; }
.mw-label { position: absolute; right: 38px; top: 26px; height: 64px; display: flex; align-items: center; color: #fff; font-family: "Inter Tight"; font-weight: 700; font-size: 30px; letter-spacing: 0.08em; }
.mw-label img { height: 64px; width: auto; }
.mw-item { position: absolute; left: 60px; right: 60px; top: 112px; bottom: 34px; display: flex; align-items: center; justify-content: center; }
.mw-item img { max-width: 100%; max-height: 100%; object-fit: contain; filter: drop-shadow(0 18px 24px rgba(0,0,0,.45)); }
.ostage { position: absolute; inset: 0; perspective: 1400px; }
.ocard { position: absolute; overflow: hidden; }
.ocard.big { left: 0; top: 0; width: 1080px; height: 1920px; transform-origin: 50% 50%; }
.ocard.small { width: 280px; height: 360px; border-radius: 26px; box-shadow: 0 20px 50px rgba(0,0,0,.5); }
.obwrap { position: absolute; transform-origin: 0% 100%; }
.obub { position: absolute; display: flex; align-items: center; border-radius: 60px; transform-origin: 0% 100%; }
.obub.word { position: relative; padding: 24px 58px 34px; color: #fff; font-family: "Inter Tight"; font-weight: 800; font-size: 112px; letter-spacing: -0.05em; line-height: 1; white-space: nowrap; }
.obub .dots { display: flex; gap: 12px; padding: 30px 34px; }
.obub .dots i { width: 20px; height: 20px; border-radius: 50%; background: rgba(255,255,255,.9); display: block; }
.otail { position: absolute; left: -16px; bottom: -6px; }
.otap { position: absolute; right: -58px; top: -92px; width: 124px; height: 124px; }
${EMOJI_POP_CSS}
`;
L.sort((a, b) => a.at - b.at);
const page = `<!doctype html>
<html lang="${UI.lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=1080, height=1920">
<title>${esc(spec.title || "Seoul list")}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>${CSS}</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="${W}" data-height="${H}" data-duration="${TOTAL.toFixed(6)}" data-fps="${FPS}">
 <div id="base" class="layer">
  ${baseHtml}
 </div>
 ${html.scene.join("\n ")}
 ${html.text.join("\n ")}
 ${html.over.join("\n ")}
 ${html.top.join("\n ")}
 ${audio.join("\n ")}
</div>
<script>
  const tl = gsap.timeline({ paused: true });
  ${FT_HELPER}
  // fit each word line to its max width once the fonts are in (static scale on .wb-fit, never tweened)
  const fit = () => { document.querySelectorAll(".wb-in[data-fit]").forEach((el) => {
    const target = +el.dataset.fit, w = el.getBoundingClientRect().width;
    if (!target || !w) return;
    const k = Math.min(Math.max(target / w, 0.6), 1.7);
    el.querySelectorAll(":scope > span").forEach((s) => { s.style.fontSize = (parseFloat(s.style.fontSize) * k).toFixed(1) + "px"; });
    el.style.gap = (parseFloat(el.style.gap) * k).toFixed(1) + "px";
    el.style.setProperty("--bs", (parseFloat(el.style.getPropertyValue("--bs")) * k).toFixed(1) + "px");
  });
  document.querySelectorAll(".wb-fit").forEach((el) => {
    const max = +el.dataset.max || 960, r = el.getBoundingClientRect();
    let x0 = r.left, x1 = r.right;
    el.querySelectorAll(".subpos").forEach((s) => { const q = s.getBoundingClientRect(); x0 = Math.min(x0, q.left); x1 = Math.max(x1, q.right); });
    const w = Math.max(x1 - x0, el.firstElementChild.getBoundingClientRect().width);
    if (w > max) el.style.transform = "scale(" + (max / w).toFixed(4) + ")";
  }); };
  document.fonts.ready.then(() => {
    fit();
${L.map((l) => "    " + l.code.replace(/\n/g, "\n    ")).join("\n")}
    window.__timelines["main"] = tl;
  });
</script>
</body></html>
`;
fs.writeFileSync(path.join(proj, "index.html"), page);

// ---------------------------------------------------------------- report
const pad = (s, n) => String(s).padEnd(n);
console.log(`index.html: ${TOTAL.toFixed(3)} s (${TOTAL_F} frames), voice ${VO_DUR.toFixed(2)} s, last word ${LAST_END.toFixed(2)} s`);
console.log(`\nshots (${shots.length}, median ${(shots.map((s) => s.n / FPS).sort((a, b) => a - b)[Math.floor(shots.length / 2)]).toFixed(2)} s):`);
for (const s of shots) console.log(`  ${(s.f0 / FPS).toFixed(2).padStart(6)}-${(s.f1 / FPS).toFixed(2).padEnd(6)} ${pad(s.clip, 10)} in ${(s.inF / FPS).toFixed(2)}${s.tx ? `  <- ${s.tx}` : ""}`);
console.log(`\nbeats (${beats.length}):`);
for (const k of keyTimes) console.log(`  ${k.t0.toFixed(2).padStart(6)}-${k.t1.toFixed(2).padEnd(6)} ${pad(k.type, 10)} ${pad(k.id, 5)} ${k.label}   snap: ${k.keys.join(", ")}`);
console.log(`\nsfx (${PROFILE}, ${sfxEvents.length} hits, ${(sfxEvents.length / (TOTAL / 10)).toFixed(1)} per 10 s; voice p95 ${voiceP95.toFixed(1)} dBFS):`);
for (const e of sfxEvents) console.log(`  ${e.t.toFixed(2).padStart(6)} ${pad(e.id, 20)} ${pad(e.role, 7)} vol ${e.vol}  ${e.why}`);
console.log(`music: ${musicInfo}`);
console.log(`transitions: ${txOut.length ? txOut.map((t) => `${t.id} ${t.type} at ${t.start}s for ${t.duration}s`).join("; ") : "none"}`);
if (warn.length) console.log(`\nWARNINGS:\n  ${[...new Set(warn)].join("\n  ")}`);
