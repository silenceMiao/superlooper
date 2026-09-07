import argparse
import json
import os
import re
import sys
from pathlib import Path

from create_session import (
    SessionStateValidationError,
    load_state_from_path,
    resolve_workspace_root,
    state_file_path,
    validate_session_id,
    validate_session_state,
    write_state,
)


class SessionUpdateError(Exception):
    pass


EVENT_SECRET_PATTERNS = [
    re.compile(r"(Authorization\s*:\s*Bearer\s+)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"((?:token|secret|password|api_key|access_key|secret_key)\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Update SUPERLOOPER session state.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    parser.add_argument("--current-phase", required=True, help="当前阶段。")
    parser.add_argument("--phase-status", required=True, help="阶段状态。")
    parser.add_argument("--last-command", required=True, help="最近执行命令。")
    parser.add_argument("--generated-file", action="append", default=[], help="新增生成文件，相对路径，可重复传入。")
    parser.add_argument("--report", action="append", default=[], help="新增报告文件，相对路径，可重复传入。")
    parser.add_argument("--record-script-event", action="append", default=[], help="记录脚本事件，格式为 <script_name>:<status>:<idempotency_key>，可重复传入。")
    parser.add_argument("--last-error", help="最近错误信息。")
    parser.add_argument("--next-action", action="append", default=[], help="下一步动作，可重复传入。")
    parser.add_argument("--project-mode", choices=["greenfield", "brownfield", "brownfield-selective", "single_change", "ambiguous"])
    parser.add_argument("--workflow-mode", choices=["standard", "strict_review"])
    parser.add_argument("--project-category", choices=["java", "go", "springboot", "pom", "lua"])
    parser.add_argument("--project-version", choices=["jdk-8", "jdk-11", "jdk-17", "go-1.25", "springboot-2.x", "springboot-3.x", "maven-3.5.x", "maven-3.9.x", "lua-4.x", "lua-5.x"])
    parser.add_argument("--project-root")
    parser.add_argument("--project-initialized", choices=["true", "false"])
    parser.add_argument("--initialization-report")
    parser.add_argument("--execution-summary-status", choices=["NOT_STARTED", "READY_FOR_APPROVAL", "APPROVED", "REJECTED", "BLOCKED"])
    parser.add_argument("--execution-summary-report")
    parser.add_argument("--loop-policy-json")
    parser.add_argument("--loop-state-json")
    parser.add_argument("--requirement-alignment-report")
    parser.add_argument("--requirement-alignment-passed", choices=["true", "false"])
    parser.add_argument("--prd-revision", type=int)
    parser.add_argument("--ui-revision", type=int)
    parser.add_argument("--ui-status", choices=["NOT_STARTED", "IN_PROGRESS", "READY_FOR_REVIEW", "CHANGES_REQUESTED", "APPROVED", "BLOCKED", "FAILED"])
    parser.add_argument("--ui-output-dir")
    parser.add_argument("--ui-artifacts-validated", choices=["true", "false"])
    parser.add_argument("--design-revision", type=int)
    parser.add_argument("--change-request-count", type=int)
    parser.add_argument("--active-feedback-report")
    parser.add_argument("--change-impact-report")
    parser.add_argument("--invalidated-artifact", action="append", default=[])
    parser.add_argument("--rollback-target-phase", choices=["prd", "ui_design", "design", "initialization", "run", "requirement_alignment"])
    parser.add_argument("--last-user-input-text")
    parser.add_argument("--last-user-canonical-action")
    parser.add_argument("--pending-user-choice-json")
    return parser.parse_args()


def merge_unique(existing_values, new_values):
    merged = []
    seen = set()
    for value in [*existing_values, *new_values]:
        if not isinstance(value, str):
            raise SessionUpdateError("generated_files/reports 只能包含字符串。")
        normalized = value.strip()
        if not normalized:
            raise SessionUpdateError("generated_files/reports 不能包含空字符串。")
        if normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return merged


def normalize_next_actions(values):
    actions = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            raise SessionUpdateError("next_actions 只能包含字符串。")
        normalized = value.strip()
        if not normalized:
            raise SessionUpdateError("next_actions 不能包含空字符串。")
        if normalized in seen:
            continue
        seen.add(normalized)
        actions.append(normalized)
    return actions


def merge_script_events(existing_events, raw_events):
    events = list(existing_events)
    seen = {event.get("idempotency_key") for event in events if isinstance(event, dict)}
    for raw_event in raw_events:
        parts = raw_event.split(":", 2)
        if len(parts) != 3:
            raise SessionUpdateError("script event 格式必须为 <script_name>:<status>:<idempotency_key>。")
        script, status, idempotency_key = [part.strip() for part in parts]
        if not script or not idempotency_key:
            raise SessionUpdateError("script event 的 script_name 和 idempotency_key 不能为空。")
        if status not in {"started", "completed", "failed"}:
            raise SessionUpdateError(f"script event status 不合法：{status}")
        if idempotency_key in seen:
            continue
        seen.add(idempotency_key)
        events.append({"script": script, "status": status, "idempotency_key": idempotency_key})
    return events


def apply_updates(state, args):
    updated = dict(state)
    updated["current_phase"] = args.current_phase
    updated["phase_status"] = args.phase_status
    updated["last_command"] = args.last_command
    updated["last_error"] = args.last_error
    updated["generated_files"] = merge_unique(state.get("generated_files", []), args.generated_file)
    updated["reports"] = merge_unique(state.get("reports", []), args.report)
    updated["script_events"] = merge_script_events(state.get("script_events", []), args.record_script_event)
    updated["next_actions"] = normalize_next_actions(args.next_action)
    if args.project_mode is not None:
        updated["project_mode"] = args.project_mode
    if args.workflow_mode is not None:
        updated["workflow_mode"] = args.workflow_mode
    if args.project_category is not None:
        updated["project_category"] = args.project_category
    if args.project_version is not None:
        updated["project_version"] = args.project_version
    if args.project_root is not None:
        updated["project_root"] = args.project_root
    if args.project_initialized is not None:
        updated["project_initialized"] = args.project_initialized == "true"
    if args.initialization_report is not None:
        updated["initialization_report"] = args.initialization_report
    if args.execution_summary_status is not None:
        updated["execution_summary_status"] = args.execution_summary_status
    if args.execution_summary_report is not None:
        updated["execution_summary_report"] = args.execution_summary_report
    if args.loop_policy_json is not None:
        try:
            loop_policy = json.loads(args.loop_policy_json)
        except json.JSONDecodeError as exc:
            raise SessionUpdateError(f"loop_policy JSON 解析失败：{exc}") from exc
        if not isinstance(loop_policy, dict):
            raise SessionUpdateError("loop_policy 必须为 object。")
        updated["loop_policy"] = loop_policy
    if args.loop_state_json is not None:
        try:
            loop_state = json.loads(args.loop_state_json)
        except json.JSONDecodeError as exc:
            raise SessionUpdateError(f"loop_state JSON 解析失败：{exc}") from exc
        if not isinstance(loop_state, dict):
            raise SessionUpdateError("loop_state 必须为 object。")
        updated["loop_state"] = loop_state
    if args.requirement_alignment_report is not None:
        updated["requirement_alignment_report"] = args.requirement_alignment_report
    if args.requirement_alignment_passed is not None:
        updated["requirement_alignment_passed"] = args.requirement_alignment_passed == "true"
    if args.prd_revision is not None:
        updated["prd_revision"] = args.prd_revision
    if args.ui_revision is not None:
        updated["ui_revision"] = args.ui_revision
    if args.ui_status is not None:
        updated["ui_status"] = args.ui_status
    if args.ui_output_dir is not None:
        updated["ui_output_dir"] = args.ui_output_dir
    if args.ui_artifacts_validated is not None:
        updated["ui_artifacts_validated"] = args.ui_artifacts_validated == "true"
    if args.design_revision is not None:
        updated["design_revision"] = args.design_revision
    if args.change_request_count is not None:
        updated["change_request_count"] = args.change_request_count
    if args.active_feedback_report is not None:
        updated["active_feedback_report"] = args.active_feedback_report
    if args.change_impact_report is not None:
        updated["change_impact_report"] = args.change_impact_report
    if args.invalidated_artifact:
        updated["invalidated_artifacts"] = merge_unique(state.get("invalidated_artifacts", []), args.invalidated_artifact)
    if args.rollback_target_phase is not None:
        updated["rollback_target_phase"] = args.rollback_target_phase
    if args.last_user_input_text is not None:
        updated["last_user_input_text"] = args.last_user_input_text
    if args.last_user_canonical_action is not None:
        updated["last_user_canonical_action"] = args.last_user_canonical_action
    if args.pending_user_choice_json is not None:
        try:
            pending_user_choice = json.loads(args.pending_user_choice_json)
        except json.JSONDecodeError as exc:
            raise SessionUpdateError(f"pending_user_choice JSON 解析失败：{exc}") from exc
        if pending_user_choice is not None and not isinstance(pending_user_choice, dict):
            raise SessionUpdateError("pending_user_choice 必须为 object 或 null。")
        updated["pending_user_choice"] = pending_user_choice
    return validate_session_state(updated)


def event_log_path(workspace_root, session_id):
    return Path(workspace_root) / ".superlooper" / "events" / f"{session_id}.jsonl"


def redact_event_string(value):
    if not isinstance(value, str):
        return value
    redacted = value
    for pattern in EVENT_SECRET_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def redact_event_strings(values):
    return [redact_event_string(value) for value in values]


def build_event_record(state):
    return {
        "session_id": state["session_id"],
        "current_phase": state["current_phase"],
        "phase_status": state["phase_status"],
        "last_command": redact_event_string(state.get("last_command")),
        "last_error": redact_event_string(state.get("last_error")),
        "generated_files": redact_event_strings(state.get("generated_files", [])),
        "reports": redact_event_strings(state.get("reports", [])),
        "script_events": state.get("script_events", []),
        "next_actions": redact_event_strings(state.get("next_actions", [])),
        "workflow_mode": state.get("workflow_mode"),
        "execution_summary_status": state.get("execution_summary_status"),
        "execution_summary_report": redact_event_string(state.get("execution_summary_report")),
        "loop_policy": state.get("loop_policy"),
        "loop_state": state.get("loop_state"),
        "ui_revision": state.get("ui_revision"),
        "ui_status": state.get("ui_status"),
        "ui_output_dir": redact_event_string(state.get("ui_output_dir")),
        "ui_artifacts_validated": state.get("ui_artifacts_validated"),
        "active_feedback_report": redact_event_string(state.get("active_feedback_report")),
        "change_impact_report": redact_event_string(state.get("change_impact_report")),
        "invalidated_artifacts": redact_event_strings(state.get("invalidated_artifacts", [])),
        "rollback_target_phase": state.get("rollback_target_phase"),
        "last_user_input_text": redact_event_string(state.get("last_user_input_text")),
        "last_user_canonical_action": redact_event_string(state.get("last_user_canonical_action")),
        "pending_user_choice": state.get("pending_user_choice"),
    }


def append_event_log(workspace_root, state):
    path = event_log_path(workspace_root, state["session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(build_event_record(state), ensure_ascii=False) + "\n")


def main():
    args = parse_args()
    try:
        session_id = validate_session_id(args.session_id)
        workspace_root = resolve_workspace_root(args.workspace_root)
        path = state_file_path(workspace_root, session_id)
        state = load_state_from_path(path)
        if state.get("workspace_root") != str(workspace_root):
            raise SessionUpdateError("state.workspace_root 与传入 workspace_root 不一致，拒绝覆盖。")
        updated = apply_updates(state, args)
        if updated.get("workspace_root") != state.get("workspace_root"):
            raise SessionUpdateError("禁止覆盖 state.workspace_root。")
        if updated.get("requirement_path") != state.get("requirement_path"):
            raise SessionUpdateError("禁止覆盖 state.requirement_path。")
        write_state(path, updated)
        append_event_log(workspace_root, updated)
        print(path)
        return 0
    except (SessionStateValidationError, SessionUpdateError) as exc:
        print(f"更新 session 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
