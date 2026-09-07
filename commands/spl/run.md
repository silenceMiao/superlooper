---
description: 执行 Superlooper 流程五至流程七，生成执行清单、动态 agent，并启动并行开发闭环。
argument-hint: "<session_id>"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# /superlooper:spl:run

`/superlooper:spl:run` 是运行分段触发入口，执行 `skills/superlooper/SKILL.md` 的流程五、流程六和流程七。此命令必须基于已校验通过的 `module-split.json`、已审核 UI 产物和已完成的项目结构初始化继续执行，生成 `execution_manifest.json` 后先输出 `execution_summary.md` 等待用户确认，不提供 `/spl:manifest`。

用户参数：`$ARGUMENTS`

执行规则：

1. 本文件中的 `python scripts/...` 均表示插件根内脚本路径；安装态目标项目当前目录不要求存在 `scripts/`，目标项目根必须通过 `--workspace-root <workspace_root>` 传入。
2. 读取 `skills/superlooper/SKILL.md`、`schemas/execution-manifest.schema.json`、`schemas/artifact-manifest.schema.json`、`agents/developer.md`、`agents/requirement-verifier.md`、`agents/impact-analyzer.md`、`configs/interaction-flow.json`。
3. 运行阶段对用户自然语言反馈必须先归一化为 `configs/interaction-flow.json` 中 `run` 阶段声明的 canonical action；`allowed_replies` 是内部 canonical reply 和推荐回复，不是用户唯一可输入内容。
4. 当用户在运行、测试、应用或需求反向校对阶段提出需求、UI 或设计变更时，必须归一化为 `change_impact_requested` / `需求变更，执行影响分析`；主调度器将反馈写入 `.superlooper/reports/<session_id>/change_feedback.md`，调用 `impact-analyzer` 读取 PRD、UI 产物、系统设计、`module-split.json`、`execution_manifest.json` 和现有报告，生成 `.superlooper/reports/<session_id>/change_impact_report.md`，再调用 `python scripts/validate_miao_contracts.py --workspace-root <workspace_root> --session-id <session_id> --scope change-impact-report` 校验报告。
5. 影响分析报告校验通过后，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase run --phase-status waiting_review --last-command "需求变更，执行影响分析" --active-feedback-report .superlooper/reports/<session_id>/change_feedback.md --change-impact-report .superlooper/reports/<session_id>/change_impact_report.md --report .superlooper/reports/<session_id>/change_impact_report.md --rollback-target-phase <rollback_target_phase> --invalidated-artifact <affected_artifact> --change-request-count <next_change_request_count> --next-action "审核 change_impact_report.md；通过后使用 影响分析通过，执行局部重跑；不通过使用 影响分析不通过，人工处理"`，并停止等待人工审核。
6. 用户确认 `影响分析通过，执行局部重跑` 后，必须先调用 `python scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "影响分析通过，执行局部重跑"`，由脚本校验 `change_impact_report.md` 并按 `rollback_target_phase` 推回合法阶段；用户选择 `影响分析不通过，人工处理` 时，必须停止自动执行并输出人工处理清单。
7. 运行阶段还必须识别 `代码审查未通过，返回修正`、`测试未通过，返回修正`、`应用冲突已处理，重新应用` 三个返工动作；这些动作只允许通过 `resume_session.py` 更新 state，不得直接写 state 或直接输出完成结论。
8. 确认 `.superlooper/context/<session_id>/ui/ui-handoff.md` 已进入系统设计上下文，且 `.superlooper/state/<session_id>.json` 中 `ui_status=APPROVED`、`ui_artifacts_validated=true`。
9. 确认 `.superlooper/manifests/<session_id>/module-split.json` 已通过 `module-split` 校验；`strict_review` 模式下还必须确认用户已审核模块拆分。
10. 确认 `.superlooper/state/<session_id>.json` 中 `project_initialized=true`，且 `initialization_report` 指向的报告存在。若不满足，停止并提示用户先完成初始化项目结构。
11. 在生成执行清单前，先调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase run --phase-status running --last-command "/spl:run <session_id>" --generated-file .superlooper/manifests/<session_id>/module-split.json --next-action "等待执行清单和执行摘要生成完成"`。
12. 调用 `python scripts/generate_execution_manifest.py --workspace-root <workspace_root> --session-id <session_id>`。
13. 调用 `python scripts/generate_runtime_agents.py --workspace-root <workspace_root> --session-id <session_id> --agents-dir agents`；`--agents-dir agents` 相对插件根目录解析，运行时产物仍写入目标项目 `<workspace_root>`。
14. 调用 `python scripts/validate_miao_contracts.py --workspace-root <workspace_root> --session-id <session_id> --agents-dir agents --scope execution`；静态 `agents/`、`schemas/`、`configs/` 与 `commands/` 从插件根目录读取。
15. 调用 `python scripts/build_execution_summary.py --workspace-root <workspace_root> --session-id <session_id>` 生成 `.superlooper/reports/<session_id>/execution_summary.md`，该脚本必须读取真实 `.superlooper/reports/<session_id>/upstream_alignment.md`。
16. 调用 `python scripts/validate_miao_contracts.py --workspace-root <workspace_root> --session-id <session_id> --scope execution-summary` 校验执行摘要；校验失败或 `execution_summary_status=BLOCKED` 时不得启动并行开发。`scripts/run_execution_dag.py` 如被使用，仅用于生成或校验 DAG state 和记录 script event，不是完整 executor，不得替代动态 `module_*` agent 调度、code review、merge、test、apply 和需求反向校对门禁。
17. 只有 `execution_summary_status=READY_FOR_APPROVAL` 时，才调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase run --phase-status waiting_review --last-command "/spl:run <session_id>" --generated-file .superlooper/manifests/<session_id>/execution_manifest.json --generated-file .superlooper/agents/<session_id>/ --report .superlooper/reports/<session_id>/execution_summary.md --execution-summary-status READY_FOR_APPROVAL --execution-summary-report .superlooper/reports/<session_id>/execution_summary.md --next-action "审核 execution_summary.md；确认后回复 按此执行"`，然后要求用户回复“按此执行”或“执行摘要未通过，返回修正”。
18. 用户回复 `执行摘要未通过，返回修正` 后，必须调用 `python scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "执行摘要未通过，返回修正：<反馈内容>"`，由脚本写入 `.superlooper/reports/<session_id>/execution_summary_feedback.md` 并保持 `rollback_target_phase=design`。
19. 用户回复 `按此执行` 后，必须调用 `python scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "按此执行"`，由脚本重新校验 `execution_summary.md` 为 `READY_FOR_APPROVAL` 后推进到 `run/running`；不得直接调用 `update_session.py` 绕过执行摘要门禁。
20. `strict_review` 模式下可额外输出完整 Manifest 预览，并继续接受“执行”或“开始并行开发”；默认 `standard` 模式不要求用户审核完整 Manifest。
21. 所有模块完成后，按 `skills/superlooper/SKILL.md` 执行 code review、merge、test、apply 门禁。
22. 若 code review 失败，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase run --phase-status failed --last-command "/spl:run <session_id>" --report .superlooper/reports/<session_id>/code_review_report.md --last-error "代码审查失败，请检查 code_review_report.md" --next-action "代码审查未通过，返回修正"`；用户回复后必须由 `resume_session.py` 写入 `code_review_feedback.md` 并推回 `run/pending`。
23. 若 test 失败，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase run --phase-status failed --last-command "/spl:run <session_id>" --report .superlooper/reports/<session_id>/test_report.md --last-error "测试失败，请检查 test_report.md" --next-action "测试未通过，返回修正"`；用户回复后必须由 `resume_session.py` 写入 `test_feedback.md` 并推回 `run/pending`。
24. 若 apply 产生冲突或等待人工处理，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase run --phase-status blocked --last-command "/spl:run <session_id>" --report .superlooper/reports/<session_id>/apply_conflict_report.json --last-error "apply 阶段存在冲突或等待人工处理" --next-action "处理 apply 冲突后回复 应用冲突已处理，重新应用"`；用户回复后必须由 `resume_session.py` 校验冲突报告并推回 `run/pending` 重新应用。
25. 若 apply 成功，先调用 `python scripts/build_session_report.py --workspace-root <workspace_root> --session-id <session_id>` 生成统一报告；再调用 `requirement-verifier` 生成 `requirement_alignment_report.md`；然后调用 `python scripts/validate_miao_contracts.py --workspace-root <workspace_root> --session-id <session_id> --scope requirement-alignment-report` 校验需求反向校对报告。
26. 需求反向校对报告校验通过后，调用 `python scripts/update_session.py --workspace-root <workspace_root> --session-id <session_id> --current-phase requirement_alignment --phase-status waiting_review --last-command "/spl:run <session_id>" --report .superlooper/reports/<session_id>/apply_report.json --report .superlooper/reports/<session_id>/session_report.md --report .superlooper/reports/<session_id>/requirement_alignment_report.md --requirement-alignment-report .superlooper/reports/<session_id>/requirement_alignment_report.md --next-action "审核 requirement_alignment_report.md；回复 需求校对通过，完成交付 或 需求校对未通过，返回修正"`，并要求用户回复“需求校对通过，完成交付”或“需求校对未通过，返回修正”。
27. 用户回复 `需求校对通过，完成交付` 后，必须调用 `python scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "需求校对通过，完成交付"`，由脚本重新校验 `requirement_alignment_report.md` 为 `PASS`、`unmet_requirement_count=0`、`unchecked_acceptance_count=0` 后推进到 `report/passed`；不得直接调用 `update_session.py` 绕过门禁。
28. 最后调用 `python scripts/build_session_report.py --workspace-root <workspace_root> --session-id <session_id>` 重新生成包含需求反向校对结果的统一报告。

禁止事项：

- 不读取原始需求文档。
- 不提供 `/spl:manifest`。
- 不绕过 initialization_report、code review、merge report、test report、apply report、requirement_alignment_report 门禁。
