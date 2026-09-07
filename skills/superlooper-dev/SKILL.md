---
description: Superlooper 插件源码开发入口。用于在修改本插件前自动读取开发上下文、保持标准 Claude Code plugin 结构，并避免偏离主调度协议。
---

# Superlooper 插件源码开发入口

本 skill 只用于开发和维护 Superlooper 插件源码，不用于执行 Superlooper AI 并行编排主流程。

> `/superlooper:superlooper-dev` 是历史源码开发辅助入口，不是插件安装后的公开用户入口。安装后的公开运行入口只使用 `/spl` 系列命令。

## 1. 使用方式

当用户在源码开发场景输入 `/superlooper:superlooper-dev <本轮开发需求>` 时，你必须把本文件作为开发入口，并在执行任何修改前读取开发上下文。不得把该入口写入面向插件使用者的公开运行文档。

示例：

```text
/superlooper:superlooper-dev 检查 README 是否还有旧目录描述
```

## 2. 开发前必须读取

执行任何代码、文档、配置或目录结构修改前，必须先读取：

```text
README.md
docs/DEVELOPMENT.md
skills/superlooper/SKILL.md
.claude-plugin/plugin.json
```

涉及 agent、脚本或契约时，再按修改对象读取相关文件：

| 修改对象 | 必须同时读取 |
| --- | --- |
| `agents/*.md` | `skills/superlooper/SKILL.md`、`docs/DEVELOPMENT.md` |
| `scripts/*.py` | `README.md`、`docs/DEVELOPMENT.md`、相关 `agents/*.md` |
| `schemas/*.json` | `scripts/validate_miao_contracts.py`、`agents/developer.md` |
| `.claude-plugin/plugin.json` | `README.md`、`docs/DEVELOPMENT.md` |
| `skills/superlooper/SKILL.md` | `README.md`、`docs/DEVELOPMENT.md`、`schemas/`、`scripts/validate_miao_contracts.py` |

## 3. 开发边界

- 不得恢复 plugin root 的 `CLAUDE.md` 作为运行上下文。
- 不得把插件静态 agent 放回 `.claude/agents/`。
- 不得把运行时 `.superlooper/` 内容提交为插件源码。
- 不得把动态模块 agent 直接写入插件静态 `agents/` 目录。
- 不得修改 `skills/superlooper/SKILL.md` 中的主体调度协议，除非用户明确批准。
- 不得把本机私有配置、令牌、密钥、内网地址写入插件文件。

## 4. 固定验收

修改完成后必须至少执行：

```bash
claude plugin validate . --strict
python -m py_compile scripts/validate_miao_contracts.py scripts/merge_artifacts.py scripts/apply_to_workspace.py
```

若 Python 编译生成 `scripts/__pycache__/`，该目录属于临时缓存，不进入发布源码。

## 5. 回复要求

任务完成后，回复必须包含：

- 修改过的文件路径。
- 执行过的验收命令。
- 验收输出或关键结果。
- 是否影响 Superlooper 主体调度协议。
