import unittest
from pathlib import Path


EXPECTED_SKILLS = {
    "superlooper": {
        "entry": "$superlooper <requirement_path> [session_id]",
        "scripts": ("status_session.py", "normalize_user_intent.py", "create_session.py"),
    },
    "superlooper-prd": {
        "entry": "$superlooper-prd <requirement_path> [session_id]",
        "scripts": ("create_session.py", "normalize_user_intent.py"),
    },
    "superlooper-ui": {
        "entry": "$superlooper-ui <session_id>",
        "scripts": ("validate_miao_contracts.py",),
    },
    "superlooper-design": {
        "entry": "$superlooper-design <session_id>",
        "scripts": ("initialize_project_structure.py", "validate_miao_contracts.py"),
    },
    "superlooper-run": {
        "entry": "$superlooper-run <session_id>",
        "scripts": (
            "update_session.py",
            "generate_execution_manifest.py",
            "generate_runtime_agents.py",
            "validate_miao_contracts.py",
            "build_execution_summary.py",
            "resume_session.py",
        ),
    },
    "superlooper-status": {
        "entry": "$superlooper-status <session_id>",
        "scripts": ("status_session.py",),
    },
    "superlooper-resume": {
        "entry": "$superlooper-resume <session_id>",
        "scripts": ("normalize_user_intent.py", "resume_session.py"),
    },
    "superlooper-doctor": {
        "entry": "$superlooper-doctor [session_id]",
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

    def test_doctor_skill_requires_runtime_probe_before_diagnostics(self):
        skill_path = self.root / "codex" / "skills" / "superlooper-doctor" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")

        self.assertIn("python --version", content)
        self.assertIn("--platform codex", content)
        self.assertIn("不得以局部静态检查替代", content)
        self.assertIn("不得将 `scripts/doctor.py` 作为工作区相对路径执行", content)
        self.assertIn("plugin_root", content)
        self.assertIn("../../..", content)
        self.assertIn("--workspace-root . --platform codex", content)
        self.assertIn("workspace-write", content)
        self.assertNotIn("read-only", content)

    def test_run_skill_uses_the_shared_preparation_and_resume_gates(self):
        skill_path = self.root / "codex" / "skills" / "superlooper-run" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")

        expected_commands = [
            "<plugin_root>/scripts/update_session.py --workspace-root . --session-id <session_id>",
            "<plugin_root>/scripts/generate_execution_manifest.py --workspace-root . --session-id <session_id> --platform codex",
            "<plugin_root>/scripts/generate_runtime_agents.py --workspace-root . --session-id <session_id> --agents-dir agents --platform codex",
            "<plugin_root>/scripts/validate_miao_contracts.py --workspace-root . --session-id <session_id> --agents-dir agents --scope execution",
            "<plugin_root>/scripts/build_execution_summary.py --workspace-root . --session-id <session_id>",
            "<plugin_root>/scripts/validate_miao_contracts.py --workspace-root . --session-id <session_id> --scope execution-summary",
        ]
        for command in expected_commands:
            self.assertIn(command, content)
        command_positions = [content.index(command) for command in expected_commands]
        self.assertEqual(command_positions, sorted(command_positions))
        self.assertIn("<plugin_root>/scripts/resume_session.py --workspace-root . --session-id <session_id>", content)
        self.assertNotIn("read-only", content)

    def test_dispatcher_consumes_the_shared_manifest_without_a_dag_copy(self):
        dispatcher_path = self.root / "codex" / "dispatcher" / "README.md"
        self.assertTrue(dispatcher_path.is_file())
        content = dispatcher_path.read_text(encoding="utf-8")

        self.assertIn("execution_manifest.json", content)
        self.assertIn("spawn_agent", content)
        self.assertIn("artifact_manifest.json", content)
        self.assertNotIn(".claude/agents/generated/", content)
        self.assertNotIn("codex-dispatch.json", content)
        self.assertNotIn("read-only", content)


if __name__ == "__main__":
    unittest.main()
