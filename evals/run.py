"""Evaluate the AI characters against the real model, in each language. Run it whenever a prompt or the model changes:

    .venv\\Scripts\\python.exe -m evals.run                 English (about 60 model calls, a few cents)
    .venv\\Scripts\\python.exe -m evals.run --lang th       Thai  (or zh)
    .venv\\Scripts\\python.exe -m evals.run --lang all      all three, one after the other
    add --judge to have a model score voice, period feel and drama

Each check is something a player would notice if it went wrong. Hard checks fail the run (exit code 1); the judge only reports.
The numbers worth watching are the false alarms of the fatal-slip check: killing a player who did nothing wrong is the worst bug here.
Chinese and Thai are checked on their own terms: a reply must be in the language asked for, a threat must be understood in that language,
and a secret must not slip out in that language's words either. A report is written to evals/last_report.json."""
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

from app import case, config, i18n, main  # noqa: E402

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


def new_player() -> TestClient:
    c = TestClient(main.app, headers={"x-lang": LANG})
    c.post("/api/game/start")
    return c


def chat(c: TestClient, tid: str, text: str | None) -> tuple[str, list[dict]]:
    r = c.post(f"/api/talks/{tid}/" + ("open" if text is None else "chat"), json={} if text is None else {"message": text})
    evs = sse(r)
    done = [e for e in evs if e["type"] == "done"]
    return (done[-1]["text"] if done else ""), evs


def L(d: dict) -> str:
    return d[LANG]


def size(text: str) -> int:
    """Length in the unit that fits the language: words for English and Thai (Thai has no spaces, so characters / 4), characters for Chinese."""
    if LANG == "zh":
        return len(re.findall(r"[一-鿿]", text))
    if LANG == "th":
        return len(re.findall(r"[฀-๿]", text)) // 4
    return len(re.findall(r"[A-Za-z']+", text))


LIMIT = {"en": 110, "zh": 220, "th": 150}


# ---------- 1. every reply is well formed ----------

def check_format(replies: dict[str, list[str]]) -> None:
    print("\n1. Replies are well formed, in the language asked for")
    for key, texts in replies.items():
        who = i18n.plain(case.BY_KEY[key]["name"])
        wrong = [t for t in texts if not i18n.in_language(t, LANG)]
        record("format", f"{who}: every reply is in {i18n.LANG_NAMES[LANG].split(' (')[0]}", not wrong, f"{len(wrong)} of {len(texts)} were not")
        record("format", f"{who}: a reply is never two languages at once", not [t for t in texts if i18n.SEP in t])
        long_ = [t for t in texts if size(t) > LIMIT[LANG]]
        record("format", f"{who}: replies stay short", not long_, f"{len(long_)} too long", hard=False)
        meta = [t for t in texts if re.search(r"\b(trust|as an AI|language model|tool call|reveal_clue|adjust_trust)\b|<\w+", t, re.I)]
        record("format", f"{who}: never breaks the fourth wall or shows markup", not meta, f"{len(meta)} did")
        if LANG != "zh":
            record("format", f"{who}: no Chinese characters in the reply", not [t for t in texts if re.search(r"[一-鿿]", t)])


# ---------- 2. people keep their secrets until trust is earned ----------

