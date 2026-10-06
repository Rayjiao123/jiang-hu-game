"""The visitor's journey through the API, with the model faked."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "flow.db")
os.environ["DEEPSEEK_API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config, db, game, main  # noqa: E402


def chunk(content=None):
    return NS(choices=[NS(delta=NS(content=content, tool_calls=None))])


class FakeLLM:
    """Answers every request with a fixed bilingual reply, and records what it was sent."""
    def __init__(self):
        self.requests = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        if kw.get("stream"):
            return iter([chunk("Welcome, traveller. ||| 欢迎，旅人。")])
        system = kw["messages"][0]["content"]
        if "translate" in system.lower():
            return NS(choices=[NS(message=NS(content="翻译后的话" if "into Chinese" in system else "Translated words"))])
        return NS(choices=[NS(message=NS(content=json.dumps({"verdict": "allow", "reason": ""})))])


@pytest.fixture
def api(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(main, "llm", lambda: llm)
    c = TestClient(main.app)
    c.llm = llm
    return c


def character(name, alignment="orthodox", region="emei"):
    s = game.blank_sheet()
    both = {k: f"{k} text ||| {k}文字" for k in game.BILINGUAL}
    game.apply_fields(s, both | {"name": name, "region": region, "alignment": alignment,
                                 "traits": ["bold ||| 勇", "calm ||| 静", "wry ||| 俏"], "secret": "hidden thing ||| 秘事"})
    game.apply_fields(s, {"appearance": {}})
    return s


def make_hero(api, name="苏灵 Su Ling", alignment="orthodox"):
    with db.session() as conn:
        draft_id = db.create_draft(conn, api.cookies.get("vid") or "seed", character(name, alignment))
    return draft_id


def become(api, name="苏灵 Su Ling", alignment="orthodox"):
    api.get("/api/status")                                   # gets the visitor cookie
    vid = api.cookies.get("vid")
    with db.session() as conn:
        draft_id = db.create_draft(conn, vid, character(name, alignment))
    r = api.post(f"/api/drafts/{draft_id}/release", json={"creator_name": "Tester"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def add_npc(name="Old Wu", alignment="unorthodox", region="huashan"):
    with db.session() as conn:
        return db.insert_npc(conn, character(name, alignment, region), "other-visitor", "Ray")


def test_no_character_yet_means_no_conversations(api):
    api.get("/api/status")
    npc = add_npc()
    assert api.get("/api/me").json() == {"hero": None}
    r = api.post("/api/sessions", json={"npc_id": npc})
    assert r.status_code == 409 and "character" in r.json()["detail"]


def test_releasing_a_character_makes_it_the_one_you_play(api):
    hero = become(api)
    me = api.get("/api/me").json()["hero"]
    assert me["id"] == hero and me["name"] == "苏灵 Su Ling" and me["secret"] == "hidden thing ||| 秘事"
    assert me["region"] == "emei"
    assert hero in {n["id"] for n in api.get("/api/npcs").json()["npcs"]}      # and others can meet them
    api.post("/api/me/reset")
    assert api.get("/api/me").json() == {"hero": None}
    assert hero in {n["id"] for n in api.get("/api/npcs").json()["npcs"]}      # they stay in the world


def test_public_cards_carry_a_region_and_no_secret(api):
    npc = add_npc()
    card = next(n for n in api.get("/api/npcs").json()["npcs"] if n["id"] == npc)
    assert card["region"] == "huashan" and "secret" not in card and "hidden thing" not in json.dumps(card, ensure_ascii=False)


def test_a_conversation_starts_with_a_first_impression_and_resumes(api):
    become(api, alignment="unorthodox")
    npc = add_npc(alignment="orthodox")
    first = api.post("/api/sessions", json={"npc_id": npc}).json()
    assert first["fresh"] and first["turns"] == [] and first["trust"] == game.STARTING_TRUST["orthodox"] - 2
    assert "|||" in first["impression"]

    opened = api.post(f"/api/sessions/{first['id']}/open")
    assert opened.status_code == 200 and "Welcome, traveller." in opened.text
    assert api.post(f"/api/sessions/{first['id']}/open").status_code == 409        # speaks first only once

    again = api.post("/api/sessions", json={"npc_id": npc}).json()
    assert again["id"] == first["id"] and not again["fresh"]                       # the same conversation continues
    assert [t["role"] for t in again["turns"]] == ["assistant"]                    # the hidden "approaches you" line is not shown


def test_the_npc_is_told_who_it_is_talking_to(api):
    become(api, name="柳寒烟 Liu Hanyan", alignment="unorthodox")
    npc = add_npc(alignment="orthodox")
    sid = api.post("/api/sessions", json={"npc_id": npc}).json()["id"]
    api.llm.requests.clear()
    r = api.post(f"/api/sessions/{sid}/chat", json={"message": "Good day, old friend."})
    assert r.status_code == 200
    system = api.llm.requests[-1]["messages"][0]["content"]
    assert "柳寒烟 Liu Hanyan" in system and "unorthodox" in system
    assert "hidden thing" not in system.split("The person in front of you")[1].split("Rules:")[0]   # never the hero's secret


def test_your_own_lines_are_translated_and_remembered_in_both_languages(api):
    become(api)
    npc = add_npc()
    sid = api.post("/api/sessions", json={"npc_id": npc}).json()["id"]
    r = api.post(f"/api/sessions/{sid}/chat", json={"message": "Good day, old friend."})
    users = [json.loads(l[5:]) for l in r.text.split("\n\n") if l.startswith("data:")]
    assert users[0]["type"] == "user" and users[0]["text"] == "Good day, old friend. ||| 翻译后的话"
    again = api.post("/api/sessions", json={"npc_id": npc}).json()
    assert again["turns"][0] == {"role": "user", "content": "Good day, old friend. ||| 翻译后的话"}


def test_you_cannot_talk_to_yourself_or_to_a_stranger_who_left(api):
    hero = become(api)
    assert api.post("/api/sessions", json={"npc_id": hero}).status_code == 400
    assert api.post("/api/sessions", json={"npc_id": "nobody"}).status_code == 404


def test_conversations_belong_to_the_visitor_who_started_them(api):
    become(api)
    npc = add_npc()
    sid = api.post("/api/sessions", json={"npc_id": npc}).json()["id"]
    other = TestClient(main.app)
    other.llm = api.llm
    assert other.post(f"/api/sessions/{sid}/chat", json={"message": "hello"}).status_code == 404


def test_the_page_stamps_its_scripts_with_a_version(api):
    r = api.get("/")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    import re
    assets = re.findall(r'(?:src|href)="(/[\w.-]+\.(?:js|css))\?v=(\d+)"', r.text)
    assert {a for a, _ in assets} >= {"/app.js", "/style.css", "/portrait.js", "/scenes.js", "/map.js"}
    assert len({v for _, v in assets}) == 1                                     # one version for every file
    assert 'id="screen-loading"' in r.text                                      # never a blank page


def test_the_world_endpoint_lists_every_region(api):
    regions = api.get("/api/world").json()["regions"]
    assert len(regions) == 12 and {"id", "en", "zh", "x", "y", "desc_en", "desc_zh", "scene"} <= set(regions[0])
