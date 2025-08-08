# scrapers/base.py
from __future__ import annotations

import re
import datetime as dt
from abc import ABC, abstractmethod
from typing import Iterable, Optional, Tuple

from dateutil import parser as dtparser

from common.http import get_html, save_debug
from common.types import ScrapeResult, ParsedFlight
from common.airports import Airports

RE_MONEY = re.compile(r"(\d[\d.,]*)")
RE_PCT   = re.compile(r"-?(\d+)%")

def clean_money(text: str) -> Optional[int | float]:
    m = RE_MONEY.search(text or "")
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

def parse_percent(text: str) -> Optional[int]:
    m = RE_PCT.search(text or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None

def iso_utc(dt_obj: dt.datetime) -> str:
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return dt_obj.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def to_iso_utc_naive(date_str: Optional[str], time_str: Optional[str]) -> Optional[str]:
    """Ohne TZ-Wissen: baut ISO + 'Z' (bewusst 'naiv'); Provider-spezifische TZ kannst du später im Orchestrator normalisieren."""
    if not (date_str and time_str):
        return None
    try:
        d = dtparser.parse(date_str)
        t = dtparser.parse(time_str, default=d).replace(microsecond=0, tzinfo=None)
        return t.isoformat() + "Z"
    except Exception:
        return None

def parse_local(date_s: str, time_s: str, tzinfo: dt.tzinfo) -> Optional[str]:
    """DD/MM/… + HH:MM in lokaler TZ -> ISO UTC."""
    try:
        d = dtparser.parse(date_s, dayfirst=True, yearfirst=False)
        t = dtparser.parse(time_s, default=d)
        local = dt.datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=tzinfo)
        return iso_utc(local)
    except Exception:
        return None

def pick_code_from_text(text: str) -> str:
    """Extrahiert Codes in Klammern; bevorzugt IATA (3) vor ICAO (4)."""
    if not text:
        return ""
    cands = re.findall(r"\(([A-Za-z0-9]{3,4})\)", text)
    if not cands:
        return ""
    three = [c.upper() for c in cands if len(c) == 3]
    if three:
        return three[-1]
    four = [c.upper() for c in cands if len(c) == 4]
    return four[-1] if four else cands[-1].upper()

def strip_parens(text: str) -> str:
    """Entfernt (…)-Anteile und normalisiert Whitespace."""
    import re as _re
    base = _re.sub(r"\([^)]+\)", "", text or "").strip()
    return _re.sub(r"\s+", " ", base)

class BaseProvider(ABC):
    """
    Gemeinsames Grundgerüst für Provider-Scraper.
    - HTTP-Fetch + Debug-Dump
    - optionale Normalisierung von IATA/ICAO/Ortsnamen über Airports-Registry
    - Helfer für Geld/Prozent/Datum
    """

    name: str = "provider"
    start_url: str | None = None
    default_currency: str = "EUR"

    def __init__(self, airports: Optional[Airports] = None) -> None:
        self.airports = airports  # kann None sein; dann wird nicht normalisiert

    # ---------------- HTTP ----------------
    def get_html(self, url: str, *, referer: Optional[str] = None, timeout: int = 25) -> str:
        return get_html(url, referer=referer, timeout=timeout)

    def save_debug(self, filename: str, html: str) -> None:
        save_debug(filename, html)

    # ------------- Normalisierung ----------
    def normalize_route(
        self,
        origin_iata: Optional[str],
        origin_name: Optional[str],
        dest_iata: Optional[str],
        dest_name: Optional[str],
    ) -> Tuple[str | None, str | None, str | None, str | None]:
        """
        Versucht mithilfe der Airports-Registry IATA/ICAO sauber aufzulösen.
        Gibt (o_iata, o_name, d_iata, d_name) zurück.
        """
        if not self.airports:
            # Keine Registry -> möglichst IATA großschreiben; Namen wie geliefert
            oi = origin_iata.upper() if origin_iata else None
            di = dest_iata.upper() if dest_iata else None
            return (oi, origin_name, di, dest_name)

        oi, on = self._resolve_code_name(origin_iata, origin_name)
        di, dn = self._resolve_code_name(dest_iata, dest_name)
        return (oi, on, di, dn)

    def _resolve_code_name(self, iata_or_icao: Optional[str], name: Optional[str]) -> Tuple[str | None, str | None]:
        code = (iata_or_icao or "").upper().strip()
        nm = (name or "").strip() or None

        if code:
            r = self.airports.by_code(code)
            if r:
                # Bevorzuge offizielle Namen aus Registry
                return (r.iata or r.icao, r.name or nm)

        if nm:
            r = self.airports.by_name(nm)
            if r:
                return (r.iata or r.icao, r.name)

        # nichts gefunden -> Rohwerte zurück
        return (code or None, nm)

    # ----------------- Pipeline -----------------
    @abstractmethod
    def parse_html(self, html: str) -> ScrapeResult:
        """Muss von jedem Provider implementiert werden."""
        raise NotImplementedError

    def fetch_all(self) -> ScrapeResult:
        """Standard: nur eine Seite. Provider mit Pagination überschreiben diese Methode."""
        if not self.start_url:
            return []
        html = self.get_html(self.start_url)
        self.save_debug(f"{self.name}.html", html)
        return self.parse_html(html)

    # --------- Convenience-Helfer re-export ---------
    clean_money = staticmethod(clean_money)
    parse_percent = staticmethod(parse_percent)
    iso_utc = staticmethod(iso_utc)
    to_iso_utc_naive = staticmethod(to_iso_utc_naive)
    parse_local = staticmethod(parse_local)
    pick_code_from_text = staticmethod(pick_code_from_text)
    strip_parens = staticmethod(strip_parens)