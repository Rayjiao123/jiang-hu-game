"""What visitors did, and what the characters said to them, for the admin page.

Events hold counts only (never message text). Transcripts are read from the conversations themselves."""
import hashlib
import json
import time
from collections import Counter, defaultdict

from . import i18n, story


def _who(visitor_id: str) -> str:
    """A short stable label, so the admin can follow one visitor without seeing their cookie."""
    return hashlib.sha256(visitor_id.encode()).hexdigest()[:6]


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _events(conn, kind: str | None = None, since: float = 0) -> list[dict]:
    q, args = "SELECT ts, visitor_id, kind, data FROM events WHERE ts >= ?", [since]
    if kind:
        q += " AND kind = ?"
        args.append(kind)
    return [{"ts": r["ts"], "vid": r["visitor_id"], "kind": r["kind"], "data": json.loads(r["data"] or "{}")} for r in conn.execute(q + " ORDER BY ts", args)]


def summary(conn, days: int = 14) -> dict:
    since = time.time() - days * 86400
    ev = _events(conn, since=since)
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for e in ev:
        by_kind[e["kind"]].append(e)
    uniq = lambda kind: len({e["vid"] for e in by_kind[kind]})

    visits = by_kind["visit"]
    funnel = [("Opened the page", uniq("visit")), ("Rolled a thief", uniq("roll")), ("Started a night", uniq("start")), ("Talked to someone", uniq("talk")),
              ("Fought someone", uniq("round")), ("Reached an ending", uniq("end"))]

    ends = by_kind["end"]
    endings = Counter(e["data"].get("ending", "?") for e in ends)
    causes = Counter(e["data"].get("killer", "") for e in ends if not e["data"].get("won"))

    # how long a finished night took: from the visitor's last start before the end
    starts: dict[str, list[float]] = defaultdict(list)
    for e in by_kind["start"]:
        starts[e["vid"]].append(e["ts"])
    mins = []
    for e in ends:
        before = [t for t in starts.get(e["vid"], []) if t <= e["ts"]]
        if before:
            mins.append((e["ts"] - max(before)) / 60)

    npcs = {}
    for key, c in story.BY_KEY.items():
        msgs = [e for e in by_kind["msg"] if e["data"].get("npc") == key]
        talks = [e for e in by_kind["talk"] if e["data"].get("npc") == key]
        rounds = [e for e in by_kind["round"] if e["data"].get("npc") == key]
        fb = [e for e in by_kind["feedback"] if e["data"].get("npc") == key]
        npcs[key] = {"name": i18n.plain(c["name"]), "talks": len(talks), "messages": len(msgs), "rounds_fought": len(rounds),
                     "avg_trust_change": round(sum(e["data"].get("delta", 0) for e in msgs) / len(msgs), 2) if msgs else 0,
                     "killed_her": sum(1 for e in ends if e["data"].get("killer") == key),
                     "up": sum(1 for e in fb if e["data"].get("rating") == "up"), "down": sum(1 for e in fb if e["data"].get("rating") == "down")}
    wins = sum(1 for e in ends if e["data"].get("won"))
    builds = Counter((e["data"].get("off"), e["data"].get("defn")) for e in by_kind["start"])

    day_rows: dict[str, dict] = defaultdict(lambda: {"visits": 0, "starts": 0, "endings": 0, "messages": 0})
    for kind, field in (("visit", "visits"), ("start", "starts"), ("end", "endings"), ("msg", "messages")):
        for e in by_kind[kind]:
            day_rows[_day(e["ts"])][field] += 1

    return {
        "days": days,
        "languages": dict(Counter({e["vid"]: e["data"].get("lang", "en") for e in visits}.values())),
        "visitors": uniq("visit"), "page_loads": len(visits), "returning_loads": sum(1 for e in visits if e["data"].get("returning")),
        "nights_started": len(by_kind["start"]), "nights_finished": len(ends), "nights_abandoned": len(by_kind["abandoned"]),
        "funnel": [{"step": s, "visitors": n} for s, n in funnel],
        "endings": dict(endings), "death_causes": {k or "?": v for k, v in causes.items()},
        "win_rate": round(wins / len(ends), 3) if ends else None, "avg_fights_at_end": round(sum(e["data"].get("fights", 0) for e in ends) / len(ends), 1) if ends else None,
        "builds": {f"{a} + {b}": n for (a, b), n in builds.most_common(8) if a},
        "avg_minutes_to_finish": round(sum(mins) / len(mins), 1) if mins else None,
        "avg_messages_at_end": round(sum(e["data"].get("msgs", 0) for e in ends) / len(ends), 1) if ends else None,
        "people": npcs,
        "ai": {"player_messages": len(by_kind["msg"]), "ray_questions": len(by_kind["gm"]), "errors": len(by_kind["error"]),
               "errors_by_kind": dict(Counter(e["data"].get("kind", "?") for e in by_kind["error"]))},
        "feedback": {"up": sum(1 for e in by_kind["feedback"] if e["data"].get("rating") == "up"),
                     "down": sum(1 for e in by_kind["feedback"] if e["data"].get("rating") == "down")},
        "daily": [{"date": d, **v} for d, v in sorted(day_rows.items(), reverse=True)],
    }


def transcripts(conn, limit: int = 40, only_down: bool = False) -> list[dict]:
    """The latest conversations, with each reply's thumbs, so the AI's replies can be read and judged."""
    ratings = {}
    for e in _events(conn, "feedback"):
        ratings[(e["data"].get("talk"), e["data"].get("turn"))] = e["data"].get("rating")
    rows = conn.execute("SELECT id, visitor_id, npc_key, trust, turns, updated_at, 0 AS archived FROM talks "
                        "UNION ALL SELECT id, visitor_id, npc_key, trust, turns, updated_at, 1 AS archived FROM talk_archive "
                        "ORDER BY updated_at DESC LIMIT ?", (limit * (4 if only_down else 1),)).fetchall()
    out = []
    for r in rows:
        turns = json.loads(r["turns"])
        marked = []
        for i, t in enumerate(turns):
            if t.get("hidden"):
                continue
            marked.append({"role": t["role"], "content": t["content"], "rating": ratings.get((r["id"], i)) if t["role"] == "assistant" else None})
        if only_down and not any(m["rating"] == "down" for m in marked):
            continue
        out.append({"id": r["id"], "visitor": _who(r["visitor_id"]), "npc": i18n.plain(story.BY_KEY[r["npc_key"]]["name"]) if r["npc_key"] in story.BY_KEY else r["npc_key"],
                    "trust": r["trust"], "updated": time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["updated_at"])), "archived": bool(r["archived"]),
                    "turns": marked})
    return out[:limit]
