import requests
from bs4 import BeautifulSoup
import json

URL = "https://www.globeair.com/empty-leg-flights"
response = requests.get(URL)
soup = BeautifulSoup(response.text, "html.parser")

flights = []

columns = soup.select("div.columns > div.column")
for col in columns:
    try:
        route_tag = col.find("h3", class_="caption")
        route = route_tag.get_text(strip=True) if route_tag else "–"

        details_tag = col.find("p", class_="flightdata")
        details_lines = details_tag.decode_contents().split("<br>") if details_tag else []
        date = details_lines[0].strip() if len(details_lines) > 0 else "–"
        time = details_lines[1].strip() if len(details_lines) > 1 else "–"
        price_tag = BeautifulSoup(details_lines[3], "html.parser").get_text(strip=True) if len(details_lines) > 3 else "–"
        
        book_link_tag = col.find("a", class_="button")
        link = book_link_tag["href"] if book_link_tag else None

        flights.append({
            "route": route,
            "date": date,
            "time": time,
            "price": price_tag,
            "link": link
        })
    except Exception as e:
        print("Fehler beim Parsen eines Elements:", e)

# Save to JSON
with open("flights.json", "w", encoding="utf-8") as f:
    json.dump(flights, f, indent=2, ensure_ascii=False)