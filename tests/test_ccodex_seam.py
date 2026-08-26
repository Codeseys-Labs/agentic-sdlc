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
and each lifecycle module's refusal ladder.  Their dispatcher used to be the RENDERED operator-tools
launcher, which is why the mutation patch to ``bin/ccodex`` left them green; that launcher is deleted
(gh #10 phase 4), so they now reach the ONE committed dispatcher through this module's own recording
stub ``mise``.  This module's distinctive subject is still what it always was: the committed
``bin/ccodex`` in the tree it sits in, driven as a real process across the whole lifecycle grammar.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
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
            # `recover`'s render forms are its --dry-run pair; the --apply form is checked separately
            # below, because it renders no report at all.
            rendering = [
                vector
                for vector in vectors
                if vector[0] == verb and reader.RECOVER_APPLY_FLAG not in vector
            ]
            with self.subTest(verb=verb, form="json"):
                self.assertTrue(
                    any("--json" in vector for vector in rendering),
                    f"no seam case renders `ccodex {verb} --json`",
                )
            with self.subTest(verb=verb, form="human"):
                self.assertTrue(
                    any("--json" not in vector for vector in rendering),
                    f"no seam case renders `ccodex {verb}` in its human form",
                )
        for verb in reader.LIFECYCLE_VERBS:
            with self.subTest(verb=verb):
                self.assertTrue(
                    any(vector[0] == verb for vector in vectors),
                    f"no seam case drives the mutating verb `ccodex {verb}`",
                )
        self.assertTrue(
            any(
                vector[0] == "recover" and reader.RECOVER_APPLY_FLAG in vector
                for vector in vectors
            ),
            "no seam case drives the one mutating recover form",
        )
        # THE SELECTOR HALF OF THE GRAMMAR, read from the product's own vocabulary: every verb that
        # requires a plane selector must be driven with one, and both admitted agents must appear, or
        # a plane re-pinned shut would leave this suite green.
        for verb in reader.SELECTOR_VERBS:
            with self.subTest(verb=verb, form="selected"):
                self.assertTrue(
                    any(
                        vector[0] == verb and reader.AGENT_FLAG in vector
                        and reader.SCOPE_FLAG in vector
                        for vector in vectors
                    ),
                    f"no seam case drives `ccodex {verb}` with both required selectors",
                )
        for agent in reader.LIFECYCLE_AGENTS:
            with self.subTest(agent=agent):
                self.assertTrue(
                    any(
                        reader.AGENT_FLAG in vector
                        and vector[vector.index(reader.AGENT_FLAG) + 1] == agent
                        for vector in vectors
                    ),
                    f"no seam case selects the {agent} plane",
                )
        # EVERY SCOPE, on the same terms as every agent (agentic-sdlc-7a2b, W4). The axis was missing
        # while `project` was refused as unwired -- one case covered the whole scope because it was one
        # refusal -- and its absence would now let a wired scope ship with no case at all, which is the
        # gap this inventory exists to close for the verb axis.
        for scope in reader.LIFECYCLE_SCOPES:
            with self.subTest(scope=scope):
                self.assertTrue(
                    any(
                        reader.SCOPE_FLAG in vector
                        and vector[vector.index(reader.SCOPE_FLAG) + 1] == scope
                        for vector in vectors
                    ),
                    f"no seam case drives the {scope} scope",
                )
        # THE RETIRED SPELLINGS: both namespaces must be driven, or deleting a refusal arm would go
        # unnoticed by this inventory.
        for retired in ("bundle", "sdlc"):
            with self.subTest(retired=retired):
                self.assertTrue(
                    any(vector[0] == retired for vector in vectors),
                    f"no seam case drives the retired `ccodex {retired}` spelling",
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

    def test_the_lifecycle_route_resolves_the_managed_interpreter_and_never_the_shared_uv_runner(
        self,
    ) -> None:
        """The route readout, generalized from one verb to the whole grammar.

        ``tests/test_bin_ccodex.py`` pins the exact resolution argv for one verb on a built archive.
        What is asserted here is the property across every case: no lifecycle invocation
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
                    "the lifecycle route reached the shared uv runner, which the reader refuses by name",
                )
                if harness.is_lifecycle_route(case.argv) and case.mise == "trusted":
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

    def test_no_lifecycle_invocation_creates_rewrites_or_removes_a_byte_of_the_fixture(self) -> None:
        """The other half of "receipt bytes out": what the plane looks like AFTER the invocation.

        Every case is covered, reader and mutating verb alike -- a pre-effect refusal that wrote
        something would be a false refusal, and the planted-state cases additionally prove the
        document the report describes was read rather than repaired or rewritten.
        """
        for case in harness.SEAM_CASES:
            if not harness.is_lifecycle_route(case.argv):
                continue
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                self.assertEqual(observation.effect, (), observation.transcript)

    def test_a_retired_spelling_resolves_no_tool_at_all(self) -> None:
        """A refusal must not pay for a toolchain it will never use.

        Every retired-namespace arm and the unknown-command arm sit UPSTREAM of
        ``require_toolchain``, so a correct refusal leaves the stub's argv log untouched. Without this
        the arms could be moved below the preflight and nothing would notice: the message and the exit
        code would both still be right, while a fresh host paid a mise probe -- and, on an untrusted
        root, got a trust refusal instead of the migration text the operator needs.
        """
        witnessed = 0
        for case in harness.SEAM_CASES:
            if case.argv[0] not in ("bundle", "sdlc", "frobnicate", "--help"):
                continue
            observation = self.observations[case.identifier]
            witnessed += 1
            with self.subTest(case=case.identifier):
                self.assertEqual(observation.mise_argv, (), observation.transcript)
        self.assertGreater(witnessed, 0, "no retired-spelling case is in the inventory")

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
        document = harness.write_retired_operator_tools_store(state)
        relative = "state/agentic-sdlc-operator-tools/state.json"
        before = harness.SeamRunner.inventory(cell)
        self.assertIn(relative, before)
        document.write_text(
            document.read_text(encoding="utf-8").replace('"version": 2', '"version": 3'),
            encoding="utf-8",
            newline="\n",
        )
        after = harness.SeamRunner.inventory(cell)
        self.assertEqual(set(before), set(after))
        self.assertNotEqual(before[relative], after[relative])


@executing
class GatewayStatusRouteTest(unittest.TestCase):
    """`ccodex status` is the ONE name the gateway plane and the lifecycle share, and both survive.

    RESTORED, AND RE-ANCHORED. This claim had a test until gh #10 phase 4, which drove the rendered
    operator-tools launcher through an `AGENTIC_SDLC_ROOT` override; both are deleted. The committed
    dispatcher self-locates its root as the physical parent of its own `bin/`, so the way to observe
    the gateway route now is to STAND UP a root: a copy of `bin/ccodex` over a `scripts/` directory
    holding a recording stub launcher, with a stub `mise` rooted at that same tree. The real launcher
    is never executed here -- it would start a gateway process.

    What is asserted is the disambiguation in both directions, because only the pair is a control: a
    selector-free `status` still reaches the gateway verb, and a `status` carrying a lifecycle selector
    does not. Without the second half, moving `status` wholly onto either plane would keep one of the
    two tests green.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="ccodex-seam-gateway-")
        base = Path(cls._temporary.name)
        cls.tree = harness.build_stub_launcher_tree(base / "tree")
        cls.utilities = harness.dispatcher_utilities_path(base / "utilities")
        cls.home = base / "home"
        cls.stub_bin = base / "stub-bin"
        cls.work = base / "cwd"
        for directory in (cls.home, cls.stub_bin, cls.work):
            directory.mkdir(parents=True)
        harness.write_stub_mise(
            cls.stub_bin,
            root=cls.tree,
            interpreter=Path(sys.executable),
            log=base / "mise-argv.log",
            probe="trusted",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def run_dispatcher(self, *argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.tree / "bin" / "ccodex"), *argv],
            env={
                "PATH": os.pathsep.join([str(self.stub_bin), str(self.utilities)]),
                "HOME": str(self.home),
                "XDG_STATE_HOME": str(self.home / "state"),
                "LANG": "C",
                "LC_ALL": "C",
            },
            cwd=str(self.work),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_top_level_gateway_status_route_remains_the_gateway_route(self) -> None:
        completed = self.run_dispatcher("status")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"{harness.GATEWAY_STUB_MARKER}status", completed.stdout)

    def test_gateway_status_forwards_its_own_arguments_verbatim(self) -> None:
        """A non-selector argument is the gateway's, and it must arrive unchanged rather than be
        re-read as a lifecycle flag the dispatcher does not recognise."""
        completed = self.run_dispatcher("status", "--verbose")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"{harness.GATEWAY_STUB_MARKER}status", completed.stdout)
        self.assertIn("GATEWAY-ARGV:--verbose", completed.stdout)

    def test_a_lifecycle_selector_takes_status_off_the_gateway_route(self) -> None:
        """The other half of the pair. This tree has no reader, so a lifecycle-routed `status` cannot
        reach one -- which is exactly the observation: the dispatcher declined to hand it to the
        launcher, and said so by name instead of forwarding `--scope` to the gateway."""
        completed = self.run_dispatcher("status", "--scope", "user", "--agent", "claude")

        self.assertNotIn(harness.GATEWAY_STUB_MARKER, completed.stdout)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        self.assertIn("lifecycle entry is unavailable in this distribution", completed.stderr)

    def test_the_other_gateway_short_forms_are_untouched_by_the_verb_table(self) -> None:
        for verb, forwarded in (("ensure", "ensure"), ("restart", "restart"), ("ultracode", "launch-ultracode")):
            with self.subTest(verb=verb):
                completed = self.run_dispatcher(verb)

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn(f"{harness.GATEWAY_STUB_MARKER}{forwarded}", completed.stdout)


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
        """BOTH call sites, not one. The verb table reaches `run_sdlc_python` from the six-verb arm and
        from `status`'s selector branch, so a patch that mutated only one would let some smoke and seam
        cases take the FIXED route and report green on a regressed tree."""
        mutated = (self.tree / "bin" / "ccodex").read_text(encoding="utf-8")
        self.assertEqual(mutated.count('run_python ccodex_sdlc.py "$@"'), 2)
        self.assertEqual(mutated.count('run_sdlc_python "$@"'), 0)
        # The intact tree is the positive control: the same two call sites, spelled the other way.
        intact = harness.BIN_CCODEX.read_text(encoding="utf-8")
        self.assertEqual(intact.count('run_sdlc_python "$@"'), 2)
        self.assertEqual(intact.count('run_python ccodex_sdlc.py "$@"'), 0)

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

    def test_the_regressed_lifecycle_route_really_reached_the_shared_uv_runner(self) -> None:
        """The mechanism, not just the symptom: the argv the dispatcher built is the v0.7.4 one."""
        witnessed = 0
        for case in harness.SEAM_CASES:
            if not harness.is_lifecycle_route(case.argv) or case.mise != "trusted":
                continue
            observation = self.observations[case.identifier]
            with self.subTest(case=case.identifier):
                self.assertEqual(
                    observation.mise_argv,
                    (
                        f"-C {self.tree} tasks",
                        f"-C {self.tree} exec -- uv run --python 3.12.11 --script"
                        f" {self.tree}/scripts/ccodex_sdlc.py {' '.join(case.argv)}".rstrip(),
                    ),
                    observation.transcript,
                )
                witnessed += 1
        self.assertGreater(witnessed, 0, "no lifecycle case was observed on the regressed route")

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
            len(reader.READER_VERBS) * 2 + 3,
            "the reader-verb selection drifted from the inventory: three verbs in both render forms,"
            " plus the THREE planted-state cases (the armed bundle transition in both doctor and"
            " recover --dry-run, and the retired operator-tools store)",
        )


if __name__ == "__main__":
    unittest.main()
