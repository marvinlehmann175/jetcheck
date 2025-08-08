# backend/providers/base.py
from __future__ import annotations
import os
from abc import ABC, abstractmethod
from typing import List, Optional

from common.debug import DebugCollector
from common.types import FlightRecord

class Provider(ABC):
    name: str = ""           # z.B. "globeair", "asl"
    base_url: Optional[str] = None

    def __init__(self, debug: bool | None = None, debug_dir: str | None = None):
        env_debug = os.getenv("SCRAPER_DEBUG", "0") == "1"
        enabled = bool(env_debug or (debug is True))
        self.debug: bool = enabled
        # Name fällt auf Klassenname zurück, falls kein name gesetzt
        ident = (self.name or self.__class__.__name__).lower()
        self.dbg = DebugCollector(ident, enabled, debug_dir)

    @abstractmethod
    def fetch_all(self) -> List[FlightRecord]:
        """Holt & parst alle aktuell verfügbaren Flüge dieses Providers."""
        raise NotImplementedError

    # Optionaler Convenience-Hook für Provider:
    def save_debug_html(self, filename: str, html: str) -> None:
        """Legt Debug-HTMLs unter /tmp/jetcheck/<provider>_* ab."""
        if not self.debug:
            return
        prefix = (self.name or self.__class__.__name__).lower()
        safe = filename if filename.startswith(prefix) else f"{prefix}_{filename}"
        self.dbg.save_text(safe, html)  # nutzt DebugCollector