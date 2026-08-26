"""Behaviour of the byte-identity install lifecycle in `scripts/install_skill_bundle.py`.

The physical-identity witness, the settlement ledger, the per-entry transaction journal, the
~25-tuple recovery classifier, and the v1/v2/v3 state migrations are GONE (demolition rank 4, seed
`agentic-sdlc-0c38`). What replaces them is the shape adapted from the now-deleted
`scripts/install_operator_tools.py` (its PATH plane was removed at gh #10 phase 4, so this module
is now the only copy): a closed seven-field ownership record, one `pending` slot armed before the
bytes move, and `entry_matches_record` as mode + link target + content digest.

`ByteIdentityDoctrineTests` is the pair of tests that pins the doctrine change in BOTH directions:
a destination the operator modified is still refused, and a destination the operator replaced with a
byte-identical copy of the bundle's own payload is now removed. The second is a deliberate,
documented weakening, and it is asserted as the accepted behaviour rather than left to be discovered.
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "install_skill_bundle.py"
WRAPPER = SCRIPT.with_name("install-skill-bundle.sh")
BASH = None if os.name == "nt" else shutil.which("bash")
spec = importlib.util.spec_from_file_location("installer", SCRIPT)
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)

# The shared CLI guard, loaded the way this suite loads every sibling support module. It snapshots the
# operator's real home AT IMPORT, which is here -- before any test in this file patches `HOME`.
CLI_SAFETY = Path(__file__).with_name("installer_cli_safety.py")
_safety_spec = importlib.util.spec_from_file_location("install_bundle_cli_safety", CLI_SAFETY)
assert _safety_spec and _safety_spec.loader
cli_safety = importlib.util.module_from_spec(_safety_spec)
sys.modules[_safety_spec.name] = cli_safety
_safety_spec.loader.exec_module(cli_safety)


class LifecycleTestCase(unittest.TestCase):
    """Shared isolation: every test gets its own state root, never the operator's."""

    def setUp(self) -> None:
        self.state_environment = tempfile.TemporaryDirectory()
        self.state_patch = mock.patch.dict(
            os.environ,
            {
                "XDG_STATE_HOME": self.state_environment.name,
                "LOCALAPPDATA": self.state_environment.name,
            },
            clear=False,
        )
        self.state_patch.start()

    def tearDown(self) -> None:
        self.state_patch.stop()
        self.state_environment.cleanup()

    def make_repo(self, root: Path) -> None:
        (root / "skills" / "example").mkdir(parents=True)
        (root / "skills" / "example" / "SKILL.md").write_text("---\nname: example\n---\n")
        (root / "agents" / "claude").mkdir(parents=True)
        (root / "agents" / "claude" / "role.md").write_text("agent")
        (root / "agents" / "codex" / "research").mkdir(parents=True)
        (root / "agents" / "codex" / "role.toml").write_text("role = true")
        (root / "agents" / "codex" / "research" / "excluded.toml").write_text("excluded")
        (root / "commands").mkdir()
        (root / "commands" / "command.md").write_text("command")
        (root / "workflows").mkdir()
        (root / "workflows" / "wave.js").write_text("// workflow: wave\n")
        # Only `workflows/*.js` is a payload. A sibling of another suffix must stay undiscovered
        # rather than be installed into the workflow collection under a name no host reads.
        (root / "workflows" / "notes.md").write_text("not a workflow")

    def only_entry(self, root: Path, agent: str = "claude") -> installer.Entry:
        return next(
            entry
            for entry in installer.discover_entries(root)
            if entry.agent == agent and entry.kind == "skill"
        )

    def install_only(self, config: installer.Config, entry: installer.Entry) -> installer.Result:
        with mock.patch.object(installer, "discover_entries", return_value=[entry]):
            return installer.install(config)

    def uninstall_only(self, config: installer.Config, entry: installer.Entry) -> installer.Result:
        with mock.patch.object(installer, "discover_entries", return_value=[entry]):
            return installer.uninstall(config)


