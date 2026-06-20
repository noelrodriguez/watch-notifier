#!/usr/bin/env python3
"""
Watch Tracker — secondary-market monitor for Longines Master Chrono Moonphase (40mm).

Runs ONCE per invocation (schedule it hourly via Windows Task Scheduler).
Scans r/watchexchange + eBay (+ Chrono24 best-effort), dedups against a local
state file, and pushes any NEW listings to your phone via ntfy.sh.

Setup + scheduling instructions are in README.md.
"""

import json
import os
import re
import sys
import time
import html
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ------------------------------------------------------------------ CONFIG ---
# 1) Pick a UNIQUE, hard-to-guess topic (ntfy topics are public to anyone who
#    knows the name). Subscribe to this same topic in the ntfy phone app.
# Note: `or` (not getenv's default arg) so an EMPTY env var (e.g. an unset
# GitHub secret rendered as "") falls back to the value here instead of breaking.
NTFY_TOPIC  = os.getenv("NTFY_TOPIC") or "watchtracker-noelrodriguez-12251996"
NTFY_SERVER = os.getenv("NTFY_SERVER") or "https://ntfy.sh"

# 2) What we're hunting. Keep terms broad; the relevance filter narrows results.
SEARCH_TERMS = [
    "longines master moonphase",
    "longines master chronograph moonphase",
]

# Highlight (high-priority push) anything at/under this USD price.
PRICE_ALERT_CEILING = 2000

# A listing must contain ALL of one of these keyword groups to count as relevant.
RELEVANCE_REQUIRED_ALL = [
    ["longines", "master", "moon"],   # 'moon' matches moonphase / moon phase / moon-phase
]
# Preferred signals — not required, just boost priority / called out in the alert.
PREFERRED_SIGNALS = ["40mm", "40 mm", "l2.673", "78.6", "chrono"]

# Optional: also mirror alerts to a Telegram bot (leave blank to disable).
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

STATE_FILE    = Path(__file__).parent / "data" / "monitor_state.json"
DEALS_FILE    = Path(__file__).parent / "data" / "deals.json"
REGISTRY_FILE = Path(__file__).parent / "data" / "watches.json"
MAX_PUSH_PER_RUN = 8          # safety cap so a first run / source glitch can't spam you
HTTP_TIMEOUT = 20
UA = "watch-tracker-monitor/1.0 (personal use)"
# ---------------------------------------------------------------------------


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def load_state():
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()).get("seen_ids", []))
        except Exception as e:
            log(f"WARN: could not read state file ({e}); starting fresh.")
    return set()


def save_state(seen_ids):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(
        {"updated": datetime.now(timezone.utc).isoformat(),
         "seen_ids": sorted(seen_ids)}, indent=2))


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
    item["preferred_signals"] = []

    title_lower = item["title"].lower()
    for entry in registry:
        matched_refs = [r for r in entry.get("refs", []) if r["ref"].lower() in title_lower]
        term_hit = any(term in title_lower for term in entry.get("search_terms", []))
        if term_hit or matched_refs:
            item["brand"] = entry.get("brand")
            item["model"] = entry.get("model")
            item["size_mm"] = entry.get("size_mm")

            title_l = item["title"].lower()
            item["preferred_signals"] = [
                s for s in size_signals(entry.get("size_mm")) if s in title_l
            ]

            item["ref_matches"] = [r["ref"] for r in matched_refs]
            if matched_refs:
                item["dial"] = matched_refs[0].get("dial")
                item["strap"] = matched_refs[0].get("strap")

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
        if not isinstance(existing, list):
            log("WARN: deals file is not a list; starting fresh.")
            existing = []
    existing.extend(new_items)
    DEALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEALS_FILE.write_text(json.dumps(existing, indent=2))


def parse_price(text):
    """Return the first USD price found as an int, or None."""
    if not text:
        return None
    m = re.search(r"\$\s?([0-9][0-9,]{2,7})", text)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def is_relevant(title):
    t = title.lower()
    for group in RELEVANCE_REQUIRED_ALL:
        if all(tok in t for tok in group):
            return True
    return False


def preferred_hits(title):
    t = title.lower()
    return [s for s in PREFERRED_SIGNALS if s in t]


def slugify(brand, model):
    """Stable id from brand + model: lowercase, non-alphanumerics → single hyphens."""
    raw = f"{brand} {model}".lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", raw)).strip("-")


def size_signals(size_mm):
    """Preferred-match size strings derived from a watch's case size."""
    if not size_mm:
        return []
    return [f"{size_mm}mm", f"{size_mm} mm"]


# ------------------------------------------------------------------ SOURCES --
def search_reddit():
    """r/watchexchange via the public JSON endpoint. Reliable, no auth."""
    out = []
    for term in SEARCH_TERMS:
        url = ("https://www.reddit.com/r/Watchexchange/search.json"
               f"?q={requests.utils.quote(term)}&restrict_sr=on&sort=new&limit=50")
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            for child in r.json().get("data", {}).get("children", []):
                d = child.get("data", {})
                title = html.unescape(d.get("title", ""))
                if not is_relevant(title):
                    continue
                # Skip sold / want-to-buy posts
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


