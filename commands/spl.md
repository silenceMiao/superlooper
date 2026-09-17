---
description: Superlooper 总入口，使用提示词和原始需求文档启动 AI 并行编排流程。
argument-hint: '<requirement_path> [--task-name "<task_name>"]'
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill, Agent
---

# /superlooper:spl

你是 Superlooper 主调度器。`/superlooper:spl` 是 Superlooper 安装后的总触发入口。必须遵循 `skills/superlooper/SKILL.md` 的主体调度协议，不在主会话直接编写目标业务代码。

用户参数：`$ARGUMENTS`

执行规则：

1. 在当前实际 Agent 会话执行 `python --version`，随后执行 `python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"` 断言 Python 3.9+。只有两条命令都成功后，才允许执行以下任何业务动作。
   - 任一命令失败时，固定报告：`当前 Agent 会话无法执行 Python；Superlooper workflow 在该环境中不可用`，并说明安装本身不等于运行依赖满足，最低运行版本为 Python 3.9。
   - 失败后立即停止：不创建 `.superlooper/`、不读取 task state、不恢复或推进 task、不调用 agent、不修改目标项目、不自动安装 Python、不修改 PATH 或 sandbox。
2. 从插件安装根读取 `${CLAUDE_PLUGIN_ROOT}/skills/superlooper/SKILL.md`、`${CLAUDE_PLUGIN_ROOT}/README.md`、`${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`、`${CLAUDE_PLUGIN_ROOT}/configs/interaction-flow.json`；不得把这些插件文件解释为目标工作区相对路径。
3. 调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/status_session.py" --workspace-root <workspace_root> --list-active` 读取目标项目 `.superlooper/state/*.json` 并检测 active task。active task 指存在有效 state 文件，且不是 `current_phase=report` 且 `phase_status=passed` 的已完成任务；该模式忽略 identity 环境变量，任一 state 无效时阻断并报告错误。
4. 无论用户参数是否看起来像 `requirement_path`，都必须先按 active task 数量分流：
   - 只有 1 个 active task 时，必须先调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/normalize_user_intent.py" --workspace-root <workspace_root> --task-id <task_id> --user-input "$ARGUMENTS"`，再调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/resume_session.py" --workspace-root <workspace_root> --task-id <task_id> --user-input "$ARGUMENTS"`，按 `/spl:resume <task_id>` 语义恢复，不得新建 task。
   - 存在多个 active task 时，不得猜测目标任务，必须列出每个候选 task 的 `task_name`（为空时显示“未命名任务”）、`task_id`、当前 phase/status，并要求用户使用 `task_id` 显式选择，或提示使用 `/superlooper:spl:resume <task_id>`；不得新建 task。
   - 不存在 active task 时，才进入需求文档路径判断和新 task 创建。
5. 用户自然语言反馈必须先结合 active task 和当前 phase 归一化为 `${CLAUDE_PLUGIN_ROOT}/configs/interaction-flow.json` 当前阶段声明的 canonical action；`allowed_replies` 是内部 canonical reply 和推荐回复，不是用户唯一可输入内容。
6. 如果参数中没有原始需求文档路径，且不存在可恢复 active task，只询问用户提供 `requirement_path`，不直接生成业务代码。
7. 仅在 active task 数量为零时允许新建 task。入口不得生成或接受用户提供的 `task_id`。调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/create_session.py" --workspace-root <workspace_root> --new-task --requirement-path <requirement_path>`；如果用户提供 `--task-name "<task_name>"`，将 `<requirement_path>` 和 `<task_name>` 分别按当前 shell 的安全引用规则作为单个 argv 数据传递。每个用户值都作为单个 argv 数据传递，不得拼接为 shell 源码。读取脚本输出的系统生成 `task_id`，并将其作为后续 state、路径和 agent payload 的唯一关联键。
8. 新 task 创建后必须复用 `/spl:prd` 的 canonical checkpoint 链，不得直接跳到 analyst：
   - 先调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/update_session.py" --workspace-root <workspace_root> --task-id <task_id> --current-phase prd --phase-status running --last-command "/spl <requirement_path>" --next-action "等待需求分析阶段输出完成"`。
   - 再调用 `superlooper:analyst`，payload 包含 `task_id`、`requirement_path`、`output_prd_path=.superlooper/context/<task_id>/prd.md`。
   - 校验 analyst 状态块和 PRD 产物合同；blocked 或 malformed/validation failure 分别写入带完整 `--last-command` 的 `prd/blocked` 或 `prd/failed` checkpoint 后停止。
   - 只有合法 PRD 才调用 `python "${CLAUDE_PLUGIN_ROOT}/scripts/update_session.py" --workspace-root <workspace_root> --task-id <task_id> --current-phase prd --phase-status waiting_review --last-command "/spl <requirement_path>" --generated-file .superlooper/context/<task_id>/prd.md --next-action "审核 PRD；通过后进入 UI 设计"`，然后停止于既有 PRD 人工审核点。
9. 默认 `workflow_mode=standard` 只保留 PRD、UI、执行摘要、最终 PRD 反向校对人工握手；`strict_review` 才逐步审核设计、初始化、模块拆分和执行清单。`configs/interaction-flow.json` 中的 `prd/ui_design/design/run` 是公开命令握手阶段。
10. 不提供 `/spl:manifest`；执行清单生成能力归入 `/spl:run`。

输出必须包含：

- task_id
- task_name（未提供时为 null）
- requirement_path 或 active task 分流结果
- 当前阶段
- 已创建或已读取的 `.superlooper` 路径
- 下一步用户动作
