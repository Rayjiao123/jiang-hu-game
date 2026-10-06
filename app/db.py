"""SQLite storage. One row per visitor holds their case (character, clues found, accusations left);
one row per conversation holds the trust and the lines spoken. Nothing is shared between visitors.

Databases made by the earlier shared-world version still contain its tables (npcs, drafts, players,
sessions); they are simply no longer used."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    visitor_id TEXT PRIMARY KEY,
    stage      TEXT NOT NULL,                 -- creating | playing | accused | solved | lost
    hero       TEXT NOT NULL,                 -- JSON: the character sheet
    turns      TEXT NOT NULL DEFAULT '[]',    -- the Storyteller conversation
    found      TEXT NOT NULL DEFAULT '[]',    -- clue ids the hero holds
    attempts   INTEGER NOT NULL DEFAULT 3,
    ending     TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS talks (
    id         TEXT PRIMARY KEY,
    visitor_id TEXT NOT NULL,
    npc_key    TEXT NOT NULL,
    trust      INTEGER NOT NULL,
    turns      TEXT NOT NULL DEFAULT '[]',
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS talks_by_visitor ON talks (visitor_id, npc_key);
"""


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def connect() -> sqlite3.Connection:
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with session() as conn:
        conn.executescript(SCHEMA)


# ---------- the case: one per visitor ----------

def get_game(conn, visitor_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM games WHERE visitor_id = ?", (visitor_id,)).fetchone()
    if not r:
        return None
    return {"visitor_id": r["visitor_id"], "stage": r["stage"], "hero": json.loads(r["hero"]), "turns": json.loads(r["turns"]),
            "found": json.loads(r["found"]), "attempts": r["attempts"], "ending": r["ending"]}


def new_game(conn, visitor_id: str, sheet: dict) -> dict:
    """Start again: any earlier case and its conversations are dropped."""
    conn.execute("DELETE FROM talks WHERE visitor_id = ?", (visitor_id,))
    conn.execute("DELETE FROM games WHERE visitor_id = ?", (visitor_id,))
    conn.execute("INSERT INTO games (visitor_id, stage, hero, updated_at) VALUES (?,?,?,?)",
                 (visitor_id, "creating", json.dumps(sheet, ensure_ascii=False), time.time()))
    return get_game(conn, visitor_id)


def save_game(conn, g: dict) -> None:
    conn.execute("UPDATE games SET stage = ?, hero = ?, turns = ?, found = ?, attempts = ?, ending = ?, updated_at = ? WHERE visitor_id = ?",
                 (g["stage"], json.dumps(g["hero"], ensure_ascii=False), json.dumps(g["turns"], ensure_ascii=False),
                  json.dumps(g["found"]), g["attempts"], g["ending"], time.time(), g["visitor_id"]))


def delete_game(conn, visitor_id: str) -> None:
    conn.execute("DELETE FROM talks WHERE visitor_id = ?", (visitor_id,))
    conn.execute("DELETE FROM games WHERE visitor_id = ?", (visitor_id,))


# ---------- conversations: one per (visitor, person), kept between visits ----------

def find_talk(conn, visitor_id: str, npc_key: str) -> dict | None:
    r = conn.execute("SELECT * FROM talks WHERE visitor_id = ? AND npc_key = ? ORDER BY updated_at DESC LIMIT 1",
                     (visitor_id, npc_key)).fetchone()
    return _talk(r) if r else None


def create_talk(conn, visitor_id: str, npc_key: str, trust: int) -> dict:
    tid = new_id()
    conn.execute("INSERT INTO talks (id, visitor_id, npc_key, trust, updated_at) VALUES (?,?,?,?,?)",
                 (tid, visitor_id, npc_key, trust, time.time()))
    return get_talk(conn, tid, visitor_id)


def get_talk(conn, tid: str, visitor_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM talks WHERE id = ? AND visitor_id = ?", (tid, visitor_id)).fetchone()
    return _talk(r) if r else None


def _talk(r) -> dict:
    return {"id": r["id"], "npc_key": r["npc_key"], "trust": r["trust"], "turns": json.loads(r["turns"])}


def save_talk(conn, t: dict) -> None:
    conn.execute("UPDATE talks SET trust = ?, turns = ?, updated_at = ? WHERE id = ?",
                 (t["trust"], json.dumps(t["turns"], ensure_ascii=False), time.time(), t["id"]))
