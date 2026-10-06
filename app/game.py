"""Game rules and the tools each agent can call. The model proposes; this code decides."""
import random
import re

from . import bilingual, config, db, world
from .agent import Tool, ToolError, Turn

# Everything a portrait can show. The Storyteller picks from these lists and the page
# (static/portrait.js) draws the matching layers, so every character gets the same game-art look.
COLORS = ["ink", "crimson", "jade", "azure", "violet", "gold", "white", "ash", "pink"]
APPEARANCE = {
    "build": ["feminine", "masculine", "androgynous"],
    "age": ["young", "adult", "elder"],
    "skin": ["fair", "warm", "tan", "deep"],
    "hair_style": ["long", "ponytail", "bun", "twin_buns", "short", "wild", "braid", "bald"],
    "hair_color": ["black", "brown", "silver", "white", "red", "blue", "green"],
    "eyes": ["sharp", "soft", "sleepy", "wide"],
    "eye_color": ["black", "brown", "amber", "jade", "blue", "violet", "red"],
    "expression": ["calm", "smirk", "smile", "fierce", "weary"],
    "outfit": ["robe", "scholar", "fighter", "monk", "hermit", "noble"],
    "outfit_color": COLORS,
    "accent_color": COLORS,
    "headwear": ["none", "headband", "bamboo_hat", "scholar_cap", "hairpin", "flower", "crown"],
    "mark": ["none", "scar", "beard", "mask", "eyepatch", "forehead_mark"],
    "weapon": ["sword", "saber", "staff", "spear", "fan", "flute", "brush", "none"],
    "aura": ["flame", "ice", "wind", "petals", "lightning", "moon", "ink", "none"],
    "scene": ["bamboo", "mountains", "lanterns", "snow", "river"],
}

# The scroll shows eight things; speech, knowledge and appearance work behind the scenes.
REQUIRED = ["name", "title", "sect", "location", "region", "alignment", "art", "traits", "speech", "greeting",
            "goal", "knowledge", "secret", "appearance"]
# Lengths allow for both languages in one string ("English ||| 中文").
TEXT_FIELDS = {"name": 40, "title": 110, "sect": 90, "location": 110, "art": 170, "speech": 480, "goal": 360,
               "knowledge": 480, "greeting": 320, "secret": 360}
BILINGUAL = {"title", "sect", "location", "art", "speech", "greeting", "goal", "knowledge", "secret"}
ALIGNMENTS = ("orthodox", "unorthodox", "neutral")
STARTING_TRUST = {"orthodox": 4, "unorthodox": 2, "neutral": 3}


def starting_trust(npc: dict, hero: dict) -> tuple[int, str]:
    """How much an NPC trusts a particular hero on first meeting, and why (as 'English ||| 中文')."""
    trust = STARTING_TRUST.get(npc.get("alignment"), 3)
    n, h = npc.get("alignment"), hero.get("alignment")
    if h == n and h in ("orthodox", "unorthodox"):
        trust, why = trust + 1, "You walk the same path. ||| 道不同不相为谋，但你们走的是同一条路。"
    elif {n, h} == {"orthodox", "unorthodox"}:
        trust, why = trust - 2, "Your paths are opposed; they are wary of you. ||| 正邪殊途，他对你满怀戒心。"
    elif h == "neutral":
        why = "They cannot read you yet. ||| 他一时看不透你的来路。"
    else:
        why = "A stranger on the road. ||| 路上初逢的陌生人。"
    known = any(b.get("toId") == hero.get("id") for b in npc.get("bonds") or []) or \
        any(b.get("toId") == npc.get("id") for b in hero.get("bonds") or [])
    if known:
        trust, why = trust + 1, "You share a history. ||| 你们之间有一段旧事。"
    return max(0, min(10, trust)), why


def clip(value, n: int) -> str:
    s = re.sub(r"\s+", " ", str(value or "")).strip()
    # drop one pair of quotes wrapped around the whole value, but leave bilingual text alone: its quotes belong to each half
    if bilingual.SEP not in s and len(s) >= 2 and s[0] in '"“' and s[-1] in '"”':
        s = s[1:-1].strip()
    return s[:n]


