# 可视化 YAML 脚本平台技术实现方案（plan.md）

## 1. 方案概述
本方案基于 `spe.md`，目标是实现可视化 YAML 脚本闭环：
1. 手动编写 YAML。
2. 自然语言生成 YAML。
3. 页面触发执行 YAML（调用 Midscene CLI）。
4. 直接复用 Midscene 生成的 HTML 报告并回显。

技术栈约束：
1. 前端：Vue 3。
2. 后端：Python。
3. Python 依赖与运行：`uv` 管理。

## 2. 总体架构

### 2.1 架构分层
1. Web 前端（Vue 3 + Vite）：脚本管理、编辑、执行与报告查看。
2. API 服务（FastAPI）：脚本 CRUD、AI 生成接口、执行任务编排、日志与报告查询。
3. 任务执行层（Runner）：调用 `npx midscene <yaml>` 执行脚本，采集状态与日志。
4. 数据层（SQLite/PostgreSQL）：存储脚本、版本、运行记录。
5. 文件层（本地目录）：保存 YAML 脚本文件与 Midscene 报告路径映射。

### 2.2 关键设计原则
1. 报告不自研：仅透传 Midscene 报告路径并提供预览/下载。
2. 执行异步化：接口快速返回 `runId`，前端轮询或 SSE 获取状态。
3. 脚本与运行解耦：脚本可多次执行，运行记录独立存储。
4. 错误可观测：统一错误码、结构化日志、关键操作审计。

## 3. 技术选型

### 3.1 前端
1. Vue 3 + TypeScript + Vite。
2. UI：Element Plus（或 Naive UI，二选一）。
3. 编辑器：Monaco Editor（YAML 高亮、行号、错误标注）。
4. 状态管理：Pinia。
5. 请求层：Axios。

### 3.2 后端
1. FastAPI + Pydantic。
2. SQLAlchemy 2.x + Alembic。
3. 数据库：
- 开发：SQLite。
- 生产：PostgreSQL。
4. YAML 校验：`PyYAML` + 自定义 schema 规则校验。
5. 执行任务：Python `asyncio` + `subprocess`（V1 单机串行/有限并发）。
6. LLM 调用：封装 Provider Adapter（OpenAI 兼容协议优先）。

### 3.3 环境与依赖管理（uv）
1. `uv init` 初始化 Python 项目。
2. `uv add fastapi uvicorn sqlalchemy alembic pydantic pyyaml httpx`。
3. `uv run uvicorn app.main:app --reload` 启动服务。
4. 用 `.env` 管理模型 key、Midscene 执行目录、报告目录等配置。

## 4. 目录结构建议

```text
ui_demo/
  frontend/
    src/
      pages/
        ScriptList.vue
        ScriptEditor.vue
        RunDetail.vue
      components/
        YamlEditor.vue
        AiGeneratePanel.vue
        RunStatusBadge.vue
      api/
      stores/
  backend/
    app/
      main.py
      core/
        config.py
        errors.py
      api/
        scripts.py
        runs.py
        generate.py
      models/
        script.py
        run.py
        script_version.py
      services/
        script_service.py
        yaml_validator.py
        llm_service.py
        run_service.py
        midscene_runner.py
      repositories/
      schemas/
      workers/
        run_worker.py
    migrations/
    pyproject.toml
    .env.example
  specify/
    spe.md
    plan.md
```

## 5. 核心模块设计

### 5.1 脚本管理模块
功能：新建、编辑、保存、删除、复制、版本快照。

实现要点：
1. 脚本内容以文本存 DB，执行前落盘到工作目录。
2. 每次保存自动写入 `script_versions`（保留最近 10 版，超出清理最早版本）。
3. 支持模板初始化（默认 YAML 骨架）。

### 5.2 YAML 校验模块
分两层：
1. 语法层：YAML parse。
2. 规则层：检查关键字段（如 `android.deviceId`、`tasks` 非空）。

返回结构：`line`、`column`、`message`，前端可直接定位错误。

### 5.3 AI 生成 YAML 模块
流程：
1. 接收自然语言 + 可选参数（设备 ID、语言、模型）。
2. 拼接系统提示词（强约束输出 YAML，仅返回代码块）。
3. 解析模型输出并做 YAML 校验。
4. 校验通过才返回编辑器，否则返回“生成失败+原因”。

