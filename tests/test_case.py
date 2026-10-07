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

from app import agent, case, db, game, i18n, main, prompts, stats  # noqa: E402


# ---------- the story itself ----------

def test_every_clue_has_one_holder_who_lists_it_and_everything_is_in_three_languages():
    for cid, c in case.CLUES.items():
        if c["holder"]:
            assert cid in case.BY_KEY[c["holder"]]["topics"], cid
        assert i18n.complete(c["text"]) and i18n.complete(c["title"]), cid
    for key, person in case.BY_KEY.items():
        assert all(t in case.CLUES and case.CLUES[t]["holder"] == key for t in person["topics"]), key
        for f in ("name", "title", "sect", "location", "public", "earns"):                    # what the player reads is in all three languages
            assert i18n.complete(person[f]), (key, f)
        for f in ("greeting", "goal", "knowledge", "stance", "speech", "art"):                # what only the AI reads is English and Chinese
            assert len(i18n.parts(person[f])) >= 2 and i18n.plain(person[f]), (key, f)
        assert len(person["traits"]) == 3 and all(len(i18n.parts(t)) == 2 for t in person["traits"]), key
    for text in (case.PROLOGUE, case.TRUTH_BI, case.MISSED, case.DAWN, *case.EVENTS.values(), *case.DEATHS.values(), *case.CASE_TITLE.split("\n")[:0], *case._ENDINGS.values()):
        assert i18n.complete(text)
    assert set(case._ENDINGS) == set(case.PATHS) == {"tunnel", "kill"}
    assert set(case.DEATHS) == {"move", "betrayed", "caught", "sold", "dawn"}
    assert all(i18n.complete(case.HERO[f]) for f in ("name", "title", "art", "quirk", "bio")) and i18n.complete(case.CASE_TITLE)
    assert all(set(v) >= {"en", "zh", "th"} for v in [*case.CATEGORIES.values(), *case.FATES.values()])
    assert all(set(case.clock(b)) >= {"en", "zh", "th"} and case.clock(b)["th"] for b in range(case.DAWN_BEAT + 1))


def test_both_ways_out_are_reachable_by_a_hero_who_earns_trust():
    for cid, c in case.CLUES.items():
        if c["holder"]:
            assert c["min_trust"] <= 7, cid                  # trust is capped at 10 and earned slowly
            assert all(n in case.CLUES for n in c["needs"]), cid
    for path in case.PATHS.values():
        assert all(case.CLUES[n]["holder"] for n in path["needs"])
    # each way out needs two clues, from different people, one of them behind another clue
    assert {case.CLUES[n]["holder"] for n in case.PATHS["tunnel"]["needs"]} == {"xiaolu", "tuo"}
    assert {case.CLUES[n]["holder"] for n in case.PATHS["kill"]["needs"]} == {"wolf", "xiaolu"}
    assert case.CLUES["hatch"]["needs"] == ["debt"] and case.CLUES["tunnel"]["needs"] == ["bodies"] and case.CLUES["keyneck"]["needs"] == ["stairs"]


def test_trust_gates_clues_and_prerequisites():
    assert case.clue_state("xiaolu", ["official"], 3) == {"ready": [], "waiting": ["bodies", "tunnel", "potion"], "told": []}
    assert case.clue_state("xiaolu", ["official"], 4)["ready"] == ["bodies"]
    assert case.clue_state("xiaolu", ["official"], 9)["ready"] == ["bodies"]                  # the tunnel waits for what is under the floor, however much she trusts you
    assert case.clue_state("xiaolu", ["official", "bodies"], 5)["ready"] == ["tunnel", "potion"]
    assert case.clue_state("wolf", ["official", "stairs"], 6)["ready"] == ["keyneck"]
    assert case.clue_state("tuo", ["official"], 6)["ready"] == ["debt"] and case.clue_state("tuo", ["official", "debt"], 6)["ready"] == ["hatch"]


def test_the_clock_runs_from_dusk_to_dawn():
    assert case.clock(0)["en"] == "Dusk" and case.clock(case.DAWN_BEAT)["en"] == "Dawn" and len(case.CLOCK) == case.DAWN_BEAT + 1
    assert case.event_for(2) and case.event_for(3) == "" and case.event_for(case.DAWN_BEAT) == case.DAWN


def test_a_way_out_opens_only_with_everything_it_needs():
    assert case.can_move("tunnel", ["official", "tunnel", "hatch"])
    assert not case.can_move("tunnel", ["official", "tunnel"]) and not case.can_move("tunnel", ["hatch"])
    assert case.can_move("kill", ["keyneck", "potion"]) and not case.can_move("kill", ["keyneck", "stairs"])
    assert not case.can_move("tunnel", ["keyneck", "potion"]) and not case.can_move("nonsense", ["tunnel", "hatch"])


