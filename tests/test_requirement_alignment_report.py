import textwrap
import unittest


class RequirementAlignmentReportContractTest(unittest.TestCase):
    def test_alignment_report_status_block_shape(self):
        content = textwrap.dedent(
            """
            ```yaml
            session_id: alignment-session
            requirement_alignment_status: PASS
            unmet_requirement_count: 0
            unchecked_acceptance_count: 0
            prd_path: .superlooper/context/alignment-session/prd.md
            test_report_path: .superlooper/reports/alignment-session/test_report.md
            apply_report_path: .superlooper/reports/alignment-session/apply_report.json
            report_path: .superlooper/reports/alignment-session/requirement_alignment_report.md
            ```

            # Requirement Alignment Report

            | PRD Ref | Status | Evidence |
            | --- | --- | --- |
            | REQ-001 | PASS | src/main/java/App.java |
            """
        ).strip()
        self.assertIn("requirement_alignment_status: PASS", content)
        self.assertIn("unmet_requirement_count: 0", content)
        self.assertIn("unchecked_acceptance_count: 0", content)


if __name__ == "__main__":
    unittest.main()
