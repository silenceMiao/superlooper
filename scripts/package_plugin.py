import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from render_user_readme import UserReadmeError, assert_user_readme_current
except ModuleNotFoundError:
    from scripts.render_user_readme import UserReadmeError, assert_user_readme_current


SUPPORTED_MODES = {"source", "install"}
BLOCKED_PATH_PREFIXES = [
    ".learnings/",
    "dist/",
    "docs/superpowers/",
    "scripts/__pycache__/",
]
INSTALL_ONLY_BLOCKED_PATH_PREFIXES = [
    "docs/design/",
    "tests/",
]
BLOCKED_EXACT_PATHS = {
    ".env",
}
BLOCKED_PATH_COMPONENTS = {".superlooper", ".claude", "__pycache__"}
INSTALL_RUNTIME_REQUIRED_FILES = frozenset(
    {
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        "codex/dispatcher/README.md",
        "codex/skills/superlooper/SKILL.md",
        "codex/skills/superlooper-prd/SKILL.md",
        "codex/skills/superlooper-ui/SKILL.md",
        "codex/skills/superlooper-design/SKILL.md",
        "codex/skills/superlooper-run/SKILL.md",
        "codex/skills/superlooper-status/SKILL.md",
        "codex/skills/superlooper-resume/SKILL.md",
        "codex/skills/superlooper-doctor/SKILL.md",
        "README.md",
        "docs/USER_GUIDE.md",
        "LICENSE",
        "commands/spl.md",
        "commands/spl/prd.md",
        "commands/spl/ui.md",
        "commands/spl/design.md",
        "commands/spl/run.md",
        "commands/spl/status.md",
        "commands/spl/resume.md",
        "commands/spl/doctor.md",
        "skills/superlooper/SKILL.md",
        "agents/analyst.md",
        "agents/ui-architect.md",
        "agents/architect.md",
        "agents/developer.md",
        "agents/code-reviewer.md",
        "agents/system_merger.md",
        "agents/tester.md",
        "agents/workspace_applier.md",
        "agents/requirement-verifier.md",
        "agents/impact-analyzer.md",
        "configs/interaction-flow.json",
        "schemas/artifact-manifest.schema.json",
        "schemas/execution-manifest.schema.json",
        "schemas/interaction-flow.schema.json",
        "schemas/module-split.schema.json",
        "schemas/session-state.schema.json",
        "docs/agent-flows/analyst-flow.md",
        "docs/agent-flows/ui-architect-flow.md",
        "docs/agent-flows/architect-flow.md",
        "scripts/apply_to_workspace.py",
        "scripts/build_execution_summary.py",
        "scripts/build_session_report.py",
        "scripts/create_session.py",
        "scripts/doctor.py",
        "scripts/generate_execution_manifest.py",
        "scripts/generate_runtime_agents.py",
        "scripts/initialize_project_structure.py",
        "scripts/merge_artifacts.py",
        "scripts/normalize_user_intent.py",
        "scripts/package_plugin.py",
        "scripts/render_user_readme.py",
        "scripts/resume_session.py",
        "scripts/run_execution_dag.py",
        "scripts/schema_validation.py",
        "scripts/status_session.py",
        "scripts/update_session.py",
        "scripts/validate_miao_contracts.py",
        "bin/spl",
    }
)
INSTALL_RUNTIME_FORBIDDEN_PATHS = frozenset(
    {
        "tests/",
        "docs/design/",
        "docs/requirements/",
        "docs/DEVELOPMENT.md",
        "docs/RELEASE.md",
        "docs/2026-08-14",
        "docs/superlooper-",
        "skills/superlooper-dev/",
        "hooks/",
        "monitors/",
        "output-styles/",
        "themes/",
        ".mcp.json",
        ".lsp.json",
        "settings.json",
        ".gitignore",
        "bin/.gitkeep",
        "commands/.gitkeep",
        "scripts/build_release_archive.py",
        "scripts/package_marketplace.py",
        "CHANGELOG.md",
    }
)
INSTALL_RUNTIME_FORBIDDEN_FILES = frozenset(
    {
        "CHANGELOG.md",
        ".gitignore",
        ".mcp.json",
        ".lsp.json",
        "settings.json",
        "bin/.gitkeep",
        "scripts/build_release_archive.py",
        "scripts/package_marketplace.py",
        "docs/DEVELOPMENT.md",
        "docs/RELEASE.md",
        "docs/superlooper-flow-weight-and-handshake-analysis-v3.md",
        "docs/superlooper-flow-weight-and-handshake-implementation-v3.md",
    }
)
TEXT_FILE_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".properties",
    ".xml",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".scss",
    ".html",
    ".gitignore",
}
PLACEHOLDER_VALUE_PATTERN = re.compile(r"^<[^>]+>$")
REQUIRED_RELEASE_FILES = {
    ".claude-plugin/plugin.json",
    "commands/spl.md",
    "commands/spl/ui.md",
    "commands/spl/run.md",
    "skills/superlooper/SKILL.md",
    "agents/ui-architect.md",
    "agents/impact-analyzer.md",
    "docs/agent-flows/ui-architect-flow.md",
    "scripts/build_execution_summary.py",
    "scripts/normalize_user_intent.py",
    "scripts/doctor.py",
    "bin/spl",
}
SECRET_PATTERNS = [
    "authorization_bearer",
    "access_key_assignment",
    "secret_key_assignment",
    "private_key_assignment",
    "pem_private_key",
    "jdbc_url_credentials",
    "url_credentials",
]
SECRET_REGEXES = {
    "authorization_bearer": re.compile(r"(?im)authorization\s*:\s*bearer\s+([^\s\"'`<]+)"),
    "access_key_assignment": re.compile(r"(?im)access_key\s*[:=]\s*(?:[\"'`])?([^\s\"'`#\\]+)(?:[\"'`])?"),
    "secret_key_assignment": re.compile(r"(?im)secret_key\s*[:=]\s*(?:[\"'`])?([^\s\"'`#\\]+)(?:[\"'`])?"),
    "private_key_assignment": re.compile(r"(?im)private_key\s*[:=]\s*(?:[\"'`])?([^\s\"'`#\\]+)(?:[\"'`])?"),
    "pem_private_key": re.compile("-----BEGIN PRIVATE" + " KEY-----"),
    "jdbc_url_credentials": re.compile(r"jdbc:[^\s:]+://([^\s:/?#]+):([^\s@/?#]+)@[^\s]+", re.IGNORECASE),
    "url_credentials": re.compile(r"https?://([^\s:/?#]+):([^\s@/?#]+)@[^\s]+", re.IGNORECASE),
}


