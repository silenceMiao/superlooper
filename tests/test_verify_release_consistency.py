import contextlib
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import verify_release_consistency as verifier
from scripts.render_user_readme import extract_public_readme


class VerifyReleaseConsistencyTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.source_root = Path(self.temp_dir.name) / "source"
        self.marketplace_root = Path(self.temp_dir.name) / "marketplace"
        self.release_files = sorted(verifier.INSTALL_RUNTIME_REQUIRED_FILES)
        self._write_source()
        self._write_marketplace()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_json(self, root, relative_path, value):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_source(self, version="1.0.0"):
        claude_manifest = {
            "name": "superlooper",
            "version": version,
            "license": "MIT",
            "displayName": "Superlooper",
            "description": "test plugin",
            "author": {"name": "tester"},
        }
        codex_manifest = {"name": "superlooper", "version": version, "license": "MIT"}
        self._write_json(self.source_root, ".claude-plugin/plugin.json", claude_manifest)
        self._write_json(self.source_root, ".codex-plugin/plugin.json", codex_manifest)
        guide = self.source_root / "docs" / "USER_GUIDE.md"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text(
            "<!-- public-readme:start -->\n# Superlooper\n{{USER_GUIDE_LINK}}\n{{SOURCE_MAINTENANCE_LINKS}}\n<!-- public-readme:end -->\n",
            encoding="utf-8",
        )
        (self.source_root / "README.md").write_text(extract_public_readme(guide, "source"), encoding="utf-8")
        for relative_path in self.release_files:
            path = self.source_root / relative_path
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"fixture: {relative_path}\n", encoding="utf-8")
        self._write_json(
            self.source_root,
            "dist/superlooper-release-manifest.json",
            {"plugin_name": "superlooper", "release_mode": "install", "release_files": self.release_files},
        )

    def _write_marketplace(self, version="1.0.0", source_commit=None):
        entry = {"name": "superlooper", "version": version, "source": "./plugins/superlooper"}
        other = {"name": "other", "version": "9.0.0", "source": "./plugins/other"}
        self._write_json(
            self.marketplace_root,
            ".claude-plugin/marketplace.json",
            {"name": "superAI-marketplace", "plugins": [other, entry]},
        )
        self._write_json(
            self.marketplace_root,
            ".agents/plugins/marketplace.json",
            {"name": "superAI-marketplace", "plugins": [entry, other]},
        )
        managed_paths = {}
        for relative_path in self.release_files:
            destination = self.marketplace_root / "plugins" / "superlooper" / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.source_root / relative_path).read_bytes())
            managed_paths[f"plugins/superlooper/{relative_path}"] = hashlib.sha256(destination.read_bytes()).hexdigest()
        self._write_json(
            self.marketplace_root,
            verifier.LEDGER_FILE,
            {
                "schema_version": 2,
                "plugin_name": "superlooper",
                "plugin_version": version,
                "source_commit": source_commit,
                "managed_paths": managed_paths,
            },
        )

    def _verify(self, **kwargs):
        return verifier.verify_release_consistency(self.source_root, self.marketplace_root, **kwargs)

    def _assert_error(self, expected, **kwargs):
        result = self._verify(**kwargs)
        self.assertFalse(result.ok)
        self.assertTrue(any(expected in error for error in result.errors), result.errors)

    def test_verify_accepts_v2_registry_and_ignores_marketplace_readme(self):
        git_runner = mock.Mock()
        result = self._verify(git_runner=git_runner)
        self.assertTrue(result.ok, result.errors)
        git_runner.assert_not_called()
        (self.marketplace_root / "README.md").write_text("# Marketplace overview\n", encoding="utf-8")
        self.assertTrue(self._verify().ok)

    def test_verify_rejects_plugin_and_ledger_drift(self):
        plugin_file = self.marketplace_root / "plugins" / "superlooper" / "LICENSE"
        plugin_file.write_text("changed\n", encoding="utf-8")
        self._assert_error("散列漂移")
        self._write_marketplace()
        extra = self.marketplace_root / "plugins" / "superlooper" / "extra.txt"
        extra.write_text("extra\n", encoding="utf-8")
        self._assert_error("插件文件集")

    def test_verify_rejects_invalid_shared_registry_entries(self):
        path = self.marketplace_root / ".claude-plugin/marketplace.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["plugins"].append(dict(metadata["plugins"][1]))
        path.write_text(json.dumps(metadata), encoding="utf-8")
        self._assert_error("重复")
        metadata["plugins"] = "invalid"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        self._assert_error("plugins 无效")

    def test_verify_rejects_v1_ledger_and_source_readme_drift(self):
        ledger_path = self.marketplace_root / verifier.LEDGER_FILE
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["schema_version"] = 1
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        self._assert_error("--migrate-v1")
        self._write_marketplace()
        (self.source_root / "README.md").write_text("manual\n", encoding="utf-8")
        self._assert_error("源码 README 未由用户指南生成")

    def test_cli_reports_invalid_ledger_without_traceback(self):
        (self.marketplace_root / verifier.LEDGER_FILE).write_text("{bad", encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = verifier.main(["--root", str(self.source_root), "--marketplace", str(self.marketplace_root)])
        self.assertEqual(1, exit_code)
        self.assertIn("同步账本", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_verify_require_pushed_checks_git_and_source_commit(self):
        head = "a" * 40
        self._write_marketplace(source_commit=head)

        def runner(_root, args):
            if args == ["status", "--porcelain"]:
                return (0, "", "")
            if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return (0, "main\n", "")
            if args == ["rev-parse", "HEAD"]:
                return subprocess.CompletedProcess([], 0, head + "\n", "")
            if args == ["remote", "get-url", "origin"]:
                return (0, "origin", "")
            return (0, head + "\trefs/heads/main\n", "")

        self.assertTrue(self._verify(require_pushed=True, git_runner=runner).ok)
        self._assert_error(
            "源码目录不是已绑定 origin 的 Git 工作树",
            require_pushed=True,
            git_runner=lambda *_: (1, "", "not git"),
        )


if __name__ == "__main__":
    unittest.main()
