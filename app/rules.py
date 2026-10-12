"""The dice rules, kept apart from the story so they can be tested and balanced on their own.

Three stats, thirty points between them:
  STRENGTH      sets hit points                          HP = 10 + 2 x STR
  INTELLIGENCE  sets how strong the martial arts' effects are, how much Qi she starts with and how fast guarding recovers it
  AGILITY       sets defence                             +1 to every defence roll per 3 points

Every attack and every defence is a roll of two six-sided dice. In a round the hero acts first, then the enemy:
  attack:   attacker rolls 2d6 + their attack bonus       defender rolls 2d6 + their defence bonus
            the attack lands when the attack total is at least the defence total (a tie goes to the attacker)
  damage:   the two attack dice added together (2 to 12), plus whatever the martial art adds, plus a flat bonus for enemies
Nobody heals except through what the story hands out, so a fight is paid for in hit points all night."""
import random

STAT_MIN, STAT_MAX, STAT_TOTAL = 6, 16, 30
HERO_ACCURACY = 2                    # the hero's own attack bonus
GUARD_BONUS = 3                      # guarding instead of attacking adds this to the defence roll
QI_START, QI_MAX = 2, 5              # breath for the martial art: Art costs 1, Guard gives 1 back
ART_ACCURACY, ART_DAMAGE = 2, 3      # an Art is easier to land and hits harder (plus Intelligence / 3)
HEAVY_DAMAGE, COUNTER_DEFENCE = 4, 4 # a heavy blow hurts more, and a Counter against one is a big defence bonus
GUARD_UP = 3                         # an enemy turtling up is this much harder to hit
INTENTS = ("heavy", "quick", "guard")

OFFENCE = ("sand_blade", "split_palm", "needle_rain", "shadow_step")
DEFENCE = ("iron_cloth", "willow_step", "yield_palm", "stone_breath")


def roll2(rng: random.Random) -> list[int]:
    return [rng.randint(1, 6), rng.randint(1, 6)]


def roll_stats(rng: random.Random) -> dict:
    """Thirty points over three stats, each between 6 and 16: start from 6 each and hand out the other 12 one at a time."""
    s = {"str": STAT_MIN, "int": STAT_MIN, "agi": STAT_MIN}
    for _ in range(STAT_TOTAL - 3 * STAT_MIN):
        open_ = [k for k, v in s.items() if v < STAT_MAX]
        s[rng.choice(open_)] += 1
    return s


def max_hp(stats: dict) -> int:
    return 10 + 2 * stats["str"]


