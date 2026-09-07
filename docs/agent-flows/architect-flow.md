# Architect Flow 系统设计运行规格

本文件是 `agents/architect.md` 的内部设计流程规格，不是 Claude Code agent 文件，不包含 agent frontmatter，不被主调度器直接调用。

## 1. 定位与边界

`architect` 是 Superlooper AI 并行流程编排中的设计阶段 subagent。它的价值不是替代主调度器规划阶段，也不是替代 `developer` 编码，而是把已审核 PRD 转换为可审阅、可追溯、可拆分、可下发的设计基线。

本文件只约束 `architect` 的内部设计流程，不覆盖 `agents/architect.md` 的 payload、输出路径、输出格式和禁止事项。当本文件与 `skills/superlooper/SKILL.md` 冲突时，以主调度协议为准。

职责边界：`agents/architect.md` 是输出契约源，负责 payload、必读上下文、设计产物、模块拆分清单和禁止事项；本文件是内部设计流程源，负责设计顺序、设计分类、模块拆分判断和质量扫描。两者重复时，正式输出以 `agents/architect.md` 为准。

## 2. 设计输入基线

`architect` 必须以已审核 PRD 和已审核 UI 设计产物为输入基线，不得回到原始需求重新做需求分析。用户自然语言反馈由主调度器先归一化；归一化为 `设计未通过，按反馈重新设计` 且项目尚未初始化时，`architect` 只按 `feedback_report` 重写设计文档和初始化建议，不生成正式 `module-split.json`。

必须从 PRD 中读取并消费以下章节：

| PRD 内容 | 设计阶段处理方式 |
| --- | --- |
| 需求定义总览 | 映射为模块职责、接口能力、数据对象或流程节点 |
| 功能性需求 | 转换为模块边界、API 契约、流程设计和目标文件落点 |
| 非功能性需求 | 转换为性能、安全、可观测性、可维护性等设计约束 |
| 约束与合规要求 | 转换为架构边界、数据边界、权限边界和禁止实现项 |
| 验收标准 | 转换为模块级 `acceptance_refs` 与 `test_focus` |
| 需求追溯矩阵 | 作为模块拆分和设计引用的编号来源 |
| 决策记录 | 将 `CONFIRMED_BY_USER` 与 `DEFAULT_ACCEPTED` 的 `DEC-*` 转换为设计约束、模块边界或验收依据 |
| 非阻塞开放问题 | 对建议处理阶段包含 `architect` 的 `OPEN-*` 采用 PRD 默认处理方式，并在设计产物中保留追溯 |
| 范围边界 | `MUST_NOT` 不得进入设计范围、模块范围或目标文件落点 |

## 3. UI 交付物读取与约束映射

`architect` 必须读取 `ui_output_dir` 中的固定产物：`ui-spec.md`、`page-map.md`、`interaction-flow.md`、`ui-handoff.md`、`preview.html`。UI 产物缺失、未审核通过或 `ui-artifacts` 校验失败时，不得输出系统设计。

| UI 内容 | 系统设计阶段处理方式 |
| --- | --- |
| 页面清单和页面 ID | 映射为前端模块候选、路由候选和验收关注点 |
| 页面所需数据和动作 | 映射为 API 能力、命令、查询和权限边界 |
| 交互流程和状态矩阵 | 映射为核心流程、异常路径、幂等和错误响应 |
| UI handoff | 映射为模块边界、前端目标文件候选和测试关注点 |
| UI 页面、交互、组件和验收编号 | 映射为模块级 `ui_refs`、`interaction_refs`、`component_refs`、`ui_acceptance_refs` |
| preview HTML | 只作为审核原型参考，不作为生产代码直接合并 |

## 4. 设计阶段内部流程

以下流程是内部推演顺序，不是新增主调度阶段，不改变 `skills/superlooper/SKILL.md` 中的 B1-B5。

```text
PRD 基线读取
-> UI 交付物读取与约束映射
-> 项目画像扫描
-> 架构边界设计
-> 数据设计
-> API 与接口契约设计
-> 核心流程设计
-> 初始化建议
-> 若 project_initialized=true，再生成模块拆分清单
-> PRD/UI 到设计与模块拆分上游自校对
-> 设计质量扫描
```

## 3.1 输出物分类

固定输出物必须全部产出：

- `design_output_dir/architecture.md`
- `design_output_dir/tech-stack.md`
- `design_output_dir/project-profile.md`
- `design_output_dir/initialization-advice.md`
- `payload.module_split_path`，仅在 `project_initialized=true` 后产出
- `.superlooper/reports/<session_id>/upstream_alignment.md`，用于声明设计和模块拆分是否对齐 PRD/UI 上游基线

条件输出物仅在 PRD 或目标项目结构需要时产出，不得为空生成占位文件：

- `design_output_dir/db_ddl.sql`
- `design_output_dir/api-contract.yaml`
- `design_output_dir/process.md`

条件输出物作为 `design_docs_path` 下的设计上下文供后续 agent 读取，不展开为 `execution_manifest.json` 的独立字段。

