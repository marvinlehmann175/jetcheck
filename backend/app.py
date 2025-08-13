import os
import sys
import flask
import traceback
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env locally; on Render env vars come from the dashboard
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Prefer service role key if present; fall back to SUPABASE_KEY for compatibility
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

# CORS config: either allow all via ALLOWED_ORIGIN="*" or specific list via ALLOWED_ORIGINS
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
ALLOWED_ORIGINS = [o.strip().rstrip('/') for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
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
        "<h1>JetCheck API</h1>"
        "<p>Welcome! The API is running.</p>"
        "<h2>Endpoints:</h2>"
        "<ul>"
        "  <li><a href='/api/flights'>/api/flights</a> (uses flights_public)</li>"
        "  <li><a href='/healthz'>/healthz</a></li>"
        "</ul>"
    ), 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route("/healthz")
def healthz():
    ok_env = bool(SUPABASE_URL) and bool(SUPABASE_KEY)
    status_code = 200 if ok_env else 500
    return jsonify({"ok": ok_env}), status_code

# Unified endpoint backed by the 'flights_public' view
@app.route("/api/flights", methods=["GET", "OPTIONS"])
def get_flights():
    if supabase is None:
        return jsonify({"error": "Supabase client not configured"}), 500
    try:
        resp = (
            supabase
            .table("flights_public")
            .select(
                "id,source,origin_iata,origin_name,destination_iata,destination_name,"
                "departure_ts,arrival_ts,aircraft,"
                "price_current,price_normal,discount_percent,"
                "currency_effective,status_latest,link_latest,last_seen_at"
            )
            .order("departure_ts", desc=False, nullsfirst=False)
            .limit(500)
            .execute()
        )
        return jsonify(resp.data or [])
    except Exception as e:
        print(f"❌ /api/flights error: {e}", file=sys.stderr)
        traceback.print_exc()  # add this
        return jsonify({"error": "Failed to fetch flights"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = bool(int(os.getenv("FLASK_DEBUG", "0")))
    app.run(host="0.0.0.0", port=port, debug=debug)