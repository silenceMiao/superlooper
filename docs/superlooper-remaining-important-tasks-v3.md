# Superlooper 剩余重要任务分析 v3

## 分析边界

本报告同步 Superlooper P0/P1 收口、`agents/ui/` 删除、发布产物重建、P2 设计实施和 install 包裁剪后的剩余任务状态。

本次分析不纳入以下方向：

- 统计。
- 监控。
- observability。
- monitors。

## 五步追问法结论

### 1. 这个问题的目标是什么

目标是确认剩余增强项已经具备设计边界，并判断后续是否进入实现阶段。

### 2. 当前已经完成了什么

当前已完成插件 manifest、`/spl` 系列命令、PRD、UI、设计、初始化、Manifest、动态 agent、审查、合并、测试、apply、workspace validation、需求反向校对、失败返工、安装文档、发布门禁、CHANGELOG、install smoke test、UI 历史子 agent 降噪、四项 P2 设计和四项 P2 源码能力。install artifact smoke test 只覆盖 install zip 解包和 `python bin/spl doctor`，不等于真实 Claude Code 插件安装态 E2E。

### 3. 剩余瓶颈在哪里

剩余瓶颈不再是 P2 最小源码能力缺失，而是设计文档、backlog 和发布叙述必须准确区分“已实施最小能力”和“未实施扩展边界”。

### 4. 暂时排除什么

已完成或已关闭的 P0/P1/P3 降噪任务不再作为待办保留。P2 设计文档本身不等于实现，不自动触发源码改造。

### 5. 最终判断

当前插件已具备“不要求大而全”的完整基础使用能力。四项 P2 任务已完成设计和最小源码能力落地，后续只保留已明确的扩展边界、发布产物重建验收和独立增强。

## 已完成或已关闭任务

| 原优先级 | 任务 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| P0 | active session 入口分流与继续语义 | 已完成 | `continue_current_flow` 已具备真实状态推进。 |
| P0 | apply 前后质量门禁 | 已完成 | apply 后已有 `workspace_validation`，失败阻断最终报告。 |
| P0 | 安装产物级 smoke test | 已完成 | install zip 解包后运行 `python bin/spl doctor`。 |
| P1 | code review / test / apply / requirement alignment 失败返工 | 已完成 | run 阶段失败已有 canonical action 和局部返工路径。 |
| P1 | execution manifest 脚本层 UI/设计门禁 | 已完成 | Manifest 生成前检查 UI、设计、初始化和 state 前置条件。 |
| P1 | 动态 `module_*` agent 约束固化 | 已完成 | 动态 agent 文件包含 `Runtime Module Constraints`。 |
| P1 | 用户安装、升级、卸载、首次 Quick Start | 已完成 | README 和 RELEASE 已同步 install artifact 用户路径。 |
| P1 | `dist/` 仓库卫生与发布产物重建 | 已完成 | release manifest、source zip 和 install zip 已重建。 |
| P2 | UI 历史子 agent 降噪 | 已关闭 | 用户已删除 `agents/ui/`，当前静态 UI agent 保留为 `agents/ui-architect.md`。 |
| P2 | CHANGELOG 与发布叙述收口 | 已完成 | `CHANGELOG.md` 已反映 `1.0.0` 当前能力。 |

## P2 设计与源码落地清单

| 优先级 | 任务 | 当前状态 | 设计文档 | 实现必要性 | 改善要点 |
| --- | --- | --- | --- | --- | --- |
| P2 | 消费 `execution_manifest.json` 的 DAG state runner | 已实施最小源码能力 | `docs/design/dag-executor-design.md` | 非基础可用必须项 | 当前实现为 DAG state runner；真实 subagent 调度、节点级恢复和内置执行摘要门禁属于完整 executor 未实施扩展。 |
| P2 | script 级状态推进与 command 级状态推进统一 | 已实施最小源码能力 | `docs/design/script-state-unification-design.md` | 非基础可用必须项 | 当前实现为 `script_events` 最小记录；完整桥接层、report/gate 细粒度事件和 last_error 自动采集属于未实施扩展。 |
| P2 | UI 设计到真实实现的一等契约 | 已实施最小源码能力 | `docs/design/ui-implementation-contract-design.md` | 非基础可用必须项 | UI 页面、交互、组件和验收编号已进入模块 payload、agent 契约和 validator 轻量正文审计；完整 Markdown AST 与跨报告结构化证据链属于未实施扩展。 |
| P2 | brownfield-selective 能力 | 已实施最小源码能力 | `docs/design/brownfield-selective-design.md` | 非基础可用必须项 | 当前实现为模块级 allowed/forbidden/test/overwrite 契约；project profile glob、dependency policy 和条件必填属于未实施扩展。 |

