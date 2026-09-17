# Superlooper Codex 适配说明

## 用户使用入口

Codex 的安装、doctor、新建任务、恢复、升级、卸载和常见问题统一以[用户指南](USER_GUIDE.md)为准。用户在 Codex 中使用 `$superlooper...` skill，不使用 Claude Code 的 `/superlooper:spl...` 命令。

## 当前支持状态

Superlooper 已支持 Codex Agent Plugin。Codex 使用 `.codex-plugin/plugin.json` 作为插件 manifest，使用 `codex/skills/` 作为公开 skill 入口，并从同一个 `superAI-marketplace` 的 `.agents/plugins/marketplace.json` 安装。

Codex 适配层只替换入口与原生子代理调度方式。`.superlooper/` task state、Schema、Manifest、报告、合并、测试、应用和质量门禁继续复用同一套共享实现。

## 运行环境边界

Python 是 Superlooper workflow 的 `workflow runtime dependency`，不是 Codex 插件安装标准。插件安装成功不等于当前 Codex Agent 会话能执行 workflow。

Python 最低运行版本为 3.9。完整 Codex workflow 使用 non-ephemeral、`workspace-write` Codex parent session；`$superlooper-status` 与 `$superlooper-doctor` 使用 non-ephemeral、read-only parent session。`$superlooper-doctor` 和 `$superlooper` 总入口都在当前实际 parent session 中依次运行：

```bash
python --version
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
```

任一 runtime probe 失败时，Doctor 记为 `Doctor 未启动：runtime prerequisite unavailable`。总入口 preflight 失败固定报告 `当前 Agent 会话无法执行 Python；Superlooper workflow 在该环境中不可用`，并在读取 state、创建目录、恢复 task 或调用 agent 前无副作用停止。

插件不自动安装 Python，不修改 PATH、sandbox、权限或系统配置。不得通过 `danger-full-access`、全磁盘读取、全量环境变量继承或重启系统绕过前置条件。

所有 Codex skill 都从已加载 skill 文件所在目录的 `../../..` 推导 `plugin_root`，并从 `<plugin_root>/scripts/` 调用共享脚本；不得把 `scripts/` 解释为目标工作区相对路径。Codex doctor 必须以 `--workspace-root . --platform codex` 运行；该分支检查 Codex plugin、skills、dispatcher 与共享契约，不调用 `claude plugin validate`。

## Task identity

Task 是用户工作项，使用 `task_id/task_name` 标识；task state（兼容名称 session state）是 `.superlooper/state/<task_id>.json` 中的持久化 workflow 状态。Agent session / parent session 只表示实际 Codex 运行会话及其权限，不作为 Task 身份。`session_id` 仅用于 legacy compatibility。

新建语法为：

```text
$superlooper <requirement_path> [--task-name "商城后台"]
```

`task_name` 可选、可重复、允许 Unicode 与空格，只用于展示。新任务的 `task_id` 由 `create_session.py` 自动生成，格式为 `master-framework-YYYYMMDDHHMMSS`，作为路径、state、Manifest、报告、恢复和多任务消歧的唯一关联键。

多个 active task 时显示 task name（空值显示“未命名任务”）、task ID 与 phase/status。重名任务使用 task ID 选择。

## 公开 Skill 入口

| 语义入口 | Codex 调用 |
| --- | --- |
| 总入口 | `$superlooper <requirement_path> [--task-name "<task_name>"]` |
| PRD | `$superlooper-prd <requirement_path> [task_id]` |
| UI | `$superlooper-ui <task_id>` |
| 系统设计 | `$superlooper-design <task_id>` |
| 执行 | `$superlooper-run <task_id>` |
| 状态 | `$superlooper-status <task_id>` |
| 恢复 | `$superlooper-resume <task_id>` |
| 自检 | `$superlooper-doctor [task_id]` |

`$` 是 Codex skill 显式触发标记，不是 slash command。仅 `$superlooper` 总入口新增 workflow runtime preflight；`prd/ui/design/run/status/resume` 子入口不增加该步骤。

## 调度与运行时边界

Codex `$superlooper-run` 通过 `codex/dispatcher/README.md` 中的原生调度契约消费共享 `execution_manifest.json`。该 Manifest 是节点、依赖和 payload 的唯一事实源；Codex adapter 不复制业务 DAG。

父会话仅对共享 Manifest 中当前可执行的 `mod_*` 节点直接调用 Codex native `spawn_agent`。每个 eligible 节点先运行 `scripts/render_codex_spawn_prompt.py`；renderer 校验 shared Manifest、runtime Agent containment 与 frontmatter name，并输出当前 runtime Agent 全文、当前节点、当前模块、允许的设计路径和输出契约。父会话把完整 stdout 原样传给 `spawn_agent(..., fork_turns="none", message=<renderer stdout>)`，不得手工重建或补充 prompt。

