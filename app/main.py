"""Jianghu Chronicles web server: the page, the NPC API and the DeepSeek-powered agents."""
import json
import re
import secrets
import uuid
from typing import Iterator

import openai
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, bilingual, config, db, game, moderation, prompts, ratelimit, roll as roller, world
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


# ---------- visitors: an anonymous id in a cookie owns drafts and conversations ----------

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


class Release(BaseModel):
    creator_name: str = Field(default="", max_length=40)


class NewSession(BaseModel):
    npc_id: str


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


def _hero(conn, vid: str) -> dict:
    """The character this visitor plays. Conversations need one."""
    player = db.get_player(conn, vid)
    hero = db.get_npc(conn, player["npc_id"], include_hidden=True) if player else None
    if not hero:
        raise HTTPException(409, bi("Create your character first.", "请先创建你的人物。"))
    return hero


@app.get("/api/me")
def me(request: Request):
    """The visitor's own character, with the parts only they may see."""
    vid = request.state.vid
    with db.session() as conn:
        player = db.get_player(conn, vid)
        hero = db.get_npc(conn, player["npc_id"], include_hidden=True) if player else None
        if not hero:
            if player:
                db.clear_player(conn, vid)       # an admin removed them
            return {"hero": None}
        card = db.public_card(hero)
        card.update(secret=db.get_secret(conn, hero["id"]), speech=hero.get("speech", ""),
                    knowledge=hero.get("knowledge", ""), pending=bool(hero["hidden"] and hero["flag"]))
    return {"hero": card}


@app.post("/api/me/reset")
def me_reset(request: Request):
    """Stop playing as this character and make a new one. The old character stays in the world."""
    with db.session() as conn:
        db.clear_player(conn, request.state.vid)
    return {"ok": True}


@app.get("/api/npcs")
def list_npcs():
    with db.session() as conn:
        npcs = db.list_npcs(conn)
    return {"npcs": [db.public_card(n) for n in npcs],
            "bonds": sum(len(n.get("bonds") or []) for n in npcs)}


# ---------- creating an NPC with the Storyteller ----------

@app.post("/api/drafts")
def new_draft(request: Request):
    with db.session() as conn:
        sheet = game.blank_sheet()
        draft_id = db.create_draft(conn, request.state.vid, sheet)
    return {"id": draft_id, "sheet": sheet, "missing": game.missing(sheet)}


def _draft(conn, draft_id: str, vid: str) -> dict:
    d = db.get_draft(conn, draft_id, vid)
    if not d:
        raise HTTPException(404, bi("That draft doesn't exist. Start a new NPC.", "找不到这份草稿，请重新创建人物。"))
    return d


def _open_draft(draft_id: str, vid: str) -> None:
    with db.session() as conn:
        if _draft(conn, draft_id, vid)["released"]:
            raise HTTPException(409, bi("This NPC is already in the jianghu. Start a new one.", "这位人物已放入江湖，请重新创建。"))


def _finish(client, vid: str, ev: dict) -> Iterator[dict]:
    """On a reply that is in one language only, translate it and append the other half (the model sometimes forgets)."""
    text = bilingual.normalize(ev["text"])
    if text and bilingual.SEP not in text:
        try:
            ratelimit.check(vid)
            other = bilingual.counterpart(client, config.CHAT_MODEL, text)
        except RateLimited:
            other = ""
        if other:
            en, zh = (other, text) if bilingual.language_of(text) == "Chinese" else (text, other)
            text = f"{en}\n{bilingual.SEP}\n{zh}"
    yield {"type": "done", "text": text}      # the page replaces what it streamed with this tidied version


def _bilingual_line(client, vid: str, message: str) -> str:
    """The visitor's own line as 'English ||| 中文', so both languages show under it and in the history."""
    if bilingual.SEP in message or bilingual.has_both(message):
        return message
    try:
        ratelimit.check(vid)
    except RateLimited:
        return message
    other = bilingual.counterpart(client, config.CHAT_MODEL, message)
    if not other:
        return message
    en, zh = (other, message) if bilingual.language_of(message) == "Chinese" else (message, other)
    return f"{en} {bilingual.SEP} {zh}"


