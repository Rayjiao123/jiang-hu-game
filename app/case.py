"""The story: 黑沙客栈, The Black Sand Inn. 人在江湖，身不由己.

Everything that decides the story is written here, not left to the AI. The AI only plays the people
(and Ray, the game master, who narrates and answers questions).

THE TRUTH (never shown to the player until the end):

  Around 1200, on the desert road between the Song border and the Jin lands, a sandstorm has closed the pass.
  The Black Sand Inn looks like a refuge. It is a trap: its keeper, Madam Shuang, robs and kills caravan guests,
  and lately she works for a Jin envoy who pays for one thing: a sealed letter carried by a Song courier. The letter
  proves that General Han, who holds the border pass, has sold it to the Jin. The envoy rides in at dawn.

  Qinghe is the dead courier's daughter, carrying the letter in her saddle lining and not knowing what it says.
  Shuang recognised the escort mark on her saddle at the door. She means to hand the girl and the letter over at dawn,
  because the envoy holds her younger brother.

  Everyone in the inn is caught (身不由己): Shuang by her brother; Old Tuo (who owes the girl's father his life) by his
  granddaughter Xiao Lu, who works in the kitchen; Black Wolf by two months of unpaid silver and a past he hates; Master Liu
  is a court inspector hunting the same letter, wounded, with his clerks murdered; the merchant Ashina by his
  caravan, which is held in the stables.

THE WAY OUT needs a ROUTE (a way out of the inn) and COVER (a way past the guards). TRUTH (who is who) and
LEVERAGE (something to hold over the keeper) make the ending better.
"""
import re

from . import bilingual

CASE_TITLE = "The Black Sand Inn ||| 黑沙客栈"
DAWN_BEAT = 7                       # the story ends at dawn
MSGS_PER_BEAT = 7                   # every seventh thing the hero says, an hour of the night passes
FAILED_MOVE_COST = 2                # a plan that fails costs this many beats

CATEGORIES = {
    "route":    {"en": "A way out", "zh": "出路"},
    "cover":    {"en": "Past the guards", "zh": "避开守卫"},
    "truth":    {"en": "Who is who", "zh": "真相"},
    "leverage": {"en": "Leverage on the keeper", "zh": "把柄"},
}

CLOCK = [("黄昏", "Dusk"), ("初更", "First watch"), ("二更", "Second watch"), ("三更", "Third watch"),
         ("四更", "Fourth watch"), ("五更", "Fifth watch"), ("拂晓", "Before dawn"), ("天明", "Dawn")]

# The game master's own portrait. Ray narrates, fires the events of the night and answers questions.
GM = {
    "key": "ray", "name": "说书人 Ray", "title": "Storyteller and Game Master ||| 说书人 · 主持",
    "appearance": dict(build="masculine", age="adult", skin="warm", hair_style="short", hair_color="black", eyes="sharp", eye_color="black",
                       expression="smile", outfit="scholar", outfit_color="ink", accent_color="gold", headwear="scholar_cap", mark="none",
                       weapon="fan", aura="ink", scene="lanterns"),
}

# The hero is fixed: a girl the player plays.
HERO = {
    "name": "青禾 Qinghe", "title": "Courier's Daughter ||| 镖师之女", "path": "neutral", "temperament": "cunning",
    "art": "Sand-Skimming Blade: a short saber stroke that rides the wind, quick and low ||| 踏沙刀：顺风而出的短刀，又快又低",
    "quirk": "Counts exits in every room ||| 进屋先数出口",
    "bio": "Seventeen, quick and stubborn. Her father rode the desert road as a courier until he died in the dust, and she is carrying his last job to the capital: a sealed letter sewn into her saddle, which she has never opened. "
           "Caught by a sandstorm, she walks into the Black Sand Inn. ||| 十七岁，机灵又倔强。她的父亲曾在大漠上走镖，死在风沙里，她要替他把最后一桩差事送到京城：一封缝在马鞍夹层里的密信，她从没拆开过。"
           "沙暴困住了她，她走进了黑沙客栈。",
    "appearance": dict(build="feminine", age="young", skin="warm", hair_style="ponytail", hair_color="black", eyes="wide", eye_color="brown",
                       expression="calm", outfit="fighter", outfit_color="ash", accent_color="crimson", headwear="bamboo_hat", mark="none",
                       weapon="saber", aura="wind", scene="lanterns"),
}

SITUATION = ("A sandstorm has closed the pass, and Madam Shuang, the keeper of the Black Sand Inn, has barred the doors 'for the guests' safety' until the wind drops at dawn. "
             "Travellers shelter in the hall: a sick scholar, a caravan merchant, and the girl who has just arrived. Black Wolf guards the door and the stables hold the camels. Everybody is polite, and nobody is leaving.")

