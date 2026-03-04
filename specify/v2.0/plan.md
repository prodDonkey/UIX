# v2.0 技术实现计划（plan）

## 1. 计划目标
基于 `spec.md` 落地“任务执行模块独立服务化（Runner）”，实现 runId 级结构化进度展示，并保持现有业务 API 兼容。

交付结果：
- Runner 服务可执行 YAML 并提供 `start/progress/cancel/result`。
- `ui_demo backend` 全量切换为调用 Runner。
- `RunDetail` 可展示“当前任务/当前动作/完成度”。

## 2. 技术方案落地原则
- 优先最小闭环：先通单机单实例，再优化并发与可观测性。
- 保持兼容：前端已有页面与后端主接口不破坏。
- 可回滚：通过 Runner 服务版本回滚与任务熔断实现快速止损。
- 可诊断：每个环节日志必须带 `runId`。

## 3. 分阶段实施

## Phase 1：Runner 服务 MVP
### 3.1 目标
实现独立 Node Runner，具备基础执行能力和结构化进度读取。

### 3.2 代码与目录建议
- 新增目录：`/Users/yaohongliang/work/liuyao/AI/UI/ui_demo/runner-service`
- 技术栈：Node.js + TypeScript + Fastify

建议目录结构：
- `src/server.ts`：HTTP 服务入口
- `src/services/run-manager.ts`：run 生命周期与内存状态管理
- `src/services/yaml-runner.ts`：Midscene 执行封装（`agent.runYaml`）
- `src/types.ts`：请求/响应与内部状态类型
- `src/config.ts`：环境变量配置

### 3.3 API 实现
1. `POST /runs/start`
- 入参：`runId` + `yamlContent` + 可选 `deviceId`
- 行为：
  - 校验 runId 是否已存在且状态非终态
  - 创建内存状态（queued -> running）
  - 异步执行

2. `GET /runs/:runId/progress`
- 返回：`status/currentTask/currentAction/completed/total/executionDump/updatedAt`
- 数据来源：执行过程中 `onDumpUpdate` 持续覆盖最新快照

3. `POST /runs/:runId/cancel`
- 行为：
  - 若运行中，调用 agent destroy / stop
  - 状态置 `cancelled`
  - 幂等返回

4. `GET /runs/:runId/result`
- 返回：终态、reportPath、summaryPath、errorMessage、durationMs

### 3.4 核心执行逻辑
- 使用 `@midscene/android` 创建 Agent（必要时从 YAML 中获取/注入 deviceId）。
- 在执行前注册：
  - `agent.onDumpUpdate = (_, executionDump) => { ... }`
- 从 `executionDump.tasks` 计算：
  - `total`
  - `completed`
  - `currentTask`（最后一个未结束/当前任务）
  - `currentAction`（当前 task 的 action 文案）
- 执行完成后收集报告路径、耗时、错误信息。

### 3.5 Phase 1 验收
- 本地可通过 curl 完整跑通：start -> progress -> result。
- 运行中 `progress` 字段持续变化。
- cancel 可生效且幂等。

## Phase 2：ui_demo backend 接入 Runner
### 4.1 目标
替换当前 `subprocess npx midscene` 路径为 Runner 调用路径（全量启用）。

### 4.2 影响文件（backend）
- `app/core/config.py`：新增 Runner 配置
- `app/services/run_service.py`：执行链改造
- `app/models/run.py`：新增进度字段
- `app/schemas/run.py`：新增字段返回
- `app/api/runs.py`：新增 progress 接口

### 4.3 配置项
- `RUNNER_BASE_URL`
- `RUNNER_TIMEOUT_SEC`
- `RUNNER_PROGRESS_POLL_INTERVAL_MS`

### 4.4 数据模型变更（runs）
新增字段：
- `current_task` (nullable)
- `current_action` (nullable)
- `progress_json` (nullable text/json)

迁移策略：
- 若当前无 Alembic 迁移流程，先保持与现有 `create_all` 兼容。
- 若需 MySQL 生产化，补充 Alembic revision。

### 4.5 执行链改造
- `create_run` 不变。
- `start_run_async`：
  - 调 `POST /runs/start`
    - 启动轮询线程拉取 `/progress`
    - 终态后拉 `/result` 写库

