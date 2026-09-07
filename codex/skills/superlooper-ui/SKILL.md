---
name: superlooper-ui
summary: Run the Superlooper UI design and review stage.
description: Run the Superlooper UI design and review stage.
---

# Superlooper UI

Explicit invocation: `$superlooper-ui <session_id>`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `<plugin_root>/scripts/<script>.py` with `--workspace-root .`.

Read the approved PRD from `.superlooper/context/<session_id>/prd.md` and route only the UI stage to the Codex UI-architect role. Write the fixed UI artifacts below `.superlooper/context/<session_id>/ui/`.

Validate the UI artifacts with `scripts/validate_miao_contracts.py --scope ui-artifacts`. On success, record the UI review state and stop at the shared UI review handshake. Do not continue to system design until the user approves the UI stage.
