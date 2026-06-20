# Watch Deals Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web app (Flask + Streamlit, two ports) that reads a `deals.json` deal database populated by the hourly GitHub Actions monitor and lets you filter by price, brand, model, dial color, strap, source, and date.

**Architecture:** The monitor writes every new listing to `data/deals.json` (tagged with brand/model/ref/dial/strap from a `data/watches.json` registry) alongside the existing `data/monitor_state.json`. The Flask app serves `data/deals.json` via a tiny API and renders a Dark Luxury Data Dense HTML/CSS/JS UI. The Streamlit app reads the same file directly. A single `webapp/start.sh` starts both on different ports and opens two browser tabs.

**Tech Stack:** Python 3.12, Flask 3.x, Streamlit 1.35+, pandas 2.x, pytest, vanilla JS (no framework), GitHub Actions.

**User decisions (already made):**
- Storage: `data/deals.json` (JSON, committed by GH Actions each run)
- Both Flask (:5000) and Streamlit (:8501) built; drop one later by deleting its folder
- Aesthetic: Dark Luxury Data Dense (near-black background, gold accents, compact table)
- One startup script opens both browser tabs
- Watch registry (`data/watches.json`) tags deals at ingest; ref → dial/strap as source of truth
- Data directory named `data/`; `monitor_state.json` moved there from repo root

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `data/watches.json` | Watch registry — brand, model, refs, dial/strap, price ceiling |
| Move | `monitor_state.json` → `data/monitor_state.json` | Dedup IDs (existing file, new path) |
| Auto-created | `data/deals.json` | Deal database written by monitor |
| Modify | `watch_monitor.py` | New path constants, tagging logic, save_deals() |
| Modify | `.github/workflows/monitor.yml` | Commit data/deals.json alongside state |
| Modify | `requirements.txt` | Add flask, streamlit, pandas, pytest |
| Create | `webapp/start.sh` | One-click launcher |
| Create | `webapp/flask/app.py` | Flask server — 3 routes |
| Create | `webapp/flask/templates/index.html` | Page shell |
| Create | `webapp/flask/static/style.css` | Dark Luxury Data Dense styles |
| Create | `webapp/flask/static/app.js` | Fetch, filter, sort, render |
| Create | `webapp/streamlit/app.py` | Streamlit app |
| Create | `tests/test_tagging.py` | Unit tests for tag_deal + save_deals |
| Create | `webapp/flask/tests/test_app.py` | Flask route tests |

---

## Task 0: Data directory setup + path migration

**Goal:** Create `data/`, populate `data/watches.json`, move `monitor_state.json` to `data/`, and update all references so the monitor still runs cleanly.

**Files:**
- Create: `data/watches.json`
- Modify: `watch_monitor.py` line 52
- Modify: `.github/workflows/monitor.yml` lines 58–62

**Acceptance Criteria:**
- [ ] `data/watches.json` exists and contains the Longines registry entry with all 5 refs
- [ ] `watch_monitor.py` `STATE_FILE` resolves to `data/monitor_state.json`
- [ ] `python watch_monitor.py --test` runs without error (ntfy push test still works)
- [ ] `monitor.yml` `git add` and `git status` reference `data/monitor_state.json`

**Verify:** `python watch_monitor.py --test` → "Test push sent — check your phone." (or the ntfy error if NTFY_TOPIC not set, but no Python crash)

**Steps:**

- [ ] **Step 1: Create `data/watches.json`**

```json
[
  {
    "brand": "Longines",
    "model": "Master Collection Chrono Moonphase",
    "size_mm": 40,
    "refs": [
      { "ref": "L2.673.4.78.6", "dial": "silver",     "strap": "bracelet" },
      { "ref": "L2.673.4.78.3", "dial": "silver",     "strap": "leather"  },
      { "ref": "L2.673.4.61.6", "dial": "anthracite", "strap": "bracelet" },
      { "ref": "L2.673.4.71.2", "dial": "ivory",      "strap": "leather"  },
      { "ref": "L2.673.4.92.0", "dial": "blue",       "strap": "bracelet" }
    ],
    "search_terms": [
      "longines master moonphase",
      "longines master chronograph moonphase"
    ],
    "price_ceiling": 2000,
    "notes": "40mm only — 42mm is L2.773 family, not the target"
  }
]
```

- [ ] **Step 2: Move `monitor_state.json` if it exists**

```bash
git mv monitor_state.json data/monitor_state.json 2>/dev/null || true
```

If the file doesn't exist yet (fresh clone), skip — the monitor creates it on first run.

- [ ] **Step 3: Update `STATE_FILE` in `watch_monitor.py`**

Replace line 52:
```python
# Before
STATE_FILE = Path(__file__).with_name("monitor_state.json")
```
With:
```python
STATE_FILE = Path(__file__).parent / "data" / "monitor_state.json"
```

- [ ] **Step 4: Update `monitor.yml` persist step**

Replace lines 53–66 (the "Persist dedup state" step):
```yaml
      - name: Persist monitor data
        # Commit data files back so dedup memory and deal database survive between runs.
        # This commit also keeps the repo "active", preventing GitHub from
        # auto-disabling scheduled workflows after 60 days of inactivity.
        run: |
          if [ -n "$(git status --porcelain data/monitor_state.json data/deals.json)" ]; then
            git config user.name "watch-tracker-bot"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git add data/monitor_state.json data/deals.json
            git commit -m "chore: update monitor state [skip ci]"
            git push
          else
            echo "No state change to commit."
          fi
```

- [ ] **Step 5: Verify monitor still runs**

```bash
python watch_monitor.py --test
```

Expected: "Test push sent — check your phone." (or ntfy error if secret not set). No Python traceback.

- [ ] **Step 6: Commit**

```bash
git add data/watches.json watch_monitor.py .github/workflows/monitor.yml
git add data/monitor_state.json 2>/dev/null || true
git commit -m "feat: move data files to data/ directory, add watch registry"
```

---

## Task 1: Monitor deal tagging and persistence

**Goal:** Extend `watch_monitor.py` so every new listing is tagged with brand/model/ref/dial/strap from the registry and appended to `data/deals.json`.

**Files:**
- Modify: `watch_monitor.py` (add constants + 3 functions + update `main()`)
- Create: `tests/test_tagging.py`

**Acceptance Criteria:**
- [ ] `tag_deal(item, registry)` returns item with `brand`, `model`, `size_mm`, `ref_matches`, `dial`, `strap`, `is_hot`, `date_seen`, `preferred_signals` fields set
- [ ] `ref_matches` is `[]` and `dial`/`strap` are `None` when no ref appears in title
- [ ] `is_hot` is `True` iff `price <= price_ceiling` and price is not None
- [ ] `save_deals([])` is a no-op (no file written)
- [ ] `save_deals(items)` creates `data/deals.json` if absent; appends if present
- [ ] All 11 tests in `tests/test_tagging.py` pass

