# backend/providers/eaviation.py
from __future__ import annotations

import os
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
RE_DATE_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})")  # "Verfügbar: 2025-08-08"

def _clean_place(text: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*", "", (text or "")).strip()

def _date_to_iso_utc(date_iso: str | None) -> str | None:
    if not date_iso:
        return None
    y, m, d = map(int, date_iso.split("-"))
    local = dt.datetime(y, m, d, 0, 0, tzinfo=BERLIN_TZ)
    return local.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _parse_items(html: str, debug_name: str | None = None, debug: bool = False) -> List[FlightRecord]:
    """
    Parse E-Aviation/Avinode widget markup into FlightRecords.
    Works for:
      - <div class="search-hit-list-item"> ... (widget markup)
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(".search-hit-list-item")
    if debug:
        print(f"EAV items: {len(items)}")

    flights: List[FlightRecord] = []

    for item in items:
        # Route (two spans inside .t-empty-leg-description)
        route = item.select_one(".t-empty-leg-description")
        if not route:
            continue
        spans = route.find_all("span")
        if len(spans) < 2:
            continue

        left_txt = spans[0].get_text(strip=True)
        right_txt = spans[-1].get_text(strip=True)

        left_code = (RE_CODE.search(left_txt or "") or [None, None])[1]
        right_code = (RE_CODE.search(right_txt or "") or [None, None])[1]

        oi = to_iata(left_code) if left_code else None
        di = to_iata(right_code) if right_code else None

        origin_name = _clean_place(left_txt)
        dest_name = _clean_place(right_txt)

        # Date paragraph containing "Verfügbar"
        date_iso = None
        for p in item.select(".search-hit-list-item-details__lift-itinerary p"):
            txt = p.get_text(" ", strip=True)
            if "Verfügbar" in txt:
                m = RE_DATE_ISO.search(txt)
                if m:
                    date_iso = m.group(1)
                    break
        departure_ts = _date_to_iso_utc(date_iso) if date_iso else None

        # Aircraft (the next title row after description)
        ac = None
        # There are multiple .lift__title-row elements; the non-description one is the aircraft
        for row in item.select(".lift__title-row"):
            cls = " ".join(row.get("class", []))
            # find .lift__title without 't-empty-leg-description'
            t = row.select_one(".lift__title")
            if not t:
                continue
            if "t-empty-leg-description" in t.get("class", []):
                continue
            ac = t.get_text(strip=True)
            if ac:
                break

        # Link: their button is JS-driven; fallback to list page
        link = EAVIATION_URL

        if not (oi and di and departure_ts):
            if debug:
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
                "date": date_iso,
            },
            "raw_static": {"operator": "E-Aviation", "aircraft": ac},
        }
        flights.append(rec)

    return flights

class EaviationProvider(Provider):
    name = "eaviation"
    base_url = EAVIATION_URL

    def fetch_all(self) -> List[FlightRecord]:
        # 1) Try server HTML
        html = get_html(EAVIATION_URL)
        save_debug("eaviation.html", html)
        flights = _parse_items(html, "eaviation.html", self.debug)
        if flights:
            return flights

        # 2) Try to find an Avinode iframe and fetch its src directly
        soup = BeautifulSoup(html, "html.parser")
        iframe = soup.select_one('iframe[src*="avinode"], iframe[src*="market"], iframe[src*="widget"]')
        if iframe and iframe.get("src"):
            iframe_src = iframe["src"]
            try:
                iframe_html = get_html(iframe_src, referer=EAVIATION_URL)
                save_debug("eaviation_iframe.html", iframe_html)
                flights = _parse_items(iframe_html, "eaviation_iframe.html", self.debug)
                if flights:
                    return flights
            except Exception as e:
                if self.debug:
                    print(f"EAV iframe fetch error: {e}")

        # 3) Optional: headless render via Playwright if enabled
        if os.getenv("ENABLE_BROWSER", "0") == "1":
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    ctx = browser.new_context()
                    page = ctx.new_page()
                    page.goto(EAVIATION_URL, wait_until="networkidle", timeout=45000)
                    rendered = page.content()
                    browser.close()
                save_debug("eaviation_rendered.html", rendered)
                flights = _parse_items(rendered, "eaviation_rendered.html", self.debug)
                return flights
            except Exception as e:
                if self.debug:
                    print(f"EAV Playwright render error: {e}")

        # Nothing found
        return []