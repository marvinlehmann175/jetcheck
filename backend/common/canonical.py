# common/canonical.py
import hashlib
from datetime import datetime, timezone

def floor_to_5min(ts_iso: str) -> str:
    """Return ts truncated to 5-minute buckets in ISO Z."""
    if not ts_iso:
        return ""
    dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    dt = dt.replace(second=0, microsecond=0)
    minute = (dt.minute // 5) * 5
    dt = dt.replace(minute=minute)
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")

def canonical_hash(origin_iata: str, destination_iata: str, departure_ts: str, aircraft: str | None) -> str:
    o = (origin_iata or "").strip().upper()
    d = (destination_iata or "").strip().upper()
    t = floor_to_5min(departure_ts) if departure_ts else ""
    a = (aircraft or "").strip().lower()
    key = "|".join([o, d, t, a])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()