from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "install_skill_bundle.py"
WRAPPER = SCRIPT.with_name("install-skill-bundle.sh")
BASH = shutil.which("bash")
spec = importlib.util.spec_from_file_location("installer", SCRIPT)
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


class InstallSkillBundleTests(unittest.TestCase):
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
            state = installer.load_state(config.state_path)
            state["entries"][str(destination)] = installer.entry_record(
                installer.Entry("claude", "skill", "example", old / "skills" / "example"), "link"
            )
            installer.write_state(config.state_path, state, False)

            result = installer.install(config)

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.samefile(destination.resolve(), current / "skills" / "example"))
            self.assertTrue(any(message.startswith(f"retargeted: {destination} (") for message in result.messages))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
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
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "claude")
            copy_destination = config.home / ".claude" / "skills" / "example"
            copy_destination.parent.mkdir(parents=True)
            installer.copy_item(root / "skills" / "example", copy_destination)
            agent_destination = config.home / ".claude" / "agents" / "role.md"
            agent_destination.parent.mkdir(parents=True, exist_ok=True)
            agent_destination.symlink_to(root / "agents" / "claude" / "role.md")

            adopted = installer.install(config)
            self.assertIn(f"adopted (preserved on uninstall): {copy_destination}", adopted.messages)
            self.assertIn(f"adopted: {agent_destination}", adopted.messages)

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
            config = installer.Config(root, root / "home", root / "codex", "copy", True, "all")

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

    def test_windows_prefers_junction_for_directories_and_symlink_for_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "link", False, "all")
            with mock.patch.object(installer, "platform_system", return_value="Windows"), mock.patch.object(installer, "make_junction") as junction, mock.patch.object(installer, "make_file_symlink") as file_link:
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

    def test_self_test_runs_isolated_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_repo(root)
            config = installer.Config(root, root / "home", root / "codex", "copy", False, "all")

            result = installer.self_test(config)

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.messages, ("self-test passed",))
            self.assertFalse(config.home.exists())


if __name__ == "__main__":
    unittest.main()
