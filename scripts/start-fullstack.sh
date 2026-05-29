#!/bin/sh
set -eu

export PATH="/opt/venv/bin:$PATH"
export HOSTNAME="${HOSTNAME:-0.0.0.0}"
export PORT="${PORT:-8080}"

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
backend_pid="$!"

cleanup() {
  kill "$backend_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

cd /app/frontend
node server.js
