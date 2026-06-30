# Watch Tracker — Handoff Summary

**Purpose:** Everything needed to pick this project up and continue exactly where we left off.
**Last session:** 2026-06-29
**Owner:** Noel — noel.rodriguez.shopping@gmail.com

---

## 1. TL;DR — current status

- **Goal:** Monitor secondary watch markets and get phone alerts for good deals, starting with the **Longines Master Collection Chrono Moonphase, 40mm**.
- **Built & working:** A Python monitor (`watch_monitor.py`) that runs **hourly on GitHub Actions** (`.github/workflows/monitor.yml`), scans **r/watchexchange via its RSS feed**, tags each listing with brand/model/price (recovering the price from the seller's comment when it's not in the title), dedupes, and pushes new finds to the phone via **ntfy.sh** (free, no account). A **Flask web app** (`webapp/flask/`) browses saved deals (`data/deals.json`) and manages the watch registry.
- **Deployment:** Live on GitHub Actions (hourly; `NTFY_TOPIC` etc. in repo secrets). Can also be run locally — `./run_now.sh` for a one-off scan, `./install_cron.sh` for an hourly local cron. A failed source now fires a single ntfy alert instead of failing silently.
- **Source status (important):** Reddit's anonymous JSON API is **403-blocked** (their Nov-2025 policy) — we switched to the **RSS feed**, which is rate-limited (~1 req/min/IP). **eBay** (Akamai bot-wall) and **Chrono24** (anti-bot) are **403'd and disabled by default** via `ENABLE_EBAY` / `ENABLE_CHRONO24` toggles. Official Reddit OAuth needs an approval Noel expects to fail.
- **⚠️ THE big known limitation (discovered 2026-06-29):** the RSS feed indexes a post at *submission*, but the seller posts the price in a *comment* moments later — and **old.reddit comment pages return HTTP 403 ("blocked due to a network policy") to GitHub Actions' datacenter IP**. So the hourly Action discovers deals fine but **cannot recover their prices** — they save `price: null`. Price recovery works only from a **residential IP** (i.e. running locally). See §6 and §8.
- **Price recovery is two-layered:** a regex (`parse_price`) handles the common `$3,399` / `asking 1750` / `1750 shipped` formats; when it can't read a comment (e.g. markdown-wrapped `**2700**`, odd phrasing), a **Claude fallback** (`extract_price_llm`, default model `claude-sonnet-4-6`) extracts it. Both run inside `fetch_op_price`, so both are subject to the same 403 (local-only).
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

**How it works:** Run once per invocation → scan sources → dedupe against `data/monitor_state.json` → push only genuinely-new listings to ntfy → phone. Schedule hourly with Task Scheduler.

**Sources & reliability:**

| Source | Method | Status |
|---|---|---|
| r/watchexchange (discovery) | Reddit **RSS search feed** (`search.rss`) | **Working everywhere.** Anonymous JSON API is 403-blocked, so RSS is the only free path; rate-limited ~1 req/min/IP (429-retry in `_get_reddit_rss` handles it). |
| r/watchexchange (price recovery) | `fetch_op_price` fetches the thread on **old.reddit**, reads the OP (`submitter`) comment, runs `parse_price` (regex) then the Claude fallback | **Local-only.** Works from a residential IP; **403-blocked from GitHub Actions' datacenter IP** ("snooserv" anti-bot). `fetch_op_price` retries once on 429 but does NOT retry 403 (hard block). |
| eBay | HTML scrape of newly-listed search | **Disabled** (`ENABLE_EBAY=0`). Akamai bot-wall returns 403. |
| Chrono24 | Best-effort HTML fetch of ref pages | **Disabled** (`ENABLE_CHRONO24=0`). Anti-bot blocked. |

**Price handling details (current):**
- New price-less Reddit deals are enriched at scan time (`enrich_reddit_prices`). Deals still missing a price are retried each run by `backfill_prices()` — up to **5 attempts** (`price_attempts` counter on each deal), then flagged **`price = -1`** as a permanent "gave up" sentinel so a stuck deal is visible instead of silently null. The web app renders `-1` as **"⚠ no price"** (distinct color, `.price-missing`).
- `extract_price_llm` is gated: only fires if `ANTHROPIC_API_KEY` is set **and** the comment contains a digit (so "Messaging" costs nothing); the model's answer is validated back through `_to_price` (100–100000). Model overridable via `PRICE_LLM_MODEL` env (default `claude-sonnet-4-6`; `claude-haiku-4-5` to save, `claude-opus-4-8` for strongest). Uses the official `anthropic` SDK. Any missing key / SDK / API error → `None` (best-effort).

**Files in this folder (`Watch-Tracker/`):**

