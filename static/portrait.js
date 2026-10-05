/* Anime-style wuxia portrait builder.
 *
 *   renderPortrait(appearance, seed)  ->  SVG markup (viewBox 0 0 240 300)
 *
 * Each layer is chosen by one field of `appearance` (see APPEARANCE in app/game.py). Unknown or
 * missing values fall back to a default, so a portrait always draws. `seed` (the character's name)
 * only scatters particles and leaves, so the same character always looks the same. */
(function () {
  "use strict";

  /* ---------- palettes: [main, dark, light] ---------- */
  const OUTFIT = {
    ink: ["#2c3040", "#161924", "#555c74"], crimson: ["#bd333c", "#7c1d26", "#e8707a"],
    jade: ["#2f9a82", "#1b5e50", "#74d4ba"], azure: ["#3c72c8", "#234688", "#86b2f2"],
    violet: ["#7d58bd", "#4e3484", "#b99aeb"], gold: ["#dba72e", "#926c14", "#f5d273"],
    white: ["#ebe7dd", "#b9b3a4", "#ffffff"], ash: ["#7e848c", "#4e535b", "#b0b6be"],
  };
  const HAIR = {
    black: ["#1d1d29", "#0b0b13", "#4a4a68"], brown: ["#6e4631", "#40271a", "#a56d4a"],
    silver: ["#cdd2de", "#8c93a8", "#ffffff"], white: ["#f2f2f5", "#aeb2c0", "#ffffff"],
    red: ["#b83a2c", "#74201a", "#ee765e"], blue: ["#2f509e", "#1b2f66", "#76a0ea"],
    green: ["#2f7e5b", "#1b4c36", "#72cc9c"],
  };
  const SKIN = { fair: ["#fce8d8", "#efc4aa"], warm: ["#f3d1b0", "#e0aa86"], tan: ["#dba97c", "#bf8659"], deep: ["#ab744c", "#86552f"] };
  const EYE = {
    black: ["#20202c", "#62627f"], brown: ["#4a2a1a", "#bb7d4e"], amber: ["#8a4e08", "#ffc84f"],
    jade: ["#0f5a46", "#72e4b8"], blue: ["#173a8a", "#74b4ff"], violet: ["#4a1f8a", "#c690ff"],
    red: ["#7a1020", "#ff6e7e"],
  };
  const SCENES = {
    bamboo: ["#17352d", "#7cb89c"], mountains: ["#2b3068", "#f4b99b"], lanterns: ["#170d30", "#5e2c5a"],
    snow: ["#4f6e94", "#e8f0f8"], river: ["#11364e", "#f4c797"],
  };

  const pick = (map, key, fallback) => map[key] || map[fallback];
  const n = v => Math.round(v * 10) / 10;
  const hash = s => { let h = 2166136261; for (const c of String(s)) { h ^= c.codePointAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
  const rng = seed => { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; };
  const tongue = (bx, by, tx, ty, w, fill, op) => {
    const my = (by + ty) / 2;
    return `<path d="M${n(bx - w)} ${n(by)}Q${n((bx + tx) / 2 - w)} ${n(my)} ${n(tx)} ${n(ty)}Q${n((bx + tx) / 2 + w * 1.1)} ${n(my + 10)} ${n(bx + w)} ${n(by)}Z" fill="${fill}" opacity="${op}"/>`;
  };
  const leaf = (x, y, rot, len, fill) => `<path d="M0 0Q${n(len / 2)} ${n(-len * .3)} ${n(len)} 0Q${n(len / 2)} ${n(len * .3)} 0 0Z" transform="translate(${n(x)} ${n(y)}) rotate(${n(rot)})" fill="${fill}"/>`;
  const sparkle = (x, y, r, fill, op) => `<path d="M${n(x)} ${n(y - r)}L${n(x + r * .28)} ${n(y - r * .28)}L${n(x + r)} ${n(y)}L${n(x + r * .28)} ${n(y + r * .28)}L${n(x)} ${n(y + r)}L${n(x - r * .28)} ${n(y + r * .28)}L${n(x - r)} ${n(y)}L${n(x - r * .28)} ${n(y - r * .28)}Z" fill="${fill}" opacity="${op}"/>`;

  /* ---------- background scene ---------- */
  function stalk(x, w, col, op) {
    let s = `<g opacity="${op}"><rect x="${x}" y="0" width="${w}" height="300" fill="${col}"/>`;
    for (let y = 26 + (x * 7) % 23; y < 300; y += 52) s += `<rect x="${x - 1}" y="${y}" width="${w + 2}" height="3.5" fill="#12362a"/>`;
    return s + `<rect x="${n(x + w * .2)}" y="0" width="${n(w * .22)}" height="300" fill="#fff" opacity=".18"/></g>`;
  }
  function lantern(x, y, r) {
    return `<circle cx="${x}" cy="${y}" r="${r * 2.8}" fill="url(#lg)"/><path d="M${x} ${y - r * 1.3}V${y - r * 2.2}" stroke="#2b1621" stroke-width="1.4"/>` +
      `<rect x="${x - r * .55}" y="${n(y - r * 1.4)}" width="${n(r * 1.1)}" height="3" fill="#3a2418"/><ellipse cx="${x}" cy="${y}" rx="${r}" ry="${n(r * 1.22)}" fill="#e0453a"/>` +
      `<path d="M${x - r * .5} ${y - r}Q${x} ${y - r * 1.3} ${x + r * .5} ${y - r}" stroke="#ff9a7a" stroke-width="1.2" fill="none" opacity=".6"/>` +
      `<rect x="${x - r * .55}" y="${n(y + r * 1.2)}" width="${n(r * 1.1)}" height="3" fill="#3a2418"/><path d="M${x} ${n(y + r * 1.4)}V${n(y + r * 2.5)}" stroke="#f2c14e" stroke-width="1.6"/>`;
  }
  function background(scene, R) {
    const c = SCENES[scene] || SCENES.mountains;
    let s = `<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c[0]}"/><stop offset="1" stop-color="${c[1]}"/></linearGradient>` +
      `<radialGradient id="lg"><stop offset="0" stop-color="#ffb070" stop-opacity=".55"/><stop offset="1" stop-color="#ffb070" stop-opacity="0"/></radialGradient></defs>` +
      `<rect width="240" height="300" fill="url(#bg)"/>`;
    if (scene === "bamboo") {
      s += stalk(70, 6, "#2f7a5b", .35) + stalk(168, 7, "#2f7a5b", .4);
      [[14, 11, .95], [40, 8, .8], [196, 9, .85], [222, 12, .95]].forEach(([x, w, o]) => { s += stalk(x, w, "#2e6e52", o); });
      for (let i = 0; i < 10; i++) { const left = i % 2 === 0; s += leaf(left ? 14 + R() * 46 : 176 + R() * 50, 18 + R() * 130, (R() - .5) * 110 + (left ? 25 : 155), 16 + R() * 14, "#3f9468"); }
    } else if (scene === "lanterns") {
      s += `<path d="M-5 34Q120 72 245 28" fill="none" stroke="#2b1621" stroke-width="1.6"/>`;
      [[20, 44], [64, 56], [120, 60], [178, 52], [222, 38]].forEach(([x, y], i) => { s += lantern(x, y, 9 + (i % 2) * 2); });
      s += `<path d="M0 252L30 218L60 252ZM178 252L214 206L250 252Z" fill="#2a1233" opacity=".6"/>`;
      for (let i = 0; i < 14; i++) s += sparkle(R() * 240, 90 + R() * 160, 2 + R() * 2.5, "#ffd9a0", .5);
    } else if (scene === "snow") {
      [[28, 214, 1], [206, 200, 1.15], [70, 232, .8]].forEach(([x, y, k]) => {
        s += `<path d="M${x} ${y - 70 * k}L${x + 22 * k} ${y - 36 * k}L${x + 11 * k} ${y - 36 * k}L${x + 30 * k} ${y}L${x - 30 * k} ${y}L${x - 11 * k} ${y - 36 * k}L${x - 22 * k} ${y - 36 * k}Z" fill="#274463" opacity=".75"/>`;
      });
      s += `<path d="M0 262Q60 238 120 258T240 246V300H0Z" fill="#f4f8fc" opacity=".85"/>`;
      for (let i = 0; i < 46; i++) s += `<circle cx="${n(R() * 240)}" cy="${n(R() * 280)}" r="${n(.8 + R() * 1.9)}" fill="#fff" opacity="${n(.45 + R() * .45)}"/>`;
    } else if (scene === "river") {
      s += `<circle cx="64" cy="112" r="40" fill="#ffd9a8" opacity=".35"/><circle cx="64" cy="112" r="26" fill="#fff0cf" opacity=".95"/>`;
      s += `<path d="M0 196L40 176L84 198L130 170L176 196L240 174V300H0Z" fill="#33475f" opacity=".45"/>`;
      for (let i = 0; i < 9; i++) s += `<path d="M${n(R() * 200 - 10)} ${n(214 + i * 9)}q8 -4 16 0t16 0t16 0" stroke="#fff" stroke-width="1.4" fill="none" opacity=".3"/>`;
      s += `<path d="M186 208L214 208L208 216L192 216Z" fill="#2a2030"/><path d="M200 206V178L214 204Z" fill="#f3e6cf"/>`;
    } else { // mountains
      s += `<circle cx="168" cy="92" r="42" fill="#ffe6b8" opacity=".3"/><circle cx="168" cy="92" r="28" fill="#ffefcf" opacity=".95"/>`;
      s += `<path d="M0 190L40 138L76 172L122 118L170 178L212 138L240 172V300H0Z" fill="#5a5f98" opacity=".6"/>`;
      s += `<path d="M0 224L52 172L102 212L152 160L204 208L240 182V300H0Z" fill="#3f4482" opacity=".8"/>`;
      s += `<path d="M0 262L40 232L90 256L138 226L190 258L240 238V300H0Z" fill="#2a2d62"/>`;
    }
    return s;
  }

  /* ---------- aura: elemental effect behind the character ---------- */
  function aura(kind, R) {
    let s = "";
    switch (kind) {
      case "flame":
        s += `<defs><linearGradient id="fa" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#ffb02a"/><stop offset="1" stop-color="#ff3b2e"/></linearGradient></defs>`;
        for (let i = 0; i < 11; i++) { const bx = 14 + i * 21 + R() * 8, by = 236 + R() * 40; s += tongue(bx, by, bx + (R() - .5) * 46, by - (80 + R() * 120), 13 + R() * 9, "url(#fa)", .8); }
        for (let i = 0; i < 8; i++) { const bx = 34 + i * 25 + R() * 10, by = 250 + R() * 30; s += tongue(bx, by, bx + (R() - .5) * 30, by - (50 + R() * 70), 8 + R() * 5, "#ffd45c", .85); }
        for (let i = 0; i < 18; i++) s += sparkle(R() * 240, 30 + R() * 230, 2 + R() * 3, "#ffd45c", .8);
        break;
      case "ice":
        for (let i = 0; i < 12; i++) {
          const a = (-200 + i * 20) * Math.PI / 180, r0 = 58, r1 = 98 + R() * 46, bx = 120 + Math.cos(a) * r0, by = 150 + Math.sin(a) * r0, tx = 120 + Math.cos(a) * r1, ty = 150 + Math.sin(a) * r1, px = -Math.sin(a) * 10, py = Math.cos(a) * 10;
          s += `<path d="M${n(bx - px)} ${n(by - py)}L${n(tx)} ${n(ty)}L${n(bx + px)} ${n(by + py)}Z" fill="#bfe9ff" opacity=".78" stroke="#fff" stroke-width="1.2"/>`;
          s += `<path d="M${n(bx)} ${n(by)}L${n(tx)} ${n(ty)}L${n(bx + px)} ${n(by + py)}Z" fill="#fff" opacity=".35"/>`;
        }
        for (let i = 0; i < 16; i++) s += sparkle(R() * 240, R() * 260, 2 + R() * 3.5, "#fff", .85);
        break;
      case "wind":
        for (let i = 0; i < 7; i++) {
          const y = 40 + i * 34 + R() * 10, x = -10 + R() * 40;
          s += `<path d="M${n(x)} ${n(y)}C${n(x + 60)} ${n(y - 22)} ${n(x + 120)} ${n(y + 22)} ${n(x + 190 + R() * 40)} ${n(y - 8)}c14 -6 22 8 10 14" stroke="#fff" stroke-width="${n(2 + R() * 2)}" fill="none" stroke-linecap="round" opacity="${n(.35 + R() * .3)}"/>`;
        }
        for (let i = 0; i < 9; i++) s += leaf(R() * 240, R() * 280, R() * 360, 7 + R() * 5, "#d9f0c4");
        break;
      case "petals":
        for (let i = 0; i < 26; i++) s += `<ellipse cx="${n(R() * 240)}" cy="${n(R() * 290)}" rx="${n(4 + R() * 4)}" ry="${n(2.4 + R() * 2)}" transform="rotate(${n(R() * 360)} 120 150)" fill="${R() > .4 ? "#ffb7c9" : "#fff0f3"}" opacity="${n(.65 + R() * .3)}"/>`;
        break;
      case "lightning":
        [[30, 0], [210, 10], [120, -10]].forEach(([x, y], k) => {
          let d = `${x},${y}`, px = x, py = y; const tx = k === 2 ? 120 : (x < 120 ? 96 : 144), steps = 6;
          for (let i = 1; i <= steps; i++) { px = x + (tx - x) * i / steps + (R() - .5) * 26; py = y + (110 + R() * 40) * i / steps; d += ` ${n(px)},${n(py)}`; }
          s += `<polyline points="${d}" fill="none" stroke="#ffe85a" stroke-width="7" stroke-linejoin="round" opacity=".35"/><polyline points="${d}" fill="none" stroke="#fffbd0" stroke-width="2.6" stroke-linejoin="round"/>`;
        });
        for (let i = 0; i < 10; i++) s += sparkle(R() * 240, R() * 240, 2 + R() * 3, "#fff7a8", .9);
        break;
      case "moon":
        s += `<circle cx="120" cy="132" r="96" fill="#fff4c8" opacity=".16"/><circle cx="120" cy="132" r="76" fill="#fff4c8" opacity=".3"/><circle cx="120" cy="132" r="62" fill="#fff8dc" opacity=".55"/><circle cx="120" cy="132" r="84" fill="none" stroke="#fff8dc" stroke-width="1.6" opacity=".6"/>`;
        for (let i = 0; i < 12; i++) s += sparkle(R() * 240, R() * 200, 2 + R() * 3.5, "#fff8dc", .85);
        break;
      case "ink":
        s += `<path d="M48 196C16 112 78 28 150 42C204 54 230 112 204 178" stroke="#0e0e18" stroke-width="10" fill="none" stroke-linecap="round" opacity=".85"/><path d="M60 206C34 138 86 54 146 58" stroke="#0e0e18" stroke-width="4" fill="none" stroke-linecap="round" opacity=".5"/>`;
        for (let i = 0; i < 22; i++) s += `<circle cx="${n(R() * 240)}" cy="${n(R() * 270)}" r="${n(1 + R() * 4.5)}" fill="#0e0e18" opacity="${n(.35 + R() * .5)}"/>`;
        break;
      default: break;
    }
    return s;
  }

  /* ---------- weapons ---------- */
  function weaponBack(kind, ac) {
    const tassel = `<path d="M0 -176Q-10 -150 -4 -120M0 -176Q8 -150 6 -118" stroke="${ac[0]}" stroke-width="3.2" fill="none" stroke-linecap="round"/>`;
    switch (kind) {
      case "sword":
        return `<g transform="translate(176 282) rotate(14)"><rect x="-3.4" y="-132" width="6.8" height="170" fill="#d9dfe9"/><rect x="-1" y="-132" width="2" height="170" fill="#fff" opacity=".7"/>` +
          `<rect x="-15" y="-138" width="30" height="7" rx="3" fill="${ac[1]}"/><rect x="-3.6" y="-174" width="7.2" height="38" rx="2" fill="#3a2a24"/><circle cx="0" cy="-176" r="5" fill="${ac[0]}"/>${tassel}</g>`;
      case "saber":
        return `<g transform="translate(176 284) rotate(14)"><path d="M-4 -130L4 -130C12 -60 12 0 3 36L-5 36C0 -10 -2 -70 -4 -130Z" fill="#dfe4ee"/><ellipse cx="0" cy="-134" rx="14" ry="6" fill="${ac[1]}"/>` +
          `<rect x="-3.6" y="-176" width="7.2" height="40" rx="2" fill="#3a2a24"/><path d="M0 -176Q-6 -156 -2 -140Q2 -158 6 -170Z" fill="#cc2f2f"/><circle cx="0" cy="-178" r="4.6" fill="${ac[0]}"/></g>`;
      case "staff":
        return `<g transform="translate(34 300) rotate(-6)"><rect x="-4" y="-320" width="8" height="330" rx="4" fill="#8a5a33"/><rect x="-1" y="-320" width="2.4" height="330" fill="#d9a56a" opacity=".6"/>` +
          `<rect x="-6" y="-318" width="12" height="14" rx="3" fill="${ac[0]}"/><path d="M4 -230Q22 -214 14 -190Q10 -210 4 -214Z" fill="${ac[0]}"/><rect x="-6" y="-60" width="12" height="9" rx="3" fill="${ac[1]}"/></g>`;
      case "spear":
        return `<g transform="translate(190 300) rotate(5)"><rect x="-2.6" y="-286" width="5.2" height="300" rx="2.6" fill="#7a5233"/><path d="M0 -330L9 -292L0 -284L-9 -292Z" fill="#e3e8f2"/>` +
          `<path d="M-8 -284Q0 -268 8 -284Q4 -252 0 -240Q-4 -252 -8 -284Z" fill="#cc2f2f"/></g>`;
      default: return "";
    }
  }
  function weaponFront(kind, ac) {
    switch (kind) {
      case "fan": {
        let ribs = "", d = "M0 0";
        for (let i = 0; i <= 6; i++) { const a = (-150 + i * 20) * Math.PI / 180; ribs += `<path d="M0 0L${n(Math.cos(a) * 60)} ${n(Math.sin(a) * 60)}" stroke="#7a5a2c" stroke-width="1.2"/>`; d += `L${n(Math.cos(a) * 60)} ${n(Math.sin(a) * 60)}`; }
        return `<g transform="translate(184 300)"><path d="${d}Z" fill="${ac[2]}" opacity=".96" stroke="#7a5a2c" stroke-width="1.6"/>${ribs}<path d="M${n(Math.cos(-2.6) * 60)} ${n(Math.sin(-2.6) * 60)}A60 60 0 0 1 ${n(Math.cos(-.52) * 60)} ${n(Math.sin(-.52) * 60)}" stroke="${ac[0]}" stroke-width="3" fill="none"/></g>`;
      }
      case "flute":
        return `<g transform="translate(96 282) rotate(-12)"><rect x="0" y="-4" width="104" height="8" rx="4" fill="#2f6e4a"/><rect x="0" y="-4" width="104" height="2.6" rx="1.3" fill="#7fd0a0" opacity=".6"/>` +
          [22, 36, 50, 64, 78].map(x => `<circle cx="${x}" cy="0" r="1.8" fill="#10281c"/>`).join("") + `<rect x="-2" y="-5" width="6" height="10" rx="2" fill="${ac[0]}"/><path d="M102 2Q110 18 104 30" stroke="${ac[0]}" stroke-width="3" fill="none" stroke-linecap="round"/></g>`;
      case "brush":
        return `<g transform="translate(192 296) rotate(16)"><rect x="-3" y="-120" width="6" height="90" rx="3" fill="#5a3a24"/><rect x="-3.2" y="-60" width="6.4" height="5" fill="${ac[0]}"/><path d="M-4 -30Q0 -4 4 -30Z" fill="#17131a"/><path d="M-1 -26Q0 -14 1 -26Z" fill="#fff" opacity=".7"/><path d="M0 -120Q-12 -104 -6 -90" stroke="${ac[0]}" stroke-width="2.4" fill="none"/></g>`;
      default: return "";
    }
  }

  /* ---------- hair ---------- */
  const capBack = m => `<path d="M66 128C58 62 94 38 120 38C146 38 182 62 174 128L166 152L74 152Z" fill="${m}"/>`;
  function hairBack(style, h) {
    const m = h[0], d = h[1];
    switch (style) {
      case "long": return `<path d="M66 120C58 62 92 34 120 34C148 34 182 62 174 120C180 190 176 250 194 300L46 300C64 250 60 190 66 120Z" fill="${m}"/><path d="M150 60C166 100 168 170 164 300L194 300C176 250 180 190 174 120C172 92 164 72 150 60Z" fill="${d}" opacity=".45"/>`;
      case "braid": return capBack(m) + `<path d="M64 124C58 170 60 214 66 240L96 238C92 210 88 170 92 128Z" fill="${m}"/>`;
      case "ponytail": return capBack(m) + `<path d="M146 52C192 34 232 88 218 154C214 192 200 232 210 276C186 254 180 214 190 172C196 124 176 90 144 78Z" fill="${m}"/><path d="M202 124C212 172 202 222 208 262" stroke="${d}" stroke-width="3" fill="none" opacity=".5"/>`;
      case "bun": return `<circle cx="120" cy="34" r="18" fill="${m}"/><path d="M104 30Q120 22 136 30" stroke="${d}" stroke-width="2" fill="none" opacity=".5"/>` + capBack(m);
      case "twin_buns": return `<circle cx="76" cy="64" r="20" fill="${m}"/><circle cx="164" cy="64" r="20" fill="${m}"/>` + capBack(m);
      case "wild": return `<path d="M58 134L34 84L68 90L54 28L92 58L104 10L120 52L140 8L150 56L186 24L174 88L208 82L184 136Z" fill="${m}"/>` + capBack(m);
      case "short": return capBack(m);
      default: return "";
    }
  }
  function fringe(kind, m, d) {
    const strand = (x, y, dx, dy) => `<path d="M${x} ${y}Q${x - 3} ${y + dy * .6} ${x + dx} ${y + dy}Q${x + 8} ${y + dy * .5} ${x + 10} ${y - 2}Z" fill="${m}"/>`;
    switch (kind) {
      case "split":
        return `<path d="M120 50C98 52 76 68 74 118C84 102 92 94 102 92C110 84 116 68 120 50Z" fill="${m}"/><path d="M120 50C142 52 164 68 166 118C156 102 148 94 138 92C130 84 124 68 120 50Z" fill="${m}"/>` +
          `<path d="M100 92Q96 104 90 112" stroke="${d}" stroke-width="1.6" fill="none" opacity=".5"/><path d="M140 92Q144 104 150 112" stroke="${d}" stroke-width="1.6" fill="none" opacity=".5"/>`;
      case "swept":
        return `<path d="M74 114C70 70 96 48 124 48C152 48 168 72 166 114C160 92 148 80 134 78C124 92 106 102 88 108C82 110 78 112 74 114Z" fill="${m}"/>` + strand(98, 100, -8, 14) + strand(114, 92, -4, 14);
      case "blunt":
        return `<path d="M74 110C70 66 96 48 120 48C144 48 170 66 166 110C160 102 156 98 154 96Q120 88 86 96C84 98 80 102 74 110Z" fill="${m}"/>` +
          `<path d="M96 94L94 104M110 92L108 100M130 92L132 100M146 94L148 104" stroke="${d}" stroke-width="1.4" opacity=".5"/>`;
      case "spiky":
        return `<path d="M72 114C64 66 96 42 120 42C144 42 176 66 168 114L162 92L154 108L144 84L134 104L120 78L106 104L96 84L86 108L78 92Z" fill="${m}"/>`;
      default: return "";
    }
  }
  function hairFront(style, h) {
    const m = h[0], d = h[1], l = h[2];
    const lock = len => `<path d="M80 104C74 ${n(len * .55)} 76 ${len - 30} 84 ${len}L94 ${len - 8}C90 ${len - 60} 88 140 92 110Z" fill="${m}"/><path d="M160 104C166 ${n(len * .55)} 164 ${len - 30} 156 ${len}L146 ${len - 8}C150 ${len - 60} 152 140 148 110Z" fill="${m}"/>`;
    const shine = `<path d="M92 70Q120 52 148 70" stroke="${l}" stroke-width="3" fill="none" opacity=".4" stroke-linecap="round"/>`;
    switch (style) {
      case "long": return fringe("split", m, d) + lock(228) + shine;
      case "braid": return fringe("split", m, d) + lock(176) + braid(m, d) + shine;
      case "ponytail": case "bun": return fringe("swept", m, d) + lock(156) + shine;
      case "twin_buns": return fringe("blunt", m, d) + lock(212) + shine;
      case "short": return fringe("spiky", m, d) + shine;
      case "wild": return fringe("spiky", m, d);
      default: return "";
    }
  }
  function braid(m, d) {
    let s = "";
    for (let i = 0; i < 8; i++) s += `<ellipse cx="${n(76 - i * .6)}" cy="${200 + i * 13}" rx="11" ry="9" fill="${m}"/><path d="M${68 - i * .6} ${203 + i * 13}Q${76 - i * .6} ${197 + i * 13} ${84 - i * .6} ${203 + i * 13}" stroke="${d}" stroke-width="1.6" fill="none" opacity=".6"/>`;
    return s;
  }

  /* ---------- body and outfit ---------- */
  function body(a, o, ac) {
    const w = a.build === "masculine" ? 88 : a.build === "feminine" ? 68 : 78, L = 120 - w, Rt = 120 + w;
    let s = "";
    if (a.outfit === "hermit") s += `<path d="M${L - 16} 300C${L - 16} 244 ${L + 6} 206 100 198L140 198C${Rt - 6} 206 ${Rt + 16} 244 ${Rt + 16} 300Z" fill="#4a4036"/>`;
    s += `<path d="M${L} 300C${L} 258 ${L + 22} 228 104 212L136 212C${Rt - 22} 228 ${Rt} 258 ${Rt} 300Z" fill="${o[0]}"/>`;
    s += `<path d="M${Rt - 20} 300C${Rt - 18} 262 ${Rt - 30} 240 ${Rt - 52} 228C${Rt - 14} 236 ${Rt} 262 ${Rt} 300Z" fill="${o[1]}" opacity=".45"/>`;
    const sash = `<path d="M${L + 2} 278Q120 290 ${Rt - 2} 278L${Rt - 2} 294Q120 306 ${L + 2} 294Z" fill="${ac[0]}"/><path d="M${L + 2} 278Q120 290 ${Rt - 2} 278" stroke="${ac[2]}" stroke-width="1.6" fill="none" opacity=".7"/>`;
    switch (a.outfit) {
      case "fighter": {
        s += `<path d="M92 214L108 214L${Rt - 6} 300L${Rt - 30} 300Z" fill="${ac[1]}"/><circle cx="130" cy="262" r="5" fill="${ac[2]}"/>`;
        s += `<path d="M${L + 4} 266C${L + 4} 240 ${L + 20} 226 ${L + 44} 222L${L + 52} 246C${L + 32} 248 ${L + 18} 256 ${L + 12} 270Z" fill="${o[1]}"/><path d="M${Rt - 4} 266C${Rt - 4} 240 ${Rt - 20} 226 ${Rt - 44} 222L${Rt - 52} 246C${Rt - 32} 248 ${Rt - 18} 256 ${Rt - 12} 270Z" fill="${o[1]}"/>`;
        s += `<circle cx="${L + 24}" cy="240" r="2.4" fill="${ac[2]}"/><circle cx="${Rt - 24}" cy="240" r="2.4" fill="${ac[2]}"/>`;
        s += `<path d="M101 214L103 190Q120 200 137 190L139 214Z" fill="${o[1]}"/><path d="M103 190Q120 200 137 190" stroke="${ac[0]}" stroke-width="2.4" fill="none"/>` + sash;
        break;
      }
      case "monk": {
        s += `<path d="M96 208L140 210L${Rt} 262L${Rt} 300L${L} 300L${L} 250Z" fill="${ac[0]}"/><path d="M${L + 20} 300C${L + 30} 262 70 236 100 214M${L + 56} 300C${L + 62} 268 94 246 116 226M128 300C134 268 146 246 150 228" stroke="${ac[1]}" stroke-width="2.2" fill="none" opacity=".7"/>`;
        s += `<path d="M104 208L120 240L136 208Z" fill="#efe6d4"/>`;
        for (let i = 0; i <= 11; i++) { const t = i / 11, x = (1 - t) * (1 - t) * 96 + 2 * (1 - t) * t * 120 + t * t * 144, y = (1 - t) * (1 - t) * 204 + 2 * (1 - t) * t * 270 + t * t * 204; s += `<circle cx="${n(x)}" cy="${n(y)}" r="4.2" fill="#5e3720"/><circle cx="${n(x - 1)}" cy="${n(y - 1.2)}" r="1.1" fill="#c78a5a"/>`; }
        break;
      }
      case "hermit": {
        s += `<path d="M104 208L120 246L136 208Z" fill="#d9ceb4"/><path d="M104 208L120 246M136 208L120 246" stroke="${o[1]}" stroke-width="2" fill="none"/>`;
        s += `<rect x="${L + 22}" y="244" width="22" height="18" rx="3" fill="#9d8c6a" transform="rotate(-8 ${L + 33} 253)"/><rect x="${Rt - 52}" y="262" width="20" height="16" rx="3" fill="#9d8c6a" transform="rotate(6 ${Rt - 42} 270)"/>`;
        s += `<path d="M${L + 2} 282Q120 296 ${Rt - 2} 282" stroke="#8a6b3a" stroke-width="6" fill="none"/><path d="M122 292l-8 14M128 292l4 12" stroke="#8a6b3a" stroke-width="2.4"/>`;
        break;
      }
      default: { // robe, scholar, noble: crossed collar
        s += `<path d="M104 208L120 252L136 208Z" fill="#f4efe5"/>`;
        s += `<path d="M101 206L113 202L${Rt - 4} 300L${Rt - 28} 300Z" fill="${ac[0]}"/><path d="M139 206L127 202L113 250L125 258Z" fill="${ac[0]}"/><path d="M101 206L113 202L${Rt - 4} 300L${Rt - 8} 300L109 210Z" fill="${ac[2]}" opacity=".5"/>`;
        if (a.outfit === "noble") {
          for (let i = 0; i < 10; i++) s += `<circle cx="${n(L + 24 + (i % 5) * 28)}" cy="${n(262 + Math.floor(i / 5) * 18)}" r="3.2" fill="${ac[2]}" opacity=".85"/>`;
          s += `<path d="M${L + 4} 270H${Rt - 4}" stroke="${ac[2]}" stroke-width="1.6" opacity=".8"/>`;
        }
        if (a.outfit === "scholar") s += `<path d="M${L + 14} 300C${L + 14} 262 ${L + 28} 238 ${L + 52} 226" stroke="${ac[2]}" stroke-width="2.2" fill="none" opacity=".7"/><path d="M${Rt - 14} 300C${Rt - 14} 262 ${Rt - 28} 238 ${Rt - 52} 226" stroke="${ac[2]}" stroke-width="2.2" fill="none" opacity=".7"/>`;
        s += sash;
      }
    }
    return s;
  }

  /* ---------- face ---------- */
  const faceD = build => build === "masculine" ? "M78 112C78 76 98 62 120 62C142 62 162 76 162 112C162 146 150 176 120 185C90 176 78 146 78 112Z"
    : build === "feminine" ? "M80 112C80 78 98 64 120 64C142 64 160 78 160 112C160 140 146 169 120 181C94 169 80 140 80 112Z"
      : "M79 112C79 77 98 63 120 63C142 63 161 77 161 112C161 143 148 172 120 183C92 172 79 143 79 112Z";

  function eye(cx, cy, side, kind, ec, build, age, tag) {
    const K = { sharp: [9, 7.4, 4.6], soft: [8.6, 9.8, 0], sleepy: [9, 6.2, -1], wide: [8.4, 11.4, -1] }[kind] || [8.6, 9.8, 0];
    const w = K[0], h = K[1] + (age === "young" ? .8 : 0), tilt = K[2];
    const ox = cx + side * (w + 1.5), oy = cy - tilt * .5, ix = cx - side * (w + .5), iy = cy + tilt * .35;
    const upper = `M${n(ox)} ${n(oy)}Q${n(cx)} ${n(cy - 2 * h)} ${n(ix)} ${n(iy)}`;
    const white = `${upper}Q${n(cx)} ${n(cy + 1.25 * h)} ${n(ox)} ${n(oy)}Z`;
    let s = `<defs><clipPath id="c${tag}"><path d="${white}"/></clipPath><linearGradient id="i${tag}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${ec[0]}"/><stop offset="1" stop-color="${ec[1]}"/></linearGradient></defs>`;
    s += `<path d="${white}" fill="#fffaf4"/><g clip-path="url(#c${tag})"><ellipse cx="${n(cx)}" cy="${n(cy + .6)}" rx="${n(w * .66)}" ry="${n(h * 1.05)}" fill="url(#i${tag})"/>` +
      `<ellipse cx="${n(cx)}" cy="${n(cy + .8)}" rx="${n(w * .28)}" ry="${n(h * .58)}" fill="#12101a"/><circle cx="${n(cx - w * .24)}" cy="${n(cy - h * .36)}" r="${n(w * .23)}" fill="#fff"/><circle cx="${n(cx + w * .24)}" cy="${n(cy + h * .34)}" r="${n(w * .11)}" fill="#fff" opacity=".9"/>` +
      `<path d="M${n(cx - w)} ${n(cy - h * .2)}Q${n(cx)} ${n(cy - h * 1.2)} ${n(cx + w)} ${n(cy - h * .2)}L${n(cx + w)} ${n(cy - h * 1.2)}L${n(cx - w)} ${n(cy - h * 1.2)}Z" fill="#12101a" opacity=".22"/></g>`;
    s += `<path d="${upper}" stroke="#16121c" stroke-width="2.8" fill="none" stroke-linecap="round"/>`;
    if (build !== "masculine") s += `<path d="M${n(ox)} ${n(oy)}l${n(side * 4)} -3.2" stroke="#16121c" stroke-width="2.2" stroke-linecap="round"/>`;
    s += `<path d="M${n(ix)} ${n(iy)}Q${n(cx)} ${n(cy + 1.2 * h)} ${n(ox)} ${n(oy)}" stroke="#16121c" stroke-width="1" fill="none" opacity=".35"/>`;
    return s;
  }

  const BROWS = {
    calm: ["M89 108Q101 104 113 107", "M127 107Q139 104 151 108"],
    fierce: ["M88 103L113 111", "M152 103L127 111"],
    smirk: ["M89 108Q101 105 113 108", "M127 102Q139 98 151 103"],
    smile: ["M89 107Q101 100 113 106", "M127 106Q139 100 151 107"],
    weary: ["M88 112Q100 109 113 104", "M152 112Q140 109 127 104"],
  };
  const MOUTHS = {
    calm: `<path d="M112 160Q120 162 128 160" stroke="#9a5560" stroke-width="2" fill="none" stroke-linecap="round"/>`,
    smile: `<path d="M109 157Q120 172 131 157Q120 163 109 157Z" fill="#8a3640"/><path d="M109 157Q120 172 131 157" stroke="#7a2e38" stroke-width="1.6" fill="none"/>`,
    smirk: `<path d="M111 161Q122 163 131 155" stroke="#9a5560" stroke-width="2.2" fill="none" stroke-linecap="round"/>`,
    fierce: `<path d="M111 165Q120 157 129 165" stroke="#9a5560" stroke-width="2.2" fill="none" stroke-linecap="round"/>`,
    weary: `<path d="M112 163Q120 160 128 164" stroke="#9a5560" stroke-width="2" fill="none" stroke-linecap="round"/>`,
  };

  function headwear(kind, ac, o, hairStyle) {
    switch (kind) {
      case "bamboo_hat":
        return `<path d="M18 90Q120 76 222 90Q184 24 120 16Q56 24 18 90Z" fill="#dcb86c"/><path d="M18 90Q120 76 222 90" stroke="#9a7a3a" stroke-width="2" fill="none"/>` +
          [-52, -34, -16, 0, 16, 34, 52].map(x => `<path d="M${120 + x * .15} 18L${120 + x * 1.7} 86" stroke="#b8924a" stroke-width="1.2" opacity=".7"/>`).join("") +
          `<path d="M70 88Q72 150 106 178M170 88Q168 150 134 178" stroke="${ac[0]}" stroke-width="2.4" fill="none"/><ellipse cx="120" cy="92" rx="62" ry="8" fill="#000" opacity=".16"/>`;
      case "scholar_cap":
        return `<path d="M80 74L160 74L154 30L86 30Z" fill="${o[1]}"/><path d="M80 74L160 74" stroke="${ac[0]}" stroke-width="3"/><path d="M86 30L154 30" stroke="${o[0]}" stroke-width="3"/><path d="M152 64L176 128L166 130L146 72Z" fill="${o[1]}"/>`;
      case "headband":
        return `<path d="M76 88Q120 78 164 88L164 98Q120 88 76 98Z" fill="${ac[0]}"/><path d="M76 88Q120 78 164 88" stroke="${ac[2]}" stroke-width="1.6" fill="none" opacity=".7"/><path d="M78 94L58 120L70 122L86 102Z" fill="${ac[0]}"/><path d="M80 98L62 134L74 130L90 104Z" fill="${ac[1]}"/>`;
      case "hairpin":
        return hairStyle === "bun" || hairStyle === "twin_buns"
          ? `<path d="M96 28L146 44" stroke="#f2cf6e" stroke-width="3.4" stroke-linecap="round"/><circle cx="148" cy="45" r="4.4" fill="#d6483c"/><circle cx="94" cy="27" r="3" fill="#f2cf6e"/>`
          : `<path d="M148 60L168 40" stroke="#f2cf6e" stroke-width="3.2" stroke-linecap="round"/><circle cx="170" cy="38" r="5.4" fill="#d6483c"/><path d="M168 44Q170 62 164 74" stroke="#f2cf6e" stroke-width="1.6" fill="none"/>`;
      case "flower": {
        let f = "";
        for (let i = 0; i < 5; i++) { const a = i * 72 * Math.PI / 180; f += `<circle cx="${n(152 + Math.cos(a) * 7)}" cy="${n(66 + Math.sin(a) * 7)}" r="6.2" fill="#ffb7c9"/>`; }
        return f + `<circle cx="152" cy="66" r="4" fill="#ffd45c"/><circle cx="166" cy="80" r="4" fill="#ffb7c9"/><circle cx="166" cy="80" r="1.8" fill="#ffd45c"/>`;
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
    const expr = BROWS[a.expression] ? a.expression : "calm";
    const mark = a.mark || "none", masked = mark === "mask";
    const browCol = age === "elder" ? "#dcdce6" : hair[1];
    const brow = BROWS[expr].map(d => `<path d="${d}" stroke="${browCol}" stroke-width="${build === "masculine" ? 3.4 : 2.4}" fill="none" stroke-linecap="round"/>`).join("");
    const ap = { ...a, build, outfit: a.outfit || "robe" };

    let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 300">`;
    s += background(a.scene, R) + aura(a.aura, R) + weaponBack(a.weapon, acc) + hairBack(style, hair);
    s += `<path d="M106 168V212H134V168Z" fill="${skin[0]}"/><path d="M106 186Q120 200 134 186V200Q120 214 106 200Z" fill="${skin[1]}" opacity=".7"/>`;
    s += body(ap, out, acc);
    s += `<ellipse cx="78" cy="128" rx="6.5" ry="10" fill="${skin[0]}"/><ellipse cx="162" cy="128" rx="6.5" ry="10" fill="${skin[0]}"/>`;
    s += `<path d="${faceD(build)}" fill="${skin[0]}"/><path d="M120 183C146 172 160 143 161 112C156 150 142 170 120 176Z" fill="${skin[1]}" opacity=".5"/>`;
    s += `<ellipse cx="94" cy="148" rx="9" ry="5" fill="#ff8f8f" opacity="${age === "young" || build === "feminine" ? .3 : .15}"/><ellipse cx="146" cy="148" rx="9" ry="5" fill="#ff8f8f" opacity="${age === "young" || build === "feminine" ? .3 : .15}"/>`;
    s += eye(101, 124, -1, a.eyes, ec, build, age, "l") + eye(139, 124, 1, a.eyes, ec, build, age, "r") + brow;
    if (!masked) s += `<path d="M120 140L118 148Q120 150.5 123 148" stroke="${skin[1]}" stroke-width="1.8" fill="none" stroke-linecap="round"/>` + MOUTHS[expr];
    if (age === "elder") s += `<path d="M92 150Q95 156 93 163M148 150Q145 156 147 163M106 80Q120 78 134 80" stroke="${skin[1]}" stroke-width="1.5" fill="none" opacity=".8"/>`;
    if (mark === "scar") s += `<path d="M90 104L110 142" stroke="#b9525c" stroke-width="2.6" stroke-linecap="round"/><path d="M96 112l7 -3M100 120l7 -3M104 128l7 -3" stroke="#b9525c" stroke-width="1.6" stroke-linecap="round"/>`;
    if (mark === "eyepatch") s += `<path d="M126 118L80 104M150 126L162 118" stroke="#15151d" stroke-width="2.4" fill="none"/><ellipse cx="139" cy="125" rx="12.5" ry="10.5" fill="#15151d"/>`;
    if (mark === "forehead_mark") s += `<path d="M120 86Q114 92 120 98Q126 92 120 86Z" fill="#d6393a"/>`;
    if (masked) s += `<path d="M81 142Q120 152 159 142L157 162Q148 186 120 190Q92 186 83 162Z" fill="${out[1]}"/><path d="M84 150Q120 160 156 150" stroke="${out[2]}" stroke-width="1.6" fill="none" opacity=".6"/><path d="M120 158V186" stroke="${out[0]}" stroke-width="1.6" opacity=".5"/>`;
    if (style === "bald") s += `<path d="M96 76Q120 62 144 76" stroke="#fff" stroke-width="3" fill="none" opacity=".35" stroke-linecap="round"/>` + (ap.outfit === "monk" ? `<circle cx="112" cy="75" r="2.2" fill="#a8564a"/><circle cx="120" cy="72" r="2.2" fill="#a8564a"/><circle cx="128" cy="75" r="2.2" fill="#a8564a"/>` : "");
    s += hairFront(style, hair);
    if (mark === "beard") s += `<path d="M98 166Q102 202 120 216Q138 202 142 166Q132 178 120 178Q108 178 98 166Z" fill="${hair[0]}"/><path d="M104 170Q120 182 136 170" stroke="${hair[2]}" stroke-width="1.6" fill="none" opacity=".4"/>`;
    s += headwear(a.headwear, acc, out, style) + weaponFront(a.weapon, acc);
    s += `<defs><radialGradient id="vg" cx=".5" cy=".45" r=".78"><stop offset=".62" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".42"/></radialGradient></defs><rect width="240" height="300" fill="url(#vg)"/>`;
    return s + "</svg>";
  }

  window.renderPortrait = render;
})();
