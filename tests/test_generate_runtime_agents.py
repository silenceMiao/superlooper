import hashlib
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
        self.task_id = "session_agents"
        self.agents_dir = self.workspace_root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        template = (self.repo_root / "agents" / "developer.md").read_text(encoding="utf-8")
        (self.agents_dir / "developer.md").write_text(template, encoding="utf-8")
        manifests_dir = self.workspace_root / ".superlooper" / "manifests" / self.task_id
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

    def run_script(self, plugin_root=None, platform="claude", task_id=None):
        script_path = self.repo_root / "scripts" / "generate_runtime_agents.py"
        command = [
            sys.executable,
            str(script_path),
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            task_id or self.task_id,
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

    def parse_frontmatter(self, content):
        lines = content.splitlines()
        end_index = lines.index("---", 1)
        values = {}
        for line in lines[1:end_index]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            raw_value = value.strip()
            try:
                values[key] = json.loads(raw_value)
            except json.JSONDecodeError:
                values[key] = raw_value
        return values, "\n".join(lines[end_index + 1 :])

    def parse_constraints(self, content):
        block = content.split("## Runtime Module Constraints", 1)[1]
        yaml_block = block.split("```yaml\n", 1)[1].split("\n```", 1)[0]
        values = {}
        for line in yaml_block.splitlines():
            if not line.strip():
                continue
            key, raw_value = line.split(":", 1)
            try:
                values[key.strip()] = json.loads(raw_value.strip())
            except json.JSONDecodeError:
                return None
        return values

    def test_generate_runtime_agents_creates_logical_runtime_and_task_scoped_registered_files(self):
        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "module_report_export.md"
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id / "module_report_export.md"
        runtime_content = runtime_path.read_text(encoding="utf-8")
        registered_content = registered_path.read_text(encoding="utf-8")
        runtime_frontmatter, runtime_body = self.parse_frontmatter(runtime_content)
        registered_frontmatter, registered_body = self.parse_frontmatter(registered_content)
        expected_registered_name = (
            "module_report_export__task_"
            + hashlib.sha256(self.task_id.encode("utf-8")).hexdigest()[:16]
        )
        self.assertEqual(runtime_frontmatter["name"], "module_report_export")
        self.assertEqual(registered_frontmatter["name"], expected_registered_name)
        self.assertEqual(
            {key: value for key, value in runtime_frontmatter.items() if key != "name"},
            {key: value for key, value in registered_frontmatter.items() if key != "name"},
        )
        self.assertEqual(runtime_body, registered_body)
        self.assertEqual(
            runtime_frontmatter["description"],
            "动态模块编码子代理，负责 实现报表导出控制器。",
        )
        constraints = self.parse_constraints(runtime_content)
        self.assertIsNotNone(constraints)
        self.assertEqual(constraints["task_id"], self.task_id)
        self.assertNotIn("session_id", constraints)
        self.assertEqual(constraints["module_id"], "report_export")
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
        self.assertEqual(constraints["overwrite_policy"], "block_by_default")

    def test_generate_runtime_agents_json_quotes_special_values_and_preserves_types(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module = module_split["modules"][0]
        module["description"] = '导出: #tag "quoted"\n第二行'
        module["decision_refs"] = []
        module["file_roles"][0]["metadata"] = {
            "enabled": True,
            "optional": None,
            "tags": [],
            "config": {},
        }
        module["integration_points"] = ['Report: #1 "primary"\nnext']
        self.module_split_path.write_text(
            json.dumps(module_split, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "module_report_export.md"
        content = runtime_path.read_text(encoding="utf-8")
        frontmatter, _ = self.parse_frontmatter(content)
        constraints = self.parse_constraints(content)
        self.assertEqual(
            frontmatter["description"],
            '动态模块编码子代理，负责 导出: #tag "quoted"\n第二行。',
        )
        self.assertIsNotNone(constraints)
        self.assertEqual(constraints["decision_refs"], [])
        self.assertIs(constraints["file_roles"][0]["metadata"]["enabled"], True)
        self.assertIsNone(constraints["file_roles"][0]["metadata"]["optional"])
        self.assertEqual(constraints["file_roles"][0]["metadata"]["tags"], [])
        self.assertEqual(constraints["file_roles"][0]["metadata"]["config"], {})
        self.assertEqual(
            constraints["integration_points"],
            ['Report: #1 "primary"\nnext'],
        )
        self.assertIn('decision_refs: []', content)
        self.assertIn('"enabled": true', content)
        self.assertIn('"optional": null', content)
        self.assertIn('"config": {}', content)

    def test_generate_runtime_agents_uses_distinct_registered_names_for_same_module_across_tasks(self):
        other_task_id = "session_agents_other"
        other_manifest_dir = self.workspace_root / ".superlooper" / "manifests" / other_task_id
        other_manifest_dir.mkdir(parents=True, exist_ok=True)
        (other_manifest_dir / "module-split.json").write_text(
            self.module_split_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        first_result = self.run_script()
        second_result = self.run_script(task_id=other_task_id)

        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        first_registered = (
            self.workspace_root
            / ".claude"
            / "agents"
            / "generated"
            / "superlooper"
            / self.task_id
            / "module_report_export.md"
        ).read_text(encoding="utf-8")
        second_registered = (
            self.workspace_root
            / ".claude"
            / "agents"
            / "generated"
            / "superlooper"
            / other_task_id
            / "module_report_export.md"
        ).read_text(encoding="utf-8")
        first_name = self.parse_frontmatter(first_registered)[0]["name"]
        second_name = self.parse_frontmatter(second_registered)[0]["name"]
        self.assertNotEqual(first_name, second_name)
        self.assertEqual(
            first_name,
            "module_report_export__task_"
            + hashlib.sha256(self.task_id.encode("utf-8")).hexdigest()[:16],
        )
        self.assertEqual(
            second_name,
            "module_report_export__task_"
            + hashlib.sha256(other_task_id.encode("utf-8")).hexdigest()[:16],
        )

    def test_generate_runtime_agents_for_codex_keeps_only_runtime_agents(self):
        result = self.run_script(platform="codex")

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "module_report_export.md"
        dispatch_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "codex-dispatch.json"
        self.assertTrue(runtime_path.is_file())
        runtime_frontmatter, _ = self.parse_frontmatter(runtime_path.read_text(encoding="utf-8"))
        self.assertEqual(runtime_frontmatter["name"], "module_report_export")
        self.assertFalse(dispatch_path.exists())
        self.assertFalse((self.workspace_root / ".claude").exists())

    def test_generate_runtime_agents_reads_static_template_from_plugin_root(self):
        (self.agents_dir / "developer.md").unlink()

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "module_report_export.md"
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
        runtime_path = self.workspace_root / ".superlooper" / "agents" / self.task_id / "module_report_export.md"
        self.assertTrue(runtime_path.is_file())


if __name__ == "__main__":
    unittest.main()
