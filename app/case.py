"""The murder mystery: 剑崖疑案, The Sword Cliff Murder.

Everything that decides the story is written here, not left to the AI. The AI only plays the people.

THE TRUTH (never shown to the player, and only the killer's own prompt knows it):

  Three weeks ago Yun Wuya, Master of Cloud Sword Pavilion, had a numbing herb (silver-vein dewgrass, grown
  only in the Pavilion's garden) put in the champion Lu Chenzhou's wine so the Pavilion would not lose the
  coming Sword Gathering. Lu's hand went numb. As a second step he hired a frontier blade, Leng Qianshan,
  through a go-between, paying in Pavilion silver, to cripple Lu for good.

  On the night of the murder, at the third watch, Yun was burning the leftover herb at the garden wall. The
  player's beloved, awake and out for a walk, passed by, smelled the sweet smoke and asked kindly what he was
  burning, adding that the healer Bai Suxin would know the plant and they would ask her in the morning. Yun
  panicked and killed them with a full nine-layer thrust of the Nine-Cloud Sword at the garden's side gate.
  He carried the body under a covered lantern to the top of the Sword Cliff path and let it fall, whispering
  an apology. At dawn he called it a fall in the dark and had them buried before noon, refusing Bai's request
  to examine the body.

THE SUSPECTS, and what makes each look guilty (all of them are innocent but Yun):

  Xie Sanwan     lied about being at the inn that night: he was carrying wine up to his sworn brother Lu
  Su Wanzhao     found the beloved's keepsake and kept it: she feared it pointed at her own Pavilion
  Bai Suxin      saw the wound but is bound by a healer's oath and will not name her patient
  Leng Qianshan  a hired blade, lurking near the Pavilion, sent to cripple the champion
  Lu Chenzhou    was at the scene; hiding, drunk and crippled (his hand could not have made the wound)

PROOF. A clue is worth one kind of proof: how it was done, where it happened, who was there, why (or the
cover-up), or who it could not be. An accusation needs the right person and evidence of at least three kinds.
"""
import re

from . import bilingual

CASE_TITLE = "The Sword Cliff Murder ||| 剑崖疑案"
CULPRIT = "yun"
ATTEMPTS = 3
PROOF_NEEDED = 3

CATEGORIES = {
    "how":    {"en": "How it was done", "zh": "手法"},
    "where":  {"en": "Where it happened", "zh": "地点"},
    "who":    {"en": "Who was there", "zh": "在场者"},
    "why":    {"en": "Why, or the cover-up", "zh": "动机与掩盖"},
    "clears": {"en": "Who it could not be", "zh": "排除嫌疑"},
}

