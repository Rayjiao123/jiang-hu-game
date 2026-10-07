/* The page in three languages: English, 中文 and ไทย. The player picks one on the home page; the page shows only that one.
 *
 *   I18N.tr("English", "中文", "ไทย")   the text for the chosen language (used in code)
 *   data-t="key"                         an element whose text comes from the dictionary below (HTML allowed: it is all ours)
 *   data-t-ph / data-t-aria / data-t-title   the same for a placeholder, an aria-label and a tooltip
 *
 * The server does the same for the story: it sends only the chosen language (the X-Lang header says which). */
(function () {
  "use strict";
  const LANGS = ["en", "zh", "th"];
  const NAMES = { en: "English", zh: "中文", th: "ไทย" };
  const T = {
    ask_ray: { en: "Ask Ray", zh: "问 Ray", th: "ถาม Ray" },
    menu: { en: "Menu", zh: "菜单", th: "เมนู" },
    language: { en: "Language", zh: "语言", th: "ภาษา" },
    loading: { en: "Opening the inn…", zh: "客栈开门中…", th: "กำลังเปิดโรงเตี๊ยม…" },
    slow: { en: "This is taking longer than it should, so something may be wrong.", zh: "加载时间过长，可能出了问题。", th: "ใช้เวลานานกว่าปกติ อาจมีบางอย่างผิดพลาด" },
    reload: { en: "Reload", zh: "刷新", th: "โหลดใหม่" },
    kicker_tag: { en: "Dark wuxia", zh: "黑色武侠", th: "ยุทธภพสายมืด" },
    kicker: { en: "a story game", zh: "故事游戏", th: "เกมเล่าเรื่อง" },
    gate_sub: { en: "Helpless in the Jianghu", zh: "", th: "คนในยุทธภพ ไม่อาจเป็นตัวของตัวเอง" },
    setting: {
      en: "A sandstorm traps you in the Black Sand Inn, a desert inn that kills its guests. The doors are barred. Dawn is coming.",
      zh: "沙暴把你困在黑沙客栈，一家杀客人的沙漠客栈。大门已闩，天快亮了。",
      th: "พายุทรายขังเจ้าไว้ในโรงเตี๊ยมทรายดำ โรงเตี๊ยมกลางทะเลทรายที่ฆ่าแขกของตัวเอง ประตูถูกลงกลอน และฟ้ากำลังจะสาง",
    },
    you: { en: "you", zh: "你", th: "คุณ" },
    hero_goal: {
      en: "A courier's daughter with a secret letter. <strong>Goal: get out alive before dawn</strong>, by the secret tunnel or by killing the keeper for her key.",
      zh: "带着密信的镖师之女。<strong>目标：天亮前活着出去</strong>，走暗道，或杀掉掌柜夺钥匙。",
      th: "ธิดาผู้คุ้มภัยที่แบกจดหมายลับ <strong>เป้าหมาย: รอดออกไปให้ได้ก่อนฟ้าสาง</strong> ด้วยอุโมงค์ลับ หรือฆ่าเจ้าของโรงเตี๊ยมเพื่อชิงกุญแจ",
    },
    gm_tag: { en: "game master", zh: "主持", th: "ผู้ดำเนินเกม" },
    gm_goal: { en: "Narrates the night and answers when you're stuck.", zh: "叙述这一夜，你卡住时给你提示。", th: "เล่าเรื่องราวของค่ำคืนนี้ และตอบเมื่อคุณติดขัด" },
    enter: { en: "Enter the inn", zh: "走进客栈", th: "เข้าไปในโรงเตี๊ยม" },
    enter_back: { en: "Back to the inn", zh: "回到客栈", th: "กลับเข้าโรงเตี๊ยม" },
    warn: { en: "A wrong word or a wrong move, and you die.", zh: "一句错话，一步错棋，就是死。", th: "พูดผิดคำเดียวหรือเดินผิดก้าวเดียว คุณก็ตาย" },
    privacy: { en: "Chats are saved to run and improve the game.", zh: "对话会被保存，用于运行并改进游戏。", th: "บทสนทนาจะถูกบันทึกเพื่อให้เกมทำงานและปรับปรุงเกม" },
    home: { en: "Home", zh: "首页", th: "หน้าแรก" },
    home_arrow: { en: "← Home", zh: "← 首页", th: "← หน้าแรก" },
    scene_title: { en: "The Black Sand Inn", zh: "黑沙客栈", th: "โรงเตี๊ยมทรายดำ" },
    scene_sub: { en: "Who do you talk to?", zh: "找谁说话？", th: "จะคุยกับใคร?" },
    ray_tap: { en: "Ray says · tap to ask", zh: "Ray 说 · 点我提问", th: "Ray เล่า · แตะเพื่อถาม" },
    move: { en: "Make your move", zh: "动手", th: "ลงมือ" },
    back_inn: { en: "Back to the inn", zh: "回到大堂", th: "กลับไปที่โถง" },
    back: { en: "Back", zh: "返回", th: "กลับ" },
    say_ph: { en: "Speak as Qinghe…", zh: "以青禾的身份说话…", th: "พูดในฐานะชิงเหอ…" },
    say_label: { en: "Say something as Qinghe", zh: "以青禾的身份说话", th: "พูดอะไรสักอย่างในฐานะชิงเหอ" },
    say: { en: "Say", zh: "说", th: "พูด" },
    stop: { en: "Stop", zh: "停", th: "หยุด" },
    ray_notes: { en: "Ray's notes", zh: "Ray 的笔记", th: "บันทึกของ Ray" },
    game_master: { en: "Game master", zh: "主持人", th: "ผู้ดำเนินเกม" },
    ray_ph: { en: "Ask Ray anything…", zh: "问问 Ray…", th: "ถาม Ray อะไรก็ได้…" },
    ask: { en: "Ask", zh: "问", th: "ถาม" },
    close: { en: "Close", zh: "关闭", th: "ปิด" },
    push_door: { en: "Push the door", zh: "推门而入", th: "ผลักประตูเข้าไป" },
    ray_says: { en: "Ray, your game master, says", zh: "你的主持人 Ray 说", th: "Ray ผู้ดำเนินเกมของคุณ กล่าวว่า" },
    inn_name: { en: "The Black Sand Inn", zh: "黑沙客栈", th: "โรงเตี๊ยมทรายดำ" },
    move_title: { en: "Make your move", zh: "动手", th: "ลงมือ" },
    move_lead: {
      en: "There are two ways out of this inn, and only two. Choose one only if you have learned what it needs (Ray's notes show what you know). This is your last move: press the button twice to confirm. If you are not ready, you die.",
      zh: "这家客栈只有两条出路。只有当你弄清了它需要的东西，才选它（Ray 的笔记里有你已知道的）。这是你最后一步：连点两次确认。没准备好，你就会死。",
      th: "โรงเตี๊ยมนี้มีทางออกเพียงสองทาง และมีแค่สองทางเท่านั้น เลือกทางใดทางหนึ่งก็ต่อเมื่อคุณรู้แล้วว่ามันต้องใช้อะไร (บันทึกของ Ray บอกสิ่งที่คุณรู้) นี่คือก้าวสุดท้าย กดปุ่มสองครั้งเพื่อยืนยัน ถ้ายังไม่พร้อม คุณจะตาย",
    },
    both: { en: "Both", zh: "全部", th: "ทั้งหมด" },
    play_again: { en: "Play again", zh: "再来一夜", th: "เล่นอีกรอบ" },
    stay: { en: "Stay", zh: "留在这里", th: "อยู่ต่อ" },
    start_over: { en: "Start the night over", zh: "重新开始", th: "เริ่มคืนนี้ใหม่" },
    start_over_note: {
      en: "This ends the current night and its conversations, and you begin again at dusk.",
      zh: "这会结束当前的夜晚和所有对话，你将从黄昏重新开始。",
      th: "การทำเช่นนี้จะจบคืนนี้และบทสนทนาทั้งหมด แล้วคุณจะเริ่มใหม่ตั้งแต่ย่ำค่ำ",
    },
    yes_start_over: { en: "Yes, start over", zh: "是，重新开始", th: "ใช่ เริ่มใหม่" },
    cancel: { en: "Cancel", zh: "取消", th: "ยกเลิก" },
  };

  const KEY = "lang";
  const guess = () => {
    try { const s = localStorage.getItem(KEY); if (LANGS.includes(s)) return s; } catch { /* private window */ }
    const n = (navigator.language || "en").toLowerCase();
    return n.startsWith("zh") ? "zh" : n.startsWith("th") ? "th" : "en";
  };
  let lang = guess();
  const chosen = () => { try { return LANGS.includes(localStorage.getItem(KEY)); } catch { return false; } };

  const pick = o => (o && (o[lang] ?? o.en)) ?? "";
  const tr = (en, zh, th) => ({ en, zh, th })[lang] ?? en;
  const t = key => (T[key] ? pick(T[key]) : key);

  function apply(root = document) {
    root.querySelectorAll("[data-t]").forEach(e => { e.innerHTML = t(e.dataset.t); if (e.dataset.t === "gate_sub") e.hidden = !e.innerHTML; });
    root.querySelectorAll("[data-t-ph]").forEach(e => { e.placeholder = t(e.dataset.tPh); });
    root.querySelectorAll("[data-t-aria]").forEach(e => { e.setAttribute("aria-label", t(e.dataset.tAria)); });
    root.querySelectorAll("[data-t-title]").forEach(e => { e.title = t(e.dataset.tTitle); });
    document.documentElement.lang = lang === "zh" ? "zh-Hans" : lang;
    document.querySelectorAll(".lang-pick button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  }

  function set(next) {
    if (!LANGS.includes(next)) return;
    lang = next;
    try { localStorage.setItem(KEY, next); } catch { /* private window */ }
    apply();
  }

  window.I18N = { LANGS, NAMES, T, get lang() { return lang; }, set, apply, t, tr, pick, chosen };
})();
