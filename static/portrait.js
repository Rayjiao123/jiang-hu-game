/* Wuxia portrait builder in the style of classic Chinese martial-arts illustration (Jin Yong game art):
 * ink outlines, realistic proportions, narrow eyes under strong brows, layered hanfu, topknots and
 * long beards, an ink-wash landscape on paper, and a red seal.
 *
 *   renderPortrait(appearance, seed)  ->  SVG markup (viewBox 0 0 240 300)
 *
 * Each layer is chosen by one field of `appearance` (see APPEARANCE in app/game.py). Unknown or
 * missing values fall back to a default, so a portrait always draws. `seed` (the character's name)
 * only scatters particles and leaves, so the same character always looks the same. */
(function () {
  "use strict";

  const INK = "#2a1d16";

  /* ---------- palettes (traditional mineral and ink colours): [main, dark, light] ---------- */
  const OUTFIT = {
    ink: ["#3a3b44", "#202128", "#666875"], crimson: ["#a8352f", "#6e1f1d", "#d1675c"],
    jade: ["#3d8068", "#24503f", "#7fb89a"], azure: ["#34548f", "#1f3359", "#7b97c8"],
    violet: ["#6f4c86", "#44284f", "#a487b5"], gold: ["#cf9d36", "#8c6618", "#ecc873"],
    white: ["#e8e3d3", "#b5ae98", "#faf7ee"], ash: ["#837b6c", "#554e42", "#b3ab9a"],
  };
  const HAIR = {
    black: ["#1f1e25", "#0a0a0d", "#5a5a6a"], brown: ["#5b3a27", "#35200f", "#946a46"],
    silver: ["#c4c6ce", "#868a98", "#f1f2f5"], white: ["#e8e6e2", "#a6a29a", "#ffffff"],
    red: ["#9a3524", "#5e1c10", "#cf6a4c"], blue: ["#2b3d6b", "#171f3d", "#5b78b0"],
    green: ["#2e5a44", "#173324", "#5f9478"],
  };
  const SKIN = { fair: ["#f1dcc2", "#d4b08c"], warm: ["#e6c398", "#c29868"], tan: ["#d1a070", "#a47446"], deep: ["#a87649", "#7a4f2c"] };
  const EYE = { black: "#14121a", brown: "#3d2414", amber: "#7a4a10", jade: "#1c4a3a", blue: "#1a2f66", violet: "#40206b", red: "#6b1420" };
  const PAPER = { bamboo: ["#dce3c6", "#a9bd95"], mountains: ["#f0e3c5", "#d6bd93"], lanterns: ["#1f2340", "#4b3056"], snow: ["#e6ebf0", "#bac6d2"], river: ["#f0e0b9", "#c3cfc0"] };

  const pick = (map, key, fallback) => map[key] || map[fallback];
  const n = v => Math.round(v * 10) / 10;
  const hash = s => { let h = 2166136261; for (const c of String(s)) { h ^= c.codePointAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
  const rng = seed => { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; };
  const mirror = d => d.replace(/(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)/g, (m, x, y) => `${n(240 - x)} ${y}`);   // flip an "x y x y ..." path about the centre line
  const strandLines = (list, col, w, op) => list.map(d => `<path d="${d}" stroke="${col}" stroke-width="${w}" fill="none" opacity="${op}"/>`).join("");

  /* ---------- background: an ink-wash scene on paper ---------- */
  function ridge(R, y0, amp, fill, op, step) {
    let d = `M0 300L0 ${n(y0)}`, py = y0;
    for (let x = step; x <= 240 + step; x += step) { const y = y0 - R() * amp; d += `Q${n(x - step / 2)} ${n(Math.min(py, y) - amp * .3)} ${n(x)} ${n(y)}`; py = y; }
    return `<path d="${d}L${240 + step} 300Z" fill="${fill}" opacity="${op}" stroke="none"/>`;
  }
  const mist = (cx, cy, rx, ry, op) => `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="#fffaf0" opacity="${op}" filter="url(#soft)" stroke="none"/>`;
  function stalk(x, w, col, op) {
    let s = `<g opacity="${op}" stroke="none"><rect x="${x}" y="0" width="${w}" height="300" fill="${col}"/>`;
    for (let y = 26 + (x * 7) % 23; y < 300; y += 50) s += `<rect x="${x - 1}" y="${y}" width="${w + 2}" height="3" fill="#1d3a2c"/>`;
    return s + `<rect x="${n(x + w * .2)}" y="0" width="${n(w * .2)}" height="300" fill="#fff" opacity=".22"/></g>`;
  }
  const leaf = (x, y, rot, len, fill) => `<path d="M0 0Q${n(len / 2)} ${n(-len * .26)} ${n(len)} 0Q${n(len / 2)} ${n(len * .26)} 0 0Z" transform="translate(${n(x)} ${n(y)}) rotate(${n(rot)})" fill="${fill}" stroke="none"/>`;
  function lantern(x, y, r) {
    return `<circle cx="${x}" cy="${y}" r="${r * 2.8}" fill="url(#lg)" stroke="none"/><path d="M${x} ${y - r * 1.3}V${y - r * 2.2}" stroke="#241410" stroke-width="1.2"/>` +
      `<rect x="${n(x - r * .55)}" y="${n(y - r * 1.4)}" width="${n(r * 1.1)}" height="3" fill="#2f1d12" stroke="none"/><ellipse cx="${x}" cy="${y}" rx="${r}" ry="${n(r * 1.22)}" fill="#c8402f" stroke="#5a1a14" stroke-width="1"/>` +
      `<rect x="${n(x - r * .55)}" y="${n(y + r * 1.2)}" width="${n(r * 1.1)}" height="3" fill="#2f1d12" stroke="none"/><path d="M${x} ${n(y + r * 1.4)}V${n(y + r * 2.5)}" stroke="#d9a73a" stroke-width="1.6"/>`;
  }
  function pine(x, y, k, col) {
    let s = `<g fill="${col}" stroke="none"><rect x="${n(x - 2 * k)}" y="${n(y - 40 * k)}" width="${n(4 * k)}" height="${n(42 * k)}"/>`;
    for (let i = 0; i < 4; i++) { const yy = y - (14 + i * 17) * k, w = (24 - i * 4) * k; s += `<path d="M${n(x - w)} ${n(yy)}Q${x} ${n(yy - 16 * k)} ${n(x + w)} ${n(yy)}Q${x} ${n(yy - 5 * k)} ${n(x - w)} ${n(yy)}Z"/>`; }
    return s + "</g>";
  }
  function background(scene, R) {
    const c = PAPER[scene] || PAPER.mountains;
    let s = `<rect width="240" height="300" fill="url(#bg)" stroke="none"/>`;
    if (scene === "bamboo") {
      s += ridge(R, 190, 50, "#5f7f6c", .28, 30) + mist(60, 200, 90, 14, .55);
      s += stalk(66, 6, "#4f7f60", .42) + stalk(170, 7, "#4f7f60", .46);
      [[14, 11, .95], [40, 8, .82], [198, 9, .88], [224, 12, .96]].forEach(([x, w, o]) => { s += stalk(x, w, "#3f6e52", o); });
      for (let i = 0; i < 11; i++) { const left = i % 2 === 0; s += leaf(left ? 14 + R() * 48 : 176 + R() * 50, 16 + R() * 130, (R() - .5) * 110 + (left ? 25 : 155), 16 + R() * 14, "#4f8a63"); }
    } else if (scene === "lanterns") {
      s += `<path d="M-5 34Q120 72 245 28" fill="none" stroke="#120c18" stroke-width="1.6"/>`;
      [[20, 44], [64, 56], [120, 60], [178, 52], [222, 38]].forEach(([x, y], i) => { s += lantern(x, y, 9 + (i % 2) * 2); });
      s += `<path d="M0 214Q36 200 70 226L70 300L0 300ZM170 226Q204 200 240 214L240 300L170 300Z" fill="#150f1e" stroke="none" opacity=".8"/>`;
      for (let i = 0; i < 14; i++) s += `<circle cx="${n(R() * 240)}" cy="${n(80 + R() * 160)}" r="${n(.8 + R() * 1.3)}" fill="#ffd9a0" opacity=".55" stroke="none"/>`;
    } else if (scene === "snow") {
      s += ridge(R, 170, 46, "#7d8b99", .3, 34) + ridge(R, 214, 36, "#5d6c7b", .4, 28) + mist(120, 200, 120, 16, .7);
      s += pine(26, 232, 1, "#2f4a46") + pine(212, 224, 1.15, "#2f4a46") + pine(66, 246, .75, "#3d5a54");
      s += `<path d="M0 262Q60 240 120 258T240 246V300H0Z" fill="#f6f9fc" opacity=".9" stroke="none"/>`;
      for (let i = 0; i < 48; i++) s += `<circle cx="${n(R() * 240)}" cy="${n(R() * 280)}" r="${n(.8 + R() * 1.9)}" fill="#fff" opacity="${n(.55 + R() * .4)}" stroke="none"/>`;
    } else if (scene === "river") {
      s += `<circle cx="64" cy="108" r="26" fill="#c0392b" opacity=".85" stroke="none"/>`;
      s += ridge(R, 190, 36, "#6c7d86", .35, 36) + mist(120, 200, 110, 12, .6);
      for (let i = 0; i < 9; i++) s += `<path d="M${n(R() * 200 - 10)} ${n(214 + i * 9)}q8 -4 16 0t16 0t16 0" stroke="#fffaf0" stroke-width="1.4" fill="none" opacity=".5"/>`;
      s += `<path d="M184 210L216 210L210 218L190 218Z" fill="#2a2420" stroke="none"/><path d="M200 208V176L216 206Z" fill="#f6ead2" stroke="#2a2420" stroke-width="1"/>`;
      for (let i = 0; i < 7; i++) s += `<path d="M${n(14 + i * 9)} 300Q${n(12 + i * 9)} 262 ${n(20 + i * 9)} 240" stroke="#4d5c3c" stroke-width="2" fill="none" opacity=".7"/>`;
    } else { // mountains
      s += `<circle cx="170" cy="94" r="27" fill="#c0392b" opacity=".85" stroke="none"/>`;
      s += ridge(R, 180, 66, "#58606b", .3, 40) + mist(80, 196, 100, 14, .55) + ridge(R, 224, 54, "#454c57", .46, 34) + mist(170, 236, 90, 12, .5) + ridge(R, 266, 40, "#2f343d", .66, 30);
      s += pine(206, 252, .9, "#26302e");
    }
    return s;
  }

  /* ---------- aura: an elemental effect painted behind the figure ---------- */
  const tongue = (bx, by, tx, ty, w, fill, op) => {
    const my = (by + ty) / 2;
    return `<path d="M${n(bx - w)} ${n(by)}Q${n((bx + tx) / 2 - w)} ${n(my)} ${n(tx)} ${n(ty)}Q${n((bx + tx) / 2 + w * 1.1)} ${n(my + 10)} ${n(bx + w)} ${n(by)}Z" fill="${fill}" opacity="${op}" stroke="#6e1f1d" stroke-width=".9"/>`;
  };
  const sparkle = (x, y, r, fill, op) => `<path d="M${n(x)} ${n(y - r)}L${n(x + r * .28)} ${n(y - r * .28)}L${n(x + r)} ${n(y)}L${n(x + r * .28)} ${n(y + r * .28)}L${n(x)} ${n(y + r)}L${n(x - r * .28)} ${n(y + r * .28)}L${n(x - r)} ${n(y)}L${n(x - r * .28)} ${n(y - r * .28)}Z" fill="${fill}" opacity="${op}" stroke="none"/>`;
  function aura(kind, R) {
    let s = "";
    switch (kind) {
      case "flame":
        s += `<defs><linearGradient id="fa" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#e8a23a"/><stop offset="1" stop-color="#c8402f"/></linearGradient></defs>`;
        for (let i = 0; i < 11; i++) { const bx = 14 + i * 21 + R() * 8, by = 236 + R() * 40; s += tongue(bx, by, bx + (R() - .5) * 46, by - (80 + R() * 120), 13 + R() * 9, "url(#fa)", .82); }
        for (let i = 0; i < 8; i++) { const bx = 34 + i * 25 + R() * 10, by = 250 + R() * 30; s += tongue(bx, by, bx + (R() - .5) * 30, by - (50 + R() * 70), 8 + R() * 5, "#f2cf6e", .9); }
        for (let i = 0; i < 16; i++) s += sparkle(R() * 240, 30 + R() * 230, 2 + R() * 3, "#f2cf6e", .8);
        break;
      case "ice":
        for (let i = 0; i < 12; i++) {
          const a = (-200 + i * 20) * Math.PI / 180, r0 = 58, r1 = 98 + R() * 46, bx = 120 + Math.cos(a) * r0, by = 150 + Math.sin(a) * r0, tx = 120 + Math.cos(a) * r1, ty = 150 + Math.sin(a) * r1, px = -Math.sin(a) * 10, py = Math.cos(a) * 10;
          s += `<path d="M${n(bx - px)} ${n(by - py)}L${n(tx)} ${n(ty)}L${n(bx + px)} ${n(by + py)}Z" fill="#cfe6ee" opacity=".85" stroke="#3b5566" stroke-width="1"/>`;
          s += `<path d="M${n(bx)} ${n(by)}L${n(tx)} ${n(ty)}L${n(bx + px)} ${n(by + py)}Z" fill="#fff" opacity=".45" stroke="none"/>`;
        }
        for (let i = 0; i < 14; i++) s += sparkle(R() * 240, R() * 260, 2 + R() * 3.5, "#fff", .9);
        break;
      case "wind":
        for (let i = 0; i < 7; i++) {
          const y = 40 + i * 34 + R() * 10, x = -10 + R() * 40, d = `M${n(x)} ${n(y)}C${n(x + 60)} ${n(y - 22)} ${n(x + 120)} ${n(y + 22)} ${n(x + 190 + R() * 40)} ${n(y - 8)}c14 -6 22 8 10 14`;
          s += `<path d="${d}" stroke="#fffaf0" stroke-width="${n(3 + R() * 2.4)}" fill="none" stroke-linecap="round" opacity=".75"/><path d="${d}" stroke="#4a4f55" stroke-width=".9" fill="none" opacity=".5" transform="translate(0 3)"/>`;
        }
        break;
      case "petals":
        for (let i = 0; i < 26; i++) s += `<ellipse cx="${n(R() * 240)}" cy="${n(R() * 290)}" rx="${n(4 + R() * 3.4)}" ry="${n(2.4 + R() * 1.6)}" transform="rotate(${n(R() * 360)} 120 150)" fill="${R() > .4 ? "#e9a3ad" : "#fbe9ea"}" opacity=".92" stroke="#8a4a52" stroke-width=".7"/>`;
        break;
      case "lightning":
        [[30, 0], [210, 10], [120, -10]].forEach(([x, y], k) => {
          let d = `${x},${y}`, px = x, py = y; const tx = k === 2 ? 120 : (x < 120 ? 96 : 144), steps = 6;
          for (let i = 1; i <= steps; i++) { px = x + (tx - x) * i / steps + (R() - .5) * 26; py = y + (110 + R() * 40) * i / steps; d += ` ${n(px)},${n(py)}`; }
          s += `<polyline points="${d}" fill="none" stroke="${INK}" stroke-width="7" stroke-linejoin="round" opacity=".55"/><polyline points="${d}" fill="none" stroke="#f6e27a" stroke-width="3.2" stroke-linejoin="round"/>`;
        });
        break;
      case "moon":
        s += `<circle cx="120" cy="128" r="94" fill="#fff6dc" opacity=".25" stroke="none"/><circle cx="120" cy="128" r="72" fill="#fff6dc" opacity=".5" stroke="none"/><circle cx="120" cy="128" r="60" fill="#fffaf0" opacity=".8" stroke="${INK}" stroke-width="1.2"/>`;
        s += `<path d="M20 90Q60 76 100 88T200 82" stroke="${INK}" stroke-width="5" fill="none" stroke-linecap="round" opacity=".35"/><path d="M40 190Q90 176 140 190T230 178" stroke="${INK}" stroke-width="4" fill="none" stroke-linecap="round" opacity=".28"/>`;
        break;
      case "ink":
        s += `<path d="M48 196C16 112 78 28 150 42C204 54 230 112 204 178" stroke="#14100e" stroke-width="11" fill="none" stroke-linecap="round" opacity=".85"/><path d="M60 206C34 138 86 54 146 58" stroke="#14100e" stroke-width="4" fill="none" stroke-linecap="round" opacity=".5"/>`;
        for (let i = 0; i < 22; i++) s += `<circle cx="${n(R() * 240)}" cy="${n(R() * 270)}" r="${n(1 + R() * 4.5)}" fill="#14100e" opacity="${n(.35 + R() * .5)}" stroke="none"/>`;
        break;
      default: break;
    }
    return s;
  }

  /* ---------- weapons ---------- */
  function weaponBack(kind, ac) {
    const tassel = `<path d="M0 -176Q-10 -150 -4 -120M0 -176Q8 -150 6 -118" stroke="#b5342e" stroke-width="3.2" fill="none" stroke-linecap="round"/>`;
    switch (kind) {
      case "sword":
        return `<g transform="translate(178 284) rotate(14)"><rect x="-4" y="-132" width="8" height="170" fill="#4a3a30"/><rect x="-1.2" y="-132" width="2.4" height="170" fill="#8a7458" opacity=".7" stroke="none"/>` +
          `<rect x="-15" y="-138" width="30" height="7" rx="3" fill="#a77b3a"/><rect x="-3.8" y="-174" width="7.6" height="38" rx="2" fill="#2f2018"/><circle cx="0" cy="-176" r="5" fill="#6fb99a"/>${tassel}</g>`;
      case "saber":
        return `<g transform="translate(178 286) rotate(14)"><path d="M-4 -130L4 -130C12 -60 12 0 3 36L-5 36C0 -10 -2 -70 -4 -130Z" fill="#4a3a30"/><ellipse cx="0" cy="-134" rx="14" ry="6" fill="#a77b3a"/>` +
          `<rect x="-3.8" y="-176" width="7.6" height="40" rx="2" fill="#2f2018"/><path d="M0 -176Q-6 -156 -2 -140Q2 -158 6 -170Z" fill="#b5342e"/><circle cx="0" cy="-178" r="4.6" fill="#a77b3a"/></g>`;
      case "staff":
        return `<g transform="translate(34 300) rotate(-6)"><rect x="-4" y="-320" width="8" height="330" rx="4" fill="#8a5a33"/><rect x="-1" y="-320" width="2.4" height="330" fill="#d1a26a" opacity=".6" stroke="none"/>` +
          `<rect x="-6" y="-318" width="12" height="14" rx="3" fill="#a77b3a"/><path d="M4 -230Q22 -214 14 -190Q10 -210 4 -214Z" fill="#b5342e"/><rect x="-6" y="-60" width="12" height="9" rx="3" fill="#a77b3a"/></g>`;
      case "spear":
        return `<g transform="translate(192 300) rotate(5)"><rect x="-2.8" y="-286" width="5.6" height="300" rx="2.8" fill="#7a5233"/><path d="M0 -330L9 -292L0 -284L-9 -292Z" fill="#d9dde6"/>` +
          `<path d="M-8 -284Q0 -268 8 -284Q4 -252 0 -240Q-4 -252 -8 -284Z" fill="#b5342e"/></g>`;
      default: return "";
    }
  }
  function weaponFront(kind, ac) {
    switch (kind) {
      case "fan": {
        let ribs = "", d = "M0 0";
        for (let i = 0; i <= 6; i++) { const a = (-150 + i * 20) * Math.PI / 180; ribs += `<path d="M0 0L${n(Math.cos(a) * 60)} ${n(Math.sin(a) * 60)}" stroke="#6a4a24" stroke-width="1.1"/>`; d += `L${n(Math.cos(a) * 60)} ${n(Math.sin(a) * 60)}`; }
        return `<g transform="translate(184 300)"><path d="${d}Z" fill="#efe2bd" stroke="#6a4a24" stroke-width="1.6"/>${ribs}<path d="M${n(Math.cos(-2.6) * 60)} ${n(Math.sin(-2.6) * 60)}A60 60 0 0 1 ${n(Math.cos(-.52) * 60)} ${n(Math.sin(-.52) * 60)}" stroke="${ac[0]}" stroke-width="3" fill="none"/></g>`;
      }
      case "flute":
        return `<g transform="translate(96 284) rotate(-12)"><rect x="0" y="-4" width="104" height="8" rx="4" fill="#3d6a4a"/><rect x="0" y="-4" width="104" height="2.6" rx="1.3" fill="#8fc4a0" opacity=".6" stroke="none"/>` +
          [22, 36, 50, 64, 78].map(x => `<circle cx="${x}" cy="0" r="1.8" fill="#10281c" stroke="none"/>`).join("") + `<rect x="-2" y="-5" width="6" height="10" rx="2" fill="#a77b3a"/><path d="M102 2Q110 18 104 30" stroke="#b5342e" stroke-width="3" fill="none" stroke-linecap="round"/></g>`;
      case "brush":
        return `<g transform="translate(192 296) rotate(16)"><rect x="-3" y="-120" width="6" height="90" rx="3" fill="#5a3a24"/><rect x="-3.2" y="-60" width="6.4" height="5" fill="#a77b3a"/><path d="M-4 -30Q0 -4 4 -30Z" fill="#17131a"/><path d="M0 -120Q-12 -104 -6 -90" stroke="#b5342e" stroke-width="2.4" fill="none"/></g>`;
      default: return "";
    }
  }

  /* ---------- hair ---------- */
  const capBack = m => `<path d="M82 124C74 70 96 44 120 44C144 44 166 70 158 124L154 152L86 152Z" fill="${m}"/>`;
  function hairBack(style, h) {
    const m = h[0], d = h[1];
    switch (style) {
      case "long": return `<path d="M80 124C70 70 94 40 120 40C146 40 170 70 160 124C168 190 164 250 178 298L62 298C76 250 72 190 80 124Z" fill="${m}"/>` +
        strandLines(["M96 50C84 100 84 200 78 290", "M144 50C156 100 156 200 162 290", "M120 44C118 120 120 220 118 296"], h[2], 1, .3);
      case "braid": return capBack(m);
      case "ponytail": return capBack(m) + `<path d="M138 50C186 30 230 86 214 156C210 196 196 236 206 280C182 258 176 216 186 172C192 124 172 88 138 76Z" fill="${m}"/>` + strandLines(["M170 70C198 96 204 150 196 210"], h[2], 1, .35);
      case "bun": return `<ellipse cx="120" cy="46" rx="14" ry="12" fill="${m}"/>` + capBack(m);
      case "twin_buns": return `<ellipse cx="92" cy="58" rx="15" ry="13" fill="${m}"/><ellipse cx="148" cy="58" rx="15" ry="13" fill="${m}"/>` + capBack(m);
      case "wild": return `<path d="M72 138L40 92L74 98L56 38L96 66L108 16L122 56L146 14L152 62L190 34L176 96L206 90L174 140Z" fill="${m}"/>` + capBack(m);
      case "short": return capBack(m);
      default: return "";
    }
  }
  function fringe(kind, m, d) {
    switch (kind) {
      case "split":
        return `<path d="M120 48C98 50 84 70 84 108C92 92 102 84 112 78C117 70 119 60 120 48Z" fill="${m}"/><path d="M120 48C142 50 156 70 156 108C148 92 138 84 128 78C123 70 121 60 120 48Z" fill="${m}"/>`;
      case "swept":
        return `<path d="M84 112C80 72 100 48 126 48C148 48 160 68 156 112C152 92 142 80 130 76C122 90 104 100 90 108C87 110 85 111 84 112Z" fill="${m}"/>`;
      case "blunt":
        return `<path d="M84 108C80 70 100 48 120 48C140 48 160 70 156 108C152 100 150 94 148 92Q120 84 92 92C90 94 88 100 84 108Z" fill="${m}"/>`;
      case "spiky":
        return `<path d="M82 114C76 70 98 42 120 42C142 42 164 70 158 114L152 90L146 108L138 84L130 104L120 78L110 104L102 84L94 108L88 90Z" fill="${m}"/>`;
      case "knot":
        return `<path d="M86 110C84 74 100 58 120 58C140 58 156 74 154 110C150 88 138 78 120 78C102 78 90 88 86 110Z" fill="${m}"/>`;
      default: return "";
    }
  }
  const lock = (len, m) => { const l = `M86 104C82 ${n(len * .55)} 84 ${len - 28} 90 ${len}L99 ${len - 8}C96 ${len - 56} 94 140 96 110Z`; return `<path d="${l}" fill="${m}"/><path d="${mirror(l)}" fill="${m}"/>`; };
  function hairFront(style, h) {
    const m = h[0], d = h[1], l = h[2];
    const shine = `<path d="M96 66Q120 54 144 66" stroke="${l}" stroke-width="3" fill="none" opacity=".4" stroke-linecap="round"/>`;
    switch (style) {
      case "long": return fringe("split", m, d) + lock(236, m) + strandLines(["M112 56C104 70 100 82 98 96", "M128 56C136 70 140 82 142 96"], d, 1, .55) + shine;
      case "braid": return fringe("split", m, d) + lock(170, m) + braid(m, d) + shine;
      case "ponytail": return fringe("swept", m, d) + lock(160, m) + shine;
      case "bun": return fringe("knot", m, d) + lock(180, m) + strandLines(["M100 66C96 76 94 86 92 96", "M140 66C144 76 146 86 148 96"], d, 1, .6) + shine;
      case "twin_buns": return fringe("blunt", m, d) + lock(220, m) + ribbonBows() + shine;
      case "short": return fringe("spiky", m, d) + shine;
      case "wild": return fringe("spiky", m, d) + strandLines(["M70 130L50 170", "M170 130L190 170"], m, 3, .9);
      default: return "";
    }
  }
  const ribbonBows = () => `<path d="M92 70L82 64L84 76ZM92 70L102 64L100 76Z" fill="#b5342e"/><path d="M148 70L138 64L140 76ZM148 70L158 64L156 76Z" fill="#b5342e"/>`;
  function braid(m, d) {
    let s = "";
    for (let i = 0; i < 8; i++) s += `<ellipse cx="${n(78 - i * .6)}" cy="${186 + i * 14}" rx="11" ry="9.5" fill="${m}"/><path d="M${70 - i * .6} ${189 + i * 14}Q${78 - i * .6} ${182 + i * 14} ${86 - i * .6} ${189 + i * 14}" stroke="${d}" stroke-width="1.4" fill="none" opacity=".7"/>`;
    return s + `<path d="M68 296L88 296L84 306L72 306Z" fill="#b5342e"/>`;
  }

  /* ---------- body and clothing ---------- */
  function body(a, o, ac) {
    const s = a.build === "masculine" ? 88 : a.build === "feminine" ? 70 : 80, L = 120 - s, Rt = 120 + s;
    let out = "";
    if (a.outfit === "hermit") out += `<path d="M${L - 14} 300C${L - 14} 244 ${L + 6} 204 102 198L138 198C${Rt - 6} 204 ${Rt + 14} 244 ${Rt + 14} 300Z" fill="#4a4036"/>`;
    out += `<path d="M109 212C${L + 34} 214 ${L + 8} 226 ${L} 252C${L - 3} 268 ${L - 3} 284 ${L - 3} 300L${Rt + 3} 300C${Rt + 3} 284 ${Rt + 3} 268 ${Rt} 252C${Rt - 8} 226 ${Rt - 34} 214 131 212Z" fill="${o[0]}"/>`;
    out += `<path d="M${Rt - 22} 300C${Rt - 20} 266 ${Rt - 32} 242 ${Rt - 54} 228C${Rt - 16} 238 ${Rt} 262 ${Rt} 300Z" fill="${o[1]}" opacity=".4" stroke="none"/>`;
    const folds = `<path d="M${L + 14} 262C${L + 24} 276 ${L + 22} 290 ${L + 16} 300" stroke="${o[1]}" stroke-width="1.6" fill="none" opacity=".6"/><path d="M${Rt - 14} 262C${Rt - 24} 276 ${Rt - 22} 290 ${Rt - 16} 300" stroke="${o[1]}" stroke-width="1.6" fill="none" opacity=".6"/>`;
    const sash = `<path d="M${L + 2} 280Q120 292 ${Rt - 2} 280L${Rt - 2} 296Q120 308 ${L + 2} 296Z" fill="${ac[0]}"/><path d="M${L + 2} 284Q120 296 ${Rt - 2} 284" stroke="${ac[2]}" stroke-width="1.2" fill="none" opacity=".8"/>`;
    const cross = `<path d="M107 210L120 246L133 210L127 207L120 230L113 207Z" fill="#f2ecdc"/>` +
      `<path d="M103 208L112 205L120 252L110 255Z" fill="${ac[1]}"/><path d="M127 203L138 209L${L + 24} 276L${L + 14} 268Z" fill="${ac[0]}"/>`;
    switch (a.outfit) {
      case "fighter":
        out += `<path d="M96 214L110 214L${Rt - 4} 300L${Rt - 30} 300Z" fill="${ac[1]}"/><circle cx="${n(Rt - 40)}" cy="266" r="5" fill="${ac[2]}"/>`;
        out += `<path d="M${L + 4} 266C${L + 4} 240 ${L + 22} 226 ${L + 46} 222L${L + 54} 246C${L + 34} 248 ${L + 18} 256 ${L + 12} 272Z" fill="#4a3a30"/><path d="M${Rt - 4} 266C${Rt - 4} 240 ${Rt - 22} 226 ${Rt - 46} 222L${Rt - 54} 246C${Rt - 34} 248 ${Rt - 18} 256 ${Rt - 12} 272Z" fill="#4a3a30"/>`;
        out += `<circle cx="${L + 24}" cy="240" r="2.2" fill="#c9a24a"/><circle cx="${Rt - 24}" cy="240" r="2.2" fill="#c9a24a"/>`;
        out += `<path d="M101 214L103 192Q120 202 137 192L139 214Q120 224 101 214Z" fill="${o[1]}"/>` + sash;
        break;
      case "monk":
        out += `<path d="M98 208L140 208L${Rt} 258L${Rt} 300L${L} 300L${L} 250Z" fill="${ac[0]}"/><path d="M${L + 22} 300C${L + 32} 262 70 238 100 214M${L + 58} 300C${L + 64} 270 96 248 116 228M130 300C136 268 148 248 152 230" stroke="${ac[1]}" stroke-width="1.8" fill="none" opacity=".7"/>`;
        out += `<path d="M104 208L120 240L136 208Z" fill="#e7dcc4"/>`;
        for (let i = 0; i <= 11; i++) { const t = i / 11, x = (1 - t) * (1 - t) * 96 + 2 * (1 - t) * t * 120 + t * t * 144, y = (1 - t) * (1 - t) * 204 + 2 * (1 - t) * t * 272 + t * t * 204; out += `<circle cx="${n(x)}" cy="${n(y)}" r="4.2" fill="#5e3720"/>`; }
        break;
      case "hermit":
        out += `<path d="M104 208L120 246L136 208Z" fill="#d9ceb4"/><path d="M104 208L120 250M136 208L120 250" stroke="${o[1]}" stroke-width="1.8" fill="none"/>`;
        out += `<circle cx="120" cy="266" r="11" fill="#f1ecdc"/><path d="M120 255A11 11 0 0 1 120 277A5.5 5.5 0 0 1 120 266A5.5 5.5 0 0 0 120 255Z" fill="#17151a" stroke="none"/><circle cx="120" cy="260.5" r="1.6" fill="#f1ecdc" stroke="none"/><circle cx="120" cy="271.5" r="1.6" fill="#17151a" stroke="none"/>`;
        out += `<rect x="${L + 22}" y="244" width="20" height="16" rx="3" fill="#9d8c6a" transform="rotate(-8 ${L + 32} 252)"/>`;
        out += `<path d="M${L + 2} 284Q120 298 ${Rt - 2} 284" stroke="#8a6b3a" stroke-width="6" fill="none"/><path d="M122 294l-8 14M128 294l4 12" stroke="#8a6b3a" stroke-width="2.2"/>` + folds;
        break;
      case "scholar":
        out += `<path d="M105 207L113 205L116 300L103 300Z" fill="${ac[0]}"/><path d="M135 207L127 205L124 300L137 300Z" fill="${ac[0]}"/><path d="M113 207L120 232L127 207Z" fill="#f2ecdc"/>`;
        out += `<path d="M${L + 14} 300C${L + 14} 262 ${L + 28} 238 ${L + 52} 226" stroke="${ac[2]}" stroke-width="1.8" fill="none" opacity=".7"/><path d="M${Rt - 14} 300C${Rt - 14} 262 ${Rt - 28} 238 ${Rt - 52} 226" stroke="${ac[2]}" stroke-width="1.8" fill="none" opacity=".7"/>`;
        out += sash + `<path d="M120 296L120 300" stroke="#6fb99a" stroke-width="1"/><ellipse cx="136" cy="290" rx="4" ry="6" fill="#6fb99a"/>` + folds;
        break;
      case "noble":
        out += cross;
        for (let i = 0; i < 12; i++) { const x = L + 26 + (i % 6) * 26, y = 258 + Math.floor(i / 6) * 22; out += `<circle cx="${n(x)}" cy="${y}" r="5" fill="none" stroke="${ac[2]}" stroke-width="1.4" opacity=".9"/><circle cx="${n(x)}" cy="${y}" r="1.6" fill="${ac[2]}" stroke="none"/>`; }
        out += `<path d="M101 204Q120 218 139 204" stroke="${ac[2]}" stroke-width="2" fill="none"/>` + sash + `<ellipse cx="120" cy="296" rx="6" ry="4" fill="#6fb99a"/>`;
        break;
      default: // robe
        out += cross + sash + folds;
    }
    return out;
  }

  /* ---------- face ---------- */
  const faceD = build => build === "masculine" ? "M86 108C86 78 102 63 120 63C138 63 154 78 154 108L152 130C150 150 142 162 130 170L120 178L110 170C98 162 90 150 88 130Z"
    : build === "feminine" ? "M88 108C88 79 102 65 120 65C138 65 152 79 152 108C152 132 145 153 131 168Q120 180 109 168C95 153 88 132 88 108Z"
      : "M87 108C87 78 102 64 120 64C138 64 153 78 153 108C153 132 146 154 131 169Q120 179 109 169C94 154 87 132 87 108Z";

  function eye(cx, cy, side, kind, ec, build, tag) {
    const K = { sharp: [8.4, 4.6, 2.6, 1.8], soft: [7.8, 5.4, 0.8, 2.8], sleepy: [8.2, 3.4, 0, 2.2], wide: [7.8, 6.2, 0, 3.2] }[kind] || [7.8, 5.4, 0.8, 2.8];
    const [w, up, lift, lo] = K;
    const ox = cx + side * w, oy = cy - lift, ix = cx - side * w * .9, iy = cy + .6;
    const upper = `M${n(ix)} ${n(iy)}Q${n(cx)} ${n(cy - up * 2)} ${n(ox)} ${n(oy)}`;
    const white = `${upper}Q${n(cx)} ${n(cy + lo * 2)} ${n(ix)} ${n(iy)}Z`;
    let s = `<defs><clipPath id="c${tag}"><path d="${white}"/></clipPath></defs>`;
    s += `<path d="${white}" fill="#f6f1e6" stroke="none"/><g clip-path="url(#c${tag})" stroke="none"><circle cx="${n(cx - side * .4)}" cy="${n(cy - .4)}" r="${n(up * .78)}" fill="${ec}"/><circle cx="${n(cx - side * .4)}" cy="${n(cy - .4)}" r="${n(up * .4)}" fill="#0a0810"/><circle cx="${n(cx - side * 1.6)}" cy="${n(cy - up * .35)}" r="1.05" fill="#fff" opacity=".9"/><path d="M${n(cx - w)} ${n(cy - up * .6)}H${n(cx + w)}V${n(cy - up * 1.4)}H${n(cx - w)}Z" fill="#000" opacity=".22"/></g>`;
    s += `<path d="${upper}" stroke="${INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/><path d="M${n(ix)} ${n(iy)}Q${n(cx)} ${n(cy + lo * 2)} ${n(ox)} ${n(oy)}" stroke="${INK}" stroke-width=".9" fill="none" opacity=".4"/>`;
    s += `<path d="M${n(ix + side * 1)} ${n(cy - up * 1.9)}Q${n(cx)} ${n(cy - up * 2.6)} ${n(ox + side * 1.5)} ${n(oy - 3.2)}" stroke="${INK}" stroke-width=".9" fill="none" opacity=".5"/>`;   // eyelid crease
    if (build === "feminine") s += `<path d="M${n(ox)} ${n(oy)}l${n(side * 3.6)} -2.6" stroke="${INK}" stroke-width="1.8" stroke-linecap="round"/>`;
    return s;
  }
  function brow(side, kind, build, col) {
    const ix = 120 + side * 8, ox = 120 + side * 30, t = build === "masculine" ? 3.8 : build === "feminine" ? 1.7 : 2.7;
    let iy = 106, oy = 105, arch = 3;
    if (kind === "fierce") { iy = 110; oy = 101; arch = 1; }
    else if (kind === "weary") { iy = 102; oy = 108; arch = 1; }
    else if (kind === "smile") { iy = 106; oy = 104; arch = 5; }
    else if (kind === "smirk") { if (side > 0) { iy = 102; oy = 98; arch = 4; } else { iy = 107; oy = 106; arch = 2; } }
    const mx = (ix + ox) / 2, my = (iy + oy) / 2 - arch;
    return `<path d="M${ix} ${iy}Q${n(mx)} ${n(my - 1)} ${ox} ${oy}L${ox} ${n(oy + t * .35)}Q${n(mx)} ${n(my + t)} ${ix} ${n(iy + t)}Z" fill="${col}" stroke="none"/>`;
  }
  function mouth(kind, build) {
    const lip = build === "feminine" ? "#b64a52" : build === "masculine" ? "#97594f" : "#a8554f";
    const shape = {
      calm: `M112 158Q116 156 120 157Q124 156 128 158Q120 162 112 158Z`,
      smile: `M110 156Q120 164 130 156Q120 160 110 156Z`,
      smirk: `M112 159Q120 160 129 154Q121 163 112 159Z`,
      fierce: `M112 161Q120 155 128 161Q120 158 112 161Z`,
      weary: `M112 159Q120 157 128 161Q120 162 112 159Z`,
    }[kind] || `M112 158Q116 156 120 157Q124 156 128 158Q120 162 112 158Z`;
    return `<path d="${shape}" fill="${lip}" stroke="${INK}" stroke-width="1"/><path d="M116 162Q120 164 124 162" stroke="${lip}" stroke-width="1.2" fill="none" opacity=".7"/>`;
  }

  function headwear(kind, ac, o, style) {
    switch (kind) {
      case "bamboo_hat":
        return `<path d="M22 96Q120 84 218 96Q182 26 120 18Q58 26 22 96Z" fill="#d6b873"/>` +
          [-60, -40, -20, 0, 20, 40, 60].map(x => `<path d="M${120 + x * .14} 20L${120 + x * 1.7} 92" stroke="#9a7a3a" stroke-width="1" opacity=".7"/>`).join("") +
          `<path d="M22 96Q120 84 218 96" stroke="#8a6a2a" stroke-width="2.2" fill="none"/><path d="M74 92Q76 150 108 176M166 92Q164 150 132 176" stroke="${ac[0]}" stroke-width="2.4" fill="none"/><ellipse cx="120" cy="99" rx="62" ry="8" fill="#000" opacity=".18" stroke="none"/>`;
      case "scholar_cap":
        return `<path d="M88 80L152 80L150 40L90 40Z" fill="#2b2d38"/><path d="M88 80L152 80" stroke="${ac[0]}" stroke-width="3"/><path d="M92 52L148 52" stroke="#5a5d6c" stroke-width="2" opacity=".8"/><path d="M150 70L174 134L164 136L144 78Z" fill="#2b2d38"/>`;
      case "headband":
        return `<path d="M85 90Q120 82 155 90L155 99Q120 91 85 99Z" fill="${ac[0]}"/><path d="M85 90Q120 82 155 90" stroke="${ac[2]}" stroke-width="1.2" fill="none" opacity=".8"/><circle cx="120" cy="91" r="3.2" fill="#6fb99a"/><path d="M87 96L66 124L78 126L92 104Z" fill="${ac[0]}"/><path d="M89 100L72 138L84 134L96 108Z" fill="${ac[1]}"/>`;
      case "hairpin":
        return style === "bun"
          ? `<path d="M96 44L146 54" stroke="#e1b85a" stroke-width="3.2" stroke-linecap="round"/><circle cx="148" cy="54.5" r="4" fill="#b5342e"/><circle cx="94" cy="43.5" r="3" fill="#e1b85a"/><rect x="112" y="56" width="16" height="7" rx="2" fill="#e1b85a"/>`
          : `<path d="M146 62L162 46" stroke="#e1b85a" stroke-width="3" stroke-linecap="round"/><circle cx="164" cy="44" r="5" fill="#b5342e"/><path d="M160 52Q164 70 158 86M166 50Q172 66 168 82" stroke="#e1b85a" stroke-width="1.2" fill="none"/><circle cx="158" cy="88" r="2.4" fill="#6fb99a"/><circle cx="168" cy="84" r="2.4" fill="#6fb99a"/>`;
      case "flower": {
        let f = "";
        for (let i = 0; i < 5; i++) { const a = i * 72 * Math.PI / 180; f += `<circle cx="${n(154 + Math.cos(a) * 7)}" cy="${n(68 + Math.sin(a) * 7)}" r="6" fill="#e9a3ad"/>`; }
        return f + `<circle cx="154" cy="68" r="3.6" fill="#e1b85a"/><path d="M146 80Q140 86 134 82M162 80Q168 88 174 84" stroke="#4f8a63" stroke-width="3" fill="none"/>`;
      }
      default: return "";
    }
  }

  /* ---------- the whole portrait ---------- */
  function render(a, seed) {
    a = a || {};
    const R = rng(hash(seed || "jianghu"));
    const skin = pick(SKIN, a.skin, "fair"), hair = pick(HAIR, a.hair_color, "black"), out = pick(OUTFIT, a.outfit_color, "ink");
    const acc = pick(OUTFIT, a.accent_color, "gold"), ec = pick(EYE, a.eye_color, "brown");
    const build = ["feminine", "masculine", "androgynous"].includes(a.build) ? a.build : "androgynous";
    const age = ["young", "adult", "elder"].includes(a.age) ? a.age : "adult";
    const style = ["long", "ponytail", "bun", "twin_buns", "short", "wild", "braid", "bald"].includes(a.hair_style) ? a.hair_style : "short";
    const expr = ["calm", "smirk", "smile", "fierce", "weary"].includes(a.expression) ? a.expression : "calm";
    const mark = a.mark || "none", masked = mark === "mask";
    const browCol = age === "elder" ? "#cfcfd8" : hair[1];
    const ap = { ...a, build, outfit: a.outfit || "robe" };
    const paper = PAPER[a.scene] || PAPER.mountains;

    let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 300">`;
    s += `<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${paper[0]}"/><stop offset="1" stop-color="${paper[1]}"/></linearGradient>` +
      `<radialGradient id="lg"><stop offset="0" stop-color="#ffb070" stop-opacity=".55"/><stop offset="1" stop-color="#ffb070" stop-opacity="0"/></radialGradient>` +
      `<filter id="soft"><feGaussianBlur stdDeviation="5"/></filter>` +
      `<filter id="rough" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" seed="${hash(seed || "x") % 90}" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="1.8"/></filter>` +
      `<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="4" result="g"/><feColorMatrix in="g" type="matrix" values="0 0 0 0 0.35  0 0 0 0 0.25  0 0 0 0 0.15  0.9 0 0 0 -0.28"/></filter>` +
      `<radialGradient id="vg" cx=".5" cy=".46" r=".8"><stop offset=".6" stop-color="#3a2a1a" stop-opacity="0"/><stop offset="1" stop-color="#3a2a1a" stop-opacity=".38"/></radialGradient></defs>`;
    s += `<g stroke="none">${background(a.scene, R)}${aura(a.aura, R)}</g>`;
    s += `<g stroke="${INK}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" filter="url(#rough)">`;
    s += weaponBack(a.weapon, acc) + hairBack(style, hair);
    const nk = build === "masculine" ? 15 : build === "feminine" ? 10 : 12;
    s += `<path d="M${120 - nk} 164V214H${120 + nk}V164Z" fill="${skin[0]}"/><path d="M${120 - nk} 172Q120 190 ${120 + nk} 172V192Q120 204 ${120 - nk} 192Z" fill="${skin[1]}" opacity=".85" stroke="none"/>`;
    s += body(ap, out, acc);
    s += `<ellipse cx="86" cy="126" rx="5" ry="9" fill="${skin[0]}"/><ellipse cx="154" cy="126" rx="5" ry="9" fill="${skin[0]}"/>`;
    s += `<path d="${faceD(build)}" fill="${skin[0]}"/><path d="M152 112C150 140 142 160 120 178C134 168 146 152 154 126Z" fill="${skin[1]}" opacity=".55" stroke="none"/>`;
    s += `<ellipse cx="120" cy="84" rx="32" ry="11" fill="${skin[1]}" opacity=".4" stroke="none"/>`;
    if (build !== "masculine" || age === "young") s += `<ellipse cx="101" cy="142" rx="9" ry="5" fill="#e0807a" opacity=".22" stroke="none"/><ellipse cx="139" cy="142" rx="9" ry="5" fill="#e0807a" opacity=".22" stroke="none"/>`;
    s += eye(104, 118, -1, a.eyes, ec, build, "l") + eye(136, 118, 1, a.eyes, ec, build, "r");
    s += brow(-1, expr, build, browCol) + brow(1, expr, build, browCol);
    if (!masked) s += `<path d="M120 122Q119 138 114 145Q120 150 127 145" stroke="${INK}" stroke-width="1.2" fill="none" opacity=".75"/>` + mouth(expr, build);
    if (age === "elder") s += `<path d="M92 148Q96 156 94 164M148 148Q144 156 146 164M104 80Q120 77 136 80M106 86Q120 84 134 86" stroke="${skin[1]}" stroke-width="1.4" fill="none" opacity=".9"/>`;
    if (mark === "scar") s += `<path d="M92 100L112 138" stroke="#a8453f" stroke-width="2.6" stroke-linecap="round"/><path d="M98 108l7 -3M102 116l7 -3M106 124l7 -3" stroke="#a8453f" stroke-width="1.5" stroke-linecap="round"/>`;
    if (mark === "eyepatch") s += `<path d="M126 114L86 100M146 122L154 112" stroke="#15151d" stroke-width="2.2" fill="none"/><ellipse cx="136" cy="119" rx="11.5" ry="9.5" fill="#15151d"/>`;
    if (mark === "forehead_mark") s += `<path d="M120 84Q114 90 120 96Q126 90 120 84Z" fill="#c0392b"/>`;
    if (masked) s += `<path d="M87 138Q120 150 153 138L152 158Q144 184 120 188Q96 184 88 158Z" fill="${out[1]}"/><path d="M90 146Q120 158 150 146" stroke="${out[2]}" stroke-width="1.4" fill="none" opacity=".6"/><path d="M87 138L80 124M153 138L160 124" stroke="${out[1]}" stroke-width="2.4" fill="none"/>`;
    if (style === "bald") s += `<path d="M98 72Q120 62 142 72" stroke="#fff" stroke-width="3" fill="none" opacity=".4" stroke-linecap="round" stroke-opacity=".5"/>` + (ap.outfit === "monk" ? `<circle cx="112" cy="76" r="2.2" fill="#a8453f" stroke="none"/><circle cx="120" cy="73" r="2.2" fill="#a8453f" stroke="none"/><circle cx="128" cy="76" r="2.2" fill="#a8453f" stroke="none"/>` : "");
    s += hairFront(style, hair);
    if (mark === "beard") s += `<path d="M99 148Q100 184 112 204Q118 240 120 264Q122 240 128 204Q140 184 141 148Q133 164 120 164Q107 164 99 148Z" fill="${hair[0]}"/>` +
      `<path d="M104 150Q112 144 120 149Q128 144 136 150Q128 157 120 154Q112 157 104 150Z" fill="${hair[0]}"/>` + strandLines(["M112 170Q116 210 119 250", "M128 170Q124 210 121 250", "M120 172V256"], hair[2], 1, .45);
    s += headwear(a.headwear, acc, out, style) + weaponFront(a.weapon, acc);
    s += `</g>`;
    // paper grain, frame and the red seal
    s += `<rect width="240" height="300" fill="url(#vg)" stroke="none"/><rect width="240" height="300" filter="url(#grain)" opacity=".55" stroke="none"/>`;
    s += `<rect x="5" y="5" width="230" height="290" fill="none" stroke="${INK}" stroke-width="3.2"/><rect x="10" y="10" width="220" height="280" fill="none" stroke="${INK}" stroke-width=".8" opacity=".7"/>`;
    s += `<g transform="translate(17 262) rotate(-4)" stroke="none"><rect width="24" height="24" rx="2" fill="#b5342e"/><rect x="2" y="2" width="20" height="20" fill="none" stroke="#f1dcc2" stroke-width="1" opacity=".85"/><path d="M7 7H17M7 12H17M12 7V18M8 17H16" stroke="#f1dcc2" stroke-width="2" fill="none"/></g>`;
    return s + "</svg>";
  }

  window.renderPortrait = render;
})();
