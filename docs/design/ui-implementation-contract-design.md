# UI 实现契约设计

## 设计目标

把已审核 UI 设计产物中的页面、交互、组件和 UI 验收关注点传递到模块拆分、执行 Manifest、动态 `module_*` agent 和测试链路。

本设计不要求所有项目都有前端实现。后端-only 项目允许 UI 追溯字段为空。

## 第一性原理五步分析

### 1. 根本目标是什么

让 UI 审核结果不只停留在 `.superlooper/context/<session_id>/ui/` 文档中，而能被实现、测试和最终需求反向校对消费。

### 2. 当前已完成什么

当前已将 `ui_refs`、`interaction_refs`、`component_refs`、`ui_acceptance_refs` 进入 module-split schema、execution manifest payload、动态 agent `Runtime Module Constraints`、validator 一致性校验、报告正文轻量审计、architect/developer/tester/requirement-verifier 契约和 README。

### 3. 为什么需要设计

UI 契约涉及 `ui-handoff.md`、architect、module-split、execution manifest、dynamic agent constraints、tester 和 requirement verifier。直接加字段会造成 schema、validator、agent 和 README 漂移。

### 4. 排除什么

本设计不新增 UI 多 agent 调度，不恢复 `agents/ui/` 历史子 agent，不把 UI 设计阶段变成编码阶段。当前机器校验只做 `test_report.md` 与 `requirement_alignment_report.md` 正文的轻量 UI 验收编号审计，不解析完整 Markdown AST 或跨报告结构化证据链。

### 5. 成功判据是什么

当前最小实现的成功判据是：UI refs 能从 module-split 进入 Manifest payload；动态 agent 只看到自己模块相关的 UI refs；validator 能校验 module-split、payload、runtime constraints 的字段一致性，并能轻量检查 `test_report.md` 和 `requirement_alignment_report.md` 正文是否列出 `ui_acceptance_refs` 证据。

完整扩展的成功判据是：validator 能通过 Markdown AST 和跨报告结构化证据链校验每个 `ui_acceptance_refs` 的测试、应用和最终校对证据。

## 当前已实施范围

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| module-split UI 字段 | 已实施 | `schemas/module-split.schema.json` 支持四个字段。 |
| Manifest payload 透传 | 已实施 | `scripts/generate_execution_manifest.py` 将四个字段下发到 `mod_*` payload。 |
| runtime agent constraints | 已实施 | `scripts/generate_runtime_agents.py` 写入四个字段。 |
| validator 字段一致性 | 已实施 | 校验 payload 与 module-split 对应字段一致。 |
| dynamic agent 字段存在校验 | 已实施 | 校验 `Runtime Module Constraints` 包含四个字段。 |
| architect 契约 | 已实施 | 要求从已审核 UI 产物映射 UI refs。 |
| developer 契约 | 已实施 | 要求模块只消费当前 payload 的 UI refs。 |
| tester 契约 | 已实施 | 要求测试报告说明 UI 验收覆盖证据或未覆盖原因。 |
| requirement verifier 契约 | 已实施 | 要求最终校对结合 UI 验收覆盖证据。 |
| tester report 正文机器校验 | 已实施 | validator 从 module-split 收集 `ui_acceptance_refs`，轻量检查 `test_report.md` 正文证据行。 |
| requirement alignment 正文机器校验 | 已实施 | validator 从 module-split 收集 `ui_acceptance_refs`，轻量检查 `requirement_alignment_report.md` 正文校对证据行。 |

## 新增追溯字段

`module-split.json.modules[]` 和 `execution_manifest.json.dag.nodes[].payload` 使用字段：

```json
{
  "ui_refs": ["UI-PAGE-001"],
  "interaction_refs": ["INT-001"],
  "component_refs": ["CMP-001"],
  "ui_acceptance_refs": ["UI-AC-001"]
}
```

## 字段定义

| 字段 | 来源 | 含义 |
| --- | --- | --- |
| `ui_refs` | `page-map.md` 或 `ui-handoff.md` | 页面、视图或 UI 区块编号。 |
| `interaction_refs` | `interaction-flow.md` | 用户交互流程编号。 |
| `component_refs` | `ui-spec.md` | 组件编号。 |
| `ui_acceptance_refs` | `ui-handoff.md` | UI 验收标准编号。 |

## 产物流转

```text
ui-spec.md / page-map.md / interaction-flow.md / ui-handoff.md
        ↓
architect
        ↓
module-split.json.modules[].ui_refs
        ↓
generate_execution_manifest.py
        ↓
execution_manifest.json.dag.nodes[].payload
        ↓
generate_runtime_agents.py Runtime Module Constraints
        ↓
module_* artifact_manifest.json / tester / requirement-verifier
```

