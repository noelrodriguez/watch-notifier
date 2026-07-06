# tests/test_reddit_oauth.py — Reddit OAuth path: token, discovery, price recovery.
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import watch_monitor


@pytest.fixture(autouse=True)
def _clear_token_cache():
    """Isolate the per-process token cache between tests (and from other files)."""
    if hasattr(watch_monitor.reddit_token, "cache_clear"):
        watch_monitor.reddit_token.cache_clear()
    yield
    if hasattr(watch_monitor.reddit_token, "cache_clear"):
        watch_monitor.reddit_token.cache_clear()


def _set_creds(monkeypatch, value="x"):
    for attr in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                 "REDDIT_USERNAME", "REDDIT_PASSWORD"):
        monkeypatch.setattr(watch_monitor, attr, value)


def _clear_creds(monkeypatch):
    for attr in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                 "REDDIT_USERNAME", "REDDIT_PASSWORD"):
        monkeypatch.setattr(watch_monitor, attr, None)


# ── token grant ──────────────────────────────────────────────────────────────
def test_reddit_token_none_when_creds_missing(monkeypatch):
    _clear_creds(monkeypatch)
    assert watch_monitor.reddit_token() is None


def test_reddit_token_success(monkeypatch):
    _set_creds(monkeypatch)
    resp = MagicMock(ok=True)
    resp.json.return_value = {"access_token": "tok123", "expires_in": 86400}
    monkeypatch.setattr(watch_monitor.requests, "post", lambda *a, **k: resp)
    assert watch_monitor.reddit_token() == "tok123"


def test_reddit_token_none_on_http_error(monkeypatch):
    _set_creds(monkeypatch)
    resp = MagicMock(ok=False, status_code=401, headers={}, text="unauthorized")
    monkeypatch.setattr(watch_monitor.requests, "post", lambda *a, **k: resp)
    assert watch_monitor.reddit_token() is None


