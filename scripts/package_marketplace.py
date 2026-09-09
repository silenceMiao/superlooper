import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

try:
    from package_plugin import PluginPackager
except ModuleNotFoundError:
    from scripts.package_plugin import PluginPackager


SYNC_LEDGER_NAME = ".superlooper-marketplace-sync.json"
V1_SYNC_SCHEMA_VERSION = 1
SYNC_SCHEMA_VERSION = 2
MARKETPLACE_NAME = "superAI-marketplace"
PLUGIN_NAME = "superlooper"
V1_FIXED_FILES = frozenset(
    {
        "README.md",
        ".claude-plugin/marketplace.json",
        ".agents/plugins/marketplace.json",
    }
)
REGISTRY_PATHS = (
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
)
SYNC_REPLACED_PATHS = (*REGISTRY_PATHS, "plugins/superlooper", SYNC_LEDGER_NAME)


class MarketplaceError(Exception):
    pass


def package_marketplace(root, target, marketplace_readme):
    source_root = Path(root).resolve()
    raw_target = Path(target)
    if raw_target.is_symlink():
        raise MarketplaceError("target 不能是符号链接")
    target_root = raw_target.resolve()
    _validate_target(source_root, target_root)
    overview = _read_marketplace_readme(marketplace_readme)

    staging_root, plugin_name, release_files, claude_entry, codex_entry = _build_marketplace_staging(
        source_root, target_root.parent
    )
    target_created = False
    try:
        _write_json(staging_root / REGISTRY_PATHS[0], _new_registry(claude_entry))
        _write_json(staging_root / REGISTRY_PATHS[1], _new_registry(codex_entry))
        (staging_root / "README.md").write_bytes(overview)
        _write_v2_ledger(staging_root, plugin_name, None)
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


def sync_marketplace(root, target, *, adopt_existing=False, migrate_v1=False):
    source_root = Path(root).resolve()
    raw_target = Path(target)
    if raw_target.is_symlink():
        raise MarketplaceError("target 不能是符号链接")
    target_root = raw_target.resolve()
    _validate_sync_target(source_root, target_root)
    if adopt_existing and migrate_v1:
        raise MarketplaceError("--adopt-existing 不能与 --migrate-v1 同时使用")

    source_commit = _source_commit(source_root)
    staging_root, plugin_name, release_files, claude_entry, codex_entry = _build_marketplace_staging(
        source_root, target_root.parent
    )
    try:
        state = _validate_existing_sync_target(target_root, adopt_existing, migrate_v1)
        _stage_registry_metadata(target_root, staging_root, claude_entry, codex_entry, state)
        _write_v2_ledger(staging_root, plugin_name, source_commit)
        _validate_marketplace_tree(source_root, staging_root / "plugins" / plugin_name, release_files)
        _replace_controlled_paths(target_root, staging_root)
        staging_root = None
        return 0
    finally:
        if staging_root is not None:
            shutil.rmtree(staging_root, ignore_errors=True)


def _read_marketplace_readme(path):
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise MarketplaceError("Marketplace README 必须是普通文件")
    try:
        content = source.read_bytes()
        content.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MarketplaceError("Marketplace README 必须是可读取的 UTF-8 文件") from exc
    return content


def _build_marketplace_staging(source_root, parent):
    packager = PluginPackager(root=source_root, mode="install")
    packager.run()
    manifest = _read_json_file(packager.manifest_path, "发布清单")
    if manifest.get("release_mode") != "install":
        raise MarketplaceError("发布清单不是 install 模式")
    plugin_manifest = _read_json_file(source_root / ".claude-plugin" / "plugin.json", "Claude 插件 manifest")
    codex_plugin_manifest = _read_json_file(source_root / ".codex-plugin" / "plugin.json", "Codex 插件 manifest")
    plugin_name = manifest.get("plugin_name")
    release_files = manifest.get("release_files")
    if not isinstance(release_files, list) or not all(isinstance(path, str) for path in release_files):
        raise MarketplaceError("发布清单 release_files 无效")
    if plugin_name != PLUGIN_NAME:
        raise MarketplaceError("发布清单插件名称必须为 superlooper")
    _validate_release_files(source_root, release_files)
    _validate_source_manifests(plugin_manifest, codex_plugin_manifest)

    parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(dir=parent, prefix=".marketplace-staging."))
    try:
        plugin_root = staging_root / "plugins" / plugin_name
        for relative_path in release_files:
            source_path = source_root / relative_path
            destination_path = plugin_root / relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
        return (
            staging_root,
            plugin_name,
            release_files,
            _marketplace_entry(plugin_manifest, plugin_name),
            _codex_marketplace_entry(codex_plugin_manifest, plugin_name),
        )
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def _validate_source_manifests(claude_manifest, codex_manifest):
    if (
        claude_manifest.get("name") != PLUGIN_NAME
        or codex_manifest.get("name") != PLUGIN_NAME
        or not isinstance(claude_manifest.get("version"), str)
        or not claude_manifest["version"]
        or claude_manifest.get("version") != codex_manifest.get("version")
    ):
        raise MarketplaceError("同步要求双插件 manifest 名称为 superlooper 且版本一致")


