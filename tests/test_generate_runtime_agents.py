import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GenerateRuntimeAgentsScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "session_agents"
        self.agents_dir = self.workspace_root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        template = (self.repo_root / "agents" / "developer.md").read_text(encoding="utf-8")
        (self.agents_dir / "developer.md").write_text(template, encoding="utf-8")
        manifests_dir = self.workspace_root / ".superlooper" / "manifests" / self.session_id
        manifests_dir.mkdir(parents=True, exist_ok=True)
        self.module_split_path = manifests_dir / "module-split.json"
        self.module_split_path.write_text(
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
                            "file_roles": [
                                {
                                    "path": "src/main/java/com/example/controller/ReportExportController.java",
                                    "role": "controller",
                                }
                            ],
                            "requirement_refs": ["REQ-001"],
                            "decision_refs": ["DEC-001"],
                            "open_question_refs": ["OPEN-001"],
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
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, plugin_root=None, platform="claude"):
        script_path = self.repo_root / "scripts" / "generate_runtime_agents.py"
        command = [
            sys.executable,
            str(script_path),
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--agents-dir",
            "agents",
            "--platform",
            platform,
        ]
        if plugin_root:
            command.extend(["--plugin-root", str(plugin_root)])
        return subprocess.run(
            command,
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_generate_runtime_agents_creates_matching_runtime_and_registered_files(self):
        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.session_id / "module_report_export.md"
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.session_id / "module_report_export.md"
        runtime_content = runtime_path.read_text(encoding="utf-8")
        registered_content = registered_path.read_text(encoding="utf-8")
        self.assertEqual(runtime_content, registered_content)
        self.assertIn("name: module_report_export", runtime_content)
        self.assertIn("description: 动态模块编码子代理，负责 实现报表导出控制器。", runtime_content)
        self.assertIn("## Runtime Module Constraints", runtime_content)
        self.assertIn("module_id: report_export", runtime_content)
        for field in [
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
        ]:
            self.assertIn(f"{field}:", runtime_content)
        self.assertIn("src/main/java/com/example/controller/ReportExportController.java", runtime_content)
        self.assertIn("UI-PAGE-001", runtime_content)
        self.assertIn("INT-001", runtime_content)
        self.assertIn("CMP-001", runtime_content)
        self.assertIn("UI-AC-001", runtime_content)
        self.assertIn("ReportRepository", runtime_content)
        self.assertIn("python -m unittest tests.test_report_export", runtime_content)
        self.assertIn("overwrite_policy: block_by_default", runtime_content)

    def test_generate_runtime_agents_for_codex_keeps_only_runtime_agents(self):
        result = self.run_script(platform="codex")

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.session_id / "module_report_export.md"
        dispatch_path = self.workspace_root / ".superlooper" / "agents" / self.session_id / "codex-dispatch.json"
        self.assertTrue(runtime_path.is_file())
        self.assertFalse(dispatch_path.exists())
        self.assertFalse((self.workspace_root / ".claude").exists())

    def test_generate_runtime_agents_reads_static_template_from_plugin_root(self):
        (self.agents_dir / "developer.md").unlink()

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.session_id / "module_report_export.md"
        self.assertTrue(runtime_path.is_file())

    def test_generate_runtime_agents_accepts_explicit_plugin_root(self):
        (self.agents_dir / "developer.md").unlink()
        plugin_dir = tempfile.TemporaryDirectory()
        self.addCleanup(plugin_dir.cleanup)
        plugin_root = Path(plugin_dir.name)
        plugin_agents_dir = plugin_root / "agents"
        plugin_agents_dir.mkdir(parents=True, exist_ok=True)
        template = (self.repo_root / "agents" / "developer.md").read_text(encoding="utf-8")
        (plugin_agents_dir / "developer.md").write_text(template, encoding="utf-8")

        result = self.run_script(plugin_root=plugin_root)

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.session_id / "module_report_export.md"
        self.assertTrue(runtime_path.is_file())


if __name__ == "__main__":
    unittest.main()
