"""The keepers take NOTHING from the deleted operator-tools plane, and their derivations still agree.

`scripts/install_operator_tools.py` was the PATH plane and also a live library to three modules that
outlive it. This suite was the ratchet on that coupling: every name each keeper still took was
declared with the wave that removed it, compared for EXACT equality, so a re-introduced helper failed
here and so did a name the demolition removed without updating the list.

gh #10 PHASE 4 EMPTIED IT. The plane is deleted, so the ratchet's end state is reached: all three
declarations are the empty dict, which under this suite's exact-equality rule is a literal
import-zero claim rather than an absence of interest. What that claim now defends is the reverse
direction from the one it was built for -- not "no new coupling to a retiring module" but "no
resurrection of a module that is gone" -- and it is still a live claim, because the adapter name is
read off the SOURCE rather than off an import hook, so a `ModuleType` parameter or a guarded
`load_sibling` would be seen exactly as a top-level import is.

THE ORACLE LEFT, SO THE EQUALITY CLAIM WAS RE-ANCHORED (D1's recorded note, executed while
`install_operator_tools.state_root_for` still existed) AND THEN RE-ANCHORED AGAIN, onto a real one.
D1 pinned its replacement derivations equal to that original; the original is gone, and the three
survivors pinned only against EACH OTHER was a claim a family that was uniformly wrong could satisfy
-- which it was. All three carried the POSIX branch alone, so on Windows they resolved
`<home>/.local/state` while `install_skill_bundle.state_directory()`, the value this bundle actually
writes its ownership ledger under, resolved `LOCALAPPDATA` (seed agentic-sdlc-4689). The rule now has
ONE owner, `install_skill_bundle.state_root_for(home)`, of which `state_directory()` is the
process-home specialization; `manage_claude_statusline` delegates to it and `ccodex_sdlc_recover`
deleted its copy outright. What is asserted here is the surviving distance: the reader keeps one
re-expression, because it resolves the store roster on the runtime-admission-refused path where that
substrate is deliberately not loaded, so its agreement is a test rather than an import. The matrix is
D1's inputs widened by the LOCALAPPDATA rows and run under BOTH mocked platforms, with a positive
control that the mocked platform really moves the answer -- without it, every equality here would pass
by comparing two identical POSIX results.
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
# plane's -- D2 replaced it -- so the line outlives the plane rather than retiring with it.
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reader = _load("import_freedom_reader", ROOT / "scripts" / "ccodex_sdlc.py")
recover = _load("import_freedom_recover", ROOT / "scripts" / "ccodex_sdlc_recover.py")
statusline = _load("import_freedom_statusline", ROOT / "scripts" / "manage_claude_statusline.py")
#: The AUTHORITY for the state-root rule since seed agentic-sdlc-4689, reached through the keeper that
#: imports it rather than loaded a second time. That identity is the point: the rule reads a
#: `platform_system` seam, and a second module OBJECT of the same file carries a second seam, so mocking
#: one and comparing against the other would fail on the mock rather than on the rule. One object means
#: one seam, and the statusline row below then tests the DELEGATION -- a re-introduced local copy there
#: stops tracking the mocked platform and fails.
bundle = statusline.installer
#: The one owner of "an absolute path a fixture may name on any host". `Path("/a/../b")` is absolute on
#: POSIX only, and comparing it against a lexically collapsed result is what broke below on Windows.
platform_paths = _load("import_freedom_platform_paths", ROOT / "tests" / "support" / "platform_paths.py")


#: The module attribute every keeper reached `install_operator_tools` through, whether it arrived as
#: a top-level `import ... as`, a guarded `load_sibling`, or a `ModuleType` parameter. Reading the
#: coupling off the SOURCE rather than off an import hook is what lets this suite see a name a code
#: path only reaches at run time on an interrupted host.
ADAPTER_NAME = "operator_tools"

#: The plane's own module file. Its ABSENCE is the claim the declarations below rest on: an empty
#: allowlist against a module that still existed would be satisfiable by a keeper that simply had not
#: imported it yet, and that is a weaker fact than the one this suite now states.
PLANE_MODULE = ROOT / "scripts" / "install_operator_tools.py"

#: The two names gh #10 phase 1 moved off the plane, kept as a named set because a resurrection is
#: most likely to arrive as one of these two -- they are the derivations the keepers actually needed.
FREED_NAMES = ("absolute", "state_root_for")

#: Every `install_operator_tools` name each keeper takes. Empty everywhere: the plane is deleted, so
#: any name at all is a resurrection.
RETAINED: dict[str, dict[str, str]] = {
    "scripts/ccodex_sdlc.py": {},
    "scripts/ccodex_sdlc_recover.py": {},
    "scripts/manage_claude_statusline.py": {},
}


def taken_names(source: Path) -> set[str]:
    """Every attribute the source reads off its `install_operator_tools` adapter.

    An `ast.Attribute` on `ast.Name(ADAPTER_NAME)` and nothing else: the report field spelled
    `operator_tools["state"]` was a subscript, so a closed report vocabulary could not leak in here
    and read as a library coupling.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == ADAPTER_NAME
    }


