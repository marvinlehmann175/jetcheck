# backend/providers/eaviation.py
from __future__ import annotations

import re
import datetime as dt
from typing import List

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from providers.base import Provider
from common.http import get_html, save_debug
from common.airports import to_iata
from common.types import FlightRecord

EAVIATION_URL = "https://www.e-aviation.de/leerfluege/"
BERLIN_TZ = ZoneInfo("Europe/Berlin")

RE_CODE = re.compile(r"\(([A-Z0-9]{3,4})\)")
RE_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")  # they print ISO like 2025-08-08

def _clean_place(text: str) -> str:
    # "Stuttgart, DE (STR)" -> "Stuttgart, DE"
    return re.sub(r"\s*\([^)]+\)\s*", "", (text or "")).strip()

def _parse_date_iso(p_text: str) -> str | None:
    # "Verfügbar: 2025-08-08" -> "2025-08-08T00:00:00Z" (midnight local → UTC)
    m = RE_DATE.search(p_text or "")
    if not m:
        return None
    y, mth, d = m.group(1).split("-")
    local = dt.datetime(int(y), int(mth), int(d), 0, 0, tzinfo=BERLIN_TZ)
    # normalize to UTC ISO8601 (Z)
    return local.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class EaviationProvider(Provider):
    name = "eaviation"
    base_url = EAVIATION_URL

    def fetch_all(self) -> List[FlightRecord]:
        html = get_html(EAVIATION_URL)
        save_debug("eaviation.html", html)

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".search-hit-list-item")
        if self.debug:
            print(f"EAV items: {len(items)}")

        flights: List[FlightRecord] = []

        for item in items:
            # Route block spans
            route = item.select_one(".t-empty-leg-description")
            if not route:
                # sometimes the description may be structured slightly different
                route = item.select_one(".lift__title.t-empty-leg-description")
            if not route:
                continue

            spans = route.find_all("span")
            if len(spans) < 2:
                continue

            left_txt = spans[0].get_text(strip=True)
            right_txt = spans[-1].get_text(strip=True)

            # IATA/ICAO code in parentheses
            left_code = (RE_CODE.search(left_txt or "") or [None, None])[1]
            right_code = (RE_CODE.search(right_txt or "") or [None, None])[1]

            oi = to_iata(left_code) if left_code else None
            di = to_iata(right_code) if right_code else None

            origin_name = _clean_place(left_txt)
            dest_name = _clean_place(right_txt)

            # Date paragraph containing "Verfügbar"
            date_p = None
            for p in item.select(".search-hit-list-item-details__lift-itinerary p"):
                if "Verfügbar" in p.get_text():
                    date_p = p.get_text(" ", strip=True)
                    break
            departure_ts = _parse_date_iso(date_p or "") if date_p else None

            # Aircraft: next title row after description
            # There are multiple .lift__title-row blocks; the first is route,
            # the second typically contains aircraft name
            ac = None
            title_rows = item.select(".lift__title-row .lift__title")
            if title_rows:
                # find the first title that is NOT the route description
                for t in title_rows:
                    if "t-empty-leg-description" in t.get("class", []):
                        continue
                    ac = t.get_text(strip=True)
                    if ac:
                        break

            # Link: the button is not a normal anchor (JS), so keep the page URL as fallback
            link = EAVIATION_URL

            # Build record
            if not (oi and di and departure_ts):
                # be strict: without both codes and a date, skip to avoid bad hashes
                if self.debug:
                    print(f"skip: oi={oi} di={di} date={departure_ts} text='{left_txt} → {right_txt}'")
                continue

            rec: FlightRecord = {
                "source": "eaviation",
                "origin_iata": oi,
                "origin_name": origin_name,
                "destination_iata": di,
                "destination_name": dest_name,
                "departure_ts": departure_ts,
                "arrival_ts": None,  # not provided
                "aircraft": ac,
                "currency": "EUR",
                "status": "pending",
                "price_current": None,
                "price_normal": None,
                "discount_percent": None,
                "probability": None,
                "link": link,
                "raw": {
                    "route_left": left_txt,
                    "route_right": right_txt,
                    "date": date_p,
                },
                "raw_static": {"operator": "E-Aviation", "aircraft": ac},
            }
            flights.append(rec)

        return flights