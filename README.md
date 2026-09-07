# Superlooper

Superlooper 是同时适用于 Claude Code 与 Codex 的 AI 并行编排插件。它把需求文档推进为 PRD、UI 设计、系统设计、并行实现、审查、测试与受控应用流程。

> 想安装和使用插件：阅读本页“快速开始”或[完整用户指南](docs/USER_GUIDE.md)。
>
> 想维护插件源码、发布版本或修改协议：阅读 [开发说明](docs/DEVELOPMENT.md) 与 [发布指南](docs/RELEASE.md)。

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
