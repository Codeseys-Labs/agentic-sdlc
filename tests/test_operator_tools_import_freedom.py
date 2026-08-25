"""The keepers' `install_operator_tools` surface is a CLOSED, shrinking, named set (gh #10 phase 1).

`scripts/install_operator_tools.py` is the retiring PATH plane, and it is also a live library to
three modules that outlive it. This suite is the ratchet on that coupling: every name each keeper
still takes from it is declared here with the wave that removes the name, and the declaration is
compared for EXACT equality. So a re-introduced helper fails here (the direction gh #10 phase 1's
mutation lever exercises), and so does a name the plane's demolition removed without updating this
list -- a subset check would have gone quiet in the second direction.

What phase 1 actually moved off the plane is `absolute` and `state_root_for`; `FREED_NAMES` pins
those two as absent from all three keepers, which is the crisp claim, and `RETAINED` records the
rest as scheduled deletions rather than as re-points. The re-point's no-behaviour-change control is
the second suite below: the replacement derivations are asserted EQUAL to the
`install_operator_tools` originals they replaced, over the same inputs, on the same host. Those
assertions retire with the plane; by then the equality has already been proven.

Phase 2 (D2) emptied one of the three: `scripts/manage_claude_statusline.py` takes NOTHING from the
plane any more, because the statusline is a bundle ledger row and its command path, its lock, and
its error class all come from `install_skill_bundle`. Its declaration below is the empty dict, which
under this suite's exact-equality rule is a literal import-zero claim rather than an absence of
interest -- re-introducing any name at all fails here. The plane's `default_bin_dir` equality
assertion retired with it, because no bin directory participates in resolving the command.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
# `manage_claude_statusline` reaches its SIBLING `install_skill_bundle` through a plain top-level
# import, so its containing directory has to be importable exactly as
# tests/test_manage_claude_statusline.py makes it. The import this line serves is no longer the
# plane's -- D2 replaced it -- so the line now outlives the plane rather than retiring with it.
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


operator_tools = _load("import_freedom_operator_tools", ROOT / "scripts" / "install_operator_tools.py")
reader = _load("import_freedom_reader", ROOT / "scripts" / "ccodex_sdlc.py")
recover = _load("import_freedom_recover", ROOT / "scripts" / "ccodex_sdlc_recover.py")
statusline = _load("import_freedom_statusline", ROOT / "scripts" / "manage_claude_statusline.py")


#: The module attribute every keeper reaches `install_operator_tools` through, whether it arrived as
#: a top-level `import ... as`, a guarded `load_sibling`, or a `ModuleType` parameter. Reading the
#: coupling off the SOURCE rather than off an import hook is what lets this suite see a name a code
#: path only reaches at run time on an interrupted host.
ADAPTER_NAME = "operator_tools"

#: The two names gh #10 phase 1 moved off the plane. Nothing in the three keepers may take either
#: again: `absolute` is `install_skill_bundle.operational_path`, and `state_root_for` is now each
#: module's own home-derived derivation (`install_skill_bundle.state_directory()` reads
#: `Path.home()` and so cannot honour a supplied home).
FREED_NAMES = ("absolute", "state_root_for")

#: Every `install_operator_tools` name each keeper still takes, and the wave that removes it.
#: Phase 1 re-points HELPERS; each name below is store-schema or store-machinery, which gh #10's own
#: extraction table books as "deleted with the plane" rather than as re-pointed, so this list shrinks
#: at D2 (statusline) and D3+D4 (the rest) and not before.
RETAINED: dict[str, dict[str, str]] = {
    "scripts/ccodex_sdlc.py": {
        "Config": "D3+D4: the operator-tools config dies with the plane",
        "default_bin_dir": "D3+D4: only feeds the operator-tools Config",
        "readonly_projection": "D3+D4: the read report's `operator_tools` field is deleted with it",
    },
    "scripts/ccodex_sdlc_recover.py": {
        "Config": "D3+D4: the operator-tools config dies with the plane",
        "OperatorToolsError": "D3+D4: the store's own error class",
        "STATE_VERSION": "D3+D4: the operator-tools journal leaves `derive_plan`",
        "_readonly_json_document": "D3+D4: parses the operator-tools journal's own bytes",
        "default_bin_dir": "D3+D4: only feeds the operator-tools Config",
        "lifecycle_lock": "D3+D4: the store's own lock",
        "live_matches": "D3+D4: the store's own liveness predicate",
        "load_state": "D3+D4: the store's own reader",
        "recover_pending": "D3+D4: the store's own crash-consistency machinery",
        "validate_pending": "D3+D4: the store's own pending-slot validator",
    },
    # D2 (gh #10 phase 2) landed: the statusline is a bundle ledger row, so this keeper takes
    # nothing. The empty dict is the claim -- `install_skill_bundle` now supplies the Config, the
    # lock, `exact_owned_statusline`, and the error class.
    "scripts/manage_claude_statusline.py": {},
}


def taken_names(source: Path) -> set[str]:
    """Every attribute the source reads off its `install_operator_tools` adapter.

    An `ast.Attribute` on `ast.Name(ADAPTER_NAME)` and nothing else: the report field spelled
    `operator_tools["state"]` is a subscript, so the closed report vocabulary cannot leak in here and
    read as a library coupling.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == ADAPTER_NAME
    }


