---
name: superlooper
summary: Start or continue a Superlooper session from a requirement file.
description: Start or continue a Superlooper session from a requirement file.
---

# Superlooper

Explicit invocation: `$superlooper <requirement_path> [session_id]`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `<plugin_root>/scripts/<script>.py` with `--workspace-root .`.

Use `.superlooper/` in the current workspace as the only session state location. Before creating a session, inspect active sessions with `scripts/status_session.py`.

- For one active session, normalize the user input with `scripts/normalize_user_intent.py` and continue the current session.
- For multiple active sessions, ask the user to select one.
- For a new session, require an existing requirement file and create the session with `scripts/create_session.py`.

Route the requirement phase to the Codex analyst role, validate the generated PRD with `scripts/validate_miao_contracts.py`, and stop at the existing PRD review handshake. Keep all session state, reports, manifests, and outputs under `.superlooper/`.