**Verify:** `pytest tests/test_tagging.py -v` → 11 passed

**Steps:**

- [ ] **Step 1: Write failing tests**

Create `tests/__init__.py` (empty) and `tests/test_tagging.py`:

```python
# tests/test_tagging.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from watch_monitor import tag_deal, save_deals

REGISTRY = [
    {
        "brand": "Longines",
        "model": "Master Collection Chrono Moonphase",
        "size_mm": 40,
        "refs": [
            {"ref": "L2.673.4.78.6", "dial": "silver",     "strap": "bracelet"},
            {"ref": "L2.673.4.78.3", "dial": "silver",     "strap": "leather"},
            {"ref": "L2.673.4.61.6", "dial": "anthracite", "strap": "bracelet"},
        ],
        "search_terms": ["longines master moonphase", "longines master chronograph moonphase"],
        "price_ceiling": 2000,
    }
]

BASE_ITEM = {
    "id": "reddit:abc",
    "title": "Longines Master Moonphase 40mm steel bracelet",
    "price": 1750,
    "url": "https://reddit.com/r/Watchexchange/comments/abc",
    "source": "r/watchexchange",
}


def test_tag_matches_registry_by_search_term():
    result = tag_deal(dict(BASE_ITEM), REGISTRY)
    assert result["brand"] == "Longines"
    assert result["model"] == "Master Collection Chrono Moonphase"
    assert result["size_mm"] == 40


def test_tag_extracts_ref_sets_dial_and_strap():
    item = {**BASE_ITEM, "title": "Longines Master Moonphase L2.673.4.78.6 box papers"}
    result = tag_deal(item, REGISTRY)
    assert result["ref_matches"] == ["L2.673.4.78.6"]
    assert result["dial"] == "silver"
    assert result["strap"] == "bracelet"


def test_tag_collects_multiple_refs():
    item = {**BASE_ITEM, "title": "Longines L2.673.4.78.6 or L2.673.4.78.3 available"}
    result = tag_deal(item, REGISTRY)
    assert "L2.673.4.78.6" in result["ref_matches"]
    assert "L2.673.4.78.3" in result["ref_matches"]
    assert result["dial"] == "silver"   # first match wins for dial/strap
    assert result["strap"] == "bracelet"


def test_tag_no_ref_in_title():
    item = {**BASE_ITEM, "title": "Longines Master Moonphase 40mm no ref mentioned"}
    result = tag_deal(item, REGISTRY)
    assert result["ref_matches"] == []
    assert result["dial"] is None
    assert result["strap"] is None


def test_tag_is_hot_at_ceiling():
    item = {**BASE_ITEM, "price": 2000}
    result = tag_deal(item, REGISTRY)
    assert result["is_hot"] is True


def test_tag_not_hot_above_ceiling():
    item = {**BASE_ITEM, "price": 2001}
    result = tag_deal(item, REGISTRY)
    assert result["is_hot"] is False


def test_tag_not_hot_when_price_none():
    item = {**BASE_ITEM, "price": None}
    result = tag_deal(item, REGISTRY)
    assert result["is_hot"] is False


def test_tag_no_registry_match_returns_nulls():
    item = {**BASE_ITEM, "title": "Rolex Submariner Date"}
    result = tag_deal(item, REGISTRY)
    assert result["brand"] is None
    assert result["ref_matches"] == []
    assert result["is_hot"] is False


def test_tag_adds_date_seen():
    result = tag_deal(dict(BASE_ITEM), REGISTRY)
    assert "date_seen" in result
    assert "T" in result["date_seen"]   # ISO format


def test_save_deals_creates_file(tmp_path):
    deals_file = tmp_path / "deals.json"
    items = [{"id": "test:1", "title": "Test Watch", "price": 100}]
    with patch("watch_monitor.DEALS_FILE", deals_file):
        save_deals(items)
    assert deals_file.exists()
    saved = json.loads(deals_file.read_text())
    assert len(saved) == 1
    assert saved[0]["id"] == "test:1"


def test_save_deals_appends_to_existing(tmp_path):
    deals_file = tmp_path / "deals.json"
    deals_file.write_text(json.dumps([{"id": "test:0", "title": "Old"}]))
    items = [{"id": "test:1", "title": "New"}]
    with patch("watch_monitor.DEALS_FILE", deals_file):
        save_deals(items)
    saved = json.loads(deals_file.read_text())
    assert len(saved) == 2
    assert saved[1]["id"] == "test:1"
```

- [ ] **Step 2: Run tests — confirm all fail**

```bash
pytest tests/test_tagging.py -v
```

Expected: `ImportError` or `AttributeError: module 'watch_monitor' has no attribute 'tag_deal'`

- [ ] **Step 3: Add constants and new functions to `watch_monitor.py`**

After line 52 (the updated `STATE_FILE` line), add:

```python
DEALS_FILE    = Path(__file__).parent / "data" / "deals.json"
REGISTRY_FILE = Path(__file__).parent / "data" / "watches.json"
```

Then add these three functions after the existing `save_state()` function (around line 76):

```python
def load_registry():
    if not REGISTRY_FILE.exists():
        return []
    try:
        return json.loads(REGISTRY_FILE.read_text())
    except Exception as e:
        log(f"WARN: could not read registry ({e}); tagging disabled.")
        return []


def tag_deal(item, registry):
    """Enrich a listing dict with brand/model/ref/dial/strap/is_hot from the registry."""
    item = dict(item)
    item["date_seen"] = datetime.now(timezone.utc).isoformat()
    item["brand"] = None
    item["model"] = None
    item["size_mm"] = None
    item["ref_matches"] = []
    item["dial"] = None
    item["strap"] = None
    item["is_hot"] = False
    item["preferred_signals"] = preferred_hits(item["title"])

    title_lower = item["title"].lower()
    for entry in registry:
        if any(term in title_lower for term in entry.get("search_terms", [])):
            item["brand"] = entry.get("brand")
            item["model"] = entry.get("model")
            item["size_mm"] = entry.get("size_mm")

            matched = [r for r in entry.get("refs", []) if r["ref"].lower() in title_lower]
            item["ref_matches"] = [r["ref"] for r in matched]
            if matched:
                item["dial"] = matched[0].get("dial")
                item["strap"] = matched[0].get("strap")

            ceiling = entry.get("price_ceiling", float("inf"))
            item["is_hot"] = item.get("price") is not None and item["price"] <= ceiling
            break

    return item


def save_deals(new_items):
    """Append new tagged deals to data/deals.json (creates file if absent)."""
    if not new_items:
        return
    existing = []
    if DEALS_FILE.exists():
        try:
            existing = json.loads(DEALS_FILE.read_text())
        except Exception as e:
            log(f"WARN: could not read deals file ({e}); starting fresh.")
    existing.extend(new_items)
    DEALS_FILE.write_text(json.dumps(existing, indent=2))
```

- [ ] **Step 4: Update `main()` to tag and save all new deals**

