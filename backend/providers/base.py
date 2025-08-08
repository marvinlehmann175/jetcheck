# providers/base.py
from __future__ import annotations
import os
from abc import ABC, abstractmethod
from typing import List
from common.http import get_html, save_debug
from common.airports import to_iata, to_names


class Provider(ABC):
    name: str = ""
    base_url: str | None = None

    def __init__(self, debug: bool | None = None):
        env_debug = os.getenv("SCRAPER_DEBUG", "0") == "1"
        self.debug: bool = bool(env_debug or (debug is True))

    @abstractmethod
    def fetch_all(self) -> List[dict]:
        """Holt & parst alle aktuell verfügbaren Flüge dieses Providers."""
        raise NotImplementedError


__all__ = ["Provider", "get_html", "save_debug"]

