---
description: 检查 Superlooper 插件结构、agent、schema、脚本和发布风险。
argument-hint: "[task_id]"
allowed-tools: Read, Bash, Glob, Grep
---

# /superlooper:spl:doctor

`/superlooper:spl:doctor` 是插件只读自检入口，不推进 Superlooper 业务流程。

用户参数：`$ARGUMENTS`

执行规则：

1. 在当前实际 Agent 会话执行 `python --version`，随后执行 `python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"` 断言 Python 3.9+。任一命令失败时，报告 `Doctor 未启动：runtime prerequisite unavailable` 并停止；不得以局部静态检查替代完整 doctor，不得报告 doctor 通过，也不得重启系统、安装 runtime、修改 PATH 或修改 sandbox。
2. probe 成功后，本文件中的 `python "${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py" ...` 均表示插件根内脚本路径；安装态目标项目当前目录不要求存在 `scripts/`，目标项目根必须通过 `--workspace-root <workspace_root>` 传入。
3. 执行 `python "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --workspace-root <workspace_root>`；脚本默认用自身位置推导插件根目录，`workspace_root` 只表示目标项目根目录。
4. 如果传入 `task_id`，执行 `python "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --workspace-root <workspace_root> --task-id <task_id>`。
5. `scripts/doctor.py` 内部必须覆盖以下检查：`claude plugin validate . --strict`、`scripts/*.py` 编译、`/spl` 系列命令文件存在性、禁止 `commands/spl/manifest.md`、install 发布过滤与 secret scan、可选 task contract 校验。
6. 输出逐项检查结果，不创建 task、不推进 phase、不修改生成产物，不改变 `skills/superlooper/SKILL.md` 七流程主体调度语义。

输出必须包含：

- 插件结构校验结果
- Python 脚本语法校验结果
- 命令文件检查结果
- schema 文件检查结果
- 发布风险检查结果
- task contract 检查结果
