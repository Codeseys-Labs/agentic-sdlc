from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SCRIPT = ROOT / "scripts" / "manage_claude_statusline.py"
spec = importlib.util.spec_from_file_location("manage_statusline", SCRIPT)
assert spec and spec.loader
manage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = manage
spec.loader.exec_module(manage)
import install_skill_bundle as installer

SHIPPED_STATUSLINE = ROOT / "assets" / "claude" / "statusline-command.sh"


@unittest.skipIf(
    os.name == "nt",
    "native-Windows statusline activation is uncertified and fails closed (AGENTS.md), and the"
    " command this activates is a ledger row published at mode 0o755 -- a premise no Windows"
    " filesystem can establish, since chmod there can neither grant nor take the owner-execute"
    " bit (agentic-sdlc-5ce7)",
)
class ManageClaudeStatuslineTests(unittest.TestCase):
    def setup_environment(self, root: Path) -> tuple[object, Path, Path]:
        """Install ONE bundle ledger row -- the statusline -- into an isolated home.

        The payload tree carries only the statusline asset, so `discover_entries` finds exactly the
        entry these tests are about and the install stays scoped; the bytes are the shipped ones,
        copied at their tracked 0644 so the published 0o755 can only have come from the installer.
        """
        home = root / "home"; state = root / "state"; repo = root / "repo"
        (repo / "assets" / "claude").mkdir(parents=True)
        source = repo / "assets" / "claude" / "statusline-command.sh"
        shutil.copyfile(SHIPPED_STATUSLINE, source)
        os.chmod(source, 0o644)
        config = installer.Config(repo, home, root / "codex", "auto", False, "claude", state)
        self.assertEqual(installer.install(config).exit_code, 0)
        settings = home / ".claude" / "settings.json"
        return config, settings, state

    def test_activate_and_deactivate_preserve_unmanaged_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True, exist_ok=True)
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
            settings.parent.mkdir(parents=True, exist_ok=True)
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
            expected = config.home / ".claude" / "statusline" / "agentic-sdlc-statusline"
            self.assertEqual(command, shlex.quote(str(expected)))
            self.assertEqual(shlex.split(command), [str(expected)])
            self.assertEqual(installer.exact_owned_statusline(config), expected)

    def test_linked_settings_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True, exist_ok=True)
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

            # Decision 9: a completed status read that OBSERVES a pending-recovery state is
            # still an answered query, not an internal failure -- 0, with the state named in
            # the message (agentic-sdlc-d0a4, SP-6).
            self.assertEqual(manage.status(config, settings, state)[0], 0)
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

            # Same Decision 9 rule as above, applied to the other two of the five states this
            # module distinguishes: "recovery pending" (first status call, receipt still
            # pending) and "not managed" (deactivate(), once the receipt has been recovered
            # away, has nothing further to do -- that IS the requested end state).
            self.assertEqual(manage.status(config, settings, state)[0], 0)
            self.assertEqual(manage.deactivate(config, settings, state, False)[0], 0)
            self.assertFalse(manage.receipt_path(state).exists())
            self.assertEqual(manage.status(config, settings, state)[1], [f"statusline inactive: {settings}"])

    def test_concurrent_settings_edit_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True, exist_ok=True)
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
            command = installer.exact_owned_statusline(config)
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
            self.assertEqual(code, 0)
            self.assertIn("recovery pending", messages[0])
            self.assertEqual(json.loads(manage.receipt_path(state).read_text())["phase"], "pending")

    def test_status_inactive_is_zero_not_one(self) -> None:
        # decision9-conformance-survey SP-6 / agentic-sdlc-d0a4: a host that has simply never
        # activated the statusline is an ordinary answered query, not a failure.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)

            code, messages = manage.status(config, settings, state)
            self.assertEqual(code, 0)
            self.assertNotEqual(code, 1)
            self.assertEqual(messages, [f"statusline inactive: {settings}"])

    def test_status_unmanaged_is_zero_not_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text(json.dumps({"statusLine": {"command": "/foreign"}}))

            code, messages = manage.status(config, settings, state)
            self.assertEqual(code, 0)
            self.assertNotEqual(code, 1)
            self.assertEqual(messages, [f"unmanaged statusline: {settings}"])

    def test_status_conflict_is_zero_not_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            manage.activate(config, settings, state, False)
            value = json.loads(settings.read_text())
            value["statusLine"]["command"] = "/operator-edit"
            settings.write_text(json.dumps(value))

            code, messages = manage.status(config, settings, state)
            self.assertEqual(code, 0)
            self.assertNotEqual(code, 1)
            self.assertEqual(messages, [f"statusline conflict: {settings}"])

    def test_status_active_positive_control_stays_zero(self) -> None:
        # Positive control shared by the four tests above: the pre-existing "active" state was
        # already 0 and must stay 0 -- this fix distinguishes states in the message, not by
        # making every exit code identical regardless of what happened.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            manage.activate(config, settings, state, False)

            code, messages = manage.status(config, settings, state)
            self.assertEqual(code, 0)
            self.assertEqual(messages, [f"statusline active: {settings} -> {manage.managed_values(installer.exact_owned_statusline(config))['command']}"])

    def test_real_status_failure_still_exits_nonzero(self) -> None:
        # Negative control for the whole fix: a GENUINE read failure (unreadable settings) must
        # not be swept into the same 0 the five observed states now share.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text("not json")

            with self.assertRaisesRegex(manage.StatuslineError, "cannot read Claude settings"):
                manage.status(config, settings, state)

    def test_main_cli_reports_inactive_status_at_exit_zero(self) -> None:
        # End-to-end through main(), the entrypoint an operator actually runs.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            code = manage.main(
                [
                    "status",
                    "--home",
                    str(config.home),
                    "--state-root",
                    str(state),
                ]
            )
            self.assertEqual(code, 0)

    def test_main_cli_reports_a_genuine_read_failure_at_exit_refused(self) -> None:
        # End-to-end through main(): a StatuslineError-raising vector (corrupt settings.json,
        # the same vector test_real_status_failure_still_exits_nonzero raises at the function
        # level) must reach main()'s own `except (StatuslineError, ...)` handler and come out
        # as EXIT_REFUSED (2) -- not EXIT_OK. This pins the whole nonzero path end-to-end
        # through the real CLI, rather than only at the function `manage.status()` returns
        # from, so a `main()` that swallowed the exception and returned 0 for it would be
        # caught here even though `test_real_status_failure_still_exits_nonzero` only proves
        # the exception is raised, not what the CLI entrypoint does with it.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text("not json")

            code = manage.main(
                [
                    "status",
                    "--home",
                    str(config.home),
                    "--state-root",
                    str(state),
                ]
            )
            self.assertEqual(code, manage.EXIT_REFUSED)
            self.assertNotEqual(code, manage.EXIT_OK)


