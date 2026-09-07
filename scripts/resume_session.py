import argparse
import json
import os
import sys

from create_session import (
    SessionStateValidationError,
    load_state_from_path,
    resolve_workspace_root,
    state_file_path,
    validate_session_id,
    write_state,
)
from normalize_user_intent import INITIALIZATION_OPTIONS, initialization_category_from_input, initialization_version_from_input, normalize_user_intent
from update_session import append_event_log
from validate_miao_contracts import ContractValidator


class SessionResumeError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(description="Resolve the next action for a SUPERLOOPER session.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    parser.add_argument("--user-input", help="用户自然语言输入。")
    return parser.parse_args()


def join_actions(actions):
    if not actions:
        return "无"
    return "；".join(str(action) for action in actions)


def print_header(state):
    print(f"session_id: {state['session_id']}")
    print(f"current_phase: {state['current_phase']}")
    print(f"phase_status: {state['phase_status']}")


def print_failed(state):
    print_header(state)
    print(f"last_error: {state['last_error']}")
    print(f"next_step: 修复失败原因后重试；建议动作：{join_actions(state['next_actions'])}")


def print_blocked(state):
    print_header(state)
    print(f"block_reason: {state['last_error']}")
    print(f"manual_action: {join_actions(state['next_actions'])}")


def feedback_report_for_action(action):
    if action == "prd_revision_requested":
        return "prd_feedback.md", "prd"
    if action == "ui_revision_requested":
        return "ui_feedback.md", "ui_design"
    if action == "design_revision_requested":
        return "design_feedback.md", "design"
    if action == "change_impact_requested":
        return "change_feedback.md", None
    if action == "execution_summary_revision_requested":
        return "execution_summary_feedback.md", "design"
    if action == "requirement_alignment_revision_requested":
        return "change_feedback.md", "requirement_alignment"
    if action == "code_review_revision_requested":
        return "code_review_feedback.md", "run"
    if action == "test_revision_requested":
        return "test_feedback.md", "run"
    return None, None


def write_feedback_report(workspace_root, state, normalized):
    filename, rollback_target_phase = feedback_report_for_action(normalized["canonical_action"])
    if filename is None:
        return None, rollback_target_phase
    session_id = state["session_id"]
    report_path = workspace_root / ".superlooper" / "reports" / session_id / filename
    report_path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "# Superlooper 用户反馈\n\n"
        f"- session_id: {session_id}\n"
        f"- current_phase: {state['current_phase']}\n"
        f"- phase_status: {state['phase_status']}\n"
        f"- canonical_action: {normalized['canonical_action']}\n"
        f"- canonical_reply: {normalized['canonical_reply']}\n\n"
        "## 原始输入\n\n"
        f"{normalized['feedback']}\n"
    )
    report_path.write_text(content, encoding="utf-8")
    return f".superlooper/reports/{session_id}/{filename}", rollback_target_phase


def pending_choice_from_normalized(normalized):
    if not normalized.get("requires_choice"):
        return None
    return {
        "feedback": normalized["feedback"],
        "choice_options": normalized["choice_options"],
        "reason": normalized["reason"],
    }


def validate_execution_summary_approval(workspace_root, state):
    session_id = state["session_id"]
    expected = f".superlooper/reports/{session_id}/execution_summary.md"
    report = state.get("execution_summary_report")
    if not report:
        return "execution_summary_report 尚未写入 session state。"
    if str(report).replace("\\", "/") != expected:
        return f"execution_summary_report 必须为 {expected}。"
    validator = ContractValidator(workspace_root, session_id)
    data = validator.validate_execution_summary(required=True)
    if validator.errors:
        return "；".join(validator.errors)
    if not isinstance(data, dict) or data.get("execution_summary_status") != "READY_FOR_APPROVAL":
        return "execution_summary.md 必须为 READY_FOR_APPROVAL。"
    return None


