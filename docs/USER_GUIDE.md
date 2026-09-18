# Superlooper 用户指南

<!-- public-readme:start -->
Superlooper 是同时适用于 Claude Code 与 Codex 的 AI 并行编排插件。它把需求文档推进为 PRD、UI 设计、系统设计、并行实现、审查、测试与受控应用流程。

## 运行前提

两个平台都需要：

1. Python 3.9+。
2. `python` 命令在当前实际 Agent parent session 中可执行。
3. 目标项目目录允许创建 `.superlooper/` 运行数据。
4. Codex 完整工作流必须使用 `workspace-write`、non-ephemeral parent session。

Superlooper不会：

- 自动安装 Python；
- 修改系统 `PATH`；
- 扩大 sandbox 或工具权限；
- 静默覆盖工作区中的同路径不同内容文件。

## 快速开始

1. 添加已发布的 `superAI-marketplace`。
2. 安装 `superlooper`。
3. 在目标项目根目录运行 doctor。
4. 准备 `requirements.md` 后启动首个任务。

### Claude Code

```text
/plugin marketplace add silenceMiao/superAI-marketplace
/plugin install superlooper@superAI-marketplace
/superlooper:spl:doctor
/superlooper:spl requirements.md [--task-name "商城后台"]
```

### Codex

```text
codex plugin marketplace add silenceMiao/superAI-marketplace --ref main
codex plugin add superlooper@superAI-marketplace
$superlooper-doctor
$superlooper requirements.md [--task-name "商城后台"]
```

### 安装产物选择

普通用户使用 `superlooper-<version>-install.zip` 或已发布的 `superAI-marketplace`。`superlooper-<version>-source.zip` 用于源码审计和开发验证，不是普通用户安装入口。

### 安装与 Doctor

#### Claude Code

添加并安装已发布 Marketplace：

```text
/plugin marketplace add silenceMiao/superAI-marketplace
/plugin install superlooper@superAI-marketplace
```

安装完成后，在目标项目根目录运行：

```text
/superlooper:spl:doctor
```

检查已有 task 时可传入 `task_id`：

```text
/superlooper:spl:doctor <task_id>
```

#### Codex

添加并安装同一个已发布 Marketplace：

```text
codex plugin marketplace add silenceMiao/superAI-marketplace --ref main
codex plugin add superlooper@superAI-marketplace
```

完整 Codex workflow 使用 non-ephemeral、`workspace-write` parent session，以写入目标项目的 `.superlooper/` 运行时产物；`$superlooper-status` 与 `$superlooper-doctor` 只需要 non-ephemeral、read-only parent session。

安装完成后，在目标项目根目录运行：

```text
$superlooper-doctor
```

检查已有 task 时可传入 `task_id`：

```text
$superlooper-doctor <task_id>
```

## Python 运行边界

Python 是 Superlooper workflow 的 `workflow runtime dependency`，不属于 Claude Code 或 Codex 插件安装成功的判定条件。最低运行版本为 Python 3.9。运行 doctor 或总入口的当前实际 Agent 会话必须依次执行：

```bash
python --version
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
```

安装后先手动运行 doctor 是推荐顺序。即使跳过 doctor，Claude `/superlooper:spl` 与 Codex `$superlooper` 总入口也会在读取 task state、创建目录、恢复任务或调用 agent 前执行同一 preflight。

若 preflight 失败，入口固定报告：

```text
当前 Agent 会话无法执行 Python；Superlooper workflow 在该环境中不可用
```

失败后本次 workflow 无副作用停止：不创建 `.superlooper/`、不读取或推进 task、不调用 agent、不修改目标项目。插件不自动安装 Python，不修改 PATH、sandbox、权限或系统配置。

Doctor 的 runtime probe 失败记为 `Doctor 未启动：runtime prerequisite unavailable`，不表示插件结构、源码或发布物失败。

## 新建任务与身份

Task 是用户工作项，使用 `task_id/task_name` 标识；task state（兼容名称 session state）是该任务的持久化 workflow 状态。Agent session / parent session 只表示实际 Claude Code 或 Codex 运行会话及其权限。`session_id` 仅用于旧状态兼容。

