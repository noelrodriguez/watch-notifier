#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
FLASK_DIR="$SCRIPT_DIR/flask"
STREAMLIT_APP="$SCRIPT_DIR/streamlit/app.py"
FLASK_LOG="$FLASK_DIR/flask.log"
STREAMLIT_LOG="$SCRIPT_DIR/streamlit/streamlit.log"

echo "==> Installing dependencies..."
python3 -m pip install flask streamlit pandas --quiet

echo "==> Stopping any existing instances..."
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
lsof -ti:8501 | xargs kill -9 2>/dev/null || true
sleep 0.5

echo "==> Starting Flask on :5000..."
cd "$FLASK_DIR"
FLASK_APP=app.py python -m flask run --port 5000 > "$FLASK_LOG" 2>&1 &
FLASK_PID=$!

echo "==> Starting Streamlit on :8501..."
python -m streamlit run "$STREAMLIT_APP" \
  --server.port 8501 \
  --server.headless true \
  > "$STREAMLIT_LOG" 2>&1 &
STREAMLIT_PID=$!

echo "==> Waiting for servers to start..."
sleep 2

# Verify both are still running
if ! kill -0 "$FLASK_PID" 2>/dev/null; then
  echo "ERROR: Flask failed to start. Check $FLASK_LOG"
  exit 1
fi
if ! kill -0 "$STREAMLIT_PID" 2>/dev/null; then
  echo "ERROR: Streamlit failed to start. Check $STREAMLIT_LOG"
  exit 1
fi

echo "==> Opening browsers..."
open "http://localhost:5000"
open "http://localhost:8501"

echo ""
echo "Both apps are running:"
echo "  Flask      http://localhost:5000   (logs: webapp/flask/flask.log)"
echo "  Streamlit  http://localhost:8501   (logs: webapp/streamlit/streamlit.log)"
echo ""
echo "To stop: kill $( lsof -ti:5000 ) $( lsof -ti:8501 )"
