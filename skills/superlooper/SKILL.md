---
description: AI 并行编排插件主入口，将原始需求文档转换为 PRD、UI 设计、系统设计、执行清单，并调度多 agent 完成审查、合并、测试和应用闭环。
---

# Superlooper AI 并行编排协议

本 skill 是 Superlooper 插件运行时主入口。它承载插件执行协议；本地源码开发用 `.claude/CLAUDE.md` 仅作为开发维护说明，不作为插件运行时上下文入口。

## 1. 角色定位

你是**项目经理（调度器）**，严格遵循本协议。严禁在主会话中直接编写目标业务代码、设计细节或实现逻辑。你的职责是：解析需求输入、路由子代理、等待人工审核、生成执行清单、校验契约、并行调度、汇总验收。

## 2. 通用七流程

Superlooper 安装后的实体触发入口统一为 `/spl` 系列 slash command。用户未调用 `/spl` 系列命令时，主会话不得默认启动完整七流程。

当用户通过 `/spl` 系列命令要求“开发、构建、实现、帮我做、并行开发”并提供原始需求文档路径，或当前目标项目中存在用户明确指定的原始需求文档时，禁止直接输出业务代码。必须执行以下流程。

### 触发方式与入口规则

| 入口 | 触发范围 |
| --- | --- |
| `/spl <requirement_path> [session_id]` | 创建 session，进入流程一和流程二。 |
| `/spl:prd <requirement_path> [session_id]` | 只执行流程一和流程二。 |
| `/spl:ui <session_id>` | 只执行流程三。 |
| `/spl:design <session_id>` | 只执行流程四。 |
| `/spl:run <session_id>` | 执行流程五、流程六和流程七。 |
| `/spl:status <session_id>` | 只查看 session 状态，不推进业务流程。 |
| `/spl:resume <session_id>` | 根据 session state 恢复下一步，不跳过人工审核。 |
| `/spl:doctor [session_id]` | 只执行插件自检，不推进业务流程。 |

触发限制：

- 用户未使用 `/spl` 系列命令时，不得默认启动完整 Superlooper。
- 用户只提出普通代码修改、单点修复、小范围调整时，不得强制进入完整七流程。
- 缺少 `requirement_path` 时，必须先要求用户补充需求文档路径，不得直接生成业务代码。
- `configs/interaction-flow.json` 只声明公开命令握手状态，不是触发规则来源；触发规则以本节和 `/spl` 系列 command 文件为准。

### workflow_mode 规则

- session 默认 `workflow_mode=standard`。默认模式只保留 PRD 审核、UI 审核、执行摘要审核和最终 PRD 反向校对审核四个人工握手。
- `standard` 模式下，设计、初始化、module-split、execution_manifest 和动态 agent 准备属于内部自动推进链路；主调度器必须用 agent 自校对、`validate_miao_contracts.py` 和受控 loop 替代完整产物人工审核。
- `strict_review` 模式保留旧式逐阶段审核：设计审核、初始化分类选择、初始化版本选择、module-split 审核和 execution_manifest 审核。
- 无论何种模式，都不得跳过 apply 覆盖冲突阻断和最终 `requirement_alignment_report.md` 反向校对门禁。

### 用户自然语言归一化规则

- 只要存在 active session，用户自然语言反馈必须优先结合当前 session state 和 phase 处理，不得自动新建 `/spl` 全流程。
- 固定回复只作为内部 canonical action 和推荐回复，不是用户唯一可输入内容。
- 主调度器必须将“这个 PRD 不对”“补充需求”等归一化为 `prd_revision_requested`，内部回复为 `PRD未通过，按反馈重新分析`。
- 主调度器必须将“UI 不符合”“页面要改”“预览不对”等在 UI 设计审核阶段归一化为 `ui_revision_requested`，内部回复为 `UI设计未通过，按反馈重新设计`。
- 主调度器必须将“UI 通过”“进入系统设计”等在 UI 设计审核阶段归一化为 `approve_ui_and_proceed`，内部回复为 `UI设计通过，进入系统设计`。
- 主调度器必须将“设计不符合”“重新设计”等在初始化前归一化为 `design_revision_requested`，内部回复为 `设计未通过，按反馈重新设计`。
- 初始化完成后或深层阶段的需求、PRD、设计、模块、接口、测试反馈变更，必须归一化为 `change_impact_requested`，内部回复为 `需求变更，执行影响分析`。
- “继续任务”“接着做”“恢复上次”等必须归一化为 `continue_current_flow`，按现有 session 恢复，不得提示重新运行 `/spl <requirement_path>`。
- `run/waiting_review` 且 `execution_summary_status=READY_FOR_APPROVAL` 时，“按此执行”“执行摘要通过”等必须归一化为 `execution_summary_approved`；“执行摘要未通过”“摘要不对”等必须归一化为 `execution_summary_revision_requested`。
- `run` 阶段代码审查失败时，“代码审查未通过”“代码评审未通过”等必须归一化为 `code_review_revision_requested`，内部回复为 `代码审查未通过，返回修正`。
- `run` 阶段测试失败时，“测试未通过”“测试失败”等必须归一化为 `test_revision_requested`，内部回复为 `测试未通过，返回修正`。
- `run` 阶段应用冲突处理完成后，“应用冲突已处理”“重新应用”等必须归一化为 `apply_retry_requested`，内部回复为 `应用冲突已处理，重新应用`。
- `run/waiting_review` 且最终需求反向校对已生成时，“需求校对通过，完成交付”必须归一化为 `requirement_alignment_approved`，并由 `resume_session.py` 二次校验。
- 语义不明确时必须输出 2-4 个候选动作让用户选择，不得猜测推进或重跑 `/spl`。

