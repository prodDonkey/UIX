#!/usr/bin/env bash
set -e

# 网络 adb 接入:若配置了 ANDROID_ADB_ADDR(形如 10.238.15.91:5555),
# 启动 adb server 并连接远程真机。@midscene/android 的 agentFromAdbDevice
# 会以该地址作为 deviceId 连接设备。
if [ -n "${ANDROID_ADB_ADDR}" ]; then
  echo "[adb] starting adb server, connecting to ${ANDROID_ADB_ADDR}"
  adb start-server || true
  adb connect "${ANDROID_ADB_ADDR}" || echo "[adb] WARN: 连接失败,后续将依赖应用层重试"
  adb devices || true

  # 未显式指定默认设备时,用网络 adb 地址兜底
  if [ -z "${MIDSCENE_ANDROID_DEVICE_ID}" ]; then
    export MIDSCENE_ANDROID_DEVICE_ID="${ANDROID_ADB_ADDR}"
    echo "[adb] MIDSCENE_ANDROID_DEVICE_ID defaults to ${MIDSCENE_ANDROID_DEVICE_ID}"
  fi
else
  echo "[adb] ANDROID_ADB_ADDR 未设置,跳过 adb connect(真机相关功能将不可用)"
fi

exec "$@"
