"""Offline tests: no DeepSeek calls. A fake client replays scripted streams."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DEEPSEEK_API_KEY"] = ""

from app import agent, config, db, game, svg  # noqa: E402


# ---------- svg sanitiser ----------

def test_svg_keeps_shapes_and_strips_danger():
    dirty = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" onload="alert(1)">'
             '<script>alert(1)</script><rect width="160" height="160" fill="#ebe1c8" onclick="x()"/>'
             '<circle cx="80" cy="60" r="20" fill="url(#evil)"/><image href="http://x/y.png"/>'
             '<foreignObject><div>hi</div></foreignObject></svg>')
    out = svg.clean(dirty)
    assert out and "<rect" in out and "<circle" in out
    for bad in ("script", "onload", "onclick", "url(", "image", "foreignObject", "alert"):
        assert bad not in out


def test_svg_rejects_entities_and_garbage():
    assert svg.clean('<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg>&a;</svg>') is None
    assert svg.clean("not svg at all") is None
    assert svg.clean("<html></html>") is None


def test_extract_finds_svg_in_chatter():
    assert svg.extract('Here you go:\n<svg viewBox="0 0 1 1"></svg>\nEnjoy') == '<svg viewBox="0 0 1 1"></svg>'


def test_reply_language_is_decided_in_code():
    from app import prompts
    assert prompts.reply_language("What do you sell, old man?") == "English"
    assert prompts.reply_language("老人家，你卖的是什么？") == "Chinese"
    assert prompts.reply_language("Have you met 柳寒烟 on the canal?") == "English"


# ---------- game rules ----------

def test_apply_fields_clamps_and_validates():
    s = game.blank_sheet()
    changed = game.apply_fields(s, {"name": "  柳寒烟   Liu  Hanyan ", "alignment": "chaotic",
                                     "stats": {"neigong": 99, "qinggong": "x"}, "traits": ["a", "", "b"]})
    assert s["name"] == "柳寒烟 Liu Hanyan"
    assert s["alignment"] == "neutral"
    assert s["stats"]["neigong"] == 10 and s["stats"]["qinggong"] == 5
    assert s["traits"] == ["a", "b"]
    assert {"name", "alignment", "stats", "traits"} <= set(changed)


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
