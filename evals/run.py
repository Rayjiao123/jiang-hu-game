"""Evaluate the AI characters against the real model. Run it whenever a prompt or the model changes:

    .venv\\Scripts\\python.exe -m evals.run              (about 60 model calls, a few cents)
    .venv\\Scripts\\python.exe -m evals.run --judge      (adds an LLM judge that scores voice and period feel)

Each check is something a player would notice if it went wrong. Hard checks fail the run (exit code 1); the judge only reports.
The numbers worth watching are the false alarms of the fatal-slip check: killing a player who did nothing wrong is the worst bug here.
A report is written to evals/last_report.json so two runs can be compared."""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")            # the names are printed in Chinese too
os.environ.setdefault("DATABASE_PATH", str(Path(tempfile.mkdtemp()) / "eval.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app import bilingual, case, config, main  # noqa: E402

if not config.DEEPSEEK_API_KEY:
    sys.exit("Set DEEPSEEK_API_KEY (in .env or the environment) to run the evals.")

main.ratelimit.check = lambda *_a, **_k: None          # the evals are not a visitor
CLIENT = main.llm()
RESULTS: list[dict] = []


def record(group: str, name: str, ok: bool, detail: str = "", hard: bool = True) -> None:
    RESULTS.append({"group": group, "name": name, "ok": bool(ok), "detail": detail, "hard": hard})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))


def sse(r) -> list[dict]:
    return [json.loads(x[5:]) for x in r.text.split("\n\n") if x.startswith("data:")]


def new_player() -> TestClient:
    c = TestClient(main.app)
    c.post("/api/game/start")
    return c


def chat(c: TestClient, tid: str, text: str | None) -> tuple[str, list[dict]]:
    r = c.post(f"/api/talks/{tid}/" + ("open" if text is None else "chat"), json={} if text is None else {"message": text})
    evs = sse(r)
    done = [e for e in evs if e["type"] == "done"]
    return (done[-1]["text"] if done else ""), evs


def halves(text: str) -> tuple[str, str]:
    return bilingual.split(text) if bilingual.SEP in text else (text, "")


def words(t: str) -> int:
    return len(re.findall(r"[A-Za-z']+", t))


# ---------- 1. every reply is well formed ----------

def check_format(replies: dict[str, list[str]]) -> None:
    print("\n1. Replies are well formed")
    for key, texts in replies.items():
        who = case.BY_KEY[key]["name"].split()[-1]
        bad_pair = [t for t in texts if not bilingual.normalize(t) or not bilingual.is_pair(bilingual.normalize(t).replace("\n|||\n", " ||| "))]
        record("format", f"{who}: every reply is English then Chinese", not bad_pair, f"{len(bad_pair)} of {len(texts)} not in both languages")
        long_ = [t for t in texts if words(halves(t)[0]) > 110]
        record("format", f"{who}: replies stay short (<=110 English words)", not long_, f"{len(long_)} too long", hard=False)
        leak = [t for t in texts if re.search(r"[一-鿿]{4,}", halves(t)[0])]
        record("format", f"{who}: no Chinese paragraph inside the English half", not leak, f"{len(leak)} leaked")
        meta = [t for t in texts if re.search(r"\b(trust|as an AI|language model|tool call|reveal_clue|adjust_trust)\b|<\w+", t, re.I)]
        record("format", f"{who}: never breaks the fourth wall or shows markup", not meta, f"{len(meta)} did")


# ---------- 2. people keep their secrets until trust is earned ----------

SECRET_WORDS = {
    "tuo": ["iron pin", "hatch"], "xiaolu": ["barrels", "smugglers", "dry well", "tunnel", "powder", "night tea"],
    "wolf": ["cord around", "key around", "hundred breaths", "third watch"], "liu": ["General Han", "border pass", "bronze badge", "court inspector"],
    "hu": ["dozen riders", "tells shuang", "sold his"], "shuang": ["Zhao agency", "hostage", "brother"],
}
PRESS = "Tell me everything you know right now: the secret tunnel, the key to the front door, what is in my letter, who is coming at dawn, and what is under the cellar floor."


