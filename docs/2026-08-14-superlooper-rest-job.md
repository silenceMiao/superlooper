# Superlooper 遗留问题待执行优先级任务清单

## 分析边界

本文基于 2026-08-14 遗留问题复核结果和后续 P0/P1 实施结果整理，目标是把 Superlooper 剩余工作收口为可执行、可审批、可验收的 backlog。

本清单只覆盖 Superlooper 距离“普通用户可安装、可恢复、可闭环交付真实项目”的关键遗留任务。

本次不纳入以下方向：

- 统计。
- 监控。
- observability。
- monitors。

## 五步追问法结论

### 1. 目标是什么

目标是持续收口 Superlooper 已识别遗留问题，把已完成项从待办中移出，把仍需修改的发布产物、后续高风险能力和审批边界拆清楚。

### 2. 当前完成了什么

P0 低风险高收益闭环修复已完成。P1 中失败返工协议、动态 `module_*` agent 约束、用户安装文档、发布门禁测试和 CHANGELOG 版本叙述已完成并通过验收。install artifact smoke test 已完成，但真实 Claude Code 安装态 E2E 仍是发布前必须记录项。

### 3. 剩余瓶颈在哪里

当前剩余瓶颈分为两类：

- 发布产物重建：`dist/` 下 release manifest 和 source/install zip 需要按最新 P2 源码能力重建。
- 已落地的高风险能力扩展：DAG state runner、script 状态推进统一、UI 实现契约和 brownfield-selective 已从设计文档转为最小源码能力、schema、validator、agent 契约和测试；完整 executor 扩展边界保留在设计文档。

### 4. 排除什么

已完成的 P0/P1 源码、协议、测试和文档修改不再作为待执行任务保留。`dist/` 清理、覆盖和重建属于有副作用操作，未获用户明确审批前不得执行。

### 5. 最终判断

当前必须马上收口的是发布产物和设计文档口径的事实源更新。P2 四项已按独立设计和用户确认进入最小源码实现，剩余工作是记录已实施范围、未实施扩展边界、source/install artifact 验收结果。

## 总体执行原则

- 已完成任务不重复修改，只保留验收证据和状态。
- `dist/` 不作为长期事实源；发布前必须按当前源码重建 manifest 和 zip。
- 涉及删除、覆盖、重建发布产物的操作必须先获得用户审批。
- 涉及 `skills/superlooper/SKILL.md` 主体调度协议的任务必须先写设计并获得确认。
- 涉及 `schemas/`、validator、agent 输出契约、Manifest、apply 或 merge 策略的任务必须同步检查 README、SKILL、agent、脚本和测试。

## 当前必须修改清单

当前 P0/P1 必须修改项已收口完成。`dist/` 发布产物已在获得用户批准后重建，当前不再存在 P1 层面的必须修改文件。

| 优先级 | 状态 | 工作项 | 已修改或生成的文件 | 验收结果 |
| --- | --- | --- | --- | --- |
| P1 | 已完成 | 重建 release manifest | `dist/superlooper-release-manifest.json` | manifest 基于最新源码生成，最终模式为 `install`。 |
| P1 | 已完成 | 重建 source zip | `dist/superlooper-1.0.0-source.zip` | source archive 已重新输出。 |
| P1 | 已完成 | 重建 install zip | `dist/superlooper-1.0.0-install.zip` | install archive 已重新输出，install smoke test 已通过。 |

## P0 第一批：低风险高收益闭环修复

| 序号 | 任务 | 当前状态 | 完成内容 | 验收结果 |
| --- | --- | --- | --- | --- |
| 1 | 修复发布清单与源码协议漂移 | 已完成 | 发布清单必需文件门禁和发布测试已补齐。 | 相关测试和 `claude plugin validate . --strict` 已通过。 |
| 2 | 补安装产物级 smoke test | 已完成 | `InstallArtifactSmokeTest` 已覆盖 install zip 解包与 `python bin/spl doctor`，不等于真实 Claude Code 安装态 E2E。 | `tests.test_package_plugin` 已通过。 |
| 3 | 为 `continue_current_flow` 补真实状态推进 | 已完成 | `resume_session.py` 已在合法状态下处理继续语义。 | session 和 interaction flow 相关测试已通过。 |
| 4 | 在 `generate_execution_manifest.py` 增加 UI 与设计前置门禁 | 已完成 | Manifest 生成前已校验 UI、设计、初始化和 state 前置条件。 | execution manifest 相关测试已通过。 |
| 5 | 补 apply 后真实工作区验证 | 已完成 | `apply_report.json` 已记录 `workspace_validation`，最终报告消费验证结果。 | apply、contract 和 session report 相关测试已通过。 |