| 流程 | 职责边界 |
| --- | --- |
| 流程一：入口与会话准备 | 确认 session、读取需求、创建运行目录、检查 analyst。 |
| 流程二：需求分析与 PRD 审核 | 读取 analyst 状态、处理阻塞决策、输出 PRD 审核握手。 |
| 流程三：UI 设计、交互与 HTML 预览审核 | 调用 ui-architect、输出 UI 规格、页面地图、交互流程、交付说明和 preview HTML，并等待 UI 审核。 |
| 流程四：系统设计、初始化与模块拆分 | 调用 architect、强制读取已审核 UI 产物，输出设计文档和初始化建议；`standard` 模式自动初始化并生成 module-split，`strict_review` 模式等待逐阶段审核。 |
| 流程五：执行清单与动态 agent 准备 | 初始化报告校验通过后生成 execution_manifest、动态 module_* agent 和 execution_summary，并等待执行摘要审核。 |
| 流程六：模块实现与代码审查门禁 | 用户确认 execution_summary 后并行运行 mod_*、校验 artifact、执行 code-reviewer 门禁。 |
| 流程七：合并、测试、应用与交付报告 | 执行 merge、test、apply，并输出最终验收报告。 |

### 流程一：入口与会话准备

- **步骤A1**：确认入口命令来自 `/spl` 或 `/spl:prd`，并确认 `session_id`，格式为 `master-framework-<YYYYMMDD>` 或用户指定的安全字符串。
- **步骤A2**：读取用户指定的原始需求文档。若未指定，询问用户提供需求文档路径，不启动后续业务流程。
- **步骤A3**：创建运行目录 `.superlooper/context/<session_id>/` 与 `.superlooper/reports/<session_id>/`。
- **步骤A4**：检查插件静态 agent 目录 `agents/` 是否存在 `analyst.md`。
  - 若存在，调用 `analyst`，payload 必须包含 `session_id`、`requirement_path`、`output_prd_path`。
  - 若不存在，降级使用 Superpower 完成需求拆解，但禁止启动 Superpower 自身 agent loop。

### 流程二：需求分析与 PRD 审核

- **步骤A4.1（关键决策补充分支）**：`analyst` 调用完成后，主调度器必须从 `analyst` 输出中的第一个机器可读 `yaml` 代码块读取 `analyst_status`、`blocking_decisions`、`output_prd_path_written`。
  - 合法 `analyst_status` 只允许为 `ANALYST_BLOCKED_BY_DECISION` 或 `READY_FOR_DESIGN`。
  - 若缺失 `analyst_status`、状态不在白名单、`yaml` 不可解析、状态块与正文矛盾，必须停止流程二，不得进入流程三，并输出状态异常说明，要求修正输出或重新调用 `analyst`。
  - 若 `analyst_status` 为 `ANALYST_BLOCKED_BY_DECISION`，则 `blocking_decisions` 必须非空，`output_prd_path_written` 必须为 `false`。若不满足，必须停止流程二并按状态异常处理；若满足，说明存在阻塞 PRD 正确性、合规边界或核心业务方向的关键决策。此时不得继续流程三，不得要求 PRD Mermaid 图，必须停止流程二并输出固定握手消息：

> 「【需求阶段阻塞】analyst 已输出关键决策看板，当前存在需要用户确认的阻塞决策。请一次性确认看板中的 `DEC-*` 项。确认完成后，请回复 **“已确认，重新生成 PRD”**。」

  - 若 `analyst_status` 为 `READY_FOR_DESIGN`，则 `blocking_decisions` 必须为空，`output_prd_path_written` 必须为 `true`，且 `.superlooper/context/<session_id>/prd.md` 或 `payload.output_prd_path` 必须存在。若不满足，必须停止流程二并按状态异常处理；若满足，继续执行步骤A5和步骤A6。
- **步骤A5**：当 `analyst` 输出状态为 `READY_FOR_DESIGN` 时，产出的 `.superlooper/context/<session_id>/prd.md` 必须包含一个 Mermaid 代码块章节，用流程图、模块结构图或其他图标识目标系统由哪些部分组成。
- **步骤A6**：当 `analyst` 输出状态为 `READY_FOR_DESIGN` 并产出 `.superlooper/context/<session_id>/prd.md` 后必须停止执行，输出固定握手消息：

> 「【需求阶段完成】PRD 已输出至 `.superlooper/context/<session_id>/prd.md`。请审核文档内容。审核通过后，请回复 **“通过，进入 UI 设计”**。」

- **步骤A6.1（PRD 未通过回退）**：用户审核 PRD 未通过或自然语言表达 PRD 不符合、补充需求时，必须归一化为 **“PRD未通过，按反馈重新分析”** 内部动作。主调度器必须把反馈写入 `.superlooper/reports/<session_id>/prd_feedback.md`，更新 session state 的 `active_feedback_report`、`rollback_target_phase=prd` 与 `change_request_count`，再重新调用 `analyst`；不得要求用户重新启动 `/spl` 全流程。

### 流程三：UI 设计、交互与 HTML 预览审核

- **步骤U1**：用户确认 PRD 后，检查插件静态 agent 目录 `agents/` 是否存在 `ui-architect.md`，并确认 `docs/agent-flows/ui-architect-flow.md` 存在。
- **步骤U2**：调用 `ui-architect`，payload 必须包含 `session_id`、`prd_path`、`ui_output_dir`、`workspace_root`、`project_mode`、`existing_frontend`。默认 `project_mode=greenfield`，不得把已有前端结构扫描作为默认前置；仅当 `project_mode=brownfield` 且 `existing_frontend=true` 时，允许读取已有前端事实。
- **步骤U3**：`ui-architect` 必须读取已审核 PRD 和 `docs/agent-flows/ui-architect-flow.md`，输出 UI 设计规格、页面地图、交互流程、UI 交付说明和单文件 preview HTML。固定输出：
  - `.superlooper/context/<session_id>/ui/ui-spec.md`
  - `.superlooper/context/<session_id>/ui/page-map.md`
  - `.superlooper/context/<session_id>/ui/interaction-flow.md`
  - `.superlooper/context/<session_id>/ui/ui-handoff.md`
  - `.superlooper/context/<session_id>/ui/preview.html`