### 4.6 新增 API
- `GET /api/runs/{id}/progress`
- 直接返回数据库中的 `current_task/current_action/progress_json/status`

### 4.7 Phase 2 验收
- run 生命周期可正确收敛。
- runs 主列表接口兼容原调用方。

## Phase 3：前端运行详情接入结构化进度
### 5.1 目标
在 `RunDetail` 页面展示 runId 绑定的“当前步骤”。

### 5.2 影响文件（frontend）
- `src/api/runs.ts`：新增 `progress(runId)`
- `src/pages/RunDetail.vue`：新增进度面板与渲染逻辑

### 5.3 UI 展示建议
新增“当前步骤”信息区：
- 当前任务：`current_task`
- 当前动作：`current_action`
- 进度：`completed/total`
- 最近步骤（可选）：从 `progress_json.executionDump.tasks` 提取最近 5 条

### 5.4 轮询策略
- 与当前 run detail 刷新周期对齐（默认 2 秒）
- 仅在 `queued/running` 时高频轮询，终态后降频或停止

### 5.5 Phase 3 验收
- 运行中步骤实时变化，且与 runId 一致。
- 失败/取消后步骤状态正确落地。

## Phase 4：联调、稳定性与灰度上线
### 6.1 联调清单
- 正常执行：queued -> running -> success
- 失败执行：错误可读且终态正确
- 取消执行：running -> cancelled
- 设备断连：错误归因明确
- 报告预览/下载：路径与权限校验不回归

### 6.2 观测与日志
- backend、runner 双侧日志带 `runId`
- 关键打点：
  - run start/end/cancel
  - progress 更新时间戳
  - 轮询失败次数

### 6.3 灰度策略
1. 测试环境完成 Runner 全链路验证
2. 预发环境进行稳定性压测与故障演练
3. 生产环境全量启用 Runner
4. 异常时执行 Runner 服务版本回滚或流量熔断

### 6.4 回滚策略
- 回滚 Runner 服务到上一稳定版本
- 临时关闭新任务下发（熔断），仅保留状态查询
- 已启动任务按终态收敛后清理

## 7. 任务分解（可直接建工单）
1. Runner 服务脚手架与基础 API（start/progress/cancel/result）
2. Runner 与 Midscene SDK 执行集成（含 onDumpUpdate）
3. backend 配置与 run_service 执行链改造
4. runs 表字段扩展 + schema + progress API
5. frontend RunDetail 结构化步骤展示
6. 联调测试与回归（Runner 单路径）
7. 文档更新（部署、运维、故障处置）

## 8. 测试计划
### 8.1 Backend/Runner 单元测试
- Runner 状态机测试
- cancel 幂等测试
- progress 字段映射测试
- backend 轮询写库测试

### 8.2 集成测试
- 从创建 run 到终态全链路
- 模拟 Runner 500/超时/断开
- Runner 单路径稳定性验证

### 8.3 前端验证
- RunDetail 在运行中展示当前步骤
- 终态后 UI 状态一致
- Android Playground iframe 与步骤信息同屏无冲突

## 9. 时间预估（建议）
- Phase 1：1~2 天
- Phase 2：1~2 天
- Phase 3：0.5~1 天
- Phase 4：1 天
- 合计：3.5~6 天（单人）

## 10. 风险补充与决策点
- 决策点 1：Runner 进度存储是否仅内存（MVP）
  - 建议：MVP 先内存，后续按需落 Redis。
- 决策点 2：progress_json 结构是否完整存 executionDump
  - 建议：DB 存裁剪版，完整 dump 由 Runner 提供临时查询。
- 决策点 3：Runner 服务发布策略（蓝绿/滚动）
  - 建议：先滚动发布，稳定后视情况升级到蓝绿。

## 11. 完成定义（DoD）
- 功能：runId 绑定实时步骤可用。
- 稳定：执行/取消/失败均可收敛终态。
- 兼容：脚本管理、运行列表、报告功能无回归。
- 文档：spec/plan/运行手册更新到位。
- 运维：具备监控、日志、版本回滚路径。

