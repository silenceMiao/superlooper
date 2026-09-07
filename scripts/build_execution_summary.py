import argparse
import json
import os
import sys
from pathlib import Path

from create_session import (
    SessionStateValidationError,
    load_state_from_path,
    resolve_workspace_root,
    state_file_path,
    validate_session_id,
    write_state,
)
from update_session import append_event_log
from validate_miao_contracts import ContractError, ContractValidator


class ExecutionSummaryError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(description="Build SUPERLOOPER execution summary for user approval.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    parser.add_argument("--plugin-root", default=os.getenv("SUPERLOOPER_PLUGIN_ROOT"), help="插件源码或安装根目录，默认使用当前脚本所在插件根。")
    return parser.parse_args()


def read_json(path, label):
    if not path.exists():
        raise ExecutionSummaryError(f"{label} 不存在：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExecutionSummaryError(f"{label} JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise ExecutionSummaryError(f"{label} 顶层必须是 object。")
    return data


def validate_contracts(workspace_root, session_id, plugin_root):
    validator = ContractValidator(workspace_root, session_id, plugin_root=plugin_root)
    module_split_validated = True
    execution_manifest_validated = True
    upstream_alignment_data = None
    errors = []
    try:
        validator.validate_module_split(required=True)
        validator.validate_initialization_report(required=True)
    except ContractError as exc:
        module_split_validated = False
        errors.append(str(exc))
    if validator.errors:
        module_split_validated = False
        errors.extend(validator.errors)
        validator.errors = []
    try:
        validator.validate_execution_manifest(required=True)
    except ContractError as exc:
        execution_manifest_validated = False
        errors.append(str(exc))
    if validator.errors:
        execution_manifest_validated = False
        errors.extend(validator.errors)
        validator.errors = []
    try:
        upstream_alignment_data = validator.validate_upstream_alignment(required=True)
    except ContractError as exc:
        errors.append(str(exc))
    if validator.errors:
        errors.extend(validator.errors)
    return module_split_validated, execution_manifest_validated, upstream_alignment_data, errors


def collect_summary_data(workspace_root, session_id):
    manifests_dir = workspace_root / ".superlooper" / "manifests" / session_id
    reports_dir = workspace_root / ".superlooper" / "reports" / session_id
    module_split = read_json(manifests_dir / "module-split.json", "module-split.json")
    execution_manifest = read_json(manifests_dir / "execution_manifest.json", "execution_manifest.json")
    initialization_report = read_json(reports_dir / "initialization_report.json", "initialization_report.json")
    modules = module_split.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ExecutionSummaryError("module-split.modules 必须是非空数组。")
    module_count = len(modules)
    target_files = []
    for module in modules:
        if isinstance(module, dict) and isinstance(module.get("target_files"), list):
            target_files.extend(path for path in module["target_files"] if isinstance(path, str))
    nodes = execution_manifest.get("dag", {}).get("nodes", [])
    return {
        "module_split": module_split,
        "execution_manifest": execution_manifest,
        "initialization_report": initialization_report,
        "modules": modules,
        "module_count": module_count,
        "target_file_count": len(set(target_files)),
        "node_count": len(nodes) if isinstance(nodes, list) else 0,
    }


def yaml_list_block(key, values):
    lines = [f"{key}:"]
    for value in values:
        lines.append(f"  - {value}")
    return "\n".join(lines)


def build_report(session_id, state, data, module_split_validated, execution_manifest_validated, upstream_alignment_data, validation_errors):
    report_path = f".superlooper/reports/{session_id}/execution_summary.md"
    upstream_alignment_status = upstream_alignment_data.get("upstream_alignment_status") if isinstance(upstream_alignment_data, dict) else "BLOCKED"
    blocking_decisions = list(validation_errors)
    if isinstance(upstream_alignment_data, dict) and isinstance(upstream_alignment_data.get("blocking_decisions"), list):
        blocking_decisions.extend(str(item) for item in upstream_alignment_data["blocking_decisions"])
    status = "READY_FOR_APPROVAL" if module_split_validated and execution_manifest_validated and upstream_alignment_status == "PASS" and not validation_errors else "BLOCKED"
    modules = data["modules"]
    target_files = []
    for module in modules:
        if isinstance(module, dict) and isinstance(module.get("target_files"), list):
            target_files.extend(path for path in module["target_files"] if isinstance(path, str))
    module_lines = [f"- `{module.get('id')}`：{module.get('name', module.get('description', '未命名模块'))}" for module in modules if isinstance(module, dict)]
    target_lines = [f"- `{path}`" for path in sorted(set(target_files))]
    error_lines = [f"- {error}" for error in validation_errors] or ["- 无"]
    return (
        "```yaml\n"
        f"execution_summary_status: {status}\n"
        f"session_id: {session_id}\n"
        f"workflow_mode: {state['workflow_mode']}\n"
        f"project_category: {data['initialization_report'].get('project_category')}\n"
        f"project_version: {data['initialization_report'].get('project_version')}\n"
        f"module_count: {data['module_count']}\n"
        f"target_file_count: {data['target_file_count']}\n"
        f"risk_count: {len(blocking_decisions)}\n"
        f"{yaml_list_block('blocking_decisions', blocking_decisions)}\n"
        f"upstream_alignment_status: {upstream_alignment_status}\n"
        f"module_split_validated: {str(module_split_validated).lower()}\n"
        f"execution_manifest_validated: {str(execution_manifest_validated).lower()}\n"
        f"report_path: {report_path}\n"
        "```\n\n"
        "# Superlooper 执行摘要\n\n"
        "## 项目与流程\n\n"
        f"- workflow_mode: `{state['workflow_mode']}`\n"
        f"- project_category: `{data['initialization_report'].get('project_category')}`\n"
        f"- project_version: `{data['initialization_report'].get('project_version')}`\n"
        f"- module_count: `{data['module_count']}`\n"
        f"- execution_node_count: `{data['node_count']}`\n\n"
        "## PRD/UI/Design 一致性结论\n\n"
        f"- upstream_alignment_status: `{upstream_alignment_status}`\n"
        f"- module_split_validated: `{str(module_split_validated).lower()}`\n"
        f"- execution_manifest_validated: `{str(execution_manifest_validated).lower()}`\n\n"
        "## 模块列表\n\n"
        + ("\n".join(module_lines) if module_lines else "- 无")
        + "\n\n## 关键 target files\n\n"
        + ("\n".join(target_lines) if target_lines else "- 无")
        + "\n\n## 风险、冲突和不可逆动作\n\n"
        + "\n".join(error_lines)
        + "\n\n## 测试策略\n\n"
        "- 并行模块完成后进入 code-reviewer 门禁。\n"
        "- 合并后由 tester 执行集成测试与契约测试。\n"
        "- apply 前保留同路径不同内容文件阻断策略。\n\n"
        "## 用户确认动作\n\n"
        "- 通过：回复 `按此执行`。\n"
        "- 不通过：回复 `执行摘要未通过，返回修正：<反馈内容>`。\n"
    )


def update_state(workspace_root, session_id, state_path, state, report_path, status):
    updated = dict(state)
    updated["current_phase"] = "run"
    updated["phase_status"] = "waiting_review"
    updated["execution_summary_status"] = status
    updated["execution_summary_report"] = report_path
    updated["last_command"] = "build_execution_summary"
    updated["last_error"] = None if status == "READY_FOR_APPROVAL" else "execution_summary 生成时存在阻断项。"
    updated["next_actions"] = ["等待用户确认 execution_summary.md"] if status == "READY_FOR_APPROVAL" else ["修正执行摘要阻断项后重新生成 execution_summary.md"]
    reports = list(updated.get("reports", []))
    if report_path not in reports:
        reports.append(report_path)
    updated["reports"] = reports
    write_state(state_path, updated)
    append_event_log(workspace_root, updated)
    return updated


def run(args):
    session_id = validate_session_id(args.session_id)
    workspace_root = resolve_workspace_root(args.workspace_root)
    state_path = state_file_path(workspace_root, session_id)
    state = load_state_from_path(state_path)
    data = collect_summary_data(workspace_root, session_id)
    module_split_validated, execution_manifest_validated, upstream_alignment_data, validation_errors = validate_contracts(workspace_root, session_id, args.plugin_root)
    report = build_report(session_id, state, data, module_split_validated, execution_manifest_validated, upstream_alignment_data, validation_errors)
    report_path = f".superlooper/reports/{session_id}/execution_summary.md"
    absolute_report_path = workspace_root / report_path
    absolute_report_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_report_path.write_text(report, encoding="utf-8")
    validator = ContractValidator(workspace_root, session_id, plugin_root=args.plugin_root)
    summary_data = validator.validate_execution_summary(required=True)
    if validator.errors:
        raise ExecutionSummaryError("；".join(validator.errors))
    update_state(workspace_root, session_id, state_path, state, report_path, summary_data["execution_summary_status"])
    print(report_path)
    return 0


def main():
    args = parse_args()
    try:
        return run(args)
    except (ExecutionSummaryError, SessionStateValidationError, ContractError) as exc:
        print(f"生成 execution_summary 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
