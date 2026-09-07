# Superlooper 插件开发说明

本文档用于保证在没有根目录 `CLAUDE.md` 的情况下，后续使用 Claude Code 开发 Superlooper 插件时不偏离项目目标。

## 开发定位

Superlooper 是公开发布的 Claude Code 与 Codex 双平台插件源码，不是具体业务项目。当前根目录必须保持为可通过 `claude plugin validate . --strict` 的 Claude Code plugin 根目录，并同时包含可被 Codex 读取的 `.codex-plugin/plugin.json`。

## 开发前必读文件

历史上曾使用开发辅助入口 `/superlooper:superlooper-dev <本轮开发需求>` 触发同类上下文加载；当前开发源码时不再把它视为插件安装后的公开入口。Claude Code 在本地源码目录工作时，必须先读取以下文件：

```text
README.md
.claude-plugin/plugin.json
skills/superlooper/SKILL.md
agents/developer.md
agents/requirement-verifier.md
agents/impact-analyzer.md
scripts/validate_miao_contracts.py
scripts/initialize_project_structure.py
```

历史迁移文档已移除。当前开发事实源以本文件、`README.md`、`skills/superlooper/SKILL.md`、`.claude-plugin/plugin.json` 与 `.codex-plugin/plugin.json` 为准。

## 目录边界

- Claude Code plugin manifest 固定在 `.claude-plugin/plugin.json`；Codex Agent Plugin manifest 固定在 `.codex-plugin/plugin.json`。
- Claude Code 主调度协议固定在 `skills/superlooper/SKILL.md`；不得未经明确批准改变其七流程、Slash Commands、状态机或动态 agent 注册语义。
- Codex 公开入口固定在 `codex/skills/*/SKILL.md`，native 调度边界固定在 `codex/dispatcher/README.md`。
- 插件静态 agent 固定在 `agents/`。
- 插件辅助脚本固定在 `scripts/`；共享脚本的 `--platform codex` 分支只替换平台注册物，不得分叉业务规则。
- JSON Schema 契约固定在 `schemas/`。
- 后续增强设计文档固定在 `docs/design/`；设计文档是源码开发、审计和后续扩展参考，已实施状态以文档中的“当前已实施范围”和 README/CHANGELOG/backlog 标注为准。
- 运行时产物目录为目标项目中的 `.superlooper/`，不得作为插件源码发布内容。
- Claude Code 动态 agent 注册入口为目标项目中的 `.claude/agents/generated/superlooper/<session_id>/`，不得作为插件静态源码目录。
- Codex 不创建 Claude 注册目录；其 Manifest `context.platform_registration` 固定为 `{ "platform": "codex" }`，并在目标项目的 `.superlooper/agents/<session_id>/` 生成 `module_<module_id>.md` 运行时 agent。`execution_manifest.json` 是唯一 DAG 事实源，Codex dispatcher 不得成为第二套业务协议。

## 禁止事项

- 不得把主调度协议重新放回根目录 `CLAUDE.md`。
- 不得把静态 agent 放回 `.claude/agents/`。
- 不得把运行时 `.superlooper/` 内容提交为插件源码。
- 不得把本机私有配置、令牌、密钥、内网地址写入插件文件。
- 不得修改七流程主体调度语义，除非用户明确批准；不得减少、删除或改变 `skills/superlooper/SKILL.md` 中的步骤、握手、校验或门禁。
- v3 流程减重已由用户明确批准：默认 `standard` 模式保留 PRD、UI、执行摘要和最终 PRD 反向校对四个人工握手；后续禁止的是未获授权继续减少硬门禁或绕过 validator、apply 冲突阻断、最终 PRD 反向校对。
- 流程二可增加 analyst 输出状态的补充分支，但不得改为新的主流程，不得跳过人工审核。

`configs/interaction-flow.json` 中的 `prd/ui_design/design/run` 是公开命令握手阶段，不等同于七流程文档章节数量。

- 不得新增独立入口规则事实源；触发规则以 `skills/superlooper/SKILL.md` 和 `/spl` 系列 command 文件为准。
- `configs/interaction-flow.json` 只声明公开命令握手状态，不承担触发判断。

## 修改联动检查

