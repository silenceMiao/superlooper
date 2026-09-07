# Superlooper 流程重量与握手机制只读分析 v3

## 用户问题

当前插件源码是否流程过重、即使针对新项目而言。中间流程中间握手次数是否过多、很多也看不明白是否符合不符合原始需求。是否应该让每个流程环节自己握手。比如设计设计完成之后自己握手需求、需求设计完成之后自己握手原始需求、编码完成之后自己握手设计；只读分析。

## 五步追问法结论

### 1. 你问的核心是什么

你不是在问“七流程是否完整”，而是在问：

> 当前 Superlooper 即使面向新项目，是否把用户拉进了过多人工审核点，导致用户难以判断“是否符合原始需求”。

结论：当前流程偏重，握手点偏多，且部分握手让用户承担了不该承担的校验责任。

### 2. 当前流程为什么显得重

当前协议把流程拆成七段，并在多个中间节点要求用户审核：

| 节点 | 当前握手 |
| --- | --- |
| PRD | 用户审核 PRD 后回复“通过，进入 UI 设计” |
| UI | 用户审核 UI 规格、交互、preview 后回复“UI设计通过，进入系统设计” |
| 设计文档 | 用户审核设计后回复“继续任务” |
| 初始化分类 | 用户选择 `java/go/springboot/pom/lua` |
| 初始化版本 | 用户选择版本 |
| module-split | 用户审核模块拆分后回复“继续任务” |
| execution_manifest | 用户审核执行清单后回复“执行” |
| requirement_alignment | 用户审核需求校对报告后回复“需求校对通过，完成交付” |

证据：

- 七流程职责边界：`skills/superlooper/SKILL.md:51-59`
- PRD 握手：`skills/superlooper/SKILL.md:81-85`
- UI 握手：`skills/superlooper/SKILL.md:98-104`
- 设计握手：`skills/superlooper/SKILL.md:116-120`
- 初始化分类/版本握手：`skills/superlooper/SKILL.md:122-135`
- module-split 握手：`skills/superlooper/SKILL.md:137-139`
- execution_manifest 握手：`skills/superlooper/SKILL.md:155-157`
- 最终需求校对握手：`skills/superlooper/SKILL.md:184-189`

### 3. 哪些握手是必要的，哪些过重

#### 必要握手

这些握手保留价值高：

| 握手 | 是否保留 | 原因 |
| --- | --- | --- |
| PRD 阻塞决策确认 | 保留 | 这是真正需要用户决策的业务方向问题。 |
| PRD 基线确认 | 保留，但要变轻 | PRD 是需求基线，必须有人确认。 |
| UI 方向确认 | 视项目而定 | 有前端/UI 时保留，无 UI 项目跳过。 |
| 最终需求校对确认 | 保留，但改成报告式 | 最终交付前需要用户知道是否达成需求。 |
| apply 冲突确认 | 保留 | 涉及覆盖用户工作区文件，必须人工确认。 |

#### 过重握手

这些握手对用户负担大，且用户不容易判断：

| 握手 | 问题 |
| --- | --- |
| 设计文档审核 | 用户通常难以判断架构是否真正符合 PRD、UI 和实现约束。 |
| module-split 审核 | 用户难以判断模块拆分、target_files、file_roles 是否合理。 |
| execution_manifest 审核 | 用户更难判断 DAG、动态 agent、payload 是否正确。 |
| 初始化分类/版本分两次问 | 新项目场景下可由 architect 建议默认值，再让用户一次确认。 |

判断：当前设计把“系统内部一致性校验”转嫁给了用户。

### 4. 是否应该让每个流程环节自己握手

方向正确，但术语上更准确地说，不是“每个流程自己握手”，而是：

> 每个下游 agent 在产出前，必须对自己的上游输入做“自校对”；只有发现业务决策、冲突、破坏性动作或高不确定性时，才请求用户握手。

也就是从：

```text
每产出一个中间文档 -> 用户审核 -> 下一步
```

改成：

```text
每个 agent 自校对上游契约 -> 机器/agent 校验通过 -> 自动进入下一步
只有遇到决策/冲突/不确定性 -> 用户握手
```

这个方向更适合新项目。

## 推荐的新握手模型

### 核心原则

| 原则 | 说明 |
| --- | --- |
| 用户只确认业务意图 | 不让用户审 DAG、payload、target_files 这类内部结构。 |
| agent 对上游负责 | PRD 对原始需求负责，UI 对 PRD 负责，设计对 PRD/UI 负责，编码对设计/Manifest 负责。 |
| 机器校验替代人工校验 | schema、validator、report status 替代“请用户看懂 JSON”。 |
| 只在风险点停下 | 决策、冲突、覆盖、需求偏差、不可恢复操作才停。 |

## 建议改成“四个用户握手点”

### 1. 需求基线握手

保留。

```text
原始需求 -> analyst -> PRD 自校对原始需求 -> 用户确认 PRD 基线
```

原因：

