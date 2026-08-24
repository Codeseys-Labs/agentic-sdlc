from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
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


@unittest.skipIf(
    os.name == "nt",
    "every fixture here installs operator tools through the POSIX-only durable-write plane"
    " (install_operator_tools.install -> lifecycle_lock -> sync_directory, whose os.open of a"
    " directory Windows refuses), and native-Windows statusline activation is uncertified and"
    " fails closed (AGENTS.md)",
)
class ManageClaudeStatuslineTests(unittest.TestCase):
    def setup_environment(self, root: Path) -> tuple[object, Path, Path]:
        home = root / "home"; bin_dir = home / ".local" / "bin"; state = root / "state"
        # Stub ocx/jq/uv directly rather than resolving them through mise (the pattern
        # tests/test_operator_tools.py already uses): this test module exercises the
        # statusline lifecycle, not mise's own tool resolution, and a worktree whose
        # mise.toml has not itself been explicitly trusted must not silently gate every
        # test in this file on that unrelated precondition.
        runtime = root / "runtime"; runtime.mkdir(parents=True, exist_ok=True)
        for name in ("ocx", "jq", "uv"):
            path = runtime / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        config = operator_tools.Config(
            ROOT,
            home,
            bin_dir,
            state,
            require_path=False,
            ocx_path=runtime / "ocx",
            jq_path=runtime / "jq",
            uv_path=runtime / "uv",
            sdlc_python_path=Path(sys.executable),
        )
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
            settings.parent.mkdir(parents=True)
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
            self.assertEqual(messages, [f"statusline active: {settings} -> {manage.managed_values(operator_tools.exact_owned_statusline(config))['command']}"])

    def test_real_status_failure_still_exits_nonzero(self) -> None:
        # Negative control for the whole fix: a GENUINE read failure (unreadable settings) must
        # not be swept into the same 0 the five observed states now share.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, settings, state = self.setup_environment(root)
            settings.parent.mkdir(parents=True)
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
                    "--bin-dir",
                    str(config.bin_dir),
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
                    "--bin-dir",
                    str(config.bin_dir),
                    "--state-root",
                    str(state),
                ]
            )
            self.assertEqual(code, manage.EXIT_REFUSED)
            self.assertNotEqual(code, manage.EXIT_OK)


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
