---
name: superlooper-ui
summary: Run the Superlooper UI design and review stage.
description: Run the Superlooper UI design and review stage.
---

# Superlooper UI

Explicit invocation: `$superlooper-ui <task_id>`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `python "<plugin_root>/scripts/<script>.py"` with `--workspace-root .`.

Read the approved PRD from `.superlooper/context/<task_id>/prd.md`. Before invoking the Codex UI-architect role, record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase ui_design --phase-status running --last-command "$superlooper-ui <task_id>" --ui-status IN_PROGRESS --ui-artifacts-validated false`.

Write the fixed UI artifacts below `.superlooper/context/<task_id>/ui/` and validate them with `python "<plugin_root>/scripts/validate_miao_contracts.py" --workspace-root . --task-id <task_id> --scope ui-artifacts`. On failure, record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase ui_design --phase-status failed --last-command "$superlooper-ui <task_id>" --ui-status FAILED --ui-artifacts-validated false` and stop. On success, record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase ui_design --phase-status waiting_review --last-command "$superlooper-ui <task_id>" --ui-status READY_FOR_REVIEW --ui-artifacts-validated true` and stop at the shared UI review handshake.

For UI approval, UI revision, or a requirement change reported during UI review, pass the original user text as one argv value to `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`. The shared reducer writes the relevant feedback report and performs the review state transition; this adapter must not hand-write a second state machine. Continue only from the reducer result and do not enter system design before UI approval.
