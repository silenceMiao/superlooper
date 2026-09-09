# Superlooper Release Guide

## Release modes

`python scripts/package_plugin.py` 默认等价于 `python scripts/package_plugin.py --mode source`。

| 模式 | 用途 | `tests/` | `docs/design/` | 产物 |
| --- | --- | --- | --- | --- |
| `source` | 源码分发 | 保留 | 保留 | `dist/superlooper-release-manifest.json` |
| `install` | 安装分发 | 排除 | 排除 | `dist/superlooper-release-manifest.json` |

两种模式都始终保留 `.claude-plugin/plugin.json` 与 `.codex-plugin/plugin.json`。`docs/design/` 是源码开发和审计使用的后续增强设计文档，记录已实施最小能力与未实施扩展边界，不进入普通用户 install artifact。

发布清单还必须保留运行时必需文件：Claude Code 的 `commands/spl*.md` 与 `skills/superlooper/SKILL.md`，Codex 的八个 `codex/skills/*/SKILL.md` 与 `codex/dispatcher/README.md`，以及共享 `agents/`、`schemas/`、`docs/USER_GUIDE.md`、包含 `scripts/schema_validation.py` 的 `scripts/`、`bin/spl`。

## User install artifact contract

普通用户安装入口是 `superlooper-<version>-install.zip`。`source` 产物用于源码分发、审计和开发验证，不作为普通用户安装入口。

发布者在发布 install artifact 前必须确认 `docs/USER_GUIDE.md` 已进入 install closure，且源码 README 由该指南生成并覆盖以下用户路径：

- Claude Code 安装后在目标项目根目录运行 `/superlooper:spl:doctor`，首次运行 `/superlooper:spl <requirement_path> [session_id]`，并通过 `/superlooper:spl:resume <session_id>` 恢复旧 session。
- Codex 安装后在目标项目根目录运行 `$superlooper-doctor`，首次运行 `$superlooper <requirement_path> [session_id]`，并通过 `$superlooper-resume <session_id>` 恢复旧 session。
- Claude Code 升级后先运行 `/superlooper:spl:doctor` 再恢复旧 session；Codex 升级后先运行 `$superlooper-doctor` 再恢复旧 session。
- 卸载任一平台插件时不自动清理目标项目 `.superlooper/`；Claude Code 的 `.claude/agents/generated/superlooper/` 也保留供恢复、审计和交付追溯使用。
- 常见失败处理覆盖 Claude Code `/superlooper:spl` 不可见、Codex `$superlooper` 不可见、两个平台的 doctor 失败、需求文件缺失、多 active session 和 apply 冲突重试。

## Marketplace distribution

`superlooper` 是其版本、install 文件闭包和用户文档的事实源。`superAI-marketplace` 是独立的多插件发布市场：`plugins/superlooper/` 必须从 install manifest 派生，不得手工维护；根 README 和其他插件属于 Marketplace 仓库自身。

新建此前不存在的 Marketplace 时，维护者必须显式提供市场概览：

```bash
python scripts/package_marketplace.py \
  --target <new-marketplace> \
  --marketplace-readme <marketplace-overview.md>
```

`--target` 保持目标必须不存在的安全语义。命令在 target 同级 staging 中复制 install manifest 的 `release_files` 到 `plugins/superlooper/`，生成 Claude Code 与 Codex 的初始 registry、v2 账本，并原样复制 overview 为根 `README.md`。失败时只清理本次创建的 staging 或 target。

同步已有 v2 Marketplace：

```bash
python scripts/package_marketplace.py --sync-target ../superAI-marketplace
```

日常同步只替换 `plugins/superlooper/**`、两份 metadata 中唯一的 Superlooper 条目和 `.superlooper-marketplace-sync.json`。v2 账本只记录插件树文件 SHA-256；根 README、其他 metadata 条目、其他插件和 `.git/` 不属于同步器控制范围，也不会被覆盖。metadata 存在多个 Superlooper 条目、错误 Marketplace 名称、非数组 `plugins`、错误 source 或无效 version 时必须阻断。

已有 v1 账本的 Marketplace 必须先完整验证旧账本，再显式迁移：

```bash
python scripts/package_marketplace.py --sync-target ../superAI-marketplace --migrate-v1
```

迁移前旧根 README、metadata 或插件树存在任一漂移都会阻断；成功迁移后根 README 仍保持原样。Marketplace 维护者随后可将其恢复为市场概览，例如以 `89a4c57` 的 README 为基线。

没有账本的旧镜像只能经显式接管：

```bash
python scripts/package_marketplace.py --sync-target ../superAI-marketplace --adopt-existing
```

