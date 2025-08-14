# backend/common/airports.py

from __future__ import annotations
import os, unicodedata
from typing import Dict, Optional, Tuple
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

_airport_index_by_iata: Dict[str, Dict] = {}
_airport_index_by_icao: Dict[str, Dict] = {}
_airport_index_by_city: Dict[str, Dict] = {}
_airport_index_by_name: Dict[str, Dict] = {}
_loaded = False

def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.strip().lower().split())

def build_indexes(force: bool = False) -> None:
    global _loaded, _airport_index_by_iata, _airport_index_by_icao
    global _airport_index_by_city, _airport_index_by_name
    if _loaded and not force:
        return
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("❌ SUPABASE_URL/SUPABASE_KEY fehlen für Airports-Lookup")
    client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    rows = (client.table("airports").select("*").execute().data) or []

    _airport_index_by_iata.clear()
    _airport_index_by_icao.clear()
    _airport_index_by_city.clear()
    _airport_index_by_name.clear()

    for row in rows:
        iata = (row.get("iata") or "").upper()
        icao = (row.get("icao") or "").upper()
        city = row.get("city") or ""
        name = row.get("name") or ""
        if iata: _airport_index_by_iata[iata] = row
        if icao: _airport_index_by_icao[icao] = row
        if city: _airport_index_by_city[_norm(city)] = row
        if name: _airport_index_by_name[_norm(name)] = row

    _loaded = True
    print(f"✅ Airports-Index: {len(_airport_index_by_iata)} IATA, {len(_airport_index_by_icao)} ICAO")

def _ensure_loaded() -> None:
    if not _loaded:
        build_indexes()

def resolve(code_or_name: str) -> Optional[Dict]:
    if not code_or_name:
        return None
    _ensure_loaded()
    s = code_or_name.strip().upper()
    if len(s) == 3 and s in _airport_index_by_iata:
        return _airport_index_by_iata[s]
    if len(s) == 4 and s in _airport_index_by_icao:
        return _airport_index_by_icao[s]
    n = _norm(code_or_name)
    if n in _airport_index_by_city:
        return _airport_index_by_city[n]
    if n in _airport_index_by_name:
        return _airport_index_by_name[n]
    return None

def to_iata(code_or_name: str) -> Optional[str]:
    if not code_or_name:
        return None
    _ensure_loaded()
    s = code_or_name.strip().upper()
    if len(s) == 3 and s in _airport_index_by_iata:
        return s
    if len(s) == 4 and s in _airport_index_by_icao:
        row = _airport_index_by_icao[s]
        return (row.get("iata") or "").upper() or None
    row = resolve(code_or_name)
    if row:
        return (row.get("iata") or "").upper() or None
    return None

def to_icao(code_or_name: str) -> Optional[str]:
    if not code_or_name:
        return None
    _ensure_loaded()
    s = code_or_name.strip().upper()
    if len(s) == 4 and s in _airport_index_by_icao:
        return s
    if len(s) == 3 and s in _airport_index_by_iata:
        row = _airport_index_by_iata[s]
        return (row.get("icao") or "").upper() or None
    row = resolve(code_or_name)
    if row:
        return (row.get("icao") or "").upper() or None
    return None

def to_names(code_or_name: str) -> Tuple[Optional[str], Optional[str]]:
    row = resolve(code_or_name)
    if not row:
        return (None, None)
    return (row.get("city"), row.get("name"))

def to_iata_by_name(name: str) -> Optional[str]:
    if not name:
        return None
    _ensure_loaded()
    n = _norm(name)
    row = _airport_index_by_city.get(n) or _airport_index_by_name.get(n)
    if row and row.get("iata"):
        return (row["iata"] or "").upper() or None
    for idx in (_airport_index_by_city, _airport_index_by_name):
        for key, row in idx.items():
            if key.startswith(n):
                iata = (row.get("iata") or "").upper()
                if iata:
                    return iata
    for idx in (_airport_index_by_city, _airport_index_by_name):
        for key, row in idx.items():
            if n in key:
                iata = (row.get("iata") or "").upper()
                if iata:
                    return iata
    return None

def get_latlon(code_or_name: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Returns (lat, lon) for an airport by IATA/ICAO/city/name, or (None, None).
    Accepts common column variants: lat/lon or latitude/longitude/lng.
    """
    row = resolve(code_or_name)
    if not row:
        return (None, None)
    lat = row.get("lat") or row.get("latitude")
    lon = row.get("lon") or row.get("lng") or row.get("longitude")
    try:
        return (float(lat), float(lon)) if lat is not None and lon is not None else (None, None)
    except (ValueError, TypeError):
        return (None, None)

__all__ = [
    "build_indexes",
    "resolve",
    "to_iata",
    "to_icao",
    "to_names",
    "to_iata_by_name",
    "get_latlon",
]