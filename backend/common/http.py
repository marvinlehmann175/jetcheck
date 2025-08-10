"""
common/http.py – hardened HTTP helper for scrapers
- Retries with exponential backoff (urllib3.Retry)
- Per-host polite delay to avoid hammering providers
- Lightweight UA rotation
- Single shared Session with connection pooling

Env vars:
  SCRAPER_TIMEOUT_S (default 15)
  SCRAPER_RETRIES (default 3)
  SCRAPER_BACKOFF (default 0.6)
  SCRAPER_MIN_DELAY_MS (default 250)
"""
from __future__ import annotations

import os
import time
import random
import threading
from typing import Dict, Optional, Mapping, Any
from urllib.parse import urlparse

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---- Config from env
_TIMEOUT_S: float = float(os.getenv("SCRAPER_TIMEOUT_S", "15"))
_RETRIES: int = int(os.getenv("SCRAPER_RETRIES", "3"))
_BACKOFF: float = float(os.getenv("SCRAPER_BACKOFF", "0.6"))
_MIN_DELAY_MS: int = int(os.getenv("SCRAPER_MIN_DELAY_MS", "250"))

# ---- Minimal UA pool for some variety
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


class _PerHostLimiter:
    """Simple per-host minimum delay to be polite."""

    def __init__(self, min_delay_ms: int) -> None:
        self._min_delay = max(0.0, min_delay_ms / 1000.0)
        self._lock = threading.Lock()
        self._last_ts: Dict[str, float] = {}

    def wait(self, host: str) -> None:
        if not host or self._min_delay <= 0:
            return
        with self._lock:
            now = time.time()
            last = self._last_ts.get(host, 0.0)
            to_sleep = self._min_delay - (now - last)
            if to_sleep > 0:
                # add small jitter to avoid thundering herd
                time.sleep(to_sleep + random.uniform(0, self._min_delay * 0.2))
            self._last_ts[host] = time.time()


_limiter = _PerHostLimiter(_MIN_DELAY_MS)


def _build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=_RETRIES,
        backoff_factor=_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=40)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": random.choice(_USER_AGENTS)})
    return s


def get_session() -> requests.Session:
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is None:
            _session = _build_session()
    return _session


# ---- Convenience wrappers ---------------------------------------------------

def get(
    url: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
) -> Response:
    host = urlparse(url).netloc
    _limiter.wait(host)
    s = get_session()

    # Occasionally rotate UA on the shared session
    if random.random() < 0.2:
        s.headers.update({"User-Agent": random.choice(_USER_AGENTS)})

    req_headers: Dict[str, str] = {}
    if headers:
        req_headers.update(headers)
    if "User-Agent" not in req_headers:
        req_headers["User-Agent"] = s.headers.get("User-Agent", _USER_AGENTS[0])

    resp = s.get(url, params=params, headers=req_headers, timeout=timeout or _TIMEOUT_S)
    return resp


def get_text(
    url: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
    raise_for_status: bool = True,
) -> str:
    resp = get(url, params=params, headers=headers, timeout=timeout)
    if raise_for_status:
        resp.raise_for_status()
    return resp.text


__all__ = [
    "get_session",
    "get",
    "get_text",
]