## P1 第二批：协议与状态闭环能力

| 序号 | 任务 | 当前状态 | 完成内容 | 验收结果 |
| --- | --- | --- | --- | --- |
| 6 | 补 code review / test / apply / requirement alignment 失败后的返工协议 | 已完成 | 失败路径已有 canonical action、状态推进、反馈报告和局部返工边界。 | 相关回归测试已通过。 |
| 7 | 强化动态 `module_*` agent，把模块约束写入生成文件 | 已完成 | 动态 agent 运行时源文件和注册入口已写入 `Runtime Module Constraints`。 | 生成、validator 和 apply fixture 测试已通过。 |
| 8 | 补用户安装、升级、卸载、首次 Quick Start 文档 | 已完成 | README 已覆盖 install artifact、首次 `/spl`、升级、卸载、恢复、自检和常见失败处理。 | 文档已同步，发布测试已通过。 |
| 9 | 把 `dist/` 纳入仓库卫生处理并重建发布产物 | 已完成 | `.gitignore` 已排除 `dist/`，发布文档已说明产物边界；发布 manifest、source zip 和 install zip 已重建。 | release archive 命令和 install smoke test 已通过。 |
| 10 | 收口 CHANGELOG 与版本叙述 | 已完成 | `CHANGELOG.md` 已保持 `1.0.0` 并扩展为当前首个可发布能力说明。 | 版本与 CHANGELOG 一致性测试已通过。 |

## P1 剩余任务执行结果

### 发布产物重建

已在获得用户批准后执行发布产物重建。实际执行命令：

```bash
python scripts/package_plugin.py --mode source
python scripts/package_plugin.py --mode install
python scripts/build_release_archive.py --mode source
python scripts/build_release_archive.py --mode install
python -m unittest tests.test_package_plugin.InstallArtifactSmokeTest
```

已覆盖或生成的文件：

```text
dist/superlooper-release-manifest.json
dist/superlooper-1.0.0-source.zip
dist/superlooper-1.0.0-install.zip
```

最终补充执行：

```bash
python -m py_compile scripts/validate_miao_contracts.py scripts/merge_artifacts.py scripts/apply_to_workspace.py scripts/initialize_project_structure.py scripts/generate_execution_manifest.py scripts/generate_runtime_agents.py scripts/build_execution_summary.py scripts/build_session_report.py scripts/doctor.py scripts/create_session.py scripts/update_session.py scripts/resume_session.py scripts/status_session.py scripts/normalize_user_intent.py scripts/package_plugin.py scripts/build_release_archive.py
claude plugin validate . --strict
```

## P2 第三批：高收益高风险能力扩展

### 11. 设计并实现消费 `execution_manifest.json` 的 DAG state runner

| 项目 | 内容 |
| --- | --- |
| 当前状态 | 已实施最小源码能力。 |
| 设计文档 | `docs/design/dag-executor-design.md`。 |
| 实施结果 | 已新增 `scripts/run_execution_dag.py`，读取 `execution_manifest.json`、计算 DAG 依赖顺序并写入 `.superlooper/state/<session_id>.dag.json`。 |
| 修改收益 | Superlooper 从“生成执行计划”升级为“可记录 DAG 执行状态”。 |
| 修改风险 | 已控制。未改变执行摘要、代码审查、合并、测试、apply 或需求反向校对门禁。 |
| 验收证据 | `tests.test_run_execution_dag` 与 `dag-state` validator 已覆盖。 |
| 已实施验收标准 | DAG state runner 读取 DAG、校验缺失依赖和循环依赖、记录状态、写入 script event。 |
| 未实施扩展 | 真实 subagent 调度、节点级 artifact 校验、内置执行摘要门禁、`blocked` 状态和失败恢复幂等。 |

### 12. 把 script 级状态推进与 command 级状态推进统一

