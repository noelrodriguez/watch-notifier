# Watch Registry CRUD + Config-Driven Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the monitor fully config-driven from `data/watches.json` and add full CRUD over the watch registry in the local Flask app, with an explicit push-to-activate step.

**Architecture:** Each `watches.json` entry becomes self-contained (`id`, `search_terms`, `relevance_required_all`, `refs`, `size_mm`, `price_ceiling`). The monitor loops over entries, searching and filtering with each entry's own rules; preferred-match signals are derived from `size_mm` (no stored field). Flask gains POST/PUT/DELETE `/api/watches` plus `/api/status` and `/api/push` routes; the frontend gains a Watches view with a form and a push-to-activate banner.

**Tech Stack:** Python 3, Flask, vanilla JS, pytest, git CLI via subprocess.

**User decisions (already made):**
- Each watch entry self-contained; monitor loops over all entries (chose A).
- `relevance_required_all` auto-derived from brand+model, editable in an Advanced section (chose A).
- Local edits + banner "unsaved changes — Push to activate" button does the commit+push (chose C).
- At least one `ref` with dial+strap required to save a watch (chose B).
- Preferred signals reduced to sizes only, derived from `size_mm`.
- CRUD lands in Flask only; Streamlit stays read-only.

---

### Task 1: Schema migration + pure helpers (slugify, size signals)

**Goal:** Add `id` + `relevance_required_all` to the registry and add the pure helper functions the rest of the plan depends on.

**Files:**
- Modify: `data/watches.json`
- Modify: `watch_monitor.py` (add `slugify`, `size_signals`; update `tag_deal` preferred-signals derivation)
- Test: `tests/test_tagging.py`

**Acceptance Criteria:**
- [ ] `slugify("Longines", "Master Collection Chrono Moonphase")` returns `"longines-master-collection-chrono-moonphase"`.
- [ ] `size_signals(40)` returns `["40mm", "40 mm"]`; `size_signals(None)` returns `[]`.
- [ ] `tag_deal` sets `preferred_signals` from the matched entry's `size_mm` (size strings only), not the deleted global list.
- [ ] `data/watches.json` entry has `id` and `relevance_required_all` and still validates as JSON.

**Verify:** `python3 -m pytest tests/test_tagging.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write failing tests for the helpers**

Add to `tests/test_tagging.py`:

```python
from watch_monitor import tag_deal, save_deals, slugify, size_signals


def test_slugify_brand_model():
    assert slugify("Longines", "Master Collection Chrono Moonphase") == \
        "longines-master-collection-chrono-moonphase"


def test_slugify_strips_punctuation_and_collapses():
    assert slugify("Tag Heuer", "Carrera (Calibre 16)") == "tag-heuer-carrera-calibre-16"


def test_size_signals_40():
    assert size_signals(40) == ["40mm", "40 mm"]


def test_size_signals_none():
    assert size_signals(None) == []


def test_tag_preferred_signals_from_size():
    item = {**BASE_ITEM, "title": "Longines Master Moonphase 40mm bracelet"}
    result = tag_deal(item, REGISTRY)
    assert "40mm" in result["preferred_signals"]
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_tagging.py -k "slugify or size_signals or preferred_signals_from_size" -v`
Expected: FAIL with `ImportError` / `cannot import name 'slugify'`

- [ ] **Step 3: Add the helpers to `watch_monitor.py`**

Add near the other helpers (after `preferred_hits`, around line 167):

```python
def slugify(brand, model):
    """Stable id from brand + model: lowercase, non-alphanumerics → single hyphens."""
    raw = f"{brand} {model}".lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", raw)).strip("-")


def size_signals(size_mm):
    """Preferred-match size strings derived from a watch's case size."""
    if not size_mm:
        return []
    return [f"{size_mm}mm", f"{size_mm} mm"]
```

- [ ] **Step 4: Update `tag_deal` to derive preferred_signals from the matched entry's size**

In `tag_deal`, delete the line `item["preferred_signals"] = preferred_hits(item["title"])` (currently line 102) and instead set it after a registry entry matches. Inside the `for entry in registry:` block, after `item["size_mm"] = entry.get("size_mm")`, add:

```python
            title_l = item["title"].lower()
            item["preferred_signals"] = [
                s for s in size_signals(entry.get("size_mm")) if s in title_l
            ]
