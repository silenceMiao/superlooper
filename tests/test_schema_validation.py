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

    def test_loop_count_property_name_must_be_a_rollback_phase(self):
        schema = self.load_schema("session-state.schema.json")
        count_schema = schema["properties"]["loop_state"]["properties"]["loop_count_by_phase"]

        errors = self.validator.validate({"unexpected": 1}, count_schema, "loop_count_by_phase")

        self.assertTrue(any("值不在允许枚举" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