`--adopt-existing` 仅接管合法 Superlooper 插件树和双平台 registry，且不能与 `--migrate-v1` 同用。失败时根据冲突清单处理，禁止删除或覆盖来绕过校验。

在非源码临时目标项目执行真实 Claude Code Marketplace E2E 时，按以下顺序安装：

```text
/plugin marketplace add <owner>/superAI-marketplace
/plugin install superlooper@superAI-marketplace
```

安装后确认 `/superlooper:spl` 系列命令可见，在目标项目根目录先运行 `/superlooper:spl:doctor`，再运行 `/superlooper:spl requirements.md <session_id>` 并验收到达 PRD 审核握手。此步骤不能由 Python 文件复制测试或 `InstallArtifactSmokeTest` 替代。

在另一个隔离临时目标项目执行真实 Codex Marketplace E2E 时，按以下顺序安装：

```text
codex plugin marketplace add <owner>/superAI-marketplace --ref main
codex plugin add superlooper@superAI-marketplace
```

安装后确认八个 `$superlooper...` skill 可见，在目标项目根目录先运行 `$superlooper-doctor`，再运行 `$superlooper requirements.md <session_id>` 并验收到达同一 PRD 审核握手。Codex E2E 同样不能由 Python 文件复制测试、`InstallArtifactSmokeTest` 或 Claude Code E2E 替代。

## Release checks

P2 最小契约能力发布前必须确认：DAG state runner、script 状态事件、UI traceability、UI 验收报告轻量正文审计、模块级 `brownfield-selective` 字段和 install artifact 的 `docs/design/` 排除规则均已通过测试。

```bash
python -m unittest tests.test_package_plugin tests.test_doctor tests.test_package_marketplace tests.test_verify_release_consistency tests.test_codex_marketplace tests.test_cross_platform_equivalence
python scripts/package_plugin.py --mode source
python scripts/package_plugin.py --mode install
python scripts/build_release_archive.py --mode source
python scripts/build_release_archive.py --mode install
python -m unittest tests.test_package_plugin.InstallArtifactSmokeTest
python -m py_compile scripts/schema_validation.py scripts/validate_miao_contracts.py scripts/merge_artifacts.py scripts/apply_to_workspace.py scripts/initialize_project_structure.py scripts/generate_execution_manifest.py scripts/generate_runtime_agents.py scripts/build_execution_summary.py scripts/build_session_report.py scripts/doctor.py scripts/create_session.py scripts/update_session.py scripts/resume_session.py scripts/status_session.py scripts/normalize_user_intent.py scripts/package_plugin.py scripts/package_marketplace.py scripts/verify_release_consistency.py scripts/build_release_archive.py scripts/run_execution_dag.py
claude plugin validate . --strict
```

`python scripts/package_plugin.py --mode <mode>` 会先运行 `claude plugin validate . --strict`，再编译当前仓库 `scripts/*.py`，最后生成发布清单文件。

`python scripts/build_release_archive.py --mode <mode>` 会先复用 `PluginPackager(mode=<mode>)` 生成 manifest，再输出对应 zip 归档。

`python -m unittest tests.test_package_plugin.InstallArtifactSmokeTest` 会生成 install zip、解压到临时目录，并在解压后的 install artifact 根目录运行 `python bin/spl doctor`。该 smoke test 只验证安装产物完整性和最小自检能力，不代表真实 Claude Code 插件安装器 E2E。

发布前人工 E2E 必须分别在两个隔离临时目标项目中完成：Claude Code 安装 `superlooper-<version>-install.zip` 后确认 `/superlooper:spl` 系列命令可见，运行 `/superlooper:spl:doctor`，再用已存在的 `requirements.md` 运行 `/superlooper:spl requirements.md <session_id>` 到 PRD 审核握手点；Codex 从同一 Marketplace 安装后确认八个 `$superlooper...` skill 可见，运行 `$superlooper-doctor`，再运行 `$superlooper requirements.md <session_id>` 到同一握手点。任一平台的 E2E 失败时，阻断该版本的双平台发布。

## Real Claude Code install E2E acceptance

`InstallArtifactSmokeTest` 只验证 install zip 解包后的文件完整性和 `python bin/spl doctor` 最小自检能力，不代表真实 Claude Code 插件安装器 E2E。发布 `superlooper-<version>-install.zip` 前，发布者必须在临时目标项目中完成并记录真实 Claude Code 安装态 E2E。

### Required manual steps

1. 在非插件源码目录创建临时目标项目。
2. 准备已存在的 `requirements.md`。
3. 通过真实 Claude Code 插件安装机制安装 `superlooper-<version>-install.zip`。
4. 启动 Claude Code，确认 `/superlooper:spl`、`/superlooper:spl:doctor`、`/superlooper:spl:resume`、`/superlooper:spl:run` 系列命令可见。
5. 在临时目标项目根目录运行 `/superlooper:spl:doctor`。
6. 运行 `/superlooper:spl requirements.md <session_id>`。
7. 验收到达 PRD 审核握手点：输出 `.superlooper/context/<session_id>/prd.md`，并提示用户审核 PRD 后回复 `通过，进入 UI 设计`。

