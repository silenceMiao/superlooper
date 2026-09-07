import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ObservabilityScriptsTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.fixtures_root = self.repo_root / "tests" / "fixtures"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name) / "workspace"
        self.session_id = "observability_demo"
        self.requirement_path = self.workspace_root / "requirements.md"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, script_name, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(self.repo_root / "scripts" / script_name), *args],
            cwd=cwd or self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def create_session(self):
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.requirement_path.write_text("# original requirement body\n", encoding="utf-8")
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

    def copy_fixture(self, name):
        shutil.copytree(self.fixtures_root / name / "workspace", self.workspace_root)

    def write_initialized_state(self, session_id):
        reports_dir = self.workspace_root / ".superlooper" / "reports" / session_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "initialization_report.json").write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "status": "success",
                    "project_category": "springboot",
                    "project_version": "springboot-3.x",
                    "project_root": ".",
                    "created_paths": ["src/main/java", "src/main/resources", "src/test/java", "target", "CLAUDE.md", "pom.xml"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        context_dir = self.workspace_root / ".superlooper" / "context" / session_id
        for relative_path in (
            "ui/ui-spec.md",
            "ui/page-map.md",
            "ui/interaction-flow.md",
            "ui/ui-handoff.md",
            "ui/preview.html",
            "design/architecture.md",
            "design/tech-stack.md",
            "design/project-profile.md",
            "design/initialization-advice.md",
        ):
            artifact_path = context_dir / relative_path
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text("# fixture\n", encoding="utf-8")
        state_dir = self.workspace_root / ".superlooper" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / f"{session_id}.json").write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "workspace_root": str(self.workspace_root.resolve()),
                    "requirement_path": str((self.workspace_root / "requirements.md").resolve()),
                    "current_phase": "run",
                    "phase_status": "pending",
                    "generated_files": [],
                    "reports": [],
                    "last_command": "test",
                    "last_error": None,
                    "next_actions": [],
                    "project_mode": "greenfield",
                    "workflow_mode": "standard",
                    "project_category": "springboot",
                    "project_version": "springboot-3.x",
                    "project_root": ".",
                    "project_initialized": True,
                    "initialization_report": f".superlooper/reports/{session_id}/initialization_report.json",
                    "ui_status": "APPROVED",
                    "ui_output_dir": f".superlooper/context/{session_id}/ui/",
                    "ui_artifacts_validated": True,
                    "execution_summary_status": "NOT_STARTED",
                    "execution_summary_report": None,
                    "loop_policy": {"max_auto_loop_per_phase": 2},
                    "loop_state": {
                        "current_loop_target_phase": None,
                        "loop_count_by_phase": {},
                        "last_alignment_status": None,
                        "last_feedback_report": None,
                    },
                    "requirement_alignment_report": None,
                    "requirement_alignment_passed": False,
                    "prd_revision": 0,
                    "design_revision": 0,
                    "change_request_count": 0,
                    "active_feedback_report": None,
                    "change_impact_report": None,
                    "invalidated_artifacts": [],
                    "rollback_target_phase": None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_report(self, filename, content):
        report_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / filename
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(content, encoding="utf-8")
        return report_path

    def write_json_report(self, filename, payload):
        self.write_report(filename, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def write_valid_gate_reports(self):
        self.write_report(
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
        self.write_report(
            "test_report.md",
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            "test_status: PASS\n"
            f"tested_path: .superlooper/merged/{self.session_id}\n"
            f"merge_report_path: .superlooper/reports/{self.session_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.session_id}/test_report.md\n"
            "```\n",
        )
        self.write_json_report("apply_report.json", {"session_id": self.session_id, "status": "success"})

    def test_update_session_writes_event_jsonl(self):
        self.create_session()

        result = self.run_script(
            "update_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--current-phase",
            "design",
            "--phase-status",
            "running",
            "--last-command",
            "/spl:design observability_demo",
            "--generated-file",
            ".superlooper/context/observability_demo/design/architecture.md",
            "--report",
            ".superlooper/reports/observability_demo/code_review_report.md",
            "--next-action",
            "等待设计输出完成",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        event_path = self.workspace_root / ".superlooper" / "events" / f"{self.session_id}.jsonl"
        self.assertTrue(event_path.exists())
        lines = event_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        event = json.loads(lines[0])
        self.assertEqual(event["session_id"], self.session_id)
        self.assertEqual(event["current_phase"], "design")
        self.assertEqual(event["phase_status"], "running")
        self.assertEqual(event["last_command"], "/spl:design observability_demo")
        self.assertIsNone(event["last_error"])
        self.assertEqual(event["generated_files"], [".superlooper/context/observability_demo/design/architecture.md"])
        self.assertEqual(event["reports"], [".superlooper/reports/observability_demo/code_review_report.md"])
        self.assertEqual(event["next_actions"], ["等待设计输出完成"])
        self.assertNotIn("original requirement body", lines[0])

    def test_update_session_redacts_event_log_secrets_only(self):
        self.create_session()
        bearer_header = "Authorization:" + " Bearer "
        access_key_name = "access" + "_key"
        secret_key_name = "secret" + "_key"
        last_command = f"curl -H '{bearer_header}top-secret-bearer' https://example.test?token=abc123"
        generated_file = f"build/output.txt?{access_key_name}=AKIAEXAMPLE"
        report = f".superlooper/reports/observability_demo/code_review_report.md?{secret_key_name}=secret-key-value"
        last_error = "request failed token=abc123 password: super-secret-password secret=hidden-secret api_key: demo-api-key"
        next_action = f"retry with {bearer_header}next-bearer and token: next-token"

        result = self.run_script(
            "update_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--current-phase",
            "design",
            "--phase-status",
            "failed",
            "--last-command",
            last_command,
            "--generated-file",
            generated_file,
            "--report",
            report,
            "--last-error",
            last_error,
            "--next-action",
            next_action,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        event_path = self.workspace_root / ".superlooper" / "events" / f"{self.session_id}.jsonl"
        line = event_path.read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("[REDACTED]", line)
        for secret in [
            "top-secret-bearer",
            "abc123",
            "AKIAEXAMPLE",
            "secret-key-value",
            "super-secret-password",
            "hidden-secret",
            "demo-api-key",
            "next-bearer",
            "next-token",
        ]:
            self.assertNotIn(secret, line)

        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["last_error"], last_error)
        self.assertEqual(state["next_actions"], [next_action])

    def test_validate_observability_accepts_matching_state_and_event(self):
        self.create_session()
        result = self.run_script(
            "update_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--current-phase",
            "design",
            "--phase-status",
            "running",
            "--last-command",
            "/spl:design observability_demo",
            "--next-action",
            "等待设计输出完成",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        result = self.run_script(
            "validate_miao_contracts.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--scope",
            "observability",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_observability_rejects_state_event_mismatch(self):
        self.create_session()
        result = self.run_script(
            "update_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--current-phase",
            "design",
            "--phase-status",
            "running",
            "--last-command",
            "/spl:design observability_demo",
            "--next-action",
            "等待设计输出完成",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["phase_status"] = "passed"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_script(
            "validate_miao_contracts.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--scope",
            "observability",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("event 最后状态与 state 不一致", result.stderr)

    def test_validate_observability_rejects_passed_state_without_apply_report(self):
        self.create_session()
        result = self.run_script(
            "update_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--current-phase",
            "report",
            "--phase-status",
            "passed",
            "--last-command",
            "/spl:run observability_demo",
            "--next-action",
            "查看最终报告",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        result = self.run_script(
            "validate_miao_contracts.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--scope",
            "observability",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("apply_report.json", result.stderr)

    def test_validate_observability_rejects_passed_state_with_apply_conflict(self):
        self.create_session()
        result = self.run_script(
            "update_session.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--current-phase",
            "report",
            "--phase-status",
            "passed",
            "--last-command",
            "/spl:run observability_demo",
            "--report",
            ".superlooper/reports/observability_demo/apply_report.json",
            "--next-action",
            "查看最终报告",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_json_report("apply_conflict_report.json", {"session_id": self.session_id, "status": "blocked"})

        result = self.run_script(
            "validate_miao_contracts.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--scope",
            "observability",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("state=report/passed 时不得存在 apply_conflict_report.json", result.stderr)

    def test_build_session_report_redacts_workspace_root(self):
        self.create_session()
        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["current_phase"] = "report"
        state["phase_status"] = "passed"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.write_valid_gate_reports()

        result = self.run_script(
            "build_session_report.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--redact-paths",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = (self.workspace_root / ".superlooper" / "reports" / self.session_id / "session_report.md").read_text(encoding="utf-8")
        self.assertIn("- workspace_root: .", report)
        self.assertNotIn(str(self.workspace_root.resolve()), report)

    def test_merge_and_apply_redact_paths_remove_absolute_workspace_root(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")

        result = self.run_script(
            "generate_execution_manifest.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            "session_happy",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        result = self.run_script(
            "merge_artifacts.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            "session_happy",
            "--redact-paths",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        merge_report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json"
        merge_report_text = merge_report_path.read_text(encoding="utf-8")
        merge_report = json.loads(merge_report_text)
        self.assertEqual(merge_report["workspace_root"], ".")
        self.assertNotIn(str(self.workspace_root.resolve()), merge_report_text)

        reports_dir = self.workspace_root / ".superlooper" / "reports" / "session_happy"
        reports_dir.mkdir(parents=True, exist_ok=True)
        result = self.run_script(
            "generate_runtime_agents.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            "session_happy",
            "--agents-dir",
            "agents",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        (reports_dir / "code_review_report.md").write_text(
            "```yaml\n"
            "session_id: session_happy\n"
            "code_review_status: PASS\n"
            "blocker_count: 0\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            "- report_export\n"
            "- audit_log\n"
            "report_path: .superlooper/reports/session_happy/code_review_report.md\n"
            "```\n",
            encoding="utf-8",
        )
        (reports_dir / "test_report.md").write_text(
            "```yaml\n"
            "session_id: session_happy\n"
            "test_status: PASS\n"
            "tested_path: .superlooper/merged/session_happy/\n"
            "test_workspace_path: null\n"
            "merge_report_path: .superlooper/reports/session_happy/merge_report.json\n"
            "report_path: .superlooper/reports/session_happy/test_report.md\n"
            "```\n",
            encoding="utf-8",
        )

        result = self.run_script(
            "apply_to_workspace.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            "session_happy",
            "--redact-paths",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        apply_report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json"
        apply_report_text = apply_report_path.read_text(encoding="utf-8")
        apply_report = json.loads(apply_report_text)
        self.assertEqual(apply_report["workspace_root"], ".")
        self.assertNotIn(str(self.workspace_root.resolve()), apply_report_text)


if __name__ == "__main__":
    unittest.main()
