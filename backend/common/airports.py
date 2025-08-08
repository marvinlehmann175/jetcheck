# backend/common/airports.py
"""
Airports-Resolver (IATA/ICAO) mit Lazy-Load aus Supabase.
Erlaubt schnelle Lookups und Normalisierung von Codes.
"""

import os
from typing import Dict, Optional, Tuple
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")


class Airports:
    _loaded: bool = False
    _by_iata: Dict[str, Dict] = {}
    _by_icao: Dict[str, Dict] = {}

    @classmethod
    def ensure_loaded(cls) -> None:
        """Lazy-Load: lädt Airport-Daten einmalig aus Supabase."""
        if cls._loaded:
            return
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("❌ SUPABASE_URL/SUPABASE_KEY fehlen für Airports-Resolver")

        client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = client.table("airports").select("*").execute()
        data = res.data or []

        cls._by_iata.clear()
        cls._by_icao.clear()

        for row in data:
            iata = (row.get("iata") or "").upper()
            icao = (row.get("icao") or "").upper()
            if iata:
                cls._by_iata[iata] = row
            if icao:
                cls._by_icao[icao] = row

        cls._loaded = True
        print(f"✅ Airports geladen: {len(cls._by_iata)} IATA, {len(cls._by_icao)} ICAO")

    # -------- Convenience-APIs --------

    @classmethod
    def resolve(cls, code: Optional[str]) -> Optional[Dict]:
        """Gibt Airport-Row zu IATA/ICAO zurück (oder None)."""
        if not code:
            return None
        cls.ensure_loaded()
        c = code.upper()
        return cls._by_iata.get(c) or cls._by_icao.get(c)

    @classmethod
    def to_iata(cls, code: Optional[str]) -> Optional[str]:
        """Normalisiert beliebigen Code (IATA/ICAO) zu IATA (falls bekannt)."""
        row = cls.resolve(code or "")
        return (row or {}).get("iata")

    @classmethod
    def to_icao(cls, code: Optional[str]) -> Optional[str]:
        """Normalisiert beliebigen Code (IATA/ICAO) zu ICAO (falls bekannt)."""
        row = cls.resolve(code or "")
        return (row or {}).get("icao")

    @classmethod
    def name_for(cls, code: Optional[str]) -> Optional[str]:
        """Liefert Anzeigenamen (city_name oder airport_name) für Code."""
        row = cls.resolve(code or "")
        if not row:
            return None
        return row.get("city_name") or row.get("airport_name")

    @classmethod
    def codes_for(cls, name_or_code: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Versucht, aus Name/Code beide Codes (IATA, ICAO) zu liefern.
        Wenn `name_or_code` bereits IATA/ICAO ist, nutzt resolve().
        """
        if not name_or_code:
            return (None, None)
        row = cls.resolve(name_or_code)
        if row:
            return (row.get("iata"), row.get("icao"))
        # Optional: hier könnte man später fuzzy Name-Suche ergänzen
        return (None, None)


# Kurze Funktions-Aliase für bequeme Nutzung in den Providern
def resolve(code: Optional[str]) -> Optional[Dict]:
    return Airports.resolve(code)

def to_iata(code: Optional[str]) -> Optional[str]:
    return Airports.to_iata(code)

def to_icao(code: Optional[str]) -> Optional[str]:
    return Airports.to_icao(code)

def name_for(code: Optional[str]) -> Optional[str]:
    return Airports.name_for(code)