"""The tag gate: the smoke manifest, its reader's verdicts, the workflow, and the mutation fixture.

Issue #9 is the subject. Two published prereleases shipped a ``ccodex sdlc`` plane that refused
itself at exit 3, and the reason nothing was red is the reason this module exists: the repository's
only artifact test was negative-only, so no assertion anywhere said a ``sdlc`` verb is ever
ADMITTED. Every positive here is paired with the mutation that must break it.

The reader's end-to-end verdicts run against a STUB ``bin/ccodex`` rather than a built archive: the
real-archive proof belongs to the workflow (and to ``tests/test_bin_ccodex.py``'s extract-and-run
fixture), while what needs proving HERE is that the verdict logic distinguishes an admitted report
from the v0.7.4 refusal, and that ``--expect-refusal`` cannot pass vacuously.

THE SPELLING MOVED, THE REGRESSION DID NOT (agentic-sdlc-7a2b W3a). ``ccodex sdlc <verb>`` and
``ccodex bundle <verb>`` are retired at exit 2, and the six lifecycle verbs are top-level, so every
argv here -- shipped manifest and stub fixture alike -- carries the new spelling. What v0.7.3 and
v0.7.4 shipped is unchanged history: the route they regressed is still ``run_sdlc_python``, still
refused by name by ``runtime_admission()``, and now reachable from TWO case arms rather than one,
which is what the mutation fixture had to be re-anchored onto.
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

import yaml


ROOT = Path(__file__).parents[1]
SMOKE_SCRIPT = ROOT / "scripts" / "smoke_release.py"
MANIFEST_PATH = ROOT / "policy" / "release-smoke.v1.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"
MUTATION_PATCH = ROOT / ".github" / "mutations" / "restore-v0.7.4-uv-run-sdlc-route.patch"
BIN_CCODEX = ROOT / "bin" / "ccodex"
VALIDATOR_PATH = ROOT / "scripts" / "validate_bundle.py"

#: The exact admission text ``runtime_admission()`` emits for a non-isolated interpreter, and the
#: finding code the report carries with it. Re-expressed here so a rename has to touch this suite.
ADMISSION_MARKER = "expected direct -I -B execution"
REFUSAL_FINDING = "runtime-admission-refused"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load(SMOKE_SCRIPT, "smoke_release_under_test")
validator = _load(VALIDATOR_PATH, "validate_bundle_for_release_smoke_test")
#: The READER's own verb vocabulary, not a copy of it. The manifest-coverage predicate below asks the
#: product which verbs render a report, so a fourth report-rendering verb added there without a smoke
#: case reddens `mise run check` instead of shipping uncovered. `inspect` LEFT this tuple when the
#: front door became six top-level verbs, and that deletion is exactly the kind of drift a
#: hand-written list here would have hidden in the other direction.
reader = _load(ROOT / "scripts" / "ccodex_sdlc.py", "ccodex_sdlc_for_release_smoke_test")

#: Whether the reader will select any case on this host, asked of the READER's own allowlist rather
#: than of `os.name`, so adding a platform there starts these running instead of leaving them
#: skipped. `smoke.PLATFORMS` is `("Darwin", "Linux")` and Windows is deliberately absent -- a case
#: naming it would claim coverage nobody observed (issue #9) -- and a manifest may name nothing
#: outside it, so on Windows every fixture manifest here selects zero cases and `main` refuses at
#: exit 3 before any verdict is computed. Measured on windows-2025 as six failures reading
#: `refused: no case in ...manifest.json is declared for Windows` (agentic-sdlc-5ce7). The verdict
#: logic itself is platform-independent; it is simply unreachable through this CLI there, and the
#: two sibling cases asserting a usage error still run because argument validation precedes the
#: platform gate.
SMOKE_SELECTS_A_CASE_HERE = platform.system() in smoke.PLATFORMS
NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON = (
    "the release smoke declares no case for this platform (smoke_release.PLATFORMS omits it by "
    "design, issue #9), so the reader refuses before reaching a verdict (agentic-sdlc-5ce7)"
)


def report(*, admitted: bool) -> str:
    """The two shapes that decide this gate: the admitted report, and the v0.7.4 refusal."""
    findings = (
        []
        if admitted
        else [
            {
                "code": REFUSAL_FINDING,
                "component": "runtime",
                "message": ADMISSION_MARKER,
                "path": "/somewhere/uv/environment/bin/python3",
            }
        ]
    )
    return json.dumps(
        {
            "checkout": {"plane": "checkout-development", "version": "0.7.5"},
            "command": {"dry_run": False, "verb": "status"},
            "findings": findings,
            "overall": {"exit_class": "ok" if admitted else "safe-refusal"},
            "runtime": {
                "interpreter": "/somewhere/bin/python3",
                "isolated": admitted,
                "state": "admitted" if admitted else "refused",
                "version": "3.12.11",
            },
        }
    )


class StubTree:
    """A directory shaped like an extracted archive, whose ``bin/ccodex`` is a canned responder.

    The canned bytes are written to SIBLING FILES and ``cat``-ed rather than interpolated into the
    script body. A ``printf`` whose argument is a double-quoted literal lets bash expand a backtick or
    a ``$(...)`` inside it, and these payloads are real product output: `libraries list` prints
    ``  `lifecycle:install` `` among other backticked names, so the interpolating form answered with
    something the product never printed AND ran the quoted words as commands on the host. Neither is
    acceptable in a fixture whose whole job is to reproduce an artifact's stdout faithfully.
    """

    def __init__(self, base: Path, *, stdout: str = "", stderr: str = "", exit_code: int = 0):
        self.root = base / "agentic-sdlc-stub"
        (self.root / "bin").mkdir(parents=True)
        canned_stdout = self.root / "canned-stdout"
        canned_stderr = self.root / "canned-stderr"
        canned_stdout.write_text(stdout, encoding="utf-8")
        canned_stderr.write_text(stderr, encoding="utf-8")
        dispatcher = self.root / "bin" / "ccodex"
        dispatcher.write_text(
            "#!/usr/bin/env bash\n"
            f"cat {shlex.quote(str(canned_stdout))}\n"
            f"cat {shlex.quote(str(canned_stderr))} >&2\n"
            f"exit {exit_code}\n",
            encoding="utf-8",
        )
        dispatcher.chmod(0o755)


#: A 64-hex acquisition receipt name, the only shape `acquisition_receipt_names` admits.
SEEDED_ARCHIVE_SHA256 = "b" * 64


class AcquisitionSensitiveTree:
    """A stub ``bin/ccodex`` that answers from the ACQUISITION PLANES its environment points at.

    The canned-output stub cannot test an environment mode, because its answer is a file. This one
    re-expresses the shipped installer's own two-plane admission in twenty lines of bash: a sealed
    receipt under ``XDG_STATE_HOME`` or a staged release root under ``XDG_DATA_HOME`` makes it
    proceed, and only their joint absence produces the refusal the manifest case asserts. Both halves
    are here because the product reaches for the second when the first is missing -- it mints a ticket
    from a release root -- so a fixture watching only the receipts directory would call an isolation
    complete while the other plane still decided the verdict.

    It is a re-expression and not the product, so what it can prove is that the READER hands a case an
    environment in which the operator's planes are unreachable. That the shipped dispatcher refuses
    for the same reason is the workflow's job, against a real archive.
    """

    def __init__(self, base: Path):
        self.root = base / "acquisition-sensitive-stub"
        (self.root / "bin").mkdir(parents=True)
        dispatcher = self.root / "bin" / "ccodex"
        dispatcher.write_text(
            "#!/usr/bin/env bash\n"
            'receipts="${XDG_STATE_HOME:-$HOME/.local/state}/agentic-sdlc/acquisition/receipts"\n'
            'candidates="${XDG_DATA_HOME:-$HOME/.local/share}/agentic-sdlc/acquisition/candidates"\n'
            'for receipt in "$receipts"/*.json; do\n'
            '  [ -e "$receipt" ] || continue\n'
            "  printf 'PROCEEDING PAST THE REFUSAL: sealed acquisition receipt %s\\n' \"$receipt\"\n"
            "  exit 0\n"
            "done\n"
            'for root in "$candidates"/*/root/manifest.json; do\n'
            '  [ -e "$root" ] || continue\n'
            "  printf 'PROCEEDING PAST THE REFUSAL: release root %s\\n' \"$root\"\n"
            "  exit 0\n"
            "done\n"
            "printf 'refused before any effect: no acquired candidate is available: %s holds no"
            " <archive-sha256>.json acquisition receipt and %s holds no release root to seal one"
            " from\\n' \"$receipts\" \"$candidates\" >&2\n"
            "exit 3\n",
            encoding="utf-8",
        )
        dispatcher.chmod(0o755)


def acquisition_case(**overrides: object) -> dict[str, object]:
    """The shipped install case's assertions, against the stub above."""
    case: dict[str, object] = {
        "id": "install-refuses-before-effect-on-linux",
        "argv": ["install", "--scope", "user", "--agent", "claude"],
        "platforms": ["Darwin", "Linux"],
        "environment": "scratch-state",
        "expect_exit": 3,
        "expect_stderr_present": [
            "refused before any effect",
            "no acquired candidate is available",
        ],
        "expect_stderr_absent": ["expected direct -I -B execution", "is not trusted"],
    }
    case.update(overrides)
    return case


