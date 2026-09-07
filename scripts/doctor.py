import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from package_plugin import INSTALL_RUNTIME_FORBIDDEN_FILES, INSTALL_RUNTIME_REQUIRED_FILES, PackageError, PluginPackager


COMMAND_FILES = [
    "commands/spl.md",
    "commands/spl/prd.md",
    "commands/spl/ui.md",
    "commands/spl/design.md",
    "commands/spl/run.md",
    "commands/spl/status.md",
    "commands/spl/resume.md",
    "commands/spl/doctor.md",
]
FORBIDDEN_COMMAND_FILE = "commands/spl/manifest.md"
REQUIRED_RELEASE_INCLUDE = ".claude-plugin/plugin.json"
REQUIRED_SCHEMA_FILES = [
    "schemas/artifact-manifest.schema.json",
    "schemas/execution-manifest.schema.json",
    "schemas/interaction-flow.schema.json",
    "schemas/module-split.schema.json",
    "schemas/session-state.schema.json",
]
REQUIRED_AGENT_FILES = [
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
]
CODEX_SKILL_NAMES = {
    "superlooper",
    "superlooper-prd",
    "superlooper-ui",
    "superlooper-design",
    "superlooper-run",
    "superlooper-status",
    "superlooper-resume",
    "superlooper-doctor",
}
CODEX_SKILLS_PATH = "./codex/skills/"
CODEX_DISPATCHER_REQUIRED_TEXT = [
    "execution_manifest.json",
    "sole source",
    "spawn_agent",
    "non-ephemeral",
    "second DAG representation",
]


REQUIRED_RELEASE_EXCLUDE = [
    ".superlooper/runtime.txt",
    ".claude/CLAUDE.md",
    ".learnings/note.md",
    "docs/superpowers/demo.md",
    "docs/design/demo.md",
    "dist/demo.zip",
    "scripts/__pycache__/cached.pyc",
    "nested/__pycache__/cached.pyc",
    ".env",
    ".env.local",
    "tests/test_demo.py",
]


class DoctorError(Exception):
    pass