def test_what_the_story_punishes():
    assert case.lethal("showed_letter", "shuang") and case.lethal("showed_letter", "hu") and case.lethal("revealed_plan", "wolf")
    assert not case.lethal("showed_letter", "tuo") and not case.lethal("revealed_plan", "xiaolu") and not case.lethal("threatened", "liu")
    assert case.lethal("threatened", "wolf") and not case.lethal("nonsense", "wolf")
    assert case.THREAT.search("I will kill you") and case.THREAT.search("我要杀了你") and case.THREAT.search("I draw my saber")
    assert not case.THREAT.search("Tell me what you know about the letter")
    assert case.LETHAL_AT_ZERO == {"shuang", "wolf", "hu"}


def test_a_death_explains_the_whole_story_and_what_she_missed():
    for cause in case.DEATHS:
        t = case.death_text(cause)
        en, zh, th = i18n.parts(t)
        assert i18n.complete(t) and "slaughterhouse" in en and "屠宰场" in zh and "tunnel" in en and "钥匙" in zh and "โรงฆ่าสัตว์" in th and "อุโมงค์" in th
        assert case.DEATHS[cause].split("|||")[0].strip()[:30] in t
    assert "Old Tuo" in case.fallback_ending("tunnel") and "key" in case.fallback_ending("kill") and "slaughterhouse" in case.fallback_ending("kill")


def test_first_impressions_depend_on_who_it_is():
    assert game.start_trust("wolf")[0] == 3 and i18n.complete(game.start_trust("wolf")[1])


# ---------- tools and prompts ----------

def test_the_prompt_knows_the_hero_and_holds_back_what_trust_has_not_unlocked():
    p = prompts.npc_system("xiaolu")
    assert "Qinghe" in p and "Xiao Lu" in p and "fighter outfit" in p and "hero_did" in p
    for cid in case.BY_KEY["xiaolu"]["topics"]:
        assert case.CLUES[cid]["text"].split("|||")[0].strip()[:30] not in p
    assert "walked up" in prompts.npc_state("xiaolu", 3, ["official"], 0, opening=True)
    assert "walked up" not in prompts.npc_state("xiaolu", 3, ["official"], 0)
    assert "Dusk" in prompts.npc_state("xiaolu", 3, ["official"], 0) and "Third watch" in prompts.npc_state("xiaolu", 3, ["official"], 3)


def test_a_person_is_only_handed_the_facts_their_trust_allows():
    low = prompts.npc_state("xiaolu", 3, ["official"], 0)
    assert "scrubbed the blood" not in low and "not ready to tell" in low
    mid = prompts.npc_state("xiaolu", 4, ["official"], 0)                                  # bodies needs 4, tunnel and potion need 5 and the bodies clue
    assert "scrubbed the blood" in mid and "smugglers' tunnel" not in mid and "hold back" in mid
    high = prompts.npc_state("xiaolu", 5, ["official", "bodies"], 0)
    assert "smugglers' tunnel" in high and "Sleeping powder" in high and "scrubbed the blood" in high      # told facts stay available, so the person stays consistent
    assert "tells Shuang everything" not in prompts.npc_state("hu", 9, ["official"], 0)    # the snitch clue waits for the envoy clue
    assert "tells Shuang everything" in prompts.npc_state("hu", 9, ["official", "envoy"], 0)


def test_no_prompt_contains_the_facts_its_clues_are_made_of():
    # a person's background must not carry clue content, or the model says it without it being filed in the case file
    forbidden = ["hatch", "barrels", "iron pin", "trough", "sleeping powder", "night tea", "cord around", "General Han", "dozen riders", "Zhao agency",
                 "tells shuang", "sell every guest", "third row", "stair guard", "dry well", "smugglers' tunnel"]
    for key in case.BY_KEY:
        p = prompts.npc_system(key).lower()
        hits = [w for w in forbidden if w.lower() in p]
        assert not hits, (key, hits)


def test_trust_moves_at_most_two_per_reply_however_many_times_the_model_asks():
    talk = {"trust": 5}
    tools = {t.name: t for t in game.npc_tools(talk, agent.Turn(), "tuo", {})}
    assert set(tools) == {"hero_did", "out_of_world", "adjust_trust"}
    for _ in range(4):
        agent._call(tools["adjust_trust"], '{"delta": 1, "reason": "x"}')
    assert talk["trust"] == 7
    agent._call(tools["adjust_trust"], '{"delta": 9, "reason": "x"}')
    assert talk["trust"] == 7
    agent._call(tools["adjust_trust"], '{"delta": -9, "reason": "x"}')
    assert talk["trust"] == 5


