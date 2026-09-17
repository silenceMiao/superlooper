import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import create_session


class CrossPlatformEquivalenceTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.task_id = "session_cross_platform"
        self.manifests_dir = self.workspace_root / ".superlooper" / "manifests" / self.task_id
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self._write_session_fixture()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_session_fixture(self):
        ui_dir = self.workspace_root / ".superlooper" / "context" / self.task_id / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("ui-spec.md", "page-map.md", "interaction-flow.md", "ui-handoff.md"):
            (ui_dir / filename).write_text(f"# {filename}\n", encoding="utf-8")
        (ui_dir / "preview.html").write_text("<!doctype html><html><body></body></html>\n", encoding="utf-8")

        design_dir = self.workspace_root / ".superlooper" / "context" / self.task_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("architecture.md", "tech-stack.md", "project-profile.md", "initialization-advice.md"):
            (design_dir / filename).write_text(f"# {filename}\n", encoding="utf-8")

        reports_dir = self.workspace_root / ".superlooper" / "reports" / self.task_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "initialization_report.json").write_text(
            json.dumps({"task_id": self.task_id, "status": "success"}) + "\n",
            encoding="utf-8",
        )
        state_dir = self.workspace_root / ".superlooper" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / f"{self.task_id}.json").write_text(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "task_name": None,
                    "workspace_root": str(self.workspace_root.resolve()),
                    "requirement_path": str((self.workspace_root / "requirements.md").resolve()),
                    "current_phase": "run",
                    "phase_status": "pending",
                    "generated_files": [],
                    "reports": [],
                    "script_events": [],
                    "last_command": "test",
                    "last_error": None,
                    "next_actions": [],
                    "project_mode": "greenfield",
                    "workflow_mode": "standard",
                    "project_category": "springboot",
                    "project_version": "springboot-3.x",
                    "project_root": ".",
                    "project_initialized": True,
                    "initialization_report": f".superlooper/reports/{self.task_id}/initialization_report.json",
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
                    "ui_revision": 0,
                    "ui_status": "APPROVED",
                    "ui_output_dir": f".superlooper/context/{self.task_id}/ui/",
                    "ui_artifacts_validated": True,
                    "design_revision": 0,
                    "change_request_count": 0,
                    "active_feedback_report": None,
                    "change_impact_report": None,
                    "affected_modules": [],
                    "invalidated_artifacts": [],
                    "rollback_target_phase": None,
                    "last_user_input_text": None,
                    "last_user_canonical_action": None,
                    "pending_user_choice": None,
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
                            "requirement_refs": ["REQ-001"],
                            "acceptance_refs": ["AC-001"],
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _run_script(self, script_name, platform):
        command = [
            sys.executable,
            str(self.repo_root / "scripts" / script_name),
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--platform",
            platform,
        ]
        if script_name == "generate_runtime_agents.py":
            command.extend(["--agents-dir", "agents"])
        return subprocess.run(
            command,
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def _generate_platform_artifacts(self, platform):
        manifest_result = self._run_script("generate_execution_manifest.py", platform)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        manifest = json.loads((self.manifests_dir / "execution_manifest.json").read_text(encoding="utf-8"))

        agents_result = self._run_script("generate_runtime_agents.py", platform)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_agent = (
            self.workspace_root
            / ".superlooper"
            / "agents"
            / self.task_id
            / "module_report_export.md"
        ).read_text(encoding="utf-8")
        return manifest, runtime_agent

    def test_platforms_generate_equivalent_shared_manifest_and_runtime_agent(self):
        claude_manifest, claude_runtime_agent = self._generate_platform_artifacts("claude")
        codex_manifest, codex_runtime_agent = self._generate_platform_artifacts("codex")

        self.assertEqual(claude_manifest["dag"]["nodes"], codex_manifest["dag"]["nodes"])
        self.assertEqual(claude_manifest["task_id"], codex_manifest["task_id"])
        self.assertEqual(claude_manifest["context"]["prd_path"], codex_manifest["context"]["prd_path"])
        self.assertEqual(claude_manifest["context"]["reports_path"], codex_manifest["context"]["reports_path"])

        claude_context = dict(claude_manifest["context"])
        codex_context = dict(codex_manifest["context"])
        self.assertEqual(
            claude_context.pop("registered_agents_path"),
            f".claude/agents/generated/superlooper/{self.task_id}/",
        )
        self.assertEqual(codex_context.pop("platform_registration"), {"platform": "codex"})
        self.assertEqual(claude_context, codex_context)
        self.assertEqual(claude_runtime_agent, codex_runtime_agent)
        self.assertFalse(
            (
                self.workspace_root
                / ".superlooper"
                / "agents"
                / self.task_id
                / "codex-dispatch.json"
            ).exists()
        )

    def test_windows_path_key_collapses_case_separators_and_trailing_dots_or_spaces(self):
        expected = "src/foo.java"
        for value in (
            "src/Foo.java",
            "SRC/foo.java",
            "src\\foo.java",
            "src/foo.java.",
            "src/foo.java ",
        ):
            with self.subTest(value=value):
                self.assertEqual(create_session.windows_path_key(value), expected)

    def test_safe_relative_path_rejects_windows_equivalent_protected_roots(self):
        protected_roots = {".git", ".claude", ".superlooper"}
        for value in (
            ".GIT/config",
            ".git./config",
            ".git /config",
            ".git\\config",
            ".CLAUDE/settings.json",
            ".superlooper.\\state.json",
        ):
            with self.subTest(value=value):
                self.assertFalse(
                    create_session.is_safe_relative_path(
                        value,
                        protected_roots=protected_roots,
                    )
                )

    def test_safe_relative_path_rejects_segments_that_normalize_to_empty_dot_or_dotdot(self):
        for value in (". /file.txt", ".. /file.txt", "src/ /file.txt"):
            with self.subTest(value=value):
                self.assertFalse(create_session.is_safe_relative_path(value))


if __name__ == "__main__":
    unittest.main()