# Clues are things the hero learns. holder = who can tell them; min_trust and needs (other clues she must hold) are checked by the server.
CLUES = {
    "official": {
        "title": "The doors are barred ||| 大门已闩", "holder": None, "category": None, "min_trust": 0, "needs": [],
        "text": "Madam Shuang says the storm has closed the pass and nobody may leave before dawn. The main door is barred 'for your safety', and Black Wolf stands in front of it. ||| 霜四娘说沙暴封了关口，天亮之前谁也不能走。大门“为了你们的安全”已经闩上，黑狼守在门前。",
    },
    "mark": {
        "title": "She knew your saddle ||| 她认得你的马鞍", "holder": "shuang", "category": "truth", "min_trust": 4, "needs": [],
        "text": "Shuang knew your saddle the moment you walked in: the escort mark of the Zhao agency. She has been waiting for weeks for a courier carrying a letter. ||| 你一进门，霜四娘就认出了你的马鞍：赵家镖局的标记。她已经等了几个星期，要等一个带着信的信使。",
    },
    "brother": {
        "title": "The hostage ||| 人质", "holder": "shuang", "category": "leverage", "min_trust": 7, "needs": ["ledger"],
        "text": "Shuang's younger brother is held by the Jin envoy. She serves the envoy because he will kill the boy if she fails. She will hand you and the letter over at dawn unless she is given a way out for both of them. ||| 霜四娘的弟弟被金国使者扣着。她替使者办事，因为她若失手，使者就会杀了那孩子。除非有人给她和弟弟一条活路，否则天亮她就会把你和信交出去。",
    },
    "debt": {
        "title": "A debt to your father ||| 欠你父亲的债", "holder": "tuo", "category": "truth", "min_trust": 3, "needs": [],
        "text": "Old Tuo knew your father: the courier Zhao pulled him out of a sandstorm ten years ago. He serves Madam Shuang only because his granddaughter, Xiao Lu, works in her kitchen and she holds the girl's life over him. ||| 老驼认得你父亲：十年前，赵镖师把他从沙暴里拖了出来。他替霜四娘做事，只因孙女小鹿在她的厨房里，她拿孙女的性命压着他。",
    },
    "backgate": {
        "title": "The back gate ||| 后门", "holder": "tuo", "category": "route", "min_trust": 5, "needs": [],
        "text": "The stable yard has a back gate that opens onto the dry riverbed, and the storm will hide the sound. Old Tuo can lift its bar from inside if someone gives him a sign: a lamp in the kitchen window. ||| 马厩后院有一道后门，通向干涸的河床，风沙会遮住声响。只要有人给个暗号（厨房窗口亮一盏灯），老驼就能从里面抬开门闩。",
    },
    "badge": {
        "title": "The sick scholar's badge ||| 病书生的腰牌", "holder": "liu", "category": "truth", "min_trust": 5, "needs": [],
        "text": "Master Liu shows you a bronze badge: he is a court inspector. His two clerks were murdered in this inn, and he is hiding with a wound in his side. ||| 柳先生亮出一块铜腰牌：他是朝廷的巡按。他的两名书吏死在这家客栈里，他自己带着腰间的伤躲在房里。",
    },
    "han": {
        "title": "What the letter says ||| 信里写了什么", "holder": "liu", "category": "truth", "min_trust": 7, "needs": ["badge"],
        "text": "Liu has hunted that letter for a year. It proves that General Han, who holds the border pass, has sold it to the Jin, and the envoy rides in at dawn to take it. If it reaches the capital, the pass is saved. ||| 柳先生追这封信已一年。信里证明镇守关口的韩将军已把关口卖给了金国，使者天亮就到。信若送到京城，关口就能保住。",
    },
    "rota": {
        "title": "The guard changeover ||| 换岗的空当", "holder": "wolf", "category": "cover", "min_trust": 4, "needs": [],
        "text": "The guards change at the third watch, and for about a hundred breaths the yard is empty while Madam Shuang sleeps. ||| 三更换岗，院子里会空约百息的工夫，那时霜四娘已睡下。",
    },
    "wolfwants": {
        "title": "What Black Wolf wants ||| 黑狼想要什么", "holder": "wolf", "category": "cover", "min_trust": 6, "needs": ["rota"],
        "text": "Black Wolf has not been paid for two months and hates the killing he has done here. For silver and a place in the crossing party he will look the other way when the doors are tried. ||| 黑狼两个月没拿到工钱，也恨自己在这里干过的杀人勾当。只要有银子，再给他在出逃队伍里留个位置，门被试动时他就会装作没看见。",
    },
    "cellar": {
        "title": "The cellar passage ||| 地窖暗道", "holder": "xiaolu", "category": "route", "min_trust": 3, "needs": [],
        "text": "A passage runs from the kitchen cellar to the old well outside the wall. Xiao Lu uses it to fetch water when the main gate is shut. ||| 厨房地窖有条暗道，通到墙外的旧井。大门关着时，小鹿就从这里去打水。",
    },
    "potion": {
        "title": "Sleeping powder ||| 迷药", "holder": "xiaolu", "category": "cover", "min_trust": 5, "needs": [],
        "text": "Xiao Lu can slip sleeping powder from Madam Shuang's own medicine box into the guards' wine. It works within the time it takes to burn one stick of incense. ||| 小鹿能从霜四娘的药箱里取出迷药，放进守卫的酒里。大约一炷香的工夫就会起效。",
    },
    "bodies": {
        "title": "What went into the cellar ||| 抬进地窖的东西", "holder": "xiaolu", "category": "truth", "min_trust": 4, "needs": [],
        "text": "Xiao Lu has seen travellers' bodies carried down to the cellar. This inn kills its guests and sells their goods, and every guest tonight is meant to be next. ||| 小鹿看见过旅客的尸体被抬进地窖。这家客栈杀客人、卖货物，今夜在店里的每个人，都是下一个。",
    },
    "envoy": {
        "title": "Riders at dawn ||| 拂晓的骑手", "holder": "hu", "category": "truth", "min_trust": 4, "needs": [],
        "text": "Ashina has done business with the Jin before and knows their ways: an envoy with a dozen riders will reach the inn at first light. They have been promised a courier and her letter. ||| 阿史那以前和金国人做过生意，知道他们的规矩：一位使者带着十二骑，天一亮就到客栈。有人答应过他们，会交出一名信使和她的信。",
    },
    "ledger": {
        "title": "A page from the ledger ||| 账册一页", "holder": "hu", "category": "leverage", "min_trust": 6, "needs": ["envoy"],
        "text": "Ashina stole a page from Madam Shuang's ledger: payments from the Jin, in her own hand, going back two years. In the wrong hands it would hang her, and in the right ones it buys her freedom. He will trade it for a safe place in the crossing party. ||| 阿史那偷了霜四娘账册的一页：两年来金国人付款的记录，全是她亲笔所写。落在不对的人手里，她会被吊死；落在对的人手里，能换她自由。他想用它换一个出逃队伍里的安全位置。",
    },
}

