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
        (self.source_root / "LICENSE").write_text("MIT\n", encoding="utf-8")
        guide = self.source_root / "docs" / "USER_GUIDE.md"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text(
            "<!-- public-readme:start -->\n# Marketplace\n{{USER_GUIDE_LINK}}\n{{SOURCE_MAINTENANCE_LINKS}}\n<!-- public-readme:end -->\n",
            encoding="utf-8",
        )
        (self.source_root / "README.md").write_text(
            extract_public_readme(guide, "source"), encoding="utf-8"
        )
        for relative_path in self.release_files:
            path = self.source_root / relative_path
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"fixture: {relative_path}\n", encoding="utf-8")
        self._write_json(
            self.source_root,
            "dist/superlooper-release-manifest.json",
            {
                "plugin_name": "superlooper",
                "release_mode": "install",
                "release_files": self.release_files,
            },
        )

    def _write_marketplace(self, version="1.0.0", source_commit=None):
        source_manifest = json.loads((self.source_root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        codex_manifest = json.loads((self.source_root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        source_manifest["version"] = version
        codex_manifest["version"] = version
        self._write_json(
            self.marketplace_root,
            ".claude-plugin/marketplace.json",
            {"name": "superAI-marketplace", "plugins": [{"name": "superlooper", "version": version, "source": "./plugins/superlooper"}]},
        )
        self._write_json(
            self.marketplace_root,
            ".agents/plugins/marketplace.json",
            {"name": "superAI-marketplace", "plugins": [{"name": "superlooper", "version": version, "source": "./plugins/superlooper"}]},
        )
        for relative_path in self.release_files:
            destination = self.marketplace_root / "plugins" / "superlooper" / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if relative_path in {".claude-plugin/plugin.json", ".codex-plugin/plugin.json"} and version != "1.0.0":
                manifest = source_manifest if relative_path == ".claude-plugin/plugin.json" else codex_manifest
                destination.write_text(json.dumps(manifest), encoding="utf-8")
            else:
                destination.write_bytes((self.source_root / relative_path).read_bytes())
        (self.marketplace_root / "README.md").write_text(
            extract_public_readme(self.source_root / "docs" / "USER_GUIDE.md", "marketplace"), encoding="utf-8"
        )
        managed_paths = {
            "README.md",
            ".claude-plugin/marketplace.json",
            ".agents/plugins/marketplace.json",
            *{f"plugins/superlooper/{path}" for path in self.release_files},
        }
        ledger = {
            "schema_version": 1,
            "plugin_name": "superlooper",
            "plugin_version": version,
            "source_commit": source_commit,
            "managed_paths": {
                path: hashlib.sha256((self.marketplace_root / path).read_bytes()).hexdigest()
                for path in sorted(managed_paths)
            },
        }
        self._write_json(self.marketplace_root, verifier.LEDGER_FILE, ledger)

    def _verify(self, **kwargs):
        return verifier.verify_release_consistency(self.source_root, self.marketplace_root, **kwargs)

    def _assert_error(self, expected, **kwargs):
        result = self._verify(**kwargs)
        self.assertFalse(result.ok)
        self.assertTrue(any(expected in error for error in result.errors), result.errors)

    def test_verify_accepts_exact_local_fixture_without_git_or_packager_run(self):
        git_runner = mock.Mock()
        with mock.patch.object(verifier.PluginPackager, "run", side_effect=AssertionError("must not package")):
            result = self._verify(git_runner=git_runner)
        self.assertTrue(result.ok, result.errors)
        git_runner.assert_not_called()

    def test_verify_rejects_version_drift_and_invalid_metadata(self):
        self._write_marketplace(version="0.9.0")
        self._assert_error("版本不一致")
        metadata_path = self.marketplace_root / ".claude-plugin" / "marketplace.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["plugins"][0]["source"] = "./plugins/other"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        self._assert_error("metadata 插件引用无效")
        metadata["name"] = "other-marketplace"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        self._assert_error("Claude Marketplace metadata name 无效")
        codex_metadata_path = self.marketplace_root / ".agents" / "plugins" / "marketplace.json"
        codex_metadata = json.loads(codex_metadata_path.read_text(encoding="utf-8"))
        codex_metadata["name"] = "other-marketplace"
        codex_metadata_path.write_text(json.dumps(codex_metadata), encoding="utf-8")
        self._assert_error("Codex Marketplace metadata name 无效")

    def test_verify_rejects_plugin_manifest_and_license_drift(self):
        manifest_path = self.marketplace_root / "plugins" / "superlooper" / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["name"] = "other"
        manifest["license"] = "Apache-2.0"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self._assert_error("Marketplace Claude/Codex manifest name 不一致")
        self._assert_error("Marketplace Claude/Codex manifest license 不一致")

    def test_verify_rejects_missing_extra_and_changed_plugin_files(self):
        (self.marketplace_root / "plugins" / "superlooper" / "LICENSE").unlink()
        self._assert_error("插件文件集")
        self._write_marketplace()
        extra = self.marketplace_root / "plugins" / "superlooper" / "extra.txt"
        extra.write_text("extra", encoding="utf-8")
        self._assert_error("插件文件集")
        extra.unlink()
        plugin_readme = self.marketplace_root / "plugins" / "superlooper" / "README.md"
        plugin_readme.write_text("changed\n", encoding="utf-8")
        self._assert_error("插件文件内容不一致")

    def test_verify_rejects_extra_plugin_directory_and_readme_drift(self):
        (self.marketplace_root / "plugins" / "superlooper" / "empty").mkdir()
        self._assert_error("插件目录集")
        (self.marketplace_root / "plugins" / "superlooper" / "empty").rmdir()
        (self.marketplace_root / "README.md").write_text("manual\n", encoding="utf-8")
        self._assert_error("README 未由用户指南生成")

    def test_verify_rejects_source_readme_drift(self):
        (self.source_root / "README.md").write_text("manual\n", encoding="utf-8")
        self._assert_error("源码 README 未由用户指南生成")

    def test_verify_rejects_missing_and_stale_install_manifest(self):
        (self.source_root / "dist" / "superlooper-release-manifest.json").unlink()
        self._assert_error("缺少文件")
        self._write_source()
        self._write_marketplace()
        manifest_path = self.source_root / "dist" / "superlooper-release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["release_files"].remove("LICENSE")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self._assert_error("当前安装闭包不一致")
        self._write_source()
        self._write_marketplace()
        missing_required = "agents/analyst.md"
        (self.source_root / missing_required).unlink()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["release_files"].remove(missing_required)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self._assert_error(f"install 安装闭包缺少必需文件: {missing_required}")

    def test_verify_rejects_ledger_schema_paths_hashes_and_extra_fields(self):
        ledger_path = self.marketplace_root / verifier.LEDGER_FILE
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        cases = [
            ("schema_version", 2, "schema_version 无效"),
            ("plugin_name", "other", "plugin_name 无效"),
            ("plugin_version", "", "plugin_version 无效"),
            ("source_commit", "bad", "source_commit 无效"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field):
                changed = dict(ledger)
                changed[field] = value
                ledger_path.write_text(json.dumps(changed), encoding="utf-8")
                self._assert_error(expected)
        changed = dict(ledger)
        changed["marketplace_name"] = "legacy"
        ledger_path.write_text(json.dumps(changed), encoding="utf-8")
        self._assert_error("schema 无效")
        changed = dict(ledger)
        changed["managed_paths"] = dict(ledger["managed_paths"])
        changed["managed_paths"]["files/manual.txt"] = "0" * 64
        ledger_path.write_text(json.dumps(changed), encoding="utf-8")
        self._assert_error("路径或 SHA-256 无效")
        changed["managed_paths"] = dict(ledger["managed_paths"])
        changed["managed_paths"].pop("README.md")
        ledger_path.write_text(json.dumps(changed), encoding="utf-8")
        self._assert_error("受控路径与发布闭包不一致")
        changed = dict(ledger)
        changed["managed_paths"] = dict(ledger["managed_paths"])
        changed["managed_paths"]["README.md"] = "0" * 64
        ledger_path.write_text(json.dumps(changed), encoding="utf-8")
        self._assert_error("散列漂移")

    def test_verify_rejects_controlled_symlinks_and_ancestor_symlinks(self):
        target = self.marketplace_root / "plugins" / "superlooper" / "README.md"
        original_is_symlink = Path.is_symlink

        def linked(path):
            if path == target:
                return True
            return original_is_symlink(path)

        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=linked):
            self._assert_error("受控路径或祖先不能是符号链接")
        ancestor = self.marketplace_root / ".agents"

        def ancestor_linked(path):
            if path == ancestor:
                return True
            return original_is_symlink(path)

        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=ancestor_linked):
            self._assert_error("受控路径或祖先不能是符号链接")

    def test_verify_rejects_unknown_metadata_entries(self):
        cases = (
            ("claude-file", ".claude-plugin/untracked.json", "file"),
            ("codex-file", ".agents/plugins/untracked.json", "file"),
            ("claude-empty-directory", ".claude-plugin/untracked", "empty-directory"),
            ("codex-nonempty-directory", ".agents/plugins/untracked", "nonempty-directory"),
        )
        for name, relative_path, entry_type in cases:
            with self.subTest(name=name):
                unexpected = self.marketplace_root / relative_path
                if entry_type == "file":
                    unexpected.write_text("untracked\n", encoding="utf-8")
                else:
                    unexpected.mkdir()
                    if entry_type == "nonempty-directory":
                        (unexpected / "untracked.json").write_text("untracked\n", encoding="utf-8")
                self._assert_error("受控 metadata 目录包含未知路径")
                if entry_type == "nonempty-directory":
                    (unexpected / "untracked.json").unlink()
                if entry_type != "file":
                    unexpected.rmdir()
                else:
                    unexpected.unlink()

    def test_verify_rejects_metadata_directory_symlink(self):
        unexpected = self.marketplace_root / ".claude-plugin" / "untracked-link"
        unexpected.write_text("untracked\n", encoding="utf-8")
        original_is_symlink = Path.is_symlink

        def linked(path):
            if path == unexpected:
                return True
            return original_is_symlink(path)

        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=linked):
            self._assert_error("受控 metadata 目录包含符号链接")

    def test_verify_collects_ledger_and_git_executable_errors_without_traceback(self):
        (self.marketplace_root / verifier.LEDGER_FILE).write_text("{bad", encoding="utf-8")

        def missing_git(_root, _args):
            raise FileNotFoundError("git missing")

        result = self._verify(require_pushed=True, git_runner=missing_git)
        self.assertFalse(result.ok)
        self.assertTrue(any("同步账本" in error for error in result.errors), result.errors)
        self.assertTrue(any("Git 命令执行失败" in error for error in result.errors), result.errors)

    def test_cli_reports_bad_ledger_without_traceback(self):
        (self.marketplace_root / verifier.LEDGER_FILE).write_text("{bad", encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = verifier.main(["--root", str(self.source_root), "--marketplace", str(self.marketplace_root)])
        self.assertEqual(1, exit_code)
        self.assertIn("同步账本", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_verify_require_pushed_rejects_non_git_dirty_branch_origin_and_remote(self):
        self._assert_error("源码目录不是已绑定 origin 的 Git 工作树", require_pushed=True, git_runner=lambda *_: (1, "", "not git"))
        head = "a" * 40

        def runner(root, args):
            if args == ["status", "--porcelain"]:
                return (0, " M file\n" if root == self.source_root else "", "")
            if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return (0, "wrong\n", "")
            if args == ["rev-parse", "HEAD"]:
                return (0, head + "\n", "")
            if args == ["remote", "get-url", "origin"]:
                return (1, "", "missing")
            return (0, "", "")

        result = self._verify(require_pushed=True, git_runner=runner)
        self.assertFalse(result.ok)
        self.assertTrue(any("工作树不干净" in error for error in result.errors), result.errors)
        self.assertTrue(any("当前分支不是 main" in error for error in result.errors), result.errors)
        self.assertTrue(any("缺少 origin" in error for error in result.errors), result.errors)

        def remote_runner(_root, args):
            if args == ["status", "--porcelain"]:
                return (0, "", "")
            if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return (0, "main\n", "")
            if args == ["rev-parse", "HEAD"]:
                return (0, head + "\n", "")
            if args == ["remote", "get-url", "origin"]:
                return (0, "origin", "")
            return (0, "b" * 40 + "\trefs/heads/main\n", "")

        self._assert_error("远程 main HEAD 与本地不一致", require_pushed=True, git_runner=remote_runner)

    def test_verify_require_pushed_accepts_matching_git_and_source_commit(self):
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

        result = self._verify(require_pushed=True, git_runner=runner)
        self.assertTrue(result.ok, result.errors)

    def test_verify_require_pushed_rejects_ledger_source_commit_drift(self):
        self._write_marketplace(source_commit="b" * 40)
        head = "a" * 40

        def runner(_root, args):
            if args == ["status", "--porcelain"]:
                return (0, "", "")
            if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return (0, "main\n", "")
            if args == ["rev-parse", "HEAD"]:
                return (0, head + "\n", "")
            if args == ["remote", "get-url", "origin"]:
                return (0, "origin", "")
            return (0, head + "\trefs/heads/main\n", "")

        self._assert_error("source_commit 与源码 HEAD 不一致", require_pushed=True, git_runner=runner)


if __name__ == "__main__":
    unittest.main()
