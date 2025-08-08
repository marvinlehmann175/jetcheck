# providers/eaviation.py
import re
import datetime as dt
from typing import List

from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from zoneinfo import ZoneInfo

from providers.base import Provider
from common.http import get_html, save_debug
from common.types import FlightRecord
from common.airports import to_iata

EAV_BASE = "https://www.e-aviation.de"
EAV_URL  = f"{EAV_BASE}/leerfluege/"

# Example bits:
#   "Stuttgart, DE (STR) … Nuernberg, DE (NUE)"
RE_CODE = re.compile(r"\(([A-Z0-9]{3,4})\)")
RE_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")  # "Verfügbar: 2025-08-08"

# Site shows only a DATE (no exact dep time). Use a neutral local noon to avoid TZ pitfalls.
DEFAULT_TZ = ZoneInfo("Europe/Berlin")
DEFAULT_HOUR = 12
DEFAULT_MIN = 0


class EaviationProvider(Provider):
    name = "eaviation"

    def fetch_all(self) -> List[FlightRecord]:
        html = get_html(EAV_URL, referer=EAV_BASE + "/")
        save_debug("eaviation.html", html)
        return self._parse(html)

    def _parse(self, html: str) -> List[FlightRecord]:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".search-hit-list .search-hit-list-item")
        rows: List[FlightRecord] = []

        for it in items:
            # Route line (two <span> inside .t-empty-leg-description)
            route_el = it.select_one(".t-empty-leg-description")
            if not route_el:
                continue
            spans = route_el.select("span")
            if len(spans) < 2:
                continue
            left_txt = spans[0].get_text(" ", strip=True)
            right_txt = spans[-1].get_text(" ", strip=True)

            # Codes (prefer IATA (3) even if 4-char ICAO appears; Airports resolver will normalize)
            def pick_code(s: str) -> str | None:
                m = RE_CODE.search(s or "")
                if not m:
                    return None
                return to_iata(m.group(1))  # will convert ICAO->IATA if we have it; else pass-through

            origin_iata = pick_code(left_txt) or None
            dest_iata   = pick_code(right_txt) or None

            # Human names (strip trailing “(XXX)”)
            def clean_name(s: str) -> str:
                base = RE_CODE.sub("", s or "").strip()
                return re.sub(r"\s{2,}", " ", base)

            origin_name = clean_name(left_txt)
            dest_name   = clean_name(right_txt)

            # Date (no time on page)
            # <p>Verfügbar: 2025-08-08</p>
            date_p = None
            for p in it.select("p"):
                txt = p.get_text(" ", strip=True)
                if "Verfügbar" in txt:
                    date_p = txt
                    break
            dep_iso = None
            if date_p:
                dm = RE_DATE.search(date_p)
                if dm:
                    try:
                        d = dtparser.parse(dm.group(1))
                        local_noon = dt.datetime(d.year, d.month, d.day, DEFAULT_HOUR, DEFAULT_MIN, tzinfo=DEFAULT_TZ)
                        dep_iso = local_noon.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
                    except Exception:
                        dep_iso = None

            # Aircraft (second .lift__title-row usually holds model)
            ac = None
            title_rows = it.select(".lift__title-row .lift__title")
            if title_rows:
                ac = title_rows[-1].get_text(" ", strip=True)

            # Link: there’s only an “Anfragen” button without href → keep None or fallback to site root
            link = None

            # Build record
            if not (origin_iata and dest_iata and dep_iso):
                # If an IATA code is missing, try a last-ditch fallback: take first 3 letters of name
                origin_iata = origin_iata or (origin_name[:3].upper() if origin_name else None)
                dest_iata   = dest_iata   or (dest_name[:3].upper() if dest_name else None)

            rec: FlightRecord = {
                "source": self.name,
                "origin_iata": origin_iata,
                "origin_name": origin_name,
                "destination_iata": dest_iata,
                "destination_name": dest_name,
                "departure_ts": dep_iso,   # required by DB: we supply local noon on that date
                "arrival_ts": None,        # not provided
                "status": "pending",
                "currency": "EUR",
                "link": link,
                "price_current": None,
                "price_normal": None,
                "discount_percent": None,
                "probability": None,
                "raw": {
                    "route_left": left_txt,
                    "route_right": right_txt,
                    "date_line": date_p,
                },
                "raw_static": {"operator": "e-aviation", "aircraft": ac},
                "aircraft": ac,
            }
            rows.append(rec)

        return rows