```

Also initialize `item["preferred_signals"] = []` in the default block (where the other defaults like `item["ref_matches"] = []` are set), so non-matching items still have the key.

- [ ] **Step 5: Run tests, verify pass**

Run: `python3 -m pytest tests/test_tagging.py -v`
Expected: PASS (all, including pre-existing)

- [ ] **Step 6: Migrate `data/watches.json`**

Add `id` and `relevance_required_all` to the existing entry. Set `relevance_required_all` to the value that preserves today's behavior (the old global), NOT the stricter auto-derived form:

```json
[
  {
    "id": "longines-master-collection-chrono-moonphase",
    "brand": "Longines",
    "model": "Master Collection Chrono Moonphase",
    "size_mm": 40,
    "search_terms": [
      "longines master moonphase",
      "longines master chronograph moonphase"
    ],
    "relevance_required_all": [["longines", "master", "moon"]],
    "refs": [
      { "ref": "L2.673.4.78.6", "dial": "silver",     "strap": "bracelet" },
      { "ref": "L2.673.4.78.3", "dial": "silver",     "strap": "leather"  },
      { "ref": "L2.673.4.61.6", "dial": "anthracite", "strap": "bracelet" },
      { "ref": "L2.673.4.71.2", "dial": "ivory",      "strap": "leather"  },
      { "ref": "L2.673.4.92.0", "dial": "blue",       "strap": "bracelet" }
    ],
    "price_ceiling": 2000,
    "notes": "40mm only — 42mm is L2.773 family, not the target"
  }
]
```

- [ ] **Step 7: Commit**

```bash
git add watch_monitor.py tests/test_tagging.py data/watches.json
git commit -m "feat: add slugify/size_signals helpers and migrate watches.json schema"
```

---

### Task 2: Config-driven search, relevance, and push

**Goal:** Drive searching, relevance filtering, and the hot flag entirely from the registry; delete the global config constants.

**Files:**
- Modify: `watch_monitor.py` (`is_relevant`, `search_reddit`, `search_ebay`, `push_ntfy`, `main`; delete globals)
- Test: `tests/test_tagging.py`

**Acceptance Criteria:**
- [ ] `is_relevant(title, groups)` takes relevance groups as an argument (no global).
- [ ] `search_reddit(registry)` / `search_ebay(registry)` loop over each entry's `search_terms` and filter by that entry's `relevance_required_all`.
- [ ] `push_ntfy` uses `item["is_hot"]` and `item["preferred_signals"]` (no global ceiling / `preferred_hits`).
- [ ] Globals `SEARCH_TERMS`, `RELEVANCE_REQUIRED_ALL`, `PREFERRED_SIGNALS`, `PRICE_ALERT_CEILING`, and the `preferred_hits` function are removed.
- [ ] `main()` loads the registry before searching and passes it to the source functions.

**Verify:** `python3 -m pytest tests/test_tagging.py -v` → all pass; `python3 -c "import watch_monitor"` → no error

**Steps:**

- [ ] **Step 1: Write failing tests for relevance-by-argument**

Add to `tests/test_tagging.py`:

```python
from watch_monitor import is_relevant


def test_is_relevant_matches_group():
    groups = [["longines", "master", "moon"]]
    assert is_relevant("Longines Master Moonphase 40mm", groups) is True


def test_is_relevant_rejects_partial():
    groups = [["longines", "master", "moon"]]
    assert is_relevant("Longines Master Collection (no complication)", groups) is False


def test_is_relevant_empty_groups_is_false():
    assert is_relevant("anything at all", []) is False
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_tagging.py -k is_relevant -v`
Expected: FAIL — `is_relevant() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Rewrite `is_relevant` to take groups**

Replace the existing `is_relevant` (lines 156-161):

```python
def is_relevant(title, groups):
    t = title.lower()
    for group in groups:
        if group and all(tok in t for tok in group):
            return True
    return False
```

- [ ] **Step 4: Delete the global config constants and `preferred_hits`**

Remove lines 32-46 (`SEARCH_TERMS`, `PRICE_ALERT_CEILING`, `RELEVANCE_REQUIRED_ALL`, `PREFERRED_SIGNALS` and their comments) and the `preferred_hits` function (lines 164-166). Keep `NTFY_TOPIC`, `NTFY_SERVER`, the Telegram vars, and the file-path constants.

- [ ] **Step 5: Make `search_reddit` / `search_ebay` registry-driven**

Replace `search_reddit` signature and loop:

