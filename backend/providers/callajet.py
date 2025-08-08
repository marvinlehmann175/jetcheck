# backend/providers/callajet.py
from __future__ import annotations

import re
import datetime as dt
from typing import List, Optional

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from providers.base import Provider
from common.http import get_html
from common.types import FlightRecord
from common.airports import to_iata_by_name  # ✅ use name→IATA resolver

PAGE_URL = "https://www.callajet.de/privatjet-fluege/"
TZ = ZoneInfo("Europe/Berlin")

RE_PRICE = re.compile(r"(\d[\d\.\,]*)")
RE_DATE_DMY = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")  # 05.08.2025
# Titles look like "Munich – Tavaux" (en dash or hyphen variations)
SPLIT_ROUTE = re.compile(r"\s+[–-]\s+")

def _parse_date_dmy(s: str) -> Optional[str]:
    m = RE_DATE_DMY.search(s or "")
    if not m:
        return None
    d, mth, y = map(int, m.groups())
    local = dt.datetime(y, mth, d, 0, 0, tzinfo=TZ)
    return local.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _money_to_int(s: str) -> Optional[int]:
    m = RE_PRICE.search(s or "")
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        return int(float(raw))
    except Exception:
        return None

def _clean_city(s: str) -> str:
    # remove extra whitespace etc.
    return (s or "").strip()

def _guess_iata_from_name(name: str) -> Optional[str]:
    """
    Map a free-text city/airport name to an IATA code:
    1) direct lookup: to_iata_by_name(name)
    2) try first/last token
    3) last resort: 3-letter uppercase slice if alphabetic (keeps out digits/garbage)
    """
    if not name:
        return None
    code = to_iata_by_name(name)
    if code:
        return code
    tokens = re.split(r"[,\\s/–-]+", name.strip())
    candidates = []
    if tokens:
        candidates.append(tokens[0])
        candidates.append(tokens[-1])
    for cand in candidates:
        if not cand:
            continue
        code = to_iata_by_name(cand)
        if code:
            return code
    rough = name[:3].upper()
    return rough if rough.isalpha() and len(rough) == 3 else None

class CallajetProvider(Provider):
    name = "callajet"
    base_url = "https://www.callajet.de/"

    def fetch_all(self) -> List[FlightRecord]:
        html = get_html(PAGE_URL, referer=self.base_url)
        self.dbg.save_html("callajet.html", html)

        soup = BeautifulSoup(html, "html.parser")
        # Each flight card is a .tmb inside .isotope-container
        cards = soup.select(".isotope-container .tmb")
        self.dbg.add(f"cards={len(cards)}")

        out: List[FlightRecord] = []
        for i, card in enumerate(cards):
            # title: h3.t-entry-title e.g. "Munich – Tavaux"
            h3 = card.select_one("h3.t-entry-title")
            if not h3:
                continue
            title = h3.get_text(" ", strip=True)

            parts = SPLIT_ROUTE.split(title)
            if len(parts) < 2:
                # try simple split as fallback
                parts = [p.strip() for p in re.split(r"\s*-\s*", title) if p.strip()]
                if len(parts) < 2:
                    self.dbg.add(f"skip[{i}]: route parse fail '{title}'")
                    continue
            origin_name = _clean_city(parts[0])
            dest_name   = _clean_city(parts[-1])

            # date: .t-entry-cf-acf-current_flights_date e.g. 05.08.2025
            date_el = card.select_one(".t-entry-cf-acf-current_flights_date")
            departure_ts = _parse_date_dmy(date_el.get_text(strip=True)) if date_el else None

            # aircraft: in “Jet:” row (optional link or text)
            jet_el = card.select_one(".t-entry-cf-acf-current_flights_jet")
            aircraft = None
            if jet_el:
                # either "<strong>Jet: </strong>Text" or contains <a>
                a = jet_el.find("a")
                aircraft = (a.get_text(strip=True) if a else jet_el.get_text(" ", strip=True))
                aircraft = re.sub(r"^\s*Jet:\s*", "", aircraft, flags=re.I).strip()

            # price: “Price: 13.500€” -> number only
            price_el = card.select_one(".t-entry-cf-acf-current_flights_price")
            price_current = _money_to_int(price_el.get_text(" ", strip=True)) if price_el else None

            # Map names → IATA using airports index (with sane fallbacks)
            origin_iata = _guess_iata_from_name(origin_name)
            dest_iata   = _guess_iata_from_name(dest_name)
            if not (origin_iata and dest_iata):
                self.dbg.add(
                    f"skip[{i}]: no IATA (origin='{origin_name}'→{origin_iata}, dest='{dest_name}'→{dest_iata})"
                )
                continue

            rec: FlightRecord = {
                "source": self.name,
                "origin_iata": origin_iata,
                "origin_name": origin_name,
                "destination_iata": dest_iata,
                "destination_name": dest_name,
                "departure_ts": departure_ts,
                "arrival_ts": None,
                "aircraft": aircraft,
                "currency": "EUR",
                "status": "pending",
                "price_current": price_current,
                "price_normal": None,
                "discount_percent": None,
                "probability": None,
                "link": PAGE_URL,  # no per-card link; keep page link
                "raw": {
                    "title": title,
                    "date": date_el.get_text(strip=True) if date_el else None,
                    "price": price_el.get_text(" ", strip=True) if price_el else None,
                },
                "raw_static": {"operator": "Call a Jet", "aircraft": aircraft},
            }
            out.append(rec)

        self.dbg.add(f"parsed={len(out)}")
        return out