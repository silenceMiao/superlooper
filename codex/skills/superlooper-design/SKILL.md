---
name: superlooper-design
summary: Run the Superlooper system design and module split stage.
description: Run the Superlooper system design and module split stage.
---

# Superlooper Design

Explicit invocation: `$superlooper-design <task_id>`.

For every shared script, resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `python "<plugin_root>/scripts/<script>.py"` with `--workspace-root .`.

Require approved and validated UI artifacts under `.superlooper/context/<task_id>/ui/`. Before invoking the Codex architect role, record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase design --phase-status running --last-command "$superlooper-design <task_id>"` and retain design outputs under `.superlooper/context/<task_id>/design/`.

After the architect writes `.superlooper/context/<task_id>/design/initialization-advice.md`, run `python "<plugin_root>/scripts/validate_miao_contracts.py" --workspace-root . --task-id <task_id> --scope initialization-advice`. Read `project_category`, `project_version`, and `project_root` only from its first YAML block; this adapter must not infer missing values from `project-profile.md` or natural-language prose. Stop if the block is missing or validation fails.

In `standard` mode, after upstream alignment passes, persist the validated values with `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase design --phase-status running --last-command "$superlooper-design <task_id>" --project-category <project_category> --project-version <project_version> --project-root <project_root>`, then run `python "<plugin_root>/scripts/initialize_project_structure.py" --workspace-root . --task-id <task_id> --project-category <project_category> --project-version <project_version> --project-root <project_root>`. Each argv value must be copied unchanged from the validated machine block. Generate the post-initialization module split, validate it through `python "<plugin_root>/scripts/validate_miao_contracts.py" --workspace-root . --task-id <task_id> --scope module-split`, then record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase run --phase-status pending --last-command "$superlooper-design <task_id>"`.

In `strict_review` mode, first record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase design --phase-status waiting_review --last-command "$superlooper-design <task_id>"` and stop for design approval. After approval, enter `initialization/waiting_review` for project-category selection and remain there for project-version selection. Only after both choices agree with the validated machine block may the adapter run `initialize_project_structure.py`. After initialization succeeds, generate and validate the post-initialization module split, then return to `design/waiting_review` for module-split review. Advance to `run/pending` only after the user submits `继续任务` or `生成执行清单` through the shared reducer. Do not collapse category selection, version selection, and module-split review into one checkpoint.

If design, initialization, or module-split validation fails in either mode, record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase design --phase-status failed --last-command "$superlooper-design <task_id>"` and stop.

When pre-initialization design feedback requests revision, pass the original user text as one argv value to `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`. The shared reducer writes `design_feedback.md` and performs the design review transition; this adapter must not hand-write a second state machine. After initialization, pass requirement or design changes to the same shared reducer so it can require impact analysis rather than overwrite downstream artifacts.
