"""How hard is the game? Simulate thousands of nights with the real dice rules and a sensible player, and report how often she lives.

    .venv\\Scripts\\python.exe -m evals.balance

No AI is involved: talking is modelled by how often each kind of person can be talked down. The point is to catch a game that is
too easy, or one that is unwinnable, whenever a number in app/case.py changes."""
import random
import statistics
import sys

from app import rules, story as case

sys.stdout.reconfigure(encoding="utf-8")


# how often a good talker settles each hostile person before the fuse runs out (the real game asks the AI; this is a stand-in)
CALM_ODDS = {"yue": 0.5, "monk": 0.6, "gu": 0.35, "fang": 0.6, "qin": 0.25}


def fresh_hero(rng: random.Random) -> dict:
    stats = rules.roll_stats(rng)
    h = {**stats, "qi": rules.start_qi(stats), "hp": rules.max_hp(stats), "hp_max": rules.max_hp(stats), "off": rng.choice(rules.OFFENCE), "defn": rng.choice(rules.DEFENCE)}
    return h


def fight(hero: dict, npc_key: str, rng: random.Random, edge: int = 0, cap: int = 40, ambushed: bool = False) -> tuple[bool, int]:
    """Fight to the end like a sensible player: counter heavy blows, use the art when there is breath, guard when hurt or out of breath. Returns (won, rounds)."""
    n = case.BY_KEY[npc_key]
    npc = {"hp": n["hp"], "atk": n["atk"], "defn": n["defn"], "dmg": n["dmg"]}
    hero.setdefault("qi", rules.start_qi(hero))
    if ambushed:
        rules.ambush(hero, npc, rng)
    rounds = 0
    while hero["hp"] > 0 and npc["hp"] > 0 and rounds < cap:
        rounds += 1
        intent = rules.pick_intent(rng)
        if intent == "heavy":
            action = "counter"
        elif intent == "guard":
            action = "guard" if hero["qi"] < 2 else "art"
        elif hero["hp"] <= 0.3 * hero["hp_max"]:
            action = "guard"
        else:
            action = "art" if hero["qi"] >= 1 else "strike"
        rules.fight_round(hero, npc, action, rng, edge, intent)
    return hero["hp"] > 0 and npc["hp"] <= 0, rounds


def one_night(rng: random.Random, talk_skill: float) -> dict:
    """She fights everyone who attacks her. `talk_skill` is how well she talks the others down (1.0 = always works)."""
    hero = fresh_hero(rng)
    ticks = 0
    fights = won = 0
    for n in case.CAST:
        # a friendly person never fights unless provoked; the rest are talked down with a chance that depends on how stubborn they are
        if n["mood"] == "friendly":
            ticks += 2
            continue
        calm = rng.random() < talk_skill * CALM_ODDS.get(n["key"], 0.4)
        ticks += 3
        if calm:
            continue
        fights += 1
        ok, rounds = fight(hero, n["key"], rng, ambushed=True)
        ticks += rounds
        if not ok:
            return {"alive": False, "fights": fights, "won": won, "hp": 0, "killer": n["key"]}
        won += 1
    return {"alive": hero["hp"] > 0, "fights": fights, "won": won, "hp": hero["hp"], "killer": None}


def report(n: int = 4000, seed: int = 7) -> dict:
    rng = random.Random(seed)
    out = {}
    for label, skill in (("never talks anyone down", 0.0), ("talks well", 1.0)):
        nights = [one_night(rng, skill) for _ in range(n)]
        out[label] = {"survive": sum(x["alive"] for x in nights) / n, "avg_fights": statistics.mean(x["fights"] for x in nights),
                      "killers": {k: sum(1 for x in nights if x["killer"] == k) / n for k in {x["killer"] for x in nights if x["killer"]}}}
    # a single fight against each person, from full health, for a typical build
    duels = {}
    for k in case.BY_KEY:
        w = rounds = 0
        for _ in range(n):
            ok, r = fight(fresh_hero(rng), k, rng)
            w += ok
            rounds += r
        duels[k] = {"win": w / n, "rounds": rounds / n}
    out["duels"] = duels
    return out


if __name__ == "__main__":
    r = report()
    for label in ("never talks anyone down", "talks well"):
        x = r[label]
        print(f"{label}: survives {x['survive']:.0%}, fights {x['avg_fights']:.1f}; killed by " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(x["killers"].items(), key=lambda kv: -kv[1])))
    print("one-on-one from full health (win rate, rounds):")
    for k, v in r["duels"].items():
        print(f"  {k:8} {v['win']:.0%}  {v['rounds']:.1f}")
