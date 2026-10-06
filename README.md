# 江湖录 Jianghu Chronicles

A website for a Song-dynasty wuxia game where every NPC is an AI agent created by a visitor.

**The journey.** A visitor arrives at a landing page that shows what the game is (the cast, how it plays, the map),
makes their own character (one line, or **Roll one**:
the Storyteller agent writes the name, quirks, secret, signature move and a painted portrait), and
steps into the jianghu. They walk an ink-wash map of Song China, visit a place, and talk to the people
standing there **as their own character**. **Only Mount Hua is open for now**: it has six hand-written
residents (`app/seed.py`) and a story (the Summit Sword Gathering opens in seven days and the champion has
vanished), and everything else on the map shows as "opens later". Every NPC is told exactly who is in front of them (name,
epithet, sect, alignment, look, habits, ties), so it greets and treats each character differently.
Each character is also released into the world as an NPC for the next visitor to meet.

The AI runs on [DeepSeek](https://api-docs.deepseek.com/) through its OpenAI-compatible API.

## Run it locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env      # then put your key in DEEPSEEK_API_KEY (or set it as an environment variable)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000. Run the tests (no API calls, no cost) with `.\.venv\Scripts\python.exe -m pytest -q`.

## How it fits together

```
static/index.html      the screens: landing page, create your character, map, a place, a conversation
static/style.css       the game interface: lacquer panels and gold frames over painted scenes
static/app.js          the journey: screens, Storyteller chat, map, places, conversations
static/portrait.js     painted character portraits (soft Jin Yong game-art style), with a cutout mode
static/scenes.js       painted ink-wash backdrops for each of the twelve regions
static/map.js          the ink-wash map of Song China with a seal for each region
static/hero.js         the moonlit painting on the gate
static/admin.html      password-protected review page: approve, hide, delete, add citizens, back up
app/main.py            FastAPI routes; streams replies to the page as server-sent events
app/agent.py           streaming tool-use loop for DeepSeek (OpenAI chat format)
app/game.py            game rules, first impressions, and the tools each agent may call
app/world.py           the twelve regions, which are open, and what is happening in each place
app/seed.py            the hand-written residents of Mount Hua, added or refreshed on start-up
app/prompts.py         world bible, era rules, Storyteller and NPC instructions
app/roll.py            the dice: random role, place, twist and look for "Roll one" (English and Chinese)
app/bilingual.py       the "English ||| 中文" format, tidying replies, and the fallback translation
app/moderation.py      automatic content check before a character goes public
app/db.py              SQLite: npcs, npc_secrets, drafts, players, sessions
app/ratelimit.py       per-visitor and daily caps on model calls
```

**The model proposes, the server decides.** Agents change the game only through tools that run
on the server: `set_fields`, `list_jianghu` and `link_npc` for the Storyteller; `adjust_trust`,
`reveal_secret`, `recall_person` and `out_of_world` for NPCs. Trust is clamped to ±2 per call, and
a secret is stored in its own table and only given to the model after the server checks
`trust >= 7`. A player cannot talk their way into it.

**Prompt layout for caching.** Each request is `[system: world + era rules + character] [history]
[system: current state + reply language] [user message]`. The first part is identical every turn,
so DeepSeek's automatic prefix cache bills it at the cache-hit rate.

**One line in, a whole character out.** The Storyteller fills every field in a single `set_fields`
call, so a visitor never fills in a form. Later requests ("make her hair red") send only what changes.
The scroll shows eight things (name, epithet, origin, signature move, three quirks, first words, what
they want, secret). How they speak, what they know and don't, and their look work behind the scenes.

**Every conversation is about this hero.** `POST /api/sessions` pairs the visitor's character with an NPC.
The NPC's instructions include a block describing the hero (never their secret). The server also works
out a first impression (`game.starting_trust`): the same path is warmer, opposed paths colder, a shared
bond softer. The NPC speaks first, to this particular hero (`/open`), and conversations are kept per
pair of characters, so coming back later continues where you left off, with trust intact.

**Roll one.** `app/roll.py` rolls a role, a place, a twist and four visual cues in code, because a model
asked for "a random character" keeps producing the same one. The Storyteller builds the character from
that seed. Each place belongs to a region, so a rolled character starts somewhere sensible on the map.

**Portraits in the soft painted style of Jin Yong game art, drawn from the personality.** DeepSeek's API
doesn't generate images, so the Storyteller picks about 17 appearance options (hair, eyes, outfit,
weapon, aura, scene and so on) from fixed lists in `app/game.py`, and `static/portrait.js` draws the
matching layers: sculpted faces with gradient shading, long almond eyes, flowing hair, layered hanfu,
and a misty ink-wash backdrop. With `{bg: false}` it draws just the figure on a transparent ground, which
is how characters stand over a scene. Portraits appear instantly, cost nothing, and cannot carry unsafe
markup. They are procedural vector art; for painted-from-scratch art, send the same `appearance` object
to an image model, or have an artist draw the layers.

