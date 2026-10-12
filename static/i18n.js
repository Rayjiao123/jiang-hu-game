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
    kicker: { en: "a 5-minute survival game", zh: "五分钟生存游戏", th: "เกมเอาชีวิตรอด 5 นาที" },
    h_scene: { en: "The scene", zh: "场景", th: "ฉาก" },
    h_goal: { en: "Your goal", zh: "你的目标", th: "เป้าหมายของเจ้า" },
    h_thief: { en: "Your thief: roll the dice", zh: "你的女贼：掷骰子", th: "โจรของเจ้า: ทอยลูกเต๋า" },
    reroll: { en: "Roll again", zh: "再掷一次", th: "ทอยใหม่" },
    gm_tag: { en: "game master", zh: "主持", th: "ผู้ดำเนินเกม" },
    gm_goal: { en: "I'm Ray. I narrate the night, explain the rules, and answer when you're stuck. I'm on nobody's side.", zh: "我是 Ray。我讲述这一夜，解释规则，你卡住时给你提示。我不偏向任何人。", th: "ข้าคือ Ray ข้าเล่าเรื่องค่ำคืนนี้ อธิบายกติกา และตอบเมื่อเจ้าติดขัด ข้าไม่เข้าข้างใคร" },
    enter: { en: "Enter the inn", zh: "走进客栈", th: "เข้าไปในโรงเตี๊ยม" },
    enter_back: { en: "Back to the inn", zh: "回到客栈", th: "กลับเข้าโรงเตี๊ยม" },
    warn: { en: "Most thieves don't see the morning.", zh: "多数的贼，都看不到天亮。", th: "โจรส่วนใหญ่ไม่ได้เห็นรุ่งเช้า" },
    privacy: { en: "Chats are saved to run and improve the game.", zh: "对话会被保存，用于运行并改进游戏。", th: "บทสนทนาจะถูกบันทึกเพื่อให้เกมทำงานและปรับปรุงเกม" },
    home: { en: "Home", zh: "首页", th: "หน้าแรก" },
    back_inn: { en: "Back to the inn", zh: "回到大堂", th: "กลับไปที่โถง" },
    say_ph: { en: "Speak as Yan Qi…", zh: "以燕七的身份说话…", th: "พูดในฐานะเยี่ยนชี…" },
    say_label: { en: "Say something as Yan Qi", zh: "以燕七的身份说话", th: "พูดอะไรสักอย่างในฐานะเยี่ยนชี" },
    say: { en: "Say", zh: "说", th: "พูด" },
    stop: { en: "Stop", zh: "停", th: "หยุด" },
    fight: { en: "Fight", zh: "动手", th: "สู้" },
    game_master: { en: "Game master", zh: "主持人", th: "ผู้ดำเนินเกม" },
    ray_ph: { en: "Ask Ray anything…", zh: "问问 Ray…", th: "ถาม Ray อะไรก็ได้…" },
    ask: { en: "Ask", zh: "问", th: "ถาม" },
    close: { en: "Close", zh: "关闭", th: "ปิด" },
    push_door: { en: "Push the door", zh: "推门而入", th: "ผลักประตูเข้าไป" },
    ray_says: { en: "Ray, your game master, says", zh: "你的主持人 Ray 说", th: "Ray ผู้ดำเนินเกมของคุณ กล่าวว่า" },
    inn_name: { en: "The Black Sand Inn", zh: "黑沙客栈", th: "โรงเตี๊ยมทรายดำ" },
    play_again: { en: "Play again", zh: "再来一夜", th: "เล่นอีกรอบ" },
    leave_title: { en: "Go out into the storm?", zh: "走进沙暴？", th: "จะออกไปในพายุหรือ?" },
    leave_warn: { en: "The storm has not passed. If you walk out now, the desert will kill you.", zh: "沙暴还没过去。你现在走出去，大漠会要你的命。", th: "พายุยังไม่ผ่านไป ถ้าเจ้าเดินออกไปตอนนี้ ทะเลทรายจะเอาชีวิตเจ้า" },
    leave_yes: { en: "Go out anyway", zh: "还是走出去", th: "ออกไปอยู่ดี" },
    cancel: { en: "Cancel", zh: "取消", th: "ยกเลิก" },
    start_over: { en: "Start over", zh: "重新开始", th: "เริ่มใหม่" },
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
    root.querySelectorAll("[data-t]").forEach(e => { e.innerHTML = t(e.dataset.t); if (false) e.hidden = !e.innerHTML; });
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
