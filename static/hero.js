/* ---------- the hero painting: moonlit ink-wash mountains, a lone swordsman, drifting plum petals ---------- */
(() => {
  const cv = document.getElementById("scene"); if (!cv) return;
  const ctx = cv.getContext("2d"), host = cv.parentElement;
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let W = 0, H = 0, dpr = 1, layers = [], mist = null, petals = [], px = 0, tx = 0, running = false, visible = true;
  const M = 80; // parallax margin

  function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function noise1(r, n) { const v = Array.from({ length: n + 2 }, () => r()); return x => { const i = Math.floor(x), f = x - i, s = f * f * (3 - 2 * f); return v[i % v.length] * (1 - s) + v[(i + 1) % v.length] * s; }; }

  function buildLayers() {
    const specs = [
      { base: .50, amp: .30, freq: 3.5, col: [150, 168, 158], a: .28, depth: .15, seed: 11 },
      { base: .58, amp: .26, freq: 5, col: [110, 128, 120], a: .40, depth: .3, seed: 23 },
      { base: .67, amp: .20, freq: 6.5, col: [70, 84, 78], a: .62, depth: .5, seed: 37 },
      { base: .78, amp: .14, freq: 8, col: [36, 42, 38], a: .85, depth: .75, seed: 51 }
    ];
    layers = specs.map(s => {
      const c = document.createElement("canvas"); c.width = (W + 2 * M) * dpr; c.height = H * dpr;
      const g = c.getContext("2d"); g.scale(dpr, dpr);
      const r = rng(s.seed), n1 = noise1(r, 64), n2 = noise1(r, 64), n3 = noise1(r, 64);
      const w = W + 2 * M, pts = [];
      for (let x = 0; x <= w; x += 4) {
        const u = x / w;
        let h = n1(u * s.freq) * .62 + n2(u * s.freq * 2.3) * .26 + n3(u * s.freq * 6) * .12;
        h = Math.pow(h, 1.9);                            // sharpen into tall, thin peaks
        pts.push([x, H * s.base - h * H * s.amp * 1.6]);
      }
      const top = Math.min(...pts.map(p => p[1]));
      const grad = g.createLinearGradient(0, top, 0, H * s.base + H * .14);
      grad.addColorStop(0, `rgba(${s.col},${s.a})`);
      grad.addColorStop(.55, `rgba(${s.col},${s.a * .55})`);
      grad.addColorStop(1, `rgba(${s.col},0)`);         // dissolve into mist, like wet ink on paper
      g.beginPath(); g.moveTo(0, H); pts.forEach(p => g.lineTo(p[0], p[1])); g.lineTo(w, H); g.closePath();
      g.fillStyle = grad; g.fill();
      g.beginPath(); pts.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]));
      g.strokeStyle = `rgba(${s.col.map(v => Math.round(v * .6))},${Math.min(1, s.a + .15)})`; g.lineWidth = 1.4; g.stroke();
      return { c, depth: s.depth };
    });
    mist = document.createElement("canvas"); mist.width = 600; mist.height = 120;
    const mg = mist.getContext("2d"), rg = mg.createRadialGradient(300, 300, 0, 300, 300, 300);
    rg.addColorStop(0, "rgba(220,214,196,.22)"); rg.addColorStop(1, "rgba(220,214,196,0)");
    mg.setTransform(1, 0, 0, .2, 0, 0); mg.fillStyle = rg; mg.fillRect(0, 0, 600, 600);
  }

  function resize() {
    const r = host.getBoundingClientRect(); dpr = Math.min(2, devicePixelRatio || 1);
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    buildLayers();
    const r2 = rng(99);
    petals = Array.from({ length: Math.round(W / 40) }, () => ({ x: r2() * W, y: r2() * H, s: 2 + r2() * 3, v: .3 + r2() * .5, a: r2() * 6.28, w: r2() * 6.28, pink: r2() > .45 }));
    if (!running) draw(performance.now());
  }

  function figure(t, hx, hy, s) {
    const fl = Math.sin(t * 2.2) * 5 * s, fl2 = Math.cos(t * 1.7) * 4 * s;
    ctx.strokeStyle = "#c8402f"; ctx.lineCap = "round"; ctx.lineWidth = 3 * s;   // scarf in the wind
    ctx.beginPath(); ctx.moveTo(hx - 2 * s, hy - 43 * s);
    ctx.bezierCurveTo(hx - 16 * s, hy - 40 * s + fl, hx - 26 * s, hy - 50 * s + fl2, hx - 42 * s, hy - 44 * s + fl);
    ctx.stroke();
    ctx.fillStyle = "#0a0a08";
    ctx.beginPath(); ctx.moveTo(hx - 7 * s, hy - 44 * s); ctx.lineTo(hx + 8 * s, hy - 44 * s);
    ctx.lineTo(hx + 15 * s, hy); ctx.lineTo(hx - 13 * s + Math.sin(t * 2) * 1.5 * s, hy); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.arc(hx, hy - 50 * s, 5 * s, 0, 6.29); ctx.fill();
    ctx.beginPath(); ctx.ellipse(hx, hy - 54 * s, 17 * s, 3.4 * s, 0, 0, 6.29); ctx.fill();   // bamboo hat
    ctx.beginPath(); ctx.moveTo(hx - 7 * s, hy - 55 * s); ctx.lineTo(hx, hy - 63 * s); ctx.lineTo(hx + 7 * s, hy - 55 * s); ctx.fill();
    ctx.strokeStyle = "#0a0a08"; ctx.lineWidth = 2 * s;
    ctx.beginPath(); ctx.moveTo(hx - 9 * s, hy - 18 * s); ctx.lineTo(hx + 13 * s, hy - 62 * s); ctx.stroke();   // sword across the back
    ctx.lineWidth = 4 * s; ctx.beginPath(); ctx.moveTo(hx + 9 * s, hy - 55 * s); ctx.lineTo(hx + 13 * s, hy - 62 * s); ctx.stroke();
  }

  function pine(x, y, s) {
    ctx.strokeStyle = "#0b0c0a"; ctx.lineCap = "round"; ctx.lineWidth = 7 * s;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.bezierCurveTo(x - 10 * s, y - 50 * s, x - 70 * s, y - 70 * s, x - 120 * s, y - 64 * s); ctx.stroke();
    ctx.lineWidth = 4 * s; ctx.beginPath(); ctx.moveTo(x - 50 * s, y - 62 * s); ctx.quadraticCurveTo(x - 60 * s, y - 100 * s, x - 40 * s, y - 120 * s); ctx.stroke();
    ctx.fillStyle = "rgba(14,17,15,.95)";
    [[-120, -70, 46, 12], [-82, -80, 40, 11], [-40, -124, 38, 10], [-20, -98, 30, 9], [-140, -60, 26, 7], [-62, -108, 26, 8]].forEach(([dx, dy, rx, ry]) => {
      ctx.beginPath(); ctx.ellipse(x + dx * s, y + dy * s, rx * s, ry * s, -.08, 0, 6.29); ctx.fill();
    });
  }

  function draw(now) {
    const t = now / 1000;
    px += (tx - px) * .05;
    const sky = ctx.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#0d0f0e"); sky.addColorStop(.6, "#1b2421"); sky.addColorStop(1, "#262a24");
    ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);

    const small = W < 600, mx = W * (small ? .8 : .73) - px * 8, my = small ? 66 : H * .26, mr = small ? 30 : Math.min(W, H) * .11;   // on a phone the moon rides high, clear of the headline
    const glow = ctx.createRadialGradient(mx, my, mr * .8, mx, my, mr * 3.2);
    glow.addColorStop(0, "rgba(233,223,196,.18)"); glow.addColorStop(1, "rgba(233,223,196,0)");
    ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#e9dfc4"; ctx.beginPath(); ctx.arc(mx, my, mr, 0, 6.29); ctx.fill();
    ctx.fillStyle = "rgba(200,190,160,.25)"; ctx.beginPath(); ctx.arc(mx - mr * .3, my + mr * .15, mr * .22, 0, 6.29); ctx.fill();

    ctx.strokeStyle = "rgba(10,10,8,.8)"; ctx.lineWidth = 1.3;   // geese crossing the moon
    for (let i = 0; i < 6; i++) {
      const gx = ((t * 14 + i * 22) % (W + 200)) - 100 + (i % 2) * 6, gy = H * .2 + Math.abs(i - 2.5) * 9, f = Math.sin(t * 6 + i) * 3;
      ctx.beginPath(); ctx.moveTo(gx - 6, gy - 2 + f); ctx.lineTo(gx, gy); ctx.lineTo(gx + 6, gy - 2 + f); ctx.stroke();
    }

    layers.forEach((l, i) => {
      ctx.drawImage(l.c, -M - px * l.depth * 40, 0, W + 2 * M, H);
      const drift = (t * (6 + i * 4)) % (W + 600);
      for (let k = 0; k < 3; k++) ctx.drawImage(mist, ((drift + k * (W / 2.4)) % (W + 600)) - 600, H * (.52 + i * .08) - 30, 600 + i * 120, 120);
    });

    const off = -px * 34, s = Math.max(.7, Math.min(1.4, H / 540));   // foreground cliff on the right, clear of the text
    ctx.fillStyle = "#0b0c0a";
    ctx.beginPath(); ctx.moveTo(W + 10, H * .58);
    ctx.lineTo(W * .9 + off, H * .6); ctx.lineTo(W * .82 + off, H * .64); ctx.lineTo(W * .76 + off, H * .655);
    ctx.lineTo(W * .735 + off, H * .7); ctx.lineTo(W * .75 + off, H * .82); ctx.lineTo(W * .72 + off, H); ctx.lineTo(W + 10, H); ctx.closePath(); ctx.fill();
    pine(W * .93 + off, H * .6, s);
    if (cv.dataset.figure !== "off") figure(t, W * .79 + off, H * .645, s);

    petals.forEach(p => {   // plum petals on the wind
      if (!still) { p.x -= p.v * 1.2 + Math.sin(t + p.w) * .3; p.y += p.v; p.a += .02; if (p.y > H + 10 || p.x < -10) { p.x = W * (.4 + Math.random() * .7); p.y = -10; } }
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.a);
      ctx.fillStyle = p.pink ? "rgba(233,163,160,.85)" : "rgba(200,64,47,.85)";
      ctx.beginPath(); ctx.ellipse(0, 0, p.s, p.s * .55, 0, 0, 6.29); ctx.fill(); ctx.restore();
    });

    if (running) requestAnimationFrame(draw);
  }

  function setRunning(on) { if (still) return; if (on && !running) { running = true; requestAnimationFrame(draw); } else if (!on) running = false; }
  host.addEventListener("pointermove", e => { const r = host.getBoundingClientRect(); tx = (e.clientX - r.left) / r.width - .5; });
  host.addEventListener("pointerleave", () => { tx = 0; });
  new ResizeObserver(resize).observe(host);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; setRunning(visible && !document.hidden); }).observe(host);
  document.addEventListener("visibilitychange", () => setRunning(visible && !document.hidden));
})();