def validate_requirement_alignment_approval(workspace_root, state):
    session_id = state["session_id"]
    expected = f".superlooper/reports/{session_id}/requirement_alignment_report.md"
    report = state.get("requirement_alignment_report")
    if not report:
        return "requirement_alignment_report 尚未写入 session state。"
    if str(report).replace("\\", "/") != expected:
        return f"requirement_alignment_report 必须为 {expected}。"
    validator = ContractValidator(workspace_root, session_id)
    data = validator.validate_requirement_alignment_report(required=True)
    if validator.errors:
        return "；".join(validator.errors)
    if not isinstance(data, dict) or data.get("requirement_alignment_status") != "PASS":
        return "requirement_alignment_report 必须为 PASS。"
    if int(data.get("unmet_requirement_count", -1)) != 0:
        return "requirement_alignment_report PASS 时 unmet_requirement_count 必须为 0。"
    if int(data.get("unchecked_acceptance_count", -1)) != 0:
        return "requirement_alignment_report PASS 时 unchecked_acceptance_count 必须为 0。"
    return None


def read_yaml_status_report(workspace_root, state, filename):
    report_path = workspace_root / ".superlooper" / "reports" / state["session_id"] / filename
    if not report_path.exists():
        return None, f"{filename} 不存在：{report_path}"
    validator = ContractValidator(workspace_root, state["session_id"])
    data = validator._read_first_yaml_block(report_path)
    if validator.errors:
        return None, "；".join(validator.errors)
    if not isinstance(data, dict):
        return None, f"{filename} 缺少机器可读状态块。"
    if data.get("session_id") != state["session_id"]:
        return None, f"{filename} session_id 与当前 session_id 不一致。"
    return data, None


def read_json_report(workspace_root, state, filename):
    report_path = workspace_root / ".superlooper" / "reports" / state["session_id"] / filename
    if not report_path.exists():
        return None, f"{filename} 不存在：{report_path}"
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"读取 JSON 报告失败：{report_path}: {exc}"
    if not isinstance(data, dict):
        return None, f"{filename} 顶层必须是 object。"
    if data.get("session_id") != state["session_id"]:
        return None, f"{filename} session_id 与当前 session_id 不一致。"
    return data, None


def append_invalidated_artifacts(state, paths):
    existing = list(state.get("invalidated_artifacts") or [])
    for path in paths:
        if path not in existing:
            existing.append(path)
    return existing


def validate_code_review_rework(workspace_root, state):
    data, error = read_yaml_status_report(workspace_root, state, "code_review_report.md")
    if error:
        return None, error
    if data.get("code_review_status") != "FAIL":
        return None, "code_review_report.md 必须为 FAIL 才能进入代码审查返工。"
    return data, None


def validate_test_rework(workspace_root, state):
    data, error = read_yaml_status_report(workspace_root, state, "test_report.md")
    if error:
        return None, error
    if data.get("test_status") != "FAIL":
        return None, "test_report.md 必须为 FAIL 才能进入测试返工。"
    return data, None


def validate_apply_retry(workspace_root, state):
    data, error = read_json_report(workspace_root, state, "apply_conflict_report.json")
    if error:
        return None, error
    if data.get("status") != "conflict":
        return None, "apply_conflict_report.json.status 必须为 conflict。"
    conflicts = data.get("conflicts")
    if not isinstance(conflicts, list) or not conflicts:
        return None, "apply_conflict_report.json.conflicts 必须是非空数组。"
    return data, None


def validate_apply_report_gate(workspace_root, state):
    validator = ContractValidator(workspace_root, state["session_id"])
    validator.validate_apply_report(required=True)
    if validator.errors:
        return "；".join(validator.errors)
    return None


def validate_local_rerun_approval(workspace_root, state):
    validator = ContractValidator(workspace_root, state["session_id"])
    data = validator.validate_change_impact_report(required=True)
    if validator.errors:
        return None, "；".join(validator.errors)
    if not isinstance(data, dict):
        return None, "change_impact_report.md 缺少机器可读状态块。"
    if data.get("change_impact_status") != "PASS":
        return None, "change_impact_report.md 必须为 PASS。"
    if data.get("local_rerun_allowed") not in (True, "true"):
        return None, "change_impact_report.md 必须允许 local_rerun_allowed。"
    return data, None