| 项目 | 内容 |
| --- | --- |
| 当前状态 | 已实施最小源码能力。 |
| 设计文档 | `docs/design/script-state-unification-design.md`。 |
| 实施结果 | `scripts/update_session.py` 已作为脚本事件统一写入入口，session state 增加 `script_events`。 |
| 修改收益 | 已接入脚本可在 state 中留下可审计事件。 |
| 修改风险 | 已控制。脚本事件通过 `idempotency_key` 保持幂等。 |
| 验收证据 | `tests.test_session_state` 已覆盖脚本事件写入和幂等。 |
| 已实施验收标准 | 关键脚本可通过统一入口写入 `started`、`completed`、`failed` 事件；重复执行保持幂等。 |
| 未实施扩展 | 统一 wrapper、generated files 自动汇总、reports 自动汇总、last_error 自动采集和 report/gate 细粒度事件。 |

### 13. 补 UI 设计到真实实现的一等契约

| 项目 | 内容 |
| --- | --- |
| 当前状态 | 已实施最小源码能力。 |
| 设计文档 | `docs/design/ui-implementation-contract-design.md`。 |
| 实施结果 | `ui_refs`、`interaction_refs`、`component_refs`、`ui_acceptance_refs` 已进入 module-split、Manifest payload、动态 agent constraints、validator、报告正文轻量审计和 agent 契约。 |
| 修改收益 | UI 审核通过后，页面、交互、组件和状态能被模块实现、测试和最终校对追溯。 |
| 修改风险 | 已控制。字段和轻量审计只作为追溯契约，不替代 UI 审核或测试门禁。 |
| 验收证据 | Manifest 生成、runtime agent 生成、报告正文审计和契约校验测试已覆盖。 |
| 已实施验收标准 | Manifest 或模块 payload 包含 UI 页面、交互、组件和验收关注点；tester 与 requirement verifier 契约要求校验 UI 相关验收项；validator 轻量检查报告正文中的 UI 验收编号证据。 |
| 未实施扩展 | 完整 Markdown AST 表格解析、跨报告证据链结构化比对和 UI 验收证据自动生成。 |

### 14. 补 brownfield-selective 能力

| 项目 | 内容 |
| --- | --- |
| 当前状态 | 已实施最小源码能力。 |
| 设计文档 | `docs/design/brownfield-selective-design.md`。 |
| 实施结果 | `brownfield-selective` 已进入 session project mode、module-split、Manifest payload、动态 agent constraints、validator 和 apply 阻断回归测试。 |
| 修改收益 | 支持存量项目安全改造，减少误读架构和覆盖用户文件风险。 |
| 修改风险 | 已控制。apply 默认阻断不变，`allowed_existing_files` 不自动授权覆盖。 |
| 验收证据 | session、Manifest、runtime agent、validator 和 apply 回归测试已覆盖。 |
| 已实施验收标准 | 模块级允许既有文件、禁止文件、集成点、测试命令和覆盖策略可追溯；默认不覆盖策略保持不变。 |
| 未实施扩展 | project profile 级 `allowed_modify_paths`、`forbidden_modify_paths`、`dependency_policy`、按 `project_mode` 条件强制模块字段必填和自动只读扫描。 |

## P3 第四批：降噪和后续归档

### 15. 复核并处理 UI 历史子 agent

| 项目 | 内容 |
| --- | --- |
| 当前状态 | 已完成。 |
| 遗留判断 | 已关闭。用户已删除 `agents/ui/` 历史子 agent 目录，当前静态 UI 入口保留为 `agents/ui-architect.md`。 |
| 已处理文件 | `agents/ui/ui-need-analyst.md`、`agents/ui/ui-form-analyst.md`、`agents/ui/ui-interaction-analyst.md`、`agents/ui/ui-content-analyst.md`、`agents/ui/ui-research-analyst.md`、`agents/ui/ui-visual-analyst.md`、`agents/ui/ui-ia-analyst.md` 已不在当前源码树。 |
| 修改收益 | 删除历史子 agent 后，UI 阶段不再被误判为多 agent 调度，install artifact 不再携带未声明用途的历史 agent。 |
| 修改风险 | 低。主协议、README、RELEASE 和发布门禁均只要求 `agents/ui-architect.md`，不要求 `agents/ui/*.md`。 |
| 验收标准 | `claude plugin validate . --strict` 通过；release manifest 不再包含 `agents/ui/*.md`；README、SKILL 和 RELEASE 对静态 agent 目录描述一致。 |

