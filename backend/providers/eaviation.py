# backend/providers/eaviation.py
from __future__ import annotations

import re
import datetime as dt
from typing import List, Optional

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from providers.base import Provider
from common.http import get_html
from common.airports import to_iata
from common.types import FlightRecord

EAVIATION_URL = "https://www.e-aviation.de/leerfluege/"
BERLIN_TZ = ZoneInfo("Europe/Berlin")

RE_CODE = re.compile(r"\(([A-Z0-9]{3,4})\)")
RE_DATE_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})")  # 2025-08-08
RE_EMBEDDED_JSON = re.compile(r'"emptyLegs"\s*:\s*(\[[\s\S]*?\])')  # hopeful fallback

def _clean_place(text: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*", "", (text or "")).strip()

def _departure_from_date_iso(date_text: str) -> Optional[str]:
    m = RE_DATE_ISO.search(date_text or "")
    if not m:
        return None
    y, mth, d = m.group(1).split("-")
    local = dt.datetime(int(y), int(mth), int(d), 0, 0, tzinfo=BERLIN_TZ)
    return local.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class EaviationProvider(Provider):
    name = "eaviation"
    base_url = EAVIATION_URL

    def fetch_all(self) -> List[FlightRecord]:
        html = get_html(EAVIATION_URL)
        self.dbg.save_text("eaviation.html", html)
        soup = BeautifulSoup(html, "html.parser")

        # 1) Try server-rendered list (unlikely, but cheap check)
        items = soup.select(".search-hit-list-item")
        self.dbg.log("items_ssr", len(items))

        if items:
            recs = self._parse_items(items)
            if recs:
                return recs

        # 2) Try <noscript> (sometimes widgets dump fallback HTML there)
        noscripts = soup.find_all("noscript")
        for ns in noscripts:
            ns_soup = BeautifulSoup(ns.string or "", "html.parser")
            ns_items = ns_soup.select(".search-hit-list-item")
            if ns_items:
                self.dbg.log("noscript_items", len(ns_items))
                recs = self._parse_items(ns_items)
                if recs:
                    return recs

        # 3) Try embedded JSON patterns we can parse without JS
        m = RE_EMBEDDED_JSON.search(html)
        if m:
            self.dbg.log("embedded_json_detected", True)
            # You could add a real JSON parser here if/when we learn their schema.

        # Nothing usable without JS → return empty, don’t fail builds.
        self.dbg.log("js_rendered_skip", True)
        return []

    def _parse_items(self, items) -> List[FlightRecord]:
        flights: List[FlightRecord] = []
        for item in items:
            # Route
            route = item.select_one(".t-empty-leg-description") or item.select_one(".lift__title.t-empty-leg-description")
            if not route:
                continue
            spans = route.find_all("span")
            if len(spans) < 2:
                continue
            left_txt = spans[0].get_text(strip=True)
            right_txt = spans[-1].get_text(strip=True)

            # Codes (IATA/ICAO) → IATA
            left_code = (RE_CODE.search(left_txt or "") or [None, None])[1]
            right_code = (RE_CODE.search(right_txt or "") or [None, None])[1]
            oi = to_iata(left_code) if left_code else None
            di = to_iata(right_code) if right_code else None

            origin_name = _clean_place(left_txt)
            dest_name = _clean_place(right_txt)

            # Date (look for “Verfügbar: YYYY-MM-DD” nearby)
            date_text = None
            for p in item.select(".search-hit-list-item-details__lift-itinerary p"):
                if "Verfügbar" in p.get_text():
                    date_text = p.get_text(" ", strip=True)
                    break
            departure_ts = _departure_from_date_iso(date_text or "") if date_text else None

            # Aircraft (second title row)
            aircraft = None
            title_rows = item.select(".lift__title-row .lift__title")
            if title_rows:
                for t in title_rows:
                    # skip the route description node (has the t-empty-leg-description class)
                    classes = t.get("class", [])
                    if "t-empty-leg-description" in classes:
                        continue
                    text = t.get_text(strip=True)
                    if text:
                        aircraft = text
                        break

            # link fallback: page URL; their button uses JS
            link = EAVIATION_URL

            if not (oi and di and departure_ts):
                # strict: avoid creating ambiguous hashes
                self.dbg.log("skip_incomplete", {
                    "oi": oi, "di": di, "date": departure_ts,
                    "route": f"{left_txt} → {right_txt}",
                })
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
                    "date": date_text,
                },
                "raw_static": {"operator": "E-Aviation", "aircraft": aircraft},
            })
        return flights