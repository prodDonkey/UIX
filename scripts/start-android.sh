#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID_ROOT="${ROOT_DIR}/android-playground"
ANDROID_PKG_DIR="${ANDROID_ROOT}/packages/android-playground"
HOST_IP=10.238.15.91
WSL_GATEWAY_IP=

if grep -qi microsoft /proc/version 2>/dev/null; then
  WSL_GATEWAY_IP="$(ip route 2>/dev/null | awk '/default/ {print $3; exit}')"
fi

if [ -z "${ANDROID_HOME:-}" ] && [ -d "/mnt/c/Android" ]; then
  export ANDROID_HOME="/mnt/c/Android"
fi

if [ -z "${ANDROID_SDK_ROOT:-}" ] && [ -n "${ANDROID_HOME:-}" ]; then
  export ANDROID_SDK_ROOT="${ANDROID_HOME}"
fi

if [ -n "${ANDROID_HOME:-}" ]; then
  export PATH="${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/cmdline-tools/latest/bin:${PATH}"
fi

if [ -n "${ANDROID_HOME:-}" ] && [ -f "${ANDROID_HOME}/platform-tools/adb.exe" ] && [ ! -e "${ANDROID_HOME}/platform-tools/adb" ]; then
  cat > "${ANDROID_HOME}/platform-tools/adb" <<'EOF'
#!/bin/sh
exec "$(dirname "$0")/adb.exe" "$@"
EOF
  chmod +x "${ANDROID_HOME}/platform-tools/adb"
fi

if [ -z "${MIDSCENE_ADB_PATH:-}" ] && [ -f "${ANDROID_HOME:-}/platform-tools/adb.exe" ]; then
  export MIDSCENE_ADB_PATH="${ANDROID_HOME}/platform-tools/adb.exe"
fi

if [ -z "${MIDSCENE_ADB_REMOTE_HOST:-}" ] && [ -n "${WSL_GATEWAY_IP}" ]; then
  export MIDSCENE_ADB_REMOTE_HOST="${WSL_GATEWAY_IP}"
fi

if [ -z "${MIDSCENE_ADB_REMOTE_PORT:-}" ]; then
  export MIDSCENE_ADB_REMOTE_PORT="5037"
fi

cd "${ANDROID_ROOT}" || exit

echo "🚀 starting android-playground..."
echo "🌐 playground url: http://${HOST_IP}:5800"
if [ -n "${MIDSCENE_ADB_REMOTE_HOST:-}" ]; then
  echo "📱 adb server: ${MIDSCENE_ADB_REMOTE_HOST}:${MIDSCENE_ADB_REMOTE_PORT}"
fi

if [ -n "${MIDSCENE_ADB_PATH:-}" ]; then
  if [ -n "${MIDSCENE_ADB_REMOTE_HOST:-}" ] && [ "${MIDSCENE_ADB_REMOTE_HOST}" != "127.0.0.1" ] && [ "${MIDSCENE_ADB_REMOTE_HOST}" != "localhost" ]; then
    "${MIDSCENE_ADB_PATH}" -a start-server >/dev/null 2>&1 || true
  else
    "${MIDSCENE_ADB_PATH}" start-server >/dev/null 2>&1 || true
  fi
fi

# 自动安装依赖
if [ ! -d "node_modules" ]; then
  echo "📦 installing dependencies..."
  corepack pnpm install
fi

while true
do
  echo "🔨 rebuilding shared/core/playground/android/android-playground..."
  corepack pnpm --filter @midscene/shared build || exit 1
  corepack pnpm --filter @midscene/core build || exit 1
  corepack pnpm --filter @midscene/playground build || exit 1
  corepack pnpm --filter @midscene/android build || exit 1
  corepack pnpm --filter @midscene/android-playground build || exit 1

  cd "${ANDROID_PKG_DIR}" || exit
  MIDSCENE_NO_OPEN=1 node ./dist/lib/bin.js
  cd "${ANDROID_ROOT}" || exit

  echo "⚠️ server crashed, restarting in 2s..."
  sleep 2
done
