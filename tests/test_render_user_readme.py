import tempfile
import unittest
from pathlib import Path


class RenderUserReadmeTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.guide = self.root / "USER_GUIDE.md"
        self.output = self.root / "README.md"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_guide(self, content):
        self.guide.write_text(content, encoding="utf-8")

    def test_extracts_public_section_for_source_audience(self):
        from scripts.render_user_readme import extract_public_readme

        self._write_guide(
            "内部开发规则\n"
            "<!-- public-readme:start -->\n"
            "# Superlooper\n\n"
            "[指南]({{USER_GUIDE_LINK}})\n\n"
            "{{SOURCE_MAINTENANCE_LINKS}}\n"
            "<!-- public-readme:end -->\n"
        )

        source = extract_public_readme(self.guide, "source")

        self.assertIn("(docs/USER_GUIDE.md)", source)
        self.assertIn("[开发说明](docs/DEVELOPMENT.md)", source)
        self.assertNotIn("内部开发规则", source)
        self.assertTrue(source.endswith("\n"))
        self.assertFalse(source.endswith("\n\n"))

    def test_rejects_invalid_markers_and_unknown_audience(self):
        from scripts.render_user_readme import UserReadmeError, extract_public_readme

        invalid_guides = (
            "missing",
            "<!-- public-readme:start -->\ntext\n<!-- public-readme:start -->\n<!-- public-readme:end -->",
            "<!-- public-readme:end -->\n<!-- public-readme:start -->",
            "<!-- public-readme:start -->\n<!-- public-readme:end -->",
        )
        for content in invalid_guides:
            with self.subTest(content=content):
                self._write_guide(content)
                with self.assertRaises(UserReadmeError):
                    extract_public_readme(self.guide, "source")

        self._write_guide("<!-- public-readme:start -->\ntext\n<!-- public-readme:end -->")
        for audience in ("invalid", "marketplace"):
            with self.subTest(audience=audience):
                with self.assertRaisesRegex(UserReadmeError, "未知 README 受众"):
                    extract_public_readme(self.guide, audience)

    def test_render_and_check_detect_drift(self):
        from scripts.render_user_readme import UserReadmeError, assert_user_readme_current, render_user_readme

        self._write_guide("<!-- public-readme:start -->\n# Public\n<!-- public-readme:end -->")
        render_user_readme(self.guide, self.output)
        assert_user_readme_current(self.guide, self.output, "source")

        self.output.write_text("manual\n", encoding="utf-8")
        with self.assertRaisesRegex(UserReadmeError, "未由用户指南生成"):
            assert_user_readme_current(self.guide, self.output, "source")


if __name__ == "__main__":
    unittest.main()
