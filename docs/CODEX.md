# Superlooper Codex 适配说明

## 用户使用入口

Codex 的安装、doctor、首次会话、恢复、升级、卸载和常见问题统一以[用户指南](USER_GUIDE.md)为准。用户在 Codex 中使用 `$superlooper...` skill，不使用 Claude Code 的 `/superlooper:spl...` 命令。

## 当前支持状态

Superlooper 已支持 Codex Agent Plugin。Codex 使用 `.codex-plugin/plugin.json` 作为插件 manifest，使用 `codex/skills/` 作为公开 skill 入口，并从同一个 `superAI-marketplace` 的 `.agents/plugins/marketplace.json` 安装。

Codex 适配层只替换入口与原生子代理调度方式。`.superlooper/` session state、Schema、Manifest、报告、合并、测试、应用和质量门禁继续复用同一套共享实现。

## 运行环境边界

完整 Codex workflow 使用 non-ephemeral、`workspace-write` Codex parent session。`$superlooper-doctor` 会运行共享 Python 脚本，当前 Codex parent session 必须能解析并执行可用 Python runtime。宿主 shell 能执行 Python 不足以证明该前置条件已满足；必须在将运行 doctor 的同一个当前 Codex parent session 中先成功执行 `python --version`。

所有 Codex skill 都从已加载 skill 文件所在目录的 `../../..` 推导 `plugin_root`，并从 `<plugin_root>/scripts/` 调用共享脚本；不得把 `scripts/` 解释为目标工作区相对路径。Codex doctor 必须以 `--workspace-root . --platform codex` 运行；该分支检查 Codex plugin、skills、dispatcher 与共享契约，不调用 `claude plugin validate`。

如果当前 Codex parent session 无法执行 Python，不要通过 `danger-full-access`、全磁盘读取或全量环境变量继承绕过该前置条件，也不要通过重启系统尝试修复。安装 system-wide Python 或修改 Codex sandbox 配置属于系统级变更，必须先获得明确授权。

## 公开 Skill 入口

| 语义入口 | Codex 调用 |
| --- | --- |
| 总入口 | `$superlooper <requirement_path> [session_id]` |
| PRD | `$superlooper-prd <requirement_path> [session_id]` |
| UI | `$superlooper-ui <session_id>` |
| 系统设计 | `$superlooper-design <session_id>` |
| 执行 | `$superlooper-run <session_id>` |
| 状态 | `$superlooper-status <session_id>` |
| 恢复 | `$superlooper-resume <session_id>` |
| 自检 | `$superlooper-doctor [session_id]` |

`$` 是 Codex skill 显式触发标记，不是 slash command。

## 调度与运行时边界

Codex `$superlooper-run` 通过 `codex/dispatcher/README.md` 中的原生调度契约消费共享 `execution_manifest.json`。该 Manifest 是节点、依赖和 payload 的唯一事实源；Codex adapter 不复制业务 DAG。

父会话仅对共享 Manifest 中当前可执行的 `mod_*` 节点直接调用 Codex native `spawn_agent`。每个子代理只接收当前节点 payload、当前模块对象和明确列出的设计上下文，不接收原始需求文档、其他模块 payload 或其他模块输出目录。

Codex parent 会话必须为 non-ephemeral、`workspace-write` 会话。Codex adapter 不写入 `.claude/agents/generated/`，只在 `.superlooper/agents/<session_id>/` 写入动态 `module_<module_id>.md` 运行时 agent。仅共享 `task_apply_to_workspace` 门禁可在所有前置质量门禁通过后写入目标项目文件。

## 功能等价验收

Superlooper 的跨平台承诺是**功能、流程、产物和质量门禁等价**。同一需求文件在 Claude Code 与 Codex 中必须满足：

- 产生符合相同契约的 session state、PRD、UI、设计、Manifest、报告和最终需求反向校对结论。
- 使用相同 Schema 与 `scripts/validate_miao_contracts.py` 验证 `execution_manifest.json`、`artifact_manifest.json` 与报告。
- 按相同顺序保留 PRD、UI、执行摘要和最终需求反向校对四个人工握手。
- 使用相同的 merge、integration test、apply 冲突阻断和 requirement alignment 门禁。

终端 UI、入口字符、模型措辞、token 消耗、工具输出顺序、实际并发时序和完成时间不属于跨平台一致性承诺。

## 验证证据与设计背景

Codex CLI、Plugin、Marketplace、skill frontmatter 与 native `spawn_agent` 的现场验证记录位于 [Codex baseline evidence](codex-evidence/2026-08-31-codex-plugin-baseline.md)。架构边界和非目标见 [双平台兼容与 MIT 许可证设计](superpowers/specs/2026-08-31-superlooper-dual-platform-compatibility-design.md)。