def _storyteller_events(client, draft_id: str, vid: str, message: str, translate: bool = True) -> Iterator[dict]:
    """One Storyteller turn: stream its reply and tool effects, and keep the sheet in the database."""
    line = message
    if translate:
        line = _bilingual_line(client, vid, message)
        yield {"type": "user", "text": line}
    with db.session() as conn:
        draft = _draft(conn, draft_id, vid)
        turn = agent.Turn()
        tools = game.storyteller_tools(conn, draft["sheet"], turn)
        messages = [{"role": "system", "content": prompts.STORYTELLER}, *agent.history(draft["turns"]),
                    {"role": "system", "content": prompts.storyteller_state(draft["sheet"], game.missing(draft["sheet"]))},
                    {"role": "user", "content": bilingual.plain(line)}]
        try:
            # the first reply carries a whole scroll of fields, so it needs room for the tool call
            for raw in agent.run(client, config.CHAT_MODEL, messages, tools, turn, vid, max_tokens=1800):
                for ev in (_finish(client, vid, raw) if raw["type"] == "done" else [raw]):
                    if ev["type"] == "done":
                        draft["turns"] += [{"role": "user", "content": line},
                                           {"role": "assistant", "content": ev["text"] or "…"}]
                    yield ev
        finally:
            db.save_draft(conn, draft)   # keep sheet changes even if the reply failed


@app.post("/api/drafts/{draft_id}/chat")
def storyteller_chat(draft_id: str, body: Message, request: Request):
    vid = request.state.vid
    _open_draft(draft_id, vid)
    client = llm()
    return sse(guarded(_storyteller_events(client, draft_id, vid, body.message)))


@app.post("/api/drafts/{draft_id}/roll")
def roll(draft_id: str, request: Request):
    """Build a random character: the dice are rolled here, the Storyteller does the rest."""
    vid = request.state.vid
    _open_draft(draft_id, vid)
    client = llm()
    seed = roller.random_seed()
    with db.session() as conn:
        draft = _draft(conn, draft_id, vid)
        draft["sheet"], draft["turns"] = game.blank_sheet(), []
        db.save_draft(conn, draft)

    def events():
        yield {"type": "roll", "text": seed["summary"], "text_zh": seed["summary_zh"]}
        yield from _storyteller_events(client, draft_id, vid, roller.roll_message(seed), translate=False)
    return sse(guarded(events()))


@app.post("/api/drafts/{draft_id}/release")
def release(draft_id: str, body: Release, request: Request):
    vid = request.state.vid
    with db.session() as conn:
        draft = _draft(conn, draft_id, vid)
    if draft["released"]:
        with db.session() as conn:
            db.set_player(conn, vid, draft_id, draft["released"])
        return {"id": draft["released"], "pending": False}
    if game.missing(draft["sheet"]):
        raise HTTPException(400, bi("The scroll isn't finished yet. Ask the Storyteller to fill the rest.", "卷轴还没写完，请让说书人补全。"))

    sheet = {**draft["sheet"], "creator_name": game.clip(body.creator_name, 40)}
    try:
        ratelimit.check(vid)
        client = llm()
    except RateLimited as e:
        raise HTTPException(429, str(e))
    except HTTPException:
        client = None
    verdict, reason = moderation.check(client, config.CHAT_MODEL, sheet)
    if verdict == "block":
        why_en, why_zh = bilingual.split(reason)
        raise HTTPException(422, bi(f"This character can't enter the jianghu yet: {why_en or reason} Ask the Storyteller to change it, then try again.",
                                    f"暂时不能放入江湖：{why_zh or why_en} 请让说书人修改后再试。"))

    with db.session() as conn:
        draft = _draft(conn, draft_id, vid)
        npc_id = db.insert_npc(conn, draft["sheet"], vid, sheet["creator_name"],
                               hidden=verdict == "review", flag=reason if verdict == "review" else "")
        draft["released"] = npc_id
        db.save_draft(conn, draft)
        db.set_player(conn, vid, draft_id, npc_id)       # from now on the visitor plays as this character
    return {"id": npc_id, "pending": verdict == "review"}


