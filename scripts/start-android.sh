#!/bin/bash

cd android-playground || exit

HOST_IP=10.238.15.91

echo "🚀 starting android-playground..."
echo "🌐 playground url: http://${HOST_IP}:5800"

# 自动安装依赖
if [ ! -d "node_modules" ]; then
  echo "📦 installing dependencies..."
  corepack pnpm install
fi

while true
do
  echo "🔨 rebuilding core/playground/android-playground..."
  corepack pnpm --filter @midscene/core build || exit 1
  corepack pnpm --filter @midscene/android-playground build || exit 1
  MIDSCENE_NO_OPEN=1 node ./packages/android-playground/dist/lib/bin.js
  echo "⚠️ server crashed, restarting in 2s..."
  sleep 2
done