| 修改对象 | 必须同时检查 |
| --- | --- |
| `skills/superlooper/SKILL.md` | `README.md`、`agents/analyst.md`、`agents/architect.md`、`docs/agent-flows/analyst-flow.md`、`docs/agent-flows/architect-flow.md`、`schemas/`、`scripts/validate_miao_contracts.py` |
| 入口触发规则 | `skills/superlooper/SKILL.md`、`README.md`、`commands/`、`configs/interaction-flow.json`、`docs/superpowers/specs/` |
| `agents/analyst.md` | `docs/agent-flows/analyst-flow.md`、`skills/superlooper/SKILL.md`、`README.md` |
| `agents/architect.md` | `docs/agent-flows/architect-flow.md`、`skills/superlooper/SKILL.md`、`README.md`、`schemas/module-split.schema.json`、`scripts/validate_miao_contracts.py` |
| `docs/agent-flows/architect-flow.md` | `agents/architect.md`、`skills/superlooper/SKILL.md`、`schemas/module-split.schema.json` |
| `agents/*.md` | `README.md`、`skills/superlooper/SKILL.md`、Manifest 中的 agent 字段 |
| `.codex-plugin/plugin.json` | `.claude-plugin/plugin.json`、`README.md`、`docs/CODEX.md`、`scripts/doctor.py`、install package tests |
| `codex/skills/*/SKILL.md` | `README.md`、`docs/CODEX.md`、共享 scripts、`tests/test_codex_skills.py` |
| `codex/dispatcher/README.md` | `scripts/generate_execution_manifest.py`、`scripts/generate_runtime_agents.py`、`scripts/validate_miao_contracts.py`、`docs/CODEX.md`、`tests/test_codex_registration.py` |
| `agents/developer.md` | `skills/superlooper/SKILL.md`、`README.md`、`scripts/validate_miao_contracts.py`、动态 `module_*` 生成规则 |
| 动态 `module_*` agent 生成规则 | `scripts/generate_runtime_agents.py`、`scripts/generate_execution_manifest.py`、`scripts/validate_miao_contracts.py`、`agents/developer.md`、`README.md`、`skills/superlooper/SKILL.md`、`tests/test_generate_runtime_agents.py`、`tests/test_validate_contracts.py` |
| `scripts/run_execution_dag.py` | `schemas/execution-manifest.schema.json`、`scripts/validate_miao_contracts.py`、`scripts/update_session.py`、`README.md`、`tests/test_run_execution_dag.py`、`tests/test_validate_contracts.py` |
| UI traceability 契约 | `agents/architect.md`、`docs/agent-flows/architect-flow.md`、`agents/developer.md`、`agents/tester.md`、`agents/requirement-verifier.md`、`schemas/module-split.schema.json`、`scripts/generate_execution_manifest.py`、`scripts/generate_runtime_agents.py`、`scripts/validate_miao_contracts.py`、`README.md`、`tests/test_generate_execution_manifest.py`、`tests/test_generate_runtime_agents.py`、`tests/test_validate_contracts.py` |
| `brownfield-selective` 契约 | `schemas/session-state.schema.json`、`scripts/create_session.py`、`scripts/update_session.py`、`schemas/module-split.schema.json`、`scripts/generate_execution_manifest.py`、`scripts/generate_runtime_agents.py`、`scripts/validate_miao_contracts.py`、`agents/architect.md`、`agents/developer.md`、`agents/workspace_applier.md`、`README.md`、`tests/test_session_state.py`、`tests/test_generate_execution_manifest.py`、`tests/test_generate_runtime_agents.py`、`tests/test_validate_contracts.py`、`tests/test_apply_to_workspace.py` |
| `scripts/validate_miao_contracts.py` | `README.md` 常用命令、`schemas/` |
| 项目初始化门禁 | `skills/superlooper/SKILL.md`、`commands/spl/design.md`、`commands/spl/run.md`、`schemas/session-state.schema.json`、`scripts/initialize_project_structure.py`、`scripts/generate_execution_manifest.py`、`tests/test_initialize_project_structure.py`、`tests/test_generate_execution_manifest.py` |
| PRD 反向需求校对 | `skills/superlooper/SKILL.md`、`commands/spl/run.md`、`agents/requirement-verifier.md`、`scripts/build_session_report.py`、`scripts/validate_miao_contracts.py`、`tests/test_requirement_alignment_report.py`、`tests/test_build_session_report.py` |
| PRD 回退协议 | `skills/superlooper/SKILL.md`、`commands/spl/prd.md`、`agents/analyst.md`、`configs/interaction-flow.json`、`schemas/session-state.schema.json`、`scripts/update_session.py`、`tests/test_session_state.py` |
| UI 设计流程 | `skills/superlooper/SKILL.md`、`commands/spl/ui.md`、`agents/ui-architect.md`、`docs/agent-flows/ui-architect-flow.md`、`agents/architect.md`、`docs/agent-flows/architect-flow.md`、`configs/interaction-flow.json`、`schemas/session-state.schema.json`、`scripts/validate_miao_contracts.py`、`tests/test_session_state.py`、`tests/test_validate_contracts.py` |
| 设计回退协议 | `skills/superlooper/SKILL.md`、`commands/spl/design.md`、`agents/architect.md`、`configs/interaction-flow.json`、`schemas/session-state.schema.json`、`scripts/update_session.py`、`tests/test_session_state.py` |
| 深层变更影响分析 | `skills/superlooper/SKILL.md`、`commands/spl/run.md`、`agents/impact-analyzer.md`、`scripts/validate_miao_contracts.py`、`scripts/update_session.py`、`scripts/resume_session.py`、`tests/test_validate_contracts.py` |
| 运行阶段返工协议 | `skills/superlooper/SKILL.md`、`commands/spl/run.md`、`configs/interaction-flow.json`、`scripts/normalize_user_intent.py`、`scripts/resume_session.py`、`scripts/validate_miao_contracts.py`、`tests/test_session_state.py`、`tests/test_interaction_flow.py`、`README.md` |
| 自然语言归一化与 active session 恢复 | `skills/superlooper/SKILL.md`、`commands/spl.md`、`commands/spl/resume.md`、`configs/interaction-flow.json`、`schemas/session-state.schema.json`、`scripts/normalize_user_intent.py`、`scripts/resume_session.py`、`scripts/update_session.py`、`tests/test_session_state.py`、`README.md` |
| `schemas/*.schema.json` | `scripts/validate_miao_contracts.py`、`agents/developer.md` |
| `scripts/merge_artifacts.py` | `agents/system_merger.md`、`README.md` |
| `scripts/apply_to_workspace.py` | `agents/workspace_applier.md`、`README.md`、`skills/superlooper/SKILL.md`、`scripts/validate_miao_contracts.py`、`scripts/build_session_report.py`、`tests/test_apply_to_workspace.py`、`tests/test_validate_contracts.py`、`tests/test_build_session_report.py` |
| `scripts/build_session_report.py` | `README.md`、`skills/superlooper/SKILL.md`、`scripts/validate_miao_contracts.py`、`tests/test_build_session_report.py` |
| 发布清单、归档或 Marketplace 脚本 | `README.md`、`docs/RELEASE.md`、`.claude-plugin/marketplace.json`、`.agents/plugins/marketplace.json`、`tests/test_package_plugin.py`、`tests/test_package_marketplace.py`、`tests/test_codex_marketplace.py`、安装态 smoke test |