# ---------- talking to an NPC as the visitor's own character ----------

def _card(npc: dict) -> dict:
    return {k: npc.get(k) for k in ("id", "name", "title", "sect", "location", "alignment", "greeting", "appearance")} | {"region": world.region_for(npc)}


@app.post("/api/sessions")
def new_session(body: NewSession, request: Request):
    """Start talking to an NPC, or pick up where this character and that NPC left off."""
    vid = request.state.vid
    with db.session() as conn:
        hero = _hero(conn, vid)
        npc = db.get_npc(conn, body.npc_id)
        if not npc:
            raise HTTPException(404, bi("That NPC has left the jianghu.", "这位人物已离开江湖。"))
        if npc["id"] == hero["id"]:
            raise HTTPException(400, bi("That is your own character.", "那是你自己的人物。"))
        trust0, why = game.starting_trust(npc, hero)
        sess = db.find_session(conn, vid, hero["id"], npc["id"])
        if not sess:
            sid = db.create_session(conn, vid, trust0, npc["id"], hero["id"])
            sess = db.get_session(conn, sid, vid)
        has_secret = bool(db.get_secret(conn, npc["id"]))
    shown = [t for t in sess["turns"] if not t.get("hidden")][-40:]
    return {"id": sess["id"], "npc": _card(npc), "trust": sess["trust"], "revealed": sess["revealed"], "has_secret": has_secret,
            "threshold": config.SECRET_TRUST_THRESHOLD, "impression": why, "turns": shown, "fresh": not sess["turns"]}


def _npc_turn(client, sid: str, vid: str, message: str | None) -> Iterator[dict]:
    """One NPC turn. message=None means the hero has just walked up and the NPC speaks first."""
    opening = message is None
    line = "*approaches you* ||| *走上前来*" if opening else _bilingual_line(client, vid, message)
    if not opening:
        yield {"type": "user", "text": line}
    with db.session() as conn:
        sess = db.get_session(conn, sid, vid)
        if not sess:
            raise HTTPException(404, bi("That conversation has ended. Talk to them again.", "这段对话已结束，请重新交谈。"))
        hero = _hero(conn, vid)
        npc = db.get_npc(conn, sess["npc_id"])
        if not npc:
            raise HTTPException(404, bi("That NPC has left the jianghu.", "这位人物已离开江湖。"))
        secret = db.get_secret(conn, npc["id"])
        others = [n for n in db.list_npcs(conn) if n["id"] not in (npc["id"], hero["id"])]
        turn = agent.Turn()
        tools = game.npc_tools(conn, npc, secret, sess, turn)
        messages = [{"role": "system", "content": prompts.npc_system(npc, others, game.admirers(conn, npc["id"]), hero)},
                    *agent.history(sess["turns"]),
                    {"role": "system", "content": prompts.npc_state(sess["trust"], sess["revealed"], opening)},
                    {"role": "user", "content": bilingual.plain(line)}]
        try:
            for raw in agent.run(client, config.CHAT_MODEL, messages, tools, turn, vid, max_tokens=800):
                for ev in (_finish(client, vid, raw) if raw["type"] == "done" else [raw]):
                    if ev["type"] == "done":
                        sess["turns"] += [{"role": "user", "content": line, **({"hidden": True} if opening else {})},
                                          {"role": "assistant", "content": ev["text"] or "…"}]
                    yield ev
        finally:
            db.save_session(conn, sess)


def _own_session(sid: str, vid: str) -> dict:
    with db.session() as conn:
        sess = db.get_session(conn, sid, vid)
    if not sess:
        raise HTTPException(404, bi("That conversation has ended. Talk to them again.", "这段对话已结束，请重新交谈。"))
    return sess


