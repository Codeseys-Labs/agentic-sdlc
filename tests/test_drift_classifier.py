"""Tests for the drift classifier: its taxonomy table, its severity fold, its safety rule, and its IO.

Seven kinds of test live here and they check different things.

The TABLE tests are the point of the file. All sixteen rows are asserted in ONE run over ONE observed
document -- one `subTest` per kind -- because the table is a total function and sixteen separate runs
would prove the same thing sixteen times more slowly. Each subtest asserts BOTH the outcome and the
issue-16 clause the row is grounded in, by the phrase that clause is built from: a row whose outcome was
flipped and a row whose grounding was quietly swapped for a different clause are different bugs, and
asserting only the outcome would catch just the first. The expected table is RE-EXPRESSED here from
issue 16's own prose, so a drifted tool fails rather than agrees with itself.

The SEVERITY tests pin the fold against the two mutations that look right. `min` instead of `max` is
caught by any mixed document; an ALPHABETICAL maximum is caught only by a document whose severity
maximum and alphabetical maximum differ, and `{authority, added-node}` is exactly that document --
`hard-stop` sorts BEFORE `replan-required`, so an alphabetical fold answers `replan-required`. That
case carries its own positive control: the test asserts the two orders really do disagree on those two
strings, because a comparison whose premise had rotted would pass while proving nothing.

The AMBIGUITY tests are issue 16:79 ("Ambiguous classification is `hard-stop`, never compatible") in
four applications: an unknown kind, a subject the plan does not name, a plan-digest mismatch, and an
empty or unreadable change entry. Every one of them starts from the SAME control document that is
asserted to reach `replan-required` first, so a test that stopped exercising its guard would also have
to stop reaching the control state. They also assert the OTHER half of the rule: each of these is an
OUTCOME, so the run's verdict is `classified` with no reasons at all -- a tool that refused instead
would leave the caller at a boundary with no document to stop on.

The NO-DRIFT tests pin the fifth verdict. An empty change list must reach `no-drift` with a null
`overall_outcome` and the tool's own fixed sentence -- never a silent `compatible` -- and an empty list
whose binding does not hold must still be `hard-stop`, because zero observations about an unknown plan
is not "no drift".

The VERIFY tests hand-seal `drift-classification@1` documents with this module's own canonical helpers
and hand them to `verify`, so the tool is proved to agree with the family's published derivation rather
than with itself. Each mutation breaks exactly one of the three cross-checks, and the unmutated
document is asserted to verify first as the positive control. `--expect-digest` closes the loop a
downstream consumer will actually use.

The INSTANT tests exist for one character class: the guard is `[0-9]`, not `\\d`, so an Arabic-Indic
digit string that `\\d` would happily accept must be refused. They also prove the guard runs BEFORE any
file is read, which is what makes "this tool reads no clock" checkable rather than aspirational.

The NON-FINITE tests put `1e400` at NESTED positions -- inside a list, and inside an object several
levels down -- because `parse_constant` never sees that literal: it is an ordinary JSON number that
overflows during parsing, and the post-parse iterative walk is the only thing that catches it.

THE PLAN FIXTURE IS BUILT BY RUNNING THE REAL SIBLINGS -- `mission-contract.py define`,
`planning-snapshot.py capture`, and `wave-plan-compiler.py compile` -- once per test run into one
module-level scratch directory. Nothing here hand-writes a guess of a sibling's sealed form: the whole
point of admitting an input by re-deriving its digest is that a hand-written approximation would either
be rejected for the wrong reason or, worse, accepted while the real sibling's output was not. It also
pins the SUBJECT SPELLINGS: `ws-cartography -> ws-classifier` is the compiler's own edge spelling, and a
classifier deriving a different one would hard-stop every edge change in a real PlanDiff. Building the
snapshot needs a real `git`, so every class that consumes the plan skips with a named reason when git
is absent; the classes that hand-seal their own documents run everywhere.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "skills" / "agentic-sdlc" / "tools"
TOOL = TOOLS / "drift-classifier.py"
MISSION_TOOL = TOOLS / "mission-contract.py"
SNAPSHOT_TOOL = TOOLS / "planning-snapshot.py"
COMPILER_TOOL = TOOLS / "wave-plan-compiler.py"

PLAN_SCHEMA = "agentic-sdlc/wave-plan@1"
OBSERVED_SCHEMA = "agentic-sdlc/observed-drift@1"
CLASSIFICATION_SCHEMA = "agentic-sdlc/drift-classification@1"
RESULT_SCHEMA = "agentic-sdlc/drift-classifier-result@1"

CLASSIFIED = "classified"
NO_DRIFT = "no-drift"
VERIFIED = "verified"
REFUSED = "refused"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

AT = "2026-08-19T06:00:00Z"
OBSERVED_AT = "2026-08-19T05:00:00Z"
MISSION_ID = "mission-slice-6"

COMPATIBLE = "compatible"
REVALIDATION = "revalidation-required"
REPLAN = "replan-required"
HARD_STOP = "hard-stop"
#: The four outcomes in SEMANTIC severity order, re-expressed from issue 16:74-79. Deliberately kept as
#: an ordered tuple here too, so this module can assert that the order is not the alphabetical one.
OUTCOMES_BY_SEVERITY = (COMPATIBLE, REVALIDATION, REPLAN, HARD_STOP)

#: The expected table, re-expressed from issue 16's own taxonomy prose rather than from the tool:
#: kind -> (outcome, a phrase the row's grounding must contain). The phrase is the ANCHOR of the
#: grounding -- the exact words the row is grounded in -- so a row that kept its outcome while losing
#: its grounding, or that swapped one issue-16 clause for another, fails here.
#:
#: Fourteen rows come from the replan EXAMPLE LIST at :96-98 ("changes to mission or terminal criteria,
#: nodes or edges, repository base or owned paths, dependencies, custody, required artifacts, policies or
#: gates, capability demands, route constraints, egress, budgets, retries, fallback, integration, or
#: review"). The two kinds that list does NOT name are `approval` (:91-93 puts approval validity inside
#: revalidation) and `authority` (:77-79 and :105 name it as a hard-stop boundary twice), and they are
#: exactly the two rows that land elsewhere. `stop-rule` is the one row grounded in the general
#: definition at :77 instead of an example.
EXPECTED_TABLE: dict[str, tuple[str, str]] = {
    "added-edge": (REPLAN, "nodes or edges"),
    "added-node": (REPLAN, "nodes or edges"),
    "approval": (REVALIDATION, "without a new plan approval only when the semantic digest is unchanged"),
    "artifact": (REPLAN, "required artifacts"),
    "authority": (HARD_STOP, "authority expansion"),
    "budget": (REPLAN, "budgets"),
    "changed-node": (REPLAN, "nodes or edges"),
    "custody-boundary": (REPLAN, "custody"),
    "egress": (REPLAN, "egress"),
    "gate": (REPLAN, "policies or gates"),
    "removed-edge": (REPLAN, "nodes or edges"),
    "removed-node": (REPLAN, "nodes or edges"),
    "retry": (REPLAN, "retries"),
    "route-constraint": (REPLAN, "route constraints"),
    "stop-rule": (REPLAN, "does not name a stop rule"),
    "terminal-criterion": (REPLAN, "mission or terminal criteria"),
}

#: A realistic in-plan subject per kind, in the spellings the real compiler's PlanDiff emits. The
#: wave-wide dimensions take the mission id, because their subject is the wave rather than one vertex of
#: it, and the graph dimensions take a node, an edge, or a declared custody path.
SUBJECT_FOR_KIND: dict[str, str] = {
    "added-edge": "ws-cartography -> ws-classifier",
    "added-node": "ws-classifier",
    "approval": MISSION_ID,
    "artifact": MISSION_ID,
    "authority": "ws-cartography",
    "budget": "ws-classifier",
    "changed-node": "ws-classifier",
    "custody-boundary": ".worktrees/drift-classifier",
    "egress": "ws-classifier",
    "gate": MISSION_ID,
    "removed-edge": "ws-cartography -> ws-classifier",
    "removed-node": "ws-cartography",
    "retry": "ws-classifier",
    "route-constraint": "ws-classifier",
    "stop-rule": MISSION_ID,
    "terminal-criterion": MISSION_ID,
}

#: issue 16:79, re-expressed. Every ambiguity ground must quote it, because the four ambiguous cases are
#: four applications of ONE rule and a paraphrase in any of them would be the tool inventing a fifth.
AMBIGUOUS_QUOTE = "Ambiguous classification is `hard-stop`, never compatible."

#: The tool reads no environment variable at all, so nothing needs scrubbing by name; every spawn still
#: CONSTRUCTS its environment from this function rather than passing `os.environ` through, so a variable
#: a future version began reading could not silently reach it from a developer's shell.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def constructed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment every spawn in this module hands a tool: an ALLOWLIST, not an inheritance."""
    environment = {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}
    if extra:
        environment.update(extra)
    return environment


