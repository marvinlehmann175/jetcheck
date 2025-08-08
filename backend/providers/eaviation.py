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

# DOM parsing helpers
RE_PAREN_CODE = re.compile(r"\(([A-Z0-9]{3,4})\)")
RE_DATE_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})")
RE_SEGMENT_CODES = re.compile(r"\b([A-Z0-9]{3})\s*-\s*([A-Z0-9]{3})\b")

# Regex fallback (works on the raw HTML even if content is JS-hydrated later)
# Matches:
#   <span class="lift__title t-empty-leg-description">
#     <span>Stuttgart, DE (STR)</span> ... <span>Nuernberg, DE (NUE)</span>
#   ...
#   Verfügbar:&nbsp;2025-08-08
RE_BLOCK = re.compile(
    r'<span[^>]*class="[^"]*\bt-empty-leg-description\b[^"]*"[^>]*>\s*'
    r'<span>(?P<left>[^<]+)</span>.*?'
    r'<span>(?P<right>[^<]+)</span>.*?'
    r'Verfügbar:&nbsp;(?P<date>\d{4}-\d{2}-\d{2})',
    re.S | re.I
)

def _clean_place(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s*\([^)]+\)\s*", "", text).strip()

def _to_utc_midnight(date_iso: str) -> str:
    y, mth, d = map(int, date_iso.split("-"))
    local = dt.datetime(y, mth, d, 0, 0, tzinfo=BERLIN_TZ)
    return local.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class EaviationProvider(Provider):
    name = "eaviation"
    base_url = EAVIATION_URL

    def __init__(self, debug: bool | None = None):
        super().__init__(debug)

    def fetch_all(self) -> List[FlightRecord]:
        html = get_html(EAVIATION_URL, referer="https://www.e-aviation.de/")
        print(html[:2000])
        if self.debug:
            save_debug("eaviation.html", html)

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".search-hit-list-item")
        if self.debug:
            print(f"EAV items: {len(items)}")

        flights: List[FlightRecord] = []

        # 1) Try DOM parsing (if SSR is present)
        if items:
            flights.extend(self._parse_dom(items))

        # 2) Fallback: regex over raw HTML if DOM is empty (CSR only)
        if not flights:
            flights.extend(self._parse_regex(html))

        return flights

    def _parse_dom(self, items) -> List[FlightRecord]:
        out: List[FlightRecord] = []
        for item in items:
            route = item.select_one(".t-empty-leg-description") or item.select_one(".lift__title.t-empty-leg-description")
            if not route:
                continue

            spans = route.find_all("span")
            if len(spans) < 2:
                continue

            left_txt = spans[0].get_text(strip=True)
            right_txt = spans[-1].get_text(strip=True)

            # Codes in parentheses
            left_code = (RE_PAREN_CODE.search(left_txt or "") or [None, None])[1]
            right_code = (RE_PAREN_CODE.search(right_txt or "") or [None, None])[1]

            oi = to_iata(left_code) if left_code else None
            di = to_iata(right_code) if right_code else None

            # Fallback: segment table like "STR - NUE"
            if not (oi and di):
                seg = item.select_one(".itinerary__segments")
                if seg:
                    m = RE_SEGMENT_CODES.search(seg.get_text(" ", strip=True))
                    if m:
                        seg_o, seg_d = m.group(1), m.group(2)
                        oi = oi or to_iata(seg_o) or seg_o
                        di = di or to_iata(seg_d) or seg_d

            # Date paragraph containing "Verfügbar"
            departure_ts = None
            for p in item.select(".search-hit-list-item-details__lift-itinerary p"):
                txt = p.get_text(" ", strip=True)
                m = RE_DATE_ISO.search(txt)
                if "Verfügbar" in txt and m:
                    departure_ts = _to_utc_midnight(m.group(1))
                    break

            aircraft = None
            title_rows = item.select(".lift__title-row .lift__title")
            if title_rows:
                for t in title_rows:
                    if "t-empty-leg-description" in (t.get("class") or []):
                        continue
                    aircraft = t.get_text(strip=True)
                    if aircraft:
                        break

            if not (oi and di and departure_ts):
                if self.debug:
                    print(f"skip (dom) oi={oi} di={di} date={departure_ts} text='{left_txt} → {right_txt}'")
                continue

            out.append(self._mk_record(oi, di, left_txt, right_txt, departure_ts, aircraft))
        return out

    def _parse_regex(self, html: str) -> List[FlightRecord]:
        out: List[FlightRecord] = []
        for m in RE_BLOCK.finditer(html):
            left_txt = m.group("left").strip()
            right_txt = m.group("right").strip()
            date_iso = m.group("date")

            # Try codes from parentheses in left/right strings
            left_code = (RE_PAREN_CODE.search(left_txt or "") or [None, None])[1]
            right_code = (RE_PAREN_CODE.search(right_txt or "") or [None, None])[1]

            oi = to_iata(left_code) if left_code else None
            di = to_iata(right_code) if right_code else None

            # As regex fallback, also try inline "AAA - BBB" somewhere nearby in HTML (optional)
            if not (oi and di):
                # Quick global search; safe since we only fallback when DOM is empty
                seg = RE_SEGMENT_CODES.search(html)
                if seg:
                    oi = oi or to_iata(seg.group(1)) or seg.group(1)
                    di = di or to_iata(seg.group(2)) or seg.group(2)

            if not (oi and di):
                if self.debug:
                    print(f"skip (rx codes) left='{left_txt}' right='{right_txt}'")
                continue

            dep_utc = _to_utc_midnight(date_iso)
            out.append(self._mk_record(oi, di, left_txt, right_txt, dep_utc, aircraft=None))
        if self.debug:
            print(f"EAV regex hits: {len(out)}")
        return out

    def _mk_record(
        self,
        oi: str,
        di: str,
        left_txt: str,
        right_txt: str,
        departure_ts: str,
        aircraft: Optional[str],
    ) -> FlightRecord:
        origin_name = _clean_place(left_txt)
        dest_name = _clean_place(right_txt)
        return {
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
            "link": EAVIATION_URL,  # button is JS-driven; keep list URL
            "raw": {
                "route_left": left_txt,
                "route_right": right_txt,
            },
            "raw_static": {"operator": "E-Aviation", "aircraft": aircraft},
        }