class ImportFreedomTests(unittest.TestCase):
    """The declared coupling is the whole coupling, in both directions."""

    def test_every_keeper_takes_exactly_its_declared_names(self) -> None:
        for relative, declared in RETAINED.items():
            with self.subTest(module=relative):
                self.assertEqual(taken_names(ROOT / relative), set(declared))

    def test_no_keeper_takes_a_name_phase_one_moved_off_the_plane(self) -> None:
        for relative in RETAINED:
            with self.subTest(module=relative):
                taken = taken_names(ROOT / relative)
                for freed in FREED_NAMES:
                    self.assertNotIn(freed, taken)

    def test_the_scanner_sees_a_name_that_is_really_there(self) -> None:
        """Positive control: `taken_names` is not structurally blind.

        Anchored on `ccodex_sdlc_recover.py` since D2 emptied the statusline module: a suite whose
        every assertion is an absence proves nothing until one presence is read off real source.
        """
        self.assertEqual(
            taken_names(ROOT / "scripts" / "ccodex_sdlc_recover.py") & {"lifecycle_lock"},
            {"lifecycle_lock"},
        )

    def test_the_scanner_reports_a_reintroduced_helper(self) -> None:
        """The mutation the ratchet exists to catch, run against synthesised source.

        Re-introducing `operator_tools.state_root_for` must show up as a taken name; the tests above
        then fail on it. Synthesised rather than planted in the tree so the lever runs on every gate
        instead of only when someone remembers to edit a module by hand.
        """
        mutated = ROOT / "scripts" / "manage_claude_statusline.py"
        source = mutated.read_text(encoding="utf-8")
        regressed = source.replace(
            "else state_root_for(home)", "else operator_tools.state_root_for(home)", 1
        )
        # Compared as a boolean rather than with assertNotEqual: an inequality diff here would print
        # the whole module twice, and the only fact wanted is whether the anchor still exists.
        self.assertTrue(regressed != source, "the phase-1 call site moved; re-derive this lever")
        tree = ast.parse(regressed)
        taken = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == ADAPTER_NAME
        }
        self.assertIn("state_root_for", taken)
        self.assertNotEqual(taken, set(RETAINED["scripts/manage_claude_statusline.py"]))

    def test_every_declared_name_still_exists_on_the_plane(self) -> None:
        """A declaration naming a name the plane no longer exports is stale, not satisfied."""
        for relative, declared in RETAINED.items():
            for name in declared:
                with self.subTest(module=relative, name=name):
                    self.assertTrue(hasattr(operator_tools, name))

    def test_every_freed_name_still_exists_on_the_plane(self) -> None:
        """Positive control for the absence assertions: the names were reachable, not misspelled."""
        for freed in FREED_NAMES:
            with self.subTest(name=freed):
                self.assertTrue(hasattr(operator_tools, freed))


class ReplacementDerivationTests(unittest.TestCase):
    """The re-point changed no path this host resolves. Retires with the plane."""

    HOMES = (
        Path("/home/fixture"),
        Path("/home/fixture/nested"),
        Path("~/fixture"),
        Path("relative-home"),
    )

    def replacements(self):
        return (
            ("ccodex_sdlc.state_root_for", reader.state_root_for),
            ("ccodex_sdlc_recover._state_root_for", recover._state_root_for),
            ("manage_claude_statusline.state_root_for", statusline.state_root_for),
        )

    def test_every_state_root_replacement_equals_the_retiring_original(self) -> None:
        for environment in ({}, {"XDG_STATE_HOME": "/xdg/state"}, {"XDG_STATE_HOME": "~/xdg"}):
            for home in self.HOMES:
                with mock.patch.dict("os.environ", environment, clear=False) as _patched:
                    if "XDG_STATE_HOME" not in environment:
                        _patched.pop("XDG_STATE_HOME", None)
                    expected = operator_tools.state_root_for(home)
                    for label, replacement in self.replacements():
                        with self.subTest(label=label, home=str(home), env=environment):
                            self.assertEqual(replacement(home), expected)

    def test_the_statusline_takes_no_bin_directory_at_all(self) -> None:
        """The retired half of the D1 equality pair, asserted as the absence D2 created.

        `default_bin_dir` was the one replacement scheduled to LEAVE rather than survive, because
        the command path now comes from the ledger row and no bin directory participates. Both the
        helper and the `--bin-dir` option are gone, and an operator who passes it gets argparse's
        own exit-2 refusal rather than a silently ignored value.
        """
        self.assertFalse(hasattr(statusline, "default_bin_dir"))
        self.assertTrue(hasattr(operator_tools, "default_bin_dir"), "positive control")
        self.assertNotIn("--bin-dir", (ROOT / "scripts" / "manage_claude_statusline.py").read_text(encoding="utf-8"))

    def test_the_equality_check_can_fail(self) -> None:
        """Positive control: the comparison above is not comparing a value to itself."""
        with mock.patch.dict("os.environ", {"XDG_STATE_HOME": "/xdg/state"}, clear=False):
            self.assertNotEqual(
                reader.state_root_for(Path("/home/fixture")),
                operator_tools.state_root_for(Path("/home/other")) / "elsewhere",
            )

    def test_the_absolute_replacement_equals_the_retiring_original(self) -> None:
        """`install_skill_bundle.operational_path` is what replaced `install_operator_tools.absolute`."""
        bundle = _load("import_freedom_bundle", ROOT / "scripts" / "install_skill_bundle.py")
        for candidate in (*self.HOMES, Path("/a/../b"), Path("./c")):
            with self.subTest(path=str(candidate)):
                self.assertEqual(
                    bundle.operational_path(candidate), operator_tools.absolute(candidate)
                )


if __name__ == "__main__":
    unittest.main()
