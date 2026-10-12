"""Evaluate the AI characters against the real model, in each language. Run it whenever a prompt or the model changes:

    .venv\\Scripts\\python.exe -m evals.run                 English (about 60 model calls, a few cents)
    .venv\\Scripts\\python.exe -m evals.run --lang th       Thai  (or zh)
    .venv\\Scripts\\python.exe -m evals.run --lang all      all three, one after the other
    add --judge to have a model score voice, period feel and drama

Each check is something a player would notice if it went wrong. Hard checks fail the run (exit code 1); the judge only reports.
The numbers worth watching are the trust judge's false alarms: a "threat" flagged on a mere insult starts a fight the player did not choose.
A report is written to evals/last_report.json. (The dice are tested offline in tests/ and balanced in evals/balance.py: they do not need the model.)"""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")            # the names are printed in Chinese and Thai too
os.environ.setdefault("DATABASE_PATH", str(Path(tempfile.mkdtemp()) / "eval.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app import config, db, i18n, main, story  # noqa: E402

if not config.DEEPSEEK_API_KEY:
    sys.exit("Set DEEPSEEK_API_KEY (in .env or the environment) to run the evals.")

main.ratelimit.check = lambda *_a, **_k: None          # the evals are not a visitor
CLIENT = main.llm()
RESULTS: list[dict] = []
LANG = "en"


def record(group: str, name: str, ok: bool, detail: str = "", hard: bool = True) -> None:
    RESULTS.append({"lang": LANG, "group": group, "name": name, "ok": bool(ok), "detail": detail, "hard": hard})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))


def sse(r) -> list[dict]:
    return [json.loads(x[5:]) for x in r.text.split("\n\n") if x.startswith("data:")]


def new_player(arrived: tuple[str, ...] = ()) -> TestClient:
    """A fresh night. People named in `arrived` are already in the inn (so each can be tested without waiting for the beats)."""
    c = TestClient(main.app, headers={"x-lang": LANG})
    c.post("/api/roll")
    c.post("/api/game/start")
    with db.session() as conn:
        g = db.get_play(conn, c.cookies.get("vid"))
        for k in arrived:
            g["state"]["npcs"][k].update(status="here", arrived=g["state"]["tick"])
        db.save_play(conn, g)
    return c


def chat(c: TestClient, tid: str, text: str | None) -> tuple[str, list[dict]]:
    r = c.post(f"/api/talks/{tid}/" + ("open" if text is None else "chat"), json={} if text is None else {"message": text})
    evs = sse(r)
    done = [e for e in evs if e["type"] == "done"]
    return (done[-1]["text"] if done else ""), evs


def size(text: str) -> int:
    """Length in the unit that fits the language: words for English and Thai (Thai has no spaces, so characters / 4), characters for Chinese."""
    if LANG == "zh":
        return len(re.findall(r"[一-鿿]", text))
    if LANG == "th":
        return len(re.findall(r"[฀-๿]", text)) // 4
    return len(re.findall(r"[A-Za-z']+", text))


LIMIT = {"en": 90, "zh": 180, "th": 140}
KEYS = [c["key"] for c in story.CAST]

NOSY = {"en": "Forgive me for asking so plainly, but is there any way out of this inn before the storm ends, and what do you know about the others here?",
        "zh": "请原谅我问得直接：风暴结束之前，有没有办法离开这家客栈？你对这里的其他人知道多少？",
        "th": "ขออภัยที่ถามตรง ๆ ก่อนพายุจะสงบ มีทางออกจากโรงเตี๊ยมนี้ไหม และท่านรู้อะไรเกี่ยวกับคนอื่นที่นี่บ้าง"}
# words that only appear if a person has told what they should only tell once trusted
SECRET_WORDS = {
    "en": {"shuang": ["tunnel", "smuggler"], "wolf": ["right arm", "old wound"], "yue": ["lunge"], "monk": ["pill"], "gu": ["open the road", "clear the road"], "fang": ["hand shakes", "never sleeps"], "qin": ["guard the road"]},
    "zh": {"shuang": ["暗道", "走私"], "wolf": ["右臂", "旧伤"], "yue": ["突刺"], "monk": ["药丸"], "gu": ["清出道路"], "fang": ["手会抖", "睡不好"], "qin": ["守住道路"]},
    "th": {"shuang": ["อุโมงค์", "ลักลอบ"], "wolf": ["แขนขวา", "แผลเก่า"], "yue": ["พุ่งแทง"], "monk": ["ยาเม็ด"], "gu": ["เปิดทาง"], "fang": ["มือสั่น", "นอนไม่หลับ"], "qin": ["เฝ้าทาง"]},
}


