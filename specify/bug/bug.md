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
