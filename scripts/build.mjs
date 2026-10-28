#!/usr/bin/env node
// Generate a HyperFrames composition (index.html) for a vertical talking-head
// reel from one edit spec, reel.json, and the whisper word json.
//
//   node build.mjs <project-dir>            (reads <project>/reel.json)
//
// Every time in reel.json is an ORIGINAL-recording second. E(t) maps it to
// edit time through the chosen takes and throws when t was cut, so a beat
// can never point at material that is not in the video.
//
// What the build owns so the plan does not have to:
//   - takes as muted <video> ranges + matching <audio> with 2/3-frame fades
//   - snap zooms and push-ins on two nested wrappers (they multiply)
//   - word-timed captions (house, pill, clean, mini, editorial, chest, or a template from lib/caption-templates.mjs)
//   - overlays: big, chips, strike, quote, list, emoji (Fluent when fetched), logo, meme, endcard, behind,
//     broll, title, scene (lib/motion.mjs, shader backgrounds), textfx (lib/kinetic.mjs), stan style: panel, hook,
//     diagram, step, cta, aside + chest captions (lib/stan.mjs)
//   - optional: a film-graded plate (look.film), transition windows (transitions), shader overlays (look.shader),
//     BiRefNet cutout windows (cutout beats via scripts/cutout_fx.py) and plates (look.cutout), taste defaults and
//     warnings (taste.json)
//   - SFX: default sound per beat type, round-robin variants, level by role
//     from the normalized kit, density and repetition rules
//   - copies every asset into <project>/assets so the render is self-contained
// It writes index.html, build/sfx_events.json (for qa.py) and prints the edit
// timeline, the caption text and an SFX density report.

import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { MOTION_CSS, buildScene, buildEditorialCaptions, buildMusic } from "./lib/motion.mjs";
import { KINETIC_CSS, buildKinetic, blockHeight, placeY } from "./lib/kinetic.mjs";
import { installShaderRuntime, shaderLayerHtml, extractStill } from "./lib/shader-layer.mjs";
import { loadManifest as emojiManifest, installEmoji, emojiPopHtml, emojiPopJs, EMOJI_POP_CSS, EMOJI_DIR } from "./lib/emoji-pop.mjs";
import { makePlacer, PLATFORMS } from "./lib/safezone.mjs";
import { PY, npxSync, venvPython, venvDefault } from "./lib/plat.mjs";
import { TEMPLATE_NAMES, buildTemplateCaptions } from "./lib/caption-templates.mjs";
import { aiTag } from "./lib/ai-tag.mjs";
import { findTaste, loadTaste, applyTaste, checkTaste, bannedSfx } from "./lib/taste.mjs";
import { STAN_CSS, isStanBeat, stanPrepare, stanBeat, stanPipTweens, buildChestCaptions, stanMatteWindows } from "./lib/stan.mjs";

const SKILL = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const LIB = path.join(SKILL, "library");
const proj = path.resolve(process.argv[2] || ".");
const rawSpec = JSON.parse(fs.readFileSync(path.join(proj, "reel.json"), "utf8"));
// a style preset (styles/<name>.json) supplies defaults; reel.json overrides
const deepMerge = (a, b) => {
  if (b === undefined) return a;
  if (a && b && typeof a === "object" && typeof b === "object" && !Array.isArray(a) && !Array.isArray(b)) {
    const o = { ...a };
    for (const k of Object.keys(b)) o[k] = deepMerge(a[k], b[k]);
    return o;
  }
  return b;
};
const STYLE_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "styles");
let preset = {};
if (rawSpec.style) {
  const sp = path.join(STYLE_DIR, `${rawSpec.style}.json`);
  if (!fs.existsSync(sp)) { console.error(`ERROR: unknown style '${rawSpec.style}'; have: ${fs.readdirSync(STYLE_DIR).map((f) => f.replace(".json", "")).join(", ")}`); process.exit(1); }
  preset = JSON.parse(fs.readFileSync(sp, "utf8"));
  delete preset._about;
}
// taste.json (the user's corrections and the skill's learned rules, across reels) fills what reel.json leaves unset:
// preset < taste < reel.json. Its checks run after the SFX rules.
const taste = loadTaste(findTaste({ proj, skill: SKILL }));
const { spec, applied: tasteApplied } = applyTaste(deepMerge(preset, rawSpec), rawSpec, taste);
const BANNED_SFX = bannedSfx(taste);

const FPS = spec.fps ?? 30;
// brand kit: one accent (60/30/10), ink for text on light scenes, caption size
const brand = { accent: "#D13F34", accentDark: "#B93026", ink: "#262626", capSize: 58, font: null, ...(spec.brand || {}) };
const W = 1080, H = 1920;
const warn = [];
const die = (m) => { console.error("ERROR: " + m); process.exit(1); };

// ---------- takes and time mapping ----------
const takes = spec.takes.map((t, i) => {
  if (!(t.b > t.a)) die(`take ${i} has b <= a`);
  return { ...t, frames: Math.round((t.b - t.a) * FPS) };
});
// hold: seconds of frozen last frame AFTER a take (no voice). It makes air
// for a meme on a tightly cut recording; the meme's `at` is the take's b.
let acc = 0;
for (const t of takes) {
  t.f0 = acc; t.start = acc / FPS; acc += t.frames; t.dur = t.frames / FPS;  // f0: the take's first output frame
  t.holdFrames = Math.round((t.hold ?? 0) * FPS); t.hf0 = acc; t.holdStart = acc / FPS; acc += t.holdFrames;
}
const SPEECH_F = acc;
const SPEECH = acc / FPS;
const OUTRO = spec.outro ?? 3;
const TOTAL = +(SPEECH + OUTRO).toFixed(3);

const E = (t, what = "") => {
  if (t === "end") return TOTAL;
  if (typeof t === "string" && t.startsWith("outro+")) return SPEECH + parseFloat(t.slice(6));
  for (const k of takes) if (t >= k.a - 1e-6 && t <= k.b + 1e-6) return +(k.start + (t - k.a)).toFixed(3);
  // whisper word times are loose around pauses: a time inside a short removed
  // gap (< 1.2 s) snaps to the start of the next kept take
  if (typeof t === "number") for (let i = 0; i + 1 < takes.length; i++) if (t > takes[i].b && t < takes[i + 1].a && takes[i + 1].a - takes[i].b < 1.2) return +takes[i + 1].start.toFixed(3);
  // "hold:<i>+s" = s seconds into the hold after take i
  if (typeof t === "string" && t.startsWith("hold:")) { const [i, off] = t.slice(5).split("+"); return +(takes[+i].holdStart + (parseFloat(off) || 0)).toFixed(3); }
  throw new Error(`E(${t})${what ? " for " + what : ""}: not inside any take`);
};
const r3 = (x) => Math.round(x * 1000) / 1000;
// A clip time on the output frame grid, for the data-start / data-duration of everything that shows footage (takes,
// holds, matte, transition and cutout windows): a frame count / FPS TRUNCATED to 6 decimals, never rounded up.
// HyperFrames snaps a clip start to the grid only within 0.001 frame and picks a <video>'s frame with
// floor((t - data-start) * fps): a start rounded UP (r3 writes 0.067 for 2/30) shows the clip one frame late for its whole
// length, and a 6-decimal round-up (0.066667) repeats its first frame (numbered-frame test render, HyperFrames 0.8.147).
const fgrid = (frames) => (Math.floor((frames / FPS) * 1e6) / 1e6).toFixed(6);

// ---------- words -> edit-time captions ----------
const core = (w) => w.replace(/[.,!?;:]+$/, "");
const punct = (w) => w.slice(core(w).length);
const whisper = JSON.parse(fs.readFileSync(path.resolve(proj, spec.words), "utf8"));
const allWords = whisper.segments.flatMap((s) => (s.words || []).map((w) => ({ word: w.word.trim(), start: w.start, end: w.end })));
const fixes = Object.entries(spec.captions?.fixes || {});
const words = [];
console.log("\n edit-start   orig a  ->  orig b   dur   text");
// each word belongs to ONE take: the one it overlaps most (whisper stretches
// words over pauses, so a boundary word can touch two neighbouring takes)
const ov = (w, k) => Math.min(w.end, k.b) - Math.max(w.start, k.a);
const owner = allWords.map((w) => {
  let best = -1, bo = 0;
  takes.forEach((k, i) => { const o = ov(w, k); if (o > bo) { bo = o; best = i; } });
  return bo >= Math.min(0.1, 0.5 * (w.end - w.start)) ? best : -1;
});
for (const [ti, k] of takes.entries()) {
  const ws = allWords.filter((w, wi) => owner[wi] === ti);
  if (!ws.length) { warn.push(`take ${k.a}-${k.b} owns no words (a breath or a tail); fine for autocut takes`); continue; }
  ws.forEach((w, i) => {
    let text = w.word;
    for (const [o, n] of fixes) if (core(text).toLowerCase() === o.toLowerCase()) text = n + punct(text);
    if (i === 0 && /^[a-z]/.test(text) && (!words.length || /[.?!]$/.test(words.at(-1).word))) text = text[0].toUpperCase() + text.slice(1);
    const prev = words.at(-1);
    // whisper splits "co-founder" and "50,000"; glue the pieces back
    if (prev && (text.startsWith("-") || (/^[,.]\d/.test(text) && /\d$/.test(prev.word)))) { prev.word += text; prev.end = r3(k.start + Math.min(w.end, k.b) - k.a); return; }
    words.push({ word: text, start: r3(k.start + Math.max(w.start, k.a) - k.a), end: r3(k.start + Math.min(w.end, k.b) - k.a) });
  });
  const line = ws.map((w) => w.word).join(" ");
  console.log(`${k.start.toFixed(2).padStart(9)}   ${k.a.toFixed(2).padStart(7)} -> ${k.b.toFixed(2).padStart(7)}  ${k.dur.toFixed(2).padStart(5)}   ${line.slice(0, 90)}${line.length > 90 ? "..." : ""}`);
}

// phrase fixes: whisper mangles product names across several words
// ("a call for reach" -> "Coffer Reach"); the first word takes the new text
// and the span of the whole phrase, the rest are dropped
for (const [from, to] of Object.entries(spec.captions?.phrases || {})) {
  const pat = from.toLowerCase().split(/\s+/);
  for (let i = 0; i + pat.length <= words.length; i++) {
    if (pat.every((p, k) => core(words[i + k].word).toLowerCase() === p)) {
      const tail = punct(words[i + pat.length - 1].word);
      words[i] = { word: to + tail, start: words[i].start, end: words[i + pat.length - 1].end };
      words.splice(i + 1, pat.length - 1);
    }
  }
}

// ---------- assets ----------
const A = path.join(proj, "assets");
for (const d of ["sfx", "memes", "icons", "fonts"]) fs.mkdirSync(path.join(A, d), { recursive: true });
for (const f of fs.readdirSync(path.join(SKILL, "templates", "fonts"))) fs.copyFileSync(path.join(SKILL, "templates", "fonts", f), path.join(A, "fonts", f));

const sfxManifest = JSON.parse(fs.readFileSync(path.join(LIB, "sfx", "manifest.json"), "utf8"));
const memeLib = (id) => {
  const dir = path.join(LIB, "memes", id);
  const mp = path.join(dir, "meta.json");
  if (!fs.existsSync(mp)) die(`meme '${id}' not in library (library/memes/${id}/meta.json); add it with meme_add.py or run meme_find.py`);
  return { dir, meta: JSON.parse(fs.readFileSync(mp, "utf8")) };
};
const icon = (slug) => {
  // simple-icons (CC0), fetched at build time, never at render time
  const dst = path.join(A, "icons", `${slug}.svg`);
  if (!fs.existsSync(dst)) {
    try { execFileSync("curl", ["-sfL", "-o", dst, `https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/${slug}.svg`]); }
    catch { die(`no simple-icons slug '${slug}' (see https://simpleicons.org); pass "src" with your own image instead`); }
  }
  return `assets/icons/${slug}.svg`;
};
const userAsset = (p) => {
  const src = path.resolve(proj, p);
  if (!fs.existsSync(src)) die(`asset not found: ${p}`);
  if (src.startsWith(A + path.sep)) return path.relative(proj, src);
  const dst = path.join(A, path.basename(src));
  fs.copyFileSync(src, dst);
  return `assets/${path.basename(src)}`;
};

