#!/bin/bash

clear_dead_local_proxy() {
  local proxy_value="${https_proxy:-${HTTPS_PROXY:-${http_proxy:-${HTTP_PROXY:-${all_proxy:-${ALL_PROXY:-}}}}}}"
  if [ -z "${proxy_value}" ]; then
    return
  fi

  if [[ "${proxy_value}" =~ ^(http|https|socks5)://(127\.0\.0\.1|localhost):([0-9]+)$ ]]; then
    local proxy_host="${BASH_REMATCH[2]}"
    local proxy_port="${BASH_REMATCH[3]}"
    if ! (echo >"/dev/tcp/${proxy_host}/${proxy_port}") >/dev/null 2>&1; then
      echo "⚠️ local proxy ${proxy_host}:${proxy_port} is unreachable, disabling proxy env for this session..."
      unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
    fi
  fi
}

clear_dead_local_proxy

cd frontend || exit

HOST_IP=10.238.15.91

echo "🚀 starting frontend..."
echo "🌐 frontend url: http://${HOST_IP}:5173"

if [ ! -d "node_modules" ]; then
  echo "📦 installing deps..."
  corepack pnpm install
fi

corepack pnpm dev --host 0.0.0.0 --port 5173