## 消费方规则

| 消费方 | 规则 | 当前状态 |
| --- | --- | --- |
| `agents/architect.md` | 从已审核 UI 产物提取与模块相关的 UI refs。 | 已落地契约。 |
| `schemas/module-split.schema.json` | 允许模块声明 UI 追溯字段。 | 已落地 schema。 |
| `scripts/generate_execution_manifest.py` | 将模块 UI refs 下发到对应 `mod_*` payload。 | 已落地生成链路。 |
| `scripts/generate_runtime_agents.py` | 将 UI refs 写入 `Runtime Module Constraints`。 | 已落地生成链路。 |
| `agents/developer.md` | 模块只实现当前 payload 中出现的 UI refs，不读取完整 UI 文档。 | 已落地契约。 |
| `agents/tester.md` | 测试报告覆盖相关 UI 验收编号。 | 已落地契约，validator 已做轻量正文审计。 |
| `agents/requirement-verifier.md` | 最终校对 UI 验收编号是否已被实现和测试覆盖。 | 已落地契约，validator 已做轻量正文审计。 |

## 约束规则

- UI refs 不替代 `requirement_refs`。
- UI refs 不允许模块读取原始需求文档。
- UI refs 不允许模块修改未声明 `target_files`。
- UI refs 为空时，不阻断后端-only 项目。
- 若 `ui_acceptance_refs` 非空，tester 必须在 `test_report.md` 中说明覆盖结果。
- 若前端页面有 target file，`file_roles` 必须说明页面、组件或交互职责。

## Schema 设计

当前新增字段均为数组，元素为非空字符串：

```json
{
  "ui_refs": {
    "type": "array",
    "items": {"type": "string", "minLength": 1}
  },
  "interaction_refs": {
    "type": "array",
    "items": {"type": "string", "minLength": 1}
  },
  "component_refs": {
    "type": "array",
    "items": {"type": "string", "minLength": 1}
  },
  "ui_acceptance_refs": {
    "type": "array",
    "items": {"type": "string", "minLength": 1}
  }
}
```

字段缺失时，生成脚本按空数组写入 Manifest payload 和 runtime constraints。

## Validator 设计

| 校验 | 当前状态 |
| --- | --- |
| module-split 字段类型 | 已实施。 |
| execution manifest payload 与 module-split 一致 | 已实施。 |
| dynamic agent `Runtime Module Constraints` 包含 UI refs 字段 | 已实施。 |
| tester report 存在 `ui_acceptance_refs` 时必须声明覆盖结果 | 已进入 agent 契约和轻量正文机器审计。 |
| requirement alignment 中 UI 验收未覆盖时不得输出 PASS | 已进入 agent 契约、YAML 计数门禁和轻量正文机器审计。 |

## 与现有文件的联动

| 文件 | 影响 |
| --- | --- |
| `agents/ui-architect.md` | 保持 UI 产物编号来源职责。 |
| `docs/agent-flows/ui-architect-flow.md` | 保持编号生成和交付规则。 |
| `agents/architect.md` | 已把 UI refs 映射到模块拆分。 |
| `schemas/module-split.schema.json` | 已增加 UI 追溯字段。 |
| `scripts/generate_execution_manifest.py` | 已增加 payload UI 追溯字段。 |
| `scripts/generate_runtime_agents.py` | 已增加 runtime constraints UI 追溯字段。 |
| `scripts/validate_miao_contracts.py` | 已增加类型、payload 一致性和动态 agent 字段存在校验。 |
| `tests/test_generate_execution_manifest.py` | 已覆盖 UI refs 下发。 |
| `tests/test_generate_runtime_agents.py` | 已覆盖 runtime constraints 字段。 |
| `tests/test_validate_contracts.py` | 已覆盖字段类型和一致性错误。 |

## 改善后的要点

- UI 审核结果进入实现链路。
- 页面、交互、组件和 UI 验收编号可追溯。
- tester、requirement verifier 和 validator 可以发现 UI 验收证据缺失问题。
- 后端-only 项目不被额外字段阻断。
- 删除历史 `agents/ui/` 后，单一 `ui-architect` 仍能承担 UI 契约源职责。

## 已实施范围与未实施扩展边界

当前已实施范围是 UI traceability 字段链路、agent 契约和 validator 对 `test_report.md`、`requirement_alignment_report.md` 正文的轻量 UI 验收编号审计。

未实施扩展包括：从 UI 文档自动抽取 refs、强制前端模块必须声明 UI refs、完整 Markdown AST 表格解析、跨报告证据链结构化比对和 UI 验收证据自动生成。