def write_upstream_alignment_feedback(workspace_root, state, alignment):
    session_id = state["session_id"]
    report_path = workspace_root / ".superlooper" / "reports" / session_id / "upstream_alignment_feedback.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    blocking_decisions = alignment.get("blocking_decisions") if isinstance(alignment.get("blocking_decisions"), list) else []
    content = (
        "# Superlooper 上游自校对反馈\n\n"
        f"- session_id: {session_id}\n"
        f"- current_phase: {state['current_phase']}\n"
        f"- upstream_alignment_status: {alignment.get('upstream_alignment_status')}\n"
        f"- loop_target_phase: {alignment.get('loop_target_phase')}\n"
        f"- mismatch_count: {alignment.get('mismatch_count')}\n\n"
        "## blocking_decisions\n\n"
        + ("\n".join(f"- {item}" for item in blocking_decisions) if blocking_decisions else "- 无")
        + "\n"
    )
    report_path.write_text(content, encoding="utf-8")
    return f".superlooper/reports/{session_id}/upstream_alignment_feedback.md"


def apply_upstream_alignment_loop(workspace_root, state_path, state):
    if state.get("phase_status") != "running" or state.get("current_phase") not in {"prd", "ui_design", "design", "initialization", "run", "requirement_alignment"}:
        return None
    report_path = workspace_root / ".superlooper" / "reports" / state["session_id"] / "upstream_alignment.md"
    if not report_path.exists():
        return None
    validator = ContractValidator(workspace_root, state["session_id"])
    alignment = validator.validate_upstream_alignment(required=True)
    if validator.errors:
        updated = dict(state)
        updated["phase_status"] = "blocked"
        updated["last_error"] = "；".join(validator.errors)
        updated["next_actions"] = ["修正 upstream_alignment.md 后继续"]
        write_state(state_path, updated)
        append_event_log(workspace_root, updated)
        return updated
    if not isinstance(alignment, dict):
        return None
    status = alignment.get("upstream_alignment_status")
    if status == "PASS":
        return None
    updated = dict(state)
    loop_state = dict(updated.get("loop_state") or {})
    loop_count_by_phase = dict(loop_state.get("loop_count_by_phase") or {})
    target_phase = alignment.get("loop_target_phase")
    loop_state["current_loop_target_phase"] = target_phase
    loop_state["last_alignment_status"] = status
    if status == "BLOCKED":
        decisions = alignment.get("blocking_decisions") if isinstance(alignment.get("blocking_decisions"), list) else []
        updated["phase_status"] = "blocked"
        updated["loop_state"] = loop_state
        updated["last_error"] = "；".join(str(item) for item in decisions)
        updated["next_actions"] = ["处理 upstream_alignment.md 中的 blocking_decisions 后继续"]
    elif status == "FAIL" and alignment.get("loop_required") in (True, "true"):
        current_count = int(loop_count_by_phase.get(target_phase, 0))
        max_count = int((updated.get("loop_policy") or {}).get("max_auto_loop_per_phase", 0))
        if current_count >= max_count:
            updated["phase_status"] = "blocked"
            updated["loop_state"] = loop_state
            updated["last_error"] = f"{target_phase} 已达到自动 loop 上限 {max_count}。"
            updated["next_actions"] = ["人工处理 upstream_alignment.md 后继续"]
        else:
            feedback_report = write_upstream_alignment_feedback(workspace_root, updated, alignment)
            loop_count_by_phase[target_phase] = current_count + 1
            loop_state["loop_count_by_phase"] = loop_count_by_phase
            loop_state["last_feedback_report"] = feedback_report
            updated["current_phase"] = target_phase
            updated["phase_status"] = "pending"
            updated["loop_state"] = loop_state
            updated["active_feedback_report"] = feedback_report
            updated["rollback_target_phase"] = target_phase
            updated["last_error"] = None
            updated["next_actions"] = [f"按 upstream_alignment_feedback.md 重新运行 {target_phase} 阶段"]
    write_state(state_path, updated)
    append_event_log(workspace_root, updated)
    return updated


