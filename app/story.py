"""The story: 黑沙客栈, The Black Sand Inn, one stormy night. 人在江湖，身不由己.

You are a thief, hiding in an inn while a sandstorm closes the road. All night, more people ride in out of the storm. Some are outlaws
like you (friendly, but bad), some are righteous fighters who want to cut down a thief (aggressive, but good), some are the law who want to
take you in. Every one of them can be talked to, and every one of them can be fought. Talking can win you what they know; so can winning a fight.
Lose a fight and you are dead (or hanged). Live until the storm passes, then walk out: that is winning.

Everything that decides the game is here and in app/rules.py, not left to the AI. The AI only plays the people (and Ray, the game master).
Fixed text is written once in three languages: 'English ||| 中文 ||| ไทย'.
"""
from . import i18n
from .i18n import tr

TITLE = tr("Helpless in the Jianghu", "人在江湖，身不由己", "คนในยุทธภพ ไม่อาจเป็นตัวของตัวเอง")
STORM_END = 16                     # the storm passes when this many beats have gone
SHORTEST = 8                       # however much she learns, she cannot leave before this
MIN_STAT, MAX_STAT = 6, 16

SETUP = tr(
    "Black Sand Inn, somewhere on the desert road, about the year 1200. A sandstorm has closed the pass and you, a thief with a stolen jade seal under your shirt, are stuck in the hall with a cup of cold tea. "
    "The storm will not break for a long while. Out of it, one by one, other travellers keep pushing through the door: outlaws, righteous swordsmen, and the law, and every one of them is looking at you.",
    "黑沙客栈，大漠官道旁，约莫公元一二〇〇年。沙暴封了关口，你，一个怀里藏着偷来的玉印的贼，被困在大堂里，面前一杯凉茶。"
    "风沙一时半会儿不会停。人一个接一个从风沙里推门进来：绿林好汉、正道侠客、官府的人，而每一个人，都在看着你。",
    "โรงเตี๊ยมทรายดำ ริมทางสายทะเลทราย ราวปี ค.ศ. 1200 พายุทรายปิดช่องเขา และเจ้า โจรที่ซ่อนตราหยกขโมยมาไว้ใต้เสื้อ ก็ติดอยู่ในโถงโรงเตี๊ยมกับชาเย็นหนึ่งถ้วย "
    "พายุจะไม่สงบง่าย ๆ ผู้คนผลักประตูฝ่าพายุเข้ามาทีละคน ทั้งพวกนอกกฎหมาย ยอดฝีมือฝ่ายธรรมะ และทางการ และทุกคนกำลังมองมาที่เจ้า")

GOAL = tr(
    "Stay alive until the storm passes, then walk out the door. Talk your way through, or fight. If you lose a fight, you die.",
    "活到沙暴过去，然后走出大门。靠嘴巴过关，或者靠拳脚。打输，就是死。",
    "รอดชีวิตจนกว่าพายุจะผ่านไป แล้วเดินออกจากประตู จะเจรจาให้พ้นตัวหรือจะสู้ก็ได้ แต่ถ้าแพ้ เจ้าตาย")

HOW_TO = tr(
    "Each beat of the night, someone new may arrive. Every message you send, and every round you fight, is one beat. When the storm passes, you can leave.",
    "夜里每过一拍，就可能有新人到。你每说一句话、每打一回合，都算一拍。沙暴一过，你就能走。",
    "ทุกจังหวะของค่ำคืนอาจมีคนใหม่มาถึง ทุกข้อความที่เจ้าส่งและทุกยกที่สู้นับเป็นหนึ่งจังหวะ เมื่อพายุผ่านไป เจ้าก็ออกไปได้")

# ---------- the stats and the martial arts ----------

STATS = {
    "str": {"name": tr("Strength", "力量", "กำลัง"), "does": tr("sets your hit points", "决定你的生命值", "กำหนดพลังชีวิตของเจ้า")},
    "int": {"name": tr("Intelligence", "智慧", "ปัญญา"), "does": tr("strengthens your martial arts", "强化你的武功", "ทำให้วิชายุทธ์ของเจ้าแรงขึ้น")},
    "agi": {"name": tr("Agility", "敏捷", "ความคล่องแคล่ว"), "does": tr("sets your defence", "决定你的防御", "กำหนดการป้องกันของเจ้า")},
}

