#!/bin/bash

cd frontend || exit

echo "🚀 starting frontend..."

if [ ! -d "node_modules" ]; then
  echo "📦 installing deps..."
  pnpm install
fi

pnpm dev --host 0.0.0.0 --port 5173