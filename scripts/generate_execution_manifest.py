import argparse
import json
import os
import re
import sys
from pathlib import Path


SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
MODULE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
PROTECTED_ROOTS = {".superlooper", ".git", ".svn", ".hg"}
SYSTEM_NODES = [
    {
        "id": "task_code_review",
        "agent": "code-reviewer",
        "payload": "审查所有并行模块节点代码",
    },
    {
        "id": "task_merge",
        "agent": "system_merger",
        "payload": "执行 scripts/merge_artifacts.py 进行冲突消解",
    },
    {
        "id": "task_integration_test",
        "agent": "tester",
        "payload": "执行合并后集成测试与契约测试",
    },
    {
        "id": "task_apply_to_workspace",
        "agent": "workspace_applier",
        "payload": "将测试通过的合并产物应用到当前目标项目根目录",
    },
]
FORBIDDEN_INPUTS = ["原始需求文档", "其他模块 payload", "其他模块输出目录"]
FORBIDDEN_OUTPUTS = ["未包含在 target_files 中的文件", "目标项目根目录直接写入"]
REQUIRED_UI_ARTIFACTS = ["ui-spec.md", "page-map.md", "interaction-flow.md", "ui-handoff.md", "preview.html"]
REQUIRED_DESIGN_ARTIFACTS = ["architecture.md", "tech-stack.md", "project-profile.md", "initialization-advice.md"]
UI_TRACEABILITY_FIELDS = [
    "ui_refs",
    "interaction_refs",
    "component_refs",
    "ui_acceptance_refs",
]
BROWNFIELD_MODULE_LIST_FIELDS = [
    "allowed_existing_files",
    "forbidden_files",
    "integration_points",
    "test_commands",
]
ALLOWED_PHASE_STATUSES = {"pending", "running"}


class ManifestGenerationError(Exception):
    pass


