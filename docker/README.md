# Docker Compose 部署

## 服务

- `frontend`：Vue 前端，容器内用 Nginx 提供静态资源，并反向代理 `/api` 到 `backend`
- `backend`：FastAPI 主服务
- `runner`：可选，默认不启动；如果你需要单独的 runner，可用 `--profile runner`

`Android Playground` 默认不放进 compose，因为它通常需要直接访问宿主机上的 `adb` 和已连接设备。推荐在宿主机启动它，再把：

- `MIDSCENE_BASE_URL`
- `ANDROID_PLAYGROUND_URL`

指向宿主机实际地址。

## 启动

```bash
cp docker/.env.example .env
docker compose up -d --build
```

启用 runner：

```bash
docker compose --profile runner up -d --build
```

## 访问

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Runner: `http://localhost:8100`（仅启用 `runner` profile 时）

## 说明

- 默认使用 SQLite，数据落在 `backend_data` volume。
- `midscene_report` volume 用于保留报告产物。
- `frontend` 通过运行时生成 `app-config.js`，所以修改 `.env` 后只需重启前端容器，不必重新构建前端镜像。