def executable_strings_from_source(source: str) -> set[str]:
    """Every module name and string literal the source EXECUTES, with docstrings removed.

    A docstring is an `ast.Expr` whose value is a string `Constant` at the head of a module, class, or
    function body, so those exact nodes are subtracted by identity rather than by value -- subtracting
    by value would also drop a real argument that happened to read like a docstring.
    """
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            found.add(node.value)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def executable_strings(source: Path) -> set[str]:
    return executable_strings_from_source(source.read_text(encoding="utf-8"))


class ImportFreedomTests(unittest.TestCase):
    """The declared coupling is the whole coupling, in both directions."""

    def test_the_plane_module_is_gone(self) -> None:
        """The premise. Without it every assertion below is about a module that could come back."""
        self.assertFalse(PLANE_MODULE.exists(), PLANE_MODULE)
        # Positive control that the path is the real one and not a typo that trivially does not
        # exist: its surviving sibling, named the same way, is there.
        self.assertTrue((ROOT / "scripts" / "install_skill_bundle.py").is_file())

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

    def test_no_keeper_names_the_deleted_module_in_executable_source(self) -> None:
        """A different failure from the one the attribute scan catches, and a narrower one than grep.

        `taken_names` sees attribute reads off an adapter already in hand; it cannot see a keeper that
        ASKS for the module -- `guard.load_sibling(path, "install_operator_tools")` passes the stem as
        a STRING, and `import install_operator_tools` never touches the adapter name at all. Both are
        forbidden here, over the executable source only: DOCSTRINGS are excluded on purpose, because a
        module deleted for a reason should be nameable in prose that records the reason, and a check
        that forbade that would be answered by deleting the explanation.
        """
        for relative in RETAINED:
            with self.subTest(module=relative):
                # Tested as a boolean: the set holds every string literal in the module, and an
                # `assertNotIn` diff would print all of them instead of the one fact wanted.
                self.assertTrue(
                    "install_operator_tools" not in executable_strings(ROOT / relative),
                    f"{relative} names the deleted plane in executable source",
                )

    def test_the_forbidden_string_check_reads_a_string_that_is_really_there(self) -> None:
        """Positive control for the exclusion: a docstring is skipped, a real argument is not."""
        excluded = executable_strings_from_source(
            '"""install_operator_tools is deleted."""\nvalue = 1\n'
        )
        self.assertEqual(excluded, set())
        included = executable_strings_from_source(
            '"""prose."""\nimport install_operator_tools\nload("install_operator_tools")\n'
        )
        self.assertEqual(included, {"install_operator_tools"})

    def test_the_scanner_sees_a_name_that_is_really_there(self) -> None:
        """Positive control: `taken_names` is not structurally blind.

        Every assertion above is an absence, so one presence is read off real source -- synthesised
        source, since no keeper carries the coupling any more. This is the same lever
        `test_the_scanner_reports_a_reintroduced_helper` runs, isolated to the scanner itself.
        """
        planted = "operator_tools = None\nvalue = operator_tools.state_root_for(home)\n"
        tree = ast.parse(planted)
        taken = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == ADAPTER_NAME
        }
        self.assertEqual(taken, {"state_root_for"})

    def test_the_scanner_reports_a_reintroduced_helper(self) -> None:
        """The mutation the ratchet exists to catch, run against synthesised keeper source.

        Re-introducing `operator_tools.state_root_for` into a real keeper must show up as a taken
        name, so the exact-equality test above fails on it. Synthesised rather than planted in the
        tree so the lever runs on every gate instead of only when someone edits a module by hand.
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


class ReplacementDerivationTests(unittest.TestCase):
    """Every spelling of one state-root rule resolves one path per host, on BOTH platforms.

    THE AUTHORITY IS `install_skill_bundle.state_root_for` (seed agentic-sdlc-4689), and it is where
    the rule lives because `AGENTS.md` states it as this bundle's own -- `XDG_STATE_HOME` on Unix,
    `LOCALAPPDATA` on Windows. `state_directory()` is that function applied to the process home, so a
    consumer handed a home and a consumer reading the environment cannot land under two roots.
    """

    HOMES = (
        Path("/home/fixture"),
        Path("/home/fixture/nested"),
        Path("~/fixture"),
        Path("relative-home"),
    )
    #: Every environment shape that selects a different branch of the rule, per platform. The
    #: LOCALAPPDATA-absent row is the one that makes the home a parameter on Windows at all: with the
    #: variable set, the rule ignores the home entirely.
    ENVIRONMENTS = (
        {},
        {"XDG_STATE_HOME": "/xdg/state"},
        {"XDG_STATE_HOME": "~/xdg"},
        {"LOCALAPPDATA": "/local/app/data"},
        {"XDG_STATE_HOME": "/xdg/state", "LOCALAPPDATA": "/local/app/data"},
    )
    _CLEARED = ("XDG_STATE_HOME", "LOCALAPPDATA")

    def replacements(self):
        return (
            ("ccodex_sdlc.state_root_for", reader.state_root_for),
            ("manage_claude_statusline.state_root_for", statusline.state_root_for),
        )

    def environments(self, system: str):
        """Each environment shape with the host platform forced to `system`.

        PATCHED AT THE STDLIB, not at a module seam, because there is exactly ONE predicate to move:
        the authority reads it through `install_skill_bundle.platform_system` and the reader's one
        surviving re-expression calls `platform.system()` directly, so `platform.system` is where the
        two meet. Patching either module's own name would move one side and leave the other on the real
        host, and the comparison would then fail on the mock rather than on the rule.
        """
        for environment in self.ENVIRONMENTS:
            with mock.patch.dict("os.environ", environment, clear=False) as patched:
                for name in self._CLEARED:
                    if name not in environment:
                        patched.pop(name, None)
                with mock.patch("platform.system", return_value=system):
                    yield environment

    def test_every_state_root_spelling_agrees_with_the_authority(self) -> None:
        """Anchored on the authority, across both platforms and every branch of the rule.

        The reader renders the plan digest and `ccodex_sdlc_recover` re-derives it at apply time
        through this same authority. If two spellings resolved different state roots they would read
        different journals and derive different digests for one host, and `--apply` would refuse every
        approval the reader ever printed. On Windows they ALSO used to split the report itself: the
        ownership ledger under `LOCALAPPDATA`, the acquisition and activation planes under
        `<home>/.local/state`.
        """
        for system in ("Linux", "Windows"):
            for environment in self.environments(system):
                for home in self.HOMES:
                    expected = bundle.state_root_for(home)
                    for label, replacement in self.replacements():
                        with self.subTest(
                            label=label, system=system, home=str(home), env=environment
                        ):
                            self.assertEqual(replacement(home), expected)

    def test_the_authority_and_its_process_home_specialization_agree(self) -> None:
        """`state_directory()` is `state_root_for(Path.home())` and every keeper matches it.

        THE AXIS THE DIVERGENCE NEEDED (seed agentic-sdlc-4689). The equality above pins the
        home-parameterized spellings against each other, which a family that was uniformly wrong about
        Windows would satisfy. This one compares them against the zero-argument function the installer
        actually writes its ownership ledger under, which is the value `AGENTS.md` documents.
        """
        for system in ("Linux", "Windows"):
            for environment in self.environments(system):
                home = bundle.operational_path(Path.home())
                directory = bundle.state_directory()
                with self.subTest(system=system, env=environment, side="authority"):
                    self.assertEqual(bundle.state_root_for(home), directory)
                for label, replacement in self.replacements():
                    with self.subTest(label=label, system=system, env=environment):
                        self.assertEqual(replacement(home), directory)

    def test_the_windows_branch_is_really_reached(self) -> None:
        """Positive control for both tests above: the mocked platform MOVES the answer.

        Without this, a platform predicate the equality tests failed to reach -- or a rule that had no
        Windows branch at all -- would make every assertion above pass by comparing two identical POSIX
        answers. So the same home and the same environment must resolve to two DIFFERENT roots under the
        two systems, and the Windows one must be the `LOCALAPPDATA` value.
        """
        home = Path("/home/fixture")
        resolved: dict[str, Path] = {}
        for system in ("Linux", "Windows"):
            with mock.patch.dict(
                "os.environ",
                {"XDG_STATE_HOME": "/xdg/state", "LOCALAPPDATA": "/local/app/data"},
                clear=False,
            ):
                with mock.patch("platform.system", return_value=system):
                    resolved[system] = bundle.state_root_for(home)
                    self.assertEqual(reader.state_root_for(home), resolved[system], system)
        self.assertNotEqual(resolved["Linux"], resolved["Windows"])
        self.assertEqual(
            resolved["Windows"], bundle.operational_path(Path("/local/app/data"))
        )
        self.assertEqual(resolved["Linux"], bundle.operational_path(Path("/xdg/state")))

    def test_the_authority_is_the_repository_module_and_not_a_stand_in(self) -> None:
        """The premise of every equality above: `bundle` really is `scripts/install_skill_bundle.py`."""
        self.assertEqual(
            Path(bundle.__file__).resolve(),
            (ROOT / "scripts" / "install_skill_bundle.py").resolve(),
        )
        # The authority's own platform seam, whose delegation down to `platform.system` is what the
        # stdlib patch in `environments` relies on to move BOTH sides of every equality.
        self.assertTrue(hasattr(bundle, "platform_system"))
        with mock.patch("platform.system", return_value="Plan9"):
            self.assertEqual(bundle.platform_system(), "Plan9")

    def test_the_recovery_plane_takes_the_authority_rather_than_a_copy(self) -> None:
        """`ccodex_sdlc_recover` has no state-root spelling of its own left to diverge.

        It is the one keeper that could delete its copy outright: the adapter it needs is already in
        hand at the single call site (`build_configs`), so the derivation is TAKEN from the substrate
        whose journal the plan describes instead of kept in step with it by hand. Asserted as an
        absence plus the delegation, because either alone is satisfiable by the other's regression.
        """
        self.assertFalse(hasattr(recover, "_state_root_for"))
        source = (ROOT / "scripts" / "ccodex_sdlc_recover.py").read_text(encoding="utf-8")
        self.assertIn("bundle.state_root_for(resolved_home)", source)
        # Positive control for both: the authority really carries the name being delegated to, and the
        # module really was read.
        self.assertTrue(callable(bundle.state_root_for))
        self.assertIn("def build_configs(", source)

    def test_the_statusline_takes_no_bin_directory_at_all(self) -> None:
        """The retired half of the D1 equality pair, asserted as the absence D2 created.

        `default_bin_dir` was the one replacement scheduled to LEAVE rather than survive, because the
        command path comes from the ledger row and no bin directory participates. Both the helper and
        the `--bin-dir` option are gone, and an operator who passes it gets argparse's own exit-2
        refusal rather than a silently ignored value.
        """
        self.assertFalse(hasattr(statusline, "default_bin_dir"))
        self.assertNotIn(
            "--bin-dir", (ROOT / "scripts" / "manage_claude_statusline.py").read_text(encoding="utf-8")
        )
        # Positive control for both absences: the module was really loaded and really read.
        self.assertTrue(hasattr(statusline, "state_root_for"))

    def test_the_equality_check_can_fail(self) -> None:
        """Positive control: the comparisons above are not comparing a value to itself."""
        with mock.patch.dict("os.environ", {"XDG_STATE_HOME": "/xdg/state"}, clear=False):
            self.assertNotEqual(
                reader.state_root_for(Path("/home/fixture")),
                bundle.state_root_for(Path("/home/other")) / "elsewhere",
            )

    def test_the_absolute_replacement_is_the_bundle_helper(self) -> None:
        """`install_skill_bundle.operational_path` is what replaced `install_operator_tools.absolute`.

        The retired original is gone, so what is pinned is the property D1's equality assertion was
        really about: every result is absolute, and `..` is collapsed LEXICALLY rather than by
        resolving the filesystem, which is what keeps a link in the path from being followed.

        THE COLLAPSE CASE IS BUILT FROM THE HOST'S ANCHOR. `Path("/a/../b")` is absolute on POSIX and
        not on Windows, so the helper completed it against the current drive and the equality compared
        `WindowsPath('C:/b')` against `WindowsPath('/b')` (main@818bf09, seed context
        `ci-red-818bf09`). The collapse is the subject; the anchor is not.
        """
        uncollapsed = platform_paths.absolute_fixture("a", "..", "b")
        for candidate in (*self.HOMES, uncollapsed, Path("./c")):
            with self.subTest(path=str(candidate)):
                resolved = bundle.operational_path(candidate)
                self.assertTrue(resolved.is_absolute(), resolved)
        self.assertEqual(bundle.operational_path(uncollapsed), platform_paths.absolute_fixture("b"))


if __name__ == "__main__":
    unittest.main()
