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
import xml.etree.ElementTree as ET
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

# Optional: also mirror alerts to a Telegram bot (leave blank to disable).
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

STATE_FILE    = Path(__file__).parent / "data" / "monitor_state.json"
DEALS_FILE    = Path(__file__).parent / "data" / "deals.json"
REGISTRY_FILE = Path(__file__).parent / "data" / "watches.json"
MAX_PUSH_PER_RUN = 8          # safety cap so a first run / source glitch can't spam you
HTTP_TIMEOUT = 20
UA = "watch-tracker-monitor/1.0 (personal use)"
# Browser-like UA for old.reddit HTML (used to recover OP-comment prices).
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _flag(name, default):
    """Read a boolean toggle from the environment ("1/true/yes/on" = enabled)."""
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# Per-source toggles. Flip the default here or set the env var (e.g. ENABLE_EBAY=1).
# Reddit is on (it works via the RSS feed); eBay (Akamai-blocked) and Chrono24
# (anti-bot) are off by default until they're working again.
ENABLE_REDDIT   = _flag("ENABLE_REDDIT", "1")
ENABLE_EBAY     = _flag("ENABLE_EBAY", "0")
ENABLE_CHRONO24 = _flag("ENABLE_CHRONO24", "0")

# Source fetch failures collected during a run. A non-empty list at the end of
# main() triggers one ntfy alert so a broken scrape (e.g. Reddit 429) isn't silent.
# ponytail: module-level list, fine for a single-run script; reset at top of main().
RUN_ERRORS = []
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
        # Also accept the same relevance gate that let the listing in: search_terms
        # are contiguous substrings, but real titles read "Master Collection ...
        # Moonphase", so match on relevance_required_all (all tokens present) too.
        group_hit = is_relevant(item["title"], entry.get("relevance_required_all", []))
        if term_hit or matched_refs or group_hit:
            item["brand"] = entry.get("brand")
            item["model"] = entry.get("model")
            item["size_mm"] = entry.get("size_mm")

            item["preferred_signals"] = [
                s for s in size_signals(entry.get("size_mm")) if s in title_lower
            ]

            item["ref_matches"] = [r["ref"] for r in matched_refs]
            if matched_refs:
                item["dial"] = matched_refs[0].get("dial")
                item["strap"] = matched_refs[0].get("strap")

            ceiling = entry.get("price_ceiling") or float("inf")
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


# Words sellers use around a price, for $-less detection in comment bodies.
_PRICE_CUE = r"asking|price|selling|sell|firm|obo|shipped|net|usd|best offer"


def _to_price(s):
    """'1,750' -> 1750 if it's a plausible watch price (100..100000), else None."""
    try:
        n = int(s.replace(",", ""))
    except ValueError:
        return None
    return n if 100 <= n <= 100000 else None


def parse_price(text, loose=False):
    """Return the first USD price found as an int, or None.

    Strict mode (default, used on titles/listings) only matches an explicit
    "$" amount — titles are full of refs/years/sizes, so a bare number there is
    not safely a price. loose=True (used on a seller's comment body) also matches
    a number tied to a price cue like "asking 3750" or "3750 shipped", because
    on r/watchexchange the price is often stated that way without a "$".
    """
    if not text:
        return None
    m = re.search(r"\$\s?([0-9][0-9,]{2,7})", text)
    if m:
        return _to_price(m.group(1))
    if loose:
        # cue then number: "asking 3750", "price: 1,750", "selling for 1750"
        m = re.search(rf"(?:{_PRICE_CUE})\D{{0,10}}?([0-9][0-9,]{{2,7}})", text, re.I)
        if m and _to_price(m.group(1)) is not None:
            return _to_price(m.group(1))
        # number then cue: "3750 shipped", "1750 obo", "3,750 firm"
        m = re.search(rf"([0-9][0-9,]{{2,7}})\s*(?:{_PRICE_CUE})", text, re.I)
        if m:
            return _to_price(m.group(1))
    return None


def is_relevant(title, groups):
    t = title.lower()
    for group in groups:
        if group and all(tok in t for tok in group):
            return True
    return False


def slugify(brand, model):
    """Stable id from brand + model: lowercase, non-alphanumerics → single hyphens."""
    raw = f"{brand} {model}".lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", raw)).strip("-")