def _new_registry(entry):
    return {"name": MARKETPLACE_NAME, "plugins": [entry]}


def _stage_registry_metadata(target_root, staging_root, claude_entry, codex_entry, state):
    if state == "empty":
        claude_metadata = _new_registry(claude_entry)
        codex_metadata = _new_registry(codex_entry)
    else:
        claude_metadata = _read_registry_metadata(target_root / REGISTRY_PATHS[0], "Claude")
        codex_metadata = _read_registry_metadata(target_root / REGISTRY_PATHS[1], "Codex")
        _upsert_superlooper_entry(claude_metadata, claude_entry, "Claude")
        _upsert_superlooper_entry(codex_metadata, codex_entry, "Codex")
    _write_json(staging_root / REGISTRY_PATHS[0], claude_metadata)
    _write_json(staging_root / REGISTRY_PATHS[1], codex_metadata)


def _read_registry_metadata(path, platform):
    _validate_path_and_ancestors_not_symlink(path, path.parents)
    metadata = _read_json_file(path, f"{platform} Marketplace metadata")
    if metadata.get("name") != MARKETPLACE_NAME:
        raise MarketplaceError(f"{platform} Marketplace metadata name 无效")
    if not isinstance(metadata.get("plugins"), list):
        raise MarketplaceError(f"{platform} Marketplace metadata plugins 无效")
    return metadata


def _upsert_superlooper_entry(metadata, entry, platform):
    indices = [
        index
        for index, candidate in enumerate(metadata["plugins"])
        if isinstance(candidate, dict) and candidate.get("name") == PLUGIN_NAME
    ]
    if len(indices) > 1:
        raise MarketplaceError(f"{platform} Marketplace metadata 包含重复 superlooper 条目")
    if not indices:
        metadata["plugins"].append(entry)
        return
    index = indices[0]
    _validate_existing_superlooper_entry(metadata["plugins"][index], platform)
    metadata["plugins"][index] = entry


def _validate_existing_superlooper_entry(entry, platform):
    if (
        not isinstance(entry, dict)
        or entry.get("name") != PLUGIN_NAME
        or entry.get("source") != "./plugins/superlooper"
        or not isinstance(entry.get("version"), str)
        or not entry["version"]
    ):
        raise MarketplaceError(f"{platform} Marketplace metadata superlooper 条目无效")


def _validate_existing_sync_target(target_root, adopt_existing, migrate_v1):
    ledger_path = target_root / SYNC_LEDGER_NAME
    _validate_sync_paths_not_symlink(target_root)
    if ledger_path.exists():
        ledger = _read_json_file(ledger_path, "同步账本")
        schema_version = ledger.get("schema_version")
        if schema_version == V1_SYNC_SCHEMA_VERSION:
            if not migrate_v1:
                raise MarketplaceError("同步账本为 v1；使用 --migrate-v1 后才能迁移")
            _validate_v1_sync_ledger(target_root, ledger)
            return "v1"
        if schema_version == SYNC_SCHEMA_VERSION:
            if migrate_v1:
                raise MarketplaceError("--migrate-v1 仅适用于 v1 同步账本")
            _validate_v2_sync_ledger(target_root, ledger)
            _read_registry_metadata(target_root / REGISTRY_PATHS[0], "Claude")
            _read_registry_metadata(target_root / REGISTRY_PATHS[1], "Codex")
            return "v2"
        raise MarketplaceError("同步账本 schema 无效")
    if _has_sync_content(target_root):
        if not adopt_existing:
            raise MarketplaceError("目标存在未受管控内容；使用 --adopt-existing 后才能接管")
        _validate_adoption_target(target_root)
        return "adopt"
    if adopt_existing or migrate_v1:
        raise MarketplaceError("目标没有可接管或迁移的同步内容")
    return "empty"


def _validate_sync_paths_not_symlink(target_root):
    for relative_path in (*REGISTRY_PATHS, "plugins", "plugins/superlooper", SYNC_LEDGER_NAME):
        _validate_path_and_ancestors_not_symlink(target_root / relative_path, (target_root,))
    plugin_root = target_root / "plugins" / PLUGIN_NAME
    if plugin_root.exists():
        _validate_plugin_tree_links_and_directories(plugin_root)