### Acceptance record template

| Item | Value |
| --- | --- |
| Date |  |
| OS |  |
| Claude Code version |  |
| Artifact | `superlooper-<version>-install.zip` |
| Artifact checksum |  |
| Temporary target project |  |
| Install method |  |
| `/superlooper:spl` commands visible | PASS/FAIL |
| `/superlooper:spl:doctor` | PASS/FAIL |
| `/superlooper:spl requirements.md <session_id>` reached PRD review handshake | PASS/FAIL |
| Evidence |  |
| Deviations / failures |  |

Boundary: this E2E stops at the PRD review handshake. It proves real Claude Code plugin installation, command discovery, doctor startup and first session entry. It does not prove full module implementation, merge, test, apply or final requirement alignment.

## Real Codex install E2E acceptance

Codex E2E 使用与 Claude Code E2E 不同的临时目标项目和 non-ephemeral、`workspace-write` parent session。它验证真实 Codex Marketplace 安装、skill discovery、doctor 与首次 session 入口，不以 Claude Code 安装结果推断兼容性。

### Required manual steps

1. 在非插件源码目录创建独立于 Claude Code E2E 的临时目标项目。
2. 准备已存在的 `requirements.md`。
3. 添加已发布的 Marketplace：`codex plugin marketplace add <owner>/superAI-marketplace --ref main`。
4. 安装插件：`codex plugin add superlooper@superAI-marketplace`。
5. 启动 Codex，确认 `$superlooper`、`$superlooper-doctor`、`$superlooper-resume`、`$superlooper-run` 等八个 skill 可见。
6. 在临时目标项目根目录运行 `$superlooper-doctor`。
7. 运行 `$superlooper requirements.md <session_id>`。
8. 验收到达 PRD 审核握手点：输出 `.superlooper/context/<session_id>/prd.md`，并提示用户审核 PRD 后回复 `通过，进入 UI 设计`。

### Acceptance record template

| Item | Value |
| --- | --- |
| Date |  |
| OS |  |
| Codex version |  |
| Marketplace commit |  |
| Plugin version |  |
| Temporary target project |  |
| Install method | `codex plugin marketplace add` + `codex plugin add` |
| Eight `$superlooper...` skills visible | PASS/FAIL |
| `$superlooper-doctor` | PASS/FAIL |
| `$superlooper requirements.md <session_id>` reached PRD review handshake | PASS/FAIL |
| Evidence |  |
| Deviations / failures |  |

Boundary: this E2E stops at the PRD review handshake. It does not prove full module implementation, merge, test, apply or final requirement alignment. A release cannot be promoted as dual-platform compatible until both this record and the Claude Code record are PASS.

## Files excluded from release

两种模式都排除以下内容：

- `.superlooper/`
- `.claude/`
- `.learnings/`
- `docs/superpowers/`
- `dist/`
- `__pycache__/`
- `.env`
- `.env.*`

额外规则：

- `source` 模式保留 `tests/` 和 `docs/design/`。
- `install` 模式排除 `tests/` 和 `docs/design/`。
- `release_files` 只允许使用项目根目录相对路径，不允许出现本机绝对路径。

## Release manifest contract

发布清单文件固定输出到 `dist/superlooper-release-manifest.json`，发布前必须核对：

- `release_mode` 与实际命令一致。
- `workspace_root` 固定为 `.`。
- `validation_commands` 是可复现命令字符串，不包含本机绝对路径。
- `release_files` 只包含相对路径，不包含本机绝对路径。
- `release_files` 包含 `.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`、Claude Code 命令和主 skill、八个 Codex skill、Codex dispatcher 及共享运行时必需文件。
- `install` 模式的 `release_files` 不包含 `tests/` 或 `docs/design/`，但解压后的 install artifact 必须能运行 `python bin/spl doctor`。

## Archive command

```bash
python scripts/build_release_archive.py --mode source
python scripts/build_release_archive.py --mode install
```

归档文件输出规则：

- `dist/superlooper-<version>-source.zip`
- `dist/superlooper-<version>-install.zip`

zip 内部路径必须与 release manifest 中 `release_files` 完全一致。

## Secret scan contract

发布前 secret scan 至少拦截以下模式：

