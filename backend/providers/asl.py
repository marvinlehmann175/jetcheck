# providers/asl.py
from __future__ import annotations
import re
import datetime as dt
from typing import List, Optional
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from zoneinfo import ZoneInfo

from providers.base import Provider
from common.http import get_html
from common.types import FlightRecord
from common.airports import to_iata  # maps IATA/ICAO -> IATA

ASL_BASE = "https://www.aslgroup.eu"
ASL_FIRST = f"{ASL_BASE}/en/empty-legs"

ASL_TZ = ZoneInfo("Europe/Brussels")
RE_DATE = re.compile(r"(\d{2}-\d{2}-\d{4})")
RE_TIME = re.compile(r"(\d{1,2}:\d{2})")

def _clean_place_name(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", text)).strip()

def _parse_asl_datetime(date_s: str, time_s: str) -> Optional[str]:
    try:
        # Be explicit: DD-MM-YYYY
        d = dtparser.parse(date_s, dayfirst=True)
        t = dtparser.parse(time_s, default=d)
        local = dt.datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=ASL_TZ)
        return local.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None

def _pick_code_pref_iata(text: Optional[str]) -> Optional[str]:
    """
    Find all codes inside parentheses and choose:
      - last IATA (3 chars) if present
      - else last ICAO (4 chars), mapped to IATA if possible
    """
    if not text:
        return None
    parens = re.findall(r"\(([A-Za-z0-9]{2,5})\)", text)
    if not parens:
        return None
    parens = [p.strip().upper() for p in parens]
    iatas = [p for p in parens if len(p) == 3]
    if iatas:
        return to_iata(iatas[-1]) or iatas[-1]
    icaos = [p for p in parens if len(p) == 4]
    if icaos:
        mapped = to_iata(icaos[-1])  # ICAO -> IATA if known
        return mapped or icaos[-1]
    last = parens[-1]
    return to_iata(last) or last

class ASLProvider(Provider):
    name = "asl"
    base_url = "https://www.aslgroup.eu/"

    def __init__(self, debug: bool | None = None, debug_dir: str | None = None):
        super().__init__(debug=debug, debug_dir=debug_dir)

    def fetch_all(self) -> List[FlightRecord]:
        rows: List[FlightRecord] = []

        first = get_html(ASL_FIRST, referer=self.base_url)
        self.dbg.add(f"asl_first_bytes={len(first)}")
        self.dbg.save_html("asl_1.html", first)
        rows.extend(self._parse(first))

        # pagination
        soup = BeautifulSoup(first, "html.parser")
        pages = []
        for a in soup.select(".pagination a.pagination-page, .pagination a"):
            try:
                n = int(a.get_text(strip=True))
                pages.append(n)
            except Exception:
                pass
        max_page = max(pages or [1])

        for p in range(2, max_page + 1):
            url = f"{ASL_BASE}/en/empty-legs/{p}"
            html = get_html(url, referer=self.base_url)
            self.dbg.save_html(f"asl_{p}.html", html)
            rows.extend(self._parse(html))

        return rows

    def _parse(self, html: str) -> List[FlightRecord]:
        soup = BeautifulSoup(html, "html.parser")
        arts = soup.select("article.plane")
        self.dbg.add(f"asl_items={len(arts)}")
        out: List[FlightRecord] = []

        for idx, art in enumerate(arts):
            ac_el = art.select_one(".plane-name")
            aircraft = ac_el.get_text(strip=True) if ac_el else None

            head = art.select_one(".plane-headline") or art.select_one(".leading-headline")
            if not head:
                self.dbg.add(f"skip[{idx}]: no headline")
                continue

            # Try explicit left/right spans first
            spans = head.find_all("span")
            left_txt = spans[0].get_text(" ", strip=True) if len(spans) >= 1 else None
            right_txt = spans[-1].get_text(" ", strip=True) if len(spans) >= 2 else None

            if not (left_txt and right_txt):
                # fallback: split by arrow or dash
                txt = head.get_text("→", strip=True)
                parts = [p.strip() for p in re.split(r"[→\-]", txt) if p.strip()]
                if len(parts) >= 2:
                    left_txt, right_txt = parts[0], parts[-1]

            if not (left_txt and right_txt):
                self.dbg.add(f"skip[{idx}]: route parse fail")
                continue

            origin_name = _clean_place_name(left_txt)
            dest_name   = _clean_place_name(right_txt)
            origin_iata = _pick_code_pref_iata(left_txt) or (origin_name[:3].upper() if origin_name else None)
            dest_iata   = _pick_code_pref_iata(right_txt) or (dest_name[:3].upper() if dest_name else None)

            # date + time
            date_li = time_li = None
            for li in art.select("ul.plane-specs li"):
                t = li.get_text(" ", strip=True)
                if RE_DATE.search(t):
                    date_li = t
                if RE_TIME.search(t):
                    time_li = t
            dm = RE_DATE.search(date_li or "")
            tm = RE_TIME.search(time_li or "")
            departure_ts = _parse_asl_datetime(dm.group(1), tm.group(1)) if (dm and tm) else None

            # link
            a = art.select_one("a.button, a.button-full, a.button-primary, a[href]")
            link = a.get("href") if a else None
            if link and link.startswith("/"):
                link = ASL_BASE + link

            out.append({
                "source": self.name,
                "origin_iata": origin_iata,
                "origin_name": origin_name,
                "destination_iata": dest_iata,
                "destination_name": dest_name,
                "departure_ts": departure_ts,
                "arrival_ts": None,
                "status": "pending",
                "price_current": None,
                "price_normal": None,
                "discount_percent": None,
                "probability": None,
                "currency": "EUR",
                "link": link,
                "raw": {
                    "headline_left": left_txt,
                    "headline_right": right_txt,
                    "date": date_li,
                    "time": time_li
                },
                "raw_static": {"operator": "ASL", "aircraft": aircraft},
                "aircraft": aircraft,
            })
        return out