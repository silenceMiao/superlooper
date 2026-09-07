import argparse
import sys
import tempfile
from pathlib import Path


START_MARKER = "<!-- public-readme:start -->"
END_MARKER = "<!-- public-readme:end -->"
AUDIENCE_REPLACEMENTS = {
    "source": {
        "{{USER_GUIDE_LINK}}": "docs/USER_GUIDE.md",
        "{{SOURCE_MAINTENANCE_LINKS}}": "想维护插件源码、发布版本或修改协议：阅读 [开发说明](docs/DEVELOPMENT.md) 与 [发布指南](docs/RELEASE.md)。",
    },
    "marketplace": {
        "{{USER_GUIDE_LINK}}": "plugins/superlooper/docs/USER_GUIDE.md",
        "{{SOURCE_MAINTENANCE_LINKS}}": "",
    },
}


class UserReadmeError(Exception):
    pass


def extract_public_readme(source_path, audience):
    if audience not in AUDIENCE_REPLACEMENTS:
        raise UserReadmeError(f"未知 README 受众: {audience}")

    content = Path(source_path).read_text(encoding="utf-8")
    if content.count(START_MARKER) != 1 or content.count(END_MARKER) != 1:
        raise UserReadmeError("用户指南必须各包含一个 README 开始和结束标记")

    start = content.index(START_MARKER) + len(START_MARKER)
    end = content.index(END_MARKER)
    if start > end:
        raise UserReadmeError("README 标记顺序无效")

    rendered = content[start:end].strip()
    if not rendered:
        raise UserReadmeError("README 公开区段不能为空")

    for placeholder, replacement in AUDIENCE_REPLACEMENTS[audience].items():
        if replacement:
            rendered = rendered.replace(placeholder, replacement)
        else:
            rendered = rendered.replace(f"> {placeholder}", "")
            rendered = rendered.replace(placeholder, "")
    if "{{" in rendered or "}}" in rendered:
        raise UserReadmeError("README 公开区段包含未知占位符")
    return rendered + "\n"


def render_user_readme(source_path, destination_path, audience="source"):
    destination = Path(destination_path)
    rendered = extract_public_readme(source_path, audience)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as temporary:
        temporary.write(rendered)
        temporary_path = Path(temporary.name)
    temporary_path.replace(destination)


def assert_user_readme_current(source_path, destination_path, audience):
    destination = Path(destination_path)
    if not destination.is_file():
        raise UserReadmeError(f"README 不存在: {destination}")
    expected = extract_public_readme(source_path, audience)
    actual = destination.read_text(encoding="utf-8")
    if actual != expected:
        raise UserReadmeError(f"README 未由用户指南生成: {destination}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="从用户指南生成公开 README。")
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--audience", choices=sorted(AUDIENCE_REPLACEMENTS), default="source")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.check:
            assert_user_readme_current(args.source, args.destination, args.audience)
        else:
            render_user_readme(args.source, args.destination, args.audience)
        return 0
    except (OSError, UserReadmeError) as exc:
        print(f"render README failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
