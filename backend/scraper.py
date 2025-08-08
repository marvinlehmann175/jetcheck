import os
import sys
from flask import Flask, jsonify, Response
from dotenv import load_dotenv
from supabase import create_client, Client

# Load local .env when running locally; on Render environment vars are provided by the dashboard
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLE = os.getenv("SUPABASE_TABLE", "globeair_flights")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")  # e.g. https://jetcheck.de

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_KEY in environment.", file=sys.stderr)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# ----------------------------
# Deine Scraper-Logik hier
# ----------------------------
def scrape_and_save():
    if supabase is None:
        print("❌ Supabase client not configured", file=sys.stderr)
        return
    try:
        # Hier deine bestehende Scraping-Logik einsetzen
        # Beispiel:
        print("🔄 Starte Scraper...")
        # ... scrape ...
        print("✅ Flüge gespeichert.")
    except Exception as e:
        print(f"❌ Scraper error: {e}", file=sys.stderr)

# ----------------------------
# Flask-App nur laden, wenn API-Mode
# ----------------------------
def create_app():
    app = Flask(__name__)

    @app.after_request
    def add_cors_headers(resp: Response):
        resp.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resp

    @app.route("/")
    def index():
        return (
            "JetCheck API\n\n"
            "Welcome! The API is running.\n\n"
            "/api/globeair\n"
            "/api/asl\n"
        ), 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.route("/api/globeair")
    def get_globeair():
        if supabase is None:
            return jsonify({"error": "Supabase client not configured"}), 500
        try:
            resp = (
                supabase
                .table(TABLE)
                .select("route,date,time,price,link,probability,id")
                .order("id", desc=True)
                .execute()
            )
            return jsonify(resp.data or [])
        except Exception as e:
            print(f"❌ /api/globeair error: {e}", file=sys.stderr)
            return jsonify({"error": "Failed to fetch flights"}), 500

    @app.route("/api/asl")
    def get_asl():
        path = os.path.join(os.path.dirname(__file__), "flights_asl.json")
        if os.path.exists(path):
            import json
            with open(path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify([])

    @app.route("/run-scraper")
    def run_scraper_endpoint():
        scrape_and_save()
        return jsonify({"status": "scraper run"}), 200

    return app

# ----------------------------
# Main entry point
# ----------------------------
if __name__ == "__main__":
    mode = os.environ.get("SCRAPER_MODE", "api")  # Default: API-Mode
    if mode == "scrape":
        scrape_and_save()
    else:
        port = int(os.getenv("PORT", 5000))
        app = create_app()
        app.run(host="0.0.0.0", port=port, debug=False)