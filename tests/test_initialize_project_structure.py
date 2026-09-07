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
        self.session_id = "init-session"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(self.repo_root / "scripts" / "create_session.py"),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                self.session_id,
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
        path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_initializes_springboot_structure_and_state(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
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
        report_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / "initialization_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["project_category"], "springboot")
        self.assertEqual(report["project_version"], "springboot-3.x")
        state = self.read_state()
        self.assertTrue(state["project_initialized"])
        self.assertEqual(state["initialization_report"], f".superlooper/reports/{self.session_id}/initialization_report.json")

    def test_rejects_overwriting_different_pom(self):
        (self.workspace_root / "pom.xml").write_text("<project>custom</project>\n", encoding="utf-8")
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--project-category",
            "springboot",
            "--project-version",
            "springboot-3.x",
            "--project-root",
            ".",
        )
        self.assertEqual(result.returncode, 2)
        conflict_path = self.workspace_root / ".superlooper" / "reports" / self.session_id / "initialization_conflict_report.json"
        self.assertTrue(conflict_path.is_file())
        self.assertFalse(self.read_state()["project_initialized"])


if __name__ == "__main__":
    unittest.main()