// ---------- SFX: levels by role, defaults per beat, rules ----------
// Levels are set RELATIVE TO THIS RECORDING'S VOICE: the p95 of 50 ms peak
// windows over the kept words (the voice is -16 LUFS after prep.sh, but a
// compressed voice peaks higher than a dynamic one). Kit files are
// peak-normalized to -1 dBFS and the HyperFrames mixer is linear (verified:
// volume 0.5 = -6 dB, no normalization by track count), so
// volume = 10^((voiceP95 + roleDb - (-1)) / 20).
// ui ticks sit well under the voice, meme hits come close to it because they
// land in pauses.
const ROLE_DB = { ui: -14, whoosh: -12, impact: -8, meme: -3, foley: -14, ...(spec.mix?.roleDb || {}) };
const voiceP95 = (() => {
  const raw = execFileSync("ffmpeg", ["-v", "error", "-i", path.resolve(proj, spec.source), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], { maxBuffer: 1 << 30 });
  const x = new Float32Array(raw.buffer, raw.byteOffset, Math.floor(raw.length / 4));
  const win = 800, pk = [];
  for (const k of takes) for (const w of allWords) {
    if (w.start < k.a || w.end > k.b) continue;
    for (let i = Math.floor(w.start * 16000); i + win <= w.end * 16000; i += win) {
      let m = 0;
      for (let j = i; j < i + win; j++) m = Math.max(m, Math.abs(x[j]));
      pk.push(m);
    }
  }
  pk.sort((a, b) => a - b);
  return 20 * Math.log10(Math.max(pk[Math.floor(pk.length * 0.95)] || 0.3, 1e-6));
})();
const volFor = (role, extraDb = 0) => r3(Math.min(1, Math.pow(10, (voiceP95 + ROLE_DB[role] + extraDb + 1) / 20)));
const VARIANTS = { pop: ["pop-1", "pop-2", "pop-3"], whoosh: ["whoosh-1", "whoosh-2", "whoosh-3"], impact: ["impact-1", "impact-2"] };
const rr = {};
const pick = (id) => {
  if (!VARIANTS[id]) return id;
  rr[id] = ((rr[id] ?? -1) + 1) % VARIANTS[id].length;
  return VARIANTS[id][rr[id]];
};
const sfxEvents = []; // {t, id, role, vol, src, why}
// sfxProfile: restrained keeps only structural hits (scene changes, hero words,
// clicks, impacts); rich adds a whoosh to every snap. Standard = everything.
const SFX_PROFILE = spec.sfxProfile || "standard";
const RESTRAINED_DROP = /type tick|fly3d word|chip|list line|card pill|badge in|push-in|device line|ui line|kinetic keyword|emoji|logo/;
const addSfx = (t, id, why, { db = 0, lead = 0, explicit = false } = {}) => {
  if (!id || id === "none") return;
  if (SFX_PROFILE === "restrained" && RESTRAINED_DROP.test(why)) return;
  const real = pick(id);
  // a default sound banned in taste.json is skipped; one written in reel.json still plays (and taste warns)
  if ((BANNED_SFX.has(id) || BANNED_SFX.has(real)) && !explicit && why !== "manual") { warn.push(`taste: default sound '${real}' (${why}) skipped, banned in taste.json`); return; }
  const m = sfxManifest[real];
  if (!m) die(`sfx '${real}' not in library/sfx/manifest.json (${why})`);
  fs.copyFileSync(path.join(LIB, "sfx", m.file), path.join(A, "sfx", m.file));
  sfxEvents.push({ t: r3(Math.max(0, t - lead)), id: real, role: m.role, vol: volFor(m.role, db), dur: m.duration, src: `assets/sfx/${m.file}`, why });
};
const beatSfx = (b, t, def, why, opts) => {
  const s = b.sfx === undefined ? def : b.sfx;
  if (s === false || s === "none") return;
  for (const id of [].concat(s)) addSfx(t, id, why, { ...opts, explicit: b.sfx !== undefined });
};

// ---------- zoom ----------
const zoom = spec.zoom || {};
const tl = []; // GSAP lines
const snaps = (zoom.snaps || []).map(([t, z]) => [E(t, "snap"), z]).sort((a, b) => a[0] - b[0]);
tl.push(`tl.set("#snap", { scale: 1 }, 0);`);
for (const [t, z] of snaps) {
  tl.push(`tl.set("#snap", { scale: ${z} }, ${t});`);
  if (zoom.snapSfx || SFX_PROFILE === "rich") addSfx(t, !zoom.snapSfx || zoom.snapSfx === true ? "whoosh" : zoom.snapSfx, "snap", { db: -6, lead: 0.05 });
}
let lastPushEnd = -1;
const pushesEdit = [];
for (const p of zoom.pushes || []) {
  const a = E(p.at, "push"), up = p.up ?? 0.4, down = p.down ?? 0;
  const b = p.until === "end" ? TOTAL : E(p.until, "push until");
  pushesEdit.push({ a, b, z: p.z, up, down: p.until === "end" ? 0 : down });
  if (a < lastPushEnd) die(`push at ${p.at} overlaps the previous push`);
  tl.push(`ft("#push", { scale: 1 }, { scale: ${p.z}, duration: ${up}, ease: "power3.out" }, ${a});`);
  if (p.sfx) addSfx(a, p.sfx, "push-in", { db: -4, lead: 0.05 });
  if (p.until !== "end") tl.push(down > 0 ? `tl.to("#push", { scale: 1, duration: ${down}, ease: "power2.inOut" }, ${b});` : `tl.set("#push", { scale: 1 }, ${b});`);
  lastPushEnd = b + down;
}

// ---------- the speaker ----------
let SRC = spec.source;
if (!fs.existsSync(path.resolve(proj, SRC))) die(`source ${SRC} missing; run prep.sh first`);
// the speaker's face keeps its natural, as-shot colour: a colour look on the plate
// (look.grade, look.film) only when the user asked for one, with their words in look.asked. broll_qa.py fails a regraded plate.
if (spec.look && (spec.look.grade || spec.look.film) && !spec.look.asked) {
  console.warn(`WARNING look.grade / look.film ignored: the speaker's face stays as shot. Set look.asked: "<the user's words>" only when they asked for a graded look.`);
  delete spec.look.grade; delete spec.look.film;
}
// look.film: a film-stock plate graded once by scripts/film_look.py (same frames, timestamps and audio, only the colour
// changes), so the takes play the graded file; captions and cards stay ungraded
if (spec.look?.film) {
  const plate = spec.look.plate || "assets/talk.film.mp4";
  const fp = path.resolve(proj, plate), sp = path.resolve(proj, SRC);
  const cmd = `${PY} ${path.join(SKILL, "scripts", "film_look.py")} apply ${SRC} ${plate} --look ${spec.look.film}` +
    (spec.look.grain != null ? ` --grain ${spec.look.grain}` : "") + (spec.look.halation != null ? ` --halation ${spec.look.halation}` : "");
  if (!fs.existsSync(fp) || fs.statSync(fp).mtimeMs < fs.statSync(sp).mtimeMs) die(`look.film: grade the plate first (in ${proj}):\n  ${cmd}`);
  SRC = plate;
}
// look.cutout: a reel-wide selective colour / spotlight / portrait blur baked into the plate by scripts/cutout_fx.py
// (BiRefNet, matte venv; same frames, timestamps and audio, the takes play the new plate). The whole source goes through
// the model once, so like look.film it is an explicit step: the build stops with the command when the plate is missing,
// older than its source, or was made with other options (its sidecar <plate>.json records them).
if (spec.look?.cutout) {
  const lc = typeof spec.look.cutout === "string" ? { fx: spec.look.cutout } : spec.look.cutout;
  if (!["selective", "spotlight", "bg-blur"].includes(lc.fx)) die(`look.cutout.fx must be selective, spotlight or bg-blur (got ${lc.fx})`);
  const plate = lc.plate || `assets/talk.${lc.fx}.mp4`;
  const fp = path.resolve(proj, plate), sp = path.resolve(proj, SRC);
  const dur = parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", sp]).toString());
  const kebab = (k) => k.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
  const opts = Object.entries(lc).filter(([k]) => !["fx", "plate", "model", "batch", "ramp", "at"].includes(k));
  const cmd = `${venvPython(venvDefault("MATTE_VENV", "ghost-matte"))} ${path.join(SKILL, "scripts", "cutout_fx.py")} ${lc.fx} ${SRC}` +
    ` --ss 0 --t ${dur} --at 0 --ramp 0 --model ${lc.model || "lite@512"} --batch ${lc.batch ?? 4} -o ${plate}` +
    opts.map(([k, v]) => ` --${kebab(k)} '${v}'`).join("");
  let sig = null;
  try { sig = JSON.parse(fs.readFileSync(fp + ".json", "utf8")).sig; } catch { /* no sidecar: not made by cutout_fx.py */ }
  const eq = (a, b) => String(a) === String(b) || (a !== null && a !== "" && +a === +b);
  const same = sig && sig.cmd === lc.fx && sig.model === (lc.model || "lite@512") && opts.every(([k, v]) => eq(sig[kebab(k).replace(/-/g, "_")], v));
  if (!fs.existsSync(fp) || fs.statSync(fp).mtimeMs < fs.statSync(sp).mtimeMs || !same)
    die(`look.cutout: render the plate first (in ${proj}; lite@512: ~12 min for a 65 s source on an M3 Air, alpha ~6.5 + effect ~5):\n  ${cmd}`);
  SRC = plate;
}
const srcDur = parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path.resolve(proj, SRC)]).toString());
const stillAt = (t) => String(Math.max(0, Math.min(t, srcDur - 0.12)));
// edit time -> source media time (stills of the footage, e.g. the fluted-self shader look)
const mediaAt = (t) => { const k = takes.find((k) => t >= k.start && t < k.start + k.dur) || takes.at(-1); return k.a + Math.max(0, t - k.start); };
const fadeLane = (d) => JSON.stringify({ version: 1, lanes: [{ target: "volume", points: [{ t: 0, v: 0 }, { t: r3(2 / FPS), v: 1 }, { t: r3(d - 3 / FPS), v: 1 }, { t: r3(d), v: 0 }] }] });
const takeHtml = takes.map((k, i) => {
  let h = `
      <video id="take-${i}" src="${SRC}" data-start="${fgrid(k.f0)}" data-duration="${fgrid(k.frames)}" data-media-start="${k.a}" data-track-index="0" muted playsinline></video>`;
  if (k.holdFrames) {
    execFileSync("ffmpeg", ["-v", "error", "-y", "-ss", stillAt(k.a + k.dur - 1 / FPS), "-i", path.resolve(proj, SRC), "-frames:v", "1", "-q:v", "2", "-update", "1", path.join(A, `hold-${i}.jpg`)]);
    h += `
      <img id="hold-${i}" class="fill" src="assets/hold-${i}.jpg" data-start="${fgrid(k.hf0)}" data-duration="${fgrid(k.holdFrames)}" data-track-index="0" />`;
  }
  return h;
}).join("");
const takeAudio = takes.map((k, i) => `
  <audio id="take-${i}-audio" src="${SRC}" data-start="${fgrid(k.f0)}" data-duration="${fgrid(k.frames)}" data-media-start="${k.a}" data-track-index="${10 + (i % 2)}" data-automation='${fadeLane(k.dur)}'></audio>`).join("");
