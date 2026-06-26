#!/usr/bin/env bash
set -e

# 启动 adb server(容器内置 adb 客户端)。
# 本项目设备选择遵循 Midscene 机制(见 android-executor.ts):
#   1. 脚本 YAML 的 android.deviceId
#   2. 环境变量 MIDSCENE_ANDROID_DEVICE_ID
#   3. 都没有则 agentFromAdbDevice() 自动选当前 adb 已连接的设备
#
# 云真机用法:先用 cloud-real-device 占用一台设备拿到 connectCmd,
# 再在容器内执行(connectCmd 给出的地址,例如 10.238.15.91:30000):
#   docker compose exec backend-ts adb connect <agentHost:port>
# 占用返回的 udId 也可作为 MIDSCENE_ANDROID_DEVICE_ID 写入 .env。
adb start-server || true
adb devices || true

exec "$@"
