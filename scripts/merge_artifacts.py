import argparse
import filecmp
import json
import os
import re
import shutil
import sys
from pathlib import Path


SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
PROTECTED_ROOTS = {".superlooper", ".git", ".svn", ".hg"}


class MergeError(Exception):
    pass


class ParallelMergeEngine:
    def __init__(self, workspace_root, session_id=None, outputs_dir=None, merged_dir=None, reports_dir=None, manifest_path=None, redact_paths=False):
        self.root = Path(workspace_root).resolve()
        self.redact_paths = redact_paths
        self.outputs_root = self._resolve_scoped_path(outputs_dir, self.root / ".superlooper" / "outputs")
        self.session_id = session_id or self._infer_session_id()
        self._validate_session_id(self.session_id)
        self.agent_outputs = self.outputs_root / self.session_id
        self.merged_dir = self._resolve_scoped_path(merged_dir, self.root / ".superlooper" / "merged" / self.session_id)
        self.reports_dir = self._resolve_scoped_path(reports_dir, self.root / ".superlooper" / "reports" / self.session_id)
        self.manifest_path = self._resolve_scoped_path(manifest_path, self.root / ".superlooper" / "manifests" / self.session_id / "execution_manifest.json")
        self.conflicts = []
        self.merged_files = []
        self.skipped_files = []
        self.validated_artifacts = []
        self.ignored_files = []
        self.execution_manifest = None
        self.module_ids = []
        self.artifacts = {}

    def run(self):
        self._validate_inputs()
        self.execution_manifest = self._load_execution_manifest()
        self.module_ids = self._module_ids_from_manifest(self.execution_manifest)
        module_dirs = self._module_dirs()
        self.artifacts = self._load_artifacts(module_dirs)

        self.merged_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._merge_modules(module_dirs)

        if self.conflicts:
            self._write_conflict_report()
            return 2

        self._write_merge_report(module_dirs)
        return 0

    def _resolve_scoped_path(self, value, default):
        path = Path(value) if value else Path(default)
        if value and not path.is_absolute() and (":" in str(value) or path.drive):
            raise MergeError(f"相对路径不能包含盘符或冒号：{value}")
        if not path.is_absolute():
            path = self.root / path
        path = path.resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise MergeError(f"路径必须位于 workspace_root 内：{path}") from exc
        return path

    def _infer_session_id(self):
        env_session = os.getenv("SUPERLOOPER_SESSION_ID")
        if env_session:
            return env_session

        if not self.outputs_root.exists():
            raise MergeError("未提供 --session-id，且 outputs 目录不存在，无法推断 session_id。")

        sessions = [p.name for p in self.outputs_root.iterdir() if p.is_dir()]
        if len(sessions) == 1:
            return sessions[0]
        if not sessions:
            raise MergeError("未提供 --session-id，且 outputs 目录下没有可用 session。")
        raise MergeError("未提供 --session-id，且 outputs 目录下存在多个 session，无法唯一推断。")

    def _validate_session_id(self, session_id):
        if not session_id or not SESSION_PATTERN.match(session_id):
            raise MergeError("session_id 只能包含字母、数字、下划线、短横线和点。")

    def _validate_inputs(self):
        if not self.root.exists():
            raise MergeError(f"workspace_root 不存在：{self.root}")
        if not self.agent_outputs.exists():
            raise MergeError(f"模块产物目录不存在：{self.agent_outputs}")
        if not self.manifest_path.exists():
            raise MergeError(f"Execution Manifest 文件不存在：{self.manifest_path}")

    def _load_execution_manifest(self):
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MergeError(f"Execution Manifest 解析失败：{exc}") from exc
        if not isinstance(manifest, dict):
            raise MergeError("Execution Manifest 顶层必须是 object。")
        if manifest.get("session_id") != self.session_id:
            raise MergeError("Execution Manifest session_id 与当前 session_id 不一致。")
        if manifest.get("granularity") != "module":
            raise MergeError("Execution Manifest granularity 必须为 module。")
        nodes = manifest.get("dag", {}).get("nodes")
        if not isinstance(nodes, list):
            raise MergeError("Execution Manifest dag.nodes 必须是数组。")
        return manifest

    def _module_ids_from_manifest(self, manifest):
        module_ids = []
        for node in manifest.get("dag", {}).get("nodes", []):
            node_id = node.get("id") if isinstance(node, dict) else None
            if isinstance(node_id, str) and node_id.startswith("mod_"):
                module_ids.append(node_id.removeprefix("mod_"))
        if not module_ids:
            raise MergeError("Execution Manifest 中没有 mod_* 模块节点。")
        return sorted(module_ids)

    def _module_dirs(self):
        dirs = []
        for module_id in self.module_ids:
            module_dir = self.agent_outputs / module_id
            if not module_dir.is_dir():
                raise MergeError(f"模块产物目录不存在：{module_dir}")
            dirs.append(module_dir)
        return dirs

    def _load_artifacts(self, module_dirs):
        artifacts = {}
        for module_dir in module_dirs:
            artifact_path = module_dir / "artifact_manifest.json"
            if not artifact_path.exists():
                raise MergeError(f"缺少 artifact_manifest.json：{artifact_path}")
            try:
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise MergeError(f"artifact_manifest.json 解析失败：{artifact_path}: {exc}") from exc
            self._validate_artifact(module_dir.name, module_dir, artifact)
            artifacts[module_dir.name] = artifact
            self.validated_artifacts.append(str(artifact_path))
        return artifacts

    def _validate_artifact(self, module_id, module_dir, artifact):
        if not isinstance(artifact, dict):
            raise MergeError(f"{module_id} artifact_manifest 顶层必须是 object。")
        if artifact.get("session_id") != self.session_id:
            raise MergeError(f"{module_id} artifact_manifest session_id 不一致。")
        if artifact.get("module_id") != module_id:
            raise MergeError(f"{module_id} artifact_manifest module_id 不一致。")
        if artifact.get("status") != "success":
            raise MergeError(f"{module_id} artifact_manifest status 必须为 success。")
        produced_files = artifact.get("produced_files")
        if not isinstance(produced_files, list):
            raise MergeError(f"{module_id} artifact_manifest produced_files 必须是数组。")
        declared = set()
        for item in produced_files:
            if not isinstance(item, dict):
                raise MergeError(f"{module_id} produced_files 每一项必须是 object。")
            relative = item.get("path")
            if not self._safe_relative_path(relative):
                raise MergeError(f"{module_id} 声明了不安全路径：{relative}")
            declared.add(relative)
            if item.get("operation") not in ("create", "modify"):
                raise MergeError(f"{module_id} 声明了不支持的 operation：{item.get('operation')}")
            if item.get("required_for_merge") is True and not (module_dir / relative).exists():
                raise MergeError(f"{module_id} 声明文件不存在：{module_dir / relative}")
        actual_files = {
            str(path.relative_to(module_dir)).replace("\\", "/")
            for path in module_dir.rglob("*")
            if path.is_file() and path.name != "artifact_manifest.json"
        }
        undeclared = sorted(actual_files - declared)
        if undeclared:
            raise MergeError(f"{module_id} 存在未声明文件：{', '.join(undeclared)}")

    def _merge_modules(self, module_dirs):
        for module_dir in module_dirs:
            artifact = self.artifacts[module_dir.name]
            for item in artifact.get("produced_files", []):
                if item.get("required_for_merge") is not True:
                    self.skipped_files.append(f"{module_dir.name}:{item.get('path')}")
                    continue
                relative_path = Path(item["path"])
                source = module_dir / relative_path
                self._merge_file(module_dir.name, source, relative_path)
            self._record_ignored_files(module_dir, artifact)

    def _record_ignored_files(self, module_dir, artifact):
        declared = {item.get("path") for item in artifact.get("produced_files", []) if isinstance(item, dict)}
        for source in sorted(module_dir.rglob("*")):
            if source.is_dir() or source.name == "artifact_manifest.json":
                continue
            relative = str(source.relative_to(module_dir)).replace("\\", "/")
            if relative not in declared:
                self.ignored_files.append({"module": module_dir.name, "path": relative, "reason": "not_declared"})

    def _merge_file(self, module_name, source, relative_path):
        target = self.merged_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)

        if relative_path.name == "requirements.txt":
            self._merge_requirements(source, target, module_name, relative_path)
            return

        if relative_path.name == "package.json":
            self._merge_package_json(source, target, module_name, relative_path)
            return

        if not target.exists():
            shutil.copy2(source, target)
            self.merged_files.append({"module": module_name, "path": str(relative_path), "strategy": "copy"})
            return

        if filecmp.cmp(source, target, shallow=False):
            self.merged_files.append({"module": module_name, "path": str(relative_path), "strategy": "identical"})
            return

        self._record_conflict(module_name, source, target, relative_path, "same_path_different_content")

    def _merge_requirements(self, source, target, module_name, relative_path):
        existing = self._read_lines(target) if target.exists() else []
        incoming = self._read_lines(source)
        merged = []
        seen = set()
        for line in existing + incoming:
            normalized = line.strip()
            if not normalized or normalized.startswith("#") or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        target.write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
        self.merged_files.append({"module": module_name, "path": str(relative_path), "strategy": "requirements_union"})

    def _merge_package_json(self, source, target, module_name, relative_path):
        try:
            incoming = json.loads(source.read_text(encoding="utf-8"))
            existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        except json.JSONDecodeError as exc:
            self._record_conflict(module_name, source, target, relative_path, f"invalid_package_json:{exc}")
            return

        conflict_count = len(self.conflicts)
        merged = dict(existing)
        for key, value in incoming.items():
            if key not in merged:
                merged[key] = value
                continue
            if merged[key] == value:
                continue
            if isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_dict_field(module_name, source, target, relative_path, key, merged[key], value)
                continue
            self._record_conflict(module_name, source, target, relative_path, f"package_json_field_conflict:{key}")
            return

        if len(self.conflicts) > conflict_count:
            return
        target.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.merged_files.append({"module": module_name, "path": str(relative_path), "strategy": "package_json_semantic"})

    def _merge_dict_field(self, module_name, source, target, relative_path, field_name, existing, incoming):
        merged = dict(existing)
        for key, value in incoming.items():
            if key not in merged or merged[key] == value:
                merged[key] = value
                continue
            self._record_conflict(module_name, source, target, relative_path, f"package_json_{field_name}_conflict:{key}")
        return merged

    def _read_lines(self, path):
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def _record_conflict(self, module_name, source, target, relative_path, reason):
        conflict_dir = self.reports_dir / "conflicts" / str(relative_path).replace("/", "__").replace("\\", "__")
        conflict_dir.mkdir(parents=True, exist_ok=True)
        source_copy = conflict_dir / f"{module_name}{source.suffix or '.file'}"
        target_copy = conflict_dir / f"merged{target.suffix or '.file'}"
        shutil.copy2(source, source_copy)
        if target.exists():
            shutil.copy2(target, target_copy)
        self.conflicts.append({
            "module": module_name,
            "path": str(relative_path),
            "reason": reason,
            "incoming_file": str(source_copy),
            "current_merged_file": str(target_copy) if target.exists() else None,
        })

    def _write_conflict_report(self):
        report = {
            "status": "conflict",
            "session_id": self.session_id,
            "workspace_root": self._report_path(self.root),
            "manifest_path": self._report_path(self.manifest_path),
            "outputs_dir": self._report_path(self.agent_outputs),
            "merged_dir": self._report_path(self.merged_dir),
            "validated_artifacts": [self._report_path(path) for path in self.validated_artifacts],
            "conflicts": [self._report_conflict_item(item) for item in self.conflicts],
        }
        report_path = self.reports_dir / "conflict_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"检测到 {len(self.conflicts)} 个合并冲突，报告已生成：{report_path}")

    def _write_merge_report(self, module_dirs):
        report = {
            "status": "success",
            "session_id": self.session_id,
            "workspace_root": self._report_path(self.root),
            "manifest_path": self._report_path(self.manifest_path),
            "outputs_dir": self._report_path(self.agent_outputs),
            "merged_dir": self._report_path(self.merged_dir),
            "modules": [p.name for p in module_dirs],
            "validated_artifacts": [self._report_path(path) for path in self.validated_artifacts],
            "merged_files": self.merged_files,
            "skipped_files": sorted(set(self.skipped_files)),
            "ignored_files": self.ignored_files,
        }
        report_path = self.reports_dir / "merge_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"合并完成，报告已生成：{report_path}")

    def _safe_relative_path(self, value):
        if not isinstance(value, str) or not value or ":" in value:
            return False
        path = Path(value)
        normalized_parts = [part for part in path.parts if part not in ("", ".")]
        if not normalized_parts or normalized_parts[0] in PROTECTED_ROOTS:
            return False
        return not path.is_absolute() and not path.drive and ".." not in path.parts

    def _report_path(self, value):
        if value is None:
            return None
        if isinstance(value, Path):
            value = str(value)
        if not self.redact_paths or not isinstance(value, str):
            return value
        normalized_root = str(self.root).replace("\\", "/")
        normalized_value = value.replace("\\", "/")
        if normalized_value == normalized_root:
            return "."
        path = Path(value)
        if path.is_absolute():
            try:
                relative = path.resolve().relative_to(self.root)
            except ValueError:
                return value
            relative_text = str(relative).replace("\\", "/")
            return relative_text or "."
        return normalized_value

    def _report_conflict_item(self, item):
        return {
            **item,
            "incoming_file": self._report_path(item.get("incoming_file")),
            "current_merged_file": self._report_path(item.get("current_merged_file")),
        }


