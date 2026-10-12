"""Offline tests for the dice game: the rules, the story data, and a whole night through the API with a fake model."""
import json
import os
import random
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "game.db")
os.environ["DEEPSEEK_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, i18n, main, prompts, rules, story  # noqa: E402


# ---------- the rules ----------

def test_thirty_points_over_three_stats_every_time():
    rng = random.Random(1)
    for _ in range(500):
        s = rules.roll_stats(rng)
        assert sum(s.values()) == 30 and set(s) == {"str", "int", "agi"}
        assert all(rules.STAT_MIN <= v <= rules.STAT_MAX for v in s.values())


def test_strength_sets_hit_points_and_agility_sets_defence():
    assert rules.max_hp({"str": 6}) == 22 and rules.max_hp({"str": 16}) == 42
    assert rules.defence_bonus({"agi": 6}) == 2 and rules.defence_bonus({"agi": 16}) == 5


class Dice(random.Random):
    """Dice that roll the numbers they were told to."""
    def __init__(self, *rolls):
        super().__init__()
        self.rolls = list(rolls)

    def randint(self, a, b):
        return self.rolls.pop(0)


def hero(off="split_palm", defn="iron_cloth", **kw):
    h = {"str": 10, "int": 10, "agi": 10, "hp": 50, "hp_max": 50, "qi": 2, "off": off, "defn": defn}
    h.update(kw)
    return h


def foe(**kw):
    return {"hp": 30, "atk": 3, "defn": 3, "dmg": 2, **kw}


def test_damage_is_the_sum_of_the_attack_dice():
    h, n = hero(off="sand_blade"), foe()
    r = rules.fight_round(h, n, "strike", Dice(4, 3, 1, 1, 1, 1, 1, 1))         # 7+2=9 against 2+3=5: lands for the sum, 7
    assert r["hero"]["hit"] and r["hero"]["damage"] == 7 and n["hp"] == 23


def test_a_miss_does_nothing_and_a_tie_goes_to_the_attacker():
    h, n = hero(), foe(defn=3)
    r = rules.fight_round(h, n, "strike", Dice(1, 1, 5, 6, 1, 1, 1, 1))        # 2+2=4 against 11+3=14
    assert not r["hero"]["hit"] and n["hp"] == 30
    n = foe(defn=2)
    r = rules.fight_round(hero(), n, "strike", Dice(3, 4, 3, 4, 1, 1, 1, 1))   # 7+2=9 against 7+2=9: a tie
    assert r["hero"]["hit"]


def test_the_enemy_hits_back_with_dice_and_guarding_helps():
    h = hero(defn="stone_breath")
    r = rules.fight_round(h, foe(atk=3, dmg=2), "guard", Dice(1, 1, 1, 1))     # enemy 2+3=5 against 2+3(agi 10)+3(guard)=8
    assert r["hero"] is None and not r["npc"]["hit"] and h["hp"] == 50
    r = rules.fight_round(h, foe(atk=9, dmg=2), "guard", Dice(6, 6, 1, 2))      # 12+9=21 against 3+3+3=9: hit for 12+2=14
    assert r["npc"]["hit"] and r["npc"]["damage"] == 14 and h["hp"] == 36


def test_each_martial_art_does_its_thing():
    assert rules.attack_effect("sand_blade", [3, 3], 10, 5, 10) == (12, [("doubled", 6)])
    assert rules.attack_effect("sand_blade", [3, 4], 10, 5, 10)[0] == 7
    assert rules.attack_effect("split_palm", [5, 5], 12, 5, 10) == (15, [("shockwave", 5)])
    assert rules.attack_effect("split_palm", [2, 3], 12, 5, 10)[0] == 5
    assert rules.attack_effect("needle_rain", [5, 6], 12, 5, 8)[0] == 11 + 2 * 3
    assert rules.attack_effect("shadow_step", [2, 2], 14, 5, 10)[0] == 4 + 7 and rules.attack_effect("shadow_step", [2, 2], 9, 5, 10)[0] == 4
    assert rules.soften("iron_cloth", 10, 10) == (6, 4) and rules.soften("iron_cloth", 1, 10) == (1, 0) and rules.soften("willow_step", 10, 10) == (10, 0)
    assert rules.defence_roll_bonus("willow_step", 12) == 4 and rules.defence_roll_bonus("iron_cloth", 12) == 0
    assert rules.reflect("yield_palm", 15, 10, 10) == 7 and rules.reflect("yield_palm", 12, 10, 10) == 0
    assert rules.breath_heal("stone_breath", [3, 3], 10) == 6 and rules.breath_heal("stone_breath", [3, 4], 10) == 0


def test_intelligence_sets_the_starting_qi_and_how_fast_guarding_recovers_it():
    assert [rules.start_qi({"int": i}) for i in (6, 8, 10, 12, 16)] == [2, 3, 3, 4, 5]
    assert rules.qi_recovery({"int": 10}) == 1 and rules.qi_recovery({"int": 11}) == 2
    h = hero(qi=0, int=14)
    rules.fight_round(h, foe(), "guard", Dice(1, 1, 1, 1))
    assert h["qi"] == 2


def test_intelligence_makes_the_arts_stronger():
    assert rules.attack_effect("split_palm", [5, 5], 12, 5, 16)[0] > rules.attack_effect("split_palm", [5, 5], 12, 5, 6)[0]
    assert rules.soften("iron_cloth", 10, 16)[1] > rules.soften("iron_cloth", 10, 6)[1]


def test_a_dead_foe_does_not_strike_back():
    h, n = hero(), foe(hp=3)
    r = rules.fight_round(h, n, "strike", Dice(6, 6, 1, 1))
    assert n["hp"] == 0 and r["npc"] is None and h["hp"] == 50


def test_every_art_has_a_name_and_a_description_in_three_languages():
    assert set(story.ARTS) == set(rules.OFFENCE + rules.DEFENCE)
    for key, art in story.ARTS.items():
        assert i18n.complete(art["name"]) and i18n.complete(art["does"]) and art["kind"] == ("offence" if key in rules.OFFENCE else "defence")


# ---------- the story data ----------

def test_the_cast_arrives_over_the_night_and_every_mood_is_present():
    arrivals = [c["arrive"] for c in story.CAST]
    assert arrivals[0] == 0 and arrivals == sorted(arrivals) and max(arrivals) < story.STORM_END - 1
    assert {c["mood"] for c in story.CAST} == {"friendly", "aggressive", "police"}
    for c in story.CAST:
        if c["mood"] != "friendly":
            assert c["fuse"] and 0 < c["calm"] <= 10
        assert c["reward"]["trust"] <= 10 and c["reward"]["effect"]["kind"] in ("edge", "heal", "shortcut")
        if c["reward"]["effect"]["kind"] == "edge":
            assert c["reward"]["effect"]["target"] in story.BY_KEY


def test_the_ending_and_cast_text_is_complete():
    for e in story.ENDINGS.values():
        assert i18n.complete(e["fallback"]) and i18n.complete(e["title"])
    assert "Wuhui" in prompts.npc_system("monk") and "do NOT attack" in prompts.npc_system("monk")


def test_a_person_is_told_the_reward_only_when_the_server_unlocks_it():
    secret = story.BY_KEY["wolf"]["reward"]["fact"]
    assert secret not in prompts.npc_system("wolf") and secret not in prompts.npc_state("wolf", 3, 2, "", False, "en")
    assert secret in prompts.npc_state("wolf", 5, 2, secret, False, "en")


# ---------- a night through the API ----------

def chunk(content=None):
    return NS(choices=[NS(delta=NS(content=content, tool_calls=None))])


class FakeLLM:
    def __init__(self):
        self.requests, self.trust, self.threat, self.reply = [], 0, False, "A quiet nod."
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        if kw.get("stream"):
            return iter([chunk(self.reply)])
        system = kw["messages"][0]["content"]
        if system.startswith("You judge one message"):
            return NS(choices=[NS(message=NS(content=json.dumps({"threat": self.threat, "trust": self.trust})))])
        if "Tell the ending" in kw["messages"][-1]["content"]:
            return NS(choices=[NS(message=NS(content="The storm took its time and so did the inn. " * 8))])
        return NS(choices=[NS(message=NS(content="..."))])


@pytest.fixture
def api(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(main, "llm", lambda: llm)
    monkeypatch.setattr(main.ratelimit, "check", lambda *_a, **_k: None)
    monkeypatch.setattr(main.rules, "pick_intent", lambda rng: "quick")                  # a steady enemy, so the dice scripts below mean something
    with db.session() as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM talk_archive")
    c = TestClient(main.app)
    c.llm = llm
    return c


def sse_events(r):
    return [json.loads(x[5:]) for x in r.text.split("\n\n") if x.startswith("data:")]


def rigged(api, **changes):
    """Change the saved night directly: hero fields, per-person fields, or any top-level field of the state."""
    with db.session() as conn:
        g = db.get_play(conn, api.cookies.get("vid"))
        st = g["state"]
        for k, v in changes.items():
            if k == "hero":
                st["hero"].update(v)
            elif k == "npc":
                for key, upd in v.items():
                    st["npcs"][key].update(upd)
            else:
                st[k] = v
        db.save_play(conn, g)


def begin(api):
    api.post("/api/roll")
    return api.post("/api/game/start").json()["game"]


def say(api, tid, text="hello"):
    return sse_events(api.post(f"/api/talks/{tid}/chat", json={"message": text}))


def test_rolling_gives_a_thief_with_thirty_points_and_two_arts_and_can_be_rerolled(api):
    seen = set()
    for _ in range(6):
        g = api.post("/api/roll").json()["game"]
        h = g["hero"]
        assert g["stage"] == "rolling" and h["str"] + h["int"] + h["agi"] == 30 and h["hp"] == h["hp_max"] == 10 + 2 * h["str"]
        assert h["off"]["key"] in rules.OFFENCE and h["defn"]["key"] in rules.DEFENCE and h["off"]["name"] and h["defn"]["does"]
        seen.add((h["str"], h["int"], h["agi"], h["off"]["key"], h["defn"]["key"]))
    assert len(seen) > 1


def test_the_night_starts_with_the_keeper_and_people_arrive_as_beats_pass(api):
    g = begin(api)
    assert g["stage"] == "playing" and g["tick"] == 0 and [n["key"] for n in g["npcs"]] == ["shuang"] and g["incoming"] == 6 and not g["can_leave"]
    assert api.post("/api/roll").status_code == 409                                       # no re-rolling mid-night
    t = api.post("/api/talks", json={"npc": "shuang"}).json()
    ev = []
    for _ in range(2):
        ev = say(api, t["id"])
    g = ev[-1]["game"]
    assert g["tick"] == 2 and {n["key"] for n in g["npcs"]} == {"shuang", "wolf"} and any(f["kind"] == "arrival" for f in g["feed"])
    assert api.post("/api/talks", json={"npc": "qin"}).status_code == 404                  # someone who hasn't arrived can't be talked to


def test_enough_trust_pays_out_the_reward_once_and_the_reward_reaches_the_model(api):
    begin(api)
    api.llm.trust = 2
    t = api.post("/api/talks", json={"npc": "shuang"}).json()
    for _ in range(2):
        ev = say(api, t["id"], "you are wise")
    g = ev[-1]["game"]
    shuang = next(n for n in g["npcs"] if n["key"] == "shuang")
    assert shuang["trust"] >= 7 and shuang["rewarded"] and g["exit_at"] == 11                  # the tunnel: five beats sooner
    states = [r["messages"][-2]["content"] for r in api.llm.requests if r.get("stream")]
    assert sum("smugglers' tunnel" in s for s in states) == 1                                   # told to the model once, in the turn it was earned
    assert sum(1 for f in g["feed"] if f["kind"] == "gain") == 1


def test_the_righteous_attack_first_when_their_patience_ends_and_no_talking_mid_fight(api):
    begin(api)
    rigged(api, tick=3, npc={"yue": {"status": "here", "arrived": 3}})
    t = api.post("/api/talks", json={"npc": "shuang"}).json()
    ev = []
    for _ in range(3):
        ev = say(api, t["id"], "tea?")
    g = ev[-1]["game"]
    assert g["fight"]["npc"] == "yue" and any(e["type"] == "ambush" for e in ev)             # she kept Yue waiting: Yue strikes first
    assert g["hero"]["hp"] >= 1
    assert any(e["type"] == "error" for e in say(api, t["id"], "wait"))


def test_winning_someone_round_settles_the_talk_and_a_settled_person_never_attacks(api):
    begin(api)
    rigged(api, tick=3, npc={"yue": {"status": "here", "arrived": 3, "trust": 3}})
    api.llm.trust = 2
    t = api.post("/api/talks", json={"npc": "yue"}).json()
    ev = say(api, t["id"], "I steal to feed my sister. I am sorry.")
    g = ev[-1]["game"]
    yue = next(n for n in g["npcs"] if n["key"] == "yue")
    assert yue["status"] == "calm" and yue["rewarded"] and any(e["type"] == "resolved" for e in ev) and g["edges"] == {"gu": 2}
    assert any(e["type"] == "error" for e in say(api, t["id"], "more?"))                      # nothing more to say
    rigged(api, tick=9, npc={"yue": {"arrived": 0}})
    s2 = api.post("/api/talks", json={"npc": "shuang"}).json()
    ev = say(api, s2["id"], "tea?")
    assert not ev[-1]["game"]["fight"] or ev[-1]["game"]["fight"]["npc"] != "yue"


def test_a_talk_that_runs_out_ends_in_a_fight_where_they_strike_first(api):
    begin(api)
    t = api.post("/api/talks", json={"npc": "shuang"}).json()
    ev = []
    for _ in range(5):                                                                       # Shuang gives her five exchanges
        ev = say(api, t["id"], "hmm")
    g = ev[-1]["game"]
    assert g["fight"]["npc"] == "shuang" and any(e["type"] == "ambush" for e in ev) and any(f["kind"] == "fight" for f in g["feed"])
    last = [r for r in api.llm.requests if r.get("stream")][-1]["messages"][-2]["content"]
    assert "LAST exchange" in last


def test_the_person_is_told_the_goal_and_how_many_exchanges_are_left(api):
    begin(api)
    t = api.post("/api/talks", json={"npc": "shuang"}).json()
    say(api, t["id"], "hello")
    state = [r for r in api.llm.requests if r.get("stream")][-1]["messages"][-2]["content"]
    assert "4 more exchanges" in state and "way to leave the pass early" in state
    g = api.get("/api/game").json()["game"]
    shuang = g["npcs"][0]
    assert shuang["talk_limit"] == 5 and shuang["talks"] == 1 and shuang["goal_trust"] == 7 and shuang["goal"]


def test_a_free_blow_never_kills_and_the_enemy_telegraphs_what_it_will_do():
    h = hero(hp=3)
    r = rules.ambush(h, foe(atk=9, dmg=9), Dice(6, 6, 1, 1))
    assert h["hp"] == 1 and r["hit"]
    assert {rules.pick_intent(random.Random(i)) for i in range(60)} == set(rules.INTENTS)


def test_an_art_costs_breath_and_guarding_gives_it_back():
    h, n = hero(off="sand_blade", qi=1), foe()
    r = rules.fight_round(h, n, "art", Dice(3, 3, 1, 1, 1, 1, 1, 1))                         # 6+2+2=10 against 2+3=5; pair doubles to 12, art adds 3+3
    assert h["qi"] == 0 and r["hero"]["art"] and r["hero"]["damage"] == 12 + 3 + 10 // 3 and ("flourish", 6) in r["hero"]["notes"]
    h["qi"] = rules.QI_MAX
    rules.fight_round(h, foe(), "guard", Dice(1, 1, 1, 1))
    assert h["qi"] == rules.QI_MAX
    h["qi"] = 1
    rules.fight_round(h, foe(), "guard", Dice(1, 1, 1, 1))
    assert h["qi"] == 2


def test_the_art_is_refused_without_breath(api):
    begin(api)
    rigged(api, hero={"qi": 0, "int": 8})
    api.post("/api/fight/start", json={"npc": "shuang"})
    assert api.post("/api/fight/round", json={"action": "art"}).status_code == 409
    assert api.post("/api/fight/round", json={"action": "guard"}).json()["game"]["hero"]["qi"] == 1


def test_a_counter_beats_a_heavy_blow_and_is_wasted_on_anything_else():
    h, n = hero(defn="stone_breath"), foe(atk=3)
    r = rules.fight_round(h, n, "counter", Dice(6, 5, 1, 1), 0, "heavy")                    # heavy: 11+3-1=13 against 2+3+4=9 would hit... so give the hero real dice
    assert r["npc"]["hit"]
    h, n = hero(defn="stone_breath"), foe(atk=3)
    r = rules.fight_round(h, n, "counter", Dice(1, 1, 6, 6), 0, "heavy")                    # enemy 2+3-1=4 against 12+3+4=19: blocked, and turned back on them
    assert not r["npc"]["hit"] and ("counter", 12 + 2 + 3) in r["npc"]["notes"] and n["hp"] == 30 - 17
    h, n = hero(defn="stone_breath"), foe(atk=3)
    r = rules.fight_round(h, n, "counter", Dice(1, 1, 6, 6), 0, "quick")                    # against a quick strike the counter leaves her open (-2) and does nothing to them
    assert n["hp"] == 30 and not any(x[0] == "counter" for x in r["npc"]["notes"]) and r["npc"]["against"]["total"] == 12 + 3 - 2


def test_a_turtling_enemy_does_not_attack_but_is_harder_to_hit_and_a_heavy_one_hits_harder():
    h, n = hero(), foe(defn=0)
    r = rules.fight_round(h, n, "strike", Dice(6, 6, 1, 1), 0, "guard")
    assert r["npc"] is None and r["hero"]["against"]["total"] == 2 + rules.GUARD_UP
    h = hero(defn="willow_step")
    r = rules.fight_round(h, foe(atk=9, dmg=2), "strike", Dice(1, 1, 6, 6, 6, 6, 1, 1), 0, "heavy")
    assert r["npc"]["hit"] and r["npc"]["damage"] == 12 + 2 + rules.HEAVY_DAMAGE


def test_a_threat_turns_the_righteous_hostile_and_the_model_is_told(api):
    begin(api)
    rigged(api, tick=3, npc={"yue": {"status": "here", "arrived": 3}})
    api.llm.threat = True
    t = api.post("/api/talks", json={"npc": "yue"}).json()
    ev = say(api, t["id"], "Come near me and I will kill you.")
    assert ev[-1]["game"]["fight"]["npc"] == "yue"
    assert any("threatened you" in str(r["messages"]) for r in api.llm.requests if r.get("stream"))


def test_she_can_pick_a_fight_with_anyone_and_beating_them_takes_what_they_know(api, monkeypatch):
    begin(api)
    rigged(api, hero={"str": 16, "hp": 70, "hp_max": 70, "off": "sand_blade"}, edges={"shuang": 2})
    assert api.post("/api/fight/start", json={"npc": "nobody"}).status_code == 404
    assert api.post("/api/fight/start", json={"npc": "shuang"}).json()["game"]["fight"]["npc"] == "shuang"
    assert api.post("/api/fight/start", json={"npc": "shuang"}).status_code == 409
    monkeypatch.setattr(main, "_dice", Dice(*([6, 6] * 40)))                                   # she rolls double sixes every time
    out = {}
    for _ in range(10):
        out = api.post("/api/fight/round", json={"action": "strike"}).json()
        if not out["game"]["fight"]:
            break
    g = out["game"]
    shuang = next(n for n in g["npcs"] if n["key"] == "shuang")
    assert g["stage"] == "playing" and not g["fight"] and shuang["status"] == "down" and shuang["rewarded"] and g["exit_at"] == 11
    assert out["round"]["hero"]["damage"] >= 24 and out["round"]["hero"]["dice"] == [6, 6]


def test_losing_a_fight_to_the_law_is_arrest_and_the_ending_is_told_once(api, monkeypatch):
    begin(api)
    rigged(api, hero={"hp": 1}, tick=8, npc={"gu": {"status": "here", "arrived": 7}})
    api.post("/api/fight/start", json={"npc": "gu"})
    monkeypatch.setattr(main, "_dice", Dice(1, 1, 1, 1, 6, 6, 1, 1))
    out = api.post("/api/fight/round", json={"action": "strike"}).json()
    assert out["game"]["stage"] == "dead" and out["game"]["ending_key"] == "arrested" and out["game"]["killer"] == "gu"
    assert api.post("/api/talks", json={"npc": "shuang"}).status_code == 409                    # the night is over
    ending = api.post("/api/ending").json()["game"]
    assert ending["ending"] and ending["won"] is False
    assert api.post("/api/ending").json()["game"]["ending"] == ending["ending"]


def test_losing_to_the_wolf_is_being_slain(api, monkeypatch):
    begin(api)
    rigged(api, hero={"hp": 1}, npc={"wolf": {"status": "here", "arrived": 1}})
    api.post("/api/fight/start", json={"npc": "wolf"})
    monkeypatch.setattr(main, "_dice", Dice(6, 6, 1, 1))
    assert api.post("/api/fight/round", json={"action": "guard"}).json()["game"]["ending_key"] == "slain"


def test_leaving_after_the_storm_wins_and_leaving_early_is_death(api):
    begin(api)
    r = api.post("/api/leave").json()["game"]
    assert r["stage"] == "dead" and r["ending_key"] == "storm"
    begin(api)
    rigged(api, tick=story.STORM_END)
    r = api.post("/api/leave").json()["game"]
    assert r["stage"] == "solved" and r["won"] and r["ending_key"] == "escaped"
    assert api.post("/api/ending").json()["game"]["ending"]


def test_she_cannot_leave_in_the_middle_of_a_fight(api):
    begin(api)
    rigged(api, tick=story.STORM_END)
    api.post("/api/fight/start", json={"npc": "shuang"})
    assert api.post("/api/leave").status_code == 409


def test_the_ending_falls_back_to_the_written_one_if_the_model_fails(api, monkeypatch):
    begin(api)
    rigged(api, tick=story.STORM_END)
    api.post("/api/leave")

    def broken():
        raise main.HTTPException(503, "no")
    monkeypatch.setattr(main, "llm", broken)
    assert i18n.pick(story.ENDINGS["escaped"]["fallback"], "en") in api.post("/api/ending").json()["game"]["ending"]


def test_ray_knows_the_state_but_not_the_rewards_nobody_has_earned(api):
    begin(api)
    with db.session() as conn:
        g = db.get_play(conn, api.cookies.get("vid"))
    snap = main._snapshot(g)
    assert "Shuang" in snap and "Black Wolf" not in snap
    for c in story.CAST:
        assert c["reward"]["fact"] not in snap and c["reward"]["fact"] not in prompts.gm_system(snap, g["state"]["hero"], 16)
    assert any(e["type"] == "done" for e in sse_events(api.post("/api/gm/chat", json={"message": "what should I do?"})))


def test_three_languages_all_the_way_through(api):
    for lang in ("en", "zh", "th"):
        h = {"x-lang": lang}
        case = api.get("/api/case", headers=h).json()
        assert "|||" not in json.dumps(case, ensure_ascii=False) and len(case["cast"]) == 7
        g = api.post("/api/roll", headers=h).json()["game"]
        assert "|||" not in json.dumps(g, ensure_ascii=False)
    th = api.get("/api/case", headers={"x-lang": "th"}).json()
    assert any("฀" <= ch <= "๿" for ch in th["setup"]) and th["cast"][0]["name"] == "ฮูหยินซวง"


def test_the_admin_lists_every_player_with_how_long_they_played(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    h = {"authorization": "Bearer s3cret"}
    api.get("/api/case")                                                      # a visitor who only looked
    other = TestClient(main.app)
    other.get("/api/case")
    other.post("/api/roll")
    other.post("/api/game/start")
    t = other.post("/api/talks", json={"npc": "shuang"}).json()
    other.post(f"/api/talks/{t['id']}/chat", json={"message": "hello"})
    with db.session() as conn:
        conn.execute("UPDATE events SET ts = ts - 300 WHERE kind IN ('visit', 'roll', 'start')")             # they started five minutes ago
    other.post("/api/leave")
    rows = api.get("/api/admin/stats", headers=h).json()["players"]
    assert len(rows) == 2 and all("who" in r and len(r["who"]) == 6 for r in rows)
    looked = next(r for r in rows if r["nights"] == 0)
    played = next(r for r in rows if r["nights"] == 1)
    assert looked["last_result"] == "only looked" and played["finished"] == 1 and played["messages"] == 1
    assert 4.5 < played["minutes"] < 5.5 and played["last_result"] == "storm"


def test_the_admin_sees_nights_wins_and_what_killed_her(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    h = {"authorization": "Bearer s3cret"}
    begin(api)
    api.post("/api/leave")
    s = api.get("/api/admin/stats", headers=h).json()
    assert s["nights_started"] == 1 and s["nights_finished"] == 1 and s["win_rate"] == 0.0 and s["endings"] == {"storm": 1}
    assert s["people"]["gu"]["name"] == "Captain Gu" and s["funnel"][1]["step"] == "Rolled a thief"


def test_a_night_saved_by_the_old_version_is_dropped_instead_of_breaking_the_page(api):
    with db.session() as conn:
        conn.execute("INSERT OR REPLACE INTO plays (visitor_id, stage, state, updated_at) VALUES (?,?,?,?)", ("a" * 32, "playing", "{}", 0))
    c = TestClient(main.app, cookies={"vid": "a" * 32})
    r = c.get("/api/game")
    assert r.status_code == 200 and r.json() == {"game": None}


def test_a_night_saved_by_an_older_shape_of_the_game_is_dropped_too(api):
    with db.session() as conn:
        conn.execute("INSERT OR REPLACE INTO plays (visitor_id, stage, state, updated_at) VALUES (?,?,?,?)", ("b" * 32, "playing", '{"hero": {"hp": 5}}', 0))
    assert TestClient(main.app, cookies={"vid": "b" * 32}).get("/api/game").json() == {"game": None}


def test_the_visitors_country_device_and_referrer_are_counted_without_storing_the_ip(api, monkeypatch):
    monkeypatch.setattr(main.config, "ADMIN_PASSWORD", "s3cret")
    h = {"authorization": "Bearer s3cret"}
    thai = TestClient(main.app)
    thai.get("/api/case", headers={"x-forwarded-for": "49.228.0.1, 10.0.0.2", "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile", "x-ref": "https://www.linkedin.com/feed/"})
    us = TestClient(main.app)
    us.get("/api/case", headers={"x-forwarded-for": "8.8.8.8", "user-agent": "Mozilla/5.0 (Windows NT 10.0) Chrome"})
    s = api.get("/api/admin/stats", headers=h).json()
    assert s["countries"] == {"TH": 1, "US": 1} and s["devices"] == {"phone": 1, "desktop": 1} and s["referrers"] == {"www.linkedin.com": 1}
    rows = {r["country"]: r for r in s["players"]}
    assert rows["TH"]["device"] == "phone"
    with db.session() as conn:
        raw = " ".join(r["data"] for r in conn.execute("SELECT data FROM events"))
    assert "49.228" not in raw and "8.8.8.8" not in raw


def test_the_country_lookup_ignores_private_and_bad_addresses():
    from app import geo
    assert geo.country("49.228.0.1") == "TH" and geo.country("8.8.8.8") == "US"
    assert geo.country("127.0.0.1") == "" and geo.country("10.1.2.3") == "" and geo.country("nonsense") == "" and geo.country("") == ""
