import re
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
            "# Superlooper 用户指南\n\n"
            "内部开发规则\n"
            "<!-- public-readme:start -->\n"
            "公开内容\n"
            "<!-- public-readme:end -->\n"
        )

        source = extract_public_readme(self.guide, "source")

        self.assertTrue(source.startswith("# Superlooper\n"))
        self.assertIn("[完整用户指南](docs/USER_GUIDE.md)", source)
        self.assertIn("公开内容", source)
        self.assertNotIn("内部开发规则", source)
        self.assertNotIn("docs/DEVELOPMENT.md", source)
        self.assertNotIn("docs/RELEASE.md", source)
        self.assertTrue(source.endswith("\n"))
        self.assertFalse(source.endswith("\n\n"))

    def test_rejects_invalid_markers_and_unknown_audience(self):
        from scripts.render_user_readme import UserReadmeError, extract_public_readme

        invalid_guides = (
            "missing",
            "<!-- public-readme:start -->\ntext\n<!-- public-readme:start -->\n<!-- public-readme:end -->",
            "<!-- public-readme:end -->\n<!-- public-readme:start -->",
            "<!-- public-readme:start -->\n<!-- public-readme:end -->",
            "<!-- public-readme:start -->\n{{UNKNOWN}}\n<!-- public-readme:end -->",
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

    def test_user_docs_start_with_required_runtime_prerequisites(self):
        required_sections = [
            "## 运行前提",
            "## 快速开始",
            "## Python 运行边界",
            "## 新建任务与身份",
        ]
        required_content = [
            "1. Python 3.9+。",
            "2. `python` 命令在当前实际 Agent parent session 中可执行。",
            "3. 目标项目目录允许创建 `.superlooper/` 运行数据。",
            "4. Codex 完整工作流必须使用 `workspace-write`、non-ephemeral parent session。",
            "- 自动安装 Python；",
            "- 修改系统 `PATH`；",
            "- 扩大 sandbox 或工具权限；",
            "- 静默覆盖工作区中的同路径不同内容文件。",
        ]

        for content in (self.user_guide, self.readme):
            positions = [content.index(section) for section in required_sections]
            self.assertEqual(sorted(positions), positions)
            for expected in required_content:
                self.assertIn(expected, content)

    def test_user_guide_and_public_readme_have_no_broken_template_links(self):
        prose = re.sub(r"```.*?```", "", self.user_guide, flags=re.DOTALL)
        top_level_headings = [
            line
            for line in prose.splitlines()
            if line.startswith("# ")
        ]

        self.assertEqual(["# Superlooper 用户指南"], top_level_headings)
        self.assertNotIn("{{", self.user_guide)
        self.assertNotIn("}}", self.user_guide)
        self.assertIn("[完整用户指南](docs/USER_GUIDE.md)", self.readme)
        self.assertNotIn("docs/DEVELOPMENT.md", self.readme)
        self.assertNotIn("docs/RELEASE.md", self.readme)

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
