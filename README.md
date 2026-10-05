# 江湖录 Jianghu Chronicles

A website for a Song-dynasty wuxia game where every NPC is an AI agent created by a visitor.
Visitors design an NPC with the Storyteller agent, rehearse talking to it, paint its ink-wash
portrait and release it into a shared world. Anyone can then talk to any NPC as the hero.

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
static/index.html      the whole page: hero painting, Storyteller chat, scroll, NPC cards, conversations
app/main.py            FastAPI routes; streams replies to the page as server-sent events
app/agent.py           streaming tool-use loop for DeepSeek (OpenAI chat format)
app/game.py            game rules and the tools each agent may call
app/prompts.py         world bible, era rules, Storyteller and NPC instructions, portrait brief
app/svg.py             whitelist sanitiser for model-drawn portraits
app/moderation.py      automatic content check before an NPC goes public
app/db.py              SQLite: npcs, npc_secrets, drafts, sessions
static/admin.html      password-protected review page: approve, hide, delete, back up
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

**Reply language is decided in code** (`prompts.reply_language`), because the model otherwise
drifts into the character's own language.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | whether the AI is configured |
| GET | `/api/npcs` | public NPC cards (never secrets) and bond count |
| POST | `/api/drafts` | start a new NPC |
| POST | `/api/drafts/{id}/chat` | talk to the Storyteller (stream) |
| POST | `/api/drafts/{id}/portrait` | paint the portrait (stream) |
| POST | `/api/drafts/{id}/release` | publish the NPC |
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
reading their secrets) and to download a JSON backup of every NPC.

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
