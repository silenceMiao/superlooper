import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class PackageMarketplaceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "source"
        self.target = Path(self.temp_dir.name) / "marketplace"
        self._create_source_tree()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_source_tree(self):
        files = {
            ".claude-plugin/plugin.json": json.dumps(
                {
                    "name": "superlooper",
                    "displayName": "Superlooper",
                    "version": "1.0.0",
                    "description": "test plugin",
                    "author": {"name": "tester"},
                    "license": "Apache-2.0",
                    "keywords": ["plugin"],
                }
            ),
            ".codex-plugin/plugin.json": json.dumps(
                {
                    "name": "superlooper",
                    "version": "1.0.0",
                    "description": "test plugin",
                    "author": {"name": "tester"},
                    "license": "Apache-2.0",
                    "skills": "./codex/skills/",
                }
            ),
            "README.md": "# Test\n",
            "LICENSE": "Apache-2.0\n",
            "scripts/package_plugin.py": "# package script\n",
        }
        for relative_path, content in files.items():
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _create_sync_user_guide(self):
        path = self.root / "docs" / "USER_GUIDE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<!-- public-readme:start -->\n# Marketplace Test\n{{USER_GUIDE_LINK}}\n{{SOURCE_MAINTENANCE_LINKS}}\n<!-- public-readme:end -->\n",
            encoding="utf-8",
        )

    def _install_packager(self, release_files):
        class FakePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.mode = mode
                self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

            def run(self):
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(
                    json.dumps({"plugin_name": "superlooper", "release_mode": "install", "release_files": release_files}),
                    encoding="utf-8",
                )
                return 0

        return FakePackager

    def _sync_release_files(self):
        return [
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
            "README.md",
            "LICENSE",
            "scripts/package_plugin.py",
        ]

    def test_package_marketplace_copies_install_manifest_and_writes_relative_metadata(self):
        from scripts import package_marketplace

        release_files = [
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
            "README.md",
            "LICENSE",
            "scripts/package_plugin.py",
        ]

        class FakePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.mode = mode
                self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

            def run(self):
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(
                    json.dumps({"plugin_name": "superlooper", "release_mode": "install", "release_files": release_files}),
                    encoding="utf-8",
                )
                return 0

        with mock.patch.object(package_marketplace, "PluginPackager", FakePackager):
            package_marketplace.package_marketplace(root=self.root, target=self.target)

        plugin_root = self.target / "plugins" / "superlooper"
        self.assertEqual(set(release_files), {str(path.relative_to(plugin_root)).replace("\\", "/") for path in plugin_root.rglob("*") if path.is_file()})
        marketplace = json.loads((self.target / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual("superAI-marketplace", marketplace["name"])
        self.assertEqual({"name": "tester"}, marketplace["owner"])
        self.assertEqual("test plugin", marketplace["description"])
        self.assertEqual(
            {
                "name": "superlooper",
                "displayName": "Superlooper",
                "description": "test plugin",
                "version": "1.0.0",
                "author": {"name": "tester"},
                "source": "./plugins/superlooper",
            },
            marketplace["plugins"][0],
        )
        self.assertTrue((plugin_root / ".claude-plugin" / "plugin.json").is_file())
        self.assertTrue((plugin_root / ".codex-plugin" / "plugin.json").is_file())
        self.assertNotIn(str(self.root), json.dumps(marketplace))

        codex_marketplace = json.loads((self.target / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual("superAI-marketplace", codex_marketplace["name"])
        self.assertEqual(
            {
                "name": "superlooper",
                "version": "1.0.0",
                "source": "./plugins/superlooper",
            },
            codex_marketplace["plugins"][0],
        )

    def test_package_marketplace_rejects_non_install_manifest(self):
        from scripts import package_marketplace

        for release_mode in ("source", None):
            with self.subTest(release_mode=release_mode):
                class FakePackager:
                    def __init__(self, root, mode):
                        self.root = Path(root)
                        self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

                    def run(self):
                        manifest = {"plugin_name": "superlooper", "release_files": ["README.md"]}
                        if release_mode is not None:
                            manifest["release_mode"] = release_mode
                        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                with mock.patch.object(package_marketplace, "PluginPackager", FakePackager):
                    with self.assertRaisesRegex(package_marketplace.MarketplaceError, "发布清单不是 install 模式"):
                        package_marketplace.package_marketplace(root=self.root, target=self.target)

                self.assertFalse(self.target.exists())

    def test_package_marketplace_cleans_staging_when_copy_fails(self):
        from scripts import package_marketplace

        release_files = ["README.md", "LICENSE"]

        class FakePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

            def run(self):
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(
                    json.dumps({"plugin_name": "superlooper", "release_mode": "install", "release_files": release_files}),
                    encoding="utf-8",
                )

        with mock.patch.object(package_marketplace, "PluginPackager", FakePackager), mock.patch.object(
            package_marketplace.shutil,
            "copy2",
            side_effect=[None, OSError("copy failed")],
        ):
            with self.assertRaises(OSError):
                package_marketplace.package_marketplace(root=self.root, target=self.target)

        self.assertFalse(self.target.exists())
        self.assertEqual([], list(self.target.parent.glob(f".{self.target.name}.*")))

    def test_package_marketplace_cleans_staging_when_marketplace_write_fails(self):
        from scripts import package_marketplace

        release_files = ["README.md"]

        class FakePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

            def run(self):
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(
                    json.dumps({"plugin_name": "superlooper", "release_mode": "install", "release_files": release_files}),
                    encoding="utf-8",
                )

        original_write_text = Path.write_text

        def fail_marketplace_write(path, content, *args, **kwargs):
            if path.name == "marketplace.json":
                raise OSError("marketplace write failed")
            return original_write_text(path, content, *args, **kwargs)

        with mock.patch.object(package_marketplace, "PluginPackager", FakePackager), mock.patch.object(
            Path,
            "write_text",
            new=fail_marketplace_write,
        ):
            with self.assertRaises(OSError):
                package_marketplace.package_marketplace(root=self.root, target=self.target)

        self.assertFalse(self.target.exists())
        self.assertEqual([], list(self.target.parent.glob(f".{self.target.name}.*")))

    def test_package_marketplace_cleans_claimed_target_when_publish_move_fails(self):
        from scripts import package_marketplace

        release_files = ["README.md"]

        class FakePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

            def run(self):
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(
                    json.dumps({"plugin_name": "superlooper", "release_mode": "install", "release_files": release_files}),
                    encoding="utf-8",
                )

        with mock.patch.object(package_marketplace, "PluginPackager", FakePackager), mock.patch.object(
            Path,
            "rename",
            side_effect=OSError("publish move failed"),
        ):
            with self.assertRaisesRegex(OSError, "publish move failed"):
                package_marketplace.package_marketplace(root=self.root, target=self.target)

        self.assertFalse(self.target.exists())
        self.assertEqual([], list(self.target.parent.glob(f".{self.target.name}.*")))

    def test_validate_release_files_rejects_mocked_symlink(self):
        from scripts import package_marketplace

        source_path = self.root / "README.md"
        original_is_symlink = Path.is_symlink

        def mocked_is_symlink(path):
            if path == source_path:
                return True
            return original_is_symlink(path)

        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=mocked_is_symlink):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "README.md"):
                package_marketplace._validate_release_files(self.root, ["README.md"])

    def test_package_marketplace_rejects_mocked_target_symlink(self):
        from scripts import package_marketplace

        original_is_symlink = Path.is_symlink

        def mocked_is_symlink(path):
            if path == self.target:
                return True
            return original_is_symlink(path)

        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=mocked_is_symlink):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "target 不能是符号链接"):
                package_marketplace.package_marketplace(root=self.root, target=self.target)

        self.assertFalse(self.target.exists())

    def test_package_marketplace_rejects_empty_target(self):
        from scripts import package_marketplace

        self.target.mkdir()

        with self.assertRaisesRegex(package_marketplace.MarketplaceError, "target 必须不存在"):
            package_marketplace._validate_target(self.root, self.target)

        self.assertTrue(self.target.is_dir())
        self.assertEqual([], list(self.target.iterdir()))

    def test_package_marketplace_rejects_nonempty_target(self):
        from scripts import package_marketplace

        self.target.mkdir()
        (self.target / "existing.txt").write_text("existing\n", encoding="utf-8")

        with self.assertRaises(package_marketplace.MarketplaceError):
            package_marketplace.package_marketplace(root=self.root, target=self.target)

    def test_package_marketplace_preserves_target_created_during_staging(self):
        from scripts import package_marketplace

        release_files = ["README.md"]

        class FakePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

            def run(self):
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(
                    json.dumps({"plugin_name": "superlooper", "release_mode": "install", "release_files": release_files}),
                    encoding="utf-8",
                )

        original_validate = package_marketplace._validate_marketplace_tree

        def create_target_during_staging(source_root, plugin_root, release_files):
            self.target.mkdir()
            (self.target / "existing.txt").write_text("existing\n", encoding="utf-8")
            original_validate(source_root, plugin_root, release_files)

        with mock.patch.object(package_marketplace, "PluginPackager", FakePackager), mock.patch.object(
            package_marketplace,
            "_validate_marketplace_tree",
            side_effect=create_target_during_staging,
        ):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "target 在发布期间已被创建"):
                package_marketplace.package_marketplace(root=self.root, target=self.target)

        self.assertEqual("existing\n", (self.target / "existing.txt").read_text(encoding="utf-8"))
        self.assertEqual([], list(self.target.parent.glob(f".{self.target.name}.*")))

    def test_package_marketplace_rejects_source_root_as_target(self):
        from scripts import package_marketplace

        with self.assertRaises(package_marketplace.MarketplaceError):
            package_marketplace.package_marketplace(root=self.root, target=self.root)

    def test_package_marketplace_rejects_target_inside_source_root(self):
        from scripts import package_marketplace

        with self.assertRaises(package_marketplace.MarketplaceError):
            package_marketplace.package_marketplace(root=self.root, target=self.root / "marketplace")

    def test_sync_marketplace_writes_marketplace_readme_and_ledger_without_touching_unmanaged_paths(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        (self.target / ".git").mkdir()
        (self.target / ".git" / "keep").write_text("keep\n", encoding="utf-8")
        (self.target / ".agents" / "unmanaged").mkdir(parents=True)
        (self.target / ".agents" / "unmanaged" / "keep").write_text("keep\n", encoding="utf-8")
        (self.target / "plugins" / "other-plugin").mkdir(parents=True)
        (self.target / "plugins" / "other-plugin" / "keep").write_text("keep\n", encoding="utf-8")

        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._sync_release_files())):
            package_marketplace.sync_marketplace(root=self.root, target=self.target)
            package_marketplace.sync_marketplace(root=self.root, target=self.target)

        self.assertEqual("keep\n", (self.target / ".git" / "keep").read_text(encoding="utf-8"))
        self.assertEqual("keep\n", (self.target / ".agents" / "unmanaged" / "keep").read_text(encoding="utf-8"))
        self.assertEqual("keep\n", (self.target / "plugins" / "other-plugin" / "keep").read_text(encoding="utf-8"))
        self.assertIn("plugins/superlooper/docs/USER_GUIDE.md", (self.target / "README.md").read_text(encoding="utf-8"))
        ledger = json.loads((self.target / ".superlooper-marketplace-sync.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {"schema_version", "plugin_name", "plugin_version", "source_commit", "managed_paths"},
            set(ledger),
        )
        self.assertEqual(1, ledger["schema_version"])
        self.assertEqual("superlooper", ledger["plugin_name"])
        self.assertEqual("1.0.0", ledger["plugin_version"])
        self.assertIsNone(ledger["source_commit"])
        self.assertEqual(
            {
                "README.md",
                ".claude-plugin/marketplace.json",
                ".agents/plugins/marketplace.json",
                *{f"plugins/superlooper/{path}" for path in self._sync_release_files()},
            },
            set(ledger["managed_paths"]),
        )
        self.assertNotIn(".superlooper-marketplace-sync.json", ledger["managed_paths"])

    def test_sync_marketplace_blocks_drift_before_replacing_controlled_files(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        packager = self._install_packager(self._sync_release_files())
        with mock.patch.object(package_marketplace, "PluginPackager", packager):
            package_marketplace.sync_marketplace(root=self.root, target=self.target)
            (self.target / "README.md").write_text("drift\n", encoding="utf-8")
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "受控文件已漂移"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)

        self.assertEqual("drift\n", (self.target / "README.md").read_text(encoding="utf-8"))

    def test_sync_marketplace_rejects_unknown_metadata_entries_without_replacing_files(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        cases = (
            ("claude-file", ".claude-plugin/untracked.json", "file"),
            ("codex-file", ".agents/plugins/untracked.json", "file"),
            ("claude-empty-directory", ".claude-plugin/untracked", "empty-directory"),
            ("codex-nonempty-directory", ".agents/plugins/untracked", "nonempty-directory"),
        )
        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._sync_release_files())):
            for name, relative_path, entry_type in cases:
                with self.subTest(name=name):
                    target = self.root.parent / f"marketplace-{name}"
                    target.mkdir()
                    package_marketplace.sync_marketplace(root=self.root, target=target)
                    metadata = target / (".claude-plugin/marketplace.json" if name.startswith("claude") else ".agents/plugins/marketplace.json")
                    before = metadata.read_bytes()
                    unexpected = target / relative_path
                    if entry_type == "file":
                        unexpected.write_text("untracked\n", encoding="utf-8")
                    else:
                        unexpected.mkdir()
                        if entry_type == "nonempty-directory":
                            (unexpected / "untracked.json").write_text("untracked\n", encoding="utf-8")

                    with self.assertRaisesRegex(package_marketplace.MarketplaceError, "受控 metadata 目录包含未知路径"):
                        package_marketplace.sync_marketplace(root=self.root, target=target)

                    self.assertEqual(before, metadata.read_bytes())

    def test_sync_marketplace_rejects_metadata_directory_symlink_without_replacing_files(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        metadata = self.target / ".claude-plugin" / "marketplace.json"
        unexpected = self.target / ".claude-plugin" / "untracked-link"
        original_is_symlink = Path.is_symlink

        def linked(path):
            if path == unexpected:
                return True
            return original_is_symlink(path)

        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._sync_release_files())):
            package_marketplace.sync_marketplace(root=self.root, target=self.target)
            before = metadata.read_bytes()
            unexpected.write_text("untracked\n", encoding="utf-8")
            with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=linked):
                with self.assertRaisesRegex(package_marketplace.MarketplaceError, "受控 metadata 目录包含符号链接"):
                    package_marketplace.sync_marketplace(root=self.root, target=self.target)

        self.assertEqual(before, metadata.read_bytes())

    def test_sync_marketplace_records_clean_git_head_and_rejects_dirty_git_source(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        commit = "a" * 40

        def clean_git(command, **_kwargs):
            if command[1:] == ["status", "--porcelain"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 0, f"{commit}\n", "")

        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._sync_release_files())), mock.patch.object(
            package_marketplace.subprocess, "run", side_effect=clean_git
        ):
            package_marketplace.sync_marketplace(root=self.root, target=self.target)

        ledger = json.loads((self.target / ".superlooper-marketplace-sync.json").read_text(encoding="utf-8"))
        self.assertEqual(commit, ledger["source_commit"])

        dirty_git = subprocess.CompletedProcess(["git", "status", "--porcelain"], 0, " M README.md\n", "")
        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._sync_release_files())), mock.patch.object(
            package_marketplace.subprocess, "run", return_value=dirty_git
        ):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "源码 Git 工作树不干净"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)

    def test_sync_marketplace_rejects_invalid_managed_paths_and_metadata_source(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        packager = self._install_packager(self._sync_release_files())
        with mock.patch.object(package_marketplace, "PluginPackager", packager):
            package_marketplace.sync_marketplace(root=self.root, target=self.target)
            ledger_path = self.target / ".superlooper-marketplace-sync.json"
            original_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

            invalid_path_ledger = dict(original_ledger)
            invalid_path_ledger["managed_paths"] = dict(original_ledger["managed_paths"])
            invalid_path_ledger["managed_paths"]["unmanaged.txt"] = "0" * 64
            ledger_path.write_text(json.dumps(invalid_path_ledger), encoding="utf-8")
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "未允许路径"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)

            missing_path_ledger = dict(original_ledger)
            missing_path_ledger["managed_paths"] = dict(original_ledger["managed_paths"])
            missing_path_ledger["managed_paths"].pop("README.md")
            ledger_path.write_text(json.dumps(missing_path_ledger), encoding="utf-8")
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "受控文件集"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)

            metadata_path = self.target / ".claude-plugin" / "marketplace.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["plugins"][0]["source"] = "./plugins/other"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            metadata_ledger = dict(original_ledger)
            metadata_ledger["managed_paths"] = dict(original_ledger["managed_paths"])
            metadata_ledger["managed_paths"][".claude-plugin/marketplace.json"] = package_marketplace._sha256(metadata_path)
            ledger_path.write_text(json.dumps(metadata_ledger), encoding="utf-8")
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "source 无效"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)

    def test_sync_marketplace_adopts_install_closure_subset_and_adds_new_files(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        old_release_files = self._sync_release_files()[:-1]
        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(old_release_files)):
            package_marketplace.package_marketplace(root=self.root, target=self.target / "initial")
        for path in (self.target / "initial").iterdir():
            path.rename(self.target / path.name)
        (self.target / "initial").rmdir()

        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._sync_release_files())):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "--adopt-existing"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)
            package_marketplace.sync_marketplace(root=self.root, target=self.target, adopt_existing=True)

        self.assertTrue((self.target / ".superlooper-marketplace-sync.json").is_file())
        self.assertTrue((self.target / "plugins" / "superlooper" / "scripts" / "package_plugin.py").is_file())

    def test_sync_marketplace_adoption_requires_superlooper_plugin_manifests(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        packager = self._install_packager(self._sync_release_files())
        with mock.patch.object(package_marketplace, "PluginPackager", packager):
            package_marketplace.package_marketplace(root=self.root, target=self.target / "initial")
            for path in (self.target / "initial").iterdir():
                path.rename(self.target / path.name)
            (self.target / "initial").rmdir()
            manifest_path = self.target / "plugins" / "superlooper" / ".claude-plugin" / "plugin.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["name"] = "other-plugin"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "manifest 名称必须为 superlooper"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target, adopt_existing=True)

    def test_sync_marketplace_rejects_adoption_with_extra_plugin_file_or_empty_directory(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        packager = self._install_packager(self._sync_release_files())
        with mock.patch.object(package_marketplace, "PluginPackager", packager):
            package_marketplace.package_marketplace(root=self.root, target=self.target / "initial")
            for path in (self.target / "initial").iterdir():
                path.rename(self.target / path.name)
            (self.target / "initial").rmdir()
            (self.target / "plugins" / "superlooper" / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "额外文件"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target, adopt_existing=True)
            (self.target / "plugins" / "superlooper" / "unexpected.txt").unlink()
            (self.target / "plugins" / "superlooper" / "empty").mkdir()
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "空目录"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target, adopt_existing=True)

    def test_sync_marketplace_removes_directories_created_before_plugin_install_failure(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        before_paths = {path.relative_to(self.target).as_posix() for path in self.target.rglob("*")}
        original_rename = Path.rename

        def fail_plugin_install(path, destination):
            if Path(destination) == self.target / "plugins" / "superlooper":
                raise OSError("plugin install failed")
            return original_rename(path, destination)

        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._sync_release_files())), mock.patch.object(
            Path, "rename", autospec=True, side_effect=fail_plugin_install
        ):
            with self.assertRaisesRegex(OSError, "plugin install failed"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)

        after_paths = {path.relative_to(self.target).as_posix() for path in self.target.rglob("*")}
        self.assertEqual(before_paths, after_paths)
        self.assertEqual([], list(self.target.iterdir()))

    def test_sync_marketplace_restores_backups_after_replacement_failure(self):
        from scripts import package_marketplace

        self._create_sync_user_guide()
        self.target.mkdir()
        packager = self._install_packager(self._sync_release_files())
        with mock.patch.object(package_marketplace, "PluginPackager", packager):
            package_marketplace.sync_marketplace(root=self.root, target=self.target)
            before = (self.target / "README.md").read_bytes()
            original_rename = Path.rename

            def fail_readme_install(path, destination):
                if path.parent.name.startswith(".marketplace-staging.") and Path(destination) == self.target / "README.md":
                    raise OSError("replace failed")
                return original_rename(path, destination)

            with mock.patch.object(Path, "rename", autospec=True, side_effect=fail_readme_install):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    package_marketplace.sync_marketplace(root=self.root, target=self.target)

        self.assertEqual(before, (self.target / "README.md").read_bytes())
        self.assertTrue((self.target / ".superlooper-marketplace-sync.json").is_file())
        self.assertEqual([], list(self.target.parent.glob(f".{self.target.name}.sync-backup.*")))

    def test_sync_cli_routes_to_sync_target_and_rejects_adopt_for_package_target(self):
        from scripts import package_marketplace

        args = package_marketplace.parse_args(["--sync-target", "marketplace", "--adopt-existing"])
        self.assertEqual("marketplace", args.sync_target)
        with mock.patch.object(sys, "stderr"):
            with self.assertRaises(SystemExit):
                package_marketplace.parse_args(["--target", "marketplace", "--adopt-existing"])


