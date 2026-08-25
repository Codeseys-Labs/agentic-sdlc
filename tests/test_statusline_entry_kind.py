"""The statusline entry kind: owned ledger bytes whose MODE is part of what ownership publishes.

Every other kind is read by a host. This one is EXECUTED by it: `statusLine.command` names the
installed file and Claude Code runs it, so the tracked source's 100644 is a trap the ledger's copy
path would otherwise inherit -- `shutil.copy2` preserves 0644, and a check that reads
`settings.json` passes while the feature is broken (gh #10 phase 2, critique-b row V6). The claims
here are therefore proven by RUNNING the installed file rather than by reading it, and the mode is
asserted with `stat` on the published path rather than trusted from the code that set it.

The rest of the suite asks the question the workflow and hook kinds already answered from different
payloads: does `statusline` ride the SAME discovery, ownership, staging, refresh, preservation, and
removal machinery? Two answers are unique to this kind and get their own tests: `--mode link` cannot
choose a link (a link resolves to the tracked 0644 source), and `exact_owned_statusline` is the only
path from a ledger row to a command an operator's settings may name.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
INSTALLER_PATH = ROOT / "scripts" / "install_skill_bundle.py"
SHIPPED_STATUSLINE = ROOT / "assets" / "claude" / "statusline-command.sh"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


installer = _load("statusline_kind_installer", INSTALLER_PATH)


def _execute_bit_is_observable() -> bool:
    """Whether this filesystem carries the one mode bit this kind publishes and reads back.

    `apply_posix_mode` sets 0o755 and asserts `S_IXUSR`; a Windows filesystem never carries it --
    `chmod(path, 0o755)` cannot grant it and `chmod(path, 0o644)` cannot take it away (measured on
    windows-2025, agentic-sdlc-5ce7) -- so on such a host the fixture cannot establish its own
    premise and the product code records the readback as unavailable rather than failed. Probed on
    a real temporary file rather than branched on `os.name`, so a POSIX host that also cannot
    honour the bit is reported the same way and for the same stated reason.
    """
    with tempfile.NamedTemporaryFile(suffix="-execute-bit-probe", delete=False) as handle:
        probe = Path(handle.name)
    try:
        os.chmod(probe, 0o755)
        return bool(os.stat(probe).st_mode & stat.S_IXUSR)
    finally:
        probe.unlink(missing_ok=True)


EXECUTE_BIT_IS_OBSERVABLE = _execute_bit_is_observable()
EXECUTE_BIT_SKIP_REASON = (
    "this filesystem does not carry the owner-execute bit the statusline kind publishes, so the"
    " mode this asserts cannot be established here (agentic-sdlc-5ce7)"
)
JQ = shutil.which("jq")
JQ_SKIP_REASON = (
    "the shipped statusline renders its full line through jq and degrades to the bare `claude`"
    " fallback without it; the degraded branch is asserted unconditionally by"
    " test_the_installed_file_degrades_to_one_line_without_jq"
)

#: One synthetic Claude Code status payload. Every value is fabricated: this suite renders a status
#: line, it never reads a session.
STDIN_PAYLOAD = json.dumps(
    {
        "workspace": {"project_dir": "/fixture/project"},
        "model": {"id": "claude-fable-5"},
        "effort": {"level": "high"},
        "context_window": {
            "total_input_tokens": 12345,
            "total_output_tokens": 678,
            "used_percentage": 42,
            "context_window_size": 1000000,
        },
        "cost": {"total_cost_usd": 1.25, "total_duration_ms": 90000},
    }
)


class StatuslineKindTestCase(unittest.TestCase):
    """A repo carrying exactly one payload: the SHIPPED statusline bytes, at their tracked mode."""

    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        (self.repo / "assets" / "claude").mkdir(parents=True)
        self.source = self.repo / "assets" / "claude" / "statusline-command.sh"
        shutil.copyfile(SHIPPED_STATUSLINE, self.source)
        # The fixture's own premise, stated rather than inherited from the checkout: the source is
        # NOT executable, so every 0o755 assertion below can only pass through the installer.
        os.chmod(self.source, 0o644)
        self.addCleanup(self.temp.cleanup)

    def config(self, mode: str = "auto", *, agent: str = "claude", dry_run: bool = False):
        return installer.Config(
            self.repo,
            self.root / "home",
            self.root / "codex",
            mode,
            dry_run,
            agent,
            self.root / "state",
        )

    @property
    def entry(self):
        entries = [
            entry for entry in installer.discover_entries(self.repo) if entry.kind == "statusline"
        ]
        self.assertEqual(len(entries), 1, "exactly one statusline payload is expected")
        return entries[0]

    def destination(self, config) -> Path:
        return installer.destination_for(self.entry, config)

    def run_installed(self, destination: Path, *, path_value: str | None = None):
        """Execute the INSTALLED file as a program, with one synthetic payload on stdin.

        No interpreter is named and no `sh` is prepended: the kernel reads the published file's own
        shebang, which it can only do if the file this lifecycle published is executable. That is
        the whole point of running it here instead of reading it.
        """
        environment = dict(os.environ)
        environment["HOME"] = str(self.root / "home")
        if path_value is not None:
            environment["PATH"] = path_value
        return subprocess.run(
            [str(destination)],
            input=STDIN_PAYLOAD,
            capture_output=True,
            text=True,
            cwd=str(self.root),
            env=environment,
            timeout=120,
        )


class StatuslineDiscoveryTests(StatuslineKindTestCase):
    """What the kind is, before anything is installed."""

    def test_the_kind_maps_to_its_own_claude_only_collection(self) -> None:
        self.assertEqual(installer.entry_collection("statusline"), "statusline")
        self.assertIn("statusline", installer.CLAUDE_ONLY_KINDS)
        self.assertNotIn("statusline", installer.DIRECTORY_KINDS)
        self.assertEqual(installer.POSIX_MODE_FOR_KIND["statusline"], 0o755)
        self.assertEqual(installer.COPY_ONLY_KINDS, frozenset({"statusline"}))

    def test_discovery_names_the_installed_command_not_the_source_file(self) -> None:
        entry = self.entry
        self.assertEqual(entry.agent, "claude")
        self.assertEqual(entry.name, installer.STATUSLINE_COMMAND_NAME)
        self.assertEqual(entry.name, "agentic-sdlc-statusline")
        self.assertEqual(entry.source, self.source)
        self.assertNotEqual(entry.name, entry.source.name)

    def test_this_repository_carries_exactly_one_statusline_payload(self) -> None:
        """The claim about THIS tree, not about a fixture."""
        entries = [
            entry for entry in installer.discover_entries(ROOT) if entry.kind == "statusline"
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].source, SHIPPED_STATUSLINE)

    def test_a_tree_without_the_source_discovers_no_statusline(self) -> None:
        """A pruned or older payload tree stays installable rather than raising."""
        self.source.unlink()
        self.assertIsNone(installer.statusline_entry(self.repo))
        self.assertEqual(
            [entry for entry in installer.discover_entries(self.repo) if entry.kind == "statusline"],
            [],
        )

    def test_the_codex_plane_owns_no_statusline_destination(self) -> None:
        codex_config = self.config(agent="codex")
        with self.assertRaisesRegex(installer.InstallerError, "no Codex destination"):
            installer.destination_for(
                installer.Entry("codex", "statusline", self.entry.name, self.source), codex_config
            )


class StatuslineLifecycleTests(StatuslineKindTestCase):
    """The lifecycle chain over the new kind, on the machinery the other kinds use."""

    def test_install_records_ownership_and_uninstall_removes_the_owned_command(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(
            destination,
            config.home / ".claude" / "statusline" / "agentic-sdlc-statusline",
        )

        installed = installer.install(config)

        self.assertEqual(installed.exit_code, 0, installed.messages)
        self.assertIn(f"installed: {destination} (copy)", installed.messages)
        self.assertTrue(destination.is_file())
        self.assertFalse(destination.is_symlink())
        self.assertEqual(destination.read_bytes(), self.source.read_bytes())
        record = installer.load_state(config.state_path)["entries"][str(destination)]
        self.assertEqual(set(record), installer.RECORD_FIELDS)
        self.assertEqual(record["kind"], "statusline")
        self.assertEqual(record["name"], "agentic-sdlc-statusline")
        self.assertEqual(record["mode"], "copy")
        self.assertEqual(record["source"], str(self.source.resolve()))
        self.assertEqual(record["digest"], installer.digest(self.source))
        self.assertTrue(record["removable"])

        removed = installer.uninstall(config)

        self.assertEqual(removed.exit_code, 0, removed.messages)
        self.assertIn(f"removed: {destination}", removed.messages)
        self.assertFalse(destination.exists())
        self.assertEqual(installer.load_state(config.state_path)["entries"], {})

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_the_installed_command_carries_mode_755_the_source_never_had(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(stat.S_IMODE(self.source.stat().st_mode), 0o644)

        self.assertEqual(installer.install(config).exit_code, 0)

        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o755)
        self.assertTrue(os.access(destination, os.X_OK))

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_link_mode_still_publishes_an_executable_copy(self) -> None:
        """`--mode link` cannot choose a link here: a link would carry the source's own 0644."""
        config = self.config(mode="link")
        destination = self.destination(config)

        installed = installer.install(config)

        self.assertEqual(installed.exit_code, 0, installed.messages)
        self.assertIn(f"installed: {destination} (copy)", installed.messages)
        self.assertFalse(destination.is_symlink())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o755)
        self.assertEqual(
            installer.load_state(config.state_path)["entries"][str(destination)]["mode"], "copy"
        )

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_a_link_left_by_another_generation_is_replaced_with_a_copy(self) -> None:
        """Under `--mode link` every other kind ADOPTS such a link; this kind may not."""
        config = self.config(mode="link")
        destination = self.destination(config)
        destination.parent.mkdir(parents=True)
        destination.symlink_to(self.source)

        installed = installer.install(config)

        self.assertEqual(installed.exit_code, 0, installed.messages)
        self.assertIn(f"replaced link with copy: {destination}", installed.messages)
        self.assertFalse(destination.is_symlink())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o755)

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_a_refresh_restores_a_mode_an_operator_removed(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        os.chmod(destination, 0o644)

        refreshed = installer.install(config)

        self.assertEqual(refreshed.exit_code, 0, refreshed.messages)
        self.assertIn(f"refreshed: {destination}", refreshed.messages)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o755)

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_an_identical_but_unexecutable_file_is_preserved_not_adopted(self) -> None:
        """Content equality is not enough for a kind whose payload is executed.

        Adopting it would write a `removable: False` row this lifecycle never republishes, so the
        row's own reader would then refuse the command forever. Preserved and named instead.
        """
        config = self.config()
        destination = self.destination(config)
        destination.parent.mkdir(parents=True)
        shutil.copyfile(self.source, destination)
        os.chmod(destination, 0o644)

        installed = installer.install(config)

        self.assertEqual(installed.exit_code, 1, installed.messages)
        self.assertIn(f"conflict: {destination}", installed.messages)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o644)
        self.assertEqual(installer.load_state(config.state_path)["entries"], {})

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_an_identical_executable_file_is_still_adopted(self) -> None:
        """Positive control for the refusal above: only the MODE decided it."""
        config = self.config()
        destination = self.destination(config)
        destination.parent.mkdir(parents=True)
        shutil.copyfile(self.source, destination)
        os.chmod(destination, 0o755)

        installed = installer.install(config)

        self.assertEqual(installed.exit_code, 0, installed.messages)
        self.assertIn(f"adopted (preserved on uninstall): {destination}", installed.messages)
        record = installer.load_state(config.state_path)["entries"][str(destination)]
        self.assertFalse(record["removable"])

    def test_installing_the_statusline_writes_no_settings_document_anywhere(self) -> None:
        """The install!=enable boundary: naming the command is a separate authorized step."""
        config = self.config()
        destination = self.destination(config)

        self.assertEqual(installer.install(config).exit_code, 0)

        self.assertEqual(sorted(self.root.rglob("settings.json")), [])
        self.assertTrue(destination.is_file(), "positive control: the payload really did land")

    def test_a_dry_run_installs_nothing(self) -> None:
        config = self.config(dry_run=True)
        destination = self.destination(config)

        planned = installer.install(config)

        self.assertEqual(planned.exit_code, 0, planned.messages)
        self.assertIn(f"would install: {destination}", planned.messages)
        self.assertFalse(destination.exists())
        self.assertFalse(config.state_path.exists())


