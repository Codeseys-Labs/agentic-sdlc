"""The tag gate: the smoke manifest, its reader's verdicts, the workflow, and the mutation fixture.

Issue #9 is the subject. Two published prereleases shipped a ``ccodex sdlc`` plane that refused
itself at exit 3, and the reason nothing was red is the reason this module exists: the repository's
only artifact test was negative-only, so no assertion anywhere said a ``sdlc`` verb is ever
ADMITTED. Every positive here is paired with the mutation that must break it.

The reader's end-to-end verdicts run against a STUB ``bin/ccodex`` rather than a built archive: the
real-archive proof belongs to the workflow (and to ``tests/test_bin_ccodex.py``'s extract-and-run
fixture), while what needs proving HERE is that the verdict logic distinguishes an admitted report
from the v0.7.4 refusal, and that ``--expect-refusal`` cannot pass vacuously.
"""

from __future__ import annotations

import importlib.util
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

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
    """A directory shaped like an extracted archive, whose ``bin/ccodex`` is a canned responder."""

    def __init__(self, base: Path, *, stdout: str = "", stderr: str = "", exit_code: int = 0):
        self.root = base / "agentic-sdlc-stub"
        (self.root / "bin").mkdir(parents=True)
        dispatcher = self.root / "bin" / "ccodex"
        dispatcher.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s' {json.dumps(stdout)}\n"
            f"printf '%s' {json.dumps(stderr)} >&2\n"
            f"exit {exit_code}\n",
            encoding="utf-8",
        )
        dispatcher.chmod(0o755)


def manifest_document(cases: list[dict[str, object]]) -> dict[str, object]:
    return {"schema_version": "release-smoke/v1", "cases": cases}


def admitted_case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {
        "id": "stub-status-is-admitted",
        "argv": ["sdlc", "status", "--json"],
        "platforms": ["Darwin", "Linux"],
        "environment": "host",
        "expect_exit": 0,
        "expect_stdout_json": {"runtime.isolated": True, "runtime.state": "admitted"},
        "forbid_finding_codes": [REFUSAL_FINDING],
    }
    case.update(overrides)
    return case


def run_smoke(tree: Path, manifest: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT), "--tree", str(tree), "--policy", str(manifest), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