| File | What it is |
|---|---|
| `watch_monitor.py` | The monitor. Config knobs at top (incl. `ENABLE_*` toggles, `PRICE_LLM_MODEL`). `--test` fires a sample push. First run seeds baseline silently. Key funcs: `search_reddit`, `fetch_op_price`, `extract_price_llm`, `enrich_reddit_prices`, `backfill_prices`, `parse_price`, `tag_deal`. |
| `requirements.txt` | `requests`, `beautifulsoup4`, `anthropic` (+ flask/streamlit/pandas/pytest) |
| `.github/workflows/monitor.yml` | Hourly GitHub Actions run; commits `data/` state back to the repo |
| `run_now.sh` / `install_cron.sh` | Local one-off scan / install an hourly local cron |
| `webapp/flask/` | Flask web app — browse deals (clickable column sort, **hide/show columns** persisted in localStorage, **delete a deal**) + manage the watch registry. Local-only `/api/status` + `/api/push` git plumbing covers both `watches.json` and `deals.json`. |
| `data/watches.json` | The watch registry (search terms, relevance groups, refs, price ceiling) |
| `data/monitor_state.json` | Dedup memory — committed by the Action each run |
| `data/deals.json` | Deal history (price + brand/model enriched) — committed by the Action |
| `.claude/skills/` | Project skills: `deliver-feature`, `create-pr` (+ user-level `pr-merged`) |
| `CLAUDE.md` | Project rules: Karpathy LLM-coding guidelines + branch/PR workflow |
| `requested_watches.md` | Log of watches Noel has asked about + inferred preferences |
| `HANDOFF_SUMMARY.md` | This file |

**Verified working in production:** the hourly Action discovers and saves real deals; brand/model populated (0 missing). **Prices on Action-discovered deals are recovered only on a later *local* run** (see the 403 limitation). The web app sort/filter, column hide/show, deal delete, and registry CRUD all work. Test suite: `python3 -m pytest tests/ webapp/flask/tests/ -q` (**96 passing** as of 2026-06-29).

---

## 6. Running it

**Primary (already deployed):** GitHub Actions runs `watch_monitor.py` hourly via `.github/workflows/monitor.yml` and commits the updated `data/` state back to the repo. Secrets (`NTFY_TOPIC`, optional `TELEGRAM_*`) live in **Settings → Secrets and variables → Actions**. Trigger manually from the **Actions** tab → "Run workflow".

**Local (optional):**
1. `pip install -r requirements.txt`
2. Install the **ntfy** app on the iPhone and **Subscribe** to the topic in `NTFY_TOPIC`.
3. `./run_now.sh --test` → confirm the phone gets the push.
4. `./run_now.sh` → one-off scan (first run seeds the silent baseline).
5. `./install_cron.sh` → installs an hourly local cron (logs to `data/cron.log`). macOS may prompt for Full Disk Access for cron.

**Web app:** `webapp/start.sh` (Flask on `127.0.0.1:5000`*, Streamlit on `:8501`). *Bind `127.0.0.1`, not `localhost` — macOS AirPlay grabs port 5000 on IPv6.

