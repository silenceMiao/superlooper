---
description: 执行 Superlooper 流程三，输出 UI 设计、交互流程和 HTML 预览原型。
argument-hint: "<session_id>"
allowed-tools: Read, Write, Bash, Glob, Grep, Agent
---

# /superlooper:spl:ui

`/superlooper:spl:ui` 是 UI 设计分段触发入口，只执行 `skills/superlooper/SKILL.md` 的流程三 UI 设计、交互与 HTML 预览审核，不执行系统设计、初始化、模块拆分、执行清单或编码。

用户参数：`$ARGUMENTS`

执行规则：

1. 读取 `skills/superlooper/SKILL.md`、`agents/ui-architect.md`、`docs/agent-flows/ui-architect-flow.md`、`configs/interaction-flow.json`。
2. UI 设计阶段对用户自然语言反馈必须先归一化为 `configs/interaction-flow.json` 中 `ui_design` 阶段声明的 canonical action；`allowed_replies` 是内部 canonical reply 和推荐回复，不是用户唯一可输入内容。
3. 确认 `.superlooper/context/<session_id>/prd.md` 存在，且 PRD 已由用户审核通过。
4. 先调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase ui_design --phase-status running --last-command "/spl:ui <session_id>" --generated-file .superlooper/context/<session_id>/prd.md --ui-status IN_PROGRESS --ui-output-dir .superlooper/context/<session_id>/ui/ --ui-artifacts-validated false --next-action "等待 UI 设计阶段输出完成"`。
5. 调用 `ui-architect` agent，payload 必须包含 `session_id`、`prd_path`、`ui_output_dir`、`workspace_root`、`project_mode`、`existing_frontend`；当存在 UI 审核反馈时，payload 必须额外包含 `feedback_report` 与 `ui_revision`。
6. `ui-architect` 必须把固定产物写入 `.superlooper/context/<session_id>/ui/`：`ui-spec.md`、`page-map.md`、`interaction-flow.md`、`ui-handoff.md`、`preview.html`。
7. UI 产物生成后，调用 `python scripts/validate_miao_contracts.py --workspace-root <workspace_root> --session-id <session_id> --scope ui-artifacts` 校验 UI 产物。
8. 校验失败时，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase ui_design --phase-status failed --last-command "/spl:ui <session_id>" --ui-status FAILED --ui-output-dir .superlooper/context/<session_id>/ui/ --ui-artifacts-validated false --last-error "UI 产物校验失败" --next-action "修复 UI 产物后重新运行 /spl:ui <session_id>"`，然后停止。
9. 校验通过后，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase ui_design --phase-status waiting_review --last-command "/spl:ui <session_id>" --generated-file .superlooper/context/<session_id>/ui/ui-spec.md --generated-file .superlooper/context/<session_id>/ui/page-map.md --generated-file .superlooper/context/<session_id>/ui/interaction-flow.md --generated-file .superlooper/context/<session_id>/ui/ui-handoff.md --generated-file .superlooper/context/<session_id>/ui/preview.html --ui-revision <next_ui_revision> --ui-status READY_FOR_REVIEW --ui-output-dir .superlooper/context/<session_id>/ui/ --ui-artifacts-validated true --next-action "审核 UI 设计和 preview.html；通过后使用 UI设计通过，进入系统设计；不通过使用 UI设计未通过，按反馈重新设计"`，并输出流程三完成握手。
10. 用户审核 UI 未通过或用自然语言表达 UI、页面、交互、视觉、预览 HTML 不符合时，先归一化为 `ui_revision_requested` / `UI设计未通过，按反馈重新设计`，将反馈写入 `.superlooper/reports/<session_id>/ui_feedback.md`，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase ui_design --phase-status running --last-command "UI设计未通过，按反馈重新设计" --active-feedback-report .superlooper/reports/<session_id>/ui_feedback.md --rollback-target-phase ui_design --change-request-count <next_change_request_count> --ui-revision <next_ui_revision> --ui-status CHANGES_REQUESTED --ui-artifacts-validated false --next-action "调用 ui-architect 按反馈重新生成 UI 设计"`，再重新调用 `ui-architect`。
11. UI 重设计时，未受影响页面 ID、交互 ID、需求追溯编号必须保持稳定；受影响页面、交互或视觉规则必须说明变更原因。
12. 用户确认 UI 设计通过后，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase design --phase-status pending --last-command "UI设计通过，进入系统设计" --generated-file .superlooper/context/<session_id>/ui/ui-spec.md --generated-file .superlooper/context/<session_id>/ui/page-map.md --generated-file .superlooper/context/<session_id>/ui/interaction-flow.md --generated-file .superlooper/context/<session_id>/ui/ui-handoff.md --generated-file .superlooper/context/<session_id>/ui/preview.html --ui-status APPROVED --ui-output-dir .superlooper/context/<session_id>/ui/ --ui-artifacts-validated true --next-action "运行 /spl:design <session_id>"`。
13. 用户在 UI 阶段提出需求本身变化时，先归一化为 `prd_revision_requested` / `需求变更，返回 PRD 修订`，写入 `.superlooper/reports/<session_id>/prd_feedback.md`，回到 PRD 修订；不得从 `/spl` 全流程重启。

禁止事项：

- 不做需求分析。
- 不读取原始需求文档。
- 不进入流程四系统设计。
- 不生成 `module-split.json`。
- 不生成 `execution_manifest.json`。
- 不调用编码 agent。
- 不修改目标项目根目录业务文件。
