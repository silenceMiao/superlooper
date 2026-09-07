import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ValidateContractsScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "session_validate"
        self.runtime_root = self.workspace_root / ".superlooper"
        self.manifests_dir = self.runtime_root / "manifests" / self.session_id
        self.outputs_dir = self.runtime_root / "outputs" / self.session_id
        self.reports_dir = self.runtime_root / "reports" / self.session_id
        self.agents_dir = self.workspace_root / "agents"
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.write_static_agents()
        self.write_module_split()
        self.write_initialized_state()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_validate(self, scope):
        script_path = self.repo_root / "scripts" / "validate_miao_contracts.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                self.session_id,
                "--agents-dir",
                "agents",
                "--scope",
                scope,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_generate_manifest(self):
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

    def run_generate_agents(self):
        script_path = self.repo_root / "scripts" / "generate_runtime_agents.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                self.session_id,
                "--agents-dir",
                "agents",
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_static_agents(self):
        shutil.copy2(self.repo_root / "agents" / "developer.md", self.agents_dir / "developer.md")
        for agent_name in ("code-reviewer", "system_merger", "tester", "workspace_applier"):
            (self.agents_dir / f"{agent_name}.md").write_text(
                f"---\nname: {agent_name}\ndescription: {agent_name}\n---\n",
                encoding="utf-8",
            )

    def write_ui_artifacts(self, project_mode="greenfield", ui_status="READY_FOR_REVIEW", preview=None, handoff=None):
        ui_dir = self.runtime_root / "context" / self.session_id / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "ui-spec.md").write_text(
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            f"ui_status: {ui_status}\n"
            f"prd_path: .superlooper/context/{self.session_id}/prd.md\n"
            f"ui_output_dir: .superlooper/context/{self.session_id}/ui/\n"
            f"preview_path: .superlooper/context/{self.session_id}/ui/preview.html\n"
            f"project_mode: {project_mode}\n"
            "existing_frontend: false\n"
            "page_count: 2\n"
            "interaction_count: 3\n"
            "unresolved_ui_decision_count: 0\n"
            "```\n",
            encoding="utf-8",
        )
        (ui_dir / "page-map.md").write_text("# 页面地图\n", encoding="utf-8")
        (ui_dir / "interaction-flow.md").write_text("# 交互流程\n", encoding="utf-8")
        (ui_dir / "ui-handoff.md").write_text(
            handoff or "# UI Handoff\n\narchitect 消费说明\n\n## 页面到 API\n\n## 页面到模块\n\n## 验收关注点\n",
            encoding="utf-8",
        )
        (ui_dir / "preview.html").write_text(
            preview or "<!doctype html><html><head><title>demo</title></head><body><main>demo</main></body></html>\n",
            encoding="utf-8",
        )
        return ui_dir

    def write_design_artifacts(self):
        design_dir = self.runtime_root / "context" / self.session_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        (design_dir / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
        (design_dir / "tech-stack.md").write_text("# Tech Stack\n", encoding="utf-8")
        (design_dir / "project-profile.md").write_text("# Project Profile\n", encoding="utf-8")
        (design_dir / "initialization-advice.md").write_text("# Initialization Advice\n", encoding="utf-8")

    def write_initialized_state(self):
        self.write_ui_artifacts(ui_status="READY_FOR_REVIEW")
        self.write_design_artifacts()
        report_path = self.reports_dir / "initialization_report.json"
        report_path.write_text(
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
        state_dir = self.runtime_root / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / f"{self.session_id}.json").write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
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
                    "initialization_report": f".superlooper/reports/{self.session_id}/initialization_report.json",
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
                    "ui_output_dir": f".superlooper/context/{self.session_id}/ui/",
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

    def write_dag_state(self, status="success", node_status="success"):
        dag_state_path = self.runtime_root / "state" / f"{self.session_id}.dag.json"
        dag_state_path.parent.mkdir(parents=True, exist_ok=True)
        dag_state_path.write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "dag_status": status,
                    "current_node": "mod_report_export",
                    "execution_order": ["mod_report_export"],
                    "error_summary": "",
                    "manifest_path": f".superlooper/manifests/{self.session_id}/execution_manifest.json",
                    "nodes": {
                        "mod_report_export": {
                            "status": node_status,
                            "agent": "module_report_export",
                            "depends_on": [],
                            "artifact_manifest": f".superlooper/outputs/{self.session_id}/report_export/artifact_manifest.json",
                            "error_summary": "",
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_module_split(self):
        self.module_split_path = self.manifests_dir / "module-split.json"
        self.module_split_path.write_text(
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
                            "target_files": [
                                "src/main/java/com/example/controller/ReportExportController.java"
                            ],
                            "file_roles": [
                                {
                                    "path": "src/main/java/com/example/controller/ReportExportController.java",
                                    "role": "controller",
                                }
                            ],
                            "requirement_refs": ["REQ-001"],
                            "acceptance_refs": ["AC-001"],
                            "ui_refs": ["UI-PAGE-001"],
                            "interaction_refs": ["INT-001"],
                            "component_refs": ["CMP-001"],
                            "ui_acceptance_refs": ["UI-AC-001"],
                            "allowed_existing_files": [
                                "src/main/java/com/example/controller/ReportExportController.java"
                            ],
                            "forbidden_files": ["src/main/resources/application.yml"],
                            "integration_points": ["ReportRepository"],
                            "test_commands": ["python -m unittest tests.test_report_export"],
                            "overwrite_policy": "block_by_default",
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

    def write_success_artifact(self):
        module_dir = self.outputs_dir / "report_export"
        target_file = module_dir / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("public class ReportExportController {}\n", encoding="utf-8")
        artifact_path = module_dir / "artifact_manifest.json"
        artifact_path.write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "module_id": "report_export",
                    "agent": "module_report_export",
                    "status": "success",
                    "produced_files": [
                        {
                            "path": "src/main/java/com/example/controller/ReportExportController.java",
                            "kind": "code",
                            "operation": "create",
                            "required_for_merge": True,
                        }
                    ],
                    "verification": {
                        "commands": [
                            {
                                "command": "python -c \"print('ok')\"",
                                "status": "passed",
                                "summary": "模块校验通过",
                            }
                        ],
                        "summary": "模块校验通过",
                    },
                    "notes": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_test_report(self, status="PASS", body=None):
        report_path = self.reports_dir / "test_report.md"
        if body is None:
            body = (
                "\n"
                "## UI 验收覆盖\n"
                "- UI-AC-001: PASS，已覆盖报表导出入口与导出成功反馈。\n"
            )
        report_path.write_text(
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            f"test_status: {status}\n"
            f"tested_path: .superlooper/merged/{self.session_id}\n"
            f"merge_report_path: .superlooper/reports/{self.session_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.session_id}/test_report.md\n"
            "```\n"
            f"{body}",
            encoding="utf-8",
        )

    def write_requirement_alignment_report(self, status="PASS", unmet=0, unchecked=0, body=None):
        if body is None:
            body = (
                "\n"
                "## UI 验收校对\n"
                "- UI-AC-001: PASS，已校对 test_report.md 覆盖证据，满足 UI 验收要求。\n"
            )
        report_path = self.reports_dir / "requirement_alignment_report.md"
        report_path.write_text(
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            f"requirement_alignment_status: {status}\n"
            f"unmet_requirement_count: {unmet}\n"
            f"unchecked_acceptance_count: {unchecked}\n"
            f"prd_path: .superlooper/context/{self.session_id}/prd.md\n"
            f"test_report_path: .superlooper/reports/{self.session_id}/test_report.md\n"
            f"apply_report_path: .superlooper/reports/{self.session_id}/apply_report.json\n"
            f"report_path: .superlooper/reports/{self.session_id}/requirement_alignment_report.md\n"
            "```\n"
            f"{body}",
            encoding="utf-8",
        )

    def write_change_impact_report(self, affected_module="report_export", affected_artifact=None, status="PASS"):
        artifact = affected_artifact or f".superlooper/outputs/{self.session_id}/report_export/artifact_manifest.json"
        report_path = self.reports_dir / "change_impact_report.md"
        report_path.write_text(
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            f"change_impact_status: {status}\n"
            "rollback_target_phase: run\n"
            "requires_reinitialization: false\n"
            "affected_artifacts:\n"
            f"  - {artifact}\n"
            "affected_modules:\n"
            f"  - {affected_module}\n"
            "local_rerun_allowed: true\n"
            "manual_approval_required: true\n"
            f"report_path: .superlooper/reports/{self.session_id}/change_impact_report.md\n"
            "```\n",
            encoding="utf-8",
        )

    def write_execution_summary(self, status="READY_FOR_APPROVAL", module_split_validated="true", execution_manifest_validated="true", upstream_alignment_status="PASS"):
        report_path = self.reports_dir / "execution_summary.md"
        report_path.write_text(
            "```yaml\n"
            f"execution_summary_status: {status}\n"
            f"session_id: {self.session_id}\n"
            "workflow_mode: standard\n"
            "project_category: springboot\n"
            "project_version: springboot-3.x\n"
            "module_count: 1\n"
            "target_file_count: 1\n"
            "risk_count: 0\n"
            "blocking_decisions:\n"
            f"upstream_alignment_status: {upstream_alignment_status}\n"
            f"module_split_validated: {module_split_validated}\n"
            f"execution_manifest_validated: {execution_manifest_validated}\n"
            f"report_path: .superlooper/reports/{self.session_id}/execution_summary.md\n"
            "```\n",
            encoding="utf-8",
        )

    def write_upstream_alignment(self, status="PASS", mismatch_count=0, loop_required="false", loop_target_phase="design", blocking_decisions=None):
        decisions = blocking_decisions or []
        lines = [
            "```yaml",
            f"session_id: {self.session_id}",
            f"upstream_alignment_status: {status}",
            f"mismatch_count: {mismatch_count}",
            f"loop_required: {loop_required}",
            f"loop_target_phase: {loop_target_phase}",
            "blocking_decisions:",
        ]
        lines.extend(f"  - {item}" for item in decisions)
        lines.append(f"report_path: .superlooper/reports/{self.session_id}/upstream_alignment.md")
        lines.append("```")
        (self.reports_dir / "upstream_alignment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_code_review_report(self, status):
        report_path = self.reports_dir / "code_review_report.md"
        report_path.write_text(
            "```yaml\n"
            f"session_id: {self.session_id}\n"
            f"code_review_status: {status}\n"
            "blocker_count: 0\n"
            "blocking_major_count: 0\n"
            "reviewed_modules:\n"
            "- report_export\n"
            f"report_path: .superlooper/reports/{self.session_id}/code_review_report.md\n"
            "```\n",
            encoding="utf-8",
        )

    def write_apply_report(self, validation=None):
        workspace_validation = validation or {
            "status": "PASS",
            "checked_file_count": 1,
            "matched_file_count": 1,
            "failed_file_count": 0,
            "checked_files": [],
            "failures": [],
        }
        (self.reports_dir / "apply_report.json").write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "status": "success" if workspace_validation["status"] == "PASS" else "failed",
                    "workspace_validation": workspace_validation,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_validate_contracts_accepts_valid_module_split(self):
        result = self.run_validate("module-split")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_rejects_module_split_unknown_field_from_schema(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["unexpected"] = True
        self.module_split_path.write_text(json.dumps(module_split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明字段", result.stderr)

    def test_validate_contracts_rejects_execution_node_unknown_field_from_schema(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"][0]["unexpected"] = True
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明字段", result.stderr)

    def test_validate_contracts_rejects_artifact_unknown_verification_field_from_schema(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["verification"]["unexpected"] = True
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("artifacts")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明字段", result.stderr)

    def test_validate_contracts_rejects_artifact_command_missing_schema_required_field(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        del artifact["verification"]["commands"][0]["summary"]
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("artifacts")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少必填字段", result.stderr)

    def test_validate_contracts_blocks_allowed_existing_files_outside_target_files(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["allowed_existing_files"] = ["src/main/java/com/example/service/ReportExportService.java"]
        self.module_split_path.write_text(json.dumps(module_split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("allowed_existing_files 必须是 target_files 子集", result.stderr)

    def test_validate_contracts_blocks_forbidden_files_target_overlap(self):
        target_file = "src/main/java/com/example/controller/ReportExportController.java"
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["forbidden_files"] = [target_file]
        self.module_split_path.write_text(json.dumps(module_split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden_files 不能与 target_files 重叠", result.stderr)

    def test_validate_contracts_blocks_invalid_overwrite_policy(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["overwrite_policy"] = "overwrite_existing"
        self.module_split_path.write_text(json.dumps(module_split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overwrite_policy 只允许 block_by_default", result.stderr)

    def test_validate_contracts_blocks_module_payload_brownfield_boundary_mismatch(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"][0]["payload"]["allowed_existing_files"] = []
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload.allowed_existing_files 必须与 module-split.modules[].allowed_existing_files 一致", result.stderr)

    def test_validate_contracts_accepts_initialization_report(self):
        result = self.run_validate("initialization-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_accepts_valid_apply_report(self):
        self.write_apply_report()
        result = self.run_validate("apply-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_apply_report_without_workspace_validation(self):
        (self.reports_dir / "apply_report.json").write_text(
            json.dumps({"session_id": self.session_id, "status": "success"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self.run_validate("apply-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace_validation", result.stderr)

    def test_validate_contracts_blocks_failed_apply_workspace_validation(self):
        self.write_apply_report(
            {
                "status": "FAIL",
                "checked_file_count": 1,
                "matched_file_count": 0,
                "failed_file_count": 1,
                "checked_files": [],
                "failures": [{"path": "src/App.java", "reason": "content_mismatch"}],
            }
        )
        result = self.run_validate("apply-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace_validation.status", result.stderr)
        self.assertIn("failed_file_count", result.stderr)
        self.assertIn("failures", result.stderr)

    def test_validate_contracts_accepts_requirement_alignment_report(self):
        self.write_requirement_alignment_report()
        result = self.run_validate("requirement-alignment-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_test_report_missing_ui_acceptance_coverage(self):
        self.write_test_report(body="\n## UI 验收覆盖\n- 未列出 UI 验收编号。\n")

        result = self.run_validate("test-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test_report", result.stderr)
        self.assertIn("UI-AC-001", result.stderr)

    def test_validate_contracts_accepts_test_report_with_ui_acceptance_coverage(self):
        self.write_test_report(
            body=(
                "\n"
                "## UI 验收覆盖\n"
                "- UI-AC-001: PASS，已覆盖导出按钮、导出成功反馈和异常提示。\n"
            )
        )

        result = self.run_validate("test-report")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_requirement_alignment_missing_ui_acceptance_evidence(self):
        self.write_requirement_alignment_report(
            body="\n## UI 验收校对\n- 只声明需求均已校对，但未列出 UI 验收编号。\n"
        )

        result = self.run_validate("requirement-alignment-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_alignment_report", result.stderr)
        self.assertIn("UI-AC-001", result.stderr)

    def test_validate_contracts_accepts_requirement_alignment_with_ui_acceptance_evidence(self):
        self.write_requirement_alignment_report(
            body=(
                "\n"
                "## UI 验收校对\n"
                "- UI-AC-001: PASS，已校对 test_report.md 覆盖证据，满足验收标准。\n"
            )
        )

        result = self.run_validate("requirement-alignment-report")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_accepts_valid_ui_artifacts(self):
        self.write_ui_artifacts()
        result = self.run_validate("ui-artifacts")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_missing_ui_spec(self):
        ui_dir = self.write_ui_artifacts()
        (ui_dir / "ui-spec.md").unlink()
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UI 固定产物不存在", result.stderr)

    def test_validate_contracts_blocks_invalid_ui_status(self):
        self.write_ui_artifacts(ui_status="DONE")
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ui-spec.ui_status", result.stderr)

    def test_validate_contracts_blocks_new_project_mode(self):
        self.write_ui_artifacts(project_mode="new_project")
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("禁止使用 new_project", result.stderr)

    def test_validate_contracts_blocks_remote_preview_resource(self):
        self.write_ui_artifacts(preview="<!doctype html><html><head></head><body><img src='https://example.com/a.png'></body></html>\n")
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preview.html 禁止引用远程资源", result.stderr)

    def test_validate_contracts_blocks_missing_ui_handoff_keyword(self):
        self.write_ui_artifacts(handoff="# UI Handoff\n\n无映射。\n")
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ui-handoff.md 缺少 architect 消费关键词", result.stderr)

    def test_validate_contracts_blocks_failed_requirement_alignment_counts(self):
        self.write_requirement_alignment_report(status="PASS", unmet=1, unchecked=0)
        result = self.run_validate("requirement-alignment-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unmet_requirement_count", result.stderr)

    def test_validate_contracts_accepts_valid_change_impact_report(self):
        self.write_change_impact_report()
        result = self.run_validate("change-impact-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_accepts_valid_execution_summary(self):
        self.write_execution_summary()
        result = self.run_validate("execution-summary")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_unready_execution_summary(self):
        self.write_execution_summary(upstream_alignment_status="FAIL")
        result = self.run_validate("execution-summary")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("upstream_alignment_status", result.stderr)

    def test_validate_contracts_accepts_valid_upstream_alignment(self):
        self.write_upstream_alignment()
        result = self.run_validate("upstream-alignment")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_invalid_upstream_alignment_loop(self):
        self.write_upstream_alignment(status="FAIL", mismatch_count=1, loop_required="false")
        result = self.run_validate("upstream-alignment")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("loop_required", result.stderr)

    def test_validate_contracts_blocks_blocked_upstream_alignment_without_decision(self):
        self.write_upstream_alignment(status="BLOCKED")
        result = self.run_validate("upstream-alignment")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("blocking_decisions", result.stderr)

    def test_validate_contracts_blocks_unknown_change_impact_module(self):
        self.write_change_impact_report(affected_module="missing_module")
        result = self.run_validate("change-impact-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不存在于 module-split", result.stderr)

    def test_validate_contracts_blocks_unsafe_change_impact_artifact(self):
        self.write_change_impact_report(affected_artifact="../outside.txt")
        result = self.run_validate("change-impact-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("affected_artifacts", result.stderr)

    def test_validate_contracts_accepts_valid_dag_state(self):
        self.write_dag_state()
        result = self.run_validate("dag-state")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_invalid_dag_node_status(self):
        self.write_dag_state(node_status="done")
        result = self.run_validate("dag-state")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dag-state.nodes.mod_report_export.status", result.stderr)

    def test_validate_contracts_accepts_valid_execution_manifest(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)

        result = self.run_validate("execution")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_dynamic_agent_missing_constraints(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_path = self.runtime_root / "agents" / self.session_id / "module_report_export.md"
        content = runtime_path.read_text(encoding="utf-8")
        runtime_path.write_text(content.split("## Runtime Module Constraints", 1)[0], encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("动态 agent 缺少模块约束块", result.stderr)

    def test_validate_contracts_blocks_dynamic_agent_wrong_module_id_constraint(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_path = self.runtime_root / "agents" / self.session_id / "module_report_export.md"
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.session_id / "module_report_export.md"
        for path in (runtime_path, registered_path):
            content = path.read_text(encoding="utf-8")
            path.write_text(content.replace("module_id: report_export", "module_id: wrong_module"), encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("动态 agent 模块约束 module_id 必须为 report_export", result.stderr)

    def test_validate_contracts_blocks_module_payload_missing_session_id(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["dag"]["nodes"][0]["payload"]["session_id"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload 缺少模块执行锚点：session_id", result.stderr)

    def test_validate_contracts_blocks_module_payload_missing_traceability_anchor(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["dag"]["nodes"][0]["payload"]["requirement_refs"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload 缺少模块执行锚点：requirement_refs", result.stderr)

    def test_validate_contracts_blocks_module_payload_missing_file_roles_anchor(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["dag"]["nodes"][0]["payload"]["file_roles"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload 缺少模块执行锚点：file_roles", result.stderr)

    def test_validate_contracts_blocks_module_payload_ui_traceability_mismatch(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"][0]["payload"]["ui_refs"] = ["UI-PAGE-999"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload.ui_refs 必须与 module-split.modules[].ui_refs 一致", result.stderr)

    def test_validate_contracts_blocks_module_payload_string(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"][0]["payload"] = "实现 report_export 模块"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload 必须是 object", result.stderr)

    def test_validate_contracts_blocks_failed_or_blocked_artifact(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["status"] = "blocked"
        artifact["verification"]["summary"] = "等待设计决策"
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status 为 blocked", result.stderr)

    def test_validate_contracts_blocks_undeclared_artifact_file(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        extra_file = self.outputs_dir / "report_export" / "src" / "main" / "java" / "com" / "example" / "controller" / "Extra.java"
        extra_file.parent.mkdir(parents=True, exist_ok=True)
        extra_file.write_text("public class Extra {}\n", encoding="utf-8")

        result = self.run_validate("artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明文件", result.stderr)

    def test_validate_contracts_blocks_invalid_report_status_block(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_code_review_report("UNKNOWN")

        result = self.run_validate("code-review-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code_review_status", result.stderr)


if __name__ == "__main__":
    unittest.main()
