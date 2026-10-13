"""人在江湖，身不由己 web server: the page, the game rules and the DeepSeek-powered characters and game master."""
import json
import random
import re
import secrets
import threading
import uuid
from typing import Iterator

import openai
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, config, db, geo, i18n, judge, prompts, ratelimit, rules, stats, story
from .i18n import tr
from .ratelimit import RateLimited

app = FastAPI(title="人在江湖，身不由己")
db.init()

_client: openai.OpenAI | None = None
_dice = random.SystemRandom()


def llm() -> openai.OpenAI:
    global _client
    if not config.DEEPSEEK_API_KEY:
        raise HTTPException(503, tr("The AI isn't configured on this server yet (DEEPSEEK_API_KEY is missing).", "此服务器尚未配置 AI（缺少 DEEPSEEK_API_KEY）。", "เซิร์ฟเวอร์นี้ยังไม่ได้ตั้งค่า AI (ไม่มี DEEPSEEK_API_KEY)"))
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
    request.state.fresh = fresh
    request.state.lang = i18n.valid(request.headers.get("x-lang"))
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


class Round(BaseModel):
    action: str = Field(pattern="^(strike|art|guard|counter)$")


def sse(events: Iterator[dict], lang: str = i18n.DEFAULT) -> StreamingResponse:
    def body():
        for ev in events:
            yield f"data: {json.dumps(i18n.localize(ev, lang), ensure_ascii=False)}\n\n"
    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _count_error(vid: str, kind: str) -> None:
    try:
        with db.session() as conn:
            db.log(conn, vid, "error", kind=kind)
    except Exception as e:  # counting must never break a reply
        print("Could not record an error:", repr(e))


def guarded(events: Iterator[dict], vid: str = "") -> Iterator[dict]:
    """Turn failures inside a stream into a final error event the page can show."""
    try:
        yield from events
    except RateLimited as e:
        _count_error(vid, "rate_limited")
        yield {"type": "error", "code": "rate_limited", "message": str(e)}
    except HTTPException as e:
        yield {"type": "error", "code": "bad_request", "message": str(e.detail)}
    except openai.APIError as e:
        _count_error(vid, "upstream")
        yield {"type": "error", "code": "upstream", "message": tr("The AI service didn't answer. Try again in a moment.", "AI 服务没有响应，请稍后再试。", "บริการ AI ไม่ตอบสนอง ลองใหม่อีกครั้งในอีกสักครู่")}
        print("DeepSeek error:", repr(e))


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    """Error messages are written once in all three languages; the page gets the one it asked for."""
    detail = i18n.localize(exc.detail, getattr(request.state, "lang", i18n.DEFAULT)) if isinstance(exc.detail, str) else exc.detail
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


def _L(request: Request, data):
    return i18n.localize(data, request.state.lang)


# ---------- the night: the state kept for each visitor ----------

def _fresh_state() -> dict:
    """A new thief: thirty points over three stats, and one martial art to attack with and one to defend with."""
    stats_ = rules.roll_stats(_dice)
    hp = rules.max_hp(stats_)
    return {"v": db.STATE_VERSION, "hero": {**stats_, "qi": rules.start_qi(stats_), "hp": hp, "hp_max": hp, "off": _dice.choice(rules.OFFENCE), "defn": _dice.choice(rules.DEFENCE)},
            "tick": 0, "rounds": 0, "rests": 0, "intent": "quick", "fights": 0, "shortcut": 0, "edges": {}, "fight": None, "killer": "", "feed": [], "log": [],
            "npcs": {c["key"]: {"status": "away", "hp": c["hp"], "trust": c["start_trust"], "arrived": -1, "rewarded": False, "talks": 0, "ambush": False} for c in story.CAST}}


def _exit_at(st: dict) -> int:
    return max(story.SHORTEST, story.STORM_END - st["shortcut"])


def _say(st: dict, kind: str, text: str, plain: str = "", npc: str = "") -> dict:
    """One line in the night's story, shown to the player in her language, and kept in plain English for Ray's ending."""
    item = {"kind": kind, "text": text, "tick": st["tick"], "npc": npc}
    st["feed"] = (st["feed"] + [item])[-40:]
    if plain:
        st["log"] = (st["log"] + [f"[beat {st['tick']}] {plain}"])[-40:]
    return {"type": "feed", "item": item}


def _name(key: str) -> str:
    return i18n.plain(story.BY_KEY[key]["name"])


def _arrive(st: dict) -> list[dict]:
    out = []
    for c in story.CAST:
        n = st["npcs"][c["key"]]
        if n["status"] == "away" and c["arrive"] <= st["tick"]:
            n.update(status="here", arrived=st["tick"])
            out.append(_say(st, "arrival", c["arrival"], f"{_name(c['key'])} ({i18n.plain(c['title'])}) arrived.", c["key"]))
    return out


def _turn_hostile(st: dict, key: str, ambush: bool = True) -> None:
    """They are going to fight her. Unless she started it, they get the first blow."""
    st["npcs"][key].update(status="hostile", ambush=ambush)