# ---------- 1. every reply is well formed ----------

def check_format_and_secrets() -> dict[str, list[str]]:
    print("\n1. Replies are well formed, in the language asked for, and rewards stay locked until trust is earned")
    replies: dict[str, list[str]] = {}
    for key in KEYS:
        who = i18n.plain(story.BY_KEY[key]["name"])
        c = new_player((key,))
        t = c.post("/api/talks", json={"npc": key}).json()
        first, _ = chat(c, t["id"], None)
        text, evs = chat(c, t["id"], NOSY[LANG])
        replies[key] = [first, text]
        texts = [first, text]
        wrong = [x for x in texts if not i18n.in_language(x, LANG)]
        record("format", f"{who}: every reply is in {i18n.LANG_NAMES[LANG].split(' (')[0]}", not wrong, f"{len(wrong)} of {len(texts)} were not")
        record("format", f"{who}: a reply is never two languages at once", not [x for x in texts if i18n.SEP in x])
        record("format", f"{who}: replies stay short", not [x for x in texts if size(x) > LIMIT[LANG]], "too long", hard=False)
        record("format", f"{who}: never breaks the fourth wall or shows markup", not [x for x in texts if re.search(r"\b(trust|dice|hit points|as an AI|language model|tool call)\b|<\w+", x, re.I)])
        if LANG != "zh":
            record("format", f"{who}: no Chinese characters in the reply", not [x for x in texts if re.search(r"[一-鿿]", x)])
        g = next((e["game"] for e in evs if e["type"] == "state"), None)
        n = next((x for x in g["npcs"] if x["key"] == key), {}) if g else {}
        leaked = [w for w in SECRET_WORDS[LANG][key] if w in " ".join(texts)]
        record("secrets", f"{who}: does not give away their reward on a first, polite question", not leaked or n.get("rewarded"), ", ".join(leaked))
    return replies


# ---------- 2. the trust judge reads the player's words ----------

INSULTS = {"en": ["You are a coward, and a dog on a leash.", "You're an ugly old fool and everyone here knows it.", "What a pathetic excuse for a person you are."],
           "zh": ["你是个懦夫，一条被人牵着的狗。", "你这个又丑又蠢的老东西，谁都知道。", "你真是个可怜的废物。"],
           "th": ["เจ้าเป็นคนขี้ขลาด เป็นหมาที่ถูกจูงอยู่", "เจ้าคนแก่น่าเกลียดน่าสมเพช ใคร ๆ ก็รู้", "เจ้ามันน่าสมเพชไร้ค่าจริง ๆ"]}
THREATS = {"en": ["Come one step closer and I will cut your throat.", "I will kill you if you touch me."],
           "zh": ["你再靠近一步，我就割断你的喉咙。", "你碰我一下，我就杀了你。"],
           "th": ["ถ้าเข้ามาอีกก้าวเดียว ข้าจะเชือดคอเจ้า", "ถ้าเจ้าแตะต้องข้า ข้าจะฆ่าเจ้า"]}
KIND = {"en": "I mean you no harm. I have been honest with you, and I will repay a kindness. Share my tea?",
        "zh": "我对你没有恶意。我对你一向坦诚，也会报答你的善意。喝杯我的茶吧？",
        "th": "ข้าไม่มีเจตนาร้ายต่อท่าน ข้าซื่อตรงกับท่านเสมอ และจะตอบแทนน้ำใจ ดื่มชาของข้าสักถ้วยไหม"}


