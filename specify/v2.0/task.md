# v2.0 任务拆解（task）

## 1. 说明
本文档将 `v2.0/spec.md` 与 `v2.0/plan.md` 落地为可执行任务清单，默认采用 Runner 单路径（不保留 legacy 模式）。

任务状态建议：`TODO` / `DOING` / `DONE` / `BLOCKED`
优先级建议：`P0`（必须）/ `P1`（重要）/ `P2`（优化）

---

## 2. Milestone A：Runner 服务 MVP（P0）

## A1. 初始化 runner-service 工程
- 优先级：P0
- 状态：TODO
- 目标：完成可运行的 Node + TypeScript 服务骨架。
- 产出：
  - `runner-service/package.json`
  - `runner-service/tsconfig.json`
  - `runner-service/src/server.ts`
  - `runner-service/src/config.ts`
- 验收：
  - 本地可启动，`/health` 返回 200。

## A2. 定义 Runner 领域模型与内存状态管理
- 优先级：P0
- 状态：TODO
- 目标：建立 run 生命周期模型与内存存储结构。
- 产出：
  - `runner-service/src/types.ts`
  - `runner-service/src/services/run-manager.ts`
- 关键点：
  - 状态：`queued/running/success/failed/cancelled`
  - 字段：`currentTask/currentAction/completed/total/executionDump/updatedAt`
- 验收：
  - 单元测试覆盖状态转移与幂等更新。

## A3. 集成 Midscene 执行能力（runYaml + onDumpUpdate）
- 优先级：P0
- 状态：TODO
- 目标：可执行 YAML 并持续产出结构化进度。
- 产出：
  - `runner-service/src/services/yaml-runner.ts`
- 关键点：
  - 使用 `@midscene/android` 创建 agent
  - 调用 `agent.runYaml(yamlContent)`
  - 监听 `agent.onDumpUpdate`
  - 从 dump 计算 `currentTask/currentAction/completed/total`
- 验收：
  - 执行中 `progress` 持续变化；终态结果准确。

## A4. 实现 Runner API
- 优先级：P0
- 状态：TODO
- 目标：暴露标准接口。
- 产出：
  - `POST /runs/start`
  - `GET /runs/:runId/progress`
  - `POST /runs/:runId/cancel`
  - `GET /runs/:runId/result`
- 验收：
  - curl 全链路通过（start -> progress -> result）
  - cancel 幂等可重复调用。

## A5. Runner 基础测试与日志
- 优先级：P1
- 状态：TODO
- 目标：具备最小可维护性。
- 产出：
  - 单元测试（状态机、取消、进度映射）
  - 关键日志（runId、状态变化、异常）
- 验收：
  - 核心测试通过。

---

## 3. Milestone B：ui_demo backend 接入 Runner（P0）

## B1. backend 配置扩展
- 优先级：P0
- 状态：TODO
- 目标：支持 Runner 连接配置。
- 影响文件：
  - `backend/app/core/config.py`
  - `backend/.env.example`
- 配置项：
  - `RUNNER_BASE_URL`
  - `RUNNER_TIMEOUT_SEC`
  - `RUNNER_PROGRESS_POLL_INTERVAL_MS`
- 验收：
  - 启动时配置可读取且有默认值。

## B2. runs 数据模型扩展
- 优先级：P0
- 状态：TODO
- 目标：持久化结构化进度快照。
- 影响文件：
  - `backend/app/models/run.py`
  - `backend/app/schemas/run.py`
  - （如启用）迁移脚本
- 字段：
  - `current_task` / `current_action` / `progress_json`
- 验收：
  - 读写正常，旧数据兼容。

## B3. run_service 执行链替换为 Runner 调用
- 优先级：P0
- 状态：TODO
- 目标：移除直接 `subprocess npx midscene` 主路径，改为 Runner API 驱动。
- 影响文件：
  - `backend/app/services/run_service.py`
- 子任务：
  - 创建 run 后调用 `POST /runs/start`
  - 后台线程轮询 `/progress` 更新数据库
  - 终态时调用 `/result` 写入 `report_path/summary_path/error_message`
- 验收：
  - run 状态可从 queued -> running -> 终态正确收敛。

