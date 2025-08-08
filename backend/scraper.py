# backend/scraper.py
import os
import sys
import datetime as dt
from typing import Dict, Any, List, Optional, Tuple
import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
SYSTEM_USER_ID = os.getenv("SYSTEM_USER_ID")
DEBUG = os.getenv("SCRAPER_DEBUG", "0") == "1"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
    sys.exit(1)
if not SYSTEM_USER_ID:
    print("❌ Missing SYSTEM_USER_ID (must be an auth.users.id UUID)", file=sys.stderr)
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- utils ----------
SESSION = requests.Session()
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 JetCheckBot/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,en-GB;q=0.9,de;q=0.8",
    "Cache-Control": "no-cache",
}

def iso_utc(dt_obj: dt.datetime) -> str:
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return dt_obj.astimezone(dt.timezone.utc)\
                 .replace(microsecond=0)\
                 .isoformat()\
                 .replace("+00:00", "Z")

def save_debug(name: str, text: str):
    if not DEBUG:
        return
    os.makedirs("/tmp/jetcheck", exist_ok=True)
    path = f"/tmp/jetcheck/{name}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"🪵 DEBUG saved: {path}")

# ---------- GlobeAir ----------
GLOBEAIR_URL = "https://www.globeair.com/empty-leg-flights"

RE_GA_TITLE = re.compile(r"^\s*(.+?)\s*\(([A-Z]{3})\)\s*→\s*(.+?)\s*\(([A-Z]{3})\)\s*$")
RE_GA_TIME  = re.compile(r"^\s*([0-9: ]+[AP]M)\s*→\s*([0-9: ]+[AP]M)\s*$")
RE_PCT      = re.compile(r"-?(\d+)%")
RE_MONEY    = re.compile(r"(\d[\d.,]*)")

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

def _to_iso_utc_naive(date_str: Optional[str], time_str: Optional[str]) -> Optional[str]:
    if not (date_str and time_str):
        return None
    try:
        d = dtparser.parse(date_str)
        t = dtparser.parse(time_str, default=d)
        t = t.replace(tzinfo=None)
        return t.isoformat() + "Z"
    except Exception:
        return None

def parse_globeair_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cols = soup.select(".columns .column")
    if DEBUG:
        print(f"GA: .columns .column => {len(cols)}")
    # Fallback: manchmal anderes Grid
    if not cols:
        cols = soup.select("div.column")
        if DEBUG:
            print(f"GA: fallback div.column => {len(cols)}")

    rows: List[Dict[str, Any]] = []
    for col in cols:
        h3 = col.select_one("h3.caption")
        p  = col.select_one("p.flightdata")
        if not h3 or not p:
            continue

        title = h3.get_text(" ", strip=True)
        m = RE_GA_TITLE.match(title)
        if not m:
            continue
        origin_name, origin_iata, dest_name, dest_iata = m.groups()

        lines = [s.strip() for s in p.stripped_strings]
        date_line = lines[0] if len(lines) > 0 else None
        time_line = lines[1] if len(lines) > 1 else None
        info_line = lines[2] if len(lines) > 2 else ""

        dep_time = arr_time = None
        tm = RE_GA_TIME.match(time_line or "")
        if tm:
            dep_time, arr_time = tm.groups()

        departure_ts = _to_iso_utc_naive(date_line, dep_time) if dep_time else None
        arrival_ts   = _to_iso_utc_naive(date_line, arr_time) if arr_time else None

        status = "pending"
        price_current = None
        price_normal = None
        discount_percent = None
        probability = None
        currency = "EUR"

        book_btn = col.select_one("a.button.is-primary, a.button.is-rounded.is-primary")
        if book_btn:
            price_current = _clean_money(book_btn.get_text())
            if price_current:
                status = "confirmed"

        strike = col.select_one("p.flightdata strike")
        if strike:
            price_normal = _clean_money(strike.get_text())

        strong = col.select_one("p.flightdata strong")
        if strong:
            pm = RE_PCT.search(strong.get_text())
            if pm:
                try:
                    discount_percent = int(pm.group(1))
                except ValueError:
                    discount_percent = None

        if "Flight not confirmed" in (info_line or ""):
            status = "pending"

        prob_span = col.select_one(".tags .tag.is-info")
        if prob_span:
            pm2 = RE_PCT.search(prob_span.get_text())
            if pm2:
                try:
                    probability = int(pm2.group(1)) / 100.0
                except ValueError:
                    probability = None

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
            "raw": {"title": title, "date": date_line, "times": time_line, "info": info_line},
            "raw_static": {"operator": "GlobeAir"},
        })
    return rows

