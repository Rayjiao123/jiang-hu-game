# 人在江湖，身不由己

**Helpless in the Jianghu.** A dark Song-dynasty wuxia survival game, about five minutes long, in English, 中文 and ไทย. Every person in it is an
AI (DeepSeek) and a game master, Ray, runs the night like a tabletop DM. The dice are not AI: they are code you can test.

**The setting.** 黑沙客栈, the Black Sand Inn, on the desert road around the year 1200. A sandstorm has closed the pass. You are **Yan Qi, a thief**
hiding in the hall with the magistrate's stolen jade seal under your shirt. All night, more people push through the door out of the storm,
and every one of them wants something from you:

| Who | Mood | What they do |
|---|---|---|
| Outlaws (Madam Shuang, Black Wolf) | friendly, but bad | on your side; bargain, share secrets once they trust you |
| Righteous fighters (Yue Qinghan, Monk Wuhui, Old Qin) | aggressive, but good | want to punish a thief; attack when their patience runs out unless you talk them down |
| The law (Captain Gu, Deputy Fang) | hunting you | want the seal and you in chains; arrest = a fight you must win |

**The goal.** Stay alive until the storm passes (16 beats; every message and every second round of a fight is one beat), then walk out the door.
Walk out early and the desert kills you. Lose a fight and you are dead (or taken to be hanged). Most players die: that is the design.

**Your thief is rolled, not chosen.** The home page rolls three stats that always total 30 (6 to 16 each) and two martial arts:
- **Strength** sets hit points (10 + 2 x Strength, so about 30 on average).
- **Intelligence** makes your martial arts' effects stronger and sets your Qi: how much you start with (1 + Intelligence / 4, up to 5) and how fast Guard recovers it (2 above Intelligence 10).
- **Agility** sets defence (+1 to every defence roll per 3 points).
- One of four **attack arts** (Sand-Skimming Blade, Mountain-Splitting Palm, Rain of Needles, Shadow-Step Strike) and one of four **defence arts**
  (Iron Cloth, Drifting Willow Step, Yielding Palm, Stone Breath), each with its own trick.

**Fighting is a decision each round, not a dice contest.** The enemy shows what it is about to do (a heavy blow, a quick strike, or turtling up) and you choose:
**Strike** (plain), **Art** (your attack art: costs 1 Qi, easier to land, hits harder), **Guard** (+3 defence and one Qi back) or **Counter**
(huge against a heavy blow: the blow is turned back on them; against anything else it leaves you open). Dice still decide hits (two dice each way, ties to the attacker,
damage from the dice) but they are a small line under each result. `app/rules.py` is the whole rulebook; the AI decides nothing in a fight.

**Every talk is a negotiation with a goal.** Each person has a stated goal (win Shuang's trust, convince the monk you can change, make Captain Gu doubt you have the
seal), a trust target shown on a meter, and a limited number of exchanges. Reach the target and you get what they know (a shortcut, a medicine, or a weakness to exploit)
and they stand down. Run out of exchanges, or fall to zero trust, or ignore the righteous and the law too long, and **they strike first** in a fight you start at a disadvantage.
You can also pick a fight yourself, and beating someone takes what they know by force. The server decides when trust is enough, never the model.

**Phone first.** Home page: the scene, the goal, your rolled thief (roll again as often as you like), Ray, and a sticky Enter button. In the inn:
your hit points, the storm clock, a short feed, and a card per person with a Talk and a Fight button. A fight shows the dice rolling.

## Run it locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env      # then put your key in DEEPSEEK_API_KEY (or set it as an environment variable)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000. Run the tests (no API calls, no cost) with `.\.venv\Scripts\python.exe -m pytest -q`.

## The game is code, the AI plays the people

- **The dice** (`app/rules.py`): stats, hit points, the two-dice rounds, and each martial art. Server-side, tested, never the model.
- **The story** (`app/story.py`): the cast with their stats, arrival beats, patience, what they give, the endings. All fixed text in three languages.
- **The server decides, the model proposes.** Before any person answers, one plain check (`main._watch`) reads the player's own message: is it a threat
  (a threat to the righteous or the law starts a fight) and how does it land (trust -2 to +2, judged against what that person values; insults are not threats).
  Trust, standing down, rewards, arrivals, patience and fights are all computed in `app/main.py`. A person is only told their reward in the
  turn the server unlocks it, so it cannot leak earlier (a test checks it).
- **Ray** is told the state of the night in plain English (never a reward nobody has earned yet), can explain the rules and give hints, and costs no time.
  After the last move he tells the ending from a log of what really happened that night, with written endings as the fallback.
- **Balance** (`python -m evals.balance`): simulates thousands of nights with the real dice and reports how often a sensible player lives.
  Currently about 0 percent for a player who never talks anyone down, and about 12 percent for one who talks well in the model, so most runs end in death.

## How it fits together

