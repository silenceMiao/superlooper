---
name: superlooper-resume
summary: Resume a Superlooper session without bypassing review gates.
description: Resume a Superlooper session without bypassing review gates.
---

# Superlooper Resume

Explicit invocation: `$superlooper-resume <session_id>`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `<plugin_root>/scripts/<script>.py` with `--workspace-root .`.

Use `.superlooper/` as the authoritative session location. Normalize the current user input with `scripts/normalize_user_intent.py`, then invoke `scripts/resume_session.py` for the selected session.

Follow the next action derived from the shared session state. Do not create a new session, skip PRD/UI/execution-summary/final-review gates, or overwrite downstream artifacts outside the allowed rollback scope.