def test_reddit_token_none_on_exception(monkeypatch):
    _set_creds(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(watch_monitor.requests, "post", boom)
    assert watch_monitor.reddit_token() is None


def test_reddit_token_is_cached(monkeypatch):
    """lru_cache: the grant is POSTed once per process, not per call."""
    _set_creds(monkeypatch)
    resp = MagicMock(ok=True)
    resp.json.return_value = {"access_token": "tok"}
    post = MagicMock(return_value=resp)
    monkeypatch.setattr(watch_monitor.requests, "post", post)
    watch_monitor.reddit_token()
    watch_monitor.reddit_token()
    assert post.call_count == 1


# ── discovery ─────────────────────────────────────────────────────────────────
REGISTRY = [{
    "brand": "Longines", "model": "Master Collection Chrono Moonphase", "size_mm": 40,
    "search_terms": ["longines master moonphase"],
    "relevance_required_all": [["longines", "master", "moon"]],
    "refs": [], "price_ceiling": 2000,
}]


def _search_resp(children):
    resp = MagicMock(ok=True, status_code=200)
    resp.json.return_value = {"data": {"children": children}}
    return resp


def test_search_reddit_uses_oauth_when_token(monkeypatch):
    monkeypatch.setattr(watch_monitor, "reddit_token", lambda: "tok")
    children = [
        {"data": {"id": "abc", "title": "Longines Master Moonphase 40mm $1750",
                  "permalink": "/r/Watchexchange/comments/abc/x/"}},
        {"data": {"id": "zzz", "title": "Rolex Submariner Date",
                  "permalink": "/r/Watchexchange/comments/zzz/y/"}},
    ]
    monkeypatch.setattr(watch_monitor, "_oauth_get", lambda *a, **k: _search_resp(children))
    out = watch_monitor.search_reddit(REGISTRY)
    assert len(out) == 1                                    # only the relevant listing
    assert out[0]["id"] == "reddit:abc"
    assert out[0]["price"] == 1750
    assert out[0]["url"] == "https://www.reddit.com/r/Watchexchange/comments/abc/x/"


def test_search_reddit_skips_wtb_and_sold(monkeypatch):
    monkeypatch.setattr(watch_monitor, "reddit_token", lambda: "tok")
    children = [
        {"data": {"id": "a", "title": "[WTB] Longines Master Moonphase",
                  "permalink": "/r/Watchexchange/comments/a/"}},
        {"data": {"id": "b", "title": "Longines Master Moonphase 40mm SOLD",
                  "permalink": "/r/Watchexchange/comments/b/"}},
    ]
    monkeypatch.setattr(watch_monitor, "_oauth_get", lambda *a, **k: _search_resp(children))
    assert watch_monitor.search_reddit(REGISTRY) == []


def test_search_reddit_falls_back_to_rss_without_token(monkeypatch):
    monkeypatch.setattr(watch_monitor, "reddit_token", lambda: None)
    called = {}

    def fake_rss(reg):
        called["rss"] = True
        return [{"id": "reddit:rss1"}]
    monkeypatch.setattr(watch_monitor, "_search_reddit_rss", fake_rss)
    out = watch_monitor.search_reddit(REGISTRY)
    assert called.get("rss") is True
    assert out == [{"id": "reddit:rss1"}]


# ── price recovery ────────────────────────────────────────────────────────────
def _comments_resp(op_bodies):
    """The [post, comments] shape the comment API returns; adds one non-OP comment."""
    children = [{"data": {"is_submitter": True, "body": b}} for b in op_bodies]
    children.append({"data": {"is_submitter": False, "body": "asking 999 (not OP)"}})
    resp = MagicMock(ok=True, status_code=200)
    resp.json.return_value = [{"data": {}}, {"data": {"children": children}}]
    return resp


_POST_URL = "https://www.reddit.com/r/Watchexchange/comments/xyz/slug/"


def test_op_price_oauth_reads_submitter_price(monkeypatch):
    resp = _comments_resp(["Description?", "Asking $1700 shipped CONUS"])
    monkeypatch.setattr(watch_monitor, "_oauth_get", lambda *a, **k: resp)
    assert watch_monitor._op_price_oauth(_POST_URL, "tok", "Longines") == 1700


def test_op_price_oauth_ignores_non_op_comment(monkeypatch):
    resp = _comments_resp(["just some text, no price here"])
    monkeypatch.setattr(watch_monitor, "_oauth_get", lambda *a, **k: resp)
    monkeypatch.setattr(watch_monitor, "extract_price_llm", lambda *a, **k: None)
    # the "asking 999" lives in a non-OP comment and must be ignored
    assert watch_monitor._op_price_oauth(_POST_URL, "tok") is None


def test_op_price_oauth_falls_back_to_llm(monkeypatch):
    resp = _comments_resp(["L2.673 box and papers **2700** shipped"])   # regex misses this
    monkeypatch.setattr(watch_monitor, "_oauth_get", lambda *a, **k: resp)
    monkeypatch.setattr(watch_monitor, "extract_price_llm", lambda *a, **k: 2700)
    assert watch_monitor._op_price_oauth(_POST_URL, "tok") == 2700


def test_op_price_oauth_none_on_403(monkeypatch):
    resp = MagicMock(ok=False, status_code=403, headers={}, text="blocked")
    monkeypatch.setattr(watch_monitor, "_oauth_get", lambda *a, **k: resp)
    assert watch_monitor._op_price_oauth(_POST_URL, "tok") is None


def test_fetch_op_price_uses_oauth_when_token(monkeypatch):
    monkeypatch.setattr(watch_monitor, "reddit_token", lambda: "tok")
    monkeypatch.setattr(watch_monitor, "_op_price_oauth", lambda *a, **k: 4242)
    monkeypatch.setattr(watch_monitor, "_op_price_html",
                        lambda *a, **k: pytest.fail("should not hit the HTML path"))
    assert watch_monitor.fetch_op_price(_POST_URL) == 4242


def test_fetch_op_price_falls_back_to_html_without_token(monkeypatch):
    monkeypatch.setattr(watch_monitor, "reddit_token", lambda: None)
    monkeypatch.setattr(watch_monitor, "_op_price_html", lambda *a, **k: 111)
    assert watch_monitor.fetch_op_price(_POST_URL) == 111


# ── backfill: Actions gating now depends on OAuth availability ─────────────────
def test_backfill_runs_on_actions_with_oauth(tmp_path, monkeypatch):
    """With OAuth, price recovery works from a runner, so backfill no longer skips."""
    deals = [{"id": "reddit:a", "source": "r/watchexchange", "price": None,
              "url": _POST_URL}]
    deals_file = tmp_path / "deals.json"
    deals_file.write_text(json.dumps(deals))
    monkeypatch.setattr(watch_monitor, "reddit_token", lambda: "tok")
    with patch("watch_monitor.DEALS_FILE", deals_file), \
         patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
         patch("watch_monitor.fetch_op_price", return_value=1750), \
         patch("watch_monitor.time.sleep"):
        watch_monitor.backfill_prices()
    assert json.loads(deals_file.read_text())[0]["price"] == 1750
