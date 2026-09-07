import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GenerateExecutionManifestScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "session_manifest"
        self.manifests_dir = self.workspace_root / ".superlooper" / "manifests" / self.session_id
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.module_split_path = self.manifests_dir / "module-split.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_ui_artifacts(self):
        ui_dir = self.workspace_root / ".superlooper" / "context" / self.session_id / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "ui-spec.md").write_text("# UI Spec\n", encoding="utf-8")
        (ui_dir / "page-map.md").write_text("# Page Map\n", encoding="utf-8")
        (ui_dir / "interaction-flow.md").write_text("# Interaction Flow\n", encoding="utf-8")
        (ui_dir / "ui-handoff.md").write_text("# UI Handoff\n", encoding="utf-8")
        (ui_dir / "preview.html").write_text("<!doctype html><html><body>demo</body></html>\n", encoding="utf-8")

    def write_design_artifacts(self):
        design_dir = self.workspace_root / ".superlooper" / "context" / self.session_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        (design_dir / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
        (design_dir / "tech-stack.md").write_text("# Tech Stack\n", encoding="utf-8")
        (design_dir / "project-profile.md").write_text("# Project Profile\n", encoding="utf-8")
        (design_dir / "initialization-advice.md").write_text("# Initialization Advice\n", encoding="utf-8")

    def write_state(self, project_initialized=True, initialization_report=None, current_phase="run", phase_status="pending", ui_status="APPROVED", ui_artifacts_validated=True):
        state_dir = self.workspace_root / ".superlooper" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        report = initialization_report
        if project_initialized and report is None:
            report = f".superlooper/reports/{self.session_id}/initialization_report.json"
            report_path = self.workspace_root / report
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps({"session_id": self.session_id, "status": "success"}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        self.write_ui_artifacts()
        self.write_design_artifacts()
        (state_dir / f"{self.session_id}.json").write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "workspace_root": str(self.workspace_root.resolve()),
                    "requirement_path": str((self.workspace_root / "requirements.md").resolve()),
                    "current_phase": current_phase,
                    "phase_status": phase_status,
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
                    "project_initialized": project_initialized,
                    "initialization_report": report,
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
                    "ui_status": ui_status,
                    "ui_output_dir": f".superlooper/context/{self.session_id}/ui/",
                    "ui_artifacts_validated": ui_artifacts_validated,
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

    def run_script(self):
        script_path = self.repo_root / "scripts" / "generate_execution_manifest.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                self.session_id,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_module_split(self, modules):
        self.module_split_path.write_text(
            json.dumps({"project_name": "demo", "modules": modules}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_generate_execution_manifest_writes_module_nodes_and_system_nodes(self):
        self.write_module_split(
            [
                {
                    "id": "report_export",
                    "name": "Report Export",
                    "description": "实现导出控制器",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/com/example/controller/ReportExportController.java"],
                    "requirement_refs": ["REQ-001"],
                    "acceptance_refs": ["AC-001"],
                    "ui_refs": ["UI-PAGE-001"],
                    "interaction_refs": ["INT-001"],
                    "component_refs": ["CMP-001"],
                    "ui_acceptance_refs": ["UI-AC-001"],
                    "allowed_existing_files": ["src/main/java/com/example/controller/ReportExportController.java"],
                    "forbidden_files": ["src/main/resources/application.yml"],
                    "integration_points": ["ReportRepository"],
                    "test_commands": ["python -m unittest tests.test_report_export"],
                    "overwrite_policy": "block_by_default",
                    "test_focus": ["导出成功路径"],
                },
                {
                    "id": "audit_log",
                    "name": "Audit Log",
                    "description": "实现审计日志服务",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/com/example/service/AuditLogService.java"],
                },
            ]
        )
        self.write_state()

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        node_map = {node["id"]: node for node in manifest["dag"]["nodes"]}
        self.assertEqual(manifest["session_id"], self.session_id)
        self.assertEqual(manifest["granularity"], "module")
        self.assertIn("mod_report_export", node_map)
        self.assertIn("mod_audit_log", node_map)
        for node_id in (
            "task_code_review",
            "task_merge",
            "task_integration_test",
            "task_apply_to_workspace",
        ):
            self.assertIn(node_id, node_map)

        payload = node_map["mod_report_export"]["payload"]
        self.assertEqual(payload["session_id"], self.session_id)
        self.assertEqual(payload["module_id"], "report_export")
        self.assertEqual(payload["output_dir"], f".superlooper/outputs/{self.session_id}/report_export/")
        self.assertEqual(payload["artifact_manifest_path"], f".superlooper/outputs/{self.session_id}/report_export/artifact_manifest.json")
        self.assertEqual(payload["requirement_refs"], ["REQ-001"])
        self.assertEqual(payload["acceptance_refs"], ["AC-001"])
        self.assertEqual(payload["ui_refs"], ["UI-PAGE-001"])
        self.assertEqual(payload["interaction_refs"], ["INT-001"])
        self.assertEqual(payload["component_refs"], ["CMP-001"])
        self.assertEqual(payload["ui_acceptance_refs"], ["UI-AC-001"])
        self.assertEqual(payload["allowed_existing_files"], ["src/main/java/com/example/controller/ReportExportController.java"])
        self.assertEqual(payload["forbidden_files"], ["src/main/resources/application.yml"])
        self.assertEqual(payload["integration_points"], ["ReportRepository"])
        self.assertEqual(payload["test_commands"], ["python -m unittest tests.test_report_export"])
        self.assertEqual(payload["overwrite_policy"], "block_by_default")
        self.assertEqual(payload["test_focus"], ["导出成功路径"])
        self.assertEqual(payload["forbidden_inputs"], ["原始需求文档", "其他模块 payload", "其他模块输出目录"])
        self.assertEqual(payload["forbidden_outputs"], ["未包含在 target_files 中的文件", "目标项目根目录直接写入"])

    def test_rejects_manifest_generation_before_ui_approval(self):
        self.write_module_split(
            [
                {
                    "id": "main",
                    "name": "Main",
                    "description": "main module",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/App.java"],
                }
            ]
        )
        self.write_state(ui_status="READY_FOR_REVIEW")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ui_status", result.stderr)

    def test_rejects_manifest_generation_before_ui_artifacts_validation(self):
        self.write_module_split(
            [
                {
                    "id": "main",
                    "name": "Main",
                    "description": "main module",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/App.java"],
                }
            ]
        )
        self.write_state(ui_artifacts_validated=False)
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ui_artifacts_validated", result.stderr)

    def test_rejects_manifest_generation_without_ui_artifacts(self):
        self.write_module_split(
            [
                {
                    "id": "main",
                    "name": "Main",
                    "description": "main module",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/App.java"],
                }
            ]
        )
        self.write_state()
        (self.workspace_root / ".superlooper" / "context" / self.session_id / "ui" / "preview.html").unlink()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preview.html", result.stderr)

    def test_rejects_manifest_generation_without_design_artifacts(self):
        self.write_module_split(
            [
                {
                    "id": "main",
                    "name": "Main",
                    "description": "main module",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/App.java"],
                }
            ]
        )
        self.write_state()
        (self.workspace_root / ".superlooper" / "context" / self.session_id / "design" / "project-profile.md").unlink()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project-profile.md", result.stderr)

    def test_rejects_manifest_generation_before_run_phase(self):
        self.write_module_split(
            [
                {
                    "id": "main",
                    "name": "Main",
                    "description": "main module",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/App.java"],
                }
            ]
        )
        self.write_state(current_phase="design", phase_status="waiting_review")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("current_phase", result.stderr)

    def test_rejects_manifest_generation_before_project_initialization(self):
        self.write_module_split(
            [
                {
                    "id": "main",
                    "name": "Main",
                    "description": "main module",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/App.java"],
                }
            ]
        )
        self.write_state(project_initialized=False, initialization_report=None)
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project_initialized", result.stderr)

    def test_generate_execution_manifest_rejects_cross_module_duplicate_target_files(self):
        duplicate_path = "src/main/java/com/example/shared/SharedService.java"
        self.write_module_split(
            [
                {
                    "id": "report_export",
                    "name": "Report Export",
                    "description": "实现导出控制器",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": [duplicate_path],
                },
                {
                    "id": "audit_log",
                    "name": "Audit Log",
                    "description": "实现审计日志服务",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": [duplicate_path],
                },
            ]
        )
        self.write_state()

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("重复 target_files", result.stderr)

    def test_generate_execution_manifest_rejects_duplicate_module_ids(self):
        self.write_module_split(
            [
                {
                    "id": "report_export",
                    "name": "Report Export A",
                    "description": "实现导出控制器",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/com/example/controller/ReportExportController.java"],
                },
                {
                    "id": "report_export",
                    "name": "Report Export B",
                    "description": "实现第二个导出控制器",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": ["src/main/java/com/example/service/ReportExportService.java"],
                },
            ]
        )
        self.write_state()

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("重复 module_id", result.stderr)


if __name__ == "__main__":
    unittest.main()
