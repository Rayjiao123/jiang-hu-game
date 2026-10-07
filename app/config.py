"""Settings, read from environment variables (or a local .env file)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
CHAT_MODEL = os.getenv("CHAT_MODEL", "deepseek-flash")

# Password for /admin.html (visitor stats, transcripts, feedback). The admin area is switched off when empty.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", ROOT / "data" / "jianghu.db"))

# Abuse and spend protection. Every model request counts as one call. One message from the player
# costs about four or five (a translation, the message check, the reply, the clue referee), so a whole night
# is a few hundred calls.
CALLS_PER_VISITOR_PER_10_MIN = _int("CALLS_PER_VISITOR_PER_10_MIN", 150)
DAILY_CALL_CAP = _int("DAILY_CALL_CAP", 8000)

MAX_MESSAGE_CHARS = 600
MAX_HISTORY_TURNS = 20