def _fuses(st: dict) -> None:
    """The righteous and the law do not wait for ever; and anybody whose trust is gone turns on her."""
    for c in story.CAST:
        n = st["npcs"][c["key"]]
        if n["status"] == "here":
            if c.get("fuse") and st["tick"] - n["arrived"] >= c["fuse"]:
                _turn_hostile(st, c["key"])
            elif n["trust"] <= 0:
                _turn_hostile(st, c["key"])


def _start_fight_if_needed(st: dict) -> list[dict]:
    if st["fight"]:
        return []
    for c in story.CAST:
        n = st["npcs"][c["key"]]
        if n["status"] == "hostile":
            return _begin_fight(st, c["key"], n.get("ambush", False))
    return []


def _begin_fight(st: dict, key: str, ambush: bool = False) -> list[dict]:
    n, c = st["npcs"][key], story.BY_KEY[key]
    n["status"] = "fighting"
    st["fight"], st["rounds"] = key, 0
    st["fights"] += 1
    st["intent"] = rules.pick_intent(_dice)
    out = [_say(st, "fight", c["hostile"], f"{_name(key)} attacked her.", key), {"type": "fight", "npc": key}]
    if ambush:
        foe = {"hp": n["hp"], "atk": c["atk"], "defn": c["defn"], "dmg": c["dmg"]}
        hit = rules.ambush(st["hero"], foe, _dice)
        out.append(_say(st, "fight", tr("They strike first, before you are ready!", "他抢先出手，你措手不及！", "เขาลงมือก่อนก่อนที่เจ้าจะทันตั้งตัว!"),
                        f"{_name(key)} got the first blow in ({hit['damage']} damage)." if hit["hit"] else f"{_name(key)} struck first but missed.", key))
        out.append({"type": "ambush", "result": hit})
    return out


def _storm_check(st: dict) -> list[dict]:
    if st["tick"] >= _exit_at(st) and not st.get("storm_said"):
        st["storm_said"] = True
        return [_say(st, "storm", tr("The wind drops. The storm is passing, and the door can be opened. You can leave now.", "风小了，沙暴正在过去，大门可以打开了。你现在可以走了。", "ลมสงบ พายุกำลังผ่านไป ประตูเปิดได้แล้ว เจ้าออกไปได้เลย"), "The storm passed; she could leave.", "")]
    return []


def _advance(st: dict, beats: int = 1) -> list[dict]:
    """Let the night go on. People arrive, patience runs out, and anyone out of patience attacks."""
    out = []
    for _ in range(beats):
        st["tick"] += 1
        out += _arrive(st)
        _fuses(st)
    return out + _storm_check(st) + _start_fight_if_needed(st)


def _apply_reward(st: dict, key: str, how: str) -> list[dict]:
    """What a person gives, once they trust her or once she has beaten them. The server decides it, never the model."""
    n, c = st["npcs"][key], story.BY_KEY[key]
    if n["rewarded"]:
        return []
    n["rewarded"] = True
    e, hero = c["reward"]["effect"], st["hero"]
    if e["kind"] == "heal":
        hero["hp"] = min(hero["hp_max"], hero["hp"] + e["n"])
    elif e["kind"] == "edge":
        st["edges"][e["target"]] = st["edges"].get(e["target"], 0) + e["n"]
    elif e["kind"] == "shortcut":
        st["shortcut"] += e["n"]
    return [_say(st, "gain", c["reward"]["gain"], f"{_name(key)} gave her something ({how}): {c['reward']['fact']}", key)]


def _finish(g: dict, stage: str, cause: str) -> None:
    g.update(stage=stage, cause=cause)


# ---------- the state the page needs ----------

def _look(art: str) -> dict:
    return {"key": art, "name": story.ARTS[art]["name"], "does": story.ARTS[art]["does"]}


