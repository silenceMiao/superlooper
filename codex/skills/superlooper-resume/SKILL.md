---
name: superlooper-resume
summary: Resume a Superlooper task without bypassing review gates.
description: Resume a Superlooper task without bypassing review gates.
---

# Superlooper Resume

Explicit invocation: `$superlooper-resume <task_id>`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `python "<plugin_root>/scripts/<script>.py"` with `--workspace-root .`.

Use `.superlooper/` as the authoritative task state location. When user input is present, pass the original text as one safely quoted argv value to `python "<plugin_root>/scripts/normalize_user_intent.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`, then invoke `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`. Without user input, invoke `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id>` to obtain the next action.

Follow the next action derived from the shared task state. For `run/waiting_review + execution_summary_status=BLOCKED`, only the explicit canonical action `重试执行摘要` may recover the summary: failed prerequisites keep `run/waiting_review + BLOCKED`, while successful validation returns `run/pending + NOT_STARTED`. For `READY_FOR_APPROVAL`, Codex passes approval directly to the shared reducer and does not perform Claude registered-Agent discovery; subsequent module dispatch continues through logical names and the renderer. Do not create a new task, skip PRD/UI/execution-summary/final-review gates, or overwrite downstream artifacts outside the allowed rollback scope.
