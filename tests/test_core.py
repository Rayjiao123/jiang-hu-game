"""Offline tests: no DeepSeek calls. A fake client replays scripted streams."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DEEPSEEK_API_KEY"] = ""

from app import agent, config, db, game, roll  # noqa: E402


def test_reply_language_is_decided_in_code():
    from app import prompts
    assert prompts.reply_language("What do you sell, old man?") == "English"
    assert prompts.reply_language("老人家，你卖的是什么？") == "Chinese"
    assert prompts.reply_language("Have you met 柳寒烟 on the canal?") == "English"


# ---------- game rules ----------

def test_apply_fields_clamps_and_validates():
    s = game.blank_sheet()
    changed = game.apply_fields(s, {"name": "  柳寒烟   Liu  Hanyan ", "alignment": "chaotic",
                                     "traits": ["a", "", "b", "c", "d"]})
    assert s["name"] == "柳寒烟 Liu Hanyan"
    assert s["alignment"] == "neutral"
    assert s["traits"] == ["a", "b", "c"]            # exactly three quirks at most
    assert {"name", "alignment", "traits"} <= set(changed)


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
    game.apply_fields(s, {k: "x" for k in game.TEXT_FIELDS} | {"alignment": "neutral", "traits": ["a", "b", "c"]})
    assert game.missing(s) == ["appearance"]
    game.apply_fields(s, {"appearance": {}})          # even an empty look is filled in with defaults
    assert game.missing(s) == []


def test_dice_give_varied_valid_seeds():
    import random
    seeds = [roll.random_seed(random.Random(i)) for i in range(40)]
    assert len({x["summary"] for x in seeds}) > 30
    for x in seeds:
        for key, value in x["look"].items():
            assert value in game.APPEARANCE[key]
        assert x["look"]["aura"] != "none"
    msg = roll.roll_message(seeds[0])
    assert seeds[0]["summary"] in msg and "aura=" in msg


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
    game.apply_fields(sheet, {"name": "Old Wu", "secret": "He poisoned the abbot"})
    with db.session() as conn:
        npc_id = db.insert_npc(conn, sheet, "v1", "Ray")
        card = db.public_card(db.get_npc(conn, npc_id))
        assert "poisoned" not in json.dumps(card, ensure_ascii=False)
        assert card["has_secret"] is True
        assert db.get_secret(conn, npc_id) == "He poisoned the abbot"


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
    assert [e["type"] for e in events if e["type"] != "text"] == ["tool", "sheet", "done"]
    assert events[-1]["text"] == "Let me write that down.\n\nOld Wu it is. What does he want?"
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