## 当前可用性判断

当前 Superlooper 已具备基础完整使用能力：

- 可以通过 `.claude-plugin/plugin.json` 作为 Claude Code plugin 识别。
- 可以通过 `/spl` 系列命令进入 PRD、UI、设计、run、status、resume 和 doctor。
- 可以生成 PRD、UI 固定产物、设计文档、初始化报告、module-split、execution manifest、动态 `module_*` agent 和 execution summary。
- 可以执行模块产物审查、合并、测试、apply 和 PRD 反向需求校对闭环。
- 可以处理 PRD/UI/设计反馈、代码审查失败、测试失败、apply 冲突、需求校对失败和深层变更影响分析。
- 可以构建 source/install 发布产物，并通过 install artifact smoke test。
- 发布候选对外发布前必须按 `docs/RELEASE.md` 的记录模板补充真实 Claude Code 安装态 E2E。

## 当前收口顺序

1. 重建 source archive，确认 `docs/design/` 仍保留。
2. 重建 install archive，确认 `docs/design/` 不进入普通用户安装产物。
3. 执行 install artifact smoke test。
4. 执行 Python 编译、定向测试、完整相关测试和 `claude plugin validate . --strict`。
5. 执行并记录真实 Claude Code 安装态 E2E：安装 install zip、确认 `/spl` 系列命令可见、运行 `/spl:doctor`、运行 `/spl requirements.md <session_id>` 到 PRD 审核握手点。

原因：四项 P2 已进入源码、schema、validator、agent 契约和测试，最终风险集中在发布产物是否与最新源码一致。

## 实现前硬门禁

任一 P2 项进入实现前，必须先确认：

- 是否修改 `skills/superlooper/SKILL.md`。
- 是否改变七流程主体语义。
- 是否改 schema。
- 是否改 validator。
- 是否改 agent payload。
- 是否改 apply 覆盖策略。
- 是否需要重建发布产物。

## 验收要求

如果只更新本文档和设计文档，至少执行：

```bash
python scripts/build_release_archive.py --mode source
python scripts/build_release_archive.py --mode install
python -m unittest tests.test_package_plugin.InstallArtifactSmokeTest
claude plugin validate . --strict
```

如果修改源码、协议、schema 或测试，至少执行：

```bash
python -m py_compile scripts/validate_miao_contracts.py scripts/merge_artifacts.py scripts/apply_to_workspace.py scripts/initialize_project_structure.py scripts/generate_execution_manifest.py scripts/generate_runtime_agents.py scripts/build_execution_summary.py scripts/build_session_report.py scripts/doctor.py scripts/create_session.py scripts/update_session.py scripts/resume_session.py scripts/status_session.py scripts/normalize_user_intent.py scripts/package_plugin.py scripts/build_release_archive.py
python -m unittest tests.test_interaction_flow tests.test_create_session tests.test_session_state tests.test_initialize_project_structure tests.test_generate_execution_manifest tests.test_generate_runtime_agents tests.test_requirement_alignment_report tests.test_build_session_report tests.test_validate_contracts tests.test_doctor tests.test_apply_to_workspace tests.test_package_plugin
claude plugin validate . --strict
```

## 未执行项或风险说明

- DAG state runner、script 状态推进统一、UI 实现契约和 brownfield-selective 已落地最小源码能力，完整 executor 等扩展边界已记录在对应设计文档。
- 若没有真实 Claude Code 安装态 E2E 记录，不得宣称发布前真实安装态 E2E 已通过。
- `InstallArtifactSmokeTest` 不覆盖 Claude Code 插件安装器、slash command 可见性或真实 `/spl` 命令调度。
- `docs/design/` 只作为 source 分发、审计和后续维护参考，不进入普通用户 install artifact。
- 任何修改 `skills/superlooper/SKILL.md` 主体调度协议的任务都必须明确说明是否影响七流程主体语义。
- 后续新增增强项必须继续按设计、schema、validator、agent 契约、测试和 README 联动方式落地。