每个子代理只接收当前 runtime Agent、当前节点 payload、当前模块对象和明确列出的设计上下文，不接收原始需求文档、其他模块 payload 或其他模块输出目录。renderer 不写状态、不计算第二 DAG，也不生成 `codex-dispatch.json`。

四个系统质量节点继续使用 Manifest logical agent 名称，并消费经过 Schema 与 `ContractValidator` 校验的 object payload。动态模块的 runtime logical name 固定为 `module_<module_id>`；Claude 注册入口的 frontmatter name 使用 task-scoped 名称，但该名称不写入 shared Manifest。

Codex 不执行 Claude 当前会话 Agent 类型发现检查。它不写入 `.claude/agents/generated/`，只在 `.superlooper/agents/<task_id>/` 写入动态 `module_<module_id>.md` runtime Agent，并继续通过 renderer 调度 logical name。完整 workflow 的 Codex parent 会话必须为 non-ephemeral、`workspace-write` 会话；Doctor 与 status 不适用该写权限要求。仅共享 `task_apply_to_workspace` 门禁可在所有前置质量门禁通过后写入目标项目文件。

## 初始化参数边界

Codex design adapter 必须先调用 `validate_miao_contracts.py --scope initialization-advice` 校验 `initialization-advice.md` 的第一个 YAML 参数块。参数块固定包含 `task_id`、`project_category`、`project_version`、`project_root`。

校验通过后，adapter 将三个初始化值持久化到 task state，并以 `--project-category`、`--project-version`、`--project-root` 三个独立 argv 原样传给 `initialize_project_structure.py`。缺字段、非法 category/version 组合或不安全 project root 必须停止；不得从 `project-profile.md` 或自然语言正文推断缺失值。

`strict_review` 下，设计批准进入 `initialization/waiting_review`，依次完成项目分类和版本选择；初始化成功并生成、校验 module-split 后回到 `design/waiting_review`。用户继续后才进入 `run/pending`。`standard` 仍只保留 PRD、UI、执行摘要和最终需求反向校对四个人工审核点。

## 审核、影响范围与事务边界

- 人工审核 fail-closed。`BLOCKED` execution summary 保持 `run/waiting_review + BLOCKED`，只有明确 `重试执行摘要` 可恢复；失败仍保持 BLOCKED，成功前置校验后回 `run/pending + NOT_STARTED`。
- 影响分析记录 checkpoint 不得用 `update_session.py` 写入非空 `affected_modules`。只有用户批准局部重跑后，`resume_session.py` reducer 才写入已校验报告中的授权模块范围。
- code review PASS 的 `reviewed_modules` 必须非空、无重复且完全覆盖当前 Manifest 模块集合。
- merge 在空 staging 重建快照，计算 `snapshot_digest` 并事务式发布快照与报告。apply 写入前重新校验 digest，并把 create/overwrite、工作区验证和成功报告发布纳入可回滚事务；部分回滚保留 backup 并转人工恢复。

## 功能等价验收

Superlooper 的跨平台承诺是**功能、流程、产物和质量门禁等价**。同一需求文件在 Claude Code 与 Codex 中必须满足：

- 产生符合相同契约的 task state、PRD、UI、设计、Manifest、报告和最终需求反向校对结论。
- 使用相同 Schema 与 `scripts/validate_miao_contracts.py` 验证 `execution_manifest.json`、`artifact_manifest.json` 与报告。
- `standard` 模式按相同顺序只保留 PRD、UI、执行摘要和最终需求反向校对四个人工握手；`strict_review` 额外阶段按相同状态序列执行。
- 使用相同的 merge、integration test、apply 冲突阻断和 requirement alignment 门禁。
- 使用相同的 fail-closed 审核 reducer，以及 code review PASS、测试命令证据和 PRD 稳定编号全量覆盖规则。

终端 UI、入口字符、模型措辞、token 消耗、工具输出顺序、实际并发时序和完成时间不属于跨平台一致性承诺。

Codex platform E2E 必须在满足 Python 与 Codex 运行前提的真实环境执行。缺少环境前提导致未执行时记录 `NOT_RUN_ENVIRONMENT_PREREQUISITE`，不判定源码或发布物失败，也不计为 E2E PASS。双平台兼容声明仍要求 Claude Code 与 Codex 各自存在受控环境 PASS 证据。

## 验证证据与设计背景

Codex CLI、Plugin、Marketplace、skill frontmatter 与 native `spawn_agent` 的现场验证记录位于 [Codex baseline evidence](codex-evidence/2026-08-31-codex-plugin-baseline.md)。架构边界和非目标见 [双平台兼容与 MIT 许可证设计](superpowers/specs/2026-08-31-superlooper-dual-platform-compatibility-design.md)。