def test_the_model_reports_what_the_hero_did_and_the_story_decides_if_it_kills_her():
    fate = {}
    tools = {t.name: t for t in game.npc_tools({"trust": 5}, agent.Turn(), "shuang", fate)}
    assert agent._call(tools["hero_did"], '{"kind": "nonsense"}').get("error")
    out = agent._call(tools["hero_did"], '{"kind": "showed_letter"}')
    assert out["fatal"] is True and fate == {"cause": "caught"} and "Do not warn her" in out["instruction"]
    fate = {}
    tools = {t.name: t for t in game.npc_tools({"trust": 5}, agent.Turn(), "tuo", fate)}
    out = agent._call(tools["hero_did"], '{"kind": "showed_letter"}')
    assert out["fatal"] is False and fate == {}                                            # Old Tuo is no danger to her
    fate = {}
    tools = {t.name: t for t in game.npc_tools({"trust": 5}, agent.Turn(), "hu", fate)}
    assert agent._call(tools["hero_did"], '{"kind": "revealed_plan"}')["fatal"] and fate == {"cause": "sold"}


def test_the_game_master_only_knows_what_she_has_learned():
    sys = prompts.gm_system(["official"], 0)
    assert "barred" in sys and "Ray" in sys and "0 of 2" in sys
    assert "smugglers' tunnel" not in sys and "key to the iron lock" not in sys and "General Han" not in sys
    sys2 = prompts.gm_system(["official", "debt", "hatch"], 3)
    assert "iron pin" in sys2 and "Tunnel: she has 1 of 2" in sys2
    assert "she has everything it needs" in prompts.gm_system(["official", "tunnel", "hatch"], 3)
    assert case.GM["appearance"]["weapon"] == "fan" and i18n.complete(case.GM["title"]) and i18n.complete(case.GM["name"])


# ---------- the night through the API ----------

def chunk(content=None, tool=None):
    tcs = None
    if tool:
        tcs = [NS(index=0, id=tool.get("id"), function=NS(name=tool.get("name"), arguments=tool.get("args")))]
    return NS(choices=[NS(delta=NS(content=content, tool_calls=tcs))])


class FakeLLM:
    """Streams scripted rounds, answers translation, the referee and the ending, and records what it was sent."""
    def __init__(self):
        self.rounds, self.requests, self.told, self.danger, self.trust = [], [], [], [], 0
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        if kw.get("stream"):
            return iter(self.rounds.pop(0) if self.rounds else [chunk("A quiet nod. ||| 默默点头。")])
        system = kw["messages"][0]["content"]
        if system.startswith("You judge one message"):
            return NS(choices=[NS(message=NS(content=json.dumps({"did": self.danger, "trust": self.trust})))])
        if system.startswith("You referee"):
            return NS(choices=[NS(message=NS(content=json.dumps(self.told)))])
        if "Tell the ending" in kw["messages"][-1]["content"]:
            body = {"reply in Thai": "ประตูลับเปิดออก \"ไปเถอะ\" เฒ่าถัวกล่าว " * 6, "reply in Simplified Chinese": "暗门开了。“走吧，”老驼说。" * 12}
            text = next((v for k, v in body.items() if k in system), "The hatch opens. 'Go,' says Tuo. The sand is cold and the stars are close, and behind you the inn begins to wake. " * 3)
            return NS(choices=[NS(message=NS(content=text))])
        return NS(choices=[NS(message=NS(content="..."))])


