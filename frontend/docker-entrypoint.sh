#!/bin/sh
set -e

# 运行时生成前端配置:把环境变量注入 app-config.js
# 前端通过 window.__APP_CONFIG__ 读取(见 frontend/src/config/runtime.ts)
# API_BASE_URL 留空 => axios 用相对路径 /api,经 nginx 反代到 backend-ts(同域名)
: "${API_BASE_URL:=}"
: "${ANDROID_PLAYGROUND_URL:=}"
export API_BASE_URL ANDROID_PLAYGROUND_URL

envsubst '${API_BASE_URL} ${ANDROID_PLAYGROUND_URL}' \
  < /usr/share/nginx/html/app-config.template.js \
  > /usr/share/nginx/html/app-config.js

echo "[app-config] API_BASE_URL='${API_BASE_URL}' ANDROID_PLAYGROUND_URL='${ANDROID_PLAYGROUND_URL}'"
