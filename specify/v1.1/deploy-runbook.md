# D2/D4 发布与运维手册（Runner 单路径）

日期：2026-03-04

## 1. 架构说明
- 执行入口统一为 `runner-service`。
- `backend` 只负责任务编排、状态落库、对外 API。
- `frontend` 通过 `runs` 与 `progress` 接口展示状态/步骤。

## 2. 环境要求
- Node.js >= 18
- Python >= 3.11
- `uv` 已安装
- 可用 ADB 与 Android 设备

## 3. 启动方式
### 3.1 启动 Runner
```bash
cd /Users/yaohongliang/work/liuyao/AI/UI/ui_demo/runner-service
npm install
npm run dev
```
默认端口：`8787`

### 3.2 启动 backend
```bash
cd /Users/yaohongliang/work/liuyao/AI/UI/ui_demo/backend
uv sync --extra dev
cp .env.example .env
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3.3 启动 frontend
```bash
cd /Users/yaohongliang/work/liuyao/AI/UI/ui_demo/frontend
npm install
npm run dev -- --port 5173
```

## 4. 关键配置
### 4.1 backend -> Midscene 连接配置
- `MIDSCENE_BASE_URL`：Midscene / Android Playground 服务地址（示例：`http://127.0.0.1:5800`）
- `MIDSCENE_TIMEOUT_SEC`：后端请求 Midscene 的超时秒数
- `MIDSCENE_STATUS_POLL_INTERVAL_MS`：后端轮询 Midscene 状态周期（毫秒）

### 4.2 Midscene 配置
- `MIDSCENE_MODEL_BASE_URL`
- `MIDSCENE_MODEL_API_KEY`
- `MIDSCENE_MODEL_NAME`
- `MIDSCENE_MODEL_FAMILY`

## 5. 发布流程（测试 -> 预发 -> 生产）
1. 发布 `runner-service` 新版本并完成健康检查（`GET /health`）。
2. 更新 backend 环境变量中的 `MIDSCENE_BASE_URL` 指向目标 Android Playground 服务。
3. 发布 backend，执行 `runs` 与 `progress` 接口冒烟。
4. 发布 frontend，确认运行详情页步骤面板与实时画面均可用。
5. 执行 D1 四类用例抽检后放量。

## 6. 运维巡检
- Runner 健康：`curl http://127.0.0.1:8787/health`
- Backend 健康：`curl http://127.0.0.1:8000/health`
- 设备连通：`adb devices -l`
- 运行链路：创建 run 并观察 `status/current_task/current_action` 持续变化。

## 7. 常见故障排查
1. 任务一直 queued
- 检查 `MIDSCENE_BASE_URL` 是否可达。
- 检查 Android Playground 日志是否有启动失败或端口冲突。

2. 有实时画面但无步骤更新
- 检查 `/api/runs/{id}/progress` 返回是否包含 `progress_json`。
- 检查 backend 轮询线程是否异常退出。

3. 取消不生效
- 检查 backend 是否调用 Runner `/cancel`。
- 检查 run 是否已进入终态（终态取消会幂等忽略）。

4. 报告预览失败
- 检查 `report_path` 是否存在。
- 检查报告路径是否在后端白名单目录内。
