"""人在江湖，身不由己 web server: the page, the story API and the DeepSeek-powered characters and game master."""
import json
import re
import uuid
from typing import Iterator

import openai
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, bilingual, case, config, db, game, prompts, ratelimit
from .bilingual import bi
from .ratelimit import RateLimited

app = FastAPI(title="人在江湖，身不由己")
db.init()

_client: openai.OpenAI | None = None


def llm() -> openai.OpenAI:
    global _client
    if not config.DEEPSEEK_API_KEY:
        raise HTTPException(503, bi("The AI isn't configured on this server yet (DEEPSEEK_API_KEY is missing).", "此服务器尚未配置 AI（缺少 DEEPSEEK_API_KEY）。"))
    if _client is None:
        _client = openai.OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL, timeout=120, max_retries=1)
    return _client


# ---------- visitors: an anonymous id in a cookie owns the night and the conversations ----------

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


class NewTalk(BaseModel):
    npc: str = Field(max_length=20)


class Move(BaseModel):
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


@app.get("/api/case")
def get_case():
    """What the landing page shows before anyone has started: the story, the people in the inn, the game master."""
    return {"title": case.CASE_TITLE, "situation": case.SITUATION, "prologue": case.PROLOGUE, "cast": [case.public_card(k) for k in case.BY_KEY],
            "hero": case.hero_card(), "gm": case.gm_card(), "categories": case.CATEGORIES, "fates": case.FATES, "clock": case.CLOCK}


def _play(conn, vid: str, stage: str | tuple | None = None) -> dict:
    g = db.get_play(conn, vid)
    if not g:
        raise HTTPException(409, bi("Start the story first.", "请先开始故事。"))
    if stage and g["stage"] not in ((stage,) if isinstance(stage, str) else stage):
        raise HTTPException(409, bi("That isn't possible at this point in the story.", "故事此刻不能这样做。"))
    return g


def _events(upto: int) -> list[dict]:
    return [{"beat": b, "text": case.event_for(b)} for b in range(1, min(upto, case.DAWN_BEAT) + 1) if case.event_for(b)]


def _state(conn, g: dict) -> dict:
    """Everything the page needs to draw the night, and nothing the visitor has not earned."""
    found = g["found"]
    cast = []
    for k in case.BY_KEY:
        card = case.public_card(k)
        talk = db.find_talk(conn, g["visitor_id"], k)
        card.update(clues_told=sum(1 for c in case.BY_KEY[k]["topics"] if c in found), met=bool(talk and talk["turns"]),
                    trust=talk["trust"] if talk else None)
        cast.append(card)
    out = {"stage": g["stage"], "cast": cast, "found": [case.clue_view(c) for c in found if c in case.CLUES], "clock": case.clock(g["beat"]),
           "events": _events(g["beat"]), "ending": g["ending"], "tier": g["tier"], "prologue": case.PROLOGUE, "hero": case.hero_card(), "gm": case.gm_card(),
           "unmet": len(case.discoverable()) - len([c for c in found if case.CLUES[c]["holder"]]), "gm_turns": g["turns"][-12:]}
    if g["stage"] == "lost":
        out["truth"] = f"{case.LOSS.split('|||')[0].strip()} {case.truth().split('|||')[0].strip()} {bilingual.SEP} {case.LOSS.split('|||')[1].strip()} {case.truth().split('|||')[1].strip()}"
    return out


@app.get("/api/game")
def get_game(request: Request):
    with db.session() as conn:
        g = db.get_play(conn, request.state.vid)
        return {"game": _state(conn, g) if g else None}


@app.post("/api/game/start")
def start_game(request: Request):
    """The night begins: the doors are barred, and that is the first thing she knows."""
    with db.session() as conn:
        g = db.new_play(conn, request.state.vid, ["official"])
        return {"game": _state(conn, g)}


@app.post("/api/game/reset")
def reset_game(request: Request):
    with db.session() as conn:
        db.delete_play(conn, request.state.vid)
    return {"ok": True}


# ---------- language helpers ----------

_MARKUP = re.compile(r"</?[A-Za-z_][\w-]*(?:\s[^<>]*)?/?>")


def _names() -> str:
    """People who must keep one spelling in both languages."""
    return bilingual.glossary([c["name"] for c in case.CAST] + [case.HERO["name"]])


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


