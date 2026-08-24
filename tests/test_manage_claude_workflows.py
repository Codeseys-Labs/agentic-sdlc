"""Per-file ownership of a target repository's `.claude/workflows/`, on the hook manager's discipline.

The unit of ownership here is ONE FILE in the TARGET repository — the host's Workflow name
registry reads only a project's own `.claude/workflows/` at session start, and a project's own
workflow files legitimately live beside the managed copy — so every test asks a file-scale
question: does activate place exactly one self-contained copy and leave every neighbour intact,
does deactivate remove only the copy still byte-identical to its receipt, is a foreign or
modified file preserved and reported rather than guessed at, and does the manager refuse to
enable workflow bytes the bundle lifecycle does not currently own?
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "manage_claude_workflows.py"
spec = importlib.util.spec_from_file_location("manage_workflows", SCRIPT)
assert spec and spec.loader
manage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = manage
spec.loader.exec_module(manage)
import install_skill_bundle as installer


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = _load("workflow_enablement_validator", ROOT / "scripts" / "validate_bundle.py")


WORKFLOW_TEXT = (
    "// workflow: wave\n"
    "export const meta = { name: 'wave', description: 'map one wave' };\n"
    "const plan = await agent('map the wave', options);\n"
    "return plan;\n"
)
REVISED_TEXT = (
    "// workflow: wave\n"
    "export const meta = { name: 'wave', description: 'map one wave' };\n"
    "const plan = await agent('map the wave twice', options);\n"
    "return plan;\n"
)
FOREIGN_TEXT = "// workflow: wave\n// someone else's overlay\n"


class ManageClaudeWorkflowsTests(unittest.TestCase):
    maxDiff = None

    def setup_environment(self, root: Path, *, install: bool = True):
        """Build a fake repo shipping one workflow, install it, and return the manager's inputs."""
        repo = root / "repo"
        (repo / "workflows").mkdir(parents=True)
        (repo / "workflows" / "wave.js").write_text(WORKFLOW_TEXT, encoding="utf-8")
        state = root / "state"
        config = installer.Config(repo, root / "home", root / "codex", "copy", False, "claude", state)
        if install:
            self.assertEqual(installer.install(config).exit_code, 0)
        workflows_dir = root / "home" / ".claude" / "workflows"
        target = root / "project"
        target.mkdir()
        return target, workflows_dir, state, config

    def destination(self, target: Path) -> Path:
        return target / ".claude" / "workflows" / "wave.js"

    def test_activate_places_exactly_one_file_and_preserves_every_neighbour(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            neighbour = destination.parent / "someone-elses.js"
            destination.parent.mkdir(parents=True)
            neighbour.write_text("// workflow: someone-elses\n", encoding="utf-8")

            code, messages = manage.activate("wave", target, workflows_dir, state, False)

            self.assertEqual(code, 0, messages)
            self.assertEqual(destination.read_text(encoding="utf-8"), WORKFLOW_TEXT)
            self.assertFalse(destination.is_symlink(), "the enabled entry must be a self-contained copy")
            self.assertEqual(neighbour.read_text(encoding="utf-8"), "// workflow: someone-elses\n")
            self.assertEqual(sorted(path.name for path in destination.parent.iterdir()), ["someone-elses.js", "wave.js"])
            receipt = json.loads(manage.receipt_path(state, "wave", destination).read_text())
            self.assertEqual(receipt["phase"], "committed")
            self.assertEqual(receipt["target"], str(destination))
            self.assertEqual(receipt["workflow_digest"], manage.settings_io.digest_bytes(WORKFLOW_TEXT.encode()))

    def test_activate_and_deactivate_name_the_session_start_snapshot(self) -> None:
        """The de40 seed requires the step's OUTPUT to state the session-start snapshot fact."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)

            code, messages = manage.activate("wave", target, workflows_dir, state, False)
            self.assertEqual(code, 0, messages)
            self.assertIn(manage.SESSION_SNAPSHOT_NOTE, messages)
            self.assertIn("session start", manage.SESSION_SNAPSHOT_NOTE)
            self.assertIn("next Claude Code session", manage.SESSION_SNAPSHOT_NOTE)

            code, messages = manage.deactivate("wave", target, state, False)
            self.assertEqual(code, 0, messages)
            self.assertIn(manage.SESSION_SNAPSHOT_NOTE, messages)

    def test_a_second_activate_reports_already_active_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)
            before = destination.read_bytes()
            receipt_before = manage.receipt_path(state, "wave", destination).read_bytes()

            code, messages = manage.activate("wave", target, workflows_dir, state, False)

            self.assertEqual(code, 0)
            self.assertTrue(any("already active" in message for message in messages), messages)
            self.assertEqual(destination.read_bytes(), before)
            self.assertEqual(manage.receipt_path(state, "wave", destination).read_bytes(), receipt_before)

    def test_an_unmanaged_byte_identical_copy_is_already_active_and_claims_no_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            destination.parent.mkdir(parents=True)
            destination.write_text(WORKFLOW_TEXT, encoding="utf-8")

            code, messages = manage.activate("wave", target, workflows_dir, state, False)

            self.assertEqual(code, 0)
            self.assertTrue(any("already active" in message for message in messages), messages)
            # Writing a receipt would claim ownership of a file this manager never placed, so
            # deactivate must later treat it as unmanaged rather than remove it.
            self.assertFalse(manage.receipt_path(state, "wave", destination).exists())
            code, messages = manage.deactivate("wave", target, state, False)
            self.assertEqual(code, 0)
            self.assertEqual(messages, ["workflow wave is not managed for this target"])
            self.assertEqual(destination.read_text(encoding="utf-8"), WORKFLOW_TEXT)

    def test_deactivate_removes_only_the_receipt_copy_and_restores_the_prestate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            neighbour = destination.parent / "someone-elses.js"
            destination.parent.mkdir(parents=True)
            neighbour.write_text("// workflow: someone-elses\n", encoding="utf-8")
            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)

            code, messages = manage.deactivate("wave", target, state, False)

            self.assertEqual(code, 0, messages)
            self.assertFalse(destination.exists())
            self.assertEqual(neighbour.read_text(encoding="utf-8"), "// workflow: someone-elses\n")
            self.assertTrue(destination.parent.is_dir(), "a pre-existing collection must survive")
            self.assertFalse(manage.receipt_path(state, "wave", destination).exists())

    def test_created_containers_are_removed_and_preexisting_ones_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)

            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)
            self.assertTrue(destination.is_file())
            self.assertEqual(manage.deactivate("wave", target, state, False)[0], 0)
            # Both containers were created at activation, so the round trip restores exactly
            # the empty target.
            self.assertFalse((target / ".claude").exists())
            self.assertEqual(sorted(target.iterdir()), [])

            # Positive control: a pre-existing empty collection survives the same round trip.
            destination.parent.mkdir(parents=True)
            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)
            self.assertEqual(manage.deactivate("wave", target, state, False)[0], 0)
            self.assertTrue(destination.parent.is_dir())
            self.assertEqual(sorted(destination.parent.iterdir()), [])

    def test_an_occupied_foreign_destination_is_refused_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            destination.parent.mkdir(parents=True)
            destination.write_text(FOREIGN_TEXT, encoding="utf-8")

            with self.assertRaisesRegex(manage.WorkflowsError, "occupied by a foreign workflow file"):
                manage.activate("wave", target, workflows_dir, state, False)

            self.assertEqual(destination.read_text(encoding="utf-8"), FOREIGN_TEXT)
            self.assertFalse(manage.receipt_path(state, "wave", destination).exists())
            # Positive control: the same activate succeeds once the foreign file is gone, so the
            # refusal above is about occupancy and not a manager that can never activate.
            destination.unlink()
            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)

    def test_a_modified_enabled_copy_is_preserved_and_the_receipt_released_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)
            destination.write_text(WORKFLOW_TEXT + "// operator edit\n", encoding="utf-8")

            # Re-activating over the operator's edit must refuse rather than clobber.
            with self.assertRaisesRegex(manage.WorkflowsError, "modified after activation"):
                manage.activate("wave", target, workflows_dir, state, False)

            code, messages = manage.deactivate("wave", target, state, False)

            self.assertEqual(code, 0, messages)
            self.assertTrue(any("released" in message for message in messages), messages)
            self.assertTrue(any("preserved" in message for message in messages), messages)
            self.assertEqual(destination.read_text(encoding="utf-8"), WORKFLOW_TEXT + "// operator edit\n")
            self.assertFalse(manage.receipt_path(state, "wave", destination).exists())

    def test_activate_refuses_an_absent_unowned_or_drifted_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            source = workflows_dir / "wave.js"
            destination = self.destination(target)

            # Drifted: the installed copy no longer matches its ownership record's digest.
            source.write_text(WORKFLOW_TEXT + "// drift\n", encoding="utf-8")
            with self.assertRaisesRegex(manage.WorkflowsError, "drifted from its ownership record"):
                manage.activate("wave", target, workflows_dir, state, False)

            # Absent: the owned record exists but the bytes are gone.
            source.unlink()
            with self.assertRaisesRegex(manage.WorkflowsError, "installed workflow is absent"):
                manage.activate("wave", target, workflows_dir, state, False)

            # Unowned: bytes exist at the source but no lifecycle record covers them.
            source.write_text(WORKFLOW_TEXT, encoding="utf-8")
            with self.assertRaisesRegex(manage.WorkflowsError, "not owned by the bundle lifecycle"):
                manage.activate("wave", target, workflows_dir, root / "other-state", False)

            self.assertFalse((target / ".claude").exists(), "every refusal must precede any write")
            # Positive control: with the owned bytes restored the same activate succeeds, so the
            # refusals above are the guards and not a manager that can never activate.
            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)
            self.assertEqual(destination.read_text(encoding="utf-8"), WORKFLOW_TEXT)

    def test_a_refreshed_source_replaces_only_a_receipt_matched_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, config = self.setup_environment(root)
            destination = self.destination(target)
            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)

            # The bundle moves on: the authored source changes and the lifecycle refreshes its
            # owned home-plane copy, so the record's digest now names the revised bytes.
            (config.repo_root / "workflows" / "wave.js").write_text(REVISED_TEXT, encoding="utf-8")
            self.assertEqual(installer.install(config).exit_code, 0)

            code, messages = manage.activate("wave", target, workflows_dir, state, False)

            self.assertEqual(code, 0, messages)
            self.assertTrue(any(message.startswith("refreshed:") for message in messages), messages)
            self.assertEqual(destination.read_text(encoding="utf-8"), REVISED_TEXT)
            receipt = json.loads(manage.receipt_path(state, "wave", destination).read_text())
            self.assertEqual(receipt["workflow_digest"], manage.settings_io.digest_bytes(REVISED_TEXT.encode()))

            # Negative control: the refresh path never overwrites an operator-modified copy.
            destination.write_text(REVISED_TEXT + "// operator edit\n", encoding="utf-8")
            with self.assertRaisesRegex(manage.WorkflowsError, "modified after activation"):
                manage.activate("wave", target, workflows_dir, state, False)
            self.assertEqual(destination.read_text(encoding="utf-8"), REVISED_TEXT + "// operator edit\n")

    def test_deactivating_an_unmanaged_workflow_is_the_end_state_not_a_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            del workflows_dir

            code, messages = manage.deactivate("wave", target, state, False)

            self.assertEqual(code, 0)
            self.assertEqual(messages, ["workflow wave is not managed for this target"])

    def test_a_receipt_for_a_different_destination_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            other_destination = root / "other-project" / ".claude" / "workflows" / "wave.js"
            forged = {
                "version": manage.RECEIPT_VERSION,
                "phase": "committed",
                "target": str(other_destination),
                "workflow": "wave",
                "workflow_digest": "0" * 64,
                "created_claude_dir": False,
                "created_workflows_dir": False,
            }
            receipt_file = manage.receipt_path(state, "wave", destination)
            receipt_file.parent.mkdir(parents=True)
            receipt_file.write_text(json.dumps(forged), encoding="utf-8")

            with self.assertRaisesRegex(manage.WorkflowsError, "different destination path"):
                manage.deactivate("wave", target, state, False)
            with self.assertRaisesRegex(manage.WorkflowsError, "different destination path"):
                manage.activate("wave", target, workflows_dir, state, False)

    def test_dry_run_previews_both_verbs_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)

            code, messages = manage.activate("wave", target, workflows_dir, state, True)
            self.assertEqual(code, 0)
            self.assertTrue(messages[0].startswith("would activate:"), messages)
            self.assertFalse((target / ".claude").exists())
            self.assertFalse(manage.receipt_path(state, "wave", destination).exists())

            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)
            code, messages = manage.deactivate("wave", target, state, True)
            self.assertEqual(code, 0)
            self.assertTrue(messages[0].startswith("would deactivate:"), messages)
            self.assertEqual(destination.read_text(encoding="utf-8"), WORKFLOW_TEXT)

    def test_a_crash_between_receipt_arm_and_placement_recovers_on_rerun(self) -> None:
        """Pending-slot crash consistency, driven through the real code path: the first
        `atomic_bytes` call in a transaction writes the pending receipt (via atomic_json) and the
        second writes the destination, so failing exactly the second models a crash inside the
        window."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)

            real = manage.settings_io.atomic_bytes

            def crash_on_placement(path, content, mode, expected=None):
                if path == destination:
                    raise OSError("simulated crash")
                return real(path, content, mode, expected)

            with mock.patch.object(manage.settings_io, "atomic_bytes", side_effect=crash_on_placement):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    manage.activate("wave", target, workflows_dir, state, False)

            receipt = json.loads(manage.receipt_path(state, "wave", destination).read_text())
            self.assertEqual(receipt["phase"], "pending")
            self.assertFalse(destination.exists(), "the crash left the target at the prestate")

            # A dry run must demand recovery rather than planning over an armed transaction.
            with self.assertRaisesRegex(manage.WorkflowsError, "requires recovery"):
                manage.activate("wave", target, workflows_dir, state, True)

            status_code, status_messages = manage.status(target, workflows_dir, state, None)
            self.assertEqual(status_code, 0)
            self.assertTrue(any("recovery pending" in message for message in status_messages), status_messages)

            # The rerun resolves the armed slot (the destination matches `before`, so the
            # activate aborts cleanly) and then performs the activation it was asked for.
            code, messages = manage.activate("wave", target, workflows_dir, state, False)
            self.assertEqual(code, 0, messages)
            self.assertEqual(destination.read_text(encoding="utf-8"), WORKFLOW_TEXT)
            self.assertEqual(
                json.loads(manage.receipt_path(state, "wave", destination).read_text())["phase"], "committed"
            )

    def test_a_destination_change_mid_activate_is_preserved_and_the_receipt_disarmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)

            real = manage.settings_io.atomic_bytes

            def racing_edit(path, content, mode, expected=None):
                if path == destination:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(FOREIGN_TEXT, encoding="utf-8")
                return real(path, content, mode, expected)

            with mock.patch.object(manage.settings_io, "atomic_bytes", side_effect=racing_edit):
                with self.assertRaisesRegex(manage.settings_io.SettingsChangedError, "preserving operator edit"):
                    manage.activate("wave", target, workflows_dir, state, False)

            self.assertEqual(destination.read_text(encoding="utf-8"), FOREIGN_TEXT)
            self.assertFalse(
                manage.receipt_path(state, "wave", destination).exists(), "the armed receipt must be disarmed"
            )

    def test_status_reports_each_state_and_always_ends_with_one_terminal_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            destination.parent.mkdir(parents=True)
            (destination.parent / "someone-elses.js").write_text("// workflow: someone-elses\n", encoding="utf-8")

            code, messages = manage.status(target, workflows_dir, state, None)
            self.assertEqual(code, 0)
            self.assertIn("workflow wave: installed, inactive", messages)
            self.assertIn(f"foreign workflow files in {destination.parent}: 1 (preserved)", messages)
            self.assertEqual(messages[-1], "0 active, 1 inactive, 0 conflict")

            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)
            code, messages = manage.status(target, workflows_dir, state, None)
            self.assertIn("workflow wave: installed, active", messages)
            self.assertEqual(messages[-1], "1 active, 0 inactive, 0 conflict")

            # An operator removing the copy by hand turns the receipt into a named conflict.
            destination.unlink()
            code, messages = manage.status(target, workflows_dir, state, None)
            self.assertTrue(
                any("receipt without its enabled copy" in message for message in messages), messages
            )
            self.assertEqual(messages[-1], "0 active, 0 inactive, 1 conflict")

            # A drifted installed source is reported without blocking the read.
            (workflows_dir / "wave.js").write_text(WORKFLOW_TEXT + "// drift\n", encoding="utf-8")
            code, messages = manage.status(target, workflows_dir, state, None)
            self.assertTrue(any("drifted from its ownership record" in message for message in messages), messages)

    def test_status_on_an_empty_plane_still_ends_with_one_terminal_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root, install=False)

            code, messages = manage.status(target, workflows_dir, state, None)

            self.assertEqual(code, 0)
            self.assertEqual(len(messages), 1)
            self.assertTrue(messages[0].startswith("no owned workflows for this plane"), messages)

    def test_main_wires_the_cli_and_refuses_malformed_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            destination = self.destination(target)
            base = ["--home", str(root / "home"), "--state-root", str(state), "--target", str(target)]

            self.assertEqual(manage.main(["activate", "--workflow", "wave", *base]), 0)
            self.assertEqual(destination.read_text(encoding="utf-8"), WORKFLOW_TEXT)
            self.assertEqual(manage.main(["status", *base]), 0)
            self.assertEqual(manage.main(["deactivate", "--workflow", "wave", *base]), 0)
            self.assertFalse(destination.exists())

            # A missing or non-slug --workflow is a refusal at EXIT_REFUSED, before any write.
            self.assertEqual(manage.main(["activate", *base]), 2)
            self.assertEqual(manage.main(["activate", "--workflow", "../wave", *base]), 2)
            self.assertEqual(manage.main(["deactivate", *base]), 2)

            # A missing target directory and the installed home plane itself are refusals.
            missing = ["--home", str(root / "home"), "--state-root", str(state), "--target", str(root / "nowhere")]
            self.assertEqual(manage.main(["activate", "--workflow", "wave", *missing]), 2)
            home_plane = ["--home", str(root / "home"), "--state-root", str(state), "--target", str(root / "home")]
            self.assertEqual(manage.main(["activate", "--workflow", "wave", *home_plane]), 2)

            # --target is required by the parser itself and refuses at the same exit code.
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    manage.main(["status", "--home", str(root / "home"), "--state-root", str(state)])
            self.assertEqual(raised.exception.code, 2)

    def test_the_claude_config_dir_override_moves_the_workflow_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            del workflows_dir
            argv = [
                "activate", "--workflow", "wave",
                "--home", str(root / "elsewhere"),
                "--claude-config-dir", str(root / "home" / ".claude"),
                "--state-root", str(state),
                "--target", str(target),
            ]

            self.assertEqual(manage.main(argv), 0)

            self.assertEqual(self.destination(target).read_text(encoding="utf-8"), WORKFLOW_TEXT)

    def test_the_placed_file_satisfies_the_validator_discovery_grammar(self) -> None:
        """Discovery contract: the enabled copy must pass the same authored-shape grammar the
        gate holds `workflows/*.js` to, because the placed file IS what a target session loads."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, workflows_dir, state, _ = self.setup_environment(root)
            self.assertEqual(manage.activate("wave", target, workflows_dir, state, False)[0], 0)
            placed = self.destination(target).read_text(encoding="utf-8")

            self.assertIsNone(validator.workflow_meta_violation(placed, "wave"))
            self.assertTrue(placed.startswith("// workflow: wave\n"))

        # Positive control on the grammar itself: a meta-less document is a named violation, so
        # the None above is the grammar passing and not a check that never bites.
        self.assertEqual(
            validator.workflow_meta_violation("// workflow: wave\nconst x = 1;\n", "wave"),
            validator.WORKFLOW_META_FIRST_STATEMENT_ERROR,
        )

    def test_the_required_mise_tasks_include_the_workflow_manager_verbs(self) -> None:
        for task in ("claude:workflows:status", "claude:workflows:activate", "claude:workflows:deactivate"):
            self.assertIn(task, validator.REQUIRED_TASKS)


if __name__ == "__main__":
    unittest.main()
