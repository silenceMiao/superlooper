import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ApplyToWorkspaceScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.fixtures_root = self.repo_root / "tests" / "fixtures"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name) / "workspace"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_generate_manifest(self, task_id):
        script_path = self.repo_root / "scripts" / "generate_execution_manifest.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                task_id,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_merge(self, task_id):
        script_path = self.repo_root / "scripts" / "merge_artifacts.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                task_id,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_apply(self, task_id, *extra_args):
        script_path = self.repo_root / "scripts" / "apply_to_workspace.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                task_id,
                *extra_args,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def copy_fixture(self, name):
        shutil.copytree(self.fixtures_root / name / "workspace", self.workspace_root)

    def compute_fixture_tree_digest(self, root):
        entries = []
        for path in sorted(
            (path for path in root.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(root).as_posix(),
        ):
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        payload = json.dumps(
            entries,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def refresh_merge_report_digest(self, task_id):
        merged_dir = self.workspace_root / ".superlooper" / "merged" / task_id
        report_path = self.workspace_root / ".superlooper" / "reports" / task_id / "merge_report.json"
        if not merged_dir.is_dir() or not report_path.is_file():
            return
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["snapshot_digest"] = self.compute_fixture_tree_digest(merged_dir)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def create_directory_link(self, link_path, target_path):
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            return
        link_path.symlink_to(target_path, target_is_directory=True)

    def write_ui_and_design_artifacts(self, task_id):
        ui_dir = self.workspace_root / ".superlooper" / "context" / task_id / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "ui-spec.md").write_text("# UI Spec\n", encoding="utf-8")
        (ui_dir / "page-map.md").write_text("# Page Map\n", encoding="utf-8")
        (ui_dir / "interaction-flow.md").write_text("# Interaction Flow\n", encoding="utf-8")
        (ui_dir / "ui-handoff.md").write_text("# UI Handoff\n", encoding="utf-8")
        (ui_dir / "preview.html").write_text("<!doctype html><html><body>demo</body></html>\n", encoding="utf-8")
        (self.workspace_root / ".superlooper" / "context" / task_id / "prd.md").write_text(
            "# PRD\n\n### REQ-001：应用合并产物\n\n### AC-001：应用成功\n",
            encoding="utf-8",
        )
        design_dir = self.workspace_root / ".superlooper" / "context" / task_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        (design_dir / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
        (design_dir / "tech-stack.md").write_text("# Tech Stack\n", encoding="utf-8")
        (design_dir / "project-profile.md").write_text("# Project Profile\n", encoding="utf-8")
        (design_dir / "initialization-advice.md").write_text("# Initialization Advice\n", encoding="utf-8")

    def write_initialized_state(self, task_id):
        self.write_ui_and_design_artifacts(task_id)
        reports_dir = self.workspace_root / ".superlooper" / "reports" / task_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "initialization_report.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
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
        (state_dir / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
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
                    "initialization_report": f".superlooper/reports/{task_id}/initialization_report.json",
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
                    "ui_output_dir": f".superlooper/context/{task_id}/ui/",
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
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def runtime_agent_constraints(self, task_id, module_id):
        manifest_path = self.workspace_root / ".superlooper" / "manifests" / task_id / "execution_manifest.json"
        payload = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for node in manifest.get("dag", {}).get("nodes", []):
                if node.get("id") == f"mod_{module_id}" and isinstance(node.get("payload"), dict):
                    payload = node["payload"]
                    break
        fields = [
            "task_id",
            "module_id",
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
        constraints = {
            "task_id": task_id,
            "module_id": module_id,
        }
        for field in fields:
            if field in constraints:
                continue
            if field == "overwrite_policy":
                constraints[field] = payload.get(field) or "block_by_default"
            else:
                constraints[field] = payload.get(field, [])
        lines = ["## Runtime Module Constraints\n\n", "```yaml\n"]
        for field in fields:
            value = json.dumps(constraints[field], ensure_ascii=False, separators=(",", ":"))
            lines.append(f"{field}: {value}\n")
        lines.append("```\n")
        return "".join(lines)

    def ensure_quality_gate_manifest(self, task_id, reviewed_modules):
        manifest_path = (
            self.workspace_root
            / ".superlooper"
            / "manifests"
            / task_id
            / "execution_manifest.json"
        )
        if manifest_path.exists():
            return
        state_path = self.workspace_root / ".superlooper" / "state" / f"{task_id}.json"
        if not state_path.exists():
            self.write_initialized_state(task_id)
        modules = []
        for module_id in reviewed_modules:
            artifact_path = (
                self.workspace_root
                / ".superlooper"
                / "outputs"
                / task_id
                / module_id
                / "artifact_manifest.json"
            )
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            target_files = [
                item["path"]
                for item in artifact.get("produced_files", [])
                if isinstance(item, dict) and isinstance(item.get("path"), str)
            ]
            modules.append(
                {
                    "id": module_id,
                    "name": module_id.replace("_", " ").title(),
                    "description": f"Apply fixture module {module_id}.",
                    "referenced_tables": [],
                    "referenced_apis": [],
                    "target_files": target_files,
                    "file_roles": [
                        {"path": path, "role": "other"}
                        for path in target_files
                    ],
                    "requirement_refs": ["REQ-001"],
                    "acceptance_refs": ["AC-001"],
                    "test_focus": ["应用成功路径"],
                }
            )
        module_split_path = manifest_path.parent / "module-split.json"
        module_split_path.parent.mkdir(parents=True, exist_ok=True)
        module_split_path.write_text(
            json.dumps(
                {"project_name": "apply-fixture", "modules": modules},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        agents_dir = self.workspace_root / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for agent_name in (
            "developer",
            "code-reviewer",
            "system_merger",
            "tester",
            "workspace_applier",
        ):
            shutil.copy2(
                self.repo_root / "agents" / f"{agent_name}.md",
                agents_dir / f"{agent_name}.md",
            )
        result = self.run_generate_manifest(task_id)
        self.assertEqual(result.returncode, 0, result.stderr)

    def write_quality_gate_reports(self, task_id, reviewed_modules=None, test_status="PASS", code_review_status="PASS"):
        prd_path = self.workspace_root / ".superlooper" / "context" / task_id / "prd.md"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        if not prd_path.exists():
            prd_path.write_text(
                "# PRD\n\n### REQ-001：应用合并产物\n\n### AC-001：应用成功\n",
                encoding="utf-8",
            )
        reports_dir = self.workspace_root / ".superlooper" / "reports" / task_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        if reviewed_modules is None:
            merge_report_path = reports_dir / "merge_report.json"
            merge_report = json.loads(merge_report_path.read_text(encoding="utf-8"))
            reviewed = sorted(
                {
                    item["module"]
                    for item in merge_report.get("merged_files", [])
                    if isinstance(item, dict) and isinstance(item.get("module"), str)
                }
            )
        else:
            reviewed = reviewed_modules
        if code_review_status == "PASS":
            self.ensure_quality_gate_manifest(task_id, reviewed)
        if reviewed:
            reviewed_yaml = "reviewed_modules:\n" + "".join(f"  - {module}\n" for module in reviewed)
        else:
            reviewed_yaml = "reviewed_modules:\n"
        for module in reviewed:
            agent_name = f"module_{module}"
            constraints = self.runtime_agent_constraints(task_id, module)
            agent_content = f"---\nname: {agent_name}\ndescription: test module agent\n---\n\n# {agent_name}\n\n{constraints}"
            task_hash = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:16]
            registered_name = f"{agent_name}__task_{task_hash}"
            registered_content = f"---\nname: {registered_name}\ndescription: test module agent\n---\n\n# {agent_name}\n\n{constraints}"
            runtime_agent = self.workspace_root / ".superlooper" / "agents" / task_id / f"{agent_name}.md"
            registered_agent = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / task_id / f"{agent_name}.md"
            runtime_agent.parent.mkdir(parents=True, exist_ok=True)
            registered_agent.parent.mkdir(parents=True, exist_ok=True)
            runtime_agent.write_text(agent_content, encoding="utf-8")
            registered_agent.write_text(registered_content, encoding="utf-8")
        (reports_dir / "code_review_report.md").write_text(
            "```yaml\n"
            f"code_review_status: {code_review_status}\n"
            f"task_id: {task_id}\n"
            "blocker_count: 0\n"
            "blocking_major_count: 0\n"
            f"{reviewed_yaml}"
            f"report_path: .superlooper/reports/{task_id}/code_review_report.md\n"
            "```\n",
            encoding="utf-8",
        )
        (reports_dir / "test_report.md").write_text(
            "```yaml\n"
            f"test_status: {test_status}\n"
            f"task_id: {task_id}\n"
            f"tested_path: .superlooper/merged/{task_id}/\n"
            "test_workspace_path: null\n"
            f"merge_report_path: .superlooper/reports/{task_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{task_id}/test_report.md\n"
            "```\n"
            "```json\n"
            "{\n"
            "  \"commands\": [{\"command\": \"python -m unittest\", \"exit_code\": 0, \"result\": \"PASS\", \"key_output\": \"tests passed\"}],\n"
            "  \"requirement_coverage\": [\n"
            "    {\"id\": \"REQ-001\", \"status\": \"PASS\", \"evidence\": \"apply path verified\"},\n"
            "    {\"id\": \"AC-001\", \"status\": \"PASS\", \"evidence\": \"success path verified\"}\n"
            "  ]\n"
            "}\n"
            "```\n",
            encoding="utf-8",
        )
        self.refresh_merge_report_digest(task_id)

    def load_apply_engine(self):
        scripts_dir = str(self.repo_root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from apply_to_workspace import WorkspaceApplyEngine

        return WorkspaceApplyEngine

    def add_create_file_to_conflict_fixture(self):
        relative = "src/main/java/com/example/controller/NewController.java"
        merged_file = self.workspace_root / ".superlooper" / "merged" / "session_conflict" / relative
        merged_file.parent.mkdir(parents=True, exist_ok=True)
        merged_file.write_text("public class NewController {}\n", encoding="utf-8")
        merge_report_path = self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "merge_report.json"
        merge_report = json.loads(merge_report_path.read_text(encoding="utf-8"))
        merge_report["merged_files"].append(
            {"module": "report_export", "path": relative, "strategy": "copy"}
        )
        merge_report_path.write_text(
            json.dumps(merge_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact_path = self.workspace_root / ".superlooper" / "outputs" / "session_conflict" / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["produced_files"].append(
            {
                "path": relative,
                "kind": "code",
                "operation": "create",
                "required_for_merge": True,
            }
        )
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.refresh_merge_report_digest("session_conflict")
        return relative

    def test_apply_to_workspace_rejects_windows_equivalent_protected_root(self):
        self.workspace_root.mkdir(parents=True)
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(self.workspace_root, task_id="session_safe_path")

        self.assertFalse(engine._safe_relative_path(".GIT\\config"))
        self.assertFalse(engine._safe_relative_path(".git./config"))

    def test_apply_to_workspace_rejects_merged_source_outside_merged_directory(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        merged_dir = self.workspace_root / ".superlooper" / "merged" / "session_happy"
        source_root = merged_dir / "src"
        outside_source = Path(self.temp_dir.name) / "outside-merged-source"
        shutil.copytree(source_root, outside_source)
        outside_file = outside_source / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        outside_content = outside_file.read_bytes()
        shutil.rmtree(source_root)
        self.create_directory_link(source_root, outside_source)

        result = self.run_apply("session_happy")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("授权目录", result.stderr)
        self.assertEqual(outside_file.read_bytes(), outside_content)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())

    def test_apply_to_workspace_rejects_target_through_outside_junction(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        outside_target = Path(self.temp_dir.name) / "outside-workspace-target"
        outside_target.mkdir()
        workspace_source_root = self.workspace_root / "src"
        self.create_directory_link(workspace_source_root, outside_target)
        escaped_file = outside_target / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"

        result = self.run_apply("session_happy")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("授权目录", result.stderr)
        self.assertFalse(escaped_file.exists())

    def test_apply_to_workspace_reports_partial_rollback_when_overwrite_backup_is_missing(self):
        self.workspace_root.mkdir(parents=True)
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(self.workspace_root, task_id="session_rollback")
        target = self.workspace_root / "src" / "App.java"
        target.parent.mkdir(parents=True)
        target.write_text("new content\n", encoding="utf-8")
        backup_dir = self.workspace_root / ".superlooper" / "reports" / "session_rollback" / ".apply-backup.test"
        backup_dir.mkdir(parents=True)
        missing_backup = backup_dir / "src" / "App.java"

        rollback = engine._rollback_apply(
            [
                {
                    "path": "src/App.java",
                    "action": "overwrite",
                    "target": target,
                    "backup": missing_backup,
                }
            ],
            [],
            backup_dir,
        )

        self.assertEqual(rollback["status"], "partial")
        self.assertTrue(rollback["failures"])
        self.assertTrue(backup_dir.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "new content\n")

    def test_apply_to_workspace_reports_partial_rollback_for_escaped_target(self):
        self.workspace_root.mkdir(parents=True)
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(self.workspace_root, task_id="session_rollback")
        outside_target = Path(self.temp_dir.name) / "outside-rollback-target"
        outside_target.mkdir()
        escaped_file = outside_target / "App.java"
        escaped_file.write_text("outside sentinel\n", encoding="utf-8")
        sentinel_content = escaped_file.read_bytes()
        workspace_source_root = self.workspace_root / "src"
        self.create_directory_link(workspace_source_root, outside_target)
        backup_dir = self.workspace_root / ".superlooper" / "reports" / "session_rollback" / ".apply-backup.test"
        backup_dir.mkdir(parents=True)

        rollback = engine._rollback_apply(
            [
                {
                    "path": "src/App.java",
                    "action": "create",
                    "target": workspace_source_root / "App.java",
                    "backup": None,
                }
            ],
            [],
            backup_dir,
        )

        self.assertEqual(rollback["status"], "partial")
        self.assertTrue(rollback["failures"])
        self.assertTrue(backup_dir.exists())
        self.assertEqual(escaped_file.read_bytes(), sentinel_content)

    def test_apply_to_workspace_blocks_failed_code_review(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports(
            "session_happy",
            ["report_export", "audit_log"],
            code_review_status="FAIL",
        )

        result = self.run_apply("session_happy")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code_review_status", result.stderr)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())

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
        merge_report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["snapshot_digest"], merge_report["snapshot_digest"])

    def test_apply_to_workspace_rejects_tampered_merged_snapshot_before_workspace_write(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        merged_file = self.workspace_root / ".superlooper" / "merged" / "session_happy" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        merged_file.write_text("tampered\n", encoding="utf-8")
        reports_dir = self.workspace_root / ".superlooper" / "reports" / "session_happy"
        (reports_dir / "apply_report.json").write_text(
            json.dumps({"status": "success", "task_id": "session_happy"}) + "\n",
            encoding="utf-8",
        )

        result = self.run_apply("session_happy")

        self.assertEqual(result.returncode, 1)
        self.assertIn("snapshot_digest", result.stderr)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())
        apply_report_path = reports_dir / "apply_report.json"
        if apply_report_path.exists():
            self.assertNotEqual(
                json.loads(apply_report_path.read_text(encoding="utf-8")).get("status"),
                "success",
            )

    def test_apply_to_workspace_rolls_back_when_validation_returns_fail(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(self.workspace_root, task_id="session_happy")
        validation = {
            "status": "FAIL",
            "checked_file_count": 2,
            "matched_file_count": 1,
            "failed_file_count": 1,
            "checked_files": [],
            "failures": [{"path": "src/failure", "reason": "content_mismatch"}],
        }

        with mock.patch.object(engine, "_validate_workspace_after_apply", return_value=validation):
            result = engine.run()

        self.assertEqual(result, 1)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["rollback"]["status"], "success")

    def test_apply_to_workspace_rolls_back_when_validation_raises_oserror(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(self.workspace_root, task_id="session_happy")

        with mock.patch.object(engine, "_validate_workspace_after_apply", side_effect=OSError("injected validation failure")):
            result = engine.run()

        self.assertEqual(result, 1)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["rollback"]["status"], "success")
        self.assertEqual(report["workspace_validation"]["status"], "FAIL")

    def test_apply_to_workspace_rolls_back_when_success_report_publish_fails(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(self.workspace_root, task_id="session_happy")
        original_replace = os.replace
        replace_count = 0

        def fail_first_replace(source, target):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 1:
                raise OSError("injected success report publish failure")
            return original_replace(source, target)

        with mock.patch("apply_to_workspace.os.replace", side_effect=fail_first_replace):
            result = engine.run()

        self.assertEqual(result, 1)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["rollback"]["status"], "success")

    def test_apply_to_workspace_keeps_overwrite_backup_until_success_report_is_published(self):
        self.copy_fixture("conflict-path")
        self.write_quality_gate_reports("session_conflict")
        target_relative = "src/main/java/com/example/controller/ReportExportController.java"
        target_file = self.workspace_root / target_relative
        original_bytes = target_file.read_bytes()
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(
            self.workspace_root,
            task_id="session_conflict",
            overwrite_files=[target_relative],
        )
        original_replace = os.replace
        replace_count = 0

        def fail_first_replace(source, target):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 1:
                raise OSError("injected success report publish failure")
            return original_replace(source, target)

        with mock.patch("apply_to_workspace.os.replace", side_effect=fail_first_replace):
            result = engine.run()

        self.assertEqual(result, 1)
        self.assertEqual(target_file.read_bytes(), original_bytes)
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "apply_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["rollback"]["status"], "success")

    def test_apply_to_workspace_rolls_back_created_files_after_copy_failure(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(self.workspace_root, task_id="session_happy")
        original_copy2 = shutil.copy2
        copy_count = 0

        def fail_second_copy(source, target, *args, **kwargs):
            nonlocal copy_count
            copy_count += 1
            if copy_count == 2:
                raise OSError("injected create failure")
            return original_copy2(source, target, *args, **kwargs)

        with mock.patch("apply_to_workspace.shutil.copy2", side_effect=fail_second_copy):
            try:
                result = engine.run()
            except OSError as exc:
                self.fail(f"apply I/O failure escaped without rollback: {exc}")

        self.assertEqual(result, 1)
        controller = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        service = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "service" / "AuditLogService.java"
        self.assertFalse(controller.exists())
        self.assertFalse(service.exists())
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["rollback"]["status"], "success")
        self.assertEqual(report["workspace_validation"]["status"], "FAIL")

    def test_apply_to_workspace_restores_overwrite_after_later_copy_failure(self):
        self.copy_fixture("conflict-path")
        self.write_quality_gate_reports("session_conflict")
        create_relative = self.add_create_file_to_conflict_fixture()
        target_relative = "src/main/java/com/example/controller/ReportExportController.java"
        target_file = self.workspace_root / target_relative
        original_bytes = target_file.read_bytes()
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(
            self.workspace_root,
            task_id="session_conflict",
            overwrite_files=[target_relative],
        )
        original_copy2 = shutil.copy2
        copy_count = 0

        def fail_second_copy(source, target, *args, **kwargs):
            nonlocal copy_count
            copy_count += 1
            if copy_count == 2:
                raise OSError("injected create failure")
            return original_copy2(source, target, *args, **kwargs)

        with mock.patch("apply_to_workspace.shutil.copy2", side_effect=fail_second_copy):
            try:
                result = engine.run()
            except OSError as exc:
                self.fail(f"apply I/O failure escaped without rollback: {exc}")

        self.assertEqual(result, 1)
        self.assertEqual(target_file.read_bytes(), original_bytes)
        self.assertFalse((self.workspace_root / create_relative).exists())
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "apply_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["rollback"]["status"], "success")

    def test_apply_to_workspace_reports_partial_rollback_when_restore_fails(self):
        self.copy_fixture("conflict-path")
        self.write_quality_gate_reports("session_conflict")
        self.add_create_file_to_conflict_fixture()
        target_relative = "src/main/java/com/example/controller/ReportExportController.java"
        WorkspaceApplyEngine = self.load_apply_engine()
        engine = WorkspaceApplyEngine(
            self.workspace_root,
            task_id="session_conflict",
            overwrite_files=[target_relative],
        )
        original_copy2 = shutil.copy2
        original_move = shutil.move
        copy_count = 0
        move_count = 0

        def fail_second_copy(source, target, *args, **kwargs):
            nonlocal copy_count
            copy_count += 1
            if copy_count == 2:
                raise OSError("injected create failure")
            return original_copy2(source, target, *args, **kwargs)

        def fail_restore(source, target, *args, **kwargs):
            nonlocal move_count
            move_count += 1
            if move_count == 2:
                raise OSError("injected restore failure")
            return original_move(source, target, *args, **kwargs)

        with mock.patch("apply_to_workspace.shutil.copy2", side_effect=fail_second_copy), mock.patch(
            "apply_to_workspace.shutil.move",
            side_effect=fail_restore,
        ):
            try:
                result = engine.run()
            except OSError as exc:
                self.fail(f"partial rollback was not reported: {exc}")

        self.assertEqual(result, 1)
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_conflict" / "apply_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["rollback"]["status"], "partial")
        self.assertTrue(report["rollback"]["failures"])
        self.assertTrue(Path(report["rollback"]["backup_dir"]).exists())

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
        engine = WorkspaceApplyEngine(self.workspace_root, task_id="session_unit")
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
        self.assertEqual(
            list(report_path.parent.glob(".apply-backup.*")),
            [],
        )

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
                    "task_id": "session_conflict",
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
        self.refresh_merge_report_digest("session_conflict")

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
        self.refresh_merge_report_digest("session_conflict")

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
            "task_id: session_happy\n"
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

    def test_apply_to_workspace_accepts_legacy_inputs_without_rewriting(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        merge_report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json"
        merge_report = json.loads(merge_report_path.read_text(encoding="utf-8"))
        merge_report["session_id"] = merge_report.pop("task_id")
        merge_report_path.write_text(json.dumps(merge_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifact_paths = [Path(path) for path in merge_report["validated_artifacts"]]

        result = self.run_apply("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_happy" / "apply_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["task_id"], "session_happy")
        self.assertNotIn("session_id", report)
        persisted_merge_report = json.loads(merge_report_path.read_text(encoding="utf-8"))
        self.assertIn("session_id", persisted_merge_report)
        self.assertNotIn("task_id", persisted_merge_report)
        for artifact_path in artifact_paths:
            persisted_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertIn("session_id", persisted_artifact)
            self.assertNotIn("task_id", persisted_artifact)

    def test_apply_to_workspace_rejects_dual_merge_report_identity(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_quality_gate_reports("session_happy", ["report_export", "audit_log"])
        merge_report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json"
        merge_report = json.loads(merge_report_path.read_text(encoding="utf-8"))
        merge_report["session_id"] = "session_happy"
        merge_report_path.write_text(json.dumps(merge_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_apply("session_happy")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不能同时包含 task_id 和 legacy session_id", result.stderr)
        target_file = self.workspace_root / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        self.assertFalse(target_file.exists())


if __name__ == "__main__":
    unittest.main()
