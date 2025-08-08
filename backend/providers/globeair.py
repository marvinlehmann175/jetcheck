# providers/globeair.py
import re
import datetime as dt
from typing import Dict, Any, List, Optional

from bs4 import BeautifulSoup

from common.http import SESSION, COMMON_HEADERS, save_debug, DEBUG
from providers.base import Provider
from common.types import FlightRecord
from common.airports import to_iata, to_names

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
    """GlobeAir liefert lokale Strings ohne TZ → als naive ISO+Z zurück (später DB prüft)."""
    if not (date_str and time_str):
        return None
    try:
        from dateutil import parser as dtparser  # local import to keep provider self-contained
        d = dtparser.parse(date_str)
        t = dtparser.parse(time_str, default=d)
        t = t.replace(tzinfo=None)  # naive
        return t.replace(microsecond=0).isoformat() + "Z"
    except Exception:
        return None


def _pretty_name(iata: Optional[str], fallback: Optional[str]) -> Optional[str]:
    if not iata:
        return fallback
    name, city, _country = to_names(iata)
    return name or city or fallback


def parse_globeair_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cols = soup.select(".columns .column")
    if DEBUG:
        print(f"GA: .columns .column => {len(cols)}")
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
        raw_origin_name, origin_code_raw, raw_dest_name, dest_code_raw = m.groups()

        # normalize to IATA and skip if unknown
        oi = to_iata(origin_code_raw)
        di = to_iata(dest_code_raw)
        if not oi or not di:
            if DEBUG:
                print(f"⚠️  GlobeAir skip (unknown code): {origin_code_raw} -> {dest_code_raw}")
            continue

        # nice names (fallback to parsed names)
        origin_name = _pretty_name(oi, raw_origin_name)
        dest_name   = _pretty_name(di, raw_dest_name)

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
            "origin_iata": oi,
            "origin_name": origin_name,
            "destination_iata": di,
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


class GlobeAirProvider(Provider):
    def fetch(self, timeout: int = 25) -> List[Dict[str, Any]]:
        r = SESSION.get(
            GLOBEAIR_URL,
            headers={**COMMON_HEADERS, "Referer": "https://www.globeair.com/"},
            timeout=timeout,
        )
        if DEBUG:
            print(f"GA status={r.status_code}, len={len(r.text)}")
        r.raise_for_status()
        save_debug("globeair.html", r.text)
        return parse_globeair_html(r.text)