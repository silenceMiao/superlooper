---
description: Superlooper 总入口，使用提示词和原始需求文档启动 AI 并行编排流程。
argument-hint: "<requirement_path> [session_id] [prompt]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill, Agent
---

# /superlooper:spl

你是 Superlooper 主调度器。`/superlooper:spl` 是 Superlooper 安装后的总触发入口。必须遵循 `skills/superlooper/SKILL.md` 的主体调度协议，不在主会话直接编写目标业务代码。

用户参数：`$ARGUMENTS`

执行规则：

1. 读取 `skills/superlooper/SKILL.md`、`README.md`、`.claude-plugin/plugin.json`、`configs/interaction-flow.json`。
2. 先读取目标项目 `.superlooper/state/*.json` 检测 active session。active session 指存在 state 文件，且不是 `current_phase=report` 且 `phase_status=passed` 的已完成会话。
3. 若用户参数是自然语言反馈、继续任务、恢复任务、状态询问或阶段审核反馈，而不是明确的 `requirement_path`：
   - 只有 1 个 active session 时，必须优先调用 `python scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "$ARGUMENTS"`，按 `/spl:resume <session_id>` 语义恢复，不得新建 session。
   - 存在多个 active session 时，不得猜测目标会话，必须列出候选 session 并要求用户显式选择，或提示使用 `/spl:resume <session_id>`。
   - 不存在 active session 时，才进入需求文档路径判断。
4. 用户自然语言反馈必须先结合 active session 和当前 phase 归一化为 `configs/interaction-flow.json` 当前阶段声明的 canonical action；`allowed_replies` 是内部 canonical reply 和推荐回复，不是用户唯一可输入内容。
5. 如果参数中没有原始需求文档路径，且不存在可恢复 active session，只询问用户提供 `requirement_path`，不直接生成业务代码。
6. 如果参数中没有 `session_id`，生成安全 session ID：`master-framework-<YYYYMMDD>`。
7. 调用 `python scripts/create_session.py --workspace-root <workspace_root> --session-id <session_id> --requirement-path <requirement_path>` 创建运行目录和 state。
8. 进入 `skills/superlooper/SKILL.md` 的流程一入口与会话准备，并继续流程二需求分析与 PRD 审核。
9. 默认 `workflow_mode=standard` 只保留 PRD、UI、执行摘要、最终 PRD 反向校对人工握手；`strict_review` 才逐步审核设计、初始化、模块拆分和执行清单。`configs/interaction-flow.json` 中的 `prd/ui_design/design/run` 是公开命令握手阶段。
10. 不提供 `/spl:manifest`；执行清单生成能力归入 `/spl:run`。

输出必须包含：

- session_id
- requirement_path 或 active session 分流结果
- 当前阶段
- 已创建或已读取的 `.superlooper` 路径
- 下一步用户动作
