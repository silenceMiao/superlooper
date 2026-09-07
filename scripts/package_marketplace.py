import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

try:
    from package_plugin import PackageError, PluginPackager
    from render_user_readme import render_user_readme
except ModuleNotFoundError:
    from scripts.package_plugin import PackageError, PluginPackager
    from scripts.render_user_readme import render_user_readme


SYNC_LEDGER_NAME = ".superlooper-marketplace-sync.json"
SYNC_SCHEMA_VERSION = 1
MARKETPLACE_NAME = "superAI-marketplace"
PLUGIN_NAME = "superlooper"
SYNC_FIXED_FILES = frozenset(
    {
        "README.md",
        ".claude-plugin/marketplace.json",
        ".agents/plugins/marketplace.json",
    }
)
SYNC_REPLACED_PATHS = (
    "README.md",
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    "plugins/superlooper",
    SYNC_LEDGER_NAME,
)
CONTROLLED_METADATA_DIRECTORIES = {
    ".claude-plugin": "marketplace.json",
    ".agents/plugins": "marketplace.json",
}


class MarketplaceError(Exception):
    pass


def package_marketplace(root, target):
    source_root = Path(root).resolve()
    raw_target = Path(target)
    if raw_target.is_symlink():
        raise MarketplaceError("target 不能是符号链接")
    target_root = raw_target.resolve()
    _validate_target(source_root, target_root)

    staging_root, plugin_name, release_files = _build_marketplace_staging(source_root, target_root.parent)
    target_created = False
    try:
        _validate_marketplace_tree(source_root, staging_root / "plugins" / plugin_name, release_files)
        try:
            target_root.mkdir()
        except FileExistsError as exc:
            raise MarketplaceError("target 在发布期间已被创建") from exc
        target_created = True
        for path in staging_root.iterdir():
            path.rename(target_root / path.name)
        staging_root.rmdir()
        staging_root = None
        target_created = False
        return 0
    finally:
        if staging_root is not None:
            shutil.rmtree(staging_root, ignore_errors=True)
        if target_created:
            shutil.rmtree(target_root, ignore_errors=True)


def sync_marketplace(root, target, *, adopt_existing=False):
    source_root = Path(root).resolve()
    raw_target = Path(target)
    if raw_target.is_symlink():
        raise MarketplaceError("target 不能是符号链接")
    target_root = raw_target.resolve()
    _validate_sync_target(source_root, target_root)

    source_commit = _source_commit(source_root)
    staging_root, plugin_name, release_files = _build_marketplace_staging(source_root, target_root.parent)
    try:
        _add_sync_files(source_root, staging_root, plugin_name, source_commit)
        _validate_marketplace_tree(source_root, staging_root / "plugins" / plugin_name, release_files)
        _validate_existing_sync_target(target_root, staging_root, adopt_existing)
        _replace_controlled_paths(target_root, staging_root)
        staging_root = None
        return 0
    finally:
        if staging_root is not None:
            shutil.rmtree(staging_root, ignore_errors=True)


