/* Painted backdrops for the places of the jianghu, in a soft misty ink-wash style.
 *
 *   const handle = Scenes.paint(canvas, "huashan");   handle.stop();
 *
 * The scene is drawn once into two offscreen layers (far and near) and each frame only draws
 * those, drifting mist between them, and a few falling particles. It pauses when off screen
 * and stays still for visitors who prefer reduced motion. */
(function () {
  "use strict";

  const n = v => Math.round(v * 10) / 10;
  const rng = seed => { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; };
  const hash = s => { let h = 2166136261; for (const c of String(s)) { h ^= c.codePointAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };

  // sky top/bottom, ink tone, sun [x, y, radius, colour], ridges [baseline, height, strength], water line, particles
  const K = {
    linan:    { sky: ["#f4d6cb", "#fcf0e2"], ink: "#6b5566", sun: [.8, .27, .06, "#d9503a"], ridges: [[.62, .09, .22], [.72, .07, .32]], p: "petal" },
    westlake: { sky: ["#edf3ee", "#faf6ea"], ink: "#5f7a78", sun: [.22, .24, .05, "#e07a5a"], ridges: [[.54, .17, .26], [.6, .11, .38]], water: .66, p: "petal" },
    canal:    { sky: ["#f6efe0", "#eaf1ea"], ink: "#667c7c", sun: [.7, .22, .055, "#d9503a"], ridges: [[.56, .11, .24]], water: .7, p: "leaf" },
    yangtze:  { sky: ["#f7eadb", "#f0e7d7"], ink: "#6a6a68", sun: [.5, .3, .07, "#d9503a"], ridges: [[.5, .26, .3], [.6, .16, .42]], water: .68, p: "none" },
    taihu:    { sky: ["#eaf1f4", "#f6f4ec"], ink: "#6a8286", sun: [.3, .26, .05, "#e07a5a"], ridges: [[.6, .05, .2]], water: .6, p: "none" },
    huashan:  { sky: ["#f6ecd2", "#fbf6e8"], ink: "#5a6066", sun: [.78, .22, .06, "#d9503a"], ridges: [[.62, .17, .26]], p: "none" },
    wudang:   { sky: ["#e8f0e6", "#f6f6ea"], ink: "#4f7266", sun: [.2, .24, .05, "#e08a5a"], ridges: [[.52, .19, .3], [.64, .13, .42]], p: "leaf" },
    emei:     { sky: ["#e7eef5", "#f5f7f9"], ink: "#7a8ea2", sun: [.76, .26, .05, "#f2c28a"], ridges: [[.54, .2, .3], [.64, .13, .4]], p: "snow" },
    shaolin:  { sky: ["#f3e3c4", "#f8f0dc"], ink: "#6c5a46", sun: [.74, .26, .06, "#d9503a"], ridges: [[.62, .13, .26]], p: "autumn" },
    shu:      { sky: ["#eaf2dc", "#f4f6e6"], ink: "#55785f", sun: null, ridges: [[.62, .15, .28]], p: "leaf" },
    dali:     { sky: ["#e3eef6", "#f4f6f2"], ink: "#5f7e96", sun: [.8, .24, .05, "#f0b890"], ridges: [[.5, .22, .32], [.62, .13, .4]], water: .72, p: "petal" },
    inn:      { sky: ["#f2d2a4", "#f8e6c6"], ink: "#8a6a45", sun: [.24, .34, .09, "#d9603a"], ridges: [[.66, .1, .22], [.76, .08, .3]], p: "dust" },
    border:   { sky: ["#ead9cb", "#f3ebe2"], ink: "#6d5f58", sun: [.7, .3, .07, "#c9553a"], ridges: [[.68, .06, .2]], p: "dust" },
  };

  /* ---------- shapes ---------- */
  function ridge(ctx, W, H, R, base, amp, color, strength, bottom) {
    const pts = [];
    for (let x = -20; x <= W + 60; x += W / 9) pts.push([x, H * base - R() * H * amp]);
    ctx.beginPath(); ctx.moveTo(-20, H);
    ctx.lineTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) { const [px, py] = pts[i - 1], [x, y] = pts[i]; ctx.quadraticCurveTo((px + x) / 2, Math.min(py, y) - H * amp * .35, x, y); }
    ctx.lineTo(W + 60, H); ctx.closePath();
    const top = Math.min(...pts.map(p => p[1]));
    const g = ctx.createLinearGradient(0, top, 0, H * (base + .16));
    g.addColorStop(0, hexA(color, strength)); g.addColorStop(.6, hexA(color, strength * .35)); g.addColorStop(1, hexA(bottom, 0));
    ctx.fillStyle = g; ctx.fill();
  }
  function hexA(hex, a) { const v = parseInt(hex.slice(1), 16); return `rgba(${v >> 16},${v >> 8 & 255},${v & 255},${a})`; }

  function spire(ctx, R, x, base, w, h, color, a) {
    const g = ctx.createLinearGradient(0, base - h, 0, base);
    g.addColorStop(0, hexA(color, a)); g.addColorStop(1, hexA(color, 0));
    ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x - w / 2, base);
    const steps = 7;
    for (let i = 1; i <= steps; i++) { const t = i / steps; ctx.lineTo(x - w / 2 * (1 - t) - (R() - .5) * w * .18, base - h * t * (1 - (1 - t) * (1 - t) * .05)); }
    ctx.lineTo(x, base - h);
    for (let i = steps; i >= 1; i--) { const t = i / steps; ctx.lineTo(x + w / 2 * (1 - t) + (R() - .5) * w * .18, base - h * t); }
    ctx.lineTo(x + w / 2, base); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = hexA(color, a * .5); ctx.lineWidth = 1.2;
    for (let i = 0; i < 5; i++) { const t = .2 + i * .15; ctx.beginPath(); ctx.moveTo(x - w * .1 * (1 - t) + (R() - .5) * 8, base - h * t); ctx.lineTo(x + w * .16 * (1 - t) + (R() - .5) * 8, base - h * t - 10 - R() * 14); ctx.stroke(); }
  }
  function pine(ctx, x, y, k, col, a) {
    ctx.save(); ctx.fillStyle = hexA(col, a);
    ctx.fillRect(x - 1.8 * k, y - 46 * k, 3.6 * k, 48 * k);
    for (let i = 0; i < 4; i++) { const yy = y - (12 + i * 15) * k, w = (24 - i * 4.4) * k; ctx.beginPath(); ctx.moveTo(x - w, yy); ctx.quadraticCurveTo(x, yy - 17 * k, x + w, yy); ctx.quadraticCurveTo(x, yy - 5 * k, x - w, yy); ctx.fill(); }
    ctx.restore();
  }
  function pagoda(ctx, x, y, k, col, a, tiers = 5) {
    ctx.save(); ctx.fillStyle = hexA(col, a);
    for (let i = 0; i < tiers; i++) {
      const w = (32 - i * 4) * k, h = 11 * k, yy = y - i * (h + 5 * k);
      ctx.fillRect(x - (w - 9 * k) / 2, yy - h, w - 9 * k, h);
      ctx.beginPath(); ctx.moveTo(x - w / 2 - 7 * k, yy - h + 3 * k);
      ctx.quadraticCurveTo(x - w / 2, yy - h - 1 * k, x, yy - h - 8 * k); ctx.quadraticCurveTo(x + w / 2, yy - h - 1 * k, x + w / 2 + 7 * k, yy - h + 3 * k);
      ctx.lineTo(x + w / 2 - 2 * k, yy - h + 5 * k); ctx.lineTo(x - w / 2 + 2 * k, yy - h + 5 * k); ctx.closePath(); ctx.fill();
    }
    const top = y - tiers * 16 * k - 6 * k;
    ctx.fillRect(x - 1 * k, top - 16 * k, 2 * k, 16 * k); ctx.restore();
  }
  function hall(ctx, x, y, k, col, a, roof) {
    ctx.save(); ctx.fillStyle = hexA(col, a);
    const w = 100 * k, h = 24 * k;
    ctx.fillRect(x - w * .36, y - h, w * .72, h);
    for (let i = 0; i < 5; i++) { ctx.fillStyle = hexA(col, a * .55); ctx.fillRect(x - w * .33 + i * w * .165, y - h + 3 * k, 2.4 * k, h - 3 * k); }
    ctx.fillStyle = hexA(roof || col, a);
    ctx.beginPath(); ctx.moveTo(x - w / 2 - 12 * k, y - h + 6 * k); ctx.quadraticCurveTo(x - w * .3, y - h - 2 * k, x - w * .16, y - h - 20 * k); ctx.lineTo(x + w * .16, y - h - 20 * k);
    ctx.quadraticCurveTo(x + w * .3, y - h - 2 * k, x + w / 2 + 12 * k, y - h + 6 * k); ctx.lineTo(x + w / 2 - 4 * k, y - h + 10 * k); ctx.lineTo(x - w / 2 + 4 * k, y - h + 10 * k); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x - w * .3, y - h - 16 * k); ctx.quadraticCurveTo(x - w * .16, y - h - 22 * k, x, y - h - 40 * k); ctx.quadraticCurveTo(x + w * .16, y - h - 22 * k, x + w * .3, y - h - 16 * k); ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  function willow(ctx, R, x, y, k, a) {
    ctx.save(); ctx.strokeStyle = hexA("#3a3a2c", a); ctx.lineWidth = 5 * k; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x - 8 * k, y - 60 * k, x + 14 * k, y - 120 * k); ctx.stroke();
    for (let i = 0; i < 26; i++) {
      const sx = x + 14 * k + (R() - .5) * 120 * k, sy = y - 112 * k + R() * 24 * k, len = (70 + R() * 90) * k, dx = (R() - .5) * 18 * k;
      ctx.strokeStyle = hexA(R() > .4 ? "#6f9a5a" : "#8cb06a", a * .9); ctx.lineWidth = 1.3 * k;
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.quadraticCurveTo(sx + dx, sy + len * .55, sx + dx * 1.5, sy + len); ctx.stroke();
    }
    ctx.restore();
  }
  function boat(ctx, x, y, k, col, a, sail) {
    ctx.save(); ctx.fillStyle = hexA(col, a);
    ctx.beginPath(); ctx.moveTo(x - 36 * k, y - 6 * k); ctx.quadraticCurveTo(x, y + 8 * k, x + 36 * k, y - 8 * k); ctx.lineTo(x + 28 * k, y + 3 * k); ctx.quadraticCurveTo(x, y + 12 * k, x - 28 * k, y + 3 * k); ctx.closePath(); ctx.fill();
    if (sail) { ctx.fillStyle = "rgba(250,240,220,.92)"; ctx.beginPath(); ctx.moveTo(x - 2 * k, y - 8 * k); ctx.lineTo(x - 2 * k, y - 54 * k); ctx.quadraticCurveTo(x + 30 * k, y - 36 * k, x + 28 * k, y - 10 * k); ctx.closePath(); ctx.fill(); ctx.fillStyle = hexA(col, a); ctx.fillRect(x - 3 * k, y - 56 * k, 2 * k, 50 * k); }
    else { ctx.beginPath(); ctx.moveTo(x - 14 * k, y - 8 * k); ctx.quadraticCurveTo(x, y - 30 * k, x + 18 * k, y - 8 * k); ctx.fill(); }
    ctx.fillStyle = "rgba(217,80,58,.9)"; ctx.beginPath(); ctx.arc(x + 30 * k, y - 12 * k, 3 * k, 0, 6.29); ctx.fill();
    ctx.restore();
  }
  function bridge(ctx, x, y, w, k, col, a) {
    ctx.save(); ctx.fillStyle = hexA(col, a);
    ctx.beginPath(); ctx.moveTo(x - w / 2, y); ctx.quadraticCurveTo(x, y - w * .3, x + w / 2, y); ctx.lineTo(x + w / 2, y + 9 * k); ctx.quadraticCurveTo(x, y - w * .3 + 9 * k, x - w / 2, y + 9 * k); ctx.closePath(); ctx.fill();
    ctx.fillRect(x - w / 2, y, 8 * k, 26 * k); ctx.fillRect(x + w / 2 - 8 * k, y, 8 * k, 26 * k);
    ctx.strokeStyle = hexA(col, a * .9); ctx.lineWidth = 6 * k; ctx.beginPath(); ctx.arc(x, y + 24 * k, w * .3, Math.PI * 1.08, Math.PI * 1.92); ctx.stroke();
    ctx.restore();
  }
  function tower(ctx, x, y, k, col, a) {
    ctx.save(); ctx.fillStyle = hexA(col, a); ctx.strokeStyle = hexA(col, a); ctx.lineWidth = 3 * k;
    ctx.beginPath(); ctx.moveTo(x - 14 * k, y); ctx.lineTo(x - 8 * k, y - 60 * k); ctx.moveTo(x + 14 * k, y); ctx.lineTo(x + 8 * k, y - 60 * k); ctx.moveTo(x - 12 * k, y - 22 * k); ctx.lineTo(x + 8 * k, y - 50 * k); ctx.moveTo(x + 12 * k, y - 22 * k); ctx.lineTo(x - 8 * k, y - 50 * k); ctx.stroke();
    ctx.fillRect(x - 17 * k, y - 66 * k, 34 * k, 6 * k); ctx.fillRect(x - 12 * k, y - 90 * k, 24 * k, 24 * k);
    ctx.beginPath(); ctx.moveTo(x - 20 * k, y - 88 * k); ctx.lineTo(x, y - 108 * k); ctx.lineTo(x + 20 * k, y - 88 * k); ctx.closePath(); ctx.fill();
    ctx.fillRect(x + 14 * k, y - 120 * k, 2 * k, 30 * k); ctx.fillStyle = "rgba(200,64,47,.85)"; ctx.beginPath(); ctx.moveTo(x + 16 * k, y - 120 * k); ctx.lineTo(x + 42 * k, y - 112 * k); ctx.lineTo(x + 16 * k, y - 102 * k); ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  function stalk(ctx, x, w, col, a) {
    const H = ctx.canvas.height;
    ctx.fillStyle = hexA(col, a); ctx.fillRect(x, -4, w, H + 8);
    ctx.fillStyle = hexA("#2f5240", a * .8); for (let y = 30 + (x * 7) % 40; y < H; y += 54 + (x % 13)) ctx.fillRect(x - 1, y, w + 2, 3);
    ctx.fillStyle = "rgba(255,255,255,.28)"; ctx.fillRect(x + w * .2, -4, w * .2, H + 8);
  }
  function leaf(ctx, x, y, rot, len, col, a) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.fillStyle = hexA(col, a);
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.quadraticCurveTo(len / 2, -len * .22, len, 0); ctx.quadraticCurveTo(len / 2, len * .22, 0, 0); ctx.fill(); ctx.restore();
  }
  function roofs(ctx, R, x0, x1, y, k, col, a) {
    ctx.save(); ctx.fillStyle = hexA(col, a);
    for (let x = x0; x < x1; x += (30 + R() * 20) * k) {
      const w = (26 + R() * 18) * k, h = (14 + R() * 8) * k;
      ctx.fillRect(x - w * .4, y - h * .5, w * .8, h * .5 + 4 * k);
      ctx.beginPath(); ctx.moveTo(x - w * .6, y - h * .4); ctx.quadraticCurveTo(x - w * .3, y - h * .6, x, y - h * 1.3); ctx.quadraticCurveTo(x + w * .3, y - h * .6, x + w * .6, y - h * .4); ctx.lineTo(x + w * .45, y - h * .2); ctx.lineTo(x - w * .45, y - h * .2); ctx.closePath(); ctx.fill();
    }
    ctx.restore();
  }
  function lanternLine(ctx, W, y, k) {
    ctx.strokeStyle = "rgba(60,36,24,.7)"; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(-10, y); ctx.quadraticCurveTo(W / 2, y + 44 * k, W + 10, y - 6 * k); ctx.stroke();
    for (let i = 1; i <= 6; i++) {
      const t = i / 7, x = W * t, yy = y + 44 * k * 2 * t * (1 - t) - 6 * k * t, r = 9 * k;
      const g = ctx.createRadialGradient(x, yy + 14 * k, 0, x, yy + 14 * k, r * 3.4); g.addColorStop(0, "rgba(255,170,100,.55)"); g.addColorStop(1, "rgba(255,170,100,0)");
      ctx.fillStyle = g; ctx.fillRect(x - r * 3.4, yy - r * 2, r * 6.8, r * 6.8);
      ctx.fillStyle = "#d9503a"; ctx.beginPath(); ctx.ellipse(x, yy + 14 * k, r, r * 1.2, 0, 0, 6.29); ctx.fill();
      ctx.fillStyle = "rgba(255,200,170,.6)"; ctx.beginPath(); ctx.ellipse(x - r * .3, yy + 11 * k, r * .3, r * .5, 0, 0, 6.29); ctx.fill();
      ctx.fillStyle = "#5a3a22"; ctx.fillRect(x - r * .5, yy + 14 * k - r * 1.35, r, 3); ctx.fillRect(x - r * .5, yy + 14 * k + r * 1.15, r, 3);
    }
  }
  function island(ctx, R, x, y, w, col, a) {
    ctx.fillStyle = hexA(col, a); ctx.beginPath(); ctx.ellipse(x, y, w, w * .16, 0, Math.PI, 0); ctx.fill();
    for (let i = 0; i < 3; i++) pine(ctx, x + (R() - .5) * w * 1.2, y, .45 + R() * .3, "#3d5a50", a);
  }
  function water(ctx, W, H, R, y, tint) {
    const g = ctx.createLinearGradient(0, y, 0, H); g.addColorStop(0, hexA(tint, .5)); g.addColorStop(1, hexA(tint, .22));
    ctx.fillStyle = g; ctx.fillRect(0, y, W, H - y);
    ctx.strokeStyle = "rgba(255,255,255,.55)"; ctx.lineWidth = 1.3;
    for (let i = 0; i < 28; i++) { const x = R() * W, yy = y + 8 + R() * (H - y - 8), l = 18 + R() * 40; ctx.beginPath(); ctx.moveTo(x, yy); ctx.quadraticCurveTo(x + l / 4, yy - 3, x + l / 2, yy); ctx.quadraticCurveTo(x + l * .75, yy + 3, x + l, yy); ctx.stroke(); }
  }

  /* ---------- the scenes ---------- */
  const NEAR = {
    linan(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      roofs(c, R, -10, W + 20, H * .66, k * 1.1, "#5a4658", .55); pagoda(c, W * .2, H * .64, k * 1.2, "#4e3e52", .75, 6); pagoda(c, W * .62, H * .64, k, "#4e3e52", .7, 5);
      c.fillStyle = "rgba(90,70,86,.6)"; c.fillRect(0, H * .66, W, 10 * k); for (let x = 0; x < W; x += 14 * k) c.fillRect(x, H * .66 - 6 * k, 8 * k, 6 * k);
      hall(c, W * .42, H * .66, k * 1.1, "#4a3a4e", .8, "#3c2e42"); lanternLine(c, W, H * .1, k * 1.4);
    },
    westlake(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      pagoda(c, W * .18, H * .56, k * 1.3, "#5a6a62", .55, 5); willow(c, R, W * .08, H * .66, k * 1.7, .8); willow(c, R, W * .93, H * .68, k * 1.5, .8);
      boat(c, W * .56, H * .78, k * 1.5, "#3e3a34", .85, false); boat(c, W * .36, H * .86, k * 1, "#3e3a34", .6, false);
    },
    canal(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      bridge(c, W * .62, H * .7, W * .3, k * 1.2, "#4a4a44", .85); boat(c, W * .28, H * .84, k * 1.5, "#3e3a34", .9, true); willow(c, R, W * .93, H * .72, k * 1.6, .8);
      roofs(c, R, -10, W * .3, H * .62, k, "#5a5a52", .5);
    },
    yangtze(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      boat(c, W * .5, H * .82, k * 1.7, "#3e3a34", .9, true); boat(c, W * .78, H * .74, k * .9, "#3e3a34", .6, true); pine(c, W * .08, H * .66, k * 1.4, "#3d4a44", .8); pine(c, W * .94, H * .66, k * 1.2, "#3d4a44", .8);
    },
    taihu(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      island(c, R, W * .24, H * .6, W * .12, "#4e6a66", .75); island(c, R, W * .7, H * .58, W * .16, "#4e6a66", .6); island(c, R, W * .5, H * .64, W * .07, "#4e6a66", .5);
      boat(c, W * .4, H * .82, k * 1.3, "#3e3a34", .85, true); boat(c, W * .72, H * .88, k * 1.7, "#3e3a34", .9, false);
    },
    huashan(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      spire(c, R, W * .22, H * .75, W * .22, H * .6, "#4c5258", .75); spire(c, R, W * .52, H * .78, W * .18, H * .5, "#555b62", .6); spire(c, R, W * .82, H * .76, W * .24, H * .64, "#4c5258", .78);
      pine(c, W * .2, H * .36, k * 1.2, "#2d3a34", .85); pine(c, W * .8, H * .34, k * 1.4, "#2d3a34", .85); pine(c, W * .5, H * .52, k, "#2d3a34", .7);
    },
    wudang(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      hall(c, W * .64, H * .52, k * 1.5, "#3f4e48", .85, "#b08a3a"); hall(c, W * .34, H * .62, k * 1, "#46564f", .6, "#8a7a4a");
      pine(c, W * .1, H * .66, k * 1.5, "#2f4a40", .85); pine(c, W * .9, H * .7, k * 1.6, "#2f4a40", .85); pine(c, W * .78, H * .66, k, "#2f4a40", .7);
    },
    emei(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      hall(c, W * .62, H * .6, k * 1.4, "#55606e", .85, "#a0463a"); pagoda(c, W * .3, H * .64, k, "#55606e", .6, 4);
      pine(c, W * .1, H * .7, k * 1.5, "#3a4e52", .85); pine(c, W * .92, H * .72, k * 1.3, "#3a4e52", .85);
      c.fillStyle = "rgba(255,255,255,.85)"; c.beginPath(); c.moveTo(0, H * .8); c.quadraticCurveTo(W * .3, H * .72, W * .6, H * .8); c.quadraticCurveTo(W * .85, H * .86, W, H * .78); c.lineTo(W, H); c.lineTo(0, H); c.fill();
    },
    shaolin(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      hall(c, W * .66, H * .62, k * 1.6, "#5a4a3a", .85, "#4a3a2c");
      for (let i = 0; i < 6; i++) pagoda(c, W * (.1 + i * .075) + R() * 14, H * (.68 + (i % 2) * .03), k * (.6 + R() * .4), "#6a5a46", .6, 3 + (i % 3));
      for (let i = 0; i < 4; i++) {
        const tx = W * (.76 + i * .07) + R() * 10, ty = H * .7;
        c.fillStyle = "rgba(70,52,40,.7)"; c.fillRect(tx - 2 * k, ty - 46 * k, 4 * k, 50 * k);
        for (let j = 0; j < 7; j++) { c.fillStyle = hexA(["#d9803a", "#c8602f", "#e0a040"][(i + j) % 3], .5); c.beginPath(); c.arc(tx + (R() - .5) * 46 * k, ty - 56 * k + (R() - .5) * 34 * k, (11 + R() * 10) * k, 0, 6.29); c.fill(); }
      }
    },
    shu(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      for (let i = 0; i < 18; i++) stalk(c, R() * W, (6 + R() * 12) * k * 1.4, "#5f8a6c", .3 + R() * .55);
      for (let i = 0; i < 46; i++) leaf(c, R() * W, R() * H * .7, R() * 6.28, (18 + R() * 24) * k, R() > .5 ? "#5f9a74" : "#7ab08a", .5 + R() * .3);
    },
    dali(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      pagoda(c, W * .3, H * .66, k * 1.7, "#8e9aa4", .85, 6); pagoda(c, W * .44, H * .67, k * 1.2, "#9aa6ae", .8, 5); pagoda(c, W * .18, H * .67, k * 1.2, "#9aa6ae", .8, 5);
      c.strokeStyle = "rgba(90,100,110,.45)"; c.lineWidth = 1.2; for (const px of [.3, .44, .18]) { c.beginPath(); c.moveTo(W * px - 20 * k, H * .66); c.lineTo(W * px + 20 * k, H * .66); c.stroke(); }
      boat(c, W * .68, H * .84, k * 1.3, "#3e3a34", .85, true);
    },
    inn(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      hall(c, W * .62, H * .66, k * 2, "#4a3626", .92, "#6a4630");
      c.fillStyle = "rgba(60,40,26,.9)"; c.fillRect(W * .62 + 78 * k, H * .66 - 150 * k, 3 * k, 120 * k);      // the flag on its pole
      c.fillStyle = "rgba(170,50,36,.9)"; c.beginPath(); c.moveTo(W * .62 + 81 * k, H * .66 - 148 * k); c.lineTo(W * .62 + 126 * k, H * .66 - 138 * k); c.lineTo(W * .62 + 81 * k, H * .66 - 124 * k); c.fill();
      for (const [dx, dy] of [[-52, -52], [-4, -52], [44, -52], [-28, -96], [24, -96]]) {                      // lanterns glowing in the windows
        const x = W * .62 + dx * k * 1.8, y = H * .66 + dy * k * 1.8, g = c.createRadialGradient(x, y, 0, x, y, 24 * k);
        g.addColorStop(0, "rgba(255,196,90,.9)"); g.addColorStop(1, "rgba(255,150,60,0)"); c.fillStyle = g; c.fillRect(x - 26 * k, y - 26 * k, 52 * k, 52 * k);
      }
      for (let i = 0; i < 9; i++) { c.fillStyle = "rgba(74,54,38,.7)"; c.fillRect(W * (.05 + i * .045), H * .75 - 14 * k, 3 * k, 18 * k); }   // the stable fence
      c.strokeStyle = "rgba(74,54,38,.7)"; c.lineWidth = 2 * k; c.beginPath(); c.moveTo(W * .05, H * .75 - 8 * k); c.lineTo(W * .41, H * .75 - 8 * k); c.stroke();
      c.fillStyle = "rgba(74,54,38,.78)"; for (const x of [.14, .24]) { c.beginPath(); c.ellipse(W * x, H * .76, 20 * k, 11 * k, 0, 0, 6.29); c.fill(); c.fillRect(W * x - 2 * k, H * .76 - 30 * k, 4 * k, 26 * k); c.beginPath(); c.arc(W * x - 1 * k, H * .76 - 32 * k, 4 * k, 0, 6.29); c.fill(); }   // camels
    },
    border(c, W, H, R) {
      const k = Math.min(W, H) / 560;
      tower(c, W * .72, H * .72, k * 1.5, "#4a3e38", .85); tower(c, W * .2, H * .74, k, "#5a4c44", .55);
      c.strokeStyle = "rgba(74,62,56,.7)"; c.lineWidth = 3 * k; c.beginPath(); c.moveTo(0, H * .76); for (let x = 0; x <= W; x += 40 * k) c.lineTo(x, H * .76 + (x / (40 * k) % 2 ? 6 : 0)); c.stroke();
      for (let i = 0; i < 8; i++) { const x = W * (.1 + i * .11); c.fillStyle = "rgba(74,62,56,.5)"; c.fillRect(x, H * .76 - 20 * k, 2 * k, 24 * k); }
    },
  };

  function layers(kind, W, H, dpr) {
    const cfg = K[kind] || K.huashan, R = rng(hash(kind));
    const mk = () => { const c = document.createElement("canvas"); c.width = W * dpr; c.height = H * dpr; const x = c.getContext("2d"); x.scale(dpr, dpr); return [c, x]; };
    const [far, f] = mk(), [near, c] = mk();
    // sky
    const sg = f.createLinearGradient(0, 0, 0, H); sg.addColorStop(0, cfg.sky[0]); sg.addColorStop(1, cfg.sky[1]); f.fillStyle = sg; f.fillRect(0, 0, W, H);
    for (const [x, y, rx, col, a] of [[.12, .2, .4, "#cfe1d6", .5], [.88, .32, .35, "#f2d4cf", .45], [.5, .75, .5, "#dfe9e2", .4]]) {
      const g = f.createRadialGradient(W * x, H * y, 0, W * x, H * y, W * rx); g.addColorStop(0, hexA(col, a)); g.addColorStop(1, hexA(col, 0)); f.fillStyle = g; f.fillRect(0, 0, W, H);
    }
    if (cfg.sun) {
      const [sx, sy, sr, sc] = cfg.sun, r = Math.min(W, H) * sr;
      const g = f.createRadialGradient(W * sx, H * sy, r * .6, W * sx, H * sy, r * 3.2); g.addColorStop(0, hexA(sc, .28)); g.addColorStop(1, hexA(sc, 0)); f.fillStyle = g; f.fillRect(0, 0, W, H);
      f.fillStyle = hexA(sc, .8); f.beginPath(); f.arc(W * sx, H * sy, r, 0, 6.29); f.fill();
    }
    cfg.ridges.forEach(([b, a, s], i) => ridge(i === cfg.ridges.length - 1 && cfg.ridges.length > 1 ? c : f, W, H, R, b, a, cfg.ink, s, cfg.sky[1]));
    if (kind === "huashan") ridge(f, W, H, R, .7, .1, cfg.ink, .22, cfg.sky[1]);
    if (kind === "emei") { f.fillStyle = "rgba(255,255,255,.55)"; for (let i = 0; i < 9; i++) { const x = W * (i / 8), h = H * (.12 + R() * .1); f.beginPath(); f.moveTo(x - 40, H * .54); f.lineTo(x, H * .54 - h); f.lineTo(x + 40, H * .54); f.fill(); } }
    if (cfg.water) { water(c, W, H, R, H * cfg.water, kind === "yangtze" ? "#c9bfa0" : "#c4dcdc"); }
    (NEAR[kind] || NEAR.huashan)(c, W, H, R);
    return { far, near, cfg };
  }

  function particles(kind, W, H, R) {
    const type = (K[kind] || {}).p || "none", count = type === "none" ? 0 : Math.round(W / 38);
    const col = { petal: ["#f4b2c0", "#fdeaee"], leaf: ["#8ab27a", "#b6d092"], autumn: ["#d98a3a", "#e8b050"], snow: ["#ffffff", "#eef4fa"], dust: ["#c9b8a0", "#e0d2bc"] }[type] || ["#fff", "#fff"];
    return Array.from({ length: count }, () => ({ x: R() * W, y: R() * H, s: 2 + R() * 3.2, v: .3 + R() * .6, a: R() * 6.28, w: R() * 6.28, c: col[R() > .5 ? 1 : 0], t: type }));
  }

  function paint(canvas, kind) {
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ctx = canvas.getContext("2d"), host = canvas.parentElement, R = rng(hash(kind) + 7);
    let W = 0, H = 0, dpr = 1, L = null, mist = null, ps = [], raf = 0, running = false, visible = true, last = 0, t0 = performance.now();
    function build() {
      const r = host.getBoundingClientRect(); dpr = Math.min(2, devicePixelRatio || 1);
      W = Math.max(1, r.width); H = Math.max(1, r.height); canvas.width = W * dpr; canvas.height = H * dpr;
      L = layers(kind, W, H, dpr); ps = particles(kind, W, H, R);
      mist = document.createElement("canvas"); mist.width = 640; mist.height = 160; const m = mist.getContext("2d");
      m.setTransform(1, 0, 0, .25, 0, 0); const g = m.createRadialGradient(320, 320, 0, 320, 320, 320); g.addColorStop(0, "rgba(255,253,246,.8)"); g.addColorStop(1, "rgba(255,253,246,0)"); m.fillStyle = g; m.fillRect(0, 0, 640, 640);
      draw(performance.now());
    }
    function draw(now) {
      if (!L) return;                      // the first frame can arrive before the first size is known
      const t = (now - t0) / 1000;
      ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(L.far, 0, 0);
      const bands = [[.5, 18, .45], [.62, 12, .5], [.74, 8, .4]];
      bands.forEach(([y, sp, a], i) => { ctx.globalAlpha = a; const off = (t * sp) % (W + 640); for (let k = 0; k < 3; k++) ctx.drawImage(mist, (off + k * (W / 2.2)) % (W + 640) - 640, H * y - 26, 640 + i * 160, 150); });
      ctx.globalAlpha = 1; ctx.drawImage(L.near, 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      for (const p of ps) {
        if (!still) { p.x -= p.v * (p.t === "dust" ? 2.6 : 1.1) + Math.sin(t + p.w) * .25; p.y += p.t === "dust" ? .15 : p.v * (p.t === "snow" ? .8 : 1); p.a += .02; if (p.y > H + 8 || p.x < -8) { p.x = W * (.3 + Math.random() * .8); p.y = -8; } }
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.a); ctx.fillStyle = p.c; ctx.globalAlpha = .85;
        if (p.t === "snow" || p.t === "dust") { ctx.beginPath(); ctx.arc(0, 0, p.t === "dust" ? p.s * .45 : p.s * .5, 0, 6.29); ctx.fill(); } else { ctx.beginPath(); ctx.ellipse(0, 0, p.s, p.s * .5, 0, 0, 6.29); ctx.fill(); }
        ctx.restore();
      }
    }
    function frame(now) { if (!running) return; if (now - last > 33) { last = now; draw(now); } raf = requestAnimationFrame(frame); }
    function setRunning(on) { if (still) return; if (on && !running) { running = true; raf = requestAnimationFrame(frame); } else if (!on) { running = false; cancelAnimationFrame(raf); } }
    const ro = new ResizeObserver(build); ro.observe(host);
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; setRunning(visible && !document.hidden); }); io.observe(canvas);
    const vis = () => setRunning(visible && !document.hidden); document.addEventListener("visibilitychange", vis);
    return { stop() { running = false; cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); document.removeEventListener("visibilitychange", vis); } };
  }

  window.Scenes = { paint, kinds: Object.keys(K) };
})();