# Clues. holder = who can give it; min_trust and needs (other clues the hero must already hold) are checked by the server.
# {beloved} and {token} are filled in from the player's character.
CLUES = {
    "official": {
        "title": "The official story ||| 官方说法", "holder": None, "category": None, "min_trust": 0, "needs": [],
        "text": "The Pavilion says {beloved} lost their footing on the dark Sword Cliff path at the third watch and fell. The body was found at dawn and buried before noon. ||| 云剑阁说，{beloved}三更时在黑暗的剑崖山道上失足坠崖，清晨被发现，中午前已下葬。",
    },
    "burning": {
        "title": "Sweet smoke in the garden ||| 园中的甜烟", "holder": "xie", "category": "why", "min_trust": 3, "needs": [],
        "text": "The Pavilion gardener's boy told Xie that Master Yun has burned something in the garden pit every night this week. The smoke smells sweet, and on the morning {beloved} was found the ashes were still warm. ||| 云剑阁园丁的小徒弟告诉谢三碗：本周每晚，云阁主都在园中的火坑里烧东西，烟味发甜；{beloved}被发现的那天清晨，灰烬还是热的。",
    },
    "footsteps": {
        "title": "Soft-soled footsteps ||| 软底脚步声", "holder": "xie", "category": "who", "min_trust": 4, "needs": [],
        "text": "Xie counts every footstep on his stairs. At the third watch {beloved} went out by the front door, and a second pair followed: soft-soled, even, never a limp. The cloth shoes the Pavilion's masters wear. ||| 谢三碗数得清店里每一声脚步。三更时分，{beloved}出了前门，随后另有一双脚步跟了出去：软底、匀称、不带一点跛。那是云剑阁师长穿的布鞋。",
    },
    "lu_lead": {
        "title": "Where Lu Chenzhou hides ||| 陆沉舟的藏身处", "holder": "xie", "category": None, "min_trust": 6, "needs": [], "unlocks": "lu",
        "text": "Xie admits that the champion Lu Chenzhou is alive and hiding at the Sword Cliff. Xie lied about being at the inn that night because he was carrying wine up the cliff path to Lu. ||| 谢三碗承认魁首陆沉舟还活着，就藏在剑崖。他那夜谎称没出过客栈，是因为他正提着酒上剑崖去给陆沉舟送去。",
    },
    "layers": {
        "title": "Seven layers, and two more ||| 七层，与另外两层", "holder": "su", "category": "how", "min_trust": 4, "needs": [],
        "text": "Su Wanzhao says Pavilion disciples are taught only seven of the nine layers of the Nine-Cloud Sword. The last two are shown only to the Master of the Pavilion and the reigning champion. ||| 苏晚照说，云剑阁弟子只学九重云剑的前七层。最后两层，只传给阁主和在任魁首。",
    },
    "charm": {
        "title": "The keepsake at the garden gate ||| 园门边的信物", "holder": "su", "category": "where", "min_trust": 5, "needs": [],
        "text": "Su found {beloved}'s keepsake ({token}) on the ground at the Pavilion garden's side gate at dawn. It was nowhere near the Sword Cliff, where the body was said to have been found. ||| 天亮时，苏晚照在云剑阁花园的侧门边捡到{beloved}的信物（{token}）。那里离据说发现尸体的剑崖很远。",
    },
    "burial": {
        "title": "A hurried burial ||| 仓促的下葬", "holder": "su", "category": "why", "min_trust": 4, "needs": [],
        "text": "Su says Master Yun ordered the burial before noon on the day of the discovery, and refused when the healer Bai Suxin asked to examine the body first. ||| 苏晚照说，发现尸体当天，云阁主就下令在中午前下葬，并回绝了医女白素心先验尸的请求。",
    },
    "wound": {
        "title": "The wound ||| 伤口", "holder": "bai", "category": "how", "min_trust": 5, "needs": [],
        "text": "Bai Suxin glimpsed the body for the time it takes to count ten before the Pavilion men covered it: one narrow thrust, with nine thin scores fanned around it like cloud. Not a fall. ||| 白素心在云剑阁的人盖上布之前，只看了尸体数到十的工夫：一道窄窄的刺伤，周围散开九道细痕，像云。不是摔死的。",
    },
    "herb": {
        "title": "Silver-vein dewgrass ||| 银脉露草", "holder": "bai", "category": "why", "min_trust": 6, "needs": [],
        "text": "Bai says silver-vein dewgrass numbs the hand and smells sweet when burned. It grows only in the Cloud Sword Pavilion's own garden. Someone has used it to ruin a swordsman's grip (she will not say whose). ||| 白素心说，银脉露草能麻痹手筋，烧起来有甜味，只长在云剑阁自家的花园里。有人用它废了某位剑客的握力（她不肯说是谁）。",
    },
    "lantern": {
        "title": "The covered lantern ||| 蒙布的灯笼", "holder": "leng", "category": "who", "min_trust": 5, "needs": [],
        "text": "Leng Qianshan, watching the Pavilion that night, saw a lantern wrapped in cloth slip through the garden's side gate at the third watch, carried by a man in a white robe with an azure sash. ||| 冷千山那夜监视着云剑阁，三更时看见一盏蒙了布的灯笼溜进花园侧门，提灯的是个身穿白袍、系青色腰带的人。",
    },
    "lu_seen": {
        "title": "The ruined man on the cliff ||| 剑崖上的废人", "holder": "leng", "category": None, "min_trust": 4, "needs": [], "unlocks": "lu",
        "text": "Leng tracked the champion to the Sword Cliff, where a ruined man drinks alone every night. He did not touch him: the champion's hand was already useless. ||| 冷千山一路追踪魁首到了剑崖，那里每晚有个废人独自喝酒。他没有动手：魁首的手早已废了。",
    },
    "contract": {
        "title": "The Pavilion silver ||| 云剑阁的银子", "holder": "leng", "category": "why", "min_trust": 7, "needs": [],
        "text": "Leng was hired through a go-between to cripple the champion Lu Chenzhou. The silver was stamped with the Pavilion treasury's mark: someone inside the Pavilion wanted Lu out of the gathering. ||| 冷千山经中间人受雇去废魁首陆沉舟。报酬的银锭上有云剑阁钱库的印记：阁里有人想让陆沉舟无法参加剑会。",
    },
    "hand": {
        "title": "Lu's ruined hand ||| 陆沉舟的废手", "holder": "lu", "category": "clears", "min_trust": 4, "needs": [],
        "text": "Lu Chenzhou's sword hand has been numb for weeks. He cannot close it, let alone thrust. He could not have made the wound. ||| 陆沉舟的剑手已麻木数周，连握拢都不能，更别说刺出那一剑。伤口不可能出自他手。",
    },
    "voice": {
        "title": "The voice at the cliff ||| 剑崖上的声音", "holder": "lu", "category": "who", "min_trust": 6, "needs": ["wound"],
        "text": "From the foot of the cliff, Lu heard something heavy fall with no cry, then a polite, even voice above whisper 'forgive me.' He has known that voice for twenty years: Yun Wuya's. ||| 在崖脚，陆沉舟听见有重物落下，没有一声呼喊，随后崖上有个有礼、平稳的声音低低说了句“请原谅”。这声音他认了二十年：是云无涯的。",
    },
    "slip": {
        "title": "The slip of the tongue ||| 失言", "holder": "yun", "category": "where", "min_trust": 0, "needs": [],
        "text": "Asked where exactly {beloved} was found, Yun Wuya first said they had 'lost their way by the garden wall', then corrected himself to the Sword Cliff path. ||| 被问到{beloved}具体在哪里出事，云无涯先说是“在园墙边迷了路”，随即改口说是剑崖山道。",
    },
}