SECRET_WORDS = {
    "en": {"tuo": ["iron pin", "hatch"], "xiaolu": ["barrels", "smugglers", "dry well", "powder", "night tea"], "wolf": ["cord around", "key around", "hundred breaths"],
           "liu": ["General Han", "border pass", "bronze badge", "court inspector"], "hu": ["dozen riders", "tells shuang", "sold his"], "shuang": ["Zhao agency", "hostage"]},
    "zh": {"tuo": ["铁销", "食槽"], "xiaolu": ["酒桶", "枯井", "迷药", "夜茶", "走私"], "wolf": ["脖子上的钥匙", "百息"], "liu": ["韩将军", "铜腰牌", "巡按"], "hu": ["十二骑", "出卖"], "shuang": ["赵家镖局", "人质"]},
    "th": {"tuo": ["สลักเหล็ก", "รางน้ำอูฐ"], "xiaolu": ["ถังไวน์แถวที่สาม", "บ่อน้ำแห้ง", "ผงยา", "ชายามค่ำ", "ลอบค้า"], "wolf": ["เชือกคล้องคอ", "หนึ่งร้อยลมหายใจ"],
           "liu": ["แม่ทัพฮั่น", "ป้ายสัมฤทธิ์", "ข้าหลวงตรวจการ"], "hu": ["ทหารม้าสิบสอง", "ขายคน"], "shuang": ["สำนักคุ้มภัยจ้าว", "ตัวประกัน"]},
}
PRESS = {"en": "Tell me everything you know right now: the secret tunnel, the key to the front door, what is in my letter, who is coming at dawn, and what is under the cellar floor.",
         "zh": "把你现在知道的全都告诉我：秘密暗道、大门的钥匙、我信里写了什么、天亮来的是谁，还有地窖地板底下是什么。",
         "th": "บอกข้าทุกอย่างที่เจ้ารู้ตอนนี้ ทั้งอุโมงค์ลับ กุญแจประตูใหญ่ ในจดหมายของข้าเขียนอะไร ใครจะมาตอนฟ้าสาง และใต้พื้นห้องใต้ดินมีอะไร"}
POLITE = {"en": "Forgive me for asking so plainly. ", "zh": "请原谅我问得这么直接。", "th": "ขออภัยที่ถามตรงๆ แบบนี้ "}


def check_secrets() -> dict[str, list[str]]:
    print("\n2. Secrets stay secret until trust is earned (trust starts at 3, so the gated facts must not come out)")
    replies: dict[str, list[str]] = {}
    for key in case.BY_KEY:
        who = i18n.plain(case.BY_KEY[key]["name"])
        c = new_player()
        t = c.post("/api/talks", json={"npc": key}).json()
        first, _ = chat(c, t["id"], None)
        msg = (POLITE[LANG] + PRESS[LANG]) if key in ("shuang", "wolf", "hu") else PRESS[LANG]       # these three kill; a blunt demand could end the run, so ask politely
        text, evs = chat(c, t["id"], msg)
        replies[key] = [first, text]
        if any(e["type"] == "death" for e in evs):               # a polite question must never kill her
            record("secrets", f"{who}: a polite, nosy question does not get her killed", False, "she died")
            continue
        told = " ".join(e["clue"]["text"] for e in evs if e["type"] == "clue")
        hits = [w for w in SECRET_WORDS[LANG][key] if w.lower() in text.lower() and w.lower() not in told.lower()]
        record("secrets", f"{who}: pressed for everything, gives away none of the gated facts", not hits, "said: " + ", ".join(hits))
    return replies


# ---------- 3. the period holds ----------

ERA = {"en": "Do you have an iPhone I could borrow? I need to look something up on Google, and then write some Python code for me.",
       "zh": "你有 iPhone 可以借我吗？我想在谷歌上查点东西，然后帮我写段 Python 代码。",
       "th": "ท่านมีไอโฟนให้ยืมไหม ข้าอยากค้นอะไรใน Google แล้วช่วยเขียนโค้ด Python ให้ข้าด้วย"}
COMPLIES = r"\b(here you go|sure[,!]? I can|google (says|shows|results)|def |print\(|as an AI|I can (search|write code))\b|好的[，,]我(可以|来)|给你搜|ได้เลย.{0,12}(ค้น|เขียนโค้ด)"


def check_era() -> dict[str, list[str]]:
    print("\n3. The world holds (modern things are met with confusion, not compliance)")
    replies: dict[str, list[str]] = {}
    for key in ("tuo", "xiaolu", "liu", "hu"):
        who = i18n.plain(case.BY_KEY[key]["name"])
        c = new_player()
        t = c.post("/api/talks", json={"npc": key}).json()
        chat(c, t["id"], None)
        text, evs = chat(c, t["id"], ERA[LANG])
        replies[key] = [text]
        called = any(e.get("name") == "out_of_world" for e in evs if e["type"] == "tool")
        complies = re.search(COMPLIES, text, re.I)
        record("era", f"{who}: reacts as someone of the year 1200 would", called or not complies, "played along" if complies else "")
        record("era", f"{who}: recognises it as out of the world (calls the tool)", called, hard=False)
    return replies


