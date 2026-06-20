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
