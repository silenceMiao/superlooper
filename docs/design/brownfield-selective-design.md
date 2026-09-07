# Brownfield Selective 设计

## 设计目标

`brownfield-selective` 用于支持存量项目中的受控局部改造。它要求先只读识别项目结构，再按模块声明的允许既有文件、禁止文件、集成点和测试命令生成模块产物，默认不覆盖已有差异文件。

本设计不把 brownfield 作为默认模式，不削弱现有 apply 安全策略。

## 第一性原理五步分析

### 1. 根本目标是什么

让 Superlooper 能安全服务存量项目，避免误扫描、误初始化、误覆盖和误改依赖。

### 2. 当前已完成什么

当前已增加 `project_mode=brownfield-selective`，并在 module-split、Manifest payload、动态 agent constraints、validator 和 apply 回归测试中落地模块级边界字段：`allowed_existing_files`、`forbidden_files`、`integration_points`、`test_commands`、`overwrite_policy`。

### 3. 为什么需要设计

brownfield 会接触真实已有代码、配置、依赖和测试命令。未先定义边界时，模块 agent 会误改公共配置、依赖版本、CI/CD 或未授权路径。

### 4. 排除什么

本设计不允许自动全仓扫描后直接改写项目，不允许默认覆盖已有文件，不允许自动升级依赖，不允许删除已有文件。当前实现不使用 project profile 级 glob 白名单作为强校验来源。

### 5. 成功判据是什么

当前最小实现的成功判据是：session 接收 `brownfield-selective`；模块可声明允许既有文件、禁止文件、集成点、测试命令和覆盖策略；Manifest 与 runtime constraints 透传这些字段；validator 阻断越界声明；apply 默认阻断差异覆盖不变。

完整扩展的成功判据是：brownfield 只能在用户明确选择后启用；项目画像记录允许路径和禁止路径；模块 target files 受 project profile 级 allowed scope 约束；依赖策略可审计。

## 当前已实施范围

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| session project mode | 已实施 | `session-state.schema.json`、`create_session.py`、`update_session.py` 接收 `brownfield-selective`。 |
| module-split 模块级字段 | 已实施 | 支持 `allowed_existing_files`、`forbidden_files`、`integration_points`、`test_commands`、`overwrite_policy`。 |
| Manifest payload 透传 | 已实施 | `generate_execution_manifest.py` 下发模块级 brownfield 字段。 |
| runtime agent constraints | 已实施 | `generate_runtime_agents.py` 写入模块级 brownfield 字段。 |
| validator 边界校验 | 已实施 | 校验 allowed/forbidden/overwrite policy。 |
| apply 默认阻断回归 | 已实施 | `brownfield-selective` 不放宽已有差异文件冲突阻断。 |
| project profile glob 白名单 | 未实施扩展 | `allowed_modify_paths`、`forbidden_modify_paths` 未进入 schema 强校验。 |
| dependency policy | 未实施扩展 | `dependency_policy` 未进入 schema、payload 或 validator。 |
| brownfield 字段条件必填 | 未实施扩展 | 当前字段存在时校验，未按 `project_mode` 强制每个模块必填。 |

## 模式定义

| 模式 | 含义 |
| --- | --- |
| `greenfield` | 默认模式，适合新项目或受控初始化项目。 |
| `brownfield` | 存量项目前端或结构读取模式，保持旧有语义。 |
| `brownfield-selective` | 存量项目受控局部改造，模块级声明允许既有文件和禁止文件。 |

## 入口条件

| 条件 | 当前最小实现 | 完整扩展目标 |
| --- | --- | --- |
| 用户确认 | session 可设置 `project_mode=brownfield-selective`。 | 必须由用户明确选择后启用。 |
| 只读扫描 | 由 architect 契约描述，不由脚本自动全仓扫描。 | 先读取项目结构、构建工具、源码根、测试根和配置根。 |
| 允许范围 | 当前使用模块级 `allowed_existing_files`。 | project profile 可声明 `allowed_modify_paths`。 |
| 禁止范围 | 当前使用模块级 `forbidden_files`。 | 配置、密钥、CI/CD、部署脚本默认进入 `forbidden_modify_paths`。 |
| 测试命令 | 当前使用模块级 `test_commands`。 | 从项目画像识别或由用户确认。 |
| 覆盖策略 | 当前固定 `block_by_default`。 | 保持 `block_by_default`。 |

## 当前模块拆分扩展

`module-split.json.modules[]` 使用模块级字段：

```json
{
  "target_files": ["src/main/java/com/example/report/ReportService.java"],
  "allowed_existing_files": ["src/main/java/com/example/report/ReportService.java"],
  "forbidden_files": ["src/main/resources/application.yml"],
  "integration_points": ["ReportRepository"],
  "test_commands": ["mvn test -Dtest=ReportServiceTest"],
  "overwrite_policy": "block_by_default"
}
```

字段规则：

| 字段 | 当前规则 |
| --- | --- |
| `allowed_existing_files` | 当前模块允许声明修改的既有文件，必须是 `target_files` 子集。 |
| `forbidden_files` | 当前模块禁止创建或修改的目标项目相对路径，不得与 `target_files` 重叠。 |
| `integration_points` | 当前模块与既有项目对接的服务、接口、配置或数据访问点。 |
| `test_commands` | 当前模块在目标项目中优先执行的验证命令。 |
| `overwrite_policy` | 固定为 `block_by_default`。 |

