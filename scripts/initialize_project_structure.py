import argparse
import json
import os
import sys
from pathlib import Path

from create_session import load_state_from_path, resolve_workspace_root, state_file_path, validate_session_id, validate_session_state, write_state


PROJECT_VERSIONS = {
    "java": ["jdk-8", "jdk-11", "jdk-17"],
    "go": ["go-1.25"],
    "springboot": ["springboot-2.x", "springboot-3.x"],
    "pom": ["maven-3.5.x", "maven-3.9.x"],
    "lua": ["lua-4.x", "lua-5.x"],
}
PROTECTED_ROOTS = {".git", ".hg", ".svn", ".claude", ".superlooper", ".env"}


class InitializationError(Exception):
    pass


SPRINGBOOT_3_POM = """<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.0</version>
    <relativePath/>
  </parent>
  <groupId>com.example</groupId>
  <artifactId>superlooper-app</artifactId>
  <version>0.0.1-SNAPSHOT</version>
  <properties>
    <java.version>17</java.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
"""

SPRINGBOOT_2_POM = SPRINGBOOT_3_POM.replace("<version>3.3.0</version>", "<version>2.7.18</version>").replace("<java.version>17</java.version>", "<java.version>8</java.version>")
MAVEN_POM = """<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>superlooper-app</artifactId>
  <version>1.0.0</version>
</project>
"""
PROJECT_CLAUDE = """# Project CLAUDE.md

本文件由 Superlooper 项目结构初始化生成，用于记录目标项目级协作说明。

## 约束

- 业务代码必须落在当前项目源码目录内。
- 禁止硬编码密码、密钥、令牌和连接串。
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Initialize SUPERLOOPER target project structure.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    parser.add_argument("--project-category", required=True, choices=sorted(PROJECT_VERSIONS), help="初始化项目分类。")
    parser.add_argument("--project-version", required=True, help="初始化项目版本。")
    parser.add_argument("--project-root", required=True, help="workspace_root 内的项目根目录相对路径。")
    return parser.parse_args()


def resolve_project_root(workspace_root, value):
    raw = Path(value)
    if raw.is_absolute() or raw.drive or ".." in raw.parts:
        raise InitializationError("project_root 必须是 workspace_root 内的安全相对路径。")
    parts = [part for part in raw.parts if part not in ("", ".")]
    if parts and parts[0] in PROTECTED_ROOTS:
        raise InitializationError("project_root 不能指向保护目录。")
    project_root = (workspace_root / raw).resolve()
    try:
        project_root.relative_to(workspace_root)
    except ValueError as exc:
        raise InitializationError("project_root 必须位于 workspace_root 内。") from exc
    return project_root


def validate_version(project_category, project_version):
    allowed = PROJECT_VERSIONS[project_category]
    if project_version not in allowed:
        raise InitializationError(f"project_version 不属于 {project_category} 的允许版本：{project_version}")


def write_file_deny_conflict(path, content, conflicts):
    if path.exists() and path.read_text(encoding="utf-8") != content:
        conflicts.append(str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)


def structure_for(category, version):
    if category == "springboot":
        pom = SPRINGBOOT_3_POM if version == "springboot-3.x" else SPRINGBOOT_2_POM
        return ["src/main/java", "src/main/resources", "src/test/java", "target"], {"CLAUDE.md": PROJECT_CLAUDE, "pom.xml": pom}
    if category == "pom":
        return ["src/main/java", "src/main/resources", "src/test/java", "target"], {"pom.xml": MAVEN_POM}
    if category == "java":
        return ["src/main/java", "src/test/java"], {}
    if category == "go":
        return ["cmd", "internal", "pkg"], {}
    if category == "lua":
        return ["src", "tests"], {}
    raise InitializationError(f"project_category 不合法：{category}")


def write_report(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_state(workspace_root, session_id, args, report_path):
    path = state_file_path(workspace_root, session_id)
    state = load_state_from_path(path)
    state["current_phase"] = "initialization"
    state["phase_status"] = "passed"
    state["project_category"] = args.project_category
    state["project_version"] = args.project_version
    state["project_root"] = args.project_root
    state["project_initialized"] = True
    state["initialization_report"] = f".superlooper/reports/{session_id}/initialization_report.json"
    state["next_actions"] = ["生成 module-split.json"]
    write_state(path, validate_session_state(state))
    return report_path


def run(args):
    session_id = validate_session_id(args.session_id)
    workspace_root = resolve_workspace_root(args.workspace_root)
    validate_version(args.project_category, args.project_version)
    project_root = resolve_project_root(workspace_root, args.project_root)
    dirs, files = structure_for(args.project_category, args.project_version)
    reports_dir = workspace_root / ".superlooper" / "reports" / session_id
    conflicts = []
    for directory in dirs:
        ensure_dir(project_root / directory)
    for relative, content in files.items():
        write_file_deny_conflict(project_root / relative, content, conflicts)
    if conflicts:
        write_report(
            reports_dir / "initialization_conflict_report.json",
            {
                "session_id": session_id,
                "status": "conflict",
                "project_category": args.project_category,
                "project_version": args.project_version,
                "project_root": args.project_root,
                "conflicts": conflicts,
            },
        )
        return 2
    created_paths = [*dirs, *files.keys()]
    report_path = reports_dir / "initialization_report.json"
    write_report(
        report_path,
        {
            "session_id": session_id,
            "status": "success",
            "project_category": args.project_category,
            "project_version": args.project_version,
            "project_root": args.project_root,
            "created_paths": created_paths,
        },
    )
    update_state(workspace_root, session_id, args, report_path)
    print(f".superlooper/reports/{session_id}/initialization_report.json")
    return 0


def main():
    args = parse_args()
    try:
        return run(args)
    except InitializationError as exc:
        print(f"初始化项目结构失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