- PRD 是所有后续工作的业务基线。
- 当前 analyst 已经有状态块和阻塞决策机制：`agents/analyst.md:271-290`
- 关键决策看板只在阻塞 PRD 正确性时输出：`agents/analyst.md:292-333`

建议：

- PRD 不仅输出文档，还输出 `prd_alignment_to_raw_requirement`。
- 用户只看“需求是否被正确理解”，不看技术细节。

### 2. 体验/功能方向握手

有 UI 时保留，无 UI 项目跳过。

```text
PRD -> ui-architect -> UI 自校对 PRD -> 用户确认 UI/功能方向
```

当前 UI agent 已经具备质量扫描：

- UI 追溯 PRD：`agents/ui-architect.md:271-289`
- UI 产物供 architect 消费：`agents/ui-architect.md:247-260`
- UI 不得越界产出设计、代码、Manifest：`agents/ui-architect.md:262-269`

建议：

- 用户只审核 `preview.html` 和核心页面/任务流。
- UI 的 PRD 追溯结果由 agent 自己报告，不要求用户逐条审。

### 3. 执行前摘要握手

把“设计审核 + 初始化分类 + 初始化版本 + module-split 审核 + Manifest 审核”合并成一个握手。

```text
UI/PRD -> architect -> design + init advice + module split
-> validator 校验
-> 输出一页执行摘要
-> 用户确认“按此执行”
```

执行摘要只展示：

- 项目类型和版本
- 将创建/修改哪些关键文件
- 模块列表
- 风险和冲突
- 不可逆动作
- 测试策略

不展示：

- 完整 `execution_manifest.json`
- 动态 agent 文件
- payload 内部结构
- DAG 细节

证据说明当前这些内容已经过细：

- 设计阶段会生成设计和初始化建议：`skills/superlooper/SKILL.md:111-118`
- 初始化后才生成 module-split：`skills/superlooper/SKILL.md:135-139`
- 执行清单还要求用户审核 Manifest：`skills/superlooper/SKILL.md:155-157`
- 设计质量扫描已覆盖模块边界、PRD 追溯、文件落点、target_files 冲突：`agents/architect.md:234-249`

判断：既然 architect 和 validator 已经能检查这些，就不需要用户逐项握手。

### 4. 最终交付握手

保留，但改成更清晰的“需求符合性报告”。

```text
编码 -> code review -> merge -> test -> apply
-> requirement-verifier 对照 PRD
-> 用户确认交付
```

当前最终校对机制是合理的：

- requirement verifier 必须读取 PRD、测试报告、应用报告、session report、module-split、execution_manifest：`agents/requirement-verifier.md:10-18`
- PASS 必须满足所有 `REQ-*`、`AC-*`、`DEC-*`、`OPEN-*` 有状态和证据：`agents/requirement-verifier.md:36-38`
- 主协议要求最终报告通过后才进入交付握手：`skills/superlooper/SKILL.md:184-189`

建议：

- 最终用户只看：
  - 满足了哪些需求
  - 未满足哪些需求
  - 哪些验收未覆盖
  - 哪些文件被应用
  - 哪些测试通过
- 不要求用户审内部 Manifest。

## 推荐流程形态

### 当前流程

```text
需求文档
-> PRD
-> 用户审核
-> UI
-> 用户审核
-> 设计
-> 用户审核
-> 初始化分类
-> 用户选择
-> 初始化版本
-> 用户选择
-> module-split
-> 用户审核
-> execution_manifest
-> 用户审核
-> 编码
-> code review
-> merge
-> test
-> apply
-> requirement alignment
-> 用户审核
-> 完成交付
```

### 建议流程

```text
需求文档
-> PRD 自校对原始需求
-> 用户确认需求基线

-> UI/功能方向自校对 PRD
-> 用户确认体验/功能方向

-> 设计 + 初始化建议 + module-split + Manifest
-> 机器校验 + agent 自校对
-> 用户确认一页执行摘要

-> 编码自校对设计与 Manifest
-> code review 自校对模块产物
-> test 自校对 PRD/设计验收
-> apply

-> requirement-verifier 反向校对 PRD
-> 用户确认最终交付
```

## 对“每个流程环节自己握手”的判断

### 我赞成，但建议拆成两类

#### 1. 内部自校对

这个必须增强。

| 环节 | 自校对对象 |
| --- | --- |
| analyst | 原始需求 |
| ui-architect | PRD |
| architect | PRD + UI |
| module developer | design + module payload + Manifest |
| code-reviewer | module output + Manifest + design |
| tester | merge output + PRD + design + acceptance_refs |
| requirement-verifier | PRD + test + apply + session report |

当前部分已经有基础：

- analyst 有状态块：`agents/analyst.md:271-290`
- ui-architect 有质量扫描：`agents/ui-architect.md:271-289`
- architect 有设计质量扫描：`agents/architect.md:234-249`
- developer 有模块 checklist：`agents/developer.md:88-97`
- code-reviewer 有强制检查项：`agents/code-reviewer.md:42-78`
- tester 有报告要求：`agents/tester.md:74-84`

