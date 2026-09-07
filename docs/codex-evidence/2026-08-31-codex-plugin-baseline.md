# Codex CLI 与 Marketplace 现场基线

- 日期：2026-08-31
- 总体状态：`DONE`
- 范围：本记录覆盖 Codex CLI 0.151.0 的现场插件、Marketplace 与原生多 agent 验证。
- 边界：未修改 Claude Code 插件、命令、七流程协议或打包逻辑。

## Version

官方 npm 包 `@openai/codex` 已安装，现场命令返回：

```text
codex --version
codex-cli 0.151.0
```

以下命令均返回 `0`：

```text
codex plugin --help
Commands: add, list, marketplace, remove, help

codex plugin marketplace --help
Commands: add, list, upgrade, remove, help
```

`codex features list` 将 `multi_agent` 标示为 `stable true`。

### 最新 help 参数证据

本轮再次执行两个 help 命令，均返回 `0`。`codex plugin` 的实际命令为 `add`、`list`、`marketplace`、`remove` 和 `help`；`codex plugin marketplace` 的实际命令为 `add`、`list`、`upgrade`、`remove` 和 `help`。两个命令组均提供以下全局选项：

```text
-c, --config <key=value>
--enable <FEATURE>
--disable <FEATURE>
-h, --help
```

`plugin add` 从已配置 Marketplace snapshot 安装插件；`plugin marketplace add` 接受 local 或 Git Marketplace。该参数级证据确认本文件后续使用的注册、安装、卸载与移除命令来自当前 CLI，而非推测。

## Plugin manifest contract

当前 Codex Agent Plugin 使用以下 manifest 路径：

```text
.codex-plugin/plugin.json
```

现场通过的最小核心字段如下：

```json
{
  "name": "hello",
  "version": "0.1.0",
  "description": "...",
  "author": { "name": "..." },
  "skills": "./skills/",
  "interface": {
    "displayName": "...",
    "shortDescription": "...",
    "longDescription": "...",
    "developerName": "...",
    "category": "...",
    "capabilities": ["Interactive"],
    "defaultPrompt": ["..."],
    "brandColor": "#111111",
    "screenshots": []
  }
}
```

`name` 使用 kebab-case，`version` 使用严格 semver，组件路径以 `./` 开头。不要声明不存在的 `apps` 或 `mcpServers`；当前官方规格拒绝 `hooks` 等不支持字段。

## Marketplace manifest contract

Marketplace metadata 的仓库内路径为：

```text
.agents/plugins/marketplace.json
```

现场 fixture 使用的条目如下：

```json
{
  "name": "hello",
  "source": { "source": "local", "path": "./plugins/hello" },
  "policy": { "installation": "AVAILABLE", "authentication": "ON_USE" },
  "category": "Developer Tools"
}
```

`policy.installation` 的合法值是 `NOT_AVAILABLE`、`AVAILABLE` 与 `INSTALLED_BY_DEFAULT`；`policy.authentication` 的合法值是 `ON_INSTALL` 与 `ON_USE`。`source.path` 相对于 Marketplace 根目录。

## Install and update commands

CLI 接受本地目录、`owner/repo[@ref]`、HTTPS Git URL 或 SSH Git URL 作为 Marketplace source。

```bash
# 注册 GitHub Marketplace；可选指定 ref 或稀疏目录
codex plugin marketplace add owner/repo --ref main
codex plugin marketplace add https://github.com/owner/repo --sparse plugins/hello

# 安装、查看、刷新、卸载和移除
codex plugin add hello@marketplace-name
codex plugin list
codex plugin marketplace upgrade marketplace-name
codex plugin remove hello@marketplace-name
codex plugin marketplace remove marketplace-name
```

本地 fixture 的 source 是 `./tests/fixtures/codex-marketplace-minimal/`。现场命令从插件根目录运行；local path 必须以 `./` 开头，缺少该前缀的 `tests/fixtures/...` 会被 CLI 拒绝为无效 Marketplace source。本次未注册、升级或变更任何远程 GitHub Marketplace。

### 本地 fixture 实测命令

以下是本次在插件根目录实际执行的完整生命周期命令。路径保持仓库相对形式，避免记录机器局部绝对路径：