# The cast. Public fields are shown to the player; the rest is for the AI that plays them.
CAST = [
    {
        "key": "xie", "name": "谢三碗 Xie Sanwan", "alignment": "neutral", "start": "visible",
        "title": "Three-Bowl Innkeeper ||| 三碗掌柜", "sect": "Unaffiliated ||| 无门无派",
        "location": "Halfway Inn ||| 半山客栈",
        "public": "Runs the Halfway Inn, where your beloved stayed. He knows every guest on the mountain. ||| 经营半山客栈，你的爱人曾住在这里。山上每位客人他都认得。",
        "earns": "Likes a good story, a shared bowl of wine and honest guests. ||| 爱听好故事，爱分一碗酒，喜欢诚实的客人。",
        "likes": ["wry", "gentle"], "trust": {"base": 3, "orthodox": 0, "unorthodox": 0, "neutral": 0},
        "art": "Spilled-Wine Palm: a flick of the wrist turns a cup of wine into a blinding spray ||| 泼酒掌：手腕一抖，满杯酒化作迷眼水幕",
        "traits": ["Counts every guest's footsteps ||| 数每位客人的脚步声", "Waters the wine, then confesses it ||| 往酒里兑水，又自己招认", "Always sits facing the door ||| 总坐在正对大门的位置"],
        "speech": "Slow, warm and teasing; answers a question with another question; calls the visitor 'little guest' and ends gossip with 'but you didn't hear it from me'. ||| 说话慢悠悠，热络里带着调侃；爱用问题回答问题，称来客为“小客官”，说完闲话总要补一句“可别说是我讲的”。",
        "greeting": "Sit, little guest, before the wind finishes your tea. The first bowl is on the house; the second costs a story. ||| 坐吧，小客官，别让山风把茶吹凉了。头一碗算我的，第二碗，拿故事来换。",
        "goal": "He wants to be told that your beloved did not suffer, and wants you to leave the Sword Cliff alone. ||| 他想听人说你的爱人没受苦，也希望你别去剑崖。",
        "knowledge": "Knows every traveller on the mountain, the price of everything and who owes whom; has never seen the capital and cannot read a sword manual. ||| 熟知山上每位旅人、各样物价和谁欠谁的账；没去过京城，也看不懂剑谱。",
        "stance": "You say you were at the inn all night and heard nothing unusual, and that the hero's beloved was a quiet, polite guest. ||| 你说那夜自己一直在客栈，没听见异常，说来客的爱人是位安静有礼的客人。",
        "truth": "That night you were not where you say you were: you were doing something loyal for someone you love, and you will protect them until you truly trust the hero. You saw no killing. You liked the hero's beloved, who was kind to you. Every concrete fact you hold is only available through your clue ids.",
        "relations": 'Lu Chenzhou is your sworn brother (you never say where he is). Su Wanzhao is a good girl who works too hard. Master Yun is respected. Bai Suxin buys your herb wine. Leng Qianshan is a frightening guest who pays on time.',
        "topics": {"burning": "what a Pavilion servant told you", "footsteps": "the footsteps on your stairs that night", "lu_lead": "where your sworn brother is"},
        "appearance": dict(build="masculine", age="elder", skin="warm", hair_style="bun", hair_color="silver", eyes="sleepy", eye_color="brown", expression="smile",
                           outfit="hermit", outfit_color="ash", accent_color="gold", headwear="none", mark="beard", weapon="none", aura="none", scene="mountains"),
    },
    {
        "key": "su", "name": "苏晚照 Su Wanzhao", "alignment": "orthodox", "start": "visible",
        "title": "Evening-Glow Sword ||| 晚照剑", "sect": "Cloud Sword Pavilion ||| 云剑阁",
        "location": "Gate of Cloud Sword Pavilion ||| 云剑阁山门",
        "public": "A proud young disciple of Cloud Sword Pavilion. She was first to reach the body. ||| 云剑阁年轻骄傲的弟子，她是最早赶到尸体旁的人之一。",
        "earns": "Respects directness and courage; hates flattery. ||| 欣赏直率和胆气，讨厌奉承。",
        "likes": ["blunt", "proud"], "trust": {"base": 3, "orthodox": 1, "unorthodox": -1, "neutral": 0},
        "art": "Evening Glow Thirteen: thirteen thrusts, each faster than the sunset fades ||| 晚照十三式：十三剑连刺，一剑快过一剑，快过落日",
        "traits": ["Challenges strangers by reflex ||| 见陌生人就想比划", "Polishes her sword when worried ||| 一担心就擦剑", "Refuses to admit she is hungry ||| 饿了也不肯承认"],
        "speech": "Crisp, proud and quick; short sentences; sharp when worried; calls the visitor 'you' until she respects them. ||| 干脆、骄傲、爽利；句子短，一着急就带刺；对来客直呼“你”，直到她认可你为止。",
        "greeting": "State your sect and your sword, or step aside. I have a master to find and no time for strangers. ||| 报上门派和兵器，不然让开。我要去找师父，没空应付陌生人。",
        "goal": "She wants help finding her missing master, Lu Chenzhou, and wants nobody to say the Pavilion is lying. ||| 她想找到失踪的师父陆沉舟，也不许任何人说云剑阁撒谎。",
        "knowledge": "Knows the Pavilion's sword forms and every path on the mountain; knows nothing of herbs, money or what grown-ups mean when they smile. ||| 熟知云剑阁的剑法和山上每一条路；对草药、银钱，以及大人们笑里藏着什么，一无所知。",
        "stance": "You say you were training all night (you were out searching for your master), and that the Pavilion's account is the truth. You do not mention the keepsake you found. ||| 你说那夜你整晚在练剑（其实在外寻找师父），并说云剑阁的说法就是真相。你不提自己捡到的信物。",
        "truth": "At dawn you found something that belonged to the hero's beloved and kept it, afraid it pointed at the Pavilion and at Master Yun, who raised you. You are loyal to him and do not want to believe it. You know your master Lu is hurt but not where he is. Every concrete fact you hold is only available through your clue ids.",
        "relations": "Master Yun raised you and you admire him. Lu Chenzhou is your own master, missing for a month. Xie Sanwan always feeds you. Bai Suxin is the healer, a little strange. Leng Qianshan is a dangerous stranger.",
        "topics": {"layers": "what the Pavilion teaches its disciples", "charm": "what you found at dawn", "burial": "how quickly the burial was done"},
        "appearance": dict(build="feminine", age="young", skin="fair", hair_style="ponytail", hair_color="black", eyes="sharp", eye_color="black", expression="fierce",
                           outfit="fighter", outfit_color="crimson", accent_color="gold", headwear="headband", mark="none", weapon="sword", aura="flame", scene="mountains"),
    },
    {
        "key": "bai", "name": "白素心 Bai Suxin", "alignment": "neutral", "start": "visible",
        "title": "Frost-Moss Healer ||| 采霜医女", "sect": "Unaffiliated ||| 无门无派",
        "location": "Herb Slope ||| 采药坡",
        "public": "A healer who gathers herbs on the mountain and keeps to herself. ||| 在山上采药的医女，独来独往。",
        "earns": "Values honesty and gentleness; will not help anyone who lies to her. ||| 看重诚实与温和，对她撒谎的人她不理。",
        "likes": ["gentle", "cunning"], "trust": {"base": 3, "orthodox": 0, "unorthodox": 0, "neutral": 0},
        "art": "Seven-Needle Calm: seven needles that quiet pain, and sometimes quiet a man entirely ||| 七针定心：七针能止痛，有时也能让人彻底安静",
        "traits": ["Names every plant she steps on ||| 踩到哪棵草都要叫出名字", "Won't treat anyone who lies to her ||| 对她撒谎的人，她不医", "Keeps a spare needle behind each ear ||| 每只耳后各别一根备用针"],
        "speech": "Soft, precise and a little dry; speaks as if writing a prescription; apologises to plants. ||| 轻声、精准、带点冷幽默；说话像在开药方；对草木会说抱歉。",
        "greeting": "Mind where you step: that is frost-moss, and it grows once in ten years. Are you hurt, or only grieving? ||| 小心脚下，那是霜苔，十年才长一回。你是受伤了，还是只是悲痛？",
        "goal": "She wants someone to take the death seriously, but she will not accuse anyone without being sure. ||| 她希望有人认真对待这桩死亡，但没有把握，她不会指认任何人。",
        "knowledge": "Knows herbs, poisons, wounds and the mountain's weather; knows nothing of sword rankings or sect politics. ||| 通晓草药、毒物、伤势和山中天气；对剑法排名和门派政治一概不懂。",
        "stance": "You say you only saw the body briefly and cannot say how the death came about, and that you do not discuss patients. ||| 你说你只匆匆看过尸体，说不清死因，并说你从不谈论病人的事。",
        "truth": "You glimpsed the body briefly and know it was no fall. You also know something about a substance that was used to hurt someone you treated. Your healer's oath forbids you to name any patient, so you may speak of what you saw and know but never of whose body or hand it was. Every concrete fact you hold is only available through your clue ids.",
        "relations": "Master Yun is the Pavilion's master and your neighbour on the slope, always courteous. Su Wanzhao is a stubborn girl. Xie Sanwan sells you wine for liniment. Leng Qianshan came to you with frostbite once. Lu Chenzhou is the champion; you will not say more.",
        "topics": {"wound": "the body you glimpsed", "herb": "a sweet-smelling herb that numbs"},
        "appearance": dict(build="feminine", age="adult", skin="fair", hair_style="braid", hair_color="black", eyes="soft", eye_color="brown", expression="calm",
                           outfit="robe", outfit_color="jade", accent_color="white", headwear="bamboo_hat", mark="none", weapon="none", aura="petals", scene="bamboo"),
    },
    {
        "key": "leng", "name": "冷千山 Leng Qianshan", "alignment": "unorthodox", "start": "visible",
        "title": "Lone Blade of the Frontier ||| 塞北孤刀", "sect": "Unaffiliated (hired blade) ||| 无门无派（受雇刀客）",
        "location": "Old pine path ||| 古松道",
        "public": "A hired blade from the frontier, new on the mountain. Everyone assumes he did it. ||| 刚到山上的塞北雇佣刀客。人人都猜是他干的。",
        "earns": "Respects people who don't threaten him and speak plainly. ||| 尊重不威胁他、说话直白的人。",
        "likes": ["cool", "blunt"], "trust": {"base": 3, "orthodox": -1, "unorthodox": 1, "neutral": 0},
        "art": "Frozen River Cut: one slow draw, one instant stroke, and the water stops flowing ||| 冰河斩：缓缓拔刀，一刀出手，水流顿止",
        "traits": ["Never sits with his back to a wall ||| 从不背靠墙坐", "Eats snow instead of drinking water ||| 不喝水，只吃雪", "Apologises to men he is about to fight ||| 对要交手的人先说抱歉"],
        "speech": "Low, flat and unhurried; few words; no wasted courtesy; dry frontier humour. ||| 低沉、平淡、不慌不忙；惜字如金，不讲虚礼；带着边塞的冷幽默。",
        "greeting": "Stand where I can see your hands. I won't hurt you unless I'm paid to, and nobody has paid yet. ||| 站在我看得见你手的地方。除非有人付钱，否则我不会伤你，而眼下还没人付钱。",
        "goal": "He wants to clear his name so he can go home, and fears being the one who is blamed. ||| 他想洗清自己好回家，也怕自己成了替罪羊。",
        "knowledge": "Knows the frontier, hired killing and cold; knows nothing of the mountain's customs and hears polite phrases as threats. ||| 熟悉边塞、雇佣杀手的行当和严寒；不懂山上的规矩，常把客套话听成威胁。",
        "stance": "You say you were just passing through, minding your own business, and saw nothing. ||| 你说你只是路过，不管闲事，什么也没看见。",
        "truth": 'You were hired through a go-between, by someone with Pavilion money, to cripple the champion Lu Chenzhou, and you did nothing because you found him already ruined. That night you were watching the Pavilion and saw something. You fear being blamed as the stranger with a blade, so you hide all this until you trust the hero. Every concrete fact you hold is only available through your clue ids.',
        "relations": 'Master Yun received you politely. Su Wanzhao glares at you. Xie Sanwan gave you a bowl of wine and you owe him. Bai Suxin treated your frostbite. Lu Chenzhou is the target you did not touch.',
        "topics": {"lantern": "what you saw at the Pavilion garden that night", "lu_seen": "the ruined man you found on the Sword Cliff", "contract": "who hired you"},
        "appearance": dict(build="masculine", age="adult", skin="tan", hair_style="wild", hair_color="black", eyes="sharp", eye_color="black", expression="fierce",
                           outfit="fighter", outfit_color="ink", accent_color="crimson", headwear="none", mark="scar", weapon="saber", aura="ice", scene="snow"),
    },
    {
        "key": "lu", "name": "陆沉舟 Lu Chenzhou", "alignment": "neutral", "start": "hidden",
        "title": "Sunken Boat, Last Champion ||| 沉舟客，上届魁首", "sect": "Cloud Sword Pavilion (absent) ||| 云剑阁（离阁）",
        "location": "Sword Cliff ||| 剑崖",
        "public": "The last champion, unseen for a month. ||| 上届魁首，已一月不见踪影。",
        "earns": "A shared jar of wine, honesty about pain, and no pity. ||| 一同喝酒，坦诚谈痛处，不带怜悯。",
        "likes": ["wry", "proud"], "trust": {"base": 3, "orthodox": 0, "unorthodox": 0, "neutral": 0},
        "art": "Sinking Boat Style: gives ground until the last step, then ends the duel in one cut ||| 沉舟式：步步退让，退到最后一步，一剑定胜负",
        "traits": ["Talks to his empty scabbard ||| 对着空剑鞘说话", "Drinks only with his left hand ||| 只用左手喝酒", "Hums off-key when afraid ||| 害怕时就跑调哼歌"],
        "speech": "Slurred, wry and self-mocking; trails off mid-sentence; flashes of sharp clarity whenever a sword is mentioned. ||| 醉醺醺的，苦笑里带着自嘲；话说一半常断；一提到剑，眼神忽然清亮锋利。",
        "greeting": "If you've come to challenge me, you're a month late. If you've brought wine, sit. ||| 要是来挑战我的，你晚了一个月。要是带了酒，就坐吧。",
        "goal": "He wants to know who ruined his hand, and does not want anyone to see him like this. ||| 他想知道是谁废了他的手，也不愿被人看见自己这副样子。",
        "knowledge": "Knows swordplay and the old duels better than anyone alive; knows nothing of markets, politics or the Pavilion's finances. ||| 论剑术和旧日比武，当世无人比他熟；对集市、朝局和云剑阁的钱粮一无所知。",
        "stance": "You say you were too drunk to see or hear anything that night and wave questions away. ||| 你说那夜醉得什么也没看见没听见，对追问一概摆手。",
        "truth": 'Your sword hand is ruined and you hide it; you plan to lose on purpose at the gathering and vanish. That night, at the foot of the Sword Cliff, you heard something you recognised. You cannot bear to accuse an old friend without proof. Every concrete fact you hold is only available through your clue ids.',
        "relations": "Xie Sanwan is your sworn brother. Su Wanzhao is your disciple, and you cannot face her. Master Yun is your rival of twenty years, and once your friend. Bai Suxin treated your hand. Leng Qianshan: you have heard of a frontier blade on the mountain.",
        "topics": {"hand": "your hand", "voice": "what you heard at the cliff that night"},
        "appearance": dict(build="masculine", age="adult", skin="warm", hair_style="wild", hair_color="black", eyes="sleepy", eye_color="black", expression="weary",
                           outfit="robe", outfit_color="ink", accent_color="crimson", headwear="none", mark="none", weapon="none", aura="moon", scene="mountains"),
    },
    {
        "key": "yun", "name": "云无涯 Yun Wuya", "alignment": "orthodox", "start": "visible",
        "title": "Master of Cloud Sword Pavilion ||| 云剑阁阁主", "sect": "Cloud Sword Pavilion ||| 云剑阁",
        "location": "Cloud Sword Pavilion ||| 云剑阁",
        "public": "Master of Cloud Sword Pavilion, who arranged your beloved's burial. ||| 云剑阁阁主，你爱人的后事由他一手料理。",
        "earns": "Politeness and respect for the Pavilion. ||| 礼数周到，敬重云剑阁。",
        "likes": ["gentle", "proud"], "trust": {"base": 4, "orthodox": 1, "unorthodox": -1, "neutral": 0},
        "art": "Nine-Cloud Sword: nine layered cuts that hide one another like cloud on a peak ||| 九重云剑：九层剑势层层遮掩，如峰顶云海",
        "traits": ["Never raises his voice ||| 从不提高嗓门", "Bows to everyone, even enemies ||| 对谁都行礼，连仇人也不例外", "Has not slept a full night in weeks ||| 几周来没睡过一个整觉"],
        "speech": "Measured, courteous and formal; speaks in classical phrases; every compliment has a hook in it. ||| 沉稳、有礼、拘于规矩；爱用文言；每句夸奖里都藏着一个钩子。",
        "greeting": "A guest on the mountain in the week of the gathering, and in sorrow. Cloud Sword Pavilion grieves with you. ||| 剑会之周有客登山，又带着哀痛。云剑阁与你同悲。",
        "goal": "He wants you to accept the accident, rest as the Pavilion's guest, and leave the matter alone. ||| 他希望你接受这是一场意外，作为云剑阁的客人休息，不再追问。",
        "knowledge": "Knows sword lore, sect etiquette and the history of the gathering; knows little of common people's lives. ||| 精通剑学、门派礼数和剑会的掌故；对百姓生计所知甚少。",
        "stance": "You say it was a tragic accident on a dark path, that you had the burial done quickly to spare the hero further pain, and you invite the hero to rest as the Pavilion's guest. ||| 你说这是黑暗山道上的一场不幸意外，下葬从速是为了免去来客更多痛苦，并邀来客留在云剑阁休息。",
        "truth": "YOU ARE THE KILLER. You had the champion Lu Chenzhou drugged and hired a blade to cripple him, so the Pavilion would not lose the gathering. Your hero's beloved noticed what you were burning that night, and in a panic you killed them with a full thrust of the Nine-Cloud Sword, moved the body to the cliff path and buried it quickly. You are ashamed, exhausted and exquisitely courteous. You will never confess in conversation. You never raise your voice, and you never mention the garden, the herb, the lantern or the wound unless the hero raises them first. If the hero presses with real evidence, you grow quiet, formal and cold, and steer them away from the Pavilion's grounds. Your only clue (slip) is a mistake you cannot help making when asked exactly where the hero's beloved was found.",
        "relations": "Lu Chenzhou is your old rival of twenty years. Su Wanzhao is your protégée. Bai Suxin is a neighbour whose curiosity you fear. Xie Sanwan is a harmless innkeeper. Leng Qianshan is a stranger you paid through another man and would rather not meet.",
        "topics": {"slip": "where exactly the hero's beloved was found"},
        "appearance": dict(build="masculine", age="elder", skin="fair", hair_style="bun", hair_color="white", eyes="sharp", eye_color="black", expression="calm",
                           outfit="scholar", outfit_color="white", accent_color="azure", headwear="crown", mark="beard", weapon="sword", aura="ink", scene="mountains"),
    },
]
BY_KEY = {c["key"]: c for c in CAST}

