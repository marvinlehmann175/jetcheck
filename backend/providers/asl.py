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

ASL_BASE = "https://www.aslgroup.eu"
ASL_FIRST = f"{ASL_BASE}/en/empty-legs"

ASL_TZ = ZoneInfo("Europe/Brussels")
RE_DATE = re.compile(r"(\d{2}-\d{2}-\d{4})")
RE_TIME = re.compile(r"(\d{1,2}:\d{2})")
RE_CODE = re.compile(r"\(([A-Za-z0-9]{3,4})\)")

def _clean_place_name(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*", " ", text or "").strip()

def _parse_asl_datetime(date_s: str, time_s: str) -> str | None:
    try:
        d = dtparser.parse(date_s)  # 09-08-2025
        t = dtparser.parse(time_s, default=d)
        local = dt.datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=ASL_TZ)
        return local.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None

class ASLProvider(Provider):
    name = "asl"

    def fetch_all(self) -> List[FlightRecord]:
        rows: List[FlightRecord] = []

        first = get_html(ASL_FIRST, referer=ASL_BASE + "/")
        save_debug("asl_1.html", first)
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
            html = get_html(url, referer=ASL_BASE + "/")
            save_debug(f"asl_{p}.html", html)
            rows.extend(self._parse(html))

        return rows

    def _parse(self, html: str) -> List[FlightRecord]:
        soup = BeautifulSoup(html, "html.parser")
        arts = soup.select("article.plane")
        out: List[FlightRecord] = []

        for art in arts:
            ac_el = art.select_one(".plane-name")
            aircraft = ac_el.get_text(strip=True) if ac_el else None

            head = art.select_one(".plane-headline") or art.select_one(".leading-headline")
            if not head:
                continue
            left_txt, right_txt = None, None
            spans = head.select("span")
            if len(spans) >= 2:
                left_txt  = spans[0].get_text(" ", strip=True)
                right_txt = spans[-1].get_text(" ", strip=True)
            else:
                txt = head.get_text("→", strip=True)
                parts = [p.strip() for p in re.split(r"[→\-]", txt) if p.strip()]
                if len(parts) >= 2:
                    left_txt, right_txt = parts[0], parts[-1]
            if not (left_txt and right_txt):
                continue

            def pick_iata(s: str | None) -> str | None:
                if not s: return None
                m = RE_CODE.search(s)
                if not m: return None
                return to_iata(m.group(1))  # ICAO→IATA if possible

            origin_iata = pick_iata(left_txt)
            dest_iata   = pick_iata(right_txt)
            origin_name = _clean_place_name(left_txt)
            dest_name   = _clean_place_name(right_txt)

            date_li = time_li = None
            for li in art.select("ul.plane-specs li"):
                txt = li.get_text(" ", strip=True)
                if RE_DATE.search(txt): date_li = txt
                if RE_TIME.search(txt): time_li = txt
            dm = RE_DATE.search(date_li or "")
            tm = RE_TIME.search(time_li or "")
            departure_ts = _parse_asl_datetime(dm.group(1), tm.group(1)) if (dm and tm) else None

            a = art.select_one("a.button, a.button-full, a.button-primary, a[href]")
            link = a.get("href") if a else None
            if link and link.startswith("/"):
                link = ASL_BASE + link

            out.append({
                "source": self.name,
                "origin_iata": origin_iata or (origin_name[:3].upper() if origin_name else None),
                "origin_name": origin_name,
                "destination_iata": dest_iata or (dest_name[:3].upper() if dest_name else None),
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
                "raw": {"headline_left": left_txt, "headline_right": right_txt, "date": date_li, "time": time_li},
                "raw_static": {"operator": "ASL", "aircraft": aircraft},
                "aircraft": aircraft,
            })
        return out