**Recovering prices (must be local — Action can't, see §1/§8):** run `./run_now.sh` on Noel's machine; its residential IP can read old.reddit comments. `backfill_prices()` re-fetches every price-less stored deal. To enable the Claude fallback for hard-to-parse comments, set `ANTHROPIC_API_KEY` first:
- One-off: `ANTHROPIC_API_KEY=sk-ant-... ./run_now.sh`
- Persistent: `export ANTHROPIC_API_KEY=sk-ant-...` in `~/.zshrc` (key from console.anthropic.com — a billing API key, separate from the Claude Code subscription). Cron won't see `~/.zshrc`, so export it inside `run_now.sh` if you want the fallback under cron. **Setting the key as a GitHub Actions secret is pointless** — the Action is 403-blocked from the comment fetch, so the fallback is never reached there.
- After a local run recovers prices, push `data/deals.json` (branch + PR per `CLAUDE.md`, or via the web app's push banner) so the recovered prices persist before the next Action run overwrites state.

**Adding a watch (web app / `POST /api/watches`):** required fields are `brand`, `model`, `size_mm`, and **at least one ref with a non-empty `ref`** (dial & strap are optional as of #17). Brand+model slug must be unique (else 409). No type/range validation on `size_mm`/`price_ceiling` yet.

Result = phone push on every new listing, cheapest first, 🔥 high-priority under the watch's price ceiling.

---

## 7. Decision log (so context isn't lost)

- **In-app scheduled tasks fire correctly** (confirmed via `lastRunAt` on 8 test tasks) and notify the **desktop** — but the **iPhone push via Dispatch never arrived**, even after mobile re-login and toggling permissions. Root cause unconfirmed; likely a Dispatch (research-preview) delivery issue or account/permission mismatch. Not fixable from inside the session. Left as a possible Anthropic support item if Noel wants in-app phone alerts later.
- **Chose ntfy.sh** over email→SMS (T-Mobile gateway), Twilio (paid), and Telegram — because it's free, zero-account, and more reliable than the push path that failed. Telegram mirror is supported in the script if ever wanted (env vars).
- **Declined:** headless-browser Chrono24 (Playwright). Revisit only if Chrono24 coverage proves too spotty.
- The 8 one-time test scheduled tasks (`watch-tracker-push-test*`) auto-disabled after firing; can be deleted from the Scheduled sidebar.

---

## 8. Open items / good next moves

- [ ] **🔑 Prices on Action-discovered deals (the biggest gap).** The hourly Action is 403-blocked from old.reddit comment pages, so it can't recover prices — only a later local run can. Options to make it automatic: (a) run price recovery on a **local cron** (residential IP) and push `deals.json`; (b) route the Action's comment fetch through a **residential/rotating proxy**; (c) official Reddit OAuth (gated, Noel expects rejection). Until one is done, **remember to run `./run_now.sh` locally to fill in prices.**
- [ ] **eBay rebuild** — replace the Akamai-blocked HTML scrape with eBay's official **Browse API** (free, needs a dev key), then re-enable `ENABLE_EBAY`. Good `deliver-feature` candidate.
- [ ] Small tidy: gitignore `.claude/launch.json` alongside the existing `.claude/settings.local.json` + `.claude/worktrees/` entries.
- [ ] Stale merged branches: ~18 old feature branches remain locally (Noel said leave them 2026-06-29). Prune with `git branch -d` when wanted.
- [ ] `chrono24:test3` is seeded **test data** in `data/deals.json` (fake URL, will never get a price). Delete it if a truly-0-missing dataset is wanted.
- [ ] Add more watches Noel is hunting → improves the learned style/size profile (`data/watches.json`, or the web UI's Watches tab).
- [ ] Optional: widen beyond Longines to other brands/models.
- [ ] Optional: add WatchUSeek/WatchRecon as additional sources.
- [ ] Optional hardening: input type/range validation on the watch-add form (`size_mm`, `price_ceiling`).

---

## 9. Session log — 2026-06-24

Shipped via branch + PR (per `CLAUDE.md`), merged #3–#15:
- **Reddit 403 fix:** anonymous JSON API is dead → switched `search_reddit` to the RSS feed with a 429-retry (#6).
- **Prices:** recover the seller's price from the OP's comment via old.reddit (#9); backfilled existing deals (#10); parse `$`-less prices like "Asking 3750" (#11).
- **Brand/model:** `tag_deal` matches via `relevance_required_all` groups, not just contiguous terms (#12); backfilled existing deals (#13). 0 deals now missing brand/model.
- **Reliability/UX:** single ntfy alert on source failure (#3); richer HTTP error logging (#5); per-source `ENABLE_*` toggles, eBay+Chrono24 off (#8); click-column-header sorting in the web app (#14).
- **Tooling:** local `run_now.sh` + `install_cron.sh` (#4); `CLAUDE.md` rules + Karpathy guidelines (#15); skills `deliver-feature` / `create-pr` / `pr-merged`; permission allowlist for PR commands.

---

## 10. Session log — 2026-06-29

Shipped via branch + PR (per `CLAUDE.md`), merged #17–#25:
- **Prices — root-caused the recurring "no price" problem.** Two causes found: (1) a *timing race* — the RSS feed indexes a post before the OP posts the price comment; the deal was saved null and dedup meant it was never revisited. Fixed with `backfill_prices()` retrying price-less deals each run, cap 5, then flag `-1` (#19; web app shows "⚠ no price"). (2) **old.reddit comment pages are 403-blocked from the GitHub Actions datacenter IP** (confirmed in the Action logs: "snooserv / blocked due to a network policy"). The regex/parser was never the problem — prices recover fine from a residential IP. Backfilled the stored deals from a local run (#20, #23).
- **`fetch_op_price` 429 retry (#24):** a price-less batch fires several old.reddit fetches back-to-back; transient 429s were causing false `-1` give-ups. Now retries once on 429 (waits `x-ratelimit-reset`); 403 is NOT retried (hard block).
- **Claude price fallback (#25):** when `parse_price` can't read a comment (e.g. markdown `**2700**`, "shipping" cue not adjacent), `extract_price_llm` asks Claude. Gated on `ANTHROPIC_API_KEY` + a digit present; validated via `_to_price`; `PRICE_LLM_MODEL` default `claude-sonnet-4-6`. Added `anthropic` to requirements. **Only reachable locally** (same 403 — the Action can't fetch the comment to feed the model).
- **Web app:** delete a deal via the UI, persisted through the existing push banner (`/api/status` + `/api/push` now cover `deals.json` too) (#21); hide/show table columns, persisted in `localStorage` (#22).
- **Watch registry:** adding a watch now requires only `ref` per ref-row — dial & strap optional (#17).
- **Process notes:** all work done via branch → PR → user merges (never direct to main). Parallel features (#21/#22) were built in isolated git worktrees under `.claude/worktrees/`; the `pr-merged` skill now also prunes merged worktrees/branches. Test suite grew 79 → 96.

**Memory files updated this session** (`~/.claude/.../memory/`): `project_source_access.md` now documents the old.reddit-comment-403-from-Actions finding.
