"""The workflow overlay entry kind: one bounded payload kind on the existing bundle lifecycle.

Every test here asks the same question from a different angle: does `workflow` ride the SAME
ownership, staging, refresh, preservation, and removal machinery the other kinds ride, and does the
validator hold the authored document to a checkable shape? Nothing here executes a workflow —
installing one is a byte-ownership effect only.
"""

from __future__ import annotations

import importlib.util
import os
import re
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
SHIPPED_WORKFLOW = ROOT / "workflows" / "sdlc-wave-scout.js"
# The repo-pinned node, rather than `shutil.which("node")`: an ambient PATH node could be a
# different major version than the one this bundle's toolchain certifies, and the collapse test
# below cares about exact refusal wording this pin is known to produce.
PINNED_NODE = Path.home() / ".local" / "share" / "mise" / "installs" / "node" / "22.23.2" / "bin" / "node"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


installer = _load("workflow_kind_installer", INSTALLER_PATH)
validator = _load("workflow_kind_validator", VALIDATOR_PATH)

def meta_line(name: str = "wave") -> str:
    """The host-required first statement, in the smallest shape the validator admits."""
    return f"export const meta = {{ name: '{name}', description: 'map one wave' }};\n"


DOCUMENT = (
    "// workflow: wave\n"
    + meta_line()
    + "const plan = await agent('map the wave', options);\nreturn plan;\n"
)
REVISED = (
    "// workflow: wave\n"
    + meta_line()
    + "const plan = await agent('map the wave twice', options);\nreturn plan;\n"
)


