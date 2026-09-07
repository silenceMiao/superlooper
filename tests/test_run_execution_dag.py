import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RunExecutionDagTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "dag-session"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")
        self.create_session()
        self.manifest_dir = self.workspace_root / ".superlooper" / "manifests" / self.session_id
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, script_name, *args):
        script_path = self.repo_root / "scripts" / script_name
        return subprocess.run(
            [sys.executable, str(script_path), *args],
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

    def write_execution_manifest(self, nodes):
        manifest = {
            "session_id": self.session_id,
            "dag": {"nodes": nodes},
        }
        (self.manifest_dir / "execution_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def read_dag_state(self):
        path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.dag.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def read_session_state(self):
        path = self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_run_execution_dag_writes_success_state_in_dependency_order(self):
        self.write_execution_manifest(
            [
                {"id": "mod_a", "type": "module", "agent": "module_a", "depends_on": [], "payload": {"module_id": "a"}},
                {"id": "task_code_review", "type": "quality_gate", "agent": "code-reviewer", "depends_on": ["mod_a"], "payload": "review"},
            ]
        )

        result = self.run_script(
            "run_execution_dag.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        dag_state = self.read_dag_state()
        self.assertEqual(dag_state["session_id"], self.session_id)
        self.assertEqual(dag_state["dag_status"], "success")
        self.assertEqual(dag_state["execution_order"], ["mod_a", "task_code_review"])
        self.assertEqual(dag_state["nodes"]["mod_a"]["status"], "success")
        self.assertEqual(dag_state["nodes"]["task_code_review"]["status"], "success")
        session_state = self.read_session_state()
        self.assertEqual(session_state["script_events"][-1]["script"], "run_execution_dag")
        self.assertEqual(session_state["script_events"][-1]["status"], "completed")

    def test_run_execution_dag_blocks_missing_dependency(self):
        self.write_execution_manifest(
            [
                {"id": "task_code_review", "agent": "code-reviewer", "depends_on": ["mod_missing"], "payload": "review"},
            ]
        )

        result = self.run_script(
            "run_execution_dag.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertNotEqual(result.returncode, 0)
        dag_state = self.read_dag_state()
        self.assertEqual(dag_state["dag_status"], "failed")
        self.assertIn("mod_missing", dag_state["error_summary"])

    def test_run_execution_dag_blocks_cycle_dependency(self):
        self.write_execution_manifest(
            [
                {"id": "mod_a", "agent": "module_a", "depends_on": ["mod_b"], "payload": {"module_id": "a"}},
                {"id": "mod_b", "agent": "module_b", "depends_on": ["mod_a"], "payload": {"module_id": "b"}},
            ]
        )

        result = self.run_script(
            "run_execution_dag.py",
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
        )

        self.assertNotEqual(result.returncode, 0)
        dag_state = self.read_dag_state()
        self.assertEqual(dag_state["dag_status"], "failed")
        self.assertIn("循环依赖", dag_state["error_summary"])


if __name__ == "__main__":
    unittest.main()