def apply_continue_current_flow(workspace_root, state):
    updated = dict(state)
    session_id = updated["session_id"]
    current_phase = updated.get("current_phase")
    phase_status = updated.get("phase_status")
    if current_phase == "design" and phase_status == "waiting_review":
        module_split = workspace_root / ".superlooper" / "manifests" / session_id / "module-split.json"
        if updated.get("project_initialized") is not True:
            updated["phase_status"] = "blocked"
            updated["last_error"] = "project_initialized 必须为 true 才能继续到执行清单。"
            updated["next_actions"] = ["先完成系统设计、项目结构初始化和 module-split.json 生成"]
        elif updated.get("ui_status") != "APPROVED" or updated.get("ui_artifacts_validated") is not True:
            updated["phase_status"] = "blocked"
            updated["last_error"] = "UI 尚未审核通过或 ui_artifacts_validated 不是 true。"
            updated["next_actions"] = ["先完成 UI 审核并校验 UI 产物"]
        elif not module_split.exists():
            updated["phase_status"] = "blocked"
            updated["last_error"] = f"module-split.json 不存在：.superlooper/manifests/{session_id}/module-split.json"
            updated["next_actions"] = ["先完成模块拆分清单生成和校验"]
        else:
            updated["current_phase"] = "run"
            updated["phase_status"] = "pending"
            updated["last_error"] = None
            updated["next_actions"] = [f"运行 /spl:run {session_id} 生成执行清单和执行摘要"]
        return updated
    if current_phase == "run" and phase_status == "waiting_review" and updated.get("execution_summary_status") == "READY_FOR_APPROVAL":
        updated["next_actions"] = ["等待用户审核 execution_summary.md；通过请回复 按此执行，未通过请回复 执行摘要未通过，返回修正"]
        return updated
    if current_phase == "run" and phase_status == "blocked":
        apply_report = workspace_root / ".superlooper" / "reports" / session_id / "apply_report.json"
        if apply_report.exists():
            apply_error = validate_apply_report_gate(workspace_root, updated)
            if apply_error:
                updated["last_error"] = apply_error
                updated["next_actions"] = ["修复 apply_report.json 中的 workspace_validation 失败项后重新应用"]
                return updated
    return updated