```python
def search_reddit(registry):
    """r/watchexchange via the public JSON endpoint. Reliable, no auth."""
    out = []
    for entry in registry:
        groups = entry.get("relevance_required_all", [])
        for term in entry.get("search_terms", []):
            url = ("https://www.reddit.com/r/Watchexchange/search.json"
                   f"?q={requests.utils.quote(term)}&restrict_sr=on&sort=new&limit=50")
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                for child in r.json().get("data", {}).get("children", []):
                    d = child.get("data", {})
                    title = html.unescape(d.get("title", ""))
                    if not is_relevant(title, groups):
                        continue
                    low = title.lower()
                    if low.startswith("[wtb") or "sold" in low:
                        continue
                    out.append({
                        "id": f"reddit:{d.get('id')}",
                        "title": title,
                        "price": parse_price(title),
                        "url": "https://www.reddit.com" + d.get("permalink", ""),
                        "source": "r/watchexchange",
                    })
            except Exception as e:
                log(f"WARN: Reddit search failed for '{term}': {e}")
            time.sleep(1)
    return out
```

Replace `search_ebay` the same way:

```python
def search_ebay(registry):
    """eBay newly-listed search results (HTML scrape — usually works w/o JS)."""
    out = []
    for entry in registry:
        groups = entry.get("relevance_required_all", [])
        for term in entry.get("search_terms", []):
            url = ("https://www.ebay.com/sch/i.html"
                   f"?_nkw={requests.utils.quote(term)}&_sop=10&LH_BIN=1")
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                for li in soup.select("li.s-item"):
                    a = li.select_one("a.s-item__link")
                    title_el = li.select_one(".s-item__title")
                    price_el = li.select_one(".s-item__price")
                    if not a or not title_el:
                        continue
                    title = title_el.get_text(" ", strip=True)
                    if not is_relevant(title, groups) or "shop on ebay" in title.lower():
                        continue
                    link = a.get("href", "").split("?")[0]
                    m = re.search(r"/itm/(\d+)", link)
                    item_id = m.group(1) if m else link
                    out.append({
                        "id": f"ebay:{item_id}",
                        "title": title,
                        "price": parse_price(price_el.get_text() if price_el else ""),
                        "url": link,
                        "source": "eBay",
                    })
            except Exception as e:
                log(f"WARN: eBay search failed for '{term}': {e}")
            time.sleep(1)
    return out
```

`search_chrono24()` is left unchanged (best-effort, its own ref pages).

- [ ] **Step 6: Update `push_ntfy` to use the tagged fields**

Replace the top of `push_ntfy` (the `prefs` / `under_ceiling` lines, currently 276-278):

```python
def push_ntfy(item):
    price = f"${item['price']}" if item.get("price") else "price?"
    prefs = item.get("preferred_signals", [])
    under_ceiling = bool(item.get("is_hot"))
```

The rest of `push_ntfy` is unchanged.

- [ ] **Step 7: Update `main()` to load the registry before searching**

Replace the search section in `main()` (currently lines 347-352 region). Load registry up front and pass it in:

```python
    seen = load_state()
    first_run = not STATE_FILE.exists()
    registry = load_registry()

    found = []
    found.extend(search_reddit(registry))
    found.extend(search_ebay(registry))
    found.extend(search_chrono24())
```

Delete the later `registry = load_registry()` line (currently line 373) so it is loaded only once.

- [ ] **Step 8: Give the `--test` sample the tagged fields**

In `run_test_push`, add to the `sample` dict so `push_ntfy` renders it as hot:

```python
        "source": "self-test",
        "is_hot": True,
        "preferred_signals": ["40mm"],
```

- [ ] **Step 9: Run tests + import check**

Run: `python3 -m pytest tests/test_tagging.py -v`
Expected: PASS
Run: `python3 -c "import watch_monitor"`
Expected: no output, exit 0

- [ ] **Step 10: Commit**

```bash
git add watch_monitor.py tests/test_tagging.py
git commit -m "feat: drive monitor search/relevance/hot-flag from registry; drop globals"
```

---

### Task 3: Flask CRUD API for the watch registry

**Goal:** Add validated create/update/delete routes for `watches.json` with atomic writes.

**Files:**
- Modify: `webapp/flask/app.py`
- Test: `webapp/flask/tests/test_app.py`

**Acceptance Criteria:**
- [ ] `POST /api/watches` with valid body → `201` and a generated slug `id`.
- [ ] `POST` missing `brand`/`model`/`size_mm` → `400` with `{"error": ...}`.
- [ ] `POST` with no ref having both `dial` and `strap` → `400`.
- [ ] `POST` whose generated `id` already exists → `409`.
- [ ] `PUT /api/watches/<id>` updates the entry; unknown id → `404`.
- [ ] `DELETE /api/watches/<id>` removes the entry; unknown id → `404`.
- [ ] `relevance_required_all` defaults to one lowercased brand+model word group when omitted.
- [ ] Writes are atomic (temp file + `os.replace`).

