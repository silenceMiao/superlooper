import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from scripts.package_plugin import INSTALL_RUNTIME_REQUIRED_FILES, PackageError, PluginPackager


class PackagePluginReleaseBehaviorTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self._create_minimal_plugin_tree()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_minimal_plugin_tree(self):
        files = {
            ".claude-plugin/plugin.json": '{"name":"superlooper","version":"1.0.0"}\n',
            "README.md": "# test plugin\n",
            "CHANGELOG.md": "# Changelog\n\n## 1.0.0\n",
            "LICENSE": "Apache-2.0\n",
            "commands/spl.md": "# /spl\n",
            "commands/spl/ui.md": "# /spl:ui\n",
            "commands/spl/run.md": "# /spl:run\n",
            "skills/superlooper/SKILL.md": "# skill\n",
            "agents/ui-architect.md": "---\nname: ui-architect\ndescription: ui architect\n---\n\n# ui architect\n",
            "agents/impact-analyzer.md": "---\nname: impact-analyzer\ndescription: impact analyzer\n---\n\n# impact analyzer\n",
            "docs/DEVELOPMENT.md": "# dev\n",
            "docs/RELEASE.md": "# release\n",
            "docs/design/demo.md": "# Demo design\n",
            "docs/agent-flows/ui-architect-flow.md": "# ui flow\n",
            "scripts/build_execution_summary.py": "print('summary')\n",
            "scripts/normalize_user_intent.py": "print('normalize')\n",
            "scripts/doctor.py": "print('doctor')\n",
            "bin/spl": "print('doctor route')\n",
            "tests/test_package_plugin.py": "# retained in source mode\n",
            ".superlooper/context/demo/prd.md": "runtime\n",
            ".claude/CLAUDE.md": "private\n",
            ".learnings/note.md": "private\n",
            "docs/superpowers/plans/demo.md": "private\n",
            "dist/old.zip": "old\n",
            "scripts/__pycache__/cached.pyc": "cache\n",
            "nested/__pycache__/cached.pyc": "cache\n",
            ".env": "NAME=value\n",
            ".env.local": "NAME=value\n",
            "module/.env": "NAME=value\n",
            "module/.env.prod": "NAME=value\n",
            "src/module.py": "print('ok')\n",
        }
        for relative_path in INSTALL_RUNTIME_REQUIRED_FILES:
            content = "---\ndescription: runtime file\n---\n\n# runtime file\n" if relative_path.startswith(("agents/", "commands/")) else "# runtime file\n"
            files.setdefault(relative_path, content)
        files["docs/USER_GUIDE.md"] = "<!-- public-readme:start -->\n# test plugin\n<!-- public-readme:end -->\n"
        files["README.md"] = "# test plugin\n"
        for relative_path, content in files.items():
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _build_packager(self, mode="source"):
        return PluginPackager(root=self.root, mode=mode)

    def _run_without_external_validation(self, packager):
        with mock.patch.object(packager, "_run_validate"), mock.patch.object(
            packager,
            "_run_py_compile",
            return_value=["scripts/package_plugin.py", "scripts/build_release_archive.py"],
        ):
            packager.run()

    def test_source_mode_keeps_tests_and_install_mode_excludes_them(self):
        source_packager = self._build_packager(mode="source")
        install_packager = self._build_packager(mode="install")

        source_files = source_packager._build_release_file_list()
        install_files = install_packager._build_release_file_list()

        self.assertIn("tests/test_package_plugin.py", source_files)
        self.assertNotIn("tests/test_package_plugin.py", install_files)
        self.assertIn("docs/design/demo.md", source_files)
        self.assertNotIn("docs/design/demo.md", install_files)
        self.assertTrue(all(not name.startswith("docs/design/") for name in install_files))

    def test_release_file_list_rejects_mocked_symlink_file(self):
        linked_file = self.root / "linked.py"
        linked_file.write_text("print('linked')\n", encoding="utf-8")
        original_is_symlink = Path.is_symlink

        def mocked_is_symlink(path):
            if path == linked_file:
                return True
            return original_is_symlink(path)

        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=mocked_is_symlink):
            with self.assertRaisesRegex(PackageError, "linked.py"):
                self._build_packager(mode="source")._build_release_file_list()

    def test_install_mode_excludes_development_only_files(self):
        install_files = set(self._build_packager(mode="install")._build_release_file_list())

        development_only_files = {
            "CHANGELOG.md",
            "docs/DEVELOPMENT.md",
            "docs/RELEASE.md",
            "docs/superlooper-flow-weight-and-handshake-analysis-v3.md",
            "docs/superlooper-flow-weight-and-handshake-implementation-v3.md",
            "settings.json",
            ".mcp.json",
            ".lsp.json",
            ".gitignore",
            "bin/.gitkeep",
            "scripts/build_release_archive.py",
            "scripts/package_marketplace.py",
        }

        self.assertTrue(development_only_files.isdisjoint(install_files))

    def test_claude_plugin_manifest_is_always_retained(self):
        for mode in ("source", "install"):
            with self.subTest(mode=mode):
                release_files = self._build_packager(mode=mode)._build_release_file_list()
                self.assertIn(".claude-plugin/plugin.json", release_files)

    def test_required_runtime_files_are_retained(self):
        required_files = {
            ".claude-plugin/plugin.json",
            "commands/spl.md",
            "commands/spl/ui.md",
            "commands/spl/run.md",
            "skills/superlooper/SKILL.md",
            "agents/ui-architect.md",
            "agents/impact-analyzer.md",
            "docs/agent-flows/ui-architect-flow.md",
            "scripts/build_execution_summary.py",
            "scripts/normalize_user_intent.py",
            "scripts/doctor.py",
            "bin/spl",
        }
        for mode in ("source", "install"):
            with self.subTest(mode=mode):
                release_files = set(self._build_packager(mode=mode)._build_release_file_list())
                self.assertTrue(required_files.issubset(release_files))

    def test_install_mode_retains_user_guide(self):
        release_files = self._build_packager(mode="install")._build_release_file_list()

        self.assertIn("docs/USER_GUIDE.md", release_files)

    def test_packager_rejects_source_readme_drift(self):
        packager = self._build_packager(mode="install")
        (self.root / "README.md").write_text("manual edit\n", encoding="utf-8")

        with mock.patch.object(packager, "_run_validate"), mock.patch.object(packager, "_run_py_compile", return_value=[]):
            with self.assertRaisesRegex(Exception, "README 未由用户指南生成"):
                packager.run()

    def test_normalize_user_intent_script_is_retained(self):
        for mode in ("source", "install"):
            with self.subTest(mode=mode):
                release_files = self._build_packager(mode=mode)._build_release_file_list()
                self.assertIn("scripts/normalize_user_intent.py", release_files)

    def test_schema_validation_script_is_retained(self):
        for mode in ("source", "install"):
            with self.subTest(mode=mode):
                release_files = self._build_packager(mode=mode)._build_release_file_list()
                self.assertIn("scripts/schema_validation.py", release_files)

    def test_install_mode_requires_codex_adapter_files(self):
        release_files = set(self._build_packager(mode="install")._build_release_file_list())
        required_codex_files = {
            ".codex-plugin/plugin.json",
            "codex/dispatcher/README.md",
            "codex/skills/superlooper/SKILL.md",
            "codex/skills/superlooper-prd/SKILL.md",
            "codex/skills/superlooper-ui/SKILL.md",
            "codex/skills/superlooper-design/SKILL.md",
            "codex/skills/superlooper-run/SKILL.md",
            "codex/skills/superlooper-status/SKILL.md",
            "codex/skills/superlooper-resume/SKILL.md",
            "codex/skills/superlooper-doctor/SKILL.md",
        }

        self.assertTrue(required_codex_files.issubset(release_files))

    def test_forbidden_paths_are_always_excluded(self):
        forbidden_paths = {
            ".superlooper/context/demo/prd.md",
            ".claude/CLAUDE.md",
            ".learnings/note.md",
            "docs/superpowers/plans/demo.md",
            "dist/old.zip",
            "scripts/__pycache__/cached.pyc",
            "nested/__pycache__/cached.pyc",
            ".env",
            ".env.local",
            "module/.env",
            "module/.env.prod",
        }

        for mode in ("source", "install"):
            with self.subTest(mode=mode):
                release_files = set(self._build_packager(mode=mode)._build_release_file_list())
                self.assertTrue(forbidden_paths.isdisjoint(release_files))

    def test_secret_patterns_block_release(self):
        secret_cases = {
            "docs/bearer.md": "Authorization:" " Bearer " "abc123token\n",
            "docs/access_key.md": "access" + "_key = " + "live_access_value\n",
            "docs/access_key_quoted.md": 'access' + '_key = "live_access_value"\n',
            "docs/secret_key.md": "secret" + "_key: " + "live_secret_value\n",
            "docs/secret_key_quoted.md": 'secret' + '_key: "live_secret_value"\n',
            "docs/private_key.md": "private" + "_key = " + "live_private_value\n",
            "docs/private_key_single_quoted.md": "private" + "_key = 'live_private_value'\n",
            "docs/pem.md": "-----BEGIN PRIVATE" " KEY-----\nABC\n",
            "docs/jdbc.md": "jdbc:mysql://" "user:pass@host/db\n",
            "docs/url.md": "https://" "user:pass@example.com/path\n",
        }

        for relative_path, content in secret_cases.items():
            with self.subTest(path=relative_path):
                path = self.root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                packager = self._build_packager(mode="source")
                release_files = packager._build_release_file_list()
                with self.assertRaises(PackageError):
                    packager._scan_secrets(release_files)
                path.unlink()

    def test_secret_scan_does_not_flag_field_names_without_values(self):
        doc_path = self.root / "docs/fields.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(
            "access_key = <value>\nsecret_key: <value>\nprivate_key = <value>\nAuthorization: Bearer <token>\n",
            encoding="utf-8",
        )
        packager = self._build_packager(mode="source")
        release_files = packager._build_release_file_list()
        packager._scan_secrets(release_files)

    def test_release_manifest_contains_mode_and_no_absolute_paths(self):
        packager = self._build_packager(mode="install")
        self._run_without_external_validation(packager)

        manifest = json.loads(packager.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual("install", manifest["release_mode"])
        self.assertEqual(".", manifest["workspace_root"])
        for command in manifest["validation_commands"]:
            self.assertNotIn(str(self.root), command)
        for relative_path in manifest["release_files"]:
            self.assertFalse(Path(relative_path).is_absolute())
            self.assertNotIn(str(self.root), relative_path)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build_packager(mode="invalid")


class RepositoryVersionContractTest(unittest.TestCase):
    def test_plugin_version_has_changelog_entry(self):
        repo_root = Path(__file__).resolve().parents[1]
        plugin_manifest = json.loads((repo_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn(f"## {plugin_manifest['version']}", changelog)

    def test_runtime_license_and_manifests_are_mit_and_dual_platform(self):
        repo_root = Path(__file__).resolve().parents[1]
        claude_manifest = json.loads((repo_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        codex_manifest_path = repo_root / ".codex-plugin" / "plugin.json"

        self.assertEqual("MIT", claude_manifest["license"])
        self.assertTrue(codex_manifest_path.is_file())
        codex_manifest = json.loads(codex_manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("MIT", codex_manifest["license"])
        self.assertIn("MIT License", (repo_root / "LICENSE").read_text(encoding="utf-8"))


class InstallArtifactSmokeTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.repo_root = Path(__file__).resolve().parents[1]

    def tearDown(self):
        self.temp_dir.cleanup()

    def copy_repo_source(self):
        source_root = self.temp_root / "source"
        shutil.copytree(
            self.repo_root,
            source_root,
            ignore=shutil.ignore_patterns(".claude", ".superlooper", ".learnings", "dist", "__pycache__", "*.pyc"),
        )
        return source_root

    def test_install_archive_extracts_and_runs_doctor_smoke(self):
        source_root = self.copy_repo_source()
        result = subprocess.run(
            [
                sys.executable,
                "scripts/build_release_archive.py",
                "--mode",
                "install",
            ],
            cwd=source_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)

        version = json.loads((source_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        archive_path = source_root / "dist" / f"superlooper-{version}-install.zip"
        self.assertTrue(archive_path.is_file())
        extract_root = self.temp_root / "artifact"
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_root)
            archive_names = set(archive.namelist())

        required_files = {
            ".claude-plugin/plugin.json",
            "commands/spl.md",
            "commands/spl/ui.md",
            "commands/spl/run.md",
            "skills/superlooper/SKILL.md",
            "agents/ui-architect.md",
            "agents/impact-analyzer.md",
            "docs/agent-flows/ui-architect-flow.md",
            "scripts/build_execution_summary.py",
            "scripts/normalize_user_intent.py",
            "scripts/doctor.py",
            "bin/spl",
        }
        self.assertTrue(required_files.issubset(archive_names))
        self.assertTrue(all(not name.startswith("tests/") for name in archive_names))
        self.assertTrue(all(not name.startswith("docs/design/") for name in archive_names))
        self.assertTrue(all(not name.startswith(".superlooper/") for name in archive_names))
        self.assertTrue(all(not name.startswith(".claude/") for name in archive_names))
        self.assertTrue(all(not name.startswith("dist/") for name in archive_names))

        smoke = subprocess.run(
            [sys.executable, "bin/spl", "doctor"],
            cwd=extract_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(0, smoke.returncode, msg=smoke.stdout + smoke.stderr)
        self.assertIn("plugin_validate: PASS", smoke.stdout)
        self.assertIn("release_filter: PASS", smoke.stdout)


class BuildReleaseArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        files = {
            ".claude-plugin/plugin.json": json.dumps(
                {
                    "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
                    "name": "superlooper",
                    "displayName": "Superlooper",
                    "version": "2.3.4",
                    "description": "test plugin",
                    "author": {"name": "tester", "organization": "example"},
                    "license": "Apache-2.0",
                    "skills": "./skills/",
                    "commands": "./commands/",
                }
            )
            + "\n",
            "README.md": "# test plugin\n",
            "LICENSE": "Apache-2.0\n",
            "skills/superlooper/SKILL.md": "---\ndescription: test skill\n---\n\n# skill\n",
            "commands/spl.md": "---\ndescription: test command\n---\n\n# /spl\n",
            "commands/spl/ui.md": "---\ndescription: test ui command\n---\n\n# /spl:ui\n",
            "commands/spl/run.md": "---\ndescription: test run command\n---\n\n# /spl:run\n",
            "agents/ui-architect.md": "---\nname: ui-architect\ndescription: ui architect\n---\n\n# ui architect\n",
            "agents/impact-analyzer.md": "---\nname: impact-analyzer\ndescription: impact analyzer\n---\n\n# impact analyzer\n",
            "docs/agent-flows/ui-architect-flow.md": "# ui flow\n",
            "docs/design/demo.md": "# Demo design\n",
            "scripts/package_plugin.py": "print('package')\n",
            "scripts/build_release_archive.py": "print('archive')\n",
            "scripts/build_execution_summary.py": "print('summary')\n",
            "scripts/normalize_user_intent.py": "print('normalize')\n",
            "scripts/doctor.py": "print('doctor')\n",
            "bin/spl": "print('doctor route')\n",
            "src/module.py": "print('ok')\n",
            "tests/test_package_plugin.py": "# retained in source mode\n",
        }
        for relative_path in INSTALL_RUNTIME_REQUIRED_FILES:
            content = "---\ndescription: runtime file\n---\n\n# runtime file\n" if relative_path.startswith(("agents/", "commands/")) else "# runtime file\n"
            files.setdefault(relative_path, content)
        files["docs/USER_GUIDE.md"] = "<!-- public-readme:start -->\n# test plugin\n<!-- public-readme:end -->\n"
        files["README.md"] = "# test plugin\n"
        for relative_path, content in files.items():
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_archive_paths_match_manifest(self):
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "build_release_archive.py"
        result = subprocess.run(
            [
                "python",
                str(script_path),
                "--mode",
                "install",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)

        manifest_path = self.root / "dist" / "superlooper-release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        archive_path = self.root / "dist" / "superlooper-2.3.4-install.zip"
        self.assertTrue(archive_path.is_file())
        with zipfile.ZipFile(archive_path) as archive:
            archive_names = sorted(archive.namelist())
        self.assertEqual(sorted(manifest["release_files"]), archive_names)
        self.assertIn("commands/spl/run.md", archive_names)
        self.assertIn("scripts/normalize_user_intent.py", archive_names)
        self.assertIn("scripts/doctor.py", archive_names)
        self.assertIn("bin/spl", archive_names)
        self.assertNotIn("tests/test_package_plugin.py", archive_names)
        self.assertNotIn("docs/design/demo.md", archive_names)
        self.assertTrue(all(not name.startswith("docs/design/") for name in archive_names))

    def test_archive_build_reports_package_error_without_traceback(self):
        secret_path = self.root / "README.md"
        secret_path.write_text("secret" + "_key: live_secret_value\n", encoding="utf-8")
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "build_release_archive.py"

        result = subprocess.run(
            [
                "python",
                str(script_path),
                "--mode",
                "install",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("build release archive failed:", result.stderr)
        self.assertIn("secret", result.stderr.lower())
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
