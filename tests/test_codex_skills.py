import re
import unittest
from pathlib import Path


EXPECTED_SKILLS = {
    "superlooper": {
        "entry": "$superlooper <requirement_path> [--task-name \"<task_name>\"]",
        "scripts": ("status_session.py", "normalize_user_intent.py", "resume_session.py", "create_session.py"),
    },
    "superlooper-prd": {
        "entry": "$superlooper-prd <requirement_path> [task_id]",
        "scripts": ("create_session.py", "update_session.py", "resume_session.py"),
    },
    "superlooper-ui": {
        "entry": "$superlooper-ui <task_id>",
        "scripts": ("update_session.py", "validate_miao_contracts.py", "resume_session.py"),
    },
    "superlooper-design": {
        "entry": "$superlooper-design <task_id>",
        "scripts": ("update_session.py", "initialize_project_structure.py", "validate_miao_contracts.py", "resume_session.py"),
    },
    "superlooper-run": {
        "entry": "$superlooper-run <task_id>",
        "scripts": (
            "update_session.py",
            "generate_execution_manifest.py",
            "generate_runtime_agents.py",
            "render_codex_spawn_prompt.py",
            "validate_miao_contracts.py",
            "build_execution_summary.py",
            "resume_session.py",
        ),
    },
    "superlooper-status": {
        "entry": "$superlooper-status <task_id>",
        "scripts": ("status_session.py",),
    },
    "superlooper-resume": {
        "entry": "$superlooper-resume <task_id>",
        "scripts": ("normalize_user_intent.py", "resume_session.py"),
    },
    "superlooper-doctor": {
        "entry": "$superlooper-doctor [task_id]",
        "scripts": ("doctor.py",),
    },
}


class CodexSkillStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_each_codex_skill_uses_the_shared_session_contract(self):
        for skill_name, expected in EXPECTED_SKILLS.items():
            with self.subTest(skill_name=skill_name):
                skill_path = self.root / "codex" / "skills" / skill_name / "SKILL.md"
                self.assertTrue(skill_path.is_file())
                content = skill_path.read_text(encoding="utf-8")

                self.assertIn(f"name: {skill_name}", content)
                self.assertIn("description:", content)
                self.assertIn(expected["entry"], content)
                self.assertIn(".superlooper/", content)
                for script_name in expected["scripts"]:
                    self.assertIn(script_name, content)
                self.assertIn("plugin_root", content)
                self.assertIn("../../..", content)
                self.assertNotIn(".claude/agents/generated/", content)
                self.assertNotIn("$ARGUMENTS", content)
                self.assertNotIn("/superlooper:spl", content)

    def test_main_skill_preflights_python_before_business_actions(self):
        skill_path = self.root / "codex" / "skills" / "superlooper" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")

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
            ".superlooper/",
            "status_session.py",
            "normalize_user_intent.py",
            "resume_session.py",
            "create_session.py",
            "Codex analyst",
        ]:
            self.assertGreater(content.index(later_action), version_position)
        self.assertIn("--task-name", content)
        self.assertNotIn("master-framework-<YYYYMMDD>", content)

    def test_main_skill_uses_active_listing_resume_and_isolated_creation(self):
        skill_path = self.root / "codex" / "skills" / "superlooper" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")

        self.assertIn('status_session.py" --workspace-root . --list-active', content)
        self.assertIn('normalize_user_intent.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>', content)
        self.assertIn('resume_session.py" --workspace-root . --task-id <task_id> --user-input <原始用户输入>', content)
        self.assertIn('create_session.py" --workspace-root . --new-task', content)
        self.assertIn("single argv", content)
        self.assertIn("shell source", content)

    def test_all_shared_python_scripts_use_the_interpreter_and_quoted_plugin_root(self):
        for skill_name in EXPECTED_SKILLS:
            with self.subTest(skill_name=skill_name):
                content = (
                    self.root / "codex" / "skills" / skill_name / "SKILL.md"
                ).read_text(encoding="utf-8")
                naked_calls = re.findall(r'(?<!python ")<plugin_root>/scripts/[a-z_]+\.py', content)
                self.assertEqual(naked_calls, [], content)

    def test_stage_checkpoint_commands_include_required_update_arguments(self):
        for skill_name in ["superlooper-prd", "superlooper-ui", "superlooper-design"]:
            with self.subTest(skill_name=skill_name):
                content = (
                    self.root / "codex" / "skills" / skill_name / "SKILL.md"
                ).read_text(encoding="utf-8")
                commands = re.findall(r'`([^`\n]*update_session\.py[^`\n]*)`', content)
                self.assertTrue(commands, content)
                for command in commands:
                    self.assertIn("--current-phase", command)
                    self.assertIn("--phase-status", command)
                    self.assertIn("--last-command", command)

    def test_main_skill_enters_the_canonical_prd_checkpoint_chain_after_creation(self):
        content = (
            self.root / "codex" / "skills" / "superlooper" / "SKILL.md"
        ).read_text(encoding="utf-8")

        create_position = content.index("create_session.py")
        running_position = content.index("--current-phase prd --phase-status running", create_position)
        analyst_position = content.index("Codex analyst", running_position)
        validation_position = content.index("Validate the analyst status block and PRD artifact contract", analyst_position)
        terminal_position = content.index("--phase-status waiting_review", validation_position)
        self.assertEqual(
            [create_position, running_position, analyst_position, validation_position, terminal_position],
            sorted([create_position, running_position, analyst_position, validation_position, terminal_position]),
        )

    def test_stage_skills_record_checkpoints_and_use_shared_reducer(self):
        for skill_name in ["superlooper-prd", "superlooper-ui", "superlooper-design"]:
            with self.subTest(skill_name=skill_name):
                skill_path = self.root / "codex" / "skills" / skill_name / "SKILL.md"
                content = skill_path.read_text(encoding="utf-8")
                self.assertIn("update_session.py", content)
                self.assertIn("--phase-status running", content)
                self.assertRegex(content, r"--phase-status (waiting_review|pending)")
                self.assertRegex(content, r"--phase-status (blocked|failed)")
                self.assertIn("resume_session.py", content)
                self.assertIn("--user-input <原始用户输入>", content)
                self.assertIn("shared reducer", content)

    def test_design_skill_validates_and_forwards_initialization_advice(self):
        content = (
            self.root / "codex" / "skills" / "superlooper-design" / "SKILL.md"
        ).read_text(encoding="utf-8")
        validator_command = (
            'python "<plugin_root>/scripts/validate_miao_contracts.py" '
            '--workspace-root . --task-id <task_id> --scope initialization-advice'
        )
        initialization_command = (
            'python "<plugin_root>/scripts/initialize_project_structure.py" '
            '--workspace-root . --task-id <task_id> '
            '--project-category <project_category> '
            '--project-version <project_version> --project-root <project_root>'
        )

        self.assertIn(validator_command, content)
        self.assertIn(initialization_command, content)
        self.assertLess(
            content.index(validator_command),
            content.index(initialization_command),
        )
        self.assertIn("must not infer", content)
        self.assertIn("first YAML block", content)

    def test_design_skill_preserves_strict_review_state_sequence(self):
        content = (
            self.root / "codex" / "skills" / "superlooper-design" / "SKILL.md"
        ).read_text(encoding="utf-8")

        start = content.index("In `strict_review` mode")
        design_review = content.index("design --phase-status waiting_review", start)
        initialization_review = content.index("initialization/waiting_review", design_review)
        module_review = content.index("design/waiting_review", initialization_review)
        run_pending = content.index("run/pending", module_review)
        self.assertEqual(
            [design_review, initialization_review, module_review, run_pending],
            sorted([design_review, initialization_review, module_review, run_pending]),
        )
        self.assertIn("Do not collapse category selection, version selection, and module-split review", content)

    def test_business_subskills_do_not_add_python_preflight(self):
        for skill_name in [
            "superlooper-prd",
            "superlooper-ui",
            "superlooper-design",
            "superlooper-run",
            "superlooper-status",
            "superlooper-resume",
        ]:
            with self.subTest(skill_name=skill_name):
                skill_path = self.root / "codex" / "skills" / skill_name / "SKILL.md"
                content = skill_path.read_text(encoding="utf-8")
                self.assertNotIn("python --version", content)

    def test_doctor_skill_requires_runtime_probe_before_diagnostics(self):
        skill_path = self.root / "codex" / "skills" / "superlooper-doctor" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")

        self.assertIn("python --version", content)
        self.assertIn("sys.version_info >= (3, 9)", content)
        self.assertIn("Python 3.9+", content)
        self.assertIn("Doctor 未启动：runtime prerequisite unavailable", content)
        self.assertLess(content.index("python --version"), content.index("sys.version_info >= (3, 9)"))
        self.assertLess(content.index("sys.version_info >= (3, 9)"), content.index("doctor.py"))
        self.assertIn("--platform codex", content)
        self.assertIn("不得以局部静态检查替代", content)
        self.assertIn("不得将 `scripts/doctor.py` 作为工作区相对路径执行", content)
        self.assertIn("plugin_root", content)
        self.assertIn("../../..", content)
        self.assertIn("--workspace-root . --platform codex", content)
        self.assertIn("read-only", content)
        self.assertNotIn("workspace-write", content)
        self.assertNotIn("session ID", content)
        self.assertNotIn("session-contract", content)

    def test_status_skill_is_read_only(self):
        skill_path = self.root / "codex" / "skills" / "superlooper-status" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")

        self.assertIn("read-only", content)
        self.assertNotIn("workspace-write", content)

    def test_run_skill_uses_the_shared_preparation_and_resume_gates(self):
        skill_path = self.root / "codex" / "skills" / "superlooper-run" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")

        expected_commands = [
            'python "<plugin_root>/scripts/update_session.py" --workspace-root . --task-id <task_id>',
            'python "<plugin_root>/scripts/generate_execution_manifest.py" --workspace-root . --task-id <task_id> --platform codex',
            'python "<plugin_root>/scripts/generate_runtime_agents.py" --workspace-root . --task-id <task_id> --agents-dir agents --platform codex',
            'python "<plugin_root>/scripts/validate_miao_contracts.py" --workspace-root . --task-id <task_id> --agents-dir agents --scope execution',
            'python "<plugin_root>/scripts/build_execution_summary.py" --workspace-root . --task-id <task_id>',
            'python "<plugin_root>/scripts/validate_miao_contracts.py" --workspace-root . --task-id <task_id> --scope execution-summary',
        ]
        for command in expected_commands:
            self.assertIn(command, content)
        command_positions = [content.index(command) for command in expected_commands]
        self.assertEqual(command_positions, sorted(command_positions))
        self.assertIn('python "<plugin_root>/scripts/resume_session.py" --workspace-root . --task-id <task_id>', content)
        self.assertIn("--user-input <原始用户输入>", content)
        self.assertIn("original user text", content)
        self.assertNotIn("<shared canonical feedback>", content)
        self.assertNotIn("read-only", content)
        self.assertIn(
            'python "<plugin_root>/scripts/render_codex_spawn_prompt.py" --workspace-root . --task-id <task_id> --node-id <node_id>',
            content,
        )
        self.assertIn('spawn_agent(..., fork_turns="none", message=<renderer stdout>)', content)
        self.assertIn("完整 stdout", content)
        self.assertIn("Codex does not perform Claude registered-Agent discovery", content)
        self.assertIn("logical names through the renderer", content)

    def test_run_and_resume_skills_keep_blocked_summary_fail_closed(self):
        for skill_name in ("superlooper-run", "superlooper-resume"):
            with self.subTest(skill_name=skill_name):
                content = (
                    self.root / "codex" / "skills" / skill_name / "SKILL.md"
                ).read_text(encoding="utf-8")
                self.assertIn("重试执行摘要", content)
                self.assertIn("run/waiting_review + BLOCKED", content)
                self.assertIn("run/pending + NOT_STARTED", content)

    def test_run_skill_does_not_preapprove_impact_modules(self):
        content = (
            self.root / "codex" / "skills" / "superlooper-run" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("do not pass `--affected-module`", content)
        self.assertIn("Only after the shared reducer approves", content)
        self.assertNotIn("first persist every reported module", content)

    def test_run_skill_documents_full_review_digest_and_apply_transaction(self):
        content = (
            self.root / "codex" / "skills" / "superlooper-run" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("reviewed_modules", content)
        self.assertIn("complete Manifest module-ID set", content)
        self.assertIn("snapshot_digest", content)
        self.assertIn("transactionally publishes", content)
        self.assertIn("success-report publication failure must roll it back", content)

    def test_run_skill_clears_local_rerun_scope_before_global_code_review(self):
        content = (
            self.root / "codex" / "skills" / "superlooper-run" / "SKILL.md"
        ).read_text(encoding="utf-8")

        selected_complete_position = content.index(
            "selected modules finish and their artifact contracts pass"
        )
        clear_position = content.index("--clear-affected-modules")
        global_review_position = content.index(
            "global code review",
            clear_position,
        )
        self.assertEqual(
            [selected_complete_position, clear_position, global_review_position],
            sorted(
                [selected_complete_position, clear_position, global_review_position]
            ),
        )
        self.assertIn(
            "Before this checkpoint, resume dispatches the original state affected_modules",
            content,
        )

    def test_prd_and_design_skills_record_all_terminal_checkpoints(self):
        prd_content = (
            self.root / "codex" / "skills" / "superlooper-prd" / "SKILL.md"
        ).read_text(encoding="utf-8")
        design_content = (
            self.root / "codex" / "skills" / "superlooper-design" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("--current-phase prd --phase-status failed", prd_content)
        self.assertIn("--last-error", prd_content)
        self.assertIn("--next-action", prd_content)
        self.assertIn("--current-phase design --phase-status waiting_review", design_content)

    def test_dispatcher_consumes_the_shared_manifest_without_a_dag_copy(self):
        dispatcher_path = self.root / "codex" / "dispatcher" / "README.md"
        self.assertTrue(dispatcher_path.is_file())
        content = dispatcher_path.read_text(encoding="utf-8")

        self.assertIn("execution_manifest.json", content)
        self.assertIn("spawn_agent", content)
        self.assertIn("artifact_manifest.json", content)
        self.assertIn("render_codex_spawn_prompt.py", content)
        self.assertIn('spawn_agent(..., fork_turns="none", message=<renderer stdout>)', content)
        self.assertIn("完整 stdout", content)
        self.assertNotIn(".claude/agents/generated/", content)
        self.assertNotIn("codex-dispatch.json", content)
        self.assertNotIn("read-only", content)


if __name__ == "__main__":
    unittest.main()
