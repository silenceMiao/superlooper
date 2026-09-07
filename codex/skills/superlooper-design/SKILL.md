---
name: superlooper-design
summary: Run the Superlooper system design and module split stage.
description: Run the Superlooper system design and module split stage.
---

# Superlooper Design

Explicit invocation: `$superlooper-design <session_id>`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `<plugin_root>/scripts/<script>.py` with `--workspace-root .`.

Require approved UI artifacts under `.superlooper/context/<session_id>/ui/`. Route the system design stage to the Codex architect role and retain design outputs under `.superlooper/context/<session_id>/design/`.

After upstream alignment passes, use `scripts/initialize_project_structure.py` and validate the generated module split through `scripts/validate_miao_contracts.py`. Respect the existing `standard` and `strict_review` state transitions; do not skip a required review handshake.
