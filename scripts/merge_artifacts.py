import argparse
import filecmp
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from create_session import (
    SessionStateValidationError,
    is_safe_relative_path,
    normalize_legacy_identity,
    portable_path_parts,
    resolve_explicit_task_id,
    windows_path_key,
)
from snapshot_digest import compute_tree_digest


TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
PROTECTED_ROOTS = {".superlooper", ".git", ".svn", ".hg"}


class MergeError(Exception):
    pass


class ParallelMergeEngine:
    def __init__(self, workspace_root, task_id=None, outputs_dir=None, merged_dir=None, reports_dir=None, manifest_path=None, redact_paths=False):
        self.root = Path(workspace_root).resolve()
        self.redact_paths = redact_paths
        self.outputs_root = self._resolve_scoped_path(outputs_dir, self.root / ".superlooper" / "outputs")
        self.task_id = task_id or self._infer_task_id()
        self._validate_task_id(self.task_id)
        self.agent_outputs = self.outputs_root / self.task_id
        self.merged_dir = self._resolve_scoped_path(merged_dir, self.root / ".superlooper" / "merged" / self.task_id)
        self.reports_dir = self._resolve_scoped_path(reports_dir, self.root / ".superlooper" / "reports" / self.task_id)
        self.manifest_path = self._resolve_scoped_path(manifest_path, self.root / ".superlooper" / "manifests" / self.task_id / "execution_manifest.json")
        self.conflicts = []
        self.merged_files = []
        self.skipped_files = []
        self.validated_artifacts = []
        self.ignored_files = []
        self.execution_manifest = None
        self.module_ids = []
        self.artifacts = {}
        self.artifact_sources = {}
        self.merge_target_dir = self.merged_dir

    def run(self):
        self._validate_inputs()
        self.execution_manifest = self._load_execution_manifest()
        self.module_ids = self._module_ids_from_manifest(self.execution_manifest)
        module_dirs = self._module_dirs()
        self.artifacts = self._load_artifacts(module_dirs)

        self.merged_dir.parent.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.reports_dir / "conflicts", ignore_errors=True)
        staging_dir = Path(
            tempfile.mkdtemp(
                dir=self.merged_dir.parent,
                prefix=f".{self.merged_dir.name}.staging.",
            )
        )
        self.merge_target_dir = staging_dir
        staged_report = None
        try:
            self._merge_modules(module_dirs)

            if self.conflicts:
                (self.reports_dir / "merge_report.json").unlink(missing_ok=True)
                self._write_conflict_report()
                return 2

            snapshot_digest = compute_tree_digest(staging_dir)
            staged_report = self._stage_merge_report(module_dirs, snapshot_digest)
            self._publish_staging(staging_dir, staged_report)
            staging_dir = None
            staged_report = None
            (self.reports_dir / "conflict_report.json").unlink(missing_ok=True)
            shutil.rmtree(self.reports_dir / "conflicts", ignore_errors=True)
            print(f"合并完成，报告已生成：{self.reports_dir / 'merge_report.json'}")
            return 0
        finally:
            if staging_dir is not None:
                shutil.rmtree(staging_dir, ignore_errors=True)
            if staged_report is not None:
                staged_report.unlink(missing_ok=True)

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

    def _resolve_within(self, path, root, label, strict=True):
        try:
            resolved_root = Path(root).resolve(strict=True)
            resolved = Path(path).resolve(strict=strict)
        except OSError as exc:
            raise MergeError(f"{label} 真实路径解析失败：{path}: {exc}") from exc
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise MergeError(
                f"{label} 不在授权目录内：{path} -> {resolved}"
            ) from exc
        return resolved

    def _infer_task_id(self):
        env_task_id = os.getenv("SUPERLOOPER_TASK_ID") or os.getenv("SUPERLOOPER_SESSION_ID")
        if env_task_id:
            return env_task_id

        if not self.outputs_root.exists():
            raise MergeError("未提供 --task-id，且 outputs 目录不存在，无法推断 task_id。")

        sessions = [p.name for p in self.outputs_root.iterdir() if p.is_dir()]
        if len(sessions) == 1:
            return sessions[0]
        if not sessions:
            raise MergeError("未提供 --task-id，且 outputs 目录下没有可用 session。")
        raise MergeError("未提供 --task-id，且 outputs 目录下存在多个 session，无法唯一推断。")

    def _validate_task_id(self, task_id):
        if not task_id or not TASK_ID_PATTERN.match(task_id):
            raise MergeError("task_id 只能包含字母、数字、下划线、短横线和点。")

    def _validate_inputs(self):
        if not self.root.exists():
            raise MergeError(f"workspace_root 不存在：{self.root}")
        if not self.agent_outputs.exists():
            raise MergeError(f"模块产物目录不存在：{self.agent_outputs}")
        if not self.manifest_path.exists():
            raise MergeError(f"Execution Manifest 文件不存在：{self.manifest_path}")

    def _normalize_identity(self, data, label):
        try:
            return normalize_legacy_identity(data, label)
        except SessionStateValidationError as exc:
            raise MergeError(str(exc)) from exc

    def _load_execution_manifest(self):
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MergeError(f"Execution Manifest 解析失败：{exc}") from exc
        if not isinstance(manifest, dict):
            raise MergeError("Execution Manifest 顶层必须是 object。")
        manifest = self._normalize_identity(manifest, "Execution Manifest")
        if manifest.get("task_id") != self.task_id:
            raise MergeError("Execution Manifest task_id 与当前 task_id 不一致。")
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
        agent_outputs = self._resolve_within(
            self.agent_outputs,
            self.outputs_root,
            "task 模块产物目录",
        )
        dirs = []
        for module_id in self.module_ids:
            module_dir = agent_outputs / module_id
            if not module_dir.is_dir():
                raise MergeError(f"模块产物目录不存在：{module_dir}")
            resolved_module_dir = self._resolve_within(
                module_dir,
                agent_outputs,
                f"{module_id} 模块产物目录",
            )
            if resolved_module_dir != module_dir:
                raise MergeError(
                    f"{module_id} 模块产物目录不在对应授权目录内：{module_dir}"
                )
            dirs.append(resolved_module_dir)
        return dirs

    def _load_artifacts(self, module_dirs):
        artifacts = {}
        for module_dir in module_dirs:
            artifact_path = module_dir / "artifact_manifest.json"
            if not artifact_path.exists():
                raise MergeError(f"缺少 artifact_manifest.json：{artifact_path}")
            artifact_path = self._resolve_within(
                artifact_path,
                module_dir,
                f"{module_dir.name} artifact_manifest.json",
            )
            if not artifact_path.is_file():
                raise MergeError(f"artifact_manifest.json 不是文件：{artifact_path}")
            try:
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise MergeError(f"artifact_manifest.json 解析失败：{artifact_path}: {exc}") from exc
            if isinstance(artifact, dict):
                artifact = self._normalize_identity(artifact, f"{module_dir.name} artifact_manifest")
            self._validate_artifact(module_dir.name, module_dir, artifact)
            artifacts[module_dir.name] = artifact
            self.validated_artifacts.append(str(artifact_path))
        return artifacts

    def _validate_artifact(self, module_id, module_dir, artifact):
        if not isinstance(artifact, dict):
            raise MergeError(f"{module_id} artifact_manifest 顶层必须是 object。")
        if artifact.get("task_id") != self.task_id:
            raise MergeError(f"{module_id} artifact_manifest task_id 不一致。")
        if artifact.get("module_id") != module_id:
            raise MergeError(f"{module_id} artifact_manifest module_id 不一致。")
        if artifact.get("status") != "success":
            raise MergeError(f"{module_id} artifact_manifest status 必须为 success。")
        produced_files = artifact.get("produced_files")
        if not isinstance(produced_files, list):
            raise MergeError(f"{module_id} artifact_manifest produced_files 必须是数组。")
        actual_files = {}
        for path in module_dir.rglob("*"):
            if not path.is_file() or path.name == "artifact_manifest.json":
                continue
            relative = str(path.relative_to(module_dir)).replace("\\", "/")
            resolved_path = self._resolve_within(
                path,
                module_dir,
                f"{module_id} 模块文件 {relative}",
            )
            relative_key = windows_path_key(relative)
            existing = actual_files.get(relative_key)
            if existing is not None:
                raise MergeError(
                    f"{module_id} 模块实际文件存在 Windows 等价重复路径："
                    f"{existing['relative']} 与 {relative}"
                )
            actual_files[relative_key] = {
                "relative": relative,
                "path": resolved_path,
            }

        declared = set()
        for item in produced_files:
            if not isinstance(item, dict):
                raise MergeError(f"{module_id} produced_files 每一项必须是 object。")
            relative = item.get("path")
            if not self._safe_relative_path(relative):
                raise MergeError(f"{module_id} 声明了不安全路径：{relative}")
            relative_key = windows_path_key(relative)
            if relative_key in declared:
                raise MergeError(f"{module_id} produced_files 存在重复路径：{relative}")
            declared.add(relative_key)
            if item.get("operation") not in ("create", "modify"):
                raise MergeError(f"{module_id} 声明了不支持的 operation：{item.get('operation')}")
            if item.get("required_for_merge") is True and relative_key not in actual_files:
                raise MergeError(f"{module_id} 声明文件不存在：{module_dir / relative}")
        undeclared = sorted(
            actual_files[key]["relative"]
            for key in actual_files.keys() - declared
        )
        if undeclared:
            raise MergeError(f"{module_id} 存在未声明文件：{', '.join(undeclared)}")
        self.artifact_sources[module_id] = actual_files

    def _merge_modules(self, module_dirs):
        for module_dir in module_dirs:
            artifact = self.artifacts[module_dir.name]
            for item in artifact.get("produced_files", []):
                if item.get("required_for_merge") is not True:
                    self.skipped_files.append(f"{module_dir.name}:{item.get('path')}")
                    continue
                relative = item["path"]
                relative_path = Path(*portable_path_parts(relative))
                source = self.artifact_sources[module_dir.name][
                    windows_path_key(relative)
                ]["path"]
                self._merge_file(module_dir.name, source, relative_path)
            self._record_ignored_files(module_dir, artifact)

    def _record_ignored_files(self, module_dir, artifact):
        declared = {
            windows_path_key(item.get("path"))
            for item in artifact.get("produced_files", [])
            if isinstance(item, dict)
        }
        for key, source in sorted(self.artifact_sources[module_dir.name].items()):
            if key not in declared:
                self.ignored_files.append(
                    {
                        "module": module_dir.name,
                        "path": source["relative"],
                        "reason": "not_declared",
                    }
                )

    def _merge_file(self, module_name, source, relative_path):
        target = self.merge_target_dir / relative_path
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

    def _publish_staging(self, staging_dir, staged_report):
        backup_dir = None
        if self.merged_dir.exists():
            backup_dir = Path(
                tempfile.mkdtemp(
                    dir=self.merged_dir.parent,
                    prefix=f".{self.merged_dir.name}.backup.",
                )
            )
            backup_dir.rmdir()
            try:
                self.merged_dir.rename(backup_dir)
            except OSError as exc:
                raise MergeError(f"旧合并快照备份失败：{exc}") from exc

        try:
            staging_dir.rename(self.merged_dir)
        except OSError as exc:
            if backup_dir is not None and backup_dir.exists():
                try:
                    backup_dir.rename(self.merged_dir)
                except OSError as rollback_exc:
                    raise MergeError(
                        f"新合并快照发布失败且旧快照恢复失败：{rollback_exc}"
                    ) from exc
            raise MergeError(f"新合并快照发布失败，旧快照已保留：{exc}") from exc

        report_path = self.reports_dir / "merge_report.json"
        try:
            os.replace(staged_report, report_path)
        except OSError as exc:
            try:
                shutil.rmtree(self.merged_dir)
                if backup_dir is not None and backup_dir.exists():
                    backup_dir.rename(self.merged_dir)
            except OSError as rollback_exc:
                raise MergeError(
                    f"合并报告发布失败且旧快照恢复失败：{rollback_exc}"
                ) from exc
            raise MergeError(f"合并报告发布失败，旧快照和报告已恢复：{exc}") from exc

        if backup_dir is not None:
            shutil.rmtree(backup_dir, ignore_errors=True)

    def _write_conflict_report(self):
        report = {
            "status": "conflict",
            "task_id": self.task_id,
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

    def _stage_merge_report(self, module_dirs, snapshot_digest):
        report = {
            "status": "success",
            "task_id": self.task_id,
            "workspace_root": self._report_path(self.root),
            "manifest_path": self._report_path(self.manifest_path),
            "outputs_dir": self._report_path(self.agent_outputs),
            "merged_dir": self._report_path(self.merged_dir),
            "snapshot_digest": snapshot_digest,
            "modules": [p.name for p in module_dirs],
            "validated_artifacts": [self._report_path(path) for path in self.validated_artifacts],
            "merged_files": self.merged_files,
            "skipped_files": sorted(set(self.skipped_files)),
            "ignored_files": self.ignored_files,
        }
        try:
            descriptor, temp_name = tempfile.mkstemp(
                dir=self.reports_dir,
                prefix=".merge-report.",
                suffix=".tmp",
            )
            os.close(descriptor)
            staged_report = Path(temp_name)
            staged_report.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return staged_report
        except OSError as exc:
            if "staged_report" in locals():
                staged_report.unlink(missing_ok=True)
            raise MergeError(f"合并报告暂存失败：{exc}") from exc

    def _safe_relative_path(self, value):
        return is_safe_relative_path(
            value,
            protected_roots=PROTECTED_ROOTS,
        )

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
    parser.add_argument("--task-id", default=os.getenv("SUPERLOOPER_TASK_ID"), help="执行任务 ID；缺省时尝试从 .superlooper/outputs 目录唯一推断。")
    parser.add_argument("--session-id", default=os.getenv("SUPERLOOPER_SESSION_ID"), help=argparse.SUPPRESS)
    parser.add_argument("--outputs-dir", default=os.getenv("SUPERLOOPER_OUTPUTS_DIR"), help="模块产物根目录，默认 <workspace-root>/.superlooper/outputs。")
    parser.add_argument("--merged-dir", default=os.getenv("SUPERLOOPER_MERGED_DIR"), help="合并输出目录，默认 <workspace-root>/.superlooper/merged/<task-id>。")
    parser.add_argument("--reports-dir", default=os.getenv("SUPERLOOPER_REPORTS_DIR"), help="报告输出目录，默认 <workspace-root>/.superlooper/reports/<task-id>。")
    parser.add_argument("--manifest-path", default=os.getenv("SUPERLOOPER_MANIFEST_PATH"), help="Execution Manifest 路径，默认 <workspace-root>/.superlooper/manifests/<task-id>/execution_manifest.json。")
    parser.add_argument("--redact-paths", action="store_true", help="将 JSON 报告中的 workspace_root 与工作区内绝对路径脱敏为相对路径。")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        task_id = resolve_explicit_task_id(args.task_id, args.session_id)
        engine = ParallelMergeEngine(
            workspace_root=args.workspace_root,
            task_id=task_id,
            outputs_dir=args.outputs_dir,
            merged_dir=args.merged_dir,
            reports_dir=args.reports_dir,
            manifest_path=args.manifest_path,
            redact_paths=args.redact_paths,
        )
        return engine.run()
    except (MergeError, SessionStateValidationError) as exc:
        print(f"合并失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