In `main()`, find the block starting with `pushed = 0` (around line 309). Replace:

```python
pushed = 0
for it in new_items[:MAX_PUSH_PER_RUN]:
    if push_ntfy(it):
        push_telegram(it)
        seen.add(it["id"])
        pushed += 1
        log(f"  pushed: {it['id']} {it.get('price')} {it['title'][:60]}")
```

With:

```python
registry = load_registry()
tagged_new = [tag_deal(it, registry) for it in new_items]

pushed = 0
for it in tagged_new[:MAX_PUSH_PER_RUN]:
    if push_ntfy(it):
        push_telegram(it)
        seen.add(it["id"])
        pushed += 1
        log(f"  pushed: {it['id']} {it.get('price')} {it['title'][:60]}")

# Save ALL new deals (including overflow beyond MAX_PUSH_PER_RUN) to the web app DB.
save_deals(tagged_new)
```

- [ ] **Step 5: Run tests — confirm all pass**

```bash
pytest tests/test_tagging.py -v
```

Expected:
```
tests/test_tagging.py::test_tag_matches_registry_by_search_term PASSED
tests/test_tagging.py::test_tag_extracts_ref_sets_dial_and_strap PASSED
tests/test_tagging.py::test_tag_collects_multiple_refs PASSED
tests/test_tagging.py::test_tag_no_ref_in_title PASSED
tests/test_tagging.py::test_tag_is_hot_at_ceiling PASSED
tests/test_tagging.py::test_tag_not_hot_above_ceiling PASSED
tests/test_tagging.py::test_tag_not_hot_when_price_none PASSED
tests/test_tagging.py::test_no_registry_match_returns_nulls PASSED
tests/test_tagging.py::test_tag_adds_date_seen PASSED
tests/test_tagging.py::test_save_deals_creates_file PASSED
tests/test_tagging.py::test_save_deals_appends_to_existing PASSED

11 passed
```

- [ ] **Step 6: Commit**

```bash
git add watch_monitor.py tests/__init__.py tests/test_tagging.py
git commit -m "feat: tag deals with registry metadata and persist to data/deals.json"
```

---

## Task 2: Flask backend

**Goal:** Create a minimal Flask server that serves `data/deals.json` and `data/watches.json` via two JSON endpoints, plus the HTML shell.

**Files:**
- Create: `webapp/flask/app.py`
- Create: `webapp/flask/tests/__init__.py` (empty)
- Create: `webapp/flask/tests/test_app.py`
- Create: `webapp/flask/templates/` (directory, created implicitly)

**Acceptance Criteria:**
- [ ] `GET /` returns HTTP 200 with HTML containing `<title>Watch Deals</title>`
- [ ] `GET /api/deals` returns `[]` when `data/deals.json` absent, or its contents when present
- [ ] `GET /api/watches` returns `[]` when `data/watches.json` absent, or its contents when present
- [ ] All 5 Flask route tests pass

**Verify:** `pytest webapp/flask/tests/test_app.py -v` → 5 passed

**Steps:**

- [ ] **Step 1: Write failing tests**

Create `webapp/flask/tests/__init__.py` (empty) and `webapp/flask/tests/test_app.py`:

```python
# webapp/flask/tests/test_app.py
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_index_returns_200(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Watch Deals" in r.data


def test_api_deals_empty_when_no_file(client, tmp_path):
    with patch("app.DATA_DIR", tmp_path):
        r = client.get("/api/deals")
    assert r.status_code == 200
    assert json.loads(r.data) == []


def test_api_deals_returns_contents(client, tmp_path):
    deals = [{"id": "test:1", "price": 1500, "title": "Test Watch"}]
    (tmp_path / "deals.json").write_text(json.dumps(deals))
    with patch("app.DATA_DIR", tmp_path):
        r = client.get("/api/deals")
    assert json.loads(r.data) == deals


def test_api_watches_empty_when_no_file(client, tmp_path):
    with patch("app.DATA_DIR", tmp_path):
        r = client.get("/api/watches")
    assert r.status_code == 200
    assert json.loads(r.data) == []


def test_api_watches_returns_contents(client, tmp_path):
    watches = [{"brand": "Longines", "model": "Master"}]
    (tmp_path / "watches.json").write_text(json.dumps(watches))
    with patch("app.DATA_DIR", tmp_path):
        r = client.get("/api/watches")
    assert json.loads(r.data) == watches
```

- [ ] **Step 2: Run tests — confirm all fail**

```bash
pytest webapp/flask/tests/test_app.py -v
```

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Create `webapp/flask/app.py`**

```python
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
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
pytest webapp/flask/tests/test_app.py -v
```

Expected:
```
webapp/flask/tests/test_app.py::test_index_returns_200 FAILED  ← needs index.html first
```

The index test fails because `index.html` doesn't exist yet — that's expected. The 4 API tests should pass. Create a stub template to make the index test pass too:

Create `webapp/flask/templates/index.html` (stub — will be replaced in Task 3):

```html
<!DOCTYPE html>
<html><head><title>Watch Deals</title></head><body>stub</body></html>
```

Run again:
```bash
pytest webapp/flask/tests/test_app.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add webapp/flask/app.py webapp/flask/templates/index.html webapp/flask/tests/
git commit -m "feat: add Flask backend with /api/deals and /api/watches routes"
```

---

## Task 3: Flask frontend — HTML and CSS

**Goal:** Replace the stub `index.html` with the full Dark Luxury Data Dense page shell and write the complete stylesheet.

**Files:**
- Modify: `webapp/flask/templates/index.html`
- Create: `webapp/flask/static/style.css`

**Acceptance Criteria:**
- [ ] `python webapp/flask/app.py` starts without error
- [ ] `http://localhost:5000` loads with a near-black background and gold "WATCH DEALS" header
- [ ] Sidebar with all 9 filter sections is visible
- [ ] Table with column headers is visible
- [ ] Page renders without console JS errors (JS not wired yet — expected empty tbody)

**Verify:** `python webapp/flask/app.py` then open `http://localhost:5000` — confirm visual matches the design spec mockup.

**Steps:**

