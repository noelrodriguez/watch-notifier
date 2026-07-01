#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLASK_DIR="$SCRIPT_DIR/flask"
FLASK_LOG="$FLASK_DIR/flask.log"

echo "==> Installing dependencies..."
python3 -m pip install flask --quiet

echo "==> Stopping any existing instance..."
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
sleep 0.5

echo "==> Starting Flask on :5000..."
cd "$FLASK_DIR"
FLASK_APP=app.py python3 -m flask run --port 5000 > "$FLASK_LOG" 2>&1 &
FLASK_PID=$!

echo "==> Waiting for server to start..."
sleep 2

if ! kill -0 "$FLASK_PID" 2>/dev/null; then
  echo "ERROR: Flask failed to start. Check $FLASK_LOG"
  exit 1
fi

echo "==> Opening browser..."
open "http://127.0.0.1:5000"

echo ""
echo "Flask is running:"
echo "  http://127.0.0.1:5000   (pid $FLASK_PID)   logs: webapp/flask/flask.log"
echo ""
echo "To stop:"
echo "  kill $FLASK_PID"
