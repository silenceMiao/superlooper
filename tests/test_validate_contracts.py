import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SNAPSHOT_DIGEST = "sha256:f80ff197bdd6c1ddb1b5ddc2ccdf097c86af29980bd82e1440064489ade45f98"


class ValidateContractsScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.task_id = "session_validate"
        self.runtime_root = self.workspace_root / ".superlooper"
        self.manifests_dir = self.runtime_root / "manifests" / self.task_id
        self.outputs_dir = self.runtime_root / "outputs" / self.task_id
        self.reports_dir = self.runtime_root / "reports" / self.task_id
        self.agents_dir = self.workspace_root / "agents"
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.write_static_agents()
        self.write_prd()
        self.write_module_split()
        self.write_initialized_state()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_validate(self, scope, encoding=None):
        script_path = self.repo_root / "scripts" / "validate_miao_contracts.py"
        env = None
        if encoding:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = encoding
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                self.task_id,
                "--agents-dir",
                "agents",
                "--scope",
                scope,
            ],
            cwd=self.repo_root,
            text=True,
            encoding=encoding,
            env=env,
            capture_output=True,
            check=False,
        )

    def run_generate_manifest(self):
        script_path = self.repo_root / "scripts" / "generate_execution_manifest.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                self.task_id,
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_generate_agents(self):
        script_path = self.repo_root / "scripts" / "generate_runtime_agents.py"
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                self.task_id,
                "--agents-dir",
                "agents",
            ],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def rewrite_agent_constraints(
        self,
        path,
        legacy_identity=False,
        dual_identity=False,
        **overrides,
    ):
        manifest = json.loads(
            (self.manifests_dir / "execution_manifest.json").read_text(encoding="utf-8")
        )
        payload = next(
            node["payload"]
            for node in manifest["dag"]["nodes"]
            if node["id"] == "mod_report_export"
        )
        fields = [
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
        constraints = {field: payload[field] for field in fields}
        constraints.update(overrides)
        content = path.read_text(encoding="utf-8")
        prefix = content.split("## Runtime Module Constraints", 1)[0].rstrip()
        block = [prefix, "", "## Runtime Module Constraints", "", "```yaml"]
        for field in constraints:
            if field == "task_id" and legacy_identity:
                block.append(
                    f"session_id: {json.dumps(constraints[field], ensure_ascii=False)}"
                )
                if not dual_identity:
                    continue
            block.append(
                f"{field}: {json.dumps(constraints[field], ensure_ascii=False)}"
            )
        block.extend(["```", ""])
        path.write_text("\n".join(block), encoding="utf-8")

    def replace_frontmatter_name(self, path, name):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                break
            if line.startswith("name:"):
                newline = "\n" if line.endswith("\n") else ""
                lines[index] = f"name: {name}{newline}"
                break
        path.write_text("".join(lines), encoding="utf-8")

    def system_payloads(self):
        return {
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

    def write_manifest_with_system_payloads(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payloads = self.system_payloads()
        for node in manifest["dag"]["nodes"]:
            if node["id"] in payloads:
                node["payload"] = payloads[node["id"]]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest_path, manifest

    def create_directory_link(self, link_path, target_path):
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            return
        link_path.symlink_to(target_path, target_is_directory=True)

    def write_static_agents(self):
        shutil.copy2(self.repo_root / "agents" / "developer.md", self.agents_dir / "developer.md")
        for agent_name in ("code-reviewer", "system_merger", "tester", "workspace_applier"):
            (self.agents_dir / f"{agent_name}.md").write_text(
                f"---\nname: {agent_name}\ndescription: {agent_name}\n---\n",
                encoding="utf-8",
            )

    def write_ui_artifacts(self, project_mode="greenfield", ui_status="READY_FOR_REVIEW", preview=None, handoff=None):
        ui_dir = self.runtime_root / "context" / self.task_id / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        (ui_dir / "ui-spec.md").write_text(
            "```yaml\n"
            f"task_id: {self.task_id}\n"
            f"ui_status: {ui_status}\n"
            f"prd_path: .superlooper/context/{self.task_id}/prd.md\n"
            f"ui_output_dir: .superlooper/context/{self.task_id}/ui/\n"
            f"preview_path: .superlooper/context/{self.task_id}/ui/preview.html\n"
            f"project_mode: {project_mode}\n"
            "existing_frontend: false\n"
            "page_count: 2\n"
            "interaction_count: 3\n"
            "unresolved_ui_decision_count: 0\n"
            "```\n",
            encoding="utf-8",
        )
        (ui_dir / "page-map.md").write_text("# 页面地图\n", encoding="utf-8")
        (ui_dir / "interaction-flow.md").write_text("# 交互流程\n", encoding="utf-8")
        (ui_dir / "ui-handoff.md").write_text(
            handoff or "# UI Handoff\n\narchitect 消费说明\n\n## 页面到 API\n\n## 页面到模块\n\n## 验收关注点\n",
            encoding="utf-8",
        )
        (ui_dir / "preview.html").write_text(
            preview or "<!doctype html><html><head><title>demo</title></head><body><main>demo</main></body></html>\n",
            encoding="utf-8",
        )
        return ui_dir

    def write_prd(self):
        prd_path = self.runtime_root / "context" / self.task_id / "prd.md"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        prd_path.write_text(
            "# PRD\n\n"
            "### REQ-001：导出报表\n\n"
            "### AC-001：导出成功\n\n"
            "### DEC-001：采用同步导出\n\n"
            "### OPEN-001：大文件阈值按默认值处理\n",
            encoding="utf-8",
        )

    def write_initialization_advice(
        self,
        task_id=None,
        project_category="springboot",
        project_version="springboot-3.x",
        project_root=".",
        omit_field=None,
    ):
        values = {
            "task_id": task_id or self.task_id,
            "project_category": project_category,
            "project_version": project_version,
            "project_root": project_root,
        }
        if omit_field:
            values.pop(omit_field)
        design_dir = self.runtime_root / "context" / self.task_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        lines = ["# Initialization Advice", "", "```yaml"]
        lines.extend(f"{key}: {value}" for key, value in values.items())
        lines.extend(["```", ""])
        (design_dir / "initialization-advice.md").write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    def write_design_artifacts(self):
        design_dir = self.runtime_root / "context" / self.task_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        (design_dir / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
        (design_dir / "tech-stack.md").write_text("# Tech Stack\n", encoding="utf-8")
        (design_dir / "project-profile.md").write_text("# Project Profile\n", encoding="utf-8")
        self.write_initialization_advice()

    def write_initialized_state(self):
        self.write_ui_artifacts(ui_status="READY_FOR_REVIEW")
        self.write_design_artifacts()
        report_path = self.reports_dir / "initialization_report.json"
        report_path.write_text(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "status": "success",
                    "project_category": "springboot",
                    "project_version": "springboot-3.x",
                    "project_root": ".",
                    "created_paths": ["src/main/java", "src/main/resources", "src/test/java", "target", "CLAUDE.md", "pom.xml"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        state_dir = self.runtime_root / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / f"{self.task_id}.json").write_text(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "task_name": None,
                    "workspace_root": str(self.workspace_root.resolve()),
                    "requirement_path": str((self.workspace_root / "requirements.md").resolve()),
                    "current_phase": "run",
                    "phase_status": "pending",
                    "generated_files": [],
                    "reports": [],
                    "script_events": [],
                    "last_command": "test",
                    "last_error": None,
                    "next_actions": [],
                    "project_mode": "greenfield",
                    "workflow_mode": "standard",
                    "project_category": "springboot",
                    "project_version": "springboot-3.x",
                    "project_root": ".",
                    "project_initialized": True,
                    "initialization_report": f".superlooper/reports/{self.task_id}/initialization_report.json",
                    "execution_summary_status": "NOT_STARTED",
                    "execution_summary_report": None,
                    "loop_policy": {"max_auto_loop_per_phase": 2},
                    "loop_state": {
                        "current_loop_target_phase": None,
                        "loop_count_by_phase": {},
                        "last_alignment_status": None,
                        "last_feedback_report": None,
                    },
                    "requirement_alignment_report": None,
                    "requirement_alignment_passed": False,
                    "prd_revision": 0,
                    "ui_revision": 0,
                    "ui_status": "APPROVED",
                    "ui_output_dir": f".superlooper/context/{self.task_id}/ui/",
                    "ui_artifacts_validated": True,
                    "design_revision": 0,
                    "change_request_count": 0,
                    "active_feedback_report": None,
                    "change_impact_report": None,
                    "affected_modules": [],
                    "invalidated_artifacts": [],
                    "rollback_target_phase": None,
                    "last_user_input_text": None,
                    "last_user_canonical_action": None,
                    "pending_user_choice": None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_dag_state(self, status="success", node_status="success"):
        dag_state_path = self.runtime_root / "state" / f"{self.task_id}.dag.json"
        dag_state_path.parent.mkdir(parents=True, exist_ok=True)
        dag_state_path.write_text(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "dag_status": status,
                    "current_node": "mod_report_export",
                    "execution_order": ["mod_report_export"],
                    "error_summary": "",
                    "manifest_path": f".superlooper/manifests/{self.task_id}/execution_manifest.json",
                    "nodes": {
                        "mod_report_export": {
                            "status": node_status,
                            "agent": "module_report_export",
                            "depends_on": [],
                            "artifact_manifest": f".superlooper/outputs/{self.task_id}/report_export/artifact_manifest.json",
                            "error_summary": "",
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_module_split(self):
        self.module_split_path = self.manifests_dir / "module-split.json"
        self.module_split_path.write_text(
            json.dumps(
                {
                    "project_name": "fixture-demo",
                    "modules": [
                        {
                            "id": "report_export",
                            "name": "Report Export",
                            "description": "实现报表导出控制器。",
                            "referenced_tables": [],
                            "referenced_apis": [],
                            "target_files": [
                                "src/main/java/com/example/controller/ReportExportController.java"
                            ],
                            "file_roles": [
                                {
                                    "path": "src/main/java/com/example/controller/ReportExportController.java",
                                    "role": "controller",
                                }
                            ],
                            "requirement_refs": ["REQ-001"],
                            "acceptance_refs": ["AC-001"],
                            "ui_refs": ["UI-PAGE-001"],
                            "interaction_refs": ["INT-001"],
                            "component_refs": ["CMP-001"],
                            "ui_acceptance_refs": ["UI-AC-001"],
                            "allowed_existing_files": [
                                "src/main/java/com/example/controller/ReportExportController.java"
                            ],
                            "forbidden_files": ["src/main/resources/application.yml"],
                            "integration_points": ["ReportRepository"],
                            "test_commands": ["python -m unittest tests.test_report_export"],
                            "overwrite_policy": "block_by_default",
                            "test_focus": ["导出成功路径"],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_success_artifact(self):
        module_dir = self.outputs_dir / "report_export"
        target_file = module_dir / "src" / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("public class ReportExportController {}\n", encoding="utf-8")
        artifact_path = module_dir / "artifact_manifest.json"
        artifact_path.write_text(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "module_id": "report_export",
                    "agent": "module_report_export",
                    "status": "success",
                    "produced_files": [
                        {
                            "path": "src/main/java/com/example/controller/ReportExportController.java",
                            "kind": "code",
                            "operation": "create",
                            "required_for_merge": True,
                        }
                    ],
                    "verification": {
                        "commands": [
                            {
                                "command": "python -c \"print('ok')\"",
                                "status": "passed",
                                "summary": "模块校验通过",
                            }
                        ],
                        "summary": "模块校验通过",
                    },
                    "notes": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_test_report(self, status="PASS", body=None, evidence=None):
        report_path = self.reports_dir / "test_report.md"
        if body is None:
            body = (
                "\n"
                "## UI 验收覆盖\n"
                "- UI-AC-001: PASS，已覆盖报表导出入口与导出成功反馈。\n"
            )
        if evidence is None:
            evidence = {
                "commands": [
                    {
                        "command": "python -m unittest tests.test_report_export",
                        "exit_code": 0,
                        "result": "PASS",
                        "key_output": "1 test passed",
                    }
                ],
                "requirement_coverage": [
                    {"id": item_id, "status": "PASS", "evidence": f"verified {item_id}"}
                    for item_id in ("REQ-001", "AC-001", "DEC-001", "OPEN-001")
                ],
            }
        evidence_block = ""
        if evidence is not False:
            evidence_block = "```json\n" + json.dumps(evidence, ensure_ascii=False, indent=2) + "\n```\n"
        report_path.write_text(
            "```yaml\n"
            f"task_id: {self.task_id}\n"
            f"test_status: {status}\n"
            f"tested_path: .superlooper/merged/{self.task_id}\n"
            f"merge_report_path: .superlooper/reports/{self.task_id}/merge_report.json\n"
            f"report_path: .superlooper/reports/{self.task_id}/test_report.md\n"
            "```\n"
            f"{evidence_block}{body}",
            encoding="utf-8",
        )

    def write_requirement_alignment_report(self, status="PASS", unmet=0, unchecked=0, body=None, evidence=None):
        if body is None:
            body = (
                "\n"
                "## UI 验收校对\n"
                "- UI-AC-001: PASS，已校对 test_report.md 覆盖证据，满足 UI 验收要求。\n"
            )
        if evidence is None:
            evidence = {
                "requirement_coverage": [
                    {
                        "id": item_id,
                        "type": item_id.split("-", 1)[0],
                        "status": "PASS",
                        "implementation_evidence": [f"implementation for {item_id}"],
                        "test_evidence": [f"test for {item_id}"],
                        "delivery_evidence": [f"delivery for {item_id}"],
                    }
                    for item_id in ("REQ-001", "AC-001", "DEC-001", "OPEN-001")
                ]
            }
        evidence_block = ""
        if evidence is not False:
            evidence_block = "```json\n" + json.dumps(evidence, ensure_ascii=False, indent=2) + "\n```\n"
        report_path = self.reports_dir / "requirement_alignment_report.md"
        report_path.write_text(
            "```yaml\n"
            f"task_id: {self.task_id}\n"
            f"requirement_alignment_status: {status}\n"
            f"unmet_requirement_count: {unmet}\n"
            f"unchecked_acceptance_count: {unchecked}\n"
            f"prd_path: .superlooper/context/{self.task_id}/prd.md\n"
            f"test_report_path: .superlooper/reports/{self.task_id}/test_report.md\n"
            f"apply_report_path: .superlooper/reports/{self.task_id}/apply_report.json\n"
            f"report_path: .superlooper/reports/{self.task_id}/requirement_alignment_report.md\n"
            "```\n"
            f"{evidence_block}{body}",
            encoding="utf-8",
        )

    def write_change_impact_report(
        self,
        affected_module="report_export",
        affected_modules=None,
        affected_artifact=None,
        status="PASS",
        rollback_target_phase="run",
        requires_reinitialization="false",
        local_rerun_allowed="true",
    ):
        artifact = affected_artifact or f".superlooper/outputs/{self.task_id}/report_export/artifact_manifest.json"
        modules = [affected_module] if affected_modules is None else affected_modules
        lines = [
            "```yaml",
            f"task_id: {self.task_id}",
            f"change_impact_status: {status}",
            f"rollback_target_phase: {rollback_target_phase}",
            f"requires_reinitialization: {requires_reinitialization}",
            "affected_artifacts:",
            f"  - {artifact}",
            "affected_modules:",
        ]
        lines.extend(f"  - {module_id}" for module_id in modules)
        lines.extend(
            [
                f"local_rerun_allowed: {local_rerun_allowed}",
                "manual_approval_required: true",
                f"report_path: .superlooper/reports/{self.task_id}/change_impact_report.md",
                "```",
            ]
        )
        report_path = self.reports_dir / "change_impact_report.md"
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_execution_summary(self, status="READY_FOR_APPROVAL", module_split_validated="true", execution_manifest_validated="true", upstream_alignment_status="PASS"):
        report_path = self.reports_dir / "execution_summary.md"
        report_path.write_text(
            "```yaml\n"
            f"execution_summary_status: {status}\n"
            f"task_id: {self.task_id}\n"
            "workflow_mode: standard\n"
            "project_category: springboot\n"
            "project_version: springboot-3.x\n"
            "module_count: 1\n"
            "target_file_count: 1\n"
            "risk_count: 0\n"
            "blocking_decisions:\n"
            f"upstream_alignment_status: {upstream_alignment_status}\n"
            f"module_split_validated: {module_split_validated}\n"
            f"execution_manifest_validated: {execution_manifest_validated}\n"
            f"report_path: .superlooper/reports/{self.task_id}/execution_summary.md\n"
            "```\n",
            encoding="utf-8",
        )

    def write_upstream_alignment(self, status="PASS", mismatch_count=0, loop_required="false", loop_target_phase="design", blocking_decisions=None):
        decisions = blocking_decisions or []
        lines = [
            "```yaml",
            f"task_id: {self.task_id}",
            f"upstream_alignment_status: {status}",
            f"mismatch_count: {mismatch_count}",
            f"loop_required: {loop_required}",
            f"loop_target_phase: {loop_target_phase}",
            "blocking_decisions:",
        ]
        lines.extend(f"  - {item}" for item in decisions)
        lines.append(f"report_path: .superlooper/reports/{self.task_id}/upstream_alignment.md")
        lines.append("```")
        (self.reports_dir / "upstream_alignment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_code_review_report(self, status, reviewed_modules=None):
        modules = ["report_export"] if reviewed_modules is None else reviewed_modules
        lines = [
            "```yaml",
            f"task_id: {self.task_id}",
            f"code_review_status: {status}",
            "blocker_count: 0",
            "blocking_major_count: 0",
            "reviewed_modules:",
        ]
        lines.extend(f"- {module_id}" for module_id in modules)
        lines.extend(
            [
                f"report_path: .superlooper/reports/{self.task_id}/code_review_report.md",
                "```",
            ]
        )
        report_path = self.reports_dir / "code_review_report.md"
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_apply_report(
        self,
        validation=None,
        merge_snapshot_digest=SNAPSHOT_DIGEST,
        apply_snapshot_digest=SNAPSHOT_DIGEST,
        merged_content="hello\n",
    ):
        merged_file = self.runtime_root / "merged" / self.task_id / "src" / "app.txt"
        merged_file.parent.mkdir(parents=True, exist_ok=True)
        merged_file.write_bytes(merged_content.encode("utf-8"))
        (self.reports_dir / "merge_report.json").write_text(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "status": "success",
                    "snapshot_digest": merge_snapshot_digest,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        workspace_validation = validation or {
            "status": "PASS",
            "checked_file_count": 1,
            "matched_file_count": 1,
            "failed_file_count": 0,
            "checked_files": [],
            "failures": [],
        }
        (self.reports_dir / "apply_report.json").write_text(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "status": "success" if workspace_validation["status"] == "PASS" else "failed",
                    "snapshot_digest": apply_snapshot_digest,
                    "workspace_validation": workspace_validation,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_validate_contracts_accepts_valid_module_split(self):
        result = self.run_validate("module-split")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_rejects_module_split_unknown_field_from_schema(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["unexpected"] = True
        self.module_split_path.write_text(json.dumps(module_split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明字段", result.stderr)

    def test_validate_contracts_rejects_windows_equivalent_targets_in_one_module(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["target_files"].append(
            "SRC/main/java/com/example/controller/reportexportcontroller.java."
        )
        self.module_split_path.write_text(
            json.dumps(module_split, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target_files 存在重复路径", result.stderr)
        self.assertIn("reportexportcontroller.java.", result.stderr)

    def test_validate_contracts_rejects_windows_equivalent_cross_module_targets(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"].append(
            {
                "id": "audit_log",
                "name": "Audit Log",
                "description": "实现审计日志服务。",
                "referenced_tables": [],
                "referenced_apis": [],
                "target_files": [
                    "SRC/main/java/com/example/controller/reportexportcontroller.java "
                ],
            }
        )
        self.module_split_path.write_text(
            json.dumps(module_split, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("跨模块重复路径", result.stderr)
        self.assertIn("audit_log", result.stderr)

    def test_validate_contracts_rejects_execution_node_unknown_field_from_schema(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"][0]["unexpected"] = True
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明字段", result.stderr)

    def test_validate_contracts_rejects_artifact_source_outside_module_directory(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        module_dir = self.outputs_dir / "report_export"
        source_root = module_dir / "src"
        outside_source = self.workspace_root / "outside-artifact-source"
        shutil.copytree(source_root, outside_source)
        outside_file = outside_source / "main" / "java" / "com" / "example" / "controller" / "ReportExportController.java"
        outside_content = outside_file.read_bytes()
        shutil.rmtree(source_root)
        self.create_directory_link(source_root, outside_source)

        result = self.run_validate("artifacts")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("授权目录", result.stderr)
        self.assertEqual(outside_file.read_bytes(), outside_content)

    def test_validate_contracts_rejects_artifact_unknown_verification_field_from_schema(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["verification"]["unexpected"] = True
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("artifacts")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明字段", result.stderr)

    def test_validate_contracts_rejects_artifact_command_missing_schema_required_field(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        del artifact["verification"]["commands"][0]["summary"]
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("artifacts")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("缺少必填字段", result.stderr)

    def test_validate_contracts_blocks_allowed_existing_files_outside_target_files(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["allowed_existing_files"] = ["src/main/java/com/example/service/ReportExportService.java"]
        self.module_split_path.write_text(json.dumps(module_split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("allowed_existing_files 必须是 target_files 子集", result.stderr)

    def test_validate_contracts_blocks_forbidden_files_target_overlap(self):
        target_file = "src/main/java/com/example/controller/ReportExportController.java"
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["forbidden_files"] = [target_file]
        self.module_split_path.write_text(json.dumps(module_split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden_files 不能与 target_files 重叠", result.stderr)

    def test_validate_contracts_accepts_windows_equivalent_allowed_existing_file(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["allowed_existing_files"] = [
            "SRC/main/java/com/example/controller/reportexportcontroller.java."
        ]
        self.module_split_path.write_text(
            json.dumps(module_split, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("module-split")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_contracts_blocks_windows_equivalent_forbidden_target_overlap(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["forbidden_files"] = [
            "SRC/main/java/com/example/controller/reportexportcontroller.java "
        ]
        self.module_split_path.write_text(
            json.dumps(module_split, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden_files 不能与 target_files 重叠", result.stderr)

    def test_validate_contracts_accepts_windows_equivalent_file_role_path(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["file_roles"][0]["path"] = (
            "SRC/main/java/com/example/controller/reportexportcontroller.java."
        )
        self.module_split_path.write_text(
            json.dumps(module_split, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("module-split")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_contracts_blocks_invalid_overwrite_policy(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        module_split["modules"][0]["overwrite_policy"] = "overwrite_existing"
        self.module_split_path.write_text(json.dumps(module_split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("module-split")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overwrite_policy 只允许 block_by_default", result.stderr)

    def test_validate_contracts_blocks_module_payload_brownfield_boundary_mismatch(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"][0]["payload"]["allowed_existing_files"] = []
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload.allowed_existing_files 必须与 module-split.modules[].allowed_existing_files 一致", result.stderr)

    def test_validate_contracts_accepts_initialization_advice(self):
        result = self.run_validate("initialization-advice")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("scope=initialization-advice", result.stdout)

    def test_validate_contracts_blocks_initialization_advice_missing_fields(self):
        for field in (
            "task_id",
            "project_category",
            "project_version",
            "project_root",
        ):
            with self.subTest(field=field):
                self.write_initialization_advice(omit_field=field)

                result = self.run_validate("initialization-advice")

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(field, result.stderr)

    def test_validate_contracts_blocks_initialization_advice_wrong_task_id(self):
        self.write_initialization_advice(task_id="other-task")

        result = self.run_validate("initialization-advice")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task_id", result.stderr)

    def test_validate_contracts_blocks_initialization_advice_invalid_category_version_pair(self):
        for project_category, project_version, expected_field in (
            ("unknown", "springboot-3.x", "project_category"),
            ("springboot", "jdk-17", "project_version"),
        ):
            with self.subTest(
                project_category=project_category,
                project_version=project_version,
            ):
                self.write_initialization_advice(
                    project_category=project_category,
                    project_version=project_version,
                )

                result = self.run_validate("initialization-advice")

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_field, result.stderr)

    def test_validate_contracts_blocks_initialization_advice_unsafe_project_root(self):
        for project_root in (
            "../outside",
            ".CLAUDE/project",
            ".superlooper /project",
            ".git\\project",
        ):
            with self.subTest(project_root=project_root):
                self.write_initialization_advice(project_root=project_root)

                result = self.run_validate("initialization-advice")

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("project_root", result.stderr)

    def test_validate_contracts_accepts_initialization_report(self):
        result = self.run_validate("initialization-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_accepts_valid_apply_report(self):
        self.write_apply_report()
        result = self.run_validate("apply-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_apply_report_without_snapshot_digest(self):
        self.write_apply_report()
        apply_path = self.reports_dir / "apply_report.json"
        apply_report = json.loads(apply_path.read_text(encoding="utf-8"))
        del apply_report["snapshot_digest"]
        apply_path.write_text(
            json.dumps(apply_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("apply-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("apply_report.snapshot_digest", result.stderr)

    def test_validate_contracts_blocks_invalid_merge_snapshot_digest_format(self):
        self.write_apply_report(merge_snapshot_digest="sha256:ABC")

        result = self.run_validate("apply-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("merge_report.snapshot_digest", result.stderr)
        self.assertIn("sha256:<64 lowercase hex>", result.stderr)

    def test_validate_contracts_blocks_merge_snapshot_digest_tree_mismatch(self):
        self.write_apply_report(merged_content="changed\n")

        result = self.run_validate("apply-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("merge_report.snapshot_digest 与 merged tree 不一致", result.stderr)

    def test_validate_contracts_blocks_apply_snapshot_digest_mismatch(self):
        self.write_apply_report(
            apply_snapshot_digest="sha256:" + "0" * 64,
        )

        result = self.run_validate("apply-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("apply_report.snapshot_digest 与 merge_report.snapshot_digest 不一致", result.stderr)

    def test_validate_contracts_blocks_apply_report_without_workspace_validation(self):
        (self.reports_dir / "apply_report.json").write_text(
            json.dumps({"task_id": self.task_id, "status": "success"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self.run_validate("apply-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace_validation", result.stderr)

    def test_validate_contracts_blocks_failed_apply_workspace_validation(self):
        self.write_apply_report(
            {
                "status": "FAIL",
                "checked_file_count": 1,
                "matched_file_count": 0,
                "failed_file_count": 1,
                "checked_files": [],
                "failures": [{"path": "src/App.java", "reason": "content_mismatch"}],
            }
        )
        result = self.run_validate("apply-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace_validation.status", result.stderr)
        self.assertIn("failed_file_count", result.stderr)
        self.assertIn("failures", result.stderr)

    def test_validate_contracts_rejects_failed_apply_after_successful_rollback(self):
        (self.reports_dir / "apply_report.json").write_text(
            json.dumps(
                {
                    "task_id": self.task_id,
                    "status": "failed",
                    "rollback": {
                        "status": "success",
                        "backup_dir": None,
                        "failures": [],
                    },
                    "workspace_validation": {
                        "status": "FAIL",
                        "checked_file_count": 1,
                        "matched_file_count": 0,
                        "failed_file_count": 1,
                        "checked_files": [],
                        "failures": [
                            {
                                "path": "src/App.java",
                                "reason": "apply_io_error",
                            }
                        ],
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("apply-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("apply_report.status", result.stderr)
        self.assertIn("workspace_validation.status", result.stderr)

    def test_validate_contracts_accepts_requirement_alignment_report(self):
        self.write_requirement_alignment_report()
        result = self.run_validate("requirement-alignment-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_test_report_missing_ui_acceptance_coverage(self):
        self.write_test_report(body="\n## UI 验收覆盖\n- 未列出 UI 验收编号。\n")

        result = self.run_validate("test-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test_report", result.stderr)
        self.assertIn("UI-AC-001", result.stderr)

    def test_validate_contracts_accepts_test_report_with_ui_acceptance_coverage(self):
        self.write_test_report(
            body=(
                "\n"
                "## UI 验收覆盖\n"
                "- UI-AC-001: PASS，已覆盖导出按钮、导出成功反馈和异常提示。\n"
            )
        )

        result = self.run_validate("test-report")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_pass_test_report_without_machine_evidence(self):
        self.write_test_report(evidence=False)

        result = self.run_validate("test-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("JSON 证据块", result.stderr)

    def test_validate_contracts_blocks_invalid_test_command_evidence(self):
        evidence = {
            "commands": [
                {
                    "command": "python -m unittest tests.test_report_export",
                    "exit_code": 1,
                    "result": "FAIL",
                    "key_output": "test failed",
                }
            ],
            "requirement_coverage": [
                {"id": item_id, "status": "PASS", "evidence": f"verified {item_id}"}
                for item_id in ("REQ-001", "AC-001", "DEC-001", "OPEN-001")
            ],
        }
        self.write_test_report(evidence=evidence)

        result = self.run_validate("test-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exit_code", result.stderr)
        self.assertIn("result", result.stderr)

    def test_validate_contracts_blocks_test_report_missing_prd_coverage(self):
        evidence = {
            "commands": [
                {
                    "command": "python -m unittest tests.test_report_export",
                    "exit_code": 0,
                    "result": "PASS",
                    "key_output": "1 test passed",
                }
            ],
            "requirement_coverage": [
                {"id": "REQ-001", "status": "PASS", "evidence": "verified REQ-001"}
            ],
        }
        self.write_test_report(evidence=evidence)

        result = self.run_validate("test-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AC-001", result.stderr)
        self.assertIn("DEC-001", result.stderr)
        self.assertIn("OPEN-001", result.stderr)

    def test_validate_contracts_blocks_requirement_alignment_missing_prd_coverage(self):
        evidence = {
            "requirement_coverage": [
                {
                    "id": item_id,
                    "type": item_id.split("-", 1)[0],
                    "status": "PASS",
                    "implementation_evidence": ["implementation"],
                    "test_evidence": ["test"],
                    "delivery_evidence": ["delivery"],
                }
                for item_id in ("REQ-001", "AC-001", "DEC-001")
            ]
        }
        self.write_requirement_alignment_report(evidence=evidence)

        result = self.run_validate("requirement-alignment-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OPEN-001", result.stderr)

    def test_validate_contracts_blocks_requirement_alignment_unknown_and_duplicate_ids(self):
        coverage = [
            {
                "id": item_id,
                "type": item_id.split("-", 1)[0],
                "status": "PASS",
                "implementation_evidence": ["implementation"],
                "test_evidence": ["test"],
                "delivery_evidence": ["delivery"],
            }
            for item_id in ("REQ-001", "AC-001", "DEC-001", "OPEN-001")
        ]
        coverage.append(dict(coverage[0]))
        coverage.append(
            {
                "id": "REQ-999",
                "type": "REQ",
                "status": "PASS",
                "implementation_evidence": ["implementation"],
                "test_evidence": ["test"],
                "delivery_evidence": ["delivery"],
            }
        )
        self.write_requirement_alignment_report(evidence={"requirement_coverage": coverage})

        result = self.run_validate("requirement-alignment-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("重复", result.stderr)
        self.assertIn("REQ-999", result.stderr)

    def test_validate_contracts_blocks_requirement_alignment_empty_evidence(self):
        evidence = {
            "requirement_coverage": [
                {
                    "id": item_id,
                    "type": item_id.split("-", 1)[0],
                    "status": "PASS",
                    "implementation_evidence": [] if item_id == "AC-001" else ["implementation"],
                    "test_evidence": ["test"],
                    "delivery_evidence": ["delivery"],
                }
                for item_id in ("REQ-001", "AC-001", "DEC-001", "OPEN-001")
            ]
        }
        self.write_requirement_alignment_report(evidence=evidence)

        result = self.run_validate("requirement-alignment-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("implementation_evidence", result.stderr)

    def test_validate_contracts_blocks_requirement_alignment_missing_ui_acceptance_evidence(self):
        self.write_requirement_alignment_report(
            body="\n## UI 验收校对\n- 只声明需求均已校对，但未列出 UI 验收编号。\n"
        )

        result = self.run_validate("requirement-alignment-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_alignment_report", result.stderr)
        self.assertIn("UI-AC-001", result.stderr)

    def test_validate_contracts_accepts_requirement_alignment_with_ui_acceptance_evidence(self):
        self.write_requirement_alignment_report(
            body=(
                "\n"
                "## UI 验收校对\n"
                "- UI-AC-001: PASS，已校对 test_report.md 覆盖证据，满足验收标准。\n"
            )
        )

        result = self.run_validate("requirement-alignment-report")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_accepts_valid_ui_artifacts(self):
        self.write_ui_artifacts()
        result = self.run_validate("ui-artifacts")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_missing_ui_spec(self):
        ui_dir = self.write_ui_artifacts()
        (ui_dir / "ui-spec.md").unlink()
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UI 固定产物不存在", result.stderr)

    def test_validate_contracts_blocks_invalid_ui_status(self):
        self.write_ui_artifacts(ui_status="DONE")
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ui-spec.ui_status", result.stderr)

    def test_validate_contracts_blocks_new_project_mode(self):
        self.write_ui_artifacts(project_mode="new_project")
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("禁止使用 new_project", result.stderr)

    def test_validate_contracts_blocks_remote_preview_resource(self):
        self.write_ui_artifacts(preview="<!doctype html><html><head></head><body><img src='https://example.com/a.png'></body></html>\n")
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preview.html 禁止引用远程资源", result.stderr)

    def test_validate_contracts_blocks_missing_ui_handoff_keyword(self):
        self.write_ui_artifacts(handoff="# UI Handoff\n\n无映射。\n")
        result = self.run_validate("ui-artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ui-handoff.md 缺少 architect 消费关键词", result.stderr)

    def test_validate_contracts_blocks_failed_requirement_alignment_counts(self):
        self.write_requirement_alignment_report(status="PASS", unmet=1, unchecked=0)
        result = self.run_validate("requirement-alignment-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unmet_requirement_count", result.stderr)

    def test_validate_contracts_accepts_valid_change_impact_report(self):
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        self.write_change_impact_report()
        result = self.run_validate("change-impact-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_local_rerun_without_execution_manifest(self):
        self.write_change_impact_report()

        result = self.run_validate("change-impact-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Execution Manifest 文件不存在", result.stderr)

    def test_validate_contracts_blocks_local_rerun_without_affected_modules(self):
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        self.write_change_impact_report(affected_modules=[])

        result = self.run_validate("change-impact-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local_rerun_allowed=true 时必须非空", result.stderr)

    def test_validate_contracts_blocks_duplicate_local_rerun_modules(self):
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        self.write_change_impact_report(
            affected_modules=["report_export", "report_export"]
        )

        result = self.run_validate("change-impact-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("affected_modules 包含重复模块", result.stderr)

    def test_validate_contracts_blocks_local_rerun_module_missing_from_execution_manifest(self):
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        audit_module = json.loads(json.dumps(module_split["modules"][0]))
        audit_module["id"] = "audit_log"
        audit_module["name"] = "Audit Log"
        audit_module["target_files"] = ["src/main/java/com/example/controller/AuditLogController.java"]
        audit_module["file_roles"] = [
            {
                "path": "src/main/java/com/example/controller/AuditLogController.java",
                "role": "controller",
            }
        ]
        audit_module["allowed_existing_files"] = list(audit_module["target_files"])
        module_split["modules"].append(audit_module)
        self.module_split_path.write_text(
            json.dumps(module_split, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.write_change_impact_report(affected_module="audit_log")

        result = self.run_validate("change-impact-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("affected_modules 包含非 Execution Manifest 模块：audit_log", result.stderr)

    def test_validate_contracts_rejects_reinitialization_as_run_local_rerun(self):
        self.write_change_impact_report(
            rollback_target_phase="run",
            requires_reinitialization="true",
            local_rerun_allowed="true",
        )

        result = self.run_validate("change-impact-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires_reinitialization=true", result.stderr)
        self.assertIn("local_rerun_allowed", result.stderr)
        self.assertIn("rollback_target_phase", result.stderr)

    def test_validate_contracts_accepts_valid_execution_summary(self):
        self.write_execution_summary()
        result = self.run_validate("execution-summary")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_unready_execution_summary(self):
        self.write_execution_summary(upstream_alignment_status="FAIL")
        result = self.run_validate("execution-summary")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("upstream_alignment_status", result.stderr)

    def test_validate_contracts_accepts_valid_upstream_alignment(self):
        self.write_upstream_alignment()
        result = self.run_validate("upstream-alignment")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_invalid_upstream_alignment_loop(self):
        self.write_upstream_alignment(status="FAIL", mismatch_count=1, loop_required="false")
        result = self.run_validate("upstream-alignment")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("loop_required", result.stderr)

    def test_validate_contracts_blocks_blocked_upstream_alignment_without_decision(self):
        self.write_upstream_alignment(status="BLOCKED")
        result = self.run_validate("upstream-alignment")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("blocking_decisions", result.stderr)

    def test_validate_contracts_blocks_unknown_change_impact_module(self):
        self.write_change_impact_report(affected_module="missing_module")
        result = self.run_validate("change-impact-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不存在于 module-split", result.stderr)

    def test_validate_contracts_blocks_unsafe_change_impact_artifact(self):
        self.write_change_impact_report(affected_artifact="../outside.txt")
        result = self.run_validate("change-impact-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("affected_artifacts", result.stderr)

    def test_validate_contracts_accepts_valid_dag_state(self):
        self.write_dag_state()
        result = self.run_validate("dag-state")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_invalid_dag_node_status(self):
        self.write_dag_state(node_status="done")
        result = self.run_validate("dag-state")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dag-state.nodes.mod_report_export.status", result.stderr)

    def test_validate_contracts_accepts_valid_execution_manifest(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)

        result = self.run_validate("execution")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("契约校验通过", result.stdout)

    def test_validate_contracts_blocks_system_payload_wrong_task_id(self):
        manifest_path, manifest = self.write_manifest_with_system_payloads()
        node = next(
            item for item in manifest["dag"]["nodes"]
            if item["id"] == "task_code_review"
        )
        node["payload"]["task_id"] = "wrong-task"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            f"task_code_review.payload.task_id 必须为 {self.task_id}",
            result.stderr,
        )

    def test_validate_contracts_blocks_system_payload_wrong_standard_path(self):
        manifest_path, manifest = self.write_manifest_with_system_payloads()
        node = next(
            item for item in manifest["dag"]["nodes"]
            if item["id"] == "task_merge"
        )
        node["payload"]["merged_dir"] = ".superlooper/merged/other-task"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            f"task_merge.payload.merged_dir 必须为 .superlooper/merged/{self.task_id}",
            result.stderr,
        )

    def test_validate_contracts_blocks_system_payload_missing_required_field(self):
        manifest_path, manifest = self.write_manifest_with_system_payloads()
        node = next(
            item for item in manifest["dag"]["nodes"]
            if item["id"] == "task_integration_test"
        )
        del node["payload"]["merge_report_path"]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "task_integration_test.payload 缺少系统执行锚点：merge_report_path",
            result.stderr,
        )

    def test_validate_contracts_blocks_apply_payload_overwrite_authorization(self):
        manifest_path, manifest = self.write_manifest_with_system_payloads()
        node = next(
            item for item in manifest["dag"]["nodes"]
            if item["id"] == "task_apply_to_workspace"
        )
        node["payload"]["overwrite_existing"] = True
        node["payload"]["overwrite_files"] = ["src/main/java/App.java"]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "task_apply_to_workspace.payload 禁止默认携带覆盖授权字段",
            result.stderr,
        )

    def test_validate_contracts_blocks_dynamic_agent_missing_constraints(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_path = self.runtime_root / "agents" / self.task_id / "module_report_export.md"
        content = runtime_path.read_text(encoding="utf-8")
        runtime_path.write_text(content.split("## Runtime Module Constraints", 1)[0], encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("动态 agent 缺少模块约束块", result.stderr)

    def test_validate_contracts_blocks_dynamic_agent_wrong_module_id_constraint(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_path = self.runtime_root / "agents" / self.task_id / "module_report_export.md"
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id / "module_report_export.md"
        for path in (runtime_path, registered_path):
            self.rewrite_agent_constraints(path, module_id="wrong_module")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("动态 agent 模块约束字段值或类型不一致：module_id", result.stderr)

    def test_validate_contracts_blocks_dynamic_agent_constraint_type_mismatch(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_path = self.runtime_root / "agents" / self.task_id / "module_report_export.md"
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id / "module_report_export.md"
        target_file = "src/main/java/com/example/controller/ReportExportController.java"
        for path in (runtime_path, registered_path):
            self.rewrite_agent_constraints(path, target_files=target_file)

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "动态 agent 模块约束字段值或类型不一致：target_files",
            result.stderr,
        )

    def test_validate_contracts_blocks_dynamic_agent_constraint_value_mismatch(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        runtime_path = self.runtime_root / "agents" / self.task_id / "module_report_export.md"
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id / "module_report_export.md"
        for path in (runtime_path, registered_path):
            self.rewrite_agent_constraints(path, test_focus=["错误测试重点"])

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "动态 agent 模块约束字段值或类型不一致：test_focus",
            result.stderr,
        )

    def test_validate_contracts_rejects_unscoped_claude_registered_name(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        registered_path = self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id / "module_report_export.md"
        self.replace_frontmatter_name(registered_path, "module_report_export")

        result = self.run_validate("execution")

        scoped_name = (
            "module_report_export__task_"
            + hashlib.sha256(self.task_id.encode("utf-8")).hexdigest()[:16]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"agent frontmatter name 必须为 {scoped_name}", result.stderr)

    def test_validate_contracts_blocks_module_payload_missing_task_id(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["dag"]["nodes"][0]["payload"]["task_id"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload 缺少模块执行锚点：task_id", result.stderr)

    def test_validate_contracts_blocks_module_payload_missing_traceability_anchor(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["dag"]["nodes"][0]["payload"]["requirement_refs"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload 缺少模块执行锚点：requirement_refs", result.stderr)

    def test_validate_contracts_blocks_module_payload_missing_file_roles_anchor(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["dag"]["nodes"][0]["payload"]["file_roles"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload 缺少模块执行锚点：file_roles", result.stderr)

    def test_validate_contracts_blocks_module_payload_ui_traceability_mismatch(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"][0]["payload"]["ui_refs"] = ["UI-PAGE-999"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload.ui_refs 必须与 module-split.modules[].ui_refs 一致", result.stderr)

    def test_validate_contracts_blocks_module_payload_string(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["dag"]["nodes"][0]["payload"] = "实现 report_export 模块"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload 必须是 object", result.stderr)

    def test_validate_contracts_blocks_failed_or_blocked_artifact(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["status"] = "blocked"
        artifact["verification"]["summary"] = "等待设计决策"
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status 为 blocked", result.stderr)

    def test_validate_contracts_blocks_undeclared_artifact_file(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        extra_file = self.outputs_dir / "report_export" / "src" / "main" / "java" / "com" / "example" / "controller" / "Extra.java"
        extra_file.parent.mkdir(parents=True, exist_ok=True)
        extra_file.write_text("public class Extra {}\n", encoding="utf-8")

        result = self.run_validate("artifacts")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未声明文件", result.stderr)

    def test_validate_contracts_rejects_windows_equivalent_actual_file_duplicates(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        controller_dir = (
            self.outputs_dir
            / "report_export"
            / "src"
            / "main"
            / "java"
            / "com"
            / "example"
            / "controller"
        )
        first_relative = "src/main/java/com/example/controller/StraßeController.java"
        second_relative = "src/main/java/com/example/controller/STRASSECONTROLLER.JAVA"
        (controller_dir / "StraßeController.java").write_text(
            "public class StraßeController {}\n",
            encoding="utf-8",
        )
        (controller_dir / "STRASSECONTROLLER.JAVA").write_text(
            "public class StrasseController {}\n",
            encoding="utf-8",
        )
        if len([path for path in controller_dir.iterdir() if "trasse" in path.name.casefold()]) < 2:
            self.skipTest("当前文件系统无法同时创建用于 Windows 等价冲突测试的两个文件")

        result = self.run_validate("artifacts", encoding="utf-8")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("模块实际文件存在 Windows 等价重复路径", result.stderr)
        self.assertIn(first_relative, result.stderr)
        self.assertIn(second_relative, result.stderr)

    def test_validate_contracts_accepts_windows_equivalent_artifact_target_membership(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["produced_files"][0]["path"] = (
            "SRC/main/java/com/example/controller/reportexportcontroller.java."
        )
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("artifacts")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_contracts_rejects_windows_equivalent_produced_file_duplicates(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        duplicate = dict(artifact["produced_files"][0])
        duplicate["path"] = (
            "SRC/main/java/com/example/controller/reportexportcontroller.java "
        )
        artifact["produced_files"].append(duplicate)
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate("artifacts")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("produced_files 存在重复路径", result.stderr)
        self.assertIn("reportexportcontroller.java ", result.stderr)

    def test_validate_contracts_accepts_pass_code_review_for_all_manifest_modules(self):
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        self.write_code_review_report("PASS")

        result = self.run_validate("code-review-report")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_contracts_blocks_pass_code_review_without_execution_manifest(self):
        self.write_code_review_report("PASS")

        result = self.run_validate("code-review-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Execution Manifest 文件不存在", result.stderr)

    def test_validate_contracts_blocks_pass_code_review_without_reviewed_modules(self):
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        self.write_code_review_report("PASS", reviewed_modules=[])

        result = self.run_validate("code-review-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code_review_status=PASS 时必须非空", result.stderr)

    def test_validate_contracts_blocks_duplicate_reviewed_modules(self):
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        self.write_code_review_report(
            "PASS",
            reviewed_modules=["report_export", "report_export"],
        )

        result = self.run_validate("code-review-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reviewed_modules 包含重复模块", result.stderr)

    def test_validate_contracts_blocks_pass_code_review_missing_manifest_module(self):
        module_split = json.loads(self.module_split_path.read_text(encoding="utf-8"))
        audit_module = json.loads(json.dumps(module_split["modules"][0]))
        audit_module["id"] = "audit_log"
        audit_module["name"] = "Audit Log"
        audit_module["target_files"] = [
            "src/main/java/com/example/controller/AuditLogController.java"
        ]
        audit_module["file_roles"] = [
            {
                "path": "src/main/java/com/example/controller/AuditLogController.java",
                "role": "controller",
            }
        ]
        audit_module["allowed_existing_files"] = list(audit_module["target_files"])
        module_split["modules"].append(audit_module)
        self.module_split_path.write_text(
            json.dumps(module_split, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        self.write_code_review_report("PASS", reviewed_modules=["report_export"])

        result = self.run_validate("code-review-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reviewed_modules 缺少模块：audit_log", result.stderr)

    def test_validate_contracts_blocks_pass_code_review_with_non_manifest_module(self):
        self.assertEqual(self.run_generate_manifest().returncode, 0)
        self.assertEqual(self.run_generate_agents().returncode, 0)
        self.write_code_review_report(
            "PASS",
            reviewed_modules=["report_export", "audit_log"],
        )

        result = self.run_validate("code-review-report")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reviewed_modules 包含非 Manifest 模块：audit_log", result.stderr)

    def test_validate_contracts_accepts_fail_code_review_for_rework_without_manifest(self):
        self.write_code_review_report("FAIL", reviewed_modules=["report_export"])

        result = self.run_validate("code-review-report")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_contracts_blocks_invalid_report_status_block(self):
        self.run_generate_manifest()
        self.run_generate_agents()
        self.write_code_review_report("UNKNOWN")

        result = self.run_validate("code-review-report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code_review_status", result.stderr)

    def test_validate_contracts_accepts_legacy_execution_identity_without_rewriting(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["session_id"] = manifest.pop("task_id")
        module_node = next(node for node in manifest["dag"]["nodes"] if node["id"].startswith("mod_"))
        module_node["payload"]["session_id"] = module_node["payload"].pop("task_id")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertEqual(result.returncode, 0, result.stderr)
        persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["session_id"], self.task_id)
        self.assertNotIn("task_id", persisted)
        persisted_node = next(node for node in persisted["dag"]["nodes"] if node["id"].startswith("mod_"))
        self.assertEqual(persisted_node["payload"]["session_id"], self.task_id)
        self.assertNotIn("task_id", persisted_node["payload"])

    def test_validate_contracts_rejects_dual_execution_identity(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        manifest_path = self.manifests_dir / "execution_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["session_id"] = self.task_id
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不能同时包含 task_id 和 legacy session_id", result.stderr)

    def test_validate_contracts_accepts_legacy_artifact_identity_without_rewriting(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["session_id"] = artifact.pop("task_id")
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("artifacts")

        self.assertEqual(result.returncode, 0, result.stderr)
        persisted = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["session_id"], self.task_id)
        self.assertNotIn("task_id", persisted)

    def test_validate_contracts_rejects_dual_artifact_identity(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        self.write_success_artifact()
        artifact_path = self.outputs_dir / "report_export" / "artifact_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["session_id"] = self.task_id
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = self.run_validate("artifacts")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不能同时包含 task_id 和 legacy session_id", result.stderr)

    def test_validate_contracts_accepts_legacy_runtime_agent_identity(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        paths = [
            self.runtime_root / "agents" / self.task_id / "module_report_export.md",
            self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id / "module_report_export.md",
        ]
        for path in paths:
            self.rewrite_agent_constraints(path, legacy_identity=True)

        result = self.run_validate("execution")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_contracts_rejects_dual_runtime_agent_identity(self):
        manifest_result = self.run_generate_manifest()
        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        agents_result = self.run_generate_agents()
        self.assertEqual(agents_result.returncode, 0, agents_result.stderr)
        paths = [
            self.runtime_root / "agents" / self.task_id / "module_report_export.md",
            self.workspace_root / ".claude" / "agents" / "generated" / "superlooper" / self.task_id / "module_report_export.md",
        ]
        for path in paths:
            self.rewrite_agent_constraints(
                path,
                legacy_identity=True,
                dual_identity=True,
            )

        result = self.run_validate("execution")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不能同时包含 task_id 和 legacy session_id", result.stderr)


if __name__ == "__main__":
    unittest.main()