class StatuslineExecutionTests(StatuslineKindTestCase):
    """The named check: EXECUTE the installed file and read what it printed."""

    def installed(self) -> Path:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        return destination

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    @unittest.skipUnless(JQ, JQ_SKIP_REASON)
    def test_executing_the_installed_file_prints_a_status_line(self) -> None:
        destination = self.installed()

        completed = self.run_installed(destination)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(completed.stdout.splitlines()), 1, completed.stdout)
        # Values carried from THIS suite's payload through the installed file's own rendering.
        self.assertIn("fable", completed.stdout)
        self.assertIn("42%", completed.stdout)
        self.assertIn("/fixture/project", completed.stdout)
        self.assertIn("$1.25", completed.stdout)

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_the_installed_file_degrades_to_one_line_without_jq(self) -> None:
        """Unconditional half of the pair, and the harness's own positive control.

        A PATH holding only `bash` and `cat` reaches the shipped script's documented fallback, so
        this asserts that the published bytes ran and printed, on any host, without depending on
        which tools it happens to have.
        """
        destination = self.installed()
        stub_path = self.root / "stub-path"
        stub_path.mkdir()
        for name in ("bash", "cat"):
            resolved = shutil.which(name)
            self.assertIsNotNone(resolved, f"this host has no {name}")
            (stub_path / name).symlink_to(resolved)

        completed = self.run_installed(destination, path_value=str(stub_path))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "claude\n")

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_a_mode_the_installer_did_not_publish_cannot_be_executed(self) -> None:
        """Negative control for both tests above: the exec bit is what made them possible."""
        destination = self.installed()
        os.chmod(destination, 0o644)

        with self.assertRaises(PermissionError):
            self.run_installed(destination)