## 4. 项目画像扫描

`architect` 必须扫描 `workspace_root` 下的目标项目结构，识别当前工程事实，不得凭空创建与项目不一致的源码根目录或测试根目录。

必须识别：

- 语言。
- 构建工具。
- 源码根目录。
- 测试根目录。
- 配置根目录。
- 包名或模块路径。
- 既有分层习惯。
- 数据访问方式。
- API 暴露方式。

输出到 `design_output_dir/project-profile.md`。

Java 后端项目必须在既有源码根目录、测试根目录和 `base_package` 内按以下标准层次输出文件落点：

| 层级 | 标准目录 |
| --- | --- |
| 控制层 | `src/main/java/<base_package>/controller/` |
| 服务层接口 | `src/main/java/<base_package>/service/` |
| 服务层实现 | `src/main/java/<base_package>/service/impl/` |
| 数据库映射层 | `src/main/java/<base_package>/dao/` |
| 模块层 | `src/main/java/<base_package>/module/{beans,common,aop,core,vo,security,log}/` |
| 工具层 | `src/main/java/<base_package>/utils/{inner,outer}/` |
| Mapper XML | `src/main/resources/mapper/` |

若现有工程结构与标准层次存在偏差，必须在 `project-profile.md` 中记录兼容策略和偏差原因，不得静默另起一套目录。

## 5. 架构边界设计

输出到 `design_output_dir/architecture.md`。

必须包含：

- 系统组件。
- 模块边界。
- 模块协作关系。
- 外部依赖。
- 数据流。
- 权限边界。
- 失败边界。
- 可观测边界。
- 与 `REQ-*`、`DEC-*`、`OPEN-*`、`AC-*` 的追溯关系。

架构设计只给出后续模块实现需要遵守的边界和契约，不编写业务代码，不生成类实现。

## 6. 数据设计

当 PRD 或现有项目结构表明需要数据库变更时，输出 `design_output_dir/db_ddl.sql`。

DDL 必须满足：

- 表名和字段名来自业务语义。
- 包含主键。
- 包含审计字段。
- 包含字段注释。
- 包含必要索引。
- 敏感字段说明存储边界。
- 通过注释或相邻设计文档映射到 `REQ-*`、`CON-*`、`NFR-*` 或 `AC-*`。

禁止设计依赖 SQL 字符串拼接的方案。

## 7. API 与接口契约设计

当项目存在外部接口或 PRD 要求 API 能力时，输出 `design_output_dir/api-contract.yaml`，格式使用 OpenAPI 3.0。

API 设计必须包含：

- 接口路径。
- 请求方法。
- 请求参数。
- 响应结构。
- 错误响应。
- 鉴权要求。
- 输入校验要求。
- 与 `REQ-*`、`DEC-*`、`OPEN-*`、`AC-*` 的追溯关系。

API 设计不得输出业务代码，不得替 `developer` 生成控制器实现。

## 8. 核心流程设计

当项目存在核心流程、状态流转、审批链路、批处理链路或跨系统协作时，输出 `design_output_dir/process.md`。

流程文档必须使用 Markdown + Mermaid，覆盖：

- P0 正常路径。
- 异常路径。
- 状态变更。
- 幂等或重复提交处理。
- 失败补偿或人工介入入口。
- 与 `AC-*` 的验收映射。

## 9. 模块拆分清单设计

项目结构初始化完成前必须先输出初始化建议，不得生成正式 `module-split.json`。项目结构初始化完成后，必须生成机器可读的 `module-split.json`，写入 payload 指定的 `module_split_path`。

模块拆分规则：

- 按业务能力拆分，不按 controller、service、dao 技术层机械拆分。
- 明确并列模块必须拆成独立模块。
- 每个模块 `id` 使用小写字母、数字和下划线。
- 禁止使用 `feature_a`、`feature_b`、`module_a`、`module_b` 作为正式模块 ID。
- 每个模块描述必须足够让 `developer` 只看模块 payload、设计上下文和 Manifest 节点工作。
- 每个模块如能确定目标文件，必须在 `target_files` 中列出目标后端项目根目录相对路径。
- 当 `project_profile.project_mode=brownfield-selective` 时，每个模块必须声明 `allowed_existing_files`、`forbidden_files`、`integration_points`、`test_commands` 和 `overwrite_policy`；`allowed_existing_files` 必须是 `target_files` 子集，`forbidden_files` 不得与 `target_files` 重叠，`overwrite_policy` 固定为 `block_by_default`。
- 不同模块的 `target_files` 不得声明同一路径；若多个模块需要修改同一文件，必须重新调整模块边界，指定唯一归属模块，或将共享改动拆为独立公共支撑模块，不得把冲突留到流程四、并行编码或合并流程处理。
- 当模块声明 `target_files` 且文件职责可确定时，必须同步声明 `file_roles`，路径必须与 `target_files` 保持一致。
- Java 后端项目必须为每个模块声明 `target_files`。
- 不允许把整份 PRD 或原始需求直接塞入单个模块 payload。

