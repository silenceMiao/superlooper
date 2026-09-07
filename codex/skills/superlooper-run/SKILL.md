---
name: superlooper-run
summary: Prepare and execute the Superlooper run stage through the Codex native adapter.
description: Prepare and execute the Superlooper run stage through the Codex native adapter.
---

# Superlooper Run

Explicit invocation: `$superlooper-run <session_id>`.

This skill is the Codex entry adapter for flows five through seven in the shared `skills/superlooper/SKILL.md`. It does not define a separate state machine, DAG, report format, quality gate, or apply policy.

## Shared-script boundary

1. Resolve `plugin_root` from this loaded `SKILL.md` as `../../..`. Never resolve `scripts/...` relative to the target workspace.
2. Use the current target project as `workspace_root=.`. All shared-script invocations below use the installed `<plugin_root>/scripts/<script>.py` and must retain `--workspace-root . --session-id <session_id>`.
3. Use a non-ephemeral Codex session with permission to write the target project's `.superlooper/` directory. `task_apply_to_workspace` may write target project files only after the shared review, merge, test, and conflict gates pass.
4. Before preparing a run, confirm the approved UI artifacts, design artifacts, `module-split.json`, `project_initialized=true`, and the referenced `initialization_report` satisfy shared flow-five preconditions.

## Prepare the execution summary

Run the shared preparation chain in this exact order. Stop immediately if any command fails.

1. `<plugin_root>/scripts/update_session.py --workspace-root . --session-id <session_id> --current-phase run --phase-status running --last-command "$superlooper-run <session_id>" --generated-file .superlooper/manifests/<session_id>/module-split.json --next-action "等待执行清单和执行摘要生成完成"`
2. `<plugin_root>/scripts/generate_execution_manifest.py --workspace-root . --session-id <session_id> --platform codex`
3. `<plugin_root>/scripts/generate_runtime_agents.py --workspace-root . --session-id <session_id> --agents-dir agents --platform codex`
4. `<plugin_root>/scripts/validate_miao_contracts.py --workspace-root . --session-id <session_id> --agents-dir agents --scope execution`
5. `<plugin_root>/scripts/build_execution_summary.py --workspace-root . --session-id <session_id>`
6. `<plugin_root>/scripts/validate_miao_contracts.py --workspace-root . --session-id <session_id> --scope execution-summary`

Only when `execution_summary_status=READY_FOR_APPROVAL`, call `<plugin_root>/scripts/update_session.py --workspace-root . --session-id <session_id> --current-phase run --phase-status waiting_review --last-command "$superlooper-run <session_id>" --generated-file .superlooper/manifests/<session_id>/execution_manifest.json --generated-file .superlooper/agents/<session_id>/ --report .superlooper/reports/<session_id>/execution_summary.md --execution-summary-status READY_FOR_APPROVAL --execution-summary-report .superlooper/reports/<session_id>/execution_summary.md --next-action "审核 execution_summary.md；确认后回复 按此执行"`, then stop for the existing execution-summary review.

If the user rejects the summary, call `<plugin_root>/scripts/resume_session.py --workspace-root . --session-id <session_id> --user-input "执行摘要未通过，返回修正：<反馈内容>"`. Do not write a rollback state directly.

## Execute only after approval

When the user approves with `按此执行` (or the shared `strict_review` equivalent), call `<plugin_root>/scripts/resume_session.py --workspace-root . --session-id <session_id> --user-input "按此执行"`. Confirm the resulting shared state is `run/running` before dispatching work.

Read nodes, dependencies, and payloads only from `.superlooper/manifests/<session_id>/execution_manifest.json`. This Manifest is the sole DAG source. Use the Codex native adapter in `codex/dispatcher/README.md` to call `spawn_agent` for eligible `mod_*` nodes. Each module child receives only its current node payload, its current module object, and the listed design context; it must not receive the original requirement document, another module payload, or another module output directory.

After every module finishes, validate its `artifact_manifest.json` and follow shared steps D4 through D8.6 without bypassing any gate:

1. Run `code-reviewer`; only `code_review_status=PASS` permits `task_merge`.
2. Run `system_merger`; only a valid `merge_report.json` with `status=success` permits `task_integration_test`.
3. Run `tester`; only `test_status=PASS` permits `task_apply_to_workspace`.
4. Run `workspace_applier`; a same-path, different-content target file remains blocked unless the user explicitly authorizes the shared overwrite option. A conflict report never counts as a successful apply.
5. After a valid `apply_report.json`, build `session_report.md`, run `requirement-verifier`, validate `requirement_alignment_report.md`, and stop for the required final review.
6. Complete delivery only after `<plugin_root>/scripts/resume_session.py --workspace-root . --session-id <session_id> --user-input "需求校对通过，完成交付"` revalidates the PASS report and advances shared state to `report/passed`.

For code-review failure, test failure, apply retry, requirement-alignment revision, or approved impact-analysis local rerun, always route the user's normalized feedback through `<plugin_root>/scripts/resume_session.py --workspace-root . --session-id <session_id> --user-input "<shared canonical feedback>"`. Do not mutate shared state directly or restart the whole workflow.
