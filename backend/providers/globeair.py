# providers/globeair.py
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from providers.base import Provider
from common.http import get_text
from common.types import FlightRecord

from datetime import timezone
from zoneinfo import ZoneInfo
from dateutil import parser as dtparser

from common.airports import get_tz

GLOBEAIR_URL = "https://www.globeair.com/empty-leg-flights"

RE_GA_TITLE = re.compile(r"^\s*(.+?)\s*\(([A-Z]{3})\)\s*→\s*(.+?)\s*\(([A-Z]{3})\)\s*$")
RE_GA_TIME  = re.compile(r"^\s*([0-9: ]+[AP]M)\s*→\s*([0-9: ]+[AP]M)\s*$")
RE_PCT      = re.compile(r"-?(\d+)%")
RE_MONEY    = re.compile(r"(\d[\d.,]*)")


def _clean_money(text: Optional[str]):
    if not text:
        return None
    m = RE_MONEY.search(text)
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


def _to_utc_iso(date_str: Optional[str], time_str: Optional[str], tz_name: Optional[str]) -> Optional[str]:
    """
    Convert local date+time (e.g. 'August 16, 2025' + '6:50 AM') in tz_name
    to a UTC ISO string ending with 'Z'.
    """
    if not (date_str and time_str and tz_name):
        return None
    try:
        naive = dtparser.parse(f"{date_str} {time_str}")  # naive, calendar time
        try:
            tz = ZoneInfo(tz_name)  # can raise if tz_name invalid
        except Exception:
            return None
        local = naive.replace(tzinfo=tz)                   # attach correct tz
        utc   = local.astimezone(timezone.utc)
        return utc.isoformat().replace("+00:00", "Z")
    except Exception:
        return None

class GlobeAirProvider(Provider):
    name = "globeair"
    base_url = "https://www.globeair.com/"

    def __init__(self, debug: bool | None = None, debug_dir: str | None = None):
        super().__init__(debug=debug, debug_dir=debug_dir)

    def fetch_all(self) -> List[FlightRecord]:
        html = get_text(GLOBEAIR_URL, headers={"Referer": self.base_url})
        self.dbg.save_html("globeair.html", html)
        self.dbg.add(f"fetched_bytes={len(html)}")
        return self._parse(html)  # <-- this exists again

    def _parse(self, html: str) -> List[FlightRecord]:
        soup = BeautifulSoup(html, "html.parser")
        cols = soup.select(".columns .column")
        if not cols:
            cols = soup.select("div.column")
        self.dbg.add(f"ga_cols={len(cols)}")

        rows: List[FlightRecord] = []
        seen_keys: set[tuple[str, str, str | None, str | None, str | None]] = set()

        for idx, col in enumerate(cols):
            h3 = col.select_one("h3.caption")
            p  = col.select_one("p.flightdata")
            if not h3 or not p:
                if self.debug:
                    self.dbg.add(f"skip[{idx}]=no_caption_or_flightdata")
                continue

            title = h3.get_text(" ", strip=True)
            m = RE_GA_TITLE.match(title)
            if not m:
                if self.debug:
                    self.dbg.add(f"skip[{idx}]=title_nomatch '{title}'")
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

            tz_o = get_tz(origin_iata) or "Europe/Vienna"  # safe fallback within EU
            tz_d = get_tz(dest_iata) or tz_o

            departure_ts = _to_utc_iso(date_line, dep_time, tz_o) if dep_time else None
            arrival_ts   = _to_utc_iso(date_line, arr_time, tz_d) if arr_time else None

            # default pending; bump to available if a priced "Book" button is present
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
                    status = "available"

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
                href = a0.get("href")
                link = urljoin(self.base_url, href) if href else None

            # ---------- NEW: de-dupe per card ----------
            # normalize link a bit to avoid duplicates from tracking params
            link_key = None
            if link:
                # keep only scheme+netloc+path; drop query/fragment
                from urllib.parse import urlsplit, urlunsplit
                s = urlsplit(link)
                link_key = urlunsplit((s.scheme, s.netloc, s.path, "", ""))

            key = (origin_iata, dest_iata, departure_ts, arrival_ts, link_key)
            if key in seen_keys:
                if self.debug:
                    self.dbg.add(f"skip[{idx}]=duplicate_card {key}")
                continue
            seen_keys.add(key)
            # ------------------------------------------

            rows.append({
                "source": self.name,
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
                    "info": info_line,
                },
                "raw_static": {"operator": "GlobeAir"},
                "aircraft": None,
            })

        self.dbg.add(f"parsed={len(rows)}")
        return rows