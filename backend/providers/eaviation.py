# backend/providers/eaviation.py
from __future__ import annotations

import re
import datetime as dt
from typing import List, Optional

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from providers.base import Provider
from common.http import get_html, save_debug
from common.airports import to_iata
from common.types import FlightRecord

EAVIATION_URL = "https://www.e-aviation.de/leerfluege/"
BERLIN_TZ = ZoneInfo("Europe/Berlin")

RE_PAREN_CODE = re.compile(r"\(([A-Z0-9]{3,4})\)")
RE_DATE_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})")  # e.g. 2025-08-08
RE_SEGMENT_CODES = re.compile(r"\b([A-Z0-9]{3})\s*-\s*([A-Z0-9]{3})\b")  # STR - NUE

def _clean_place(text: Optional[str]) -> str:
    # "Stuttgart, DE (STR)" -> "Stuttgart, DE"
    if not text:
        return ""
    return re.sub(r"\s*\([^)]+\)\s*", "", text).strip()

def _to_utc_midnight(date_iso: str) -> str:
    y, mth, d = map(int, date_iso.split("-"))
    local = dt.datetime(y, mth, d, 0, 0, tzinfo=BERLIN_TZ)
    return local.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _extract_date_text(container: BeautifulSoup) -> Optional[str]:
    # look for a <p> containing "Verfügbar"
    for p in container.select(".search-hit-list-item-details__lift-itinerary p"):
        txt = p.get_text(" ", strip=True)
        if "Verfügbar" in txt:
            m = RE_DATE_ISO.search(txt)
            if m:
                return _to_utc_midnight(m.group(1))
    return None

class EaviationProvider(Provider):
    name = "eaviation"
    base_url = EAVIATION_URL

    def __init__(self, debug: bool | None = None):
        super().__init__(debug)

    def fetch_all(self) -> List[FlightRecord]:
        html = get_html(EAVIATION_URL, referer="https://www.e-aviation.de/")
        if self.debug:
            save_debug("eaviation.html", html)

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".search-hit-list-item")
        if self.debug:
            print(f"EAV items: {len(items)}")

        flights: List[FlightRecord] = []

        for item in items:
            # 1) route block: spans with city/country + codes in parens
            route = item.select_one(".t-empty-leg-description")
            if not route:
                route = item.select_one(".lift__title.t-empty-leg-description")
            if not route:
                # weird card, skip
                continue

            spans = route.find_all("span")
            if len(spans) < 2:
                # weird card, skip
                continue

            left_txt = spans[0].get_text(strip=True)
            right_txt = spans[-1].get_text(strip=True)

            # try parens first
            left_code = (RE_PAREN_CODE.search(left_txt or "") or [None, None])[1]
            right_code = (RE_PAREN_CODE.search(right_txt or "") or [None, None])[1]

            oi = to_iata(left_code) if left_code else None
            di = to_iata(right_code) if right_code else None

            # fallback: segment table like "STR - NUE"
            if not (oi and di):
                seg = item.select_one(".itinerary__segments")
                if seg:
                    m = RE_SEGMENT_CODES.search(seg.get_text(" ", strip=True))
                    if m:
                        seg_o, seg_d = m.group(1), m.group(2)
                        oi = oi or to_iata(seg_o) or seg_o
                        di = di or to_iata(seg_d) or seg_d

            origin_name = _clean_place(left_txt)
            dest_name = _clean_place(right_txt)

            # 2) date (midnight local → UTC Z)
            departure_ts = _extract_date_text(item)
            if not departure_ts:
                # no date = no good hash; skip
                if self.debug:
                    print(f"skip (no date): {left_txt} → {right_txt}")
                continue

            # 3) aircraft (2nd title row usually)
            aircraft = None
            title_rows = item.select(".lift__title-row .lift__title")
            if title_rows:
                for t in title_rows:
                    # the route has class 't-empty-leg-description'; pick the next non-route title
                    if "t-empty-leg-description" in (t.get("class") or []):
                        continue
                    aircraft = t.get_text(strip=True)
                    if aircraft:
                        break

            # No real deeplink; the button is JS-driven → keep list URL
            link = EAVIATION_URL

            if not (oi and di):
                if self.debug:
                    print(f"skip (no codes): oi={oi} di={di} for '{left_txt} → {right_txt}'")
                continue

            flights.append({
                "source": self.name,
                "origin_iata": oi,
                "origin_name": origin_name,
                "destination_iata": di,
                "destination_name": dest_name,
                "departure_ts": departure_ts,
                "arrival_ts": None,
                "aircraft": aircraft,
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
                },
                "raw_static": {"operator": "E-Aviation", "aircraft": aircraft},
            })

        return flights