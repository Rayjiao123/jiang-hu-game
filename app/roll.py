"""Random characters. The dice live here, in code, because a model left to pick "a random
character" keeps returning the same lantern seller. We choose a role, a place, a twist and a
few visual cues, then ask the Storyteller to build someone from them."""
import random

from . import game

ROLES = [
    "wandering swordswoman", "drunken monk", "retired escort-agency captain", "poison-master's apprentice",
    "teahouse storyteller", "salt smuggler", "disgraced court physician", "blind lute player",
    "beggar-guild elder", "bandit chief with a conscience", "bamboo-grove hermit", "Mount Hua dropout",
    "pearl diver", "fortune-teller", "blacksmith who forges legendary blades", "river ferryman",
    "tavern keeper", "master thief", "imperial bodyguard turned deserter", "Emei nun",
    "Wudang disciple", "opera performer", "painter who kills for hire", "herbalist", "bounty hunter",
    "caravan guard", "scholar who failed the imperial exams", "spy for the Jin", "tea merchant",
    "fisherwoman", "teenage pickpocket", "lantern seller", "famous restaurant chef", "graveyard keeper",
    "kite maker", "puppeteer", "silk-workshop heiress", "wandering doctor", "dice-hall boss",
]

PLACES = [
    "the Grand Canal", "West Lake", "Mount Hua", "a Yangtze river crossing", "the foothills of Wudang",
    "Lin'an's night market", "the salt marshes of Yangzhou", "a snowbound monastery on Mount Emei",
    "a Sichuan tea road", "the bamboo sea of Shu", "the Jin-held northern border", "a pearl harbour in Guangdong",
    "the borderlands of Dali", "the fishing villages of Dongting Lake", "Suzhou's garden quarter",
    "the islands of Lake Tai", "the tea hills of Fujian", "Hangzhou's silk workshops",
]

TWISTS = [
    "is secretly afraid of water", "owes a life debt to a rival", "lies constantly, but only about trivial things",
    "is searching for a lost twin", "collects stolen poems", "has never lost a fight and never won one cleanly",
    "keeps a famous sword hidden in a teapot", "cheats at dice but never at duels", "is being hunted by their own sect",
    "speaks only in proverbs", "pretends to be much weaker than they are", "cries at every sunset",
    "has sworn never to draw a blade again", "is writing a martial arts manual full of mistakes", "cannot read",
    "is publicly and hopelessly in love with a rival", "has a bounty on their head and doesn't know it",
    "teaches children kung fu in exchange for dumplings", "is the last student of a vanished sect",
    "thinks every stranger is the hero from a prophecy", "is a terrible singer but fights to their own song",
    "always sleeps on rooftops", "forgot their own name once and picked a new one", "hates swords",
    "is far too polite to hurt anyone, usually", "is a legend nobody has ever actually seen fight",
]


def _a(phrase: str) -> str:
    return ("an " if phrase[0].lower() in "aeiou" else "a ") + phrase


def random_seed(rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    role, place, twist = rng.choice(ROLES), rng.choice(PLACES), rng.choice(TWISTS)
    look = {
        "aura": rng.choice([a for a in game.APPEARANCE["aura"] if a != "none"]),
        "scene": rng.choice(game.APPEARANCE["scene"]),
        "hair_color": rng.choice(game.APPEARANCE["hair_color"]),
        "outfit_color": rng.choice(game.APPEARANCE["outfit_color"]),
    }
    return {"summary": f"{_a(role)} from {place} who {twist}", "look": look}


def roll_message(seed: dict) -> str:
    look = ", ".join(f"{k}={v}" for k, v in seed["look"].items())
    return (f"Roll me a random character: {seed['summary']}. "
            f"For their appearance, use exactly these options even if they seem unusual, and make the story fit them: {look}. "
            "Fill every field now in one go, then introduce them to me.")
