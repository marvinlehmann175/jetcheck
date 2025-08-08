# backend/providers/callajet.py
from __future__ import annotations

import os
import re
import time
import datetime as dt
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from providers.base import Provider
from common.http import get_html
from common.types import FlightRecord
from common.airports import to_iata_by_name  # name→IATA resolver

PAGE_URL = "https://www.callajet.de/privatjet-fluege/"
TZ = ZoneInfo("Europe/Berlin")

RE_PRICE = re.compile(r"(\d[\d\.\,]*)")
RE_DATE_DMY = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")  # 05.08.2025
SPLIT_ROUTE = re.compile(r"\s+[–-]\s+")

def _parse_date_dmy(s: str) -> Optional[str]:
    m = RE_DATE_DMY.search(s or "")
    if not m:
        return None
    d, mth, y = map(int, m.groups())
    local = dt.datetime(y, mth, d, 0, 0, tzinfo=TZ)
    return (
        local.astimezone(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

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
    return (s or "").strip()

def _guess_iata_from_name(name: str) -> Optional[str]:
    if not name:
        return None
    code = to_iata_by_name(name)
    if code:
        return code
    tokens = re.split(r"[,/\s–-]+", name.strip())
    for cand in [tokens[0] if tokens else None, tokens[-1] if tokens else None]:
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
        """
        - lädt Seite 1
        - ermittelt max. Seitenzahl aus Pager (<ul class="pagination">)
        - folgt /page/2 ... /page/N (hart gecappt über CALLAJET_MAX_PAGES, default 5)
        """
        max_pages_env = os.getenv("CALLAJET_MAX_PAGES")
        try:
            max_pages_cap = int(max_pages_env) if max_pages_env else 5
        except Exception:
            max_pages_cap = 5

        rows: List[FlightRecord] = []

        # Seite 1
        html1 = get_html(PAGE_URL, referer=self.base_url)
        self.dbg.save_html("callajet_1.html", html1)
        soup1 = BeautifulSoup(html1, "html.parser")

        rows.extend(self._parse_cards(soup1, page_no=1))

        # Pager auslesen: finde größte Zahl in a.page-numbers
        total_pages = 1
        for a in soup1.select("ul.pagination a.page-numbers"):
            try:
                n = int(a.get_text(strip=True))
                total_pages = max(total_pages, n)
            except Exception:
                pass

        self.dbg.add(f"pager_total={total_pages}, cap={max_pages_cap}")

        # weitere Seiten, aber caps beachten
        last_page = min(total_pages, max_pages_cap)
        for p in range(2, last_page + 1):
            url = urljoin(PAGE_URL, f"./page/{p}")
            html = get_html(url, referer=PAGE_URL)
            self.dbg.save_html(f"callajet_{p}.html", html)
            soup = BeautifulSoup(html, "html.parser")
            rows.extend(self._parse_cards(soup, page_no=p))
            # kleine Höflichkeitspause
            time.sleep(0.5)

        self.dbg.add(f"parsed_total={len(rows)}")
        return rows

    def _parse_cards(self, soup: BeautifulSoup, *, page_no: int) -> List[FlightRecord]:
        cards = soup.select(".isotope-container .tmb")
        self.dbg.add(f"page[{page_no}]_cards={len(cards)}")
        out: List[FlightRecord] = []

        for i, card in enumerate(cards, start=1):
            h3 = card.select_one("h3.t-entry-title")
            if not h3:
                self.dbg.add(f"page[{page_no}] skip[{i}]: no title")
                continue
            title = h3.get_text(" ", strip=True)

            parts = SPLIT_ROUTE.split(title)
            if len(parts) < 2:
                parts = [p.strip() for p in re.split(r"\s*-\s*", title) if p.strip()]
                if len(parts) < 2:
                    self.dbg.add(f"page[{page_no}] skip[{i}]: route parse fail '{title}'")
                    continue
            origin_name = _clean_city(parts[0])
            dest_name = _clean_city(parts[-1])

            date_el = card.select_one(".t-entry-cf-acf-current_flights_date")
            departure_ts = _parse_date_dmy(date_el.get_text(strip=True)) if date_el else None

            jet_el = card.select_one(".t-entry-cf-acf-current_flights_jet")
            aircraft = None
            if jet_el:
                a = jet_el.find("a")
                aircraft = (a.get_text(strip=True) if a else jet_el.get_text(" ", strip=True))
                aircraft = re.sub(r"^\s*Jet:\s*", "", aircraft, flags=re.I).strip()

            price_el = card.select_one(".t-entry-cf-acf-current_flights_price")
            price_current = _money_to_int(price_el.get_text(" ", strip=True)) if price_el else None

            origin_iata = _guess_iata_from_name(origin_name)
            dest_iata = _guess_iata_from_name(dest_name)
            if not (origin_iata and dest_iata):
                self.dbg.add(
                    f"page[{page_no}] skip[{i}]: no IATA (origin='{origin_name}'→{origin_iata}, dest='{dest_name}'→{dest_iata})"
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
                "link": PAGE_URL,
                "raw": {
                    "title": title,
                    "date": date_el.get_text(strip=True) if date_el else None,
                    "price": price_el.get_text(" ", strip=True) if price_el else None,
                    "page": page_no,
                },
                "raw_static": {"operator": "Call a Jet", "aircraft": aircraft},
            }
            out.append(rec)

        return out