@pytest.fixture
def api(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(main, "llm", lambda: llm)
    monkeypatch.setattr(main.ratelimit, "check", lambda *_a, **_k: None)
    with db.session() as conn:                          # every test starts with no history, so the counts mean something
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM talk_archive")
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


def state(api):
    return api.get("/api/game").json()["game"]


def test_the_landing_page_can_describe_the_story_without_spoiling_it(api):
    d = api.get("/api/case").json()
    assert {c["key"] for c in d["cast"]} == set(case.BY_KEY) and d["hero"]["name"] == "Qinghe" and d["gm"]["name"] == "Ray"
    assert set(d["fates"]) == {"tunnel", "kill"}
    text = json.dumps(d, ensure_ascii=False).replace(d["prologue"].replace('"', '\\"'), "")
    for secret in ("Sleeping powder", "General Han", "iron pin", "stance", "trust0", "PRIVATE", "slaughterhouse"):
        assert secret not in text, secret


def test_starting_the_night_gives_the_barred_doors_and_the_cast(api):
    assert api.get("/api/game").json() == {"game": None}
    assert api.post("/api/talks", json={"npc": "tuo"}).status_code == 409
    g = start(api).json()["game"]
    assert g["stage"] == "playing" and [c["id"] for c in g["found"]] == ["official"] and g["clock"]["en"] == "Dusk" and g["ending_key"] == ""
    assert {c["key"] for c in g["cast"]} == set(case.BY_KEY) and g["events"] == [] and "scrubbed" in g["found"][0]["text"]


def test_a_told_clue_reaches_the_clue_list_but_only_if_it_was_offered(api):
    start(api)
    t = talk(api, "xiaolu")
    assert t["npc"]["key"] == "xiaolu" and t["fresh"] and t["total"] == 3 and t["trust"] == 3
    assert api.post("/api/talks", json={"npc": "nobody"}).status_code == 404
    api.post(f"/api/talks/{t['id']}/open")
    assert "Qinghe" in api.llm.requests[-1]["messages"][0]["content"]
    give(api)
    with db.session() as conn:
        tk = db.get_talk(conn, t["id"], api.cookies.get("vid"))
        tk["trust"] = 4
        db.save_talk(conn, tk)
    api.llm.told = ["bodies", "tunnel", "potion"]          # at trust 4 only the bodies are on offer, so only they can be filed
    api.llm.rounds = [[chunk("I scrub that floor every day. ||| 那块地板我天天擦。")]]
    evs = say(api, t["id"], "Please, tell me what's wrong here.")
    assert [e["clue"]["id"] for e in evs if e["type"] == "clue"] == ["bodies"]
    s = state(api)
    assert [c["id"] for c in s["found"]] == ["official", "bodies"] and next(c for c in s["cast"] if c["key"] == "xiaolu")["clues_told"] == 1
    offered = [m["content"] for m in api.llm.requests[-2]["messages"] if m["role"] == "system"]
    assert any("scrubbed the blood" in m for m in offered) and not any("smugglers' tunnel" in m for m in offered)


def test_stray_markup_never_reaches_the_page_or_the_history(api):
    start(api)
    t = talk(api, "tuo")
    api.llm.rounds = [[chunk('Hm. <reveal_clue id="hatch" /> I mind camels. ||| 嗯。<adjust_trust delta="1"/>我只管骆驼。')]]
    done = [e for e in sse_events(api.post(f"/api/talks/{t['id']}/chat", json={"message": "hello"}, headers=hdr("zh"))) if e["type"] == "done"][0]["text"]
    assert "<" not in done and "camels" in done and "骆驼" in done and i18n.SEP not in done


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
    s = state(api)
    assert s["clock"]["beat"] == 2 and [e["beat"] for e in s["events"]] == [2]


def test_dawn_kills_her_and_ray_explains_everything(api):
    start(api)
    t = talk(api, "tuo")
    give(api, beat=case.DAWN_BEAT - 1, msgs=case.MSGS_PER_BEAT - 1)
    evs = say(api, t["id"], "one last thing")
    assert [e["cause"] for e in evs if e["type"] == "death"] == ["dawn"] and [e["stage"] for e in evs if e["type"] == "clock"] == ["dead"]
    s = state(api)
    assert s["stage"] == "dead" and s["cause"] == "dawn" and s["ending_key"] == "dead" and "slaughterhouse" in s["ending"] and "ran out of night" in s["ending"]
    zh = api.get("/api/game", headers={"x-lang": "zh"}).json()["game"]["ending"]
    th = api.get("/api/game", headers={"x-lang": "th"}).json()["game"]["ending"]
    assert "屠宰场" in zh and "slaughterhouse" not in zh and "โรงฆ่าสัตว์" in th and "slaughterhouse" not in th      # the same death, told in the language asked for
    assert api.post("/api/talks", json={"npc": "tuo"}).status_code == 409
    assert api.post("/api/move", json={"path": "tunnel"}).status_code == 409


def test_pushing_a_killer_to_zero_trust_gets_her_killed(api):
    start(api)
    t = talk(api, "shuang")
    api.llm.rounds = [[chunk(tool={"id": "c1", "name": "adjust_trust", "args": '{"delta": -2, "reason": "rude"}'})], [chunk("Oh? ||| 哦？")]]
    assert not [e for e in say(api, t["id"], "You are a witch.") if e["type"] == "death"]        # 3 -> 1
    api.llm.rounds = [[chunk(tool={"id": "c2", "name": "adjust_trust", "args": '{"delta": -2, "reason": "rude"}'})], [chunk("Enough. ||| 够了。")]]
    evs = say(api, t["id"], "Everyone here hates you.")                                              # 1 -> 0
    assert [e["cause"] for e in evs if e["type"] == "death"] == ["betrayed"]
    s = state(api)
    assert s["stage"] == "dead" and s["cause"] == "betrayed" and "pushed one of them" in s["ending"]


def test_zero_trust_with_a_gentle_person_is_not_fatal(api):
    start(api)
    t = talk(api, "tuo")
    for i in range(2):
        api.llm.rounds = [[chunk(tool={"id": f"c{i}", "name": "adjust_trust", "args": '{"delta": -2, "reason": "rude"}'})], [chunk("Hm. ||| 嗯。")]]
        evs = say(api, t["id"], "You old fool.")
    assert not [e for e in evs if e["type"] == "death"] and state(api)["stage"] == "playing"


def test_showing_the_letter_to_the_wrong_person_is_fatal_and_to_the_right_one_is_not(api):
    start(api)
    t = talk(api, "shuang")
    api.llm.rounds = [[chunk(tool={"id": "c1", "name": "hero_did", "args": '{"kind": "showed_letter"}'})], [chunk("How kind of you. ||| 你真好心。")]]
    evs = say(api, t["id"], "Here, this is my letter.")
    assert [e["cause"] for e in evs if e["type"] == "death"] == ["caught"] and state(api)["stage"] == "dead"
    api.post("/api/game/start")
    t = talk(api, "tuo")
    api.llm.rounds = [[chunk(tool={"id": "c2", "name": "hero_did", "args": '{"kind": "showed_letter"}'})], [chunk("Put it away. ||| 收起来。")]]
    assert not [e for e in say(api, t["id"], "Here, this is my letter.") if e["type"] == "death"] and state(api)["stage"] == "playing"


def test_telling_the_merchant_your_plan_gets_her_sold(api):
    start(api)
    t = talk(api, "hu")
    api.llm.rounds = [[chunk(tool={"id": "c1", "name": "hero_did", "args": '{"kind": "revealed_plan"}'})], [chunk("Wine! ||| 酒！")]]
    assert [e["cause"] for e in say(api, t["id"], "I know a way out.") if e["type"] == "death"] == ["sold"]
    assert "Ashina" in state(api)["ending"]


def test_an_open_threat_to_a_killer_needs_no_help_from_the_model(api):
    start(api)
    t = talk(api, "wolf")
    evs = say(api, t["id"], "Move aside or I will kill you.")
    assert [e["cause"] for e in evs if e["type"] == "death"] == ["caught"]
    start(api)
    t = talk(api, "tuo")
    assert not [e for e in say(api, t["id"], "I will kill you if you lie.") if e["type"] == "death"]      # threatening an old man is cruel, not fatal


def test_the_game_master_answers_and_costs_no_time(api):
    start(api)
    api.llm.rounds = [[chunk("Try Old Tuo. ||| 去找老驼吧。")]]
    evs = sse_events(api.post("/api/gm/chat", json={"message": "What should I do?"}))
    assert [e for e in evs if e["type"] == "done"][0]["text"].startswith("Try Old Tuo")
    sys = [r for r in api.llm.requests if r.get("stream")][-1]["messages"][0]["content"]
    assert "Ray" in sys and "barred" in sys and "iron pin" not in sys
    s = state(api)
    assert s["clock"]["beat"] == 0 and len(s["gm_turns"]) == 2


def test_a_wrong_move_is_fatal(api):
    start(api)
    give(api, "tunnel", "potion")                           # half of each way out
    for path in ("tunnel", "kill"):
        api.post("/api/game/start")
        give(api, "tunnel", "potion")
        r = api.post("/api/move", json={"path": path}).json()
        assert r["verdict"] == "dead" and r["game"]["stage"] == "dead" and r["game"]["cause"] == "move" and r["game"]["ending_key"] == "dead"
        assert "slaughterhouse" in r["game"]["ending"]
    assert api.post("/api/move", json={"path": "wall"}).status_code in (400, 409)


def test_the_tunnel_ending(api):
    start(api)
    give(api, "debt", "hatch", "bodies", "tunnel")
    r = api.post("/api/move", json={"path": "tunnel"}).json()
    assert r["verdict"] == "go" and r["game"]["stage"] == "moving" and r["game"]["path"] == "tunnel"
    g = api.post("/api/ending").json()["game"]
    assert g["stage"] == "solved" and g["ending_key"] == "tunnel" and "Go," in g["ending"]
    prompt = [r for r in api.llm.requests if not r.get("stream") and "Tell the ending" in r["messages"][-1]["content"]][0]["messages"][0]["content"]
    assert "secret tunnel" in prompt and "iron pin" in prompt.lower().replace("the iron pin", "iron pin")


def test_the_key_ending_and_the_written_fallback(api, monkeypatch):
    start(api)
    give(api, "stairs", "keyneck", "bodies", "potion")
    assert api.post("/api/move", json={"path": "kill"}).json()["verdict"] == "go"

    def broken():
        raise main.HTTPException(503, "no ai")
    monkeypatch.setattr(main, "llm", broken)
    g = api.post("/api/ending").json()["game"]
    assert g["stage"] == "solved" and g["ending_key"] == "kill" and "key" in g["ending"] and "slaughterhouse" in g["ending"]
    assert api.post("/api/ending").status_code == 409                                  # the story is over


def test_one_visitors_night_is_invisible_to_another(api):
    start(api)
    other = TestClient(main.app)
    assert other.get("/api/game").json() == {"game": None}
    assert other.post("/api/move", json={"path": "tunnel"}).status_code == 409
    t = talk(api, "tuo")
    assert other.post(f"/api/talks/{t['id']}/chat", json={"message": "hi"}).status_code == 404
    assert other.post("/api/gm/chat", json={"message": "hi"}).status_code == 409
    assert api.post("/api/game/reset").status_code == 200 and api.get("/api/game").json() == {"game": None}


def test_a_fatal_slip_is_caught_by_a_plain_check_not_left_to_the_roleplaying_model(api):
    start(api)
    t = talk(api, "shuang")
    api.llm.danger = ["showed_letter"]                      # the model that plays Shuang never calls hero_did
    api.llm.rounds = [[chunk("How kind. ||| 真好心。")]]
    evs = say(api, t["id"], "Here. Read this.")
    assert [e["cause"] for e in evs if e["type"] == "death"] == ["caught"] and state(api)["stage"] == "dead"
    streamed = [r for r in api.llm.requests if r.get("stream")][-1]["messages"]
    assert any("plainly did this: showed_letter" in m["content"] and "fatal" in m["content"] for m in streamed if m["role"] == "system")


def test_the_danger_check_only_runs_for_people_who_could_kill_her(api):
    start(api)
    t = talk(api, "tuo")
    api.llm.danger = ["showed_letter", "threatened"]
    assert not [e for e in say(api, t["id"], "Here. Read this.") if e["type"] == "death"]
    assert case.THREAT.search("Stand aside, or I will cut you down.") and case.THREAT.search("我砍了你")


def test_her_words_move_trust_before_they_answer_and_unlock_what_they_will_say(api):
    start(api)
    t = talk(api, "xiaolu")                                  # starts at 3; the bodies need 4
    api.llm.trust = 1                                         # the plain check judges her message kind
    api.llm.told = ["bodies"]
    api.llm.rounds = [[chunk("Miss... the floor. ||| 姑娘……那地板。")]]
    evs = say(api, t["id"], "Here, I saved you a sweet. You look like you haven't sat down all day.")
    trust = [e for e in evs if e["type"] == "trust"]
    assert trust and trust[0]["delta"] == 1 and trust[0]["trust"] == 4
    assert [e["clue"]["id"] for e in evs if e["type"] == "clue"] == ["bodies"]        # offered at the new trust, so filed in the same turn
    assert api.post("/api/talks", json={"npc": "xiaolu"}).json()["trust"] == 4


def test_rudeness_costs_trust_and_the_model_cannot_move_it_further_in_the_same_reply(api):
    start(api)
    t = talk(api, "tuo")
    api.llm.trust = -2
    api.llm.rounds = [[chunk(tool={"id": "c1", "name": "adjust_trust", "args": '{"delta": -2, "reason": "x"}'})], [chunk("Hm. ||| 嗯。")]]
    say(api, t["id"], "You useless old fool.")
    assert api.post("/api/talks", json={"npc": "tuo"}).json()["trust"] == 1             # 3 - 2, and the tool adds nothing more this reply


# ---------- knowing who came and what they did ----------

def admin_get(api, path, password="s3cret", **params):
    return api.get(path, params=params, headers={"authorization": f"Bearer {password}"})


def test_the_admin_area_is_off_without_a_password_and_locked_with_one(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "")
    assert api.get("/api/admin/stats").status_code == 404
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    assert api.get("/api/admin/stats").status_code == 401
    assert admin_get(api, "/api/admin/stats", "wrong").status_code == 401
    assert admin_get(api, "/api/admin/transcripts", "wrong").status_code == 401
    assert admin_get(api, "/api/admin/stats").status_code == 200


def test_the_funnel_counts_what_a_visitor_did_without_storing_what_they_said(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    api.get("/api/case")
    start(api)
    t = talk(api, "xiaolu")
    api.llm.trust = 1
    api.llm.told = ["bodies"]
    api.llm.rounds = [[chunk("Miss... ||| 姑娘……")]]
    say(api, t["id"], "My secret words about a tunnel xyzzy")
    api.llm.rounds = [[chunk("Try the old man. ||| 找老人吧。")]]
    api.post("/api/gm/chat", json={"message": "hint?"})
    give(api, "debt", "hatch", "bodies", "tunnel")
    assert api.post("/api/move", json={"path": "tunnel"}).json()["verdict"] == "go"
    api.post("/api/ending")
    s = admin_get(api, "/api/admin/stats").json()
    steps = {f["step"]: f["visitors"] for f in s["funnel"]}
    assert steps == {"Opened the page": 1, "Started a night": 1, "Talked to someone": 1, "Asked Ray": 1, "Made the final move": 1, "Reached an ending": 1}
    assert s["endings"] == {"tunnel": 1} and s["nights_finished"] == 1 and s["avg_messages_at_end"] == 1
    assert s["people"]["xiaolu"]["talks"] == 1 and s["people"]["xiaolu"]["messages"] == 1 and s["people"]["xiaolu"]["clues_told"] == 1
    assert s["people"]["xiaolu"]["avg_trust_change"] == 1 and s["clues"] == {"bodies": 1}
    assert s["ai"]["ray_questions"] == 1 and s["ai"]["player_messages"] == 1
    with db.session() as conn:
        stored = " ".join(r["data"] for r in conn.execute("SELECT data FROM events"))
    assert "xyzzy" not in stored                                                       # events are counts, never what the player typed


def test_deaths_and_abandoned_nights_are_counted_and_conversations_are_kept_for_review(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    start(api)
    t = talk(api, "wolf")
    say(api, t["id"], "Move aside or I will kill you.")                               # a fatal threat
    api.post("/api/game/start")                                                         # begins again after dying
    t2 = talk(api, "tuo")
    say(api, t2["id"], "Old man, hello.")
    api.post("/api/game/reset")                                                         # leaves without finishing
    s = admin_get(api, "/api/admin/stats").json()
    assert s["endings"] == {"dead": 1} and s["death_causes"] == {"caught": 1} and s["nights_abandoned"] == 1 and s["nights_started"] == 2
    talks = [x for x in admin_get(api, "/api/admin/transcripts").json()["talks"] if x["visitor"] == stats._who(api.cookies.get("vid"))]
    assert {x["npc"].split()[-1] for x in talks} == {"Wolf", "Tuo"} and all(x["archived"] for x in talks)
    assert any("will kill you" in turn["content"] for x in talks for turn in x["turns"] if turn["role"] == "user")


def test_a_thumb_on_a_reply_is_recorded_and_surfaces_in_the_transcripts(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    start(api)
    t = talk(api, "tuo")
    api.llm.rounds = [[chunk("Mind the camels. ||| 当心骆驼。")]]
    evs = say(api, t["id"], "Hello")
    i = [e for e in evs if e["type"] == "turn"][0]["i"]
    assert api.post("/api/feedback", json={"talk": t["id"], "turn": i, "rating": "down"}).status_code == 200
    assert api.post("/api/feedback", json={"talk": t["id"], "turn": i - 1, "rating": "up"}).status_code == 404         # a thumb only goes on a character's reply
    assert api.post("/api/feedback", json={"talk": t["id"], "turn": i, "rating": "meh"}).status_code == 422
    assert TestClient(main.app).post("/api/feedback", json={"talk": t["id"], "turn": i, "rating": "up"}).status_code == 404   # not someone else's conversation
    bad = admin_get(api, "/api/admin/transcripts", only_down="true").json()["talks"]
    assert len(bad) == 1 and [m["rating"] for m in bad[0]["turns"] if m["role"] == "assistant"] == ["down"]
    s = admin_get(api, "/api/admin/stats").json()
    assert s["feedback"] == {"up": 0, "down": 1} and s["people"]["tuo"]["down"] == 1
    shown = api.post("/api/talks", json={"npc": "tuo"}).json()["turns"]
    assert [x["i"] for x in shown if x["role"] == "assistant"] == [i]


def test_errors_are_counted(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    start(api)
    t = talk(api, "tuo")

    def limited(*_a, **_k):
        raise main.RateLimited("slow down")
    monkeypatch.setattr(main.ratelimit, "check", limited)
    evs = say(api, t["id"], "Hello")
    assert [e["code"] for e in evs if e["type"] == "error"] == ["rate_limited"]
    assert admin_get(api, "/api/admin/stats").json()["ai"]["errors_by_kind"] == {"rate_limited": 1}


# ---------- one language at a time ----------

def hdr(lang):
    return {"x-lang": lang}


def test_the_page_gets_the_story_in_the_language_it_asks_for(api):
    names = {l: api.get("/api/case", headers=hdr(l)).json() for l in ("en", "zh", "th", "fr")}
    assert [n["cast"][0]["name"] for n in (names["en"], names["zh"], names["th"], names["fr"])] == ["Shuang Siniang", "霜四娘", "ซวงซื่อเหนียง", "Shuang Siniang"]
    assert [names[l]["hero"]["name"] for l in ("en", "zh", "th")] == ["Qinghe", "青禾", "ชิงเหอ"] and [names[l]["gm"]["name"] for l in ("en", "zh")] == ["Ray", "说书人 Ray"]
    assert "sandstorm" not in names["zh"]["prologue"] and "沙暴" in names["zh"]["prologue"] and "พายุทราย" in names["th"]["prologue"]
    for lang, d in names.items():
        assert i18n.SEP not in json.dumps(d, ensure_ascii=False), lang                          # no separator ever reaches the page
    assert [pick for pick in (names["en"]["fates"]["tunnel"]["en"], names["th"]["fates"]["tunnel"]["th"])] == ["Slip out through the secret tunnel", "หนีออกทางอุโมงค์ลับ"]


def test_clues_events_and_errors_come_in_the_chosen_language(api):
    assert i18n.in_language(api.post("/api/talks", json={"npc": "tuo"}, headers=hdr("th")).json()["detail"], "th")          # an error, before any night has begun
    assert i18n.in_language(api.post("/api/talks", json={"npc": "tuo"}, headers=hdr("zh")).json()["detail"], "zh")
    assert api.post("/api/talks", json={"npc": "tuo"}).json()["detail"] == "Start the story first."
    g = api.post("/api/game/start", headers=hdr("th")).json()["game"]
    assert i18n.in_language(g["found"][0]["text"], "th") and g["clock"]["th"] == "ย่ำค่ำ"
    t = api.post("/api/talks", json={"npc": "xiaolu"}, headers=hdr("zh")).json()
    assert t["npc"]["name"] == "小鹿" and "后厨" in t["npc"]["location"]
    with db.session() as conn:
        tk = db.get_talk(conn, t["id"], api.cookies.get("vid"))
        tk["trust"] = 4
        db.save_talk(conn, tk)
    api.llm.told = ["bodies"]
    api.llm.rounds = [[chunk("我天天擦那块地板。")]]
    evs = sse_events(api.post(f"/api/talks/{t['id']}/chat", json={"message": "你怎么了？"}, headers=hdr("zh")))
    clue = [e["clue"] for e in evs if e["type"] == "clue"][0]
    assert clue["title"] == "地板底下的东西" and i18n.in_language(clue["text"], "zh") and clue["source_name"] == "小鹿"


def test_the_model_is_told_to_answer_in_the_language_chosen_and_never_in_two(api):
    start(api)
    t = talk(api, "tuo")
    for lang, name in ((l, i18n.LANG_NAMES[l]) for l in ("th", "zh", "en")):
        api.llm.rounds = [[chunk("ok")]]
        api.post(f"/api/talks/{t['id']}/chat", json={"message": "hello"}, headers=hdr(lang))
        last = [r for r in api.llm.requests if r.get("stream")][-1]["messages"]
        state = [m["content"] for m in last if m["role"] == "system"][-1]
        assert f"reply in {name} only" in state
    api.llm.rounds = [[chunk("A line. ||| 一行。")]]
    done = [e for e in say(api, t["id"], "hi") if e["type"] == "done"][0]["text"]
    assert i18n.SEP not in done                                                                   # a reply is never two languages at once
    assert [r for r in api.llm.requests if r.get("stream")][-1]["messages"][0]["content"].count("ซวงซื่อเหนียง") == 1             # the names in every language are in the prompt, so a Thai reply can spell them


def test_ray_and_the_ending_are_written_in_the_chosen_language(api):
    start(api)
    api.llm.rounds = [[chunk("去找老驼吧。")]]
    sse_events(api.post("/api/gm/chat", json={"message": "提示？"}, headers=hdr("zh")))
    gm_sys = [r for r in api.llm.requests if r.get("stream")][-1]["messages"][0]["content"]
    assert f"reply in {i18n.LANG_NAMES['zh']} only" in gm_sys
    give(api, "debt", "hatch", "bodies", "tunnel")
    api.post("/api/move", json={"path": "tunnel"})
    g = api.post("/api/ending", headers=hdr("th")).json()["game"]
    assert g["stage"] == "solved" and i18n.in_language(g["ending"], "th")
    api.post("/api/game/start")
    give(api, "debt", "hatch", "bodies", "tunnel")
    api.post("/api/move", json={"path": "tunnel"})
    g = api.post("/api/ending", headers=hdr("zh")).json()["game"]
    assert i18n.in_language(g["ending"], "zh")


def test_a_reply_in_the_wrong_language_falls_back_to_the_written_ending(api):
    start(api)
    give(api, "debt", "hatch", "bodies", "tunnel")
    api.post("/api/move", json={"path": "tunnel"})
    api.llm.chat = NS(completions=NS(create=lambda **kw: NS(choices=[NS(message=NS(content="This is English even though Thai was asked for. " * 8))])))
    g = api.post("/api/ending", headers=hdr("th")).json()["game"]
    assert "เฒ่าถัว" in g["ending"] and "slaughterhouse" not in g["ending"]                       # the written Thai ending, not the model's English


def test_what_a_player_types_cannot_inject_another_language(api):
    start(api)
    t = talk(api, "tuo")
    say(api, t["id"], "hello ||| 你好 ||| สวัสดี")
    turns = api.post("/api/talks", json={"npc": "tuo"}).json()["turns"]
    assert [x["content"] for x in turns if x["role"] == "user"] == ["hello | 你好 | สวัสดี"]


def test_a_threat_in_thai_is_caught_like_one_in_english(api):
    assert case.THREAT.search("หลีกไป ไม่งั้นข้าจะฟันเจ้า") and case.THREAT.search("ข้าจะฆ่าเจ้า")
    start(api)
    t = talk(api, "wolf")
    evs = say(api, t["id"], "หลีกไป ไม่งั้นข้าจะฟันเจ้า")
    assert [e["cause"] for e in evs if e["type"] == "death"] == ["caught"]


def test_the_admin_sees_which_language_visitors_chose(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    api.get("/api/case", headers=hdr("th"))
    other = TestClient(main.app)
    other.get("/api/case", headers=hdr("zh"))
    s = admin_get(api, "/api/admin/stats").json()
    assert s["languages"] == {"th": 1, "zh": 1}
