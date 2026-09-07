# Changelog

## 1.1.1

- Codex 运行链只从共享 `execution_manifest.json` 读取节点、依赖与 payload；不再生成或消费 `codex-dispatch.json`。
- 完整 Codex workflow 固定使用 non-ephemeral、`workspace-write` parent session，以便写入 `.superlooper/` 运行时产物；`task_apply_to_workspace` 仍受共享审查、合并、测试与冲突门禁约束。
- 共享 Schema 执行器在 module split、execution Manifest、artifact Manifest、interaction flow 和 session state 输入路径强制执行结构约束；doctor 改为内存编译、解析 Schema，并校验 Codex manifest skills 注册和 skill frontmatter。

## 1.1.0

- 将项目与双平台发布物许可证从 Apache-2.0 切换为 MIT。
- 新增 Codex Agent Plugin manifest；Claude Code 的 `/superlooper:spl`、既有七流程和动态 agent 注册协议保持不变。
- 同步 README、开发说明、发布指南和 Codex 使用说明，明确双平台 Marketplace metadata、安装生命周期、等价边界与双平台发布门禁。

## 1.0.1

- 修正 GitHub Marketplace 安装后的公开命令为 `/superlooper:spl` 系列；保留 `commands/spl*.md` 物理路径、`/spl...` internal canonical key 和七流程调度语义。

## 1.0.0

- 发布标准 Claude Code plugin manifest 与源码结构，固定 `.claude-plugin/plugin.json`、`skills/`、`commands/`、`agents/`、`schemas/`、`scripts/` 和文档目录边界。
- 提供 `/spl` 系列公开命令入口：`/spl`、`/spl:prd`、`/spl:ui`、`/spl:design`、`/spl:run`、`/spl:status`、`/spl:resume`、`/spl:doctor`；不提供 `/spl:manifest`。
- 建立 PRD、UI 设计、系统设计、项目初始化、模块拆分、执行摘要、动态 agent、代码审查、合并、测试、应用、交付报告和 PRD 反向需求校对闭环。
- 支持 `standard` 与 `strict_review` 工作模式，默认保留 PRD、UI、执行摘要和最终需求反向校对四个人工握手。
- 支持 active session 自然语言恢复、PRD/UI/设计反馈回退、代码审查失败返工、测试失败返工、apply 冲突重试和受控变更影响分析。
- 运行时根据模块拆分生成动态 `module_*` agent，并在运行时源文件和 Claude Code 注册入口写入一致的 `Runtime Module Constraints` 约束块。
- 发布 `scripts/validate_miao_contracts.py`、`scripts/generate_execution_manifest.py`、`scripts/generate_runtime_agents.py`、`scripts/run_execution_dag.py`、`scripts/merge_artifacts.py`、`scripts/apply_to_workspace.py`、`scripts/build_session_report.py` 等契约、执行、合并、应用和报告脚本。
- 增加 script 状态事件统一记录、DAG state runner、UI traceability 字段、UI 验收报告轻量正文审计和模块级 `brownfield-selective` 受控存量项目契约；完整扩展边界保留在 source-only 设计文档。
- 发布 source/install 两种分发模式，包含 release filtering、secret scan、manifest 与 zip 路径一致性校验、install artifact smoke test 和 `bin/spl doctor` 最小自检路由；install artifact 排除 source-only 的 `docs/design/` 设计文档。
