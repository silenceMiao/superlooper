import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

try:
    from package_plugin import INSTALL_RUNTIME_REQUIRED_FILES
    from render_user_readme import UserReadmeError, extract_public_readme
except ModuleNotFoundError:
    from scripts.package_plugin import INSTALL_RUNTIME_REQUIRED_FILES
    from scripts.render_user_readme import UserReadmeError, extract_public_readme


LEDGER_FILE = ".superlooper-marketplace-sync.json"
LEDGER_KEYS = {"schema_version", "plugin_name", "plugin_version", "source_commit", "managed_paths"}
REGISTRY_PATHS = (
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
)
CONTROLLED_ANCESTORS = {
    ".claude-plugin",
    ".agents",
    ".agents/plugins",
    "plugins",
    "plugins/superlooper",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass
class VerificationResult:
    ok: bool
    errors: list[str]


def verify_release_consistency(
    source_root,
    marketplace_root,
    *,
    require_pushed=False,
    source_branch="main",
    marketplace_branch="main",
    git_runner=None,
):
    source_root = _absolute_path(source_root)
    marketplace_root = _absolute_path(marketplace_root)
    errors = []
    ledger = None
    try:
        source_version = _validate_source(source_root, errors)
        release_files = _validate_install_manifest(source_root, errors)
        ledger = _validate_marketplace(source_root, marketplace_root, release_files, source_version, errors)
    except Exception as exc:
        errors.append(f"本地发布一致性检查异常: {exc}")

    if require_pushed:
        try:
            _validate_pushed_state(
                source_root,
                marketplace_root,
                ledger,
                source_branch,
                marketplace_branch,
                git_runner or _default_git_runner,
                errors,
            )
        except Exception as exc:
            errors.append(f"Git 发布状态检查异常: {exc}")
    return VerificationResult(ok=not errors, errors=errors)


def _absolute_path(value):
    return Path(os.path.abspath(os.fspath(value)))


def _validate_source(source_root, errors):
    if source_root.is_symlink() or not source_root.is_dir():
        errors.append("源码根目录不存在或为符号链接")
        return None
    claude_manifest = _read_json(source_root / ".claude-plugin" / "plugin.json", errors)
    codex_manifest = _read_json(source_root / ".codex-plugin" / "plugin.json", errors)
    if claude_manifest is None or codex_manifest is None:
        return None
    _validate_manifest_identity(claude_manifest, "源码 Claude manifest", errors)
    _validate_manifest_identity(codex_manifest, "源码 Codex manifest", errors)
    _require_matching_manifest_fields(claude_manifest, codex_manifest, "源码", errors)
    _validate_source_readme(source_root, errors)
    return claude_manifest.get("version")


def _validate_manifest_identity(manifest, label, errors):
    if not isinstance(manifest, dict):
        errors.append(f"{label} 无效")
        return
    if manifest.get("name") != "superlooper":
        errors.append(f"{label} name 无效")
    for field in ("version", "license"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            errors.append(f"{label} {field} 无效")


def _validate_source_readme(source_root, errors):
    source_readme = source_root / "README.md"
    if source_readme.is_symlink() or not source_readme.is_file():
        errors.append("源码 README 缺失或为符号链接")
        return
    try:
        expected = extract_public_readme(source_root / "docs" / "USER_GUIDE.md", "source")
        if source_readme.read_text(encoding="utf-8") != expected:
            errors.append("源码 README 未由用户指南生成")
    except (OSError, UserReadmeError) as exc:
        errors.append(f"源码 README 无法验证: {exc}")


def _require_matching_manifest_fields(claude_manifest, codex_manifest, label, errors):
    if not isinstance(claude_manifest, dict) or not isinstance(codex_manifest, dict):
        return
    for field in ("name", "version", "license"):
        if claude_manifest.get(field) != codex_manifest.get(field):
            errors.append(f"{label} Claude/Codex manifest {field} 不一致")


def _validate_install_manifest(source_root, errors):
    manifest = _read_json(source_root / "dist" / "superlooper-release-manifest.json", errors)
    if not isinstance(manifest, dict):
        return []
    if manifest.get("plugin_name") != "superlooper":
        errors.append("install 发布清单 plugin_name 无效")
    if manifest.get("release_mode") != "install":
        errors.append("install 发布清单不存在或不是 install 模式")
    release_files = manifest.get("release_files")
    if not isinstance(release_files, list) or not all(isinstance(path, str) for path in release_files):
        errors.append("install 发布清单 release_files 无效")
        return []
    if len(release_files) != len(set(release_files)):
        errors.append("install 发布清单包含重复文件")
    if any(not _is_source_relative_file(path) for path in release_files):
        errors.append("install 发布清单包含无效路径")
        return release_files
    actual_files = _build_install_closure(source_root, errors)
    if set(release_files) != actual_files:
        errors.append("install 发布清单与当前安装闭包不一致")
    for relative_path in release_files:
        path = source_root / relative_path
        if path.is_symlink() or not path.is_file():
            errors.append(f"install 发布清单文件缺失或为符号链接: {relative_path}")
    return release_files


def _build_install_closure(source_root, errors):
    closure = set()
    if not source_root.is_dir():
        return closure
    for relative_path in sorted(INSTALL_RUNTIME_REQUIRED_FILES):
        path = source_root / relative_path
        if path.is_symlink() or not path.is_file():
            errors.append(f"install 安装闭包缺少必需文件: {relative_path}")
            continue
        closure.add(relative_path)
    for path in source_root.rglob("*"):
        if path.is_symlink():
            errors.append(f"源码安装闭包包含符号链接: {path.relative_to(source_root).as_posix()}")
    return closure


def _is_source_relative_file(relative_path):
    path = PurePosixPath(relative_path)
    return (
        bool(relative_path)
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in relative_path
        and str(path) == relative_path
    )


def _validate_marketplace(source_root, marketplace_root, release_files, source_version, errors):
    if marketplace_root.is_symlink() or not marketplace_root.is_dir():
        errors.append("Marketplace 根目录不存在或为符号链接")
        return None
    expected_paths = {f"plugins/superlooper/{relative_path}" for relative_path in release_files}
    _validate_controlled_path_links(marketplace_root, expected_paths, errors)
    ledger = _read_json(marketplace_root / LEDGER_FILE, errors, "同步账本")
    _validate_ledger(marketplace_root, ledger, expected_paths, errors)

    claude_metadata = _read_json(marketplace_root / REGISTRY_PATHS[0], errors, "Claude Marketplace metadata")
    codex_metadata = _read_json(marketplace_root / REGISTRY_PATHS[1], errors, "Codex Marketplace metadata")
    plugin_root = marketplace_root / "plugins" / "superlooper"
    plugin_manifest = _read_json(plugin_root / ".claude-plugin" / "plugin.json", errors)
    plugin_codex_manifest = _read_json(plugin_root / ".codex-plugin" / "plugin.json", errors)

    claude_entry = _metadata_entry(claude_metadata, "Claude", errors)
    codex_entry = _metadata_entry(codex_metadata, "Codex", errors)
    _validate_metadata_entry(claude_entry, "Claude Marketplace", errors)
    _validate_metadata_entry(codex_entry, "Codex Marketplace", errors)
    _validate_manifest_identity(plugin_manifest, "Marketplace Claude manifest", errors)
    _validate_manifest_identity(plugin_codex_manifest, "Marketplace Codex manifest", errors)
    _require_matching_manifest_fields(plugin_manifest, plugin_codex_manifest, "Marketplace", errors)
    _validate_manifest_against_source(plugin_manifest, source_version, "Marketplace Claude manifest", errors)
    _validate_manifest_against_source(plugin_codex_manifest, source_version, "Marketplace Codex manifest", errors)

    versions = {
        "源码": source_version,
        "Claude Marketplace": _entry_value(claude_entry, "version"),
        "Codex Marketplace": _entry_value(codex_entry, "version"),
        "Marketplace Claude manifest": _entry_value(plugin_manifest, "version"),
        "Marketplace Codex manifest": _entry_value(plugin_codex_manifest, "version"),
        "同步账本": _entry_value(ledger, "plugin_version"),
    }
    if len(set(versions.values())) != 1:
        errors.append("版本不一致: " + ", ".join(f"{label}={value}" for label, value in versions.items()))
    _validate_plugin_tree(source_root, plugin_root, release_files, errors)
    return ledger if isinstance(ledger, dict) else None


def _read_json(path, errors, label=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        errors.append(f"{label + ' ' if label else ''}缺少文件或为符号链接: {path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label + ' ' if label else ''}无效: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label + ' ' if label else ''}必须是 JSON 对象")
        return None
    return value


def _metadata_entry(metadata, label, errors):
    if not isinstance(metadata, dict):
        return None
    if metadata.get("name") != "superAI-marketplace":
        errors.append(f"{label} Marketplace metadata name 无效")
    plugins = metadata.get("plugins")
    if not isinstance(plugins, list):
        errors.append(f"{label} Marketplace metadata plugins 无效")
        return None
    entries = [entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == "superlooper"]
    if not entries:
        errors.append(f"{label} Marketplace metadata 缺少 superlooper 条目")
        return None
    if len(entries) > 1:
        errors.append(f"{label} Marketplace metadata 包含重复 superlooper 条目")
        return None
    return entries[0]


def _validate_metadata_entry(entry, label, errors):
    if not isinstance(entry, dict):
        return
    if entry.get("name") != "superlooper" or entry.get("source") != "./plugins/superlooper":
        errors.append(f"{label} metadata 插件引用无效")
    if not isinstance(entry.get("version"), str) or not entry["version"]:
        errors.append(f"{label} metadata version 无效")


def _validate_manifest_against_source(manifest, source_version, label, errors):
    if isinstance(manifest, dict) and source_version is not None and manifest.get("version") != source_version:
        errors.append(f"{label} version 与源码不一致")


def _entry_value(entry, key):
    return entry.get(key) if isinstance(entry, dict) else None


def _validate_controlled_path_links(marketplace_root, expected_paths, errors):
    paths = set(CONTROLLED_ANCESTORS) | {LEDGER_FILE, *REGISTRY_PATHS}
    for relative_path in expected_paths:
        path = PurePosixPath(relative_path)
        paths.update(parent.as_posix() for parent in path.parents if parent.as_posix() != ".")
        paths.add(relative_path)
    for relative_path in sorted(paths):
        if (marketplace_root / relative_path).is_symlink():
            errors.append(f"受控路径或祖先不能是符号链接: {relative_path}")


def _validate_ledger(marketplace_root, ledger, expected_paths, errors):
    if not isinstance(ledger, dict):
        return
    if set(ledger) != LEDGER_KEYS:
        errors.append("同步账本 schema 无效：只允许 schema_version/plugin_name/plugin_version/source_commit/managed_paths")
    schema_version = ledger.get("schema_version")
    if schema_version == 1:
        errors.append("同步账本为 v1；需要使用 --migrate-v1 迁移")
    elif schema_version != 2:
        errors.append("同步账本 schema_version 无效")
    if ledger.get("plugin_name") != "superlooper":
        errors.append("同步账本 plugin_name 无效")
    if not isinstance(ledger.get("plugin_version"), str) or not ledger.get("plugin_version"):
        errors.append("同步账本 plugin_version 无效")
    source_commit = ledger.get("source_commit")
    if source_commit is not None and (not isinstance(source_commit, str) or not COMMIT_PATTERN.fullmatch(source_commit)):
        errors.append("同步账本 source_commit 无效")
    managed_paths = ledger.get("managed_paths")
    if not isinstance(managed_paths, dict):
        errors.append("同步账本 managed_paths 无效")
        return
    if set(managed_paths) != expected_paths:
        errors.append("同步账本受控路径与发布闭包不一致")
    for relative_path, digest in managed_paths.items():
        if not _is_managed_path(relative_path) or not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            errors.append(f"同步账本路径或 SHA-256 无效: {relative_path}")
            continue
        path = marketplace_root / relative_path
        if path.is_symlink() or not path.is_file():
            errors.append(f"同步账本文件缺失或为符号链接: {relative_path}")
            continue
        try:
            if _sha256(path) != digest:
                errors.append(f"同步账本散列漂移: {relative_path}")
        except OSError as exc:
            errors.append(f"同步账本文件无法读取: {relative_path}: {exc}")


def _is_managed_path(relative_path):
    if not isinstance(relative_path, str):
        return False
    path = PurePosixPath(relative_path)
    return (
        bool(relative_path)
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in relative_path
        and str(path) == relative_path
        and relative_path.startswith("plugins/superlooper/")
    )


def _validate_plugin_tree(source_root, plugin_root, release_files, errors):
    if plugin_root.is_symlink() or not plugin_root.is_dir():
        errors.append("Marketplace 插件目录不存在或为符号链接")
        return
    expected_files = set(release_files)
    expected_directories = set()
    for relative_path in release_files:
        parent = PurePosixPath(relative_path).parent
        while parent.as_posix() != ".":
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    actual_files = set()
    actual_directories = set()
    for path in plugin_root.rglob("*"):
        relative_path = path.relative_to(plugin_root).as_posix()
        if path.is_symlink():
            errors.append(f"Marketplace 插件树包含符号链接: {relative_path}")
        elif path.is_file():
            actual_files.add(relative_path)
        elif path.is_dir():
            actual_directories.add(relative_path)
        else:
            errors.append(f"Marketplace 插件树包含无效路径: {relative_path}")
    if actual_files != expected_files:
        errors.append("Marketplace 插件文件集与 install 发布清单不一致")
    if actual_directories != expected_directories:
        errors.append("Marketplace 插件目录集与 install 发布清单不一致")
    for relative_path in expected_files.intersection(actual_files):
        source_path = source_root / relative_path
        plugin_path = plugin_root / relative_path
        try:
            if source_path.is_symlink() or source_path.read_bytes() != plugin_path.read_bytes():
                errors.append(f"Marketplace 插件文件内容不一致: {relative_path}")
        except OSError as exc:
            errors.append(f"Marketplace 插件文件无法比较: {relative_path}: {exc}")


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate_pushed_state(source_root, marketplace_root, ledger, source_branch, marketplace_branch, git_runner, errors):
    source_head = _validate_git_repository(source_root, source_branch, "源码", git_runner, errors)
    _validate_git_repository(marketplace_root, marketplace_branch, "Marketplace", git_runner, errors)
    if source_head is None:
        return
    if not isinstance(ledger, dict):
        errors.append("同步账本缺失或无效，无法校验 source_commit")
    elif ledger.get("source_commit") != source_head:
        errors.append("同步账本 source_commit 与源码 HEAD 不一致")


def _validate_git_repository(root, branch, label, git_runner, errors):
    status = _run_git(git_runner, root, ["status", "--porcelain"], label, errors)
    if status is None or status.returncode != 0:
        errors.append(f"{label}目录不是已绑定 origin 的 Git 工作树")
        return None
    if status.stdout.strip():
        errors.append(f"{label} Git 工作树不干净")
    current_branch = _run_git(git_runner, root, ["rev-parse", "--abbrev-ref", "HEAD"], label, errors)
    branch_ok = current_branch is not None and current_branch.returncode == 0 and current_branch.stdout.strip() == branch
    if not branch_ok:
        errors.append(f"{label} 当前分支不是 {branch}")
    head_result = _run_git(git_runner, root, ["rev-parse", "HEAD"], label, errors)
    head = head_result.stdout.strip() if head_result is not None and head_result.returncode == 0 else None
    if head is None or not COMMIT_PATTERN.fullmatch(head):
        errors.append(f"{label} HEAD 无效")
    origin = _run_git(git_runner, root, ["remote", "get-url", "origin"], label, errors)
    origin_ok = origin is not None and origin.returncode == 0 and bool(origin.stdout.strip())
    if not origin_ok:
        errors.append(f"{label} 缺少 origin")
    remote = _run_git(git_runner, root, ["ls-remote", "--heads", "origin", f"refs/heads/{branch}"], label, errors)
    remote_sha = remote.stdout.split()[0] if remote is not None and remote.returncode == 0 and remote.stdout.split() else None
    if head is not None and remote_sha != head:
        errors.append(f"{label} 远程 {branch} HEAD 与本地不一致")
    return head if branch_ok and origin_ok and COMMIT_PATTERN.fullmatch(head or "") else None


def _run_git(git_runner, root, args, label, errors):
    try:
        result = git_runner(Path(root), args)
        if isinstance(result, subprocess.CompletedProcess):
            return result
        return subprocess.CompletedProcess([], result[0], result[1], result[2])
    except (OSError, TypeError, ValueError, IndexError) as exc:
        errors.append(f"{label} Git 命令执行失败: {' '.join(args)}: {exc}")
        return None


def _default_git_runner(root, args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="验证 Superlooper 源码与 Marketplace 发布一致性。")
    parser.add_argument("--marketplace", required=True)
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--require-pushed", action="store_true")
    parser.add_argument("--source-branch", default="main")
    parser.add_argument("--marketplace-branch", default="main")
    return parser.parse_args(argv)


def main(argv=None):
    try:
        args = parse_args(argv)
        result = verify_release_consistency(
            args.root,
            args.marketplace,
            require_pushed=args.require_pushed,
            source_branch=args.source_branch,
            marketplace_branch=args.marketplace_branch,
        )
    except Exception as exc:
        print(f"release consistency: FAIL - 验证器异常: {exc}", file=sys.stderr)
        return 1
    if result.ok:
        print("release consistency: PASS")
        return 0
    for error in result.errors:
        print(f"release consistency: FAIL - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