def _state(g: dict) -> dict:
    st = g["state"]
    h = st["hero"]
    npcs = []
    for c in story.CAST:
        n = st["npcs"][c["key"]]
        if n["status"] == "away":
            continue
        fuse_left = max(0, c["fuse"] - (st["tick"] - n["arrived"])) if c.get("fuse") and n["status"] == "here" else None
        npcs.append({**story.public_card(c["key"]), "goal": c["goal"], "talks": n["talks"], "talk_limit": c["talk_limit"], "status": n["status"], "hp": n["hp"], "hp_max": c["hp"], "trust": n["trust"], "rewarded": n["rewarded"],
                     "fuse_left": fuse_left, "goal_trust": c["reward"]["trust"]})
    away = [c["arrive"] for c in story.CAST if st["npcs"][c["key"]]["status"] == "away"]
    fight = None
    if st["fight"]:
        c, n = story.BY_KEY[st["fight"]], st["npcs"][st["fight"]]
        fight = {"npc": st["fight"], "hp": n["hp"], "hp_max": c["hp"], "edge": story.edge_for(st["edges"], st["fight"]), "intent": st["intent"]}
    over = g["stage"] in ("solved", "dead")
    return {"stage": g["stage"], "hero": {**story.hero_card(), "str": h["str"], "int": h["int"], "agi": h["agi"], "hp": h["hp"], "hp_max": h["hp_max"], "qi": h["qi"], "qi_max": rules.QI_MAX, "rests_left": rules.REST_MAX - st.get("rests", 0), "rest_heal": rules.rest_heal(h), "rest_beats": rules.REST_BEATS,
                                          "off": _look(h["off"]), "defn": _look(h["defn"]), "defence_bonus": rules.defence_bonus(h)},
            "tick": st["tick"], "storm_end": story.STORM_END, "exit_at": _exit_at(st), "can_leave": st["tick"] >= _exit_at(st), "npcs": npcs,
            "incoming": len(away), "next_in": (min(away) - st["tick"]) if away else None, "fight": fight, "edges": st["edges"], "feed": st["feed"][-30:],
            "ending_key": g["cause"] if over else "", "won": g["stage"] == "solved", "ending": g["ending"], "killer": st["killer"], "gm_turns": g["turns"][-12:]}


# ---------- read-only ----------

@app.get("/api/status")
def status():
    return {"ai": bool(config.DEEPSEEK_API_KEY)}


@app.get("/api/case")
def get_case(request: Request):
    """What the home page shows before anyone has started: the setting, the goal, the rules, the people, the game master."""
    with db.session() as conn:
        ref = re.sub(r"^https?://([^/:]+).*$", r"\1", request.headers.get("x-ref", "")).lower()[:60]
        if ref == request.url.hostname:
            ref = ""
        db.log(conn, request.state.vid, "visit", returning=not request.state.fresh, lang=request.state.lang,
               country=geo.country(geo.client_ip(request.headers, request.client.host if request.client else "")),
               device=geo.device(request.headers.get("user-agent", "")), ref=ref)
    return _L(request, {"title": story.TITLE, "setup": story.SETUP, "goal": story.GOAL, "how_to": story.HOW_TO, "prologue": story.PROLOGUE,
                        "cast": [story.public_card(c["key"]) for c in story.CAST], "gm": story.gm_card(), "moods": story.MOODS, "notes": story.NOTES,
                        "stats": story.STATS, "arts": story.ARTS, "storm_end": story.STORM_END,
                        "endings": {k: {"title": v["title"], "won": v["won"]} for k, v in story.ENDINGS.items()}})


def _play(conn, vid: str, stage: str | tuple | None = None) -> dict:
    g = db.get_play(conn, vid)
    if not g:
        raise HTTPException(409, tr("Start the story first.", "请先开始故事。", "เริ่มเรื่องก่อนนะ"))
    if stage and g["stage"] not in ((stage,) if isinstance(stage, str) else stage):
        raise HTTPException(409, tr("That isn't possible at this point in the story.", "故事此刻不能这样做。", "ในตอนนี้ของเรื่อง ทำแบบนั้นไม่ได้"))
    return g


@app.get("/api/game")
def get_game(request: Request):
    with db.session() as conn:
        g = db.get_play(conn, request.state.vid)
        return _L(request, {"game": _state(g) if g else None})


@app.post("/api/roll")
def roll(request: Request):
    """Roll a thief: thirty points over Strength, Intelligence and Agility, and two martial arts. As many rolls as she likes before the night starts."""
    with db.session() as conn:
        g = db.get_play(conn, request.state.vid)
        if g and g["stage"] == "playing":
            raise HTTPException(409, tr("The night has already begun. Start over from the menu to roll again.", "夜晚已经开始。要重新掷骰，请在菜单里重新开始。", "ค่ำคืนเริ่มแล้ว ถ้าอยากทอยใหม่ให้เริ่มใหม่จากเมนู"))
        g = db.new_play(conn, request.state.vid, _fresh_state(), "rolling")
        db.log(conn, request.state.vid, "roll", lang=request.state.lang)
        return _L(request, {"game": _state(g)})


@app.post("/api/game/start")
def start_game(request: Request):
    """The night begins with the thief she rolled, and the door still banging."""
    with db.session() as conn:
        g = db.get_play(conn, request.state.vid)
        if not g or g["stage"] != "rolling":
            g = db.new_play(conn, request.state.vid, _fresh_state(), "rolling")
        st = g["state"]
        g["stage"] = "playing"
        _say(st, "start", story.START_LINE, "She was hiding in the Black Sand Inn with a stolen jade seal while a sandstorm closed the road.")
        _arrive(st)
        db.save_play(conn, g)
        h = st["hero"]
        db.log(conn, request.state.vid, "start", lang=request.state.lang, str=h["str"], int=h["int"], agi=h["agi"], off=h["off"], defn=h["defn"])
        return _L(request, {"game": _state(g)})