def _build_marketplace_staging(source_root, parent):
    packager = PluginPackager(root=source_root, mode="install")
    packager.run()
    manifest = json.loads(packager.manifest_path.read_text(encoding="utf-8"))
    if manifest.get("release_mode") != "install":
        raise MarketplaceError("发布清单不是 install 模式")
    plugin_manifest = json.loads((source_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    codex_plugin_manifest = json.loads((source_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    plugin_name = manifest["plugin_name"]
    release_files = manifest["release_files"]
    _validate_release_files(source_root, release_files)

    parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(dir=parent, prefix=".marketplace-staging."))
    try:
        plugin_root = staging_root / "plugins" / plugin_name
        for relative_path in release_files:
            source_path = source_root / relative_path
            destination_path = plugin_root / relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)

        marketplace_path = staging_root / ".claude-plugin" / "marketplace.json"
        marketplace_path.parent.mkdir(parents=True, exist_ok=True)
        marketplace_path.write_text(
            json.dumps(_marketplace_manifest(plugin_manifest, plugin_name), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        codex_marketplace_path = staging_root / ".agents" / "plugins" / "marketplace.json"
        codex_marketplace_path.parent.mkdir(parents=True, exist_ok=True)
        codex_marketplace_path.write_text(
            json.dumps(_codex_marketplace_manifest(codex_plugin_manifest, plugin_name), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return staging_root, plugin_name, release_files
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def _add_sync_files(source_root, staging_root, plugin_name, source_commit):
    plugin_manifest = json.loads((source_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    codex_plugin_manifest = json.loads((source_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if (
        plugin_name != PLUGIN_NAME
        or plugin_manifest.get("name") != PLUGIN_NAME
        or codex_plugin_manifest.get("name") != PLUGIN_NAME
        or plugin_manifest.get("version") != codex_plugin_manifest.get("version")
    ):
        raise MarketplaceError("同步要求双插件 manifest 名称为 superlooper 且版本一致")
    render_user_readme(source_root / "docs" / "USER_GUIDE.md", staging_root / "README.md", "marketplace")
    ledger = {
        "schema_version": SYNC_SCHEMA_VERSION,
        "plugin_name": plugin_name,
        "plugin_version": plugin_manifest["version"],
        "source_commit": source_commit,
        "managed_paths": _managed_file_hashes(staging_root),
    }
    (staging_root / SYNC_LEDGER_NAME).write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _source_commit(source_root):
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=source_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None
    if status.returncode != 0:
        return None
    if status.stdout:
        raise MarketplaceError("源码 Git 工作树不干净，拒绝同步")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        return None
    commit = completed.stdout.strip()
    return commit if len(commit) == 40 and all(character in "0123456789abcdef" for character in commit) else None


def _managed_file_hashes(root):
    return {
        relative_path: _sha256(root / relative_path)
        for relative_path in sorted(_controlled_file_paths(root))
    }


def _controlled_file_paths(root):
    files = set(SYNC_FIXED_FILES)
    plugin_root = root / "plugins" / PLUGIN_NAME
    if plugin_root.is_dir() and not plugin_root.is_symlink():
        for path in plugin_root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                files.add(_relative_path(root, path))
    return files


def _validate_existing_sync_target(target_root, staging_root, adopt_existing):
    _validate_controlled_path_links(target_root)
    _validate_controlled_metadata_trees(target_root)
    ledger_path = target_root / SYNC_LEDGER_NAME
    if ledger_path.exists():
        _validate_sync_ledger(target_root, ledger_path)
        return
    if _has_controlled_content(target_root):
        if not adopt_existing:
            raise MarketplaceError("目标存在未受管控内容；使用 --adopt-existing 后才能接管")
        _validate_adoption_target(target_root, staging_root)


def _validate_controlled_path_links(target_root):
    paths = (
        "README.md",
        ".claude-plugin",
        ".claude-plugin/marketplace.json",
        ".agents",
        ".agents/plugins",
        ".agents/plugins/marketplace.json",
        "plugins",
        "plugins/superlooper",
        SYNC_LEDGER_NAME,
    )
    for relative_path in paths:
        path = target_root / relative_path
        if path.is_symlink():
            raise MarketplaceError(f"受控路径不能是符号链接: {relative_path}")
    plugin_root = target_root / "plugins" / PLUGIN_NAME
    if plugin_root.exists():
        _validate_plugin_tree_links_and_directories(plugin_root)


def _validate_controlled_metadata_trees(target_root):
    for relative_directory, metadata_file in CONTROLLED_METADATA_DIRECTORIES.items():
        directory = target_root / relative_directory
        if not directory.exists() and not directory.is_symlink():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise MarketplaceError(f"受控 metadata 目录必须是普通目录: {relative_directory}")
        actual_files = set()
        for path in directory.rglob("*"):
            relative_path = _relative_path(directory, path)
            if path.is_symlink():
                raise MarketplaceError(f"受控 metadata 目录包含符号链接: {relative_directory}/{relative_path}")
            if path.is_file():
                actual_files.add(relative_path)
                if relative_path != metadata_file:
                    raise MarketplaceError(f"受控 metadata 目录包含未知路径: {relative_directory}/{relative_path}")
            else:
                raise MarketplaceError(f"受控 metadata 目录包含未知路径: {relative_directory}/{relative_path}")
        if actual_files != {metadata_file}:
            raise MarketplaceError(f"受控 metadata 目录文件集无效: {relative_directory}")


def _has_controlled_content(target_root):
    return any((target_root / relative_path).exists() or (target_root / relative_path).is_symlink() for relative_path in SYNC_REPLACED_PATHS)


def _validate_adoption_target(target_root, staging_root):
    plugin_root = target_root / "plugins" / PLUGIN_NAME
    expected_plugin_files = _plugin_file_paths(staging_root / "plugins" / PLUGIN_NAME)
    actual_plugin_files = _plugin_file_paths(plugin_root)
    if not actual_plugin_files.issubset(expected_plugin_files):
        raise MarketplaceError("接管目标的插件树包含额外文件")
    _validate_plugin_manifest_names(plugin_root)


def _validate_sync_ledger(target_root, ledger_path):
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarketplaceError("同步账本无效") from exc
    required_keys = {"schema_version", "plugin_name", "plugin_version", "source_commit", "managed_paths"}
    if set(ledger) != required_keys or ledger["schema_version"] != SYNC_SCHEMA_VERSION:
        raise MarketplaceError("同步账本 schema 无效")
    if ledger["plugin_name"] != PLUGIN_NAME:
        raise MarketplaceError("同步账本名称无效")
    if not isinstance(ledger["plugin_version"], str) or not ledger["plugin_version"]:
        raise MarketplaceError("同步账本版本无效")
    source_commit = ledger["source_commit"]
    if source_commit is not None and (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise MarketplaceError("同步账本 source_commit 无效")
    if not isinstance(ledger["managed_paths"], dict) or not ledger["managed_paths"]:
        raise MarketplaceError("同步账本受控路径无效")
    for relative_path, digest in ledger["managed_paths"].items():
        if not isinstance(relative_path, str) or not _is_allowed_ledger_path(relative_path):
            raise MarketplaceError(f"同步账本包含未允许路径: {relative_path}")
        if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise MarketplaceError(f"同步账本哈希无效: {relative_path}")

    _validate_controlled_path_links(target_root)
    _validate_controlled_metadata_trees(target_root)
    actual_files = _controlled_file_paths(target_root)
    if set(ledger["managed_paths"]) != actual_files:
        raise MarketplaceError("受控文件集与同步账本不一致")
    for relative_path, digest in ledger["managed_paths"].items():
        path = target_root / relative_path
        if not path.is_file() or path.is_symlink() or _sha256(path) != digest:
            raise MarketplaceError(f"受控文件已漂移: {relative_path}")
    _validate_plugin_manifest_names(target_root / "plugins" / PLUGIN_NAME, ledger["plugin_version"])
    _validate_marketplace_metadata(target_root, ledger["plugin_version"])


def _is_allowed_ledger_path(relative_path):
    path = PurePosixPath(relative_path)
    if path.is_absolute() or ".." in path.parts or str(path) != relative_path:
        return False
    return relative_path in SYNC_FIXED_FILES or relative_path.startswith("plugins/superlooper/")


def _validate_plugin_manifest_names(plugin_root, expected_version=None):
    try:
        claude_manifest = json.loads((plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        codex_manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarketplaceError("插件 manifest 无效") from exc
    if not isinstance(claude_manifest, dict) or not isinstance(codex_manifest, dict):
        raise MarketplaceError("插件 manifest 无效")
    if claude_manifest.get("name") != PLUGIN_NAME or codex_manifest.get("name") != PLUGIN_NAME:
        raise MarketplaceError("插件 manifest 名称必须为 superlooper")
    if claude_manifest.get("version") != codex_manifest.get("version"):
        raise MarketplaceError("双插件 manifest 版本不一致")
    if expected_version is not None and claude_manifest.get("version") != expected_version:
        raise MarketplaceError("插件 manifest 版本与同步账本不一致")


def _validate_marketplace_metadata(target_root, expected_version):
    try:
        claude_metadata = json.loads((target_root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        codex_metadata = json.loads((target_root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        claude_plugin = claude_metadata["plugins"][0]
        codex_plugin = codex_metadata["plugins"][0]
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise MarketplaceError("Marketplace metadata 无效") from exc
    if (
        claude_metadata.get("name") != MARKETPLACE_NAME
        or codex_metadata.get("name") != MARKETPLACE_NAME
        or not isinstance(claude_metadata.get("plugins"), list)
        or not isinstance(codex_metadata.get("plugins"), list)
        or len(claude_metadata["plugins"]) != 1
        or len(codex_metadata["plugins"]) != 1
        or not isinstance(claude_plugin, dict)
        or not isinstance(codex_plugin, dict)
        or claude_plugin.get("name") != PLUGIN_NAME
        or codex_plugin.get("name") != PLUGIN_NAME
        or claude_plugin.get("version") != expected_version
        or codex_plugin.get("version") != expected_version
        or claude_plugin.get("source") != "./plugins/superlooper"
        or codex_plugin.get("source") != "./plugins/superlooper"
    ):
        raise MarketplaceError("Marketplace metadata 名称、版本或 source 无效")


def _validate_plugin_tree_links_and_directories(plugin_root):
    if plugin_root.is_symlink() or not plugin_root.is_dir():
        raise MarketplaceError("插件树必须是普通目录")
    for path in plugin_root.rglob("*"):
        if path.is_symlink():
            raise MarketplaceError(f"插件树不能包含符号链接: {path}")
        if path.is_dir() and not any(path.iterdir()):
            raise MarketplaceError(f"插件树不能包含空目录: {path}")
        if not path.is_dir() and not path.is_file():
            raise MarketplaceError(f"插件树包含无效路径: {path}")


def _plugin_file_paths(plugin_root):
    if not plugin_root.is_dir() or plugin_root.is_symlink():
        raise MarketplaceError("插件树必须是普通目录")
    _validate_plugin_tree_links_and_directories(plugin_root)
    return {
        _relative_path(plugin_root, path)
        for path in plugin_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _replace_controlled_paths(target_root, staging_root):
    backup_root = Path(tempfile.mkdtemp(dir=target_root.parent, prefix=f".{target_root.name}.sync-backup."))
    moved_paths = []
    installed_paths = []
    created_directories = []
    try:
        for relative_path in SYNC_REPLACED_PATHS:
            destination = target_root / relative_path
            if destination.exists() or destination.is_symlink():
                backup = backup_root / relative_path
                backup.parent.mkdir(parents=True, exist_ok=True)
                destination.rename(backup)
                moved_paths.append(relative_path)
        for relative_path in SYNC_REPLACED_PATHS:
            source = staging_root / relative_path
            destination = target_root / relative_path
            missing_directories = []
            parent = destination.parent
            while parent != target_root and not parent.exists():
                missing_directories.append(parent)
                parent = parent.parent
            destination.parent.mkdir(parents=True, exist_ok=True)
            created_directories.extend(reversed(missing_directories))
            source.rename(destination)
            installed_paths.append(relative_path)
        _validate_sync_ledger(target_root, target_root / SYNC_LEDGER_NAME)
        shutil.rmtree(staging_root)
    except Exception:
        for relative_path in reversed(installed_paths):
            _remove_path(target_root / relative_path)
        for relative_path in reversed(moved_paths):
            backup = backup_root / relative_path
            destination = target_root / relative_path
            if backup.exists() or backup.is_symlink():
                destination.parent.mkdir(parents=True, exist_ok=True)
                backup.rename(destination)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)


def _remove_path(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(root, path):
    return str(path.relative_to(root)).replace("\\", "/")


def _validate_target(source_root, target_root):
    if target_root == source_root:
        raise MarketplaceError("target 不能等于插件源码目录")
    if source_root in target_root.parents:
        raise MarketplaceError("target 不能位于插件源码目录内")
    if target_root.exists():
        raise MarketplaceError("target 必须不存在")


def _validate_sync_target(source_root, target_root):
    if target_root == source_root:
        raise MarketplaceError("sync target 不能等于插件源码目录")
    if source_root in target_root.parents:
        raise MarketplaceError("sync target 不能位于插件源码目录内")
    if not target_root.is_dir():
        raise MarketplaceError("sync target 必须是已存在的目录")


def _validate_release_files(source_root, release_files):
    for relative_path in release_files:
        path = Path(relative_path)
        source_path = source_root / path
        if path.is_absolute() or ".." in path.parts or source_path.is_symlink() or not source_path.is_file():
            raise MarketplaceError(f"发布清单包含无效文件: {relative_path}")
        try:
            source_path.resolve().relative_to(source_root)
        except ValueError as exc:
            raise MarketplaceError(f"发布清单文件越出插件源码目录: {relative_path}") from exc


def _marketplace_manifest(plugin_manifest, plugin_name):
    plugin = {
        "name": plugin_manifest["name"],
        "displayName": plugin_manifest["displayName"],
        "description": plugin_manifest["description"],
        "version": plugin_manifest["version"],
        "author": plugin_manifest["author"],
        "source": f"./plugins/{plugin_name}",
    }
    return {
        "name": MARKETPLACE_NAME,
        "owner": {"name": plugin_manifest["author"]["name"]},
        "description": plugin_manifest["description"],
        "plugins": [plugin],
    }


def _codex_marketplace_manifest(plugin_manifest, plugin_name):
    return {
        "name": MARKETPLACE_NAME,
        "plugins": [
            {
                "name": plugin_name,
                "version": plugin_manifest["version"],
                "source": f"./plugins/{plugin_name}",
            }
        ],
    }


def _validate_marketplace_tree(source_root, plugin_root, release_files):
    expected = set(release_files)
    actual = {
        _relative_path(plugin_root, path)
        for path in plugin_root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise MarketplaceError("marketplace 文件集与发布清单不一致")
    for relative_path in release_files:
        if (source_root / relative_path).read_bytes() != (plugin_root / relative_path).read_bytes():
            raise MarketplaceError(f"marketplace 文件内容不一致: {relative_path}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument("--target")
    targets.add_argument("--sync-target")
    parser.add_argument("--adopt-existing", action="store_true")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    if args.adopt_existing and not args.sync_target:
        parser.error("--adopt-existing 只能与 --sync-target 一起使用")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.sync_target:
            return sync_marketplace(root=args.root, target=args.sync_target, adopt_existing=args.adopt_existing)
        return package_marketplace(root=args.root, target=args.target)
    except Exception as exc:
        print(f"package marketplace failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