def apply_user_input(workspace_root, state_path, state, user_input):
    normalized = normalize_user_intent(state, user_input)
    updated = dict(state)
    updated["last_user_input_text"] = normalized["feedback"]
    updated["last_user_canonical_action"] = normalized["canonical_action"]
    updated["pending_user_choice"] = pending_choice_from_normalized(normalized)
    feedback_report, rollback_target_phase = write_feedback_report(workspace_root, state, normalized)
    if feedback_report is not None:
        updated["active_feedback_report"] = feedback_report
        updated["change_request_count"] = updated.get("change_request_count", 0) + 1
    if rollback_target_phase is not None:
        updated["rollback_target_phase"] = rollback_target_phase
    if normalized["canonical_action"] == "prd_decisions_confirmed":
        updated["phase_status"] = "running"
        updated["last_error"] = None
        updated["next_actions"] = ["调用 analyst 基于已确认 DEC-* 重新生成 PRD"]
    elif normalized["canonical_action"] == "continue_current_flow":
        updated = apply_continue_current_flow(workspace_root, updated)
    elif normalized["canonical_action"] == "prd_revision_requested":
        updated["prd_revision"] = updated.get("prd_revision", 0) + 1
        if state.get("current_phase") == "ui_design":
            updated["current_phase"] = "prd"
            updated["phase_status"] = "running"
            updated["ui_status"] = "CHANGES_REQUESTED"
            updated["ui_artifacts_validated"] = False
        updated["next_actions"] = ["调用 analyst 按反馈重新生成 PRD"]
    elif normalized["canonical_action"] == "ui_revision_requested":
        updated["ui_revision"] = updated.get("ui_revision", 0) + 1
        updated["ui_status"] = "CHANGES_REQUESTED"
        updated["ui_artifacts_validated"] = False
        updated["next_actions"] = ["调用 ui-architect 按反馈重新生成 UI 设计"]
    elif normalized["canonical_action"] == "approve_ui_and_proceed":
        if updated.get("ui_artifacts_validated") is not True:
            updated["ui_status"] = "BLOCKED"
            updated["phase_status"] = "blocked"
            updated["last_error"] = "UI 产物尚未通过 ui-artifacts 校验"
            updated["next_actions"] = ["先运行 /spl:ui 生成并校验 UI 产物"]
        else:
            updated["ui_status"] = "APPROVED"
            updated["ui_output_dir"] = updated.get("ui_output_dir") or f".superlooper/context/{updated['session_id']}/ui/"
            updated["current_phase"] = "design"
            updated["phase_status"] = "pending"
            updated["next_actions"] = ["运行 /spl:design 进入系统设计阶段"]
    elif normalized["canonical_action"] == "select_project_category":
        category = initialization_category_from_input(normalized["feedback"])
        updated["project_category"] = category
        updated["project_version"] = None
        versions = "/".join(INITIALIZATION_OPTIONS[category])
        updated["last_error"] = None
        updated["next_actions"] = [f"请选择 {category} 的初始化版本：{versions}"]
    elif normalized["canonical_action"] == "select_project_version":
        version = initialization_version_from_input(normalized["feedback"])
        updated["project_version"] = version
        updated["last_error"] = None
        updated["next_actions"] = ["运行初始化脚本完成项目结构初始化"]
    elif normalized["canonical_action"] == "design_revision_requested":
        updated["design_revision"] = updated.get("design_revision", 0) + 1
        updated["next_actions"] = ["调用 architect 按反馈重新生成设计文档"]
    elif normalized["canonical_action"] == "change_impact_requested":
        updated["next_actions"] = ["调用 impact-analyzer 生成 change_impact_report.md"]
    elif normalized["canonical_action"] == "execution_summary_revision_requested":
        updated["execution_summary_status"] = "REJECTED"
        updated["design_revision"] = updated.get("design_revision", 0) + 1
        updated["next_actions"] = ["使用 active_feedback_report 回到设计或执行摘要生成链路修正"]
    elif normalized["canonical_action"] == "execution_summary_approved":
        approval_error = validate_execution_summary_approval(workspace_root, updated)
        if approval_error:
            updated["phase_status"] = "blocked"
            updated["execution_summary_status"] = "BLOCKED"
            updated["last_error"] = approval_error
            updated["next_actions"] = ["先生成并校验 execution_summary.md"]
        else:
            updated["execution_summary_status"] = "APPROVED"
            updated["phase_status"] = "running"
            updated["last_error"] = None
            updated["next_actions"] = ["按执行摘要确认结果开始并行开发"]
    elif normalized["canonical_action"] == "start_execution":
        approval_error = validate_execution_summary_approval(workspace_root, updated)
        if approval_error:
            updated["phase_status"] = "blocked"
            updated["execution_summary_status"] = "BLOCKED"
            updated["last_error"] = approval_error
            updated["next_actions"] = ["先生成并校验 execution_summary.md"]
        else:
            updated["execution_summary_status"] = "APPROVED"
            updated["phase_status"] = "running"
            updated["last_error"] = None
            updated["next_actions"] = ["按执行摘要确认结果开始并行开发"]
    elif normalized["canonical_action"] == "code_review_revision_requested":
        review_data, review_error = validate_code_review_rework(workspace_root, updated)
        if review_error:
            updated["phase_status"] = "blocked"
            updated["last_error"] = review_error
            updated["next_actions"] = ["先生成并校验 code_review_report.md"]
        else:
            report_path = f".superlooper/reports/{updated['session_id']}/code_review_report.md"
            updated["current_phase"] = "run"
            updated["phase_status"] = "pending"
            updated["rollback_target_phase"] = "run"
            updated["invalidated_artifacts"] = append_invalidated_artifacts(
                updated,
                [
                    report_path,
                    f".superlooper/reports/{updated['session_id']}/merge_report.json",
                    f".superlooper/reports/{updated['session_id']}/test_report.md",
                    f".superlooper/reports/{updated['session_id']}/apply_report.json",
                    f".superlooper/reports/{updated['session_id']}/session_report.md",
                    f".superlooper/reports/{updated['session_id']}/requirement_alignment_report.md",
                ],
            )
            updated["last_error"] = None
            updated["next_actions"] = ["按 code_review_report.md 和 active_feedback_report 修正受影响模块产物后重新执行代码审查"]
    elif normalized["canonical_action"] == "test_revision_requested":
        test_data, test_error = validate_test_rework(workspace_root, updated)
        if test_error:
            updated["phase_status"] = "blocked"
            updated["last_error"] = test_error
            updated["next_actions"] = ["先生成并校验 test_report.md"]
        else:
            report_path = f".superlooper/reports/{updated['session_id']}/test_report.md"
            updated["current_phase"] = "run"
            updated["phase_status"] = "pending"
            updated["rollback_target_phase"] = "run"
            updated["invalidated_artifacts"] = append_invalidated_artifacts(
                updated,
                [
                    report_path,
                    f".superlooper/reports/{updated['session_id']}/apply_report.json",
                    f".superlooper/reports/{updated['session_id']}/session_report.md",
                    f".superlooper/reports/{updated['session_id']}/requirement_alignment_report.md",
                ],
            )
            updated["last_error"] = None
            updated["next_actions"] = ["按 test_report.md 和 active_feedback_report 修正模块产物后重新 merge/test"]
    elif normalized["canonical_action"] == "apply_retry_requested":
        conflict_data, conflict_error = validate_apply_retry(workspace_root, updated)
        if conflict_error:
            updated["phase_status"] = "blocked"
            updated["last_error"] = conflict_error
            updated["next_actions"] = ["先基于 apply_conflict_report.json 处理冲突或取得具体 overwrite 授权"]
        else:
            conflict_paths = [item.get("path") for item in conflict_data.get("conflicts", []) if isinstance(item, dict) and item.get("path")]
            updated["current_phase"] = "run"
            updated["phase_status"] = "pending"
            updated["rollback_target_phase"] = "run"
            updated["invalidated_artifacts"] = append_invalidated_artifacts(
                updated,
                [
                    f".superlooper/reports/{updated['session_id']}/apply_conflict_report.json",
                    f".superlooper/reports/{updated['session_id']}/apply_report.json",
                    f".superlooper/reports/{updated['session_id']}/session_report.md",
                    f".superlooper/reports/{updated['session_id']}/requirement_alignment_report.md",
                ],
            )
            updated["last_error"] = None
            updated["next_actions"] = ["重新调用 workspace_applier；未获授权不得覆盖未确认路径：" + ", ".join(conflict_paths)]
    elif normalized["canonical_action"] == "local_rerun_approved":
        impact_data, impact_error = validate_local_rerun_approval(workspace_root, updated)
        if impact_error:
            updated["phase_status"] = "blocked"
            updated["last_error"] = impact_error
            updated["next_actions"] = ["先生成并校验 change_impact_report.md"]
        else:
            target_phase = impact_data["rollback_target_phase"]
            affected_artifacts = impact_data.get("affected_artifacts") or []
            updated["current_phase"] = target_phase
            updated["phase_status"] = "pending"
            updated["rollback_target_phase"] = target_phase
            updated["invalidated_artifacts"] = append_invalidated_artifacts(updated, affected_artifacts)
            updated["last_error"] = None
            updated["next_actions"] = [f"按 change_impact_report.md 只重跑 {target_phase} 阶段和受影响模块"]
    elif normalized["canonical_action"] == "manual_handling_requested":
        updated["phase_status"] = "blocked"
        updated["last_error"] = "用户要求人工处理 change_impact_report.md。"
        updated["next_actions"] = ["停止自动执行，等待人工处理"]
    elif normalized["canonical_action"] == "requirement_alignment_revision_requested":
        updated["phase_status"] = "blocked"
        updated["last_error"] = "需求反向校对未通过，必须先执行影响分析。"
        updated["next_actions"] = ["调用 impact-analyzer 分析需求校对失败影响范围"]
    elif normalized["canonical_action"] == "requirement_alignment_approved":
        approval_error = validate_requirement_alignment_approval(workspace_root, updated)
        if approval_error:
            updated["phase_status"] = "blocked"
            updated["requirement_alignment_passed"] = False
            updated["last_error"] = approval_error
            updated["next_actions"] = ["先生成并校验 requirement_alignment_report.md"]
        else:
            updated["current_phase"] = "report"
            updated["phase_status"] = "passed"
            updated["requirement_alignment_passed"] = True
            updated["last_error"] = None
            updated["next_actions"] = [f"查看 .superlooper/reports/{updated['session_id']}/session_report.md"]
    write_state(state_path, updated)
    append_event_log(workspace_root, updated)
    return normalized, updated