class WorkflowLifecycleTests(unittest.TestCase):
    """The lifecycle chain over the new kind, on the machinery the other kinds use."""

    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        (self.repo / "workflows").mkdir(parents=True)
        (self.repo / "workflows" / "wave.js").write_text(DOCUMENT, encoding="utf-8")
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
        entries = [
            entry
            for entry in installer.discover_entries(self.repo)
            if entry.kind == "workflow"
        ]
        self.assertEqual(len(entries), 1, "exactly one workflow payload is expected")
        return entries[0]

    def destination(self, config) -> Path:
        return installer.destination_for(self.entry, config)

    def test_install_records_ownership_and_uninstall_removes_the_owned_document(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(destination, config.home / ".claude" / "workflows" / "wave.js")

        installed = installer.install(config)

        self.assertEqual(installed.exit_code, 0, installed.messages)
        self.assertIn(f"installed: {destination} (copy)", installed.messages)
        self.assertTrue(destination.is_file())
        self.assertFalse(destination.is_symlink())
        self.assertEqual(destination.read_text(encoding="utf-8"), DOCUMENT)
        record = installer.load_state(config.state_path)["entries"][str(destination)]
        self.assertEqual(record["kind"], "workflow")
        self.assertEqual(record["name"], "wave.js")
        self.assertEqual(set(record), installer.RECORD_FIELDS)
        self.assertEqual(record["digest"], installer.digest(self.entry.source))

        removed = installer.uninstall(config)

        self.assertEqual(removed.exit_code, 0, removed.messages)
        self.assertIn(f"removed: {destination}", removed.messages)
        self.assertFalse(destination.exists())
        self.assertEqual(installer.load_state(config.state_path)["entries"], {})

    def test_link_mode_installs_and_removes_a_workflow_link(self) -> None:
        config = self.config("link")
        destination = self.destination(config)

        installed = installer.install(config)

        self.assertEqual(installed.exit_code, 0, installed.messages)
        self.assertTrue(destination.is_symlink() or installer.is_junction(destination))
        self.assertTrue(os.path.samefile(destination.resolve(), self.entry.source))
        self.assertEqual(installer.uninstall(config).exit_code, 0)
        self.assertFalse(destination.exists())

    def test_owned_workflow_copy_is_refreshed_when_the_source_drifts(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        stale_digest = installer.load_state(config.state_path)["entries"][str(destination)]["digest"]
        self.entry.source.write_text(REVISED, encoding="utf-8")

        # Positive control on the refresh path: a dry run must report the pending refresh and
        # change nothing, so the mutation below is provably the write and not a coincidence.
        preview = installer.install(self.config(dry_run=True))
        self.assertIn(f"would refresh: {destination}", preview.messages)
        self.assertEqual(destination.read_text(encoding="utf-8"), DOCUMENT)

        refreshed = installer.install(config)

        self.assertEqual(refreshed.exit_code, 0, refreshed.messages)
        self.assertIn(f"refreshed: {destination}", refreshed.messages)
        self.assertEqual(destination.read_text(encoding="utf-8"), REVISED)
        current = installer.load_state(config.state_path)["entries"][str(destination)]
        self.assertNotEqual(current["digest"], stale_digest)
        self.assertEqual(current["digest"], installer.digest(self.entry.source))

    def test_a_user_modified_owned_workflow_is_preserved_and_reported(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        destination.write_text("// workflow: wave\n// operator edit\n", encoding="utf-8")

        again = installer.install(config)

        self.assertEqual(again.exit_code, 1, again.messages)
        self.assertIn(f"conflict: {destination}", again.messages)
        self.assertIn(
            f"preserved: {destination} (owned entry changed; inspect and resolve it before retrying)",
            again.messages,
        )
        self.assertEqual(
            destination.read_text(encoding="utf-8"), "// workflow: wave\n// operator edit\n"
        )

        removal = installer.uninstall(config)

        self.assertEqual(removal.exit_code, 1, removal.messages)
        self.assertIn(f"conflict: {destination}", removal.messages)
        self.assertTrue(destination.is_file(), "a modified workflow must survive uninstall")
        self.assertEqual(
            destination.read_text(encoding="utf-8"), "// workflow: wave\n// operator edit\n"
        )

    def test_a_foreign_workflow_overlay_file_is_preserved_and_reported(self) -> None:
        config = self.config()
        destination = self.destination(config)
        destination.parent.mkdir(parents=True)
        destination.write_text("// workflow: wave\n// someone else's overlay\n", encoding="utf-8")

        result = installer.install(config)

        self.assertEqual(result.exit_code, 1, result.messages)
        self.assertIn(f"conflict: {destination}", result.messages)
        self.assertIn(
            f"preserved: {destination} (a non-bundle entry already exists; inspect and resolve it before retrying)",
            result.messages,
        )
        self.assertEqual(
            destination.read_text(encoding="utf-8"), "// workflow: wave\n// someone else's overlay\n"
        )
        self.assertEqual(installer.load_state(config.state_path)["entries"], {})

        # Positive control: the same install succeeds once the foreign document is gone, so the
        # refusal above is about ownership and not about the workflow kind being uninstallable.
        destination.unlink()
        self.assertEqual(installer.install(config).exit_code, 0)
        self.assertIn(str(destination), installer.load_state(config.state_path)["entries"])

    def test_uninstall_removes_only_the_owned_workflow_in_the_collection(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        foreign = destination.with_name("someone-elses.js")
        foreign.write_text("// workflow: someone-elses\n", encoding="utf-8")

        removed = installer.uninstall(config)

        self.assertEqual(removed.exit_code, 0, removed.messages)
        self.assertFalse(destination.exists())
        self.assertTrue(foreign.is_file(), "an unowned neighbour must not be removed")
        self.assertEqual(foreign.read_text(encoding="utf-8"), "// workflow: someone-elses\n")

    def test_status_inventories_the_workflow_kind(self) -> None:
        config = self.config()
        destination = self.destination(config)

        self.assertEqual(installer.status(config).messages[-1], "no owned entries for this host (run: mise run bundle:install)")
        self.assertEqual(installer.install(config).exit_code, 0)

        healthy = installer.status(config)

        self.assertEqual(healthy.exit_code, 0, healthy.messages)
        self.assertIn(f"ok: {destination}", healthy.messages)
        self.assertEqual(healthy.messages[-1], "1 ok, 0 conflict, 0 absent")

        destination.unlink()
        absent = installer.status(config)

        self.assertEqual(absent.exit_code, 1)
        self.assertIn(f"absent: {destination}", absent.messages)
        self.assertEqual(absent.messages[-1], "0 ok, 0 conflict, 1 absent")

    def test_readonly_projection_reports_the_workflow_entry_without_naming_it(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)

        projection = installer.readonly_projection(config)

        self.assertEqual(projection["state"], "healthy")
        self.assertEqual(
            projection["entries"],
            [{"name": "claude-workflow-1", "path": "bundle-entry://claude/workflow/1", "state": "owned"}],
        )
        self.assertEqual(projection["findings"], [])

        destination.write_text("// workflow: wave\n// edited\n", encoding="utf-8")
        degraded = installer.readonly_projection(config)

        self.assertEqual(degraded["state"], "degraded")
        self.assertEqual([entry["state"] for entry in degraded["entries"]], ["foreign"])

    def test_a_workflow_transition_is_admitted_only_under_its_own_collection(self) -> None:
        config = self.config()
        destination = self.destination(config)
        record = installer.entry_record(self.entry, "copy")
        state = installer.empty_state()
        state["pending"] = installer.pending_slot("install", str(destination), None, record)

        installer.validate_pending(config, state)

        mismatched = installer.empty_state()
        mismatched["pending"] = installer.pending_slot(
            "install", str(destination), None, dict(record, kind="command")
        )
        with self.assertRaises(installer.InstallerError) as raised:
            installer.validate_pending(config, mismatched)
        self.assertIn(str(destination), str(raised.exception))

    def test_the_codex_plane_owns_no_workflow(self) -> None:
        codex_config = self.config(agent="codex")

        result = installer.install(codex_config)

        self.assertEqual(result.exit_code, 0, result.messages)
        self.assertFalse((self.root / "codex" / "workflows").exists())
        self.assertEqual(installer.load_state(codex_config.state_path)["entries"], {})
        with self.assertRaises(installer.InstallerError) as raised:
            installer.destination_for(
                installer.Entry("codex", "workflow", "wave.js", self.entry.source), codex_config
            )
        self.assertIn("no Codex destination", str(raised.exception))

        # Positive control: the claude plane installs the same payload.
        self.assertEqual(installer.install(self.config()).exit_code, 0)

    def test_an_unsupported_entry_kind_refuses_by_name_at_exit_two(self) -> None:
        config = self.config()
        with self.assertRaises(installer.InstallerError) as raised:
            installer.destination_for(
                installer.Entry("claude", "playbook", "wave.js", self.entry.source), config
            )
        self.assertEqual(str(raised.exception), "unsupported entry kind: playbook")

        # `main` derives its state path from the environment, so the state root is redirected here:
        # without it this assertion reads the OPERATOR's own ownership document and could pass on
        # whatever that document happens to say rather than on the refusal under test.
        with mock.patch.dict(
            os.environ,
            {"XDG_STATE_HOME": str(self.root / "cli-state"), "LOCALAPPDATA": str(self.root / "cli-state")},
            clear=False,
        ), mock.patch.object(
            installer,
            "discover_entries",
            return_value=[installer.Entry("claude", "playbook", "wave.js", self.entry.source)],
        ):
            exit_code = installer.main(
                [
                    "install",
                    "--claude-home",
                    str(self.root / "home"),
                    "--codex-home",
                    str(self.root / "codex"),
                ]
            )
        self.assertEqual(exit_code, 2)

    def test_an_unhashable_record_kind_is_refused_rather_than_raising_type_error(self) -> None:
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        state = installer.load_state(config.state_path)
        state["entries"][str(destination)]["kind"] = ["workflow"]

        with self.assertRaises(installer.InstallerError) as raised:
            installer.validate_state(config, state)
        self.assertEqual(str(raised.exception), f"invalid ownership record for {destination}")

    def test_an_unhashable_record_agent_is_refused_rather_than_raising_type_error(self) -> None:
        """Sibling of the kind test above: `agent in {"claude", "codex"}` is exactly as unguarded
        against an unhashable value as the `kind in {...}` membership test was, and the fix has to
        be pinned the same way -- an unhashable `agent` must be a refused record, not a TypeError.
        """
        config = self.config()
        destination = self.destination(config)
        self.assertEqual(installer.install(config).exit_code, 0)
        state = installer.load_state(config.state_path)
        state["entries"][str(destination)]["agent"] = []

        with self.assertRaises(installer.InstallerError) as raised:
            installer.validate_state(config, state)
        self.assertEqual(str(raised.exception), f"invalid ownership record for {destination}")

        # Positive control: the unmodified record (a real string agent) still validates, so the
        # refusal above is about the unhashable value and not a change that refuses every record.
        healthy_state = installer.load_state(config.state_path)
        installer.validate_state(config, healthy_state)

    def test_a_workflow_record_is_refused_under_another_collection(self) -> None:
        home = self.root / "home"
        record = {
            "agent": "claude",
            "kind": "workflow",
            "name": "wave.js",
            "source": str(self.entry.source),
            "mode": "copy",
            "digest": "0" * 64,
            "removable": True,
        }

        self.assertFalse(
            installer.record_structure_valid(str(home / ".claude" / "commands" / "wave.js"), record)
        )

        # Positive control: the same record under its own collection is admitted.
        self.assertTrue(
            installer.record_structure_valid(str(home / ".claude" / "workflows" / "wave.js"), record)
        )

    def test_the_record_reader_refuses_an_unhashable_agent_rather_than_raising(self) -> None:
        """`record_structure_valid` carries an `agent in {"claude", "codex"}` membership test, so it
        needs the same `isinstance` guard the kind path already has, or an unhashable `agent` raises
        TypeError instead of refusing.
        """
        home = self.root / "home"
        key = str(home / ".claude" / "commands" / "wave.md")
        record = {
            "agent": [],
            "kind": "command",
            "name": "wave.md",
            "source": str(self.entry.source),
            "mode": "copy",
            "digest": "0" * 64,
            "removable": True,
        }

        self.assertFalse(installer.record_structure_valid(key, record))

        # Positive control: the same record shape with a real agent string is admitted.
        self.assertTrue(installer.record_structure_valid(key, dict(record, agent="claude")))

    def test_the_entry_kind_docstring_states_the_authority_boundary(self) -> None:
        text = installer.entry_collection.__doc__ or ""
        self.assertIn(".claude/workflows/", text)
        self.assertIn("never runs it", text)
        self.assertIn("separately authorized", text)
        self.assertEqual(installer.entry_collection("workflow"), "workflows")
        self.assertIsNone(installer.entry_collection("playbook"))
        self.assertIsNone(installer.entry_collection(["workflow"]))


class WorkflowValidatorTests(unittest.TestCase):
    """Shape rules for an authored workflow document, each with a positive control."""

    maxDiff = None

    def check(self, *, name: str = "wave.js", text: str = DOCUMENT, link: bool = False) -> list[str]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "workflows").mkdir()
            path = root / "workflows" / name
            if link:
                path.symlink_to(root / "elsewhere.js")
                (root / "elsewhere.js").write_text(text, encoding="utf-8")
            else:
                path.write_text(text, encoding="utf-8")
            result = validator.Validation()
            validator.validate_workflows(root, result)
            return result.errors

    def test_a_clean_document_passes(self) -> None:
        self.assertEqual(self.check(), [])

    def test_the_shipped_workflow_tree_passes(self) -> None:
        result = validator.Validation()
        validator.validate_workflows(ROOT, result)
        self.assertEqual(result.errors, [])
        self.assertTrue(SHIPPED_WORKFLOW.is_file(), "the bundle must ship a real workflow entry")

    def test_an_absent_workflows_tree_is_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = validator.Validation()
            validator.validate_workflows(Path(temp), result)
            self.assertEqual(result.errors, [])

    def test_a_non_js_sibling_is_rejected(self) -> None:
        self.assertEqual(
            self.check(name="notes.md", text="notes\n"),
            ["workflows/notes.md: workflow documents must use the .js suffix"],
        )

    def test_a_symlinked_workflow_is_rejected(self) -> None:
        self.assertEqual(
            self.check(link=True),
            ["workflows/wave.js: workflows/ holds regular workflow documents only"],
        )

    def test_a_non_slug_name_is_rejected(self) -> None:
        for name in ("Wave.js", "wave_scout.js", "-wave.js", "wave..js"):
            with self.subTest(name=name):
                stem = Path(name).stem
                errors = self.check(name=name, text=f"// workflow: {stem}\nreturn 1;\n")
                self.assertIn(f"workflows/{name}: workflow name must be a lowercase slug", errors)
        self.assertEqual(
            self.check(
                name="wave-scout-2.js",
                text=f"// workflow: wave-scout-2\n{meta_line('wave-scout-2')}return 1;\n",
            ),
            [],
        )

    def test_a_missing_or_mismatched_header_is_rejected(self) -> None:
        self.assertEqual(
            self.check(text=f"{meta_line()}const plan = 1;\nreturn plan;\n"),
            ["workflows/wave.js: missing a leading '// workflow: <name>' header"],
        )
        self.assertEqual(
            self.check(text=f"// workflow: other\n{meta_line()}return 1;\n"),
            ["workflows/wave.js: declared workflow name does not match the file name"],
        )
        self.assertEqual(self.check(text=f"// workflow: wave\r\n{meta_line()}return 1;\n"), [])

    META_FIRST_STATEMENT_ERROR = (
        "workflows/wave.js: the first statement must be an 'export const meta = {...}' literal"
        " (only '//' comments and blank lines may precede it)"
    )
    META_PURE_LITERAL_ERROR = (
        "workflows/wave.js: meta must be a pure object literal"
        " (no variables, calls, spreads, or interpolation)"
    )

    def test_the_pre_fix_scout_shape_is_rejected_and_the_fixed_scout_passes(self) -> None:
        """The live host refused the meta-less scout at LOAD (agentic-sdlc-60f0); the gate must
        refuse the same shape. The negative fixture is the shipped scout with its meta statement
        stripped, which restores the pre-fix shape whose first statement is `const STAGES`.
        """
        shipped = SHIPPED_WORKFLOW.read_text(encoding="utf-8")
        stripped = re.sub(r"export const meta = \{.*?\};\n", "", shipped, count=1, flags=re.DOTALL)
        self.assertNotEqual(stripped, shipped, "the shipped scout must carry a meta export to strip")
        # The comment above the shipped statement may still QUOTE the phrase; what must be gone
        # is the statement itself.
        self.assertNotIn("export const meta = {", stripped)
        self.assertEqual(
            self.check(name="sdlc-wave-scout.js", text=stripped),
            [
                "workflows/sdlc-wave-scout.js: the first statement must be an"
                " 'export const meta = {...}' literal"
                " (only '//' comments and blank lines may precede it)"
            ],
        )
        # Positive control: the fixed shipped bytes pass the same check under the same name.
        self.assertEqual(self.check(name="sdlc-wave-scout.js", text=shipped), [])

    def test_a_document_without_a_leading_meta_export_is_rejected(self) -> None:
        self.assertEqual(
            self.check(text="// workflow: wave\nconst plan = 1;\nreturn plan;\n"),
            [self.META_FIRST_STATEMENT_ERROR],
        )
        # A meta export declared after another statement is the same load failure: the host
        # requires it as the FIRST statement, not merely present.
        self.assertEqual(
            self.check(text=f"// workflow: wave\nconst first = 1;\n{meta_line()}return first;\n"),
            [self.META_FIRST_STATEMENT_ERROR],
        )

    def test_a_non_literal_meta_is_rejected(self) -> None:
        self.assertEqual(
            self.check(text="// workflow: wave\nexport const meta = { ...base };\nreturn 1;\n"),
            [self.META_PURE_LITERAL_ERROR],
        )
        self.assertEqual(
            self.check(
                text="// workflow: wave\nexport const meta = { name: `wave`, description: 'x' };\nreturn 1;\n"
            ),
            [self.META_PURE_LITERAL_ERROR],
        )
        self.assertEqual(
            self.check(
                text="// workflow: wave\nexport const meta = { name: NAME, description: 'x' };\nreturn 1;\n"
            ),
            ["workflows/wave.js: meta.name must be a string literal"],
        )
        self.assertEqual(
            self.check(
                text="// workflow: wave\nexport const meta = { name: 'wave', description: describe() };\nreturn 1;\n"
            ),
            ["workflows/wave.js: meta.description must be a string literal"],
        )

    def test_meta_fields_are_a_closed_set_without_duplicates(self) -> None:
        self.assertEqual(
            self.check(
                text=(
                    "// workflow: wave\n"
                    "export const meta = { name: 'wave', description: 'x', title: 'y' };\n"
                    "return 1;\n"
                )
            ),
            ["workflows/wave.js: meta field 'title' is not one of name, description, phases"],
        )
        self.assertEqual(
            self.check(
                text=(
                    "// workflow: wave\n"
                    "export const meta = { name: 'wave', name: 'wave', description: 'x' };\n"
                    "return 1;\n"
                )
            ),
            ["workflows/wave.js: meta declares 'name' more than once"],
        )

    def test_meta_must_declare_a_matching_name_and_a_nonempty_description(self) -> None:
        self.assertEqual(
            self.check(
                text="// workflow: wave\nexport const meta = { name: 'other', description: 'x' };\nreturn 1;\n"
            ),
            ["workflows/wave.js: meta.name must be the string 'wave'"],
        )
        self.assertEqual(
            self.check(text="// workflow: wave\nexport const meta = { name: 'wave' };\nreturn 1;\n"),
            ["workflows/wave.js: meta must declare both name and description"],
        )
        self.assertEqual(
            self.check(
                text="// workflow: wave\nexport const meta = { name: 'wave', description: ' ' };\nreturn 1;\n"
            ),
            ["workflows/wave.js: meta.description must be a nonempty string literal"],
        )

    def test_meta_phases_must_be_an_array_of_string_literals(self) -> None:
        for phases in ("'cartography'", "[plan()]"):
            with self.subTest(phases=phases):
                errors = self.check(
                    text=(
                        "// workflow: wave\n"
                        f"export const meta = {{ name: 'wave', description: 'x', phases: {phases} }};\n"
                        "return 1;\n"
                    )
                )
                self.assertEqual(
                    errors, ["workflows/wave.js: meta.phases must be an array of string literals"]
                )
        # Positive control: the documented optional field in its admitted shape.
        self.assertEqual(
            self.check(
                text=(
                    "// workflow: wave\n"
                    "export const meta = { name: 'wave', description: 'x',"
                    " phases: ['cartography', 'wave graph'] };\n"
                    "return 1;\n"
                )
            ),
            [],
        )

    def test_an_unterminated_meta_export_is_rejected(self) -> None:
        errors = self.check(text="// workflow: wave\nexport const meta = { name: 'wave',\n")
        self.assertIn("workflows/wave.js: the meta export is unterminated", errors)

    def test_module_loading_is_rejected(self) -> None:
        for body in (
            "const fs = require('fs');\nreturn fs;\n",
            "import helper from './helper.js';\nreturn helper;\n",
            "const helper = await import('./helper.js');\nreturn helper;\n",
        ):
            with self.subTest(body=body.split("\n", 1)[0]):
                errors = self.check(text=f"// workflow: wave\n{body}")
                self.assertIn("workflows/wave.js: a workflow document must not load modules", errors)
        self.assertEqual(
            self.check(text=f"// workflow: wave\n{meta_line()}return agent('go', {{}});\n"), []
        )

    def test_a_static_model_or_effort_pin_is_rejected(self) -> None:
        for body in (
            "return agent('go', { model: 'claude-opus-5' });\n",
            'return agent("go", { effort: "xhigh" });\n',
        ):
            with self.subTest(body=body.strip()):
                errors = self.check(text=f"// workflow: wave\n{body}")
                self.assertIn("workflows/wave.js: static model or effort pins are forbidden", errors)
        self.assertEqual(
            self.check(
                text=(
                    "// workflow: wave\n"
                    + meta_line()
                    + "return agent('go', { model: assignment.requested_model_id, "
                    "effort: assignment.requested_effort });\n"
                )
            ),
            [],
        )

    def test_a_user_specific_path_is_rejected(self) -> None:
        for body in (
            "// see /home/operator/.claude/workflows\nreturn 1;\n",
            "// see /Users/operator/.claude/workflows\nreturn 1;\n",
            "// see C:\\\\Users\\\\operator\\\\.claude\nreturn 1;\n",
        ):
            with self.subTest(body=body.split("\n", 1)[0]):
                errors = self.check(text=f"// workflow: wave\n{body}")
                self.assertIn("workflows/wave.js: user-specific paths are forbidden", errors)
        self.assertEqual(
            self.check(
                text=(
                    "// workflow: wave\n// see ~/.claude/workflows and $HOME/.claude\n"
                    + meta_line()
                    + "return 1;\n"
                )
            ),
            [],
        )

    @unittest.skipIf(shutil.which("node") is None, "node is unavailable for the parse probe")
    def test_an_unparseable_document_is_rejected(self) -> None:
        errors = self.check(text=f"// workflow: wave\n{meta_line()}const broken = ;\n")
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith("workflows/wave.js does not parse: "), errors)
        # The real child's `.message` for this input is single-line, so this is a genuine
        # zero-newline claim: no raw control character reaches the rendered report.
        self.assertNotIn("\n", errors[0])
        # Positive control on the escape step itself, not just on this one input: mock a child
        # whose stderr WOULD embed a real newline (a future refactor that writes `.stack` instead
        # of `.message` could do exactly this) and confirm the escaped two-character sequence
        # survives into the rendered line. Without this, the assertion above would be true for the
        # wrong reason -- no multi-line message was ever produced, not because escaping worked.
        fake = subprocess.CompletedProcess(
            args=["node"], returncode=1, stdout="", stderr="first line\nsecond line\n"
        )
        with mock.patch.object(validator.shutil, "which", return_value="node"), mock.patch.object(
            validator.subprocess, "run", return_value=fake
        ):
            escaped_errors = self.check(text=f"// workflow: wave\n{meta_line()}const broken = ;\n")
        self.assertEqual(len(escaped_errors), 1, escaped_errors)
        self.assertNotIn("\n", escaped_errors[0])
        self.assertIn("\\n", escaped_errors[0])
        # Positive control: the documented shape (the meta export, then top-level await plus a
        # terminal return) parses, so the failure above is the syntax error and not the shape.
        self.assertEqual(
            self.check(
                text=f"// workflow: wave\n{meta_line()}const x = await agent('go', {{}});\nreturn x;\n"
            ),
            [],
        )

    @unittest.skipIf(shutil.which("node") is None, "node is unavailable for the parse probe")
    def test_the_parse_probe_compiles_without_executing_the_document(self) -> None:
        """Validating a workflow must not run it, and the check has to be able to tell."""
        # Executing this body would end the probe's child with status 7, which the validator would
        # report as a parse failure. Silence is therefore evidence that it was only compiled.
        self.assertEqual(
            self.check(text=f"// workflow: wave\n{meta_line()}process.exit(7);\nreturn 1;\n"), []
        )
        # Positive control: the same probe still reports a genuine syntax error, so the silence
        # above is compile-only behaviour and not a probe that never ran.
        self.assertEqual(
            len(self.check(text=f"// workflow: wave\n{meta_line()}const broken = ;\n")), 1
        )

    def test_the_whole_validator_runs_the_workflow_checks(self) -> None:
        """The registration is load-bearing: a check nothing calls is a check nothing enforces."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "workflows").mkdir()
            (root / "workflows" / "wave.js").write_text("// workflow: other\n", encoding="utf-8")
            errors = validator.validate(root).errors
        self.assertIn(
            "workflows/wave.js: declared workflow name does not match the file name", errors
        )

    def test_a_secret_shaped_string_in_a_workflow_document_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "workflows").mkdir()
            planted = "AKIA" + "A" * 16
            (root / "workflows" / "wave.js").write_text(
                f"// workflow: wave\nconst key = '{planted}';\nreturn key;\n", encoding="utf-8"
            )
            result = validator.Validation()
            validator.validate_policy(root, result)
            self.assertIn(
                "possible secret or internal hostname found: workflows/wave.js", result.errors
            )
            # Positive control: the same document without the planted string is clean, so the
            # finding above is the string and not the suffix.
            (root / "workflows" / "wave.js").write_text(DOCUMENT, encoding="utf-8")
            clean = validator.Validation()
            validator.validate_policy(root, clean)
            self.assertEqual(clean.errors, [])

    def test_the_validator_skips_the_parse_probe_without_node(self) -> None:
        with mock.patch.object(validator.shutil, "which", return_value=None), mock.patch.object(
            validator.subprocess, "run", side_effect=AssertionError("node was invoked")
        ):
            self.assertEqual(
                self.check(text=f"// workflow: wave\n{meta_line()}const broken = ;\n"), []
            )


class WorkflowPayloadTests(unittest.TestCase):
    """The shipped payload and the release-candidate payload roots agree about the new tree."""

    def test_the_release_candidate_payload_carries_the_workflows_tree(self) -> None:
        policy = validator.load_json_object(
            ROOT / "policy" / "release-candidate.v1.json", "release-candidate policy"
        )
        payload = policy["payload"]
        assert isinstance(payload, dict)
        trees = payload["trees"]
        assert isinstance(trees, list)
        self.assertIn("workflows", trees)
        self.assertEqual(trees, sorted(trees))

    def test_the_candidate_policy_must_require_the_workflows_root(self) -> None:
        """Dropping the tree from the payload allowlist must fail the gate, not ship silently."""
        source = (ROOT / "policy" / "release-candidate.v1.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "policy").mkdir()
            target = root / "policy" / "release-candidate.v1.json"

            missing_roots = (
                "policy/release-candidate.v1.json: minimal authored payload roots are missing"
            )
            # The policy validator also cross-checks version identity against files this temp
            # root does not carry, so the control is the specific finding rather than silence.
            target.write_text(source, encoding="utf-8")
            intact = validator.Validation()
            validator.validate_release_candidate_policy(root, intact)
            self.assertNotIn(missing_roots, intact.errors)

            stripped_source = source.replace(',"workflows"]', "]")
            self.assertNotEqual(stripped_source, source, "the tree must be present to remove")
            target.write_text(stripped_source, encoding="utf-8")
            stripped = validator.Validation()
            validator.validate_release_candidate_policy(root, stripped)
            self.assertIn(missing_roots, stripped.errors)

    def test_the_plugin_tree_exposes_the_workflows_collection(self) -> None:
        link = ROOT / "plugin" / "workflows"
        self.assertTrue(link.is_symlink(), "the plugin tree links its component collections")
        # The checked-in blob's target is `../workflows`; Windows renders the reparse-point
        # target with backslashes (`..\\workflows`), the same relative payload, so compare the
        # normalized form rather than one platform's rendering.
        self.assertEqual(Path(os.readlink(link)).as_posix(), "../workflows")
        self.assertTrue(link.is_dir())

    def test_the_shipped_workflow_refuses_before_dispatch_without_an_assignment(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is unavailable to exercise the shipped refusal")
        probe = (
            "const fs = require('fs');"
            "const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;"
            # `export` cannot appear in a function body; demote the meta statement to a plain
            # `const` exactly as the validator's parse probe does before wrapping the body
            # (line-anchored, because a comment may quote the phrase).
            "const body = fs.readFileSync(process.argv[1], 'utf8')"
            ".replace(/^([ \\t]*)export(?=[ \\t]+const[ \\t]+meta\\b)/m, '$1');"
            "const run = new AsyncFunction('agent', body);"
            "run(() => { throw new Error('dispatched'); })"
            ".then(() => { process.stdout.write('DISPATCHED'); })"
            ".catch((error) => { process.stdout.write(String(error && error.message)); });"
        )
        completed = subprocess.run(
            [node, "-e", probe, str(SHIPPED_WORKFLOW)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("no RuntimeAssignment was supplied", completed.stdout)
        self.assertNotIn("DISPATCHED", completed.stdout)

    def test_the_shipped_workflow_names_an_incomplete_assignment_distinctly(self) -> None:
        """The other direction of the same collapse the test above pins: `requireResolvedAssignment`
        names "not supplied" for a stage with NO entry in `ASSIGNMENTS`, and a DIFFERENT message,
        "is incomplete; missing", for a stage whose entry arrived but did not resolve. Patching
        `ASSIGNMENTS` to a model-only (no `requested_effort`, no `resolution_state`) assignment for
        the first stage in a temp copy exercises the second branch without ever touching the
        distributed bytes, and both assertions below have to hold or the two messages have
        collapsed into one.
        """
        if not PINNED_NODE.is_file():
            self.skipTest(f"the repo-pinned node is unavailable at {PINNED_NODE}")
        source = SHIPPED_WORKFLOW.read_text(encoding="utf-8")
        marker = "const ASSIGNMENTS = {};"
        self.assertIn(marker, source, "the shipped source must still declare ASSIGNMENTS this way")
        patched = source.replace(
            marker,
            "const ASSIGNMENTS = { cartography: { requested_model_id: 'x' } };",
        )
        self.assertNotEqual(patched, source, "the substitution must actually take effect")

        with tempfile.TemporaryDirectory() as temp:
            copy_path = Path(temp) / "sdlc-wave-scout-incomplete.js"
            copy_path.write_text(patched, encoding="utf-8")
            probe = (
                "const fs = require('fs');"
                "const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;"
                # `export` cannot appear in a function body; demote the meta statement to a plain
            # `const` exactly as the validator's parse probe does before wrapping the body
            # (line-anchored, because a comment may quote the phrase).
            "const body = fs.readFileSync(process.argv[1], 'utf8')"
            ".replace(/^([ \\t]*)export(?=[ \\t]+const[ \\t]+meta\\b)/m, '$1');"
                "const run = new AsyncFunction('agent', body);"
                "run(() => { throw new Error('dispatched'); })"
                ".then(() => { process.stdout.write('DISPATCHED'); })"
                ".catch((error) => { process.stdout.write(String(error && error.message)); });"
            )
            completed = subprocess.run(
                [str(PINNED_NODE), "-e", probe, str(copy_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("is incomplete; missing", completed.stdout)
        self.assertNotIn("no RuntimeAssignment was supplied", completed.stdout)
        self.assertNotIn("DISPATCHED", completed.stdout)


if __name__ == "__main__":
    unittest.main()