# What a wrong accusation teaches. It never names the killer; it removes one suspect.
REBUTTALS = {
    "xie": "Xie Sanwan lied about that night, but his lie was about a friend, not a murder. ||| 谢三碗那夜撒了谎，但他护的是一位朋友，而不是一桩凶案。",
    "su": "Su Wanzhao hid the keepsake out of fear, not guilt, and she only knows seven layers of the sword. ||| 苏晚照藏起信物是出于害怕，不是心虚；而且她只学了七层剑法。",
    "bai": "Bai Suxin kept silent because of an oath. A healer who wanted someone dead would not have wanted the wound examined. ||| 白素心沉默是因为誓言。想杀人的医者，不会想让人验伤。",
    "leng": "Leng Qianshan is a hired blade and looks the part, but a saber does not leave a wound like that, and he was no friend of the one who hired him. ||| 冷千山是雇佣刀客，也一副凶相，但刀留不下那样的伤口，而且他对雇主毫无好感。",
    "lu": "Lu Chenzhou was at the cliff, but his hand has not closed in weeks. He could not have made that thrust. ||| 陆沉舟当时在剑崖，但他的手已数周握不拢，刺不出那一剑。",
}

FATES = {
    "justice": {"en": "Hand him to the Gathering's elders", "zh": "交给剑会诸位长老"},
    "mercy": {"en": "Spare his life, strip his name", "zh": "饶他性命，夺其名号"},
    "vengeance": {"en": "Take your revenge yourself", "zh": "亲手报仇"},
}


