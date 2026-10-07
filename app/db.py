"""SQLite storage. One row per visitor holds their night (clues found, the clock, how it ended); one row
per conversation holds the trust and the lines spoken. Nothing is shared between visitors.

Databases made by earlier versions still contain their tables (npcs, drafts, players, sessions, games);
they are simply no longer used."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS plays (
    visitor_id TEXT PRIMARY KEY,
    stage      TEXT NOT NULL,                 -- playing | moving | solved | lost
    found      TEXT NOT NULL DEFAULT '[]',    -- clue ids the hero holds
    beat       INTEGER NOT NULL DEFAULT 0,    -- how much of the night has gone
    msgs       INTEGER NOT NULL DEFAULT 0,    -- how many things the hero has said
    tier       INTEGER NOT NULL DEFAULT 0,    -- how well the escape was prepared
    turns      TEXT NOT NULL DEFAULT '[]',    -- the conversation with the game master
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


# ---------- the night: one per visitor ----------

def get_play(conn, visitor_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM plays WHERE visitor_id = ?", (visitor_id,)).fetchone()
    if not r:
        return None
    return {"visitor_id": r["visitor_id"], "stage": r["stage"], "found": json.loads(r["found"]), "beat": r["beat"], "msgs": r["msgs"],
            "tier": r["tier"], "turns": json.loads(r["turns"]), "ending": r["ending"]}


def new_play(conn, visitor_id: str, found: list[str]) -> dict:
    """Start again: any earlier night and its conversations are dropped."""
    delete_play(conn, visitor_id)
    conn.execute("INSERT INTO plays (visitor_id, stage, found, updated_at) VALUES (?,?,?,?)",
                 (visitor_id, "playing", json.dumps(found), time.time()))
    return get_play(conn, visitor_id)


def save_play(conn, g: dict) -> None:
    conn.execute("UPDATE plays SET stage = ?, found = ?, beat = ?, msgs = ?, tier = ?, turns = ?, ending = ?, updated_at = ? WHERE visitor_id = ?",
                 (g["stage"], json.dumps(g["found"]), g["beat"], g["msgs"], g["tier"], json.dumps(g["turns"], ensure_ascii=False),
                  g["ending"], time.time(), g["visitor_id"]))


def delete_play(conn, visitor_id: str) -> None:
    conn.execute("DELETE FROM talks WHERE visitor_id = ?", (visitor_id,))
    conn.execute("DELETE FROM plays WHERE visitor_id = ?", (visitor_id,))


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
