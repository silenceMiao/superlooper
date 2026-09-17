import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from create_session import (
    SessionStateValidationError,
    normalize_legacy_identity,
    resolve_explicit_task_id,
    resolve_workspace_root,
)


class DagRunError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(description="Run SUPERLOOPER execution manifest DAG state runner.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--task-id", default=os.getenv("SUPERLOOPER_TASK_ID"), help="执行任务 ID。")
    parser.add_argument("--session-id", default=os.getenv("SUPERLOOPER_SESSION_ID"), help=argparse.SUPPRESS)
    return parser.parse_args()


def manifest_path(workspace_root, task_id):
    return workspace_root / ".superlooper" / "manifests" / task_id / "execution_manifest.json"


def dag_state_path(workspace_root, task_id):
    return workspace_root / ".superlooper" / "state" / f"{task_id}.dag.json"


def load_manifest(path, task_id):
    if not path.exists():
        raise DagRunError(f"execution_manifest.json 不存在：{path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DagRunError(f"execution_manifest.json 解析失败：{exc}") from exc
    if not isinstance(manifest, dict):
        raise DagRunError("execution_manifest.json 顶层必须是 object。")
    try:
        manifest = normalize_legacy_identity(manifest, "execution_manifest.json")
    except SessionStateValidationError as exc:
        raise DagRunError(str(exc)) from exc
    if manifest.get("task_id") != task_id:
        raise DagRunError("execution_manifest.json task_id 与当前 task_id 不一致。")
    dag = manifest.get("dag")
    if not isinstance(dag, dict):
        raise DagRunError("execution_manifest.json.dag 必须是 object。")
    nodes = dag.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise DagRunError("execution_manifest.json.dag.nodes 必须是非空数组。")
    return manifest


def sort_nodes(nodes):
    node_map = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise DagRunError("dag.nodes 中存在非 object 节点。")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            raise DagRunError("dag.nodes[].id 必须是非空字符串。")
        if node_id in node_map:
            raise DagRunError(f"DAG 节点重复：{node_id}")
        depends_on = node.get("depends_on", [])
        if not isinstance(depends_on, list):
            raise DagRunError(f"{node_id}.depends_on 必须是数组。")
        node_map[node_id] = node
    for node_id, node in node_map.items():
        for dependency in node.get("depends_on", []):
            if dependency not in node_map:
                raise DagRunError(f"{node_id} 依赖不存在的节点：{dependency}")
    ordered = []
    temporary = set()
    permanent = set()

    def visit(node_id):
        if node_id in permanent:
            return
        if node_id in temporary:
            raise DagRunError(f"DAG 存在循环依赖：{node_id}")
        temporary.add(node_id)
        for dependency in node_map[node_id].get("depends_on", []):
            visit(dependency)
        temporary.remove(node_id)
        permanent.add(node_id)
        ordered.append(node_id)

    for node_id in node_map:
        visit(node_id)
    return node_map, ordered


def build_state(task_id, manifest, node_map, ordered, status, error_summary=""):
    return {
        "task_id": task_id,
        "dag_status": status,
        "current_node": ordered[-1] if ordered else None,
        "execution_order": ordered,
        "error_summary": error_summary,
        "manifest_path": f".superlooper/manifests/{task_id}/execution_manifest.json",
        "nodes": {
            node_id: {
                "status": "success" if status == "success" and node_id in ordered else "pending",
                "agent": node_map[node_id].get("agent"),
                "depends_on": node_map[node_id].get("depends_on", []),
                "artifact_manifest": artifact_manifest_path(task_id, node_id),
                "error_summary": "",
            }
            for node_id in node_map
        },
    }


def artifact_manifest_path(task_id, node_id):
    if not node_id.startswith("mod_"):
        return ""
    module_id = node_id.removeprefix("mod_")
    return f".superlooper/outputs/{task_id}/{module_id}/artifact_manifest.json"


def write_dag_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_script_event(workspace_root, task_id, status):
    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "update_session.py"),
        "--workspace-root",
        str(workspace_root),
        "--task-id",
        task_id,
        "--current-phase",
        "run",
        "--phase-status",
        "running" if status == "completed" else "failed",
        "--last-command",
        "run_execution_dag",
        "--record-script-event",
        f"run_execution_dag:{status}:{task_id}:{status}",
    ]
    completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        raise DagRunError(completed.stderr or completed.stdout or "记录 script event 失败。")


def run(workspace_root, task_id):
    path = manifest_path(workspace_root, task_id)
    try:
        manifest = load_manifest(path, task_id)
        node_map, ordered = sort_nodes(manifest["dag"]["nodes"])
    except DagRunError as exc:
        nodes = []
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                nodes = raw.get("dag", {}).get("nodes", []) if isinstance(raw, dict) else []
            except json.JSONDecodeError:
                nodes = []
        node_map = {node.get("id", f"invalid_{index}"): node for index, node in enumerate(nodes) if isinstance(node, dict)}
        state = build_state(task_id, {}, node_map, [], "failed", str(exc))
        write_dag_state(dag_state_path(workspace_root, task_id), state)
        record_script_event(workspace_root, task_id, "failed")
        raise
    state = build_state(task_id, manifest, node_map, ordered, "success")
    write_dag_state(dag_state_path(workspace_root, task_id), state)
    record_script_event(workspace_root, task_id, "completed")
    return state


def main():
    args = parse_args()
    try:
        task_id = resolve_explicit_task_id(args.task_id, args.session_id, required=True)
        workspace_root = resolve_workspace_root(args.workspace_root)
        run(workspace_root, task_id)
        print(dag_state_path(workspace_root, task_id))
        return 0
    except (DagRunError, SessionStateValidationError) as exc:
        print(f"执行 DAG 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