# ---------- reading the case ----------

def names(name: str) -> tuple[str, str]:
    """'陆沉舟 Lu Chenzhou' -> ('Lu Chenzhou', '陆沉舟')."""
    m = re.match(r"^((?:[一-鿿·]+\s*)+)(.*)$", str(name or "").strip())
    if not m:
        return str(name or "").strip(), str(name or "").strip()
    zh = m.group(1).strip()
    return (m.group(2).strip() or zh), zh


def fill(text: str, ch: dict) -> str:
    """Put the player's beloved and keepsake into a clue's text, in each language."""
    b_en, b_zh = names(ch.get("beloved_name", ""))
    t_en, t_zh = bilingual.split(ch.get("beloved_token", ""))
    en, zh = bilingual.split(text)
    en = en.replace("{beloved}", b_en).replace("{token}", t_en or t_zh)
    zh = zh.replace("{beloved}", b_zh).replace("{token}", t_zh or t_en)
    return f"{en} {bilingual.SEP} {zh}"


def clue_view(cid: str, ch: dict) -> dict:
    c = CLUES[cid]
    return {"id": cid, "title": c["title"], "text": fill(c["text"], ch), "category": c["category"],
            "source": c["holder"], "source_name": BY_KEY[c["holder"]]["name"] if c["holder"] else ""}