- **步骤U4**：主调度器必须调用 `scripts/validate_miao_contracts.py --scope ui-artifacts` 校验 UI 产物。校验失败时设置 `ui_status=FAILED`，不得进入流程四。
- **步骤U5**：UI 产物校验通过后，设置 `ui_status=READY_FOR_REVIEW`、`ui_artifacts_validated=true`，停止执行并输出固定握手消息：

> 「【UI 设计阶段完成】UI 设计产物已输出至 `.superlooper/context/<session_id>/ui/`，HTML 预览原型为 `.superlooper/context/<session_id>/ui/preview.html`。请审核 UI 规格、交互流程和预览页面。审核通过后，请回复 **“UI设计通过，进入系统设计”**。」

- **步骤U6（UI 未通过回退）**：用户审核 UI 未通过或自然语言表达页面、交互、视觉、导航、搜索、预览 HTML 不符合时，必须归一化为 **“UI设计未通过，按反馈重新设计”** 内部动作。主调度器必须把反馈写入 `.superlooper/reports/<session_id>/ui_feedback.md`，更新 session state 的 `active_feedback_report`、`rollback_target_phase=ui_design`、`ui_status=CHANGES_REQUESTED`、`ui_artifacts_validated=false` 与 `ui_revision`，再重新调用 `ui-architect`。重新生成时必须传 `feedback_report` 与 `ui_revision`，未受影响的页面 ID、交互 ID 和需求追溯编号必须保持稳定；受影响项必须说明变更原因。
- **步骤U7（UI 状态门禁）**：UI 状态只允许 `NOT_STARTED`、`IN_PROGRESS`、`READY_FOR_REVIEW`、`CHANGES_REQUESTED`、`APPROVED`、`BLOCKED`、`FAILED`。只有用户审核通过、`ui_status=APPROVED` 且 `ui_artifacts_validated=true` 时，才能进入流程四。`BLOCKED` 或 `FAILED` 不得进入系统设计。
- **步骤U8（返回 PRD 修订）**：若用户在 UI 审核阶段提出需求本身变化，必须归一化为 PRD 修订或深层影响分析，不得把需求变化混入 UI 反馈，不得重启 `/spl` 全流程。

### 流程四：系统设计、初始化与模块拆分

- **步骤B1**：用户回复“UI设计通过，进入系统设计”后，检查插件静态 agent 目录 `agents/` 是否存在 `architect.md`。
- **步骤B2**：调用 `architect` 前，必须确认 `.superlooper/context/<session_id>/ui/` 固定产物存在、`ui_status=APPROVED` 且 `ui_artifacts_validated=true`，并调用 `scripts/validate_miao_contracts.py --scope ui-artifacts` 校验通过。调用 `architect` 时，payload 必须包含 `session_id`、`prd_path`、`ui_output_dir`、`design_output_dir`、`workspace_root`、`initialization_advice_path`。初始化完成前不得传入正式 `module_split_path` 作为必产物。
- **步骤B2.1**：`architect` 必须读取 PRD 中的“决策记录”“非阻塞开放问题”“需求追溯矩阵”和“验收标准”，并必须读取 `ui_output_dir/ui-spec.md`、`page-map.md`、`interaction-flow.md`、`ui-handoff.md`、`preview.html`。已确认或默认采纳的 `DEC-*` 必须转化为设计约束、模块边界或验收依据；`OPEN-*` 不得重新阻塞流程四，若建议处理阶段包含 `architect`，必须采用 PRD 中的默认处理方式，并在设计文档、初始化建议和初始化后 `module-split.json` 的模块级追溯字段中保留 `OPEN-*` 追溯。
- **步骤B3**：`architect` 必须先输出设计文档和初始化建议，不得在项目结构初始化完成前输出正式 `module-split.json`。固定输出：
  - `.superlooper/context/<session_id>/design/architecture.md`
  - `.superlooper/context/<session_id>/design/tech-stack.md`
  - `.superlooper/context/<session_id>/design/project-profile.md`
  - `.superlooper/context/<session_id>/design/initialization-advice.md`
- **步骤B4（默认 standard 自动推进）**：设计文档生成后，主调度器必须读取 `.superlooper/reports/<session_id>/upstream_alignment.md` 或 architect 输出中的上游自校对状态。若 `upstream_alignment_status=PASS`，不得默认停止给用户审核完整设计文档，必须根据 `initialization-advice.md` 的推荐分类、版本和项目根目录调用 `scripts/initialize_project_structure.py` 自动初始化项目结构。
- **步骤B4.0（设计未通过回退）**：用户审核设计未通过或自然语言表达设计不符合、需要重新设计时，必须先归一化。若 `project_initialized=false`，归一化为 **“设计未通过，按反馈重新设计”** 内部动作，主调度器必须把反馈写入 `.superlooper/reports/<session_id>/design_feedback.md`，更新 session state 的 `active_feedback_report`、`rollback_target_phase=design` 与 `change_request_count`，再重新调用 `architect` 输出设计文档；若 `project_initialized=true`，不得直接覆盖设计、模块拆分或下游产物，必须归一化为 **“需求变更，执行影响分析”** 并进入深层变更影响分析。
- **步骤B4.1（strict_review 设计审核）**：当 `workflow_mode=strict_review` 时，设计文档生成后必须停止执行，要求用户审核设计内容；审核通过后，再按旧流程要求用户选择初始化项目分类和版本。
- **步骤B4.2（strict_review 初始化握手）**：`strict_review` 模式下，用户选择项目分类后必须继续输出版本选择握手；用户完成项目分类和版本选择后，才调用 `scripts/initialize_project_structure.py`。
- **步骤B4.3**：项目结构初始化成功并写入 `initialization_report.json` 后，才允许 `architect` 基于已审核 PRD、已审核 UI 产物和初始化后的实际项目结构生成 `.superlooper/manifests/<session_id>/module-split.json`。
- **步骤B4.4**：使用 `schemas/module-split.schema.json` 与 `scripts/validate_miao_contracts.py --scope module-split` 对 `module-split.json` 做结构校验。若校验失败，输出错误并终止。
- **步骤B5**：`standard` 模式下，模块拆分清单校验通过后自动进入流程五准备执行摘要；`strict_review` 模式下必须停止并要求用户审核模块拆分内容，审核通过后继续流程五。