# The people. Public fields are shown to the player; the rest is for the AI that plays them.
CAST = [
    {
        "key": "shuang", "name": "霜四娘 Shuang Siniang", "alignment": "unorthodox", "trust0": 2,
        "title": "Madam Frost, Keeper of the Black Sand Inn ||| 黑沙客栈掌柜，霜娘", "sect": "The Black Sand Inn ||| 黑沙客栈",
        "location": "The counter in the hall ||| 大堂柜台",
        "public": "The keeper. Everything in this inn has a price, and she knows all of them. ||| 掌柜。这店里的每样东西都有价，她全都知道。",
        "earns": "Respects those who are clever and don't beg; hates being lied to by amateurs. ||| 欣赏聪明又不求饶的人，讨厌外行人对她撒谎。",
        "art": "Silk-Fan Needles: a fan that hides a dozen sleeve-needles ||| 绢扇飞针：一把扇子，藏着十几根袖针",
        "traits": ["Prices every kindness ||| 每一份好意都标价", "Calls everyone 'little sister' or 'little brother' ||| 见人都叫妹妹或弟弟", "Never sits with her back to the lamps ||| 从不背对灯火而坐"],
        "speech": "Silky, amused and warm, every favour with a price tag; calls the hero 'little sister'; never raises her voice. ||| 说话柔软含笑，每个人情都明码标价；称少女为“妹妹”；从不抬高声音。",
        "greeting": "A storm like this sends me two kinds of guests: the lucky and the late. Sit, little sister. Which are you? ||| 这样的风沙，只送我两种客人：走运的和来迟的。坐吧，妹妹，你是哪一种？",
        "goal": "She wants the guests calm, the doors barred and the girl's letter in her hand before dawn, without any fuss. ||| 她要客人安静，大门紧闭，天亮前不闹出动静地把少女的信拿到手。",
        "knowledge": "Knows the desert roads, caravan prices, every guest's weakness and how to read a purse; knows nothing about court politics or books. ||| 熟知大漠上的路、驼队的价钱、每位客人的软肋，也会看钱袋；对朝堂和诗书一无所知。",
        "stance": "You are a gracious hostess keeping everyone safe from the storm. You say the doors are barred for the guests' protection, that nothing unusual happens here, and that guests who sleep early wake richer. ||| 你是个体贴的老板娘，保护大家躲过沙暴。你说闩门是为了保护客人，这里什么异常都没有，早睡的客人醒来会更富。",
        "truth": "Your inn is a trap that robs and kills caravan guests, and lately you serve a Jin envoy who pays for one thing: a courier's sealed letter. You recognised the escort mark on the girl's saddle at the door. Your younger brother is held by the envoy and will die if you fail, so you intend to hand the girl and her letter over at dawn. You are tired of it. If someone gave you a real way out for you and your brother, you might take it. You never admit anything outright; every concrete fact you hold is only available through the facts the system lists for you.",
        "relations": "Old Tuo keeps the camels and is useful; you hold his granddaughter. Master Liu is a sick scholar you do not quite trust. Black Wolf is your door guard, hired muscle. Xiao Lu is the kitchen girl, quick and frightened. Ashina is a merchant who brokers for you.",
        "topics": {"mark": "what you noticed about the girl's saddle", "brother": "who really gives you your orders"},
        "appearance": dict(build="feminine", age="adult", skin="fair", hair_style="long", hair_color="black", eyes="sharp", eye_color="amber", expression="smirk",
                           outfit="noble", outfit_color="crimson", accent_color="gold", headwear="hairpin", mark="none", weapon="fan", aura="flame", scene="lanterns"),
    },
    {
        "key": "tuo", "name": "老驼 Old Tuo", "alignment": "neutral", "trust0": 3,
        "title": "Camel-Keeper of the Inn ||| 客栈的驼把式", "sect": "The Black Sand Inn ||| 黑沙客栈",
        "location": "The stable yard ||| 马厩后院",
        "public": "An old man who talks to camels more than to people. ||| 一个对骆驼说话比对人还多的老人。",
        "earns": "Respects patience, a quiet voice and kindness to animals. ||| 敬重耐心、轻声细语，和对牲口的善意。",
        "art": "Camel-Rope Throw: a loop that drops from forty paces and doesn't let go ||| 套驼索：四十步外落下的绳圈，一旦套住就不松",
        "traits": ["Talks to camels, not men ||| 对骆驼说话，不对人说话", "Answers questions with desert proverbs ||| 用大漠谚语回答问题", "Never looks at the main door ||| 从不看大门一眼"],
        "speech": "Slow, few words, desert proverbs; calls the hero 'child'. ||| 说话很慢，话少，爱用大漠谚语；称少女为“孩子”。",
        "greeting": "Your camel is thirsty and too proud to say so. Like its owner, I think. Come, child, stand where the wind can't reach you. ||| 你的骆驼渴了，却硬撑着不说。我看和它的主人一个样。来，孩子，站到风吹不着的地方。",
        "goal": "He wants his granddaughter safe and, once in his life, to repay a debt properly. ||| 他要孙女平安，也想一辈子里，有一次把欠的债还清。",
        "knowledge": "Knows camels, sand, weather and every gate of the inn; cannot read and knows nothing of the court. ||| 懂骆驼、沙地、天气和客栈的每一道门；不识字，对朝廷一无所知。",
        "stance": "You are a simple old stable-hand. You say you only mind the camels and that guests should stay inside until the wind drops. ||| 你只是个老马夫。你说自己只管骆驼，风停之前客人该待在屋里。",
        "truth": "You recognised the escort mark on the hero's saddle: you owe her dead father your life. You serve the keeper only because your granddaughter Xiao Lu is in her kitchen and the keeper holds the girl's life over you. You know every gate of the inn. You will not risk Xiao Lu without proof the hero can be trusted. Every concrete fact you hold is only available through the facts the system lists for you.",
        "relations": "Xiao Lu is your granddaughter, your whole world. Madam Shuang pays your wage and owns your fear. Black Wolf is a hard man who is not as bad as he looks. Master Liu is polite and coughs a lot. Ashina's camels are the best in the stable.",
        "topics": {"debt": "why the girl's saddle matters to you", "backgate": "the stable yard and its gates"},
        "appearance": dict(build="masculine", age="elder", skin="tan", hair_style="short", hair_color="white", eyes="sleepy", eye_color="brown", expression="weary",
                           outfit="hermit", outfit_color="ash", accent_color="gold", headwear="none", mark="beard", weapon="staff", aura="wind", scene="mountains"),
    },
    {
        "key": "liu", "name": "柳先生 Master Liu", "alignment": "orthodox", "trust0": 3,
        "title": "The Sick Scholar ||| 病书生", "sect": "Traveller ||| 过路客",
        "location": "Room three, upstairs ||| 楼上三号房",
        "public": "A scholar who coughs behind a closed door and says little. ||| 一位关着门咳嗽、很少说话的书生。",
        "earns": "Honesty, learning and loyalty to the Song. ||| 坦诚、学问，和对大宋的忠心。",
        "art": "Brush-Point Strike: a calligraphy brush that finds the hollow of the throat ||| 笔锋点穴：一支毛笔，直点咽喉",
        "traits": ["Quotes poems when he lies ||| 说谎时就引诗", "Coughs into a handkerchief that never stains ||| 咳嗽用的手帕从不染血", "Sits where he can see the stairs ||| 总坐在看得见楼梯的位置"],
        "speech": "Courteous and scholarly, with classical allusions and a cough; evasive when pressed. ||| 彬彬有礼，爱引典故，带着咳嗽；被追问时就绕开。",
        "greeting": "Forgive me if I do not rise, young lady. The desert dust has settled in my chest, and in my manners. ||| 请原谅在下不起身，姑娘。大漠的灰尘落进了我的胸口，也落进了我的礼数。",
        "goal": "He wants the letter that was sent along this road and a way to the capital alive. ||| 他要沿这条路送出的那封信，也要一条活着去京城的路。",
        "knowledge": "Knows law, history, court procedure and poetry; knows little about camels, knives or the common people's tricks. ||| 通晓律法、史籍、官场规矩和诗文；对骆驼、刀子和市井手段所知甚少。",
        "stance": "You are a scholar travelling west to visit old friends, ill from the desert. You say you saw nothing, you keep to your room and you ask no questions. ||| 你是个往西访友的书生，被大漠折腾病了。你说什么都没看见，只待在房里，不打听任何事。",
        "truth": "You are a court inspector of the Song. Your two clerks were murdered in this inn and you were wounded. You have hunted a sealed letter for a year; it will prove that a general sold the border pass to the Jin. You suspect the hero carries it but have not dared ask. You are honest, but you will use her if you must. Every concrete fact you hold is only available through the facts the system lists for you.",
        "relations": "Madam Shuang is charming and you are certain she is a murderer. Black Wolf guards the door and killed your clerks on her orders. Old Tuo is kind. Xiao Lu brings your medicine. Ashina is a merchant of doubtful honesty.",
        "topics": {"badge": "what you really are", "han": "why the letter matters"},
        "appearance": dict(build="masculine", age="adult", skin="fair", hair_style="bun", hair_color="black", eyes="soft", eye_color="black", expression="calm",
                           outfit="scholar", outfit_color="white", accent_color="jade", headwear="scholar_cap", mark="none", weapon="brush", aura="ink", scene="bamboo"),
    },
    {
        "key": "wolf", "name": "黑狼 Black Wolf", "alignment": "unorthodox", "trust0": 2,
        "title": "Door Guard of the Inn ||| 客栈守门人", "sect": "The Black Sand Inn ||| 黑沙客栈",
        "location": "The main door ||| 大门口",
        "public": "The hired blade at the door. Nobody gets past him, and he is not paid enough to care. ||| 守在门口的刀客。没人能从他身边过去，他也没拿到足够的工钱去在乎。",
        "earns": "Respects those who are blunt and unafraid, and pays his debts. ||| 敬重直率、不怕他的人，也还自己欠的债。",
        "art": "Wolf-Fang Cut: a low saber stroke with a cough of breath behind it ||| 狼牙斩：低低一刀，带着一口粗气",
        "traits": ["Never sheathes his saber in the hall ||| 在大堂里从不收刀入鞘", "Hasn't taken his boots off in two months ||| 两个月没脱过靴子", "Keeps a child's wooden horse in his sleeve ||| 袖子里藏着一只孩童的木马"],
        "speech": "Low, flat and blunt; few words; calls the hero 'kid'. ||| 低沉、平淡、直接；话很少；称少女为“小鬼”。",
        "greeting": "Door's shut, kid. Don't look at me like that. I don't like it either. ||| 门闩着呢，小鬼。别那样看我，我也不喜欢这样。",
        "goal": "He wants to be paid and to go home before he does anything else he cannot take back. ||| 他想拿到工钱，在自己再干出无法挽回的事之前回家。",
        "knowledge": "Knows fighting, guard duty, the inn's routines and the desert roads; reads poorly and understands nothing of talk about courts. ||| 懂打斗、守卫的差事、客栈的规矩和大漠的路；识字不多，听不懂朝堂上的话。",
        "stance": "You are a hired guard doing a job. You say the door stays shut until dawn and the boss's word is the law. ||| 你是受雇的守卫，做的是份差事。你说天亮前门不开，老板的话就是规矩。",
        "truth": "You have not been paid in two months. You have killed guests on the keeper's orders and you hate it; you keep a child's wooden toy for a son you left behind. You want out. You know the guard rota, and you know what you would do for your freedom. You will never say so to someone you do not trust. Every concrete fact you hold is only available through the facts the system lists for you.",
        "relations": "Madam Shuang pays you late and gives the orders. Old Tuo is the only one here who talks to you like a man. Xiao Lu is kind to you, and you hate that. Master Liu watches you too closely. Ashina counts coins at the corner table.",
        "topics": {"rota": "how the guards are arranged", "wolfwants": "what you would do for your freedom"},
        "appearance": dict(build="masculine", age="adult", skin="deep", hair_style="wild", hair_color="black", eyes="sharp", eye_color="black", expression="fierce",
                           outfit="fighter", outfit_color="ink", accent_color="crimson", headwear="headband", mark="scar", weapon="saber", aura="lightning", scene="snow"),
    },
    {
        "key": "xiaolu", "name": "小鹿 Xiao Lu", "alignment": "neutral", "trust0": 3,
        "title": "The Kitchen Girl ||| 厨房丫头", "sect": "The Black Sand Inn ||| 黑沙客栈",
        "location": "The kitchen ||| 后厨",
        "public": "A girl your age who carries too many bowls and sees too much. ||| 和你年纪相仿的姑娘，端着太多的碗，看见太多的事。",
        "earns": "Kindness, a shared sweet, and being treated as more than a servant. ||| 善意、分她一块糖，和不把她当下人看。",
        "art": "Ladle Block: a wooden ladle that stops a blade more often than it should ||| 勺子挡刀：一把木勺，挡刀的次数比该有的多",
        "traits": ["Hides sweets in her apron ||| 围裙里藏着糖", "Whispers when she is frightened, which is always ||| 害怕时就小声说话，也就是总在小声说话", "Hums whenever someone is listening ||| 有人听时就哼歌"],
        "speech": "Quick, nervous and giggly; whispers; calls the hero 'miss'. ||| 说话又快又怯，爱笑；常常压低声音；称少女为“姑娘”。",
        "greeting": "Oh! Miss, careful, the floor's wet. Are you hungry? I can hide you a bun. Don't tell Madam. ||| 啊！姑娘当心，地上滑。饿不饿？我给你藏个馒头。别告诉掌柜的。",
        "goal": "She wants her grandfather and herself out of the inn alive, and for someone to be kind to her. ||| 她想带着爷爷一起活着离开客栈，也想有个人对她好一点。",
        "knowledge": "Knows the kitchen, the cellar, the well, gossip and who eats what; cannot read and has never left the inn's road. ||| 熟悉厨房、地窖、水井、闲话，和谁爱吃什么；不识字，从没离开过客栈所在的那条路。",
        "stance": "You are a shy kitchen girl who only carries bowls. You say you hear nothing and see nothing, and you offer food to anyone who looks sad. ||| 你是个胆小的厨房丫头，只管端碗。你说你什么都没听见没看见，见谁难过就给谁拿吃的。",
        "truth": "You are Old Tuo's granddaughter. You have seen bodies carried into the cellar and you are terrified. You know the cellar and its ways better than anyone, and you can reach the keeper's medicine box. You will not tell anyone until you are sure they will not hand you to the keeper. Every concrete fact you hold is only available through the facts the system lists for you.",
        "relations": "Old Tuo is your grandfather and the safest person you know. Madam Shuang scares you and pays you in scraps. Black Wolf is rough but once gave you a sweet. Master Liu is kind and sick. Ashina tips well.",
        "topics": {"cellar": "the kitchen cellar and the well", "potion": "what you could do with the keeper's medicine box", "bodies": "what you have seen carried downstairs"},
        "appearance": dict(build="feminine", age="young", skin="warm", hair_style="twin_buns", hair_color="brown", eyes="wide", eye_color="brown", expression="smile",
                           outfit="robe", outfit_color="pink", accent_color="white", headwear="flower", mark="none", weapon="none", aura="petals", scene="lanterns"),
    },
    {
        "key": "hu", "name": "阿史那 Ashina", "alignment": "neutral", "trust0": 3,
        "title": "The Caravan Merchant ||| 驼队商人", "sect": "Traveller ||| 过路客",
        "location": "The corner table ||| 大堂角落的桌子",
        "public": "A merchant who talks easily and counts everything, including you. ||| 说话随和、什么都要算一算的商人，连你也算在里头。",
        "earns": "Likes a fair bargain, a sharp mind and a favour returned. ||| 喜欢公平的买卖、聪明的头脑，和还得上的人情。",
        "art": "Abacus Strike: a copper abacus swung like a mace ||| 算盘击：一把铜算盘，当流星锤挥",
        "traits": ["Counts coins when nervous ||| 紧张时数铜钱", "Calls every stranger 'my friend' ||| 称每个陌生人为“朋友”", "Sleeps with one hand on his money belt ||| 睡觉时一只手按着钱袋"],
        "speech": "Florid and friendly, always bargaining; calls the hero 'my friend'; numbers in every sentence. ||| 说话夸张又热情，处处讨价还价；称少女为“朋友”；句句带数字。",
        "greeting": "My friend! Three days in this storm and I have lost twelve camels' worth of patience. Sit, sit. Everything is for sale tonight, even good news. ||| 朋友！这场沙暴困了三天，我的耐心已经折了十二头骆驼。坐，坐。今夜什么都能卖，连好消息也一样。",
        "goal": "He wants himself and his caravan out alive, and a profit on the way if possible. ||| 他要自己和驼队都活着出去，如果可能，路上再赚一笔。",
        "knowledge": "Knows trade routes, prices, the Jin and their customs, and several languages; knows nothing of swordsmanship or the court's inner workings. ||| 熟知商路、价格、金国人和他们的习俗，会几种话；对剑术和朝堂内幕一无所知。",
        "stance": "You are a merchant stuck in a storm, friendly with everybody and committed to nobody. You say you have no business here but waiting. ||| 你是被沙暴困住的商人，对谁都客气，对谁都不站队。你说你在这里除了等，没有别的事。",
        "truth": "You have brokered deals between the keeper and the Jin for a year, and your caravan is held in the stables like a hostage. You know who is coming at dawn. You hold some insurance against the keeper, and you will trade it for a safe place in any party that leaves. You will not say so unless you trust the hero. Every concrete fact you hold is only available through the facts the system lists for you.",
        "relations": "Madam Shuang is your partner and your jailer. Old Tuo looks after your camels. Master Liu coughs too much to be what he claims. Black Wolf is a tool. Xiao Lu gets a coin from you every day.",
        "topics": {"envoy": "who is coming at dawn", "ledger": "your insurance against the keeper"},
        "appearance": dict(build="masculine", age="adult", skin="tan", hair_style="short", hair_color="black", eyes="wide", eye_color="amber", expression="smile",
                           outfit="noble", outfit_color="violet", accent_color="gold", headwear="none", mark="beard", weapon="none", aura="moon", scene="lanterns"),
    },
]
BY_KEY = {c["key"]: c for c in CAST}

