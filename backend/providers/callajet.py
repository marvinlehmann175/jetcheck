# backend/providers/callajet.py
from __future__ import annotations

import re
import datetime as dt
from typing import List, Optional

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from providers.base import Provider
from common.http import get_html
from common.types import FlightRecord
from common.airports import to_iata

CALLAJET_URL = "https://www.callajet.de/privatjet-leerfluege/"
LOCAL_TZ = ZoneInfo("Europe/Berlin")  # grobe Annahme – kann je nach Quelle variieren

# Hilfs-Regex
RE_CODE = re.compile(r"\(([A-Z0-9]{3,4})\)")
RE_DATE_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})")           # 2025-08-09
RE_DATE_DMY = re.compile(r"(\d{1,2}\.\d{1,2}\.\d{4})")     # 09.08.2025
RE_TIME = re.compile(r"(\d{1,2}:\d{2})")                   # 14:35
RE_ROUTE_ARROW = re.compile(r"\s*[→\-]\s*")                # trennt "IBZ → ZRH" o.ä.

def _clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

def _strip_parens(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*", "", text or "").strip()

def _pick_code_pref_iata(text: str) -> Optional[str]:
    m = RE_CODE.search(text or "")
    if not m:
        return None
    return to_iata(m.group(1)) or m.group(1)

def _to_utc_iso(date_s: Optional[str], time_s: Optional[str]) -> Optional[str]:
    """Baue UTC-ISO aus (Datum[, Uhrzeit]) unter Annahme LOCAL_TZ."""
    if not date_s:
        return None
    # Datumsformat erkennen
    y, m, d = None, None, None
    if RE_DATE_ISO.search(date_s or ""):
        y, m, d = date_s.split("-")
    else:
        m_dmy = RE_DATE_DMY.search(date_s or "")
        if m_dmy:
            dd, mm, yyyy = m_dmy.group(1).split(".")
            y, m, d = yyyy, mm, dd
    if not (y and m and d):
        return None

    hh, mm = 0, 0
    tm = RE_TIME.search(time_s or "")
    if tm:
        hh, mm = tm.group(1).split(":")
    try:
        local = dt.datetime(int(y), int(m), int(d), int(hh), int(mm), tzinfo=LOCAL_TZ)
        return local.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return None

class CallaJetProvider(Provider):
    name = "callajet"
    base_url = "https://www.callajet.de/"

    def __init__(self, debug: bool | None = None, debug_dir: str | None = None):
        super().__init__(debug, debug_dir)

    def fetch_all(self) -> List[FlightRecord]:
        # 1) HTML laden & debug speichern
        html = get_html(CALLAJET_URL, referer=self.base_url)
        self.dbg.save_html("callajet.html", html)

        # 2) Parsen
        flights = self._parse(html)
        self.dbg.add_kv("items_parsed", len(flights))
        return flights

    def _parse(self, html: str) -> List[FlightRecord]:
        soup = BeautifulSoup(html, "html.parser")
        out: List[FlightRecord] = []

        # --- TAB finden (All-TAB) ---
        # Häufiger Aufbau: <div id="tab-1753881400708-2-217539465301761753957562541"> ... </div>
        # Falls sich die ID ändert, alternativ: suche nach data-Attributen / Rolle.
        tab_all = soup.select_one('#tab-1753881400708-2-217539465301761753957562541')
        if not tab_all:
            # Fallback: irgendein Tab-Panel, das viele Einträge hat
            candidates = soup.select('[id^="tab-"]')
            self.dbg.add_kv("tab_candidates", len(candidates))
            # nimm das größte Panel (heuristik)
            tab_all = max(candidates, key=lambda el: len(el.get_text(strip=True)), default=None)

        if not tab_all:
            self.dbg.add("no_tab_panel_found")
            return out

        # --- Einträge selektieren ---
        # TODO: Klassennamen/Struktur an realen HTML anpassen.
        # Platzhalter-Selektor:
        items = tab_all.select(".elementor-widget, .jet-listing-grid__item, .flight-item, .elementor-post") or []
        self.dbg.add_kv("items_found", len(items))

        if not items:
            # fallback: alles innerhalb des Tabs und später filtern
            items = tab_all.find_all(["article", "div"], recursive=True)

        for el in items:
            text_all = _clean(el.get_text(" ", strip=True))
            if not text_all:
                continue

            # --- Heuristisch: Route extrahieren ---
            # Oft steht eine Route wie "Ibiza (IBZ) → Zürich (ZRH)" oder "IBZ → ZRH"
            route_block = text_all
            parts = re.split(RE_ROUTE_ARROW, route_block)
            left_txt = right_txt = None
            if len(parts) >= 2:
                left_txt, right_txt = parts[0], parts[-1]

            origin_iata = _pick_code_pref_iata(left_txt or "") if left_txt else None
            dest_iata   = _pick_code_pref_iata(right_txt or "") if right_txt else None
            origin_name = _strip_parens(left_txt or "") if left_txt else ""
            dest_name   = _strip_parens(right_txt or "") if right_txt else ""

            # --- Datum / Uhrzeit finden ---
            # Versuche ISO oder DMY + Uhrzeit im gleichen Block
            date_match = RE_DATE_ISO.search(text_all) or RE_DATE_DMY.search(text_all)
            time_match = RE_TIME.search(text_all)
            departure_ts = _to_utc_iso(date_match.group(1) if date_match else None,
                                       time_match.group(1) if time_match else None)

            # --- Aircraft (optional) ---
            aircraft = None
            # Häufig: ein Label wie "Cessna Citation..." – hier nur simple Heuristik:
            # Wenn du einen stabilen Selektor findest (z.B. .jet-name), nutze den stattdessen.
            # aircraft = _extract_aircraft(el)  # optional Funktion

            # Einfache Validierung
            if not (origin_iata and dest_iata and departure_ts):
                # Debug mit kurzer Rohvorschau
                self.dbg.add(f"skip: oi={origin_iata}, di={dest_iata}, dep={departure_ts}; snippet='{text_all[:120]}'")
                continue

            rec: FlightRecord = {
                "source": self.name,
                "origin_iata": origin_iata,
                "origin_name": origin_name or origin_iata,
                "destination_iata": dest_iata,
                "destination_name": dest_name or dest_iata,
                "departure_ts": departure_ts,
                "arrival_ts": None,
                "status": "pending",
                "price_current": None,
                "price_normal": None,
                "discount_percent": None,
                "probability": None,
                "currency": "EUR",
                "link": CALLAJET_URL,  # meist führt der CTA zu einem Modal/JS; Seite ist ok als Deeplink
                "raw": {
                    "block_text": text_all[:1000],  # begrenzen für Debug
                },
                "raw_static": {"operator": "Call a Jet", "aircraft": aircraft},
                "aircraft": aircraft,
            }
            out.append(rec)

        return out