def blank_sheet() -> dict:
    return {"name": "", "title": "", "sect": "", "location": "", "region": "", "alignment": "", "art": "", "traits": [],
            "speech": "", "greeting": "", "goal": "", "knowledge": "", "secret": "", "appearance": {}, "bonds": []}


def missing(sheet: dict) -> list[str]:
    return [k for k in REQUIRED if not sheet.get(k)]


def merge_appearance(current: dict | None, raw: dict, seed: str = "") -> dict:
    """Keep only valid choices. Anything the model left out is filled in (deterministically from the
    name) the first time, and left alone on later edits."""
    rng = random.Random(seed or "jianghu")
    out = dict(current or {})
    for key, options in APPEARANCE.items():
        value = str(raw.get(key, "")).strip().lower().replace(" ", "_") if isinstance(raw, dict) else ""
        if value in options:
            out[key] = value
        elif key not in out:
            out[key] = rng.choice(options)
    return out


def describe_appearance(a: dict) -> str:
    if not a:
        return ""
    hair = "a shaved head" if a.get("hair_style") == "bald" else f"{a.get('hair_color')} hair worn in a {a.get('hair_style', '').replace('_', ' ')} style"
    parts = [f"a {a.get('age')} {a.get('build')} figure", hair, f"{a.get('eyes')} {a.get('eye_color')} eyes",
             f"a {a.get('expression')} expression", f"wearing a {a.get('outfit_color')} {a.get('outfit')} outfit"]
    if a.get("headwear") not in (None, "none"):
        parts.append(f"with a {a['headwear'].replace('_', ' ')}")
    if a.get("mark") not in (None, "none"):
        parts.append(f"marked by {'a ' if a['mark'] != 'beard' else 'a long '}{a['mark'].replace('_', ' ')}")
    if a.get("weapon") not in (None, "none"):
        parts.append(f"carrying a {a['weapon']}")
    if a.get("aura") not in (None, "none"):
        parts.append(f"surrounded by {a['aura']}")
    return ", ".join(parts)


def apply_fields(sheet: dict, fields: dict, rejected: list | None = None) -> list[str]:
    """Validate and write model-proposed fields onto a sheet. Returns the keys changed.
    Fields that are not written in both languages are not saved; their names go into `rejected`."""
    changed = []
    for k, n in TEXT_FIELDS.items():
        if fields.get(k) is None:
            continue
        value = clip(fields[k], n)
        if k in BILINGUAL and not bilingual.is_pair(value):
            if rejected is not None:
                rejected.append(k)
            continue
        sheet[k] = value
        changed.append(k)
    if fields.get("region") is not None:
        if world.valid(fields["region"]):
            sheet["region"] = str(fields["region"]).strip().lower()
            changed.append("region")
        elif rejected is not None:
            rejected.append("region")
    if fields.get("alignment") is not None:
        a = str(fields["alignment"]).lower()
        sheet["alignment"] = a if a in ALIGNMENTS else "neutral"
        changed.append("alignment")
    if isinstance(fields.get("traits"), list):
        quirks = [t for t in (clip(x, 90) for x in fields["traits"]) if t][:3]
        if quirks and all(bilingual.is_pair(q) for q in quirks):
            sheet["traits"] = quirks
            changed.append("traits")
        elif rejected is not None:
            rejected.append("traits")
    if isinstance(fields.get("appearance"), dict):
        sheet["appearance"] = merge_appearance(sheet.get("appearance"), fields["appearance"], sheet.get("name", ""))
        changed.append("appearance")
    return changed


# ---------- the Storyteller's tools ----------

