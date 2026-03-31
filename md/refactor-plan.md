# UIX 精简重构方案

## 1. 重构目标

将当前项目收敛为一个只保留以下能力的前后端应用：

- 脚本管理
- 场景管理
- 任务编排

其余能力全部移除，包括但不限于：

- 运行记录
- 执行能力
- 实时进度
- 报告预览 / 下载
- 设备画面
- runner-service
- android-playground
- docker 相关内容
- AI 生成功能

---

## 2. 最终保留范围

### 前端保留

- `frontend/src/pages/ScriptList.vue`
- `frontend/src/pages/ScriptEditor.vue`
- `frontend/src/pages/SceneList.vue`
- `frontend/src/pages/SceneDetail.vue`
- `frontend/src/components/YamlEditor.vue`
- `frontend/src/components/SceneScriptPicker.vue`
- `frontend/src/api/scripts.ts`（删减后）
- `frontend/src/api/scenes.ts`
- `frontend/src/api/client.ts`
- `frontend/src/config/runtime.ts`（仅保留 API 地址）
- `frontend/src/router/index.ts`（删减后）
- `frontend/src/App.vue`（删减后）

### 后端保留

- `backend/app/api/scripts.py`（删减后）
- `backend/app/api/scenes.py`（删减后）
- `backend/app/services/scene_compiler.py`
- `backend/app/services/yaml_validator.py`
- `backend/app/models/script.py`
- `backend/app/models/script_version.py`
- `backend/app/models/scene.py`
- `backend/app/models/scene_script.py`
- `backend/app/models/scene_task_item.py`
- `backend/app/schemas/script.py`（删减后）
- `backend/app/schemas/scene.py`
- `backend/app/core/config.py`（删减后）
- `backend/app/core/database.py`
- `backend/app/main.py`（删减后）

---

## 3. 需要删除的模块

## 3.1 目录级删除

直接删除：

- `runner-service/`
- `android-playground/`
- `docker/`
- `docker-compose.yml`

## 3.2 脚本级删除

直接删除：

- `scripts/start-runner.sh`
- `scripts/start-android.sh`

---

## 4. 前端重构清单

## 4.1 删除运行域页面

删除：

- `frontend/src/pages/RunList.vue`
- `frontend/src/pages/RunDetail.vue`
- `frontend/src/api/runs.ts`

## 4.2 删除运行相关路由

修改：

- `frontend/src/router/index.ts`

删除路由：

- `/runs`
- `/run/:id`

## 4.3 删除顶部导航中的运行入口

修改：

- `frontend/src/App.vue`

删除：

- “运行列表”按钮
- `isRunsPage`
- `goRuns()`
- 与 `/runs`、`/run/` 相关判断

## 4.4 精简 ScriptEditor

修改：

- `frontend/src/pages/ScriptEditor.vue`

保留：

- 脚本名称编辑
- 来源编辑
- YAML 编辑
- YAML 校验
- 被场景引用展示

删除：

- “执行”按钮
- `runApi` 引用
- AI 生成入口
- `AiGeneratePanel` 组件引用
- `onYamlGenerated()`
- 与运行跳转相关逻辑

## 4.5 精简 SceneDetail

修改：

- `frontend/src/pages/SceneDetail.vue`

保留：

- 场景基础信息编辑
- 关联脚本
- 任务编排
- 任务同步
- 拖拽排序
- 编译预览

删除：

- “执行整个场景”按钮
- `runApi` 引用
- `sceneApi.runScene()` 调用

## 4.6 删除 AI 生成功能

删除：

- `frontend/src/components/AiGeneratePanel.vue`

修改：

- `frontend/src/api/scripts.ts`

删除：

- `GenerateScriptPayload`
- `GenerateScriptResult`
- `generate()`

## 4.7 精简运行时配置

修改：

- `frontend/src/config/runtime.ts`

删除：

- `ANDROID_PLAYGROUND_URL`
- `getAndroidPlaygroundUrl()`
- 相关类型字段

保留：

- `API_BASE_URL`
- `getApiBaseUrl()`

---

## 5. 后端重构清单

## 5.1 删除 runs 域

删除：

- `backend/app/api/runs.py`
- `backend/app/services/run_service.py`
- `backend/app/models/run.py`
- `backend/app/schemas/run.py`

## 5.2 修改应用入口

修改：

- `backend/app/main.py`

删除：

- `runs_router` import
- `app.include_router(runs_router)`
- `run` 模型 import
- `_ensure_runs_columns()`
- 启动时对 `runs` 表的自动补列逻辑

保留：

- scripts / scenes 路由
- 健康检查
- 基础建表逻辑

## 5.3 精简 scenes API

修改：

- `backend/app/api/scenes.py`

删除：

- `create_scene_run`
- `POST /api/scenes/{scene_id}/runs`
- `create_scene_run` / `start_run_async` 相关 import

保留：