def print_normalized_action(workspace_root, state, normalized):
    print_header(state)
    print(f"canonical_action: {normalized['canonical_action']}")
    print(f"canonical_reply: {normalized['canonical_reply']}")
    print(f"confidence: {normalized['confidence']}")
    print(f"reason: {normalized['reason']}")
    if normalized.get("requires_choice"):
        print("choice_options:")
        for option in normalized.get("choice_options", []):
            print(f"- {option}")
        print("next_step: 当前输入需要选择下一步动作；不会重新启动完整流程。")
        return
    action = normalized["canonical_action"]
    session_id = state["session_id"]
    if action == "prd_decisions_confirmed":
        print("next_step: 重新调用 analyst 生成 PRD，不重新启动完整流程。")
        return
    if action == "prd_revision_requested":
        print("next_step: 使用 active_feedback_report 重新调用 analyst，不重新启动完整流程。")
        return
    if action == "design_revision_requested":
        print("next_step: 使用 active_feedback_report 重新调用 architect，不重新启动完整流程。")
        return
    if action == "change_impact_requested":
        print("next_step: 调用 impact-analyzer 生成 change_impact_report.md，等待人工确认后再局部重跑。")
        return
    if action == "approve_and_proceed":
        print(f"next_step: /spl:ui {session_id}")
        return
    if action == "ui_revision_requested":
        print("next_step: 使用 active_feedback_report 重新调用 ui-architect，不重新启动完整流程。")
        return
    if action == "approve_ui_and_proceed":
        if state.get("ui_artifacts_validated") is not True:
            print("next_step: 先运行 /spl:ui 生成并校验 UI 产物。")
            return
        print(f"next_step: /spl:design {session_id}")
        return
    if action == "select_project_category":
        print("next_step: 选择初始化版本。")
        return
    if action == "select_project_version":
        print("next_step: 运行初始化脚本完成项目结构初始化。")
        return
    if action == "execution_summary_revision_requested":
        print("next_step: 使用 active_feedback_report 回到设计或执行摘要生成链路修正。")
        return
    if action == "execution_summary_approved":
        print(f"next_step: /spl:run {session_id}，按执行摘要确认结果启动并行开发。")
        return
    if action == "start_execution":
        print(f"next_step: /spl:run {session_id}，按当前执行清单启动并行开发。")
        return
    if action == "requirement_alignment_approved":
        if state.get("current_phase") == "report" and state.get("phase_status") == "passed":
            print("next_step: 进入最终验收报告输出。")
        else:
            print("next_step: 先生成并校验 requirement_alignment_report.md。")
        return
    if action == "code_review_revision_requested":
        print("next_step: 按 code_review_report.md 和 active_feedback_report 修正受影响模块产物后重新执行代码审查。")
        return
    if action == "test_revision_requested":
        print("next_step: 按 test_report.md 和 active_feedback_report 修正模块产物后重新 merge/test。")
        return
    if action == "apply_retry_requested":
        print("next_step: 重新调用 workspace_applier，不直接输出完成结论。")
        return
    if action == "requirement_alignment_revision_requested":
        print("next_step: 调用 impact-analyzer 分析需求校对失败影响范围，不重新启动完整流程。")
        return
    if action == "local_rerun_approved":
        print("next_step: 按 change_impact_report.md 声明范围执行局部重跑，不重启完整流程。")
        return
    if action == "manual_handling_requested":
        print("next_step: 停止自动执行，等待人工处理 change_impact_report.md。")
        return
    print_mapped_next_step(workspace_root, state)