// ---------- transitions: pre-rendered windows from scripts/transitions.py reel ----------
// Each window is a short clip laid over the cut inside the camera wrappers (zooms and the look apply to it like to the
// takes); the edit's timing and the voice are untouched (the voice stays a hard cut).
let txHtml = "";
if (spec.transitions) {
  const tp = path.join(proj, "build", "transitions.json");
  const fresh = `${PY} ${path.join(SKILL, "scripts", "transitions.py")} reel ${proj}`;
  if (!fs.existsSync(tp)) die(`transitions: render them first:\n  ${fresh}`);
  const txs = JSON.parse(fs.readFileSync(tp, "utf8"));
  const txSpec = (i) => (Array.isArray(spec.transitions) ? spec.transitions.find((x) => x.after === i) : spec.transitions) || {};
  for (const t of txs) {
    const k = takes[t.after], nx = takes[t.after + 1];
    if (!k || !nx || Math.abs(k.b - t.out_point) > 1e-3 || Math.abs(nx.a - t.in_point) > 1e-3 || t.source !== SRC)
      die(`transitions: ${t.id} was rendered for another cut (takes or source changed):\n  ${fresh}`);
    if (Math.abs(t.start - (nx.start - t.duration / 2)) > 0.1) warn.push(`${t.id}: window not centred on the cut, check build/transitions.json`);
    if (!fs.existsSync(path.join(proj, t.src))) die(`transitions: ${t.src} missing:\n  ${fresh}`);
    // a deliberate punchy transition gets a sound (bare cuts and subtle dissolves stay dry)
    const sx = txSpec(t.after).sfx;
    if (sx !== false && sx !== "none") {
      if (sx) addSfx(t.start, sx, `transition ${t.type}`, { explicit: true });
      else if (["whip", "scaled_push", "static_wipe"].includes(t.type)) addSfx(t.start, "whoosh", `transition ${t.type}`, { lead: 0.05 });
      else if (t.type === "flash") addSfx(r3(t.start + t.duration / 2), "impact", "transition flash", { db: -4 });
    }
  }
  txHtml = txs.map((t) => `
      <video id="${t.id}" src="${t.src}" data-start="${fgrid(Math.round(t.start * FPS))}" data-duration="${fgrid(t.frames ?? Math.round(t.duration * FPS))}" data-media-start="0" data-track-index="6" muted playsinline></video>`).join("");
  console.log(`transitions: ${txs.map((t) => `${t.type}@${r3(t.start + t.duration / 2)}s`).join(", ")}`);
  for (const t of txs) for (const b of (spec.beats || []).filter((b) => b.type === "behind"))
    if (E(b.at) < t.start + t.duration && (b.to !== undefined ? E(b.to) : E(b.at) + 2.5) > t.start) warn.push(`behind beat at ${b.at} overlaps ${t.id}: the old take's cut-out would show over the transition; move one of them`);
}
// ---------- cutout beats: BiRefNet effects pre-rendered by scripts/cutout_fx.py (matte venv) ----------
// Each beat renders its own source window once (assets/fx/cutout-<j>.mp4 + .json signature; the alpha is cached in
// ~/.cache/ghost-matte/alpha) and plays over the take inside the camera wrappers, like a transition window: zooms and the
// look apply; the voice keeps playing from the take audio (the fx clip is silent). The window sits on the frame grid: it
// starts on the output frame nearest `at`, its first frame is exactly the source frame the take shows there (HyperFrames
// samples a <video> at floor(media time x fps)) and it holds exactly the beat's frame count, so the head does not jump at
// either edge and the picture cannot drift against the take's voice. Effects ease back into the take over `release`
// (default 0.3 s); the sticker's hold is fitted so it has dropped back before the window ends.
const CUTOUT_OPTS = {
  "bg-swap": ["bg", "bg2", "switch", "wrap", "match", "defocus", "push", "wipe", "release"],
  "bg-blur": ["radius", "ramp", "bokeh", "dim", "release"], selective: ["look", "ramp", "release"],
  spotlight: ["dim", "ramp", "color", "release"], sticker: ["hold", "stroke", "stickerScale", "bg"],
  neon: ["colors", "trace", "dim", "release"], clones: ["offsets", "bust", "midScale", "sideScale", "backdrop", "light", "release"],
  pop: ["frame", "bg", "plate", "bottom", "brk", "release"],
};
let cutoutHtml = "";
const cutoutBeats = (spec.beats || []).filter((b) => b.type === "cutout");
const cutoutWins = []; // -> build/cutouts.json, what each window was cut from (qa.py re-counts the clips)
if (cutoutBeats.length) {
  const py = venvPython(venvDefault("MATTE_VENV", "ghost-matte"));
  if (!fs.existsSync(py)) die(`cutout beats need the matte venv: bash ${path.join(SKILL, "scripts", "setup_matte.sh")}`);
  const [fn, fd] = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0",
    path.resolve(proj, SRC)]).toString().trim().split("/").map(Number);
  const srcFps = fn / (fd || 1);
  fs.mkdirSync(path.join(A, "fx"), { recursive: true });
  cutoutBeats.forEach((b, j) => {
    const opts = CUTOUT_OPTS[b.fx];
    if (!opts) die(`cutout beat at ${b.at}: unknown fx "${b.fx}" (${Object.keys(CUTOUT_OPTS).join(", ")})`);
    const t0 = E(b.at, "cutout at"), t1 = b.to === undefined ? t0 + 2.5 : E(b.to, "cutout to");
    const F0 = Math.round(t0 * FPS), n = Math.round(t1 * FPS) - F0; // the window in output frames
    const k = takes.find((k) => F0 >= k.f0 && F0 < k.f0 + k.frames);
    if (!k || F0 + n > k.f0 + k.frames) die(`cutout beat at ${b.at}: keep it inside one take (it runs past the take's cut)`);
    if (n < Math.round(0.5 * FPS)) die(`cutout beat at ${b.at}: the window is ${(n / FPS).toFixed(2)} s; give it a "to" at least 0.5 s later`);
    // the source frame the take shows at edit frame F0 (HyperFrames' floor), passed as that frame's exact time
    const fi = Math.floor((k.a + (F0 - k.f0) / FPS) * srcFps + 1e-4);
    const ss = fi / srcFps, nSrc = Math.round((n / FPS) * srcFps);
    // clones: the side copies run ahead by the largest offset, so the window needs that much more source
    const extra = b.fx === "clones" ? Math.max(0, ...String(b.offsets ?? "0,0.4,0.8").split(",").map((x) => Math.round(parseFloat(x) * srcFps))) : 0;
    if ((fi + nSrc + extra) / srcFps > srcDur + 1e-3) die(`cutout beat at ${b.at}: the window runs past the end of ${SRC}`);
    const rel = `assets/fx/cutout-${j}.mp4`;
    const model = b.model || spec.cutout?.model || "lite@1024";
    // --ss with 6 decimals and --t half a frame short of the window: ffmpeg's input seek then returns exactly these nSrc
    // frames at every phase of the grid (3 decimals, or t = n/fps, lose a frame on some phases; tests/test_cutout_fx.py)
    const args = [path.join(SKILL, "scripts", "cutout_fx.py"), b.fx, path.resolve(proj, SRC), "--ss", ss.toFixed(6),
      "--t", ((nSrc + extra - 0.5) / srcFps).toFixed(6), "--at", ss.toFixed(6), "--no-audio", "-o", path.join(proj, rel), "--model", model];
    const o = { ...b };
    if (b.fx === "sticker") {
      // the frozen frame: the one on screen when the beat lands, or `freeze` (original seconds inside the window: the
      // window plays live until then; use it when `at` lands on a blink or mid-gesture)
      let Ff = F0, ff = fi;
      if (b.freeze !== undefined) {
        Ff = Math.round(E(b.freeze, "cutout freeze") * FPS);
        if (Ff < F0 || Ff >= F0 + n) die(`cutout sticker at ${b.at}: freeze ${b.freeze} is outside the beat's window`);
        ff = Math.floor((k.a + (Ff - k.f0) / FPS) * srcFps + 1e-4);
      }
      args.push("--freeze", (ff / srcFps).toFixed(6));
      // drop-back takes 0.35 s; leave the live take on screen for the window's last 0.15 s so the hand-back is seamless
      const fit = Math.max(0.3, (F0 + n - Ff) / FPS - 0.5);
      if (o.hold === undefined) o.hold = r3(fit);
      else if (o.hold > fit + 1e-3) warn.push(`cutout sticker at ${b.at}: hold ${o.hold} s + the 0.35 s drop-back runs past the window (${(n / FPS).toFixed(2)} s): the take cuts back in under the sticker; use hold <= ${r3(fit)} or a later "to"`);
    } else if (o.release === undefined) o.release = 0.3;
    for (const key of opts) {
      if (o[key] === undefined) continue;
      let v = Array.isArray(o[key]) ? o[key].join(",") : String(o[key]);
      if ((key === "bg" || key === "bg2") && !/^(#|dim$|blur$|plate$)/.test(v)) {
        v = path.resolve(proj, v);
        if (!fs.existsSync(v)) die(`cutout beat at ${b.at}: ${key} ${o[key]} not found`);
      }
      args.push("--" + key.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase()), v);
    }
    console.log(`cutout ${b.fx} at ${b.at}: edit frames ${F0}-${F0 + n - 1}, source frame ${fi} (${ss.toFixed(3)} s) + ${nSrc}, ${model} -> ${rel}`);
    const T = Date.now();
    execFileSync(py, args, { stdio: ["ignore", "inherit", "inherit"], cwd: proj, maxBuffer: 1 << 28 });
    const side = JSON.parse(fs.readFileSync(path.join(proj, rel + ".json"), "utf8"));
    if (side.frames !== nSrc) die(`cutout beat at ${b.at}: ${rel} has ${side.frames} frames, the window needs ${nSrc}`);
    console.log(`  cutout ${b.fx} ready in ${((Date.now() - T) / 1000).toFixed(1)} s`);
    cutoutWins.push({ id: `cutout-${j}`, fx: b.fx, at: b.at, to: b.to, src: rel, f0: F0, start: r3(F0 / FPS), frames: n, srcFrames: nSrc,
      ss: +ss.toFixed(6), source: SRC, model, take: takes.indexOf(k) });
    cutoutHtml += `
      <video id="cutout-${j}" src="${rel}" data-start="${fgrid(F0)}" data-duration="${fgrid(n)}" data-media-start="0" data-track-index="7" muted playsinline></video>`;
  });
  // edit-time spans; a behind word's matte would show the ORIGINAL footage over the effect
  const span = (x) => { const a = E(x.at); return [a, x.to !== undefined ? E(x.to) : a + 2.5]; };
  if (cutoutBeats.length > 2) warn.push(`${cutoutBeats.length} cutout beats: more than 2 per reel reads as a filter showcase`);
  for (const b of cutoutBeats) {
    const [b0, b1] = span(b);
    for (const o of (spec.beats || []).filter((x) => x.type === "behind" && !x.front)) {
      const [o0, o1] = span(o);
      if (o0 < b1 && o1 > b0) warn.push(`behind beat at ${o.at} overlaps cutout ${b.fx} at ${b.at}: the matte would show the original footage over the effect`);
    }
    for (const o of cutoutBeats) if (o !== b && span(o)[0] >= b0 && span(o)[0] < b1) warn.push(`cutout ${o.fx} at ${o.at} starts inside cutout ${b.fx} at ${b.at}: only the later window shows`);
    for (const o of (spec.beats || []).filter((x) => x.type === "scene" || (x.type === "broll" && x.mode !== "split"))) {
      const [o0, o1] = span(o);
      if (o0 < b1 - 0.05 && o1 > b0 + 0.05) warn.push(`cutout ${b.fx} at ${b.at} runs under the full-screen ${o.type} at ${o.at}: that part of the effect is hidden`);
    }
  }
}
let matteHtml = "";
// stan-style panels sit BEHIND the speaker: a cut-out of the speaker for the panel windows is drawn over the panel (matteM below)
const panelMatte = stanMatteWindows(spec.beats || [], E);
let panelMatteOk = false;
if (spec.matte || panelMatte.length) {
  // person cut-out for `behind` beats (and stan panels): BiRefNet-portrait via scripts/matte.py (optional venv,
  // scripts/setup_matte.sh), computed only for the source seconds they show; every other frame is transparent. Without the
  // venv (or with matte: {engine: "hyperframes"}) behind beats fall back to hyperframes remove-background (u2net, whole file).
  const mp = path.join(A, "talk-matte.webm");
  const mcfg = typeof spec.matte === "object" ? spec.matte : {};
  const ranges = [];
  const wins = [...(spec.matte ? (spec.beats || []).filter((b) => b.type === "behind" && !b.front) // a front word sits over the matte
    .map((b) => { const t0 = E(b.at, "behind at"); return [t0, b.to === undefined ? t0 + 2.5 : E(b.to, "behind to")]; }) : []), ...panelMatte];
  for (const [t0, t1] of wins) {
    for (const k of takes) {
      const a = Math.max(t0, k.start), z = Math.min(t1, k.start + k.dur);
      if (z > a) ranges.push(`${(k.a + a - k.start).toFixed(2)}-${(k.a + z - k.start).toFixed(2)}`);
    }
  }
  const venv = venvDefault("MATTE_VENV", "ghost-matte");
  const py = venvPython(venv);
  if (!spec.matte && !fs.existsSync(py)) {
    warn.push(`panels behind the speaker need the matte venv (bash ${path.join(SKILL, "scripts", "setup_matte.sh")}); without it the panels cover the speaker's head`);
  } else if (mcfg.engine !== "hyperframes" && fs.existsSync(py)) {
    const args = [path.join(SKILL, "scripts", "matte.py"), path.resolve(proj, SRC), "-o", mp];
    if (ranges.length && !mcfg.all) args.push("--ranges", ranges.join(","));
    if (mcfg.model) args.push("--model", mcfg.model);
    if (mcfg.stride) args.push("--stride", String(mcfg.stride));
    if (mcfg.inferSize) args.push("--infer-size", mcfg.inferSize);
    console.log(`person matte (BiRefNet-portrait) for ${ranges.length && !mcfg.all ? ranges.join(", ") + " s of the source" : "the whole source"}; cached in assets/talk-matte.webm + .json`);
    execFileSync(py, args, { stdio: ["ignore", "inherit", "inherit"], cwd: proj, maxBuffer: 1 << 28 });
    panelMatteOk = panelMatte.length > 0;
  } else if (!fs.existsSync(mp)) {
    if (mcfg.engine !== "hyperframes") warn.push(`matte: BiRefNet venv not set up (bash ${path.join(SKILL, "scripts", "setup_matte.sh")}); used hyperframes remove-background (u2net: softer, jumpier edges)`);
    console.log("cutting the speaker out (hyperframes remove-background, ~4 fps; cached in assets/talk-matte.webm)...");
    npxSync(["hyperframes", "remove-background", path.resolve(proj, SRC), "-o", mp], { stdio: ["ignore", "ignore", "pipe"], cwd: proj, maxBuffer: 1 << 28 }); console.log("  matte done");
  }
  if (spec.matte) matteHtml = takes.map((k, i) => `
      <video id="matte-${i}" class="matte" src="assets/talk-matte.webm" data-start="${fgrid(k.f0)}" data-duration="${fgrid(k.frames)}" data-media-start="${k.a}" data-track-index="2" muted playsinline></video>`).join("");
}
// the cut-out over the panels: its own copy of the camera wrappers (pipM > baseM > snapM > pushM > punchM, every camera
// tween drives both copies) ABOVE the panel layers and under every other overlay; one clip per panel run inside each take,
// on the frame grid, always fully opaque: over the plate it is the same pixels, and fading it with the panel drew a hard
// line across the head where the half-faded panel met the half-faded cut-out (smoke test, 2026-10-13)
let matteM = "";
if (panelMatteOk) {
  let j = 0;
  for (const [t0, t1] of panelMatte) for (const k of takes) {
    const F0 = Math.max(Math.round(t0 * FPS), k.f0), F1 = Math.min(Math.round(t1 * FPS), k.f0 + k.frames);
    if (F1 - F0 < 2) continue;
    const id = `mattep-${j++}`;
    matteM += `
      <video id="${id}" class="matte" src="assets/talk-matte.webm" data-start="${fgrid(F0)}" data-duration="${fgrid(F1 - F0)}" data-media-start="${(k.a + (F0 - k.f0) / FPS).toFixed(6)}" data-track-index="8" muted playsinline></video>`;
  }
}
// the outro is a real still of the last frame, frozen under the end card
const last = takes.at(-1);
if (OUTRO > 0) execFileSync("ffmpeg", ["-v", "error", "-y", "-ss", stillAt(last.a + last.dur - 1 / FPS), "-i", path.resolve(proj, SRC), "-frames:v", "1", "-q:v", "2", "-update", "1", path.join(A, "outro.jpg")]);
const outroHtml = OUTRO > 0 ? `
      <img id="outro-still" class="fill" src="assets/outro.jpg" data-start="${fgrid(SPEECH_F)}" data-duration="${r3(OUTRO)}" data-track-index="0" />` : "";