每个模块必须优先输出能确定的追溯字段；无相关编号时使用空数组或省略，不得编造编号。

| 字段 | 说明 |
| --- | --- |
| `requirement_refs` | 当前模块实现的 `REQ-*` 编号 |
| `decision_refs` | 当前模块必须遵守的 `DEC-*` 编号 |
| `open_question_refs` | 当前模块继承默认处理方式的 `OPEN-*` 编号 |
| `acceptance_refs` | 当前模块对应的 `AC-*` 编号 |
| `ui_refs` | 当前模块关联的 UI 页面编号 |
| `interaction_refs` | 当前模块关联的 UI 交互编号 |
| `component_refs` | 当前模块关联的 UI 组件编号 |
| `ui_acceptance_refs` | 当前模块关联的 UI 验收编号 |
| `allowed_existing_files` | 当前模块允许修改的既有目标文件，必须是 `target_files` 子集 |
| `forbidden_files` | 当前模块禁止创建或修改的目标项目相对路径 |
| `integration_points` | 当前模块与既有项目对接的服务、接口、配置或数据访问点 |
| `test_commands` | 当前模块在目标项目中优先执行的验证命令 |
| `overwrite_policy` | 当前模块覆盖策略，固定为 `block_by_default` |
| `test_focus` | 当前模块后续测试关注点 |
| `depends_on_modules` | 当前模块在设计语义上依赖的其他模块 ID；无依赖时使用空数组或省略 |

- `requirement_refs`、`decision_refs`、`open_question_refs`、`acceptance_refs` 必须来自已审核 PRD 中真实存在的编号；无相关编号时使用空数组或省略。
- `ui_refs`、`interaction_refs`、`component_refs`、`ui_acceptance_refs` 必须来自已审核 UI 产物中的真实页面、交互、组件和 UI 验收编号；无相关编号时使用空数组或省略。
- `test_focus` 必须描述后续测试关注点，禁止写入 `TODO`、`TBD`、`...`、`后续处理` 等占位内容。

`depends_on_modules` 只表达设计语义依赖，不改变流程五中并列编码节点默认并行的主调度规则。若依赖会造成并行开发不可安全执行，必须在设计文档中说明原因并让主会话人工审核，不得由 `architect` 自行改写执行链路。

## 10. 设计质量扫描

写入设计产物前，必须完成以下检查：

| 检查组 | 通过标准 |
| --- | --- |
| 主协议边界检查 | 未新增主阶段，未生成 `execution_manifest.json`，未创建动态 agent，未写业务代码 |
| PRD 追溯检查 | 每个模块能追溯到 `REQ-*` 或明确设计依据 |
| 决策落实检查 | `DEC-*` 已转为设计约束、模块边界或验收依据 |
| 开放问题检查 | `OPEN-*` 已按默认处理方式处理，并保留追溯 |
| 范围边界检查 | `MUST_NOT` 未进入模块范围、API、DDL 或目标文件 |
| 文件落点检查 | `target_files` 使用目标后端项目根目录相对路径 |
| 模块边界冲突检查 | 不同模块的 `target_files` 不存在重复路径 |
| Java 分层检查 | Java 文件落点符合标准目录 |
| 可测试性检查 | P0 模块具备 `acceptance_refs` 或 `test_focus` |
| UI 追溯检查 | 前端相关模块保留 `ui_refs`、`interaction_refs`、`component_refs`、`ui_acceptance_refs` |
| 存量边界检查 | `brownfield-selective` 模块声明允许修改文件、禁止文件、集成点、测试命令和 `block_by_default` 覆盖策略 |
| 契约污染检查 | 不残留 `TODO`、`TBD`、`...`、示例模块名或占位路径 |

## 11. 后续消费映射规则

`architect` 的设计产物必须让后续阶段能稳定消费：

| 后续阶段 | 消费内容 | architect 输出要求 |
| --- | --- | --- |
| 主调度器流程四 | `module-split.json` | 模块 ID、描述、目标文件、追溯字段可直接生成 Manifest payload |
| `developer` / `module_*` | Manifest payload 与设计上下文 | 模块职责、目标文件和约束边界清晰，不需要读取原始需求文档 |
| `tester` | 设计文档、接口契约、流程文档、验收引用 | `AC-*` 与 `test_focus` 能成为测试依据 |
| `code-reviewer` | 模块产物与 Manifest payload | `DEC-*` 与 `OPEN-*` 能成为审查检查项 |

## 12. 禁止事项

- 不做需求分析。
- 不生成 PRD。
- 不读取原始需求文档，除非主会话明确要求补充核对。
- 不把 `OPEN-*` 重新升级为流程三阻塞。
- 不生成 `execution_manifest.json`。
- 不创建动态 `module_*` agent。
- 不编写业务代码。
- 不执行单元测试、集成测试或端到端测试。
- 不修改目标项目根目录业务文件。
