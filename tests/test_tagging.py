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
