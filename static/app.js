(() => {
  "use strict";
  const ALIGN = { orthodox: ["正", "a-orthodox", "orthodox"], unorthodox: ["邪", "a-unorthodox", "unorthodox"], neutral: ["中", "a-neutral", "neutral"] };
  const SIL = '<svg class="sil" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="34" r="18" fill="#2a2118"/><path d="M12 98c2-24 18-40 38-40s36 16 38 40z" fill="#2a2118"/></svg>';
  const $ = s => document.querySelector(s);

  const S = { aiReady: false, info: null, game: null, screen: null, npc: null, session: null, talkBusy: false, talkCtl: null, bg: null, gmBusy: false, dying: false };

  /* ---------- two languages everywhere ----------
     AI text arrives as "English ||| 中文". Notes and labels are written as pairs in the code below. */
  const SEP = "|||";
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
  // Fill an element with an English block and a Chinese block.
  function fillBi(box, text) {
    box.textContent = "";
    const [a, b] = splitBi(text);
    const add = (cls, t) => { if (!t) return; const d = document.createElement("div"); d.className = cls; d.textContent = t; box.append(d); };
    if (b) { add("en", a); add("zh", b); } else add(langOf(a) === "zh" ? "zh" : "en", a);
  }
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

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
  const hero = () => S.info?.hero;
  const gm = () => S.info?.gm;

  /* ---------- state ---------- */
  const stage = () => S.game?.stage || null;
  const live = () => ["playing", "moving"].includes(stage());
  const cast = () => S.game?.cast || S.info?.cast || [];
  const found = () => S.game?.found || [];
  const CATS = { tunnel: ["暗道", "The tunnel"], kill: ["杀掉掌柜", "Killing the keeper"], truth: ["客栈的真相", "The truth of the inn"] };
  function setGame(g) { S.game = g; renderTop(); }
  async function refreshGame() { setGame((await api("/api/game")).game); }

  function renderTop() {
    const on = live();
    $("#gmBtn").hidden = !on; $("#me").hidden = !on; $("#clock").hidden = !on;
    $("#menuBtn").hidden = !S.game;
    if (!S.game) closeMenu();
    if (!on) return;
    const gi = $("#gmBtnImg"); if (!gi.firstChild) setPortrait(gi, gm(), true, false);
    const av = $("#meImg"); if (!av.firstChild) av.append(portraitImg(hero(), true, ""));
    $("#meName").textContent = nameParts(hero().name).zh;
    renderClock();
  }
  function renderClock() {
    const c = S.game.clock, box = $("#clock"); box.textContent = "";
    for (let i = 0; i <= c.last; i++) box.append(el("i", i < c.beat ? "tick past" : i === c.beat ? "tick now" : "tick"));
    box.append(el("span", "", `${c.zh} ${c.en}`));
    box.setAttribute("aria-label", `${c.en}, ${c.last - c.beat} hours until dawn 距天明还有 ${c.last - c.beat} 个时辰`);
    box.classList.toggle("late", c.last - c.beat <= 2);
  }

  /* ---------- screens ---------- */
  const SCREENS = ["gate", "scene", "talk"];
  function go(name) {
    if (S.bg) { S.bg.stop(); S.bg = null; }
    if (name !== "talk") S.talkCtl?.abort();
    $("#screen-loading").classList.remove("on");
    SCREENS.forEach(s => $("#screen-" + s).classList.toggle("on", s === name));
    S.screen = name;
    window.scrollTo(0, 0);
    ({ gate: enterGate, scene: enterScene, talk: enterTalk })[name]();
  }
  function paintBg(canvasSel, kind) { S.bg = window.Scenes.paint($(canvasSel), kind); }

  /* ---------- 1. gate: one screen ---------- */
  function enterGate() {
    paintBg("#gateBg", "inn");
    $("#gateStart").textContent = live() ? "回到客栈 · Back to the inn" : "走进客栈 · Enter the inn";
    const h = $("#gateHero"); h.textContent = ""; h.append(portraitImg(hero(), true, ""));
    const g = $("#gateGm"); g.textContent = ""; g.append(portraitImg(gm(), true, ""));
  }
  async function begin() {
    if (live()) { go("scene"); if (stage() === "moving") openMove(); return; }
    if (stage() === "solved" || stage() === "dead") { go("scene"); showEnding(); return; }
    try { setGame((await api("/api/game/start", {})).game); }
    catch (e) { toast(errText(e)); return; }
    showPrologue();
  }
  $("#gateStart").addEventListener("click", begin);
  $("#brandBtn").addEventListener("click", () => go("gate"));
  $("#homeLink").addEventListener("click", () => go("gate"));

  /* ---------- the menu: a way to get anywhere from anywhere ---------- */
  function menuItems() {
    const items = [];
    if (S.screen !== "gate") items.push(["home", "首页 Home", "The title page"]);
    if (live() && S.screen !== "scene") items.push(["inn", "回到大堂 The inn", "Who is here"]);
    if (live()) items.push(["ray", "问 Ray Ask Ray", "Notes and hints"], ["me", "青禾 Qinghe", "Who you are"]);
    if (S.game) items.push(["restart", "重新开始 Start the night over", ""]);
    return items;
  }
  function openMenu() {
    const box = $("#menu"); box.textContent = "";
    menuItems().forEach(([act, zh, sub]) => { const b = el("button", "menu-item" + (act === "restart" ? " danger" : "")); b.type = "button"; b.setAttribute("role", "menuitem"); b.dataset.act = act; b.append(el("b", "", zh)); if (sub) b.append(el("small", "", sub)); box.append(b); });
    box.hidden = false; $("#menuBtn").setAttribute("aria-expanded", "true"); box.querySelector("button")?.focus();
  }
  function closeMenu() { $("#menu").hidden = true; $("#menuBtn").setAttribute("aria-expanded", "false"); }
  $("#menuBtn").addEventListener("click", e => { e.stopPropagation(); $("#menu").hidden ? openMenu() : closeMenu(); });
  $("#menu").addEventListener("click", e => {
    const b = e.target.closest(".menu-item"); if (!b) return;
    closeMenu(); S.talkCtl?.abort();
    ({ home: () => go("gate"), inn: () => go("scene"), ray: openGm, me: openMe, restart: () => { openMe(); $("#mdConfirm").hidden = false; } })[b.dataset.act]?.();
  });
  document.addEventListener("click", e => { if (!$("#menu").hidden && !e.target.closest("#menu")) closeMenu(); });

  /* ---------- Ray tells the opening ---------- */
  function showPrologue() {
    setPortrait($("#plPortrait"), gm(), true);
    fillBi($("#plText"), S.game.prologue);
    $("#prologue").hidden = false; $("#plGo").focus({ preventScroll: true });
  }
  $("#plGo").addEventListener("click", () => { $("#prologue").hidden = true; go("scene"); });

  /* ---------- Qinghe, in a window ---------- */
  function openMe() {
    const h = hero(); if (!h) return;
    setPortrait($("#mdPortrait"), h, true);
    const body = $("#mdBody"); body.textContent = "";
    body.append(el("h3", "", h.name)); const ep = el("div", "ep bi"); fillBi(ep, h.title); body.append(ep);
    const dl = document.createElement("dl");
    const row = (label, text) => { if (!text) return; const dd = el("dd", "bi"); fillBi(dd, text); dl.append(el("dt", "", label), dd); };
    row("身世 WHO SHE IS", h.bio); row("绝技 SIGNATURE MOVE", h.art); row("习癖 QUIRK", h.quirk);
    body.append(dl);
    $("#mdConfirm").hidden = true; $("#modal").hidden = false; $("#mdClose").focus({ preventScroll: true });
  }
  const closeMe = () => { $("#modal").hidden = true; $("#meBtn").focus(); };
  $("#meBtn").addEventListener("click", openMe);
  $("#mdClose").addEventListener("click", closeMe);
  $("#modal").addEventListener("click", e => { if (e.target.id === "modal") closeMe(); });
  $("#mdNew").addEventListener("click", () => { $("#mdConfirm").hidden = false; });
  $("#mdNo").addEventListener("click", () => { $("#mdConfirm").hidden = true; });
  $("#mdYes").addEventListener("click", async () => { $("#modal").hidden = true; await newNight(); });
  async function newNight() {
    try { await api("/api/game/reset", {}); } catch (e) { toast(errText(e)); return; }
    closeMove(); closeGm(); $("#endModal").hidden = true; $("#gmToast").hidden = true;
    setGame(null); S.npc = null; S.session = null; S.dying = false;
    go("gate");
  }

  /* ---------- 2. the inn: who is here ---------- */
  function enterScene() {
    paintBg("#sceneBg", "inn");
    renderNews(); renderPeople();
  }
  function renderNews() {
    const strip = $("#scNews"); strip.textContent = "";
    const ev = S.game.events || [];
    const last = ev.length ? ev[ev.length - 1].text : (found().find(c => c.id === "official") || {}).text || "";
    const av = el("span", "avatar"); setPortrait(av, gm(), true, false);
    const t = el("div", "ray-text"); t.append(el("b", "", "说书人 Ray 说 · tap to ask 点我提问")); const b = el("div", "bi"); fillBi(b, last); t.append(b);
    strip.append(av, t);
  }
  function renderPeople() {
    const box = $("#people"); box.textContent = "";
    cast().forEach(n => {
      const b = el("button", "person" + (n.clues_told ? " learned" : "")); b.type = "button"; b.setAttribute("aria-label", `Talk to ${n.name} 与${nameParts(n.name).zh}交谈`);
      const av = el("span", "avatar big"); setPortrait(av, n, true, false);
      const tx = el("div", "p-text"); const nm = el("b"); nm.append(alignEl(n.alignment), nameParts(n.name).zh, el("small", "", ` ${nameParts(n.name).en}`));
      const t = el("div", "p-title"); t.textContent = biText(n.title).split(" / ")[0];
      const st = el("div", "p-status", n.clues_told ? `✓ 已问出 Learned ${n.clues_told}/${n.clues_total}` : n.met ? "已交谈 Spoken · nothing yet 尚无所获" : "未交谈 Not spoken to");
      tx.append(nm, t, st); b.append(av, tx); b.addEventListener("click", () => openTalk(n.key)); box.append(b);
    });
    $("#sceneMove").hidden = !live();
  }
  $("#sceneMove").addEventListener("click", openMove);
  $("#scNews").addEventListener("click", openGm);

  /* ---------- 3. a conversation, as a chat ---------- */
  async function openTalk(key) {
    if (!S.aiReady) { toast(NO_AI); return; }
    let sess;
    try { sess = await api("/api/talks", { npc: key }); }
    catch (e) { toast(errText(e)); return; }
    S.session = sess; S.npc = sess.npc;
    go("talk");
  }
  function msgRow(who, text) {
    const thread = $("#thread");
    const row = el("div", "msg " + who);
    if (who === "npc") { const av = el("span", "avatar"); setPortrait(av, S.npc, true, false); row.append(av); }
    const bubble = el("div", "bubble");
    if (text) fillBi(bubble, text);
    const wrap = el("div", "bwrap"); wrap.append(bubble); row.append(wrap); thread.append(row); scrollThread();
    return bubble;
  }
  // 👍 / 👎 under a character's reply, so weak answers can be found later
  function addFeedback(bubble, turnIndex) {
    if (bubble.parentElement.querySelector(".fb") || turnIndex == null) return;
    const fb = el("span", "fb"); const talkId = S.session.id;
    const send = async rating => {
      fb.querySelectorAll("button").forEach(b => b.disabled = true);
      try { await api("/api/feedback", { talk: talkId, turn: turnIndex, rating }); fb.textContent = rating === "up" ? "谢谢 Thanks 👍" : "收到 Noted 👎"; }
      catch { fb.textContent = ""; }
    };
    for (const [r, icon, label] of [["up", "👍", "Good reply 好"], ["down", "👎", "Bad reply 不好"]]) { const b = el("button", "", icon); b.type = "button"; b.title = label; b.setAttribute("aria-label", label); b.addEventListener("click", () => send(r)); fb.append(b); }
    bubble.parentElement.append(fb);
  }
  const scrollThread = () => { const t = $("#thread"); t.scrollTop = t.scrollHeight; };
  function clueCard(c, fresh) {
    const card = el("div", "learned-card" + (fresh ? " fresh" : ""));
    card.append(el("b", "", `${fresh ? "新线索 New clue" : "已问出 Learned"} · ${biText(c.title)}`));
    const t = el("div", "bi"); fillBi(t, c.text); card.append(t);
    $("#thread").append(card); scrollThread();
  }
  function enterTalk() {
    const npc = S.npc, s = S.session;
    paintBg("#talkBg", "inn");
    setPortrait($("#chatAvatar"), npc, true, false);
    $("#chatName").textContent = `${nameParts(npc.name).zh} ${nameParts(npc.name).en}`;
    $("#chatTitle").textContent = biText(npc.title).split(" / ")[0];
    const thread = $("#thread"); thread.textContent = "";
    // what this person has already told you stays at the top of the page
    found().filter(c => c.source === npc.key).forEach(c => clueCard(c, false));
    s.turns.forEach(t => { const b = msgRow(t.role === "user" ? "hero" : "npc", t.content); if (t.role !== "user" && !t.hidden) addFeedback(b, t.i); });
    renderTrust(); renderQuick(); note("#talkNote", "");
    S.talkBusy = false; S.dying = false; setTalkBusy(false);
    if (s.fresh && !s.turns.length) converse(null);
    scrollThread();
  }
  function renderTrust() {
    const s = S.session, box = $("#chatTrust"); box.textContent = "";
    const m = el("div", "meter"); for (let i = 0; i < 10; i++) m.append(el("i", i < s.trust ? "on" : ""));
    box.append(el("span", "", `信任 Trust ${s.trust}/10`), m, el("span", "told", s.told ? `✓ ${s.told}/${s.total}` : `${s.total} 件事待问 to learn`));
  }

  // Things Qinghe might say, written for her and for this inn.
  function renderQuick() {
    const q = [
      { label: "自报家门 Introduce yourself", say: `I'm Qinghe. The storm caught me on the road, like everyone else. ${SEP} 我叫青禾。和大家一样，我在路上被沙暴困住了。` },
      { label: "问这家店 Ask about the inn", say: `What kind of place is this? Why is the door barred? ${SEP} 这是什么地方？为什么要把门闩上？` },
      { label: "问对方的难处 Ask what they need", say: `You look like someone carrying a weight. What do you need? ${SEP} 你看起来心事很重。你需要什么？` },
      { label: "我想离开 I want to leave", say: `I want to leave before dawn. Is there any way out of here? ${SEP} 我想在天亮前离开。这里有没有出路？` },
      { label: "示以善意 Offer a kindness", say: `Here, share my water. Nobody should go thirsty on a night like this. ${SEP} 来，分你一口水。这样的夜里，谁都不该渴着。` },
      { label: "亮出那封信 Show the letter", say: `Here. This is what my father died carrying. Read it. ${SEP} 看。这是我父亲临死还带着的东西。你读读。` },
      { label: "说出你的打算 Tell them your plan", say: `I'm getting out of here tonight, and I think I know how. ${SEP} 我今晚就要离开这里，而且我想我知道怎么走。` },
      { label: "威胁他 Threaten them", say: `Stand aside, or I will cut you down. ${SEP} 让开，不然我砍了你。` },
      { label: "试探：现代之物 Test: something modern", say: `Have you ever seen an iPhone? Can you look something up on Google for me? ${SEP} 你见过 iPhone 吗？能帮我在谷歌上查点东西吗？` },
      { label: "逼问 Press them hard", say: `Stop dancing around it. Tell me what is really going on in this inn. ${SEP} 别绕圈子了。告诉我这家客栈到底是怎么回事。` }];
    const box = $("#quick"); box.textContent = "";
    q.forEach(x => { const b = el("button", "qc", x.label); b.type = "button"; b.dataset.say = x.say; b.disabled = S.talkBusy; box.append(b); });
  }
  $("#quick").addEventListener("click", e => { const b = e.target.closest(".qc"); if (b && !S.talkBusy) converse(b.dataset.say); });
  function setTalkBusy(on) {
    S.talkBusy = on;
    $("#talkSend").hidden = on; $("#talkStop").hidden = !on; $("#talkInput").disabled = on;
    document.querySelectorAll("#quick .qc").forEach(b => b.disabled = on);
  }
  function gotClue(c) {
    if (!found().some(x => x.id === c.id)) S.game.found.push(c);
    const card = cast().find(n => n.key === S.npc?.key); if (card) card.clues_told = (card.clues_told || 0) + 1;
    if (S.session) S.session.told = (S.session.told || 0) + 1;
    clueCard(c, true); renderTrust();
  }
  // One turn. text === null means the person speaks first, to Qinghe.
  async function converse(text) {
    if (S.talkBusy || !S.session) return;
    const opening = text === null, id = S.session.id, mine = S.session;
    note("#talkNote", "");
    let mineBubble = null, said = "";
    if (!opening) mineBubble = msgRow("hero", text);
    const out = msgRow("npc", ""); out.classList.add("thinking"); out.textContent = "…";
    S.talkCtl = new AbortController(); setTalkBusy(true);
    try {
      await stream(`/api/talks/${id}/${opening ? "open" : "chat"}`, opening ? {} : { message: text }, ev => {
        if (S.session !== mine) return;
        if (ev.type === "user" && mineBubble) fillBi(mineBubble, ev.text);
        else if (ev.type === "retract") { said = ""; out.classList.add("thinking"); out.textContent = "…"; }
        else if (ev.type === "text") { said += ev.delta; out.classList.remove("thinking"); fillBi(out, said); }
        else if (ev.type === "done" && ev.text) { said = ev.text; out.classList.remove("thinking"); fillBi(out, said); }
        else if (ev.type === "turn") addFeedback(out, ev.i);
        else if (ev.type === "tool" && ev.name === "adjust_trust" && /^[+-]\d/.test(ev.detail || "")) {
          const d = parseInt(ev.detail, 10); if (d) out.parentElement.append(el("span", "trust-tag " + (d > 0 ? "up" : "down"), `信任 Trust ${d > 0 ? "+" : ""}${d}`));
        }
        else if (ev.type === "trust") {
          mine.trust = ev.trust; renderTrust();
          if (ev.delta && mineBubble) mineBubble.parentElement.append(el("span", "trust-tag " + (ev.delta > 0 ? "up" : "down"), `信任 Trust ${ev.delta > 0 ? "+" : ""}${ev.delta}`));   // how her words landed
        }
        else if (ev.type === "clue") gotClue(ev.clue);
        else if (ev.type === "gm") { S.game.events.push({ beat: ev.beat, text: ev.text }); showGm(ev.text); }
        else if (ev.type === "clock") { S.game.clock = ev.clock; renderTop(); }
        else if (ev.type === "death") dies();
        scrollThread();
      }, S.talkCtl.signal);
    } catch (e) {
      out.classList.remove("thinking");
      if (!said) out.textContent = e?.name === "AbortError" ? bi1("(silence)", "（沉默）") : "…";
      if (errText(e)) note("#talkNote", errText(e), true);
    } finally {
      if (S.session === mine && !S.dying) setTalkBusy(false);
    }
  }
  $("#talkForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#talkInput").value.trim(); if (v && !S.talkBusy) { $("#talkInput").value = ""; converse(v); } });
  $("#talkStop").addEventListener("click", () => S.talkCtl?.abort());
  $("#talkBack").addEventListener("click", () => { S.talkCtl?.abort(); renderPeople(); go("scene"); const n = S.npc, told = S.session?.told; if (told) toast(bi(`${nameParts(n.name).en} has told you ${told} of ${S.session.total} things. Ray has noted them.`, `${nameParts(n.name).zh}已告诉你 ${told}/${S.session.total} 件事，Ray 已记下。`)); });

  /* ---------- Ray: announcements, what you've learned, and questions ---------- */
  let gmTimer = 0;
  function showGm(text) {
    const t = $("#gmToast"); if (!$("#gmToastImg").firstChild) setPortrait($("#gmToastImg"), gm(), true, false);
    fillBi($("#gmToastText"), text); t.hidden = false; clearTimeout(gmTimer); gmTimer = setTimeout(() => { t.hidden = true; }, 20000);
    if ($("#screen-scene").classList.contains("on")) renderNews();
  }
  $("#gmToastX").addEventListener("click", () => { $("#gmToast").hidden = true; });
  function openGm() {
    if (!live()) return;
    const img = $("#gmDrawerImg"); if (!img.firstChild) setPortrait(img, gm(), true, false);
    renderLearned(); renderGmLog(); $("#gmDrawer").hidden = false; $("#gmBtn").setAttribute("aria-expanded", "true"); $("#gmInput").focus();
    const q = $("#gmQuick"); if (!q.children.length) [["现在什么情况？ What's going on?", `Remind me: what's going on, and where do things stand? ${SEP} 帮我理一理：现在是什么情况，进展到哪了？`],
      ["我该找谁？ Who next?", `Who should I talk to next, and how? ${SEP} 我接下来该找谁，怎么谈？`],
      ["给点提示 A hint", `I'm stuck. Can you give me a hint? ${SEP} 我卡住了，能给我点提示吗？`]].forEach(([label, say]) => { const b = el("button", "qc", label); b.type = "button"; b.dataset.say = say; q.append(b); });
  }
  function closeGm() { $("#gmDrawer").hidden = true; $("#gmBtn").setAttribute("aria-expanded", "false"); }
  // Ray's notes: everything she has learned, and how close each way out is.
  function renderLearned() {
    const list = found(), c = S.game.clock;
    $("#gmClock").textContent = `${c.zh} ${c.en} · ${c.last - c.beat} 个时辰到天明 hours to dawn`;
    $("#gmLearnedSum").textContent = `Ray 的笔记 Ray's notes · ${list.length}`;
    const box = $("#gmClues"); box.textContent = "";
    list.forEach(cl => {
      const card = el("article", "clue"); const t = el("b", "bi"); t.textContent = biText(cl.title);
      const meta = el("small", "", [cl.source_name ? `${nameParts(cl.source_name).zh} 告诉你 told you` : "背景 Background", cl.category ? `${CATS[cl.category][0]} ${CATS[cl.category][1]}` : ""].filter(Boolean).join(" · "));
      const tx = el("div", "bi"); fillBi(tx, cl.text); card.append(t, meta, tx); box.append(card);
    });
    const ways = $("#gmWays"); ways.textContent = "";
    Object.entries(S.game.ways || {}).forEach(([k, w]) => ways.append(el("div", "way" + (w.have === w.need ? " ready" : ""), `${w.zh} ${w.en}: ${w.have === w.need ? "✓ 万事俱备 ready" : `${w.have}/${w.need}`}`)));
  }
  function renderGmLog() {
    const body = $("#gmLog"); body.textContent = "";
    const turns = S.game.gm_turns || [];
    const add = (who, text) => { const e = el("div", "entry " + who); e.append(el("span", "who", who === "hero" ? nameParts(hero().name).zh + " 你" : "说书人 Ray")); const t = el("div", "bi"); fillBi(t, text); e.append(t); body.append(e); };
    if (!turns.length) add("npc", `Ask me anything about the night. I won't tell you what you haven't learned, but I can point you in the right direction. ${SEP} 关于今夜，你想问什么都行。你没打听到的我不会说，但我能给你指个方向。`);
    turns.forEach(l => add(l.role === "user" ? "hero" : "npc", l.content));
    const b = $("#gmBody"); b.scrollTop = b.scrollHeight;
  }
  async function askGm(text) {
    if (S.gmBusy || !S.aiReady) { if (!S.aiReady) note("#gmNote", NO_AI, true); return; }
    S.gmBusy = true; note("#gmNote", ""); $("#gmSend").disabled = true; $("#gmInput").disabled = true;
    const mine = { role: "user", content: text }, reply = { role: "assistant", content: "…" };
    S.game.gm_turns = [...(S.game.gm_turns || []), mine, reply]; renderGmLog();
    try {
      await stream("/api/gm/chat", { message: text }, ev => {
        if (ev.type === "user") mine.content = ev.text;
        else if (ev.type === "retract") reply.content = "…";
        else if (ev.type === "text") { reply.content = (reply.content === "…" ? "" : reply.content) + ev.delta; }
        else if (ev.type === "done" && ev.text) reply.content = ev.text;
        renderGmLog();
      });
    } catch (e) { if (reply.content === "…") S.game.gm_turns = S.game.gm_turns.slice(0, -2); note("#gmNote", errText(e), true); renderGmLog(); }
    finally { S.gmBusy = false; $("#gmSend").disabled = false; $("#gmInput").disabled = false; $("#gmInput").focus(); }
  }
  $("#gmForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#gmInput").value.trim(); if (v) { $("#gmInput").value = ""; askGm(v); } });
  $("#gmQuick").addEventListener("click", e => { const b = e.target.closest(".qc"); if (b) askGm(b.dataset.say); });
  $("#gmBtn").addEventListener("click", () => $("#gmDrawer").hidden ? openGm() : closeGm());
  $("#gmClose").addEventListener("click", closeGm);

  /* ---------- the move: the last one she makes ---------- */
  function openMove() {
    if (!live()) return;
    const list = $("#mvPaths"); list.textContent = ""; $("#mvNote").textContent = "";
    Object.entries(S.info?.fates || {}).forEach(([k, f]) => {
      const b = el("button", "btn big path-btn", `${f.zh} · ${f.en}`); b.type = "button"; b.dataset.path = k;
      b.addEventListener("click", () => {
        if (b.dataset.armed !== "1") { list.querySelectorAll("button").forEach(x => { x.dataset.armed = ""; x.classList.remove("armed"); x.textContent = `${S.info.fates[x.dataset.path].zh} · ${S.info.fates[x.dataset.path].en}`; }); b.dataset.armed = "1"; b.classList.add("armed"); b.textContent = `确定？没准备好就是死 · Sure? If you're not ready, you die.`; return; }
        attempt(k, list);
      });
      list.append(b);
    });
    $("#move").hidden = false; $("#mvClose").focus({ preventScroll: true });
  }
  async function attempt(path, list) {
    list.querySelectorAll("button").forEach(x => x.disabled = true); $("#mvNote").textContent = bi1("You move…", "你动手了…");
    try {
      const r = await api("/api/move", { path });
      setGame(r.game);
      if (r.verdict === "dead") { closeMove(); showEnding(); return; }
      $("#mvNote").textContent = bi1("You are out. Ray is telling it…", "你出去了。Ray 正在讲述…");
      setGame((await api("/api/ending", {})).game); closeMove(); showEnding();
    } catch (e) { $("#mvNote").textContent = errText(e); list.querySelectorAll("button").forEach(x => x.disabled = false); }
  }
  function closeMove() { $("#move").hidden = true; }
  $("#mvClose").addEventListener("click", closeMove);
  $("#move").addEventListener("click", e => { if (e.target.id === "move") closeMove(); });

  /* ---------- how it ends ---------- */
  // She has been killed in a conversation: let the last line sink in, then Ray explains.
  async function dies() {
    S.dying = true;
    setTalkBusy(true);
    await new Promise(r => setTimeout(r, 3200));
    try { await refreshGame(); } catch { /* keep what we have */ }
    closeMove(); closeGm(); showEnding();
  }
  const ENDINGS = { dead: ["游戏结束", "Game over"], tunnel: ["暗道", "Out through the tunnel"], kill: ["夺钥", "The keeper's key"] };
  function endingsFound(add) {
    let have = [];
    try { have = JSON.parse(localStorage.getItem("endings") || "[]"); } catch { /* private window */ }
    if (add && !have.includes(add)) { have.push(add); try { localStorage.setItem("endings", JSON.stringify(have)); } catch { /* private window */ } }
    return have;
  }
  function showEnding() {
    const key = S.game.ending_key || "dead", dead = key === "dead";
    const [zh, en] = ENDINGS[key];
    $("#endTitle").textContent = `${zh} · ${en}`;
    $("#endModal .modal-card").classList.toggle("dead", dead);
    const t = $("#endText"); t.textContent = "";
    if (dead) { const c = el("div", "bi cause"); fillBi(c, "You are dead. Ray tells you what happened. ||| 你死了。Ray 告诉你发生了什么。"); t.append(c); }
    const e = el("div", "bi"); fillBi(e, S.game.ending); t.append(e);
    const have = endingsFound(key), track = $("#endTrack"); track.textContent = ""; track.append(el("span", "", `结局 Endings ${have.length} / 3`));
    Object.entries(ENDINGS).forEach(([k, [z, n]]) => track.append(el("span", "end-chip" + (have.includes(k) ? " on" : ""), have.includes(k) ? `${z} ${n}` : "？")));
    closeGm(); $("#endModal").hidden = false; $("#endAgain").focus({ preventScroll: true }); $("#endModal").scrollTop = 0;
  }
  $("#endLang").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    $("#endText").classList.remove("only-en", "only-zh"); if (b.dataset.l) $("#endText").classList.add(b.dataset.l);
    $("#endLang").querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  });
  $("#endAgain").addEventListener("click", async () => { $("#endModal").hidden = true; await newNight(); });
  $("#endStay").addEventListener("click", () => { $("#endModal").hidden = true; });
  $("#endHome").addEventListener("click", () => { $("#endModal").hidden = true; go("gate"); });

  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    if (!$("#endModal").hidden) $("#endModal").hidden = true;
    else if (!$("#move").hidden) closeMove();
    else if (!$("#modal").hidden) closeMe();
    else if (!$("#gmDrawer").hidden) closeGm();
    else if (!$("#menu").hidden) closeMenu();
  });

  /* ---------- boot ---------- */
  async function boot() {
    try {
      const [st, info] = await Promise.all([api("/api/status").catch(() => ({ ai: false })), api("/api/case")]);
      S.aiReady = st.ai; S.info = info;
      await refreshGame();
    } catch {
      const s = document.querySelector("#screen-loading .slow"); if (s) s.hidden = false;       // cannot reach the server
      return;
    }
    const st = stage();
    if (st === "playing") go("scene");
    else if (st === "moving") { go("scene"); openMove(); }
    else if (st === "solved" || st === "dead") { go("scene"); showEnding(); }
    else go("gate");
    window.__booted = true;
  }
  boot();
})();