def parse_args():
    parser = argparse.ArgumentParser(description="Merge SUPERLOOPER parallel agent artifacts into a public project workspace.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="项目工作目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", default=os.getenv("SUPERLOOPER_SESSION_ID"), help="执行会话 ID；缺省时尝试从 .superlooper/outputs 目录唯一推断。")
    parser.add_argument("--outputs-dir", default=os.getenv("SUPERLOOPER_OUTPUTS_DIR"), help="模块产物根目录，默认 <workspace-root>/.superlooper/outputs。")
    parser.add_argument("--merged-dir", default=os.getenv("SUPERLOOPER_MERGED_DIR"), help="合并输出目录，默认 <workspace-root>/.superlooper/merged/<session-id>。")
    parser.add_argument("--reports-dir", default=os.getenv("SUPERLOOPER_REPORTS_DIR"), help="报告输出目录，默认 <workspace-root>/.superlooper/reports/<session-id>。")
    parser.add_argument("--manifest-path", default=os.getenv("SUPERLOOPER_MANIFEST_PATH"), help="Execution Manifest 路径，默认 <workspace-root>/.superlooper/manifests/<session-id>/execution_manifest.json。")
    parser.add_argument("--redact-paths", action="store_true", help="将 JSON 报告中的 workspace_root 与工作区内绝对路径脱敏为相对路径。")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        engine = ParallelMergeEngine(
            workspace_root=args.workspace_root,
            session_id=args.session_id,
            outputs_dir=args.outputs_dir,
            merged_dir=args.merged_dir,
            reports_dir=args.reports_dir,
            manifest_path=args.manifest_path,
            redact_paths=args.redact_paths,
        )
        return engine.run()
    except MergeError as exc:
        print(f"合并失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
