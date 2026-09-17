import json
import unittest
from pathlib import Path

from scripts.schema_validation import SchemaValidator


class SchemaValidationTest(unittest.TestCase):
    def setUp(self):
        self.schemas_dir = Path(__file__).resolve().parents[1] / "schemas"
        self.validator = SchemaValidator()

    def load_schema(self, filename):
        return json.loads((self.schemas_dir / filename).read_text(encoding="utf-8"))

    def test_module_id_rejects_reserved_placeholder_from_not_constraint(self):
        schema = self.load_schema("module-split.schema.json")
        module_id_schema = schema["properties"]["modules"]["items"]["properties"]["id"]

        errors = self.validator.validate("feature_a", module_id_schema, "module.id")

        self.assertTrue(any("不得匹配禁止约束" in error for error in errors))

    def test_interaction_command_name_rejects_forbidden_manifest_command(self):
        schema = self.load_schema("interaction-flow.schema.json")
        name_schema = schema["properties"]["commands"]["items"]["properties"]["name"]

        errors = self.validator.validate("/spl:manifest", name_schema, "command.name")

        self.assertTrue(any("不得匹配禁止约束" in error for error in errors))

    def test_codex_context_rejects_claude_registration_path_from_conditional_constraint(self):
        schema = self.load_schema("execution-manifest.schema.json")
        context_schema = schema["properties"]["context"]
        context = {
            "prd_path": "prd.md",
            "design_docs_path": "design/",
            "module_split_path": "module-split.json",
            "agents_path": "agents/",
            "runtime_agents_path": "runtime/",
            "outputs_path": "outputs/",
            "merged_path": "merged/",
            "reports_path": "reports/",
            "platform_registration": {"platform": "codex"},
            "registered_agents_path": "registered/",
        }

        errors = self.validator.validate(context, context_schema, "context")

        self.assertTrue(any("不得匹配禁止约束" in error for error in errors))

    def test_module_node_requires_object_payload_from_conditional_constraint(self):
        schema = self.load_schema("execution-manifest.schema.json")
        node_schema = schema["properties"]["dag"]["properties"]["nodes"]["items"]
        node = {
            "id": "mod_valid_module",
            "agent": "module_valid_module",
            "depends_on": [],
            "payload": "not-an-object",
        }

        errors = self.validator.validate(node, node_schema, "node")

        self.assertTrue(any("node.payload 类型必须为 object" in error for error in errors))

    def test_system_nodes_require_object_payloads(self):
        schema = self.load_schema("execution-manifest.schema.json")
        node_schema = schema["properties"]["dag"]["properties"]["nodes"]["items"]
        agents = {
            "task_code_review": "code-reviewer",
            "task_merge": "system_merger",
            "task_integration_test": "tester",
            "task_apply_to_workspace": "workspace_applier",
        }

        for node_id, agent in agents.items():
            with self.subTest(node_id=node_id):
                node = {
                    "id": node_id,
                    "agent": agent,
                    "depends_on": [],
                    "payload": "not-an-object",
                }
                errors = self.validator.validate(node, node_schema, "node")
                self.assertTrue(any("node.payload 类型必须为 object" in error for error in errors))

    def test_system_node_payload_requires_declared_fields(self):
        schema = self.load_schema("execution-manifest.schema.json")
        node_schema = schema["properties"]["dag"]["properties"]["nodes"]["items"]
        node = {
            "id": "task_code_review",
            "agent": "code-reviewer",
            "depends_on": [],
            "payload": {
                "workspace_root": ".",
                "task_id": "session_schema",
                "outputs_path": ".superlooper/outputs/session_schema/",
                "reports_path": ".superlooper/reports/session_schema/",
                "execution_manifest_path": ".superlooper/manifests/session_schema/execution_manifest.json",
                "design_docs_path": ".superlooper/context/session_schema/design/",
            },
        }

        errors = self.validator.validate(node, node_schema, "node")

        self.assertTrue(any("node.payload 缺少必填字段：module_split_path" in error for error in errors))

    def test_apply_system_payload_rejects_overwrite_authorization(self):
        schema = self.load_schema("execution-manifest.schema.json")
        node_schema = schema["properties"]["dag"]["properties"]["nodes"]["items"]
        node = {
            "id": "task_apply_to_workspace",
            "agent": "workspace_applier",
            "depends_on": ["task_integration_test"],
            "payload": {
                "workspace_root": ".",
                "task_id": "session_schema",
                "merged_dir": ".superlooper/merged/session_schema",
                "reports_dir": ".superlooper/reports/session_schema",
                "merge_report_path": ".superlooper/reports/session_schema/merge_report.json",
                "test_report_path": ".superlooper/reports/session_schema/test_report.md",
                "overwrite_existing": True,
            },
        }

        errors = self.validator.validate(node, node_schema, "node")

        self.assertTrue(any("node.payload 存在未声明字段：overwrite_existing" in error for error in errors))

    def test_loop_count_property_name_must_be_a_rollback_phase(self):
        schema = self.load_schema("session-state.schema.json")
        count_schema = schema["properties"]["loop_state"]["properties"]["loop_count_by_phase"]

        errors = self.validator.validate({"unexpected": 1}, count_schema, "loop_count_by_phase")

        self.assertTrue(any("值不在允许枚举" in error for error in errors))

    def test_string_max_length_is_enforced(self):
        errors = self.validator.validate("abcd", {"type": "string", "maxLength": 3}, "value")

        self.assertTrue(any("长度必须不超过 3" in error for error in errors))

    def test_task_name_schema_rejects_control_and_unicode_line_separators(self):
        schema = self.load_schema("session-state.schema.json")
        task_name_schema = schema["properties"]["task_name"]

        for value in ("line\nbreak", "line" + chr(0x85) + "break", "line" + chr(0x2028) + "break", "line" + chr(0x2029) + "break"):
            with self.subTest(value=repr(value)):
                errors = self.validator.validate(value, task_name_schema, "task_name")
                self.assertTrue(errors)

        self.assertEqual(self.validator.validate("发布 任务", task_name_schema, "task_name"), [])


if __name__ == "__main__":
    unittest.main()
