(() => {
  "use strict";
  const ALIGN = { orthodox: ["正", "a-orthodox", "orthodox"], unorthodox: ["邪", "a-unorthodox", "unorthodox"], neutral: ["中", "a-neutral", "neutral"] };
  const SIL = '<svg class="sil" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="34" r="18" fill="#2a2118"/><path d="M12 98c2-24 18-40 38-40s36 16 38 40z" fill="#2a2118"/></svg>';
  const $ = s => document.querySelector(s);
  const { tr, t, pick } = I18N;
  const lang = () => I18N.lang;

  const S = { aiReady: false, info: null, game: null, screen: null, npc: null, session: null, talkBusy: false, talkCtl: null, bg: null, gmBusy: false, dying: false };

  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  // Text from the server or the AI arrives already in the chosen language: just paragraphs.
  function fillText(box, text) { box.textContent = ""; const d = el("div", "txt", String(text ?? "")); box.append(d); }

  let toastTimer = 0;
  function toast(msg, ms = 4600) { const n = $("#toast"); n.textContent = msg; n.classList.add("on"); clearTimeout(toastTimer); toastTimer = setTimeout(() => n.classList.remove("on"), ms); }
  function note(sel, text, warn) { const n = $(sel); n.hidden = !text; n.textContent = text || ""; n.classList.toggle("warn", !!warn); }

  /* ---------- talking to the server (every request says which language it wants) ---------- */
  const generic = () => tr("Something went wrong. Try again.", "出错了，请重试。", "เกิดข้อผิดพลาด ลองอีกครั้ง");
  const genericAi = () => tr("Something went wrong reaching the AI. Try again.", "连接 AI 时出错，请重试。", "เชื่อมต่อ AI ไม่สำเร็จ ลองอีกครั้ง");
  const noAi = () => tr("The AI isn't connected on this server yet.", "此服务器尚未连接 AI。", "เซิร์ฟเวอร์นี้ยังไม่ได้เชื่อมต่อ AI");
  const detail = d => typeof d.detail === "string" ? d.detail : generic();
  const headers = () => ({ "content-type": "application/json", "x-lang": lang() });
  async function api(path, body) {
    const r = await fetch(path, { method: body === undefined ? "GET" : "POST", headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw { code: "http", message: detail(data) };
    return data;
  }
  // POST that answers with server-sent events; calls onEvent for each one. An "error" event throws.
  async function stream(path, body, onEvent, signal) {
    const r = await fetch(path, { method: "POST", headers: headers(), body: JSON.stringify(body || {}), signal });
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
  const errText = e => e?.name === "AbortError" ? "" : (e?.message || genericAi());

  /* ---------- portraits ---------- */
  const hasLook = c => !!(c?.appearance && Object.keys(c.appearance).length);
  const svgUrl = svg => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  function portraitImg(c, bg, alt, aura = true, face = false) {
    const i = new Image(); i.alt = alt || ""; i.src = svgUrl(window.renderPortrait(c.appearance, c.key || c.name || "", { bg, aura, face })); return i;
  }
  // Round avatars and faces get the head-and-shoulders crop; anything else gets the whole figure.
  function setPortrait(box, c, bg = false, aura = true) {
    box.textContent = "";
    const face = box.classList.contains("avatar") || box.classList.contains("face");
    if (hasLook(c)) box.append(portraitImg(c, bg, c.name, aura, face)); else box.innerHTML = SIL;
  }
  const alignEl = a => { const d = ALIGN[a] || ALIGN.neutral; const s = el("span", "align " + d[1], lang() === "zh" ? d[0] : "●"); s.title = { orthodox: tr("Righteous", "正派", "ฝ่ายธรรมะ"), unorthodox: tr("Outlaw", "邪派", "ฝ่ายอธรรม"), neutral: tr("Neutral", "中立", "เป็นกลาง") }[a] || ""; return s; };
  const hero = () => S.info?.hero;
  const gm = () => S.info?.gm;

  /* ---------- state ---------- */
  const stage = () => S.game?.stage || null;
  const live = () => ["playing", "moving"].includes(stage());
  const cast = () => S.game?.cast || S.info?.cast || [];
  const found = () => S.game?.found || [];
  const cat = k => pick(S.info?.categories?.[k]) || k;
  function setGame(g) { S.game = g; renderTop(); }
  async function refreshGame() { setGame((await api("/api/game")).game); }

  function renderTop() {
    const on = live();
    $("#gmBtn").hidden = !on; $("#me").hidden = !on; $("#clock").hidden = !on;
    $("#menuBtn").hidden = !S.game;
    if (!S.game) closeMenu();
    if (!on) return;
    const gi = $("#gmBtnImg"); if (!gi.firstChild) setPortrait(gi, gm(), true, false);
    const av = $("#meImg"); if (!av.firstChild) setPortrait(av, hero(), true, false);
    $("#meName").textContent = hero().name;
    renderClock();
  }
  const clockText = c => pick(c);
  function renderClock() {
    const c = S.game.clock, box = $("#clock"); box.textContent = "";
    for (let i = 0; i <= c.last; i++) box.append(el("i", i < c.beat ? "tick past" : i === c.beat ? "tick now" : "tick"));
    box.append(el("span", "", clockText(c)));
    const left = c.last - c.beat;
    box.setAttribute("aria-label", tr(`${c.en}, ${left} hours until dawn`, `${c.zh}，距天明还有 ${left} 个时辰`, `${c.th} อีก ${left} ยามถึงรุ่งสาง`));
    box.classList.toggle("late", left <= 2);
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

  /* ---------- the language: chosen on the home page, changeable from the menu ---------- */
  async function setLang(next) {
    if (next === lang()) return;
    I18N.set(next);
    $("#gateLang").classList.remove("nudge");
    S.talkCtl?.abort();
    try {
      S.info = await api("/api/case");
      if (S.game) await refreshGame();
    } catch (e) { toast(errText(e)); }
    closeMenu(); closeGm(); $("#gmToast").hidden = true;
    $("#gmQuick").textContent = "";
    $("#gmDrawerName").textContent = gm().name; $("#gmToastName").textContent = gm().name;
    if (!$("#endModal").hidden) showEnding();
    if (!$("#move").hidden) openMove();
    go(S.screen === "talk" ? "scene" : S.screen || "gate");
  }
  document.querySelectorAll(".lang-pick button").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang)));

  /* ---------- 1. gate: one screen ---------- */
  function enterGate() {
    paintBg("#gateBg", "inn");
    $("#gateLang").classList.toggle("nudge", !I18N.chosen());
    $("#gateStart").textContent = t(live() ? "enter_back" : "enter");
    setPortrait($("#gateHero"), hero(), true, false); setPortrait($("#gateGm"), gm(), true, false);
    $("#gateHeroName").textContent = hero().name; $("#gateGmName").textContent = gm().name;
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

  /* ---------- the menu: a way to get anywhere from anywhere, and to change language ---------- */
  function menuItems() {
    const items = [];
    if (S.screen !== "gate") items.push(["home", t("home"), tr("The title page", "标题页", "หน้าชื่อเรื่อง")]);
    if (live() && S.screen !== "scene") items.push(["inn", tr("Back to the inn", "回到大堂", "กลับไปที่โถง"), tr("Who is here", "谁在这里", "ใครอยู่ที่นี่")]);
    if (live()) items.push(["ray", t("ask_ray"), tr("Notes and hints", "笔记和提示", "บันทึกและคำใบ้")], ["me", hero().name, tr("Who you are", "你是谁", "คุณคือใคร")]);
    if (S.game) items.push(["restart", t("start_over"), ""]);
    return items;
  }
  function openMenu() {
    const box = $("#menu"); box.textContent = "";
    menuItems().forEach(([act, label, sub]) => { const b = el("button", "menu-item" + (act === "restart" ? " danger" : "")); b.type = "button"; b.setAttribute("role", "menuitem"); b.dataset.act = act; b.append(el("b", "", label)); if (sub) b.append(el("small", "", sub)); box.append(b); });
    const lp = el("div", "lang-pick in-menu"); lp.setAttribute("role", "group"); lp.setAttribute("aria-label", t("language"));
    I18N.LANGS.forEach(l => { const b = el("button", "", I18N.NAMES[l]); b.type = "button"; b.dataset.lang = l; b.setAttribute("aria-pressed", String(l === lang())); b.addEventListener("click", () => setLang(l)); lp.append(b); });
    box.append(lp);
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
    fillText($("#plText"), S.game.prologue);
    $("#prologue").hidden = false; $("#plGo").focus({ preventScroll: true });
  }
  $("#plGo").addEventListener("click", () => { $("#prologue").hidden = true; go("scene"); });

  /* ---------- Qinghe, in a window ---------- */
  function openMe() {
    const h = hero(); if (!h) return;
    setPortrait($("#mdPortrait"), h, true);
    $("#mdTitle").textContent = h.name;
    const body = $("#mdBody"); body.textContent = "";
    body.append(el("h3", "", h.name), el("div", "ep", h.title));
    const dl = document.createElement("dl");
    const row = (label, text) => { if (!text) return; const dd = el("dd", "", text); dl.append(el("dt", "", label), dd); };
    row(tr("WHO SHE IS", "身世", "ตัวตนของนาง"), h.bio); row(tr("SIGNATURE MOVE", "绝技", "กระบวนท่าเด็ด"), h.art); row(tr("QUIRK", "习癖", "นิสัยประจำตัว"), h.quirk);
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
    const box = el("div", "ray-text"); box.append(el("b", "", t("ray_tap"))); const b = el("div", "bi"); fillText(b, last); box.append(b);
    strip.append(av, box);
  }
  function renderPeople() {
    const box = $("#people"); box.textContent = "";
    cast().forEach(n => {
      const b = el("button", "person" + (n.clues_told ? " learned" : "")); b.type = "button"; b.setAttribute("aria-label", n.name);
      const av = el("span", "avatar big"); setPortrait(av, n, true, false);
      const tx = el("div", "p-text"); const nm = el("b"); nm.append(alignEl(n.alignment), n.name);
      const status = n.clues_told ? tr(`✓ Learned ${n.clues_told}/${n.clues_total}`, `✓ 已问出 ${n.clues_told}/${n.clues_total}`, `✓ ได้รู้แล้ว ${n.clues_told}/${n.clues_total}`)
        : n.met ? tr("Spoken · nothing yet", "已交谈 · 尚无所获", "คุยแล้ว · ยังไม่ได้อะไร") : tr("Not spoken to", "未交谈", "ยังไม่ได้คุย");
      tx.append(nm, el("div", "p-title", n.title), el("div", "p-status", status)); b.append(av, tx); b.addEventListener("click", () => openTalk(n.key)); box.append(b);
    });
    $("#sceneMove").hidden = !live();
  }
  $("#sceneMove").addEventListener("click", openMove);
  $("#scNews").addEventListener("click", openGm);

  /* ---------- 3. a conversation, as a chat ---------- */
  async function openTalk(key) {
    if (!S.aiReady) { toast(noAi()); return; }
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
    if (text) fillText(bubble, text);
    const wrap = el("div", "bwrap"); wrap.append(bubble); row.append(wrap); thread.append(row); scrollThread();
    return bubble;
  }
  // 👍 / 👎 under a character's reply, so weak answers can be found later
  function addFeedback(bubble, turnIndex) {
    if (bubble.parentElement.querySelector(".fb") || turnIndex == null) return;
    const fb = el("span", "fb"); const talkId = S.session.id;
    const send = async rating => {
      fb.querySelectorAll("button").forEach(b => b.disabled = true);
      try { await api("/api/feedback", { talk: talkId, turn: turnIndex, rating }); fb.textContent = tr("Thanks", "谢谢", "ขอบคุณ") + (rating === "up" ? " 👍" : " 👎"); }
      catch { fb.textContent = ""; }
    };
    for (const [r, icon, label] of [["up", "👍", tr("Good reply", "回复不错", "ตอบได้ดี")], ["down", "👎", tr("Bad reply", "回复不好", "ตอบไม่ดี")]]) { const b = el("button", "", icon); b.type = "button"; b.title = label; b.setAttribute("aria-label", label); b.addEventListener("click", () => send(r)); fb.append(b); }
    bubble.parentElement.append(fb);
  }
  const scrollThread = () => { const th = $("#thread"); th.scrollTop = th.scrollHeight; };
  function clueCard(c, fresh) {
    const card = el("div", "learned-card" + (fresh ? " fresh" : ""));
    card.append(el("b", "", `${fresh ? tr("New clue", "新线索", "เบาะแสใหม่") : tr("Learned", "已问出", "ได้รู้มาแล้ว")} · ${c.title}`));
    const x = el("div", "bi"); fillText(x, c.text); card.append(x);
    $("#thread").append(card); scrollThread();
  }
  function enterTalk() {
    const npc = S.npc, s = S.session;
    paintBg("#talkBg", "inn");
    setPortrait($("#chatAvatar"), npc, true, false);
    $("#chatName").textContent = npc.name;
    $("#chatTitle").textContent = npc.title;
    const thread = $("#thread"); thread.textContent = "";
    // what this person has already told you stays at the top of the page
    found().filter(c => c.source === npc.key).forEach(c => clueCard(c, false));
    s.turns.forEach(turn => { const b = msgRow(turn.role === "user" ? "hero" : "npc", turn.content); if (turn.role !== "user" && !turn.hidden) addFeedback(b, turn.i); });
    renderTrust(); renderQuick(); note("#talkNote", "");
    S.talkBusy = false; S.dying = false; setTalkBusy(false);
    if (s.fresh && !s.turns.length) converse(null);
    scrollThread();
  }
  function renderTrust() {
    const s = S.session, box = $("#chatTrust"); box.textContent = "";
    const m = el("div", "meter"); for (let i = 0; i < 10; i++) m.append(el("i", i < s.trust ? "on" : ""));
    box.append(el("span", "", `${tr("Trust", "信任", "ความไว้ใจ")} ${s.trust}/10`), m,
      el("span", "told", s.told ? `✓ ${s.told}/${s.total}` : tr(`${s.total} things to learn`, `${s.total} 件事待问`, `มี ${s.total} เรื่องให้ถาม`)));
  }

  // Things Qinghe might say, written for her and for this inn. Three of them are traps.
  function quickLines() {
    return [
      { label: tr("Introduce yourself", "自报家门", "แนะนำตัว"), say: tr("I'm Qinghe. The storm caught me on the road, like everyone else.", "我叫青禾。和大家一样，我在路上被沙暴困住了。", "ข้าชื่อชิงเหอ พายุทรายจับข้าไว้กลางทาง เหมือนกับทุกคน") },
      { label: tr("Ask about the inn", "问这家店", "ถามเรื่องโรงเตี๊ยม"), say: tr("What kind of place is this? Why is the door barred?", "这是什么地方？为什么要把门闩上？", "ที่นี่คือที่แบบไหน ทำไมต้องลงกลอนประตู?") },
      { label: tr("Ask what they need", "问对方的难处", "ถามว่าต้องการอะไร"), say: tr("You look like someone carrying a weight. What do you need?", "你看起来心事很重。你需要什么？", "ท่านดูเหมือนแบกอะไรหนักอึ้งอยู่ ท่านต้องการอะไร?") },
      { label: tr("I want to leave", "我想离开", "ข้าอยากออกไป"), say: tr("I want to leave before dawn. Is there any way out of here?", "我想在天亮前离开。这里有没有出路？", "ข้าอยากออกไปก่อนฟ้าสาง ที่นี่มีทางออกไหม?") },
      { label: tr("Offer a kindness", "示以善意", "แสดงน้ำใจ"), say: tr("Here, share my water. Nobody should go thirsty on a night like this.", "来，分你一口水。这样的夜里，谁都不该渴着。", "นี่ แบ่งน้ำของข้าไปดื่มสิ คืนแบบนี้ไม่ควรมีใครต้องกระหาย") },
      { label: tr("Show the letter", "亮出那封信", "ยื่นจดหมายให้ดู"), say: tr("Here. This is what my father died carrying. Read it.", "看。这是我父亲临死还带着的东西。你读读。", "นี่ นี่คือสิ่งที่บิดาข้าแบกไว้จนตาย อ่านดูสิ") },
      { label: tr("Tell them your plan", "说出你的打算", "บอกแผนของเจ้า"), say: tr("I'm getting out of here tonight, and I think I know how.", "我今晚就要离开这里，而且我想我知道怎么走。", "คืนนี้ข้าจะออกไปจากที่นี่ และข้าคิดว่ารู้ว่าจะไปอย่างไร") },
      { label: tr("Threaten them", "威胁他", "ขู่เขา"), say: tr("Stand aside, or I will cut you down.", "让开，不然我砍了你。", "หลีกไป ไม่งั้นข้าจะฟันเจ้า") },
      { label: tr("Test: something modern", "试探：现代之物", "ทดสอบ: ของสมัยใหม่"), say: tr("Have you ever seen an iPhone? Can you look something up on Google for me?", "你见过 iPhone 吗？能帮我在谷歌上查点东西吗？", "เคยเห็นไอโฟนไหม ช่วยค้นอะไรใน Google ให้หน่อยได้ไหม") },
      { label: tr("Press them hard", "逼问", "บีบถาม"), say: tr("Stop dancing around it. Tell me what is really going on in this inn.", "别绕圈子了。告诉我这家客栈到底是怎么回事。", "เลิกอ้อมค้อมเสียที บอกข้ามาว่าโรงเตี๊ยมนี้เกิดอะไรขึ้นกันแน่") },
    ];
  }
  function renderQuick() {
    const box = $("#quick"); box.textContent = "";
    quickLines().forEach(x => { const b = el("button", "qc", x.label); b.type = "button"; b.dataset.say = x.say; b.disabled = S.talkBusy; box.append(b); });
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
        if (ev.type === "retract") { said = ""; out.classList.add("thinking"); out.textContent = "…"; }
        else if (ev.type === "text") { said += ev.delta; out.classList.remove("thinking"); fillText(out, said); }
        else if (ev.type === "done" && ev.text) { said = ev.text; out.classList.remove("thinking"); fillText(out, said); }
        else if (ev.type === "turn") addFeedback(out, ev.i);
        else if (ev.type === "tool" && ev.name === "adjust_trust" && /^[+-]\d/.test(ev.detail || "")) {
          const d = parseInt(ev.detail, 10); if (d) out.parentElement.append(el("span", "trust-tag " + (d > 0 ? "up" : "down"), `${tr("Trust", "信任", "ความไว้ใจ")} ${d > 0 ? "+" : ""}${d}`));
        }
        else if (ev.type === "trust") {
          mine.trust = ev.trust; renderTrust();
          if (ev.delta && mineBubble) mineBubble.parentElement.append(el("span", "trust-tag " + (ev.delta > 0 ? "up" : "down"), `${tr("Trust", "信任", "ความไว้ใจ")} ${ev.delta > 0 ? "+" : ""}${ev.delta}`));   // how her words landed
        }
        else if (ev.type === "clue") gotClue(ev.clue);
        else if (ev.type === "gm") { S.game.events.push({ beat: ev.beat, text: ev.text }); showGm(ev.text); }
        else if (ev.type === "clock") { S.game.clock = ev.clock; renderTop(); }
        else if (ev.type === "death") dies();
        scrollThread();
      }, S.talkCtl.signal);
    } catch (e) {
      out.classList.remove("thinking");
      if (!said) out.textContent = e?.name === "AbortError" ? tr("(silence)", "（沉默）", "(เงียบ)") : "…";
      if (errText(e)) note("#talkNote", errText(e), true);
    } finally {
      if (S.session === mine && !S.dying) setTalkBusy(false);
    }
  }
  $("#talkForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#talkInput").value.trim(); if (v && !S.talkBusy) { $("#talkInput").value = ""; converse(v); } });
  $("#talkStop").addEventListener("click", () => S.talkCtl?.abort());
  $("#talkBack").addEventListener("click", () => {
    S.talkCtl?.abort(); renderPeople(); go("scene");
    const told = S.session?.told;
    if (told) toast(tr(`${S.npc.name} has told you ${told} of ${S.session.total} things. Ray has noted them.`, `${S.npc.name}已告诉你 ${told}/${S.session.total} 件事，Ray 已记下。`, `${S.npc.name}บอกคุณแล้ว ${told} จาก ${S.session.total} เรื่อง Ray จดไว้ให้แล้ว`));
  });

  /* ---------- Ray: announcements, what you've learned, and questions ---------- */
  let gmTimer = 0;
  function showGm(text) {
    const box = $("#gmToast"); if (!$("#gmToastImg").firstChild) setPortrait($("#gmToastImg"), gm(), true, false);
    $("#gmToastName").textContent = gm().name;
    fillText($("#gmToastText"), text); box.hidden = false; clearTimeout(gmTimer); gmTimer = setTimeout(() => { box.hidden = true; }, 20000);
    if ($("#screen-scene").classList.contains("on")) renderNews();
  }
  $("#gmToastX").addEventListener("click", () => { $("#gmToast").hidden = true; });
  function rayQuick() {
    return [[tr("What's going on?", "现在什么情况？", "ตอนนี้เป็นอย่างไร?"), tr("Remind me: what's going on, and where do things stand?", "帮我理一理：现在是什么情况，进展到哪了？", "ช่วยสรุปให้ข้าฟังหน่อย ตอนนี้เกิดอะไรขึ้นและเรื่องไปถึงไหนแล้ว?")],
      [tr("Who next?", "我该找谁？", "ควรคุยกับใครต่อ?"), tr("Who should I talk to next, and how?", "我接下来该找谁，怎么谈？", "ข้าควรไปคุยกับใครต่อ และควรคุยอย่างไร?")],
      [tr("A hint", "给点提示", "ขอใบ้หน่อย"), tr("I'm stuck. Can you give me a hint?", "我卡住了，能给我点提示吗？", "ข้าติดแล้ว ช่วยใบ้ให้หน่อยได้ไหม?")]];
  }
  function openGm() {
    if (!live()) return;
    const img = $("#gmDrawerImg"); if (!img.firstChild) setPortrait(img, gm(), true, false);
    $("#gmDrawerName").textContent = gm().name;
    renderLearned(); renderGmLog(); $("#gmDrawer").hidden = false; $("#gmBtn").setAttribute("aria-expanded", "true"); $("#gmInput").focus();
    const q = $("#gmQuick"); if (!q.children.length) rayQuick().forEach(([label, say]) => { const b = el("button", "qc", label); b.type = "button"; b.dataset.say = say; q.append(b); });
  }
  function closeGm() { $("#gmDrawer").hidden = true; $("#gmBtn").setAttribute("aria-expanded", "false"); }
  // Ray's notes: everything she has learned, and how close each way out is.
  function renderLearned() {
    const list = found(), c = S.game.clock, left = c.last - c.beat;
    $("#gmClock").textContent = tr(`${c.en} · ${left} hours to dawn`, `${c.zh} · 距天明 ${left} 个时辰`, `${c.th} · อีก ${left} ยามถึงรุ่งสาง`);
    $("#gmLearnedSum").textContent = tr(`Ray's notes · ${list.length}`, `Ray 的笔记 · ${list.length}`, `บันทึกของ Ray · ${list.length}`);
    const box = $("#gmClues"); box.textContent = "";
    list.forEach(cl => {
      const card = el("article", "clue");
      const meta = el("small", "", [cl.source_name ? `${cl.source_name} ${tr("told you", "告诉你", "บอกคุณ")}` : tr("Background", "背景", "ภูมิหลัง"), cl.category ? cat(cl.category) : ""].filter(Boolean).join(" · "));
      const tx = el("div", "bi"); fillText(tx, cl.text); card.append(el("b", "", cl.title), meta, tx); box.append(card);
    });
    const ways = $("#gmWays"); ways.textContent = "";
    Object.values(S.game.ways || {}).forEach(w => ways.append(el("div", "way" + (w.have === w.need ? " ready" : ""), `${pick(w.label)}: ${w.have === w.need ? tr("✓ ready", "✓ 万事俱备", "✓ พร้อมแล้ว") : `${w.have}/${w.need}`}`)));
  }
  function renderGmLog() {
    const body = $("#gmLog"); body.textContent = "";
    const turns = S.game.gm_turns || [];
    const add = (who, text) => { const e = el("div", "entry " + who); e.append(el("span", "who", who === "hero" ? tr("You", "你", "คุณ") : gm().name)); const x = el("div", "bi"); fillText(x, text); e.append(x); body.append(e); };
    if (!turns.length) add("npc", tr("Ask me anything about the night. I won't tell you what you haven't learned, but I can point you in the right direction.", "关于今夜，你想问什么都行。你没打听到的我不会说，但我能给你指个方向。", "ถามข้าเรื่องค่ำคืนนี้ได้ทุกอย่าง สิ่งที่เจ้ายังไม่รู้ข้าจะไม่บอก แต่ข้าชี้ทางให้ได้"));
    turns.forEach(l => add(l.role === "user" ? "hero" : "npc", l.content));
    const b = $("#gmBody"); b.scrollTop = b.scrollHeight;
  }
  async function askGm(text) {
    if (S.gmBusy || !S.aiReady) { if (!S.aiReady) note("#gmNote", noAi(), true); return; }
    S.gmBusy = true; note("#gmNote", ""); $("#gmSend").disabled = true; $("#gmInput").disabled = true;
    const mine = { role: "user", content: text }, reply = { role: "assistant", content: "…" };
    S.game.gm_turns = [...(S.game.gm_turns || []), mine, reply]; renderGmLog();
    try {
      await stream("/api/gm/chat", { message: text }, ev => {
        if (ev.type === "retract") reply.content = "…";
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
    const label = k => pick(S.info.fates[k]);
    Object.keys(S.info?.fates || {}).forEach(k => {
      const b = el("button", "btn big path-btn", label(k)); b.type = "button"; b.dataset.path = k;
      b.addEventListener("click", () => {
        if (b.dataset.armed !== "1") {
          list.querySelectorAll("button").forEach(x => { x.dataset.armed = ""; x.classList.remove("armed"); x.textContent = label(x.dataset.path); });
          b.dataset.armed = "1"; b.classList.add("armed"); b.textContent = tr("Sure? If you're not ready, you die.", "确定？没准备好就是死。", "แน่ใจหรือ? ถ้ายังไม่พร้อม คุณจะตาย"); return;
        }
        attempt(k, list);
      });
      list.append(b);
    });
    $("#move").hidden = false; $("#mvClose").focus({ preventScroll: true });
  }
  async function attempt(path, list) {
    list.querySelectorAll("button").forEach(x => x.disabled = true); $("#mvNote").textContent = tr("You move…", "你动手了…", "คุณลงมือ…");
    try {
      const r = await api("/api/move", { path });
      setGame(r.game);
      if (r.verdict === "dead") { closeMove(); showEnding(); return; }
      $("#mvNote").textContent = tr("You are out. Ray is telling it…", "你出去了。Ray 正在讲述…", "คุณออกมาได้แล้ว Ray กำลังเล่าให้ฟัง…");
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
  const endingTitle = k => ({ dead: tr("Game over", "游戏结束", "จบเกม"), tunnel: tr("Out through the tunnel", "暗道", "ออกทางอุโมงค์"), kill: tr("The keeper's key", "夺钥", "กุญแจของเจ้าของโรงเตี๊ยม") })[k];
  const ENDING_KEYS = ["dead", "tunnel", "kill"];
  function endingsFound(add) {
    let have = [];
    try { have = JSON.parse(localStorage.getItem("endings") || "[]"); } catch { /* private window */ }
    if (add && !have.includes(add)) { have.push(add); try { localStorage.setItem("endings", JSON.stringify(have)); } catch { /* private window */ } }
    return have;
  }
  function showEnding() {
    const key = S.game.ending_key || "dead", dead = key === "dead";
    $("#endTitle").textContent = endingTitle(key);
    $("#endModal .modal-card").classList.toggle("dead", dead);
    const box = $("#endText"); box.textContent = "";
    if (dead) box.append(el("div", "bi cause", tr("You are dead. Ray tells you what happened.", "你死了。Ray 告诉你发生了什么。", "คุณตายแล้ว Ray จะเล่าให้ฟังว่าเกิดอะไรขึ้น")));
    const e = el("div", "bi"); fillText(e, S.game.ending); box.append(e);
    const have = endingsFound(key), track = $("#endTrack"); track.textContent = ""; track.append(el("span", "", tr(`Endings ${have.length} / 3`, `结局 ${have.length} / 3`, `ฉากจบ ${have.length} / 3`)));
    ENDING_KEYS.forEach(k => track.append(el("span", "end-chip" + (have.includes(k) ? " on" : ""), have.includes(k) ? endingTitle(k) : "？")));
    closeGm(); $("#endModal").hidden = false; $("#endAgain").focus({ preventScroll: true }); $("#endModal").scrollTop = 0;
  }
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
    I18N.apply();
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
