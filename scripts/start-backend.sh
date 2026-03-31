#!/bin/bash

source ~/.zshrc >/dev/null 2>&1 || true

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "${ROOT_DIR}/.env" ]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi

cd "${ROOT_DIR}/backend" || exit

HOST_IP=10.238.15.91
PORT=8000

echo "🚀 starting backend..."
echo "🌐 backend url: http://${HOST_IP}:${PORT}"

PID=$(lsof -ti:$PORT)

if [ ! -z "$PID" ]; then
  echo "⚠️ killing process on port $PORT"
  kill -9 $PID
fi

if [ ! -d ".venv" ]; then
  echo "📦 installing python deps"
  uv sync
fi

while true
do
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  echo "⚠️ backend crashed, restarting..."
  sleep 2
done
