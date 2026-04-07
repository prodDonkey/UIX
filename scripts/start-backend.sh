#!/bin/bash

source ~/.zshrc >/dev/null 2>&1 || true

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_IMPL="${UIX_BACKEND_IMPL:-ts}"

if [ -f "${ROOT_DIR}/.env" ]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi

HOST_IP=10.238.15.91

if [ "${BACKEND_IMPL}" = "python" ]; then
  cd "${ROOT_DIR}/backend" || exit
  PORT=8000

  echo "🚀 starting backend (python)..."
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
fi

cd "${ROOT_DIR}/backend-ts" || exit
PORT=8001

echo "🚀 starting backend (typescript)..."
echo "🌐 backend url: http://${HOST_IP}:${PORT}"

PID=$(lsof -ti:$PORT)
if [ ! -z "$PID" ]; then
  echo "⚠️ killing process on port $PORT"
  kill -9 $PID
fi

if [ ! -d "node_modules" ]; then
  echo "📦 installing node deps"
  npm install
fi

while true
do
  PORT=8001 npm run dev
  echo "⚠️ backend crashed, restarting..."
  sleep 2
done
