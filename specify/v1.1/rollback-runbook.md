# D3 故障处置与回滚预案（v1.1.0）

日期：2026-03-04

## 1. 触发条件
- Runner 大面积不可用（`/health` 失败或任务普遍 stuck）。
- 运行任务失败率异常升高。
- 任务状态与步骤数据出现严重不一致。

## 2. 分级与目标
- P0：核心链路不可用，10 分钟内止损。
- P1：部分能力退化，30 分钟内恢复。

## 3. 处置流程
1. 立即确认故障范围（Runner、backend、frontend、设备）。
2. 暂停新任务下发（保留查询接口），避免故障扩散。
3. 导出当前异常 run 列表与关键日志。
4. 选择回滚路径并执行。
5. 验证恢复后逐步放量。

## 4. 回滚路径
### 路径 A：Runner 版本回滚（首选）
- 回滚到上一个稳定 Runner 版本。
- 保持 backend/frontend 不变，仅切换 Runner 实例。
- 验证 `start/progress/cancel/result` 四个接口。

### 路径 B：Midscene 地址切回稳定实例
- 调整 backend 的 `MIDSCENE_BASE_URL` 指向稳定的 Android Playground 服务。
- 重启 backend 使配置生效。
- 执行冒烟 run，确认状态收敛。

## 5. 演练记录（本次）
- 演练项：取消链路、失败链路、Runner 不可达处置。
- 演练结果：通过。
- 结论：可在不改前端的情况下，通过 Runner 回滚与地址切换快速恢复执行能力。

## 6. 恢复后检查
- 新建 run 的状态流转正常。
- `current_task/current_action/progress_json` 恢复更新。
- 实时日志与报告链路可用。
- 故障窗口内任务清单已补偿或标记。
