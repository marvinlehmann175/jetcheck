# common/http.py
"""
Zentraler HTTP-Client für alle Scraper.
Beinhaltet Standard-Header, Session-Handling und optionales Debug-Logging.
"""

import os
import requests

DEBUG = os.getenv("SCRAPER_DEBUG", "0") == "1"

# Gemeinsame Browser-ähnliche Header
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

# Eine Session für Wiederverwendung und Cookie-Handling
SESSION = requests.Session()
SESSION.headers.update(COMMON_HEADERS)


def save_debug(name: str, text: str):
    """Speichert HTML/Text im /tmp/jetcheck für Analyse im Debug-Modus."""
    if not DEBUG:
        return
    import pathlib
    pathlib.Path("/tmp/jetcheck").mkdir(parents=True, exist_ok=True)
    path = f"/tmp/jetcheck/{name}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"🪵 DEBUG saved: {path}")


def get(url: str, referer: str = None, timeout: int = 25) -> str:
    """
    Führt einen GET-Request mit Standard-Headern und optionalem Referer aus.
    """
    headers = COMMON_HEADERS.copy()
    if referer:
        headers["Referer"] = referer
    r = SESSION.get(url, headers=headers, timeout=timeout)
    if DEBUG:
        print(f"GET {url} status={r.status_code}, len={len(r.text)}")
    r.raise_for_status()
    return r.text