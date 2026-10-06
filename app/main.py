"""Jianghu Chronicles web server: the page, the murder-mystery API and the DeepSeek-powered agents."""
import json
import re
import uuid
from typing import Iterator

import openai
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, bilingual, case, config, db, game, prompts, ratelimit, roll as roller, world
from .bilingual import bi
from .ratelimit import RateLimited

app = FastAPI(title="Jianghu Chronicles")
db.init()

_client: openai.OpenAI | None = None


def llm() -> openai.OpenAI:
    global _client
    if not config.DEEPSEEK_API_KEY:
        raise HTTPException(503, bi("The AI isn't configured on this server yet (DEEPSEEK_API_KEY is missing).", "此服务器尚未配置 AI（缺少 DEEPSEEK_API_KEY）。"))
    if _client is None:
        _client = openai.OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL, timeout=120, max_retries=1)
    return _client


# ---------- visitors: an anonymous id in a cookie owns the case and the conversations ----------

@app.middleware("http")
async def visitor_cookie(request: Request, call_next):
    vid = request.cookies.get("vid", "")
    fresh = not re.fullmatch(r"[0-9a-f]{32}", vid)
    if fresh:
        vid = uuid.uuid4().hex
    request.state.vid = vid
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"      # re-check pages and scripts each visit, so updates show up at once
    if fresh:
        response.set_cookie("vid", vid, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https")
    return response


class Message(BaseModel):
    message: str = Field(min_length=1, max_length=config.MAX_MESSAGE_CHARS)


class Edit(BaseModel):
    field: str = Field(max_length=30)
    value: str = Field(max_length=300)


class NewTalk(BaseModel):
    npc: str = Field(max_length=20)


class Accusation(BaseModel):
    suspect: str = Field(max_length=20)
    evidence: list[str] = Field(default_factory=list, max_length=30)


class Fate(BaseModel):
    fate: str = Field(max_length=20)


def sse(events: Iterator[dict]) -> StreamingResponse:
    def body():
        for ev in events:
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def guarded(events: Iterator[dict]) -> Iterator[dict]:
    """Turn failures inside a stream into a final error event the page can show."""
    try:
        yield from events
    except RateLimited as e:
        yield {"type": "error", "code": "rate_limited", "message": str(e)}
    except HTTPException as e:
        yield {"type": "error", "code": "bad_request", "message": str(e.detail)}
    except openai.APIError as e:
        yield {"type": "error", "code": "upstream", "message": bi("The AI service didn't answer. Try again in a moment.", "AI 服务没有响应，请稍后再试。")}
        print("DeepSeek error:", repr(e))


# ---------- read-only ----------

@app.get("/api/status")
def status():
    return {"ai": bool(config.DEEPSEEK_API_KEY)}


@app.get("/api/world")
def get_world():
    return {"regions": world.public()}


@app.get("/api/case")
def get_case():
    """What the landing page shows before anyone has made a character: the case and the people on the mountain."""
    return {"title": case.CASE_TITLE, "cast": [case.public_card(k) for k in case.starting_cast()],
            "categories": case.CATEGORIES, "attempts": case.ATTEMPTS, "proof_needed": case.PROOF_NEEDED, "fates": case.FATES}


def _game(conn, vid: str, stage: str | tuple | None = None) -> dict:
    g = db.get_game(conn, vid)
    if not g:
        raise HTTPException(409, bi("Create your character first.", "请先创建你的人物。"))
    if stage and g["stage"] not in ((stage,) if isinstance(stage, str) else stage):
        raise HTTPException(409, bi("That isn't possible at this point in the story.", "故事此刻不能这样做。"))
    return g


def _visible(g: dict) -> list[str]:
    keys = case.starting_cast()
    if any(c in g["found"] for c in ("lu_lead", "lu_seen")):
        keys.append("lu")
    return keys


def _state(conn, g: dict) -> dict:
    """Everything the page needs to draw the game, and nothing the visitor has not earned."""
    found = g["found"]
    out = {"stage": g["stage"], "hero": g["hero"], "missing": game.missing(g["hero"]), "attempts": g["attempts"], "ending": g["ending"]}
    if g["stage"] == "creating":
        return out
    cast = []
    for k in _visible(g):
        card = case.public_card(k)
        talk = db.find_talk(conn, g["visitor_id"], k)
        card.update(clues_told=sum(1 for c in case.BY_KEY[k]["topics"] if c in found), met=bool(talk and talk["turns"]),
                    trust=talk["trust"] if talk else None)
        cast.append(card)
    out.update(cast=cast, found=[case.clue_view(c, g["hero"]) for c in found if c in case.CLUES],
               prologue=case.prologue(g["hero"]), unmet=len(case.discoverable()) - len([c for c in found if case.CLUES[c]["holder"]]))
    if g["stage"] == "lost":
        out["truth"] = case.truth(g["hero"])
    return out


@app.get("/api/game")
def get_game(request: Request):
    with db.session() as conn:
        g = db.get_game(conn, request.state.vid)
        return {"game": _state(conn, g) if g else None}


# ---------- making the hero with the Storyteller ----------

@app.post("/api/game/new")
def new_game(request: Request):
    with db.session() as conn:
        g = db.new_game(conn, request.state.vid, game.blank_sheet())
        return {"game": _state(conn, g)}


@app.post("/api/game/reset")
def reset_game(request: Request):
    with db.session() as conn:
        db.delete_game(conn, request.state.vid)
    return {"ok": True}


_MARKUP = re.compile(r"</?[A-Za-z_][\w-]*(?:\s[^<>]*)?/?>")


def _finish(client, vid: str, ev: dict) -> Iterator[dict]:
    """On a reply that is in one language only, translate it and append the other half (the model sometimes forgets).
    Stray tool-call markup the model sometimes writes into its text is removed first."""
    text = bilingual.normalize(re.sub(r"[ \t]+\n", "\n", _MARKUP.sub("", ev["text"])).strip())
    if text and bilingual.SEP not in text:
        try:
            ratelimit.check(vid)
            other = bilingual.counterpart(client, config.CHAT_MODEL, text, _names())
        except RateLimited:
            other = ""
        if other:
            en, zh = (other, text) if bilingual.language_of(text) == "Chinese" else (text, other)
            text = f"{en}\n{bilingual.SEP}\n{zh}"
    yield {"type": "done", "text": text}      # the page replaces what it streamed with this tidied version


def _names(hero: dict | None = None) -> str:
    """People who must keep one spelling in both languages."""
    extra = [hero.get("name", ""), hero.get("beloved_name", "")] if hero else []
    return bilingual.glossary([c["name"] for c in case.CAST] + extra)


def _bilingual_line(client, vid: str, message: str, hero: dict | None = None) -> str:
    """The visitor's own line as 'English ||| 中文', so both languages show under it and in the history."""
    if bilingual.SEP in message or bilingual.has_both(message):
        return message
    try:
        ratelimit.check(vid)
    except RateLimited:
        return message
    other = bilingual.counterpart(client, config.CHAT_MODEL, message, _names(hero))
    if not other:
        return message
    en, zh = (other, message) if bilingual.language_of(message) == "Chinese" else (message, other)
    return f"{en} {bilingual.SEP} {zh}"


def _storyteller_events(client, vid: str, message: str, translate: bool = True) -> Iterator[dict]:
    """One Storyteller turn: stream its reply and tool effects, and keep the sheet in the database."""
    line = message
    if translate:
        line = _bilingual_line(client, vid, message)
        yield {"type": "user", "text": line}
    with db.session() as conn:
        g = _game(conn, vid, "creating")
        turn = agent.Turn()
        tools = game.storyteller_tools(g["hero"], turn)
        messages = [{"role": "system", "content": prompts.STORYTELLER}, *agent.history(g["turns"]),
                    {"role": "system", "content": prompts.storyteller_state(g["hero"], game.missing(g["hero"]))},
                    {"role": "user", "content": bilingual.plain(line)}]
        try:
            # the first reply carries the whole sheet, so it needs room for the tool call
            for raw in agent.run(client, config.CHAT_MODEL, messages, tools, turn, vid, max_tokens=1800):
                for ev in (_finish(client, vid, raw) if raw["type"] == "done" else [raw]):
                    if ev["type"] == "done":
                        g["turns"] += [{"role": "user", "content": line}, {"role": "assistant", "content": ev["text"] or "…"}]
                    yield ev
        finally:
            db.save_game(conn, g)   # keep sheet changes even if the reply failed


@app.post("/api/game/chat")
def storyteller_chat(body: Message, request: Request):
    vid = request.state.vid
    with db.session() as conn:
        _game(conn, vid, "creating")
    client = llm()
    return sse(guarded(_storyteller_events(client, vid, body.message)))


@app.post("/api/game/roll")
def roll(request: Request):
    """Build a random hero: the dice are rolled here, the Storyteller does the rest."""
    vid = request.state.vid
    with db.session() as conn:
        g = _game(conn, vid, "creating")
    client = llm()
    seed = roller.random_seed()
    with db.session() as conn:
        g = _game(conn, vid, "creating")
        g["hero"], g["turns"] = game.blank_sheet(), []
        db.save_game(conn, g)

    def events():
        yield {"type": "roll", "text": seed["summary"], "text_zh": seed["summary_zh"]}
        yield from _storyteller_events(client, vid, roller.roll_message(seed), translate=False)
    return sse(guarded(events()))


@app.post("/api/game/edit")
def edit_hero(body: Edit, request: Request):
    """The visitor rewrites one trait by hand."""
    vid = request.state.vid
    with db.session() as conn:
        g = _game(conn, vid, "creating")
    value = body.value
    client = None
    if body.field in game.BILINGUAL and not bilingual.is_pair(value):
        try:
            ratelimit.check(vid)
            client = llm()
        except RateLimited as e:
            raise HTTPException(429, str(e))
    with db.session() as conn:
        g = _game(conn, vid, "creating")
        err = game.edit_field(client, config.CHAT_MODEL, g["hero"], body.field, value, _names(g["hero"]))
        if err:
            raise HTTPException(400, err)
        db.save_game(conn, g)
        return {"hero": g["hero"], "missing": game.missing(g["hero"])}


@app.post("/api/game/start")
def start_game(request: Request):
    """The hero is settled: the story begins at the first place, with the official story as the first clue."""
    with db.session() as conn:
        g = _game(conn, request.state.vid, "creating")
        if game.missing(g["hero"]):
            raise HTTPException(400, bi("Your hero isn't finished yet. Ask the Storyteller to fill in the rest.", "人物还没写完，请让说书人补全。"))
        g.update(stage="playing", found=["official"], attempts=case.ATTEMPTS)
        db.save_game(conn, g)
        return {"game": _state(conn, g)}


# ---------- talking to the people on the mountain ----------

def _card(key: str) -> dict:
    c = case.public_card(key)
    c.pop("clues_total", None)
    return c


@app.post("/api/talks")
def new_talk(body: NewTalk, request: Request):
    """Start talking to someone, or pick up where the hero and that person left off."""
    vid = request.state.vid
    with db.session() as conn:
        g = _game(conn, vid, ("playing", "accused"))
        if body.npc not in _visible(g):
            raise HTTPException(404, bi("There is nobody like that here.", "这里没有这个人。"))
        trust0, why = case.start_trust(body.npc, g["hero"])
        talk = db.find_talk(conn, vid, body.npc) or db.create_talk(conn, vid, body.npc, trust0)
        state = case.clue_state(body.npc, g["found"], talk["trust"])
    shown = [t for t in talk["turns"] if not t.get("hidden")][-40:]
    return {"id": talk["id"], "npc": _card(body.npc), "trust": talk["trust"], "impression": why, "turns": shown,
            "fresh": not talk["turns"], "told": len(state["told"]), "total": len(case.BY_KEY[body.npc]["topics"])}


def _npc_turn(client, tid: str, vid: str, message: str | None) -> Iterator[dict]:
    """One NPC turn. message=None means the hero has just walked up and the NPC speaks first."""
    opening = message is None
    with db.session() as conn:
        g = _game(conn, vid)
        line_hero = g["hero"]
    line = "*approaches you* ||| *走上前来*" if opening else _bilingual_line(client, vid, message, line_hero)
    if not opening:
        yield {"type": "user", "text": line}
    with db.session() as conn:
        g = _game(conn, vid, ("playing", "accused"))
        talk = db.get_talk(conn, tid, vid)
        if not talk:
            raise HTTPException(404, bi("That conversation has ended. Talk to them again.", "这段对话已结束，请重新交谈。"))
        key = talk["npc_key"]
        talk["trust_before"] = talk["trust"]       # clues are offered at the trust the hero walked in with
        turn = agent.Turn()
        tools = game.npc_tools(talk, turn)
        messages = [{"role": "system", "content": prompts.npc_system(key, g["hero"])},
                    *agent.history(talk["turns"]),
                    {"role": "system", "content": prompts.npc_state(key, talk["trust"], g["found"], g["hero"], opening)},
                    {"role": "user", "content": bilingual.plain(line)}]
        try:
            for raw in agent.run(client, config.CHAT_MODEL, messages, tools, turn, vid, max_tokens=800):
                for ev in (_finish(client, vid, raw) if raw["type"] == "done" else [raw]):
                    if ev["type"] == "done":
                        talk["turns"] += [{"role": "user", "content": line, **({"hidden": True} if opening else {})},
                                          {"role": "assistant", "content": ev["text"] or "…"}]
                    yield ev
                    if ev["type"] == "done" and not opening:
                        for clue in _credit(client, vid, key, g, ev["text"], talk["trust_before"]):
                            yield {"type": "clue", "clue": clue}
        finally:
            db.save_talk(conn, talk)
            db.save_game(conn, g)


VERIFY = ("You referee a murder-mystery game. A character has just spoken to the hero. Below are the facts the character was willing to tell. "
          "Answer with a JSON array of the ids of facts whose KEY information the character clearly told the hero in this reply. A fact counts when its main "
          "content was stated, even in other words. Hints, deflections, questions, or only a vague part of it do not count. Answer [] if none. Output only the JSON array.")


def _credit(client, vid: str, key: str, g: dict, reply: str, trust: int) -> list[dict]:
    """Which clues did this reply actually tell? The server decides (not the model that played the person) and files them in the case file."""
    ready = case.clue_state(key, g["found"], trust)["ready"]
    if not ready or not reply.strip():
        return []
    facts = "\n".join(f"{cid}: {case.plain_fact(cid, g['hero'])}" for cid in ready)
    try:
        ratelimit.check(vid)
        r = client.chat.completions.create(
            model=config.CHAT_MODEL, max_tokens=60, temperature=0, extra_body={"thinking": {"type": "disabled"}},
            messages=[{"role": "system", "content": VERIFY}, {"role": "user", "content": f"FACTS:\n{facts}\n\nREPLY:\n{bilingual.plain(reply)}"}])
        raw = (r.choices[0].message.content or "")
        told = json.loads(re.search(r"\[.*?\]", raw, re.S).group(0))
    except (RateLimited, AttributeError, ValueError, openai.APIError) as e:
        print("Clue check skipped:", repr(e))
        return []
    new = []
    for cid in told if isinstance(told, list) else []:
        if cid in ready and cid not in g["found"]:
            g["found"].append(cid)
            new.append(case.clue_view(cid, g["hero"]))
    return new


def _own_talk(tid: str, vid: str) -> dict:
    with db.session() as conn:
        talk = db.get_talk(conn, tid, vid)
    if not talk:
        raise HTTPException(404, bi("That conversation has ended. Talk to them again.", "这段对话已结束，请重新交谈。"))
    return talk


@app.post("/api/talks/{tid}/open")
def npc_open(tid: str, request: Request):
    """The person speaks first, to this particular hero."""
    vid = request.state.vid
    if _own_talk(tid, vid)["turns"]:
        raise HTTPException(409, bi("This conversation has already begun.", "这段对话已经开始。"))
    client = llm()
    return sse(guarded(_npc_turn(client, tid, vid, None)))


@app.post("/api/talks/{tid}/chat")
def npc_chat(tid: str, body: Message, request: Request):
    vid = request.state.vid
    _own_talk(tid, vid)
    client = llm()
    return sse(guarded(_npc_turn(client, tid, vid, body.message)))


# ---------- naming the killer ----------

@app.post("/api/accuse")
def accuse(body: Accusation, request: Request):
    """Name a suspect and lay out proof. The verdict is decided here, from the clues the hero actually holds."""
    with db.session() as conn:
        g = _game(conn, request.state.vid, "playing")
        if body.suspect not in _visible(g):
            raise HTTPException(404, bi("There is nobody like that here.", "这里没有这个人。"))
        result = case.judge(body.suspect, body.evidence, g["found"])
        if result["verdict"] == "correct":
            g["stage"] = "accused"
        else:
            g["attempts"] = max(0, g["attempts"] - 1)
            if g["attempts"] == 0:
                g["stage"] = "lost"
        db.save_game(conn, g)
        result.update(attempts=g["attempts"], stage=g["stage"])
        if g["stage"] == "lost":
            result["truth"] = case.truth(g["hero"])
        return result


@app.post("/api/ending")
def ending(body: Fate, request: Request):
    """The last scene: Yun Wuya confesses, and the hero chooses what to do with him."""
    vid = request.state.vid
    if body.fate not in case.FATES:
        raise HTTPException(400, bi("Choose one of the three.", "请从三者中选一。"))
    with db.session() as conn:
        g = _game(conn, vid, "accused")
        hero = g["hero"]
    text = ""
    try:
        ratelimit.check(vid)
        client = llm()
        prompt = prompts.ENDING.format(
            truth=case.fill(case.TRUTH_FOR_EPILOGUE, hero), hero=f"{hero['name']}, {bilingual.plain(hero['title'])}, path {hero['path']}, manner {hero['temperament']}",
            beloved=hero["beloved_name"], token=bilingual.plain(hero["beloved_token"]), fate=case.FATES[body.fate]["en"], format=bilingual.REPLY_FORMAT)
        r = client.chat.completions.create(model=config.CHAT_MODEL, max_tokens=900, extra_body={"thinking": {"type": "disabled"}},
                                           messages=[{"role": "system", "content": prompt}, {"role": "user", "content": "Write the final scene."}])
        text = bilingual.normalize((r.choices[0].message.content or "").strip())
        if text and bilingual.SEP not in text:
            other = bilingual.counterpart(client, config.CHAT_MODEL, text, _names(hero))
            if other:
                en, zh = (other, text) if bilingual.language_of(text) == "Chinese" else (text, other)
                text = f"{en}\n{bilingual.SEP}\n{zh}"
        if not bilingual.is_pair(text):
            text = ""
    except (RateLimited, HTTPException, openai.APIError) as e:
        print("Ending fell back to the written version:", repr(e))
    text = text or case.fallback_ending(body.fate, hero)
    with db.session() as conn:
        g = _game(conn, vid, "accused")
        g.update(stage="solved", ending=text)
        db.save_game(conn, g)
        return {"game": _state(conn, g)}


@app.get("/", include_in_schema=False)
def index():
    """The page, with each script and stylesheet stamped with a version so a browser can never mix old and new files."""
    static = config.ROOT / "static"
    version = str(int(max(p.stat().st_mtime for p in static.iterdir() if p.is_file())))
    html = (static / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'(src|href)="(/[\w.-]+\.(?:js|css))"', lambda m: f'{m.group(1)}="{m.group(2)}?v={version}"', html)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")
