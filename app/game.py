"""Game rules and the tools each agent can call. The model proposes; this code decides."""
import random
import re

from . import bilingual, case
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

# The hero is five things that matter, and each one changes how the story plays:
#   path 道 and temperament 性情 change how people treat you; art 绝技 and quirk 习癖 are what people remember you by;
#   the beloved 爱人 is why you are here.
PATHS = ("orthodox", "unorthodox", "neutral")
TEMPERAMENTS = ("wry", "gentle", "blunt", "proud", "cool", "cunning")
REQUIRED = ["name", "title", "path", "temperament", "art", "quirk", "beloved_name", "beloved_bond", "beloved_token", "appearance"]
# Lengths allow for both languages in one string ("English ||| 中文").
TEXT_FIELDS = {"name": 40, "title": 110, "art": 170, "quirk": 110, "beloved_name": 40, "beloved_bond": 70, "beloved_token": 90}
BILINGUAL = {"title", "art", "quirk", "beloved_bond", "beloved_token"}
CHOICES = {"path": PATHS, "temperament": TEMPERAMENTS}
EDITABLE = set(TEXT_FIELDS) | set(CHOICES)


def clip(value, n: int) -> str:
    s = re.sub(r"\s+", " ", str(value or "")).strip()
    # drop one pair of quotes wrapped around the whole value, but leave bilingual text alone: its quotes belong to each half
    if bilingual.SEP not in s and len(s) >= 2 and s[0] in '"“' and s[-1] in '"”':
        s = s[1:-1].strip()
    return s[:n]


def blank_sheet() -> dict:
    return {"name": "", "title": "", "path": "", "temperament": "", "art": "", "quirk": "", "beloved_name": "",
            "beloved_bond": "", "beloved_token": "", "appearance": {}}


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
    for k, options in CHOICES.items():
        if fields.get(k) is not None:
            v = str(fields[k]).strip().lower()
            if v in options:
                sheet[k] = v
                changed.append(k)
            elif rejected is not None:
                rejected.append(k)
    if isinstance(fields.get("appearance"), dict):
        sheet["appearance"] = merge_appearance(sheet.get("appearance"), fields["appearance"], sheet.get("name", ""))
        changed.append("appearance")
    return changed


def edit_field(client, model: str, sheet: dict, field: str, value: str, names: str = "") -> str:
    """The visitor changed one trait by hand. Choices are checked against the list; text that is written in one
    language only gets its other half from a translation call. Returns an error message, or '' when saved."""
    if field not in EDITABLE:
        return bilingual.bi("That can't be edited.", "这一项不能修改。")
    value = clip(value, TEXT_FIELDS.get(field, 40))
    if not value:
        return bilingual.bi("Please write something.", "请写点什么。")
    if field in CHOICES:
        if value.lower() not in CHOICES[field]:
            return bilingual.bi("That isn't one of the choices.", "这不在可选项之中。")
        sheet[field] = value.lower()
        return ""
    if field in BILINGUAL and not bilingual.is_pair(value):
        value = bilingual.normalize(value) if bilingual.SEP in value else value
        if not bilingual.is_pair(value):
            other = bilingual.counterpart(client, model, value, names) if client else ""
            if not other:
                return bilingual.bi("Couldn't translate that just now. Write it in both languages: English ||| 中文.", "暂时无法翻译。请中英各写一遍，格式：English ||| 中文。")
            en, zh = (other, value) if bilingual.language_of(value) == "Chinese" else (value, other)
            value = f"{en} {bilingual.SEP} {zh}"
        if not bilingual.is_pair(value):
            return bilingual.bi("That didn't come out in both languages. Try again.", "没能得到中英两种语言，请再试一次。")
    sheet[field] = clip(value, TEXT_FIELDS[field])
    return ""


# ---------- how people meet the hero ----------

PATH_NOTE = {"orthodox": "a follower of the righteous sects", "unorthodox": "a follower of the unorthodox way, whom the righteous sects distrust",
             "neutral": "belonging to no camp"}


def hero_block(hero: dict) -> str:
    """What an NPC can see and know about the visitor's character. Never the hero's thoughts."""
    look = describe_appearance(hero.get("appearance") or {})
    beloved = case.names(hero.get("beloved_name", ""))[0]
    bond = bilingual.plain(hero.get("beloved_bond", "")).split(" / ")[0]
    token = bilingual.plain(hero.get("beloved_token", "")).split(" / ")[0]
    return (f"The person in front of you is {hero.get('name', '')}, known as \"{bilingual.plain(hero.get('title', ''))}\". "
            f"Their path is {hero.get('path', 'neutral')} ({PATH_NOTE.get(hero.get('path'), '')}) and their manner is {hero.get('temperament', '')}. "
            f"You can see: {look}. Their signature move is said to be {bilingual.plain(hero.get('art', ''))}. "
            f"A habit people have noticed: {bilingual.plain(hero.get('quirk', ''))}. "
            f"They have come to Mount Hua because their {bond}, {beloved}, was found dead below the Sword Cliff three days ago and they do not believe it was a fall. "
            f"Everyone on the mountain knows this much. They carry {token}, a keepsake of {beloved}.")