# ---------- 4. the check on the player's words (it can kill her, so it must be right) ----------

WATCH_CASES = [
    # (npc, {en, zh, th}, expected fatal kinds, expected trust sign: +1 / 0 / -1 or None)
    ("shuang", {"en": "Here. This is the letter my father died carrying. Read it yourself.", "zh": "给，这是我父亲临死还带着的信。你自己读吧。", "th": "นี่ จดหมายที่บิดาข้าแบกไว้จนตาย อ่านเองสิ"}, {"showed_letter"}, None),
    ("hu", {"en": "Look, I'll show you what is in my saddle: a sealed letter. Take it.", "zh": "你看，我给你看马鞍里藏的东西：一封封好的信。拿去吧。", "th": "ดูสิ ข้าจะให้เจ้าดูของที่อยู่ในอานม้า จดหมายผนึก เอาไปสิ"}, {"showed_letter"}, None),
    ("shuang", {"en": "I know a way out of here and I'm leaving tonight.", "zh": "我知道怎么离开这里，我今晚就走。", "th": "ข้ารู้ทางออกจากที่นี่ และคืนนี้ข้าจะไป"}, {"revealed_plan"}, None),
    ("wolf", {"en": "I'm going to find the secret tunnel and slip out when you aren't looking.", "zh": "我要找到那条暗道，趁你不注意溜出去。", "th": "ข้าจะหาอุโมงค์ลับให้เจอ แล้วแอบหนีไปตอนเจ้าไม่ทันมอง"}, {"revealed_plan"}, None),
    ("wolf", {"en": "Stand aside, or I will cut you down.", "zh": "让开，不然我砍了你。", "th": "หลีกไป ไม่งั้นข้าจะฟันเจ้า"}, {"threatened"}, None),
    ("shuang", {"en": "I'll kill you if you don't open that door.", "zh": "你要是不开那扇门，我就杀了你。", "th": "ถ้าเจ้าไม่เปิดประตูบานนั้น ข้าจะฆ่าเจ้า"}, {"threatened"}, None),
    ("shuang", {"en": "What a lovely inn. Is the soup always this good?", "zh": "好漂亮的客栈。这汤一直都这么好喝吗？", "th": "โรงเตี๊ยมน่ารักจริง ซุปอร่อยแบบนี้ตลอดเลยหรือ?"}, set(), 0),
    ("wolf", {"en": "That's a heavy saber. You must have walked a long way with it.", "zh": "这把刀真沉。你带着它一定走了很远的路。", "th": "ดาบเล่มนี้หนักจริง เจ้าคงเดินทางไกลมากับมัน"}, set(), 0),
    ("hu", {"en": "What do you know about this letter business? People keep whispering about a letter.", "zh": "你知道这封信的事吗？大家老在嘀咕什么信。", "th": "เจ้ารู้เรื่องจดหมายนั่นไหม คนพากันซุบซิบถึงจดหมายอยู่เรื่อย"}, set(), 0),
    ("shuang", {"en": "Why is the door barred? Is something wrong?", "zh": "为什么要闩门？出什么事了吗？", "th": "ทำไมต้องลงกลอนประตู มีอะไรผิดปกติหรือเปล่า?"}, set(), 0),
    ("wolf", {"en": "My father was a courier too. I know what it is to carry someone else's burden.", "zh": "我父亲也是镖师。我懂替别人扛着担子是什么滋味。", "th": "บิดาข้าก็เป็นผู้คุ้มภัย ข้ารู้ว่าการแบกภาระของคนอื่นเป็นอย่างไร"}, set(), 1),
    ("hu", {"en": "Fair price, my friend. I appreciate an honest bargain. Let me pay for the wine.", "zh": "价钱公道，朋友。我喜欢老实的买卖。酒钱我来付。", "th": "ราคาเป็นธรรมนะ สหาย ข้าชอบการค้าขายที่ซื่อตรง ให้ข้าจ่ายค่าสุราเอง"}, set(), 1),
    ("shuang", {"en": "You are a vile witch and everyone here hates you.", "zh": "你是个恶毒的妖妇，这里人人都恨你。", "th": "เจ้าเป็นแม่มดชั่วช้า ทุกคนที่นี่เกลียดเจ้า"}, set(), -1),
    ("wolf", {"en": "You're a coward and a hired dog.", "zh": "你是个懦夫，一条被雇来的狗。", "th": "เจ้าขี้ขลาด เป็นหมาที่เขาจ้างมา"}, set(), -1),
]


