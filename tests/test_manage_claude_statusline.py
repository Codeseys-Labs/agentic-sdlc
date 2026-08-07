from __future__ import annotations

import importlib.util
import json
from pathlib import Path
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
            self.assertEqual(manage.status(settings, state)[0], 0)

            self.assertEqual(manage.deactivate(settings, state, False)[0], 0)
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
                manage.deactivate(settings, state, False)
            self.assertEqual(json.loads(settings.read_text())["statusLine"]["command"], "/operator-edit")

    def test_dry_run_does_not_write_settings_or_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            result = manage.activate(config, settings, state, True)

            self.assertEqual(result[0], 0)
            self.assertFalse(settings.exists())
            self.assertFalse(manage.receipt_path(state).exists())

    def test_linked_settings_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True)
            target = root / "foreign.json"; target.write_text("{}")
            settings.symlink_to(target)

            with self.assertRaisesRegex(manage.StatuslineError, "must not be a link"):
                manage.activate(config, settings, state, False)


if __name__ == "__main__":
    unittest.main()
