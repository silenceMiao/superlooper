---
description: 根据 Superlooper session state 恢复到下一步动作。
argument-hint: "<session_id>"
allowed-tools: Read, Write, Bash, Glob, Grep, Agent
---

# /superlooper:spl:resume

`/superlooper:spl:resume` 是 session 恢复入口，不创建新 session，不跳过人工审核点。

用户参数：`$ARGUMENTS`

执行规则：

1. 解析 `session_id`。
2. 调用 `python scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id>` 获取下一步建议；当用户提供自然语言反馈时，追加 `--user-input <text>` 先做意图归一化。
3. `resume_session.py` 必须先按 `schemas/session-state.schema.json` 校验 state 的字段和枚举；校验失败时直接报错。
4. 当传入 `--user-input` 时，脚本必须写入 `last_user_input_text`、`last_user_canonical_action`、`pending_user_choice` 和 event log；明确反馈类动作必须写入对应 feedback report。
5. 当 state 显示 `waiting_review` 时，只输出待用户确认的动作，不自动跳过审核。
6. 当 state 显示 `run/running` 时，输出“等待执行完成或检查报告”，不重复触发执行链路。
7. 当 state 显示 `running` 且存在 `upstream_alignment.md` 为 `FAIL` 或 `BLOCKED` 时，`resume_session.py` 必须按 `loop_policy.max_auto_loop_per_phase` 更新 `loop_state`，未达上限时写入 `upstream_alignment_feedback.md` 并回到 `loop_target_phase`，达到上限或 `BLOCKED` 时阻断并等待人工处理。
8. 当 state 显示 `failed` 或 `blocked` 时，输出失败原因和恢复建议。
9. 当 state 显示可继续执行时，按 `skills/superlooper/SKILL.md` 对应阶段继续，不得提示重新运行 `/spl <requirement_path>` 创建新 session。

禁止事项：

- 不自动覆盖目标项目已有差异文件。
- 不跳过 PRD、UI、执行摘要和最终 PRD 反向校对人工审核点；`strict_review` 模式下不跳过设计、初始化、模块拆分和执行清单审核点。
- 不提供 `/spl:manifest`。
