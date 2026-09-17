# Superlooper 用户指南

<!-- public-readme:start -->
# Superlooper

Superlooper 是同时适用于 Claude Code 与 Codex 的 AI 并行编排插件。它把需求文档推进为 PRD、UI 设计、系统设计、并行实现、审查、测试与受控应用流程。

> 想安装和使用插件：阅读本页“快速开始”或[完整用户指南]({{USER_GUIDE_LINK}})。
>
> {{SOURCE_MAINTENANCE_LINKS}}

## 快速开始

1. 添加已发布的 `superAI-marketplace`。
2. 安装 `superlooper`。
3. 在目标项目根目录运行 doctor。
4. 准备 `requirements.md` 后启动首个任务。

### Claude Code

```text
/plugin marketplace add <owner>/superAI-marketplace
/plugin install superlooper@superAI-marketplace
/superlooper:spl:doctor
/superlooper:spl requirements.md [--task-name "商城后台"]
```

### Codex

```text
codex plugin marketplace add <owner>/superAI-marketplace --ref main
codex plugin add superlooper@superAI-marketplace
$superlooper-doctor
$superlooper requirements.md [--task-name "商城后台"]
```

Python 3.9+ 是 Superlooper 的 `workflow runtime dependency`，不是 Claude Code 或 Codex 的插件安装标准。安装成功不等于当前 Agent 会话已满足运行依赖。

深层需求或设计变更会先进入影响分析。报告生成时不会提前授权受影响模块；只有用户批准局部重跑后，审核 reducer 才把已校验范围写入 task state。所选模块产物校验完成后会清空局部范围，再进入完整 DAG 的全局审查、合并、测试和应用门禁。模块目标文件、`produced_files` 声明和实际产物文件均按 Windows 大小写不敏感、尾点/尾空格等价规则保持唯一。

每次 merge 都从当前模块产物在空 staging 中重建完整快照，计算 `snapshot_digest` 后事务式发布快照和报告；冲突、路径越界、digest 或发布失败不会部分覆盖上一份成功快照。apply 写入前重新校验 merged tree digest，并把 create/overwrite、工作区验证和成功报告发布纳入同一可回滚事务。部分回滚必须保留 backup 并人工恢复。任何 failed apply 都不能通过最终门禁，最终完成同时要求需求校对报告通过和人工校对标志为 `true`。

人工审核采用 fail-closed 语义：否定、暂停和修订表达不会因为包含“通过”或“执行”等子串而被误批准；普通 checkpoint 也不能直接离开 `waiting_review` 或构造最终批准状态。BLOCKED 执行摘要只接受明确“重试执行摘要”恢复；重试校验成功前保持阻断。代码审查 PASS 必须非空、完整覆盖当前 Manifest 的全部模块；测试和需求反向校对的 PASS 报告必须携带机器可读命令、退出码、关键输出及 PRD 稳定编号覆盖证据。

四个系统质量节点使用经过 Schema 和 validator 校验的 object payload。Claude Code 正式静态 Agent 调用使用 `superlooper:<agent-name>` namespace，Manifest 与 runtime Agent 继续保存 `module_<module_id>` logical name；Claude 注册入口使用 task-scoped frontmatter name。用户提交“按此执行”前，当前 Claude Code 会话必须已发现全部 scoped name，否则 task 保持 READY_FOR_APPROVAL，并只提示启动新会话后执行 `/superlooper:spl:resume <task_id>` 再次提交“按此执行”。Codex 不执行该发现检查，继续使用只读 renderer 调度 logical Agent。

系统设计阶段的 `initialization-advice.md` 以第一个 YAML 参数块声明 `task_id`、`project_category`、`project_version` 和 `project_root`。Claude Code 与 Codex 都会先校验该参数块，再完整传给初始化脚本；缺失或非法参数会阻断，adapter 不会从自然语言或项目画像猜测。

Superlooper 使用 MIT 许可证发布。
<!-- public-readme:end -->

## 安装产物选择

