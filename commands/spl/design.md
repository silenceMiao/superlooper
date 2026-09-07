---
description: 执行 Superlooper 流程四，输出系统设计、自动初始化和初始化后 module-split.json。
argument-hint: "<session_id>"
allowed-tools: Read, Write, Bash, Glob, Grep, Agent
---

# /superlooper:spl:design

`/superlooper:spl:design` 是系统设计分段触发入口，只执行 `skills/superlooper/SKILL.md` 的流程四系统设计、初始化和初始化后模块拆分准备，不启动执行清单或编码。默认 `standard` 模式自动使用 `architect` 初始化建议完成初始化与模块拆分；`strict_review` 模式保留设计、初始化分类、初始化版本和模块拆分人工握手。

用户参数：`$ARGUMENTS`

执行规则：

1. 读取 `skills/superlooper/SKILL.md`、`agents/architect.md`、`docs/agent-flows/architect-flow.md`、`agents/ui-architect.md`、`docs/agent-flows/ui-architect-flow.md`、`schemas/module-split.schema.json`、`configs/interaction-flow.json`。
2. 设计阶段对用户自然语言反馈必须先归一化为 `configs/interaction-flow.json` 中 `design` 阶段声明的 canonical action；`allowed_replies` 是内部 canonical reply 和推荐回复，不是用户唯一可输入内容。
3. 确认 PRD 和 UI 设计均已由用户审核通过。
4. 确认 `.superlooper/context/<session_id>/prd.md` 存在。
5. 确认 `.superlooper/context/<session_id>/ui/ui-spec.md`、`.superlooper/context/<session_id>/ui/page-map.md`、`.superlooper/context/<session_id>/ui/interaction-flow.md`、`.superlooper/context/<session_id>/ui/ui-handoff.md`、`.superlooper/context/<session_id>/ui/preview.html` 均存在。
6. 调用 `python scripts/validate_miao_contracts.py --workspace-root <workspace_root> --session-id <session_id> --scope ui-artifacts` 校验 UI 产物；若校验失败，停止并要求先运行 `/spl:ui <session_id>` 修复 UI 产物。
7. 确认 `.superlooper/state/<session_id>.json` 中 `ui_status=APPROVED` 且 `ui_artifacts_validated=true`；若不满足，不得调用 `architect`。
8. 先调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase design --phase-status running --last-command "/spl:design <session_id>" --generated-file .superlooper/context/<session_id>/prd.md --generated-file .superlooper/context/<session_id>/ui/ui-handoff.md --next-action "等待系统设计阶段输出完成"`。
9. 调用 `architect` agent，payload 必须包含 `session_id`、`prd_path`、`ui_output_dir`、`design_output_dir`、`workspace_root`、`initialization_advice_path`。初始化完成前不得传入正式 `module_split_path` 作为必产物。
10. 设计文档生成后，`standard` 模式不得默认停止给用户审核完整设计文档；必须读取 `initialization-advice.md` 中的推荐 `project_category`、`project_version` 与 `project_root`，并把 `upstream_alignment_status` 写入 `.superlooper/reports/<session_id>/upstream_alignment.md`。
11. `upstream_alignment_status=PASS` 时，调用 `python scripts/initialize_project_structure.py --workspace-root <workspace_root> --session-id <session_id> --project-category <project_category> --project-version <project_version> --project-root <project_root>` 自动初始化项目结构。
12. `upstream_alignment_status=FAIL` 且 `loop_required=true` 时，按 `loop_policy.max_auto_loop_per_phase` 受控回到对应阶段重生成；达到上限后停止并升级人工处理。`upstream_alignment_status=BLOCKED` 时停止并列出 `blocking_decisions`。
13. 项目结构初始化成功后，再调用 `architect` 生成正式 `module-split.json`，payload 必须包含 `session_id`、`prd_path`、`ui_output_dir`、`design_output_dir`、`module_split_path`、`workspace_root`、`initialization_report`。
14. 调用 `python scripts/validate_miao_contracts.py --workspace-root <workspace_root> --session-id <session_id> --scope module-split` 校验模块拆分清单。
15. `module-split` 校验通过后，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase run --phase-status pending --last-command "/spl:design <session_id>" --generated-file .superlooper/context/<session_id>/design/architecture.md --generated-file .superlooper/context/<session_id>/design/tech-stack.md --generated-file .superlooper/context/<session_id>/design/project-profile.md --generated-file .superlooper/context/<session_id>/design/initialization-advice.md --generated-file .superlooper/manifests/<session_id>/module-split.json --report .superlooper/reports/<session_id>/upstream_alignment.md --next-action "运行 /spl:run <session_id> 生成执行摘要"`。
16. `strict_review` 模式下，设计文档生成后保留人工审核，审核通过后按旧握手提示用户回复“java”或“go”或“springboot”或“pom”或“lua”，再提示对应版本如“jdk-8”“jdk-11”“jdk-17”“go-1.25”“springboot-2.x”“springboot-3.x”“maven-3.5.x”“maven-3.9.x”“lua-4.x”“lua-5.x”，模块拆分生成后仍等待用户回复“继续任务”或“生成执行清单”。
17. 用户审核设计未通过且 `project_initialized=false` 时，将自然语言反馈归一化为 `design_revision_requested` / `设计未通过，按反馈重新设计`，写入 `.superlooper/reports/<session_id>/design_feedback.md`，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase design --phase-status running --last-command "设计未通过，按反馈重新设计" --active-feedback-report .superlooper/reports/<session_id>/design_feedback.md --rollback-target-phase design --change-request-count <next_change_request_count> --next-action "调用 architect 按反馈重新生成设计文档"`，再重新调用 `architect`，payload 必须额外包含 `feedback_report`、`design_revision` 与 `ui_output_dir`，初始化完成前仍不得生成正式 `module-split.json`。
18. 用户审核设计未通过但 `project_initialized=true` 时，不得直接覆盖设计、模块拆分或执行产物；必须将自然语言反馈归一化为 `change_impact_requested` / `需求变更，执行影响分析`，进入深层变更影响分析。
19. 若设计、初始化或模块拆分校验失败，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase design --phase-status failed --last-command "/spl:design <session_id>" --generated-file .superlooper/context/<session_id>/prd.md --last-error "设计、初始化或 module-split 校验失败" --next-action "修复设计输出后重新运行 /spl:design <session_id>"`，然后停止。

禁止事项：

- 不生成 `execution_manifest.json`。
- 不创建动态 `module_*` agent。
- 不调用 `developer` 或并行编码 agent。
- 不把 UI 反馈写入 `design_feedback.md`。
