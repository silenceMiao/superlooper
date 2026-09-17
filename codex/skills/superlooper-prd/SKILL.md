---
name: superlooper-prd
summary: Run the Superlooper requirement and PRD review stage.
description: Run the Superlooper requirement and PRD review stage.
---

# Superlooper PRD

Explicit invocation: `$superlooper-prd <requirement_path> [task_id]`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `python "<plugin_root>/scripts/<script>.py"` with `--workspace-root .`.

Require an existing requirement file and pass it as one safely quoted argv value. Without a task ID, create a task with `python "<plugin_root>/scripts/create_session.py" --workspace-root . --new-task --requirement-path <requirement_path>`. With a task ID, recover it idempotently with `python "<plugin_root>/scripts/create_session.py" --workspace-root . --task-id <task_id> --requirement-path <requirement_path>`; the canonical requirement path must match and existing task state must not be reset.

Before invoking the Codex analyst role, record the generation checkpoint with `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase prd --phase-status running --last-command "$superlooper-prd <requirement_path> <task_id>"`. Route only the requirement phase to the analyst and write the PRD to `.superlooper/context/<task_id>/prd.md`.

If the analyst is blocked by required decisions, record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase prd --phase-status blocked --last-command "$superlooper-prd <requirement_path> <task_id>" --next-action "确认关键决策后重新运行 PRD 阶段"` and stop. If the analyst output is malformed or PRD contract validation fails, record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase prd --phase-status failed --last-command "$superlooper-prd <requirement_path> <task_id>" --last-error <校验失败原因> --next-action <修复 analyst 输出后重新运行 PRD 阶段>` and stop. If the PRD contract passes, record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase prd --phase-status waiting_review --last-command "$superlooper-prd <requirement_path> <task_id>" --generated-file .superlooper/context/<task_id>/prd.md --next-action "审核 PRD"`, then stop at the PRD review handshake.

For PRD approval or revision feedback, pass the original user text as one argv value to `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`. The shared reducer writes feedback reports and performs the review state transition; this adapter must not hand-write a second review state machine. Continue only from the reducer result and do not advance to UI design without the required user approval.