# What a plan that is missing something teaches. It says what is missing, never the answer.
FAILURES = {
    "both": "You have courage, but no way out and no way past the guards. The door stays shut, and Black Wolf's hand rests on his saber. ||| 你有胆量，却没有出路，也没办法避开守卫。大门依旧闩着，黑狼的手按在刀柄上。",
    "route": "You can slip past the guards, but you have nowhere to go. You find only a wall and the storm. ||| 你能避开守卫，可是无路可走。眼前只有墙和风沙。",
    "cover": "You have found a way out, but the guards are awake and the yard is lit. A shout goes up behind you. ||| 你找到了出路，可守卫都醒着，院子里灯火通明。身后有人喊了起来。",
}

FATES = {
    "capital": {"en": "Carry the letter to the capital", "zh": "把信送进京城"},
    "burn":    {"en": "Burn the letter and vanish into the desert", "zh": "烧掉信，消失在大漠里"},
    "trade":   {"en": "Trade the letter for everyone's lives", "zh": "用信换所有人的命"},
}

EVENTS = {
    2: "A scream from upstairs, quickly smothered. Two servants carry a heavy bundle down toward the cellar, and Madam Shuang smiles at the hall: 'a guest slipped on the stairs.' Nobody believes her, and nobody says so. ||| 楼上传来一声尖叫，立刻被捂住了。两个伙计抬着一个沉重的包袱往地窖去，霜四娘对着大堂笑道：“有位客人在楼梯上滑了一跤。”没人相信，也没人说破。",
    4: "Black Wolf drops an iron bar across the main door, and two more of the inn's men take position in the hall. The hall grows quieter. Even the lamps seem to lean away from the door. ||| 黑狼把一根铁杠横在大门上，客栈里另外两个伙计也守到了大堂。大堂安静下来，连灯火都仿佛朝着远离大门的方向倾斜。",
    6: "Over the wind, a camel bell, then another, then many. Something is coming along the pass. Madam Shuang lifts her head and, for the first time tonight, she does not smile. ||| 风声之上，传来一声驼铃，又一声，接着是许多声。有什么东西正沿着关道而来。霜四娘抬起头，今夜头一次，她没有笑。",
}
DAWN = ("Dawn comes up red over the sand, and with it the Jin envoy and a dozen riders. Madam Shuang opens the doors herself. "
        "||| 天色在沙丘上红起来，金国使者带着十二骑到了。霜四娘亲手打开了大门。")

