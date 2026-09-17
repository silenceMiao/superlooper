---
name: superlooper-doctor
summary: Run non-mutating Superlooper structural and task diagnostics.
description: Run non-mutating Superlooper structural and task diagnostics.
---

# Superlooper Doctor

Explicit invocation: `$superlooper-doctor [task_id]`.

在运行诊断前，必须在当前 non-ephemeral、read-only Codex parent session 执行 `python --version`，随后执行 `python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"` 断言 Python 3.9+。只有两条命令都成功后，才运行已安装插件根目录中的 `scripts/doctor.py --platform codex`。

不得将 `scripts/doctor.py` 作为工作区相对路径执行：从当前已加载的 `codex/skills/superlooper-doctor/SKILL.md` 所在目录向上三级定位 `plugin_root`（`../../..`），然后运行 `python "<plugin_root>/scripts/doctor.py" --workspace-root . --platform codex`；如传入 task ID，仅用于可选的 `.superlooper/` task contract diagnostic。

若任一 runtime probe 失败，报告 `Doctor 未启动：runtime prerequisite unavailable` 并停止；不得以局部静态检查替代完整 doctor，也不得报告 doctor 通过。不得通过重启系统、安装 runtime、修改 PATH 或修改 sandbox 自行修复该前置条件。

报告诊断结果时不得创建 task、推进 phase、修改生成产物或绕过任何共享契约检查。
