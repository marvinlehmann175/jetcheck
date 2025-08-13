import os
import sys
import flask
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from supabase import create_client, Client
import json

# Load .env locally; on Render env vars are provided in the dashboard
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Prefer service role key if present; fall back to SUPABASE_KEY for backward compatibility
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
        "  <li><a href='/api/flights'>/api/flights</a> (NEW – uses flights_public)</li>"
        "  <li><a href='/api/globeair'>/api/globeair</a> (legacy, old table if still needed)</li>"
        "  <li><a href='/api/asl'>/api/asl</a> (static JSON if present)</li>"
        "  <li><a href='/healthz'>/healthz</a></li>"
        "</ul>"
    ), 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route("/healthz")
def healthz():
    ok_env = bool(SUPABASE_URL) and bool(SUPABASE_KEY)
    status_code = 200 if ok_env else 500
    return jsonify({"ok": ok_env}), status_code

# ---- NEW: unified endpoint backed by the 'flights_public' view ----
# Supports optional query params for server-side filtering/sorting:
#   q, from, to, date (YYYY-MM-DD), maxPrice, status (available|pending),
#   sort (departure|price|seen), dir (asc|desc), limit (<= 500)
@app.route("/api/flights", methods=["GET", "OPTIONS"])
def get_flights():
    if supabase is None:
        return jsonify({"error": "Supabase client not configured"}), 500

    try:
        q = supabase.table("flights_public").select(
            "id,source,origin_iata,origin_name,destination_iata,destination_name,"
            "departure_ts,arrival_ts,aircraft,"
            "price_current,price_normal,discount_percent,"
            "currency_effective,status_latest,link_latest,last_seen_at"
        )

        # ---- Filters ----
        qstr = (request.args.get("q") or "").strip()
        from_q = (request.args.get("from") or "").strip()
        to_q   = (request.args.get("to") or "").strip()
        date_q = (request.args.get("date") or "").strip()        # YYYY-MM-DD
        max_price_q = (request.args.get("maxPrice") or "").strip()
        status_q = (request.args.get("status") or "").strip().lower()  # available|pending

        if qstr:
            pat = f"%{qstr}%"
            q = q.or_(
                f"origin_name.ilike.{pat},destination_name.ilike.{pat},"
                f"origin_iata.ilike.{pat},destination_iata.ilike.{pat}",
                reference_table="flights_public"
            )

        if from_q:
            pat = f"%{from_q}%"
            q = q.or_(
                f"origin_name.ilike.{pat},origin_iata.ilike.{pat}",
                reference_table="flights_public"
            )

        if to_q:
            pat = f"%{to_q}%"
            q = q.or_(
                f"destination_name.ilike.{pat},destination_iata.ilike.{pat}",
                reference_table="flights_public"
            )

        if date_q:
            start = f"{date_q}T00:00:00Z"
            end   = f"{date_q}T23:59:59Z"
            q = q.filter("departure_ts", "gte", start).filter("departure_ts", "lte", end)

        if max_price_q:
            try:
                maxv = int(float(max_price_q))
                q = q.or_(
                    f"price_current.lte.{maxv},price_normal.lte.{maxv}",
                    reference_table="flights_public"
                )
            except ValueError:
                pass

        if status_q in ("available", "pending"):
            q = q.eq("status_latest", status_q)

        # ---- Sorting ----
        sort = (request.args.get("sort") or "departure").lower()
        direction = (request.args.get("dir") or "asc").lower()
        desc = True if direction == "desc" else False

        sort_map = {
            "departure": "departure_ts",
            "price": "price_current",
            "seen": "last_seen_at",
        }
        sort_col = sort_map.get(sort, "departure_ts")
        q = q.order(sort_col, desc=desc, nullsfirst=False)

        # ---- Limit ----
        try:
            limit = min(max(int(request.args.get("limit", "500")), 1), 500)
        except ValueError:
            limit = 500
        q = q.limit(limit)

        resp = q.execute()
        return jsonify(resp.data or [])

    except Exception as e:
        print(f"❌ /api/flights error: {e}", file=sys.stderr)
        return jsonify({"error": "Failed to fetch flights"}), 500
# Legacy endpoint (kept for compatibility while frontend migrates)
TABLE = os.getenv("SUPABASE_TABLE", "globeair_flights")  # legacy table name
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
            .limit(500)
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
    port = int(os.getenv("PORT", "5000"))
    debug = bool(int(os.getenv("FLASK_DEBUG", "0")))
    app.run(host="0.0.0.0", port=port, debug=debug)