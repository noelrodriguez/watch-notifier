# Watch Tracker — Handoff Summary

**Purpose:** Everything needed to pick this project up and continue exactly where we left off.
**Last session:** 2026-07-05
**Owner:** Noel — noel.rodriguez.shopping@gmail.com

---

## 0. Latest (2026-07-05, session 2) — read this first

Reddit OAuth landed — the biggest change since this project began. It supersedes
several statements below (esp. "OAuth is DEAD" and "THE big known limitation" — those
are annotated inline).

- **🎯 Reddit OAuth shipped (PR #36) — closes the #1 open gap.** The monitor now uses a
  Reddit **script-app OAuth token** (password grant) for BOTH discovery and price
  recovery via `oauth.reddit.com`, which **works from GitHub Actions' datacenter IP** —
  bypassing the old.reddit 403. The hourly Action can now recover prices itself; the
  "must run locally to fill in prices" limitation is gone (once secrets are set). Bonus:
  ~100 req/min vs the RSS feed's ~1/min (kills the 429s).
  - **Nuance on "OAuth is dead":** self-serve app *registration* is still closed. What
    changed is Noel got credentials for a **pre-existing** script app (his brother's;
    Noel is a developer on it). You still can't create a new app — this only works
    because an old one exists.
  - **Fallback preserved:** with no `REDDIT_*` creds the monitor falls back to the
    anonymous RSS feed (discovery) + old.reddit HTML (prices, residential-only), so it
    keeps working either way.
  - **⚠️ ACTION REQUIRED to activate in the cloud:** add four repo secrets —
    `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`
    (Settings → Secrets and variables → Actions). Until then the Action uses the
    anonymous fallback (no cloud price recovery). Setup table: `docs/GITHUB_ACTIONS_SETUP.md` §1b.
  - **Validated** before building via a throwaway spike (PR #35, since deleted): token
    grant + comment fetch confirmed from BOTH residential and datacenter (Actions) IPs.
    Token TTL ~24h.
  - **Credential decision:** password grant, not a refresh token — refresh tokens need
    the auth-code flow / a web-app type that can't be created (registration closed), and
    script apps don't issue them. Password lives in CI secrets. Optional future
    mitigation: a dedicated throwaway Reddit account as developer, so the stored password
    isn't Noel's main account.
  - Key funcs: `reddit_token()` (lru_cache, per-run), `_search_reddit_oauth` /
    `_search_reddit_rss`, `_op_price_oauth` / `_op_price_html` — the dispatchers
    `search_reddit` / `fetch_op_price` pick OAuth when a token exists, else the anon path.

- **Price backfill bug fixed (PR #34).** Two compounding bugs left 8 deals stuck at
  `price: -1`: (1) `backfill_prices()` never retried `-1` ("gave up") deals — now it
  retries `None` AND `-1`; (2) Actions' 403s burned the 5-attempt budget into false
  `-1`s — the `GITHUB_ACTIONS` skip is now **conditional on NOT having an OAuth token**
  (with OAuth, Actions recovers fine; without it, still skip so the HTML 403 can't burn
  the budget). Recovered all 8 stuck prices; `data/deals.json` now 0 missing.

- **LLM price fallback moved to the `claude` CLI (PR #34).** `extract_price_llm` now
  shells `claude -p` (Claude Code **subscription**, no `ANTHROPIC_API_KEY` /
  pay-per-token). Dropped the `anthropic` package dep. Needs the `claude` CLI on the
  machine running recovery (present locally; degrades to None if missing).

- **Test suite: 113 passing** (was 98). New `tests/test_reddit_oauth.py` plus the
  `-1`-retry / CLI-fallback tests.

- **Deferred follow-up (task chip created):** multi-watch posts where `parse_price` picks
  the wrong price among several (e.g. post `1uod3c6` "Big Drop", stored $8500 vs actual
  $4175). Both price paths call `parse_price` on the OP comment; needs to anchor on the
  matched watch's ref/model. Explicitly scoped OUT of the OAuth PR.

---

## 0b. Latest (2026-07-05, session 1)

Key deltas since 2026-06-29 (older sections below may still say the old thing):

- **This doc moved** to `docs/HANDOFF_SUMMARY.md` (root tidy, PR #30). Root is now 11 tracked files; standalone docs live in `docs/`.
- **Monitor is Reddit-only now.** The first audit cleanup (PR #29) **deleted** the disabled `search_ebay`, `search_chrono24`, the `push_telegram` mirror, dead `REPLACE-ME` guards, and a duplicate `slugify`. Also **deleted the entire Streamlit UI** (`webapp/streamlit/`) — Flask is the only web app. Net −352 lines, −2 deps. Test suite is now **95 passing** (`watch_monitor.py` kept as a single file on purpose).
- **Flask Watches view + Add/Edit modal were polished** (PR #28) onto the "Midnight Desk" design system (they'd drifted). Deals view was already on-system.
- **🔑 Reddit OAuth is DEAD, not just gated.** Self-serve app creation at `reddit.com/prefs/apps` is **closed** ("You cannot create any more applications…"); the 2025 crackdown requires manual pre-approval for ALL new apps incl. hobby. Viable only if pre-cutoff app credentials already exist. Don't plan around "register a script app." — **UPDATE (session 2): those "pre-cutoff credentials already exist" (brother's app) and OAuth is now shipped and working. Registration is still closed, but OAuth itself is live. See §0.**
- **eBay rebuild is now greenfield** — the old HTML scrape is deleted, so a rebuild starts clean on eBay's official **Browse API**.
- **Two open decisions with a chosen direction (not yet built):**
  1. *Web app "reachable from anywhere":* chosen path = keep the app **running locally + expose via Cloudflare Tunnel** (public URL, full app). Needs **auth added** (currently none) and must **not** expose `/api/push`. **Gating question unanswered:** is the host an always-on/at-home machine (viable) or a daily-carry laptop (fragile — sleeps kill cron + site)?
  2. *Price-recovery 403 / hosting:* going **fully local collapses three problems at once** — a local cron replaces GitHub Actions, the residential IP fixes the price-recovery 403 (no proxy needed), and it serves the web app. Alternative if not local: route only the comment fetch through a **residential proxy / fetch-as-a-service** ("FetchLayer"), keeping free Actions hosting. Moving to another *cloud* does NOT help — the lever is exit-IP + auth, not the host.

---

## 1. TL;DR — current status

- **Goal:** Monitor secondary watch markets and get phone alerts for good deals, starting with the **Longines Master Collection Chrono Moonphase, 40mm**.
- **Built & working:** A Python monitor (`watch_monitor.py`) that runs **hourly on GitHub Actions** (`.github/workflows/monitor.yml`), scans **r/watchexchange via its RSS feed**, tags each listing with brand/model/price (recovering the price from the seller's comment when it's not in the title), dedupes, and pushes new finds to the phone via **ntfy.sh** (free, no account). A **Flask web app** (`webapp/flask/`) browses saved deals (`data/deals.json`) and manages the watch registry.
- **Deployment:** Live on GitHub Actions (hourly; `NTFY_TOPIC` etc. in repo secrets). Can also be run locally — `./run_now.sh` for a one-off scan, `./install_cron.sh` for an hourly local cron. A failed source now fires a single ntfy alert instead of failing silently.
- **Source status (important):** Reddit's anonymous JSON API is **403-blocked** (their Nov-2025 policy). **r/watchexchange is the only source** — eBay (Akamai) and Chrono24 (anti-bot) scrapers were **deleted** in the 2026-07-05 cleanup (see §0). **UPDATE (session 2): discovery now prefers authenticated OAuth (`oauth.reddit.com`) when `REDDIT_*` secrets are set, falling back to the RSS feed (~1 req/min/IP) otherwise. See §0.**
- **⚠️ THE big known limitation (discovered 2026-06-29) — NOW RESOLVED (session 2).** The RSS feed indexes a post at *submission*, but the seller posts the price in a *comment* moments later, and **old.reddit comment pages return HTTP 403 to GitHub Actions' datacenter IP** — so the Action historically couldn't recover prices (residential-only). **With Reddit OAuth (PR #36), price recovery goes through `oauth.reddit.com`, which works on Actions — the Action recovers prices itself once the `REDDIT_*` secrets are added.** Without the secrets, the old residential-only limitation still applies (RSS/HTML fallback). See §0.
- **Price recovery is two-layered:** a regex (`parse_price`) handles the common `$3,399` / `asking 1750` / `1750 shipped` formats; when it can't read a comment (e.g. markdown-wrapped `**2700**`, odd phrasing), an **LLM fallback** (`extract_price_llm`) extracts it. **UPDATE (session 2): the fallback now shells the local `claude` CLI (`claude -p`, subscription — no `ANTHROPIC_API_KEY`), and the whole path works on Actions via OAuth (no longer local-only).**
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

- [x] ~~**🔑 Prices on Action-discovered deals (the biggest gap).**~~ **RESOLVED (session 2, PR #36)** via Reddit OAuth — `oauth.reddit.com` works from Actions. **Remaining action: add the four `REDDIT_*` repo secrets to activate it in the cloud** (see §0). Until the secrets are set, the fallback still needs a local `./run_now.sh` for prices.
- [ ] **Multi-watch price parsing (new, deferred from PR #36).** `parse_price` picks the wrong price on posts selling several watches (e.g. `1uod3c6` "Big Drop": stored $8500 vs actual $4175). Anchor on the matched watch's ref/model in the OP comment. Task chip created this session.
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
