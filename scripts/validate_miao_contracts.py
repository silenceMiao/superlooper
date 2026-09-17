import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from create_session import (
    SessionStateValidationError,
    is_safe_relative_path,
    normalize_legacy_identity,
    resolve_explicit_task_id,
    windows_path_key,
)
from schema_validation import SchemaValidationError, SchemaValidator
from snapshot_digest import compute_tree_digest


TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
SNAPSHOT_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
PROTECTED_ROOTS = {".superlooper", ".git", ".svn", ".hg", ".claude", ".env"}
MODULE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
REQ_REF_PATTERN = re.compile(r"^REQ-[0-9]{3,}$")
DEC_REF_PATTERN = re.compile(r"^DEC-[0-9]{3,}$")
OPEN_REF_PATTERN = re.compile(r"^OPEN-[0-9]{3,}$")
AC_REF_PATTERN = re.compile(r"^AC-[0-9]{3,}$")
PRD_TRACEABILITY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])(?:REQ|AC|DEC|OPEN)-[0-9]{3,}(?![A-Za-z0-9_-])"
)
NODE_PATTERN = re.compile(r"^(mod_[a-z][a-z0-9_]*|task_[a-z0-9_]+)$")
UI_TRACEABILITY_FIELDS = ["ui_refs", "interaction_refs", "component_refs", "ui_acceptance_refs"]
BROWNFIELD_MODULE_LIST_FIELDS = ["allowed_existing_files", "forbidden_files", "integration_points", "test_commands"]
BROWNFIELD_MODULE_FIELDS = [*BROWNFIELD_MODULE_LIST_FIELDS, "overwrite_policy"]
PROJECT_MODES = {"greenfield", "brownfield", "brownfield-selective", "single_change", "ambiguous"}
SYSTEM_CHAIN = ["task_code_review", "task_merge", "task_integration_test", "task_apply_to_workspace"]
RESERVED_PLACEHOLDER_MODULE_IDS = {"feature_a", "feature_b", "module_a", "module_b"}
JAVA_MODULE_SUBDIRS = {"beans", "common", "aop", "core", "vo", "security", "log"}
JAVA_UTILS_SUBDIRS = {"inner", "outer"}
JAVA_FILE_ROLES = {
    "controller",
    "service",
    "service_impl",
    "dao",
    "module_beans",
    "module_common",
    "module_aop",
    "module_core",
    "module_vo",
    "module_security",
    "module_log",
    "utils_inner",
    "utils_outer",
    "mapper_xml",
    "test",
    "config",
    "other",
}
MODULE_PAYLOAD_ANCHORS = [
    "task_id",
    "module_id",
    "module_payload",
    "design_docs_path",
    "project_profile_path",
    "module_split_path",
    "execution_manifest_path",
    "output_dir",
    "artifact_manifest_path",
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
DYNAMIC_AGENT_CONSTRAINT_TITLE = "## Runtime Module Constraints"
DYNAMIC_AGENT_CONSTRAINT_FIELDS = [
    "task_id",
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
INTERACTION_COMMAND_PATTERN = re.compile(r"^/spl(:[a-z_]+)?$")
INTERACTION_FORBIDDEN_COMMAND = "/spl:manifest"
INTERACTION_COMMAND_PHASES = {"init", "prd", "ui_design", "design", "run", "status", "resume", "doctor"}
INTERACTION_WORKFLOW_PHASES = {"prd", "ui_design", "design", "run"}
INTERACTION_INITIALIZATION_OPTIONS = {
    "java": ["jdk-8", "jdk-11", "jdk-17"],
    "go": ["go-1.25"],
    "springboot": ["springboot-2.x", "springboot-3.x"],
    "pom": ["maven-3.5.x", "maven-3.9.x"],
    "lua": ["lua-4.x", "lua-5.x"],
}
INTERACTION_REPLY_PATTERN = re.compile(r"回复\s+(?:“([^”]+)”|([^`\n。]+))")
INTERACTION_COMMAND_FILES = {
    "/spl": "commands/spl.md",
    "/spl:prd": "commands/spl/prd.md",
    "/spl:ui": "commands/spl/ui.md",
    "/spl:design": "commands/spl/design.md",
    "/spl:run": "commands/spl/run.md",
    "/spl:status": "commands/spl/status.md",
    "/spl:resume": "commands/spl/resume.md",
    "/spl:doctor": "commands/spl/doctor.md",
}
INTERACTION_REQUIRED_REPLIES = {
    "已确认，重新生成 PRD",
    "PRD未通过，按反馈重新分析",
    "通过，进入 UI 设计",
    "UI设计未通过，按反馈重新设计",
    "UI设计通过，进入系统设计",
    "需求变更，返回 PRD 修订",
    "继续任务",
    "设计未通过，按反馈重新设计",
    "生成执行清单",
    "执行",
    "开始并行开发",
    "按此执行",
    "执行摘要未通过，返回修正",
    "需求变更，执行影响分析",
    "选择初始化项目分类",
    "选择初始化项目版本",
    "影响分析通过，执行局部重跑",
    "影响分析不通过，人工处理",
    "java",
    "go",
    "springboot",
    "pom",
    "lua",
    "jdk-8",
    "jdk-11",
    "jdk-17",
    "go-1.25",
    "springboot-2.x",
    "springboot-3.x",
    "maven-3.5.x",
    "maven-3.9.x",
    "lua-4.x",
    "lua-5.x",
    "需求校对通过，完成交付",
    "需求校对未通过，返回修正",
    "代码审查未通过，返回修正",
    "测试未通过，返回修正",
    "应用冲突已处理，重新应用",
}
INTERACTION_REQUIRED_CANONICAL_ACTIONS = {
    "prd": {"prd_decisions_confirmed", "prd_revision_requested", "approve_and_proceed"},
    "ui_design": {"ui_revision_requested", "approve_ui_and_proceed", "prd_revision_requested"},
    "design": {"continue_current_flow", "design_revision_requested", "change_impact_requested", "select_project_category", "select_project_version"},
    "run": {"execution_summary_approved", "execution_summary_revision_requested", "start_execution", "change_impact_requested", "local_rerun_approved", "manual_handling_requested", "code_review_revision_requested", "test_revision_requested", "apply_retry_requested", "requirement_alignment_approved", "requirement_alignment_revision_requested"},
}
UI_STATUSES = {"NOT_STARTED", "IN_PROGRESS", "READY_FOR_REVIEW", "CHANGES_REQUESTED", "APPROVED", "BLOCKED", "FAILED"}
EXECUTION_SUMMARY_STATUSES = {"NOT_STARTED", "READY_FOR_APPROVAL", "APPROVED", "REJECTED", "BLOCKED"}
WORKFLOW_MODES = {"standard", "strict_review"}
ALIGNMENT_STATUSES = {"PASS", "FAIL", "BLOCKED"}
ALIGNMENT_LOOP_TARGET_PHASES = {"prd", "ui_design", "design", "initialization", "run", "requirement_alignment"}
UI_REQUIRED_FILES = ["ui-spec.md", "page-map.md", "interaction-flow.md", "ui-handoff.md", "preview.html"]
UI_SPEC_REQUIRED_FIELDS = [
    "task_id",
    "ui_status",
    "prd_path",
    "ui_output_dir",
    "preview_path",
    "project_mode",
    "existing_frontend",
    "page_count",
    "interaction_count",
    "unresolved_ui_decision_count",
]
UI_PREVIEW_FORBIDDEN_PATTERNS = ["http://", "https://", "cdn.", "fetch(", "XMLHttpRequest"]


class ContractError(Exception):
    pass


class ContractValidator:
    def __init__(self, workspace_root, task_id, agents_dir=None, module_split=None, execution_manifest=None, outputs_root=None, runtime_agents_dir=None, registered_agents_dir=None, plugin_root=None):
        self.root = Path(workspace_root).resolve()
        self.plugin_root = Path(plugin_root).resolve() if plugin_root else Path(__file__).resolve().parents[1]
        self.task_id = task_id
        self.errors = []
        self.agents_dir = self._resolve_plugin_path(agents_dir, self.plugin_root / "agents")
        self.runtime_agents_dir = self._resolve_scoped_path(runtime_agents_dir, self.root / ".superlooper" / "agents" / self.task_id)
        self.registered_agents_dir = self._resolve_scoped_path(registered_agents_dir, self.root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id)
        self.manifests_dir = self.root / ".superlooper" / "manifests" / self.task_id
        self.module_split_path = self._resolve_scoped_path(module_split, self.manifests_dir / "module-split.json")
        self.execution_manifest_path = self._resolve_scoped_path(execution_manifest, self.manifests_dir / "execution_manifest.json")
        self.outputs_root = self._resolve_scoped_path(outputs_root, self.root / ".superlooper" / "outputs")
        self.reports_dir = self.root / ".superlooper" / "reports" / self.task_id
        self.state_path = self.root / ".superlooper" / "state" / f"{self.task_id}.json"
        self.dag_state_path = self.root / ".superlooper" / "state" / f"{self.task_id}.dag.json"
        self.event_log_path = self.root / ".superlooper" / "events" / f"{self.task_id}.jsonl"

    def _resolve_scoped_path(self, value, default):
        path = Path(value) if value else Path(default)
        if value and not path.is_absolute() and (":" in str(value) or path.drive):
            raise ContractError(f"相对路径不能包含盘符或冒号：{value}")
        if not path.is_absolute():
            path = self.root / path
        path = path.resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ContractError(f"路径必须位于 workspace_root 内：{path}") from exc
        return path

    def _resolve_plugin_path(self, value, default):
        path = Path(value) if value else Path(default)
        if value and not path.is_absolute() and (":" in str(value) or path.drive):
            raise ContractError(f"相对路径不能包含盘符或冒号：{value}")
        if not path.is_absolute():
            path = self.plugin_root / path
        return path.resolve()

    def validate(self, scope):
        self._validate_task_id()
        if scope in ("interaction-flow", "all"):
            self.validate_interaction_flow(required=True)
        if scope in ("module-split", "all"):
            self.validate_module_split(required=scope == "module-split")
        if scope in ("execution", "all"):
            self.validate_execution_manifest(required=scope == "execution")
        if scope in ("artifacts", "all"):
            self.validate_artifacts(required=scope == "artifacts")
        if scope in ("code-review-report", "reports"):
            self.validate_code_review_report(required=True)
        if scope in ("test-report", "reports"):
            self.validate_test_report(required=True)
        if scope in ("apply-report", "reports"):
            self.validate_apply_report(required=True)
        if scope == "initialization-advice":
            self.validate_initialization_advice(required=True)
        if scope in ("initialization-report", "reports"):
            self.validate_initialization_report(required=True)
        if scope in ("requirement-alignment-report", "reports"):
            self.validate_requirement_alignment_report(required=True)
        if scope in ("execution-summary", "reports"):
            self.validate_execution_summary(required=True)
        if scope in ("upstream-alignment", "reports"):
            self.validate_upstream_alignment(required=True)
        if scope in ("change-impact-report", "reports"):
            self.validate_change_impact_report(required=True)
        if scope in ("ui-artifacts", "all"):
            self.validate_ui_artifacts(required=scope == "ui-artifacts")
        if scope in ("dag-state", "all"):
            self.validate_dag_state(required=scope == "dag-state")
        if scope in ("observability", "all"):
            self.validate_observability(required=scope == "observability")
        if scope == "all":
            self.validate_code_review_report(required=False)
            self.validate_test_report(required=False)
            self.validate_apply_report(required=False)
            self.validate_initialization_advice(required=False)
            self.validate_initialization_report(required=False)
            self.validate_requirement_alignment_report(required=False)
            self.validate_execution_summary(required=False)
            self.validate_upstream_alignment(required=False)
            self.validate_change_impact_report(required=False)
        if self.errors:
            raise ContractError("\n".join(f"- {error}" for error in self.errors))

    def validate_interaction_flow(self, required=False):
        flow_path = self.plugin_root / "configs" / "interaction-flow.json"
        schema_path = self.plugin_root / "schemas" / "interaction-flow.schema.json"
        if not flow_path.exists():
            if required:
                self.errors.append(f"interaction-flow 文件不存在：{flow_path}")
            return None
        if not schema_path.exists():
            self.errors.append(f"interaction-flow schema 不存在：{schema_path}")
            return None
        flow = self._read_json(flow_path)
        schema = self._read_json(schema_path)
        if not isinstance(flow, dict):
            self.errors.append("interaction-flow 顶层必须是 object。")
            return None
        if not isinstance(schema, dict):
            self.errors.append("interaction-flow schema 顶层必须是 object。")
            return flow
        self._validate_schema_data(flow, schema, "interaction-flow")
        schema_required = schema.get("required")
        if not isinstance(schema_required, list):
            self.errors.append("interaction-flow schema.required 必须是数组。")
            return flow
        for field in schema_required:
            if field not in flow:
                self.errors.append(f"interaction-flow 缺少必填字段：{field}")
        self._require_string(flow, "version", "interaction-flow")
        initialization_options = flow.get("initialization_options")
        if initialization_options != INTERACTION_INITIALIZATION_OPTIONS:
            self.errors.append("interaction-flow.initialization_options 必须声明固定项目分类和版本。")
        commands = flow.get("commands")
        phases = flow.get("phases")
        if not isinstance(commands, list) or not commands:
            self.errors.append("interaction-flow.commands 必须是非空数组。")
            return flow
        if not isinstance(phases, list) or not phases:
            self.errors.append("interaction-flow.phases 必须是非空数组。")
            return flow
        command_names = set()
        command_phases = {}
        exposed_commands = set()
        for index, command in enumerate(commands):
            label = f"interaction-flow.commands[{index}]"
            if not isinstance(command, dict):
                self.errors.append(f"{label} 必须是 object。")
                continue
            name = command.get("name")
            if not isinstance(name, str) or not INTERACTION_COMMAND_PATTERN.match(name):
                self.errors.append(f"{label}.name 必须匹配 {INTERACTION_COMMAND_PATTERN.pattern}。")
            elif name == INTERACTION_FORBIDDEN_COMMAND:
                self.errors.append(f"{label}.name 禁止使用 {INTERACTION_FORBIDDEN_COMMAND}。")
            elif name in command_names:
                self.errors.append(f"interaction-flow.commands 存在重复命令：{name}")
            else:
                command_names.add(name)
            phase = command.get("phase")
            if phase not in INTERACTION_COMMAND_PHASES:
                self.errors.append(f"{label}.phase 必须为 init/prd/ui_design/design/run/status/resume/doctor：{phase}")
            elif isinstance(name, str) and name in command_names:
                command_phases[name] = phase
            if not isinstance(command.get("exposed"), bool):
                self.errors.append(f"{label}.exposed 必须是 boolean。")
            elif command.get("exposed") is True and isinstance(name, str):
                exposed_commands.add(name)
        phase_ids = set()
        flow_replies = set()
        for index, phase in enumerate(phases):
            label = f"interaction-flow.phases[{index}]"
            if not isinstance(phase, dict):
                self.errors.append(f"{label} 必须是 object。")
                continue
            phase_id = phase.get("id")
            if phase_id not in INTERACTION_WORKFLOW_PHASES:
                self.errors.append(f"{label}.id 必须为 prd/ui_design/design/run：{phase_id}")
            elif phase_id in phase_ids:
                self.errors.append(f"interaction-flow.phases 存在重复阶段：{phase_id}")
            else:
                phase_ids.add(phase_id)
            entry_command = phase.get("entry_command")
            if not isinstance(entry_command, str) or not INTERACTION_COMMAND_PATTERN.match(entry_command):
                self.errors.append(f"{label}.entry_command 必须匹配 {INTERACTION_COMMAND_PATTERN.pattern}。")
            elif entry_command == INTERACTION_FORBIDDEN_COMMAND:
                self.errors.append(f"{label}.entry_command 禁止使用 {INTERACTION_FORBIDDEN_COMMAND}。")
            elif entry_command not in command_names:
                self.errors.append(f"{label}.entry_command 必须已声明于 commands：{entry_command}")
            elif phase_id in INTERACTION_WORKFLOW_PHASES and command_phases.get(entry_command) != phase_id:
                self.errors.append(f"{label}.entry_command 对应 command.phase 必须为 {phase_id}：{entry_command}")
            allowed_replies = phase.get("allowed_replies")
            if not isinstance(allowed_replies, list) or not allowed_replies:
                self.errors.append(f"{label}.allowed_replies 必须是非空数组。")
                allowed_reply_set = set()
            else:
                allowed_reply_set = set()
                for reply_index, reply in enumerate(allowed_replies):
                    if not isinstance(reply, str) or not reply.strip():
                        self.errors.append(f"{label}.allowed_replies[{reply_index}] 必须是非空字符串。")
                    else:
                        flow_replies.add(reply)
                        allowed_reply_set.add(reply)
            canonical_actions = phase.get("canonical_actions")
            action_names = set()
            alias_owners = {}
            if not isinstance(canonical_actions, list) or not canonical_actions:
                self.errors.append(f"{label}.canonical_actions 必须是非空数组。")
            else:
                for action_index, action in enumerate(canonical_actions):
                    action_label = f"{label}.canonical_actions[{action_index}]"
                    if not isinstance(action, dict):
                        self.errors.append(f"{action_label} 必须是 object。")
                        continue
                    name = action.get("name")
                    if not isinstance(name, str) or not name.strip():
                        self.errors.append(f"{action_label}.name 必须是非空字符串。")
                    elif name in action_names:
                        self.errors.append(f"{label}.canonical_actions 存在重复动作：{name}")
                    else:
                        action_names.add(name)
                    canonical_reply = action.get("canonical_reply")
                    if not isinstance(canonical_reply, str) or not canonical_reply.strip():
                        self.errors.append(f"{action_label}.canonical_reply 必须是非空字符串。")
                    elif canonical_reply not in allowed_reply_set:
                        self.errors.append(f"{action_label}.canonical_reply 必须存在于 allowed_replies：{canonical_reply}")
                    aliases = action.get("aliases")
                    if not isinstance(aliases, list) or not aliases:
                        self.errors.append(f"{action_label}.aliases 必须是非空数组。")
                    else:
                        for alias_index, alias in enumerate(aliases):
                            if not isinstance(alias, str) or not alias.strip():
                                self.errors.append(f"{action_label}.aliases[{alias_index}] 必须是非空字符串。")
                                continue
                            owner = alias_owners.get(alias)
                            if owner and owner != name:
                                self.errors.append(f"{label}.canonical_actions alias 重复映射：{alias}")
                            else:
                                alias_owners[alias] = name
                    if not isinstance(action.get("requires_feedback"), bool):
                        self.errors.append(f"{action_label}.requires_feedback 必须是 boolean。")
            if isinstance(phase_id, str):
                missing_actions = sorted(INTERACTION_REQUIRED_CANONICAL_ACTIONS.get(phase_id, set()) - action_names)
                for action_name in missing_actions:
                    self.errors.append(f"interaction-flow.{phase_id} 缺少 canonical action：{action_name}")
            next_phase = phase.get("next_phase")
            if next_phase not in {"prd", "ui_design", "design", "run", None}:
                self.errors.append(f"{label}.next_phase 必须为 prd/ui_design/design/run/null：{next_phase}")
        missing_phase_ids = sorted(INTERACTION_WORKFLOW_PHASES - phase_ids)
        for phase_id in missing_phase_ids:
            self.errors.append(f"interaction-flow 缺少必需阶段：{phase_id}")
        phase_by_id = {phase.get("id"): phase for phase in phases if isinstance(phase, dict)}
        if phase_by_id.get("prd", {}).get("next_phase") != "ui_design":
            self.errors.append("interaction-flow.prd.next_phase 必须为 ui_design。")
        if phase_by_id.get("ui_design", {}).get("next_phase") != "design":
            self.errors.append("interaction-flow.ui_design.next_phase 必须为 design。")
        for command_name in sorted(exposed_commands):
            expected_path = INTERACTION_COMMAND_FILES.get(command_name)
            if not expected_path:
                self.errors.append(f"公开命令缺少文件映射：{command_name}")
                continue
            command_path = self.plugin_root / expected_path
            if not command_path.exists():
                self.errors.append(f"公开命令文件不存在：{command_path}")
            else:
                for reply in self._command_handshake_replies(command_path):
                    if reply not in flow_replies:
                        self.errors.append(f"命令文件握手回复未声明于 interaction-flow：{expected_path}: {reply}")
        missing_replies = sorted(INTERACTION_REQUIRED_REPLIES - flow_replies)
        for reply in missing_replies:
            self.errors.append(f"interaction-flow 缺少固定握手回复：{reply}")
        return flow

    def _command_handshake_replies(self, command_path):
        content = command_path.read_text(encoding="utf-8")
        replies = []
        for match in INTERACTION_REPLY_PATTERN.finditer(content):
            raw = match.group(1) or match.group(2) or ""
            raw = raw.replace("`", "").replace("。", " ")
            for item in re.split(r"\s+或\s+|\s+和\s+", raw):
                reply = item.strip(" ，,；;。\"'“”")
                if reply:
                    replies.append(reply)
        return replies

    def validate_module_split(self, required=False):
        if not self.module_split_path.exists():
            if required:
                self.errors.append(f"module-split 文件不存在：{self.module_split_path}")
            return None
        data = self._read_json(self.module_split_path)
        if not isinstance(data, dict):
            self.errors.append("module-split 顶层必须是 object。")
            return None
        self._validate_schema(data, "module-split.schema.json", "module-split")
        self._require_string(data, "project_name", "module-split")
        project_profile = data.get("project_profile")
        if project_profile is not None:
            self._validate_project_profile(project_profile)
        java_project = self._is_java_project(project_profile)
        modules = data.get("modules")
        if not isinstance(modules, list) or not modules:
            self.errors.append("module-split.modules 必须是非空数组。")
            return data
        seen = set()
        target_file_owners = {}
        for index, module in enumerate(modules):
            path = f"module-split.modules[{index}]"
            if not isinstance(module, dict):
                self.errors.append(f"{path} 必须是 object。")
                continue
            module_id = module.get("id")
            if not isinstance(module_id, str) or not MODULE_PATTERN.match(module_id):
                self.errors.append(f"{path}.id 必须匹配 {MODULE_PATTERN.pattern}。")
            elif module_id in RESERVED_PLACEHOLDER_MODULE_IDS:
                self.errors.append(f"{path}.id 不能使用无业务语义的占位命名：{module_id}")
            elif module_id in seen:
                self.errors.append(f"{path}.id 重复：{module_id}")
            else:
                seen.add(module_id)
            self._require_string(module, "name", path)
            self._require_string(module, "description", path)
            self._require_array(module, "referenced_tables", path)
            self._require_array(module, "referenced_apis", path)
            target_files = module.get("target_files")
            if java_project and not target_files:
                self.errors.append(f"{path}.target_files 在 Java 后端项目中必须声明。")
            if target_files is not None:
                if not isinstance(target_files, list):
                    self.errors.append(f"{path}.target_files 必须是数组。")
                else:
                    module_target_files = set()
                    for file_index, target_file in enumerate(target_files):
                        target_label = f"{path}.target_files[{file_index}]"
                        if not self._safe_relative_path(target_file):
                            self.errors.append(f"{target_label} 不是安全相对路径：{target_file}")
                            continue
                        target_key = windows_path_key(target_file)
                        if target_key in module_target_files:
                            self.errors.append(f"{path}.target_files 存在重复路径：{target_file}")
                        module_target_files.add(target_key)
                        owner = target_file_owners.get(target_key)
                        if owner and owner != module_id:
                            self.errors.append(f"module-split.modules target_files 存在跨模块重复路径：{target_file} 同时属于 {owner}, {module_id}")
                        else:
                            target_file_owners[target_key] = module_id
                        if java_project:
                            self._validate_java_target_file(target_file, target_label)
            file_roles = module.get("file_roles")
            if file_roles is not None:
                self._validate_file_roles(path, file_roles, target_files)
            self._validate_traceability_refs(path, module)
            self._validate_brownfield_boundaries(path, module, target_files)
        self._validate_module_dependencies(modules)
        return data

    def _validate_project_profile(self, project_profile):
        if not isinstance(project_profile, dict):
            self.errors.append("module-split.project_profile 必须是 object。")
            return
        project_mode = project_profile.get("project_mode")
        if project_mode is not None and project_mode not in PROJECT_MODES:
            self.errors.append(f"module-split.project_profile.project_mode 不合法：{project_mode}")
        for field in ["source_roots", "test_roots", "config_roots", "mapper_roots"]:
            values = project_profile.get(field)
            if values is None:
                continue
            if not isinstance(values, list):
                self.errors.append(f"module-split.project_profile.{field} 必须是数组。")
                continue
            for index, value in enumerate(values):
                if not self._safe_relative_path(value):
                    self.errors.append(f"module-split.project_profile.{field}[{index}] 不是安全相对路径：{value}")
        layer_conventions = project_profile.get("layer_conventions")
        if layer_conventions is not None:
            self._validate_layer_conventions(layer_conventions)

    def _validate_layer_conventions(self, layer_conventions):
        if not isinstance(layer_conventions, dict):
            self.errors.append("module-split.project_profile.layer_conventions 必须是 object。")
            return
        path_fields = [
            "controller_dirs",
            "service_dirs",
            "service_impl_dirs",
            "dao_dirs",
            "module_dirs",
            "utils_dirs",
            "mapper_xml_dirs",
        ]
        for field in path_fields:
            values = layer_conventions.get(field)
            if values is None:
                continue
            if not isinstance(values, list):
                self.errors.append(f"module-split.project_profile.layer_conventions.{field} 必须是数组。")
                continue
            for index, value in enumerate(values):
                if not self._safe_relative_path(value):
                    self.errors.append(f"module-split.project_profile.layer_conventions.{field}[{index}] 不是安全相对路径：{value}")
        self._validate_string_set(layer_conventions, "module_subdirs", JAVA_MODULE_SUBDIRS)
        self._validate_string_set(layer_conventions, "utils_subdirs", JAVA_UTILS_SUBDIRS)

    def _validate_string_set(self, data, field, allowed):
        values = data.get(field)
        if values is None:
            return
        if not isinstance(values, list):
            self.errors.append(f"module-split.project_profile.layer_conventions.{field} 必须是数组。")
            return
        for index, value in enumerate(values):
            if value not in allowed:
                self.errors.append(f"module-split.project_profile.layer_conventions.{field}[{index}] 不合法：{value}")

    def validate_execution_manifest(self, required=False):
        if not self.execution_manifest_path.exists():
            if required:
                self.errors.append(f"Execution Manifest 文件不存在：{self.execution_manifest_path}")
            return None
        manifest = self._read_json(self.execution_manifest_path)
        if not isinstance(manifest, dict):
            self.errors.append("Execution Manifest 顶层必须是 object。")
            return None
        dag = manifest.get("dag")
        nodes = dag.get("nodes") if isinstance(dag, dict) else None
        if isinstance(nodes, list):
            for index, node in enumerate(nodes):
                payload = node.get("payload") if isinstance(node, dict) else None
                if isinstance(payload, dict):
                    normalized_payload = self._normalize_identity(payload, f"Execution Manifest dag.nodes[{index}].payload")
                    if normalized_payload is None:
                        return None
                    node["payload"] = normalized_payload
        self._validate_schema(manifest, "execution-manifest.schema.json", "Execution Manifest")
        if manifest.get("task_id") != self.task_id:
            self.errors.append("Execution Manifest task_id 必须与当前 task_id 一致。")
        if manifest.get("granularity") != "module":
            self.errors.append("Execution Manifest granularity 必须为 module。")
        context = manifest.get("context")
        platform = "claude"
        if not isinstance(context, dict):
            self.errors.append("Execution Manifest context 必须是 object。")
        else:
            platform = self._validate_execution_context(context)
        dag = manifest.get("dag")
        if not isinstance(dag, dict):
            self.errors.append("Execution Manifest dag 必须是 object。")
            return manifest
        nodes = dag.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            self.errors.append("Execution Manifest dag.nodes 必须是非空数组。")
            return manifest
        node_map = {}
        for index, node in enumerate(nodes):
            path = f"dag.nodes[{index}]"
            if not isinstance(node, dict):
                self.errors.append(f"{path} 必须是 object。")
                continue
            node_id = node.get("id")
            if not isinstance(node_id, str) or not NODE_PATTERN.match(node_id):
                self.errors.append(f"{path}.id 不合法：{node_id}")
                continue
            if node_id in node_map:
                self.errors.append(f"DAG 节点 id 重复：{node_id}")
            node_map[node_id] = node
            self._require_string(node, "agent", path)
            self._validate_node_payload(path, node.get("payload"))
            if not isinstance(node.get("depends_on"), list):
                self.errors.append(f"{path}.depends_on 必须是数组。")
            agent = node.get("agent")
            if node_id.startswith("mod_"):
                module_id = node_id.removeprefix("mod_")
                if module_id in RESERVED_PLACEHOLDER_MODULE_IDS:
                    self.errors.append(f"{path}.id 不能使用无业务语义的占位命名：{node_id}")
                if isinstance(agent, str):
                    expected_agent = f"module_{module_id}"
                    if agent != expected_agent:
                        self.errors.append(f"{path}.agent 必须为 {expected_agent}。")
                    self._validate_module_payload_anchors(path, node.get("payload"), module_id)
                    self._validate_dynamic_agent(agent, node.get("payload"), require_registered=platform == "claude")
            else:
                if node_id in SYSTEM_CHAIN:
                    self._validate_system_payload(node_id, node.get("payload"))
                if isinstance(agent, str):
                    self._validate_static_agent(agent)
        self._validate_module_node_set(node_map)
        self._validate_dag_links(node_map)
        self._validate_system_chain(node_map)
        return manifest

    def validate_artifacts(self, required=False):
        manifest = self.validate_execution_manifest(required=False)
        target_files_by_module, java_project = self._target_files_by_module()
        if not self.outputs_root.exists():
            if required:
                self.errors.append(f"模块 outputs 根目录不存在：{self.outputs_root}")
            return
        task_outputs = self.outputs_root / self.task_id
        resolved_task_outputs = task_outputs
        if task_outputs.exists():
            resolved_task_outputs = self._resolve_artifact_path(
                task_outputs,
                self.outputs_root,
                "task 模块产物目录",
            )
            if resolved_task_outputs is None:
                return
        module_ids = self._module_ids_from_manifest(manifest)
        if not module_ids:
            module_ids = [p.name for p in task_outputs.iterdir() if p.is_dir()] if task_outputs.exists() else []
        for module_id in module_ids:
            module_dir = resolved_task_outputs / module_id
            if not module_dir.is_dir():
                self.errors.append(f"模块产物目录不存在：{module_dir}")
                continue
            resolved_module_dir = self._resolve_artifact_path(
                module_dir,
                resolved_task_outputs,
                f"{module_id} 模块产物目录",
            )
            if resolved_module_dir is None:
                continue
            if resolved_module_dir != module_dir:
                self.errors.append(
                    f"{module_id} 模块产物目录不在对应授权目录内：{module_dir}"
                )
                continue
            artifact_path = resolved_module_dir / "artifact_manifest.json"
            if not artifact_path.exists():
                self.errors.append(f"缺少 artifact_manifest.json：{artifact_path}")
                continue
            resolved_artifact_path = self._resolve_artifact_path(
                artifact_path,
                resolved_module_dir,
                f"{module_id} artifact_manifest.json",
            )
            if resolved_artifact_path is None:
                continue
            artifact = self._read_json(resolved_artifact_path)
            self._validate_artifact(module_id, resolved_module_dir, artifact, target_files_by_module.get(module_id), java_project)

    def _validate_artifact(self, module_id, module_dir, artifact, target_files=None, java_project=False):
        if not isinstance(artifact, dict):
            self.errors.append(f"{module_id} artifact_manifest 顶层必须是 object。")
            return
        self._validate_schema(artifact, "artifact-manifest.schema.json", f"{module_id} artifact_manifest")
        if artifact.get("task_id") != self.task_id:
            self.errors.append(f"{module_id} artifact task_id 不一致。")
        if artifact.get("module_id") != module_id:
            self.errors.append(f"{module_id} artifact module_id 不一致。")
        expected_agent = f"module_{module_id}"
        if artifact.get("agent") != expected_agent:
            self.errors.append(f"{module_id} artifact agent 必须为 {expected_agent}。")
        status = artifact.get("status")
        if status not in ["success", "failed", "blocked"]:
            self.errors.append(f"{module_id} artifact status 不合法。")
        elif status != "success":
            self.errors.append(f"{module_id} artifact status 为 {status}，禁止进入 code-review / merge。")
        produced_files = artifact.get("produced_files")
        if not isinstance(produced_files, list):
            self.errors.append(f"{module_id} produced_files 必须是数组。")
            return
        declared = set()
        allowed_targets = {
            windows_path_key(value)
            for value in (target_files or [])
        }
        actual_files = {}
        for actual_path in module_dir.rglob("*"):
            if not actual_path.is_file() or actual_path.name == "artifact_manifest.json":
                continue
            relative = str(actual_path.relative_to(module_dir)).replace("\\", "/")
            resolved_actual_path = self._resolve_artifact_path(
                actual_path,
                module_dir,
                f"{module_id} 模块文件 {relative}",
            )
            if resolved_actual_path is None:
                continue
            relative_key = windows_path_key(relative)
            existing = actual_files.get(relative_key)
            if existing is not None:
                self.errors.append(
                    f"{module_id} 模块实际文件存在 Windows 等价重复路径："
                    f"{existing} 与 {relative}"
                )
                continue
            actual_files[relative_key] = relative
        for index, item in enumerate(produced_files):
            path = f"{module_id}.produced_files[{index}]"
            if not isinstance(item, dict):
                self.errors.append(f"{path} 必须是 object。")
                continue
            relative = item.get("path")
            if not self._safe_relative_path(relative):
                self.errors.append(f"{path}.path 不是安全相对路径：{relative}")
                continue
            relative_key = windows_path_key(relative)
            if relative_key in declared:
                self.errors.append(f"{module_id}.produced_files 存在重复路径：{relative}")
            declared.add(relative_key)
            if allowed_targets and relative_key not in allowed_targets:
                self.errors.append(f"{path}.path 未包含在 module-split target_files 中：{relative}")
            if java_project:
                self._validate_java_target_file(relative, f"{path}.path")
            if item.get("kind") not in ["code", "config", "test", "doc", "asset", "other"]:
                self.errors.append(f"{path}.kind 不合法。")
            if item.get("operation") not in ["create", "modify"]:
                self.errors.append(f"{path}.operation 不合法；当前合并与应用链路仅支持 create / modify。")
            if not isinstance(item.get("required_for_merge"), bool):
                self.errors.append(f"{path}.required_for_merge 必须是 boolean。")
            if item.get("required_for_merge") is True and relative_key not in actual_files:
                self.errors.append(f"{path}.path 声明文件不存在：{module_dir / relative}")
        notes = artifact.get("notes")
        verification = artifact.get("verification")
        if not isinstance(verification, dict):
            self.errors.append(f"{module_id}.verification 必须是 object。")
        else:
            self._validate_artifact_verification(module_id, status, verification, notes)
        if not isinstance(notes, list):
            self.errors.append(f"{module_id}.notes 必须是数组。")
        undeclared = sorted(
            actual_files[key]
            for key in actual_files.keys() - declared
        )
        if undeclared:
            self.errors.append(f"{module_id} 存在未声明文件：{', '.join(undeclared)}")

    def _validate_artifact_verification(self, module_id, artifact_status, verification, notes):
        commands = verification.get("commands")
        if not isinstance(commands, list):
            self.errors.append(f"{module_id}.verification.commands 必须是数组。")
            return
        summary = verification.get("summary")
        if not isinstance(summary, str):
            self.errors.append(f"{module_id}.verification.summary 必须是字符串。")
        if artifact_status == "success" and not commands:
            self.errors.append(f"{module_id}.verification.commands 在 artifact status=success 时必须是非空数组。")
        skipped_without_context = False
        for index, command in enumerate(commands):
            label = f"{module_id}.verification.commands[{index}]"
            if not isinstance(command, dict):
                self.errors.append(f"{label} 必须是 object。")
                continue
            command_status = command.get("status")
            if command_status not in ["passed", "failed", "skipped"]:
                self.errors.append(f"{label}.status 不合法。")
            if artifact_status == "success" and command_status == "failed":
                self.errors.append(f"{label}.status 为 failed，artifact status 不得为 success。")
            if artifact_status == "success" and command_status == "skipped":
                skipped_without_context = True
        has_summary = isinstance(summary, str) and bool(summary.strip())
        has_notes = isinstance(notes, list) and any(isinstance(note, str) and note.strip() for note in notes)
        if artifact_status in ["failed", "blocked"] and not has_summary and not has_notes:
            self.errors.append(f"{module_id} artifact status 为 {artifact_status} 时必须在 verification.summary 或 notes 说明原因。")
        if skipped_without_context and not has_summary and not has_notes:
            self.errors.append(f"{module_id}.verification.commands 存在 skipped 时必须在 verification.summary 或 notes 说明原因。")

    def _validate_execution_context(self, context):
        registration = context.get("platform_registration")
        platform = "claude"
        if registration is None:
            fields = [
                "prd_path",
                "design_docs_path",
                "module_split_path",
                "agents_path",
                "runtime_agents_path",
                "registered_agents_path",
                "outputs_path",
                "merged_path",
                "reports_path",
            ]
        else:
            platform = "codex"
            fields = [
                "prd_path",
                "design_docs_path",
                "module_split_path",
                "agents_path",
                "runtime_agents_path",
                "outputs_path",
                "merged_path",
                "reports_path",
            ]
            if not isinstance(registration, dict):
                self.errors.append("Execution Manifest context.platform_registration 必须是 object。")
            else:
                if registration != {"platform": "codex"}:
                    self.errors.append("Execution Manifest context.platform_registration 必须为 {\"platform\": \"codex\"}。")
            if "registered_agents_path" in context:
                self.errors.append("Codex Execution Manifest context 不得包含 registered_agents_path。")
        for field in fields:
            self._require_string(context, field, "Execution Manifest context")
            value = context.get(field)
            if isinstance(value, str) and not self._safe_relative_path(value, allow_protected=True):
                self.errors.append(f"Execution Manifest context.{field} 不是安全相对路径：{value}")
        expected_paths = {
            "prd_path": f".superlooper/context/{self.task_id}/prd.md",
            "design_docs_path": f".superlooper/context/{self.task_id}/design/",
            "module_split_path": f".superlooper/manifests/{self.task_id}/module-split.json",
            "runtime_agents_path": f".superlooper/agents/{self.task_id}/",
            "outputs_path": f".superlooper/outputs/{self.task_id}/",
            "merged_path": f".superlooper/merged/{self.task_id}/",
            "reports_path": f".superlooper/reports/{self.task_id}/",
        }
        if platform == "claude":
            expected_paths["registered_agents_path"] = f".claude/agents/generated/superlooper/{self.task_id}/"
        for field, expected in expected_paths.items():
            value = context.get(field)
            if isinstance(value, str) and self._normalize_context_path(value) != self._normalize_context_path(expected):
                self.errors.append(f"Execution Manifest context.{field} 必须为 {expected}。")
        return platform

    def _normalize_context_path(self, value):
        return value.replace("\\", "/").rstrip("/")

    def _validate_node_payload(self, node_path, payload):
        if isinstance(payload, str):
            if not payload.strip():
                self.errors.append(f"{node_path}.payload 必须是非空字符串或 object。")
            return
        if isinstance(payload, dict):
            if not payload:
                self.errors.append(f"{node_path}.payload object 不能为空。")
            return
        self.errors.append(f"{node_path}.payload 必须是非空字符串或 object。")

    def _validate_system_payload(self, node_id, payload):
        expected_payloads = {
            "task_code_review": {
                "workspace_root": ".",
                "task_id": self.task_id,
                "outputs_path": f".superlooper/outputs/{self.task_id}/",
                "reports_path": f".superlooper/reports/{self.task_id}/",
                "execution_manifest_path": f".superlooper/manifests/{self.task_id}/execution_manifest.json",
                "design_docs_path": f".superlooper/context/{self.task_id}/design/",
                "module_split_path": f".superlooper/manifests/{self.task_id}/module-split.json",
            },
            "task_merge": {
                "workspace_root": ".",
                "task_id": self.task_id,
                "manifest_path": f".superlooper/manifests/{self.task_id}/execution_manifest.json",
                "outputs_dir": ".superlooper/outputs",
                "merged_dir": f".superlooper/merged/{self.task_id}",
                "reports_dir": f".superlooper/reports/{self.task_id}",
                "code_review_report_path": f".superlooper/reports/{self.task_id}/code_review_report.md",
            },
            "task_integration_test": {
                "workspace_root": ".",
                "task_id": self.task_id,
                "merged_path": f".superlooper/merged/{self.task_id}/",
                "reports_path": f".superlooper/reports/{self.task_id}/",
                "prd_path": f".superlooper/context/{self.task_id}/prd.md",
                "design_docs_path": f".superlooper/context/{self.task_id}/design/",
                "execution_manifest_path": f".superlooper/manifests/{self.task_id}/execution_manifest.json",
                "merge_report_path": f".superlooper/reports/{self.task_id}/merge_report.json",
                "test_workspace_path": f".superlooper/test_workspace/{self.task_id}/",
            },
            "task_apply_to_workspace": {
                "workspace_root": ".",
                "task_id": self.task_id,
                "merged_dir": f".superlooper/merged/{self.task_id}",
                "reports_dir": f".superlooper/reports/{self.task_id}",
                "merge_report_path": f".superlooper/reports/{self.task_id}/merge_report.json",
                "test_report_path": f".superlooper/reports/{self.task_id}/test_report.md",
            },
        }
        label = f"{node_id}.payload"
        expected = expected_payloads[node_id]
        if not isinstance(payload, dict):
            self.errors.append(f"{label} 必须是 object。")
            return
        for field in expected:
            if field not in payload:
                self.errors.append(f"{label} 缺少系统执行锚点：{field}")
        if payload.get("task_id") != self.task_id:
            self.errors.append(f"{label}.task_id 必须为 {self.task_id}。")
        for field, expected_value in expected.items():
            if field == "task_id" or field not in payload:
                continue
            value = payload.get(field)
            if (
                not isinstance(value, str)
                or self._normalize_context_path(value)
                != self._normalize_context_path(expected_value)
            ):
                self.errors.append(f"{label}.{field} 必须为 {expected_value}。")
        extra_fields = sorted(set(payload) - set(expected))
        if node_id == "task_apply_to_workspace":
            overwrite_fields = sorted(
                set(payload) & {"overwrite_existing", "overwrite_files"}
            )
            if overwrite_fields:
                self.errors.append(
                    f"{label} 禁止默认携带覆盖授权字段：{', '.join(overwrite_fields)}"
                )
        for field in extra_fields:
            self.errors.append(f"{label} 包含未声明字段：{field}")

    def _validate_module_payload_anchors(self, node_path, payload, module_id):
        expected_paths = {
            "design_docs_path": f".superlooper/context/{self.task_id}/design/",
            "project_profile_path": f".superlooper/context/{self.task_id}/design/project-profile.md",
            "module_split_path": f".superlooper/manifests/{self.task_id}/module-split.json",
            "execution_manifest_path": f".superlooper/manifests/{self.task_id}/execution_manifest.json",
            "output_dir": f".superlooper/outputs/{self.task_id}/{module_id}/",
            "artifact_manifest_path": f".superlooper/outputs/{self.task_id}/{module_id}/artifact_manifest.json",
        }
        if not isinstance(payload, dict):
            self.errors.append(f"{node_path}.payload 必须是 object。")
            return
        for anchor in MODULE_PAYLOAD_ANCHORS:
            if anchor not in payload:
                self.errors.append(f"{node_path}.payload 缺少模块执行锚点：{anchor}")
        if payload.get("task_id") != self.task_id:
            self.errors.append(f"{node_path}.payload.task_id 必须为 {self.task_id}。")
        if payload.get("module_id") != module_id:
            self.errors.append(f"{node_path}.payload.module_id 必须为 {module_id}。")
        for field, expected in expected_paths.items():
            value = payload.get(field)
            if isinstance(value, str) and self._normalize_context_path(value) != self._normalize_context_path(expected):
                self.errors.append(f"{node_path}.payload.{field} 必须为 {expected}。")
        module = self._module_from_module_split(module_id)
        if isinstance(module, dict):
            for field in [*UI_TRACEABILITY_FIELDS, *BROWNFIELD_MODULE_LIST_FIELDS]:
                expected = module.get(field) if isinstance(module.get(field), list) else []
                if payload.get(field) != expected:
                    self.errors.append(f"{node_path}.payload.{field} 必须与 module-split.modules[].{field} 一致。")
            expected_policy = module.get("overwrite_policy") if isinstance(module.get("overwrite_policy"), str) else "block_by_default"
            if payload.get("overwrite_policy") != expected_policy:
                self.errors.append(f"{node_path}.payload.overwrite_policy 必须与 module-split.modules[].overwrite_policy 一致。")

    def _validate_module_node_set(self, node_map):
        module_ids = self._module_ids_from_module_split()
        if module_ids is None:
            return
        manifest_module_ids = {node_id.removeprefix("mod_") for node_id in node_map if node_id.startswith("mod_")}
        missing = sorted(module_ids - manifest_module_ids)
        extra = sorted(manifest_module_ids - module_ids)
        for module_id in missing:
            self.errors.append(f"Execution Manifest 缺少 module-split 模块节点：{module_id}")
        for module_id in extra:
            self.errors.append(f"Execution Manifest 存在 module-split 未声明的模块节点：{module_id}")

    def _validate_dag_links(self, node_map):
        for node_id, node in node_map.items():
            for dependency in node.get("depends_on", []):
                if dependency not in node_map:
                    self.errors.append(f"节点 {node_id} 依赖不存在的节点：{dependency}")
        visiting = set()
        visited = set()

        def visit(node_id):
            if node_id in visiting:
                self.errors.append(f"DAG 存在循环依赖：{node_id}")
                return
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in node_map[node_id].get("depends_on", []):
                if dependency in node_map:
                    visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in node_map:
            visit(node_id)

    def _validate_system_chain(self, node_map):
        module_nodes = sorted(node_id for node_id in node_map if node_id.startswith("mod_"))
        if not module_nodes:
            self.errors.append("Execution Manifest 必须包含至少一个 mod_* 节点。")
        for node_id in SYSTEM_CHAIN:
            if node_id not in node_map:
                self.errors.append(f"Execution Manifest 缺少系统节点：{node_id}")
        if "task_code_review" in node_map:
            expected = module_nodes
            actual = sorted(node_map["task_code_review"].get("depends_on", []))
            if actual != expected:
                self.errors.append("task_code_review.depends_on 必须等于所有 mod_* 节点。")
        if "task_merge" in node_map:
            if node_map["task_merge"].get("agent") != "system_merger":
                self.errors.append("task_merge.agent 必须为 system_merger。")
            if node_map["task_merge"].get("depends_on") != ["task_code_review"]:
                self.errors.append("task_merge.depends_on 必须为 [\"task_code_review\"]。")
        if "task_integration_test" in node_map:
            if node_map["task_integration_test"].get("agent") != "tester":
                self.errors.append("task_integration_test.agent 必须为 tester。")
            if node_map["task_integration_test"].get("depends_on") != ["task_merge"]:
                self.errors.append("task_integration_test.depends_on 必须为 [\"task_merge\"]。")
        if "task_apply_to_workspace" in node_map:
            if node_map["task_apply_to_workspace"].get("agent") != "workspace_applier":
                self.errors.append("task_apply_to_workspace.agent 必须为 workspace_applier。")
            if node_map["task_apply_to_workspace"].get("depends_on") != ["task_integration_test"]:
                self.errors.append("task_apply_to_workspace.depends_on 必须为 [\"task_integration_test\"]。")

    def _validate_static_agent(self, agent):
        path = self.agents_dir / f"{agent}.md"
        if not path.exists():
            self.errors.append(f"静态 agent 文件不存在：{path}")
            return
        self._validate_agent_frontmatter(path, agent)

    def _validate_dynamic_agent(self, agent, payload=None, require_registered=True):
        runtime_path = self.runtime_agents_dir / f"{agent}.md"
        if not runtime_path.exists():
            self.errors.append(f"动态 agent 运行时源文件不存在：{runtime_path}")
            return
        self._validate_agent_frontmatter(runtime_path, agent)
        try:
            runtime_content = runtime_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.errors.append(f"动态 agent 文件内容读取失败：{agent}: {exc}")
            return
        runtime_constraints = self._validate_dynamic_agent_constraints(
            agent,
            runtime_content,
            payload,
        )
        if not require_registered:
            return
        registered_path = self.registered_agents_dir / f"{agent}.md"
        if not registered_path.exists():
            self.errors.append(f"动态 agent 注册入口不存在：{registered_path}")
            return
        registered_name = self._registered_agent_name(agent.removeprefix("module_"))
        self._validate_agent_frontmatter(registered_path, registered_name)
        try:
            registered_content = registered_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.errors.append(f"动态 agent 注册入口内容读取失败：{agent}: {exc}")
            return
        registered_constraints = self._validate_dynamic_agent_constraints(
            agent,
            registered_content,
            payload,
        )
        runtime_semantics = self._dynamic_agent_semantics(
            runtime_content,
            runtime_constraints,
        )
        registered_semantics = self._dynamic_agent_semantics(
            registered_content,
            registered_constraints,
        )
        if runtime_semantics != registered_semantics:
            self.errors.append(f"动态 agent 运行时源文件与注册入口除 name 外语义不一致：{agent}.md")

    def _validate_dynamic_agent_constraints(self, agent, content, payload):
        module_id = agent.removeprefix("module_")
        constraints = self._parse_dynamic_agent_constraints(agent, content)
        if constraints is None:
            return None
        has_task_id = "task_id" in constraints
        has_session_id = "session_id" in constraints
        if has_task_id and has_session_id:
            self.errors.append(f"动态 agent 模块约束不能同时包含 task_id 和 legacy session_id：{agent}.md")
        elif has_session_id:
            constraints = dict(constraints)
            constraints["task_id"] = constraints.pop("session_id")
        expected = self._expected_dynamic_agent_constraints(module_id, payload)
        for field in DYNAMIC_AGENT_CONSTRAINT_FIELDS:
            if field not in constraints:
                self.errors.append(f"动态 agent 模块约束缺少字段：{field}：{agent}.md")
                continue
            if not self._same_typed_value(constraints[field], expected[field]):
                self.errors.append(
                    f"动态 agent 模块约束字段值或类型不一致：{field}：{agent}.md"
                )
        return constraints

    def _parse_dynamic_agent_constraints(self, agent, content):
        if DYNAMIC_AGENT_CONSTRAINT_TITLE not in content:
            self.errors.append(f"动态 agent 缺少模块约束块：{agent}.md")
            return None
        section = content.split(DYNAMIC_AGENT_CONSTRAINT_TITLE, 1)[1]
        match = re.search(r"```ya?ml\s*\n(.*?)\n```", section, re.DOTALL)
        if match is None:
            self.errors.append(f"动态 agent 模块约束块缺少 yaml 代码块：{agent}.md")
            return None
        constraints = {}
        for line in match.group(1).splitlines():
            if not line.strip():
                continue
            if line.startswith((" ", "\t")) or ":" not in line:
                self.errors.append(f"动态 agent 模块约束必须使用顶层 JSON 兼容 YAML：{agent}.md")
                return None
            field, raw_value = line.split(":", 1)
            field = field.strip()
            if field in constraints:
                self.errors.append(f"动态 agent 模块约束字段重复：{field}：{agent}.md")
                return None
            try:
                constraints[field] = json.loads(raw_value.strip())
            except json.JSONDecodeError:
                self.errors.append(
                    f"动态 agent 模块约束字段不是 JSON 兼容值：{field}：{agent}.md"
                )
                return None
        return constraints

    def _expected_dynamic_agent_constraints(self, module_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        expected = {
            "task_id": self.task_id,
            "module_id": module_id,
            "forbidden_inputs": payload.get("forbidden_inputs", []),
            "forbidden_outputs": payload.get("forbidden_outputs", []),
        }
        for field in DYNAMIC_AGENT_CONSTRAINT_FIELDS:
            if field in expected:
                continue
            if field == "overwrite_policy":
                expected[field] = payload.get(field) or "block_by_default"
            else:
                expected[field] = payload.get(field, [])
        return expected

    def _same_typed_value(self, actual, expected):
        if type(actual) is not type(expected):
            return False
        if isinstance(expected, list):
            return len(actual) == len(expected) and all(
                self._same_typed_value(actual_item, expected_item)
                for actual_item, expected_item in zip(actual, expected)
            )
        if isinstance(expected, dict):
            return actual.keys() == expected.keys() and all(
                self._same_typed_value(actual[key], expected[key])
                for key in expected
            )
        return actual == expected

    def _dynamic_agent_semantics(self, content, constraints):
        frontmatter, body = self._parse_agent_document(content)
        if frontmatter is None:
            return None
        frontmatter = dict(frontmatter)
        frontmatter.pop("name", None)
        body_without_constraints = body.split(DYNAMIC_AGENT_CONSTRAINT_TITLE, 1)[0].rstrip()
        return frontmatter, body_without_constraints, constraints

    def _registered_agent_name(self, module_id):
        task_hash = hashlib.sha256(self.task_id.encode("utf-8")).hexdigest()[:16]
        return f"module_{module_id}__task_{task_hash}"

    def _validate_agent_frontmatter(self, path, expected_name):
        name = self._frontmatter_name(path)
        if name != expected_name:
            self.errors.append(f"agent frontmatter name 必须为 {expected_name}：{path}")

    def _frontmatter_name(self, path):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.errors.append(f"agent 文件读取失败：{path}: {exc}")
            return None
        frontmatter, _ = self._parse_agent_document(content)
        if frontmatter is None:
            return None
        return frontmatter.get("name")

    def _parse_agent_document(self, content):
        lines = content.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            return None, content
        frontmatter = {}
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return frontmatter, "".join(lines[index + 1 :])
            if ":" not in line:
                return None, content
            field, raw_value = line.split(":", 1)
            raw_value = raw_value.strip()
            try:
                frontmatter[field.strip()] = json.loads(raw_value)
            except json.JSONDecodeError:
                frontmatter[field.strip()] = raw_value.strip("'\"")
        return None, content

    def _module_ids_from_manifest(self, manifest):
        if not manifest:
            return []
        nodes = manifest.get("dag", {}).get("nodes", [])
        return [node["id"].removeprefix("mod_") for node in nodes if isinstance(node, dict) and isinstance(node.get("id"), str) and node["id"].startswith("mod_")]

    def _module_ids_from_module_split(self):
        if not self.module_split_path.exists():
            return None
        data = self._read_json(self.module_split_path)
        if not isinstance(data, dict):
            return None
        modules = data.get("modules")
        if not isinstance(modules, list):
            return None
        return {module["id"] for module in modules if isinstance(module, dict) and isinstance(module.get("id"), str) and MODULE_PATTERN.match(module["id"])}

    def _module_from_module_split(self, module_id):
        if not self.module_split_path.exists():
            return None
        data = self._read_json(self.module_split_path)
        if not isinstance(data, dict):
            return None
        modules = data.get("modules")
        if not isinstance(modules, list):
            return None
        for module in modules:
            if isinstance(module, dict) and module.get("id") == module_id:
                return module
        return None

    def _expected_ui_acceptance_refs_from_module_split(self):
        if not self.module_split_path.exists():
            return []
        data = self._read_json(self.module_split_path)
        if not isinstance(data, dict):
            return []
        modules = data.get("modules")
        if not isinstance(modules, list):
            return []
        refs = []
        for module in modules:
            if not isinstance(module, dict):
                continue
            values = module.get("ui_acceptance_refs")
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str) and value.strip():
                    refs.append(value.strip())
        return sorted(set(refs))

    def _read_markdown_body_without_first_yaml_block(self, path):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            self.errors.append(f"报告读取失败：{path}: {exc}")
            return ""

        in_yaml = False
        yaml_done = False
        body = []

        for line in lines:
            stripped = line.strip()
            if not yaml_done and not in_yaml and stripped in ("```yaml", "```yml"):
                in_yaml = True
                continue
            if in_yaml and stripped == "```":
                in_yaml = False
                yaml_done = True
                continue
            if in_yaml:
                continue
            if yaml_done:
                body.append(line)

        if not yaml_done:
            return "\n".join(lines)
        return "\n".join(body)

    def _validate_ui_acceptance_refs_in_report_body(self, label, report_path, evidence_keywords):
        expected_refs = self._expected_ui_acceptance_refs_from_module_split()
        if not expected_refs:
            return

        body = self._read_markdown_body_without_first_yaml_block(report_path)
        body_lines = [line.strip() for line in body.splitlines() if line.strip()]
        missing = []

        for ref in expected_refs:
            matched = False
            for line in body_lines:
                if ref not in line:
                    continue
                lower_line = line.lower()
                if any(keyword in lower_line for keyword in evidence_keywords):
                    matched = True
                    break
            if not matched:
                missing.append(ref)

        if missing:
            self.errors.append(f"{label} 正文缺少 UI 验收证据：{', '.join(missing)}。")

    def _target_files_by_module(self):
        data = self._read_json(self.module_split_path) if self.module_split_path.exists() else None
        if not isinstance(data, dict):
            return {}, False
        java_project = self._is_java_project(data.get("project_profile"))
        result = {}
        modules = data.get("modules")
        if not isinstance(modules, list):
            return result, java_project
        for module in modules:
            if isinstance(module, dict) and isinstance(module.get("id"), str):
                target_files = module.get("target_files")
                if isinstance(target_files, list):
                    result[module["id"]] = [item for item in target_files if isinstance(item, str)]
        return result, java_project

    def _validate_traceability_refs(self, module_path, module):
        self._validate_ref_array(module_path, module, "requirement_refs", REQ_REF_PATTERN)
        self._validate_ref_array(module_path, module, "decision_refs", DEC_REF_PATTERN)
        self._validate_ref_array(module_path, module, "open_question_refs", OPEN_REF_PATTERN)
        self._validate_ref_array(module_path, module, "acceptance_refs", AC_REF_PATTERN)
        for field in UI_TRACEABILITY_FIELDS:
            self._validate_non_empty_string_array(module_path, module, field)
        self._validate_non_empty_string_array(module_path, module, "test_focus")
        self._validate_module_ref_array(module_path, module, "depends_on_modules")

    def _validate_brownfield_boundaries(self, module_path, module, target_files):
        for field in BROWNFIELD_MODULE_LIST_FIELDS:
            self._validate_non_empty_string_array(module_path, module, field)
        for field in ["allowed_existing_files", "forbidden_files"]:
            values = module.get(field)
            if not isinstance(values, list):
                continue
            for index, value in enumerate(values):
                if isinstance(value, str) and value.strip() and not self._safe_relative_path(value):
                    self.errors.append(f"{module_path}.{field}[{index}] 不是安全相对路径：{value}")
        target_set = {
            windows_path_key(value)
            for value in (target_files or [])
            if isinstance(value, str)
        }
        allowed_existing_files = module.get("allowed_existing_files")
        if isinstance(allowed_existing_files, list):
            extra = sorted(
                value
                for value in allowed_existing_files
                if isinstance(value, str)
                and windows_path_key(value) not in target_set
            )
            if extra:
                self.errors.append(f"{module_path}.allowed_existing_files 必须是 target_files 子集：{', '.join(extra)}")
        forbidden_files = module.get("forbidden_files")
        if isinstance(forbidden_files, list):
            overlap = sorted(
                value
                for value in forbidden_files
                if isinstance(value, str)
                and windows_path_key(value) in target_set
            )
            if overlap:
                self.errors.append(f"{module_path}.forbidden_files 不能与 target_files 重叠：{', '.join(overlap)}")
        overwrite_policy = module.get("overwrite_policy")
        if overwrite_policy is not None and overwrite_policy != "block_by_default":
            self.errors.append(f"{module_path}.overwrite_policy 只允许 block_by_default。")

    def _validate_ref_array(self, module_path, module, field, pattern):
        values = module.get(field)
        if values is None:
            return
        if not isinstance(values, list):
            self.errors.append(f"{module_path}.{field} 必须是数组。")
            return
        for index, value in enumerate(values):
            if not isinstance(value, str) or not pattern.match(value):
                self.errors.append(f"{module_path}.{field}[{index}] 编号格式不合法：{value}")

    def _validate_non_empty_string_array(self, module_path, module, field):
        values = module.get(field)
        if values is None:
            return
        if not isinstance(values, list):
            self.errors.append(f"{module_path}.{field} 必须是数组。")
            return
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value.strip():
                self.errors.append(f"{module_path}.{field}[{index}] 必须是非空字符串。")

    def _validate_module_ref_array(self, module_path, module, field):
        values = module.get(field)
        if values is None:
            return
        if not isinstance(values, list):
            self.errors.append(f"{module_path}.{field} 必须是数组。")
            return
        module_id = module.get("id")
        for index, value in enumerate(values):
            if not isinstance(value, str) or not MODULE_PATTERN.match(value):
                self.errors.append(f"{module_path}.{field}[{index}] 模块 ID 格式不合法：{value}")
            elif value in RESERVED_PLACEHOLDER_MODULE_IDS:
                self.errors.append(f"{module_path}.{field}[{index}] 不能使用无业务语义的占位命名：{value}")
            elif value == module_id:
                self.errors.append(f"{module_path}.{field}[{index}] 不能依赖自身：{value}")

    def _validate_module_dependencies(self, modules):
        module_ids = {module.get("id") for module in modules if isinstance(module, dict) and isinstance(module.get("id"), str)}
        for index, module in enumerate(modules):
            if not isinstance(module, dict):
                continue
            values = module.get("depends_on_modules")
            if values is None or not isinstance(values, list):
                continue
            for value_index, value in enumerate(values):
                if isinstance(value, str) and MODULE_PATTERN.match(value) and value not in module_ids:
                    self.errors.append(f"module-split.modules[{index}].depends_on_modules[{value_index}] 依赖不存在的模块：{value}")

    def _validate_file_roles(self, module_path, file_roles, target_files):
        if not isinstance(file_roles, list):
            self.errors.append(f"{module_path}.file_roles 必须是数组。")
            return
        target_paths = {
            windows_path_key(path): path
            for path in (target_files or [])
            if isinstance(path, str)
        }
        role_paths = set()
        for index, item in enumerate(file_roles):
            label = f"{module_path}.file_roles[{index}]"
            if not isinstance(item, dict):
                self.errors.append(f"{label} 必须是 object。")
                continue
            path = item.get("path")
            role = item.get("role")
            path_key = windows_path_key(path) if isinstance(path, str) else None
            if path_key is not None:
                role_paths.add(path_key)
            if not self._safe_relative_path(path):
                self.errors.append(f"{label}.path 不是安全相对路径：{path}")
            if role not in JAVA_FILE_ROLES:
                self.errors.append(f"{label}.role 不合法：{role}")
            if target_paths and path_key not in target_paths:
                self.errors.append(f"{label}.path 必须包含在同模块 target_files 中：{path}")
        if target_paths:
            missing_roles = sorted(target_paths.keys() - role_paths)
            for path_key in missing_roles:
                self.errors.append(f"{module_path}.target_files 缺少 file_roles 声明：{target_paths[path_key]}")

    def validate_code_review_report(self, required=False, require_pass=False):
        report_path = self.reports_dir / "code_review_report.md"
        if not report_path.exists():
            if required:
                self.errors.append(f"code_review_report.md 不存在：{report_path}")
            return
        data = self._read_first_yaml_block(report_path)
        if not isinstance(data, dict):
            return
        label = "code_review_report"
        status = data.get("code_review_status")
        if status not in ("PASS", "FAIL"):
            self.errors.append(f"{label}.code_review_status 必须为 PASS 或 FAIL。")
        elif require_pass and status != "PASS":
            self.errors.append(f"{label}.code_review_status 必须为 PASS 才能进入 apply。")
        if data.get("task_id") != self.task_id:
            self.errors.append(f"{label}.task_id 与当前 task_id 不一致。")
        expected_report_path = f".superlooper/reports/{self.task_id}/code_review_report.md"
        report_path_value = data.get("report_path")
        if not isinstance(report_path_value, str) or not report_path_value.strip():
            self.errors.append(f"{label}.report_path 必须是非空字符串。")
        elif self._normalize_context_path(report_path_value) != self._normalize_context_path(expected_report_path):
            self.errors.append(f"{label}.report_path 必须为 {expected_report_path}。")
        blocker_count = self._yaml_int(data, "blocker_count", label)
        blocking_major_count = self._yaml_int(data, "blocking_major_count", label)
        if status == "PASS":
            if blocker_count != 0:
                self.errors.append(f"{label}.code_review_status=PASS 时 blocker_count 必须为 0。")
            if blocking_major_count != 0:
                self.errors.append(f"{label}.code_review_status=PASS 时 blocking_major_count 必须为 0。")
        reviewed_modules = data.get("reviewed_modules")
        if not isinstance(reviewed_modules, list):
            self.errors.append(f"{label}.reviewed_modules 必须是数组。")
            return
        if status != "PASS":
            return
        if not reviewed_modules:
            self.errors.append(
                f"{label}.reviewed_modules 在 code_review_status=PASS 时必须非空。"
            )
        duplicates = sorted(
            module_id
            for module_id in set(reviewed_modules)
            if reviewed_modules.count(module_id) > 1
        )
        if duplicates:
            self.errors.append(
                f"{label}.reviewed_modules 包含重复模块：{', '.join(duplicates)}"
            )
        manifest = self.validate_execution_manifest(required=True)
        module_ids = set(self._module_ids_from_manifest(manifest))
        reviewed = set(reviewed_modules)
        missing = sorted(module_ids - reviewed)
        extra = sorted(reviewed - module_ids)
        if missing:
            self.errors.append(f"{label}.reviewed_modules 缺少模块：{', '.join(missing)}")
        if extra:
            self.errors.append(f"{label}.reviewed_modules 包含非 Manifest 模块：{', '.join(extra)}")

    def validate_test_report(self, required=False):
        report_path = self.reports_dir / "test_report.md"
        if not report_path.exists():
            if required:
                self.errors.append(f"test_report.md 不存在：{report_path}")
            return
        data = self._read_first_yaml_block(report_path)
        if not isinstance(data, dict):
            return
        label = "test_report"
        status = data.get("test_status")
        if status not in ("PASS", "FAIL"):
            self.errors.append(f"{label}.test_status 必须为 PASS 或 FAIL。")
        if data.get("task_id") != self.task_id:
            self.errors.append(f"{label}.task_id 与当前 task_id 不一致。")
        expected_tested_path = f".superlooper/merged/{self.task_id}"
        tested_path = data.get("tested_path")
        if not isinstance(tested_path, str) or not tested_path.strip():
            self.errors.append(f"{label}.tested_path 必须是非空字符串。")
        elif self._normalize_context_path(tested_path) != self._normalize_context_path(expected_tested_path):
            self.errors.append(f"{label}.tested_path 必须为 .superlooper/merged/{self.task_id}/。")
        expected_merge_report = f".superlooper/reports/{self.task_id}/merge_report.json"
        merge_report_path = data.get("merge_report_path")
        if not isinstance(merge_report_path, str) or not merge_report_path.strip():
            self.errors.append(f"{label}.merge_report_path 必须是非空字符串。")
        elif self._normalize_context_path(merge_report_path) != self._normalize_context_path(expected_merge_report):
            self.errors.append(f"{label}.merge_report_path 必须为 {expected_merge_report}。")
        expected_report_path = f".superlooper/reports/{self.task_id}/test_report.md"
        report_path_value = data.get("report_path")
        if not isinstance(report_path_value, str) or not report_path_value.strip():
            self.errors.append(f"{label}.report_path 必须是非空字符串。")
        elif self._normalize_context_path(report_path_value) != self._normalize_context_path(expected_report_path):
            self.errors.append(f"{label}.report_path 必须为 {expected_report_path}。")
        if status != "PASS":
            self.errors.append(f"{label}.test_status 必须为 PASS 才能进入 apply。")
        else:
            evidence = self._read_first_json_block(report_path, label)
            if isinstance(evidence, dict):
                self._validate_test_evidence(evidence)
        self._validate_ui_acceptance_refs_in_report_body(
            label,
            report_path,
            {
                "pass",
                "passed",
                "covered",
                "coverage",
                "verified",
                "通过",
                "覆盖",
                "已覆盖",
                "验证",
                "已验证",
            },
        )

    def validate_apply_report(self, required=False):
        apply_report = self.reports_dir / "apply_report.json"
        conflict_report = self.reports_dir / "apply_conflict_report.json"
        if conflict_report.exists():
            self.errors.append(f"存在应用冲突报告，禁止输出最终完成结论：{conflict_report}")
        if not apply_report.exists():
            if required:
                self.errors.append(f"apply_report.json 不存在：{apply_report}")
            return
        report = self._read_json(apply_report)
        if not isinstance(report, dict):
            return
        if report.get("status") != "success":
            self.errors.append("apply_report.status 必须为 success。")
        if report.get("task_id") != self.task_id:
            self.errors.append("apply_report.task_id 与当前 task_id 不一致。")
        self._validate_snapshot_digest_chain(report)
        validation = report.get("workspace_validation")
        if not isinstance(validation, dict):
            self.errors.append("apply_report.workspace_validation 必须是 object。")
            return
        if validation.get("status") != "PASS":
            self.errors.append("apply_report.workspace_validation.status 必须为 PASS。")
        checked_count = validation.get("checked_file_count")
        matched_count = validation.get("matched_file_count")
        failed_count = validation.get("failed_file_count")
        if not isinstance(checked_count, int) or checked_count < 0:
            self.errors.append("apply_report.workspace_validation.checked_file_count 必须是非负整数。")
        if not isinstance(matched_count, int) or matched_count < 0:
            self.errors.append("apply_report.workspace_validation.matched_file_count 必须是非负整数。")
        if not isinstance(failed_count, int) or failed_count < 0:
            self.errors.append("apply_report.workspace_validation.failed_file_count 必须是非负整数。")
        elif failed_count != 0:
            self.errors.append("apply_report.workspace_validation.failed_file_count 必须为 0。")
        failures = validation.get("failures")
        if not isinstance(failures, list):
            self.errors.append("apply_report.workspace_validation.failures 必须是数组。")
        elif failures:
            self.errors.append("apply_report.workspace_validation.failures 必须为空。")

    def _validate_snapshot_digest_chain(self, apply_report):
        apply_digest = apply_report.get("snapshot_digest")
        if not isinstance(apply_digest, str) or not SNAPSHOT_DIGEST_PATTERN.fullmatch(apply_digest):
            self.errors.append(
                "apply_report.snapshot_digest 必须匹配 sha256:<64 lowercase hex>。"
            )

        merge_report_path = self.reports_dir / "merge_report.json"
        if not merge_report_path.exists():
            self.errors.append(f"merge_report.json 不存在：{merge_report_path}")
            return
        merge_report = self._read_json(merge_report_path)
        if not isinstance(merge_report, dict):
            return
        if merge_report.get("status") != "success":
            self.errors.append("merge_report.status 必须为 success。")
        if merge_report.get("task_id") != self.task_id:
            self.errors.append("merge_report.task_id 与当前 task_id 不一致。")

        merge_digest = merge_report.get("snapshot_digest")
        if not isinstance(merge_digest, str) or not SNAPSHOT_DIGEST_PATTERN.fullmatch(merge_digest):
            self.errors.append(
                "merge_report.snapshot_digest 必须匹配 sha256:<64 lowercase hex>。"
            )
            return

        merged_dir = self.root / ".superlooper" / "merged" / self.task_id
        if not merged_dir.is_dir():
            self.errors.append(f"merged tree 不存在：{merged_dir}")
            return
        try:
            actual_digest = compute_tree_digest(merged_dir)
        except OSError as exc:
            self.errors.append(f"merged tree snapshot_digest 计算失败：{exc}")
            return
        if merge_digest != actual_digest:
            self.errors.append(
                "merge_report.snapshot_digest 与 merged tree 不一致："
                f"expected={merge_digest}, actual={actual_digest}"
            )
        if isinstance(apply_digest, str) and apply_digest != merge_digest:
            self.errors.append(
                "apply_report.snapshot_digest 与 merge_report.snapshot_digest 不一致。"
            )

    def validate_initialization_advice(self, required=False):
        advice_path = (
            self.root
            / ".superlooper"
            / "context"
            / self.task_id
            / "design"
            / "initialization-advice.md"
        )
        if not advice_path.exists():
            if required:
                self.errors.append(f"initialization-advice.md 不存在：{advice_path}")
            return None
        data = self._read_first_yaml_block(advice_path)
        if not isinstance(data, dict):
            return None
        label = "initialization_advice"
        for field in (
            "task_id",
            "project_category",
            "project_version",
            "project_root",
        ):
            self._require_string(data, field, label)
        if data.get("task_id") != self.task_id:
            self.errors.append(f"{label}.task_id 与当前 task_id 不一致。")
        category = data.get("project_category")
        if category not in INTERACTION_INITIALIZATION_OPTIONS:
            self.errors.append(f"{label}.project_category 不合法。")
        version = data.get("project_version")
        if (
            category in INTERACTION_INITIALIZATION_OPTIONS
            and version not in INTERACTION_INITIALIZATION_OPTIONS[category]
        ):
            self.errors.append(f"{label}.project_version 不属于对应分类。")
        project_root = data.get("project_root")
        if (
            isinstance(project_root, str)
            and project_root
            and project_root != "."
            and not self._safe_relative_path(project_root, allow_protected=False)
        ):
            self.errors.append(f"{label}.project_root 必须是安全相对路径。")
        return data

    def validate_initialization_report(self, required=False):
        report_path = self.reports_dir / "initialization_report.json"
        if not report_path.exists():
            if required:
                self.errors.append(f"initialization_report.json 不存在：{report_path}")
            return None
        report = self._read_json(report_path)
        if not isinstance(report, dict):
            return None
        if report.get("task_id") != self.task_id:
            self.errors.append("initialization_report.task_id 与当前 task_id 不一致。")
        if report.get("status") != "success":
            self.errors.append("initialization_report.status 必须为 success。")
        category = report.get("project_category")
        if category not in INTERACTION_INITIALIZATION_OPTIONS:
            self.errors.append("initialization_report.project_category 不合法。")
        version = report.get("project_version")
        if category in INTERACTION_INITIALIZATION_OPTIONS and version not in INTERACTION_INITIALIZATION_OPTIONS[category]:
            self.errors.append("initialization_report.project_version 不属于对应分类。")
        project_root = report.get("project_root")
        if project_root != "." and not self._safe_relative_path(project_root, allow_protected=False):
            self.errors.append("initialization_report.project_root 必须是安全相对路径。")
        created_paths = report.get("created_paths")
        if not isinstance(created_paths, list) or not created_paths:
            self.errors.append("initialization_report.created_paths 必须是非空数组。")
        elif any(not self._safe_relative_path(path, allow_protected=False) for path in created_paths):
            self.errors.append("initialization_report.created_paths 必须全部为安全相对路径。")
        return report

    def validate_requirement_alignment_report(self, required=False):
        report_path = self.reports_dir / "requirement_alignment_report.md"
        if not report_path.exists():
            if required:
                self.errors.append(f"requirement_alignment_report 不存在：{report_path}")
            return None
        data = self._read_first_yaml_block(report_path)
        if not isinstance(data, dict):
            return None
        status = data.get("requirement_alignment_status")
        if status not in ("PASS", "FAIL"):
            self.errors.append("requirement_alignment_status 必须为 PASS 或 FAIL。")
        if data.get("task_id") != self.task_id:
            self.errors.append("requirement_alignment_report.task_id 与当前 task_id 不一致。")
        expected_prd = f".superlooper/context/{self.task_id}/prd.md"
        expected_test = f".superlooper/reports/{self.task_id}/test_report.md"
        expected_apply = f".superlooper/reports/{self.task_id}/apply_report.json"
        expected_report = f".superlooper/reports/{self.task_id}/requirement_alignment_report.md"
        expected_paths = {
            "prd_path": expected_prd,
            "test_report_path": expected_test,
            "apply_report_path": expected_apply,
            "report_path": expected_report,
        }
        for field, expected in expected_paths.items():
            value = data.get(field)
            if not isinstance(value, str) or self._normalize_context_path(value) != self._normalize_context_path(expected):
                self.errors.append(f"requirement_alignment_report.{field} 必须为 {expected}。")
        unmet = self._yaml_int(data, "unmet_requirement_count", "requirement_alignment_report")
        unchecked = self._yaml_int(data, "unchecked_acceptance_count", "requirement_alignment_report")
        if status == "PASS" and unmet != 0:
            self.errors.append("requirement_alignment_report PASS 时 unmet_requirement_count 必须为 0。")
        if status == "PASS" and unchecked != 0:
            self.errors.append("requirement_alignment_report PASS 时 unchecked_acceptance_count 必须为 0。")
        if status == "PASS":
            evidence = self._read_first_json_block(
                report_path,
                "requirement_alignment_report",
            )
            if isinstance(evidence, dict):
                self._validate_requirement_alignment_evidence(evidence)
        self._validate_ui_acceptance_refs_in_report_body(
            "requirement_alignment_report",
            report_path,
            {
                "pass",
                "passed",
                "aligned",
                "verified",
                "covered",
                "test_report",
                "apply_report",
                "通过",
                "满足",
                "校对",
                "已校对",
                "覆盖",
                "已覆盖",
                "验证",
                "已验证",
            },
        )
        return data

    def validate_execution_summary(self, required=False):
        report_path = self.reports_dir / "execution_summary.md"
        if not report_path.exists():
            if required:
                self.errors.append(f"execution_summary.md 不存在：{report_path}")
            return None
        data = self._read_first_yaml_block(report_path)
        if not isinstance(data, dict):
            return None
        label = "execution_summary"
        status = data.get("execution_summary_status")
        if status not in EXECUTION_SUMMARY_STATUSES:
            self.errors.append(f"{label}.execution_summary_status 不合法：{status}")
        if data.get("task_id") != self.task_id:
            self.errors.append(f"{label}.task_id 与当前 task_id 不一致。")
        workflow_mode = data.get("workflow_mode")
        if workflow_mode not in WORKFLOW_MODES:
            self.errors.append(f"{label}.workflow_mode 必须为 standard 或 strict_review。")
        category = data.get("project_category")
        if category not in INTERACTION_INITIALIZATION_OPTIONS:
            self.errors.append(f"{label}.project_category 不合法。")
        version = data.get("project_version")
        if category in INTERACTION_INITIALIZATION_OPTIONS and version not in INTERACTION_INITIALIZATION_OPTIONS[category]:
            self.errors.append(f"{label}.project_version 不属于对应分类。")
        module_count = self._yaml_int(data, "module_count", label)
        target_file_count = self._yaml_int(data, "target_file_count", label)
        risk_count = self._yaml_int(data, "risk_count", label)
        if module_count is not None and module_count < 1:
            self.errors.append(f"{label}.module_count 必须大于 0。")
        if target_file_count is not None and target_file_count < 0:
            self.errors.append(f"{label}.target_file_count 必须为非负整数。")
        if risk_count is not None and risk_count < 0:
            self.errors.append(f"{label}.risk_count 必须为非负整数。")
        if not isinstance(data.get("blocking_decisions"), list):
            self.errors.append(f"{label}.blocking_decisions 必须是数组。")
        upstream_alignment_status = data.get("upstream_alignment_status")
        if upstream_alignment_status not in ALIGNMENT_STATUSES:
            self.errors.append(f"{label}.upstream_alignment_status 必须为 PASS、FAIL 或 BLOCKED。")
        self._yaml_bool(data, "module_split_validated", label)
        self._yaml_bool(data, "execution_manifest_validated", label)
        expected_report = f".superlooper/reports/{self.task_id}/execution_summary.md"
        value = data.get("report_path")
        if not isinstance(value, str) or self._normalize_context_path(value) != self._normalize_context_path(expected_report):
            self.errors.append(f"{label}.report_path 必须为 {expected_report}。")
        if status == "READY_FOR_APPROVAL":
            if upstream_alignment_status != "PASS":
                self.errors.append(f"{label}.READY_FOR_APPROVAL 时 upstream_alignment_status 必须为 PASS。")
            if data.get("module_split_validated") not in (True, "true"):
                self.errors.append(f"{label}.READY_FOR_APPROVAL 时 module_split_validated 必须为 true。")
            if data.get("execution_manifest_validated") not in (True, "true"):
                self.errors.append(f"{label}.READY_FOR_APPROVAL 时 execution_manifest_validated 必须为 true。")
        return data

    def validate_upstream_alignment(self, required=False):
        report_path = self.reports_dir / "upstream_alignment.md"
        if not report_path.exists():
            if required:
                self.errors.append(f"upstream_alignment.md 不存在：{report_path}")
            return None
        data = self._read_first_yaml_block(report_path)
        if not isinstance(data, dict):
            return None
        self._validate_upstream_alignment_data(data, "upstream_alignment", f".superlooper/reports/{self.task_id}/upstream_alignment.md")
        return data

    def _validate_upstream_alignment_data(self, data, label, expected_report_path=None):
        status = data.get("upstream_alignment_status")
        if status not in ALIGNMENT_STATUSES:
            self.errors.append(f"{label}.upstream_alignment_status 必须为 PASS、FAIL 或 BLOCKED。")
        if data.get("task_id") != self.task_id:
            self.errors.append(f"{label}.task_id 与当前 task_id 不一致。")
        mismatch_count = self._yaml_int(data, "mismatch_count", label)
        if mismatch_count is not None and mismatch_count < 0:
            self.errors.append(f"{label}.mismatch_count 必须为非负整数。")
        loop_required_valid = self._yaml_bool(data, "loop_required", label)
        blocking_decisions = data.get("blocking_decisions")
        if not isinstance(blocking_decisions, list):
            self.errors.append(f"{label}.blocking_decisions 必须是数组。")
            blocking_decisions = []
        loop_target_phase = data.get("loop_target_phase")
        if loop_target_phase not in ALIGNMENT_LOOP_TARGET_PHASES:
            self.errors.append(f"{label}.loop_target_phase 不合法。")
        if expected_report_path is not None:
            report_path_value = data.get("report_path")
            if not isinstance(report_path_value, str) or self._normalize_context_path(report_path_value) != self._normalize_context_path(expected_report_path):
                self.errors.append(f"{label}.report_path 必须为 {expected_report_path}。")
        if status == "PASS" and mismatch_count != 0:
            self.errors.append(f"{label}.PASS 时 mismatch_count 必须为 0。")
        if status == "FAIL" and loop_required_valid and data.get("loop_required") not in (True, "true"):
            self.errors.append(f"{label}.FAIL 时 loop_required 必须为 true。")
        if status == "BLOCKED" and not blocking_decisions:
            self.errors.append(f"{label}.BLOCKED 时 blocking_decisions 必须非空。")

    def validate_change_impact_report(self, required=False):
        report_path = self.reports_dir / "change_impact_report.md"
        if not report_path.exists():
            if required:
                self.errors.append(f"change_impact_report 不存在：{report_path}")
            return None
        data = self._read_first_yaml_block(report_path)
        if not isinstance(data, dict):
            return None
        status = data.get("change_impact_status")
        if status not in ("PASS", "FAIL"):
            self.errors.append("change_impact_status 必须为 PASS 或 FAIL。")
        if data.get("task_id") != self.task_id:
            self.errors.append("change_impact_report.task_id 与当前 task_id 不一致。")
        rollback_target_phase = data.get("rollback_target_phase")
        if rollback_target_phase not in ("prd", "ui_design", "design", "initialization", "run", "requirement_alignment"):
            self.errors.append("change_impact_report.rollback_target_phase 不合法。")
        for field in ("requires_reinitialization", "local_rerun_allowed", "manual_approval_required"):
            self._yaml_bool(data, field, "change_impact_report")
        if data.get("requires_reinitialization") in (True, "true"):
            if data.get("local_rerun_allowed") in (True, "true"):
                self.errors.append(
                    "change_impact_report.requires_reinitialization=true 时 local_rerun_allowed 必须为 false。"
                )
            if rollback_target_phase in ("run", "requirement_alignment"):
                self.errors.append(
                    "change_impact_report.requires_reinitialization=true 时 rollback_target_phase 必须回到 prd、design 或 initialization。"
                )
        affected_artifacts = data.get("affected_artifacts")
        if not isinstance(affected_artifacts, list):
            self.errors.append("change_impact_report.affected_artifacts 必须是数组。")
        else:
            for index, value in enumerate(affected_artifacts):
                if not self._safe_relative_path(value, allow_protected=True):
                    self.errors.append(f"change_impact_report.affected_artifacts[{index}] 不是安全相对路径：{value}")
        affected_modules = data.get("affected_modules")
        module_ids = self._module_ids_from_module_split()
        if not isinstance(affected_modules, list):
            self.errors.append("change_impact_report.affected_modules 必须是数组。")
        else:
            for index, value in enumerate(affected_modules):
                if not isinstance(value, str) or not MODULE_PATTERN.match(value):
                    self.errors.append(f"change_impact_report.affected_modules[{index}] 模块 ID 格式不合法：{value}")
                elif module_ids is not None and value not in module_ids:
                    self.errors.append(f"change_impact_report.affected_modules[{index}] 不存在于 module-split：{value}")
            if data.get("local_rerun_allowed") in (True, "true"):
                if not affected_modules:
                    self.errors.append(
                        "change_impact_report.affected_modules 在 local_rerun_allowed=true 时必须非空。"
                    )
                duplicates = sorted(
                    module_id
                    for module_id in set(affected_modules)
                    if affected_modules.count(module_id) > 1
                )
                if duplicates:
                    self.errors.append(
                        "change_impact_report.affected_modules 包含重复模块："
                        + ", ".join(duplicates)
                    )
                manifest = self.validate_execution_manifest(required=True)
                manifest_module_ids = set(self._module_ids_from_manifest(manifest))
                extra = sorted(set(affected_modules) - manifest_module_ids)
                if extra:
                    self.errors.append(
                        "change_impact_report.affected_modules 包含非 Execution Manifest 模块："
                        + ", ".join(extra)
                    )
        expected_report = f".superlooper/reports/{self.task_id}/change_impact_report.md"
        value = data.get("report_path")
        if not isinstance(value, str) or self._normalize_context_path(value) != self._normalize_context_path(expected_report):
            self.errors.append(f"change_impact_report.report_path 必须为 {expected_report}。")
        return data

    def validate_ui_artifacts(self, required=False):
        ui_dir = self.root / ".superlooper" / "context" / self.task_id / "ui"
        if not ui_dir.exists():
            if required:
                self.errors.append(f"UI 产物目录不存在：{ui_dir}")
            return None
        for filename in UI_REQUIRED_FILES:
            path = ui_dir / filename
            if not path.exists():
                self.errors.append(f"UI 固定产物不存在：{path}")
        ui_spec_path = ui_dir / "ui-spec.md"
        if ui_spec_path.exists():
            data = self._read_first_yaml_block(ui_spec_path)
            if isinstance(data, dict):
                for field in UI_SPEC_REQUIRED_FIELDS:
                    if field not in data:
                        self.errors.append(f"ui-spec 缺少状态字段：{field}")
                if data.get("task_id") != self.task_id:
                    self.errors.append("ui-spec.task_id 与当前 task_id 不一致。")
                ui_status = data.get("ui_status")
                if ui_status not in UI_STATUSES:
                    self.errors.append(f"ui-spec.ui_status 不合法：{ui_status}")
                project_mode = data.get("project_mode")
                if project_mode == "new_project":
                    self.errors.append("ui-spec.project_mode 禁止使用 new_project，必须使用 greenfield 或 brownfield。")
                if self.state_path.exists():
                    state = self._read_json(self.state_path)
                    if isinstance(state, dict) and isinstance(project_mode, str) and project_mode != state.get("project_mode"):
                        self.errors.append("ui-spec.project_mode 必须与 session state.project_mode 一致。")
                expected_prd = f".superlooper/context/{self.task_id}/prd.md"
                expected_ui_dir = f".superlooper/context/{self.task_id}/ui/"
                expected_preview = f".superlooper/context/{self.task_id}/ui/preview.html"
                expected_paths = {
                    "prd_path": expected_prd,
                    "ui_output_dir": expected_ui_dir,
                    "preview_path": expected_preview,
                }
                for field, expected in expected_paths.items():
                    value = data.get(field)
                    if not isinstance(value, str) or self._normalize_context_path(value) != self._normalize_context_path(expected):
                        self.errors.append(f"ui-spec.{field} 必须为 {expected}。")
                self._yaml_int(data, "page_count", "ui-spec")
                self._yaml_int(data, "interaction_count", "ui-spec")
                self._yaml_int(data, "unresolved_ui_decision_count", "ui-spec")
                self._yaml_bool(data, "existing_frontend", "ui-spec")
        preview_path = ui_dir / "preview.html"
        if preview_path.exists():
            content = preview_path.read_text(encoding="utf-8").lower()
            for required in ["<!doctype html", "<html", "<head", "<body"]:
                if required not in content:
                    self.errors.append(f"preview.html 缺少 HTML 结构：{required}")
            original_content = preview_path.read_text(encoding="utf-8")
            for pattern in UI_PREVIEW_FORBIDDEN_PATTERNS:
                if pattern in original_content:
                    self.errors.append(f"preview.html 禁止引用远程资源或外部请求：{pattern}")
        handoff_path = ui_dir / "ui-handoff.md"
        if handoff_path.exists():
            content = handoff_path.read_text(encoding="utf-8")
            required_keywords = ["architect", "页面到 API", "页面到模块", "验收关注点"]
            for keyword in required_keywords:
                if keyword not in content:
                    self.errors.append(f"ui-handoff.md 缺少 architect 消费关键词：{keyword}")
        return ui_dir

    def validate_dag_state(self, required=False):
        if not self.dag_state_path.exists():
            if required:
                self.errors.append(f"dag-state 文件不存在：{self.dag_state_path}")
            return None
        dag_state = self._read_json(self.dag_state_path)
        if not isinstance(dag_state, dict):
            self.errors.append("dag-state 顶层必须是 object。")
            return None
        if dag_state.get("task_id") != self.task_id:
            self.errors.append("dag-state.task_id 与当前 task_id 不一致。")
        if dag_state.get("dag_status") not in {"pending", "running", "success", "failed"}:
            self.errors.append(f"dag-state.dag_status 不合法：{dag_state.get('dag_status')}")
        nodes = dag_state.get("nodes")
        if not isinstance(nodes, dict):
            self.errors.append("dag-state.nodes 必须是 object。")
            return dag_state
        for node_id, node in nodes.items():
            if not isinstance(node, dict):
                self.errors.append(f"dag-state.nodes.{node_id} 必须是 object。")
                continue
            status = node.get("status")
            if status not in {"pending", "ready", "running", "success", "failed", "skipped"}:
                self.errors.append(f"dag-state.nodes.{node_id}.status 不合法：{status}")
            agent = node.get("agent")
            if agent is not None and not isinstance(agent, str):
                self.errors.append(f"dag-state.nodes.{node_id}.agent 必须是 string 或 null。")
            depends_on = node.get("depends_on")
            if not isinstance(depends_on, list):
                self.errors.append(f"dag-state.nodes.{node_id}.depends_on 必须是数组。")
        return dag_state

    def validate_observability(self, required=False):
        state_exists = self.state_path.exists()
        event_exists = self.event_log_path.exists()
        if not state_exists:
            if required:
                self.errors.append(f"observability state 不存在：{self.state_path}")
            return
        if not event_exists:
            if required:
                self.errors.append(f"observability event log 不存在：{self.event_log_path}")
            return
        state = self._read_json(self.state_path)
        events = self._read_event_log(self.event_log_path)
        if not isinstance(state, dict) or events is None:
            return
        if state.get("task_id") != self.task_id:
            self.errors.append("observability state.task_id 与当前 task_id 不一致。")
        last_event = events[-1] if events else None
        if not isinstance(last_event, dict):
            self.errors.append("observability event log 至少需要一条 object 事件。")
            return
        if last_event.get("task_id") != self.task_id:
            self.errors.append("observability event.task_id 与当前 task_id 不一致。")
        state_status = (state.get("current_phase"), state.get("phase_status"))
        event_status = (last_event.get("current_phase"), last_event.get("phase_status"))
        if state_status != event_status:
            self.errors.append("observability event 最后状态与 state 不一致。")
        apply_conflict_report = self.reports_dir / "apply_conflict_report.json"
        if state_status == ("report", "passed"):
            self.validate_apply_report(required=True)
        if state_status == ("report", "passed") and apply_conflict_report.exists():
            self.errors.append("observability state=report/passed 时不得存在 apply_conflict_report.json。")
        if state_status == ("report", "passed") and event_status[1] in {"failed", "blocked"}:
            self.errors.append("observability state=report/passed 时 event 最后状态不得为 failed/blocked。")

    def _is_java_project(self, project_profile):
        if not isinstance(project_profile, dict):
            return False
        language = str(project_profile.get("language", "")).lower()
        backend_type = str(project_profile.get("backend_type", "")).lower()
        return language == "java" or "spring" in backend_type

    def _validate_java_target_file(self, value, label):
        normalized = value.replace("\\", "/")
        parts = normalized.split("/")
        filename = parts[-1]
        if normalized.startswith("src/test/java/"):
            return
        if normalized.startswith("src/main/resources/mapper/"):
            if not filename.lower().endswith("-mapper.xml"):
                self.errors.append(f"{label} Mapper XML 文件名必须使用 ***-mapper.xml：{value}")
            return
        if filename.endswith(".xml") and "mapper" in parts:
            self.errors.append(f"{label} Mapper XML 必须位于 src/main/resources/mapper/：{value}")
            return
        if not normalized.startswith("src/main/java/"):
            return
        allowed_layers = {"controller", "service", "dao", "module", "utils"}
        if not any(part in allowed_layers for part in parts):
            self.errors.append(f"{label} Java 主源码必须位于 controller/service/dao/module/utils 标准目录：{value}")
        if filename.endswith("Controller.java") and "controller" not in parts:
            self.errors.append(f"{label} Controller 必须位于 controller 目录：{value}")
        if filename.endswith("ServiceImpl.java") and not self._contains_sequence(parts, ["service", "impl"]):
            self.errors.append(f"{label} ServiceImpl 必须位于 service/impl 目录：{value}")
        if filename.endswith("Service.java") and not filename.endswith("ServiceImpl.java") and "service" not in parts:
            self.errors.append(f"{label} Service 接口必须位于 service 目录：{value}")
        if (filename.endswith("Dao.java") or filename.endswith("Mapper.java")) and "dao" not in parts:
            self.errors.append(f"{label} Dao/Mapper 接口必须位于 dao 目录：{value}")
        if "module" in parts:
            module_index = parts.index("module")
            if len(parts) <= module_index + 1 or parts[module_index + 1] not in JAVA_MODULE_SUBDIRS:
                self.errors.append(f"{label} module 目录下只允许 beans/common/aop/core/vo/security/log：{value}")
        if "utils" in parts:
            utils_index = parts.index("utils")
            if len(parts) <= utils_index + 1 or parts[utils_index + 1] not in JAVA_UTILS_SUBDIRS:
                self.errors.append(f"{label} utils 目录下只允许 inner/outer：{value}")

    def _contains_sequence(self, parts, sequence):
        for index in range(len(parts) - len(sequence) + 1):
            if parts[index:index + len(sequence)] == sequence:
                return True
        return False

    def _read_event_log(self, path):
        events = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            self.errors.append(f"event log 读取失败：{path}: {exc}")
            return None
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                self.errors.append(f"event log JSONL 解析失败：{path}:{index}: {exc}")
                return None
            if not isinstance(event, dict):
                self.errors.append(f"event log 每行必须是 object：{path}:{index}")
                return None
            events.append(event)
        return events

    def _validate_schema(self, value, filename, label):
        schema_path = self.plugin_root / "schemas" / filename
        if not schema_path.exists():
            self.errors.append(f"{label} schema 不存在：{schema_path}")
            return
        schema = self._read_json(schema_path)
        if not isinstance(schema, dict):
            self.errors.append(f"{label} schema 顶层必须是 object。")
            return
        self._validate_schema_data(value, schema, label)

    def _validate_schema_data(self, value, schema, label):
        try:
            self.errors.extend(SchemaValidator().validate(value, schema, label))
        except SchemaValidationError as exc:
            self.errors.append(str(exc))

    def _normalize_identity(self, data, label):
        try:
            return normalize_legacy_identity(data, label)
        except SessionStateValidationError as exc:
            self.errors.append(str(exc))
            return None

    def _read_json(self, path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self.errors.append(f"JSON 解析失败：{path}: {exc}")
            return None
        if isinstance(data, dict):
            return self._normalize_identity(data, str(path))
        return data

    def _read_first_json_block(self, path, label):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            self.errors.append(f"报告读取失败：{path}: {exc}")
            return None
        in_json = False
        block = []
        for line in lines:
            stripped = line.strip()
            if not in_json and stripped == "```json":
                in_json = True
                continue
            if in_json and stripped == "```":
                try:
                    data = json.loads("\n".join(block))
                except json.JSONDecodeError as exc:
                    self.errors.append(f"{label} JSON 证据块解析失败：{exc}")
                    return None
                if not isinstance(data, dict):
                    self.errors.append(f"{label} JSON 证据块顶层必须是 object。")
                    return None
                return data
            if in_json:
                block.append(line)
        if in_json:
            self.errors.append(f"{label} JSON 证据块未正常结束。")
        else:
            self.errors.append(f"{label} 缺少首个 JSON 证据块。")
        return None

    def _prd_traceability_ids(self):
        prd_path = self.root / ".superlooper" / "context" / self.task_id / "prd.md"
        if not prd_path.exists():
            self.errors.append(f"PRD 不存在：{prd_path}")
            return set()
        try:
            content = prd_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.errors.append(f"PRD 读取失败：{prd_path}: {exc}")
            return set()
        requirement_ids = set(PRD_TRACEABILITY_PATTERN.findall(content))
        if not requirement_ids:
            self.errors.append("PRD 未包含 REQ-*、AC-*、DEC-* 或 OPEN-* 编号。")
        return requirement_ids

    def _validate_requirement_coverage_ids(self, coverage, label):
        if not isinstance(coverage, list) or not coverage:
            self.errors.append(f"{label} 必须是非空数组。")
            return []
        ids = []
        seen = set()
        duplicates = set()
        for index, item in enumerate(coverage):
            item_label = f"{label}[{index}]"
            if not isinstance(item, dict):
                self.errors.append(f"{item_label} 必须是 object。")
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str) or not PRD_TRACEABILITY_PATTERN.fullmatch(item_id):
                self.errors.append(f"{item_label}.id 必须是合法的 REQ-*、AC-*、DEC-* 或 OPEN-* 编号。")
                continue
            if item_id in seen:
                duplicates.add(item_id)
            seen.add(item_id)
            ids.append((item_id, item, item_label))
        if duplicates:
            self.errors.append(f"{label} 包含重复编号：{', '.join(sorted(duplicates))}。")
        expected_ids = self._prd_traceability_ids()
        actual_ids = {item_id for item_id, _, _ in ids}
        missing = sorted(expected_ids - actual_ids)
        unknown = sorted(actual_ids - expected_ids)
        if missing:
            self.errors.append(f"{label} 缺少 PRD 编号：{', '.join(missing)}。")
        if unknown:
            self.errors.append(f"{label} 包含 PRD 未定义编号：{', '.join(unknown)}。")
        return ids

    def _validate_test_evidence(self, evidence):
        label = "test_report"
        commands = evidence.get("commands")
        if not isinstance(commands, list) or not commands:
            self.errors.append(f"{label}.commands 必须是非空数组。")
        else:
            for index, command in enumerate(commands):
                item_label = f"{label}.commands[{index}]"
                if not isinstance(command, dict):
                    self.errors.append(f"{item_label} 必须是 object。")
                    continue
                if not isinstance(command.get("command"), str) or not command.get("command").strip():
                    self.errors.append(f"{item_label}.command 必须是非空字符串。")
                exit_code = command.get("exit_code")
                if not isinstance(exit_code, int) or isinstance(exit_code, bool):
                    self.errors.append(f"{item_label}.exit_code 必须是整数。")
                elif exit_code != 0:
                    self.errors.append(f"{item_label}.exit_code 必须为 0。")
                if command.get("result") != "PASS":
                    self.errors.append(f"{item_label}.result 必须为 PASS。")
                if not isinstance(command.get("key_output"), str) or not command.get("key_output").strip():
                    self.errors.append(f"{item_label}.key_output 必须是非空字符串。")
        coverage = self._validate_requirement_coverage_ids(
            evidence.get("requirement_coverage"),
            f"{label}.requirement_coverage",
        )
        for _, item, item_label in coverage:
            if item.get("status") != "PASS":
                self.errors.append(f"{item_label}.status 必须为 PASS。")
            if not isinstance(item.get("evidence"), str) or not item.get("evidence").strip():
                self.errors.append(f"{item_label}.evidence 必须是非空字符串。")

    def _validate_requirement_alignment_evidence(self, evidence):
        label = "requirement_alignment_report"
        coverage = self._validate_requirement_coverage_ids(
            evidence.get("requirement_coverage"),
            f"{label}.requirement_coverage",
        )
        for item_id, item, item_label in coverage:
            if item.get("type") != item_id.split("-", 1)[0]:
                self.errors.append(f"{item_label}.type 必须与编号前缀一致。")
            if item.get("status") != "PASS":
                self.errors.append(f"{item_label}.status 必须为 PASS。")
            for field in (
                "implementation_evidence",
                "test_evidence",
                "delivery_evidence",
            ):
                values = item.get(field)
                if (
                    not isinstance(values, list)
                    or not values
                    or any(not isinstance(value, str) or not value.strip() for value in values)
                ):
                    self.errors.append(f"{item_label}.{field} 必须是非空字符串数组。")

    def _read_first_yaml_block(self, path):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            self.errors.append(f"报告读取失败：{path}: {exc}")
            return None
        in_yaml = False
        block = []
        for line in lines:
            stripped = line.strip()
            if not in_yaml and stripped in ("```yaml", "```yml"):
                in_yaml = True
                continue
            if in_yaml and stripped == "```":
                return self._parse_simple_yaml(block, path)
            if in_yaml:
                block.append(line)
        self.errors.append(f"报告缺少第一个 yaml 状态块：{path}")
        return None

    def _parse_simple_yaml(self, lines, path):
        result = {}
        current_key = None
        for line in lines:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            stripped = line.strip()
            if stripped.startswith("-") and current_key:
                result.setdefault(current_key, []).append(stripped[1:].strip().strip("'\""))
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if value == "[]":
                result[key] = []
                current_key = None
            elif value:
                result[key] = value
                current_key = None
            else:
                result[key] = []
                current_key = key
        if not result:
            self.errors.append(f"报告 yaml 状态块为空或不可解析：{path}")
            return None
        return self._normalize_identity(result, str(path))

    def _yaml_bool(self, data, field, label):
        value = data.get(field)
        if isinstance(value, bool):
            return True
        if isinstance(value, str) and value in ("true", "false"):
            return True
        self.errors.append(f"{label}.{field} 必须是 boolean。")
        return False

    def _yaml_int(self, data, field, label):
        value = data.get(field)
        try:
            return int(value)
        except (TypeError, ValueError):
            self.errors.append(f"{label}.{field} 必须是整数。")
            return None

    def _require_string(self, data, field, label):
        if not isinstance(data.get(field), str) or not data.get(field):
            self.errors.append(f"{label}.{field} 必须是非空字符串。")

    def _require_array(self, data, field, label):
        if not isinstance(data.get(field), list):
            self.errors.append(f"{label}.{field} 必须是数组。")

    def _validate_task_id(self):
        if not self.task_id or not TASK_ID_PATTERN.match(self.task_id):
            self.errors.append("task_id 只能包含字母、数字、下划线、短横线和点。")

    def _resolve_artifact_path(self, path, root, label, strict=True):
        try:
            resolved_root = Path(root).resolve(strict=True)
            resolved = Path(path).resolve(strict=strict)
        except OSError as exc:
            self.errors.append(f"{label} 真实路径解析失败：{path}: {exc}")
            return None
        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            self.errors.append(
                f"{label} 不在授权目录内：{path} -> {resolved}"
            )
            return None
        return resolved

    def _safe_relative_path(self, value, allow_protected=False):
        return is_safe_relative_path(
            value,
            protected_roots=(set() if allow_protected else PROTECTED_ROOTS),
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Validate SUPERLOOPER orchestration contracts.")
    parser.add_argument("--workspace-root", default=os.getenv("SUPERLOOPER_WORKSPACE_ROOT", os.getcwd()), help="目标项目根目录，默认 SUPERLOOPER_WORKSPACE_ROOT 或当前目录。")
    parser.add_argument("--task-id", default=os.getenv("SUPERLOOPER_TASK_ID"), help="执行任务 ID。")
    parser.add_argument("--session-id", default=os.getenv("SUPERLOOPER_SESSION_ID"), help=argparse.SUPPRESS)
    parser.add_argument("--agents-dir", default=os.getenv("SUPERLOOPER_AGENTS_DIR"), help="插件静态 agent 目录，默认 <plugin-root>/agents。")
    parser.add_argument("--plugin-root", default=os.getenv("SUPERLOOPER_PLUGIN_ROOT"), help="插件源码或安装根目录，默认使用当前脚本所在插件根。")
    parser.add_argument("--runtime-agents-dir", default=os.getenv("SUPERLOOPER_RUNTIME_AGENTS_DIR"), help="动态 agent 运行时源目录，默认 <workspace-root>/.superlooper/agents/<task_id>。")
    parser.add_argument("--registered-agents-dir", default=os.getenv("SUPERLOOPER_REGISTERED_AGENTS_DIR"), help="动态 agent 注册入口目录，默认 <workspace-root>/.claude/agents/generated/superlooper/<task_id>。")
    parser.add_argument("--module-split", default=os.getenv("SUPERLOOPER_MODULE_SPLIT"), help="module-split.json 路径。")
    parser.add_argument("--execution-manifest", default=os.getenv("SUPERLOOPER_MANIFEST_PATH"), help="execution_manifest.json 路径。")
    parser.add_argument("--outputs-root", default=os.getenv("SUPERLOOPER_OUTPUTS_DIR"), help="模块产物根目录，默认 <workspace-root>/.superlooper/outputs。")
    parser.add_argument("--scope", choices=["interaction-flow", "ui-artifacts", "module-split", "execution", "artifacts", "code-review-report", "test-report", "apply-report", "initialization-advice", "initialization-report", "requirement-alignment-report", "execution-summary", "upstream-alignment", "change-impact-report", "dag-state", "observability", "reports", "all"], default="all", help="校验范围。")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        task_id = resolve_explicit_task_id(args.task_id, args.session_id, required=True)
        validator = ContractValidator(
            workspace_root=args.workspace_root,
            task_id=task_id,
            agents_dir=args.agents_dir,
            runtime_agents_dir=args.runtime_agents_dir,
            registered_agents_dir=args.registered_agents_dir,
            module_split=args.module_split,
            execution_manifest=args.execution_manifest,
            outputs_root=args.outputs_root,
            plugin_root=args.plugin_root,
        )
        validator.validate(args.scope)
    except (ContractError, SessionStateValidationError) as exc:
        print(f"校验失败：\n{exc}", file=sys.stderr)
        return 1
    print(f"SUPERLOOPER 契约校验通过：scope={args.scope}, task_id={task_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
