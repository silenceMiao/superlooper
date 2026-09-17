import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class MergeArtifactsScriptTest(unittest.TestCase):
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

    def run_merge(self, task_id, encoding=None):
        script_path = self.repo_root / "scripts" / "merge_artifacts.py"
        env = None
        if encoding:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = encoding
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
            encoding=encoding,
            env=env,
            capture_output=True,
            check=False,
        )

    def copy_fixture(self, name):
        shutil.copytree(self.fixtures_root / name / "workspace", self.workspace_root)

    def load_merge_engine(self):
        scripts_dir = str(self.repo_root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from merge_artifacts import MergeError, ParallelMergeEngine

        return MergeError, ParallelMergeEngine

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

    def write_initialized_state(self, task_id):
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
        context_dir = self.workspace_root / ".superlooper" / "context" / task_id
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

    def write_conflict_manifest(self, task_id):
        manifest_dir = self.workspace_root / ".superlooper" / "manifests" / task_id
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "execution_manifest.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "granularity": "module",
                    "context": {
                        "prd_path": f".superlooper/context/{task_id}/prd.md",
                        "design_docs_path": f".superlooper/context/{task_id}/design/",
                        "module_split_path": f".superlooper/manifests/{task_id}/module-split.json",
                        "agents_path": "agents/",
                        "runtime_agents_path": f".superlooper/agents/{task_id}/",
                        "registered_agents_path": f".claude/agents/generated/superlooper/{task_id}/",
                        "outputs_path": f".superlooper/outputs/{task_id}/",
                        "merged_path": f".superlooper/merged/{task_id}/",
                        "reports_path": f".superlooper/reports/{task_id}/",
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

    def add_report_export_copy(self, task_id, content):
        outputs_dir = self.workspace_root / ".superlooper" / "outputs" / task_id
        duplicate_dir = outputs_dir / "report_export_copy"
        shutil.copytree(outputs_dir / "report_export", duplicate_dir)
        artifact_path = duplicate_dir / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["module_id"] = "report_export_copy"
        artifact["agent"] = "module_report_export_copy"
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        target_file = duplicate_dir / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        target_file.write_text(content, encoding="utf-8")

        manifest_path = self.workspace_root / ".superlooper" / "manifests" / task_id / "execution_manifest.json"
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
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_snapshot_digest_uses_sorted_posix_paths_and_file_hashes(self):
        scripts_dir = str(self.repo_root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from snapshot_digest import compute_tree_digest

        tree = Path(self.temp_dir.name) / "digest-tree"
        (tree / "nested").mkdir(parents=True)
        (tree / "nested" / "b.bin").write_bytes(bytes([0, 255]))
        (tree / "a.txt").write_bytes(b"alpha\n")

        self.assertEqual(
            compute_tree_digest(tree),
            "sha256:49e35f23eb3ec201848fc758de126b047147be17ec84b1c3778539e7d494a0ec",
        )

    def test_merge_artifacts_report_carries_published_snapshot_digest(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        scripts_dir = str(self.repo_root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from snapshot_digest import compute_tree_digest

        merged_dir = self.workspace_root / ".superlooper" / "merged" / "session_happy"
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["snapshot_digest"], compute_tree_digest(merged_dir))
        self.assertRegex(report["snapshot_digest"], r"^sha256:[0-9a-f]{64}$")

    def test_merge_artifacts_report_publish_failure_restores_previous_snapshot_and_report(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        merged_file = self.workspace_root / ".superlooper" / "merged" / "session_happy" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json"
        old_snapshot = merged_file.read_bytes()
        old_report = report_path.read_bytes()
        source_file = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        source_file.write_text("public class ReportExportController { int revision = 2; }\n", encoding="utf-8")
        MergeError, ParallelMergeEngine = self.load_merge_engine()
        engine = ParallelMergeEngine(self.workspace_root, task_id="session_happy")

        with mock.patch("merge_artifacts.os.replace", side_effect=OSError("injected report publish failure")):
            with self.assertRaisesRegex(MergeError, "报告发布失败"):
                engine.run()

        self.assertEqual(merged_file.read_bytes(), old_snapshot)
        self.assertEqual(report_path.read_bytes(), old_report)

    def test_merge_artifacts_first_report_publish_failure_removes_new_snapshot(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        MergeError, ParallelMergeEngine = self.load_merge_engine()
        engine = ParallelMergeEngine(self.workspace_root, task_id="session_happy")
        merged_dir = self.workspace_root / ".superlooper" / "merged" / "session_happy"
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json"

        with mock.patch("merge_artifacts.os.replace", side_effect=OSError("injected report publish failure")):
            with self.assertRaisesRegex(MergeError, "报告发布失败"):
                engine.run()

        self.assertFalse(merged_dir.exists())
        self.assertFalse(report_path.exists())

    def test_merge_artifacts_rejects_windows_equivalent_protected_root(self):
        self.workspace_root.mkdir(parents=True)
        scripts_dir = str(self.repo_root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from merge_artifacts import ParallelMergeEngine

        engine = ParallelMergeEngine(self.workspace_root, task_id="session_safe_path")

        self.assertFalse(engine._safe_relative_path(".GIT\\config"))
        self.assertFalse(engine._safe_relative_path(".git./config"))

    def test_merge_artifacts_rejects_module_directory_outside_task_outputs(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        published_file = self.workspace_root / ".superlooper" / "merged" / "session_happy" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        published_content = published_file.read_bytes()
        module_dir = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export"
        outside_module = Path(self.temp_dir.name) / "outside-module"
        shutil.copytree(module_dir, outside_module)
        outside_file = outside_module / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        outside_content = outside_file.read_bytes()
        shutil.rmtree(module_dir)
        self.create_directory_link(module_dir, outside_module)

        result = self.run_merge("session_happy")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("授权目录", result.stderr)
        self.assertEqual(outside_file.read_bytes(), outside_content)
        self.assertEqual(published_file.read_bytes(), published_content)

    def test_merge_artifacts_rejects_declared_source_outside_module_directory(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        published_file = self.workspace_root / ".superlooper" / "merged" / "session_happy" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        published_content = published_file.read_bytes()
        module_dir = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export"
        source_root = module_dir / "src"
        outside_source = Path(self.temp_dir.name) / "outside-source"
        shutil.copytree(source_root, outside_source)
        outside_file = outside_source / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        outside_content = outside_file.read_bytes()
        shutil.rmtree(source_root)
        self.create_directory_link(source_root, outside_source)

        result = self.run_merge("session_happy")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("授权目录", result.stderr)
        self.assertEqual(outside_file.read_bytes(), outside_content)
        self.assertEqual(published_file.read_bytes(), published_content)

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

    def test_merge_artifacts_second_run_uses_latest_module_content(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        source_file = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        merged_file = self.workspace_root / ".superlooper" / "merged" / "session_happy" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        latest_content = "public class ReportExportController { int revision = 2; }\n"
        source_file.write_text(latest_content, encoding="utf-8")

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(merged_file.read_text(encoding="utf-8"), latest_content)

    def test_merge_artifacts_second_run_removes_stale_artifacts(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        stale_file = self.workspace_root / ".superlooper" / "merged" / "session_happy" / "src" / "main" / "java" / "com" / "example" / "service" / "AuditLogService.java"
        self.assertTrue(stale_file.exists())
        manifest_path = self.workspace_root / ".superlooper" / "manifests" / "session_happy" / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"] = [
            node
            for node in manifest["dag"]["nodes"]
            if node["id"] != "mod_audit_log"
        ]
        for node in manifest["dag"]["nodes"]:
            if node["id"] == "task_code_review":
                node["depends_on"] = ["mod_report_export"]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(stale_file.exists())

    def test_merge_artifacts_success_clears_stale_conflict_evidence(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        duplicate_content = "public class ReportExportController { int duplicated = 1; }\n"
        self.add_report_export_copy("session_happy", duplicate_content)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 2, result.stderr)
        reports_dir = self.workspace_root / ".superlooper" / "reports" / "session_happy"
        self.assertTrue((reports_dir / "conflict_report.json").exists())
        self.assertTrue((reports_dir / "conflicts").exists())
        original_file = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        duplicate_file = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "report_export_copy" / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        duplicate_file.write_bytes(original_file.read_bytes())

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((reports_dir / "merge_report.json").exists())
        self.assertFalse((reports_dir / "conflict_report.json").exists())
        self.assertFalse((reports_dir / "conflicts").exists())

    def test_merge_artifacts_conflict_preserves_published_snapshot(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        merged_dir = self.workspace_root / ".superlooper" / "merged" / "session_happy"
        published_file = merged_dir / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        published_content = published_file.read_bytes()
        self.add_report_export_copy(
            "session_happy",
            "public class ReportExportController { int duplicated = 1; }\n",
        )
        audit_dir = self.workspace_root / ".superlooper" / "outputs" / "session_happy" / "audit_log"
        new_relative_path = "src/main/java/com/example/service/NewAuditService.java"
        new_source = audit_dir / new_relative_path
        new_source.parent.mkdir(parents=True, exist_ok=True)
        new_source.write_text("public class NewAuditService {}\n", encoding="utf-8")
        artifact_path = audit_dir / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["produced_files"].append(
            {
                "path": new_relative_path,
                "kind": "code",
                "operation": "create",
                "required_for_merge": True,
            }
        )
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 2, result.stderr)
        reports_dir = self.workspace_root / ".superlooper" / "reports" / "session_happy"
        self.assertFalse((reports_dir / "merge_report.json").exists())
        self.assertTrue((reports_dir / "conflict_report.json").exists())
        self.assertEqual(published_file.read_bytes(), published_content)
        self.assertFalse((merged_dir / new_relative_path).exists())

    def test_merge_artifacts_conflict_path_writes_conflict_report(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.add_report_export_copy(
            "session_happy",
            "public class ReportExportController { int duplicated = 1; }\n",
        )

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 2, result.stderr)
        report_path = self.workspace_root / ".superlooper" / "reports" / "session_happy" / "conflict_report.json"
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

    def test_merge_artifacts_rejects_windows_equivalent_actual_file_duplicates(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_merge("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        published_file = (
            self.workspace_root
            / ".superlooper"
            / "merged"
            / "session_happy"
            / "src"
            / "main"
            / "java"
            / "com"
            / "example"
            / "controller"
            / "ReportExportController.java"
        )
        published_content = published_file.read_bytes()
        controller_dir = (
            self.workspace_root
            / ".superlooper"
            / "outputs"
            / "session_happy"
            / "report_export"
            / "src"
            / "main"
            / "java"
            / "com"
            / "example"
            / "controller"
        )
        first_relative = "src/main/java/com/example/controller/StraßeController.java"
        second_relative = "src/main/java/com/example/controller/STRASSECONTROLLER.JAVA"
        (controller_dir / "StraßeController.java").write_text(
            "public class StraßeController {}\n",
            encoding="utf-8",
        )
        (controller_dir / "STRASSECONTROLLER.JAVA").write_text(
            "public class StrasseController {}\n",
            encoding="utf-8",
        )
        if len([path for path in controller_dir.iterdir() if "trasse" in path.name.casefold()]) < 2:
            self.skipTest("当前文件系统无法同时创建用于 Windows 等价冲突测试的两个文件")

        result = self.run_merge("session_happy", encoding="utf-8")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("模块实际文件存在 Windows 等价重复路径", result.stderr)
        self.assertIn(first_relative, result.stderr)
        self.assertIn(second_relative, result.stderr)
        self.assertEqual(published_file.read_bytes(), published_content)

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

    def test_merge_artifacts_accepts_legacy_inputs_without_rewriting(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = self.workspace_root / ".superlooper" / "manifests" / "session_happy" / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["session_id"] = manifest.pop("task_id")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifact_paths = sorted(
            (self.workspace_root / ".superlooper" / "outputs" / "session_happy").glob("*/artifact_manifest.json")
        )

        result = self.run_merge("session_happy")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(
            (self.workspace_root / ".superlooper" / "reports" / "session_happy" / "merge_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["task_id"], "session_happy")
        self.assertNotIn("session_id", report)
        persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("session_id", persisted_manifest)
        self.assertNotIn("task_id", persisted_manifest)
        for artifact_path in artifact_paths:
            persisted_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertIn("session_id", persisted_artifact)
            self.assertNotIn("task_id", persisted_artifact)

    def test_merge_artifacts_rejects_dual_manifest_identity(self):
        self.copy_fixture("happy-path")
        self.write_initialized_state("session_happy")
        result = self.run_generate_manifest("session_happy")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = self.workspace_root / ".superlooper" / "manifests" / "session_happy" / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["session_id"] = "session_happy"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_merge("session_happy")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不能同时包含 task_id 和 legacy session_id", result.stderr)


if __name__ == "__main__":
    unittest.main()
