# tests/test_tagging.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import watch_monitor
from watch_monitor import tag_deal, save_deals, slugify, size_signals, is_relevant, describe_response, parse_price, _to_price

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


def _run_backfill(tmp_path, deals, fetch_return):
    deals_file = tmp_path / "deals.json"
    deals_file.write_text(json.dumps(deals))
    with patch("watch_monitor.DEALS_FILE", deals_file), \
         patch("watch_monitor.fetch_op_price", return_value=fetch_return), \
         patch("watch_monitor.time.sleep"):
        watch_monitor.backfill_prices()
    return json.loads(deals_file.read_text())


def test_backfill_recovers_price(tmp_path):
    deals = [{"id": "reddit:a", "source": "r/watchexchange", "price": None, "url": "u"}]
    saved = _run_backfill(tmp_path, deals, fetch_return=1750)
    assert saved[0]["price"] == 1750
    assert saved[0]["price_attempts"] == 1


def test_backfill_increments_attempts_on_miss(tmp_path):
    deals = [{"id": "reddit:a", "source": "r/watchexchange", "price": None,
              "url": "u", "price_attempts": 2}]
    saved = _run_backfill(tmp_path, deals, fetch_return=None)
    assert saved[0]["price"] is None          # still blank, not given up yet
    assert saved[0]["price_attempts"] == 3


def test_backfill_flags_minus_one_after_five_attempts(tmp_path):
    deals = [{"id": "reddit:a", "source": "r/watchexchange", "price": None,
              "url": "u", "price_attempts": 4}]
    saved = _run_backfill(tmp_path, deals, fetch_return=None)
    assert saved[0]["price"] == -1            # 5th miss -> give-up sentinel
    assert saved[0]["price_attempts"] == 5


def test_backfill_skips_priced_and_nonreddit(tmp_path):
    deals = [
        {"id": "reddit:a", "source": "r/watchexchange", "price": 500, "url": "u"},
        {"id": "ebay:b", "source": "eBay", "price": None, "url": "u"},
    ]
    saved = _run_backfill(tmp_path, deals, fetch_return=9999)
    assert saved[0]["price"] == 500           # already priced -> untouched
    assert "price_attempts" not in saved[0]
    assert saved[1]["price"] is None          # non-reddit -> untouched
    assert "price_attempts" not in saved[1]


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


_OP_HTML = """<div class="commentarea"><div class="comment">
  <a class="author submitter">seller</a>
  <div class="entry"><div class="usertext-body">Price: $2,499 shipped</div></div>
</div></div>"""


def test_fetch_op_price_retries_once_on_429():
    """A transient 429 is waited out and retried once, so the price still recovers."""
    from unittest.mock import MagicMock
    limited = MagicMock(status_code=429, headers={"x-ratelimit-reset": "2"})
    ok = MagicMock(status_code=200, ok=True, text=_OP_HTML)
    with patch("watch_monitor.requests.get", side_effect=[limited, ok]) as get, \
         patch("watch_monitor.time.sleep") as sleep:
        price = watch_monitor.fetch_op_price("https://www.reddit.com/r/Watchexchange/comments/x/")
    assert price == 2499
    assert get.call_count == 2        # retried once after the 429
    assert sleep.called               # waited out the reset


def test_fetch_op_price_does_not_retry_on_403():
    """A 403 is a hard IP block, not transient — return None without a wasted retry."""
    from unittest.mock import MagicMock
    blocked = MagicMock(status_code=403, ok=False, headers={})
    with patch("watch_monitor.requests.get", return_value=blocked) as get, \
         patch("watch_monitor.time.sleep"), \
         patch("watch_monitor.describe_response", return_value="HTTP 403"):
        price = watch_monitor.fetch_op_price("https://www.reddit.com/r/Watchexchange/comments/x/")
    assert price is None
    assert get.call_count == 1        # no retry on a hard block


_OP_HTML_MARKDOWN_PRICE = """<div class="commentarea"><div class="comment">
  <a class="author submitter">seller</a>
  <div class="entry"><div class="usertext-body">L2.773.4.78.3 Box and Papers **2700** fully insured shipping incl</div></div>
</div></div>"""


def _fake_anthropic(reply_text):
    """Build a stand-in `anthropic` module whose messages.create returns reply_text."""
    from unittest.mock import MagicMock
    block = MagicMock(type="text", text=reply_text)
    resp = MagicMock(content=[block])
    module = MagicMock()
    module.Anthropic.return_value.messages.create.return_value = resp
    return module


def test_parse_price_misses_markdown_wrapped_price():
    """Documents the regex gap the LLM fallback exists for: **2700** + 'shipping'."""
    text = "L2.773.4.78.3 Box and Papers **2700** fully insured shipping incl"
    assert watch_monitor.parse_price(text, loose=True) is None


def test_extract_price_llm_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert watch_monitor.extract_price_llm("asking **2700** shipped") is None


