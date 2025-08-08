# backend/scraper.py
import os
import sys
import datetime as dt
from typing import Dict, Any, List
import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
SYSTEM_USER_ID = os.getenv("SYSTEM_USER_ID")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
    sys.exit(1)
if not SYSTEM_USER_ID:
    print("❌ Missing SYSTEM_USER_ID (must be an auth.users.id UUID)", file=sys.stderr)
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def iso_utc(dt_obj: dt.datetime) -> str:
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return dt_obj.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

# ----------------------------
# GlobeAir parsing helpers
# ----------------------------
GLOBEAIR_URL = "https://www.globeair.com/empty-leg-flights"

# "Amsterdam (AMS) → Zurich (ZRH)"
RE_TITLE = re.compile(r"^\s*(.+?)\s*\(([A-Z]{3})\)\s*→\s*(.+?)\s*\(([A-Z]{3})\)\s*$")
RE_TIME  = re.compile(r"^\s*([0-9: ]+[AP]M)\s*→\s*([0-9: ]+[AP]M)\s*$")
RE_PCT   = re.compile(r"-?(\d+)%")
RE_MONEY = re.compile(r"(\d[\d.,]*)")

def _clean_money(text: str):
    m = RE_MONEY.search(text or "")
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return None

def _to_iso_utc(date_str: str, time_str: str):
    """
    GlobeAir liefert keine Zeitzonen. Wir interpretieren Datum+Uhrzeit zunächst als naive Zeit
    und speichern diese als UTC-ISO-String. Später können wir das mit IATA-&gt;TZ aufbohren.
    """
    if not (date_str and time_str):
        return None
    d = dtparser.parse(date_str)
    t = dtparser.parse(time_str, default=d)
    # ohne echte TZ als UTC persistieren
    t = t.replace(tzinfo=None)
    return t.isoformat() + "Z"

def parse_globeair_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[Dict[str, Any]] = []

    for col in soup.select(".columns .column"):
        h3 = col.select_one("h3.caption")
        p  = col.select_one("p.flightdata")
        if not h3 or not p:
            continue

        title = h3.get_text(" ", strip=True)  # z.B. "Osijek (OSI) → Friedrichshafen (FDH)"
        m = RE_TITLE.match(title)
        if not m:
            continue

        origin_name, origin_iata, dest_name, dest_iata = m.groups()

        # Textzeilen der Details
        lines = [s.strip() for s in p.stripped_strings]
        date_line = lines[0] if len(lines) > 0 else None
        time_line = lines[1] if len(lines) > 1 else None
        info_line = lines[2] if len(lines) > 2 else ""

        dep_time = arr_time = None
        tm = RE_TIME.match(time_line or "")
        if tm:
            dep_time, arr_time = tm.groups()

        departure_ts = _to_iso_utc(date_line, dep_time) if dep_time else None
        arrival_ts   = _to_iso_utc(date_line, arr_time) if arr_time else None

        # Defaults
        status = "pending"
        price_current = None
        price_normal = None
        discount_percent = None
        probability = None
        currency = "EUR"

        # Aktueller Preis im "Book for €..." Button
        book_btn = col.select_one("a.button.is-primary")
        if book_btn:
            price_current = _clean_money(book_btn.get_text())
            if price_current:
                status = "confirmed"

        # Durchgestrichener Preis
        strike = col.select_one("p.flightdata strike")
        if strike:
            price_normal = _clean_money(strike.get_text())

        # "(–91%)" im strong
        strong = col.select_one("p.flightdata strong")
        if strong:
            pm = RE_PCT.search(strong.get_text())
            if pm:
                try:
                    discount_percent = int(pm.group(1))
                except ValueError:
                    discount_percent = None

        # "Flight not confirmed yet."
        if "Flight not confirmed" in (info_line or ""):
            status = "pending"

        # Probability-Tag
        prob_span = col.select_one(".tags .tag.is-info")
        if prob_span:
            pm2 = RE_PCT.search(prob_span.get_text())
            if pm2:
                try:
                    probability = int(pm2.group(1)) / 100.0
                except ValueError:
                    probability = None

        # Deeplink
        link = None
        a0 = col.select_one("a[href]")
        if a0:
            link = a0.get("href")

        rows.append({
            "source": "globeair",
            "origin_iata": origin_iata,
            "origin_name": origin_name,
            "destination_iata": dest_iata,
            "destination_name": dest_name,
            "departure_ts": departure_ts,
            "arrival_ts": arrival_ts,
            "status": status,
            "price_current": price_current,
            "price_normal": price_normal,
            "discount_percent": discount_percent,
            "probability": probability,
            "currency": currency,
            "link": link,
            "raw": {
                "title": title,
                "date": date_line,
                "times": time_line,
                "info": info_line
            },
            "raw_static": {"operator": "GlobeAir"}
        })
    return rows

