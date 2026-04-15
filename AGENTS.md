# AGENTS.md

本文件用于定义编码代理在本仓库中的工作方式。

## 适用范围
- 仓库根目录：`/Users/yaohongliang/work/liuyao/AI/UI/uix`
- 主要模块：
  - `backend`：FastAPI + SQLAlchemy（Python 3.11+，使用 `uv` 管理，当前仍是生产联调基线）
  - `backend-ts`：Fastify + TypeScript + Prisma + Zod（Node.js 20+，迁移主线）
  - `frontend`：Vue 3 + Vite + TypeScript

## 目标
- 以最小改动完成任务。
- 除非任务明确要求改变行为，否则保持现有行为稳定。
- 优先修复根因，避免表面性补丁。

## 安装与运行
### 后端
- 安装依赖：`cd backend && uv sync`
- 启动开发服务：`cd backend && uv run uvicorn app.main:app --reload --port 8000`

### 后端（TypeScript 迁移版）
- 安装依赖：`cd backend-ts && npm install`
- 启动开发服务：`cd backend-ts && npm run dev`
- 构建：`cd backend-ts && npm run build`

### 前端
- 安装依赖：`cd frontend && npm install`
- 启动开发服务：`cd frontend && npm run dev`
- 构建：`cd frontend && npm run build`

## 校验规则
代码变更后应执行与改动相关的校验。

- 后端改动：
  - 执行：`cd backend && uv run pytest`
  - 若相关逻辑缺少测试，在可行时补充聚焦测试。

- TypeScript 后端改动：
  - 迁移目标优先落在 `backend-ts`，`backend` 仅作为行为对照与回退基线。
  - 执行：`cd backend-ts && npm run build`
  - 若已引入类型校验脚本，执行：`cd backend-ts && npm run check`
  - 若修改 Prisma schema，执行：`cd backend-ts && npm run prisma:generate`
  - 迁移核心执行链路时，需补充与 Python 行为一致的对照验证，至少覆盖：
    - YAML 输入到 task snapshot 的编排结果
    - 输入变量绑定与未解析变量报错
    - `respMsg` / `response` 响应取值兼容
    - 数组路径绑定

- 前端改动：
  - 执行：`cd frontend && npm run build`
  - 若涉及高风险 UI 行为，需提供手工验证步骤。

- 全栈改动：
  - 同时满足后端与前端校验要求。

## 代码风格
- 优先清晰、小而专注的函数，避免过度抽象。
- 命名与现有代码保持一致。
- 仅在逻辑不直观时添加简洁注释。
- 避免与任务无关的大规模重构。
- 关键节点加入日志和中文备注，方便调试和理解。
- 后端迁移到 TypeScript 时，优先“并行迁移”而不是直接覆盖 Python 后端。
- 迁移顺序应优先保持 API 路径、请求结构、响应结构兼容，再替换内部实现。
- `backend-ts` 默认使用不同端口，避免直接覆盖 Python `backend` 的 `8000`。
- 不要删除 Python `backend` 目录，除非用户明确要求结束并行迁移。



## 交付输出要求
任务完成时需说明：
- 修改了什么（文件与意图）
- 执行了哪些命令
- 测试/构建结果
- 存在的假设或风险

## 提交规范
- 一个任务对应一个聚焦提交。 提交commit使用中文
- 不提交本地 `.env`、抓包文件、测试数据库、`dist/` 等运行产物。
- 提交信息建议前缀：
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `refactor: ...`
  - `test: ...`

## GitHub Issue 规范
- 若任务涉及创建 GitHub issue，默认使用中文标题与中文正文。
- issue 标题应简洁明确，建议前缀：
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `refactor: ...`
  - `test: ...`
- issue 正文建议包含以下小节：
  - `背景`
  - `问题现象`
  - `期望行为`
  - `建议方案`
  - `影响范围`
  - `补充说明`（可选）
- 除非用户明确要求，否则不要默认使用英文 issue 模板。
