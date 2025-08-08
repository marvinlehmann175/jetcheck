# backend/scraper.py
import os
import sys
import datetime as dt
from typing import Dict, Any, List, Optional
import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from dateutil.tz import gettz
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
    return (
        dt_obj.astimezone(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

# ----------------------------
# GlobeAir parsing helpers
# ----------------------------
GLOBEAIR_URL = "https://www.globeair.com/empty-leg-flights"

# "Amsterdam (AMS) → Zurich (ZRH)"
RE_TITLE = re.compile(r"^\s*(.+?)\s*\(([A-Z]{3})\)\s*→\s*(.+?)\s*\(([A-Z]{3})\)\s*$")
RE_TIME  = re.compile(r"^\s*([0-9: ]+[AP]M)\s*→\s*([0-9: ]+[AP]M)\s*$")
RE_PCT   = re.compile(r"-?(\d+)%")
RE_MONEY = re.compile(r"(\d[\d.,]*)")

def _clean_money(text: str) -> Optional[float]:
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

def _to_iso_utc(date_str: str, time_str: str) -> Optional[str]:
    """
    GlobeAir liefert keine Zeitzonen. Wir interpretieren Datum+Uhrzeit zunächst als naive Zeit
    und speichern diese als UTC-ISO-String. Später können wir das mit IATA->TZ aufbohren.
    """
    if not (date_str and time_str):
        return None
    d = dtparser.parse(date_str)
    t = dtparser.parse(time_str, default=d)
    # ohne echte TZ als UTC persistieren
    t = t.replace(tzinfo=dt.timezone.utc)
    return iso_utc(t)

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

# ----------------------------
# ASL parsing helpers
# ----------------------------
ASL_BASE = "https://www.aslgroup.eu"
ASL_START = f"{ASL_BASE}/en/empty-legs"
ASL_TZ = gettz("Europe/Brussels")

def _extract_name_and_code(raw: str):
    """
    Erwartet Strings wie:
      "Rotterdam(EHRD)"
      "Montichiari (BS)(LIPO)"
      "Ibiza (Eivissa)(LEIB)"
    Nimmt den letzten (...) Block als Code, der Rest als Name.
    """
    raw = (raw or "").strip()
    matches = list(re.finditer(r"\(([A-Z0-9]{3,4})\)\s*$", raw))
    if matches:
        code = matches[-1].group(1).strip().upper()
        name = raw[:matches[-1].start()].strip()
    else:
        code = None
        name = raw
    name = re.sub(r"\s+", " ", name).strip(" -–—")
    return name, code

def _parse_asl_article(art) -> Optional[Dict[str, Any]]:
    # Flugzeug
    plane_name_el = art.select_one(".plane-name")
    aircraft = plane_name_el.get_text(strip=True) if plane_name_el else None

    # Headline mit Route
    head = art.select_one(".plane-headline")
    if not head:
        return None

    head_txt = head.get_text(" ", strip=True)
    # Split am Pfeil (es gibt ein Icon)
    parts = re.split(r"\s*→\s*|\s*>\s*", head_txt)
    if len(parts) < 2:
        return None
    origin_raw, dest_raw = parts[0].strip(), parts[-1].strip()

    origin_name, origin_code = _extract_name_and_code(origin_raw)
    dest_name, dest_code = _extract_name_and_code(dest_raw)

    # Specs: Datum, Zeit, Pax
    specs = [li.get_text(" ", strip=True) for li in art.select(".plane-specs .plane-spec-item")]
    date_str = next((s for s in specs if re.search(r"\d{2}-\d{2}-\d{4}", s)), None)
    time_str = next((s for s in specs if re.search(r"\b\d{2}:\d{2}\b", s)), None)
    pax_str  = next((s for s in specs if "passengers" in s.lower()), None)

    # Link
    link_el = art.select_one('a.button.button-primary')
    link = ASL_BASE + link_el["href"] if link_el and link_el.get("href") else None

    # Datum/Zeit -> UTC
    departure_ts = None
    if date_str and time_str:
        m_date = re.search(r"(\d{2})-(\d{2})-(\d{4})", date_str)
        m_time = re.search(r"\b(\d{2}):(\d{2})\b", time_str)
        if m_date and m_time:
            local_dt = dt.datetime(
                int(m_date.group(3)),
                int(m_date.group(2)),
                int(m_date.group(1)),
                int(m_time.group(1)),
                int(m_time.group(2)),
                tzinfo=ASL_TZ
            )
            departure_ts = iso_utc(local_dt)

    # Seats (optional)
    seats = None
    if pax_str:
        m_pax = re.search(r"(\d+)(?:\s*-\s*(\d+))?\s*passengers", pax_str.lower())
        if m_pax:
            seats = int(m_pax.group(2) or m_pax.group(1))

    if not departure_ts:
        return None

    return {
        "source": "asl",
        "origin_name": origin_name or None,
        "destination_name": dest_name or None,
        "origin_iata": (origin_code or "").upper() or None,       # ASL liefert oft ICAO (4-Letter)
        "destination_iata": (dest_code or "").upper() or None,
        "departure_ts": departure_ts,   # ISO UTC
        "arrival_ts": None,             # nicht vorhanden
        "currency": "EUR",
        "status": "pending",
        "aircraft": aircraft,
        "seats": seats,
        "link": link,
        "raw": {"pax": pax_str} if pax_str else None,
        "raw_static": {"operator": "ASL"}
    }

def fetch_asl_pages(max_pages: int = 20, timeout: int = 25) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; JetCheckBot/1.0; +https://jetcheck.de)"})

    page = 1
    while page <= max_pages:
        url = ASL_START if page == 1 else f"{ASL_START}/{page}"
        r = session.get(url, timeout=timeout)
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        arts = soup.select("article.plane")
        if not arts:
            break
        for art in arts:
            row = _parse_asl_article(art)
            if row:
                out.append(row)
        # Pagination: gibt es einen Next-Button?
        next_btn = soup.select_one(".pagination a.pagination-button")
        if not next_btn:
            break
        page += 1

    return out

# ----------------------------
# DB upsert helpers
# ----------------------------
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
    # Ensure arrival is after departure and within a sane window; else drop to satisfy DB constraint
    try:
        if dep and arr:
            dep_dt = dtparser.isoparse(dep)
            arr_dt = dtparser.isoparse(arr)
            delta = (arr_dt - dep_dt).total_seconds()
            if delta <= 0 or delta > 24 * 3600:
                arr = None
    except Exception:
        arr = None

    flight_payload = {
        "user_id": SYSTEM_USER_ID,
        "source": rec["source"],
        "origin_iata": rec.get("origin_iata"),
        "origin_name": rec.get("origin_name"),
        "destination_iata": rec.get("destination_iata"),
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

    up = (
        supabase
        .table("flights")
        .upsert(flight_payload, on_conflict="hash", returning="representation")
        .execute()
    )
    if not up.data:
        raise RuntimeError("Upsert flights returned no data")
    flight_id = up.data[0]["id"]

    # Preise validieren
    price_current = rec.get("price_current")
    price_normal = rec.get("price_normal")
    if isinstance(price_current, (int, float)) and price_current <= 0:
        price_current = None
    if isinstance(price_normal, (int, float)) and price_normal <= 0:
        price_normal = None

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

# ----------------------------
# Orchestrierung
# ----------------------------
def scrape() -> List[Dict[str, Any]]:
    """
    Ruft GlobeAir & ASL ab und normalisiert sie für die DB.
    """
    all_rows: List[Dict[str, Any]] = []

    # GlobeAir
    try:
        ga = fetch_globeair_cards()
        print(f"ℹ️  GlobeAir: {len(ga)}")
        all_rows.extend(ga)
    except Exception as e:
        print(f"❌ GlobeAir fetch error: {e}", file=sys.stderr)

    # ASL (mit Pagination)
    try:
        asl = fetch_asl_pages()
        print(f"ℹ️  ASL: {len(asl)}")
        all_rows.extend(asl)
    except Exception as e:
        print(f"❌ ASL fetch error: {e}", file=sys.stderr)

    return all_rows

def main():
    print("🔄 Starte Scraper…")
    records = scrape()
    print(f"ℹ️  Insgesamt {len(records)} Datensätze geparst.")
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