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
)
from snapshot_digest import compute_tree_digest
from validate_miao_contracts import ContractValidator


TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
SNAPSHOT_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
PROTECTED_ROOTS = {".superlooper", ".git", ".svn", ".hg"}


class ApplyError(Exception):
    pass


class WorkspaceApplyEngine:
    def __init__(self, workspace_root, task_id=None, merged_dir=None, reports_dir=None, merge_report_path=None, overwrite_existing=False, overwrite_files=None, redact_paths=False):
        self.root = Path(workspace_root).resolve()
        self.redact_paths = redact_paths
        self.task_id = task_id or os.getenv("SUPERLOOPER_TASK_ID")
        self._validate_task_id(self.task_id)
        self.merged_dir = self._resolve_scoped_path(merged_dir, self.root / ".superlooper" / "merged" / self.task_id)
        self.reports_dir = self._resolve_scoped_path(reports_dir, self.root / ".superlooper" / "reports" / self.task_id)
        self.merge_report_path = self._resolve_scoped_path(merge_report_path, self.reports_dir / "merge_report.json")
        self.overwrite_existing = overwrite_existing
        self.overwrite_files = self._normalize_overwrite_files(overwrite_files or [])
        self.apply_plan = []
        self.conflicts = []
        self.applied_files = []
        self.identical_files = []
        self.workspace_validation = None
        self.snapshot_digest = None
        self.failure = None
        self.transaction_operations = []
        self.created_directories = []
        self.backup_dir = None
        self.rollback = {
            "status": "not_required",
            "backup_dir": None,
            "failures": [],
        }

    def run(self):
        self._invalidate_apply_report()
        self._validate_inputs()
        self._validate_quality_gates()
        merge_report = self._load_merge_report()
        self._validate_snapshot_digest(merge_report)
        artifact_operations = self._load_artifact_operations(merge_report)
        paths = self._collect_apply_paths(merge_report)
        self._build_apply_plan(paths, artifact_operations)

        if self.conflicts:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            self._write_conflict_report()
            return 2

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        try:
            applied = self._apply_files()
        except (ApplyError, OSError, shutil.Error) as exc:
            self._set_transaction_failure("apply", exc)
            self.workspace_validation = self._failure_validation("apply_io_error")
            self._rollback_transaction()
            self._write_failed_report_safely()
            return 1
        if not applied:
            self._write_failed_report_safely()
            return 1

        try:
            self.workspace_validation = self._validate_workspace_after_apply()
        except (ApplyError, OSError, shutil.Error) as exc:
            self._set_transaction_failure("workspace_validation", exc)
            self.workspace_validation = self._failure_validation("workspace_validation_error")
            self._rollback_transaction()
            self._write_failed_report_safely()
            return 1

        if self.workspace_validation["status"] != "PASS":
            self.failure = {
                "stage": "workspace_validation",
                "path": None,
                "action": None,
                "error": "workspace validation failed",
            }
            self._rollback_transaction()
            self._write_failed_report_safely()
            return 1

        try:
            self._write_apply_report()
        except (ApplyError, OSError, shutil.Error) as exc:
            self._set_transaction_failure("success_report_publish", exc)
            self._rollback_transaction()
            self.workspace_validation = self._failure_validation("success_report_publish_failed")
            self._write_failed_report_safely()
            return 1

        self._cleanup_transaction()
        return 0

    def _resolve_scoped_path(self, value, default):
        path = Path(value) if value else Path(default)
        if value and not path.is_absolute() and (":" in str(value) or path.drive):
            raise ApplyError(f"相对路径不能包含盘符或冒号：{value}")
        if not path.is_absolute():
            path = self.root / path
        path = path.resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ApplyError(f"路径必须位于 workspace_root 内：{path}") from exc
        return path

    def _resolve_within(self, path, root, label, strict=False):
        try:
            resolved_root = Path(root).resolve(strict=True)
            resolved = Path(path).resolve(strict=strict)
        except OSError as exc:
            raise ApplyError(f"{label} 真实路径解析失败：{path}: {exc}") from exc
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise ApplyError(
                f"{label} 不在授权目录内：{path} -> {resolved}"
            ) from exc
        return resolved

    def _normalize_overwrite_files(self, values):
        result = set()
        for value in values:
            if not self._safe_relative_path(value):
                raise ApplyError(f"--overwrite-file 不是安全相对路径：{value}")
            result.add(value.replace("\\", "/"))
        return result

    def _validate_task_id(self, task_id):
        if not task_id or not TASK_ID_PATTERN.match(task_id):
            raise ApplyError("task_id 只能包含字母、数字、下划线、短横线和点。")

    def _invalidate_apply_report(self):
        report_path = self.reports_dir / "apply_report.json"
        try:
            report_path.unlink(missing_ok=True)
        except OSError as exc:
            raise ApplyError(f"旧应用报告失效失败：{exc}") from exc

    def _validate_inputs(self):
        if not self.root.exists():
            raise ApplyError(f"workspace_root 不存在：{self.root}")
        if not self.merged_dir.exists():
            raise ApplyError(f"合并目录不存在：{self.merged_dir}")
        if not self.merge_report_path.exists():
            raise ApplyError(f"合并报告不存在：{self.merge_report_path}")

    def _validate_quality_gates(self):
        validator = ContractValidator(self.root, self.task_id)
        validator.validate_code_review_report(required=True, require_pass=True)
        validator.validate_test_report(required=True)
        if validator.errors:
            raise ApplyError("质量门禁未通过：" + "；".join(validator.errors))

    def _normalize_identity(self, data, label):
        try:
            return normalize_legacy_identity(data, label)
        except SessionStateValidationError as exc:
            raise ApplyError(str(exc)) from exc

    def _load_merge_report(self):
        try:
            report = json.loads(self.merge_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ApplyError(f"merge_report.json 解析失败：{exc}") from exc
        if not isinstance(report, dict):
            raise ApplyError("merge_report.json 顶层必须是 object。")
        report = self._normalize_identity(report, "merge_report.json")
        if report.get("status") != "success":
            raise ApplyError("merge_report.json status 必须为 success。")
        if report.get("task_id") != self.task_id:
            raise ApplyError("merge_report.json task_id 与当前 task_id 不一致。")
        return report

    def _validate_snapshot_digest(self, merge_report):
        expected = merge_report.get("snapshot_digest")
        if not isinstance(expected, str) or not SNAPSHOT_DIGEST_PATTERN.fullmatch(expected):
            raise ApplyError("merge_report.json snapshot_digest 必须为 sha256:<64hex>。")
        try:
            actual = compute_tree_digest(self.merged_dir)
        except OSError as exc:
            raise ApplyError(f"merged tree snapshot_digest 计算失败：{exc}") from exc
        if actual != expected:
            raise ApplyError(
                "merge_report.json snapshot_digest 与 merged tree 不一致："
                f"expected={expected}, actual={actual}"
            )
        self.snapshot_digest = expected

    def _load_artifact_operations(self, merge_report):
        operations = {}
        for artifact_path in merge_report.get("validated_artifacts", []):
            artifact_file = self._resolve_scoped_path(artifact_path, artifact_path)
            if not artifact_file.exists():
                raise ApplyError(f"artifact_manifest.json 不存在：{artifact_file}")
            try:
                artifact = json.loads(artifact_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ApplyError(f"artifact_manifest.json 解析失败：{artifact_file}: {exc}") from exc
            if not isinstance(artifact, dict):
                raise ApplyError(f"artifact_manifest.json 顶层必须是 object：{artifact_file}")
            artifact = self._normalize_identity(artifact, str(artifact_file))
            for item in artifact.get("produced_files", []):
                if not isinstance(item, dict) or item.get("required_for_merge") is not True:
                    continue
                operation = item.get("operation", "create")
                if operation not in ("create", "modify"):
                    raise ApplyError(f"artifact_manifest.json 存在不支持的 operation：{operation}")
                relative = item.get("path")
                if self._safe_relative_path(relative):
                    operations[relative.replace("\\", "/")] = operation
        return operations

    def _collect_apply_paths(self, merge_report):
        paths = []
        seen = set()
        for item in merge_report.get("merged_files", []):
            if not isinstance(item, dict):
                continue
            relative = item.get("path")
            if not self._safe_relative_path(relative):
                raise ApplyError(f"merge_report 中存在不安全路径：{relative}")
            normalized = relative.replace("\\", "/")
            if normalized not in seen:
                seen.add(normalized)
                paths.append(normalized)
        if not paths:
            raise ApplyError("merge_report 中没有可应用文件。")
        return paths

    def _build_apply_plan(self, paths, artifact_operations):
        for relative in paths:
            path_parts = portable_path_parts(relative)
            source = self.merged_dir.joinpath(*path_parts)
            target = self.root.joinpath(*path_parts)
            operation = artifact_operations.get(relative, "create")
            if operation not in ("create", "modify"):
                raise ApplyError(f"merge_report 引用了不支持的 operation：{operation}")
            resolved_source = self._resolve_within(
                source,
                self.merged_dir,
                f"合并文件 {relative}",
                strict=True,
            )
            if not resolved_source.is_file():
                raise ApplyError(f"合并文件不存在：{source}")
            self._resolve_within(
                target,
                self.root,
                f"工作区目标 {relative}",
                strict=False,
            )
            if target.exists() and not target.is_file():
                self.conflicts.append({"path": relative, "reason": "target_exists_not_file", "target": str(target)})
                continue
            if not target.exists():
                self.apply_plan.append({"path": relative, "source": source, "target": target, "action": "create"})
                continue
            if filecmp.cmp(source, target, shallow=False):
                self.apply_plan.append({"path": relative, "source": source, "target": target, "action": "identical"})
                continue
            if operation == "modify" and (self.overwrite_existing or relative in self.overwrite_files):
                self.apply_plan.append({"path": relative, "source": source, "target": target, "action": "overwrite"})
                continue
            reason = "target_differs"
            if operation == "modify":
                reason = "modify_requires_overwrite_existing"
            self.conflicts.append({"path": relative, "reason": reason, "target": str(target), "source": str(source), "operation": operation})

    def _apply_files(self):
        self.backup_dir = Path(
            tempfile.mkdtemp(
                dir=self.reports_dir,
                prefix=".apply-backup.",
            )
        )
        self.transaction_operations = []
        self.created_directories = []
        current_item = None
        try:
            for item in self.apply_plan:
                current_item = item
                relative = item["path"]
                action = item["action"]
                source = item["source"]
                target = item["target"]
                self._resolve_within(
                    source,
                    self.merged_dir,
                    f"合并文件 {relative}",
                    strict=True,
                )
                self._resolve_within(
                    target,
                    self.root,
                    f"工作区目标 {relative}",
                    strict=False,
                )
                if action == "identical":
                    self.identical_files.append(relative)
                    continue

                missing_directories = []
                parent = target.parent
                while parent != self.root and not parent.exists():
                    missing_directories.append(parent)
                    parent = parent.parent
                self._resolve_within(
                    target,
                    self.root,
                    f"工作区目标 {relative}",
                    strict=False,
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                self._resolve_within(
                    target,
                    self.root,
                    f"工作区目标 {relative}",
                    strict=False,
                )
                for directory in reversed(missing_directories):
                    if directory not in self.created_directories:
                        self.created_directories.append(directory)

                operation = {
                    "path": relative,
                    "action": action,
                    "target": target,
                    "backup": None,
                }
                self.transaction_operations.append(operation)
                if action == "overwrite":
                    backup = self.backup_dir.joinpath(*portable_path_parts(relative))
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    operation["backup"] = backup
                    self._resolve_within(
                        target,
                        self.root,
                        f"工作区目标 {relative}",
                        strict=False,
                    )
                    shutil.move(target, backup)

                self._resolve_within(
                    source,
                    self.merged_dir,
                    f"合并文件 {relative}",
                    strict=True,
                )
                self._resolve_within(
                    target,
                    self.root,
                    f"工作区目标 {relative}",
                    strict=False,
                )
                shutil.copy2(source, target)
                self.applied_files.append({"path": relative, "action": action})
        except (ApplyError, OSError, shutil.Error) as exc:
            self.failure = {
                "path": current_item["path"] if current_item else None,
                "action": current_item["action"] if current_item else None,
                "error": str(exc),
            }
            self._rollback_transaction()
            self.workspace_validation = {
                "status": "FAIL",
                "checked_file_count": 1,
                "matched_file_count": 0,
                "failed_file_count": 1,
                "checked_files": [
                    {
                        "path": self.failure["path"],
                        "action": self.failure["action"],
                        "result": "FAIL",
                        "reason": "apply_io_error",
                    }
                ],
                "failures": [
                    {
                        "path": self.failure["path"],
                        "reason": "apply_io_error",
                    }
                ],
            }
            return False

        return True

    def _rollback_transaction(self):
        if self.backup_dir is None:
            return
        self.rollback = self._rollback_apply(
            self.transaction_operations,
            self.created_directories,
            self.backup_dir,
        )

    def _cleanup_transaction(self):
        if self.backup_dir is not None:
            shutil.rmtree(self.backup_dir, ignore_errors=True)

    def _rollback_apply(self, operations, created_directories, backup_dir):
        failures = []
        for operation in reversed(operations):
            target = operation["target"]
            backup = operation["backup"]
            try:
                self._resolve_within(
                    target,
                    self.root,
                    f"回滚目标 {operation['path']}",
                    strict=False,
                )
                if operation["action"] == "create":
                    if target.exists() or target.is_symlink():
                        target.unlink()
                    continue
                if backup is not None and backup.exists():
                    if target.exists() or target.is_symlink():
                        target.unlink()
                    self._resolve_within(
                        target,
                        self.root,
                        f"回滚目标 {operation['path']}",
                        strict=False,
                    )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    self._resolve_within(
                        target,
                        self.root,
                        f"回滚目标 {operation['path']}",
                        strict=False,
                    )
                    shutil.move(backup, target)
                elif backup is not None:
                    raise OSError("overwrite backup missing")
            except (ApplyError, OSError, shutil.Error) as exc:
                failures.append(
                    {
                        "path": operation["path"],
                        "action": operation["action"],
                        "error": str(exc),
                    }
                )

        for directory in reversed(created_directories):
            try:
                self._resolve_within(
                    directory,
                    self.root,
                    f"回滚目录 {directory}",
                    strict=False,
                )
                directory.rmdir()
            except (ApplyError, OSError) as exc:
                failures.append(
                    {
                        "path": str(directory),
                        "action": "remove_created_directory",
                        "error": str(exc),
                    }
                )

        status = "partial" if failures else "success"
        if status == "success":
            shutil.rmtree(backup_dir, ignore_errors=True)
        return {
            "status": status,
            "backup_dir": self._report_path(backup_dir) if status == "partial" else None,
            "failures": failures,
        }

    def _set_transaction_failure(self, stage, exc):
        self.failure = {
            "stage": stage,
            "path": None,
            "action": None,
            "error": str(exc),
        }

    def _failure_validation(self, reason):
        return {
            "status": "FAIL",
            "checked_file_count": 1,
            "matched_file_count": 0,
            "failed_file_count": 1,
            "checked_files": [
                {
                    "path": self.failure.get("path") if self.failure else None,
                    "action": self.failure.get("action") if self.failure else None,
                    "result": "FAIL",
                    "reason": reason,
                }
            ],
            "failures": [
                {
                    "path": self.failure.get("path") if self.failure else None,
                    "reason": reason,
                }
            ],
        }

    def _write_failed_report_safely(self):
        try:
            self._write_apply_report()
        except (ApplyError, OSError, shutil.Error):
            try:
                (self.reports_dir / "apply_report.json").unlink(missing_ok=True)
            except OSError:
                pass

    def _validate_workspace_after_apply(self):
        checked_files = []
        failures = []
        for item in self.apply_plan:
            source = item["source"]
            target = item["target"]
            relative = item["path"]
            result = {
                "path": relative,
                "action": item["action"],
                "source": self._report_path(source),
                "target": self._report_path(target),
                "result": "PASS",
            }
            try:
                self._resolve_within(
                    source,
                    self.merged_dir,
                    f"合并文件 {relative}",
                    strict=True,
                )
                self._resolve_within(
                    target,
                    self.root,
                    f"工作区目标 {relative}",
                    strict=False,
                )
            except ApplyError:
                result["result"] = "FAIL"
                result["reason"] = "real_path_escape"
            if result["result"] == "PASS" and not source.is_file():
                result["result"] = "FAIL"
                result["reason"] = "missing_source_file"
            elif result["result"] == "PASS" and not target.is_file():
                result["result"] = "FAIL"
                result["reason"] = "missing_workspace_file"
            elif result["result"] == "PASS" and not filecmp.cmp(source, target, shallow=False):
                result["result"] = "FAIL"
                result["reason"] = "content_mismatch"
            checked_files.append(result)
            if result["result"] != "PASS":
                failures.append({"path": relative, "reason": result["reason"]})
        checked_count = len(checked_files)
        failed_count = len(failures)
        return {
            "status": "PASS" if failed_count == 0 else "FAIL",
            "checked_file_count": checked_count,
            "matched_file_count": checked_count - failed_count,
            "failed_file_count": failed_count,
            "checked_files": checked_files,
            "failures": failures,
        }

    def _write_apply_report(self):
        self._remove_stale_conflict_report()
        validation = self.workspace_validation or {
            "status": "PASS",
            "checked_file_count": 0,
            "matched_file_count": 0,
            "failed_file_count": 0,
            "checked_files": [],
            "failures": [],
        }
        report = {
            "status": "success" if validation["status"] == "PASS" else "failed",
            "task_id": self.task_id,
            "workspace_root": self._report_path(self.root),
            "merged_dir": self._report_path(self.merged_dir),
            "merge_report_path": self._report_path(self.merge_report_path),
            "snapshot_digest": self.snapshot_digest,
            "overwrite_existing": self.overwrite_existing,
            "overwrite_files": sorted(self.overwrite_files),
            "applied_files": self.applied_files,
            "identical_files": sorted(self.identical_files),
            "failure": self.failure,
            "rollback": self.rollback,
            "workspace_validation": validation,
        }
        report_path = self.reports_dir / "apply_report.json"
        descriptor, temp_name = tempfile.mkstemp(
            dir=self.reports_dir,
            prefix=".apply-report.",
            suffix=".tmp",
        )
        os.close(descriptor)
        staged_report = Path(temp_name)
        try:
            staged_report.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(staged_report, report_path)
        finally:
            staged_report.unlink(missing_ok=True)
        if report["status"] == "success":
            print(f"应用完成，报告已生成：{report_path}")
        else:
            print(f"应用后工作区验证失败，报告已生成：{report_path}", file=sys.stderr)

    def _remove_stale_conflict_report(self):
        conflict_report = self.reports_dir / "apply_conflict_report.json"
        if conflict_report.exists():
            conflict_report.unlink()

    def _write_conflict_report(self):
        report = {
            "status": "conflict",
            "task_id": self.task_id,
            "workspace_root": self._report_path(self.root),
            "merged_dir": self._report_path(self.merged_dir),
            "merge_report_path": self._report_path(self.merge_report_path),
            "overwrite_existing": self.overwrite_existing,
            "overwrite_files": sorted(self.overwrite_files),
            "conflicts": [self._report_conflict_item(item) for item in self.conflicts],
        }
        report_path = self.reports_dir / "apply_conflict_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"检测到 {len(self.conflicts)} 个应用冲突，报告已生成：{report_path}")

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
            "target": self._report_path(item.get("target")),
            "source": self._report_path(item.get("source")),
        }


def parse_args():
    parser = argparse.ArgumentParser(description="Apply SUPERLOOPER merged backend artifacts into the target project workspace.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--task-id", default=os.getenv("SUPERLOOPER_TASK_ID"), help="执行任务 ID。")
    parser.add_argument("--session-id", default=os.getenv("SUPERLOOPER_SESSION_ID"), help=argparse.SUPPRESS)
    parser.add_argument("--merged-dir", default=os.getenv("SUPERLOOPER_MERGED_DIR"), help="合并输出目录，默认 <workspace-root>/.superlooper/merged/<task-id>。")
    parser.add_argument("--reports-dir", default=os.getenv("SUPERLOOPER_REPORTS_DIR"), help="报告输出目录，默认 <workspace-root>/.superlooper/reports/<task-id>。")
    parser.add_argument("--merge-report-path", default=os.getenv("SUPERLOOPER_MERGE_REPORT_PATH"), help="合并报告路径，默认 <workspace-root>/.superlooper/reports/<task-id>/merge_report.json。")
    parser.add_argument("--overwrite-existing", action="store_true", help="允许覆盖 artifact_manifest 中 operation=modify 的所有已有差异文件。")
    parser.add_argument("--overwrite-file", action="append", default=[], help="只覆盖指定的 operation=modify 冲突文件；可重复传入。")
    parser.add_argument("--redact-paths", action="store_true", help="将 JSON 报告中的 workspace_root 与工作区内绝对路径脱敏为相对路径。")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        task_id = resolve_explicit_task_id(args.task_id, args.session_id, required=True)
        engine = WorkspaceApplyEngine(
            workspace_root=args.workspace_root,
            task_id=task_id,
            merged_dir=args.merged_dir,
            reports_dir=args.reports_dir,
            merge_report_path=args.merge_report_path,
            overwrite_existing=args.overwrite_existing,
            overwrite_files=args.overwrite_file,
            redact_paths=args.redact_paths,
        )
        return engine.run()
    except (ApplyError, SessionStateValidationError) as exc:
        print(f"应用失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
