# watch-notifier

A secondary-market **watch tracker**. You define which watches to track — brand,
model, size, reference numbers, and a price ceiling — and it scans **r/watchexchange**
for matching listings and pushes new finds to your phone via **[ntfy](https://ntfy.sh)**.
Runs on a **self-hosted Linux VM** on a systemd timer — no third-party CI, no PC left
running.

The tracked watches live in `data/watches.json` (editable in the dashboard); the
registry currently ships with one entry — the Longines Master Collection Chrono
Moonphase (40mm) — as a worked example, but you can add, edit, or remove any watch.

## How it works

```
Self-hosted VM (GCP e2-micro, Debian)
  └─ systemd timer (every 5 min) → python watch_monitor.py
       ├─ for each watch in the registry → scan r/watchexchange (Reddit OAuth)
       ├─ filter to listings matching that watch's relevance rules
       ├─ recover the asking price from the seller's OP comment
       ├─ dedup + tag against data/*.json (local disk)
       └─ push NEW listings to your ntfy topic → phone
```

- New listings only — the first run seeds a silent baseline, then you're alerted on
  genuinely new drops.
- Anything at or under a watch's **price ceiling** gets a 🔥 high-priority push (the
  ceiling is set per watch in the registry).
- State lives on the VM's local disk (`data/monitor_state.json` dedup memory,
  `data/deals.json` deal history). There is **no** commit-back-to-git step — the VM is
  the sole writer.

## Deployment

The monitor runs on a **GCP e2-micro VM** (Debian, always-free tier) under a **systemd
timer** (`watch-monitor.timer`, `OnCalendar=*:0/5`, `Persistent=true` so missed ticks
fire on next boot). Code lives at `/opt/watch-notifier`, run by a dedicated `watch`
service user in a venv; secrets are in a root-owned `/etc/watch-notifier.env`
(systemd `EnvironmentFile`).

**Reddit OAuth is required on the VM.** From datacenter IPs the anonymous Reddit paths
are unreliable — RSS discovery is heavily rate-limited and old.reddit price recovery is
403-blocked. Set the four `REDDIT_*` env vars (script-app password grant) so discovery
and price recovery go through `oauth.reddit.com`, which works from the VM:

```
NTFY_TOPIC=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USERNAME=...      # a Reddit account that is a developer on the app
REDDIT_PASSWORD=...
```

Provisioning steps, access (Tailscale SSH / IAP), and the operational runbook live in
`VM_MIGRATION.md` and `HANDOVER.md` — local, gitignored, not shipped in the repo.

## Running locally

The monitor runs anywhere Python does — useful for development and one-off scans. A
residential IP can use the anonymous fallback (no `REDDIT_*` needed) for discovery, and
recovers prices from old.reddit directly.

1. `pip install -r requirements.txt`
2. Install the **ntfy** app on your phone and **Subscribe** to your `NTFY_TOPIC`.
3. `./run_now.sh --test` → confirm the phone gets the push.
4. `./run_now.sh` → one-off scan (first run seeds the silent baseline).
5. `./install_cron.sh` → optional hourly local cron (logs to `data/cron.log`).

## Dashboard

`webapp/flask/` is a Flask dashboard ("The Midnight Desk" — see `DESIGN.md`) for
triaging saved deals (`data/deals.json`) and managing the watch registry
(`data/watches.json`). Each deals row carries a **price-trend sparkline** (median asking
per model, derived from the deals already stored), and clicking a row opens a **detail
view** with that model's price-history chart and a link to the listing. The chart is
**hoverable** (nearest-point price + date) and has a **time-range selector** whose options
come from `data/dashboard_config.json` (edit it on the box; picked up on the next page
load). Start it with `webapp/start.sh` (binds `127.0.0.1:5000`*).

*Bind `127.0.0.1`, not `localhost` — macOS AirPlay grabs port 5000 on IPv6; local dev
uses `:5001` (see `.claude/launch.json`).

## Files

| File | Purpose |
|---|---|
| `watch_monitor.py` | The monitor (config knobs at top; `--test` sends a sample push) |
| `requirements.txt` | Python deps (`requests`, `beautifulsoup4`, `flask`, `pytest`) |
| `run_now.sh` / `install_cron.sh` | Local one-off scan / hourly local cron |
| `webapp/flask/` | Flask dashboard — browse deals + manage the watch registry |
| `data/watches.json` | Watch registry (search terms, relevance groups, refs, price ceiling) |
| `data/monitor_state.json` | Auto-created dedup memory |
| `data/deals.json` | Deal history (price + brand/model enriched) |
| `data/dashboard_config.json` | Dashboard config — the trend-chart time ranges (served fresh per page load) |
| `docs/HANDOFF_SUMMARY.md` | Project context / decision log |
| `docs/requested_watches.md` | Tracked watch preferences |

## Tuning

Watches are configured in `data/watches.json` — each entry has `brand`, `model`,
`size_mm`, `search_terms`, `relevance_required_all`, `refs`, and `price_ceiling`. Edit
the file directly or use the **Watches** tab in the dashboard. The only monitor-level
knob that stays in `watch_monitor.py` is `MAX_PUSH_PER_RUN`.

The dashboard's trend-chart time ranges live in `data/dashboard_config.json`
(`trend_ranges` + `default_range`). Edit it on the box to change which range buttons the
detail chart offers — the frontend reads it fresh on each page load, so no restart is
needed. If the file is missing or malformed, the app falls back to built-in defaults.

## Caveats

- **Price recovery is comment-based.** The seller usually posts the asking price in a
  comment moments after listing, so a just-discovered deal may show "no price" until a
  later run backfills it (up to 5 attempts, then flagged as `-1` / "⚠ no price").
- **Reddit is the only source.** eBay (Akamai) and Chrono24 (anti-bot) scrapers were
  retired; only r/watchexchange is monitored.
- **Data on the git remote is frozen** at the last pre-VM-migration commit — intended.
  The repo is no longer a backup; the VM disk is the live copy.