@app.post("/api/game/reset")
def reset_game(request: Request):
    with db.session() as conn:
        db.delete_play(conn, request.state.vid)
    return {"ok": True}


# ---------- language helpers ----------

def _typed(message: str) -> str:
    """What the player typed. The separator is ours, so a player cannot use it to inject another language into the log."""
    return message.replace(i18n.SEP, "|").strip()


THREAT = re.compile(r"\b(?:kill|murder|stab|slit|slice|gut|strangle|cut you|cut your throat|run you through|end you|hurt you|harm you|break your|draw my (?:saber|blade|sword|knife)|fight me|i(?:'ll| will) fight)\b|杀了你|宰了你|砍了你|砍你|拔刀|一刀捅|要你的命|让你死|来打|打一架|ฆ่าเจ้า|ฆ่าเธอ|ฆ่าแก|ฆ่าท่าน|ฟันเจ้า|ฟันแก|ฟันท่าน|แทงเจ้า|แทงแก|ชักดาบ|ชักมีด|สู้กัน|มาสู้", re.I)

WATCH = ("You judge one message in a wuxia survival game. The hero, Yan Qi, a thief, has just said something to a character. "
         "Answer with one JSON object: {\"threat\": true|false, \"trust\": n}. "
         "\"threat\" is true only if she PLAINLY says she will hurt, kill or fight them, or draws a weapon. Insults, rude names, anger and contempt are NOT threats. "
         "\"trust\" is how the message changes this character's trust in her, from -2 to 2: +1 for sincere honesty, respect, a believable reason, a gift or humour that fits what the character values "
         "(it should usually move up when she is genuinely good company), +2 only for something that truly moves them, 0 for plain questions or small talk, "
         "-1 for rudeness, pressure or a clumsy lie, -2 for insults, threats or a lie caught. Output only the JSON object.\n"
         "The character: {who}. What earns their trust: {earns}")


def _watch(client, vid: str, key: str, text: str) -> dict:
    """Read her own words before the person answers: does it threaten them, and how does it change their trust?
    A plain check, so neither an insult nor a kindness is left to the roleplaying model's whim."""
    c = story.BY_KEY[key]
    threat, delta = bool(THREAT.search(text)), 0
    try:
        ratelimit.check(vid)
        system = WATCH.replace("{who}", f"{i18n.plain(c['name'])}, {i18n.plain(c['title'])}").replace("{earns}", c["calms"])
        r = client.chat.completions.create(model=config.CHAT_MODEL, max_tokens=60, temperature=0, extra_body={"thinking": {"type": "disabled"}},
                                           messages=[{"role": "system", "content": system}, {"role": "user", "content": text}])
        obj = json.loads(re.search(r"\{.*\}", r.choices[0].message.content or "", re.S).group(0))
        threat = threat or obj.get("threat") is True
        delta = max(-2, min(2, round(float(obj.get("trust", 0)))))
    except (RateLimited, AttributeError, ValueError, TypeError, openai.APIError) as e:
        print("Message check skipped:", repr(e))
    return {"threat": threat, "delta": delta}


# ---------- the AI judge: scores a sample of real replies in the background ----------

_judge_threads: list[threading.Thread] = []      # kept so the tests can wait for the judge


def _maybe_judge(vid: str, key: str, lang: str, reply: str, player: str, trust: int, left: int, locked_fact: str, talk_id: str, turn: int) -> None:
    if not reply or _dice.random() >= config.JUDGE_SAMPLE_RATE:
        return

    def work() -> None:
        try:
            ratelimit.check(vid)
            s = judge.score_reply(llm(), key, lang, reply, player, trust, left, locked_fact)
            if s:
                with db.session() as conn:
                    db.log(conn, vid, "judge", npc=key, lang=lang, talk=talk_id, turn=turn, leaked=s["leaked"], overall=s["overall"], **{d: s[d] for d in judge.DIMS})
        except Exception as e:   # scoring must never disturb a player
            print("Judge skipped:", repr(e))
    t = threading.Thread(target=work, daemon=True)
    _judge_threads[:] = [x for x in _judge_threads if x.is_alive()][-20:] + [t]
    t.start()


# ---------- talking to the people in the inn ----------

@app.post("/api/talks")
def new_talk(body: NewTalk, request: Request):
    """Start talking to someone, or pick up where the hero and that person left off."""
    vid = request.state.vid
    with db.session() as conn:
        g = _play(conn, vid, "playing")
        st = g["state"]
        if body.npc not in story.BY_KEY or st["npcs"][body.npc]["status"] == "away":
            raise HTTPException(404, tr("There is nobody like that here.", "这里没有这个人。", "ที่นี่ไม่มีคนแบบนั้น"))
        n = st["npcs"][body.npc]
        talk = db.find_talk(conn, vid, body.npc)
        if not talk:
            talk = db.create_talk(conn, vid, body.npc, n["trust"])
            db.log(conn, vid, "talk", npc=body.npc)
    shown = [{**t, "i": i} for i, t in enumerate(talk["turns"]) if not t.get("hidden")][-40:]       # i: the reply's place in the conversation, for feedback
    return _L(request, {"id": talk["id"], "npc": story.public_card(body.npc), "trust": n["trust"], "status": n["status"], "turns": shown,
                        "fresh": not talk["turns"], "game": _state(g)})


