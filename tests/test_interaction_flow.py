import json
import re
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
    "重试执行摘要",
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
        self.static_agent_files = {
            "system_merger": self.repo_root / "agents" / "system_merger.md",
            "workspace_applier": self.repo_root / "agents" / "workspace_applier.md",
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
                "--task-id",
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

    def test_spl_command_declares_active_task_first_routing(self):
        content = self.command_files["/spl"].read_text(encoding="utf-8")
        self.assertIn("检测 active task", content)
        self.assertIn("无论用户参数是否看起来像 `requirement_path`", content)
        self.assertIn("只有 1 个 active task", content)
        self.assertIn("不得新建 task", content)
        self.assertIn("存在多个 active task 时，不得猜测目标任务", content)
        self.assertIn("不存在 active task 时，才进入需求文档路径判断", content)
        self.assertNotIn("而不是明确的 `requirement_path`", content)

    def test_spl_command_preflights_python_before_business_actions(self):
        content = self.command_files["/spl"].read_text(encoding="utf-8")

        self.assertIn('argument-hint: \'<requirement_path> [--task-name "<task_name>"]\'', content)
        self.assertIn("python --version", content)
        self.assertIn("sys.version_info >= (3, 9)", content)
        self.assertIn("Python 3.9+", content)
        self.assertIn("当前 Agent 会话无法执行 Python；Superlooper workflow 在该环境中不可用", content)
        self.assertIn("安装本身不等于运行依赖满足", content)
        for prohibited_effect in [
            "不创建 `.superlooper/`",
            "不恢复或推进 task",
            "不调用 agent",
            "不修改目标项目",
            "不自动安装 Python",
            "不修改 PATH 或 sandbox",
        ]:
            self.assertIn(prohibited_effect, content)
        probe_position = content.index("python --version")
        version_position = content.index("sys.version_info >= (3, 9)")
        self.assertGreater(version_position, probe_position)
        for later_action in [
            "`${CLAUDE_PLUGIN_ROOT}/skills/superlooper/SKILL.md`",
            "`.superlooper/state/*.json`",
            "status_session.py",
            "normalize_user_intent.py",
            "resume_session.py",
            "create_session.py",
            "调用 `superlooper:analyst`",
        ]:
            self.assertGreater(content.index(later_action), version_position)
        self.assertIn("--task-name", content)
        self.assertNotIn("master-framework-<YYYYMMDD>", content)

    def test_spl_command_uses_active_listing_and_isolated_new_task_mode(self):
        content = self.command_files["/spl"].read_text(encoding="utf-8")

        self.assertIn("status_session.py\" --workspace-root <workspace_root> --list-active", content)
        self.assertIn("create_session.py\" --workspace-root <workspace_root> --new-task", content)
        self.assertIn("每个用户值都作为单个 argv 数据传递", content)
        self.assertIn("不得拼接为 shell 源码", content)
        self.assertNotIn("将其原样追加", content)

    def test_spl_new_task_enters_the_canonical_prd_checkpoint_chain(self):
        content = self.command_files["/spl"].read_text(encoding="utf-8")

        create_position = content.index("create_session.py")
        running_position = content.index("--current-phase prd --phase-status running", create_position)
        analyst_position = content.index("调用 `superlooper:analyst`", running_position)
        validation_position = content.index("校验 analyst 状态块和 PRD 产物合同", analyst_position)
        terminal_position = content.index("--phase-status waiting_review", validation_position)
        self.assertEqual(
            [create_position, running_position, analyst_position, validation_position, terminal_position],
            sorted([create_position, running_position, analyst_position, validation_position, terminal_position]),
        )

    def test_claude_commands_resolve_scripts_from_plugin_root(self):
        for command_name, path in self.command_files.items():
            with self.subTest(command_name=command_name):
                content = path.read_text(encoding="utf-8")
                if "python " not in content:
                    continue
                self.assertIn('${CLAUDE_PLUGIN_ROOT}/scripts/', content)
                self.assertNotIn("python scripts/", content)
        for command_name in ["/spl", "/spl:prd", "/spl:ui", "/spl:design", "/spl:run"]:
            with self.subTest(plugin_reads=command_name):
                content = self.command_files[command_name].read_text(encoding="utf-8")
                self.assertIn("${CLAUDE_PLUGIN_ROOT}/", content)
                self.assertNotRegex(content, r"读取 `(?:skills|agents|docs|schemas|configs)/")

    def test_claude_static_agent_scripts_resolve_from_plugin_root(self):
        for agent_name, path in self.static_agent_files.items():
            with self.subTest(agent_name=agent_name):
                content = path.read_text(encoding="utf-8")
                invocations = re.findall(r'python [^`\n]+?\.py"?', content)
                self.assertTrue(invocations)
                for invocation in invocations:
                    self.assertRegex(
                        invocation,
                        r'^python "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/[A-Za-z0-9_]+\.py"$',
                    )
                self.assertNotIn("python scripts/", content)

    def test_claude_static_agent_invocations_use_plugin_namespace(self):
        expected_by_command = {
            "/spl": ["analyst"],
            "/spl:prd": ["analyst"],
            "/spl:ui": ["ui-architect"],
            "/spl:design": ["architect"],
            "/spl:run": [
                "impact-analyzer",
                "code-reviewer",
                "system_merger",
                "tester",
                "workspace_applier",
                "requirement-verifier",
            ],
        }
        for command_name, agent_names in expected_by_command.items():
            content = self.command_files[command_name].read_text(encoding="utf-8")
            for agent_name in agent_names:
                with self.subTest(command_name=command_name, agent_name=agent_name):
                    self.assertRegex(
                        content,
                        rf"(?:调用|启动|重新调用) `superlooper:{re.escape(agent_name)}`",
                    )
                    self.assertNotRegex(
                        content,
                        rf"(?:调用|启动|重新调用) `{re.escape(agent_name)}`",
                    )

        skill_content = (
            self.repo_root / "skills" / "superlooper" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for agent_name in {
            agent_name
            for agent_names in expected_by_command.values()
            for agent_name in agent_names
        }:
            with self.subTest(skill_agent_name=agent_name):
                self.assertRegex(
                    skill_content,
                    rf"(?:调用|启动|重新调用) `superlooper:{re.escape(agent_name)}`",
                )
                self.assertNotRegex(
                    skill_content,
                    rf"(?:调用|启动|重新调用) `{re.escape(agent_name)}`",
                )

    def test_claude_design_flow_validates_and_forwards_initialization_advice(self):
        validator_command = (
            'validate_miao_contracts.py" --workspace-root <workspace_root> '
            '--task-id <task_id> --scope initialization-advice'
        )
        initialization_command = (
            'initialize_project_structure.py" --workspace-root <workspace_root> '
            '--task-id <task_id> --project-category <project_category> '
            '--project-version <project_version> --project-root <project_root>'
        )
        for path in (
            self.command_files["/spl:design"],
            self.repo_root / "skills" / "superlooper" / "SKILL.md",
        ):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn(validator_command, content)
                self.assertIn(initialization_command, content)
                self.assertLess(
                    content.index(validator_command),
                    content.index(initialization_command),
                )
                self.assertIn("不得从 project-profile.md 或自然语言猜测", content)

    def test_architect_contract_defines_initialization_advice_machine_block(self):
        expected_block = (
            "```yaml\n"
            "task_id: <task_id>\n"
            "project_category: springboot\n"
            "project_version: springboot-3.x\n"
            "project_root: .\n"
            "```"
        )
        for path in (
            self.repo_root / "agents" / "architect.md",
            self.repo_root / "docs" / "agent-flows" / "architect-flow.md",
        ):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn(expected_block, content)
                self.assertIn("第一个 YAML", content)

    def test_stage_review_feedback_uses_shared_resume_reducer(self):
        expected_replies = {
            "/spl:prd": ("PRD未通过，按反馈重新分析", "通过，进入 UI 设计"),
            "/spl:ui": ("UI设计未通过，按反馈重新设计", "UI设计通过，进入系统设计"),
            "/spl:design": ("设计未通过，按反馈重新设计",),
        }
        for command_name, replies in expected_replies.items():
            with self.subTest(command_name=command_name):
                content = self.command_files[command_name].read_text(encoding="utf-8")
                self.assertIn("resume_session.py", content)
                self.assertIn("--user-input", content)
                self.assertIn("共享 reducer", content)
                for reply in replies:
                    self.assertIn(reply, content)

    def test_business_subcommands_do_not_add_python_preflight(self):
        for command_name in ["/spl:prd", "/spl:ui", "/spl:design", "/spl:run", "/spl:status", "/spl:resume"]:
            with self.subTest(command_name=command_name):
                content = self.command_files[command_name].read_text(encoding="utf-8")
                self.assertNotIn("python --version", content)

    def test_canonical_examples_use_generated_14_digit_task_ids(self):
        legacy_date_id = re.compile(r"master-framework-\d{8}(?!\d)")
        for path in [
            self.repo_root / "skills" / "superlooper" / "SKILL.md",
            self.repo_root / "agents" / "developer.md",
        ]:
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIsNone(legacy_date_id.search(content), str(path))
                self.assertIn("master-framework-20260714143522", content)

    def test_canonical_task_id_terminology_is_not_session_identity(self):
        current_sources = [
            *sorted((self.repo_root / "agents").glob("*.md")),
            *sorted((self.repo_root / "scripts").glob("*.py")),
        ]
        for path in current_sources:
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertNotIn("执行会话 ID", content)
                self.assertNotIn("当前编排会话 ID", content)
                self.assertNotIn("`task_id` 必须等于当前会话 ID", content)
                self.assertNotIn("Show SUPERLOOPER session status", content)
                self.assertNotIn("Resolve the next action for a SUPERLOOPER session", content)
                self.assertNotIn("恢复 session 失败", content)
                self.assertNotIn("validated session", content)

    def test_current_agent_flows_use_task_id_report_paths(self):
        for path in sorted((self.repo_root / "docs" / "agent-flows").glob("*.md")):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertNotIn("<session_id>", content)

    def test_skill_defines_task_state_and_agent_session_boundaries(self):
        content = (self.repo_root / "skills" / "superlooper" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("**Task**", content)
        self.assertIn("**Task state / session state**", content)
        self.assertIn("**Agent session / parent session**", content)
        self.assertIn("**`session_id`**", content)
        self.assertNotIn("active session", content)
        self.assertNotIn("session 默认 `workflow_mode", content)
        self.assertNotIn("入口与会话准备", content)
        self.assertNotIn("确认 session", content)
        self.assertNotIn("当前会话一致", content)

    def test_authoritative_skill_routes_review_actions_through_shared_reducer(self):
        content = (self.repo_root / "skills" / "superlooper" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("${CLAUDE_PLUGIN_ROOT}", content)
        self.assertIn("resume_session.py", content)
        self.assertIn("--user-input <原始用户输入>", content)
        for action in [
            "approve_and_proceed",
            "prd_revision_requested",
            "approve_ui_and_proceed",
            "ui_revision_requested",
            "design_revision_requested",
        ]:
            self.assertIn(action, content)
        self.assertIn("不得手写第二套审核状态转换", content)

    def test_run_command_clears_local_rerun_scope_before_global_code_review(self):
        content = self.command_files["/spl:run"].read_text(encoding="utf-8")

        selected_complete_position = content.index(
            "所选模块全部完成且 artifact contract 校验通过"
        )
        clear_position = content.index("--clear-affected-modules")
        global_review_position = content.index(
            "进入全局 code review",
            clear_position,
        )
        self.assertEqual(
            [selected_complete_position, clear_position, global_review_position],
            sorted(
                [selected_complete_position, clear_position, global_review_position]
            ),
        )
        self.assertIn(
            "清空前中断恢复时继续按 state 中原 affected_modules 调度",
            content,
        )

    def test_authoritative_skill_clears_local_rerun_scope_after_artifact_validation(self):
        content = (
            self.repo_root / "skills" / "superlooper" / "SKILL.md"
        ).read_text(encoding="utf-8")

        artifact_position = content.index("**步骤D4**")
        clear_position = content.index("--clear-affected-modules", artifact_position)
        review_position = content.index("**步骤D5**", clear_position)
        self.assertEqual(
            [artifact_position, clear_position, review_position],
            sorted([artifact_position, clear_position, review_position]),
        )
        self.assertIn(
            "清空前中断恢复时继续按 state 中原 affected_modules 调度",
            content,
        )

    def test_manifest_example_is_labeled_as_non_canonical_relationship_example(self):
        content = (self.repo_root / "skills" / "superlooper" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("关键关系示意", content)
        self.assertIn("不能直接作为正式 `execution_manifest.json`", content)
        self.assertIn("generate_execution_manifest.py", content)
        self.assertIn("schemas/execution-manifest.schema.json", content)
        self.assertIn("validate_miao_contracts.py", content)

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
        actions = {action["name"]: action for action in run["canonical_actions"]}
        self.assertIn("execution_summary_approved", actions)
        self.assertIn("execution_summary_revision_requested", actions)
        self.assertIn("retry_execution_summary", actions)
        self.assertIn("按此执行", run["allowed_replies"])
        self.assertIn("执行摘要未通过，返回修正", run["allowed_replies"])
        self.assertIn("重试执行摘要", run["allowed_replies"])
        self.assertEqual(
            actions["retry_execution_summary"]["aliases"],
            ["重试执行摘要", "重新生成执行摘要", "阻断已修复，重试执行摘要", "阻断已修复，重新生成摘要"],
        )

    def test_execution_summary_blocked_recovery_is_fail_closed(self):
        run_content = self.command_files["/spl:run"].read_text(encoding="utf-8")
        resume_content = self.command_files["/spl:resume"].read_text(encoding="utf-8")
        skill_content = (self.repo_root / "skills" / "superlooper" / "SKILL.md").read_text(encoding="utf-8")

        for content in (run_content, resume_content, skill_content):
            self.assertIn("run/waiting_review + BLOCKED", content)
            self.assertIn("run/pending + NOT_STARTED", content)
            self.assertIn("重试执行摘要", content)
        self.assertIn("唯一 canonical 恢复动作", run_content)
        self.assertIn("不得以批准、执行、继续或状态查询恢复", resume_content)

    def test_claude_dynamic_agent_discovery_precedes_execution_approval_reducer(self):
        run_content = self.command_files["/spl:run"].read_text(encoding="utf-8")
        resume_content = self.command_files["/spl:resume"].read_text(encoding="utf-8")
        skill_content = (self.repo_root / "skills" / "superlooper" / "SKILL.md").read_text(encoding="utf-8")
        recovery = "启动新 Claude Code 会话，执行 `/superlooper:spl:resume <task_id>`，再次提交‘按此执行’。"

        discovery_position = run_content.index("Agent 工具可用类型列表")
        reducer_position = run_content.index(
            'resume_session.py" --workspace-root <workspace_root> --task-id <task_id> --user-input "按此执行"',
            discovery_position,
        )
        self.assertLess(discovery_position, reducer_position)
        self.assertIn("module_<module_id>__task_<sha256(task_id)[:16]>", run_content)
        self.assertIn("run/waiting_review + READY_FOR_APPROVAL", run_content)
        self.assertIn(recovery, run_content)
        self.assertIn(recovery, resume_content)
        self.assertIn(recovery, skill_content)
        self.assertIn("不得调用 reducer", resume_content)

    def test_strict_review_keeps_initialization_and_module_split_checkpoints(self):
        design_content = self.command_files["/spl:design"].read_text(encoding="utf-8")
        skill_content = (self.repo_root / "skills" / "superlooper" / "SKILL.md").read_text(encoding="utf-8")

        for content, anchor in (
            (design_content, "16. `strict_review`"),
            (skill_content, "**步骤B4.1（strict_review 设计审核）**"),
        ):
            start = content.index(anchor)
            design_review = content.index("design/waiting_review", start)
            initialization_review = content.index("initialization/waiting_review", design_review)
            module_review = content.index("design/waiting_review", initialization_review)
            run_pending = content.index("run/pending", module_review)
            self.assertEqual(
                [design_review, initialization_review, module_review, run_pending],
                sorted([design_review, initialization_review, module_review, run_pending]),
            )

    def test_design_command_limits_automatic_run_transition_to_standard_mode(self):
        design_content = self.command_files["/spl:design"].read_text(encoding="utf-8")

        self.assertIn(
            "15. `standard` 模式下，`module-split` 校验通过后",
            design_content,
        )

    def test_run_command_passes_raw_execution_summary_feedback_to_reducer(self):
        run_content = self.command_files["/spl:run"].read_text(encoding="utf-8")

        self.assertIn("--user-input <原始用户输入>", run_content)
        self.assertNotIn(
            '--user-input "执行摘要未通过，返回修正：<反馈内容>"',
            run_content,
        )

    def test_runtime_agent_generation_contract_preserves_existing_dynamic_agents(self):
        run_content = self.command_files["/spl:run"].read_text(encoding="utf-8")
        skill_content = (self.repo_root / "skills" / "superlooper" / "SKILL.md").read_text(encoding="utf-8")

        for content in (run_content, skill_content):
            self.assertIn("不得清理", content)
            self.assertIn("其他 task", content)

    def test_impact_recording_does_not_authorize_affected_modules(self):
        run_content = self.command_files["/spl:run"].read_text(encoding="utf-8")
        impact_checkpoint = next(
            command
            for command in re.findall(r'`([^`\n]*update_session\.py[^`\n]*)`', run_content)
            if "--change-impact-report" in command
        )
        self.assertNotIn("--affected-module", impact_checkpoint)
        self.assertIn("审核前必须保持空数组", run_content)

    def test_run_protocol_documents_review_digest_and_transaction_gates(self):
        run_content = self.command_files["/spl:run"].read_text(encoding="utf-8")
        skill_content = (self.repo_root / "skills" / "superlooper" / "SKILL.md").read_text(encoding="utf-8")

        for content in (run_content, skill_content):
            self.assertIn("reviewed_modules", content)
            self.assertIn("snapshot_digest", content)
            self.assertIn("事务", content)
            self.assertIn("rollback.status", content)
            self.assertIn("partial", content)

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