// ---------- caption placement: face-aware, inside the platform's safe area ----------
const platform = spec.platform || "instagram";
const facePath = path.join(proj, spec.face || "build/face.json");
const face = fs.existsSync(facePath) ? JSON.parse(fs.readFileSync(facePath, "utf8")) : null;
if (!face) warn.push(`no ${path.relative(proj, facePath)}: captions sit at a fixed height and may cover the face; run scripts/face_track.py first`);
const placer = makePlacer({ face, takes, zoom: { ...zoom, snapsEdit: snaps, pushesEdit }, TOTAL, platform, ideal: spec.captions?.y ?? 1180 });

// ---------- overlays ----------
const CARD = { x: 60, y: spec.layout?.cardY ?? 990, w: 870 };
const SLOT = { x: 720, y: spec.layout?.slotY ?? 240 }; // reaction slot next to the head
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
if (JSON.stringify(spec.beats || []).includes("—")) warn.push("em dash in on-screen text");
const overlays = [];
let n = 0;
const enter = (sel, t, kind = "pop") => kind === "slide"
  ? `ft("${sel}", { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.3, ease: "power3.out" }, ${t});`
  : `ft("${sel}", { autoAlpha: 0, scale: 0.55 }, { autoAlpha: 1, scale: 1, duration: 0.38, ease: "back.out(2.2)" }, ${t});`;
const exit = (sel, end) => `tl.to("${sel}", { autoAlpha: 0, scale: 0.9, duration: 0.18, ease: "power2.in" }, ${r3(end - 0.22)});`;
const slotUsed = [];
const hiddenCaps = [];
const behindHtml = [];
const throughFront = []; // behind-styled words printed AFTER the matte: `front: true` words and the front half of `through`
const shownCaps = []; // scenes that keep captions (captions.onlyInScenes shows ONLY these)
const faceFile = path.join(proj, spec.face || "build/face.json");
const faceY = (() => {
  if (!fs.existsSync(faceFile)) return 700;
  const ys = JSON.parse(fs.readFileSync(faceFile, "utf8")).samples.filter((x) => x[1] != null).map((x) => (x[1] + x[2]) / 2).sort((a, b) => a - b);
  return ys.length ? Math.round(ys[Math.floor(ys.length / 2)]) : 700;
})();
// warn: blocks report their own problems; punchSel: the footage wrapper a textfx hook may punch
// usesShaders: a scene put a Paper shader layer on the page (the runtime script gets installed); stillAt: a frame of the footage
const motionCtx = { tl, E, r3, esc, addSfx, brand, userAsset, words, proj, LIB, faceY, warn, punchSel: "punch", usesShaders: false,
  stillAt: (t, name) => extractStill(proj, path.resolve(proj, SRC), mediaAt(t), name), get SPEECH() { return SPEECH; }, get TOTAL() { return TOTAL; } };
// stan style (lib/stan.mjs): panel runs and the speaker's move under them are worked out before any beat is built, so
// labels and chest captions know where the face is during a panel
const stanCtx = { tl, E, r3, esc, warn, die, fgrid, FPS, proj, LIB, A, icon, userAsset, placer, face, SPEECH, cap: spec.captions || {}, beats: spec.beats || [],
  cyr: /[\u0400-\u04FF]/.test(words.map((w) => w.word).join(" ")), beatSfx };
const stan = stanPrepare(spec.beats || [], stanCtx);

