import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class CodexMarketplaceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "source"
        self.target = Path(self.temp_dir.name) / "marketplace"
        self.overview = Path(self.temp_dir.name) / "overview.md"
        self.overview.write_text("# Marketplace\n", encoding="utf-8")
        self._create_source_tree()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_source_tree(self):
        files = {
            ".claude-plugin/plugin.json": {
                "name": "superlooper",
                "displayName": "Superlooper",
                "version": "1.1.0",
                "description": "test plugin",
                "author": {"name": "tester"},
                "license": "MIT",
            },
            ".codex-plugin/plugin.json": {
                "name": "superlooper",
                "version": "1.1.0",
                "description": "test plugin",
                "author": {"name": "tester"},
                "license": "MIT",
                "skills": "./codex/skills/",
            },
            "README.md": "# Test\n",
            "LICENSE": "MIT License\n",
        }
        for relative_path, content in files.items():
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, dict):
                path.write_text(json.dumps(content), encoding="utf-8")
            else:
                path.write_text(content, encoding="utf-8")

    def test_marketplace_materializes_matching_claude_and_codex_entries(self):
        from scripts import package_marketplace

        release_files = [
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
            "README.md",
            "LICENSE",
        ]

        class FakePackager:
            def __init__(self, root, mode):
                self.root = Path(root)
                self.mode = mode
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
                return 0

        with mock.patch.object(package_marketplace, "PluginPackager", FakePackager):
            package_marketplace.package_marketplace(
                root=self.root,
                target=self.target,
                marketplace_readme=self.overview,
            )

        claude_marketplace = json.loads(
            (self.target / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        codex_marketplace = json.loads(
            (self.target / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        claude_plugin = claude_marketplace["plugins"][0]
        codex_plugin = codex_marketplace["plugins"][0]

        self.assertEqual(claude_marketplace["name"], codex_marketplace["name"])
        self.assertEqual(claude_plugin["name"], codex_plugin["name"])
        self.assertEqual(claude_plugin["version"], codex_plugin["version"])
        self.assertEqual(claude_plugin["source"], codex_plugin["source"])
        self.assertTrue((self.target / "plugins" / "superlooper" / ".claude-plugin" / "plugin.json").is_file())
        self.assertTrue((self.target / "plugins" / "superlooper" / ".codex-plugin" / "plugin.json").is_file())


class CodexDocumentationTest(unittest.TestCase):
    def test_codex_documentation_describes_current_support_and_equivalence(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "docs" / "CODEX.md").read_text(encoding="utf-8")

        self.assertNotIn("当前未支持 Codex", content)
        self.assertIn("功能、流程、产物和质量门禁等价", content)
        self.assertIn("Python", content)
        self.assertIn("workspace-write", content)
        self.assertNotIn("read-only", content)
        self.assertIn("--platform codex", content)

    def test_user_guide_describes_codex_workspace_write_runtime_prerequisite(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")

        self.assertIn("Python runtime", content)
        self.assertIn("workspace-write", content)
        self.assertNotIn("read-only", content)
        self.assertIn("运行 doctor 的 Codex parent session", content)
        self.assertIn("不要通过扩大权限", content)

    def test_runtime_documentation_keeps_adapter_requirements_in_codex_document(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "docs" / "CODEX.md").read_text(encoding="utf-8")

        self.assertIn("宿主 shell 能执行 Python 不足以证明", content)
        self.assertIn("当前 Codex parent session", content)
        self.assertIn("不要通过重启系统", content)
        self.assertIn("--platform codex", content)

    def test_release_documentation_requires_workspace_write_codex_e2e(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "docs" / "RELEASE.md").read_text(encoding="utf-8")

        self.assertIn("workspace-write", content)
        self.assertNotIn("只读 parent session", content)
        self.assertNotIn("read-only", content)

    def test_manifests_and_changelog_use_version_1_1_1(self):
        root = Path(__file__).resolve().parents[1]
        claude_manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        codex_manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertEqual("1.1.1", claude_manifest["version"])
        self.assertEqual("1.1.1", codex_manifest["version"])
        self.assertIn("## 1.1.1", changelog)


if __name__ == "__main__":
    unittest.main()
