import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CLAUDE_PLATFORM = "claude"
CODEX_PLATFORM = "codex"


class CodexRegistrationTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "session_codex_registration"
        self.manifests_dir = self.workspace_root / ".superlooper" / "manifests" / self.session_id
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self._write_session_fixture()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_session_fixture(self):
        ui_dir = self.workspace_root / ".superlooper" / "context" / self.session_id / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("ui-spec.md", "page-map.md", "interaction-flow.md", "ui-handoff.md"):
            (ui_dir / filename).write_text(f"# {filename}\n", encoding="utf-8")
        (ui_dir / "preview.html").write_text("<!doctype html><html><body></body></html>\n", encoding="utf-8")

        design_dir = self.workspace_root / ".superlooper" / "context" / self.session_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("architecture.md", "tech-stack.md", "project-profile.md", "initialization-advice.md"):
            (design_dir / filename).write_text(f"# {filename}\n", encoding="utf-8")

        reports_dir = self.workspace_root / ".superlooper" / "reports" / self.session_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        initialization_report = reports_dir / "initialization_report.json"
        initialization_report.write_text(
            json.dumps({"session_id": self.session_id, "status": "success"}) + "\n",
            encoding="utf-8",
        )
        state_dir = self.workspace_root / ".superlooper" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / f"{self.session_id}.json").write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "current_phase": "run",
                    "phase_status": "pending",
                    "project_initialized": True,
                    "initialization_report": f".superlooper/reports/{self.session_id}/initialization_report.json",
                    "ui_status": "APPROVED",
                    "ui_artifacts_validated": True,
                    "ui_output_dir": f".superlooper/context/{self.session_id}/ui/",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.manifests_dir / "module-split.json").write_text(
            json.dumps(
                {
                    "project_name": "demo",
                    "modules": [
                        {
                            "id": "report_export",
                            "name": "Report Export",
                            "description": "实现报表导出控制器",
                            "referenced_tables": [],
                            "referenced_apis": [],
                            "target_files": ["src/main/java/com/example/controller/ReportExportController.java"],
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        agents_dir = self.workspace_root / "agents"
        agents_dir.mkdir()
        (agents_dir / "developer.md").write_text(
            (self.repo_root / "agents" / "developer.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def _run_manifest(self, platform):
        return self._run_script(
            "generate_execution_manifest.py",
            "--platform",
            platform,
        )

    def _run_agents(self, platform):
        return self._run_script(
            "generate_runtime_agents.py",
            "--platform",
            platform,
            "--agents-dir",
            "agents",
        )

    def _run_validate(self):
        return self._run_script(
            "validate_miao_contracts.py",
            "--scope",
            "execution",
            "--agents-dir",
            "agents",
        )

    def _run_script(self, script_name, *extra_args):
        return subprocess.run(
            [
                sys.executable,
                str(self.repo_root / "scripts" / script_name),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                self.session_id,
                *extra_args,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def _read_manifest(self):
        return json.loads((self.manifests_dir / "execution_manifest.json").read_text(encoding="utf-8"))

    def test_claude_registration_keeps_matching_runtime_and_registered_agents(self):
        manifest_result = self._run_manifest(CLAUDE_PLATFORM)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self._run_agents(CLAUDE_PLATFORM)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)

        manifest = self._read_manifest()
        self.assertEqual(
            manifest["context"]["registered_agents_path"],
            f".claude/agents/generated/superlooper/{self.session_id}/",
        )
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.session_id / "module_report_export.md"
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.session_id / "module_report_export.md"
        self.assertEqual(runtime_path.read_text(encoding="utf-8"), registered_path.read_text(encoding="utf-8"))

    def test_codex_registration_keeps_runtime_agents_without_a_dispatcher_copy(self):
        manifest_result = self._run_manifest(CODEX_PLATFORM)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self._run_agents(CODEX_PLATFORM)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)

        manifest = self._read_manifest()
        context = manifest["context"]
        self.assertNotIn("registered_agents_path", context)
        self.assertEqual(context["platform_registration"], {"platform": CODEX_PLATFORM})
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.session_id / "module_report_export.md"
        dispatch_path = self.workspace_root / ".superlooper" / "agents" / self.session_id / "codex-dispatch.json"
        self.assertTrue(runtime_path.is_file())
        self.assertFalse(dispatch_path.exists())
        self.assertFalse((self.workspace_root / ".claude").exists())

        validation_result = self._run_validate()
        self.assertEqual(validation_result.returncode, 0, validation_result.stderr)


if __name__ == "__main__":
    unittest.main()
