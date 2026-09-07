# DAG state runner 设计

## 设计目标

当前实现是 DAG state runner，用于消费 `execution_manifest.json`，校验 DAG 结构，生成可审计的 DAG 状态文件，并记录 script event。它不是完整 agent executor，不直接调度 Claude subagent，不直接执行 merge、test、apply，也不替代 `/spl:run` 主协议中的人工审核和质量门禁。

本设计不替代 `skills/superlooper/SKILL.md` 主体调度协议，不减少 PRD、UI、执行摘要和最终需求反向校对人工握手。完整 executor 仅作为未实施扩展保留。只有当 Superlooper 明确支持无人值守、CI/headless 或节点级自动恢复时，才需要另起设计实现。

## 第一性原理五步分析

### 1. 根本目标是什么

让 Superlooper 能按 `execution_manifest.json` 的 DAG 依赖关系记录模块实现、代码审查、合并、测试和应用节点状态，形成可审计的运行状态文件。

### 2. 当前已完成什么

当前已具备 Manifest 生成、动态 `module_*` agent 生成、执行摘要审核和 `scripts/run_execution_dag.py`。DAG state runner 已能读取 Manifest、校验 DAG 基本结构、拓扑排序、写入 `.superlooper/state/<session_id>.dag.json`，并通过 `scripts/update_session.py` 记录 script event。

### 3. 为什么需要设计

完整 executor 扩展会接触 agent 调度、失败恢复、合并、测试和真实工作区应用。必须先定义状态模型和门禁边界，防止未来执行器绕过现有人工审核、validator 或 apply 冲突阻断。

### 4. 排除什么

本设计不实现新的需求分析、UI 设计、系统设计、模块拆分或 Manifest 生成逻辑。当前源码实现不直接调度 Claude subagent，不直接执行 merge、test、apply，也不直接改写 PRD、UI、设计、Manifest 或目标工作区。

### 5. 成功判据是什么

当前最小实现的成功判据是：Manifest 可被消费，DAG 依赖关系可排序，缺失依赖和循环依赖可失败退出，DAG 状态文件可被 validator 校验，script event 可进入 session state。

完整 executor 扩展的成功判据是：只能在执行摘要已审核通过后运行；节点状态可恢复；失败节点能停在合法返工点；apply 安全策略和最终需求反向校对门禁不变。

## 当前已实施范围

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 读取 `execution_manifest.json` | 已实施 | 从 `.superlooper/manifests/<session_id>/execution_manifest.json` 读取运行时 DAG。 |
| 基础 DAG 校验 | 已实施 | 校验 Manifest 顶层、session_id、dag、nodes、节点 ID、依赖数组、缺失依赖和循环依赖。 |
| 拓扑排序 | 已实施 | 按 `depends_on` 计算 `execution_order`。 |
| DAG state 写入 | 已实施 | 写入 `.superlooper/state/<session_id>.dag.json`。 |
| script event 记录 | 已实施 | 通过 `scripts/update_session.py --record-script-event` 写入 `run_execution_dag` 事件。 |
| validator scope | 已实施 | `validate_miao_contracts.py --scope dag-state` 校验 DAG state。 |
| 真实 agent 调度 | 未实施扩展 | 当前脚本不调用 Claude subagent。 |
| 节点级 merge/test/apply 执行 | 未实施扩展 | 仍由 `/spl:run` 主协议和对应 agent/脚本门禁处理。 |
| 执行摘要前置门禁内置校验 | 未实施扩展 | 当前门禁仍由 `/spl:run` 与 `resume_session.py` 保证。 |

## 运行前置条件

| 条件 | 当前最小实现 | 完整扩展目标 |
| --- | --- | --- |
| session state | 通过 `session_id` 定位运行目录。 | `current_phase=run`，且执行摘要已审核通过。 |
| UI 门禁 | 由 Manifest 生成前置校验保证。 | 执行器内再次校验 `ui_status=APPROVED` 且 `ui_artifacts_validated=true`。 |
| 初始化门禁 | 由 Manifest 生成前置校验保证。 | 执行器内再次校验 `project_initialized=true`，且 `initialization_report` 存在。 |
| Manifest | 当前脚本读取并校验基础结构。 | 执行前调用完整 validator。 |
| 动态 agent | 由 Manifest 生成和 validator 链路保证。 | 执行器内校验 runtime agent 与 registered agent 一致。 |
| 执行摘要 | 由 `/spl:run` 等待用户确认。 | 执行器拒绝未审核执行摘要。 |

## 文件设计

| 文件 | 职责 | 当前状态 |
| --- | --- | --- |
| `scripts/run_execution_dag.py` | 读取 execution manifest，按 DAG 依赖生成节点状态。 | 已实施最小 state runner。 |
| `.superlooper/state/<session_id>.dag.json` | 记录 DAG 状态、当前节点、执行顺序、节点依赖和错误摘要。 | 已实施。 |
| `tests/test_run_execution_dag.py` | 覆盖拓扑排序、缺失依赖失败和 script event。 | 已实施。 |

