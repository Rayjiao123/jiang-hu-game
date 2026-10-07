"""Offline tests: no DeepSeek calls. A fake client replays scripted streams."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DEEPSEEK_API_KEY"] = ""

from app import agent, i18n  # noqa: E402
from app.agent import Tool  # noqa: E402


# ---------- three languages ----------

def test_fixed_text_holds_all_three_languages_and_the_server_picks_one():
    text = i18n.tr("Hello", "你好", "สวัสดี")
    assert i18n.parts(text) == ["Hello", "你好", "สวัสดี"] and i18n.complete(text)
    assert [i18n.pick(text, l) for l in ("en", "zh", "th")] == ["Hello", "你好", "สวัสดี"]
    assert i18n.pick(text, "fr") == "Hello" and i18n.valid("fr") == "en" and i18n.valid(None) == "en"
    assert i18n.plain(text) == "Hello"                                                 # prompts get the English part
    assert i18n.pick("No separator here", "th") == "No separator here"
    assert i18n.pick("Only ||| 只有两种", "th") == "Only"                              # a missing language falls back to English
    assert i18n.tr("Only English", "仅英文") .endswith("Only English")                  # and tr() fills a missing Thai with English


def test_localize_walks_a_whole_response():
    data = {"name": i18n.tr("Qinghe", "青禾", "ชิงเหอ"), "cast": [{"title": i18n.tr("Guard", "守卫", "ยาม"), "n": 3, "ok": True}], "plain": "text", "none": None}
    assert i18n.localize(data, "zh") == {"name": "青禾", "cast": [{"title": "守卫", "n": 3, "ok": True}], "plain": "text", "none": None}
    assert i18n.localize(data, "th")["cast"][0]["title"] == "ยาม"


def test_join_keeps_each_language_together():
    joined = i18n.join(i18n.tr("One.", "一。", "หนึ่ง"), i18n.tr("Two.", "二。", "สอง"))
    assert i18n.parts(joined) == ["One.\n\nTwo.", "一。\n\n二。", "หนึ่ง\n\nสอง"]


def test_a_fixed_text_is_complete_only_with_each_language_in_its_own_script():
    assert not i18n.complete("English only") and not i18n.complete("a b ||| 你好")
    assert not i18n.complete("Hello there ||| 你好 ||| still English here")
    assert i18n.complete("Hello there ||| 你好 ||| สวัสดี")


def test_a_reply_is_checked_against_the_language_that_was_asked_for():
    en, zh, th = "The wind is strong tonight, child. Stay inside.", "今晚风很大，孩子，待在屋里。", "คืนนี้ลมแรง เด็กน้อย อยู่ข้างในเถอะ"
    assert i18n.in_language(en, "en") and not i18n.in_language(zh, "en") and not i18n.in_language(th, "en")
    assert i18n.in_language(zh, "zh") and not i18n.in_language(en, "zh") and not i18n.in_language(th, "zh")
    assert i18n.in_language(th, "th") and not i18n.in_language(en, "th") and not i18n.in_language(zh, "th")
    assert i18n.in_language("Madam Shuang says 霜四娘 is near, and the wind is cold.", "en")       # a name in another script is fine
    assert i18n.in_language("老驼说：风很大，孩子。Tuo is kind.", "zh")


def test_what_the_model_writes_is_cleaned_before_it_is_shown():
    cleaned = i18n.clean_ai('Hm. <reveal_clue id="x" /> I mind camels.')
    assert "<" not in cleaned and "camels" in cleaned
    assert i18n.SEP not in i18n.clean_ai("A ||| B")


def test_chinese_characters_are_removed_from_thai_and_english_replies_but_not_from_chinese():
    thai = "ข้าเลี้ยงอูฐมา三十年 ใครผ่านด่านนี้ข้าจำได้หมด"
    assert i18n.clean_ai(thai, "th") == "ข้าเลี้ยงอูฐมา ใครผ่านด่านนี้ข้าจำได้หมด"
    assert i18n.clean_ai("Madam 霜四娘 is near。", "en") == "Madam is near" and i18n.clean_ai("She said “no”.", "en") == "She said “no”."
    assert i18n.clean_ai("三十年，我都在这里。", "zh") == "三十年，我都在这里。" and i18n.clean_ai("三十年", None) == "三十年"


def test_the_model_is_told_which_language_to_write():
    for lang, name in (("en", "English"), ("zh", "Simplified Chinese"), ("th", "Thai")):
        rule = i18n.reply_rule(lang)
        assert name in rule and "only" in rule and i18n.SEP in rule                                  # it names the language and forbids the separator
        assert ("no Chinese characters" in rule) == (lang != "zh")                                     # and keeps Chinese out of Thai and English
    assert i18n.reply_rule("xx") == i18n.reply_rule("en")


def set_fields_tool(sheet, turn):
    """A stand-in tool: writes a name onto a dict, and tells the page."""
    def run(args):
        sheet.update({k: v for k, v in args.items() if k == "name"})
        turn.emit(type="tool", name="set_fields", detail="name")
        turn.emit(type="sheet", sheet=sheet)
        return {"ok": True}
    return [Tool("set_fields", "write fields", {"type": "object", "properties": {"name": {"type": "string"}}}, run)]


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


def test_a_reply_without_narration_is_kept_whole():
    turn = agent.Turn()
    if True:
        tools = set_fields_tool({}, turn)
        client = FakeClient([[chunk("Hello there "), chunk("friend")]])
        events = list(agent.run(client, "m", [{"role": "user", "content": "hi"}], tools, turn, "visitor-c"))
    assert all(e["type"] != "retract" for e in events)
    assert events[-1]["text"] == "Hello there friend"


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
