---
name: superlooper-run
summary: Prepare and execute the Superlooper run stage through the Codex native adapter.
description: Prepare and execute the Superlooper run stage through the Codex native adapter.
---

# Superlooper Run

Explicit invocation: `$superlooper-run <task_id>`.

This skill is the Codex entry adapter for flows five through seven in the shared `skills/superlooper/SKILL.md`. It does not define a separate state machine, DAG, report format, quality gate, or apply policy.

## Shared-script boundary

1. Resolve `plugin_root` from this loaded `SKILL.md` as `../../..`. Never resolve `scripts/...` relative to the target workspace.
2. Use the current target project as `workspace_root=.`. All shared-script invocations below use `python "<plugin_root>/scripts/<script>.py"` and must retain `--workspace-root . --task-id <task_id>`.
3. Use a non-ephemeral Codex session with permission to write the target project's `.superlooper/` directory. `task_apply_to_workspace` may write target project files only after the shared review, merge, test, and conflict gates pass.
4. Before preparing a run, confirm the approved UI artifacts, design artifacts, `module-split.json`, `project_initialized=true`, and the referenced `initialization_report` satisfy shared flow-five preconditions.

## Prepare the execution summary

Run the shared preparation chain in this exact order. Stop immediately if any command fails.

1. `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase run --phase-status running --last-command "$superlooper-run <task_id>" --generated-file .superlooper/manifests/<task_id>/module-split.json --next-action "等待执行清单和执行摘要生成完成"`
2. `python "<plugin_root>/scripts/generate_execution_manifest.py" --workspace-root . --task-id <task_id> --platform codex`
3. `python "<plugin_root>/scripts/generate_runtime_agents.py" --workspace-root . --task-id <task_id> --agents-dir agents --platform codex`; generation must not clean runtime or registered dynamic Agent files belonging to other tasks or existing files in the current task that are not part of this generation.
4. `python "<plugin_root>/scripts/validate_miao_contracts.py" --workspace-root . --task-id <task_id> --agents-dir agents --scope execution`
5. `python "<plugin_root>/scripts/build_execution_summary.py" --workspace-root . --task-id <task_id>`
6. `python "<plugin_root>/scripts/validate_miao_contracts.py" --workspace-root . --task-id <task_id> --scope execution-summary`

Only when `execution_summary_status=READY_FOR_APPROVAL`, call `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase run --phase-status waiting_review --last-command "$superlooper-run <task_id>" --generated-file .superlooper/manifests/<task_id>/execution_manifest.json --generated-file .superlooper/agents/<task_id>/ --report .superlooper/reports/<task_id>/execution_summary.md --execution-summary-status READY_FOR_APPROVAL --execution-summary-report .superlooper/reports/<task_id>/execution_summary.md --next-action "审核 execution_summary.md；确认后回复 按此执行"`, then stop for the existing execution-summary review.

A `BLOCKED` summary must be recorded with `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase run --phase-status waiting_review --last-command "$superlooper-run <task_id>" --report .superlooper/reports/<task_id>/execution_summary.md --execution-summary-status BLOCKED --execution-summary-report .superlooper/reports/<task_id>/execution_summary.md --next-action "修正阻断项后回复 重试执行摘要"` and remain `run/waiting_review + BLOCKED`. The only canonical recovery action is `重试执行摘要`; approval, start, continue, or status input must not recover it. Pass the original retry text to the shared reducer. If retry prerequisites still fail, keep `run/waiting_review + BLOCKED`; only a successful retry validation may return the state to `run/pending + NOT_STARTED` for summary regeneration.

If the user rejects the summary, pass the original user text as one safely quoted argv value to `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`. Do not replace the original text with a canonical reply and do not write a rollback state directly.

## Execute only after approval

When the user approves with `按此执行` (or the shared `strict_review` equivalent), call `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input "按此执行"`. Confirm the resulting shared state is `run/running` before dispatching work. Codex does not perform Claude registered-Agent discovery; it continues to dispatch from Manifest logical names through the renderer.

