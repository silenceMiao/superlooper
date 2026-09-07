import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BuildSessionReportScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "session_report"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")
        self.create_session()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, script_name, *args):
        return subprocess.run(
            [sys.executable, str(self.repo_root / "scripts" / script_name), *args],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def create_session(self):
        result = self.run_script(
            "create_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--requirement-path",
            str(self.requirement_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def state_path(self):
        return self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"

    def reports_dir(self):
        return self.workspace_root / ".superlooper" / "reports" / self.session_id

    def write_state(self, current_phase, phase_status, last_error=None):
        state = json.loads(self.state_path().read_text(encoding="utf-8"))
        state["current_phase"] = current_phase
        state["phase_status"] = phase_status
        state["last_error"] = last_error
        self.state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_json_report(self, filename, payload):
        path = self.reports_dir() / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_markdown_report(self, filename, content):
        path = self.reports_dir() / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_all_pass_reports(self):
        self.write_markdown_report(
            "code_review_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "code_review_status: PASS\n"
            "blocker_count: 0\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            "- report_export\n"
            f"report_path: .superlooper/reports/{self.session_id}/code_review_report.md\n"
            "```\n",
        )
        self.write_json_report("merge_report.json", {"session_id": self.session_id, "status": "success"})
        self.write_markdown_report(
            "test_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "test_status: PASS\n"
            f"tested_path: .superlooper/merged/{self.session_id}\n"
            f"merge_report_path: .superlooper/reports/{self.session_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.session_id}/test_report.md\n"
            "```\n",
        )
        self.write_json_report(
            "apply_report.json",
            {
                "session_id": self.session_id,
                "status": "success",
                "workspace_validation": {
                    "status": "PASS",
                    "checked_file_count": 2,
                    "matched_file_count": 2,
                    "failed_file_count": 0,
                    "checked_files": [],
                    "failures": [],
                },
            },
        )

    def write_requirement_alignment_report(self, status="PASS", unmet=0, unchecked=0):
        self.write_markdown_report(
            "requirement_alignment_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            f"requirement_alignment_status: {status}\n"
            f"unmet_requirement_count: {unmet}\n"
            f"unchecked_acceptance_count: {unchecked}\n"
            f"prd_path: .superlooper/context/{self.session_id}/prd.md\n"
            f"test_report_path: .superlooper/reports/{self.session_id}/test_report.md\n"
            f"apply_report_path: .superlooper/reports/{self.session_id}/apply_report.json\n"
            f"report_path: .superlooper/reports/{self.session_id}/requirement_alignment_report.md\n"
            "```\n",
        )

    def build_report(self):
        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.reports_dir() / "session_report.md").read_text(encoding="utf-8")

    def test_build_session_report_outputs_pass_when_apply_and_upstream_reports_all_pass(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()

        report = self.build_report()

        self.assertIn("- result: PASS", report)
        self.assertIn("code_review/test/merge/apply/requirement_alignment 报告全部通过", report)

    def test_build_session_report_requires_requirement_alignment_when_state_passed(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("requirement_alignment_report.md", report)

    def test_build_session_report_passes_with_requirement_alignment_report(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()

        report = self.build_report()

        self.assertIn("- result: PASS", report)

    def test_build_session_report_outputs_workspace_validation_summary(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()

        report = self.build_report()

        self.assertIn("## Workspace Validation", report)
        self.assertIn("- status: PASS", report)
        self.assertIn("- checked_file_count: 2", report)
        self.assertIn("- failed_file_count: 0", report)

    def test_build_session_report_fails_when_workspace_validation_fails(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_json_report(
            "apply_report.json",
            {
                "session_id": self.session_id,
                "status": "failed",
                "workspace_validation": {
                    "status": "FAIL",
                    "checked_file_count": 1,
                    "matched_file_count": 0,
                    "failed_file_count": 1,
                    "checked_files": [],
                    "failures": [{"path": "src/App.java", "reason": "content_mismatch"}],
                },
            },
        )
        self.write_requirement_alignment_report()

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("apply_report.json 状态不是 success", report)
        self.assertIn("- status: FAIL", report)
        self.assertIn("- failed_file_count: 1", report)

    def test_build_session_report_fails_without_workspace_validation(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_json_report("apply_report.json", {"session_id": self.session_id, "status": "success"})
        self.write_requirement_alignment_report()

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("apply_report.workspace_validation 必须是 object", report)

    def test_build_session_report_outputs_blocked_when_apply_conflict_report_exists(self):
        self.write_state("run", "blocked", "等待人工处理应用冲突")
        self.write_json_report("apply_conflict_report.json", {"session_id": self.session_id, "status": "conflict"})

        report = self.build_report()

        self.assertIn("- result: BLOCKED", report)
        self.assertIn("apply_conflict_report.json", report)

    def test_build_session_report_outputs_fail_when_code_review_or_test_fails(self):
        self.write_state("run", "running")
        self.write_markdown_report(
            "code_review_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "code_review_status: FAIL\n"
            "blocker_count: 1\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            "- report_export\n"
            f"report_path: .superlooper/reports/{self.session_id}/code_review_report.md\n"
            "```\n",
        )
        self.write_json_report("merge_report.json", {"session_id": self.session_id, "status": "success"})
        self.write_markdown_report(
            "test_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "test_status: FAIL\n"
            f"tested_path: .superlooper/merged/{self.session_id}\n"
            f"merge_report_path: .superlooper/reports/{self.session_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.session_id}/test_report.md\n"
            "```\n",
        )
        self.write_json_report(
            "apply_report.json",
            {
                "session_id": self.session_id,
                "status": "success",
                "workspace_validation": {
                    "status": "PASS",
                    "checked_file_count": 2,
                    "matched_file_count": 2,
                    "failed_file_count": 0,
                    "checked_files": [],
                    "failures": [],
                },
            },
        )

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("code_review_report.md 指示 FAIL", report)

    def test_build_session_report_outputs_waiting_review_when_state_is_running(self):
        self.write_state("run", "running")

        report = self.build_report()

        self.assertIn("- result: WAITING_REVIEW", report)
        self.assertIn("等待执行完成", report)


if __name__ == "__main__":
    unittest.main()
