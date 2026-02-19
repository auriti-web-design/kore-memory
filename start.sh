#!/usr/bin/env sh
# Kore — start server in background
# Usage: ./start.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

PID_FILE="$DIR/logs/kore.pid"
mkdir -p "$DIR/logs"

# Already running?
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Kore already running (pid $PID)"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

nohup "$DIR/.venv/bin/uvicorn" src.main:app \
    --host 127.0.0.1 \
    --port 8765 \
    --log-level warning \
    > "$DIR/logs/server.log" 2>&1 &

echo $! > "$PID_FILE"
echo "Kore started (pid $!)"
