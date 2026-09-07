# Superlooper 流程减重、下游自校对与 PRD 反向门禁 v3 实施文档

## 项目概述

本文档融合三类输入：

- `docs/superlooper-flow-weight-and-handshake-analysis-v3.md` 对当前流程过重、握手过多、用户难以审核内部产物的只读分析。
- 新增问题一：下一个流程的产物如何握手复核上一个流程的产物，不符合则自动 loop，以减少人工握手和终端提示。
- 新增问题二：全流程执行完成后必须反向再握手 PRD，确保最终交付不是只完成代码和测试，而是回到需求基线闭环。

综合结论：方案可行，推荐将 Superlooper v3 主模型定义为：

```text
阶段自校对 + validator 校验 + 受控 loop + 执行摘要握手 + PRD 最终反向门禁
```

综合可行度为 **91%**。

| 议题 | 可行度 | 结论 |
| --- | --- | --- |
| 下游产物复核上游产物 | 88% | 可落地为统一 `upstream_alignment` 状态块、validator 校验和受控 loop。 |
| 中间人工握手减重 | 86% | 设计、初始化、module-split、Manifest 可合并为执行前摘要握手。 |
| 全流程完成后反向握手 PRD | 95% | 当前已有 `requirement-verifier` 和 `resume_session.py` 复核门禁，必须保留并强化。 |
| apply 覆盖风险握手 | 98% | 当前 `apply_to_workspace.py` 已默认阻断同路径不同内容文件，不能弱化。 |
| 高级逐阶段审核模式 | 80% | 可作为 `strict_review` 模式保留，不作为默认路径。 |

## 综合分析

### 1. 问题本质

当前流程的主要问题不是七流程本身，而是用户被要求审核多个内部产物：设计文档、初始化分类、初始化版本、module-split、execution_manifest。用户无法稳定判断这些产物是否符合原始需求、PRD、UI 和实现约束。

新模型把审核责任重新分配：

| 审核对象 | 当前责任 | v3 责任 |
| --- | --- | --- |
| 需求理解 | 用户审核 PRD | analyst 自校对原始需求，用户确认 PRD 基线。 |
| UI 是否符合 PRD | 用户看 UI 产物 | ui-architect 输出 PRD 追溯状态，用户只确认体验方向。 |
| 设计是否符合 PRD/UI | 用户看设计文档 | architect 输出 `upstream_alignment`，validator 校验结构。 |
| module-split 是否合理 | 用户看 JSON | architect 自校对模块边界，validator 校验 target_files、refs、file_roles。 |
| Manifest 是否正确 | 用户看 DAG/payload | Manifest 生成器和 validator 校验，不再展示完整 JSON 给用户审核。 |
| 最终是否满足 PRD | 用户看最终报告 | requirement-verifier 对 PRD 逐项反向校对，用户最终确认。 |

### 2. 第一性原理五步追问法

#### 问题本质

要解决的是“谁最适合判断一致性”。内部产物一致性由 agent 和 validator 判断；业务意图、风险接受和交付确认由用户判断。

#### 受益对象

| 对象 | 收益 |
| --- | --- |
| 用户 | 终端提示减少，只处理业务确认、风险确认和最终确认。 |
| 调度器 | 状态流转更清晰，减少连续 waiting_review。 |
| agent 链路 | 每个下游环节必须对上游输入负责。 |
| validator | 成为内部产物放行依据，而不是事后辅助检查。 |
| 维护者 | loop、反馈、revision 都有记录，问题可追溯。 |

#### 现状约束

| 约束 | 证据 |
| --- | --- |
| PRD 阻塞决策和 PRD 基线确认不能删除。 | `skills/superlooper/SKILL.md:72`、`skills/superlooper/SKILL.md:81` |
| UI 产物已有机器校验入口。 | `skills/superlooper/SKILL.md:97` |
| 当前设计、初始化、module-split、Manifest 存在连续人工握手。 | `skills/superlooper/SKILL.md:116`、`skills/superlooper/SKILL.md:122`、`skills/superlooper/SKILL.md:131`、`skills/superlooper/SKILL.md:137`、`skills/superlooper/SKILL.md:155` |
| 深层变更已有受控影响分析协议，可复用为 loop 边界。 | `skills/superlooper/SKILL.md:159` |
| 最终 PRD 反向校对已有硬门禁。 | `skills/superlooper/SKILL.md:185`、`skills/superlooper/SKILL.md:186`、`skills/superlooper/SKILL.md:187`、`skills/superlooper/SKILL.md:188` |
| apply 覆盖冲突必须阻断。 | `skills/superlooper/SKILL.md:182`、`scripts/apply_to_workspace.py:45`、`scripts/apply_to_workspace.py:164` |
| 修改协议必须联动 README、commands、configs、schemas、validator 和测试。 | `docs/DEVELOPMENT.md:52`、`docs/DEVELOPMENT.md:73` |

