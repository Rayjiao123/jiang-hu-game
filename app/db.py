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

STATE_VERSION = 2          # bump whenever the shape of a saved night changes: older nights are dropped instead of breaking the page

SCHEMA = """
CREATE TABLE IF NOT EXISTS plays (
    visitor_id TEXT PRIMARY KEY,
    stage      TEXT NOT NULL,                 -- playing | moving | solved | dead
    found      TEXT NOT NULL DEFAULT '[]',    -- clue ids the hero holds
    beat       INTEGER NOT NULL DEFAULT 0,    -- how much of the night has gone
    msgs       INTEGER NOT NULL DEFAULT 0,    -- how many things the hero has said
    tier       INTEGER NOT NULL DEFAULT 0,    -- (unused)
    path       TEXT NOT NULL DEFAULT '',      -- the way out she chose: tunnel | kill
    cause      TEXT NOT NULL DEFAULT '',      -- how she died, when she did
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
CREATE TABLE IF NOT EXISTS talk_archive (               -- conversations from nights that were ended or restarted, kept to review the AI
    id          TEXT PRIMARY KEY,
    visitor_id  TEXT NOT NULL,
    npc_key     TEXT NOT NULL,
    trust       INTEGER NOT NULL,
    turns       TEXT NOT NULL DEFAULT '[]',
    updated_at  REAL NOT NULL,
    archived_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (                     -- what visitors did: one row per thing, no message text
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    visitor_id TEXT NOT NULL,
    kind       TEXT NOT NULL,
    data       TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS events_by_kind ON events (kind, ts);
CREATE INDEX IF NOT EXISTS events_by_visitor ON events (visitor_id, ts);
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
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(plays)")}      # a night saved by the earlier version lacks these
        for name, default in (("path", "''"), ("cause", "''"), ("state", "'{}'")):
            if name not in cols:
                conn.execute(f"ALTER TABLE plays ADD COLUMN {name} TEXT NOT NULL DEFAULT {default}")


# ---------- the night: one per visitor ----------

def get_play(conn, visitor_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM plays WHERE visitor_id = ?", (visitor_id,)).fetchone()
    if not r:
        return None
    if json.loads(r["state"] or "{}").get("v") != STATE_VERSION:       # a night saved by an earlier version of the game cannot be continued
        delete_play(conn, visitor_id)
        return None
    return {"visitor_id": r["visitor_id"], "stage": r["stage"], "found": json.loads(r["found"]), "beat": r["beat"], "msgs": r["msgs"],
            "tier": r["tier"], "path": r["path"], "cause": r["cause"], "turns": json.loads(r["turns"]), "ending": r["ending"],
            "state": json.loads(r["state"] or "{}")}


def log(conn, visitor_id: str, event: str, **data) -> None:
    """Record one thing a visitor did. Never message text: the numbers are for counting, the transcripts for reading."""
    conn.execute("INSERT INTO events (ts, visitor_id, kind, data) VALUES (?,?,?,?)", (time.time(), visitor_id, event, json.dumps(data, ensure_ascii=False)))


def new_play(conn, visitor_id: str, state: dict, stage: str = "rolling") -> dict:
    """Start again: any earlier night is closed (its conversations are archived) and a new one begins."""
    delete_play(conn, visitor_id)
    conn.execute("INSERT INTO plays (visitor_id, stage, state, updated_at) VALUES (?,?,?,?)",
                 (visitor_id, stage, json.dumps(state, ensure_ascii=False), time.time()))
    return get_play(conn, visitor_id)


def save_play(conn, g: dict) -> None:
    before = conn.execute("SELECT stage FROM plays WHERE visitor_id = ?", (g["visitor_id"],)).fetchone()
    if before and before["stage"] not in ("dead", "solved") and g["stage"] in ("dead", "solved"):
        st = g["state"]
        log(conn, g["visitor_id"], "end", stage=g["stage"], ending=g["cause"], beat=g["beat"], msgs=g["msgs"], won=g["stage"] == "solved",
            hp=st.get("hero", {}).get("hp", 0), fights=st.get("fights", 0), killer=st.get("killer", ""), rewards=sum(1 for n in st.get("npcs", {}).values() if n.get("rewarded")))
    conn.execute("UPDATE plays SET stage = ?, found = ?, beat = ?, msgs = ?, tier = ?, path = ?, cause = ?, turns = ?, ending = ?, state = ?, updated_at = ? WHERE visitor_id = ?",
                 (g["stage"], json.dumps(g["found"]), g["beat"], g["msgs"], g["tier"], g["path"], g["cause"], json.dumps(g["turns"], ensure_ascii=False),
                  g["ending"], json.dumps(g["state"], ensure_ascii=False), time.time(), g["visitor_id"]))


def delete_play(conn, visitor_id: str) -> None:
    """Close a night. Conversations are moved to the archive, not thrown away, so the AI's replies can still be reviewed."""
    play = conn.execute("SELECT stage, msgs, beat FROM plays WHERE visitor_id = ?", (visitor_id,)).fetchone()
    if play and play["stage"] not in ("dead", "solved"):
        log(conn, visitor_id, "abandoned", msgs=play["msgs"], beat=play["beat"])          # left, or started over, without finishing
    conn.execute("INSERT OR IGNORE INTO talk_archive (id, visitor_id, npc_key, trust, turns, updated_at, archived_at) "
                 "SELECT id, visitor_id, npc_key, trust, turns, updated_at, ? FROM talks WHERE visitor_id = ?", (time.time(), visitor_id))
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
