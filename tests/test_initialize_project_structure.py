import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class InitializeProjectStructureScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.task_id = "init-session"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(self.repo_root / "scripts" / "create_session.py"),
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                self.task_id,
                "--requirement-path",
                str(self.requirement_path),
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, str(self.repo_root / "scripts" / "initialize_project_structure.py"), *args],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def read_state(self):
        path = self.workspace_root / ".superlooper" / "state" / f"{self.task_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_initializes_springboot_structure_and_state(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--project-category",
            "springboot",
            "--project-version",
            "springboot-3.x",
            "--project-root",
            ".",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.workspace_root / "src").is_dir())
        self.assertTrue((self.workspace_root / "src" / "main" / "java").is_dir())
        self.assertTrue((self.workspace_root / "src" / "main" / "resources").is_dir())
        self.assertTrue((self.workspace_root / "src" / "test" / "java").is_dir())
        self.assertTrue((self.workspace_root / "target").is_dir())
        self.assertTrue((self.workspace_root / "CLAUDE.md").is_file())
        self.assertTrue((self.workspace_root / "pom.xml").is_file())
        report_path = self.workspace_root / ".superlooper" / "reports" / self.task_id / "initialization_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["project_category"], "springboot")
        self.assertEqual(report["project_version"], "springboot-3.x")
        state = self.read_state()
        self.assertTrue(state["project_initialized"])
        self.assertEqual(state["initialization_report"], f".superlooper/reports/{self.task_id}/initialization_report.json")

    def test_rejects_overwriting_different_pom(self):
        (self.workspace_root / "pom.xml").write_text("<project>custom</project>\n", encoding="utf-8")
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--project-category",
            "springboot",
            "--project-version",
            "springboot-3.x",
            "--project-root",
            ".",
        )
        self.assertEqual(result.returncode, 2)
        conflict_path = self.workspace_root / ".superlooper" / "reports" / self.task_id / "initialization_conflict_report.json"
        self.assertTrue(conflict_path.is_file())
        self.assertFalse(self.read_state()["project_initialized"])

    def test_initialization_accepts_legacy_alias_and_canonicalizes_state(self):
        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.task_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["session_id"] = state.pop("task_id")
        state.pop("task_name")
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.task_id,
            "--project-category",
            "java",
            "--project-version",
            "jdk-17",
            "--project-root",
            ".",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        persisted = self.read_state()
        self.assertEqual(persisted["task_id"], self.task_id)
        self.assertIsNone(persisted["task_name"])
        self.assertNotIn("session_id", persisted)
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / self.task_id / "initialization_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["task_id"], self.task_id)
        self.assertNotIn("session_id", report)

    def test_rejects_windows_equivalent_protected_project_roots(self):
        for project_root in (
            ".CLAUDE/project",
            ".claude./project",
            ".superlooper /project",
            ".git\\project",
        ):
            with self.subTest(project_root=project_root):
                result = self.run_script(
                    "--workspace-root",
                    str(self.workspace_root),
                    "--task-id",
                    self.task_id,
                    "--project-category",
                    "springboot",
                    "--project-version",
                    "springboot-3.x",
                    "--project-root",
                    project_root,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("project_root", result.stderr)


if __name__ == "__main__":
    unittest.main()
