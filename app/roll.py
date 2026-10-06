"""Random characters. The dice live here, in code, because a model left to pick "a random
character" keeps returning the same lantern seller. We choose a role, a place, a twist and a
few visual cues, then ask the Storyteller to build someone from them. Every phrase has an English
and a Chinese form, so the roll can be shown in both languages without a translation call.

Everyone rolled lives in an open region (see app/world.py) and, at Mount Hua, has come for the
Summit Sword Gathering."""
import random

from . import game, world

ROLES = [
    ("wandering swordswoman", "游历的女剑客"), ("drunken monk", "醉酒的和尚"),
    ("retired escort-agency captain", "退隐的镖局总镖头"), ("poison-master's apprentice", "毒师的弟子"),
    ("teahouse storyteller selling tales of past gatherings", "兜售往届剑会故事的说书人"), ("blind lute player", "盲眼琵琶客"),
    ("disgraced court physician", "获罪的太医"), ("beggar-guild elder", "丐帮长老"),
    ("bandit chief with a conscience", "有良心的山寨大王"), ("bamboo-grove hermit", "竹林隐士"),
    ("Mount Hua dropout", "华山派的逃徒"), ("fortune-teller", "算命先生"),
    ("blacksmith who forges legendary blades", "能铸名剑的铁匠"), ("bookmaker taking bets on the gathering", "在剑会上坐庄收注的赌坊掌柜"),
    ("master thief", "神偷"), ("imperial bodyguard turned deserter", "叛逃的御前侍卫"),
    ("Emei nun", "峨眉师太"), ("Wudang disciple", "武当弟子"), ("opera performer", "戏班伶人"),
    ("painter who kills for hire", "以画为刃的杀手"), ("herbalist", "采药人"), ("bounty hunter", "追捕悬赏的游侠"),
    ("caravan guard", "商队护卫"), ("scholar who failed the imperial exams", "科考落第的书生"),
    ("spy for the Jin", "金国的细作"), ("tea seller on the stone steps", "石阶上卖茶的小贩"),
    ("teenage pickpocket", "少年扒手"), ("lantern seller", "卖灯人"), ("street-food cook", "挑担卖吃食的厨子"),
    ("graveyard keeper", "守墓人"), ("puppeteer", "傀儡戏艺人"), ("silk-workshop heiress", "绸缎坊的千金"),
    ("wandering doctor", "游方郎中"), ("dice-hall boss", "赌坊老板"), ("sword collector", "收藏名剑的富商"),
    ("retired sword judge", "退隐的剑会裁判"), ("mountain guide", "带客登山的向导"), ("wandering pilgrim", "云游的香客"),
    ("sect messenger", "门派的信使"), ("failed challenger from the last gathering", "上届剑会落败的挑战者"),
]

# (English, Chinese, region)
PLACES = [
    ("the Halfway Inn", "半山客栈", "huashan"), ("the Sword Cliff", "剑崖", "huashan"),
    ("Cloud Sword Pavilion", "云剑阁", "huashan"), ("the Herb Slope", "采药坡", "huashan"),
    ("the old pine path", "古松道", "huashan"), ("the cliff-top terrace", "绝顶剑台", "huashan"),
    ("the stone steps of the mountain gate", "山门石阶", "huashan"), ("the Mountain God's shrine", "山神庙", "huashan"),
    ("the Grand Canal", "大运河", "canal"), ("West Lake", "西湖", "westlake"), ("a Yangtze river crossing", "长江渡口", "yangtze"),
    ("the foothills of Wudang", "武当山脚", "wudang"), ("Lin'an's night market", "临安夜市", "linan"),
    ("a snowbound monastery on Mount Emei", "峨眉山雪中古寺", "emei"), ("the bamboo sea of Shu", "蜀南竹海", "shu"),
    ("the Jin-held northern border", "金国控制的北方边境", "border"), ("the borderlands of Dali", "大理边境", "dali"),
    ("the islands of Lake Tai", "太湖岛上", "taihu"), ("Shaolin's pagoda forest", "少林塔林", "shaolin"),
]

