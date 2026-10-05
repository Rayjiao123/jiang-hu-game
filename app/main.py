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

from . import agent, config, db, game, moderation, prompts, ratelimit, roll as roller
from .ratelimit import RateLimited

app = FastAPI(title="Jianghu Chronicles")
db.init()

_client: openai.OpenAI | None = None


def llm() -> openai.OpenAI:
    global _client
    if not config.DEEPSEEK_API_KEY:
        raise HTTPException(503, "The AI isn't configured on this server yet (DEEPSEEK_API_KEY is missing).")
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
    if fresh:
        response.set_cookie("vid", vid, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https")
    return response


class Message(BaseModel):
    message: str = Field(min_length=1, max_length=config.MAX_MESSAGE_CHARS)


class Release(BaseModel):
    creator_name: str = Field(default="", max_length=40)


class NewSession(BaseModel):
    npc_id: str | None = None
    draft_id: str | None = None


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
        yield {"type": "error", "code": "upstream", "message": "The AI service didn't answer. Try again in a moment."}
        print("DeepSeek error:", repr(e))


# ---------- read-only ----------

@app.get("/api/status")
def status():
    return {"ai": bool(config.DEEPSEEK_API_KEY)}


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
        raise HTTPException(404, "That draft doesn't exist. Start a new NPC.")
    return d


def _open_draft(draft_id: str, vid: str) -> None:
    with db.session() as conn:
        if _draft(conn, draft_id, vid)["released"]:
            raise HTTPException(409, "This NPC is already in the jianghu. Start a new one.")


def _storyteller_events(client, draft_id: str, vid: str, message: str) -> Iterator[dict]:
    """One Storyteller turn: stream its reply and tool effects, and keep the sheet in the database."""
    with db.session() as conn:
        draft = _draft(conn, draft_id, vid)
        turn = agent.Turn()
        tools = game.storyteller_tools(conn, draft["sheet"], turn)
        messages = [{"role": "system", "content": prompts.STORYTELLER}, *agent.history(draft["turns"]),
                    {"role": "system", "content": prompts.storyteller_state(draft["sheet"], game.missing(draft["sheet"]), message)},
                    {"role": "user", "content": message}]
        try:
            # the first reply carries a whole scroll of fields, so it needs room for the tool call
            for ev in agent.run(client, config.CHAT_MODEL, messages, tools, turn, vid, max_tokens=1600):
                if ev["type"] == "done":
                    draft["turns"] += [{"role": "user", "content": message},
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
        yield {"type": "roll", "text": seed["summary"]}
        yield from _storyteller_events(client, draft_id, vid, roller.roll_message(seed))
    return sse(guarded(events()))


@app.post("/api/drafts/{draft_id}/release")
def release(draft_id: str, body: Release, request: Request):
    vid = request.state.vid
    with db.session() as conn:
        draft = _draft(conn, draft_id, vid)
    if draft["released"]:
        return {"id": draft["released"], "pending": False}
    if game.missing(draft["sheet"]):
        raise HTTPException(400, "The scroll isn't finished yet. Ask the Storyteller to fill the rest.")

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
        raise HTTPException(422, f"This NPC can't be released yet: {reason} Ask the Storyteller to change it, then try again.")

    with db.session() as conn:
        draft = _draft(conn, draft_id, vid)
        npc_id = db.insert_npc(conn, draft["sheet"], vid, sheet["creator_name"],
                               hidden=verdict == "review", flag=reason if verdict == "review" else "")
        draft["released"] = npc_id
        db.save_draft(conn, draft)
    return {"id": npc_id, "pending": verdict == "review"}


# ---------- talking to an NPC (released, or a draft in rehearsal) ----------

def _npc_for(conn, sess: dict, vid: str) -> tuple[dict, str]:
    if sess.get("npc_id"):
        npc = db.get_npc(conn, sess["npc_id"])
        if not npc:
            raise HTTPException(404, "That NPC has left the jianghu.")
        return npc, db.get_secret(conn, npc["id"])
    sheet = _draft(conn, sess["draft_id"], vid)["sheet"]
    return {**sheet, "id": "draft"}, sheet.get("secret", "")


@app.post("/api/sessions")
def new_session(body: NewSession, request: Request):
    vid = request.state.vid
    with db.session() as conn:
        if body.npc_id:
            npc = db.get_npc(conn, body.npc_id)
            if not npc:
                raise HTTPException(404, "That NPC has left the jianghu.")
            has_secret = bool(db.get_secret(conn, npc["id"]))
        elif body.draft_id:
            npc = {**_draft(conn, body.draft_id, vid)["sheet"], "id": "draft"}
            has_secret = bool(npc.get("secret"))
        else:
            raise HTTPException(400, "Say who to talk to.")
        trust = game.STARTING_TRUST.get(npc.get("alignment"), 3)
        sid = db.create_session(conn, vid, trust, npc_id=body.npc_id if body.npc_id else None,
                                draft_id=None if body.npc_id else body.draft_id)
    card = {k: npc.get(k) for k in ("name", "title", "sect", "location", "alignment", "greeting", "appearance", "svg")}
    return {"id": sid, "npc": card, "trust": trust, "revealed": False, "has_secret": has_secret,
            "threshold": config.SECRET_TRUST_THRESHOLD, "rehearsal": not body.npc_id}


@app.post("/api/sessions/{sid}/chat")
def npc_chat(sid: str, body: Message, request: Request):
    vid = request.state.vid
    with db.session() as conn:
        if not db.get_session(conn, sid, vid):
            raise HTTPException(404, "That conversation has ended. Talk to them again.")
    client = llm()

    def events():
        with db.session() as conn:
            sess = db.get_session(conn, sid, vid)
            npc, secret = _npc_for(conn, sess, vid)
            others = [n for n in db.list_npcs(conn) if n["id"] != npc["id"]]
            turn = agent.Turn()
            tools = game.npc_tools(conn, npc, secret, sess, turn)
            messages = [{"role": "system", "content": prompts.npc_system(npc, others, game.admirers(conn, npc["id"]))},
                        *agent.history(sess["turns"]),
                        {"role": "system", "content": prompts.npc_state(sess["trust"], sess["revealed"], body.message)},
                        {"role": "user", "content": body.message}]
            try:
                for ev in agent.run(client, config.CHAT_MODEL, messages, tools, turn, vid, max_tokens=500):
                    if ev["type"] == "done":
                        sess["turns"] += [{"role": "user", "content": body.message},
                                          {"role": "assistant", "content": ev["text"] or "…"}]
                    yield ev
            finally:
                db.save_session(conn, sess)
    return sse(guarded(events()))


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
    for _ in _storyteller_events(client, draft_id, vid, roller.roll_message(seed)):
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
