(() => {
  // What a finished NPC needs. Visitors see eight things; speech, knowledge and appearance work behind the scenes.
  const REQUIRED = ["name", "title", "sect", "location", "alignment", "art", "traits", "speech", "greeting", "goal", "knowledge", "secret", "appearance"];
  const ALIGN = { orthodox: ["正", "a-orthodox", "orthodox"], unorthodox: ["邪", "a-unorthodox", "unorthodox"], neutral: ["中", "a-neutral", "neutral"] };
  const SIL = '<svg class="sil" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="34" r="18" fill="#24211b"/><path d="M12 98c2-24 18-40 38-40s36 16 38 40z" fill="#24211b"/></svg>';
  const $ = s => document.querySelector(s);
  const str = (v, n) => String(v ?? "").replace(/\s+/g, " ").trim().slice(0, n);
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scrollTo = (el, block = "start") => el?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block });

  /* ---------- two languages everywhere ----------
     AI text arrives as "English ||| 中文". Notes and labels are written as pairs in the code below. */
  const SEP = "|||";
  const nCJK = t => (String(t).match(/[一-鿿]/g) || []).length;
  const nLat = t => (String(t).match(/[A-Za-z]{2,}/g) || []).length;
  const langOf = t => nCJK(t) > nLat(t) ? "zh" : "en";
  const hasBoth = t => nCJK(t) >= 2 && nLat(t) >= 2;
  const splitBi = t => { t = String(t ?? ""); const i = t.indexOf(SEP); return i < 0 ? [t.trim(), ""] : [t.slice(0, i).trim(), t.slice(i + SEP.length).trim()]; };
  const bi = (en, zh) => `${en}\n${zh}`;                     // for notes; they render with line breaks
  const bi1 = (en, zh) => `${en} ${zh}`;                     // for short status labels
  // Fill an element with an English block and a Chinese block. quote wraps each in curly quotes.
  function fillBi(el, text, quote = false) {
    el.textContent = "";
    let [a, b] = splitBi(text);
    const add = (cls, t) => { if (!t) return; const d = document.createElement("div"); d.className = cls; d.textContent = quote ? `“${t}”` : t; el.append(d); };
    if (b) { add("en", a); add("zh", b); }
    else add(langOf(a) === "zh" ? "zh" : "en", a);          // only one language so far (still streaming, or a translation is on its way)
  }
  const biText = t => { const [a, b] = splitBi(t); return b ? `${a} / ${b}` : a; };

  let draftId = null, sheet = null, aiReady = false, cast = [];
  let busy = false, ctl = null;
  const filled = k => { const v = sheet?.[k]; return k === "appearance" ? !!v && Object.keys(v).length > 0 : Array.isArray(v) ? v.length > 0 : !!v; };
  const missing = () => REQUIRED.filter(k => !filled(k));

  /* ---------- talking to the server ---------- */
  const GENERIC = bi("Something went wrong. Try again.", "出错了，请重试。");
  const GENERIC_AI = bi("Something went wrong reaching the AI. Try again.", "连接 AI 时出错，请重试。");
  async function api(path, body) {
    const r = await fetch(path, { method: body === undefined ? "GET" : "POST", headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw { code: "http", message: typeof data.detail === "string" ? data.detail : GENERIC };
    return data;
  }
  // POST that answers with a stream of server-sent events; calls onEvent for each one.
  async function stream(path, body, onEvent, signal) {
    const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}), signal });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw { code: "http", message: typeof d.detail === "string" ? d.detail : GENERIC }; }
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
  const errText = e => e?.name === "AbortError" ? "" : (e?.message || GENERIC_AI);

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
    bonds.forEach(b => { const s = document.createElement("span"); s.className = "rel"; const r = document.createElement("b"); r.textContent = biText(str(b.relation, 100)); s.append(r, " · " + str(b.toName, 40)); w.append(s); });
    return w;
  }
  function quirksEl(traits) {
    const w = document.createElement("div"); w.className = "chips quirks";
    traits.forEach(t => { const x = document.createElement("span"); x.className = "chip"; fillBi(x, t); w.append(x); });
    return w;
  }
  function alignEl(a) { const d = ALIGN[a] || ALIGN.neutral; const s = document.createElement("span"); s.className = "align " + d[1]; s.textContent = d[0]; s.title = d[2]; return s; }
  // "Emei Sect · Frost Bell Monastery" over "峨眉派 · 霜铃寺"
  const joinBi = (...parts) => { const p = parts.filter(Boolean).map(splitBi); return [p.map(x => x[0]).filter(Boolean).join(" · "), p.map(x => x[1]).filter(Boolean).join(" · ")].join(` ${SEP} `); };
  function note(sel, text, warn) { const n = $(sel); n.hidden = !text; n.textContent = text || ""; n.classList.toggle("warn", !!warn); }
  function chatMsg(log, role, label, text) {
    const m = document.createElement("div"); m.className = "msg" + (role === "user" ? " you" : "");
    const who = document.createElement("span"); who.className = "who"; who.textContent = label;
    const calls = document.createElement("div"); calls.className = "calls";
    const b = document.createElement("div"); b.className = "bubble";
    if (text) fillBi(b, text);
    m.append(who); if (role !== "user") m.append(calls); m.append(b);
    log.append(m); log.scrollTop = log.scrollHeight;
    return { bubble: b, calls };
  }
  // The visitor's own words, with the other language filled in a moment later.
  async function userBubble(log, who, text) {
    const { bubble } = chatMsg(log, "user", who, text);
    if (text.includes(SEP) || hasBoth(text)) return bubble;
    try {
      const r = await api("/api/translate", { message: text });
      if (r.text) { const [en, zh] = langOf(text) === "zh" ? [r.text, text] : [text, r.text]; fillBi(bubble, `${en} ${SEP} ${zh}`); log.scrollTop = log.scrollHeight; }
    } catch { /* the original stays; a missing translation must not break the chat */ }
    return bubble;
  }
  function chip(box, log, ev) {
    const c = document.createElement("span"); c.className = "call" + (ev.refused ? " no" : "");
    const b = document.createElement("b"); b.textContent = ev.name; c.append("⚙ ", b, ev.detail ? " · " + biText(ev.detail) : "");
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
        else { if (s.alignment) dd.append(alignEl(s.alignment)); const box = document.createElement("div"); box.className = "bi"; fillBi(box, joinBi(s.sect, s.location)); dd.append(box); }
      } else if (k === "traits") { s.traits?.length ? dd.append(quirksEl(s.traits)) : empty(); }
      else if (k === "name") { s.name ? (dd.textContent = s.name) : empty(); }
      else if (s[k]) { dd.className = "bi" + (k === "greeting" ? " quote" : k === "secret" ? " lock" : ""); fillBi(dd, s[k], k === "greeting"); }
      else empty();
      const touched = changed.includes(k) || (k === "sect" && changed.some(c => c === "location" || c === "alignment"));
      if (touched) { f.classList.add("flash"); setTimeout(() => f.classList.remove("flash"), 900); }
    });
    const hasPortrait = !!(s.appearance && Object.keys(s.appearance).length);
    setFrame($("#portrait"), s, s.name);
    if (changed.includes("appearance") || (changed.includes("name") && hasPortrait)) { const p = $("#portrait"); p.classList.remove("pop"); void p.offsetWidth; p.classList.add("pop"); }
    const done = sheet && !missing().length;
    $("#sheetState").textContent = !sheet ? bi1("empty", "空") : done ? bi1("ready to release", "可放入江湖") : bi1("filling in…", "填写中…");
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
    $("#forgeState").textContent = label || (on ? bi1("thinking…", "思考中…") : bi1("ready", "就绪"));
    renderSheet();
  }
  async function newDraft() {
    const d = await api("/api/drafts", {});
    draftId = d.id; sheet = d.sheet; renderSheet();
  }
  const SHEET_HINT = bi("The scroll fills in as you talk to the Storyteller.", "你与说书人交谈时，卷轴会自动填写。");
  function clearHall() {
    ctl?.abort();
    draftId = null; sheet = null;
    $("#forgeLog").querySelectorAll(".msg:not(:first-child)").forEach(m => m.remove());
    $("#forgeStarters").hidden = false;
    note("#forgeNote", ""); note("#sheetNote", SHEET_HINT);
    renderSheet();
  }
  // One Storyteller turn. kind is "chat" (the visitor wrote something) or "roll" (the server rolls the dice).
  async function tell(kind, text) {
    if (!aiReady || busy) return;
    const log = $("#forgeLog");
    $("#forgeStarters").hidden = true; note("#forgeNote", ""); note("#sheetNote", "");
    let bubble = null, calls = null, said = "";
    const speak = () => { if (!bubble) { ({ bubble, calls } = chatMsg(log, "assistant", "说书人 Storyteller", "")); bubble.textContent = bi1("Thinking…", "思考中…"); bubble.classList.add("thinking"); } };
    if (kind === "chat") { userBubble(log, "你 You", text); speak(); }
    ctl = new AbortController(); setBusy(true, kind === "roll" ? bi1("rolling…", "掷骰中…") : bi1("thinking…", "思考中…"));
    try {
      if (!draftId) await newDraft();
      await stream(`/api/drafts/${draftId}/${kind}`, kind === "chat" ? { message: text } : {}, ev => {
        if (ev.type === "roll") { chatMsg(log, "user", "你 You", `Roll the dice: ${ev.text} ${SEP} 掷骰：${ev.text_zh}`); speak(); }
        else if (ev.type === "retract") { said = ""; bubble.textContent = bi1("Thinking…", "思考中…"); bubble.classList.add("thinking"); }
        else if (ev.type === "text") { speak(); said += ev.delta; bubble.classList.remove("thinking"); fillBi(bubble, said); log.scrollTop = log.scrollHeight; }
        else if (ev.type === "tool") { speak(); chip(calls, log, ev); }
        else if (ev.type === "sheet") { sheet = ev.sheet; renderSheet(ev.changed); }
      }, ctl.signal);
    } catch (e) {
      speak(); bubble.classList.remove("thinking");
      if (!said) bubble.textContent = e?.name === "AbortError" ? bi1("(stopped)", "（已停止）") : "…";
      if (errText(e)) note("#forgeNote", errText(e), true);
    } finally {
      setBusy(false);
      if (sheet && !missing().length) note("#sheetNote", bi("They're ready. Talk to them first, release them into the jianghu, or ask the Storyteller to change anything.", "他们准备好了。可以先交谈试试，直接放入江湖，或让说书人修改任何地方。"));
    }
  }
  const NO_AI = bi("The AI isn't connected on this server yet.", "此服务器尚未连接 AI。");
  function roll() {
    if (!aiReady) { scrollTo($("#hall")); note("#forgeNote", NO_AI, true); return; }
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
    setBusy(true, bi1("checking…", "审核中…"));
    try {
      const r = await api(`/api/drafts/${draftId}/release`, { creator_name: $("#signName").value });
      const who = splitBi(sheet.name)[0];
      if (r.pending) { note("#sheetNote", bi(`${who} is waiting at the city gate: the automatic check couldn't run, so Ray will review them before they appear.`, `${who} 正在城门外等候：自动审核未能运行，Ray 会先审阅再放行。`)); return; }
      note("#sheetNote", bi(`${who} has entered the jianghu. Find them below and press Talk to meet them as the hero.`, `${who} 已入江湖。在下方找到他，点「交谈」以主角身份相见。`));
      chatMsg($("#forgeLog"), "assistant", "说书人 Storyteller", `And so ${who} walks into our story. Go and speak with them, or roll another stranger. ${SEP} 于是 ${who} 走进了我们的故事。去和他说话吧，或者再掷一位陌生人。`);
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
    s.textContent = !session.has_secret ? bi("Secret 秘密 · nothing to hide", "他似乎没有什么可隐瞒的。")
      : session.revealed ? bi("Secret 秘密 · they told you.", "他已向你吐露了秘密。")
        : bi(`Secret 秘密 · they are hiding something. Trust ${session.threshold}+ may open them up.`, `他藏着一个秘密。信任达到 ${session.threshold} 以上，或许能让他开口。`);
  }
  async function openAudience(body) {
    if (aBusy) aCtl?.abort();
    try { session = await api("/api/sessions", body); }
    catch (e) { note(body.draft_id ? "#sheetNote" : "#forgeNote", errText(e), true); return; }
    const n = session.npc;
    $("#audience").hidden = false;
    $("#aBanner").hidden = !session.rehearsal;
    $("#aBanner").textContent = session.rehearsal ? bi("Rehearsal: this NPC isn't in the jianghu yet. Try them out, then go back and change anything with the Storyteller.", "试谈：这位人物尚未放入江湖。先试试他，再回去让说书人修改。") : "";
    $("#aStarters").hidden = false;
    setFrame($("#aPortrait"), n, splitBi(n.name)[0]);
    $("#aName").textContent = str(n.name, 40);
    fillBi($("#aTitle"), n.title || "");
    fillBi($("#aWhere"), joinBi(n.sect, n.location));
    $("#aHead").textContent = str(n.name, 40); const em = document.createElement("em"); em.textContent = "audience 谒见"; $("#aHead").append(em);
    $("#aLog").textContent = ""; note("#aNote", "");
    const g = chatMsg($("#aLog"), "assistant", str(n.name, 40), "");
    fillBi(g.bubble, n.greeting || "…");
    renderTrust(); setABusy(false);
    scrollTo($("#audience"));
  }
  $("#leaveBtn").addEventListener("click", () => { aCtl?.abort(); $("#audience").hidden = true; session = null; });
  $("#testBtn").addEventListener("click", () => draftId && openAudience({ draft_id: draftId }));
  function setABusy(on) {
    aBusy = on;
    $("#aSend").hidden = on; $("#aStop").hidden = !on;
    $("#aInput").disabled = on || !aiReady;
    $("#aState").textContent = on ? bi1("thinking…", "思考中…") : bi1("ready", "就绪");
  }
  $("#aStop").addEventListener("click", () => aCtl?.abort());
  $("#aForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#aInput").value.trim(); if (v && session && !aBusy && aiReady) { $("#aInput").value = ""; aSay(v); } });
  $("#aStarters").addEventListener("click", e => { const b = e.target.closest(".starter"); if (b && session && !aBusy && aiReady) aSay(b.dataset.say); });
  async function aSay(text) {
    note("#aNote", ""); $("#aStarters").hidden = true;
    userBubble($("#aLog"), "少侠 Hero", text);
    const { bubble, calls } = chatMsg($("#aLog"), "assistant", str(session.npc.name, 40), "");
    bubble.textContent = "…"; bubble.classList.add("thinking");
    aCtl = new AbortController(); setABusy(true);
    const mine = session; let said = "";
    try {
      await stream(`/api/sessions/${session.id}/chat`, { message: text }, ev => {
        if (session !== mine) return;
        if (ev.type === "retract") { said = ""; bubble.textContent = "…"; bubble.classList.add("thinking"); }
        else if (ev.type === "text") { said += ev.delta; bubble.classList.remove("thinking"); fillBi(bubble, said); $("#aLog").scrollTop = 1e9; }
        else if (ev.type === "tool") chip(calls, $("#aLog"), ev);
        else if (ev.type === "trust") { session.trust = ev.trust; session.revealed = ev.revealed; renderTrust(); }
      }, aCtl.signal);
    } catch (e) {
      bubble.classList.remove("thinking");
      if (!said) bubble.textContent = e?.name === "AbortError" ? bi1("(silence)", "（沉默）") : "…";
      if (errText(e)) note("#aNote", errText(e), true);
    } finally { setABusy(false); }
  }

  /* ---------- the people on the road ---------- */
  function wander() {
    if (!aiReady) { scrollTo($("#hall")); note("#forgeNote", NO_AI, true); return; }
    if (!cast.length) { scrollTo($("#hall")); note("#forgeNote", bi("No one lives here yet. Roll the first stranger and they'll be waiting for the next visitor.", "这里还没有人。掷出第一位陌生人，他会在这里等下一位访客。"), false); return; }
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
      const fr = document.createElement("div"); fr.className = "frame"; setFrame(fr, c, splitBi(c.name)[0]);
      const t = document.createElement("div");
      const h = document.createElement("h3"); h.textContent = str(c.name, 40);
      const ti = document.createElement("div"); ti.className = "title bi"; fillBi(ti, c.title || "");
      const wh = document.createElement("div"); wh.className = "where"; const whBox = document.createElement("div"); whBox.className = "bi"; fillBi(whBox, joinBi(c.sect, c.location)); wh.append(alignEl(c.alignment), whBox);
      t.append(h, ti, wh); top.append(fr, t); card.append(top);
      if (Array.isArray(c.traits) && c.traits.length) card.append(quirksEl(c.traits.slice(0, 3)));
      if (c.art) { const a = document.createElement("div"); a.className = "bi art"; fillBi(a, c.art); card.append(a); }
      if (c.greeting) { const g = document.createElement("div"); g.className = "greet bi quote"; fillBi(g, c.greeting, true); card.append(g); }
      if (Array.isArray(c.bonds) && c.bonds.length) card.append(bondsEl(c.bonds.slice(0, 3)));
      const by = document.createElement("div"); by.className = "by";
      by.append(`Created by 创作者 ${str(c.creator_name, 40) || "a visitor 访客"}`);
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
    if (!aiReady) note("#forgeNote", bi("The AI isn't connected on this server yet, so new NPCs can't be created. Browsing still works.", "此服务器尚未连接 AI，暂时无法创建新人物，但仍可浏览。"), true);
    setBusy(false); setABusy(false);
    await loadCast();
    setInterval(() => { if (!document.hidden) loadCast(); }, 20000);
  })();
})();
