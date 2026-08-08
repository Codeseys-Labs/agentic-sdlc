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

    # --- help is not a side-effecting operation ------------------------------------------
    #
    # Asserted against the RENDERED dispatcher, driven end to end with stub `mise`/`claude` on
    # PATH, and asserted on OUTPUT rather than exit status. An exit code cannot distinguish
    # "printed usage" from "launched Claude Code, which then exited 0" -- that ambiguity is
    # exactly how `ccodex launch --help` was previously believed to be correct while it was in
    # fact mounting session inheritance and constructing settings.json in the isolated dir.
    SIDE_EFFECT_MARKER = "preparing gateway-routed Claude Code"

    def stub_environment(self, root: Path, bin_dir: Path) -> dict[str, str]:
        """A PATH whose `mise`/`claude` record their argv instead of running anything real."""
        stubs = root / "stubs"
        stubs.mkdir(parents=True, exist_ok=True)
        mise = stubs / "mise"
        mise.write_text(
            "#!/bin/sh\n"
            'while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done\n'
            '[ "${1:-}" = -- ] && shift\n'
            'case "${1:-} ${2:-} ${3:-}" in\n'
            "  'ocx --version ') exit 0 ;;\n"
            "  'ocx health ') exit 0 ;;\n"
            "  'ocx health --json') printf '{\"ok\":true,\"pid\":1,\"port\":10100}\\n'; exit 0 ;;\n"
            "  'ocx config get') exit 0 ;;\n"
            "esac\n"
            'if [ "${1:-} ${2:-}" = "ocx claude" ]; then shift 2; exec claude "$@"; fi\n'
            'printf "STUB-OCX:"; for a in "$@"; do printf "<%s>" "$a"; done; printf "\\n"\n'
            "exit 0\n"
        )
        mise.chmod(0o755)
        claude = stubs / "claude"
        claude.write_text(
            "#!/bin/sh\n"
            'printf "STUB-CLAUDE:"; for a in "$@"; do printf "<%s>" "$a"; done; printf "\\n"\n'
            "exit 0\n"
        )
        claude.chmod(0o755)
        home = root / "operator-home"
        (home / ".claude").mkdir(parents=True, exist_ok=True)
        (home / ".claude" / "history.jsonl").write_text('{"display":"global"}\n')
        return {
            "HOME": str(home),
            "XDG_STATE_HOME": str(root / "operator-state"),
            "PATH": f"{stubs}:{bin_dir}:/usr/bin:/bin",
        }

    def test_every_help_form_prints_usage_and_prepares_nothing(self) -> None:
        # Top-level help was already correct; the verb level was not, and `ocx --help` errored
        # with "unknown ccodex ocx verb: --help". All eight forms are asserted together because
        # the defect was a per-route inconsistency, not a single wrong branch.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            environment = self.stub_environment(root, config.bin_dir)
            isolated = Path(environment["XDG_STATE_HOME"]) / "agentic-sdlc" / "ocx-claude"

            for arguments in (
                ["help"],
                ["-h"],
                ["--help"],
                ["launch", "--help"],
                ["launch", "-h"],
                ["ultracode", "--help"],
                ["ocx", "--help"],
                ["ocx", "launch", "--help"],
            ):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [str(dispatcher), *arguments],
                        capture_output=True, text=True, env=environment, check=False,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage:", result.stdout)
                    self.assertNotIn(self.SIDE_EFFECT_MARKER, result.stdout)
                    self.assertNotIn("unknown", result.stderr)
                    # A help request neither creates the isolated plane nor writes into it.
                    self.assertFalse(
                        isolated.exists(), f"{arguments} created {isolated}"
                    )

    def test_sub_dispatcher_help_is_not_a_usage_error(self) -> None:
        # `ccodex bundle --help` printed `error: ccodex bundle needs install|status|uninstall` on
        # STDERR and exited 2 -- the same defect fixed for the launch verbs on 2026-08-07,
        # surviving in the three routes that fix did not touch. Found while writing the README
        # command reference, by running every documented verb rather than reading the source.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            environment = self.stub_environment(root, config.bin_dir)

            for route in ("bundle", "libraries", "statusline"):
                for form in ("--help", "-h", "help"):
                    with self.subTest(route=route, form=form):
                        result = subprocess.run(
                            [str(dispatcher), route, form],
                            capture_output=True, text=True, env=environment, check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn(f"usage: ccodex {route}", result.stdout)
                        self.assertNotIn("error:", result.stderr)

                # A BARE verb is still a usage error, because it is a genuine invocation
                # mistake rather than a question. The fix must not blur the two.
                bare = subprocess.run(
                    [str(dispatcher), route],
                    capture_output=True, text=True, env=environment, check=False,
                )
                self.assertEqual(bare.returncode, 2, f"{route} bare should stay a usage error")
                self.assertIn("error:", bare.stderr)

    def test_verb_help_is_the_verbs_own_text_not_the_top_level_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            environment = self.stub_environment(root, config.bin_dir)

            result = subprocess.run(
                [str(config.bin_dir / "ccodex"), "launch", "--help"],
                capture_output=True, text=True, env=environment, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage: ccodex launch", result.stdout)
            # And it says how to reach the wrapped tool's own help, so the interception does not
            # silently remove a capability.
            self.assertIn("-- --help", result.stdout)

    def test_the_forwarding_separator_reaches_claude_code_through_the_dispatcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            environment = self.stub_environment(root, config.bin_dir)

            for arguments, expected in (
                (["launch", "--", "--help"], "STUB-CLAUDE:<--help>"),
                (["ocx", "launch", "--", "--help"], "STUB-CLAUDE:<--help>"),
                (
                    ["ultracode", "--", "--help"],
                    'STUB-CLAUDE:<--settings><{"ultracode":true}><--help>',
                ),
            ):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [str(config.bin_dir / "ccodex"), *arguments],
                        capture_output=True, text=True, env=environment, check=False,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    # A real session WAS prepared -- that is the point of the escape hatch.
                    self.assertIn(self.SIDE_EFFECT_MARKER, result.stdout)
                    self.assertIn(expected, result.stdout)

    def test_dispatcher_routes_the_session_verb(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            environment = self.stub_environment(root, config.bin_dir)

            result = subprocess.run(
                [str(config.bin_dir / "ccodex"), "session", "status"],
                capture_output=True, text=True, env=environment, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("session inheritance:", result.stdout)

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