class ExecutionManifestGenerator:
    def __init__(self, workspace_root, session_id, module_split=None, output=None, platform="claude"):
        self.root = Path(workspace_root).resolve()
        self.session_id = self._validate_session_id(session_id)
        self.platform = platform
        self.module_split_path = self._resolve_scoped_path(
            module_split,
            self.root / ".superlooper" / "manifests" / self.session_id / "module-split.json",
        )
        self.output_path = self._resolve_scoped_path(
            output,
            self.root / ".superlooper" / "manifests" / self.session_id / "execution_manifest.json",
        )

    def run(self):
        state = self._load_session_state()
        self._validate_preconditions(state)
        module_split = self._load_module_split()
        modules = self._collect_modules(module_split)
        manifest = self._build_manifest(modules)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(self._contract_path(self.output_path))
        return 0

    def _resolve_scoped_path(self, value, default):
        path = Path(value) if value else Path(default)
        if value and not path.is_absolute() and (":" in str(value) or path.drive):
            raise ManifestGenerationError(f"相对路径不能包含盘符或冒号：{value}")
        if not path.is_absolute():
            path = self.root / path
        path = path.resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ManifestGenerationError(f"路径必须位于 workspace_root 内：{path}") from exc
        return path

    def _validate_session_id(self, session_id):
        if not session_id or session_id in {".", ".."} or not SESSION_PATTERN.match(session_id):
            raise ManifestGenerationError("session_id 只能包含字母、数字、下划线、短横线和点，且不能为 . 或 ..。")
        return session_id

    def _load_session_state(self):
        state_path = self.root / ".superlooper" / "state" / f"{self.session_id}.json"
        if not state_path.exists():
            raise ManifestGenerationError(f"session state 不存在：{state_path}")
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManifestGenerationError(f"session state 解析失败：{exc}") from exc
        if state.get("project_initialized") is not True:
            raise ManifestGenerationError("project_initialized 必须为 true 才能生成 execution_manifest。")
        report_path = state.get("initialization_report")
        if not isinstance(report_path, str) or not report_path.strip():
            raise ManifestGenerationError("initialization_report 缺失，不能生成 execution_manifest。")
        if not (self.root / report_path).exists():
            raise ManifestGenerationError(f"initialization_report 不存在：{report_path}")
        return state

    def _validate_preconditions(self, state):
        if state.get("current_phase") != "run":
            raise ManifestGenerationError("current_phase 必须为 run 才能生成 execution_manifest。")
        if state.get("phase_status") not in ALLOWED_PHASE_STATUSES:
            raise ManifestGenerationError("phase_status 必须为 pending 或 running 才能生成 execution_manifest。")
        if state.get("ui_status") != "APPROVED":
            raise ManifestGenerationError("ui_status 必须为 APPROVED 才能生成 execution_manifest。")
        if state.get("ui_artifacts_validated") is not True:
            raise ManifestGenerationError("ui_artifacts_validated 必须为 true 才能生成 execution_manifest。")
        ui_output_dir = state.get("ui_output_dir") or f".superlooper/context/{self.session_id}/ui/"
        ui_dir = self._resolve_scoped_path(ui_output_dir, self.root / ".superlooper" / "context" / self.session_id / "ui")
        for filename in REQUIRED_UI_ARTIFACTS:
            self._require_file(ui_dir / filename, f"UI 固定产物不存在：{filename}")
        design_dir = self.root / ".superlooper" / "context" / self.session_id / "design"
        for filename in REQUIRED_DESIGN_ARTIFACTS:
            self._require_file(design_dir / filename, f"设计固定产物不存在：{filename}")

    def _require_file(self, path, message):
        if not path.is_file():
            raise ManifestGenerationError(f"{message}: {self._contract_path(path)}")

    def _load_module_split(self):
        if not self.module_split_path.exists():
            raise ManifestGenerationError(f"module-split 文件不存在：{self.module_split_path}")
        try:
            data = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManifestGenerationError(f"module-split 解析失败：{exc}") from exc
        if not isinstance(data, dict):
            raise ManifestGenerationError("module-split 顶层必须是 object。")
        return data

    def _collect_modules(self, module_split):
        modules = module_split.get("modules")
        if not isinstance(modules, list) or not modules:
            raise ManifestGenerationError("module-split.modules 必须是非空数组。")
        seen_ids = set()
        target_file_to_module = {}
        collected = []
        for index, module in enumerate(modules):
            label = f"module-split.modules[{index}]"
            if not isinstance(module, dict):
                raise ManifestGenerationError(f"{label} 必须是 object。")
            module_id = module.get("id")
            if not isinstance(module_id, str) or not MODULE_PATTERN.match(module_id):
                raise ManifestGenerationError(f"{label}.id 必须匹配 {MODULE_PATTERN.pattern}。")
            if module_id in seen_ids:
                raise ManifestGenerationError(f"检测到重复 module_id：{module_id}")
            seen_ids.add(module_id)
            target_files = module.get("target_files") or []
            if not isinstance(target_files, list):
                raise ManifestGenerationError(f"{label}.target_files 必须是数组。")
            module_target_files = set()
            for file_index, target_file in enumerate(target_files):
                if not self._safe_relative_path(target_file):
                    raise ManifestGenerationError(f"{label}.target_files[{file_index}] 不是安全相对路径：{target_file}")
                if target_file in module_target_files:
                    raise ManifestGenerationError(f"{label}.target_files 存在重复路径：{target_file}")
                module_target_files.add(target_file)
                owner = target_file_to_module.get(target_file)
                if owner is not None:
                    raise ManifestGenerationError(
                        f"检测到跨模块重复 target_files：{target_file} 同时属于 {owner} 和 {module_id}"
                    )
                target_file_to_module[target_file] = module_id
            collected.append(module)
        return collected

    def _build_manifest(self, modules):
        nodes = [self._build_module_node(module) for module in modules]
        module_node_ids = [node["id"] for node in nodes]
        system_nodes = self._build_system_nodes(module_node_ids)
        nodes.extend(system_nodes)
        context = {
            "prd_path": f".superlooper/context/{self.session_id}/prd.md",
            "design_docs_path": f".superlooper/context/{self.session_id}/design/",
            "module_split_path": f".superlooper/manifests/{self.session_id}/module-split.json",
            "agents_path": "agents/",
            "runtime_agents_path": f".superlooper/agents/{self.session_id}/",
        }
        if self.platform == "claude":
            context["registered_agents_path"] = f".claude/agents/generated/superlooper/{self.session_id}/"
        else:
            context["platform_registration"] = {"platform": "codex"}
        context.update(
            {
                "outputs_path": f".superlooper/outputs/{self.session_id}/",
                "merged_path": f".superlooper/merged/{self.session_id}/",
                "reports_path": f".superlooper/reports/{self.session_id}/",
            }
        )
        return {
            "session_id": self.session_id,
            "granularity": "module",
            "context": context,
            "dag": {"nodes": nodes},
        }

    def _build_module_node(self, module):
        module_id = module["id"]
        module_payload = self._build_module_payload_text(module)
        payload = dict(module)
        payload.update(
            {
                "session_id": self.session_id,
                "module_id": module_id,
                "module_payload": module_payload,
                "design_docs_path": f".superlooper/context/{self.session_id}/design/",
                "project_profile_path": f".superlooper/context/{self.session_id}/design/project-profile.md",
                "module_split_path": f".superlooper/manifests/{self.session_id}/module-split.json",
                "execution_manifest_path": f".superlooper/manifests/{self.session_id}/execution_manifest.json",
                "output_dir": f".superlooper/outputs/{self.session_id}/{module_id}/",
                "artifact_manifest_path": f".superlooper/outputs/{self.session_id}/{module_id}/artifact_manifest.json",
                "target_files": self._as_list(module.get("target_files")),
                "file_roles": self._as_list(module.get("file_roles")),
                "requirement_refs": self._as_list(module.get("requirement_refs")),
                "decision_refs": self._as_list(module.get("decision_refs")),
                "open_question_refs": self._as_list(module.get("open_question_refs")),
                "acceptance_refs": self._as_list(module.get("acceptance_refs")),
                "test_focus": self._as_list(module.get("test_focus")),
                **self._field_lists(module, UI_TRACEABILITY_FIELDS),
                **self._field_lists(module, BROWNFIELD_MODULE_LIST_FIELDS),
                "overwrite_policy": module.get("overwrite_policy") or "block_by_default",
                "forbidden_inputs": list(FORBIDDEN_INPUTS),
                "forbidden_outputs": list(FORBIDDEN_OUTPUTS),
            }
        )
        return {
            "id": f"mod_{module_id}",
            "agent": f"module_{module_id}",
            "depends_on": [],
            "payload": payload,
        }

    def _build_module_payload_text(self, module):
        description = module.get("description")
        name = module.get("name")
        if isinstance(description, str) and description.strip():
            return description.strip()
        if isinstance(name, str) and name.strip():
            return f"负责 {name.strip()} 的能力交付，代码必须落到目标项目根目录相对路径。"
        return f"负责 {module['id']} 模块交付，代码必须落到目标项目根目录相对路径。"

    def _build_system_nodes(self, module_node_ids):
        nodes = []
        for node in SYSTEM_NODES:
            node_id = node["id"]
            depends_on = []
            if node_id == "task_code_review":
                depends_on = list(module_node_ids)
            elif node_id == "task_merge":
                depends_on = ["task_code_review"]
            elif node_id == "task_integration_test":
                depends_on = ["task_merge"]
            elif node_id == "task_apply_to_workspace":
                depends_on = ["task_integration_test"]
            nodes.append(
                {
                    "id": node_id,
                    "agent": node["agent"],
                    "depends_on": depends_on,
                    "payload": node["payload"],
                }
            )
        return nodes

    def _as_list(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ManifestGenerationError("模块字段类型不合法，预期为数组。")
        return value

    def _field_lists(self, module, fields):
        return {field: self._as_list(module.get(field)) for field in fields}

    def _safe_relative_path(self, value):
        if not isinstance(value, str) or not value or ":" in value:
            return False
        path = Path(value)
        normalized_parts = [part for part in path.parts if part not in ("", ".")]
        if not normalized_parts:
            return False
        if normalized_parts[0] in PROTECTED_ROOTS:
            return False
        return not path.is_absolute() and not path.drive and ".." not in path.parts

    def _contract_path(self, path):
        return str(path.relative_to(self.root)).replace("\\", "/")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate SUPERLOOPER execution_manifest.json from module-split.json.")
    parser.add_argument(
        "--workspace-root",
        default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()),
        help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。",
    )
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    parser.add_argument(
        "--module-split",
        default=os.getenv("SUPERLOOPER_MODULE_SPLIT"),
        help="module-split.json 路径，默认 <workspace-root>/.superlooper/manifests/<session_id>/module-split.json。",
    )
    parser.add_argument(
        "--output",
        default=os.getenv("SUPERLOOPER_MANIFEST_PATH"),
        help="execution_manifest.json 输出路径，默认 <workspace-root>/.superlooper/manifests/<session_id>/execution_manifest.json。",
    )
    parser.add_argument("--platform", choices=("claude", "codex"), default="claude", help="平台注册目标，默认 claude。")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        generator = ExecutionManifestGenerator(
            workspace_root=args.workspace_root,
            session_id=args.session_id,
            module_split=args.module_split,
            output=args.output,
            platform=args.platform,
        )
        return generator.run()
    except ManifestGenerationError as exc:
        print(f"生成 execution_manifest 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
