# Script 状态推进统一设计

## 设计目标

统一 Python 脚本、slash command 和 session state 的写入边界，减少“文件已生成但 state 未更新”或“state 已推进但文件不存在”的漂移。

本设计不要求每个业务脚本直接手写 state JSON。唯一写入入口保持为 `scripts/update_session.py`。

## 第一性原理五步分析

### 1. 根本目标是什么

让 `status`、`resume`、event log 和文件系统事实保持一致，确保单独运行关键脚本后仍能被 session 恢复逻辑识别。

### 2. 当前已完成什么

当前已在 session state 中增加 `script_events`，并通过 `scripts/update_session.py --record-script-event <script_name>:<status>:<idempotency_key>` 统一记录脚本事件。`scripts/status_session.py` 已展示脚本事件，`scripts/run_execution_dag.py` 已接入该事件入口。

### 3. 为什么需要设计

状态推进涉及 phase、status、reports、generated_files、next_action、last_error 和 event log。多个脚本各自写 state 会导致重复推进、幂等失败和恢复错误。

### 4. 排除什么

本设计不让 `generate_execution_manifest.py`、`merge_artifacts.py`、`apply_to_workspace.py` 等脚本直接手写 state JSON。本设计不改变现有 phase 枚举、canonical action 和人工审核门禁。

### 5. 成功判据是什么

当前最小实现的成功判据是：关键脚本可通过统一入口追加 `script_events`；重复 `idempotency_key` 不重复写入；session schema 接收该字段；status 输出可观察。

完整扩展的成功判据是：关键脚本完成后通过统一桥接层记录 state、generated files、reports 和 event；失败时记录 last_error；`resume_session.py` 能基于扩展状态输出更精准下一步。

## 当前已实施范围

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `script_events` 字段 | 已实施 | `schemas/session-state.schema.json` 已要求该字段。 |
| 统一写入入口 | 已实施 | `scripts/update_session.py` 接收 `--record-script-event`。 |
| 幂等去重 | 已实施 | 相同 `idempotency_key` 不重复追加。 |
| 事件状态 | 已实施 | 当前仅接收 `started`、`completed`、`failed`。 |
| status 展示 | 已实施 | `scripts/status_session.py` 输出 script events。 |
| DAG runner 接入 | 已实施 | `scripts/run_execution_dag.py` 记录 completed/failed 事件。 |
| generated_files/reports 扩展桥接 | 未实施扩展 | 当前仍通过既有参数显式传入。 |
| last_error 脚本桥接 | 未实施扩展 | 当前没有统一脚本桥接层封装 stderr。 |
| gate/report 细粒度事件 | 未实施扩展 | 当前未实现 `artifact_validated`、`gate_passed` 等事件。 |

## 分层职责

| 层级 | 组件 | 当前职责 |
| --- | --- | --- |
| 业务脚本 | `generate_execution_manifest.py` 等 | 生成产物、报告和命令退出码。 |
| 状态桥接层 | command 调用约定或后续统一封装 | 把脚本结果转换为 `update_session.py` 参数。当前仅最小接入 script event。 |
| 状态写入层 | `scripts/update_session.py` | 唯一写入 `.superlooper/state/<session_id>.json` 的入口。 |
| 恢复层 | `scripts/resume_session.py` | 读取 state，解释用户输入，输出下一步。 |

## 当前状态事件

当前 `script_events[].status` 只允许：

```text
started
completed
failed
```

事件结构：

```json
{
  "script": "run_execution_dag",
  "status": "completed",
  "idempotency_key": "master-framework-20260818:completed"
}
```

## 后续扩展事件

以下事件属于完整桥接层扩展，不属于当前最小实现：

```text
script_started
script_completed
script_failed
artifact_validated
artifact_invalid
report_generated
gate_passed
gate_failed
```

如启用这些事件，必须同步修改 `schemas/session-state.schema.json`、`scripts/update_session.py`、`scripts/status_session.py`、`scripts/resume_session.py`、README 和测试。

## 状态更新输入结构

当前已实施输入：

| 字段 | 说明 |
| --- | --- |
| `session_id` | 当前 session。 |
| `current_phase` | 当前 phase。 |
| `phase_status` | 当前 phase 状态。 |
| `last_command` | 触发脚本或 command 名称。 |
| `record_script_event` | `<script_name>:<status>:<idempotency_key>`。 |