// a scene that hands over to an expand/wipe scene stays underneath until the
// incoming panel has covered it
const beatsList = spec.beats || [];
const HANDOVER = 0.45;
// animated Fluent emoji (library/emoji, scripts/emoji_fetch.py): an emoji beat whose glyph or name is in the set pops
// the VP9-alpha clip; anything else (or fluent: false, or no library) keeps the font-glyph pop
const emojiMan = fs.existsSync(path.join(EMOJI_DIR, "manifest.json")) ? emojiManifest(EMOJI_DIR) : {};
const unVS = (g) => String(g || "").replace(/\uFE0F/g, "");
const fluentSlug = (b) => b.type !== "emoji" || b.fluent === false ? null : b.name && emojiMan[b.name] ? b.name : Object.keys(emojiMan).find((k) => unVS(emojiMan[k].glyph) === unVS(b.emoji)) || null;
const fluentBeats = new Set();
const splitWins = []; // [t0, t1, shift] of split-screen broll beats
for (const b of beatsList) {
  const id = `b${n++}`;
  const t0 = E(b.at, `${b.type} at`);
  let t1 = b.to === undefined ? (b.type === "endcard" ? TOTAL : t0 + (b.type === "meme" ? 1.8 : 2.5)) : E(b.to, `${b.type} to`);
  if (b.type === "scene" && beatsList.some((o) => o !== b && o.type === "scene" && ["expand", "wipe"].includes(o.in) && Math.abs(E(o.at) - t1) < 0.06)) t1 = r3(Math.min(TOTAL, t1 + HANDOVER));
  const dur = r3(t1 - t0);
  const inSlot = ["emoji", "logo", "meme"].includes(b.type);
  if (inSlot) {
    for (const [s, e] of slotUsed) if (t0 < e && t1 > s) warn.push(`reaction slot double-booked at ${b.at} (${b.type})`);
    slotUsed.push([t0, t1]);
  }
  let inner = "", css = "";
  // cards and the reaction slot avoid the face too (unless the spec pins them)
  const CARD_H = { big: b.sub ? 230 : 180, chips: 200, strike: 190, quote: 90 + (b.lines || []).length * 70, list: 60 + (b.lines || []).length * 64 };
  let cy = CARD.y;
  if (CARD_H[b.type] && spec.layout?.cardY === undefined && face) {
    const pc = placer.card(t0, t1, CARD_H[b.type] * (spec.layout?.compact ? 0.8 : 1));
    if (pc) cy = pc.y;
    else if (b.type === "big") {
      // close-up: no room for a card without covering the face, so the number
      // becomes a short full-screen accent scene instead (voice continues)
      warn.push(`big at ${b.at}: no room beside the face, promoted to a full-screen scene`);
      const subText = typeof b.sub === "string" ? b.sub : null;
      Object.assign(b, { type: "scene", kind: "sentence", bg: "accent", in: b.in ?? "expand", out: b.out ?? "blur", lines: subText ? [subText] : [], hero: { text: b.text, at: b.at, size: b.text.length > 6 ? 170 : 230 }, sfx: b.sfx });
      delete b.sub;
    } else warn.push(`${b.type} at ${b.at}: no room beside the face for a card (close-up); make it a full-screen scene`);
  }
  let slotPos = null;
  if (["emoji", "logo", "meme"].includes(b.type) && b.x === undefined && b.y === undefined && face) {
    const eSize = fluentSlug(b) ? (b.size ?? 260) : 360; // the Fluent source is 256 px: keep it <= ~280
    slotPos = placer.slot(t0, t1, b.type === "emoji" ? eSize : b.type === "logo" ? 280 : (b.w ?? 320), b.type === "emoji" ? eSize : 300);
    if (!slotPos) { warn.push(`${b.type} at ${b.at}: the face fills the frame, no room beside it: skipped`); continue; }
  }
  const box = (html, x = CARD.x, y = cy, w = CARD.w) => `<div id="${id}-in" class="ov card" style="left:${x}px;top:${y}px;width:${w}px">${html}</div>`;

  switch (b.type) {
    case "big": {
      inner = box(`<div class="big-text" id="${id}-n">${esc(b.text)}</div>${b.sub ? `<div class="big-sub">${esc(b.sub)}</div>` : ""}`);
      tl.push(enter(`#${id}-in`, t0));
      const num = /^([^\d]*)([\d,.]+)(.*)$/.exec(b.text);
      if (b.count && num) {
        const target = parseFloat(num[2].replace(/,/g, ""));
        tl.push(`(() => { const o = { v: 0 }, el = document.getElementById("${id}-n"); tl.to(o, { v: ${target}, duration: 0.6, ease: "power2.out", onUpdate: () => { el.textContent = ${JSON.stringify(num[1])} + Math.round(o.v).toLocaleString("en-US") + ${JSON.stringify(num[3])}; } }, ${t0}); })();`);
      }
      beatSfx(b, t0, ["whoosh-cine", "impact"], "big", { lead: 0.08 });
      break;
    }
    case "chips": {
      const items = b.items.map((it, i) => {
        const img = it.icon ? icon(it.icon) : it.src ? userAsset(it.src) : null;
        const face = img ? `<img src="${img}" style="${it.invert ? "filter:invert(1);" : ""}"/>` : `<span>${esc(it.text ?? "")}</span>`;
        const at = it.at !== undefined ? E(it.at, "chip") : t0 + i * 0.35;
        tl.push(`ft("#${id}-c${i}", { autoAlpha: 0, scale: 0.4, y: 30 }, { autoAlpha: 1, scale: 1, y: 0, duration: 0.35, ease: "back.out(2.4)" }, ${r3(at)});`);
        beatSfx(it, at, "pop", "chip");
        return `<div id="${id}-c${i}" class="chip"><div class="chip-face" style="background:${it.bg || "#fff"};color:${it.fg || "#111"}">${face}</div>${it.label ? `<div class="chip-label">${esc(it.label)}</div>` : ""}</div>`;
      });
      inner = `<div id="${id}-in" class="ov chips" style="left:${CARD.x}px;top:${cy}px;width:${CARD.w}px">${items.join("")}</div>`;
      break;
    }
    case "strike": {
      const st = E(b.strikeAt ?? b.at + 0.6, "strikeAt");
      inner = box(`<div class="strike-wrap"><div class="big-text">${esc(b.text)}</div><div id="${id}-line" class="strike-line"></div></div><div id="${id}-x" class="strike-x">✗</div>`);
      tl.push(enter(`#${id}-in`, t0));
      tl.push(`ft("#${id}-line", { scaleX: 0 }, { scaleX: 1, duration: 0.22, ease: "power2.out" }, ${st});`);
      tl.push(`ft("#${id}-x", { autoAlpha: 0, scale: 2.2 }, { autoAlpha: 1, scale: 1, duration: 0.25, ease: "back.out(2)" }, ${r3(st + 0.15)});`);
      beatSfx(b, st, "whoosh", "strike");
      break;
    }
    case "quote": {
      const lines = b.lines.map((l, i) => {
        const at = E(l.at, "quote line");
        tl.push(`ft("#${id}-l${i}", { autoAlpha: 0, y: 18 }, { autoAlpha: 1, y: 0, duration: 0.3, ease: "power3.out" }, ${at});`);
        if (l.big) beatSfx(l, at, "impact", "quote big line");
        return `<div id="${id}-l${i}" class="${l.big ? "q-big" : "q-line"}">${esc(l.text)}</div>`;
      });
      inner = box(`${b.header ? `<div class="q-head">${esc(b.header)}</div>` : ""}${lines.join("")}`);
      tl.push(enter(`#${id}-in`, t0, "slide"));
      break;
    }
    case "list": {
      const sa = b.stampAt !== undefined ? E(b.stampAt, "stampAt") : null;
      const lines = b.lines.map((l, i) => {
        const at = E(l.at, "list line");
        tl.push(`ft("#${id}-l${i}", { autoAlpha: 0, x: -24 }, { autoAlpha: 1, x: 0, duration: 0.28, ease: "power3.out" }, ${at});`);
        beatSfx(l, at, "pop", "list line");
        if (sa !== null) tl.push(`ft("#${id}-s${i}", { scaleX: 0 }, { scaleX: 1, duration: 0.2 }, ${r3(sa + 0.12 + i * 0.08)});`);
        return `<div id="${id}-l${i}" class="l-line"><span class="l-num">${i + 1}</span><span class="l-text">${esc(l.text)}<i id="${id}-s${i}" class="l-strike"></i></span></div>`;
      });
      const stamp = sa !== null ? `<div id="${id}-stamp" class="stamp">${esc(b.stamp || "nope")}</div>` : "";
      inner = box(`${lines.join("")}${stamp}`);
      tl.push(enter(`#${id}-in`, t0, "slide"));
      if (sa !== null) {
        tl.push(`ft("#${id}-stamp", { autoAlpha: 0, scale: 2.6, rotation: -30 }, { autoAlpha: 1, scale: 1, rotation: -12, duration: 0.22, ease: "power4.in" }, ${sa});`);
        beatSfx({ sfx: b.stampSfx }, sa, ["impact", "buzzer-1"], "stamp");
      }
      break;
    }
    case "emoji": {
      const slug = fluentSlug(b);
      if (slug) {
        const size = b.size ?? 260, x = slotPos ? slotPos.x : b.x ?? 760, y = slotPos ? slotPos.y : b.y ?? SLOT.y;
        installEmoji(proj, [slug], emojiMan);
        inner = emojiPopHtml({ id: `${id}-e`, slug, item: emojiMan[slug], x, y, size, at: t0, dur });
        tl.push(emojiPopJs({ id: `${id}-e`, at: t0, dur, side: x + size / 2 > W / 2 ? "right" : "left", kind: emojiMan[slug].kind }));
        fluentBeats.add(id);
        beatSfx(b, t0, "pop", "emoji");
        break;
      }
      if (b.name && !b.emoji) die(`emoji at ${b.at}: '${b.name}' is not in library/emoji (run scripts/emoji_fetch.py, or give a glyph)`);
      inner = `<div id="${id}-in" class="ov emoji" style="left:${slotPos ? slotPos.x : b.x ?? 690}px;top:${slotPos ? slotPos.y : b.y ?? SLOT.y}px;width:360px;height:360px;font-size:290px;line-height:360px">${b.emoji}</div>`;
      tl.push(enter(`#${id}-in`, t0));
      tl.push(`ft("#${id}-in", { rotation: -14 }, { rotation: 0, duration: 0.6, ease: "elastic.out(1.2,0.35)" }, ${t0});`);
      beatSfx(b, t0, "pop", "emoji");
      break;
    }
    case "logo": {
      const img = b.icon ? icon(b.icon) : userAsset(b.src);
      inner = `<div id="${id}-in" class="ov logo" style="left:${slotPos ? slotPos.x : SLOT.x}px;top:${slotPos ? slotPos.y : SLOT.y}px;background:${b.bg || "#fff"}"><img src="${img}" style="${b.invert ? "filter:invert(1);" : ""}"/></div>`;
      tl.push(enter(`#${id}-in`, t0));
      beatSfx(b, t0, "pop", "logo");
      break;
    }
    case "broll": {
      // full-bleed video cutaway (e.g. AI B-roll): timed muted video inside an UNtimed wrapper, like meme clips;
      // captions (z 8) stay on top. "in" = seconds into the clip, "zoom" = [from, to] slow push.
      // mode "split": the clip fills the top `h` px and the speaker plate slides down into the bottom panel
      const src = userAsset(b.src);
      const [z0, z1] = b.zoom ?? [1.0, 1.08];
      const bh = b.mode === "split" ? (b.h ?? 960) : 1920;
      if (b.mode === "split") splitWins.push([t0, t1, b.shift ?? 560]);
      inner = `<div id="${id}-in" class="ov broll" style="left:0;top:0;width:${W}px;height:${bh}px;overflow:hidden;background:#000">
        <video id="${id}-v" src="${src}" data-start="${t0}" data-duration="${dur}" data-media-start="${b.in ?? 0}" muted playsinline style="width:100%;height:100%;object-fit:cover;display:block;${b.grade ? `filter:${b.grade};` : ""}"></video></div>`;
      tl.push(`ft("#${id}-in", { autoAlpha: 0, filter: "blur(22px)", scale: 1.06 }, { autoAlpha: 1, filter: "blur(0px)", scale: 1, duration: 0.2, ease: "power2.out" }, ${t0});`);
      tl.push(`ft("#${id}-v", { scale: ${z0} }, { scale: ${z1}, duration: ${dur}, ease: "none" }, ${t0});`);
      tl.push(`tl.to("#${id}-in", { autoAlpha: 0, duration: 0.1 }, ${r3(t1 - 0.1)});`);
      if (b.sfx) beatSfx(b, t0, null, "broll in");
      break;
    }
    case "title": {
      // giant display words that pop in one by one on their spoken times (`words: [{text, at}]`), or a whole `text` at once
      const ws = b.words ?? [{ text: b.text, at: b.at }];
      const pop = (b.anim ?? "pop") === "pop";
      const spans = ws.map((w, i) => {
        const at = E(w.at, "title word");
        tl.push(pop
          ? `ft("#${id}-w${i}", { autoAlpha: 0, scale: 0.8 }, { autoAlpha: 1, scale: 1, duration: 0.16, ease: "back.out(2)" }, ${at});`
          : `ft("#${id}-w${i}", { autoAlpha: 0, scale: 0.82, filter: "blur(14px)" }, { autoAlpha: 1, scale: 1, filter: "blur(0px)", duration: 0.24, ease: "power3.out" }, ${at});`);
        return `<span id="${id}-w${i}" style="display:inline-block;margin:0 0.14em">${esc(w.text)}</span>`;
      }).join(" ");
      inner = `<div id="${id}-in" class="ov title" style="left:${b.x ?? 60}px;right:${b.x ?? 60}px;top:${b.y ?? 190}px;z-index:4;text-align:${b.align ?? "center"};font-family:'${b.font ?? brand.font ?? "Inter"}', Inter, sans-serif;font-size:${b.size ?? 120}px;font-weight:${b.weight ?? 900};line-height:0.98;letter-spacing:${b.tracking ?? "-2px"};text-transform:uppercase;color:${b.color ?? "#fff"};text-shadow:${b.glow ? `0 0 28px ${b.glow}, ` : ""}0 6px 24px rgba(0,0,0,.45)">${spans}</div>`;
      if (b.sfx) beatSfx(b, t0, null, "title");
      break;
    }
    case "meme": {
      const { dir, meta } = memeLib(b.id);
      const file = meta.clip || meta.image;
      const dst = `assets/memes/${b.id}-${path.basename(file)}`;
      fs.copyFileSync(path.join(dir, file), path.join(proj, dst));
      const w = b.w ?? meta.w ?? 320;
      const x = b.x ?? (slotPos ? slotPos.x : Math.min(W - w - 40, SLOT.x)), y = b.y ?? (slotPos ? slotPos.y : SLOT.y);
      const tilt = b.tilt ?? (n % 2 ? 4 : -4);
      if (meta.clip) {
        // alpha webm: timed video inside an UNtimed wrapper; the wrapper animates
        const clipIn = b.in ?? meta.in ?? 0; // beat-level "in": start later in the clip
        const md = Math.min(dur, (meta.duration ?? dur) - clipIn);
        inner = `<div id="${id}-in" class="ov meme-clip${meta.has_alpha ? "" : " meme-framed"}" style="left:${x}px;top:${y}px;width:${w}px">
        <video id="${id}-v" src="${dst}" data-start="${t0}" data-duration="${r3(md)}" data-media-start="${clipIn}" muted playsinline style="width:100%;display:block"></video></div>`;
        if (meta.has_audio && b.audio !== false) {
          overlays.push({ audio: `<audio id="${id}-a" src="${dst}" data-start="${t0}" data-duration="${r3(md)}" data-media-start="${clipIn}" data-track-index="12" data-volume="${volFor("meme", b.db ?? 0)}"></audio>` });
          sfxEvents.push({ t: t0, id: `meme:${b.id}`, role: "meme", vol: volFor("meme", b.db ?? 0), dur: md, src: dst, why: "meme clip audio" });
        }
        tl.push(`ft("#${id}-in", { autoAlpha: 0, scale: 0.5, rotation: ${tilt + 14} }, { autoAlpha: 1, scale: 1, rotation: ${tilt}, duration: 0.3, ease: "back.out(2)" }, ${t0});`);
        tl.push(`tl.to("#${id}-in", { autoAlpha: 0, scale: 0.85, duration: 0.15 }, ${r3(t0 + md - 0.17)});`);
        if (b.sfx) beatSfx(b, t0, null, "meme extra");
      } else {
        inner = `<div id="${id}-in" class="ov meme-img" style="left:${x}px;top:${y}px;width:${w}px"><img src="${dst}"/></div>`;
        tl.push(`ft("#${id}-in", { autoAlpha: 0, scale: 0.5, rotation: ${tilt + 14} }, { autoAlpha: 1, scale: 1, rotation: ${tilt}, duration: 0.32, ease: "back.out(2)" }, ${t0});`);
        // default punch: vine boom when the (private) rip kit has it, else a licensed impact
        const memeDefault = meta.sfx && sfxManifest[meta.sfx] ? meta.sfx : sfxManifest["vine-boom"] ? "vine-boom" : "cinematic-deep-boom" in sfxManifest ? "cinematic-deep-boom" : "impact";
        beatSfx(b, t0, memeDefault, "meme image");
      }
      break;
    }
    case "endcard": {
      inner = `<div id="${id}-dim" class="ov dim"></div><div id="${id}-in" class="ov endcard">${b.title ? `<div class="ec-title">${esc(b.title)}</div>` : ""}${b.line ? `<div class="ec-line">${esc(b.line)}</div>` : ""}${b.url ? `<div class="ec-url">${esc(b.url)}</div>` : ""}</div>`;
      tl.push(`ft("#${id}-dim", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, ${t0});`);
      tl.push(enter(`#${id}-in`, r3(t0 + 0.1), "slide"));
      beatSfx(b, t0, "whoosh", "endcard");
      break;
    }
    case "behind": {
      // lives INSIDE the camera wrappers, between the plate and the matte, so it
      // zooms with the speaker and the person stays in front of the letters
      // (front: true = the same word over the matte; through: true = it slides across and passes through the speaker)
      if (!spec.matte && !b.front) die("a 'behind' beat needs \"matte\": true (a person cut-out of talk.mp4)");
      // fit the frame width (display type runs ~0.8 em per char), and sit where the
      // head is so the matte actually covers part of the letters
      const size = Math.min(b.size ?? 300, Math.floor(1180 / Math.max(1, b.text.length * 0.8)));
      let y = b.y;
      const sp = face ? placer.span(t0, t1) : null;
      if (y === undefined) y = sp && sp.seen ? Math.round(Math.max(placer.safeTop, sp.top + (sp.eyes - sp.top) * 0.35 - size * 0.55)) : 380;
      const color = b.color ?? brand.accent;
      if (b.through) {
        // the word slides right to left; left of the face centre it is clipped into the layer under the matte (behind
        // the head), right of it into the layer over the matte (in front), so it passes through the speaker. It crosses
        // the face centre half-way through the beat: set at/to symmetric around the spoken word.
        const cx = sp && sp.seen ? Math.round((sp.left + sp.right) / 2) : W / 2;
        const word = (side) => `<div id="${id}-${side}" class="clip behind" data-start="${t0}" data-duration="${dur}" data-track-index="${side === "l" ? 1 : 3}" style="clip-path:${side === "l" ? `inset(0 ${W - cx}px 0 0)` : `inset(0 0 0 ${cx}px)`}"><div id="${id}-${side}-in" class="behind-in" style="top:${y}px;font-size:${size}px;color:${color}">${esc(b.text)}</div></div>`;
        behindHtml.push(word("l"));
        throughFront.push(word("r"));
        const dx = cx - W / 2, run = W + 100; // start and end fully off screen
        for (const side of ["l", "r"]) tl.push(`ft("#${id}-${side}-in", { x: ${dx + run} }, { x: ${dx - run}, duration: ${dur}, ease: "none" }, ${t0});`);
        beatSfx(b, r3(t0 + dur / 2), "whoosh", "through word", { lead: 0.2 });
        break;
      }
      (b.front ? throughFront : behindHtml).push(`<div id="${id}" class="clip behind" data-start="${t0}" data-duration="${dur}" data-track-index="${b.front ? 3 : 1}"><div id="${id}-in" class="behind-in" style="top:${y}px;font-size:${size}px;color:${color}">${esc(b.text)}</div></div>`);
      tl.push(`ft("#${id}-in", { autoAlpha: 0, y: 80, scaleY: 1.6 }, { autoAlpha: 1, y: 0, scaleY: 1, duration: 0.45, ease: "expo.out" }, ${t0});`);
      tl.push(`tl.to("#${id}-in", { autoAlpha: 0, y: -40, duration: 0.2, ease: "power2.in" }, ${r3(t1 - 0.22)});`);
      beatSfx(b, t0, "impact", b.front ? "front word" : "behind word");
      break;
    }
    case "cutout": {
      // the pre-rendered window lives with the takes (cutoutHtml); only its sound is placed here (a sticker pops on `freeze`)
      if (b.sfx) beatSfx(b, b.fx === "sticker" && b.freeze !== undefined ? E(b.freeze, "cutout freeze") : t0, null, `cutout ${b.fx}`);
      continue;
    }
    case "textfx": {
      // kinetic type over the footage, or on its own ground with bg (lib/kinetic.mjs); captions hide unless captions: true
      const bb = { ...(spec.textfx?.[b.kind] || {}), ...b };
      if (bb.y === undefined && !bb.bg) {
        const h = blockHeight(bb);
        const pc = face ? placer.card(t0, t1, h) : null;
        bb.y = pc ? placeY(bb, pc.y) : placeY(bb, Math.min(1500 - h, 1180 - h / 2)); // below the chin, inside the safe area
        if (face && !pc) warn.push(`textfx ${b.kind} at ${b.at}: no room beside the face; give it a bg (full-screen) or a y`);
      }
      inner = buildKinetic(bb, id, t0, t1, motionCtx);
      if (b.captions !== true) hiddenCaps.push([t0, t1]); else shownCaps.push([t0, t1]);
      break;
    }
    case "panel": case "hook": case "diagram": case "step": case "cta": case "aside": {
      const r = stanBeat(b, id, t0, t1, stan, stanCtx);
      inner = r.html;
      if (r.timedInside) b._timedInside = true;
      if (r.track) b._track = r.track;
      if (r.z && panelMatteOk) b._z = r.z;
      break;
    }
    case "scene": {
      const sd = spec.scenes || {};
      const bb = { ...(sd[b.kind] || {}), ...b };
      if (b.in === undefined && sd.default_in) bb.in = sd.default_in;
      inner = buildScene(bb, id, t0, t1, motionCtx);
      if (b.captions !== true) hiddenCaps.push([t0, t1]); else shownCaps.push([t0, t1]);
      break;
    }
    default:
      die(`unknown beat type '${b.type}'`);
  }
  if (b.type === "behind") continue;
  if (!["endcard", "scene", "broll", "textfx"].includes(b.type) && !isStanBeat(b) && !fluentBeats.has(id) && !(b.type === "meme" && memeLib(b.id).meta.clip)) tl.push(exit(`#${id}-in`, t1));
  // a timed <video> inside (B-roll, meme clip, animated emoji, a stan panel) needs an untimed wrapper; the emoji pop has its own exit
  const clipMeme = b.type === "broll" || b._timedInside || fluentBeats.has(id) || (b.type === "meme" && memeLib(b.id).meta.clip);
  overlays.push({ html: clipMeme
    ? `<div id="${id}" class="layer"${b._z ? ` style="z-index:${b._z}"` : ""}>${inner}</div>` // the <video> inside is the timed element; a timed wrapper would break it
    : `<div id="${id}" class="clip layer" data-start="${t0}" data-duration="${dur}" data-track-index="${b._track ?? (b.type === "scene" || b.type === "textfx" ? 4 : inSlot ? 3 : 2)}">${inner}</div>` });
}

