import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SNAPSHOT_DIGEST = "sha256:f80ff197bdd6c1ddb1b5ddc2ccdf097c86af29980bd82e1440064489ade45f98"


class BuildSessionReportScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.task_id = "session_report"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")
        self.create_session()
        prd_path = self.workspace_root / ".superlooper" / "context" / self.task_id / "prd.md"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        prd_path.write_text(
            "# PRD\n\n"
            "### REQ-001：导出报表\n\n"
            "### AC-001：导出成功\n\n"
            "### DEC-001：采用同步导出\n\n"
            "### OPEN-001：大文件阈值按默认值处理\n",
            encoding="utf-8",
        )

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
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(self.requirement_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def state_path(self):
        return self.workspace_root / ".superlooper" / "state" / f"{self.task_id}.json"

    def reports_dir(self):
        return self.workspace_root / ".superlooper" / "reports" / self.task_id

    def write_state(
        self,
        current_phase,
        phase_status,
        last_error=None,
        requirement_alignment_passed=None,
    ):
        state = json.loads(self.state_path().read_text(encoding="utf-8"))
        state["current_phase"] = current_phase
        state["phase_status"] = phase_status
        state["last_error"] = last_error
        if requirement_alignment_passed is not None:
            state["requirement_alignment_passed"] = requirement_alignment_passed
        elif current_phase == "report" and phase_status == "passed":
            state["requirement_alignment_passed"] = True
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
            f"task_id: {self.task_id}\n"
            "code_review_status: PASS\n"
            "blocker_count: 0\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            "- report_export\n"
            f"report_path: .superlooper/reports/{self.task_id}/code_review_report.md\n"
            "```\n",
        )
        merged_file = self.workspace_root / ".superlooper" / "merged" / self.task_id / "src" / "app.txt"
        merged_file.parent.mkdir(parents=True, exist_ok=True)
        merged_file.write_bytes(b"hello\n")
        self.write_json_report(
            "merge_report.json",
            {
                "task_id": self.task_id,
                "status": "success",
                "snapshot_digest": SNAPSHOT_DIGEST,
            },
        )
        test_evidence = {
            "commands": [
                {
                    "command": "python -m unittest tests.test_report_export",
                    "exit_code": 0,
                    "result": "PASS",
                    "key_output": "1 test passed",
                }
            ],
            "requirement_coverage": [
                {"id": item_id, "status": "PASS", "evidence": f"verified {item_id}"}
                for item_id in ("REQ-001", "AC-001", "DEC-001", "OPEN-001")
            ],
        }
        self.write_markdown_report(
            "test_report.md",
            "```yaml\n"
            f"task_id: {self.task_id}\n"
            "test_status: PASS\n"
            f"tested_path: .superlooper/merged/{self.task_id}\n"
            f"merge_report_path: .superlooper/reports/{self.task_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.task_id}/test_report.md\n"
            "```\n"
            "```json\n"
            + json.dumps(test_evidence, ensure_ascii=False, indent=2)
            + "\n```\n",
        )
        self.write_json_report(
            "apply_report.json",
            {
                "task_id": self.task_id,
                "status": "success",
                "snapshot_digest": SNAPSHOT_DIGEST,
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

    def write_requirement_alignment_report(self, status="PASS", unmet=0, unchecked=0, evidence=True):
        evidence_block = ""
        if evidence:
            alignment_evidence = {
                "requirement_coverage": [
                    {
                        "id": item_id,
                        "type": item_id.split("-", 1)[0],
                        "status": "PASS",
                        "implementation_evidence": [f"implementation for {item_id}"],
                        "test_evidence": [f"test for {item_id}"],
                        "delivery_evidence": [f"delivery for {item_id}"],
                    }
                    for item_id in ("REQ-001", "AC-001", "DEC-001", "OPEN-001")
                ]
            }
            evidence_block = "```json\n" + json.dumps(alignment_evidence, ensure_ascii=False, indent=2) + "\n```\n"
        self.write_markdown_report(
            "requirement_alignment_report.md",
            "```yaml\n"
            f"task_id: {self.task_id}\n"
            f"requirement_alignment_status: {status}\n"
            f"unmet_requirement_count: {unmet}\n"
            f"unchecked_acceptance_count: {unchecked}\n"
            f"prd_path: .superlooper/context/{self.task_id}/prd.md\n"
            f"test_report_path: .superlooper/reports/{self.task_id}/test_report.md\n"
            f"apply_report_path: .superlooper/reports/{self.task_id}/apply_report.json\n"
            f"report_path: .superlooper/reports/{self.task_id}/requirement_alignment_report.md\n"
            "```\n"
            f"{evidence_block}",
        )

    def build_report(self):
        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
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
        self.assertIn(f"- snapshot_digest: {SNAPSHOT_DIGEST}", report)

    def test_build_session_report_blocks_merge_digest_tree_mismatch_without_writing_report(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()
        merged_file = self.workspace_root / ".superlooper" / "merged" / self.task_id / "src" / "app.txt"
        merged_file.write_text("changed\n", encoding="utf-8")

        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("snapshot_digest 与 merged tree 不一致", result.stderr)
        self.assertFalse((self.reports_dir() / "session_report.md").exists())

    def test_build_session_report_blocks_apply_digest_mismatch_without_writing_report(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()
        apply_path = self.reports_dir() / "apply_report.json"
        apply_report = json.loads(apply_path.read_text(encoding="utf-8"))
        apply_report["snapshot_digest"] = "sha256:" + "0" * 64
        apply_path.write_text(
            json.dumps(apply_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("apply_report.snapshot_digest 与 merge_report.snapshot_digest 不一致", result.stderr)
        self.assertFalse((self.reports_dir() / "session_report.md").exists())

    def test_build_session_report_blocks_invalid_digest_format(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()
        merge_path = self.reports_dir() / "merge_report.json"
        merge_report = json.loads(merge_path.read_text(encoding="utf-8"))
        merge_report["snapshot_digest"] = "sha256:ABC"
        merge_path.write_text(
            json.dumps(merge_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sha256:<64 lowercase hex>", result.stderr)
        self.assertFalse((self.reports_dir() / "session_report.md").exists())

    def test_build_session_report_rejects_pass_test_report_without_machine_evidence(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_markdown_report(
            "test_report.md",
            "```yaml\n"
            f"task_id: {self.task_id}\n"
            "test_status: PASS\n"
            f"tested_path: .superlooper/merged/{self.task_id}\n"
            f"merge_report_path: .superlooper/reports/{self.task_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.task_id}/test_report.md\n"
            "```\n",
        )
        self.write_requirement_alignment_report()

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("JSON 证据块", report)

    def test_build_session_report_rejects_alignment_without_machine_evidence(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report(evidence=False)

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("JSON 证据块", report)

    def test_build_session_report_rejects_passed_state_without_alignment_approval_flag(self):
        self.write_state(
            "report",
            "passed",
            requirement_alignment_passed=False,
        )
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("requirement_alignment_passed", report)

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
                "task_id": self.task_id,
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
        self.write_json_report("apply_report.json", {"task_id": self.task_id, "status": "success"})
        self.write_requirement_alignment_report()

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("apply_report.workspace_validation 必须是 object", report)

    def test_build_session_report_outputs_blocked_when_apply_conflict_report_exists(self):
        self.write_state("run", "blocked", "等待人工处理应用冲突")
        self.write_json_report("apply_conflict_report.json", {"task_id": self.task_id, "status": "conflict"})

        report = self.build_report()

        self.assertIn("- result: BLOCKED", report)
        self.assertIn("apply_conflict_report.json", report)

    def test_build_session_report_outputs_fail_when_code_review_or_test_fails(self):
        self.write_state("run", "running")
        self.write_markdown_report(
            "code_review_report.md",
            "```yaml\n"
            f"task_id: {self.task_id}\n"
            "code_review_status: FAIL\n"
            "blocker_count: 1\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            "- report_export\n"
            f"report_path: .superlooper/reports/{self.task_id}/code_review_report.md\n"
            "```\n",
        )
        self.write_json_report("merge_report.json", {"task_id": self.task_id, "status": "success"})
        self.write_markdown_report(
            "test_report.md",
            "```yaml\n"
            f"task_id: {self.task_id}\n"
            "test_status: FAIL\n"
            f"tested_path: .superlooper/merged/{self.task_id}\n"
            f"merge_report_path: .superlooper/reports/{self.task_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.task_id}/test_report.md\n"
            "```\n",
        )
        self.write_json_report(
            "apply_report.json",
            {
                "task_id": self.task_id,
                "status": "success",
                "snapshot_digest": SNAPSHOT_DIGEST,
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

    def test_build_session_report_accepts_legacy_reports_without_rewriting(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()
        markdown_paths = [
            self.reports_dir() / "code_review_report.md",
            self.reports_dir() / "test_report.md",
            self.reports_dir() / "requirement_alignment_report.md",
        ]
        for path in markdown_paths:
            path.write_text(path.read_text(encoding="utf-8").replace("task_id:", "session_id:"), encoding="utf-8")
        json_paths = [
            self.reports_dir() / "merge_report.json",
            self.reports_dir() / "apply_report.json",
        ]
        for path in json_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["session_id"] = payload.pop("task_id")
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.task_id,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = (self.reports_dir() / "session_report.md").read_text(encoding="utf-8")
        self.assertIn(f"- task_id: {self.task_id}", report)
        self.assertNotIn("- session_id:", report)
        self.assertIn("- result: PASS", report)
        for path in markdown_paths:
            persisted = path.read_text(encoding="utf-8")
            self.assertIn("session_id:", persisted)
            self.assertNotIn("task_id:", persisted)
        for path in json_paths:
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("session_id", persisted)
            self.assertNotIn("task_id", persisted)

    def test_build_session_report_rejects_dual_json_report_identity(self):
        self.write_state("report", "passed")
        self.write_all_pass_reports()
        self.write_requirement_alignment_report()
        merge_report_path = self.reports_dir() / "merge_report.json"
        merge_report = json.loads(merge_report_path.read_text(encoding="utf-8"))
        merge_report["session_id"] = self.task_id
        merge_report_path.write_text(json.dumps(merge_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        report = self.build_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("不能同时包含 task_id 和 legacy session_id", report)


if __name__ == "__main__":
    unittest.main()
