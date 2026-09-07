import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ApplyToWorkspaceScriptTest(unittest.TestCase):
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

    def run_apply(self, session_id, *extra_args):
        script_path = self.repo_root / "scripts" / "apply_to_workspace.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                session_id,
                *extra_args,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def copy_fixture(self, name):
        shutil.copytree(self.fixtures_root / name / "workspace", self.workspace_root)

    def write_ui_and_design_artifacts(self, session_id):
        ui_dir = self.workspace_root / ".superlooper" / "context" / session_id / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "ui-spec.md").write_text("# UI Spec\n", encoding="utf-8")
        (ui_dir / "page-map.md").write_text("# Page Map\n", encoding="utf-8")
        (ui_dir / "interaction-flow.md").write_text("# Interaction Flow\n", encoding="utf-8")
        (ui_dir / "ui-handoff.md").write_text("# UI Handoff\n", encoding="utf-8")
        (ui_dir / "preview.html").write_text("<!doctype html><html><body>demo</body></html>\n", encoding="utf-8")
        design_dir = self.workspace_root / ".superlooper" / "context" / session_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        (design_dir / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
        (design_dir / "tech-stack.md").write_text("# Tech Stack\n", encoding="utf-8")
        (design_dir / "project-profile.md").write_text("# Project Profile\n", encoding="utf-8")
        (design_dir / "initialization-advice.md").write_text("# Initialization Advice\n", encoding="utf-8")

    def write_initialized_state(self, session_id):
        self.write_ui_and_design_artifacts(session_id)
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

    def runtime_agent_constraints(self, session_id, module_id):
        manifest_path = self.workspace_root / ".superlooper" / "manifests" / session_id / "execution_manifest.json"
        payload = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for node in manifest.get("dag", {}).get("nodes", []):
                if node.get("id") == f"mod_{module_id}" and isinstance(node.get("payload"), dict):
                    payload = node["payload"]
                    break
        fields = [
            "target_files",
            "file_roles",
            "requirement_refs",
            "decision_refs",
            "open_question_refs",
            "acceptance_refs",
            "ui_refs",
            "interaction_refs",
            "component_refs",
            "ui_acceptance_refs",
            "allowed_existing_files",
            "forbidden_files",
            "integration_points",
            "test_commands",
            "overwrite_policy",
            "test_focus",
            "forbidden_inputs",
            "forbidden_outputs",
        ]
        lines = ["## Runtime Module Constraints\n\n", "```yaml\n", f"session_id: {session_id}\n", f"module_id: {module_id}\n"]
        for field in fields:
            lines.append(f"{field}:\n")
            values = payload.get(field)
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, dict):
                    lines.append("  -\n")
                    for child_key, child_value in value.items():
                        lines.append(f"    {child_key}: {child_value}\n")
                else:
                    lines.append(f"  - {value}\n")
        lines.append("```\n")
        return "".join(lines)

    def write_quality_gate_reports(self, session_id, reviewed_modules=None, test_status="PASS"):
        reports_dir = self.workspace_root / ".superlooper" / "reports" / session_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        reviewed = reviewed_modules if reviewed_modules is not None else []
        if reviewed:
            reviewed_yaml = "reviewed_modules:\n" + "".join(f"  - {module}\n" for module in reviewed)
        else:
            reviewed_yaml = "reviewed_modules:\n"
        for module in reviewed:
            agent_name = f"module_{module}"
            agent_content = f"---\nname: {agent_name}\ndescription: test module agent\n---\n\n# {agent_name}\n\n{self.runtime_agent_constraints(session_id, module)}"
            runtime_agent = self.workspace_root / ".superlooper" / "agents" / session_id / f"{agent_name}.md"
            registered_agent = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / session_id / f"{agent_name}.md"
            runtime_agent.parent.mkdir(parents=True, exist_ok=True)
            registered_agent.parent.mkdir(parents=True, exist_ok=True)
            runtime_agent.write_text(agent_content, encoding="utf-8")
            registered_agent.write_text(agent_content, encoding="utf-8")
        (reports_dir / "code_review_report.md").write_text(
            "```yaml\n"
            "code_review_status: PASS\n"
            f"session_id: {session_id}\n"
            "blocker_count: 0\n"
            "blocking_major_count: 0\n"
            f"{reviewed_yaml}"
            f"report_path: .superlooper/reports/{session_id}/code_review_report.md\n"
            "```\n",
            encoding="utf-8",
        )
        (reports_dir / "test_report.md").write_text(
            "```yaml\n"
            f"test_status: {test_status}\n"
            f"session_id: {session_id}\n"
            f"tested_path: .superlooper/merged/{session_id}/\n"
            "test_workspace_path: null\n"
            f"merge_report_path: .superlooper/reports/{session_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{session_id}/test_report.md\n"
            "```\n",
            encoding="utf-8",
        )

    def test_apply_to_workspace_creates_new_file_successfully(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])

        result = self.run_apply("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertTrue(target_file.exists())
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["workspace_validation"]["status"], "PASS")
        self.assertEqual(report["workspace_validation"]["failed_file_count"], 0)
        self.assertEqual(report["workspace_validation"]["checked_file_count"], 2)

    def test_apply_to_workspace_validates_identical_files(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        target_relative = "src/main/java/com/example/controller/ReportExportController.java"
        merge_report = json.loads((self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json").read_text(encoding="utf-8"))
        for item in merge_report["merged_files"]:
            relative = item["path"]
            merged_file = self.workspace_root / ".superlooper" / "merged" / "session_happy" / relative
            target_file = self.workspace_root / relative
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(merged_file, target_file)

        result = self.run_apply("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json").read_text(encoding="utf-8"))
        self.assertIn(target_relative, report["identical_files"])
        checked = {item["path"]: item for item in report["workspace_validation"]["checked_files"]}
        self.assertEqual(checked[target_relative]["action"], "identical")
        self.assertEqual(checked[target_relative]["result"], "PASS")

    def test_apply_to_workspace_validates_overwritten_files(self):
        self.copy_fixture("conflict-path")
        self.write_quality_gate_reports("session_conflict")
        target_relative = "src/main/java/com/example/controller/ReportExportController.java"

        result = self.run_apply("session_conflict", "--overwrite-file", target_relative)

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "apply_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["workspace_validation"]["status"], "PASS")
        self.assertEqual(report["workspace_validation"]["failed_file_count"], 0)
        checked = {item["path"]: item for item in report["workspace_validation"]["checked_files"]}
        self.assertEqual(checked[target_relative]["action"], "overwrite")
        self.assertEqual(checked[target_relative]["result"], "PASS")

    def test_apply_to_workspace_validation_detects_content_mismatch(self):
        sys.path.insert(0, str(self.repo_root / "scripts"))
        from apply_to_workspace import WorkspaceApplyEngine

        source = self.workspace_root / ".superlooper" / "merged" / "session_unit" / "src" / "App.java"
        target = self.workspace_root / "src" / "App.java"
        source.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("class App { int source = 1; }\n", encoding="utf-8")
        target.write_text("class App { int target = 1; }\n", encoding="utf-8")
        engine = WorkspaceApplyEngine(self.workspace_root, session_id="session_unit")
        engine.apply_plan = [{"path": "src/App.java", "source": source, "target": target, "action": "overwrite"}]

        validation = engine._validate_workspace_after_apply()

        self.assertEqual(validation["status"], "FAIL")
        self.assertEqual(validation["failed_file_count"], 1)
        self.assertEqual(validation["failures"][0]["reason"], "content_mismatch")

    def test_apply_to_workspace_writes_conflict_report_when_existing_file_differs(self):
        self.copy_fixture("conflict-path")
        self.write_quality_gate_reports("session_conflict")

        result = self.run_apply("session_conflict")

        self.assertEqual(result.returncode, 2, result.stderr)
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "apply_conflict_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "conflict")
        self.assertEqual(report["conflicts"][0]["reason"], "modify_requires_overwrite_existing")

    def test_apply_to_workspace_keeps_conflict_block_for_brownfield_selective(self):
        self.copy_fixture("conflict-path")
        self.write_initialized_state("session_conflict")
        state_path = self.workspace_root / ".superlooper" / "state" / "session_conflict.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["project_mode"] = "brownfield-selective"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.write_quality_gate_reports("session_conflict")

        result = self.run_apply("session_conflict")

        self.assertEqual(result.returncode, 2, result.stderr)
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "apply_conflict_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "conflict")
        self.assertEqual(report["conflicts"][0]["reason"], "modify_requires_overwrite_existing")

    def test_apply_to_workspace_overwrites_only_named_file_with_overwrite_file(self):
        self.copy_fixture("conflict-path")
        self.write_quality_gate_reports("session_conflict")
        other_relative = "src/main/java/com/example/service/AuditLogService.java"
        merged_other = self.workspace_root / ".superlooper" / "merged" / "session_conflict" / "src" / "main" / "java" / "com" / "example" / "service" / "AuditLogService.java"
        merged_other.parent.mkdir(parents=True, exist_ok=True)
        merged_other.write_text("public class AuditLogService { int merged = 1; }\n", encoding="utf-8")
        target_other = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "service" / "AuditLogService.java"
        target_other.parent.mkdir(parents=True, exist_ok=True)
        target_other.write_text("public class AuditLogService { int workspace = 1; }\n", encoding="utf-8")
        merge_report_path = self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "merge_report.json"
        merge_report = json.loads(merge_report_path.read_text(encoding="utf-8"))
        merge_report["merged_files"].append({"module": "audit_log", "path": other_relative, "strategy": "copy"})
        merge_report["validated_artifacts"].append(str(self.workspace_root / ".superlooper" / "outputs" / "session_conflict" / "audit_log" / "artifact_manifest.json"))
        merge_report_path.write_text(json.dumps(merge_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        audit_output_dir = self.workspace_root / ".superlooper" / "outputs" / "session_conflict" / "audit_log"
        audit_output_dir.mkdir(parents=True, exist_ok=True)
        (audit_output_dir / "src" / "main" / "java" / "com" / "example" / "service").mkdir(parents=True, exist_ok=True)
        (audit_output_dir / "src" / "main" / "java" / "com" / "example" / "service" / "AuditLogService.java").write_text(
            "public class AuditLogService { int merged = 1; }\n",
            encoding="utf-8",
        )
        (audit_output_dir / "artifact_manifest.json").write_text(
            json.dumps(
                {
                    "session_id": "session_conflict",
                    "module_id": "audit_log",
                    "agent": "module_audit_log",
                    "status": "success",
                    "produced_files": [
                        {
                            "path": other_relative,
                            "kind": "code",
                            "operation": "modify",
                            "required_for_merge": True,
                        }
                    ],
                    "verification": {
                        "commands": [
                            {
                                "command": "python -c \"print('ok')\"",
                                "status": "passed",
                                "summary": "ok",
                            }
                        ],
                        "summary": "ok",
                    },
                    "notes": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        target_relative = "src/main/java/com/example/controller/ReportExportController.java"
        target_file = self.workspace_root / target_relative
        original_target = target_file.read_text(encoding="utf-8")

        result = self.run_apply("session_conflict", "--overwrite-file", target_relative)

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(
            target_file.read_text(encoding="utf-8"),
            original_target,
        )
        self.assertEqual(target_other.read_text(encoding="utf-8"), "public class AuditLogService { int workspace = 1; }\n")
        conflict_report = json.loads((self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "apply_conflict_report.json").read_text(encoding="utf-8"))
        self.assertEqual(conflict_report["conflicts"][0]["path"], other_relative)

    def test_apply_to_workspace_overwrite_existing_only_overwrites_modify_files(self):
        self.copy_fixture("conflict-path")
        self.write_quality_gate_reports("session_conflict")
        create_relative = "src/main/java/com/example/controller/NewController.java"
        merged_create = self.workspace_root / ".superlooper" / "merged" / "session_conflict" / create_relative
        merged_create.parent.mkdir(parents=True, exist_ok=True)
        merged_create.write_text("public class NewController { int merged = 1; }\n", encoding="utf-8")
        target_create = self.workspace_root / create_relative
        target_create.parent.mkdir(parents=True, exist_ok=True)
        target_create.write_text("public class NewController { int workspace = 1; }\n", encoding="utf-8")
        merge_report_path = self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "merge_report.json"
        merge_report = json.loads(merge_report_path.read_text(encoding="utf-8"))
        merge_report["merged_files"].append({"module": "report_export", "path": create_relative, "strategy": "copy"})
        merge_report_path.write_text(json.dumps(merge_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifact_path = self.workspace_root / ".superlooper" / "outputs" / "session_conflict" / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["produced_files"].append(
            {
                "path": create_relative,
                "kind": "code",
                "operation": "create",
                "required_for_merge": True,
            }
        )
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        modify_target = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        original_modify = modify_target.read_text(encoding="utf-8")

        result = self.run_apply("session_conflict", "--overwrite-existing")

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(
            modify_target.read_text(encoding="utf-8"),
            original_modify,
        )
        self.assertEqual(target_create.read_text(encoding="utf-8"), "public class NewController { int workspace = 1; }\n")
        conflict_report = json.loads((self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "apply_conflict_report.json").read_text(encoding="utf-8"))
        self.assertEqual(conflict_report["conflicts"][0]["path"], create_relative)
        self.assertEqual(conflict_report["conflicts"][0]["reason"], "target_differs")

    def test_apply_to_workspace_blocks_without_code_review_report(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        reports_dir = self.workspace_root / ".superlooper" / "reports" / "session_happy"
        (reports_dir / "test_report.md").write_text(
            "```yaml\n"
            "test_status: PASS\n"
            "session_id: session_happy\n"
            "tested_path: .superlooper/merged/session_happy/\n"
            "test_workspace_path: null\n"
            "merge_report_path: .superlooper/reports/session_happy/merge_report.json\n"
            "report_path: .superlooper/reports/session_happy/test_report.md\n"
            "```\n",
            encoding="utf-8",
        )

        result = self.run_apply("session_happy")

        self.assertEqual(result.returncode, 1)
        self.assertIn("code_review_report.md", result.stderr)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())
        self.assertFalse((reports_dir / "apply_report.json").exists())

    def test_apply_to_workspace_blocks_failed_test_report(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"], test_status="FAIL")

        result = self.run_apply("session_happy")

        self.assertEqual(result.returncode, 1)
        self.assertIn("test_status 必须为 PASS", result.stderr)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json"
        self.assertFalse(report_path.exists())


if __name__ == "__main__":
    unittest.main()
