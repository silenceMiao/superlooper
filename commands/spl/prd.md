---
description: 执行 Superlooper 流程一和流程二，输出 PRD 或关键决策看板。
argument-hint: "<requirement_path> [task_id]"
allowed-tools: Read, Write, Bash, Glob, Grep, Agent
---

# /superlooper:spl:prd

`/superlooper:spl:prd` 是 PRD 分段触发入口，只执行 `${CLAUDE_PLUGIN_ROOT}/skills/superlooper/SKILL.md` 的流程一入口与 task 准备、流程二需求分析与 PRD 审核。

用户参数：`$ARGUMENTS`

执行规则：

1. 从插件安装根读取 `${CLAUDE_PLUGIN_ROOT}/skills/superlooper/SKILL.md`、`${CLAUDE_PLUGIN_ROOT}/agents/analyst.md`、`${CLAUDE_PLUGIN_ROOT}/docs/agent-flows/analyst-flow.md`、`${CLAUDE_PLUGIN_ROOT}/configs/interaction-flow.json`；不得把这些插件文件解释为目标工作区相对路径。
2. 需求阶段对用户自然语言反馈必须先归一化为 `configs/interaction-flow.json` 中 `prd` 阶段声明的 canonical action；`allowed_replies` 是内部 canonical reply 和推荐回复，不是用户唯一可输入内容。
3. 确认 `requirement_path`，并把路径作为单个 argv 数据传递，不得拼接为 shell 源码。无 `task_id` 时调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/create_session.py" --workspace-root <workspace_root> --new-task --requirement-path <requirement_path>` 创建新 task；有 `task_id` 时调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/create_session.py" --workspace-root <workspace_root> --task-id <task_id> --requirement-path <requirement_path>` 幂等恢复既有 task。恢复时 requirement path 必须一致，且不得重置已有 state。
4. 确认 `.superlooper/context/<task_id>/` 与 `.superlooper/reports/<task_id>/` 存在后，调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/update_session.py" --workspace-root <workspace_root> --task-id <task_id> --current-phase prd --phase-status running --last-command "/spl:prd <requirement_path> <task_id>" --next-action "等待需求分析阶段输出完成"` 记录业务产物生成 checkpoint。
5. 调用 `superlooper:analyst` agent，payload 必须包含 `task_id`、`requirement_path`、`output_prd_path`。
6. 读取 analyst 输出中的第一个机器可读 `yaml` 代码块。
7. 当 `analyst_status=ANALYST_BLOCKED_BY_DECISION` 时，调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/update_session.py" --workspace-root <workspace_root> --task-id <task_id> --current-phase prd --phase-status blocked --last-command "/spl:prd <requirement_path> <task_id>" --last-error "analyst 输出关键决策看板，等待用户确认 DEC-*" --next-action "一次性确认关键决策看板中的 DEC-*"`，然后停止并要求用户一次性确认 `DEC-*`。
8. 当 `analyst_status=READY_FOR_DESIGN` 时，调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/update_session.py" --workspace-root <workspace_root> --task-id <task_id> --current-phase prd --phase-status waiting_review --last-command "/spl:prd <requirement_path> <task_id>" --generated-file .superlooper/context/<task_id>/prd.md --prd-revision <next_prd_revision> --next-action "审核 PRD；通过后使用 通过，进入 UI 设计；不通过使用 PRD未通过，按反馈重新分析"`，确认 PRD 已写入，并输出流程二完成握手。
9. 当用户审核 PRD 未通过或用自然语言表达 PRD 不符合、需要补充需求时，把原始反馈作为单个 argv 数据调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/resume_session.py" --workspace-root <workspace_root> --task-id <task_id> --user-input <原始用户输入>`。由 `resume_session.py` 的共享 reducer 归一化为 `prd_revision_requested` / `PRD未通过，按反馈重新分析`、写入 `prd_feedback.md` 并推进到 `prd/running`；command 不得再手写同一审核状态转换。随后按 reducer 返回的 `feedback_report` 与 `prd_revision` 重新调用 `superlooper:analyst`。
10. 当用户确认 PRD 时，同样把原始反馈作为单个 argv 数据调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/resume_session.py" --workspace-root <workspace_root> --task-id <task_id> --user-input <原始用户输入>`。由共享 reducer 执行 `approve_and_proceed`，推进到 `ui_design/pending`；不得用 `update_session.py` 绕过审核归约器。

禁止事项：

- 不进入流程三 UI 设计。
- 不进入流程四系统设计。
- 不生成 `module-split.json`。
- 不生成 `execution_manifest.json`。
- 不调用编码 agent。
