(() => {
  "use strict";
  const SIL = '<svg class="sil" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="34" r="18" fill="#2a2118"/><path d="M12 98c2-24 18-40 38-40s36 16 38 40z" fill="#2a2118"/></svg>';
  const DIE = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];
  const $ = s => document.querySelector(s);
  const { tr, t } = I18N;
  const pick = x => typeof x === "string" ? x : I18N.pick(x);      // text from the server is already in the chosen language
  const lang = () => I18N.lang;

  const S = { aiReady: false, info: null, game: null, screen: null, session: null, talkBusy: false, talkCtl: null, bg: null, gmBusy: false, fightBusy: false, dying: false };

  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  function fillText(box, text) { box.textContent = ""; box.append(el("div", "txt", String(text ?? ""))); }

  let toastTimer = 0;
  function toast(msg, ms = 5200) { const n = $("#toast"); n.textContent = msg; n.classList.add("on"); clearTimeout(toastTimer); toastTimer = setTimeout(() => n.classList.remove("on"), ms); }
  function note(sel, text, warn) { const n = $(sel); n.hidden = !text; n.textContent = text || ""; n.classList.toggle("warn", !!warn); }

  /* ---------- talking to the server (every request says which language it wants) ---------- */
  const generic = () => tr("Something went wrong. Try again.", "出错了，请重试。", "เกิดข้อผิดพลาด ลองอีกครั้ง");
  const genericAi = () => tr("Something went wrong reaching the AI. Try again.", "连接 AI 时出错，请重试。", "เชื่อมต่อ AI ไม่สำเร็จ ลองอีกครั้ง");
  const noAi = () => tr("The AI isn't connected on this server yet.", "此服务器尚未连接 AI。", "เซิร์ฟเวอร์นี้ยังไม่ได้เชื่อมต่อ AI");
  const detail = d => typeof d.detail === "string" ? d.detail : generic();
  const headers = () => ({ "content-type": "application/json", "x-lang": lang(), "x-ref": document.referrer || "" });
  async function api(path, body) {
    const r = await fetch(path, { method: body === undefined ? "GET" : "POST", headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw { code: "http", message: detail(data) };
    return data;
  }
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
  function setPortrait(box, c, bg = true, aura = false) {
    box.textContent = "";
    const face = box.classList.contains("avatar") || box.classList.contains("face");
    if (hasLook(c)) { const i = new Image(); i.alt = c.name || ""; i.src = svgUrl(window.renderPortrait(c.appearance, c.key || c.name || "", { bg, aura, face })); box.append(i); }
    else box.innerHTML = SIL;
  }
  const gm = () => S.info?.gm;
  const hero = () => S.game?.hero;
  const stage = () => S.game?.stage || null;
  const live = () => stage() === "playing";
  const over = () => stage() === "dead" || stage() === "solved";
  const npcByKey = k => S.game?.npcs.find(n => n.key === k) || S.info?.cast.find(n => n.key === k);
  const moodOf = m => S.info.moods[m];

  function setGame(g) { S.game = g; renderTop(); }
  async function refreshGame() { setGame((await api("/api/game")).game); }

  function renderTop() {
    const on = live();
    $("#gmBtn").hidden = !on;
    if (on && !$("#gmBtnImg").firstChild) setPortrait($("#gmBtnImg"), gm(), true, false);
  }

  /* ---------- screens ---------- */
  const SCREENS = ["gate", "game", "talk", "fight"];
  // Once a night is over and its ending has been read, the home page offers a brand-new thief instead of the finished one.
  async function freshThief() {
    try { await api("/api/game/reset", {}); setGame((await api("/api/roll", {})).game); } catch (e) { toast(errText(e)); }
  }
  function go(name) {
    if (name === "gate" && over()) { freshThief().then(() => { if (over()) S.game = null; go("gate"); }); return; }
    if (S.bg) { S.bg.stop(); S.bg = null; }
    if (name !== "talk") S.talkCtl?.abort();
    $("#screen-loading").classList.remove("on");
    SCREENS.forEach(s => $("#screen-" + s).classList.toggle("on", s === name));
    S.screen = name;
    window.scrollTo(0, 0);
    ({ gate: enterGate, game: enterGame, talk: enterTalk, fight: enterFight })[name]();
  }
  const paintBg = (sel, kind) => { S.bg = window.Scenes.paint($(sel), kind); };

  /* ---------- language ---------- */
  async function setLang(next) {
    if (next === lang()) return;
    I18N.set(next);
    S.talkCtl?.abort();
    try { S.info = await api("/api/case"); await refreshGame(); } catch (e) { toast(errText(e)); }
    closeGm(); $("#modal").hidden = true;
    $("#gmQuick").textContent = "";
    if (!$("#endModal").hidden) showEnding();
    go(S.screen === "talk" ? "game" : S.screen === "fight" ? "fight" : S.screen || "gate");
  }
  document.querySelectorAll(".lang-pick button").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang)));

  /* ---------- 1. home: scene, goal, roll a thief, Ray ---------- */
  const STAT_ORDER = ["str", "int", "agi"];
  const STAT_ICON = { str: "💪", int: "🧠", agi: "🪶" };
  function derived(k, h) {
    return k === "str" ? tr(`${h.hp_max} hit points`, `生命值 ${h.hp_max}`, `พลังชีวิต ${h.hp_max}`)
      : k === "agi" ? tr(`+${h.defence_bonus} to every defence roll`, `每次防御骰 +${h.defence_bonus}`, `+${h.defence_bonus} ทุกครั้งที่ทอยป้องกัน`)
        : tr(`start with ${Math.min(5, 1 + Math.floor(h.int / 4))} Qi, regain ${h.int >= 11 ? 2 : 1} per guard`, `起始气 ${Math.min(5, 1 + Math.floor(h.int / 4))}，每次防守回复 ${h.int >= 11 ? 2 : 1}`, `เริ่มด้วยลมปราณ ${Math.min(5, 1 + Math.floor(h.int / 4))} ฟื้น ${h.int >= 11 ? 2 : 1} ต่อการตั้งรับ`);
  }
  function renderRoll(h) {
    const box = $("#gateStats"); box.textContent = "";
    STAT_ORDER.forEach(k => {
      const row = el("div", "stat");
      const top = el("div", "stat-top"); top.append(el("span", "stat-name", `${STAT_ICON[k]} ${pick(S.info.stats[k].name)}`), el("b", "stat-val", h[k]));
      const bar = el("div", "bar"); const fill = el("i"); fill.style.width = Math.round((h[k] / 16) * 100) + "%"; bar.append(fill);
      row.append(top, bar, el("small", "", [pick(S.info.stats[k].does), derived(k, h)].filter(Boolean).join(" · "))); box.append(row);
    });
    const arts = $("#gateArts"); arts.textContent = "";
    [["off", tr("Attack art", "进攻武功", "วิชาโจมตี"), "⚔"], ["defn", tr("Defence art", "防御武功", "วิชาป้องกัน"), "🛡"]].forEach(([k, label, icon]) => {
      const a = h[k], card = el("div", "art"); card.append(el("small", "", `${icon} ${label}`), el("b", "", a.name), el("p", "", a.does)); arts.append(card);
    });
  }
  function enterGate() {
    paintBg("#gateBg", "inn");
    const g = S.game, h = g?.hero;
    $("#gateStart").textContent = t(live() ? "enter_back" : "enter");
    $("#gateSub").textContent = S.info.title;
    $("#gateSetup").textContent = S.info.setup; $("#gateGoal").textContent = S.info.goal; $("#gateHow").textContent = S.info.how_to;
    setPortrait($("#gateGm"), gm(), true, false); $("#gateGmName").textContent = gm().name;
    if (h) { setPortrait($("#gateHero"), h, true, false); $("#gateHeroName").textContent = h.name; $("#gateHeroTitle").textContent = h.title; $("#gateHeroBio").textContent = h.bio; renderRoll(h); }
    $("#reroll").hidden = live() || over();
    $("#gateReset").hidden = !(live() || over());
  }
  async function reroll() {
    if (live()) return;
    const btn = $("#reroll"); btn.disabled = true; btn.classList.add("rolling");
    const spin = setInterval(() => document.querySelectorAll(".stat-val").forEach(v => { v.textContent = 6 + Math.floor(Math.random() * 11); }), 70);
    try { const [r] = await Promise.all([api("/api/roll", {}), sleep(750)]); setGame(r.game); }
    catch (e) { toast(errText(e)); }
    clearInterval(spin); btn.disabled = false; btn.classList.remove("rolling");
    if (S.screen === "gate") enterGate();
  }
  $("#reroll").addEventListener("click", reroll);
  async function begin() {
    if (live()) { go(S.game.fight ? "fight" : "game"); return; }
    if (over()) { go("game"); showEnding(); return; }
    try { setGame((await api("/api/game/start", {})).game); } catch (e) { toast(errText(e)); return; }
    setPortrait($("#plPortrait"), gm(), true); fillText($("#plText"), S.info.prologue);
    $("#prologue").hidden = false; $("#plGo").focus({ preventScroll: true });
  }
  $("#gateStart").addEventListener("click", begin);
  $("#plGo").addEventListener("click", () => { $("#prologue").hidden = true; go("game"); });
  $("#brandBtn").addEventListener("click", () => go("gate"));

  $("#gateReset").addEventListener("click", () => { if (confirm(tr("End this night and start over?", "结束这一夜并重新开始？", "จบคืนนี้และเริ่มใหม่?"))) newNight(); });

  /* ---------- your thief, in a window ---------- */
  function openMe() {
    const h = hero(); if (!h) return;
    const body = $("#mdBody"); body.textContent = "";
    const head = el("div", "who"); const face = el("div", "face"); setPortrait(face, h, true, false);
    const tx = el("div", "who-text"); tx.append(el("b", "", h.name), el("i", "", " " + h.title), el("p", "small", h.bio)); head.append(face, tx);
    const stats = el("div", "stats"); STAT_ORDER.forEach(k => stats.append(el("div", "stat-line", `${STAT_ICON[k]} ${pick(S.info.stats[k].name)} ${h[k]}${derived(k, h) ? " · " + derived(k, h) : ""}`)));
    const arts = el("div", "arts"); [h.off, h.defn].forEach(a => { const c = el("div", "art"); c.append(el("b", "", a.name), el("p", "", a.does)); arts.append(c); });
    body.append(head, stats, arts); $("#modal").hidden = false; $("#mdClose").focus({ preventScroll: true });
  }
  $("#mdClose").addEventListener("click", () => { $("#modal").hidden = true; });
  $("#modal").addEventListener("click", e => { if (e.target.id === "modal") $("#modal").hidden = true; });
  async function newNight() {
    try { await api("/api/game/reset", {}); setGame((await api("/api/roll", {})).game); } catch (e) { toast(errText(e)); return; }
    closeGm(); $("#endModal").hidden = true; $("#prologue").hidden = true; S.session = null; S.dying = false;
    go("gate");
  }

  /* ---------- 2. the inn ---------- */
  const bar = (v, max, cls) => { const b = el("div", "bar " + (cls || "")); const f = el("i"); f.style.width = Math.max(0, Math.min(100, (v / max) * 100)) + "%"; b.append(f); return b; };
  function renderHud() {
    const g = S.game, h = g.hero, box = $("#hud"); box.textContent = "";
    const top = el("div", "hud-top");
    const av = el("button", "avatar"); av.type = "button"; av.setAttribute("aria-label", h.name); setPortrait(av, h, true, false); av.addEventListener("click", openMe);
    const hp = el("div", "hp"); hp.append(el("div", "hp-text", `❤ ${h.hp} / ${h.hp_max}`), bar(h.hp, h.hp_max, h.hp / h.hp_max < .35 ? "low" : "hp-bar"));
    const chips = el("div", "chips"); STAT_ORDER.forEach(k => chips.append(el("span", "chip", `${STAT_ICON[k]} ${h[k]}`)));
    top.append(av, hp, chips);
    const storm = el("div", "storm"); const track = el("div", "track");
    for (let i = 1; i <= g.storm_end; i++) track.append(el("i", "beat" + (i <= g.tick ? " past" : "") + (i === g.exit_at ? " exit" : "")));
    storm.append(track, el("div", "storm-text", g.can_leave ? tr("🌤 The storm has passed. You can leave.", "🌤 沙暴已过，你可以走了。", "🌤 พายุผ่านไปแล้ว เจ้าออกไปได้") : tr(`🌪 Beat ${g.tick} · you can leave at beat ${g.exit_at}`, `🌪 第 ${g.tick} 拍 · 第 ${g.exit_at} 拍可以离开`, `🌪 จังหวะที่ ${g.tick} · ออกได้ที่จังหวะ ${g.exit_at}`)));
    box.append(top, storm);
  }
  function renderFeed() {
    const box = $("#feed"); box.textContent = "";
    const items = S.game.feed.slice(-5);
    items.forEach(f => { const d = el("div", "f f-" + f.kind); d.append(el("span", "b", `${f.tick}`), el("span", "", f.text)); box.append(d); });
    box.scrollTop = box.scrollHeight;
  }
  function personCard(n) {
    const away = !["here", "calm"].includes(n.status);
    const c = el("div", "person" + (n.status === "down" ? " down" : "") + (n.status === "calm" ? " calm" : ""));
    const av = el("span", "avatar big"); setPortrait(av, n, true, false);
    const tx = el("div", "p-text");
    const mood = moodOf(n.mood);
    const nm = el("b", "", n.name); tx.append(nm, el("div", "p-title", n.title), el("div", "mood m-" + n.mood, `${mood.icon} ${pick(mood.name)}`));
    let st = "";
    if (n.status === "down") st = tr("Defeated", "已被击败", "พ่ายแพ้แล้ว");
    else if (n.status === "calm") st = tr("Standing down", "已放下戒备", "ผ่อนท่าทีลงแล้ว");
    else if (n.fuse_left != null) st = n.fuse_left > 0 ? tr(`⏳ Loses patience in ${n.fuse_left} beat${n.fuse_left === 1 ? "" : "s"}`, `⏳ ${n.fuse_left} 拍后失去耐心`, `⏳ หมดความอดทนใน ${n.fuse_left} จังหวะ`) : tr("⏳ About to attack", "⏳ 即将动手", "⏳ กำลังจะลงมือ");
    if (st) tx.append(el("div", "p-status", st));
    if (n.status === "here" || n.status === "calm") {
      const m = el("div", "meters"); m.append(el("small", "", `${tr("Trust", "信任", "ไว้ใจ")} ${n.trust}/10`), bar(n.trust, 10, "trust-bar"), el("small", "", `❤ ${n.hp}/${n.hp_max}`), bar(n.hp, n.hp_max, "foe-bar")); tx.append(m);
    }
    c.append(av, tx);
    if (away) return c;
    const acts = el("div", "p-acts");
    const talk = el("button", "btn jade sm", tr("Talk", "交谈", "คุย")); talk.type = "button"; talk.addEventListener("click", () => openTalk(n.key));
    const fight = el("button", "btn sm", tr("Fight", "动手", "สู้")); fight.type = "button"; fight.addEventListener("click", () => startFight(n.key));
    acts.append(talk, fight); c.append(acts);
    return c;
  }
  // people who are here and might still do something come first; the defeated sink to the bottom
  const rank = n => ({ here: 0, calm: 1, fighting: 0, hostile: 0, down: 3 })[n.status] ?? 2;
  function renderPeople() {
    const box = $("#people"); box.textContent = "";
    [...S.game.npcs].sort((a, b) => rank(a) - rank(b)).forEach(n => box.append(personCard(n)));
    const g = S.game;
    $("#incoming").textContent = g.incoming && !g.can_leave ? tr("Out in the storm, somebody else is coming…", "风沙里，还有人在赶来…", "ในพายุ ยังมีใครบางคนกำลังมา…") : "";
    const door = $("#doorBtn");
    door.classList.toggle("jade", g.can_leave); door.classList.toggle("ghost", !g.can_leave);
    door.textContent = g.can_leave ? tr("🚪 Walk out of the inn", "🚪 走出客栈", "🚪 เดินออกจากโรงเตี๊ยม") : tr(`🚪 Leave into the storm (${g.exit_at - g.tick} beats until it passes)`, `🚪 走进沙暴（还有 ${g.exit_at - g.tick} 拍沙暴才过去）`, `🚪 ออกไปในพายุ (อีก ${g.exit_at - g.tick} จังหวะพายุจึงผ่าน)`);
  }
  function enterGame() {
    if (S.game.fight) { go("fight"); return; }
    paintBg("#gameBg", "inn");
    renderHud(); renderFeed(); renderPeople();
  }
  $("#doorBtn").addEventListener("click", async () => {
    if (!S.game.can_leave) { $("#leaveModal").hidden = false; return; }
    await leave();
  });
  $("#lvNo").addEventListener("click", () => { $("#leaveModal").hidden = true; });
  $("#lvYes").addEventListener("click", async () => { $("#leaveModal").hidden = true; await leave(); });
  async function leave() {
    try { setGame((await api("/api/leave", {})).game); } catch (e) { toast(errText(e)); return; }
    await finish();
  }

  /* ---------- 3. a conversation ---------- */
  async function openTalk(key) {
    if (!S.aiReady) { toast(noAi()); return; }
    let sess;
    try { sess = await api("/api/talks", { npc: key }); } catch (e) { toast(errText(e)); return; }
    S.session = sess; setGame(sess.game);
    go("talk");
  }
  const sessNpc = () => npcByKey(S.session.npc.key);
  function msgRow(who, text) {
    const row = el("div", "msg " + who);
    if (who === "npc") { const av = el("span", "avatar"); setPortrait(av, S.session.npc, true, false); row.append(av); }
    const bubble = el("div", "bubble"); if (text) fillText(bubble, text);
    const wrap = el("div", "bwrap"); wrap.append(bubble); row.append(wrap); $("#thread").append(row); scrollThread();
    return bubble;
  }
  function addFeedback(bubble, turnIndex) {
    if (bubble.parentElement.querySelector(".fb") || turnIndex == null) return;
    const fb = el("span", "fb"); const talkId = S.session.id;
    const send = async rating => {
      fb.querySelectorAll("button").forEach(b => b.disabled = true);
      try { await api("/api/feedback", { talk: talkId, turn: turnIndex, rating }); fb.textContent = tr("Thanks", "谢谢", "ขอบคุณ") + (rating === "up" ? " 👍" : " 👎"); } catch { fb.textContent = ""; }
    };
    for (const [r, icon] of [["up", "👍"], ["down", "👎"]]) { const b = el("button", "", icon); b.type = "button"; b.addEventListener("click", () => send(r)); fb.append(b); }
    bubble.parentElement.append(fb);
  }
  const scrollThread = () => { const th = $("#thread"); th.scrollTop = th.scrollHeight; };
  function renderMeta() {
    const n = sessNpc(), box = $("#chatMeta"); box.textContent = "";
    const mood = moodOf(n.mood), left = Math.max(0, n.talk_limit - n.talks);
    const head = el("div", "goal-head");
    head.append(el("span", "mood m-" + n.mood, `${mood.icon} ${pick(mood.name)}`), el("span", "left" + (left <= 1 && !n.rewarded ? " last" : ""), n.rewarded ? tr("✓ Settled", "✓ 已谈妥", "✓ จบเรื่องแล้ว") : tr(`${left} exchange${left === 1 ? "" : "s"} left`, `还能说 ${left} 句`, `เหลือ ${left} ครั้ง`)));
    const goal = el("div", "goal-text", (n.rewarded ? "✓ " : "🎯 ") + n.goal);
    const meter = el("div", "goal-meter"); meter.append(el("small", "", `${tr("Trust", "信任", "ไว้ใจ")} ${S.session.trust}/10`));
    const track = el("div", "bar trust-bar"); const fill = el("i"); fill.style.width = S.session.trust * 10 + "%"; track.append(fill);
    const mark = el("span", "goal-mark"); mark.style.left = n.goal_trust * 10 + "%"; mark.title = tr("Goal", "目标", "เป้าหมาย"); track.append(mark); meter.append(track);
    box.append(head, goal, meter);
    if (n.fuse_left != null && n.status === "here" && !n.rewarded) box.append(el("span", "p-status", n.fuse_left > 0 ? tr(`⏳ ${n.fuse_left} beat${n.fuse_left === 1 ? "" : "s"} until they lose patience`, `⏳ ${n.fuse_left} 拍后失去耐心`, `⏳ อีก ${n.fuse_left} จังหวะจะหมดความอดทน`) : tr("⏳ About to attack", "⏳ 即将动手", "⏳ กำลังจะลงมือ")));
    box.append(el("small", "stake", n.rewarded ? "" : tr("If the talk runs out, they strike first.", "话说完还没谈妥，他会抢先动手。", "ถ้าเจรจาไม่สำเร็จ เขาจะลงมือก่อน")));
    const done = n.rewarded;
    $("#talkInput").disabled = done || S.talkBusy; $("#talkSend").disabled = done;
    document.querySelectorAll("#quick .qc").forEach(b => b.disabled = done || S.talkBusy);
  }
  function quickLines() {
    return [
      { label: tr("Just a traveller", "只是过路人", "แค่ผู้เดินทาง"), say: tr("I'm just a traveller the storm caught on the road, like you.", "我只是个被沙暴困在路上的旅人，和你一样。", "ข้าเป็นแค่ผู้เดินทางที่พายุจับไว้กลางทาง เหมือนท่าน") },
      { label: tr("Tell the truth", "说实话", "บอกความจริง"), say: tr("All right. I stole the magistrate's seal. I'm not proud of it, but I had my reasons.", "好吧。我偷了知府的玉印。我不引以为傲，但我有我的理由。", "ก็ได้ ข้าขโมยตราของเจ้าเมือง ข้าไม่ภูมิใจ แต่ข้ามีเหตุผลของข้า") },
      { label: tr("Offer a drink", "递杯茶", "ชวนดื่มชา"), say: tr("Here, share my tea. Nobody should freeze on a night like this.", "来，喝我这杯茶。这样的夜里，谁都不该冻着。", "นี่ ดื่มชาของข้าสิ คืนแบบนี้ไม่ควรมีใครต้องหนาว") },
      { label: tr("Ask about them", "问问对方", "ถามเรื่องเขา"), say: tr("And what brings you out in this storm?", "那你呢，这样的风沙天，怎么出来了？", "แล้วท่านล่ะ อะไรพาท่านออกมาในพายุแบบนี้?") },
      { label: tr("Offer silver", "塞点银子", "ยื่นเงินให้"), say: tr("There's silver in it for you if you forget you ever saw me.", "只要你忘了见过我，这些银子就是你的。", "มีเงินให้ท่านถ้าท่านลืมไปว่าเคยเห็นข้า") },
      { label: tr("Threaten", "威胁", "ขู่"), say: tr("Stay out of my way, or I will cut you down.", "别挡我的路，不然我砍了你。", "อย่าขวางทางข้า ไม่งั้นข้าจะฟันท่าน") },
    ];
  }
  function renderQuick() {
    const box = $("#quick"); box.textContent = "";
    quickLines().forEach(x => { const b = el("button", "qc", x.label); b.type = "button"; b.dataset.say = x.say; b.disabled = S.talkBusy; box.append(b); });
  }
  $("#quick").addEventListener("click", e => { const b = e.target.closest(".qc"); if (b && !S.talkBusy) converse(b.dataset.say); });
  function setTalkBusy(on) {
    S.talkBusy = on;
    const done = !!(S.session && sessNpc()?.rewarded);
    $("#talkSend").hidden = on; $("#talkStop").hidden = !on; $("#talkInput").disabled = on || done; $("#talkSend").disabled = done; $("#chatFight").disabled = done;
    document.querySelectorAll("#quick .qc").forEach(b => b.disabled = on || done);
  }
  function enterTalk() {
    const npc = S.session.npc, s = S.session;
    paintBg("#talkBg", "inn");
    setPortrait($("#chatAvatar"), npc, true, false);
    $("#chatName").textContent = npc.name; $("#chatTitle").textContent = npc.title;
    const thread = $("#thread"); thread.textContent = "";
    s.turns.forEach(turn => { const b = msgRow(turn.role === "user" ? "hero" : "npc", turn.content); if (turn.role !== "user") addFeedback(b, turn.i); });
    renderMeta(); renderQuick(); note("#talkNote", "");
    $("#chatFight").textContent = t("fight"); $("#chatFight").classList.remove("armed");
    S.talkBusy = false; setTalkBusy(false);
    if (s.fresh && !s.turns.length) converse(null);
    scrollThread();
  }
  const tag = d => el("span", "trust-tag " + (d > 0 ? "up" : "down"), `${tr("Trust", "信任", "ไว้ใจ")} ${d > 0 ? "+" : ""}${d}`);
  async function converse(text) {
    if (S.talkBusy || !S.session) return;
    const opening = text === null, id = S.session.id, mine = S.session;
    note("#talkNote", "");
    let mineBubble = null, said = "", fightNow = false;
    if (!opening) mineBubble = msgRow("hero", text);
    const out = msgRow("npc", ""); out.classList.add("thinking"); out.textContent = "…";
    S.talkCtl = new AbortController(); setTalkBusy(true);
    try {
      await stream(`/api/talks/${id}/${opening ? "open" : "chat"}`, opening ? {} : { message: text }, ev => {
        if (S.session !== mine) return;
        if (ev.type === "retract") { said = ""; out.textContent = "…"; }
        else if (ev.type === "text") { said += ev.delta; out.classList.remove("thinking"); fillText(out, said); }
        else if (ev.type === "done" && ev.text) { said = ev.text; out.classList.remove("thinking"); fillText(out, said); }
        else if (ev.type === "turn") addFeedback(out, ev.i);
        else if (ev.type === "trust") { mine.trust = ev.trust; if (ev.delta && mineBubble) mineBubble.parentElement.append(tag(ev.delta)); }
        else if (ev.type === "feed") { S.game.feed.push(ev.item); if (["arrival", "gain", "calm", "storm"].includes(ev.item.kind)) toast(ev.item.text, 7000); }
        else if (ev.type === "fight") fightNow = true;
        else if (ev.type === "resolved") toast(tr("Settled: you got what you came for. Back to the inn when you are ready.", "谈妥了：你得到了想要的。准备好就回大堂吧。", "เจรจาสำเร็จ: เจ้าได้สิ่งที่ต้องการ พร้อมแล้วก็กลับไปที่โถง"), 6000);
        else if (ev.type === "state") { setGame(ev.game); renderMeta(); }
        scrollThread();
      }, S.talkCtl.signal);
    } catch (e) {
      out.classList.remove("thinking");
      if (!said) out.textContent = e?.name === "AbortError" ? tr("(silence)", "（沉默）", "(เงียบ)") : "…";
      if (errText(e)) note("#talkNote", errText(e), true);
    } finally { if (S.session === mine) setTalkBusy(false); }
    if (fightNow && S.session === mine) { setTalkBusy(true); await sleep(1400); S.session = null; go("fight"); }
  }
  $("#talkForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#talkInput").value.trim(); if (v && !S.talkBusy) { $("#talkInput").value = ""; converse(v); } });
  $("#talkStop").addEventListener("click", () => S.talkCtl?.abort());
  $("#talkBack").addEventListener("click", () => { S.talkCtl?.abort(); go("game"); });
  $("#chatFight").addEventListener("click", async e => {
    const b = e.currentTarget;
    if (!b.classList.contains("armed")) { b.classList.add("armed"); b.textContent = tr("Sure?", "确定？", "แน่ใจ?"); setTimeout(() => { b.classList.remove("armed"); b.textContent = t("fight"); }, 3000); return; }
    S.talkCtl?.abort(); await startFight(S.session.npc.key);
  });

  /* ---------- 4. a fight: read what they are about to do, then choose ---------- */
  async function startFight(key) {
    try { const r = await api("/api/fight/start", { npc: key }); setGame(r.game); S.session = null; } catch (e) { toast(errText(e)); return; }
    go("fight");
  }
  const qiPips = (qi, max) => { const w = el("span", "pips"); for (let i = 0; i < max; i++) w.append(el("i", i < qi ? "on" : "")); return w; };
  function fighterBox(box, c, hp, max, label, qi) {
    box.textContent = "";
    const av = el("span", "avatar big"); setPortrait(av, c, true, false);
    box.append(av, el("b", "", label), el("div", "hp-text", `❤ ${hp} / ${max}`), bar(hp, max, hp / max < .35 ? "low" : "hp-bar"));
    if (qi != null) { const q = el("div", "qi", ""); q.append(el("small", "", tr("Qi", "气", "ลมปราณ") + " "), qiPips(qi, S.game.hero.qi_max)); box.append(q); }
  }
  function renderDuel(foeKey, foeHp, foeMax) {
    const g = S.game, h = g.hero, f = g.fight;
    const key = foeKey || f?.npc; if (!key) return;
    const foe = npcByKey(key);
    fighterBox($("#fHero"), h, h.hp, h.hp_max, h.name, h.qi);
    fighterBox($("#fFoe"), foe, foeHp ?? f.hp, foeMax ?? f.hp_max, foe.name);
  }
  const INTENT = {
    heavy: n => [tr("⚠ HEAVY BLOW", "⚠ 重击", "⚠ ฟาดหนัก"), tr(`${n} winds up for a crushing blow. Counter it, or guard!`, `${n}蓄力要来一记重击。反击它，或者防守！`, `${n} รวบรวมแรงเตรียมฟาดหนัก สวนกลับ หรือตั้งรับ!`)],
    quick: n => [tr("⚡ QUICK STRIKE", "⚡ 快攻", "⚡ ฟันเร็ว"), tr(`${n} lunges fast. Hit first, or guard.`, `${n}出手极快。抢先攻击，或者防守。`, `${n} พุ่งเข้าฟันเร็ว ชิงโจมตีก่อน หรือตั้งรับ`)],
    guard: n => [tr("🛡 BRACING", "🛡 严守", "🛡 ตั้งท่ารับ"), tr(`${n} braces behind a tight guard: harder to hit, and no attack this round. Use your art, or catch your breath.`, `${n}收势严守：更难打中，这一回合不会进攻。用武功，或者调息。`, `${n} ตั้งท่ารับแน่น โดนยากขึ้นและรอบนี้ไม่โจมตี ใช้วิชายุทธ์ หรือหายใจเรียกลมปราณ`)],
  };
  function renderIntent() {
    const g = S.game, box = $("#rolls"); box.textContent = "";
    if (!g.fight) return;
    const foe = npcByKey(g.fight.npc), [head, text] = INTENT[g.fight.intent](foe.name);
    box.className = "rolls panel intent i-" + g.fight.intent;
    box.append(el("b", "", head), el("span", "", text));
    if (g.fight.edge) box.append(el("small", "good", tr(`You know how to hurt them: +${g.fight.edge} to hit.`, `你知道怎么对付他：命中 +${g.fight.edge}。`, `เจ้ารู้จุดอ่อนของเขา: +${g.fight.edge} ในการโจมตี`)));
    const h = g.hero;
    $("#artBtn").disabled = h.qi < 1;
  }
  function actionButtons() {
    const h = S.game.hero, mk = (id, title, sub) => { const b = $(id); b.textContent = ""; b.append(el("b", "", title), el("small", "", sub)); };
    mk("#atkBtn", tr("⚔ Strike", "⚔ 出招", "⚔ ฟัน"), tr("plain attack", "普通攻击", "โจมตีธรรมดา"));
    mk("#artBtn", `✨ ${h.off.name}`, tr("costs 1 Qi · lands easier, hits harder", "耗 1 点气 · 更易命中，伤害更高", "ใช้ลมปราณ 1 · โดนง่ายขึ้น แรงขึ้น"));
    mk("#grdBtn", tr("🛡 Guard", "🛡 防守", "🛡 ตั้งรับ"), tr(`+3 defence · regain ${h.int >= 11 ? 2 : 1} Qi`, `防御 +3 · 回复 ${h.int >= 11 ? 2 : 1} 点气`, `ป้องกัน +3 · ฟื้นลมปราณ ${h.int >= 11 ? 2 : 1}`));
    mk("#ctrBtn", tr("↩ Counter", "↩ 反击", "↩ สวนกลับ"), tr("huge against a heavy blow, risky otherwise", "对重击极强，其余情况有风险", "ได้ผลมากกับการฟาดหนัก ที่เหลือเสี่ยง"));
  }
  function enterFight() {
    const g = S.game;
    paintBg("#fightBg", "inn");
    $("#battleLog").textContent = ""; $("#fightDone").hidden = true; $("#fightActions").hidden = false;
    if (!g.fight) { go("game"); return; }
    renderDuel(); actionButtons(); renderIntent();
    g.feed.slice(-3).filter(f => f.kind === "fight").forEach(f => $("#battleLog").prepend(el("div", "bl f-fight", f.text)));
    document.querySelectorAll("#fightActions button").forEach(b => { if (b.id !== "artBtn") b.disabled = false; });
  }
  const diceStr = arr => arr.map(v => DIE[v]).join("");
  function roundCard(R, foeName, h) {
    const card = el("div", "round-card");
    const line = (cls, text, dice) => { const d = el("div", "dline " + cls); d.append(el("span", "", text)); if (dice) d.append(el("small", "dsmall", dice)); card.append(d); };
    const note = side => (side.notes || []).map(([c, v]) => `${pick(S.info.notes[c])}${v ? " +" + v : ""}`).join(" · ");
    if (R.hero) {
      const x = R.hero, what = x.art ? h.off.name : tr("Strike", "出招", "ฟัน");
      line(x.hit ? "good" : "dim", x.hit ? tr(`${what}: ${x.damage} damage to ${foeName}!`, `${what}：对${foeName}造成 ${x.damage} 点伤害！`, `${what}: ${foeName} เสีย ${x.damage} แต้ม!`) : tr(`${what} misses ${foeName}.`, `${what}没有打中${foeName}。`, `${what} พลาด ${foeName}`),
        `${diceStr(x.dice)} ${x.total} vs ${diceStr(x.against.dice)} ${x.against.total}`);
      if (note(x)) line("art", note(x));
    } else if (R.action === "guard") line("dim", tr("You guard and steady your breath.", "你防守并调整气息。", "เจ้าตั้งรับและหายใจเรียกลมปราณ"));
    else if (R.action === "counter") line("dim", tr("You wait for the blow to counter it.", "你等着对方出招，伺机反击。", "เจ้ารอรับการโจมตีเพื่อสวนกลับ"));
    if (R.npc) {
      const x = R.npc;
      line(x.hit ? "bad" : "good", x.hit ? tr(`${foeName} hits you for ${x.damage}.`, `${foeName}击中你，造成 ${x.damage} 点伤害。`, `${foeName} โจมตีเจ้าโดน ${x.damage} แต้ม`) : tr(`You avoid ${foeName}'s attack.`, `你躲开了${foeName}的攻击。`, `เจ้าหลบการโจมตีของ ${foeName}`),
        `${diceStr(x.dice)} ${x.total} vs ${diceStr(x.against.dice)} ${x.against.total}`);
      if (note(x)) line("art", note(x));
    } else if (R.intent === "guard") line("dim", tr(`${foeName} only defends this round.`, `${foeName}这一回合只守不攻。`, `${foeName} ตั้งรับอย่างเดียวในรอบนี้`));
    return card;
  }
  async function doRound(action) {
    if (S.fightBusy) return;
    S.fightBusy = true; document.querySelectorAll("#fightActions button").forEach(b => b.disabled = true);
    let r;
    try { r = await api("/api/fight/round", { action }); }
    catch (e) { toast(errText(e)); S.fightBusy = false; document.querySelectorAll("#fightActions button").forEach(b => b.disabled = false); renderIntent(); return; }
    const prev = S.game.fight, foe = npcByKey(prev.npc), foeName = foe.name, foeMax = prev.hp_max;
    $("#rolls").classList.add("rolling"); await sleep(380);
    setGame(r.game);
    const g = r.game, R = r.round;
    renderDuel(prev.npc, g.fight ? g.fight.hp : 0, foeMax);
    $("#battleLog").prepend(roundCard(R, foeName, g.hero));
    r.events.filter(e => e.type === "feed" && ["win", "gain", "arrival", "storm", "death"].includes(e.item.kind)).forEach(e => $("#battleLog").prepend(el("div", "bl f-" + e.item.kind, e.item.text)));
    $("#rolls").classList.remove("rolling");
    S.fightBusy = false;
    if (g.stage === "dead") { $("#fightActions").hidden = true; $("#rolls").textContent = ""; await sleep(1500); await finish(); return; }
    if (!g.fight) {
      $("#fightActions").hidden = true; $("#rolls").textContent = ""; $("#rolls").className = "rolls panel";
      const done = $("#fightDone"); done.hidden = false; done.textContent = tr("Catch your breath", "喘口气", "หายใจเอาแรง"); return;
    }
    renderIntent();
    document.querySelectorAll("#fightActions button").forEach(b => { if (b.id !== "artBtn") b.disabled = false; });
    $("#artBtn").disabled = g.hero.qi < 1;
  }
  [["#atkBtn", "strike"], ["#artBtn", "art"], ["#grdBtn", "guard"], ["#ctrBtn", "counter"]].forEach(([sel, a]) => $(sel).addEventListener("click", () => doRound(a)));
  $("#fightDone").addEventListener("click", () => go("game"));

  /* ---------- Ray ---------- */
  function rayQuick() {
    return [[tr("How does this work?", "这游戏怎么玩？", "เกมนี้เล่นอย่างไร?"), tr("Explain the rules to me, quickly: dice, stats, and how I win.", "快速给我讲讲规则：骰子、属性，还有怎么才算赢。", "อธิบายกติกาให้ข้าฟังเร็ว ๆ: ลูกเต๋า ค่าสถานะ และข้าจะชนะได้อย่างไร")],
      [tr("Who should I talk to?", "我该找谁谈？", "ควรคุยกับใคร?"), tr("Who should I talk to right now, and how?", "我现在该找谁谈，怎么谈？", "ตอนนี้ข้าควรคุยกับใคร และคุยอย่างไร?")],
      [tr("Should I fight?", "该动手吗？", "ควรสู้ไหม?"), tr("Should I fight anyone? Be honest about my odds.", "我该跟谁动手吗？照实说我的胜算。", "ข้าควรสู้กับใครไหม บอกโอกาสของข้าตามตรง")]];
  }
  function openGm() {
    if (!live()) return;
    if (!$("#gmDrawerImg").firstChild) setPortrait($("#gmDrawerImg"), gm(), true, false);
    $("#gmDrawerName").textContent = gm().name;
    renderGmLog(); $("#gmDrawer").hidden = false; $("#gmBtn").setAttribute("aria-expanded", "true"); $("#gmInput").focus({ preventScroll: true });
    const q = $("#gmQuick"); if (!q.children.length) rayQuick().forEach(([label, say]) => { const b = el("button", "qc", label); b.type = "button"; b.dataset.say = say; q.append(b); });
  }
  function closeGm() { $("#gmDrawer").hidden = true; $("#gmBtn").setAttribute("aria-expanded", "false"); }
  function renderGmLog() {
    const body = $("#gmLog"); body.textContent = "";
    const turns = S.game.gm_turns || [];
    const add = (who, text) => { const e = el("div", "entry " + who); e.append(el("span", "who", who === "hero" ? tr("You", "你", "เจ้า") : gm().name)); const x = el("div", "bi"); fillText(x, text); e.append(x); body.append(e); };
    if (!turns.length) add("npc", tr("Ask me anything: the rules, who to trust, whether a fight is worth it. I won't tell you what people are hiding, but I can point you the right way.", "想问什么都行：规则、该信谁、值不值得动手。别人藏着的事我不会说，但我能给你指个方向。", "ถามได้ทุกอย่าง: กติกา ควรเชื่อใคร คุ้มไหมที่จะสู้ สิ่งที่คนอื่นซ่อนไว้ข้าไม่บอก แต่ชี้ทางให้ได้"));
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
        else if (ev.type === "text") reply.content = (reply.content === "…" ? "" : reply.content) + ev.delta;
        else if (ev.type === "done" && ev.text) reply.content = ev.text;
        renderGmLog();
      });
    } catch (e) { if (reply.content === "…") S.game.gm_turns = S.game.gm_turns.slice(0, -2); note("#gmNote", errText(e), true); renderGmLog(); }
    finally { S.gmBusy = false; $("#gmSend").disabled = false; $("#gmInput").disabled = false; $("#gmInput").focus({ preventScroll: true }); }
  }
  $("#gmForm").addEventListener("submit", e => { e.preventDefault(); const v = $("#gmInput").value.trim(); if (v) { $("#gmInput").value = ""; askGm(v); } });
  $("#gmQuick").addEventListener("click", e => { const b = e.target.closest(".qc"); if (b) askGm(b.dataset.say); });
  $("#gmBtn").addEventListener("click", () => $("#gmDrawer").hidden ? openGm() : closeGm());
  $("#gmClose").addEventListener("click", closeGm);

  /* ---------- how it ends ---------- */
  const ENDING_KEYS = ["escaped", "slain", "arrested", "storm"];
  async function finish() {
    closeGm(); $("#leaveModal").hidden = true;
    go("game");
    showEnding(true);
    if (!S.game.ending) {
      try { setGame((await api("/api/ending", {})).game); } catch (e) { toast(errText(e)); }
    }
    showEnding();
  }
  function endingsFound(add) {
    let have = [];
    try { have = JSON.parse(localStorage.getItem("endings2") || "[]"); } catch { /* private window */ }
    if (add && !have.includes(add)) { have.push(add); try { localStorage.setItem("endings2", JSON.stringify(have)); } catch { /* private window */ } }
    return have;
  }
  function showEnding(waiting) {
    const g = S.game, key = g.ending_key || "slain", e = S.info.endings[key] || { title: "", won: false };
    $("#endTitle").textContent = pick(e.title) || e.title;
    $("#endModal .modal-card").classList.toggle("dead", !g.won);
    $("#endStatus").textContent = g.won ? tr("YOU SURVIVED", "你活下来了", "เจ้ารอดชีวิต") : tr("YOU DIED", "你死了", "เจ้าตายแล้ว");
    const box = $("#endText"); box.textContent = "";
    if (waiting || !g.ending) box.append(el("div", "bi", tr("Ray is telling it…", "Ray 正在讲述……", "Ray กำลังเล่า…"))); else fillText(box, g.ending);
    const st = $("#endStats"); st.textContent = "";
    st.append(el("span", "chip", `❤ ${g.hero.hp}/${g.hero.hp_max}`), el("span", "chip", tr(`Beat ${g.tick}/${g.storm_end}`, `第 ${g.tick}/${g.storm_end} 拍`, `จังหวะ ${g.tick}/${g.storm_end}`)));
    const have = endingsFound(waiting ? null : key), track = $("#endTrack"); track.textContent = "";
    track.append(el("span", "", tr(`Endings ${have.length} / 4`, `结局 ${have.length} / 4`, `ฉากจบ ${have.length} / 4`)));
    ENDING_KEYS.forEach(k => track.append(el("span", "end-chip" + (have.includes(k) ? " on" : ""), have.includes(k) ? pick(S.info.endings[k].title) : "？")));
    $("#endModal").hidden = false; $("#endModal").scrollTop = 0;
  }
  $("#endAgain").addEventListener("click", async () => { $("#endModal").hidden = true; await newNight(); });
  $("#endHome").addEventListener("click", () => { $("#endModal").hidden = true; go("gate"); });

  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    if (!$("#leaveModal").hidden) $("#leaveModal").hidden = true;
    else if (!$("#modal").hidden) $("#modal").hidden = true;
    else if (!$("#gmDrawer").hidden) closeGm();
  });

  /* ---------- boot ---------- */
  async function boot() {
    I18N.apply();
    try {
      const [st, info] = await Promise.all([api("/api/status").catch(() => ({ ai: false })), api("/api/case")]);
      S.aiReady = st.ai; S.info = info;
      await refreshGame();
      if (!S.game) setGame((await api("/api/roll", {})).game);        // a thief is already waiting on the home page
    } catch {
      const s = document.querySelector("#screen-loading .slow"); if (s) s.hidden = false;
      return;
    }
    if (live()) go(S.game.fight ? "fight" : "game");
    else if (over()) { go("game"); showEnding(); }
    else go("gate");
    window.__booted = true;
  }
  boot();
})();