def size_signals(size_mm):
    """Preferred-match size strings derived from a watch's case size."""
    if not size_mm:
        return []
    return [f"{size_mm}mm", f"{size_mm} mm"]


# ------------------------------------------------------------------ HELPERS --
_DIAGNOSTIC_HEADERS = {
    "retry-after", "www-authenticate",
    "x-ratelimit-remaining", "x-ratelimit-used", "x-ratelimit-reset",
    "server", "cf-mitigated", "cf-ray",
}


def describe_response(r):
    """Return a compact diagnostic string for a non-2xx (or blocked) response.

    Captures: status code, filtered headers (rate-limit / anti-bot signals),
    and the first ~500 chars of the body — enough to diagnose 403/429 causes
    without blowing up log lines.
    """
    hdrs = {k.lower(): v for k, v in r.headers.items()}
    relevant = {k: v for k, v in hdrs.items()
                if k in _DIAGNOSTIC_HEADERS or k.startswith("x-reddit-")}
    body_snippet = (r.text or "")[:500].strip()
    return f"HTTP {r.status_code} | headers={relevant} | body={body_snippet!r}"


# ------------------------------------------------------------------ SOURCES --
ATOM = "{http://www.w3.org/2005/Atom}"  # namespace prefix for Reddit's RSS/Atom feed


def _get_reddit_rss(url):
    """GET a Reddit RSS URL, retrying ONCE on 429 after the rate-limit reset.

    The anonymous feed allows only ~1 request per ~minute per IP (it reports
    x-ratelimit-remaining 0 after every call), so back-to-back per-term queries
    will 429. We read x-ratelimit-reset and wait it out, then retry once.
    ponytail: one retry, reset capped at 65s. With many search_terms a run can
    take a few minutes of waiting — prune terms or cache results if that bites.
    """
    r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
    if r.status_code == 429:
        try:
            wait = min(int(r.headers.get("x-ratelimit-reset", "5")) + 1, 65)
        except ValueError:
            wait = 5
        log(f"INFO: Reddit RSS rate-limited; waiting {wait}s then retrying.")
        time.sleep(wait)
        r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
    return r


def search_reddit(registry):
    """r/watchexchange via the public RSS search feed (search.rss). No auth.

    Reddit's anonymous JSON API (search.json and the other *.json endpoints) now
    returns 403 for unauthenticated clients regardless of User-Agent or IP, but
    the RSS syndication feed still serves results anonymously. Atom entries carry
    the title (for relevance + price), the permalink, and the post id — all we
    need. NOTE: the feed's search does NOT honor boolean OR, so terms must be
    queried one at a time. Relevance is scoped per registry entry.
    """
    out = []
    seen_ids = set()
    for entry in registry:
        groups = entry.get("relevance_required_all", [])
        for term in entry.get("search_terms", []):
            url = ("https://www.reddit.com/r/Watchexchange/search.rss"
                   f"?q={requests.utils.quote(term)}&restrict_sr=on&sort=new&limit=50")
            try:
                r = _get_reddit_rss(url)
                if not r.ok:
                    log(f"WARN: Reddit search failed for '{term}': {describe_response(r)}")
                    RUN_ERRORS.append(f"Reddit '{term}': HTTP {r.status_code}")
                    continue
                feed = ET.fromstring(r.content)
                for item in feed.iter(f"{ATOM}entry"):
                    title_el = item.find(f"{ATOM}title")
                    link_el = item.find(f"{ATOM}link")
                    id_el = item.find(f"{ATOM}id")
                    title = html.unescape(title_el.text or "") if title_el is not None else ""
                    if not is_relevant(title, groups):
                        continue
                    low = title.lower()
                    if low.startswith("[wtb") or "sold" in low:
                        continue
                    raw_id = (id_el.text if id_el is not None else "") or ""
                    post_id = raw_id.split("_")[-1]  # "t3_abc123" -> "abc123"
                    item_id = f"reddit:{post_id}"
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    out.append({
                        "id": item_id,
                        "title": title,
                        "price": parse_price(title),
                        "url": link_el.get("href") if link_el is not None else "",
                        "source": "r/watchexchange",
                    })
            except Exception as e:
                resp = getattr(e, "response", None)
                detail = f" | {describe_response(resp)}" if resp is not None else ""
                log(f"WARN: Reddit search failed for '{term}': {e}{detail}")
                RUN_ERRORS.append(f"Reddit '{term}': {e}")
    return out