def fetch_globeair_cards(timeout: int = 25) -> List[Dict[str, Any]]:
    resp = requests.get(GLOBEAIR_URL, timeout=timeout, headers={
        "User-Agent": "Mozilla/5.0 (compatible; JetCheckBot/1.0; +https://jetcheck.de)"
    })
    resp.raise_for_status()
    return parse_globeair_html(resp.text)

def upsert_flight_and_snapshot(rec: Dict[str, Any]) -> int:
    """
    Erwartet Keys:
      source, origin_iata, origin_name?, destination_iata, destination_name?,
      departure_ts (ISO oder datetime), arrival_ts? (ISO/datetime),
      aircraft?, link?, currency? ('EUR'/'USD'/'GBP'), status?, probability?,
      price_current?, price_normal?, raw?, raw_static?
    Returns: flight_id
    """
    # Zeitfelder normieren
    dep = rec["departure_ts"]
    if isinstance(dep, dt.datetime):
        dep = iso_utc(dep)
    arr = rec.get("arrival_ts")
    if isinstance(arr, dt.datetime):
        arr = iso_utc(arr)
    # Ensure arrival is strictly after departure; otherwise omit arrival
    try:
        if dep and arr:
            dep_dt = dtparser.isoparse(dep)
            arr_dt = dtparser.isoparse(arr)
            # Keep arrival if it is within a reasonable window (e.g., less than 24h after departure)
            # This avoids dropping arrivals that appear earlier due to time zone differences
            delta = (arr_dt - dep_dt).total_seconds()
            if delta <= 0 or delta > 24 * 3600:
                arr = None
    except Exception:
        # If parsing fails for any reason, fall back to dropping arrival to avoid DB constraint errors
        arr = None

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
        "status": rec.get("status", "pending"),
        "probability": rec.get("probability"),
        "raw_static": rec.get("raw_static"),
    }

    # Upsert nach unique hash (DB-Trigger setzt den Hash)
    up = (
        supabase
        .table("flights")
        .upsert(flight_payload, on_conflict="hash", returning="representation")
        .execute()
    )
    if not up.data:
        raise RuntimeError("Upsert flights returned no data")
    flight_id = up.data[0]["id"]

    # Ensure prices are positive numbers if provided; otherwise store as None
    price_current = rec.get("price_current")
    price_normal = rec.get("price_normal")
    if isinstance(price_current, (int, float)) and price_current <= 0:
        price_current = None
    if isinstance(price_normal, (int, float)) and price_normal <= 0:
        price_normal = None

    # Snapshot IMMER anhängen (Historie)
    snap_payload = {
        "flight_id": flight_id,
        "price_current": price_current,
        "price_normal": price_normal,
        "currency": rec.get("currency", "EUR"),
        "status": rec.get("status"),
        "link": rec.get("link"),
        "raw": rec.get("raw"),
    }
    supabase.table("flight_snapshots").insert(snap_payload).execute()
    return flight_id

def scrape() -> List[Dict[str, Any]]:
    """
    Ruft GlobeAir-Empty-Legs ab und normalisiert sie für die DB.
    """
    try:
        return fetch_globeair_cards()
    except Exception as e:
        print(f"❌ fetch_globeair_cards error: {e}", file=sys.stderr)
        return []

def main():
    print("🔄 Starte Scraper…")
    records = scrape()
    print(f"ℹ️  {len(records)} Datensätze von GlobeAir geparst.")
    saved = 0
    for r in records:
        try:
            upsert_flight_and_snapshot(r)
            saved += 1
        except Exception as e:
            print(f"❌ Fehler für {r.get('origin_iata')}→{r.get('destination_iata')}: {e}", file=sys.stderr)
    print(f"✅ {saved} Flüge/Snapshots gespeichert.")

if __name__ == "__main__":
    main()