class InstallSkillBundleTests(LifecycleTestCase):
    def test_discovers_only_supported_top_level_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)

            entries = installer.discover_entries(root)

            self.assertEqual(
                [(entry.agent, entry.kind, entry.name) for entry in entries],
                [
                    ("claude", "skill", "example"),
                    ("codex", "skill", "example"),
                    ("claude", "agent", "role.md"),
                    ("claude", "command", "command.md"),
                    ("codex", "agent", "role.toml"),
                    ("claude", "workflow", "wave.js"),
                ],
            )

    def test_copy_lifecycle_tracks_state_and_uninstalls_owned_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            codex_home = root / "codex"
            self.make_repo(root)
            config = installer.Config(root, home, codex_home, "copy", False, "all")

            result = installer.install(config)
            destination = home / ".claude" / "skills" / "example"

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(destination.is_dir())
            self.assertFalse(destination.is_symlink())
            state = installer.load_state(config.state_path)
            self.assertIn(str(destination), state["entries"])
            self.assertIsNone(state["pending"])
            self.assertEqual(
                set(state["entries"][str(destination)]), installer.RECORD_FIELDS
            )

            removed = installer.uninstall(config)
            self.assertEqual(removed.exit_code, 0)
            self.assertFalse(destination.exists())
            self.assertEqual(installer.load_state(config.state_path)["entries"], {})

    def test_a_published_entry_leaves_no_private_sibling_behind(self) -> None:
        """The staging container is discarded on the refresh path, which needs a REAL refresh.

        A second install of an unchanged payload converges and stages nothing, so reaching the
        refresh through repetition alone would assert this cleanup about a cycle that no longer
        runs. The source is drifted so the refresh is one that genuinely stages, publishes, and has
        a private sibling to discard.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            entry = self.only_entry(root)

            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            destination = installer.destination_for(entry, config)
            (entry.source / "SKILL.md").write_text("---\nname: example\nrevised: true\n---\n")
            refreshed = self.install_only(config, entry)

            self.assertIn(f"refreshed: {destination}", refreshed.messages)
            self.assertEqual(
                sorted(child.name for child in destination.parent.iterdir()), ["example"]
            )
            self.assertEqual(installer.leftover_messages(destination), [])

    def test_link_lifecycle_creates_symlinks_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "link", False, "all")

            result = installer.install(config)
            destination = config.home / ".claude" / "skills" / "example"

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(destination.is_symlink() or installer.is_junction(destination))
            self.assertTrue(os.path.samefile(destination.resolve(), root / "skills" / "example"))
            self.assertEqual(installer.uninstall(config).exit_code, 0)
            self.assertFalse(destination.exists())

    def test_owned_link_is_retargeted_to_current_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "old"
            current = root / "current"
            self.make_repo(old)
            self.make_repo(current)
            config = installer.Config(
                current, root / "home", root / "codex", "link", False, "claude", root / "state"
            )
            destination = config.home / ".claude" / "skills" / "example"
            destination.parent.mkdir(parents=True)
            # The owned link has to be the kind THIS platform's installer creates: a bare
            # `symlink_to` of a directory makes a FILE-type symlink on Windows, which is not a
            # state ownership can hold, and it made this retarget fail as `[WinError 5]`.
            # ...and the record has to carry the mode it actually produced, which is `junction`
            # for a directory source on Windows; a record disagreeing with the live object is a
            # conflict, so the retarget under test would never be reached.
            mode = installer.link_item(old / "skills" / "example", destination)
            state = installer.load_state(config.state_path)
            state["entries"][str(destination)] = installer.entry_record(
                installer.Entry("claude", "skill", "example", old / "skills" / "example"), mode
            )
            installer.write_state(config.state_path, state, False)

            result = installer.install(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.samefile(destination.resolve(), current / "skills" / "example"))
            self.assertTrue(
                any(message.startswith(f"retargeted: {destination} (") for message in result.messages)
            )
            self.assertIsNone(installer.load_state(config.state_path)["pending"])

    def test_adopts_identical_copy_and_exact_legacy_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "adoption-state"
            )
            copy_destination = config.home / ".claude" / "skills" / "example"
            copy_destination.parent.mkdir(parents=True)
            installer.copy_item(root / "skills" / "example", copy_destination)
            agent_destination = config.home / ".claude" / "agents" / "role.md"
            agent_destination.parent.mkdir(parents=True, exist_ok=True)
            agent_destination.symlink_to(root / "agents" / "claude" / "role.md")

            adopted = installer.install(config)

            self.assertIn(f"adopted (preserved on uninstall): {copy_destination}", adopted.messages)
            self.assertIn(f"replaced link with copy: {agent_destination}", adopted.messages)
            self.assertIn("2 adopted", adopted.messages[-1])
            self.assertFalse(agent_destination.is_symlink())

    def test_copy_mode_replaces_exact_legacy_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            destination = config.home / ".claude" / "skills" / "example"
            destination.parent.mkdir(parents=True)
            destination.symlink_to(root / "skills" / "example")

            result = installer.install(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(destination.is_dir())
            self.assertFalse(destination.is_symlink())
            self.assertIn(f"replaced link with copy: {destination}", result.messages)
            state = installer.load_state(config.state_path)
            self.assertEqual(state["entries"][str(destination)]["mode"], "copy")
            self.assertIsNone(state["pending"])

    def test_copy_mode_dry_run_preserves_exact_legacy_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", True, "claude")
            destination = config.home / ".claude" / "skills" / "example"
            destination.parent.mkdir(parents=True)
            destination.symlink_to(root / "skills" / "example")

            result = installer.install(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(destination.is_symlink())
            self.assertIn(f"would replace link with copy: {destination}", result.messages)
            self.assertFalse(config.state_path.exists())

    def test_copy_mode_restores_legacy_link_when_copy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            destination = config.home / ".claude" / "skills" / "example"
            destination.parent.mkdir(parents=True)
            destination.symlink_to(root / "skills" / "example")

            with mock.patch.object(installer, "copy_item", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(installer.InstallerError, "cannot stage"):
                    installer.install(config)

            self.assertTrue(destination.is_symlink())
            self.assertTrue(os.path.samefile(destination, root / "skills" / "example"))
            self.assertFalse(config.state_path.exists())

    def test_legacy_link_mode_recognizes_windows_junction(self) -> None:
        with mock.patch.object(installer, "is_junction", return_value=True), mock.patch.object(
            installer.os.path, "samefile", return_value=True
        ):
            self.assertEqual(
                installer.legacy_link_mode(Path("destination"), Path("source")), "junction"
            )

    def test_adopts_line_ending_only_copy_but_preserves_it_on_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "codex")
            destination = config.codex_home / "skills" / "example"
            destination.mkdir(parents=True)
            source_bytes = (
                (root / "skills" / "example" / "SKILL.md").read_bytes().replace(b"\r\n", b"\n")
            )
            (destination / "SKILL.md").write_bytes(source_bytes.replace(b"\n", b"\r\n"))

            result = installer.install(config)
            removed = installer.uninstall(config)

            self.assertEqual(result.exit_code, 0)
            self.assertIn(f"adopted (preserved on uninstall): {destination}", result.messages)
            self.assertIn(f"kept: {destination} (adopted pre-existing entry)", removed.messages)
            self.assertTrue(destination.exists())

    def test_dry_run_on_a_fresh_host_creates_neither_home_nor_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", True, "all", root / "fresh-state"
            )

            result = installer.install(config)

            self.assertEqual(result.exit_code, 0)
            self.assertFalse((config.home / ".claude").exists())
            self.assertFalse(config.state_path.exists())
            self.assertTrue(any(message.startswith("would install:") for message in result.messages))

    def test_auto_falls_back_to_copy_but_link_mode_is_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            auto = installer.Config(
                root, root / "auto-home", root / "auto-codex", "auto", False, "claude"
            )
            strict = installer.Config(
                root, root / "link-home", root / "link-codex", "link", False, "claude"
            )

            with mock.patch.object(installer, "link_item", side_effect=OSError("not permitted")):
                self.assertEqual(installer.install(auto).exit_code, 0)
                self.assertTrue((auto.home / ".claude" / "skills" / "example").is_dir())
                with self.assertRaises(installer.InstallerError):
                    installer.install(strict)

    def test_auto_falls_back_to_copy_for_failed_windows_junction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "auto", False, "claude")

            with mock.patch.object(
                installer, "platform_system", return_value="Windows"
            ), mock.patch.object(
                installer,
                "make_junction",
                side_effect=installer.subprocess.CalledProcessError(1, ["cmd"]),
            ):
                result = installer.install(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue((config.home / ".claude" / "skills" / "example").is_dir())

    def test_cli_rejects_empty_codex_home(self) -> None:
        """A blank `CODEX_HOME` is refused rather than resolved to some fallback root.

        Isolated homes are supplied even though the refusal fires before any home is read, and the
        temp root's emptiness is asserted independently of the exit code (`agentic-sdlc-8dca`): this
        was the pre-existing test whose safety rested entirely on the product refusing first, and a
        mutation run deletes exactly that. `--codex-home` is deliberately NOT passed, because the
        ambient value is the input under test; the guard follows the blank value to the same
        `<home>/.codex` fallback `main` would reach without its refusal, and admits it as isolated.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.dict(os.environ, {"CODEX_HOME": ""}):
                run = cli_safety.run_cli(
                    self,
                    installer,
                    ["status", "--agent", "claude", "--home", str(root / "home")],
                    must_stay_empty=root,
                )
            self.assertEqual(run.exit_code, 2)
            self.assertIn("CODEX_HOME must not be empty", run.stderr)

    def test_cli_requires_one_agent_selector_on_every_lifecycle_verb(self) -> None:
        """No default and no wildcard: a verb that moves or reads a plane must be told which one.

        The message names BOTH planes, because the operator's next command is the remedy, and each
        verb is asserted separately: `install` is the one gh #11 called out, and a `status` or
        `uninstall` that quietly meant "both" is the same defect one step removed.
        """
        # Isolated homes are supplied even though the refusal fires BEFORE any home is read: this
        # test's own mutation lever removes the refusal, and a lever that then drove a real
        # `uninstall` across the operator's `~/.claude` and `~/.codex` would be a test that damages
        # the machine it is run on. Measured, not hypothetical -- the first run of that mutation did
        # exactly that. The isolation is now enforced by `installer_cli_safety`, so the mutation that
        # deletes this refusal can no longer reach the operator's plane either.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for command in ("install", "status", "uninstall"):
                with self.subTest(command=command):
                    run = cli_safety.run_cli(
                        self,
                        installer,
                        [
                            command,
                            "--home",
                            str(root / "home"),
                            "--codex-home",
                            str(root / "codex"),
                        ],
                        must_stay_empty=root,
                    )
                    self.assertEqual(run.exit_code, 2)
                    self.assertIn(f"{command} requires --agent", run.stderr)
                    self.assertIn("--agent claude", run.stderr)
                    self.assertIn("--agent codex", run.stderr)

    def test_cli_offers_no_wildcard_agent_selector(self) -> None:
        """`--agent all` is not a spelling an operator can reach; argparse names the two that are."""
        stream = io.StringIO()
        with mock.patch("sys.stderr", stream), self.assertRaises(SystemExit) as raised:
            installer.parse_args(["install", "--agent", "all"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("invalid choice: 'all'", stream.getvalue())
        self.assertIn("claude, codex", stream.getvalue())

    def test_self_test_needs_no_selector_because_it_names_no_plane(self) -> None:
        """Positive control for the requirement: the one exempt verb still runs, in its own home.

        `mise run self-test` is a pinned gate leaf that passes no selector, so this is the boundary
        of the requirement rather than a hole in it.
        """
        parsed = installer.parse_args(["self-test"])
        self.assertIsNone(parsed.agent)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # `self_test` builds its own throwaway configuration, so even the homes handed to it here
            # stay untouched -- which `must_stay_empty` asserts separately from the exit code.
            run = cli_safety.run_cli(
                self,
                installer,
                ["self-test", "--home", str(root / "home"), "--codex-home", str(root / "codex")],
                must_stay_empty=root,
            )
            self.assertEqual(run.exit_code, 0)

    def test_cli_rejects_duplicate_agent_selectors(self) -> None:
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as raised:
            installer.parse_args(["install", "--agent", "claude", "--agent", "codex"])
        self.assertEqual(raised.exception.code, 2)

    def test_cli_help_names_configured_roots_agent_selection_and_read_only_modes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], text=True, capture_output=True, check=False
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--claude-home PATH", completed.stdout)
        self.assertIn("--codex-home PATH", completed.stdout)
        self.assertIn("--agent {claude,codex}", completed.stdout)
        self.assertIn("there is no default and no wildcard", completed.stdout)
        self.assertIn("Status and --dry-run never write", completed.stdout)

    def test_cli_offers_no_state_migration_flag(self) -> None:
        """The retired migrations left no vestigial flag behind for an operator to reach for."""
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], text=True, capture_output=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("--migrate-state", completed.stdout)

        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as raised:
            installer.parse_args(["install", "--migrate-state"])
        self.assertEqual(raised.exception.code, 2)

    def test_cli_uses_explicit_claude_home_alias(self) -> None:
        parsed = installer.parse_args(
            ["status", "--claude-home", "/tmp/claude", "--codex-home", "/tmp/codex"]
        )

        self.assertEqual(parsed.claude_home, Path("/tmp/claude"))
        self.assertEqual(parsed.codex_home, Path("/tmp/codex"))

    def test_invalid_state_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "all")
            config.state_path.parent.mkdir(parents=True)
            config.state_path.write_text("not-json")

            with self.assertRaises(installer.InstallerError):
                installer.install(config)

    def test_cli_returns_fatal_code_for_invalid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_root = root / "state"
            state_path = state_root / "agentic-sdlc-installer" / "state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text("invalid")

            with mock.patch.object(installer, "state_directory", return_value=state_root):
                run = cli_safety.run_cli(
                    self,
                    installer,
                    [
                        "status",
                        "--agent",
                        "claude",
                        "--home",
                        str(root / "home"),
                        "--codex-home",
                        str(root / "codex"),
                    ],
                )
            self.assertEqual(run.exit_code, 2)
            # The selector is supplied so this stays a STATE failure: without it the missing-selector
            # refusal would return the same 2 and this test would pass while proving nothing.
            self.assertIn("cannot read state", run.stderr)
            # `--codex-home` is now explicit too: it used to default through the ambient `CODEX_HOME`,
            # so on a host that sets it this read-only verb resolved the operator's own Codex root.
            self.assertFalse((root / "codex").exists())

    def test_changed_codex_home_preserves_old_records_and_installs_new_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            state_root = root / "state"
            old = installer.Config(
                root, root / "home", root / "old-codex", "copy", False, "codex", state_root
            )
            new = installer.Config(
                root, root / "home", root / "new-codex", "copy", False, "codex", state_root
            )
            installer.install(old)
            old_destination = old.codex_home / "skills" / "example"

            claude_status = installer.status(
                installer.Config(
                    root, root / "home", new.codex_home, "copy", False, "claude", state_root
                )
            )
            installed = installer.install(new)
            new_destination = new.codex_home / "skills" / "example"

            self.assertEqual(claude_status.exit_code, 0)
            self.assertEqual(installed.exit_code, 0)
            self.assertTrue(old_destination.exists())
            self.assertTrue(new_destination.exists())

            removed = installer.uninstall(new)

            self.assertEqual(removed.exit_code, 0)
            self.assertTrue(old_destination.exists())
            self.assertFalse(new_destination.exists())
            self.assertIn(str(old_destination), installer.load_state(old.state_path)["entries"])
            self.assertEqual(installer.uninstall(old).exit_code, 0)
            self.assertFalse(old_destination.exists())

    def test_persists_earlier_ownership_when_later_install_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            original = installer.create_destination
            calls = 0

            def fail_second(
                entry: installer.Entry, destination: Path, current: installer.Config
            ) -> str:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("disk full")
                return original(entry, destination, current)

            with mock.patch.object(installer, "create_destination", side_effect=fail_second):
                with self.assertRaisesRegex(installer.InstallerError, "cannot stage"):
                    installer.install(config)

            destination = config.home / ".claude" / "skills" / "example"
            failed = config.home / ".claude" / "agents" / "role.md"
            state = installer.load_state(config.state_path)
            self.assertTrue(destination.exists())
            self.assertTrue(state["entries"][str(destination)]["removable"])
            self.assertNotIn(str(failed), state["entries"])
            self.assertIsNone(state["pending"])

            self.assertEqual(installer.uninstall(config).exit_code, 0)
            self.assertFalse(destination.exists())

    def test_rejects_linked_collection_root_without_external_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            external = root / "external"
            external.mkdir()
            collection = config.home / ".claude" / "skills"
            collection.parent.mkdir(parents=True)
            collection.symlink_to(external, target_is_directory=True)

            with self.assertRaisesRegex(
                installer.InstallerError, "collection root must not be a link"
            ):
                installer.install(config)

            self.assertEqual(list(external.iterdir()), [])
            self.assertFalse(config.state_path.exists())

    def test_retargeted_collection_link_cannot_redirect_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            self.assertEqual(installer.install(config).exit_code, 0)
            destination = config.home / ".claude" / "skills" / "example"
            installer.remove_path(destination)
            collection = destination.parent
            collection.rmdir()
            external = root / "external"
            external.mkdir()
            installer.copy_item(root / "skills" / "example", external / "example")
            collection.symlink_to(external, target_is_directory=True)

            with self.assertRaisesRegex(
                installer.InstallerError, "collection root must not be a link"
            ):
                installer.uninstall(config)

            self.assertTrue((external / "example").exists())

    def test_marketplace_skip_does_not_validate_unused_claude_collections(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "all")
            marketplace = config.home / ".claude" / "plugins" / "marketplaces" / "agentic-sdlc"
            marketplace.mkdir(parents=True)
            external = root / "external"
            external.mkdir()
            collection = config.home / ".claude" / "skills"
            collection.parent.mkdir(parents=True, exist_ok=True)
            collection.symlink_to(external, target_is_directory=True)

            result = installer.install(config)

            self.assertEqual(result.exit_code, 1)
            self.assertTrue(config.codex_home.joinpath("skills", "example").exists())
            self.assertEqual(list(external.iterdir()), [])

    @unittest.skipIf(
        os.name == "nt", "Windows removes a dangling directory symlink with its target"
    )
    def test_uninstall_removes_owned_dangling_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "link", False, "claude", root / "state"
            )
            installer.install(config)
            destination = config.home / ".claude" / "skills" / "example"
            installer.remove_path(root / "skills" / "example")

            result = installer.uninstall(config)

            self.assertEqual(result.exit_code, 0)
            self.assertFalse(destination.is_symlink())
            self.assertNotIn(str(destination), installer.load_state(config.state_path)["entries"])

    def test_install_republishes_a_recorded_destination_the_operator_deleted(self) -> None:
        """The recorded-but-absent shape is what an interrupted publication leaves, so it converges.

        `status` calls it `absent` and `install` writes it again, which is the whole crash story of
        the retired per-entry journal reduced to two ordinary code paths.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            entry = self.only_entry(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            destination = installer.destination_for(entry, config)
            installer.remove_path(destination)

            checked = installer.status(config)
            reinstalled = self.install_only(config, entry)

            self.assertEqual(checked.exit_code, 1)
            self.assertIn(f"absent: {destination}", checked.messages)
            self.assertEqual(reinstalled.exit_code, 0)
            self.assertTrue(
                any(
                    message.startswith(f"installed: {destination} (")
                    for message in reinstalled.messages
                )
            )
            self.assertTrue(destination.is_dir())

    def test_marketplace_overlap_skips_only_claude(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "all")
            marketplace = config.home / ".claude" / "plugins" / "marketplaces" / "agentic-sdlc"
            marketplace.mkdir(parents=True)

            result = installer.install(config)

            self.assertEqual(result.exit_code, 1)
            self.assertFalse((config.home / ".claude" / "skills" / "example").exists())
            self.assertTrue((config.codex_home / "skills" / "example").exists())
            overlaps = [
                message for message in result.messages if message.startswith("marketplace overlap:")
            ]
            self.assertEqual(overlaps, [f"marketplace overlap: {config.home / '.claude'}"])
            self.assertIn("preserved:", result.messages[1])
            self.assertTrue(result.messages[-1].startswith("install summary:"))

    def test_marketplace_overlap_is_visible_in_status_once_and_leaves_codex_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "all")
            marketplace = config.home / ".claude" / "plugins" / "marketplaces" / "agentic-sdlc"
            marketplace.mkdir(parents=True)
            self.assertEqual(
                installer.install(
                    installer.Config(
                        root, config.home, config.codex_home, "copy", False, "codex"
                    )
                ).exit_code,
                0,
            )

            state_before = config.state_path.read_bytes()
            result = installer.status(config)

            self.assertEqual(result.exit_code, 1)
            self.assertEqual(
                [message for message in result.messages if message.startswith("marketplace overlap:")],
                [f"marketplace overlap: {config.home / '.claude'}"],
            )
            self.assertIn(f"ok: {config.codex_home / 'skills' / 'example'}", result.messages)
            self.assertEqual(result.messages[-1], "2 ok, 1 conflict, 0 absent")
            self.assertEqual(config.state_path.read_bytes(), state_before)

    def test_windows_prefers_junction_for_directories_and_symlink_for_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "link", False, "all")
            with mock.patch.object(
                installer, "platform_system", return_value="Windows"
            ), mock.patch.object(
                installer, "is_junction", side_effect=lambda path: path.is_symlink()
            ), mock.patch.object(
                installer,
                "make_junction",
                side_effect=lambda source, destination: destination.symlink_to(
                    source, target_is_directory=True
                ),
            ) as junction, mock.patch.object(
                installer,
                "make_file_symlink",
                side_effect=lambda source, destination: destination.symlink_to(source),
            ) as file_link:
                installer.install(config)

            self.assertGreaterEqual(junction.call_count, 2)
            self.assertGreaterEqual(file_link.call_count, 3)

    def test_uninstall_rejects_noncanonical_state_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "all")
            victim = root / "outside-victim"
            victim.write_text("owned-looking")
            state = installer.load_state(config.state_path)
            state["entries"][str(victim)] = {
                "agent": "claude",
                "kind": "agent",
                "name": victim.name,
                "source": str(victim),
                "mode": "copy",
                "digest": installer.digest(victim),
                "removable": True,
            }
            installer.write_state(config.state_path, state, False)

            with self.assertRaisesRegex(installer.InstallerError, "invalid ownership record"):
                installer.uninstall(config)

            self.assertTrue(victim.exists())

    def test_record_with_an_unknown_field_is_refused_before_mutation(self) -> None:
        """The record key set is CLOSED, so a field this schema does not own fails closed."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            entry = self.only_entry(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            destination = installer.destination_for(entry, config)
            document = json.loads(config.state_path.read_text())
            document["entries"][str(destination)]["destination_identity"] = "stat-v2:1:2:3.4"
            config.state_path.write_text(json.dumps(document))

            with self.assertRaisesRegex(installer.InstallerError, "invalid ownership record"):
                installer.uninstall(config)

            self.assertTrue(destination.exists())

    def test_stale_structural_record_has_no_deletion_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "all")
            victim = root / "old-codex" / "skills" / "example"
            victim.mkdir(parents=True)
            (victim / "SKILL.md").write_text("owned-looking")
            state = installer.load_state(config.state_path)
            state["entries"][str(victim)] = {
                "agent": "codex",
                "kind": "skill",
                "name": "example",
                "source": str(root / "skills" / "example"),
                "mode": "copy",
                "digest": installer.digest(victim),
                "removable": True,
            }
            installer.write_state(config.state_path, state, False)

            result = installer.uninstall(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(victim.exists())
            self.assertIn(str(victim), installer.load_state(config.state_path)["entries"])

    def test_windows_junction_rejects_cmd_metacharacters(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentic-sdlc-&-") as temp:
            with self.assertRaisesRegex(OSError, "unsupported cmd.exe metacharacters"):
                installer.make_junction(Path(temp) / "source", Path(temp) / "destination")

    def test_compatibility_wrapper_preserves_lifecycle_dispatch(self) -> None:
        if not BASH:
            self.skipTest("Bash is required for the compatibility wrapper test")
        cases = {
            (): "run lifecycle:install --",
            ("status",): "run lifecycle:status --",
            ("uninstall",): "run lifecycle:uninstall --",
            ("self-test",): "run self-test --",
            ("--copy",): "run lifecycle:install -- --mode copy",
            ("status", "-n", ":::", "escaped"): "run lifecycle:status -- -n ::: escaped",
        }
        for args, expected in cases.items():
            with self.subTest(args=args), tempfile.TemporaryDirectory() as temp:
                bin_dir = Path(temp) / "bin"
                bin_dir.mkdir()
                trace = Path(temp) / "trace"
                mise = bin_dir / "mise"
                mise.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$TRACE\"\n")
                mise.chmod(0o755)
                result = subprocess.run(
                    [BASH, str(WRAPPER), *args],
                    cwd=SCRIPT.parents[1],
                    env=os.environ
                    | {
                        "PATH": os.pathsep.join((str(bin_dir), os.environ["PATH"])),
                        "TRACE": str(trace),
                    },
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                lines = trace.read_text().splitlines()
                self.assertTrue(lines[0].endswith(expected), lines[0])
                self.assertEqual(len(lines), 1)

    def test_operational_path_spelling_is_not_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            real_home = root / "real-home"
            real_home.mkdir()
            alias_home = root / "alias-home"
            alias_home.symlink_to(real_home, target_is_directory=True)
            config = installer.Config(root, alias_home, root / "codex", "copy", False, "claude")
            entry = self.only_entry(root)

            self.install_only(config, entry)

            key = str(alias_home / ".claude" / "skills" / "example")
            state = installer.load_state(config.state_path)
            self.assertIn(key, state["entries"])
            self.assertNotIn(str(real_home / ".claude" / "skills" / "example"), state["entries"])

    def test_dry_run_fresh_install_writes_nothing_and_calls_no_mutators(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", True, "claude")
            entry = self.only_entry(root)

            with mock.patch.object(Path, "mkdir") as mkdir, mock.patch.object(
                installer.tempfile, "mkdtemp"
            ) as mkdtemp, mock.patch.object(
                installer, "copy_item"
            ) as copy_item, mock.patch.object(
                installer, "link_item"
            ) as link_item, mock.patch.object(
                installer.os, "replace"
            ) as replace, mock.patch.object(
                installer, "remove_path"
            ) as remove, mock.patch.object(installer, "write_state") as write:
                result = self.install_only(config, entry)

            self.assertEqual(result.exit_code, 0)
            mkdir.assert_not_called()
            mkdtemp.assert_not_called()
            copy_item.assert_not_called()
            link_item.assert_not_called()
            replace.assert_not_called()
            remove.assert_not_called()
            write.assert_not_called()
            self.assertFalse(config.home.exists())
            self.assertFalse(config.state_path.exists())

    def test_default_state_path_does_not_follow_configured_home_alias(self) -> None:
        """The state document is per-operator, never relative to a configured home's target.

        Redirecting the configured home is the operator relocating their own plane, and byte identity
        follows it: the recorded destination now reads `absent` and install republishes there. The
        preservation claim that survives the retired identity witness is the one asserted here --
        nothing at the ORIGINAL location is touched.
        """
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            operator_home = root / "operator-home"
            operator_home.mkdir()
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            selected = root / "selected"
            selected.symlink_to(first, target_is_directory=True)
            entry = self.only_entry(root)

            state_environment = {"HOME": str(operator_home)}
            if installer.platform_system() == "Windows":
                state_root = operator_home / "AppData" / "Local"
                state_environment["LOCALAPPDATA"] = str(state_root)
            else:
                state_root = operator_home / ".local" / "state"

            with mock.patch.dict(os.environ, state_environment, clear=False):
                if installer.platform_system() != "Windows":
                    os.environ.pop("XDG_STATE_HOME", None)
                config = installer.Config(root, selected, root / "codex", "copy", False, "claude")
                self.assertEqual(
                    config.state_path, state_root / "agentic-sdlc-installer" / "state.json"
                )
                self.assertEqual(self.install_only(config, entry).exit_code, 0)
                destination = installer.destination_for(entry, config)
                selected.unlink()
                selected.symlink_to(second, target_is_directory=True)

                checked = installer.status(config)
                installed = self.install_only(config, entry)

            self.assertEqual(checked.exit_code, 1)
            self.assertIn(f"absent: {destination}", checked.messages)
            self.assertEqual(installed.exit_code, 0)
            self.assertTrue((second / ".claude" / "skills" / "example" / "SKILL.md").is_file())
            self.assertTrue((first / ".claude" / "skills" / "example" / "SKILL.md").is_file())

    def test_relative_legacy_symlink_is_adopted_and_replaced_without_dereference_damage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = self.only_entry(root)

            link_config = installer.Config(
                root, root / "link-home", root / "link-codex", "link", False, "claude", root / "link-state"
            )
            link_destination = installer.destination_for(entry, link_config)
            link_destination.parent.mkdir(parents=True)
            link_destination.symlink_to(
                os.path.relpath(entry.source, link_destination.parent), target_is_directory=True
            )
            self.assertEqual(self.install_only(link_config, entry).exit_code, 0)
            removed = self.uninstall_only(link_config, entry)
            self.assertEqual(removed.exit_code, 0)
            self.assertFalse(link_destination.is_symlink())
            self.assertTrue(entry.source.is_dir())

            copy_config = installer.Config(
                root, root / "copy-home", root / "copy-codex", "copy", False, "claude", root / "copy-state"
            )
            copy_destination = installer.destination_for(entry, copy_config)
            copy_destination.parent.mkdir(parents=True)
            copy_destination.symlink_to(
                os.path.relpath(entry.source, copy_destination.parent), target_is_directory=True
            )
            replaced = self.install_only(copy_config, entry)
            self.assertEqual(replaced.exit_code, 0)
            self.assertTrue(copy_destination.is_dir())
            self.assertFalse(copy_destination.is_symlink())
            self.assertTrue(entry.source.is_dir())

    def test_owned_copy_requires_the_node_type_its_kind_implies(self) -> None:
        """An empty file and an empty directory digest alike, so the kind decides the node type."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            file_entry = next(
                entry
                for entry in installer.discover_entries(root)
                if entry.agent == "claude" and entry.kind == "agent"
            )
            file_entry.source.write_bytes(b"")
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            self.assertEqual(self.install_only(config, file_entry).exit_code, 0)
            destination = installer.destination_for(file_entry, config)
            record = installer.load_state(config.state_path)["entries"][str(destination)]
            self.assertTrue(installer.entry_matches_record(destination, record))

            destination.unlink()
            destination.mkdir()

            self.assertFalse(installer.entry_matches_record(destination, record))
            removed = self.uninstall_only(config, file_entry)
            self.assertEqual(removed.exit_code, 1)
            self.assertIn(f"conflict: {destination}", removed.messages)
            self.assertTrue(destination.is_dir())

    def test_rename_absent_refuses_a_destination_that_appeared(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.write_text("staged")
            occupied = root / "occupied"
            occupied.write_text("precious")

            with self.assertRaisesRegex(
                installer.PublicationConflict, "rename destination is no longer absent"
            ):
                installer.rename_absent(source, occupied)

            self.assertEqual(occupied.read_text(), "precious")
            self.assertTrue(source.exists())

            with self.assertRaisesRegex(installer.PublicationConflict, "rename source is absent"):
                installer.rename_absent(root / "missing", root / "target")

    def test_publish_replaces_a_file_destination_in_one_namespace_operation(self) -> None:
        """A file-or-link swap needs no rename-aside, so it has no window at all."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = root / "staged"
            staged.write_text("new")
            destination = root / "destination"
            destination.write_text("old")

            with mock.patch.object(
                installer.os, "replace", wraps=installer.os.replace
            ) as replace:
                installer.publish(staged, destination)

            self.assertEqual(destination.read_text(), "new")
            self.assertFalse(staged.exists())
            self.assertEqual(replace.call_count, 1)
            self.assertEqual(sorted(child.name for child in root.iterdir()), ["destination"])

    def test_publish_uses_a_named_aside_for_a_directory_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = root / "staged"
            staged.mkdir()
            (staged / "new.txt").write_text("new")
            destination = root / "destination"
            destination.mkdir()
            (destination / "old.txt").write_text("old")

            with mock.patch.object(
                installer.os, "replace", wraps=installer.os.replace
            ) as replace:
                installer.publish(staged, destination)

            self.assertEqual(replace.call_count, 2)
            self.assertTrue((destination / "new.txt").is_file())
            self.assertFalse((destination / "old.txt").exists())
            self.assertEqual(sorted(child.name for child in root.iterdir()), ["destination"])

    def test_publish_uses_a_named_aside_for_a_windows_directory_link_payload(self) -> None:
        """A junction or directory symlink is a DIRECTORY to Windows' replacing rename.

        Link-mode ownership publishes exactly that payload, and `os.replace` onto an occupied
        name raises `[WinError 5] Access is denied` for it while succeeding onto an absent one, so
        choosing the one-call path made a link retarget fail outright on windows-2025. The
        platform seam is forced here because Linux has no junction and replaces a directory
        symlink in one call, so only the DECISION is observable from this host: the aside pair is
        two namespace operations and the fast path is one.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "new.txt").write_text("new")
            payload = root / "payload"
            payload.symlink_to(source, target_is_directory=True)
            destination = root / "destination"
            destination.write_text("old")

            with mock.patch.object(installer, "platform_system", return_value="Windows"):
                with mock.patch.object(
                    installer.os, "replace", wraps=installer.os.replace
                ) as replace:
                    installer.publish(payload, destination)

            self.assertEqual(replace.call_count, 2)
            self.assertTrue(destination.is_symlink())
            self.assertEqual((destination / "new.txt").read_text(), "new")
            self.assertEqual(sorted(child.name for child in root.iterdir()), ["destination", "source"])

    def test_publish_restores_the_previous_tree_when_the_swap_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = root / "staged"
            staged.mkdir()
            destination = root / "destination"
            destination.mkdir()
            (destination / "old.txt").write_text("old")
            real = installer.os.replace
            calls = 0

            def fail_second(source: object, target: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("publish failed")
                real(source, target)

            with mock.patch.object(installer.os, "replace", side_effect=fail_second):
                with self.assertRaisesRegex(
                    installer.PublicationConflict, "cannot publish"
                ):
                    installer.publish(staged, destination)

            self.assertEqual((destination / "old.txt").read_text(), "old")

    def test_read_only_copy_installs_without_changing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            read_only = root / "agents" / "claude" / "role.md"
            read_only.chmod(0o444)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")

            result = installer.install(config)
            destination = config.home / ".claude" / "agents" / "role.md"

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(destination.stat().st_mode & 0o777, read_only.stat().st_mode & 0o777)

    def test_nested_symlink_is_not_equivalent_to_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            left = root / "left"
            right = root / "right"
            left.mkdir()
            right.mkdir()
            (left / "target").write_text("payload")
            (left / "child").symlink_to(left / "target")
            (right / "target").write_text("payload")
            (right / "child").write_text("payload")

            self.assertFalse(installer.content_equivalent(left, right))

    def test_self_test_runs_isolated_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "all")

            result = installer.self_test(config)

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.messages, ("self-test passed",))
            self.assertFalse(config.home.exists())

    def test_status_on_a_clean_host_names_the_empty_result_and_next_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "all", root / "state"
            )

            checked = installer.status(config)

            self.assertEqual(checked.exit_code, 0)
            self.assertEqual(
                checked.messages[-1],
                "no owned entries for this host (run: mise run lifecycle:install)",
            )

    def test_unmanaged_codex_skill_is_named_by_status_in_the_writers_own_words(self) -> None:
        """`status` names the collision `install` would refuse, and still writes nothing.

        This test asserted the opposite until 2026-08-26: that `status` answered `no owned entries`
        on a host where `install --dry-run` refused, so an operator had to already suspect the
        collision to find it (gh #13 G3, report 01 §D.5). What replaces it is the agreement itself --
        the two readers' conflict lines are compared to EACH OTHER rather than to a literal, so a
        reworded reason on either side fails here instead of drifting apart quietly.
        """
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            codex_home = root / "codex"
            destination = codex_home / "skills" / "example"
            external = root / "external-example"
            external.mkdir()
            (external / "SKILL.md").write_text("foreign\n")
            destination.parent.mkdir(parents=True)
            destination.symlink_to(external, target_is_directory=True)
            config = installer.Config(
                root, root / "home", codex_home, "link", False, "codex", root / "state"
            )
            dry = installer.Config(
                root, root / "home", codex_home, "link", True, "codex", root / "state"
            )

            checked = installer.status(config)
            previewed = self.install_only(dry, self.only_entry(root, "codex"))

            self.assertEqual(checked.exit_code, 1)
            self.assertEqual(checked.messages[-1], "0 ok, 1 conflict, 0 absent")
            expected = installer.conflict_messages(
                destination, "a non-bundle entry already exists"
            )
            for line in expected:
                self.assertIn(line, checked.messages)
                self.assertIn(line, previewed.messages)
            self.assertEqual(previewed.exit_code, 1)
            # The reader is still read-only: naming a collision creates no state document and does
            # not touch the foreign entry it names.
            self.assertTrue(destination.is_symlink())
            self.assertEqual(destination.resolve(), external.resolve())
            self.assertFalse(config.state_path.exists())

    def test_status_always_ends_with_a_counted_summary_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            self.install_only(config, entry)
            destination = installer.destination_for(entry, config)

            installed = installer.status(config)
            installer.remove_path(destination)
            absent = installer.status(config)

            self.assertEqual(installed.exit_code, 0)
            self.assertEqual(installed.messages[-1], "1 ok, 0 conflict, 0 absent")
            self.assertEqual(absent.exit_code, 1)
            self.assertEqual(absent.messages[-1], "0 ok, 0 conflict, 1 absent")

    def test_write_lifecycle_summaries_are_terminal_and_conflicts_name_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            destination = config.home / ".claude" / "skills" / "example"
            destination.mkdir(parents=True)
            (destination / "foreign.txt").write_text("preserve")

            conflicted = installer.install(config)
            removed = installer.uninstall(config)

            self.assertEqual(conflicted.exit_code, 1)
            self.assertIn(f"conflict: {destination}", conflicted.messages)
            self.assertIn(
                f"preserved: {destination} (a non-bundle entry already exists; inspect and resolve it before retrying)",
                conflicted.messages,
            )
            self.assertTrue(conflicted.messages[-1].startswith("install summary:"))
            self.assertEqual(removed.exit_code, 0)
            self.assertTrue(removed.messages[-1].startswith("uninstall summary:"))
            self.assertTrue(destination.exists())

    def test_a_second_install_over_an_unchanged_copy_converges_instead_of_republishing(self) -> None:
        """Convergence is three observables plus one control that MOVES all three.

        `ok:` on its own would also pass on a reader that had stopped publishing entirely, so the
        claim is the conjunction: the published file's inode survives (a republication renames a
        freshly staged payload over the destination), the state document's BYTES survive (a refresh
        rewrites the record), and the content is still the payload's. The drifted-source install at
        the end is the sensitivity control -- it moves all three -- and its inode change cannot be
        an accident of inode reuse, because `publish` allocates the staged copy while the previous
        file is still linked.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, config)

            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            first_inode = (destination / "SKILL.md").stat().st_ino
            first_state = config.state_path.read_bytes()

            second = self.install_only(config, entry)

            self.assertEqual(second.exit_code, 0, second.messages)
            self.assertIn(f"ok: {destination}", second.messages)
            self.assertNotIn(f"refreshed: {destination}", second.messages)
            self.assertEqual((destination / "SKILL.md").stat().st_ino, first_inode)
            self.assertEqual(config.state_path.read_bytes(), first_state)
            self.assertIn("1 unchanged", second.messages[-1])

            (entry.source / "SKILL.md").write_text("---\nname: example\nrevised: true\n---\n")
            third = self.install_only(config, entry)

            self.assertIn(f"refreshed: {destination}", third.messages)
            self.assertNotEqual((destination / "SKILL.md").stat().st_ino, first_inode)
            self.assertNotEqual(config.state_path.read_bytes(), first_state)

    def test_convergence_does_not_survive_a_publication_mode_change(self) -> None:
        """A copy row whose effective mode became `link` is still converted, not called unchanged.

        The digest is equal on both sides of this transition, so digest equality alone would report
        the host converged and leave a copy where the selected mode says a link belongs.
        """
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            as_copy = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            as_link = installer.Config(
                root, root / "home", root / "codex", "link", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, as_copy)

            self.assertEqual(self.install_only(as_copy, entry).exit_code, 0)
            self.assertFalse(destination.is_symlink())
            record = installer.load_state(as_copy.state_path)["entries"][str(destination)]
            self.assertEqual(record["digest"], installer.digest(entry.source))

            converted = self.install_only(as_link, entry)

            self.assertIn(f"refreshed: {destination}", converted.messages)
            self.assertNotIn(f"ok: {destination}", converted.messages)
            self.assertTrue(destination.is_symlink())
            self.assertEqual(
                installer.load_state(as_link.state_path)["entries"][str(destination)]["mode"],
                "link",
            )

    def test_convergence_does_not_survive_a_source_that_moved(self) -> None:
        """Identical bytes from a SECOND checkout still re-point the row at the source installed from.

        The two payloads are byte-identical on purpose, so the digest conjunct holds and only the
        recorded source separates them. A row left naming the first checkout would describe a
        payload this install did not read.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_root = root / "first"
            second_root = root / "second"
            first_root.mkdir()
            self.make_repo(first_root)
            shutil.copytree(first_root, second_root)
            home, codex_home, state = root / "home", root / "codex", root / "state"
            first_config = installer.Config(
                first_root, home, codex_home, "copy", False, "claude", state
            )
            second_config = installer.Config(
                second_root, home, codex_home, "copy", False, "claude", state
            )
            first_entry = self.only_entry(first_root)
            second_entry = self.only_entry(second_root)
            destination = installer.destination_for(first_entry, first_config)

            self.assertEqual(self.install_only(first_config, first_entry).exit_code, 0)
            self.assertEqual(
                installer.digest(first_entry.source), installer.digest(second_entry.source)
            )

            relocated = self.install_only(second_config, second_entry)

            self.assertIn(f"refreshed: {destination}", relocated.messages)
            self.assertEqual(
                installer.load_state(second_config.state_path)["entries"][str(destination)]["source"],
                str(second_entry.source.resolve()),
            )

    def test_status_summary_is_terminal_for_every_counted_shape(self) -> None:
        self.assertEqual(
            installer.status_summary({"ok": 0, "conflict": 0, "absent": 0}),
            "no owned entries for this host (run: mise run lifecycle:install)",
        )
        self.assertEqual(
            installer.status_summary({"ok": 3, "conflict": 2, "absent": 1}),
            "3 ok, 2 conflict, 1 absent",
        )

    def test_status_counts_an_owned_entry_and_a_collision_in_one_terminal_line(self) -> None:
        """The two halves compose into the SAME terminal shape, and the collision is not the owned row.

        The planted collision sits at a different payload destination from the installed entry, so a
        reader that mistook one for the other would produce `1 ok, 0 conflict` or `0 ok, 1 conflict`
        rather than both.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            skill = self.only_entry(root)
            self.assertEqual(self.install_only(config, skill).exit_code, 0)
            command = next(
                entry
                for entry in installer.discover_entries(root)
                if entry.agent == "claude" and entry.kind == "command"
            )
            collision = installer.destination_for(command, config)
            collision.parent.mkdir(parents=True, exist_ok=True)
            collision.write_text("someone else's command\n")

            checked = installer.status(config)

            self.assertEqual(checked.exit_code, 1)
            self.assertEqual(checked.messages[-1], "1 ok, 1 conflict, 0 absent")
            self.assertIn(f"ok: {installer.destination_for(skill, config)}", checked.messages)
            self.assertIn(f"conflict: {collision}", checked.messages)
            self.assertEqual(collision.read_text(), "someone else's command\n")

    def test_status_does_not_call_an_adoptable_destination_a_collision(self) -> None:
        """The false-positive control: install ADOPTS these two, so status must not refuse them.

        Without it, "status reports collisions" is satisfiable by reporting every unowned present
        destination, which would name a legacy link and an identical copy the writer adopts silently
        -- and would make the empty-plane terminal line unreachable on any host mid-adoption.
        """
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "link", False, "claude", root / "state"
            )
            skill = self.only_entry(root)
            command = next(
                entry
                for entry in installer.discover_entries(root)
                if entry.agent == "claude" and entry.kind == "command"
            )
            legacy = installer.destination_for(skill, config)
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.symlink_to(skill.source, target_is_directory=True)
            identical = installer.destination_for(command, config)
            identical.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(command.source, identical)

            checked = installer.status(config)

            self.assertEqual(checked.exit_code, 0, checked.messages)
            self.assertEqual(
                checked.messages[-1],
                "no owned entries for this host (run: mise run lifecycle:install)",
            )
            self.assertFalse(any(message.startswith("conflict:") for message in checked.messages))
            # POSITIVE CONTROL that both plants are the adoptable shapes and not merely unread: the
            # writer names each one as an adoption rather than a preserved collision.
            previewed = installer.install(
                installer.Config(
                    root, root / "home", root / "codex", "link", True, "claude", root / "state"
                )
            )
            self.assertIn(f"adopted: {legacy}", previewed.messages)
            self.assertIn(f"adopted (preserved on uninstall): {identical}", previewed.messages)

    def test_status_refuses_a_linked_collection_it_has_no_owned_row_in(self) -> None:
        """The collection boundary is the one check byte identity cannot substitute for.

        `status` asserted it only for destinations it already owned, so on a host with no rows yet it
        reported `no owned entries` for a collection it could not safely read at all. It now refuses
        by the same name `install` uses, before any destination in that collection is examined.
        """
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            collection = config.home / ".claude" / "skills"
            collection.parent.mkdir(parents=True)
            collection.symlink_to(elsewhere, target_is_directory=True)

            with self.assertRaisesRegex(
                installer.InstallerError, f"collection root must not be a link: {collection}"
            ):
                installer.status(config)
            self.assertFalse(config.state_path.exists())

    def test_codex_home_alias_is_an_allowed_configured_root(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            real = root / "real-codex"
            real.mkdir()
            alias = root / "alias-codex"
            alias.symlink_to(real, target_is_directory=True)
            config = installer.Config(
                root, root / "home", alias, "copy", False, "codex", root / "state"
            )
            entry = self.only_entry(root, "codex")

            installed = self.install_only(config, entry)
            removed = self.uninstall_only(config, entry)

            self.assertEqual(installed.exit_code, 0)
            self.assertEqual(removed.exit_code, 0)
            self.assertFalse((real / "skills" / "example").exists())


class StateSchemaTests(LifecycleTestCase):
    """Every schema but the current one is refused by name, with the remedy in the message."""

    def retired_document(self, version: int) -> dict[str, object]:
        return {"version": version, "entries": {}, "transactions": {}}

    def test_every_retired_schema_is_refused_without_a_rewrite(self) -> None:
        for version in (1, 2, 3):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                config = installer.Config(
                    root, root / "home", root / "codex", "copy", False, "all", root / "state"
                )
                config.state_path.parent.mkdir(parents=True)
                document = json.dumps(self.retired_document(version))
                config.state_path.write_text(document)

                with self.assertRaisesRegex(
                    installer.InstallerError, "remove it and reinstall to rebuild it"
                ):
                    installer.install(config)
                with self.assertRaisesRegex(installer.InstallerError, "different installer schema"):
                    installer.status(config)
                with self.assertRaisesRegex(installer.InstallerError, "different installer schema"):
                    installer.uninstall(config)

                self.assertEqual(config.state_path.read_text(), document)
                self.assertFalse((config.home / ".claude").exists())

    def test_a_newer_schema_is_refused_without_a_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "all", root / "state"
            )
            config.state_path.parent.mkdir(parents=True)
            document = json.dumps({"version": installer.STATE_VERSION + 1, "entries": {}, "pending": None})
            config.state_path.write_text(document)

            with self.assertRaisesRegex(installer.InstallerError, "different installer schema"):
                installer.status(config)

            self.assertEqual(config.state_path.read_text(), document)

    def test_an_unknown_top_level_field_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "all", root / "state"
            )
            config.state_path.parent.mkdir(parents=True)
            config.state_path.write_text(
                json.dumps(
                    {"version": installer.STATE_VERSION, "entries": {}, "pending": None, "extra": 1}
                )
            )

            with self.assertRaisesRegex(installer.InstallerError, "invalid state"):
                installer.status(config)

    def test_a_document_at_the_retired_home_relative_location_fails_no_verb(self) -> None:
        """The hazard is GONE, not renamed: a state document under the configured home is ignored.

        This is the exact configuration the deleted refusal fired on -- a configured home that is
        not the operator's home, with no `XDG_STATE_HOME`, so the retired mirror
        `<configured-home>/.local/state/agentic-sdlc-installer/state.json` is a different file from
        the selected one. A repository handed to `--claude-home` legitimately owns that path, and
        every verb used to die on it. All four now run, the planted bytes are never read, and
        nothing rewrites or removes them.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            operator_home = root / "operator-home"
            operator_home.mkdir()
            configured_home = root / "configured-home"
            configured_home.mkdir()
            with mock.patch.dict(os.environ, {"HOME": str(operator_home)}, clear=False):
                os.environ.pop("XDG_STATE_HOME", None)
                os.environ.pop("LOCALAPPDATA", None)
                with mock.patch.object(
                    installer, "state_directory", return_value=root / "central"
                ):
                    config = installer.Config(
                        root, configured_home, root / "codex", "copy", False, "claude"
                    )
                    planted = (
                        configured_home
                        / ".local"
                        / "state"
                        / "agentic-sdlc-installer"
                        / "state.json"
                    )
                    planted.parent.mkdir(parents=True)
                    planted.write_text('{"not": "this lifecycle\'s document"}', encoding="utf-8")
                    before = planted.read_bytes()

                    self.assertEqual(installer.status(config).exit_code, 0)
                    self.assertEqual(installer.install(config).exit_code, 0)
                    self.assertEqual(installer.status(config).exit_code, 0)
                    self.assertEqual(installer.uninstall(config).exit_code, 0)
                    self.assertEqual(installer.self_test(config).exit_code, 0)

                    self.assertEqual(planted.read_bytes(), before)
                    # And the document the lifecycle DID select is the central one, not the plant.
                    self.assertEqual(
                        config.state_path,
                        root / "central" / "agentic-sdlc-installer" / "state.json",
                    )

    def test_atomic_write_succeeds_where_os_fchmod_does_not_exist(self) -> None:
        """Native Windows has no os.fchmod (CI run 32624250660): the unguarded call raised
        before fdopen took the descriptor, and the still-open handle made the finally-unlink
        fail with WinError 32. On POSIX, simulate the absent attribute; on Windows this
        exercises the real branch natively."""
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "state.json"
            had_fchmod = hasattr(os, "fchmod")
            if had_fchmod:
                original = os.fchmod
                del os.fchmod
            try:
                installer.atomic_write(target, b"{}\n", 0o600)
            finally:
                if had_fchmod:
                    os.fchmod = original
            self.assertEqual(target.read_bytes(), b"{}\n")
            self.assertEqual([p.name for p in Path(temp).iterdir()], ["state.json"])


class ReadOnlyProjectionTests(LifecycleTestCase):
    def test_projection_names_exactly_one_state_path_even_where_two_used_to_differ(self) -> None:
        """The read report's `bundle.state_paths` is one path, in the configuration that split it.

        With no `XDG_STATE_HOME` and a configured home that is not the operator's, the retired
        mirror resolved to a SECOND location, and the projection listed both -- so a report reader
        saw two bundle state paths and, with a document at each, a `state-ambiguous` verdict. There
        is one selected document now, so there is one path and that verdict is unreachable here.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            operator_home = root / "operator-home"
            operator_home.mkdir()
            configured_home = root / "configured-home"
            configured_home.mkdir()
            with mock.patch.dict(os.environ, {"HOME": str(operator_home)}, clear=False):
                os.environ.pop("XDG_STATE_HOME", None)
                os.environ.pop("LOCALAPPDATA", None)
                with mock.patch.object(
                    installer, "state_directory", return_value=root / "central"
                ):
                    config = installer.Config(
                        root, configured_home, root / "codex", "copy", False, "claude"
                    )
                    for path in (
                        config.state_path,
                        configured_home / ".local" / "state" / "agentic-sdlc-installer" / "state.json",
                    ):
                        path.parent.mkdir(parents=True, exist_ok=True)
                        installer.write_state(path, installer.empty_state(), False)

                    selected = config.state_path
                    projection = installer.readonly_projection(config)

            self.assertEqual(projection["state_paths"], [str(selected)])
            self.assertNotIn(
                "state-ambiguous", {finding["code"] for finding in projection["findings"]}
            )

    def test_projection_reports_an_armed_transition_without_a_lock_or_a_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, config)
            installer.ensure_collection(entry, destination, config)
            state = installer.empty_state()
            state["pending"] = installer.pending_slot(
                "install", str(destination), None, installer.entry_record(entry, "copy")
            )
            installer.write_state(config.state_path, state, False)
            before = config.state_path.read_bytes()

            projection = installer.readonly_projection(config)

            self.assertEqual(projection["state"], "blocked")
            self.assertEqual(
                projection["recovery"],
                [
                    {
                        "action": "lifecycle-dry-run",
                        "component": "bundle",
                        "path": "bundle-transition://claude/skill/1",
                        "state": "pending",
                    }
                ],
            )
            self.assertIn(
                "pending-recovery", {finding["code"] for finding in projection["findings"]}
            )
            self.assertEqual(config.state_path.read_bytes(), before)
            self.assertFalse(config.state_path.with_name("installer.lock").exists())

    def test_projection_types_malformed_and_foreign_evidence_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            config.state_path.parent.mkdir(parents=True)
            config.state_path.write_text('{"version":4,"entries":{},"entries":{},"pending":null}')
            malformed_before = config.state_path.read_bytes()

            malformed = installer.readonly_projection(config)

            self.assertEqual(malformed["state"], "unreadable")
            self.assertIn("state-malformed", {finding["code"] for finding in malformed["findings"]})
            self.assertEqual(config.state_path.read_bytes(), malformed_before)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            self.install_only(config, entry)
            destination = installer.destination_for(entry, config)
            (destination / "SKILL.md").write_text("foreign replacement")
            before = config.state_path.read_bytes()

            foreign = installer.readonly_projection(config)

            self.assertEqual(foreign["state"], "degraded")
            self.assertIn(
                "owned-entry-conflict", {finding["code"] for finding in foreign["findings"]}
            )
            self.assertEqual(config.state_path.read_bytes(), before)

    def test_projection_is_healthy_for_an_ordinary_installed_plane(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            self.install_only(config, self.only_entry(root))

            projection = installer.readonly_projection(config)

            self.assertEqual(projection["state"], "healthy")
            self.assertEqual(projection["findings"], [])
            self.assertEqual(projection["recovery"], [])
            self.assertEqual(
                [entry["state"] for entry in projection["entries"]], ["owned"]
            )


class ByteIdentityDoctrineTests(LifecycleTestCase):
    """The two directions of the honestly-weakened preservation doctrine, both asserted.

    Rank 4 replaced a `stat-v2:<dev>:<ino>:<btime>` physical witness with byte identity. One
    direction had to stay fail-closed and does; the other got weaker and is recorded here as the
    accepted behaviour rather than left for an operator to discover.
    """

    def test_tree_digest_refuses_the_boundary_splice(self) -> None:
        """With byte identity the sole ownership check, the digest stream must be prefix-free.
        Under an unprefixed encoding, deleting `b` and appending its serialized record
        (`F\\0b\\0` + content) to `a` yields the identical stream, so a materially different
        tree would read as owned and uninstall would remove it."""
        with tempfile.TemporaryDirectory() as temp:
            two = Path(temp) / "two"
            two.mkdir()
            (two / "a").write_bytes(b"alpha")
            (two / "b").write_bytes(b"beta")
            spliced = Path(temp) / "spliced"
            spliced.mkdir()
            (spliced / "a").write_bytes(b"alpha" + b"F\0b\0" + b"beta")
            self.assertNotEqual(installer.digest(two), installer.digest(spliced))
            # Positive control: the same walker still answers identical for identical trees.
            twin = Path(temp) / "twin"
            twin.mkdir()
            (twin / "a").write_bytes(b"alpha")
            (twin / "b").write_bytes(b"beta")
            self.assertEqual(installer.digest(two), installer.digest(twin))

    def install_copy(self, root: Path) -> tuple[installer.Config, installer.Entry, Path]:
        self.make_repo(root)
        config = installer.Config(
            root, root / "home", root / "codex", "copy", False, "claude", root / "state"
        )
        entry = self.only_entry(root)
        self.assertEqual(self.install_only(config, entry).exit_code, 0)
        return config, entry, installer.destination_for(entry, config)

    def test_a_tree_the_operator_modified_is_refused_and_preserved(self) -> None:
        """FAIL-CLOSED. Any content the operator adds changes the tree digest, so ownership lapses."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.install_copy(root)
            (destination / "OPERATOR-NOTES.md").write_text("my own working notes\n")
            notes = (destination / "OPERATOR-NOTES.md").read_bytes()

            checked = installer.status(config)
            refreshed = self.install_only(config, entry)
            removed = self.uninstall_only(config, entry)

            for result in (checked, refreshed, removed):
                self.assertEqual(result.exit_code, 1)
                self.assertIn(f"conflict: {destination}", result.messages)
                self.assertIn(
                    f"preserved: {destination} (owned entry changed; inspect and resolve it before retrying)",
                    result.messages,
                )
            self.assertEqual((destination / "OPERATOR-NOTES.md").read_bytes(), notes)
            self.assertIn(str(destination), installer.load_state(config.state_path)["entries"])

    def test_an_edited_file_inside_an_owned_tree_is_refused_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.install_copy(root)
            (destination / "SKILL.md").write_text("---\nname: example\n---\nedited by hand\n")
            edited = (destination / "SKILL.md").read_bytes()

            removed = self.uninstall_only(config, entry)

            self.assertEqual(removed.exit_code, 1)
            self.assertIn(f"conflict: {destination}", removed.messages)
            self.assertEqual((destination / "SKILL.md").read_bytes(), edited)

    def test_a_byte_identical_operator_recopy_is_now_removed(self) -> None:
        """ACCEPTED WEAKENING, asserted as such.

        The retired physical witness refused this: a delete-and-recopy is a different object even
        when it is the same bytes. Byte identity cannot see the difference and does not pretend to.
        What is removed is a byte-for-byte copy of the bundle's own payload, which is why the harm is
        bounded -- no content the operator authored can be byte-identical to a payload they did not
        write. AGENTS.md and the module docstring both record this.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.install_copy(root)
            recorded = copy.deepcopy(installer.load_state(config.state_path)["entries"][str(destination)])
            # The object the record was minted for is really GONE before the replacement appears.
            # That is the fact this test rests on, and it is asserted rather than inferred from a
            # stat field: an immediate delete-and-recreate can reuse the very same inode, which is
            # itself part of why the retired witness could not discriminate on the reference runner.
            shutil.rmtree(destination)
            self.assertFalse(installer.path_present(destination))
            installer.copy_item(entry.source, destination)

            self.assertEqual(installer.digest(destination), recorded["digest"])
            self.assertTrue(installer.entry_matches_record(destination, recorded))

            removed = self.uninstall_only(config, entry)

            self.assertEqual(removed.exit_code, 0)
            self.assertIn(f"removed: {destination}", removed.messages)
            self.assertFalse(installer.path_present(destination))
            self.assertEqual(installer.load_state(config.state_path)["entries"], {})

    def test_a_repointed_configured_home_removes_an_identical_copy_and_preserves_a_different_one(
        self,
    ) -> None:
        """The sharpest instance of the weakening, spelled out rather than left to be discovered.

        The configured home is the operator's own explicit argument, and `assert_safe_collection`
        deliberately exempts that boundary from its no-links rule, so re-pointing it RELOCATES the
        plane. The retired root-identity witness turned that into a conflict; byte identity follows
        the redirect. Both directions are asserted here, because only the second one is a boundary.
        """
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        for identical in (True, False):
            with self.subTest(identical=identical), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                first = root / "first"
                second = root / "second"
                first.mkdir()
                second.mkdir()
                selected = root / "selected"
                selected.symlink_to(first, target_is_directory=True)
                config = installer.Config(
                    root, selected, root / "codex", "copy", False, "claude", root / "state"
                )
                entry = self.only_entry(root)
                self.assertEqual(self.install_only(config, entry).exit_code, 0)
                destination = installer.destination_for(entry, config)
                relocated = second / ".claude" / "skills" / "example"
                relocated.parent.mkdir(parents=True)
                installer.copy_item(destination, relocated)
                if not identical:
                    (relocated / "OPERATOR-NOTES.md").write_text("mine\n")
                selected.unlink()
                selected.symlink_to(second, target_is_directory=True)

                removed = self.uninstall_only(config, entry)

                if identical:
                    self.assertEqual(removed.exit_code, 0)
                    self.assertIn(f"removed: {destination}", removed.messages)
                    self.assertFalse(relocated.exists())
                else:
                    self.assertEqual(removed.exit_code, 1)
                    self.assertIn(f"conflict: {destination}", removed.messages)
                    self.assertEqual((relocated / "OPERATOR-NOTES.md").read_text(), "mine\n")
                # Either way the ORIGINAL location is untouched: nothing followed the old target.
                self.assertTrue((first / ".claude" / "skills" / "example" / "SKILL.md").is_file())

    def test_a_relinked_owned_link_is_refused_and_preserved(self) -> None:
        """A link the operator re-pointed elsewhere no longer matches its recorded source."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "link", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            destination = installer.destination_for(entry, config)
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            destination.unlink()
            destination.symlink_to(elsewhere, target_is_directory=True)

            removed = self.uninstall_only(config, entry)

            self.assertEqual(removed.exit_code, 1)
            self.assertIn(f"conflict: {destination}", removed.messages)
            self.assertTrue(destination.is_symlink())
            self.assertTrue(elsewhere.is_dir())

    def test_a_recreated_link_to_the_same_source_is_now_removed(self) -> None:
        """The link-mode counterpart of the accepted weakening, spelled out rather than implied."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "link", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            destination = installer.destination_for(entry, config)
            # Recreate it the way this platform's installer does, so the doctrine under test is
            # "the same link, made again" rather than "a different link kind". On Windows the
            # installer publishes a junction for a directory source and a bare `symlink_to` makes
            # a symlink instead, which uninstall correctly reads as a mode conflict.
            installer.remove_path(destination)
            installer.link_item(entry.source, destination)

            removed = self.uninstall_only(config, entry)

            self.assertEqual(removed.exit_code, 0)
            self.assertIn(f"removed: {destination}", removed.messages)
            self.assertFalse(installer.path_present(destination))
            self.assertTrue(entry.source.is_dir())


class PendingTransitionTests(LifecycleTestCase):
    """The single `pending` slot, adapted from the deleted `install_operator_tools`, and what it converges."""

    def prepared(self, root: Path, mode: str = "copy") -> tuple[installer.Config, installer.Entry, Path]:
        self.make_repo(root)
        config = installer.Config(
            root, root / "home", root / "codex", mode, False, "claude", root / "state"
        )
        entry = self.only_entry(root)
        return config, entry, installer.destination_for(entry, config)

    def test_an_install_interrupted_before_the_publish_is_aborted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)

            with mock.patch.object(installer, "publish", side_effect=OSError("power loss")):
                with self.assertRaisesRegex(installer.InstallerError, "cannot install"):
                    self.install_only(config, entry)

            armed = installer.load_state(config.state_path)
            self.assertEqual(armed["pending"]["operation"], "install")
            self.assertEqual(armed["pending"]["path"], str(destination))
            self.assertEqual(armed["entries"], {})
            self.assertFalse(installer.path_present(destination))

            checked = installer.status(config)
            self.assertEqual(checked.exit_code, 1)
            self.assertIn(f"would recover abort: {destination}", checked.messages)

            recovered = self.install_only(config, entry)

            self.assertEqual(recovered.exit_code, 0)
            self.assertIn(f"recovered abort: {destination}", recovered.messages)
            settled = installer.load_state(config.state_path)
            self.assertIsNone(settled["pending"])
            self.assertIn(str(destination), settled["entries"])
            self.assertTrue(destination.is_dir())

    def test_a_read_only_recovery_report_takes_no_durability_barrier(self) -> None:
        """`status` and `--dry-run` resolve an armed transition without committing anything,
        so a failing barrier must not turn their report into a DurabilityError."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)

            with mock.patch.object(installer, "publish", side_effect=OSError("power loss")):
                with self.assertRaisesRegex(installer.InstallerError, "cannot install"):
                    self.install_only(config, entry)

            with mock.patch.object(
                installer,
                "fsync_directory",
                side_effect=installer.DurabilityError("barrier unavailable"),
            ):
                checked = installer.status(config)
            self.assertEqual(checked.exit_code, 1)
            self.assertIn(f"would recover abort: {destination}", checked.messages)

    def test_an_install_interrupted_after_the_publish_is_committed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)

            with mock.patch.object(
                installer, "commit_pending", side_effect=OSError("power loss")
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot install"):
                    self.install_only(config, entry)

            armed = installer.load_state(config.state_path)
            self.assertEqual(armed["pending"]["operation"], "install")
            self.assertEqual(armed["entries"], {})
            self.assertTrue(destination.is_dir())

            recovered = installer.status(config)
            self.assertIn(f"would recover commit: {destination}", recovered.messages)

            applied = self.install_only(config, entry)

            self.assertIn(f"recovered commit: {destination}", applied.messages)
            settled = installer.load_state(config.state_path)
            self.assertIsNone(settled["pending"])
            self.assertIn(str(destination), settled["entries"])

    def test_a_refresh_interrupted_after_the_publish_is_committed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            (entry.source / "SKILL.md").write_text("---\nname: example\n---\nupdated\n")

            with mock.patch.object(
                installer, "commit_pending", side_effect=OSError("power loss")
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot refresh"):
                    self.install_only(config, entry)

            armed = installer.load_state(config.state_path)
            self.assertEqual(armed["pending"]["operation"], "refresh")
            self.assertEqual((destination / "SKILL.md").read_text(), "---\nname: example\n---\nupdated\n")

            applied = self.install_only(config, entry)

            self.assertIn(f"recovered commit: {destination}", applied.messages)
            settled = installer.load_state(config.state_path)
            self.assertIsNone(settled["pending"])
            self.assertEqual(
                settled["entries"][str(destination)]["digest"], installer.digest(destination)
            )

    def test_an_uninstall_interrupted_after_the_aside_rename_is_committed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)

            with mock.patch.object(
                installer, "commit_pending", side_effect=OSError("power loss")
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot remove"):
                    self.uninstall_only(config, entry)

            armed = installer.load_state(config.state_path)
            self.assertEqual(armed["pending"]["operation"], "uninstall")
            self.assertIn(str(destination), armed["entries"])
            self.assertFalse(installer.path_present(destination))

            recovered = self.uninstall_only(config, entry)

            self.assertIn(f"recovered commit: {destination}", recovered.messages)
            settled = installer.load_state(config.state_path)
            self.assertIsNone(settled["pending"])
            self.assertEqual(settled["entries"], {})
            self.assertTrue(
                any(message.startswith("leftover: ") for message in recovered.messages),
                recovered.messages,
            )

    def test_bytes_matching_neither_recorded_record_are_preserved_and_the_leftover_named(self) -> None:
        """The one window a directory swap accepts: report it and name where the old tree is."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            state = installer.load_state(config.state_path)
            before = copy.deepcopy(state["entries"][str(destination)])
            after = dict(before, digest="0" * 64)
            aside = installer.unique_sibling(destination, "old")
            destination.rename(aside)
            state["pending"] = installer.pending_slot("refresh", str(destination), before, after)
            installer.write_state(config.state_path, state, False)

            checked = installer.status(config)
            attempted = self.install_only(config, entry)

            for result in (checked, attempted):
                self.assertEqual(result.exit_code, 1)
                self.assertIn(f"interrupted conflict: {destination}", result.messages)
                self.assertTrue(
                    any(
                        message == (
                            f"leftover: {aside} (an interrupted write left this private sibling; "
                            "inspect and remove it by hand)"
                        )
                        for message in result.messages
                    ),
                    result.messages,
                )
            self.assertTrue((aside / "SKILL.md").is_file())
            self.assertEqual(
                installer.load_state(config.state_path)["pending"]["operation"], "refresh"
            )

    def test_a_blocked_transition_does_not_stop_the_other_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)
            state = installer.empty_state()
            state["pending"] = installer.pending_slot(
                "refresh",
                str(destination),
                installer.entry_record(entry, "copy"),
                dict(installer.entry_record(entry, "copy"), digest="0" * 64),
            )
            state["entries"][str(destination)] = installer.entry_record(entry, "copy")
            installer.write_state(config.state_path, state, False)

            result = installer.install(config)

            self.assertEqual(result.exit_code, 1)
            self.assertIn(f"interrupted conflict: {destination}", result.messages)
            self.assertTrue((config.home / ".claude" / "agents" / "role.md").is_file())
            self.assertFalse(installer.path_present(destination))

    def test_an_inadmissible_transition_is_refused_rather_than_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)
            record = installer.entry_record(entry, "copy")
            cases = {
                "unknown operation": installer.pending_slot("rename", str(destination), None, record),
                "install with a before record": installer.pending_slot(
                    "install", str(destination), record, record
                ),
                "refresh with no live record": installer.pending_slot(
                    "refresh", str(destination), record, record
                ),
                "uninstall with an after record": installer.pending_slot(
                    "uninstall", str(destination), record, record
                ),
            }
            for label, pending in cases.items():
                with self.subTest(label=label):
                    state = installer.empty_state()
                    state["pending"] = pending
                    with self.assertRaises(installer.InstallerError):
                        installer.validate_pending(config, state)

            # Positive control: the shapes a writer really arms all validate.
            admitted = installer.empty_state()
            admitted["pending"] = installer.pending_slot("install", str(destination), None, record)
            installer.validate_pending(config, admitted)
            owned = installer.empty_state()
            owned["entries"][str(destination)] = record
            owned["pending"] = installer.pending_slot(
                "refresh", str(destination), record, dict(record, digest="0" * 64)
            )
            installer.validate_pending(config, owned)
            owned["pending"] = installer.pending_slot("uninstall", str(destination), record, None)
            installer.validate_pending(config, owned)

    def test_a_dry_run_over_an_armed_transition_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, entry, destination = self.prepared(root)
            state = installer.empty_state()
            state["pending"] = installer.pending_slot(
                "install", str(destination), None, installer.entry_record(entry, "copy")
            )
            installer.write_state(config.state_path, state, False)
            before = config.state_path.read_bytes()
            dry = installer.Config(
                root, config.home, config.codex_home, "copy", True, "claude", config.state_root
            )

            with mock.patch.object(installer.tempfile, "mkdtemp") as mkdtemp, mock.patch.object(
                installer, "copy_item"
            ) as copy_item, mock.patch.object(
                installer.os, "replace"
            ) as replace, mock.patch.object(
                installer, "remove_path"
            ) as remove, mock.patch.object(installer, "write_state") as write:
                checked = installer.status(config)
                planned = self.install_only(dry, entry)

            self.assertIn(f"would recover abort: {destination}", checked.messages)
            self.assertIn(f"would recover abort: {destination}", planned.messages)
            mkdtemp.assert_not_called()
            copy_item.assert_not_called()
            replace.assert_not_called()
            remove.assert_not_called()
            write.assert_not_called()
            self.assertEqual(config.state_path.read_bytes(), before)


