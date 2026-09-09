import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import verify_release_consistency as verifier
from scripts.render_user_readme import extract_public_readme


class VerifyReleaseV2Test(unittest.TestCase):
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

    def _write_source(self):
        claude_manifest = {
            "name": "superlooper",
            "version": "1.0.0",
            "license": "MIT",
            "displayName": "Superlooper",
            "description": "test plugin",
            "author": {"name": "tester"},
        }
        codex_manifest = {"name": "superlooper", "version": "1.0.0", "license": "MIT"}
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

    def _write_marketplace(self):
        other = {"name": "other", "version": "9.0.0", "source": "./plugins/other"}
        superlooper = {"name": "superlooper", "version": "1.0.0", "source": "./plugins/superlooper"}
        self._write_json(
            self.marketplace_root,
            ".claude-plugin/marketplace.json",
            {"name": "superAI-marketplace", "plugins": [other, superlooper]},
        )
        self._write_json(
            self.marketplace_root,
            ".agents/plugins/marketplace.json",
            {"name": "superAI-marketplace", "plugins": [other, superlooper]},
        )
        managed_paths = {}
        for relative_path in self.release_files:
            destination = self.marketplace_root / "plugins" / "superlooper" / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.source_root / relative_path).read_bytes())
            managed_paths[f"plugins/superlooper/{relative_path}"] = hashlib.sha256(destination.read_bytes()).hexdigest()
        self._write_json(
            self.marketplace_root,
            ".superlooper-marketplace-sync.json",
            {
                "schema_version": 2,
                "plugin_name": "superlooper",
                "plugin_version": "1.0.0",
                "source_commit": None,
                "managed_paths": managed_paths,
            },
        )

    def test_accepts_shared_registry_and_marketplace_owned_readme(self):
        result = verifier.verify_release_consistency(self.source_root, self.marketplace_root)

        self.assertTrue(result.ok, result.errors)

    def test_rejects_duplicate_superlooper_registry_entry(self):
        path = self.marketplace_root / ".claude-plugin" / "marketplace.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["plugins"].append(dict(metadata["plugins"][1]))
        path.write_text(json.dumps(metadata), encoding="utf-8")

        result = verifier.verify_release_consistency(self.source_root, self.marketplace_root)

        self.assertFalse(result.ok)
        self.assertTrue(any("重复" in error for error in result.errors), result.errors)


if __name__ == "__main__":
    unittest.main()