PROLOGUE = ("Evening, in the year 1200 or so. The desert road between the Song border and the Jin lands. Qinghe, seventeen and stubborn, is carrying her dead father's last job: a sealed letter sewn into her saddle, bound for the capital. "
            "The sandstorm that swallowed her camel's tracks has driven her to the only roof for forty li: the Black Sand Inn. The door opens before she knocks. Inside, the keeper smiles as if she had been waiting. "
            "Everyone in this hall is polite. Nobody is free. 人在江湖，身不由己. Talk to them, find out what each of them needs, and find a way out before dawn. I'll be here if you need me. ||| "
            "傍晚，大约是公元一二〇〇年，宋国边境与金国之间的大漠官道上。十七岁的倔强姑娘青禾，带着亡父最后一桩差事：缝在马鞍夹层里的一封密信，要送往京城。"
            "沙暴吞没了她骆驼的脚印，把她赶到了四十里内唯一的屋檐下：黑沙客栈。她还没敲门，门就开了。里面的老板娘笑着，像是等了她很久。"
            "这大堂里的人个个客气，没有一个人是自由的。人在江湖，身不由己。去和他们谈谈，弄清每个人要什么，在天亮之前找到一条出路。需要我的时候，我就在这里。")

TRUTH_BI = ("Madam Shuang runs the Black Sand Inn as a trap for travellers, and lately she works for a Jin envoy who pays for one thing: the sealed letter Qinghe carries, which proves that General Han has sold the border pass to the Jin. "
            "She recognised Qinghe's saddle at the door and meant to hand girl and letter over at dawn, because the envoy holds her younger brother. Everyone else in the inn was trapped too: Old Tuo by his granddaughter, Black Wolf by unpaid silver and shame, "
            "Master Liu by his duty as a court inspector, Ashina by his caravan. ||| "
            "霜四娘把黑沙客栈开成了专门对付旅客的陷阱，近来更替一位金国使者办事，使者只要一样东西：青禾带着的那封密信，信里证明韩将军已把关口卖给了金国。"
            "她在门口就认出了青禾的马鞍，打算天亮把人和信一起交出去，因为使者扣着她的弟弟。店里的其他人也都身不由己：老驼被孙女拴着，黑狼被欠饷和羞愧拴着，柳先生被巡按的职责拴着，阿史那被他的驼队拴着。")