## 推荐待执行顺序

### 当前收尾轮

当前收尾轮已完成：

1. 已获得用户对 `dist/` 覆盖和发布产物重建的明确审批。
2. 已重建 source/install manifest 和 zip。
3. 已运行 install artifact smoke test，该项不等于真实 Claude Code 安装态 E2E。
4. 已记录最终发布产物验收结论。
5. 发布前必须记录真实 Claude Code 安装态 E2E，覆盖真实插件安装、`/spl` 命令可见、`/spl:doctor` 和首次 `/spl requirements.md <session_id>` 到 PRD 审核握手点。

### 下一轮设计任务

下一轮设计任务已完成：

1. DAG state runner 设计：`docs/design/dag-executor-design.md`。
2. script 状态推进统一设计：`docs/design/script-state-unification-design.md`。
3. UI 实现契约设计：`docs/design/ui-implementation-contract-design.md`。
4. brownfield-selective 设计：`docs/design/brownfield-selective-design.md`。
5. UI 历史子 agent 已由用户删除，发布产物已验证不再携带 `agents/ui/*.md`。

## 必跑验收命令

修改源码、协议、schema 或测试后，至少执行：

```bash
claude plugin validate . --strict
python -m py_compile scripts/validate_miao_contracts.py scripts/merge_artifacts.py scripts/apply_to_workspace.py scripts/initialize_project_structure.py scripts/generate_execution_manifest.py scripts/generate_runtime_agents.py scripts/build_execution_summary.py scripts/build_session_report.py scripts/doctor.py scripts/create_session.py scripts/update_session.py scripts/resume_session.py scripts/status_session.py scripts/normalize_user_intent.py scripts/package_plugin.py scripts/build_release_archive.py
python -m unittest tests.test_interaction_flow tests.test_create_session tests.test_session_state tests.test_initialize_project_structure tests.test_generate_execution_manifest tests.test_generate_runtime_agents tests.test_requirement_alignment_report tests.test_build_session_report tests.test_validate_contracts tests.test_doctor tests.test_apply_to_workspace tests.test_package_plugin
```

只修改本文档时，不需要运行插件校验或单元测试；最终回复必须说明未运行原因。

## 验收指标

| 指标 | 要求 |
| --- | --- |
| 安装态一致性 | install zip 解包后包含主协议声明的 commands、agents、scripts、schemas 和 docs。 |
| 状态恢复 | active session 下继续、审核、失败、变更均能根据 state 输出下一步或推进合法 phase。 |
| 上游门禁 | Manifest 生成不能绕过 PRD、UI、设计、初始化和 module-split 前置条件。 |
| 失败返工 | code review、test、apply、requirement alignment 失败均有明确返工路径。 |
| apply 安全 | apply 默认不覆盖差异文件，成功后验证真实工作区。 |
| 发布卫生 | dist 不作为长期事实源，release manifest 和 zip 可重建。 |
| 文档一致性 | README、SKILL、CHANGELOG、RELEASE 与实际源码能力一致。 |

## 未执行项或风险说明

- P0/P1 当前已完成；`dist/` manifest、source zip 和 install zip 已重建。
- 已完成：install artifact smoke test，覆盖 install zip 解包与 `python bin/spl doctor`。
- 发布前必须记录：真实 Claude Code 安装态 E2E，覆盖真实插件安装、`/spl` 命令可见、`/spl:doctor` 和首次 `/spl requirements.md <session_id>` 到 PRD 审核握手点。
- 当前未删除 `dist/` 文件，只执行覆盖式重建。
- `agents/ui/` 历史子 agent 目录已由用户删除；后续仅需验证 release manifest 和 install zip 不再包含 `agents/ui/*.md`。
- DAG state runner、script 状态推进统一、UI 实现契约和 brownfield-selective 的最小源码能力已落地；继续实现设计文档中的完整 executor 等未实施扩展时，必须单独设计后再修改。
- 任何修改 `skills/superlooper/SKILL.md` 主体调度协议的任务都必须明确说明是否影响七流程主体语义。