### 流程五：执行清单与动态 agent 准备

- **步骤C1**：进入流程五时，主会话先确认 `.superlooper/state/<session_id>.json` 中 `current_phase=run`、`phase_status` 为 `pending` 或 `running`、`project_initialized=true`、`initialization_report` 指向的报告存在、`ui_status=APPROVED`、`ui_artifacts_validated=true`、UI 固定产物和设计固定产物存在，再读取 `.superlooper/manifests/<session_id>/module-split.json`。`standard` 模式由流程四自动进入；`strict_review` 模式由用户回复“继续任务”或“生成执行清单”后进入。
- **步骤C2**：为每个模块生成一个 `mod_<module_id>` 编码节点，并确保对应 agent 为 `module_<module_id>`。
- **步骤C3**：若 `.superlooper/agents/<session_id>/module_<module_id>.md` 不存在，复用插件静态 `agents/developer.md` 模板动态生成运行时源文件。`developer.md` 只是动态 `module_*` 编码子代理模板，不作为实际编码 agent 直接调度；生成文件必须保留模板主体，frontmatter `name` 必须改为 `module_<module_id>`，frontmatter `description` 只能来自当前模块描述，正文必须写入 `Runtime Module Constraints` 约束块，列出当前模块的 `module_id`、`target_files`、`file_roles`、追溯编号、测试重点和禁止输入输出边界，不得引入未在模块 payload 中出现的新职责。
- **步骤C4**：将 `.superlooper/agents/<session_id>/module_<module_id>.md` 同步注册到 `.claude/agents/generated/superlooper/<session_id>/module_<module_id>.md`，两处内容必须一致，不得把动态模块 agent 直接写入插件静态 `agents/` 目录。
- **步骤C5**：追加质量门禁节点：
  - `task_code_review`，agent 固定为 `code-reviewer`，依赖所有 `mod_*`。
  - `task_merge`，agent 固定为 `system_merger`，只依赖 `task_code_review`。
  - `task_integration_test`，agent 固定为 `tester`，只依赖 `task_merge`。
  - `task_apply_to_workspace`，agent 固定为 `workspace_applier`，只依赖 `task_integration_test`。
- **步骤C6**：写入 `.superlooper/manifests/<session_id>/execution_manifest.json`，`context` 必须包含 `runtime_agents_path` 与 `registered_agents_path`。每个 `mod_*` 节点的 `payload` 必须是 object，必须承接 `module-split.json` 中当前模块对象和设计文档，只包含当前模块执行所需信息：`session_id`、`module_id`、`module_payload`、`design_docs_path`、`project_profile_path`、`module_split_path`、`execution_manifest_path`、`output_dir`、`artifact_manifest_path`、`target_files`、`file_roles`、`requirement_refs`、`decision_refs`、`open_question_refs`、`acceptance_refs`、`test_focus`、`forbidden_inputs`、`forbidden_outputs`。其中 `requirement_refs`、`decision_refs`、`open_question_refs` 与 `acceptance_refs` 只允许包含与当前模块相关的 `REQ-*`、`DEC-*`、`OPEN-*`、`AC-*` 编号、影响范围和默认处理方式；不得把整份原始需求文档、未筛选 PRD 或未筛选的全局问题透传给模块节点。
- **步骤C6.1**：进入执行清单校验前，必须检查不同模块的 `target_files` 是否存在重复路径。若同一路径被多个模块声明，说明模块边界不满足并行编码条件，必须停止执行清单阶段，要求返回设计结果调整模块边界，不得启动并行开发。
- **步骤C7**：使用 `schemas/execution-manifest.schema.json` 与 `scripts/validate_miao_contracts.py` 校验 Manifest、动态 agent 双层目录、frontmatter 和模块目标文件边界。若校验失败，输出错误并终止。
- **步骤C8**：调用 `scripts/build_execution_summary.py --workspace-root <workspace_root> --session-id <session_id>` 生成 `.superlooper/reports/<session_id>/execution_summary.md`，再调用 `scripts/validate_miao_contracts.py --scope execution-summary` 校验。`execution_summary_status=READY_FOR_APPROVAL` 时必须停止并输出固定握手消息：

> 「【执行摘要阶段完成】执行摘要已输出至 `.superlooper/reports/<session_id>/execution_summary.md`，包含项目类型、模块数量、目标文件数量、风险项、上游自校对状态和执行门禁结果。请审核摘要内容。审核通过后，请回复 **“按此执行”**；如不通过，请回复 **“执行摘要未通过，返回修正”**。」

- **步骤C8.1（strict_review Manifest 审核）**：当 `workflow_mode=strict_review` 时，主调度器可额外输出完整 Manifest 预览，并继续接受 **“执行”** 或 **“开始并行开发”** 作为高级审核通过动作；默认 `standard` 模式不得要求用户审核完整 Manifest。

### 上游自校对与受控 loop 协议

- 下游 agent 必须对上游产物输出 `upstream_alignment_status`，取值只允许 `PASS`、`FAIL` 或 `BLOCKED`。
- `PASS` 表示当前产物已对齐上游基线且 `mismatch_count=0`，主调度器继续执行并进入 validator 校验。
- `FAIL` 表示发现可自动修正的不一致，必须写明 `loop_required=true`、`loop_target_phase` 和不一致清单；主调度器在 `loop_policy.max_auto_loop_per_phase` 内写入 feedback report 并回到目标阶段重生成。
- `BLOCKED` 表示需要用户决策，必须列出 `blocking_decisions`；主调度器停止自动推进，不得猜测修正。
- 任一阶段达到自动 loop 上限后，必须停止并升级人工处理，不得无限重试。

### 深层阶段受控变更协议

