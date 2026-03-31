#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

"${ROOT_DIR}/scripts/start-backend.sh" &
BACKEND_PID=$!

"${ROOT_DIR}/scripts/start-frontend.sh" &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
