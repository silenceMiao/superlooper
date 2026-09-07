import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class DoctorScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name) / "workspace"
        shutil.copytree(
            self.repo_root,
            self.workspace_root,
            ignore=shutil.ignore_patterns("__pycache__", ".superlooper", "dist", ".git"),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_doctor(self, *args, env=None):
        return subprocess.run(
            [
                sys.executable,
                str(self.workspace_root / "scripts" / "doctor.py"),
                "--workspace-root",
                str(self.workspace_root),
                *args,
            ],
            cwd=self.workspace_root,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def run_bin(self, *args):
        return subprocess.run(
            [
                sys.executable,
                str(self.workspace_root / "bin" / "spl"),
                *args,
            ],
            cwd=self.workspace_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_doctor_success_outputs_required_checks(self):
        result = self.run_doctor()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = result.stdout
        for check_name in [
            "plugin_validate",
            "python_compile",
            "commands_contract",
            "schema_contract",
            "agent_contract",
            "forbidden_manifest_command",
            "release_filter",
            "codex_plugin",
            "codex_skills",
            "codex_dispatcher",
            "session_contract",
        ]:
            self.assertIn(f"{check_name}: ", output)
        self.assertIn("session_contract: SKIPPED", output)
        self.assertIn("agent_contract: PASS - found 10 agent files", output)

    def test_codex_doctor_does_not_require_claude_cli(self):
        env = os.environ.copy()
        env["PATH"] = str(Path(sys.executable).parent)

        result = self.run_doctor("--platform", "codex", env=env)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("codex_plugin: PASS", result.stdout)
        self.assertNotIn("plugin_validate: ", result.stdout)

    def test_codex_python_compile_does_not_write_bytecode_to_plugin_root(self):
        sys.path.insert(0, str(self.workspace_root / "scripts"))
        try:
            from doctor import DoctorRunner

            runner = DoctorRunner(workspace_root=self.workspace_root, plugin_root=self.workspace_root, platform="codex")
            with mock.patch.object(runner, "_run_command", side_effect=AssertionError("py_compile subprocess must not run")):
                status, message = runner.check_python_compile()
        finally:
            sys.path.pop(0)
            sys.modules.pop("doctor", None)

        self.assertEqual("PASS", status)
        self.assertIn("compiled", message)

    def test_doctor_skips_session_contract_without_session_id(self):
        result = self.run_doctor()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("session_contract: SKIPPED", result.stdout)

    def test_doctor_fails_when_required_schema_file_is_missing(self):
        schema_path = self.workspace_root / "schemas" / "execution-manifest.schema.json"
        schema_path.unlink()

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("schema_contract: FAIL", result.stdout)

    def test_claude_python_compile_does_not_write_bytecode_to_plugin_root(self):
        sys.path.insert(0, str(self.workspace_root / "scripts"))
        try:
            from doctor import DoctorRunner

            runner = DoctorRunner(workspace_root=self.workspace_root, plugin_root=self.workspace_root, platform="claude")
            with mock.patch.object(runner, "_run_command", side_effect=AssertionError("py_compile subprocess must not run")):
                status, message = runner.check_python_compile()
        finally:
            sys.path.pop(0)
            sys.modules.pop("doctor", None)

        self.assertEqual("PASS", status)
        self.assertIn("compiled", message)

    def test_doctor_fails_when_schema_json_is_malformed(self):
        schema_path = self.workspace_root / "schemas" / "execution-manifest.schema.json"
        schema_path.write_text("{broken json", encoding="utf-8")

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("schema_contract: FAIL", result.stdout)

    def test_doctor_fails_when_codex_manifest_skills_path_is_invalid(self):
        manifest_path = self.workspace_root / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["skills"] = "./outside/skills/"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("codex_plugin: FAIL", result.stdout)

    def test_doctor_fails_when_codex_skill_name_does_not_match_directory(self):
        skill_path = self.workspace_root / "codex" / "skills" / "superlooper-run" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        skill_path.write_text(content.replace("name: superlooper-run", "name: wrong-name", 1), encoding="utf-8")

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("codex_skills: FAIL", result.stdout)

    def test_doctor_fails_when_codex_skill_description_is_empty(self):
        skill_path = self.workspace_root / "codex" / "skills" / "superlooper-run" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        skill_path.write_text(content.replace("description: Prepare and execute the Superlooper run stage through the Codex native adapter.", "description:", 1), encoding="utf-8")

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("codex_skills: FAIL", result.stdout)

    def test_doctor_rejects_forbidden_manifest_command_file(self):
        forbidden_path = self.workspace_root / "commands" / "spl" / "manifest.md"
        forbidden_path.write_text("# forbidden\n", encoding="utf-8")

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden_manifest_command: FAIL", result.stdout)

    def test_doctor_release_filter_excludes_development_only_files(self):
        result = self.run_doctor()
        manifest_path = self.workspace_root / "dist" / "superlooper-release-manifest.json"

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("release_filter: PASS", result.stdout)
        self.assertFalse(manifest_path.exists())

        sys.path.insert(0, str(self.workspace_root))
        try:
            from scripts.package_plugin import PluginPackager

            release_files = set(PluginPackager(root=self.workspace_root, mode="install")._build_release_file_list())
        finally:
            sys.path.pop(0)
        self.assertTrue(
            {
                "CHANGELOG.md",
                "docs/DEVELOPMENT.md",
                "docs/RELEASE.md",
                "scripts/build_release_archive.py",
            }.isdisjoint(release_files)
        )

    def test_doctor_release_filter_requires_user_guide(self):
        (self.workspace_root / "docs" / "USER_GUIDE.md").unlink()

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release_filter: FAIL", result.stdout)
        self.assertIn("docs/USER_GUIDE.md", result.stdout)

    def test_doctor_release_filter_runs_secret_scan(self):
        secret_path = self.workspace_root / "README.md"
        secret_path.write_text("secret" + "_key: live_secret_value\n", encoding="utf-8")

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release_filter: FAIL", result.stdout)
        self.assertIn("secret", result.stdout.lower())

    def test_bin_spl_routes_doctor_command(self):
        result = self.run_bin("doctor")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("plugin_validate: PASS", result.stdout)
        self.assertIn("agent_contract: PASS", result.stdout)
        self.assertIn("session_contract: SKIPPED", result.stdout)


if __name__ == "__main__":
    unittest.main()
