# Watch Tracker — Handoff Summary

**Purpose:** Everything needed to pick this project up on a different (always-on) PC and continue exactly where we left off.
**Last session:** 2026-06-13 (evening)
**Owner:** Noel — noel.rodriguez.shopping@gmail.com

---

## 1. TL;DR — current status

- **Goal:** Monitor secondary watch markets and get phone alerts for good deals, starting with the **Longines Master Collection Chrono Moonphase, 40mm**.
- **Built & working:** A standalone Python monitor (`watch_monitor.py`) that scans **r/watchexchange + eBay (+ Chrono24 best-effort)** hourly and pushes new listings to the phone via **ntfy.sh** (free, no account).
- **Why a script instead of the built-in scheduler:** The in-app scheduled-task → iPhone push (via Dispatch) **never delivered to the phone** despite 8 tests. Desktop notifications worked; iPhone never did. Also, the original Mac is often closed, so in-app scheduling couldn't run reliably. We pivoted to a self-hosted script on an always-on PC.
- **Remaining to do (on the new PC):** Install Python deps, set an ntfy topic, run `--test`, seed baseline, schedule hourly in Task Scheduler. ~5 minutes. Details in §6 and `README.md`.
- **Explicitly declined:** Headless-browser (Playwright) Chrono24 upgrade — not wanted for now.

---

## 2. Project objective (from project instructions)

Build a system that monitors key secondary markets for buying watches. Determine the best ~10+ places to buy second-hand watches, then run an agent that pulls listings roughly hourly so Noel sees the latest deals. First feature: type in a brand / model / reference and get current listings ranked by best deal. Over time, **track every watch Noel requests** to learn his style and preferred sizes, and refine searches accordingly. Ask clarifying questions when useful.

---

## 3. Watch target + learned preferences

**Active target:**

| Field | Value |
|---|---|
| Brand / model | Longines Master Collection **Chrono Moonphase** (complete calendar: day/date/month/moonphase + chronograph) |
| Size | **40mm** (the 42mm version is the L2.773.4.x family — not the target) |
| 40mm references | **L2.673.4.78.6** (silver dial, **steel bracelet — PREFERRED**), L2.673.4.78.3 (silver, leather), L2.673.4.61.6 (anthracite), L2.673.4.71.2 (ivory), L2.673.4.92.0 (blue) |
| Retail (new) | ~$3,325 USD |
| Specific ask this session | The **.78.6** with **box & papers** |
| Price alert threshold | Flag anything **≤ $2,000** as a hot deal |

**Inferred style signals so far (only one watch requested — low confidence):** dress / complicated, steel bracelet preference, 40mm. Logged in `requested_watches.md` and `seen_listings.json`. Add more watches to sharpen this.

---

## 4. Deal findings snapshot (as of 2026-06-13 — prices go stale fast)

**Best secondary markets identified for second-hand watches:** Chrono24, eBay, r/watchexchange (via WatchRecon aggregator), WatchUSeek forums, Jomashop, WatchBox/Bezel, WatchMaxx, DelrayWatch, Bob's Watches, Crown & Caliber, Hodinkee Shop, plus brand-authorized pre-owned.

**Live listings found for the .78.6 (Chrono24, with box & papers):**

| Price (delivered) | Box & papers | Location | Note |
|---|---|---|---|
| ~$2,486 | Yes ("Full set") | HK | Cheapest verified full set, free shipping |
| ~$2,444 + ship | Yes ("Full Set 2021") | CH | |
| ~$2,800 | Yes ("rarely worn") | **US** | Cheapest US-based full set |
| $1,837 | Ambiguous | — | Cheapest .78.6 but documentation unconfirmed |

**r/watchexchange + forums (materially cheaper — private sales, no dealer margin):**

| Price | Listing | Source |
|---|---|---|
| $1,590 | Triple Date Moonphase 40mm | r/watchexchange |
| $1,749 | Full Calendar Chrono 40mm (US) | WatchUSeek |
| $1,750 | Triple Calendar Moonphase, steel bracelet (newest) | r/watchexchange |
| $1,900–$2,250 | Several more moonphase variants | r/watchexchange |