def storyteller_tools(conn, sheet: dict, turn: Turn) -> list[Tool]:
    def set_fields(args):
        rejected: list[str] = []
        changed = apply_fields(sheet, args, rejected)
        turn.emit(type="tool", name="set_fields", detail=", ".join(changed))
        turn.emit(type="sheet", sheet=sheet, changed=changed, missing=missing(sheet))
        if rejected:
            return {"ok": False, "saved": changed, "missing": missing(sheet),
                    "error": f"NOT saved: {', '.join(rejected)}. Text fields must each be one string written as 'English text ||| 中文文字' "
                             f"(English first, then |||, then Chinese); region must be one of: {', '.join(world.IDS)}. Send them again in that form."}
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
        relation = clip(args.get("relation"), 90)
        sheet["bonds"] = [b for b in sheet["bonds"] if b["toId"] != other["id"]][:2] + [
            {"toId": other["id"], "toName": other["name"], "relation": relation}]
        turn.emit(type="tool", name="link_npc", detail=f"{bilingual.plain(relation)} → {other['name']}")
        turn.emit(type="sheet", sheet=sheet, changed=["bonds"], missing=missing(sheet))
        return {"ok": True}

    text = {"type": "string"}
    appearance = {"type": "object", "description": "How the portrait looks. Choose every option so the picture shows who they are.",
                  "properties": {k: {"type": "string", "enum": v} for k, v in APPEARANCE.items()}}
    return [
        Tool("set_fields", "Write fields of the NPC scroll the visitor sees. On the first call fill EVERY field. Afterwards send only the fields being changed (for appearance, only the options being changed). Returns the fields still missing.",
             {"type": "object", "properties": {
                 "name": {"type": "string", "description": "the person's own name only, never their epithet or title: Chinese name then pinyin, e.g. '柳寒烟 Liu Hanyan'"},
                 "title": {"type": "string", "description": "wuxia epithet, at most 6 words each language, e.g. 'Ferryman of the Broken Oar ||| 断桨渡人'"},
                 "sect": {"type": "string", "description": "sect or guild name only, or unaffiliated, e.g. 'Emei Sect ||| 峨眉派' or 'Unaffiliated ||| 无门无派'"},
                 "location": {"type": "string", "description": "where the hero finds them, a short place name, e.g. 'Frost Bell Monastery ||| 霜铃寺'"},
                 "region": {"type": "string", "enum": world.IDS, "description": "which part of the jianghu they live in; the visitor's character starts the game here and others meet them here"},
                 "alignment": {"type": "string", "enum": list(ALIGNMENTS)},
                 "art": {"type": "string", "description": "the poetic name of their signature move plus a few words on what it does, e.g. 'Nine-Fold Wind Step: runs on wind-wake ||| 九重风步：踏风而行'"},
                 "traits": {"type": "array", "items": text, "description": "exactly 3 fun quirks, 2-5 words each, concrete and funny or telling, each written 'English ||| 中文', e.g. 'Never forgives a debt ||| 有债必讨', 'Talks to his lantern ||| 对灯笼说话'"},
                 "speech": {"type": "string", "description": "how they talk: register, verbal tic, a favourite saying. One or two sentences in each language. This drives the NPC agent."},
                 "greeting": {"type": "string", "description": "their first line to the hero, in their voice, one or two short sentences in each language; it should also work as their catchphrase"},
                 "goal": {"type": "string", "description": "what they want from the hero, one sentence in each language"},
                 "knowledge": {"type": "string", "description": "what this person knows and does not know, given their station, schooling and travels, e.g. 'Knows every smuggler signal on the Grand Canal; cannot read. ||| 熟知大运河上所有私盐信号；不识字。'"},
                 "secret": {"type": "string", "description": "a juicy secret they only tell a trusted hero, one sentence in each language"},
                 "appearance": appearance,
             }}, set_fields),
        Tool("list_jianghu", "List NPCs other visitors already released into the world (id, name, epithet, sect, location, alignment). Call once so you can propose a bond.",
             {"type": "object", "properties": {}}, list_jianghu),
        Tool("link_npc", "Record a bond (恩怨) between the new NPC and an existing one from list_jianghu. relation is 2-4 words written 'English ||| 中文', e.g. 'sworn brother ||| 结义兄弟', 'owes a life debt to ||| 欠其一命'.",
             {"type": "object", "properties": {"id": text, "relation": text}, "required": ["id", "relation"]}, link_npc),
    ]


# ---------- an NPC's tools ----------

