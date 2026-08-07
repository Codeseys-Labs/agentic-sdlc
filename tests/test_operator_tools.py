from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "install_operator_tools.py"
spec = importlib.util.spec_from_file_location("operator_tools", SCRIPT)
assert spec and spec.loader
operator_tools = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = operator_tools
spec.loader.exec_module(operator_tools)


class OperatorToolsTests(unittest.TestCase):
    def config(self, root: Path, *, dry_run: bool = False) -> object:
        return operator_tools.Config(
            Path(__file__).parents[1],
            root / "home",
            root / "home" / ".local" / "bin",
            root / "state",
            dry_run,
            False,
        )

    def test_install_status_uninstall_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            installed = operator_tools.install(config)
            checked = operator_tools.status(config)

            self.assertEqual(installed[0], 0)
            self.assertEqual(checked[0], 0)
            for name in operator_tools.COMMANDS:
                path = config.bin_dir / name
                self.assertTrue(path.is_file())
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
            self.assertIn(
                str(Path(__file__).parents[1] / "scripts" / "opencodex-claude.sh"),
                (config.bin_dir / "ocx-launch").read_text(),
            )
            self.assertEqual(operator_tools.uninstall(config)[0], 0)
            self.assertFalse(any((config.bin_dir / name).exists() for name in operator_tools.COMMANDS))

    def test_modified_owned_command_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            path = config.bin_dir / "ocx-launch"
            path.write_text("foreign\n")

            installed = operator_tools.install(config)
            removed = operator_tools.uninstall(config)

            self.assertEqual(installed[0], 1)
            self.assertEqual(removed[0], 1)
            self.assertEqual(path.read_text(), "foreign\n")

    def test_foreign_command_is_not_adopted_when_different(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            config.bin_dir.mkdir(parents=True)
            path = config.bin_dir / "ocx-launch"
            path.write_text("foreign\n")

            result = operator_tools.install(config)

            self.assertEqual(result[0], 1)
            self.assertEqual(path.read_text(), "foreign\n")

    def test_path_preflight_refuses_unlisted_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = operator_tools.Config(
                Path(__file__).parents[1], root / "home", root / "bin", root / "state"
            )
            with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=False):
                with self.assertRaisesRegex(operator_tools.OperatorToolsError, "not on PATH"):
                    operator_tools.install(config)

    def test_self_test_is_isolated(self) -> None:
        code, messages = operator_tools.self_test(Path(__file__).parents[1])
        self.assertEqual(code, 0)
        self.assertEqual(messages, ["operator-tools self-test passed"])


if __name__ == "__main__":
    unittest.main()