class ExactOwnedStatuslineTests(StatuslineKindTestCase):
    """The one path from a ledger row to a command an operator's settings may name."""

    def test_an_installed_row_resolves_to_the_published_destination(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)

        self.assertEqual(installer.exact_owned_statusline(config), destination)

    def test_an_uninstalled_statusline_refuses_by_name(self) -> None:
        config = self.config()

        with self.assertRaisesRegex(installer.InstallerError, "not an installed bundle entry"):
            installer.exact_owned_statusline(config)

    def test_a_row_whose_bytes_drifted_refuses_by_name(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        destination.write_text("#!/bin/sh\necho drifted\n", encoding="utf-8")

        with self.assertRaisesRegex(installer.InstallerError, "drifted from its ownership record"):
            installer.exact_owned_statusline(config)

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_an_unexecutable_row_refuses_by_name_even_though_its_bytes_match(self) -> None:
        """Ownership is byte identity and carries no mode, so this refusal is not the digest's."""
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        os.chmod(destination, 0o644)
        record = installer.load_state(config.state_path)["entries"][str(destination)]

        self.assertTrue(
            installer.entry_matches_record(destination, record),
            "positive control: the digest still matches, so only the mode is left to refuse on",
        )
        with self.assertRaisesRegex(installer.InstallerError, "is not executable"):
            installer.exact_owned_statusline(config)

    def test_an_interrupted_lifecycle_transition_refuses_before_resolving(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        state = installer.load_state(config.state_path)
        state["pending"] = installer.pending_slot(
            "uninstall", str(destination), state["entries"][str(destination)], None
        )
        installer.write_state(config.state_path, state, False)

        with self.assertRaisesRegex(installer.InstallerError, "interrupted pending operation"):
            installer.exact_owned_statusline(config)

    def test_a_tree_carrying_no_payload_refuses_before_reading_the_ledger(self) -> None:
        config = self.config()
        self.assertEqual(installer.install(config).exit_code, 0)
        self.source.unlink()

        with self.assertRaisesRegex(installer.InstallerError, "carries no statusline payload"):
            installer.exact_owned_statusline(config)


if __name__ == "__main__":
    unittest.main()