- [ ] **Step 1: Write `webapp/flask/templates/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Watch Deals</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>

<header class="app-header">
  <div class="app-title">Watch Deals</div>
  <div class="app-meta">Last synced <span id="last-sync">—</span></div>
</header>

<div class="layout">

  <aside class="sidebar">

    <div class="filter-section">
      <span class="filter-label">Hot Deals</span>
      <div class="toggle-row">
        <span class="toggle-label">Under ceiling only</span>
        <button class="toggle" id="hot-toggle" aria-pressed="false">
          <span class="toggle-dot"></span>
        </button>
      </div>
    </div>

    <div class="filter-section">
      <span class="filter-label">Price Range</span>
      <div class="price-row">
        <input class="price-input" id="price-min" type="number" placeholder="$min">
        <span class="price-sep">–</span>
        <input class="price-input" id="price-max" type="number" placeholder="$max">
      </div>
    </div>

    <div class="filter-section">
      <span class="filter-label">Brand</span>
      <select class="filter-select" id="brand-select">
        <option value="">All brands</option>
      </select>
    </div>

    <div class="filter-section">
      <span class="filter-label">Model</span>
      <select class="filter-select" id="model-select">
        <option value="">All models</option>
      </select>
    </div>

    <div class="filter-section">
      <span class="filter-label">Size</span>
      <select class="filter-select" id="size-select">
        <option value="">All sizes</option>
      </select>
    </div>

    <div class="filter-section">
      <span class="filter-label">Dial Color</span>
      <select class="filter-select" id="dial-select">
        <option value="">All dials</option>
      </select>
    </div>

    <div class="filter-section">
      <span class="filter-label">Strap</span>
      <select class="filter-select" id="strap-select">
        <option value="">All straps</option>
      </select>
    </div>

    <div class="filter-section">
      <span class="filter-label">Source</span>
      <div class="checkbox-group" id="source-group"></div>
    </div>

    <div class="filter-section">
      <span class="filter-label">Date Seen</span>
      <select class="filter-select" id="date-select">
        <option value="">All time</option>
        <option value="24h">Last 24 hours</option>
        <option value="7d">Last 7 days</option>
        <option value="30d">Last 30 days</option>
      </select>
    </div>

    <button class="clear-btn" id="clear-btn">Clear filters</button>

  </aside>

  <main class="main">

    <div class="toolbar">
      <div class="result-count" id="result-count">Loading…</div>
      <div class="sort-row">
        <span class="sort-label">Sort</span>
        <select class="sort-select" id="sort-select">
          <option value="newest">Newest first</option>
          <option value="price-asc">Price: low to high</option>
          <option value="price-desc">Price: high to low</option>
        </select>
      </div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Price</th>
            <th>Title</th>
            <th>Brand</th>
            <th>Model</th>
            <th>Ref</th>
            <th>Dial / Strap</th>
            <th>Source</th>
            <th>Seen</th>
          </tr>
        </thead>
        <tbody id="deals-tbody"></tbody>
      </table>
      <div class="empty-state" id="empty-state" style="display:none">
        No deals yet — check back after the next monitor run.
      </div>
    </div>

  </main>
</div>

<script src="{{ url_for('static', filename='app.js') }}"></script>
</body>
</html>
```

- [ ] **Step 2: Write `webapp/flask/static/style.css`**

```css
/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: #07070d;
  color: #e0d9cc;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 13px;
  min-height: 100vh;
}

/* ── Header ── */
.app-header {
  background: #0a0a12;
  border-bottom: 1px solid #1e1e2e;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 20;
}

.app-title {
  color: #c9a84c;
  font-size: 12px;
  letter-spacing: 4px;
  text-transform: uppercase;
  font-weight: 400;
}

.app-meta { font-size: 11px; color: #444; }
.app-meta span { color: #c9a84c; }

/* ── Layout ── */
.layout {
  display: flex;
  height: calc(100vh - 49px);
}

/* ── Sidebar ── */
.sidebar {
  width: 220px;
  min-width: 220px;
  background: #09090f;
  border-right: 1px solid #1a1a28;
  padding: 20px 16px;
  overflow-y: auto;
}

.filter-section { margin-bottom: 22px; }

.filter-label {
  display: block;
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #c9a84c;
  margin-bottom: 8px;
}

.filter-select {
  width: 100%;
  background: #111120;
  border: 1px solid #252535;
  color: #c0b89a;
  font-size: 12px;
  padding: 7px 10px;
  border-radius: 4px;
  appearance: none;
  cursor: pointer;
  outline: none;
}
.filter-select:focus { border-color: #c9a84c44; }

/* ── Price range ── */
.price-row { display: flex; gap: 6px; align-items: center; }
.price-input {
  flex: 1;
  background: #111120;
  border: 1px solid #252535;
  color: #c0b89a;
  font-size: 12px;
  padding: 7px 8px;
  border-radius: 4px;
  width: 100%;
  outline: none;
}
.price-input::placeholder { color: #333; }
.price-input:focus { border-color: #c9a84c44; }
.price-sep { color: #444; font-size: 11px; }

/* ── Toggle ── */
.toggle-row { display: flex; align-items: center; justify-content: space-between; }
.toggle-label { font-size: 12px; color: #c0b89a; }

.toggle {
  width: 34px;
  height: 20px;
  background: #1a1a28;
  border: 1px solid #2a2a3a;
  border-radius: 10px;
  position: relative;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  padding: 0;
}
.toggle.active {
  background: #1a2a1a;
  border-color: #2a4a2a;
}
.toggle-dot {
  width: 14px;
  height: 14px;
  background: #333;
  border-radius: 50%;
  position: absolute;
  top: 2px;
  left: 2px;
  transition: left 0.2s, background 0.2s;
}
.toggle.active .toggle-dot {
  left: 16px;
  background: #5db85d;
}

/* ── Source checkboxes ── */
.checkbox-group { display: flex; flex-direction: column; gap: 8px; }
.checkbox-row { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.checkbox-box {
  width: 16px;
  height: 16px;
  background: #111120;
  border: 1px solid #252535;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s, border-color 0.15s;
}
.checkbox-box.checked { background: #c9a84c22; border-color: #c9a84c88; }
.checkbox-box.checked::after { content: '✓'; color: #c9a84c; font-size: 10px; line-height: 1; }
.checkbox-text { font-size: 12px; color: #c0b89a; user-select: none; }
.checkbox-row input[type="checkbox"] { position: absolute; opacity: 0; pointer-events: none; }

/* ── Clear button ── */
.clear-btn {
  width: 100%;
  background: transparent;
  border: 1px solid #252535;
  color: #555;
  font-size: 10px;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  letter-spacing: 1px;
  text-transform: uppercase;
  transition: border-color 0.15s, color 0.15s;
}
.clear-btn:hover { border-color: #c9a84c44; color: #c9a84c; }

/* ── Main content ── */
.main { flex: 1; overflow: auto; }

/* ── Toolbar ── */
.toolbar {
  padding: 12px 20px;
  border-bottom: 1px solid #141420;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #09090f;
  position: sticky;
  top: 0;
  z-index: 10;
}

.result-count { font-size: 11px; color: #444; }
.result-count span { color: #c9a84c; }

.sort-row { display: flex; gap: 8px; align-items: center; }
.sort-label { font-size: 10px; color: #444; letter-spacing: 1px; text-transform: uppercase; }
.sort-select {
  background: #111120;
  border: 1px solid #252535;
  color: #888;
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 4px;
  appearance: none;
  cursor: pointer;
  outline: none;
}

/* ── Table ── */
.table-wrap { padding: 0 20px 40px; }

table { width: 100%; border-collapse: collapse; font-size: 12px; }

thead th {
  padding: 10px 12px 10px 0;
  color: #c9a84c;
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  font-weight: 500;
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid #1e1e2e;
}

tbody tr {
  border-bottom: 1px solid #0f0f1a;
  cursor: pointer;
  transition: background 0.1s;
}
tbody tr:hover { background: #111120; }
tbody tr.hot { border-left: 2px solid #5db85d; }
tbody tr.hot td:first-child { padding-left: 10px; }

td { padding: 9px 12px 9px 0; vertical-align: middle; }

.price-cell { font-weight: 600; white-space: nowrap; }
.price-hot  { color: #5db85d; }
.price-ok   { color: #c0b89a; }
.price-none { color: #444; }

.hot-badge { font-size: 14px; line-height: 1; }

.title-cell {
  max-width: 260px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #d0c9bc;
}

.brand-cell { color: #c9a84c; white-space: nowrap; font-size: 11px; }
.model-cell { color: #9a9282; font-size: 11px; white-space: nowrap; max-width: 180px; overflow: hidden; text-overflow: ellipsis; }
.ref-cell   { font-family: 'Menlo', 'Courier New', monospace; font-size: 10px; color: #665d4a; white-space: nowrap; }
.dial-cell  { font-size: 11px; color: #8a8070; white-space: nowrap; }
.age-cell   { font-size: 11px; color: #444; white-space: nowrap; }

.source-badge {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 10px;
  white-space: nowrap;
  display: inline-block;
}
.source-reddit { background: #1a1520; color: #9c7fc0; border: 1px solid #2a2035; }
.source-ebay   { background: #1a1820; color: #7c9fc0; border: 1px solid #202835; }
.source-chrono { background: #201a10; color: #c09a50; border: 1px solid #352810; }

/* ── Empty state ── */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #333;
  font-size: 13px;
  letter-spacing: 0.5px;
}
```

