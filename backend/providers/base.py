# backend/providers/base.py
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from common.http import get_html, save_debug  # re-exported für Bequemlichkeit


class Provider(ABC):
    """
    Abstrakte Basis-Klasse für alle Provider.
    Implementiere mindestens:
      - fetch_all() -> List[Dict[str, Any]]
    Optional:
      - name (z. B. "globeair", "asl")
    """

    name: str = "provider"

    # einige Helpers allen Providern verfügbar machen
    get_html = staticmethod(get_html)
    save_debug = staticmethod(save_debug)

    @abstractmethod
    def fetch_all(self) -> List[Dict[str, Any]]:
        """Holt & parst alle aktuell verfügbaren Flüge dieses Providers."""
        raise NotImplementedError


__all__ = ["Provider", "get_html", "save_debug"]