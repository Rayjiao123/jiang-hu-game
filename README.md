# 人在江湖，身不由己

**人在江湖，身不由己.** A dark Song-dynasty wuxia story game where every character is an AI and a game master runs the night.

**黑沙客栈 · The Black Sand Inn.** Qinghe, a courier's daughter of seventeen, is carrying her dead father's last job: a sealed letter
sewn into her saddle. A sandstorm drives her into a desert inn that is a slaughterhouse, like *New Dragon Gate Inn* with the lights off.
The keeper drugs, robs and kills the caravans that shelter there, and tonight every guest is meant to die at the third watch. Everyone
in the hall is trapped by something too, and nobody is clean: the keeper by a hostage brother, the camel-keeper by a granddaughter, the
door guard by unpaid silver and a dozen throats, a sick scholar by his duty as a court inspector, a merchant by the people he sold.

**Two ways out, and only two.** The secret **tunnel** (she must learn where it is and how to open it) or **killing the keeper and taking
the key** (she must learn where the key is and drug the keeper first). Pressing the "move" button without what a way out needs kills her.

**She can die.** Show the letter or reveal her plan to the keeper, the door guard or the merchant, threaten the keeper or the guard, push
one of the killers to zero trust, make a wrong move, or let dawn come, and it is a game-over screen where Ray tells her what happened,
the whole story of the inn, and what she could have done. There are three endings: dead, out through the tunnel, or the keeper's key.
The ending screen tracks which ones this browser has found.

**Phone first.** The landing page is one screen: the name, the setting, Qinghe and her goal, Ray, and an enter button. The inn is a
list of six people with a status line each (not spoken to / learned 2 of 3). A conversation is a chat thread: every reply stays on the
page, trust changes show as tags, and each clue Ray files appears in the thread as a green card. There is no separate clue screen:
"问 Ray" opens a sheet with Ray's notes (everything she has learned, and how close each way out is) above the chat with him.

**Ray is the game master.** Ray (the author) narrates in the voice of a teahouse storyteller, has a portrait, opens the story, fires the
events of the night (a scream upstairs, the lamps snuffed, camel bells on the pass), and can be asked anything at any time: what's going
on, who someone is, or for a nudge. He only knows what Qinghe has learned, so he can't spoil the story. Like a tabletop DM, he will also
run combat in a later chapter: the player says what she does, he decides what happens. Fighting is not in this version.