在目标项目根目录创建真实需求文件，例如 `requirements.md`。不要把需求正文直接写入命令参数。

```markdown
# 商城后台

开发一个商城后台管理系统。

## 核心功能

- 商品管理
- 订单管理
- 用户管理
- 权限管理
```

Claude Code：

```text
/superlooper:spl requirements.md [--task-name "商城后台"]
```

Codex：

```text
$superlooper requirements.md [--task-name "商城后台"]
```

`task_name` 可选，只用于展示：

- 可包含 Unicode、中文和空格。
- 可重复；重名不会影响任务创建。
- 未提供时持久化为 `null`，界面显示“未命名任务”。
- 不参与目录、恢复定位、唯一性或 ID 生成。

新任务的 `task_id` 由脚本自动生成，格式为 `master-framework-YYYYMMDDHHMMSS`。它唯一且创建后不可变，是 state、目录、Manifest、报告、输出和恢复定位的关联键。用户新建任务时不填写 `task_id`。

首次任务会在目标项目创建 `.superlooper/` 运行时目录。任务名称相同或未命名时，使用 `task_id` 消歧。

## 工作流程概览

Superlooper 按以下七个流程推进任务：

1. 确认需求文件、创建 task，并初始化 `.superlooper/` 运行目录。
2. 生成 PRD，完成需求追溯和第一次人工审核。
3. 生成 UI 规格、页面地图、交互流程和 HTML 预览，完成第二次人工审核。
4. 生成系统设计、初始化建议和模块拆分；`standard` 模式自动完成初始化和模块清单校验。
5. 生成唯一的 `execution_manifest.json`、动态模块 Agent 和执行摘要，完成第三次人工审核。
6. 并行实现模块，执行产物契约校验和代码审查。
7. 完成合并、集成测试、受控应用、交付报告和需求反向校对，等待第四次人工审核后结束任务。

`standard` 模式只保留四个人工审核点。`strict_review` 模式增加设计、初始化和模块拆分等逐阶段审核，但不会绕过代码审查、测试、apply 冲突阻断或最终需求反向校对。

## 推荐使用顺序

1. 在目标项目根目录确认当前 Agent parent session 可以执行 Python 3.9+。
2. 安装插件后启动新会话，先运行对应平台的 doctor。
3. 创建真实的 `requirements.md`，通过总入口创建 task，并保存返回的 `task_id`。
4. 审核 PRD 和 UI 产物，分别提交第一、第二个人工审核回复。
5. 系统设计、初始化、模块拆分、Manifest 和动态 Agent 准备完成后，审核 `execution_summary.md`。
6. Claude Code 如果提示当前会话未发现动态 Agent，启动新会话并恢复同一 task；Codex 继续在满足运行前提的 parent session 中执行。
7. 提交第三个人工审核回复后，系统依次执行模块实现、代码审查、合并、测试和受控应用。
8. 审核 `requirement_alignment_report.md` 并提交第四个人工审核回复，完成交付。

任务中断时不要重新创建 task。使用 status 确认当前状态，再使用 resume 继续原 `task_id`。

## 审核点

默认 `standard` 流程只保留四个人工审核点：

| 审核点 | 主要产物 | 通过时回复 |
| --- | --- | --- |
| PRD 审核 | `prd.md` | `通过，进入 UI 设计` |
| UI 审核 | UI 规格与 HTML 预览 | `UI设计通过，进入系统设计` |
| 执行摘要审核 | `execution_summary.md` | `按此执行` |
| 需求反向校对 | `requirement_alignment_report.md` | `需求校对通过，完成交付` |

`strict_review` 模式保留逐阶段审核：设计批准后进入 `initialization/waiting_review` 依次选择项目分类和版本；初始化完成并生成、校验 module-split 后回到 `design/waiting_review`，用户继续后才进入 `run/pending`。

审核未通过时直接说明反馈。插件会基于当前 task 恢复，不需要重新启动完整流程。包含否定、暂停或修订语义的回复不会自动推进；语义不明确时会提供候选动作。

