import argparse
import json
import sys
import zipfile
from pathlib import Path

from package_plugin import PackageError, PluginPackager


SUPPORTED_MODES = {"source", "install"}


class ArchiveBuildError(Exception):
    pass


class ReleaseArchiveBuilder:
    def __init__(self, root=None, mode="source"):
        self.packager = PluginPackager(root=root, mode=mode)

    def run(self):
        self.packager.run()
        manifest = json.loads(self.packager.manifest_path.read_text(encoding="utf-8"))
        version = self._read_version()
        archive_path = self.packager.dist_dir / f"superlooper-{version}-{self.packager.mode}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative_path in manifest["release_files"]:
                archive.write(self.packager.root / relative_path, arcname=relative_path)
        with zipfile.ZipFile(archive_path) as archive:
            archive_names = sorted(archive.namelist())
        expected_names = sorted(manifest["release_files"])
        if archive_names != expected_names:
            raise ArchiveBuildError("release archive contents do not match release manifest.")
        print(f"release archive written: {archive_path}")
        return 0

    def _read_version(self):
        plugin_manifest_path = self.packager.root / ".claude-plugin" / "plugin.json"
        plugin_manifest = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))
        version = plugin_manifest.get("version")
        if not version:
            raise ArchiveBuildError("plugin version 缺失。")
        return version


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="source")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        builder = ReleaseArchiveBuilder(mode=args.mode)
        return builder.run()
    except (ArchiveBuildError, PackageError, ValueError) as exc:
        print(f"build release archive failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