**Verify:** `python3 -m pytest webapp/flask/tests/test_app.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write failing tests**

Add to `webapp/flask/tests/test_app.py`:

```python
VALID_WATCH = {
    "brand": "Rolex",
    "model": "Submariner Date",
    "size_mm": 41,
    "search_terms": ["rolex submariner date"],
    "refs": [{"ref": "126610LN", "dial": "black", "strap": "bracelet"}],
    "price_ceiling": 15000,
}


def test_create_watch_valid(client, tmp_path):
    (tmp_path / "watches.json").write_text("[]")
    with patch("app.DATA_DIR", tmp_path):
        r = client.post("/api/watches", json=VALID_WATCH)
    assert r.status_code == 201
    body = json.loads(r.data)
    assert body["id"] == "rolex-submariner-date"
    assert body["relevance_required_all"] == [["rolex", "submariner", "date"]]


def test_create_watch_missing_field(client, tmp_path):
    (tmp_path / "watches.json").write_text("[]")
    bad = {k: v for k, v in VALID_WATCH.items() if k != "size_mm"}
    with patch("app.DATA_DIR", tmp_path):
        r = client.post("/api/watches", json=bad)
    assert r.status_code == 400
    assert "error" in json.loads(r.data)


def test_create_watch_no_valid_ref(client, tmp_path):
    (tmp_path / "watches.json").write_text("[]")
    bad = {**VALID_WATCH, "refs": [{"ref": "X", "dial": "", "strap": "bracelet"}]}
    with patch("app.DATA_DIR", tmp_path):
        r = client.post("/api/watches", json=bad)
    assert r.status_code == 400


def test_create_watch_duplicate_id(client, tmp_path):
    existing = [{"id": "rolex-submariner-date", "brand": "Rolex",
                 "model": "Submariner Date"}]
    (tmp_path / "watches.json").write_text(json.dumps(existing))
    with patch("app.DATA_DIR", tmp_path):
        r = client.post("/api/watches", json=VALID_WATCH)
    assert r.status_code == 409


def test_update_watch(client, tmp_path):
    existing = [{"id": "rolex-submariner-date", "brand": "Rolex",
                 "model": "Submariner Date", "size_mm": 41,
                 "refs": [{"ref": "126610LN", "dial": "black", "strap": "bracelet"}]}]
    (tmp_path / "watches.json").write_text(json.dumps(existing))
    with patch("app.DATA_DIR", tmp_path):
        r = client.put("/api/watches/rolex-submariner-date",
                       json={**VALID_WATCH, "price_ceiling": 12000})
    assert r.status_code == 200
    saved = json.loads((tmp_path / "watches.json").read_text())
    assert saved[0]["price_ceiling"] == 12000


def test_update_watch_unknown_id(client, tmp_path):
    (tmp_path / "watches.json").write_text("[]")
    with patch("app.DATA_DIR", tmp_path):
        r = client.put("/api/watches/nope", json=VALID_WATCH)
    assert r.status_code == 404


def test_delete_watch(client, tmp_path):
    existing = [{"id": "rolex-submariner-date", "brand": "Rolex"}]
    (tmp_path / "watches.json").write_text(json.dumps(existing))
    with patch("app.DATA_DIR", tmp_path):
        r = client.delete("/api/watches/rolex-submariner-date")
    assert r.status_code == 200
    assert json.loads((tmp_path / "watches.json").read_text()) == []


def test_delete_watch_unknown_id(client, tmp_path):
    (tmp_path / "watches.json").write_text("[]")
    with patch("app.DATA_DIR", tmp_path):
        r = client.delete("/api/watches/nope")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest webapp/flask/tests/test_app.py -k "create_watch or update_watch or delete_watch" -v`
Expected: FAIL — routes return 405/404 (not implemented)

- [ ] **Step 3: Implement helpers + routes in `webapp/flask/app.py`**

Add imports at the top (after `import json`):

```python
import os
import re
import tempfile
from flask import request
```

Add helpers and routes (after the existing `watches()` route):

```python
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
    for field in ("brand", "model", "size_mm"):
        if not payload.get(field):
            return None, f"{field} is required"
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest webapp/flask/tests/test_app.py -v`
Expected: PASS (all, including pre-existing GET tests)

- [ ] **Step 5: Commit**

```bash
git add webapp/flask/app.py webapp/flask/tests/test_app.py
git commit -m "feat: add validated CRUD routes for the watch registry"
```

---

### Task 4: Flask git status + push-to-activate routes

**Goal:** Expose whether `watches.json` has unsaved/unpushed changes and a route to commit+push it.

**Files:**
- Modify: `webapp/flask/app.py`
- Test: `webapp/flask/tests/test_app.py`

**Acceptance Criteria:**
- [ ] `GET /api/status` returns `{"dirty": bool, "ahead": int, "needs_push": bool}`.
- [ ] `POST /api/push` runs `git add`/`commit`/`push` and returns `{"ok": true}` on success.
- [ ] `POST /api/push` returns `{"ok": false, "error": ...}` with `500` when a git command fails.
- [ ] Git failures in `/api/status` degrade safely (no 500; returns defaults).

**Verify:** `python3 -m pytest webapp/flask/tests/test_app.py -k "status or push" -v` → all pass

**Steps:**

- [ ] **Step 1: Write failing tests (git mocked)**

Add to `webapp/flask/tests/test_app.py`:

```python
from unittest.mock import MagicMock


