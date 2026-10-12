"""Which country a visitor is in, worked out on this server from the IP address.

The lookup uses DB-IP's free "IP to Country Lite" file (app/geo/, CC BY 4.0, https://db-ip.com), so no IP address is sent to any other service,
and only the two-letter country code is ever stored: never the IP itself."""
import gzip
import ipaddress
import tempfile
from pathlib import Path

import maxminddb

_FILE = Path(__file__).parent / "geo" / "dbip-country-lite.mmdb.gz"
_reader = None


def _db():
    global _reader
    if _reader is None:
        out = Path(tempfile.gettempdir()) / "dbip-country-lite.mmdb"
        if not out.exists() or out.stat().st_mtime < _FILE.stat().st_mtime:
            out.write_bytes(gzip.decompress(_FILE.read_bytes()))
        _reader = maxminddb.open_database(str(out))
    return _reader


def country(ip: str) -> str:
    """Two-letter country code ("TH", "US"...), or "" for a private, local or unknown address."""
    try:
        addr = ipaddress.ip_address((ip or "").strip())
        if not addr.is_global:
            return ""
        rec = _db().get(str(addr)) or {}
        return (rec.get("country") or {}).get("iso_code", "") or ""
    except (ValueError, OSError, maxminddb.InvalidDatabaseError):
        return ""


def client_ip(headers, peer: str = "") -> str:
    """The visitor's address: behind Railway's proxy it is the first entry of X-Forwarded-For."""
    fwd = headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else peer


def device(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if any(k in ua for k in ("iphone", "android", "mobile")) and "ipad" not in ua:
        return "phone"
    if any(k in ua for k in ("ipad", "tablet")):
        return "tablet"
    return "desktop" if ua else ""
