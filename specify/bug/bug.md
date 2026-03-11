# Bug: auto-glm 在 `aiInput` 定位阶段返回 `Type` 动作导致执行失败

## 概要
- 时间：2026-03-03
- 场景：AI 生成 YAML 后执行 Android 自动化任务（小红书 + 抖音粉丝数统计）
- 运行：`@midscene/cli v1.5.1`
- 结果：任务在抖音搜索输入阶段失败

## 现象
- 任务：`run-26-script-17.yaml`
- 失败步骤：`查询抖音粉丝数 (task 4/10)`
- 报错：
  - `failed to locate element`
  - `Unexpected action type in auto-glm locate response: do(action="Type", text="魔搭ModelScope社区")`

## 关键日志
- 日志文件：`backend/runtime/logs/run-26.log`
- 报告地址：`/api/runs/26/report/file`
- 关键堆栈：
  - `Service.locate` 抛错（Locate 期望定位结果，但模型返回了 Type 动作）

## 复现条件
1. 使用以下流程（抖音部分）执行：
   - `aiTap: 点击底部「搜索」图标`
   - `aiInput: 搜索「魔搭ModelScope社区」 + value`
   - `aiKeyboardPress: Enter`
2. 模型为 `autoglm-phone`（auto-glm mode）
3. 运行时可能在 `aiInput` 的 locate 阶段触发不兼容返回

## 影响范围
- 受影响步骤：`aiInput` / `aiTap + aiInput + aiKeyboardPress` 组合
- 影响结果：任务中断，后续步骤（抖音粉丝查询、汇总）不执行

## 根因分析
- `Locate` 阶段接口协议期望“元素定位信息”，但 `auto-glm` 返回了“Type 动作指令”。
- 该返回类型与当前 `Service.locate` 处理逻辑不匹配，触发异常并终止任务。

## 临时规避方案
1. 将“点击搜索 + 输入 + 回车”合并为单条 `aiAct`，避免 `aiInput` 单独走 locate：
   - 示例：`aiAct: 点击底部搜索图标，输入“魔搭ModelScope社区”，并执行搜索`
2. 对高风险步骤减少拆分动作，优先使用单步自然语言动作。

## 已落地改进
- 已更新 YAML 生成提示词（`backend/prompts/yaml_system_prompt.txt`）：
  - Android 搜索输入类步骤优先生成单条 `aiAct`
  - 尽量避免 `aiTap + aiInput + aiKeyboardPress` 组合，提升 auto-glm 兼容性

## 后续建议
1. 后端运行前校验：发现高风险组合时给出 warning。
2. 运行器容错：`Locate` 收到 `Type` 动作时尝试降级处理（可选）。
3. 增加回归样例：覆盖抖音/小红书搜索输入链路。

---

# Issue: 运行详情页的 timeout 错误缺少分类，无法快速判断根因

## 概要
- 时间：2026-03-11
- 场景：查看运行详情页，例如 `http://localhost:5173/run/173`
- 现状：页面只展示原始 `error_message`
- 问题：当报错为 `timeout` 时，用户无法判断是哪一层超时

## 现象
- 在运行详情页中，错误区域直接显示后端写入的 `run.error_message`
- 当报错包含 `timeout` 时，无法从 UI 上区分以下情况：
  - Midscene HTTP 接口调用超时
  - `aiWaitFor` / `waitFor` 等页面状态等待超时
  - 其它 AI 执行链路的超时

## 影响
- 用户看到“超时”后无法快速定位问题
- 排查需要进入日志或后端代码，门槛较高
- 容易误判为前端页面超时或系统整体不可用

## 已知代码背景
- 运行详情页当前直接显示：
  - `frontend/src/pages/RunDetail.vue`
- 后端调用 Midscene 服务超时配置：
  - `backend/app/core/config.py`
  - `backend/app/services/run_service.py`
- Midscene `aiWaitFor` 默认等待：
  - `android-playground/packages/core/src/agent/agent.ts`

## 期望行为
- 在运行详情页中，把 timeout 类错误细分成更明确的中文提示，例如：
  - `Midscene 服务调用超时`
  - `页面等待超时：未出现目标元素或页面状态`
  - `AI 执行超时`
- 同时保留原始错误文本，便于技术排查

## 建议方案
1. 在后端增加错误归类逻辑，对 `run.error_message` 做轻量识别。
2. 在运行详情页额外展示“错误类型”或“可能原因”字段。
3. 对 `ReadTimeout`、`ConnectTimeout`、`waitFor timeout`、`Replanned ...` 等常见模式做标准化文案映射。

## 暂不处理原因
- 当前问题不影响任务主链路执行
- 需要等真实 timeout case 再基于日志样本细化分类规则

## 后续建议
1. 等再次出现 timeout 样本后，补充具体匹配规则和测试用例。
2. 前端增加“错误分类 + 原始错误”双展示模式。
3. 回归覆盖：
   - Midscene HTTP timeout
   - `waitFor timeout`
   - `replanningCycleLimit` 超限
