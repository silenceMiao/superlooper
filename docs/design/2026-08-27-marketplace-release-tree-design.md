# Marketplace 发布树设计

## 背景与目标

Superlooper 源码根 `<plugin-source-root>` 保持为 Claude Code 与 Codex 双平台插件源码。`superAI-marketplace` 是独立 Git 发布市场，用于声明和分发多个可安装插件，不是 Superlooper 的第二套源码。

发布树中 `plugins/superlooper/` 只包含从 install 发布清单派生的安装闭包。Marketplace 根 README、其他插件目录和其他 registry 条目不属于 Superlooper install closure。

## 第一性原理分析

1. **发布对象**：发布对象是多插件 Marketplace 仓库，不是源码根或 install ZIP。
2. **文件事实源**：Superlooper 插件树的唯一文件事实源是 install manifest 的 `release_files`。
3. **所有权**：Superlooper 源码管理自身版本、用户 README 和 install closure；Marketplace 管理根 README、插件目录、插件发现和其他插件条目。
4. **安全边界**：同步器只写入 Superlooper 插件树、双 registry 中唯一 Superlooper 条目和本插件 v2 账本。
5. **验证方式**：对 Superlooper 树验证文件集、目录集、字节、双 manifest、唯一 registry 条目和 ledger hash；不把根 README 或其他插件视为漂移。

## 目标目录结构

```text
superAI-marketplace/
├── README.md                              # Marketplace 自有概览
├── .claude-plugin/
│   └── marketplace.json                   # Claude Code 共享 registry
├── .agents/
│   └── plugins/
│       └── marketplace.json               # Codex 共享 registry
├── .superlooper-marketplace-sync.json     # Superlooper v2 私有账本
└── plugins/
    └── superlooper/                       # install closure 镜像
        ├── README.md                      # Superlooper 用户 README
        ├── .claude-plugin/plugin.json
        ├── .codex-plugin/plugin.json
        ├── agents/
        ├── commands/
        ├── skills/
        ├── codex/
        ├── scripts/
        └── ... install release_files 的其他文件
```

两个 Marketplace metadata 都通过 `source: "./plugins/superlooper"` 指向同一插件树。未来新增插件使用独立的 `plugins/<plugin-id>/` 目录和自己的安装闭包。

## v2 同步账本与共享 registry

v2 账本只散列 `plugins/superlooper/**` 的普通文件：

```json
{
  "schema_version": 2,
  "plugin_name": "superlooper",
  "plugin_version": "<version>",
  "source_commit": "<sha-or-null>",
  "managed_paths": {
    "plugins/superlooper/<release-file>": "<sha256>"
  }
}
```

同步器读取现有 Claude/Codex registry，并只处理 `name == "superlooper"` 的唯一条目：合法条目在原数组位置更新，缺失时追加，重复或不合法条目阻断。所有其他条目的值和顺序保持不变。

根 README 是市场概览，不从 Superlooper 用户指南生成，也不进入账本。它可链接 `plugins/superlooper/README.md`，但不承担 Superlooper 的用户文案事实源职责。

## 生成与迁移流程

1. `PluginPackager(mode="install")` 生成并校验 install manifest。
2. 打包器逐文件复制 `release_files` 到 staging 中的 `plugins/superlooper/`，不使用 `copytree`。
3. 新建市场必须显式提供 overview 文件；该文件原样写入根 README，registry 从空数组加 Superlooper canonical 条目初始化。
4. 日常同步校验 v2 ledger 和 Superlooper tree，再更新两个 registry 的目标条目、插件树与账本。
5. 发现 v1 ledger 时，只有 `--migrate-v1` 可以启动迁移。迁移先验证 v1 README、metadata、插件树和 hash 均未漂移，成功后才写 v2 路径集合。
6. 无账本旧镜像只允许通过 `--adopt-existing` 接管；它不能与 v1 migration 同用。

同步器不删除或改写 `.git/`、根 README、其他插件、metadata 相邻路径或其他 registry 条目。写入失败时仅恢复本次替换的 metadata 文件、Superlooper tree 和 ledger。

## 发布边界

不得将以下内容纳入 `plugins/<plugin-id>/`：

- `.superlooper/` 运行时产物；
- `.claude/` 本地开发上下文；
- `__pycache__/`、`dist/` 和本地验证缓存；
- 用户配置、认证文件、令牌、密码或其他密钥；
- 不属于插件 install closure 的测试与设计文档。

Marketplace 根目录不建立全局 skill 注册中心、全局 MCP 路由、共享密钥、跨插件权限或跨插件运行协议。插件可声明自身所需的 skills、agents、scripts、schemas 和 MCP 集成边界。

## 验收标准

| 验收项 | 通过条件 |
| --- | --- |
| Superlooper 镜像 | 文件集、目录集和字节与 install manifest 完全一致。 |
| v2 账本 | 仅包含 `plugins/superlooper/**` 的 SHA-256。 |
| 根 README | 是 Marketplace 概览，且不被 Superlooper 同步改写。 |
| 共享 registry | 仅更新唯一 Superlooper 条目，其他条目和值顺序保持不变。 |
| 安全阻断 | v1 漂移、插件树漂移、重复/非法目标条目和受控符号链接均在写入前失败。 |
| 双平台 | Claude Code 与 Codex metadata 及插件 manifest 均指向同一插件树。 |