**Everything is in English and Chinese.** AI text is written `English ||| 中文`. Every scroll field
(except the name, which is Chinese plus pinyin) must follow that form: `set_fields` refuses a field
written in one language and tells the model what to fix. Replies use the same form, and if the model
forgets or repeats the separator, the server tidies it into one English half and one Chinese half
(`bilingual.normalize`), and translates a missing half. The visitor's own lines are translated by the
server and stored in both languages. Fixed messages and errors are written in both languages in the
code. The admin page is English only.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | whether the AI is configured |
| GET | `/api/world` | the twelve regions and their map positions |
| GET | `/api/npcs` | public character cards (never secrets), each with its region |
| GET | `/api/me` | the visitor's own character, with the parts only they may see |
| POST | `/api/me/reset` | stop playing as this character and make a new one |
| POST | `/api/drafts` | start a new character |
| POST | `/api/drafts/{id}/chat` | talk to the Storyteller (stream) |
| POST | `/api/drafts/{id}/roll` | roll a random character (stream) |
| POST | `/api/drafts/{id}/release` | check the character, publish it, and play as it |
| POST | `/api/sessions` | start (or resume) talking to an NPC as your character |
| POST | `/api/sessions/{id}/open` | the NPC speaks first, to your character (stream) |
| POST | `/api/sessions/{id}/chat` | say something to the NPC (stream) |

Visitors are identified by an anonymous `vid` cookie, which owns their drafts and conversations.

## Opening more places

Everything on the map exists, but only the regions listed in `OPEN_REGIONS` (default `huashan`) can be entered.
The Storyteller may only place new characters in open regions, `/api/npcs` only returns people in open
regions, and a conversation with someone in a closed region is refused. To open a place:

1. Write its residents in `app/seed.py` (copy the Mount Hua entries: a goal, a secret, a way of speaking,
   ties to each other) and give the place a rumour in `world.SITUATION`.
2. Add a few places in that region to `PLACES` in `app/roll.py` so rolled characters can live there.
3. Set `OPEN_REGIONS=huashan,shaolin` (comma-separated) and restart.

The residents are matched by `seed_key`, so editing them in `seed.py` updates a running world without
duplicating anyone. `SEED_WORLD=0` turns the start-up seeding off.

## Moderation and admin

Releasing an NPC runs an automatic check (`app/moderation.py`): links are refused outright, then
DeepSeek reviews the scroll against a short policy (no real people, no characters lifted from
existing novels, no sexual content or hate, no instructions aimed at the AI). A blocked NPC gets a
reason the creator can fix with the Storyteller. If the check itself fails, the NPC is saved hidden
and marked "needs review" rather than going live unchecked.

Set `ADMIN_PASSWORD` and open `/admin.html` to approve, hide, restore or delete NPCs (including
reading their secrets), to download a JSON backup, and to press **Add 3 citizens**, which rolls
and releases characters signed "Ray" so the first visitor isn't alone in an empty world.

## Deploying to Railway

The repo includes a `Dockerfile` and `railway.json`, so Railway builds it without extra settings.

1. Push this repository to GitHub.
2. In Railway: **New Project → Deploy from GitHub repo**, and pick it.
3. **Add a volume** to the service, mounted at `/data`. The SQLite database lives there
   (`DATABASE_PATH=/data/jianghu.db` is already set in the Dockerfile). Without a volume, every
   deploy wipes the NPCs.
4. **Variables:** `DEEPSEEK_API_KEY`, and a long random `ADMIN_PASSWORD`.
5. **Settings → Networking → Generate Domain** for a free `*.up.railway.app` address, or add your
   own domain there and create the DNS record it shows.
6. Keep the service at **one replica**: the rate limiter lives in memory.

Each push to GitHub redeploys. The same `Dockerfile` runs on Fly.io, Render or any server with
Docker. DeepSeek bills from a prepaid balance, so a small top-up doubles as a hard spending cap.

## Next steps

1. Longer NPC memory: summarise old conversations instead of dropping them
2. A second, cheap check that rewrites out-of-period or out-of-voice replies
3. An eval set of probing lines run against several NPCs on every prompt change
4. Rumours: notable deeds spread to bonded NPCs and across regions
5. Real painted art: an image model, or layered parts drawn by an artist, behind `portrait.js`
