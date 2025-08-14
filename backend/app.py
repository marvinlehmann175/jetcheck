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
        q = supabase.table("flights_public").select(
            "id,canonical_hash,"
            "origin_iata,origin_name,origin_lat,origin_lon,"
            "destination_iata,destination_name,destination_lat,destination_lon,"
            "departure_ts,arrival_ts,aircraft,"
            "price_current,price_normal,discount_percent,"
            "currency_effective,status_latest,link_latest,last_seen_at,"
            "probability"
        )

        # --- filters (all optional) ---
        origin = (request.args.get("from") or "").strip().upper()
        dest   = (request.args.get("to") or "").strip().upper()
        status = (request.args.get("status") or "").strip().lower()
        aircraft = (request.args.get("aircraft") or "").strip()

        if origin:
            q = q.eq("origin_iata", origin)
        if dest:
            q = q.eq("destination_iata", dest)
        if status in ("available", "pending"):
            q = q.eq("status_latest", status)
        if aircraft:
            q = q.eq("aircraft", aircraft)

        # single date or date range
        date_exact = (request.args.get("date") or "").strip()
        date_from  = (request.args.get("date_from") or "").strip()
        date_to    = (request.args.get("date_to") or "").strip()

        if date_exact:
            # compare by day range (UTC)
            q = q.gte("departure_ts", f"{date_exact}T00:00:00Z") \
                 .lte("departure_ts", f"{date_exact}T23:59:59Z")
        else:
            if date_from:
                q = q.gte("departure_ts", f"{date_from}T00:00:00Z")
            if date_to:
                q = q.lte("departure_ts", f"{date_to}T23:59:59Z")

        # price / discount
        max_price = request.args.get("max_price")
        min_disc  = request.args.get("min_discount")
        try:
            if max_price is not None and max_price != "":
                q = q.lte("price_current", float(max_price))
        except ValueError:
            pass
        try:
            if min_disc is not None and min_disc != "":
                q = q.gte("discount_percent", float(min_disc))
        except ValueError:
            pass

        # --- sorting ---
        sort_key = request.args.get("sort_key", "departure_ts")
        sort_dir = request.args.get("sort_dir", "asc").lower()
        sort_key_map = {
            "departure_ts": "departure_ts",
            "price_current": "price_current",
            "last_seen_at": "last_seen_at",
        }
        col = sort_key_map.get(sort_key, "departure_ts")
        asc = (sort_dir != "desc")
        q = q.order(col, desc=not asc, nullsfirst=False)

        # --- pagination ---
        page = request.args.get("page", "1")
        page_size = request.args.get("page_size", "100")
        try:
            page = max(1, int(page))
        except ValueError:
            page = 1
        try:
            page_size = max(1, min(500, int(page_size)))
        except ValueError:
            page_size = 100
        start = (page - 1) * page_size
        end = start + page_size - 1
        q = q.range(start, end)

        resp = q.execute()
        out = resp.data or []

        # make responses explicitly non-cacheable (optional)
        response = jsonify(out)
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as e:
        err = getattr(e, "args", [str(e)])[0]
        print(f"❌ /api/flights error: {err}", file=sys.stderr)
        traceback.print_exc()
        if os.getenv("FLASK_DEBUG", "0") == "1":
            return jsonify({"error": "Failed to fetch flights", "detail": str(err)}), 500
        return jsonify({"error": "Failed to fetch flights"}), 500
    
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = bool(int(os.getenv("FLASK_DEBUG", "0")))
    app.run(host="0.0.0.0", port=port, debug=debug)