def test_extract_price_llm_skips_textless(monkeypatch):
    """No digit in the comment → no API call, returns None."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    import sys
    called = _fake_anthropic("2700")
    monkeypatch.setitem(sys.modules, "anthropic", called)
    assert watch_monitor.extract_price_llm("Messaging") is None
    assert not called.Anthropic.called           # never reached the SDK


def test_extract_price_llm_parses_and_validates(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    import sys
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic("2700"))
    assert watch_monitor.extract_price_llm("**2700** shipped") == 2700
    # Implausible number rejected by _to_price (must be 100..100000)
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic("5"))
    assert watch_monitor.extract_price_llm("watch for 5 bucks lol") is None


def test_fetch_op_price_falls_back_to_llm(monkeypatch):
    """When the regex finds no price, the best OP comment goes to the LLM."""
    from unittest.mock import MagicMock
    ok = MagicMock(status_code=200, ok=True, text=_OP_HTML_MARKDOWN_PRICE)
    with patch("watch_monitor.requests.get", return_value=ok), \
         patch("watch_monitor.time.sleep"), \
         patch("watch_monitor.extract_price_llm", return_value=2700) as llm:
        price = watch_monitor.fetch_op_price(
            "https://www.reddit.com/r/Watchexchange/comments/x/", title="Longines")
    assert price == 2700
    assert llm.called
    assert "2700" in llm.call_args.args[0]       # passed the OP comment text


def test_fetch_op_price_skips_llm_when_regex_hits(monkeypatch):
    """The cheap regex path wins; the LLM is never called when a price is found."""
    from unittest.mock import MagicMock
    ok = MagicMock(status_code=200, ok=True, text=_OP_HTML)
    with patch("watch_monitor.requests.get", return_value=ok), \
         patch("watch_monitor.extract_price_llm") as llm:
        price = watch_monitor.fetch_op_price("https://www.reddit.com/r/Watchexchange/comments/x/")
    assert price == 2499
    assert not llm.called


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

    # fetch_op_price called exactly once, with item_a's url + title
    mock_fetch.assert_called_once_with(item_a["url"], item_a["title"])
    # politeness sleep called once for the one fetch
    mock_sleep.assert_called_once_with(1)


# ------------------------------------------------------------------ parse_price / _to_price ---

# 1. Strict mode (default) parses explicit $ amounts
def test_parse_price_strict_dollar_with_comma():
    """$1,750 in a title is parsed and comma is stripped."""
    assert parse_price("$1,750 box and papers") == 1750


def test_parse_price_strict_dollar_no_comma():
    """$2000 (no comma) is also parsed correctly in strict mode."""
    assert parse_price("WTS Longines $2000 shipped") == 2000


def test_parse_price_strict_dollar_with_space():
    """$ 1850 (space after dollar sign) is tolerated by the regex."""
    assert parse_price("$ 1850 OBO") == 1850


# 2. Strict mode returns None for bare numbers (no $) — protects against
#    refs, years, and sizes found in listing titles
def test_parse_price_strict_rejects_bare_number_in_title():
    """A realistic Longines title with ref, year, and size — no $ — returns None."""
    assert parse_price("Longines Master 40mm ref L2.673.4.78.3 2025") is None


def test_parse_price_strict_rejects_year():
    """A bare year like 2025 with no $ must return None."""
    assert parse_price("Bought in 2025") is None


def test_parse_price_strict_rejects_size_only():
    """A bare size like 40mm with no $ must return None."""
    assert parse_price("40mm case") is None


# 3. Loose mode: cue-then-number patterns
def test_parse_price_loose_asking_number():
    """'Asking 3750' in a seller comment body is matched in loose mode."""
    assert parse_price("Asking 3750", loose=True) == 3750


def test_parse_price_loose_price_colon_number():
    """'price: 2100' is matched in loose mode."""
    assert parse_price("price: 2100", loose=True) == 2100


def test_parse_price_loose_selling_for_number():
    """'selling for 1750 shipped' is matched in loose mode."""
    assert parse_price("selling for 1750 shipped", loose=True) == 1750


# 4. Loose mode: number-then-cue patterns
def test_parse_price_loose_number_obo():
    """'3,250 obo' (number then cue, comma included) is matched in loose mode."""
    assert parse_price("3,250 obo", loose=True) == 3250


def test_parse_price_loose_number_firm():
    """'1750 firm' (number then cue) is matched in loose mode."""
    assert parse_price("1750 firm", loose=True) == 1750


def test_parse_price_loose_number_shipped():
    """'2800 shipped' (number then cue) is matched in loose mode."""
    assert parse_price("2800 shipped", loose=True) == 2800


# 5. Loose mode still returns None when there's no $ and no price cue,
#    even when numbers are present (year / size / ref)
def test_parse_price_loose_no_cue_no_dollar_returns_none():
    """A body with only ref, year, and size — no $ and no cue — returns None in loose mode."""
    assert parse_price("Bought in 2025, 40mm, ref L2.673.4.78.3", loose=True) is None


# 6. Plausibility bounds via _to_price
def test_to_price_too_small_returns_none():
    """A number below 100 is not a plausible watch price."""
    assert _to_price("50") is None


def test_to_price_too_large_returns_none():
    """A number above 100000 is not a plausible watch price."""
    assert _to_price("250000") is None


def test_to_price_normal_returns_int():
    """A normal watch price like 2,000 is parsed to an int."""
    assert _to_price("2,000") == 2000


def test_parse_price_strict_too_small_returns_none():
    """$50 is below the plausibility floor; parse_price must return None."""
    assert parse_price("$50") is None


def test_parse_price_strict_too_large_returns_none():
    """$250000 exceeds the plausibility ceiling; parse_price must return None."""
    assert parse_price("$250000") is None


def test_parse_price_strict_boundary_price_returns_value():
    """$2,000 is a plausible price and should be returned correctly."""
    assert parse_price("$2,000") == 2000


# ------------------------------------------------------------------ tag_deal: group-hit path (relevance_required_all) ---

# A minimal registry entry that has a relevance_required_all group whose tokens
# are NOT a contiguous substring found in search_terms, which lets us isolate
# the group_hit branch in tag_deal.
REGISTRY_WITH_GROUP = [
    {
        "brand": "Longines",
        "model": "Master Collection Chrono Moonphase",
        "size_mm": 40,
        "refs": [
            {"ref": "L2.673.4.78.6", "dial": "silver", "strap": "bracelet"},
        ],
        # search_terms only contain a contiguous phrase that WON'T appear in the
        # test title ("Collection Triple Date Moonphase" breaks the contiguity).
        "search_terms": ["longines master moonphase", "longines master chronograph moonphase"],
        "relevance_required_all": [["longines", "master", "moon"]],
        "price_ceiling": 2000,
    }
]

# Title that matches the group ["longines","master","moon"] but does NOT contain
# the contiguous search_term "longines master moonphase" (the words "master" and
# "moonphase" are separated by "Collection Triple Date") and contains no ref.
_GROUP_TITLE = "[WTS] Longines Master Collection Triple Date Moonphase 40mm box"
_GROUP_ITEM = {
    "id": "reddit:zzz",
    "title": _GROUP_TITLE,
    "price": 1800,
    "url": "https://reddit.com/r/Watchexchange/comments/zzz",
    "source": "r/watchexchange",
}


def test_tag_group_hit_sets_brand_model_size():
    """A title matching relevance_required_all (all tokens present, non-contiguous)
    gets brand/model/size_mm populated even when no contiguous search_term matches
    and no registry ref appears in the title."""
    result = tag_deal(dict(_GROUP_ITEM), REGISTRY_WITH_GROUP)
    assert result["brand"] == "Longines"
    assert result["model"] == "Master Collection Chrono Moonphase"
    assert result["size_mm"] == 40


def test_tag_contiguous_search_term_still_tags():
    """Regression: a title containing a contiguous search_term continues to tag
    (the group_hit addition must not break the existing term_hit path)."""
    item = {**BASE_ITEM, "title": "Longines Master Moonphase 40mm great condition"}
    result = tag_deal(item, REGISTRY_WITH_GROUP)
    assert result["brand"] == "Longines"
    assert result["model"] == "Master Collection Chrono Moonphase"


def test_tag_ref_in_title_still_tags():
    """Regression: a title containing a registry ref continues to tag
    (the group_hit addition must not break the existing matched_refs path)."""
    item = {**BASE_ITEM, "title": "Longines L2.673.4.78.6 barely worn box papers"}
    result = tag_deal(item, REGISTRY_WITH_GROUP)
    assert result["brand"] == "Longines"
    assert result["ref_matches"] == ["L2.673.4.78.6"]
    assert result["dial"] == "silver"
    assert result["strap"] == "bracelet"


def test_tag_unrelated_title_not_tagged_by_group():
    """Negative: a title that matches neither a search_term, nor a ref, nor the
    relevance group returns brand=None — the group path must not match everything."""
    item = {**BASE_ITEM, "title": "Rolex Submariner Date blue dial box papers"}
    result = tag_deal(item, REGISTRY_WITH_GROUP)
    assert result["brand"] is None
    assert result["model"] is None
    assert result["preferred_signals"] == []
    assert result["is_hot"] is False


def test_tag_group_hit_populates_preferred_signals_for_size():
    """A group-matched title that contains '40mm' gets preferred_signals populated
    (the size signals branch runs for any match path, including group_hit)."""
    item = {**_GROUP_ITEM, "title": "[WTS] Longines Master Collection Triple Date Moonphase 40mm"}
    result = tag_deal(item, REGISTRY_WITH_GROUP)
    assert "40mm" in result["preferred_signals"]