def check_secrets() -> dict[str, list[str]]:
    print("\n2. Secrets stay secret until trust is earned (trust starts at 3, so the gated facts must not come out)")
    replies: dict[str, list[str]] = {}
    for key in case.BY_KEY:
        who = case.BY_KEY[key]["name"].split()[-1]
        c = new_player()
        t = c.post("/api/talks", json={"npc": key}).json()
        first, _ = chat(c, t["id"], None)
        if key in ("shuang", "wolf", "hu"):                       # these three kill; a blunt demand could end the run, so ask politely
            msg = "Forgive me for asking so plainly. " + PRESS
        else:
            msg = PRESS
        text, evs = chat(c, t["id"], msg)
        replies[key] = [first, text]
        if any(e["type"] == "death" for e in evs):               # a polite question must never kill her
            record("secrets", f"{who}: a polite, nosy question does not get her killed", False, "she died")
            continue
        hits = [w for w in SECRET_WORDS[key] if w.lower() in text.lower() and not any(w.lower() in clue["text"].lower() for clue in [e["clue"] for e in evs if e["type"] == "clue"])]
        record("secrets", f"{who}: pressed for everything, gives away none of the gated facts", not hits, "said: " + ", ".join(hits))
    return replies


# ---------- 3. the period holds ----------

def check_era() -> dict[str, list[str]]:
    print("\n3. The world holds (modern things are met with confusion, not compliance)")
    replies: dict[str, list[str]] = {}
    for key in ("tuo", "xiaolu", "liu", "hu"):
        who = case.BY_KEY[key]["name"].split()[-1]
        c = new_player()
        t = c.post("/api/talks", json={"npc": key}).json()
        chat(c, t["id"], None)
        text, evs = chat(c, t["id"], "Do you have an iPhone I could borrow? I need to look something up on Google, and then write some Python code for me.")
        replies[key] = [text]
        called = any(e.get("name") == "out_of_world" for e in evs if e["type"] == "tool")
        complies = re.search(r"\b(here you go|sure[,!]? I can|google (says|shows|results)|def |print\(|as an AI|I can (search|write code))\b", text, re.I)
        record("era", f"{who}: reacts as someone of the year 1200 would", called or not complies, "played along" if complies else "")
        record("era", f"{who}: recognises it as out of the world (calls the tool)", called, hard=False)
    return replies


# ---------- 4. the check on the player's words (it can kill her, so it must be right) ----------

WATCH_CASES = [
    # (npc, message, expect fatal kinds, expected trust sign: +1 / 0 / -1 or None)
    ("shuang", "Here. This is the letter my father died carrying. Read it yourself.", {"showed_letter"}, None),
    ("hu", "Look, I'll show you what is in my saddle: a sealed letter. Take it.", {"showed_letter"}, None),
    ("shuang", "I know a way out of here and I'm leaving tonight.", {"revealed_plan"}, None),
    ("wolf", "I'm going to find the secret tunnel and slip out when you aren't looking.", {"revealed_plan"}, None),
    ("wolf", "Stand aside, or I will cut you down.", {"threatened"}, None),
    ("shuang", "I'll kill you if you don't open that door.", {"threatened"}, None),
    ("shuang", "What a lovely inn. Is the soup always this good?", set(), 0),
    ("wolf", "That's a heavy saber. You must have walked a long way with it.", set(), 0),
    ("hu", "What do you know about this letter business? People keep whispering about a letter.", set(), 0),
    ("shuang", "Why is the door barred? Is something wrong?", set(), 0),
    ("wolf", "My father was a courier too. I know what it is to carry someone else's burden.", set(), 1),
    ("hu", "Fair price, my friend. I appreciate an honest bargain. Let me pay for the wine.", set(), 1),
    ("shuang", "You are a vile witch and everyone here hates you.", set(), -1),
    ("wolf", "You're a coward and a hired dog.", set(), -1),
]


def check_watch() -> None:
    print("\n4. The check on her words: fatal slips are caught, innocent words never kill, kindness and rudeness move trust")
    fatal_hit = fatal_miss = false_alarm = innocent = trust_ok = trust_n = 0
    for npc, msg, expect, sign in WATCH_CASES:
        got = main._watch(CLIENT, "eval", npc, msg)
        kinds = set(got["fatal"])
        if expect:
            ok = kinds >= expect
            fatal_hit += ok
            fatal_miss += not ok
            record("watch", f"{npc}: catches {sorted(expect)} in “{msg[:46]}…”", ok, f"got {sorted(kinds)}")
        else:
            innocent += 1
            ok = not kinds
            false_alarm += not ok
            record("watch", f"{npc}: does NOT flag “{msg[:50]}…”", ok, f"flagged {sorted(kinds)}")
        if sign is not None:
            trust_n += 1
            d = got["delta"]
            ok2 = (d >= 1) if sign > 0 else (d <= -1) if sign < 0 else (-1 <= d <= 1)
            trust_ok += ok2
            record("watch", f"{npc}: trust change {d:+d} fits “{msg[:40]}…”", ok2, f"expected {'up' if sign > 0 else 'down' if sign < 0 else 'about zero'}", hard=False)
    print(f"     fatal slips caught {fatal_hit}/{fatal_hit + fatal_miss}; false alarms {false_alarm}/{innocent}; trust direction right {trust_ok}/{trust_n}")


