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
PORTRAIT_MODEL = os.getenv("PORTRAIT_MODEL", "deepseek-flash")

# Password for /admin.html (hide, restore, delete NPCs). Admin is switched off when empty.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

DATABASE_PATH =Path(os.getenv("DATABASE_PATH", ROOT / "data" / "jianghu.db"))

# Abuse and spend protection. Every model request counts as one call
# (an agent turn that uses two tools is three calls).
CALLS_PER_VISITOR_PER_10_MIN = _int("CALLS_PER_VISITOR_PER_10_MIN", 60)
DAILY_CALL_CAP = _int("DAILY_CALL_CAP", 3000)

MAX_MESSAGE_CHARS = 600
MAX_HISTORY_TURNS = 20
SECRET_TRUST_THRESHOLD = 7
