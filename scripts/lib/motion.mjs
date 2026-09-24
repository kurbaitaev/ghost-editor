// Motion layer for build.mjs: full-screen graphic scenes, scene transitions,
// the editorial caption style and the music bed. Everything here emits HTML
// strings plus GSAP lines into ctx.tl, the same way build.mjs does, so the
// composition stays one paused timeline.
//
// Scenes replace the PICTURE while the voice continues (the take audio keeps
// playing underneath). Kinds:
//   card      white card: text lines + a pill word + an optional cursor click
//   stats     accent gradient: glass ring badges that land as heroes, then
//             shrink into a row with their label; rows re-center as they stack
//   fly3d     grey depth field: words placed in 3D, a camera dolly moves
//             through them, blur and brightness follow the distance to focus
//   image     a still (e.g. AI B-roll) with a slow push; captions stay on
//   sentence  kinetic sentence: words ink in as they are spoken, then a big
//             accent hero word lands and a "not X" line gets a hand-drawn X
import { spawnSync } from "node:child_process";

// Transitions in/out: blur (0.2 s dissolve through blur), expand (rounded
// panel grows from the centre), wipe (left to right), cut.

export const MOTION_CSS = (brand) => `
  .scene { position: absolute; inset: 0; overflow: hidden; }
  .scene .col { position: absolute; left: 0; right: 0; display: flex; flex-direction: column; align-items: center; }
  .sc-line { font-weight: 400; letter-spacing: -1px; line-height: 1.05; white-space: nowrap; }
  .sc-pill { display: inline-block; background: ${brand.accent}; color: #fff; font-weight: 700; border-radius: 999px; padding: 6px 34px 12px; white-space: nowrap; box-shadow: 0 10px 24px rgba(0,0,0,.18); }
  .sc-ring { position: absolute; border: 7px solid ${brand.accent}; border-radius: 50%; opacity: 0; }
  .sc-cursor { position: absolute; width: 86px; height: 86px; filter: drop-shadow(0 6px 10px rgba(0,0,0,.3)); }
  .badge { position: absolute; left: 0; top: 0; width: 330px; height: 330px; margin: -165px 0 0 -165px; border-radius: 50%;
    border: 3px solid rgba(255,255,255,.62); box-shadow: 0 0 34px rgba(255,255,255,.28), inset 0 0 44px rgba(255,255,255,.14);
    background: radial-gradient(circle at 35% 28%, rgba(255,255,255,.2), rgba(255,255,255,.03) 62%);
    display: flex; flex-direction: column; align-items: center; justify-content: center; color: #fff; text-align: center; }
  .badge .v { font-size: 104px; font-weight: 700; letter-spacing: -3px; line-height: .95; }
  .badge .s { font-size: 50px; font-weight: 600; line-height: 1; margin-top: 4px; }
  .badge-label { position: absolute; left: 0; top: 0; color: #fff; font-size: 52px; font-weight: 300; white-space: nowrap; letter-spacing: -1px; }
  .badge-label b { font-weight: 600; }
  .badge-label span { display: inline-block; margin-right: 0.28em; }
  .fly-stage { position: absolute; inset: 0; perspective: 900px; perspective-origin: 50% 45%; }
  .fly-item { position: absolute; left: 50%; top: 45%; color: #fff; text-align: center; white-space: nowrap; will-change: transform, filter; }
  .fly-item .t { font-weight: 600; letter-spacing: -2px; line-height: .95; }
  .fly-item .u { font-weight: 400; letter-spacing: -1px; margin-top: 6px; }
  .img-fill { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; transform-origin: 50% 45%; }
  .sent-lines { position: absolute; left: 0; right: 0; top: 800px; text-align: center; }
  .sent-line { font-size: 64px; font-weight: 500; color: ${brand.ink}; letter-spacing: -1.5px; line-height: 1.08; white-space: nowrap; }
  .sent-line span { display: inline-block; margin: 0 0.12em; }
  .sent-hero { position: absolute; left: 0; right: 0; top: 880px; text-align: center; font-size: 168px; font-weight: 800; color: ${brand.accent}; letter-spacing: -6px; line-height: 1; }
  .sent-sub { position: absolute; left: 0; right: 0; top: 1080px; text-align: center; font-size: 54px; font-weight: 600; color: ${brand.ink}; letter-spacing: -1px; }
  .xw { position: relative; display: inline-block; }
  .xw svg { position: absolute; left: 50%; top: 50%; width: 120px; height: 90px; margin: -45px 0 0 -60px; overflow: visible; }
  /* ui window (launch) */
  .ui-win { position: absolute; left: 70px; right: 70px; border-radius: 30px; background: #15151b; border: 1.5px solid rgba(255,255,255,.1); box-shadow: 0 40px 90px rgba(0,0,0,.55), 0 0 120px ${brand.accent}33; overflow: hidden; }
  .ui-bar { height: 64px; display: flex; align-items: center; gap: 12px; padding: 0 26px; border-bottom: 1px solid rgba(255,255,255,.08); color: rgba(255,255,255,.55); font-family: ${brand.mono ? `"${brand.mono}", ` : ""}ui-monospace, monospace; font-size: 24px; }
  .ui-bar i { width: 16px; height: 16px; border-radius: 50%; background: #3a3a44; display: inline-block; }
  .ui-bar b { margin-left: 14px; font-weight: 500; }
  .ui-body { padding: 34px 40px 40px; }
  .ui-prompt { font-family: ${brand.mono ? `"${brand.mono}", ` : ""}ui-monospace, monospace; font-size: 42px; line-height: 1.3; color: #fff; white-space: pre-wrap; min-height: 60px; }
  .ui-prompt .pr { color: ${brand.accent}; margin-right: 18px; }
  .ui-caret { display: inline-block; width: 20px; height: 46px; background: ${brand.accent}; vertical-align: -8px; margin-left: 4px; }
  .ui-line { font-size: 40px; color: rgba(255,255,255,.88); margin-top: 22px; display: flex; gap: 18px; align-items: center; }
  .ui-line .ck { width: 40px; height: 40px; border-radius: 50%; background: ${brand.accent}; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 26px; font-weight: 800; flex: none; }
  .ui-label { position: absolute; left: 0; right: 0; text-align: center; font-family: ${brand.mono ? `"${brand.mono}", ` : ""}ui-monospace, monospace; font-size: 30px; letter-spacing: 6px; text-transform: uppercase; color: ${brand.accent}; }
  /* device (launch) */
  .dev { position: absolute; left: 50%; width: 480px; height: 980px; margin-left: -240px; border-radius: 72px; background: #0b0b0e; border: 14px solid #1d1d22; box-shadow: 0 50px 110px rgba(0,0,0,.55), inset 0 0 0 2px #2c2c33; overflow: hidden; }
  .dev::before { content: ""; position: absolute; top: 18px; left: 50%; width: 130px; height: 36px; margin-left: -65px; border-radius: 20px; background: #000; z-index: 2; }
  .dev img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .dev .scr { position: absolute; inset: 0; padding: 110px 34px 40px; color: #fff; }
  .dev .scr div { font-size: 34px; line-height: 1.25; margin-bottom: 18px; padding: 18px 22px; border-radius: 22px; background: rgba(255,255,255,.08); }
  .dev .scr div.me { background: ${brand.accent}; margin-left: 60px; }
  /* kinetic type */
  .kin-world { position: absolute; left: 0; top: 0; width: 960px; transform-origin: 0 0; }
  .kin-text { position: absolute; left: 0; top: 0; width: 960px; text-align: center; line-height: 1.12; letter-spacing: -2px; font-weight: 800; }
  .kin-text span { display: inline-block; margin: 0 0.14em; }
  .kin-text .em { color: ${brand.accent}; }
  .kin-text .it { font-style: italic; font-weight: 400; }
  /* serif keyword captions (cinematic) */
  .eser { display: inline-block; margin: 0 0.13em; font-family: "${brand.serif || "Georgia"}", Georgia, serif; font-style: italic; font-weight: 500; color: ${brand.accent}; text-shadow: 0 0 22px ${brand.accent}99, 0 2px 12px rgba(0,0,0,.4); letter-spacing: 0; }
  /* editorial captions */
  #ecaps { position: absolute; left: 0; right: 0; top: 0; height: 0; }
  .eblock { position: absolute; left: 130px; right: 130px; text-align: center; }
  .ebacked { background: rgba(8,8,10,.5); border-radius: 26px; padding: 10px 0 14px; }
  .eline { display: block; font-size: ${brand.capSize}px; line-height: 1.08; letter-spacing: -1px; white-space: nowrap; }
  .ew { display: inline-block; margin: 0 0.13em; color: #fff; font-weight: 700; text-shadow: 0 3px 14px rgba(0,0,0,.35); }
  .etag { display: inline-block; background: ${brand.accent}; color: #fff; font-weight: 700; border-radius: 16px; padding: 2px 18px 8px; margin-bottom: 6px; box-shadow: 0 6px 18px rgba(0,0,0,.25); font-size: ${Math.round(brand.capSize * 0.95)}px; }
  .ehl { position: relative; display: inline-block; margin: 0 0.13em; }
  .ehl i { position: absolute; left: -8px; right: -8px; top: 12%; bottom: 2%; background: ${brand.accent}; transform-origin: 0 50%; }
  .ehl .ew { position: relative; margin: 0; }
`;