#### 成功标准

| 标准 | 判断方式 |
| --- | --- |
| 下游环节能明确说明检查了哪些上游输入。 | `upstream_alignment.checked_inputs` 非空。 |
| 不符合时能自动 loop。 | `alignment_status=FAIL`、`loop_required=true`、`loop_target_phase` 合法。 |
| 真正需要用户决策时才停。 | `alignment_status=BLOCKED` 且 `blocking_decisions` 非空。 |
| loop 不无限重试。 | session state 记录 loop 次数和 revision，超过阈值升级人工。 |
| 执行前只让用户确认摘要。 | `execution_summary.md` 取代完整 Manifest 预览。 |
| 最终必须回到 PRD。 | `requirement_alignment_status=PASS`、`unmet_requirement_count=0`、`unchecked_acceptance_count=0` 才能交付。 |

#### 边界反证

| 场景 | 处理 |
| --- | --- |
| PRD 存在阻塞 DEC | 停止并让用户确认，不自动 loop。 |
| 下游发现上游遗漏需求 | 写 feedback report，loop 回上游产物。 |
| loop 两次仍不通过 | 停止并输出人工介入摘要。 |
| 初始化完成后发现设计偏差 | 不直接覆盖下游产物，进入影响分析或受控局部重跑。 |
| apply 发现目标文件不同 | 停止并输出冲突报告，不静默覆盖。 |
| 最终 PRD 反向校对失败 | 不允许完成交付，进入修正链路。 |

## 可行性评估

### 总体评估

| 维度 | 评分 | 说明 |
| --- | --- | --- |
| 技术可行性 | 92% | 当前已有 agent 状态块、validator、report 和 session state。 |
| 协议改造可行性 | 86% | 需要调整 `SKILL.md`、commands、configs、resume 和 tests。 |
| 用户体验收益 | 94% | 默认人工停顿减少，用户只看摘要和风险。 |
| 质量风险可控性 | 89% | 受控 loop 和最终 PRD 反向门禁能覆盖主要偏差。 |
| 实施复杂度 | 84% | 需要新增执行摘要脚本、状态字段、loop 计数和 validator scope。 |

综合评估：**91% 可行**。

### 人工握手变化

| 当前握手 | v3 默认处理 | 是否保留人工 |
| --- | --- | --- |
| PRD 阻塞决策 | analyst 输出关键决策看板 | 保留 |
| PRD 基线确认 | analyst 自校对原始需求后输出 PRD 摘要 | 保留 |
| UI 审核 | ui-architect 自校对 PRD，用户只确认体验/功能方向 | 保留但变轻 |
| 设计文档审核 | architect 自校对 PRD/UI，失败自动 loop | 默认不保留 |
| 初始化分类选择 | architect 给出默认分类，执行摘要一次确认 | 默认不保留 |
| 初始化版本选择 | architect 给出默认版本，执行摘要一次确认 | 默认不保留 |
| module-split 审核 | validator + architect 自校对 | 默认不保留 |
| execution_manifest 审核 | validator + 执行摘要 | 默认不保留 |
| apply 冲突确认 | 冲突报告 + 用户授权覆盖策略 | 保留 |
| 最终 PRD 反向确认 | requirement-verifier 输出需求符合性表格 | 保留 |

## 技术引用

