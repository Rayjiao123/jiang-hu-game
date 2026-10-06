"""The map of the jianghu. One list, used by the server (where an NPC lives), the Storyteller
(which regions it may choose) and the page (the map, via /api/world). Positions are on a
1000 x 640 canvas, north at the top."""
import zlib

REGIONS = {
    "border":   {"en": "Northern Frontier", "zh": "北境", "x": 610, "y": 78, "scene": "border",
                 "desc_en": "The Jin frontier: cold wind, watchtowers and men who have seen war.",
                 "desc_zh": "金国边境：朔风、烽燧，和见过战火的人。"},
    "huashan":  {"en": "Mount Hua", "zh": "华山", "x": 360, "y": 192, "scene": "huashan",
                 "desc_en": "Sheer granite peaks where swordsmen settle things.",
                 "desc_zh": "绝壁孤峰，剑客在此了断恩怨。"},
    "shaolin":  {"en": "Shaolin, Mount Song", "zh": "嵩山少林", "x": 565, "y": 205, "scene": "shaolin",
                 "desc_en": "The old monastery, its pagoda forest and its martial legends.",
                 "desc_zh": "千年古寺，塔林与武学传说。"},
    "wudang":   {"en": "Mount Wudang", "zh": "武当山", "x": 500, "y": 322, "scene": "wudang",
                 "desc_en": "Taoist halls above the clouds. Calm, until someone disturbs it.",
                 "desc_zh": "云上道观，平静如水，直到有人来扰。"},
    "canal":    {"en": "Grand Canal", "zh": "大运河", "x": 748, "y": 268, "scene": "canal",
                 "desc_en": "Grain barges, salt smugglers and every rumour that travels by water.",
                 "desc_zh": "漕船盐枭，水路上走的每一桩传闻。"},
    "yangtze":  {"en": "Yangtze Crossing", "zh": "长江渡口", "x": 640, "y": 368, "scene": "yangtze",
                 "desc_en": "A wide brown river and the ferrymen who know who crossed last night.",
                 "desc_zh": "浑黄大江，渡夫记得昨夜谁渡了河。"},
    "taihu":    {"en": "Lake Tai", "zh": "太湖", "x": 795, "y": 398, "scene": "taihu",
                 "desc_en": "Misty islands, fishing villages and sects hiding among the reeds.",
                 "desc_zh": "烟波岛屿，渔村苇荡，藏着隐世门派。"},
    "linan":    {"en": "Lin'an", "zh": "临安", "x": 862, "y": 452, "scene": "linan",
                 "desc_en": "The Southern Song capital. Court spies, silk, and a thousand lanterns after dark.",
                 "desc_zh": "南宋都城。朝堂耳目、绫罗绸缎，入夜万盏灯火。"},
    "westlake": {"en": "West Lake", "zh": "西湖", "x": 790, "y": 492, "scene": "westlake",
                 "desc_en": "Willows, painted boats and old grudges floating on still water.",
                 "desc_zh": "杨柳画舫，旧怨浮于静水之上。"},
    "emei":     {"en": "Mount Emei", "zh": "峨眉山", "x": 188, "y": 385, "scene": "emei",
                 "desc_en": "Snow, bells and the quiet discipline of the Emei nuns.",
                 "desc_zh": "雪、钟声，与峨眉师太们的清修。"},
    "shu":      {"en": "Bamboo Sea of Shu", "zh": "蜀南竹海", "x": 268, "y": 478, "scene": "shu",
                 "desc_en": "A sea of bamboo, tea roads and hermits who don't want to be found.",
                 "desc_zh": "万顷竹海，茶马古道，不愿被找到的隐士。"},
    "dali":     {"en": "Dali", "zh": "大理", "x": 160, "y": 565, "scene": "dali",
                 "desc_en": "Lake Erhai, white pagodas and a kingdom with its own rules.",
                 "desc_zh": "洱海白塔，自成规矩的一方国度。"},
}

IDS = list(REGIONS)


def valid(region_id) -> bool:
    return str(region_id or "").strip().lower() in REGIONS


def region_for(npc: dict) -> str:
    """The region an NPC lives in. Older NPCs made before regions existed get a stable one from their id."""
    r = str(npc.get("region", "")).strip().lower()
    if r in REGIONS:
        return r
    return IDS[zlib.crc32(str(npc.get("id", npc.get("name", ""))).encode()) % len(IDS)]


def public() -> list[dict]:
    return [{"id": k, **v} for k, v in REGIONS.items()]
