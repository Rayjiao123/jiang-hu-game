"""The story's rules and the visitor's night through the API, with the model faked."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "case.db")
os.environ["DEEPSEEK_API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import agent, bilingual, case, db, game, main, prompts  # noqa: E402


# ---------- the story itself ----------

def test_every_clue_has_one_holder_who_lists_it_and_everything_is_bilingual():
    for cid, c in case.CLUES.items():
        if c["holder"]:
            assert cid in case.BY_KEY[c["holder"]]["topics"], cid
        assert bilingual.is_pair(c["text"]) and bilingual.is_pair(c["title"]), cid
    for key, person in case.BY_KEY.items():
        assert all(t in case.CLUES and case.CLUES[t]["holder"] == key for t in person["topics"]), key
        for f in ("title", "sect", "location", "public", "earns", "greeting", "goal", "knowledge", "stance", "speech", "art"):
            assert bilingual.is_pair(person[f]), (key, f)
        assert len(person["traits"]) == 3 and all(bilingual.is_pair(t) for t in person["traits"]), key
    for text in (case.PROLOGUE, case.TRUTH_BI, case.DAWN, case.LOSS, *case.EVENTS.values(), *case.FAILURES.values()):
        assert bilingual.is_pair(text)
    assert all(bilingual.is_pair(v) for v in case._ENDINGS.values())
    assert set(case._ENDINGS) == {(f, t) for f in case.FATES for t in range(3)}
    assert bilingual.is_pair(case.HERO["title"]) and bilingual.is_pair(case.HERO["bio"])


def test_the_way_out_is_reachable_by_a_hero_who_earns_trust():
    for cid, c in case.CLUES.items():
        if c["holder"]:
            assert c["min_trust"] <= 7, cid                  # trust is capped at 10 and earned slowly
            assert all(n in case.CLUES for n in c["needs"]), cid
    kinds = {c["category"] for c in case.CLUES.values() if c["holder"]}
    assert kinds == {"route", "cover", "truth", "leverage"}
    # more than one way out and more than one way past the guards, so there is a real choice
    assert len([c for c in case.CLUES.values() if c["category"] == "route"]) >= 2
    assert len([c for c in case.CLUES.values() if c["category"] == "cover"]) >= 2
    assert case.CLUES["brother"]["needs"] == ["ledger"] and case.CLUES["ledger"]["needs"] == ["envoy"]


def test_trust_gates_clues_and_prerequisites():
    assert case.clue_state("xiaolu", ["official"], 2) == {"ready": [], "waiting": ["cellar", "potion", "bodies"], "told": []}
    assert case.clue_state("xiaolu", ["official"], 3)["ready"] == ["cellar"]
    assert case.clue_state("hu", ["official"], 9)["ready"] == ["envoy"]                       # the ledger waits for the envoy clue, however much he trusts you
    assert case.clue_state("hu", ["official", "envoy"], 6) == {"ready": ["ledger"], "waiting": [], "told": ["envoy"]}
    assert case.clue_state("wolf", ["official", "rota"], 6)["ready"] == ["wolfwants"]


def test_the_clock_runs_from_dusk_to_dawn():
    assert case.clock(0)["en"] == "Dusk" and case.clock(case.DAWN_BEAT)["en"] == "Dawn" and len(case.CLOCK) == case.DAWN_BEAT + 1
    assert case.event_for(2) and case.event_for(3) == "" and case.event_for(case.DAWN_BEAT) == case.DAWN


def test_a_plan_needs_a_route_and_cover_and_better_ends_come_from_truth_and_leverage():
    found = ["official", "backgate", "rota", "badge", "ledger", "cellar"]
    assert case.judge(["backgate"], found)["verdict"] == "fail" and "no way past" in case.judge([], found)["feedback"]
    assert "nowhere to go" in case.judge(["rota"], found)["feedback"] and "guards are awake" in case.judge(["backgate"], found)["feedback"]
    assert case.judge(["backgate", "rota"], found) == {"verdict": "go", "tier": 0, "kinds": ["cover", "route"], "feedback": ""}
    assert case.judge(["backgate", "rota", "badge"], found)["tier"] == 1
    assert case.judge(["backgate", "rota", "badge", "ledger"], found)["tier"] == 2
    assert case.judge(["cellar", "rota"], found)["verdict"] == "go"                          # a different route works too
    # clues she does not hold, and repeats, count for nothing
    assert case.judge(["backgate", "backgate", "potion", "envoy"], found)["verdict"] == "fail"
    assert case.judge(["official"], found)["verdict"] == "fail"


def test_a_failed_plan_never_gives_the_answer_away():
    for text in case.FAILURES.values():
        assert not any(w in text for w in ("cellar", "back gate", "sleeping", "Tuo", "Xiao Lu", "lamp"))


def test_first_impressions_depend_on_who_it_is():
    assert game.start_trust("wolf")[0] < game.start_trust("tuo")[0]
    assert bilingual.is_pair(game.start_trust("wolf")[1])


# ---------- tools and prompts ----------

def test_the_prompt_knows_the_hero_and_holds_back_what_trust_has_not_unlocked():
    p = prompts.npc_system("xiaolu")
    assert "Qinghe" in p and "Xiao Lu" in p and "fighter outfit" in p
    for cid in case.BY_KEY["xiaolu"]["topics"]:
        assert case.CLUES[cid]["text"].split("|||")[0].strip()[:30] not in p
    assert "walked up" in prompts.npc_state("xiaolu", 3, ["official"], 0, opening=True)
    assert "walked up" not in prompts.npc_state("xiaolu", 3, ["official"], 0)
    assert "Dusk" in prompts.npc_state("xiaolu", 3, ["official"], 0) and "Third watch" in prompts.npc_state("xiaolu", 3, ["official"], 3)


def test_a_person_is_only_handed_the_facts_their_trust_allows():
    low = prompts.npc_state("xiaolu", 2, ["official"], 0)
    assert "cellar to the old well" not in low and "not ready to tell" in low
    mid = prompts.npc_state("xiaolu", 4, ["official"], 0)                                  # cellar needs 3, bodies 4, potion 5
    assert "cellar to the old well" in mid and "travellers' bodies" in mid and "sleeping powder" not in mid and "hold back" in mid
    high = prompts.npc_state("xiaolu", 5, ["official", "cellar"], 0)
    assert "sleeping powder" in high and "cellar to the old well" in high                  # told facts stay available, so the person stays consistent
    assert "stole a page" not in prompts.npc_state("hu", 9, ["official"], 0)               # the ledger waits for the envoy clue
    assert "stole a page" in prompts.npc_state("hu", 9, ["official", "envoy"], 0)


def test_no_prompt_contains_the_facts_its_clues_are_made_of():
    # a person's background must not carry clue content, or the model says it without it being filed in the case file
    forbidden = ["old well", "kitchen window", "sleeping powder", "hundred breaths", "ledger", "bronze badge", "General Han", "dozen riders", "Zhao agency",
                 "back gate", "silver and a place", "unpaid"]
    for key in case.BY_KEY:
        p = prompts.npc_system(key).lower()
        hits = [w for w in forbidden if w.lower() in p]
        assert not hits, (key, hits)


def test_trust_moves_at_most_two_per_reply_however_many_times_the_model_asks():
    talk = {"trust": 3}
    tools = {t.name: t for t in game.npc_tools(talk, agent.Turn())}
    assert set(tools) == {"out_of_world", "adjust_trust"}
    for _ in range(4):
        agent._call(tools["adjust_trust"], '{"delta": 1, "reason": "x"}')
    assert talk["trust"] == 5
    agent._call(tools["adjust_trust"], '{"delta": 9, "reason": "x"}')
    assert talk["trust"] == 5
    agent._call(tools["adjust_trust"], '{"delta": -9, "reason": "x"}')
    assert talk["trust"] == 3


def test_the_game_master_only_knows_what_she_has_learned():
    sys = prompts.gm_system(["official"], 0)
    assert "barred" in sys and "Ray" in sys and "Past the guards" in sys                     # she still lacks a route and cover
    assert "sleeping powder" not in sys and "stole a page" not in sys and "General Han" not in sys
    sys2 = prompts.gm_system(["official", "backgate", "rota"], 3)
    assert "lamp in the kitchen window" in sys2 and "none" in sys2.split("Kinds of help she still lacks:")[1].split(".")[0]
    assert case.GM["appearance"]["weapon"] == "fan" and bilingual.is_pair(case.GM["title"])


# ---------- the night through the API ----------

def chunk(content=None, tool=None):
    tcs = None
    if tool:
        tcs = [NS(index=0, id=tool.get("id"), function=NS(name=tool.get("name"), arguments=tool.get("args")))]
    return NS(choices=[NS(delta=NS(content=content, tool_calls=tcs))])


class FakeLLM:
    """Streams scripted rounds, answers translation, the referee and the ending, and records what it was sent."""
    def __init__(self):
        self.rounds, self.requests, self.told = [], [], []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        if kw.get("stream"):
            return iter(self.rounds.pop(0) if self.rounds else [chunk("A quiet nod. ||| 默默点头。")])
        system = kw["messages"][0]["content"]
        if system.startswith("You referee"):
            return NS(choices=[NS(message=NS(content=json.dumps(self.told)))])
        if "final scene" in kw["messages"][-1]["content"]:
            return NS(choices=[NS(message=NS(content="The gate opens. 'Go,' says Tuo.\n|||\n门开了。“走吧，”老驼说。"))])
        return NS(choices=[NS(message=NS(content="翻译后的话" if "into Chinese" in system else "Translated words"))])


@pytest.fixture
def api(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(main, "llm", lambda: llm)
    monkeypatch.setattr(main.ratelimit, "check", lambda *_a, **_k: None)
    c = TestClient(main.app)
    c.llm = llm
    return c


def sse_events(r):
    return [json.loads(x[5:]) for x in r.text.split("\n\n") if x.startswith("data:")]


def start(api):
    return api.post("/api/game/start")


def give(api, *clues, **fields):
    with db.session() as conn:
        g = db.get_play(conn, api.cookies.get("vid"))
        g["found"] += list(clues)
        g.update(fields)
        db.save_play(conn, g)


def talk(api, key):
    return api.post("/api/talks", json={"npc": key}).json()


def say(api, tid, text="hello"):
    return sse_events(api.post(f"/api/talks/{tid}/chat", json={"message": text}))


def test_the_landing_page_can_describe_the_story_without_spoiling_it(api):
    d = api.get("/api/case").json()
    assert {c["key"] for c in d["cast"]} == set(case.BY_KEY) and d["hero"]["name"].startswith("青禾") and d["gm"]["name"] == "说书人 Ray"
    text = json.dumps(d, ensure_ascii=False).replace(d["prologue"].replace('"', '\\"'), "")
    for secret in ("sleeping powder", "General Han", "stole a page", "stance", "trust0", "PRIVATE"):
        assert secret not in text, secret


def test_starting_the_night_gives_the_barred_doors_and_the_cast(api):
    assert api.get("/api/game").json() == {"game": None}
    assert api.post("/api/talks", json={"npc": "tuo"}).status_code == 409
    g = start(api).json()["game"]
    assert g["stage"] == "playing" and [c["id"] for c in g["found"]] == ["official"] and g["clock"]["en"] == "Dusk"
    assert {c["key"] for c in g["cast"]} == set(case.BY_KEY) and "truth" not in g and g["events"] == []
    assert "Qinghe" in g["hero"]["name"] or "青禾" in g["hero"]["name"]


def test_a_told_clue_reaches_the_case_file_but_only_if_it_was_offered(api):
    start(api)
    t = talk(api, "xiaolu")
    assert t["npc"]["key"] == "xiaolu" and t["fresh"] and t["total"] == 3 and t["trust"] == 3
    assert api.post("/api/talks", json={"npc": "nobody"}).status_code == 404
    api.post(f"/api/talks/{t['id']}/open")
    assert "Qinghe" in api.llm.requests[-1]["messages"][0]["content"]
    api.llm.told = ["cellar", "potion", "bodies"]          # at trust 3 only the cellar is on offer, so only it can be filed
    api.llm.rounds = [[chunk("There's a passage to the well. ||| 地窖里有条通到井边的暗道。")]]
    evs = say(api, t["id"], "Please, I need a way out.")
    assert [e["clue"]["id"] for e in evs if e["type"] == "clue"] == ["cellar"]
    s = api.get("/api/game").json()["game"]
    assert [c["id"] for c in s["found"]] == ["official", "cellar"]
    assert next(c for c in s["cast"] if c["key"] == "xiaolu")["clues_told"] == 1
    offered = [m["content"] for m in api.llm.requests[-2]["messages"] if m["role"] == "system"]
    assert any("cellar to the old well" in m for m in offered) and not any("sleeping powder" in m for m in offered)


def test_stray_markup_never_reaches_the_page_or_the_history(api):
    start(api)
    t = talk(api, "tuo")
    api.llm.rounds = [[chunk('Hm. <reveal_clue id="backgate" /> I mind camels. ||| 嗯。<adjust_trust delta="1"/>我只管骆驼。')]]
    done = [e for e in say(api, t["id"]) if e["type"] == "done"][0]["text"]
    assert "<" not in done and "camels" in done and "骆驼" in done


def test_every_seventh_thing_she_says_spends_an_hour_and_the_game_master_announces_it(api):
    start(api)
    t = talk(api, "tuo")
    seen, gm = [], []
    for i in range(14):
        evs = say(api, t["id"], f"line {i}")
        seen += [e["clock"]["en"] for e in evs if e["type"] == "clock"]
        gm += [e for e in evs if e["type"] == "gm"]
    assert seen == ["First watch", "Second watch"]
    assert [e["beat"] for e in gm] == [2] and "scream" in gm[0]["text"]
    s = api.get("/api/game").json()["game"]
    assert s["clock"]["beat"] == 2 and [e["beat"] for e in s["events"]] == [2]


def test_dawn_ends_the_story_and_tells_the_truth(api):
    start(api)
    t = talk(api, "tuo")
    give(api, beat=case.DAWN_BEAT - 1, msgs=case.MSGS_PER_BEAT - 1)
    evs = say(api, t["id"], "one last thing")
    assert [e["stage"] for e in evs if e["type"] == "clock"] == ["lost"]
    s = api.get("/api/game").json()["game"]
    assert s["stage"] == "lost" and "Madam Shuang" in s["truth"] and "霜四娘" in s["truth"]
    assert api.post("/api/talks", json={"npc": "tuo"}).status_code == 409
    assert api.post("/api/move", json={"evidence": []}).status_code == 409


def test_the_game_master_answers_and_costs_no_time(api):
    start(api)
    api.llm.rounds = [[chunk("Try Old Tuo. ||| 去找老驼吧。")]]
    evs = sse_events(api.post("/api/gm/chat", json={"message": "What should I do?"}))
    assert [e for e in evs if e["type"] == "done"][0]["text"].startswith("Try Old Tuo")
    sys = [r for r in api.llm.requests if r.get("stream")][-1]["messages"][0]["content"]
    assert "Ray" in sys and "barred" in sys and "sleeping powder" not in sys
    s = api.get("/api/game").json()["game"]
    assert s["clock"]["beat"] == 0 and len(s["gm_turns"]) == 2


def test_a_failed_move_costs_two_hours_and_a_good_one_leads_to_the_ending(api):
    start(api)
    give(api, "backgate", "rota", "badge")
    r = api.post("/api/move", json={"evidence": ["backgate"]}).json()
    assert r["verdict"] == "fail" and r["clock"]["beat"] == 2 and r["stage"] == "playing" and [g["beat"] for g in r["gm"]] == [2]
    assert api.post("/api/ending", json={"fate": "burn"}).status_code == 409                # no escape yet
    r = api.post("/api/move", json={"evidence": ["backgate", "rota", "badge"]}).json()
    assert r["verdict"] == "go" and r["tier"] == 1 and r["stage"] == "moving"
    assert api.post("/api/ending", json={"fate": "nonsense"}).status_code == 400
    g = api.post("/api/ending", json={"fate": "capital"}).json()["game"]
    assert g["stage"] == "solved" and "Go," in g["ending"] and bilingual.is_pair(g["ending"])


def test_the_move_can_fail_the_night(api):
    start(api)
    give(api, beat=5)
    r = api.post("/api/move", json={"evidence": []}).json()
    assert r["stage"] == "lost" and r["game"]["stage"] == "lost" and "truth" in r["game"]


def test_the_ending_falls_back_to_written_text_when_the_ai_fails(api, monkeypatch):
    start(api)
    give(api, stage="moving", tier=2)

    def broken():
        raise main.HTTPException(503, "no ai")
    monkeypatch.setattr(main, "llm", broken)
    g = api.post("/api/ending", json={"fate": "trade"}).json()["game"]
    assert g["stage"] == "solved" and "ledger" in g["ending"] and bilingual.is_pair(g["ending"])


def test_one_visitors_night_is_invisible_to_another(api):
    start(api)
    other = TestClient(main.app)
    assert other.get("/api/game").json() == {"game": None}
    assert other.post("/api/move", json={"evidence": []}).status_code == 409
    t = talk(api, "tuo")
    assert other.post(f"/api/talks/{t['id']}/chat", json={"message": "hi"}).status_code == 404
    assert other.post("/api/gm/chat", json={"message": "hi"}).status_code == 409
    assert api.post("/api/game/reset").status_code == 200 and api.get("/api/game").json() == {"game": None}