// split-screen B-roll: slide the speaker plate down once per run of adjacent split beats
{
  const runs = [];
  for (const [a, b, sh] of [...splitWins].sort((x, y) => x[0] - y[0])) { if (runs.length && a <= runs.at(-1)[1] + 0.6) runs.at(-1)[1] = Math.max(runs.at(-1)[1], b); else runs.push([a, b, sh]); }
  for (const [a, b, sh] of runs) {
    tl.push(`tl.to("#pip", { y: ${sh}, duration: 0.28, ease: "power3.inOut" }, ${r3(Math.max(0, a - 0.05))});`);
    tl.push(`tl.to("#pip", { y: 0, duration: 0.28, ease: "power3.inOut" }, ${r3(b - 0.2)});`);
  }
  spec._splitRuns = runs;
}
stanPipTweens(stan, stanCtx);
for (const s of spec.sfx || []) addSfx(E(s.at, "sfx"), s.id, "manual", { db: s.db ?? 0, lead: s.lead ?? 0 });

// ---------- SFX rules ----------
sfxEvents.sort((a, b) => a.t - b.t);
const memeHits = sfxEvents.filter((e) => e.role === "meme");
const seenMeme = new Set();
for (const e of memeHits) {
  if (seenMeme.has(e.id)) warn.push(`meme sound '${e.id}' used twice; never repeat a meme sound in one reel`);
  seenMeme.add(e.id);
}
for (let i = 1; i < memeHits.length; i++) if (memeHits[i].t - memeHits[i - 1].t < 8) warn.push(`meme sounds ${memeHits[i - 1].id} and ${memeHits[i].id} only ${(memeHits[i].t - memeHits[i - 1].t).toFixed(1)}s apart (want >= 8 s)`);
const perMin = (xs) => (xs.length / Math.max(TOTAL, 1)) * 60;
// a layered hit (whoosh + impact on one frame) is one event to the ear
const accent = sfxEvents.filter((e) => e.role !== "ui").filter((e, i, xs) => !xs.slice(0, i).some((p) => Math.abs(p.t - e.t) < 0.2));
if (perMin(memeHits) > 3.5) warn.push(`${perMin(memeHits).toFixed(1)} meme sounds/min (want 1-3)`);
if (perMin(accent) > 14) warn.push(`${perMin(accent).toFixed(1)} whoosh/impact/meme hits per min (want <= 12)`);
// taste: only the user's own feedback is quoted as "you said"; a learned rule says "skill rule"
for (const w of checkTaste(spec, { takes, wordsOrig: allWords, sfxEvents, proj, raw: rawSpec }, taste)) warn.push(`taste [${w.id}] ${w.msg}; ${w.quote}`);
// a meme hit should land in air, not on top of speech
for (const e of memeHits) {
  const talking = words.filter((w) => w.start < e.t + 0.5 && w.end > e.t + 0.05);
  if (talking.length) warn.push(`meme sound ${e.id} at ${e.t}s lands on speech ("${talking.map((w) => w.word).join(" ")}"); put it in a pause or on the last word's end`);
}
const sfxAudio = sfxEvents.filter((e) => !e.id.startsWith("meme:")).map((e, i) =>
  `<audio id="sfx-${i}" src="${e.src}" data-start="${e.t}" data-duration="${r3(Math.min(e.dur, TOTAL - e.t))}" data-track-index="${14 + (i % 4)}" data-volume="${e.vol}"></audio>`);

motionCtx.placeCaption = (t0, t1, h) => placer.place(t0, t1, h);
motionCtx.sidePad = placer.sidePad;