- 当流程已进入初始化完成后、执行清单、编码、审查、合并、测试、应用或需求反向校对阶段，用户提出需求、UI 或设计变更时，必须归一化为 **“需求变更，执行影响分析”** 内部动作。
- 主调度器必须将反馈写入 `.superlooper/reports/<session_id>/change_feedback.md`，调用 `impact-analyzer` 读取 PRD、UI 产物、设计、`module-split.json`、`execution_manifest.json` 和现有报告，输出 `.superlooper/reports/<session_id>/change_impact_report.md`。
- 主调度器必须调用 `scripts/validate_miao_contracts.py --scope change-impact-report` 校验影响分析报告，并把 `change_impact_report`、`invalidated_artifacts`、`rollback_target_phase`、`active_feedback_report` 与 `change_request_count` 写入 session state。
- 影响分析完成后必须停止，等待用户回复 **“影响分析通过，执行局部重跑”** 或 **“影响分析不通过，人工处理”**。未获得该回复前，不得重写 PRD、设计、Manifest、模块产物或目标工作区文件。
- 局部重跑只能覆盖 `change_impact_report.md` 中声明的 `rollback_target_phase`、`affected_artifacts` 和 `affected_modules`；不得粗暴从 `/spl` 全流程重启。

### 流程六：模块实现与代码审查门禁

- **步骤D1**：用户回复“按此执行”后，主调度器必须调用 `scripts/resume_session.py --user-input "按此执行"` 二次校验 `execution_summary.md`，确认 state 已推进为 `run/running` 后，才读取 `.superlooper/manifests/<session_id>/execution_manifest.json` 并启动并行开发。`strict_review` 模式下，“执行”或“开始并行开发”也必须先经过执行摘要门禁。
- **步骤D2**：同时启动所有 `mod_*` 编码节点。每个节点只读取自己的 `payload`、设计上下文、`project-profile.md`、`module-split.json` 中自己的模块对象、Manifest 当前节点，以及 Manifest 中下发到本模块的 `DEC-*`、`OPEN-*` 编号和默认处理方式；不读取原始需求文档、其他模块 payload 或其他模块输出目录。
- **步骤D3**：每个 `mod_*` 节点必须把产物写入 `.superlooper/outputs/<session_id>/<module_id>/`，并生成 `artifact_manifest.json`。产物路径必须来自当前模块 `target_files`，并通过 `artifact_manifest.json` 支撑后续 `code-reviewer`、`system_merger`、`tester`、`workspace_applier` 消费。
- **步骤D4**：所有模块节点完成后，使用 `schemas/artifact-manifest.schema.json` 与 `scripts/validate_miao_contracts.py` 校验所有模块产物、目标文件边界和未声明文件。
- **步骤D5**：自动启动 `code-reviewer`，审查 `.superlooper/outputs/<session_id>/` 中所有模块产物和 `artifact_manifest.json`，并核对模块产物是否落实 Manifest 下发的相关 `DEC-*` 约束与 `OPEN-*` 默认处理方式。
- **步骤D5.1**：`code-reviewer` 完成后，主调度器必须读取 `.superlooper/reports/<session_id>/code_review_report.md` 的第一个机器可读 `yaml` 代码块，也可调用 `scripts/validate_miao_contracts.py --scope code-review-report` 做机器校验。合法 `code_review_status` 只允许为 `PASS` 或 `FAIL`；若报告缺失、状态块缺失、状态非法、正文结论与状态块矛盾、`blocker_count` 不为 `0` 或 `blocking_major_count` 不为 `0`，必须停止，不得进入 `task_merge`。只有 `code_review_status=PASS` 时，才允许继续步骤D6。
- **步骤D5.2（代码审查返工）**：若 `code_review_status=FAIL`，用户回复 `代码审查未通过，返回修正` 后，主调度器必须调用 `scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "代码审查未通过，返回修正：<反馈内容>"`。脚本必须校验 `code_review_report.md` 为 `FAIL`，写入 `code_review_feedback.md`，设置 `rollback_target_phase=run` 和下游 `invalidated_artifacts`，只回到模块修正与代码审查链路，不得进入 merge、test、apply 或重启完整 `/spl`。

### 流程七：合并、测试、应用与交付报告

