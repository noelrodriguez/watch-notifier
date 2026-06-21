#!/usr/bin/env bash
# Instant on-demand scan — the same thing the hourly GitHub Action runs, locally.
# Usage:
#   ./run_now.sh          # real scan, pushes any new listings to ntfy
#   ./run_now.sh --test   # send a single test ntfy push to verify your phone
set -euo pipefail
cd "$(dirname "$0")"
# Make Homebrew/system python visible even under cron's minimal PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
# Optional local secrets (e.g. NTFY_TOPIC override, TELEGRAM_*). Safe to omit;
# watch_monitor.py falls back to its built-in topic. .env is git-ignored.
[ -f .env ] && set -a && . ./.env && set +a
exec python3 watch_monitor.py "$@"
