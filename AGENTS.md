# AGENTS.md

本文件用于定义编码代理在本仓库中的工作方式。

## 适用范围
- 仓库根目录：`/Users/yaohongliang/work/liuyao/AI/UI/uix`
- 主要模块：
  - `backend`：FastAPI + SQLAlchemy（Python 3.11+，使用 `uv` 管理）
  - `frontend`：Vue 3 + Vite + TypeScript
  - `specify`：产品文档、计划与运行手册

## 目标
- 以最小改动完成任务。
- 除非任务明确要求改变行为，否则保持现有行为稳定。
- 优先修复根因，避免表面性补丁。

## 修改边界
- 允许修改：
  - `backend/**`
  - `frontend/**`
  - `runner-service/**`
  - `android-playground/**`
  - 任务需要的小范围配置文件
  - 与任务相关的 `specify/**` 文档
- 需要谨慎：
  - `backend/.env`（不得覆盖用户密钥或敏感配置）
  - 锁文件（`uv.lock`、`package-lock.json`），除非任务明确涉及依赖变更
- 禁止：
  - 删除无关代码
  - 非必要地重命名或移动文件
  - 未经要求引入新的框架或工具链

## 安装与运行
### 后端
- 安装依赖：`cd backend && uv sync`
- 启动开发服务：`cd backend && uv run uvicorn app.main:app --reload --port 8000`

### 前端
- 安装依赖：`cd frontend && npm install`
- 启动开发服务：`cd frontend && npm run dev`
- 构建：`cd frontend && npm run build`

## 校验规则
代码变更后应执行与改动相关的校验。

- 后端改动：
  - 执行：`cd backend && uv run pytest`
  - 若相关逻辑缺少测试，在可行时补充聚焦测试。

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

## API 与数据安全
- 除非任务明确要求，保持 API 契约向后兼容。
- 若请求/响应结构变更，需同步更新 `specify/` 相关文档。
- 未经明确要求，不执行破坏性数据库操作。

## 交付输出要求
任务完成时需说明：
- 修改了什么（文件与意图）
- 执行了哪些命令
- 测试/构建结果
- 存在的假设或风险

## 提交规范
- 一个任务对应一个聚焦提交。 提交commit使用中文
- 提交信息建议前缀：
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `refactor: ...`
  - `test: ...`
