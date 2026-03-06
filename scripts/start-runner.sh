#!/bin/bash

cd runner-service || exit

echo "🚀 starting runner service..."

if [ ! -d "node_modules" ]; then
  npm install
fi

while true
do
  npm run dev
  echo "⚠️ runner crashed, restarting..."
  sleep 2
done