## 后续 Project Profile 扩展

以下 project profile 级字段属于未实施扩展：

```yaml
project_mode: brownfield-selective
source_roots:
  - src/main/java
test_roots:
  - src/test/java
config_roots:
  - src/main/resources
allowed_modify_paths:
  - src/main/java/com/example/report/**
forbidden_modify_paths:
  - src/main/resources/application.yml
  - .github/workflows/**
  - Dockerfile
test_commands:
  - mvn test
dependency_policy: reuse_existing
overwrite_policy: block_by_default
```

启用该扩展前，必须同步修改 schema、validator、architect、developer、Manifest 生成、runtime agent 生成、README 和测试。

## 执行清单扩展

`execution_manifest.json.dag.nodes[].payload` 当前承接字段：

| 字段 | 说明 | 当前状态 |
| --- | --- | --- |
| `allowed_existing_files` | 当前模块允许声明修改的既有文件。 | 已实施。 |
| `forbidden_files` | 当前模块禁止修改的文件。 | 已实施。 |
| `integration_points` | 当前模块允许对接的已有接口、服务或组件。 | 已实施。 |
| `test_commands` | 当前模块验证命令。 | 已实施。 |
| `overwrite_policy` | 默认 `block_by_default`。 | 已实施。 |
| `project_mode` | 模块 payload 固定标记 `brownfield-selective`。 | 未实施扩展。当前 session 和 module-split project profile 记录模式。 |

## 模块 agent 规则

模块 agent 必须遵守：

- 只读取 payload、项目画像、设计文档、module-split 当前模块对象和 execution manifest 当前节点。
- 只产出 `target_files` 中声明的路径。
- `allowed_existing_files` 只表示模块允许声明修改的既有文件，不表示 apply 阶段允许自动覆盖目标工作区已有不同内容文件。
- 不修改 `forbidden_files`。
- 不新增全局配置。
- 不升级依赖版本。
- 不修改 CI/CD、部署脚本或安全配置。
- 不删除已有文件。
- 需要越界时输出 `artifact_manifest.json.status=blocked`。

## Apply 策略

保持现有默认策略：

| 场景 | 处理 |
| --- | --- |
| 目标文件不存在 | 可创建。 |
| 目标文件存在且内容相同 | 可通过。 |
| 目标文件存在且内容不同 | 阻断，输出 conflict report。 |
| 用户授权单文件覆盖 | 使用 `--overwrite-file <relative_path>`。 |
| 用户授权全量覆盖 | 使用 `--overwrite-existing`。 |
| apply 后验证失败 | 阻断最终报告。 |

`brownfield-selective` 不改变上述策略。

## Validator 设计

| 校验 | 当前状态 |
| --- | --- |
| session state 接收 `brownfield-selective` | 已实施。 |
| module-split 字段类型 | 已实施。 |
| `allowed_existing_files` 是 `target_files` 子集 | 已实施。 |
| `forbidden_files` 不与 `target_files` 重叠 | 已实施。 |
| `overwrite_policy` 只允许 `block_by_default` | 已实施。 |
| execution manifest payload 承接模块级字段 | 已实施。 |
| dynamic agent constraints 包含模块级字段 | 已实施。 |
| project profile `allowed_modify_paths` 约束 `target_files` | 未实施扩展。 |
| `dependency_policy` 校验 | 未实施扩展。 |
| `project_mode=brownfield-selective` 时模块字段条件必填 | 未实施扩展。 |

## 与现有文件的联动

| 文件 | 影响 |
| --- | --- |
| `skills/superlooper/SKILL.md` | 当前未修改主体调度协议。 |
| `agents/architect.md` | 已增加存量项目模块级边界输出要求。 |
| `docs/agent-flows/architect-flow.md` | 已增加存量边界检查要求。 |
| `agents/developer.md` | 已增加 brownfield 模块越界阻断说明。 |
| `agents/workspace_applier.md` | 已说明 apply 默认阻断不因 brownfield-selective 放宽。 |
| `schemas/session-state.schema.json` | 已增加 `brownfield-selective`。 |
| `schemas/module-split.schema.json` | 已增加 brownfield 模块级字段。 |
| `scripts/generate_execution_manifest.py` | 已透传 brownfield 模块级字段。 |
| `scripts/generate_runtime_agents.py` | 已写入 brownfield runtime constraints。 |
| `scripts/validate_miao_contracts.py` | 已增加模块级边界校验。 |
| `tests/test_validate_contracts.py` | 已覆盖 forbidden path、allowed path 和 overwrite policy。 |
| `tests/test_apply_to_workspace.py` | 已覆盖 brownfield 覆盖阻断。 |

## 改善后的要点

- 存量项目进入模式可表达。
- 修改范围在模块级可审计。
- 默认不覆盖真实工作区差异文件。
- 测试命令可从模块传递到 tester。
- 依赖版本和全局配置不会被默认修改。

## 已实施范围与未实施扩展边界

当前已实施范围是模块级 `brownfield-selective` 边界契约，不是 project profile 级 glob 策略引擎。

未实施扩展包括：`allowed_modify_paths`、`forbidden_modify_paths`、`dependency_policy`、按 `project_mode` 条件强制每个模块必填 brownfield 字段、把 `project_mode` 注入每个 module payload、自动只读扫描生成项目画像。