def discoverable() -> list[str]:
    return [k for k, c in CLUES.items() if c["holder"]]


def public_card(key: str) -> dict:
    c = BY_KEY[key]
    return {"key": key, "name": c["name"], "title": c["title"], "sect": c["sect"], "location": c["location"],
            "alignment": c["alignment"], "public": c["public"], "earns": c["earns"], "greeting": c["greeting"],
            "appearance": c["appearance"], "clues_total": len(c["topics"])}


def starting_cast() -> list[str]:
    return [c["key"] for c in CAST if c["start"] == "visible"]


def start_trust(key: str, ch: dict) -> tuple[int, str]:
    """How much this person trusts the hero on first meeting, and why ('English ||| 中文')."""
    c = BY_KEY[key]
    t = c["trust"]
    trust = t["base"] + t.get(ch.get("path"), 0)
    if ch.get("temperament") in c["likes"]:
        trust += 1
        why = "Your manner suits them. ||| 你的做派合他的脾气。"
    elif t.get(ch.get("path"), 0) < 0:
        why = "Your path is not theirs, and they are wary. ||| 你们走的路不同，他心存戒备。"
    elif t.get(ch.get("path"), 0) > 0:
        why = "You walk a path they respect. ||| 你走的路，他是敬重的。"
    else:
        why = "A stranger, and a grieving one. ||| 一个陌生人，一个悲痛的人。"
    return max(0, min(10, trust)), why


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