```bash
codex plugin marketplace add ./tests/fixtures/codex-marketplace-minimal/
codex plugin add hello@codex-fixture-marketplace
codex exec --ephemeral --skip-git-repo-check --sandbox read-only --cd . '$hello'
codex plugin remove hello@codex-fixture-marketplace
codex plugin marketplace remove codex-fixture-marketplace
codex plugin list
codex plugin marketplace list
```

本次输出依次确认 Marketplace 已添加、`hello` 已添加、skill 返回精确契约、plugin 与 Marketplace 均已移除；最终两个 list 输出均不包含 `hello@codex-fixture-marketplace` 或 `codex-fixture-marketplace`。`--ephemeral` 只用于单 skill 调用，不用于多 agent 编排。

## Skill invocation contract

Codex 用户入口是 `$skill-name`。最小 fixture 位于：

```text
tests/fixtures/codex-marketplace-minimal/
├── .agents/plugins/marketplace.json
└── plugins/hello/
    ├── .codex-plugin/plugin.json
    └── skills/hello/SKILL.md
```

其中 `skills/hello/SKILL.md` 保留 Task 1 要求的 `summary` frontmatter、`# Hello` 标题和精确正文 ``Reply with `codex-plugin-fixture-ok`.``。Codex CLI 0.151.0 的实际 skill loader 还要求 `description` frontmatter：仅使用 `summary` 会报 `missing field description`。因此 fixture 同时包含 `summary` 与 `description`，并已以该最小兼容形式完成真实安装验证。

输出契约为：

```text
$hello
codex-plugin-fixture-ok
```

现场按注册、安装、调用、卸载、移除的完整生命周期验证：

| 操作 | 结果 | 现场输出摘要 |
| --- | --- | --- |
| 注册本地 Marketplace | PASS | `Added marketplace \`codex-fixture-marketplace\`` |
| 安装 `hello@codex-fixture-marketplace` | PASS | `Added plugin \`hello\`` |
| 全新隔离会话调用 `$hello` | PASS | 输出精确为 `codex-plugin-fixture-ok` |
| 卸载 fixture plugin | PASS | `Removed plugin \`hello\`` |
| 移除 fixture Marketplace | PASS | `Removed marketplace \`codex-fixture-marketplace\`` |

技能调用使用 `codex exec --ephemeral --skip-git-repo-check --sandbox read-only`。`--ephemeral` 防止该 skill 验证持久化会话文件，`read-only` 阻止 agent 写入工作区。

该入口不同于 Claude Code 的 `/superlooper:spl`，本次验证未改变现有 Claude 命令或七流程。

## Multi-agent capability contract

真实验证显示，Codex 原生多 agent 是父 agent 在会话内直接调用 `spawn_agent` 的能力，不存在用于创建子 agent 的独立 CLI 命令；`codex agents` 只用于浏览共享 app-server daemon 中的会话。

| 项目 | 现场结论 |
| --- | --- |
| 触发方式 | 父 agent 直接调用原生 `spawn_agent`，不能从 agent 的 shell `exec` 内调用该工具。实际调用参数是 `task_name`、`fork_turns` 和 `message`；本次两个任务分别使用 `task_name="child_a"`、`task_name="child_b"`，均使用 `fork_turns="none"`。|
| 参数形式 | `spawn_agent({"task_name":"child_a","fork_turns":"none","message":"<task instruction>"})`。持久化 trace 将 `message` 以不透明值保存；本文只保留字段形式，避免写入会话原文或机器局部数据。 |
| 会话结构 | 每个子 agent 都产生独立 thread，记录父 `thread_id`、`thread_source=subagent` 与 `/root/<task-name>` agent path。 |
| 返回结构 | 调用结果为 `{"task_name":"/root/child_a"}` 或相同结构的 child B 路径；子 agent 以 `agent_message` 返回最终文本，父 agent 等待子任务完成后汇总并输出最终消息。 |
| 并发上限 | 本运行时给出 4 个并发 slot，包含父 agent；本次父 agent 实际创建 2 个只读子任务。 |
| 现场结果 | child A 返回 `CHILD_A_OK`；child B 返回 `CHILD_B_OK`；父 agent 最终输出 `PARENT_SUMMARY CHILD_A_OK CHILD_B_OK`。 |