#### 2. 用户外部握手

这个要减少。

用户只参与：

1. 需求基线确认。
2. UI/功能方向确认。
3. 执行摘要确认。
4. 覆盖/冲突确认。
5. 最终交付确认。

## 当前最大问题

### 不是流程多，而是“用户审核对象不对”

现在用户被要求审核：

- 设计文档
- module-split
- execution_manifest
- requirement_alignment_report

其中后两个对普通用户不可读，对业务用户价值低。

真正应该给用户审核的是：

- 原始需求是否被理解对了。
- 功能/界面方向是否对。
- 执行会改什么、风险是什么。
- 最终需求是否满足。

## 是否即使新项目也过重

结论：是。

即使是 greenfield，新项目也不需要这么多用户停顿。

新项目中，以下内容可以默认自动推进：

| 当前环节 | 建议 |
| --- | --- |
| 初始化分类 | 由 architect 根据 PRD/项目类型建议，用户只在执行摘要中确认 |
| 初始化版本 | 给默认推荐值，用户只在执行摘要中确认 |
| module-split 审核 | 改为 agent 自校对 + validator 校验 |
| execution_manifest 审核 | 改为机器校验 + 执行摘要展示 |
| 设计文档审核 | 改为“关键设计摘要确认”，不是完整文档审核 |

## 建议的产品定位调整

当前像：

```text
严格项目管理型编排器
```

建议改成：

```text
默认自动推进、关键节点请求确认的 AI 工程流水线
```

也就是：

- 默认自动。
- 关键风险停下。
- 用户看摘要。
- agent 做一致性校对。
- validator 做结构校验。
- 最终 verifier 做需求闭环。

## 只读分析结论

### 结论一

当前 Superlooper 流程对新项目偏重。

### 结论二

中间握手次数偏多，尤其是设计、初始化、module-split、execution_manifest 连续握手，会打断流畅性。

### 结论三

很多中间产物确实让用户难以判断是否符合原始需求。这个判断应由 agent 自校对和 requirement verifier 承担。

### 结论四

建议保留“人工审核门”，但把审核对象从内部产物改成用户可理解摘要。

### 结论五

你的“每个环节自己校对上游”的方向正确。更准确的落地方式是：

```text
阶段自校对 + 机器校验 + 风险摘要
```

而不是每个阶段都让用户读完整文档再确认。

## 建议优先级

| 优先级 | 建议 |
| --- | --- |
| P0 | 合并设计、初始化、module-split、Manifest 为一个“执行前摘要握手”。 |
| P0 | 为 analyst、ui-architect、architect、developer、tester 增加标准化上游自校对状态块。 |
| P0 | 用户审核对象从完整内部产物改成摘要报告。 |
| P1 | 新项目默认自动选择初始化分类和版本，用户只确认摘要。 |
| P1 | Manifest 不再要求用户审核完整 JSON，只展示模块、文件、风险摘要。 |
| P1 | requirement-verifier 报告改成面向用户的需求符合性表格。 |
| P2 | 保留高级模式，让需要严控的项目启用逐阶段审核。 |

## 验收结果

### 完成内容

- 已整理用户问题和最新只读分析回复。
- 已按 Markdown 文档结构保存。
- 文档内容仅为分析，不包含源码修改方案的执行步骤。

### 证据路径和行号

- `README.md:222-238`
- `README.md:285-308`
- `skills/superlooper/SKILL.md:51-59`
- `skills/superlooper/SKILL.md:81-85`
- `skills/superlooper/SKILL.md:98-104`
- `skills/superlooper/SKILL.md:116-139`
- `skills/superlooper/SKILL.md:155-157`
- `skills/superlooper/SKILL.md:184-189`
- `commands/spl/prd.md:15-24`
- `commands/spl/ui.md:15-27`
- `commands/spl/design.md:15-34`
- `commands/spl/run.md:15-36`
- `configs/interaction-flow.json:52-171`
- `agents/analyst.md:271-290`
- `agents/ui-architect.md:271-289`
- `agents/architect.md:234-249`
- `agents/developer.md:88-97`
- `agents/code-reviewer.md:42-78`
- `agents/tester.md:74-84`
- `agents/requirement-verifier.md:36-38`

### 验收指标

| 指标 | 结果 |
| --- | --- |
| 文档格式 | Markdown |
| 是否包含原始问题 | 是 |
| 是否包含最新回复 | 是 |
| 是否包含五步追问法 | 是 |
| 是否包含证据路径和行号 | 是 |
| 是否保持只读分析口径 | 是 |
| 是否修改插件协议或源码 | 否 |

### 未执行项或风险说明

- 未运行 `claude plugin validate . --strict`，因为本次只新增分析文档，没有修改插件运行协议或源码。
- 未运行单元测试，原因同上。
- 本文档是流程产品分析，不等同于实现计划。