- [ ] **Step 3: Verify page loads**

```bash
cd webapp/flask && python app.py
```

Open `http://localhost:5000`. Expected:
- Near-black page, gold "WATCH DEALS" header
- Sidebar with 9 filter sections visible
- Empty table with gold column headers
- No JS console errors (except possibly "app.js not found" — that's Task 4)

Stop the server with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add webapp/flask/templates/index.html webapp/flask/static/style.css
git commit -m "feat: add Flask frontend HTML shell and Dark Luxury CSS"
```

---

## Task 4: Flask frontend — JavaScript

**Goal:** Wire up `app.js` — fetch deals/watches, populate filter dropdowns, render the table, and handle all filtering, sorting, and source checkbox interactions.

**Files:**
- Create: `webapp/flask/static/app.js`

**Acceptance Criteria:**
- [ ] Page loads `data/deals.json` via `/api/deals` and renders all rows
- [ ] "Last synced" shows relative time of the most recently seen deal
- [ ] Brand, Model, Size, Dial, Strap dropdowns are populated from deal data
- [ ] Model dropdown options update when Brand filter changes
- [ ] Source checkboxes are built dynamically and checked by default
- [ ] Hot toggle, price min/max, all dropdowns, and source checkboxes filter the table live
- [ ] Sort dropdown reorders rows (newest / price asc / price desc)
- [ ] Result count reflects filtered count and hot deal count
- [ ] Row click opens listing URL in new tab
- [ ] Clear filters button resets all filters
- [ ] Empty state message shows when no deals match

**Verify:** Load `http://localhost:5000` with a populated `data/deals.json` (run the monitor once, or create a test fixture file manually). Confirm each filter works.

**Steps:**

- [ ] **Step 1: Create `webapp/flask/static/app.js`**

```javascript
/* app.js — Watch Deals frontend */

let allDeals = [];

/* ── Data fetch ── */
async function fetchData() {
  try {
    const [dealsRes, watchesRes] = await Promise.all([
      fetch('/api/deals'),
      fetch('/api/watches'),
    ]);
    allDeals = await dealsRes.json();
    await watchesRes.json(); // reserved for future use
  } catch (e) {
    document.getElementById('result-count').textContent = 'Failed to load deals.';
    return;
  }
  buildSourceCheckboxes();
  populateDropdowns();
  updateLastSync();
  render();
}

/* ── Populate dropdowns from deal data ── */
function populateDropdowns() {
  const unique = (key) =>
    [...new Set(allDeals.map((d) => d[key]).filter(Boolean))].sort();

  populateSelect('brand-select', unique('brand'), 'All brands');
  populateSelect('dial-select', unique('dial').map(capitalize), 'All dials', unique('dial'));
  populateSelect('strap-select', unique('strap').map(capitalize), 'All straps', unique('strap'));

  const sizes = [...new Set(allDeals.map((d) => d.size_mm).filter(Boolean))].sort((a, b) => a - b);
  populateSelect('size-select', sizes.map((s) => `${s}mm`), 'All sizes', sizes.map(String));

  updateModelDropdown();
}

function populateSelect(id, labels, placeholder, values = null) {
  const sel = document.getElementById(id);
  const current = sel.value;
  sel.innerHTML = `<option value="">${placeholder}</option>`;
  labels.forEach((label, i) => {
    const opt = document.createElement('option');
    opt.value = values ? values[i] : label;
    opt.textContent = label;
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}

function updateModelDropdown() {
  const brand = document.getElementById('brand-select').value;
  const subset = brand ? allDeals.filter((d) => d.brand === brand) : allDeals;
  const models = [...new Set(subset.map((d) => d.model).filter(Boolean))].sort();
  const current = document.getElementById('model-select').value;
  populateSelect('model-select', models, 'All models');
  if (current && models.includes(current)) document.getElementById('model-select').value = current;
}

/* ── Source checkboxes (built after data loads) ── */
function buildSourceCheckboxes() {
  const sources = [...new Set(allDeals.map((d) => d.source).filter(Boolean))].sort();
  const group = document.getElementById('source-group');
  group.innerHTML = sources
    .map(
      (s) => `
    <label class="checkbox-row">
      <span class="checkbox-box checked">
        <input type="checkbox" class="source-checkbox" value="${s}" checked>
      </span>
      <span class="checkbox-text">${s}</span>
    </label>`
    )
    .join('');

  group.querySelectorAll('.checkbox-row').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.tagName === 'INPUT') return;
      const cb = row.querySelector('input');
      cb.checked = !cb.checked;
      row.querySelector('.checkbox-box').classList.toggle('checked', cb.checked);
      render();
    });
    row.querySelector('input').addEventListener('change', (e) => {
      row.querySelector('.checkbox-box').classList.toggle('checked', e.target.checked);
      render();
    });
  });
}

/* ── Last sync time ── */
function updateLastSync() {
  if (!allDeals.length) return;
  const latest = allDeals.reduce((a, b) =>
    (a.date_seen || '') > (b.date_seen || '') ? a : b
  );
  document.getElementById('last-sync').textContent = relativeTime(latest.date_seen);
}

/* ── Filters ── */
function getFilters() {
  const checkedSources = [...document.querySelectorAll('.source-checkbox:checked')].map(
    (cb) => cb.value
  );
  return {
    hotOnly: document.getElementById('hot-toggle').getAttribute('aria-pressed') === 'true',
    priceMin: parseFloat(document.getElementById('price-min').value) || null,
    priceMax: parseFloat(document.getElementById('price-max').value) || null,
    brand:  document.getElementById('brand-select').value,
    model:  document.getElementById('model-select').value,
    size:   document.getElementById('size-select').value,
    dial:   document.getElementById('dial-select').value,
    strap:  document.getElementById('strap-select').value,
    dateRange: document.getElementById('date-select').value,
    sources: checkedSources,
    sort: document.getElementById('sort-select').value,
  };
}

function applyFilters(deals, f) {
  return deals.filter((d) => {
    if (f.hotOnly && !d.is_hot) return false;
    if (f.priceMin !== null && (d.price == null || d.price < f.priceMin)) return false;
    if (f.priceMax !== null && (d.price == null || d.price > f.priceMax)) return false;
    if (f.brand && d.brand !== f.brand) return false;
    if (f.model && d.model !== f.model) return false;
    if (f.size  && String(d.size_mm) !== f.size)  return false;
    if (f.dial  && d.dial  !== f.dial)  return false;
    if (f.strap && d.strap !== f.strap) return false;
    if (f.sources.length && !f.sources.includes(d.source)) return false;
    if (f.dateRange) {
      const cutoff = dateCutoff(f.dateRange);
      if (cutoff && (!d.date_seen || new Date(d.date_seen) < cutoff)) return false;
    }
    return true;
  });
}

function sortDeals(deals, sort) {
  const s = [...deals];
  if (sort === 'price-asc')  s.sort((a, b) => (a.price ?? Infinity)  - (b.price ?? Infinity));
  if (sort === 'price-desc') s.sort((a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity));
  if (sort === 'newest')     s.sort((a, b) => (b.date_seen || '').localeCompare(a.date_seen || ''));
  return s;
}

function dateCutoff(range) {
  const now = Date.now();
  if (range === '24h') return new Date(now - 864e5);
  if (range === '7d')  return new Date(now - 6048e5);
  if (range === '30d') return new Date(now - 2592e6);
  return null;
}

/* ── Render ── */
function render() {
  const f = getFilters();
  const filtered = applyFilters(allDeals, f);
  const sorted   = sortDeals(filtered, f.sort);

  const tbody   = document.getElementById('deals-tbody');
  const empty   = document.getElementById('empty-state');
  const countEl = document.getElementById('result-count');

  const hotCount = sorted.filter((d) => d.is_hot).length;
  countEl.innerHTML =
    `<span>${sorted.length}</span> listing${sorted.length !== 1 ? 's' : ''}` +
    (hotCount ? ` · <span>${hotCount}</span> hot deal${hotCount !== 1 ? 's' : ''}` : '');

  if (!sorted.length) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  tbody.innerHTML = sorted
    .map((d) => {
      const rowCls   = d.is_hot ? ' class="hot"' : '';
      const price    = d.price != null ? `$${d.price.toLocaleString()}` : '—';
      const priceCls = d.is_hot ? 'price-hot' : d.price != null ? 'price-ok' : 'price-none';
      const ref      = d.ref_matches && d.ref_matches.length ? d.ref_matches[0] : '—';
      const dialStr  = d.dial
        ? `${capitalize(d.dial)} · ${capitalize(d.strap || '')}`
        : '—';
      const safeUrl  = encodeURI(d.url || '#');
      const safeTitle = (d.title || '').replace(/"/g, '&quot;');
      return `<tr${rowCls} onclick="window.open('${safeUrl}','_blank')">
        <td>${d.is_hot ? '<span class="hot-badge">🔥</span>' : ''}</td>
        <td class="price-cell ${priceCls}">${price}</td>
        <td class="title-cell" title="${safeTitle}">${d.title || '—'}</td>
        <td class="brand-cell">${d.brand || '—'}</td>
        <td class="model-cell">${d.model || '—'}</td>
        <td class="ref-cell">${ref}</td>
        <td class="dial-cell">${dialStr}</td>
        <td>${sourceBadge(d.source)}</td>
        <td class="age-cell">${relativeTime(d.date_seen)}</td>
      </tr>`;
    })
    .join('');
}

/* ── Helpers ── */
function relativeTime(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function sourceBadge(source) {
  if (!source) return '—';
  if (source === 'r/watchexchange') return `<span class="source-badge source-reddit">r/WEX</span>`;
  if (source === 'eBay')            return `<span class="source-badge source-ebay">eBay</span>`;
  if (source === 'Chrono24')        return `<span class="source-badge source-chrono">Chrono24</span>`;
  return `<span class="source-badge">${source}</span>`;
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

/* ── Event listeners ── */
function setupListeners() {
  const hotToggle = document.getElementById('hot-toggle');
  hotToggle.addEventListener('click', () => {
    const pressed = hotToggle.getAttribute('aria-pressed') === 'true';
    hotToggle.setAttribute('aria-pressed', String(!pressed));
    hotToggle.classList.toggle('active', !pressed);
    render();
  });

  ['price-min', 'price-max'].forEach((id) =>
    document.getElementById(id).addEventListener('input', render)
  );

  ['brand-select', 'model-select', 'size-select', 'dial-select',
   'strap-select', 'date-select', 'sort-select'].forEach((id) => {
    document.getElementById(id).addEventListener('change', () => {
      if (id === 'brand-select') updateModelDropdown();
      render();
    });
  });

  document.getElementById('clear-btn').addEventListener('click', () => {
    hotToggle.setAttribute('aria-pressed', 'false');
    hotToggle.classList.remove('active');
    document.getElementById('price-min').value = '';
    document.getElementById('price-max').value = '';
    ['brand-select', 'model-select', 'size-select', 'dial-select',
     'strap-select', 'date-select'].forEach((id) => {
      document.getElementById(id).value = '';
    });
    document.querySelectorAll('.source-checkbox').forEach((cb) => {
      cb.checked = true;
      cb.closest('.checkbox-row').querySelector('.checkbox-box').classList.add('checked');
    });
    render();
  });
}

/* ── Boot ── */
document.addEventListener('DOMContentLoaded', () => {
  setupListeners();
  fetchData();
});
```

- [ ] **Step 2: Create a test fixture to verify the UI with real data**

```bash
cat > /tmp/test-deals.json << 'EOF'
[
  {"id":"reddit:t1","title":"Longines Master Moonphase 40mm L2.673.4.78.6 box papers","price":1750,"url":"https://reddit.com","source":"r/watchexchange","date_seen":"2026-06-19T10:00:00Z","brand":"Longines","model":"Master Collection Chrono Moonphase","size_mm":40,"ref_matches":["L2.673.4.78.6"],"dial":"silver","strap":"bracelet","preferred_signals":["40mm","l2.673"],"is_hot":true},
  {"id":"ebay:t2","title":"Longines Master Chrono Moonphase Steel","price":2200,"url":"https://ebay.com","source":"eBay","date_seen":"2026-06-19T05:00:00Z","brand":"Longines","model":"Master Collection Chrono Moonphase","size_mm":40,"ref_matches":[],"dial":null,"strap":null,"preferred_signals":[],"is_hot":false},
  {"id":"chrono:t3","title":"Longines L2.673.4.61.6 anthracite dial","price":null,"url":"https://chrono24.com","source":"Chrono24","date_seen":"2026-06-18T12:00:00Z","brand":"Longines","model":"Master Collection Chrono Moonphase","size_mm":40,"ref_matches":["L2.673.4.61.6"],"dial":"anthracite","strap":"bracelet","preferred_signals":[],"is_hot":false}
]
EOF
cp /tmp/test-deals.json data/deals.json
```

- [ ] **Step 3: Start Flask and verify all UI behaviors**

```bash
cd webapp/flask && python app.py
```

Open `http://localhost:5000`. Confirm:
1. Three rows render; "3 listings · 1 hot deal" in toolbar
2. First row has 🔥, green price, green left border
3. Brand dropdown shows "Longines"
4. Dial dropdown shows "Anthracite", "Silver"
5. Toggle "Under ceiling only" → only row 1 remains
6. Source checkboxes built: r/watchexchange, eBay, Chrono24 all checked
7. Uncheck eBay → row 2 disappears
8. Sort "Price: low to high" → row 1 first, row 3 (no price) last
9. Click a row → opens URL in new tab
10. Clear filters → all rows back

Stop with Ctrl+C.

- [ ] **Step 4: Clean up test fixture**

```bash
rm data/deals.json
```

- [ ] **Step 5: Commit**

```bash
git add webapp/flask/static/app.js
git commit -m "feat: add Flask frontend JavaScript — filtering, sorting, render"
```

---

## Task 5: Streamlit app

**Goal:** Build the Streamlit alternative that reads `data/deals.json` and provides the same filter dimensions via `st.sidebar`.

**Files:**
- Create: `webapp/streamlit/app.py`

**Acceptance Criteria:**
- [ ] `python -m streamlit run webapp/streamlit/app.py` starts without error
- [ ] `http://localhost:8501` loads with the deals table
- [ ] Sidebar contains: hot-only toggle, price min/max, brand, model, size, dial, strap, source multiselect, date range
- [ ] Filtering any sidebar control re-renders the table
- [ ] Empty state message appears when `data/deals.json` is absent
- [ ] Result count shown above table

**Verify:** `python -m streamlit run webapp/streamlit/app.py` → open `http://localhost:8501`, filter by brand "Longines" — table updates.

**Steps:**

- [ ] **Step 1: Create `webapp/streamlit/app.py`**

```python
# webapp/streamlit/app.py
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Watch Deals", page_icon="⌚", layout="wide")

DEALS_FILE = Path(__file__).parent.parent.parent / "data" / "deals.json"

st.markdown(
    "<h1 style='font-size:1.2rem;letter-spacing:4px;text-transform:uppercase;"
    "color:#c9a84c;font-weight:400'>Watch Deals</h1>",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def load_deals():
    if not DEALS_FILE.exists():
        return []
    try:
        return json.loads(DEALS_FILE.read_text())
    except Exception:
        return []


deals = load_deals()

if not deals:
    st.info("No deals yet — check back after the next monitor run.")
    st.stop()

df = pd.DataFrame(deals)

# ── Sidebar filters ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    hot_only = st.toggle("Hot deals only (≤ ceiling)")

    col1, col2 = st.columns(2)
    price_min = col1.number_input("Min $", min_value=0, value=0, step=100)
    price_max = col2.number_input("Max $", min_value=0, value=10000, step=100)

    brands = ["All"] + sorted(df["brand"].dropna().unique().tolist())
    brand = st.selectbox("Brand", brands)

    if brand != "All":
        model_pool = df[df["brand"] == brand]["model"].dropna().unique().tolist()
    else:
        model_pool = df["model"].dropna().unique().tolist()
    models = ["All"] + sorted(set(model_pool))
    model = st.selectbox("Model", models)

    sizes = ["All"] + [f"{s}mm" for s in sorted(df["size_mm"].dropna().unique())]
    size = st.selectbox("Size", sizes)

    dials = ["All"] + sorted(df["dial"].dropna().unique().tolist())
    dial = st.selectbox("Dial color", dials)

    straps = ["All"] + sorted(df["strap"].dropna().unique().tolist())
    strap = st.selectbox("Strap", straps)

    all_sources = sorted(df["source"].dropna().unique().tolist())
    sources = st.multiselect("Source", all_sources, default=all_sources)

    date_options = {"All time": None, "Last 24h": 1, "Last 7 days": 7, "Last 30 days": 30}
    date_label = st.selectbox("Date seen", list(date_options.keys()))
    date_days = date_options[date_label]

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = df.copy()

if hot_only:
    filtered = filtered[filtered["is_hot"] == True]
if price_min > 0:
    filtered = filtered[filtered["price"].notna() & (filtered["price"] >= price_min)]
if price_max < 10000:
    filtered = filtered[filtered["price"].notna() & (filtered["price"] <= price_max)]
if brand != "All":
    filtered = filtered[filtered["brand"] == brand]
if model != "All":
    filtered = filtered[filtered["model"] == model]
if size != "All":
    size_val = float(size.replace("mm", ""))
    filtered = filtered[filtered["size_mm"] == size_val]
if dial != "All":
    filtered = filtered[filtered["dial"] == dial]
if strap != "All":
    filtered = filtered[filtered["strap"] == strap]
if sources:
    filtered = filtered[filtered["source"].isin(sources)]
if date_days:
    cutoff = datetime.now(timezone.utc) - timedelta(days=date_days)
    filtered = filtered[pd.to_datetime(filtered["date_seen"], utc=True) >= cutoff]

# ── Sort & display ────────────────────────────────────────────────────────────
if "date_seen" in filtered.columns:
    filtered = filtered.sort_values("date_seen", ascending=False)

hot_count = int(filtered["is_hot"].sum()) if "is_hot" in filtered.columns else 0
st.caption(
    f"**{len(filtered)}** listing{'s' if len(filtered) != 1 else ''}"
    + (f" · **{hot_count}** hot deal{'s' if hot_count != 1 else ''}" if hot_count else "")
)

DISPLAY_COLS = ["price", "is_hot", "title", "brand", "model", "ref_matches",
                "dial", "strap", "source", "date_seen", "url"]
show_cols = [c for c in DISPLAY_COLS if c in filtered.columns]

st.dataframe(
    filtered[show_cols],
    use_container_width=True,
    column_config={
        "price":      st.column_config.NumberColumn("Price ($)", format="$%d"),
        "is_hot":     st.column_config.CheckboxColumn("🔥"),
        "title":      st.column_config.TextColumn("Title", width="large"),
        "ref_matches":st.column_config.ListColumn("Ref(s)"),
        "dial":       st.column_config.TextColumn("Dial"),
        "strap":      st.column_config.TextColumn("Strap"),
        "date_seen":  st.column_config.DatetimeColumn("Seen", format="relative"),
        "url":        st.column_config.LinkColumn("Link"),
    },
    hide_index=True,
)
```

- [ ] **Step 2: Copy test fixture and start Streamlit**

```bash
cp /tmp/test-deals.json data/deals.json
python -m streamlit run webapp/streamlit/app.py
```

Open `http://localhost:8501`. Confirm:
1. Table shows 3 rows
2. Sidebar shows all filter controls
3. Toggle "Hot deals only" → 1 row remains
4. Brand dropdown shows "Longines"
5. Uncheck "eBay" in Source → 2 rows remain

Stop with Ctrl+C, then:
```bash
rm data/deals.json
```

- [ ] **Step 3: Commit**

```bash
git add webapp/streamlit/app.py
git commit -m "feat: add Streamlit app with sidebar filters"
```

---

## Task 6: Startup script and requirements update

**Goal:** Write `webapp/start.sh` (one-click launcher for both stacks) and update `requirements.txt` with all new deps.

**Files:**
- Create: `webapp/start.sh`
- Modify: `requirements.txt`

**Acceptance Criteria:**
- [ ] `bash webapp/start.sh` starts Flask on :5000 and Streamlit on :8501
- [ ] Script opens `http://localhost:5000` and `http://localhost:8501` in the default browser
- [ ] Re-running the script kills existing instances first (no port-in-use error)
- [ ] `requirements.txt` lists flask, streamlit, pandas, pytest with stack comments
- [ ] `pip install -r requirements.txt` completes without error

**Verify:** `bash webapp/start.sh` → both browser tabs open within ~3 seconds.

**Steps:**

- [ ] **Step 1: Create `webapp/start.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
FLASK_DIR="$SCRIPT_DIR/flask"
STREAMLIT_APP="$SCRIPT_DIR/streamlit/app.py"
FLASK_LOG="$FLASK_DIR/flask.log"
STREAMLIT_LOG="$SCRIPT_DIR/streamlit/streamlit.log"

echo "==> Installing dependencies..."
pip install flask streamlit pandas --quiet

echo "==> Stopping any existing instances..."
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
lsof -ti:8501 | xargs kill -9 2>/dev/null || true
sleep 0.5

echo "==> Starting Flask on :5000..."
cd "$FLASK_DIR"
FLASK_APP=app.py python -m flask run --port 5000 > "$FLASK_LOG" 2>&1 &
FLASK_PID=$!

echo "==> Starting Streamlit on :8501..."
python -m streamlit run "$STREAMLIT_APP" \
  --server.port 8501 \
  --server.headless true \
  > "$STREAMLIT_LOG" 2>&1 &
STREAMLIT_PID=$!

echo "==> Waiting for servers to start..."
sleep 2

# Verify both are still running
if ! kill -0 "$FLASK_PID" 2>/dev/null; then
  echo "ERROR: Flask failed to start. Check $FLASK_LOG"
  exit 1
fi
if ! kill -0 "$STREAMLIT_PID" 2>/dev/null; then
  echo "ERROR: Streamlit failed to start. Check $STREAMLIT_LOG"
  exit 1
fi

echo "==> Opening browsers..."
open "http://localhost:5000"
open "http://localhost:8501"

echo ""
echo "Both apps are running:"
echo "  Flask      http://localhost:5000   (logs: webapp/flask/flask.log)"
echo "  Streamlit  http://localhost:8501   (logs: webapp/streamlit/streamlit.log)"
echo ""
echo "To stop: kill \$( lsof -ti:5000 ) \$( lsof -ti:8501 )"
```

Make it executable:
```bash
chmod +x webapp/start.sh
```

- [ ] **Step 2: Update `requirements.txt`**

```
# ── Monitor deps ──────────────────────────────────────────────────────────────
requests>=2.31
beautifulsoup4>=4.12

# ── Flask web app (webapp/flask/) ─────────────────────────────────────────────
# Remove this section if dropping Flask: rm -rf webapp/flask
flask>=3.0

# ── Streamlit web app (webapp/streamlit/) ─────────────────────────────────────
# Remove this section if dropping Streamlit: rm -rf webapp/streamlit
streamlit>=1.35
pandas>=2.0

# ── Dev / testing ─────────────────────────────────────────────────────────────
pytest>=8.0
```

- [ ] **Step 3: Install deps and verify**

```bash
pip install -r requirements.txt
```

Expected: all packages install cleanly (or "Requirement already satisfied").

- [ ] **Step 4: Run the startup script**

```bash
cp /tmp/test-deals.json data/deals.json   # use test fixture
bash webapp/start.sh
```

Expected:
- Two browser tabs open automatically
- `http://localhost:5000` shows the Dark Luxury Data Dense table
- `http://localhost:8501` shows the Streamlit table
- Both show the 3 test deals

Stop both:
```bash
kill $(lsof -ti:5000) $(lsof -ti:8501) 2>/dev/null || true
rm data/deals.json
```

- [ ] **Step 5: Commit**

```bash
git add webapp/start.sh requirements.txt
git commit -m "feat: add one-click startup script and update requirements"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|-----------|
| `data/` folder with watches.json, deals.json, monitor_state.json | Task 0 |
| watch_monitor.py reads registry, writes deals.json | Task 1 |
| monitor.yml commits data/deals.json | Task 0 |
| Flask stack on :5000, full delete = rm -rf webapp/flask | Tasks 2–4 |
| Streamlit stack on :8501, full delete = rm -rf webapp/streamlit | Task 5 |
| start.sh starts both, opens 2 tabs | Task 6 |
| requirements.txt with stack comments | Task 6 |
| Dark Luxury Data Dense aesthetic | Tasks 3–4 |
| All 9 filter dimensions | Tasks 4, 5 |
| Tagging: brand, model, size, ref, dial, strap, is_hot, date_seen | Task 1 |
| First-run / empty state | Task 4 (empty-state div), Task 5 (st.stop) |
| Row click opens URL | Task 4 |

All spec requirements have a corresponding task. No gaps found.

**Type consistency check:** `tag_deal` returns a `dict` with keys `brand`, `model`, `size_mm`, `ref_matches`, `dial`, `strap`, `is_hot`, `date_seen`, `preferred_signals` — these exact keys are referenced in `app.js` (`d.brand`, `d.ref_matches`, etc.) and in `webapp/streamlit/app.py` column config. Consistent throughout.

**Placeholder scan:** No TBD, TODO, or vague steps found. Every step has complete code or exact commands.
