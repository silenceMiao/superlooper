---
name: superlooper-status
summary: Show a Superlooper session without advancing it.
description: Show a Superlooper session without advancing it.
---

# Superlooper Status

Explicit invocation: `$superlooper-status <session_id>`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `<plugin_root>/scripts/<script>.py` with `--workspace-root .`.

Read the requested `.superlooper/` session state with `scripts/status_session.py`. Report its current phase, status, generated artifacts, reports, and next action without creating, modifying, or advancing the session.
