import argparse
import filecmp
import json
import os
import re
import shutil
import sys
from pathlib import Path

from validate_miao_contracts import ContractValidator


SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
PROTECTED_ROOTS = {".superlooper", ".git", ".svn", ".hg"}


class ApplyError(Exception):
    pass


class WorkspaceApplyEngine:
    def __init__(self, workspace_root, session_id=None, merged_dir=None, reports_dir=None, merge_report_path=None, overwrite_existing=False, overwrite_files=None, redact_paths=False):
        self.root = Path(workspace_root).resolve()
        self.redact_paths = redact_paths
        self.session_id = session_id or os.getenv("SUPERLOOPER_SESSION_ID")
        self._validate_session_id(self.session_id)
        self.merged_dir = self._resolve_scoped_path(merged_dir, self.root / ".superlooper" / "merged" / self.session_id)
        self.reports_dir = self._resolve_scoped_path(reports_dir, self.root / ".superlooper" / "reports" / self.session_id)
        self.merge_report_path = self._resolve_scoped_path(merge_report_path, self.reports_dir / "merge_report.json")
        self.overwrite_existing = overwrite_existing
        self.overwrite_files = self._normalize_overwrite_files(overwrite_files or [])
        self.apply_plan = []
        self.conflicts = []
        self.applied_files = []
        self.identical_files = []
        self.workspace_validation = None

    def run(self):
        self._validate_inputs()
        self._validate_quality_gates()
        merge_report = self._load_merge_report()
        artifact_operations = self._load_artifact_operations(merge_report)
        paths = self._collect_apply_paths(merge_report)
        self._build_apply_plan(paths, artifact_operations)

        if self.conflicts:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            self._write_conflict_report()
            return 2

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._apply_files()
        self.workspace_validation = self._validate_workspace_after_apply()
        self._write_apply_report()
        if self.workspace_validation["status"] != "PASS":
            return 1
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

    def _normalize_overwrite_files(self, values):
        result = set()
        for value in values:
            if not self._safe_relative_path(value):
                raise ApplyError(f"--overwrite-file 不是安全相对路径：{value}")
            result.add(value.replace("\\", "/"))
        return result

    def _validate_session_id(self, session_id):
        if not session_id or not SESSION_PATTERN.match(session_id):
            raise ApplyError("session_id 只能包含字母、数字、下划线、短横线和点。")

    def _validate_inputs(self):
        if not self.root.exists():
            raise ApplyError(f"workspace_root 不存在：{self.root}")
        if not self.merged_dir.exists():
            raise ApplyError(f"合并目录不存在：{self.merged_dir}")
        if not self.merge_report_path.exists():
            raise ApplyError(f"合并报告不存在：{self.merge_report_path}")

    def _validate_quality_gates(self):
        validator = ContractValidator(self.root, self.session_id)
        validator.validate_code_review_report(required=True)
        validator.validate_test_report(required=True)
        if validator.errors:
            raise ApplyError("质量门禁未通过：" + "；".join(validator.errors))

    def _load_merge_report(self):
        try:
            report = json.loads(self.merge_report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ApplyError(f"merge_report.json 解析失败：{exc}") from exc
        if not isinstance(report, dict):
            raise ApplyError("merge_report.json 顶层必须是 object。")
        if report.get("status") != "success":
            raise ApplyError("merge_report.json status 必须为 success。")
        if report.get("session_id") != self.session_id:
            raise ApplyError("merge_report.json session_id 与当前 session_id 不一致。")
        return report

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
            source = self.merged_dir / relative
            target = self.root / relative
            operation = artifact_operations.get(relative, "create")
            if operation not in ("create", "modify"):
                raise ApplyError(f"merge_report 引用了不支持的 operation：{operation}")
            if not source.exists() or not source.is_file():
                raise ApplyError(f"合并文件不存在：{source}")
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
        for item in self.apply_plan:
            relative = item["path"]
            action = item["action"]
            source = item["source"]
            target = item["target"]
            if action == "identical":
                self.identical_files.append(relative)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            self.applied_files.append({"path": relative, "action": action})

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
            if not source.is_file():
                result["result"] = "FAIL"
                result["reason"] = "missing_source_file"
            elif not target.is_file():
                result["result"] = "FAIL"
                result["reason"] = "missing_workspace_file"
            elif not filecmp.cmp(source, target, shallow=False):
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
            "session_id": self.session_id,
            "workspace_root": self._report_path(self.root),
            "merged_dir": self._report_path(self.merged_dir),
            "merge_report_path": self._report_path(self.merge_report_path),
            "overwrite_existing": self.overwrite_existing,
            "overwrite_files": sorted(self.overwrite_files),
            "applied_files": self.applied_files,
            "identical_files": sorted(self.identical_files),
            "workspace_validation": validation,
        }
        report_path = self.reports_dir / "apply_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
            "session_id": self.session_id,
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
        if not isinstance(value, str) or not value or ":" in value:
            return False
        path = Path(value)
        normalized_parts = [part for part in path.parts if part not in ("", ".")]
        if not normalized_parts:
            return False
        if normalized_parts[0] in PROTECTED_ROOTS:
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
            "target": self._report_path(item.get("target")),
            "source": self._report_path(item.get("source")),
        }


def parse_args():
    parser = argparse.ArgumentParser(description="Apply SUPERLOOPER merged backend artifacts into the target project workspace.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", default=os.getenv("SUPERLOOPER_SESSION_ID"), help="执行会话 ID。")
    parser.add_argument("--merged-dir", default=os.getenv("SUPERLOOPER_MERGED_DIR"), help="合并输出目录，默认 <workspace-root>/.superlooper/merged/<session-id>。")
    parser.add_argument("--reports-dir", default=os.getenv("SUPERLOOPER_REPORTS_DIR"), help="报告输出目录，默认 <workspace-root>/.superlooper/reports/<session-id>。")
    parser.add_argument("--merge-report-path", default=os.getenv("SUPERLOOPER_MERGE_REPORT_PATH"), help="合并报告路径，默认 <workspace-root>/.superlooper/reports/<session-id>/merge_report.json。")
    parser.add_argument("--overwrite-existing", action="store_true", help="允许覆盖 artifact_manifest 中 operation=modify 的所有已有差异文件。")
    parser.add_argument("--overwrite-file", action="append", default=[], help="只覆盖指定的 operation=modify 冲突文件；可重复传入。")
    parser.add_argument("--redact-paths", action="store_true", help="将 JSON 报告中的 workspace_root 与工作区内绝对路径脱敏为相对路径。")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        engine = WorkspaceApplyEngine(
            workspace_root=args.workspace_root,
            session_id=args.session_id,
            merged_dir=args.merged_dir,
            reports_dir=args.reports_dir,
            merge_report_path=args.merge_report_path,
            overwrite_existing=args.overwrite_existing,
            overwrite_files=args.overwrite_file,
            redact_paths=args.redact_paths,
        )
        return engine.run()
    except ApplyError as exc:
        print(f"应用失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
