/* Wuxia character portraits in the soft, semi-realistic painted style of Jin Yong game art:
 * sculpted faces with gradient shading, long almond eyes, flowing hair, layered hanfu, and a misty
 * ink-wash landscape that fades into paper.
 *
 *   renderPortrait(appearance, seed, { bg: true })  ->  SVG markup (viewBox 0 0 240 300)
 *
 * With bg:false only the figure and its aura are drawn on a transparent ground, so busts can stand
 * over a scene. Each layer is chosen by one field of `appearance` (APPEARANCE in app/game.py);
 * unknown values fall back to a default, so a portrait always draws. `seed` (the character's name)
 * only scatters particles, so the same character always looks the same. */
(function () {
  "use strict";

  const LINE = "#3a2418";                         // warm brown line work, never pure black
  const n = v => Math.round(v * 10) / 10;
  const hash = s => { let h = 2166136261; for (const c of String(s)) { h ^= c.codePointAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
  const rng = seed => { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; };
  // flip an absolute path ("x y" pairs only) about the centre line x=120
  const mirror = d => d.replace(/(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)/g, (m, x, y) => `${n(240 - x)} ${y}`);
  const both = d => [d, mirror(d)];
  const pick = (map, key, fallback) => map[key] || map[fallback];
  const strands = (list, col, w, op) => list.map(d => `<path d="${d}" stroke="${col}" stroke-width="${w}" fill="none" stroke-linecap="round" opacity="${op}"/>`).join("");

  /* ---------- palettes: [main, dark, light] ---------- */
  const OUTFIT = {
    ink: ["#4a4d60", "#262836", "#8d90a6"], crimson: ["#c14d58", "#852a35", "#ee9099"], jade: ["#46a088", "#29634f", "#92d6bd"],
    azure: ["#4873ba", "#2b4880", "#92b3e6"], violet: ["#8661ab", "#53367a", "#bba0da"], gold: ["#dcae44", "#98701a", "#f5d57e"],
    white: ["#f2eee3", "#c3bba6", "#ffffff"], ash: ["#908a7a", "#5b5547", "#c2bcad"], pink: ["#f0a0b4", "#c5607c", "#fbd3de"],
  };
  const HAIR = {
    black: ["#2d2733", "#120f18", "#76708a"], brown: ["#704c38", "#3f291b", "#b0805f"], silver: ["#d6d8e0", "#979bad", "#ffffff"],
    white: ["#f1f0f0", "#aaa9b2", "#ffffff"], red: ["#aa4630", "#68231a", "#e8896a"], blue: ["#364b82", "#1b274b", "#7b97d8"], green: ["#3e6c54", "#213d2f", "#80b89a"],
  };
  const SKIN = { fair: ["#fdeee0", "#eec3a8", "#f8dccb"], warm: ["#f5d8b8", "#d6a47c", "#ebc39e"], tan: ["#e0b488", "#b5815a", "#d09f70"], deep: ["#b8825a", "#82552f", "#a37048"] };
  const EYE = { black: ["#1b1620", "#5c5668"], brown: ["#4a2a18", "#b9784a"], amber: ["#7c4a0e", "#f0b84e"], jade: ["#16503f", "#6fd8b0"], blue: ["#1a3470", "#78b2f4"], violet: ["#44206f", "#c28cf2"], red: ["#6e1424", "#f0687a"] };
  const SCENES = {
    mountains: { sky: ["#f8f4ea", "#e6eee9"], wash: ["#cde0d6", "#f3d6d1"], ink: "#5f7270" },
    bamboo: { sky: ["#f5f7eb", "#deead8"], wash: ["#bddcc3", "#e7f0ca"], ink: "#587a66" },
    lanterns: { sky: ["#d8d2e6", "#f1cdc3"], wash: ["#b5a7d6", "#f5baa8"], ink: "#4b476c" },
    snow: { sky: ["#f3f7fb", "#dde8f1"], wash: ["#d1e3f1", "#eef2f6"], ink: "#76889a" },
    river: { sky: ["#fbf4e3", "#e5efe6"], wash: ["#d4e6e4", "#f7ddc3"], ink: "#667f84" },
  };

  /* ---------- definitions: gradients and soft-focus filters ---------- */
  function defs(P) {
    const g = (id, a, b, x2 = 1, y2 = 1) => `<linearGradient id="${id}" x1="0" y1="0" x2="${x2}" y2="${y2}"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`;
    const blur = (id, sd) => `<filter id="${id}" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="${sd}"/></filter>`;
    return `<defs>${g("skin", P.skin[0], P.skin[2], .6, 1)}${g("hair", P.hair[0], P.hair[1], .5, 1)}${g("robe", P.out[0], P.out[1], .3, 1)}${g("trim", P.acc[2], P.acc[0], 0, 1)}` +
      `${blur("b1", 1.3)}${blur("b2", 2.8)}${blur("b4", 6)}` +
      `<radialGradient id="glow"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>` +
      `<radialGradient id="lg"><stop offset="0" stop-color="#ffb070" stop-opacity=".6"/><stop offset="1" stop-color="#ffb070" stop-opacity="0"/></radialGradient>` +
      `<linearGradient id="fire" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#f6b24a"/><stop offset=".6" stop-color="#e5683a"/><stop offset="1" stop-color="#c0392b" stop-opacity=".2"/></linearGradient></defs>`;
  }

  /* ---------- background: a misty ink-wash landscape on paper ---------- */
  function ridge(R, id, base, amp, color, op, step, bottomColor) {
    let d = `M-10 300L-10 ${n(base)}`, px = -10, py = base;
    for (let x = step - 10; x <= 250 + step; x += step) {
      const y = base - R() * amp, mx = (px + x) / 2;
      d += `Q${n(mx)} ${n(Math.min(py, y) - amp * .35)} ${n(x)} ${n(y)}`; px = x; py = y;
    }
    return `<linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity="${op}"/><stop offset=".55" stop-color="${color}" stop-opacity="${n(op * .35)}"/><stop offset="1" stop-color="${bottomColor}" stop-opacity="0"/></linearGradient>` +
      `<path d="${d}L${250 + step} 300Z" fill="url(#${id})"/>`;
  }
  const mist = (cx, cy, rx, ry, op) => `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="#fffdf6" opacity="${op}" filter="url(#b4)"/>`;
  const pineAt = (x, y, k, col, op) => {
    let s = `<g fill="${col}" opacity="${op}"><rect x="${n(x - 1.6 * k)}" y="${n(y - 40 * k)}" width="${n(3.2 * k)}" height="${n(42 * k)}"/>`;
    for (let i = 0; i < 4; i++) { const yy = y - (12 + i * 14) * k, w = (22 - i * 4) * k; s += `<path d="M${n(x - w)} ${n(yy)}Q${x} ${n(yy - 14 * k)} ${n(x + w)} ${n(yy)}Q${x} ${n(yy - 4 * k)} ${n(x - w)} ${n(yy)}Z"/>`; }
    return s + "</g>";
  };
  const stalk = (x, w, col, op) => {
    let s = `<g opacity="${op}"><rect x="${x}" y="-4" width="${w}" height="310" fill="${col}"/>`;
    for (let y = 22 + (x * 7) % 21; y < 300; y += 46) s += `<rect x="${x - .8}" y="${y}" width="${n(w + 1.6)}" height="2.6" fill="#2f5240" opacity=".7"/>`;
    return s + `<rect x="${n(x + w * .2)}" y="-4" width="${n(w * .22)}" height="310" fill="#fff" opacity=".3"/></g>`;
  };
  const leafAt = (x, y, rot, len, fill, op) => `<path d="M0 0Q${n(len / 2)} ${n(-len * .24)} ${n(len)} 0Q${n(len / 2)} ${n(len * .24)} 0 0Z" transform="translate(${n(x)} ${n(y)}) rotate(${n(rot)})" fill="${fill}" opacity="${op}"/>`;
  const lantern = (x, y, r) =>
    `<circle cx="${x}" cy="${y}" r="${r * 3}" fill="url(#lg)"/><path d="M${x} ${n(y - r * 1.3)}V${n(y - r * 2.4)}" stroke="#3a2418" stroke-width="1"/>` +
    `<ellipse cx="${x}" cy="${y}" rx="${r}" ry="${n(r * 1.2)}" fill="#d9503a"/><ellipse cx="${n(x - r * .3)}" cy="${n(y - r * .3)}" rx="${n(r * .35)}" ry="${n(r * .5)}" fill="#ffb59a" opacity=".6"/>` +
    `<rect x="${n(x - r * .5)}" y="${n(y - r * 1.35)}" width="${n(r)}" height="2.4" fill="#5a3a22"/><rect x="${n(x - r * .5)}" y="${n(y + r * 1.15)}" width="${n(r)}" height="2.4" fill="#5a3a22"/><path d="M${x} ${n(y + r * 1.4)}V${n(y + r * 2.4)}" stroke="#e1b050" stroke-width="1.4"/>`;

  function background(scene, R) {
    const c = SCENES[scene] || SCENES.mountains;
    let s = `<defs><linearGradient id="bgf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c.sky[0]}"/><stop offset="1" stop-color="${c.sky[1]}"/></linearGradient>` +
      `<filter id="paper" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="3" result="g"/><feColorMatrix in="g" type="matrix" values="0 0 0 0 .45  0 0 0 0 .36  0 0 0 0 .25  .8 0 0 0 -.3"/></filter></defs>`;
    s += `<rect width="240" height="300" fill="url(#bgf)"/>`;
    // watercolour washes
    s += `<ellipse cx="48" cy="96" rx="78" ry="56" fill="${c.wash[0]}" opacity=".55" filter="url(#b4)"/><ellipse cx="196" cy="150" rx="70" ry="62" fill="${c.wash[1]}" opacity=".5" filter="url(#b4)"/><ellipse cx="120" cy="250" rx="110" ry="40" fill="${c.wash[0]}" opacity=".4" filter="url(#b4)"/>`;
    if (scene === "bamboo") {
      s += ridge(R, "r1", 196, 44, c.ink, .26, 34, c.sky[1]) + mist(60, 214, 96, 14, .6);
      s += stalk(64, 5, "#6fa07e", .5) + stalk(172, 6, "#6fa07e", .55);
      [[10, 10, .85], [36, 7, .7], [200, 8, .8], [226, 11, .9]].forEach(([x, w, o]) => { s += stalk(x, w, "#55876a", o); });
      for (let i = 0; i < 12; i++) { const left = i % 2 === 0; s += leafAt(left ? 6 + R() * 56 : 172 + R() * 60, 14 + R() * 150, (R() - .5) * 100 + (left ? 28 : 152), 15 + R() * 15, "#5f9a74", .7); }
    } else if (scene === "lanterns") {
      s += `<circle cx="178" cy="78" r="22" fill="#fff7e6" opacity=".9"/><circle cx="178" cy="78" r="38" fill="#fff7e6" opacity=".25" filter="url(#b2)"/>`;
      s += ridge(R, "r1", 190, 50, c.ink, .34, 36, c.sky[1]) + mist(120, 210, 110, 14, .55) + ridge(R, "r2", 236, 36, "#3a3860", .5, 30, c.sky[1]);
      s += `<path d="M-5 30Q120 70 245 24" fill="none" stroke="#3a2418" stroke-width="1.2"/>`;
      [[20, 44], [66, 57], [120, 61], [176, 53], [222, 36]].forEach(([x, y], i) => { s += lantern(x, y, 8 + (i % 2) * 2); });
    } else if (scene === "snow") {
      s += ridge(R, "r1", 168, 54, c.ink, .3, 38, c.sky[1]) + mist(70, 190, 100, 14, .7) + ridge(R, "r2", 214, 40, "#5d6e80", .4, 30, c.sky[1]);
      s += pineAt(26, 236, 1, "#3d5a56", .8) + pineAt(210, 228, 1.15, "#3d5a56", .8) + pineAt(68, 250, .7, "#4d6a64", .7);
      s += `<path d="M-6 262Q60 242 120 258T250 248V300H-6Z" fill="#fbfdff" opacity=".92"/>`;
      for (let i = 0; i < 50; i++) s += `<circle cx="${n(R() * 240)}" cy="${n(R() * 280)}" r="${n(.7 + R() * 1.8)}" fill="#fff" opacity="${n(.55 + R() * .4)}"/>`;
    } else if (scene === "river") {
      s += `<circle cx="62" cy="104" r="24" fill="#d9503a" opacity=".78"/><circle cx="62" cy="104" r="40" fill="#f6c4a0" opacity=".3" filter="url(#b2)"/>`;
      s += ridge(R, "r1", 194, 40, c.ink, .3, 38, c.sky[1]) + mist(120, 206, 120, 12, .65);
      s += `<rect x="-5" y="208" width="250" height="100" fill="#d7e8e6" opacity=".55"/>`;
      for (let i = 0; i < 10; i++) s += `<path d="M${n(R() * 200 - 10)} ${n(216 + i * 8.5)}q8 -4 16 0t16 0t16 0" stroke="#fff" stroke-width="1.3" fill="none" opacity=".6"/>`;
      s += `<path d="M180 214L218 214L212 222L186 222Z" fill="#4a3a30" opacity=".85"/><path d="M198 212V178L216 210Z" fill="#fbf1dc"/>`;
    } else { // mountains
      s += `<circle cx="168" cy="92" r="26" fill="#d9503a" opacity=".78"/><circle cx="168" cy="92" r="42" fill="#f6c4a0" opacity=".28" filter="url(#b2)"/>`;
      s += `<linearGradient id="spire" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c.ink}" stop-opacity=".55"/><stop offset="1" stop-color="${c.ink}" stop-opacity="0"/></linearGradient>`;
      s += `<path d="M30 230L52 120L60 150L74 78L86 132L96 110L110 230Z" fill="url(#spire)"/><path d="M150 236L172 150L184 170L204 104L214 150L232 236Z" fill="url(#spire)" opacity=".8"/>`;
      s += ridge(R, "r1", 188, 54, c.ink, .32, 40, c.sky[1]) + mist(80, 200, 100, 14, .6) + ridge(R, "r2", 230, 44, "#46555a", .46, 34, c.sky[1]) + mist(176, 238, 90, 12, .5);
      s += pineAt(206, 258, .9, "#34464a", .8);
    }
    for (let i = 0; i < 18; i++) s += `<circle cx="${n(R() * 240)}" cy="${n(180 + R() * 120)}" r="${n(.6 + R() * 1.6)}" fill="#2b2b36" opacity="${n(.1 + R() * .2)}"/>`;
    return s + `<rect width="240" height="300" filter="url(#paper)" opacity=".5"/>`;
  }

  /* ---------- aura: an elemental glow painted behind the figure ---------- */
  const flameTongue = (bx, by, tx, ty, w, fill, op) => {
    const my = (by + ty) / 2;
    return `<path d="M${n(bx - w)} ${n(by)}Q${n((bx + tx) / 2 - w * 1.2)} ${n(my)} ${n(tx)} ${n(ty)}Q${n((bx + tx) / 2 + w * 1.3)} ${n(my + 10)} ${n(bx + w)} ${n(by)}Z" fill="${fill}" opacity="${op}"/>`;
  };
  const sparkle = (x, y, r, fill, op) => `<path d="M${n(x)} ${n(y - r)}L${n(x + r * .26)} ${n(y - r * .26)}L${n(x + r)} ${n(y)}L${n(x + r * .26)} ${n(y + r * .26)}L${n(x)} ${n(y + r)}L${n(x - r * .26)} ${n(y + r * .26)}L${n(x - r)} ${n(y)}L${n(x - r * .26)} ${n(y - r * .26)}Z" fill="${fill}" opacity="${op}"/>`;
  function aura(kind, R) {
    let s = "";
    switch (kind) {
      case "flame":
        s += `<g filter="url(#b1)">`;
        for (let i = 0; i < 11; i++) { const bx = 10 + i * 22 + R() * 8, by = 240 + R() * 40; s += flameTongue(bx, by, bx + (R() - .5) * 46, by - (90 + R() * 110), 13 + R() * 9, "url(#fire)", .78); }
        for (let i = 0; i < 8; i++) { const bx = 30 + i * 26 + R() * 10, by = 256 + R() * 24; s += flameTongue(bx, by, bx + (R() - .5) * 30, by - (50 + R() * 70), 8 + R() * 5, "#ffd96a", .8); }
        s += `</g>`;
        for (let i = 0; i < 18; i++) s += sparkle(R() * 240, 30 + R() * 230, 1.6 + R() * 2.6, "#ffd96a", .85);
        break;
      case "ice":
        s += `<circle cx="120" cy="140" r="86" fill="#dff0f8" opacity=".5" filter="url(#b4)"/>`;
        for (let i = 0; i < 12; i++) {
          const a = (-200 + i * 20) * Math.PI / 180, r0 = 60, r1 = 98 + R() * 44, bx = 120 + Math.cos(a) * r0, by = 150 + Math.sin(a) * r0, tx = 120 + Math.cos(a) * r1, ty = 150 + Math.sin(a) * r1, px = -Math.sin(a) * 9, py = Math.cos(a) * 9;
          s += `<path d="M${n(bx - px)} ${n(by - py)}L${n(tx)} ${n(ty)}L${n(bx + px)} ${n(by + py)}Z" fill="#d6ecf6" opacity=".8" stroke="#8fb6cc" stroke-width=".8"/><path d="M${n(bx)} ${n(by)}L${n(tx)} ${n(ty)}L${n(bx + px)} ${n(by + py)}Z" fill="#fff" opacity=".5"/>`;
        }
        for (let i = 0; i < 16; i++) s += sparkle(R() * 240, R() * 260, 1.8 + R() * 3, "#fff", .95);
        break;
      case "wind":
        for (let i = 0; i < 8; i++) {
          const y = 36 + i * 32 + R() * 10, x = -12 + R() * 40, d = `M${n(x)} ${n(y)}C${n(x + 60)} ${n(y - 24)} ${n(x + 120)} ${n(y + 24)} ${n(x + 190 + R() * 40)} ${n(y - 8)}c14 -6 22 8 10 14`;
          s += `<path d="${d}" stroke="#fff" stroke-width="${n(3 + R() * 3)}" fill="none" stroke-linecap="round" opacity=".7" filter="url(#b1)"/><path d="${d}" stroke="#9db4b0" stroke-width=".8" fill="none" opacity=".45" transform="translate(0 3)"/>`;
        }
        for (let i = 0; i < 10; i++) s += leafAt(R() * 240, R() * 280, R() * 360, 7 + R() * 5, "#bfe0b8", .85);
        break;
      case "petals":
        for (let i = 0; i < 30; i++) {
          const blurry = R() > .65, x = R() * 240, y = R() * 290, rx = 4 + R() * 3.4, rot = R() * 360;
          s += `<ellipse cx="${n(x)}" cy="${n(y)}" rx="${n(rx)}" ry="${n(rx * .56)}" transform="rotate(${n(rot)} ${n(x)} ${n(y)})" fill="${R() > .4 ? "#f4b2c0" : "#fdeaee"}" opacity="${blurry ? .55 : .92}"${blurry ? ' filter="url(#b1)"' : ""}/>`;
        }
        break;
      case "lightning":
        s += `<circle cx="120" cy="120" r="90" fill="#cfd8f8" opacity=".35" filter="url(#b4)"/>`;
        [[30, 0], [210, 10], [120, -10]].forEach(([x, y], k) => {
          let d = `${x},${y}`, px, py; const tx = k === 2 ? 120 : (x < 120 ? 92 : 148), steps = 6;
          for (let i = 1; i <= steps; i++) { px = x + (tx - x) * i / steps + (R() - .5) * 26; py = y + (110 + R() * 40) * i / steps; d += ` ${n(px)},${n(py)}`; }
          s += `<polyline points="${d}" fill="none" stroke="#9cb0ff" stroke-width="9" stroke-linejoin="round" opacity=".5" filter="url(#b2)"/><polyline points="${d}" fill="none" stroke="#fffbe0" stroke-width="2.6" stroke-linejoin="round"/>`;
        });
        break;
      case "moon":
        s += `<circle cx="120" cy="124" r="100" fill="#fff6d8" opacity=".35" filter="url(#b4)"/><circle cx="120" cy="124" r="74" fill="#fffaec" opacity=".75"/><circle cx="120" cy="124" r="66" fill="none" stroke="#e8dcc0" stroke-width="1.2" opacity=".8"/>`;
        s += `<path d="M20 90Q60 78 100 90T200 84" stroke="#fff" stroke-width="6" fill="none" stroke-linecap="round" opacity=".5" filter="url(#b1)"/>`;
        for (let i = 0; i < 12; i++) s += sparkle(R() * 240, R() * 200, 1.6 + R() * 3, "#fffaec", .9);
        break;
      case "ink":
        s += `<path d="M44 200C14 112 78 26 152 40C208 52 232 112 206 180" stroke="#2a2630" stroke-width="12" fill="none" stroke-linecap="round" opacity=".7" filter="url(#b1)"/><path d="M58 208C32 138 86 52 148 56" stroke="#2a2630" stroke-width="4" fill="none" stroke-linecap="round" opacity=".5"/>`;
        for (let i = 0; i < 24; i++) s += `<circle cx="${n(R() * 240)}" cy="${n(R() * 270)}" r="${n(1 + R() * 4.5)}" fill="#2a2630" opacity="${n(.25 + R() * .45)}"/>`;
        break;
      default: break;
    }
    return s;
  }

  /* ---------- weapons ---------- */
  function weaponBack(kind, P) {
    const gold = "#c9a24a", red = "#c8402f";
    const tassel = `<path d="M0 -176Q-10 -152 -4 -122M0 -176Q8 -152 6 -120" stroke="${red}" stroke-width="3" fill="none" stroke-linecap="round"/>`;
    switch (kind) {
      case "sword":
        return `<g transform="translate(180 286) rotate(14)"><rect x="-4" y="-132" width="8" height="170" rx="1" fill="#5a4636"/><rect x="-1.2" y="-132" width="2.4" height="170" fill="#c9b08c" opacity=".7"/>` +
          `<rect x="-15" y="-139" width="30" height="7" rx="3" fill="${gold}"/><rect x="-3.8" y="-175" width="7.6" height="38" rx="2" fill="#2f2018"/><circle cx="0" cy="-177" r="5" fill="#7cc4a4"/>${tassel}</g>`;
      case "saber":
        return `<g transform="translate(180 288) rotate(14)"><path d="M-4 -130L4 -130C12 -60 12 0 3 36L-5 36C0 -10 -2 -70 -4 -130Z" fill="#5a4636"/><ellipse cx="0" cy="-134" rx="14" ry="6" fill="${gold}"/>` +
          `<rect x="-3.8" y="-176" width="7.6" height="40" rx="2" fill="#2f2018"/><path d="M0 -176Q-6 -156 -2 -140Q2 -158 6 -170Z" fill="${red}"/><circle cx="0" cy="-178" r="4.6" fill="${gold}"/></g>`;
      case "staff":
        return `<g transform="translate(32 300) rotate(-6)"><rect x="-4" y="-320" width="8" height="330" rx="4" fill="#94623a"/><rect x="-1" y="-320" width="2.4" height="330" fill="#e0b57c" opacity=".6"/>` +
          `<rect x="-6" y="-318" width="12" height="14" rx="3" fill="${gold}"/><path d="M4 -230Q22 -214 14 -190Q10 -210 4 -214Z" fill="${red}"/><rect x="-6" y="-60" width="12" height="9" rx="3" fill="${gold}"/></g>`;
      case "spear":
        return `<g transform="translate(194 300) rotate(5)"><rect x="-2.8" y="-286" width="5.6" height="300" rx="2.8" fill="#84583a"/><path d="M0 -330L9 -292L0 -284L-9 -292Z" fill="#dfe3ec"/>` +
          `<path d="M-8 -284Q0 -268 8 -284Q4 -252 0 -240Q-4 -252 -8 -284Z" fill="${red}"/></g>`;
      default: return "";
    }
  }
  function weaponFront(kind, P) {
    switch (kind) {
      case "fan": {
        let ribs = "", d = "M0 0";
        for (let i = 0; i <= 6; i++) { const a = (-150 + i * 20) * Math.PI / 180; ribs += `<path d="M0 0L${n(Math.cos(a) * 62)} ${n(Math.sin(a) * 62)}" stroke="#8a6a3a" stroke-width="1"/>`; d += `L${n(Math.cos(a) * 62)} ${n(Math.sin(a) * 62)}`; }
        return `<g transform="translate(186 302)"><path d="${d}Z" fill="#f6ecd0" stroke="#8a6a3a" stroke-width="1.4"/><path d="${d}Z" fill="${P.acc[2]}" opacity=".35"/>${ribs}</g>`;
      }
      case "flute":
        return `<g transform="translate(94 286) rotate(-12)"><rect x="0" y="-4" width="108" height="8" rx="4" fill="#4a7a56"/><rect x="0" y="-4" width="108" height="2.6" rx="1.3" fill="#a6d4b0" opacity=".7"/>` +
          [24, 38, 52, 66, 80].map(x => `<circle cx="${x}" cy="0" r="1.8" fill="#16301f"/>`).join("") + `<rect x="-2" y="-5" width="6" height="10" rx="2" fill="#c9a24a"/><path d="M106 2Q114 18 108 30" stroke="#c8402f" stroke-width="3" fill="none" stroke-linecap="round"/></g>`;
      case "brush":
        return `<g transform="translate(194 298) rotate(16)"><rect x="-3" y="-120" width="6" height="90" rx="3" fill="#6a4630"/><rect x="-3.2" y="-60" width="6.4" height="5" fill="#c9a24a"/><path d="M-4 -30Q0 -4 4 -30Z" fill="#241c28"/><path d="M0 -120Q-12 -104 -6 -90" stroke="#c8402f" stroke-width="2.4" fill="none"/></g>`;
      default: return "";
    }
  }

  /* ---------- hair ---------- */
  const HAIRF = 'fill="url(#hair)"';
  const cap = `<path ${HAIRF} d="M82 118C74 66 96 42 120 42C144 42 166 66 158 118L156 152L84 152Z"/>`;
  function hairBack(style, P) {
    const l = P.hair[2];
    switch (style) {
      case "long": return `<path ${HAIRF} d="M80 112C66 62 94 34 120 34C146 34 174 62 160 112C168 172 166 232 190 296L50 296C74 232 72 172 80 112Z"/>` +
        strands(["M96 48C84 100 84 200 72 290", "M144 48C156 100 156 200 168 290", "M120 40C116 120 122 220 118 296", "M104 44C94 110 98 210 88 292"], l, 1.1, .3);
      case "ponytail": return cap + `<path ${HAIRF} d="M140 52C190 30 234 88 216 158C212 198 198 238 210 284C184 262 178 218 188 174C194 126 174 90 140 78Z"/>` +
        strands(["M170 66C204 92 210 150 200 214", "M158 60C190 70 214 110 206 170"], l, 1.2, .35);
      case "bun": return `<ellipse ${HAIRF} cx="120" cy="40" rx="12" ry="10"/><path ${HAIRF} d="M108 46Q120 58 132 46L130 62L110 62Z"/>` + cap +
        strands(["M114 36Q120 31 126 36"], l, 1.2, .5);
      case "twin_buns": return `<ellipse ${HAIRF} cx="88" cy="58" rx="15" ry="13"/><ellipse ${HAIRF} cx="152" cy="58" rx="15" ry="13"/>` + cap +
        strands(["M80 54Q88 48 96 54", "M144 54Q152 48 160 54"], l, 1.2, .5);
      case "wild": return `<path ${HAIRF} d="M78 112C62 60 92 30 120 30C148 30 178 60 162 112C174 158 178 208 200 268L184 258L186 296L166 268L156 298L142 266L120 298L102 266L90 298L80 262L58 286L66 244C70 196 72 156 78 112Z"/>` +
        strands(["M98 48C84 100 80 190 66 280", "M146 46C160 100 166 190 184 284", "M120 38C122 110 118 210 122 290"], l, 1.2, .3);
      case "braid": case "short": return cap;
      default: return "";
    }
  }
  function fringe(kind, P) {
    const f = HAIRF;
    switch (kind) {
      case "split": { const [a, b] = both("M120 62C98 62 85 80 84 112C93 98 103 90 113 84C118 78 120 70 120 62Z"); return `<path ${f} d="${a}"/><path ${f} d="${b}"/>`; }
      case "swept": return `<path ${f} d="M84 112C82 76 100 58 124 60C148 62 158 82 156 112C152 92 142 80 128 76C120 90 104 100 90 108Z"/>`;
      case "slick": return `<path ${f} d="M86 108C84 78 100 62 120 62C140 62 156 78 154 108C150 86 138 76 120 76C102 76 90 86 86 108Z"/>` + strands(["M120 64C112 60 102 62 94 74", "M120 64C128 60 138 62 146 74"], P.hair[2], 1, .4);
      case "blunt": return `<path ${f} d="M84 108C82 72 100 52 120 52C140 52 158 72 156 108C152 100 150 94 148 92Q120 84 92 92C90 94 88 100 84 108Z"/>`;
      case "spiky": return `<path ${f} d="M82 114C76 70 98 44 120 44C142 44 164 70 158 114L152 90L146 108L138 84L130 104L120 78L110 104L102 84L94 108L88 90Z"/>`;
      default: return "";
    }
  }
  const sideLocks = (len, w, P) => {
    const [a, b] = both(`M85 104C79 ${n(len * .5)} 81 ${len - 24} 87 ${len}L${87 + w} ${len - 4}C${87 + w - 1} ${len - 50} 89 150 91 122C90 114 89 108 90 104Z`);
    return `<path ${HAIRF} d="${a}"/><path ${HAIRF} d="${b}"/>`;
  };
  function braidShape(P) {
    let s = "";
    for (let i = 0; i < 8; i++) s += `<ellipse ${HAIRF} cx="${n(78 - i * .6)}" cy="${190 + i * 14}" rx="11" ry="9.5"/><path d="M${70 - i * .6} ${193 + i * 14}Q${78 - i * .6} ${186 + i * 14} ${86 - i * .6} ${193 + i * 14}" stroke="${P.hair[1]}" stroke-width="1.2" fill="none" opacity=".7"/>`;
    return s + `<path d="M68 300L88 300L84 306L72 306Z" fill="#c8402f"/>`;
  }
  function hairFront(style, P, male) {
    const l = P.hair[2], shine = `<path d="M94 68Q120 52 146 68" stroke="${l}" stroke-width="3" fill="none" opacity=".4" stroke-linecap="round"/>`;
    switch (style) {
      case "long": return fringe("split", P) + sideLocks(250, 10, P) + strands(["M112 58C104 72 100 84 98 98", "M128 58C136 72 140 84 142 98", "M82 130C80 180 78 220 72 250", "M158 130C160 180 162 220 168 250"], l, 1, .45) + shine;
      case "braid": return fringe("split", P) + sideLocks(176, 8, P) + braidShape(P) + shine;
      case "ponytail": return fringe("swept", P) + sideLocks(162, 7, P) + shine;
      case "bun": return fringe("slick", P) + sideLocks(male ? 150 : 184, 6, P) + strands(["M86 110C84 130 86 146 88 160", "M154 110C156 130 154 146 152 160"], l, 1, .4) + shine;
      case "twin_buns": return fringe("blunt", P) + sideLocks(226, 8, P) + `<path d="M92 66L82 60L84 72ZM92 66L102 60L100 72Z" fill="#c8402f"/><path d="M148 66L138 60L140 72ZM148 66L158 60L156 72Z" fill="#c8402f"/>` + shine;
      case "short": return fringe("spiky", P) + shine;
      case "wild": return `<path ${HAIRF} d="M84 112C80 74 100 54 124 54C150 54 162 80 156 114C150 92 142 82 130 78L124 98L114 80L102 100L96 86C90 92 86 102 84 112Z"/>` + sideLocks(210, 9, P) +
        strands(["M110 58C100 70 94 84 92 100", "M132 58C142 72 148 86 150 102", "M78 130C74 176 66 220 58 262", "M162 130C166 176 174 220 186 262"], l, 1, .4) + shine;
      default: return "";
    }
  }

  /* ---------- body and clothing ---------- */
  function body(a, P, nk) {
    const s = a.build === "masculine" ? 84 : a.build === "feminine" ? 66 : 74, L = 120 - s, Rt = 120 + s;
    const o = P.out, ac = P.acc;
    let out = "";
    if (a.outfit === "hermit") out += `<path d="M${L - 16} 300C${L - 14} 246 ${L + 6} 208 104 202L136 202C${Rt - 6} 208 ${Rt + 14} 246 ${Rt + 16} 300Z" fill="#74624a"/><path d="M${L - 8} 300C${L - 6} 250 ${L + 10} 216 ${L + 30} 208" stroke="#5a4a36" stroke-width="2" fill="none"/>`;
    const torso = `M${120 - nk} 204C${120 - nk - 10} 210 ${L + 24} 214 ${L + 8} 228C${L - 2} 240 ${L - 6} 264 ${L - 8} 300L${Rt + 8} 300C${Rt + 6} 264 ${Rt + 2} 240 ${Rt - 8} 228C${Rt - 24} 214 ${120 + nk + 10} 210 ${120 + nk} 204Z`;
    out += `<path d="${torso}" fill="url(#robe)"/>`;
    // wide sleeves hanging at the sides
    const [sl, sr] = both(`M${L + 12} 226C${L - 6} 240 ${L - 16} 272 ${L - 12} 300L${L + 30} 300C${L + 26} 276 ${L + 26} 252 ${L + 30} 238Z`);
    out += `<path d="${sl}" fill="${o[1]}" opacity=".5"/><path d="${sr}" fill="${o[1]}" opacity=".5"/>`;
    // light and shade
    out += `<path d="M${Rt - 26} 300C${Rt - 24} 268 ${Rt - 36} 244 ${Rt - 58} 230C${Rt - 18} 240 ${Rt} 264 ${Rt} 300Z" fill="${o[1]}" opacity=".32" filter="url(#b1)"/>` +
      `<path d="M${L + 14} 232C${L + 30} 222 ${L + 52} 218 ${L + 70} 216" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round" opacity=".16" filter="url(#b1)"/>`;
    const folds = strands([`M${L + 14} 250C${L + 20} 272 ${L + 18} 288 ${L + 12} 300`, `M${Rt - 14} 250C${Rt - 20} 272 ${Rt - 18} 288 ${Rt - 12} 300`, `M${L + 46} 262C${L + 52} 280 ${L + 50} 292 ${L + 44} 300`], o[1], 1.3, .5);
    const collar = `<path d="M${120 - nk - 2} 203L120 246L${120 + nk + 2} 203L${120 + nk - 3} 200L120 234L${120 - nk + 3} 200Z" fill="#f4efe2" stroke="${LINE}" stroke-width=".7" stroke-linejoin="round"/>` +
      `<path d="M${120 - nk - 7} 205L${120 - nk + 3} 200L132 262L120 268Z" fill="${ac[1]}" stroke="${LINE}" stroke-width=".7" stroke-linejoin="round"/>` +
      `<path d="M${120 + nk + 7} 205L${120 + nk - 3} 200L${L + 34} 296L${L + 18} 296Z" fill="url(#trim)" stroke="${LINE}" stroke-width=".7" stroke-linejoin="round"/>`;
    const sash = `<path d="M${L + 4} 276Q120 290 ${Rt - 4} 276L${Rt - 4} 294Q120 308 ${L + 4} 294Z" fill="url(#trim)" stroke="${LINE}" stroke-width=".7"/>` +
      `<path d="M${L + 4} 280Q120 294 ${Rt - 4} 280" stroke="#fff" stroke-width="1" fill="none" opacity=".5"/>` +
      `<path d="M${L + 40} 288l-5 18l6 -3l5 5l1 -20Z" fill="${ac[0]}" stroke="${LINE}" stroke-width=".6"/>`;
    const pendant = `<path d="M${L + 28} 292V302" stroke="#c8402f" stroke-width="1.4"/><ellipse cx="${L + 28}" cy="306" rx="4" ry="5.5" fill="#8fd6b6" stroke="${LINE}" stroke-width=".6"/>`;
    switch (a.outfit) {
      case "fighter":
        out += `<path d="M${120 - nk - 2} 203L${120 - nk + 4} 192Q120 202 ${120 + nk - 4} 192L${120 + nk + 2} 203Q120 214 ${120 - nk - 2} 203Z" fill="${o[1]}" stroke="${LINE}" stroke-width=".7"/>`;
        out += `<path d="M${L + 4} 270C${L + 4} 244 ${L + 22} 230 ${L + 46} 226L${L + 56} 250C${L + 36} 252 ${L + 20} 260 ${L + 14} 276Z" fill="#5a4636" stroke="${LINE}" stroke-width=".7"/><path d="M${Rt - 4} 270C${Rt - 4} 244 ${Rt - 22} 230 ${Rt - 46} 226L${Rt - 56} 250C${Rt - 36} 252 ${Rt - 20} 260 ${Rt - 14} 276Z" fill="#5a4636" stroke="${LINE}" stroke-width=".7"/>`;
        out += `<circle cx="${L + 26}" cy="244" r="2.4" fill="#d9b25a"/><circle cx="${Rt - 26}" cy="244" r="2.4" fill="#d9b25a"/>`;
        out += `<path d="M100 214L${Rt - 6} 296L${Rt - 28} 300L96 218Z" fill="#6a5240" stroke="${LINE}" stroke-width=".7"/><circle cx="${n(Rt - 40)}" cy="268" r="5" fill="#d9b25a" stroke="${LINE}" stroke-width=".6"/>` + sash + folds;
        break;
      case "monk":
        out += `<path d="M104 204L${Rt + 4} 252L${Rt + 6} 300L${L - 4} 300L${L - 4} 250Z" fill="${ac[0]}" stroke="${LINE}" stroke-width=".7"/>`;
        out += strands([`M${L + 22} 300C${L + 32} 262 70 238 100 214`, `M${L + 58} 300C${L + 64} 270 96 248 116 228`, "M130 300C136 268 148 248 152 230"], ac[1], 1.6, .7);
        out += `<path d="M106 204L120 238L134 204Z" fill="#eadfc6"/>`;
        for (let i = 0; i <= 11; i++) { const t = i / 11, x = (1 - t) * (1 - t) * 96 + 2 * (1 - t) * t * 120 + t * t * 144, y = (1 - t) * (1 - t) * 204 + 2 * (1 - t) * t * 276 + t * t * 204; out += `<circle cx="${n(x)}" cy="${n(y)}" r="4.2" fill="#6a4026" stroke="${LINE}" stroke-width=".5"/><circle cx="${n(x - 1.2)}" cy="${n(y - 1.2)}" r="1" fill="#d6a070"/>`; }
        break;
      case "hermit":
        out += `<path d="M104 206L120 248L136 206Z" fill="#e0d6bc"/><path d="M104 206L120 252M136 206L120 252" stroke="${o[1]}" stroke-width="1.6" fill="none"/>`;
        out += `<path d="M${L + 4} 232C${L + 20} 252 ${L + 20} 270 ${L + 10} 290" stroke="#8a7a5a" stroke-width="2" fill="none"/>` +
          `<path d="M${L + 4} 284Q120 300 ${Rt - 4} 284" stroke="#9a7c46" stroke-width="6" fill="none"/><path d="M${L + 30} 288Q${L + 22} 304 ${L + 34} 308Q${L + 44} 304 ${L + 36} 290Z" fill="#c89a4c" stroke="${LINE}" stroke-width=".7"/>` + folds;
        break;
      case "scholar":
        out += `<path d="M104 204L113 200L116 300L102 300Z" fill="${ac[0]}"/><path d="M136 204L127 200L124 300L138 300Z" fill="${ac[0]}"/><path d="M113 203L120 234L127 203Z" fill="#f4efe2"/>`;
        out += strands([`M${L + 14} 300C${L + 14} 262 ${L + 28} 240 ${L + 52} 228`, `M${Rt - 14} 300C${Rt - 14} 262 ${Rt - 28} 240 ${Rt - 52} 228`], ac[2], 1.6, .7);
        out += sash + pendant + folds;
        break;
      case "noble": {
        out += collar;
        for (let i = 0; i < 10; i++) { const x = L + 18 + (i % 5) * 20, y = 256 + Math.floor(i / 5) * 22; out += `<circle cx="${n(x)}" cy="${y}" r="5.5" fill="none" stroke="${ac[2]}" stroke-width="1.3" opacity=".9"/><circle cx="${n(x)}" cy="${y}" r="1.8" fill="${ac[2]}"/>`; }
        for (let i = 0; i < 4; i++) { const y = 250 + i * 12; out += `<path d="M${L - 4} ${y}q6 -6 12 0t12 0" stroke="${ac[2]}" stroke-width="1" fill="none" opacity=".8"/><path d="M${Rt - 28} ${y}q6 -6 12 0t12 0" stroke="${ac[2]}" stroke-width="1" fill="none" opacity=".8"/>`; }
        out += `<path d="M${120 - nk - 4} 206Q120 222 ${120 + nk + 4} 206" stroke="${ac[2]}" stroke-width="2.2" fill="none"/>` + sash + pendant;
        break;
      }
      default: out += collar + sash + pendant + folds;     // robe
    }
    return out;
  }

  /* ---------- the face ---------- */
  const FACE = {
    feminine: "M88 108C88 80 102 66 120 66C138 66 152 80 152 108C152 128 147 148 135 163C128 172 123 177 120 178C117 177 112 172 105 163C93 148 88 128 88 108Z",
    masculine: "M85 106C85 78 101 65 120 65C139 65 155 78 155 106C155 126 152 146 142 160C134 171 126 178 120 179C114 178 106 171 98 160C88 146 85 126 85 106Z",
    androgynous: "M86 107C86 79 101 66 120 66C139 66 154 79 154 107C154 127 149 147 138 162C130 172 124 178 120 179C116 178 110 172 102 162C91 147 86 127 86 107Z",
  };

  function eye(cx, cy, side, kind, ec, build, tag) {
    const K = { sharp: [10.4, 5.2, 3.6, 2.8], soft: [9.8, 6.6, 1.4, 3.7], sleepy: [10.4, 3.9, .8, 2.8], wide: [9.4, 7.5, .6, 4.2] }[kind] || [9.8, 6.6, 1.4, 3.7];
    const [w, up, lift, lo] = K;
    const ix = cx - side * w * .95, iy = cy + .8, ox = cx + side * w, oy = cy - lift;
    const upper = `M${n(ix)} ${n(iy)}C${n(cx - side * w * .4)} ${n(cy - up * 1.9)} ${n(cx + side * w * .45)} ${n(cy - up * 2)} ${n(ox)} ${n(oy)}`;
    const lower = `C${n(cx + side * w * .4)} ${n(cy + lo * 1.7)} ${n(cx - side * w * .3)} ${n(cy + lo * 1.8)} ${n(ix)} ${n(iy)}`;
    const ic = [cx - side * .6, cy - .2], r = up * 1.02;
    let s = `<defs><clipPath id="c${tag}"><path d="${upper}${lower}Z"/></clipPath><radialGradient id="i${tag}" cx=".5" cy=".62" r=".6"><stop offset="0" stop-color="${ec[1]}"/><stop offset=".75" stop-color="${ec[0]}"/><stop offset="1" stop-color="#0c0810"/></radialGradient></defs>`;
    s += `<path d="${upper}${lower}Z" fill="#f6f1ea"/><g clip-path="url(#c${tag})"><rect x="${n(cx - w - 2)}" y="${n(cy - up * 2.2)}" width="${n(w * 2 + 4)}" height="${n(up * 1.1)}" fill="#8a5a48" opacity=".22"/>` +
      `<circle cx="${n(ic[0])}" cy="${n(ic[1])}" r="${n(r)}" fill="url(#i${tag})"/><circle cx="${n(ic[0])}" cy="${n(ic[1] + .3)}" r="${n(r * .46)}" fill="#0a0810"/>` +
      `<ellipse cx="${n(ic[0])}" cy="${n(ic[1] - r * .55)}" rx="${n(r)}" ry="${n(r * .5)}" fill="#000" opacity=".22"/>` +
      `<circle cx="${n(ic[0] - r * .34)}" cy="${n(ic[1] - r * .42)}" r="${n(r * .3)}" fill="#fff" opacity=".95"/><circle cx="${n(ic[0] + r * .38)}" cy="${n(ic[1] + r * .4)}" r="${n(r * .15)}" fill="#fff" opacity=".8"/></g>`;
    s += `<path d="${upper}" stroke="${LINE}" stroke-width="2.3" fill="none" stroke-linecap="round"/>`;
    s += `<path d="M${n(ox)} ${n(oy)}L${n(ox + side * 4)} ${n(oy - 1.2 - (kind === "sharp" ? 1.8 : 0))}" stroke="${LINE}" stroke-width="2" stroke-linecap="round"/>`;
    s += `<path d="M${n(ix + side * 1)} ${n(iy)}${lower.replace(/ -?[\d.]+ -?[\d.]+$/, ` ${n(ox)} ${n(oy)}`)}" stroke="${LINE}" stroke-width=".8" fill="none" opacity=".45"/>`;
    s += `<path d="M${n(cx - side * w * .6)} ${n(cy - up * 1.5)}Q${n(cx + side * 1)} ${n(cy - up * 3)} ${n(ox + side * 1.6)} ${n(oy - 2.6)}" stroke="#a87858" stroke-width=".9" fill="none" opacity=".75"/>`;
    if (build !== "masculine") s += `<path d="M${n(ox - side * 1.6)} ${n(oy + .2)}l${n(side * 3.4)} -3.4M${n(ox - side * 4)} ${n(oy - 1.2)}l${n(side * 2.4)} -3.2" stroke="${LINE}" stroke-width="1.1" stroke-linecap="round"/>`;
    return s;
  }
  function brow(side, kind, build, col) {
    const ix = 120 + side * 9, ox = 120 + side * 33, t = build === "masculine" ? 4.4 : build === "feminine" ? 2.3 : 3.2;
    let iy = 107, my = 103.6, oy = 106.6;
    if (kind === "fierce") { iy = 111; my = 104.5; oy = 100.5; }
    else if (kind === "weary") { iy = 102; my = 103.5; oy = 109; }
    else if (kind === "smile") { iy = 106; my = 101.5; oy = 105; }
    else if (kind === "smirk" && side > 0) { iy = 102.5; my = 97.5; oy = 99; }
    const mx = (ix + ox) / 2;
    return `<path d="M${ix} ${iy}Q${n(mx)} ${n(my - 1)} ${ox} ${oy}L${ox} ${n(oy + t * .35)}Q${n(mx)} ${n(my + t)} ${ix} ${n(iy + t)}Z" fill="${col}" opacity=".92"/>`;
  }
  function mouth(kind, build) {
    const lip = build === "feminine" ? "#d0686e" : build === "masculine" ? "#b8746a" : "#c46c6c";
    const M = {
      calm: ["M111 158Q115.5 155.4 120 156.8Q124.5 155.4 129 158Q120 159.4 111 158Z", "M112 158.4Q120 165.4 128 158.4Q120 160 112 158.4Z"],
      smile: ["M109.5 156.4Q115 154.8 120 156Q125 154.8 130.5 156.4Q120 160 109.5 156.4Z", "M111 157.8Q120 167 129 157.8Q120 160.4 111 157.8Z"],
      smirk: ["M112 159Q116 156.6 120.5 157Q125 155.6 130 153.4Q123 160 112 159Z", "M113 159Q121 164.6 129 156.4Q121 160.6 113 159Z"],
      fierce: ["M111.5 159.4Q120 155.4 128.5 159.4Q120 157.6 111.5 159.4Z", "M113 159.6Q120 163 127 159.6Q120 160.4 113 159.6Z"],
      weary: ["M111.5 158.6Q120 156.6 128.5 160.4Q120 159.8 111.5 158.6Z", "M113 159Q120 163.6 127.4 160.4Q120 160.4 113 159Z"],
    }[kind] || null;
    const m = M || ["M111 158Q115.5 155.4 120 156.8Q124.5 155.4 129 158Q120 159.4 111 158Z", "M112 158.4Q120 165.4 128 158.4Q120 160 112 158.4Z"];
    return `<path d="${m[1]}" fill="${lip}"/><path d="${m[0]}" fill="${lip}" stroke="#7a3a3a" stroke-width=".8" stroke-linejoin="round"/><path d="M115 162Q120 164.4 125 162" stroke="#fff" stroke-width="1" fill="none" opacity=".4"/>`;
  }

  function headwear(kind, P, style) {
    const ac = P.acc, o = P.out;
    switch (kind) {
      case "bamboo_hat":
        return `<path d="M22 98Q120 86 218 98Q182 28 120 20Q58 28 22 98Z" fill="#dcc07e"/><path d="M22 98Q120 86 218 98Q182 28 120 20Q58 28 22 98Z" fill="url(#glow)" opacity=".3"/>` +
          [-60, -40, -20, 0, 20, 40, 60].map(x => `<path d="M${120 + x * .14} 22L${120 + x * 1.7} 94" stroke="#a88650" stroke-width="1" opacity=".7"/>`).join("") +
          `<path d="M22 98Q120 86 218 98" stroke="#8a6a2e" stroke-width="2" fill="none"/><path d="M74 94Q76 152 108 178M166 94Q164 152 132 178" stroke="${ac[0]}" stroke-width="2.2" fill="none"/><ellipse cx="120" cy="102" rx="62" ry="8" fill="#000" opacity=".16" filter="url(#b1)"/>`;
      case "scholar_cap":
        return `<path d="M88 80L152 80L150 42L90 42Z" fill="#2f313e" stroke="${LINE}" stroke-width=".8"/><path d="M88 80L152 80" stroke="${ac[0]}" stroke-width="3"/><path d="M92 54L148 54" stroke="#6a6d80" stroke-width="2" opacity=".7"/><path d="M150 72L176 136L166 138L144 80Z" fill="#2f313e" stroke="${LINE}" stroke-width=".8"/>`;
      case "headband":
        return `<path d="M85 90Q120 82 155 90L155 99Q120 91 85 99Z" fill="url(#trim)" stroke="${LINE}" stroke-width=".7"/><circle cx="120" cy="91" r="3.2" fill="#8fd6b6" stroke="${LINE}" stroke-width=".5"/><path d="M87 96L66 126L78 128L92 104Z" fill="${ac[0]}"/><path d="M89 100L72 140L84 136L96 108Z" fill="${ac[1]}"/>`;
      case "crown": {
        const y = style === "bun" ? 40 : 54;
        return `<path d="M107 ${y + 2}Q120 ${y - 12} 133 ${y + 2}L131 ${y + 14}Q120 ${y + 19} 109 ${y + 14}Z" fill="#e8c05c" stroke="#8a6418" stroke-width=".8"/><path d="M96 ${y + 6}L144 ${y + 6}" stroke="#d4a63e" stroke-width="2.4" stroke-linecap="round"/><circle cx="95" cy="${y + 6}" r="2.6" fill="#8fd6b6" stroke="#8a6418" stroke-width=".5"/><circle cx="145" cy="${y + 6}" r="2.6" fill="#8fd6b6" stroke="#8a6418" stroke-width=".5"/><circle cx="120" cy="${y - 2}" r="3.2" fill="#c8402f" stroke="#8a6418" stroke-width=".5"/>`;
      }
      case "hairpin":
        return style === "bun" || style === "twin_buns"
          ? `<path d="M96 44L146 54" stroke="#e8c05c" stroke-width="3" stroke-linecap="round"/><circle cx="148" cy="54.5" r="4" fill="#c8402f" stroke="#8a6418" stroke-width=".5"/><circle cx="94" cy="43.5" r="3" fill="#e8c05c"/><path d="M146 58Q150 72 144 84M152 56Q158 70 154 82" stroke="#e8c05c" stroke-width="1.1" fill="none"/><circle cx="144" cy="86" r="2.2" fill="#8fd6b6"/>`
          : `<path d="M146 62L162 46" stroke="#e8c05c" stroke-width="3" stroke-linecap="round"/><circle cx="164" cy="44" r="5" fill="#c8402f" stroke="#8a6418" stroke-width=".5"/><path d="M160 52Q164 70 158 86M166 50Q172 66 168 82" stroke="#e8c05c" stroke-width="1.1" fill="none"/><circle cx="158" cy="88" r="2.4" fill="#8fd6b6"/><circle cx="168" cy="84" r="2.4" fill="#8fd6b6"/>`;
      case "flower": {
        let f = "";
        for (let i = 0; i < 5; i++) { const a = i * 72 * Math.PI / 180; f += `<circle cx="${n(154 + Math.cos(a) * 7)}" cy="${n(68 + Math.sin(a) * 7)}" r="6" fill="#f4b2c0"/>`; }
        return f + `<circle cx="154" cy="68" r="3.6" fill="#f0c860"/><path d="M146 80Q140 86 134 82M162 80Q168 88 174 84" stroke="#5f9a74" stroke-width="3" fill="none"/>`;
      }
      default: return "";
    }
  }

  /* ---------- the whole portrait ---------- */
  function render(a, seed, opts) {
    a = a || {}; opts = opts || {};
    const R = rng(hash(seed || "jianghu"));
    const P = {
      skin: pick(SKIN, a.skin, "fair"), hair: pick(HAIR, a.hair_color, "black"), out: pick(OUTFIT, a.outfit_color, "ink"),
      acc: pick(OUTFIT, a.accent_color, "gold"), eye: pick(EYE, a.eye_color, "brown"),
    };
    const build = ["feminine", "masculine", "androgynous"].includes(a.build) ? a.build : "androgynous";
    const age = ["young", "adult", "elder"].includes(a.age) ? a.age : "adult";
    const style = ["long", "ponytail", "bun", "twin_buns", "short", "wild", "braid", "bald"].includes(a.hair_style) ? a.hair_style : "short";
    const expr = ["calm", "smirk", "smile", "fierce", "weary"].includes(a.expression) ? a.expression : "calm";
    const mark = a.mark || "none", masked = mark === "mask", male = build === "masculine";
    const nk = male ? 14 : build === "feminine" ? 10.5 : 12.5;
    const browCol = age === "elder" ? "#d0d0da" : P.hair[1];
    const ap = { ...a, build, outfit: a.outfit || "robe" };
    const T = 'transform="rotate(-2.5 120 190)"';
    const sk = P.skin[1];

    let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 300">` + defs(P);
    if (opts.bg !== false) s += background(a.scene, R);
    s += aura(a.aura, R);
    s += `<g transform="translate(120 218) scale(1.14) translate(-120 -218)">`;
    s += weaponBack(a.weapon, P) + `<g ${T}>${hairBack(style, P)}</g>`;
    // neck
    s += `<path d="M${120 - nk} 160V212H${120 + nk}V160Z" fill="${P.skin[2]}"/><path d="M${120 - nk} 170Q120 196 ${120 + nk} 170V190Q120 208 ${120 - nk} 190Z" fill="${sk}" opacity=".75" filter="url(#b1)"/>`;
    s += body(ap, P, nk);
    // the head
    s += `<g ${T}>`;
    s += `<ellipse cx="87" cy="124" rx="4.8" ry="8.6" fill="${P.skin[2]}"/><ellipse cx="153" cy="124" rx="4.8" ry="8.6" fill="${P.skin[2]}"/>`;
    s += `<path d="${FACE[build]}" fill="url(#skin)"/><path d="${FACE[build]}" fill="none" stroke="#a87858" stroke-width=".8" opacity=".5"/>`;
    s += `<path d="M150 104C151 130 145 152 132 166C127 172 123 176 120 178C134 170 148 150 152 122Z" fill="${sk}" opacity=".5" filter="url(#b1)"/>`;
    s += `<ellipse cx="120" cy="84" rx="34" ry="12" fill="${sk}" opacity=".42" filter="url(#b2)"/>`;
    if (build !== "masculine" || age === "young") s += `<ellipse cx="99" cy="140" rx="9.5" ry="5.4" fill="#f08a82" opacity=".26" filter="url(#b2)"/><ellipse cx="141" cy="140" rx="9.5" ry="5.4" fill="#f08a82" opacity=".26" filter="url(#b2)"/>`;
    s += eye(105.5, 122, -1, a.eyes, P.eye, build, "l") + eye(134.5, 122, 1, a.eyes, P.eye, build, "r");
    s += brow(-1, expr, build, browCol) + brow(1, expr, build, browCol);
    if (!masked) {
      s += `<path d="M118.6 128Q117 140 113.4 146" stroke="${sk}" stroke-width="1.2" fill="none" opacity=".6" stroke-linecap="round"/><path d="M113.6 146.4Q120 151.4 126.4 146.4" stroke="#9a6a58" stroke-width="1.1" fill="none" opacity=".75" stroke-linecap="round"/>` +
        `<ellipse cx="121.4" cy="142" rx="2" ry="3.4" fill="#fff" opacity=".28"/>` + mouth(expr, build);
    }
    if (age === "elder") s += strands(["M92 146Q96 154 94 162", "M148 146Q144 154 146 162", "M104 80Q120 77 136 80", "M106 86Q120 84 134 86"], sk, 1.2, .8);
    if (mark === "scar") s += `<path d="M92 100L112 138" stroke="#b0504a" stroke-width="2.4" stroke-linecap="round"/><path d="M98 108l7 -3M102 116l7 -3M106 124l7 -3" stroke="#b0504a" stroke-width="1.3" stroke-linecap="round"/>`;
    if (mark === "eyepatch") s += `<path d="M126 114L86 100M146 122L154 112" stroke="#1c1a24" stroke-width="2" fill="none"/><ellipse cx="136" cy="120" rx="12" ry="10" fill="#1c1a24"/><ellipse cx="133" cy="116" rx="4" ry="2.4" fill="#fff" opacity=".12"/>`;
    if (mark === "forehead_mark") s += `<path d="M120 84Q114 90 120 96Q126 90 120 84Z" fill="#cf3b3a"/>`;
    if (masked) s += `<path d="M87 138Q120 150 153 138L152 158Q144 184 120 188Q96 184 88 158Z" fill="${P.out[1]}"/><path d="M90 146Q120 158 150 146" stroke="${P.out[2]}" stroke-width="1.3" fill="none" opacity=".6"/><path d="M87 138L80 124M153 138L160 124" stroke="${P.out[1]}" stroke-width="2.4" fill="none"/>`;
    if (style === "bald") s += `<path d="M98 72Q120 62 142 72" stroke="#fff" stroke-width="3" fill="none" opacity=".45" stroke-linecap="round"/>` + (ap.outfit === "monk" ? `<circle cx="112" cy="76" r="2.2" fill="#b0504a"/><circle cx="120" cy="73" r="2.2" fill="#b0504a"/><circle cx="128" cy="76" r="2.2" fill="#b0504a"/>` : "");
    s += hairFront(style, P, male);
    if (mark === "beard") s += `<path ${HAIRF} d="M99 148Q100 184 112 204Q118 242 120 266Q122 242 128 204Q140 184 141 148Q133 164 120 164Q107 164 99 148Z"/><path ${HAIRF} d="M104 150Q112 144 120 149Q128 144 136 150Q128 157 120 154Q112 157 104 150Z"/>` + strands(["M112 170Q116 210 119 252", "M128 170Q124 210 121 252", "M120 172V258"], P.hair[2], 1, .5);
    s += headwear(a.headwear, P, style);
    s += `</g>` + weaponFront(a.weapon, P) + `</g>`;
    return s + "</svg>";
  }

  window.renderPortrait = render;
})();