ARTS = {
    "sand_blade": {"kind": "offence", "name": tr("Sand-Skimming Blade", "踏沙刀", "กระบี่เลียดทราย"),
                   "does": tr("Doubles the damage when both attack dice match.", "两颗攻击骰点数相同时，伤害加倍。", "ถ้าลูกเต๋าโจมตีทั้งสองลูกออกแต้มเท่ากัน ความเสียหายเป็นสองเท่า")},
    "split_palm": {"kind": "offence", "name": tr("Mountain-Splitting Palm", "裂山掌", "ฝ่ามือผ่าภูผา"),
                   "does": tr("When the dice add to 9 or more, a shockwave adds damage equal to half your Intelligence.", "骰点合计 9 点以上时，震波额外造成相当于智慧一半的伤害。", "เมื่อแต้มรวมได้ 9 ขึ้นไป คลื่นกระแทกเพิ่มความเสียหายเท่ากึ่งหนึ่งของปัญญา")},
    "needle_rain": {"kind": "offence", "name": tr("Rain of Needles", "漫天花雨", "ฝนเข็มกระจายฟ้า"),
                    "does": tr("Each attack die showing 5 or 6 throws a needle: extra damage, more with Intelligence.", "每颗显示 5 或 6 的攻击骰射出一根针，造成额外伤害，智慧越高越多。", "ลูกเต๋าโจมตีที่ออก 5 หรือ 6 ปล่อยเข็มหนึ่งเล่ม เพิ่มความเสียหาย ยิ่งฉลาดยิ่งเพิ่มมาก")},
    "shadow_step": {"kind": "offence", "name": tr("Shadow-Step Strike", "影步袭", "ท่าเงาลอบโจมตี"),
                    "does": tr("If your attack beats their defence by 5 or more, you strike from behind for extra damage.", "攻击总点数比对方防御高出 5 以上时，从背后偷袭，额外造成伤害。", "ถ้าแต้มโจมตีสูงกว่าแต้มป้องกันของศัตรูตั้งแต่ 5 ขึ้นไป เจ้าจะโจมตีจากด้านหลัง เพิ่มความเสียหาย")},
    "iron_cloth": {"kind": "defence", "name": tr("Iron Cloth", "金钟罩", "เกราะระฆังทอง"),
                   "does": tr("Every hit you take is reduced, more with Intelligence.", "你受到的每一击都会减伤，智慧越高减得越多。", "ทุกครั้งที่ถูกโจมตี ความเสียหายลดลง ยิ่งฉลาดยิ่งลดมาก")},
    "willow_step": {"kind": "defence", "name": tr("Drifting Willow Step", "飘柳步", "ก้าวหลิวล่องลอย"),
                    "does": tr("Adds to every defence roll, more with Intelligence.", "每次防御骰都有加成，智慧越高加成越多。", "เพิ่มแต้มป้องกันทุกครั้ง ยิ่งฉลาดยิ่งเพิ่มมาก")},
    "yield_palm": {"kind": "defence", "name": tr("Yielding Palm", "以柔克刚", "ฝ่ามือน้ำอ่อนชนะแข็ง"),
                   "does": tr("If your defence beats their attack by 4 or more, their own force strikes them back.", "防御总点数比对方攻击高出 4 以上时，对方的力道反弹回去伤他自己。", "ถ้าแต้มป้องกันสูงกว่าแต้มโจมตีของศัตรูตั้งแต่ 4 ขึ้นไป แรงของเขาจะสะท้อนกลับ")},
    "stone_breath": {"kind": "defence", "name": tr("Stone Breath", "磐石息", "ลมหายใจศิลา"),
                     "does": tr("If both defence dice match, you catch your breath and heal.", "两颗防御骰点数相同时，你调息回血。", "ถ้าลูกเต๋าป้องกันทั้งสองลูกออกแต้มเท่ากัน เจ้าหายใจเรียกลมปราณและฟื้นเลือด")},
}

NOTES = {   # what an art did in a round: shown under the dice
    "doubled": tr("Matching dice: damage doubled", "骰点相同：伤害加倍", "ลูกเต๋าซ้ำกัน: ความเสียหายเป็นสองเท่า"),
    "shockwave": tr("Shockwave", "震波", "คลื่นกระแทก"), "needles": tr("Needles", "飞针", "เข็มพิฆาต"), "backstab": tr("Struck from behind", "背后一击", "โจมตีจากด้านหลัง"),
    "softened": tr("Iron Cloth absorbed", "金钟罩卸去", "เกราะระฆังทองรับไว้"), "reflected": tr("Force turned back", "力道反弹", "สะท้อนแรงกลับ"),
    "breath": tr("Stone Breath healed", "磐石息回血", "ลมหายใจศิลาฟื้นเลือด"),
    "flourish": tr("Art flourish", "招式加成", "พลังของท่าไม้ตาย"), "counter": tr("Counter-strike!", "反击！", "สวนกลับ!"),
}

# ---------- the people in the story ----------

MOODS = {
    "friendly":   {"name": tr("Outlaw · friendly", "绿林 · 友善", "พวกนอกกฎหมาย · เป็นมิตร"), "icon": "🗡", "short": tr("bad guy, but on your side", "坏人，但站在你这边", "คนไม่ดี แต่อยู่ข้างเจ้า")},
    "aggressive": {"name": tr("Righteous · hostile", "正道 · 敌意", "ฝ่ายธรรมะ · เป็นปรปักษ์"), "icon": "⚔", "short": tr("good guy, wants to punish a thief", "好人，想惩治窃贼", "คนดี อยากลงโทษโจร")},
    "police": {"name": tr("The law · hunting you", "官府 · 追捕你", "ทางการ · ตามล่าเจ้า"), "icon": "⛓", "short": tr("here to arrest you", "来抓你的", "มาจับเจ้า")},
}