def test_status_clean(client):
    fake = MagicMock(returncode=0, stdout="", stderr="")
    with patch("app.subprocess.run", return_value=fake):
        r = client.get("/api/status")
    assert r.status_code == 200
    body = json.loads(r.data)
    assert body["needs_push"] is False


def test_status_dirty(client):
    def fake_run(cmd, **kw):
        if "status" in cmd:
            return MagicMock(returncode=0, stdout=" M data/watches.json\n", stderr="")
        return MagicMock(returncode=0, stdout="0\n", stderr="")
    with patch("app.subprocess.run", side_effect=fake_run):
        r = client.get("/api/status")
    body = json.loads(r.data)
    assert body["dirty"] is True
    assert body["needs_push"] is True


def test_push_success(client):
    fake = MagicMock(returncode=0, stdout="", stderr="")
    with patch("app.subprocess.run", return_value=fake):
        r = client.post("/api/push")
    assert r.status_code == 200
    assert json.loads(r.data)["ok"] is True


def test_push_failure(client):
    fake = MagicMock(returncode=1, stdout="", stderr="rejected: auth failed")
    with patch("app.subprocess.run", return_value=fake):
        r = client.post("/api/push")
    assert r.status_code == 500
    body = json.loads(r.data)
    assert body["ok"] is False
    assert "auth failed" in body["error"]
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest webapp/flask/tests/test_app.py -k "status or push" -v`
Expected: FAIL — routes 404 / `app.subprocess` missing

- [ ] **Step 3: Implement the routes**

Add `import subprocess` to the top of `webapp/flask/app.py`, define the repo root near `DATA_DIR`:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
```

Add the routes:

```python
def _git(*args):
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          capture_output=True, text=True)


@app.route("/api/status")
def status():
    try:
        st = _git("status", "--porcelain", "data/watches.json")
        dirty = bool(st.stdout.strip())
        ahead_res = _git("rev-list", "--count", "@{u}..HEAD")
        ahead = int(ahead_res.stdout.strip()) if ahead_res.returncode == 0 else 0
    except Exception:
        return jsonify({"dirty": False, "ahead": 0, "needs_push": False})
    return jsonify({"dirty": dirty, "ahead": ahead,
                    "needs_push": dirty or ahead > 0})


@app.route("/api/push", methods=["POST"])
def push():
    add = _git("add", "data/watches.json")
    if add.returncode != 0:
        return jsonify({"ok": False, "error": add.stderr.strip()}), 500
    # Commit only if there is something staged; an empty commit would error.
    diff = _git("diff", "--cached", "--quiet", "data/watches.json")
    if diff.returncode == 1:  # 1 => staged changes present
        commit = _git("commit", "-m", "chore: update watch registry")
        if commit.returncode != 0:
            return jsonify({"ok": False, "error": commit.stderr.strip()}), 500
    push_res = _git("push")
    if push_res.returncode != 0:
        return jsonify({"ok": False, "error": push_res.stderr.strip()}), 500
    return jsonify({"ok": True})
```

