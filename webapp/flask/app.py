# webapp/flask/app.py
from flask import Flask, jsonify, render_template, request
from pathlib import Path
import json
import os
import re
import tempfile

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
    try:
        data = json.loads(p.read_text())
    except Exception:
        return jsonify([])
    if not isinstance(data, list):
        return jsonify([])
    return jsonify(data)


@app.route("/api/watches")
def watches():
    return jsonify(_load_watches())


# Keep in sync with slugify() in watch_monitor.py (separate process, no shared import).
def _slugify(brand, model):
    raw = f"{brand} {model}".lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", raw)).strip("-")


def _load_watches():
    p = DATA_DIR / "watches.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save_watches(watches):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(watches, f, indent=2)
        os.replace(tmp, DATA_DIR / "watches.json")
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _validate(payload):
    """Return (entry, error). entry is the normalized dict on success."""
    for field in ("brand", "model"):
        if not payload.get(field):
            return None, f"{field} is required"
    if payload.get("size_mm") is None:
        return None, "size_mm is required"
    refs = payload.get("refs") or []
    if not any(r.get("dial") and r.get("strap") and r.get("ref") for r in refs):
        return None, "at least one ref with dial and strap is required"
    brand, model = payload["brand"], payload["model"]
    rel = payload.get("relevance_required_all")
    if not rel:
        words = re.findall(r"[a-z0-9]+", f"{brand} {model}".lower())
        rel = [words]
    entry = {
        "id": _slugify(brand, model),
        "brand": brand,
        "model": model,
        "size_mm": payload["size_mm"],
        "search_terms": payload.get("search_terms") or [f"{brand} {model}".lower()],
        "relevance_required_all": rel,
        "refs": refs,
        "price_ceiling": payload.get("price_ceiling"),
        "notes": payload.get("notes", ""),
    }
    return entry, None


@app.route("/api/watches", methods=["POST"])
def create_watch():
    entry, err = _validate(request.get_json(silent=True) or {})
    if err:
        return jsonify({"error": err}), 400
    watches = _load_watches()
    if any(w.get("id") == entry["id"] for w in watches):
        return jsonify({"error": "a watch with that brand+model already exists"}), 409
    watches.append(entry)
    _save_watches(watches)
    return jsonify(entry), 201


@app.route("/api/watches/<watch_id>", methods=["PUT"])
def update_watch(watch_id):
    entry, err = _validate(request.get_json(silent=True) or {})
    if err:
        return jsonify({"error": err}), 400
    watches = _load_watches()
    idx = next((i for i, w in enumerate(watches) if w.get("id") == watch_id), None)
    if idx is None:
        return jsonify({"error": "not found"}), 404
    entry["id"] = watch_id  # preserve the id being edited
    watches[idx] = entry
    _save_watches(watches)
    return jsonify(entry), 200


@app.route("/api/watches/<watch_id>", methods=["DELETE"])
def delete_watch(watch_id):
    watches = _load_watches()
    remaining = [w for w in watches if w.get("id") != watch_id]
    if len(remaining) == len(watches):
        return jsonify({"error": "not found"}), 404
    _save_watches(remaining)
    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)
