#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_IMPL="${UIX_BACKEND_IMPL:-ts}"

if [ "${BACKEND_IMPL}" = "python" ]; then
  echo "ℹ️ dev.sh backend mode: python (http://127.0.0.1:8000)"
else
  echo "ℹ️ dev.sh backend mode: typescript (http://127.0.0.1:8001)"
fi
echo "ℹ️ set UIX_BACKEND_IMPL=python to temporarily rollback local dev backend"

"${ROOT_DIR}/scripts/start-backend.sh" &
BACKEND_PID=$!

"${ROOT_DIR}/scripts/start-frontend.sh" &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