Note: in `test_push_failure` the first `_git("add")` returns the failing mock (returncode 1), so the route returns 500 with the stderr — matching the assertion.

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest webapp/flask/tests/test_app.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add webapp/flask/app.py webapp/flask/tests/test_app.py
git commit -m "feat: add git status + push-to-activate routes"
```

---

### Task 5: Watches view — nav, list, form, push banner

**Goal:** Add a browser UI to view/add/edit/delete watches and push changes, in the existing Flask single-page app.

**Files:**
- Modify: `webapp/flask/templates/index.html`
- Modify: `webapp/flask/static/app.js`
- Modify: `webapp/flask/static/style.css`

**Acceptance Criteria:**
- [ ] A nav toggle switches between the existing Deals view and a new Watches view.
- [ ] Watches view lists each watch (brand · model · size, ref count, price ceiling) with Edit and Delete (Delete confirms first).
- [ ] "＋ Add Watch" opens a form with Brand, Model, Size, Price ceiling, Notes; a required Refs section (≥1 row of Ref/Dial/Strap, with "＋ Add ref"); and a collapsed Advanced section with Search terms + Relevance groups (pre-filled from brand+model).
- [ ] Saving calls POST/PUT; validation errors from the API render inline.
- [ ] After any change, a gold banner appears ("⚠ N unsaved changes — not yet monitoring") with a "Push to activate" button calling `POST /api/push`; banner clears on success and shows git errors on failure.
- [ ] Banner reflects `GET /api/status` on load.

**Verify:** `python3 webapp/flask/app.py` then open `http://127.0.0.1:5000` → add a test watch, confirm it appears, banner shows; `python3 -m pytest webapp/flask/tests/test_app.py -v` still passes (index served).

**Steps:**

- [ ] **Step 1: Add nav + Watches section + banner to `index.html`**

Read the current `index.html` first to match its structure. Wrap the existing deals content in a `<section id="deals-view">` and add a sibling view. Add a nav in the header:

```html
<nav class="view-nav">
  <button id="nav-deals" class="nav-btn active" data-view="deals-view">Deals</button>
  <button id="nav-watches" class="nav-btn" data-view="watches-view">Watches</button>
</nav>
```

Add the watches view markup after the deals view:

```html
<section id="watches-view" style="display:none">
  <div id="push-banner" class="push-banner" style="display:none">
    <span id="push-banner-text"></span>
    <button id="push-btn">Push to activate</button>
  </div>
  <div class="watches-header">
    <h2>Tracked Watches (<span id="watch-count">0</span>)</h2>
    <button id="add-watch-btn">＋ Add Watch</button>
  </div>
  <div id="watches-list"></div>
</section>

<div id="watch-modal" class="modal" style="display:none">
  <div class="modal-card">
    <h3 id="watch-modal-title">Add Watch</h3>
    <div id="form-error" class="form-error" style="display:none"></div>
    <input type="hidden" id="f-id">
    <label>Brand <input id="f-brand"></label>
    <label>Model <input id="f-model"></label>
    <label>Size (mm) <input id="f-size" type="number"></label>
    <label>Price ceiling <input id="f-ceiling" type="number"></label>
    <label>Notes <input id="f-notes"></label>
    <div class="refs-section">
      <div class="label">Refs (at least one)</div>
      <div id="refs-rows"></div>
      <button id="add-ref-btn" type="button">＋ Add ref</button>
    </div>
    <details class="advanced">
      <summary>Advanced</summary>
      <label>Search terms (one per line)
        <textarea id="f-search-terms"></textarea></label>
      <label>Relevance groups (comma-separated words, one group per line)
        <textarea id="f-relevance"></textarea></label>
    </details>
    <div class="modal-actions">
      <button id="watch-cancel" type="button">Cancel</button>
      <button id="watch-save" type="button">Save</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Add the Watches controller to `app.js`**

Append to `app.js` (keeps the existing deals code untouched). Adds nav switching, list render, form, and push banner:

```javascript
/* ── Watches view ── */
let allWatches = [];

async function fetchWatches() {
  const res = await fetch('/api/watches');
  allWatches = await res.json();
  renderWatches();
  refreshStatus();
}

function renderWatches() {
  document.getElementById('watch-count').textContent = allWatches.length;
  document.getElementById('watches-list').innerHTML = allWatches.map((w) => `
    <div class="watch-row">
      <div class="watch-meta">
        <span class="watch-name">${escapeHtml(w.brand)} · ${escapeHtml(w.model)}</span>
        <span class="watch-sub">${w.size_mm ? w.size_mm + 'mm' : '—'} ·
          ${(w.refs || []).length} ref(s) ·
          ${w.price_ceiling ? '$' + w.price_ceiling : 'no ceiling'}</span>
      </div>
      <div class="watch-actions">
        <button data-edit="${escapeHtml(w.id)}">Edit</button>
        <button data-del="${escapeHtml(w.id)}">Delete</button>
      </div>
    </div>`).join('') || '<p class="subtitle">No watches yet.</p>';

  document.querySelectorAll('[data-edit]').forEach((b) =>
    b.addEventListener('click', () => openWatchForm(b.dataset.edit)));
  document.querySelectorAll('[data-del]').forEach((b) =>
    b.addEventListener('click', () => deleteWatch(b.dataset.del)));
}