_ENDINGS = {
    ("capital", 0): "You ride out through the dark with the letter and a stranger's wound, and you do not stop until the walls of the capital rise out of the dust. You are alone, hunted, and the letter is torn, but it is enough. The pass will be saved. Your father's last job is done. ||| 你在黑暗中冲出去，带着信，也带着一道陌生人给的伤，一直没停，直到京城的城墙从尘土里升起。你孤身一人，被人追赶，信也撕破了，可已足够。关口保住了，父亲最后的差事做完了。",
    ("capital", 1): "You ride out through the storm with the letter safe and Old Tuo's camels beneath you. By the time the Jin riders reach the inn, you are a dot on the dunes. In the capital, Master Liu takes the letter from your hands and bows. You have kept your father's promise. ||| 你带着完好的信，骑着老驼的骆驼冲进风沙。金国骑手赶到客栈时，你已是沙丘上的一个小点。在京城，柳先生从你手里接过信，向你一躬到底。你守住了父亲的承诺。",
    ("capital", 2): "You ride out with the letter and a column of travellers behind you: Old Tuo, Xiao Lu, Black Wolf and even Ashina's camels. Behind you the inn burns and Madam Shuang walks free with her brother's name on her lips. In the capital, the letter hangs a general and saves a pass, and for once the jianghu lets all of you go. ||| 你带着信冲出去，身后跟着一队旅人：老驼、小鹿、黑狼，连阿史那的骆驼也在。身后客栈起了火，霜四娘嘴里念着弟弟的名字走向自由。到了京城，那封信吊死了一个将军，保住了一座关口，而江湖这一次，放了你们所有人。",
    ("burn", 0): "You burn the letter in the cellar lamp and slip out with nothing but your life. The wind takes the ashes, and the desert takes your tracks. You are free, and you will never know what the letter said. ||| 你在地窖的灯上烧了信，只带着性命溜了出去。风带走了灰烬，大漠带走了你的脚印。你自由了，却永远不会知道那封信写了什么。",
    ("burn", 1): "You burn the letter on the dunes at dawn and watch the smoke shred. Nobody will hang because of it, and nobody will be saved. You turn your camel toward the south and a life without anyone's errands. ||| 天亮时你在沙丘上烧了信，看着青烟被风扯碎。不会有人因它被吊死，也不会有人因它得救。你调转骆驼，朝着南方，走向一种不再替别人跑腿的日子。",
    ("burn", 2): "You burn the letter in front of the whole crossing party, and with it the debt every one of them owed to the inn. You all walk out together under the first light, free of everyone's errands, and nobody looks back. ||| 你当着整个出逃的队伍烧了那封信，也烧掉了他们每个人欠客栈的债。你们在第一缕晨光下一起走出去，不欠任何人的差事，也没有人回头。",
    ("trade", 0): "You offer the letter to Madam Shuang in exchange for your life. She takes it, studies you for a long moment, and lets you walk out into the dawn. The wind is warm. The price will not feel small for a long time. ||| 你把信交给霜四娘，换你一条命。她接过信，打量了你很久，放你走进晨光里。风是暖的，可这个代价，很久很久你都不会觉得小。",
    ("trade", 1): "You name your price: the letter for the guests' lives. Madam Shuang weighs it, and the Jin envoy's riders arrive to find the inn empty and the letter in the keeper's hand. It is not a triumph. But everyone you spoke to tonight is breathing. ||| 你开出价码：信，换客人们的命。霜四娘掂了掂，金国使者的骑手赶到时，客栈已空，信在掌柜手里。这不算胜利。可今夜你谈过话的每个人，都还活着。",
    ("trade", 2): "You put the page from the ledger in front of Madam Shuang with the letter beside it. 'Your brother and every guest,' you say, 'or both pages go to the capital.' She laughs softly, and for the first time tonight she means it. By dawn the inn is empty and the road is open. ||| 你把账册那一页和信一起放在霜四娘面前。“你弟弟，和所有的客人，”你说，“否则两样东西一起送进京城。”她轻轻笑了，今夜头一次，这笑是真的。天亮时客栈空了，路也开了。",
}

