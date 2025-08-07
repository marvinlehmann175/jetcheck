import requests
from bs4 import BeautifulSoup
import json

URL = "https://www.globeair.com/empty-leg-flights"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def scrape_globeair():
    response = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    flights = []

    for column in soup.select("div.column"):
        # Route
        caption = column.select_one("h3.caption")
        if not caption:
            continue
        route = caption.get_text(strip=True).replace("\n", "")

        # Details (Datum, Uhrzeit etc.)
        details_block = column.select_one("p.flightdata")
        if not details_block:
            continue
        details_lines = [line.strip() for line in details_block.stripped_strings]
        if len(details_lines) < 3:
            continue
        date = details_lines[0]
        time = details_lines[1]
        price_line = details_lines[2]

        # Buchungslink
        book_button = column.select_one("a.button")
        link = book_button["href"] if book_button else None

        flights.append({
            "route": route,
            "date": date,
            "time": time,
            "price": price_line,
            "link": link
        })

    # Speichern als JSON
    with open("flights.json", "w", encoding="utf-8") as f:
        json.dump(flights, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(flights)} Flüge gespeichert.")

if __name__ == "__main__":
    scrape_globeair()