- `Authorization: Bearer <token>`
- `access_key = <value>` / `access_key: <value>`
- `secret_key = <value>` / `secret_key: <value>`
- `private_key = <value>` / `private_key: <value>`
- `-----BEGIN PRIVATE` + ` KEY-----`
- JDBC URL credential，例如 `jdbc:mysql://<user>:<password>@host/db`
- URL credential，例如 `https://<user>:<password>@host/path`

仅列出字段名或占位符时不构成阻断，例如 `<token>`、`<value>`。

## Command contract

Claude Code 公开命令前缀是 `/superlooper:spl`；Codex 公开 skill 前缀是 `$superlooper`。Claude command 文件和 `configs/interaction-flow.json` 中的 `/spl...` 是内部 canonical key，不是用户直接输入的命令。Codex 的 `$` 是 skill 显式触发标记，不是 slash command。

发布物不提供 `/superlooper:spl:manifest` 或 `$superlooper-manifest`。两个平台都将 Manifest 生成功能归入运行入口：`/superlooper:spl:run` 或 `$superlooper-run`。不得为任一平台暴露其他历史长前缀或第二套业务协议。

## Version update workflow

1. 同步更新 `.claude-plugin/plugin.json` 与 `.codex-plugin/plugin.json` 的 `version`，并保持版本与 `CHANGELOG.md` 一致。
2. 核对两个 manifest 的 `name`、`version` 和 `license` 相同，且 `LICENSE` 仍为完整 MIT License。
3. 复核 README 用户路径：Claude Code 与 Codex 的安装、首次会话、doctor、resume、升级、卸载和失败处理均准确。
4. 复核公开入口：Claude Code 只使用 `/superlooper:spl...`，Codex 只使用八个 `$superlooper...` skill；不得新增 manifest 独立入口。
5. 在项目根目录运行 release checks，并审阅生成的 Marketplace tree 同时包含两份 metadata 与两份 plugin manifest。
6. 打开 release manifest JSON，确认本文件中的 manifest contract，尤其是 install closure、MIT license 与 release filter。
7. 只发布 release manifest JSON 或对应归档列出的文件；不得带入 `.superlooper/`、`.claude/`、`.learnings/`、缓存、测试、私有配置或密钥。
8. 在两个独立临时项目完成 Claude Code 与 Codex E2E；任一平台失败时停止双平台发布。
9. 打包后 spot check 最终 artifact 与 Marketplace tree，确认 Claude command 文件仍位于 `commands/spl.md` 和 `commands/spl/*.md`，Codex skill 仍位于 `codex/skills/`。

## 发布一致性检查

本地候选必须按以下顺序验证：

```bash
python scripts/render_user_readme.py --source docs/USER_GUIDE.md --destination README.md --audience source --check
python scripts/package_plugin.py --mode source
python scripts/package_plugin.py --mode install
python scripts/build_release_archive.py --mode source
python scripts/build_release_archive.py --mode install
python -m unittest tests.test_package_plugin.InstallArtifactSmokeTest
python scripts/package_marketplace.py --sync-target ../superAI-marketplace
python scripts/verify_release_consistency.py --marketplace ../superAI-marketplace
python -m unittest tests.test_package_marketplace.MarketplaceDoctorSmokeTest
```

推送前只把通过上述检查的内容视为本地候选。真实 Claude Code 与 Codex Marketplace 安装 E2E 必须使用已推送的远程候选，不能由文件复制测试或 install artifact smoke 替代。

Git 提交与推送需要当轮明确授权。两个独立仓库都完成授权的提交与推送后，运行：

```bash
python scripts/verify_release_consistency.py --marketplace ../superAI-marketplace --require-pushed --source-branch main --marketplace-branch main
```

该命令只读取 Git 状态、HEAD、origin 和远程分支。它不执行仓库初始化、remote 修改、commit、push、pull、merge 或 reset。两个 remote HEAD 均等于本地 HEAD，且同步账本 `source_commit` 等于源码 HEAD 时，才可宣布版本已发布完成。

## Rollback

1. If a version update is not released yet, revert the synchronized version changes in `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`, then revert the matching `CHANGELOG.md` entry in the same patch.
2. If `python scripts/package_plugin.py --mode <mode>` or `python scripts/build_release_archive.py --mode <mode>` generated an invalid manifest or archive, fix the source files first, then rerun the command. Do not publish the old artifact.
3. If a published artifact exposes a forbidden Claude command or Codex skill entry, remove that artifact from the release candidate, restore the public entry set to `/superlooper:spl...` and `$superlooper...`, then regenerate the release manifest and both Marketplace metadata files.
4. If a published artifact contains local path traces, runtime files, development files or secret-bearing content, stop distribution immediately, regenerate the package after cleanup, and verify the new manifest does not contain forbidden paths.
5. After rollback, rerun the full release checks and both platform E2E records, then compare the new manifest and Marketplace tree with the previous candidate before publishing again.
