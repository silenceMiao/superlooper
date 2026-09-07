# Superlooper 双平台安装态 E2E 证据

## 记录范围

- 记录日期：2026-09-01、2026-09-02。
- 发布版本：`1.1.0`。
- 初始候选来源：本地生成的双 metadata Marketplace tree；其 Claude manifest SHA-256 为 `c2f6ea2bae802fde144653678cf64a74a84e15d6a5a613fc5da5e6cdfad7f426`。
- 公开 Marketplace：[`silenceMiao/superAI-marketplace`](https://github.com/silenceMiao/superAI-marketplace)，发布提交 `2bfc9c26115e448cd59efb5cc3c8bf0810fab859`。
- CLI：Claude Code `2.1.258`，Codex CLI `0.151.0`。
- 边界：本记录覆盖插件安装、入口发现、doctor 与 PRD 审核握手；不覆盖模块编码、合并、测试、应用或最终需求反向校对。

## Claude Code E2E

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 隔离临时项目 | PASS | Claude Code 与 Codex 使用不同项目目录。 |
| 项目级本地 Marketplace 注册 | PASS | 在新的 `superlooper-claude-e2e-20260902` 项目执行 `claude plugin marketplace add --scope project ../superlooper-e2e-candidate-20260902-codex-doctor` 成功。 |
| 项目级插件安装 | PASS | `claude plugin install --scope project --yes superlooper@superAI-marketplace` 成功。 |
| `/superlooper:spl:doctor` | PASS | 通过新安装的 `1.1.0` 候选执行；结构、16 个脚本编译、命令、schema、发布过滤、Codex 结构检查均通过，未提供 session ID 时 session contract 按设计跳过。 |
| `/superlooper:spl requirements.md claude-dual-e2e-20260902` | PASS | 生成 `prd.md` 与 `upstream_alignment.md`，到达 PRD 审核握手。 |
| 安装态 YAML 上游对齐契约 | PASS | 安装 cache 中的 `validate_miao_contracts.py --scope upstream-alignment` 返回 0；报告的 `blocking_decisions: []` 被正确接受。 |
| PRD session state | PASS | `current_phase=prd`、`phase_status=waiting_review`，下一步为审核 PRD 后回复“通过，进入 UI 设计”。 |

Claude Code 运行过程出现一次 `superlooper:analyst` API stream error，但已生成的 PRD 与上游对齐报告未被覆盖。该偏差未阻断本次 PRD 审核握手证据。

## Claude Code validator 偏差与处置

原始安装态报告使用合法 YAML 内联空数组：

```yaml
blocking_decisions: []
```

旧版共享 validator 将该值当作字符串，错误输出 `upstream_alignment.blocking_decisions 必须是数组`。源码已增加回归测试并修复 `scripts/validate_miao_contracts.py` 的 `[]` 解析；修复后的源码已对本次真实报告执行 `--scope upstream-alignment`，结果通过。

已重新生成、在新的隔离项目按 project scope 安装并复验 `1.1.0` 候选。新的安装态 PRD 会话包含 `blocking_decisions: []`，安装 cache 中的共享 validator 已通过 `--scope upstream-alignment` 校验。因此 YAML 修复已取得新的 Claude Code 安装态证据。

## Codex E2E

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 本地 Marketplace 注册 | PASS | 本机 `superAI-marketplace` source 已切换到本轮生成的 `1.1.0` candidate。 |
| 安装态刷新 | PASS | 先执行 `codex plugin remove superlooper@superAI-marketplace`，再执行 `codex plugin add superlooper@superAI-marketplace`；实际激活 cache 已包含 `plugin_root` 定位规则。 |
| `$superlooper-doctor` runtime probe | PASS | 在 fresh、non-ephemeral、`read-only` Codex session 中，受控 runtime 返回 `Python 3.12.10`。 |
| `$superlooper-doctor` | PASS | 从已安装 plugin root 运行共享 `doctor.py --workspace-root . --platform codex`；9 项 PASS、`session_contract` 因未传 session ID 按设计 SKIPPED、0 项 FAIL。 |
| Codex read-only bytecode 边界 | PASS | `python_compile` 输出 `compiled 16 scripts`，没有向只读 plugin cache 写入 `__pycache__`。 |
| `$superlooper requirements.md codex-dual-e2e` | PASS | 在独立、`workspace-write` E2E 项目生成 PRD 和上游对齐报告。 |
| Codex PRD 产物契约 | PASS | `.superlooper/context/codex-dual-e2e/prd.md` 的首个 YAML 状态块为 `READY_FOR_DESIGN`，且 `blocking_decisions: []`。 |
| Codex PRD session state | PASS | `.superlooper/state/codex-dual-e2e.json` 为 `current_phase=prd`、`phase_status=waiting_review`。 |
| Codex PRD 审核握手 | PASS | 输入“通过，进入 UI 设计”被归一化为 `approve_and_proceed`，`resume_session.py` 返回下一步 `/spl:ui codex-dual-e2e`；本次 E2E 按范围未生成 UI 产物。 |

真实 read-only doctor 输出：

```text
python_compile: PASS - compiled 16 scripts
commands_contract: PASS - found 8 command files
schema_contract: PASS - found 5 schema files
agent_contract: PASS - found 10 agent files
forbidden_manifest_command: PASS - commands/spl/manifest.md is absent
release_filter: PASS - install release filter keeps runtime closure, excludes blocked paths, and scans secrets
session_contract: SKIPPED - session_id not provided
codex_plugin: PASS - Codex name, version, and license match Claude manifest
codex_skills: PASS - found 8 Codex skills
codex_dispatcher: PASS - Codex dispatcher declares the full DAG
```

## Codex runtime 与安装态修复

Windows Codex `read-only` session 不能执行宿主用户 profile 中的 Python，即使宿主 PowerShell 可以执行同一解释器。该现象是 sandbox 的运行时可见性边界，不是插件源码或 Marketplace tree 缺失 Python。

本次仅为隔离 E2E 工作区提供受控 Python 3.12 runtime，并只对每次 `codex exec` 通过临时 `PATH` 和 `PYTHONHOME` override 暴露它。未修改用户级 Codex 配置、未重启系统、未使用 `danger-full-access`、未开启全磁盘读取或环境变量全量继承。该 runtime 不在插件源码、install archive 或 Marketplace candidate 中。

首次真实安装态调用还发现两个插件缺陷：

1. Codex skill 将 `scripts/doctor.py` 当成目标工作区相对路径，导致隔离工作区找不到该文件。所有 Codex skill 现从已加载 `SKILL.md` 的 `../../..` 推导安装态 `plugin_root`，并以 `--workspace-root .` 调用共享 scripts。
2. `scripts/doctor.py` 的 `py_compile` 会尝试向只读 plugin cache 写入 `.pyc`。`--platform codex` 现用内存 `compile()` 进行语法检查；默认 Claude Code 分支继续使用原有 `py_compile`。

上述修复不改变共享 session state、Manifest、DAG、业务规则、质量门禁或七流程主体协议。

## 跨平台比对结论

已验证的共同契约：

- 都使用同一候选版本、同一共享 scripts、schema、`.superlooper/` 路径和 session state 格式。
- 两端均生成 PRD 与 `upstream_alignment.md`。
- 两端 PRD 会话均停在 `prd / waiting_review`。
- 两端均接受“通过，进入 UI 设计”作为 PRD 审核语义；Codex 返回显式下一 skill 调用，未自动生成 UI 产物。

不比较：`/` 与 `$` 入口字符、终端 UI、模型措辞、token 消耗、并发时序和完成时间。

## Task 10 发布后 E2E

### Claude Code 用户级安装态

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 用户级插件版本 | PASS | `claude plugin list` 显示 `superlooper@superAI-marketplace` 为 `1.1.0`、`Scope: user`、enabled。 |
| 新隔离项目入口 | PASS | 新项目通过 `/superlooper:spl:doctor` 执行安装 cache 中 `1.1.0` 的共享 doctor。 |
| `/superlooper:spl:doctor` | PASS | 10 个必需检查通过；`session_contract` 因未传 session ID 按设计 SKIPPED；退出码 `0`。 |
| `/superlooper:spl:prd requirements.md master-framework-20260902` | PASS | 生成 `prd.md` 与 `upstream_alignment.md`；首个 YAML 状态块为 `READY_FOR_DESIGN`，上游对齐为 `PASS`、`mismatch_count: 0`。 |
| PRD session state | PASS | `current_phase=prd`、`phase_status=waiting_review`。 |
| PRD 审核握手 | PASS | “通过，进入 UI 设计”归一化为 `approve_and_proceed`；建议下一入口为内部 canonical key `/spl:ui master-framework-20260902`，未生成 UI 产物。 |

首次 print-mode PRD 调用受 Claude Code 的 plan-mode Bash 写入确认阻断，只创建了 session。随后在同一隔离工作区使用 `acceptEdits` 与受限 Bash 授权完成运行时产物和状态写回；未修改 `requirements.md` 或 `.superlooper/` 外的文件。

### Codex 公开 Marketplace 安装态

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 公开 source 安装 cache | PASS | 实际加载路径为公开 Marketplace 的 `superlooper/1.1.0` cache，而非本地候选目录。 |
| runtime probe | PASS | 在新的 non-ephemeral、`read-only` Codex parent session 中，`python --version` 返回 `Python 3.12.10`。 |
| `$superlooper-doctor` | PASS | 从安装态 plugin root 运行共享 `doctor.py --workspace-root . --platform codex`；9 项 PASS、`session_contract` 按设计 SKIPPED、退出码 `0`。 |
| read-only 边界 | PASS | 未创建 session 或生成产物；`python_compile` 在内存中完成，未向只读 plugin cache 写入 `__pycache__`。 |

此次 Codex 调用仅通过一次性 `shell_environment_policy` 的 `core` 继承与受控 `PATH`、`PYTHONHOME` 注入 runtime；未修改用户级 Codex 配置、未使用 `danger-full-access`、未开启全磁盘读取、未全量继承环境变量，也未重启系统。受控 runtime 位于隔离 E2E 工作区，不在插件源码、install archive 或 Marketplace tree 中。

## 当前结论

Task 9 与 Task 10 的双平台安装态证据均已完成：公开 Marketplace 已提交并推送，Claude Code 用户级 `1.1.0` 与 Codex 公开 source `1.1.0` 均通过真实安装态 doctor；Claude Code 发布后 E2E 进一步完成 PRD 产物与审核握手。Codex 验证使用真实 `read-only` session 和受控临时 runtime，不依赖权限绕过或系统重启。

本记录未执行 E2E 临时目录清理；删除这些目录属于破坏性操作，需单独获得授权。
