# webapp/flask/app.py
from flask import Flask, jsonify, render_template, request
from pathlib import Path
import json
import logging
import os
import re
import subprocess
import tempfile

app = Flask(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger(__name__)


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


# Watch-id slug from brand + model (this app is the only place watch ids are minted).
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
    if not any(r.get("ref") for r in refs):
        return None, "at least one ref is required"
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


def _load_deals():
    p = DATA_DIR / "deals.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save_deals(deals):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(deals, f, indent=2)
        os.replace(tmp, DATA_DIR / "deals.json")
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


@app.route("/api/deals/<deal_id>", methods=["DELETE"])
def delete_deal(deal_id):
    deals = _load_deals()
    remaining = [d for d in deals if d.get("id") != deal_id]
    if len(remaining) == len(deals):
        return jsonify({"error": "not found"}), 404
    _save_deals(remaining)
    return jsonify({"ok": True}), 200


def _git(*args):
    # Local-only convenience routes: this Flask app is meant to run on the user's
    # machine, so invoking git (including push) from a route is a deliberate design
    # choice, not a public endpoint. No CSRF/auth guard by design.
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=30)


@app.route("/api/status")
def status():
    try:
        st = _git("status", "--porcelain", "data/watches.json", "data/deals.json")
        dirty = bool(st.stdout.strip())
        ahead_res = _git("rev-list", "--count", "@{u}..HEAD")
        ahead = int(ahead_res.stdout.strip()) if ahead_res.returncode == 0 else 0
    except Exception as e:
        log.warning("git status check failed: %s", e)
        return jsonify({"dirty": False, "ahead": 0, "needs_push": False})
    return jsonify({"dirty": dirty, "ahead": ahead,
                    "needs_push": dirty or ahead > 0})


@app.route("/api/push", methods=["POST"])
def push():
    try:
        add = _git("add", "data/watches.json", "data/deals.json")
        if add.returncode != 0:
            return jsonify({"ok": False, "error": add.stderr.strip()}), 500
        diff = _git("diff", "--cached", "--quiet", "data/watches.json", "data/deals.json")
        if diff.returncode == 1:  # 1 => staged changes present
            commit = _git("commit", "-m", "chore: update watch registry and deals")
            if commit.returncode != 0:
                return jsonify({"ok": False, "error": commit.stderr.strip()}), 500
        push_res = _git("push")
        if push_res.returncode != 0:
            return jsonify({"ok": False, "error": push_res.stderr.strip()}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "git command timed out"}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
