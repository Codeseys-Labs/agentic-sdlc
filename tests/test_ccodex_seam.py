#!/usr/bin/env python3
"""The subprocess seam of the committed ``bin/ccodex``, and the lever that keeps it honest.

``tests/seam_harness.py`` carries the mechanics and the case inventory; this module drives it and
owns the three questions a harness has to answer about itself:

  1. **Does the inventory still cover the grammar?**  ``SeamInventoryTest`` reads the reader's own
     closed verb vocabulary and fails when a verb has no case, so a grammar that grows outruns its
     seam coverage loudly instead of silently.  It also refuses a case that asserts no output, and
     requires every route-insensitive case to state WHY it survives the mutation.
  2. **Does every case hold on the intact tree?**  ``SeamCasesTest``.
  3. **Would every case notice the regression it exists for?**  ``RouteRegressionLeverTest`` restores
     the v0.7.4 route from the tracked mutation patch onto a fixture root over this checkout's own
     scripts and policy, then requires each route-sensitive case to FAIL naming one of the release
     workflow's own markers, and each declared control to keep passing.  A case that cannot go red
     there is not a seam case; it is decoration.

WHAT THIS DOES NOT COVER, DELIBERATELY.  ``tests/test_bin_ccodex.py`` owns the same dispatcher as it
arrives from a BUILT ARCHIVE -- the archive's mode bits, the tool-free ``version``/``--help`` verbs,
the missing-mise refusal, and the trust boundary against REAL mise.  ``scripts/smoke_release.py``
plus ``policy/release-smoke.v1.json`` own the EXTRACTED artifact and the per-platform refusal texts.
The in-process suites (``tests/test_ccodex_sdlc*.py``) own the reader's grammar, its report schema,
and each lifecycle module's refusal ladder, and their dispatcher is the RENDERED operator-tools
launcher, which is why the mutation patch to ``bin/ccodex`` leaves them green.  This module's
distinctive subject is the committed ``bin/ccodex`` in the tree it sits in, across the whole ``sdlc``
grammar.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

HARNESS_PATH = Path(__file__).resolve().parent / "seam_harness.py"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


harness = _load(HARNESS_PATH, "ccodex_seam_harness")
reader = _load(harness.ROOT / "scripts" / "ccodex_sdlc.py", "ccodex_sdlc_for_seam_test")

EXECUTION_SKIPS = (
    unittest.skipIf(os.name == "nt", harness.DISPATCHER_IS_POSIX_SHELL_SKIP_REASON),
    unittest.skipUnless(harness.EXECUTABLE_BIT_IS_HONORED, harness.EXECUTABLE_BIT_SKIP_REASON),
    unittest.skipUnless(sys.version_info[:3] == (3, 12, 11), harness.PINNED_INTERPRETER_SKIP_REASON),
)


def executing(cls: type) -> type:
    for decorator in EXECUTION_SKIPS:
        cls = decorator(cls)
    return cls


class SeamInventoryTest(unittest.TestCase):
    """The inventory's own shape. No subprocess, so it runs on every platform the suite reaches."""

    def test_every_case_id_is_a_unique_lowercase_slug(self) -> None:
        identifiers = [case.identifier for case in harness.SEAM_CASES]
        self.assertEqual(len(identifiers), len(set(identifiers)), "duplicate seam case id")
        for identifier in identifiers:
            with self.subTest(case=identifier):
                self.assertRegex(identifier, r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")

    def test_every_case_asserts_output_and_not_merely_an_exit_code(self) -> None:
        """The methodological rule: exit 3 is a legitimate status, so only the body separates
        "refused because this host has no activation" from "refused because the route regressed"."""
        for case in harness.SEAM_CASES:
            with self.subTest(case=case.identifier):
                self.assertGreater(case.assertions_declared, 0)

    def test_the_mutation_classification_is_declared_for_every_case(self) -> None:
        sensitive = [case for case in harness.SEAM_CASES if case.route_sensitive]
        controls = [case for case in harness.SEAM_CASES if not case.route_sensitive]
        # Both halves must exist: a suite with no sensitive case proves nothing about the route, and
        # one with no control cannot tell a scoped regression from a broken fixture.
        self.assertTrue(sensitive)
        self.assertTrue(controls)
        for case in controls:
            with self.subTest(case=case.identifier):
                self.assertTrue(
                    len(case.insensitivity_reason) > 40,
                    "a case that survives the route regression must state why, at length",
                )
        for case in sensitive:
            with self.subTest(case=case.identifier):
                self.assertEqual(case.insensitivity_reason, "")

    def test_the_inventory_covers_every_verb_in_the_readers_closed_grammar(self) -> None:
        """Read the vocabulary from the product, never from a second list here that could drift."""
        argv_by_case = {case.identifier: case.argv for case in harness.SEAM_CASES}
        vectors = list(argv_by_case.values())
        for verb in reader.READER_VERBS:
            with self.subTest(verb=verb, form="json"):
                self.assertTrue(
                    any(vector[:2] == ("sdlc", verb) and "--json" in vector for vector in vectors),
                    f"no seam case renders `sdlc {verb} --json`",
                )
            with self.subTest(verb=verb, form="human"):
                self.assertTrue(
                    any(
                        vector[:2] == ("sdlc", verb) and "--json" not in vector for vector in vectors
                    ),
                    f"no seam case renders `sdlc {verb}` in its human form",
                )
        for verb in reader.LIFECYCLE_VERBS:
            with self.subTest(verb=verb):
                self.assertTrue(
                    any(vector[:2] == ("sdlc", verb) for vector in vectors),
                    f"no seam case drives the mutating verb `sdlc {verb}`",
                )
        self.assertTrue(
            any(
                vector[:2] == ("sdlc", "recover") and reader.RECOVER_APPLY_FLAG in vector
                for vector in vectors
            ),
            "no seam case drives the one mutating recover form",
        )

    def test_every_lifecycle_refusal_fragment_is_a_literal_in_its_own_module(self) -> None:
        """A reworded refusal must fail here, not silently weaken the case to nothing.

        ``stderr_present_any`` is an alternation across platforms, so an assertion whose fragments no
        longer appear anywhere would keep passing on the platform that still matched -- or, worse,
        pass vacuously once every fragment rotted, because the case would then be red for a reason
        nobody attributed to a rename.
        """
        for verb, fragments in harness.LIFECYCLE_OWN_REASON.items():
            source = (harness.ROOT / "scripts" / harness.LIFECYCLE_REASON_SOURCES[verb]).read_text(
                encoding="utf-8"
            )
            for fragment in fragments:
                with self.subTest(verb=verb, fragment=fragment):
                    self.assertIn(fragment, source)

    def test_the_lever_applies_the_same_patch_the_release_gate_applies(self) -> None:
        self.assertTrue(harness.MUTATION_PATCH.is_file())
        workflow = (harness.ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn(harness.MUTATION_PATCH.relative_to(harness.ROOT).as_posix(), workflow)
        for marker in harness.ROUTE_REGRESSION_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)


@executing
class SeamCasesTest(unittest.TestCase):
    """Every declared case, driven through the committed dispatcher in this tree."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="ccodex-seam-")
        cls.runner = harness.SeamRunner(Path(cls._temporary.name))
        cls.observations = {case.identifier: cls.runner.run(case) for case in harness.SEAM_CASES}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_every_declared_observation_holds_on_the_intact_tree(self) -> None:
        for case in harness.SEAM_CASES:
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                failures = harness.assess(observation)
                self.assertEqual(failures, [], f"{failures}\n{observation.transcript}")

    def test_the_sdlc_route_resolves_the_managed_interpreter_and_never_the_shared_uv_runner(
        self,
    ) -> None:
        """The route readout, generalized from one verb to the whole grammar.

        ``tests/test_bin_ccodex.py`` pins the exact resolution argv for one verb on a built archive.
        What is asserted here is the property across every case: no invocation of the ``sdlc`` family
        ever asked ``uv run --script`` to run the reader, and each one that reached a route resolved
        the managed interpreter exactly once.
        """
        for case in harness.SEAM_CASES:
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                reader_through_uv_run = [
                    line
                    for line in observation.mise_argv
                    if "uv run" in line and "ccodex_sdlc.py" in line
                ]
                self.assertEqual(
                    reader_through_uv_run,
                    [],
                    "the sdlc route reached the shared uv runner, which the reader refuses by name",
                )
                if case.argv[0] == "sdlc" and case.mise == "trusted":
                    self.assertEqual(
                        observation.mise_argv,
                        (
                            f"-C {self.runner.root} tasks",
                            f"-C {self.runner.root} exec -- uv python find --managed-python 3.12.11",
                        ),
                        observation.transcript,
                    )

    def test_a_refused_toolchain_probe_resolves_no_interpreter_at_all(self) -> None:
        """Positive control for the case above: the untrusted and unreadable arms stop at the probe."""
        for case in harness.SEAM_CASES:
            if case.mise == "trusted":
                continue
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                self.assertEqual(
                    observation.mise_argv, (f"-C {self.runner.root} tasks",), observation.transcript
                )

    def test_no_sdlc_invocation_creates_rewrites_or_removes_a_byte_of_the_fixture(self) -> None:
        """The other half of "receipt bytes out": what the plane looks like AFTER the invocation.

        Every case is covered, reader and mutating verb alike -- a pre-effect refusal that wrote
        something would be a false refusal, and the planted-state cases additionally prove the
        document the report describes was read rather than repaired or rewritten.
        """
        for case in harness.SEAM_CASES:
            if case.argv[0] != "sdlc":
                continue
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                self.assertEqual(observation.effect, (), observation.transcript)

    def test_the_effect_detector_itself_reports_a_planted_change(self) -> None:
        """Positive control for the test above: the detector is not structurally silent.

        Without this, "no effect observed" could mean the comparison never looked at anything.  The
        probe drives a case whose fixture is deliberately mutated by a verb this harness controls --
        ``bundle status`` is read-only too, so the change is planted by the case's own state writer
        and then observed as a rewrite of a file that already existed.
        """
        cell = Path(self._temporary.name) / "detector-control"
        state = cell / "state"
        home = cell / "home"
        state.mkdir(parents=True)
        home.mkdir(parents=True)
        document = harness.write_operator_tools_pending(state, home)
        before = harness.SeamRunner.inventory(cell)
        self.assertIn("state/agentic-sdlc-operator-tools/state.json", before)
        document.write_text(
            document.read_text(encoding="utf-8").replace('"install"', '"uninstall"'),
            encoding="utf-8",
            newline="\n",
        )
        after = harness.SeamRunner.inventory(cell)
        self.assertEqual(set(before), set(after))
        self.assertNotEqual(
            before["state/agentic-sdlc-operator-tools/state.json"],
            after["state/agentic-sdlc-operator-tools/state.json"],
        )


@executing
@unittest.skipUnless(shutil.which("git"), "git is required to apply the tracked mutation patch")
class RouteRegressionLeverTest(unittest.TestCase):
    """Restore the v0.7.4 route and require the seam to notice.

    This is the wave's acceptance check, executed on every gate rather than demonstrated once: the
    tracked patch is applied to a copy of ``bin/ccodex`` standing over this checkout's own scripts
    and policy, so the reader that refuses is the real one and the refusal is its own.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="ccodex-seam-regressed-")
        base = Path(cls._temporary.name)
        cls.tree = harness.build_regressed_tree(base / "tree")
        cls.runner = harness.SeamRunner(base / "scratch", root=cls.tree)
        cls.observations = {case.identifier: cls.runner.run(case) for case in harness.SEAM_CASES}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_the_fixture_really_carries_the_v074_route(self) -> None:
        route = (self.tree / "bin" / "ccodex").read_text(encoding="utf-8").split("  sdlc)", 1)[1]
        route = route.split(";;", 1)[0]
        self.assertIn('run_python ccodex_sdlc.py "$@"', route)
        self.assertNotIn("run_sdlc_python", route)

    def test_every_route_sensitive_case_goes_red_naming_the_release_gates_own_marker(self) -> None:
        for case in harness.SEAM_CASES:
            if not case.route_sensitive:
                continue
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                failures = harness.assess(observation)
                self.assertNotEqual(
                    failures,
                    [],
                    "this case passed with the v0.7.4 route restored, so it proves nothing about the"
                    f" route and must be fixed or deleted\n{observation.transcript}",
                )
                named = [
                    marker
                    for marker in harness.ROUTE_REGRESSION_MARKERS
                    if marker in observation.evidence
                ]
                self.assertNotEqual(
                    named,
                    [],
                    "the case failed, but for a reason the route regression cannot be attributed to"
                    f"\n{observation.transcript}",
                )

    def test_every_declared_control_still_passes_with_the_route_regressed(self) -> None:
        """Without this, a fixture that broke everything would read as a working lever."""
        for case in harness.SEAM_CASES:
            if case.route_sensitive:
                continue
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                self.assertEqual(
                    harness.assess(observation), [], observation.transcript
                )

    def test_the_regressed_sdlc_route_really_reached_the_shared_uv_runner(self) -> None:
        """The mechanism, not just the symptom: the argv the dispatcher built is the v0.7.4 one."""
        witnessed = 0
        for case in harness.SEAM_CASES:
            if case.argv[0] != "sdlc" or case.mise != "trusted":
                continue
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                self.assertEqual(
                    observation.mise_argv,
                    (
                        f"-C {self.tree} tasks",
                        f"-C {self.tree} exec -- uv run --python 3.12.11 --script"
                        f" {self.tree}/scripts/ccodex_sdlc.py {' '.join(case.argv[1:])}".rstrip(),
                    ),
                    observation.transcript,
                )
                witnessed += 1
        self.assertGreater(witnessed, 0, "no sdlc case was observed on the regressed route")

    def test_the_regressed_reader_refuses_by_name_rather_than_crashing(self) -> None:
        """Every regressed reader verb renders a REPORT that names the refusal, never a traceback."""
        witnessed = 0
        for case in harness.SEAM_CASES:
            # The admitted reader verbs only: `--help` is answered by the parser before any runtime
            # admission (it is a declared control), and the mutating verbs render no report at all.
            if not case.route_sensitive or case.expect_exit != 0 or case.stdout_empty:
                continue
            observation = self.observations[case.identifier]
            witnessed += 1
            with self.subTest(case=case.identifier):
                self.assertEqual(observation.returncode, 3, observation.transcript)
                self.assertNotIn("Traceback", observation.evidence)
                self.assertIn("runtime-admission-refused", observation.stdout)
                self.assertIn("expected direct -I -B execution", observation.stdout)
        self.assertEqual(
            witnessed,
            len(reader.READER_VERBS) * 2 + 2,
            "the reader-verb selection drifted from the inventory: four verbs in both render forms,"
            " plus the two planted-state cases",
        )


if __name__ == "__main__":
    unittest.main()