### 5.4 执行模块（Midscene Runner）
流程：
1. 创建运行记录（`queued`）。
2. 将脚本写入临时 YAML 文件。
3. 执行命令：`npx midscene <yaml_path>`。
4. 持续采集 stdout/stderr，写入 run log。
5. 从输出中提取报告路径与 summary 文件路径。
6. 更新运行状态为 `success`/`failed`。

状态机：
1. `queued`
2. `running`
3. `success`
4. `failed`
5. `cancelled`

### 5.5 报告回显模块
1. 报告文件来源：Midscene 产出的 HTML 文件。
2. 后端提供报告读取接口（校验路径必须在允许目录内，防止路径穿越）。
3. 前端支持：
- 新窗口打开报告。
- 页面内 iframe 预览。
- 下载原始 html 文件。

## 6. API 设计（V1）

### 6.1 Scripts
1. `POST /api/scripts`：创建脚本。
2. `GET /api/scripts`：分页列表。
3. `GET /api/scripts/{id}`：详情。
4. `PUT /api/scripts/{id}`：更新。
5. `DELETE /api/scripts/{id}`：删除。
6. `POST /api/scripts/{id}/validate`：校验 YAML。
7. `POST /api/scripts/{id}/copy`：复制脚本。

### 6.2 AI Generate
1. `POST /api/scripts/generate`
- 入参：`prompt`, `deviceId`, `language`, `model`。
- 出参：`yaml`, `warnings`。

### 6.3 Runs
1. `POST /api/runs`：发起执行。
2. `GET /api/runs/{id}`：运行详情（状态、耗时、错误、报告路径）。
3. `GET /api/runs/{id}/logs`：日志分页或增量拉取。
4. `POST /api/runs/{id}/cancel`：取消任务。
5. `GET /api/runs/{id}/report`：返回报告访问地址。

## 7. 数据库设计（V1）

### 7.1 scripts
1. `id` (PK)
2. `name`
3. `content`
4. `source_type` (`manual`/`ai`)
5. `created_at`
6. `updated_at`

### 7.2 script_versions
1. `id` (PK)
2. `script_id` (FK)
3. `version_no`
4. `content`
5. `created_at`

### 7.3 runs
1. `id` (PK)
2. `script_id` (FK)
3. `status`
4. `started_at`
5. `ended_at`
6. `duration_ms`
7. `log_path`（或日志文本分表）
8. `report_path`
9. `summary_path`
10. `error_message`

## 8. 前端页面设计

### 8.1 脚本列表页
1. 列表列：名称、来源、更新时间、最近执行状态。
2. 操作：新建、复制、删除、进入编辑。

### 8.2 脚本编辑页
1. 左侧参数：设备 ID、模型、语言。
2. 右侧 Monaco YAML 编辑器。
3. 顶部操作：保存、校验、执行、AI 生成。
4. 底部提示：语法错误定位、规则校验结果。

### 8.3 执行详情页
1. 状态卡片：`queued/running/success/failed`。
2. 日志窗口：增量刷新。
3. 报告窗口：iframe 预览 + 下载按钮。
4. 历史执行记录侧栏。

## 9. 安全与稳定性
1. API Key 仅后端持有，前端不暴露。
2. 报告访问做目录白名单限制。
3. 执行命令参数固定模板，避免命令注入。
4. 运行超时控制（例如 15 分钟可配置）。
5. 任务互斥策略（V1 每设备同一时间仅一个任务）。

## 10. 开发计划（按 3.5 周）

### M1（第 1 周）
1. 初始化前后端工程。
2. 完成脚本 CRUD + YAML 编辑器接入。
3. 完成 YAML 语法/规则校验。

### M2（第 2 周）
1. 打通执行链路（FastAPI -> Midscene Runner）。
2. 完成运行状态、日志、取消执行。
3. 完成运行记录持久化。

### M3（第 3 周）
1. 接入 LLM 生成 YAML。
2. 完成报告预览与下载（复用 Midscene HTML）。
3. 完成异常处理与错误码。

### M4（第 3.5 周）
1. 联调与回归。
2. 性能与稳定性验收。
3. 交付文档与部署说明。

## 11. 验收清单
1. 手动创建 YAML 可保存、可校验、可执行。
2. 自然语言生成 YAML 可回填编辑器并通过基础校验。
3. 执行后可查看 Midscene 报告并下载。
4. 失败场景有明确错误信息与日志。
5. 刷新页面后能恢复运行状态与历史记录。

## 12. 后续扩展（V2）
1. 多设备任务队列与并发调度。
2. 脚本标签、检索、收藏。
3. CI 触发执行（Webhook）。
4. 团队权限与审计日志。