def fixture_host_environment(home: Path) -> dict[str, str]:
    """An invoking environment whose every operator plane is under `home`, never the real one.

    Every test below runs the reader as a subprocess, and a subprocess that inherited this process's
    HOME would read and could write the operator's own planes even on the runs that expect a refusal
    first. So the fixture supplies all four XDG roots explicitly rather than letting any of them
    re-derive.
    """
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    for variable, tail in (
        ("XDG_STATE_HOME", "state"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
    ):
        root = home / tail
        root.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(root)
    return environment


def tree_snapshot(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def manifest_document(cases: list[dict[str, object]]) -> dict[str, object]:
    return {"schema_version": "release-smoke/v1", "cases": cases}


def admitted_case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {
        "id": "stub-status-is-admitted",
        # The top-level lifecycle spelling, with the selectors that pick the reader over the gateway
        # `status`. The stub dispatcher ignores its argv, so this is documentation of the invocation
        # under test rather than a live parse -- which is exactly why a retired spelling must not be
        # left sitting here.
        "argv": ["status", "--scope", "user", "--agent", "claude", "--json"],
        "platforms": ["Darwin", "Linux"],
        "environment": "host",
        "expect_exit": 0,
        "expect_stdout_json": {"runtime.isolated": True, "runtime.state": "admitted"},
        "forbid_finding_codes": [REFUSAL_FINDING],
    }
    case.update(overrides)
    return case


def run_smoke(
    tree: Path, manifest: Path, *extra: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT), "--tree", str(tree), "--policy", str(manifest), *extra],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class ShippedManifestTest(unittest.TestCase):
    """The manifest this repository actually ships, against issue #9's acceptance criteria."""

    def setUp(self) -> None:
        self.cases = smoke.load_manifest(MANIFEST_PATH)

    def test_the_shipped_manifest_loads_through_the_readers_own_validator(self) -> None:
        self.assertTrue(self.cases)

    def test_every_reader_verb_has_a_case_asserting_it_is_admitted(self) -> None:
        """Criterion 11's first half, asked of the reader's OWN verb list rather than a copy of it.

        The verbs are top-level now, so the argv is matched at position 0 instead of behind a `sdlc`
        namespace token, and `inspect` is gone from `READER_VERBS` -- `status` reads one plane and
        `doctor` reads the whole box, which is what made a fourth read spelling redundant. Reading the
        tuple from the product keeps the coverage claim honest in both directions: a verb added there
        without a manifest case fails here, and a verb retired there stops being demanded.
        """
        self.assertTrue(reader.READER_VERBS, "the reader must declare which verbs render a report")
        for verb in reader.READER_VERBS:
            with self.subTest(verb=verb):
                matching = [
                    case
                    for case in self.cases
                    if case["argv"][:1] == [verb]
                    and case["expect_exit"] == 0
                    and case.get("expect_stdout_json", {}).get("runtime.state") == "admitted"
                    and REFUSAL_FINDING in case.get("forbid_finding_codes", [])
                ]
                self.assertTrue(
                    matching,
                    f"no case asserts that `ccodex {verb}` is admitted and carries no"
                    f" {REFUSAL_FINDING} finding; that absence is the whole defect of issue #9",
                )

    def test_a_refusal_case_forbids_the_admission_text_on_stderr(self) -> None:
        """Criterion 11's second half, and the case that would have PASSED at v0.7.4 without it.

        `sdlc install` refuses at exit 3 either way. Only forbidding the admission text tells the
        two refusals apart, so a dispatcher on the wrong interpreter cannot hide behind an
        otherwise-expected exit code.
        """
        guarded = [
            case
            for case in self.cases
            if case["expect_exit"] == 3 and ADMISSION_MARKER in case.get("expect_stderr_absent", [])
        ]
        self.assertTrue(guarded, "no refusal case forbids the runtime-admission text on stderr")
        for case in guarded:
            with self.subTest(case=case["id"]):
                self.assertTrue(
                    case.get("expect_stderr_present"),
                    "a refusal case must also name the refusal it EXPECTS, or exit 3 alone satisfies it",
                )

    def test_every_case_asserts_output_and_not_merely_an_exit_code(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(
                    any(
                        case.get(field)
                        for field in (*smoke.STRING_LIST_FIELDS, "expect_stdout_json")
                    )
                )

    def test_the_manifest_names_no_uncertified_platform(self) -> None:
        """Windows stays absent: whether the extracted bash dispatcher runs there is unmeasured."""
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual([], [name for name in case["platforms"] if name not in ("Darwin", "Linux")])


class SharedUvRunnerControlLineTest(unittest.TestCase):
    """The shared-uv-runner case's expected line, bound to the PRODUCT that emits it.

    RE-ANCHORED (agentic-sdlc-7a2b W3a) from ``bundle-status-reads-the-ledger-and-ends-with-its-
    terminal-line``. That case is gone from the manifest because ``ccodex bundle status`` was the only
    dispatcher route that could reach ``install_skill_bundle.py status``, and ``ccodex bundle`` is now
    a refusal that resolves no tool; the re-authored manifest put ``libraries list`` in its place as
    the shared-``run_python`` control, and ``tests/seam_harness.py`` records the same substitution for
    the same reason. So this class pins THAT case's line instead.

    THE CLAIM IS UNCHANGED, and it is worth restating because it cost two red CI runners: the first
    version of the retired case asserted AGENTS.md's PARAPHRASE of a product line instead of the line
    the product actually returns, and the local run passed anyway because this host only ever
    exercised the other branch. Asserting the manifest's needle against the function that emits it is
    what keeps a reworded product line reddening `mise run check` instead of surfacing as a
    release-gate failure nobody can reproduce locally.

    WHAT MOVED RATHER THAN VANISHED. The retired case carried a ``\\Z``-anchored
    ``expect_stdout_matches`` regex, so it could also claim that ``status`` ends in exactly ONE
    terminal line and never in silence. The re-authored manifest makes no positional claim anywhere --
    no case uses ``expect_stdout_matches`` at all -- so that half is not re-anchored here. It is
    pinned in-process, on BOTH branches, by ``tests/test_install_skill_bundle.py``'s ``messages[-1]``
    assertions (``test_status_on_a_clean_host_names_the_empty_result_and_next_command``,
    ``test_status_always_ends_with_a_counted_summary_line``, and
    ``test_status_summary_is_terminal_for_every_counted_shape``), which this wave leaves untouched.
    """

    CASE_ID = "libraries-list-still-reaches-the-shared-uv-runner"

    @classmethod
    def setUpClass(cls) -> None:
        cls.libraries = _load(
            ROOT / "scripts" / "install_external_libraries.py", "libraries_for_release_smoke_test"
        )
        cases = {case["id"]: case for case in smoke.load_manifest(MANIFEST_PATH)}
        cls.case = cases[cls.CASE_ID]
        cls.present = list(cls.case["expect_stdout_present"])
        cls.absent = list(cls.case["expect_stdout_absent"])
        assert cls.present and cls.absent, cls.case

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        # The SHIPPED case document, alone in a fixture manifest, so the end-to-end verdicts below
        # assess the real case's own fields rather than a restatement of them.
        self.manifest = self.base / "manifest.json"
        self.manifest.write_text(json.dumps(manifest_document([self.case])), encoding="utf-8")

    def product_lines(self) -> list[str]:
        """What `ccodex libraries list` really prints, from the product's own renderer.

        ISOLATED HOME, as every CLI-shaped test here must be: this renderer reads `config.home` and
        the state root to report what already occupies the skills namespace, so pointing either at the
        developer's real `~` would make the assertion about their machine.
        """
        home = self.base / "home"
        (home / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        config = self.libraries.Config(
            repo_root=ROOT, home=home, state_home=self.base / "state"
        )
        exit_code, lines = self.libraries.command_list(config)
        self.assertEqual(0, exit_code, lines)
        return lines

    def stub_verdict(self, stdout: str) -> subprocess.CompletedProcess[str]:
        directory = self.base / f"tree-{len(list(self.base.glob('tree-*')))}"
        directory.mkdir()
        return run_smoke(StubTree(directory, stdout=stdout).root, self.manifest)

    def test_the_case_asserts_lines_the_product_itself_emits(self) -> None:
        """The binding, in-process, so it holds on hosts where the smoke CLI selects no case."""
        lines = self.product_lines()
        for needle in self.present:
            with self.subTest(needle=needle):
                self.assertTrue(
                    [line for line in lines if needle in line],
                    f"{needle!r} is not in `libraries list`'s own output; the manifest is quoting"
                    " something other than the product",
                )

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_the_products_own_output_passes_this_case_end_to_end(self) -> None:
        completed = self.stub_verdict("\n".join(self.product_lines()) + "\n")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn(f"pass {self.CASE_ID}", completed.stdout)

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_a_reworded_product_line_fails_this_case_by_name(self) -> None:
        """The exact regression, mutated: reword what the product prints and the gate must go red."""
        needle = self.present[0]
        reworded = [line.replace(needle, "External skill libraries.") for line in self.product_lines()]
        self.assertNotIn(needle, "\n".join(reworded), "the line must be present to reword")
        completed = self.stub_verdict("\n".join(reworded) + "\n")
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn(f"FAIL {self.CASE_ID}", completed.stdout)
        self.assertIn(repr(needle), completed.stdout)

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_silent_output_does_not_satisfy_this_case(self) -> None:
        """A silent exit 0 is a defect, not a clean host (AGENTS.md)."""
        for stdout in ("", "\n"):
            with self.subTest(stdout=stdout):
                completed = self.stub_verdict(stdout)
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertIn(f"FAIL {self.CASE_ID}", completed.stdout)

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_the_case_still_forbids_the_failure_shapes_this_route_can_emit(self) -> None:
        """Reaching the runner is not enough: the expected line plus a traceback is still a failure."""
        for forbidden in self.absent:
            with self.subTest(forbidden=forbidden):
                completed = self.stub_verdict(
                    "\n".join(self.product_lines()) + f"\n{forbidden} something\n"
                )
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertIn(f"FAIL {self.CASE_ID}", completed.stdout)
                self.assertIn(repr(forbidden), completed.stdout)


class ManifestSchemaTest(unittest.TestCase):
    """Each refusal is paired with the positive control that proves it fired for its own reason."""

    def refusal_for(self, document: object) -> str:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(smoke.Refusal) as caught:
                smoke.load_manifest(path)
            return str(caught.exception)

    def loads(self, document: object) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            smoke.load_manifest(path)

    def test_the_control_document_loads(self) -> None:
        self.loads(manifest_document([admitted_case()]))

    def test_a_case_asserting_only_an_exit_code_is_refused_by_name(self) -> None:
        bare = admitted_case()
        del bare["expect_stdout_json"]
        del bare["forbid_finding_codes"]
        self.assertIn("asserts only an exit code", self.refusal_for(manifest_document([bare])))

    def test_an_unknown_field_is_refused_rather_than_ignored(self) -> None:
        self.assertIn(
            "unknown fields",
            self.refusal_for(manifest_document([admitted_case(expect_stdout_contains=["x"])])),
        )

    def test_a_duplicate_case_id_is_refused(self) -> None:
        self.assertIn("twice", self.refusal_for(manifest_document([admitted_case(), admitted_case()])))

    def test_an_uncertified_platform_is_refused(self) -> None:
        self.assertIn(
            "platforms must be",
            self.refusal_for(manifest_document([admitted_case(platforms=["Windows"])])),
        )

    def test_an_out_of_class_exit_code_is_refused(self) -> None:
        self.assertIn(
            "exit class",
            self.refusal_for(manifest_document([admitted_case(expect_exit=7)])),
        )

    def test_a_wrong_schema_version_is_refused(self) -> None:
        document = manifest_document([admitted_case()])
        document["schema_version"] = "release-smoke/v2"
        self.assertIn("declares schema", self.refusal_for(document))


class VerdictTest(unittest.TestCase):
    """The reader's verdict on the two report shapes that decide this gate."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.manifest = self.base / "manifest.json"
        self.manifest.write_text(json.dumps(manifest_document([admitted_case()])), encoding="utf-8")

    def tree(self, *, admitted: bool) -> Path:
        directory = self.base / ("admitted" if admitted else "refused")
        directory.mkdir()
        stub = StubTree(
            directory,
            stdout=report(admitted=admitted),
            stderr="" if admitted else f"error: {ADMISSION_MARKER}\n",
            exit_code=0 if admitted else 3,
        )
        return stub.root

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_an_admitted_report_passes_its_case(self) -> None:
        completed = run_smoke(self.tree(admitted=True), self.manifest)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass stub-status-is-admitted", completed.stdout)
        self.assertIn("1 selected, 1 passed, 0 failed", completed.stdout)

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_the_v074_refusal_shape_fails_and_names_both_markers(self) -> None:
        completed = run_smoke(self.tree(admitted=False), self.manifest)
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("FAIL stub-status-is-admitted", completed.stdout)
        self.assertIn(f"forbidden finding code '{REFUSAL_FINDING}'", completed.stdout)
        self.assertIn("exit 3, expected 0", completed.stdout)
        # The captured evidence reaches the log, so a CI reader sees WHY rather than a bare verdict.
        self.assertIn(ADMISSION_MARKER, completed.stdout)

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_expect_refusal_admits_the_mutated_shape(self) -> None:
        completed = run_smoke(
            self.tree(admitted=False),
            self.manifest,
            "--expect-refusal",
            "--require-marker",
            REFUSAL_FINDING,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("refusal proven", completed.stdout)

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_expect_refusal_fails_when_nothing_broke(self) -> None:
        """The anti-vacuity control: a mutation job cannot be green because the mutation stopped mattering."""
        completed = run_smoke(
            self.tree(admitted=True),
            self.manifest,
            "--expect-refusal",
            "--require-marker",
            REFUSAL_FINDING,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("every case passed", completed.stdout)

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_expect_refusal_rejects_a_failure_it_cannot_attribute(self) -> None:
        """An unrelated breakage must not satisfy the mutation proof."""
        directory = self.base / "unrelated"
        directory.mkdir()
        stub = StubTree(directory, stdout="", stderr="error: something else entirely\n", exit_code=1)
        completed = run_smoke(
            stub.root, self.manifest, "--expect-refusal", "--require-marker", REFUSAL_FINDING
        )
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("unrelated reason", completed.stdout)
        self.assertIn("NEVER OBSERVED", completed.stdout)

    def test_expect_refusal_requires_a_marker(self) -> None:
        completed = run_smoke(self.tree(admitted=False), self.manifest, "--expect-refusal")
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
        self.assertIn("requires at least one --require-marker", completed.stderr)

    def test_a_marker_without_the_inverted_verdict_is_a_usage_error(self) -> None:
        completed = run_smoke(self.tree(admitted=True), self.manifest, "--require-marker", "x")
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)

    @unittest.skipUnless(SMOKE_SELECTS_A_CASE_HERE, NO_CASE_FOR_THIS_PLATFORM_SKIP_REASON)
    def test_a_truthy_integer_does_not_satisfy_a_boolean_assertion(self) -> None:
        """`isolated: 1` is not `isolated: true`; Python's `1 == True` must not decide this gate."""
        directory = self.base / "truthy"
        directory.mkdir()
        document = json.loads(report(admitted=True))
        document["runtime"]["isolated"] = 1
        stub = StubTree(directory, stdout=json.dumps(document), exit_code=0)
        completed = run_smoke(stub.root, self.manifest)
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("report runtime.isolated is 1, expected True", completed.stdout)

    def test_a_tree_inside_this_checkout_is_refused(self) -> None:
        """Criterion 6 in code: the gate must execute the ARCHIVE, never the checkout it was built from."""
        completed = run_smoke(ROOT, self.manifest)
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertIn("sits inside this checkout", completed.stderr)

    def test_a_tree_without_an_executable_dispatcher_is_refused(self) -> None:
        directory = self.base / "hollow"
        (directory / "bin").mkdir(parents=True)
        completed = run_smoke(directory, self.manifest)
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertIn("not an extracted archive", completed.stderr)

    def test_an_unknown_case_id_is_refused_rather_than_silently_selecting_nothing(self) -> None:
        completed = run_smoke(self.tree(admitted=True), self.manifest, "--case", "no-such-case")
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertIn("no such case", completed.stderr)


class ScratchStateEnvironmentTest(unittest.TestCase):
    """The `scratch-state` mode, and the host state it exists to stop deciding a verdict.

    Issue #9's install case asserted a refusal that only holds while the acquisition planes are empty
    (agentic-sdlc-66ca). Under `host` that made the verdict a fact about the invoking machine: seed one
    receipt and the same argv proceeds past the refusal, which on the real dispatcher means a live
    activation into the operator's Claude home during a smoke run. Every test here seeds exactly that
    state and then asks whether the mode still refuses.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.home = self.base / "invoking-home"
        self.home.mkdir()
        self.environment = fixture_host_environment(self.home)
        self.tree = AcquisitionSensitiveTree(self.base).root
        self.manifest = self.base / "manifest.json"
        self.addCleanup(self.temporary.cleanup)

    def seed_receipt(self) -> Path:
        receipts = Path(self.environment["XDG_STATE_HOME"]) / "agentic-sdlc" / "acquisition" / "receipts"
        receipts.mkdir(parents=True)
        receipt = receipts / f"{SEEDED_ARCHIVE_SHA256}.json"
        receipt.write_text(json.dumps({"schema_version": "acquisition-receipt/v1"}), encoding="utf-8")
        return receipt

    def seed_release_root(self) -> Path:
        candidates = (
            Path(self.environment["XDG_DATA_HOME"]) / "agentic-sdlc" / "acquisition" / "candidates"
        )
        root = candidates / SEEDED_ARCHIVE_SHA256 / "root"
        root.mkdir(parents=True)
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"version": "0.7.5"}), encoding="utf-8")
        return manifest

    def write_manifest(self, **overrides: object) -> None:
        self.manifest.write_text(
            json.dumps(manifest_document([acquisition_case(**overrides)])), encoding="utf-8"
        )

    def test_a_host_case_lets_a_seeded_receipt_decide_the_verdict(self) -> None:
        """SENSITIVITY CONTROL: the seeded state must actually be able to change the answer.

        Without this the isolation tests below prove nothing -- a refusal that was never at risk is
        not evidence of isolation. This is also the defect itself, reproduced: the case as shipped
        before this change would have gone RED on a host holding one receipt, and on the real
        dispatcher it would instead have proceeded to a real install.
        """
        receipt = self.seed_receipt()
        self.write_manifest(environment="host")
        completed = run_smoke(self.tree, self.manifest, env=self.environment)
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("PROCEEDING PAST THE REFUSAL", completed.stdout)
        self.assertIn(str(receipt), completed.stdout)

    def test_scratch_state_still_refuses_with_a_receipt_seeded_on_the_invoking_host(self) -> None:
        self.seed_receipt()
        self.write_manifest()
        completed = run_smoke(self.tree, self.manifest, env=self.environment)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass install-refuses-before-effect-on-linux", completed.stdout)
        self.assertNotIn("PROCEEDING PAST THE REFUSAL", completed.stdout)

    def test_scratch_state_still_refuses_with_a_release_root_staged_on_the_invoking_host(self) -> None:
        """The second acquisition plane, which `XDG_STATE_HOME` alone does not cover.

        The installer mints its own ticket from a staged release root when no receipt is filed, so a
        mode that relocated only the receipts plane would still let the candidates plane under
        `XDG_DATA_HOME` decide this verdict.
        """
        self.seed_release_root()
        self.write_manifest()
        completed = run_smoke(self.tree, self.manifest, env=self.environment)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass install-refuses-before-effect-on-linux", completed.stdout)

    def test_scratch_state_refuses_naming_its_own_planes_and_not_the_invoking_hosts(self) -> None:
        self.seed_receipt()
        self.write_manifest(expect_exit=0, expect_stdout_present=["never"])
        completed = run_smoke(self.tree, self.manifest, env=self.environment)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("no acquired candidate is available", completed.stdout)
        self.assertNotIn(self.environment["XDG_STATE_HOME"], completed.stdout)
        self.assertNotIn(self.environment["XDG_DATA_HOME"], completed.stdout)

    def test_the_invoking_hosts_own_planes_are_untouched_by_a_scratch_state_run(self) -> None:
        self.seed_receipt()
        self.seed_release_root()
        self.write_manifest()
        before = tree_snapshot(self.home)
        completed = run_smoke(self.tree, self.manifest, env=self.environment)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(tree_snapshot(self.home), before)

    def test_scratch_state_relocates_every_operator_plane_into_the_cases_own_directory(self) -> None:
        with tempfile.TemporaryDirectory() as scratch_name:
            scratch = Path(scratch_name)
            with mock.patch.dict(os.environ, self.environment, clear=True):
                environment = smoke.case_environment(acquisition_case(), scratch)
            base = scratch / "scratch-state" / "install-refuses-before-effect-on-linux"
            self.assertEqual(environment["HOME"], str(base / "home"))
            for variable, tail in smoke.SCRATCH_STATE_ROOTS:
                with self.subTest(variable=variable):
                    self.assertEqual(environment[variable], str(base.joinpath(*tail)))
                    self.assertTrue(Path(environment[variable]).is_dir())
                    self.assertEqual(tree_snapshot(Path(environment[variable])), set())

    def test_scratch_state_pins_the_toolchains_own_directories_back_to_the_invoking_host(self) -> None:
        """The hazard this mode had to engineer around, asserted rather than described.

        mise keeps its trust store and its installed toolchain under the operator's XDG roots. Moving
        those roots without pinning makes the dispatcher refuse `mise.toml is not trusted` -- exit 3,
        the same code the case expects, for an unrelated reason -- and makes the pinned toolset read as
        absent, so `auto_install` downloads it inside a smoke run. So every pin must point OUTSIDE the
        case's scratch directory.
        """
        with tempfile.TemporaryDirectory() as scratch_name:
            scratch = Path(scratch_name)
            with mock.patch.dict(os.environ, self.environment, clear=True):
                environment = smoke.case_environment(acquisition_case(), scratch)
            self.assertTrue(smoke.TOOLCHAIN_PINS)
            for variable, _xdg, _default, _leaf in smoke.TOOLCHAIN_PINS:
                with self.subTest(variable=variable):
                    self.assertIn(variable, environment)
                    pinned = Path(environment[variable])
                    self.assertTrue(pinned.is_absolute(), pinned)
                    self.assertFalse(
                        pinned.is_relative_to(scratch),
                        f"{variable} was relocated with the case instead of pinned back to the host",
                    )
                    self.assertTrue(pinned.is_relative_to(self.home), pinned)

    def test_an_explicit_toolchain_pin_in_the_environment_is_the_operators_own_and_is_kept(self) -> None:
        chosen = self.base / "operator-chosen-mise-state"
        self.environment["MISE_STATE_DIR"] = str(chosen)
        with tempfile.TemporaryDirectory() as scratch_name:
            with mock.patch.dict(os.environ, self.environment, clear=True):
                environment = smoke.case_environment(acquisition_case(), Path(scratch_name))
        self.assertEqual(environment["MISE_STATE_DIR"], str(chosen))

    def test_an_unknown_environment_mode_is_refused_by_name(self) -> None:
        self.write_manifest(environment="scratch")
        completed = run_smoke(self.tree, self.manifest, env=self.environment)
        self.assertEqual(completed.returncode, 3)
        self.assertIn("environment must be one of", completed.stderr)
        self.assertIn("scratch-state", completed.stderr)

    def test_the_shipped_install_case_is_isolated_and_forbids_the_trust_refusal(self) -> None:
        """The manifest this repository ships, not a fixture: the flip is the point of the change.

        The trust text is forbidden because isolation alone cannot say WHY the dispatcher refused, and
        a moved trust store answers at the same exit code with the same `refused:` prefix.
        """
        cases = {case["id"]: case for case in smoke.load_manifest(MANIFEST_PATH)}
        case = cases["install-refuses-before-effect-on-linux"]
        self.assertEqual(case["environment"], "scratch-state")
        self.assertIn("no acquired candidate is available", case["expect_stderr_present"])
        self.assertIn("is not trusted", case["expect_stderr_absent"])


class MutationFixtureTest(unittest.TestCase):
    """The patch the mutation job applies: it must exist, apply, and restore the v0.7.4 route.

    RE-ANCHORED (agentic-sdlc-7a2b W3a) from a `  sdlc)`-delimited slice of the dispatcher onto a
    COUNT of the route's call sites. The `sdlc)` arm these tests used to cut out is now a refusal that
    calls nothing, and the fixed route is reached from TWO places -- the
    `install|update|uninstall|doctor|recover` table and the `status` arm's selector branch -- so a
    slice of one arm can no longer see the route at all, and a patch that mutated only one of the two
    would leave a smoke case taking the fixed route and reporting green on a regressed tree. The
    count is asserted in BOTH directions on purpose: an intact tree is (2 fixed, 0 regressed) and a
    mutated one is exactly the reverse, so neither a missed call site nor a silently added one passes.
    """

    #: The two spellings the mutation swaps between, as they appear at a CALL SITE. `run_sdlc_python`
    #: also appears as a function definition, and `run_python` also serves the libraries and
    #: statusline verbs, so both forms carry their argument vector to keep the count exact.
    FIXED_CALL = 'run_sdlc_python "$@"'
    REGRESSED_CALL = 'run_python ccodex_sdlc.py "$@"'
    #: How many places take that route. Ratified decision 1's verb table is one; `status`'s selector
    #: branch is the other, because `status` is the one name the gateway plane and the lifecycle share.
    CALL_SITES = 2

    def test_the_patch_restores_the_uv_run_dispatch_at_every_lifecycle_call_site(self) -> None:
        text = MUTATION_PATCH.read_text(encoding="utf-8")
        self.assertIn("diff --git a/bin/ccodex b/bin/ccodex", text)
        # Counted rather than merely present: the indentation differs between the two call sites (the
        # `status` one sits inside an `if`), so a substring check on one spelling would pass on a
        # patch that had quietly stopped touching the other.
        removed = [
            line
            for line in text.splitlines()
            if line.startswith("-") and line.endswith(self.FIXED_CALL)
        ]
        added = [
            line
            for line in text.splitlines()
            if line.startswith("+") and line.endswith(self.REGRESSED_CALL)
        ]
        self.assertEqual(self.CALL_SITES, len(removed), text)
        self.assertEqual(self.CALL_SITES, len(added), text)
        # The preamble must name the commit whose regression this reproduces, so a future reader
        # can find the history without the CI job depending on it.
        self.assertIn("cd3fd3dec33e429fddb0a2acfe5a1d4bc2f01428", text)

    @unittest.skipUnless(shutil.which("git"), "git is required to apply the mutation fixture")
    def test_applying_the_patch_puts_every_call_site_back_on_the_shared_uv_runner(self) -> None:
        """Applied to a COPY of the shipped dispatcher, not to the checkout's own bytes."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bin").mkdir()
            shutil.copy2(BIN_CCODEX, root / "bin" / "ccodex")
            completed = subprocess.run(
                ["git", "apply", "-p1", str(MUTATION_PATCH)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            mutated = (root / "bin" / "ccodex").read_text(encoding="utf-8")
        self.assertEqual(self.CALL_SITES, mutated.count(self.REGRESSED_CALL))
        self.assertEqual(0, mutated.count(self.FIXED_CALL))

    def test_the_intact_dispatcher_takes_the_direct_isolated_route(self) -> None:
        """Positive control for the test above: without the patch, every call site is the fixed one."""
        intact = BIN_CCODEX.read_text(encoding="utf-8")
        self.assertEqual(self.CALL_SITES, intact.count(self.FIXED_CALL))
        self.assertEqual(0, intact.count(self.REGRESSED_CALL))


class ReleaseWorkflowTest(unittest.TestCase):
    """The structure the digest pin only freezes: what a re-pinned edit still has to keep."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.document = yaml.safe_load(cls.text)
        # PyYAML reads an unquoted `on:` key as the boolean True.
        cls.triggers = cls.document.get("on", cls.document.get(True))
        cls.jobs = cls.document["jobs"]

    def test_the_gate_fires_on_a_tag_and_can_be_exercised_before_one_exists(self) -> None:
        self.assertEqual(self.triggers["push"]["tags"], ["v*"])
        self.assertIn("workflow_dispatch", self.triggers)

    def test_publication_is_gated_on_both_the_smoke_and_the_mutation(self) -> None:
        self.assertEqual(self.jobs["publish"]["needs"], ["smoke", "mutation"])
        # A manual dispatch exercises the gate; only a tag push may publish.
        self.assertIn("github.event_name == 'push'", self.jobs["publish"]["if"])

    def test_only_the_publish_job_may_write(self) -> None:
        self.assertEqual(self.document["permissions"], {"contents": "read"})
        self.assertEqual(self.jobs["publish"]["permissions"], {"contents": "write"})
        for name in ("build", "smoke", "mutation"):
            with self.subTest(job=name):
                self.assertNotIn("permissions", self.jobs[name])

    def test_the_smoke_runs_the_extracted_tree_on_both_certified_runners(self) -> None:
        operating_systems = self.jobs["smoke"]["strategy"]["matrix"]["os"]
        self.assertTrue(any("ubuntu" in name for name in operating_systems), operating_systems)
        self.assertTrue(any("macos" in name for name in operating_systems), operating_systems)
        self.assertNotIn(
            "windows",
            " ".join(operating_systems),
            "a Windows leg needs a measurement nobody has taken (issue #9, out of scope)",
        )

    def test_the_subject_is_extracted_outside_the_checkout(self) -> None:
        """Criterion 6: every ccodex invocation must come from a path the checkout does not contain."""
        extract = self._step(self.jobs["smoke"], "extract outside the checkout")
        self.assertIn("$RUNNER_TEMP/artifact", extract["run"])
        self.assertNotIn("$GITHUB_WORKSPACE/artifact", extract["run"])
        tree = self.jobs["smoke"]["steps"][-1]
        self.assertEqual(tree["env"]["TREE"], "${{ steps.extract.outputs.tree }}")
        self.assertIn("mise run release:smoke -- --tree", tree["run"])

    def test_the_downstream_jobs_consume_the_one_build(self) -> None:
        """The gate and the publication cannot diverge if neither rebuilds what it checks."""
        self.assertEqual(self.jobs["smoke"]["needs"], "build")
        for job in ("smoke", "publish"):
            with self.subTest(job=job):
                uses = [step.get("uses", "") for step in self.jobs[job]["steps"]]
                self.assertTrue(
                    any(entry.startswith("actions/download-artifact@") for entry in uses), uses
                )
        builds = [
            step
            for job in ("smoke", "publish")
            for step in self.jobs[job]["steps"]
            if "release:build" in (step.get("run") or "")
        ]
        self.assertEqual([], builds, "a downstream job that rebuilds is checking different bytes")

    def test_the_mutation_job_requires_the_smoke_to_fail_by_name(self) -> None:
        step = self.jobs["mutation"]["steps"][-1]
        self.assertIn("--expect-refusal", step["run"])
        self.assertIn(f"--require-marker {REFUSAL_FINDING}", step["run"])
        self.assertIn(f"--require-marker '{ADMISSION_MARKER}'", step["run"])
        applied = self._step(self.jobs["mutation"], "Restore the v0.7.4 sdlc route")
        # `as_posix`, not `str`: this path is being looked for inside a POSIX shell script that a
        # Linux runner executes, so its separator is `/` on every host reading this file. `str` gave
        # `.github\mutations\...` on windows-2025 and matched nothing (agentic-sdlc-5ce7).
        self.assertIn(MUTATION_PATCH.relative_to(ROOT).as_posix(), applied["run"])
        self.assertIn("git apply --check", applied["run"])

    def test_every_action_is_pinned_to_a_commit(self) -> None:
        for job, body in self.jobs.items():
            for step in body["steps"]:
                uses = step.get("uses")
                if not uses:
                    continue
                with self.subTest(job=job, uses=uses):
                    self.assertRegex(uses, r"@[0-9a-f]{40}$", "a floating tag can be repointed upstream")

    def test_no_second_task_runner_drives_this_workflow(self) -> None:
        for pattern in (
            re.compile(r"(?m)^\s*run:\s*(?:make|just|task)\s"),
            re.compile(r"(?m)^\s*run:\s*npm run\s"),
        ):
            with self.subTest(pattern=pattern.pattern):
                self.assertNotRegex(self.text, pattern)

    def test_no_untrusted_expression_reaches_a_shell_body(self) -> None:
        """Workflow-injection hygiene: values cross into a shell through `env:`, never inline."""
        for job, body in self.jobs.items():
            for index, step in enumerate(body["steps"]):
                run = step.get("run")
                if not run:
                    continue
                with self.subTest(job=job, step=index):
                    self.assertNotIn("${{", run)

    def _step(self, job: dict, name_fragment: str) -> dict:
        for step in job["steps"]:
            if name_fragment in (step.get("name") or ""):
                return step
        raise AssertionError(f"no step named like {name_fragment!r}")


class ValidatorPinTest(unittest.TestCase):
    """The new CI surface is a reviewed edit: an unreviewed one fails the gate by name."""

    def copied(self, root: Path) -> None:
        for relative in (
            "scripts/validate-bundle.sh",
            "scripts/bump-version.sh",
            "lefthook.yml",
            ".github/workflows/validate.yml",
            ".github/workflows/release.yml",
            "CLAUDE.md",
        ):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)

    def gate_errors(self, root: Path) -> list[str]:
        result = validator.Validation()
        validator.validate_gate_graph(root, result)
        return result.errors

    def test_the_shipped_workflow_satisfies_its_pin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copied(root)
            self.assertEqual([], self.gate_errors(root))

    def test_an_edited_release_workflow_reddens_the_gate(self) -> None:
        """Mutation pair: dropping the mutation gating from `publish` must not pass silently."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copied(root)
            path = root / ".github" / "workflows" / "release.yml"
            text = path.read_text(encoding="utf-8")
            weakened = text.replace("needs: [smoke, mutation]", "needs: [smoke]", 1)
            self.assertNotEqual(weakened, text, "the gating must be present to weaken")
            path.write_text(weakened, encoding="utf-8")
            errors = self.gate_errors(root)
        self.assertTrue(any("release workflow must equal" in error for error in errors), errors)

    def test_a_missing_release_workflow_is_reported_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copied(root)
            (root / ".github" / "workflows" / "release.yml").unlink()
            errors = self.gate_errors(root)
        self.assertIn(".github/workflows/release.yml is required", errors)


class TaskWiringTest(unittest.TestCase):
    def test_the_smoke_is_a_task_and_never_a_gate_leaf(self) -> None:
        import tomllib

        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        self.assertIn("release:smoke", config["tasks"])
        self.assertIn("smoke_release.py", config["tasks"]["release:smoke"]["run"])
        # It needs an artifact extracted outside the checkout, which `check` neither builds nor
        # should require, so it must not be reachable from the authoritative gate.
        self.assertNotIn("release:smoke", config["tasks"]["check"]["depends"])
        for leaf in config["tasks"]["check"]["depends"]:
            with self.subTest(leaf=leaf):
                self.assertNotIn("release:smoke", config["tasks"][leaf].get("depends", []))
        lefthook = (ROOT / "lefthook.yml").read_text(encoding="utf-8")
        self.assertNotIn("release:smoke", lefthook)


if __name__ == "__main__":
    unittest.main()
