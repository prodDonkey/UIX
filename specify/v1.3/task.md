# v1.3.0 任务拆解（task）

## 1. 说明
本文档将 `v1.3/plan.md` 落地为可执行任务清单，范围聚焦“场景任务级执行编排”。

任务状态建议：`TODO` / `DOING` / `DONE` / `BLOCKED`
优先级建议：`P0`（必须）/ `P1`（重要）/ `P2`（优化）

---

## 2. 功能实现状态总览

| 里程碑 | 目标 | 当前实现状态 | 备注 |
|---|---|---|---|
| Milestone A | 后端任务编排模型与解析能力 | DONE | 已完成任务模型、解析接口、编排 CRUD、编译接口与测试 |
| Milestone B | 前端场景详情页任务编排 UI | DONE | 已完成任务选择、编排列表、备注、预览交互 |
| Milestone C | 场景运行接入现有 run 系统 | DONE | 已支持执行整个场景，并在运行详情展示来源场景 |
| Milestone D | 联调验证与文档收敛 | DOING | 自动化校验已完成，手工验收记录与补充文档待收敛 |

> 当前已具备的前置能力：
> 1. 场景已支持按顺序关联多个脚本。
> 2. 脚本 YAML 编辑与单脚本执行已可用。
> 3. 运行详情页已支持查看运行时脚本快照。
> 4. 当前缺失的是“任务级编排”和“场景执行”。

---

## 3. Milestone A：后端任务编排模型与解析能力（P0）

当前目标：
1. 建立场景任务编排数据模型。
2. 提供脚本任务解析 API。
3. 提供场景任务编排 CRUD 和编译能力。

## A1. 新增 SceneTaskItem 数据模型
- 优先级：P0
- 状态：DONE
- 目标：为场景保存任务级编排项。
- 产出：
  - `backend/app/models/scene_task_item.py`
  - `backend/app/models/__init__.py`
- 建议字段：
  - `scene_id`
  - `script_id`
  - `scene_script_id`（可选）
  - `task_index`
  - `task_name_snapshot`
  - `task_content_snapshot`
  - `sort_order`
  - `remark`
  - `created_at`
- 验收：
  - 可建立一对多的场景任务编排关系
  - 单个场景可保存多个任务片段

## A2. 新增 Task 编排相关 schema
- 优先级：P0
- 状态：DONE
- 目标：定义任务解析结果、编排项读写结构、编译结果结构。
- 产出：
  - `backend/app/schemas/scene_task_item.py` 或合并到 `scene.py`
- 验收：
  - 前端可直接消费脚本任务列表和场景编排项

## A3. 实现脚本任务解析接口
- 优先级：P0
- 状态：DONE
- 目标：解析脚本 YAML 中的 `tasks[]` 并返回任务列表。
- 产出：
  - `GET /api/scripts/{script_id}/tasks`
- 返回建议：
  - `task_index`
  - `task_name`
  - `flow`
  - `continue_on_error`
- 验收：
  - 可从任意合法脚本提取任务列表
  - 非法 YAML 时返回明确错误

## A4. 实现场景任务编排 CRUD
- 优先级：P0
- 状态：DONE
- 目标：支持向场景添加任务项、调整顺序、编辑备注、删除编排项。
- API：
  - `GET /api/scenes/{scene_id}/task-items`
  - `POST /api/scenes/{scene_id}/task-items`
  - `PUT /api/scenes/{scene_id}/task-items/{item_id}`
  - `DELETE /api/scenes/{scene_id}/task-items/{item_id}`
- 验收：
  - 场景编排项可正确增删改查
  - 顺序调整后可持久化

## A5. 实现场景编译接口
- 优先级：P0
- 状态：DONE
- 目标：将场景编排项拼装成最终 YAML。
- API：
  - `GET /api/scenes/{scene_id}/compiled-script`
- 关键点：
  - 任务按 `sort_order` 拼接
  - 环境头可复用首个脚本配置
  - 对冲突配置给出提示或约束
- 验收：
  - 可稳定输出合法 YAML

## A6. 后端测试与回归保护
- 优先级：P1
- 状态：DONE
- 目标：补齐任务级编排相关测试。
- 覆盖点：
  - 脚本任务解析
  - 场景任务编排增删改
  - 编译 YAML 正确性
  - 非法 YAML 与冲突边界
- 验收：
  - `cd backend && uv run pytest` 通过

---

## 4. Milestone B：前端场景详情页任务编排 UI（P0）

当前目标：
1. 在现有场景详情页中新增“执行编排”区域。
2. 支持从关联脚本中选择 task。
3. 支持维护场景编排顺序与备注。

## B1. 扩展 scenes API 封装
- 优先级：P0
- 状态：DONE
- 目标：补齐任务编排相关接口调用。
- 产出：
  - `frontend/src/api/scenes.ts`
- 需新增方法：
  - `listScriptTasks`
  - `listTaskItems`
  - `addTaskItem`
  - `updateTaskItem`
  - `removeTaskItem`
  - `getCompiledScript`
  - `runScene`