| 能力 | 当前基础 | v3 改造 |
| --- | --- | --- |
| PRD 状态块 | analyst 已输出 `analyst_status` | 增加 `prd_alignment_to_raw_requirement`。 |
| UI 校验 | `ui-artifacts` scope | 增加 UI 对 PRD 的 `upstream_alignment`。 |
| 设计质量扫描 | architect 已读取 PRD/UI | 增加标准化 PASS/FAIL/BLOCKED 状态。 |
| Manifest 校验 | `execution` scope | Manifest 不再进入用户审核，校验结果进入执行摘要。 |
| 代码审查门禁 | code-reviewer PASS/FAIL | FAIL 指向具体 module loop。 |
| 测试门禁 | tester PASS/FAIL | 增加 PRD/AC 覆盖状态。 |
| 最终校对 | requirement-verifier | 正文改成需求符合性表格，保留 YAML 状态块。 |
| 状态恢复 | resume_session | 增加自动 loop 和执行摘要确认路径。 |

## 目录结构

重点新增和修改范围如下：

```text
superlooper/
├── agents/
│   ├── analyst.md                    # 增加 PRD 对原始需求自校对
│   ├── ui-architect.md               # 增加 UI 对 PRD 自校对
│   ├── architect.md                  # 增加设计/module-split 对 PRD/UI 自校对
│   ├── developer.md                  # 增加模块实现对 design/Manifest 自校对
│   ├── code-reviewer.md              # 增加失败指向 module loop 的报告字段
│   ├── tester.md                     # 增加 PRD/AC 测试覆盖自校对
│   └── requirement-verifier.md       # 强化 PRD 反向需求符合性表格
├── commands/
│   └── spl/
│       ├── design.md                 # 默认自动完成设计、初始化、module-split 内部链路
│       ├── run.md                    # 生成执行摘要并进入执行确认
│       └── resume.md                 # 支持 loop、摘要确认和最终 PRD 门禁恢复
├── configs/
│   └── interaction-flow.json         # 新增执行摘要和 loop canonical action
├── schemas/
│   ├── interaction-flow.schema.json  # 同步 action 枚举
│   └── session-state.schema.json     # 增加 loop、summary、mode 字段
├── scripts/
│   ├── build_execution_summary.py    # 新增执行前摘要报告生成器
│   ├── normalize_user_intent.py      # 增加摘要确认和 loop 相关意图
│   ├── resume_session.py             # 增加自动 loop 调度和最终 PRD 复核路径
│   ├── update_session.py             # 记录 loop 次数、revision 和摘要报告
│   └── validate_miao_contracts.py    # 增加 upstream alignment 和 execution summary 校验
├── tests/
│   ├── test_execution_summary.py
│   ├── test_upstream_alignment.py
│   ├── test_interaction_flow.py
│   ├── test_session_state.py
│   └── test_validate_contracts.py
└── README.md                         # 更新默认握手路径和验收说明
```

## 常用命令

| 命令 | 运行目录 | 用途 | 预期结果 |
| --- | --- | --- | --- |
| `claude plugin validate . --strict` | 插件根目录 | 校验 Claude Code plugin 结构 | 返回成功。 |
| `python -m py_compile scripts/validate_miao_contracts.py scripts/merge_artifacts.py scripts/apply_to_workspace.py` | 插件根目录 | 执行项目固定脚本语法验收 | 返回 0。 |
| `python -m py_compile scripts/build_execution_summary.py scripts/normalize_user_intent.py scripts/resume_session.py scripts/update_session.py` | 插件根目录 | 校验新增和联动脚本语法 | 返回 0。 |
| `python scripts/validate_miao_contracts.py --workspace-root . --session-id session_dummy --scope interaction-flow` | 插件根目录 | 校验交互配置和命令映射 | 无 schema 或命令映射错误。 |
| `python scripts/validate_miao_contracts.py --workspace-root <project-root> --session-id <session_id> --scope upstream-alignment` | 插件根目录 | 校验下游复核上游状态块 | 所有状态块字段完整且状态合法。 |
| `python scripts/validate_miao_contracts.py --workspace-root <project-root> --session-id <session_id> --scope execution-summary` | 插件根目录 | 校验执行前摘要报告 | 摘要 YAML 和正文必备章节完整。 |
| `python scripts/validate_miao_contracts.py --workspace-root <project-root> --session-id <session_id> --scope requirement-alignment-report` | 插件根目录 | 校验最终 PRD 反向门禁 | PASS 时未满足需求数和未覆盖验收数均为 0。 |
| `python -m unittest tests.test_execution_summary tests.test_upstream_alignment tests.test_interaction_flow tests.test_session_state tests.test_validate_contracts` | 插件根目录 | 回归摘要、loop、交互、状态和契约 | 所有测试通过。 |