def npc_tools(conn, npc: dict, secret: str, sess: dict, turn: Turn) -> list[Tool]:
    def out_of_world(args):
        turn.emit(type="tool", name="out_of_world", detail=bilingual.plain(clip(args.get("thing"), 90)), refused=True)
        return {"note": "This is unknown in your world. Stay in character and react as your person would; do not explain or acknowledge it as real."}

    def adjust_trust(args):
        try:
            d = max(-2, min(2, round(float(args.get("delta", 0)))))
        except (TypeError, ValueError):
            d = 0
        sess["trust"] = max(0, min(10, sess["trust"] + d))
        turn.emit(type="tool", name="adjust_trust", detail=f"{'+' if d >= 0 else ''}{d} · {bilingual.plain(clip(args.get('reason'), 100))}")
        turn.emit(type="trust", trust=sess["trust"], revealed=sess["revealed"])
        return {"trust": sess["trust"]}

    def reveal_secret(_args):
        if not secret:
            raise ToolError("You have no secret.")
        if sess["trust"] < config.SECRET_TRUST_THRESHOLD:
            turn.emit(type="tool", name="reveal_secret", detail=f"refused 拒绝 · trust 信任 {sess['trust']}/{config.SECRET_TRUST_THRESHOLD}", refused=True)
            raise ToolError(f"You do not trust the hero enough yet (trust {sess['trust']}/10). Deflect in character; do not hint at the content.")
        sess["revealed"] = True
        turn.emit(type="tool", name="reveal_secret", detail="granted 已透露")
        turn.emit(type="trust", trust=sess["trust"], revealed=True)
        return {"secret": secret}

    def recall_person(args):
        q = clip(args.get("name"), 40).lower()
        others = [n for n in db.list_npcs(conn) if n["id"] != npc.get("id")]
        match = next((o for o in others if q and (q in o["name"].lower() or o["name"].lower().split(" ")[0] in q)), None)
        if not match:
            turn.emit(type="tool", name="recall_person", detail=f"{q} · unknown 不认识")
            raise ToolError("You have never heard of them.")
        bond = next((b["relation"] for b in npc.get("bonds") or [] if b["toId"] == match["id"]), None) or next(
            (f"they call you their {b['relation']}" for b in match.get("bonds") or [] if b["toId"] == npc.get("id")), None)
        turn.emit(type="tool", name="recall_person", detail=match["name"])
        return {k: match.get(k) for k in ("name", "title", "sect", "location", "alignment", "art")} | {"bond": bond}

    text = {"type": "string"}
    return [
        Tool("out_of_world", "Call this BEFORE replying whenever the hero mentions something that does not exist in your world around 1200 (modern technology, later history, foreign things you could not have heard of) or asks you to do something outside your life (write code, do homework, discuss the real world, act as an AI). Name the thing in a few words, written 'English ||| 中文'.",
             {"type": "object", "properties": {"thing": text}, "required": ["thing"]}, out_of_world),
        Tool("adjust_trust", "Change how much you trust the hero, by -2 to +2, when their words or deeds in this conversation genuinely move you. Most replies need no change. Returns the new trust level out of 10.",
             {"type": "object", "properties": {"delta": {"type": "number"}, "reason": {"type": "string", "description": "a few words, written 'English ||| 中文'"}}, "required": ["delta", "reason"]}, adjust_trust),
        Tool("reveal_secret", "Retrieve your own secret so you can tell it to the hero. Only works if you trust them enough; otherwise it fails and you must deflect in character.",
             {"type": "object", "properties": {}}, reveal_secret),
        Tool("recall_person", "Recall what you know of another person in the jianghu by name, for gossip, warnings or old grudges. Returns their epithet, sect, whereabouts, alignment and any bond you share.",
             {"type": "object", "properties": {"name": text}, "required": ["name"]}, recall_person),
    ]


def admirers(conn, npc_id: str) -> list[str]:
    """Bonds other NPCs declared toward this one."""
    return [f"{o['name']} calls you their {b['relation']}" for o in db.list_npcs(conn)
            for b in o.get("bonds") or [] if b.get("toId") == npc_id]