def plain_fact(cid: str, ch: dict) -> str:
    """A clue's text in 'English / 中文' form for a prompt, with the hero's names filled in."""
    return bilingual.plain(fill(CLUES[cid]["text"], ch))


def can_reveal(cid: str, key: str, found: list[str], trust: int) -> tuple[bool, str]:
    c = CLUES.get(cid)
    if not c or cid not in BY_KEY[key]["topics"]:
        return False, "You know nothing about that."
    if cid in found:
        return True, "already told"
    if trust < c["min_trust"]:
        return False, f"You do not trust the hero enough yet (trust {trust}/10). Deflect in character; do not hint at the content."
    missing = [n for n in c["needs"] if n not in found]
    if missing:
        return False, "The hero has not yet found what would make you speak of this. Deflect in character; do not hint at the content."
    return True, "ok"


def judge(suspect: str, evidence: list[str], found: list[str]) -> dict:
    """The verdict on an accusation: wrong person, right person without enough proof, or solved."""
    owned = [e for e in dict.fromkeys(evidence) if e in found and e in CLUES]
    kinds = {CLUES[e]["category"] for e in owned if CLUES[e]["category"]}
    if suspect != CULPRIT:
        return {"verdict": "wrong", "kinds": sorted(kinds), "feedback": REBUTTALS.get(suspect, "That is not the killer. ||| 凶手不是他。")}
    if len(kinds) < PROOF_NEEDED:
        need = PROOF_NEEDED - len(kinds)
        left = [k for k in CATEGORIES if k not in kinds]
        names_en = ", ".join(CATEGORIES[k]["en"].lower() for k in left)
        names_zh = "、".join(CATEGORIES[k]["zh"] for k in left)
        return {"verdict": "unproven", "kinds": sorted(kinds),
                "feedback": f"You have the right name, but nobody will move against the Master of the Pavilion on a hunch. Show proof of {need} more kind{'s' if need > 1 else ''} (still open: {names_en}). {bilingual.SEP} 你说对了人，但没人会凭一个猜测就去动云剑阁的阁主。还需再出示 {need} 类证据（尚缺：{names_zh}）。"}
    return {"verdict": "correct", "kinds": sorted(kinds), "feedback": ""}


TRUTH_FOR_EPILOGUE = (
    "THE TRUTH: Yun Wuya, Master of Cloud Sword Pavilion, had silver-vein dewgrass put in the champion Lu Chenzhou's wine so the "
    "Pavilion would not lose the Sword Gathering, and hired the frontier blade Leng Qianshan with Pavilion silver to cripple Lu. "
    "At the third watch he was burning the leftover herb at the garden wall when the hero's beloved passed, smelled the sweet smoke and "
    "said they would ask the healer Bai about it. In a panic he killed them with a full nine-layer thrust of the Nine-Cloud Sword at the "
    "garden's side gate, carried the body under a covered lantern to the Sword Cliff path and let it fall, whispering 'forgive me', then had "
    "them buried before noon and refused the healer's request to look."
)


