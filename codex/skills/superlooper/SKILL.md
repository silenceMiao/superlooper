---
name: superlooper
summary: Start or continue a Superlooper task from a requirement file.
description: Start or continue a Superlooper task from a requirement file.
---

# Superlooper

Explicit invocation: `$superlooper <requirement_path> [--task-name "<task_name>"]`.

Execute `python --version` in the current actual Agent session, then execute `python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"` to require Python 3.9+. Continue only when both commands succeed; only then may the entrypoint resolve plugin files, read `.superlooper/`, run a shared script, or invoke the Codex analyst.

If either command fails, report exactly `当前 Agent 会话无法执行 Python；Superlooper workflow 在该环境中不可用` and explain that 安装本身不等于运行依赖满足. Stop immediately: 不创建 `.superlooper/`、不读取 task state、不恢复或推进 task、不调用 agent、不修改目标项目、不自动安装 Python、不修改 PATH 或 sandbox.

After the probes succeed, use a non-ephemeral, `workspace-write` Codex parent session. Resolve `plugin_root` from the directory of this loaded `SKILL.md` as `../../..`; never resolve `scripts/...` relative to the target workspace. Invoke `python "<plugin_root>/scripts/<script>.py"` with `--workspace-root .`.

Use `.superlooper/` in the current workspace as the only task state location. Inspect active tasks with `python "<plugin_root>/scripts/status_session.py" --workspace-root . --list-active` before creating a task. This mode ignores task identity environment variables and must stop if any task state is invalid.

- For one active task, pass the original user text as a single argv value to `python "<plugin_root>/scripts/normalize_user_intent.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`, then to `python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>`. Consume the shared reducer result and continue that task; do not define a second state transition.
- For multiple active tasks, show each `task_name` (or `未命名任务`), `task_id`, and current phase/status, then ask the user to select by `task_id`.
- For a new task, require an existing requirement file. Run `python "<plugin_root>/scripts/create_session.py" --workspace-root . --new-task --requirement-path <requirement_path>` and include `--task-name <task_name>` only when supplied. Pass each user-controlled value as a single argv value using the current shell's safe quoting rules; never concatenate requirement paths, task names, or feedback into shell source. Read the system-generated `task_id` from the script output; never construct or accept a user-provided ID for this entrypoint.

After task creation, reuse the canonical PRD adapter chain instead of routing directly to the analyst:

1. Record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase prd --phase-status running --last-command "$superlooper <requirement_path>" --next-action "等待需求分析阶段输出完成"`.
2. Route the requirement phase to the Codex analyst role with `task_id`, `requirement_path`, and `.superlooper/context/<task_id>/prd.md` as the output path.
3. Validate the analyst status block and PRD artifact contract exactly as `$superlooper-prd` does. A blocked or malformed result must record the corresponding `prd/blocked` or `prd/failed` checkpoint and stop.
4. Only a valid PRD may record `python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id> --current-phase prd --phase-status waiting_review --last-command "$superlooper <requirement_path>" --generated-file .superlooper/context/<task_id>/prd.md --next-action "审核 PRD；通过后进入 UI 设计"`, then stop at the existing PRD review handshake.

Keep all task state, reports, manifests, and outputs under `.superlooper/`.
