"""Game rules and the tools each agent can call. The model proposes; this code decides."""
import re

from . import config, db
from .agent import Tool, ToolError, Turn

REQUIRED = ["name", "title", "sect", "location", "alignment", "art", "traits", "speech", "voice_samples",
            "goal", "knowledge", "look", "greeting", "stats"]
TEXT_FIELDS = {"name": 40, "title": 80, "sect": 60, "location": 80, "art": 120, "speech": 360, "goal": 360,
               "knowledge": 360, "look": 360, "greeting": 300, "secret": 360}
STATS = ("neigong", "qinggong", "technique", "chivalry")
ALIGNMENTS = ("orthodox", "unorthodox", "neutral")
STARTING_TRUST = {"orthodox": 4, "unorthodox": 2, "neutral": 3}


def clip(value, n: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().strip('"“”')[:n]


def blank_sheet() -> dict:
    return {"name": "", "title": "", "sect": "", "location": "", "alignment": "", "art": "", "traits": [],
            "speech": "", "voice_samples": [], "goal": "", "knowledge": "", "look": "", "greeting": "",
            "secret": "", "stats": None, "bonds": [], "svg": ""}


def missing(sheet: dict) -> list[str]:
    return [k for k in REQUIRED if not sheet.get(k)]


def apply_fields(sheet: dict, fields: dict) -> list[str]:
    """Validate and write model-proposed fields onto a sheet. Returns the keys changed."""
    changed = []
    for k, n in TEXT_FIELDS.items():
        if fields.get(k) is not None:
            sheet[k] = clip(fields[k], n)
            changed.append(k)
    if fields.get("alignment") is not None:
        a = str(fields["alignment"]).lower()
        sheet["alignment"] = a if a in ALIGNMENTS else "neutral"
        changed.append("alignment")
    if isinstance(fields.get("traits"), list):
        sheet["traits"] = [t for t in (clip(x, 20) for x in fields["traits"]) if t][:4]
        changed.append("traits")
    if isinstance(fields.get("voice_samples"), list):
        sheet["voice_samples"] = [s for s in (clip(x, 200) for x in fields["voice_samples"]) if s][:4]
        changed.append("voice_samples")
    if isinstance(fields.get("stats"), dict):
        sheet["stats"] = {k: _stat(fields["stats"].get(k)) for k in STATS}
        changed.append("stats")
    if {"name", "look", "title", "art"} & set(changed):
        sheet["svg"] = ""          # the old portrait no longer matches
    return changed


def _stat(v) -> int:
    try:
        return max(1, min(10, round(float(v))))
    except (TypeError, ValueError):
        return 5


# ---------- the Storyteller's tools ----------

def storyteller_tools(conn, sheet: dict, turn: Turn) -> list[Tool]:
    def set_fields(args):
        changed = apply_fields(sheet, args)
        turn.emit(type="tool", name="set_fields", detail=", ".join(changed))
        turn.emit(type="sheet", sheet=sheet, changed=changed, missing=missing(sheet))
        return {"ok": True, "missing": missing(sheet)}

    def list_jianghu(_args):
        npcs = db.list_npcs(conn, 40)
        turn.emit(type="tool", name="list_jianghu", detail=f"{len(npcs)} NPCs")
        return [{"id": n["id"], "name": n["name"], "title": n.get("title"), "sect": n.get("sect"),
                 "location": n.get("location"), "alignment": n.get("alignment")} for n in npcs]

    def link_npc(args):
        other = db.get_npc(conn, str(args.get("id", "")))
        if not other:
            raise ToolError("No NPC with that id. Call list_jianghu for valid ids.")
        relation = clip(args.get("relation"), 30)
        sheet["bonds"] = [b for b in sheet["bonds"] if b["toId"] != other["id"]][:2] + [
            {"toId": other["id"], "toName": other["name"], "relation": relation}]
        turn.emit(type="tool", name="link_npc", detail=f"{relation} → {other['name']}")
        turn.emit(type="sheet", sheet=sheet, changed=["bonds"], missing=missing(sheet))
        return {"ok": True}

    text = {"type": "string"}
    return [
        Tool("set_fields", "Write one or more fields of the NPC scroll the visitor sees. Call whenever something is decided or strongly implied; include only the fields you are setting. Returns the fields still missing.",
             {"type": "object", "properties": {
                 "name": {"type": "string", "description": "Chinese name, optionally followed by pinyin, e.g. '柳寒烟 Liu Hanyan'"},
                 "title": {"type": "string", "description": "wuxia epithet, e.g. 'Ferryman of the Broken Oar'"},
                 "sect": {"type": "string", "description": "sect, guild or 'unaffiliated'"},
                 "location": {"type": "string", "description": "where the hero finds them"},
                 "alignment": {"type": "string", "enum": list(ALIGNMENTS)},
                 "art": {"type": "string", "description": "signature martial art with a poetic name"},
                 "traits": {"type": "array", "items": text, "description": "3 temperament words"},
                 "speech": {"type": "string", "description": "how they talk: register, verbal tics, favourite sayings"},
                 "voice_samples": {"type": "array", "items": text, "description": "exactly 3 short lines this NPC might say, in their own voice and in the visitor's language"},
                 "goal": {"type": "string", "description": "what they want and will pursue when talking to the hero"},
                 "knowledge": {"type": "string", "description": "what this person knows and does not know, given their station, schooling and travels, e.g. 'Knows every smuggler signal on the Grand Canal; cannot read; has never been north of the Yangtze.'"},
                 "look": {"type": "string", "description": "distinctive visual details for the portrait painter"},
                 "greeting": {"type": "string", "description": "their first line to the hero, in their voice"},
                 "secret": {"type": "string", "description": "a secret they only tell a trusted hero"},
                 "stats": {"type": "object", "properties": {k: {"type": "number"} for k in STATS}, "description": "each 1-10"},
             }}, set_fields),
        Tool("list_jianghu", "List NPCs other visitors already released into the world (id, name, epithet, sect, location, alignment). Call once early so you can propose a bond.",
             {"type": "object", "properties": {}}, list_jianghu),
        Tool("link_npc", "Record a bond (恩怨) between the new NPC and an existing one from list_jianghu. relation is short, e.g. 'sworn brother', 'former apprentice', 'owes a life debt to'.",
             {"type": "object", "properties": {"id": text, "relation": text}, "required": ["id", "relation"]}, link_npc),
    ]


# ---------- an NPC's tools ----------

def npc_tools(conn, npc: dict, secret: str, sess: dict, turn: Turn) -> list[Tool]:
    def out_of_world(args):
        turn.emit(type="tool", name="out_of_world", detail=clip(args.get("thing"), 50), refused=True)
        return {"note": "This is unknown in your world. Stay in character and react as your person would; do not explain or acknowledge it as real."}

    def adjust_trust(args):
        try:
            d = max(-2, min(2, round(float(args.get("delta", 0)))))
        except (TypeError, ValueError):
            d = 0
        sess["trust"] = max(0, min(10, sess["trust"] + d))
        turn.emit(type="tool", name="adjust_trust", detail=f"{'+' if d >= 0 else ''}{d} · {clip(args.get('reason'), 60)}")
        turn.emit(type="trust", trust=sess["trust"], revealed=sess["revealed"])
        return {"trust": sess["trust"]}

    def reveal_secret(_args):
        if not secret:
            raise ToolError("You have no secret.")
        if sess["trust"] < config.SECRET_TRUST_THRESHOLD:
            turn.emit(type="tool", name="reveal_secret", detail=f"refused · trust {sess['trust']}/{config.SECRET_TRUST_THRESHOLD}", refused=True)
            raise ToolError(f"You do not trust the hero enough yet (trust {sess['trust']}/10). Deflect in character; do not hint at the content.")
        sess["revealed"] = True
        turn.emit(type="tool", name="reveal_secret", detail="granted")
        turn.emit(type="trust", trust=sess["trust"], revealed=True)
        return {"secret": secret}

    def recall_person(args):
        q = clip(args.get("name"), 40).lower()
        others = [n for n in db.list_npcs(conn) if n["id"] != npc.get("id")]
        match = next((o for o in others if q and (q in o["name"].lower() or o["name"].lower().split(" ")[0] in q)), None)
        if not match:
            turn.emit(type="tool", name="recall_person", detail=f"{q} · unknown")
            raise ToolError("You have never heard of them.")
        bond = next((b["relation"] for b in npc.get("bonds") or [] if b["toId"] == match["id"]), None) or next(
            (f"they call you their {b['relation']}" for b in match.get("bonds") or [] if b["toId"] == npc.get("id")), None)
        turn.emit(type="tool", name="recall_person", detail=match["name"])
        return {k: match.get(k) for k in ("name", "title", "sect", "location", "alignment", "art")} | {"bond": bond}

    text = {"type": "string"}
    return [
        Tool("out_of_world", "Call this BEFORE replying whenever the hero mentions something that does not exist in your world around 1200 (modern technology, later history, foreign things you could not have heard of) or asks you to do something outside your life (write code, do homework, discuss the real world, act as an AI). Name the thing in a few words.",
             {"type": "object", "properties": {"thing": text}, "required": ["thing"]}, out_of_world),
        Tool("adjust_trust", "Change how much you trust the hero, by -2 to +2, when their words or deeds in this conversation genuinely move you. Most replies need no change. Returns the new trust level out of 10.",
             {"type": "object", "properties": {"delta": {"type": "number"}, "reason": {"type": "string", "description": "a few words"}}, "required": ["delta", "reason"]}, adjust_trust),
        Tool("reveal_secret", "Retrieve your own secret so you can tell it to the hero. Only works if you trust them enough; otherwise it fails and you must deflect in character.",
             {"type": "object", "properties": {}}, reveal_secret),
        Tool("recall_person", "Recall what you know of another person in the jianghu by name, for gossip, warnings or old grudges. Returns their epithet, sect, whereabouts, alignment and any bond you share.",
             {"type": "object", "properties": {"name": text}, "required": ["name"]}, recall_person),
    ]


def admirers(conn, npc_id: str) -> list[str]:
    """Bonds other NPCs declared toward this one."""
    return [f"{o['name']} calls you their {b['relation']}" for o in db.list_npcs(conn)
            for b in o.get("bonds") or [] if b.get("toId") == npc_id]
