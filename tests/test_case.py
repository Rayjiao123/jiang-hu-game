"""The mystery's rules and the visitor's journey through the API, with the model faked."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "case.db")
os.environ["DEEPSEEK_API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import agent, bilingual, case, db, game, main, prompts, roll  # noqa: E402

HERO = {"name": "沈青 Shen Qing", "title": "Lantern Sword ||| 灯剑", "path": "orthodox", "temperament": "wry",
        "art": "Lantern Cut: slices the flame, not the wick ||| 灯斩：断焰不断芯", "quirk": "Talks to his lantern ||| 对灯笼说话",
        "beloved_name": "柳如烟 Liu Ruyan", "beloved_bond": "betrothed ||| 未婚妻", "beloved_token": "a jade hairpin ||| 一支玉簪",
        "appearance": game.merge_appearance({}, {}, "shen")}


def hero(**over):
    return {**HERO, **over}


# ---------- the case itself ----------

def test_every_clue_has_exactly_one_holder_who_lists_it_as_a_topic():
    for cid, c in case.CLUES.items():
        if c["holder"]:
            assert cid in case.BY_KEY[c["holder"]]["topics"], cid
        assert bilingual.is_pair(c["text"]) and bilingual.is_pair(c["title"]), cid
    for key, person in case.BY_KEY.items():
        assert all(t in case.CLUES and case.CLUES[t]["holder"] == key for t in person["topics"]), key
        for f in ("title", "sect", "location", "public", "greeting", "goal", "knowledge", "stance", "speech", "art"):
            assert bilingual.is_pair(person[f]), (key, f)
        assert len(person["traits"]) == 3 and all(bilingual.is_pair(t) for t in person["traits"]), key


def test_enough_proof_exists_to_solve_it_without_the_hidden_champion():
    visible = set(case.starting_cast())
    kinds = {c["category"] for c in case.CLUES.values() if c["holder"] in visible and c["category"]}
    assert len(kinds) >= case.PROOF_NEEDED + 1


def test_every_clue_is_reachable_by_a_hero_who_earns_trust():
    for cid, c in case.CLUES.items():
        if c["holder"]:
            assert c["min_trust"] <= 7, cid                  # trust is capped at 10 and earned slowly
            assert all(n in case.CLUES for n in c["needs"]), cid
    assert case.CLUES["voice"]["needs"] == ["wound"]


def test_clues_are_written_in_the_heros_own_names():
    text = case.fill(case.CLUES["charm"]["text"], hero())
    assert "Liu Ruyan" in text and "柳如烟" in text and "jade hairpin" in text and "玉簪" in text and "{" not in text
    assert bilingual.is_pair(case.prologue(hero())) and "Liu Ruyan" in case.prologue(hero())
    assert bilingual.is_pair(case.truth(hero()))
    for fate in case.FATES:
        assert bilingual.is_pair(case.fallback_ending(fate, hero()))


def test_trust_gates_clues_and_prerequisites():
    assert case.can_reveal("wound", "bai", [], 4)[0] is False
    assert case.can_reveal("wound", "bai", [], 5)[0] is True
    assert case.can_reveal("voice", "lu", [], 9)[0] is False                  # needs the wound first, however much he trusts you
    assert case.can_reveal("voice", "lu", ["wound"], 6)[0] is True
    assert case.can_reveal("wound", "xie", [], 10)[0] is False                # not his to tell
    assert case.can_reveal("nonsense", "xie", [], 10)[0] is False
    assert case.clue_state("bai", ["wound"], 5) == {"ready": [], "waiting": ["herb"], "told": ["wound"]}


def test_first_impressions_depend_on_who_arrives():
    same, _ = case.start_trust("su", hero(path="orthodox", temperament="blunt"))
    opposed, _ = case.start_trust("su", hero(path="unorthodox", temperament="wry"))
    assert same > opposed
    assert case.start_trust("leng", hero(path="unorthodox", temperament="cool"))[0] > case.start_trust("leng", hero(path="orthodox", temperament="wry"))[0]


def test_an_accusation_needs_the_right_person_and_three_kinds_of_proof():
    found = ["official", "wound", "charm", "lantern", "herb"]
    wrong = case.judge("leng", ["wound"], found)
    assert wrong["verdict"] == "wrong" and "Leng" in wrong["feedback"]
    thin = case.judge("yun", ["wound", "herb"], found)                       # how + why
    assert thin["verdict"] == "unproven" and "1 more" in thin["feedback"]
    assert case.judge("yun", ["wound", "herb", "charm"], found)["verdict"] == "correct"      # how + why + where
    assert case.judge("yun", ["wound", "herb", "lantern"], found)["verdict"] == "correct"    # how + why + who
    # clues the hero does not hold, and repeats, count for nothing
    assert case.judge("yun", ["wound", "wound", "wound", "hand", "voice"], found)["verdict"] == "unproven"
    assert case.judge("yun", ["official", "official", "official"], found)["verdict"] == "unproven"


def test_a_wrong_name_never_names_the_killer():
    for key, line in case.REBUTTALS.items():
        assert key != case.CULPRIT and "Yun" not in line and "云无涯" not in line


# ---------- tools and prompts ----------

def test_npc_prompt_knows_the_hero_but_holds_back_clue_text():
    p = prompts.npc_system("bai", hero())
    assert "Shen Qing" in p and "Liu Ruyan" in p and "orthodox" in p and "wry" in p
    for cid in case.BY_KEY["bai"]["topics"]:
        assert case.CLUES[cid]["text"].split("|||")[0].strip()[:30] not in p       # clue text is only given turn by turn, when trust allows
    assert "walked up" in prompts.npc_state("bai", 3, [], hero(), opening=True)
    assert "walked up" not in prompts.npc_state("bai", 3, [], hero())


def test_a_person_is_only_handed_the_facts_their_trust_allows():
    low = prompts.npc_state("bai", 3, ["official"], hero())
    assert "Not a fall" not in low and "not ready to tell" in low
    mid = prompts.npc_state("bai", 5, ["official"], hero())                              # wound needs 5, herb needs 6
    assert "Not a fall" in mid and "dewgrass" not in mid and "hold back" in mid
    high = prompts.npc_state("bai", 6, ["official", "wound"], hero())
    assert "dewgrass" in high and "Not a fall" in high                                   # told facts stay available, so the person stays consistent
    assert "Liu Ruyan" in prompts.npc_state("su", 5, ["official"], hero())               # facts are written in the hero's names
    assert "heard something heavy fall" not in prompts.npc_state("lu", 9, ["official"], hero())      # "voice" waits for the wound clue
    assert "heard something heavy fall" in prompts.npc_state("lu", 9, ["official", "wound"], hero())


def test_trust_moves_at_most_two_per_reply_however_many_times_the_model_asks():
    talk = {"trust": 3}
    turn = agent.Turn()
    tools = {t.name: t for t in game.npc_tools(talk, turn)}
    assert "reveal_clue" not in tools
    for _ in range(4):
        agent._call(tools["adjust_trust"], '{"delta": 1, "reason": "x"}')
    assert talk["trust"] == 5
    agent._call(tools["adjust_trust"], '{"delta": 9, "reason": "x"}')
    assert talk["trust"] == 5
    agent._call(tools["adjust_trust"], '{"delta": -9, "reason": "x"}')
    assert talk["trust"] == 3                                                            # a rude reply can take it back by 2 more in the other direction


def test_no_witness_prompt_contains_the_facts_their_clues_are_made_of():
    # a person's background must not carry clue content, or the model says it without reveal_clue and the case file never records it
    forbidden = ["dewgrass", "burnt sugar", "gardener", "side gate", "azure sash", "forgive me", "soft-soled", "treasury", "Pavilion silver", "nine thin", "seven of the nine"]
    for key in ("xie", "su", "bai", "leng", "lu"):
        p = prompts.npc_system(key, hero()).lower()
        assert not [w for w in forbidden if w.lower() in p], (key, [w for w in forbidden if w.lower() in p])


def test_the_hero_sheet_is_built_and_edited_within_the_rules():
    s = game.blank_sheet()
    assert set(game.missing(s)) == set(game.REQUIRED)
    rejected = []
    game.apply_fields(s, {"path": "evil", "temperament": "gentle", "quirk": "only English"}, rejected)
    assert set(rejected) == {"quirk", "path"}
    assert s["temperament"] == "gentle" and s["path"] == ""
    assert game.edit_field(None, "m", s, "path", "neutral") == "" and s["path"] == "neutral"
    assert game.edit_field(None, "m", s, "path", "evil") != ""
    assert game.edit_field(None, "m", s, "title", "Lone Wolf ||| 孤狼") == "" and s["title"] == "Lone Wolf ||| 孤狼"
    assert game.edit_field(None, "m", s, "bogus", "x") != ""

    class T:
        def __init__(self):
            self.chat = NS(completions=NS(create=lambda **k: NS(choices=[NS(message=NS(content="夜行者"))])))
    assert game.edit_field(T(), "m", s, "quirk", "Walks at night") == ""                      # one language is completed by translation
    assert bilingual.is_pair(s["quirk"]) and s["quirk"].startswith("Walks at night")


def test_dice_make_complete_varied_heroes():
    seeds = [roll.random_seed() for _ in range(40)]
    assert len({s["summary"] for s in seeds}) > 25
    assert all(s["path"] in game.PATHS and s["temperament"] in game.TEMPERAMENTS and s["summary_zh"] for s in seeds)
    assert "murdered" in seeds[0]["summary"] and "path" in roll.roll_message(seeds[0])


# ---------- the journey through the API ----------

def chunk(content=None, tool=None):
    tcs = None
    if tool:
        tcs = [NS(index=0, id=tool.get("id"), function=NS(name=tool.get("name"), arguments=tool.get("args")))]
    return NS(choices=[NS(delta=NS(content=content, tool_calls=tcs))])


class FakeLLM:
    """Streams scripted rounds, answers translation and the ending, and records what it was sent."""
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
            return NS(choices=[NS(message=NS(content="He bows. 'It was I.'\n|||\n他躬身：“是我。”"))])
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


def start(api, sheet=None):
    api.post("/api/game/new")
    with db.session() as conn:
        g = db.get_game(conn, api.cookies.get("vid"))
        g["hero"] = sheet or hero()
        db.save_game(conn, g)
    return api.post("/api/game/start")


def give(api, *clues):
    with db.session() as conn:
        g = db.get_game(conn, api.cookies.get("vid"))
        g["found"] += list(clues)
        db.save_game(conn, g)


def test_the_landing_page_can_describe_the_case_without_spoiling_it(api):
    d = api.get("/api/case").json()
    keys = {c["key"] for c in d["cast"]}
    assert keys == set(case.starting_cast()) and "lu" not in keys
    text = json.dumps(d, ensure_ascii=False)
    for secret in ("dewgrass", "silver-vein", "nine-layer", "truth", "stance"):
        assert secret not in text


def test_you_cannot_start_until_the_hero_is_complete_and_edits_are_checked(api):
    assert api.get("/api/game").json() == {"game": None}
    assert api.post("/api/game/start").status_code == 409
    api.post("/api/game/new")
    assert api.post("/api/game/start").status_code == 400                       # nothing filled in yet
    r = api.post("/api/game/edit", json={"field": "path", "value": "neutral"})
    assert r.status_code == 200 and r.json()["hero"]["path"] == "neutral"
    assert api.post("/api/game/edit", json={"field": "path", "value": "evil"}).status_code == 400
    r = api.post("/api/game/edit", json={"field": "title", "value": "Lone Wolf"})
    assert r.status_code == 200 and bilingual.is_pair(r.json()["hero"]["title"])
    s = api.get("/api/game").json()["game"]
    assert s["stage"] == "creating" and "path" not in s["missing"] and "title" not in s["missing"]


def test_starting_the_story_gives_the_official_account_and_the_cast(api):
    r = start(api)
    assert r.status_code == 200
    g = r.json()["game"]
    assert g["stage"] == "playing" and [c["id"] for c in g["found"]] == ["official"] and g["attempts"] == 3
    assert "Liu Ruyan" in g["found"][0]["text"] and "Liu Ruyan" in g["prologue"]
    assert {c["key"] for c in g["cast"]} == set(case.starting_cast())
    assert "truth" not in g
    assert api.post("/api/game/edit", json={"field": "path", "value": "neutral"}).status_code == 409      # the hero is fixed now


def test_a_conversation_is_tailored_and_a_told_clue_reaches_the_case_file(api):
    start(api)
    t = api.post("/api/talks", json={"npc": "bai"}).json()
    assert t["npc"]["key"] == "bai" and t["fresh"] and t["total"] == 2
    assert api.post("/api/talks", json={"npc": "lu"}).status_code == 404                    # not found yet
    api.post(f"/api/talks/{t['id']}/open")
    sys_prompt = api.llm.requests[-1]["messages"][0]["content"]
    assert "Shen Qing" in sys_prompt and "Bai Suxin" in sys_prompt

    # trust 3: nothing is ready, so even a referee that says "told" cannot file a clue that was never offered
    api.llm.told = ["wound", "herb"]
    evs = sse_events(api.post(f"/api/talks/{t['id']}/chat", json={"message": "How did she die?"}))
    assert not [e for e in evs if e["type"] == "clue"]
    assert [c["id"] for c in api.get("/api/game").json()["game"]["found"]] == ["official"]

    # earn trust (two points in one reply), and next turn the wound is on offer and gets filed
    api.llm.rounds = [[chunk(tool={"id": "c2", "name": "adjust_trust", "args": '{"delta": 2, "reason": "kind"}'})],
                      [chunk("Fine. ||| 好吧。")]]
    sse_events(api.post(f"/api/talks/{t['id']}/chat", json={"message": "Please. She was everything to me."}))
    api.llm.told = ["wound", "herb"]                      # herb needs trust 6: it was never offered, so it is not filed
    api.llm.rounds = [[chunk("One narrow thrust, ringed by nine thin scores. ||| 一道窄窄的刺伤，周围九道细痕。")]]
    evs = sse_events(api.post(f"/api/talks/{t['id']}/chat", json={"message": "What did you see?"}))
    assert [e["clue"]["id"] for e in evs if e["type"] == "clue"] == ["wound"]
    s = api.get("/api/game").json()["game"]
    assert [c["id"] for c in s["found"]] == ["official", "wound"]
    assert next(c for c in s["cast"] if c["key"] == "bai")["clues_told"] == 1
    # the facts were offered to the model in the system turn, not in its history
    offered = api.llm.requests[-2]["messages"]
    assert any("Not a fall" in m["content"] for m in offered if m["role"] == "system")


def test_stray_markup_never_reaches_the_page_or_the_history(api):
    start(api)
    t = api.post("/api/talks", json={"npc": "xie"}).json()
    api.llm.rounds = [[chunk('Hm. <reveal_clue id="footsteps" /> I heard nothing. ||| 嗯。<adjust_trust delta="1"/>我什么也没听见。')]]
    evs = sse_events(api.post(f"/api/talks/{t['id']}/chat", json={"message": "Hello"}))
    done = [e for e in evs if e["type"] == "done"][0]["text"]
    assert "<" not in done and "heard nothing" in done and "没听见" in done


def test_the_hidden_champion_appears_only_after_someone_points_to_him(api):
    start(api)
    assert "lu" not in {c["key"] for c in api.get("/api/game").json()["game"]["cast"]}
    give(api, "lu_lead")
    assert "lu" in {c["key"] for c in api.get("/api/game").json()["game"]["cast"]}
    assert api.post("/api/talks", json={"npc": "lu"}).status_code == 200


def test_accusing_and_the_ending(api):
    start(api)
    give(api, "wound", "herb", "charm")
    r = api.post("/api/accuse", json={"suspect": "leng", "evidence": ["wound"]}).json()
    assert r["verdict"] == "wrong" and r["attempts"] == 2 and r["stage"] == "playing"
    r = api.post("/api/accuse", json={"suspect": "yun", "evidence": ["wound"]}).json()
    assert r["verdict"] == "unproven" and r["attempts"] == 1
    assert api.post("/api/ending", json={"fate": "mercy"}).status_code == 409           # not accused yet
    r = api.post("/api/accuse", json={"suspect": "yun", "evidence": ["wound", "herb", "charm"]}).json()
    assert r["verdict"] == "correct" and r["stage"] == "accused" and r["attempts"] == 1
    assert api.post("/api/ending", json={"fate": "nonsense"}).status_code == 400
    g = api.post("/api/ending", json={"fate": "mercy"}).json()["game"]
    assert g["stage"] == "solved" and bilingual.is_pair(g["ending"]) and "It was I" in g["ending"]


def test_the_ending_falls_back_to_written_text_when_the_ai_fails(api, monkeypatch):
    start(api)
    with db.session() as conn:
        g = db.get_game(conn, api.cookies.get("vid"))
        g.update(stage="accused")
        db.save_game(conn, g)

    def broken():
        raise main.HTTPException(503, "no ai")
    monkeypatch.setattr(main, "llm", broken)
    g = api.post("/api/ending", json={"fate": "justice"}).json()["game"]
    assert g["stage"] == "solved" and "Liu Ruyan" in g["ending"] and bilingual.is_pair(g["ending"])


def test_three_wrong_accusations_end_the_case_and_reveal_the_truth(api):
    start(api)
    for _ in range(3):
        r = api.post("/api/accuse", json={"suspect": "su", "evidence": []}).json()
    assert r["stage"] == "lost" and r["attempts"] == 0 and "Yun Wuya" in r["truth"]
    assert api.post("/api/accuse", json={"suspect": "yun", "evidence": []}).status_code == 409
    s = api.get("/api/game").json()["game"]
    assert s["stage"] == "lost" and "Yun Wuya" in s["truth"]
    assert api.post("/api/game/reset").status_code == 200 and api.get("/api/game").json() == {"game": None}


def test_one_visitors_case_is_invisible_to_another(api):
    start(api)
    other = TestClient(main.app)
    assert other.get("/api/game").json() == {"game": None}
    assert other.post("/api/accuse", json={"suspect": "yun", "evidence": []}).status_code == 409
    t = api.post("/api/talks", json={"npc": "xie"}).json()
    assert other.post(f"/api/talks/{t['id']}/chat", json={"message": "hi"}).status_code == 404
