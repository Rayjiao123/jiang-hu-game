"""SQLite storage. Public NPC cards and private secrets live in separate tables,
so an endpoint that lists NPCs can never leak a secret by accident."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from . import config, world

SCHEMA = """
CREATE TABLE IF NOT EXISTS npcs (
    id           TEXT PRIMARY KEY,
    created_at   REAL NOT NULL,
    creator_id   TEXT NOT NULL,
    creator_name TEXT NOT NULL DEFAULT '',
    card         TEXT NOT NULL,          -- JSON: everything except the secret
    svg          TEXT NOT NULL DEFAULT '',
    hidden       INTEGER NOT NULL DEFAULT 0,
    flag         TEXT NOT NULL DEFAULT ''  -- why it is hidden / needs review
);
CREATE TABLE IF NOT EXISTS npc_secrets (
    npc_id TEXT PRIMARY KEY REFERENCES npcs(id),
    secret TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id         TEXT PRIMARY KEY,
    visitor_id TEXT NOT NULL,
    sheet      TEXT NOT NULL,            -- JSON, includes the secret (the creator may see it)
    turns      TEXT NOT NULL DEFAULT '[]',
    released   TEXT,                     -- npc id once released
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS players (
    visitor_id TEXT PRIMARY KEY,         -- the character this visitor plays as
    draft_id   TEXT NOT NULL,
    npc_id     TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    visitor_id TEXT NOT NULL,
    npc_id     TEXT,                     -- the character being talked to
    draft_id   TEXT,                     -- (unused since rehearsals were replaced by playing a character)
    hero_id    TEXT,                     -- the visitor's own character in this conversation
    trust      INTEGER NOT NULL,
    revealed   INTEGER NOT NULL DEFAULT 0,
    turns      TEXT NOT NULL DEFAULT '[]',
    updated_at REAL NOT NULL
);
"""

PUBLIC_FIELDS = ("name", "title", "sect", "location", "alignment", "art", "traits", "greeting", "goal", "bonds", "appearance")


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
        # databases created before moderation existed lack these columns
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(npcs)")}
        if "hidden" not in cols:
            conn.execute("ALTER TABLE npcs ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")
        if "flag" not in cols:
            conn.execute("ALTER TABLE npcs ADD COLUMN flag TEXT NOT NULL DEFAULT ''")
        scols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)")}
        if "hero_id" not in scols:
            conn.execute("ALTER TABLE sessions ADD COLUMN hero_id TEXT")


# ---------- NPCs ----------

def list_npcs(conn, limit: int = 200, include_hidden: bool = False) -> list[dict]:
    where = "" if include_hidden else "WHERE hidden = 0"
    rows = conn.execute(f"SELECT * FROM npcs {where} ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_npc(r) for r in rows]


def get_npc(conn, npc_id: str, include_hidden: bool = False) -> dict | None:
    r = conn.execute("SELECT * FROM npcs WHERE id = ?", (npc_id,)).fetchone()
    if not r or (r["hidden"] and not include_hidden):
        return None
    return _npc(r)


def set_hidden(conn, npc_id: str, hidden: bool, flag: str = "") -> bool:
    cur = conn.execute("UPDATE npcs SET hidden = ?, flag = ? WHERE id = ?", (int(hidden), flag, npc_id))
    return cur.rowcount > 0


def delete_npc(conn, npc_id: str) -> bool:
    conn.execute("DELETE FROM npc_secrets WHERE npc_id = ?", (npc_id,))
    return conn.execute("DELETE FROM npcs WHERE id = ?", (npc_id,)).rowcount > 0


def get_secret(conn, npc_id: str) -> str:
    r = conn.execute("SELECT secret FROM npc_secrets WHERE npc_id = ?", (npc_id,)).fetchone()
    return r["secret"] if r else ""


def _npc(r) -> dict:
    return {"id": r["id"], "created_at": r["created_at"], "creator_name": r["creator_name"],
            "svg": r["svg"], "hidden": bool(r["hidden"]), "flag": r["flag"], **json.loads(r["card"])}


def public_card(npc: dict) -> dict:
    """What any visitor may see."""
    out = {k: npc.get(k) for k in PUBLIC_FIELDS}
    out.update(id=npc["id"], svg=npc.get("svg", ""), creator_name=npc.get("creator_name", ""),
               created_at=npc.get("created_at"), has_secret=bool(npc.get("has_secret")),
               region=world.region_for(npc))
    return out


def insert_npc(conn, sheet: dict, creator_id: str, creator_name: str, hidden: bool = False, flag: str = "") -> str:
    npc_id = new_id()
    secret = sheet.get("secret", "")
    card = {k: v for k, v in sheet.items() if k not in ("secret", "svg")}
    card["has_secret"] = bool(secret)
    conn.execute("INSERT INTO npcs (id, created_at, creator_id, creator_name, card, svg, hidden, flag) VALUES (?,?,?,?,?,?,?,?)",
                 (npc_id, time.time(), creator_id, creator_name, json.dumps(card, ensure_ascii=False),
                  sheet.get("svg", ""), int(hidden), flag))
    if secret:
        conn.execute("INSERT INTO npc_secrets (npc_id, secret) VALUES (?,?)", (npc_id, secret))
    return npc_id


# ---------- drafts ----------

def create_draft(conn, visitor_id: str, sheet: dict) -> str:
    draft_id = new_id()
    conn.execute("INSERT INTO drafts (id, visitor_id, sheet, updated_at) VALUES (?,?,?,?)",
                 (draft_id, visitor_id, json.dumps(sheet, ensure_ascii=False), time.time()))
    return draft_id


def get_draft(conn, draft_id: str, visitor_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM drafts WHERE id = ? AND visitor_id = ?", (draft_id, visitor_id)).fetchone()
    if not r:
        return None
    return {"id": r["id"], "sheet": json.loads(r["sheet"]), "turns": json.loads(r["turns"]), "released": r["released"]}


def save_draft(conn, draft: dict) -> None:
    conn.execute("UPDATE drafts SET sheet = ?, turns = ?, released = ?, updated_at = ? WHERE id = ?",
                 (json.dumps(draft["sheet"], ensure_ascii=False), json.dumps(draft["turns"], ensure_ascii=False),
                  draft.get("released"), time.time(), draft["id"]))


# ---------- the character a visitor plays ----------

def set_player(conn, visitor_id: str, draft_id: str, npc_id: str) -> None:
    conn.execute("INSERT INTO players (visitor_id, draft_id, npc_id, updated_at) VALUES (?,?,?,?) "
                 "ON CONFLICT(visitor_id) DO UPDATE SET draft_id = excluded.draft_id, npc_id = excluded.npc_id, updated_at = excluded.updated_at",
                 (visitor_id, draft_id, npc_id, time.time()))


def get_player(conn, visitor_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM players WHERE visitor_id = ?", (visitor_id,)).fetchone()
    return {"draft_id": r["draft_id"], "npc_id": r["npc_id"]} if r else None


def clear_player(conn, visitor_id: str) -> None:
    conn.execute("DELETE FROM players WHERE visitor_id = ?", (visitor_id,))


# ---------- conversation sessions: one per (visitor, their character, the NPC), kept between visits ----------

def find_session(conn, visitor_id: str, hero_id: str, npc_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM sessions WHERE visitor_id = ? AND hero_id = ? AND npc_id = ? ORDER BY updated_at DESC LIMIT 1",
                     (visitor_id, hero_id, npc_id)).fetchone()
    return _session(r) if r else None


def create_session(conn, visitor_id: str, trust: int, npc_id: str, hero_id: str) -> str:
    sid = new_id()
    conn.execute("INSERT INTO sessions (id, visitor_id, npc_id, hero_id, trust, updated_at) VALUES (?,?,?,?,?,?)",
                 (sid, visitor_id, npc_id, hero_id, trust, time.time()))
    return sid


def get_session(conn, sid: str, visitor_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM sessions WHERE id = ? AND visitor_id = ?", (sid, visitor_id)).fetchone()
    return _session(r) if r else None


def _session(r) -> dict:
    return {"id": r["id"], "npc_id": r["npc_id"], "hero_id": r["hero_id"], "trust": r["trust"],
            "revealed": bool(r["revealed"]), "turns": json.loads(r["turns"])}


def save_session(conn, s: dict) -> None:
    conn.execute("UPDATE sessions SET trust = ?, revealed = ?, turns = ?, updated_at = ? WHERE id = ?",
                 (s["trust"], int(s["revealed"]), json.dumps(s["turns"], ensure_ascii=False), time.time(), s["id"]))