## 验收命令

每次修改后至少执行：

```bash
claude plugin validate . --strict
python -m py_compile scripts/schema_validation.py scripts/validate_miao_contracts.py scripts/merge_artifacts.py scripts/apply_to_workspace.py scripts/initialize_project_structure.py scripts/generate_execution_manifest.py scripts/generate_runtime_agents.py scripts/build_execution_summary.py scripts/build_session_report.py scripts/doctor.py scripts/create_session.py scripts/update_session.py scripts/resume_session.py scripts/status_session.py scripts/normalize_user_intent.py scripts/package_plugin.py scripts/verify_release_consistency.py scripts/build_release_archive.py scripts/run_execution_dag.py
python -m unittest tests.test_interaction_flow tests.test_create_session tests.test_session_state tests.test_initialize_project_structure tests.test_generate_execution_manifest tests.test_requirement_alignment_report tests.test_build_session_report tests.test_validate_contracts tests.test_doctor tests.test_codex_skills tests.test_codex_registration tests.test_codex_marketplace tests.test_verify_release_consistency
```

如果执行 Python 编译后生成 `scripts/__pycache__/`，该目录属于临时缓存，不进入发布源码。

## 开发方式建议

当前未安装插件、只在本机开发源码时，使用本地私有上下文文件：

```text
.claude/CLAUDE.md
```