const CURSOR_SVG = `<svg viewBox="0 0 64 64"><path d="M22 6c-2.8 0-5 2.2-5 5v25l-4.6-4.3c-2-1.9-5.2-1.7-7 .4-1.7 2-1.5 5 .3 6.8l13.8 13.8C23.6 56.9 28.4 59 33.5 59H38c9.4 0 17-7.6 17-17V30c0-2.8-2.2-5-5-5-.9 0-1.8.3-2.5.7-.6-2.2-2.6-3.7-4.9-3.7-1.2 0-2.3.4-3.2 1.1-.8-1.9-2.7-3.1-4.8-3.1-.9 0-1.8.2-2.6.7V11c0-2.8-2.2-5-5-5z" fill="#fff" stroke="#111" stroke-width="3" stroke-linejoin="round"/></svg>`;
const X_SVG = (color, id) => `<svg viewBox="0 0 120 90"><path id="${id}a" d="M8 12 Q60 50 112 80" fill="none" stroke="${color}" stroke-width="9" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/><path id="${id}b" d="M110 8 Q58 42 10 84" fill="none" stroke="${color}" stroke-width="9" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`;

const norm = (s) => s.toLowerCase().replace(/[^\p{L}\p{N}%]+/gu, "");

// transitions ----------------------------------------------------------------
function transIn(ctx, sel, kind, t0) {
  const { tl } = ctx;
  if (kind === "cut" || !kind) return;
  if (kind === "blur") tl.push(`ft("${sel}", { autoAlpha: 0, filter: "blur(28px)", scale: 1.05 }, { autoAlpha: 1, filter: "blur(0px)", scale: 1, duration: 0.22, ease: "power2.out" }, ${t0});`);
  if (kind === "expand") tl.push(`ft("${sel}", { clipPath: "inset(40% 26% 40% 26% round 120px)" }, { clipPath: "inset(0% 0% 0% 0% round 0px)", duration: 0.42, ease: "expo.inOut" }, ${t0});`);
  if (kind === "wipe") tl.push(`ft("${sel}", { clipPath: "inset(0% 100% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.3, ease: "power3.inOut" }, ${t0});`);
  if (kind === "glitch") {
    // six stepped frames of slice + RGB-ish shift, then clean: deterministic, no random
    const { r3 } = ctx;
    const steps = [[-26, "inset(18% 0% 52% 0%)", 120], [18, "inset(55% 0% 12% 0%)", 250], [-10, "inset(0% 0% 70% 0%)", 60], [14, "inset(30% 0% 30% 0%)", 300], [-6, "inset(62% 0% 4% 0%)", 180], [0, "inset(0% 0% 0% 0%)", 0]];
    tl.push(`tl.set("${sel}", { autoAlpha: 0 }, 0);`);
    steps.forEach(([x, clip, hue], i) => tl.push(`tl.set("${sel}", { autoAlpha: 1, x: ${x}, clipPath: "${clip}", filter: "hue-rotate(${hue}deg) saturate(${hue ? 2.2 : 1})" }, ${r3(t0 + i * 0.035)});`));
  }
}
function transOut(ctx, sel, kind, t1) {
  const { tl, r3 } = ctx;
  if (kind === "blur") tl.push(`tl.to("${sel}", { autoAlpha: 0, filter: "blur(28px)", duration: 0.18, ease: "power2.in" }, ${r3(t1 - 0.18)});`);
}

