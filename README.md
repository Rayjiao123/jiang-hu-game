# 江湖录 Jianghu Chronicles

A website for a Song-dynasty wuxia game where every NPC is an AI agent created by a visitor.
A visitor says one line (or just presses **Roll a stranger**) and the Storyteller agent writes a
whole character: name, epithet, quirks, secret, signature move, and a wuxia-illustration portrait drawn
from their personality. They can talk to the NPC to try it out, release it into the shared world,
and anyone can then talk to any NPC as the hero (or just **Wander** and meet someone).

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
static/index.html      page markup and styles
static/app.js          Storyteller chat, roll, scroll, conversations, NPC cards, wander
static/portrait.js     portrait builder in the style of classic Chinese wuxia game art: appearance options in, SVG out
static/hero.js         the animated ink-wash painting behind the introduction
static/admin.html      password-protected review page: approve, hide, delete, add citizens, back up
app/main.py            FastAPI routes; streams replies to the page as server-sent events
app/agent.py           streaming tool-use loop for DeepSeek (OpenAI chat format)
app/game.py            game rules and the tools each agent may call
app/prompts.py         world bible, era rules, Storyteller and NPC instructions
app/roll.py            the dice: random role, place, twist and look for "Roll a stranger" (each phrase in English and Chinese)
app/bilingual.py       the "English ||| 中文" format, its checks, and the fallback translation
app/moderation.py      automatic content check before an NPC goes public
app/db.py              SQLite: npcs, npc_secrets, drafts, sessions
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

**Roll a stranger.** `app/roll.py` rolls a role, a place, a twist and four visual cues in code,
because a model asked for "a random character" keeps producing the same one. The Storyteller builds
the character from that seed.

**Portraits in the style of Chinese wuxia game art, drawn from the personality.** DeepSeek's API
doesn't generate images, so the Storyteller picks 16 appearance options (hair, eyes, outfit, weapon,
aura, scene and so on) from fixed lists in `app/game.py`, and `static/portrait.js` draws the matching
layers: ink outlines with a hand-brushed wobble, realistic proportions, narrow eyes under strong brows,
hanfu, topknots and long beards, an ink-wash landscape on paper, and a red seal. Every portrait shares
one look, appears instantly, costs nothing, and cannot carry unsafe markup. To use a real image model
later, send the same `appearance` object to it as a prompt.

**Everything is in English and Chinese.** AI text is written `English ||| 中文`. Every scroll field
(except the name, which is Chinese plus pinyin) must follow that form: `set_fields` refuses a field
written in one language and tells the model what to fix. Replies use the same form, and if the model
forgets, the server translates the missing half (`app/bilingual.py`). The visitor's own messages are
translated by `/api/translate` and shown under them. Fixed messages and errors are written in both
languages in the code. The admin page is English only.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | whether the AI is configured |
| GET | `/api/npcs` | public NPC cards (never secrets) and bond count |
| POST | `/api/drafts` | start a new NPC |
| POST | `/api/drafts/{id}/chat` | talk to the Storyteller (stream) |
| POST | `/api/drafts/{id}/roll` | roll a random character (stream) |
| POST | `/api/translate` | the other-language version of a visitor's message |
| POST | `/api/drafts/{id}/release` | check and publish the NPC |
| POST | `/api/sessions` | start talking to an NPC (`npc_id`) or rehearse a draft (`draft_id`) |
| POST | `/api/sessions/{id}/chat` | talk to the NPC (stream) |

Visitors are identified by an anonymous `vid` cookie, which owns their drafts and conversations.

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

1. NPC memory: summarise each conversation and load it next time
2. A second, cheap check that rewrites out-of-period or out-of-voice replies
3. An eval set of probing lines run against several NPCs on every prompt change
4. Rumours: notable deeds spread to bonded NPCs