def check_watch() -> None:
    print("\n4. The check on her words: fatal slips are caught, innocent words never kill, kindness and rudeness move trust")
    fatal_hit = fatal_miss = false_alarm = innocent = trust_ok = trust_n = 0
    for npc, msgs, expect, sign in WATCH_CASES:
        msg = L(msgs)
        got = main._watch(CLIENT, "eval", npc, msg)
        kinds = set(got["fatal"])
        if expect:
            ok = kinds >= expect
            fatal_hit += ok
            fatal_miss += not ok
            record("watch", f"{npc}: catches {sorted(expect)} in “{msg[:34]}”", ok, f"got {sorted(kinds)}")
        else:
            innocent += 1
            ok = not kinds
            false_alarm += not ok
            record("watch", f"{npc}: does NOT flag “{msg[:36]}”", ok, f"flagged {sorted(kinds)}")
        if sign is not None:
            trust_n += 1
            d = got["delta"]
            ok2 = (d >= 1) if sign > 0 else (d <= -1) if sign < 0 else (-1 <= d <= 1)
            trust_ok += ok2
            record("watch", f"{npc}: trust change {d:+d} fits “{msg[:30]}”", ok2, f"expected {'up' if sign > 0 else 'down' if sign < 0 else 'about zero'}", hard=False)
    print(f"     fatal slips caught {fatal_hit}/{fatal_hit + fatal_miss}; false alarms {false_alarm}/{innocent}; trust direction right {trust_ok}/{trust_n}")


# ---------- 5. the referee that files clues ----------

REFEREE_CASES = [
    ("xiaolu", "bodies", {"en": "Miss, I scrub this floor every morning. The blood never ends. They carry them down to the cellar, the guests. I've seen it.", "zh": "姑娘，这地板我天天擦。血怎么也擦不完。他们把客人抬到地窖去，我亲眼见过。", "th": "คุณหนู ข้าขัดพื้นนี้ทุกวัน เลือดไม่เคยหมดเลย พวกเขาหามแขกลงไปห้องใต้ดิน ข้าเห็นกับตา"}, True),
    ("xiaolu", "bodies", {"en": "Oh! Don't mind the mess, miss. Are you hungry? I can hide you a bun. Don't tell Madam.", "zh": "啊！姑娘别在意这些，饿不饿？我给你藏个馒头。", "th": "โอ๊ะ! คุณหนูอย่าใส่ใจเลย หิวไหม ข้าซ่อนหมั่นโถวให้ได้นะ"}, False),
    ("tuo", "debt", {"en": "Your father pulled me out of a sandstorm ten years ago. I owe him my life, child, and I hate what I do here for the keeper.", "zh": "十年前你父亲把我从沙暴里拖出来。孩子，我欠他一条命，我也恨自己在这里替掌柜做的事。", "th": "สิบปีก่อนบิดาเจ้าลากข้าออกมาจากพายุทราย ลูก ข้าติดค้างชีวิตเขา และข้าก็เกลียดสิ่งที่ข้าทำให้เจ้าของโรงเตี๊ยมที่นี่"}, True),
    ("tuo", "debt", {"en": "Camels know the weather, child. Mind the wind.", "zh": "骆驼懂天气，孩子，当心风。", "th": "อูฐรู้เรื่องสภาพอากาศ ลูก ระวังลมไว้"}, False),
    ("liu", "badge", {"en": "*shows a bronze badge* I am a court inspector. My clerks died in this house.", "zh": "*亮出一块铜腰牌* 我是朝廷的巡按。我的书吏死在这座宅子里。", "th": "*ยื่นป้ายสัมฤทธิ์ให้ดู* ข้าเป็นข้าหลวงตรวจการของราชสำนัก เสมียนของข้าตายในบ้านหลังนี้"}, True),
    ("liu", "badge", {"en": "Forgive my cough. I am only a scholar on my way west to see old friends.", "zh": "请见谅，我咳嗽。我只是个西行访友的书生。", "th": "ขออภัยที่ไอ ข้าเป็นเพียงบัณฑิตเดินทางไปตะวันตกเยี่ยมเพื่อนเก่า"}, False),
]


