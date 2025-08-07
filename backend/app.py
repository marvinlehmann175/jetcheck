from flask import Flask, jsonify
import json

app = Flask(__name__)

@app.route("/api/globeair")
def get_globeair():
    with open("flights.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

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