function refRowHtml(ref = {}) {
  return `<div class="ref-row">
    <input class="ref-ref" placeholder="Ref" value="${escapeHtml(ref.ref || '')}">
    <input class="ref-dial" placeholder="Dial" value="${escapeHtml(ref.dial || '')}">
    <input class="ref-strap" placeholder="Strap" value="${escapeHtml(ref.strap || '')}">
  </div>`;
}

function openWatchForm(id) {
  const w = allWatches.find((x) => x.id === id);
  document.getElementById('watch-modal-title').textContent = w ? 'Edit Watch' : 'Add Watch';
  document.getElementById('form-error').style.display = 'none';
  document.getElementById('f-id').value = w ? w.id : '';
  document.getElementById('f-brand').value = w ? w.brand : '';
  document.getElementById('f-model').value = w ? w.model : '';
  document.getElementById('f-size').value = w ? (w.size_mm || '') : '';
  document.getElementById('f-ceiling').value = w ? (w.price_ceiling || '') : '';
  document.getElementById('f-notes').value = w ? (w.notes || '') : '';
  document.getElementById('f-search-terms').value =
    w && w.search_terms ? w.search_terms.join('\n') : '';
  document.getElementById('f-relevance').value =
    w && w.relevance_required_all
      ? w.relevance_required_all.map((g) => g.join(', ')).join('\n') : '';
  const rows = (w && w.refs && w.refs.length) ? w.refs : [{}];
  document.getElementById('refs-rows').innerHTML = rows.map(refRowHtml).join('');
  document.getElementById('watch-modal').style.display = 'flex';
}

function collectForm() {
  const refs = [...document.querySelectorAll('.ref-row')].map((r) => ({
    ref: r.querySelector('.ref-ref').value.trim(),
    dial: r.querySelector('.ref-dial').value.trim(),
    strap: r.querySelector('.ref-strap').value.trim(),
  })).filter((r) => r.ref || r.dial || r.strap);
  const terms = document.getElementById('f-search-terms').value
    .split('\n').map((s) => s.trim()).filter(Boolean);
  const rel = document.getElementById('f-relevance').value
    .split('\n').map((line) => line.split(',').map((s) => s.trim().toLowerCase())
      .filter(Boolean)).filter((g) => g.length);
  const size = parseInt(document.getElementById('f-size').value, 10);
  const ceiling = parseInt(document.getElementById('f-ceiling').value, 10);
  return {
    brand: document.getElementById('f-brand').value.trim(),
    model: document.getElementById('f-model').value.trim(),
    size_mm: Number.isNaN(size) ? null : size,
    price_ceiling: Number.isNaN(ceiling) ? null : ceiling,
    notes: document.getElementById('f-notes').value.trim(),
    refs,
    search_terms: terms,
    relevance_required_all: rel,
  };
}

async function saveWatch() {
  const id = document.getElementById('f-id').value;
  const payload = collectForm();
  const res = await fetch(id ? `/api/watches/${id}` : '/api/watches', {
    method: id ? 'PUT' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    const el = document.getElementById('form-error');
    el.textContent = err.error || 'Save failed';
    el.style.display = 'block';
    return;
  }
  document.getElementById('watch-modal').style.display = 'none';
  fetchWatches();
}

async function deleteWatch(id) {
  if (!confirm('Delete this watch?')) return;
  await fetch(`/api/watches/${id}`, { method: 'DELETE' });
  fetchWatches();
}

/* ── Push banner ── */
async function refreshStatus() {
  let s;
  try { s = await (await fetch('/api/status')).json(); } catch { return; }
  const banner = document.getElementById('push-banner');
  if (s.needs_push) {
    document.getElementById('push-banner-text').textContent =
      '⚠ Unsaved changes — not yet monitoring.';
    banner.style.display = 'flex';
  } else {
    banner.style.display = 'none';
  }
}

async function pushChanges() {
  const btn = document.getElementById('push-btn');
  btn.disabled = true;
  const res = await fetch('/api/push', { method: 'POST' });
  const body = await res.json();
  btn.disabled = false;
  if (body.ok) {
    refreshStatus();
  } else {
    document.getElementById('push-banner-text').textContent =
      'Push failed: ' + (body.error || 'unknown error');
  }
}

function setupWatchesListeners() {
  document.querySelectorAll('.nav-btn').forEach((b) =>
    b.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      document.getElementById('deals-view').style.display =
        b.dataset.view === 'deals-view' ? 'block' : 'none';
      document.getElementById('watches-view').style.display =
        b.dataset.view === 'watches-view' ? 'block' : 'none';
      if (b.dataset.view === 'watches-view') fetchWatches();
    }));
  document.getElementById('add-watch-btn').addEventListener('click', () => openWatchForm(null));
  document.getElementById('add-ref-btn').addEventListener('click', () => {
    document.getElementById('refs-rows').insertAdjacentHTML('beforeend', refRowHtml());
  });
  document.getElementById('watch-cancel').addEventListener('click', () => {
    document.getElementById('watch-modal').style.display = 'none';
  });
  document.getElementById('watch-save').addEventListener('click', saveWatch);
  document.getElementById('push-btn').addEventListener('click', pushChanges);
}
```

Then add `setupWatchesListeners();` inside the existing `DOMContentLoaded` handler (next to `setupListeners();`).

- [ ] **Step 3: Add styles to `style.css`**

Append (match the existing dark-luxury palette — near-black bg, gold `#c9a84c`):

