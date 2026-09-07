import argparse
import json
import os
import re
import sys
from pathlib import Path

from create_session import (
    SessionStateValidationError,
    load_state_from_path,
    resolve_workspace_root,
    state_file_path,
    validate_session_id,
)


SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
REPORT_FILES = {
    "code_review_report": "code_review_report.md",
    "merge_report": "merge_report.json",
    "conflict_report": "conflict_report.json",
    "test_report": "test_report.md",
    "apply_report": "apply_report.json",
    "apply_conflict_report": "apply_conflict_report.json",
    "requirement_alignment_report": "requirement_alignment_report.md",
}
RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"
RESULT_WAITING_REVIEW = "WAITING_REVIEW"
RESULT_BLOCKED = "BLOCKED"
REPORT_OK = "ok"
REPORT_MISSING = "missing"
REPORT_INVALID = "invalid"


class SessionReportError(Exception):
    pass


class SessionReportBuilder:
    def __init__(self, workspace_root, session_id, redact_paths=False):
        self.workspace_root = resolve_workspace_root(workspace_root)
        self.session_id = self._validate_session_id(session_id)
        self.redact_paths = redact_paths
        self.runtime_root = self.workspace_root / ".superlooper"
        self.state_path = state_file_path(self.workspace_root, self.session_id)
        self.reports_dir = self.runtime_root / "reports" / self.session_id
        self.report_path = self.reports_dir / "session_report.md"
        self.state = self._load_state()

    def run(self):
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        report_files = self._collect_report_files()
        summary = self._build_summary(report_files)
        content = self._render_report(summary, report_files)
        self.report_path.write_text(content, encoding="utf-8")
        print(self.report_path)
        return 0

    def _validate_session_id(self, session_id):
        if not session_id or session_id in {".", ".."} or not SESSION_PATTERN.match(session_id):
            raise SessionReportError("session_id 只能包含字母、数字、下划线、短横线和点，且不能为 . 或 ..。")
        return session_id

    def _load_state(self):
        try:
            return load_state_from_path(self.state_path)
        except SessionStateValidationError as exc:
            raise SessionReportError(str(exc)) from exc

    def _collect_report_files(self):
        files = {}
        for key, filename in REPORT_FILES.items():
            path = self.reports_dir / filename
            files[key] = {
                "path": path,
                "exists": path.exists(),
                "contract_path": self._contract_path(path),
            }
        return files

    def _build_summary(self, report_files):
        current_phase = self.state["current_phase"]
        phase_status = self.state["phase_status"]
        inputs = {
            "requirement_path": self._state_or_default("requirement_path", "unknown"),
            "prd_path": self._state_or_default("prd_path", f".superlooper/context/{self.session_id}/prd.md"),
            "design_docs_path": self._state_or_default("design_docs_path", f".superlooper/context/{self.session_id}/design/"),
            "module_split_path": self._state_or_default("module_split_path", f".superlooper/manifests/{self.session_id}/module-split.json"),
            "execution_manifest_path": self._state_or_default("execution_manifest_path", f".superlooper/manifests/{self.session_id}/execution_manifest.json"),
        }
        result, reason = self._derive_result(report_files, current_phase, phase_status)
        apply_report = self._apply_report(report_files["apply_report"]["path"])
        return {
            "session_id": self.session_id,
            "workspace_root": self._display_path(self.state["workspace_root"]),
            "current_phase": current_phase,
            "phase_status": phase_status,
            "inputs": {key: self._display_path(value) for key, value in inputs.items()},
            "workspace_validation": apply_report.get("workspace_validation"),
            "result": result,
            "reason": reason,
        }

    def _state_or_default(self, key, default):
        value = self.state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default

    def _derive_result(self, report_files, current_phase, phase_status):
        state_is_passed = current_phase == "report" and phase_status == "passed"
        code_review = self._code_review_report(report_files["code_review_report"]["path"])
        test_report = self._test_report(report_files["test_report"]["path"])
        merge_report = self._json_status(report_files["merge_report"]["path"])
        apply_report = self._apply_report(report_files["apply_report"]["path"])
        alignment_report = self._requirement_alignment_report(report_files["requirement_alignment_report"]["path"])

        if report_files["apply_conflict_report"]["exists"]:
            if state_is_passed:
                return RESULT_BLOCKED, "state/report 不一致：state=report/passed，但存在 apply_conflict_report.json"
            return RESULT_BLOCKED, "发现 apply_conflict_report.json"

        if phase_status == "blocked":
            return RESULT_BLOCKED, self._state_or_default("last_error", "state.phase_status=blocked")

        if report_files["conflict_report"]["exists"]:
            if state_is_passed:
                return RESULT_FAIL, "state/report 不一致：state=report/passed，但存在 conflict_report.json"
            return RESULT_FAIL, "发现 conflict_report.json"

        required_reports = [
            ("code_review_report.md", code_review, "PASS"),
            ("test_report.md", test_report, "PASS"),
            ("merge_report.json", merge_report, "success"),
            ("apply_report.json", apply_report, "success"),
        ]
        fatal_problems = []
        pending_problems = []
        for filename, report, expected in required_reports:
            if report["state"] == REPORT_MISSING:
                pending_problems.append(f"缺少 {filename}")
                continue
            if report["state"] == REPORT_INVALID:
                fatal_problems.append(report["reason"])
                continue
            if report["status"] == "FAIL":
                fatal_problems.append(f"{filename} 指示 FAIL")
                continue
            if report["status"] != expected:
                fatal_problems.append(f"{filename} 状态不是 {expected}")

        if fatal_problems:
            if state_is_passed:
                return RESULT_FAIL, f"state/report 不一致：{'; '.join(fatal_problems)}"
            return RESULT_FAIL, "; ".join(fatal_problems)

        if phase_status == "running":
            return RESULT_WAITING_REVIEW, "当前阶段正在运行，等待执行完成后重新生成报告"

        if pending_problems:
            if state_is_passed:
                return RESULT_FAIL, f"state/report 不一致：{'; '.join(pending_problems)}"
            return RESULT_WAITING_REVIEW, "; ".join(pending_problems)

        if phase_status == "failed":
            return RESULT_FAIL, self._state_or_default("last_error", "state.phase_status=failed")

        if state_is_passed:
            if alignment_report["state"] == REPORT_MISSING:
                return RESULT_FAIL, "state/report 不一致：缺少 requirement_alignment_report.md"
            if alignment_report["state"] == REPORT_INVALID:
                return RESULT_FAIL, alignment_report["reason"]
            if alignment_report["status"] != "PASS":
                return RESULT_FAIL, "requirement_alignment_report.md 状态不是 PASS"
            return RESULT_PASS, "state=report/passed，且 code_review/test/merge/apply/requirement_alignment 报告全部通过"

        if apply_report["state"] == REPORT_OK and apply_report["status"] == "success":
            return RESULT_WAITING_REVIEW, "state/report 不一致：apply_report.json 已成功，但 state 不是 report/passed"

        if phase_status == "waiting_review":
            return RESULT_WAITING_REVIEW, "state.phase_status=waiting_review"
        if phase_status == "pending":
            return RESULT_WAITING_REVIEW, "state.phase_status=pending"
        return RESULT_WAITING_REVIEW, "缺少可判定的最终成功或失败信号"

    def _code_review_report(self, path):
        report = self._markdown_report(path)
        if report["state"] != REPORT_OK:
            return report
        data = report["data"]
        errors = []
        status = data.get("code_review_status")
        if status not in ("PASS", "FAIL"):
            errors.append("code_review_report.code_review_status 必须为 PASS 或 FAIL")
        if data.get("session_id") != self.session_id:
            errors.append("code_review_report.session_id 与当前 session_id 不一致")
        expected_path = f".superlooper/reports/{self.session_id}/code_review_report.md"
        if self._normalized_yaml_value(data.get("report_path")) != expected_path:
            errors.append(f"code_review_report.report_path 必须为 {expected_path}")
        blocker_count = self._yaml_int(data.get("blocker_count"), "code_review_report.blocker_count", errors)
        blocking_major_count = self._yaml_int(data.get("blocking_major_count"), "code_review_report.blocking_major_count", errors)
        if status == "PASS" and blocker_count != 0:
            errors.append("code_review_report.code_review_status=PASS 时 blocker_count 必须为 0")
        if status == "PASS" and blocking_major_count != 0:
            errors.append("code_review_report.code_review_status=PASS 时 blocking_major_count 必须为 0")
        if "reviewed_modules" not in data:
            errors.append("code_review_report.reviewed_modules 必须存在")
        if errors:
            return {"state": REPORT_INVALID, "status": None, "reason": "; ".join(errors)}
        return {"state": REPORT_OK, "status": status, "reason": None}

    def _test_report(self, path):
        report = self._markdown_report(path)
        if report["state"] != REPORT_OK:
            return report
        data = report["data"]
        errors = []
        status = data.get("test_status")
        if status not in ("PASS", "FAIL"):
            errors.append("test_report.test_status 必须为 PASS 或 FAIL")
        if data.get("session_id") != self.session_id:
            errors.append("test_report.session_id 与当前 session_id 不一致")
        expected_tested_path = f".superlooper/merged/{self.session_id}"
        if self._normalized_yaml_value(data.get("tested_path")) != expected_tested_path:
            errors.append(f"test_report.tested_path 必须为 {expected_tested_path}")
        expected_merge_report = f".superlooper/reports/{self.session_id}/merge_report.json"
        if self._normalized_yaml_value(data.get("merge_report_path")) != expected_merge_report:
            errors.append(f"test_report.merge_report_path 必须为 {expected_merge_report}")
        expected_report_path = f".superlooper/reports/{self.session_id}/test_report.md"
        if self._normalized_yaml_value(data.get("report_path")) != expected_report_path:
            errors.append(f"test_report.report_path 必须为 {expected_report_path}")
        if status != "PASS":
            errors.append("test_report.test_status 必须为 PASS 才能进入 apply")
        if errors:
            return {"state": REPORT_INVALID, "status": None, "reason": "; ".join(errors)}
        return {"state": REPORT_OK, "status": status, "reason": None}

    def _requirement_alignment_report(self, path):
        report = self._markdown_report(path)
        if report["state"] != REPORT_OK:
            return report
        data = report["data"]
        errors = []
        status = data.get("requirement_alignment_status")
        if status not in ("PASS", "FAIL"):
            errors.append("requirement_alignment_report.requirement_alignment_status 必须为 PASS 或 FAIL")
        unmet = self._yaml_int(data.get("unmet_requirement_count"), "requirement_alignment_report.unmet_requirement_count", errors)
        unchecked = self._yaml_int(data.get("unchecked_acceptance_count"), "requirement_alignment_report.unchecked_acceptance_count", errors)
        if status == "PASS" and unmet != 0:
            errors.append("requirement_alignment_report PASS 时 unmet_requirement_count 必须为 0")
        if status == "PASS" and unchecked != 0:
            errors.append("requirement_alignment_report PASS 时 unchecked_acceptance_count 必须为 0")
        if errors:
            return {"state": REPORT_INVALID, "status": None, "reason": "; ".join(errors)}
        return {"state": REPORT_OK, "status": status, "reason": None}

    def _markdown_report(self, path):
        if not path.exists():
            return {"state": REPORT_MISSING, "status": None, "reason": f"缺少 {path.name}"}
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise SessionReportError(f"读取 Markdown 报告失败：{path}: {exc}") from exc
        in_yaml = False
        data = {}
        for line in lines:
            stripped = line.strip()
            if not in_yaml and stripped in ("```yaml", "```yml"):
                in_yaml = True
                continue
            if in_yaml and stripped == "```":
                if not data:
                    return {"state": REPORT_INVALID, "status": None, "reason": f"{path.name} 第一个 YAML 状态块为空"}
                return {"state": REPORT_OK, "status": None, "reason": None, "data": data}
            if in_yaml:
                match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", stripped)
                if match:
                    key = match.group(1)
                    value = match.group(2).strip().strip("'\"")
                    data[key] = value
        if in_yaml:
            return {"state": REPORT_INVALID, "status": None, "reason": f"{path.name} 第一个 YAML 状态块未正常结束"}
        return {"state": REPORT_INVALID, "status": None, "reason": f"{path.name} 缺少第一个 YAML 状态块"}

    def _normalized_yaml_value(self, value):
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip().rstrip("/").replace("\\", "/")

    def _yaml_int(self, value, label, errors):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} 必须是整数")
            return None
        try:
            return int(value.strip().strip("'\""))
        except ValueError:
            errors.append(f"{label} 必须是整数")
            return None

    def _json_status(self, path):
        if not path.exists():
            return {"state": REPORT_MISSING, "status": None, "reason": f"缺少 {path.name}"}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SessionReportError(f"读取 JSON 报告失败：{path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SessionReportError(f"JSON 报告顶层必须是 object：{path}")
        status = data.get("status")
        if isinstance(status, str) and status.strip():
            return {"state": REPORT_OK, "status": status.strip(), "reason": None}
        return {"state": REPORT_INVALID, "status": None, "reason": f"{path.name} 缺少 status"}

    def _apply_report(self, path):
        if not path.exists():
            return {"state": REPORT_MISSING, "status": None, "reason": f"缺少 {path.name}", "workspace_validation": None}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SessionReportError(f"读取 JSON 报告失败：{path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SessionReportError(f"JSON 报告顶层必须是 object：{path}")
        errors = []
        status = data.get("status")
        if not isinstance(status, str) or not status.strip():
            errors.append(f"{path.name} 缺少 status")
            status = None
        else:
            status = status.strip()
        if data.get("session_id") != self.session_id:
            errors.append("apply_report.json session_id 与当前 session_id 不一致")
        validation = data.get("workspace_validation")
        if not isinstance(validation, dict):
            errors.append("apply_report.workspace_validation 必须是 object")
            validation = None
        elif status == "success":
            if validation.get("status") != "PASS":
                errors.append("apply_report.workspace_validation.status 必须为 PASS")
            if validation.get("failed_file_count") != 0:
                errors.append("apply_report.workspace_validation.failed_file_count 必须为 0")
            failures = validation.get("failures")
            if not isinstance(failures, list):
                errors.append("apply_report.workspace_validation.failures 必须是数组")
            elif failures:
                errors.append("apply_report.workspace_validation.failures 必须为空")
        if errors:
            return {"state": REPORT_INVALID, "status": status, "reason": "; ".join(errors), "workspace_validation": validation}
        return {"state": REPORT_OK, "status": status, "reason": None, "workspace_validation": validation}

    def _render_report(self, summary, report_files):
        lines = [
            "# Superlooper Session Report",
            "",
            "## Session",
            "",
            f"- session_id: {summary['session_id']}",
            f"- workspace_root: {summary['workspace_root']}",
            f"- current_phase: {summary['current_phase']}",
            f"- phase_status: {summary['phase_status']}",
            "",
            "## Inputs",
            "",
            f"- requirement_path: {summary['inputs']['requirement_path']}",
            f"- prd_path: {summary['inputs']['prd_path']}",
            f"- design_docs_path: {summary['inputs']['design_docs_path']}",
            f"- module_split_path: {summary['inputs']['module_split_path']}",
            f"- execution_manifest_path: {summary['inputs']['execution_manifest_path']}",
            "",
            "## Reports",
            "",
        ]
        for key in [
            "code_review_report",
            "merge_report",
            "conflict_report",
            "test_report",
            "apply_report",
            "apply_conflict_report",
            "requirement_alignment_report",
        ]:
            info = report_files[key]
            value = info["contract_path"] if info["exists"] else "missing"
            lines.append(f"- {key}: {self._display_path(value)}")
        validation = summary.get("workspace_validation") or {}
        lines.extend(
            [
                "",
                "## Workspace Validation",
                "",
                f"- status: {validation.get('status', 'missing')}",
                f"- checked_file_count: {validation.get('checked_file_count', 0)}",
                f"- matched_file_count: {validation.get('matched_file_count', 0)}",
                f"- failed_file_count: {validation.get('failed_file_count', 0)}",
                "",
                "## Conclusion",
                "",
                f"- result: {summary['result']}",
                f"- reason: {summary['reason']}",
                "",
            ]
        )
        return "\n".join(lines)

    def _contract_path(self, path):
        return str(path.relative_to(self.workspace_root)).replace("\\", "/")

    def _display_path(self, value):
        if not self.redact_paths or not isinstance(value, str) or not value.strip():
            return value
        normalized = value.replace("\\", "/")
        workspace = str(self.workspace_root).replace("\\", "/")
        if normalized == workspace:
            return "."
        try:
            candidate = Path(value)
        except (TypeError, ValueError):
            return value
        if candidate.is_absolute():
            try:
                relative = candidate.resolve().relative_to(self.workspace_root)
            except ValueError:
                return value
            relative_text = str(relative).replace("\\", "/")
            return relative_text or "."
        return value


def parse_args():
    parser = argparse.ArgumentParser(description="Build SUPERLOOPER session_report.md from runtime state and report files.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    parser.add_argument("--redact-paths", action="store_true", help="将报告中的 workspace_root 与工作区内绝对路径脱敏为相对路径。")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        builder = SessionReportBuilder(workspace_root=args.workspace_root, session_id=args.session_id, redact_paths=args.redact_paths)
        return builder.run()
    except (SessionReportError, SessionStateValidationError) as exc:
        print(f"生成 session_report 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