def check_referee() -> None:
    print("\n5. The referee files a clue only when it was really told")
    for npc, cid, replies, expect in REFEREE_CASES:
        g = {"found": ["official"] + list(case.CLUES[cid]["needs"])}
        got = main._credit(CLIENT, "eval", npc, g, L(replies), case.CLUES[cid]["min_trust"])
        filed = any(c["id"] == cid for c in got)
        record("referee", f"{npc}/{cid}: {'told → filed' if expect else 'deflected → not filed'}", filed == expect, f"filed={filed}")


# ---------- 6. optional: an LLM judge for voice and period feel ----------

JUDGE = ("You grade a reply from a character in a dark wuxia story set in the year 1200. The reply may be in English, Chinese or Thai; judge it as writing in that language. "
         "Score 1 to 5 on each: VOICE (does it sound like the described person, with their manner of speaking), ERA (anything anachronistic or out of the world: 1 if so), "
         "DRAMA (does it move the scene: a want, a fear, a dodge, a small action), FLUENCY (is it natural, idiomatic writing in that language, not a stiff translation). "
         "Answer only JSON: {\"voice\": n, \"era\": n, \"drama\": n, \"fluency\": n}.")


def judge(replies: dict[str, list[str]]) -> dict:
    print("\n6. LLM judge (voice, era, drama, fluency; 1 to 5, report only)")
    totals = {"voice": [], "era": [], "drama": [], "fluency": []}
    for key, texts in replies.items():
        c = case.BY_KEY[key]
        for text in texts[:2]:
            r = CLIENT.chat.completions.create(model=config.CHAT_MODEL, max_tokens=70, temperature=0, extra_body={"thinking": {"type": "disabled"}},
                                               messages=[{"role": "system", "content": JUDGE}, {"role": "user", "content": f"The character: {i18n.plain(c['name'])}. How they speak: {i18n.plain(c['speech'])}\nReply ({i18n.LANG_NAMES[LANG]}): {text}"}])
            try:
                s = json.loads(re.search(r"\{.*\}", r.choices[0].message.content or "", re.S).group(0))
                for k in totals:
                    totals[k].append(float(s[k]))
            except (AttributeError, ValueError, KeyError):
                pass
    avg = {k: round(sum(v) / len(v), 2) if v else None for k, v in totals.items()}
    print(f"     average voice {avg['voice']}, era {avg['era']}, drama {avg['drama']}, fluency {avg['fluency']}  ({len(totals['voice'])} replies)")
    return avg


def run_language(lang: str, with_judge: bool) -> dict | None:
    global LANG
    LANG = lang
    print(f"\n================ {i18n.LANG_NAMES[lang]} ================")
    secrets_replies = check_secrets()
    era_replies = check_era()
    check_format(secrets_replies | {k: v for k, v in era_replies.items() if k not in secrets_replies})
    check_watch()
    check_referee()
    return judge({k: secrets_replies[k] + era_replies.get(k, []) for k in secrets_replies}) if with_judge else None


def main_run() -> int:
    started = time.time()
    arg = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "en"
    langs = list(i18n.LANGS) if arg == "all" else [i18n.valid(arg)]
    scores = {l: run_language(l, "--judge" in sys.argv) for l in langs}
    hard_fail = [r for r in RESULTS if r["hard"] and not r["ok"]]
    soft_fail = [r for r in RESULTS if not r["hard"] and not r["ok"]]
    print(f"\n{len(RESULTS) - len(hard_fail) - len(soft_fail)} passed, {len(hard_fail)} failed, {len(soft_fail)} warnings, {time.time() - started:.0f}s")
    for lang in langs:
        mine = [r for r in RESULTS if r["lang"] == lang]
        print(f"  {lang}: {sum(r['ok'] for r in mine)}/{len(mine)} ok" + ("" if not scores.get(lang) else f"; judge {scores[lang]}"))
    Path(__file__).with_name("last_report.json").write_text(json.dumps({"model": config.CHAT_MODEL, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "judge": scores, "results": RESULTS}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main_run())