# effect kinds: edge (+N to her attack against `target` from now on), heal (+N hit points), shortcut (the storm passes N beats sooner)
CAST = [
    {
        "key": "shuang", "talk_limit": 5, "goal": tr("Win Madam Shuang's trust and she will show you a way to leave the pass early.", '赢得霜四娘的信任，她会告诉你提早离开关口的路。', 'ชนะใจเถ้าแก่เนี้ยซวง นางจะบอกทางออกจากช่องเขาก่อนเวลา'), "name": tr("Madam Shuang", "霜四娘", "เถ้าแก่เนี้ยซวง"), "mood": "friendly", "arrive": 0, "start_trust": 3, "calm": 0,
        "title": tr("Keeper of the Black Sand Inn, a fence", "黑沙客栈掌柜，销赃人", "เจ้าของโรงเตี๊ยมทรายดำ ผู้รับซื้อของโจร"),
        "public": tr("Everything in this inn has a price, and she buys what thieves bring.", "这店里什么都有价，贼带来的东西她也收。", "ในโรงเตี๊ยมนี้ทุกอย่างมีราคา และนางรับซื้อของที่โจรนำมา"),
        "hp": 25, "atk": 3, "defn": 3, "dmg": 3,
        "arrival": tr("Madam Shuang is already behind the counter, polishing a cup that does not need it. 'Another one for the storm,' she purrs.", "霜四娘早已站在柜台后，擦着一只本不需要擦的杯子。“又是一个来躲风沙的。”她轻声道。", "เถ้าแก่เนี้ยซวงยืนอยู่หลังเคาน์เตอร์แล้ว ขัดถ้วยที่ไม่จำเป็นต้องขัด 'มาหลบพายุอีกคนสินะ' นางพูดเบา ๆ"),
        "hostile": tr("Madam Shuang's smile does not move. Her fan opens, and needles glitter between its ribs.", "霜四娘的笑纹丝不动，折扇一展，扇骨之间寒光点点。", "รอยยิ้มของเถ้าแก่เนี้ยซวงไม่ขยับ พัดกางออก เข็มวาวระหว่างซี่พัด"),
        "down": tr("Madam Shuang folds against the counter and spits out a laugh. Her keys slide across the floor to you.", "霜四娘伏在柜台上，啐出一声笑，钥匙滑到你脚边。", "เถ้าแก่เนี้ยซวงฟุบกับเคาน์เตอร์ หัวเราะในลำคอ พวงกุญแจลื่นมาถึงเท้าเจ้า"),
        "reward": {"trust": 7, "effect": {"kind": "shortcut", "n": 5},
                   "fact": "There is an old smugglers' tunnel under the cellar that leaves the pass early. She will show you the way, for a favour owed; with it you can leave five beats sooner.",
                   "gain": tr("Shuang shows you the smugglers' tunnel. You can leave 5 beats earlier.", "霜四娘告诉你走私客的暗道：你可以提早 5 拍离开。", "เถ้าแก่เนี้ยซวงบอกทางอุโมงค์ของพวกลักลอบ เจ้าออกไปได้เร็วขึ้น 5 จังหวะ")},
        "voice": "Silky and amused, every favour with a price tag; calls the young woman 'little sister'; never raises her voice, and is most gentle when she is most dangerous.",
        "wants": "She wants the thief to sell her the jade seal cheaply, and she hates the law.",
        "calms": "Respects the clever who don't beg; likes jokes and a fair price.",
        "appearance": dict(build="feminine", age="adult", skin="fair", hair_style="long", hair_color="black", eyes="sharp", eye_color="amber", expression="smirk",
                           outfit="noble", outfit_color="crimson", accent_color="gold", headwear="hairpin", mark="none", weapon="fan", aura="flame", scene="lanterns"),
    },
    {
        "key": "wolf", "talk_limit": 5, "goal": tr("Win Black Wolf's trust and he will tell you how to beat Captain Gu.", '赢得黑狼的信任，他会告诉你怎么对付顾捕头。', 'ชนะใจหมาป่าดำ เขาจะบอกวิธีรับมือหัวหน้ากู้'), "name": tr("Black Wolf", "黑狼", "หมาป่าดำ"), "mood": "friendly", "arrive": 1, "start_trust": 3, "calm": 0,
        "title": tr("Desert bandit chief", "大漠马贼头领", "หัวหน้าโจรทะเลทราย"),
        "public": tr("A scarred bandit who respects only people who don't flinch.", "脸上带疤的马贼，只敬不退缩的人。", "โจรหน้าบากที่นับถือแต่คนไม่ถอย"),
        "hp": 32, "atk": 5, "defn": 4, "dmg": 5,
        "arrival": tr("The door bangs. Black Wolf stamps the sand from his boots, grins at you across the hall, and takes the seat nearest the exit.", "门被撞开。黑狼跺掉靴子上的沙，隔着大堂冲你咧嘴一笑，在离出口最近的位子坐下。", "ประตูกระแทกเปิด หมาป่าดำกระทืบเท้าสะบัดทรายออกจากรองเท้าบู๊ต ยิ้มกว้างให้เจ้าข้ามโถง แล้วนั่งที่ใกล้ทางออกที่สุด"),
        "hostile": tr("Black Wolf stops grinning. 'Nothing personal, little thief,' he says, and the saber comes out.", "黑狼收了笑。“没什么私仇，小贼。”他说着，刀已出鞘。", "หมาป่าดำเลิกยิ้ม 'ไม่ใช่เรื่องส่วนตัวนะ โจรน้อย' เขาว่า แล้วชักกระบี่ออก"),
        "down": tr("Black Wolf goes down on one knee, laughing through the blood. 'Hah. Good. You're one of us.'", "黑狼单膝跪地，血里带笑。“哈，不错，你是自己人。”", "หมาป่าดำคุกเข่าลงข้างหนึ่ง หัวเราะทั้งเลือด 'ฮ่า ดี เจ้าเป็นพวกเดียวกัน'"),
        "reward": {"trust": 5, "effect": {"kind": "edge", "target": "gu", "n": 2},
                   "fact": "A constable named Gu is riding in tonight. Wolf has seen him fight: his right arm is slow since an old wound, so strike at that side and you will land hits on him more easily.",
                   "gain": tr("Wolf tells you Captain Gu's right arm is slow. You hit Captain Gu more easily (+2).", "黑狼告诉你顾捕头右臂不灵。你打顾捕头更容易命中（+2）。", "หมาป่าดำบอกว่าแขนขวาของหัวหน้ากู้เชื่องช้า เจ้าโจมตีเขาโดนง่ายขึ้น (+2)")},
        "voice": "Loud, blunt and funny, laughs at danger; calls the young woman 'little thief' and means it kindly.",
        "wants": "He wants a fellow outlaw to drink with and a way to rob the next caravan; he hates the law and the self-righteous.",
        "calms": "Respects nerve, a good joke and anyone who laughs at the law; despises whining and cowards.",
        "appearance": dict(build="masculine", age="adult", skin="tan", hair_style="wild", hair_color="black", eyes="sharp", eye_color="black", expression="fierce",
                           outfit="fighter", outfit_color="ash", accent_color="crimson", headwear="none", mark="scar", weapon="saber", aura="wind", scene="mountains"),
    },
    {
        "key": "yue", "talk_limit": 4, "goal": tr('Convince Yue Qinghan you are worth sparing, and she will stand down and warn you about Captain Gu.', '说服岳清寒你值得饶恕，她会收剑，并提醒你提防顾捕头。', 'โน้มน้าวเย่ว์ชิงหานว่าเจ้าควรไว้ชีวิต นางจะเก็บกระบี่และเตือนเรื่องหัวหน้ากู้'), "name": tr("Yue Qinghan", "岳清寒", "เย่ว์ชิงหาน"), "mood": "aggressive", "arrive": 3, "start_trust": 1, "calm": 5, "fuse": 3,
        "title": tr("Swordswoman of the Righteous Sect", "名门正派的女剑客", "นักกระบี่หญิงแห่งสำนักธรรมะ"),
        "public": tr("Cold, upright, and sure that a thief deserves a sword.", "冷峻正直，坚信贼就该吃一剑。", "เย็นชา ซื่อตรง และมั่นใจว่าโจรสมควรโดนกระบี่"),
        "hp": 31, "atk": 5, "defn": 4, "dmg": 4,
        "arrival": tr("A woman in white shakes the sand from her sleeves. Her eyes find your bulging collar. 'A thief,' says Yue Qinghan. 'I can smell it.'", "一位白衣女子抖落袖上的沙。她的目光落在你鼓起的衣领上。“有贼。”岳清寒说，“我闻得出来。”", "หญิงชุดขาวสะบัดทรายออกจากแขนเสื้อ สายตาจับที่ปกเสื้อป่อง ๆ ของเจ้า 'มีโจร' เย่ว์ชิงหานว่า 'ข้าได้กลิ่น'"),
        "hostile": tr("Yue Qinghan's sword leaves its sheath with a whisper. 'For the people you stole from,' she says.", "岳清寒长剑出鞘，轻吟一声。“为了被你偷过的人。”她说。", "กระบี่ของเย่ว์ชิงหานออกจากฝักเสียงแผ่ว 'เพื่อผู้คนที่เจ้าขโมยมา' นางว่า"),
        "down": tr("Yue Qinghan lowers her sword. 'Strike me down, then. A thief with a spine is still a thief.'", "岳清寒垂下剑。“要杀便杀。有骨气的贼，也还是贼。”", "เย่ว์ชิงหานลดกระบี่ 'จะฆ่าก็ฆ่าเถอะ โจรที่มีศักดิ์ศรีก็ยังเป็นโจร'"),
        "reward": {"trust": 5, "effect": {"kind": "edge", "target": "gu", "n": 2},
                   "fact": "She has worked with Captain Gu and knows he is arrogant: he always lunges first, so a quick counter-stroke after his lunge lands cleanly on him.",
                   "gain": tr("Yue warns you about Captain Gu's lunge. You hit Captain Gu more easily (+2).", "岳清寒提醒你顾捕头的突刺。你打顾捕头更容易命中（+2）。", "เย่ว์ชิงหานเตือนเรื่องท่าพุ่งแทงของหัวหน้ากู้ เจ้าโจมตีเขาโดนง่ายขึ้น (+2)")},
        "voice": "Clipped, formal, quietly disdainful; calls the young woman 'thief'; softens only when shown real honesty or remorse.",
        "wants": "She wants to bring a thief to justice, but not at the cost of her honour: she will not strike someone who sincerely repents or who is clearly doing right.",
        "calms": "Honesty, remorse, a good reason for stealing, and proof that the thief is not cruel.",
        "appearance": dict(build="feminine", age="young", skin="fair", hair_style="ponytail", hair_color="black", eyes="sharp", eye_color="black", expression="calm",
                           outfit="fighter", outfit_color="white", accent_color="azure", headwear="headband", mark="none", weapon="sword", aura="ice", scene="snow"),
    },
    {
        "key": "monk", "talk_limit": 4, "goal": tr('Convince Monk Wuhui you can change, and he will stand down and give you medicine.', '说服无晦和尚你能改过，他会收杖，并给你药。', 'โน้มน้าวพระอู๋ฮุ่ยว่าเจ้าเปลี่ยนได้ ท่านจะวางไม้เท้าและให้ยา'), "name": tr("Monk Wuhui", "无晦和尚", "พระอู๋ฮุ่ย"), "mood": "aggressive", "arrive": 5, "start_trust": 1, "calm": 5, "fuse": 4,
        "title": tr("Warrior monk of the Stone Temple", "石寺的武僧", "พระนักรบแห่งวัดศิลา"),
        "public": tr("Huge, slow-spoken, and absolutely certain that thieves must be corrected.", "身躯魁梧，说话缓慢，坚信窃贼必须被管教。", "ร่างใหญ่ พูดช้า และมั่นใจเต็มร้อยว่าโจรต้องถูกสั่งสอน"),
        "hp": 36, "atk": 4, "defn": 5, "dmg": 4,
        "arrival": tr("A monk as wide as the doorframe ducks inside. 'Amitabha,' says Wuhui, and sets his iron staff against the wall with a clang. 'Who here has stolen?'", "一位宽得像门框的和尚低头进门。“阿弥陀佛。”无晦把铁杖靠在墙上，当啷一响，“这里谁偷了东西？”", "พระรูปหนึ่งตัวกว้างเท่าวงกบประตูก้มตัวเข้ามา 'อมิตพุทธ' อู๋ฮุ่ยว่า วางไม้เท้าเหล็กพิงผนังเสียงดังก้อง 'ใครในนี้ขโมยของมา?'"),
        "hostile": tr("Monk Wuhui lifts his staff in one hand. 'Be still, child. This will hurt me more than you.'", "无晦单手举起铁杖。“别动，孩子。这一下，疼的是我，不是你。”", "พระอู๋ฮุ่ยยกไม้เท้าด้วยมือเดียว 'อยู่นิ่ง ๆ เด็กน้อย เรื่องนี้อาตมาเจ็บยิ่งกว่าเจ้า'"),
        "down": tr("Monk Wuhui sits down on the floor and folds his hands. 'I have never seen anyone so fast.'", "无晦盘腿坐在地上，合十。“这么快的身手，贫僧从没见过。”", "พระอู๋ฮุ่ยนั่งลงกับพื้น ประนมมือ 'ความเร็วแบบนี้ อาตมายังไม่เคยเห็นมาก่อน'"),
        "reward": {"trust": 5, "effect": {"kind": "heal", "n": 10},
                   "fact": "He carries a bitter pill that closes wounds, and he is willing to give one to a thief who really does mean to change.",
                   "gain": tr("Wuhui gives you a pill. You heal 10 hit points.", "无晦给了你一颗药丸。你回复 10 点生命。", "อู๋ฮุ่ยให้ยาเม็ดหนึ่งแก่เจ้า เจ้าฟื้นเลือด 10 แต้ม")},
        "voice": "Slow, gentle and absolutely immovable; quotes a little scripture; calls the young woman 'child'.",
        "wants": "He wants to correct a thief and turn her toward a better life, by force if there is no other way.",
        "calms": "Sincere repentance, kindness to the weak, patience; he cannot stand lies or boasting.",
        "appearance": dict(build="masculine", age="adult", skin="warm", hair_style="bald", hair_color="black", eyes="soft", eye_color="brown", expression="calm",
                           outfit="monk", outfit_color="ash", accent_color="gold", headwear="none", mark="none", weapon="staff", aura="moon", scene="mountains"),
    },
    {
        "key": "gu", "talk_limit": 4, "goal": tr('Convince Captain Gu you are not carrying the seal, and he will stand down and clear the road for you.', '让顾捕头相信你身上没有玉印，他会收手，并为你清出道路。', 'ทำให้หัวหน้ากู้เชื่อว่าเจ้าไม่ได้พกตราไว้ เขาจะยอมถอยและเปิดทางให้'), "name": tr("Captain Gu", "顾捕头", "หัวหน้ากู้"), "mood": "police", "arrive": 7, "start_trust": 1, "calm": 6, "fuse": 4,
        "title": tr("Chief constable of the pass", "关口的总捕头", "หัวหน้าชุดจับกุมประจำด่าน"),
        "public": tr("A proud officer who has never lost a prisoner.", "骄傲的捕头，从没跑掉过一个犯人。", "เจ้าพนักงานผู้ทระนง ไม่เคยปล่อยนักโทษหลุดมือ"),
        "hp": 35, "atk": 5, "defn": 5, "dmg": 5,
        "arrival": tr("The door opens on a wet black cloak and a chain at the belt. 'Constable Gu,' says the man. 'A seal was stolen from the magistrate. Whoever has it is under arrest.'", "门开了，湿透的黑斗篷，腰间一串铁链。“我是顾捕头。”来人说，“知府的印被偷了。谁带着，谁就被捕。”", "ประตูเปิดออก ผ้าคลุมสีดำเปียกชุ่ม โซ่ห้อยที่เอว 'ข้าคือกู้ หัวหน้าชุดจับกุม' ชายผู้นั้นว่า 'ตราของเจ้าเมืองถูกขโมย ใครพกตราไว้ ถูกจับกุมทันที'"),
        "hostile": tr("Captain Gu snaps the chain loose. 'You had your chance to come quietly.'", "顾捕头抖开铁链。“我给过你机会，让你乖乖跟我走。”", "หัวหน้ากู้สะบัดโซ่ 'เจ้ามีโอกาสแล้วที่จะไปกับข้าดี ๆ'"),
        "down": tr("Captain Gu drops to the floor, gasping, his pride in pieces. 'No… prisoner has ever…'", "顾捕头跌坐在地，喘息着，傲气碎了一地。“从来……没有犯人……”", "หัวหน้ากู้ทรุดลงบนพื้นหอบหายใจ ความทระนงแตกเป็นเสี่ยง ๆ 'ไม่เคย... มีนักโทษคนไหน...'"),
        "reward": {"trust": 6, "effect": {"kind": "shortcut", "n": 3},
                   "fact": "If she can make him believe the seal is not here, he will leave her be and open the pass road at first light himself, which lets her leave three beats sooner.",
                   "gain": tr("Gu agrees to clear the road. You can leave 3 beats earlier.", "顾捕头答应为你清出道路。你可以提早 3 拍离开。", "หัวหน้ากู้ตกลงเปิดทางให้ เจ้าออกไปได้เร็วขึ้น 3 จังหวะ")},
        "voice": "Official and clipped, proud, suspicious; calls the young woman 'suspect'.",
        "wants": "He wants the seal back and the thief in chains; he is vain and hates being made a fool of.",
        "calms": "A believable story, a good bribe offered carefully, flattery that does not sound like flattery.",
        "appearance": dict(build="masculine", age="adult", skin="warm", hair_style="short", hair_color="black", eyes="sharp", eye_color="black", expression="fierce",
                           outfit="robe", outfit_color="ink", accent_color="crimson", headwear="scholar_cap", mark="none", weapon="saber", aura="lightning", scene="river"),
    },
    {
        "key": "fang", "talk_limit": 4, "goal": tr("Calm Deputy Fang and he will stand down and tell you the captain's weakness.", '安抚方小乙，他会收手，并告诉你顾捕头的弱点。', 'ปลอบรองฟาง เขาจะลดอาวุธและบอกจุดอ่อนของหัวหน้า'), "name": tr("Deputy Fang", "方小乙", "รองฟางเสี่ยวอี่"), "mood": "police", "arrive": 10, "start_trust": 2, "calm": 5, "fuse": 3,
        "title": tr("Gu's young deputy", "顾捕头的年轻差役", "ลูกน้องหนุ่มของหัวหน้ากู้"),
        "public": tr("Nervous, soaked, and secretly afraid of his captain.", "紧张、浑身湿透，暗地里怕他的头儿。", "ประหม่า เปียกโชก และแอบกลัวหัวหน้าของตัวเอง"),
        "hp": 22, "atk": 3, "defn": 3, "dmg": 4,
        "arrival": tr("A boy in a constable's cap stumbles in, dripping. 'Deputy Fang,' he stammers, 'on the captain's orders, I have to… search… everyone.'", "一个戴着差役帽的少年跌跌撞撞进来，浑身滴水。“我、我是方差役，”他结结巴巴，“奉捕头之命，要……搜……每一个人。”", "เด็กหนุ่มสวมหมวกเจ้าพนักงานเซเข้ามา น้ำหยดติ๋ง ๆ 'รองฟาง...' เขาติดอ่าง 'ตามคำสั่งหัวหน้า ต้อง... ค้น... ทุกคน'"),
        "hostile": tr("Deputy Fang's hands shake, but he draws his short sword. 'I'm sorry, I'm sorry. Please don't make me.'", "方小乙手在抖，还是拔出了短剑。“对不住，对不住。求你别逼我。”", "มือของรองฟางสั่น แต่เขาก็ชักกระบี่สั้น 'ขอโทษ ๆ อย่าบังคับข้าเลย'"),
        "down": tr("Deputy Fang curls up around his stomach. 'Captain Gu is going to kill me.'", "方小乙抱着肚子蜷成一团。“顾捕头会杀了我的。”", "รองฟางงอตัวกุมท้อง 'หัวหน้ากู้ต้องฆ่าข้าแน่'"),
        "reward": {"trust": 5, "effect": {"kind": "edge", "target": "gu", "n": 3},
                   "fact": "The captain never sleeps well in a storm and his sword hand shakes by the third hour of a fight. Wait for that and strike.",
                   "gain": tr("Fang tells you Captain Gu's sword hand shakes late in a fight. You hit Captain Gu much more easily (+3).", "方小乙告诉你顾捕头打久了持剑的手会抖。你打顾捕头容易得多（+3）。", "รองฟางบอกว่ามือถือกระบี่ของหัวหน้ากู้สั่นเมื่อสู้นาน เจ้าโจมตีเขาโดนง่ายขึ้นมาก (+3)")},
        "voice": "Stammering, polite, over-apologising; calls the young woman 'miss'.",
        "wants": "He wants to survive the night without disappointing the captain; he would much rather not fight.",
        "calms": "Kindness, reassurance, a promise that no one will tell the captain.",
        "appearance": dict(build="masculine", age="young", skin="warm", hair_style="short", hair_color="brown", eyes="wide", eye_color="brown", expression="weary",
                           outfit="robe", outfit_color="azure", accent_color="white", headwear="scholar_cap", mark="none", weapon="sword", aura="none", scene="river"),
    },
    {
        "key": "qin", "talk_limit": 3, "goal": tr('Convince Old Qin you are not the thief he hunts, and he will stand down and guard the road for you.', '说服秦无咎你不是他要抓的贼，他会收剑，并替你守住道路。', 'โน้มน้าวลุงฉินว่าเจ้าไม่ใช่โจรที่เขาตามล่า เขาจะเก็บกระบี่และเฝ้าทางให้'), "name": tr("Old Qin", "秦无咎", "ลุงฉิน"), "mood": "aggressive", "arrive": 13, "start_trust": 2, "calm": 7, "fuse": 2,
        "title": tr("The Nameless Blade, righteous hero of the north", "无名剑，北方的正道大侠", "กระบี่ไร้นาม วีรบุรุษธรรมะแห่งภาคเหนือ"),
        "public": tr("A grey-bearded legend who has never been beaten, and never hesitates.", "灰须传奇，从没败过，也从不迟疑。", "ตำนานเคราสีเทา ไม่เคยแพ้ และไม่เคยลังเล"),
        "hp": 35, "atk": 6, "defn": 6, "dmg": 5,
        "arrival": tr("The wind falls silent for a breath. Old Qin steps over the threshold, grey beard frozen with sand, and does not look at anyone but you. 'The seal,' he says. 'Now.'", "风静了一息。秦无咎跨过门槛，灰须上结着沙，目光只落在你一个人身上。“玉印。”他说，“现在。”", "ลมสงบลงชั่วครู่ ลุงฉินก้าวข้ามธรณีประตู เคราสีเทาจับทราย และมองแต่เจ้าคนเดียว 'ตราหยก' เขาว่า 'เดี๋ยวนี้'"),
        "hostile": tr("Old Qin draws a plain iron sword and the whole hall goes cold. 'I do not enjoy this, child.'", "秦无咎拔出一柄朴素铁剑，整个大堂都冷了下来。“孩子，我并不喜欢这样。”", "ลุงฉินชักกระบี่เหล็กธรรมดาเล่มหนึ่ง ทั้งโถงเย็นเยือก 'ข้าไม่ชอบเรื่องนี้เลย เด็กน้อย'"),
        "down": tr("Old Qin sheaths his sword, bleeding. 'Thirty years. Who taught you that?' He smiles for the first time.", "秦无咎还剑入鞘，血顺着衣襟流。“三十年了，谁教你的？”他第一次笑了。", "ลุงฉินเก็บกระบี่เข้าฝัก เลือดไหลลงเสื้อ 'สามสิบปีแล้ว ใครสอนเจ้า?' เขายิ้มเป็นครั้งแรก"),
        "reward": {"trust": 7, "effect": {"kind": "shortcut", "n": 3},
                   "fact": "If he is convinced the thief is not the one he hunts, he will guard the road himself and she can leave three beats earlier.",
                   "gain": tr("Qin vouches for you at the pass. You can leave 3 beats earlier.", "秦无咎在关口替你作保。你可以提早 3 拍离开。", "ลุงฉินรับรองเจ้าที่ด่าน เจ้าออกไปได้เร็วขึ้น 3 จังหวะ")},
        "voice": "Quiet, weary, absolute; speaks in short sentences; calls the young woman 'child'.",
        "wants": "He wants the stolen seal returned to the magistrate, and he does not want to hurt a young person; he will if there is no other way.",
        "calms": "Courage, a promise to return the seal, truth said plainly; he despises begging and clever lies.",
        "appearance": dict(build="masculine", age="elder", skin="tan", hair_style="short", hair_color="silver", eyes="sharp", eye_color="black", expression="calm",
                           outfit="hermit", outfit_color="ink", accent_color="gold", headwear="none", mark="beard", weapon="sword", aura="wind", scene="mountains"),
    },
]

