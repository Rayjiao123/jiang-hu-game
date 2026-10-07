"""Offline tests: no DeepSeek calls. A fake client replays scripted streams."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DEEPSEEK_API_KEY"] = ""

from app import agent, bilingual  # noqa: E402
from app.agent import Tool  # noqa: E402


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



def set_fields_tool(sheet, turn):
    """A stand-in tool: writes a name onto a dict, and tells the page."""
    def run(args):
        sheet.update({k: v for k, v in args.items() if k == "name"})
        turn.emit(type="tool", name="set_fields", detail="name")
        turn.emit(type="sheet", sheet=sheet)
        return {"ok": True}
    return [Tool("set_fields", "write fields", {"type": "object", "properties": {"name": {"type": "string"}}}, run)]


def _clip(v, n):
    return v[:n] if bilingual.SEP in v else v.strip('"')[:n]


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
    sheet = {}
    turn = agent.Turn()
    if True:
        tools = set_fields_tool(sheet, turn)
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
    if True:
        tools = set_fields_tool({}, turn)
        client = FakeClient([[chunk(tool={"id": "c1", "name": "set_fields", "args": "{not json"})], [chunk("Sorry.")]])
        events = list(agent.run(client, "m", [{"role": "user", "content": "hi"}], tools, turn, "visitor-b"))
    assert events[-1] == {"type": "done", "text": "Sorry."}
    assert "error" in client.requests[1]["messages"][-1]["content"]


def test_quotes_inside_bilingual_text_are_kept():
    assert _clip('"Hello there"', 40) == "Hello there"                                 # wrapped around a single value: dropped
    both = 'Calls every blade "little sister" ||| 管每把剑叫"小妹"'
    assert _clip(both, 80) == both                                                      # each half keeps its own quotes


def test_a_reply_without_narration_is_kept_whole():
    turn = agent.Turn()
    if True:
        tools = set_fields_tool({}, turn)
        client = FakeClient([[chunk("Hello there "), chunk("friend ||| 你好，朋友")]])
        events = list(agent.run(client, "m", [{"role": "user", "content": "hi"}], tools, turn, "visitor-c"))
    assert all(e["type"] != "retract" for e in events)
    assert events[-1]["text"] == "Hello there friend ||| 你好，朋友"


def test_text_that_follows_tool_calls_in_the_same_round_is_not_the_reply():
    turn = agent.Turn()
    if True:
        tools = set_fields_tool({}, turn)
        client = FakeClient([
            [chunk(tool={"id": "c1", "name": "set_fields", "args": "{}"}), chunk("A first draft of the reply ||| 初稿")],
            [chunk("The real reply ||| 正式回复")],
        ])
        events = list(agent.run(client, "m", [{"role": "user", "content": "hi"}], tools, turn, "visitor-d"))
    assert "retract" in [e["type"] for e in events]
    assert events[-1]["text"] == "The real reply ||| 正式回复"


# ---------- the world, first impressions and tailored prompts ----------


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


def test_a_language_leaking_into_the_other_half_is_cut_out():
    # the model copies the history's "English / 中文" form into its English half
    assert bilingual.normalize("Start where the light is. / 从有光的地方开始。\n|||\n从有光的地方开始。") == "Start where the light is.\n|||\n从有光的地方开始。"
    # a Chinese paragraph sitting inside the English half
    messy = "Sit down.\n\n除了那件事——有人来。\n|||\n坐下。"
    assert bilingual.normalize(messy) == "Sit down.\n|||\n坐下。"
    # a Chinese name inside English is not a leak
    keep = "Tell Old Tuo / 老驼 I said hello.\n|||\n替我向老驼问好。"
    assert bilingual.normalize(keep) == keep
