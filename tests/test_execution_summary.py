import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ExecutionSummaryScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "session_summary"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")
        self.reports_dir = self.workspace_root / ".superlooper" / "reports" / self.session_id
        self.manifests_dir = self.workspace_root / ".superlooper" / "manifests" / self.session_id
        self.agents_dir = self.workspace_root / "agents"

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
            "--session-id",
            self.session_id,
            "--requirement-path",
            str(self.requirement_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def read_state(self):
        return json.loads((self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json").read_text(encoding="utf-8"))

    def write_state(self, state):
        (self.workspace_root / ".superlooper" / "state" / f"{self.session_id}.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_initialized_state(self):
        self.create_session()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        (self.reports_dir / "initialization_report.json").write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
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
        context_dir = self.workspace_root / ".superlooper" / "context" / self.session_id
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
        state = self.read_state()
        state.update(
            {
                "current_phase": "run",
                "phase_status": "pending",
                "project_category": "springboot",
                "project_version": "springboot-3.x",
                "project_root": ".",
                "project_initialized": True,
                "initialization_report": f".superlooper/reports/{self.session_id}/initialization_report.json",
                "ui_status": "APPROVED",
                "ui_output_dir": f".superlooper/context/{self.session_id}/ui/",
                "ui_artifacts_validated": True,
            }
        )
        self.write_state(state)

    def write_module_split(self):
        (self.manifests_dir / "module-split.json").write_text(
            json.dumps(
                {
                    "project_name": "fixture-demo",
                    "modules": [
                        {
                            "id": "report_export",
                            "name": "Report Export",
                            "description": "实现报表导出控制器。",
                            "referenced_tables": [],
                            "referenced_apis": [],
                            "target_files": ["src/main/java/com/example/controller/ReportExportController.java"],
                            "file_roles": [
                                {
                                    "path": "src/main/java/com/example/controller/ReportExportController.java",
                                    "role": "controller",
                                }
                            ],
                            "requirement_refs": ["REQ-001"],
                            "acceptance_refs": ["AC-001"],
                            "test_focus": ["导出成功路径"],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_upstream_alignment(self, status="PASS", mismatch_count=0, loop_required="false", blocking_decisions=None):
        decisions = blocking_decisions or []
        lines = [
            "```yaml",
            f"session_id: {self.session_id}",
            f"upstream_alignment_status: {status}",
            f"mismatch_count: {mismatch_count}",
            f"loop_required: {loop_required}",
            "loop_target_phase: design",
            "blocking_decisions:",
        ]
        lines.extend(f"  - {item}" for item in decisions)
        lines.append(f"report_path: .superlooper/reports/{self.session_id}/upstream_alignment.md")
        lines.append("```")
        (self.reports_dir / "upstream_alignment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_static_agents(self):
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.repo_root / "agents" / "developer.md", self.agents_dir / "developer.md")
        for agent_name in ("code-reviewer", "system_merger", "tester", "workspace_applier"):
            (self.agents_dir / f"{agent_name}.md").write_text(
                f"---\nname: {agent_name}\ndescription: {agent_name}\n---\n",
                encoding="utf-8",
            )

    def prepare_ready_workspace(self):
        self.write_initialized_state()
        self.write_module_split()
        self.write_upstream_alignment()
        self.write_static_agents()
        manifest = self.run_script("generate_execution_manifest.py", "--workspace-root", str(self.workspace_root), "--session-id", self.session_id)
        self.assertEqual(manifest.returncode, 0, manifest.stderr)
        agents = self.run_script("generate_runtime_agents.py", "--workspace-root", str(self.workspace_root), "--session-id", self.session_id, "--agents-dir", "agents")
        self.assertEqual(agents.returncode, 0, agents.stderr)

    def test_build_execution_summary_writes_report_and_updates_state(self):
        self.prepare_ready_workspace()

        result = self.run_script("build_execution_summary.py", "--workspace-root", str(self.workspace_root), "--session-id", self.session_id)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f".superlooper/reports/{self.session_id}/execution_summary.md", result.stdout)
        report = (self.reports_dir / "execution_summary.md").read_text(encoding="utf-8")
        self.assertIn("execution_summary_status: READY_FOR_APPROVAL", report)
        self.assertIn("module_split_validated: true", report)
        self.assertIn("execution_manifest_validated: true", report)
        state = self.read_state()
        self.assertEqual(state["current_phase"], "run")
        self.assertEqual(state["phase_status"], "waiting_review")
        self.assertEqual(state["execution_summary_status"], "READY_FOR_APPROVAL")
        self.assertEqual(state["execution_summary_report"], f".superlooper/reports/{self.session_id}/execution_summary.md")

    def test_build_execution_summary_report_passes_contract_validator(self):
        self.prepare_ready_workspace()
        result = self.run_script("build_execution_summary.py", "--workspace-root", str(self.workspace_root), "--session-id", self.session_id)
        self.assertEqual(result.returncode, 0, result.stderr)

        validate = self.run_script("validate_miao_contracts.py", "--workspace-root", str(self.workspace_root), "--session-id", self.session_id, "--scope", "execution-summary")

        self.assertEqual(validate.returncode, 0, validate.stderr)
        self.assertIn("契约校验通过", validate.stdout)

    def test_build_execution_summary_blocks_when_upstream_alignment_is_blocked(self):
        self.prepare_ready_workspace()
        self.write_upstream_alignment(status="BLOCKED", blocking_decisions=["DEC-001 需要用户确认模块边界"])

        result = self.run_script("build_execution_summary.py", "--workspace-root", str(self.workspace_root), "--session-id", self.session_id)

        self.assertEqual(result.returncode, 0, result.stderr)
        report = (self.reports_dir / "execution_summary.md").read_text(encoding="utf-8")
        self.assertIn("execution_summary_status: BLOCKED", report)
        self.assertIn("upstream_alignment_status: BLOCKED", report)
        self.assertIn("DEC-001 需要用户确认模块边界", report)
        state = self.read_state()
        self.assertEqual(state["execution_summary_status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