def search_ebay():
    """eBay newly-listed search results (HTML scrape — usually works w/o JS)."""
    out = []
    for term in SEARCH_TERMS:
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
                if not is_relevant(title) or "shop on ebay" in title.lower():
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


def search_chrono24():
    """Chrono24 best-effort. Often blocked by anti-bot; failures are non-fatal."""
    out = []
    ref_pages = [
        "https://www.chrono24.com/longines/ref-l26734786.htm",  # L2.673.4.78.6 (steel bracelet)
        "https://www.chrono24.com/longines/ref-l26734783.htm",  # L2.673.4.78.3 (leather)
    ]
    for url in ref_pages:
        try:
            r = requests.get(url, headers={"User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
                timeout=HTTP_TIMEOUT)
            if r.status_code != 200 or "captcha" in r.text.lower():
                log(f"WARN: Chrono24 blocked/non-200 for {url} (status {r.status_code}).")
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href*='--id']"):
                href = a.get("href", "")
                m = re.search(r"--id(\d+)", href)
                if not m:
                    continue
                item_id = m.group(1)
                title = a.get_text(" ", strip=True)[:120] or "Longines Master Collection L2.673.4.78.x"
                link = href if href.startswith("http") else "https://www.chrono24.com" + href
                out.append({
                    "id": f"chrono24:{item_id}",
                    "title": title,
                    "price": parse_price(a.get_text()),
                    "url": link,
                    "source": "Chrono24",
                })
        except Exception as e:
            log(f"WARN: Chrono24 fetch failed for {url}: {e}")
        time.sleep(1)
    return out


# -------------------------------------------------------------------- PUSH ---
def push_ntfy(item):
    price = f"${item['price']}" if item.get("price") else "price?"
    prefs = preferred_hits(item["title"])
    under_ceiling = item.get("price") and item["price"] <= PRICE_ALERT_CEILING

    title = f"{price} · {item['source']}"
    if under_ceiling:
        title = "🔥 " + title

    body = item["title"]
    if prefs:
        body += f"\n[match: {', '.join(prefs)}]"

    headers = {
        "Title": title.encode("utf-8"),
        "Click": item["url"],
        "Tags": "watch" + (",fire" if under_ceiling else ""),
        "Priority": "high" if under_ceiling else "default",
    }
    try:
        r = requests.post(f"{NTFY_SERVER}/{NTFY_TOPIC}",
                          data=body.encode("utf-8"), headers=headers,
                          timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return True
    except Exception as e:
        log(f"ERROR: ntfy push failed: {e}")
        return False


def push_telegram(item):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    price = f"${item['price']}" if item.get("price") else "price?"
    text = f"*{price} · {item['source']}*\n{item['title']}\n{item['url']}"
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text,
                  "parse_mode": "Markdown", "disable_web_page_preview": False},
            timeout=HTTP_TIMEOUT)
    except Exception as e:
        log(f"WARN: Telegram push failed: {e}")


# -------------------------------------------------------------------- MAIN ---
def run_test_push():
    """`python watch_monitor.py --test` — fire one sample alert to confirm your phone receives it."""
    if "REPLACE-ME" in NTFY_TOPIC:
        log("ERROR: set NTFY_TOPIC (top of file or env var) to your own unique topic first.")
        sys.exit(1)
    sample = {
        "id": "test:sample",
        "title": "TEST — Longines Master Chrono Moonphase 40mm L2.673.4.78.6, box & papers",
        "price": 1750,
        "url": "https://www.reddit.com/r/Watchexchange/comments/1to9v9y/wts_longines_master_collection_triple_calendar/",
        "source": "self-test",
    }
    ok = push_ntfy(sample)
    push_telegram(sample)
    log("Test push sent — check your phone." if ok else "Test push FAILED — see error above.")
    sys.exit(0 if ok else 1)


def main():
    if "--test" in sys.argv:
        run_test_push()

    if "REPLACE-ME" in NTFY_TOPIC:
        log("ERROR: set NTFY_TOPIC (top of file or env var) to your own unique topic first.")
        sys.exit(1)

    seen = load_state()
    first_run = not STATE_FILE.exists()

    found = []
    for fn in (search_reddit, search_ebay, search_chrono24):
        found.extend(fn())

    # Dedup within this run and against history
    unique = {}
    for it in found:
        unique[it["id"]] = it
    new_items = [it for it in unique.values() if it["id"] not in seen]

    # Cheapest first (None prices sort last)
    new_items.sort(key=lambda x: (x.get("price") is None, x.get("price") or 0))

    log(f"Scanned {len(unique)} listings, {len(new_items)} new "
        f"(first_run={first_run}).")

    if first_run:
        # Seed baseline silently so we don't blast every existing listing.
        save_state(set(unique.keys()))
        log("First run: baseline saved, no notifications sent. "
            "Future runs will alert on genuinely new listings.")
        return

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

    # Remember everything we saw (even un-pushed overflow) to avoid re-alerting.
    seen.update(unique.keys())
    save_state(seen)
    log(f"Done. {pushed} notification(s) sent.")


if __name__ == "__main__":
    main()