BY_KEY = {c["key"]: c for c in CAST}
ARRIVALS = {c["key"]: c["arrive"] for c in CAST}
ARRIVALS_BY_KEY = ARRIVALS

HERO = {
    "key": "yan", "name": tr("Yan Qi", "燕七", "เยี่ยนชี"),
    "title": tr("Thief", "女贼", "โจรหญิง"),
    "bio": tr("Quick-fingered and quicker-tongued, known on the desert road as the Seventh Swallow. Tonight she lifted the magistrate's jade seal and ran into a sandstorm. Nobody knows her face, but everybody knows what she took.",
              "手快，嘴更快，大漠道上人称“七燕”。今夜她从知府手里偷了玉印，一头撞进沙暴。没人认得她的脸，却人人知道她偷了什么。",
              "มือไว ปากไวกว่า ชาวทางทะเลทรายเรียกว่า 'นางนกนางแอ่นที่เจ็ด' คืนนี้นางขโมยตราหยกของเจ้าเมืองแล้ววิ่งเข้าพายุทราย ไม่มีใครรู้จักหน้านาง แต่ทุกคนรู้ว่านางขโมยอะไร"),
    "appearance": dict(build="feminine", age="young", skin="warm", hair_style="ponytail", hair_color="black", eyes="sharp", eye_color="brown",
                       expression="smirk", outfit="fighter", outfit_color="ink", accent_color="crimson", headwear="headband", mark="none", weapon="saber", aura="wind", scene="lanterns"),
}

