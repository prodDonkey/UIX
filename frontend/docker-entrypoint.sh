#!/bin/sh
set -eu

envsubst '${API_BASE_URL} ${ANDROID_PLAYGROUND_URL}' \
  < /usr/share/nginx/html/app-config.template.js \
  > /usr/share/nginx/html/app-config.js

exec "$@"
