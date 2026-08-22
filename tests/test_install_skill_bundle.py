from __future__ import annotations

import contextlib
import copy
import errno
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "install_skill_bundle.py"
WRAPPER = SCRIPT.with_name("install-skill-bundle.sh")
BASH = None if os.name == "nt" else shutil.which("bash")
spec = importlib.util.spec_from_file_location("installer", SCRIPT)
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


class InstallSkillBundleTests(unittest.TestCase):
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

    @staticmethod
    def advancing_birth_witness():
        """A platform-independent stub birth clock that ADVANCES.

        Stubbing `stat_birth_identity` to a constant is not a neutral simplification: a constant
        birth witness is precisely the pathological host the lifecycle now refuses by name,
        because a witness no replacement can differ from cannot carry an ownership claim. This
        stub keeps a stable value per physical object -- so verification still compares equal --
        while stamping each newly observed object strictly later, which is what any real birth
        clock does and what a recording transaction must be able to prove.
        """
        counter = [0]
        seen: dict[tuple[int, int], str] = {}

        def witness(path: Path, *, follow_symlinks: bool = True) -> str:
            metadata = os.stat(path) if follow_symlinks else os.lstat(path)
            key = (metadata.st_dev, metadata.st_ino)
            if key not in seen:
                counter[0] += 1
                seen[key] = f"{counter[0]}.0"
            return seen[key]

        return witness

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

    def create_armed_create_transaction(
        self, config: installer.Config, entry: installer.Entry
    ) -> tuple[Path, dict[str, object]]:
        destination = installer.destination_for(entry, config)
        installer.ensure_collection(entry, destination, config)
        root_identity, collection_identity = installer.authority_tokens(
            entry, destination, config
        )
        staged = installer.stage_candidate(
            entry, destination, config, root_identity, collection_identity
        )
        tx = installer.transaction_record(
            "create",
            str(destination),
            old_record=None,
            old_owned=False,
            new_record=staged.record,
            stage=staged.artifact,
            backup=None,
        )
        state = installer.empty_state()
        state["transactions"][str(destination)] = tx
        installer.write_state(config.state_path, state, False)
        return destination, tx

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

            removed = installer.uninstall(config)
            self.assertEqual(removed.exit_code, 0)
            self.assertFalse(destination.exists())
            self.assertEqual(installer.load_state(config.state_path)["entries"], {})

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

    def test_uninstall_preserves_replaced_same_target_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "link", False, "claude"
            )
            entry = self.only_entry(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            destination = installer.destination_for(entry, config)
            original_identity = installer.link_identity(destination)
            replacement = destination.with_name("replacement")
            installer.link_item(entry.source, replacement)
            replacement_identity = installer.link_identity(replacement)
            installer.remove_path(destination)
            replacement.rename(destination)

            result = self.uninstall_only(config, entry)

            self.assertNotEqual(replacement_identity, original_identity)
            self.assertEqual(installer.link_identity(destination), replacement_identity)
            self.assertEqual(result.exit_code, 1)
            self.assertIn(f"conflict: {destination}", result.messages)
            self.assertTrue(destination.is_symlink() or installer.is_junction(destination))

    def test_owned_link_is_retargeted_to_current_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "old"
            current = root / "current"
            self.make_repo(old)
            self.make_repo(current)
            config = installer.Config(current, root / "home", root / "codex", "link", False, "claude", root / "state")
            destination = config.home / ".claude" / "skills" / "example"
            destination.parent.mkdir(parents=True)
            destination.symlink_to(old / "skills" / "example")
            root_identity, collection_identity = installer.authority_tokens(
                installer.Entry("claude", "skill", "example", old / "skills" / "example"),
                destination,
                config,
            )
            state = installer.load_state(config.state_path)
            state["entries"][str(destination)] = installer.entry_record(
                installer.Entry("claude", "skill", "example", old / "skills" / "example"),
                "link",
                root_identity,
                collection_identity,
                installed_path=destination,
            )
            installer.write_state(config.state_path, state, False)

            result = installer.install(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.samefile(destination.resolve(), current / "skills" / "example"))
            self.assertTrue(any(message.startswith(f"retargeted: {destination} (") for message in result.messages))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root,
                root / "home",
                root / "codex",
                "copy",
                False,
                "claude",
                root / "modified-copy-state",
            )
            installer.install(config)
            destination = config.home / ".claude" / "skills" / "example"
            (destination / "SKILL.md").write_text("locally modified")

            install_result = installer.install(config)
            uninstall_result = installer.uninstall(config)

            self.assertEqual(install_result.exit_code, 1)
            self.assertIn(f"conflict: {destination}", install_result.messages)
            self.assertEqual(uninstall_result.exit_code, 1)
            self.assertTrue(destination.exists())

    def test_adopts_identical_copy_and_exact_legacy_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root,
                root / "home",
                root / "codex",
                "copy",
                False,
                "claude",
                root / "adoption-state",
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
                with self.assertRaisesRegex(installer.InstallerError, "cannot replace link with copy"):
                    installer.install(config)

            self.assertTrue(destination.is_symlink())
            self.assertTrue(os.path.samefile(destination, root / "skills" / "example"))

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
            source_bytes = (root / "skills" / "example" / "SKILL.md").read_bytes().replace(b"\r\n", b"\n")
            (destination / "SKILL.md").write_bytes(source_bytes.replace(b"\n", b"\r\n"))

            result = installer.install(config)
            removed = installer.uninstall(config)

            self.assertEqual(result.exit_code, 0)
            self.assertIn(f"adopted (preserved on uninstall): {destination}", result.messages)
            self.assertIn(f"kept: {destination} (adopted pre-existing entry)", removed.messages)
            self.assertTrue(destination.exists())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root,
                root / "home",
                root / "codex",
                "copy",
                True,
                "all",
                root / "fresh-state",
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
            auto = installer.Config(root, root / "auto-home", root / "auto-codex", "auto", False, "claude")
            strict = installer.Config(root, root / "link-home", root / "link-codex", "link", False, "claude")

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

            with mock.patch.object(installer, "platform_system", return_value="Windows"), mock.patch.object(
                installer, "stat_birth_identity", self.advancing_birth_witness()
            ), mock.patch.object(
                installer, "make_junction", side_effect=installer.subprocess.CalledProcessError(1, ["cmd"])
            ):
                result = installer.install(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue((config.home / ".claude" / "skills" / "example").is_dir())

    def test_cli_rejects_empty_codex_home(self) -> None:
        with mock.patch.dict(os.environ, {"CODEX_HOME": ""}), mock.patch("sys.stderr"):
            self.assertEqual(installer.main(["status"]), 2)

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
        self.assertIn("--agent {all,claude,codex}", completed.stdout)
        self.assertIn("Status and --dry-run never write", completed.stdout)

    def test_cli_uses_explicit_claude_home_alias(self) -> None:
        parsed = installer.parse_args(["status", "--claude-home", "/tmp/claude", "--codex-home", "/tmp/codex"])

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
            self.assertIn(
                str(old_destination), installer.load_state(old.state_path)["entries"]
            )
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
                with self.assertRaisesRegex(installer.InstallerError, "cannot install"):
                    installer.install(config)

            destination = config.home / ".claude" / "skills" / "example"
            failed = config.home / ".claude" / "agents" / "role.md"
            state = installer.load_state(config.state_path)
            self.assertTrue(destination.exists())
            self.assertTrue(state["entries"][str(destination)]["removable"])
            self.assertNotIn(str(failed), state["entries"])

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

            with self.assertRaisesRegex(installer.InstallerError, "collection root must not be a link"):
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

            with self.assertRaisesRegex(installer.InstallerError, "collection root must not be a link"):
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
            config = installer.Config(root, root / "home", root / "codex", "link", False, "claude", root / "state")
            installer.install(config)
            destination = config.home / ".claude" / "skills" / "example"
            installer.remove_path(root / "skills" / "example")

            result = installer.uninstall(config)

            self.assertEqual(result.exit_code, 0)
            self.assertFalse(destination.is_symlink())
            self.assertNotIn(str(destination), installer.load_state(config.state_path)["entries"])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            installer.install(config)
            destination = config.home / ".claude" / "skills" / "example"
            installer.remove_path(destination)

            result = installer.install(config)

            self.assertEqual(result.exit_code, 1)
            self.assertIn(f"conflict: {destination}", result.messages)
            self.assertFalse(destination.exists())

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
            overlaps = [message for message in result.messages if message.startswith("marketplace overlap:")]
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
            self.assertEqual(installer.install(installer.Config(root, config.home, config.codex_home, "copy", False, "codex")).exit_code, 0)

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
            with mock.patch.object(installer, "platform_system", return_value="Windows"), mock.patch.object(
                installer, "stat_birth_identity", self.advancing_birth_witness()
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

    def test_cli_returns_fatal_code_for_invalid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_root = root / "state"
            state_path = state_root / "agentic-sdlc-installer" / "state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text("invalid")

            with mock.patch.object(installer, "state_directory", return_value=state_root), mock.patch("sys.stderr"):
                self.assertEqual(installer.main(["status", "--home", str(root / "home")]), 2)

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
                "destination_type": "directory",
                "destination_identity": installer.stat_identity(victim),
                "root_identity": installer.stat_identity(victim.parent.parent),
                "collection_identity": installer.stat_identity(victim.parent),
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
            (): "run bundle:install --",
            ("status",): "run bundle:status --",
            ("uninstall",): "run bundle:uninstall --",
            ("self-test",): "run self-test --",
            ("--copy",): "run bundle:install -- --mode copy",
            ("status", "-n", ":::", "escaped"): "run bundle:status -- -n ::: escaped",
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
                    | {"PATH": os.pathsep.join((str(bin_dir), os.environ["PATH"])), "TRACE": str(trace)},
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                lines = trace.read_text().splitlines()
                self.assertTrue(lines[0].endswith(expected), lines[0])
                self.assertEqual(len(lines), 1)

    def test_v1_state_is_inspectable_and_explicitly_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, config)
            destination.parent.mkdir(parents=True)
            installer.copy_item(entry.source, destination)
            v1 = {
                "version": 1,
                "entries": {
                    str(destination): {
                        "agent": entry.agent,
                        "kind": entry.kind,
                        "name": entry.name,
                        "source": str(entry.source.resolve()),
                        "mode": "copy",
                        "digest": installer.digest(destination),
                        "removable": True,
                    }
                },
            }
            installer.write_state(config.state_path, v1, False)
            before = config.state_path.read_bytes()

            inspected = installer.status(config)
            dry = installer.migrate_v1_state(
                installer.Config(
                    root,
                    config.home,
                    config.codex_home,
                    "copy",
                    True,
                    "claude",
                    config.state_root,
                )
            )

            self.assertEqual(inspected.exit_code, 1)
            self.assertIn(f"migration candidate: {destination}", inspected.messages)
            self.assertIn(f"would migrate: {destination}", dry.messages)
            self.assertEqual(config.state_path.read_bytes(), before)

            migrated = installer.migrate_v1_state(config)

            self.assertEqual(migrated.exit_code, 0)
            self.assertFalse(any(message.startswith("installed:") for message in migrated.messages))
            state = installer.load_state(config.state_path)
            self.assertEqual(state["version"], 3)
            self.assertEqual(installer.read_state_document(config.state_path)["version"], 3)
            self.assertIn(str(destination), state["entries"])
            self.assertTrue(state["entries"][str(destination)]["removable"])
            self.assertEqual(installer.uninstall(config).exit_code, 0)
            self.assertFalse(destination.exists())

    def test_v1_migration_rejects_changed_destination_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, config)
            destination.parent.mkdir(parents=True)
            installer.copy_item(entry.source, destination)
            v1 = {
                "version": 1,
                "entries": {
                    str(destination): {
                        "agent": entry.agent,
                        "kind": entry.kind,
                        "name": entry.name,
                        "source": str(entry.source.resolve()),
                        "mode": "copy",
                        "digest": installer.digest(destination),
                        "removable": True,
                    }
                },
            }
            installer.write_state(config.state_path, v1, False)
            (destination / "SKILL.md").write_text("foreign change")
            before = config.state_path.read_bytes()

            with self.assertRaisesRegex(installer.InstallerError, "changed destination"):
                installer.migrate_v1_state(config)

            self.assertEqual(config.state_path.read_bytes(), before)
            self.assertEqual((destination / "SKILL.md").read_text(), "foreign change")

    def test_malformed_v2_is_rejected_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            config.state_path.parent.mkdir(parents=True)
            config.state_path.write_text(
                json.dumps({"version": 3, "entries": {}, "transactions": {"bad": {}}})
            )
            with mock.patch.object(installer, "digest") as hash_path, self.assertRaisesRegex(
                installer.InstallerError, "invalid transaction"
            ):
                installer.status(config)
            hash_path.assert_not_called()

    def test_v1_state_migrates_directly_to_v3_in_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, config)
            destination.parent.mkdir(parents=True)
            installer.copy_item(entry.source, destination)
            v1 = {
                "version": 1,
                "entries": {
                    str(destination): {
                        "agent": entry.agent,
                        "kind": entry.kind,
                        "name": entry.name,
                        "source": str(entry.source.resolve()),
                        "mode": "copy",
                        "digest": installer.digest(destination),
                        "removable": True,
                    }
                },
            }
            installer.write_state(config.state_path, v1, False)

            migrated = installer.migrate_v1_state(config)
            state = installer.load_state(config.state_path)
            on_disk = installer.read_state_document(config.state_path)

            self.assertEqual(migrated.exit_code, 0)
            self.assertEqual(state["version"], installer.STATE_VERSION)
            self.assertEqual(on_disk["version"], installer.STATE_VERSION)
            self.assertIn(str(destination), state["entries"])

    def test_v2_state_is_read_as_v3_without_touching_disk(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, config)
            destination.parent.mkdir(parents=True)
            installer.copy_item(entry.source, destination)
            v2 = {
                "version": 2,
                "entries": {
                    str(destination): installer.entry_record(
                        installer.record_entry(
                            {
                                "agent": entry.agent,
                                "kind": entry.kind,
                                "name": entry.name,
                                "source": str(entry.source.resolve()),
                                "mode": "copy",
                            },
                            str(destination),
                        ),
                        "copy",
                        installer.stat_identity(config.home),
                        installer.stat_identity(destination.parent),
                        removable=True,
                        installed_digest=installer.digest(destination),
                        installed_path=destination,
                    )
                },
                "transactions": {},
            }
            installer.write_state(config.state_path, v2, False)
            before = config.state_path.read_bytes()

            checked = installer.status(config)
            in_memory = installer.load_state(config.state_path)
            after = config.state_path.read_bytes()

            self.assertEqual(checked.exit_code, 0)
            self.assertEqual(in_memory["version"], installer.STATE_VERSION)
            self.assertEqual(after, before)
            self.assertEqual(json.loads(after)["version"], 2)

    def test_v2_state_persists_to_v3_only_with_migrate_state_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, config)
            destination.parent.mkdir(parents=True)
            installer.copy_item(entry.source, destination)
            v2 = {
                "version": 2,
                "entries": {
                    str(destination): installer.entry_record(
                        installer.record_entry(
                            {
                                "agent": entry.agent,
                                "kind": entry.kind,
                                "name": entry.name,
                                "source": str(entry.source.resolve()),
                                "mode": "copy",
                            },
                            str(destination),
                        ),
                        "copy",
                        installer.stat_identity(config.home),
                        installer.stat_identity(destination.parent),
                        removable=True,
                        installed_digest=installer.digest(destination),
                        installed_path=destination,
                    )
                },
                "transactions": {},
            }
            installer.write_state(config.state_path, v2, False)

            migrated = installer.migrate_v1_state(config)
            on_disk = installer.read_state_document(config.state_path)

            self.assertEqual(migrated.exit_code, 0)
            self.assertEqual(on_disk["version"], installer.STATE_VERSION)
            self.assertIn(str(destination), on_disk["entries"])

    def test_state_newer_than_v3_is_refused_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            config.state_path.parent.mkdir(parents=True)
            v4 = {"version": 4, "entries": {}, "transactions": {}}
            config.state_path.write_text(json.dumps(v4))
            before = config.state_path.read_bytes()

            with self.assertRaisesRegex(installer.InstallerError, "newer installer"):
                installer.status(config)

            self.assertEqual(config.state_path.read_bytes(), before)

            with self.assertRaisesRegex(installer.InstallerError, "newer installer"):
                installer.migrate_v1_state(config)

            self.assertEqual(config.state_path.read_bytes(), before)

    def test_create_state_write_failures_are_exactly_recoverable(self) -> None:
        for fail_after_replace in (False, True):
            with self.subTest(fail_after_replace=fail_after_replace), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                config = installer.Config(
                    root, root / "home", root / "codex", "copy", False, "claude"
                )
                entry = self.only_entry(root)
                destination = installer.destination_for(entry, config)
                original_write = installer.write_state
                calls = 0

                def failing_write(path: Path, state: dict[str, object], dry_run: bool) -> None:
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        if fail_after_replace:
                            original_write(path, state, dry_run)
                        raise OSError("state write failed")
                    original_write(path, state, dry_run)

                with mock.patch.object(installer, "write_state", side_effect=failing_write):
                    with self.assertRaisesRegex(installer.InstallerError, "cannot install"):
                        self.install_only(config, entry)

                self.assertFalse(destination.exists())
                self.assertEqual(installer.load_state(config.state_path)["transactions"], {})
                self.assertEqual(self.install_only(config, entry).exit_code, 0)
                state = installer.load_state(config.state_path)
                self.assertIn(str(destination), state["entries"])
                self.assertEqual(state["transactions"], {})

    def test_create_final_state_failure_recovers_published_destination_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            destination = installer.destination_for(entry, config)
            original_write = installer.write_state
            calls = 0

            def fail_final(path: Path, state: dict[str, object], dry_run: bool) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("final state failed")
                original_write(path, state, dry_run)

            with mock.patch.object(installer, "write_state", side_effect=fail_final), mock.patch.object(
                installer, "recover_durable_after_failure"
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot install"):
                    self.install_only(config, entry)

            pending = installer.load_state(config.state_path)
            self.assertTrue(destination.exists())
            self.assertIn(str(destination), pending["transactions"])
            recovered = self.install_only(config, entry)
            self.assertIn(f"recovered: {destination}", recovered.messages)
            final = installer.load_state(config.state_path)
            self.assertIn(str(destination), final["entries"])
            self.assertEqual(final["transactions"], {})
            self.assertEqual(self.install_only(config, entry).exit_code, 0)

    def test_refresh_staging_failure_preserves_old_tree_and_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            destination = installer.destination_for(entry, config)
            old_bytes = (destination / "SKILL.md").read_bytes()
            old_record = json.loads(json.dumps(installer.load_state(config.state_path)["entries"][str(destination)]))
            (entry.source / "SKILL.md").write_text("new source")

            def partial_copy(source: Path, target: Path) -> None:
                target.mkdir()
                (target / "partial").write_text("partial")
                raise OSError("disk full")

            with mock.patch.object(installer, "copy_item", side_effect=partial_copy):
                with self.assertRaisesRegex(installer.InstallerError, "cannot refresh"):
                    self.install_only(config, entry)

            self.assertEqual((destination / "SKILL.md").read_bytes(), old_bytes)
            state = installer.load_state(config.state_path)
            self.assertEqual(state["entries"][str(destination)], old_record)
            self.assertEqual(state["transactions"], {})
            stage_containers = list(
                destination.parent.glob(f".{destination.name}.stage-*")
            )
            self.assertEqual(len(stage_containers), 1)
            self.assertEqual((stage_containers[0] / "payload" / "partial").read_text(), "partial")

    def test_replace_rename_failure_restores_old_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            self.install_only(config, entry)
            destination = installer.destination_for(entry, config)
            old_bytes = (destination / "SKILL.md").read_bytes()
            (entry.source / "SKILL.md").write_text("replacement")
            original_rename = installer._rename_noreplace
            calls = 0

            def fail_publish(source: Path, target: Path, **kwargs: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("publish failed")
                original_rename(source, target, **kwargs)

            with mock.patch.object(installer, "_rename_noreplace", side_effect=fail_publish):
                with self.assertRaisesRegex(installer.InstallerError, "cannot refresh"):
                    self.install_only(config, entry)

            self.assertEqual((destination / "SKILL.md").read_bytes(), old_bytes)
            state = installer.load_state(config.state_path)
            self.assertIn(str(destination), state["entries"])
            self.assertEqual(state["transactions"], {})

    def test_delete_cleanup_failure_retries_only_private_container(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            self.install_only(config, entry)
            destination = installer.destination_for(entry, config)
            original_rmdir = Path.rmdir

            def fail_backup_cleanup(path: Path) -> None:
                if path.name.startswith(f".{destination.name}.backup-"):
                    raise OSError("cleanup failed")
                original_rmdir(path)

            with mock.patch.object(Path, "rmdir", autospec=True, side_effect=fail_backup_cleanup), mock.patch.object(
                installer, "recover_durable_after_failure"
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot remove"):
                    self.uninstall_only(config, entry)

            pending = installer.load_state(config.state_path)
            tx = pending["transactions"][str(destination)]
            backup = Path(tx["backup_container"])
            self.assertEqual(tx["phase"], "cleanup")
            self.assertFalse(destination.exists())
            self.assertTrue(backup.exists())
            recovered = self.uninstall_only(config, entry)
            self.assertIn(f"recovered: {destination}", recovered.messages)
            self.assertFalse(backup.exists())
            self.assertEqual(installer.load_state(config.state_path), installer.empty_state())

    def test_recovery_retries_after_cleanup_completed_before_state_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            self.install_only(config, entry)
            destination = installer.destination_for(entry, config)
            original_write = installer.write_state
            calls = 0

            def fail_final(path: Path, state: dict[str, object], dry_run: bool) -> None:
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError("final state failed")
                original_write(path, state, dry_run)

            with mock.patch.object(installer, "write_state", side_effect=fail_final), mock.patch.object(
                installer, "recover_durable_after_failure"
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot remove"):
                    self.uninstall_only(config, entry)

            pending = installer.load_state(config.state_path)
            tx = pending["transactions"][str(destination)]
            self.assertEqual(tx["phase"], "cleanup")
            self.assertFalse(destination.exists())
            self.assertFalse(Path(tx["backup_container"]).exists())
            recovered = self.uninstall_only(config, entry)
            self.assertIn(f"recovered: {destination}", recovered.messages)
            self.assertEqual(installer.load_state(config.state_path), installer.empty_state())

    def test_pending_create_with_foreign_destination_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            destination, tx = self.create_armed_create_transaction(config, entry)
            destination.mkdir()
            (destination / "foreign").write_text("keep")

            result = self.install_only(config, entry)

            self.assertEqual(result.exit_code, 1)
            self.assertIn(f"interrupted conflict: {destination}", result.messages)
            self.assertEqual((destination / "foreign").read_text(), "keep")
            self.assertEqual(
                installer.load_state(config.state_path)["transactions"][str(destination)], tx
            )

    def test_status_and_dry_run_pending_recovery_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            destination, _ = self.create_armed_create_transaction(config, entry)
            before = config.state_path.read_bytes()
            dry = installer.Config(
                root,
                config.home,
                config.codex_home,
                "copy",
                True,
                "claude",
                config.state_root,
            )

            with mock.patch.object(installer.tempfile, "mkdtemp") as mkdtemp, mock.patch.object(
                installer, "copy_item"
            ) as copy_item, mock.patch.object(installer.os, "rename") as rename, mock.patch.object(
                installer, "remove_path"
            ) as remove, mock.patch.object(installer, "write_state") as write:
                status = installer.status(config)
                planned = self.install_only(dry, entry)

            self.assertIn(f"would recover: {destination}", status.messages)
            self.assertIn(f"would recover: {destination}", planned.messages)
            mkdtemp.assert_not_called()
            copy_item.assert_not_called()
            rename.assert_not_called()
            remove.assert_not_called()
            write.assert_not_called()
            self.assertEqual(config.state_path.read_bytes(), before)

    def test_readonly_projection_preserves_pending_transaction_evidence_without_a_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination, _transaction = self.create_armed_create_transaction(config, entry)
            before = config.state_path.read_bytes()

            projection = installer.readonly_projection(config)

            self.assertEqual(projection["state"], "blocked")
            self.assertEqual(
                projection["recovery"],
                [
                    {
                        "action": "lifecycle-dry-run",
                        "component": "bundle",
                        "path": "bundle-transaction://claude/skill/1",
                        "state": "pending",
                    }
                ],
            )
            self.assertIn("pending-recovery", {finding["code"] for finding in projection["findings"]})
            self.assertEqual(config.state_path.read_bytes(), before)
            self.assertFalse(config.state_path.with_name("installer.lock").exists())

    def test_readonly_projection_types_malformed_and_foreign_evidence_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            config.state_path.parent.mkdir(parents=True)
            config.state_path.write_text('{"version":3,"entries":{},"entries":{},"transactions":{}}')
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
            self.assertIn("owned-entry-conflict", {finding["code"] for finding in foreign["findings"]})
            self.assertEqual(config.state_path.read_bytes(), before)

    def test_root_retarget_and_recreated_path_conflict_without_victim_inspection(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            safe = root / "safe"
            victim = root / "victim"
            safe.mkdir()
            victim.mkdir()
            selected = root / "selected"
            selected.symlink_to(safe, target_is_directory=True)
            config = installer.Config(
                root, selected, root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            self.install_only(config, entry)
            destination = selected / ".claude" / "skills" / "example"
            installer.copy_item(destination, victim / ".claude" / "skills" / "example")
            selected.unlink()
            safe.rename(root / "safe-original")
            safe.mkdir()
            selected.symlink_to(victim, target_is_directory=True)

            with mock.patch.object(installer, "digest", wraps=installer.digest) as hash_path:
                checked = installer.status(config)
                removed = self.uninstall_only(config, entry)

            self.assertEqual(checked.exit_code, 1)
            self.assertEqual(removed.exit_code, 1)
            self.assertIn(f"root/collection conflict: {destination}", checked.messages)
            self.assertTrue((victim / ".claude" / "skills" / "example").exists())
            self.assertIn(str(destination), installer.load_state(config.state_path)["entries"])
            hashed = [Path(call.args[0]) for call in hash_path.call_args_list]
            self.assertFalse(any(str(path).startswith(str(victim)) for path in hashed))

    def test_collection_replacement_conflicts_and_preserves_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            self.install_only(config, entry)
            destination = installer.destination_for(entry, config)
            collection = destination.parent
            old_collection = collection.with_name("skills-old")
            collection.rename(old_collection)
            collection.mkdir()
            installer.copy_item(entry.source, destination)

            result = self.uninstall_only(config, entry)

            self.assertEqual(result.exit_code, 1)
            self.assertIn(f"root/collection conflict: {destination}", result.messages)
            self.assertTrue(destination.exists())
            self.assertIn(str(destination), installer.load_state(config.state_path)["entries"])

    def test_stale_home_transaction_does_not_block_current_home(self) -> None:
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
            entry = self.only_entry(root, "codex")
            old_destination, old_tx = self.create_armed_create_transaction(old, entry)

            result = self.install_only(new, entry)
            new_destination = installer.destination_for(entry, new)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(new_destination.exists())
            state = installer.load_state(new.state_path)
            self.assertEqual(state["transactions"][str(old_destination)], old_tx)
            self.assertIn(str(new_destination), state["entries"])

    def test_operational_path_spelling_is_not_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            real_home = root / "real-home"
            real_home.mkdir()
            alias_home = root / "alias-home"
            alias_home.symlink_to(real_home, target_is_directory=True)
            config = installer.Config(
                root, alias_home, root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)

            self.install_only(config, entry)

            key = str(alias_home / ".claude" / "skills" / "example")
            state = installer.load_state(config.state_path)
            self.assertIn(key, state["entries"])
            self.assertEqual(
                state["entries"][key]["root_identity"], installer.stat_identity(alias_home)
            )

    def test_dry_run_fresh_install_writes_nothing_and_calls_no_mutators(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", True, "claude"
            )
            entry = self.only_entry(root)

            with mock.patch.object(Path, "mkdir") as mkdir, mock.patch.object(
                installer.tempfile, "mkdtemp"
            ) as mkdtemp, mock.patch.object(installer, "copy_item") as copy_item, mock.patch.object(
                installer, "link_item"
            ) as link_item, mock.patch.object(installer.os, "rename") as rename, mock.patch.object(
                installer, "remove_path"
            ) as remove, mock.patch.object(installer, "write_state") as write:
                result = self.install_only(config, entry)

            self.assertEqual(result.exit_code, 0)
            mkdir.assert_not_called()
            mkdtemp.assert_not_called()
            copy_item.assert_not_called()
            link_item.assert_not_called()
            rename.assert_not_called()
            remove.assert_not_called()
            write.assert_not_called()
            self.assertFalse(config.home.exists())
            self.assertFalse(config.state_path.exists())

    def test_default_state_path_does_not_follow_configured_home_alias(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            operator_home = root / "operator-home"
            operator_home.mkdir()
            safe = root / "safe"
            victim = root / "victim"
            safe.mkdir()
            victim.mkdir()
            selected = root / "selected"
            selected.symlink_to(safe, target_is_directory=True)
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
                config = installer.Config(
                    root, selected, root / "codex", "copy", False, "claude"
                )
                self.assertEqual(
                    config.state_path,
                    state_root / "agentic-sdlc-installer" / "state.json",
                )
                self.assertEqual(self.install_only(config, entry).exit_code, 0)
                destination = installer.destination_for(entry, config)
                selected.unlink()
                selected.symlink_to(victim, target_is_directory=True)

                checked = installer.status(config)
                installed = self.install_only(config, entry)

            self.assertEqual(checked.exit_code, 1)
            self.assertEqual(installed.exit_code, 1)
            self.assertIn(f"root/collection conflict: {destination}", checked.messages)
            self.assertFalse((victim / ".claude").exists())

    def test_relative_link_is_not_mutated_before_backup_rename(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = self.only_entry(root)
            config = installer.Config(
                root,
                root / "home",
                root / "codex",
                "copy",
                False,
                "claude",
                root / "state",
            )
            destination = installer.destination_for(entry, config)
            destination.parent.mkdir(parents=True)
            raw_target = os.path.relpath(entry.source, destination.parent)
            destination.symlink_to(raw_target, target_is_directory=True)
            original_rename = installer._rename_noreplace

            def fail_before_backup(source: Path, target: Path, **kwargs: object) -> None:
                if source == destination:
                    self.assertEqual(Path(os.readlink(destination)), Path(raw_target))
                    self.assertTrue(os.path.samefile(destination, entry.source))
                    raise OSError("simulated crash point")
                original_rename(source, target, **kwargs)

            with mock.patch.object(
                installer, "_rename_noreplace", side_effect=fail_before_backup
            ):
                with self.assertRaisesRegex(
                    installer.InstallerError, "cannot replace link with copy"
                ):
                    self.install_only(config, entry)

            self.assertEqual(Path(os.readlink(destination)), Path(raw_target))
            self.assertTrue(os.path.samefile(destination, entry.source))

    @unittest.skipIf(os.name == "nt", "Darwin libc test requires POSIX descriptors")
    def test_darwin_no_replace_uses_renameatx_np_exclusive_flag(self) -> None:
        renameatx_np = mock.Mock(return_value=0)
        library = mock.Mock(renameatx_np=renameatx_np)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "destination"
            source.write_text("payload")

            with mock.patch.object(installer, "platform_system", return_value="Darwin"), mock.patch.object(
                installer.ctypes, "CDLL", return_value=library
            ), mock.patch.object(installer.os, "fsync"):
                installer._rename_noreplace(source, destination)

        args = renameatx_np.call_args.args
        self.assertEqual(args[1], b"source")
        self.assertEqual(args[3:], (b"destination", 0x00000004))

    def test_relative_legacy_symlink_survives_transactional_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = self.only_entry(root)

            link_config = installer.Config(
                root,
                root / "link-home",
                root / "link-codex",
                "link",
                False,
                "claude",
                root / "link-state",
            )
            link_destination = installer.destination_for(entry, link_config)
            link_destination.parent.mkdir(parents=True)
            link_destination.symlink_to(
                os.path.relpath(entry.source, link_destination.parent),
                target_is_directory=True,
            )
            self.assertEqual(self.install_only(link_config, entry).exit_code, 0)
            removed = self.uninstall_only(link_config, entry)
            self.assertEqual(removed.exit_code, 0)
            self.assertFalse(link_destination.is_symlink())

            copy_config = installer.Config(
                root,
                root / "copy-home",
                root / "copy-codex",
                "copy",
                False,
                "claude",
                root / "copy-state",
            )
            copy_destination = installer.destination_for(entry, copy_config)
            copy_destination.parent.mkdir(parents=True)
            copy_destination.symlink_to(
                os.path.relpath(entry.source, copy_destination.parent),
                target_is_directory=True,
            )
            replaced = self.install_only(copy_config, entry)
            self.assertEqual(replaced.exit_code, 0)
            self.assertTrue(copy_destination.is_dir())
            self.assertFalse(copy_destination.is_symlink())

    def test_relative_legacy_symlink_restores_after_publish_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = self.only_entry(root)
            config = installer.Config(
                root,
                root / "home",
                root / "codex",
                "copy",
                False,
                "claude",
                root / "state",
            )
            destination = installer.destination_for(entry, config)
            destination.parent.mkdir(parents=True)
            destination.symlink_to(
                os.path.relpath(entry.source, destination.parent),
                target_is_directory=True,
            )
            original_rename = installer._rename_noreplace
            calls = 0

            def fail_publish(source: Path, target: Path, **kwargs: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("publish failed")
                original_rename(source, target, **kwargs)

            with mock.patch.object(
                installer, "_rename_noreplace", side_effect=fail_publish
            ):
                with self.assertRaisesRegex(
                    installer.InstallerError, "cannot replace link with copy"
                ):
                    self.install_only(config, entry)

            self.assertTrue(destination.is_symlink())
            self.assertTrue(os.path.samefile(destination, entry.source))
            pending = installer.load_state(config.state_path)
            self.assertEqual(pending, installer.empty_state())

            recovered = self.install_only(config, entry)

            self.assertIn(f"replaced link with copy: {destination}", recovered.messages)
            self.assertTrue(destination.is_dir())
            self.assertFalse(destination.is_symlink())
            self.assertEqual(installer.load_state(config.state_path)["transactions"], {})

    def test_owned_copy_requires_recorded_type_and_object_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            file_entry = next(
                entry
                for entry in installer.discover_entries(root)
                if entry.agent == "claude" and entry.kind == "agent"
            )
            file_entry.source.write_bytes(b"")
            file_config = installer.Config(
                root,
                root / "file-home",
                root / "file-codex",
                "copy",
                False,
                "claude",
                root / "file-state",
            )
            self.assertEqual(self.install_only(file_config, file_entry).exit_code, 0)
            file_destination = installer.destination_for(file_entry, file_config)
            file_destination.unlink()
            file_destination.mkdir()

            wrong_type = self.uninstall_only(file_config, file_entry)

            self.assertEqual(wrong_type.exit_code, 1)
            self.assertIn(f"conflict: {file_destination}", wrong_type.messages)
            self.assertTrue(file_destination.is_dir())

            tree_entry = self.only_entry(root)
            tree_config = installer.Config(
                root,
                root / "tree-home",
                root / "tree-codex",
                "copy",
                False,
                "claude",
                root / "tree-state",
            )
            self.assertEqual(self.install_only(tree_config, tree_entry).exit_code, 0)
            tree_destination = installer.destination_for(tree_entry, tree_config)
            installer.remove_path(tree_destination)
            installer.copy_item(tree_entry.source, tree_destination)

            replaced_tree = self.uninstall_only(tree_config, tree_entry)

            self.assertEqual(replaced_tree.exit_code, 1)
            self.assertIn(f"conflict: {tree_destination}", replaced_tree.messages)
            self.assertTrue(tree_destination.exists())

    def test_publish_does_not_replace_destination_created_after_absence_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = next(
                entry
                for entry in installer.discover_entries(root)
                if entry.agent == "claude" and entry.kind == "agent"
            )
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            destination = installer.destination_for(entry, config)
            original_present = installer.path_present
            raced = False

            def create_foreign_after_check(path: Path) -> bool:
                nonlocal raced
                present = original_present(path)
                if path == destination and not present and destination.parent.exists() and not raced:
                    stage_containers = list(
                        destination.parent.glob(f".{destination.name}.stage-*")
                    )
                    if stage_containers:
                        raced = True
                        destination.write_text("foreign")
                        return False
                return present

            with mock.patch.object(
                installer, "path_present", side_effect=create_foreign_after_check
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot install"):
                    self.install_only(config, entry)

            self.assertTrue(raced)
            self.assertEqual(destination.read_text(), "foreign")

    def test_uninstall_rename_cannot_be_redirected_by_collection_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = self.only_entry(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            self.assertEqual(self.install_only(config, entry).exit_code, 0)
            destination = installer.destination_for(entry, config)
            collection = destination.parent
            original_collection = collection.with_name("skills-original")
            attacker_collection = root / "attacker-skills"
            attacker_collection.mkdir()
            installer.copy_item(entry.source, attacker_collection / entry.name)
            original_rename = installer._rename_noreplace
            raced = False

            def replace_collection_before_rename(
                source: Path, target: Path, **kwargs: object
            ) -> None:
                nonlocal raced
                if source == destination and not raced:
                    raced = True
                    (attacker_collection / target.parent.name).mkdir()
                    os.rename(collection, original_collection)
                    os.rename(attacker_collection, collection)
                    original_rename(source, target, **kwargs)
                    original_rename(
                        original_collection / entry.name,
                        target.parent / entry.name,
                    )
                else:
                    original_rename(source, target, **kwargs)

            with mock.patch.object(
                installer, "_rename_noreplace", side_effect=replace_collection_before_rename
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot remove"):
                    self.uninstall_only(config, entry)

            self.assertTrue(raced)
            self.assertTrue(destination.exists())
            self.assertEqual(
                (destination / "SKILL.md").read_bytes(), entry.source.joinpath("SKILL.md").read_bytes()
            )

    def test_create_abort_cleanup_preserves_unexpected_partial_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination, tx = self.create_armed_create_transaction(config, entry)
            stage_container = Path(tx["stage_container"])
            stage_payload = Path(tx["stage_payload"])
            original_remove = installer.remove_path
            failed = False

            def partially_remove(path: Path) -> None:
                nonlocal failed
                if path == stage_container and not failed:
                    failed = True
                    first = next(stage_payload.rglob("*"))
                    original_remove(first)
                    raise OSError("cleanup interrupted")
                original_remove(path)

            with mock.patch.object(installer, "remove_path", side_effect=partially_remove):
                first = self.install_only(config, entry)

            self.assertIn(f"recovered: {destination}", first.messages)
            self.assertIn(f"installed: {destination} (copy)", first.messages)
            self.assertFalse(stage_container.exists())
            final = installer.load_state(config.state_path)
            self.assertIn(str(destination), final["entries"])
            self.assertEqual(final["transactions"], {})

    def test_recovery_reloads_durable_state_after_ambiguous_final_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude", root / "state"
            )
            entry = self.only_entry(root)
            destination, tx = self.create_armed_create_transaction(config, entry)
            stage_container = Path(tx["stage_container"])
            os.rename(Path(tx["stage_payload"]), destination)
            original_write = installer.write_state
            failed = False

            def write_then_raise(
                path: Path, state: dict[str, object], dry_run: bool
            ) -> None:
                nonlocal failed
                original_write(path, state, dry_run)
                if not failed:
                    failed = True
                    raise OSError("ambiguous state write")

            with mock.patch.object(installer, "write_state", side_effect=write_then_raise):
                result = self.install_only(config, entry)

            self.assertTrue(failed)
            self.assertEqual(result.exit_code, 0)
            self.assertIn(f"recovered: {destination}", result.messages)
            self.assertFalse(stage_container.exists())
            state = installer.load_state(config.state_path)
            self.assertIn(str(destination), state["entries"])
            self.assertEqual(state["transactions"], {})

    def test_codex_home_alias_is_an_allowed_configured_root(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            real_codex = root / "real-codex"
            real_codex.mkdir()
            alias_codex = root / "alias-codex"
            alias_codex.symlink_to(real_codex, target_is_directory=True)
            config = installer.Config(
                root,
                root / "home",
                alias_codex,
                "copy",
                False,
                "codex",
                root / "state",
            )
            entry = self.only_entry(root, "codex")

            result = self.install_only(config, entry)

            destination = installer.destination_for(entry, config)
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(destination.exists())
            self.assertIn(str(destination), installer.load_state(config.state_path)["entries"])

    def test_stat_identity_fails_closed_without_stable_generation(self) -> None:
        metadata = mock.Mock(st_dev=7, st_ino=11)
        with mock.patch.object(installer.os, "stat", return_value=metadata), mock.patch.object(
            installer, "stat_birth_identity", return_value=None
        ), self.assertRaisesRegex(installer.InstallerError, "stable object identity"):
            installer.stat_identity(Path("unsupported"))

    def test_v1_migration_rejects_copy_type_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = next(
                candidate
                for candidate in installer.discover_entries(root)
                if candidate.agent == "claude" and candidate.kind == "agent"
            )
            entry.source.write_bytes(b"")
            config = installer.Config(
                root,
                root / "home",
                root / "codex",
                "copy",
                False,
                "claude",
                root / "state",
            )
            destination = installer.destination_for(entry, config)
            destination.mkdir(parents=True)
            v1 = {
                "version": 1,
                "entries": {
                    str(destination): {
                        "agent": entry.agent,
                        "kind": entry.kind,
                        "name": entry.name,
                        "source": str(entry.source.resolve()),
                        "mode": "copy",
                        "digest": installer.digest(entry.source),
                        "removable": True,
                    }
                },
            }
            installer.write_state(config.state_path, v1, False)

            with self.assertRaisesRegex(installer.InstallerError, "changed destination"):
                installer.migrate_v1_state(config)

            self.assertTrue(destination.is_dir())
            self.assertEqual(installer.read_state_document(config.state_path), v1)

    @unittest.skipIf(os.name == "nt", "HOME-based state alias test requires POSIX")
    def test_v1_migration_deduplicates_physical_state_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            operator_home = root / "operator-home"
            operator_home.mkdir()
            configured_home = root / "configured-home-alias"
            configured_home.symlink_to(operator_home, target_is_directory=True)
            environment = dict(os.environ)
            environment["HOME"] = str(operator_home)
            environment.pop("XDG_STATE_HOME", None)
            with mock.patch.dict(os.environ, environment, clear=True):
                config = installer.Config(
                    root, configured_home, root / "codex", "copy", False, "claude"
                )
                entry = self.only_entry(root)
                destination = installer.destination_for(entry, config)
                destination.parent.mkdir(parents=True)
                installer.copy_item(entry.source, destination)
                v1 = {
                    "version": 1,
                    "entries": {
                        str(destination): {
                            "agent": entry.agent,
                            "kind": entry.kind,
                            "name": entry.name,
                            "source": str(entry.source.resolve()),
                            "mode": "copy",
                            "digest": installer.digest(destination),
                            "removable": True,
                        }
                    },
                }
                installer.write_state(config.state_path, v1, False)
                self.assertNotEqual(config.state_path, config.legacy_state_path)
                self.assertTrue(os.path.samefile(config.state_path, config.legacy_state_path))

                migrated = installer.migrate_v1_state(config)
                checked = installer.status(config)
                migrated_state = installer.load_state(config.state_path)

            self.assertEqual(migrated.exit_code, 0)
            self.assertEqual(checked.exit_code, 0)
            self.assertIn(str(destination), migrated_state["entries"])

    @unittest.skipIf(os.name == "nt", "POSIX hard links are required")
    def test_v1_migration_retires_hard_link_state_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            operator_home = root / "operator-home"
            configured_home = root / "configured-home"
            environment = dict(os.environ)
            environment["HOME"] = str(operator_home)
            environment.pop("XDG_STATE_HOME", None)
            with mock.patch.dict(os.environ, environment, clear=True):
                config = installer.Config(
                    root, configured_home, root / "codex", "copy", False, "claude"
                )
                entry = self.only_entry(root)
                destination = installer.destination_for(entry, config)
                destination.parent.mkdir(parents=True)
                installer.copy_item(entry.source, destination)
                v1 = {
                    "version": 1,
                    "entries": {
                        str(destination): {
                            "agent": entry.agent,
                            "kind": entry.kind,
                            "name": entry.name,
                            "source": str(entry.source.resolve()),
                            "mode": "copy",
                            "digest": installer.digest(destination),
                            "removable": True,
                        }
                    },
                }
                installer.write_state(config.state_path, v1, False)
                config.legacy_state_path.parent.mkdir(parents=True)
                os.link(config.state_path, config.legacy_state_path)
                self.assertTrue(os.path.samefile(config.state_path, config.legacy_state_path))

                migrated = installer.migrate_v1_state(config)
                checked = installer.status(config)

            self.assertEqual(migrated.exit_code, 0)
            self.assertEqual(checked.exit_code, 0)
            self.assertFalse(configured_home.joinpath(".local/state/agentic-sdlc-installer/state.json").exists())

    @unittest.skipIf(os.name == "nt", "POSIX home symlink is required")
    def test_v1_migration_collapses_duplicate_destination_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            real_home = root / "real-home"
            real_home.mkdir()
            alias_home = root / "alias-home"
            alias_home.symlink_to(real_home, target_is_directory=True)
            config = installer.Config(
                root,
                alias_home,
                root / "codex",
                "copy",
                False,
                "claude",
                root / "state",
            )
            entry = self.only_entry(root)
            alias_destination = installer.destination_for(entry, config)
            alias_destination.parent.mkdir(parents=True)
            installer.copy_item(entry.source, alias_destination)
            real_destination = real_home / ".claude" / "skills" / entry.name
            record = {
                "agent": entry.agent,
                "kind": entry.kind,
                "name": entry.name,
                "source": str(entry.source.resolve()),
                "mode": "copy",
                "digest": installer.digest(alias_destination),
                "removable": True,
            }
            v1 = {
                "version": 1,
                "entries": {
                    str(real_destination): copy.deepcopy(record),
                    str(alias_destination): copy.deepcopy(record),
                },
            }
            installer.write_state(config.state_path, v1, False)

            migrated = installer.migrate_v1_state(config)
            state = installer.load_state(config.state_path)

            self.assertEqual(migrated.exit_code, 0)
            self.assertIn(str(alias_destination), state["entries"])
            self.assertNotIn(str(real_destination), state["entries"])
            self.assertEqual(installer.uninstall(config).exit_code, 0)
            self.assertEqual(installer.load_state(config.state_path), installer.empty_state())

    def test_v1_migration_accepts_record_outside_current_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root,
                root / "home",
                root / "codex",
                "copy",
                False,
                "claude",
                root / "state",
            )
            entry = self.only_entry(root, "codex")
            destination = installer.destination_for(entry, config)
            destination.parent.mkdir(parents=True)
            installer.copy_item(entry.source, destination)
            v1 = {
                "version": 1,
                "entries": {
                    str(destination): {
                        "agent": entry.agent,
                        "kind": entry.kind,
                        "name": entry.name,
                        "source": str(entry.source.resolve()),
                        "mode": "copy",
                        "digest": installer.digest(destination),
                        "removable": True,
                    }
                },
            }
            installer.write_state(config.state_path, v1, False)

            migrated = installer.migrate_v1_state(config)

            self.assertEqual(migrated.exit_code, 0)
            state = installer.load_state(config.state_path)
            self.assertIn(str(destination), state["entries"])
            self.assertEqual(state["entries"][str(destination)]["agent"], "codex")

    def test_read_only_copy_installs_without_changing_mode(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX permission bits are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            source = root / "skills" / "example" / "SKILL.md"
            source.chmod(0o444)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)

            result = self.install_only(config, entry)

            destination = installer.destination_for(entry, config) / "SKILL.md"
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o444)
            self.assertEqual(list(destination.parent.parent.glob(".example.stage-*")), [])

    def test_nested_symlink_is_not_equivalent_to_regular_file(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            copied = root / "copied"
            installer.copy_item(root / "skills" / "example", copied)
            regular = copied / "SKILL.md"
            external = root / "external.md"
            external.write_bytes(regular.read_bytes())
            regular.unlink()
            regular.symlink_to(external)

            self.assertFalse(
                installer.content_equivalent(copied, root / "skills" / "example")
            )
            self.assertNotEqual(
                installer.digest(copied), installer.digest(root / "skills" / "example")
            )

    def test_create_cleanup_precedes_final_state_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(
                root, root / "home", root / "codex", "copy", False, "claude"
            )
            entry = self.only_entry(root)
            original_write = installer.write_state
            calls = 0

            def fail_final(path: Path, state: dict[str, object], dry_run: bool) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("final state failed")
                original_write(path, state, dry_run)

            with mock.patch.object(installer, "write_state", side_effect=fail_final), mock.patch.object(
                installer, "recover_durable_after_failure"
            ):
                with self.assertRaisesRegex(installer.InstallerError, "cannot install"):
                    self.install_only(config, entry)

            destination = installer.destination_for(entry, config)
            tx = installer.load_state(config.state_path)["transactions"][str(destination)]
            self.assertFalse(Path(tx["stage_container"]).exists())
            self.assertEqual(self.install_only(config, entry).exit_code, 0)

    def test_cleanup_preserves_foreign_private_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "example"
            artifact = installer.reserve_private_artifact(destination, "stage")
            foreign = artifact.container / "foreign.txt"
            foreign.write_text("keep")

            with self.assertRaisesRegex(installer.RecoveryConflict, "foreign content"):
                installer.cleanup_private_artifact(artifact)

            self.assertEqual(foreign.read_text(), "keep")

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
                "no owned entries for this host (run: mise run bundle:install)",
            )

    def test_unmanaged_codex_skill_is_found_by_install_dry_run_not_owned_status(self) -> None:
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

            self.assertEqual(checked.exit_code, 0)
            self.assertEqual(
                checked.messages[-1],
                "no owned entries for this host (run: mise run bundle:install)",
            )
            self.assertEqual(previewed.exit_code, 1)
            self.assertIn(f"conflict: {destination}", previewed.messages)
            self.assertIn(
                f"preserved: {destination} (a non-bundle entry already exists; inspect and resolve it before retrying)",
                previewed.messages,
            )
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

    def test_status_summary_is_terminal_for_every_counted_shape(self) -> None:
        self.assertEqual(
            installer.status_summary({"ok": 0, "conflict": 0, "absent": 0}),
            "no owned entries for this host (run: mise run bundle:install)",
        )
        self.assertEqual(
            installer.status_summary({"ok": 3, "conflict": 2, "absent": 1}),
            "3 ok, 2 conflict, 1 absent",
        )

    def make_identity_repo(self, root: Path) -> None:
        (root / "skills" / "agentic-sdlc-orchestrator").mkdir(parents=True)
        (root / "skills" / "agentic-sdlc-orchestrator" / "SKILL.md").write_text(
            "---\nname: agentic-sdlc-orchestrator\n---\n"
        )
        (root / "agents" / "claude").mkdir(parents=True)
        (root / "agents" / "codex").mkdir(parents=True)
        (root / "commands").mkdir()

    def install_old_slug(
        self, root: Path, mode: str = "copy"
    ) -> tuple[installer.Config, str, str, installer.Entry]:
        """Install the old-slug skill, then rename its repo source to the new slug."""
        home = root / "home"
        codex_home = root / "codex"
        self.make_identity_repo(root)
        config = installer.Config(root, home, codex_home, mode, False, "claude")
        result = installer.install(config)
        self.assertEqual(result.exit_code, 0)
        old_key = str(home / ".claude" / "skills" / "agentic-sdlc-orchestrator")
        new_key = str(home / ".claude" / "skills" / "agentic-sdlc")
        (root / "skills" / "agentic-sdlc-orchestrator").rename(root / "skills" / "agentic-sdlc")
        entry_new = installer.Entry(
            "claude", "skill", "agentic-sdlc", root / "skills" / "agentic-sdlc"
        )
        return config, old_key, new_key, entry_new

    def arm_rename_transaction(
        self,
        config: installer.Config,
        old_key: str,
        new_key: str,
        entry_new: installer.Entry,
    ) -> tuple[installer.StagedCandidate, installer.PrivateArtifact, dict[str, object]]:
        """Stage and journal an armed rename transaction, simulating a pre-publish crash."""
        state = installer.load_state(config.state_path)
        old_record = state["entries"][old_key]
        staged = installer.stage_candidate(
            entry_new,
            Path(new_key),
            config,
            old_record["root_identity"],
            old_record["collection_identity"],
        )
        backup = installer.reserve_private_artifact(Path(old_key), "backup")
        tx = installer.rename_transaction_record(
            old_key,
            new_key,
            old_record=old_record,
            new_record=staged.record,
            stage=staged.artifact,
            backup=backup,
            new_source_digest=installer.digest(entry_new.source),
        )
        candidate = installer.state_with_transaction(state, new_key, tx)
        candidate["entries"].pop(old_key, None)
        installer.write_state(config.state_path, candidate, False)
        return staged, backup, tx

    def assert_rename_converged(
        self, config: installer.Config, old_key: str, new_key: str
    ) -> None:
        state = installer.load_state(config.state_path)
        self.assertEqual(state["transactions"], {})
        self.assertNotIn(old_key, state["entries"])
        self.assertIn(new_key, state["entries"])
        self.assertFalse(installer.path_present(Path(old_key)))
        self.assertTrue(
            installer.entry_matches_record(Path(new_key), state["entries"][new_key])
        )

    def test_plan_identity_renames_targets_only_old_slug_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, new_key, _ = self.install_old_slug(root)
            state = installer.load_state(config.state_path)
            state["entries"]["/other/agents/role.md"] = {"kind": "agent"}

            planned = installer.plan_identity_renames(state, config)

            self.assertEqual(
                planned, [(old_key, new_key, state["entries"][old_key])]
            )

    def test_plan_identity_renames_is_pure_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, _, _, _ = self.install_old_slug(root)
            state = installer.load_state(config.state_path)
            before = config.state_path.read_bytes()

            installer.plan_identity_renames(state, config)

            self.assertEqual(config.state_path.read_bytes(), before)

    def test_transactional_rename_moves_owned_copy_to_new_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, new_key, entry_new = self.install_old_slug(root)
            state = installer.load_state(config.state_path)
            old_record = state["entries"][old_key]

            mode = installer.transactional_rename(
                entry_new,
                old_key,
                new_key,
                config,
                state,
                old_record,
                new_source_digest=installer.digest(entry_new.source),
            )

            self.assertEqual(mode, "copy")
            self.assert_rename_converged(config, old_key, new_key)

    def test_transactional_rename_refuses_foreign_new_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, new_key, entry_new = self.install_old_slug(root)
            foreign = Path(new_key)
            foreign.mkdir()
            (foreign / "keep.txt").write_text("keep")
            state = installer.load_state(config.state_path)
            old_record = state["entries"][old_key]

            with self.assertRaisesRegex(installer.InstallerError, "occupied"):
                installer.transactional_rename(
                    entry_new,
                    old_key,
                    new_key,
                    config,
                    state,
                    old_record,
                    new_source_digest=installer.digest(entry_new.source),
                )

            self.assertEqual((foreign / "keep.txt").read_text(), "keep")
            durable = installer.load_state(config.state_path)
            self.assertEqual(durable["transactions"], {})
            self.assertIn(old_key, durable["entries"])
            self.assertTrue(
                installer.entry_matches_record(Path(old_key), durable["entries"][old_key])
            )

    def test_rename_recovery_from_armed_crash_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, new_key, entry_new = self.install_old_slug(root)
            self.arm_rename_transaction(config, old_key, new_key, entry_new)

            for _ in range(2):
                state = installer.load_state(config.state_path)
                installer.validate_state(config, state)
                messages, partial = installer.recover_transactions(
                    config, state, read_only=False
                )
                self.assertFalse(partial, messages)
                self.assert_rename_converged(config, old_key, new_key)

    def test_rename_recovery_from_published_crash_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, new_key, entry_new = self.install_old_slug(root)
            staged, _, _ = self.arm_rename_transaction(config, old_key, new_key, entry_new)
            os.rename(staged.artifact.payload, new_key)

            for _ in range(2):
                state = installer.load_state(config.state_path)
                installer.validate_state(config, state)
                messages, partial = installer.recover_transactions(
                    config, state, read_only=False
                )
                self.assertFalse(partial, messages)
                self.assert_rename_converged(config, old_key, new_key)

    def test_rename_old_link_witness_never_dereferences_dangling_target(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX symlink fixture")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, _, _ = self.install_old_slug(root, mode="link")
            state = installer.load_state(config.state_path)
            old_record = state["entries"][old_key]
            self.assertTrue(Path(old_key).is_symlink())

            # The cumulative source rename makes the recorded target dangle.
            self.assertTrue(
                installer.entry_matches_record(Path(old_key), old_record)
            )

    def test_migrate_state_performs_identity_rename_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, new_key, _ = self.install_old_slug(root)

            result = installer.migrate_v1_state(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(
                any("renamed:" in message for message in result.messages), result.messages
            )
            self.assert_rename_converged(config, old_key, new_key)

    def test_migrate_state_dry_run_reports_rename_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, _, _ = self.install_old_slug(root)
            before = config.state_path.read_bytes()
            dry = installer.Config(
                root, root / "home", root / "codex", "copy", True, "claude"
            )

            result = installer.migrate_v1_state(dry)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(
                any("would rename:" in message for message in result.messages),
                result.messages,
            )
            self.assertEqual(config.state_path.read_bytes(), before)
            self.assertTrue(installer.path_present(Path(old_key)))

    def test_migrate_state_reports_marketplace_overlap_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, new_key, _ = self.install_old_slug(root)
            plugin_cache = config.home / ".claude" / "plugins" / "cache" / "agentic-sdlc"
            plugin_cache.mkdir(parents=True)

            result = installer.migrate_v1_state(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(
                any("marketplace plugin detected" in message for message in result.messages),
                result.messages,
            )
            self.assert_rename_converged(config, old_key, new_key)

    def test_rename_transaction_record_is_journal_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, old_key, new_key, entry_new = self.install_old_slug(root)
            self.arm_rename_transaction(config, old_key, new_key, entry_new)

            state = installer.load_state(config.state_path)
            installer.validate_state(config, state)

            mutated = copy.deepcopy(state)
            mutated["transactions"][new_key]["old_key"] = new_key
            with self.assertRaisesRegex(installer.InstallerError, "invalid transaction"):
                installer.validate_transactions(config, mutated)

    # --- birth-witness settlement -------------------------------------------------------
    #
    # `stat-v2` names an object by device, inode, and birth timestamp. Inodes are reused, so on a
    # filesystem whose birth timestamps are quantized every object created inside one quantum
    # carries the same witness, and a delete-and-recreate at the same name can reproduce a
    # recorded witness exactly. The measured case is not hypothetical: CI run 32554149554
    # (ubuntu, kernel 6.6.141, ext4) saw ONE distinct btime across 40 back-to-back creates and
    # repeated an identical (inode, btime) pair in 20 of 20 delete-recreate trials. A per-entry
    # content digest cannot substitute, because a byte-identical re-copy satisfies it.
    #
    # The coarse arms below force their birth-clock granularity through the
    # `stat_birth_identity` seam; the 1ns arm of the coarse-and-native tests is a deliberate
    # native passthrough that trusts this host's real clock. A simulated clock can only be
    # made COARSER than the real one -- a test cannot invent discrimination the host does not
    # have -- which is exactly the direction that matters, because coarseness is the defect.

    @contextlib.contextmanager
    def simulated_birth_clock(self, quantum_seconds: float | None):
        """Force the installer's birth-timestamp source to a chosen granularity.

        A float truncates every witness the installer reads to that quantum, modelling a
        filesystem that stamps everything created inside one window identically. `None` models
        the pathological host whose birth clock never advances at all. Truncation preserves the
        Linux `<tv_sec>.<tv_nsec>` spelling that `birth_witness_order` parses.
        """
        real = installer.stat_birth_identity
        quantum_ns = None if quantum_seconds is None else max(1, int(quantum_seconds * 10**9))
        # Anchor the grid on the FIRST REAL BIRTH VALUE this clock observes, never on a wall-clock
        # reading. That is what makes these tests deterministic in BOTH directions: any operation
        # sequence shorter than the quantum provably lands inside ONE bucket, so an unsettled
        # witness is always reproducible and a settled one is always strictly older than the
        # replacement.
        #
        # A `time.time_ns()` origin is NOT equivalent, and the difference is measured rather than
        # theoretical. A filesystem stamps btime on a clock tick, so an object created microseconds
        # AFTER the sample can report a btime BEFORE it; Python's `//` floors that value into the
        # bucket one quantum EARLIER and reports the object a whole quantum older than a sibling
        # the filesystem stamped identically. On a fine-btime host the effect is rare rather than
        # absent -- measured at roughly 1 failure in 55 native runs of this module -- and on the
        # coarse-btime host these tests model it is intermittent, and CI run 32565128438 failed the
        # sibling module's own POSITIVE CONTROL that way, with two witnesses exactly one 3600s
        # quantum apart and an identical fractional part on both sides.
        #
        # An observed birth value cannot split one of the filesystem's own quanta, and a value
        # below the anchor is clamped UP into the first bucket rather than floored below it,
        # because looking OLDER is what grants settlement and this helper exists to withhold it.
        anchor: int | None = None

        def simulated(path: Path, *, follow_symlinks: bool = True) -> str | None:
            nonlocal anchor
            value = real(path, follow_symlinks=follow_symlinks)
            if value is None:
                return None
            if quantum_ns is None:
                return "1700000000.0"
            seconds, _, nanoseconds = value.partition(".")
            total = int(seconds) * 10**9 + int(nanoseconds or 0)
            if anchor is None:
                anchor = total
            total = anchor + max(0, (total - anchor) // quantum_ns) * quantum_ns
            return f"{total // 10**9}.{total % 10**9}"

        with mock.patch.object(installer, "stat_birth_identity", simulated):
            yield

    @staticmethod
    def reused_inode_witness(replacement_token: str, recorded_token: str) -> str:
        """The witness a record would carry if a replacement landed on the recorded inode.

        This is what the CI probe measured 20/20 times, so it is modelled rather than raced:
        the replacement's device and inode with the RECORDED birth timestamp.
        """
        version, device, inode, _ = replacement_token.split(":", 3)
        return f"{version}:{device}:{inode}:{installer.identity_generation(recorded_token)}"

    def tree_config(self, root: Path) -> installer.Config:
        return installer.Config(
            root, root / "home", root / "codex", "copy", False, "claude", root / "state"
        )

    def install_replaceable_tree(
        self, root: Path, *, extra_files: int = 0
    ) -> tuple[installer.Config, installer.Entry, Path]:
        """Install one skill tree in copy mode and hand back its destination."""
        self.make_repo(root)
        for index in range(extra_files):
            (root / "skills" / "example" / f"note-{index}.md").write_text(f"note {index}\n")
        entry = self.only_entry(root)
        config = self.tree_config(root)
        self.assertEqual(self.install_only(config, entry).exit_code, 0)
        return config, entry, installer.destination_for(entry, config)

    def replace_tree_byte_identically(self, entry: installer.Entry, destination: Path) -> None:
        installer.remove_path(destination)
        installer.copy_item(entry.source, destination)

    def test_replaced_tree_is_refused_under_a_coarse_birth_clock(self) -> None:
        with self.simulated_birth_clock(0.5):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config, entry, destination = self.install_replaceable_tree(root)
                record = installer.load_state(config.state_path)["entries"][str(destination)]
                self.replace_tree_byte_identically(entry, destination)
                # The replacement is byte-identical, so the recorded digest still matches and
                # only the physical witness can refuse it.
                self.assertEqual(installer.digest(destination), record["digest"])

                replaced = self.uninstall_only(config, entry)

                self.assertEqual(replaced.exit_code, 1)
                self.assertIn(f"conflict: {destination}", replaced.messages)
                self.assertTrue(destination.is_dir())

    def test_replaced_file_is_refused_under_a_coarse_birth_clock(self) -> None:
        with self.simulated_birth_clock(0.5):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                entry = next(
                    candidate
                    for candidate in installer.discover_entries(root)
                    if candidate.agent == "claude" and candidate.kind == "agent"
                )
                config = self.tree_config(root)
                self.assertEqual(self.install_only(config, entry).exit_code, 0)
                destination = installer.destination_for(entry, config)
                record = installer.load_state(config.state_path)["entries"][str(destination)]
                content = destination.read_bytes()
                destination.unlink()
                destination.write_bytes(content)
                self.assertEqual(installer.digest(destination), record["digest"])

                replaced = self.uninstall_only(config, entry)

                self.assertEqual(replaced.exit_code, 1)
                self.assertIn(f"conflict: {destination}", replaced.messages)
                self.assertTrue(destination.is_file())

    def test_recorded_witness_is_strictly_older_than_any_later_replacement(self) -> None:
        """The granularity-independent contract the CI test's exit 1 rests on."""
        for quantum in (0.000000001, 0.5, 1.0):
            with self.subTest(quantum=quantum):
                with self.simulated_birth_clock(quantum):
                    with tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        config, entry, destination = self.install_replaceable_tree(root)
                        recorded = installer.load_state(config.state_path)["entries"][
                            str(destination)
                        ]["destination_identity"]
                        self.replace_tree_byte_identically(entry, destination)

                        current = installer.stat_identity(destination)

                        self.assertLess(
                            installer.birth_witness_order(
                                installer.identity_generation(recorded)
                            ),
                            installer.birth_witness_order(
                                installer.identity_generation(current)
                            ),
                        )
                        self.assertNotEqual(
                            self.reused_inode_witness(current, recorded), current
                        )

    def test_owner_can_uninstall_under_coarse_and_native_birth_clocks(self) -> None:
        for quantum in (0.000000001, 0.5):
            with self.subTest(quantum=quantum):
                with self.simulated_birth_clock(quantum):
                    with tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        config, entry, destination = self.install_replaceable_tree(root)

                        removed = self.uninstall_only(config, entry)

                        self.assertEqual(removed.exit_code, 0)
                        self.assertFalse(installer.path_present(destination))
                        self.assertEqual(
                            installer.load_state(config.state_path)["entries"], {}
                        )

    def test_install_records_unsettled_and_never_trusts_it_when_the_clock_cannot_discriminate(
        self,
    ) -> None:
        """The degenerate host records by name and then discriminates on nothing.

        Recording no longer blocks per transaction, so a witness whose quantum never closes is
        persisted CARRYING that fact instead of aborting the install. The command still refuses by
        name and exits non-zero, and the record it left is non-discriminating: status calls it a
        conflict and uninstall preserves it. Never-remove is the property under test.
        """
        with self.simulated_birth_clock(None):
            with mock.patch.object(installer, "BIRTH_SETTLE_TIMEOUT_SECONDS", 0.05):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    self.make_repo(root)
                    entry = self.only_entry(root)
                    config = self.tree_config(root)
                    destination = installer.destination_for(entry, config)

                    installed = self.install_only(config, entry)

                    self.assertEqual(installed.exit_code, 1)
                    self.assertTrue(
                        any(
                            "birth timestamps cannot distinguish" in message
                            and "unsettled ownership records preserved" in message
                            for message in installed.messages
                        ),
                        installed.messages,
                    )
                    state = installer.load_state(config.state_path)
                    self.assertEqual(state["transactions"], {})
                    self.assertIs(
                        state["entries"][str(destination)]["witness_settled"], False
                    )
                    self.assertEqual(
                        list(destination.parent.glob(f".{destination.name}.*")), []
                    )

                    # A LATER command -- a fresh ledger, exactly as a new process has -- must not
                    # discriminate on that witness, so it preserves rather than removes. The
                    # AUTHORITY gate answers first, because a fresh install mints the collection
                    # and root witnesses too and an unsettled record's are no better than its
                    # destination's; that is the stronger of the two refusals.
                    checked = installer.status(config)
                    self.assertEqual(checked.exit_code, 1)
                    self.assertIn(
                        f"root/collection conflict: {destination}", checked.messages
                    )
                    self.assertIn("0 ok, 1 conflict, 0 absent", checked.messages)

                    removed = self.uninstall_only(config, entry)
                    self.assertEqual(removed.exit_code, 1)
                    self.assertTrue(
                        any(
                            message.startswith(f"preserved: {destination} ")
                            for message in removed.messages
                        ),
                        removed.messages,
                    )
                    self.assertNotIn(f"removed: {destination}", removed.messages)
                    self.assertTrue(installer.path_present(destination))

    def test_adoption_never_owns_an_unsettleable_destination(self) -> None:
        """A degenerate host never grants discriminating ownership, so it can never remove."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = self.only_entry(root)
            config = installer.Config(
                root, root / "home", root / "codex", "link", False, "claude", root / "state"
            )
            destination = installer.destination_for(entry, config)
            installer.ensure_collection(entry, destination, config)
            destination.symlink_to(entry.source)

            with self.simulated_birth_clock(None):
                with mock.patch.object(installer, "BIRTH_SETTLE_TIMEOUT_SECONDS", 0.05):
                    adopted = self.install_only(config, entry)
                    self.assertEqual(adopted.exit_code, 1)
                    self.assertTrue(
                        any(
                            "birth timestamps cannot distinguish" in message
                            for message in adopted.messages
                        ),
                        adopted.messages,
                    )
                    removed = self.uninstall_only(config, entry)

                    self.assertEqual(removed.exit_code, 1)
                    self.assertNotIn(f"removed: {destination}", removed.messages)
                    record = installer.load_state(config.state_path)["entries"][
                        str(destination)
                    ]
                    self.assertIs(record["witness_settled"], False)
                    self.assertFalse(installer.entry_matches_record(destination, record))
                    # Positive control for the marker itself, taken INSIDE the simulated clock so
                    # the recorded witness is still the one this host reports: the SAME record
                    # without the marker discriminates, which proves the refusal above comes from
                    # the marker and not from the link's own identity.
                    self.assertTrue(
                        installer.entry_matches_record(
                            destination,
                            {
                                key: value
                                for key, value in record.items()
                                if key != "witness_settled"
                            },
                        )
                    )

            self.assertTrue(destination.is_symlink())
            self.assertEqual(os.readlink(destination), str(entry.source))

    def hard_killed_armed_journal(
        self, config: installer.Config, entry: installer.Entry
    ) -> Path:
        """A durable armed journal marked unsettled, as a HARD-KILLED command would leave it.

        `one_settle_per_command` pays the deferred wait even when the command raises, so an
        in-process failure leaves nothing unproven. SIGKILL, a power cut and an OOM kill reach no
        handler at all, so the marker survives with no ledger anywhere that could clear it -- and
        the marker is written in the same atomic replace as the witness it qualifies, which is
        exactly the shape reconstructed here.
        """
        destination, _ = self.create_armed_create_transaction(config, entry)
        key = str(destination)
        document = json.loads(config.state_path.read_text(encoding="utf-8"))
        document["transactions"][key]["witness_settled"] = False
        document["transactions"][key]["new_record"]["witness_settled"] = False
        config.state_path.write_text(json.dumps(document), encoding="utf-8")
        # Precondition, so this can never silently stop exercising the marker it exists for.
        self.assertIs(
            installer.load_state(config.state_path)["transactions"][key]["witness_settled"],
            False,
        )
        return destination

    def test_hard_killed_journal_recovers_and_is_idempotent_under_a_coarse_clock(
        self,
    ) -> None:
        """Convergence: an interrupted transaction no later run can prove was never recoverable.

        Settlement is RE-PROVABLE -- a probe now proves the recorded quantum closed before now --
        so `resolve_inherited_settlement` pays one bounded wait and the journal becomes exactly as
        trustworthy as one written on a fine-grained host. Without it the shipped behaviour was a
        permanent `interrupted conflict` on every run forever, which is the positive control below.
        """
        with self.simulated_birth_clock(0.5):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                entry = self.only_entry(root)
                config = self.tree_config(root)
                destination = self.hard_killed_armed_journal(config, entry)
                key = str(destination)
                stage = Path(
                    installer.load_state(config.state_path)["transactions"][key][
                        "stage_container"
                    ]
                )

                # Positive control FIRST, because recovery consumes the journal: with the inherited
                # marker left unresolved the same journal is the shipped permanent conflict.
                with mock.patch.object(
                    installer,
                    "resolve_inherited_settlement",
                    lambda config, state: ([], False),
                ):
                    stuck = self.install_only(config, entry)
                self.assertEqual(stuck.exit_code, 1)
                self.assertIn(f"interrupted conflict: {key}", stuck.messages)
                self.assertTrue(stage.is_dir())
                self.assertIs(
                    installer.load_state(config.state_path)["transactions"][key][
                        "witness_settled"
                    ],
                    False,
                )

                recovered = self.install_only(config, entry)

                self.assertEqual(recovered.exit_code, 0)
                self.assertIn(f"settled interrupted lifecycle state: {key}", recovered.messages)
                self.assertIn(f"recovered: {key}", recovered.messages)
                self.assertFalse(stage.exists())
                state = installer.load_state(config.state_path)
                self.assertEqual(state["transactions"], {})
                # The resolved record must carry no marker, or the transaction would have converged
                # into an entry no later ownership decision could ever trust.
                self.assertNotIn("witness_settled", state["entries"][key])
                self.assertTrue(
                    installer.entry_matches_record(destination, state["entries"][key])
                )

                # Idempotent: a re-run is a clean owned refresh with no journal left behind and no
                # marker reintroduced. A copy-mode entry is re-copied by design, so the record's
                # physical witness legitimately changes; what must not change is its trustedness.
                again = self.install_only(config, entry)
                self.assertEqual(again.exit_code, 0)
                self.assertIn(f"refreshed: {key}", again.messages)
                repeated = installer.load_state(config.state_path)
                self.assertEqual(repeated["transactions"], {})
                self.assertNotIn("witness_settled", repeated["entries"][key])
                self.assertEqual(
                    repeated["entries"][key]["digest"], state["entries"][key]["digest"]
                )
                # And the converged entry is genuinely owned: uninstall removes it.
                self.assertEqual(self.uninstall_only(config, entry).exit_code, 0)
                self.assertFalse(installer.path_present(destination))

    def test_hard_killed_journal_is_preserved_when_settlement_stays_unprovable(self) -> None:
        """The degenerate host converges on nothing, which is still the fail-closed answer.

        Re-proving is the whole mechanism, so a clock that never advances must leave the marker
        durable and the journal refused -- byte for byte the answer seed 249d shipped.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            entry = self.only_entry(root)
            config = self.tree_config(root)
            # The journal is armed on THIS host's clock, because staging outside a command scope
            # settles inline and a clock that never advances could not produce one at all.
            destination = self.hard_killed_armed_journal(config, entry)
            key = str(destination)
            stage = Path(
                installer.load_state(config.state_path)["transactions"][key][
                    "stage_container"
                ]
            )

            with self.simulated_birth_clock(None):
                with mock.patch.object(installer, "BIRTH_SETTLE_TIMEOUT_SECONDS", 0.05):
                    refused = self.install_only(config, entry)

                    self.assertEqual(refused.exit_code, 1)
                    self.assertTrue(
                        any(
                            message.startswith(
                                f"unsettled ownership records preserved for {key}: "
                            )
                            for message in refused.messages
                        ),
                        refused.messages,
                    )
                    self.assertIn(f"interrupted conflict: {key}", refused.messages)
                    self.assertTrue(stage.is_dir())
                    self.assertIs(
                        installer.load_state(config.state_path)["transactions"][key][
                            "witness_settled"
                        ],
                        False,
                    )

    def test_inherited_resolution_never_clears_an_owned_entry_marker(self) -> None:
        """The scope line: recovery may converge, an ownership DELETION may not.

        A journal marker is a question about finishing this lifecycle's own transaction. An owned
        record's marker is the ownership-deletion question seed 249d exists for, so a write command
        must leave it exactly where it is -- and uninstall must still preserve rather than remove.
        """
        with self.simulated_birth_clock(0.5):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config, entry, destination = self.install_replaceable_tree(root)
                key = str(destination)
                document = json.loads(config.state_path.read_text(encoding="utf-8"))
                document["entries"][key]["witness_settled"] = False
                config.state_path.write_text(json.dumps(document), encoding="utf-8")

                targets, keys = installer.inherited_settlement_targets(
                    config, installer.load_state(config.state_path)
                )
                self.assertEqual((targets, keys), ([], set()))

                # Positive control: the SAME marker on the JOURNAL half IS enrolled, so the empty
                # answer above comes from the scope line and not from an inert helper.
                journal = copy.deepcopy(installer.load_state(config.state_path))
                journal["transactions"][key] = {
                    "witness_settled": False,
                    "destination": key,
                    **journal["entries"][key],
                }
                enrolled_targets, enrolled_keys = installer.inherited_settlement_targets(
                    config, journal
                )
                self.assertEqual(enrolled_keys, {key})
                self.assertTrue(enrolled_targets)

                kept = self.uninstall_only(config, entry)

                self.assertEqual(kept.exit_code, 1)
                self.assertNotIn(f"removed: {key}", kept.messages)
                self.assertTrue(destination.is_dir())
                self.assertIs(
                    installer.load_state(config.state_path)["entries"][key][
                        "witness_settled"
                    ],
                    False,
                )
                # Positive control: the same record without the marker is removed, so the refusal
                # above comes from the marker and not from the tree's own identity.
                document["entries"][key].pop("witness_settled")
                config.state_path.write_text(json.dumps(document), encoding="utf-8")
                self.assertEqual(self.uninstall_only(config, entry).exit_code, 0)
                self.assertFalse(installer.path_present(destination))

    def test_a_failed_command_still_pays_the_settlement_it_deferred(self) -> None:
        """A failing command owes its deferred wait and still holds the lock, so it pays it.

        Refusing to pay bought nothing: the entries it created stay on disk either way, and the
        marker it left behind could never be cleared by anything, so a crashed install's owned
        entry was permanently unremovable on a coarse-clock host. The `pay=False` leg is the
        shipped behaviour and the control.
        """
        for pay in (True, False):
            with self.subTest(pay=pay):
                with self.simulated_birth_clock(0.5):
                    with tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        self.make_repo(root)
                        config = self.tree_config(root)
                        original = installer.create_destination
                        calls = 0

                        def fail_second(
                            entry: installer.Entry,
                            destination: Path,
                            current: installer.Config,
                        ) -> str:
                            nonlocal calls
                            calls += 1
                            if calls == 2:
                                raise OSError("disk full")
                            return original(entry, destination, current)

                        with contextlib.ExitStack() as stack:
                            stack.enter_context(
                                mock.patch.object(
                                    installer,
                                    "create_destination",
                                    side_effect=fail_second,
                                )
                            )
                            if not pay:
                                # The shipped behaviour exactly: drop the in-process ledger and
                                # discard the debt. Dropping the ledger matters -- leaking it would
                                # let the NEXT command strip markers it never placed.
                                stack.enter_context(
                                    mock.patch.object(
                                        installer,
                                        "settle_after_failure",
                                        lambda config: installer.SETTLEMENT.reset(),
                                    )
                                )
                            with self.assertRaisesRegex(
                                installer.InstallerError, "cannot install"
                            ):
                                installer.install(config)

                        destination = config.home / ".claude" / "skills" / "example"
                        record = installer.load_state(config.state_path)["entries"][
                            str(destination)
                        ]
                        if pay:
                            self.assertNotIn("witness_settled", record)
                            self.assertEqual(installer.uninstall(config).exit_code, 0)
                            self.assertFalse(installer.path_present(destination))
                        else:
                            self.assertIs(record["witness_settled"], False)
                            self.assertEqual(installer.uninstall(config).exit_code, 1)
                            self.assertTrue(destination.is_dir())

    def test_settle_refuses_within_its_bound_when_timestamps_never_advance(self) -> None:
        self.assertGreater(installer.BIRTH_SETTLE_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(installer.BIRTH_SETTLE_TIMEOUT_SECONDS, 5.0)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "object"
            target.mkdir()
            with self.simulated_birth_clock(None):
                token = installer.stat_identity(target)
                with mock.patch.object(installer, "BIRTH_SETTLE_TIMEOUT_SECONDS", 0.05):
                    started = time.monotonic()
                    with self.assertRaisesRegex(
                        installer.InstallerError,
                        f"cannot distinguish {target} from a replacement",
                    ):
                        installer.settle_identity_witnesses(
                            ((target, token),), probe_dir=root
                        )
                    elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)

    def test_settle_probes_once_per_round_not_once_per_witness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            targets = []
            for index in range(4):
                target = root / f"object-{index}"
                target.mkdir()
                targets.append(target)
            probes = 0
            sleeps = 0
            real_probe = installer.birth_probe_token
            real_sleep = installer.time.sleep

            def counted_probe(directory: Path) -> str:
                nonlocal probes
                probes += 1
                return real_probe(directory)

            def counted_sleep(seconds: float) -> None:
                nonlocal sleeps
                sleeps += 1
                real_sleep(seconds)

            with self.simulated_birth_clock(None):
                witnesses = [(target, installer.stat_identity(target)) for target in targets]
                with mock.patch.object(installer, "birth_probe_token", counted_probe):
                    with mock.patch.object(installer.time, "sleep", counted_sleep):
                        with mock.patch.object(
                            installer, "BIRTH_SETTLE_TIMEOUT_SECONDS", 0.05
                        ):
                            with self.assertRaises(installer.InstallerError):
                                installer.settle_identity_witnesses(
                                    witnesses, probe_dir=root
                                )
            self.assertGreater(probes, 0)
            self.assertEqual(probes, sleeps + 1)

    def test_one_transaction_probes_once_whatever_the_tree_size(self) -> None:
        measurements = []
        for extra_files in (0, 12):
            calls: list[int] = []
            real_defer = installer.defer_identity_witnesses

            def recorded_defer(witnesses, **kwargs):  # type: ignore[no-untyped-def]
                materialized = list(witnesses)
                calls.append(len(materialized))
                return real_defer(materialized, **kwargs)

            with mock.patch.object(
                installer, "defer_identity_witnesses", recorded_defer
            ):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    _, _, destination = self.install_replaceable_tree(
                        root, extra_files=extra_files
                    )
                    installed = sum(1 for _ in destination.rglob("*"))
            measurements.append((installed, tuple(calls)))
        self.assertLess(measurements[0][0], measurements[1][0])
        self.assertEqual(measurements[0][1], measurements[1][1])
        self.assertEqual(len(measurements[0][1]), 1)

    def test_wait_count_is_one_per_command_however_many_entries_it_installs(self) -> None:
        """The wait budget must not grow with the entry count -- the whole point of deferring.

        A coarse clock is what makes every recording site defer, so this is the shape that used to
        cost one full birth quantum per transaction. `wait_for_settlement` is the ONLY function
        that sleeps, so counting its invocations counts the waits.
        """
        observed = []
        for count in (1, 4, 16):
            waits: list[int] = []
            real_wait = installer.wait_for_settlement

            def counted_wait(targets):  # type: ignore[no-untyped-def]
                waits.append(len(targets))
                return real_wait(targets)

            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                for index in range(count - 1):
                    extra = root / "skills" / f"extra-{index:03d}"
                    extra.mkdir(parents=True)
                    (extra / "SKILL.md").write_text(f"---\nname: extra-{index:03d}\n---\n")
                config = self.tree_config(root)
                entries = [
                    candidate
                    for candidate in installer.discover_entries(root)
                    if candidate.agent == "claude" and candidate.kind == "skill"
                ]
                self.assertEqual(len(entries), count)
                with self.simulated_birth_clock(0.25):
                    with mock.patch.object(
                        installer, "wait_for_settlement", counted_wait
                    ):
                        with mock.patch.object(
                            installer, "discover_entries", return_value=entries
                        ):
                            result = installer.install(config)
                self.assertEqual(result.exit_code, 0)
                self.assertEqual(
                    sum(1 for m in result.messages if m.startswith("installed:")), count
                )
                # Nothing may stay marked once the single wait has proven settlement.
                state = installer.load_state(config.state_path)
                self.assertEqual(
                    [
                        key
                        for key, record in state["entries"].items()
                        if record.get("witness_settled") is not None
                    ],
                    [],
                )
            observed.append((count, len(waits)))
        self.assertEqual([waits for _, waits in observed], [1, 1, 1], observed)

    def test_an_interrupted_command_leaves_a_witness_a_later_run_will_not_trust(self) -> None:
        """Crash safety: durable after a state write, never settled, never later trusted.

        The interruption is placed exactly where it matters -- after the durable write that makes
        the witness persistent and BEFORE the command's single settle -- and the later run is
        modelled the way a later run actually differs: a fresh, empty ledger.
        """
        with self.simulated_birth_clock(0.25):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                entry = self.only_entry(root)
                config = self.tree_config(root)
                destination = installer.destination_for(entry, config)

                def interrupt(*args, **kwargs):
                    raise KeyboardInterrupt("interrupted before the settle")

                with mock.patch.object(installer, "wait_for_settlement", interrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        self.install_only(config, entry)

                # The entry IS on disk and IS recorded -- the interruption came after publication.
                self.assertTrue(installer.path_present(destination))
                document = json.loads(config.state_path.read_text(encoding="utf-8"))
                record = document["entries"][str(destination)]
                self.assertIs(record["witness_settled"], False)

            # A later run's ledger is empty, which is what makes the marker bite.
            self.assertEqual(installer.SETTLEMENT.keys, set())
            self.assertFalse(installer.SETTLEMENT.deferred)
            self.assertFalse(installer.record_witness_trusted(record))
            self.assertTrue(
                installer.record_witness_trusted(
                    {k: v for k, v in record.items() if k != "witness_settled"}
                )
            )

    def test_a_probe_that_cannot_be_retired_refuses_by_name(self) -> None:
        """Killing test for the probe-unlink guard: a leftover probe must never be swallowed.

        Without the guard the probe stays behind, and a private container's exactness check reads
        ANY extra child as foreign -- so the failure would resurface later as an unrelated
        "foreign content" complaint about a payload nothing touched.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real_unlink = Path.unlink

            def refuse_probe_unlink(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                if self.name.startswith(".birth-probe-"):
                    raise OSError(errno.EPERM, "operation not permitted")
                return real_unlink(self, *args, **kwargs)

            with mock.patch.object(Path, "unlink", refuse_probe_unlink):
                with self.assertRaisesRegex(
                    installer.InstallerError, "cannot retire creation probe"
                ):
                    installer.birth_probe_token(root)

            # The refusal named the probe, and the probe is exactly what was left behind.
            leftovers = list(root.glob(".birth-probe-*"))
            self.assertEqual(len(leftovers), 1, leftovers)
            for leftover in leftovers:
                real_unlink(leftover)

            # Positive control: with unlink restored the same call succeeds and retires the probe.
            token = installer.birth_probe_token(root)
            self.assertTrue(installer.identity_token_valid(token))
            self.assertEqual(list(root.glob(".birth-probe-*")), [])

    @contextlib.contextmanager
    def settlement_removed(self):
        """Neutralize BOTH settlement seams, which is what "no settlement at all" now means.

        Recording defers through `defer_identity_witnesses`, which never sleeps, and only
        `wait_for_settlement` ever blocks. A mutation that removes just one leaves the other still
        enforcing, so a positive control has to remove both or it proves nothing.
        """
        with mock.patch.object(
            installer, "defer_identity_witnesses", lambda *a, **k: True
        ):
            with mock.patch.object(
                installer, "settle_identity_witnesses", lambda *a, **k: None
            ):
                yield

    def test_same_quantum_witness_cannot_discriminate_a_reused_inode(self) -> None:
        """Positive control: with settlement removed the recorded witness is reproducible."""
        with self.simulated_birth_clock(3600.0):
            with self.settlement_removed():
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    config, entry, destination = self.install_replaceable_tree(root)
                    record = installer.load_state(config.state_path)["entries"][
                        str(destination)
                    ]
                    self.replace_tree_byte_identically(entry, destination)
                    replacement = installer.stat_identity(destination)
                    reused = self.reused_inode_witness(
                        replacement, record["destination_identity"]
                    )

                    self.assertEqual(reused, replacement)
                    self.assertTrue(
                        installer.entry_matches_record(
                            destination, {**record, "destination_identity": reused}
                        )
                    )

        with self.simulated_birth_clock(0.5):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config, entry, destination = self.install_replaceable_tree(root)
                record = installer.load_state(config.state_path)["entries"][str(destination)]
                self.replace_tree_byte_identically(entry, destination)
                replacement = installer.stat_identity(destination)
                reused = self.reused_inode_witness(
                    replacement, record["destination_identity"]
                )

                self.assertNotEqual(reused, replacement)
                self.assertFalse(
                    installer.entry_matches_record(
                        destination, {**record, "destination_identity": reused}
                    )
                )
                self.assertFalse(installer.entry_matches_record(destination, record))

    def test_read_only_surfaces_create_no_creation_probe(self) -> None:
        """A settle proves itself by CREATING an object, so no read-only surface may take one."""
        probes = 0
        real_probe = installer.birth_probe_token

        def counted_probe(directory: Path) -> str:
            nonlocal probes
            probes += 1
            return real_probe(directory)

        with mock.patch.object(installer, "birth_probe_token", counted_probe):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                entry = self.only_entry(root)
                dry = installer.Config(
                    root, root / "home", root / "codex", "copy", True, "claude", root / "state"
                )
                self.assertEqual(self.install_only(dry, entry).exit_code, 0)
                installer.status(dry)
                self.assertEqual(self.uninstall_only(dry, entry).exit_code, 0)
                probes_before_migration = probes

            # `--migrate-state --dry-run` MINTS a witness for an entry a v1 document never
            # witnessed, so it is the one preview that would otherwise take the settle's probe.
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_repo(root)
                config = installer.Config(
                    root, root / "home", root / "codex", "copy", False, "claude", root / "state"
                )
                entry = self.only_entry(root)
                destination = installer.destination_for(entry, config)
                destination.parent.mkdir(parents=True)
                installer.copy_item(entry.source, destination)
                installer.write_state(
                    config.state_path,
                    {
                        "version": 1,
                        "entries": {
                            str(destination): {
                                "agent": entry.agent,
                                "kind": entry.kind,
                                "name": entry.name,
                                "source": str(entry.source.resolve()),
                                "mode": "copy",
                                "digest": installer.digest(destination),
                                "removable": True,
                            }
                        },
                    },
                    False,
                )
                before = config.state_path.read_bytes()
                dry_config = installer.Config(
                    root, config.home, config.codex_home, "copy", True, "claude", config.state_root
                )

                preview = installer.migrate_v1_state(dry_config)

                self.assertIn(f"would migrate: {destination}", preview.messages)
                self.assertEqual(config.state_path.read_bytes(), before)
                probes_after_preview = probes

                migrated = installer.migrate_v1_state(config)

                self.assertEqual(migrated.exit_code, 0)
        self.assertEqual(probes_before_migration, 0)
        self.assertEqual(probes_after_preview, 0)
        self.assertGreater(probes, 0)

    def test_windows_skips_a_file_id_witness_and_settles_the_timestamp_fallback(self) -> None:
        """A reused Windows file id already differs; the ctime fallback does not, so it settles."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "object"
            target.mkdir()
            probes = 0
            real_probe = installer.birth_probe_token

            def counted_probe(directory: Path) -> str:
                nonlocal probes
                probes += 1
                return real_probe(directory)

            with mock.patch.object(installer, "platform_system", lambda: "Windows"):
                with mock.patch.object(installer, "birth_probe_token", counted_probe):
                    with mock.patch.object(
                        installer, "windows_file_identity", lambda *a, **k: (1, 2, 0)
                    ):
                        token = installer.stat_identity(target)
                        installer.settle_identity_witnesses(
                            ((target, token),), probe_dir=root
                        )
                        self.assertEqual(probes, 0)
                    with mock.patch.object(
                        installer, "windows_file_identity", lambda *a, **k: None
                    ):
                        fallback = installer.stat_identity(target)
                        self.assertNotEqual(fallback, token)
                        installer.settle_identity_witnesses(
                            ((target, fallback),), probe_dir=root
                        )
            self.assertGreater(probes, 0)


if __name__ == "__main__":
    unittest.main()
