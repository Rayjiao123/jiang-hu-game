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
"Ask Ray" opens a sheet with Ray's notes (everything she has learned, and how close each way out is) above the chat with him.

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
static/portrait.js     painted character portraits (soft Jin Yong game-art style), with a cutout mode and a head-and-shoulders face crop for round avatars
static/scenes.js       painted backdrops, including the desert inn at dusk
app/case.py            THE STORY: truth, cast, clues, clock, events, escape rules, prologue and endings
app/main.py            FastAPI routes; streams replies as server-sent events; the clue referee; the clock; Ray
app/agent.py           streaming tool-use loop for DeepSeek (OpenAI chat format)
app/game.py            appearance options, first impressions, what people can see of Qinghe, and the tools they may call (including hero_did)
app/prompts.py         world bible, era rules, per-person instructions, Ray's instructions, the ending prompt
app/i18n.py            the three languages: picking one for a request, cleaning the model's text, checking a reply is in the right language
app/case_th.py         the Thai text of everything fixed in the story (case.py appends it at start-up and refuses to start if any is missing)
static/i18n.js         the page's own text in English, Chinese and Thai, and the language picker
app/db.py              SQLite: plays (one per visitor) and talks (one per visitor and person)
app/ratelimit.py       per-visitor and daily caps on model calls
app/stats.py           the admin's numbers and transcripts, built from the events table
static/admin.html      the admin page: funnel, endings, per-character numbers, conversations
evals/run.py           the live evaluation of the characters
```

**Prompt layout for caching.** Each request is `[system: world + era rules + this person + Qinghe] [history]
[system: time, trust and the facts they may tell now + reply language] [user message]`. The first part is identical every turn,
so DeepSeek's automatic prefix cache bills it at the cache-hit rate.

**Portraits in the soft painted style of Jin Yong game art.** DeepSeek's API doesn't generate images, so each character is a set of
about 17 appearance options (hair, eyes, outfit, weapon, aura and so on) from fixed lists in `app/game.py`, and `static/portrait.js`
draws the matching layers. Portraits appear instantly and cost nothing. Ray's look in `case.GM` is a guess; change its appearance dict
to match. They are procedural vector art; for painted-from-scratch art, send the same `appearance` object to an image model, or have an
artist draw the layers.

**Three languages, one at a time.** The player picks English, 中文 or ไทย on the home page (it is remembered, guessed from the browser the first time, and
changeable from the ☰ menu, even mid-game). The page shows only that language.

- **Fixed story text** (the cast cards, clues, the night's events, the opening, the deaths and written endings, error messages) is written once in all three in a single
  string, `English ||| 中文 ||| ไทย`. The browser sends an `X-Lang` header and the server picks the part before anything leaves it (`i18n.localize`), so
  the page never sees a separator. English and Chinese live in `app/case.py`, Thai in `app/case_th.py`; `case.py` fails to import if a Thai text is missing,
  and a test checks every one is in the right script. The AI-only fields (how a person talks, what they know) are English and Chinese only.
- **What the AI writes** is one language from the start. Every turn ends with an instruction to reply in the chosen language only (`i18n.reply_rule`: no translation, no `|||`,
  no Chinese characters in Thai or English, natural idiom for the language), and every prompt carries the names spelled in all three languages so a Thai reply writes ชิงเหอ,
  not 青禾. This replaced the old "English then Chinese" replies, so there are no translation calls any more. If a stray Chinese phrase still slips into Thai or English,
  `i18n.clean_ai` removes it.
- **The player's words** are sent as typed, in whatever language, and the separator is stripped from them. The checks that read them (fatal slips, trust, the clue referee) are
  evaluated in all three languages.
- **Thai** has its own font (Noto Serif Thai) and Thai threats are recognised like English and Chinese ones.

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
| POST | `/api/feedback` | a 👍 or 👎 on one of a character's replies |
| GET | `/api/admin/stats` · `/api/admin/transcripts` | visitor numbers and conversations (needs `ADMIN_PASSWORD`) |
| POST | `/api/move` | try one of the two ways out (`tunnel` or `kill`); fatal if the clues she holds don't open it |
| POST | `/api/ending` | after a successful move: Ray's telling of the whole story and what became of everyone |

Every request may carry `X-Lang: en|zh|th`; responses, errors and streamed events come back in that language.

Visitors are identified by an anonymous `vid` cookie, which owns their night and conversations. Nothing is shared between visitors.

## Knowing your visitors

Set `ADMIN_PASSWORD` and open `/admin.html`. The page needs the password (sent as a bearer token to `/api/admin/*`), is marked `noindex`,
and is switched off entirely when the variable is empty.

- **Counts, never text.** `events` records one row per thing a visitor did: `visit`, `start`, `talk` (who), `msg` (who, trust change, fatal or not),
  `clue`, `gm`, `move`, `end` (ending, cause of death, messages, minutes), `abandoned`, `error`, `feedback`. A visitor is the anonymous `vid` cookie; the
  admin shows a short hash of it. The test suite checks that what a player typed never reaches `events`.
- **What the page shows:** visitors and page loads, nights started / finished / left unfinished, a funnel (opened the page, started, talked,
  asked Ray, made the final move, reached an ending), how many reached each ending and how they died, minutes to finish, per-character
  numbers (talks, messages, clues told, average trust change, how often they killed her, thumbs), which clues get found, AI errors by kind, and a per-day table.
- **Conversations are kept** so the AI's replies can be read. A night that ends or is restarted moves its conversations to `talk_archive` instead of deleting them.
  The landing page says chats are saved to run and improve the game; if you keep them for long, add a retention rule and a privacy page.
- **Thumbs.** Every reply has 👍 / 👎. The admin transcript view can show only the conversations with a 👎.
- **Spend.** `CALLS_PER_VISITOR_PER_10_MIN` (default 150) and `DAILY_CALL_CAP` (default 8000) cap model calls. One player message costs about four or five calls
  (the message check, the reply, the clue referee, sometimes the ending), and a whole night is a few hundred. The counters live in memory, so a restart resets them.

## Evaluating the characters

Three layers, from cheap to real:

1. **`pytest` (offline, free, 59 tests)**: the rules that must never break, with a fake model. Facts above the trust line are not in a person's prompt;
   clues are filed only when offered; a wrong move or a fatal slip kills her; trust moves at most ±2; endings fall back to written text; the admin is locked.
2. **`python -m evals.run [--lang en|zh|th|all] [--judge]` (live model, about 60 calls and a minute per language)**: what a player would notice if it went wrong, run on all six characters.
   It checks that every reply is in the language asked for with no leaks or markup; that a nosy, polite question gets no gated fact out of anyone and never gets her killed;
   that modern things are met with confusion; that the check on her words catches fatal slips (showing the letter, revealing a plan, threatening) and,
   most importantly, never flags innocent messages; that kindness and rudeness move trust the right way; and that the clue referee files only what was really told.
   Every probe message is written in all three languages, so Chinese and Thai are tested on their own terms (a threat in Thai must be understood as one, a polite question in Chinese must not kill her). `--judge` adds a model that scores voice, period feel, drama and fluency from 1 to 5. Hard checks make the exit code 1; the report goes to `evals/last_report.json`.
   Run it whenever a prompt or the model changes and compare with the last report.
3. **Real players**: 👍/👎 on every reply, the transcripts page, the death-cause and per-person numbers. The eval set is small by design; the way it grows
   is to copy a 👎 reply from the admin into `evals/run.py` as a new case.

## Getting around

The ☰ menu is on every screen once a night has started: Home (the title page), the inn, Ray, Qinghe, and Start the night over. The logo goes home,
the inn has a ← Home link, a conversation has ←, and the ending screen offers Play again, Stay and Home. Leaving a conversation keeps it; the night is only
lost if you start over.

## Deploying to Railway

The repo includes a `Dockerfile` and `railway.json`, so Railway builds it without extra settings.

1. Push this repository to GitHub.
2. In Railway: **New Project → Deploy from GitHub repo**, and pick it.
3. **Add a volume** to the service, mounted at `/data`. The SQLite database lives there
   (`DATABASE_PATH=/data/jianghu.db` is already set in the Dockerfile). Without a volume, every
   deploy wipes the players' progress.
4. **Variables:** `DEEPSEEK_API_KEY`, and a long random `ADMIN_PASSWORD` to switch on `/admin.html`.
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
4. Grow the eval set from 👎 replies, and move the rate limiter to Redis if you run more than one replica
5. Longer conversation memory: summarise old turns instead of dropping them
6. Real painted art: an image model, or layered parts drawn by an artist, behind `portrait.js`