GM = {
    "key": "ray", "name": tr("Ray", "说书人 Ray", "Ray"), "title": tr("Storyteller and Game Master", "说书人 · 主持", "ผู้เล่าเรื่องและผู้ดำเนินเกม"),
    "appearance": dict(build="masculine", age="adult", skin="warm", hair_style="short", hair_color="black", eyes="sharp", eye_color="black",
                       expression="smile", outfit="scholar", outfit_color="ink", accent_color="gold", headwear="scholar_cap", mark="none", weapon="fan", aura="ink", scene="lanterns"),
}

# ---------- how it ends ----------

ENDINGS = {
    "escaped": {"title": tr("The storm passes", "风沙已过", "พายุผ่านไป"), "won": True,
                "fallback": tr("The wind drops, and the sun lays one red stripe across the floor. You pick up your pack, step over the sleeping and the wounded, and walk out of the Black Sand Inn with the magistrate's seal still in your shirt. Nobody stops you. In the jianghu, surviving the night is the only victory there is. Ray lifts his teacup to your back as you go.",
                               "风声渐息，阳光在地板上落下一道红线。你拿起行囊，从睡着的人、受伤的人身边走过，揣着知府的玉印走出黑沙客栈。没人拦你。在江湖里，活过这一夜，就是唯一的胜利。你离去时，Ray 对着你的背影举了举茶杯。",
                               "ลมสงบ แสงอาทิตย์ทอดเป็นแถบสีแดงบนพื้น เจ้าหยิบห่อสัมภาระ ก้าวข้ามคนที่หลับและคนที่บาดเจ็บ เดินออกจากโรงเตี๊ยมทรายดำพร้อมตราหยกของเจ้าเมืองที่ยังซ่อนในเสื้อ ไม่มีใครขวาง ในยุทธภพ การรอดผ่านคืนนี้คือชัยชนะเดียวที่มี Ray ยกถ้วยชาให้แผ่นหลังเจ้าตอนเจ้าจากไป")},
    "slain": {"title": tr("Cut down", "命丧刀下", "ถูกสังหาร"), "won": False,
              "fallback": tr("The blade finds you, and the hall goes very quiet. In the end the storm kept its promise to the Black Sand Inn: nobody who shelters here leaves unchanged. Ray sets down his cup. 'People in the jianghu,' he says, 'do not get to choose.'",
                             "刀锋找到了你，大堂静得吓人。到头来，沙暴兑现了对黑沙客栈的承诺：在这里躲过风的人，没有谁能原样离开。Ray 放下茶杯。“人在江湖，”他说，“身不由己。”",
                             "คมดาบหาเจ้าเจอ โถงเงียบกริบ สุดท้ายพายุก็รักษาสัญญากับโรงเตี๊ยมทรายดำ ไม่มีใครที่หลบอยู่ที่นี่ออกไปเหมือนเดิม Ray วางถ้วยชา 'คนในยุทธภพ' เขาว่า 'ไม่อาจเลือกได้เอง'")},
    "arrested": {"title": tr("Taken in chains", "锒铛入狱", "ถูกจับใส่โซ่"), "won": False,
                 "fallback": tr("The chain closes on your wrists and the seal comes out of your shirt. By the time the storm has passed you are on a cart to the magistrate's yard, and the magistrate does not forgive thieves. Ray sighs. 'A good night's work, wasted.'",
                                "铁链锁上了你的手腕，玉印从你衣襟里被掏了出来。沙暴过去时，你已经在去往知府衙门的囚车上，而知府从不饶恕贼。Ray 叹气。“一夜的好功夫，白费了。”",
                                "โซ่คล้องข้อมือเจ้า ตราหยกถูกดึงออกจากเสื้อ เมื่อพายุผ่านไป เจ้าก็อยู่บนเกวียนไปลานศาลเจ้าเมือง และเจ้าเมืองไม่อภัยโจร Ray ถอนหายใจ 'งานที่ดีหนึ่งคืน สูญเปล่า'")},
    "storm": {"title": tr("Lost in the sand", "葬身风沙", "จมหายในทราย"), "won": False,
              "fallback": tr("You step out too early. The wind picks you up like a leaf, and the desert, which is older than every grudge in the inn, takes you without anger. Ray looks at the closed door a long time. 'Some people cannot wait,' he says.",
                             "你出去得太早。风像卷一片叶子一样卷起了你，大漠比客栈里的每一桩恩怨都古老，它毫无怒意地收走了你。Ray 久久望着紧闭的大门。“有些人，就是等不了。”他说。",
                             "เจ้าก้าวออกไปเร็วเกิน ลมหอบเจ้าไปเหมือนใบไม้ ทะเลทรายเก่าแก่กว่าความแค้นทั้งหมดในโรงเตี๊ยม รับเจ้าไว้โดยไม่โกรธเคือง Ray มองประตูที่ปิดสนิทอยู่นาน 'บางคนก็รอไม่ได้' เขาว่า")},
}

