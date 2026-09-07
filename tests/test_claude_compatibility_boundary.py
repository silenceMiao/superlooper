import json
import subprocess
import sys
import unittest
from pathlib import Path


class ClaudeCompatibilityBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_claude_protocol_files_keep_their_existing_contract(self):
        claude_manifest = (self.root / ".claude-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
        claude_skill = (self.root / "skills" / "superlooper" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        root_command = (self.root / "commands" / "spl.md").read_text(encoding="utf-8")
        command_files = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((self.root / "commands" / "spl").glob("*.md"))
        )
        interaction_flow = json.loads(
            (self.root / "configs" / "interaction-flow.json").read_text(encoding="utf-8")
        )

        self.assertIn('"name": "superlooper"', claude_manifest)
        self.assertIn('"commands": "./commands/"', claude_manifest)
        self.assertIn("# /superlooper:spl", root_command)
        self.assertIn('"/spl:', command_files)
        self.assertIn("Runtime Module Constraints", claude_skill)
        self.assertIn(".claude/agents/generated/superlooper/", claude_skill)
        self.assertEqual("/spl", interaction_flow["commands"][0]["name"])

    def test_doctor_keeps_the_claude_plugin_checks_green(self):
        completed = subprocess.run(
            [sys.executable, "bin/spl", "doctor"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("plugin_validate: PASS", completed.stdout)
        self.assertIn("release_filter: PASS", completed.stdout)


if __name__ == "__main__":
    unittest.main()
