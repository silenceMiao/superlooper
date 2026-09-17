import argparse
import os
import sys

from create_session import (
    SessionStateValidationError,
    load_state_from_path,
    resolve_explicit_task_id,
    resolve_workspace_root,
    state_file_path,
)


class SessionStatusError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(description="Show SUPERLOOPER task state.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--task-id", default=os.getenv("SUPERLOOPER_TASK_ID"), help="执行任务 ID。")
    parser.add_argument("--session-id", default=os.getenv("SUPERLOOPER_SESSION_ID"), help=argparse.SUPPRESS)
    parser.add_argument("--list-active", action="store_true", help="列出所有未完成 task；忽略 identity 环境变量。")
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
    print(f"task_id: {state['task_id']}")
    print(f"task_name: {state['task_name'] if state['task_name'] is not None else '(none)'}")
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
    print_list("affected_modules", state["affected_modules"])
    print_list("invalidated_artifacts", state["invalidated_artifacts"])
    print_list("generated_files", state["generated_files"])
    print_list("reports", state["reports"])
    print_script_events(state["script_events"])
    print(f"last_error: {state['last_error']}")
    print_list("next_actions", state["next_actions"])


def is_active_task(state):
    return not (state["current_phase"] == "report" and state["phase_status"] == "passed")


def load_active_tasks(state_dir):
    if not state_dir.exists():
        return []
    active_tasks = []
    for path in sorted(state_dir.glob("*.json")):
        if not path.is_file() or path.name.endswith(".dag.json"):
            continue
        try:
            state = load_state_from_path(path)
        except SessionStateValidationError as exc:
            raise SessionStatusError(f"{path.name}: {exc}") from exc
        if state["task_id"] != path.stem:
            raise SessionStatusError(f"{path.name}: state task_id 与文件名不一致。")
        if is_active_task(state):
            active_tasks.append(state)
    return active_tasks


def print_active_tasks(active_tasks):
    print("active_tasks:")
    if not active_tasks:
        print("- (none)")
        return
    for state in active_tasks:
        print(f"- task_name: {state['task_name'] if state['task_name'] is not None else '未命名任务'}")
        print(f"  task_id: {state['task_id']}")
        print(f"  current_phase: {state['current_phase']}")
        print(f"  phase_status: {state['phase_status']}")


def print_available_tasks(state_dir):
    if not state_dir.exists():
        print("available_tasks:")
        print("- (none)")
        return
    task_files = sorted(path.stem for path in state_dir.glob("*.json") if path.is_file())
    print("available_tasks:")
    if not task_files:
        print("- (none)")
        return
    for task_id in task_files:
        print(f"- {task_id}")


def main():
    args = parse_args()
    workspace_root = None
    state_dir = None
    try:
        workspace_root = resolve_workspace_root(args.workspace_root)
        state_dir = workspace_root / ".superlooper" / "state"
        if args.list_active:
            print_active_tasks(load_active_tasks(state_dir))
            return 0
        task_id = resolve_explicit_task_id(args.task_id, args.session_id, required=True)
        state = load_state_from_path(state_file_path(workspace_root, task_id))
        print_state_summary(state)
        return 0
    except (SessionStateValidationError, SessionStatusError) as exc:
        label = "读取 active task 失败" if args.list_active else "读取任务状态失败"
        print(f"{label}：{exc}", file=sys.stderr)
        if args.list_active:
            return 1
        if state_dir is None and workspace_root is not None:
            state_dir = workspace_root / ".superlooper" / "state"
        if state_dir is not None:
            print_available_tasks(state_dir)
        return 1


if __name__ == "__main__":
    sys.exit(main())