class RetiredHomeRelativeStateMirrorTests(unittest.TestCase):
    """No source under `scripts/` or `tests/` reads the retired home-relative state mirror.

    The mirror had four readers plus a lock-time re-check, and deleting only the ones a reviewer
    remembered is how a hazard gets renamed instead of removed. The token is spelled from two halves
    so this file is not itself a match, and the scan is byte-level so a fixture that does not decode
    as text cannot hide one.
    """

    TOKEN = ("legacy" + "_state").encode()
    ROOTS = ("scripts", "tests")
    SKIPPED_TREES = frozenset({"__pycache__"})

    def occurrences(self, paths: list[Path]) -> list[str]:
        return sorted(
            f"{path}:{number}"
            for path in paths
            for number, line in enumerate(path.read_bytes().splitlines(), start=1)
            if self.TOKEN in line
        )

    def scanned_sources(self) -> list[Path]:
        root = Path(__file__).parents[1]
        return [
            path
            for name in self.ROOTS
            for path in sorted((root / name).rglob("*"))
            if path.is_file() and self.SKIPPED_TREES.isdisjoint(path.parts)
        ]

    def test_no_scanned_source_reads_the_retired_mirror(self) -> None:
        sources = self.scanned_sources()
        self.assertGreater(len(sources), 100, "the scan found almost nothing; re-derive its roots")
        self.assertEqual([], self.occurrences(sources))

    def test_the_scan_sees_the_token_it_forbids(self) -> None:
        """Positive control: the assertion above is an absence the scanner can actually detect."""
        with tempfile.TemporaryDirectory() as temp:
            regressed = Path(temp) / "regressed.py"
            regressed.write_bytes(
                b"    root = self.state_root or " + self.TOKEN + b"_directory(self.home)\n"
            )
            self.assertEqual([f"{regressed}:1"], self.occurrences([regressed]))


