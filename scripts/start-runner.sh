#!/bin/bash

HOST_IP=10.238.15.91
PORT=8100

cd runner-service || exit

echo "🚀 starting runner service..."
echo "🌐 runner url: http://${HOST_IP}:${PORT}"

if [ ! -d "node_modules" ]; then
  npm install
fi

while true
do
  RUNNER_HOST=0.0.0.0 RUNNER_PORT=${PORT} npm run dev
  echo "⚠️ runner crashed, restarting..."
  sleep 2
done