完整扩展输入：

| 字段 | 说明 |
| --- | --- |
| `generated_files` | 新增或更新的文件。 |
| `reports` | 新增或更新的报告。 |
| `next_action` | 下一步建议。 |
| `last_error` | 失败摘要，成功时为空。 |
| `idempotency_key` | 防止重复追加同一事件。 |

## 首批接入脚本

| 脚本 | 当前状态 |
| --- | --- |
| `scripts/run_execution_dag.py` | 已接入 `run_execution_dag:completed|failed:<idempotency_key>`。 |
| `scripts/generate_execution_manifest.py` | 未接入扩展桥接层，仍由 `/spl:run` 调用 `update_session.py` 推进。 |
| `scripts/generate_runtime_agents.py` | 未接入扩展桥接层，仍由 `/spl:run` 调用链路保证。 |
| `scripts/build_execution_summary.py` | 未接入扩展桥接层，仍由 `/spl:run` 调用 validator 和 update_session。 |
| `scripts/merge_artifacts.py` | 未接入扩展桥接层，仍由系统合并流程记录报告。 |
| `scripts/apply_to_workspace.py` | 未接入扩展桥接层，仍由 apply report 和冲突报告表达结果。 |
| `scripts/build_session_report.py` | 未接入扩展桥接层，仍由 run 阶段显式调用。 |

## 幂等规则

- 相同 `idempotency_key` 的事件不得重复写入 `script_events`。
- command 层与脚本层同时上报时，以同一 `idempotency_key` 去重。
- 当前最小实现不自动去重 `generated_files` 或 `reports`。
- 当前最小实现不根据 script event 自动回退 `phase_status`。

## 失败处理

| 场景 | 当前最小实现 |
| --- | --- |
| 脚本返回非 0 | 调用方可记录 `status=failed` 的 script event。 |
| 产物缺失 | 由对应脚本或 validator 输出错误，不由 script event 单独推进 phase。 |
| validator 失败 | 仍由 command 或主调度器记录 last_error 和 next_action。 |
| apply 冲突 | 仍由 `apply_conflict_report.json` 与 run 阶段 blocked 状态处理。 |
| 状态写入失败 | 调用方不得声明流程完成。 |

## 与现有文件的联动

| 文件 | 影响 |
| --- | --- |
| `scripts/update_session.py` | 已增加 `--record-script-event`、事件去重和状态校验。 |
| `scripts/status_session.py` | 已展示 script events。 |
| `scripts/resume_session.py` | 当前不改变 canonical action；后续扩展再读取细粒度事件。 |
| `schemas/session-state.schema.json` | 已增加 `script_events` 字段。 |
| `configs/interaction-flow.json` | 不增加公开用户回复，仅在内部事件层扩展。 |
| `tests/test_session_state.py` | 已覆盖脚本事件写入和幂等。 |
| `README.md` | 已记录脚本状态统一边界。 |

## 验收设计

| 验收项 | 当前状态 |
| --- | --- |
| 成功脚本写入 script event | 已覆盖。 |
| 重复事件去重 | 已覆盖。 |
| session schema 接收 `script_events` | 已覆盖。 |
| status 展示 script event | 已实施。 |
| 成功脚本写入报告路径 | 未实施扩展。 |
| 失败脚本不推进 phase | 未实施扩展。 |
| apply 冲突映射 gate event | 未实施扩展。 |
| resume 基于细粒度事件输出下一步 | 未实施扩展。 |

## 改善后的要点

- command 层和脚本层共享 `update_session.py` 作为状态写入入口。
- 单独运行已接入脚本后有可审计事件。
- event log 最小模型具备幂等能力。
- 为 DAG state runner 提供稳定状态基础。
- 不改变现有用户握手和主流程语义。

## 已实施范围与未实施扩展边界

当前已实施范围是最小 `script_events` 记录能力，不是完整脚本状态桥接层。

未实施扩展包括：统一 wrapper、`generated_files` 自动汇总、`reports` 自动汇总、`last_error` 统一采集、`artifact_validated`、`artifact_invalid`、`report_generated`、`gate_passed`、`gate_failed` 和 resume 对细粒度事件的策略消费。
