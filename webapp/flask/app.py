# webapp/flask/app.py
from flask import Flask, jsonify, render_template
from pathlib import Path
import json

app = Flask(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/deals")
def deals():
    p = DATA_DIR / "deals.json"
    if not p.exists():
        return jsonify([])
    return jsonify(json.loads(p.read_text()))


@app.route("/api/watches")
def watches():
    p = DATA_DIR / "watches.json"
    if not p.exists():
        return jsonify([])
    return jsonify(json.loads(p.read_text()))


if __name__ == "__main__":
    app.run(port=5000, debug=True)
