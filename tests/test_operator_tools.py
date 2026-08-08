from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import subprocess
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

    def test_install_commit_failure_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            original_write_state = operator_tools.write_state
            writes = 0

            def fail_final_write(selected: object, state: dict[str, object]) -> None:
                nonlocal writes
                writes += 1
                if writes == 2:
                    raise OSError("simulated crash")
                original_write_state(selected, state)

            with mock.patch.object(operator_tools, "write_state", fail_final_write):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    operator_tools.install(config)

            disk_state = operator_tools.load_state(config.state_path, config)
            self.assertIsNotNone(disk_state["pending"])
            result = operator_tools.install(config)
            self.assertEqual(result[0], 0)
            recovered = operator_tools.load_state(config.state_path, config)
            self.assertIsNone(recovered["pending"])
            self.assertEqual(operator_tools.status(config)[0], 0)

    def test_uninstall_commit_failure_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            original_write_state = operator_tools.write_state
            writes = 0

            def fail_final_write(selected: object, state: dict[str, object]) -> None:
                nonlocal writes
                writes += 1
                if writes == 2:
                    raise OSError("simulated crash")
                original_write_state(selected, state)

            with mock.patch.object(operator_tools, "write_state", fail_final_write):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    operator_tools.uninstall(config)

            disk_state = operator_tools.load_state(config.state_path, config)
            self.assertIsNotNone(disk_state["pending"])
            result = operator_tools.uninstall(config)
            self.assertEqual(result[0], 0)
            self.assertFalse(any((config.bin_dir / name).exists() for name in operator_tools.COMMANDS))

    def test_pending_conflict_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            content = operator_tools.desired_files(config)["ocx-launch"]
            path = config.bin_dir / "ocx-launch"
            record = {"path": str(path), "digest": operator_tools.digest_bytes(content), "removable": "true"}
            state = operator_tools.empty_state()
            operator_tools.arm(config, state, "install", path, None, record)
            config.bin_dir.mkdir(parents=True, exist_ok=True)
            path.write_text("foreign\n")

            with self.assertRaisesRegex(operator_tools.OperatorToolsError, "conflicts"):
                operator_tools.install(config)
            self.assertEqual(path.read_text(), "foreign\n")
            self.assertIsNotNone(operator_tools.load_state(config.state_path, config)["pending"])

    def test_ccodex_dispatcher_is_installed_and_resolves_its_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            body = dispatcher.read_text()

            self.assertTrue(dispatcher.is_file())
            self.assertTrue(dispatcher.stat().st_mode & stat.S_IXUSR)
            # Substituted, not left as a placeholder.
            self.assertNotIn("@CANONICAL_ROOT@", body)
            self.assertNotIn("@CANONICAL_LAUNCHER@", body)
            self.assertIn(str(Path(__file__).parents[1]), body)
            # Root is overridable at run time, so a clone that later moves to a managed path can
            # be pointed at without reinstalling this file.
            self.assertIn("AGENTIC_SDLC_ROOT", body)
            self.assertEqual(
                subprocess.run(["bash", "-n", str(dispatcher)], capture_output=True).returncode, 0
            )

    def test_ccodex_omits_repository_maintenance_verbs(self) -> None:
        # The use surface is not the maintenance surface. Shipping `check`/`test`/`validate` on an
        # operator's PATH would present repo upkeep as a product feature.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            body = (config.bin_dir / "ccodex").read_text()
            # Assert on the dispatch arms, not on the whole file: the header PROSE names the
            # maintenance tasks in order to explain why they are excluded, so a substring search
            # over the file would match that explanation and prove nothing.
            arms = {
                line.strip().rstrip(")")
                for line in body.splitlines()
                if line.startswith("  ") and line.strip().endswith(")") and "|" not in line
            }
            routed = {
                token
                for line in body.splitlines()
                if line.strip().endswith(")") and not line.strip().startswith("#")
                for token in line.strip().rstrip(")").split("|")
            }

            for verb in ("mermaid", "provision", "check", "secrets", "validate", "hooks"):
                self.assertNotIn(verb, routed, f"{verb} must not be an operator route")
            for route in ("launch", "status", "providers", "models", "libraries", "bundle"):
                self.assertIn(route, routed, f"{route} should be an operator route")
            self.assertTrue(arms)

    def test_ccodex_reports_a_missing_repository_root_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)

            result = subprocess.run(
                [str(config.bin_dir / "ccodex"), "status"],
                capture_output=True, text=True,
                env={**os.environ, "AGENTIC_SDLC_ROOT": str(root / "definitely-absent")},
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("repository root is missing", result.stderr)
            self.assertIn("AGENTIC_SDLC_ROOT", result.stderr)

    def test_ccodex_rejects_an_unknown_verb_without_running_anything(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)

            for arguments in (["not-a-command"], ["ocx", "not-a-verb"], ["bundle", "reinstall"]):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [str(config.bin_dir / "ccodex"), *arguments],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 2)

    def test_status_says_absent_for_a_file_that_was_never_installed(self) -> None:
        # `unmanaged` for a nonexistent file sent an operator hunting for a conflict to
        # resolve. A missing file is `absent`, and the report names the install command.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)

            code, messages = operator_tools.status(config)

            self.assertEqual(code, 1)
            self.assertEqual(len(messages), len(operator_tools.COMMANDS))
            for message in messages:
                self.assertTrue(message.startswith("absent: "), message)
                self.assertIn("operator-tools:install", message)
            self.assertFalse(any("unmanaged" in message for message in messages))

    def test_status_still_says_unmanaged_for_a_foreign_file(self) -> None:
        # The distinction has to cut both ways: a file that IS there but is not owned is a
        # real conflict for the operator to resolve, and must not be softened to `absent`.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            config.bin_dir.mkdir(parents=True)
            (config.bin_dir / "ocx-launch").write_text("foreign\n")

            code, messages = operator_tools.status(config)

            self.assertEqual(code, 1)
            self.assertIn(f"unmanaged: {config.bin_dir / 'ocx-launch'}", messages)
            self.assertTrue(
                any(message.startswith("absent: ") for message in messages),
                messages,
            )

    def test_status_reports_pending_without_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            content = operator_tools.desired_files(config)["ocx-launch"]
            path = config.bin_dir / "ocx-launch"
            record = {"path": str(path), "digest": operator_tools.digest_bytes(content), "removable": "true"}
            state = operator_tools.empty_state()
            operator_tools.arm(config, state, "install", path, None, record)
            before = config.state_path.read_bytes()

            result = operator_tools.status(config)
            self.assertEqual(result[0], 1)
            self.assertIn("would recover abort", result[1][0])
            self.assertEqual(config.state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