常用返工和恢复回复：

```text
PRD未通过，按反馈重新分析：<具体反馈>
UI设计未通过，按反馈重新设计：<具体反馈>
执行摘要未通过，返回修正：<具体反馈>
代码审查未通过，返回修正：<具体反馈>
测试未通过，返回修正：<具体反馈>
需求校对未通过，返回修正：<具体反馈>
```

若执行摘要为 BLOCKED，修复阻断项后必须明确回复 `重试执行摘要`；校验失败仍保持 BLOCKED，校验通过后回到待重新生成摘要状态。深层阶段发生需求或设计变更时，系统先生成影响分析；只有用户回复 `影响分析通过，执行局部重跑` 后，才会重跑已批准范围。

质量门禁中的 PASS 不是纯文本声明：code review 的 `reviewed_modules` 必须非空、无重复且完整覆盖当前 Manifest 模块；`test_report.md` 必须记录测试命令、退出码、结果、关键输出和全部 `REQ-*`、`AC-*`、`DEC-*`、`OPEN-*` 覆盖证据；`requirement_alignment_report.md` 必须逐项给出实现、测试和交付证据。证据缺失、编号遗漏、未知编号或重复编号都会阻断后续阶段。

## 恢复与状态

Claude Code：

```text
/superlooper:spl:status <task_id>
/superlooper:spl:resume <task_id>
/superlooper:spl:prd <requirement_path> [task_id]
/superlooper:spl:ui <task_id>
/superlooper:spl:design <task_id>
/superlooper:spl:run <task_id>
```

Codex：

```text
$superlooper-status <task_id>
$superlooper-resume <task_id>
$superlooper-prd <requirement_path> [task_id]
$superlooper-ui <task_id>
$superlooper-design <task_id>
$superlooper-run <task_id>
```

若目标项目只有一个 active task，也可在总入口输入“继续任务”等自然语言反馈。存在多个 active task 时，入口会显示 `task_name`（空值显示“未命名任务”）、`task_id` 和当前 phase/status；重名任务必须用 `task_id` 选择。

## Claude Code 动态 Agent 新会话恢复

执行清单阶段会为当前 task 生成 task-scoped 动态 Agent。Claude Code 不会在已运行会话中热加载这些新类型。若系统提示当前会话未发现全部动态 Agent：

1. 保留当前 task 和 `.superlooper/` 运行目录，不要重新创建任务。
2. 启动新的 Claude Code 会话。
3. 在同一个目标项目根目录执行：

```text
/superlooper:spl:resume <task_id>
```

4. 确认恢复到 `run/waiting_review` 和 `READY_FOR_APPROVAL` 后，再次提交：

```text
按此执行
```

必须使用完整安装态 namespace `/superlooper:spl:resume <task_id>`，不要使用旧的 `/spl:resume <task_id>`。Codex 不需要 Claude 动态 Agent 类型发现，但仍必须满足 Python 和 parent session 权限前提。

## 升级与卸载

### Claude Code 升级

更新 Marketplace 和 user-scope 插件：

```text
/plugin marketplace update superAI-marketplace
/plugin update superlooper@superAI-marketplace
```

Claude Code 不会在当前运行会话中热加载更新后的插件。升级完成后启动新会话，再运行：

```text
/superlooper:spl:doctor
/superlooper:spl:resume <task_id>
```

如果执行摘要已经生成，但新动态 Agent 尚未被当前会话发现，任务会保持 `READY_FOR_APPROVAL`。启动新会话、执行完整 namespace 的 `/superlooper:spl:resume <task_id>`，然后重新回复 `按此执行`；不要使用旧的 `/spl:resume` 安装态命令。

### Codex 升级

更新 Marketplace：

```bash
codex plugin marketplace upgrade superAI-marketplace
```

需要重新安装当前发布版本时执行：

```bash
codex plugin remove superlooper@superAI-marketplace
codex plugin add superlooper@superAI-marketplace
```

启动新的 Codex session 后运行：

```text
$superlooper-doctor
$superlooper-resume <task_id>
```