def fetch_globeair_cards(timeout: int = 25) -> List[Dict[str, Any]]:
    r = SESSION.get(GLOBEAIR_URL, headers={**COMMON_HEADERS, "Referer": "https://www.globeair.com/"}, timeout=timeout)
    if DEBUG:
        print(f"GA status={r.status_code}, len={len(r.text)}")
    r.raise_for_status()
    save_debug("globeair.html", r.text)
    return parse_globeair_html(r.text)

# ---------- ASL ----------
ASL_BASE = "https://www.aslgroup.eu"
ASL_FIRST = f"{ASL_BASE}/en/empty-legs"

RE_ASL_ROUTE = re.compile(r"\s*(.+?)\(([^)]+)\)\s*→?\s*(.+?)\(([^)]+)\)\s*")
# Datum z. B. 09-08-2025, Uhrzeit 15:00, TZ Europe/Brussels
ASL_TZ = ZoneInfo("Europe/Brussels")

def _last_paren_code(text: str) -> str:
    # nimmt den letzten (...) Inhalt als Code-Kandidat und extrahiert 3–4 Buchstaben/Ziffern (ICAO/IATA mix)
    parts = re.findall(r"\(([^)]+)\)", text or "")
    cand = parts[-1].strip() if parts else ""
    # ICAO (4) oder IATA (3) akzeptieren, alphanumerisch
    m = re.search(r"[A-Z0-9]{3,4}$", cand.strip())
    return (m.group(0) if m else cand).upper()

def _parse_asl_datetime(date_s: str, time_s: str) -> Optional[str]:
    try:
        # 09-08-2025 + 15:00 in Europe/Brussels
        d = dtparser.parse(date_s, dayfirst=False)  # Format ist DD-MM-YYYY; dateutil frisst es
        t = dtparser.parse(time_s, default=d)
        # tz-aware
        local = dt.datetime(
            year=d.year, month=d.month, day=d.day,
            hour=t.hour, minute=t.minute, tzinfo=ASL_TZ
        )
        return iso_utc(local)
    except Exception:
        return None

def parse_asl_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    arts = soup.select("article.plane")
    if DEBUG:
        print(f"ASL: article.plane => {len(arts)}")
    rows: List[Dict[str, Any]] = []

    for art in arts:
        # Aircraft
        ac = (art.select_one(".plane-name") or {}).get_text(strip=True) if art.select_one(".plane-name") else None

        # Headline with route
        headline = art.select_one(".plane-headline")
        if not headline:
            # fallback: take text of the leading-heading container
            headline = art.select_one(".leading-headline")
        if not headline:
            continue
        route_text = headline.get_text(" ", strip=True)
        m = RE_ASL_ROUTE.search(route_text.replace("mdi mdi-arrow-right", "→"))
        if not m:
            # try more naive split by arrow icon
            arrow = "→"
            if arrow not in route_text:
                arrow = "-"
            parts = [p.strip() for p in route_text.split(arrow)]
            if len(parts) != 2:
                continue
            left, right = parts
            origin_name = re.sub(r"\([^)]*\)", "", left).strip()
            dest_name = re.sub(r"\([^)]*\)", "", right).strip()
            origin_iata = _last_paren_code(left)
            dest_iata = _last_paren_code(right)
        else:
            left_name, left_code, right_name, right_code = m.groups()
            origin_name = left_name.strip()
            dest_name = right_name.strip()
            origin_iata = _last_paren_code(left_code)
            dest_iata = _last_paren_code(right_code)

        # Specs list (date/time/passengers)
        date_li = None
        time_li = None
        for li in art.select("ul.plane-specs li"):
            txt = li.get_text(" ", strip=True)
            if re.search(r"\d{2}-\d{2}-\d{4}", txt):
                date_li = txt.strip()
            elif re.search(r"\d{1,2}:\d{2}", txt):
                time_li = txt.strip()

        date_s = re.search(r"(\d{2}-\d{2}-\d{4})", date_li or "")
        time_s = re.search(r"(\d{1,2}:\d{2})", time_li or "")
        departure_ts = _parse_asl_datetime(date_s.group(1), time_s.group(1)) if (date_s and time_s) else None

        # Deeplink
        a = art.select_one("a.button, a.button-full, a.button-primary, a[href]")
        link = a.get("href") if a else None
        if link and link.startswith("/"):
            link = ASL_BASE + link

        rows.append({
            "source": "asl",
            "origin_iata": origin_iata,
            "origin_name": origin_name,
            "destination_iata": dest_iata,
            "destination_name": dest_name,
            "departure_ts": departure_ts,
            "arrival_ts": None,   # Website zeigt keine Ankunft – optional später berechnen
            "status": "pending",
            "price_current": None,
            "price_normal": None,
            "discount_percent": None,
            "probability": None,
            "currency": "EUR",
            "link": link,
            "raw": {"headline": route_text, "date": date_li, "time": time_li},
            "raw_static": {"operator": "ASL", "aircraft": ac},
            "aircraft": ac,
        })
    return rows