def _npc_turn(client, tid: str, vid: str, message: str | None, lang: str = i18n.DEFAULT) -> Iterator[dict]:
    """One turn with a person. message=None means the hero has just walked up and they speak first."""
    opening = message is None
    line = "*approaches you*" if opening else _typed(message)
    if not opening:
        yield {"type": "user", "text": line}
    with db.session() as conn:
        g = _play(conn, vid, "playing")
        st = g["state"]
        talk = db.get_talk(conn, tid, vid)
        if not talk:
            raise HTTPException(404, tr("That conversation has ended. Talk to them again.", "这段对话已结束，请重新交谈。", "บทสนทนานั้นจบแล้ว ลองคุยกับเขาอีกครั้ง"))
        key = talk["npc_key"]
        n, c = st["npcs"][key], story.BY_KEY[key]
        if st["fight"]:
            raise HTTPException(409, tr("You are in a fight. Finish it first.", "你正在打斗中，先把它了结。", "เจ้ากำลังสู้อยู่ สู้ให้จบก่อน"))
        if n["rewarded"]:
            raise HTTPException(409, tr("They have nothing more to say to you.", "他已经没什么好对你说的了。", "เขาไม่มีอะไรจะพูดกับเจ้าอีกแล้ว"))
        if n["status"] not in ("here", "calm"):
            raise HTTPException(409, tr("They are in no state to talk.", "他已经没法和你交谈了。", "เขาอยู่ในสภาพที่คุยไม่ได้แล้ว"))
        seen = _watch(client, vid, key, line) if not opening else {"threat": False, "delta": 0}
        n["trust"] = max(0, min(10, n["trust"] + seen["delta"]))
        talk["trust"] = n["trust"]
        if seen["delta"]:
            yield {"type": "trust", "trust": n["trust"], "delta": seen["delta"]}
        fact_now = ""
        if not opening:
            db.log(conn, vid, "msg", npc=key, delta=seen["delta"], threat=seen["threat"], trust=n["trust"])
            if n["status"] == "here" and c["mood"] != "friendly" and c.get("calm") and n["trust"] >= c["calm"]:
                n["status"] = "calm"
                yield _say(st, "calm", tr(f"{i18n.plain(c['name'])} lowers their guard and stands down.", f"{i18n.plain(c['name'])} 放下了戒备，不再动手。", f"{i18n.plain(c['name'])} ผ่อนท่าทีลง ไม่คิดจะลงมือแล้ว"), f"{_name(key)} was talked down and stood down.", key)
            if not n["rewarded"] and n["trust"] >= c["reward"]["trust"]:
                fact_now = c["reward"]["fact"]
                yield from _apply_reward(st, key, "by talking")
                yield from _storm_check(st)
        messages = [{"role": "system", "content": prompts.npc_system(key)}, *agent.history(talk["turns"]),
                    {"role": "system", "content": prompts.npc_state(key, n["trust"], st["tick"], fact_now, opening, lang, max(0, c["talk_limit"] - n["talks"] - (0 if opening else 1)), c["reward"]["trust"], c["goal"],
                                                                         [(o["key"], st["npcs"][o["key"]]["status"] == "down") for o in story.CAST if o["key"] != key and st["npcs"][o["key"]]["status"] != "away"])},
                    {"role": "user", "content": line}]
        if seen["threat"] and c["mood"] != "friendly":
            messages.insert(-1, {"role": "system", "content": "The hero just threatened you. Answer with cold anger: you are about to attack her."})
        try:
            for raw in agent.run(client, config.CHAT_MODEL, messages, [], agent.Turn(), vid, max_tokens=500):
                ev = {"type": "done", "text": i18n.clean_ai(raw["text"], lang)} if raw["type"] == "done" else raw
                if ev["type"] == "done":
                    talk["turns"] += [{"role": "user", "content": line, **({"hidden": True} if opening else {})},
                                      {"role": "assistant", "content": ev["text"] or "…"}]
                yield ev
                if ev["type"] == "done":
                    yield {"type": "turn", "i": len(talk["turns"]) - 1}                      # which reply this was, so the page can ask what the player thought of it
                    _maybe_judge(vid, key, lang, ev["text"], "" if opening else line, n["trust"], max(0, c["talk_limit"] - n["talks"] - (0 if opening else 1)),
                                 "" if (n["rewarded"] or fact_now) else c["reward"]["fact"], talk["id"], len(talk["turns"]) - 1)
                    if not opening:
                        g["msgs"] += 1
                        n["talks"] += 1
                        if seen["threat"] and c["mood"] != "friendly":
                            _turn_hostile(st, key, ambush=False)                 # she provoked it
                        elif n["trust"] <= 0:
                            _turn_hostile(st, key)
                        elif n["rewarded"]:
                            yield {"type": "resolved", "npc": key}
                        elif n["talks"] >= c["talk_limit"]:
                            _turn_hostile(st, key)                               # the talk ran out without winning them: they strike first
                            yield _say(st, "fight", tr(f"{i18n.plain(c['name'])} has heard enough. The talking is over.", f"{i18n.plain(c['name'])} 听够了，没什么好谈的了。", f"{i18n.plain(c['name'])} ฟังพอแล้ว การเจรจาจบลง"), f"Talking to {_name(key)} failed.", key)
                        yield from _advance(st, 1)
        finally:
            db.save_talk(conn, talk)
            db.save_play(conn, g)
        yield {"type": "state", "game": _state(g)}