class PackageError(Exception):
    pass


class PluginPackager:
    def __init__(self, root=None, mode="source"):
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"unsupported release mode: {mode}")
        self.root = Path(root or os.getcwd()).resolve()
        self.mode = mode
        self.dist_dir = self.root / "dist"
        self.manifest_path = self.dist_dir / "superlooper-release-manifest.json"

    def run(self):
        self._run_validate()
        compiled_scripts = self._run_py_compile()
        release_files = self._build_release_file_list()
        self._reject_blocked_paths(release_files)
        self._assert_required_release_files(release_files)
        self._scan_secrets(release_files)
        try:
            assert_user_readme_current(self.root / "docs" / "USER_GUIDE.md", self.root / "README.md", "source")
        except UserReadmeError as exc:
            raise PackageError(str(exc)) from exc
        manifest = {
            "plugin_name": self._read_plugin_name(),
            "release_mode": self.mode,
            "workspace_root": ".",
            "release_file_count": len(release_files),
            "release_files": release_files,
            "validation_commands": [
                "claude plugin validate . --strict",
                "python -m py_compile " + " ".join(compiled_scripts),
            ],
            "secret_scan_patterns": list(SECRET_PATTERNS),
            "blocked_release_paths": sorted(BLOCKED_EXACT_PATHS)
            + BLOCKED_PATH_PREFIXES
            + [
                ".env.*",
                "docs/design/ (install mode only)",
                "tests/ (install mode only)",
                "*/.superlooper/*",
                "*/.claude/*",
                "*/__pycache__/*",
            ],
        }
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"release manifest written: {self.manifest_path}")
        return 0

    def _read_plugin_name(self):
        plugin_manifest_path = self.root / ".claude-plugin" / "plugin.json"
        plugin_manifest = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))
        return plugin_manifest["name"]

    def _run_validate(self):
        claude_command = self._claude_command_prefix() + ["plugin", "validate", ".", "--strict"]
        self._run_command(claude_command)

    def _run_py_compile(self):
        scripts = sorted(path for path in (self.root / "scripts").glob("*.py") if path.is_file())
        if not scripts:
            raise PackageError("scripts 目录下没有可编译的 Python 文件。")
        command = [sys.executable, "-m", "py_compile", *[str(path) for path in scripts]]
        self._run_command(command)
        return [self._contract_path(path) for path in scripts]

    def _run_command(self, command):
        completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.stdout:
            self._write_stream(sys.stdout, completed.stdout)
        if completed.stderr:
            self._write_stream(sys.stderr, completed.stderr)
        if completed.returncode != 0:
            raise PackageError(f"命令执行失败: {' '.join(command)}")

    def _write_stream(self, stream, text):
        encoding = getattr(stream, "encoding", None) or "utf-8"
        stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
        stream.flush()

    def _claude_command_prefix(self):
        if os.name == "nt":
            claude_cmd = shutil.which("claude.cmd")
            if claude_cmd:
                return [claude_cmd]
            claude_exe = shutil.which("claude.exe")
            if claude_exe:
                return [claude_exe]
            claude_shim = shutil.which("claude")
            if claude_shim:
                return ["cmd", "/c", "claude"]
            raise PackageError("未找到 claude CLI。")
        claude_binary = shutil.which("claude")
        if not claude_binary:
            raise PackageError("未找到 claude CLI。")
        return [claude_binary]

    def _build_release_file_list(self):
        release_files = []
        for path in sorted(self.root.rglob("*")):
            relative = self._contract_path(path)
            if path.is_symlink():
                raise PackageError(f"发布目录包含符号链接: {relative}")
            if not path.is_file():
                continue
            if self._should_skip_release_path(relative):
                continue
            release_files.append(relative)
        if not release_files:
            raise PackageError("发布清单为空。")
        return release_files

    def _should_skip_release_path(self, relative_path):
        parts = relative_path.split("/")
        if parts[0] == ".git":
            return True
        if relative_path in BLOCKED_EXACT_PATHS:
            return True
        if self._is_env_variant(relative_path):
            return True
        if any(relative_path.startswith(prefix) for prefix in BLOCKED_PATH_PREFIXES):
            return True
        if any(part in BLOCKED_PATH_COMPONENTS for part in parts):
            return True
        if self.mode == "install" and relative_path not in INSTALL_RUNTIME_REQUIRED_FILES:
            return True
        return False

    def _reject_blocked_paths(self, release_files):
        blocked = []
        for relative in release_files:
            if relative in BLOCKED_EXACT_PATHS or self._is_env_variant(relative):
                blocked.append(relative)
                continue
            if any(relative.startswith(prefix) for prefix in BLOCKED_PATH_PREFIXES):
                blocked.append(relative)
                continue
            if any(part in BLOCKED_PATH_COMPONENTS for part in relative.split("/")):
                blocked.append(relative)
                continue
            if self.mode == "install" and relative not in INSTALL_RUNTIME_REQUIRED_FILES:
                blocked.append(relative)
        if blocked:
            raise PackageError(f"发布清单包含禁止路径: {', '.join(sorted(blocked))}")

    def _assert_required_release_files(self, release_files):
        required_files = INSTALL_RUNTIME_REQUIRED_FILES if self.mode == "install" else REQUIRED_RELEASE_FILES
        missing = sorted(required_files.difference(release_files))
        if missing:
            raise PackageError(f"发布清单缺少必需文件: {', '.join(missing)}")

    def _scan_secrets(self, release_files):
        findings = []
        for relative in release_files:
            if not self._is_text_file(relative):
                continue
            path = self.root / relative
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern_name, secret_regex in SECRET_REGEXES.items():
                if pattern_name == "pem_private_key":
                    if secret_regex.search(content):
                        findings.append(f"{relative}: {pattern_name}")
                    continue
                for match in secret_regex.finditer(content):
                    if self._match_contains_real_secret(pattern_name, match):
                        findings.append(f"{relative}: {pattern_name}")
                        break
        if findings:
            raise PackageError("检测到疑似秘钥内容: " + "; ".join(findings))

    def _match_contains_real_secret(self, pattern_name, match):
        if pattern_name in {"jdbc_url_credentials", "url_credentials"}:
            values = [group.strip() for group in match.groups()]
            return all(self._is_real_secret_value(value) for value in values)
        value = match.group(1).strip().strip('"\'`')
        return self._is_real_secret_value(value)

    def _is_real_secret_value(self, value):
        if not value:
            return False
        if PLACEHOLDER_VALUE_PATTERN.fullmatch(value):
            return False
        lowered = value.lower()
        if lowered in {"example", "example_value", "changeme", "your_value", "null", "none"}:
            return False
        return True

    def _is_text_file(self, relative_path):
        suffix = Path(relative_path).suffix.lower()
        if suffix in TEXT_FILE_SUFFIXES:
            return True
        name = Path(relative_path).name
        return name in {"LICENSE", ".gitignore"}

    def _is_env_variant(self, relative_path):
        name = Path(relative_path).name
        return name == ".env" or name.startswith(".env.")

    def _contract_path(self, path):
        return str(path.relative_to(self.root)).replace("\\", "/")


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="source")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        packager = PluginPackager(mode=args.mode)
        return packager.run()
    except (PackageError, ValueError) as exc:
        print(f"package plugin failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