def search_ebay(registry):
    """eBay newly-listed search results (HTML scrape — usually works w/o JS).

    Relevance is scoped per registry entry: a listing is kept if it matches the
    search-term entry's own relevance_required_all groups.
    """
    out = []
    seen_ids = set()
    for entry in registry:
        groups = entry.get("relevance_required_all", [])
        for term in entry.get("search_terms", []):
            url = ("https://www.ebay.com/sch/i.html"
                   f"?_nkw={requests.utils.quote(term)}&_sop=10&LH_BIN=1")
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
                if not r.ok:
                    detail = describe_response(r)
                    log(f"WARN: eBay search failed for '{term}': {detail}")
                    RUN_ERRORS.append(f"eBay '{term}': HTTP {r.status_code}")
                    time.sleep(1)
                    continue
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
                    full_id = f"ebay:{item_id}"
                    if full_id in seen_ids:
                        continue
                    seen_ids.add(full_id)
                    out.append({
                        "id": full_id,
                        "title": title,
                        "price": parse_price(price_el.get_text() if price_el else ""),
                        "url": link,
                        "source": "eBay",
                    })
            except Exception as e:
                resp = getattr(e, "response", None)
                if resp is not None:
                    log(f"WARN: eBay search failed for '{term}': {e} | {describe_response(resp)}")
                else:
                    log(f"WARN: eBay search failed for '{term}': {e}")
                RUN_ERRORS.append(f"eBay '{term}': {e}")
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
                detail = describe_response(r)
                log(f"WARN: Chrono24 blocked/non-200 for {url}: {detail}")
                RUN_ERRORS.append(f"Chrono24 blocked/non-200 ({r.status_code}): {url}")
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
            resp = getattr(e, "response", None)
            if resp is not None:
                log(f"WARN: Chrono24 fetch failed for {url}: {e} | {describe_response(resp)}")
            else:
                log(f"WARN: Chrono24 fetch failed for {url}: {e}")
            RUN_ERRORS.append(f"Chrono24 fetch failed: {e}")
        time.sleep(1)
    return out


# -------------------------------------------------------------------- PUSH ---
def push_ntfy(item):
    price = f"${item['price']}" if item.get("price") else "price?"
    prefs = item.get("preferred_signals", [])
    under_ceiling = bool(item.get("is_hot"))

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


def notify_failure(errors):
    """Fire ONE ntfy alert summarizing source failures so a broken run isn't silent."""
    body = "\n".join(errors[:10])
    if len(errors) > 10:
        body += f"\n…and {len(errors) - 10} more"
    headers = {
        "Title": f"⚠️ Watch monitor: {len(errors)} source error(s)".encode("utf-8"),
        "Tags": "warning",
        "Priority": "high",
    }
    try:
        r = requests.post(f"{NTFY_SERVER}/{NTFY_TOPIC}", data=body.encode("utf-8"),
                          headers=headers, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        log(f"ERROR: failure-alert ntfy push failed: {e}")


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
        "is_hot": True,
        "preferred_signals": ["40mm"],
    }
    ok = push_ntfy(sample)
    push_telegram(sample)
    log("Test push sent — check your phone." if ok else "Test push FAILED — see error above.")
    sys.exit(0 if ok else 1)


# LLM fallback model for prices the regex can't read (markdown-wrapped numbers,
# unusual phrasing, multi-watch posts). Sonnet 4.6 balances cost and accuracy for
# this simple extraction; override with PRICE_LLM_MODEL (e.g. claude-haiku-4-5 to
# save more, claude-opus-4-8 for the strongest model).
PRICE_LLM_MODEL = os.getenv("PRICE_LLM_MODEL", "claude-sonnet-4-6")


