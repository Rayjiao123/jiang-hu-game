(() => {
  "use strict";
  const ALIGN = { orthodox: ["正", "a-orthodox", "orthodox"], unorthodox: ["邪", "a-unorthodox", "unorthodox"], neutral: ["中", "a-neutral", "neutral"] };
  const SIL = '<svg class="sil" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="34" r="18" fill="#2a2118"/><path d="M12 98c2-24 18-40 38-40s36 16 38 40z" fill="#2a2118"/></svg>';
  const $ = s => document.querySelector(s);

  const S = { aiReady: false, info: null, game: null, screen: null, npc: null, session: null, log: [], talkBusy: false, talkCtl: null, bg: null, gmBusy: false };

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
  // Fill an element with an English block and a Chinese block. quote wraps each in curly quotes.
  function fillBi(box, text, quote = false) {
    box.textContent = "";
    const [a, b] = splitBi(text);
    const add = (cls, t) => { if (!t) return; const d = document.createElement("div"); d.className = cls; d.textContent = quote ? `“${t}”` : t; box.append(d); };
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
    $("#caseBtn").hidden = !on; $("#gmBtn").hidden = !on; $("#me").hidden = !on; $("#clock").hidden = !on;
    if (!on) return;
    $("#caseBtn").textContent = `线索 Clues · ${found().length}`;
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
    if (name !== "talk") { S.talkCtl?.abort(); closeLog(); }
    $("#screen-loading").classList.remove("on");
    $("#aboutBtn").hidden = name === "gate";
    SCREENS.forEach(s => $("#screen-" + s).classList.toggle("on", s === name));
    S.screen = name;
    window.scrollTo(0, 0);
    ({ gate: enterGate, scene: enterScene, talk: enterTalk })[name]();
    renderCrumbs();
  }
  function paintBg(canvasSel, kind) { S.bg = window.Scenes.paint($(canvasSel), kind); }
  function renderCrumbs() {
    const c = $("#crumbs"); c.textContent = "";
    const add = (label, fn) => { const b = document.createElement(fn ? "button" : "span"); b.textContent = label; if (fn) { b.type = "button"; b.onclick = fn; } else b.className = "here"; c.append(b); };
    if (S.screen === "scene") add("黑沙客栈 The Black Sand Inn");
    else if (S.screen === "talk") { add("黑沙客栈 The Black Sand Inn", () => go("scene")); c.append(" › "); add(nameParts(S.npc?.name).zh); }
  }

  /* ---------- 1. gate: a landing page that shows what the game is ---------- */
  const SAMPLE_TALK = [
    ["you", `Is the door really barred for our safety? ${SEP} 大门真是为了我们的安全才闩上的吗？`],
    ["npc", `*smiles, and the smile does not reach her fan* Every door in this inn is for somebody's safety, little sister. Whose, I wouldn't say. ${SEP} *笑着，那笑意没有到达她的扇子* 这店里的每道门都是为谁的安全而闩，妹妹。是谁，我可不说。`],
  ];
  function enterGate() { paintBg("#gateBg", "inn"); renderGate(); }
  function renderGate() {
    const back = live();
    $("#gateStart").textContent = $("#gateStart2").textContent = back ? "回到客栈 · Back to the inn" : "走进客栈 · Step inside";
    const people = S.info?.cast || [];
    const row = $("#gateCast"); row.textContent = "";
    ["tuo", "shuang", "wolf"].map(k => people.find(n => n.key === k)).filter(Boolean).forEach(n => { const d = el("div", "bu"); setPortrait(d, n, false, false); row.append(d); });
    const a1 = $("#howArt1"); a1.textContent = ""; a1.append(portraitImg(hero(), true, ""));
    const mock = $("#howArt2"); mock.textContent = "";
    SAMPLE_TALK.forEach(([who, t]) => { const d = el("div", "l " + who); fillBi(d, t); mock.append(d); });
    const a3 = $("#howArt3"); a3.textContent = ""; a3.append(portraitImg(gm(), true, ""));
    const ga = $("#gmArt"); ga.textContent = ""; ga.append(portraitImg(gm(), true, ""));
    const list = $("#meetRow"); list.textContent = "";
    people.forEach(n => {
      const b = el("button", "meet-card"); b.type = "button"; b.setAttribute("aria-label", `${n.name}: meet them`);
      const pic = el("div", "pic"); if (hasLook(n)) pic.append(portraitImg(n, true, ""));
      const ep = el("div", "ep bi"); fillBi(ep, n.title || "");
      const q = el("div", "q bi"); fillBi(q, n.public || "");
      b.append(pic, el("b", "", nameParts(n.name).zh), ep, q); b.addEventListener("click", () => meetFromGate(n)); list.append(b);
    });
  }
  async function begin() {
    if (live()) { go("scene"); if (stage() === "moving") openMove(); return; }
    if (stage() === "solved" || stage() === "dead") { go("scene"); showEnding(); return; }
    try { setGame((await api("/api/game/start", {})).game); }
    catch (e) { toast(errText(e)); return; }
    showPrologue();
  }
  function meetFromGate(n) {
    if (live()) { go("scene"); openTalk(n.key); return; }
    toast(bi("Step inside first, then you can talk to them.", "先走进客栈，才能和他们交谈。"));
  }
  $("#gateStart").addEventListener("click", begin);
  $("#gateStart2").addEventListener("click", begin);
  $("#brandBtn").addEventListener("click", () => go(live() ? "scene" : "gate"));
  $("#aboutBtn").addEventListener("click", () => go("gate"));

  /* ---------- Ray tells the opening ---------- */
  function showPrologue() {
    setPortrait($("#plPortrait"), gm(), true);
    fillBi($("#plText"), S.game.prologue);
    $("#prologue").hidden = false; $("#plGo").focus();
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
    $("#mdConfirm").hidden = true; $("#modal").hidden = false; $("#mdClose").focus();
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
    closeCase(); closeMove(); closeGm(); $("#endModal").hidden = true; $("#gmToast").hidden = true;
    setGame(null); S.npc = null; S.session = null; S.dying = false;
    go("gate");
  }

  /* ---------- 2. the inn: who is here, and what the game master says ---------- */
  function enterScene() {
    paintBg("#sceneBg", "inn");
    renderNews(); renderStage();
  }
  function renderNews() {
    const news = $("#scNews"); news.textContent = "";
    const ev = S.game.events || [];
    const last = ev.length ? ev[ev.length - 1].text : (found().find(c => c.id === "official") || {}).text || "";
    const head = el("div", "gm-line"); const av = el("span", "avatar mini"); setPortrait(av, gm(), true, false); head.append(av, el("b", "", "说书人 Ray 说"));
    const t = el("div", "bi"); fillBi(t, last);
    news.append(head, t);
  }
  function renderStage() {
    const stageEl = $("#sceneStage"); stageEl.textContent = "";
    const me = el("button", "stand me"); me.type = "button"; me.setAttribute("aria-label", "Qinghe 青禾");
    const mi = el("div", "img"); setPortrait(mi, hero(), false);
    const mt = el("div", "tag"); mt.append(el("b", "", nameParts(hero().name).zh), el("span", "", "你 You")); me.append(mi, mt); me.addEventListener("click", openMe); stageEl.append(me);
    cast().forEach(n => {
      const b = el("button", "stand"); b.type = "button"; b.setAttribute("aria-label", `Talk to ${n.name} 与${nameParts(n.name).zh}交谈`);
      const im = el("div", "img"); setPortrait(im, n, false);
      const tag = el("div", "tag"); const ep = el("em", "bi"); fillBi(ep, n.title || "");
      const al = el("span"); al.append(alignEl(n.alignment), splitBi(n.location)[0] || "");
      const prog = el("span", "prog", n.clues_told ? `线索 Clues ${n.clues_told}/${n.clues_total}` : n.met ? "已交谈 Spoken" : "未交谈 Not yet");
      tag.append(el("b", "", nameParts(n.name).zh), ep, al, prog);
      b.append(im, tag, el("span", "go", "交谈 Talk")); b.addEventListener("click", () => openTalk(n.key)); stageEl.append(b);
    });
    $("#sceneMove").hidden = !live();
  }
  $("#sceneMove").addEventListener("click", openMove);
  $("#sceneCase").addEventListener("click", openCase);
  $("#sceneGm").addEventListener("click", openGm);

  /* ---------- 3. a conversation ---------- */
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
    paintBg("#talkBg", "inn");
    setPortrait($("#bustHero .img"), hero(), false); $("#bhName").textContent = nameParts(hero().name).zh;
    setPortrait($("#bustNpc .img"), npc, false); $("#bnName").textContent = nameParts(npc.name).zh;
    fillBi($("#bnTitle"), npc.title || "");
    $("#speaker").textContent = nameParts(npc.name).zh;
    $("#tImpression").textContent = splitBi(S.session.impression).join("\n");
    renderTrust(); renderQuick(); renderLog(); note("#talkNote", ""); $("#talkCalls").textContent = "";
    S.talkBusy = false; setTalkBusy(false);
    const lastNpc = [...S.log].reverse().find(l => l.who === "npc");
    if (S.session.fresh && !S.log.length) converse(null);
    else { showSaid(""); fillBi($("#talkText"), lastNpc ? lastNpc.text : npc.greeting || ""); $("#talkText").classList.remove("thinking"); const lastHero = [...S.log].reverse().find(l => l.who === "hero"); if (lastHero && S.log.indexOf(lastHero) > S.log.indexOf(lastNpc)) showSaid(lastHero.text); }
  }
  function renderTrust() {
    const s = S.session, m = $("#tMeter"); m.textContent = "";
    for (let i = 0; i < 10; i++) { const p = document.createElement("i"); if (i < s.trust) p.className = "on"; m.append(p); }
    $("#tTrustN").textContent = `${s.trust} / 10`;
    const e = $("#tSecret"); e.classList.toggle("open", s.told > 0);
    e.textContent = s.told ? bi(`What they've told you: ${s.told} of ${s.total}.`, `他告诉你的事：${s.told} / ${s.total}。`) : bi("Nothing useful yet. Trust opens people up.", "还没有问出什么。信任能让人开口。");
  }
  function showSaid(text) {
    const e = $("#said"); e.textContent = "";
    if (!text) return;
    const [a, b] = splitBi(text); e.append(`你 You: ${a}`); if (b) e.append(el("span", "zh", b));
  }
  function renderLog() {
    const body = $("#logBody"); body.textContent = "";
    S.log.forEach(l => {
      const e = el("div", "entry " + l.who);
      e.append(el("span", "who", l.who === "hero" ? nameParts(hero().name).zh + " 你" : nameParts(S.npc.name).zh));
      const t = el("div", "bi"); fillBi(t, l.text); e.append(t); body.append(e);
    });
    body.scrollTop = body.scrollHeight;
  }
  function openLog() { renderLog(); $("#logDrawer").hidden = false; $("#logBtn").setAttribute("aria-expanded", "true"); }
  function closeLog() { $("#logDrawer").hidden = true; $("#logBtn").setAttribute("aria-expanded", "false"); }
  $("#logBtn").addEventListener("click", () => $("#logDrawer").hidden ? openLog() : closeLog());
  $("#logClose").addEventListener("click", closeLog);
  $("#talkGm").addEventListener("click", openGm);

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
    $("#bustHero").classList.toggle("dim", on);
  }
  function chip(box, ev) {
    const c = document.createElement("span"); c.className = "call" + (ev.refused ? " no" : "");
    const b = document.createElement("b"); b.textContent = ev.name; c.append("⚙ ", b, ev.detail ? " · " + biText(ev.detail) : "");
    box.append(c);
  }
  function gotClue(c) {
    if (!found().some(x => x.id === c.id)) S.game.found.push(c);
    const card = cast().find(n => n.key === S.npc?.key); if (card) card.clues_told = (card.clues_told || 0) + 1;
    if (S.session) S.session.told = (S.session.told || 0) + 1;
    renderTop(); renderTrust();
    const [t1, t2] = splitBi(c.title);
    toast(bi(`New clue: ${t1}`, `新线索：${t2 || t1}`), 6000);
    const b = $("#caseBtn"); b.classList.remove("flash"); void b.offsetWidth; b.classList.add("flash");
  }
  // One turn. text === null means the person speaks first, to Qinghe.
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
        else if (ev.type === "gm") { S.game.events.push({ beat: ev.beat, text: ev.text }); showGm(ev.text); }
        else if (ev.type === "clock") { S.game.clock = ev.clock; renderTop(); }
        else if (ev.type === "death") dies(ev.cause);
      }, S.talkCtl.signal);
    } catch (e) {
      out.classList.remove("thinking");
      if (!said) out.textContent = e?.name === "AbortError" ? bi1("(silence)", "（沉默）") : "…";
      if (errText(e)) note("#talkNote", errText(e), true);
    } finally {
      if (said && S.session === mine) S.log.push({ who: "npc", text: said });
      if (S.session === mine && !S.dying) setTalkBusy(false);
      if (!$("#logDrawer").hidden) renderLog();
    }
  }
  $("#talkForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#talkInput").value.trim(); if (v && !S.talkBusy) { $("#talkInput").value = ""; converse(v); } });
  $("#talkStop").addEventListener("click", () => S.talkCtl?.abort());
  $("#talkBack").addEventListener("click", () => go("scene"));

  /* ---------- Ray: announcements and questions ---------- */
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
    renderGmLog(); $("#gmDrawer").hidden = false; $("#gmBtn").setAttribute("aria-expanded", "true"); $("#gmInput").focus();
    const q = $("#gmQuick"); if (!q.children.length) [["现在是什么情况？ What's going on?", `Remind me: what's going on, and where do things stand? ${SEP} 帮我理一理：现在是什么情况，进展到哪了？`],
      ["我该找谁？ Who should I talk to?", `Who should I talk to next, and how? ${SEP} 我接下来该找谁，怎么谈？`],
      ["给点提示 Give me a hint", `I'm stuck. Can you give me a hint? ${SEP} 我卡住了，能给我点提示吗？`]].forEach(([label, say]) => { const b = el("button", "qc", label); b.type = "button"; b.dataset.say = say; q.append(b); });
  }
  function closeGm() { $("#gmDrawer").hidden = true; $("#gmBtn").setAttribute("aria-expanded", "false"); }
  function renderGmLog() {
    const body = $("#gmLog"); body.textContent = "";
    const turns = S.game.gm_turns || [];
    if (!turns.length) { const e = el("div", "entry npc"); e.append(el("span", "who", "说书人 Ray")); const t = el("div", "bi"); fillBi(t, `Ask me anything about the night. I won't tell you what you haven't learned, but I can point you in the right direction. ${SEP} 关于今夜，你想问什么都行。你没打听到的我不会说，但我能给你指个方向。`); e.append(t); body.append(e); }
    turns.forEach(l => { const e = el("div", "entry " + (l.role === "user" ? "hero" : "npc")); e.append(el("span", "who", l.role === "user" ? nameParts(hero().name).zh + " 你" : "说书人 Ray")); const t = el("div", "bi"); fillBi(t, l.content); e.append(t); body.append(e); });
    body.scrollTop = body.scrollHeight;
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

  /* ---------- the clues she has gathered ---------- */
  function openCase() {
    if (!live()) return;
    renderCase(); $("#caseDrawer").hidden = false; $("#caseBtn").setAttribute("aria-expanded", "true");
  }
  function closeCase() { $("#caseDrawer").hidden = true; $("#caseBtn").setAttribute("aria-expanded", "false"); }
  function renderCase() {
    const body = $("#caseBody"); body.textContent = "";
    const kinds = new Set(found().map(c => c.category).filter(Boolean));
    const strip = el("div", "kinds");
    Object.entries(CATS).forEach(([k, [zh, en]]) => { const s = el("span", "kind" + (kinds.has(k) ? " on" : "")); s.append(el("b", "", kinds.has(k) ? "✓" : "○"), ` ${zh} ${en}`); strip.append(s); });
    body.append(el("p", "case-lead", bi("There are two ways out of this inn, and only two. Each needs two things you must learn first. If you try one without them, you die.", "这家客栈只有两条出路。每一条都需要你先弄清两件事。没准备好就动手，你会死。")), strip);
    const list = el("div", "clues");
    found().forEach(c => {
      const card = el("article", "clue"); const h = el("header"); const t = el("b", "bi"); t.textContent = biText(c.title); h.append(t);
      const meta = el("small", "", [c.source_name ? `${nameParts(c.source_name).zh} told you 告诉你` : "背景 Background", c.category ? `${CATS[c.category][0]} ${CATS[c.category][1]}` : ""].filter(Boolean).join(" · "));
      const tx = el("div", "bi"); fillBi(tx, c.text);
      card.append(h, meta, tx); list.append(card);
    });
    body.append(list);
    if (S.game.unmet > 0 && stage() === "playing") body.append(el("p", "case-lead dim", bi("There is more to learn. Keep talking, and earn people's trust.", "还有更多可打听的。继续交谈，赢得人们的信任。")));
    const c = S.game.clock; $("#caseClock").textContent = `${c.zh} ${c.en}\n${c.last - c.beat} 个时辰到天明 hours to dawn`;
    $("#caseMove").hidden = !live();
  }
  $("#caseBtn").addEventListener("click", () => $("#caseDrawer").hidden ? openCase() : closeCase());
  $("#caseClose").addEventListener("click", closeCase);
  $("#caseMove").addEventListener("click", () => { closeCase(); openMove(); });

  /* ---------- the move: the last one she makes ---------- */
  function openMove() {
    if (!live()) return;
    const list = $("#mvPaths"); list.textContent = ""; $("#mvNote").textContent = "";
    Object.entries(S.info?.fates || {}).forEach(([k, f]) => {
      const b = el("button", "btn big path-btn", `${f.zh} · ${f.en}`); b.type = "button"; b.dataset.path = k;
      b.addEventListener("click", () => {
        if (b.dataset.armed !== "1") { list.querySelectorAll("button").forEach(x => { x.dataset.armed = ""; x.classList.remove("armed"); }); b.dataset.armed = "1"; b.classList.add("armed"); b.textContent = `确定？没准备好就是死 · Sure? If you're not ready, you die.`; return; }
        attempt(k, list);
      });
      list.append(b);
    });
    $("#move").hidden = false; $("#mvClose").focus();
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
    S.dying = true;                       // the page stays still while Ray gets ready
    setTalkBusy(true);
    await new Promise(r => setTimeout(r, 3200));
    try { await refreshGame(); } catch { /* keep what we have */ }
    closeMove(); showEnding();
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
    closeCase(); closeGm(); $("#endModal").hidden = false; $("#endAgain").focus();
  }
  $("#endAgain").addEventListener("click", async () => { $("#endModal").hidden = true; await newNight(); });
  $("#endStay").addEventListener("click", () => { $("#endModal").hidden = true; });

  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    if (!$("#endModal").hidden) $("#endModal").hidden = true;
    else if (!$("#move").hidden) closeMove();
    else if (!$("#modal").hidden) closeMe();
    else if (!$("#gmDrawer").hidden) closeGm();
    else if (!$("#caseDrawer").hidden) closeCase();
    else if (!$("#logDrawer").hidden) closeLog();
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