## DAG 状态文件结构

```json
{
  "session_id": "master-framework-20260818",
  "dag_status": "success",
  "current_node": "task_apply_to_workspace",
  "execution_order": ["mod_auth_center", "task_code_review", "task_merge", "task_integration_test", "task_apply_to_workspace"],
  "error_summary": "",
  "manifest_path": ".superlooper/manifests/master-framework-20260818/execution_manifest.json",
  "nodes": {
    "mod_auth_center": {
      "status": "success",
      "agent": "module_auth_center",
      "depends_on": [],
      "artifact_manifest": ".superlooper/outputs/master-framework-20260818/auth_center/artifact_manifest.json",
      "error_summary": ""
    }
  }
}
```

当前合法 `dag_status`：

```text
pending
running
success
failed
```

当前合法节点状态：

```text
pending
ready
running
success
failed
skipped
```

`blocked` 状态属于完整 executor 扩展目标，当前 validator 未接收该状态。

## 节点执行规则

| 节点类型 | 当前最小实现 | 完整扩展目标 |
| --- | --- | --- |
| `mod_*` | 写入节点状态和 artifact manifest 约定路径。 | 当前节点依赖全部成功后调度对应 `module_*` agent，并校验 `artifact_manifest.json.status=success`。 |
| `task_code_review` | 写入系统节点状态。 | 所有 `mod_*` 成功后调用 `code-reviewer`，要求 `code_review_status=PASS`。 |
| `task_merge` | 写入系统节点状态。 | 代码审查通过后执行 `scripts/merge_artifacts.py`，要求 `merge_report.json.status=success`。 |
| `task_integration_test` | 写入系统节点状态。 | 合并成功后调用 `tester`，要求 `test_status=PASS`。 |
| `task_apply_to_workspace` | 写入系统节点状态。 | 测试通过后调用 `workspace_applier`，要求 `apply_report.json.status=success` 且 `workspace_validation.status=PASS`。 |

## 恢复规则

- 当前最小实现每次按 Manifest 重新生成 DAG state，不调度真实节点，不重放业务副作用。
- 完整扩展中，已成功节点不得重复执行，除非上游影响分析声明该节点失效。
- 完整扩展中，`failed` 节点是恢复起点；`blocked` 节点需先进入状态枚举、validator 和测试。
- `resume_session.py` 仍负责解释用户输入和合法回退目标。
- 当前 DAG state runner 不直接改写 PRD、UI、设计、Manifest 或目标工作区；未来完整 executor 扩展也不得绕过这些边界。

## 与现有文件的联动

| 文件 | 影响 |
| --- | --- |
| `skills/superlooper/SKILL.md` | 当前未修改主体调度协议。完整扩展前必须单独审批。 |
| `commands/spl/run.md` | 当前未强制调用 `scripts/run_execution_dag.py`；`/spl:run` 仍按主协议执行流程六和流程七。 |
| `scripts/validate_miao_contracts.py` | 已增加 `dag-state` scope。 |
| `schemas/session-state.schema.json` | 当前 DAG state 独立保存，不写入主 session schema。 |
| `README.md` | 已记录 `scripts/run_execution_dag.py` 是 DAG state runner。 |

## 验收设计

| 验收项 | 当前状态 |
| --- | --- |
| 正确拓扑执行 | 已由 `tests/test_run_execution_dag.py` 覆盖。 |
| 缺失依赖失败 | 已由 `tests/test_run_execution_dag.py` 覆盖。 |
| script event 记录 | 已由 `tests/test_run_execution_dag.py` 覆盖。 |
| DAG state schema | 已由 `validate_miao_contracts.py --scope dag-state` 覆盖。 |
| 拒绝未审核执行摘要 | 未实施扩展。 |
| code review 失败阻断 | 未实施扩展，仍由 `/spl:run` 主协议处理。 |
| apply 冲突阻断 | 未实施扩展，仍由 `workspace_applier` 和 apply validator 处理。 |
| 恢复幂等 | 未实施扩展。 |

## 改善后的要点

- 节点级状态可观察。
- DAG 依赖错误可提前暴露。
- 状态写入与 session script event 形成链路。
- 不绕过执行摘要审核、validator、apply 冲突阻断和最终需求反向校对。
- 为后续真实节点调度提供稳定状态基础。

## 已实施范围与未实施扩展边界

当前已实施范围是 DAG state runner，不是完整 agent executor。它负责消费 Manifest、排序 DAG、写入 DAG state 和记录 script event。

未实施扩展包括：真实 subagent 调度、节点级 artifact 校验、内置执行摘要门禁、`blocked` 状态、失败恢复幂等、merge/test/apply 的脚本级联动执行。