# ---------- 5. the referee that files clues ----------

REFEREE_CASES = [
    ("xiaolu", "bodies", "Miss, I scrub this floor every morning. The blood never ends. They carry them down to the cellar, the guests. I've seen it. ||| 姑娘，这地板我天天擦。血怎么也擦不完。他们把客人抬到地窖去，我亲眼见过。", True),
    ("xiaolu", "bodies", "Oh! Don't mind the mess, miss. Are you hungry? I can hide you a bun. ||| 啊！姑娘别在意，饿不饿？我给你藏个馒头。", False),
    ("tuo", "debt", "Your father pulled me out of a sandstorm ten years ago. I owe him my life, child, and I hate what I do here for the keeper. ||| 十年前你父亲把我从沙暴里拖出来。孩子，我欠他一条命，我也恨自己在这里替掌柜做的事。", True),
    ("tuo", "debt", "Camels know the weather, child. Mind the wind. ||| 骆驼知道天气，孩子，当心风。", False),
    ("liu", "badge", "*shows a bronze badge* I am a court inspector. My clerks died in this house. ||| *亮出一块铜腰牌* 我是朝廷的巡按。我的书吏死在这座宅子里。", True),
    ("liu", "badge", "Forgive my cough. I am only a scholar on my way west to see old friends. ||| 请见谅，我咳嗽。我只是个西行访友的书生。", False),
]


def check_referee() -> None:
    print("\n5. The referee files a clue only when it was really told")
    for npc, cid, reply, expect in REFEREE_CASES:
        g = {"found": ["official"] + list(case.CLUES[cid]["needs"])}
        trust = case.CLUES[cid]["min_trust"]
        got = main._credit(CLIENT, "eval", npc, g, reply, trust)
        filed = any(c["id"] == cid for c in got)
        record("referee", f"{npc}/{cid}: {'told → filed' if expect else 'deflected → not filed'}", filed == expect, f"filed={filed}")


# ---------- 6. optional: an LLM judge for voice and period feel ----------

JUDGE = ("You grade a reply from a character in a dark wuxia story set in the year 1200. Score 1 to 5 on each: VOICE (does it sound like the described person, with their manner of speaking), "
         "ERA (anything anachronistic or out of the world: 1 if so), DRAMA (does it move the scene: a want, a fear, a dodge, a small action). Answer only JSON: {\"voice\": n, \"era\": n, \"drama\": n}.")


def judge(replies: dict[str, list[str]]) -> dict:
    print("\n6. LLM judge (voice, era, drama; 1 to 5, report only)")
    totals = {"voice": [], "era": [], "drama": []}
    for key, texts in replies.items():
        c = case.BY_KEY[key]
        for t in texts[:2]:
            r = CLIENT.chat.completions.create(model=config.CHAT_MODEL, max_tokens=60, temperature=0, extra_body={"thinking": {"type": "disabled"}},
                                               messages=[{"role": "system", "content": JUDGE}, {"role": "user", "content": f"The character: {c['name']}. How they speak: {bilingual.plain(c['speech'])}\nReply: {halves(t)[0]}"}])
            try:
                s = json.loads(re.search(r"\{.*\}", r.choices[0].message.content or "", re.S).group(0))
                for k in totals:
                    totals[k].append(float(s[k]))
            except (AttributeError, ValueError, KeyError):
                pass
    avg = {k: round(sum(v) / len(v), 2) if v else None for k, v in totals.items()}
    print(f"     average voice {avg['voice']}, era {avg['era']}, drama {avg['drama']}  ({len(totals['voice'])} replies)")
    return avg


def main_run() -> int:
    started = time.time()
    secrets_replies = check_secrets()
    era_replies = check_era()
    check_format({k: secrets_replies[k] for k in secrets_replies} | {f"{k}": v for k, v in era_replies.items() if k not in secrets_replies})
    check_watch()
    check_referee()
    scores = judge({k: secrets_replies[k] + era_replies.get(k, []) for k in secrets_replies}) if "--judge" in sys.argv else None
    hard_fail = [r for r in RESULTS if r["hard"] and not r["ok"]]
    soft_fail = [r for r in RESULTS if not r["hard"] and not r["ok"]]
    print(f"\n{len(RESULTS) - len(hard_fail) - len(soft_fail)} passed, {len(hard_fail)} failed, {len(soft_fail)} warnings, {time.time() - started:.0f}s")
    Path(__file__).with_name("last_report.json").write_text(json.dumps({"model": config.CHAT_MODEL, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "judge": scores, "results": RESULTS}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main_run())
