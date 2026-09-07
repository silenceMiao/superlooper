---
name: superlooper-prd
summary: Run the Superlooper requirement and PRD review stage.
description: Run the Superlooper requirement and PRD review stage.
---

# Superlooper PRD

Explicit invocation: `$superlooper-prd <requirement_path> [session_id]`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `<plugin_root>/scripts/<script>.py` with `--workspace-root .`.

Require an existing requirement file. Create or recover the `.superlooper/` session with `scripts/create_session.py` and normalize existing-session feedback with `scripts/normalize_user_intent.py`.

Route only the requirement phase to the Codex analyst role. Write the PRD to `.superlooper/context/<session_id>/prd.md`, validate its required contract with `scripts/validate_miao_contracts.py`, and stop at the PRD review handshake. Do not advance to UI design without the user approval required by the shared session state.
