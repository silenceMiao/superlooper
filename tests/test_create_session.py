import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CreateSessionScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "session_create"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, *args):
        script_path = self.repo_root / "scripts" / "create_session.py"
        return subprocess.run(
            [sys.executable, str(script_path), *args],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_create_session_creates_runtime_layout_and_initial_state(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--requirement-path",
            str(self.requirement_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_root = self.workspace_root / ".superlooper"
        expected_dirs = [
            runtime_root / "context" / self.session_id,
            runtime_root / "reports" / self.session_id,
            runtime_root / "manifests" / self.session_id,
            runtime_root / "agents" / self.session_id,
            runtime_root / "outputs" / self.session_id,
            runtime_root / "state",
        ]
        for path in expected_dirs:
            self.assertTrue(path.is_dir(), path)

        state_path = runtime_root / "state" / f"{self.session_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["session_id"], self.session_id)
        self.assertEqual(state["workspace_root"], str(self.workspace_root.resolve()))
        self.assertEqual(state["requirement_path"], str(self.requirement_path.resolve()))
        self.assertEqual(state["current_phase"], "prd")
        self.assertEqual(state["phase_status"], "pending")
        self.assertEqual(state["generated_files"], [])
        self.assertEqual(state["reports"], [])
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

    def test_create_session_rejects_dot_and_dotdot_session_ids(self):
        for session_id in (".", ".."):
            with self.subTest(session_id=session_id):
                result = self.run_script(
                    "--workspace-root",
                    str(self.workspace_root),
                    "--session-id",
                    session_id,
                    "--requirement-path",
                    str(self.requirement_path),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("session_id", result.stderr)

    def test_create_session_rejects_relative_requirement_path_with_parent_segment(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--requirement-path",
            "../requirements.md",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path", result.stderr)

    def test_create_session_rejects_missing_requirement_path(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--requirement-path",
            str(self.workspace_root / "missing.md"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path 不存在", result.stderr)

    def test_create_session_rejects_directory_requirement_path(self):
        requirement_dir = self.workspace_root / "requirements-dir"
        requirement_dir.mkdir()

        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--requirement-path",
            str(requirement_dir),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path 必须是文件", result.stderr)


if __name__ == "__main__":
    unittest.main()