class MarketplaceDoctorSmokeTest(unittest.TestCase):
    def test_generated_marketplace_plugin_runs_doctor(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_root = temp_root / "source"
            target_root = temp_root / "marketplace"
            shutil.copytree(
                repo_root,
                source_root,
                ignore=shutil.ignore_patterns(".claude", ".superlooper", ".learnings", "dist", "__pycache__"),
            )

            package_result = subprocess.run(
                [
                    sys.executable,
                    "scripts/package_marketplace.py",
                    "--target",
                    str(target_root),
                ],
                cwd=source_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(0, package_result.returncode, msg=package_result.stdout + package_result.stderr)

            plugin_root = target_root / "plugins" / "superlooper"
            self.assertTrue((plugin_root / ".claude-plugin" / "plugin.json").is_file())
            self.assertTrue((plugin_root / ".codex-plugin" / "plugin.json").is_file())
            self.assertTrue((plugin_root / "codex" / "skills" / "superlooper" / "SKILL.md").is_file())
            readme = (plugin_root / "README.md").read_text(encoding="utf-8")
            self.assertIn("MIT", readme)
            self.assertIn("/superlooper:spl", readme)
            self.assertIn("$superlooper", readme)
            expected_commands = {
                "commands/spl.md": "/superlooper:spl",
                "commands/spl/prd.md": "/superlooper:spl:prd",
                "commands/spl/ui.md": "/superlooper:spl:ui",
                "commands/spl/design.md": "/superlooper:spl:design",
                "commands/spl/run.md": "/superlooper:spl:run",
                "commands/spl/status.md": "/superlooper:spl:status",
                "commands/spl/resume.md": "/superlooper:spl:resume",
                "commands/spl/doctor.md": "/superlooper:spl:doctor",
            }
            for relative_path, command_name in expected_commands.items():
                with self.subTest(relative_path=relative_path):
                    self.assertIn(
                        f"# {command_name}",
                        (plugin_root / relative_path).read_text(encoding="utf-8"),
                    )

            smoke = subprocess.run(
                [sys.executable, "bin/spl", "doctor"],
                cwd=target_root / "plugins" / "superlooper",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(0, smoke.returncode, msg=smoke.stdout + smoke.stderr)
            self.assertIn("plugin_validate: PASS", smoke.stdout)
            self.assertIn("release_filter: PASS", smoke.stdout)


if __name__ == "__main__":
    unittest.main()