When recording a validated `change_impact_report.md`, do not pass `--affected-module` to `update_session.py` and do not otherwise write a non-empty state `affected_modules`; the field remains empty while the report awaits review. Only after the shared reducer approves `影响分析通过，执行局部重跑` may it persist the report's authorized module IDs. Then dispatch only the module IDs in state `affected_modules`; the reducer consumes the state `change_impact_report` review pointer so the same report is not reviewed again. Outside local rerun, an empty `affected_modules` keeps the full Manifest DAG behavior.

Read nodes, dependencies, and payloads only from `.superlooper/manifests/<task_id>/execution_manifest.json`. This Manifest is the sole DAG source. For every eligible `mod_*` node, run `python "<plugin_root>/scripts/render_codex_spawn_prompt.py" --workspace-root . --task-id <task_id> --node-id <node_id>` and stop immediately if it fails. Pass its 完整 stdout unchanged to `spawn_agent(..., fork_turns="none", message=<renderer stdout>)`; do not reconstruct, shorten, or supplement the prompt manually. The renderer injects the current runtime Agent file, current node payload, current module object, listed design paths, and output contract. The child must not receive the original requirement document, another module payload, or another module output directory.

After every module finishes, validate its `artifact_manifest.json` and follow shared steps D4 through D8.6 without bypassing any gate. Each module directory, artifact manifest, and produced file must resolve inside that module's output directory; declared `produced_files[].path` values and actual output files must both be unique under the shared Windows-equivalent path rules. For a local rerun, after all selected modules finish and their artifact contracts pass, call `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase run --phase-status running --last-command "$superlooper-run <task_id>" --clear-affected-modules --next-action "enter global code review, merge, test, and apply gates"` before global code review. Before this checkpoint, resume dispatches the original state affected_modules; after it, the full DAG downstream gates must not reuse the old local scope.

1. Run `code-reviewer`; `code_review_status=PASS` permits `task_merge` only when `reviewed_modules` is non-empty, duplicate-free, and exactly equals the complete Manifest module-ID set.
2. Run `system_merger`; module directories, artifact manifests, and declared sources must resolve inside their module output directories. Merge rebuilds an empty staging snapshot, computes a `sha256:<64hex>` `snapshot_digest`, and transactionally publishes the snapshot with `merge_report.json`; conflicts, digest failure, or publication failure must preserve the prior successful snapshot. Only a valid success report permits `task_integration_test`.
3. Run `tester`; only `test_status=PASS` permits `task_apply_to_workspace`.
4. Run `workspace_applier`; before planning or writing, recompute the merged-tree digest and require an exact match with `merge_report.json.snapshot_digest`. Merged sources and workspace targets must resolve inside their authorized roots and be rechecked before writes and rollback. A same-path, different-content target file remains blocked unless the user explicitly authorizes the shared overwrite option. Create/overwrite operations form one transaction; apply I/O failure, post-apply validation failure, or success-report publication failure must roll it back, and backup cleanup occurs only after successful report publication. A conflict report never counts as a successful apply. A failed apply must report `rollback.status`: `success` allows retry only after the cause is fixed, while `partial` requires manual recovery from the retained backup. Neither result permits the final gates.
5. After a valid `apply_report.json`, build `session_report.md`, run `requirement-verifier`, validate `requirement_alignment_report.md`, and stop for the required final review.
6. Complete delivery only after `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input "需求校对通过，完成交付"` revalidates the PASS report and advances shared state to `report/passed`.

For code-review failure, test failure, apply retry, requirement-alignment revision, or approved impact-analysis local rerun, always pass the original user text as one safely quoted argv value to `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`. The shared reducer performs normalization; this adapter must not replace feedback with canonical text, mutate shared state directly, or restart the whole workflow.
