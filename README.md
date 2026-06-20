# watch-notifier

Hourly monitor for **Longines Master Collection Chrono Moonphase (40mm)** secondary-market
listings. Scans **r/watchexchange + eBay (+ Chrono24 best-effort)** and pushes new finds to
your phone via **[ntfy](https://ntfy.sh)**. Runs free on **GitHub Actions** — no server, no PC required.

## How it works

```
GitHub Actions (hourly cron)
  └─ python watch_monitor.py
       ├─ scan sources  → filter to relevant listings
       ├─ dedup against data/monitor_state.json (committed back each run)
       └─ push NEW listings to your ntfy topic → phone
```

- New listings only — the first run seeds a silent baseline, then you're alerted on genuinely new drops.
- Anything **≤ $2,000** gets a 🔥 high-priority push.
- Dedup state lives in `data/monitor_state.json`, which the workflow commits back after each run (this also keeps the repo active so GitHub won't auto-disable the schedule).

## Setup

Full step-by-step (secrets, permissions, testing) is in **[GITHUB_ACTIONS_SETUP.md](./GITHUB_ACTIONS_SETUP.md)**. Short version:

1. Add a repo secret `NTFY_TOPIC` (Settings → Secrets and variables → Actions).
2. Set **Settings → Actions → General → Workflow permissions → Read and write**.
3. Push to `main`, then **Actions → Watch Tracker Monitor → Run workflow** with `test_push = true` to verify the phone push.
4. Run once more with `test_push = false` to seed the baseline. Hourly schedule takes over after that.

## Files

| File | Purpose |
|---|---|
| `watch_monitor.py` | The monitor (config knobs at top; `--test` sends a sample push) |
| `requirements.txt` | Python deps (`requests`, `beautifulsoup4`) |
| `.github/workflows/monitor.yml` | Hourly schedule + manual test button + state commit |
| `data/monitor_state.json` | Auto-created dedup memory (tracked in git on purpose) |
| `GITHUB_ACTIONS_SETUP.md` | Detailed setup + troubleshooting |
| `HANDOFF_SUMMARY.md` | Project context / decision log |
| `requested_watches.md` | Tracked watch preferences |

## Tuning

Watches are configured in `data/watches.json` — each entry has `brand`, `model`, `size_mm`,
`search_terms`, `relevance_required_all`, `refs`, and `price_ceiling`. Edit the file directly or
use the **Watches** tab in the web app. The only monitor-level knob that stays in `watch_monitor.py`
is `MAX_PUSH_PER_RUN`.

## Caveats

- GitHub cron is **UTC** and runs can lag **10–30 min** under load (fine for hourly).
- **Datacenter IPs get bot-blocked more than a home connection** — Reddit's JSON keeps working, but eBay/Chrono24 coverage may be thinner on Actions than running locally. Check a few run logs.
- Local-run mode still works too: set `NTFY_TOPIC`, then `python watch_monitor.py` (see `GITHUB_ACTIONS_SETUP.md`).