## 编码规范

- 不删除七流程叙述，默认路径改为“内部自动推进 + 执行摘要握手”。
- 不把执行摘要写入 Manifest，执行摘要属于 report 层。
- 不把完整 `execution_manifest.json` 作为用户审核对象，Manifest 由 validator 放行。
- 下游 agent 不直接修改上游产物，只能写 feedback report 并由调度器触发 loop。
- 自动 loop 必须记录 `loop_target_phase`、`feedback_report`、`revision` 和 `loop_count`。
- 同一阶段默认最多自动 loop 2 次，第 3 次仍失败必须升级人工处理。
- 初始化完成后不得直接覆盖设计、module-split、Manifest 或模块产物，必须走受控影响分析或局部重跑。
- `execution_summary.md` 第一个代码块必须是 YAML 状态块。
- `upstream_alignment` 必须包含 `alignment_status`、`checked_inputs`、`checked_refs`、`mismatch_count`、`blocking_decisions`、`loop_required`、`loop_target_phase`、`feedback_report`。
- `requirement_alignment_report.md` 第一个代码块仍必须是 YAML 状态块，正文必须包含 PRD 需求符合性表格。
- 安全红线保持不变：禁止 SQL 拼接，禁止硬编码密码、密钥、令牌、连接串；外部输入进入鉴权、查询、文件、命令、模板渲染链路前必须校验。

## 工作流程

### 阶段一：定义统一上游自校对契约

统一状态块如下：

```yaml
upstream_alignment:
  alignment_status: PASS
  checked_inputs:
    - .superlooper/context/<session_id>/prd.md
  checked_refs:
    requirements:
      covered:
        - REQ-001
      missing: []
    acceptance:
      covered:
        - AC-001
      missing: []
    decisions:
      covered:
        - DEC-001
      missing: []
    open_questions:
      covered:
        - OPEN-001
      missing: []
  mismatch_count: 0
  blocking_decisions: []
  loop_required: false
  loop_target_phase: null
  feedback_report: null
```

状态含义：

| 状态 | 含义 | 调度动作 |
| --- | --- | --- |
| `PASS` | 下游产物与上游输入一致 | 自动进入下一步。 |
| `FAIL` | 存在可由 agent 修复的不一致 | 写 feedback report，loop 回 `loop_target_phase`。 |
| `BLOCKED` | 存在需要用户决策的问题 | 停止并输出阻塞决策摘要。 |

### 阶段二：建立下游复核上游链路

| 当前阶段 | 下游复核对象 | FAIL loop 目标 | BLOCKED 停止条件 |
| --- | --- | --- | --- |
| analyst | 原始需求 | `prd` | 需求方向、合规边界、业务规则缺失。 |
| ui-architect | 已审核 PRD | `ui_design` | 用户体验方向需要业务选择。 |
| architect | 已审核 PRD + UI 产物 | `design` | 技术边界影响业务范围。 |
| module-split | design + initialization_report | `design` | 模块边界无法满足并行开发。 |
| execution_manifest | module-split + runtime agent 规则 | `design` 或 `run` | target_files 冲突无法自动消解。 |
| developer | design + module payload + Manifest | 当前 module | 模块需求缺少必要决策。 |
| code-reviewer | module output + Manifest + design | 对应 module | 安全或架构阻断问题。 |
| tester | merge output + PRD + design + AC-* | module 或 merge | 验收口径需要用户确认。 |
| requirement-verifier | PRD + test + apply + session report | `run` 修正链路 | PRD 与交付结果存在不可自动修复偏差。 |

### 阶段三：实现受控 loop

调度规则：

```text
alignment_status=PASS
validator=PASS
=> continue

alignment_status=FAIL
loop_required=true
loop_count < max_loop_count
=> write feedback report
=> update revision
=> rerun loop_target_phase

alignment_status=FAIL
loop_count >= max_loop_count
=> stop
=> ask user with failure summary

alignment_status=BLOCKED
blocking_decisions 非空
=> stop
=> ask user
```