```css
.view-nav { display: flex; gap: 8px; margin: 12px 0; }
.nav-btn { background: transparent; color: #888; border: 1px solid #222;
  padding: 6px 14px; cursor: pointer; border-radius: 4px; }
.nav-btn.active { color: #c9a84c; border-color: #c9a84c; }
.watches-header { display: flex; justify-content: space-between; align-items: center; }
#add-watch-btn { background: #c9a84c; color: #07070d; border: none;
  padding: 8px 14px; border-radius: 4px; cursor: pointer; font-weight: 600; }
.watch-row { display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border-bottom: 1px solid #161620; }
.watch-name { color: #c9a84c; }
.watch-sub { color: #777; font-size: 0.85em; margin-left: 8px; }
.watch-actions button { background: transparent; color: #aaa; border: 1px solid #333;
  margin-left: 6px; padding: 4px 10px; border-radius: 4px; cursor: pointer; }
.push-banner { display: flex; justify-content: space-between; align-items: center;
  background: #2a2410; border: 1px solid #c9a84c; color: #e7d6a0;
  padding: 10px 14px; border-radius: 4px; margin-bottom: 12px; }
#push-btn { background: #c9a84c; color: #07070d; border: none; padding: 6px 12px;
  border-radius: 4px; cursor: pointer; font-weight: 600; }
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  align-items: center; justify-content: center; z-index: 50; }
.modal-card { background: #0d0d16; border: 1px solid #222; padding: 22px;
  border-radius: 8px; width: 460px; max-height: 86vh; overflow-y: auto; }
.modal-card label { display: block; margin: 8px 0; color: #aaa; }
.modal-card input, .modal-card textarea { width: 100%; background: #07070d;
  border: 1px solid #333; color: #e7e7ea; padding: 6px; border-radius: 4px; }
.ref-row { display: flex; gap: 6px; margin-bottom: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
#watch-save { background: #c9a84c; color: #07070d; border: none; padding: 8px 16px;
  border-radius: 4px; cursor: pointer; font-weight: 600; }
.form-error { background: #3a1414; border: 1px solid #a33; color: #f1b0b0;
  padding: 8px; border-radius: 4px; margin-bottom: 10px; }
.advanced summary { cursor: pointer; color: #c9a84c; margin: 10px 0; }
```

- [ ] **Step 4: Manual verification**

Run: `python3 webapp/flask/app.py`
Open `http://127.0.0.1:5000`, click **Watches**, add a watch with one ref, save → it appears in the list and the push banner shows. Edit it, delete it. Then stop the server (Ctrl-C).

Run: `python3 -m pytest webapp/flask/tests/test_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/flask/templates/index.html webapp/flask/static/app.js webapp/flask/static/style.css
git commit -m "feat: add Watches CRUD view with push-to-activate banner"
```

---

## Self-Review

- **Spec coverage:** Section 1 (data model + monitor) → Tasks 1-2. Section 2 (CRUD API) → Task 3. Section 2 status/push routes → Task 4. Section 3 (UI) → Task 5. Section 4 (testing) → tests embedded in each task; migration check covered by pre-existing `test_tagging.py` tests staying green after Task 1-2. ✓
- **Placeholders:** none — all steps carry concrete code/commands. ✓
- **Type consistency:** `slugify`/`_slugify` use identical regex; `is_relevant(title, groups)` signature consistent across monitor + tests; API entry shape matches `tag_deal`'s expected keys (`search_terms`, `relevance_required_all`, `refs`, `size_mm`, `price_ceiling`). ✓
