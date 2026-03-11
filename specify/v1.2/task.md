# v1.2.0 任务拆解（task）

## 1. 说明
本文档将 `v1.2/plan.md` 落地为可执行任务清单，范围聚焦“场景列表 + 场景关联脚本”。

任务状态建议：`TODO` / `DOING` / `DONE` / `BLOCKED`
优先级建议：`P0`（必须）/ `P1`（重要）/ `P2`（优化）

---

## 2. 功能实现状态总览

| 里程碑 | 目标 | 当前实现状态 | 备注 |
|---|---|---|---|
| Milestone A | 后端场景模型与 API | DONE | 已完成模型、CRUD、关联 API 与测试 |
| Milestone B | 前端场景管理页面 | DONE | 已完成导航、场景列表、详情、脚本选择 |
| Milestone C | 脚本与场景联动增强 | DONE | 已补充脚本引用数与删除提示 |
| Milestone D | 联调验证与文档收敛 | DOING | 已完成自动化验证，手工联调记录待补 |

> 当前已具备的前置能力：
> 1. 脚本 CRUD 已可用。
> 2. 运行列表与运行详情已可用。
> 3. 顶部导航目前包含“脚本列表 / 运行列表”。
> 4. 本期默认不改造现有脚本运行链路，只新增场景组织层。

---

## 3. Milestone A：后端场景模型与 API（P0）

当前目标：
1. 新增场景主表与场景脚本关联表。
2. 提供场景 CRUD 和关联脚本维护 API。
3. 保证现有脚本与运行相关接口不回归。

## A1. 新增 Scene / SceneScript 数据模型
- 优先级：P0
- 状态：DONE
- 目标：建立场景与脚本的多对多关联关系。
- 产出：
  - `backend/app/models/scene.py`
  - `backend/app/models/scene_script.py`
  - `backend/app/models/__init__.py`
- 关键点：
  - `Scene` 包含 `name/description/source_type/created_at/updated_at`
  - `SceneScript` 包含 `scene_id/script_id/sort_order/remark/created_at`
  - 外键关系清晰，支持脚本复用
- 验收：
  - 本地建表成功
  - 一个脚本可被多个场景关联
  - 删除场景不删除脚本

## A2. 新增 Scene 相关 schema
- 优先级：P0
- 状态：DONE
- 目标：定义场景列表、详情、创建、更新、关联项读写结构。
- 产出：
  - `backend/app/schemas/scene.py`
- 关键点：
  - 列表响应包含 `script_count`
  - 详情响应包含关联脚本信息
  - 请求结构尽量与现有 `scripts` 风格保持一致
- 验收：
  - 接口请求/响应结构可支持前端列表与详情页

## A3. 实现场景 CRUD API
- 优先级：P0
- 状态：DONE
- 目标：提供场景的基础增删改查能力。
- 产出：
  - `backend/app/api/scenes.py`
  - `backend/app/main.py`
- API：
  - `GET /api/scenes`
  - `POST /api/scenes`
  - `GET /api/scenes/{scene_id}`
  - `PUT /api/scenes/{scene_id}`
  - `DELETE /api/scenes/{scene_id}`
- 验收：
  - 可创建、编辑、删除、查询场景
  - 返回字段满足前端展示要求

## A4. 实现场景关联脚本 API
- 优先级：P0
- 状态：DONE
- 目标：支持为场景添加脚本、编辑备注、调整顺序、移除脚本。
- 产出：
  - `backend/app/api/scenes.py`
  - 必要时 `backend/app/services/scene_service.py`
- API：
  - `POST /api/scenes/{scene_id}/scripts`
  - `PUT /api/scenes/{scene_id}/scripts/{relation_id}`
  - `DELETE /api/scenes/{scene_id}/scripts/{relation_id}`
- 关键点：
  - 同一场景内默认不重复添加相同脚本
  - `sort_order` 由后端兜底补齐
- 验收：
  - 可向场景添加多个脚本
  - 可修改顺序和备注
  - 可单独移除关联项

## A5. 后端测试与回归保护
- 优先级：P1
- 状态：DONE
- 目标：为新增模型和接口补齐聚焦测试。
- 产出：
  - `backend/tests/test_scenes_api.py`
- 覆盖点：
  - 场景 CRUD
  - 场景脚本关联增删改
  - 同一脚本被多个场景复用
  - 删除场景不影响脚本
- 验收：
  - `cd backend && uv run pytest` 通过

---

## 4. Milestone B：前端场景管理页面（P0）

当前目标：
1. 新增“场景列表”导航入口。
2. 新增场景列表页与场景详情页。
3. 实现场景内脚本关联与排序管理。

## B1. 新增 scenes API 封装
- 优先级：P0
- 状态：DONE
- 目标：封装场景相关接口，供页面复用。
- 产出：
  - `frontend/src/api/scenes.ts`
- 方法建议：
  - `list`
  - `detail`
  - `create`
  - `update`
  - `remove`
  - `addScript`
  - `updateSceneScript`
  - `removeSceneScript`
- 验收：
  - 前端能通过统一 API 模块访问场景后端接口

## B2. 顶部导航与路由改造
- 优先级：P0
- 状态：DONE
- 目标：将“场景列表”接入现有导航体系。
- 产出：
  - `frontend/src/App.vue`
  - `frontend/src/router/index.ts` 或对应路由文件
- 关键点：
  - 导航改为“场景列表 / 脚本列表 / 运行列表”
  - 场景页高亮状态正确
