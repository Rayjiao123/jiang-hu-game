/* The map of the jianghu: an ink-wash map of Song China with a red seal for each region.
 *
 *   const map = JianghuMap.build(container, regions, { onPick(id), onHover(id|null) });
 *   map.update({ counts: {huashan: 2, ...}, here: "emei" });
 *
 * Positions come from /api/world (app/world.py) on a 1000 x 640 canvas, north at the top. */
(function () {
  "use strict";

  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const rng = seed => { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; };
  const n = v => Math.round(v * 10) / 10;

  function peaks(R, x, y, count, size, op, snow) {
    let s = "";
    for (let i = 0; i < count; i++) {
      const px = x + (i - (count - 1) / 2) * size * .9 + (R() - .5) * size * .4, py = y + (R() - .5) * size * .35, w = size * (.55 + R() * .4), h = size * (.8 + R() * .7);
      s += `<path d="M${n(px - w)} ${n(py)}Q${n(px - w * .25)} ${n(py - h * .55)} ${n(px + (R() - .5) * 6)} ${n(py - h)}Q${n(px + w * .3)} ${n(py - h * .5)} ${n(px + w)} ${n(py)}Z" fill="url(#mtn)" opacity="${op}"/>`;
      s += `<path d="M${n(px + 2)} ${n(py - h * .96)}Q${n(px + w * .12)} ${n(py - h * .5)} ${n(px + w * .5)} ${n(py - h * .05)}" stroke="#46555a" stroke-width="1.1" fill="none" opacity="${op * .6}"/>`;
      s += `<path d="M${n(px - w * .5)} ${n(py - h * .3)}Q${n(px - w * .2)} ${n(py - h * .5)} ${n(px - w * .02)} ${n(py - h * .7)}" stroke="#46555a" stroke-width=".9" fill="none" opacity="${op * .4}"/>`;
      if (snow) s += `<path d="M${n(px - w * .3)} ${n(py - h * .66)}L${n(px)} ${n(py - h)}L${n(px + w * .3)} ${n(py - h * .66)}Q${n(px)} ${n(py - h * .72)} ${n(px - w * .3)} ${n(py - h * .66)}Z" fill="#fff" opacity=".9"/>`;
    }
    return s;
  }

  function terrain() {
    const R = rng(11);
    let s = `<defs>
      <linearGradient id="paper" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f6efdc"/><stop offset="1" stop-color="#e9dfc6"/></linearGradient>
      <linearGradient id="mtn" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4f6168" stop-opacity=".62"/><stop offset=".7" stop-color="#6c7f84" stop-opacity=".2"/><stop offset="1" stop-color="#9aa9a6" stop-opacity="0"/></linearGradient>
      <linearGradient id="sea" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#9ec4c8" stop-opacity=".75"/><stop offset="1" stop-color="#9ec4c8" stop-opacity="0"/></linearGradient>
      <filter id="blur8" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="8"/></filter>
      <filter id="blur2"><feGaussianBlur stdDeviation="1.6"/></filter>
      <filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" seed="5" result="g"/><feColorMatrix in="g" type="matrix" values="0 0 0 0 .45  0 0 0 0 .36  0 0 0 0 .24  .75 0 0 0 -.28"/></filter>
    </defs>`;
    s += `<rect width="1000" height="640" fill="url(#paper)"/>`;
    s += `<ellipse cx="180" cy="130" rx="190" ry="110" fill="#d9e4d2" opacity=".55" filter="url(#blur8)"/><ellipse cx="520" cy="400" rx="260" ry="150" fill="#ead7c0" opacity=".5" filter="url(#blur8)"/><ellipse cx="330" cy="560" rx="230" ry="80" fill="#d3e2d4" opacity=".45" filter="url(#blur8)"/><ellipse cx="760" cy="150" rx="200" ry="90" fill="#efe3c9" opacity=".5" filter="url(#blur8)"/>`;
    // the sea to the east
    s += `<path d="M905 -10C868 80 934 140 902 222C872 300 944 382 916 462C896 540 944 600 928 650L1010 650L1010 -10Z" fill="url(#sea)"/>`;
    for (let i = 0; i < 16; i++) { const x = 930 + R() * 60, y = 20 + R() * 600; s += `<path d="M${n(x)} ${n(y)}q10 -5 20 0t20 0" stroke="#6d9aa0" stroke-width="1.3" fill="none" opacity=".5"/>`; }
    // rivers: the Yellow River, the Yangtze and the Grand Canal
    const river = (d, w) => `<path d="${d}" stroke="#7fa6ae" stroke-width="${w + 6}" fill="none" stroke-linecap="round" opacity=".28" filter="url(#blur2)"/><path d="${d}" stroke="#5f8e98" stroke-width="${w}" fill="none" stroke-linecap="round" opacity=".75"/><path d="${d}" stroke="#d9ecee" stroke-width="${w * .35}" fill="none" stroke-linecap="round" opacity=".7"/>`;
    s += river("M40 152C190 118 276 196 384 164C478 138 548 236 646 204C726 178 806 192 906 220", 7);
    s += river("M18 362C120 332 224 384 332 352C442 322 542 392 640 374C742 356 830 410 922 424", 9);
    s += river("M764 196C742 262 772 332 794 400", 4);
    s += `<ellipse cx="796" cy="400" rx="38" ry="22" fill="#bcd9dc" opacity=".8" stroke="#6f9ca4" stroke-width="1"/><ellipse cx="790" cy="494" rx="18" ry="10" fill="#bcd9dc" opacity=".8" stroke="#6f9ca4" stroke-width="1"/><ellipse cx="170" cy="545" rx="16" ry="30" fill="#bcd9dc" opacity=".8" stroke="#6f9ca4" stroke-width="1"/>`;
    // mountains
    s += peaks(R, 160, 300, 4, 70, .8, false) + peaks(R, 250, 250, 3, 56, .6, false);       // the western highlands
    s += peaks(R, 360, 215, 3, 52, .85, false) + peaks(R, 565, 226, 3, 44, .8, false) + peaks(R, 500, 342, 3, 50, .85, false);     // Hua, Song, Wudang
    s += peaks(R, 188, 400, 3, 52, .85, true) + peaks(R, 268, 496, 2, 40, .6, false) + peaks(R, 480, 150, 3, 40, .55, false) + peaks(R, 560, 540, 4, 42, .5, false) + peaks(R, 700, 90, 3, 36, .45, false);
    s += `<ellipse cx="300" cy="420" rx="120" ry="14" fill="#fffaf0" opacity=".7" filter="url(#blur8)"/><ellipse cx="610" cy="290" rx="130" ry="12" fill="#fffaf0" opacity=".7" filter="url(#blur8)"/><ellipse cx="420" cy="110" rx="100" ry="10" fill="#fffaf0" opacity=".6" filter="url(#blur8)"/>`;
    // the Great Wall of the north, a dotted line
    s += `<path d="M300 58C400 44 520 54 640 40C730 30 810 40 880 56" stroke="#7a6a58" stroke-width="3" stroke-dasharray="9 5" fill="none" opacity=".4"/>`;
    // title and compass
    s += `<g transform="translate(34 38)"><rect x="-8" y="-24" width="232" height="62" rx="3" fill="#f6efdc" opacity=".82" stroke="#8a6a3a" stroke-width="1"/><text x="6" y="12" font-family="Ma Shan Zheng, STKaiti, serif" font-size="34" fill="#2a2118">大宋江湖图</text><text x="8" y="31" font-family="Cormorant Garamond, Georgia, serif" font-style="italic" font-size="14" fill="#6a5a44">The Jianghu of the Song</text></g>`;
    s += `<g transform="translate(70 578)" opacity=".85"><circle r="26" fill="none" stroke="#5a4a38" stroke-width="1"/><path d="M0 -34L7 0L0 34L-7 0Z" fill="#5a4a38" opacity=".7"/><path d="M-34 0L0 -6L34 0L0 6Z" fill="#5a4a38" opacity=".35"/><text y="-40" text-anchor="middle" font-family="Ma Shan Zheng, serif" font-size="20" fill="#2a2118">北</text></g>`;
    s += `<text x="930" y="330" text-anchor="middle" font-family="Ma Shan Zheng, STKaiti, serif" font-size="26" fill="#3a6a74" opacity=".55" writing-mode="tb" letter-spacing="8">东海</text>`;
    s += `<rect width="1000" height="640" filter="url(#grain)" opacity=".4"/>`;
    return s;
  }

  function marker(r) {
    const ch = esc(r.zh.charAt(0));
    return `<g class="mk" data-id="${r.id}" transform="translate(${r.x} ${r.y})" tabindex="0" role="button" aria-label="${esc(r.en)} ${esc(r.zh)}">
      <g class="pop">
        <circle class="halo" r="30" fill="#c8402f" opacity="0"/>
        <ellipse cx="2" cy="20" rx="20" ry="5" fill="#000" opacity=".12" filter="url(#blur2)"/>
        <g transform="rotate(-5)"><rect class="seal" x="-17" y="-17" width="34" height="34" rx="3" fill="#c8402f" stroke="#7a1f16" stroke-width="1.2"/><rect x="-14" y="-14" width="28" height="28" rx="1.5" fill="none" stroke="#f6e3c8" stroke-width="1" opacity=".65"/></g>
        <text class="ch" y="8" text-anchor="middle" font-family="Ma Shan Zheng, STKaiti, serif" font-size="24" fill="#fbeedd">${ch}</text>
        <g class="badge" transform="translate(16 -17)"><circle r="9" fill="#2a2118" stroke="#d8b45a" stroke-width="1.2"/><text class="cnt" y="3.6" text-anchor="middle" font-family="Noto Serif SC, serif" font-size="11" font-weight="700" fill="#f6e9c8">0</text></g>
        <text class="nm" y="36" text-anchor="middle" font-family="Ma Shan Zheng, STKaiti, serif" font-size="21" fill="#2a2118" stroke="#f6efdc" stroke-width="5" paint-order="stroke" stroke-linejoin="round">${esc(r.zh)}</text>
        <text class="en" y="51" text-anchor="middle" font-family="Cormorant Garamond, Georgia, serif" font-style="italic" font-weight="600" font-size="13.5" fill="#4a3c2c" stroke="#f6efdc" stroke-width="4" paint-order="stroke" stroke-linejoin="round">${esc(r.en)}</text>
      </g>
      <g class="flag" opacity="0"><path d="M0 -20V-62" stroke="#2a2118" stroke-width="2"/><path d="M1 -62L38 -54L1 -44Z" fill="#2a2118"/><text x="9" y="-50" font-family="Ma Shan Zheng, serif" font-size="13" fill="#f6e9c8">你</text></g>
    </g>`;
  }

  function build(container, regions, handlers) {
    handlers = handlers || {};
    container.innerHTML = `<svg viewBox="0 0 1000 640" role="group" aria-label="Map of the jianghu 江湖地图" preserveAspectRatio="xMidYMid meet">${terrain()}${regions.map(marker).join("")}</svg>`;
    const svg = container.firstElementChild, byId = Object.fromEntries(regions.map(r => [r.id, r]));
    svg.querySelectorAll(".mk").forEach(g => {
      const id = g.dataset.id;
      g.addEventListener("click", () => handlers.onPick && handlers.onPick(id));
      g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handlers.onPick && handlers.onPick(id); } });
      g.addEventListener("pointerenter", () => handlers.onHover && handlers.onHover(id));
      g.addEventListener("focus", () => handlers.onHover && handlers.onHover(id));
      g.addEventListener("pointerleave", () => handlers.onHover && handlers.onHover(null));
      g.addEventListener("blur", () => handlers.onHover && handlers.onHover(null));
    });
    return {
      update({ counts = {}, here = null } = {}) {
        svg.querySelectorAll(".mk").forEach(g => {
          const id = g.dataset.id, c = counts[id] || 0;
          g.querySelector(".cnt").textContent = c;
          g.querySelector(".badge").style.opacity = c ? 1 : .55;
          g.classList.toggle("here", id === here);
          g.querySelector(".flag").setAttribute("opacity", id === here ? 1 : 0);
          g.setAttribute("aria-label", `${byId[id].en} ${byId[id].zh}, ${c} ${c === 1 ? "person" : "people"} 人`);
        });
      },
    };
  }

  window.JianghuMap = { build };
})();
