import hashlib
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
        self.overview = Path(self.temp_dir.name) / "overview.md"
        self.overview.write_text("# Test Marketplace\n", encoding="utf-8")
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
                    "license": "MIT",
                }
            ),
            ".codex-plugin/plugin.json": json.dumps(
                {
                    "name": "superlooper",
                    "version": "1.0.0",
                    "description": "test plugin",
                    "author": {"name": "tester"},
                    "license": "MIT",
                    "skills": "./codex/skills/",
                }
            ),
            "README.md": "# Test\n",
            "LICENSE": "MIT\n",
            "scripts/package_plugin.py": "# package script\n",
        }
        for relative_path, content in files.items():
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    @staticmethod
    def _install_packager(release_files):
        class FakePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

            def run(self):
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(
                    json.dumps(
                        {
                            "plugin_name": "superlooper",
                            "release_mode": "install",
                            "release_files": release_files,
                        }
                    ),
                    encoding="utf-8",
                )

        return FakePackager

    @staticmethod
    def _release_files():
        return [
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
            "README.md",
            "LICENSE",
            "scripts/package_plugin.py",
        ]

    def _package(self, target=None):
        from scripts import package_marketplace

        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._release_files())):
            package_marketplace.package_marketplace(
                root=self.root,
                target=target or self.target,
                marketplace_readme=self.overview,
            )

    def test_new_target_copies_install_manifest_overview_and_v2_ledger(self):
        self._package()

        plugin_root = self.target / "plugins" / "superlooper"
        actual_files = {
            path.relative_to(plugin_root).as_posix()
            for path in plugin_root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(set(self._release_files()), actual_files)
        self.assertEqual("# Test Marketplace\n", (self.target / "README.md").read_text(encoding="utf-8"))
        ledger = json.loads((self.target / ".superlooper-marketplace-sync.json").read_text(encoding="utf-8"))
        self.assertEqual(2, ledger["schema_version"])
        self.assertEqual(
            {f"plugins/superlooper/{path}" for path in self._release_files()},
            set(ledger["managed_paths"]),
        )
        self.assertNotIn("README.md", ledger["managed_paths"])
        self.assertNotIn(".claude-plugin/marketplace.json", ledger["managed_paths"])

    def test_new_target_requires_explicit_marketplace_overview(self):
        from scripts import package_marketplace

        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._release_files())):
            with self.assertRaises(TypeError):
                package_marketplace.package_marketplace(root=self.root, target=self.target)
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "README"):
                package_marketplace.package_marketplace(
                    root=self.root,
                    target=self.target,
                    marketplace_readme=self.target / "missing.md",
                )
        self.assertFalse(self.target.exists())

    def test_package_marketplace_rejects_non_install_manifest_and_existing_target(self):
        from scripts import package_marketplace

        class SourcePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.manifest_path = self.root / "dist" / "superlooper-release-manifest.json"

            def run(self):
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(
                    json.dumps({"plugin_name": "superlooper", "release_mode": "source", "release_files": ["README.md"]}),
                    encoding="utf-8",
                )

        with mock.patch.object(package_marketplace, "PluginPackager", SourcePackager):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "install"):
                package_marketplace.package_marketplace(self.root, self.target, self.overview)
        self.target.mkdir()
        with self.assertRaisesRegex(package_marketplace.MarketplaceError, "必须不存在"):
            package_marketplace.package_marketplace(self.root, self.target, self.overview)

    def test_sync_preserves_marketplace_owned_paths_and_other_registry_entries(self):
        from scripts import package_marketplace

        self._package()
        (self.target / "README.md").write_text("# Maintained overview\n", encoding="utf-8")
        (self.target / ".git").mkdir()
        (self.target / ".git" / "keep").write_text("keep\n", encoding="utf-8")
        (self.target / "plugins" / "other").mkdir()
        (self.target / "plugins" / "other" / "keep").write_text("keep\n", encoding="utf-8")
        neighbor = self.target / ".claude-plugin" / "extra.json"
        neighbor.write_text("{}\n", encoding="utf-8")
        for relative_path in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            path = self.target / relative_path
            metadata = json.loads(path.read_text(encoding="utf-8"))
            metadata["plugins"].insert(0, {"name": "other", "version": "1.0.0", "source": "./plugins/other"})
            path.write_text(json.dumps(metadata), encoding="utf-8")

        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._release_files())):
            package_marketplace.sync_marketplace(root=self.root, target=self.target)

        self.assertEqual("# Maintained overview\n", (self.target / "README.md").read_text(encoding="utf-8"))
        self.assertEqual("keep\n", (self.target / ".git" / "keep").read_text(encoding="utf-8"))
        self.assertEqual("keep\n", (self.target / "plugins" / "other" / "keep").read_text(encoding="utf-8"))
        self.assertEqual("{}\n", neighbor.read_text(encoding="utf-8"))
        for relative_path in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            metadata = json.loads((self.target / relative_path).read_text(encoding="utf-8"))
            self.assertEqual(["other", "superlooper"], [entry["name"] for entry in metadata["plugins"]])

    def test_sync_rejects_plugin_drift_and_duplicate_registry_entries_before_writing(self):
        from scripts import package_marketplace

        self._package()
        plugin_file = self.target / "plugins" / "superlooper" / "LICENSE"
        plugin_file.write_text("changed\n", encoding="utf-8")
        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._release_files())):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "漂移"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)
        self.assertEqual("changed\n", plugin_file.read_text(encoding="utf-8"))

        self._package(target=self.target.parent / "second")
        second = self.target.parent / "second"
        metadata_path = second / ".claude-plugin/marketplace.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["plugins"].append(dict(metadata["plugins"][0]))
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._release_files())):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "重复"):
                package_marketplace.sync_marketplace(root=self.root, target=second)

    def test_sync_requires_explicit_clean_v1_migration(self):
        from scripts import package_marketplace

        self._package()
        managed_paths = {
            "README.md",
            ".claude-plugin/marketplace.json",
            ".agents/plugins/marketplace.json",
            *{f"plugins/superlooper/{path}" for path in self._release_files()},
        }
        legacy = {
            "schema_version": 1,
            "plugin_name": "superlooper",
            "plugin_version": "1.0.0",
            "source_commit": None,
            "managed_paths": {
                path: hashlib.sha256((self.target / path).read_bytes()).hexdigest()
                for path in sorted(managed_paths)
            },
        }
        (self.target / ".superlooper-marketplace-sync.json").write_text(json.dumps(legacy), encoding="utf-8")
        with mock.patch.object(package_marketplace, "PluginPackager", self._install_packager(self._release_files())):
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "--migrate-v1"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)
            package_marketplace.sync_marketplace(root=self.root, target=self.target, migrate_v1=True)

        ledger = json.loads((self.target / ".superlooper-marketplace-sync.json").read_text(encoding="utf-8"))
        self.assertEqual(2, ledger["schema_version"])
        self.assertNotIn("README.md", ledger["managed_paths"])

    def test_cli_rejects_invalid_flag_combinations(self):
        from scripts import package_marketplace

        for args in (
            ["--target", "marketplace"],
            ["--sync-target", "marketplace", "--marketplace-readme", "overview.md"],
            ["--target", "marketplace", "--marketplace-readme", "overview.md", "--adopt-existing"],
            ["--sync-target", "marketplace", "--adopt-existing", "--migrate-v1"],
        ):
            with self.subTest(args=args), mock.patch.object(sys, "stderr"):
                with self.assertRaises(SystemExit):
                    package_marketplace.parse_args(args)


class MarketplaceDoctorSmokeTest(unittest.TestCase):
    def test_generated_marketplace_plugin_runs_doctor(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_root = temp_root / "source"
            target_root = temp_root / "marketplace"
            overview = temp_root / "overview.md"
            overview.write_text("# Marketplace\n", encoding="utf-8")
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
                    "--marketplace-readme",
                    str(overview),
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
            smoke = subprocess.run(
                [sys.executable, "bin/spl", "doctor"],
                cwd=plugin_root,
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
