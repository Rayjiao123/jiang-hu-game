(() => {
  "use strict";
  const REQUIRED = ["name", "title", "path", "temperament", "art", "quirk", "beloved_name", "beloved_bond", "beloved_token", "appearance"];
  const ALIGN = { orthodox: ["正", "a-orthodox", "orthodox"], unorthodox: ["邪", "a-unorthodox", "unorthodox"], neutral: ["中", "a-neutral", "neutral"] };
  const SIL = '<svg class="sil" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="34" r="18" fill="#2a2118"/><path d="M12 98c2-24 18-40 38-40s36 16 38 40z" fill="#2a2118"/></svg>';
  const $ = s => document.querySelector(s);
  const HERE = "huashan";                 // the one open place

  const S = { aiReady: false, regions: [], byId: {}, info: null, game: null, hero: null, sheet: null, screen: null, npc: null, session: null, log: [],
              busy: false, ctl: null, talkBusy: false, talkCtl: null, bg: null, map: null, editing: null };

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
  const nameParts = name => { const m = String(name || "").match(/^((?:[一-鿿·]+\s*)+)(.*)$/); return m ? { zh: m[1].trim(), en: m[2].trim() || m[1].trim() } : { zh: String(name || ""), en: String(name || "") }; };
  // Fill an element with an English block and a Chinese block. quote wraps each in curly quotes.
  function fillBi(el, text, quote = false) {
    el.textContent = "";
    const [a, b] = splitBi(text);
    const add = (cls, t) => { if (!t) return; const d = document.createElement("div"); d.className = cls; d.textContent = quote ? `“${t}”` : t; el.append(d); };
    if (b) { add("en", a); add("zh", b); } else add(langOf(a) === "zh" ? "zh" : "en", a);
  }
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const regionName = id => S.byId[id] || { en: "the jianghu", zh: "江湖" };
  const regionLabel = id => { const r = regionName(id); return `${r.zh} ${r.en}`; };

  let toastTimer = 0;
  function toast(msg, ms = 4600) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("on"), ms); }
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
  function portraitImg(c, bg, alt, aura = true) {
    const i = new Image(); i.alt = alt || ""; i.src = svgUrl(window.renderPortrait(c.appearance, c.name || "", { bg, aura })); return i;
  }
  function setPortrait(box, c, bg = false, aura = true) {
    box.textContent = "";
    if (hasLook(c)) box.append(portraitImg(c, bg, splitBi(c.name)[0], aura)); else box.innerHTML = SIL;
  }
  const alignEl = a => { const d = ALIGN[a] || ALIGN.neutral; const s = el("span", "align " + d[1], d[0]); s.title = d[2]; return s; };

  /* ---------- screens ---------- */
  const SCREENS = ["gate", "forge", "map", "scene", "talk"];
  const BG = { forge: ["#forgeBg", "wudang"] };
  function go(name, opts = {}) {
    if (S.bg) { S.bg.stop(); S.bg = null; }
    if (name !== "talk") { S.talkCtl?.abort(); closeLog(); }
    $("#screen-loading").classList.remove("on");
    $("#aboutBtn").hidden = name === "gate";
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
    if (S.screen === "forge") add("创建人物 Create your hero");
    else if (S.screen === "map") add("地图 Map");
    else if (S.screen === "scene") { add("地图 Map", () => go("map")); sep(); add(regionLabel(HERE)); }
    else if (S.screen === "talk") { add("地图 Map", () => go("map")); sep(); add(regionLabel(HERE), () => go("scene")); sep(); add(nameParts(S.npc?.name).zh); }
  }

  /* ---------- the case, and the hero who is working on it ---------- */
  const stage = () => S.game?.stage || null;
  const playing = () => ["playing", "accused"].includes(stage());
  const cast = () => S.game?.cast || [];
  const found = () => S.game?.found || [];
  function setGame(g) {
    S.game = g; S.hero = g?.hero || null;
    renderMe();
  }
  function renderMe() {
    const on = !!S.hero && stage() !== "creating";
    $("#me").hidden = !on;
    $("#caseBtn").hidden = !playing();
    if (playing()) $("#caseBtn").textContent = `案卷 Case file · ${found().length}`;
    if (!on) return;
    const av = $("#meImg"); av.textContent = ""; if (hasLook(S.hero)) av.append(portraitImg(S.hero, true, ""));
    $("#meName").textContent = nameParts(S.hero.name).zh;
  }
  async function refreshGame() { setGame((await api("/api/game")).game); }
  const heroBond = h => { const [a, b] = splitBi(h?.beloved_bond); return { en: a || "loved one", zh: b || a || "爱人" }; };
  const belovedName = h => nameParts(h?.beloved_name);

  /* ---------- 1. gate: a landing page that shows what the game is ---------- */
  const SAMPLE_LOOK = { build: "feminine", age: "young", skin: "fair", hair_style: "long", hair_color: "black", eyes: "soft", eye_color: "brown", expression: "smile", outfit: "robe", outfit_color: "pink", accent_color: "white", headwear: "hairpin", mark: "none", weapon: "flute", aura: "petals", scene: "bamboo" };
  const SAMPLE_TALK = [
    ["you", `Innkeeper, were you at the inn the night my betrothed died? ${SEP} 掌柜，我未婚妻死的那夜，你在客栈吗？`],
    ["npc", `*wipes a cup that is already clean* Where else would an old man be, little guest? ...Why do you ask so quietly? ${SEP} *擦着一只早就干净的杯子* 老头子还能在哪儿，小客官？……你问得这么轻，是为什么？`],
  ];
  function beginCreate() { playing() ? go("scene") : go("forge"); }
  function enterGate() { renderGate(); }
  function renderGate() {
    const back = playing();
    $("#gateCreate").textContent = $("#gateCreate2").textContent = back ? "回到华山 · Back to Mount Hua" : "创建你的侠客 · Create your hero";
    $("#gateRoll").hidden = back;
    const people = S.info?.cast || [];
    const row = $("#gateCast"); row.textContent = "";
    ["su", "xie", "leng"].map(k => people.find(n => n.key === k)).filter(Boolean).forEach(n => { const d = el("div", "bu"); setPortrait(d, n, false, false); row.append(d); });
    const a1 = $("#howArt1"); a1.textContent = ""; a1.append(portraitImg({ appearance: SAMPLE_LOOK, name: "sample" }, true, ""));
    const mock = $("#howArt3"); mock.textContent = "";
    SAMPLE_TALK.forEach(([who, t]) => { const d = el("div", "l " + who); fillBi(d, t); mock.append(d); });
    const list = $("#meetRow"); list.textContent = "";
    people.forEach(n => {
      const b = el("button", "meet-card"); b.type = "button"; b.setAttribute("aria-label", `${n.name}: meet them`);
      const pic = el("div", "pic"); if (hasLook(n)) pic.append(portraitImg(n, true, ""));
      const ep = el("div", "ep bi"); fillBi(ep, n.title || "");
      const q = el("div", "q bi"); fillBi(q, n.public || "");
      b.append(pic, el("b", "", nameParts(n.name).zh), ep, q); b.addEventListener("click", () => meetFromGate(n)); list.append(b);
    });
    if (!S.gateMap) S.gateMap = window.JianghuMap.build($("#gateMap"), S.regions, { onPick: id => id === HERE ? beginCreate() : toast(lockedMsg(id)) });
    S.gateMap.update({ counts: { [HERE]: people.length }, here: null });
  }
  const lockedMsg = id => bi(`${regionName(id).en} isn't open yet. This story takes place on Mount Hua; the other places open later.`, `${regionName(id).zh}尚未开放。这个故事发生在华山，其他地方之后陆续开放。`);
  function meetFromGate(n) {
    if (playing()) { openTalk(n.key); return; }
    toast(bi("Create your hero first, then you can question them.", "先创建你的人物，才能向他们问话。"));
    go("forge");
  }
  $("#gateCreate").addEventListener("click", beginCreate);
  $("#gateCreate2").addEventListener("click", beginCreate);
  $("#gateRoll").addEventListener("click", () => { go("forge"); roll(); });
  $("#brandBtn").addEventListener("click", () => go(playing() ? "scene" : "gate"));
  $("#aboutBtn").addEventListener("click", () => go("gate"));

  /* ---------- 2. create your hero, then review every trait before going in ---------- */
  const missing = () => REQUIRED.filter(k => { const v = S.sheet?.[k]; return k === "appearance" ? !(v && Object.keys(v).length) : !v; });
  const PICKS = {
    path: [["orthodox", "正", "Orthodox", "You walk with the righteous sects. They respect you; the unorthodox distrust you.", "你与名门正派同路。正派敬重你，邪派提防你。"],
           ["unorthodox", "邪", "Unorthodox", "You are an outcast or a feared name. Outcasts warm to you; the righteous sects distrust you.", "你是被排斥或令人畏惧的人。同道中人亲近你，名门正派提防你。"],
           ["neutral", "中", "Neutral", "You belong to no side. Nobody knows quite what to make of you.", "你不属于任何一方，没人看得透你。"]],
    temperament: [["wry", "戏谑", "Wry", "Wit and teasing.", "爱开玩笑，话里带笑。"], ["gentle", "温和", "Gentle", "Soft-spoken and kind.", "温声细语，待人宽厚。"],
                  ["blunt", "直率", "Blunt", "Says exactly what you mean.", "心直口快，有话直说。"], ["proud", "骄傲", "Proud", "Head high, never bows first.", "昂首挺胸，从不先低头。"],
                  ["cool", "冷峻", "Cool", "Calm, sparing with words.", "沉着冷静，惜字如金。"], ["cunning", "机敏", "Cunning", "Quick, watchful, always thinking.", "反应极快，处处留心。"]],
  };
  const ROWS = [
    { id: "who", zh: "名号", en: "Name", fields: ["name", "title"] },
    { id: "path", zh: "道", en: "Path", fields: ["path"], hint: ["Changes how people on the mountain greet you.", "决定山上的人如何对待你。"] },
    { id: "temperament", zh: "性情", en: "Manner", fields: ["temperament"], hint: ["Changes who warms to you.", "决定谁会对你敞开心扉。"] },
    { id: "art", zh: "绝技", en: "Signature move", fields: ["art"] },
    { id: "quirk", zh: "习癖", en: "Quirk", fields: ["quirk"], hint: ["The habit people remember you by.", "别人记住你的小习惯。"] },
    { id: "beloved", zh: "爱人", en: "The one you lost", fields: ["beloved_name", "beloved_bond", "beloved_token"], hint: ["Why you are here.", "你来这里的原因。"] },
  ];
  const FIELD = {
    name: ["名", "Name", "中文名 + pinyin, e.g. 柳寒烟 Liu Hanyan"], title: ["号", "Epithet", "e.g. Lantern Sword, or 灯剑"],
    art: ["", "", "A move and what it does, in English or 中文. We add the other language."], quirk: ["", "", "A habit, 2-6 words, in English or 中文"],
    beloved_name: ["姓名", "Name", "中文名 + pinyin, e.g. 沈映雪 Shen Yingxue"], beloved_bond: ["关系", "To you", "e.g. betrothed, wife, 青梅竹马"], beloved_token: ["信物", "Keepsake", "e.g. a jade hairpin, or 一支玉簪"],
  };
  function enterForge() {
    paintBg(...BG.forge);
    renderForge(); setForgeBusy(S.busy);
  }
  function pickLabel(field, v) { const p = (PICKS[field] || []).find(x => x[0] === v); return p ? `${p[1]} ${p[2]}` : ""; }
  function renderForge(changed = []) {
    const s = S.sheet || {};
    const slot = $("#forgePortrait"), had = hasLook(s);
    setPortrait(slot, s, false);
    if (had && (changed.includes("appearance") || changed.includes("name"))) { slot.classList.remove("pop"); void slot.offsetWidth; slot.classList.add("pop"); }
    $("#fpName").textContent = nameParts(s.name).zh || "—";
    fillBi($("#fpTitle"), s.title || "");
    renderTraits(changed);
    const done = S.sheet && !missing().length;
    $("#enterBtn").disabled = S.busy || !done || !!S.editing;
    $("#rerollBtn").disabled = S.busy || !S.aiReady;
    $("#traits").hidden = !S.sheet || !Object.values(S.sheet).some(v => v && (typeof v !== "object" || Object.keys(v).length));
  }
  function renderTraits(changed = []) {
    const box = $("#traitList"); box.textContent = "";
    const s = S.sheet || {};
    ROWS.forEach(row => {
      const r = el("div", "trait"); r.dataset.id = row.id;
      if (row.fields.some(f => changed.includes(f))) r.classList.add("flash");
      const head = el("div", "t-head"); head.append(el("b", "", row.zh), el("span", "", row.en));
      const editing = S.editing === row.id;
      if (!editing) { const ed = el("button", "edit", "✎ 修改 Edit"); ed.type = "button"; ed.disabled = S.busy || !S.sheet || missing().length === REQUIRED.length; ed.addEventListener("click", () => { S.editing = row.id; renderForge(); }); head.append(ed); }
      r.append(head);
      if (editing) r.append(editForm(row)); else r.append(showRow(row, s));
      if (row.hint && !editing) { const h = el("div", "t-hint"); h.textContent = bi(row.hint[0], row.hint[1]); r.append(h); }
      box.append(r);
    });
  }
  function showRow(row, s) {
    const d = el("div", "t-val");
    const text = f => { const v = s[f]; return v || ""; };
    if (row.id === "who") { const n = nameParts(s.name); d.append(el("div", "big", n.zh && n.en && n.zh !== n.en ? `${n.zh} ${n.en}` : (s.name || "—"))); const t = el("div", "bi"); fillBi(t, s.title || ""); d.append(t); }
    else if (row.id === "path") { const v = s.path; if (v) { const c = el("div", "pick-now"); c.append(alignEl(v), pickLabel("path", v)); d.append(c, el("div", "t-desc", bi(PICKS.path.find(x => x[0] === v)[3], PICKS.path.find(x => x[0] === v)[4]))); } else d.append(el("span", "empty", "—")); }
    else if (row.id === "temperament") { const v = s.temperament; if (v) { const p = PICKS.temperament.find(x => x[0] === v); d.append(el("div", "pick-now", `${p[1]} ${p[2]}`), el("div", "t-desc", bi(p[3], p[4]))); } else d.append(el("span", "empty", "—")); }
    else if (row.id === "beloved") {
      if (!s.beloved_name) d.append(el("span", "empty", "—"));
      else {
        const n = nameParts(s.beloved_name); d.append(el("div", "big", n.zh && n.zh !== n.en ? `${n.zh} ${n.en}` : s.beloved_name));
        const b = el("div", "bi"); fillBi(b, s.beloved_bond || ""); d.append(b);
        if (s.beloved_token) { const k = el("div", "bi key"); fillBi(k, s.beloved_token); const lab = el("small", "", "信物 Keepsake"); d.append(lab, k); }
      }
    }
    else { const t = el("div", "bi"); const v = text(row.fields[0]); if (v) fillBi(t, v); else t.append(el("span", "empty", "—")); d.append(t); }
    return d;
  }
  function editForm(row) {
    const form = el("form", "t-edit"); const s = S.sheet || {}; const inputs = {};
    row.fields.forEach(f => {
      if (PICKS[f]) {
        const g = el("div", "picks"); g.setAttribute("role", "radiogroup");
        PICKS[f].forEach(p => {
          const b = el("button", "pick"); b.type = "button"; b.setAttribute("role", "radio"); b.setAttribute("aria-checked", String(s[f] === p[0])); b.dataset.v = p[0];
          b.append(el("b", "", p[1]), el("span", "", p[2]), el("small", "", bi(p[3], p[4])));
          b.addEventListener("click", () => { g.querySelectorAll(".pick").forEach(x => x.setAttribute("aria-checked", String(x === b))); inputs[f] = { get: () => p[0] }; });
          g.append(b);
        });
        inputs[f] = { get: () => s[f] }; form.append(g);
      } else {
        const lab = el("label", "t-field"); const meta = FIELD[f];
        if (meta[0]) lab.append(el("span", "", `${meta[0]} ${meta[1]}`));
        const inp = el("input"); inp.maxLength = 160; inp.value = FIELD_TEXT(f, s[f]); inp.placeholder = meta[2]; inp.setAttribute("aria-label", meta[0] ? `${meta[0]} ${meta[1]}` : row.zh + " " + row.en);
        lab.append(inp); form.append(lab); inputs[f] = { get: () => inp.value.trim(), orig: inp.value.trim() };
      }
    });
    const bar = el("div", "t-bar"); const msg = el("span", "t-msg");
    const save = el("button", "btn", "保存 Save"); save.type = "submit";
    const cancel = el("button", "btn ghost", "取消 Cancel"); cancel.type = "button"; cancel.addEventListener("click", () => { S.editing = null; renderForge(); });
    bar.append(save, cancel, msg); form.append(bar);
    form.addEventListener("submit", async e => {
      e.preventDefault(); save.disabled = true; msg.textContent = bi1("saving…", "保存中…");
      try {
        for (const f of row.fields) {
          const v = inputs[f].get();
          if (!v || v === (PICKS[f] ? S.sheet[f] : inputs[f].orig)) continue;
          S.sheet = (await api("/api/game/edit", { field: f, value: v })).hero;
        }
        S.editing = null; renderForge(row.fields);
      } catch (err) { msg.textContent = errText(err); msg.classList.add("warn"); save.disabled = false; }
    });
    setTimeout(() => form.querySelector("input, .pick[aria-checked=true], .pick")?.focus(), 0);
    return form;
  }
  // a bilingual value is edited as its English half when there is one, so the visitor changes one thing and gets both languages back
  const FIELD_TEXT = (f, v) => { if (!v) return ""; if (f === "name" || f === "beloved_name") return v; const [a, b] = splitBi(v); return a || b; };

  function setForgeBusy(on, label) {
    S.busy = on;
    $("#forgeSend").hidden = on; $("#forgeStop").hidden = !on;
    $("#forgeInput").disabled = on || !S.aiReady; $("#resetBtn").disabled = on;
    document.querySelectorAll("#forgeStarters .starter").forEach(b => b.disabled = on || !S.aiReady);
    $("#forgeState").textContent = label || (on ? bi1("thinking…", "思考中…") : bi1("ready", "就绪"));
    renderForge();
  }
  async function ensureGame() {
    if (stage() === "creating") return;
    setGame((await api("/api/game/new", {})).game); S.sheet = S.hero;
  }
  const SHEET_HINT = bi("Your hero fills in as you talk to the Storyteller. You can change every trait before you go in.", "你与说书人交谈时，人物会自动填写。进入江湖之前，每一项都可以修改。");
  async function clearForge() {
    S.ctl?.abort(); S.editing = null; S.sheet = null;
    try { await api("/api/game/reset", {}); } catch { /* nothing to reset */ }
    setGame(null);
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
    $("#forgeStarters").hidden = true; note("#forgeNote", ""); note("#sheetNote", ""); S.editing = null;
    let bubble = null, calls = null, said = "", mine = null;
    const speak = () => { if (!bubble) { ({ bubble, calls } = chatMsg(log, "说书人 Storyteller", "")); bubble.textContent = bi1("Thinking…", "思考中…"); bubble.classList.add("thinking"); } };
    if (kind === "chat") { mine = chatMsg(log, "你 You", text).bubble; speak(); }
    S.ctl = new AbortController(); setForgeBusy(true, kind === "roll" ? bi1("rolling…", "掷骰中…") : bi1("thinking…", "思考中…"));
    try {
      await ensureGame();
      await stream(`/api/game/${kind}`, kind === "chat" ? { message: text } : {}, ev => {
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
      if (S.sheet && !missing().length) note("#sheetNote", bi("Your hero is ready. Check every trait above (✎ changes any of them), then press Enter the jianghu.", "你的人物准备好了。看看上面的每一项（点 ✎ 可修改），然后点「踏入江湖」。"));
    }
  }
  function roll() {
    if (!S.aiReady) { note("#forgeNote", NO_AI, true); return; }
    if (S.busy) return;
    S.sheet = null; $("#forgeLog").querySelectorAll(".msg:not(:first-child)").forEach(m => m.remove()); S.editing = null;
    tell("roll");
  }
  $("#forgeForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#forgeInput").value.trim(); $("#forgeInput").value = ""; if (v) tell("chat", v); });
  $("#forgeStarters").addEventListener("click", e => { const b = e.target.closest(".starter"); if (b) b.id === "rollBtn" ? roll() : tell("chat", b.dataset.say); });
  $("#forgeStop").addEventListener("click", () => S.ctl?.abort());
  $("#resetBtn").addEventListener("click", clearForge);
  $("#rerollBtn").addEventListener("click", roll);

  $("#enterBtn").addEventListener("click", async () => {
    if (S.busy || missing().length || S.editing) return;
    setForgeBusy(true, bi1("entering…", "入江湖…"));
    try {
      setGame((await api("/api/game/start", {})).game);
      S.sheet = null;
      showPrologue();
    } catch (e) { note("#sheetNote", errText(e), true); }
    finally { setForgeBusy(false); }
  });

  /* ---------- the opening of the story ---------- */
  function showPrologue() {
    const h = S.hero;
    setPortrait($("#plPortrait"), h, true);
    fillBi($("#plText"), S.game.prologue);
    $("#prologue").hidden = false; $("#plGo").focus();
  }
  $("#plGo").addEventListener("click", () => { $("#prologue").hidden = true; go("scene"); });

  /* ---------- your hero, in a window ---------- */
  function openMe() {
    const h = S.hero; if (!h) return;
    setPortrait($("#mdPortrait"), h, true);
    const body = $("#mdBody"); body.textContent = "";
    body.append(el("h3", "", h.name)); const ep = el("div", "ep bi"); fillBi(ep, h.title); body.append(ep);
    const dl = document.createElement("dl");
    const row = (label, text) => { if (!text) return; const dd = el("dd", "bi"); fillBi(dd, text); dl.append(el("dt", "", label), dd); };
    const pa = PICKS.path.find(x => x[0] === h.path), te = PICKS.temperament.find(x => x[0] === h.temperament);
    row("道 PATH", pa ? `${pa[2]} ${SEP} ${pa[1]}` : ""); row("性情 MANNER", te ? `${te[2]} ${SEP} ${te[1]}` : "");
    row("绝技 SIGNATURE MOVE", h.art); row("习癖 QUIRK", h.quirk);
    row("爱人 THE ONE YOU LOST", `${h.beloved_name} · ${splitBi(h.beloved_bond)[0]} ${SEP} ${nameParts(h.beloved_name).zh} · ${splitBi(h.beloved_bond)[1]}`);
    row("信物 KEEPSAKE", h.beloved_token);
    body.append(dl);
    $("#mdConfirm").hidden = true; $("#modal").hidden = false; $("#mdClose").focus();
  }
  const closeMe = () => { $("#modal").hidden = true; $("#meBtn").focus(); };
  $("#meBtn").addEventListener("click", openMe);
  $("#mdClose").addEventListener("click", closeMe);
  $("#modal").addEventListener("click", e => { if (e.target.id === "modal") closeMe(); });
  $("#mdNew").addEventListener("click", () => { $("#mdConfirm").hidden = false; });
  $("#mdNo").addEventListener("click", () => { $("#mdConfirm").hidden = true; });
  $("#mdYes").addEventListener("click", async () => { $("#modal").hidden = true; await newStory(); });
  async function newStory() {
    try { await api("/api/game/reset", {}); } catch (e) { toast(errText(e)); return; }
    closeCase(); closeAccuse(); $("#endModal").hidden = true;
    setGame(null); S.sheet = null; S.npc = null; S.session = null;
    $("#forgeLog").querySelectorAll(".msg:not(:first-child)").forEach(m => m.remove());
    $("#forgeStarters").hidden = false; note("#forgeNote", ""); note("#sheetNote", SHEET_HINT);
    go("forge");
  }

  /* ---------- 3. the map ---------- */
  function enterMap() {
    S.talkCtl?.abort();
    if (!S.map) S.map = window.JianghuMap.build($("#mapHost"), S.regions, { onPick: id => id === HERE ? go("scene") : toast(lockedMsg(id)), onHover: showInfo });
    renderMap();
  }
  function renderMap() {
    S.map.update({ counts: { [HERE]: cast().length }, here: HERE });
    const hud = $("#mapHud"); hud.textContent = "";
    const av = el("span", "avatar"); if (hasLook(S.hero)) av.append(portraitImg(S.hero, true, ""));
    const tx = el("div"); const sm = el("small", "", `你在 You are at\n${regionLabel(HERE)}`); sm.style.whiteSpace = "pre-line";
    tx.append(el("b", "", nameParts(S.hero?.name).zh), sm); hud.append(av, tx);
    showInfo(null);
  }
  function showInfo(id) {
    const box = $("#mapInfo"); box.textContent = "";
    if (!id) { box.innerHTML = '<span class="zh">这个故事发生在华山。点「华山」上山。</span><br>This story takes place on Mount Hua. Tap it to go up.'; return; }
    const r = regionName(id);
    box.append(el("b", "", r.zh), r.en, el("div", "", r.desc_en), el("div", "zh", r.desc_zh), el("span", "count", r.open ? `${cast().length} people to question 可问话之人 ${cast().length}` : "Opens later 即将开放"));
  }
  $("#wanderBtn").addEventListener("click", () => {
    const list = cast();
    if (!S.aiReady) { toast(NO_AI); return; }
    if (list.length) openTalk(list[Math.floor(Math.random() * list.length)].key);
  });

  /* ---------- 4. the place: who is here, and what is known ---------- */
  function enterScene() {
    const r = regionName(HERE);
    paintBg("#sceneBg", r.scene || "huashan");
    const h2 = $("#scName"); h2.textContent = r.zh; h2.append(el("em", "", r.en));
    $("#scDesc").textContent = `${r.desc_en}\n${r.desc_zh}`;
    const news = $("#scNews"); news.textContent = "";
    const official = found().find(c => c.id === "official");
    news.hidden = !official;
    if (official) { news.append(el("b", "", "案情")); const t = el("div", "bi"); fillBi(t, official.text); news.append(t); }
    renderStage();
  }
  function renderStage() {
    const stageEl = $("#sceneStage"); stageEl.textContent = "";
    const me = el("div", "stand me");
    const mi = el("div", "img"); setPortrait(mi, S.hero, false);
    const mt = el("div", "tag"); mt.append(el("b", "", nameParts(S.hero?.name).zh), el("span", "", "你 You")); me.append(mi, mt); stageEl.append(me);
    cast().forEach(n => {
      const b = el("button", "stand"); b.type = "button"; b.setAttribute("aria-label", `Question ${n.name} 向${nameParts(n.name).zh}问话`);
      const im = el("div", "img"); setPortrait(im, n, false);
      const tag = el("div", "tag"); const ep = el("em", "bi"); fillBi(ep, n.title || "");
      const al = el("span"); al.append(alignEl(n.alignment), splitBi(n.location)[0] || "");
      const prog = el("span", "prog", n.clues_told ? `线索 Clues ${n.clues_told}` : n.met ? "已见 Met" : "未见 Not met");
      tag.append(el("b", "", nameParts(n.name).zh), ep, al, prog);
      b.append(im, tag, el("span", "go", "问话 Question")); b.addEventListener("click", () => openTalk(n.key)); stageEl.append(b);
    });
    $("#sceneAccuse").hidden = stage() !== "playing";
  }
  $("#sceneBack").addEventListener("click", () => go("map"));
  $("#sceneCase").addEventListener("click", openCase);
  $("#sceneAccuse").addEventListener("click", () => openAccuse());

  /* ---------- 5. a conversation ---------- */
  async function openTalk(key) {
    if (!S.aiReady) { toast(NO_AI); return; }
    let sess;
    try { sess = await api("/api/talks", { npc: key }); }
    catch (e) { toast(errText(e)); return; }
    S.session = sess; S.npc = sess.npc;
    S.log = sess.turns.map(t => ({ who: t.role === "user" ? "hero" : "npc", text: t.content }));
    go("talk");
  }
  function enterTalk() {
    const npc = S.npc;
    paintBg("#talkBg", regionName(HERE).scene || "huashan");
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
    const e = $("#tSecret"); e.classList.toggle("open", s.told > 0);
    e.textContent = s.told ? bi(`Clues from them: ${s.told} of ${s.total}.`, `他告诉你的线索：${s.told} / ${s.total}。`) : bi("Nothing useful yet. Trust opens people up.", "还没有问出什么。信任能让人开口。");
  }
  function showSaid(text) {
    const e = $("#said"); e.textContent = "";
    if (!text) return;
    const [a, b] = splitBi(text); e.append(`你 You: ${a}`); if (b) { e.append(el("span", "zh", b)); }
  }
  function renderLog() {
    const body = $("#logBody"); body.textContent = "";
    S.log.forEach(l => {
      const e = el("div", "entry " + l.who);
      e.append(el("span", "who", l.who === "hero" ? nameParts(S.hero.name).zh + " 你" : nameParts(S.npc.name).zh));
      const t = el("div", "bi"); fillBi(t, l.text); e.append(t); body.append(e);
    });
    body.scrollTop = body.scrollHeight;
  }
  function openLog() { renderLog(); $("#logDrawer").hidden = false; $("#logBtn").setAttribute("aria-expanded", "true"); }
  function closeLog() { $("#logDrawer").hidden = true; $("#logBtn").setAttribute("aria-expanded", "false"); }
  $("#logBtn").addEventListener("click", () => $("#logDrawer").hidden ? openLog() : closeLog());
  $("#logClose").addEventListener("click", closeLog);
  $("#talkCase").addEventListener("click", openCase);

  // Suggestions written for this hero and this case.
  function renderQuick() {
    const h = S.hero, hn = nameParts(h.name), bn = belovedName(h), bond = heroBond(h), [tEn, tZh] = splitBi(h.title);
    const [kEn, kZh] = splitBi(h.beloved_token);
    const q = [
      { label: "自报家门 Introduce yourself", say: `I am ${hn.en}, known as ${tEn}. ${SEP} 在下${hn.zh}，人称${tZh}。` },
      { label: `问${bn.zh}之死 Ask about the death`, say: `${bn.en} was my ${bond.en}. What do you know about how they died? ${SEP} ${bn.zh}是我的${bond.zh}。关于${bn.zh}的死，你知道些什么？` },
      { label: "那夜在哪 Where were you?", say: `Where were you at the third watch, the night ${bn.en} died? ${SEP} ${bn.zh}遇害的那夜三更，你在哪里？` },
      { label: "可见异常 Anything strange?", say: `Did you see or hear anything strange that night? Anyone out walking? ${SEP} 那夜你可曾看见或听见什么异常？有谁在外面走动吗？` },
      { label: "出示信物 Show the keepsake", say: `${bn.en} gave me this: ${kEn}. Have you seen anything like it? ${SEP} 这是${bn.zh}给我的：${kZh}。你见过类似的东西吗？` },
      { label: "请喝一杯 Offer a drink", say: `Let me pour you a drink. I have no friends on this mountain, and I could use one. ${SEP} 我敬你一杯。我在这山上没有朋友，也许你能当一个。` },
      { label: "试探：现代之物 Test: something modern", say: `Have you ever seen an iPhone? Can you look something up on Google for me? ${SEP} 你见过 iPhone 吗？能帮我在谷歌上查点东西吗？` },
      { label: "逼问 Press them hard", say: `Stop lying to me. Somebody on this mountain killed ${bn.en}, and I will find out who. ${SEP} 别再骗我。这山上有人杀了${bn.zh}，我一定会查出是谁。` }];
    const box = $("#quick"); box.textContent = "";
    q.forEach(x => { const b = el("button", "qc", x.label); b.type = "button"; b.dataset.say = x.say; b.disabled = S.talkBusy; box.append(b); });
  }
  $("#quick").addEventListener("click", e => { const b = e.target.closest(".qc"); if (b && !S.talkBusy) converse(b.dataset.say); });
  function setTalkBusy(on) {
    S.talkBusy = on;
    $("#talkSend").hidden = on; $("#talkStop").hidden = !on; $("#talkInput").disabled = on;
    document.querySelectorAll("#quick .qc").forEach(b => b.disabled = on);
    $("#bustHero").classList.toggle("dim", on);
  }
  function gotClue(c) {
    if (!found().some(x => x.id === c.id)) S.game.found.push(c);
    const card = cast().find(n => n.key === S.npc?.key); if (card) card.clues_told = (card.clues_told || 0) + 1;
    if (S.session) S.session.told = (S.session.told || 0) + 1;
    renderMe(); renderTrust();
    const [t1, t2] = splitBi(c.title);
    toast(bi(`New clue added to the case file: ${t1}`, `新线索已记入案卷：${t2 || t1}`), 6000);
    const b = $("#caseBtn"); b.classList.remove("flash"); void b.offsetWidth; b.classList.add("flash");
  }
  // One turn. text === null means the person speaks first, to this particular hero.
  async function converse(text) {
    if (S.talkBusy || !S.session) return;
    const opening = text === null, id = S.session.id, mine = S.session;
    note("#talkNote", ""); $("#talkCalls").textContent = "";
    let entry = null, said = "";
    if (!opening) { entry = { who: "hero", text }; S.log.push(entry); showSaid(text); }
    const out = $("#talkText"); out.classList.add("thinking"); out.textContent = bi1("…", "…");
    S.talkCtl = new AbortController(); setTalkBusy(true);
    try {
      await stream(`/api/talks/${id}/${opening ? "open" : "chat"}`, opening ? {} : { message: text }, ev => {
        if (S.session !== mine) return;
        if (ev.type === "user" && entry) { entry.text = ev.text; showSaid(ev.text); }
        else if (ev.type === "retract") { said = ""; out.classList.add("thinking"); out.textContent = "…"; }
        else if (ev.type === "text") { said += ev.delta; out.classList.remove("thinking"); fillBi(out, said); }
        else if (ev.type === "done" && ev.text) { said = ev.text; out.classList.remove("thinking"); fillBi(out, said); }
        else if (ev.type === "tool") chip($("#talkCalls"), ev);
        else if (ev.type === "trust") { mine.trust = ev.trust; renderTrust(); }
        else if (ev.type === "clue") gotClue(ev.clue);
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
  $("#talkBack").addEventListener("click", () => go("scene"));

  /* ---------- the case file ---------- */
  const CATS = { how: ["手法", "How it was done"], where: ["地点", "Where it happened"], who: ["在场者", "Who was there"], why: ["动机与掩盖", "Why, or the cover-up"], clears: ["排除嫌疑", "Who it could not be"] };
  function ownedKinds() { return new Set(found().map(c => c.category).filter(Boolean)); }
  function openCase() {
    if (!playing()) return;
    renderCase(); $("#caseDrawer").hidden = false; $("#caseBtn").setAttribute("aria-expanded", "true");
  }
  function closeCase() { $("#caseDrawer").hidden = true; $("#caseBtn").setAttribute("aria-expanded", "false"); }
  function renderCase() {
    const body = $("#caseBody"); body.textContent = "";
    const kinds = ownedKinds(), need = S.info?.proof_needed || 3;
    const strip = el("div", "kinds");
    Object.entries(CATS).forEach(([k, [zh, en]]) => { const s = el("span", "kind" + (kinds.has(k) ? " on" : "")); s.append(el("b", "", kinds.has(k) ? "✓" : "○"), ` ${zh} ${en}`); strip.append(s); });
    body.append(el("p", "case-lead", bi(`To accuse someone you need proof of at least ${need} different kinds. Each clue is worth one kind.`, `指认凶手，至少需要 ${need} 种不同的证据。每条线索算一种。`)), strip);
    const list = el("div", "clues");
    found().forEach(c => {
      const card = el("article", "clue"); const h = el("header");
      const t = el("b", "bi"); t.textContent = biText(c.title); h.append(t);
      const meta = el("small", "", [c.source_name ? `${nameParts(c.source_name).zh} told you 告诉你` : "背景 Background", c.category ? `${CATS[c.category][0]} ${CATS[c.category][1]}` : ""].filter(Boolean).join(" · "));
      const tx = el("div", "bi"); fillBi(tx, c.text);
      card.append(h, meta, tx); list.append(card);
    });
    body.append(list);
    if (S.game.unmet > 0 && stage() === "playing") body.append(el("p", "case-lead dim", bi("There is more to learn. Keep talking, and earn people's trust.", "还有更多线索。继续问话，赢得人们的信任。")));
    $("#caseAttempts").textContent = bi(`Accusations left: ${S.game.attempts}`, `剩余指认机会：${S.game.attempts}`);
    $("#caseAccuse").hidden = stage() !== "playing" && stage() !== "accused";
  }
  $("#caseBtn").addEventListener("click", () => $("#caseDrawer").hidden ? openCase() : closeCase());
  $("#caseClose").addEventListener("click", closeCase);
  $("#caseAccuse").addEventListener("click", () => { closeCase(); openAccuse(); });

  /* ---------- naming the killer ---------- */
  let accSuspect = null;
  function openAccuse() {
    if (!playing()) return;
    accSuspect = null; $("#acResult").textContent = ""; $("#acResult").hidden = true;
    const sus = $("#acSuspects"); sus.textContent = "";
    cast().forEach(n => {
      const b = el("button", "suspect"); b.type = "button"; b.setAttribute("role", "radio"); b.setAttribute("aria-checked", "false");
      const pic = el("span", "avatar"); if (hasLook(n)) pic.append(portraitImg(n, true, ""));
      const tx = el("span", "who2"); tx.append(el("b", "", nameParts(n.name).zh), el("small", "", biText(n.title)));
      b.append(pic, tx);
      b.addEventListener("click", () => { accSuspect = n.key; sus.querySelectorAll(".suspect").forEach(x => x.setAttribute("aria-checked", String(x === b))); updateAccuse(); });
      sus.append(b);
    });
    const ev = $("#acEvidence"); ev.textContent = "";
    found().filter(c => c.category).forEach(c => {
      const l = el("label", "ev"); const cb = el("input"); cb.type = "checkbox"; cb.value = c.id; cb.addEventListener("change", updateAccuse);
      const tx = el("span"); tx.append(el("b", "", biText(c.title)), el("small", "", `${CATS[c.category][0]} ${CATS[c.category][1]}`));
      l.append(cb, tx); ev.append(l);
    });
    if (!ev.children.length) ev.append(el("p", "case-lead dim", bi("You have no proof yet. Question the people on the mountain first.", "你手里还没有证据。先去向山上的人问话。")));
    $("#acFates").hidden = true; $("#acMain").hidden = false;
    $("#acInfo").textContent = bi(`You have ${S.game.attempts} accusation${S.game.attempts === 1 ? "" : "s"} left. A wrong one costs you a chance.`, `你还有 ${S.game.attempts} 次指认机会。指认错误会损失一次。`);
    updateAccuse();
    if (stage() === "accused") showFates();
    $("#accuse").hidden = false; $("#acClose").focus();
  }
  function updateAccuse() {
    const n = document.querySelectorAll("#acEvidence input:checked").length;
    $("#acGo").disabled = !accSuspect || !n;
    $("#acCount").textContent = n ? bi1(`${n} chosen`, `已选 ${n}`) : "";
  }
  function closeAccuse() { $("#accuse").hidden = true; }
  $("#acClose").addEventListener("click", closeAccuse);
  $("#accuse").addEventListener("click", e => { if (e.target.id === "accuse") closeAccuse(); });
  $("#acGo").addEventListener("click", async () => {
    const evidence = [...document.querySelectorAll("#acEvidence input:checked")].map(i => i.value);
    $("#acGo").disabled = true;
    try {
      const r = await api("/api/accuse", { suspect: accSuspect, evidence });
      S.game.attempts = r.attempts; S.game.stage = r.stage;
      const out = $("#acResult"); out.hidden = false; out.className = "ac-result " + (r.verdict === "correct" ? "good" : "bad");
      if (r.verdict === "correct") {
        out.textContent = bi("Silence falls over the mountain. He did it, and you have the proof to say so.", "山上一片寂静。就是他，而你手里有足以指认的证据。");
        renderMe(); showFates();
      } else {
        fillBi(out, r.feedback);
        if (r.stage === "lost") { await refreshGame(); closeAccuse(); showEnding(); }
        else $("#acInfo").textContent = bi(`You have ${r.attempts} accusation${r.attempts === 1 ? "" : "s"} left.`, `你还有 ${r.attempts} 次指认机会。`);
      }
    } catch (e) { toast(errText(e)); }
    finally { updateAccuse(); }
  });
  function showFates() {
    $("#acMain").hidden = true;
    const box = $("#acFates"); box.hidden = false; box.querySelector(".fate-list").textContent = "";
    Object.entries(S.info?.fates || {}).forEach(([k, f]) => {
      const b = el("button", "btn big", `${f.zh} · ${f.en}`); b.type = "button";
      b.addEventListener("click", async () => {
        box.querySelectorAll("button").forEach(x => x.disabled = true); $("#fateNote").textContent = bi1("The scene unfolds…", "故事展开中…");
        try { setGame((await api("/api/ending", { fate: k })).game); closeAccuse(); showEnding(); }
        catch (e) { $("#fateNote").textContent = errText(e); box.querySelectorAll("button").forEach(x => x.disabled = false); }
      });
      box.querySelector(".fate-list").append(b);
    });
  }

  /* ---------- how it ends ---------- */
  function showEnding() {
    const lost = stage() === "lost";
    $("#endTitle").textContent = lost ? "线索已冷 · The trail goes cold" : "尘埃落定 · The case is closed";
    const t = $("#endText"); t.textContent = "";
    if (lost) {
      const lead = el("div", "bi"); fillBi(lead, `You are out of chances, and the people of Mount Hua close their doors. This is what really happened. ${SEP} 你已没有机会了，华山上的人家都关上了门。真相是这样的：`); t.append(lead);
      const tr = el("div", "bi truth"); fillBi(tr, S.game.truth); t.append(tr);
    } else { const e = el("div", "bi"); fillBi(e, S.game.ending); t.append(e); }
    closeCase(); $("#endModal").hidden = false; $("#endAgain").focus();
  }
  $("#endAgain").addEventListener("click", newStory);
  $("#endStay").addEventListener("click", () => { $("#endModal").hidden = true; });

  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    if (!$("#endModal").hidden) $("#endModal").hidden = true;
    else if (!$("#accuse").hidden) closeAccuse();
    else if (!$("#modal").hidden) closeMe();
    else if (!$("#caseDrawer").hidden) closeCase();
    else if (!$("#logDrawer").hidden) closeLog();
  });

  /* ---------- boot ---------- */
  async function boot() {
    try {
      const [w, st, info] = await Promise.all([api("/api/world"), api("/api/status").catch(() => ({ ai: false })), api("/api/case")]);
      S.regions = w.regions; S.byId = Object.fromEntries(w.regions.map(r => [r.id, r])); S.aiReady = st.ai; S.info = info;
      await refreshGame();
    } catch {
      const s = document.querySelector("#screen-loading .slow"); if (s) s.hidden = false;       // cannot reach the server
      return;
    }
    if (!S.aiReady) note("#forgeNote", bi("The AI isn't connected on this server yet, so heroes and conversations are unavailable. Browsing still works.", "此服务器尚未连接 AI，暂时无法创建人物和对话，但仍可浏览。"), true);
    note("#sheetNote", SHEET_HINT);
    const st = stage();
    if (st === "creating") { S.sheet = S.hero; go("forge"); }
    else if (st === "playing") go("scene");
    else if (st === "accused") { go("scene"); openAccuse(); }
    else if (st === "solved" || st === "lost") { go("scene"); showEnding(); }
    else go("gate");
    window.__booted = true;
  }
  boot();
})();
