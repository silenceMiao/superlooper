---
name: superlooper-status
summary: Show a Superlooper task without advancing it.
description: Show a Superlooper task without advancing it.
---

# Superlooper Status

Explicit invocation: `$superlooper-status <task_id>`.

Run this skill in a non-ephemeral, read-only Codex parent session. For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `python "<plugin_root>/scripts/<script>.py"` with `--workspace-root .`.

Read the requested `.superlooper/` task state with `python "<plugin_root>/scripts/status_session.py" --workspace-root . --task-id <task_id>`. Report its current phase, status, generated artifacts, reports, and next action without creating, modifying, or advancing the task.
