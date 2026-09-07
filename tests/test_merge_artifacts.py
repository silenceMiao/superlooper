import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MergeArtifactsScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.fixtures_root = self.repo_root / "tests" / "fixtures"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name) / "workspace"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_generate_manifest(self, session_id):
        script_path = self.repo_root / "scripts" / "generate_execution_manifest.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                session_id,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_merge(self, session_id):
        script_path = self.repo_root / "scripts" / "merge_artifacts.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                session_id,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

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
                    "ui_output_dir": f".superlooper/context/{session_id}/ui/",
                    "ui_artifacts_validated": True,
                    "design_revision": 0,
                    "change_request_count": 0,
                    "active_feedback_report": None,
                    "change_impact_report": None,
                    "invalidated_artifacts": [],
                    "rollback_target_phase": None,
                    "last_user_input_text": None,
                    "last_user_canonical_action": None,
                    "pending_user_choice": None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_conflict_manifest(self, session_id):
        manifest_dir = self.workspace_root / ".superlooper" / "manifests" / session_id
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "execution_manifest.json").write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "granularity": "module",
                    "context": {
                        "prd_path": f".superlooper/context/{session_id}/prd.md",
                        "design_docs_path": f".superlooper/context/{session_id}/design/",
                        "module_split_path": f".superlooper/manifests/{session_id}/module-split.json",
                        "agents_path": "agents/",
                        "runtime_agents_path": f".superlooper/agents/{session_id}/",
                        "registered_agents_path": f".claude/agents/generated/superlooper/{session_id}/",
                        "outputs_path": f".superlooper/outputs/{session_id}/",
                        "merged_path": f".superlooper/merged/{session_id}/",
                        "reports_path": f".superlooper/reports/{session_id}/",
                    },
                    "dag": {
                        "nodes": [
                            {
                                "id": "mod_report_export",
                                "agent": "module_report_export",
                                "depends_on": [],
                                "payload": {"module_id": "report_export"},
                            },
                            {
                                "id": "task_code_review",
                                "agent": "code-reviewer",
                                "depends_on": ["mod_report_export"],
                                "payload": "review",
                            },
                            {
                                "id": "task_merge",
                                "agent": "system_merger",
                                "depends_on": ["task_code_review"],
                                "payload": "merge",
                            },
                            {
                                "id": "task_integration_test",
                                "agent": "tester",
                                "depends_on": ["task_merge"],
                                "payload": "test",
                            },
                            {
                                "id": "task_apply_to_workspace",
                                "agent": "workspace_applier",
                                "depends_on": ["task_integration_test"],
                                "payload": "apply",
                            },
                        ]
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_merge_artifacts_happy_path_merges_successfully(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "success")
        self.assertEqual(sorted(report["modules"]), ["audit_log", "report_export"])
        merged_file = self.workspace_root / ".superlooper" / "merged" / "session_happy" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertTrue(merged_file.exists())

    def test_merge_artifacts_conflict_path_writes_conflict_report(self):
        self.copy_fixture("conflict-path")
        self.write_conflict_manifest("session_conflict")
        output_file = self.workspace_root / ".superlooper" / "outputs" / "session_conflict" / "report_export" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("public class ReportExportController { int module = 1; }\n", encoding="utf-8")

        result = self.run_merge("session_conflict")

        self.assertEqual(result.returncode, 2, result.stderr)
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "conflict_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "conflict")
        self.assertEqual(report["conflicts"][0]["reason"], "same_path_different_content")

    def test_merge_artifacts_rejects_undeclared_files(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        extra_file = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export" / "src" / "main" / "java" / "com" / "example" / "controller" / "Extra.java"
        extra_file.parent.mkdir(parents=True, exist_ok=True)
        extra_file.write_text("public class Extra {}\n", encoding="utf-8")

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 1)
        self.assertIn("未声明文件", result.stderr)

    def test_merge_artifacts_returns_conflict_for_same_path_with_different_content(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        duplicate_dir = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export_copy"
        original_dir = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export"
        shutil.copytree(original_dir, duplicate_dir)
        artifact_path = duplicate_dir / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["module_id"] = "report_export_copy"
        artifact["agent"] = "module_report_export_copy"
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        target_file = duplicate_dir / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        target_file.write_text("public class ReportExportController { int duplicated = 1; }\n", encoding="utf-8")
        manifest_path = self.workspace_root / ".superlooper" / "manifests" / "session_happy" / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"].insert(
            1,
            {
                "id": "mod_report_export_copy",
                "agent": "module_report_export_copy",
                "depends_on": [],
                "payload": {"module_id": "report_export_copy"},
            },
        )
        for node in manifest["dag"]["nodes"]:
            if node["id"] == "task_code_review":
                node["depends_on"] = ["mod_audit_log", "mod_report_export", "mod_report_export_copy"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 2, result.stderr)
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "conflict_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "conflict")
        self.assertEqual(report["conflicts"][0]["reason"], "same_path_different_content")


if __name__ == "__main__":
    unittest.main()