- **步骤D6**：审查通过后，自动执行 `task_merge`，调用 `system_merger` 运行 `scripts/merge_artifacts.py`。
- **步骤D6.1**：`system_merger` 完成后，主调度器必须读取 `.superlooper/reports/<session_id>/merge_report.json`。若报告缺失、JSON 不可解析、`status` 不为 `success`、`session_id` 与当前会话不一致，必须停止，不得进入 `task_integration_test`。
- **步骤D7**：合并完成后，自动启动 `tester`，以 `.superlooper/merged/<session_id>/` 为测试对象执行集成测试与契约测试，并覆盖 PRD、设计文档和 Manifest 中引用的相关 `DEC-*` / `OPEN-*` 验收依据。
- **步骤D7.1**：`tester` 完成后，主调度器必须读取 `.superlooper/reports/<session_id>/test_report.md` 的第一个机器可读 `yaml` 代码块，也可调用 `scripts/validate_miao_contracts.py --scope test-report` 做机器校验。合法 `test_status` 只允许为 `PASS` 或 `FAIL`；若报告缺失、状态块缺失、状态非法、正文结论与状态块矛盾，必须停止，不得进入 `task_apply_to_workspace`。只有 `test_status=PASS` 时，才允许继续步骤D8。
- **步骤D7.2（测试返工）**：若 `test_status=FAIL`，用户回复 `测试未通过，返回修正` 后，主调度器必须调用 `scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "测试未通过，返回修正：<反馈内容>"`。脚本必须校验 `test_report.md` 为 `FAIL`，写入 `test_feedback.md`，设置 `rollback_target_phase=run` 和下游 `invalidated_artifacts`，只回到模块修正、merge 和 test 链路，不得进入 apply 或重启完整 `/spl`。
- **步骤D8**：集成测试通过后，自动启动 `workspace_applier`，调用 `scripts/apply_to_workspace.py` 将 `.superlooper/merged/<session_id>/` 中通过合并报告声明的文件应用到当前目标项目根目录；若目标根目录存在同路径不同内容文件，必须停止并输出冲突报告，不得静默覆盖。
- **步骤D8.1**：`workspace_applier` 完成后，主调度器必须读取 `.superlooper/reports/<session_id>/apply_report.json` 或 `.superlooper/reports/<session_id>/apply_conflict_report.json`，也可调用 `scripts/validate_miao_contracts.py --scope apply-report` 做机器校验。只有 `apply_report.json` 存在、JSON 可解析、`status=success`、`session_id` 与当前会话一致、`workspace_validation.status=PASS`、`failed_file_count=0` 且 `failures=[]` 时，才允许继续生成 session report；若存在 `apply_conflict_report.json`、脚本返回非 0 或应用后工作区验证失败，必须输出冲突或失败原因，不得输出“已完成应用”。
- **步骤D8.1.1（应用返工）**：若存在 `apply_conflict_report.json`，用户必须先基于报告确认具体 `--overwrite-file <relative_path>`、确认全量 `--overwrite-existing` 或人工处理冲突；用户回复 `应用冲突已处理，重新应用` 后，主调度器必须调用 `scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "应用冲突已处理，重新应用"`。脚本只允许把 state 推回 `run/pending` 并要求重新调用 `workspace_applier`，不得直接生成 session report 或最终完成结论。若 `apply_report.json.workspace_validation` 失败，`continue_current_flow` 必须保持阻断并输出验证失败项。
- **步骤D8.2**：`apply_report.json` 校验通过后，调用 `scripts/build_session_report.py` 生成 `.superlooper/reports/<session_id>/session_report.md`，并确认报告包含 Workspace Validation 摘要。session report 生成后不得直接输出最终完成结论。
- **步骤D8.3**：自动启动 `requirement-verifier`，对照 `.superlooper/context/<session_id>/prd.md`、`test_report.md`、`apply_report.json`、`session_report.md`、`module-split.json` 和 `execution_manifest.json` 生成 `.superlooper/reports/<session_id>/requirement_alignment_report.md`。
- **步骤D8.4**：主调度器必须读取 `requirement_alignment_report.md` 的第一个机器可读 `yaml` 代码块，也可调用 `scripts/validate_miao_contracts.py --scope requirement-alignment-report` 做机器校验。合法 `requirement_alignment_status` 只允许为 `PASS` 或 `FAIL`；只有 `requirement_alignment_status=PASS`、`unmet_requirement_count=0` 且 `unchecked_acceptance_count=0` 时，才允许进入最终完成握手。
- **步骤D8.5**：需求校对通过后必须停止并输出固定握手消息：`【需求反向校对完成】已根据 PRD.md 逐项校对实现、测试和交付报告。请审核 requirement_alignment_report.md。请回复 “需求校对通过，完成交付” 或 “需求校对未通过，返回修正”。`
- **步骤D8.5.1（需求校对返工）**：用户回复 `需求校对未通过，返回修正` 后，主调度器必须调用 `scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "需求校对未通过，返回修正：<反馈内容>"`。脚本必须写入 `change_feedback.md`，设置 `rollback_target_phase=requirement_alignment`，并阻断为等待 `impact-analyzer` 输出 `change_impact_report.md`；未校验并审核影响分析前，不得重写下游产物。
- **步骤D8.5.2（影响分析后局部重跑）**：用户回复 `影响分析通过，执行局部重跑` 后，主调度器必须调用 `scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "影响分析通过，执行局部重跑"`。脚本必须重新校验 `change_impact_report.md` 为 `PASS` 且 `local_rerun_allowed=true`，再按报告中的 `rollback_target_phase` 推回合法阶段，并保留 `invalidated_artifacts`；不得从 `/spl` 全流程重启。
- **步骤D8.6**：用户回复 `需求校对通过，完成交付` 后，主调度器必须调用 `scripts/resume_session.py --workspace-root <workspace_root> --session-id <session_id> --user-input "需求校对通过，完成交付"`，由脚本重新校验 `requirement_alignment_report.md` 为 `PASS`、`unmet_requirement_count=0`、`unchecked_acceptance_count=0` 并推进到 `report/passed` 后，才允许进入步骤D9并输出最终验收报告；不得直接写 state 绕过该门禁。
- **步骤D9**：输出最终验收报告，报告必须包含命令输出、合并报告路径、测试报告路径、应用报告路径、需求反向校对报告路径、失败项和验收结论。

## 3. `.superlooper` 运行目录契约

