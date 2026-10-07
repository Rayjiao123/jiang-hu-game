"""Game rules and the tools each person can call. The model proposes; this code decides."""
import re

from . import bilingual, case
from .agent import Tool, Turn

# Everything a portrait can show. Characters pick from these lists and the page
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


def clip(value, n: int) -> str:
    s = re.sub(r"\s+", " ", str(value or "")).strip()
    return s[:n]


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
    return ", ".join(parts)


def start_trust(key: str) -> tuple[int, str]:
    """How much this person trusts the hero on first meeting, and why ('English ||| 中文')."""
    t = case.BY_KEY[key]["trust0"]
    if t <= 2:
        why = "They watch you the way you would watch a stranger at the door. ||| 对方看你，就像看门口的陌生人。"
    else:
        why = "A traveller caught by the storm, like them. ||| 和他们一样，是个被沙暴困住的旅人。"
    return t, why


def hero_block() -> str:
    """What a person in the inn can see and know about Qinghe. Never her inner thoughts."""
    h = case.HERO
    return (f"The person in front of you is {h['name']}, \"{bilingual.plain(h['title'])}\", a girl of about seventeen who has just come in out of the storm. "
            f"You can see: {describe_appearance(h['appearance'])}. She has a camel outside with a courier's saddle and she counts the exits when she walks into a room. "
            f"Her signature move is said to be {bilingual.plain(h['art'])}. She is quick, careful and stubborn, like someone who has had to look after herself. "
            f"Whatever you know beyond what you can see, you only know if the system tells you.")


# ---------- a person's tools ----------

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