- 验收：
  - 前端可直接调用任务编排相关接口

## B2. SceneDetail 页面新增“执行编排”区域
- 优先级：P0
- 状态：DONE
- 目标：保留现有“关联脚本”，并新增任务级编排面板。
- 产出：
  - `frontend/src/pages/SceneDetail.vue`
- 页面建议：
  - 关联脚本区域保留
  - 编排区展示已关联脚本与其 `tasks[].name`
  - 当前编排列表展示顺序、任务名、来源脚本、备注、操作
- 验收：
  - 页面可展示并维护场景任务编排项

## B3. 开发任务选择组件
- 优先级：P1
- 状态：DONE
- 目标：支持从已关联脚本中挑选 task 进入编排。
- 产出：
  - 已内嵌于 `frontend/src/pages/SceneDetail.vue`
- 交互建议：
  - 以脚本分组展示任务名
  - 支持搜索 task 名称
  - 选中后回填到编排列表
- 验收：
  - 用户可直观看到每个脚本中的任务

## B4. 支持编排预览
- 优先级：P1
- 状态：DONE
- 目标：以弹窗形式展示编译后的 YAML。
- 产出：
  - `frontend/src/components/SceneCompiledScriptPreview.vue`
  - 或直接内嵌于 `SceneDetail.vue`
- 验收：
  - 用户可预览最终场景执行脚本

## B5. 前端构建与页面回归
- 优先级：P1
- 状态：DONE
- 目标：确保新增编排能力不影响现有场景页与脚本页。
- 验收：
  - `cd frontend && npm run build` 通过
  - 场景列表、场景详情、脚本列表、运行列表正常访问

---

## 5. Milestone C：场景运行接入现有 run 系统（P0）

当前目标：
1. 支持执行编排后的场景脚本。
2. 运行详情可追溯本次编排结果。

## C1. 新增场景运行接口
- 优先级：P0
- 状态：DONE
- 目标：从场景编排结果直接发起运行。
- API：
  - `POST /api/scenes/{scene_id}/runs`
- 建议行为：
  - 动态编译场景 YAML
  - 复用现有 `runs` 执行链路
- 验收：
  - 场景可发起运行并生成 run 记录

## C2. 为 run 补充来源场景与编排快照
- 优先级：P0
- 状态：DONE
- 目标：保证场景执行可追溯。
- 建议字段：
  - `scene_id`
  - `scene_name_snapshot`
  - `compiled_script_snapshot`
- 验收：
  - run 可区分来源于“单脚本执行”还是“场景执行”
  - 运行详情页可查看编排快照

## C3. 运行详情页联动展示
- 优先级：P1
- 状态：DONE
- 目标：在运行详情页补充来源场景和执行快照入口。
- 影响文件：
  - `frontend/src/pages/RunDetail.vue`
  - `frontend/src/api/runs.ts`
- 验收：
  - 场景运行详情可查看来源场景
  - 可查看本次执行的合成脚本快照

---

## 6. Milestone D：联调、验收与文档收敛（P0）

当前目标：
1. 完成任务级编排从后端到前端的全链路联调。
2. 确认场景现有能力和脚本执行能力无回归。

## D1. 后端联调验证
- 优先级：P0
- 状态：DONE
- 目标：验证解析、编排、编译、运行全链路。
- 验收：
  - 场景任务编排接口返回正确
  - 编译结果结构符合预期
  - 场景运行成功进入 run 系统

## D2. 前端手工验证
- 优先级：P0
- 状态：DOING
- 核心验收路径：
  1. 创建/打开场景
  2. 关联多个脚本
  3. 选择脚本中的多个 task
  4. 调整任务顺序
  5. 预览合成 YAML
  6. 执行整个场景
  7. 在运行详情查看执行快照
- 验收：
  - 页面流程完整无阻塞

## D3. 回归验证
- 优先级：P0
- 状态：DONE
- 范围：
  - 场景关联脚本原有能力
  - 脚本编辑与脚本执行
  - 运行详情查看脚本快照
- 验收：
  - 主流程无回归

## D4. 文档收敛
- 优先级：P1
- 状态：DOING
- 目标：补充本期设计与验收记录。
- 产出建议：
  - `specify/v1.3/spec.md`（如需要）
  - `specify/v1.3/d1-integration-report.md`（可选）
- 验收：
  - 关键实现与联调结果有记录

---

## 7. 当前建议实施顺序
1. 先做后端任务解析与编排模型
2. 再做前端编排列表与预览
3. 最后接入场景运行

原因：
- 如果先做前端，没有稳定的“任务快照”和“编译结果”接口，页面会反复返工
- 先固化后端模型，前端交互更容易收敛

---

## 8. 完成定义（DoD）
- 场景支持从关联脚本中选择任务片段进行编排
- 编排项支持排序、备注、删除
- 可预览最终合成 YAML
- 可执行整个场景编排结果
- 场景执行结果具备可追溯性
