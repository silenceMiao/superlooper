---
description: 执行 Superlooper 流程三，输出 UI 设计、交互流程和 HTML 预览原型。
argument-hint: "<task_id>"
allowed-tools: Read, Write, Bash, Glob, Grep, Agent
---

# /superlooper:spl:ui

`/superlooper:spl:ui` 是 UI 设计分段触发入口，只执行 `skills/superlooper/SKILL.md` 的流程三 UI 设计、交互与 HTML 预览审核，不执行系统设计、初始化、模块拆分、执行清单或编码。

用户参数：`$ARGUMENTS`

执行规则：

1. 从插件安装根读取 `${CLAUDE_PLUGIN_ROOT}/skills/superlooper/SKILL.md`、`${CLAUDE_PLUGIN_ROOT}/agents/ui-architect.md`、`${CLAUDE_PLUGIN_ROOT}/docs/agent-flows/ui-architect-flow.md`、`${CLAUDE_PLUGIN_ROOT}/configs/interaction-flow.json`；不得把这些插件文件解释为目标工作区相对路径。
2. UI 设计阶段对用户自然语言反馈必须先归一化为 `configs/interaction-flow.json` 中 `ui_design` 阶段声明的 canonical action；`allowed_replies` 是内部 canonical reply 和推荐回复，不是用户唯一可输入内容。
3. 确认 `.superlooper/context/<task_id>/prd.md` 存在，且 PRD 已由用户审核通过。
4. 先调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/update_session.py" --workspace-root <workspace_root> --task-id <task_id> --current-phase ui_design --phase-status running --last-command "/spl:ui <task_id>" --generated-file .superlooper/context/<task_id>/prd.md --ui-status IN_PROGRESS --ui-output-dir .superlooper/context/<task_id>/ui/ --ui-artifacts-validated false --next-action "等待 UI 设计阶段输出完成"`。
5. 调用 `superlooper:ui-architect` agent，payload 必须包含 `task_id`、`prd_path`、`ui_output_dir`、`workspace_root`、`project_mode`、`existing_frontend`；当存在 UI 审核反馈时，payload 必须额外包含 `feedback_report` 与 `ui_revision`。
6. `ui-architect` 必须把固定产物写入 `.superlooper/context/<task_id>/ui/`：`ui-spec.md`、`page-map.md`、`interaction-flow.md`、`ui-handoff.md`、`preview.html`。
7. UI 产物生成后，调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/validate_miao_contracts.py" --workspace-root <workspace_root> --task-id <task_id> --scope ui-artifacts` 校验 UI 产物。
8. 校验失败时，调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/update_session.py" --workspace-root <workspace_root> --task-id <task_id> --current-phase ui_design --phase-status failed --last-command "/spl:ui <task_id>" --ui-status FAILED --ui-output-dir .superlooper/context/<task_id>/ui/ --ui-artifacts-validated false --last-error "UI 产物校验失败" --next-action "修复 UI 产物后重新运行 /spl:ui <task_id>"`，然后停止。
9. 校验通过后，调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/update_session.py" --workspace-root <workspace_root> --task-id <task_id> --current-phase ui_design --phase-status waiting_review --last-command "/spl:ui <task_id>" --generated-file .superlooper/context/<task_id>/ui/ui-spec.md --generated-file .superlooper/context/<task_id>/ui/page-map.md --generated-file .superlooper/context/<task_id>/ui/interaction-flow.md --generated-file .superlooper/context/<task_id>/ui/ui-handoff.md --generated-file .superlooper/context/<task_id>/ui/preview.html --ui-revision <next_ui_revision> --ui-status READY_FOR_REVIEW --ui-output-dir .superlooper/context/<task_id>/ui/ --ui-artifacts-validated true --next-action "审核 UI 设计和 preview.html；通过后使用 UI设计通过，进入系统设计；不通过使用 UI设计未通过，按反馈重新设计"`，并输出流程三完成握手。
10. 用户审核 UI 未通过或用自然语言表达 UI、页面、交互、视觉、预览 HTML 不符合时，把原始反馈作为单个 argv 数据调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/resume_session.py" --workspace-root <workspace_root> --task-id <task_id> --user-input <原始用户输入>`。由 `resume_session.py` 的共享 reducer 归一化为 `ui_revision_requested` / `UI设计未通过，按反馈重新设计`、写入 `ui_feedback.md` 并推进到 `ui_design/running`；command 不得再手写同一审核状态转换。随后按 reducer 返回的 `feedback_report` 与 `ui_revision` 重新调用 `superlooper:ui-architect`。
11. UI 重设计时，未受影响页面 ID、交互 ID、需求追溯编号必须保持稳定；受影响页面、交互或视觉规则必须说明变更原因。
12. 用户确认 UI 设计通过后，把原始反馈作为单个 argv 数据调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/resume_session.py" --workspace-root <workspace_root> --task-id <task_id> --user-input <原始用户输入>`。由共享 reducer 执行 `approve_ui_and_proceed`，推进到 `design/pending`；不得用 `update_session.py` 绕过审核归约器。
13. 用户在 UI 阶段提出需求本身变化时，同样调用 `resume_session.py --user-input <原始用户输入>`，由共享 reducer 归一化为 `prd_revision_requested`、写入 `prd_feedback.md` 并回到 `prd/running`；不得从 `/spl` 全流程重启。

禁止事项：

- 不做需求分析。
- 不读取原始需求文档。
- 不进入流程四系统设计。
- 不生成 `module-split.json`。
- 不生成 `execution_manifest.json`。
- 不调用编码 agent。
- 不修改目标项目根目录业务文件。
