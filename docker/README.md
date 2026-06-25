# Docker 部署说明（生产镜像）

把原来的 `./dev.sh` 本地启动方式容器化为可部署的生产镜像。

## 架构

```
浏览器 ──▶ frontend 容器 (nginx :80, 映射宿主 :8080)
                │  静态资源 + 运行时 app-config.js
                └─ /api/* 反向代理 ──▶ backend-ts 容器 (Fastify :8001)
                                            │ adb connect ──▶ 远程 Android 真机
                                            ├─ 远程 MySQL (.env DATABASE_URL)
                                            └─ 远程 LLM / Midscene 模型
```

- **不含数据库容器**：MySQL 是远程的（`.env` 里的 `DATABASE_URL`）。
- **单域名**：前端 `/api` 请求经 nginx 反代到后端，无 CORS 问题。
- **Python 后端（`backend/`）未纳入**：当前以 TS 为迁移主线。需要的话可再加一个 service。

## 前置条件

1. 安装 Docker / Docker Compose（v2）。
2. 仓库根目录已有 `.env`（含 `DATABASE_URL`、`LLM_*`、`MIDSCENE_*` 等）。
3. **网络 adb**：确认能从部署机访问到远程真机的 adb 端口（形如 `host:5555`）。
   先在宿主机验证：`adb connect <host:port> && adb devices` 能看到 `device`。

## 配置

Compose 会自动读取根目录 `.env`。除已有变量外，按需在 `.env` 追加：

```bash
# 网络 adb 真机地址（backend-ts 启动时 adb connect，并作为默认 deviceId）
ANDROID_ADB_ADDR=10.238.15.91:5555

# 一般留空：前端走相对路径 /api 由 nginx 反代。
# 仅当前端与后端不同域名/不经本 nginx 时才填后端可公开访问地址。
FRONTEND_API_BASE_URL=
```

> `VITE_ANDROID_PLAYGROUND_URL` 已在 `.env` 中，会注入到前端运行时配置。

## 构建与启动

```bash
cd ~/work/liuyao/AI/UI/UIX

# 构建镜像
docker compose build

# 后台启动
docker compose up -d

# 查看日志
docker compose logs -f backend-ts
docker compose logs -f frontend
```

访问：

- 前端：`http://<部署机IP>:8080`
- 后端(直连，调试用)：`http://<部署机IP>:8001/api/...`

## 验证 adb 是否连上

```bash
docker compose exec backend-ts adb devices
# 期望看到 <host:port>  device
```

## 常用操作

```bash
docker compose restart backend-ts     # 改了 .env 后重启生效
docker compose down                   # 停止并移除容器
docker compose build backend-ts       # 只重建后端
docker compose up -d --build          # 重建并滚动更新
```

## 设计要点 / 注意

- **运行时配置**：前端镜像构建一次即可多环境复用。`API_BASE_URL`、`ANDROID_PLAYGROUND_URL`
  在容器启动时由 `envsubst` 写入 `app-config.js`（前端读 `window.__APP_CONFIG__`）。
- **Prisma**：构建阶段 `prisma generate` 生成 Client 并随 `node_modules` 进入运行镜像。
  改了 `prisma/schema.prisma` 需重建 backend-ts 镜像。
- **adb**：`backend-ts` 镜像装了 `android-tools-adb`，entrypoint 在启动时
  `adb connect $ANDROID_ADB_ADDR`。若是 USB 直连真机（非网络 adb），容器方案不适用，
  后端需留在宿主机运行。
- **耗时任务**：nginx 对 `/api` 的 `proxy_read/send_timeout` 已放宽到 600s。
