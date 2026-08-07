from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "manage_claude_statusline.py"
spec = importlib.util.spec_from_file_location("manage_statusline", SCRIPT)
assert spec and spec.loader
manage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = manage
spec.loader.exec_module(manage)
import install_operator_tools as operator_tools


class ManageClaudeStatuslineTests(unittest.TestCase):
    def setup_environment(self, root: Path) -> tuple[object, Path, Path]:
        home = root / "home"; bin_dir = home / ".local" / "bin"; state = root / "state"
        config = operator_tools.Config(ROOT, home, bin_dir, state, require_path=False)
        self.assertEqual(operator_tools.install(config)[0], 0)
        settings = home / ".claude" / "settings.json"
        return config, settings, state

    def test_activate_and_deactivate_preserve_unmanaged_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True)
            original = {"model": "fable", "enabledPlugins": {"example": True}, "statusLine": {"padding": 1}}
            settings.write_text(json.dumps(original))

            activated = manage.activate(config, settings, state, False)
            active = json.loads(settings.read_text())
            self.assertEqual(activated[0], 0)
            self.assertEqual(active["model"], "fable")
            self.assertEqual(active["enabledPlugins"], {"example": True})
            self.assertEqual(active["statusLine"]["padding"], 1)
            self.assertEqual(active["statusLine"]["type"], "command")
            self.assertEqual(manage.status(config, settings, state)[0], 0)

            self.assertEqual(manage.deactivate(config, settings, state, False)[0], 0)
            self.assertEqual(json.loads(settings.read_text()), original)

    def test_foreign_statusline_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({"statusLine": {"command": "/foreign"}}))

            with self.assertRaisesRegex(manage.StatuslineError, "foreign"):
                manage.activate(config, settings, state, False)
            self.assertEqual(json.loads(settings.read_text())["statusLine"]["command"], "/foreign")

    def test_operator_edit_after_activation_blocks_deactivation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            manage.activate(config, settings, state, False)
            value = json.loads(settings.read_text())
            value["statusLine"]["command"] = "/operator-edit"
            settings.write_text(json.dumps(value))

            with self.assertRaisesRegex(manage.StatuslineError, "preserving operator edit"):
                manage.deactivate(config, settings, state, False)
            self.assertEqual(json.loads(settings.read_text())["statusLine"]["command"], "/operator-edit")

    def test_dry_run_does_not_write_settings_or_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            result = manage.activate(config, settings, state, True)

            self.assertEqual(result[0], 0)
            self.assertFalse(settings.exists())
            self.assertFalse(manage.receipt_path(state).exists())

    def test_managed_command_shell_quotes_metacharacter_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="status line $; '") as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            manage.activate(config, settings, state, False)

            command = json.loads(settings.read_text())["statusLine"]["command"]
            expected = config.bin_dir / "agentic-sdlc-statusline"
            self.assertEqual(command, shlex.quote(str(expected)))
            self.assertEqual(shlex.split(command), [str(expected)])

    def test_linked_settings_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True)
            target = root / "foreign.json"; target.write_text("{}")
            settings.symlink_to(target)

            with self.assertRaisesRegex(manage.StatuslineError, "must not be a link"):
                manage.activate(config, settings, state, False)

    def test_activation_recovers_after_settings_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            original_atomic_json = manage.atomic_json

            def crash_before_commit(path: Path, value: dict[str, object], mode: int, expected=None) -> None:
                if path == manage.receipt_path(state) and value.get("phase") == "committed":
                    raise OSError("simulated crash")
                original_atomic_json(path, value, mode, expected)

            manage.atomic_json = crash_before_commit
            try:
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    manage.activate(config, settings, state, False)
            finally:
                manage.atomic_json = original_atomic_json

            self.assertEqual(manage.status(config, settings, state)[0], 1)
            self.assertIn("recovery pending", manage.status(config, settings, state)[1][0])
            with self.assertRaisesRegex(manage.StatuslineError, "already exists"):
                manage.activate(config, settings, state, False)
            receipt = json.loads(manage.receipt_path(state).read_text())
            self.assertEqual(receipt["phase"], "committed")
            self.assertEqual(manage.status(config, settings, state)[0], 0)

    def test_deactivation_recovers_after_settings_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            manage.activate(config, settings, state, False)
            original_remove = manage.remove_durable

            def crash_before_receipt_removal(path: Path) -> None:
                if path == manage.receipt_path(state):
                    raise OSError("simulated crash")
                original_remove(path)

            manage.remove_durable = crash_before_receipt_removal
            try:
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    manage.deactivate(config, settings, state, False)
            finally:
                manage.remove_durable = original_remove

            self.assertEqual(manage.status(config, settings, state)[0], 1)
            self.assertEqual(manage.deactivate(config, settings, state, False)[0], 1)
            self.assertFalse(manage.receipt_path(state).exists())
            self.assertEqual(manage.status(config, settings, state)[1], [f"statusline inactive: {settings}"])

    def test_concurrent_settings_edit_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({"model": "fable"}))
            original_atomic_bytes = manage.atomic_bytes

            def edit_before_replace(path: Path, content: bytes, mode: int, expected=None) -> None:
                if path == settings and expected is not None:
                    path.write_text(json.dumps({"model": "operator-edit"}))
                original_atomic_bytes(path, content, mode, expected)

            manage.atomic_bytes = edit_before_replace
            try:
                with self.assertRaisesRegex(manage.SettingsChangedError, "preserving operator edit"):
                    manage.activate(config, settings, state, False)
            finally:
                manage.atomic_bytes = original_atomic_bytes

            self.assertEqual(json.loads(settings.read_text()), {"model": "operator-edit"})
            self.assertFalse(manage.receipt_path(state).exists())

    def test_status_reports_pending_without_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            command = operator_tools.exact_owned_statusline(config)
            before = {"exists": False}
            wanted = manage.managed_values(command)
            value = {"statusLine": wanted}
            content = manage.json_bytes(value)
            pending = {
                "version": manage.RECEIPT_VERSION,
                "phase": "pending",
                "operation": "activate",
                "settings": str(settings),
                "managed": wanted,
                "previous": {key: {"present": False} for key in manage.MANAGED_KEYS},
                "before": before,
                "after": manage.after_snapshot(content, 0o600),
            }
            manage.atomic_json(manage.receipt_path(state), pending, 0o600)

            code, messages = manage.status(config, settings, state)
            self.assertEqual(code, 1)
            self.assertIn("recovery pending", messages[0])
            self.assertEqual(json.loads(manage.receipt_path(state).read_text())["phase"], "pending")


if __name__ == "__main__":
    unittest.main()
