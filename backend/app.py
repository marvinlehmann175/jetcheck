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

if __name__ == "__main__":
    app.run(debug=True)
