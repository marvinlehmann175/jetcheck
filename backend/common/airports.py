# backend/common/airports.py
"""
Airports-Resolver (IATA/ICAO/Name/City) aus Supabase.
Bietet bequeme Helpers: to_iata(), to_icao(), to_names().
"""

import os
import unicodedata
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
    s = s or ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.strip().lower().split())

def build_indexes(force: bool = False) -> None:
    """Lädt airports aus Supabase (airports) und baut Indizes."""
    global _loaded, _airport_index_by_iata, _airport_index_by_icao
    global _airport_index_by_city, _airport_index_by_name

    if _loaded and not force:
        return

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("❌ SUPABASE_URL/SUPABASE_KEY fehlen für Airports-Lookup")

    client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = client.table("airports").select("*").execute()
    rows = res.data or []

    _airport_index_by_iata.clear()
    _airport_index_by_icao.clear()
    _airport_index_by_city.clear()
    _airport_index_by_name.clear()

    for row in rows:
        iata = (row.get("iata") or "").upper()
        icao = (row.get("icao") or "").upper()
        city = row.get("city") or ""
        name = row.get("name") or ""

        if iata:
            _airport_index_by_iata[iata] = row
        if icao:
            _airport_index_by_icao[icao] = row
        if city:
            _airport_index_by_city[_norm(city)] = row
        if name:
            _airport_index_by_name[_norm(name)] = row

    _loaded = True
    print(f"✅ Airports-Index: {len(_airport_index_by_iata)} IATA, {len(_airport_index_by_icao)} ICAO")

def _ensure_loaded():
    if not _loaded:
        build_indexes()

def resolve(code_or_name: str) -> Optional[Dict]:
    """Sucht Airport per IATA/ICAO/City/Name."""
    if not code_or_name:
        return None
    _ensure_loaded()

    s = code_or_name.strip().upper()

    # direkter Code
    if len(s) == 3 and s in _airport_index_by_iata:
        return _airport_index_by_iata[s]
    if len(s) == 4 and s in _airport_index_by_icao:
        return _airport_index_by_icao[s]

    # city / name
    n = _norm(code_or_name)
    if n in _airport_index_by_city:
        return _airport_index_by_city[n]
    if n in _airport_index_by_name:
        return _airport_index_by_name[n]

    return None

def to_iata(code_or_name: str) -> Optional[str]:
    """Gibt IATA code (3) zurück – egal ob Input IATA, ICAO, City oder Name war."""
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
    """Gibt ICAO code (4) zurück – Input kann IATA/ICAO/City/Name sein."""
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
    """Gibt (city, name) zurück – nützlich für Kartenanzeige."""
    row = resolve(code_or_name)
    if not row:
        return (None, None)
    return (row.get("city"), row.get("name"))

__all__ = ["build_indexes", "resolve", "to_iata", "to_icao", "to_names"]