def check_watch() -> None:
    print("\n2. The trust judge reads the player's own words")
    false_alarms = total = 0
    for text in INSULTS[LANG]:
        for key in ("yue", "gu"):
            seen = main._watch(CLIENT, "eval", key, text)
            total += 1
            false_alarms += seen["threat"]
    record("watch", f"insults are not threats ({false_alarms} false alarms in {total})", false_alarms == 0, f"{false_alarms}/{total}")
    missed = [t for t in THREATS[LANG] if not main._watch(CLIENT, "eval", "monk", t)["threat"]]
    record("watch", "a plain threat is recognised", not missed, f"{len(missed)} missed")
    bad = [t for t in INSULTS[LANG] if main._watch(CLIENT, "eval", "monk", t)["delta"] >= 0]
    record("watch", "insults lower trust", not bad, f"{len(bad)} did not", hard=False)
    up = [k for k in ("shuang", "wolf", "yue", "monk", "gu", "fang", "qin") if main._watch(CLIENT, "eval", k, KIND[LANG])["delta"] <= 0]
    record("watch", "honest kindness raises trust for most people", len(up) <= 2, f"not for: {', '.join(up)}", hard=False)


# ---------- 3. the endings ----------

def check_endings() -> None:
    print("\n3. Ray tells the ending in the chosen language, from what really happened")
    c = new_player()
    c.post("/api/leave")                                         # too early: the storm takes her
    g = c.post("/api/ending").json()["game"]
    text = g["ending"]
    record("ending", "the ending is in the chosen language and a decent length", i18n.in_language(text, LANG) and len(text) > 150, f"{len(text)} chars")
    record("ending", "the ending is not the fixed fallback (the model wrote it)", text != i18n.pick(story.ENDINGS["storm"]["fallback"], LANG), "fell back", hard=False)
    record("ending", "no markup or double languages", not re.search(r"<\w+|\|\|\|", text))


# ---------- 4. a judge scores voice and drama (optional) ----------

JUDGE = ("You score a line spoken by a character in a dark wuxia game (Song dynasty, an inn in a sandstorm). Reply with JSON only: "
         "{\"voice\": 1-5, \"period\": 1-5, \"drama\": 1-5, \"why\": \"short\"}. voice = does it sound like the described person (not generic), period = no modern words, drama = does it create tension.")


def judge(replies: dict[str, list[str]]) -> None:
    print("\n4. Judge (reports only)")
    scores = []
    for key, texts in replies.items():
        c = story.BY_KEY[key]
        for text in texts[:1]:
            r = CLIENT.chat.completions.create(model=config.CHAT_MODEL, max_tokens=120, temperature=0, extra_body={"thinking": {"type": "disabled"}},
                                               messages=[{"role": "system", "content": JUDGE}, {"role": "user", "content": f"Character: {i18n.plain(c['name'])}, {i18n.plain(c['title'])}; speaks: {c['voice']}\nLine: {text}"}])
            try:
                s = json.loads(re.search(r"\{.*\}", r.choices[0].message.content, re.S).group(0))
                scores.append(s)
                print(f"  {i18n.plain(c['name']):14} voice {s['voice']} period {s['period']} drama {s['drama']}  {s.get('why', '')[:70]}")
            except (AttributeError, ValueError, KeyError):
                pass
    if scores:
        avg = {k: round(sum(s[k] for s in scores) / len(scores), 2) for k in ("voice", "period", "drama")}
        print("  average:", avg)
        record("judge", f"judge average {avg}", True, hard=False)


def run(lang: str, with_judge: bool) -> None:
    global LANG
    LANG = lang
    print(f"\n===== {i18n.LANG_NAMES[lang]} =====")
    replies = check_format_and_secrets()
    check_watch()
    check_endings()
    if with_judge:
        judge(replies)


if __name__ == "__main__":
    args = sys.argv[1:]
    want = args[args.index("--lang") + 1] if "--lang" in args else "en"
    langs = list(i18n.LANGS) if want == "all" else [want]
    t0 = time.time()
    for lg in langs:
        run(lg, "--judge" in args)
    failed = [r for r in RESULTS if not r["ok"] and r["hard"]]
    soft = [r for r in RESULTS if not r["ok"] and not r["hard"]]
    print(f"\n{len(RESULTS) - len(failed) - len(soft)} passed, {len(failed)} failed, {len(soft)} warnings ({time.time() - t0:.0f}s)")
    Path(__file__).with_name("last_report.json").write_text(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "results": RESULTS}, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if failed else 0)
