import hashlib
import json
import stat
from pathlib import Path


def _file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_tree_digest(root):
    root = Path(root)
    entries = []
    files = []
    for path in root.rglob("*"):
        if stat.S_ISREG(path.lstat().st_mode):
            files.append((path.relative_to(root).as_posix(), path))
    for relative, path in sorted(files, key=lambda item: item[0]):
        entries.append({"path": relative, "sha256": _file_sha256(path)})
    payload = json.dumps(
        entries,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()