class DoctorRunner:
    def __init__(self, workspace_root, session_id=None, plugin_root=None, platform="claude"):
        self.workspace_root = Path(workspace_root).resolve()
        self.plugin_root = Path(plugin_root).resolve() if plugin_root else Path(__file__).resolve().parents[1]
        self.session_id = session_id
        self.platform = platform
        self.packager = PluginPackager(root=self.plugin_root, mode="install")
        self.results = []

    def run(self):
        if self.platform == "claude":
            self._run_check("plugin_validate", self.check_plugin_validate)
        self._run_check("python_compile", self.check_python_compile)
        self._run_check("commands_contract", self.check_commands_contract)
        self._run_check("schema_contract", self.check_schema_contract)
        self._run_check("agent_contract", self.check_agent_contract)
        self._run_check("forbidden_manifest_command", self.check_forbidden_manifest_command)
        self._run_check("release_filter", self.check_release_filter)
        self._run_check("session_contract", self.check_session_contract)
        self._run_check("codex_plugin", self.check_codex_plugin)
        self._run_check("codex_skills", self.check_codex_skills)
        self._run_check("codex_dispatcher", self.check_codex_dispatcher)
        for check_name, status, message in self.results:
            self._print_line(f"{check_name}: {status} - {message}")
        return 1 if any(status == "FAIL" for _, status, _ in self.results) else 0

    def _run_check(self, check_name, func):
        try:
            status, message = func()
        except Exception as exc:
            status, message = "FAIL", str(exc)
        self.results.append((check_name, status, self._single_line(message)))

    def check_plugin_validate(self):
        command = [*self.packager._claude_command_prefix(), "plugin", "validate", ".", "--strict"]
        completed = self._run_command(command)
        if completed.returncode != 0:
            return "FAIL", completed.stderr or completed.stdout or "claude plugin validate failed"
        return "PASS", "claude plugin validate . --strict"

    def check_python_compile(self):
        scripts = sorted(path for path in (self.plugin_root / "scripts").glob("*.py") if path.is_file())
        if not scripts:
            return "FAIL", "scripts 目录下没有可编译的 Python 文件"
        for path in scripts:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        return "PASS", f"compiled {len(scripts)} scripts"

    def check_commands_contract(self):
        missing = [relative for relative in COMMAND_FILES if not (self.plugin_root / relative).exists()]
        if missing:
            return "FAIL", "missing: " + ", ".join(missing)
        return "PASS", f"found {len(COMMAND_FILES)} command files"

    def check_schema_contract(self):
        missing = [relative for relative in REQUIRED_SCHEMA_FILES if not (self.plugin_root / relative).exists()]
        if missing:
            return "FAIL", "missing: " + ", ".join(missing)
        for relative in REQUIRED_SCHEMA_FILES:
            path = self.plugin_root / relative
            try:
                schema = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return "FAIL", f"invalid JSON: {relative}: {exc}"
            if not isinstance(schema, dict):
                return "FAIL", f"schema root must be object: {relative}"
        return "PASS", f"parsed {len(REQUIRED_SCHEMA_FILES)} schema files"

    def check_agent_contract(self):
        missing = [relative for relative in REQUIRED_AGENT_FILES if not (self.plugin_root / relative).exists()]
        if missing:
            return "FAIL", "missing: " + ", ".join(missing)
        return "PASS", f"found {len(REQUIRED_AGENT_FILES)} agent files"

    def check_codex_plugin(self):
        claude_manifest_path = self.plugin_root / ".claude-plugin" / "plugin.json"
        codex_manifest_path = self.plugin_root / ".codex-plugin" / "plugin.json"
        if not codex_manifest_path.is_file():
            return "FAIL", "missing: .codex-plugin/plugin.json"
        claude_manifest = json.loads(claude_manifest_path.read_text(encoding="utf-8"))
        codex_manifest = json.loads(codex_manifest_path.read_text(encoding="utf-8"))
        fields = ("name", "version", "license")
        mismatched = [field for field in fields if codex_manifest.get(field) != claude_manifest.get(field)]
        if mismatched:
            return "FAIL", "mismatch with Claude manifest: " + ", ".join(mismatched)
        self._codex_skills_root(codex_manifest)
        return "PASS", "Codex name, version, license, and skills path match the runtime contract"

    def check_codex_skills(self):
        codex_manifest_path = self.plugin_root / ".codex-plugin" / "plugin.json"
        if not codex_manifest_path.is_file():
            return "FAIL", "missing: .codex-plugin/plugin.json"
        codex_manifest = json.loads(codex_manifest_path.read_text(encoding="utf-8"))
        skills_root = self._codex_skills_root(codex_manifest)
        actual_names = {path.parent.name for path in skills_root.glob("*/SKILL.md")}
        if actual_names != CODEX_SKILL_NAMES:
            missing = sorted(CODEX_SKILL_NAMES - actual_names)
            extra = sorted(actual_names - CODEX_SKILL_NAMES)
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extra:
                details.append("unexpected: " + ", ".join(extra))
            return "FAIL", "; ".join(details)
        invalid = []
        for skill_name in sorted(CODEX_SKILL_NAMES):
            path = skills_root / skill_name / "SKILL.md"
            frontmatter = self._read_frontmatter(path)
            if frontmatter.get("name") != skill_name:
                invalid.append(f"{skill_name}: name must equal directory")
            description = frontmatter.get("description")
            if not isinstance(description, str) or not description.strip():
                invalid.append(f"{skill_name}: description must be non-empty")
        if invalid:
            return "FAIL", "; ".join(invalid)
        return "PASS", f"validated {len(CODEX_SKILL_NAMES)} manifest-discovered Codex skills"

    def check_codex_dispatcher(self):
        relative = "codex/dispatcher/README.md"
        path = self.plugin_root / relative
        if not path.is_file():
            return "FAIL", f"missing: {relative}"
        content = path.read_text(encoding="utf-8")
        missing = [text for text in CODEX_DISPATCHER_REQUIRED_TEXT if text not in content]
        if missing:
            return "FAIL", "missing adapter boundary: " + ", ".join(missing)
        return "PASS", "Codex dispatcher delegates the sole shared Manifest DAG"

    def _codex_skills_root(self, codex_manifest):
        relative = codex_manifest.get("skills")
        if relative != CODEX_SKILLS_PATH:
            raise DoctorError(f"Codex skills must be {CODEX_SKILLS_PATH}")
        root = (self.plugin_root / relative).resolve()
        try:
            root.relative_to(self.plugin_root)
        except ValueError as exc:
            raise DoctorError("Codex skills path escapes plugin root") from exc
        if not root.is_dir():
            raise DoctorError(f"Codex skills directory missing: {relative}")
        return root

    def _read_frontmatter(self, path):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            raise DoctorError(f"skill frontmatter missing: {path}")
        try:
            end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
        except StopIteration as exc:
            raise DoctorError(f"skill frontmatter not closed: {path}") from exc
        values = {}
        for line in lines[1:end]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip("'\"")
        return values

    def check_forbidden_manifest_command(self):
        path = self.plugin_root / FORBIDDEN_COMMAND_FILE
        if path.exists():
            return "FAIL", f"forbidden file exists: {FORBIDDEN_COMMAND_FILE}"
        return "PASS", "commands/spl/manifest.md is absent"

    def check_release_filter(self):
        release_files = set(self.packager._build_release_file_list())
        missing = sorted(INSTALL_RUNTIME_REQUIRED_FILES.difference(release_files))
        if missing:
            return "FAIL", "missing required release files: " + ", ".join(missing)
        forbidden = sorted(INSTALL_RUNTIME_FORBIDDEN_FILES.intersection(release_files))
        if forbidden:
            return "FAIL", "release files unexpectedly include: " + ", ".join(forbidden)
        for relative in REQUIRED_RELEASE_EXCLUDE:
            if not self.packager._should_skip_release_path(relative) or relative in release_files:
                return "FAIL", f"release filter unexpectedly keeps: {relative}"
        self.packager._scan_secrets(release_files)
        return "PASS", "install release filter keeps runtime closure, excludes blocked paths, and scans secrets"

    def check_session_contract(self):
        if not self.session_id:
            return "SKIPPED", "session_id not provided"
        command = [
            sys.executable,
            str(self.plugin_root / "scripts" / "validate_miao_contracts.py"),
            "--workspace-root",
            str(self.workspace_root),
            "--session-id",
            self.session_id,
            "--scope",
            "all",
        ]
        completed = self._run_command(command)
        if completed.returncode != 0:
            return "FAIL", completed.stderr or completed.stdout or "session contract validation failed"
        return "PASS", f"validated session {self.session_id}"

    def _run_command(self, command):
        return subprocess.run(
            command,
            cwd=self.plugin_root,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def _single_line(self, message):
        return " ".join(str(message).split()) if message else "ok"

    def _print_line(self, text):
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace") + "\n")
        sys.stdout.flush()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run SUPERLOOPER doctor checks.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--plugin-root", default=os.getenv("SUPERLOOPER_PLUGIN_ROOT"), help="插件源码或安装根目录，默认使用当前脚本所在插件根。")
    parser.add_argument("--session-id", help="执行会话 ID。")
    parser.add_argument("--platform", choices=("claude", "codex"), default="claude", help="运行 doctor 的平台。")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        runner = DoctorRunner(
            workspace_root=args.workspace_root,
            session_id=args.session_id,
            plugin_root=args.plugin_root,
            platform=args.platform,
        )
        return runner.run()
    except (DoctorError, PackageError, ValueError) as exc:
        print(f"doctor failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
