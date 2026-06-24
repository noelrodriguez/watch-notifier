# tests/test_tagging.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import watch_monitor
from watch_monitor import tag_deal, save_deals, slugify, size_signals, is_relevant, describe_response

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
    assert result["preferred_signals"] == []
    assert result["is_hot"] is False


def test_tag_adds_date_seen():
    result = tag_deal(dict(BASE_ITEM), REGISTRY)
    assert "date_seen" in result
    assert "T" in result["date_seen"]   # ISO format


def test_save_deals_noop_on_empty_list(tmp_path):
    deals_file = tmp_path / "deals.json"
    with patch("watch_monitor.DEALS_FILE", deals_file):
        save_deals([])
    assert not deals_file.exists()


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
    assert result["preferred_signals"] == ["40mm"]


def test_is_relevant_matches_group():
    groups = [["longines", "master", "moon"]]
    assert is_relevant("Longines Master Moonphase 40mm", groups) is True


def test_is_relevant_rejects_partial():
    groups = [["longines", "master", "moon"]]
    assert is_relevant("Longines Master Collection (no complication)", groups) is False


def test_is_relevant_empty_groups_is_false():
    assert is_relevant("anything at all", []) is False


def test_tag_no_ceiling_does_not_crash():
    registry = [{
        "brand": "Omega", "model": "Speedmaster", "size_mm": 42,
        "search_terms": ["omega speedmaster"],
        "refs": [{"ref": "310.30", "dial": "black", "strap": "bracelet"}],
        "price_ceiling": None,
    }]
    item = {
        "id": "reddit:xyz",
        "title": "Omega Speedmaster 42mm",
        "price": 5000,
        "url": "https://reddit.com/r/Watchexchange/comments/xyz",
        "source": "r/watchexchange",
    }
    result = tag_deal(item, registry)  # must not raise
    assert result["brand"] == "Omega"
    assert result["is_hot"] is True  # no ceiling = infinite ceiling, priced item qualifies


def test_source_failure_is_recorded_not_silent():
    watch_monitor.RUN_ERRORS.clear()
    registry = [{"search_terms": ["x"], "relevance_required_all": [["x"]]}]
    with patch("watch_monitor.requests.get", side_effect=Exception("429 Too Many Requests")), \
         patch("watch_monitor.time.sleep"):
        out = watch_monitor.search_reddit(registry)
    assert out == []
    assert watch_monitor.RUN_ERRORS  # failure surfaced instead of being swallowed


def test_notify_failure_posts_high_priority_alert():
    with patch("watch_monitor.requests.post") as post:
        watch_monitor.notify_failure(["Reddit 'x': boom"])
    assert post.called
    assert post.call_args.kwargs["headers"]["Priority"] == "high"


def test_search_reddit_parses_rss_feed():
    """search_reddit reads Reddit's Atom RSS feed: relevance + WTB filter, id strip, price."""
    from unittest.mock import MagicMock
    atom = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>[WTS] Longines Master Moonphase 40mm $1750</title>
    <link href="https://www.reddit.com/r/Watchexchange/comments/abc123/wts_longines/"/>
    <id>t3_abc123</id>
  </entry>
  <entry>
    <title>[WTB] Longines Master Moonphase wanted</title>
    <link href="https://www.reddit.com/r/Watchexchange/comments/def456/wtb_longines/"/>
    <id>t3_def456</id>
  </entry>