- 场景 CRUD
- 脚本关联
- task item 编排
- sync task items
- compiled script preview

## 5.4 精简 scripts API

修改：

- `backend/app/api/scripts.py`
- `backend/app/schemas/script.py`

保留：

- 脚本 CRUD
- 脚本复制
- YAML 校验
- 列出脚本 tasks

删除：

- 与 AI 生成相关的 schema 字段

## 5.5 删除 AI 生成功能

删除：

- `backend/app/api/generate.py`
- `backend/app/services/llm_service.py`

修改：

- `backend/app/main.py`
- `backend/app/schemas/script.py`

删除：

- `generate_router`
- `app.include_router(generate_router)`
- `ScriptGenerateRequest`
- `ScriptGenerateResponse`

## 5.6 精简配置

修改：

- `backend/app/core/config.py`

删除：

- `run_scripts_dir`
- `run_command_prefix`
- `midscene_base_url`
- `midscene_timeout_sec`
- `midscene_status_poll_interval_ms`
- `report_root_dir`
- `llm_base_url`
- `llm_api_key`
- `llm_model_name`
- `llm_timeout_sec`
- `llm_generation_system_prompt`
- `llm_generation_system_prompt_file`
- `midscene_model_base_url`
- `midscene_model_api_key`
- `midscene_model_name`
- `midscene_model_family`

保留：

- `app_name`
- `app_env`
- `database_url`
- 数据库连接池配置

---

## 6. 数据库处理建议

## 6.1 保留表

保留：

- `scripts`
- `script_versions`
- `scenes`
- `scene_scripts`
- `scene_task_items`

## 6.2 删除表

最终删除：

- `runs`

## 6.3 实施建议

建议分两步：

### 第一阶段

- 先删除代码引用
- 先不动数据库表
- 保证前后端能正常跑起来

### 第二阶段

- 再清理 `runs` 表
- 再补 migration 或手动 SQL

这样风险更低。

---

## 7. 文档与说明清理

需要同步修改或删除以下内容中的旧引用：

- `md/architecture-analysis.md`
- `docker/README.md`（若目录未直接删除前）
- 根目录 README（如存在）
- 启动说明
- `.env.example`
- 任何提到以下内容的文档：
  - runner-service
  - android-playground
  - Midscene
  - 执行 / 报告 / 设备预览
  - docker

---

## 8. 推荐实施顺序

## Phase 1：删除外围模块

1. 删除 `runner-service/`
2. 删除 `android-playground/`
3. 删除 `docker/`
4. 删除 `docker-compose.yml`
5. 删除 `scripts/start-runner.sh`
6. 删除 `scripts/start-android.sh`

## Phase 2：删除前端运行域与 AI 功能

1. 删除 `RunList.vue`
2. 删除 `RunDetail.vue`
3. 删除 `frontend/src/api/runs.ts`
4. 删除 `frontend/src/components/AiGeneratePanel.vue`
5. 修改 `frontend/src/router/index.ts`
6. 修改 `frontend/src/App.vue`
7. 修改 `frontend/src/pages/ScriptEditor.vue`
8. 修改 `frontend/src/pages/SceneDetail.vue`
9. 修改 `frontend/src/api/scripts.ts`
10. 修改 `frontend/src/config/runtime.ts`

## Phase 3：删除后端运行域与 AI 功能

1. 删除 `backend/app/api/runs.py`
2. 删除 `backend/app/services/run_service.py`
3. 删除 `backend/app/models/run.py`
4. 删除 `backend/app/schemas/run.py`
5. 删除 `backend/app/api/generate.py`
6. 删除 `backend/app/services/llm_service.py`
7. 修改 `backend/app/main.py`
8. 修改 `backend/app/api/scenes.py`
9. 修改 `backend/app/schemas/script.py`
10. 修改 `backend/app/core/config.py`

## Phase 4：收口与验证

1. 清理无用 import
2. 清理无用类型
3. 清理文档引用
4. 验证脚本 CRUD
5. 验证场景 CRUD
6. 验证任务编排
7. 验证场景编译预览

---

## 9. 重构完成后的系统形态

重构完成后，项目应收敛为一个纯粹的“脚本资产 + 场景编排”系统：

### 前端

- 脚本列表
- 脚本编辑
- 场景列表
- 场景详情
- 任务编排
- 编译预览

### 后端

- scripts API
- scenes API
- scene_compiler
- yaml_validator
- 对应的脚本 / 场景 / task item 数据模型

### 不再包含

- 运行域
- 执行器
- 设备依赖
- 外部执行平台耦合
- docker 运行体系
- AI 生成链路

---

## 10. 结论

本次重构的本质，不是简单删除两个目录，而是将项目从“自动化执行平台”收敛为“脚本与场景编排工具”。

最值得保留的核心能力是：

- Script 资产模型
- Scene 组织模型
- SceneTaskItem 任务快照编排模型
- Scene compiled script 预览能力

这四部分构成了重构后的核心产品价值。
