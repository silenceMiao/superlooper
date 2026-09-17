import hashlib
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
        self.task_id = "session_codex_registration"
        self.manifests_dir = self.workspace_root / ".superlooper" / "manifests" / self.task_id
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self._write_session_fixture()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_session_fixture(self):
        (self.workspace_root / "requirements.md").write_text(
            "TOP SECRET ORIGINAL REQUIREMENT\n",
            encoding="utf-8",
        )
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
        initialization_report = reports_dir / "initialization_report.json"
        initialization_report.write_text(
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
                        },
                        {
                            "id": "audit_log",
                            "name": "Audit Log",
                            "description": "实现审计日志服务",
                            "referenced_tables": [],
                            "referenced_apis": [],
                            "target_files": ["src/main/java/com/example/service/AuditLogService.java"],
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

    def _run_renderer(self, node_id="mod_report_export"):
        return self._run_script(
            "render_codex_spawn_prompt.py",
            "--node-id",
            node_id,
        )

    def _run_script(self, script_name, *extra_args):
        return subprocess.run(
            [
                sys.executable,
                str(self.repo_root / "scripts" / script_name),
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                self.task_id,
                *extra_args,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def _read_manifest(self):
        return json.loads((self.manifests_dir / "execution_manifest.json").read_text(encoding="utf-8"))

    def _frontmatter_and_body(self, content):
        lines = content.splitlines()
        end_index = lines.index("---", 1)
        frontmatter = {}
        for line in lines[1:end_index]:
            key, value = line.split(":", 1)
            raw_value = value.strip()
            try:
                frontmatter[key] = json.loads(raw_value)
            except json.JSONDecodeError:
                frontmatter[key] = raw_value
        return frontmatter, "\n".join(lines[end_index + 1 :])

    def test_claude_registration_scopes_name_and_preserves_runtime_semantics(self):
        manifest_result = self._run_manifest(CLAUDE_PLATFORM)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self._run_agents(CLAUDE_PLATFORM)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)

        manifest = self._read_manifest()
        report_node = next(node for node in manifest["dag"]["nodes"] if node["id"] == "mod_report_export")
        self.assertEqual(report_node["agent"], "module_report_export")
        self.assertEqual(
            manifest["context"]["registered_agents_path"],
            f".claude/agents/generated/superlooper/{self.task_id}/",
        )
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "module_report_export.md"
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id / "module_report_export.md"
        runtime_frontmatter, runtime_body = self._frontmatter_and_body(
            runtime_path.read_text(encoding="utf-8")
        )
        registered_frontmatter, registered_body = self._frontmatter_and_body(
            registered_path.read_text(encoding="utf-8")
        )
        self.assertEqual(runtime_frontmatter["name"], "module_report_export")
        self.assertEqual(
            registered_frontmatter["name"],
            "module_report_export__task_"
            + hashlib.sha256(self.task_id.encode("utf-8")).hexdigest()[:16],
        )
        self.assertEqual(
            {key: value for key, value in runtime_frontmatter.items() if key != "name"},
            {key: value for key, value in registered_frontmatter.items() if key != "name"},
        )
        self.assertEqual(runtime_body, registered_body)

    def test_agent_generation_preserves_existing_dynamic_agent_files(self):
        preserved_files = {
            self.workspace_root
            / ".superlooper"
            / "agents"
            / "older_task"
            / "module_legacy.md": "older runtime\n",
            self.workspace_root
            / ".claude"
            / "agents"
            / "generated"
            / "superlooper"
            / "older_task"
            / "module_legacy.md": "older registered\n",
            self.workspace_root
            / ".superlooper"
            / "agents"
            / self.task_id
            / "module_stale.md": "current runtime sentinel\n",
            self.workspace_root
            / ".claude"
            / "agents"
            / "generated"
            / "superlooper"
            / self.task_id
            / "module_stale.md": "current registered sentinel\n",
        }
        for path, content in preserved_files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        manifest_result = self._run_manifest(CLAUDE_PLATFORM)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self._run_agents(CLAUDE_PLATFORM)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)

        for path, content in preserved_files.items():
            self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_codex_registration_keeps_runtime_agents_without_a_dispatcher_copy(self):
        manifest_result = self._run_manifest(CODEX_PLATFORM)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self._run_agents(CODEX_PLATFORM)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)

        manifest = self._read_manifest()
        context = manifest["context"]
        report_node = next(node for node in manifest["dag"]["nodes"] if node["id"] == "mod_report_export")
        self.assertEqual(report_node["agent"], "module_report_export")
        self.assertNotIn("registered_agents_path", context)
        self.assertEqual(context["platform_registration"], {"platform": CODEX_PLATFORM})
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "module_report_export.md"
        dispatch_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "codex-dispatch.json"
        self.assertTrue(runtime_path.is_file())
        self.assertFalse(dispatch_path.exists())
        self.assertFalse((self.workspace_root / ".claude").exists())

        validation_result = self._run_validate()
        self.assertEqual(validation_result.returncode, 0, validation_result.stderr)

    def test_codex_renderer_injects_only_current_runtime_agent_and_context(self):
        manifest_result = self._run_manifest(CODEX_PLATFORM)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self._run_agents(CODEX_PLATFORM)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_path = (
            self.workspace_root
            / ".superlooper"
            / "agents"
            / self.task_id
            / "module_report_export.md"
        )
        runtime_content = runtime_path.read_text(encoding="utf-8")

        result = self._run_renderer()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(runtime_content, result.stdout)
        self.assertIn("## Runtime Module Constraints", result.stdout)
        self.assertIn('"id": "mod_report_export"', result.stdout)
        self.assertIn('"id": "report_export"', result.stdout)
        self.assertIn(
            f".superlooper/context/{self.task_id}/design/architecture.md",
            result.stdout,
        )
        self.assertIn(
            f".superlooper/outputs/{self.task_id}/report_export/",
            result.stdout,
        )
        self.assertIn(
            f".superlooper/outputs/{self.task_id}/report_export/artifact_manifest.json",
            result.stdout,
        )
        self.assertNotIn("mod_audit_log", result.stdout)
        self.assertNotIn("module_audit_log", result.stdout)
        self.assertNotIn("AuditLogService.java", result.stdout)
        self.assertNotIn("TOP SECRET ORIGINAL REQUIREMENT", result.stdout)

    def test_codex_renderer_rejects_runtime_agent_path_outside_task_root(self):
        manifest_result = self._run_manifest(CODEX_PLATFORM)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self._run_agents(CODEX_PLATFORM)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = self._read_manifest()
        manifest["context"]["runtime_agents_path"] = "../outside/"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self._run_renderer()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime_agents_path", result.stderr)

    def test_codex_renderer_rejects_runtime_agent_frontmatter_name_mismatch(self):
        manifest_result = self._run_manifest(CODEX_PLATFORM)
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self._run_agents(CODEX_PLATFORM)
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_path = (
            self.workspace_root
            / ".superlooper"
            / "agents"
            / self.task_id
            / "module_report_export.md"
        )
        content = runtime_path.read_text(encoding="utf-8")
        runtime_path.write_text(
            content.replace("name: module_report_export", "name: wrong_agent"),
            encoding="utf-8",
        )

        result = self._run_renderer()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("frontmatter name", result.stderr)


if __name__ == "__main__":
    unittest.main()
