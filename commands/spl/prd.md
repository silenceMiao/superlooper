---
description: 执行 Superlooper 流程一和流程二，输出 PRD 或关键决策看板。
argument-hint: "<requirement_path> [session_id]"
allowed-tools: Read, Write, Bash, Glob, Grep, Agent
---

# /superlooper:spl:prd

`/superlooper:spl:prd` 是 PRD 分段触发入口，只执行 `skills/superlooper/SKILL.md` 的流程一入口与会话准备、流程二需求分析与 PRD 审核。

用户参数：`$ARGUMENTS`

执行规则：

1. 读取 `skills/superlooper/SKILL.md`、`agents/analyst.md`、`docs/agent-flows/analyst-flow.md`、`configs/interaction-flow.json`。
2. 需求阶段对用户自然语言反馈必须先归一化为 `configs/interaction-flow.json` 中 `prd` 阶段声明的 canonical action；`allowed_replies` 是内部 canonical reply 和推荐回复，不是用户唯一可输入内容。
3. 确认 `session_id` 和 `requirement_path`。
4. 调用 `scripts/create_session.py` 确保 `.superlooper/context/<session_id>/` 与 `.superlooper/reports/<session_id>/` 存在。
5. 调用 `analyst` agent，payload 必须包含 `session_id`、`requirement_path`、`output_prd_path`。
6. 读取 analyst 输出中的第一个机器可读 `yaml` 代码块。
7. 当 `analyst_status=ANALYST_BLOCKED_BY_DECISION` 时，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase prd --phase-status blocked --last-command "/spl:prd <requirement_path> <session_id>" --last-error "analyst 输出关键决策看板，等待用户确认 DEC-*" --next-action "一次性确认关键决策看板中的 DEC-*"`，然后停止并要求用户一次性确认 `DEC-*`。
8. 当 `analyst_status=READY_FOR_DESIGN` 时，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase prd --phase-status waiting_review --last-command "/spl:prd <requirement_path> <session_id>" --generated-file .superlooper/context/<session_id>/prd.md --prd-revision <next_prd_revision> --next-action "审核 PRD；通过后使用 通过，进入 UI 设计；不通过使用 PRD未通过，按反馈重新分析"`，确认 PRD 已写入，并输出流程二完成握手。
9. 当用户审核 PRD 未通过或用自然语言表达 PRD 不符合、需要补充需求时，先归一化为 `prd_revision_requested` / `PRD未通过，按反馈重新分析`，将反馈写入 `.superlooper/reports/<session_id>/prd_feedback.md`，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase prd --phase-status running --last-command "PRD未通过，按反馈重新分析" --active-feedback-report .superlooper/reports/<session_id>/prd_feedback.md --rollback-target-phase prd --change-request-count <next_change_request_count> --next-action "调用 analyst 按反馈重新生成 PRD"`，再重新调用 `analyst`，payload 必须额外包含 `feedback_report` 与 `prd_revision`。
10. 当用户确认 PRD 并进入 UI 设计前，先调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase ui_design --phase-status pending --last-command "用户确认 PRD，进入 UI 设计" --generated-file .superlooper/context/<session_id>/prd.md --ui-status NOT_STARTED --ui-output-dir .superlooper/context/<session_id>/ui/ --ui-artifacts-validated false --next-action "运行 /spl:ui <session_id>"`。

禁止事项：

- 不进入流程三 UI 设计。
- 不进入流程四系统设计。
- 不生成 `module-split.json`。
- 不生成 `execution_manifest.json`。
- 不调用编码 agent。
