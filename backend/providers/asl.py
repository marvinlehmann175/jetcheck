# providers/asl.py
import re
from typing import Dict, Any, List, Optional

from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from zoneinfo import ZoneInfo

from common.http import SESSION, COMMON_HEADERS, save_debug, DEBUG
from common.types import Provider
from common.airports import to_iata, to_names

ASL_BASE = "https://www.aslgroup.eu"
ASL_FIRST = f"{ASL_BASE}/en/empty-legs"
ASL_TZ = ZoneInfo("Europe/Brussels")  # site times are local


def _parse_asl_datetime(date_s: str, time_s: str) -> Optional[str]:
    try:
        # "09-08-2025" + "15:00" in Europe/Brussels → ISO UTC Z
        d = dtparser.parse(date_s, dayfirst=True)  # DD-MM-YYYY
        t = dtparser.parse(time_s, default=d)
        local = d.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0, tzinfo=ASL_TZ)
        return local.astimezone().astimezone(ZoneInfo("UTC")).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _pick_code(text: str) -> str:
    """
    Sucht alle Codes in Klammern und bevorzugt IATA (3) gegenüber ICAO (4).
    Z.B. "Montichiari (BS)(LIPO)" -> nimmt 3-stellig (falls vorhanden), sonst 4-stellig; jeweils den letzten Treffer.
    """
    if not text:
        return ""
    cands = re.findall(r"\(([A-Za-z0-9]{3,4})\)", text)
    if not cands:
        return ""
    three = [c.upper() for c in cands if len(c) == 3]
    if three:
        return three[-1]
    four = [c.upper() for c in cands if len(c) == 4]
    return four[-1] if four else cands[-1].upper()


def _clean_place_name(side_text: str) -> str:
    base = re.sub(r"\([^)]+\)", "", side_text or "").strip()
    return re.sub(r"\s+", " ", base)


def _pretty_name(iata: Optional[str], fallback: Optional[str]) -> Optional[str]:
    if not iata:
        return fallback
    name, city, _country = to_names(iata)
    return name or city or fallback


def parse_asl_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    arts = soup.select("article.plane")
    if DEBUG:
        print(f"ASL: article.plane => {len(arts)}")

    rows: List[Dict[str, Any]] = []

    for art in arts:
        # Aircraft
        ac_el = art.select_one(".plane-name")
        aircraft = ac_el.get_text(strip=True) if ac_el else None

        # Headline with route
        headline = art.select_one(".plane-headline") or art.select_one(".leading-headline")
        if not headline:
            continue
        route_text = headline.get_text(" | ", strip=True)

        # Robust split for left/right
        parts = [p.strip() for p in route_text.split("|") if p.strip()]
        if len(parts) < 2:
            if "→" in route_text:
                parts = [p.strip() for p in route_text.split("→", 1)]
            elif "-" in route_text:
                parts = [p.strip() for p in route_text.split("-", 1)]
        if len(parts) < 2:
            continue
        left, right = parts[0], parts[-1]

        origin_code_raw = _pick_code(left)
        dest_code_raw   = _pick_code(right)

        # normalize to IATA and skip if unknown
        oi = to_iata(origin_code_raw)
        di = to_iata(dest_code_raw)
        if not oi or not di:
            if DEBUG:
                print(f"⚠️  ASL skip (unknown code): {origin_code_raw} -> {dest_code_raw}")
            continue

        origin_name = _pretty_name(oi, _clean_place_name(left))
        dest_name   = _pretty_name(di, _clean_place_name(right))

        # Specs (date/time)
        date_li = time_li = None
        for li in art.select("ul.plane-specs li"):
            txt = li.get_text(" ", strip=True)
            if re.search(r"\d{2}-\d{2}-\d{4}", txt):
                date_li = txt.strip()
            elif re.search(r"\d{1,2}:\d{2}", txt):
                time_li = txt.strip()

        date_s = re.search(r"(\d{2}-\d{2}-\d{4})", date_li or "")
        time_s = re.search(r"(\d{1,2}:\d{2})", time_li or "")
        departure_ts = _parse_asl_datetime(date_s.group(1), time_s.group(1)) if (date_s and time_s) else None

        # Link
        a = art.select_one("a.button, a.button-full, a.button-primary, a[href]")
        link = a.get("href") if a else None
        if link and link.startswith("/"):
            link = ASL_BASE + link

        rows.append({
            "source": "asl",
            "origin_iata": oi,
            "origin_name": origin_name,
            "destination_iata": di,
            "destination_name": dest_name,
            "departure_ts": departure_ts,
            "arrival_ts": None,   # not provided by site
            "status": "pending",
            "price_current": None,
            "price_normal": None,
            "discount_percent": None,
            "probability": None,
            "currency": "EUR",
            "link": link,
            "raw": {"headline": route_text, "date": date_li, "time": time_li},
            "raw_static": {"operator": "ASL", "aircraft": aircraft},
            "aircraft": aircraft,
        })

    return rows


class ASLProvider(Provider):
    def fetch(self, timeout: int = 25) -> List[Dict[str, Any]]:
        def _get(url: str) -> str:
            r = SESSION.get(url, headers={**COMMON_HEADERS, "Referer": ASL_BASE + "/"}, timeout=timeout)
            if DEBUG:
                print(f"ASL GET {url} status={r.status_code}, len={len(r.text)}")
            r.raise_for_status()
            return r.text

        first_html = _get(ASL_FIRST)
        save_debug("asl_1.html", first_html)
        rows = parse_asl_html(first_html)

        # discover pagination
        soup = BeautifulSoup(first_html, "html.parser")
        pages = []
        for a in soup.select(".pagination a.pagination-page, .pagination a"):
            try:
                n = int(a.get_text(strip=True))
                pages.append((n, a.get("href")))
            except Exception:
                continue
        max_page = max([n for n, _ in pages], default=1)

        # fetch remaining pages
        for p in range(2, max_page + 1):
            url = f"{ASL_BASE}/en/empty-legs/{p}"
            html = _get(url)
            save_debug(f"asl_{p}.html", html)
            rows.extend(parse_asl_html(html))

        return rows