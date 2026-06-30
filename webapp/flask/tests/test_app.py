# webapp/flask/tests/test_app.py
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

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


def test_index_has_sortable_headers_not_dropdown(client):
    """Sorting is via clickable column headers, not the old sort dropdown."""
    r = client.get("/")
    html = r.data
    assert b'id="sort-select"' not in html          # dropdown removed
    assert b'data-sort="price"' in html             # headers are sortable
    assert b'data-sort="date_seen"' in html
    assert html.count(b'class="sortable') == 8     # all 8 data columns


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


def test_api_deals_returns_empty_on_malformed_json(client, tmp_path):
    (tmp_path / "deals.json").write_text("not-json")
    with patch("app.DATA_DIR", tmp_path):
        r = client.get("/api/deals")
    assert r.status_code == 200
    assert json.loads(r.data) == []


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
    bad = {**VALID_WATCH, "refs": [{"ref": "", "dial": "black", "strap": "bracelet"}]}
    with patch("app.DATA_DIR", tmp_path):
        r = client.post("/api/watches", json=bad)
    assert r.status_code == 400


def test_create_watch_ref_without_dial_strap(client, tmp_path):
    (tmp_path / "watches.json").write_text("[]")
    ok = {**VALID_WATCH, "refs": [{"ref": "126610LN"}]}
    with patch("app.DATA_DIR", tmp_path):
        r = client.post("/api/watches", json=ok)
    assert r.status_code == 201
    assert json.loads(r.data)["refs"] == [{"ref": "126610LN"}]


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


def test_create_watch_size_zero_rejected_is_none_only(client, tmp_path):
    (tmp_path / "watches.json").write_text("[]")
    # size_mm explicitly None → rejected; but a real positive size is accepted.
    bad = {**VALID_WATCH, "size_mm": None}
    with patch("app.DATA_DIR", tmp_path):
        r = client.post("/api/watches", json=bad)
    assert r.status_code == 400


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
    def fake_run(cmd, **kw):
        if "push" in cmd:
            return MagicMock(returncode=1, stdout="", stderr="rejected: auth failed")
        if "diff" in cmd:
            return MagicMock(returncode=1, stdout="", stderr="")  # staged changes present
        return MagicMock(returncode=0, stdout="", stderr="")
    with patch("app.subprocess.run", side_effect=fake_run):
        r = client.post("/api/push")
    assert r.status_code == 500
    body = json.loads(r.data)
    assert body["ok"] is False
    assert "auth failed" in body["error"]


def test_push_add_failure(client):
    def fake_run(cmd, **kw):
        if "add" in cmd:
            return MagicMock(returncode=1, stdout="", stderr="add failed")
        return MagicMock(returncode=0, stdout="", stderr="")
    with patch("app.subprocess.run", side_effect=fake_run):
        r = client.post("/api/push")
    assert r.status_code == 500
    assert "add failed" in json.loads(r.data)["error"]


def test_push_timeout(client):
    import subprocess as sp
    with patch("app.subprocess.run", side_effect=sp.TimeoutExpired(cmd="git", timeout=30)):
        r = client.post("/api/push")
    assert r.status_code == 500
    assert "timed out" in json.loads(r.data)["error"]


# ── Delete deal ──

def test_delete_deal(client, tmp_path):
    deals = [{"id": "reddit:1uex7dl", "title": "Rolex"}, {"id": "chrono24:test3", "title": "Omega"}]
    (tmp_path / "deals.json").write_text(json.dumps(deals))
    with patch("app.DATA_DIR", tmp_path):
        r = client.delete("/api/deals/reddit%3A1uex7dl")
    assert r.status_code == 200
    assert json.loads(r.data) == {"ok": True}
    saved = json.loads((tmp_path / "deals.json").read_text())
    assert len(saved) == 1
    assert saved[0]["id"] == "chrono24:test3"


def test_delete_deal_not_found(client, tmp_path):
    deals = [{"id": "reddit:1uex7dl", "title": "Rolex"}]
    (tmp_path / "deals.json").write_text(json.dumps(deals))
    with patch("app.DATA_DIR", tmp_path):
        r = client.delete("/api/deals/nonexistent")
    assert r.status_code == 404
    assert "not found" in json.loads(r.data)["error"]


def test_status_dirty_deals(client):
    def fake_run(cmd, **kw):
        if "status" in cmd:
            return MagicMock(returncode=0, stdout=" M data/deals.json\n", stderr="")
        return MagicMock(returncode=0, stdout="0\n", stderr="")
    with patch("app.subprocess.run", side_effect=fake_run):
        r = client.get("/api/status")
    body = json.loads(r.data)
    assert body["dirty"] is True
    assert body["needs_push"] is True


def test_push_stages_deals(client):
    """push stages both watches.json and deals.json."""
    staged_files = []

    def fake_run(cmd, **kw):
        if "add" in cmd:
            staged_files.extend(cmd[cmd.index("add") + 1:])
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("app.subprocess.run", side_effect=fake_run):
        r = client.post("/api/push")
    assert r.status_code == 200
    assert "data/deals.json" in staged_files
    assert "data/watches.json" in staged_files