该文件会在当前源码目录的新 Claude Code 会话中自动加载，并固化必读文件、目录边界、禁止事项和验收命令。每轮任务只需要直接输入本轮需求，不再需要手动输入“请先读取 README.md、docs/DEVELOPMENT.md、skills/superlooper/SKILL.md，再执行本轮修改。”。

示例：

```text
检查 README 是否还有旧目录描述
```

插件安装后的公开运行入口统一为 `/spl` 系列命令；`/superlooper:superlooper-dev` 只作为历史开发辅助入口留档，不作为当前插件安装后的快捷入口。

`.claude/CLAUDE.md` 已通过 `.gitignore` 排除，只用于本机开发源码时自动加载上下文，不属于插件发布源码。

如果执行 `/init` 导致根目录重新生成 `CLAUDE.md`，必须在提交或发布前确认它是否影响 `claude plugin validate . --strict`。

## 源码、Marketplace 与 GitHub 一致性

`D:\www_21\my-claude\superlooper` 是插件源码、版本、install 文件闭包与用户文档的唯一事实源。`D:\www_21\my-claude\superAI-marketplace` 是独立 Git 发布镜像，不是第二套插件源码。

- `plugins/superlooper/` 必须由 `PluginPackager(mode="install")` 的 `release_files` 生成，不得手工修改。
- Marketplace 同步仅接管 `README.md`、`.claude-plugin/marketplace.json`、`.agents/plugins/marketplace.json`、`plugins/superlooper/**` 与 `.superlooper-marketplace-sync.json`。
- 同步账本记录所有受控文件的 SHA-256。账本漂移、受控文件被人工修改、受控区域未知文件或目录、任一受控符号链接均必须阻断同步。
- 同步不得改写 `.git/`、远程配置、提交历史、其他插件或账本外文件。已有未登记镜像只能经显式 `--adopt-existing` 接管。
- `docs/USER_GUIDE.md` 是唯一用户文案事实源；`README.md` 与 Marketplace 根 README 必须由 `scripts/render_user_readme.py` 生成。修改用户文案时，同时检查用户指南、渲染器、install closure、Marketplace 同步器和一致性验证器。
- 双仓库无法原子推送。只有源码与 Marketplace 两个远程分支 HEAD 分别等于已验证本地 HEAD，且账本 `source_commit` 等于源码 HEAD 时，才能宣布版本已发布完成。
- Git 提交、推送、remote 修改、仓库初始化和远程创建必须取得当轮明确授权。同步器与验证器不得执行这些操作。
- 当前源码目录不是 Git 工作树。`verify_release_consistency.py --require-pushed` 必须报告阻断，不得执行 `git init` 或添加 remote。

## 发布联动检查

| 修改对象 | 必须同时检查 |
| --- | --- |
| `docs/USER_GUIDE.md` | `README.md`、`scripts/render_user_readme.py`、install manifest、Marketplace README 与对应测试 |
| `scripts/render_user_readme.py` | `scripts/package_plugin.py`、`scripts/package_marketplace.py`、`scripts/verify_release_consistency.py`、`tests/test_render_user_readme.py` |
| `scripts/package_marketplace.py` | install manifest、双平台 Marketplace metadata、同步账本、`tests/test_package_marketplace.py`、`docs/RELEASE.md` |
| `scripts/verify_release_consistency.py` | 双 manifest、同步账本、README 渲染器、`tests/test_verify_release_consistency.py`、`docs/RELEASE.md` |

## 发布架构边界

Claude Code Marketplace 根 metadata 固定为 `.claude-plugin/marketplace.json`，Codex Marketplace 根 metadata 固定为 `.agents/plugins/marketplace.json`。二者都通过 `source: "./plugins/superlooper"` 指向同一个插件树；插件树内仍保留 `.claude-plugin/plugin.json` 与 `.codex-plugin/plugin.json`。

install artifact 只包含运行闭包和用户指南，不包含开发说明、发布指南、设计文档、测试、`.superlooper/`、本机 `.claude/`、缓存、`.env*` 或私有配置。完整七流程、静态 agent、动态 agent、Schema、merge 与 apply 约束继续以 `skills/superlooper/SKILL.md`、`agents/`、`schemas/` 与对应脚本为准。