// ---------- captions ----------
const cap = { style: "house", group: 3, highlight: null, ...(spec.captions || {}) };
if (cap.style === "clean" && !cap.highlight) cap.highlight = brand.accent;
const groups = [];
let cur = [];
for (const w of words) {
  if (cur.length && (w.start - cur.at(-1).end > 0.6)) { groups.push(cur); cur = []; }
  cur.push(w);
  if (cur.length >= cap.group || /[.?!,]$/.test(w.word)) { groups.push(cur); cur = []; }
}
if (cur.length) groups.push(cur);
// captions.onlyInScenes: the recording already has burned-in captions, so ours
// appear only over scenes that cover them (e.g. an image scene)
const complement = (wins) => { const out = []; let c = 0; for (const [a, b] of [...wins].sort((x, y) => x[0] - y[0])) { if (a > c) out.push([c, a]); c = Math.max(c, b); } if (c < TOTAL) out.push([c, TOTAL + 1]); return out; };
// every caption style hides under full-screen scenes (editorial and the templates handle their own)
// caption templates: hype, explosive, line-focus, neo-minimal, karaoke-fill, highlighter (lib/caption-templates.mjs)
const isTpl = TEMPLATE_NAMES.includes(cap.style);
if (cap.style !== "editorial" && cap.style !== "none" && !isTpl) {
  const wins = cap.onlyInScenes ? complement(shownCaps) : hiddenCaps;
  const merged = [];
  for (const [a, b] of [...wins].sort((x, y) => x[0] - y[0])) { if (merged.length && a <= merged.at(-1)[1] + 0.05) merged.at(-1)[1] = Math.max(merged.at(-1)[1], b); else merged.push([a, b]); }
  tl.push(`tl.set("#caps", { autoAlpha: 1 }, 0);`);
  for (const [a, b] of merged) { tl.push(`tl.to("#caps", { autoAlpha: 0, duration: 0.08 }, ${r3(a)});`); tl.push(`tl.to("#caps", { autoAlpha: 1, duration: 0.12 }, ${r3(b - 0.05)});`); }
}
const edit = cap.style === "editorial" ? buildEditorialCaptions(words, cap, motionCtx, cap.onlyInScenes ? complement(shownCaps) : hiddenCaps) : null;
// a template keeps its own grouping and size: only reel.json's own captions block overrides it, never the style
// preset (a preset's group/y would also switch off the face-aware placer)
fs.mkdirSync(path.join(proj, "build"), { recursive: true });
const aiTags = isTpl && cap.ai ? await aiTag(words, { cache: path.join(proj, "build", "ai-tags.json") }) : undefined;
const tasteCap = Object.fromEntries(tasteApplied.filter((x) => x.path.startsWith("captions.")).map((x) => [x.path.slice(9), x.value]));
const tpl = isTpl ? buildTemplateCaptions(words, { ...tasteCap, ...(rawSpec.captions || {}), style: cap.style, ai: aiTags }, motionCtx, cap.onlyInScenes ? complement(shownCaps) : hiddenCaps) : null;
for (const w of tpl?.warnings || []) warn.push(`captions: ${w}`);
// chest (stan style): phrases at the chest that cut on their first word, single words, forehead words (lib/stan.mjs)
const chest = cap.style === "chest" ? buildChestCaptions(words, cap, stan, { ...stanCtx, SPEECH }) : null;
const capHtml = chest ? chest.html : cap.style === "none" || edit || tpl ? "" : groups.map((g, gi) => {
  const s = Math.max(0, g[0].start - 0.05);
  const nextS = gi + 1 < groups.length ? groups[gi + 1][0].start - 0.05 : SPEECH;
  const e = Math.min(g.at(-1).end + 0.3, nextS, SPEECH);
  g.forEach((w, wi) => {
    tl.push(`ft("#cg${gi}w${wi}", { scale: 1 }, { scale: 1.08, duration: 0.08, yoyo: true, repeat: 1, ease: "power1.out" }, ${r3(w.start)});`);
    if (cap.highlight) tl.push(`tl.set("#cg${gi}w${wi}", { color: "${cap.highlight}" }, ${r3(w.start)}); tl.set("#cg${gi}w${wi}", { color: "#fff" }, ${r3(Math.min(w.end + 0.02, e - 0.01))});`);
  });
  const capSize = cap.style === "pill" ? 66 : cap.style === "clean" ? (cap.size ?? brand.capSize) : (cap.size ?? 56);
  // mini: small captions at a fixed height (reference-style); they jump to the panel seam during split-screen B-roll
  const inSplit = (spec._splitRuns || []).some(([a, b]) => s < b && e > a);
  const pl = cap.style === "mini" ? { y: inSplit ? (cap.splitY ?? 985) : (cap.y ?? 1360), mode: "fixed" } : placer.place(s, e, capSize * (cap.style === "pill" ? 1.6 : 1.3));
  return `<div id="cg${gi}" class="cap-group clip${pl.mode === "lower-face" && cap.style !== "pill" ? " cap-backed" : ""}" style="top:${pl.y}px${pl.scale && pl.scale < 1 ? `;transform:translateX(-50%) scale(${pl.scale});transform-origin:50% 0` : ""}" data-start="${r3(s)}" data-duration="${r3(Math.max(0.1, e - s))}" data-track-index="5">${g.map((w, wi) => `<span id="cg${gi}w${wi}" class="w">${esc(w.word)}</span>`).join("")}</div>`;
}).join("\n      ");

const cyr = /[\u0400-\u04FF]/.test(JSON.stringify(spec.beats || []) + words.map((w) => w.word).join(" "));
const UI_FONT = brand.font || (cyr ? "Inter" : "Geist");
const capCss = cap.style === "mini"
  ? `.cap-group { font-family: '${cap.font ?? UI_FONT}', ${UI_FONT}, system-ui, sans-serif; font-size: ${cap.size ?? 40}px; font-weight: ${cap.weight ?? 800}; color: #fff; letter-spacing: ${cap.tracking ?? "1px"}; ${cap.upper ? "text-transform: uppercase;" : ""} ${cap.stroke ? `-webkit-text-stroke: ${cap.stroke}px rgba(0,0,0,.85); paint-order: stroke fill;` : ""} text-shadow: 0 2px 10px rgba(0,0,0,.7), 0 1px 2px rgba(0,0,0,.8); max-width: 940px; }`
  : cap.style === "clean"
  ? `.cap-group { font-family: ${UI_FONT}, system-ui, sans-serif; font-size: ${cap.size ?? brand.capSize}px; font-weight: 800; color: #fff; letter-spacing: -1px; text-shadow: 0 4px 18px rgba(0,0,0,.55), 0 1px 3px rgba(0,0,0,.6); }`
  : cap.style === "pill"
  ? `.cap-group { font-family: ${UI_FONT}, system-ui, sans-serif; font-size: 66px; font-weight: 800; color: #fff; background: rgba(12,12,14,.88); border-radius: 22px; padding: 16px 32px; max-width: 900px; }`
  : `.cap-group { font-family: Arial, Helvetica, sans-serif; font-size: ${cap.size ?? 56}px; font-weight: 700; color: #fff; max-width: 900px;
      -webkit-text-stroke: 8px #000; paint-order: stroke fill; text-shadow: 0 4px 10px rgba(0,0,0,.35); }`;

// ---------- music bed ----------
let musicHtml = "";
if (spec.music) {
  if (spec.music.id === "auto") {
    const man = JSON.parse(fs.readFileSync(path.join(LIB, "music", "manifest.json"), "utf8"));
    const pickId = Object.keys(man).find((k) => (man[k].styles || []).includes(spec.style)) || "deep-techno-ambience";
    spec.music = { ...spec.music, id: pickId };
  }
  const m = buildMusic(spec.music, motionCtx, execFileSync, path, fs);
  musicHtml = m.html;
  console.log(`music: ${spec.music.id || spec.music.src} at ${m.I} LUFS -> volume ${m.vol} (${spec.music.db ?? -20} dB under the voice)`);
}

