#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID_ROOT="${ROOT_DIR}/android-playground"
ANDROID_PKG_DIR="${ANDROID_ROOT}/packages/android-playground"
HOST_IP=10.238.15.91

cd "${ANDROID_ROOT}" || exit

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

  cd "${ANDROID_PKG_DIR}" || exit
  MIDSCENE_NO_OPEN=1 node ./dist/lib/bin.js
  cd "${ANDROID_ROOT}" || exit

  echo "⚠️ server crashed, restarting in 2s..."
  sleep 2
done
