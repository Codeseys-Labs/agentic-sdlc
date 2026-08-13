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
            self.assertTrue(installed[1][-1].startswith("install summary:"))
            self.assertTrue(checked[1][-1].startswith("status summary:"))
            for name in operator_tools.DESIRED_COMMANDS:
                path = config.bin_dir / name
                self.assertTrue(path.is_file())
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
            for name in operator_tools.HISTORICAL_ALIASES:
                self.assertFalse((config.bin_dir / name).exists())
            removed = operator_tools.uninstall(config)
            self.assertEqual(removed[0], 0)
            self.assertTrue(removed[1][-1].startswith("uninstall summary:"))
            self.assertFalse(any((config.bin_dir / name).exists() for name in operator_tools.RECOGNIZED_COMMANDS))

    def historical_alias_content(self, config: object, name: str = "ocx-launch") -> bytes:
        del config
        verb = "launch-ultracode" if name == "ocx-ultracode" else "launch"
        return f"#!/bin/sh\nexec opencodex-claude.sh {verb} \"$@\"\n".encode()

    def seed_owned_historical_alias(
        self, config: object, name: str = "ocx-launch", *, removable: str = "true"
    ) -> Path:
        content = self.historical_alias_content(config, name)
        path = config.bin_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o755)
        state = operator_tools.empty_state()
        key = str(path)
        state["entries"][key] = {
            "path": key,
            "digest": operator_tools.digest_bytes(content),
            "removable": removable,
        }
        operator_tools.write_state(config, state)
        return path

    def test_modified_owned_historical_alias_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            path = self.seed_owned_historical_alias(config)
            path.write_text("modified\n")

            installed = operator_tools.install(config)
            retired = operator_tools.retire_aliases(config)

            self.assertEqual(installed[0], 0)
            self.assertEqual(retired[0], 1)
            self.assertEqual(path.read_text(), "modified\n")
            self.assertTrue(any("changed since install" in message for message in retired[1]))

    def test_foreign_historical_alias_is_ignored_by_install_and_preserved_on_retirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            config.bin_dir.mkdir(parents=True)
            path = config.bin_dir / "ocx-launch"
            path.write_text("foreign\n")

            installed = operator_tools.install(config)
            retired = operator_tools.retire_aliases(config)

            self.assertEqual(installed[0], 0)
            self.assertEqual(retired[0], 0)
            self.assertEqual(path.read_text(), "foreign\n")
            self.assertTrue(any("unmanaged" in message for message in retired[1]))

    def test_unchanged_owned_historical_alias_requires_explicit_retirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            path = self.seed_owned_historical_alias(config)

            self.assertEqual(operator_tools.install(config)[0], 0)
            self.assertTrue(path.exists())
            checked = operator_tools.status(config)
            retired = operator_tools.retire_aliases(config)

            self.assertEqual(checked[0], 0)
            self.assertTrue(any("retirable historical alias" in message for message in checked[1]))
            self.assertEqual(retired[0], 0)
            self.assertFalse(path.exists())
            self.assertNotIn(str(path), operator_tools.load_state(config.state_path, config)["entries"])

    def test_adopted_historical_alias_is_never_retired(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            path = self.seed_owned_historical_alias(config, removable="false")

            retired = operator_tools.retire_aliases(config)

            self.assertEqual(retired[0], 0)
            self.assertTrue(path.exists())
            self.assertTrue(any("adopted pre-existing" in message for message in retired[1]))

    def test_status_is_read_only_on_a_never_installed_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)

            code, messages = operator_tools.status(config)

            self.assertEqual(code, 1)
            self.assertFalse(config.state_path.exists())
            self.assertFalse(config.lock_path.exists())
            self.assertTrue(messages[-1].startswith("status summary:"))

    def test_path_preflight_refuses_unlisted_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = operator_tools.Config(
                Path(__file__).parents[1], root / "home", root / "bin", root / "state"
            )
            with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=False):
                with self.assertRaisesRegex(operator_tools.OperatorToolsError, "not on PATH") as raised:
                    operator_tools.install(config)

            self.assertIn("never edits PATH", str(raised.exception))
            self.assertIn("start a new shell", str(raised.exception))
            self.assertFalse(config.bin_dir.exists())

    def test_cli_help_explains_read_only_inspection_and_path_boundary(self) -> None:
        # argparse re-wraps usage and epilog to the caller's terminal width, so COLUMNS is pinned
        # wide: an unpinned width makes these substrings depend on whoever runs the suite.
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], text=True, capture_output=True, check=False,
            env={**os.environ, "COLUMNS": "200"},
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--bin-dir PATH", completed.stdout)
        self.assertIn("Status and --dry-run", completed.stdout)
        self.assertIn("never creates shell aliases or edits PATH", completed.stdout)

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
            self.assertFalse(any((config.bin_dir / name).exists() for name in operator_tools.RECOGNIZED_COMMANDS))

    def test_pending_conflict_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            content = self.historical_alias_content(config)
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
            for route in ("ensure", "launch", "status", "providers", "models", "libraries", "bundle"):
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
            'if [ "${1:-} ${2:-} ${3:-} ${4:-}" = "ocx claude config set" ]; then\n'
            '  printf "STUB-OCX:"; for a in "$@"; do printf "<%s>" "$a"; done; printf "\\n"; exit 0\n'
            "fi\n"
            'if [ "${1:-} ${2:-} ${3:-}" = "ocx models live" ]; then\n'
            '  [ "${STUB_OCX_MODELS_FAIL:-}" = 1 ] && { printf "catalog unavailable\\n" >&2; exit 1; }\n'
            '  printf \'[{"namespaced":"gpt-5.6-luna","native":true,"provider":"openai","disabled":false},{"namespaced":"muse/muse-spark-1.2","provider":"muse","disabled":false}]\\n\'; exit 0\n'
            "fi\n"
            'if [ "${1:-}" = jq ]; then\n'
            '  cat >/dev/null; printf "gpt-5.6-luna\\tnative OCX\\nmuse/muse-spark-1.2\\trouted via muse\\n"; exit 0\n'
            "fi\n"
            'case "${1:-} ${2:-} ${3:-}" in\n'
            "  'ocx --version ') exit 0 ;;\n"
            "  'ocx health ') exit 0 ;;\n"
            "  'ocx health --json') printf '{\"ok\":true,\"pid\":1,\"port\":10100}\\n'; exit 0 ;;\n"
            "  'ocx claude config') printf '{\"enabled\":true,\"authMode\":\"subscription\",\"admissionKeyActive\":false,\"authDetectionUnknown\":false,\"authFoundBy\":\"claude-credentials-file\",\"modelMap\":{}}\\n'; exit 0 ;;\n"
            "  'ocx config get') printf 'config path not found: %s\\n' \"${4:-}\" >&2; exit 2 ;;\n"
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
                ["ensure", "--help"],
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
                    # A real route WAS invoked, so it reports its preparation.
                    self.assertIn(self.SIDE_EFFECT_MARKER, result.stdout)
                    self.assertIn(expected, result.stdout)

    def test_dispatcher_yolo_is_available_on_launch_and_ultracode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            environment = self.stub_environment(root, config.bin_dir)

            for arguments, expected in (
                (
                    ["launch", "--yolo", "--model", "gpt-5.6-sol"],
                    "STUB-CLAUDE:<--dangerously-skip-permissions><--model><gpt-5.6-sol>",
                ),
                (
                    ["ultracode", "--yolo", "--model", "gpt-5.6-sol"],
                    "STUB-CLAUDE:<--dangerously-skip-permissions><--settings>"
                    '<{\"ultracode\":true}><--model><gpt-5.6-sol>',
                ),
            ):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [str(config.bin_dir / "ccodex"), *arguments],
                        capture_output=True, text=True, env=environment, check=False,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(expected, result.stdout)
                    self.assertNotIn("<--yolo>", result.stdout)
                    self.assertIn("permissions: BYPASSED", result.stdout)

    def test_dispatcher_routes_ensure_in_short_and_long_forms(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            environment = self.stub_environment(root, config.bin_dir)

            for arguments in (["ensure"], ["ocx", "ensure"]):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [str(dispatcher), *arguments],
                        capture_output=True,
                        text=True,
                        env=environment,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("does not launch Claude Code", result.stdout)
                    self.assertNotIn("STUB-CLAUDE", result.stdout)

    def test_set_fast_model_forwards_one_exact_value_without_launching(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            environment = self.stub_environment(root, config.bin_dir)

            for value in ("gpt-5.6-luna", "claude-sonnet-5", "muse/muse-spark-1.2", "-"):
                with self.subTest(value=value):
                    result = subprocess.run(
                        [str(dispatcher), "set-fast-model", value],
                        capture_output=True,
                        text=True,
                        env=environment,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(
                        f"STUB-OCX:<ocx><claude><config><set><--small-fast-model><{value}>",
                        result.stdout,
                    )
                    self.assertNotIn(self.SIDE_EFFECT_MARKER, result.stdout)
                    self.assertNotIn("STUB-CLAUDE", result.stdout)

    def test_set_fast_model_bare_invocation_selects_from_claude_families_and_live_ocx(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            environment = self.stub_environment(root, config.bin_dir)

            for choice, expected in (
                ("1", "sonnet"),
                ("4", "gpt-5.6-luna"),
                ("5", "muse/muse-spark-1.2"),
            ):
                with self.subTest(choice=choice, expected=expected):
                    result = subprocess.run(
                        [str(dispatcher), "set-fast-model"],
                        input=f"{choice}\n",
                        capture_output=True,
                        text=True,
                        env=environment,
                        check=False,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("Claude Code families", result.stdout)
                    self.assertIn("Live OCX catalog", result.stdout)
                    self.assertIn("  5) muse/muse-spark-1.2", result.stdout)
                    self.assertIn(
                        "STUB-OCX:<ocx><claude><config><set><--small-fast-model>"
                        f"<{expected}>",
                        result.stdout,
                    )
                    self.assertNotIn(self.SIDE_EFFECT_MARKER, result.stdout)
                    self.assertNotIn("STUB-CLAUDE", result.stdout)

    def test_set_fast_model_selector_can_clear_and_cancel_without_a_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            environment = self.stub_environment(root, config.bin_dir)

            cleared = subprocess.run(
                [str(dispatcher), "set-fast-model"], input="6\n",
                capture_output=True, text=True, env=environment, check=False,
            )
            cancelled = subprocess.run(
                [str(dispatcher), "set-fast-model"], input="q\n",
                capture_output=True, text=True, env=environment, check=False,
            )

            self.assertEqual(cleared.returncode, 0, cleared.stderr)
            self.assertIn(
                "STUB-OCX:<ocx><claude><config><set><--small-fast-model><->",
                cleared.stdout,
            )
            self.assertEqual(cancelled.returncode, 3)
            self.assertIn("selection cancelled", cancelled.stderr)
            self.assertNotIn("config><set", cancelled.stdout)

    def test_set_fast_model_selector_fails_closed_when_live_catalog_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            environment = self.stub_environment(root, config.bin_dir)
            environment["STUB_OCX_MODELS_FAIL"] = "1"

            result = subprocess.run(
                [str(config.bin_dir / "ccodex"), "set-fast-model"], input="1\n",
                capture_output=True, text=True, env=environment, check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("cannot read the live OCX catalog", result.stderr)
            self.assertNotIn("config><set", result.stdout)

    def test_set_fast_model_refuses_extra_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            environment = self.stub_environment(root, config.bin_dir)

            result = subprocess.run(
                [str(dispatcher), "set-fast-model", "gpt-5.6-luna", "extra"],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("usage: ccodex set-fast-model", result.stderr)
            self.assertNotIn("STUB-OCX", result.stdout)

    def test_set_fast_model_help_is_side_effect_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            dispatcher = config.bin_dir / "ccodex"
            environment = self.stub_environment(root, config.bin_dir)

            result = subprocess.run(
                [str(dispatcher), "set-fast-model", "--help"],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage: ccodex set-fast-model", result.stdout)
            self.assertIn("not the Auto mode permission classifier", result.stdout)
            self.assertNotIn("STUB-OCX", result.stdout)
            self.assertNotIn("STUB-CLAUDE", result.stdout)

    def test_status_says_absent_for_a_file_that_was_never_installed(self) -> None:
        # `unmanaged` for a nonexistent file sent an operator hunting for a conflict to
        # resolve. A missing file is `absent`, and the report names the install command.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)

            code, messages = operator_tools.status(config)

            self.assertEqual(code, 1)
            self.assertEqual(len(messages), len(operator_tools.DESIRED_COMMANDS) + 1)
            for message in messages[:-1]:
                self.assertTrue(message.startswith("absent: "), message)
                self.assertIn("operator-tools:install", message)
            self.assertTrue(messages[-1].startswith("status summary:"))
            self.assertFalse(any("unmanaged" in message for message in messages))
            self.assertFalse(any("ocx-launch" in message for message in messages))
            self.assertFalse(any("ocx-ultracode" in message for message in messages))

    def test_status_still_says_unmanaged_for_a_foreign_file(self) -> None:
        # The distinction has to cut both ways: a file that IS there but is not owned is a
        # real conflict for the operator to resolve, and must not be softened to `absent`.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            config.bin_dir.mkdir(parents=True)
            (config.bin_dir / "ocx-launch").write_text("foreign\n")

            code, messages = operator_tools.status(config)

            self.assertEqual(code, 1)
            unmanaged = config.bin_dir / "ocx-launch"
            self.assertIn(f"kept historical alias (unmanaged): {unmanaged}", messages)
            self.assertFalse(any(message.startswith("absent: ") and "ocx-launch" in message for message in messages))
            self.assertTrue(
                any(message.startswith("absent: ") for message in messages),
                messages,
            )

    def test_v1_state_with_historical_alias_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            path = self.seed_owned_historical_alias(config)
            state = operator_tools.load_state(config.state_path, config)
            state.pop("pending")
            state["version"] = operator_tools.LEGACY_STATE_VERSION
            config.state_path.write_text(operator_tools.json.dumps(state))

            loaded = operator_tools.load_state(config.state_path, config)

            self.assertEqual(loaded["version"], operator_tools.STATE_VERSION)
            self.assertIn(str(path), loaded["entries"])

    def test_retire_aliases_dry_run_preserves_file_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); mutable = self.config(root)
            path = self.seed_owned_historical_alias(mutable)
            before = mutable.state_path.read_bytes()
            dry_run = self.config(root, dry_run=True)

            code, messages = operator_tools.retire_aliases(dry_run)

            self.assertEqual(code, 0)
            self.assertTrue(path.exists())
            self.assertEqual(mutable.state_path.read_bytes(), before)
            self.assertTrue(any("would retire historical alias" in message for message in messages))

    def test_status_detects_ownership_state_change_during_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            operator_tools.install(config)
            before_lock = config.lock_path.stat() if config.lock_path.exists() else None
            original = operator_tools._status

            def racing_status(selected: object) -> tuple[int, list[str]]:
                result = original(selected)
                state = operator_tools.load_state(selected.state_path, selected)
                state["pending"] = {
                    "operation": "uninstall",
                    "path": str(selected.bin_dir / "ccodex"),
                    "before": state["entries"][str(selected.bin_dir / "ccodex")],
                    "after": None,
                }
                operator_tools.write_state(selected, state)
                return result

            with mock.patch.object(operator_tools, "_status", racing_status):
                code, messages = operator_tools.status(config)

            self.assertEqual(code, 1)
            self.assertIn("ownership state changed during inspection", "\n".join(messages))
            after_lock = config.lock_path.stat() if config.lock_path.exists() else None
            self.assertEqual(before_lock, after_lock)

    def test_status_reports_pending_without_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root)
            content = self.historical_alias_content(config)
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