父、子 thread 的 session metadata 与消息事件均证明两个任务由父 thread 创建并回传结果，不是父 agent 模拟结果。所有会话均使用 `sandbox: read-only`，未创建、修改或删除工作区文件。

成功的父会话按以下形态启动；`<repo-root>` 是对实际本地工作目录参数的脱敏替换：

```bash
codex exec --skip-git-repo-check --sandbox read-only --cd <repo-root> 'Use the native multi-agent capability. Create exactly two independent read-only child tasks concurrently. Child A must return exactly CHILD_A_OK. Child B must return exactly CHILD_B_OK. Do not create, edit, or delete any files. Wait for both children to finish, then return exactly one final line: PARENT_SUMMARY CHILD_A_OK CHILD_B_OK. Do not simulate child results or perform either task yourself.'
```

`codex exec --ephemeral` 不适用于此类多 agent 编排：现场会出现 `collab spawn failed: no thread with id ...`，因为 ephemeral 父线程不能供 collaboration router 查找。改用一次新的非 ephemeral、只读 `codex exec` 会话后，多 agent 测试通过。后续 Codex dispatcher 实现不得在需要 `spawn_agent` 的父会话中使用 `--ephemeral`。

### Marketplace skill 上下文复验

为避免只证明裸 `codex exec` 会话，现场另建未纳入仓库的临时本地 Marketplace，其中的 `$spawn-check` skill 明确要求直接调用 `spawn_agent`，创建两个 `fork_turns="none"` 的只读 child agent，并等待其返回。完成注册、安装与非 ephemeral 的只读 skill 会话后，父 agent 输出精确为：

```text
SKILL_PARENT_SUMMARY SKILL_CHILD_A_OK SKILL_CHILD_B_OK
```

持久化 trace 显示已安装 skill 被加载，并存在 `/root/spawn_child_a` 与 `/root/spawn_child_b` 两个独立 child agent 活动；两者分别回传 `SKILL_CHILD_A_OK` 与 `SKILL_CHILD_B_OK`。这证明 Marketplace skill 上下文可以调用当前 Codex 原生多 agent 能力，且父 agent 的汇总不是模拟结果。

本次 trace 中 child A 完成后 child B 才开始，因此该复验只证明两个独立 child agent、等待和结果汇总，**不证明实际并发重叠执行**。Task 1 Step 4 的验收要求是获得两个独立子任务结果，并未将观察到实际并发重叠列为硬门禁。

## 现场过程与清理

首次历史试验曾在模型传输阶段出现 HTTPS timeout，因而当时未将 skill 或多 agent 标为成功。本次先运行只读最小模型传输探针，得到精确输出 `codex-transport-ok`，再重新执行完整 E2E；失败记录保留是为了区分已解决的传输问题与 fixture 契约。

fixture 安装状态已完成清理：执行 `codex plugin remove hello@codex-fixture-marketplace` 与 `codex plugin marketplace remove codex-fixture-marketplace` 后，当前列表不包含该 fixture。fixture 源文件保留在仓库中供后续回归验证。

临时 `$spawn-check` 复验也已依次移除 plugin 与 Marketplace；生命周期命令均返回 `0`，最终 cleanup 断言通过。该临时 fixture 未进入仓库、发布产物或安装态缓存，且其创建目录已删除。

## Sources

- [Codex CLI 官方仓库安装说明](https://github.com/openai/codex)
- [官方 plugin manifest / marketplace 规格](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/plugin-creator/references/plugin-json-spec.md)
- [OpenAI Plugins 官方 marketplace 示例](https://github.com/openai/plugins/blob/main/.agents/plugins/marketplace.json)
- [OpenAI Help：GitHub Marketplace imports](https://help.openai.com/en/articles/20001504)

## Secrets and path check

本文件未记录 token、登录数据、环境变量值、用户绝对路径或 Codex session 文件路径。现场输出中的敏感或机器局部路径均已改写为语义化描述或仓库相对路径。
