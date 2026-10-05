(() => {
  // What a finished NPC needs. Visitors see eight things; speech, knowledge and appearance work behind the scenes.
  const REQUIRED = ["name", "title", "sect", "location", "alignment", "art", "traits", "speech", "greeting", "goal", "knowledge", "secret", "appearance"];
  const ALIGN = { orthodox: ["正", "a-orthodox", "orthodox"], unorthodox: ["邪", "a-unorthodox", "unorthodox"], neutral: ["中", "a-neutral", "neutral"] };
  const SIL = '<svg class="sil" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="34" r="18" fill="#24211b"/><path d="M12 98c2-24 18-40 38-40s36 16 38 40z" fill="#24211b"/></svg>';
  const $ = s => document.querySelector(s);
  const str = (v, n) => String(v ?? "").replace(/\s+/g, " ").trim().slice(0, n);
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scrollTo = (el, block = "start") => el?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block });

  let draftId = null, sheet = null, aiReady = false, cast = [];
  let busy = false, ctl = null;
  const filled = k => { const v = sheet?.[k]; return k === "appearance" ? !!v && Object.keys(v).length > 0 : Array.isArray(v) ? v.length > 0 : !!v; };
  const missing = () => REQUIRED.filter(k => !filled(k));

  /* ---------- talking to the server ---------- */
  async function api(path, body) {
    const r = await fetch(path, { method: body === undefined ? "GET" : "POST", headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw { code: "http", message: typeof data.detail === "string" ? data.detail : "Something went wrong. Try again." };
    return data;
  }
  // POST that answers with a stream of server-sent events; calls onEvent for each one.
  async function stream(path, body, onEvent, signal) {
    const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}), signal });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw { code: "http", message: typeof d.detail === "string" ? d.detail : "Something went wrong. Try again." }; }
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, i).trim(); buf = buf.slice(i + 2);
        if (!line.startsWith("data:")) continue;
        const ev = JSON.parse(line.slice(5));
        if (ev.type === "error") throw ev;
        onEvent(ev);
      }
    }
  }
  const errText = e => e?.name === "AbortError" ? "" : (e?.message || "Something went wrong reaching the AI. Try again.");

  /* ---------- portraits: drawn here from the character's appearance options ---------- */
  const svgImg = (svg, alt) => { const i = new Image(); i.alt = alt || ""; i.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg); return i; };
  function setFrame(el, npc, alt) {
    el.textContent = "";
    const svg = npc?.appearance && Object.keys(npc.appearance).length ? window.renderPortrait(npc.appearance, npc.name || "") : (npc?.svg || "");
    if (svg) el.append(svgImg(svg, alt)); else el.innerHTML = SIL;
  }

  /* ---------- shared bits ---------- */
  function bondsEl(bonds) {
    const w = document.createElement("div"); w.className = "rels";
    bonds.forEach(b => { const s = document.createElement("span"); s.className = "rel"; const r = document.createElement("b"); r.textContent = str(b.relation, 40); s.append(r, " · " + str(b.toName, 40)); w.append(s); });
    return w;
  }
  function quirksEl(traits) {
    const w = document.createElement("div"); w.className = "chips quirks";
    traits.forEach(t => { const x = document.createElement("span"); x.className = "chip"; x.textContent = t; w.append(x); });
    return w;
  }
  function alignEl(a) { const d = ALIGN[a] || ALIGN.neutral; const s = document.createElement("span"); s.className = "align " + d[1]; s.textContent = d[0]; s.title = d[2]; return s; }
  function note(sel, text, warn) { const n = $(sel); n.hidden = !text; n.textContent = text || ""; n.classList.toggle("warn", !!warn); }
  function chatMsg(log, role, label, text) {
    const m = document.createElement("div"); m.className = "msg" + (role === "user" ? " you" : "");
    const who = document.createElement("span"); who.className = "who"; who.textContent = label;
    const calls = document.createElement("div"); calls.className = "calls";
    const b = document.createElement("div"); b.className = "bubble"; b.textContent = text;
    m.append(who); if (role !== "user") m.append(calls); m.append(b);
    log.append(m); log.scrollTop = log.scrollHeight;
    return { bubble: b, calls };
  }
  function chip(box, log, ev) {
    const c = document.createElement("span"); c.className = "call" + (ev.refused ? " no" : "");
    const b = document.createElement("b"); b.textContent = ev.name; c.append("⚙ ", b, ev.detail ? " · " + ev.detail : "");
    box.append(c); log.scrollTop = log.scrollHeight;
  }

  /* ---------- the scroll ---------- */
  function renderSheet(changed = []) {
    const s = sheet || {};
    document.querySelectorAll(".scroll .f").forEach(f => {
      const k = f.dataset.k, dd = f.querySelector("dd");
      dd.textContent = ""; dd.className = "";
      const empty = t => { dd.textContent = t || "—"; dd.className = "empty"; };
      if (k === "sect") {
        if (!s.sect && !s.location && !s.alignment) empty();
        else { if (s.alignment) dd.append(alignEl(s.alignment)); dd.append([s.sect, s.location].filter(Boolean).join(" · ")); }
      } else if (k === "traits") { s.traits?.length ? dd.append(quirksEl(s.traits)) : empty(); }
      else if (k === "greeting") { s.greeting ? (dd.className = "quote", dd.textContent = `"${s.greeting}"`) : empty(); }
      else if (k === "secret") { s.secret ? (dd.className = "lock", dd.textContent = s.secret) : empty(); }
      else { s[k] ? (dd.textContent = s[k]) : empty(); }
      const touched = changed.includes(k) || (k === "sect" && changed.some(c => c === "location" || c === "alignment"));
      if (touched) { f.classList.add("flash"); setTimeout(() => f.classList.remove("flash"), 900); }
    });
    const hasPortrait = !!(s.appearance && Object.keys(s.appearance).length);
    setFrame($("#portrait"), s, s.name);
    if (changed.includes("appearance") || (changed.includes("name") && hasPortrait)) { const p = $("#portrait"); p.classList.remove("pop"); void p.offsetWidth; p.classList.add("pop"); }
    const done = sheet && !missing().length;
    $("#sheetState").textContent = !sheet ? "empty" : done ? "ready to release" : "filling in…";
    $("#lifeBtn").disabled = busy || !done || !aiReady;
    $("#testBtn").disabled = busy || !aiReady || !(s.name && s.speech && s.greeting);
    $("#rerollBtn").disabled = busy || !aiReady;
  }

  /* ---------- the Storyteller ---------- */
  function setBusy(on, label) {
    busy = on;
    $("#forgeSend").hidden = on; $("#forgeStop").hidden = !on;
    $("#forgeInput").disabled = on || !aiReady; $("#resetBtn").disabled = on;
    document.querySelectorAll("#forgeStarters .starter, #heroRoll").forEach(b => b.disabled = on || !aiReady);
    $("#forgeState").textContent = label || (on ? "thinking…" : "ready");
    renderSheet();
  }
  async function newDraft() {
    const d = await api("/api/drafts", {});
    draftId = d.id; sheet = d.sheet; renderSheet();
  }
  function clearHall() {
    ctl?.abort();
    draftId = null; sheet = null;
    $("#forgeLog").querySelectorAll(".msg:not(:first-child)").forEach(m => m.remove());
    $("#forgeStarters").hidden = false;
    note("#forgeNote", ""); note("#sheetNote", "The scroll fills in as you talk to the Storyteller.");
    renderSheet();
  }
  // One Storyteller turn. kind is "chat" (the visitor wrote something) or "roll" (the server rolls the dice).
  async function tell(kind, text) {
    if (!aiReady || busy) return;
    const log = $("#forgeLog");
    $("#forgeStarters").hidden = true; note("#forgeNote", ""); note("#sheetNote", "");
    let bubble = null, calls = null, said = "";
    const speak = () => { if (!bubble) { ({ bubble, calls } = chatMsg(log, "assistant", "说书人", "Thinking…")); bubble.classList.add("thinking"); } };
    if (kind === "chat") { chatMsg(log, "user", "你", text); speak(); }
    ctl = new AbortController(); setBusy(true, kind === "roll" ? "rolling…" : "thinking…");
    try {
      if (!draftId) await newDraft();
      await stream(`/api/drafts/${draftId}/${kind}`, kind === "chat" ? { message: text } : {}, ev => {
        if (ev.type === "roll") { chatMsg(log, "user", "你", "掷骰 · " + ev.text); speak(); }
        else if (ev.type === "text") { speak(); said += ev.delta; bubble.classList.remove("thinking"); bubble.textContent = said; log.scrollTop = log.scrollHeight; }
        else if (ev.type === "tool") { speak(); chip(calls, log, ev); }
        else if (ev.type === "sheet") { sheet = ev.sheet; renderSheet(ev.changed); }
      }, ctl.signal);
    } catch (e) {
      speak(); bubble.classList.remove("thinking");
      if (!said) bubble.textContent = e?.name === "AbortError" ? "(stopped)" : "…";
      if (errText(e)) note("#forgeNote", errText(e), true);
    } finally {
      setBusy(false);
      if (sheet && !missing().length) note("#sheetNote", "They're ready. Talk to them first, release them into the jianghu, or ask the Storyteller to change anything.");
    }
  }
  function roll() {
    if (!aiReady) { scrollTo($("#hall")); note("#forgeNote", "The AI isn't connected on this server yet.", true); return; }
    if (busy) return;
    clearHall();
    scrollTo($("#hall"));
    tell("roll");
  }
  $("#forgeForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#forgeInput").value.trim(); $("#forgeInput").value = ""; if (v) tell("chat", v); });
  $("#forgeStarters").addEventListener("click", e => {
    const b = e.target.closest(".starter"); if (!b) return;
    b.id === "rollBtn" ? roll() : tell("chat", b.dataset.say);
  });
  $("#forgeStop").addEventListener("click", () => ctl?.abort());
  $("#resetBtn").addEventListener("click", clearHall);
  $("#rerollBtn").addEventListener("click", roll);
  $("#heroRoll").addEventListener("click", roll);

  /* ---------- release ---------- */
  $("#lifeBtn").addEventListener("click", async () => {
    if (busy || missing().length) return;
    setBusy(true, "checking…");
    try {
      const r = await api(`/api/drafts/${draftId}/release`, { creator_name: $("#signName").value });
      if (r.pending) { note("#sheetNote", `${sheet.name} is waiting at the city gate: the automatic check couldn't run, so Ray will review them before they appear.`); return; }
      note("#sheetNote", `${sheet.name} has entered the jianghu. Find them below and press Talk to meet them as the hero.`);
      chatMsg($("#forgeLog"), "assistant", "说书人", `And so ${sheet.name} walks into our story. Go and speak with them, or roll another stranger.`);
      await loadCast();
      scrollTo(document.getElementById("npc-" + r.id), "center");
    } catch (e) { note("#sheetNote", errText(e), true); }
    finally { setBusy(false); }
  });

  /* ---------- talking to an NPC agent ---------- */
  let session = null, aBusy = false, aCtl = null;
  function renderTrust() {
    const m = $("#aTrust"); m.textContent = "";
    for (let i = 0; i < 10; i++) { const p = document.createElement("i"); if (i < session.trust) p.className = "on"; m.append(p); }
    $("#aTrustN").textContent = `${session.trust} / 10`;
    const s = $("#aSecret");
    s.classList.toggle("open", session.revealed);
    s.textContent = !session.has_secret ? "秘密 · They seem to have nothing to hide." : session.revealed ? "秘密 · They told you their secret." : `秘密 · They are hiding something. Trust ${session.threshold}+ may open them up.`;
  }
  async function openAudience(body) {
    if (aBusy) aCtl?.abort();
    try { session = await api("/api/sessions", body); }
    catch (e) { note(body.draft_id ? "#sheetNote" : "#forgeNote", errText(e), true); return; }
    const n = session.npc;
    $("#audience").hidden = false;
    $("#aBanner").hidden = !session.rehearsal;
    $("#aBanner").textContent = session.rehearsal ? "Rehearsal: this NPC isn't in the jianghu yet. Try them out, then go back and change anything with the Storyteller." : "";
    $("#aStarters").hidden = false;
    setFrame($("#aPortrait"), n, str(n.name, 40));
    $("#aName").textContent = str(n.name, 40);
    $("#aTitle").textContent = str(n.title, 80);
    $("#aWhere").textContent = [str(n.sect, 60), str(n.location, 80)].filter(Boolean).join(" · ");
    $("#aHead").textContent = str(n.name, 40); const em = document.createElement("em"); em.textContent = "audience"; $("#aHead").append(em);
    $("#aLog").textContent = ""; note("#aNote", "");
    chatMsg($("#aLog"), "assistant", str(n.name, 40), str(n.greeting, 300) || "…");
    renderTrust(); setABusy(false);
    scrollTo($("#audience"));
  }
  $("#leaveBtn").addEventListener("click", () => { aCtl?.abort(); $("#audience").hidden = true; session = null; });
  $("#testBtn").addEventListener("click", () => draftId && openAudience({ draft_id: draftId }));
  function setABusy(on) {
    aBusy = on;
    $("#aSend").hidden = on; $("#aStop").hidden = !on;
    $("#aInput").disabled = on || !aiReady;
    $("#aState").textContent = on ? "thinking…" : "ready";
  }
  $("#aStop").addEventListener("click", () => aCtl?.abort());
  $("#aForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#aInput").value.trim(); if (v && session && !aBusy && aiReady) { $("#aInput").value = ""; aSay(v); } });
  $("#aStarters").addEventListener("click", e => { const b = e.target.closest(".starter"); if (b && session && !aBusy && aiReady) aSay(b.dataset.say); });
  async function aSay(text) {
    note("#aNote", ""); $("#aStarters").hidden = true;
    chatMsg($("#aLog"), "user", "少侠", text);
    const { bubble, calls } = chatMsg($("#aLog"), "assistant", str(session.npc.name, 40), "…");
    bubble.classList.add("thinking");
    aCtl = new AbortController(); setABusy(true);
    const mine = session; let said = "";
    try {
      await stream(`/api/sessions/${session.id}/chat`, { message: text }, ev => {
        if (session !== mine) return;
        if (ev.type === "text") { said += ev.delta; bubble.classList.remove("thinking"); bubble.textContent = said; $("#aLog").scrollTop = 1e9; }
        else if (ev.type === "tool") chip(calls, $("#aLog"), ev);
        else if (ev.type === "trust") { session.trust = ev.trust; session.revealed = ev.revealed; renderTrust(); }
      }, aCtl.signal);
    } catch (e) {
      bubble.classList.remove("thinking");
      if (!said) bubble.textContent = e?.name === "AbortError" ? "(silence)" : "…";
      if (errText(e)) note("#aNote", errText(e), true);
    } finally { setABusy(false); }
  }

  /* ---------- the people on the road ---------- */
  function wander() {
    if (!aiReady) { scrollTo($("#hall")); note("#forgeNote", "The AI isn't connected on this server yet.", true); return; }
    if (!cast.length) { scrollTo($("#hall")); note("#forgeNote", "No one lives here yet. Roll the first stranger and they'll be waiting for the next visitor.", false); return; }
    openAudience({ npc_id: cast[Math.floor(Math.random() * cast.length)].id });
  }
  $("#wanderBtn").addEventListener("click", wander);
  $("#heroWander").addEventListener("click", wander);

  async function loadCast() {
    try { const d = await api("/api/npcs"); cast = d.npcs; $("#nBond").textContent = d.bonds; renderCast(); }
    catch { /* keep what is shown */ }
  }
  let castSig = null;
  function renderCast() {
    const sig = cast.map(c => c.id).join() + "|" + aiReady;
    if (sig === castSig) return;   // polling found nothing new: don't replay the unroll animation
    castSig = sig;
    $("#nNpc").textContent = cast.length;
    const box = $("#cast");
    box.querySelectorAll(".card").forEach(c => c.remove());
    $("#castEmpty").hidden = cast.length > 0;
    cast.forEach(c => {
      const card = document.createElement("article"); card.className = "scroll card"; card.id = "npc-" + c.id;
      const top = document.createElement("div"); top.className = "card-top";
      const fr = document.createElement("div"); fr.className = "frame"; setFrame(fr, c, str(c.name, 40));
      const t = document.createElement("div");
      const h = document.createElement("h3"); h.textContent = str(c.name, 40);
      const ti = document.createElement("div"); ti.className = "title"; ti.textContent = str(c.title, 80);
      const wh = document.createElement("div"); wh.className = "where"; wh.append(alignEl(c.alignment), [str(c.sect, 60), str(c.location, 80)].filter(Boolean).join(" · "));
      t.append(h, ti, wh); top.append(fr, t); card.append(top);
      if (Array.isArray(c.traits) && c.traits.length) card.append(quirksEl(c.traits.slice(0, 3).map(x => str(x, 40))));
      if (c.art) { const a = document.createElement("div"); a.style.fontSize = "13.5px"; a.textContent = "绝技 · " + str(c.art, 120); card.append(a); }
      if (c.greeting) { const g = document.createElement("p"); g.className = "greet"; g.textContent = `"${str(c.greeting, 240)}"`; card.append(g); }
      if (Array.isArray(c.bonds) && c.bonds.length) card.append(bondsEl(c.bonds.slice(0, 3)));
      const by = document.createElement("div"); by.className = "by";
      by.append(`Created by ${str(c.creator_name, 40) || "a visitor"}`);
      const talk = document.createElement("button"); talk.className = "btn"; talk.textContent = "Talk 交谈"; talk.disabled = !aiReady;
      talk.addEventListener("click", () => openAudience({ npc_id: c.id }));
      by.append(talk); card.append(by);
      box.append(card);
    });
  }

  /* ---------- boot ---------- */
  renderSheet(); setBusy(false); setABusy(false);
  (async () => {
    try { aiReady = (await api("/api/status")).ai; } catch { aiReady = false; }
    if (!aiReady) note("#forgeNote", "The AI isn't connected on this server yet, so new NPCs can't be created. Browsing still works.", true);
    setBusy(false); setABusy(false);
    await loadCast();
    setInterval(() => { if (!document.hidden) loadCast(); }, 20000);
  })();
})();
