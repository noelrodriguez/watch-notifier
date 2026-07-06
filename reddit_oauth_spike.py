#!/usr/bin/env python3
"""THROWAWAY validation spike — do not commit / ship as-is.

Question it answers: does Reddit OAuth (script-app password grant) give us stable
access to comment threads + prices?  Reads creds from env, gets a token, fetches a
few real comment threads via oauth.reddit.com, and extracts the OP's asking price
with the SAME parse_price() the monitor already uses.

Run LOCALLY (residential IP): proves creds + OAuth API + price parsing work.
It does NOT prove the datacenter-403 bypass — that needs a run ON GitHub Actions.

Required env vars:
  REDDIT_CLIENT_ID  REDDIT_CLIENT_SECRET  REDDIT_USERNAME  REDDIT_PASSWORD
Optional:
  REDDIT_USER_AGENT   (a sensible default is used)

Usage:
  python3 reddit_oauth_spike.py                # auto-picks recent posts from deals.json
  python3 reddit_oauth_spike.py <post_id> ...  # test specific article ids
"""
import os
import sys
import json
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from watch_monitor import parse_price

CID = os.getenv("REDDIT_CLIENT_ID")
CSECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER = os.getenv("REDDIT_USERNAME")
PW = os.getenv("REDDIT_PASSWORD")
UA = os.getenv("REDDIT_USER_AGENT",
               f"python:watch-notifier-spike:0.1 (by /u/{USER or 'unknown'})")

_missing = [n for n, v in [("REDDIT_CLIENT_ID", CID), ("REDDIT_CLIENT_SECRET", CSECRET),
                           ("REDDIT_USERNAME", USER), ("REDDIT_PASSWORD", PW)] if not v]
if _missing:
    print("MISSING env vars: " + ", ".join(_missing))
    print("Set them, then re-run.  (See the docstring.)")
    sys.exit(2)


def get_token():
    r = requests.post("https://www.reddit.com/api/v1/access_token",
                      auth=(CID, CSECRET),
                      data={"grant_type": "password", "username": USER, "password": PW},
                      headers={"User-Agent": UA}, timeout=20)
    print(f"[token] POST access_token -> HTTP {r.status_code}")
    if not r.ok:
        print(f"[token] FAILED: {r.text[:300]}")
        return None
    tok = r.json()
    if "access_token" not in tok:
        # Common cause: 2FA on the account, or account not a developer on the app.
        print(f"[token] no access_token in response: {tok}")
        return None
    print(f"[token] OK — scope={tok.get('scope')} expires_in={tok.get('expires_in')}s")
    return tok["access_token"]


def op_price(token, article_id):
    """Fetch a thread's comments via the OAuth API; return (price, how, ratelimit_remaining)."""
    url = f"https://oauth.reddit.com/comments/{article_id}?limit=100&depth=1&raw_json=1"
    r = requests.get(url, headers={"User-Agent": UA, "Authorization": f"bearer {token}"},
                     timeout=20)
    rl = r.headers.get("x-ratelimit-remaining")
    if not r.ok:
        return None, f"HTTP {r.status_code}", rl
    try:
        comments = r.json()[1]["data"]["children"]
    except (ValueError, IndexError, KeyError):
        return None, "bad-json", rl
    for c in comments:
        cd = c.get("data", {})
        if cd.get("is_submitter"):                     # API flags OP comments directly
            price = parse_price(cd.get("body", ""), loose=True)
            if price is not None:
                return price, "op-comment", rl
    return None, "no-op-price", rl


def load_test_ids():
    """Pick recent real reddit posts (with known prices) from deals.json as ground truth."""
    dj = Path(__file__).parent / "data" / "deals.json"
    if not dj.exists():
        return []
    out = []
    for d in json.loads(dj.read_text()):
        rid = str(d.get("id", ""))
        if not rid.startswith("reddit:") or "test" in rid:
            continue
        if isinstance(d.get("price"), int) and d["price"] > 0:
            out.append((rid.split(":", 1)[1], d["price"], d.get("title", "")[:45]))
    return out[-5:]                                     # most-recent 5 (threads still alive)


def main():
    token = get_token()
    if not token:
        sys.exit(1)
    if len(sys.argv) > 1:
        tests = [(a, None, "") for a in sys.argv[1:]]
    else:
        tests = load_test_ids()
    if not tests:
        print("No test posts found (pass article ids as args).")
        sys.exit(1)

    print(f"\nFetching {len(tests)} thread(s) via oauth.reddit.com:\n")
    ok = 0
    for art, known, title in tests:
        price, how, rl = op_price(token, art)
        if known is None:
            match = ""
        elif price == known:
            match = " OK match"
        else:
            match = f" != known ${known}"
        print(f"  {art}: price={price} ({how}) ratelimit_remaining={rl}{match}  {title}")
        if price is not None:
            ok += 1

    print(f"\nRecovered {ok}/{len(tests)} prices via the OAuth comment API.")
    if ok:
        print("PASS (local) — creds + OAuth comment API + price parsing all work.")
        print("Next: run this same script FROM a GitHub Actions runner to settle the 403 question.")
    else:
        print("CHECK — token worked but no prices came back; inspect a thread manually.")


if __name__ == "__main__":
    main()