TRUTH_BI = (
    "Yun Wuya, Master of Cloud Sword Pavilion, had silver-vein dewgrass put in the champion Lu Chenzhou's wine so the Pavilion would not lose the Sword Gathering, "
    "and paid the frontier blade Leng Qianshan with Pavilion silver to cripple him. At the third watch he was burning the leftover herb at the garden wall when {beloved} "
    "walked by, smelled the sweet smoke and said they would ask the healer Bai about it. In a panic he killed them with a full nine-layer thrust at the garden's side gate, "
    "carried the body under a covered lantern to the Sword Cliff path and let it fall, whispering 'forgive me'. Then he had them buried before noon and refused the healer's request to look. "
    f"{bilingual.SEP} "
    "云剑阁阁主云无涯，为了不让云剑阁在剑会上落败，命人在魁首陆沉舟的酒里下了银脉露草，又用云剑阁的银子雇塞北刀客冷千山去废他的手。"
    "三更时他在花园墙边焚烧剩下的草药，{beloved}恰好路过，闻到甜烟，说明早要去问问医女白素心。他惊慌之下，一记完整的九重云剑刺死了对方，"
    "用蒙布的灯笼把尸体送到剑崖山道，任其坠下，口中低声说着“请原谅”。随后他在中午前将人下葬，并拒绝了医女的验尸请求。"
)

_ENDINGS = {
    "justice": (
        "Yun Wuya does not resist. He bows to you, then to the elders, and says: 'The herb was mine, and so was the sword. {beloved} asked me a kind question and I answered it with a blade.' "
        "The elders strip him of the Pavilion's seal and take him down the mountain in chains. Lu Chenzhou, leaning on Xie Sanwan's arm, watches him go. "
        "The Gathering opens on time, with one empty seat. You leave {token} on {beloved}'s grave, and the mountain, for the first time in three days, is quiet.",
        "云无涯没有反抗。他向你躬身，又向长老们躬身，说道：“药是我的，剑也是我的。{beloved}问了我一句善意的话，我却用剑回答了他。”"
        "长老们收回了云剑阁的印信，将他戴上镣铐押下山去。陆沉舟倚着谢三碗的手臂，目送他远去。剑会如期开幕，只是少了一个座位。"
        "你把{token}放在{beloved}的坟前，三天来第一次，山上安静了。"),
    "mercy": (
        "Yun Wuya kneels in the garden, among the grey ashes of the dewgrass. 'Kill me, or do worse,' he says. You do worse: you ask the elders to strip his name and his sword, and leave him alive to tend {beloved}'s grave until the day he dies. "
        "Lu Chenzhou takes the Pavilion's seat for one season and burns the garden down. Su Wanzhao weeps, then picks up her sword and goes to look for a new master.",
        "云无涯跪在花园里，跪在露草焚烧后的灰烬中。“杀了我，或是更糟的，随你。”你选了更糟的：请长老们夺去他的名号和佩剑，留他一条命，一生守着{beloved}的坟。"
        "陆沉舟暂代云剑阁阁主一季，一把火烧了那座花园。苏晚照哭了一场，然后拾起剑，去找一位新的师父。"),
    "vengeance": (
        "You do not wait for the elders. In the garden, with the sweet smoke of the dewgrass still in the stones, you draw your sword and Yun Wuya draws his. He is the better swordsman, and for nine layers of cloud he proves it. "
        "But he was never a man who could look at {token} without flinching, and on the last layer he flinches. When it is over, the Master of Cloud Sword Pavilion lies still, whispering 'forgive me' to no one. "
        "You have your answer, and nothing else. The mountain wind takes the ashes.",
        "你没有等长老们到来。在花园里，露草的甜烟还留在石缝中，你拔出剑，云无涯也拔出了他的剑。他的剑术更高，九层云剑，层层压来。"
        "但他从来无法直视{token}而不动容，到最后一层，他动容了。一切结束时，云剑阁阁主静静倒下，对着虚空低语“请原谅”。"
        "你得到了答案，也只剩下答案。山风卷走了灰烬。"),
}


def _bond(ch: dict) -> tuple[str, str]:
    en, zh = bilingual.split(ch.get("beloved_bond", ""))
    return en or zh, zh or en


def prologue(ch: dict) -> str:
    """The opening of the story, written in code so it is always the same and always bilingual."""
    b_en, b_zh = _bond(ch)
    en = ("Three days ago, {beloved}, your " + b_en + ", climbed Mount Hua for the Sword Gathering. This morning a messenger from Cloud Sword Pavilion brought a short note: "
          "they fell from the Sword Cliff in the dark, and were buried before noon. You did not weep. You took your sword and climbed the mountain. "
          "Somebody on Mount Hua knows what really happened.")
    zh = ("三天前，你的" + b_zh + "{beloved}上了华山，赶赴剑会。今晨，云剑阁的信使送来一张短笺：他在黑暗中从剑崖失足坠下，中午前已下葬。"
          "你没有哭。你拿起剑，登上了华山。华山上一定有人知道真相。")
    return fill(f"{en} {bilingual.SEP} {zh}", ch)


def truth(ch: dict) -> str:
    return fill(TRUTH_BI, ch)


def fallback_ending(fate: str, ch: dict) -> str:
    en, zh = _ENDINGS.get(fate, _ENDINGS["justice"])
    return fill(f"{en} {bilingual.SEP} {zh}", ch)
