# Superlooper

Superlooper 是同时适用于 Claude Code 与 Codex 的 AI 并行编排插件。它把需求文档推进为 PRD、UI 设计、系统设计、并行实现、审查、测试与受控应用流程。

> 想安装和使用插件：阅读本页“快速开始”或[完整用户指南](docs/USER_GUIDE.md)。
>
> 想维护插件源码、发布版本或修改协议：阅读 [开发说明](docs/DEVELOPMENT.md) 与 [发布指南](docs/RELEASE.md)。

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