def canonical(value: Any) -> bytes:
    """The family's canonical form: sorted keys, tight separators, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def expected_digest(sealed: dict[str, Any]) -> str:
    """The digest contract, re-expressed here so a drifted tool fails rather than agrees with itself.

    sha256 over `canonical(sealed minus the digest key)`. Re-expressed rather than imported: the tool has
    a hyphen in its name, so a plain `import` statement cannot name it, and a shared implementation would
    make this assertion vacuous.
    """
    body = {key: value for key, value in sealed.items() if key != "digest"}
    return hashlib.sha256(canonical(body)).hexdigest()


def seal(body: dict[str, Any]) -> dict[str, Any]:
    """Add the one derived key. This is how a test builds a document the tool will accept as sealed."""
    sealed = dict(body)
    sealed["digest"] = expected_digest(body)
    return sealed


def fake_digest(label: str) -> str:
    """A well-formed sha256 that stands for a document this test does not need to build."""
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _load_module() -> Any:
    """White-box import of the tool, for the two properties this file's black-box style cannot reach:
    `write_document`'s own O_EXCL create (every CLI-level occupied-`--out` case is intercepted by the
    earlier `check_output_path` pre-flight refusal first) and `classify`'s self-readback of its own
    synthesized candidate (every CLI-level valid input synthesizes a candidate that already satisfies
    `check_classification`, so nothing black-box can prove the readback would catch one that did not).
    The hyphenated filename makes a plain `import` statement impossible.
    """
    spec = importlib.util.spec_from_file_location("_agentic_sdlc_drift_classifier_whitebox", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---- the plan fixture, built once per run by the real siblings ------------------------------------

FIXTURES: dict[str, Any] = {}
_SCRATCH: tempfile.TemporaryDirectory[str] | None = None
NO_GIT = "a real git is required to compile a real wave-plan@1 fixture through the real siblings"


def _run(argv: list[str], *, cwd: Path, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, capture_output=True, cwd=str(cwd), check=False, env=constructed_environment(extra))


def _mission_body() -> dict[str, Any]:
    """One complete, valid MissionContract body in the shape `mission-contract.py` requires."""
    return {
        "schema": "agentic-sdlc/mission-contract@1",
        "mission_id": MISSION_ID,
        "objective": "close slice 6 by classifying observed drift against an immutable wave plan",
        "scope": {
            "in_scope": ["skills/agentic-sdlc/tools/drift-classifier.py", "tests/test_drift_classifier.py"],
            "non_goals": ["the plan admission gate", "the auto-mode envelope"],
        },
        "constraints": ["read-only and offline", "no clock: every instant is a caller-supplied input"],
        "authority": {
            "admitted_classes": ["read-only-advisory", "owned-worktree-write"],
            "ceiling": "owned-worktree-write",
        },
        "completion_contract": {
            "success_criteria": ["the digest re-derives from every sealed document"],
            "terminal_criteria": ["one named refusal for every inadmissible input"],
        },
        # These four are mandated by `mission-contract.py`: no contract may waive them.
        "stop_conditions": sorted(
            (
                "authority-expansion-required",
                "hard-stop-drift",
                "scope-change-required",
                "unknown-or-partial-effect",
            )
        ),
        "stated_at": "2026-08-19T03:00:00Z",
        "revision": 1,
        "supersedes": None,
    }


def _submissions_body() -> dict[str, Any]:
    """One valid `workstream-submissions@1` body; the compiler seals nothing else on this module's behalf."""
    return {
        "schema": "agentic-sdlc/workstream-submissions@1",
        "submission_id": "submissions-slice-6-t7",
        "mission_id": MISSION_ID,
        "stated_at": "2026-08-19T03:45:00Z",
        "declared_concurrency": 2,
        "workstreams": [
            {
                "id": "ws-cartography",
                "objective": "map the planning artifact chain's existing tools and their digests",
                "authority_class": "read-only-advisory",
                "capability_demands": ["repository-read"],
                "dependencies": [],
                "file_custody": [],
                "worktree_custody": None,
            },
            {
                "id": "ws-classifier",
                "objective": "build the drift classifier and its tests",
                "authority_class": "owned-worktree-write",
                "capability_demands": ["git-worktree-write", "python-execution"],
                "dependencies": ["ws-cartography"],
                "file_custody": [
                    "skills/agentic-sdlc/tools/drift-classifier.py",
                    "tests/test_drift_classifier.py",
                ],
                "worktree_custody": ".worktrees/drift-classifier",
            },
        ],
    }


