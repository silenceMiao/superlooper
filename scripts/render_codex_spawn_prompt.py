import argparse
import json
import os
import re
import sys
from pathlib import Path

from create_session import SessionStateValidationError, resolve_explicit_task_id
from validate_miao_contracts import ContractError, ContractValidator


MODULE_NODE_PATTERN = re.compile(r"^mod_[a-z][a-z0-9_]*$")
DESIGN_FILENAMES = [
    "architecture.md",
    "tech-stack.md",
    "project-profile.md",
    "initialization-advice.md",
]


class CodexPromptRenderError(Exception):
    pass


class CodexSpawnPromptRenderer:
    def __init__(self, workspace_root, task_id, node_id):
        self.root = Path(workspace_root).resolve()
        self.task_id = task_id
        if not isinstance(node_id, str) or not MODULE_NODE_PATTERN.match(node_id):
            raise CodexPromptRenderError(
                "node_id 必须是合法的 mod_* 模块节点。"
            )
        self.node_id = node_id
        self.module_id = node_id.removeprefix("mod_")
        self.manifest_path = (
            self.root
            / ".superlooper"
            / "manifests"
            / self.task_id
            / "execution_manifest.json"
        )

    def run(self):
        validator = ContractValidator(self.root, self.task_id)
        validator.validate("execution")
        manifest = self._read_json(self.manifest_path, "Execution Manifest")
        if manifest.get("context", {}).get("platform_registration") != {
            "platform": "codex"
        }:
            raise CodexPromptRenderError(
                "Execution Manifest 必须声明 Codex platform_registration。"
            )
        node = self._current_node(manifest)
        module = self._current_module(manifest)
        runtime_content = self._runtime_agent_content(manifest, node)
        design_paths = self._design_paths(manifest)
        prompt = self._render_prompt(
            runtime_content,
            node,
            module,
            design_paths,
        )
        sys.stdout.write(prompt)
        return 0

    def _read_json(self, path, label):
        resolved = path.resolve()
        self._require_contained(resolved, self.root, label)
        if not resolved.is_file():
            raise CodexPromptRenderError(f"{label} 不存在：{resolved}")
        try:
            data = json.loads(resolved.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CodexPromptRenderError(f"{label} JSON 解析失败：{exc}") from exc
        if not isinstance(data, dict):
            raise CodexPromptRenderError(f"{label} 顶层必须是 object。")
        return data

    def _current_node(self, manifest):
        nodes = manifest.get("dag", {}).get("nodes", [])
        matches = [
            node
            for node in nodes
            if isinstance(node, dict) and node.get("id") == self.node_id
        ]
        if len(matches) != 1:
            raise CodexPromptRenderError(
                f"Execution Manifest 必须且只能包含一个节点：{self.node_id}"
            )
        node = matches[0]
        expected_agent = f"module_{self.module_id}"
        if node.get("agent") != expected_agent:
            raise CodexPromptRenderError(
                f"{self.node_id}.agent 必须为 {expected_agent}。"
            )
        return node

    def _current_module(self, manifest):
        relative = manifest.get("context", {}).get("module_split_path")
        module_split_path = self._workspace_path(relative, "module_split_path")
        module_split = self._read_json(module_split_path, "module-split")
        modules = module_split.get("modules")
        matches = [
            module
            for module in modules
            if isinstance(module, dict) and module.get("id") == self.module_id
        ] if isinstance(modules, list) else []
        if len(matches) != 1:
            raise CodexPromptRenderError(
                f"module-split 必须且只能包含一个模块：{self.module_id}"
            )
        return matches[0]

    def _runtime_agent_content(self, manifest, node):
        relative = manifest.get("context", {}).get("runtime_agents_path")
        runtime_root = self._workspace_path(relative, "runtime_agents_path").resolve()
        self._require_contained(runtime_root, self.root, "runtime_agents_path")
        runtime_path = (
            runtime_root / f"{node['agent']}.md"
        ).resolve()
        self._require_contained(
            runtime_path,
            runtime_root,
            "runtime Agent 文件",
        )
        if not runtime_path.is_file():
            raise CodexPromptRenderError(
                f"runtime Agent 文件不存在：{runtime_path}"
            )
        content = runtime_path.read_text(encoding="utf-8")
        name = self._frontmatter_name(content)
        if name != node["agent"]:
            raise CodexPromptRenderError(
                f"runtime Agent frontmatter name 必须为 {node['agent']}。"
            )
        if "## Runtime Module Constraints" not in content:
            raise CodexPromptRenderError(
                "runtime Agent 缺少 Runtime Module Constraints。"
            )
        return content

    def _design_paths(self, manifest):
        relative = manifest.get("context", {}).get("design_docs_path")
        design_root = self._workspace_path(relative, "design_docs_path").resolve()
        self._require_contained(design_root, self.root, "design_docs_path")
        paths = []
        for filename in DESIGN_FILENAMES:
            path = (design_root / filename).resolve()
            self._require_contained(path, design_root, f"design path {filename}")
            if not path.is_file():
                raise CodexPromptRenderError(
                    f"允许的设计文档不存在：{path}"
                )
            paths.append(self._contract_path(path))
        return paths

    def _workspace_path(self, relative, label):
        if not isinstance(relative, str) or not relative.strip():
            raise CodexPromptRenderError(f"{label} 必须是非空字符串。")
        path = Path(relative)
        if path.is_absolute() or path.drive or ":" in relative:
            raise CodexPromptRenderError(f"{label} 必须是 workspace 相对路径。")
        resolved = (self.root / path).resolve()
        self._require_contained(resolved, self.root, label)
        return resolved

    def _require_contained(self, path, root, label):
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise CodexPromptRenderError(
                f"{label} 必须位于授权根目录内：{path}"
            ) from exc

    def _frontmatter_name(self, content):
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            return None
        for line in lines[1:]:
            if line.strip() == "---":
                return None
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip().strip("'\"")
        return None

    def _render_prompt(self, runtime_content, node, module, design_paths):
        payload = node["payload"]
        output_contract = {
            "output_dir": payload["output_dir"],
            "artifact_manifest_path": payload["artifact_manifest_path"],
            "target_files": payload["target_files"],
            "forbidden_outputs": payload["forbidden_outputs"],
        }
        sections = [
            "# Superlooper Codex Module Dispatch Prompt\n\n",
            "## Runtime Agent Instructions\n\n",
            runtime_content.rstrip(),
            "\n\n## Current Manifest Node\n\n```json\n",
            json.dumps(node, ensure_ascii=False, indent=2),
            "\n```\n\n## Current Module Object\n\n```json\n",
            json.dumps(module, ensure_ascii=False, indent=2),
            "\n```\n\n## Allowed Design Paths\n\n",
        ]
        sections.extend(f"- `{path}`\n" for path in design_paths)
        sections.extend(
            [
                "\n## Output Contract\n\n```json\n",
                json.dumps(output_contract, ensure_ascii=False, indent=2),
                "\n```\n",
            ]
        )
        return "".join(sections)

    def _contract_path(self, path):
        return str(path.relative_to(self.root)).replace("\\", "/")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render one validated Codex mod_* child prompt from the shared execution manifest."
    )
    parser.add_argument(
        "--workspace-root",
        default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()),
        help="目标项目根目录。",
    )
    parser.add_argument(
        "--task-id",
        default=os.getenv("SUPERLOOPER_TASK_ID"),
        help="执行任务 ID。",
    )
    parser.add_argument(
        "--session-id",
        default=os.getenv("SUPERLOOPER_SESSION_ID"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--node-id",
        required=True,
        help="要渲染的 mod_* 节点 ID。",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        task_id = resolve_explicit_task_id(
            args.task_id,
            args.session_id,
            required=True,
        )
        renderer = CodexSpawnPromptRenderer(
            workspace_root=args.workspace_root,
            task_id=task_id,
            node_id=args.node_id,
        )
        return renderer.run()
    except (
        CodexPromptRenderError,
        ContractError,
        SessionStateValidationError,
        OSError,
    ) as exc:
        print(f"渲染 Codex child prompt 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
