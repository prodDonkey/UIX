# v2.0 需求文档：任务执行模块独立服务化（Runner）

## 1. 背景与问题
当前 `ui_demo` 的任务执行链路由 Python 后端通过子进程直接调用 `npx midscene <yaml>` 完成。

现状问题：
- 执行过程对业务层是“黑盒”，只能拿到日志文本，缺少结构化实时进度。
- 运行详情页可嵌入 Android Playground 实时画面，但无法与 `runId` 精确绑定当前步骤。
- 取消、超时、重试等控制能力受限，扩展并发/队列治理成本高。

## 2. 目标
将任务执行模块从 `ui_demo backend` 中拆分为独立 Runner 服务，实现：

1. 按 `runId` 提供结构化实时进度（任务、动作、完成度）。
2. 与现有 UI 运行详情页对齐，支持“画面 + 当前步骤 + 日志”联动展示。
3. 保持现有脚本管理与运行列表 API 的兼容性（前端改动可渐进）。
4. 为后续并发治理、调度、观测能力预留清晰边界。

## 3. 范围
### 3.1 In Scope
- 新增独立 Runner 服务（Node.js）。
- `ui_demo backend` 改为调用 Runner，不再直接执行 `npx midscene`。
- 新增/调整运行进度相关 API 与数据字段。
- 前端运行详情页展示结构化“当前步骤”。

### 3.2 Out of Scope
- 权限系统、多租户隔离。
- 分布式队列与跨机器调度。
- 大规模压测与自动弹性扩缩容。

## 4. 总体方案

### 4.1 架构
- `frontend`：继续调用 `ui_demo backend`。
- `ui_demo backend`（Python）：负责业务记录、状态聚合、对外 API。
- `runner-service`（Node）：负责实际执行 YAML、产出结构化进度、处理取消。
- `android-playground`：作为实时设备画面展示层，通过 iframe 嵌入。

### 4.2 职责边界
#### ui_demo backend
- 创建 run 记录、维护 run 生命周期。
- 调用 Runner 的 `start/progress/cancel/result`。
- 聚合并持久化进度快照，提供给前端稳定查询。

#### runner-service
- 基于 Midscene SDK 执行 YAML。
- 监听 `onDumpUpdate`，维护每个 `runId` 的最新进度状态。
- 提供结构化进度查询与取消能力。

## 5. Runner 服务需求

### 5.1 API（建议）
1. `POST /runs/start`
- 请求：`{ runId: number, yamlPath?: string, yamlContent?: string }`
- 响应：`{ accepted: true }`

2. `GET /runs/:runId/progress`
- 响应：
```json
{
  "runId": 38,
  "status": "running",
  "currentTask": "登录流程",
  "currentAction": "aiTap 登录按钮",
  "completed": 3,
  "total": 10,
  "executionDump": {}
}
```

3. `POST /runs/:runId/cancel`
- 响应：`{ success: true }`

4. `GET /runs/:runId/result`
- 响应：`{ status, reportPath, summaryPath, errorMessage }`

### 5.2 执行与状态机
- 状态：`queued -> running -> success|failed|cancelled`
- 支持幂等取消：对已终态请求取消返回成功且不重复动作。
- 进度更新频率：建议 500ms~1000ms。

### 5.3 失败处理
- 执行失败必须返回可读 `errorMessage`。
- Runner 异常退出时，backend 需将 run 标记为 `failed` 并记录原因。

## 6. ui_demo backend 改造需求

### 6.1 服务配置
新增配置项（示例）：
- `RUNNER_BASE_URL`
- `RUNNER_TIMEOUT_SEC`
- `RUNNER_PROGRESS_POLL_INTERVAL_MS`

### 6.2 数据模型调整（runs）
建议新增字段：
- `current_task`（string, nullable）
- `current_action`（string, nullable）
- `progress_json`（text/json, nullable）

### 6.3 API 调整
- 保持现有 `/api/runs` 契约可用。
- 新增：`GET /api/runs/{id}/progress`，返回结构化进度。

## 7. 前端改造需求（RunDetail）
- 在现有 2 秒轮询中增加进度查询。
- 展示：当前任务、当前动作、已完成/总数、最近步骤列表（可选）。
- 与已嵌入 Android Playground 同屏展示。

## 8. 迁移与发布
- v2.0 全量采用 Runner 单路径，不再保留 legacy 执行模式。
- 发布采用分环境推进：测试 -> 预发 -> 生产。
- 异常通过 Runner 服务版本回滚与任务熔断处置。

## 9. 非功能需求
- 可用性：单任务执行链路在本地/测试环境稳定运行。
- 可观测性：关键日志包含 `runId`、状态变化、耗时。
- 安全性：Runner 对 `yamlPath` 做白名单校验，禁止任意路径执行。

## 10. 验收标准
1. 启动 run 后，前端可在 2 秒内看到结构化当前步骤变化。
2. 取消执行后，状态在可接受时间内转为 `cancelled`。
3. 成功执行后可正常获取报告预览/下载。
4. 失败执行可返回结构化错误原因。
5. 现有脚本 CRUD 与运行列表功能无回归。

## 11. 实施里程碑（建议）
- M1：Runner 服务最小可用（start/progress/cancel/result）。
- M2：backend 接入 Runner + 数据模型扩展。
- M3：前端运行详情展示结构化步骤。
- M4：联调、回归、文档与上线开关。

## 12. 风险与应对
- 风险：Node Runner 与 Python backend 状态不一致。
  - 应对：backend 以轮询结果为准并定期对账终态。
- 风险：执行任务中断导致“悬挂 run”。
  - 应对：增加超时与 watchdog，自动失败收敛。
- 风险：设备连接波动影响步骤连续性。
  - 应对：Runner 明确区分设备异常与业务失败，输出可诊断错误。

