#!/usr/bin/env bash
# Install (or refresh) an hourly local cron job that runs the watch monitor.
# Idempotent: re-running replaces the existing entry instead of duplicating it.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
JOB="0 * * * * $DIR/run_now.sh >> $DIR/data/cron.log 2>&1"

# Drop any prior line for this script, then append the current one.
( crontab -l 2>/dev/null | grep -vF "$DIR/run_now.sh" ; echo "$JOB" ) | crontab -

echo "Hourly cron job installed:"
echo "  $JOB"
echo
echo "Verify:  crontab -l"
echo "Logs:    tail -f $DIR/data/cron.log"
echo "Remove:  crontab -l | grep -vF '$DIR/run_now.sh' | crontab -"
echo
echo "macOS note: the first run may prompt for Full Disk Access for /usr/sbin/cron"
echo "(System Settings > Privacy & Security). Grant it if cron.log stays empty."