class ShippedManifestTest(unittest.TestCase):
    """The manifest this repository actually ships, against issue #9's acceptance criteria."""

    def setUp(self) -> None:
        self.cases = smoke.load_manifest(MANIFEST_PATH)

    def test_the_shipped_manifest_loads_through_the_readers_own_validator(self) -> None:
        self.assertTrue(self.cases)

    def test_every_reader_verb_has_a_case_asserting_it_is_admitted(self) -> None:
        """Criterion 11's first half: inspect, status, and doctor each carry an admitted case."""
        for verb in ("inspect", "status", "doctor"):
            with self.subTest(verb=verb):
                matching = [
                    case
                    for case in self.cases
                    if case["argv"][:2] == ["sdlc", verb]
                    and case["expect_exit"] == 0
                    and case.get("expect_stdout_json", {}).get("runtime.state") == "admitted"
                    and REFUSAL_FINDING in case.get("forbid_finding_codes", [])
                ]
                self.assertTrue(
                    matching,
                    f"no case asserts that `sdlc {verb}` is admitted and carries no {REFUSAL_FINDING}"
                    " finding; that absence is the whole defect of issue #9",
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


class BundleStatusTerminalLineTest(unittest.TestCase):
    """The manifest's terminal-line pattern, bound to the PRODUCT that emits it.

    This exists because the first version of that case asserted AGENTS.md's PARAPHRASE
    (``no owned entries for this host``) instead of what ``status_summary`` actually returns
    (``... (run: mise run bundle:install)``), and the local run passed anyway: this host HAS owned
    entries, so only the OTHER alternative was ever exercised. Both CI runners are fresh, took the
    branch nobody had run, and failed. The pattern is asserted here against
    ``install_skill_bundle.status_summary`` itself, so the two cannot drift again -- a reworded
    summary now reddens `mise run check` instead of surfacing as a release-gate failure.
    """

    CASE_ID = "bundle-status-reads-the-ledger-and-ends-with-its-terminal-line"

    @classmethod
    def setUpClass(cls) -> None:
        cls.installer = _load(ROOT / "scripts" / "install_skill_bundle.py", "installer_for_release_smoke_test")
        cases = {case["id"]: case for case in smoke.load_manifest(MANIFEST_PATH)}
        patterns = cases[cls.CASE_ID]["expect_stdout_matches"]
        assert len(patterns) == 1, patterns
        cls.pattern = patterns[0]

    def summaries(self) -> list[str]:
        """Both branches of the product's own terminal line, from the product itself."""
        return [
            self.installer.status_summary({"ok": 0, "conflict": 0, "absent": 0}),
            self.installer.status_summary({"ok": 44, "conflict": 0, "absent": 0}),
            self.installer.status_summary({"ok": 3, "conflict": 2, "absent": 1}),
        ]

    def test_the_product_still_has_exactly_the_two_branches_this_case_covers(self) -> None:
        empty, populated, mixed = self.summaries()
        self.assertEqual(empty, "no owned entries for this host (run: mise run bundle:install)")
        self.assertEqual(populated, "44 ok, 0 conflict, 0 absent")
        self.assertEqual(mixed, "3 ok, 2 conflict, 1 absent")

    def test_the_pattern_matches_every_terminal_line_the_product_can_emit(self) -> None:
        """The blind spot closed: the no-entries branch is covered here even on a host that has some."""
        for summary in self.summaries():
            with self.subTest(summary=summary):
                # A lone terminal line, as a fresh host prints it.
                self.assertRegex(f"{summary}\n", self.pattern)
                # And after the per-entry lines a populated host prints first.
                self.assertRegex(f"ok: /somewhere/one\nok: /somewhere/two\n{summary}\n", self.pattern)

    def test_the_documentation_paraphrase_does_not_satisfy_the_pattern(self) -> None:
        """The exact regression: AGENTS.md and README quote the prefix, the product emits the hint."""
        self.assertNotRegex("no owned entries for this host\n", self.pattern)

    def test_a_summary_that_is_not_the_last_line_does_not_satisfy_the_pattern(self) -> None:
        """`\\Z` is load-bearing: `status` ends in ONE terminal line, so position is the contract."""
        for summary in self.summaries():
            with self.subTest(summary=summary):
                self.assertNotRegex(f"{summary}\nok: /somewhere/trailing\n", self.pattern)

    def test_silent_output_does_not_satisfy_the_pattern(self) -> None:
        """A silent exit 0 is a defect, not a clean host (AGENTS.md)."""
        for stdout in ("", "\n", "ok: /somewhere/one\n"):
            with self.subTest(stdout=stdout):
                self.assertNotRegex(stdout, self.pattern)


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


class MutationFixtureTest(unittest.TestCase):
    """The patch the mutation job applies: it must exist, apply, and restore the v0.7.4 route."""

    def test_the_patch_restores_the_uv_run_dispatch_at_the_sdlc_route(self) -> None:
        text = MUTATION_PATCH.read_text(encoding="utf-8")
        self.assertIn("diff --git a/bin/ccodex b/bin/ccodex", text)
        self.assertIn('-    run_sdlc_python "$@"', text)
        self.assertIn('+    run_python ccodex_sdlc.py "$@"', text)
        # The preamble must name the commit whose regression this reproduces, so a future reader
        # can find the history without the CI job depending on it.
        self.assertIn("cd3fd3dec33e429fddb0a2acfe5a1d4bc2f01428", text)

    @unittest.skipUnless(shutil.which("git"), "git is required to apply the mutation fixture")
    def test_applying_the_patch_puts_the_route_back_on_the_shared_uv_runner(self) -> None:
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
        route = mutated.split("  sdlc)", 1)[1].split(";;", 1)[0]
        self.assertIn('run_python ccodex_sdlc.py "$@"', route)
        self.assertNotIn("run_sdlc_python", route)

    def test_the_intact_dispatcher_takes_the_direct_isolated_route(self) -> None:
        """Positive control for the test above: without the patch, the route is the fixed one."""
        route = BIN_CCODEX.read_text(encoding="utf-8").split("  sdlc)", 1)[1].split(";;", 1)[0]
        self.assertIn('run_sdlc_python "$@"', route)
        self.assertNotIn("run_python ccodex_sdlc.py", route)


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