class ClaudeHomeProjectAdmissionTests(LifecycleTestCase):
    """`agentic-sdlc-3605`: the argv side door that wrote unreceipted ledger rows under a repository.

    The front-door unification's plan claimed wave W1 had deleted `--claude-home`. It had not, so an
    operator could aim the user plane at a git project root and get ownership rows under that
    repository with no receipt naming them -- the un-uninstallable-teammate-clone trap the receipted
    project scope exists to close. What lands here is a refusal on the CLI ONLY: `Config` stays
    constructible with a repository-nested home, because the receipted front door builds one on purpose
    and the fixtures that drive an isolated plane through the library reach it that way too. The last
    test in this class is that boundary, asserted rather than assumed.
    """

    def make_git_project(self, root: Path) -> Path:
        """A directory the shared detector admits as a git project root."""
        metadata = root / ".git"
        metadata.mkdir(parents=True)
        (metadata / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (metadata / "objects").mkdir()
        (metadata / "refs").mkdir()
        return root

    def as_operator_home(self, home: Path) -> Any:
        """Redirect the home `main` reads for its exemption, on both platforms' spellings."""
        return mock.patch.dict(
            os.environ, {"HOME": str(home), "USERPROFILE": str(home)}, clear=False
        )

    def test_a_claude_home_inside_a_git_project_is_refused_by_name(self) -> None:
        """The token, the enclosing root, and the receipted remedy are all in the refusal.

        The home handed over here is an ISOLATED fixture home that merely happens to sit inside a
        fixture repository, which is exactly the shape `installer_cli_safety` must keep admitting: if
        that guard refused it, this product refusal would become an unreachable branch and the two
        would be one control instead of two.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            operator = root / "operator"
            operator.mkdir()
            project = self.make_git_project(root / "project")
            nested = project / "isolated-home"

            with self.as_operator_home(operator):
                run = cli_safety.run_cli(
                    self,
                    installer,
                    [
                        "install",
                        "--agent",
                        "claude",
                        "--claude-home",
                        str(nested),
                        "--codex-home",
                        str(root / "codex"),
                    ],
                )

            self.assertEqual(run.exit_code, 2)
            self.assertIn(installer.CLAUDE_HOME_INSIDE_PROJECT, run.stderr)
            self.assertIn(str(project), run.stderr)
            self.assertIn(
                f"ccodex install --scope project --agent claude --project {project}", run.stderr
            )

    def test_the_refused_project_is_left_exactly_as_it_was(self) -> None:
        """The independent control: refusing is worth nothing if the run still wrote on its way there.

        Asserted as the project tree's own contents rather than as a second reading of the exit code,
        so a refusal that fired AFTER placing a row would fail here while the code assertion passed.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            operator = root / "operator"
            operator.mkdir()
            project = self.make_git_project(root / "project")

            with self.as_operator_home(operator):
                run = cli_safety.run_cli(
                    self,
                    installer,
                    [
                        "install",
                        "--agent",
                        "claude",
                        "--claude-home",
                        str(project),
                        "--codex-home",
                        str(root / "codex"),
                    ],
                )

            self.assertEqual(run.exit_code, 2)
            self.assertEqual(sorted(path.name for path in project.iterdir()), [".git"])
            self.assertFalse((root / "codex").exists())

    def test_every_lifecycle_verb_refuses_the_same_root(self) -> None:
        """One admission for the whole CLI, not one per verb: a read is as unreceipted as a write."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            operator = root / "operator"
            operator.mkdir()
            project = self.make_git_project(root / "project")

            for command, selector in (
                ("install", ["--agent", "claude"]),
                ("status", ["--agent", "claude"]),
                ("uninstall", ["--agent", "claude"]),
                ("install", ["--agent", "codex"]),
                ("self-test", []),
            ):
                with self.subTest(command=command, selector=selector):
                    with self.as_operator_home(operator):
                        run = cli_safety.run_cli(
                            self,
                            installer,
                            [
                                command,
                                *selector,
                                "--claude-home",
                                str(project / "home"),
                                "--codex-home",
                                str(root / "codex"),
                            ],
                        )
                    self.assertEqual(run.exit_code, 2)
                    self.assertIn(installer.CLAUDE_HOME_INSIDE_PROJECT, run.stderr)
            self.assertEqual(sorted(path.name for path in project.iterdir()), [".git"])

    def test_a_home_outside_every_git_project_still_installs(self) -> None:
        """Positive control: the refusal is conditional, so the tests above are about the condition."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            operator = root / "operator"
            operator.mkdir()
            source = root / "payload" / "example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: example\n---\n", encoding="utf-8")

            with self.as_operator_home(operator), mock.patch.object(
                installer,
                "discover_entries",
                return_value=[installer.Entry("claude", "skill", "example", source)],
            ):
                run = cli_safety.run_cli(
                    self,
                    installer,
                    [
                        "install",
                        "--agent",
                        "claude",
                        "--claude-home",
                        str(root / "home"),
                        "--codex-home",
                        str(root / "codex"),
                    ],
                )

            self.assertEqual(run.exit_code, 0)
            self.assertNotIn(installer.CLAUDE_HOME_INSIDE_PROJECT, run.stderr)
            self.assertTrue((root / "home" / ".claude" / "skills" / "example").exists())

    def test_a_version_controlled_operator_home_is_not_a_steered_side_door(self) -> None:
        """The one exemption, asserted so it is a decision rather than an accident.

        A `$HOME` under version control is an ordinary host -- dotfiles repositories are common -- and
        refusing every install on one would break the default user plane for a configuration this
        lifecycle has no quarrel with. So the enclosing root the operator's own home already sits in is
        admitted, and only a home steered into some OTHER repository refuses. The second half is the
        control: on that same host, a different project still refuses.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dotfiles = self.make_git_project(root / "dotfiles-home")
            elsewhere = self.make_git_project(root / "elsewhere")
            source = root / "payload" / "example"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: example\n---\n", encoding="utf-8")

            with self.as_operator_home(dotfiles), mock.patch.object(
                installer,
                "discover_entries",
                return_value=[installer.Entry("claude", "skill", "example", source)],
            ):
                admitted = cli_safety.run_cli(
                    self,
                    installer,
                    [
                        "install",
                        "--agent",
                        "claude",
                        "--claude-home",
                        str(dotfiles),
                        "--codex-home",
                        str(root / "codex"),
                    ],
                )
                refused = cli_safety.run_cli(
                    self,
                    installer,
                    [
                        "install",
                        "--agent",
                        "claude",
                        "--claude-home",
                        str(elsewhere),
                        "--codex-home",
                        str(root / "codex-two"),
                    ],
                )

            self.assertEqual(admitted.exit_code, 0)
            self.assertTrue((dotfiles / ".claude" / "skills" / "example").exists())
            self.assertEqual(refused.exit_code, 2)
            self.assertIn(installer.CLAUDE_HOME_INSIDE_PROJECT, refused.stderr)
            self.assertEqual(sorted(path.name for path in elsewhere.iterdir()), [".git"])

    def test_a_git_entry_that_would_not_admit_still_refuses(self) -> None:
        """Presence, not admission: a BROKEN repository is not a licence to publish inside it.

        The predicate walks to the first `.git` of any shape rather than to the first one that admits,
        because walking past a `.git` this lifecycle cannot read would publish into a parent the
        operator never named -- and a repository whose metadata is currently unreadable is still a
        repository a teammate will clone.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            operator = root / "operator"
            operator.mkdir()
            broken = root / "broken"
            broken.mkdir()
            (broken / ".git").write_text("gitdir: nowhere\nand a second line\n", encoding="utf-8")

            self.assertEqual(
                installer.load_git_project_detector().admit(broken).verdict,
                installer.load_git_project_detector().INVALID_METADATA,
            )
            with self.as_operator_home(operator):
                run = cli_safety.run_cli(
                    self,
                    installer,
                    [
                        "install",
                        "--agent",
                        "claude",
                        "--claude-home",
                        str(broken / "home"),
                        "--codex-home",
                        str(root / "codex"),
                    ],
                )

            self.assertEqual(run.exit_code, 2)
            self.assertIn(installer.CLAUDE_HOME_INSIDE_PROJECT, run.stderr)

    def test_the_library_path_still_publishes_into_a_repository_nested_home(self) -> None:
        """The preserved half: `Config` is not the CLI, and the receipted front door builds one.

        `scripts/ccodex_sdlc.py` reaches this lifecycle by constructing `Config` directly, so a
        refusal in the library would have refused the very path the unification made canonical. The
        fixture home here sits inside a real git project and the whole lifecycle runs on it.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            project = self.make_git_project(root / "project")
            config = installer.Config(
                root, project / "home", root / "codex", "copy", False, "claude"
            )

            self.assertEqual(installer.install(config).exit_code, 0)
            self.assertTrue((project / "home" / ".claude" / "skills" / "example").exists())
            self.assertEqual(installer.status(config).exit_code, 0)
            self.assertEqual(installer.uninstall(config).exit_code, 0)
            # And the enclosing project is still what the CLI would have refused, so this test is
            # about the boundary rather than about a home that was never nested.
            self.assertEqual(
                installer.claude_home_inside_project(
                    project / "home", operator_home=root / "operator"
                ),
                project,
            )


class InstallerCliSafetyGuardTests(LifecycleTestCase):
    """`agentic-sdlc-8dca`: the isolation a mutation run cannot delete.

    The guard lives in `tests/installer_cli_safety.py`, OUTSIDE the code under test, because the
    near-miss it answers was a test kept safe only by a product refusal that the wave's own mutation
    run then removed -- driving a real `uninstall` across the operator's `~/.claude` and `~/.codex`.
    These tests are what make the guard a guard rather than a helper: each names a way a call site can
    fail to isolate, and asserts that `main` is never reached.
    """

    def isolated(self, root: Path, *extra: str) -> list[str]:
        return [
            "status",
            "--agent",
            "claude",
            "--claude-home",
            str(root / "home"),
            "--codex-home",
            str(root / "codex"),
            *extra,
        ]

    def test_the_guard_fails_a_run_that_would_resolve_the_operator_home(self) -> None:
        """No isolated home supplied means the calling test fails, and `main` is never called."""
        with mock.patch.object(installer, "main") as never:
            with self.assertRaises(AssertionError) as raised:
                cli_safety.run_cli(self, installer, ["status", "--agent", "claude"])
        never.assert_not_called()
        self.assertIn(cli_safety.GUARD_REFUSAL, str(raised.exception))
        self.assertIn(str(cli_safety.REAL_HOME), str(raised.exception))

    def test_the_guard_fails_a_home_that_encloses_the_operator_home(self) -> None:
        """Containment is checked in BOTH directions: a parent of the real home is not isolation."""
        with mock.patch.object(installer, "main") as never:
            with self.assertRaises(AssertionError) as raised:
                cli_safety.run_cli(
                    self,
                    installer,
                    [
                        "uninstall",
                        "--agent",
                        "claude",
                        "--claude-home",
                        str(cli_safety.REAL_HOME.parent),
                        "--codex-home",
                        str(cli_safety.REAL_HOME.parent / "codex"),
                    ],
                )
        never.assert_not_called()
        self.assertIn(cli_safety.GUARD_REFUSAL, str(raised.exception))

    def test_the_guard_fails_an_ambient_codex_home_the_test_never_redirected(self) -> None:
        """An omitted `--codex-home` is followed to what `main` would resolve, not assumed safe."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.dict(
                os.environ, {"CODEX_HOME": str(cli_safety.REAL_CODEX_HOME)}, clear=False
            ), mock.patch.object(installer, "main") as never:
                with self.assertRaises(AssertionError) as raised:
                    cli_safety.run_cli(
                        self, installer, ["status", "--agent", "claude", "--home", str(root / "home")]
                    )
            never.assert_not_called()
            self.assertIn(cli_safety.GUARD_REFUSAL, str(raised.exception))
            self.assertIn(str(cli_safety.REAL_CODEX_HOME), str(raised.exception))

    def test_the_guard_fails_an_unredirected_state_root(self) -> None:
        """Isolated homes are not enough: the ownership document is the other operator-owned file."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(
                installer, "state_directory", return_value=cli_safety.REAL_HOME / ".local" / "state"
            ), mock.patch.object(installer, "main") as never:
                with self.assertRaises(AssertionError) as raised:
                    cli_safety.run_cli(self, installer, self.isolated(root))
            never.assert_not_called()
            self.assertIn(cli_safety.GUARD_REFUSAL, str(raised.exception))

    def test_the_guard_admits_an_isolated_run_and_returns_its_report(self) -> None:
        """Positive control: an isolated argv reaches `main` and its output comes back verbatim."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = cli_safety.run_cli(self, installer, self.isolated(root), must_stay_empty=root)

            self.assertEqual(run.exit_code, 0)
            self.assertEqual(run.stderr, "")
            self.assertIn("no owned entries for this host", run.stdout)

    def test_the_guard_admits_a_run_isolated_by_a_redirected_home_alone(self) -> None:
        """The subject is the resolved path, so isolating through `HOME` is isolation."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.dict(
                os.environ, {"HOME": str(root / "home"), "USERPROFILE": str(root / "home")}
            ):
                os.environ.pop("CODEX_HOME", None)
                run = cli_safety.run_cli(self, installer, ["status", "--agent", "claude"])
            self.assertEqual(run.exit_code, 0)

    def test_the_guard_reports_a_sandbox_the_run_dirtied(self) -> None:
        """`must_stay_empty` is a real reading of the filesystem, not a restatement of the verdict."""
        with tempfile.TemporaryDirectory() as payload, tempfile.TemporaryDirectory() as temp:
            source = Path(payload) / "example"
            source.mkdir()
            (source / "SKILL.md").write_text("---\nname: example\n---\n", encoding="utf-8")
            root = Path(temp)

            with mock.patch.object(
                installer,
                "discover_entries",
                return_value=[installer.Entry("claude", "skill", "example", source)],
            ):
                with self.assertRaises(AssertionError) as raised:
                    cli_safety.run_cli(
                        self,
                        installer,
                        [
                            "install",
                            "--agent",
                            "claude",
                            "--claude-home",
                            str(root / "home"),
                            "--codex-home",
                            str(root / "codex"),
                        ],
                        must_stay_empty=root,
                    )
            self.assertIn("created state under", str(raised.exception))
            # The effect it detected was real, so the assertion is about the filesystem.
            self.assertTrue((root / "home" / ".claude" / "skills" / "example").exists())

    def test_the_two_refusals_are_distinguishable_by_name(self) -> None:
        """The guard's reason and the product's must never be reported as one another.

        They answer different questions -- "the TEST did not isolate" against "the OPERATOR aimed the
        user plane at a repository" -- and a shared or overlapping token would let a report about one
        pass as evidence about the other.
        """
        guard = cli_safety.GUARD_REFUSAL
        product = installer.CLAUDE_HOME_INSIDE_PROJECT

        self.assertNotEqual(guard, product)
        self.assertNotIn(guard, product)
        self.assertNotIn(product, guard)

    def test_every_cli_invocation_in_this_module_routes_through_the_guard(self) -> None:
        """Structure, not doctrine: a direct `main` call in this file is a test failure.

        Seed `agentic-sdlc-8dca`'s second item asks for the lesson encoded where a mutation cannot
        remove it. A prose rule in a reference file is removed by nobody and enforced by nobody; this
        scan is what makes a future unisolated call site fail before it can be run.
        """
        needle = "installer" + ".main("
        source = Path(__file__).read_text(encoding="utf-8")

        offenders = [
            f"{index}: {line.strip()}"
            for index, line in enumerate(source.splitlines(), start=1)
            if needle in line
        ]
        self.assertEqual([], offenders)
        # Two positive controls: the scan finds the seam every call site DOES use, and it can see the
        # token it forbids when that token is present.
        self.assertGreaterEqual(source.count("cli_safety.run_cli("), 4)
        self.assertIn(needle, f"        {needle}['uninstall'])\n")


if __name__ == "__main__":
    unittest.main()