def _validate_path_and_ancestors_not_symlink(path, stop_parents):
    stops = set(stop_parents)
    current = Path(path)
    while True:
        if current.is_symlink():
            raise MarketplaceError(f"受控路径或祖先不能是符号链接: {current}")
        if current in stops:
            return
        if current.parent == current:
            return
        current = current.parent


def _has_sync_content(target_root):
    return any(
        (target_root / relative_path).exists() or (target_root / relative_path).is_symlink()
        for relative_path in (*REGISTRY_PATHS, "plugins/superlooper")
    )


def _validate_adoption_target(target_root):
    plugin_root = target_root / "plugins" / PLUGIN_NAME
    _validate_plugin_manifest_names(plugin_root)
    _read_registry_metadata(target_root / REGISTRY_PATHS[0], "Claude")
    _read_registry_metadata(target_root / REGISTRY_PATHS[1], "Codex")


def _validate_v1_sync_ledger(target_root, ledger):
    _validate_ledger_header(ledger, V1_SYNC_SCHEMA_VERSION)
    managed_paths = ledger["managed_paths"]
    if not all(_is_v1_managed_path(path) for path in managed_paths):
        raise MarketplaceError("同步账本包含未允许路径")
    expected = _v1_controlled_file_paths(target_root)
    if set(managed_paths) != expected:
        raise MarketplaceError("受控文件集与同步账本不一致")
    _validate_ledger_hashes(target_root, managed_paths)
    _validate_plugin_manifest_names(target_root / "plugins" / PLUGIN_NAME, ledger["plugin_version"])
    claude = _read_registry_metadata(target_root / REGISTRY_PATHS[0], "Claude")
    codex = _read_registry_metadata(target_root / REGISTRY_PATHS[1], "Codex")
    if len(claude["plugins"]) != 1 or len(codex["plugins"]) != 1:
        raise MarketplaceError("v1 Marketplace metadata plugins 无效")
    for metadata, platform in ((claude, "Claude"), (codex, "Codex")):
        _validate_existing_superlooper_entry(metadata["plugins"][0], platform)
        if metadata["plugins"][0]["version"] != ledger["plugin_version"]:
            raise MarketplaceError("v1 Marketplace metadata 版本无效")


def _validate_v2_sync_ledger(target_root, ledger):
    _validate_ledger_header(ledger, SYNC_SCHEMA_VERSION)
    managed_paths = ledger["managed_paths"]
    if not all(_is_v2_managed_path(path) for path in managed_paths):
        raise MarketplaceError("同步账本包含未允许路径")
    expected = _v2_controlled_file_paths(target_root)
    if set(managed_paths) != expected:
        raise MarketplaceError("受控文件集与同步账本不一致")
    _validate_ledger_hashes(target_root, managed_paths)
    _validate_plugin_manifest_names(target_root / "plugins" / PLUGIN_NAME, ledger["plugin_version"])


def _validate_ledger_header(ledger, expected_schema):
    required_keys = {"schema_version", "plugin_name", "plugin_version", "source_commit", "managed_paths"}
    if set(ledger) != required_keys or ledger.get("schema_version") != expected_schema:
        raise MarketplaceError("同步账本 schema 无效")
    if ledger.get("plugin_name") != PLUGIN_NAME:
        raise MarketplaceError("同步账本名称无效")
    if not isinstance(ledger.get("plugin_version"), str) or not ledger["plugin_version"]:
        raise MarketplaceError("同步账本版本无效")
    source_commit = ledger.get("source_commit")
    if source_commit is not None and not _is_commit(source_commit):
        raise MarketplaceError("同步账本 source_commit 无效")
    if not isinstance(ledger.get("managed_paths"), dict) or not ledger["managed_paths"]:
        raise MarketplaceError("同步账本受控路径无效")


def _validate_ledger_hashes(target_root, managed_paths):
    for relative_path, digest in managed_paths.items():
        if not _is_sha256(digest):
            raise MarketplaceError(f"同步账本哈希无效: {relative_path}")
        path = target_root / relative_path
        if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
            raise MarketplaceError(f"受控文件已漂移: {relative_path}")


def _v1_controlled_file_paths(root):
    return set(V1_FIXED_FILES) | _v2_controlled_file_paths(root)


