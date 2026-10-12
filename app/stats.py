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


ICT = 7 * 3600                     # every time shown to the admin is Thailand time (UTC+7)


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts + ICT))


def _stamp(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts + ICT))


def players(conn, since: float = 0, limit: int = 300) -> list[dict]:
    """One row per visitor: when they came, how often, how many nights they played, how long, and how the last one ended.
    A night lasts from its start to its ending; one that was never finished lasts until the visitor's last action in it."""
    by_vid: dict[str, list[dict]] = defaultdict(list)
    for e in _events(conn, since=since):
        by_vid[e["vid"]].append(e)
    rows = []
    for vid, ev in by_vid.items():
        starts = [e["ts"] for e in ev if e["kind"] == "start"]
        nights, last_end = [], None
        for i, t0 in enumerate(starts):
            t_next = starts[i + 1] if i + 1 < len(starts) else float("inf")
            inside = [e for e in ev if t0 <= e["ts"] < t_next and e["kind"] != "visit"]
            end = next((e for e in inside if e["kind"] == "end"), None)
            t1 = end["ts"] if end else max(e["ts"] for e in inside)
            nights.append({"minutes": (t1 - t0) / 60, "ended": bool(end), "won": bool(end and end["data"].get("won")), "ending": end["data"].get("ending") if end else ""})
            last_end = nights[-1]
        visits = [e for e in ev if e["kind"] == "visit"]
        langs = [e["data"].get("lang") for e in ev if e["data"].get("lang")]
        countries = [e["data"]["country"] for e in visits if e["data"].get("country")]
        devices = [e["data"]["device"] for e in visits if e["data"].get("device")]
        rows.append({"who": _who(vid), "first_seen": _stamp(ev[0]["ts"]), "last_seen": _stamp(ev[-1]["ts"]), "last_ts": ev[-1]["ts"], "visits": len(visits),
                     "lang": langs[-1] if langs else "", "country": countries[-1] if countries else "", "device": devices[-1] if devices else "", "nights": len(nights), "finished": sum(n["ended"] for n in nights), "wins": sum(n["won"] for n in nights),
                     "minutes": round(sum(n["minutes"] for n in nights), 1), "last_night_minutes": round(last_end["minutes"], 1) if last_end else None,
                     "last_result": ("won" if last_end["won"] else last_end["ending"] or "died") if last_end and last_end["ended"] else ("in progress or left" if last_end else "only looked"),
                     "messages": sum(1 for e in ev if e["kind"] == "msg"), "fights": sum(1 for e in ev if e["kind"] == "round")})
    rows.sort(key=lambda r: -r["last_ts"])
    for r in rows:
        del r["last_ts"]
    return rows[:limit]


def _events(conn, kind: str | None = None, since: float = 0) -> list[dict]:
    q, args = "SELECT ts, visitor_id, kind, data FROM events WHERE ts >= ?", [since]
    if kind:
        q += " AND kind = ?"
        args.append(kind)
    return [{"ts": r["ts"], "vid": r["visitor_id"], "kind": r["kind"], "data": json.loads(r["data"] or "{}")} for r in conn.execute(q + " ORDER BY ts", args)]


def _per_visitor(events: list[dict], field: str) -> dict:
    """How many distinct visitors had each value (their latest one)."""
    latest = {e["vid"]: e["data"].get(field) for e in events if e["data"].get(field)}
    return dict(Counter(latest.values()).most_common(15))


def _quality(judged: list[dict]) -> dict:
    """What the AI judge thought of the replies it scored (a sample of real ones): averages by person and language, and how many it flagged."""
    from . import judge
    avg = lambda rows, f: round(sum(f(r) for r in rows) / len(rows), 2) if rows else None
    dims = lambda rows: {d: avg(rows, lambda r, d=d: r["data"].get(d, 0)) for d in judge.DIMS}
    by_person = {}
    for key, c in story.BY_KEY.items():
        rows = [e for e in judged if e["data"].get("npc") == key]
        if rows:
            by_person[key] = {"name": i18n.plain(c["name"]), "scored": len(rows), "overall": avg(rows, lambda r: r["data"].get("overall", 0)), **dims(rows),
                              "leaks": sum(1 for r in rows if r["data"].get("leaked")), "low": sum(1 for r in rows if r["data"].get("overall", 5) < 3)}
    by_lang = {lg: {"scored": len(rs), "overall": avg(rs, lambda r: r["data"].get("overall", 0)), "language": avg(rs, lambda r: r["data"].get("language", 0))}
               for lg in i18n.LANGS if (rs := [e for e in judged if e["data"].get("lang") == lg])}
    return {"scored": len(judged), "overall": avg(judged, lambda r: r["data"].get("overall", 0)), **dims(judged), "leaks": sum(1 for r in judged if r["data"].get("leaked")),
            "low": sum(1 for r in judged if r["data"].get("overall", 5) < 3), "by_person": by_person, "by_lang": by_lang}


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
        "countries": _per_visitor(visits, "country"), "devices": _per_visitor(visits, "device"), "referrers": _per_visitor([e for e in visits if e["data"].get("ref")], "ref"),
        "quality": _quality(by_kind["judge"]), "people": npcs, "players": players(conn, since), "total_minutes_played": round(sum(r["minutes"] for r in players(conn, since, 100000)), 1),
        "ai": {"player_messages": len(by_kind["msg"]), "ray_questions": len(by_kind["gm"]), "errors": len(by_kind["error"]),
               "errors_by_kind": dict(Counter(e["data"].get("kind", "?") for e in by_kind["error"]))},
        "feedback": {"up": sum(1 for e in by_kind["feedback"] if e["data"].get("rating") == "up"),
                     "down": sum(1 for e in by_kind["feedback"] if e["data"].get("rating") == "down")},
        "daily": [{"date": d, **v} for d, v in sorted(day_rows.items(), reverse=True)],
    }


def transcripts(conn, limit: int = 40, only_down: bool = False) -> list[dict]:
    """The latest conversations, with each reply's thumbs, so the AI's replies can be read and judged."""
    ratings, judged = {}, {}
    for e in _events(conn, "feedback"):
        ratings[(e["data"].get("talk"), e["data"].get("turn"))] = e["data"].get("rating")
    for e in _events(conn, "judge"):
        judged[(e["data"].get("talk"), e["data"].get("turn"))] = {"overall": e["data"].get("overall"), "leaked": e["data"].get("leaked"), "language": e["data"].get("language")}
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
            marked.append({"role": t["role"], "content": t["content"], "rating": ratings.get((r["id"], i)) if t["role"] == "assistant" else None,
                           "judge": judged.get((r["id"], i)) if t["role"] == "assistant" else None})
        if only_down and not any(m["rating"] == "down" for m in marked):
            continue
        out.append({"id": r["id"], "visitor": _who(r["visitor_id"]), "npc": i18n.plain(story.BY_KEY[r["npc_key"]]["name"]) if r["npc_key"] in story.BY_KEY else r["npc_key"],
                    "trust": r["trust"], "updated": _stamp(r["updated_at"]), "archived": bool(r["archived"]),
                    "turns": marked})
    return out[:limit]