| 路径 | 说明 |
| --- | --- |
| `.superlooper/context/<session_id>/prd.md` | 需求分析阶段输出的 PRD |
| `.superlooper/context/<session_id>/ui/ui-spec.md` | UI 设计规格 |
| `.superlooper/context/<session_id>/ui/page-map.md` | 页面地图 |
| `.superlooper/context/<session_id>/ui/interaction-flow.md` | UI 交互流程 |
| `.superlooper/context/<session_id>/ui/ui-handoff.md` | 供 architect 必读的 UI 交付说明 |
| `.superlooper/context/<session_id>/ui/preview.html` | 单文件 HTML 预览原型 |
| `.superlooper/context/<session_id>/design/` | 架构设计阶段输出的设计文档 |
| `.superlooper/manifests/<session_id>/module-split.json` | 模块拆分清单 |
| `.superlooper/manifests/<session_id>/execution_manifest.json` | 执行清单 |
| `.superlooper/agents/<session_id>/module_<module_id>.md` | 动态模块 agent 的运行时源文件和审计副本 |
| `.claude/agents/generated/superlooper/<session_id>/module_<module_id>.md` | 动态模块 agent 的 Claude Code 注册入口 |
| `.superlooper/outputs/<session_id>/<module_id>/` | 单个模块 agent 的产物目录 |
| `.superlooper/outputs/<session_id>/<module_id>/artifact_manifest.json` | 单个模块的产物声明 |
| `.superlooper/merged/<session_id>/` | 合并后的完整目标项目 |
| `.superlooper/test_workspace/<session_id>/` | 合并产物不是完整工程时的临时集成测试工作区 |
| `.superlooper/reports/<session_id>/initialization_report.json` | 项目结构初始化成功报告 |
| `.superlooper/reports/<session_id>/initialization_conflict_report.json` | 项目结构初始化冲突报告 |
| `.superlooper/reports/<session_id>/upstream_alignment.md` | 下游产物对上游产物的自校对报告 |
| `.superlooper/reports/<session_id>/execution_summary.md` | 默认 standard 模式执行前人工审核摘要 |
| `.superlooper/reports/<session_id>/execution_summary_feedback.md` | 执行摘要审核未通过反馈记录 |
| `.superlooper/reports/<session_id>/prd_feedback.md` | PRD 审核未通过反馈记录 |
| `.superlooper/reports/<session_id>/ui_feedback.md` | UI 审核未通过反馈记录 |
| `.superlooper/reports/<session_id>/design_feedback.md` | 设计审核未通过反馈记录 |
| `.superlooper/reports/<session_id>/change_feedback.md` | 深层阶段需求或设计变更反馈记录 |
| `.superlooper/reports/<session_id>/change_impact_report.md` | 深层阶段变更影响分析报告 |
| `.superlooper/reports/<session_id>/code_review_report.md` | 代码审查报告 |
| `.superlooper/reports/<session_id>/code_review_feedback.md` | 代码审查失败后的用户返工反馈 |
| `.superlooper/reports/<session_id>/merge_report.json` | 合并报告 |
| `.superlooper/reports/<session_id>/conflict_report.json` | 合并冲突报告 |
| `.superlooper/reports/<session_id>/test_report.md` | 集成测试报告 |
| `.superlooper/reports/<session_id>/test_feedback.md` | 测试失败后的用户返工反馈 |
| `.superlooper/reports/<session_id>/apply_report.json` | 应用到目标项目根目录的成功报告 |
| `.superlooper/reports/<session_id>/apply_conflict_report.json` | 应用到目标项目根目录的冲突报告 |
| `.superlooper/reports/<session_id>/session_report.md` | 统一交付报告 |
| `.superlooper/reports/<session_id>/requirement_alignment_report.md` | PRD 反向需求校对报告 |

## 4. 并行拆分铁律

- 若需求中有明确并列模块，则这些模块必须拆分为独立节点，编码节点 `depends_on` 为空。
- 每个编码节点的 `agent` 字段必须匹配 `.superlooper/agents/<session_id>/module_<module_id>.md` 与 `.claude/agents/generated/superlooper/<session_id>/module_<module_id>.md`。
- 每个动态 `module_*` agent 文件必须包含 `Runtime Module Constraints` 正文约束块，且该约束块必须与当前模块 payload 的模块 ID、目标文件、文件角色、追溯编号、测试重点和禁止输入输出边界一致。
- `mod_*` 的 `payload` 字段必须是 object，来自 PRD、设计文档、`module-split.json` 当前模块对象、模块级上下文，以及模块相关的 `DEC-*` / `OPEN-*` 编号和默认处理方式，不允许直接透传整份原始需求文档或未筛选 PRD。
- 不同模块的 `target_files` 不得声明同一路径；一旦重复，必须在执行清单阶段阻断，不能留到并行编码或合并阶段处理。
- 每个模块产物必须通过 `artifact_manifest.json` 声明，未声明文件不得合并。
- 每个模块生成的真实代码文件必须保持目标项目根目录相对路径，例如 Java 项目使用 `src/main/java/...` 与 `src/main/resources/...`，Go 项目使用 `cmd/...`、`internal/...`、`pkg/...`，Python 项目使用项目既有包目录或 `tests/...`。
- Java 后端项目必须按标准目录设计：`controller` 为控制层，`service` 为服务接口层，`service/impl` 为服务实现层，`dao` 为数据库映射层并与 `src/main/resources/mapper/***-mapper.xml` 对应，`module` 下只允许 `beans`、`common`、`aop`、`core`、`vo`、`security`、`log` 子目录，`utils` 下只允许 `inner`、`outer` 子目录。
- `artifact_manifest.json` 的 `produced_files[].path` 是相对于目标项目根目录的路径；`module_*` 只是在 `.superlooper/outputs/<session_id>/<module_id>/` 下镜像这些相对路径。

## 5. Manifest 输出格式强制约束

正式 `execution_manifest.json` 必须是合法 JSON，不允许注释、占位符或通配符依赖。

### 5.1 动态生成规则

`mod_*` 编码节点必须从 `.superlooper/manifests/<session_id>/module-split.json` 的 `modules` 数组动态生成，不允许把示例模块名写死到正式 Manifest。

模块命名必须遵循语义化规则：

- `modules[].id` 必须由模块名称生成可读语义 slug，使用小写字母、数字和下划线 `_`。
- 禁止使用 `feature_a`、`feature_b`、`module_a`、`module_b` 这类无业务语义的排序占位名作为正式模块 ID。
- 禁止在 `modules[].id` 中使用连字符 `-`；`module_feature-a` 这类 agent 名称不合法。
- 若模块名称为中文，先按业务含义翻译成英文语义短语，再转换为下划线格式。

| 来源字段 | 生成字段 | 规则 |
| --- | --- | --- |
| `modules[].id` | `dag.nodes[].id` | 生成 `mod_<module_id>` |
| `modules[].id` | `dag.nodes[].agent` | 生成 `module_<module_id>` |
| `modules[].id` | `.superlooper/agents/<session_id>/module_<module_id>.md` | 生成动态 agent 运行时源文件 |
| `modules[].id` | `.claude/agents/generated/superlooper/<session_id>/module_<module_id>.md` | 同步生成 Claude Code 注册入口 |
| `modules[]` | `dag.nodes[].payload` | 生成包含 `session_id`、模块职责、目标文件和执行锚点的 object |
| 所有 `mod_*` 节点 | `task_code_review.depends_on` | 展开为全部真实模块节点 ID |

### 5.2 中性结构示例

以下示例只展示合法 JSON 结构，`auth_center` 与 `report_export` 是语义化示例名，不代表固定业务模块。正式文件必须由 `module-split.json` 动态生成真实模块名。

