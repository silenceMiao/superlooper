# Marketplace 发布树设计

## 背景与目标

Superlooper 当前源码根 `<plugin-source-root>` 保持为可通过 `claude plugin validate . --strict` 的 Claude Code plugin 根目录。Marketplace 发布仅新增独立的发布树生成能力，不迁移、不重命名、不重组当前源码根。

本设计的目标是从 install 发布清单构造可提交到独立 GitHub marketplace 仓库的目录树。发布树只包含 marketplace 元数据和 Superlooper 的安装态文件，不包含源码分发专用内容、构建输出或本地运行时内容。

## 第一性原理分析

### 需求对象

发布对象不是当前源码根，也不是 install ZIP 文件，而是一个可被 Claude Code marketplace 消费的独立 Git 仓库目录树。

### 唯一事实源

install release manifest 中的 `release_files` 是 marketplace tree 的唯一文件事实源。发布树生成器只读取该数组列出的相对路径；不得自行扫描源码目录、维护第二份包含规则或补充未列出的文件。

这样可以保证 install ZIP、install manifest 与 marketplace tree 对安装文件集合使用同一份事实。

### 路径映射

每个 `release_files` 相对路径保持不变，并映射到发布树中的 `plugins/superlooper/` 下。Marketplace 根仅额外包含 `.claude-plugin/marketplace.json`。

```text
<marketplace-target>/
├── .claude-plugin/
│   └── marketplace.json
└── plugins/
    └── superlooper/
        ├── .claude-plugin/
        │   └── plugin.json
        ├── agents/
        ├── commands/
        ├── skills/
        ├── scripts/
        └── ... install release manifest 的其他 release_files
```

### 安全边界

发布树目标目录不得等于源码根，也不得位于源码根之内。否则写入发布树会把 marketplace 产物混入插件源码，并污染后续 release manifest。

生成器必须在生成 install manifest 或创建任何目标文件前完成该路径校验。目标目录存在时必须拒绝覆盖；生成器不删除、不清空、不合并既有目标内容，调用方必须提供一个不存在的独立目标目录。

### 交付边界

发布树用于提交到独立 GitHub marketplace 仓库。当前 Superlooper 源码目录不是 Git 仓库，发布树生成能力不承担 Git 初始化、提交、推送、创建远程仓库或发布 Marketplace 的职责。

## 当前事实与设计约束

当前 `scripts/package_plugin.py` 以 install 模式生成 `dist/superlooper-release-manifest.json`，其中 `release_files` 列出安装发布文件。install 模式排除 `docs/design/` 与 `tests/`，并排除 `.superlooper`、`.claude`、`dist/`、环境文件和缓存目录。

当前 `scripts/build_release_archive.py` 按 manifest 的 `release_files` 写入 install ZIP，并在归档后核对 ZIP 内部路径集合。这证明 release manifest 已是 install 归档的文件边界；Marketplace tree 必须复用这一边界。

发布树生成不得使用 `shutil.copytree`。`copytree` 以目录为单位复制，无法保证仅复制 manifest 文件，且会把被 install 过滤排除的文件、既有构建产物或本地内容带入目标树。

## 生成流程

1. 调用现有 install 发布清单生成流程，得到 `dist/superlooper-release-manifest.json`。
2. 读取 manifest，并确认 `release_mode` 为 `install`。
3. 读取 `release_files`；每条路径都必须是相对源码根的安全文件路径。
4. 校验 target 与 source root 不相等，且 target 不位于 source root 内。
5. 校验 target 不存在；已存在目录立即失败，不写入任何文件。
6. 在 target 同级创建 staging 目录，并在其中创建 `.claude-plugin/marketplace.json`。
7. 对每个 `release_files` 项逐文件复制 `<source-root>/<relative-path>` 到 staging 的 `plugins/superlooper/<relative-path>`，保留相对路径。
8. 比较 staging 中 `plugins/superlooper/` 的文件集合与 `release_files`，确保集合完全一致。
9. 以 `mkdir()` 原子创建 target 作为所有权声明；若 target 已被并行创建则失败，并把 staging 移入本次声明的 target。移动失败时只清理本次声明的 target 与 staging。

步骤 6 的 `marketplace.json` 是 marketplace 根元数据，不属于 Superlooper install plugin 的 `release_files`。除该 metadata 文件外，目标 `plugins/superlooper/` 不得包含 `release_files` 以外的文件。

## Marketplace 元数据边界

`.claude-plugin/marketplace.json` 描述 marketplace 与其插件条目，并引用 `plugins/superlooper/` 中的插件根。Superlooper 版本、名称和 Claude plugin 元数据仍由 `plugins/superlooper/.claude-plugin/plugin.json` 提供。

发布 tree 生成逻辑必须从 install manifest 与插件 manifest 读取必要事实，不复制或维护另一份 Superlooper 版本、文件白名单或插件组件路径定义。

## 真实 Claude Code E2E 范围

E2E 必须在独立临时位置准备 marketplace tree，并以 Claude Code 的真实 marketplace 安装路径验证。范围包括：

1. Claude Code 能识别 `.claude-plugin/marketplace.json` 中的 Superlooper 条目。
2. 从该 marketplace 安装后，安装目录包含 `release_files` 声明的全部且仅有这些 Superlooper 文件。
3. 已安装插件可被 Claude Code 加载，`/spl`、`/spl:doctor` 等已发布命令可见。
4. 在独立目标工作区执行 `/spl:doctor`，验证静态文件、脚本、schema 与发布过滤检查能够通过。
5. E2E 不以源码根直接加载代替 marketplace 安装，不以手工复制目录代替安装，也不把源码分发内容视为 install 成功证据。

E2E 环境中的用户配置、已安装插件和临时 marketplace 目录必须隔离，避免本机已有 Superlooper 安装掩盖发布树缺失文件的问题。

## 非目标

- 不迁移当前源码根或修改其 Claude Code plugin 结构。
- 不将 `source` release manifest 用作 marketplace tree 文件来源。
- 不在发布树生成过程中执行 Git 提交、推送或 GitHub 仓库管理。
- 不复制 `docs/design/`、`tests/`、`.superlooper/`、`.claude/`、`dist/`、环境文件或缓存内容。
- 不使用 `copytree`，不覆盖非空 target。

## 验收标准

| 验收项 | 通过条件 |
| --- | --- |
| 源码根不迁移 | 当前源码根继续通过 Claude Code plugin 严格校验，且生成目标位于独立目录。 |
| 文件集合 | `<target>/plugins/superlooper/` 的相对文件集合与 install manifest 的 `release_files` 完全一致。 |
| Marketplace 根结构 | target 同时存在 `.claude-plugin/marketplace.json` 与 `plugins/superlooper/`。 |
| 复制策略 | 生成实现逐文件复制 manifest 项，不调用 `copytree`。 |
| 路径保护 | source root、source root 子目录和非空 target 均被拒绝且不产生覆盖。 |
| 发布方式 | 生成的 target 可作为独立 GitHub marketplace 仓库工作树。 |
| 真实 E2E | 通过 Claude Code marketplace 安装后，命令发现与 `/spl:doctor` 均通过。 |
