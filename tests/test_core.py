"""Offline tests: no DeepSeek calls. A fake client replays scripted streams."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["SEED_WORLD"] = "0"
os.environ["DEEPSEEK_API_KEY"] = ""

from app import agent, bilingual, config, db, game, prompts, roll, world  # noqa: E402


def test_language_detection():
    assert bilingual.language_of("What do you sell, old man?") == "English"
    assert bilingual.language_of("老人家，你卖的是什么？") == "Chinese"
    assert bilingual.language_of("Have you met 柳寒烟 on the canal?") == "English"   # a Chinese name inside English stays English


def test_bilingual_format():
    assert bilingual.is_pair("Never forgives a debt ||| 有债必讨")
    assert not bilingual.is_pair("Never forgives a debt")                  # one language only
    assert not bilingual.is_pair("有债必讨 ||| Never forgives a debt")      # wrong order
    assert not bilingual.is_pair("Never forgives a debt ||| ")             # an empty half
    assert bilingual.split("Hello ||| 你好") == ("Hello", "你好")
    assert bilingual.plain("Hello ||| 你好") == "Hello / 你好"
    assert bilingual.has_both("Ask about the Jin war 问问金国战事")
    assert not bilingual.has_both("Ask about the Jin war")


class Translator:
    def __init__(self, reply="你好，老人家"):
        self.reply, self.prompts = reply, []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.prompts.append(kw["messages"][0]["content"])
        return NS(choices=[NS(message=NS(content=self.reply))])


def test_counterpart_translates_to_the_other_language_only_when_needed():
    t = Translator("Hello, old man")
    assert bilingual.counterpart(t, "m", "你好，老人家") == "Hello, old man"
    assert "into English" in t.prompts[0]
    t2 = Translator()
    assert bilingual.counterpart(t2, "m", "Hello, old man") == "你好，老人家"
    assert "into Chinese" in t2.prompts[0]
    assert bilingual.counterpart(t2, "m", "Hello 你好 old man 老人家") == ""      # already both: no call
    assert len(t2.prompts) == 1


def test_a_failed_translation_never_breaks_a_reply():
    class Boom:
        chat = NS(completions=NS(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("down"))))
    assert bilingual.counterpart(Boom(), "m", "Hello, old man") == ""


# ---------- game rules ----------

def test_apply_fields_clamps_and_validates():
    s = game.blank_sheet()
    changed = game.apply_fields(s, {"name": "  柳寒烟   Liu  Hanyan ", "alignment": "chaotic",
                                     "traits": ["bold ||| 勇", "calm ||| 静", "wry ||| 俏", "mean ||| 刻"]})
    assert s["name"] == "柳寒烟 Liu Hanyan"
    assert s["alignment"] == "neutral"
    assert s["traits"] == ["bold ||| 勇", "calm ||| 静", "wry ||| 俏"]       # exactly three quirks at most
    assert {"name", "alignment", "traits"} <= set(changed)


def test_text_in_one_language_is_not_saved():
    s = game.blank_sheet()
    rejected: list[str] = []
    changed = game.apply_fields(s, {"title": "Ferryman of the Broken Oar", "goal": "Find my brother ||| 找到我的兄弟",
                                     "traits": ["Never forgives a debt", "Talks to his lantern ||| 对灯笼说话"]}, rejected)
    assert s["goal"] == "Find my brother ||| 找到我的兄弟" and "goal" in changed
    assert s["title"] == "" and s["traits"] == []
    assert set(rejected) == {"title", "traits"}


def test_set_fields_tells_the_model_what_to_fix():
    s = game.blank_sheet()
    turn = agent.Turn()
    with db.session() as conn:
        tools = {t.name: t for t in game.storyteller_tools(conn, s, turn)}
        result = agent._call(tools["set_fields"], json.dumps({"name": "Old Wu", "goal": "Find my brother"}))
    assert result["ok"] is False and "goal" in result["error"] and "|||" in result["error"]
    assert s["name"] == "Old Wu" and s["goal"] == ""           # the good field was kept, the bad one was not


def test_appearance_keeps_valid_choices_and_fills_the_rest():
    s = game.blank_sheet()
    game.apply_fields(s, {"name": "Old Wu", "appearance": {"hair_style": "Twin Buns", "aura": "flame", "weapon": "bazooka"}})
    a = s["appearance"]
    assert a["hair_style"] == "twin_buns" and a["aura"] == "flame"      # tidied and kept
    assert a["weapon"] in game.APPEARANCE["weapon"] and a["weapon"] != "bazooka"   # invalid value replaced
    assert set(a) == set(game.APPEARANCE)                               # every option present

    first = dict(a)
    game.apply_fields(s, {"appearance": {"hair_color": "silver"}})        # a later tweak changes only that option
    assert s["appearance"]["hair_color"] == "silver"
    assert {k: v for k, v in s["appearance"].items() if k != "hair_color"} == {k: v for k, v in first.items() if k != "hair_color"}


def test_a_sheet_is_complete_only_when_every_part_is_filled():
    s = game.blank_sheet()
    assert set(game.missing(s)) == set(game.REQUIRED)
    both = {k: "English text ||| 中文文字" for k in game.BILINGUAL}
    game.apply_fields(s, both | {"name": "Old Wu", "alignment": "neutral", "region": "huashan", "traits": ["bold ||| 勇", "calm ||| 静", "wry ||| 俏"]})
    assert game.missing(s) == ["appearance"]
    game.apply_fields(s, {"appearance": {}})          # even an empty look is filled in with defaults
    assert game.missing(s) == []


def test_dice_give_varied_valid_seeds_in_both_languages():
    import random
    seeds = [roll.random_seed(random.Random(i)) for i in range(40)]
    assert len({x["summary"] for x in seeds}) > 30
    for x in seeds:
        for key, value in x["look"].items():
            assert value in game.APPEARANCE[key]
        assert x["look"]["aura"] != "none"
        assert bilingual.language_of(x["summary"]) == "English" and bilingual.language_of(x["summary_zh"]) == "Chinese"
    msg = roll.roll_message(seeds[0])
    assert seeds[0]["summary"] in msg and seeds[0]["summary_zh"] in msg and "aura=" in msg


def test_secret_is_gated_by_server_trust():
    db.init()
    sess = {"trust": 3, "revealed": False}
    turn = agent.Turn()
    with db.session() as conn:
        tools = {t.name: t for t in game.npc_tools(conn, {"id": "x"}, "I buried the gold", sess, turn)}
        refused = agent._call(tools["reveal_secret"], "{}")
        assert "error" in refused and "gold" not in json.dumps(refused)
        assert sess["revealed"] is False
        agent._call(tools["adjust_trust"], json.dumps({"delta": 99, "reason": "saved my life"}))
        assert sess["trust"] == 5           # clamped to +2 per call
        sess["trust"] = config.SECRET_TRUST_THRESHOLD
        granted = agent._call(tools["reveal_secret"], "{}")
        assert granted == {"secret": "I buried the gold"} and sess["revealed"] is True


def test_secrets_never_appear_in_public_cards():
    db.init()
    sheet = game.blank_sheet()
    game.apply_fields(sheet, {"name": "Old Wu", "secret": "He poisoned the abbot ||| 他毒死了方丈"})
    with db.session() as conn:
        npc_id = db.insert_npc(conn, sheet, "v1", "Ray")
        card = db.public_card(db.get_npc(conn, npc_id))
        assert "poisoned" not in json.dumps(card, ensure_ascii=False)
        assert card["has_secret"] is True
        assert db.get_secret(conn, npc_id) == "He poisoned the abbot ||| 他毒死了方丈"


# ---------- the agent loop, with a fake streaming client ----------

def chunk(content=None, tool=None):
    tcs = None
    if tool:
        tcs = [NS(index=tool.get("index", 0), id=tool.get("id"),
                  function=NS(name=tool.get("name"), arguments=tool.get("args")))]
    return NS(choices=[NS(delta=NS(content=content, tool_calls=tcs))])


class FakeClient:
    def __init__(self, rounds):
        self.rounds, self.requests = list(rounds), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        return iter(self.rounds.pop(0))


def test_agent_runs_tool_then_answers():
    sheet = game.blank_sheet()
    turn = agent.Turn()
    with db.session() as conn:
        tools = game.storyteller_tools(conn, sheet, turn)
        client = FakeClient([
            [chunk("Let me write that down."),
             chunk(tool={"id": "c1", "name": "set_fields", "args": '{"name": "Old'}),
             chunk(tool={"args": ' Wu"}'})],                   # arguments arrive in pieces
            [chunk("Old Wu it is. "), chunk("What does he want?")],
        ])
        events = list(agent.run(client, "m", [{"role": "user", "content": "hi"}], tools, turn, "visitor-a"))
    assert sheet["name"] == "Old Wu"
    assert [e["type"] for e in events if e["type"] != "text"] == ["retract", "tool", "sheet", "done"]
    assert events[-1]["text"] == "Old Wu it is. What does he want?"       # the narration before the tool call is taken back
    second = client.requests[1]["messages"]
    assert second[-2]["tool_calls"][0]["function"]["arguments"] == '{"name": "Old Wu"}'
    assert second[-1]["role"] == "tool"


def test_agent_survives_bad_tool_arguments():
    turn = agent.Turn()
    with db.session() as conn:
        tools = game.storyteller_tools(conn, game.blank_sheet(), turn)
        client = FakeClient([[chunk(tool={"id": "c1", "name": "set_fields", "args": "{not json"})], [chunk("Sorry.")]])
        events = list(agent.run(client, "m", [{"role": "user", "content": "hi"}], tools, turn, "visitor-b"))
    assert events[-1] == {"type": "done", "text": "Sorry."}
    assert "error" in client.requests[1]["messages"][-1]["content"]


def test_quotes_inside_bilingual_text_are_kept():
    assert game.clip('"Hello there"', 40) == "Hello there"                                 # wrapped around a single value: dropped
    both = 'Calls every blade "little sister" ||| 管每把剑叫"小妹"'
    assert game.clip(both, 80) == both                                                      # each half keeps its own quotes


def test_a_reply_without_narration_is_kept_whole():
    turn = agent.Turn()
    with db.session() as conn:
        tools = game.storyteller_tools(conn, game.blank_sheet(), turn)
        client = FakeClient([[chunk("Hello there "), chunk("friend ||| 你好，朋友")]])
        events = list(agent.run(client, "m", [{"role": "user", "content": "hi"}], tools, turn, "visitor-c"))
    assert all(e["type"] != "retract" for e in events)
    assert events[-1]["text"] == "Hello there friend ||| 你好，朋友"


def test_text_that_follows_tool_calls_in_the_same_round_is_not_the_reply():
    turn = agent.Turn()
    with db.session() as conn:
        tools = game.storyteller_tools(conn, game.blank_sheet(), turn)
        client = FakeClient([
            [chunk(tool={"id": "c1", "name": "list_jianghu", "args": "{}"}), chunk("A first draft of the reply ||| 初稿")],
            [chunk("The real reply ||| 正式回复")],
        ])
        events = list(agent.run(client, "m", [{"role": "user", "content": "hi"}], tools, turn, "visitor-d"))
    assert "retract" in [e["type"] for e in events]
    assert events[-1]["text"] == "The real reply ||| 正式回复"


# ---------- the world, first impressions and tailored prompts ----------

def test_regions_have_a_name_a_scene_and_a_place_on_the_map():
    assert len(world.REGIONS) == 12
    for rid, r in world.REGIONS.items():
        assert bilingual.language_of(r["en"]) == "English" and bilingual.language_of(r["zh"]) == "Chinese"
        assert bilingual.language_of(r["desc_zh"]) == "Chinese" and r["scene"]
        assert 0 <= r["x"] <= 1000 and 0 <= r["y"] <= 640


def test_every_dice_place_points_at_a_real_region():
    assert {pl[2] for pl in roll.PLACES} <= set(world.IDS)


def test_old_characters_without_a_region_get_a_stable_one():
    a = world.region_for({"id": "abc123", "name": "x"})
    assert a in world.open_ids() and a == world.region_for({"id": "abc123", "name": "y"})      # and lands somewhere that is open
    assert world.region_for({"id": "abc123", "region": "emei"}) == "emei"
    assert world.region_for({"id": "abc123", "region": "mars"}) == a


def test_region_must_be_a_real_one():
    s = game.blank_sheet()
    rejected: list[str] = []
    game.apply_fields(s, {"region": "Mars"}, rejected)
    assert s["region"] == "" and rejected == ["region"]
    game.apply_fields(s, {"region": " Huashan "})
    assert s["region"] == "huashan"
    rejected.clear()
    game.apply_fields(s, {"region": "emei"}, rejected)             # a real place that has not opened yet
    assert s["region"] == "huashan" and rejected == ["region"]


def test_first_impression_depends_on_who_is_asking():
    npc = {"id": "n", "alignment": "orthodox", "bonds": []}
    same, _ = game.starting_trust(npc, {"id": "h", "alignment": "orthodox", "bonds": []})
    other, why = game.starting_trust(npc, {"id": "h", "alignment": "unorthodox", "bonds": []})
    neutral, _ = game.starting_trust(npc, {"id": "h", "alignment": "neutral", "bonds": []})
    assert same > neutral > other
    assert bilingual.is_pair(why)
    known, why2 = game.starting_trust(npc, {"id": "h", "alignment": "unorthodox", "bonds": [{"toId": "n", "relation": "x ||| 甲"}]})
    assert known == other + 1 and bilingual.is_pair(why2)             # a shared history softens it
    assert 0 <= game.starting_trust({"alignment": "unorthodox"}, {"alignment": "orthodox"})[0] <= 10


def _character(name, **fields):
    s = game.blank_sheet()
    both = {k: f"{k} text ||| {k}文字" for k in game.BILINGUAL}
    game.apply_fields(s, both | {"name": name, "region": "huashan", "alignment": "orthodox",
                                 "traits": ["cries at sunsets ||| 见落日必哭", "hates swords ||| 厌恶刀剑", "sleeps on roofs ||| 睡屋顶"],
                                 "secret": "buried the treasure ||| 把宝藏埋了", **fields})
    game.apply_fields(s, {"appearance": {"hair_color": "silver", "weapon": "flute"}})
    return {**s, "id": name}


def test_npc_prompt_describes_this_particular_hero_and_never_their_secret():
    npc, hero = _character("Old Wu"), _character("柳寒烟 Liu Hanyan", alignment="unorthodox", sect="Poison Hall ||| 毒堂")
    text = prompts.npc_system(npc, [], [], hero)
    assert "柳寒烟 Liu Hanyan" in text and "Poison Hall / 毒堂" in text and "unorthodox" in text
    assert "cries at sunsets / 见落日必哭" in text                     # their habits are visible
    assert "silver hair" in text and "flute" in text                  # and so is how they look
    assert "buried the treasure" not in text.split("The person in front of you")[1]   # the hero's secret never reaches an NPC
    other = prompts.npc_system(npc, [], [], _character("Su Ling", alignment="orthodox"))
    assert other != text                                               # a different hero gives a different prompt


def test_the_opening_turn_is_addressed_to_the_hero():
    assert "walked up" in prompts.npc_state(3, False, opening=True)
    assert "walked up" not in prompts.npc_state(3, False)


def test_a_reply_is_tidied_into_one_english_half_and_one_chinese_half():
    clean = "Hello there.\n|||\n你好。"
    assert bilingual.normalize(clean) == clean
    # the separator forgotten: sort the paragraphs by language
    assert bilingual.normalize("*Waves.* Hello there.\n\n*挥手。* 你好。") == "*Waves.* Hello there.\n|||\n*挥手。* 你好。"
    # the separator repeated for every paragraph
    messy = "First part. ||| 第一段。\n\nSecond part.\n|||\n第二段。"
    assert bilingual.normalize(messy) == "First part.\n\nSecond part.\n|||\n第一段。\n\n第二段。"
    # one language only is left for the translator
    assert bilingual.normalize("Only English here.") == "Only English here."
    assert bilingual.SEP not in bilingual.normalize("只有中文。")


def test_the_translator_is_told_how_to_spell_the_cast():
    assert bilingual.glossary(["陆沉舟 Lu Chenzhou", "谢三碗 Xie Sanwan", "no chinese here"]) == "Lu Chenzhou = 陆沉舟; Xie Sanwan = 谢三碗"
    t = Translator("陆沉舟在哪里？")
    assert bilingual.counterpart(t, "m", "Where is Lu Chenzhou?", "Lu Chenzhou = 陆沉舟") == "陆沉舟在哪里？"
    assert "Lu Chenzhou = 陆沉舟" in t.prompts[0]
