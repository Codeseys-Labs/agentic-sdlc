"""The agent-hook entry kind: owned lifecycle bytes that installing never runs or enables.

Every lifecycle test here asks the question the workflow kind already answered from a different
payload: does `hook` ride the SAME ownership, staging, refresh, preservation, and removal
machinery, and does the validator hold the authored script to a checkable shape? The one claim
unique to this kind is load-bearing enough to get its own test: installing a hook writes NO
settings document anywhere, because `~/.claude/hooks/` is not an auto-discovery surface and
enabling a hook is the separately authorized `claude:hooks:activate` step.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
INSTALLER_PATH = ROOT / "scripts" / "install_skill_bundle.py"
VALIDATOR_PATH = ROOT / "scripts" / "validate_bundle.py"
SHIPPED_HOOK = ROOT / "hooks" / "session-start-routing-primer.sh"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


installer = _load("hook_kind_installer", INSTALLER_PATH)
validator = _load("hook_kind_validator", VALIDATOR_PATH)

SCRIPT = (
    "#!/bin/sh\n"
    "# hook: primer\n"
    "# hook-event: SessionStart\n"
    "# hook-matcher: startup|resume|clear\n"
    "exit 0\n"
)
REVISED = (
    "#!/bin/sh\n"
    "# hook: primer\n"
    "# hook-event: SessionStart\n"
    "# hook-matcher: startup\n"
    "exit 0\n"
)


class HookLifecycleTests(unittest.TestCase):
    """The lifecycle chain over the new kind, on the machinery the other kinds use."""

    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        (self.repo / "hooks").mkdir(parents=True)
        (self.repo / "hooks" / "primer.sh").write_text(SCRIPT, encoding="utf-8")
        self.addCleanup(self.temp.cleanup)

    def config(self, mode: str = "copy", *, agent: str = "claude", dry_run: bool = False):
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
        entries = [entry for entry in installer.discover_entries(self.repo) if entry.kind == "hook"]
        self.assertEqual(len(entries), 1, "exactly one hook payload is expected")
        return entries[0]

    def destination(self, config) -> Path:
        return installer.destination_for(self.entry, config)

    def test_install_records_ownership_and_uninstall_removes_the_owned_script(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(destination, config.home / ".claude" / "hooks" / "primer.sh")

        installed = installer.install(config)

        self.assertEqual(installed.exit_code, 0, installed.messages)
        self.assertIn(f"installed: {destination} (copy)", installed.messages)
        self.assertTrue(destination.is_file())
        self.assertFalse(destination.is_symlink())
        self.assertEqual(destination.read_text(encoding="utf-8"), SCRIPT)
        record = installer.load_state(config.state_path)["entries"][str(destination)]
        self.assertEqual(record["kind"], "hook")
        self.assertEqual(record["name"], "primer.sh")
        self.assertEqual(set(record), installer.RECORD_FIELDS)
        self.assertEqual(record["digest"], installer.digest(self.entry.source))

        removed = installer.uninstall(config)

        self.assertEqual(removed.exit_code, 0, removed.messages)
        self.assertIn(f"removed: {destination}", removed.messages)
        self.assertFalse(destination.exists())
        self.assertEqual(installer.load_state(config.state_path)["entries"], {})

    def test_installing_a_hook_writes_no_settings_document_anywhere(self) -> None:
        """The install!=enable boundary, asserted as an absence with its positive control."""
        config = self.config()
        destination = self.destination(config)

        self.assertEqual(installer.install(config).exit_code, 0)

        self.assertTrue(destination.is_file(), "the hook bytes themselves must land")
        for home in (self.root / "home", self.root / "codex"):
            self.assertEqual(
                list(home.rglob("settings.json")),
                [],
                "installing a hook must never create or edit a settings document",
            )
        self.assertEqual(list((self.root / "home").rglob("hooks.json")), [])

    def test_owned_hook_copy_is_refreshed_when_the_source_drifts(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        self.entry.source.write_text(REVISED, encoding="utf-8")

        # Positive control on the refresh path: a dry run must report the pending refresh and
        # change nothing, so the mutation below is provably the write and not a coincidence.
        preview = installer.install(self.config(dry_run=True))
        self.assertIn(f"would refresh: {destination}", preview.messages)
        self.assertEqual(destination.read_text(encoding="utf-8"), SCRIPT)

        refreshed = installer.install(config)

        self.assertEqual(refreshed.exit_code, 0, refreshed.messages)
        self.assertIn(f"refreshed: {destination}", refreshed.messages)
        self.assertEqual(destination.read_text(encoding="utf-8"), REVISED)
        record = installer.load_state(config.state_path)["entries"][str(destination)]
        self.assertEqual(record["digest"], installer.digest(self.entry.source))

    def test_a_user_modified_owned_hook_is_preserved_and_reported(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        destination.write_text(SCRIPT + "# operator edit\n", encoding="utf-8")

        again = installer.install(config)

        self.assertEqual(again.exit_code, 1, again.messages)
        self.assertIn(f"conflict: {destination}", again.messages)
        self.assertEqual(destination.read_text(encoding="utf-8"), SCRIPT + "# operator edit\n")

        removal = installer.uninstall(config)

        self.assertEqual(removal.exit_code, 1, removal.messages)
        self.assertTrue(destination.is_file(), "a modified hook must survive uninstall")

    def test_a_foreign_hook_file_is_preserved_and_reported(self) -> None:
        config = self.config()
        destination = self.destination(config)
        destination.parent.mkdir(parents=True)
        destination.write_text("#!/bin/sh\n# someone else's hook\n", encoding="utf-8")

        result = installer.install(config)

        self.assertEqual(result.exit_code, 1, result.messages)
        self.assertIn(f"conflict: {destination}", result.messages)
        self.assertEqual(
            destination.read_text(encoding="utf-8"), "#!/bin/sh\n# someone else's hook\n"
        )
        self.assertEqual(installer.load_state(config.state_path)["entries"], {})

        # Positive control: the same install succeeds once the foreign file is gone, so the
        # refusal above is about ownership and not about the hook kind being uninstallable.
        destination.unlink()
        self.assertEqual(installer.install(config).exit_code, 0)
        self.assertIn(str(destination), installer.load_state(config.state_path)["entries"])

    def test_status_inventories_the_hook_kind(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)

        healthy = installer.status(config)

        self.assertEqual(healthy.exit_code, 0, healthy.messages)
        self.assertIn(f"ok: {destination}", healthy.messages)
        self.assertEqual(healthy.messages[-1], "1 ok, 0 conflict, 0 absent")

        destination.unlink()
        absent = installer.status(config)

        self.assertEqual(absent.exit_code, 1)
        self.assertIn(f"absent: {destination}", absent.messages)

    def test_the_codex_plane_owns_no_hook(self) -> None:
        codex_config = self.config(agent="codex")

        result = installer.install(codex_config)

        self.assertEqual(result.exit_code, 0, result.messages)
        self.assertFalse((self.root / "codex" / "hooks").exists())
        self.assertEqual(installer.load_state(codex_config.state_path)["entries"], {})
        with self.assertRaises(installer.InstallerError) as raised:
            installer.destination_for(
                installer.Entry("codex", "hook", "primer.sh", self.entry.source), codex_config
            )
        self.assertIn("no Codex destination", str(raised.exception))

        # Positive control: the claude plane installs the same payload.
        self.assertEqual(installer.install(self.config()).exit_code, 0)

    def test_the_entry_kind_docstring_states_the_authority_boundary(self) -> None:
        text = installer.entry_collection.__doc__ or ""
        self.assertIn(".claude/hooks/", text)
        self.assertIn("never enables it", text)
        self.assertIn("separately authorized", text)
        self.assertEqual(installer.entry_collection("hook"), "hooks")
        self.assertIsNone(installer.entry_collection(["hook"]))


class HookValidatorTests(unittest.TestCase):
    """Shape rules for an authored hook script, each with a positive control."""

    maxDiff = None

    def check(self, *, name: str = "primer.sh", text: str = SCRIPT, link: bool = False) -> list[str]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "hooks").mkdir()
            path = root / "hooks" / name
            if link:
                (root / "elsewhere.sh").write_text(text, encoding="utf-8")
                path.symlink_to(root / "elsewhere.sh")
            else:
                # newline="\n" pins the on-disk bytes: the byte budget is over LF-shipped hook
                # files, and Windows' default translation would inflate every \n to \r\n.
                path.write_text(text, encoding="utf-8", newline="\n")
            result = validator.Validation()
            validator.validate_hooks(root, result)
            return result.errors

    def test_a_clean_script_passes(self) -> None:
        self.assertEqual(self.check(), [])

    def test_the_shipped_hooks_tree_passes(self) -> None:
        result = validator.Validation()
        validator.validate_hooks(ROOT, result)
        self.assertEqual(result.errors, [])
        self.assertTrue(SHIPPED_HOOK.is_file(), "the bundle must ship a real hook entry")

    def test_an_absent_hooks_tree_is_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = validator.Validation()
            validator.validate_hooks(Path(temp), result)
            self.assertEqual(result.errors, [])

    def test_a_non_sh_sibling_is_rejected_including_a_plugin_style_hooks_json(self) -> None:
        # `hooks.json` is the plugin-channel auto-enable surface this plane deliberately refuses:
        # a plugin's hooks.json is enabled the moment the plugin is, which violates the
        # install!=enable doctrine. The suffix rule refuses it structurally, by name.
        self.assertEqual(
            self.check(name="hooks.json", text='{"hooks": {}}\n'),
            ["hooks/hooks.json: hook scripts must use the .sh suffix"],
        )

    def test_a_symlinked_hook_is_rejected(self) -> None:
        self.assertEqual(
            self.check(link=True),
            ["hooks/primer.sh: hooks/ holds regular hook scripts only"],
        )

    def test_a_non_slug_name_is_rejected(self) -> None:
        for name in ("Primer.sh", "primer_two.sh", "-primer.sh"):
            with self.subTest(name=name):
                stem = Path(name).stem
                errors = self.check(name=name, text=SCRIPT.replace("# hook: primer", f"# hook: {stem}"))
                self.assertIn(f"hooks/{name}: hook name must be a lowercase slug", errors)
        self.assertEqual(
            self.check(name="primer-2.sh", text=SCRIPT.replace("# hook: primer", "# hook: primer-2")), []
        )

    def test_a_wrong_shebang_is_rejected(self) -> None:
        errors = self.check(text="#!/bin/bash\n" + SCRIPT.split("\n", 1)[1])
        self.assertIn("hooks/primer.sh: line 1 must be exactly '#!/bin/sh'", errors)

    def test_a_missing_or_mismatched_name_header_is_rejected(self) -> None:
        self.assertEqual(
            self.check(text="#!/bin/sh\nexit 0\n"),
            [
                "hooks/primer.sh: missing a '# hook: <name>' header on line 2",
                "hooks/primer.sh: missing a '# hook-event: <event>' header on line 3",
                "hooks/primer.sh: missing a '# hook-matcher: <matchers>' header on line 4",
            ],
        )
        self.assertEqual(
            self.check(text=SCRIPT.replace("# hook: primer", "# hook: other")),
            ["hooks/primer.sh: declared hook name does not match the file name"],
        )
        # CRLF endings on the header lines stay legal, mirroring the workflow header rule.
        self.assertEqual(self.check(text=SCRIPT.replace("\n", "\r\n")), [])

    def test_an_unknown_event_is_rejected(self) -> None:
        errors = self.check(text=SCRIPT.replace("hook-event: SessionStart", "hook-event: PreToolUse"))
        self.assertIn("hooks/primer.sh: unknown hook-event 'PreToolUse'", errors)

    def test_an_unknown_matcher_token_is_rejected(self) -> None:
        errors = self.check(text=SCRIPT.replace("startup|resume|clear", "startup|sidechain"))
        self.assertEqual(errors, ["hooks/primer.sh: unknown hook-matcher token 'sidechain'"])
        # Positive control: every documented SessionStart matcher is accepted.
        self.assertEqual(
            self.check(text=SCRIPT.replace("startup|resume|clear", "startup|resume|clear|compact|fork")),
            [],
        )

    def test_an_oversize_script_is_rejected_at_the_exact_budget(self) -> None:
        budget = validator.HOOK_MAX_BYTES
        base = SCRIPT
        at_cap = base + "#" * (budget - len(base.encode("utf-8")) - 1) + "\n"
        self.assertEqual(len(at_cap.encode("utf-8")), budget)
        self.assertEqual(self.check(text=at_cap), [])

        over = at_cap + "#\n"
        errors = self.check(text=over)
        self.assertEqual(
            errors,
            [f"hooks/primer.sh: hook script exceeds the {budget}-byte context-injection budget"],
        )

    def test_a_user_specific_path_is_rejected(self) -> None:
        for body in (
            "# see /home/operator/.claude/hooks\n",
            "# see /Users/operator/.claude/hooks\n",
        ):
            with self.subTest(body=body.strip()):
                errors = self.check(text=SCRIPT + body)
                self.assertIn("hooks/primer.sh: user-specific paths are forbidden", errors)
        self.assertEqual(self.check(text=SCRIPT + "# see ~/.claude/hooks and $HOME/.claude\n"), [])

    @unittest.skipIf(shutil.which("sh") is None, "sh is unavailable for the parse probe")
    def test_an_unparseable_script_is_rejected_without_raw_control_characters(self) -> None:
        errors = self.check(text=SCRIPT + "if then fi (\n")
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith("hooks/primer.sh does not parse: "), errors)
        self.assertNotIn("\n", errors[0])
        # Positive control on the escape step itself: a child whose stderr embeds a real newline
        # must surface as the escaped two-character sequence, not a raw line break.
        fake = subprocess.CompletedProcess(args=["sh"], returncode=2, stdout="", stderr="first\nsecond\n")
        with mock.patch.object(validator.shutil, "which", return_value="sh"), mock.patch.object(
            validator.subprocess, "run", return_value=fake
        ):
            escaped = self.check()
        self.assertEqual(len(escaped), 1, escaped)
        self.assertNotIn("\n", escaped[0])
        self.assertIn("\\n", escaped[0])

    def test_the_validator_skips_the_parse_probe_without_sh(self) -> None:
        with mock.patch.object(validator.shutil, "which", return_value=None), mock.patch.object(
            validator.subprocess, "run", side_effect=AssertionError("sh was invoked")
        ):
            self.assertEqual(self.check(text=SCRIPT + "if then fi (\n"), [])

    def test_the_whole_validator_runs_the_hook_checks(self) -> None:
        """The registration is load-bearing: a check nothing calls is a check nothing enforces."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "hooks").mkdir()
            (root / "hooks" / "primer.sh").write_text(
                SCRIPT.replace("# hook: primer", "# hook: other"), encoding="utf-8"
            )
            errors = validator.validate(root).errors
        self.assertIn("hooks/primer.sh: declared hook name does not match the file name", errors)

    def test_the_manager_and_validator_share_one_event_vocabulary(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            manage = _load("hook_kind_manager", ROOT / "scripts" / "manage_claude_hooks.py")
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        self.assertEqual(manage.HOOK_EVENT_MATCHERS, validator.HOOK_EVENT_MATCHERS)


class HookPayloadTests(unittest.TestCase):
    """The shipped payload roots agree about the new tree, and the plugin channel refuses it."""

    def test_the_release_candidate_payload_carries_the_hooks_tree(self) -> None:
        policy = validator.load_json_object(
            ROOT / "policy" / "release-candidate.v1.json", "release-candidate policy"
        )
        payload = policy["payload"]
        assert isinstance(payload, dict)
        trees = payload["trees"]
        assert isinstance(trees, list)
        self.assertIn("hooks", trees)
        self.assertEqual(trees, sorted(trees))

    def test_the_candidate_policy_must_require_the_hooks_root(self) -> None:
        """Dropping the tree from the payload allowlist must fail the gate, not ship silently."""
        source = (ROOT / "policy" / "release-candidate.v1.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "policy").mkdir()
            target = root / "policy" / "release-candidate.v1.json"

            missing_roots = (
                "policy/release-candidate.v1.json: minimal authored payload roots are missing"
            )
            target.write_text(source, encoding="utf-8")
            intact = validator.Validation()
            validator.validate_release_candidate_policy(root, intact)
            self.assertNotIn(missing_roots, intact.errors)

            stripped_source = source.replace('"hooks",', "")
            self.assertNotEqual(stripped_source, source, "the tree must be present to remove")
            target.write_text(stripped_source, encoding="utf-8")
            stripped = validator.Validation()
            validator.validate_release_candidate_policy(root, stripped)
            self.assertIn(missing_roots, stripped.errors)

    def test_the_plugin_tree_does_not_expose_the_hooks_collection(self) -> None:
        """A plugin's hooks surface auto-enables when the plugin is enabled, which is exactly the
        install!=enable violation this plane refuses. The direct channel is the only distribution:
        no plugin/hooks link, no hooks/hooks.json manifest anywhere in the authored tree."""
        self.assertFalse((ROOT / "plugin" / "hooks").exists())
        self.assertFalse((ROOT / "hooks" / "hooks.json").exists())
        plugin_manifest = (ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        self.assertNotIn('"hooks"', plugin_manifest)

    def test_the_required_mise_tasks_include_the_hook_manager_verbs(self) -> None:
        for task in ("claude:hooks:status", "claude:hooks:activate", "claude:hooks:deactivate"):
            self.assertIn(task, validator.REQUIRED_TASKS)


if __name__ == "__main__":
    unittest.main()
