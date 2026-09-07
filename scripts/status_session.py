import argparse
import os
import sys

from create_session import (
    SessionStateValidationError,
    load_state_from_path,
    resolve_workspace_root,
    state_file_path,
    validate_session_id,
)


class SessionStatusError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(description="Show SUPERLOOPER session status.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    return parser.parse_args()


def print_list(label, values):
    print(f"{label}:")
    if not values:
        print("- (none)")
        return
    for value in values:
        print(f"- {value}")


def print_script_events(values):
    print("script_events:")
    if not values:
        print("- (none)")
        return
    for event in values[-5:]:
        print(f"- {event['script']}:{event['status']}:{event['idempotency_key']}")


def print_state_summary(state):
    print(f"session_id: {state['session_id']}")
    print(f"current_phase: {state['current_phase']}")
    print(f"phase_status: {state['phase_status']}")
    print(f"project_mode: {state['project_mode']}")
    print(f"workflow_mode: {state['workflow_mode']}")
    print(f"project_category: {state['project_category']}")
    print(f"project_version: {state['project_version']}")
    print(f"project_root: {state['project_root']}")
    print(f"project_initialized: {state['project_initialized']}")
    print(f"initialization_report: {state['initialization_report']}")
    print(f"execution_summary_status: {state['execution_summary_status']}")
    print(f"execution_summary_report: {state['execution_summary_report']}")
    print(f"loop_policy: {state['loop_policy']}")
    print(f"loop_state: {state['loop_state']}")
    print(f"requirement_alignment_report: {state['requirement_alignment_report']}")
    print(f"requirement_alignment_passed: {state['requirement_alignment_passed']}")
    print(f"prd_revision: {state['prd_revision']}")
    print(f"ui_revision: {state['ui_revision']}")
    print(f"ui_status: {state['ui_status']}")
    print(f"ui_output_dir: {state['ui_output_dir']}")
    print(f"ui_artifacts_validated: {state['ui_artifacts_validated']}")
    print(f"design_revision: {state['design_revision']}")
    print(f"change_request_count: {state['change_request_count']}")
    print(f"active_feedback_report: {state['active_feedback_report']}")
    print(f"change_impact_report: {state['change_impact_report']}")
    print(f"rollback_target_phase: {state['rollback_target_phase']}")
    print(f"last_user_input_text: {state['last_user_input_text']}")
    print(f"last_user_canonical_action: {state['last_user_canonical_action']}")
    print(f"pending_user_choice: {state['pending_user_choice']}")
    print_list("invalidated_artifacts", state["invalidated_artifacts"])
    print_list("generated_files", state["generated_files"])
    print_list("reports", state["reports"])
    print_script_events(state["script_events"])
    print(f"last_error: {state['last_error']}")
    print_list("next_actions", state["next_actions"])


def print_available_sessions(state_dir):
    if not state_dir.exists():
        print("available_sessions:")
        print("- (none)")
        return
    session_files = sorted(path.stem for path in state_dir.glob("*.json") if path.is_file())
    print("available_sessions:")
    if not session_files:
        print("- (none)")
        return
    for session_id in session_files:
        print(f"- {session_id}")


def main():
    args = parse_args()
    workspace_root = None
    state_dir = None
    try:
        session_id = validate_session_id(args.session_id)
        workspace_root = resolve_workspace_root(args.workspace_root)
        state_dir = workspace_root / ".superlooper" / "state"
        state = load_state_from_path(state_file_path(workspace_root, session_id))
        print_state_summary(state)
        return 0
    except (SessionStateValidationError, SessionStatusError) as exc:
        print(f"读取 session 状态失败：{exc}", file=sys.stderr)
        if state_dir is None and workspace_root is not None:
            state_dir = workspace_root / ".superlooper" / "state"
        if state_dir is not None:
            print_available_sessions(state_dir)
        return 1


if __name__ == "__main__":
    sys.exit(main())
