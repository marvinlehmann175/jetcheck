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
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")  # e.g. https://jetcheck-eight.vercel.app

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_KEY in environment.", file=sys.stderr)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

app = Flask(__name__)

# Minimal CORS without extra deps; adjust ALLOWED_ORIGIN in env for production
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
        # Select common fields and order by newest id first
        resp = (
            supabase
            .table(TABLE)
            .select("route,date,time,price,link,probability,id")
            .order("id", desc=True)
            .execute()
        )
        data = resp.data or []
        return jsonify(data)
    except Exception as e:
        print(f"❌ /api/globeair error: {e}", file=sys.stderr)
        return jsonify({"error": "Failed to fetch flights"}), 500


@app.route("/api/asl")
def get_asl():
    # Keep compatibility: serve static JSON if present; otherwise empty list
    path = os.path.join(os.path.dirname(__file__), "flights_asl.json")
    if os.path.exists(path):
        import json
        with open(path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])


if __name__ == "__main__":
    # Useful for local testing
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)