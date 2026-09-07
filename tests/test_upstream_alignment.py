import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class UpstreamAlignmentContractTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.session_id = "session_alignment"
        self.reports_dir = self.workspace_root / ".superlooper" / "reports" / self.session_id
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_validator(self):
        return subprocess.run(
            [
                sys.executable,
                str(self.repo_root / "scripts" / "validate_miao_contracts.py"),
                "--workspace-root",
                str(self.workspace_root),
                "--session-id",
                self.session_id,
                "--scope",
                "upstream-alignment",
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_report(
        self,
        status="PASS",
        mismatch_count=0,
        loop_required="false",
        loop_target_phase="design",
        blocking_decisions=None,
        inline_empty_decisions=False,
    ):
        decisions = blocking_decisions or []
        lines = [
            "```yaml",
            f"session_id: {self.session_id}",
            f"upstream_alignment_status: {status}",
            f"mismatch_count: {mismatch_count}",
            f"loop_required: {loop_required}",
            f"loop_target_phase: {loop_target_phase}",
        ]
        if inline_empty_decisions:
            lines.append("blocking_decisions: []")
        else:
            lines.append("blocking_decisions:")
            lines.extend(f"  - {item}" for item in decisions)
        lines.append(f"report_path: .superlooper/reports/{self.session_id}/upstream_alignment.md")
        lines.append("```")
        (self.reports_dir / "upstream_alignment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_pass_alignment_is_valid(self):
        self.write_report()
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_pass_alignment_accepts_inline_empty_decisions(self):
        self.write_report(inline_empty_decisions=True)
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pass_alignment_requires_zero_mismatch(self):
        self.write_report(mismatch_count=1)
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mismatch_count", result.stderr)

    def test_fail_alignment_requires_loop(self):
        self.write_report(status="FAIL", mismatch_count=1, loop_required="false")
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("loop_required", result.stderr)

    def test_blocked_alignment_requires_decision(self):
        self.write_report(status="BLOCKED")
        result = self.run_validator()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("blocking_decisions", result.stderr)

    def test_blocked_alignment_accepts_decision(self):
        self.write_report(status="BLOCKED", blocking_decisions=["DEC-001 需要用户确认支付方式"])
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
