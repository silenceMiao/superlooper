---
description: 检查 Superlooper 插件结构、agent、schema、脚本和发布风险。
argument-hint: "[session_id]"
allowed-tools: Read, Bash, Glob, Grep
---

# /superlooper:spl:doctor

`/superlooper:spl:doctor` 是插件自检入口，不推进 Superlooper 业务流程。

用户参数：`$ARGUMENTS`

执行规则：

1. 本文件中的 `python scripts/...` 均表示插件根内脚本路径；安装态目标项目当前目录不要求存在 `scripts/`，目标项目根必须通过 `--workspace-root <workspace_root>` 传入。
2. 优先执行 `python scripts/doctor.py --workspace-root <workspace_root>`；脚本默认用自身位置推导插件根目录，`workspace_root` 只表示目标项目根目录。
3. 如果传入 `session_id`，执行 `python scripts/doctor.py --workspace-root <workspace_root> --session-id <session_id>`。
4. `scripts/doctor.py` 内部必须覆盖以下检查：`claude plugin validate . --strict`、`scripts/*.py` 编译、`/spl` 系列命令文件存在性、禁止 `commands/spl/manifest.md`、install 发布过滤与 secret scan、可选 session 契约校验。
5. 输出逐项检查结果，不改变 `skills/superlooper/SKILL.md` 七流程主体调度语义。

输出必须包含：

- 插件结构校验结果
- Python 脚本语法校验结果
- 命令文件检查结果
- schema 文件检查结果
- 发布风险检查结果
- session 契约检查结果