</feed>"""
    fake = MagicMock()
    fake.ok = True
    fake.content = atom
    registry = [{"search_terms": ["longines master moonphase"],
                 "relevance_required_all": [["longines", "master", "moon"]]}]
    with patch("watch_monitor.requests.get", return_value=fake), \
         patch("watch_monitor.time.sleep"):
        out = watch_monitor.search_reddit(registry)
    assert len(out) == 1                        # [WTB] entry filtered out
    assert out[0]["id"] == "reddit:abc123"      # "t3_" stripped to match prior dedup ids
    assert out[0]["price"] == 1750
    assert "comments/abc123" in out[0]["url"]
    assert out[0]["source"] == "r/watchexchange"


def test_default_source_toggles():
    # Per request: Reddit on (works via RSS), eBay & Chrono24 off by default.
    assert watch_monitor.ENABLE_REDDIT is True
    assert watch_monitor.ENABLE_EBAY is False
    assert watch_monitor.ENABLE_CHRONO24 is False


def test_flag_parses_truthy_and_falsy(monkeypatch):
    monkeypatch.setenv("X_FLAG", "yes")
    assert watch_monitor._flag("X_FLAG", "0") is True
    monkeypatch.setenv("X_FLAG", "0")
    assert watch_monitor._flag("X_FLAG", "1") is False
    monkeypatch.delenv("X_FLAG", raising=False)
    assert watch_monitor._flag("X_FLAG", "on") is True   # falls back to default


def test_gather_listings_runs_only_enabled_sources():
    with patch("watch_monitor.ENABLE_REDDIT", True), \
         patch("watch_monitor.ENABLE_EBAY", False), \
         patch("watch_monitor.ENABLE_CHRONO24", False), \
         patch("watch_monitor.search_reddit", return_value=[{"id": "reddit:1"}]) as red, \
         patch("watch_monitor.search_ebay") as ebay, \
         patch("watch_monitor.search_chrono24") as chrono:
        out = watch_monitor.gather_listings([])
    red.assert_called_once()
    ebay.assert_not_called()
    chrono.assert_not_called()
    assert out == [{"id": "reddit:1"}]


def test_describe_response_includes_status_and_header():
    """describe_response should surface the HTTP status code and relevant headers."""
    from unittest.mock import MagicMock
    fake = MagicMock()
    fake.status_code = 403
    fake.headers = {
        "cf-ray": "abc123-SJC",
        "server": "cloudflare",
        "content-type": "text/html",  # not in diagnostic set — should be absent
    }
    fake.text = "Access denied by Cloudflare"
    result = describe_response(fake)
    assert "403" in result
    assert "abc123-SJC" in result   # cf-ray header value present
    assert "cloudflare" in result   # server header value present
    assert "content-type" not in result  # non-diagnostic header filtered out
    assert "Access denied" in result    # body snippet included


# ------------------------------------------------------------------ fetch_op_price / enrich_reddit_prices ---

def _make_old_reddit_html(op_price_text, non_op_price_text=None):
    """Build a minimal old.reddit-like HTML string for fetch_op_price tests.

    Contains one OP comment (has 'author submitter' class on the author link) and
    optionally one non-OP comment (author link lacks 'submitter').
    """
    non_op_comment = ""
    if non_op_price_text:
        non_op_comment = f"""
        <div class="comment">
          <div class="entry">
            <p class="tagline"><a class="author">other_user</a></p>
            <div class="usertext-body">{non_op_price_text}</div>
          </div>
        </div>"""

    return f"""<html><body>
    <div class="commentarea">
      {non_op_comment}
      <div class="comment">
        <div class="entry">
          <p class="tagline"><a class="author submitter">op_user</a></p>
          <div class="usertext-body">{op_price_text}</div>
        </div>
      </div>
    </div>
    </body></html>"""


def _make_no_submitter_html():
    """Build HTML where no comment has the submitter class."""
    return """<html><body>
    <div class="commentarea">
      <div class="comment">
        <div class="entry">
          <p class="tagline"><a class="author">some_user</a></p>
          <div class="usertext-body">No price here at all</div>
        </div>
      </div>
    </div>
    </body></html>"""


def test_fetch_op_price_returns_price_from_submitter_comment():
    """fetch_op_price returns the price from the OP (submitter) comment and ignores
    a non-submitter comment that has a different price."""
    from unittest.mock import MagicMock
    html = _make_old_reddit_html(
        op_price_text="Asking $1850 shipped",
        non_op_price_text="I saw this for $999 elsewhere",
    )
    fake = MagicMock()
    fake.ok = True
    fake.text = html
    with patch("watch_monitor.requests.get", return_value=fake):
        price = watch_monitor.fetch_op_price(
            "https://www.reddit.com/r/Watchexchange/comments/abc/wts_watch/"
        )
    assert price == 1850  # OP price, not the non-OP $999


def test_fetch_op_price_returns_none_when_no_submitter_comment():
    """fetch_op_price returns None when no comment has the submitter CSS class."""
    from unittest.mock import MagicMock
    fake = MagicMock()
    fake.ok = True
    fake.text = _make_no_submitter_html()
    with patch("watch_monitor.requests.get", return_value=fake):
        price = watch_monitor.fetch_op_price(
            "https://www.reddit.com/r/Watchexchange/comments/abc/wts_watch/"
        )
    assert price is None


def test_fetch_op_price_returns_none_on_non_ok_response():
    """fetch_op_price returns None when the HTTP response is not ok."""
    from unittest.mock import MagicMock
    fake = MagicMock()
    fake.ok = False
    fake.status_code = 403
    fake.headers = {}
    fake.text = "Forbidden"
    with patch("watch_monitor.requests.get", return_value=fake):
        price = watch_monitor.fetch_op_price(
            "https://www.reddit.com/r/Watchexchange/comments/abc/wts_watch/"
        )
    assert price is None


def test_fetch_op_price_returns_none_and_makes_no_request_for_empty_url():
    """fetch_op_price returns None immediately and performs no network call for an empty URL."""
    with patch("watch_monitor.requests.get") as mock_get:
        price = watch_monitor.fetch_op_price("")
    assert price is None
    mock_get.assert_not_called()


def test_enrich_reddit_prices_fills_only_priceless_reddit_items():
    """enrich_reddit_prices sets price only on r/watchexchange items with price=None;
    items that already have a price, or come from a different source, are untouched."""
    from unittest.mock import MagicMock, call

    item_a = {  # reddit, no price → should be filled
        "id": "reddit:111",
        "title": "WTS watch A",
        "price": None,
        "url": "https://reddit.com/r/Watchexchange/comments/111/",
        "source": "r/watchexchange",
    }
    item_b = {  # reddit, already has a price → must NOT be touched
        "id": "reddit:222",
        "title": "WTS watch B",
        "price": 1500,
        "url": "https://reddit.com/r/Watchexchange/comments/222/",
        "source": "r/watchexchange",
    }
    item_c = {  # non-reddit, no price → must NOT be touched
        "id": "ebay:333",
        "title": "eBay watch C",
        "price": None,
        "url": "https://ebay.com/itm/333",
        "source": "eBay",
    }

    items = [item_a, item_b, item_c]

    with patch("watch_monitor.fetch_op_price", return_value=1850) as mock_fetch, \
         patch("watch_monitor.time.sleep") as mock_sleep:
        watch_monitor.enrich_reddit_prices(items)

    # Only item_a (priceless reddit) should have been enriched
    assert items[0]["price"] == 1850
    # item_b already had a price — must be unchanged
    assert items[1]["price"] == 1500
    # item_c is not a reddit source — must remain None
    assert items[2]["price"] is None

    # fetch_op_price called exactly once, with item_a's url
    mock_fetch.assert_called_once_with(item_a["url"])
    # politeness sleep called once for the one fetch
    mock_sleep.assert_called_once_with(1)