START_LINE = tr("The door is barred against the storm. The night begins.", "大门闩上，挡住沙暴。这一夜开始了。", "ประตูลงกลอนกันพายุ ค่ำคืนเริ่มต้นขึ้น")

PROLOGUE = tr(
    "Welcome to the Black Sand Inn. Tonight you are Yan Qi, thief, with the magistrate's jade seal in your shirt. Outside, a sandstorm; inside, a hall that will fill with people who each want something from you. "
    "Talk to them or fight them, as you choose. Every word and every round of a fight is one beat of the night. Survive sixteen beats, and when the wind drops, walk out the door. Choose carefully: in the jianghu, the one who loses a fight does not get to try again.",
    "欢迎来到黑沙客栈。今晚你是燕七，女贼，怀里揣着知府的玉印。门外是沙暴；门里的大堂，会一个个坐满对你有所图的人。"
    "愿意谈就谈，愿意打就打。你说的每一句话、打的每一个回合，都是夜里的一拍。熬过十六拍，等风一停，就走出那扇门。小心：在江湖里，打输的人，没有第二次机会。",
    "ยินดีต้อนรับสู่โรงเตี๊ยมทรายดำ คืนนี้เจ้าคือเยี่ยนชี โจรหญิง พกตราหยกของเจ้าเมืองไว้ในเสื้อ ข้างนอกคือพายุทราย ข้างในคือโถงที่จะเต็มไปด้วยผู้คนที่ต่างต้องการอะไรบางอย่างจากเจ้า "
    "จะคุยหรือจะสู้ก็ได้ ทุกคำพูดและทุกยกที่สู้คือหนึ่งจังหวะของค่ำคืน รอดให้ได้สิบหกจังหวะ แล้วเมื่อลมสงบก็เดินออกจากประตู ระวังให้ดี ในยุทธภพ คนที่แพ้ไม่มีโอกาสครั้งที่สอง")