def print_mapped_next_step(workspace_root, state):
    session_id = state["session_id"]
    current_phase = state["current_phase"]
    phase_status = state["phase_status"]
    requirement_path = state["requirement_path"]
    print_header(state)

    if current_phase == "prd" and phase_status == "pending":
        print(f"next_step: /spl:prd {requirement_path} {session_id}")
        return
    if current_phase == "prd" and phase_status == "waiting_review":
        print("next_step: 等待用户审核 PRD；通过回复 通过，进入 UI 设计；未通过回复 PRD未通过，按反馈重新分析：<反馈内容>")
        return
    if current_phase == "ui_design" and phase_status == "pending":
        print(f"next_step: /spl:ui {session_id}")
        return
    if current_phase == "ui_design" and phase_status == "running":
        print("next_step: 等待 UI 设计阶段输出完成。")
        return
    if current_phase == "ui_design" and phase_status == "waiting_review":
        print("next_step: 等待用户审核 UI 设计和 preview.html；通过回复 UI设计通过，进入系统设计；未通过回复 UI设计未通过，按反馈重新设计：<反馈内容>；需求变化回复 需求变更，返回 PRD 修订：<反馈内容>")
        return
    if current_phase == "ui_design" and phase_status in {"blocked", "failed"}:
        print("next_step: 查看 UI 阶段错误或阻塞原因，修复后重新运行 /spl:ui <session_id>。")
        return
    if current_phase == "design" and phase_status == "pending":
        print(f"next_step: /spl:design {session_id}")
        return
    if current_phase == "design" and phase_status == "waiting_review":
        print("next_step: 等待用户审核设计；通过回复 继续任务 或 生成执行清单；未通过回复 设计未通过，按反馈重新设计：<反馈内容>；初始化后变更回复 需求变更，执行影响分析：<反馈内容>")
        return
    if current_phase == "initialization" and phase_status == "waiting_review":
        if state.get("project_category") is None:
            print("next_step: 请选择初始化项目分类：java/go/springboot/pom/lua")
            return
        if state.get("project_version") is None:
            print(f"next_step: 请选择 {state['project_category']} 的初始化版本")
            return
        if state.get("project_initialized") is not True:
            print("next_step: 运行初始化脚本完成项目结构初始化")
            return
    if current_phase == "requirement_alignment" and phase_status == "waiting_review":
        if state.get("change_impact_report"):
            print("next_step: 等待用户审核 change_impact_report.md；回复 影响分析通过，执行局部重跑 或 影响分析不通过，人工处理")
            return
        print("next_step: 等待用户审核 requirement_alignment_report.md；通过回复 需求校对通过，完成交付；未通过回复 需求校对未通过，返回修正：<反馈内容>")
        return
    if current_phase == "run" and phase_status == "pending":
        print(f"next_step: /spl:run {session_id}")
        return
    if current_phase == "run" and phase_status == "waiting_review":
        if state.get("change_impact_report"):
            print("next_step: 等待用户审核 change_impact_report.md；回复 影响分析通过，执行局部重跑 或 影响分析不通过，人工处理")
            return
        if state.get("execution_summary_status") == "READY_FOR_APPROVAL":
            print("next_step: 等待用户确认 execution_summary.md；通过回复 按此执行；未通过回复 执行摘要未通过，返回修正：<反馈内容>")
            return
        print("next_step: 等待用户确认执行清单预览；审核通过回复 执行 或 开始并行开发；变更回复 需求变更，执行影响分析：<反馈内容>")
        return
    if current_phase == "run" and phase_status == "running":
        print("next_step: 等待执行完成或检查报告；若代码审查失败，回复 代码审查未通过，返回修正；若测试失败，回复 测试未通过，返回修正；若需求、UI 或设计变更，回复 需求变更，执行影响分析：<反馈内容>")
        return
    if current_phase == "run" and phase_status == "blocked":
        conflict_report = workspace_root / ".superlooper" / "reports" / session_id / "apply_conflict_report.json"
        apply_report = workspace_root / ".superlooper" / "reports" / session_id / "apply_report.json"
        if conflict_report.exists():
            print("next_step: 处理 apply_conflict_report.json 中的冲突；处理完成或取得授权后回复 应用冲突已处理，重新应用。")
            return
        if apply_report.exists():
            print("next_step: 修复 apply_report.json 中的 workspace_validation 失败项后重新应用。")
            return
    if current_phase == "report" and phase_status == "passed":
        report_path = workspace_root / ".superlooper" / "reports" / session_id / "session_report.md"
        print(f"next_step: {report_path}")
        return

    print(f"next_step: {join_actions(state['next_actions'])}")


def main():
    args = parse_args()
    try:
        session_id = validate_session_id(args.session_id)
        workspace_root = resolve_workspace_root(args.workspace_root)
        path = state_file_path(workspace_root, session_id)
        state = load_state_from_path(path)
        if args.user_input is not None:
            normalized, updated = apply_user_input(workspace_root, path, state, args.user_input)
            print_normalized_action(workspace_root, updated, normalized)
            return 0
        loop_updated = apply_upstream_alignment_loop(workspace_root, path, state)
        if loop_updated is not None:
            print_mapped_next_step(workspace_root, loop_updated)
            return 0
        phase_status = state["phase_status"]
        if phase_status == "failed":
            print_failed(state)
            return 0
        if phase_status == "blocked":
            print_blocked(state)
            return 0
        print_mapped_next_step(workspace_root, state)
        return 0
    except (SessionStateValidationError, SessionResumeError) as exc:
        print(f"恢复 session 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