def fetch_asl_cards(timeout: int = 25) -> List[Dict[str, Any]]:
    # Seite 1 laden, max page ermitteln, alle Seiten iterieren
    def _get(url: str) -> str:
        r = SESSION.get(url, headers={**COMMON_HEADERS, "Referer": ASL_BASE + "/"}, timeout=timeout)
        if DEBUG:
            print(f"ASL GET {url} status={r.status_code}, len={len(r.text)}")
        r.raise_for_status()
        return r.text

    first_html = _get(ASL_FIRST)
    save_debug("asl_1.html", first_html)
    rows = parse_asl_html(first_html)

    # Pagination: suche letzte Seite
    soup = BeautifulSoup(first_html, "html.parser")
    pages = []
    for a in soup.select(".pagination a.pagination-page, .pagination a"):
        try:
            n = int(a.get_text(strip=True))
            pages.append((n, a.get("href")))
        except Exception:
            continue
    max_page = max([n for n, _ in pages], default=1)

    # weitere Seiten holen
    for p in range(2, max_page + 1):
        url = f"{ASL_BASE}/en/empty-legs/{p}"
        html = _get(url)
        save_debug(f"asl_{p}.html", html)
        rows.extend(parse_asl_html(html))

    return rows

# ---------- DB upsert ----------
def upsert_flight_and_snapshot(rec: Dict[str, Any]) -> int:
    dep = rec["departure_ts"]
    if isinstance(dep, dt.datetime):
        dep = iso_utc(dep)
    arr = rec.get("arrival_ts")
    if isinstance(arr, dt.datetime):
        arr = iso_utc(arr)
    # Safety: arrival must be > departure and within 24h window
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

    up = (
        supabase
        .table("flights")
        .upsert(flight_payload, on_conflict="hash", returning="representation")
        .execute()
    )
    if not up.data:
        raise RuntimeError("Upsert flights returned no data")
    flight_id = up.data[0]["id"]

    # sanitize prices
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

# ---------- Orchestrator ----------
def scrape() -> List[Dict[str, Any]]:
    total: List[Dict[str, Any]] = []
    # GlobeAir
    try:
        ga = fetch_globeair_cards()
        print(f"ℹ️  GlobeAir: {len(ga)}")
        total.extend(ga)
    except Exception as e:
        print(f"❌ GlobeAir fetch error: {e}", file=sys.stderr)

    # ASL
    try:
        asl = fetch_asl_cards()
        print(f"ℹ️  ASL: {len(asl)}")
        total.extend(asl)
    except Exception as e:
        print(f"❌ ASL fetch error: {e}", file=sys.stderr)

    print(f"ℹ️  Insgesamt {len(total)} Datensätze geparst.")
    return total

def main():
    print("🔄 Starte Scraper…")
    records = scrape()
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