def _v2_controlled_file_paths(root):
    plugin_root = root / "plugins" / PLUGIN_NAME
    if not plugin_root.is_dir() or plugin_root.is_symlink():
        return set()
    return {
        _relative_path(root, path)
        for path in plugin_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _is_v1_managed_path(relative_path):
    return relative_path in V1_FIXED_FILES or _is_v2_managed_path(relative_path)


def _is_v2_managed_path(relative_path):
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


def _validate_plugin_manifest_names(plugin_root, expected_version=None):
    claude_manifest = _read_json_file(plugin_root / ".claude-plugin" / "plugin.json", "插件 Claude manifest")
    codex_manifest = _read_json_file(plugin_root / ".codex-plugin" / "plugin.json", "插件 Codex manifest")
    _validate_source_manifests(claude_manifest, codex_manifest)
    if expected_version is not None and claude_manifest.get("version") != expected_version:
        raise MarketplaceError("插件 manifest 版本与同步账本不一致")


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


def _write_v2_ledger(staging_root, plugin_name, source_commit):
    plugin_manifest = _read_json_file(staging_root / "plugins" / plugin_name / ".claude-plugin" / "plugin.json", "插件 manifest")
    ledger = {
        "schema_version": SYNC_SCHEMA_VERSION,
        "plugin_name": plugin_name,
        "plugin_version": plugin_manifest["version"],
        "source_commit": source_commit,
        "managed_paths": {
            relative_path: _sha256(staging_root / relative_path)
            for relative_path in sorted(_v2_controlled_file_paths(staging_root))
        },
    }
    _write_json(staging_root / SYNC_LEDGER_NAME, ledger)


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
        _validate_v2_sync_ledger(target_root, _read_json_file(target_root / SYNC_LEDGER_NAME, "同步账本"))
        _read_registry_metadata(target_root / REGISTRY_PATHS[0], "Claude")
        _read_registry_metadata(target_root / REGISTRY_PATHS[1], "Codex")
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
    commit = completed.stdout.strip()
    return commit if completed.returncode == 0 and _is_commit(commit) else None


def _remove_path(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _is_commit(value):
    return isinstance(value, str) and len(value) == 40 and all(character in "0123456789abcdef" for character in value)


def _relative_path(root, path):
    return str(Path(path).relative_to(root)).replace("\\", "/")


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
    if len(release_files) != len(set(release_files)):
        raise MarketplaceError("发布清单包含重复文件")
    for relative_path in release_files:
        path = PurePosixPath(relative_path)
        source_path = source_root / relative_path
        if (
            not relative_path
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in relative_path
            or source_path.is_symlink()
            or not source_path.is_file()
        ):
            raise MarketplaceError(f"发布清单包含无效文件: {relative_path}")


def _marketplace_entry(plugin_manifest, plugin_name):
    return {
        "name": plugin_manifest["name"],
        "displayName": plugin_manifest["displayName"],
        "description": plugin_manifest["description"],
        "version": plugin_manifest["version"],
        "author": plugin_manifest["author"],
        "source": f"./plugins/{plugin_name}",
    }


def _codex_marketplace_entry(plugin_manifest, plugin_name):
    return {
        "name": plugin_name,
        "version": plugin_manifest["version"],
        "source": f"./plugins/{plugin_name}",
    }


def _validate_marketplace_tree(source_root, plugin_root, release_files):
    expected = set(release_files)
    actual = {
        _relative_path(plugin_root, path)
        for path in plugin_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    if actual != expected:
        raise MarketplaceError("marketplace 文件集与发布清单不一致")
    for relative_path in release_files:
        if (source_root / relative_path).read_bytes() != (plugin_root / relative_path).read_bytes():
            raise MarketplaceError(f"marketplace 文件内容不一致: {relative_path}")


def _read_json_file(path, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise MarketplaceError(f"{label} 缺少文件或为符号链接")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarketplaceError(f"{label} 无效") from exc
    if not isinstance(value, dict):
        raise MarketplaceError(f"{label} 必须是 JSON 对象")
    return value


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument("--target")
    targets.add_argument("--sync-target")
    parser.add_argument("--marketplace-readme")
    parser.add_argument("--adopt-existing", action="store_true")
    parser.add_argument("--migrate-v1", action="store_true")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    if bool(args.target) != bool(args.marketplace_readme):
        parser.error("--marketplace-readme 必须且只能与 --target 一起使用")
    if args.adopt_existing and not args.sync_target:
        parser.error("--adopt-existing 只能与 --sync-target 一起使用")
    if args.migrate_v1 and not args.sync_target:
        parser.error("--migrate-v1 只能与 --sync-target 一起使用")
    if args.adopt_existing and args.migrate_v1:
        parser.error("--adopt-existing 不能与 --migrate-v1 同时使用")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.sync_target:
            return sync_marketplace(
                root=args.root,
                target=args.sync_target,
                adopt_existing=args.adopt_existing,
                migrate_v1=args.migrate_v1,
            )
        return package_marketplace(
            root=args.root,
            target=args.target,
            marketplace_readme=args.marketplace_readme,
        )
    except Exception as exc:
        print(f"package marketplace failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
