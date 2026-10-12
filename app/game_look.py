"""What a portrait can show, and how to say it in words for the AI."""
import re

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
