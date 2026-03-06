#!/bin/bash

cd backend || exit

PORT=8000

echo "🚀 starting backend..."

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