// scenes ---------------------------------------------------------------------
export function buildScene(b, id, t0, t1, ctx) {
  const { tl, E, r3, esc, addSfx, brand, userAsset, words } = ctx;
  const sid = `${id}-sc`;
  let body = "";
  const bg = b.bg === "accent" ? `linear-gradient(135deg, ${brand.accentDark} 0%, ${brand.accent} 55%, ${brand.accentDark} 100%)` : (b.bg || "#fff");
  const inKind = b.in ?? "blur", outKind = b.out ?? "blur";
  let customBg = null;

  if (b.kind === "card") {
    const lines = (b.lines || []).map((l, i) => {
      const at = E(l.at, "card line");
      tl.push(`ft("#${id}-l${i}", { autoAlpha: 0, y: 20, filter: "blur(8px)" }, { autoAlpha: 1, y: 0, filter: "blur(0px)", duration: 0.3, ease: "power3.out" }, ${at});`);
      return `<div id="${id}-l${i}" class="sc-line" style="font-size:${l.size ?? 96}px;color:${l.color ?? brand.accentDark}">${esc(l.text)}</div>`;
    }).join("");
    let pill = "", extra = "";
    if (b.pill) {
      const pa = E(b.pill.at, "card pill");
      pill = `<div id="${id}-p" class="sc-pill" style="font-size:${b.pill.size ?? 92}px;margin-top:${b.pill.gap ?? 18}px">${esc(b.pill.text)}</div>`;
      tl.push(`ft("#${id}-p", { autoAlpha: 0, scale: 0.5, rotation: -16 }, { autoAlpha: 1, scale: 1, rotation: -6, duration: 0.34, ease: "back.out(1.7)" }, ${pa});`);
      addSfx(pa, "pop", "card pill");
    }
    if (b.cursor && b.pill) {
      const ca = E(b.cursor.clickAt, "cursor click");
      const cx = 540 + (b.cursor.dx ?? 40), cy = (b.y ?? 860) + (b.cursor.dy ?? 150);
      extra = `<div id="${id}-ring" class="sc-ring" style="left:${cx - 120}px;top:${cy - 120}px;width:240px;height:240px"></div><div id="${id}-cur" class="sc-cursor" style="left:${cx - 20}px;top:${cy - 10}px">${CURSOR_SVG}</div>`;
      tl.push(`ft("#${id}-cur", { autoAlpha: 0, x: 280, y: 420, rotation: 14 }, { autoAlpha: 1, x: 0, y: 0, rotation: 0, duration: 0.55, ease: "power3.out" }, ${r3(ca - 0.6)});`);
      tl.push(`tl.to("#${id}-cur", { scale: 0.82, duration: 0.07, yoyo: true, repeat: 1, ease: "power1.inOut" }, ${ca});`);
      tl.push(`tl.to("#${id}-p", { scale: 0.93, duration: 0.07, yoyo: true, repeat: 1, ease: "power1.inOut" }, ${ca});`);
      tl.push(`ft("#${id}-ring", { autoAlpha: 0.9, scale: 0.35 }, { autoAlpha: 0, scale: 1.25, duration: 0.5, ease: "power2.out" }, ${ca});`);
      addSfx(ca, "click-1", "cursor click", { db: 4 });
    }
    body = `<div class="col" style="top:${b.y ?? 860}px">${lines}${pill}</div>${extra}`;
  }

  else if (b.kind === "stats") {
    const CY = b.centerY ?? 930, GAP = b.gap ?? 440, ROWX = 250, HERO_S = 1, ROW_S = 0.42;
    const rowY = (k, j) => CY + (j - (k - 1) / 2) * GAP;
    const n = b.badges.length;
    body = b.badges.map((bd, i) => {
      const at = E(bd.at, "badge");
      const heroY = i === 0 ? CY - 330 : rowY(i + 1, i) + 60;
      tl.push(`tl.set("#${id}-b${i}", { x: 540, y: ${heroY}, scale: ${HERO_S} }, 0);`);
      tl.push(`ft("#${id}-b${i}", { autoAlpha: 0, scale: 0.2, filter: "blur(12px)" }, { autoAlpha: 1, scale: ${HERO_S}, filter: "blur(0px)", duration: 0.45, ease: "back.out(1.6)" }, ${at});`);
      addSfx(at, "whoosh", "badge in");
      let lab = "";
      if (bd.label) {
        const la = E(bd.labelAt ?? bd.at, "badge label");
        // this badge and every row above it move into the k = i+1 row layout
        for (let j = 0; j <= i; j++) tl.push(`tl.to("#${id}-b${j}", { x: ${ROWX}, y: ${rowY(i + 1, j)}, scale: ${ROW_S}, duration: 0.55, ease: "power3.inOut" }, ${r3(la - 0.35)});`);
        for (let j = 0; j < i; j++) tl.push(`tl.to("#${id}-lab${j}", { y: ${rowY(i + 1, j) - 34}, duration: 0.55, ease: "power3.inOut" }, ${r3(la - 0.35)});`);
        const parts = bd.label.split(/(\*\*[^*]+\*\*)/).filter(Boolean).flatMap((p) => p.startsWith("**") ? p.slice(2, -2).split(" ").map((w) => `<span><b>${esc(w)}</b></span>`) : p.trim().split(/\s+/).filter(Boolean).map((w) => `<span>${esc(w)}</span>`));
        lab = `<div id="${id}-lab${i}" class="badge-label">${parts.join("")}</div>`;
        tl.push(`tl.set("#${id}-lab${i}", { x: ${ROWX + 110}, y: ${rowY(i + 1, i) - 34} }, 0);`);
        tl.push(`ft("#${id}-lab${i} span", { autoAlpha: 0, x: -14, filter: "blur(6px)" }, { autoAlpha: 1, x: 0, filter: "blur(0px)", duration: 0.28, ease: "power3.out", stagger: 0.07 }, ${r3(la + 0.1)});`);
      }
      return `<div id="${id}-b${i}" class="badge"><div class="v">${esc(bd.value)}</div>${bd.sub ? `<div class="s">${esc(bd.sub)}</div>` : ""}</div>${lab}`;
    }).join("");
    if (n && b.drift !== false) tl.push(`ft("#${sid}", { backgroundPosition: "0% 0%" }, { backgroundPosition: "100% 100%", duration: ${r3(t1 - t0)}, ease: "none" }, ${t0});`);
  }

  else if (b.kind === "fly3d") {
    const items = b.items.map((it, i) => ({ ...it, i, at: E(it.at, "fly3d item") }));
    body = `<div class="fly-stage">${items.map((it) => `<div id="${id}-f${it.i}" class="fly-item"><div class="t" style="font-size:${it.size ?? 120}px">${esc(it.text)}</div>${it.sub ? `<div class="u" style="font-size:${Math.round((it.size ?? 120) * 0.3)}px">${esc(it.sub)}</div>` : ""}</div>`).join("")}</div>`;
    const cam = b.cam ?? { from: 0, to: 900 }, focus = b.focus ?? 0;
    const data = JSON.stringify(items.map((it) => ({ id: `${id}-f${it.i}`, x: it.x ?? 0, y: it.y ?? 0, z: it.z ?? 0, at: it.at })));
    // one painter: every item's transform, blur, opacity and grey level is a
    // pure function of (camera z, timeline time), so any frame can be sought
    tl.push(`(() => { const items = ${data}; const els = items.map((o) => document.getElementById(o.id)); const P = { z: ${cam.from} };
    const paint = () => { const t = tl.time(); items.forEach((o, k) => { const el = els[k]; const z = o.z + P.z; const d = Math.abs(z - ${focus});
      const appear = Math.min(1, Math.max(0, (t - o.at) / 0.3)); const past = Math.min(1, Math.max(0, (z - 420) / 160));
      el.style.transform = "translate(-50%,-50%) translate3d(" + o.x + "px," + o.y + "px," + z + "px)";
      el.style.filter = "blur(" + Math.min(14, d / 55).toFixed(2) + "px)"; el.style.opacity = (appear * (1 - past)).toFixed(3);
      const g = Math.round(255 - Math.min(110, d / 5)); el.style.color = "rgb(" + g + "," + g + "," + g + ")"; }); };
    tl.fromTo(P, { z: ${cam.from} }, { z: ${cam.to}, duration: ${r3(t1 - t0)}, ease: "${b.ease ?? "sine.inOut"}", onUpdate: paint, immediateRender: false }, ${t0}); })();`);
    addSfx(t0, "riser-1", "fly3d riser", { db: -2 });
    for (const it of items.slice(1)) addSfx(it.at, "whoosh", "fly3d word", { db: -6 });
  }

  else if (b.kind === "image") {
    const src = userAsset(b.src);
    const [z0, z1] = b.zoom ?? [1.0, 1.12];
    body = `<img id="${id}-img" class="img-fill" src="${src}" style="${b.grade ? `filter:${b.grade};` : ""}" />`;
    tl.push(`ft("#${id}-img", { scale: ${z0} }, { scale: ${z1}, duration: ${r3(t1 - t0)}, ease: "none" }, ${t0});`);
  }

  else if (b.kind === "sentence") {
    // align the scene's line words to the spoken words inside [t0, t1]
    const spoken = words.filter((w) => w.start >= t0 - 0.05 && w.start < t1);
    let si = 0;
    const lines = (b.lines || []).map((line, li) => `<div class="sent-line">${line.split(/\s+/).map((w, wi) => {
      let at = null;
      for (let k = si; k < spoken.length; k++) if (norm(spoken[k].word) === norm(w)) { at = spoken[k].start; si = k + 1; break; }
      if (at === null) at = t0 + 0.15 * (li * 4 + wi);
      const onAccent = b.bg === "accent";
      tl.push(`ft("#${id}-s${li}-${wi}", { autoAlpha: 0, filter: "blur(6px)", color: "${onAccent ? "rgba(255,255,255,0.5)" : "#c9c9c9"}" }, { autoAlpha: 1, filter: "blur(0px)", color: "${onAccent ? "#fff" : brand.ink}", duration: 0.26, ease: "power2.out" }, ${r3(at - 0.02)});`);
      addSfx(at, "tick-1", "type tick", { db: -4 });
      return `<span id="${id}-s${li}-${wi}">${esc(w)}</span>`;
    }).join("")}</div>`).join("");
    let hero = "", sub = "";
    if (b.hero) {
      const ha = E(b.hero.at, "hero");
      const heroColor = b.hero.color ?? (b.bg === "accent" ? "#fff" : null); // accent on accent is invisible
      hero = `<div id="${id}-hero" class="sent-hero" style="${b.hero.size ? `font-size:${b.hero.size}px;letter-spacing:${-Math.round(b.hero.size / 28)}px;` : ""}${heroColor ? `color:${heroColor};` : ""}">${esc(b.hero.text)}</div>`;
      tl.push(`tl.to("#${id}-lines", { y: -330, scale: 0.72, duration: 0.5, ease: "power3.inOut" }, ${r3(ha - 0.3)});`);
      tl.push(`ft("#${id}-hero", { autoAlpha: 0, scale: 0.55, filter: "blur(14px)" }, { autoAlpha: 1, scale: 1, filter: "blur(0px)", duration: 0.42, ease: "expo.out" }, ${ha});`);
      addSfx(ha, "impact", "hero word");
    }
    if (b.sub) {
      const sa = E(b.sub.at, "sub");
      const parts = b.sub.text.split(/\s+/).map((w) => (b.sub.cross && norm(w) === norm(b.sub.cross)) ? `<span class="xw">${esc(w)}${X_SVG(brand.accent, `${id}-x`)}</span>` : esc(w)).join(" ");
      sub = `<div id="${id}-sub" class="sent-sub">${parts}</div>`;
      tl.push(`ft("#${id}-sub", { autoAlpha: 0, y: 16 }, { autoAlpha: 1, y: 0, duration: 0.3, ease: "power3.out" }, ${sa});`);
      if (b.sub.cross) {
        const xa = E(b.sub.crossAt ?? b.sub.at, "cross");
        tl.push(`ft("#${id}-xa", { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.16, ease: "power2.out" }, ${xa});`);
        tl.push(`ft("#${id}-xb", { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.16, ease: "power2.out" }, ${r3(xa + 0.14)});`);
        addSfx(xa, "whoosh", "cross out", { db: -4 });
      }
    }
    body = `<div id="${id}-lines" class="sent-lines">${lines}</div>${hero}${sub}`;
  }

  else if (b.kind === "ui") {
    // a dark app/terminal window: the prompt types in, result lines tick in
    const ta = E(b.prompt?.at ?? b.at, "ui prompt");
    const text = b.prompt?.text ?? "";
    const cps = b.prompt?.cps ?? 28;
    const typeEnd = ta + text.length / cps;
    const chars = [...text].map((c, i) => `<span id="${id}-c${i}" style="opacity:0">${esc(c)}</span>`).join("");
    const lines = (b.lines || []).map((l, i) => {
      const at = E(l.at, "ui line");
      tl.push(`ft("#${id}-u${i}", { autoAlpha: 0, x: -30 }, { autoAlpha: 1, x: 0, duration: 0.3, ease: "power3.out" }, ${at});`);
      addSfx(at, "ding-1", "ui line", { db: -8 });
      return `<div id="${id}-u${i}" class="ui-line"><span class="ck">✓</span><span>${esc(l.text)}</span></div>`;
    }).join("");
    // typed characters: one set per char at its time; caret blinks in steps
    [...text].forEach((_, i) => tl.push(`tl.set("#${id}-c${i}", { opacity: 1 }, ${r3(ta + i / cps)});`));
    const blinkEnd = t1;
    for (let t = ta, k = 0; t < blinkEnd; t += 0.45, k++) tl.push(`tl.set("#${id}-caret", { opacity: ${k % 2 ? 0 : 1} }, ${r3(t)});`);
    if (text) addSfx(ta, "typing-1", "ui typing", { db: -6 });
    const y = b.y ?? 620;
    body = `${b.label ? `<div class="ui-label" style="top:${y - 90}px">${esc(b.label)}</div>` : ""}<div id="${id}-win" class="ui-win" style="top:${y}px"><div class="ui-bar"><i></i><i></i><i></i><b>${esc(b.title || "")}</b></div><div class="ui-body"><div class="ui-prompt"><span class="pr">›</span>${chars}<span id="${id}-caret" class="ui-caret"></span></div>${lines}</div></div>`;
    tl.push(`ft("#${id}-win", { autoAlpha: 0, y: 60, scale: 0.94 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.45, ease: "expo.out" }, ${t0});`);
  }

  else if (b.kind === "device") {
    // a phone frame rising into the scene: an image, or a mini chat of lines
    const src = b.src ? userAsset(b.src) : null;
    const screen = src ? `<img src="${src}" />` : `<div class="scr">${(b.lines || []).map((l, i) => {
      const at = E(l.at, "device line");
      tl.push(`ft("#${id}-m${i}", { autoAlpha: 0, y: 24, scale: 0.92 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.3, ease: "back.out(1.6)" }, ${at});`);
      addSfx(at, "pop", "device line", { db: -4 });
      return `<div id="${id}-m${i}" class="${l.me ? "me" : ""}">${esc(l.text)}</div>`;
    }).join("")}</div>`;
    const y = b.y ?? 470;
    body = `${b.label ? `<div class="ui-label" style="top:${y - 100}px">${esc(b.label)}</div>` : ""}<div id="${id}-dev" class="dev" style="top:${y}px">${screen}</div>`;
    tl.push(`ft("#${id}-dev", { autoAlpha: 0, y: 380, rotation: 8, scale: 0.9 }, { autoAlpha: 1, y: 0, rotation: -3, scale: 1, duration: 0.6, ease: "expo.out" }, ${t0});`);
    tl.push(`tl.to("#${id}-dev", { rotation: 2, y: -18, duration: ${r3(Math.max(0.3, t1 - t0 - 0.6))}, ease: "sine.inOut" }, ${r3(t0 + 0.6)});`);
    addSfx(t0, "whoosh", "device in");
  }

  else if (b.kind === "kinetic") {
    // words land one by one as they are spoken; a camera glides from word to
    // word, then pulls back to show the whole phrase. *word* = accent keyword,
    // _word_ = light italic filler. Optional pip: the speaker shrinks into a circle.
    const spoken = words.filter((w) => w.start >= t0 - 0.05 && w.start < t1);
    let si = 0;
    const toks = b.text.split(/\s+/).map((raw, i) => {
      const em = /^\*.*\*[.,!?]?$/.test(raw), it = /^_.*_[.,!?]?$/.test(raw);
      const txt = raw.replace(/^[*_]|[*_](?=[.,!?]?$)/g, "");
      let at = null;
      for (let k = si; k < spoken.length; k++) if (norm(spoken[k].word) === norm(txt)) { at = spoken[k].start; si = k + 1; break; }
      if (at === null) at = t0 + 0.3 * i;
      return { txt, em, it, at, i };
    });
    const size = b.size ?? 118;
    const kbg = b.bg ?? brand.kineticBg ?? "#FFE14D";
    const spans = toks.map((k) => `<span id="${id}-k${k.i}" class="${k.em ? "em" : ""}${k.it ? " it" : ""}" style="font-size:${k.em ? Math.round(size * 1.45) : size}px">${esc(k.txt)}</span>`).join(" ");
    body = `<div id="${id}-world" class="kin-world"><div id="${id}-txt" class="kin-text" style="color:${b.ink ?? brand.ink}">${spans}</div></div>`;
    const data = JSON.stringify(toks.map((k) => ({ id: `${id}-k${k.i}`, at: k.at })));
    const S = b.zoom ?? 2.1, outAt = r3(t1 - (b.pullback ?? 1.0));
    tl.push(`(() => { const ks = ${data}; const els = ks.map((k) => document.getElementById(k.id)); const world = document.getElementById("${id}-world"); const P = { u: 0 };
    const ease = (x) => x < 0 ? 0 : x > 1 ? 1 : 1 - Math.pow(1 - x, 3);
    const paint = () => { const t = tl.time(); let cur = 0; ks.forEach((k, i) => { if (t >= k.at - 0.02) cur = i; const a = ease((t - k.at + 0.02) / 0.22); els[i].style.opacity = a.toFixed(3); els[i].style.transform = "translateY(" + ((1 - a) * 40).toFixed(1) + "px) scale(" + (0.8 + 0.2 * a).toFixed(3) + ")"; });
      const c = (el) => [el.offsetLeft + el.offsetWidth / 2, el.offsetTop + el.offsetHeight / 2];
      const prevI = Math.max(0, cur - 1); const m = ease((t - ks[cur].at) / 0.38); const [x0, y0] = c(els[prevI]); const [x1, y1] = c(els[cur]);
      let cx = x0 + (x1 - x0) * m, cy = y0 + (y1 - y0) * m, s = ${S};
      const txt = document.getElementById("${id}-txt"); const po = ease((t - ${outAt}) / 0.7);
      if (po > 0) { cx += (txt.offsetWidth / 2 - cx) * po; cy += (txt.offsetHeight / 2 - cy) * po; s += (Math.min(1, 900 / txt.offsetWidth) - s) * po; }
      world.style.transform = "translate(" + (540 - s * cx).toFixed(1) + "px," + (${b.cy ?? 860} - s * cy).toFixed(1) + "px) scale(" + s.toFixed(3) + ")"; };
    tl.fromTo(P, { u: 0 }, { u: 1, duration: ${r3(t1 - t0)}, ease: "none", onUpdate: paint, immediateRender: false }, ${t0}); })();`);
    for (const k of toks.slice(1)) if (k.em) addSfx(k.at, "whoosh", "kinetic keyword", { db: -6 });
    if (b.pip) {
      // the speaker plate shrinks into a round window, above the type
      const fx = 540, fy = ctx.faceY ?? 700, R = 560, sc = 0.34, tx = b.pipX ?? 820, ty = b.pipY ?? 1330;
      tl.push(`tl.set("#pip", { zIndex: 7 }, ${t0});`);
      tl.push(`ft("#pip", { x: 0, y: 0, scale: 1, clipPath: "circle(1400px at ${fx}px ${fy}px)" }, { x: ${tx - fx}, y: ${ty - fy}, scale: ${sc}, clipPath: "circle(${R}px at ${fx}px ${fy}px)", duration: 0.5, ease: "power3.inOut" }, ${t0});`);
      tl.push(`tl.to("#pip", { x: 0, y: 0, scale: 1, clipPath: "circle(1400px at ${fx}px ${fy}px)", duration: 0.45, ease: "power3.inOut" }, ${r3(t1 - 0.45)});`);
      tl.push(`tl.set("#pip", { zIndex: 1 }, ${t1});`);
    }
    customBg = kbg;
  }

  else throw new Error(`unknown scene kind '${b.kind}'`);

  transIn(ctx, `#${sid}`, inKind, t0);
  if (inKind === "expand" || inKind === "wipe") addSfx(t0, "whoosh", `scene in (${inKind})`);
  transOut(ctx, `#${sid}`, outKind, t1);
  return `<div id="${sid}" class="scene" style="background:${customBg ?? bg};background-size:220% 220%">${body}</div>`;
}

// editorial captions ------------------------------------------------------------
// Lines of <= group words (or up to punctuation); a block holds two lines. The
// word being spoken resolves out of blur in bold white; when the next line
// starts, the previous one relaxes to a light weight. Tag phrases become a
// tilted accent pill on their own line; highlight words get an accent box wipe.
export function buildEditorialCaptions(words, cap, ctx, hidden) {
  const { tl, r3, esc, brand } = ctx;
  const tags = (cap.tags || []).map((p) => p.split(/\s+/).map(norm));
  const hl = new Set((cap.highlight || []).map(norm));
  const lines = [];
  let cur = null;
  const push = (l) => { if (l && l.words.length) lines.push(l); };
  for (let i = 0; i < words.length; i++) {
    const tag = tags.find((tw) => tw.every((x, k) => words[i + k] && norm(words[i + k].word) === x));
    if (tag) { push(cur); cur = null; lines.push({ tag: true, words: words.slice(i, i + tag.length) }); i += tag.length - 1; continue; }
    const w = words[i];
    if (!cur || cur.words.length >= (cap.group ?? 3) || (w.start - cur.words.at(-1).end > 0.6)) { push(cur); cur = { words: [] }; }
    cur.words.push(w);
    if (/[.?!,]$/.test(w.word)) { push(cur); cur = null; }
  }
  push(cur);
  // blocks: a tag line + the next line, or two plain lines
  const blocks = [];
  for (let i = 0; i < lines.length;) {
    // a tag pill heads a block of up to two lines; plain blocks hold two lines
    let take = 1;
    while (take < (lines[i].tag ? 3 : 2) && lines[i + take] && !lines[i + take].tag) take++;
    blocks.push(lines.slice(i, i + take));
    i += take;
  }
  const html = blocks.map((bl, bi) => {
    const s = bl[0].words[0].start - 0.05;
    const nextS = bi + 1 < blocks.length ? blocks[bi + 1][0].words[0].start - 0.05 : ctx.SPEECH;
    const e = Math.min(bl.at(-1).words.at(-1).end + 0.5, nextS);
    const h = bl.reduce((n, ln) => n + (ln.tag ? brand.capSize * 1.35 : brand.capSize * 1.1), 0);
    const pl = ctx.placeCaption ? ctx.placeCaption(Math.max(0, s), e, h) : { y: cap.y ?? 1150, mode: "fixed" };
    const y = pl.y;
    const inner = bl.map((ln, li) => {
      const lid = `eb${bi}l${li}`;
      if (ln.tag) {
        const t = ln.words[0].start - 0.04;
        tl.push(`ft("#${lid}", { autoAlpha: 0, scale: 0.5, rotation: -16 }, { autoAlpha: 1, scale: 1, rotation: -6, duration: 0.3, ease: "back.out(1.7)" }, ${r3(t)});`);
        return `<span class="eline"><span id="${lid}" class="etag">${esc(ln.words.map((w) => w.word.replace(/[.,!?]$/, "")).join(" "))}</span></span>`;
      }
      if (li > 0 && !bl[li - 1].tag && bl[li - 1].words) tl.push(`tl.to("#eb${bi}l${li - 1} .ew:not(.eser)", { fontWeight: 300, color: "rgba(255,255,255,0.86)", duration: 0.2, ease: "power2.out" }, ${r3(ln.words[0].start - 0.03)});`);
      return `<span id="${lid}" class="eline">${ln.words.map((w, wi) => {
        const wid = `${lid}w${wi}`;
        tl.push(`ft("#${wid}", { autoAlpha: 0, y: 10, filter: "blur(10px)" }, { autoAlpha: 1, y: 0, filter: "blur(0px)", duration: 0.26, ease: "power3.out" }, ${r3(w.start - 0.03)});`);
        const txt = cap.upper ? w.word.toUpperCase() : cap.lowercase === false ? w.word : w.word.toLowerCase();
        if (hl.has(norm(w.word)) && cap.keywordStyle === "serif") return `<span id="${wid}" class="ew eser">${esc(txt)}</span>`;
        if (hl.has(norm(w.word))) {
          tl.push(`ft("#${wid}b", { scaleX: 0 }, { scaleX: 1, duration: 0.28, ease: "power3.out" }, ${r3(w.start)});`);
          return `<span class="ehl"><i id="${wid}b"></i><span id="${wid}" class="ew">${esc(txt)}</span></span>`;
        }
        return `<span id="${wid}" class="ew">${esc(txt)}</span>`;
      }).join("")}</span>`;
    }).join("");
    return `<div id="eb${bi}" class="eblock clip${pl.mode === "lower-face" ? " ebacked" : ""}" style="top:${y}px${pl.scale && pl.scale < 1 ? `;transform:scale(${pl.scale});transform-origin:50% 0` : ""}" data-start="${r3(Math.max(0, s))}" data-duration="${r3(Math.max(0.1, e - s))}" data-track-index="5">${inner}</div>`;
  }).join("\n      ");
  // hide the captions under full-screen scenes that don't want them
  tl.push(`tl.set("#ecaps", { autoAlpha: 1 }, 0);`);
  // merge overlapping windows first, or one window's "show" fires inside the next
  const merged = [];
  for (const [a, b] of [...hidden].sort((x, y) => x[0] - y[0])) {
    if (merged.length && a <= merged.at(-1)[1] + 0.05) merged.at(-1)[1] = Math.max(merged.at(-1)[1], b);
    else merged.push([a, b]);
  }
  for (const [a, b] of merged) { tl.push(`tl.to("#ecaps", { autoAlpha: 0, duration: 0.08 }, ${r3(a)});`); tl.push(`tl.to("#ecaps", { autoAlpha: 1, duration: 0.12 }, ${r3(b - 0.05)});`); }
  return { html: `<div id="ecaps">${html}</div>`, count: blocks.length };
}

// music bed -------------------------------------------------------------------
// Level = voice (-16 LUFS after prep.sh) + db, measured against the track's own
// integrated loudness, with fades. Returns an <audio> tag.
export function buildMusic(m, ctx, execFileSync, path, fs) {
  const { r3, proj, LIB, TOTAL } = ctx;
  let src = m.src;
  const manifestPath = path.join(LIB, "music", "manifest.json");
  if (m.id) {
    const man = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    if (!man[m.id]) throw new Error(`music '${m.id}' not in library/music/manifest.json`);
    fs.mkdirSync(path.join(proj, "assets", "music"), { recursive: true });
    fs.copyFileSync(path.join(LIB, "music", man[m.id].file), path.join(proj, "assets", "music", man[m.id].file));
    src = `assets/music/${man[m.id].file}`;
  }
  const err = spawnSync("ffmpeg", ["-hide_banner", "-nostats", "-i", path.resolve(proj, src), "-t", "60", "-af", "ebur128", "-f", "null", "-"], { encoding: "utf8" }).stderr;
  const I = parseFloat((err.match(/I:\s+(-?[\d.]+) LUFS/g) || ["I: -14"]).at(-1).split(/\s+/).at(-2));
  const target = -16 + (m.db ?? -20);
  const vol = r3(Math.min(3.98, Math.pow(10, (target - I) / 20)));
  const fi = m.fadeIn ?? 0.6, fo = m.fadeOut ?? 1.2;
  const lane = JSON.stringify({ version: 1, lanes: [{ target: "volume", points: [{ t: 0, v: 0 }, { t: fi, v: vol }, { t: r3(TOTAL - fo), v: vol }, { t: r3(TOTAL), v: 0 }] }] });
  return { html: `<audio id="music-bed" src="${src}" data-start="0" data-duration="${TOTAL}" data-media-start="${m.start ?? 0}" data-track-index="20" data-automation='${lane}'></audio>`, vol, I };
}