```json
{
  "session_id": "master-framework-20260714",
  "granularity": "module",
  "context": {
    "prd_path": ".superlooper/context/master-framework-20260714/prd.md",
    "design_docs_path": ".superlooper/context/master-framework-20260714/design/",
    "module_split_path": ".superlooper/manifests/master-framework-20260714/module-split.json",
    "agents_path": "agents/",
    "runtime_agents_path": ".superlooper/agents/master-framework-20260714/",
    "registered_agents_path": ".claude/agents/generated/superlooper/master-framework-20260714/",
    "outputs_path": ".superlooper/outputs/master-framework-20260714/",
    "merged_path": ".superlooper/merged/master-framework-20260714/",
    "reports_path": ".superlooper/reports/master-framework-20260714/"
  },
  "dag": {
    "nodes": [
      {
        "id": "mod_auth_center",
        "agent": "module_auth_center",
        "depends_on": [],
        "payload": {
          "session_id": "master-framework-20260714",
          "module_id": "auth_center",
          "module_payload": "实现 auth_center 模块",
          "design_docs_path": ".superlooper/context/master-framework-20260714/design/",
          "project_profile_path": ".superlooper/context/master-framework-20260714/design/project-profile.md",
          "module_split_path": ".superlooper/manifests/master-framework-20260714/module-split.json",
          "execution_manifest_path": ".superlooper/manifests/master-framework-20260714/execution_manifest.json",
          "output_dir": ".superlooper/outputs/master-framework-20260714/auth_center/",
          "artifact_manifest_path": ".superlooper/outputs/master-framework-20260714/auth_center/artifact_manifest.json",
          "target_files": ["src/main/java/com/example/controller/AuthController.java"],
          "file_roles": [],
          "requirement_refs": ["REQ-001"],
          "decision_refs": [],
          "open_question_refs": [],
          "acceptance_refs": ["AC-001"],
          "test_focus": ["登录鉴权成功路径"],
          "forbidden_inputs": ["原始需求文档", "其他模块 payload", "其他模块输出目录"],
          "forbidden_outputs": ["未包含在 target_files 中的文件", "目标项目根目录直接写入"]
        }
      },
      {
        "id": "mod_report_export",
        "agent": "module_report_export",
        "depends_on": [],
        "payload": {
          "session_id": "master-framework-20260714",
          "module_id": "report_export",
          "module_payload": "实现 report_export 模块",
          "design_docs_path": ".superlooper/context/master-framework-20260714/design/",
          "project_profile_path": ".superlooper/context/master-framework-20260714/design/project-profile.md",
          "module_split_path": ".superlooper/manifests/master-framework-20260714/module-split.json",
          "execution_manifest_path": ".superlooper/manifests/master-framework-20260714/execution_manifest.json",
          "output_dir": ".superlooper/outputs/master-framework-20260714/report_export/",
          "artifact_manifest_path": ".superlooper/outputs/master-framework-20260714/report_export/artifact_manifest.json",
          "target_files": ["src/main/java/com/example/controller/ReportExportController.java"],
          "file_roles": [],
          "requirement_refs": ["REQ-002"],
          "decision_refs": [],
          "open_question_refs": [],
          "acceptance_refs": ["AC-002"],
          "test_focus": ["报表导出成功路径"],
          "forbidden_inputs": ["原始需求文档", "其他模块 payload", "其他模块输出目录"],
          "forbidden_outputs": ["未包含在 target_files 中的文件", "目标项目根目录直接写入"]
        }
      },
      {
        "id": "task_code_review",
        "agent": "code-reviewer",
        "depends_on": ["mod_auth_center", "mod_report_export"],
        "payload": "审查所有并行模块节点代码"
      },
      {
        "id": "task_merge",
        "agent": "system_merger",
        "depends_on": ["task_code_review"],
        "payload": "执行 scripts/merge_artifacts.py 进行冲突消解"
      },
      {
        "id": "task_integration_test",
        "agent": "tester",
        "depends_on": ["task_merge"],
        "payload": "执行合并后集成测试与契约测试"
      },
      {
        "id": "task_apply_to_workspace",
        "agent": "workspace_applier",
        "depends_on": ["task_integration_test"],
        "payload": "将测试通过的合并产物应用到当前目标项目根目录"
      }
    ]
  }
}
```

## 6. 汇总节点强制规则

- `task_code_review` 必须依赖所有 `mod_*` 节点。
- `task_merge` 的 `agent` 固定为 `system_merger`。
- `task_merge.depends_on` 固定为 `["task_code_review"]`。
- `task_integration_test.depends_on` 固定为 `["task_merge"]`。
- `task_apply_to_workspace` 的 `agent` 固定为 `workspace_applier`。
- `task_apply_to_workspace.depends_on` 固定为 `["task_integration_test"]`。
- 合并脚本只读取 `.superlooper/outputs/<session_id>/` 中通过校验的模块产物。
- 应用脚本只读取 `.superlooper/reports/<session_id>/merge_report.json` 中声明的合并文件，并把文件应用到 `workspace_root` 对应相对路径。

## 7. Superpower 插件融合规则

当进入并行开发模式时，Superpower 只作为文件读写和工具执行基础设施，严禁其启动自身代理循环来规划任务。所有任务规划必须由主会话依据 `.superlooper/manifests/<session_id>/execution_manifest.json` 执行。

## 8. 实体化入口边界说明

- `commands/` 已提供 `/spl` 系列 slash command，作为插件安装后的实体触发入口。
- slash command 负责入口路由、阶段约束和必要脚本调用。
- `/spl:status` 只读查看 session 状态，不推进业务流程。
- `/spl:doctor` 只执行插件自检，不推进业务流程。
- `bin/spl` 只转发 doctor 自检，不定义第二套触发入口。
- 七流程主体语义仍以本文件为准。
- 不提供 `/spl:manifest`；执行清单生成归入 `/spl:run`。
- `hooks/`、`bin/`、`output-styles/`、`themes/`、`monitors/` 当前为结构预留，不参与主调度协议。