普通用户使用 `superlooper-<version>-install.zip` 或已发布的 `superAI-marketplace`。`superlooper-<version>-source.zip` 用于源码审计和开发验证，不是普通用户安装入口。

## 安装

### Claude Code

添加并安装已发布 Marketplace：

```text
/plugin marketplace add <owner>/superAI-marketplace
/plugin install superlooper@superAI-marketplace
```

安装完成后，在目标项目根目录运行：

```text
/superlooper:spl:doctor
```

### Codex

添加并安装同一个已发布 Marketplace：

```text
codex plugin marketplace add <owner>/superAI-marketplace --ref main
codex plugin add superlooper@superAI-marketplace
```

完整 Codex workflow 使用 non-ephemeral、`workspace-write` parent session，以写入目标项目的 `.superlooper/` 运行时产物；`$superlooper-status` 与 `$superlooper-doctor` 只需要 non-ephemeral、read-only parent session。

安装完成后，在目标项目根目录运行：

```text
$superlooper-doctor
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

## 审核点

默认 `standard` 流程只保留四个人工审核点：

| 审核点 | 主要产物 | 通过时回复 |
| --- | --- | --- |
| PRD 审核 | `prd.md` | `通过，进入 UI 设计` |
| UI 审核 | UI 规格与 HTML 预览 | `UI设计通过，进入系统设计` |
| 执行摘要审核 | `execution_summary.md` | `按此执行` |
| 需求反向校对 | `requirement_alignment_report.md` | `需求校对通过，完成交付` |

`strict_review` 模式保留逐阶段审核：设计批准后进入 `initialization/waiting_review` 依次选择项目分类和版本；初始化完成并生成、校验 module-split 后回到 `design/waiting_review`，用户继续后才进入 `run/pending`。

审核未通过时直接说明反馈。插件会基于当前 task 恢复，不需要重新启动完整流程。包含否定、暂停或修订语义的回复不会自动推进；语义不明确时会提供候选动作。若执行摘要为 BLOCKED，修复阻断项后必须明确回复 `重试执行摘要`；校验失败仍保持 BLOCKED，校验通过后回到待重新生成摘要状态。

质量门禁中的 PASS 不是纯文本声明：code review 的 `reviewed_modules` 必须非空、无重复且完整覆盖当前 Manifest 模块；`test_report.md` 必须记录测试命令、退出码、结果、关键输出和全部 `REQ-*`、`AC-*`、`DEC-*`、`OPEN-*` 覆盖证据；`requirement_alignment_report.md` 必须逐项给出实现、测试和交付证据。证据缺失、编号遗漏、未知编号或重复编号都会阻断后续阶段。

## 恢复与状态

Claude Code：

```text
/superlooper:spl:resume <task_id>
/superlooper:spl:status <task_id>
/superlooper:spl:ui <task_id>
/superlooper:spl:design <task_id>
/superlooper:spl:run <task_id>
```

Codex：

```text
$superlooper-resume <task_id>
$superlooper-status <task_id>
$superlooper-ui <task_id>
$superlooper-design <task_id>
$superlooper-run <task_id>
```

若目标项目只有一个 active task，也可在总入口输入“继续任务”等自然语言反馈。存在多个 active task 时，入口会显示 `task_name`（空值显示“未命名任务”）、`task_id` 和当前 phase/status；重名任务必须用 `task_id` 选择。

## 升级与卸载

升级后先运行对应平台 doctor，再按 `task_id` 恢复旧任务：

```text
/superlooper:spl:doctor
/superlooper:spl:resume <task_id>
```

```text
$superlooper-doctor
$superlooper-resume <task_id>
```

生成或恢复当前 task 时不会自动清理其他 task 的 runtime/registered 动态 Agent 文件。卸载插件也不会自动删除目标项目 `.superlooper/`；Claude Code 的 `.claude/agents/generated/superlooper/` 仍会保留。清理前确认对应任务不再用于恢复、审计或交付追溯。

Codex 卸载命令：

```text
codex plugin remove superlooper@superAI-marketplace
codex plugin marketplace remove superAI-marketplace
```

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