The AI runs on [DeepSeek](https://api-docs.deepseek.com/) through its OpenAI-compatible API.

## Run it locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env      # then put your key in DEEPSEEK_API_KEY (or set it as an environment variable)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000. Run the tests (no API calls, no cost) with `.\.venv\Scripts\python.exe -m pytest -q`.

## The story is written in code, not left to the AI

The whole plot lives in `app/case.py`: the truth, six people, 14 clues, who holds each, the clock, the events, the two ways out, the
rules for dying, and the endings. The AI only plays the people and Ray.

- **Facts are handed out, not remembered.** A person's background holds feelings, loyalties and a public face but none of the plot facts
  (a test checks this). Each turn the server tells that person only the clues their trust and the clue's prerequisites allow
  (`case.clue_state`). Facts above the trust line are not in the prompt at all, so they can't leak.
- **The server files clues, not the model.** After each reply a small referee call decides which offered clues the reply actually told
  (`main._credit`) and adds them to the clue list. Clues that were not offered can't be filed.
- **The server reads her words, not the roleplaying model.** Before anyone answers, one plain check (`main._watch`) reads Qinghe's own
  message and says two things: did she do something fatal (showing the letter, revealing a plan, threatening; a regex also catches open
  threats), and how did it land with this person (-2 to +2 trust, judged against what that person values). The trust change applies
  before they answer, so it shows in the reply, in the chat as a "信任 +1" tag, and in what they will tell her. Reaching
  zero trust with a killer is fatal too. The model that plays the person is then told to act at once, and the reply shows it. A wrong
  `move` is fatal because `case.can_move` checks the clues she actually holds.
- **Trust moves at most ±2 per reply**, counting the server's judgement and anything the model's own `adjust_trust` tool adds (`game.npc_tools`).
- **The clock is the deadline.** Every seventh thing Qinghe says, an hour of the night passes (`MSGS_PER_BEAT`), and Ray announces the
  night's events. At dawn she dies. Asking Ray costs no time.
- **Ray's telling.** A death is explained from written text (`case.death_text`: how, the truth of the inn, what she missed). A win is
  told by the AI from the truth and what she learned, with written endings as the fallback.
- **Gates between people.** Some clues need another clue first (the hatch needs Old Tuo's debt; the key needs the stair guard's rota).

## How it fits together

```
static/index.html      the screens: a one-screen landing page, the inn (a list of people), a chat; Ray's sheet, the move, the ending
static/style.css       the game interface: lacquer panels and gold frames over painted scenes
static/app.js          the journey: screens, clock, the chat thread, Ray's notes and questions, the move, the ending
static/portrait.js     painted character portraits (soft Jin Yong game-art style), with a cutout mode
static/scenes.js       painted backdrops, including the desert inn at dusk
app/case.py            THE STORY: truth, cast, clues, clock, events, escape rules, prologue and endings
app/main.py            FastAPI routes; streams replies as server-sent events; the clue referee; the clock; Ray
app/agent.py           streaming tool-use loop for DeepSeek (OpenAI chat format)
app/game.py            appearance options, first impressions, what people can see of Qinghe, and the tools they may call (including hero_did)
app/prompts.py         world bible, era rules, per-person instructions, Ray's instructions, the ending prompt
app/bilingual.py       the "English ||| 中文" format, tidying replies, and the fallback translation
app/db.py              SQLite: plays (one per visitor) and talks (one per visitor and person)
app/ratelimit.py       per-visitor and daily caps on model calls
```

**Prompt layout for caching.** Each request is `[system: world + era rules + this person + Qinghe] [history]
[system: time, trust and the facts they may tell now + reply language] [user message]`. The first part is identical every turn,
so DeepSeek's automatic prefix cache bills it at the cache-hit rate.

**Portraits in the soft painted style of Jin Yong game art.** DeepSeek's API doesn't generate images, so each character is a set of
about 17 appearance options (hair, eyes, outfit, weapon, aura and so on) from fixed lists in `app/game.py`, and `static/portrait.js`
draws the matching layers. Portraits appear instantly and cost nothing. Ray's look in `case.GM` is a guess; change its appearance dict
to match. They are procedural vector art; for painted-from-scratch art, send the same `appearance` object to an image model, or have an
artist draw the layers.

**Everything is in English and Chinese.** AI text is written `English ||| 中文`. Replies use that form, and if the model forgets or
repeats the separator, the server tidies it into one English half and one Chinese half (`bilingual.normalize`: it also cuts a language
that leaks into the other half and strips stray tag markup), and translates a missing half. The visitor's own lines are translated
by the server and stored in both languages. Fixed messages are written in both languages in the code.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | whether the AI is configured |
| GET | `/api/case` | the people in the inn (public cards only), Qinghe, Ray, the opening and the endings |
| GET | `/api/game` | the visitor's night: clues found, the clock, events, who they can talk to |
| POST | `/api/game/start` · `/api/game/reset` | begin the night · drop it and start over |
| POST | `/api/talks` | start (or resume) talking to someone |
| POST | `/api/talks/{id}/open` · `/chat` | they speak first · Qinghe says something (stream; includes `clue`, `gm`, `clock` and `death` events) |
| POST | `/api/gm/chat` | ask Ray something (stream; costs no time) |
| POST | `/api/move` | try one of the two ways out (`tunnel` or `kill`); fatal if the clues she holds don't open it |
| POST | `/api/ending` | after a successful move: Ray's telling of the whole story and what became of everyone |

Visitors are identified by an anonymous `vid` cookie, which owns their night and conversations. Nothing is shared between visitors.

## Deploying to Railway

The repo includes a `Dockerfile` and `railway.json`, so Railway builds it without extra settings.

1. Push this repository to GitHub.
2. In Railway: **New Project → Deploy from GitHub repo**, and pick it.
3. **Add a volume** to the service, mounted at `/data`. The SQLite database lives there
   (`DATABASE_PATH=/data/jianghu.db` is already set in the Dockerfile). Without a volume, every
   deploy wipes the players' progress.
4. **Variables:** `DEEPSEEK_API_KEY`.
5. **Settings → Networking → Generate Domain** for a free `*.up.railway.app` address, or add your
   own domain there and create the DNS record it shows.
6. Keep the service at **one replica**: the rate limiter lives in memory.

Each push to GitHub redeploys. The same `Dockerfile` runs on Fly.io, Render or any server with
Docker. DeepSeek bills from a prepaid balance, so a small top-up doubles as a hard spending cap.
A database made by an earlier version still works: its old tables are simply unused.

## Next steps

1. Playtest with real people and tune trust levels, how many exchanges make an hour, and how freely each person talks
2. Combat, run by Ray like a tabletop game master (dice, the player's declared actions, Ray's rulings): the fight with the keeper is the obvious first one
3. More chapters and places: the second night, the road, the capital
4. Longer conversation memory: summarise old turns instead of dropping them
5. Real painted art: an image model, or layered parts drawn by an artist, behind `portrait.js`
