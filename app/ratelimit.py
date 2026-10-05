"""In-memory limits on model calls: per visitor, and a global daily cap.
Good enough for one server process; move to Redis if you run several."""
import threading
import time
from collections import defaultdict, deque

from . import config


class RateLimited(Exception):
    pass


_lock = threading.Lock()
_recent: dict[str, deque] = defaultdict(deque)
_day = {"date": "", "count": 0}


def check(visitor_id: str) -> None:
    now = time.time()
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    with _lock:
        if _day["date"] != today:
            _day.update(date=today, count=0)
        if _day["count"] >= config.DAILY_CALL_CAP:
            raise RateLimited("The jianghu is resting for today. Come back tomorrow.")
        q = _recent[visitor_id]
        while q and now - q[0] > 600:
            q.popleft()
        if len(q) >= config.CALLS_PER_VISITOR_PER_10_MIN:
            raise RateLimited("You're talking faster than the teahouse can keep up. Wait a few minutes.")
        q.append(now)
        _day["count"] += 1
