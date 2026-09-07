import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REQUIRED_COMMANDS = [
    "/spl",
    "/spl:prd",
    "/spl:ui",
    "/spl:design",
    "/spl:run",
    "/spl:status",
    "/spl:resume",
    "/spl:doctor",
]
REQUIRED_PHASES = ["prd", "ui_design", "design", "run"]
REQUIRED_COMMAND_PHASES = {
    "/spl": "init",
    "/spl:prd": "prd",
    "/spl:ui": "ui_design",
    "/spl:design": "design",
    "/spl:run": "run",
    "/spl:status": "status",
    "/spl:resume": "resume",
    "/spl:doctor": "doctor",
}
REQUIRED_REPLIES = [
    "已确认，重新生成 PRD",
    "PRD未通过，按反馈重新分析",
    "通过，进入 UI 设计",
    "UI设计未通过，按反馈重新设计",
    "UI设计通过，进入系统设计",
    "需求变更，返回 PRD 修订",
    "继续任务",
    "设计未通过，按反馈重新设计",
    "生成执行清单",
    "执行",
    "开始并行开发",
    "按此执行",
    "执行摘要未通过，返回修正",
    "需求变更，执行影响分析",
    "选择初始化项目分类",
    "选择初始化项目版本",
    "影响分析通过，执行局部重跑",
    "影响分析不通过，人工处理",
    "代码审查未通过，返回修正",
    "测试未通过，返回修正",
    "应用冲突已处理，重新应用",
]
INITIALIZATION_REPLIES = [
    "java",
    "go",
    "springboot",
    "pom",
    "lua",
    "jdk-8",
    "jdk-11",
    "jdk-17",
    "go-1.25",
    "springboot-2.x",
    "springboot-3.x",
    "maven-3.5.x",
    "maven-3.9.x",
    "lua-4.x",
    "lua-5.x",
]
REQUIREMENT_ALIGNMENT_REPLIES = [
    "需求校对通过，完成交付",
    "需求校对未通过，返回修正",
]


class InteractionFlowContractTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.flow_path = self.repo_root / "configs" / "interaction-flow.json"
        self.script_path = self.repo_root / "scripts" / "validate_miao_contracts.py"
        self.command_files = {
            "/spl": self.repo_root / "commands" / "spl.md",
            "/spl:prd": self.repo_root / "commands" / "spl" / "prd.md",
            "/spl:ui": self.repo_root / "commands" / "spl" / "ui.md",
            "/spl:design": self.repo_root / "commands" / "spl" / "design.md",
            "/spl:run": self.repo_root / "commands" / "spl" / "run.md",
            "/spl:status": self.repo_root / "commands" / "spl" / "status.md",
            "/spl:resume": self.repo_root / "commands" / "spl" / "resume.md",
            "/spl:doctor": self.repo_root / "commands" / "spl" / "doctor.md",
        }

    def run_validator(self, workspace_root=None, plugin_root=None):
        root = Path(workspace_root) if workspace_root else self.repo_root
        plugin = Path(plugin_root) if plugin_root else root
        return subprocess.run(
            [
                sys.executable,
                str(self.script_path),
                "--workspace-root",
                str(root),
                "--session-id",
                "session_dummy",
                "--scope",
                "interaction-flow",
                "--plugin-root",
                str(plugin),
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def make_flow_workspace(self):
        temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(temp_dir.name)
        shutil.copytree(self.repo_root / "configs", workspace / "configs")
        shutil.copytree(self.repo_root / "schemas", workspace / "schemas")
        shutil.copytree(self.repo_root / "commands", workspace / "commands")
        return temp_dir, workspace

    def load_flow(self):
        return json.loads(self.flow_path.read_text(encoding="utf-8"))

    def test_interaction_flow_validation_passes(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("scope=interaction-flow", result.stdout)

    def test_interaction_flow_uses_plugin_root_when_workspace_is_separate(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        workspace = Path(temp_dir.name)

        result = self.run_validator(workspace_root=workspace, plugin_root=self.repo_root)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("scope=interaction-flow", result.stdout)

    def test_manifest_command_is_rejected(self):
        temp_dir, workspace = self.make_flow_workspace()
        self.addCleanup(temp_dir.cleanup)
        flow_path = workspace / "configs" / "interaction-flow.json"
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
        flow["commands"].append({"name": "/spl:manifest", "phase": "run", "exposed": True})
        flow_path.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validator(workspace)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("/spl:manifest", result.stderr)

    def test_manifest_entry_command_is_rejected(self):
        temp_dir, workspace = self.make_flow_workspace()
        self.addCleanup(temp_dir.cleanup)
        flow_path = workspace / "configs" / "interaction-flow.json"
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
        flow["phases"][0]["entry_command"] = "/spl:manifest"
        flow_path.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validator(workspace)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("/spl:manifest", result.stderr)

    def test_phase_entry_command_must_match_command_phase(self):
        temp_dir, workspace = self.make_flow_workspace()
        self.addCleanup(temp_dir.cleanup)
        flow_path = workspace / "configs" / "interaction-flow.json"
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
        for command in flow["commands"]:
            if command["name"] == "/spl:design":
                command["phase"] = "run"
        flow_path.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validator(workspace)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("command.phase", result.stderr)

    def test_exposed_command_files_exist(self):
        flow = self.load_flow()
        exposed_commands = [item["name"] for item in flow["commands"] if item.get("exposed") is True]
        for command_name in exposed_commands:
            with self.subTest(command_name=command_name):
                self.assertIn(command_name, self.command_files)
                self.assertTrue(self.command_files[command_name].exists(), str(self.command_files[command_name]))

    def test_command_phases_keep_operational_roles(self):
        flow = self.load_flow()
        command_phases = {item["name"]: item["phase"] for item in flow["commands"]}
        for command_name, phase in REQUIRED_COMMAND_PHASES.items():
            with self.subTest(command_name=command_name):
                self.assertEqual(command_phases.get(command_name), phase)

    def test_command_file_undeclared_handshake_is_rejected(self):
        temp_dir, workspace = self.make_flow_workspace()
        self.addCleanup(temp_dir.cleanup)
        command_path = workspace / "commands" / "spl" / "run.md"
        command_path.write_text(command_path.read_text(encoding="utf-8") + "\n请回复 未声明动作。\n", encoding="utf-8")

        result = self.run_validator(workspace)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明动作", result.stderr)

    def test_spl_command_declares_active_session_first_routing(self):
        content = self.command_files["/spl"].read_text(encoding="utf-8")
        self.assertIn("先读取目标项目 `.superlooper/state/*.json` 检测 active session", content)
        self.assertIn("只有 1 个 active session", content)
        self.assertIn("不得新建 session", content)
        self.assertIn("存在多个 active session 时，不得猜测目标会话", content)
        self.assertIn("不存在 active session 时，才进入需求文档路径判断", content)

    def test_stage_commands_reference_skill_and_interaction_flow(self):
        for command_name in ["/spl", "/spl:prd", "/spl:ui", "/spl:design", "/spl:run"]:
            with self.subTest(command_name=command_name):
                content = self.command_files[command_name].read_text(encoding="utf-8")
                self.assertIn("skills/superlooper/SKILL.md", content)
                self.assertIn("configs/interaction-flow.json", content)
                self.assertIn("allowed_replies", content)
        for command_name in ["/spl", "/spl:run", "/spl:resume"]:
            with self.subTest(no_manifest=command_name):
                content = self.command_files[command_name].read_text(encoding="utf-8")
                self.assertIn("不提供 `/spl:manifest`", content)

    def test_flow_phases_match_command_files(self):
        flow = self.load_flow()
        command_names = {item["name"] for item in flow["commands"]}
        phase_ids = {item["id"] for item in flow["phases"]}
        for command_name in REQUIRED_COMMANDS:
            with self.subTest(command_name=command_name):
                self.assertIn(command_name, command_names)
        for phase_id in REQUIRED_PHASES:
            with self.subTest(phase_id=phase_id):
                self.assertIn(phase_id, phase_ids)
        for phase in flow["phases"]:
            with self.subTest(phase=phase["id"]):
                self.assertIn(phase["entry_command"], command_names)
                expected_path = self.command_files.get(phase["entry_command"])
                self.assertIsNotNone(expected_path)
                self.assertTrue(expected_path.exists(), str(expected_path))

    def test_allowed_replies_cover_required_handshakes(self):
        flow = self.load_flow()
        replies = {
            reply
            for phase in flow["phases"]
            for reply in phase.get("allowed_replies", [])
        }
        for reply in REQUIRED_REPLIES:
            with self.subTest(reply=reply):
                self.assertIn(reply, replies)

    def test_prd_flows_to_ui_and_ui_flows_to_design(self):
        flow = self.load_flow()
        phases = {phase["id"]: phase for phase in flow["phases"]}
        self.assertEqual(phases["prd"]["next_phase"], "ui_design")
        self.assertEqual(phases["ui_design"]["next_phase"], "design")
        prd_actions = {action["name"] for action in phases["prd"]["canonical_actions"]}
        self.assertIn("prd_decisions_confirmed", prd_actions)
        ui_actions = {action["name"] for action in phases["ui_design"]["canonical_actions"]}
        self.assertEqual(
            {"ui_revision_requested", "approve_ui_and_proceed", "prd_revision_requested"},
            ui_actions,
        )

    def test_initialization_and_alignment_replies_are_declared(self):
        flow = self.load_flow()
        replies = {
            reply
            for phase in flow["phases"]
            for reply in phase.get("allowed_replies", [])
        }
        for reply in [*INITIALIZATION_REPLIES, *REQUIREMENT_ALIGNMENT_REPLIES]:
            with self.subTest(reply=reply):
                self.assertIn(reply, replies)

    def test_initialization_options_are_declared(self):
        flow = self.load_flow()
        self.assertEqual(
            flow["initialization_options"],
            {
                "java": ["jdk-8", "jdk-11", "jdk-17"],
                "go": ["go-1.25"],
                "springboot": ["springboot-2.x", "springboot-3.x"],
                "pom": ["maven-3.5.x", "maven-3.9.x"],
                "lua": ["lua-4.x", "lua-5.x"],
            },
        )

    def test_canonical_actions_are_declared_in_allowed_replies(self):
        flow = self.load_flow()
        for phase in flow["phases"]:
            allowed = set(phase["allowed_replies"])
            self.assertIn("canonical_actions", phase)
            self.assertTrue(phase["canonical_actions"])
            for action in phase["canonical_actions"]:
                with self.subTest(phase=phase["id"], action=action["name"]):
                    self.assertIn(action["canonical_reply"], allowed)
                    self.assertIsInstance(action["aliases"], list)
                    self.assertTrue(action["aliases"])
                    self.assertIsInstance(action["requires_feedback"], bool)

    def test_intent_aliases_are_unique_within_phase(self):
        flow = self.load_flow()
        for phase in flow["phases"]:
            aliases = {}
            for action in phase["canonical_actions"]:
                for alias in action["aliases"]:
                    with self.subTest(phase=phase["id"], alias=alias):
                        self.assertNotIn(alias, aliases)
                    aliases[alias] = action["name"]

    def test_design_phase_declares_change_impact_action(self):
        flow = self.load_flow()
        design = next(phase for phase in flow["phases"] if phase["id"] == "design")
        action_names = {action["name"] for action in design["canonical_actions"]}
        self.assertIn("change_impact_requested", action_names)
        self.assertIn("需求变更，执行影响分析", design["allowed_replies"])

    def test_design_phase_declares_initialization_selection_actions(self):
        flow = self.load_flow()
        design = next(phase for phase in flow["phases"] if phase["id"] == "design")
        action_names = {action["name"] for action in design["canonical_actions"]}
        self.assertIn("select_project_category", action_names)
        self.assertIn("select_project_version", action_names)
        self.assertIn("选择初始化项目分类", design["allowed_replies"])
        self.assertIn("选择初始化项目版本", design["allowed_replies"])

    def test_run_phase_declares_requirement_alignment_revision_action(self):
        flow = self.load_flow()
        run = next(phase for phase in flow["phases"] if phase["id"] == "run")
        action_names = {action["name"] for action in run["canonical_actions"]}
        self.assertIn("requirement_alignment_revision_requested", action_names)
        self.assertIn("需求校对未通过，返回修正", run["allowed_replies"])

    def test_run_phase_declares_execution_summary_actions(self):
        flow = self.load_flow()
        run = next(phase for phase in flow["phases"] if phase["id"] == "run")
        action_names = {action["name"] for action in run["canonical_actions"]}
        self.assertIn("execution_summary_approved", action_names)
        self.assertIn("execution_summary_revision_requested", action_names)
        self.assertIn("按此执行", run["allowed_replies"])
        self.assertIn("执行摘要未通过，返回修正", run["allowed_replies"])

    def test_run_phase_declares_failure_rework_actions(self):
        flow = self.load_flow()
        run = next(phase for phase in flow["phases"] if phase["id"] == "run")
        action_names = {action["name"] for action in run["canonical_actions"]}
        self.assertIn("code_review_revision_requested", action_names)
        self.assertIn("test_revision_requested", action_names)
        self.assertIn("apply_retry_requested", action_names)
        self.assertIn("代码审查未通过，返回修正", run["allowed_replies"])
        self.assertIn("测试未通过，返回修正", run["allowed_replies"])
        self.assertIn("应用冲突已处理，重新应用", run["allowed_replies"])


if __name__ == "__main__":
    unittest.main()