@app.post("/api/sessions/{sid}/open")
def npc_open(sid: str, request: Request):
    """The NPC speaks first, to this particular hero."""
    vid = request.state.vid
    if _own_session(sid, vid)["turns"]:
        raise HTTPException(409, bi("This conversation has already begun.", "这段对话已经开始。"))
    client = llm()
    return sse(guarded(_npc_turn(client, sid, vid, None)))


@app.post("/api/sessions/{sid}/chat")
def npc_chat(sid: str, body: Message, request: Request):
    vid = request.state.vid
    _own_session(sid, vid)
    client = llm()
    return sse(guarded(_npc_turn(client, sid, vid, body.message)))


# ---------- admin: review, hide, restore, delete, export ----------

def require_admin(request: Request) -> None:
    if not config.ADMIN_PASSWORD:
        raise HTTPException(404, "Admin is switched off. Set ADMIN_PASSWORD to enable it.")
    given = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not secrets.compare_digest(given.encode(), config.ADMIN_PASSWORD.encode()):
        raise HTTPException(401, "Wrong password.")


@app.get("/api/admin/npcs", dependencies=[Depends(require_admin)])
def admin_list():
    with db.session() as conn:
        npcs = db.list_npcs(conn, limit=1000, include_hidden=True)
        for n in npcs:
            n["secret"] = db.get_secret(conn, n["id"])
    return {"npcs": npcs}


class Visibility(BaseModel):
    hidden: bool
    flag: str = Field(default="", max_length=200)


@app.post("/api/admin/npcs/{npc_id}/visibility", dependencies=[Depends(require_admin)])
def admin_visibility(npc_id: str, body: Visibility):
    with db.session() as conn:
        if not db.set_hidden(conn, npc_id, body.hidden, body.flag if body.hidden else ""):
            raise HTTPException(404, "No such NPC.")
    return {"ok": True}


@app.delete("/api/admin/npcs/{npc_id}", dependencies=[Depends(require_admin)])
def admin_delete(npc_id: str):
    with db.session() as conn:
        if not db.delete_npc(conn, npc_id):
            raise HTTPException(404, "No such NPC.")
    return {"ok": True}


class SeedRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=5)


def _generate_npc(client, creator_name: str) -> tuple[str | None, str]:
    """Roll a character, check it, and release it. Returns (npc id or None, note)."""
    vid = "admin-seed"
    with db.session() as conn:
        draft_id = db.create_draft(conn, vid, game.blank_sheet())
    seed = roller.random_seed()
    for _ in _storyteller_events(client, draft_id, vid, roller.roll_message(seed), translate=False):
        pass
    with db.session() as conn:
        draft = _draft(conn, draft_id, vid)
    if game.missing(draft["sheet"]):
        return None, f"{seed['summary']}: the Storyteller left fields empty"
    verdict, reason = moderation.check(client, config.CHAT_MODEL, {**draft["sheet"], "creator_name": creator_name})
    if verdict == "block":
        return None, f"{seed['summary']}: blocked ({reason})"
    with db.session() as conn:
        npc_id = db.insert_npc(conn, draft["sheet"], vid, creator_name,
                               hidden=verdict == "review", flag=reason if verdict == "review" else "")
    return npc_id, draft["sheet"]["name"]


@app.post("/api/admin/seed", dependencies=[Depends(require_admin)])
def admin_seed(body: SeedRequest):
    """Populate the world with generated citizens signed 'Ray', so the first visitor isn't alone."""
    client = llm()
    made, notes = [], []
    for _ in range(body.count):
        try:
            npc_id, note = _generate_npc(client, "Ray")
        except (RateLimited, openai.APIError) as e:
            notes.append(f"Stopped early: {e}")
            break
        (made if npc_id else notes).append(note)
    return {"created": made, "notes": notes}


@app.get("/api/admin/export", dependencies=[Depends(require_admin)])
def admin_export():
    """Every NPC including secrets, as one JSON file: a simple backup."""
    return JSONResponse(admin_list(), headers={"Content-Disposition": 'attachment; filename="jianghu-npcs.json"'})


app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")