## B4. 取消执行链路改造
- 优先级：P0
- 状态：TODO
- 目标：取消操作通过 Runner 生效。
- 影响文件：
  - `backend/app/services/run_service.py`
  - `backend/app/api/runs.py`
- 验收：
  - `POST /api/runs/{id}/cancel` 可终止 Runner 任务并正确落库 `cancelled`。

## B5. 新增进度查询 API
- 优先级：P0
- 状态：TODO
- 目标：提供前端稳定读取接口。
- 影响文件：
  - `backend/app/api/runs.py`
  - `backend/app/schemas/run.py`
- API：
  - `GET /api/runs/{id}/progress`
- 验收：
  - 返回字段完整：`status/current_task/current_action/progress_json`。

## B6. backend 回归测试
- 优先级：P1
- 状态：TODO
- 目标：保障 runs 相关功能无回归。
- 验收：
  - `scripts` CRUD 不受影响
  - `runs` 列表/详情/日志/报告仍可用
  - 新增 progress 接口测试通过

---

## 4. Milestone C：frontend 展示当前步骤（P0）

## C1. 前端 API 扩展
- 优先级：P0
- 状态：TODO
- 目标：封装 progress 查询。
- 影响文件：
  - `frontend/src/api/runs.ts`
- 验收：
  - `runApi.progress(runId)` 可用。

## C2. RunDetail 增加结构化步骤面板
- 优先级：P0
- 状态：TODO
- 目标：在运行详情展示 runId 绑定步骤。
- 影响文件：
  - `frontend/src/pages/RunDetail.vue`
- 展示内容：
  - 当前任务
  - 当前动作
  - 完成度（completed/total）
  - 最近步骤（可选）
- 验收：
  - 运行中页面每 2s 可见步骤更新。

## C3. 前端轮询优化
- 优先级：P1
- 状态：TODO
- 目标：减少无效请求。
- 规则：
  - queued/running：保持高频轮询
  - success/failed/cancelled：降频或停止
- 验收：
  - 终态后请求量明显下降。

## C4. UI 联动体验优化（可选）
- 优先级：P2
- 状态：TODO
- 目标：提升可读性。
- 内容：
  - 当前步骤高亮
  - 错误步骤突出显示
  - 与实时日志区域联动定位

---

## 5. Milestone D：联调、发布与运维（P0）

## D1. 联调用例执行
- 优先级：P0
- 状态：TODO
- 用例：
  - 正常执行成功
  - 执行失败
  - 运行中取消
  - 设备断连异常
- 验收：
  - 状态、步骤、日志、报告一致。

## D2. Runner 发布流程
- 优先级：P0
- 状态：TODO
- 目标：分环境发布（测试 -> 预发 -> 生产）。
- 验收：
  - 每环境有通过记录与回归结果。

## D3. 故障处置与回滚预案
- 优先级：P0
- 状态：TODO
- 目标：明确失败时如何止损。
- 方案：
  - Runner 版本回滚
  - 任务下发熔断（暂停新任务，仅保留查询）
- 验收：
  - 演练一次并记录结果。

## D4. 文档收敛
- 优先级：P1
- 状态：TODO
- 目标：更新运行手册与部署说明。
- 产出：
  - Runner 启动方式
  - 配置说明
  - 常见故障排查

---

## 6. 并行建议
- 可并行 1：A1/A2 与 B1/B2 可并行。
- 可并行 2：A4 完成后，B3 与 C1 可并行。
- 可并行 3：C2 与 D1（部分用例）可并行。

---

## 7. 验收总表（Checklist）
- [ ] Runner 服务 API 全部可用。
- [ ] run 生命周期与步骤进度稳定。
- [ ] 取消执行幂等且可观察。
- [ ] 前端运行详情可见 runId 绑定步骤。
- [ ] Android 画面 + 当前步骤 + 日志同屏联动可用。
- [ ] 文档与运维预案完整。

---

## 8. 预估工期（单人）
- Milestone A：1~2 天
- Milestone B：1~2 天
- Milestone C：0.5~1 天
- Milestone D：1 天
- 合计：3.5~6 天