# ---------- the Storyteller's tool ----------

def storyteller_tools(sheet: dict, turn: Turn) -> list[Tool]:
    def set_fields(args):
        rejected: list[str] = []
        changed = apply_fields(sheet, args, rejected)
        turn.emit(type="tool", name="set_fields", detail=", ".join(changed))
        turn.emit(type="sheet", sheet=sheet, changed=changed, missing=missing(sheet))
        if rejected:
            return {"ok": False, "saved": changed, "missing": missing(sheet),
                    "error": f"NOT saved: {', '.join(rejected)}. Text fields must each be one string written as 'English text ||| 中文文字' "
                             f"(English first, then |||, then Chinese); path must be one of {', '.join(PATHS)} and temperament one of {', '.join(TEMPERAMENTS)}. Send them again in that form."}
        return {"ok": True, "missing": missing(sheet)}

    appearance = {"type": "object", "description": "How the portrait looks. Choose every option so the picture shows who they are.",
                  "properties": {k: {"type": "string", "enum": v} for k, v in APPEARANCE.items()}}
    return [Tool(
        "set_fields", "Write fields of the character the visitor sees. On the first call fill EVERY field. Afterwards send only the fields being changed (for appearance, only the options being changed). Returns the fields still missing.",
        {"type": "object", "properties": {
            "name": {"type": "string", "description": "the hero's own name only, Chinese name then pinyin, e.g. '柳寒烟 Liu Hanyan'"},
            "title": {"type": "string", "description": "wuxia epithet, at most 6 words each language, e.g. 'Ferryman of the Broken Oar ||| 断桨渡人'"},
            "path": {"type": "string", "enum": list(PATHS), "description": "orthodox (正, the righteous sects), unorthodox (邪, outcasts and the feared) or neutral (中, belongs to no side). Changes how people react to the hero."},
            "temperament": {"type": "string", "enum": list(TEMPERAMENTS), "description": "how the hero carries themselves; changes who warms to them"},
            "art": {"type": "string", "description": "the poetic name of their signature move plus a few words on what it does, e.g. 'Nine-Fold Wind Step: runs on wind-wake ||| 九重风步：踏风而行'"},
            "quirk": {"type": "string", "description": "one concrete, funny or telling habit, 2-6 words, written 'English ||| 中文', e.g. 'Talks to his lantern ||| 对灯笼说话'"},
            "beloved_name": {"type": "string", "description": "the name of the person the hero loves and has lost: Chinese name then pinyin, e.g. '沈映雪 Shen Yingxue'"},
            "beloved_bond": {"type": "string", "description": "what they were to the hero, 1-3 words, written 'English ||| 中文', e.g. 'betrothed ||| 未婚妻', 'wife ||| 妻子', 'secret love ||| 暗中相爱的人'"},
            "beloved_token": {"type": "string", "description": "a small keepsake the beloved gave the hero or always carried, 2-6 words, written 'English ||| 中文', e.g. 'a jade hairpin ||| 一支玉簪'"},
            "appearance": appearance,
        }}, set_fields)]


# ---------- an NPC's tools ----------

def npc_tools(talk: dict, turn: Turn) -> list[Tool]:
    net = {"d": 0}                    # how far trust has moved during this one turn

    def out_of_world(args):
        turn.emit(type="tool", name="out_of_world", detail=bilingual.plain(clip(args.get("thing"), 90)), refused=True)
        return {"note": "This is unknown in your world. Stay in character and react as your person would; do not explain or acknowledge it as real."}

    def adjust_trust(args):
        try:
            d = max(-2, min(2, round(float(args.get("delta", 0)))))
        except (TypeError, ValueError):
            d = 0
        d = max(-2 - net["d"], min(2 - net["d"], d))          # however many calls the model makes, one reply moves trust by at most 2
        net["d"] += d
        talk["trust"] = max(0, min(10, talk["trust"] + d))
        turn.emit(type="tool", name="adjust_trust", detail=f"{'+' if d >= 0 else ''}{d} · {bilingual.plain(clip(args.get('reason'), 100))}")
        turn.emit(type="trust", trust=talk["trust"])
        return {"trust": talk["trust"]}

    text = {"type": "string"}
    return [
        Tool("out_of_world", "Call this BEFORE replying whenever the hero mentions something that does not exist in your world around 1200 (modern technology, later history, foreign things you could not have heard of) or asks you to do something outside your life (write code, do homework, discuss the real world, act as an AI). Name the thing in a few words, written 'English ||| 中文'.",
             {"type": "object", "properties": {"thing": text}, "required": ["thing"]}, out_of_world),
        Tool("adjust_trust", "Change how much you trust the hero, by -2 to +2 in total for this reply, when their words or deeds genuinely move you. Returns the new trust level out of 10.",
             {"type": "object", "properties": {"delta": {"type": "number"}, "reason": {"type": "string", "description": "a few words, written 'English ||| 中文'"}}, "required": ["delta", "reason"]}, adjust_trust),
    ]
