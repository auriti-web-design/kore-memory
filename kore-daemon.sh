#!/usr/bin/env bash
# Kore — proper daemon launcher with .env support

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

PID_FILE="$DIR/logs/kore.pid"
LOG_FILE="$DIR/logs/server.log"
mkdir -p logs

# Load .env
if [ -f "$DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$DIR/.env"
    set +a
fi

# Check if already running
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    if curl -sf http://127.0.0.1:8765/health >/dev/null 2>&1; then
        echo "Kore already running (PID $(cat "$PID_FILE"))"
        exit 0
    fi
fi

# Kill stale processes
fuser -k 8765/tcp 2>/dev/null || true
sleep 1

# Start with proper daemonization
setsid "$DIR/.venv/bin/kore" \
    --host 127.0.0.1 \
    --port 8765 \
    --log-level warning \
    < /dev/null >> "$LOG_FILE" 2>&1 &

PID=$!
echo "$PID" > "$PID_FILE"
disown

echo "Kore started (PID $PID)"
