---
name: requirement-verifier
description: 对照 PRD、测试报告、应用报告和最终产物执行反向需求完整性校对。
---

# Requirement Verifier

你负责在测试、应用和 session report 之后执行 PRD 反向需求校对。

必须读取：

- `.superlooper/context/<task_id>/prd.md`
- `.superlooper/reports/<task_id>/test_report.md`
- `.superlooper/reports/<task_id>/apply_report.json`
- `.superlooper/reports/<task_id>/session_report.md`
- `.superlooper/manifests/<task_id>/module-split.json`
- `.superlooper/manifests/<task_id>/execution_manifest.json`

必须输出：

- `.superlooper/reports/<task_id>/requirement_alignment_report.md`

报告第一个代码块必须为 YAML 状态块：

```yaml
task_id: <task_id>
requirement_alignment_status: PASS
unmet_requirement_count: 0
unchecked_acceptance_count: 0
prd_path: .superlooper/context/<task_id>/prd.md
test_report_path: .superlooper/reports/<task_id>/test_report.md
apply_report_path: .superlooper/reports/<task_id>/apply_report.json
report_path: .superlooper/reports/<task_id>/requirement_alignment_report.md
```

当 `requirement_alignment_status: PASS` 时，YAML 状态块后必须紧跟首个机器可读 `json` 证据块：

```json
{
  "requirement_coverage": [
    {
      "id": "REQ-001",
      "type": "REQ",
      "status": "PASS",
      "implementation_evidence": ["实现文件或产物证据"],
      "test_evidence": ["测试命令或测试报告证据"],
      "delivery_evidence": ["应用报告或最终交付证据"]
    }
  ]
}
```

`requirement_coverage` 必须逐项且仅覆盖 PRD 中全部 `REQ-*`、`AC-*`、`DEC-*`、`OPEN-*`，不得缺失、重复或包含未知编号。每项 `type` 必须与编号前缀一致，`status` 必须为 `PASS`，三类 evidence 都必须是非空字符串数组。

只有所有 `REQ-*`、`AC-*`、`DEC-*`、`OPEN-*` 和 `ui_acceptance_refs` 均有状态和证据时，才允许 `requirement_alignment_status: PASS`。

报告正文必须包含 PRD 反向校对表：

| 编号 | 类型 | PRD 要求 | 实现证据 | 测试证据 | 交付证据 | 状态 | 修正建议 |
| --- | --- | --- | --- | --- | --- | --- | --- |

`REQ-*`、`AC-*`、`DEC-*`、`OPEN-*` 必须逐项进入表格。`ui_acceptance_refs` 必须结合 `test_report.md` 中的 UI 验收覆盖证据进行校对。若存在未满足需求、未验证验收标准或证据链缺失，必须输出 `requirement_alignment_status: FAIL`，并列出缺口编号、缺失证据和返回修正建议。
