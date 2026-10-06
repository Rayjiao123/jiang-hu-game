"""Moderation and admin tests. Offline: the model is faked."""
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

os.environ.setdefault("DATABASE_PATH", str(Path(tempfile.mkdtemp()) / "test.db"))
os.environ.setdefault("SEED_WORLD", "0")
os.environ.setdefault("DEEPSEEK_API_KEY", "")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import bilingual, config, db, game, moderation  # noqa: E402
from app.main import app  # noqa: E402


class Reply:
    def __init__(self, content=None, error=None):
        self.content, self.error, self.calls = content, error, 0
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return NS(choices=[NS(message=NS(content=self.content))])


def npc(**fields):
    s = game.blank_sheet()
    game.apply_fields(s, {"name": "Old Wu", "speech": "gruff ||| 粗声粗气", **fields})
    return s


def test_moderation_allows_and_blocks():
    assert moderation.check(Reply('{"verdict": "allow", "reason": ""}'), "m", npc()) == ("allow", "")
    verdict, reason = moderation.check(Reply('{"verdict": "block", "reason": "Uses 郭靖 from Jin Yong."}'), "m", npc())
    assert verdict == "block" and "郭靖" in reason


def test_links_are_blocked_without_asking_the_model():
    client = Reply('{"verdict": "allow"}')
    verdict, reason = moderation.check(client, "m", npc(greeting="Visit www.example.com! ||| 来访问 www.example.com！"))
    assert verdict == "block" and bilingual.is_pair(reason)       # the creator is told why, in both languages
    assert client.calls == 0


def test_moderation_failure_means_human_review_not_a_pass():
    assert moderation.check(Reply(error=RuntimeError("timeout")), "m", npc())[0] == "review"
    assert moderation.check(Reply("sure, looks fine"), "m", npc())[0] == "review"
    assert moderation.check(None, "m", npc())[0] == "review"


def test_hidden_npcs_disappear_from_public_views():
    db.init()
    with db.session() as conn:
        live = db.insert_npc(conn, npc(name="Live One"), "v", "")
        hidden = db.insert_npc(conn, npc(name="Hidden One"), "v", "", hidden=True, flag="Automatic check unavailable.")
        ids = {n["id"] for n in db.list_npcs(conn)}
        assert live in ids and hidden not in ids
        assert db.get_npc(conn, hidden) is None
        assert db.get_npc(conn, hidden, include_hidden=True)["flag"] == "Automatic check unavailable."


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "plum-blossom")
    return TestClient(app)


def test_admin_requires_password(client):
    assert client.get("/api/admin/npcs").status_code == 401
    assert client.get("/api/admin/npcs", headers={"authorization": "Bearer wrong"}).status_code == 401


def test_admin_is_off_without_a_password(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    assert TestClient(app).get("/api/admin/npcs", headers={"authorization": "Bearer "}).status_code == 404


def test_admin_hide_restore_delete(client):
    auth = {"authorization": "Bearer plum-blossom"}
    with db.session() as conn:
        npc_id = db.insert_npc(conn, npc(name="Target", secret="buried gold ||| 埋着的金子"), "v", "Ray")
    listed = client.get("/api/admin/npcs", headers=auth).json()["npcs"]
    assert next(n for n in listed if n["id"] == npc_id)["secret"] == "buried gold ||| 埋着的金子"

    assert client.post(f"/api/admin/npcs/{npc_id}/visibility", json={"hidden": True}, headers=auth).status_code == 200
    assert npc_id not in {n["id"] for n in client.get("/api/npcs").json()["npcs"]}
    client.post(f"/api/admin/npcs/{npc_id}/visibility", json={"hidden": False}, headers=auth)
    assert npc_id in {n["id"] for n in client.get("/api/npcs").json()["npcs"]}

    assert client.delete(f"/api/admin/npcs/{npc_id}", headers=auth).status_code == 200
    assert npc_id not in {n["id"] for n in client.get("/api/admin/npcs", headers=auth).json()["npcs"]}
    assert "buried gold" not in json.dumps(client.get("/api/admin/export", headers=auth).json())
