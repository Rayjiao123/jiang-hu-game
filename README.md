# 江湖录 Jianghu Chronicles

A Song-dynasty wuxia murder mystery where every suspect is an AI agent. **剑崖疑案 · The Sword Cliff Murder.**

**The story.** You make a hero (one sentence, or **Roll one**) and the Storyteller agent writes five things that
matter: your **path** (正 orthodox / 邪 unorthodox / 中 neutral), your **manner**, your **signature move**, a **quirk**, and
**the person you love**, who was found dead below the Sword Cliff of Mount Hua three days ago. Before the story
starts you see every trait on a review screen and can change each one by hand. Then you climb the mountain and
question six people: an innkeeper who counts footsteps, a proud young swordswoman, a healer bound by an oath,
a hired blade from the frontier, a champion in hiding, and the Master of Cloud Sword Pavilion. Every one is an AI
with secrets, and every one is told exactly who is in front of them, so your path and manner change the welcome you get.
You earn trust, collect clues in a **case file**, and **name the killer** with proof. The ending is written for
the choice you make about him. Fighting is not in this version.

The AI runs on [DeepSeek](https://api-docs.deepseek.com/) through its OpenAI-compatible API.

## Run it locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env      # then put your key in DEEPSEEK_API_KEY (or set it as an environment variable)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000. Run the tests (no API calls, no cost) with `.\.venv\Scripts\python.exe -m pytest -q`.

## The mystery is written in code, not left to the AI

The whole case lives in `app/case.py`: the truth, the cast, 14 clues (plus the official story), who holds each, and the rules for solving it.
The AI only plays the people.

- **Fixed truth.** The killer, method, motive and clues are data. A wrong accusation gets a rebuttal that never names the killer.
- **Facts are handed out, not remembered.** A character's background carries feelings and loyalties but none of the case facts
  (a test checks this). Each turn the server tells that character only the clues their trust and the clue's prerequisites allow
  (`case.clue_state`), written in the hero's own names. Facts above the trust line are not in the prompt at all, so they can't leak.
- **The server, not the model, files clues.** After each reply a small referee call decides which offered clues the reply actually
  told (`main._credit`) and adds them to the case file. Clues the character was not offered can't be filed, whatever the referee says.
- **Trust moves at most ±2 per reply**, however many times the model asks (`game.npc_tools`).
- **Solving.** Accuse a suspect and lay out clues. Each clue is worth one kind of proof (how, where, who was there, why, who it
  could not be). Naming the killer needs at least **three kinds**; three accusations, then the trail goes cold and the truth is told.
- **Gates between people.** Lu Chenzhou, the champion, is hidden until another character tells you where he is, and his key
  clue needs another clue first.

## How it fits together

```
static/index.html      the screens: landing page, create your hero, map, the mountain, a conversation; case file, accusation, ending
static/style.css       the game interface: lacquer panels and gold frames over painted scenes
static/app.js          the journey: screens, Storyteller chat, trait review and editing, conversations, case file, accusation
static/portrait.js     painted character portraits (soft Jin Yong game-art style), with a cutout mode
static/scenes.js       painted ink-wash backdrops for each of the twelve regions
static/map.js          the ink-wash map of Song China with a seal for each region
static/hero.js         the moonlit painting on the landing page
app/case.py            THE MYSTERY: truth, cast, clues, proof rules, prologue and endings
app/main.py            FastAPI routes; streams replies to the page as server-sent events; the clue referee
app/agent.py           streaming tool-use loop for DeepSeek (OpenAI chat format)
app/game.py            the hero sheet (five traits), editing rules, and the tools each agent may call
app/prompts.py         world bible, era rules, Storyteller and per-person instructions, the ending prompt
app/roll.py            the dice: random role, habit, path, manner and beloved for "Roll one" (English and Chinese)
app/world.py           the twelve regions on the map; only Mount Hua is open
app/bilingual.py       the "English ||| 中文" format, tidying replies, and the fallback translation
app/db.py              SQLite: games (one per visitor) and talks (one per visitor and person)
app/ratelimit.py       per-visitor and daily caps on model calls
```

**Prompt layout for caching.** Each request is `[system: world + era rules + this person + this hero] [history]
[system: trust and the facts they may tell now + reply language] [user message]`. The first part is identical every turn,
so DeepSeek's automatic prefix cache bills it at the cache-hit rate.

**One line in, a whole hero out.** The Storyteller fills every field in a single `set_fields` call, so a visitor never
fills in a form. On the review screen each trait has an edit button: the path and manner are pickers, and text is
written in either language and completed by a translation call (`game.edit_field`). The hero is fixed once the story starts.

**Roll one.** `app/roll.py` rolls a role, a habit, a path, a manner and who the hero loves in code, because a model
asked for "a random character" keeps producing the same one. The Storyteller builds the hero from that seed.

**Portraits in the soft painted style of Jin Yong game art, drawn from the personality.** DeepSeek's API
doesn't generate images, so the Storyteller picks about 17 appearance options (hair, eyes, outfit,
weapon, aura, scene and so on) from fixed lists in `app/game.py`, and `static/portrait.js` draws the
matching layers. Portraits appear instantly, cost nothing, and cannot carry unsafe markup. They are
procedural vector art; for painted-from-scratch art, send the same `appearance` object to an image
model, or have an artist draw the layers.

**Everything is in English and Chinese.** AI text is written `English ||| 中文`. Every sheet field
(except the two names, which are Chinese plus pinyin) must follow that form: `set_fields` refuses a field
written in one language and tells the model what to fix. Replies use the same form, and if the model
forgets or repeats the separator, the server tidies it into one English half and one Chinese half
(`bilingual.normalize`), strips any stray tag markup, and translates a missing half. The visitor's own
lines are translated by the server and stored in both languages. Fixed messages are written in both languages in the code.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | whether the AI is configured |
| GET | `/api/world` | the twelve regions and their map positions |
| GET | `/api/case` | the people on the mountain (public cards only), proof rules and endings |
| GET | `/api/game` | the visitor's case: hero, clues found, accusations left, who they can question |
| POST | `/api/game/new` · `/api/game/reset` | start a hero · drop the case and start over |
| POST | `/api/game/chat` · `/api/game/roll` | talk to the Storyteller · roll a random hero (stream) |
| POST | `/api/game/edit` | change one trait by hand |
| POST | `/api/game/start` | confirm the hero and begin the story |
| POST | `/api/talks` | start (or resume) questioning someone |
| POST | `/api/talks/{id}/open` · `/chat` | they speak first · say something (stream; includes `clue` events) |
| POST | `/api/accuse` | name a suspect and the clues you offer as proof |
| POST | `/api/ending` | choose what to do with the killer; returns the written final scene |

Visitors are identified by an anonymous `vid` cookie, which owns their case and conversations. Nothing is shared between visitors.

## Opening more places later

Only Mount Hua is open (`OPEN_REGIONS`, default `huashan`); the other places show on the map as padlocked.
A later chapter would add a second case file next to `app/case.py` and open its region.

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
A database made by the earlier shared-world version still works: its old tables are simply unused.

## Next steps

1. Playtest the case with real people and adjust clue trust levels and how freely each person talks
2. Fighting, designed separately
3. More cases and places, one region at a time
4. Longer conversation memory: summarise old turns instead of dropping them
5. Real painted art: an image model, or layered parts drawn by an artist, behind `portrait.js`