def _bilingual_line(client, vid: str, message: str) -> str:
    """The visitor's own line as 'English ||| 中文', so both languages show under it and in the history."""
    if bilingual.SEP in message or bilingual.has_both(message):
        return message
    try:
        ratelimit.check(vid)
    except RateLimited:
        return message
    other = bilingual.counterpart(client, config.CHAT_MODEL, message, _names())
    if not other:
        return message
    en, zh = (other, message) if bilingual.language_of(message) == "Chinese" else (message, other)
    return f"{en} {bilingual.SEP} {zh}"


# ---------- the clock: the night is the deadline ----------

def _advance(g: dict, beats: int) -> list[dict]:
    """Let some of the night go by. Returns the game master's announcements for every hour that passed; at dawn the story is lost."""
    out = []
    for _ in range(beats):
        if g["beat"] >= case.DAWN_BEAT:
            break
        g["beat"] += 1
        if case.event_for(g["beat"]):
            out.append({"type": "gm", "beat": g["beat"], "text": case.event_for(g["beat"]), "clock": case.clock(g["beat"])})
    if g["beat"] >= case.DAWN_BEAT and g["stage"] in ("playing", "moving"):
        g["stage"] = "lost"
    return out


# ---------- talking to the people in the inn ----------

def _card(key: str) -> dict:
    c = case.public_card(key)
    c.pop("clues_total", None)
    return c


@app.post("/api/talks")
def new_talk(body: NewTalk, request: Request):
    """Start talking to someone, or pick up where the hero and that person left off."""
    vid = request.state.vid
    with db.session() as conn:
        g = _play(conn, vid, ("playing", "moving"))
        if body.npc not in case.BY_KEY:
            raise HTTPException(404, bi("There is nobody like that here.", "这里没有这个人。"))
        trust0, why = game.start_trust(body.npc)
        talk = db.find_talk(conn, vid, body.npc) or db.create_talk(conn, vid, body.npc, trust0)
        state = case.clue_state(body.npc, g["found"], talk["trust"])
    shown = [t for t in talk["turns"] if not t.get("hidden")][-40:]
    return {"id": talk["id"], "npc": _card(body.npc), "trust": talk["trust"], "impression": why, "turns": shown,
            "fresh": not talk["turns"], "told": len(state["told"]), "total": len(case.BY_KEY[body.npc]["topics"])}


VERIFY = ("You referee a story game. A character has just spoken to the hero. Below are the facts the character was willing to tell. "
          "Answer with a JSON array of the ids of facts whose KEY information the character clearly told the hero in this reply. A fact counts when its main "
          "content was stated, even in other words. Hints, deflections, questions, or only a vague part of it do not count. Answer [] if none. Output only the JSON array.")


def _credit(client, vid: str, key: str, g: dict, reply: str, trust: int) -> list[dict]:
    """Which clues did this reply actually tell? The server decides (not the model that played the person) and files them in the case file."""
    ready = case.clue_state(key, g["found"], trust)["ready"]
    if not ready or not reply.strip():
        return []
    facts = "\n".join(f"{cid}: {case.plain_fact(cid)}" for cid in ready)
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
            new.append(case.clue_view(cid))
    return new


def _npc_turn(client, tid: str, vid: str, message: str | None) -> Iterator[dict]:
    """One turn with a person. message=None means the hero has just walked up and they speak first."""
    opening = message is None
    line = "*approaches you* ||| *走上前来*" if opening else _bilingual_line(client, vid, message)
    if not opening:
        yield {"type": "user", "text": line}
    with db.session() as conn:
        g = _play(conn, vid, ("playing", "moving"))
        talk = db.get_talk(conn, tid, vid)
        if not talk:
            raise HTTPException(404, bi("That conversation has ended. Talk to them again.", "这段对话已结束，请重新交谈。"))
        key = talk["npc_key"]
        trust_before = talk["trust"]            # clues are offered at the trust the hero walked in with
        turn = agent.Turn()
        tools = game.npc_tools(talk, turn)
        messages = [{"role": "system", "content": prompts.npc_system(key)},
                    *agent.history(talk["turns"]),
                    {"role": "system", "content": prompts.npc_state(key, talk["trust"], g["found"], g["beat"], opening)},
                    {"role": "user", "content": bilingual.plain(line)}]
        try:
            for raw in agent.run(client, config.CHAT_MODEL, messages, tools, turn, vid, max_tokens=800):
                for ev in (_finish(client, vid, raw) if raw["type"] == "done" else [raw]):
                    if ev["type"] == "done":
                        talk["turns"] += [{"role": "user", "content": line, **({"hidden": True} if opening else {})},
                                          {"role": "assistant", "content": ev["text"] or "…"}]
                    yield ev
                    if ev["type"] == "done" and not opening:
                        for clue in _credit(client, vid, key, g, ev["text"], trust_before):
                            yield {"type": "clue", "clue": clue}
                        g["msgs"] += 1
                        if g["msgs"] % case.MSGS_PER_BEAT == 0:
                            yield from _advance(g, 1)
                            yield {"type": "clock", "clock": case.clock(g["beat"]), "stage": g["stage"]}
        finally:
            db.save_talk(conn, talk)
            db.save_play(conn, g)


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