def _own_talk(tid: str, vid: str) -> dict:
    with db.session() as conn:
        talk = db.get_talk(conn, tid, vid)
    if not talk:
        raise HTTPException(404, tr("That conversation has ended. Talk to them again.", "这段对话已结束，请重新交谈。", "บทสนทนานั้นจบแล้ว ลองคุยกับเขาอีกครั้ง"))
    return talk


@app.post("/api/talks/{tid}/open")
def npc_open(tid: str, request: Request):
    """The person speaks first, to this particular hero."""
    vid = request.state.vid
    if _own_talk(tid, vid)["turns"]:
        raise HTTPException(409, tr("This conversation has already begun.", "这段对话已经开始。", "บทสนทนานี้เริ่มไปแล้ว"))
    client = llm()
    return sse(guarded(_npc_turn(client, tid, vid, None, request.state.lang), vid), request.state.lang)


@app.post("/api/talks/{tid}/chat")
def npc_chat(tid: str, body: Message, request: Request):
    vid = request.state.vid
    _own_talk(tid, vid)
    client = llm()
    return sse(guarded(_npc_turn(client, tid, vid, body.message, request.state.lang), vid), request.state.lang)


# ---------- fighting ----------

@app.post("/api/fight/start")
def fight_start(body: NewTalk, request: Request):
    """Pick a fight with someone in the inn (or finish what they started)."""
    with db.session() as conn:
        g = _play(conn, request.state.vid, "playing")
        st = g["state"]
        if st["fight"]:
            raise HTTPException(409, tr("You are already in a fight.", "你已经在打斗中了。", "เจ้ากำลังสู้อยู่แล้ว"))
        n = st["npcs"].get(body.npc)
        if not n or n["status"] not in ("here", "calm"):
            raise HTTPException(404, tr("There is nobody like that here.", "这里没有这个人。", "ที่นี่ไม่มีคนแบบนั้น"))
        events = _begin_fight(st, body.npc)
        db.log(conn, request.state.vid, "fight", npc=body.npc, chosen=True)
        db.save_play(conn, g)
        return _L(request, {"events": events, "game": _state(g)})


@app.post("/api/fight/round")
def fight_round(body: Round, request: Request):
    """One round: she acts, then they do. Two dice for every attack and every defence, resolved by rules.py, never by the AI."""
    vid = request.state.vid
    with db.session() as conn:
        g = _play(conn, vid, "playing")
        st = g["state"]
        key = st["fight"]
        if not key:
            raise HTTPException(409, tr("You are not in a fight.", "你现在没有在打斗。", "เจ้าไม่ได้อยู่ในการต่อสู้"))
        c, n, hero = story.BY_KEY[key], st["npcs"][key], st["hero"]
        if body.action == "art" and hero["qi"] < 1:
            raise HTTPException(409, tr("You are out of breath for your art. Guard to recover.", "你气息不足，无法施展武功。先防守调息。", "เจ้าหมดลมหายใจสำหรับวิชายุทธ์ ตั้งรับเพื่อเรียกลมปราณคืน"))
        foe = {"hp": n["hp"], "atk": c["atk"], "defn": c["defn"], "dmg": c["dmg"]}
        result = rules.fight_round(hero, foe, body.action, _dice, story.edge_for(st["edges"], key), st["intent"])
        n["hp"] = foe["hp"]
        st["rounds"] += 1
        events: list[dict] = []
        if hero["hp"] <= 0:
            st["killer"] = key
            st["fight"] = None
            events.append(_say(st, "death", tr(f"{i18n.plain(c['name'])} wins the fight.", f"{i18n.plain(c['name'])} 赢了这场打斗。", f"{i18n.plain(c['name'])} ชนะการต่อสู้"), f"{_name(key)} beat her in a fight and she fell.", key))
            _finish(g, "dead", "arrested" if c["mood"] == "police" else "slain")
        elif foe["hp"] <= 0:
            n["status"] = "down"
            st["fight"] = None
            events.append(_say(st, "win", c["down"], f"She beat {_name(key)} in a fight.", key))
            events += _apply_reward(st, key, "by force")
            events += _storm_check(st) + _start_fight_if_needed(st)
        else:
            st["intent"] = rules.pick_intent(_dice)
            if st["rounds"] % 2 == 0:
                events += _advance(st, 1)
        db.log(conn, vid, "round", npc=key, action=body.action, hp=hero["hp"], foe=foe["hp"])
        db.save_play(conn, g)
        return _L(request, {"round": result, "events": events, "game": _state(g)})


