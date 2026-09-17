import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from schema_validation import SchemaValidationError, SchemaValidator


TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
TASK_ID_PREFIX = "master-framework-"
TASK_NAME_MAX_LENGTH = 120
PROTECTED_ROOTS = {".git", ".hg", ".svn"}
PROJECT_MODES = {"greenfield", "brownfield", "brownfield-selective", "single_change", "ambiguous"}
WORKFLOW_MODES = {"standard", "strict_review"}
EXECUTION_SUMMARY_STATUSES = {"NOT_STARTED", "READY_FOR_APPROVAL", "APPROVED", "REJECTED", "BLOCKED"}
ALIGNMENT_STATUSES = {"PASS", "FAIL", "BLOCKED"}
PROJECT_CATEGORIES = {"java", "go", "springboot", "pom", "lua"}
PROJECT_VERSIONS = {
    "jdk-8",
    "jdk-11",
    "jdk-17",
    "go-1.25",
    "springboot-2.x",
    "springboot-3.x",
    "maven-3.5.x",
    "maven-3.9.x",
    "lua-4.x",
    "lua-5.x",
}
ROLLBACK_TARGET_PHASES = {"prd", "ui_design", "design", "initialization", "run", "requirement_alignment"}
UI_STATUSES = {"NOT_STARTED", "IN_PROGRESS", "READY_FOR_REVIEW", "CHANGES_REQUESTED", "APPROVED", "BLOCKED", "FAILED"}


class SessionStateValidationError(Exception):
    pass


class SessionCreateError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(description="Create SUPERLOOPER runtime task directories and initial state.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--task-id", help="执行任务唯一 ID；缺省时按本地时间自动生成。")
    parser.add_argument("--session-id", help=argparse.SUPPRESS)
    parser.add_argument("--new-task", action="store_true", help="忽略 identity 环境变量并创建系统生成 ID 的新任务。")
    parser.add_argument("--task-name", help="可选任务名称，仅用于展示，可重复。")
    parser.add_argument("--requirement-path", required=True, help="原始需求文档路径。")
    parser.add_argument("--project-mode", choices=sorted(PROJECT_MODES), default="greenfield", help="项目模式，默认 greenfield。")
    return parser.parse_args()


def session_schema_path():
    return Path(__file__).resolve().parents[1] / "schemas" / "session-state.schema.json"


