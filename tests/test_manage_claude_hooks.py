"""Per-element ownership of the settings `hooks` arrays, on the statusline manager's discipline.

The unit of ownership here is ONE ELEMENT of a `hooks.<Event>` array — the platform merges those
arrays across scopes and a user's own entries legitimately live beside the managed one — so every
test asks an element-scale question: does activate append exactly one element and leave every
neighbour intact, does deactivate remove only the deep-equal receipt element, is a foreign or
modified element preserved and reported rather than guessed at, and does the manager refuse to
wire hook bytes the bundle lifecycle does not currently own?
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "manage_claude_hooks.py"
spec = importlib.util.spec_from_file_location("manage_hooks", SCRIPT)
assert spec and spec.loader
manage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = manage
spec.loader.exec_module(manage)
import install_skill_bundle as installer


HOOK_TEXT = (
    "#!/bin/sh\n"
    "# hook: primer\n"
    "# hook-event: SessionStart\n"
    "# hook-matcher: startup|resume|clear\n"
    "exit 0\n"
)
USER_ELEMENT = {"matcher": "compact", "hooks": [{"type": "command", "command": "echo user"}]}


class ManageClaudeHooksTests(unittest.TestCase):
    maxDiff = None

    def setup_environment(self, root: Path, *, install: bool = True):
        """Build a fake repo shipping one hook, install it, and return the manager's inputs."""
        repo = root / "repo"
        (repo / "hooks").mkdir(parents=True)
        (repo / "hooks" / "primer.sh").write_text(HOOK_TEXT, encoding="utf-8")
        state = root / "state"
        config = installer.Config(repo, root / "home", root / "codex", "copy", False, "claude", state)
        if install:
            self.assertEqual(installer.install(config).exit_code, 0)
        settings = root / "home" / ".claude" / "settings.json"
        hooks_dir = root / "home" / ".claude" / "hooks"
        return settings, hooks_dir, state

    def managed_element(self, hooks_dir: Path) -> dict:
        return {
            "matcher": "startup|resume|clear",
            "hooks": [{"type": "command", "command": f"sh {shlex.quote(str(hooks_dir / 'primer.sh'))}"}],
        }

    def test_activate_appends_exactly_one_element_and_preserves_every_neighbour(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            original = {
                "model": "fable",
                "hooks": {
                    "SessionStart": [USER_ELEMENT],
                    "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo pre"}]}],
                },
            }
            settings.write_text(json.dumps(original))

            code, messages = manage.activate("primer", settings, hooks_dir, state, False)

            self.assertEqual(code, 0, messages)
            document = json.loads(settings.read_text())
            self.assertEqual(document["model"], "fable")
            self.assertEqual(document["hooks"]["PreToolUse"], original["hooks"]["PreToolUse"])
            self.assertEqual(len(document["hooks"]["SessionStart"]), 2)
            self.assertEqual(document["hooks"]["SessionStart"][0], USER_ELEMENT)
            self.assertEqual(document["hooks"]["SessionStart"][1], self.managed_element(hooks_dir))

    def test_a_second_activate_reports_already_active_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))
            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)
            before = settings.read_bytes()

            code, messages = manage.activate("primer", settings, hooks_dir, state, False)

            self.assertEqual(code, 0)
            self.assertTrue(any("already active" in message for message in messages), messages)
            self.assertEqual(settings.read_bytes(), before)

    def test_deactivate_removes_only_the_receipt_element_and_restores_the_prestate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            original = {"hooks": {"SessionStart": [USER_ELEMENT]}, "model": "fable"}
            settings.write_text(json.dumps(original))
            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)

            code, messages = manage.deactivate("primer", settings, state, False)

            self.assertEqual(code, 0, messages)
            self.assertEqual(json.loads(settings.read_text()), original)
            self.assertFalse(manage.receipt_path(state, "primer").exists())

    def test_created_container_keys_are_removed_and_preexisting_ones_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))

            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)
            self.assertEqual(
                json.loads(settings.read_text()),
                {"hooks": {"SessionStart": [self.managed_element(hooks_dir)]}},
            )
            self.assertEqual(manage.deactivate("primer", settings, state, False)[0], 0)
            # Both containers were created at activation, so the round trip restores exactly {}.
            self.assertEqual(json.loads(settings.read_text()), {})

            # Positive control: a preexisting empty event array survives the same round trip.
            settings.write_text(json.dumps({"hooks": {"SessionStart": []}}))
            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)
            self.assertEqual(manage.deactivate("primer", settings, state, False)[0], 0)
            self.assertEqual(json.loads(settings.read_text()), {"hooks": {"SessionStart": []}})

    def test_a_foreign_hooks_shape_is_refused_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({"hooks": ["not", "an", "object"]}))

            with self.assertRaisesRegex(manage.HooksError, "must be a JSON object"):
                manage.activate("primer", settings, hooks_dir, state, False)
            self.assertEqual(json.loads(settings.read_text()), {"hooks": ["not", "an", "object"]})

            settings.write_text(json.dumps({"hooks": {"SessionStart": {"matcher": "startup"}}}))
            with self.assertRaisesRegex(manage.HooksError, "must be a JSON array"):
                manage.activate("primer", settings, hooks_dir, state, False)
            self.assertFalse(manage.receipt_path(state, "primer").exists())

    def test_a_modified_element_is_preserved_and_the_receipt_is_released_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))
            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)
            document = json.loads(settings.read_text())
            document["hooks"]["SessionStart"][0]["matcher"] = "startup"
            settings.write_text(json.dumps(document))

            code, messages = manage.deactivate("primer", settings, state, False)

            self.assertEqual(code, 0, messages)
            self.assertTrue(any("released" in message for message in messages), messages)
            self.assertTrue(any("preserved" in message for message in messages), messages)
            self.assertEqual(json.loads(settings.read_text()), document)
            self.assertFalse(manage.receipt_path(state, "primer").exists())

    def test_activate_refuses_an_absent_unowned_or_drifted_hook_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))
            destination = hooks_dir / "primer.sh"

            # Drifted: the installed copy no longer matches its ownership record's digest.
            destination.write_text(HOOK_TEXT + "# drift\n", encoding="utf-8")
            with self.assertRaisesRegex(manage.HooksError, "drifted from its ownership record"):
                manage.activate("primer", settings, hooks_dir, state, False)

            # Absent: the owned record exists but the bytes are gone.
            destination.unlink()
            with self.assertRaisesRegex(manage.HooksError, "installed hook is absent"):
                manage.activate("primer", settings, hooks_dir, state, False)

            # Unowned: bytes exist at the destination but no lifecycle record covers them.
            destination.write_text(HOOK_TEXT, encoding="utf-8")
            with self.assertRaisesRegex(manage.HooksError, "not owned by the bundle lifecycle"):
                manage.activate("primer", settings, hooks_dir, root / "other-state", False)

            self.assertEqual(json.loads(settings.read_text()), {}, "every refusal must precede any write")
            # Positive control: with the owned bytes restored the same activate succeeds, so the
            # refusals above are the guards and not a manager that can never activate.
            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)

    def test_deactivating_an_unmanaged_hook_is_the_end_state_not_a_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))

            code, messages = manage.deactivate("primer", settings, state, False)

            self.assertEqual(code, 0)
            self.assertEqual(messages, ["hook primer is not managed"])

    def test_a_receipt_for_a_different_settings_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))
            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)

            other = root / "home" / ".claude" / "other-settings.json"
            other.write_text(json.dumps({}))
            with self.assertRaisesRegex(manage.HooksError, "different Claude settings path"):
                manage.deactivate("primer", other, state, False)

    def test_dry_run_previews_both_verbs_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))

            code, messages = manage.activate("primer", settings, hooks_dir, state, True)
            self.assertEqual(code, 0)
            self.assertTrue(messages[0].startswith("would activate:"), messages)
            self.assertEqual(json.loads(settings.read_text()), {})
            self.assertFalse(manage.receipt_path(state, "primer").exists())

            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)
            code, messages = manage.deactivate("primer", settings, state, True)
            self.assertEqual(code, 0)
            self.assertTrue(messages[0].startswith("would deactivate:"), messages)
            self.assertIn("SessionStart", json.loads(settings.read_text())["hooks"])

    def test_a_crash_between_receipt_arm_and_settings_write_recovers_on_rerun(self) -> None:
        """Pending-slot crash consistency, driven through the real code path: the first
        `atomic_bytes` call in a transaction writes the pending receipt (via atomic_json) and the
        second writes settings, so failing exactly the second models a crash inside the window."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))

            real = manage.settings_io.atomic_bytes
            calls: list[Path] = []

            def crash_on_settings_write(path, content, mode, expected=None):
                calls.append(path)
                if path == settings:
                    raise OSError("simulated crash")
                return real(path, content, mode, expected)

            with mock.patch.object(manage.settings_io, "atomic_bytes", side_effect=crash_on_settings_write):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    manage.activate("primer", settings, hooks_dir, state, False)

            receipt = json.loads(manage.receipt_path(state, "primer").read_text())
            self.assertEqual(receipt["phase"], "pending")
            self.assertEqual(json.loads(settings.read_text()), {}, "the crash left settings at the prestate")

            # A dry run must demand recovery rather than planning over an armed transaction.
            with self.assertRaisesRegex(manage.HooksError, "requires recovery"):
                manage.activate("primer", settings, hooks_dir, state, True)

            status_code, status_messages = manage.status(settings, hooks_dir, state, None)
            self.assertEqual(status_code, 0)
            self.assertTrue(any("recovery pending" in message for message in status_messages), status_messages)

            # The rerun resolves the armed slot (settings match `before`, so the activate aborts
            # cleanly) and then performs the activation it was asked for.
            code, messages = manage.activate("primer", settings, hooks_dir, state, False)
            self.assertEqual(code, 0, messages)
            self.assertEqual(
                json.loads(settings.read_text())["hooks"]["SessionStart"],
                [self.managed_element(hooks_dir)],
            )
            self.assertEqual(json.loads(manage.receipt_path(state, "primer").read_text())["phase"], "committed")

    def test_a_settings_change_mid_activate_is_preserved_and_the_receipt_disarmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))

            real = manage.settings_io.atomic_bytes

            def racing_edit(path, content, mode, expected=None):
                if path == settings:
                    settings.write_text(json.dumps({"model": "raced"}))
                return real(path, content, mode, expected)

            with mock.patch.object(manage.settings_io, "atomic_bytes", side_effect=racing_edit):
                with self.assertRaisesRegex(manage.settings_io.SettingsChangedError, "preserving operator edit"):
                    manage.activate("primer", settings, hooks_dir, state, False)

            self.assertEqual(json.loads(settings.read_text()), {"model": "raced"})
            self.assertFalse(manage.receipt_path(state, "primer").exists(), "the armed receipt must be disarmed")

    def test_status_reports_each_state_and_always_ends_with_one_terminal_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({"hooks": {"SessionStart": [USER_ELEMENT]}}))

            code, messages = manage.status(settings, hooks_dir, state, None)
            self.assertEqual(code, 0)
            self.assertIn("hook primer: installed, inactive", messages)
            self.assertIn("foreign hooks.SessionStart elements: 1 (preserved)", messages)
            self.assertEqual(messages[-1], "0 active, 1 inactive, 0 conflict")

            self.assertEqual(manage.activate("primer", settings, hooks_dir, state, False)[0], 0)
            code, messages = manage.status(settings, hooks_dir, state, None)
            self.assertIn("hook primer: installed, active", messages)
            self.assertEqual(messages[-1], "1 active, 0 inactive, 0 conflict")

            # An operator removing the element by hand turns the receipt into a named conflict.
            settings.write_text(json.dumps({"hooks": {"SessionStart": [USER_ELEMENT]}}))
            code, messages = manage.status(settings, hooks_dir, state, None)
            self.assertTrue(
                any("receipt without its settings element" in message for message in messages), messages
            )
            self.assertEqual(messages[-1], "0 active, 0 inactive, 1 conflict")

            # A drifted installed copy is reported without blocking the read.
            (hooks_dir / "primer.sh").write_text(HOOK_TEXT + "# drift\n", encoding="utf-8")
            code, messages = manage.status(settings, hooks_dir, state, None)
            self.assertTrue(any("drifted from its ownership record" in message for message in messages), messages)

    def test_status_on_an_empty_plane_still_ends_with_one_terminal_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root, install=False)
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({}))

            code, messages = manage.status(settings, hooks_dir, state, None)

            self.assertEqual(code, 0)
            self.assertEqual(len(messages), 1)
            self.assertTrue(messages[0].startswith("no owned hooks for this plane"), messages)

    def test_main_wires_the_cli_and_refuses_a_malformed_hook_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))
            base = ["--home", str(root / "home"), "--state-root", str(state)]

            self.assertEqual(manage.main(["activate", "--hook", "primer", *base]), 0)
            self.assertEqual(
                json.loads(settings.read_text())["hooks"]["SessionStart"],
                [self.managed_element(hooks_dir)],
            )
            self.assertEqual(manage.main(["status", *base]), 0)
            self.assertEqual(manage.main(["deactivate", "--hook", "primer", *base]), 0)
            self.assertEqual(json.loads(settings.read_text()), {})

            # A missing or non-slug --hook is a refusal at EXIT_REFUSED, before any read or write.
            self.assertEqual(manage.main(["activate", *base]), 2)
            self.assertEqual(manage.main(["activate", "--hook", "../primer", *base]), 2)
            self.assertEqual(manage.main(["deactivate", *base]), 2)

    def test_the_claude_config_dir_override_moves_both_settings_and_the_hook_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings, hooks_dir, state = self.setup_environment(root)
            settings.write_text(json.dumps({}))
            argv = [
                "activate", "--hook", "primer",
                "--home", str(root / "elsewhere"),
                "--claude-config-dir", str(root / "home" / ".claude"),
                "--state-root", str(state),
            ]

            self.assertEqual(manage.main(argv), 0)

            self.assertIn("SessionStart", json.loads(settings.read_text())["hooks"])


if __name__ == "__main__":
    unittest.main()