session state 新增字段：

```json
{
  "workflow_mode": "standard",
  "execution_summary_status": "NOT_STARTED",
  "execution_summary_report": null,
  "loop_policy": {
    "max_auto_loop_per_phase": 2
  },
  "loop_state": {
    "current_loop_target_phase": null,
    "loop_count_by_phase": {},
    "last_alignment_status": null,
    "last_feedback_report": null
  }
}
```

### 阶段四：合并设计、初始化、module-split 和 Manifest 握手

默认 `standard` 模式流程：

```text
UI 通过
-> architect 生成 design + initialization-advice
-> architect 输出 upstream_alignment
-> PASS 后自动选择初始化分类和版本
-> initialize_project_structure.py
-> architect 生成 module-split
-> validate module-split
-> generate_execution_manifest.py
-> generate_runtime_agents.py
-> validate execution
-> build_execution_summary.py
-> 用户确认“按此执行”
```

执行摘要报告路径：

```text
.superlooper/reports/<session_id>/execution_summary.md
```

执行摘要 YAML：

```yaml
execution_summary_status: READY_FOR_APPROVAL
session_id: <session_id>
workflow_mode: standard
project_category: <category>
project_version: <version>
module_count: <number>
target_file_count: <number>
risk_count: <number>
blocking_decisions: []
upstream_alignment_status: PASS
module_split_validated: true
execution_manifest_validated: true
report_path: .superlooper/reports/<session_id>/execution_summary.md
```

执行摘要正文必须包含：

- 项目类型和版本。
- PRD/UI 到设计的符合性结论。
- 模块列表。
- 将创建或修改的关键文件。
- 风险、冲突和不可逆动作。
- 测试策略。
- 用户确认动作。

### 阶段五：强化最终 PRD 反向门禁

最终门禁不检查“流程是否跑完”，而检查“PRD 是否被满足”。

requirement-verifier 必须输出：

```yaml
session_id: <session_id>
requirement_alignment_status: PASS
unmet_requirement_count: 0
unchecked_acceptance_count: 0
prd_path: .superlooper/context/<session_id>/prd.md
test_report_path: .superlooper/reports/<session_id>/test_report.md
apply_report_path: .superlooper/reports/<session_id>/apply_report.json
report_path: .superlooper/reports/<session_id>/requirement_alignment_report.md
```

正文必须包含需求符合性表格：

| PRD 项 | 状态 | 证据 | 风险 |
| --- | --- | --- | --- |
| `REQ-*` | 满足/未满足 | 测试报告、应用报告、session report | 无或具体风险 |
| `AC-*` | 已验证/未验证 | 测试报告 | 无或具体风险 |
| `DEC-*` | 已落实/未落实 | 代码审查报告、session report | 无或具体风险 |
| `OPEN-*` | 已按默认处理/未处理 | module-split、Manifest、测试报告 | 无或具体风险 |

最终交付规则：

```text
requirement_alignment_status=PASS
unmet_requirement_count=0
unchecked_acceptance_count=0
resume_session.py 二次复核通过
=> 允许输出最终验收报告
```

若失败：

```text
requirement_alignment_status=FAIL
=> 不允许完成交付
=> 进入 run 修正链路或影响分析
```

### 阶段六：保留严格审核模式

`strict_review` 模式保留旧握手：

- 设计文档审核。
- 初始化分类选择。
- 初始化版本选择。
- module-split 审核。
- execution_manifest 审核。

启用方式：用户显式选择严格模式，或项目配置写入：

```json
{
  "workflow_mode": "strict_review"
}
```

默认模式固定为：

```json
{
  "workflow_mode": "standard"
}
```

## 模块修改联动检查表

