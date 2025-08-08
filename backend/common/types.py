# backend/common/types.py
from __future__ import annotations

from typing import TypedDict, Optional, Dict, Any

class FlightRecord(TypedDict, total=False):
    # Kern
    source: str
    origin_iata: str
    origin_name: Optional[str]
    destination_iata: str
    destination_name: Optional[str]
    departure_ts: str            # ISO-8601, UTC (z.B. "2025-08-09T12:00:00Z")
    arrival_ts: Optional[str]    # optional

    # Metadaten
    aircraft: Optional[str]
    link: Optional[str]
    currency: str
    status: str                  # "pending" | "confirmed" | ...
    probability: Optional[float]

    # Preise / Snapshot
    price_current: Optional[float]
    price_normal: Optional[float]
    discount_percent: Optional[float]

    # Rohdaten
    raw: Dict[str, Any]
    raw_static: Dict[str, Any]

__all__ = ["FlightRecord"]