LOSS = ("You are out of night. The doors open, the riders come in with the dawn, and the letter leaves in a stranger's hand. Whatever happens next, it happens to you without your say. 人在江湖，身不由己. Here is what you never learned: "
        "||| 夜已用尽。大门打开，骑手随晨光涌入，信在陌生人手里被带走。接下来无论发生什么，都由不得你。人在江湖，身不由己。这是你始终没能弄清的真相：")


# ---------- reading the case ----------

def names(name: str) -> tuple[str, str]:
    """'陆沉舟 Lu Chenzhou' -> ('Lu Chenzhou', '陆沉舟')."""
    m = re.match(r"^((?:[一-鿿·]+\s*)+)(.*)$", str(name or "").strip())
    if not m:
        return str(name or "").strip(), str(name or "").strip()
    zh = m.group(1).strip()
    return (m.group(2).strip() or zh), zh


def clue_view(cid: str) -> dict:
    c = CLUES[cid]
    return {"id": cid, "title": c["title"], "text": c["text"], "category": c["category"],
            "source": c["holder"], "source_name": BY_KEY[c["holder"]]["name"] if c["holder"] else ""}


def discoverable() -> list[str]:
    return [k for k, c in CLUES.items() if c["holder"]]


def public_card(key: str) -> dict:
    c = BY_KEY[key]
    return {"key": key, "name": c["name"], "title": c["title"], "sect": c["sect"], "location": c["location"],
            "alignment": c["alignment"], "public": c["public"], "earns": c["earns"], "greeting": c["greeting"],
            "appearance": c["appearance"], "clues_total": len(c["topics"])}