# ---------- resting ----------

@app.post("/api/rest")
def rest(request: Request):
    """Catch her breath in the inn: it costs beats, so people keep arriving and losing patience while she does. If someone attacks during it, she only gets half."""
    vid = request.state.vid
    with db.session() as conn:
        g = _play(conn, vid, "playing")
        st = g["state"]
        h = st["hero"]
        if st["fight"]:
            raise HTTPException(409, tr("You can't rest in the middle of a fight.", "打斗中不能休息。", "กลางการต่อสู้พักไม่ได้"))
        if st.get("rests", 0) >= rules.REST_MAX:
            raise HTTPException(409, tr("You have rested as much as the night allows.", "这一夜能休息的次数用完了。", "คืนนี้เจ้าพักได้เท่านี้แล้ว"))
        if h["hp"] >= h["hp_max"]:
            raise HTTPException(409, tr("You are not hurt.", "你没有受伤。", "เจ้าไม่ได้บาดเจ็บ"))
        st["rests"] = st.get("rests", 0) + 1
        events = [_say(st, "rest", tr("You find a dark corner and close your eyes for a moment.", "你找了个暗角，闭目调息片刻。", "เจ้าหามุมมืดแล้วหลับตาพักชั่วครู่"), "She rested in a corner of the hall.")]
        events += _advance(st, rules.REST_BEATS)
        gain = rules.rest_heal(h) // (2 if st["fight"] else 1)             # an interrupted rest is only half as good
        before = h["hp"]
        h["hp"] = min(h["hp_max"], h["hp"] + gain)
        events.append({"type": "rested", "healed": h["hp"] - before, "interrupted": bool(st["fight"])})
        db.log(conn, vid, "rest", healed=h["hp"] - before, interrupted=bool(st["fight"]))
        db.save_play(conn, g)
        return _L(request, {"events": events, "game": _state(g)})


# ---------- Ray, the game master ----------

def _snapshot(g: dict) -> str:
    """Where things stand, in plain English, for Ray. Rewards nobody has earned yet are never in here."""
    st = g["state"]
    lines = [f"Beat {st['tick']}. She can leave at beat {_exit_at(st)}. Her hit points: {st['hero']['hp']}/{st['hero']['hp_max']}. She can rest {rules.REST_MAX - st.get('rests', 0)} more time(s) (each rest takes {rules.REST_BEATS} beats and heals {rules.rest_heal(st['hero'])})."]
    for c in story.CAST:
        n = st["npcs"][c["key"]]
        if n["status"] == "away":
            continue
        lines.append(f"- {i18n.plain(c['name'])} ({i18n.plain(c['title'])}; {c['mood']}; {i18n.plain(c['public'])}): {n['status']}, trust {n['trust']}/10, hit points {n['hp']}/{c['hp']}"
                     + (f", calms at trust {c['calm']}" if c.get('calm') and n["status"] == "here" else ""))
    if st["fight"]:
        lines.append(f"She is fighting {_name(st['fight'])} right now.")
    lines.append(f"Advantages she has learned: {st['edges'] or 'none'}; beats saved by shortcuts: {st['shortcut']}.")
    lines.append(f"{len([c for c in story.CAST if st['npcs'][c['key']]['status'] == 'away'])} more people may still arrive.")
    return "\n".join(lines)


def _gm_turn(client, vid: str, message: str, lang: str = i18n.DEFAULT) -> Iterator[dict]:
    line = _typed(message)
    yield {"type": "user", "text": line}
    with db.session() as conn:
        g = _play(conn, vid)
        db.log(conn, vid, "gm")
        messages = [{"role": "system", "content": prompts.gm_system(_snapshot(g), g["state"]["hero"], _exit_at(g["state"]), lang)}, *agent.history(g["turns"]),
                    {"role": "user", "content": line}]
        try:
            for raw in agent.run(client, config.CHAT_MODEL, messages, [], agent.Turn(), vid, max_tokens=500):
                ev = {"type": "done", "text": i18n.clean_ai(raw["text"], lang)} if raw["type"] == "done" else raw
                if ev["type"] == "done":
                    g["turns"] += [{"role": "user", "content": line}, {"role": "assistant", "content": ev["text"] or "…"}]
                yield ev
        finally:
            db.save_play(conn, g)


@app.post("/api/gm/chat")
def gm_chat(body: Message, request: Request):
    """Ask Ray what is going on, how the rules work, or for a nudge. This costs no time."""
    vid = request.state.vid
    with db.session() as conn:
        _play(conn, vid)
    client = llm()
    return sse(guarded(_gm_turn(client, vid, body.message, request.state.lang), vid), request.state.lang)


