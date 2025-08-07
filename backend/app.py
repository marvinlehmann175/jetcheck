import os
from dotenv import load_dotenv
from supabase import create_client
from flask import Flask, jsonify
import json

app = Flask(__name__)

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route("/api/globeair")
def get_globeair():
    response = supabase.table("globeair_flights").select("*").execute()
    return jsonify(response.data)

@app.route("/api/asl")
def get_asl():
    with open("flights_asl.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/")
def index():
    return """
    <h1>JetCheck API</h1>
    <p>Welcome! The API is running.</p>
    <ul>
        <li><a href='/api/globeair'>/api/globeair</a></li>
        <li><a href='/api/asl'>/api/asl</a></li>
    </ul>
    """

if __name__ == "__main__":
    app.run(debug=True)
