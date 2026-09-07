import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SessionStateScriptsTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "demo-session"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, script_name, *args):
        script_path = self.repo_root / "scripts" / script_name
        command = [sys.executable, str(script_path), *args]
        return subprocess.run(
            command,
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
        return self.read_state()

    def update_session(self, *extra_args):
        result = self.run_script(
            "update_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            *extra_args,
        )
        return result

    def read_state(self):
        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"
        return json.loads(state_path.read_text(encoding="utf-8"))

    def write_state(self, state):
        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_report(self, filename, content):
        report_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / filename
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(content, encoding="utf-8")
        return report_path

    def write_apply_report(self):
        self.write_report(
            "apply_report.json",
            json.dumps(
                {
                    "session_id": self.session_id,
                    "status": "success",
                    "workspace_validation": {
                        "status": "PASS",
                        "checked_file_count": 1,
                        "matched_file_count": 1,
                        "failed_file_count": 0,
                        "checked_files": [],
                        "failures": [],
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )

    def write_valid_gate_reports(self):
        self.write_report(
            "code_review_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "code_review_status: PASS\n"
            "blocker_count: 0\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            "report_path: .superlooper/reports/demo-session/code_review_report.md\n"
            "```\n",
        )
        self.write_report(
            "test_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "test_status: PASS\n"
            "tested_path: .superlooper/merged/demo-session\n"
            "merge_report_path: .superlooper/reports/demo-session/merge_report.json\n"
            "report_path: .superlooper/reports/demo-session/test_report.md\n"
            "```\n",
        )
        self.write_report(
            "merge_report.json",
            json.dumps({"session_id": self.session_id, "status": "success"}, ensure_ascii=False, indent=2) + "\n",
        )
        self.write_apply_report()
        self.write_requirement_alignment_report()

    def write_requirement_alignment_report(self, status="PASS", unmet=0, unchecked=0):
        self.write_report(
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

    def write_change_impact_report(self, rollback_target_phase="run"):
        self.write_report(
            "change_impact_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "change_impact_status: PASS\n"
            f"rollback_target_phase: {rollback_target_phase}\n"
            "requires_reinitialization: false\n"
            "local_rerun_allowed: true\n"
            "manual_approval_required: true\n"
            "affected_artifacts:\n"
            f"  - .superlooper/reports/{self.session_id}/test_report.md\n"
            "affected_modules:\n"
            f"report_path: .superlooper/reports/{self.session_id}/change_impact_report.md\n"
            "```\n",
        )

    def write_upstream_alignment(self, status="PASS", mismatch_count=0, loop_required="false", loop_target_phase="design", blocking_decisions=None):
        decisions = blocking_decisions or []
        lines = [
            "```yaml",
            f"session_id: {self.session_id}",
            f"upstream_alignment_status: {status}",
            f"mismatch_count: {mismatch_count}",
            f"loop_required: {loop_required}",
            f"loop_target_phase: {loop_target_phase}",
            "blocking_decisions:",
        ]
        lines.extend(f"  - {item}" for item in decisions)
        lines.append(f"report_path: .superlooper/reports/{self.session_id}/upstream_alignment.md")
        lines.append("```")
        self.write_report("upstream_alignment.md", "\n".join(lines) + "\n")

    def write_execution_summary(self, status="READY_FOR_APPROVAL"):
        self.write_report(
            "execution_summary.md",
            "```yaml\n"
            f"execution_summary_status: {status}\n"
            f"session_id: {self.session_id}\n"
            "workflow_mode: standard\n"
            "project_category: springboot\n"
            "project_version: springboot-3.x\n"
            "module_count: 1\n"
            "target_file_count: 1\n"
            "risk_count: 0\n"
            "blocking_decisions:\n"
            "upstream_alignment_status: PASS\n"
            "module_split_validated: true\n"
            "execution_manifest_validated: true\n"
            f"report_path: .superlooper/reports/{self.session_id}/execution_summary.md\n"
            "```\n",
        )

    def build_session_report(self):
        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.workspace_root / ".superlooper" / "reports" / self.session_id / "session_report.md").read_text(encoding="utf-8")

    def test_create_session_writes_initial_state(self):
        state = self.create_session()
        self.assertEqual(state["session_id"], self.session_id)
        self.assertEqual(state["workspace_root"], str(self.workspace_root.resolve()))
        self.assertEqual(state["requirement_path"], str(self.requirement_path.resolve()))
        self.assertEqual(state["current_phase"], "prd")
        self.assertEqual(state["phase_status"], "pending")
        self.assertEqual(state["generated_files"], [])
        self.assertEqual(state["reports"], [])
        self.assertEqual(state["script_events"], [])
        self.assertEqual(state["last_command"], "create_session")
        self.assertIsNone(state["last_error"])
        self.assertEqual(state["next_actions"], ["运行 /spl:prd 进入需求分析阶段"])
        self.assertEqual(state["project_mode"], "greenfield")
        self.assertEqual(state["workflow_mode"], "standard")
        self.assertIsNone(state["project_category"])
        self.assertIsNone(state["project_version"])
        self.assertIsNone(state["project_root"])
        self.assertFalse(state["project_initialized"])
        self.assertIsNone(state["initialization_report"])
        self.assertEqual(state["execution_summary_status"], "NOT_STARTED")
        self.assertIsNone(state["execution_summary_report"])
        self.assertEqual(state["loop_policy"], {"max_auto_loop_per_phase": 2})
        self.assertEqual(
            state["loop_state"],
            {
                "current_loop_target_phase": None,
                "loop_count_by_phase": {},
                "last_alignment_status": None,
                "last_feedback_report": None,
            },
        )
        self.assertIsNone(state["requirement_alignment_report"])
        self.assertFalse(state["requirement_alignment_passed"])
        self.assertEqual(state["prd_revision"], 0)
        self.assertEqual(state["ui_revision"], 0)
        self.assertEqual(state["ui_status"], "NOT_STARTED")
        self.assertIsNone(state["ui_output_dir"])
        self.assertFalse(state["ui_artifacts_validated"])
        self.assertEqual(state["design_revision"], 0)
        self.assertEqual(state["change_request_count"], 0)
        self.assertIsNone(state["active_feedback_report"])
        self.assertIsNone(state["change_impact_report"])
        self.assertEqual(state["invalidated_artifacts"], [])
        self.assertIsNone(state["rollback_target_phase"])
        self.assertIsNone(state["last_user_input_text"])
        self.assertIsNone(state["last_user_canonical_action"])
        self.assertIsNone(state["pending_user_choice"])

    def test_create_session_accepts_brownfield_selective_project_mode(self):
        result = self.run_script(
            "create_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--requirement-path",
            str(self.requirement_path),
            "--project-mode",
            "brownfield-selective",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["project_mode"], "brownfield-selective")

    def test_update_session_accepts_brownfield_selective_project_mode(self):
        self.create_session()
        result = self.update_session(
            "--current-phase",
            "design",
            "--phase-status",
            "running",
            "--last-command",
            "classify-project-mode",
            "--project-mode",
            "brownfield-selective",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["project_mode"], "brownfield-selective")

    def test_create_session_rejects_empty_requirement_path(self):
        result = self.run_script(
            "create_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--requirement-path",
            "",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path", result.stderr)

    def test_update_session_rejects_undeclared_loop_policy_field_from_schema(self):
        self.create_session()
        state = self.read_state()
        state["loop_policy"]["unexpected"] = True
        self.write_state(state)

        result = self.update_session(
            "--current-phase",
            "prd",
            "--phase-status",
            "pending",
            "--last-command",
            "schema-extra-loop-policy",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明字段", result.stderr)

    def test_update_session_rejects_missing_loop_state_field_from_schema(self):
        self.create_session()
        state = self.read_state()
        del state["loop_state"]["last_feedback_report"]
        self.write_state(state)

        result = self.update_session(
            "--current-phase",
            "prd",
            "--phase-status",
            "pending",
            "--last-command",
            "schema-missing-loop-state-field",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少必填字段", result.stderr)

    def test_update_session_changes_phase_and_status(self):
        self.create_session()
        result = self.update_session(
            "--current-phase",
            "design",
            "--phase-status",
            "running",
            "--last-command",
            "/spl:design demo-session",
            "--generated-file",
            ".superlooper/context/demo-session/design/architecture.md",
            "--next-action",
            "等待设计输出完成",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["current_phase"], "design")
        self.assertEqual(state["phase_status"], "running")
        self.assertEqual(state["last_command"], "/spl:design demo-session")
        self.assertEqual(state["generated_files"], [".superlooper/context/demo-session/design/architecture.md"])
        self.assertEqual(state["next_actions"], ["等待设计输出完成"])
        self.assertEqual(state["workspace_root"], str(self.workspace_root.resolve()))
        self.assertEqual(state["requirement_path"], str(self.requirement_path.resolve()))

    def test_update_session_records_initialization_and_alignment_fields(self):
        self.create_session()
        result = self.update_session(
            "--current-phase",
            "initialization",
            "--phase-status",
            "waiting_review",
            "--last-command",
            "选择 springboot 初始化",
            "--project-category",
            "springboot",
            "--project-version",
            "springboot-3.x",
            "--project-root",
            ".",
            "--project-initialized",
            "true",
            "--initialization-report",
            ".superlooper/reports/demo-session/initialization_report.json",
            "--workflow-mode",
            "strict_review",
            "--execution-summary-status",
            "READY_FOR_APPROVAL",
            "--execution-summary-report",
            ".superlooper/reports/demo-session/execution_summary.md",
            "--loop-policy-json",
            '{"max_auto_loop_per_phase": 1}',
            "--loop-state-json",
            '{"current_loop_target_phase":"design","loop_count_by_phase":{"design":1},"last_alignment_status":"FAIL","last_feedback_report":".superlooper/reports/demo-session/design_feedback.md"}',
            "--requirement-alignment-report",
            ".superlooper/reports/demo-session/requirement_alignment_report.md",
            "--requirement-alignment-passed",
            "true",
            "--next-action",
            "生成 module-split.json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["current_phase"], "initialization")
        self.assertEqual(state["project_category"], "springboot")
        self.assertEqual(state["project_version"], "springboot-3.x")
        self.assertEqual(state["project_root"], ".")
        self.assertTrue(state["project_initialized"])
        self.assertEqual(state["initialization_report"], ".superlooper/reports/demo-session/initialization_report.json")
        self.assertEqual(state["workflow_mode"], "strict_review")
        self.assertEqual(state["execution_summary_status"], "READY_FOR_APPROVAL")
        self.assertEqual(state["execution_summary_report"], ".superlooper/reports/demo-session/execution_summary.md")
        self.assertEqual(state["loop_policy"], {"max_auto_loop_per_phase": 1})
        self.assertEqual(state["loop_state"]["current_loop_target_phase"], "design")
        self.assertEqual(state["loop_state"]["loop_count_by_phase"], {"design": 1})
        self.assertEqual(state["loop_state"]["last_alignment_status"], "FAIL")
        self.assertEqual(state["requirement_alignment_report"], ".superlooper/reports/demo-session/requirement_alignment_report.md")
        self.assertTrue(state["requirement_alignment_passed"])

    def test_update_session_records_ui_fields(self):
        self.create_session()
        result = self.update_session(
            "--current-phase",
            "ui_design",
            "--phase-status",
            "waiting_review",
            "--last-command",
            "/spl:ui demo-session",
            "--ui-revision",
            "1",
            "--ui-status",
            "READY_FOR_REVIEW",
            "--ui-output-dir",
            ".superlooper/context/demo-session/ui/",
            "--ui-artifacts-validated",
            "true",
            "--rollback-target-phase",
            "ui_design",
            "--next-action",
            "审核 UI 设计和 preview.html",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["current_phase"], "ui_design")
        self.assertEqual(state["ui_revision"], 1)
        self.assertEqual(state["ui_status"], "READY_FOR_REVIEW")
        self.assertEqual(state["ui_output_dir"], ".superlooper/context/demo-session/ui/")
        self.assertTrue(state["ui_artifacts_validated"])
        self.assertEqual(state["rollback_target_phase"], "ui_design")

    def test_update_session_records_feedback_and_impact_fields(self):
        self.create_session()
        result = self.update_session(
            "--current-phase",
            "run",
            "--phase-status",
            "waiting_review",
            "--last-command",
            "需求变更，执行影响分析",
            "--prd-revision",
            "2",
            "--design-revision",
            "3",
            "--change-request-count",
            "1",
            "--active-feedback-report",
            ".superlooper/reports/demo-session/change_feedback.md",
            "--change-impact-report",
            ".superlooper/reports/demo-session/change_impact_report.md",
            "--invalidated-artifact",
            ".superlooper/manifests/demo-session/execution_manifest.json",
            "--invalidated-artifact",
            ".superlooper/outputs/demo-session/report_export/artifact_manifest.json",
            "--rollback-target-phase",
            "run",
            "--last-user-input-text",
            "设计要改，补充导出逻辑",
            "--last-user-canonical-action",
            "change_impact_requested",
            "--pending-user-choice-json",
            "null",
            "--next-action",
            "审核 change_impact_report.md",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["prd_revision"], 2)
        self.assertEqual(state["design_revision"], 3)
        self.assertEqual(state["change_request_count"], 1)
        self.assertEqual(state["active_feedback_report"], ".superlooper/reports/demo-session/change_feedback.md")
        self.assertEqual(state["change_impact_report"], ".superlooper/reports/demo-session/change_impact_report.md")
        self.assertEqual(
            state["invalidated_artifacts"],
            [
                ".superlooper/manifests/demo-session/execution_manifest.json",
                ".superlooper/outputs/demo-session/report_export/artifact_manifest.json",
            ],
        )
        self.assertEqual(state["rollback_target_phase"], "run")
        self.assertEqual(state["last_user_input_text"], "设计要改，补充导出逻辑")
        self.assertEqual(state["last_user_canonical_action"], "change_impact_requested")
        self.assertIsNone(state["pending_user_choice"])

    def test_update_session_records_script_event(self):
        self.create_session()
        result = self.update_session(
            "--current-phase",
            "run",
            "--phase-status",
            "running",
            "--last-command",
            "generate_execution_manifest",
            "--record-script-event",
            "generate_execution_manifest:completed:idem-001",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["script_events"][-1]["script"], "generate_execution_manifest")
        self.assertEqual(state["script_events"][-1]["status"], "completed")
        self.assertEqual(state["script_events"][-1]["idempotency_key"], "idem-001")

    def test_update_session_script_event_is_idempotent(self):
        self.create_session()
        for _ in range(2):
            result = self.update_session(
                "--current-phase",
                "run",
                "--phase-status",
                "running",
                "--last-command",
                "merge_artifacts",
                "--record-script-event",
                "merge_artifacts:completed:merge-001",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        matching = [event for event in state["script_events"] if event["idempotency_key"] == "merge-001"]
        self.assertEqual(len(matching), 1)

    def test_update_session_deduplicates_generated_files(self):
        self.create_session()
        first = ".superlooper/context/demo-session/prd.md"
        second = ".superlooper/context/demo-session/design/architecture.md"
        result = self.update_session(
            "--current-phase",
            "design",
            "--phase-status",
            "running",
            "--last-command",
            "step-1",
            "--generated-file",
            first,
            "--generated-file",
            first,
            "--generated-file",
            second,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.update_session(
            "--current-phase",
            "design",
            "--phase-status",
            "waiting_review",
            "--last-command",
            "step-2",
            "--generated-file",
            second,
            "--generated-file",
            first,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["generated_files"], [first, second])

    def test_update_session_deduplicates_reports(self):
        self.create_session()
        first = ".superlooper/reports/demo-session/code_review_report.md"
        second = ".superlooper/reports/demo-session/test_report.md"
        result = self.update_session(
            "--current-phase",
            "run",
            "--phase-status",
            "running",
            "--last-command",
            "step-1",
            "--report",
            first,
            "--report",
            first,
            "--report",
            second,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.update_session(
            "--current-phase",
            "report",
            "--phase-status",
            "passed",
            "--last-command",
            "step-2",
            "--report",
            second,
            "--report",
            first,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.read_state()
        self.assertEqual(state["reports"], [first, second])

    def test_update_session_rejects_invalid_session_id(self):
        self.create_session()
        script_path = self.repo_root / "scripts" / "update_session.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                "..",
                "--current-phase",
                "prd",
                "--phase-status",
                "pending",
                "--last-command",
                "bad",
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("session_id", result.stderr)

    def test_update_session_rejects_invalid_phase_and_status(self):
        self.create_session()
        bad_phase = self.update_session(
            "--current-phase",
            "deploy",
            "--phase-status",
            "pending",
            "--last-command",
            "bad-phase",
        )
        self.assertNotEqual(bad_phase.returncode, 0)
        self.assertIn("current_phase", bad_phase.stderr)

        bad_status = self.update_session(
            "--current-phase",
            "prd",
            "--phase-status",
            "done",
            "--last-command",
            "bad-status",
        )
        self.assertNotEqual(bad_status.returncode, 0)
        self.assertIn("phase_status", bad_status.stderr)

    def test_build_session_report_requires_all_upstream_pass_reports(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "report"
        state["phase_status"] = "passed"
        self.write_state(state)
        self.write_apply_report()

        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = (self.workspace_root / ".superlooper" / "reports" / self.session_id / "session_report.md").read_text(encoding="utf-8")
        self.assertIn("- result: FAIL", report)
        self.assertIn("code_review_report.md", report)

    def test_build_session_report_treats_missing_yaml_field_as_failure(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "report"
        state["phase_status"] = "passed"
        self.write_state(state)
        self.write_report(
            "code_review_report.md",
            "```yaml\nsession_id: demo-session\n```\n",
        )
        self.write_report(
            "test_report.md",
            "```yaml\nsession_id: demo-session\ntest_status: PASS\ntested_path: .superlooper/merged/demo-session\nmerge_report_path: .superlooper/reports/demo-session/merge_report.json\nreport_path: .superlooper/reports/demo-session/test_report.md\n```\n",
        )
        self.write_report(
            "merge_report.json",
            json.dumps({"session_id": self.session_id, "status": "success"}, ensure_ascii=False, indent=2) + "\n",
        )
        self.write_apply_report()

        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = (self.workspace_root / ".superlooper" / "reports" / self.session_id / "session_report.md").read_text(encoding="utf-8")
        self.assertIn("- result: FAIL", report)
        self.assertIn("code_review_status", report)

    def test_build_session_report_rejects_unclosed_yaml_status_block(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "report"
        state["phase_status"] = "passed"
        self.write_state(state)
        self.write_valid_gate_reports()
        self.write_report(
            "code_review_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "code_review_status: PASS\n"
            "blocker_count: 0\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            "report_path: .superlooper/reports/demo-session/code_review_report.md\n",
        )

        report = self.build_session_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("未正常结束", report)

    def test_build_session_report_requires_code_review_gate_fields(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "report"
        state["phase_status"] = "passed"
        self.write_state(state)
        self.write_valid_gate_reports()
        self.write_report(
            "code_review_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "code_review_status: PASS\n"
            "reviewed_modules:\n"
            "```\n",
        )

        report = self.build_session_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("blocker_count", report)
        self.assertIn("blocking_major_count", report)
        self.assertIn("report_path", report)

    def test_build_session_report_requires_test_gate_fields(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "report"
        state["phase_status"] = "passed"
        self.write_state(state)
        self.write_valid_gate_reports()
        self.write_report(
            "test_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "test_status: PASS\n"
            "```\n",
        )

        report = self.build_session_report()

        self.assertIn("- result: FAIL", report)
        self.assertIn("tested_path", report)
        self.assertIn("merge_report_path", report)
        self.assertIn("report_path", report)

    def test_build_session_report_accepts_complete_gate_reports(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "report"
        state["phase_status"] = "passed"
        self.write_state(state)
        self.write_valid_gate_reports()

        report = self.build_session_report()

        self.assertIn("- result: PASS", report)
        self.assertIn("code_review/test/merge/apply/requirement_alignment 报告全部通过", report)

    def test_resume_session_rejects_empty_requirement_path_for_prd_pending(self):
        self.create_session()
        state = self.read_state()
        state["requirement_path"] = ""
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path", result.stderr)

    def test_status_session_prints_available_sessions_when_state_missing_or_broken(self):
        self.create_session()
        missing = self.run_script(
            "status_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            "missing-session",
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("available_sessions:", missing.stdout)
        self.assertIn(f"- {self.session_id}", missing.stdout)

        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"
        state_path.write_text("{broken json", encoding="utf-8")
        broken = self.run_script(
            "status_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )
        self.assertNotEqual(broken.returncode, 0)
        self.assertIn("available_sessions:", broken.stdout)
        self.assertIn(f"- {self.session_id}", broken.stdout)

    def test_update_session_rejects_tampered_workspace_root_and_requirement_path(self):
        self.create_session()
        state = self.read_state()
        state["workspace_root"] = str((self.workspace_root / "other-root").resolve())
        self.write_state(state)

        result = self.update_session(
            "--current-phase",
            "prd",
            "--phase-status",
            "pending",
            "--last-command",
            "tampered-root",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace_root", result.stderr)

        state = self.read_state()
        state["workspace_root"] = str(self.workspace_root.resolve())
        state["requirement_path"] = ""
        self.write_state(state)
        result = self.update_session(
            "--current-phase",
            "prd",
            "--phase-status",
            "pending",
            "--last-command",
            "tampered-requirement",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path", result.stderr)

    def test_resume_session_returns_expected_next_step_for_each_state(self):
        self.create_session()
        report_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / "session_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# report\n", encoding="utf-8")

        cases = [
            (
                {"current_phase": "prd", "phase_status": "pending", "next_actions": ["ignored"], "last_error": None},
                "next_step: /spl:prd",
            ),
            (
                {"current_phase": "prd", "phase_status": "waiting_review", "next_actions": ["ignored"], "last_error": None},
                "next_step: 等待用户审核 PRD；通过回复 通过，进入 UI 设计；未通过回复 PRD未通过，按反馈重新分析：<反馈内容>",
            ),
            (
                {"current_phase": "ui_design", "phase_status": "pending", "next_actions": ["ignored"], "last_error": None},
                "next_step: /spl:ui demo-session",
            ),
            (
                {"current_phase": "ui_design", "phase_status": "running", "next_actions": ["ignored"], "last_error": None},
                "next_step: 等待 UI 设计阶段输出完成。",
            ),
            (
                {"current_phase": "ui_design", "phase_status": "waiting_review", "next_actions": ["ignored"], "last_error": None},
                "next_step: 等待用户审核 UI 设计和 preview.html；通过回复 UI设计通过，进入系统设计；未通过回复 UI设计未通过，按反馈重新设计：<反馈内容>；需求变化回复 需求变更，返回 PRD 修订：<反馈内容>",
            ),
            (
                {"current_phase": "ui_design", "phase_status": "failed", "next_actions": ["ignored"], "last_error": None},
                "next_step: 修复失败原因后重试；建议动作：ignored",
            ),
            (
                {"current_phase": "design", "phase_status": "pending", "next_actions": ["ignored"], "last_error": None},
                "next_step: /spl:design demo-session",
            ),
            (
                {"current_phase": "design", "phase_status": "waiting_review", "next_actions": ["ignored"], "last_error": None},
                "next_step: 等待用户审核设计；通过回复 继续任务 或 生成执行清单；未通过回复 设计未通过，按反馈重新设计：<反馈内容>；初始化后变更回复 需求变更，执行影响分析：<反馈内容>",
            ),
            (
                {"current_phase": "initialization", "phase_status": "waiting_review", "project_category": None, "project_version": None, "project_initialized": False, "next_actions": ["ignored"], "last_error": None},
                "next_step: 请选择初始化项目分类：java/go/springboot/pom/lua",
            ),
            (
                {"current_phase": "initialization", "phase_status": "waiting_review", "project_category": "springboot", "project_version": None, "project_initialized": False, "next_actions": ["ignored"], "last_error": None},
                "next_step: 请选择 springboot 的初始化版本",
            ),
            (
                {"current_phase": "initialization", "phase_status": "waiting_review", "project_category": "springboot", "project_version": "springboot-3.x", "project_initialized": False, "next_actions": ["ignored"], "last_error": None},
                "next_step: 运行初始化脚本完成项目结构初始化",
            ),
            (
                {"current_phase": "run", "phase_status": "pending", "next_actions": ["ignored"], "last_error": None},
                "next_step: /spl:run demo-session",
            ),
            (
                {"current_phase": "run", "phase_status": "waiting_review", "next_actions": ["ignored"], "last_error": None},
                "next_step: 等待用户确认执行清单预览；审核通过回复 执行 或 开始并行开发；变更回复 需求变更，执行影响分析：<反馈内容>",
            ),
            (
                {"current_phase": "run", "phase_status": "running", "next_actions": ["ignored"], "last_error": None},
                "next_step: 等待执行完成或检查报告；若代码审查失败，回复 代码审查未通过，返回修正；若测试失败，回复 测试未通过，返回修正；若需求、UI 或设计变更，回复 需求变更，执行影响分析：<反馈内容>",
            ),
            (
                {"current_phase": "requirement_alignment", "phase_status": "waiting_review", "next_actions": ["ignored"], "last_error": None},
                "next_step: 等待用户审核 requirement_alignment_report.md；通过回复 需求校对通过，完成交付；未通过回复 需求校对未通过，返回修正：<反馈内容>",
            ),
            (
                {"current_phase": "report", "phase_status": "passed", "next_actions": ["ignored"], "last_error": None},
                f"next_step: {report_path}",
            ),
            (
                {"current_phase": "design", "phase_status": "failed", "next_actions": ["重新运行设计"], "last_error": "schema invalid"},
                "next_step: 修复失败原因后重试；建议动作：重新运行设计",
            ),
            (
                {"current_phase": "prd", "phase_status": "blocked", "next_actions": ["确认 DEC-001"], "last_error": "等待业务决策"},
                "manual_action: 确认 DEC-001",
            ),
        ]

        for updates, expected in cases:
            with self.subTest(updates=updates):
                state = self.read_state()
                state.update(updates)
                self.write_state(state)
                result = self.run_script(
                    "resume_session.py",
                    "--workspace-root",
                    str(self.workspace_root),
                    "--session-id",
                    self.session_id,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)

    def test_normalize_prd_feedback_text_to_revision_action(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "prd"
        state["phase_status"] = "waiting_review"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "这个 PRD 不对，补充导出需求",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "prd_revision_requested")
        self.assertFalse(normalized["requires_choice"])

    def test_normalize_prd_blocked_decision_confirmation(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "prd"
        state["phase_status"] = "blocked"
        state["last_error"] = "等待业务决策"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "已确认，重新生成 PRD",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "prd_decisions_confirmed")
        self.assertFalse(normalized["requires_choice"])

    def test_normalize_design_feedback_text_to_revision_action(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "design"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = False
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "设计不符合，重新设计接口",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "design_revision_requested")

    def test_normalize_ui_feedback_text_to_revision_action(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "这个 UI 预览不符合要求，导航和搜索要调整",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "ui_revision_requested")

    def test_normalize_ui_approval_text_to_design_action(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "UI 设计通过，进入系统设计",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "approve_ui_and_proceed")

    def test_normalize_requirement_alignment_revision_requested(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "requirement_alignment"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求校对未通过，返回修正，导出验收没满足",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "requirement_alignment_revision_requested")
        self.assertFalse(normalized["requires_choice"])

    def test_normalize_initialized_design_feedback_to_impact_action(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "design"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "设计要改",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "change_impact_requested")

    def test_normalize_initialization_category_choice(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "initialization"
        state["phase_status"] = "waiting_review"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "springboot",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "select_project_category")
        self.assertFalse(normalized["requires_choice"])

    def test_normalize_initialization_version_choice(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "initialization"
        state["phase_status"] = "waiting_review"
        state["project_category"] = "springboot"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "springboot-3.x",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "select_project_version")
        self.assertFalse(normalized["requires_choice"])

    def test_normalize_initialization_category_alias_choice(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "initialization"
        state["phase_status"] = "waiting_review"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "Maven",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "select_project_category")
        self.assertFalse(normalized["requires_choice"])

    def test_normalize_initialization_version_alias_choice(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "initialization"
        state["phase_status"] = "waiting_review"
        state["project_category"] = "springboot"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "Spring Boot 3",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "select_project_version")
        self.assertFalse(normalized["requires_choice"])

    def test_normalize_initialization_rejects_wrong_category_version(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "initialization"
        state["phase_status"] = "waiting_review"
        state["project_category"] = "springboot"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "go-1.25",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "choose_from_options")
        self.assertTrue(normalized["requires_choice"])
        self.assertIn("springboot-3.x", normalized["choice_options"])

    def test_normalize_ui_requirement_change_returns_to_prd_revision(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        state["ui_status"] = "READY_FOR_REVIEW"
        state["ui_artifacts_validated"] = True
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求要改，补充导出字段",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "prd_revision_requested")

    def test_resume_user_input_records_state_and_event_without_new_session(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "prd"
        state["phase_status"] = "waiting_review"
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "这个 PRD 不对，补充导出需求",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: prd_revision_requested", result.stdout)
        self.assertNotIn("/spl ", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["session_id"], self.session_id)
        self.assertEqual(updated["last_user_input_text"], "这个 PRD 不对，补充导出需求")
        self.assertEqual(updated["last_user_canonical_action"], "prd_revision_requested")
        self.assertEqual(updated["active_feedback_report"], f".superlooper/reports/{self.session_id}/prd_feedback.md")
        event_path = self.workspace_root / ".superlooper" / "events" / f"{self.session_id}.jsonl"
        self.assertTrue(event_path.exists())
        self.assertIn("prd_revision_requested", event_path.read_text(encoding="utf-8"))

    def test_resume_prd_blocked_decision_confirmation_moves_to_running(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "prd"
        state["phase_status"] = "blocked"
        state["last_error"] = "等待业务决策"
        state["next_actions"] = ["一次性确认关键决策看板中的 DEC-*"]
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "已确认，重新生成 PRD",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: prd_decisions_confirmed", result.stdout)
        self.assertIn("next_step: 重新调用 analyst 生成 PRD，不重新启动完整流程。", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "prd")
        self.assertEqual(updated["phase_status"], "running")
        self.assertIsNone(updated["last_error"])
        self.assertEqual(updated["last_user_canonical_action"], "prd_decisions_confirmed")
        self.assertEqual(updated["next_actions"], ["调用 analyst 基于已确认 DEC-* 重新生成 PRD"])

    def test_resume_user_input_records_ui_feedback_without_new_session(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        state["ui_status"] = "READY_FOR_REVIEW"
        state["ui_output_dir"] = f".superlooper/context/{self.session_id}/ui/"
        state["ui_artifacts_validated"] = True
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "UI 预览不对，页面跳转要重新设计",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: ui_revision_requested", result.stdout)
        self.assertNotIn("/spl ", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["last_user_canonical_action"], "ui_revision_requested")
        self.assertEqual(updated["active_feedback_report"], f".superlooper/reports/{self.session_id}/ui_feedback.md")
        self.assertEqual(updated["rollback_target_phase"], "ui_design")
        self.assertEqual(updated["ui_revision"], 1)
        self.assertEqual(updated["ui_status"], "CHANGES_REQUESTED")
        self.assertFalse(updated["ui_artifacts_validated"])
        feedback_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / "ui_feedback.md"
        self.assertTrue(feedback_path.exists())
        self.assertIn("UI 预览不对", feedback_path.read_text(encoding="utf-8"))

    def test_resume_ui_requirement_change_returns_to_prd_state(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        state["ui_status"] = "READY_FOR_REVIEW"
        state["ui_output_dir"] = f".superlooper/context/{self.session_id}/ui/"
        state["ui_artifacts_validated"] = True
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求要改，补充导出字段",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: prd_revision_requested", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "prd")
        self.assertEqual(updated["phase_status"], "running")
        self.assertEqual(updated["rollback_target_phase"], "prd")
        self.assertEqual(updated["active_feedback_report"], f".superlooper/reports/{self.session_id}/prd_feedback.md")
        self.assertEqual(updated["ui_status"], "CHANGES_REQUESTED")
        self.assertFalse(updated["ui_artifacts_validated"])
        self.assertEqual(updated["prd_revision"], 1)
        feedback_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / "prd_feedback.md"
        self.assertTrue(feedback_path.exists())
        feedback = feedback_path.read_text(encoding="utf-8")
        self.assertIn("canonical_action: prd_revision_requested", feedback)
        self.assertIn("需求要改，补充导出字段", feedback)

    def test_resume_initialization_category_choice_records_state(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "initialization"
        state["phase_status"] = "waiting_review"
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "springboot",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: select_project_category", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["project_category"], "springboot")
        self.assertIsNone(updated["project_version"])
        self.assertEqual(updated["next_actions"], ["请选择 springboot 的初始化版本：springboot-2.x/springboot-3.x"])

    def test_resume_initialization_version_choice_records_state(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "initialization"
        state["phase_status"] = "waiting_review"
        state["project_category"] = "springboot"
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "springboot-3.x",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: select_project_version", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["project_category"], "springboot")
        self.assertEqual(updated["project_version"], "springboot-3.x")
        self.assertEqual(updated["next_actions"], ["运行初始化脚本完成项目结构初始化"])

    def test_resume_user_input_approves_validated_ui_and_moves_to_design(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        state["ui_status"] = "READY_FOR_REVIEW"
        state["ui_output_dir"] = f".superlooper/context/{self.session_id}/ui/"
        state["ui_artifacts_validated"] = True
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "UI 设计通过，进入系统设计",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: approve_ui_and_proceed", result.stdout)
        self.assertIn("next_step: /spl:design demo-session", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "design")
        self.assertEqual(updated["phase_status"], "pending")
        self.assertEqual(updated["ui_status"], "APPROVED")
        self.assertTrue(updated["ui_artifacts_validated"])

    def test_resume_user_input_blocks_unvalidated_ui_approval(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        state["ui_status"] = "READY_FOR_REVIEW"
        state["ui_artifacts_validated"] = False
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "UI 设计通过，进入系统设计",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: approve_ui_and_proceed", result.stdout)
        self.assertIn("next_step: 先运行 /spl:ui 生成并校验 UI 产物。", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "ui_design")
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertEqual(updated["ui_status"], "BLOCKED")

    def test_normalize_execution_summary_approval(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "waiting_review"
        state["execution_summary_status"] = "READY_FOR_APPROVAL"
        self.write_state(state)

        result = self.run_script(
            "normalize_user_intent.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "按此执行",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = json.loads(result.stdout)
        self.assertEqual(normalized["canonical_action"], "execution_summary_approved")

    def test_resume_execution_summary_approval_moves_to_run_running(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "waiting_review"
        state["project_category"] = "springboot"
        state["project_version"] = "springboot-3.x"
        state["execution_summary_status"] = "READY_FOR_APPROVAL"
        state["execution_summary_report"] = f".superlooper/reports/{self.session_id}/execution_summary.md"
        self.write_state(state)
        self.write_execution_summary()

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "按此执行",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: execution_summary_approved", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "running")
        self.assertEqual(updated["execution_summary_status"], "APPROVED")
        self.assertEqual(updated["next_actions"], ["按执行摘要确认结果开始并行开发"])

    def test_resume_execution_summary_approval_blocks_without_report(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "waiting_review"
        state["execution_summary_status"] = "READY_FOR_APPROVAL"
        state["execution_summary_report"] = f".superlooper/reports/{self.session_id}/execution_summary.md"
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "按此执行",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertEqual(updated["execution_summary_status"], "BLOCKED")
        self.assertIn("execution_summary.md 不存在", updated["last_error"])

    def test_resume_start_execution_requires_execution_summary_approval(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "waiting_review"
        state["execution_summary_status"] = "NOT_STARTED"
        state["execution_summary_report"] = None
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "执行",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertEqual(updated["execution_summary_status"], "BLOCKED")
        self.assertIn("execution_summary_report 尚未写入 session state", updated["last_error"])
        self.assertEqual(updated["next_actions"], ["先生成并校验 execution_summary.md"])

    def test_resume_alignment_fail_updates_loop_state_until_limit(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "design"
        state["phase_status"] = "running"
        self.write_state(state)
        self.write_upstream_alignment(status="FAIL", mismatch_count=1, loop_required="true", loop_target_phase="design")

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "design")
        self.assertEqual(updated["phase_status"], "pending")
        self.assertEqual(updated["loop_state"]["current_loop_target_phase"], "design")
        self.assertEqual(updated["loop_state"]["loop_count_by_phase"], {"design": 1})
        self.assertEqual(updated["loop_state"]["last_alignment_status"], "FAIL")
        self.assertEqual(updated["loop_state"]["last_feedback_report"], f".superlooper/reports/{self.session_id}/upstream_alignment_feedback.md")
        self.assertEqual(updated["active_feedback_report"], f".superlooper/reports/{self.session_id}/upstream_alignment_feedback.md")

    def test_resume_alignment_fail_blocks_after_loop_limit(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "design"
        state["phase_status"] = "running"
        state["loop_state"]["loop_count_by_phase"] = {"design": 2}
        self.write_state(state)
        self.write_upstream_alignment(status="FAIL", mismatch_count=1, loop_required="true", loop_target_phase="design")

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertEqual(updated["loop_state"]["last_alignment_status"], "FAIL")
        self.assertIn("已达到自动 loop 上限", updated["last_error"])

    def test_resume_alignment_blocked_stops_for_manual_decision(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "design"
        state["phase_status"] = "running"
        self.write_state(state)
        self.write_upstream_alignment(status="BLOCKED", blocking_decisions=["DEC-001 需要确认架构边界"])

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertEqual(updated["loop_state"]["last_alignment_status"], "BLOCKED")
        self.assertIn("DEC-001 需要确认架构边界", updated["last_error"])

    def test_resume_execution_summary_revision_records_execution_summary_feedback(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "waiting_review"
        state["execution_summary_status"] = "READY_FOR_APPROVAL"
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "执行摘要未通过，返回修正，模块边界不接受",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: execution_summary_revision_requested", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["execution_summary_status"], "REJECTED")
        self.assertEqual(updated["rollback_target_phase"], "design")
        self.assertEqual(updated["active_feedback_report"], f".superlooper/reports/{self.session_id}/execution_summary_feedback.md")
        feedback_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / "execution_summary_feedback.md"
        self.assertTrue(feedback_path.exists())
        feedback = feedback_path.read_text(encoding="utf-8")
        self.assertIn("canonical_action: execution_summary_revision_requested", feedback)
        self.assertIn("模块边界不接受", feedback)

    def test_resume_code_review_failure_returns_to_run_rework(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "running"
        self.write_state(state)
        self.write_report(
            "code_review_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "code_review_status: FAIL\n"
            "blocker_count: 1\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            f"report_path: .superlooper/reports/{self.session_id}/code_review_report.md\n"
            "```\n",
        )

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "代码审查未通过，返回修正，修正 SQL 拼接问题",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: code_review_revision_requested", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "run")
        self.assertEqual(updated["phase_status"], "pending")
        self.assertEqual(updated["rollback_target_phase"], "run")
        self.assertEqual(updated["active_feedback_report"], f".superlooper/reports/{self.session_id}/code_review_feedback.md")
        self.assertIn(f".superlooper/reports/{self.session_id}/code_review_report.md", updated["invalidated_artifacts"])
        self.assertIn("重新执行代码审查", updated["next_actions"][0])

    def test_resume_test_failure_returns_to_run_rework(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "running"
        self.write_state(state)
        self.write_report(
            "test_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "test_status: FAIL\n"
            f"tested_path: .superlooper/merged/{self.session_id}\n"
            f"merge_report_path: .superlooper/reports/{self.session_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.session_id}/test_report.md\n"
            "```\n",
        )

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "测试未通过，返回修正，补测试失败路径",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: test_revision_requested", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "run")
        self.assertEqual(updated["phase_status"], "pending")
        self.assertEqual(updated["rollback_target_phase"], "run")
        self.assertEqual(updated["active_feedback_report"], f".superlooper/reports/{self.session_id}/test_feedback.md")
        self.assertIn(f".superlooper/reports/{self.session_id}/test_report.md", updated["invalidated_artifacts"])
        self.assertIn("重新 merge/test", updated["next_actions"][0])

    def test_resume_apply_conflict_resolved_requires_reapply(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "blocked"
        self.write_state(state)
        self.write_report(
            "apply_conflict_report.json",
            json.dumps(
                {
                    "session_id": self.session_id,
                    "status": "conflict",
                    "conflicts": [{"path": "src/main/java/Demo.java", "reason": "modify_requires_overwrite_existing"}],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "应用冲突已处理，重新应用",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: apply_retry_requested", result.stdout)
        self.assertIn("不直接输出完成结论", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "run")
        self.assertEqual(updated["phase_status"], "pending")
        self.assertEqual(updated["rollback_target_phase"], "run")
        self.assertIn("src/main/java/Demo.java", updated["next_actions"][0])

    def test_resume_continue_blocks_failed_apply_validation(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "blocked"
        self.write_state(state)
        self.write_report(
            "apply_report.json",
            json.dumps(
                {
                    "session_id": self.session_id,
                    "status": "failed",
                    "workspace_validation": {
                        "status": "FAIL",
                        "checked_file_count": 1,
                        "matched_file_count": 0,
                        "failed_file_count": 1,
                        "checked_files": [],
                        "failures": [{"path": "src/main/java/Demo.java", "reason": "content_mismatch"}],
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "继续任务",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertIn("workspace_validation.status 必须为 PASS", updated["last_error"])
        self.assertEqual(updated["next_actions"], ["修复 apply_report.json 中的 workspace_validation 失败项后重新应用"])

    def test_resume_local_rerun_approval_uses_change_impact_report(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "requirement_alignment"
        state["phase_status"] = "blocked"
        state["change_impact_report"] = f".superlooper/reports/{self.session_id}/change_impact_report.md"
        self.write_state(state)
        self.write_change_impact_report(rollback_target_phase="run")

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "影响分析通过，执行局部重跑",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: local_rerun_approved", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "run")
        self.assertEqual(updated["phase_status"], "pending")
        self.assertEqual(updated["rollback_target_phase"], "run")
        self.assertIn(f".superlooper/reports/{self.session_id}/test_report.md", updated["invalidated_artifacts"])
        self.assertEqual(updated["next_actions"], ["按 change_impact_report.md 只重跑 run 阶段和受影响模块"])

    def test_resume_requirement_alignment_approval_moves_to_report_passed(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "requirement_alignment"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        state["requirement_alignment_report"] = f".superlooper/reports/{self.session_id}/requirement_alignment_report.md"
        state["requirement_alignment_passed"] = False
        self.write_state(state)
        self.write_requirement_alignment_report()

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求校对通过，完成交付",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: requirement_alignment_approved", result.stdout)
        self.assertIn("next_step: 进入最终验收报告输出。", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "report")
        self.assertEqual(updated["phase_status"], "passed")
        self.assertTrue(updated["requirement_alignment_passed"])
        self.assertIsNone(updated["last_error"])
        self.assertEqual(updated["last_user_canonical_action"], "requirement_alignment_approved")
        self.assertEqual(updated["next_actions"], [f"查看 .superlooper/reports/{self.session_id}/session_report.md"])

    def test_resume_requirement_alignment_approval_blocks_without_report(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "requirement_alignment"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        state["requirement_alignment_report"] = f".superlooper/reports/{self.session_id}/requirement_alignment_report.md"
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求校对通过，完成交付",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "requirement_alignment")
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertFalse(updated["requirement_alignment_passed"])
        self.assertIn("requirement_alignment_report 不存在", updated["last_error"])
        self.assertEqual(updated["next_actions"], ["先生成并校验 requirement_alignment_report.md"])

    def test_resume_requirement_alignment_approval_blocks_failed_report(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "requirement_alignment"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        state["requirement_alignment_report"] = f".superlooper/reports/{self.session_id}/requirement_alignment_report.md"
        self.write_state(state)
        self.write_requirement_alignment_report(status="FAIL")

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求校对通过，完成交付",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertFalse(updated["requirement_alignment_passed"])
        self.assertEqual(updated["last_error"], "requirement_alignment_report 必须为 PASS。")

    def test_resume_requirement_alignment_approval_blocks_unmet_requirements(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "requirement_alignment"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        state["requirement_alignment_report"] = f".superlooper/reports/{self.session_id}/requirement_alignment_report.md"
        self.write_state(state)
        self.write_requirement_alignment_report(unmet=1)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求校对通过，完成交付",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertFalse(updated["requirement_alignment_passed"])
        self.assertIn("unmet_requirement_count 必须为 0", updated["last_error"])

    def test_resume_requirement_alignment_approval_blocks_unchecked_acceptance(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "requirement_alignment"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        state["requirement_alignment_report"] = f".superlooper/reports/{self.session_id}/requirement_alignment_report.md"
        self.write_state(state)
        self.write_requirement_alignment_report(unchecked=1)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求校对通过，完成交付",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertFalse(updated["requirement_alignment_passed"])
        self.assertIn("unchecked_acceptance_count 必须为 0", updated["last_error"])

    def test_resume_requirement_alignment_revision_writes_change_feedback(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "requirement_alignment"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "需求校对未通过，返回修正，导出验收没满足",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: requirement_alignment_revision_requested", result.stdout)
        self.assertIn("next_step: 调用 impact-analyzer 分析需求校对失败影响范围，不重新启动完整流程。", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["last_user_canonical_action"], "requirement_alignment_revision_requested")
        self.assertEqual(updated["active_feedback_report"], f".superlooper/reports/{self.session_id}/change_feedback.md")
        self.assertEqual(updated["rollback_target_phase"], "requirement_alignment")
        self.assertEqual(updated["next_actions"], ["调用 impact-analyzer 分析需求校对失败影响范围"])
        feedback_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / "change_feedback.md"
        self.assertTrue(feedback_path.exists())
        self.assertIn("需求校对未通过", feedback_path.read_text(encoding="utf-8"))

    def test_ambiguous_user_input_requires_choice(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "prd"
        state["phase_status"] = "waiting_review"
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "这个不行",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: choose_from_options", result.stdout)
        updated = self.read_state()
        self.assertIsInstance(updated["pending_user_choice"], dict)
        self.assertIn("prd_revision_requested", updated["pending_user_choice"]["choice_options"])

    def test_design_continue_moves_to_run_pending_when_ready(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "design"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = True
        state["ui_status"] = "APPROVED"
        state["ui_artifacts_validated"] = True
        self.write_state(state)
        module_split = self.workspace_root / ".superlooper" / "manifests" / self.session_id / "module-split.json"
        module_split.parent.mkdir(parents=True, exist_ok=True)
        module_split.write_text(json.dumps({"modules": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "继续任务",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: continue_current_flow", result.stdout)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "run")
        self.assertEqual(updated["phase_status"], "pending")
        self.assertIn("/spl:run", updated["next_actions"][0])

    def test_design_continue_blocks_before_initialization(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "design"
        state["phase_status"] = "waiting_review"
        state["project_initialized"] = False
        state["ui_status"] = "APPROVED"
        state["ui_artifacts_validated"] = True
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "继续任务",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "design")
        self.assertEqual(updated["phase_status"], "blocked")
        self.assertIn("project_initialized", updated["last_error"])

    def test_ui_waiting_continue_does_not_skip_ui_approval(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        state["ui_status"] = "READY_FOR_REVIEW"
        state["ui_artifacts_validated"] = True
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "继续任务",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "ui_design")
        self.assertEqual(updated["phase_status"], "waiting_review")
        self.assertIn("等待用户审核 UI", result.stdout)

    def test_execution_summary_waiting_continue_does_not_approve(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "waiting_review"
        state["execution_summary_status"] = "READY_FOR_APPROVAL"
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "继续任务",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = self.read_state()
        self.assertEqual(updated["current_phase"], "run")
        self.assertEqual(updated["phase_status"], "waiting_review")
        self.assertEqual(updated["execution_summary_status"], "READY_FOR_APPROVAL")
        self.assertIn("按此执行", result.stdout)

    def test_run_running_continue_does_not_restart_execution(self):
        self.create_session()
        state = self.read_state()
        state["current_phase"] = "run"
        state["phase_status"] = "running"
        state["next_actions"] = ["等待并行开发和质量门禁完成"]
        self.write_state(state)

        result = self.run_script(
            "resume_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--user-input",
            "继续任务",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("canonical_action: continue_current_flow", result.stdout)
        self.assertIn("等待执行完成或检查报告", result.stdout)
        self.assertNotIn("开始并行开发", result.stdout)


if __name__ == "__main__":
    unittest.main()
