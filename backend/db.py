import os
import sys
import datetime as dt
from typing import Optional

from dateutil import parser as dtparser
from dotenv import load_dotenv
from supabase import create_client, Client

from common.types import FlightRecord

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Prefer service role key so RLS policies don’t block the scraper
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
SYSTEM_USER_ID = os.getenv("SYSTEM_USER_ID")  # auth.users.id of your system user

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
    sys.exit(1)

if not SYSTEM_USER_ID:
    print("❌ Missing SYSTEM_USER_ID (auth.users.id UUID)", file=sys.stderr)
    sys.exit(1)

_client: Optional[Client] = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def _iso_utc(dt_obj: dt.datetime) -> str:
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return (
        dt_obj.astimezone(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalize_dep_arr(dep: Optional[str], arr: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Ensure timestamps are ISO UTC strings and arrival is plausible (0 < delta <= 24h).
    Never reference external variables here.
    """
    # Convert datetime objects to ISO-UTC strings
    if isinstance(dep, dt.datetime):
        dep = _iso_utc(dep)
    if isinstance(arr, dt.datetime):
        arr = _iso_utc(arr)

    # Empty strings -> None
    dep = dep or None
    arr = arr or None

    # Validate ordering (allow up to 24h duration)
    try:
        if dep and arr:
            dep_dt = dtparser.isoparse(dep)
            arr_dt = dtparser.isoparse(arr)
            delta = (arr_dt - dep_dt).total_seconds()
            if delta <= 0 or delta > 24 * 3600:
                arr = None
    except Exception:
        arr = None

    return dep, arr


def _coerce_price(p) -> Optional[float]:
    """Turn strings like '12,000' into 12000.0; negatives/zero -> None."""
    if p is None:
        return None
    try:
        if isinstance(p, str):
            p = float(p.replace(",", "").replace(" ", ""))
        p = float(p)
        if p <= 0:
            return None
        return p
    except Exception:
        return None


def _norm_status(explicit: Optional[str], price_current) -> str:
    """
    Map provider/explicit statuses to our 3-status model.
    - If price_current is a positive number -> 'available'
    - Else -> 'pending'
    - We do NOT set 'unavailable' here; the refresh function handles that.
    """
    pc = _coerce_price(price_current)
    if pc is not None and pc > 0:
        return "available"
    return "pending"


def upsert_flight_and_snapshot(rec: FlightRecord) -> int:
    supabase = get_supabase()

    # Guard empty strings and normalize timestamps
    dep_in = rec.get("departure_ts") or None
    arr_in = rec.get("arrival_ts") or None
    dep, arr = _normalize_dep_arr(dep_in, arr_in)

    # Sanitize prices (coerce strings, drop <=0)
    price_current = _coerce_price(rec.get("price_current"))
    price_normal = _coerce_price(rec.get("price_normal"))

    # Normalize status to our 3-status model BEFORE writing
    status_norm = _norm_status(rec.get("status"), price_current)

    flight_payload = {
        "user_id": SYSTEM_USER_ID,
        "source": rec["source"],
        "origin_iata": rec["origin_iata"],
        "origin_name": rec.get("origin_name"),
        "destination_iata": rec["destination_iata"],
        "destination_name": rec.get("destination_name"),
        "departure_ts": dep,
        "arrival_ts": arr,
        "aircraft": rec.get("aircraft"),
        "link": rec.get("link"),
        "currency": rec.get("currency", "EUR"),
        "status": status_norm,  # normalized here
        "probability": rec.get("probability"),
        "raw_static": rec.get("raw_static"),
    }

    up = (
        supabase
        .table("flights")
        .upsert(flight_payload, on_conflict="hash", returning="representation")
        .execute()
    )
    if not up.data or len(up.data) != 1:
        raise RuntimeError(f"Unexpected upsert result: {up.data}")

    flight_id = up.data[0]["id"]

    snap_payload = {
        "flight_id": flight_id,
        "price_current": price_current,
        "price_normal": price_normal,
        "currency": rec.get("currency", "EUR"),
        "status": status_norm,  # snapshot mirrors normalized status
        "link": rec.get("link"),
        "raw": rec.get("raw"),
    }
    supabase.table("flight_snapshots").insert(snap_payload).execute()

    return flight_id