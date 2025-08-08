# backend/common/http.py
import os
from pathlib import Path
from typing import Optional, Dict
import time

import requests
from common.debug import DebugCollector

DEBUG = os.getenv("SCRAPER_DEBUG", "0") == "1"

# Eine einzige Session für alle Requests
SESSION = requests.Session()

COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 JetCheckBot/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,en-GB;q=0.9,de;q=0.8",
    "Cache-Control": "no-cache",
}

def save_debug(name: str, text: str) -> None:
    """Schreibt Debug-Dateien nach /tmp/jetcheck, wenn SCRAPER_DEBUG=1."""
    if not DEBUG:
        return
    outdir = Path("/tmp/jetcheck")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / name
    path.write_text(text, encoding="utf-8")
    print(f"🪵 DEBUG saved: {path}")

def get_html(
    url: str,
    *,
    referer: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 25,
    dbg: Optional[DebugCollector] = None,
) -> str:
    """
    GET HTML-Text mit gemeinsamer Session & Standard-Headern.
    - referer: setzt den Referer-Header
    - headers: erlaubt zusätzliche/überschreibende Header
    - dbg: optionaler DebugCollector für Timings/Logs
    """
    h = dict(COMMON_HEADERS)
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)

    t0 = time.perf_counter()
    r = SESSION.get(url, headers=h, timeout=timeout)
    ms = (time.perf_counter() - t0) * 1000.0

    if dbg and dbg.enabled:
        dbg.log("HTTP GET", url=url, status=r.status_code, len=len(r.text), ms=round(ms, 1))
    elif DEBUG:
        print(f"HTTP GET {url} -> {r.status_code}, len={len(r.text)}")

    r.raise_for_status()
    return r.text

def absolute_url(base: str, href: Optional[str]) -> Optional[str]:
    """Hilfsfunktion: macht relative Links absolut."""
    if not href:
        return None
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return base.rstrip("/") + "/" + href

__all__ = [
    "DEBUG",
    "SESSION",
    "COMMON_HEADERS",
    "save_debug",
    "get_html",
    "absolute_url",
]