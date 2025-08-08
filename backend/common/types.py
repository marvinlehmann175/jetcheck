# common/types.py
"""
Gemeinsame Typdefinitionen für alle Scraper und das DB-Layer.
Erleichtert Autocomplete, Linting und verhindert Tippfehler bei Keys.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict, Literal, Callable
import datetime as dt

# ---- Literals / Enums (lightweight) ----
StatusLiteral = Literal["pending", "confirmed", "sold"]

# ---- Eingangsformat: was einzelne Scraper zurückgeben ----
class ParsedFlight(TypedDict, total=False):
    """
    Ergebnis eines einzelnen Scrapers (roh-parsed, noch nicht normalisiert).
    Wird später in DB-Payloads transformiert.
    """
    source: str  # "globeair", "asl", ...
    origin_iata: str
    origin_name: Optional[str]
    destination_iata: str
    destination_name: Optional[str]

    # Zeitstempel können vom Parser als ISO-String ODER datetime kommen
    departure_ts: str | dt.datetime
    arrival_ts: Optional[str | dt.datetime]

    # Metadaten / Preise
    status: StatusLiteral
    price_current: Optional[float | int]
    price_normal: Optional[float | int]
    discount_percent: Optional[int]   # z.B. 15 bedeutet -15%
    probability: Optional[float]      # 0..1
    currency: Optional[str]           # Default i.d.R. "EUR"
    link: Optional[str]
    aircraft: Optional[str]

    # Debug / Rohdaten (für spätere Auswertung)
    raw: Dict[str, Any]
    raw_static: Dict[str, Any]

# Ein Scraper liefert eine Liste von ParsedFlight
ScrapeResult = List[ParsedFlight]

# Parser-Signaturen, falls du Funktionen typisieren willst
HTMLParser = Callable[[str], ScrapeResult]
Fetcher = Callable[[], ScrapeResult]

# ---- DB-Payloads (für Supabase .upsert / .insert) ----

class FlightUpsertPayload(TypedDict, total=False):
    """
    Payload für Tabelle 'flights' (Upsert).
    Achtung: Hash wird DB-seitig via Trigger/Funktion erzeugt.
    """
    user_id: str
    source: str
    origin_iata: str
    origin_name: Optional[str]
    destination_iata: str
    destination_name: Optional[str]
    departure_ts: str               # ISO-UTC (z.B. 2025-08-08T12:34:00Z)
    arrival_ts: Optional[str]
    aircraft: Optional[str]
    link: Optional[str]
    currency: str
    status: StatusLiteral
    probability: Optional[float]
    raw_static: Dict[str, Any]

class SnapshotInsertPayload(TypedDict, total=False):
    """
    Payload für Tabelle 'flight_snapshots' (Insert).
    """
    flight_id: int
    price_current: Optional[float | int]
    price_normal: Optional[float | int]
    currency: str
    status: Optional[StatusLiteral]
    link: Optional[str]
    raw: Dict[str, Any]

__all__ = [
    "StatusLiteral",
    "ParsedFlight",
    "ScrapeResult",
    "HTMLParser",
    "Fetcher",
    "FlightUpsertPayload",
    "SnapshotInsertPayload",
]