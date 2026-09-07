---
description: 查看 Superlooper session 当前阶段、产物路径、失败原因和下一步动作。
argument-hint: "<session_id>"
allowed-tools: Read, Bash, Glob, Grep
---

# /superlooper:spl:status

`/superlooper:spl:status` 是只读状态入口，不推进 Superlooper 业务流程。

用户参数：`$ARGUMENTS`

执行规则：

1. 解析 `session_id`。
2. 调用 `python scripts/status_session.py --workspace-root <workspace_root> --session-id <session_id>`。
3. `status_session.py` 必须先按 `schemas/session-state.schema.json` 校验 state 的字段和枚举；校验失败时输出错误并列出可用 session。
4. 如果 state 文件不存在，输出可用 session 目录列表。
5. 不修改任何文件。

输出必须包含：

- session_id
- current_phase
- phase_status
- generated_files
- reports
- last_error
- next_actions