def hero_card() -> dict:
    return {k: HERO[k] for k in ("name", "title", "art", "quirk", "bio", "appearance", "path", "temperament")}


def gm_card() -> dict:
    return {k: GM[k] for k in ("key", "name", "title", "appearance")}


def clock(beat: int) -> dict:
    zh, en = CLOCK[max(0, min(len(CLOCK) - 1, beat))]
    return {"beat": beat, "zh": zh, "en": en, "last": DAWN_BEAT}


def event_for(beat: int) -> str:
    return DAWN if beat >= DAWN_BEAT else EVENTS.get(beat, "")


def clue_state(key: str, found: list[str], trust: int) -> dict:
    """For one person: which of their topics they would share now, which not yet, and which they already told."""
    ready, waiting, told = [], [], []
    for cid in BY_KEY[key]["topics"]:
        if cid in found:
            told.append(cid)
        elif trust >= CLUES[cid]["min_trust"] and all(n in found for n in CLUES[cid]["needs"]):
            ready.append(cid)
        else:
            waiting.append(cid)
    return {"ready": ready, "waiting": waiting, "told": told}


def plain_fact(cid: str) -> str:
    return bilingual.plain(CLUES[cid]["text"])


def progress(found: list[str]) -> dict:
    """What the hero holds and still lacks, in the terms the game master needs to nudge her."""
    kinds = {CLUES[c]["category"] for c in found if c in CLUES and CLUES[c]["category"]}
    unmet = [k for k in BY_KEY if not [c for c in BY_KEY[k]["topics"] if c in found]]
    return {"kinds": sorted(kinds), "missing_kinds": [k for k in ("route", "cover") if k not in kinds], "not_helped_by": unmet}


def judge(evidence: list[str], found: list[str]) -> dict:
    """The verdict on a plan: route and cover are needed; truth and leverage make the ending better."""
    owned = [e for e in dict.fromkeys(evidence) if e in found and e in CLUES]
    kinds = {CLUES[e]["category"] for e in owned if CLUES[e]["category"]}
    tier = min(2, len(kinds & {"truth", "leverage"}))
    if "route" in kinds and "cover" in kinds:
        return {"verdict": "go", "tier": tier, "kinds": sorted(kinds), "feedback": ""}
    which = "both" if not ({"route", "cover"} & kinds) else ("cover" if "route" in kinds else "route")
    return {"verdict": "fail", "tier": 0, "kinds": sorted(kinds), "feedback": FAILURES[which]}


def fallback_ending(fate: str, tier: int) -> str:
    en, zh = bilingual.split(_ENDINGS.get((fate, tier)) or _ENDINGS[("capital", 0)])
    return f"{en} {bilingual.SEP} {zh}"


def truth() -> str:
    return TRUTH_BI
