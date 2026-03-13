#!/bin/bash

cd frontend || exit

HOST_IP=10.238.15.91

echo "🚀 starting frontend..."
echo "🌐 frontend url: http://${HOST_IP}:5173"

if [ ! -d "node_modules" ]; then
  echo "📦 installing deps..."
  corepack pnpm install
fi

corepack pnpm dev --host 0.0.0.0 --port 5173
