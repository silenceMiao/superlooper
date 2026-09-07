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
4. 准备 `requirements.md` 后启动首次会话。

### Claude Code

```text
/plugin marketplace add <owner>/superAI-marketplace
/plugin install superlooper@superAI-marketplace
/superlooper:spl:doctor
/superlooper:spl requirements.md [session_id]
```

### Codex

```text
codex plugin marketplace add <owner>/superAI-marketplace --ref main
codex plugin add superlooper@superAI-marketplace
$superlooper-doctor
$superlooper requirements.md [session_id]
```

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

完整 Codex workflow 使用 non-ephemeral、`workspace-write` parent session，以写入目标项目的 `.superlooper/` 运行时产物。当前运行 doctor 的 Codex parent session 必须能执行 Python runtime；宿主 shell 能执行 Python 不代表该 session 已满足前置条件。

如果当前 session 无法运行 Python，先按组织 sandbox 策略满足该 session 的运行环境，再重新运行 doctor。不要通过扩大权限、继承全量环境变量或重启系统绕过该前置条件。

安装完成后，在目标项目根目录运行：

```text
$superlooper-doctor
```

## 首次会话

在目标项目根目录创建真实需求文件，例如 `requirements.md`。不要把需求正文直接写入命令参数。

Claude Code：

```text
/superlooper:spl requirements.md [session_id]
```

Codex：

```text
$superlooper requirements.md [session_id]
```

未提供 `session_id` 时，插件生成安全会话标识。首次会话会在目标项目创建 `.superlooper/` 运行时目录。

## 审核点

默认流程保留四个人工审核点：

| 审核点 | 主要产物 | 通过时回复 |
| --- | --- | --- |
| PRD 审核 | `prd.md` | `通过，进入 UI 设计` |
| UI 审核 | UI 规格与 HTML 预览 | `UI设计通过，进入系统设计` |
| 执行摘要审核 | `execution_summary.md` | `按此执行` |
| 需求反向校对 | `requirement_alignment_report.md` | `需求校对通过，完成交付` |

审核未通过时直接说明反馈。插件会基于当前会话恢复，不需要重新启动完整流程。

## 恢复与状态

Claude Code：

```text
/superlooper:spl:resume <session_id>
/superlooper:spl:status <session_id>
```

Codex：

```text
$superlooper-resume <session_id>
$superlooper-status <session_id>
```

若目标项目只有一个 active session，也可在总入口输入“继续任务”等自然语言反馈。多个 active session 时，先指定目标 `session_id`。

## 升级与卸载

升级后先运行对应平台 doctor，再恢复旧 session：

```text
/superlooper:spl:doctor
/superlooper:spl:resume <session_id>
```

```text
$superlooper-doctor
$superlooper-resume <session_id>
```

卸载插件不会自动删除目标项目 `.superlooper/`；Claude Code 的 `.claude/agents/generated/superlooper/` 也会保留。清理前确认对应会话不再用于恢复、审计或交付追溯。

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
| doctor 失败 | 按 doctor 输出修复安装或运行环境问题；修复前不启动业务流程。 |
| `requirements.md` 不存在 | 在目标项目根目录创建真实需求文件后重新启动首次会话。 |
| 存在多个 active session | 使用对应平台的 status 命令确认并指定 `session_id`。 |
| apply 发生冲突 | 人工处理冲突后回复 `应用冲突已处理，重新应用`；插件不会默认覆盖已有不同内容的目标文件。 |