# ---------- leaving, and how it ends ----------

@app.post("/api/leave")
def leave(request: Request):
    """Walk out of the door. After the storm passes that wins; before it, the desert takes her."""
    with db.session() as conn:
        g = _play(conn, request.state.vid, "playing")
        st = g["state"]
        if st["fight"]:
            raise HTTPException(409, tr("You can't walk out in the middle of a fight.", "打斗中不能走出去。", "กลางการต่อสู้เดินออกไปไม่ได้"))
        if st["tick"] >= _exit_at(st):
            _say(st, "leave", tr("You open the door and walk out into the clear morning.", "你推开门，走进清晨的光里。", "เจ้าเปิดประตูเดินออกไปสู่เช้าอันแจ่มใส"), "She walked out of the inn after the storm and was free.")
            _finish(g, "solved", "escaped")
        else:
            _say(st, "leave", tr("You open the door into the storm.", "你推开门，走进了沙暴。", "เจ้าเปิดประตูเข้าไปในพายุ"), "She went out into the storm too early.")
            _finish(g, "dead", "storm")
        db.save_play(conn, g)
        return _L(request, {"game": _state(g)})


@app.post("/api/ending")
def ending(request: Request):
    """Ray's telling of how the night ended, built from what really happened in it."""
    vid, lang = request.state.vid, request.state.lang
    with db.session() as conn:
        g = _play(conn, vid, ("solved", "dead"))
        if g["ending"]:
            return _L(request, {"game": _state(g)})
        key, log = g["cause"], "\n".join(g["state"]["log"])
        outcome = {"escaped": "She survived the storm and walked out, free.", "slain": "She lost a fight and was killed.",
                   "arrested": "She lost a fight to the law and was taken away in chains to hang.", "storm": "She left too early and was swallowed by the storm."}[key]
    text = ""
    try:
        ratelimit.check(vid)
        client = llm()
        prompt = prompts.ENDING.format(outcome=outcome, log=log or "(little happened)", names=story.names_line(), format=i18n.reply_rule(lang))
        r = client.chat.completions.create(model=config.CHAT_MODEL, max_tokens=900, extra_body={"thinking": {"type": "disabled"}},
                                           messages=[{"role": "system", "content": prompt}, {"role": "user", "content": "Tell the ending."}])
        text = i18n.clean_ai(r.choices[0].message.content or "", lang)
        if not i18n.in_language(text, lang) or len(text) < 120:
            text = ""
    except (RateLimited, HTTPException, openai.APIError) as e:
        print("Ending fell back to the written version:", repr(e))
    with db.session() as conn:
        g = _play(conn, vid, ("solved", "dead"))
        g["ending"] = text or i18n.pick(story.ENDINGS[key]["fallback"], lang)
        db.save_play(conn, g)
        return _L(request, {"game": _state(g)})


class Feedback(BaseModel):
    talk: str = Field(max_length=40)
    turn: int = Field(ge=0, le=1000)
    rating: str = Field(pattern="^(up|down)$")


@app.post("/api/feedback")
def feedback(body: Feedback, request: Request):
    """A thumb on one of a character's replies, so bad answers can be found later."""
    vid = request.state.vid
    with db.session() as conn:
        talk = db.get_talk(conn, body.talk, vid)
        if not talk or body.turn >= len(talk["turns"]) or talk["turns"][body.turn]["role"] != "assistant":
            raise HTTPException(404, tr("That reply isn't here any more.", "找不到这句回复。", "ไม่พบคำตอบนั้นแล้ว"))
        db.log(conn, vid, "feedback", talk=body.talk, turn=body.turn, rating=body.rating, npc=talk["npc_key"])
    return {"ok": True}


# ---------- the admin: who came, what they did, what the characters said ----------

def require_admin(request: Request) -> None:
    if not config.ADMIN_PASSWORD:
        raise HTTPException(404, "Admin is switched off. Set ADMIN_PASSWORD to enable it.")
    given = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not secrets.compare_digest(given.encode(), config.ADMIN_PASSWORD.encode()):
        raise HTTPException(401, "Wrong password.")


@app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats(days: int = 14):
    with db.session() as conn:
        return stats.summary(conn, max(1, min(days, 365)))


@app.get("/api/admin/transcripts", dependencies=[Depends(require_admin)])
def admin_transcripts(limit: int = 40, only_down: bool = False):
    with db.session() as conn:
        return {"talks": stats.transcripts(conn, max(1, min(limit, 200)), only_down)}


@app.get("/", include_in_schema=False)
def index():
    """The page, with each script and stylesheet stamped with a version so a browser can never mix old and new files."""
    static = config.ROOT / "static"
    version = str(int(max(p.stat().st_mtime for p in static.iterdir() if p.is_file())))
    html = (static / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'(src|href)="(/[\w.-]+\.(?:js|css))"', lambda m: f'{m.group(1)}="{m.group(2)}?v={version}"', html)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")
