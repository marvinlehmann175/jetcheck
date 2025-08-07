import json

# Beispiel-Flugdaten (kannst du jederzeit erweitern)
flights = [
    {"route": "Ibiza → Zürich", "details": "08.08.2025, 10:00 Uhr", "link": "https://globeair.com/xyz"},
    {"route": "Genf → Nizza", "details": "09.08.2025, 14:00 Uhr", "link": "https://globeair.com/abc"}
]

# Speichern als JSON-Datei
with open("flights.json", "w") as f:
    json.dump(flights, f)