// ---------- write ----------
const FONT_NAMES = { "playfair-display": "Playfair Display", "jetbrains-mono": "JetBrains Mono", "geist-mono": "GeistMono" };
const RANGES = { latin: "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD", cyrillic: "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116" };
const fontFaces = fs.readdirSync(path.join(A, "fonts")).filter((f) => /-(latin|cyrillic)(-italic)?\.woff2$/.test(f)).map((f) => {
  const m = /^(.*)-(latin|cyrillic)(-italic)?\.woff2$/.exec(f);
  const fam = FONT_NAMES[m[1]] || m[1].split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");
  if (["Geist", "Inter", "Montserrat"].includes(fam)) return "";
  return `@font-face { font-family: "${fam}"; src: url(assets/fonts/${f}) format("woff2"); font-weight: 100 900;${m[3] ? " font-style: italic;" : ""} unicode-range: ${RANGES[m[2]]}; }`;
}).join("\n  ");
const look = spec.look || {};
if (look.film) { delete look.grade; delete look.grain; } // the graded plate already carries the stock's colour and grain
const grainHtml = look.grain ? `<div id="grain" class="look-grain" style="opacity:${look.grain}"></div>` : "";
const vignetteHtml = look.vignette ? `<div class="look-vignette" style="background:radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 45%, rgba(0,0,0,${look.vignette}) 100%)"></div>` : "";
if (look.grain) for (let t = 0, k = 0; t < TOTAL; t += 1 / 12, k++) tl.push(`tl.set("#grain", { backgroundPosition: "${(k * 137) % 400}px ${(k * 251) % 400}px" }, ${r3(t)});`);
// look.shader: Paper Shaders overlays on the speaker plate (film-grain, halftone); z 2 = over the speaker, under cards
// (over: "all" = z 7, still under the captions). The runtime redraws every layer from the hf-seek time, never rAF.
const fxSpecs = [].concat(look.shader || []).map((o) => (typeof o === "string" ? { look: o } : o));
const fxHtml = fxSpecs.map((o, i) => shaderLayerHtml({ id: `look-fx${i}`, z: o.over === "all" ? 7 : 2, ...o })).join("\n  ");
const shaderScript = fxSpecs.length || motionCtx.usesShaders ? installShaderRuntime(proj) : "";

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=${W}, height=${H}" />
<title>${esc(spec.title || "reel")}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
  @font-face { font-family: Geist; src: url(assets/fonts/geist-latin.woff2) format("woff2"); font-weight: 100 900; }
  @font-face { font-family: GeistMono; src: url(assets/fonts/geist-mono-latin.woff2) format("woff2"); }
  @font-face { font-family: Inter; src: url(assets/fonts/inter-cyrillic.woff2) format("woff2"); font-weight: 100 900; unicode-range: U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116; }
  @font-face { font-family: Inter; src: url(assets/fonts/inter-latin.woff2) format("woff2"); font-weight: 100 900; unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD; }
  @font-face { font-family: Montserrat; src: url(assets/fonts/montserrat-cyrillic.woff2) format("woff2"); font-weight: 100 900; unicode-range: U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116; }
  @font-face { font-family: Montserrat; src: url(assets/fonts/montserrat-latin.woff2) format("woff2"); font-weight: 100 900; unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD; }
  ${fontFaces}
  body { margin: 0; background: #000; }
  #root { position: relative; width: ${W}px; height: ${H}px; overflow: hidden; background: #000; font-family: ${UI_FONT}, system-ui, sans-serif; }
  #base, #snap, #push, #punch${matteM ? ", #baseM, #snapM, #pushM, #punchM" : ""} { position: absolute; inset: 0; transform-origin: ${zoom.origin || "50% 29%"}; }
  #base${matteM ? ", #baseM" : ""} { transform: scale(${zoom.base ?? 1});${look.grade ? ` filter: ${look.grade};` : ""} }
  #pip${matteM ? ", #pipM" : ""} { position: absolute; inset: 0; z-index: 1; transform-origin: 540px ${faceY}px; }${matteM ? "\n  #pipM { z-index: 2; pointer-events: none; }" : ""}
  .behind { position: absolute; inset: 0; pointer-events: none; }
  .behind-in { position: absolute; left: -40px; right: -40px; text-align: center; font-weight: 900; line-height: .86; letter-spacing: -6px; text-transform: uppercase; white-space: nowrap; font-family: ${brand.displayFont ? `"${brand.displayFont}", ` : ""}${UI_FONT}, sans-serif; }
  .matte { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .look-grain { position: absolute; inset: 0; z-index: 6; pointer-events: none; mix-blend-mode: overlay; background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='400'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='400' height='400' filter='url(%23n)' opacity='0.9'/></svg>"); }
  .look-vignette { position: absolute; inset: 0; z-index: 6; pointer-events: none; }
  .layer { z-index: 3; }
  #caps, #ecaps { z-index: 8; }
  #push video, .fill { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .layer { position: absolute; inset: 0; pointer-events: none; }
  .ov { position: absolute; box-sizing: border-box; }
  .card { background: rgba(14,14,16,.92); color: #fff; border-radius: 28px; padding: 28px 36px; box-shadow: 0 18px 50px rgba(0,0,0,.35); }
  .big-text { font-size: 96px; font-weight: 800; letter-spacing: -2px; line-height: 1.02; }
  .big-sub { font-size: 38px; font-weight: 600; color: #FFD166; margin-top: 8px; }
  .chips { display: flex; gap: 26px; }
  .chip { display: flex; flex-direction: column; align-items: center; gap: 12px; }
  .chip-face { width: 130px; height: 130px; border-radius: 30px; display: flex; align-items: center; justify-content: center; font-size: 70px; font-weight: 800; box-shadow: 0 12px 30px rgba(0,0,0,.3); }
  .chip-face img { width: 62%; height: 62%; object-fit: contain; }
  .chip-label { font-size: 30px; font-weight: 700; color: #111; background: rgba(255,255,255,.94); padding: 6px 18px; border-radius: 14px; white-space: nowrap; }
  .strike-wrap { position: relative; display: inline-block; }
  .strike-line { position: absolute; left: -8px; right: -8px; top: 52%; height: 12px; background: #FF453A; border-radius: 6px; transform-origin: 0 50%; }
  .strike-x { position: absolute; right: 36px; top: 18px; font-size: 110px; color: #FF453A; font-weight: 900; }
  .q-head { font-size: 28px; text-transform: uppercase; letter-spacing: 3px; color: #aaa; margin-bottom: 12px; }
  .q-line { font-size: 46px; font-weight: 600; line-height: 1.2; margin: 6px 0; }
  .q-big { font-size: 60px; font-weight: 800; line-height: 1.1; color: #FFD166; margin-top: 12px; }
  .l-line { display: flex; gap: 20px; align-items: baseline; font-size: 46px; font-weight: 700; margin: 8px 0; }
  .l-num { color: #FFD166; font-family: GeistMono, monospace; }
  .l-text { position: relative; }
  .l-strike { position: absolute; left: -4px; right: -4px; top: 55%; height: 6px; background: #FF453A; transform-origin: 0 50%; display: block; }
  .stamp { position: absolute; right: 30px; top: 40%; border: 8px solid #FF453A; color: #FF453A; font-size: 78px; font-weight: 900; padding: 4px 26px; border-radius: 16px; text-transform: uppercase; background: rgba(0,0,0,.25); }
  .emoji { width: 400px; height: 400px; font-size: 320px; line-height: 400px; text-align: center; filter: drop-shadow(0 20px 30px rgba(0,0,0,.35)); }
  .logo { width: 280px; height: 280px; border-radius: 62px; display: flex; align-items: center; justify-content: center; box-shadow: 0 18px 50px rgba(0,0,0,.35); }
  .logo img { width: 60%; height: 60%; object-fit: contain; }
  .meme-img { background: #fff; padding: 8px; border-radius: 14px; box-shadow: 0 18px 50px rgba(0,0,0,.4); }
  .meme-img img { width: 100%; display: block; border-radius: 8px; }
  .meme-clip video { filter: drop-shadow(0 16px 30px rgba(0,0,0,.45)); }
  .meme-framed { background: #fff; padding: 8px; border-radius: 14px; box-shadow: 0 18px 50px rgba(0,0,0,.4); }
  .meme-framed video { filter: none; border-radius: 8px; }
  .dim { inset: 0; background: rgba(0,0,0,.55); }
  .endcard { left: 90px; top: 640px; width: 900px; background: #fff; color: #111; border-radius: 34px; padding: 44px 48px; text-align: center; box-shadow: 0 24px 70px rgba(0,0,0,.45); }
  .ec-title { font-size: 72px; font-weight: 800; letter-spacing: -1px; }
  .ec-line { font-size: 38px; font-weight: 500; margin-top: 12px; color: #333; }
  .ec-url { font-family: GeistMono, monospace; font-size: 30px; margin-top: 22px; color: #555; white-space: nowrap; }
  #caps { position: absolute; left: 0; right: 0; top: 0; height: 0; }
  .cap-group { position: absolute; left: 50%; transform: translateX(-50%); width: max-content; max-width: ${W - 2 * placer.sidePad}px !important; text-align: center; line-height: 1.18; }
  .cap-backed { background: rgba(8,8,10,.55); border-radius: 20px; padding: 6px 22px; -webkit-text-stroke: 0 !important; }
  ${capCss}
  /* layout.compact: a smaller card grammar for a narrow band (e.g. under burned-in captions) */
  .compact .card { padding: 18px 28px; border-radius: 22px; }
  .compact .big-text { font-size: 70px; letter-spacing: -1px; }
  .compact .big-sub { font-size: 30px; margin-top: 4px; }
  .compact .chip-face { width: 104px; height: 104px; border-radius: 24px; font-size: 56px; }
  .compact .chip-label { font-size: 24px; padding: 4px 14px; }
  .compact .chips { gap: 22px; }
  .compact .q-head { font-size: 22px; margin-bottom: 6px; }
  .compact .q-line { font-size: 36px; margin: 2px 0; }
  .compact .q-big { font-size: 46px; margin-top: 6px; }
  .compact .l-line { font-size: 36px; margin: 2px 0; }
  .compact .strike-x { font-size: 80px; top: 8px; }
  .w { display: inline-block; margin: 0 0.2em; transform-origin: 50% 80%; }
  ${MOTION_CSS(brand)}
  ${beatsList.some((b) => b.type === "textfx") ? KINETIC_CSS(brand) : ""}
  ${fluentBeats.size ? EMOJI_POP_CSS : ""}${chest || beatsList.some(isStanBeat) ? STAN_CSS : ""}
  ${tpl ? tpl.css : ""}
</style>
</head>
<body>
<div id="root" class="${spec.layout?.compact ? "compact" : ""}" data-composition-id="main" data-start="0" data-width="${W}" data-height="${H}" data-duration="${TOTAL}" data-fps="${FPS}">
  <div id="pip"><div id="base"><div id="snap"><div id="push"><div id="punch">${takeHtml}${txHtml}${cutoutHtml}${outroHtml}${behindHtml.join("")}${matteHtml}${throughFront.join("")}
  </div></div></div></div></div>
  ${fxHtml}
  ${overlays.filter((o) => o.html).map((o) => o.html).join("\n  ")}${matteM ? `
  <div id="pipM"><div id="baseM"><div id="snapM"><div id="pushM"><div id="punchM">${matteM}
  </div></div></div></div></div>` : ""}
  ${grainHtml}${vignetteHtml}
  <div id="caps">
      ${capHtml}
  </div>
  ${edit ? edit.html : ""}
  ${tpl ? tpl.html : ""}
  ${takeAudio}
  ${overlays.filter((o) => o.audio).map((o) => o.audio).join("\n  ")}
  ${sfxAudio.join("\n  ")}
  ${musicHtml}
</div>
${shaderScript}
<script>
  const tl = gsap.timeline({ paused: true });
  // fromTo with a baseline set ONCE per element: seeks before a tween never inherit another tween's from-values,
  // and a second baseline for an element animated twice would be rendered after the first tween on a direct
  // seek and wipe it out (pip, repeated push-ins). The baseline is a gsap.set at load, not a tl.set at 0: a set at
  // 0 does not render while the playhead sits on 0, so frame 0 showed un-hidden captions and cards
  // (hyperframes lint: gsap_timeline_set_initial_hide)
  const based = new Set();
  const ft = (sel, from, to, at) => { if (!based.has(sel)) { based.add(sel); gsap.set(sel, from); } tl.fromTo(sel, from, { ...to, immediateRender: false }, Math.max(0, at)); };
  ${(matteM ? tl.map((l) => l.replace(/"#(pip|base|snap|push|punch)"/g, '"#$1, #$1M"')) : tl).join("\n  ")}
  window.__timelines["main"] = tl;
</script>
</body>
</html>
`;
fs.writeFileSync(path.join(proj, "index.html"), html);
fs.mkdirSync(path.join(proj, "build"), { recursive: true });
fs.writeFileSync(path.join(proj, "build", "sfx_events.json"), JSON.stringify({ total: TOTAL, speech: SPEECH, voiceP95: r3(voiceP95), roleDb: ROLE_DB, events: sfxEvents }, null, 2));
fs.writeFileSync(path.join(proj, "build", "words.edit.json"), JSON.stringify(words));
// textfx windows (edit time) so qa.py can put a settled frame of each block next to the contact sheet
// cutout windows (edit frames + the source frames they were cut from) so qa.py can re-count each clip
fs.writeFileSync(path.join(proj, "build", "cutouts.json"), JSON.stringify(cutoutWins, null, 1));
fs.writeFileSync(path.join(proj, "build", "textfx.json"), JSON.stringify(beatsList.filter((b) => b.type === "textfx").map((b) => ({ kind: b.kind, t0: E(b.at), t1: b.to !== undefined ? E(b.to) : null }))));
fs.writeFileSync(path.join(proj, "build", "caption_layout.json"), JSON.stringify({ platform: placer.platform, safeTop: placer.safeTop, safeBottom: placer.safeBottom, blocks: placer.log }, null, 1));
{
  const modes = {};
  for (const b of placer.log) modes[b.mode] = (modes[b.mode] || 0) + 1;
  console.log(`caption placement (${placer.platform.name}, safe y ${placer.safeTop}-${placer.safeBottom}): ${JSON.stringify(modes)}`);
  if (modes["lower-face"]) warn.push(`${modes["lower-face"]} caption block(s) in close-up fallback (under the mouth, on a backing); see build/caption_layout.json`);
}

console.log(`\n${takes.length} takes, ${SPEECH.toFixed(2)}s speech + ${OUTRO}s outro = ${TOTAL}s`);
console.log(`captions: ${chest ? chest.count + " groups (" + ["phrase", "single", "top"].map((m) => chest.groups.filter((g) => g.mode === m).length + " " + m).join(", ") + ")" : edit ? edit.count + " blocks" : tpl ? tpl.count + " groups, keywords " + tpl.groups.flatMap((g) => g.words.filter((w) => w.kw).map((w) => w.text)).join(" ") : groups.length + " groups"}, style ${cap.style}\n  ${words.map((w) => w.word).join(" ")}`);
const byRole = {};
for (const e of sfxEvents) byRole[e.role] = (byRole[e.role] || 0) + 1;
console.log(`voice p95 peak ${voiceP95.toFixed(1)} dBFS; sfx role levels vs voice ${JSON.stringify(ROLE_DB)}`);
console.log(`sfx: ${sfxEvents.length} hits ${JSON.stringify(byRole)}, ${perMin(sfxEvents).toFixed(1)}/min`);
for (const e of sfxEvents) console.log(`  ${e.t.toFixed(2).padStart(6)}s  ${e.id.padEnd(22)} ${e.role.padEnd(6)} vol ${e.vol}  (${e.why})`);
if (tasteApplied.length) console.log(`taste defaults (${taste._path}): ${tasteApplied.map((a) => `${a.path} = ${JSON.stringify(a.value)} [${a.id}]`).join("; ")}`);
// machine-readable summary for approval_sheet.py / render_report.py (no stdout parsing)
fs.writeFileSync(path.join(proj, "build", "build_report.json"), JSON.stringify({ total: TOTAL, speech: SPEECH, fps: FPS,
  takes: takes.map((k) => ({ a: k.a, b: k.b, start: r3(k.start), dur: r3(k.dur), hold: k.holdFrames / FPS })),
  warnings: [...new Set(warn)], taste: taste ? { file: taste._path, applied: tasteApplied } : null }, null, 1));
if (warn.length) console.log("\nWARNINGS:\n  " + [...new Set(warn)].join("\n  "));
console.log(`\n-> ${path.join(proj, "index.html")}`);