def setUpModule() -> None:
    """Build the plan fixture ONCE, by running the real siblings in order.

    A failure of a sibling on a valid input is RAISED rather than skipped: a sibling that cannot seal its
    own valid input is a real regression, and swallowing it would silently delete this module's coverage.
    Only a missing `git` is a skip, because that is an absent host capability rather than a defect.
    """
    global _SCRATCH
    _SCRATCH = tempfile.TemporaryDirectory(prefix="drift-classifier-fixtures-")
    scratch = Path(_SCRATCH.name).resolve()
    FIXTURES["scratch"] = scratch

    body = scratch / "mission-body.json"
    body.write_text(json.dumps(_mission_body(), indent=2), encoding="utf-8")
    done = _run([sys.executable, "-B", str(MISSION_TOOL), "define", "--contract", str(body)], cwd=scratch)
    if done.returncode != EXIT_OK:
        raise AssertionError(f"mission-contract.py define failed: {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != "defined":
        raise AssertionError(f"mission-contract.py refused a valid body: {result['reasons']}")
    mission = scratch / "mission.json"
    mission.write_bytes(canonical(result["contract"]))

    if shutil.which("git") is None:
        return
    repository = scratch / "repo"
    repository.mkdir()
    git_environment = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    step = _run(["git", "init", "--quiet", "-b", "trunk", "."], cwd=repository, extra=git_environment)
    if step.returncode != 0:
        raise AssertionError(f"git init failed: {step.stderr!r}")
    (repository / "tracked.txt").write_text("one\n", encoding="utf-8")
    for args in (
        ["add", "tracked.txt"],
        ["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "--quiet", "-m", "one"],
    ):
        step = _run(["git", *args], cwd=repository, extra=git_environment)
        if step.returncode != 0:
            raise AssertionError(f"git {args} failed: {step.stderr!r}")
    snapshot = scratch / "snapshot.json"
    done = _run(
        [
            sys.executable, "-B", str(SNAPSHOT_TOOL), "capture",
            "--repository", str(repository), "--at", "2026-08-19T03:30:00Z", "--out", str(snapshot),
        ],
        cwd=scratch,
    )
    if done.returncode != EXIT_OK:
        raise AssertionError(f"planning-snapshot.py capture failed: {done.returncode} {done.stderr!r}")
    if json.loads(done.stdout.decode("utf-8"))["verdict"] != "captured":
        raise AssertionError(f"planning-snapshot.py refused a real repository: {done.stdout!r}")

    submissions = scratch / "submissions.json"
    submissions.write_bytes(canonical(seal(_submissions_body())))
    plan = scratch / "plan.json"
    done = _run(
        [
            sys.executable, "-B", str(COMPILER_TOOL), "compile",
            "--mission", str(mission), "--snapshot", str(snapshot), "--submissions", str(submissions),
            "--at", "2026-08-19T04:00:00Z", "--out", str(plan), "--diff-out", str(scratch / "diff.json"),
        ],
        cwd=scratch,
    )
    if done.returncode != EXIT_OK:
        raise AssertionError(f"wave-plan-compiler.py compile failed: {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != "compiled":
        raise AssertionError(f"wave-plan-compiler.py refused a valid input set: {result['reasons']}")
    FIXTURES["plan"] = plan
    FIXTURES["plan_digest"] = result["plan_digest"]
    FIXTURES["plan_revision"] = result["plan"]["revision"]
    #: Asserted rather than assumed: every subject in `SUBJECT_FOR_KIND` has to be a name the REAL
    #: compiler's plan carries, or the ambiguity guard would hard-stop the table tests for the fixture's
    #: mistake instead of classifying them.
    FIXTURES["diff_subjects"] = sorted(
        {entry["subject"] for entry in json.loads((scratch / "diff.json").read_text(encoding="utf-8"))["changes"]}
    )


def tearDownModule() -> None:
    if _SCRATCH is not None:
        _SCRATCH.cleanup()


# ---- the documents this module owns --------------------------------------------------------------


def change(kind: str, subject: str) -> dict[str, Any]:
    """One observed change entry: the three fields `observed-drift@1` admits, and no fourth."""
    return {
        "kind": kind,
        "subject": subject,
        "observation": f"a fresh bounded observation found the {kind} of {subject!r} differing from the plan",
    }


def observed_body(changes: list[Any], **overrides: Any) -> dict[str, Any]:
    """One valid `observed-drift@1` body bound to the real plan; the control every negative case starts from."""
    body: dict[str, Any] = {
        "schema": OBSERVED_SCHEMA,
        "observation_id": "obs-slice-6-t7",
        "observed_at": OBSERVED_AT,
        "plan_digest": FIXTURES.get("plan_digest", fake_digest("no plan fixture")),
        "changes": changes,
    }
    body.update(overrides)
    return body


def classification_body(**overrides: Any) -> dict[str, Any]:
    """One complete, valid `drift-classification@1` body, hand-built so `verify` is checked against the
    family's published derivation rather than against the tool that wrote it."""
    body: dict[str, Any] = {
        "schema": CLASSIFICATION_SCHEMA,
        "assessments": [
            {
                "grounds": ["this test wrote this ground itself, so the tool's own sentence is not the definition"],
                "kind": "added-node",
                "observation": "a fresh bounded observation found a node the plan does not contain",
                "outcome": REPLAN,
                "subject": "ws-classifier",
            }
        ],
        "binding": {"bound": True, "ground": None, "observed_plan_digest": fake_digest("plan")},
        "classified_at": AT,
        "mission_id": MISSION_ID,
        "no_drift_reason": None,
        "observation_id": "obs-slice-6-t7",
        "observed_at": OBSERVED_AT,
        "overall_outcome": REPLAN,
        "plan_digest": fake_digest("plan"),
        "plan_revision": 1,
    }
    body.update(overrides)
    return body


class ToolCase(unittest.TestCase):
    """Spawn helpers shared by every class. Each spawn constructs its environment from an allowlist."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="drift-classifier-case-")).resolve()
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def write(self, name: str, document: Any) -> Path:
        target = self.work / name
        target.write_bytes(canonical(document))
        return target

    def spawn(self, argv: list[str]) -> subprocess.CompletedProcess[bytes]:
        return _run([sys.executable, "-B", str(TOOL), *argv], cwd=self.work)

    def result_of(self, argv: list[str], *, expect_code: int = EXIT_OK) -> dict[str, Any]:
        done = self.spawn(argv)
        self.assertEqual(done.returncode, expect_code, done.stderr.decode("utf-8", "replace"))
        result = json.loads(done.stdout.decode("utf-8"))
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        return result


class PlanCase(ToolCase):
    """A class that consumes the REAL compiled plan, and skips by name when git could not build one."""

    def setUp(self) -> None:
        if "plan" not in FIXTURES:
            self.skipTest(NO_GIT)
        super().setUp()

    def classify(self, changes: list[Any], *, expect_code: int = EXIT_OK, **overrides: Any) -> dict[str, Any]:
        observation = self.write("observed.json", seal(observed_body(changes, **overrides)))
        return self.result_of(
            ["classify", "--plan", str(FIXTURES["plan"]), "--observed", str(observation), "--at", AT],
            expect_code=expect_code,
        )

    def assert_classified(self, result: dict[str, Any]) -> dict[str, Any]:
        """The positive control every negative case in these classes starts from: no reasons at all.

        A tolerated subset of reasons would let a guard rot silently, so none is tolerated.
        """
        self.assertEqual(result["reasons"], [])
        self.assertIn(result["verdict"], (CLASSIFIED, NO_DRIFT))
        self.assertIsNotNone(result["classification"])
        return result["classification"]


class TaxonomyTableTests(PlanCase):
    """All sixteen rows, in one run, one subTest per kind."""

    def test_the_fixture_plan_names_every_subject_the_table_tests_use(self) -> None:
        """The premise of every table subtest: these subjects are names the REAL plan carries.

        Without this, a renamed workstream would turn all sixteen rows into `hard-stop` for the fixture's
        mistake and the table would still "pass" if it expected that.
        """
        plan = json.loads(FIXTURES["plan"].read_text(encoding="utf-8"))
        named = {node["node_id"] for node in plan["nodes"]}
        named.update(f"{edge['from']} -> {edge['to']}" for edge in plan["edges"])
        named.update(node["worktree_custody"] for node in plan["nodes"] if node["worktree_custody"])
        for node in plan["nodes"]:
            named.update(node["file_custody"])
        named.add(plan["mission_id"])
        self.assertEqual(sorted(set(SUBJECT_FOR_KIND.values()) - named), [])
        # The compiler's own diff spellings are the ones this module reuses, so a spelling change in the
        # sibling is caught here rather than as sixteen unexplained hard-stops.
        self.assertIn("ws-cartography -> ws-classifier", FIXTURES["diff_subjects"])

    def test_every_kind_lands_on_its_grounded_outcome(self) -> None:
        kinds = sorted(EXPECTED_TABLE)
        observed = [change(kind, SUBJECT_FOR_KIND[kind]) for kind in kinds]
        classification = self.assert_classified(self.classify(observed))
        assessments = {entry["kind"]: entry for entry in classification["assessments"]}
        self.assertEqual(sorted(assessments), kinds)
        for kind in kinds:
            outcome, anchor = EXPECTED_TABLE[kind]
            with self.subTest(kind=kind):
                entry = assessments[kind]
                self.assertEqual(entry["outcome"], outcome)
                self.assertEqual(entry["subject"], SUBJECT_FOR_KIND[kind])
                grounds = " ".join(entry["grounds"])
                self.assertIn(anchor, grounds)
                self.assertIn("issue 16:", grounds)
                # A grounded row is not an ambiguity: the safety rule's quote must NOT appear, or a row
                # that had silently become a hard-stop-by-ambiguity would read as grounded.
                self.assertNotIn(AMBIGUOUS_QUOTE, grounds)

    def test_the_table_is_total_over_the_sixteen_kinds(self) -> None:
        """Sixteen kinds, sixteen rows: an added kind with no row would hard-stop as an unknown one."""
        self.assertEqual(len(EXPECTED_TABLE), 16)
        classification = self.assert_classified(
            self.classify([change(kind, SUBJECT_FOR_KIND[kind]) for kind in sorted(EXPECTED_TABLE)])
        )
        self.assertEqual(
            [entry["outcome"] for entry in classification["assessments"] if entry["outcome"] == HARD_STOP],
            [HARD_STOP],  # exactly one: `authority`
        )

    def test_compatible_is_unreachable_and_the_residual_says_so(self) -> None:
        """A declared limit nobody checks is how a residual and the code drift apart."""
        self.assertNotIn(COMPATIBLE, {outcome for outcome, _ in EXPECTED_TABLE.values()})
        result = self.classify([change(kind, SUBJECT_FOR_KIND[kind]) for kind in sorted(EXPECTED_TABLE)])
        self.assertTrue(
            any("`compatible` is representable in this schema and unreachable" in one for one in result["residuals"]),
            result["residuals"],
        )

    def test_the_assessment_order_is_the_observed_order(self) -> None:
        """Determinism over a supplied list: the emitted order is the input's, not a set's iteration."""
        kinds = ["retry", "added-node", "gate"]
        classification = self.assert_classified(self.classify([change(k, SUBJECT_FOR_KIND[k]) for k in kinds]))
        self.assertEqual([entry["kind"] for entry in classification["assessments"]], kinds)


class SeverityFoldTests(PlanCase):
    """The overall outcome is the maximum severity, over the SEMANTIC order and not the alphabetical one."""

    def test_the_semantic_order_is_not_the_alphabetical_order(self) -> None:
        """The positive control for the test below: the two orders really do disagree on these strings."""
        self.assertNotEqual(sorted(OUTCOMES_BY_SEVERITY), list(OUTCOMES_BY_SEVERITY))
        self.assertLess(HARD_STOP, REPLAN)  # alphabetically
        self.assertGreater(OUTCOMES_BY_SEVERITY.index(HARD_STOP), OUTCOMES_BY_SEVERITY.index(REPLAN))

    def test_a_hard_stop_beside_a_replan_is_a_hard_stop(self) -> None:
        """An ALPHABETICAL maximum answers `replan-required` here; the severity maximum answers hard-stop."""
        classification = self.assert_classified(
            self.classify([change("added-node", "ws-classifier"), change("authority", "ws-cartography")])
        )
        self.assertEqual(classification["overall_outcome"], HARD_STOP)

    def test_the_fold_is_a_maximum_and_not_a_minimum(self) -> None:
        classification = self.assert_classified(
            self.classify([change("approval", MISSION_ID), change("added-node", "ws-classifier")])
        )
        self.assertEqual([entry["outcome"] for entry in classification["assessments"]], [REVALIDATION, REPLAN])
        self.assertEqual(classification["overall_outcome"], REPLAN)

    def test_the_fold_is_a_maximum_and_not_the_last_entry(self) -> None:
        """The same two changes in the other order fold to the same maximum."""
        classification = self.assert_classified(
            self.classify([change("added-node", "ws-classifier"), change("approval", MISSION_ID)])
        )
        self.assertEqual(classification["overall_outcome"], REPLAN)

    def test_one_revalidation_alone_is_not_escalated(self) -> None:
        """The fold does not invent severity either: a lone revalidation stays one."""
        classification = self.assert_classified(self.classify([change("approval", MISSION_ID)]))
        self.assertEqual(classification["overall_outcome"], REVALIDATION)

    def test_one_hard_stop_among_many_replans_still_stops(self) -> None:
        changes = [change("added-node", "ws-classifier") for _ in range(20)]
        changes.insert(11, change("authority", "ws-cartography"))
        classification = self.assert_classified(self.classify(changes))
        self.assertEqual(classification["overall_outcome"], HARD_STOP)
        self.assertEqual(len(classification["assessments"]), 21)


class AmbiguityIsHardStopTests(PlanCase):
    """issue 16:79 in four applications, each measured against the SAME positive control."""

    CONTROL = ("added-node", "ws-classifier")

    def control(self) -> dict[str, Any]:
        """The unmutated document, asserted to reach `replan-required` with no reasons at all.

        Every test below mutates exactly this document, so a guard that stopped firing would have to
        stop reaching this state too.
        """
        classification = self.assert_classified(self.classify([change(*self.CONTROL)]))
        self.assertEqual(classification["overall_outcome"], REPLAN)
        self.assertTrue(classification["binding"]["bound"])
        self.assertIsNone(classification["binding"]["ground"])
        return classification

    def only(self, classification: dict[str, Any]) -> dict[str, Any]:
        self.assertEqual(len(classification["assessments"]), 1)
        return classification["assessments"][0]

    def test_the_control_is_a_grounded_replan(self) -> None:
        entry = self.only(self.control())
        self.assertEqual(entry["outcome"], REPLAN)
        self.assertNotIn(AMBIGUOUS_QUOTE, " ".join(entry["grounds"]))

    def test_an_unknown_kind_is_hard_stop(self) -> None:
        self.control()
        classification = self.assert_classified(self.classify([change("teleported-node", "ws-classifier")]))
        entry = self.only(classification)
        self.assertEqual(entry["outcome"], HARD_STOP)
        self.assertEqual(classification["overall_outcome"], HARD_STOP)
        self.assertIn("outside the closed sixteen", " ".join(entry["grounds"]))
        self.assertIn(AMBIGUOUS_QUOTE, " ".join(entry["grounds"]))
        # The kind is still REPORTED: a hard-stop that hid what it stopped on would be unactionable.
        self.assertEqual(entry["kind"], "teleported-node")

    def test_a_kind_that_only_looks_like_a_member_is_hard_stop(self) -> None:
        """Membership is exact: casing, whitespace, and a plural are all outside the sixteen."""
        self.control()
        for spelling in ("Added-Node", "added-node ", "added-nodes", "added_node"):
            with self.subTest(spelling=spelling):
                classification = self.assert_classified(self.classify([change(spelling, "ws-classifier")]))
                self.assertEqual(classification["overall_outcome"], HARD_STOP)

    def test_a_subject_the_plan_does_not_name_is_hard_stop(self) -> None:
        self.control()
        classification = self.assert_classified(self.classify([change("added-node", "ws-not-in-this-plan")]))
        entry = self.only(classification)
        self.assertEqual(entry["outcome"], HARD_STOP)
        self.assertIn("the bound plan names no 'ws-not-in-this-plan'", " ".join(entry["grounds"]))
        self.assertIn(AMBIGUOUS_QUOTE, " ".join(entry["grounds"]))

    def test_a_plan_digest_mismatch_is_hard_stop_for_every_change(self) -> None:
        self.control()
        other = fake_digest("some other plan revision entirely")
        classification = self.assert_classified(
            self.classify([change(*self.CONTROL), change("approval", MISSION_ID)], plan_digest=other)
        )
        self.assertEqual(classification["overall_outcome"], HARD_STOP)
        self.assertFalse(classification["binding"]["bound"])
        self.assertEqual(classification["binding"]["observed_plan_digest"], other)
        self.assertIn(AMBIGUOUS_QUOTE, classification["binding"]["ground"])
        for entry in classification["assessments"]:
            with self.subTest(kind=entry["kind"]):
                # Every change inherits it: if which plan was observed is unknown, no row applies.
                self.assertEqual(entry["outcome"], HARD_STOP)
                self.assertIn("which plan these sentences are about is unknown", " ".join(entry["grounds"]))

    def test_an_empty_change_entry_is_hard_stop(self) -> None:
        self.control()
        classification = self.assert_classified(self.classify([{}]))
        entry = self.only(classification)
        self.assertEqual(entry["outcome"], HARD_STOP)
        self.assertIsNone(entry["kind"])
        self.assertIsNone(entry["subject"])
        self.assertIsNone(entry["observation"])
        self.assertIn(AMBIGUOUS_QUOTE, " ".join(entry["grounds"]))

    def test_an_unreadable_change_entry_is_hard_stop(self) -> None:
        """Every shape an entry can be malformed in lands on the same rule, not on a traceback."""
        self.control()
        base = change(*self.CONTROL)
        malformed: list[Any] = [
            {},
            [],
            "added-node",
            None,
            0,
            {**base, "extra": "a fourth field this schema does not admit"},
            {key: value for key, value in base.items() if key != "observation"},
            {**base, "kind": ""},
            {**base, "subject": None},
            {**base, "observation": 7},
        ]
        for index, entry in enumerate(malformed):
            with self.subTest(index=index, entry=entry):
                classification = self.assert_classified(self.classify([entry]))
                self.assertEqual(classification["overall_outcome"], HARD_STOP)
                self.assertIn(AMBIGUOUS_QUOTE, " ".join(classification["assessments"][0]["grounds"]))

    def test_an_ambiguity_is_an_outcome_and_never_a_refusal(self) -> None:
        """The other half of the rule: a caller at a boundary gets a document to stop on."""
        for changes in ([change("teleported-node", "ws-classifier")], [{}], [change("added-node", "nope")]):
            with self.subTest(changes=changes):
                result = self.classify(changes)
                self.assertEqual(result["verdict"], CLASSIFIED)
                self.assertEqual(result["reasons"], [])
                self.assertEqual(result["overall_outcome"], HARD_STOP)
                self.assertIsNotNone(result["classification_digest"])


class NoDriftVerdictTests(PlanCase):
    """An empty observed list is its own verdict, never a silent `compatible`."""

    def test_an_empty_list_is_the_no_drift_verdict(self) -> None:
        result = self.classify([])
        classification = self.assert_classified(result)
        self.assertEqual(result["verdict"], NO_DRIFT)
        self.assertEqual(classification["assessments"], [])
        self.assertIsNone(classification["overall_outcome"])
        self.assertIn("explicit no-drift observation", classification["no_drift_reason"])
        # The sentence names the two things it is NOT, because "nothing observed", "nothing changed", and
        # "a compatible change" are three different claims and only the first one is true here.
        self.assertIn("not the same statement as a compatible classification", classification["no_drift_reason"])
        self.assertIn("not a claim that nothing changed", classification["no_drift_reason"])
        self.assertNotIn(COMPATIBLE, str(classification["overall_outcome"]))

    def test_a_one_change_list_is_the_classified_verdict(self) -> None:
        """The positive control: `no-drift` is reachable only from an empty list."""
        result = self.classify([change("added-node", "ws-classifier")])
        classification = self.assert_classified(result)
        self.assertEqual(result["verdict"], CLASSIFIED)
        self.assertIsNone(classification["no_drift_reason"])
        self.assertEqual(classification["overall_outcome"], REPLAN)

    def test_an_empty_list_against_an_unbound_plan_is_hard_stop(self) -> None:
        """Zero observations about an unknown plan is not no-drift; it is no idea."""
        result = self.classify([], plan_digest=fake_digest("another plan"))
        classification = self.assert_classified(result)
        self.assertEqual(result["verdict"], CLASSIFIED)
        self.assertEqual(classification["overall_outcome"], HARD_STOP)
        self.assertIsNone(classification["no_drift_reason"])
        self.assertFalse(classification["binding"]["bound"])

    def test_an_absent_changes_list_is_a_refusal_not_an_empty_one(self) -> None:
        """An absent array is a malformed document, and defaulting it to `[]` would forge a no-drift."""
        body = observed_body([])
        del body["changes"]
        observation = self.write("no-changes.json", seal(body))
        result = self.result_of(
            ["classify", "--plan", str(FIXTURES["plan"]), "--observed", str(observation), "--at", AT]
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIsNone(result["classification"])
        self.assertTrue(any("closed sealed key set" in one for one in result["reasons"]), result["reasons"])


class VerifyCase(ToolCase):
    """The `verify` spawn helpers. A base class rather than a parent test class, so the two classes below
    do not re-run each other's tests."""

    def verify(self, body: dict[str, Any], *, expect: str | None = None) -> dict[str, Any]:
        document = seal(body)
        target = self.write("classification.json", document)
        argv = ["verify", "--classification", str(target)]
        if expect is not None:
            argv += ["--expect-digest", expect]
        return self.result_of(argv)

    def refuses(self, body: dict[str, Any], fragment: str) -> None:
        result = self.verify(body)
        self.assertEqual(result["verdict"], REFUSED, result)
        self.assertTrue(any(fragment in one for one in result["reasons"]), result["reasons"])
        self.assertIsNone(result["classification"])


class DigestRoundTripTests(VerifyCase):
    """`verify` over documents this module seals itself, so the tool must agree with the family's rule."""

    def test_a_hand_sealed_classification_verifies(self) -> None:
        """The positive control for every mutation below."""
        body = classification_body()
        result = self.verify(body)
        self.assertEqual(result["verdict"], VERIFIED)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["classification_digest"], expected_digest(seal(body)))
        self.assertEqual(result["overall_outcome"], REPLAN)

    def test_expect_digest_closes_the_loop(self) -> None:
        body = classification_body()
        result = self.verify(body, expect=expected_digest(seal(body)))
        self.assertEqual(result["verdict"], VERIFIED)

    def test_a_wrong_expect_digest_is_refused(self) -> None:
        result = self.verify(classification_body(), expect=fake_digest("some other document"))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertTrue(any("--expect-digest named" in one for one in result["reasons"]), result["reasons"])

    def test_a_malformed_expect_digest_is_an_argument_error(self) -> None:
        target = self.write("classification.json", seal(classification_body()))
        done = self.spawn(["verify", "--classification", str(target), "--expect-digest", "not-a-digest"])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn("--expect-digest", done.stderr.decode("utf-8"))

    def test_an_edited_field_breaks_the_digest(self) -> None:
        document = seal(classification_body())
        document["classified_at"] = "2026-08-19T07:00:00Z"
        target = self.write("edited.json", document)
        result = self.result_of(["verify", "--classification", str(target)])
        self.assertEqual(result["verdict"], REFUSED)
        self.assertTrue(any("does not re-derive" in one for one in result["reasons"]), result["reasons"])

    def test_an_added_key_is_outside_the_closed_set(self) -> None:
        document = seal(classification_body())
        document["extra"] = "a field this schema does not admit"
        target = self.write("extra.json", document)
        result = self.result_of(["verify", "--classification", str(target)])
        self.assertEqual(result["verdict"], REFUSED)
        self.assertTrue(any("closed sealed key set" in one for one in result["reasons"]), result["reasons"])


class VerifyCrossCheckTests(VerifyCase):
    """The cross-checks that make `verify` more than a digest re-derivation.

    Each mutation is RE-SEALED, so the digest is correct and only the cross-check can catch it. That is
    the whole point: a consumer holding a forged-but-self-consistent document must still be told.
    """

    def test_a_downgraded_overall_outcome_is_refused(self) -> None:
        self.verify(classification_body())  # positive control
        body = classification_body(
            assessments=[
                classification_body()["assessments"][0],
                {
                    "grounds": ["this test wrote this ground itself"],
                    "kind": "authority",
                    "observation": "the node's admitted authority class differs from the plan's",
                    "outcome": HARD_STOP,
                    "subject": "ws-cartography",
                },
            ],
            overall_outcome=REPLAN,
        )
        self.refuses(body, "the maximum severity among")

    def test_an_upgraded_overall_outcome_is_refused(self) -> None:
        """The fold is checked in both directions: inventing severity is as wrong as hiding it."""
        self.refuses(classification_body(overall_outcome=HARD_STOP), "the maximum severity among")

    def test_a_no_drift_reason_beside_an_assessment_is_refused(self) -> None:
        self.refuses(classification_body(no_drift_reason="nothing to see here"), "still carries the")

    def test_an_empty_assessment_list_with_an_outcome_is_refused(self) -> None:
        self.refuses(
            classification_body(assessments=[], overall_outcome=COMPATIBLE, no_drift_reason=None),
            "an outcome is a statement about a change",
        )

    def test_an_empty_assessment_list_without_the_fixed_sentence_is_refused(self) -> None:
        self.refuses(
            classification_body(assessments=[], overall_outcome=None, no_drift_reason="all clear"),
            "one fixed sentence",
        )

    def test_an_unbound_observation_that_is_not_hard_stop_is_refused(self) -> None:
        body = classification_body(
            assessments=[],
            overall_outcome=None,
            no_drift_reason=None,
            binding={"bound": False, "ground": "the digests disagree", "observed_plan_digest": fake_digest("other")},
        )
        self.refuses(body, "zero observations about an unknown plan")

    def test_a_bound_observation_carrying_a_ground_is_refused(self) -> None:
        body = classification_body(
            binding={"bound": True, "ground": "the digests disagree", "observed_plan_digest": fake_digest("plan")}
        )
        self.refuses(body, "a ground here is the record of an ambiguity")

    def test_an_unbound_observation_with_no_ground_is_refused(self) -> None:
        body = classification_body(
            binding={"bound": False, "ground": None, "observed_plan_digest": fake_digest("other")},
            assessments=[{**classification_body()["assessments"][0], "outcome": HARD_STOP}],
            overall_outcome=HARD_STOP,
        )
        self.refuses(body, "must record why the plan it watched is unknown")

    def test_an_unread_entry_classified_below_hard_stop_is_refused(self) -> None:
        """The safety rule's own output is checked on the way back in, not only on the way out."""
        body = classification_body(
            assessments=[{**classification_body()["assessments"][0], "kind": None}], overall_outcome=REPLAN
        )
        self.refuses(body, "is the safety rule's own case")

    def test_an_outcome_outside_the_four_is_refused(self) -> None:
        body = classification_body(
            assessments=[{**classification_body()["assessments"][0], "outcome": "probably-fine"}],
            overall_outcome="probably-fine",
        )
        self.refuses(body, "is not one of")

    def test_an_assessment_that_is_not_the_closed_key_set_is_refused(self) -> None:
        """The PER-ASSESSMENT closed-key-set check, distinct from the classification's own top-level
        closed key set (`DigestRoundTripTests.test_an_added_key_is_outside_the_closed_set`): one
        assessment ENTRY missing a key or carrying an unrecognised one must itself be refused, not
        merely tolerated as an oddly-shaped but readable entry."""
        control = self.verify(classification_body())
        self.assertEqual(control["verdict"], VERIFIED, control)
        entry = classification_body()["assessments"][0]
        for label, mutated_entry in (
            ("missing a key", {key: value for key, value in entry.items() if key != "observation"}),
            ("an unrecognised key", {**entry, "confidence": "high"}),
        ):
            with self.subTest(shape=label):
                self.refuses(
                    classification_body(assessments=[mutated_entry]), "is not a JSON object of exactly"
                )

    def test_an_assessment_with_no_grounds_is_refused(self) -> None:
        body = classification_body(assessments=[{**classification_body()["assessments"][0], "grounds": []}])
        self.refuses(body, "an outcome with no ground is an assertion")

    def test_a_bound_flip_that_disagrees_with_its_own_digests_is_refused(self) -> None:
        """Blocker 1's proof: `bound` flipped to True while the binding's own `observed_plan_digest`
        still disagrees with `plan_digest`. Nothing in the old chain ever checked that equality at all --
        `bound` is exactly that equality, not a separate opinion."""
        body = classification_body(
            binding={"bound": True, "ground": None, "observed_plan_digest": fake_digest("some other plan")}
        )
        self.refuses(body, "bound is exactly that digest equality")

    def test_an_unbound_binding_with_downgraded_entries_is_refused(self) -> None:
        """Blocker 1's other half: the unbound rule lived only in the `elif` arm reached when the
        assessment list was empty, so a non-empty list escaped it entirely. A genuinely unbound binding
        (the digests really do disagree) must still force every outcome, and overall, to hard-stop --
        `added-node`'s own table floor is `replan-required`, so this is not caught by the kind floor."""
        entry = classification_body()["assessments"][0]  # kind "added-node"
        body = classification_body(
            assessments=[{**entry, "outcome": REPLAN}],
            overall_outcome=REPLAN,
            binding={"bound": False, "ground": "the digests disagree", "observed_plan_digest": fake_digest("other")},
        )
        self.refuses(body, "hard-stop in every assessment and overall")

    def test_a_genuinely_unbound_hard_stop_document_verifies(self) -> None:
        """The positive control for both halves above: a real unbound classification -- every outcome and
        overall hard-stop, and the binding's digest genuinely disagreeing with `bound: False` -- verifies
        cleanly, so the two guards above are catching the tamper and not the shape."""
        entry = classification_body()["assessments"][0]
        body = classification_body(
            assessments=[{**entry, "outcome": HARD_STOP}],
            overall_outcome=HARD_STOP,
            binding={"bound": False, "ground": "the digests disagree", "observed_plan_digest": fake_digest("other")},
        )
        result = self.verify(body)
        self.assertEqual(result["verdict"], VERIFIED, result)
        self.assertEqual(result["reasons"], [])

    def test_a_downgraded_entry_below_its_kind_floor_is_refused(self) -> None:
        """Blocker 2: `classify_entry` can only ever emit `TABLE[kind][0]` or escalate it to hard-stop, so
        an outcome recorded below the table's own floor for its kind is a content-derivable lower bound
        this tool can check without the plan the entry was classified against."""
        body = classification_body(
            assessments=[
                {
                    "grounds": ["this test wrote this ground itself"],
                    "kind": "authority",
                    "observation": "the node's admitted authority class differs from the plan's",
                    "outcome": COMPATIBLE,
                    "subject": "ws-cartography",
                }
            ],
            overall_outcome=COMPATIBLE,
        )
        self.refuses(body, "a lower severity")

    def test_every_entry_and_overall_downgraded_together_is_still_refused(self) -> None:
        """Blocker 2's exact proof: every entry downgraded to `compatible`, WITH `overall_outcome` moved
        to match them. That defeats the pre-existing fold check (`overall == expected`), because both
        sides moved together and stayed consistent with each other; only the per-kind floor, which has no
        opinion about the fold, still catches each entry independently."""
        body = classification_body(
            assessments=[
                {
                    "grounds": ["this test wrote this ground itself"],
                    "kind": "authority",
                    "observation": "the node's admitted authority class differs from the plan's",
                    "outcome": COMPATIBLE,
                    "subject": "ws-cartography",
                },
                {
                    "grounds": ["this test wrote this ground itself"],
                    "kind": "budget",
                    "observation": "the workstream's budget differs from the plan's",
                    "outcome": COMPATIBLE,
                    "subject": "ws-classifier",
                },
            ],
            overall_outcome=COMPATIBLE,
        )
        result = self.verify(body)
        self.assertEqual(result["verdict"], REFUSED, result)
        self.assertEqual(sum("a lower severity" in one for one in result["reasons"]), 2, result["reasons"])
        self.assertIsNone(result["classification"])

    def test_an_unknown_kind_entry_downgraded_from_hard_stop_is_refused(self) -> None:
        """A kind outside the closed sixteen must be hard-stop; downgrading it is checkable without the
        plan the closed sixteen are defined relative to."""
        body = classification_body(
            assessments=[
                {
                    "grounds": ["this test wrote this ground itself"],
                    "kind": "teleported-node",
                    "observation": "an observation naming a kind outside the closed sixteen",
                    "outcome": REPLAN,
                    "subject": "ws-classifier",
                }
            ],
            overall_outcome=REPLAN,
        )
        self.refuses(body, "is outside the closed sixteen")


class ClassifyRoundTripTests(PlanCase):
    """What `classify` seals is what `verify` admits, digest and all."""

    def test_a_classified_document_verifies_under_its_own_digest(self) -> None:
        result = self.classify([change("added-node", "ws-classifier"), change("authority", "ws-cartography")])
        classification = self.assert_classified(result)
        # The family's derivation, computed HERE: the tool agreeing with itself would prove nothing.
        self.assertEqual(result["classification_digest"], expected_digest(classification))
        target = self.write("sealed.json", classification)
        verified = self.result_of(
            ["verify", "--classification", str(target), "--expect-digest", result["classification_digest"]]
        )
        self.assertEqual(verified["verdict"], VERIFIED)
        self.assertEqual(verified["reasons"], [])
        self.assertEqual(verified["overall_outcome"], HARD_STOP)

    def test_a_no_drift_document_verifies_too(self) -> None:
        result = self.classify([])
        classification = self.assert_classified(result)
        target = self.write("no-drift.json", classification)
        verified = self.result_of(["verify", "--classification", str(target)])
        self.assertEqual(verified["verdict"], VERIFIED)
        self.assertIsNone(verified["overall_outcome"])

    def test_the_same_inputs_seal_the_same_bytes(self) -> None:
        """Determinism over the SEALED document, across two processes with different hash seeds.

        The positive control is the assertion that the two seeds really do change this interpreter's
        string hashing: comparing two runs of a tool whose randomization was disabled proves nothing.
        """
        self.assertNotEqual(
            _run([sys.executable, "-c", "print(hash('drift'))"], cwd=self.work, extra={"PYTHONHASHSEED": "1"}).stdout,
            _run([sys.executable, "-c", "print(hash('drift'))"], cwd=self.work, extra={"PYTHONHASHSEED": "2"}).stdout,
        )
        observation = self.write(
            "observed.json", seal(observed_body([change(k, SUBJECT_FOR_KIND[k]) for k in sorted(EXPECTED_TABLE)]))
        )
        argv = [
            sys.executable, "-B", str(TOOL), "classify", "--plan", str(FIXTURES["plan"]),
            "--observed", str(observation), "--at", AT,
        ]
        first = _run(argv, cwd=self.work, extra={"PYTHONHASHSEED": "1"})
        second = _run(argv, cwd=self.work, extra={"PYTHONHASHSEED": "2"})
        self.assertEqual(first.returncode, EXIT_OK, first.stderr)
        self.assertEqual(
            canonical(json.loads(first.stdout)["classification"]),
            canonical(json.loads(second.stdout)["classification"]),
        )
        self.assertEqual(
            json.loads(first.stdout)["classification_digest"], json.loads(second.stdout)["classification_digest"]
        )


class ClassifySelfReadbackTests(unittest.TestCase):
    """`classify` reads its OWN synthesized candidate back through `check_classification` and
    `check_digest` before sealing it (module docstring: "A synthesis bug then becomes a refusal rather
    than a sealed document `verify` would later reject"). Nothing else in this file proves that is an
    ACTIVE property rather than aspirational prose: every other `classify` test hands it a valid input,
    which the real derivation never gets wrong, so the self-readback never has anything to catch. This
    class imports the module directly and corrupts a synthesized candidate the way a synthesis bug
    would, so the self-readback either catches it -- proving it runs -- or this test fails.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if "plan" not in FIXTURES:
            raise unittest.SkipTest(NO_GIT)
        cls.module = _load_module()

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="drift-classifier-readback-")).resolve()
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def test_a_corrupted_synthesis_is_caught_before_sealing_not_after(self) -> None:
        module = self.module
        observation = self.work / "observed.json"
        observation.write_bytes(canonical(seal(observed_body([change("authority", "ws-cartography")]))))
        args = argparse.Namespace(
            command="classify", plan=str(FIXTURES["plan"]), observed=str(observation), at=AT, out=None,
        )

        # The CONTROL: the real, uncorrupted derivation classifies cleanly.
        control_result, _ = module.derive_command(args)
        self.assertEqual(control_result["verdict"], module.VERDICT_CLASSIFIED, control_result["reasons"])

        real_synthesize = module.synthesize_classification

        def corrupted(**kwargs: Any) -> dict[str, Any]:
            """Stand in for a synthesis bug: agree with everything real EXCEPT the fold, so the
            candidate is self-consistent (its own digest re-derives) but wrong in exactly the way
            `check_classification`'s cross-check #1 exists to catch."""
            candidate = dict(real_synthesize(**kwargs))
            candidate["overall_outcome"] = COMPATIBLE
            body = {key: value for key, value in candidate.items() if key != module.DIGEST_KEY}
            candidate[module.DIGEST_KEY] = module.document_digest(body)
            return candidate

        module.synthesize_classification = corrupted
        try:
            corrupted_result, _ = module.derive_command(args)
        finally:
            module.synthesize_classification = real_synthesize

        self.assertEqual(
            corrupted_result["verdict"], module.VERDICT_REFUSED,
            "a corrupted synthesis was sealed and published rather than caught by the self-readback",
        )
        self.assertIsNone(
            corrupted_result["classification"], "a refused self-readback still published a document"
        )
        self.assertTrue(
            any("the maximum severity among" in reason for reason in corrupted_result["reasons"]),
            corrupted_result["reasons"],
        )


class WriteDocumentTests(unittest.TestCase):
    """`write_document`'s own O_EXCL create, isolated from `check_output_path`'s earlier pre-flight
    refusal. `OutputPathTests.test_an_occupied_out_is_refused_and_never_replaced` below proves the CLI
    refuses an occupied `--out` before anything is derived; it can never reach `write_document` with a
    target that already exists, because that pre-flight check always intercepts first. Calling
    `write_document` directly is coverage for the real O_EXCL race the module docstring says the write
    is safe against: a genuine concurrent racer is not reproduced here, but the exclusive-create
    behaviour itself -- refuse rather than clobber when the target exists at open() time -- is
    exercised and proven correct.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="drift-classifier-write-")).resolve()
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def test_write_document_refuses_a_target_that_already_exists(self) -> None:
        """The racer's file -- created between `check_output_path`'s pre-flight and this open() --
        must survive untouched."""
        module = self.module
        target = self.work / "classification.json"
        target.write_bytes(b"a racer's document\n")
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            state = module.write_document(target, classification_body())
        self.assertEqual(state, module.WRITE_NOTHING, "an occupied target was written through anyway")
        self.assertEqual(target.read_bytes(), b"a racer's document\n", "the racer's file was clobbered")
        self.assertIn("cannot create the --out path", captured.getvalue())
        self.assertIn("nothing was", captured.getvalue())

    def test_write_document_creates_a_fresh_target(self) -> None:
        """The positive control: a target that does NOT exist really is written, and with the exact
        canonical bytes -- so the refusal above is about the occupied path, not a write that never
        works at all."""
        module = self.module
        target = self.work / "classification.json"
        body = classification_body()
        state = module.write_document(target, body)
        self.assertEqual(state, module.WRITE_DONE)
        self.assertEqual(target.read_bytes(), canonical(body))


class OutputPathTests(PlanCase):
    """`--out` is exclusive, and a refusal writes nothing at all."""

    def test_out_writes_the_canonical_bytes(self) -> None:
        observation = self.write("observed.json", seal(observed_body([change("added-node", "ws-classifier")])))
        target = self.work / "out" / "classification.json"
        target.parent.mkdir()
        result = self.result_of(
            [
                "classify", "--plan", str(FIXTURES["plan"]), "--observed", str(observation),
                "--at", AT, "--out", str(target),
            ]
        )
        self.assertEqual(result["out"], str(target))
        self.assertEqual(target.read_bytes(), canonical(result["classification"]))

    def test_an_occupied_out_is_refused_and_never_replaced(self) -> None:
        observation = self.write("observed.json", seal(observed_body([change("added-node", "ws-classifier")])))
        target = self.work / "taken.json"
        target.write_text("someone else's document\n", encoding="utf-8")
        result = self.result_of(
            [
                "classify", "--plan", str(FIXTURES["plan"]), "--observed", str(observation),
                "--at", AT, "--out", str(target),
            ]
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIsNone(result["classification"])
        self.assertIsNone(result["out"])
        self.assertEqual(target.read_text(encoding="utf-8"), "someone else's document\n")

    def test_a_refusal_writes_nothing(self) -> None:
        """A refused run leaves no file, so a `--out` path is safe to reuse after one."""
        observation = self.write("observed.json", seal(observed_body([change("added-node", "x")], observation_id="")))
        target = self.work / "never.json"
        result = self.result_of(
            [
                "classify", "--plan", str(FIXTURES["plan"]), "--observed", str(observation),
                "--at", AT, "--out", str(target),
            ]
        )
        self.assertEqual(result["verdict"], REFUSED)
        self.assertFalse(target.exists())


class InstantGuardTests(ToolCase):
    """`--at` is matched with `[0-9]`, never `\\d`, and the guard runs before any file is read."""

    def test_an_arabic_indic_digit_instant_is_refused(self) -> None:
        """`\\d` accepts these; `[0-9]` does not, and a digest-bound instant must be one spelling only."""
        arabic = "٢٠٢٦-٠٨-١٩T٠٦:٠٠:٠٠Z"
        done = self.spawn(["classify", "--plan", "no-such-plan.json", "--observed", "no-such.json", "--at", arabic])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn("--at", done.stderr.decode("utf-8"))
        self.assertIn("YYYY-MM-DDTHH:MM:SSZ", done.stderr.decode("utf-8"))

    def test_the_instant_guard_runs_before_any_file_is_read(self) -> None:
        """Both paths below do not exist; which message arrives says which check ran first."""
        done = self.spawn(["classify", "--plan", "missing.json", "--observed", "missing.json", "--at", "yesterday"])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn("--at 'yesterday'", done.stderr.decode("utf-8"))
        # The positive control: with a VALID instant the same run reaches the file read and says so.
        done = self.spawn(["classify", "--plan", "missing.json", "--observed", "missing.json", "--at", AT])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn("cannot read the wave plan", done.stderr.decode("utf-8"))

    def test_a_near_miss_instant_is_refused(self) -> None:
        for spelling in ("2026-08-19T06:00:00", "2026-08-19 06:00:00Z", "2026-8-19T06:00:00Z", "2026-08-19T06:00Z"):
            with self.subTest(spelling=spelling):
                done = self.spawn(["classify", "--plan", "m.json", "--observed", "m.json", "--at", spelling])
                self.assertEqual(done.returncode, EXIT_INPUT)
                self.assertIn("--at", done.stderr.decode("utf-8"))


class UnusableInputTests(ToolCase):
    """Exit 2 covers a file that cannot be read as ONE JSON object, at every position."""

    def plausible_plan(self) -> Path:
        """A JSON object that PARSES, so a refusal about the observation is reached rather than shadowed."""
        return self.write("plan.json", {"schema": PLAN_SCHEMA})

    def test_a_nested_non_finite_number_is_refused(self) -> None:
        """`1e400` never reaches `parse_constant`: it overflows during parsing, so only the walk sees it."""
        positions = {
            "in-a-list": {"schema": OBSERVED_SCHEMA, "changes": [1e400]},
            "deeply-nested": {"schema": OBSERVED_SCHEMA, "changes": [{"a": {"b": {"c": [{"d": 1e400}]}}}]},
            "beside-the-envelope": {"schema": OBSERVED_SCHEMA, "observed_at": OBSERVED_AT, "budget": 1e400},
        }
        for name, document in positions.items():
            with self.subTest(position=name):
                # Written as a literal rather than through `canonical`, which refuses infinities itself.
                target = self.work / f"{name}.json"
                target.write_text(json.dumps(document).replace("Infinity", "1e400"), encoding="utf-8")
                done = self.spawn(
                    ["classify", "--plan", str(self.plausible_plan()), "--observed", str(target), "--at", AT]
                )
                self.assertEqual(done.returncode, EXIT_INPUT, done.stdout)
                self.assertIn("non-finite number", done.stderr.decode("utf-8"))

    def test_a_non_finite_constant_token_is_refused(self) -> None:
        target = self.work / "nan.json"
        target.write_text('{"schema": "x", "changes": [NaN]}', encoding="utf-8")
        done = self.spawn(["classify", "--plan", str(self.plausible_plan()), "--observed", str(target), "--at", AT])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn("non-finite JSON constant NaN", done.stderr.decode("utf-8"))

    def test_a_finite_document_at_the_same_positions_is_not_refused(self) -> None:
        """The positive control for the two tests above: the shape is fine, only the number was not."""
        nested = {"schema": OBSERVED_SCHEMA, "changes": [{"a": {"b": {"c": [{"d": 1e40}]}}}]}
        target = self.write("finite.json", nested)
        done = self.spawn(["classify", "--plan", str(self.plausible_plan()), "--observed", str(target), "--at", AT])
        self.assertEqual(done.returncode, EXIT_OK)
        self.assertEqual(json.loads(done.stdout)["verdict"], REFUSED)

    def test_a_repeated_json_key_is_refused(self) -> None:
        target = self.work / "twice.json"
        target.write_text('{"schema": "x", "changes": [], "changes": [1]}', encoding="utf-8")
        done = self.spawn(["classify", "--plan", str(self.plausible_plan()), "--observed", str(target), "--at", AT])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn("repeats the JSON key 'changes'", done.stderr.decode("utf-8"))

    def test_a_directory_is_refused_before_it_is_opened(self) -> None:
        done = self.spawn(["classify", "--plan", str(self.work), "--observed", str(self.work), "--at", AT])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn("is not a regular file", done.stderr.decode("utf-8"))

    def test_a_json_array_is_not_a_document(self) -> None:
        target = self.work / "array.json"
        target.write_text("[]", encoding="utf-8")
        done = self.spawn(["classify", "--plan", str(target), "--observed", str(target), "--at", AT])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn("is not a JSON object", done.stderr.decode("utf-8"))

    def test_a_wrong_schema_string_is_a_reason_and_not_an_exit_code(self) -> None:
        """The file was readable and was one object, so the question WAS asked; the answer is refused."""
        plan = self.write("plan.json", seal({"schema": "agentic-sdlc/plan-diff@1"}))
        observation = self.write("observed.json", seal(observed_body([])))
        result = self.result_of(["classify", "--plan", str(plan), "--observed", str(observation), "--at", AT])
        self.assertEqual(result["verdict"], REFUSED)
        self.assertTrue(any("declares schema" in one for one in result["reasons"]), result["reasons"])


class AmbientDisciplineTests(unittest.TestCase):
    """The tool reads no clock, no environment, and no subprocess. Asserted over the AST, not by grep.

    A substring search cannot do this job: the tool's own docstring contains the substring `environ`
    -- inside the ordinary word "environment", in the very sentence promising there is no environment
    read -- so a plain text search for that string would false-positive on the docstring disclaiming
    it. The AST walk below looks for an actual `.environ`/`.getenv`/`.get_exec_path` ATTRIBUTE access,
    which "environment" in prose is not.
    """

    FORBIDDEN_MODULES = ("time", "datetime", "subprocess", "socket", "urllib", "random", "shutil")

    def test_the_tool_imports_no_clock_network_or_subprocess_module(self) -> None:
        tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(sorted(imported & set(self.FORBIDDEN_MODULES)), [])
        # The positive control: the walk really does see this module's imports.
        self.assertIn("hashlib", imported)

    def test_the_tool_reads_no_environment_variable(self) -> None:
        tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        reached = [
            ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv", "get_exec_path")
        ]
        self.assertEqual(reached, [])

    def test_this_module_reaches_for_the_environment_only_in_one_function(self) -> None:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        allowed = "constructed_environment"
        offenders: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name == allowed:
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr == "environ":
                    offenders.append(node.name)
        # `os.devnull` is not an environment read; `os.environ` is, and only the allowlist builder may.
        self.assertEqual(sorted(set(offenders)), [])


class UndeliveredDocumentTests(PlanCase):
    """A derived classification that could not be COPIED to `--out` is exit 1, not exit 0 and not exit 4."""

    def test_an_unwritable_destination_is_a_delivery_failure(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root ignores the directory mode this test uses to make the create fail")
        observation = self.write("observed.json", seal(observed_body([change("added-node", "ws-classifier")])))
        closed = self.work / "closed"
        closed.mkdir()
        target = closed / "classification.json"
        closed.chmod(0o500)
        self.addCleanup(closed.chmod, 0o700)
        result = self.result_of(
            [
                "classify", "--plan", str(FIXTURES["plan"]), "--observed", str(observation),
                "--at", AT, "--out", str(target),
            ],
            expect_code=EXIT_INTERNAL,
        )
        # The document was DERIVED and is published, so nothing is lost but the file; `out` stays null
        # because a null there must always mean no file of this run's making exists.
        self.assertEqual(result["verdict"], CLASSIFIED)
        self.assertEqual(result["exit_code"], EXIT_INTERNAL)
        self.assertIsNotNone(result["classification"])
        self.assertIsNone(result["out"])
        self.assertFalse(target.exists())