def load_session_schema():
    path = session_schema_path()
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SessionStateValidationError(f"读取 session schema 失败：{path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SessionStateValidationError(f"session schema JSON 解析失败：{path}: {exc}") from exc
    if not isinstance(schema, dict):
        raise SessionStateValidationError("session schema 顶层必须是 object。")
    return schema


def session_phase_values(schema=None):
    schema = schema or load_session_schema()
    values = schema.get("properties", {}).get("current_phase", {}).get("enum")
    if not isinstance(values, list) or not values:
        raise SessionStateValidationError("session schema 未定义 current_phase 枚举。")
    return values


def session_status_values(schema=None):
    schema = schema or load_session_schema()
    values = schema.get("properties", {}).get("phase_status", {}).get("enum")
    if not isinstance(values, list) or not values:
        raise SessionStateValidationError("session schema 未定义 phase_status 枚举。")
    return values


def validate_task_id(task_id):
    if not task_id or not TASK_ID_PATTERN.match(task_id) or task_id in (".", ".."):
        raise SessionStateValidationError("task_id 只能包含字母、数字、下划线、短横线和点，且不能为 . 或 ..。")
    return task_id


def normalize_task_name(task_name):
    if task_name is None:
        return None
    if not isinstance(task_name, str):
        raise SessionStateValidationError("task_name 必须为字符串或 null。")
    if any(unicodedata.category(character) in {"Cc", "Zl", "Zp"} for character in task_name):
        raise SessionStateValidationError("task_name 不能包含换行、行分隔符或控制字符。")
    normalized = task_name.strip()
    if not normalized:
        raise SessionStateValidationError("task_name 不能为空。")
    if len(normalized) > TASK_NAME_MAX_LENGTH:
        raise SessionStateValidationError(f"task_name 不能超过 {TASK_NAME_MAX_LENGTH} 个字符。")
    return normalized


def normalize_legacy_identity(record, label="记录"):
    if not isinstance(record, dict):
        raise SessionStateValidationError(f"{label} 顶层必须是 object。")
    normalized = dict(record)
    has_task_id = "task_id" in normalized
    has_session_id = "session_id" in normalized
    if has_task_id and has_session_id:
        raise SessionStateValidationError(f"{label} 不能同时包含 task_id 和 legacy session_id。")
    if has_session_id:
        normalized["task_id"] = normalized.pop("session_id")
    return normalized


def normalize_legacy_state(state):
    legacy_state = isinstance(state, dict) and "session_id" in state and "task_id" not in state
    normalized = normalize_legacy_identity(state, "state")
    if legacy_state and "task_name" not in normalized:
        normalized["task_name"] = None
    if legacy_state and "affected_modules" not in normalized:
        normalized["affected_modules"] = []
    return normalized


def resolve_explicit_task_id(task_id, legacy_session_id, required=False):
    if task_id and legacy_session_id and task_id != legacy_session_id:
        raise SessionStateValidationError("--task-id 与 legacy --session-id 不能同时指定不同值。")
    value = task_id or legacy_session_id
    if required and not value:
        raise SessionStateValidationError("必须提供 --task-id；旧调用可使用 legacy --session-id。")
    return validate_task_id(value) if value else None


def resolve_create_task_id(task_id, legacy_session_id, new_task, environ=None):
    if new_task:
        if task_id or legacy_session_id:
            raise SessionStateValidationError("--new-task 不能与 --task-id 或 legacy --session-id 同时使用。")
        return None
    environ = environ or os.environ
    canonical = task_id if task_id is not None else environ.get("SUPERLOOPER_TASK_ID")
    legacy = legacy_session_id if legacy_session_id is not None else environ.get("SUPERLOOPER_SESSION_ID")
    return resolve_explicit_task_id(canonical, legacy)


def task_id_for_time(value):
    return TASK_ID_PREFIX + value.strftime("%Y%m%d%H%M%S")


def reserve_task_id(workspace_root, explicit_task_id=None, now=None):
    state_dir = workspace_root / ".superlooper" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    base_time = now or datetime.now()
    offset = 0
    while True:
        task_id = explicit_task_id or task_id_for_time(base_time + timedelta(seconds=offset))
        state_path = state_file_path(workspace_root, task_id)
        reservation_path = state_dir / f".{task_id}.reserve"
        if state_path.exists():
            if explicit_task_id:
                raise SessionCreateError(f"task_id 已存在：{task_id}")
            offset += 1
            continue
        try:
            with reservation_path.open("x", encoding="utf-8") as reservation:
                reservation.write(str(os.getpid()))
        except FileExistsError:
            if explicit_task_id:
                raise SessionCreateError(f"task_id 正在创建：{task_id}")
            offset += 1
            continue
        if state_path.exists():
            reservation_path.unlink(missing_ok=True)
            if explicit_task_id:
                raise SessionCreateError(f"task_id 已存在：{task_id}")
            offset += 1
            continue
        return task_id, reservation_path


def resolve_workspace_root(value):
    path = Path(value).resolve()
    if not path.exists():
        raise SessionStateValidationError(f"workspace_root 不存在：{path}")
    if not path.is_dir():
        raise SessionStateValidationError(f"workspace_root 必须是目录：{path}")
    return path


def portable_path_parts(value):
    if not isinstance(value, str):
        return []
    return value.replace("\\", "/").split("/")


def windows_path_key(value):
    return "/".join(
        part.rstrip(" .").casefold()
        for part in portable_path_parts(value)
    )


def is_safe_relative_path(value, protected_roots=None):
    if (
        not isinstance(value, str)
        or not value
        or ":" in value
        or value.replace("\\", "/").startswith("/")
    ):
        return False
    parts = portable_path_parts(value)
    if len(parts) > 1 and parts[-1] == "":
        parts = parts[:-1]
    normalized_parts = [part.rstrip(" .").casefold() for part in parts]
    if not normalized_parts or any(not part for part in normalized_parts):
        return False
    protected = {
        windows_path_key(root)
        for root in (protected_roots or set())
    }
    return normalized_parts[0] not in protected


def resolve_requirement_path(workspace_root, value):
    if not isinstance(value, str) or not value.strip():
        raise SessionCreateError("requirement_path 必须是非空字符串。")
    stripped = value.strip()
    raw = Path(stripped)
    if raw.is_absolute():
        path = raw.resolve()
    else:
        if not is_safe_relative_path(
            stripped,
            protected_roots=PROTECTED_ROOTS,
        ):
            raise SessionCreateError(f"requirement_path 不是安全路径：{value}")
        path = workspace_root.joinpath(
            *portable_path_parts(stripped)
        ).resolve()
    try:
        relative = path.relative_to(workspace_root)
    except ValueError:
        relative = None
    if relative is not None and not is_safe_relative_path(
        relative.as_posix(),
        protected_roots=PROTECTED_ROOTS,
    ):
        raise SessionCreateError(f"requirement_path 不是安全路径：{value}")
    if not path.exists():
        raise SessionCreateError(f"requirement_path 不存在：{path}")
    if not path.is_file():
        raise SessionCreateError(f"requirement_path 必须是文件：{path}")
    return path


def state_file_path(workspace_root, task_id):
    return workspace_root / ".superlooper" / "state" / f"{task_id}.json"


def load_state_from_path(state_path):
    if not state_path.exists():
        raise SessionStateValidationError(f"state 文件不存在：{state_path}")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SessionStateValidationError(f"state JSON 解析失败：{exc}") from exc
    return validate_session_state(state)


def validate_session_state(state, schema=None):
    schema = schema or load_session_schema()
    state = normalize_legacy_state(state)
    try:
        schema_errors = SchemaValidator().validate(state, schema, "state")
    except SchemaValidationError as exc:
        raise SessionStateValidationError(str(exc)) from exc
    if schema_errors:
        raise SessionStateValidationError("\n".join(schema_errors))

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(required, list):
        raise SessionStateValidationError("session schema.required 必须是数组。")

    missing = [field for field in required if field not in state]
    if missing:
        raise SessionStateValidationError(f"state 缺少字段：{', '.join(missing)}")

    if schema.get("additionalProperties") is False:
        extra = [field for field in state if field not in properties]
        if extra:
            raise SessionStateValidationError(f"state 存在未声明字段：{', '.join(sorted(extra))}")

    validate_task_id(state.get("task_id"))
    normalized_task_name = normalize_task_name(state.get("task_name"))
    if normalized_task_name != state.get("task_name"):
        raise SessionStateValidationError("task_name 必须为去除首尾空白后的规范值。")
    require_non_empty_string(state, "workspace_root")
    require_non_empty_string(state, "requirement_path")

    current_phase = state.get("current_phase")
    if current_phase not in session_phase_values(schema):
        raise SessionStateValidationError(f"current_phase 不合法：{current_phase}")

    phase_status = state.get("phase_status")
    if phase_status not in session_status_values(schema):
        raise SessionStateValidationError(f"phase_status 不合法：{phase_status}")

    require_string_or_none(state, "last_command")
    require_string_or_none(state, "last_error")
    require_string_list(state, "generated_files")
    require_string_list(state, "reports")
    validate_script_events(state.get("script_events"))
    require_string_list(state, "next_actions")

    project_mode = state.get("project_mode")
    if project_mode not in PROJECT_MODES:
        raise SessionStateValidationError(f"project_mode 不合法：{project_mode}")
    workflow_mode = state.get("workflow_mode")
    if workflow_mode not in WORKFLOW_MODES:
        raise SessionStateValidationError(f"workflow_mode 不合法：{workflow_mode}")
    project_category = state.get("project_category")
    if project_category is not None and project_category not in PROJECT_CATEGORIES:
        raise SessionStateValidationError(f"project_category 不合法：{project_category}")
    project_version = state.get("project_version")
    if project_version is not None and project_version not in PROJECT_VERSIONS:
        raise SessionStateValidationError(f"project_version 不合法：{project_version}")
    require_string_or_none(state, "project_root")
    if not isinstance(state.get("project_initialized"), bool):
        raise SessionStateValidationError("project_initialized 必须为 boolean。")
    require_string_or_none(state, "initialization_report")
    execution_summary_status = state.get("execution_summary_status")
    if execution_summary_status not in EXECUTION_SUMMARY_STATUSES:
        raise SessionStateValidationError(f"execution_summary_status 不合法：{execution_summary_status}")
    require_string_or_none(state, "execution_summary_report")
    validate_loop_policy(state.get("loop_policy"))
    validate_loop_state(state.get("loop_state"))
    require_string_or_none(state, "requirement_alignment_report")
    if not isinstance(state.get("requirement_alignment_passed"), bool):
        raise SessionStateValidationError("requirement_alignment_passed 必须为 boolean。")
    require_non_negative_integer(state, "prd_revision")
    require_non_negative_integer(state, "ui_revision")
    ui_status = state.get("ui_status")
    if ui_status not in UI_STATUSES:
        raise SessionStateValidationError(f"ui_status 不合法：{ui_status}")
    require_string_or_none(state, "ui_output_dir")
    if not isinstance(state.get("ui_artifacts_validated"), bool):
        raise SessionStateValidationError("ui_artifacts_validated 必须为 boolean。")
    require_non_negative_integer(state, "design_revision")
    require_non_negative_integer(state, "change_request_count")
    require_string_or_none(state, "active_feedback_report")
    require_string_or_none(state, "change_impact_report")
    require_string_list(state, "affected_modules")
    if len(state["affected_modules"]) != len(set(state["affected_modules"])):
        raise SessionStateValidationError("affected_modules 不能包含重复模块。")
    require_string_list(state, "invalidated_artifacts")
    rollback_target_phase = state.get("rollback_target_phase")
    if rollback_target_phase is not None and rollback_target_phase not in ROLLBACK_TARGET_PHASES:
        raise SessionStateValidationError(f"rollback_target_phase 不合法：{rollback_target_phase}")
    require_string_or_none(state, "last_user_input_text")
    require_string_or_none(state, "last_user_canonical_action")
    pending_user_choice = state.get("pending_user_choice")
    if pending_user_choice is not None and not isinstance(pending_user_choice, dict):
        raise SessionStateValidationError("pending_user_choice 必须为 object 或 null。")
    return state


def require_non_empty_string(state, field):
    value = state.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SessionStateValidationError(f"state 字段无效：{field}")


def require_string(state, field):
    value = state.get(field)
    if not isinstance(value, str):
        raise SessionStateValidationError(f"state 字段无效：{field}")


def require_string_or_none(state, field):
    value = state.get(field)
    if value is not None and not isinstance(value, str):
        raise SessionStateValidationError(f"state 字段无效：{field}")


def require_string_list(state, field):
    value = state.get(field)
    if not isinstance(value, list):
        raise SessionStateValidationError(f"state 字段无效：{field}")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise SessionStateValidationError(f"state 字段无效：{field}[{index}]")


def require_non_negative_integer(state, field):
    value = state.get(field)
    if not isinstance(value, int) or value < 0:
        raise SessionStateValidationError(f"state 字段无效：{field}")


def validate_script_events(value):
    if not isinstance(value, list):
        raise SessionStateValidationError("script_events 必须为 array。")
    seen = set()
    for index, event in enumerate(value):
        if not isinstance(event, dict):
            raise SessionStateValidationError(f"script_events[{index}] 必须为 object。")
        extra = [field for field in event if field not in {"script", "status", "idempotency_key"}]
        if extra:
            raise SessionStateValidationError(f"script_events[{index}] 存在未声明字段：{', '.join(sorted(extra))}")
        script = event.get("script")
        status = event.get("status")
        idempotency_key = event.get("idempotency_key")
        if not isinstance(script, str) or not script.strip():
            raise SessionStateValidationError(f"script_events[{index}].script 必须为非空字符串。")
        if status not in {"started", "completed", "failed"}:
            raise SessionStateValidationError(f"script_events[{index}].status 不合法：{status}")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise SessionStateValidationError(f"script_events[{index}].idempotency_key 必须为非空字符串。")
        if idempotency_key in seen:
            raise SessionStateValidationError(f"script_events idempotency_key 重复：{idempotency_key}")
        seen.add(idempotency_key)


def validate_loop_policy(value):
    if not isinstance(value, dict):
        raise SessionStateValidationError("loop_policy 必须为 object。")
    max_auto_loop = value.get("max_auto_loop_per_phase")
    if not isinstance(max_auto_loop, int) or max_auto_loop < 0:
        raise SessionStateValidationError("loop_policy.max_auto_loop_per_phase 必须为非负整数。")


def validate_loop_state(value):
    if not isinstance(value, dict):
        raise SessionStateValidationError("loop_state 必须为 object。")
    current_loop_target_phase = value.get("current_loop_target_phase")
    if current_loop_target_phase is not None and current_loop_target_phase not in ROLLBACK_TARGET_PHASES:
        raise SessionStateValidationError(f"loop_state.current_loop_target_phase 不合法：{current_loop_target_phase}")
    loop_count_by_phase = value.get("loop_count_by_phase")
    if not isinstance(loop_count_by_phase, dict):
        raise SessionStateValidationError("loop_state.loop_count_by_phase 必须为 object。")
    for phase, count in loop_count_by_phase.items():
        if phase not in ROLLBACK_TARGET_PHASES:
            raise SessionStateValidationError(f"loop_state.loop_count_by_phase 阶段不合法：{phase}")
        if not isinstance(count, int) or count < 0:
            raise SessionStateValidationError(f"loop_state.loop_count_by_phase.{phase} 必须为非负整数。")
    last_alignment_status = value.get("last_alignment_status")
    if last_alignment_status is not None and last_alignment_status not in ALIGNMENT_STATUSES:
        raise SessionStateValidationError(f"loop_state.last_alignment_status 不合法：{last_alignment_status}")
    last_feedback_report = value.get("last_feedback_report")
    if last_feedback_report is not None and not isinstance(last_feedback_report, str):
        raise SessionStateValidationError("loop_state.last_feedback_report 必须为 string 或 null。")


def write_state(state_path, state):
    canonical_state = validate_session_state(state)
    state_path.write_text(json.dumps(canonical_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_initial_state(task_id, workspace_root, requirement_path, project_mode="greenfield", task_name=None):
    return validate_session_state(
        {
            "task_id": task_id,
            "task_name": normalize_task_name(task_name),
            "workspace_root": str(workspace_root),
            "requirement_path": str(requirement_path),
            "current_phase": "prd",
            "phase_status": "pending",
            "generated_files": [],
            "reports": [],
            "script_events": [],
            "last_command": "create_session",
            "last_error": None,
            "next_actions": ["运行 /spl:prd 进入需求分析阶段"],
            "project_mode": project_mode,
            "workflow_mode": "standard",
            "project_category": None,
            "project_version": None,
            "project_root": None,
            "project_initialized": False,
            "initialization_report": None,
            "execution_summary_status": "NOT_STARTED",
            "execution_summary_report": None,
            "loop_policy": {"max_auto_loop_per_phase": 2},
            "loop_state": {
                "current_loop_target_phase": None,
                "loop_count_by_phase": {},
                "last_alignment_status": None,
                "last_feedback_report": None,
            },
            "requirement_alignment_report": None,
            "requirement_alignment_passed": False,
            "prd_revision": 0,
            "ui_revision": 0,
            "ui_status": "NOT_STARTED",
            "ui_output_dir": None,
            "ui_artifacts_validated": False,
            "design_revision": 0,
            "change_request_count": 0,
            "active_feedback_report": None,
            "change_impact_report": None,
            "affected_modules": [],
            "invalidated_artifacts": [],
            "rollback_target_phase": None,
            "last_user_input_text": None,
            "last_user_canonical_action": None,
            "pending_user_choice": None,
        }
    )


def ensure_session_layout(workspace_root, task_id):
    runtime_root = workspace_root / ".superlooper"
    created_paths = [
        runtime_root / "context" / task_id,
        runtime_root / "reports" / task_id,
        runtime_root / "manifests" / task_id,
        runtime_root / "agents" / task_id,
        runtime_root / "outputs" / task_id,
        runtime_root / "state",
    ]
    new_task_paths = []
    for path in created_paths:
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed and path.name == task_id:
            new_task_paths.append(path)
    return created_paths, state_file_path(workspace_root, task_id), new_task_paths


def cleanup_new_task_paths(paths):
    for path in reversed(paths):
        try:
            path.rmdir()
        except OSError:
            pass


def write_state_if_missing(state_path, state):
    if state_path.exists():
        return False
    write_state(state_path, state)
    return True


def print_result(task_id, task_name, requirement_path, state_path, created_paths, state_created):
    print(f"task_id: {task_id}")
    print(f"task_name: {task_name if task_name is not None else '(none)'}")
    print(f"requirement_path: {requirement_path}")
    print(f"state_file: {state_path}")
    print(f"state_created: {'yes' if state_created else 'no'}")
    print("runtime_paths:")
    for path in created_paths:
        print(f"- {path}")


def main():
    args = parse_args()
    reservation_path = None
    new_task_paths = []
    state_written = False
    try:
        workspace_root = resolve_workspace_root(args.workspace_root)
        requirement_path = resolve_requirement_path(workspace_root, args.requirement_path)
        task_name = normalize_task_name(args.task_name)
        explicit_task_id = resolve_create_task_id(args.task_id, args.session_id, args.new_task)
        if explicit_task_id is not None:
            existing_state_path = state_file_path(workspace_root, explicit_task_id)
            if existing_state_path.exists():
                state = load_state_from_path(existing_state_path)
                if state["task_id"] != explicit_task_id:
                    raise SessionCreateError("state task_id 与请求的 task_id 不一致。")
                if Path(state["requirement_path"]).resolve() != requirement_path:
                    raise SessionCreateError("已有 task 的 requirement_path 与本次输入不一致。")
                created_paths, state_path, _ = ensure_session_layout(workspace_root, explicit_task_id)
                print_result(
                    explicit_task_id,
                    state["task_name"],
                    requirement_path,
                    state_path,
                    created_paths,
                    state_created=False,
                )
                return 0
        task_id, reservation_path = reserve_task_id(workspace_root, explicit_task_id=explicit_task_id)
        created_paths, state_path, new_task_paths = ensure_session_layout(workspace_root, task_id)
        state = build_initial_state(task_id, workspace_root, requirement_path, args.project_mode, task_name)
        write_state(state_path, state)
        state_written = True
        reservation_path.unlink(missing_ok=True)
        reservation_path = None
        print_result(task_id, task_name, requirement_path, state_path, created_paths, state_created=True)
        return 0
    except (OSError, SessionCreateError, SessionStateValidationError) as exc:
        print(f"创建 task 失败：{exc}", file=sys.stderr)
        return 1
    finally:
        if reservation_path is not None:
            reservation_path.unlink(missing_ok=True)
        if not state_written:
            cleanup_new_task_paths(new_task_paths)


if __name__ == "__main__":
    sys.exit(main())