def public_card(key: str) -> dict:
    c = BY_KEY[key]
    return {"key": key, "name": c["name"], "title": c["title"], "public": c["public"], "mood": c["mood"], "appearance": c["appearance"], "arrive": c["arrive"]}


def hero_card() -> dict:
    return {**{k: HERO[k] for k in ("key", "name", "title", "bio", "appearance")}}


def gm_card() -> dict:
    return {**{k: GM[k] for k in ("key", "name", "title", "appearance")}}


def names_line(people: list | None = None) -> str:
    """How people's names are written in each language, so a Thai or Chinese reply uses the right spelling. Without a list, everybody's."""
    people = people if people is not None else [HERO, GM, *CAST]
    return "; ".join(" / ".join(i18n.parts(p["name"])) for p in people)


def edge_for(edges: dict, key: str) -> int:
    return min(3, edges.get(key, 0))


for _c in CAST:
    assert _c["mood"] in MOODS
for _t in (SETUP, GOAL, HOW_TO, PROLOGUE, *[e["fallback"] for e in ENDINGS.values()], *[a[k] for a in ARTS.values() for k in ("name", "does")],
           *[c[k] for c in CAST for k in ("name", "title", "public", "arrival", "hostile", "down", "goal")], *[c["reward"]["gain"] for c in CAST]):
    assert i18n.complete(_t), _t[:60]