@unittest.skipIf(
    os.name == "nt",
    "native-Windows statusline activation is uncertified and fails closed (AGENTS.md); these cases"
    " resolve a POSIX state-root fallback and read a ledger row published at mode 0o755",
)
class StatuslineCliFallbackTests(unittest.TestCase):
    """The paths taken when `--state-root` is NOT supplied (W1 finding (c)).

    Every other CLI case in this file passes `--state-root` and used to pass `--bin-dir`, so the
    fallback derivations ran only in unit tests against the helper, never through `main()` -- and
    `main()` is where a wrong fallback would send an operator's receipt and ledger read. Two rules
    are honoured throughout, per agentic-sdlc-8dca: HOME and XDG_STATE_HOME are redirected into a
    temporary root even when a refusal is expected FIRST, because a refusal is not a blast shield
    (this wave's own mutations delete refusals), and each case asserts the exact set of files that
    appeared under that root rather than only the one it came for.
    """

    def files_under(self, root: Path) -> list[str]:
        return sorted(
            str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
        )

    def test_an_unsupplied_state_root_resolves_under_the_supplied_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False) as patched:
                patched.pop("XDG_STATE_HOME", None)

                code = manage.main(["status", "--home", str(home)])

            self.assertEqual(code, manage.EXIT_OK)
            self.assertEqual(manage.state_root_for(home), home / ".local" / "state")
            # The lock file IS the observable proof of where the fallback pointed: `status` takes
            # the ledger's lock, which `_status` names as the one real effect its read path admits.
            self.assertEqual(
                self.files_under(root),
                [str(Path("home/.local/state/agentic-sdlc-installer/installer.lock"))],
            )

    def test_xdg_state_home_overrides_the_home_relative_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            xdg = root / "xdg-state"
            with mock.patch.dict(
                os.environ, {"HOME": str(home), "XDG_STATE_HOME": str(xdg)}, clear=False
            ):
                code = manage.main(["status", "--home", str(home)])

            self.assertEqual(code, manage.EXIT_OK)
            self.assertEqual(
                self.files_under(root),
                [str(Path("xdg-state/agentic-sdlc-installer/installer.lock"))],
            )
            self.assertFalse((home / ".local").exists())

    def test_an_unsupplied_home_resolves_from_the_environment(self) -> None:
        """`--home` defaults to `Path.home()`, so the settings path and the state root follow HOME."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False) as patched:
                patched.pop("XDG_STATE_HOME", None)

                code = manage.main(["status"])

            self.assertEqual(code, manage.EXIT_OK)
            self.assertEqual(
                self.files_under(root),
                [str(Path("home/.local/state/agentic-sdlc-installer/installer.lock"))],
            )

    def test_activate_through_the_fallback_names_the_owned_ledger_row(self) -> None:
        """The fallback resolves BOTH stores: the receipt's root and the ledger the row lives in."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            state_root = home / ".local" / "state"
            # Installed against the REAL payload tree, because `ledger_config` resolves the repo
            # root from the module's own location: the row an operator activates is the shipped one.
            config = installer.Config(
                ROOT, home, root / "codex", "auto", False, "claude", state_root
            )
            self.assertEqual(installer.install(config).exit_code, 0)
            destination = home / ".claude" / "statusline" / "agentic-sdlc-statusline"
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o755)

            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False) as patched:
                patched.pop("XDG_STATE_HOME", None)

                code = manage.main(["activate"])

            self.assertEqual(code, manage.EXIT_OK)
            settings = json.loads((home / ".claude" / "settings.json").read_text())
            self.assertEqual(settings["statusLine"]["command"], shlex.quote(str(destination)))
            self.assertTrue(manage.receipt_path(state_root).is_file())

    def test_a_refusal_under_the_fallback_writes_nothing_into_the_claude_home(self) -> None:
        """Isolated homes even though the refusal comes first: nothing installed, so nothing named."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False) as patched:
                patched.pop("XDG_STATE_HOME", None)

                code = manage.main(["activate", "--home", str(home)])

            self.assertEqual(code, manage.EXIT_REFUSED)
            self.assertFalse((home / ".claude").exists())
            self.assertEqual(
                self.files_under(root),
                [str(Path("home/.local/state/agentic-sdlc-installer/installer.lock"))],
            )

    def test_the_retired_bin_dir_option_is_refused_rather_than_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            home.mkdir()
            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                with self.assertRaises(SystemExit) as raised:
                    manage.main(["status", "--home", str(home), "--bin-dir", str(root / "bin")])

            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(self.files_under(root), [])


@unittest.skipIf(
    os.name == "nt",
    "the simulation removes os.fchmod, which native Windows already lacks",
)
class SettingsIoAtomicBytesTests(unittest.TestCase):
    """settings_io unit level: this module is imported as the shared settings_io library by
    manage_claude_hooks.py and manage_claude_workflows.py, whose planes ARE Windows-supported,
    so atomic_bytes must complete without os.fchmod and without leaking its mkstemp staging
    file (the leaked descriptor is what made Windows unlink the temp with WinError 32 and
    killed 29 hooks/workflows tests at TemporaryDirectory cleanup)."""

    def staging_siblings(self, path: Path) -> list[Path]:
        return sorted(path.parent.glob(f".{path.name}.*"))

    def test_atomic_bytes_completes_without_fchmod_and_leaks_no_staging_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "settings.json"
            saved = os.fchmod
            delattr(os, "fchmod")
            try:
                manage.atomic_bytes(target, b"{}\n", 0o600)
            finally:
                os.fchmod = saved  # ALWAYS restore: other tests and code rely on it.
            self.assertEqual(target.read_bytes(), b"{}\n")
            self.assertEqual(self.staging_siblings(target), [])

    def test_atomic_bytes_applies_the_mode_when_fchmod_is_present(self) -> None:
        # Positive control for the guard: with os.fchmod present the requested mode is
        # applied, so the hasattr guard skips only the chmod, never the write. 0o640 is
        # deliberately NOT mkstemp's 0o600 default, so this stat can only pass through fchmod.
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "settings.json"
            manage.atomic_bytes(target, b"{}\n", 0o640)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
            self.assertEqual(self.staging_siblings(target), [])


if __name__ == "__main__":
    unittest.main()
