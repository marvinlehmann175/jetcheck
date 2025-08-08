# common/airports.py
"""
Airports lookup (IATA/ICAO) backed by Supabase.
- Lazy loads the 'airports' table into in-memory indexes
- Helpers to resolve IATA from either IATA or ICAO
- Optional helpers to get pretty names
"""

import os
from typing import Dict, Optional, Tuple
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

_airport_index_by_iata: Dict[str, Dict] = {}
_airport_index_by_icao: Dict[str, Dict] = {}
_loaded: bool = False


def _client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("❌ SUPABASE_URL or SUPABASE_*_KEY missing for airports lookup")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def build_indexes() -> None:
    """Fetch all airports from Supabase and build IATA/ICAO maps."""
    global _airport_index_by_iata, _airport_index_by_icao, _loaded
    client = _client()

    # Adjust the selected columns to match your airports table
    # Expected columns: id, iata, icao, name, city, country
    res = client.table("airports").select("*").execute()
    rows = res.data or []

    _airport_index_by_iata.clear()
    _airport_index_by_icao.clear()

    for row in rows:
        iata = (row.get("iata") or "").strip().upper()
        icao = (row.get("icao") or "").strip().upper()
        if iata:
            _airport_index_by_iata[iata] = row
        if icao:
            _airport_index_by_icao[icao] = row

    _loaded = True
    print(f"✅ Airports index loaded: {len(_airport_index_by_iata)} IATA, {len(_airport_index_by_icao)} ICAO")


def _ensure_loaded() -> None:
    global _loaded
    if not _loaded:
        build_indexes()


def resolve(code: str) -> Optional[Dict]:
    """
    Resolve an airport by IATA or ICAO. Returns the full row or None.
    """
    if not code:
        return None
    _ensure_loaded()
    c = code.strip().upper()
    if c in _airport_index_by_iata:
        return _airport_index_by_iata[c]
    if c in _airport_index_by_icao:
        return _airport_index_by_icao[c]
    return None


def to_iata(code_or_text: Optional[str]) -> Optional[str]:
    """
    Normalize a code to IATA:
    - If input is already IATA (3 letters) and known → return itself
    - If input is ICAO (4 letters) and known → map to IATA
    - If unknown → None
    """
    if not code_or_text:
        return None
    _ensure_loaded()
    code = code_or_text.strip().upper()

    # quick paths
    if len(code) == 3 and code in _airport_index_by_iata:
        return code
    if len(code) == 4 and code in _airport_index_by_icao:
        row = _airport_index_by_icao[code]
        iata = (row.get("iata") or "").strip().upper()
        return iata or None

    # Not recognized
    return None


def to_names(code_or_text: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return (airport_name, city, country) for a given IATA/ICAO code.
    Useful for UI display if you want more than just the code.
    """
    if not code_or_text:
        return (None, None, None)
    row = resolve(code_or_text)
    if not row:
        return (None, None, None)
    name = row.get("name")
    city = row.get("city")
    country = row.get("country")
    return (name, city, country)