def start_qi(stats: dict) -> int:
    """Intelligence is how much breath a thief starts the night with: 2 at Intelligence 6 to 8, up to the maximum of 5 at 16."""
    return min(QI_MAX, 1 + stats["int"] // 4)


def qi_recovery(stats: dict) -> int:
    """...and how quickly she gets it back when she guards: one at Intelligence 10 or less, two above that."""
    return 2 if stats["int"] >= 11 else 1


def defence_bonus(stats: dict) -> int:
    return stats["agi"] // 3


# ---------- the martial arts: what each does, scaled by intelligence ----------

def attack_effect(art: str, dice: list[int], atk_total: int, def_total: int, intel: int) -> tuple[int, list[tuple]]:
    """Damage from an attack that landed, and notes about what the art did (code, value) for the page to describe."""
    base = sum(dice)
    dmg, notes = base, []
    if art == "sand_blade" and dice[0] == dice[1]:
        dmg, notes = base * 2, [("doubled", base)]
    elif art == "split_palm" and base >= 9:
        extra = intel // 2
        dmg, notes = base + extra, [("shockwave", extra)]
    elif art == "needle_rain":
        needles = sum(1 for d in dice if d >= 5)
        if needles:
            extra = needles * (1 + intel // 4)
            dmg, notes = base + extra, [("needles", extra)]
    elif art == "shadow_step" and atk_total - def_total >= 5:
        extra = intel // 2 + 2
        dmg, notes = base + extra, [("backstab", extra)]
    return dmg, notes


def defence_roll_bonus(art: str, intel: int) -> int:
    return 1 + intel // 4 if art == "willow_step" else 0


def soften(art: str, dmg: int, intel: int) -> tuple[int, int]:
    """Iron Cloth: every hit that lands is reduced (never below 1). Returns (damage, how much was saved)."""
    if art != "iron_cloth":
        return dmg, 0
    cut = min(dmg - 1, 2 + intel // 4)
    return dmg - cut, cut


def reflect(art: str, def_total: int, atk_total: int, intel: int) -> int:
    """Yielding Palm: a defence that beats the attack by 4 or more turns the force back on the attacker."""
    return 2 + intel // 2 if art == "yield_palm" and def_total - atk_total >= 4 else 0


def breath_heal(art: str, dice: list[int], intel: int) -> int:
    """Stone Breath: defence dice showing a pair let the hero recover."""
    return 1 + intel // 2 if art == "stone_breath" and dice[0] == dice[1] else 0


# ---------- one round of a fight ----------
# Each round the enemy shows what it is about to do (its INTENT), then she chooses:
#   strike   a plain attack
#   art      her attack art: costs 1 Qi, easier to land, hits harder
#   guard    +3 defence and one Qi back
#   counter  against a HEAVY blow: a big defence bonus, and if it works she turns the blow on them; against anything else it only leaves her open
# intents: heavy = slower but +4 damage; quick = quicker (+1 to hit); guard = the enemy turtles (+3 defence, no attack)

def pick_intent(rng: random.Random) -> str:
    r = rng.random()
    return "heavy" if r < 0.34 else "quick" if r < 0.76 else "guard"


def _enemy_attack(hero: dict, npc: dict, action: str, rng: random.Random, intent: str) -> dict:
    intel = hero["int"]
    e, g = roll2(rng), roll2(rng)
    E = sum(e) + npc["atk"] + (1 if intent == "quick" else -1 if intent == "heavy" else 0)
    P = sum(g) + defence_bonus(hero) + defence_roll_bonus(hero["defn"], intel)
    P += GUARD_BONUS if action == "guard" else 0
    if action == "counter":
        P += COUNTER_DEFENCE if intent == "heavy" else -2
    hit = E >= P
    dmg, notes = 0, []
    if hit:
        dmg, saved = soften(hero["defn"], sum(e) + npc["dmg"] + (HEAVY_DAMAGE if intent == "heavy" else 0), intel)
        hero["hp"] = max(0, hero["hp"] - dmg)
        if saved:
            notes.append(("softened", saved))
    else:
        back = reflect(hero["defn"], P, E, intel)
        if action == "counter" and intent == "heavy":
            back += sum(g) + 2 + intel // 3
            notes.append(("counter", sum(g) + 2 + intel // 3))
        elif back:
            notes.append(("reflected", back))
        if back:
            npc["hp"] = max(0, npc["hp"] - back)
    heal = breath_heal(hero["defn"], g, intel) if hero["hp"] > 0 else 0
    if heal:
        hero["hp"] = min(hero["hp_max"], hero["hp"] + heal)
        notes.append(("breath", heal))
    return {"dice": e, "total": E, "against": {"dice": g, "total": P}, "hit": hit, "damage": dmg, "notes": notes, "guard": action == "guard"}


def ambush(hero: dict, npc: dict, rng: random.Random) -> dict:
    """A fight that starts with the enemy getting the first blow: a talk gone wrong, or someone she kept waiting. It cannot kill her outright."""
    out = _enemy_attack(hero, npc, "ambush", rng, "quick")
    hero["hp"] = max(1, hero["hp"])
    return out


def fight_round(hero: dict, npc: dict, action: str, rng: random.Random, edge: int = 0, intent: str = "quick") -> dict:
    """Resolve one round, changing hero['hp'], hero['qi'] and npc['hp'] in place. hero: stats, hp, hp_max, qi, off, defn. npc: hp, atk, defn, dmg.
    `edge` is what the hero has learned about this enemy (added to her attack total). Returns everything the page needs to show."""
    out: dict = {"action": action, "intent": intent, "hero": None, "npc": None}
    intel = hero["int"]
    if action in ("strike", "art"):
        art = action == "art"
        if art:
            hero["qi"] -= 1
        a, d = roll2(rng), roll2(rng)
        A = sum(a) + HERO_ACCURACY + edge + (ART_ACCURACY if art else 0)
        D = sum(d) + npc["defn"] + (GUARD_UP if intent == "guard" else 0)
        hit = A >= D
        dmg, notes = attack_effect(hero["off"], a, A, D, intel) if hit else (0, [])
        if hit and art:
            extra = ART_DAMAGE + intel // 3
            dmg += extra
            notes = notes + [("flourish", extra)]
        npc["hp"] = max(0, npc["hp"] - dmg)
        out["hero"] = {"dice": a, "total": A, "against": {"dice": d, "total": D}, "hit": hit, "damage": dmg, "notes": notes, "edge": edge, "art": art}
    elif action == "guard":
        hero["qi"] = min(QI_MAX, hero["qi"] + qi_recovery(hero))
    if npc["hp"] <= 0 or intent == "guard":
        return out                                           # a dead enemy does not strike back, and a turtling one only defends
    out["npc"] = _enemy_attack(hero, npc, action, rng, intent)
    if npc["hp"] <= 0:
        out["npc"]["fell"] = True                            # a counter or a reflected blow finished them
    return out
