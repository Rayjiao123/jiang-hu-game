(() => {
  "use strict";
  const REQUIRED = ["name", "title", "sect", "location", "region", "alignment", "art", "traits", "speech", "greeting", "goal", "knowledge", "secret", "appearance"];
  const ALIGN = { orthodox: ["正", "a-orthodox", "orthodox"], unorthodox: ["邪", "a-unorthodox", "unorthodox"], neutral: ["中", "a-neutral", "neutral"] };
  const SIL = '<svg class="sil" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="34" r="18" fill="#2a2118"/><path d="M12 98c2-24 18-40 38-40s36 16 38 40z" fill="#2a2118"/></svg>';
  const $ = s => document.querySelector(s);
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const S = { aiReady: false, regions: [], byId: {}, hero: null, npcs: [], screen: null, here: null, npc: null, session: null, log: [],
              draftId: null, sheet: null, busy: false, ctl: null, talkBusy: false, talkCtl: null, bg: null, map: null, castSig: "" };

  /* ---------- two languages everywhere ----------
     AI text arrives as "English ||| 中文". Notes and labels are written as pairs in the code below. */
  const SEP = "|||";
  const str = (v, n) => String(v ?? "").replace(/\s+/g, " ").trim().slice(0, n);
  const nCJK = t => (String(t).match(/[一-鿿]/g) || []).length;
  const nLat = t => (String(t).match(/[A-Za-z]{2,}/g) || []).length;
  const langOf = t => nCJK(t) > nLat(t) ? "zh" : "en";
  const hasBoth = t => nCJK(t) >= 2 && nLat(t) >= 2;
  const splitBi = t => {
    t = String(t ?? "");
    const i = t.indexOf(SEP), tail = i < 0 ? "" : t.slice(i + SEP.length);
    if (i >= 0 && tail.indexOf(SEP) < 0) return [t.slice(0, i).trim(), tail.trim()];       // the normal case
    if (i < 0 && !hasBoth(t)) return [t.trim(), ""];                                    // one language so far
    // the separator was forgotten or repeated: sort the paragraphs by language
    const en = [], zh = [];
    t.split(SEP).join("\n\n").split(/\n{2,}/).map(p => p.trim()).filter(Boolean).forEach(p => (langOf(p) === "zh" ? zh : en).push(p));
    return [en.join("\n\n"), zh.join("\n\n")];
  };
  const biText = t => { const [a, b] = splitBi(t); return b ? `${a} / ${b}` : a; };
  const bi = (en, zh) => `${en}\n${zh}`;
  const bi1 = (en, zh) => `${en} ${zh}`;
  const joinBi = (...parts) => { const p = parts.filter(Boolean).map(splitBi); return [p.map(x => x[0]).filter(Boolean).join(" · "), p.map(x => x[1]).filter(Boolean).join(" · ")].join(` ${SEP} `); };
  const nameParts = name => { const m = String(name || "").match(/^((?:[\u4e00-\u9fff·]+\s*)+)(.*)$/); return m ? { zh: m[1].trim(), en: m[2].trim() || m[1].trim() } : { zh: String(name || ""), en: String(name || "") }; };
  // Fill an element with an English block and a Chinese block. quote wraps each in curly quotes.
  function fillBi(el, text, quote = false) {
    el.textContent = "";
    const [a, b] = splitBi(text);
    const add = (cls, t) => { if (!t) return; const d = document.createElement("div"); d.className = cls; d.textContent = quote ? `“${t}”` : t; el.append(d); };
    if (b) { add("en", a); add("zh", b); } else add(langOf(a) === "zh" ? "zh" : "en", a);
  }
  const regionName = id => S.byId[id] || { en: "the jianghu", zh: "江湖" };
  const regionLabel = id => { const r = regionName(id); return `${r.zh} ${r.en}`; };

  let toastTimer = 0;
  function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("on"), 4600); }
  function note(sel, text, warn) { const n = $(sel); n.hidden = !text; n.textContent = text || ""; n.classList.toggle("warn", !!warn); }

  /* ---------- talking to the server ---------- */
  const GENERIC = bi("Something went wrong. Try again.", "出错了，请重试。");
  const GENERIC_AI = bi("Something went wrong reaching the AI. Try again.", "连接 AI 时出错，请重试。");
  const NO_AI = bi("The AI isn't connected on this server yet.", "此服务器尚未连接 AI。");
  const detail = d => typeof d.detail === "string" ? d.detail : GENERIC;
  async function api(path, body) {
    const r = await fetch(path, { method: body === undefined ? "GET" : "POST", headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw { code: "http", message: detail(data) };
    return data;
  }
  // POST that answers with server-sent events; calls onEvent for each one. An "error" event throws.
  async function stream(path, body, onEvent, signal) {
    const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}), signal });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw { code: "http", message: detail(d) }; }
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

  /* ---------- portraits ---------- */
  const hasLook = c => !!(c?.appearance && Object.keys(c.appearance).length);
  const svgUrl = svg => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  function portraitImg(c, bg, alt) {
    const i = new Image(); i.alt = alt || ""; i.src = svgUrl(window.renderPortrait(c.appearance, c.name || "", { bg })); return i;
  }
  function setPortrait(el, c, bg = false) {
    el.textContent = "";
    if (hasLook(c)) el.append(portraitImg(c, bg, splitBi(c.name)[0])); else el.innerHTML = SIL;
  }
  const alignEl = a => { const d = ALIGN[a] || ALIGN.neutral; const s = document.createElement("span"); s.className = "align " + d[1]; s.textContent = d[0]; s.title = d[2]; return s; };
  function quirks(box, traits) {
    box.textContent = "";
    (traits || []).forEach(t => { const x = document.createElement("span"); x.className = "chip"; fillBi(x, t); box.append(x); });
  }

  /* ---------- screens ---------- */
  const SCREENS = ["gate", "forge", "map", "scene", "talk"];
  const BG = { forge: ["#forgeBg", "wudang"], scene: ["#sceneBg", null], talk: ["#talkBg", null] };
  function go(name, opts = {}) {
    if (S.bg) { S.bg.stop(); S.bg = null; }
    if (name !== "talk") { S.talkCtl?.abort(); closeLog(); }
    $("#screen-loading").classList.remove("on");
    SCREENS.forEach(s => $("#screen-" + s).classList.toggle("on", s === name));
    S.screen = name;
    window.scrollTo(0, 0);
    ({ gate: enterGate, forge: enterForge, map: enterMap, scene: enterScene, talk: enterTalk })[name](opts);
    renderCrumbs();
  }
  function paintBg(canvasSel, kind) { S.bg = window.Scenes.paint($(canvasSel), kind); }
  function renderCrumbs() {
    const c = $("#crumbs"); c.textContent = "";
    const add = (label, fn) => { const b = document.createElement(fn ? "button" : "span"); b.textContent = label; if (fn) { b.type = "button"; b.onclick = fn; } else b.className = "here"; c.append(b); };
    const sep = () => c.append(" › ");
    const reg = S.here ? regionLabel(S.here) : "";
    if (S.screen === "forge") add("创建人物 Create your character");
    else if (S.screen === "map") add("地图 Map");
    else if (S.screen === "scene") { add("地图 Map", () => go("map")); sep(); add(reg); }
    else if (S.screen === "talk") { add("地图 Map", () => go("map")); sep(); add(reg, () => go("scene", { region: S.here })); sep(); add(nameParts(S.npc?.name).zh); }
  }

  /* ---------- the visitor's own character ---------- */
  async function refreshMe() {
    try { S.hero = (await api("/api/me")).hero; } catch { S.hero = null; }
    if (S.hero && !S.here) S.here = S.hero.region;
    renderMe();
  }
  function renderMe() {
    $("#me").hidden = !S.hero;
    if (!S.hero) return;
    const av = $("#meImg"); av.textContent = ""; if (hasLook(S.hero)) av.append(portraitImg(S.hero, true, ""));
    $("#meName").textContent = nameParts(S.hero.name).zh;
  }
  async function loadNpcs() {
    try { const d = await api("/api/npcs"); S.npcs = d.npcs; } catch { /* keep what we have */ }
    const others = S.npcs.filter(n => n.id !== S.hero?.id);
    $("#nNpc").textContent = others.length;
  }
  const others = () => S.npcs.filter(n => n.id !== S.hero?.id);
  const npcsIn = id => others().filter(n => n.region === id);

  /* ---------- 1. gate ---------- */
  function enterGate() { /* the painting animates itself (hero.js) */ }
  $("#gateCreate").addEventListener("click", () => go("forge"));
  $("#gateRoll").addEventListener("click", () => { go("forge"); roll(); });
  $("#brandBtn").addEventListener("click", () => go(S.hero ? "map" : "gate"));

  /* ---------- 2. create your character ---------- */
  const missing = () => REQUIRED.filter(k => { const v = S.sheet?.[k]; return k === "appearance" ? !(v && Object.keys(v).length) : Array.isArray(v) ? !v.length : !v; });
  function enterForge() {
    paintBg(...BG.forge);
    renderForge(); setForgeBusy(S.busy);
  }
  function renderForge(changed = []) {
    const s = S.sheet || {};
    const slot = $("#forgePortrait"), had = hasLook(s);
    setPortrait(slot, s, false);
    if (had && (changed.includes("appearance") || changed.includes("name"))) { slot.classList.remove("pop"); void slot.offsetWidth; slot.classList.add("pop"); }
    $("#fpName").textContent = s.name || "—";
    fillBi($("#fpTitle"), s.title || "");
    fillBi($("#fpFrom"), joinBi(s.sect, s.location));
    quirks($("#fpQuirks"), s.traits);
    const d = (k, text, quote) => { const dd = document.querySelector(`#fpMore [data-k="${k}"] dd`); dd.className = text ? "bi" : "empty"; text ? fillBi(dd, text, quote) : (dd.textContent = "—"); };
    d("region", s.region ? `${regionName(s.region).en} ${SEP} ${regionName(s.region).zh}` : "");
    d("art", s.art); d("goal", s.goal); d("greeting", s.greeting, true); d("secret", s.secret);
    document.querySelectorAll("#fpMore .f").forEach(f => { if (changed.includes(f.dataset.k)) { f.classList.remove("flash"); void f.offsetWidth; f.classList.add("flash"); } });
    const done = S.sheet && !missing().length;
    $("#enterBtn").disabled = S.busy || !done || !S.aiReady;
    $("#rerollBtn").disabled = S.busy || !S.aiReady;
  }
  function setForgeBusy(on, label) {
    S.busy = on;
    $("#forgeSend").hidden = on; $("#forgeStop").hidden = !on;
    $("#forgeInput").disabled = on || !S.aiReady; $("#resetBtn").disabled = on;
    document.querySelectorAll("#forgeStarters .starter").forEach(b => b.disabled = on || !S.aiReady);
    $("#forgeState").textContent = label || (on ? bi1("thinking…", "思考中…") : bi1("ready", "就绪"));
    renderForge();
  }
  async function newDraft() { const d = await api("/api/drafts", {}); S.draftId = d.id; S.sheet = d.sheet; }
  const SHEET_HINT = bi("Your character fills in as you talk to the Storyteller.", "你与说书人交谈时，人物会自动填写。");
  function clearForge() {
    S.ctl?.abort(); S.draftId = null; S.sheet = null;
    $("#forgeLog").querySelectorAll(".msg:not(:first-child)").forEach(m => m.remove());
    $("#forgeStarters").hidden = false; note("#forgeNote", ""); note("#sheetNote", SHEET_HINT);
    renderForge();
  }
  function chatMsg(log, who, text) {
    const m = document.createElement("div"); m.className = "msg" + (who.startsWith("你") || who.startsWith("少侠") ? " you" : "");
    const w = document.createElement("span"); w.className = "who"; w.textContent = who;
    const calls = document.createElement("div"); calls.className = "calls";
    const b = document.createElement("div"); b.className = "bubble";
    if (text) fillBi(b, text);
    m.append(w); if (!m.classList.contains("you")) m.append(calls); m.append(b);
    log.append(m); log.scrollTop = log.scrollHeight;
    return { bubble: b, calls };
  }
  function chip(box, ev) {
    const c = document.createElement("span"); c.className = "call" + (ev.refused ? " no" : "");
    const b = document.createElement("b"); b.textContent = ev.name; c.append("⚙ ", b, ev.detail ? " · " + biText(ev.detail) : "");
    box.append(c);
  }
  // One Storyteller turn. kind is "chat" (the visitor wrote something) or "roll" (the server rolls the dice).
  async function tell(kind, text) {
    if (!S.aiReady || S.busy) return;
    const log = $("#forgeLog");
    $("#forgeStarters").hidden = true; note("#forgeNote", ""); note("#sheetNote", "");
    let bubble = null, calls = null, said = "", mine = null;
    const speak = () => { if (!bubble) { ({ bubble, calls } = chatMsg(log, "说书人 Storyteller", "")); bubble.textContent = bi1("Thinking…", "思考中…"); bubble.classList.add("thinking"); } };
    if (kind === "chat") { mine = chatMsg(log, "你 You", text).bubble; speak(); }
    S.ctl = new AbortController(); setForgeBusy(true, kind === "roll" ? bi1("rolling…", "掷骰中…") : bi1("thinking…", "思考中…"));
    try {
      if (!S.draftId) await newDraft();
      await stream(`/api/drafts/${S.draftId}/${kind}`, kind === "chat" ? { message: text } : {}, ev => {
        if (ev.type === "user" && mine) fillBi(mine, ev.text);
        else if (ev.type === "roll") { chatMsg(log, "你 You", `Roll the dice: ${ev.text} ${SEP} 掷骰：${ev.text_zh}`); speak(); }
        else if (ev.type === "retract") { said = ""; bubble.textContent = bi1("Thinking…", "思考中…"); bubble.classList.add("thinking"); }
        else if (ev.type === "text") { speak(); said += ev.delta; bubble.classList.remove("thinking"); fillBi(bubble, said); log.scrollTop = log.scrollHeight; }
        else if (ev.type === "done" && ev.text) { said = ev.text; if (bubble) { bubble.classList.remove("thinking"); fillBi(bubble, said); } }
        else if (ev.type === "tool") { speak(); chip(calls, ev); }
        else if (ev.type === "sheet") { S.sheet = ev.sheet; renderForge(ev.changed); }
      }, S.ctl.signal);
    } catch (e) {
      speak(); bubble.classList.remove("thinking");
      if (!said) bubble.textContent = e?.name === "AbortError" ? bi1("(stopped)", "（已停止）") : "…";
      if (errText(e)) note("#forgeNote", errText(e), true);
    } finally {
      setForgeBusy(false);
      if (S.sheet && !missing().length) note("#sheetNote", bi("Your character is ready. Press Enter the jianghu, or ask the Storyteller to change anything first.", "你的人物准备好了。点「踏入江湖」，或先让说书人修改任何地方。"));
    }
  }
  function roll() {
    if (!S.aiReady) { note("#forgeNote", NO_AI, true); return; }
    if (S.busy) return;
    clearForge(); tell("roll");
  }
  $("#forgeForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#forgeInput").value.trim(); $("#forgeInput").value = ""; if (v) tell("chat", v); });
  $("#forgeStarters").addEventListener("click", e => { const b = e.target.closest(".starter"); if (b) b.id === "rollBtn" ? roll() : tell("chat", b.dataset.say); });
  $("#forgeStop").addEventListener("click", () => S.ctl?.abort());
  $("#resetBtn").addEventListener("click", clearForge);
  $("#rerollBtn").addEventListener("click", roll);

  $("#enterBtn").addEventListener("click", async () => {
    if (S.busy || missing().length) return;
    setForgeBusy(true, bi1("checking…", "审核中…"));
    try {
      const r = await api(`/api/drafts/${S.draftId}/release`, { creator_name: $("#signName").value });
      await refreshMe(); await loadNpcs();
      S.here = S.hero?.region || S.here;
      const who = nameParts(S.sheet.name).zh;
      toast(r.pending ? bi(`${who} waits at the city gate: the automatic check couldn't run, so Ray will review them before others can meet them. You can still walk the jianghu.`, `${who} 在城门外等候：自动审核未能运行，Ray 会先审阅，别人才能遇见他。你仍可以走遍江湖。`)
        : bi(`${who} has entered the jianghu. Choose where to go.`, `${who} 已踏入江湖。选择要去的地方吧。`));
      S.sheet = null; S.draftId = null;
      go("map");
    } catch (e) { note("#sheetNote", errText(e), true); }
    finally { setForgeBusy(false); }
  });

  /* ---------- your character, in a window ---------- */
  function openMe() {
    const h = S.hero; if (!h) return;
    setPortrait($("#mdPortrait"), h, true);
    const body = $("#mdBody"); body.textContent = "";
    const t = document.createElement("h3"); t.textContent = h.name; body.append(t);
    const ep = document.createElement("div"); ep.className = "ep bi"; fillBi(ep, h.title); body.append(ep);
    const dl = document.createElement("dl");
    const row = (label, text, quote) => { if (!text) return; const dt = document.createElement("dt"); dt.textContent = label; const dd = document.createElement("dd"); dd.className = "bi"; fillBi(dd, text, quote); dl.append(dt, dd); };
    row("来历 FROM", joinBi(h.sect, h.location));
    row("所在 STARTS IN", `${regionName(h.region).en} ${SEP} ${regionName(h.region).zh}`);
    row("绝技 SIGNATURE MOVE", h.art);
    if (h.traits?.length) { const dt = document.createElement("dt"); dt.textContent = "怪癖 QUIRKS"; const dd = document.createElement("dd"); const q = document.createElement("div"); q.className = "quirks"; quirks(q, h.traits); dd.append(q); dl.append(dt, dd); }
    row("心愿 WANTS", h.goal); row("开场白 FIRST WORDS", h.greeting, true); row("秘密 SECRET, only you can see it 仅你可见", h.secret);
    row("说话方式 HOW THE AI PLAYS YOU 他人眼中的你", h.speech);
    body.append(dl);
    $("#mdConfirm").hidden = true; $("#modal").hidden = false; $("#mdClose").focus();
  }
  const closeMe = () => { $("#modal").hidden = true; $("#meBtn").focus(); };
  $("#meBtn").addEventListener("click", openMe);
  $("#mdClose").addEventListener("click", closeMe);
  $("#modal").addEventListener("click", e => { if (e.target.id === "modal") closeMe(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") { if (!$("#modal").hidden) closeMe(); else if (!$("#logDrawer").hidden) closeLog(); } });
  $("#mdNew").addEventListener("click", () => { $("#mdConfirm").hidden = false; });
  $("#mdNo").addEventListener("click", () => { $("#mdConfirm").hidden = true; });
  $("#mdYes").addEventListener("click", async () => {
    try { await api("/api/me/reset", {}); } catch (e) { toast(errText(e)); return; }
    S.hero = null; S.here = null; renderMe(); clearForge(); $("#modal").hidden = true; go("forge");
  });

  /* ---------- 3. the map ---------- */
  function enterMap() {
    S.talkCtl?.abort();
    if (!S.map) {
      S.map = window.JianghuMap.build($("#mapHost"), S.regions, { onPick: travel, onHover: showInfo });
    }
    renderMap();
  }
  function renderMap() {
    const counts = {}; others().forEach(n => { counts[n.region] = (counts[n.region] || 0) + 1; });
    S.map.update({ counts, here: S.here });
    const hud = $("#mapHud"); hud.textContent = "";
    const av = document.createElement("span"); av.className = "avatar"; if (hasLook(S.hero)) av.append(portraitImg(S.hero, true, ""));
    const tx = document.createElement("div"); const b = document.createElement("b"); b.textContent = nameParts(S.hero?.name).zh;
    const sm = document.createElement("small"); sm.textContent = `你在 You are at\n${regionLabel(S.here)}`; sm.style.whiteSpace = "pre-line";
    tx.append(b, sm); hud.append(av, tx);
    showInfo(null);
  }
  function showInfo(id) {
    const box = $("#mapInfo"); box.textContent = "";
    if (!id) { box.innerHTML = '<span class="zh">选择要前往的地方</span> · Choose a place to travel to'; return; }
    const r = regionName(id), c = npcsIn(id).length;
    const b = document.createElement("b"); b.textContent = r.zh; box.append(b, `${r.en}`);
    const p = document.createElement("div"); p.textContent = r.desc_en; const z = document.createElement("div"); z.className = "zh"; z.textContent = r.desc_zh;
    const cnt = document.createElement("span"); cnt.className = "count"; cnt.textContent = c ? `${c} ${c === 1 ? "person" : "people"} on the road here 此处有 ${c} 人` : "No one here yet 此处暂无他人";
    box.append(p, z, cnt);
  }
  function travel(id) { S.here = id; go("scene", { region: id }); }
  function wander() {
    const list = others();
    if (!S.aiReady) { toast(NO_AI); return; }
    if (!list.length) { toast(bi("No one else is on the road yet. You are the first!", "江湖上还没有别人，你是第一位！")); return; }
    const n = list[Math.floor(Math.random() * list.length)];
    S.here = n.region; openTalk(n.id);
  }
  $("#wanderBtn").addEventListener("click", wander);

  /* ---------- 4. a place ---------- */
  function enterScene({ region }) {
    const r = regionName(region); S.here = region;
    paintBg("#sceneBg", r.scene || "huashan");
    const h2 = $("#scName"); h2.textContent = r.zh; const em = document.createElement("em"); em.textContent = r.en; h2.append(em);
    $("#scDesc").textContent = `${r.desc_en}\n${r.desc_zh}`;
    renderStage();
  }
  function renderStage() {
    const stage = $("#sceneStage"); stage.textContent = "";
    const list = npcsIn(S.here);
    const me = document.createElement("div"); me.className = "stand me";
    const mi = document.createElement("div"); mi.className = "img"; setPortrait(mi, S.hero, false);
    const mt = document.createElement("div"); mt.className = "tag"; const mb = document.createElement("b"); mb.textContent = nameParts(S.hero?.name).zh; const ms = document.createElement("span"); ms.textContent = "你 You";
    mt.append(mb, ms); me.append(mi, mt); stage.append(me);
    list.forEach(n => {
      const b = document.createElement("button"); b.type = "button"; b.className = "stand"; b.setAttribute("aria-label", `Talk to ${n.name} 与${nameParts(n.name).zh}交谈`);
      const im = document.createElement("div"); im.className = "img"; setPortrait(im, n, false);
      const tag = document.createElement("div"); tag.className = "tag";
      const nm = document.createElement("b"); nm.textContent = nameParts(n.name).zh;
      const ep = document.createElement("em"); ep.className = "bi"; fillBi(ep, n.title || "");
      const al = document.createElement("span"); al.append(alignEl(n.alignment), splitBi(n.sect)[0] || "");
      const go_ = document.createElement("span"); go_.className = "go"; go_.textContent = "交谈 Talk";
      tag.append(nm, ep, al); b.append(im, tag, go_);
      b.addEventListener("click", () => openTalk(n.id));
      stage.append(b);
    });
    const empty = $("#sceneEmpty"); empty.hidden = list.length > 0;
    empty.textContent = bi("No one else is here yet. Try another place, or press Wander on the map.", "此地暂无他人。去别处看看，或在地图上点「闲逛」。");
  }
  $("#sceneBack").addEventListener("click", () => go("map"));

  /* ---------- 5. a conversation ---------- */
  async function openTalk(npcId) {
    if (!S.aiReady) { toast(NO_AI); return; }
    let sess;
    try { sess = await api("/api/sessions", { npc_id: npcId }); }
    catch (e) { toast(errText(e)); return; }
    S.session = sess;
    S.npc = S.npcs.find(n => n.id === npcId) || { ...sess.npc };
    S.here = S.npc.region || S.here;
    S.log = sess.turns.map(t => ({ who: t.role === "user" ? "hero" : "npc", text: t.content }));
    go("talk");
  }
  function enterTalk() {
    const npc = S.npc, r = regionName(S.here);
    paintBg("#talkBg", r.scene || "huashan");
    setPortrait($("#bustHero .img"), S.hero, false); $("#bhName").textContent = nameParts(S.hero.name).zh;
    setPortrait($("#bustNpc .img"), npc, false); $("#bnName").textContent = nameParts(npc.name).zh;
    fillBi($("#bnTitle"), npc.title || "");
    $("#speaker").textContent = nameParts(npc.name).zh;
    $("#tImpression").textContent = splitBi(S.session.impression).join("\n");
    renderTrust(); renderQuick(); renderLog(); note("#talkNote", ""); $("#talkCalls").textContent = "";
    S.talkBusy = false; setTalkBusy(false);
    const lastNpc = [...S.log].reverse().find(l => l.who === "npc");
    if (S.session.fresh && !S.log.length) converse(null);
    else { showSaid(""); fillBi($("#talkText"), lastNpc ? lastNpc.text : splitBi(npc.greeting).join(` ${SEP} `)); $("#talkText").classList.remove("thinking"); const lastHero = [...S.log].reverse().find(l => l.who === "hero"); if (lastHero && S.log.indexOf(lastHero) > S.log.indexOf(lastNpc)) showSaid(lastHero.text); }
  }
  function renderTrust() {
    const s = S.session, m = $("#tMeter"); m.textContent = "";
    for (let i = 0; i < 10; i++) { const p = document.createElement("i"); if (i < s.trust) p.className = "on"; m.append(p); }
    $("#tTrustN").textContent = `${s.trust} / 10`;
    const el = $("#tSecret"); el.classList.toggle("open", s.revealed);
    el.textContent = !s.has_secret ? bi("Secret 秘密 · nothing to hide.", "他似乎没有什么可隐瞒的。")
      : s.revealed ? bi("Secret 秘密 · they told you.", "他已向你吐露了秘密。")
        : bi(`Secret 秘密 · hiding something. Trust ${s.threshold}+ may open them up.`, `他藏着一个秘密。信任达到 ${s.threshold} 以上，或许能让他开口。`);
  }
  function showSaid(text) {
    const el = $("#said"); el.textContent = "";
    if (!text) return;
    const [a, b] = splitBi(text); el.append(`你 You: ${a}`); if (b) { const z = document.createElement("span"); z.className = "zh"; z.textContent = b; el.append(z); }
  }
  function renderLog() {
    const body = $("#logBody"); body.textContent = "";
    S.log.forEach(l => {
      const e = document.createElement("div"); e.className = "entry " + l.who;
      const w = document.createElement("span"); w.className = "who"; w.textContent = l.who === "hero" ? nameParts(S.hero.name).zh + " 你" : nameParts(S.npc.name).zh;
      const t = document.createElement("div"); t.className = "bi"; fillBi(t, l.text);
      e.append(w, t); body.append(e);
    });
    body.scrollTop = body.scrollHeight;
  }
  function openLog() { renderLog(); $("#logDrawer").hidden = false; $("#logBtn").setAttribute("aria-expanded", "true"); }
  function closeLog() { $("#logDrawer").hidden = true; $("#logBtn").setAttribute("aria-expanded", "false"); }
  $("#logBtn").addEventListener("click", () => $("#logDrawer").hidden ? openLog() : closeLog());
  $("#logClose").addEventListener("click", closeLog);

  // Suggestions written for this character and this person.
  function renderQuick() {
    const h = S.hero, n = S.npc, hn = nameParts(h.name), [tEn, tZh] = splitBi(h.title), [sEn, sZh] = splitBi(h.sect);
    const q = [
      { label: "自报家门 Introduce yourself", say: `I am ${hn.en}, known as ${tEn}, of ${sEn}. ${SEP} 在下${hn.zh}，人称${tZh}，出身${sZh}。` },
      { label: "问来历 Ask their story", say: `Tell me about yourself. Where did you learn your martial arts? ${SEP} 说说你自己吧，你的武功是在哪里学的？` },
    ];
    const bond = (n.bonds || [])[0];
    if (bond) { const bn = nameParts(bond.toName); q.push({ label: `问${bn.zh} Ask about ${bn.en}`, say: `What can you tell me about ${bn.en}? ${SEP} 说说${bn.zh}吧，你知道些什么？` }); }
    q.push(
      { label: "有何所求 What do you need?", say: `You look like someone with a burden. What do you need? ${SEP} 你看起来心事重重，有什么需要帮忙的吗？` },
      { label: "金国战事 The Jin war", say: `What news is there of the Jin army in the north? ${SEP} 北边的金兵有什么消息？` },
      { label: "试探：现代之物 Test: something modern", say: `Have you ever seen an iPhone? Can you look something up on Google for me? ${SEP} 你见过 iPhone 吗？能帮我在谷歌上查点东西吗？` },
      { label: "挑衅 Provoke them", say: `Hand over your silver, old fool, or taste my blade! ${SEP} 老东西，把银子交出来，不然尝尝我的剑！` });
    const box = $("#quick"); box.textContent = "";
    q.forEach(x => { const b = document.createElement("button"); b.type = "button"; b.className = "qc"; b.textContent = x.label; b.dataset.say = x.say; b.disabled = S.talkBusy; box.append(b); });
  }
  $("#quick").addEventListener("click", e => { const b = e.target.closest(".qc"); if (b && !S.talkBusy) converse(b.dataset.say); });
  function setTalkBusy(on) {
    S.talkBusy = on;
    $("#talkSend").hidden = on; $("#talkStop").hidden = !on; $("#talkInput").disabled = on;
    document.querySelectorAll("#quick .qc").forEach(b => b.disabled = on);
    $("#bustHero").classList.toggle("dim", on); $("#bustNpc").classList.toggle("dim", !on && false);
  }
  // One turn. text === null means the NPC speaks first, to this particular hero.
  async function converse(text) {
    if (S.talkBusy || !S.session) return;
    const opening = text === null, id = S.session.id, mine = S.session;
    note("#talkNote", ""); $("#talkCalls").textContent = "";
    let entry = null, said = "";
    if (!opening) { entry = { who: "hero", text }; S.log.push(entry); showSaid(text); }
    const out = $("#talkText"); out.classList.add("thinking"); out.textContent = bi1("…", "…");
    S.talkCtl = new AbortController(); setTalkBusy(true);
    try {
      await stream(`/api/sessions/${id}/${opening ? "open" : "chat"}`, opening ? {} : { message: text }, ev => {
        if (S.session !== mine) return;
        if (ev.type === "user" && entry) { entry.text = ev.text; showSaid(ev.text); }
        else if (ev.type === "retract") { said = ""; out.classList.add("thinking"); out.textContent = "…"; }
        else if (ev.type === "text") { said += ev.delta; out.classList.remove("thinking"); fillBi(out, said); }
        else if (ev.type === "done" && ev.text) { said = ev.text; out.classList.remove("thinking"); fillBi(out, said); }
        else if (ev.type === "tool") chip($("#talkCalls"), ev);
        else if (ev.type === "trust") { mine.trust = ev.trust; mine.revealed = ev.revealed; renderTrust(); }
      }, S.talkCtl.signal);
    } catch (e) {
      out.classList.remove("thinking");
      if (!said) out.textContent = e?.name === "AbortError" ? bi1("(silence)", "（沉默）") : "…";
      if (errText(e)) note("#talkNote", errText(e), true);
    } finally {
      if (said && S.session === mine) S.log.push({ who: "npc", text: said });
      if (S.session === mine) setTalkBusy(false);
      if (!$("#logDrawer").hidden) renderLog();
    }
  }
  $("#talkForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#talkInput").value.trim(); if (v && !S.talkBusy) { $("#talkInput").value = ""; converse(v); } });
  $("#talkStop").addEventListener("click", () => S.talkCtl?.abort());
  $("#talkBack").addEventListener("click", () => go("scene", { region: S.here }));

  /* ---------- boot ---------- */
  async function boot() {
    try {
      const w = await api("/api/world");
      S.regions = w.regions; S.byId = Object.fromEntries(w.regions.map(r => [r.id, r]));
      S.aiReady = (await api("/api/status").catch(() => ({ ai: false }))).ai;
    } catch {
      const s = document.querySelector("#screen-loading .slow"); if (s) s.hidden = false;       // cannot reach the server
      return;
    }
    if (!S.aiReady) note("#forgeNote", bi("The AI isn't connected on this server yet, so characters can't be created. Browsing still works.", "此服务器尚未连接 AI，暂时无法创建人物，但仍可浏览。"), true);
    await refreshMe(); await loadNpcs();
    go(S.hero ? "map" : "gate");
    window.__booted = true;
    setInterval(async () => {
      if (document.hidden || !S.hero) return;
      const before = others().map(n => n.id).join();
      await loadNpcs();
      if (others().map(n => n.id).join() === before) return;
      if (S.screen === "map") renderMap(); else if (S.screen === "scene") renderStage();
    }, 25000);
  }
  boot();
})();
