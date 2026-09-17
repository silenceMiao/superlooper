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


class RepositoryDocumentationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.user_guide = (cls.repo_root / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")
        cls.readme = (cls.repo_root / "README.md").read_text(encoding="utf-8")
        cls.codex = (cls.repo_root / "docs" / "CODEX.md").read_text(encoding="utf-8")
        cls.development = (cls.repo_root / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
        cls.release = (cls.repo_root / "docs" / "RELEASE.md").read_text(encoding="utf-8")

    def test_user_docs_publish_task_name_creation_and_generated_task_id(self):
        for content in (self.user_guide, self.readme):
            self.assertIn('/superlooper:spl requirements.md [--task-name "商城后台"]', content)
            self.assertIn('$superlooper requirements.md [--task-name "商城后台"]', content)
            self.assertNotIn("[session_id]", content)
            self.assertNotIn("<session_id>", content)
        self.assertIn("master-framework-YYYYMMDDHHMMSS", self.user_guide)
        self.assertIn("task_name", self.user_guide)
        self.assertIn("可重复", self.user_guide)
        self.assertIn("Unicode", self.user_guide)
        self.assertIn("未命名任务", self.user_guide)

    def test_current_docs_use_task_id_for_existing_task_operations(self):
        for content in (self.user_guide, self.codex, self.development, self.release):
            self.assertNotIn("[session_id]", content)
            self.assertNotIn("<session_id>", content)
        for command in [
            "/superlooper:spl:resume <task_id>",
            "/superlooper:spl:status <task_id>",
            "$superlooper-resume <task_id>",
            "$superlooper-status <task_id>",
        ]:
            self.assertIn(command, self.user_guide)

    def test_runtime_dependency_and_preflight_boundaries_are_documented(self):
        for content in (self.user_guide, self.codex, self.development, self.release):
            self.assertIn("workflow runtime dependency", content)
            self.assertIn("python --version", content)
            self.assertIn("不自动安装 Python", content)
            self.assertIn("PATH", content)
            self.assertIn("sandbox", content)
        self.assertIn("当前 Agent 会话无法执行 Python；Superlooper workflow 在该环境中不可用", self.user_guide)

    def test_release_guide_separates_acceptance_layers_and_e2e_prerequisites(self):
        for layer in [
            "strict",
            "package/compile/unit",
            "doctor",
            "artifact/Marketplace smoke",
            "release consistency",
            "platform E2E",
            "runtime preflight",
        ]:
            self.assertIn(layer, self.release)
        self.assertIn("sys.executable", self.release)
        self.assertIn("NOT_RUN_ENVIRONMENT_PREREQUISITE", self.release)
        self.assertIn("支持环境中插件功能失败", self.release)
        self.assertIn("不能冒充 E2E PASS", self.release)
        self.assertIn("Claude Code 与 Codex 各自", self.release)


if __name__ == "__main__":
    unittest.main()
