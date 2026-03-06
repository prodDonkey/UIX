#!/bin/bash

cd android-playground || exit

echo "🚀 starting android-playground..."

# 自动安装依赖
if [ ! -d "node_modules" ]; then
  echo "📦 installing dependencies..."
  pnpm install
fi

while true
do
  pnpm dev:server
  echo "⚠️ server crashed, restarting in 2s..."
  sleep 2
done