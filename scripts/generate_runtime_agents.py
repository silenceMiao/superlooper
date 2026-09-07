import argparse
import json
import os
import re
import sys
from pathlib import Path

from generate_execution_manifest import FORBIDDEN_INPUTS, FORBIDDEN_OUTPUTS


SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
MODULE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
DESCRIPTION_PREFIX = "description: 动态模块编码子代理，负责 "
DESCRIPTION_ENDING_PUNCTUATION = ("。", ".", "！", "!", "？", "?")
CONSTRAINT_SECTION_TITLE = "## Runtime Module Constraints"
MODULE_CONSTRAINT_FIELDS = [
    "session_id",
    "module_id",
    "target_files",
    "file_roles",
    "requirement_refs",
    "decision_refs",
    "open_question_refs",
    "acceptance_refs",
    "ui_refs",
    "interaction_refs",
    "component_refs",
    "ui_acceptance_refs",
    "allowed_existing_files",
    "forbidden_files",
    "integration_points",
    "test_commands",
    "overwrite_policy",
    "test_focus",
    "forbidden_inputs",
    "forbidden_outputs",
]


class RuntimeAgentGenerationError(Exception):
    pass


class RuntimeAgentGenerator:
    def __init__(self, workspace_root, session_id, agents_dir, plugin_root=None, platform="claude"):
        self.root = Path(workspace_root).resolve()
        self.plugin_root = Path(plugin_root).resolve() if plugin_root else Path(__file__).resolve().parents[1]
        self.session_id = self._validate_session_id(session_id)
        self.platform = platform
        self.agents_dir = self._resolve_plugin_path(agents_dir, self.plugin_root / "agents")
        self.template_path = self.agents_dir / "developer.md"
        self.module_split_path = self.root / ".superlooper" / "manifests" / self.session_id / "module-split.json"
        self.runtime_agents_dir = self.root / ".superlooper" / "agents" / self.session_id
        self.registered_agents_dir = self.root / ".claude" / "agents" / "generated" / "superlooper" / self.session_id

    def run(self):
        template = self._read_template()
        modules = self._load_modules()
        generated_paths = []
        for module in modules:
            content = self._render_agent(template, module)
            module_id = module["id"]
            filename = f"module_{module_id}.md"
            runtime_path = self.runtime_agents_dir / filename
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.write_text(content, encoding="utf-8")
            generated_paths.append(self._contract_path(runtime_path))
            if self.platform == "claude":
                registered_path = self.registered_agents_dir / filename
                registered_path.parent.mkdir(parents=True, exist_ok=True)
                registered_path.write_text(content, encoding="utf-8")
                generated_paths.append(self._contract_path(registered_path))
        for path in generated_paths:
            print(path)
        return 0

    def _resolve_plugin_path(self, value, default):
        path = Path(value) if value else Path(default)
        if value and not path.is_absolute() and (":" in str(value) or path.drive):
            raise RuntimeAgentGenerationError(f"相对路径不能包含盘符或冒号：{value}")
        if not path.is_absolute():
            path = self.plugin_root / path
        return path.resolve()

    def _validate_session_id(self, session_id):
        if not session_id or session_id in {".", ".."} or not SESSION_PATTERN.match(session_id):
            raise RuntimeAgentGenerationError("session_id 只能包含字母、数字、下划线、短横线和点，且不能为 . 或 ..。")
        return session_id

    def _read_template(self):
        if not self.template_path.exists():
            raise RuntimeAgentGenerationError(f"developer 模板不存在：{self.template_path}")
        content = self.template_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            raise RuntimeAgentGenerationError("developer 模板缺少 YAML frontmatter。")
        if "---" not in [line.strip() for line in lines[1:]]:
            raise RuntimeAgentGenerationError("developer 模板 frontmatter 结束标记缺失。")
        if "name: developer" not in content:
            raise RuntimeAgentGenerationError("developer 模板缺少 frontmatter name: developer。")
        return content

    def _load_modules(self):
        if not self.module_split_path.exists():
            raise RuntimeAgentGenerationError(f"module-split 文件不存在：{self.module_split_path}")
        try:
            data = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeAgentGenerationError(f"module-split 解析失败：{exc}") from exc
        modules = data.get("modules") if isinstance(data, dict) else None
        if not isinstance(modules, list) or not modules:
            raise RuntimeAgentGenerationError("module-split.modules 必须是非空数组。")
        seen_ids = set()
        result = []
        for index, module in enumerate(modules):
            label = f"module-split.modules[{index}]"
            if not isinstance(module, dict):
                raise RuntimeAgentGenerationError(f"{label} 必须是 object。")
            module_id = module.get("id")
            if not isinstance(module_id, str) or not MODULE_PATTERN.match(module_id):
                raise RuntimeAgentGenerationError(f"{label}.id 必须匹配 {MODULE_PATTERN.pattern}。")
            if module_id in seen_ids:
                raise RuntimeAgentGenerationError(f"检测到重复 module_id：{module_id}")
            seen_ids.add(module_id)
            name = module.get("name")
            if not isinstance(name, str) or not name.strip():
                raise RuntimeAgentGenerationError(f"{label}.name 必须是非空字符串。")
            description = module.get("description")
            if not isinstance(description, str) or not description.strip():
                raise RuntimeAgentGenerationError(f"{label}.description 必须是非空字符串。")
            result.append(module)
        return result

    def _render_agent(self, template, module):
        module_id = module["id"]
        module_description = self._format_module_description(module["description"].strip())
        lines = template.splitlines(keepends=True)
        rendered = []
        in_frontmatter = False
        frontmatter_started = False
        frontmatter_ended = False
        description_replaced = False
        for line in lines:
            if not frontmatter_started:
                rendered.append(line)
                if line.strip() == "---":
                    frontmatter_started = True
                    in_frontmatter = True
                continue
            if in_frontmatter and line.strip() == "---":
                if not description_replaced:
                    rendered.append(f"{DESCRIPTION_PREFIX}{module_description}\n")
                    description_replaced = True
                rendered.append(line)
                in_frontmatter = False
                frontmatter_ended = True
                continue
            if in_frontmatter and line.startswith("name:"):
                rendered.append(f"name: module_{module_id}\n")
                continue
            if in_frontmatter and line.startswith("description:"):
                rendered.append(f"{DESCRIPTION_PREFIX}{module_description}\n")
                description_replaced = True
                continue
            rendered.append(line)
        if not frontmatter_ended:
            raise RuntimeAgentGenerationError("developer 模板 frontmatter 未正常结束。")
        content = "".join(rendered).rstrip() + "\n\n" + self._render_module_constraints(module)
        if f"name: module_{module_id}" not in content:
            raise RuntimeAgentGenerationError(f"模块 agent name 替换失败：{module_id}")
        if f"{DESCRIPTION_PREFIX}{module_description}" not in content:
            raise RuntimeAgentGenerationError(f"模块 agent description 替换失败：{module_id}")
        return content

    def _render_module_constraints(self, module):
        constraints = {
            "session_id": self.session_id,
            "module_id": module["id"],
            "target_files": self._module_list(module, "target_files"),
            "file_roles": self._module_list(module, "file_roles"),
            "requirement_refs": self._module_list(module, "requirement_refs"),
            "decision_refs": self._module_list(module, "decision_refs"),
            "open_question_refs": self._module_list(module, "open_question_refs"),
            "acceptance_refs": self._module_list(module, "acceptance_refs"),
            "ui_refs": self._module_list(module, "ui_refs"),
            "interaction_refs": self._module_list(module, "interaction_refs"),
            "component_refs": self._module_list(module, "component_refs"),
            "ui_acceptance_refs": self._module_list(module, "ui_acceptance_refs"),
            "allowed_existing_files": self._module_list(module, "allowed_existing_files"),
            "forbidden_files": self._module_list(module, "forbidden_files"),
            "integration_points": self._module_list(module, "integration_points"),
            "test_commands": self._module_list(module, "test_commands"),
            "overwrite_policy": module.get("overwrite_policy") or "block_by_default",
            "test_focus": self._module_list(module, "test_focus"),
            "forbidden_inputs": list(FORBIDDEN_INPUTS),
            "forbidden_outputs": list(FORBIDDEN_OUTPUTS),
        }
        lines = [f"{CONSTRAINT_SECTION_TITLE}\n\n", "```yaml\n"]
        for field in MODULE_CONSTRAINT_FIELDS:
            self._append_yaml_value(lines, field, constraints[field], 0)
        lines.append("```\n")
        return "".join(lines)

    def _module_list(self, module, field):
        value = module.get(field)
        if isinstance(value, list):
            return value
        return []

    def _append_yaml_value(self, lines, key, value, indent):
        prefix = " " * indent
        if isinstance(value, list):
            lines.append(f"{prefix}{key}:\n")
            for item in value:
                if isinstance(item, dict):
                    if not item:
                        lines.append(f"{prefix}  - {{}}\n")
                        continue
                    lines.append(f"{prefix}  -\n")
                    for child_key, child_value in item.items():
                        self._append_yaml_value(lines, child_key, child_value, indent + 4)
                else:
                    lines.append(f"{prefix}  - {self._format_yaml_scalar(item)}\n")
            return
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:\n")
            for child_key, child_value in value.items():
                self._append_yaml_value(lines, child_key, child_value, indent + 2)
            return
        lines.append(f"{prefix}{key}: {self._format_yaml_scalar(value)}\n")

    def _format_yaml_scalar(self, value):
        if value is None:
            return "null"
        text = str(value).replace("\n", "\\n")
        if not text:
            return '""'
        return text

    def _format_module_description(self, module_description):
        if module_description.endswith(DESCRIPTION_ENDING_PUNCTUATION):
            return module_description
        return f"{module_description}。"

    def _contract_path(self, path):
        return str(path.relative_to(self.root)).replace("\\", "/")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate SUPERLOOPER runtime module agents from agents/developer.md.")
    parser.add_argument(
        "--workspace-root",
        default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()),
        help="目标项目根目录，默认使用 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。",
    )
    parser.add_argument("--session-id", required=True, help="执行会话 ID。")
    parser.add_argument("--agents-dir", required=True, help="插件静态 agent 目录，例如 agents。相对路径按插件根目录解析。")
    parser.add_argument("--plugin-root", default=os.getenv("SUPERLOOPER_PLUGIN_ROOT"), help="插件源码或安装根目录，默认使用当前脚本所在插件根。")
    parser.add_argument("--platform", choices=("claude", "codex"), default="claude", help="平台注册目标，默认 claude。")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        generator = RuntimeAgentGenerator(
            workspace_root=args.workspace_root,
            session_id=args.session_id,
            agents_dir=args.agents_dir,
            plugin_root=args.plugin_root,
            platform=args.platform,
        )
        return generator.run()
    except RuntimeAgentGenerationError as exc:
        print(f"生成 runtime agents 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