**Takeaway given to Noel:** r/watchexchange undercuts Chrono24 by ~$400–$900; tradeoff is no escrow/Buyer Protection (vet seller via Reddit feedback, pay PayPal G&S). Noel said he already knows the current specific deals — so the value now is *forward monitoring*, not re-listing these.

---

## 5. The monitoring system — architecture & files

**How it works:** Run once per invocation → scan sources → dedupe against `monitor_state.json` → push only genuinely-new listings to ntfy → phone. Schedule hourly with Task Scheduler.

**Sources & reliability:**

| Source | Method | Reliability |
|---|---|---|
| r/watchexchange | Reddit public `search.json` endpoint | High (works from Noel's PC; was only blocked on Claude's side) |
| eBay | HTML scrape of newly-listed search | Usually works (no JS needed) |
| Chrono24 | Best-effort HTML fetch of ref pages | Spotty — bot-blocked often; skips silently if blocked |

**Files in this folder (`Watch-Tracker/`):**

| File | What it is |
|---|---|
| `watch_monitor.py` | The monitor. Config knobs at top. `--test` flag fires a sample push. First run seeds baseline silently. |
| `requirements.txt` | `requests`, `beautifulsoup4` |
| `README.md` | Full setup + Windows Task Scheduler instructions |
| `requested_watches.md` | Log of watches Noel has asked about + inferred preferences |
| `seen_listings.json` | Baseline of listings already surfaced (manual notes from this session) |
| `monitor_state.json` | **Auto-created by the script** on first run — dedup memory. Not present yet. |
| `HANDOFF_SUMMARY.md` | This file |

**Verified this session:** price parsing, relevance filter, dedup logic (unit tests pass), syntax clean, `--test` guard works. **Not yet verified:** a live ntfy push (sandbox blocks outbound HTTP) — this is the first thing to confirm on the new PC via `--test`.

---

## 6. Exact next steps on the new (always-on) PC

1. Copy the whole `Watch-Tracker` folder to the new PC (or sync it).
2. Install Python 3.9+ if needed (`python --version`).
3. In the folder: `pip install -r requirements.txt`
4. Install the **ntfy** app on the iPhone (App Store).
5. Pick a unique topic (e.g. `watchtracker-noel-7h3x9q`); **Subscribe** to it in the ntfy app.
6. Set that topic in `watch_monitor.py` → `NTFY_TOPIC` (or env var).
7. `python watch_monitor.py --test` → confirm the phone gets the push. **This is the real validation we couldn't do in-session.**
8. `python watch_monitor.py` once → seeds the silent baseline (`First run: baseline saved`).
9. Task Scheduler → Basic Task → program `python`, args `watch_monitor.py`, "Start in" = folder path → then edit trigger to **Repeat every 1 hour, indefinitely**, and tick **"Run task as soon as possible after a missed start."**

Done = phone push on every new listing, cheapest first, 🔥 high-priority for ≤ $2,000.

---

## 7. Decision log (so context isn't lost)

- **In-app scheduled tasks fire correctly** (confirmed via `lastRunAt` on 8 test tasks) and notify the **desktop** — but the **iPhone push via Dispatch never arrived**, even after mobile re-login and toggling permissions. Root cause unconfirmed; likely a Dispatch (research-preview) delivery issue or account/permission mismatch. Not fixable from inside the session. Left as a possible Anthropic support item if Noel wants in-app phone alerts later.
- **Chose ntfy.sh** over email→SMS (T-Mobile gateway), Twilio (paid), and Telegram — because it's free, zero-account, and more reliable than the push path that failed. Telegram mirror is supported in the script if ever wanted (env vars).
- **Declined:** headless-browser Chrono24 (Playwright). Revisit only if Chrono24 coverage proves too spotty.
- The 8 one-time test scheduled tasks (`watch-tracker-push-test*`) auto-disabled after firing; can be deleted from the Scheduled sidebar.

---

## 8. Open items / good next moves

- [ ] Run the new-PC setup (§6) and confirm `--test` push.
- [ ] Add more watches Noel is hunting → improves the learned style/size profile and expands `SEARCH_TERMS`.
- [ ] Optional: widen the monitor beyond Longines to other brands/models.
- [ ] Optional: add WatchUSeek/WatchRecon as additional scraped sources.
- [ ] Optional: revisit headless-browser Chrono24 if its coverage is too thin.