```
static/index.html      home (scene, goal, roll your thief, Ray), the inn, a chat, a fight; Ray's sheet, the ending
static/style.css       the interface (mobile first)
static/app.js          the journey: screens, rolling, the feed, the chat, the dice animation, Ray, the ending
static/portrait.js     painted character portraits (procedural), with a head-and-shoulders face crop for round avatars
static/scenes.js       painted backdrops (the inn)
app/rules.py           THE DICE: stats, hit points, two-dice rounds, the martial arts
app/story.py           THE STORY: cast, arrivals, rewards, endings, texts in 3 languages
app/main.py            FastAPI routes: the state of the night, talking, fighting, leaving, Ray, the admin
app/agent.py           streaming loop for DeepSeek (OpenAI chat format)
app/prompts.py         world, per-person instructions by mood, Ray's instructions, the ending prompt
app/game_look.py       portrait options and how to describe a look in words
app/i18n.py            the three languages: picking one per request, cleaning the model's text, checking its language
static/i18n.js         the page's own text in English, Chinese and Thai
app/db.py              SQLite: plays (one per visitor, with the state of the night) and talks (one per visitor and person)
app/ratelimit.py       per-visitor and daily caps on model calls
app/stats.py           the admin's numbers, built from the events table
evals/run.py           live evaluation of the characters, per language
evals/balance.py       offline balance simulation of the dice
```

**Three languages, one at a time.** The player picks English, 中文 or ไทย on the home page; the page shows only that language. Fixed text is written once
as `English ||| 中文 ||| ไทย` and the server sends the right part (`X-Lang` header). The AI is told to reply in one language (no translation calls), and
every prompt carries the names in all three spellings.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` · `/api/case` | AI configured · the setting, goal, cast cards, arts, endings |
| GET | `/api/game` | the visitor's night (hero, who is here, the fight, the feed, the clock) |
| POST | `/api/roll` | roll a thief (stats totalling 30, two arts); repeatable until the night starts |
| POST | `/api/game/start` · `/api/game/reset` | begin the night with the rolled thief · drop it |
| POST | `/api/talks` · `/api/talks/{id}/open` · `/chat` | start talking · they speak first · she speaks (stream) |
| POST | `/api/fight/start` · `/api/fight/round` | pick a fight · one round: `attack` or `guard`, two dice each way |
| POST | `/api/leave` | walk out: wins after the storm passes, deadly before |
| POST | `/api/ending` | Ray's telling of how the night ended |
| POST | `/api/gm/chat` | ask Ray (stream; costs no time) |
| POST | `/api/feedback` | a thumb on one of a character's replies |
| GET | `/api/admin/stats` · `/api/admin/transcripts` | visitor numbers and conversations (needs `ADMIN_PASSWORD`) |

Visitors are an anonymous `vid` cookie, which owns their night and conversations.

## Knowing your visitors

Set `ADMIN_PASSWORD` and open `/admin.html`: visitors, a funnel (opened, rolled, started, talked, fought, ended), win rate, endings and what killed players,
the builds that were rolled, per-person numbers (talks, messages, rounds fought, trust change, kills), AI errors, and the conversations. `events` stores counts
only, never message text; conversations are kept in `talk_archive` after a night ends so replies can be reviewed. Every reply has 👍 / 👎.
`CALLS_PER_VISITOR_PER_10_MIN` (150) and `DAILY_CALL_CAP` (8000) cap model calls; one talk message costs two calls and a night is a few dozen.

**Where visitors are.** The country comes from the IP address, looked up on the server in a bundled free file (DB-IP "IP to Country Lite", CC BY 4.0, <https://db-ip.com>),
so no address is sent to another service and only the two-letter country is stored, never the IP. The admin also shows the device (phone, tablet, desktop) and the site
each visitor came from.

## Evaluating

1. **`pytest` (offline, free)**: the dice (stats total 30, damage is the dice, every martial art, ties), the story rules (arrivals, patience, standing down, rewards,
   threats, picking a fight, death by the blade or by arrest, leaving early vs after the storm), Ray not knowing unearned rewards, three-language output, the admin.
2. **`python -m evals.run [--lang en|zh|th|all] [--judge]` (live model)**: every reply in the chosen language, no markup or fourth wall, rewards stay locked on a polite
   first question, insults are never threats, threats are caught, kindness raises trust, the ending is in the right language. Report in `evals/last_report.json`.
3. **`python -m evals.balance`**: how hard the dice make it.

## Deploying to Railway

The repo includes a `Dockerfile` and `railway.json`. Push to GitHub, **New Project → Deploy from GitHub repo**, add a **volume mounted at `/data`** (the SQLite database
lives there), set `DEEPSEEK_API_KEY` and a long random `ADMIN_PASSWORD`, generate a domain, and keep **one replica** (the rate limiter is in memory).
A database made by an earlier version still works: old tables are simply unused.

## Next steps

1. Playtest and tune: arrival beats, patience, how many people the player can realistically calm, hit points
2. More arrivals and rewards (a second wave, a boss), and consumables
3. Grow the eval set from 👎 replies; move the rate limiter to Redis for more than one replica
4. Real painted art behind `portrait.js`
