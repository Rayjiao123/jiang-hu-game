# 人在江湖，身不由己

**人在江湖，身不由己.** A Song-dynasty wuxia story game where every character is an AI and a game master runs the night.

**黑沙客栈 · The Black Sand Inn.** Qinghe, a courier's daughter of seventeen, is carrying her dead father's last job: a sealed letter
sewn into her saddle. A sandstorm drives her into a desert inn that is not what it seems, like *New Dragon Gate Inn*. The keeper smiles,
the door is barred, and every person in the hall is trapped by something too: the keeper by a hostage brother, the camel-keeper by a
granddaughter, the door guard by unpaid silver and shame, a sick scholar by his duty as a court inspector, a merchant by his caravan.
You play Qinghe: talk to them, learn what each one needs, earn their trust, and find a **way out** and a **way past the guards** before dawn.

**Ray is the game master.** Ray (the author) narrates in the voice of a teahouse storyteller, has a portrait, opens the story, fires the events
of the night (a scream upstairs, the door barred, camel bells on the pass), and can be asked anything at any time: what's going on, who
someone is, or for a nudge. He only knows what Qinghe has learned, so he can't spoil the story. Like a tabletop DM, he will also run
combat in a later chapter: the player says what she does, he decides what happens. Fighting is not in this version.

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

The whole plot lives in `app/case.py`: the truth, six people, 14 clues, who holds each, the clock, the events, and the rules for escaping.
The AI only plays the people and Ray.

- **Facts are handed out, not remembered.** A person's background holds feelings, loyalties and a public face but none of the plot facts
  (a test checks this). Each turn the server tells that person only the clues their trust and the clue's prerequisites allow
  (`case.clue_state`). Facts above the trust line are not in the prompt at all, so they can't leak.
- **The server files clues, not the model.** After each reply a small referee call decides which offered clues the reply actually told
  (`main._credit`) and adds them to the clue list. Clues that were not offered can't be filed.
- **Trust moves at most ±2 per reply**, however many times the model asks (`game.npc_tools`).
- **The clock is the deadline.** Every seventh thing Qinghe says, an hour of the night passes (`MSGS_PER_BEAT`), and Ray announces the
  night's events. At dawn the story is lost and the truth is told. Asking Ray costs no time.
- **The move.** To escape she must hold a **way out** (route) and a **way past the guards** (cover). Knowing who is who (truth) and
  holding something over the keeper (leverage) improve the ending. A plan that fails costs two hours. Then she chooses what to do with
  the letter (deliver it, burn it, or trade it), and Ray tells the ending for the way she prepared. If the AI is unavailable, written
  endings are used.
- **Gates between people.** Some clues need another clue first (the ledger needs the envoy; the keeper's brother needs the ledger).

## How it fits together

```
static/index.html      the screens: landing page, the inn, a conversation; clues, Ray's drawer, the move, the ending
static/style.css       the game interface: lacquer panels and gold frames over painted scenes
static/app.js          the journey: screens, clock, conversations, clues, Ray, the move, the ending
static/portrait.js     painted character portraits (soft Jin Yong game-art style), with a cutout mode
static/scenes.js       painted backdrops, including the desert inn at dusk
app/case.py            THE STORY: truth, cast, clues, clock, events, escape rules, prologue and endings
app/main.py            FastAPI routes; streams replies as server-sent events; the clue referee; the clock; Ray
app/agent.py           streaming tool-use loop for DeepSeek (OpenAI chat format)
app/game.py            appearance options, first impressions, what people can see of Qinghe, and the tools they may call
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
| POST | `/api/talks/{id}/open` · `/chat` | they speak first · Qinghe says something (stream; includes `clue`, `gm` and `clock` events) |
| POST | `/api/gm/chat` | ask Ray something (stream; costs no time) |
| POST | `/api/move` | try the escape with the chosen clues |
| POST | `/api/ending` | choose what to do with the letter; returns the written final scene |

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
2. Combat, run by Ray like a tabletop game master (dice, the player's declared actions, Ray's rulings)
3. More chapters and places: the second night, the road, the capital
4. Longer conversation memory: summarise old turns instead of dropping them
5. Real painted art: an image model, or layered parts drawn by an artist, behind `portrait.js`