- 验收：
  - 路由跳转正常
  - 三个列表入口都可访问

## B3. 开发场景列表页
- 优先级：P0
- 状态：DONE
- 目标：提供场景总览与基础操作入口。
- 产出：
  - `frontend/src/pages/SceneList.vue`
- 展示字段：
  - 场景名称
  - 脚本数
  - 来源
  - 更新时间
  - 操作
- 交互：
  - 新建场景
  - 进入详情
  - 删除场景
- 验收：
  - 列表可加载
  - 新建、删除、跳转详情可用

## B4. 开发场景详情页
- 优先级：P0
- 状态：DONE
- 目标：支持编辑场景基本信息并管理关联脚本。
- 产出：
  - `frontend/src/pages/SceneDetail.vue`
- 页面内容：
  - 基本信息表单
  - 关联脚本列表
  - 添加脚本入口
- 关键点：
  - 备注可编辑
  - 顺序可调整
  - 保存后页面可回显
- 验收：
  - 场景详情信息可编辑保存
  - 关联脚本列表可维护

## B5. 开发脚本选择弹窗/组件
- 优先级：P1
- 状态：DONE
- 目标：在场景详情中复用现有脚本资产进行关联。
- 产出：
  - `frontend/src/components/SceneScriptPicker.vue`
- 交互建议：
  - 支持按脚本名称搜索
  - 选择已有脚本后回填到场景
  - 默认过滤已关联脚本
- 验收：
  - 用户可从已有脚本中快速选择并添加到场景

## B6. 前端构建与页面回归
- 优先级：P1
- 状态：DONE
- 目标：确保新增页面不破坏现有前端构建和主流程。
- 验收：
  - `cd frontend && npm run build` 通过
  - 脚本列表与运行列表可正常访问

---

## 5. Milestone C：脚本与场景联动增强（P1）

当前目标：
1. 让用户在脚本视角知道该脚本是否被场景引用。
2. 为删除风险提供明确提示，减少误操作。

## C1. 脚本列表增加“所属场景数”列
- 优先级：P1
- 状态：DONE
- 目标：在现有脚本列表页展示脚本被引用情况。
- 影响文件：
  - `frontend/src/pages/ScriptList.vue`
  - 对应后端 `scripts` 列表接口或新增聚合字段
- 验收：
  - 列表可展示每个脚本的场景引用数

## C2. 脚本删除提示增强
- 优先级：P1
- 状态：DONE
- 目标：在删除被引用脚本时给出影响提示。
- 影响文件：
  - `frontend/src/pages/ScriptList.vue`
  - 必要时后端删除接口返回引用信息
- 验收：
  - 被场景引用的脚本删除前有明确提示

## C3. 删除策略落地
- 优先级：P1
- 状态：DONE
- 目标：明确脚本删除时关联关系的处理方式。
- 方案建议：
  - 首期采用“强提示 + 允许删除”
  - 删除脚本时同步清理 `scene_scripts` 关联
- 验收：
  - 删除脚本后数据一致
  - 场景详情不会出现失效脚本关联

---

## 6. Milestone D：联调、验收与文档收敛（P0）

当前目标：
1. 完成场景模块从后端到前端的全链路联调。
2. 确认脚本与运行相关能力无回归。
3. 收敛本期文档与验证记录。

## D1. 全链路联调
- 优先级：P0
- 状态：DOING
- 目标：完成场景创建、脚本关联、编辑、删除全链路验证。
- 验收场景：
  - 创建场景并编辑基本信息
  - 添加多个脚本并调整顺序
  - 删除场景不影响脚本
  - 删除脚本后场景关联处理正确

## D2. 回归验证
- 优先级：P0
- 状态：DONE
- 目标：确认旧功能不受本次改动影响。
- 回归范围：
  - 脚本列表 CRUD
  - 脚本详情编辑
  - 运行列表
  - 单脚本执行
- 验收：
  - 核心旧功能均可正常使用

## D3. 文档更新
- 优先级：P1
- 状态：DONE
- 目标：收敛本期需求、计划与任务文档。
- 产出：
  - `specify/v1.2/plan.md`
  - `specify/v1.2/task.md`
  - 若后续补充需求文档，可新增 `specify/v1.2/spec.md`
- 验收：
  - 文档内容与实际实现保持一致

---

## 7. 建议执行顺序
1. 先完成 Milestone A，确保场景数据模型和 API 稳定。
2. 再完成 Milestone B，让前端可用并尽快形成可联调页面。
3. 然后完成 Milestone C，补齐脚本侧提示和风险控制。
4. 最后执行 Milestone D，完成回归验证与文档收敛。

## 8. 风险与阻塞点
1. 若当前数据库初始化主要依赖 `create_all`，新增表后需确认历史环境升级路径。
2. 若脚本删除策略未提前定清，前后端会在“阻止删除”还是“允许删除并清关联”上反复返工。
3. 若场景详情页首期就引入拖拽排序，交互复杂度和状态同步成本会明显上升。
4. 若后续要支持“运行整个场景”，需额外设计 `scene_runs`，本期应避免提前耦合到 `runs` 主链路。

## 9. 交付物清单
1. 后端场景相关模型、schema、API 与测试。
2. 前端场景列表页、场景详情页、脚本选择组件。
3. 顶部导航改造。
4. 脚本与场景联动提示增强。
5. v1.2 文档与验证记录。