def extract_price_llm(comment_text, title=None):
    """Last-resort price extraction via Claude when parse_price() can't read a comment.

    Only fires when ANTHROPIC_API_KEY is set and the text actually contains a digit
    (so "Messaging"-type comments cost nothing). Best-effort: a missing key, missing
    SDK, or any API error returns None — same contract as the regex path. The model's
    answer is validated back through _to_price, so a hallucinated/implausible number
    is rejected rather than trusted.
    """
    if not os.getenv("ANTHROPIC_API_KEY") or not comment_text or not re.search(r"\d", comment_text):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    ctx = f"Listing title: {title}\n\n" if title else ""
    prompt = (
        f"{ctx}A seller posted the comment below on r/watchexchange. Extract the "
        f"seller's asking price in USD for the watch being sold. Reply with ONLY the "
        f"whole-dollar integer (no $, no commas), or the word NONE if no price is "
        f"stated.\n\nComment:\n{comment_text}"
    )
    try:
        resp = anthropic.Anthropic().messages.create(
            model=PRICE_LLM_MODEL,
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
        out = "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as e:
        log(f"WARN: LLM price extraction failed: {e}")
        return None
    m = re.search(r"\d[\d,]*", out)
    return _to_price(m.group(0)) if m else None


def fetch_op_price(post_url, title=None):
    """Best-effort: return the asking price from the OP's comment on a thread, or None.

    On r/watchexchange the price is usually in the seller's (OP's) own comment, which
    the search RSS feed never exposes. old.reddit server-renders the full comment tree
    and tags OP comments with the 'submitter' class, so we fetch the thread there and
    parse the price from the OP's comment. Any failure returns None — the listing still
    links through, so a miss just leaves the price blank (not a hard error).

    The cheap regex (parse_price) is tried first on every OP comment; only if it finds
    nothing do we fall back to extract_price_llm on the most likely OP comment, for
    prices the regex can't read (e.g. markdown-wrapped "**2700**", odd phrasing).
    """
    if not post_url:
        return None
    old_url = re.sub(r"^https?://(www\.)?reddit\.com", "https://old.reddit.com", post_url)
    try:
        r = requests.get(old_url, headers={"User-Agent": BROWSER_UA}, timeout=HTTP_TIMEOUT)
        if r.status_code == 429:
            # Transient rate-limit (a price-less batch fires several of these back to
            # back): wait out the reset and retry once, mirroring _get_reddit_rss. A
            # 403 is a hard IP block (datacenter), so it is NOT retried — only 429.
            try:
                wait = min(int(r.headers.get("x-ratelimit-reset", "5")) + 1, 65)
            except ValueError:
                wait = 5
            log(f"INFO: OP-price rate-limited for {post_url}; waiting {wait}s then retrying.")
            time.sleep(wait)
            r = requests.get(old_url, headers={"User-Agent": BROWSER_UA}, timeout=HTTP_TIMEOUT)
        if not r.ok:
            log(f"WARN: OP-price fetch failed for {post_url}: {describe_response(r)}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        best = ""  # longest digit-bearing OP comment, kept for the LLM fallback
        for c in soup.select(".commentarea div.comment"):
            if c.select_one("a.author.submitter"):           # comment authored by the OP
                body = c.select_one(".entry .usertext-body")
                if not body:
                    continue
                text = body.get_text(" ", strip=True)
                price = parse_price(text, loose=True)
                if price is not None:
                    return price
                if re.search(r"\d", text) and len(text) > len(best):
                    best = text
        if best:                                             # regex struck out — ask Claude
            return extract_price_llm(best, title)
    except Exception as e:
        log(f"WARN: OP-price fetch error for {post_url}: {e}")
    return None


def enrich_reddit_prices(items):
    """Fill in missing prices for Reddit listings from the OP's price comment.

    Runs only for price-less r/watchexchange items (the minority), one extra
    old.reddit fetch each with a politeness delay. Best-effort: a miss leaves the
    price None and the listing still links through.
    """
    for it in items:
        if it.get("price") is None and it.get("source") == "r/watchexchange":
            it["price"] = fetch_op_price(it["url"], it.get("title"))
            time.sleep(1)


PRICE_BACKFILL_MAX_ATTEMPTS = 5
PRICE_GAVE_UP = -1  # deals.json sentinel: retried MAX_ATTEMPTS times, never found a price


def backfill_prices():
    """Retry OP-comment price recovery for already-saved price-less Reddit deals.

    The RSS feed indexes a post at submission, but the seller posts the price in a
    comment moments later — so a deal first seen in that gap is saved with price
    None. Without this, dedup means it's never revisited and the blank is permanent.
    Re-fetch those here, up to PRICE_BACKFILL_MAX_ATTEMPTS times; on the final miss,
    flag price = PRICE_GAVE_UP (-1) so a persistent blank is visible in the web app
    instead of an indistinguishable null.
    """
    if not DEALS_FILE.exists():
        return
    try:
        deals = json.loads(DEALS_FILE.read_text())
    except Exception as e:
        log(f"WARN: could not read deals file for backfill ({e}).")
        return
    changed = False
    for d in deals:
        if d.get("source") != "r/watchexchange" or d.get("price") is not None:
            continue
        attempts = d.get("price_attempts", 0) + 1
        d["price_attempts"] = attempts
        price = fetch_op_price(d.get("url"), d.get("title"))
        if price is not None:
            d["price"] = price
            log(f"  backfilled price ${price} for {d['id']} (attempt {attempts})")
        elif attempts >= PRICE_BACKFILL_MAX_ATTEMPTS:
            d["price"] = PRICE_GAVE_UP
            log(f"  gave up on price for {d['id']} after {attempts} attempts; flagged {PRICE_GAVE_UP}")
        changed = True
        time.sleep(1)
    if changed:
        DEALS_FILE.write_text(json.dumps(deals, indent=2))


def gather_listings(registry):
    """Run each ENABLED source and return the combined raw listings.

    Sources are toggled via the ENABLE_* config flags so a blocked source
    (e.g. eBay/Chrono24 anti-bot) can be turned off without code surgery.
    """
    enabled = [n for n, on in (("reddit", ENABLE_REDDIT),
                               ("eBay", ENABLE_EBAY),
                               ("Chrono24", ENABLE_CHRONO24)) if on]
    log(f"Sources enabled: {', '.join(enabled) if enabled else 'none'}")

    found = []
    if ENABLE_REDDIT:
        found.extend(search_reddit(registry))
    if ENABLE_EBAY:
        found.extend(search_ebay(registry))
    if ENABLE_CHRONO24:
        found.extend(search_chrono24())
    return found


def main():
    if "--test" in sys.argv:
        run_test_push()

    if "REPLACE-ME" in NTFY_TOPIC:
        log("ERROR: set NTFY_TOPIC (top of file or env var) to your own unique topic first.")
        sys.exit(1)

    RUN_ERRORS.clear()
    seen = load_state()
    first_run = not STATE_FILE.exists()
    registry = load_registry()

    found = gather_listings(registry)

    # Dedup within this run and against history
    unique = {}
    for it in found:
        unique[it["id"]] = it
    new_items = [it for it in unique.values() if it["id"] not in seen]

    log(f"Scanned {len(unique)} listings, {len(new_items)} new "
        f"(first_run={first_run}).")

    if RUN_ERRORS:
        log(f"{len(RUN_ERRORS)} source error(s) this run; sending failure alert.")
        notify_failure(RUN_ERRORS)

    if first_run:
        # Seed baseline silently so we don't blast every existing listing.
        save_state(set(unique.keys()))
        log("First run: baseline saved, no notifications sent. "
            "Future runs will alert on genuinely new listings.")
        return

    # Recover missing prices from the OP's price comment (new Reddit items only),
    # then sort cheapest-first so recovered prices affect ordering and the push cap.
    enrich_reddit_prices(new_items)
    new_items.sort(key=lambda x: (x.get("price") is None, x.get("price") or 0))

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

    # Retry price recovery for stored Reddit deals whose price was blank when first
    # seen (the RSS feed often indexes a post before the OP posts the price comment).
    backfill_prices()

    # Remember everything we saw (even un-pushed overflow) to avoid re-alerting.
    seen.update(unique.keys())
    save_state(seen)
    log(f"Done. {pushed} notification(s) sent.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # config-error / --test exits are intentional, not crashes
    except Exception as e:
        log(f"FATAL: monitor crashed: {e}")
        notify_failure([f"Monitor crashed: {e}"])
        raise  # re-raise so the GitHub Actions job also shows red
