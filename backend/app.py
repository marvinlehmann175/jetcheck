import os
import sys
import flask
from flask import Flask, jsonify
from dotenv import load_dotenv
from supabase import create_client, Client
import json

# Load .env locally; on Render env vars are provided in the dashboard
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLE = os.getenv("SUPABASE_TABLE", "globeair_flights")  # legacy table (kept for compatibility)

# CORS config: either allow all via ALLOWED_ORIGIN="*" or specific list via ALLOWED_ORIGINS
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
ALLOWED_ORIGINS = [o.strip().rstrip('/') for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
# If ALLOWED_ORIGIN is set and not "*", ensure it's included in ALLOWED_ORIGINS list
if ALLOWED_ORIGIN != "*" and ALLOWED_ORIGIN not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(ALLOWED_ORIGIN)
ALLOW_ALL = ALLOWED_ORIGIN == "*"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_KEY in environment.", file=sys.stderr)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

app = Flask(__name__)

# Handle CORS for preflight and responses
@app.before_request
def handle_preflight():
    if flask.request.method == "OPTIONS":
        resp = app.make_default_options_response()
        origin = (flask.request.headers.get("Origin") or "").rstrip("/")
        if ALLOW_ALL:
            resp.headers["Access-Control-Allow-Origin"] = "*"
        elif origin in ALLOWED_ORIGINS:
            resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resp

@app.after_request
def add_cors_headers(resp):
    origin = (flask.request.headers.get("Origin") or "").rstrip("/")
    if ALLOW_ALL:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    elif origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Vary"] = "Origin"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp

@app.route("/")
def index():
    return (
        "JetCheck API\n\n"
        "Welcome! The API is running.\n\n"
        "Endpoints:\n"
        "  • /api/flights         (NEU – Daten aus flights_latest)\n"
        "  • /api/globeair        (Legacy, alte Tabelle falls noch benötigt)\n"
        "  • /api/asl             (statisches JSON, falls vorhanden)\n"
        "  • /healthz\n"
    ), 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})

# NEW: unified endpoint backed by the 'flights_latest' view
@app.route("/api/flights", methods=["GET", "OPTIONS"])
def get_flights():
    if supabase is None:
        return jsonify({"error": "Supabase client not configured"}), 500
    try:
        # Fetch latest snapshot per flight (from the view)
        resp = (
            supabase
            .table("flights_latest")
            .select(
                "id,source,origin_iata,origin_name,destination_iata,destination_name,"
                "departure_ts,arrival_ts,aircraft,"
                "price_current,price_normal,discount_percent,"
                "currency_effective,status_latest,link_latest,last_seen_at"
            )
            .order("departure_ts", desc=False)
            .limit(500)
            .execute()
        )
        data = resp.data or []
        return jsonify(data)
    except Exception as e:
        print(f"❌ /api/flights error: {e}", file=sys.stderr)
        return jsonify({"error": "Failed to fetch flights"}), 500

# Legacy endpoint (kept for compatibility while frontend migrates)
@app.route("/api/globeair", methods=["GET", "OPTIONS"])
def get_globeair():
    if supabase is None:
        return jsonify({"error": "Supabase client not configured"}), 500
    try:
        resp = (
            supabase
            .table(TABLE)
            .select("id,route,date,time,price,link")
            .order("id", desc=True)
            .execute()
        )
        data = resp.data or []
        return jsonify(data)
    except Exception as e:
        print(f"❌ /api/globeair error: {e}", file=sys.stderr)
        return jsonify({"error": "Failed to fetch flights"}), 500

@app.route("/api/asl", methods=["GET", "OPTIONS"])
def get_asl():
    path = os.path.join(os.path.dirname(__file__), "flights_asl.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)