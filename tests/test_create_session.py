import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import create_session


class CreateSessionScriptTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.task_id = "session_create"
        self.requirement_path = self.workspace_root / "requirements.md"
        self.requirement_path.write_text("# demo\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, *args, env=None):
        script_path = self.repo_root / "scripts" / "create_session.py"
        process_env = os.environ.copy()
        process_env.pop("SUPERLOOPER_TASK_ID", None)
        process_env.pop("SUPERLOOPER_SESSION_ID", None)
        if env:
            process_env.update(env)
        return subprocess.run(
            [sys.executable, str(script_path), *args],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
            env=process_env,
        )

    def test_create_session_default_id_uses_local_timestamp_format(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--requirement-path",
            str(self.requirement_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r"^task_id: (master-framework-\d{14})$", result.stdout, re.MULTILINE)
        self.assertIsNotNone(match, result.stdout)
        task_id = match.group(1)
        self.assertTrue((self.workspace_root / ".superlooper" / "state" / f"{task_id}.json").is_file())

    def test_reserve_task_id_increments_state_and_reservation_collisions_without_overwrite(self):
        now = datetime(2026, 9, 10, 12, 34, 56)
        base_id = create_session.task_id_for_time(now)
        next_id = create_session.task_id_for_time(now + timedelta(seconds=1))

        state_workspace = self.workspace_root / "state-collision"
        state_path = state_workspace / ".superlooper" / "state" / f"{base_id}.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text("original-state", encoding="utf-8")
        reserved_id, reservation_path = create_session.reserve_task_id(state_workspace, now=now)
        self.assertEqual(reserved_id, next_id)
        self.assertEqual(state_path.read_text(encoding="utf-8"), "original-state")
        reservation_path.unlink()

        reservation_workspace = self.workspace_root / "reservation-collision"
        existing_reservation = reservation_workspace / ".superlooper" / "state" / f".{base_id}.reserve"
        existing_reservation.parent.mkdir(parents=True)
        existing_reservation.write_text("original-reservation", encoding="utf-8")
        reserved_id, reservation_path = create_session.reserve_task_id(reservation_workspace, now=now)
        self.assertEqual(reserved_id, next_id)
        self.assertEqual(existing_reservation.read_text(encoding="utf-8"), "original-reservation")
        reservation_path.unlink()

    def test_create_session_normalizes_unicode_task_name_and_allows_duplicates(self):
        for task_id in ("named-task-one", "named-task-two"):
            result = self.run_script(
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                task_id,
                "--task-name",
                "  发布 任务  ",
                "--requirement-path",
                str(self.requirement_path),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(
                (self.workspace_root / ".superlooper" / "state" / f"{task_id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["task_id"], task_id)
            self.assertEqual(state["task_name"], "发布 任务")

    def test_create_session_accepts_120_character_task_name_boundary(self):
        task_name = "任" * 120
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            "task-name-boundary",
            "--task-name",
            task_name,
            "--requirement-path",
            str(self.requirement_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(
            (self.workspace_root / ".superlooper" / "state" / "task-name-boundary.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["task_name"], task_name)

    def test_create_session_rejects_empty_control_separator_and_overlong_task_names(self):
        invalid_names = (
            "   ",
            "line\nbreak",
            "line\rbreak",
            "\ttrimmed",
            "line" + chr(0x85) + "break",
            "line" + chr(0x2028) + "break",
            "line" + chr(0x2029) + "break",
            "任" * 121,
        )
        for index, task_name in enumerate(invalid_names, start=1):
            with self.subTest(task_name=repr(task_name)):
                result = self.run_script(
                    "--workspace-root",
                    str(self.workspace_root),
                    "--task-id",
                    f"invalid-task-name-{index}",
                    "--task-name",
                    task_name,
                    "--requirement-path",
                    str(self.requirement_path),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("task_name", result.stderr)

    def test_create_session_treats_shell_metacharacters_as_task_name_data(self):
        task_name = '发布 "任务"; $(touch should-not-exist)'
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            "shell-safe-task-name",
            "--task-name",
            task_name,
            "--requirement-path",
            str(self.requirement_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(
            (self.workspace_root / ".superlooper" / "state" / "shell-safe-task-name.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["task_name"], task_name)
        self.assertFalse((self.repo_root / "should-not-exist").exists())

    def test_create_session_blocks_canonical_and_legacy_cli_environment_conflicts(self):
        cases = [
            (
                ["--task-id", "canonical-cli", "--session-id", "legacy-cli"],
                {},
            ),
            (
                ["--task-id", "canonical-cli"],
                {"SUPERLOOPER_SESSION_ID": "legacy-env"},
            ),
            (
                ["--session-id", "legacy-cli"],
                {"SUPERLOOPER_TASK_ID": "canonical-env"},
            ),
            (
                [],
                {"SUPERLOOPER_TASK_ID": "canonical-env", "SUPERLOOPER_SESSION_ID": "legacy-env"},
            ),
        ]
        for args, env in cases:
            with self.subTest(args=args, env=env):
                result = self.run_script(
                    "--workspace-root",
                    str(self.workspace_root),
                    *args,
                    "--requirement-path",
                    str(self.requirement_path),
                    env=env,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("不能同时指定不同值", result.stderr)

    def test_create_session_accepts_legacy_environment_task_id(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--requirement-path",
            str(self.requirement_path),
            env={"SUPERLOOPER_SESSION_ID": "legacy-env-task"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state_path = self.workspace_root / ".superlooper" / "state" / "legacy-env-task.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["task_id"], "legacy-env-task")
        self.assertNotIn("session_id", state)

    def test_new_task_ignores_identity_environment_and_rejects_explicit_identity(self):
        result = self.run_script(
            "--new-task",
            "--workspace-root",
            str(self.workspace_root),
            "--requirement-path",
            str(self.requirement_path),
            env={
                "SUPERLOOPER_TASK_ID": "host-task",
                "SUPERLOOPER_SESSION_ID": "host-session",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r"^task_id: (master-framework-\d{14})$", result.stdout, re.MULTILINE)
        self.assertIsNotNone(match, result.stdout)
        self.assertNotEqual(match.group(1), "host-task")
        self.assertFalse((self.workspace_root / ".superlooper" / "state" / "host-task.json").exists())

        conflict = self.run_script(
            "--new-task",
            "--task-id",
            "explicit-task",
            "--workspace-root",
            str(self.workspace_root),
            "--requirement-path",
            str(self.requirement_path),
        )
        self.assertNotEqual(conflict.returncode, 0)
        self.assertIn("--new-task", conflict.stderr)

    def test_existing_explicit_task_is_recovered_without_resetting_state(self):
        created = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(self.requirement_path),
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.task_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["current_phase"] = "ui_design"
        state["phase_status"] = "waiting_review"
        state["prd_revision"] = 3
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before = state_path.read_bytes()
        missing_dir = self.workspace_root / ".superlooper" / "reports" / self.task_id
        missing_dir.rmdir()

        recovered = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(self.requirement_path),
        )

        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertIn("state_created: no", recovered.stdout)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertTrue(missing_dir.is_dir())

    def test_existing_explicit_task_rejects_different_requirement_path(self):
        created = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(self.requirement_path),
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        other_requirement = self.workspace_root / "other-requirements.md"
        other_requirement.write_text("# other\n", encoding="utf-8")

        recovered = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(other_requirement),
        )

        self.assertNotEqual(recovered.returncode, 0)
        self.assertIn("requirement_path", recovered.stderr)

    def test_create_session_failure_cleans_reservation_and_only_new_empty_task_directories(self):
        task_id = "cleanup-task"
        runtime_root = self.workspace_root / ".superlooper"
        preexisting_path = runtime_root / "context" / task_id
        preexisting_path.mkdir(parents=True)
        args = SimpleNamespace(
            workspace_root=str(self.workspace_root),
            task_id=task_id,
            session_id=None,
            new_task=False,
            task_name=None,
            requirement_path=str(self.requirement_path),
            project_mode="greenfield",
        )

        with mock.patch.object(create_session, "parse_args", return_value=args), mock.patch.object(
            create_session, "write_state", side_effect=create_session.SessionCreateError("forced failure")
        ):
            result = create_session.main()

        self.assertEqual(result, 1)
        self.assertTrue(preexisting_path.is_dir())
        for parent in ("reports", "manifests", "agents", "outputs"):
            self.assertFalse((runtime_root / parent / task_id).exists())
        self.assertFalse((runtime_root / "state" / f".{task_id}.reserve").exists())
        self.assertFalse((runtime_root / "state" / f"{task_id}.json").exists())

    def test_create_session_creates_runtime_layout_and_initial_state(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(self.requirement_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        runtime_root = self.workspace_root / ".superlooper"
        expected_dirs = [
            runtime_root / "context" / self.task_id,
            runtime_root / "reports" / self.task_id,
            runtime_root / "manifests" / self.task_id,
            runtime_root / "agents" / self.task_id,
            runtime_root / "outputs" / self.task_id,
            runtime_root / "state",
        ]
        for path in expected_dirs:
            self.assertTrue(path.is_dir(), path)

        state_path = runtime_root / "state" / f"{self.task_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["task_id"], self.task_id)
        self.assertIsNone(state["task_name"])
        self.assertEqual(state["workspace_root"], str(self.workspace_root.resolve()))
        self.assertEqual(state["requirement_path"], str(self.requirement_path.resolve()))
        self.assertEqual(state["current_phase"], "prd")
        self.assertEqual(state["phase_status"], "pending")
        self.assertEqual(state["generated_files"], [])
        self.assertEqual(state["reports"], [])
        self.assertEqual(state["last_command"], "create_session")
        self.assertIsNone(state["last_error"])
        self.assertEqual(state["next_actions"], ["运行 /spl:prd 进入需求分析阶段"])
        self.assertEqual(state["project_mode"], "greenfield")
        self.assertEqual(state["workflow_mode"], "standard")
        self.assertIsNone(state["project_category"])
        self.assertIsNone(state["project_version"])
        self.assertIsNone(state["project_root"])
        self.assertFalse(state["project_initialized"])
        self.assertIsNone(state["initialization_report"])
        self.assertEqual(state["execution_summary_status"], "NOT_STARTED")
        self.assertIsNone(state["execution_summary_report"])
        self.assertEqual(state["loop_policy"], {"max_auto_loop_per_phase": 2})
        self.assertEqual(
            state["loop_state"],
            {
                "current_loop_target_phase": None,
                "loop_count_by_phase": {},
                "last_alignment_status": None,
                "last_feedback_report": None,
            },
        )
        self.assertIsNone(state["requirement_alignment_report"])
        self.assertFalse(state["requirement_alignment_passed"])
        self.assertEqual(state["prd_revision"], 0)
        self.assertEqual(state["ui_revision"], 0)
        self.assertEqual(state["ui_status"], "NOT_STARTED")
        self.assertIsNone(state["ui_output_dir"])
        self.assertFalse(state["ui_artifacts_validated"])
        self.assertEqual(state["design_revision"], 0)
        self.assertEqual(state["change_request_count"], 0)
        self.assertIsNone(state["active_feedback_report"])
        self.assertIsNone(state["change_impact_report"])
        self.assertEqual(state["invalidated_artifacts"], [])
        self.assertIsNone(state["rollback_target_phase"])
        self.assertIsNone(state["last_user_input_text"])
        self.assertIsNone(state["last_user_canonical_action"])
        self.assertIsNone(state["pending_user_choice"])

    def test_validate_session_state_only_backfills_legacy_affected_modules(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(self.requirement_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.task_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))

        canonical = dict(state)
        canonical.pop("affected_modules")
        with self.assertRaisesRegex(create_session.SessionStateValidationError, "affected_modules"):
            create_session.validate_session_state(canonical)

        legacy = dict(state)
        legacy["session_id"] = legacy.pop("task_id")
        legacy.pop("task_name")
        legacy.pop("affected_modules")
        normalized = create_session.validate_session_state(legacy)
        self.assertEqual(normalized["task_id"], self.task_id)
        self.assertIsNone(normalized["task_name"])
        self.assertEqual(normalized["affected_modules"], [])

    def test_validate_session_state_rejects_duplicate_affected_modules(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(self.requirement_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state_path = self.workspace_root / ".superlooper" / "state" / f"{self.task_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["affected_modules"] = ["report_export", "report_export"]

        with self.assertRaisesRegex(create_session.SessionStateValidationError, "affected_modules"):
            create_session.validate_session_state(state)

    def test_create_session_rejects_dot_and_dotdot_task_ids(self):
        for task_id in (".", ".."):
            with self.subTest(task_id=task_id):
                result = self.run_script(
                    "--workspace-root",
                    str(self.workspace_root),
                    "--task-id",
                    task_id,
                    "--requirement-path",
                    str(self.requirement_path),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("task_id", result.stderr)

    def test_create_session_rejects_relative_requirement_path_with_parent_segment(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            "../requirements.md",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path", result.stderr)

    def test_create_session_rejects_windows_equivalent_protected_requirement_roots(self):
        for requirement_path in (
            ".GIT/config",
            ".git./config",
            ".git /config",
            ".git\\config",
        ):
            with self.subTest(requirement_path=requirement_path):
                with self.assertRaisesRegex(
                    create_session.SessionCreateError,
                    "requirement_path 不是安全路径",
                ):
                    create_session.resolve_requirement_path(
                        self.workspace_root,
                        requirement_path,
                    )

    def test_create_session_allows_absolute_requirement_outside_workspace(self):
        with tempfile.TemporaryDirectory() as outside_dir:
            outside_requirement = Path(outside_dir) / "requirements.md"
            outside_requirement.write_text("# outside\n", encoding="utf-8")

            result = self.run_script(
                "--workspace-root",
                str(self.workspace_root),
                "--task-id",
                "external-requirement",
                "--requirement-path",
                str(outside_requirement),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        state_path = (
            self.workspace_root
            / ".superlooper"
            / "state"
            / "external-requirement.json"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            state["requirement_path"],
            str(outside_requirement.resolve()),
        )

    def test_create_session_rejects_missing_requirement_path(self):
        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(self.workspace_root / "missing.md"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path 不存在", result.stderr)

    def test_create_session_rejects_directory_requirement_path(self):
        requirement_dir = self.workspace_root / "requirements-dir"
        requirement_dir.mkdir()

        result = self.run_script(
            "--workspace-root",
            str(self.workspace_root),
            "--task-id",
            self.task_id,
            "--requirement-path",
            str(requirement_dir),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirement_path 必须是文件", result.stderr)


if __name__ == "__main__":
    unittest.main()