# ---------- Ray, the game master ----------

def _gm_turn(client, vid: str, message: str) -> Iterator[dict]:
    line = _bilingual_line(client, vid, message)
    yield {"type": "user", "text": line}
    with db.session() as conn:
        g = _play(conn, vid)
        turn = agent.Turn()
        messages = [{"role": "system", "content": prompts.gm_system(g["found"], g["beat"])}, *agent.history(g["turns"]),
                    {"role": "user", "content": bilingual.plain(line)}]
        try:
            for raw in agent.run(client, config.CHAT_MODEL, messages, [], turn, vid, max_tokens=600):
                for ev in (_finish(client, vid, raw) if raw["type"] == "done" else [raw]):
                    if ev["type"] == "done":
                        g["turns"] += [{"role": "user", "content": line}, {"role": "assistant", "content": ev["text"] or "…"}]
                    yield ev
        finally:
            db.save_play(conn, g)


@app.post("/api/gm/chat")
def gm_chat(body: Message, request: Request):
    """Ask Ray what is going on, or for a nudge. This costs no time."""
    vid = request.state.vid
    with db.session() as conn:
        _play(conn, vid)
    client = llm()
    return sse(guarded(_gm_turn(client, vid, body.message)))


# ---------- the move ----------

@app.post("/api/move")
def make_move(body: Move, request: Request):
    """Try the escape with the clues she chooses. The verdict is decided here, from the clues she actually holds."""
    with db.session() as conn:
        g = _play(conn, request.state.vid, "playing")
        result = case.judge(body.evidence, g["found"])
        announcements = []
        if result["verdict"] == "go":
            g.update(stage="moving", tier=result["tier"])
        else:
            announcements = _advance(g, case.FAILED_MOVE_COST)
        db.save_play(conn, g)
        result.update(stage=g["stage"], clock=case.clock(g["beat"]), gm=announcements)
        if g["stage"] == "lost":
            result["game"] = _state(conn, g)
        return result


@app.post("/api/ending")
def ending(body: Fate, request: Request):
    """The last scene, written for the way she prepared and what she chose to do with the letter."""
    vid = request.state.vid
    if body.fate not in case.FATES:
        raise HTTPException(400, bi("Choose one of the three.", "请从三者中选一。"))
    with db.session() as conn:
        g = _play(conn, vid, "moving")
        tier = g["tier"]
    text = ""
    try:
        ratelimit.check(vid)
        client = llm()
        how = ["barely: she slipped out with little more than her life, knowing little of what she left behind",
               "well: she knew a good part of the truth or held some leverage, and brought a friend or two",
               "superbly: she knew the truth, held leverage over the keeper, and could take everyone worth saving with her"][tier]
        prompt = prompts.ENDING.format(truth=case.truth().replace(" ||| ", " / "), tier=how, fate=case.FATES[body.fate]["en"], format=bilingual.REPLY_FORMAT)
        r = client.chat.completions.create(model=config.CHAT_MODEL, max_tokens=900, extra_body={"thinking": {"type": "disabled"}},
                                           messages=[{"role": "system", "content": prompt}, {"role": "user", "content": "Write the final scene."}])
        text = bilingual.normalize(_MARKUP.sub("", (r.choices[0].message.content or "")).strip())
        if text and bilingual.SEP not in text:
            other = bilingual.counterpart(client, config.CHAT_MODEL, text, _names())
            if other:
                en, zh = (other, text) if bilingual.language_of(text) == "Chinese" else (text, other)
                text = f"{en}\n{bilingual.SEP}\n{zh}"
        if not bilingual.is_pair(text):
            text = ""
    except (RateLimited, HTTPException, openai.APIError) as e:
        print("Ending fell back to the written version:", repr(e))
    text = text or case.fallback_ending(body.fate, tier)
    with db.session() as conn:
        g = _play(conn, vid, "moving")
        g.update(stage="solved", ending=text)
        db.save_play(conn, g)
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