| 修改类别 | 必须同步检查 |
| --- | --- |
| 主协议减重 | `skills/superlooper/SKILL.md`、`README.md`、`commands/spl/design.md`、`commands/spl/run.md`、`commands/spl/resume.md` |
| 上游自校对 | `agents/*.md`、`scripts/validate_miao_contracts.py`、`tests/test_upstream_alignment.py` |
| 受控 loop | `schemas/session-state.schema.json`、`scripts/update_session.py`、`scripts/resume_session.py`、`tests/test_session_state.py` |
| 执行摘要 | `scripts/build_execution_summary.py`、`scripts/validate_miao_contracts.py`、`tests/test_execution_summary.py`、`README.md` |
| 意图归一化 | `configs/interaction-flow.json`、`schemas/interaction-flow.schema.json`、`scripts/normalize_user_intent.py`、`tests/test_interaction_flow.py` |
| PRD 反向门禁 | `agents/requirement-verifier.md`、`commands/spl/run.md`、`scripts/build_session_report.py`、`scripts/validate_miao_contracts.py`、`tests/test_requirement_alignment_report.py` |
| apply 风险握手 | `scripts/apply_to_workspace.py`、`agents/workspace_applier.md`、`commands/spl/run.md`、`README.md` |

## 注意事项

- 本方案影响 Superlooper 主体调度协议，实施前必须获得用户明确批准。
- 下游自校对不是下游私自修改上游，所有修正必须通过 feedback report 和 loop 由调度器执行。
- 自动 loop 只处理可由 agent 修正的不一致，业务决策、覆盖风险、不可恢复动作必须停下。
- 最终 PRD 反向门禁不得删除，不得改成只看 test PASS。
- apply 覆盖策略不得弱化，已有不同内容文件必须输出冲突报告。
- `strict_review` 只作为高级模式，不能让默认流程继续维持多重人工停顿。
- `.superlooper/` 和 `.claude/agents/generated/` 是运行时产物，不进入插件源码。
- 不得把本机私有配置、令牌、密钥、内网地址写入插件文件。
- 删除文件、批量改写、force push、数据库删除、共享环境修改等破坏性操作必须事先审批。

## 工具集成

| 工具 | 用途 |
| --- | --- |
| `claude plugin validate . --strict` | 校验插件结构。 |
| `scripts/validate_miao_contracts.py` | 校验 UI、module-split、execution、upstream alignment、execution summary、requirement alignment。 |
| `scripts/build_execution_summary.py` | 生成执行前摘要报告。 |
| `scripts/resume_session.py` | 执行 loop 恢复、摘要确认和最终 PRD 复核。 |
| `scripts/update_session.py` | 记录 loop、revision、summary 和事件日志。 |
| `scripts/apply_to_workspace.py` | 应用产物并保留覆盖冲突阻断。 |
| `scripts/doctor.py` | 汇总插件结构、脚本、schema、命令和发布过滤自检。 |

## 验收标准

### 文档验收

| 指标 | 标准 |
| --- | --- |
| 综合分析 | 覆盖上游自校对、受控 loop、中间握手减重和 PRD 最终反向门禁。 |
| 可行性评估 | 给出综合可行度和分项可行度。 |
| 实施步骤 | 明确状态块、loop、执行摘要、最终 PRD 门禁和高级模式。 |
| 风险边界 | 明确用户决策、apply 覆盖、无限 loop、深层变更和最终交付门禁。 |
| 联动范围 | 覆盖 agents、commands、configs、schemas、scripts、tests、README。 |

### 代码实施验收

实施代码后必须执行：

```bash
claude plugin validate . --strict
python -m py_compile scripts/validate_miao_contracts.py scripts/merge_artifacts.py scripts/apply_to_workspace.py scripts/initialize_project_structure.py scripts/generate_execution_manifest.py scripts/build_session_report.py scripts/doctor.py scripts/create_session.py scripts/update_session.py scripts/resume_session.py scripts/status_session.py scripts/normalize_user_intent.py scripts/build_execution_summary.py
python -m unittest tests.test_interaction_flow tests.test_create_session tests.test_session_state tests.test_initialize_project_structure tests.test_generate_execution_manifest tests.test_requirement_alignment_report tests.test_build_session_report tests.test_validate_contracts tests.test_doctor tests.test_execution_summary tests.test_upstream_alignment
```

通过标准：

- 默认用户中间握手减少。
- `upstream_alignment` 可机器校验。
- FAIL 可受控 loop，BLOCKED 会停止请求用户。
- 执行摘要替代完整 Manifest 审核。
- `requirement_alignment_report.md` 对 PRD 逐项闭环。
- apply 冲突仍阻断。
- `strict_review` 模式仍可逐阶段审核。