TWISTS = [
    ("is secretly afraid of heights", "暗中恐高"), ("owes a life debt to a rival", "欠了死对头一条命"),
    ("lies constantly, but only about trivial things", "总爱撒谎，却只谎称些无关紧要的事"),
    ("is searching for a lost twin", "在寻找失散的孪生兄弟"), ("collects stolen poems", "专收偷来的诗"),
    ("has never lost a fight and never won one cleanly", "从未输过，也从未赢得干净"),
    ("keeps a famous sword hidden in a teapot", "把一柄名剑藏在茶壶里"),
    ("cheats at dice but never at duels", "赌骰子出千，比武却从不作弊"),
    ("is being hunted by their own sect", "被自己的门派追杀"), ("speaks only in proverbs", "开口只说谚语"),
    ("pretends to be much weaker than they are", "装得比实际弱得多"), ("cries at every sunset", "每逢日落必落泪"),
    ("has sworn never to draw a blade again", "发誓此生不再拔刀"),
    ("is writing a martial arts manual full of mistakes", "在写一本错漏百出的武功秘籍"),
    ("cannot read", "目不识丁"), ("is publicly and hopelessly in love with a rival", "公然痴恋死对头，毫无指望"),
    ("has a bounty on their head and doesn't know it", "头上悬着赏银，自己却不知"),
    ("teaches children kung fu in exchange for dumplings", "教孩子功夫，只收饺子当学费"),
    ("is the last student of a vanished sect", "是已灭门派的最后一名弟子"),
    ("thinks every stranger is the hero from a prophecy", "总以为每个陌生人都是预言中的英雄"),
    ("is a terrible singer but fights to their own song", "唱得极难听，却要边唱边打"),
    ("always sleeps on rooftops", "总睡在屋顶上"),
    ("forgot their own name once and picked a new one", "曾忘了自己的名字，便另取了一个"),
    ("hates swords", "讨厌刀剑"), ("is far too polite to hurt anyone, usually", "太讲礼数，通常不忍伤人"),
    ("is a legend nobody has ever actually seen fight", "是个传说，却没人见过他出手"),
    ("has come to challenge the champion for a very private reason", "为了一个极私人的理由，来向魁首挑战"),
    ("secretly wants the champion to win", "暗中希望魁首夺冠"),
]


def _a(phrase: str) -> str:
    return ("an " if phrase[0].lower() in "aeiou" else "a ") + phrase


def random_seed(rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    places = [p for p in PLACES if world.is_open(p[2])] or PLACES
    (role, role_zh), (place, place_zh, region), (twist, twist_zh) = rng.choice(ROLES), rng.choice(places), rng.choice(TWISTS)
    look = {
        "aura": rng.choice([a for a in game.APPEARANCE["aura"] if a != "none"]),
        "scene": rng.choice(game.APPEARANCE["scene"]),
        "hair_color": rng.choice(["black", "black", "black", "brown", "brown", "silver", "white", "red"]),
        "outfit_color": rng.choice(game.APPEARANCE["outfit_color"]),
    }
    return {"summary": f"{_a(role)} from {place} who {twist}",
            "summary_zh": f"一位{role_zh}，来自{place_zh}，{twist_zh}", "look": look, "region": region}


def roll_message(seed: dict) -> str:
    look = ", ".join(f"{k}={v}" for k, v in seed["look"].items())
    why = world.SITUATION.get(seed["region"], {}).get("en", "")
    return (f"Roll me a random character: {seed['summary']} ({seed['summary_zh']}). "
            f"They live in the region '{seed['region']}'." + (f" Why they are there: {why}" if why else "") + " "
            f"For their appearance, use exactly these options even if they seem unusual, and make the story fit them: {look}. "
            "Fill every field now in one go, then introduce them to me.")
