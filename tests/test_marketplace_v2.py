import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class MarketplaceV2Test(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "source"
        self.target = Path(self.temp_dir.name) / "marketplace"
        self.overview = Path(self.temp_dir.name) / "overview.md"
        self.overview.write_text("# Test Marketplace\n", encoding="utf-8")
        self._write_source()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_source(self):
        files = {
            ".claude-plugin/plugin.json": {
                "name": "superlooper",
                "displayName": "Superlooper",
                "version": "1.0.0",
                "description": "test plugin",
                "author": {"name": "tester"},
                "license": "MIT",
            },
            ".codex-plugin/plugin.json": {
                "name": "superlooper",
                "version": "1.0.0",
                "description": "test plugin",
                "author": {"name": "tester"},
                "license": "MIT",
                "skills": "./codex/skills/",
            },
            "README.md": "# Superlooper\n",
            "LICENSE": "MIT\n",
        }
        for relative_path, content in files.items():
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(content) if isinstance(content, dict) else content, encoding="utf-8")

    @staticmethod
    def _packager(release_files):
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

    def test_new_marketplace_copies_overview_and_uses_plugin_only_ledger(self):
        from scripts import package_marketplace

        release_files = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "README.md", "LICENSE"]
        with mock.patch.object(package_marketplace, "PluginPackager", self._packager(release_files)):
            package_marketplace.package_marketplace(
                root=self.root,
                target=self.target,
                marketplace_readme=self.overview,
            )

        self.assertEqual("# Test Marketplace\n", (self.target / "README.md").read_text(encoding="utf-8"))
        ledger = json.loads((self.target / ".superlooper-marketplace-sync.json").read_text(encoding="utf-8"))
        self.assertEqual(2, ledger["schema_version"])
        self.assertEqual(
            {f"plugins/superlooper/{path}" for path in release_files},
            set(ledger["managed_paths"]),
        )

    def test_sync_preserves_overview_and_other_registry_entries(self):
        from scripts import package_marketplace

        release_files = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "README.md", "LICENSE"]
        with mock.patch.object(package_marketplace, "PluginPackager", self._packager(release_files)):
            package_marketplace.package_marketplace(
                root=self.root,
                target=self.target,
                marketplace_readme=self.overview,
            )
            (self.target / "README.md").write_text("# Maintained overview\n", encoding="utf-8")
            for relative_path in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
                path = self.target / relative_path
                metadata = json.loads(path.read_text(encoding="utf-8"))
                metadata["plugins"].insert(0, {"name": "other", "source": "./plugins/other", "version": "9.0.0"})
                path.write_text(json.dumps(metadata), encoding="utf-8")
            package_marketplace.sync_marketplace(root=self.root, target=self.target)

        self.assertEqual("# Maintained overview\n", (self.target / "README.md").read_text(encoding="utf-8"))
        for relative_path in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            metadata = json.loads((self.target / relative_path).read_text(encoding="utf-8"))
            self.assertEqual("other", metadata["plugins"][0]["name"])
            self.assertEqual("superlooper", metadata["plugins"][1]["name"])

    def test_sync_migrates_clean_v1_ledger_without_rewriting_overview(self):
        from scripts import package_marketplace

        release_files = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "README.md", "LICENSE"]
        with mock.patch.object(package_marketplace, "PluginPackager", self._packager(release_files)):
            package_marketplace.package_marketplace(
                root=self.root,
                target=self.target,
                marketplace_readme=self.overview,
            )
            managed_paths = {
                "README.md",
                ".claude-plugin/marketplace.json",
                ".agents/plugins/marketplace.json",
                *{f"plugins/superlooper/{path}" for path in release_files},
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
            (self.target / ".superlooper-marketplace-sync.json").write_text(
                json.dumps(legacy), encoding="utf-8"
            )
            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "--migrate-v1"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)

            package_marketplace.sync_marketplace(root=self.root, target=self.target, migrate_v1=True)

        self.assertEqual("# Test Marketplace\n", (self.target / "README.md").read_text(encoding="utf-8"))
        ledger = json.loads((self.target / ".superlooper-marketplace-sync.json").read_text(encoding="utf-8"))
        self.assertEqual(2, ledger["schema_version"])
        self.assertNotIn("README.md", ledger["managed_paths"])

    def test_sync_rejects_duplicate_superlooper_entries_without_overview_change(self):
        from scripts import package_marketplace

        release_files = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "README.md", "LICENSE"]
        with mock.patch.object(package_marketplace, "PluginPackager", self._packager(release_files)):
            package_marketplace.package_marketplace(
                root=self.root,
                target=self.target,
                marketplace_readme=self.overview,
            )
            metadata_path = self.target / ".claude-plugin/marketplace.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["plugins"].append(dict(metadata["plugins"][0]))
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            with self.assertRaisesRegex(package_marketplace.MarketplaceError, "重复"):
                package_marketplace.sync_marketplace(root=self.root, target=self.target)

        self.assertEqual("# Test Marketplace\n", (self.target / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