生成或恢复当前 task 时不会自动清理其他 task 的 runtime/registered 动态 Agent 文件。卸载插件也不会自动删除目标项目 `.superlooper/`；Claude Code 的 `.claude/agents/generated/superlooper/` 仍会保留。清理前确认对应任务不再用于恢复、审计或交付追溯。

Codex 卸载命令：

```bash
codex plugin remove superlooper@superAI-marketplace
codex plugin marketplace remove superAI-marketplace
```

## 冲突与失败恢复

Superlooper 默认不会覆盖目标工作区中同路径、不同内容的既有文件。apply 发生冲突时：

1. 查看 `.superlooper/reports/<task_id>/apply_conflict_report.json`。
2. 确认保留现有文件、调整模块产物，或明确授权覆盖指定文件。
3. 完成人工处理后回复 `应用冲突已处理，重新应用`。
4. 使用 status 或 resume 命令继续当前 task，不要重新创建任务。

只有用户显式授权时，底层 apply 才允许使用 `--overwrite-file <relative_path>` 或 `--overwrite-existing`。默认冲突阻断策略始终保持启用。

代码审查或测试失败时，分别回复 `代码审查未通过，返回修正`、`测试未通过，返回修正`。深层需求变更会先生成影响分析报告，只有用户回复 `影响分析通过，执行局部重跑` 后，才会重跑已批准范围。

## 执行与安全约束

- 深层需求或设计变更先生成影响分析；只有用户批准后，才按已校验范围局部重跑。
- merge 从模块产物重建完整快照；apply 会复核快照摘要并执行事务回滚，已有同路径不同内容文件默认阻断。
- 人工审核采用 fail-closed；否定、暂停和修订表达不会被误判为批准，BLOCKED 执行摘要必须明确回复 `重试执行摘要`。
- Claude Code 执行动态模块前必须在新会话发现 task-scoped Agent；Codex 使用 Manifest logical Agent，不执行该发现检查。
- 初始化参数只读取已校验 `initialization-advice.md` 的机器参数块，不从自然语言或项目画像猜测。

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 看不到 Claude Code 命令 | 重新检查插件或 Marketplace 是否安装成功，再运行 `/superlooper:spl:doctor`。 |
| 看不到 Codex skill | 重新检查 Marketplace 和插件安装，再运行 `$superlooper-doctor`。 |
| Doctor 未启动 | 在同一个实际 Agent 会话运行 `python --version` 并确认版本为 Python 3.9+；不可用或版本过低时记录 `runtime prerequisite unavailable`。 |
| 总入口报告 Python 不可用 | 当前 workflow 已无副作用停止。按组织规则准备 runtime 后重试；不自动安装 Python，不修改 PATH 或 sandbox。 |
| `requirements.md` 不存在 | 在目标项目根目录创建真实需求文件后重新启动首个任务。 |
| 存在多个 active task | 使用 status 命令查看名称、ID、phase/status，并指定 `task_id`。 |
| 执行摘要显示 BLOCKED | 修复摘要列出的阻断项后回复 `重试执行摘要`；不要回复“按此执行”或普通“继续”。 |
| Claude 提示当前会话缺少动态 Agent 类型 | 启动新 Claude Code 会话，执行 `/superlooper:spl:resume <task_id>`，再次提交“按此执行”。任务继续保持 READY_FOR_APPROVAL，不需要重建 task。 |
| merge 或 apply 报告真实路径越界 | 检查模块输出、merged 目录或目标工作区祖先是否包含指向授权根外的 symlink/junction；移除越界链接并重新运行对应阶段。 |
| apply 发生冲突 | 人工处理冲突后回复 `应用冲突已处理，重新应用`；插件不会默认覆盖已有不同内容的目标文件。 |
| apply I/O 失败 | 查看 `apply_report.json.rollback`。`success` 表示本次写入已回滚，可在修复 I/O 原因后重试；`partial` 表示必须使用保留的 backup 人工恢复。 |

## 许可证

Superlooper 使用 MIT 许可证发布。

<!-- public-readme:end -->
