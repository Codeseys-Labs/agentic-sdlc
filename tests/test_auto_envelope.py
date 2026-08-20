"""Tests for the AutoEnvelope schema: its closed shape, its default-off refusals, its one digest.

Eight kinds of test live here and they check different things.

The SIBLING FIXTURES are built by RUNNING `mission-contract.py define`, `planning-snapshot.py
capture`, and `wave-plan-compiler.py compile` once per test run, into one module-level scratch
directory. Nothing here hand-writes a guess of a sibling's sealed form. The AutoEnvelope binds a plan
digest and a snapshot digest, and a hand-invented pair would prove only that this module can invent
64 hex characters; one class binds the REAL digests those three tools produced. Building them needs a
real `git`, so that class skips with a named reason when git is absent, and every other class -- whose
subject is the envelope's own shape, not the identity of what it binds -- runs everywhere on
well-formed stand-in digests.

The CLOSED-SHAPE tests are the load-bearing half, because "default-off" in this schema means an
ABSENCE REFUSES. There is one deletion test per body field and one per nested field, and each asserts
the field's own name appears in the refusal: a schema that answered "invalid envelope" would pass a
laxer test while telling an operator nothing. Present-but-empty is tested in both directions --
`tool_allowlist` and `graph_change_allowlist` may be `[]` because empty is their narrowest reading,
while `checkpoints` and `stop_rules` may not -- because those four are the only place this schema
tolerates an empty value and a drift either way is a permission or a false refusal.

EVERY NEGATIVE ASSERTION CARRIES A POSITIVE CONTROL. `assert_defined` tolerates NO reasons at all, and
every class asserts the unmutated control reaches `defined` before it mutates anything. Where a
refusal depends on a cross-field combination, the control is the OTHER combination: the write effect
that is refused under a read-only ladder is asserted ADMITTED under the write ladder, so a check that
stopped discriminating would fail rather than keep passing.

The LADDER tests are about order, not membership. The ladder's order is not the alphabet's
(`owned-worktree-write` sorts before `read-only-advisory`), so a prefix check and an ascending-set
check are different questions, and a gap in the prefix, a non-prefix subset, and a rung above the
auto-mode ceiling are three separate refusals.

The PARTITION test is behavioral rather than a constant comparison: each of the compiler's sixteen
PlanDiff change kinds is offered to the tool one at a time, and exactly four are admitted while
exactly twelve are refused. Comparing this module's copy of the vocabulary against the tool's would
pass with both sides drifted the same way; running all sixteen through the tool cannot.

The WINDOW tests pin ordering, calendar validity, retroactivity, and the duration bound AT its
boundary: a window of exactly `MAX_VALIDITY_SECONDS` is admitted and one second more is refused, so a
bound that quietly moved would fail on one side or the other.

The INSTANT tests exist for one character class: the guard is `[0-9]`, not `\\d`, so an Arabic-Indic
digit string that `\\d` would happily accept must be refused -- in `stated_at` and in both ends of the
window.

The NON-FINITE tests put `1e400` at NESTED positions -- inside a list, and inside an object several
levels down -- because `parse_constant` never sees that literal: it is an ordinary JSON number that
overflows during parsing, and the post-parse ITERATIVE walk is the only thing that catches it. The
`NaN` spelling is tested separately because it takes the other path.

The DIGEST tests hand-seal an `auto-envelope@1` with this module's OWN canonical helpers and hand it to
`verify`, so the tool is proved to agree with the family's published derivation rather than with
itself. `--expect-digest` closes the loop a later approval or transition check will actually use.

The DETERMINISM and AMBIENT-INPUT tests vary `PYTHONHASHSEED` between two runs and compare BYTES, with
their own positive control that the two seeds really do change this interpreter's string hashing, and
read the tool with `ast` to assert it reaches for no clock and no environment variable. A substring
search cannot do the second job: the tool's docstring says the words "no clock" and "environment
variable" in the sentences promising it does neither.

Every subprocess spawn in this module CONSTRUCTS its environment from an allowlist rather than
inheriting the developer's shell, so a variable a future version began reading could not silently
reach it.

THE TRANSITION-ADMISSION HALF adds one class per REFUSAL FAMILY, and each class asserts the unmutated
pair -- one sealed envelope, one proposed transition, one instant -- is ADMITTED before it mutates
anything. Where a refusal is a membership test, the positive control is the OTHER side of the same
list: the tool class the narrowed envelope refuses is asserted admitted by the wider envelope, so a
membership check that stopped discriminating fails instead of quietly passing.

The WINDOW BOUNDARY is tested at BOTH edges, in both directions. Admission requires `--at` strictly
inside the envelope's window, so `at == not_before` and `at == not_after` are refusals with their own
distinct sentences, while one second inside each edge is admitted. A bound that quietly became
inclusive would fail on one side; a bound that quietly narrowed further would fail on the other.

The STOP-RULE PARTITION is behavioral, like the change-kind partition above: all sixteen change kinds
are offered one at a time, and the twelve widenings are refused in TWO groups -- once for "this
envelope's allowlist does not name it" and once for "an always-stop condition names it" -- while the
four autonomous kinds are refused in neither. The second group exists to survive a widening of the
first, so a test that only counted verdicts would not notice it disappearing.

The RECEIPT tests hand-seal an `autonomous-transition-receipt@1` with this module's OWN canonical
helpers and hand it to `verify-receipt`, so the receipt derivation is proved to agree with the
family's published form rather than with itself, and they assert the `--out` file is BYTE-IDENTICAL to
the receipt inside the result document -- one receipt, two channels, never two versions.
"""

from __future__ import annotations

import ast
import hashlib
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
TOOL = TOOLS / "auto-envelope.py"
MISSION_TOOL = TOOLS / "mission-contract.py"
SNAPSHOT_TOOL = TOOLS / "planning-snapshot.py"
COMPILER_TOOL = TOOLS / "wave-plan-compiler.py"

ENVELOPE_SCHEMA = "agentic-sdlc/auto-envelope@1"
RESULT_SCHEMA = "agentic-sdlc/auto-envelope-result@1"

DEFINED = "defined"
VERIFIED = "verified"
REFUSED = "refused"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

STATED_AT = "2026-08-20T00:00:00Z"
NOT_BEFORE = "2026-08-20T01:00:00Z"
NOT_AFTER = "2026-08-20T09:00:00Z"

#: The tool's own bounds, re-expressed so a test can sit ON a boundary. Re-expressed rather than
#: imported: the tool's name has a hyphen, so no `import` statement can name it, and a shared constant
#: would make the boundary assertions vacuous.
MAX_VALIDITY_SECONDS = 86400
MAX_CONCURRENT_NODES_CEILING = 4
MAX_ATTEMPTS_PER_NODE_CEILING = 2
MAX_TOTAL_RETRIES_CEILING = 8

AUTHORITY_CLASSES = (
    "read-only-advisory",
    "owned-worktree-write",
    "authorized-fan-in",
    "outward-effect",
)
READ_ONLY_LADDER = ["read-only-advisory"]
WRITE_LADDER = ["read-only-advisory", "owned-worktree-write"]

#: The compiler's sixteen PlanDiff change kinds, split into the four an autonomous transition may
#: cause and the twelve it may not. The split is asserted BEHAVIORALLY below, one kind per run.
CHANGE_KINDS = (
    "added-edge", "added-node", "approval", "artifact", "authority", "budget", "changed-node",
    "custody-boundary", "egress", "gate", "removed-edge", "removed-node", "retry", "route-constraint",
    "stop-rule", "terminal-criterion",
)
AUTONOMOUS_CHANGE_KINDS = ("added-edge", "added-node", "changed-node", "retry")

MANDATORY_CHECKPOINT_KINDS = (
    "authority-inheritance",
    "budget-remaining",
    "drift-recheck",
    "evidence-recheck",
)
STOP_RULE_KINDS = (
    "ambiguous-ownership",
    "authority-expansion",
    "budget-exhaustion",
    "corrupted-evidence",
    "credential-or-security-boundary-change",
    "expired-validity",
    "failed-drift-classification",
    "lost-attribution",
    "missing-transition-receipt",
    "new-destructive-or-outward-effect",
    "partial-or-unknown-prior-effect",
    "publication-push-pr-merge-deployment",
)
NON_DELEGABLE_EFFECTS = (
    "credential-access",
    "destructive-action",
    "egress-network-call",
    "fan-in-mutation",
    "outward-effect",
    "permission-change",
)

#: The tool reads no environment variable at all, so nothing needs scrubbing by name; every spawn still
#: CONSTRUCTS its environment from this function rather than passing `os.environ` through.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")

NO_GIT = "a real git is required to build the sibling WavePlan and PlanningSnapshot fixtures"


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
    """The digest contract, re-expressed: sha256 over `canonical(document minus the digest key)`."""
    body = {key: value for key, value in sealed.items() if key != "digest"}
    return hashlib.sha256(canonical(body)).hexdigest()


def seal(body: dict[str, Any]) -> dict[str, Any]:
    """Add the one derived key, the way a caller of this family would."""
    sealed = dict(body)
    sealed["digest"] = expected_digest(body)
    return sealed


def fake_digest(label: str) -> str:
    """A well-formed sha256 standing for a document a shape test does not need to build."""
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


# ---- the sibling fixtures, built once per run -----------------------------------------------------

FIXTURES: dict[str, Any] = {}
_SCRATCH: tempfile.TemporaryDirectory[str] | None = None


def _run(argv: list[str], *, cwd: Path, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, capture_output=True, cwd=str(cwd), check=False, env=constructed_environment(extra))


def _mission_body() -> dict[str, Any]:
    """One valid MissionContract body. Its ladder prefix and complete stop set are that tool's forms."""
    return {
        "schema": "agentic-sdlc/mission-contract@1",
        "mission_id": "mission-slice-6",
        "objective": "close slice 6 by binding one bounded auto-mode envelope to one plan revision",
        "scope": {
            "in_scope": ["skills/agentic-sdlc/tools/auto-envelope.py", "tests/test_auto_envelope.py"],
            "non_goals": ["the transition admission check", "the autonomous-transition receipt"],
        },
        "constraints": ["read-only and offline", "no clock: every instant is a caller-supplied input"],
        "authority": {"admitted_classes": list(WRITE_LADDER), "ceiling": "owned-worktree-write"},
        "completion_contract": {
            "success_criteria": ["the digest re-derives from every sealed document"],
            "terminal_criteria": ["one named refusal for every inadmissible field"],
        },
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
    """One valid workstream-submissions@1 body, in the canonical orders the compiler requires."""
    return {
        "schema": "agentic-sdlc/workstream-submissions@1",
        "submission_id": "submissions-slice-6-t8",
        "mission_id": "mission-slice-6",
        "stated_at": "2026-08-19T03:45:00Z",
        "declared_concurrency": 2,
        "workstreams": [
            {
                "id": "ws-envelope",
                "objective": "build the AutoEnvelope schema and its closed-shape refusals",
                "authority_class": "owned-worktree-write",
                "capability_demands": ["git-worktree-write", "python-execution"],
                "dependencies": [],
                "file_custody": ["skills/agentic-sdlc/tools/auto-envelope.py"],
                "worktree_custody": ".worktrees/auto-envelope",
            }
        ],
    }


def setUpModule() -> None:
    """Build the sibling fixtures ONCE, by running the real tools.

    A failure of a tool that CAN run is raised rather than skipped: a sibling that cannot seal its own
    valid input is a real regression, and swallowing it would silently delete this module's binding
    coverage. A missing `git` is different -- the host cannot answer the question -- so the dependent
    class skips by name.
    """
    global _SCRATCH
    _SCRATCH = tempfile.TemporaryDirectory(prefix="auto-envelope-fixtures-")
    scratch = Path(_SCRATCH.name).resolve()
    FIXTURES["scratch"] = scratch

    mission_body = scratch / "mission-body.json"
    mission_body.write_bytes(canonical(_mission_body()))
    done = _run([sys.executable, "-B", str(MISSION_TOOL), "define", "--contract", str(mission_body)], cwd=scratch)
    if done.returncode != EXIT_OK:
        raise AssertionError(f"mission-contract.py define failed: {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != DEFINED:
        raise AssertionError(f"mission-contract.py refused a valid body: {result['reasons']}")
    mission = scratch / "mission.json"
    mission.write_bytes(canonical(result["contract"]))

    if shutil.which("git") is None:
        return
    repository = scratch / "repo"
    repository.mkdir()
    git_environment = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    (repository / "tracked.txt").write_text("one\n", encoding="utf-8")
    for args in (
        ["init", "--quiet", "-b", "trunk", "."],
        ["add", "tracked.txt"],
        ["-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "--quiet", "-m", "one"],
    ):
        step = _run(["git", *args], cwd=repository, extra=git_environment)
        if step.returncode != 0:
            raise AssertionError(f"git {args} failed: {step.stderr!r}")

    done = _run(
        [
            sys.executable, "-B", str(SNAPSHOT_TOOL), "capture",
            "--repository", str(repository), "--at", "2026-08-19T03:30:00Z",
        ],
        cwd=scratch,
    )
    if done.returncode != EXIT_OK:
        raise AssertionError(f"planning-snapshot.py capture failed: {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != "captured":
        raise AssertionError(f"planning-snapshot.py refused a real repository: {result['reasons']}")
    snapshot = scratch / "snapshot.json"
    snapshot.write_bytes(canonical(result["snapshot"]))
    FIXTURES["snapshot_digest"] = result["digest"]

    submissions = scratch / "submissions.json"
    submissions.write_bytes(canonical(seal(_submissions_body())))
    done = _run(
        [
            sys.executable, "-B", str(COMPILER_TOOL), "compile",
            "--mission", str(mission), "--snapshot", str(snapshot), "--submissions", str(submissions),
            "--at", "2026-08-19T04:00:00Z",
        ],
        cwd=scratch,
    )
    if done.returncode != EXIT_OK:
        raise AssertionError(f"wave-plan-compiler.py compile failed: {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != "compiled":
        raise AssertionError(f"wave-plan-compiler.py refused a valid input set: {result['reasons']}")
    FIXTURES["plan_digest"] = result["plan_digest"]
    FIXTURES["plan_revision"] = result["plan"]["revision"]


def tearDownModule() -> None:
    if _SCRATCH is not None:
        _SCRATCH.cleanup()


# ---- the control body this module mutates ---------------------------------------------------------


def envelope_body(**overrides: Any) -> dict[str, Any]:
    """One complete, valid auto-envelope@1 body: the control every negative case starts from.

    Every set-shaped field is in the canonical form the tool requires -- ascending, no repeats, and the
    authority ladder in LADDER order rather than sorted order -- because a control that was not in
    those forms would be refused for the wrong reason.
    """
    body: dict[str, Any] = {
        "schema": ENVELOPE_SCHEMA,
        "envelope_id": "auto-slice-6-t8",
        "stated_at": STATED_AT,
        "bound_plan": {
            "plan_digest": fake_digest("wave-plan revision 2"),
            "plan_revision": 2,
            "snapshot_digest": fake_digest("planning snapshot"),
        },
        "allowed_authority_classes": list(WRITE_LADDER),
        "allowed_effect_classes": [
            "advisory-artifact-write",
            "evidence-record-append",
            "owned-worktree-file-write",
            "repository-read",
            "subagent-dispatch",
        ],
        "route_constraints": {
            "allow_fallback_selection": True,
            "allow_route_family_change": False,
            "require_resolved_assignment": True,
        },
        "egress_allowlist": {"data_classes": [], "destinations": [], "posture": "none"},
        "tool_allowlist": ["file-reader", "file-writer", "gate-runner", "repository-search", "version-control-read"],
        "graph_change_allowlist": ["added-edge", "added-node", "changed-node", "retry"],
        "concurrency_limits": {"max_concurrent_nodes": 2, "max_recursion_generations": 0},
        "retry_policy": {"max_attempts_per_node": 2, "max_total_retries": 4, "require_proven_no_effect": True},
        "validity_window": {"not_after": NOT_AFTER, "not_before": NOT_BEFORE},
        "checkpoints": [
            {"kind": "authority-inheritance", "requires_human_disposition": False},
            {"kind": "budget-remaining", "requires_human_disposition": False},
            {"kind": "drift-recheck", "requires_human_disposition": True},
            {"kind": "evidence-recheck", "requires_human_disposition": False},
        ],
        "stop_rules": list(STOP_RULE_KINDS),
    }
    body.update(overrides)
    return body


def nested(field: str, **overrides: Any) -> dict[str, Any]:
    """A control whose ONE nested object carries the overrides; every other field stays canonical."""
    inner = dict(envelope_body()[field])
    inner.update(overrides)
    return envelope_body(**{field: inner})


def without(field: str, key: str) -> dict[str, Any]:
    """A control whose one nested object is missing exactly one key."""
    inner = dict(envelope_body()[field])
    del inner[key]
    return envelope_body(**{field: inner})


class EnvelopeCase(unittest.TestCase):
    """The spawn helpers and the two assertions every class in this module is built out of."""

    maxDiff = None

    def scratch(self) -> Path:
        directory = tempfile.TemporaryDirectory(prefix="auto-envelope-case-")
        self.addCleanup(directory.cleanup)
        return Path(directory.name).resolve()

    def write(self, document: Any, *, name: str = "envelope.json") -> Path:
        target = self.scratch() / name
        target.write_bytes(canonical(document))
        return target

    def run_tool(self, argv: list[str], *, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
        return _run([sys.executable, "-B", str(TOOL), *argv], cwd=self.scratch(), extra=extra)

    def define(self, body: Any) -> dict[str, Any]:
        done = self.run_tool(["define", "--body", str(self.write(body, name="body.json"))])
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        result = json.loads(done.stdout.decode("utf-8"))
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        return result

    def verify(self, document: Any, *, expect: str | None = None) -> dict[str, Any]:
        argv = ["verify", "--envelope", str(self.write(document))]
        if expect is not None:
            argv += ["--expect-digest", expect]
        done = self.run_tool(argv)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        return json.loads(done.stdout.decode("utf-8"))

    def assert_defined(self, body: Any) -> dict[str, Any]:
        """The positive control. NO reasons are tolerated: a tolerated subset lets a guard rot."""
        result = self.define(body)
        self.assertEqual(result["reasons"], [], result["reasons"])
        self.assertEqual(result["verdict"], DEFINED)
        self.assertIsNotNone(result["envelope"])
        return result

    def assert_refused(self, body: Any, *, group: str, fragments: tuple[str, ...]) -> dict[str, Any]:
        """One refusal, in the group that owns the property, naming every fragment asked for."""
        result = self.define(body)
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIsNone(result["envelope"])
        self.assertIsNone(result["digest"])
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertFalse(groups[group]["met"], f"{group} reported met: {result['reasons']}")
        joined = " ".join(groups[group]["reasons"])
        for fragment in fragments:
            self.assertIn(fragment, joined)
        return result


class TestControlAndSealing(EnvelopeCase):
    """The positive control, what sealing adds, and what a refusal refuses to publish."""

    def test_the_control_body_is_defined_with_no_reasons(self) -> None:
        result = self.assert_defined(envelope_body())
        self.assertEqual(result["exit_code"], EXIT_OK)
        self.assertTrue(all(entry["met"] for entry in result["checks"]), result["checks"])

    def test_sealing_adds_exactly_one_key_and_changes_nothing_else(self) -> None:
        body = envelope_body()
        sealed = self.assert_defined(body)["envelope"]
        self.assertEqual(set(sealed) - set(body), {"digest"})
        self.assertEqual({key: sealed[key] for key in body}, body)

    def test_the_digest_is_the_familys_derivation_over_the_body(self) -> None:
        body = envelope_body()
        result = self.assert_defined(body)
        self.assertEqual(result["digest"], expected_digest(body))
        self.assertEqual(result["envelope"]["digest"], expected_digest(body))

    def test_an_admitted_envelope_republishes_the_facts_a_consumer_looks_up_first(self) -> None:
        body = envelope_body()
        result = self.assert_defined(body)
        self.assertEqual(result["envelope_id"], body["envelope_id"])
        self.assertEqual(result["bound_plan"], body["bound_plan"])
        self.assertEqual(result["allowed_authority_classes"], body["allowed_authority_classes"])
        self.assertEqual(result["validity_window"], body["validity_window"])

    def test_a_refusal_republishes_none_of_the_envelopes_fields(self) -> None:
        result = self.assert_refused(
            envelope_body(envelope_id="not an identifier"),
            group="identity-and-instant",
            fragments=("envelope_id",),
        )
        for key in ("envelope", "digest", "envelope_id", "bound_plan", "allowed_authority_classes", "validity_window"):
            self.assertIsNone(result[key], key)

    def test_the_consequence_says_a_defined_envelope_authorizes_nothing(self) -> None:
        result = self.assert_defined(envelope_body())
        self.assertIn("authorizes no dispatch", result["consequence"])
        self.assertIn("does not enable auto mode", result["consequence"])

    def test_the_residuals_name_the_command_boundary_and_the_uncopied_budgets(self) -> None:
        """`define` and `verify` still admit no transition; that became a command here, not a promise."""
        residuals = " ".join(self.assert_defined(envelope_body())["residuals"])
        self.assertIn("define and verify admit no proposed autonomous transition", residuals)
        self.assertIn("budgets live in the WavePlan", residuals)
        self.assertIn("bound BY DIGEST only", residuals)


class TestClosedShape(EnvelopeCase):
    """Default-off as a schema property: every absent field refuses, and no field defaults."""

    def test_the_control_is_defined_before_any_field_is_removed(self) -> None:
        self.assert_defined(envelope_body())

    def test_removing_any_single_field_refuses_and_names_it(self) -> None:
        body = envelope_body()
        for field in sorted(body):
            with self.subTest(field=field):
                mutated = {key: value for key, value in body.items() if key != field}
                self.assert_refused(
                    mutated,
                    group="closed-key-set",
                    fragments=(f"carries no {field}", "an absent field refuses rather than defaulting"),
                )

    def test_an_unknown_field_is_refused_rather_than_ignored(self) -> None:
        self.assert_refused(
            envelope_body(allow_everything=True),
            group="closed-key-set",
            fragments=("unknown field 'allow_everything'", "closed schema"),
        )

    def test_a_body_that_already_carries_a_digest_is_refused_by_name(self) -> None:
        self.assert_refused(
            seal(envelope_body()),
            group="closed-key-set",
            fragments=("already carries a digest", "second origin"),
        )

    def test_a_wrong_schema_string_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(schema="agentic-sdlc/auto-envelope@2"),
            group="closed-key-set",
            fragments=("declares schema 'agentic-sdlc/auto-envelope@2'", ENVELOPE_SCHEMA),
        )

    def test_removing_any_nested_field_refuses_and_names_the_closed_key_set(self) -> None:
        cases = {
            "bound_plan": ("bound-plan", ("plan_digest", "plan_revision", "snapshot_digest")),
            "route_constraints": (
                "route-constraints",
                ("allow_fallback_selection", "allow_route_family_change", "require_resolved_assignment"),
            ),
            "egress_allowlist": ("egress-allowlist", ("data_classes", "destinations", "posture")),
            "concurrency_limits": ("concurrency-and-recursion", ("max_concurrent_nodes", "max_recursion_generations")),
            "retry_policy": (
                "retry-policy",
                ("max_attempts_per_node", "max_total_retries", "require_proven_no_effect"),
            ),
            "validity_window": ("validity-window", ("not_after", "not_before")),
        }
        for field, (group, keys) in sorted(cases.items()):
            for key in keys:
                with self.subTest(field=field, key=key):
                    self.assert_refused(
                        without(field, key),
                        group=group,
                        fragments=(f"missing ['{key}']", "an absence refuses rather than defaults"),
                    )

    def test_an_unknown_nested_field_is_refused(self) -> None:
        self.assert_refused(
            nested("route_constraints", provider="anthropic"),
            group="route-constraints",
            fragments=("unexpected ['provider']",),
        )

    def test_the_sealed_document_names_no_provider_and_no_model_anywhere(self) -> None:
        """Route identity is the RuntimeAssignment's; this schema states a posture, never a route."""
        sealed = self.assert_defined(envelope_body())["envelope"]
        text = canonical(sealed).decode("ascii").lower()
        for token in ("provider", "model", "anthropic", "claude", "gpt", "sonnet", "opus"):
            self.assertNotIn(token, text, token)

    def test_the_two_fields_whose_empty_value_is_the_narrowest_reading_admit_it(self) -> None:
        self.assert_defined(envelope_body(tool_allowlist=[], graph_change_allowlist=[], retry_policy={
            "max_attempts_per_node": 1, "max_total_retries": 0, "require_proven_no_effect": True,
        }))

    def test_the_two_fields_whose_empty_value_would_state_nothing_refuse_it(self) -> None:
        self.assert_refused(
            envelope_body(checkpoints=[]),
            group="checkpoints",
            fragments=("not a non-empty array", "never rechecks anything"),
        )
        self.assert_refused(
            envelope_body(stop_rules=[]),
            group="stop-rules",
            fragments=("is empty", "states nothing"),
        )

    def test_allowed_effect_classes_may_not_be_empty_either(self) -> None:
        self.assert_refused(
            envelope_body(allowed_effect_classes=[]),
            group="effect-classes",
            fragments=("is empty", "states nothing"),
        )


NO_RETRY_POLICY = {"max_attempts_per_node": 1, "max_total_retries": 0, "require_proven_no_effect": True}


def read_only_body(**overrides: Any) -> dict[str, Any]:
    """A control whose ladder stops at `read-only-advisory`, with no effect or tool that needs a write.

    This is the OTHER half of every cross-field control: the same effect and tool sets that the write
    ladder admits are refused here, so a check that stopped discriminating fails on one side.
    """
    body = envelope_body(
        allowed_authority_classes=list(READ_ONLY_LADDER),
        allowed_effect_classes=[
            "advisory-artifact-write",
            "evidence-record-append",
            "repository-read",
            "subagent-dispatch",
        ],
        tool_allowlist=["file-reader", "gate-runner", "repository-search", "version-control-read"],
    )
    body.update(overrides)
    return body


class TestAuthorityLadder(EnvelopeCase):
    """A PREFIX of the ordered ladder, stopping at or below the bounded auto-mode ceiling."""

    def test_both_admissible_prefixes_are_defined(self) -> None:
        self.assert_defined(envelope_body())
        self.assert_defined(read_only_body())

    def test_a_gap_in_the_prefix_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(allowed_authority_classes=["owned-worktree-write"]),
            group="authority-ladder",
            fragments=("not a prefix of the ladder", "a gap in it would admit a wider authority"),
        )

    def test_a_non_prefix_subset_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(allowed_authority_classes=["read-only-advisory", "authorized-fan-in"]),
            group="authority-ladder",
            fragments=("not a prefix of the ladder",),
        )

    def test_ladder_order_is_not_sorted_order(self) -> None:
        """The one place this schema's canonical form is NOT ascending, asserted so a sort cannot creep in."""
        self.assertNotEqual(list(WRITE_LADDER), sorted(WRITE_LADDER))
        self.assert_refused(
            envelope_body(allowed_authority_classes=sorted(WRITE_LADDER)),
            group="authority-ladder",
            fragments=("not a prefix of the ladder",),
        )

    def test_each_rung_above_the_auto_ceiling_is_refused_by_doctrine(self) -> None:
        for length in (3, 4):
            with self.subTest(rungs=length):
                self.assert_refused(
                    envelope_body(allowed_authority_classes=list(AUTHORITY_CLASSES[:length])),
                    group="authority-ladder",
                    fragments=(
                        "above the bounded auto-mode ceiling 'owned-worktree-write'",
                        "non-delegable even when the envelope predicts them",
                    ),
                )

    def test_an_unknown_rung_is_refused_against_the_closed_vocabulary(self) -> None:
        self.assert_refused(
            envelope_body(allowed_authority_classes=["read-only-advisory", "root"]),
            group="authority-ladder",
            fragments=("names ['root']", "an open vocabulary"),
        )

    def test_an_empty_or_non_list_ladder_is_refused(self) -> None:
        for value in ([], "read-only-advisory", None, ["read-only-advisory", "read-only-advisory"]):
            with self.subTest(value=value):
                self.assert_refused(
                    envelope_body(allowed_authority_classes=value),
                    group="authority-ladder",
                    fragments=(),
                )


class TestEffectClasses(EnvelopeCase):
    """The closed effect vocabulary, its non-delegable members, and the ladder cross-check."""

    def test_the_control_effect_set_is_defined(self) -> None:
        self.assert_defined(envelope_body())

    def test_every_non_delegable_effect_is_refused_by_name(self) -> None:
        for effect in NON_DELEGABLE_EFFECTS:
            with self.subTest(effect=effect):
                effects = sorted([*envelope_body()["allowed_effect_classes"], effect])
                self.assert_refused(
                    envelope_body(allowed_effect_classes=effects),
                    group="effect-classes",
                    fragments=(f"names ['{effect}']", "always stop", "non-delegable"),
                )

    def test_an_unknown_effect_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(allowed_effect_classes=["advisory-artifact-write", "whatever-is-needed"]),
            group="effect-classes",
            fragments=("names ['whatever-is-needed']",),
        )

    def test_an_unsorted_or_repeated_effect_set_is_refused(self) -> None:
        for value in (
            ["repository-read", "advisory-artifact-write"],
            ["repository-read", "repository-read"],
        ):
            with self.subTest(value=value):
                self.assert_refused(
                    envelope_body(allowed_effect_classes=value),
                    group="effect-classes",
                    fragments=("not a strictly ascending set", "one meaning two digests"),
                )

    def test_a_write_effect_under_a_read_only_ladder_is_refused(self) -> None:
        # The positive control is the SAME effect under the write ladder, which the class's first test
        # asserts is defined: the discrimination is between the two, not between refused and anything.
        self.assert_refused(
            read_only_body(
                allowed_effect_classes=sorted([*read_only_body()["allowed_effect_classes"], "owned-worktree-file-write"])
            ),
            group="effect-classes",
            fragments=("owned-worktree-file-write", "the write authority the ladder withheld"),
        )


class TestRouteConstraints(EnvelopeCase):
    """A closed boolean posture: no provider, model, or route string exists in this schema."""

    def test_the_control_posture_is_defined(self) -> None:
        self.assert_defined(envelope_body())

    def test_a_narrower_posture_that_forbids_fallback_selection_is_also_defined(self) -> None:
        self.assert_defined(nested("route_constraints", allow_fallback_selection=False))

    def test_waiving_the_resolved_assignment_requirement_is_refused(self) -> None:
        self.assert_refused(
            nested("route_constraints", require_resolved_assignment=False),
            group="route-constraints",
            fragments=("require_resolved_assignment is false", "stops BEFORE spawn"),
        )

    def test_allowing_a_route_family_change_is_refused(self) -> None:
        self.assert_refused(
            nested("route_constraints", allow_route_family_change=True),
            group="route-constraints",
            fragments=("allow_route_family_change is true", "cannot add or widen"),
        )

    def test_a_non_boolean_posture_is_not_a_posture(self) -> None:
        for value in ("true", 1, None, [True]):
            with self.subTest(value=value):
                self.assert_refused(
                    nested("route_constraints", require_resolved_assignment=value),
                    group="route-constraints",
                    fragments=("is not a JSON boolean", "is not stated"),
                )


class TestEgressAllowlist(EnvelopeCase):
    """`none` is the whole vocabulary, and both lists must be empty to say so."""

    def test_the_none_posture_with_two_empty_lists_is_defined(self) -> None:
        self.assert_defined(envelope_body())

    def test_any_other_posture_is_outside_the_vocabulary(self) -> None:
        self.assert_refused(
            nested("egress_allowlist", posture="allowlist"),
            group="egress-allowlist",
            fragments=("'allowlist' is not one of ['none']",),
        )

    def test_a_named_destination_or_data_class_contradicts_the_posture(self) -> None:
        for key, value in (("destinations", ["api.example.invalid"]), ("data_classes", ["repository-source"])):
            with self.subTest(key=key):
                self.assert_refused(
                    nested("egress_allowlist", **{key: value}),
                    group="egress-allowlist",
                    fragments=("expresses exactly one egress posture", "a permission the posture denies"),
                )


class TestToolAllowlist(EnvelopeCase):
    """Tool CLASSES, bounded by the ladder and by the egress posture."""

    def test_the_control_and_the_empty_allowlist_are_both_defined(self) -> None:
        self.assert_defined(envelope_body())
        self.assert_defined(envelope_body(tool_allowlist=[]))

    def test_an_unknown_tool_class_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(tool_allowlist=["Bash"]),
            group="tool-allowlist",
            fragments=("names ['Bash']", "an open vocabulary"),
        )

    def test_a_network_tool_beside_the_none_posture_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(tool_allowlist=sorted([*envelope_body()["tool_allowlist"], "network-fetch"])),
            group="tool-allowlist",
            fragments=("network-fetch", "the egress this envelope forbids"),
        )

    def test_each_write_tool_under_a_read_only_ladder_is_refused(self) -> None:
        for tool in ("file-writer", "version-control-write"):
            with self.subTest(tool=tool):
                self.assert_refused(
                    read_only_body(tool_allowlist=sorted([*read_only_body()["tool_allowlist"], tool])),
                    group="tool-allowlist",
                    fragments=(tool, "the write authority the ladder withheld"),
                )


class TestGraphChangeAllowlist(EnvelopeCase):
    """Which of the compiler's sixteen PlanDiff change kinds an autonomous transition may cause."""

    def _body_for(self, kinds: list[str]) -> dict[str, Any]:
        """The retry policy tracks the allowlist, so this class tests the allowlist and not the biconditional."""
        policy = envelope_body()["retry_policy"] if "retry" in kinds else NO_RETRY_POLICY
        return envelope_body(graph_change_allowlist=kinds, retry_policy=policy)

    def test_the_control_and_the_empty_allowlist_are_both_defined(self) -> None:
        self.assert_defined(envelope_body())
        self.assert_defined(self._body_for([]))

    def test_all_sixteen_change_kinds_partition_into_four_admitted_and_twelve_refused(self) -> None:
        admitted, refused = [], []
        for kind in CHANGE_KINDS:
            with self.subTest(kind=kind):
                result = self.define(self._body_for([kind]))
                self.assertIn(result["verdict"], (DEFINED, REFUSED))
                (admitted if result["verdict"] == DEFINED else refused).append(kind)
        self.assertEqual(admitted, list(AUTONOMOUS_CHANGE_KINDS))
        self.assertEqual(len(refused), 12)

    def test_a_non_delegable_kind_is_refused_with_the_widening_sentence(self) -> None:
        self.assert_refused(
            self._body_for(["added-node", "authority"]),
            group="graph-change-allowlist",
            fragments=("names ['authority']", "cannot add or widen", "must preserve its declared outputs"),
        )

    def test_an_unknown_kind_is_refused(self) -> None:
        self.assert_refused(
            self._body_for(["improvement"]),
            group="graph-change-allowlist",
            fragments=("names ['improvement']",),
        )

    def test_an_unsorted_allowlist_is_refused(self) -> None:
        self.assert_refused(
            self._body_for(["added-node", "added-edge"]),
            group="graph-change-allowlist",
            fragments=("not a strictly ascending set",),
        )


NO_RETRY_CHANGES = ["added-edge", "added-node", "changed-node"]


class TestConcurrencyAndRecursion(EnvelopeCase):
    """Bounded concurrency, and recursive execution pinned OFF because it is a separate capability."""

    def test_the_control_and_both_ends_of_the_admitted_concurrency_range_are_defined(self) -> None:
        self.assert_defined(envelope_body())
        for value in (1, MAX_CONCURRENT_NODES_CEILING):
            with self.subTest(value=value):
                self.assert_defined(nested("concurrency_limits", max_concurrent_nodes=value))

    def test_concurrency_outside_the_range_is_refused(self) -> None:
        for value in (0, -1, MAX_CONCURRENT_NODES_CEILING + 1):
            with self.subTest(value=value):
                self.assert_refused(
                    nested("concurrency_limits", max_concurrent_nodes=value),
                    group="concurrency-and-recursion",
                    fragments=(f"outside the admitted range 1..{MAX_CONCURRENT_NODES_CEILING}",),
                )

    def test_a_boolean_is_not_a_count(self) -> None:
        self.assert_refused(
            nested("concurrency_limits", max_concurrent_nodes=True),
            group="concurrency-and-recursion",
            fragments=("is not an integer",),
        )

    def test_recursion_zero_is_the_only_admitted_value(self) -> None:
        self.assert_defined(nested("concurrency_limits", max_recursion_generations=0))
        self.assert_refused(
            nested("concurrency_limits", max_recursion_generations=1),
            group="concurrency-and-recursion",
            fragments=("recursive execution is a SEPARATE capability", "does not enable, approve, weaken, or configure"),
        )

    def test_a_negative_recursion_count_is_refused_as_a_range_error(self) -> None:
        """A raised count earns the doctrine sentence; a negative one has no doctrine, so it earns the range."""
        result = self.assert_refused(
            nested("concurrency_limits", max_recursion_generations=-1),
            group="concurrency-and-recursion",
            fragments=("outside the admitted range 0..",),
        )
        joined = " ".join(result["reasons"])
        self.assertNotIn("SEPARATE capability", joined)

    def test_a_raised_recursion_count_earns_the_doctrine_reason_not_a_range_error(self) -> None:
        result = self.assert_refused(
            nested("concurrency_limits", max_recursion_generations=2),
            group="concurrency-and-recursion",
            fragments=("recursive execution is a SEPARATE capability",),
        )
        self.assertNotIn("outside the admitted range", " ".join(result["reasons"]))


class TestRetryPolicy(EnvelopeCase):
    """Bounded counts, proof-of-no-effect pinned on, and the biconditional with the change allowlist."""

    def test_both_coherent_policies_are_defined(self) -> None:
        self.assert_defined(envelope_body())
        self.assert_defined(envelope_body(retry_policy=NO_RETRY_POLICY, graph_change_allowlist=NO_RETRY_CHANGES))

    def test_counts_outside_their_bounds_are_refused(self) -> None:
        cases = (
            ("max_attempts_per_node", MAX_ATTEMPTS_PER_NODE_CEILING + 1, f"1..{MAX_ATTEMPTS_PER_NODE_CEILING}"),
            ("max_attempts_per_node", 0, f"1..{MAX_ATTEMPTS_PER_NODE_CEILING}"),
            ("max_total_retries", MAX_TOTAL_RETRIES_CEILING + 1, f"0..{MAX_TOTAL_RETRIES_CEILING}"),
            ("max_total_retries", -1, f"0..{MAX_TOTAL_RETRIES_CEILING}"),
        )
        for key, value, expected in cases:
            with self.subTest(key=key, value=value):
                self.assert_refused(
                    nested("retry_policy", **{key: value}),
                    group="retry-policy",
                    fragments=(f"outside the admitted range {expected}",),
                )

    def test_waiving_proof_of_no_effect_is_refused(self) -> None:
        self.assert_refused(
            nested("retry_policy", require_proven_no_effect=False),
            group="retry-policy",
            fragments=("require_proven_no_effect is false", "proven no-effect", "always stops"),
        )

    def test_a_per_node_allowance_with_no_total_budget_is_refused(self) -> None:
        self.assert_refused(
            nested("retry_policy", max_total_retries=0),
            group="retry-policy",
            fragments=("could never be spent", "two different envelopes"),
        )

    def test_a_total_budget_the_per_node_limit_forbids_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(
                retry_policy={"max_attempts_per_node": 1, "max_total_retries": 2, "require_proven_no_effect": True},
                graph_change_allowlist=NO_RETRY_CHANGES,
            ),
            group="retry-policy",
            fragments=("cannot be drawn from a total", "unspendable budget"),
        )

    def test_the_biconditional_with_the_change_allowlist_is_named_in_both_directions(self) -> None:
        self.assert_refused(
            envelope_body(graph_change_allowlist=NO_RETRY_CHANGES),
            group="retry-policy",
            fragments=("graph_change_allowlist does not name 'retry'", "could never be recorded"),
        )
        self.assert_refused(
            envelope_body(retry_policy=NO_RETRY_POLICY),
            group="retry-policy",
            fragments=("names 'retry' while retry_policy admits one attempt", "a permission the policy denies"),
        )


class TestValidityWindow(EnvelopeCase):
    """Two real instants, strictly ordered, not retroactive, and bounded AT the boundary."""

    def window(self, not_before: str, not_after: str, **overrides: Any) -> dict[str, Any]:
        body = envelope_body(validity_window={"not_after": not_after, "not_before": not_before})
        body.update(overrides)
        return body

    def test_the_control_and_a_window_of_exactly_the_bound_are_defined(self) -> None:
        self.assert_defined(envelope_body())
        self.assertEqual(MAX_VALIDITY_SECONDS, 86400)  # the boundary below is this bound, spelled out
        self.assert_defined(self.window("2026-08-20T01:00:00Z", "2026-08-21T01:00:00Z"))

    def test_one_second_past_the_bound_is_refused(self) -> None:
        self.assert_refused(
            self.window("2026-08-20T01:00:00Z", "2026-08-21T01:00:01Z"),
            group="validity-window",
            fragments=(f"beyond the {MAX_VALIDITY_SECONDS}-second bound", "standing grant"),
        )

    def test_a_zero_width_or_inverted_window_is_refused(self) -> None:
        for not_before, not_after in (
            ("2026-08-20T01:00:00Z", "2026-08-20T01:00:00Z"),
            ("2026-08-20T02:00:00Z", "2026-08-20T01:00:00Z"),
        ):
            with self.subTest(not_before=not_before, not_after=not_after):
                self.assert_refused(
                    self.window(not_before, not_after),
                    group="validity-window",
                    fragments=("is not strictly before", "authorizes nothing while looking like it authorizes"),
                )

    def test_a_window_opening_before_stated_at_is_refused_as_retroactive(self) -> None:
        self.assert_refused(
            self.window("2026-08-19T23:00:00Z", "2026-08-20T05:00:00Z"),
            group="validity-window",
            fragments=("precedes the envelope's stated_at", "retroactively valid"),
        )

    def test_a_window_opening_exactly_at_stated_at_is_defined(self) -> None:
        self.assert_defined(self.window(STATED_AT, "2026-08-20T05:00:00Z"))

    def test_an_instant_with_the_right_shape_and_no_calendar_moment_is_refused(self) -> None:
        for value in ("2026-13-20T01:00:00Z", "2026-02-30T01:00:00Z", "2026-08-20T25:00:00Z"):
            with self.subTest(value=value):
                self.assert_refused(
                    self.window(value, NOT_AFTER),
                    group="validity-window",
                    fragments=("names no calendar moment",),
                )


class TestInstantCharacterClass(EnvelopeCase):
    """The guard is `[0-9]`, not `\\d`: a digit `\\d` accepts and this family does not must be refused."""

    ARABIC_INDIC = "\u0662\u0660\u0662\u0666-\u0660\u0668-\u0662\u0660T\u0660\u0661:\u0660\u0660:\u0660\u0660Z"

    def test_the_positive_control_is_that_re_would_have_accepted_it(self) -> None:
        """Without this, the refusal below could be about anything -- a length, a separator, a letter."""
        import re

        self.assertIsNotNone(re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z", self.ARABIC_INDIC))
        self.assertIsNone(re.match(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z", self.ARABIC_INDIC))

    def test_stated_at_refuses_a_non_ascii_digit_instant(self) -> None:
        self.assert_refused(
            envelope_body(stated_at=self.ARABIC_INDIC),
            group="identity-and-instant",
            fragments=("is not a YYYY-MM-DDTHH:MM:SSZ instant",),
        )

    def test_both_ends_of_the_window_refuse_a_non_ascii_digit_instant(self) -> None:
        for key in ("not_before", "not_after"):
            with self.subTest(key=key):
                self.assert_refused(
                    nested("validity_window", **{key: self.ARABIC_INDIC}),
                    group="validity-window",
                    fragments=("is not a YYYY-MM-DDTHH:MM:SSZ instant",),
                )

    def test_the_envelope_id_refuses_a_non_identifier(self) -> None:
        for value in ("auto slice 6", "../escape", "-leading-dash", ""):
            with self.subTest(value=value):
                self.assert_refused(
                    envelope_body(envelope_id=value),
                    group="identity-and-instant",
                    fragments=("envelope_id",),
                )


class TestCheckpoints(EnvelopeCase):
    """One entry per kind, ascending, covering the four every transition must recheck."""

    def test_the_four_mandatory_kinds_and_the_optional_fifth_are_defined(self) -> None:
        self.assert_defined(envelope_body())
        self.assert_defined(
            envelope_body(
                checkpoints=[
                    *envelope_body()["checkpoints"],
                    {"kind": "validity-recheck", "requires_human_disposition": True},
                ]
            )
        )

    def test_omitting_any_mandatory_kind_is_refused_by_name(self) -> None:
        for kind in MANDATORY_CHECKPOINT_KINDS:
            with self.subTest(kind=kind):
                kept = [entry for entry in envelope_body()["checkpoints"] if entry["kind"] != kind]
                self.assert_refused(
                    envelope_body(checkpoints=kept),
                    group="checkpoints",
                    fragments=(f"omits ['{kind}']", "every transition rechecks remaining budgets"),
                )

    def test_a_repeated_or_reordered_kind_is_refused(self) -> None:
        control = envelope_body()["checkpoints"]
        for value in ([*control, control[0]], list(reversed(control))):
            with self.subTest(kinds=[entry["kind"] for entry in value]):
                self.assert_refused(
                    envelope_body(checkpoints=value),
                    group="checkpoints",
                    fragments=("not a strictly ascending set",),
                )

    def test_an_unknown_kind_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(checkpoints=[{"kind": "vibe-check", "requires_human_disposition": False}]),
            group="checkpoints",
            fragments=("'vibe-check' is not one of",),
        )

    def test_a_non_boolean_disposition_is_refused(self) -> None:
        entries = [dict(entry) for entry in envelope_body()["checkpoints"]]
        entries[0]["requires_human_disposition"] = "yes"
        self.assert_refused(
            envelope_body(checkpoints=entries),
            group="checkpoints",
            fragments=("requires_human_disposition is not a JSON boolean",),
        )

    def test_an_entry_that_is_not_a_closed_object_is_refused(self) -> None:
        entries = [dict(entry) for entry in envelope_body()["checkpoints"]]
        entries[0]["notes"] = "extra"
        self.assert_refused(
            envelope_body(checkpoints=entries),
            group="checkpoints",
            fragments=("unexpected ['notes']",),
        )
        self.assert_refused(
            envelope_body(checkpoints=["authority-inheritance"]),
            group="checkpoints",
            fragments=("is not a JSON object",),
        )


class TestStopRules(EnvelopeCase):
    """All twelve always-stop conditions, enumerated in the bytes a human approves."""

    def test_the_complete_set_is_defined(self) -> None:
        self.assert_defined(envelope_body())

    def test_omitting_any_one_of_the_twelve_is_refused_by_name(self) -> None:
        for rule in STOP_RULE_KINDS:
            with self.subTest(rule=rule):
                kept = [name for name in STOP_RULE_KINDS if name != rule]
                self.assert_refused(
                    envelope_body(stop_rules=kept),
                    group="stop-rules",
                    fragments=(f"omits ['{rule}']", "always stops", "the twelve are not selectable"),
                )

    def test_an_unknown_rule_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(stop_rules=sorted([*STOP_RULE_KINDS, "vibes-are-off"])),
            group="stop-rules",
            fragments=("names ['vibes-are-off']",),
        )

    def test_an_unsorted_complete_set_is_refused(self) -> None:
        self.assert_refused(
            envelope_body(stop_rules=list(reversed(STOP_RULE_KINDS))),
            group="stop-rules",
            fragments=("not a strictly ascending set",),
        )


class TestBoundPlan(EnvelopeCase):
    """The two digests and the one revision this envelope is FOR."""

    def test_the_control_binding_is_defined(self) -> None:
        self.assert_defined(envelope_body())

    def test_a_value_that_is_not_a_sha256_is_refused(self) -> None:
        for key in ("plan_digest", "snapshot_digest"):
            for value in ("deadbeef", "A" * 64, fake_digest("x")[:63], None, 4):
                with self.subTest(key=key, value=value):
                    self.assert_refused(
                        nested("bound_plan", **{key: value}),
                        group="bound-plan",
                        fragments=(f"bound_plan.{key}", "64 lowercase hexadecimal"),
                    )

    def test_a_revision_that_is_not_a_positive_integer_is_refused(self) -> None:
        for value in (0, -1, True, "2", 1.5, None):
            with self.subTest(value=value):
                self.assert_refused(
                    nested("bound_plan", plan_revision=value),
                    group="bound-plan",
                    fragments=("bound_plan.plan_revision",),
                )

    def test_one_digest_for_both_documents_is_refused(self) -> None:
        shared = fake_digest("both")
        self.assert_refused(
            nested("bound_plan", plan_digest=shared, snapshot_digest=shared),
            group="bound-plan",
            fragments=("cannot share a content digest", "one of the two bindings is wrong"),
        )

    def require_siblings(self) -> None:
        """Skipped at RUN time, not at import time: `setUpModule` has not run when a decorator is
        evaluated, so `skipUnless` over `FIXTURES` would skip these two tests on every host."""
        if "plan_digest" not in FIXTURES:
            self.skipTest(NO_GIT)

    def test_the_real_sibling_digests_are_bound_and_republished_verbatim(self) -> None:
        self.require_siblings()
        """The digests a REAL mission -> snapshot -> compile chain produced, not two invented strings."""
        bound = {
            "plan_digest": FIXTURES["plan_digest"],
            "plan_revision": FIXTURES["plan_revision"],
            "snapshot_digest": FIXTURES["snapshot_digest"],
        }
        result = self.assert_defined(envelope_body(bound_plan=bound))
        self.assertEqual(result["bound_plan"], bound)
        self.assertEqual(result["envelope"]["bound_plan"], bound)
        self.assertNotEqual(bound["plan_digest"], bound["snapshot_digest"])

    def test_the_bound_digests_are_the_ones_the_siblings_themselves_verify(self) -> None:
        """The plan digest this envelope binds is what `wave-plan-compiler.py verify` re-derives."""
        self.require_siblings()
        plan = FIXTURES["scratch"] / "plan-for-verify.json"
        done = _run(
            [
                sys.executable, "-B", str(COMPILER_TOOL), "compile",
                "--mission", str(FIXTURES["scratch"] / "mission.json"),
                "--snapshot", str(FIXTURES["scratch"] / "snapshot.json"),
                "--submissions", str(FIXTURES["scratch"] / "submissions.json"),
                "--at", "2026-08-19T04:00:00Z", "--out", str(plan),
            ],
            cwd=FIXTURES["scratch"],
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        done = _run(
            [
                sys.executable, "-B", str(COMPILER_TOOL), "verify",
                "--plan", str(plan), "--expect-digest", FIXTURES["plan_digest"],
            ],
            cwd=FIXTURES["scratch"],
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        self.assertEqual(json.loads(done.stdout.decode("utf-8"))["verdict"], VERIFIED)


class TestDigestRoundTrip(EnvelopeCase):
    """`define` seals, `verify` re-derives, and both agree with the family's published derivation."""

    def test_define_then_verify_agree_on_the_one_digest(self) -> None:
        defined = self.assert_defined(envelope_body())
        verified = self.verify(defined["envelope"])
        self.assertEqual(verified["reasons"], [])
        self.assertEqual(verified["verdict"], VERIFIED)
        self.assertEqual(verified["digest"], defined["digest"])
        self.assertEqual(verified["envelope"], defined["envelope"])

    def test_a_document_sealed_by_this_module_verifies(self) -> None:
        """Proves the tool agrees with the family's derivation rather than only with itself."""
        body = envelope_body()
        result = self.verify(seal(body))
        self.assertEqual(result["verdict"], VERIFIED)
        self.assertEqual(result["digest"], expected_digest(body))

    def test_expect_digest_admits_the_match_and_refuses_a_mismatch(self) -> None:
        sealed = seal(envelope_body())
        matched = self.verify(sealed, expect=expected_digest(envelope_body()))
        self.assertEqual(matched["verdict"], VERIFIED)
        mismatched = self.verify(sealed, expect=fake_digest("some other envelope"))
        self.assertEqual(mismatched["verdict"], REFUSED)
        self.assertIn("is not this envelope's content digest", " ".join(mismatched["reasons"]))

    def test_an_edited_sealed_document_refuses(self) -> None:
        sealed = seal(envelope_body())
        sealed["concurrency_limits"] = {"max_concurrent_nodes": 4, "max_recursion_generations": 0}
        result = self.verify(sealed)
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("does not re-derive", " ".join(result["reasons"]))

    def test_a_recorded_digest_of_the_wrong_shape_refuses(self) -> None:
        sealed = seal(envelope_body())
        sealed["digest"] = "not-a-digest"
        self.assertEqual(self.verify(sealed)["verdict"], REFUSED)

    def test_verify_refuses_a_body_that_was_never_sealed(self) -> None:
        result = self.verify(envelope_body())
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("carries no digest", " ".join(result["reasons"]))

    def test_a_malformed_expect_digest_is_unusable_input_before_any_file_is_read(self) -> None:
        done = self.run_tool(["verify", "--envelope", str(self.scratch() / "absent.json"), "--expect-digest", "nope"])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn(b"not 64 lowercase hexadecimal", done.stderr)
        self.assertEqual(done.stdout, b"")


class TestUnusableInput(EnvelopeCase):
    """Exit 2: the question could not be asked at all. Never a refusal, never a traceback."""

    def write_raw(self, text: str) -> Path:
        target = self.scratch() / "raw.json"
        target.write_text(text, encoding="utf-8")
        return target

    def define_raw(self, text: str) -> subprocess.CompletedProcess[bytes]:
        return self.run_tool(["define", "--body", str(self.write_raw(text))])

    def test_the_positive_control_is_that_the_same_path_shape_exits_zero(self) -> None:
        done = self.define_raw(json.dumps(envelope_body()))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        self.assertEqual(json.loads(done.stdout.decode("utf-8"))["verdict"], DEFINED)

    def test_a_non_finite_number_nested_in_a_list_is_refused_by_the_post_parse_walk(self) -> None:
        body = envelope_body()
        body["stop_rules"] = [*STOP_RULE_KINDS]
        text = json.dumps(body).replace('"ambiguous-ownership"', "1e400", 1)
        done = self.define_raw(text)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout)
        self.assertIn(b"non-finite number", done.stderr)
        self.assertIn(b"at position 0", done.stderr)

    def test_a_non_finite_number_nested_deep_in_an_object_is_refused(self) -> None:
        text = json.dumps(envelope_body()).replace('"max_total_retries": 4', '"max_total_retries": 1e400', 1)
        done = self.define_raw(text)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout)
        self.assertIn(b"non-finite number", done.stderr)
        self.assertIn(b"max_total_retries", done.stderr)

    def test_each_non_finite_constant_token_is_refused_by_name(self) -> None:
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                text = json.dumps(envelope_body()).replace('"max_total_retries": 4', f'"max_total_retries": {token}', 1)
                done = self.define_raw(text)
                self.assertEqual(done.returncode, EXIT_INPUT, done.stdout)
                self.assertIn(b"non-finite JSON constant", done.stderr)

    def test_a_repeated_json_key_is_two_meanings_and_is_refused(self) -> None:
        text = json.dumps(envelope_body())
        text = text[:-1] + ', "tool_allowlist": []}'
        done = self.define_raw(text)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout)
        self.assertIn(b"repeats the JSON key 'tool_allowlist'", done.stderr)

    def test_a_top_level_non_object_is_refused(self) -> None:
        for text in ("[]", '"envelope"', "42", "null"):
            with self.subTest(text=text):
                done = self.define_raw(text)
                self.assertEqual(done.returncode, EXIT_INPUT)
                self.assertIn(b"is not a JSON object", done.stderr)

    def test_unparseable_bytes_are_refused(self) -> None:
        done = self.define_raw("{not json")
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn(b"is not JSON", done.stderr)

    def test_a_directory_is_not_a_regular_file(self) -> None:
        done = self.run_tool(["define", "--body", str(self.scratch())])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn(b"is not a regular file", done.stderr)

    def test_an_absent_path_is_refused_without_a_traceback(self) -> None:
        done = self.run_tool(["define", "--body", str(self.scratch() / "absent.json")])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertIn(b"cannot read", done.stderr)
        self.assertNotIn(b"Traceback", done.stderr)

    def test_a_missing_verb_is_a_grammar_error(self) -> None:
        done = self.run_tool([])
        self.assertEqual(done.returncode, EXIT_INPUT)


class TestDeterminismAndAmbientInput(EnvelopeCase):
    """The emitted bytes depend on the supplied document and nothing else."""

    def test_two_hash_seeds_produce_identical_bytes(self) -> None:
        body = self.write(envelope_body(), name="body.json")
        runs = []
        for seed in ("0", "1"):
            done = self.run_tool(["define", "--body", str(body)], extra={"PYTHONHASHSEED": seed})
            self.assertEqual(done.returncode, EXIT_OK, done.stderr)
            runs.append(done.stdout)
        self.assertEqual(runs[0], runs[1])

    def test_the_positive_control_is_that_the_two_seeds_really_change_string_hashing(self) -> None:
        """Without this, the comparison above would also pass on an interpreter with hashing disabled."""
        hashes = []
        for seed in ("0", "1"):
            done = subprocess.run(
                [sys.executable, "-c", "print(hash('auto-envelope'))"],
                capture_output=True,
                check=False,
                env=constructed_environment({"PYTHONHASHSEED": seed}),
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            hashes.append(done.stdout)
        self.assertNotEqual(hashes[0], hashes[1])

    def test_running_from_two_directories_produces_identical_bytes(self) -> None:
        body = self.write(envelope_body(), name="body.json")
        first = _run([sys.executable, "-B", str(TOOL), "define", "--body", str(body)], cwd=body.parent)
        second = _run([sys.executable, "-B", str(TOOL), "define", "--body", str(body)], cwd=ROOT)
        self.assertEqual(first.returncode, EXIT_OK, first.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def _tool_tree(self) -> ast.Module:
        return ast.parse(TOOL.read_text(encoding="utf-8"))

    def test_the_tool_imports_no_module_that_could_read_ambient_state(self) -> None:
        """`os` is not imported at all, which is a stronger statement than 'os.environ does not appear'."""
        imported: set[str] = set()
        for node in ast.walk(self._tool_tree()):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for forbidden in ("os", "subprocess", "socket", "urllib", "time", "random", "shutil"):
            self.assertNotIn(forbidden, imported, forbidden)
        self.assertIn("datetime", imported)  # the positive control: this collection really is populated

    def test_the_tool_reaches_for_no_clock(self) -> None:
        attributes = {
            node.attr for node in ast.walk(self._tool_tree()) if isinstance(node, ast.Attribute)
        }
        for forbidden in ("now", "utcnow", "today", "fromtimestamp", "time", "monotonic", "environ", "getenv"):
            self.assertNotIn(forbidden, attributes, forbidden)
        self.assertIn("strptime", attributes)  # the one datetime call this module does make

    def test_this_module_reaches_for_the_environment_only_inside_the_constructor(self) -> None:
        """A substring search cannot do this job; the docstring names `os.environ` while promising this."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name == "constructed_environment":
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr in ("environ", "getenv"):
                    offenders.append(node.name)
        self.assertEqual(offenders, [])


# ---- the transition-admission half ----------------------------------------------------------------

TRANSITION_SCHEMA = "agentic-sdlc/autonomous-transition@1"
RECEIPT_SCHEMA = "agentic-sdlc/autonomous-transition-receipt@1"
TRANSITION_RESULT_SCHEMA = "agentic-sdlc/autonomous-transition-result@1"

ADMITTED = "admitted"

#: Inside the control envelope's 01:00..09:00 window, and after the proposal's own instant.
AT = "2026-08-20T03:00:00Z"
#: Deliberately before `NOT_BEFORE`, so the SAME control serves the window-boundary cases: a proposal
#: stated after the admission instant is its own refusal, and it would mask the boundary reason.
TRANSITION_STATED_AT = "2026-08-20T00:30:00Z"

EFFECT_CLASSES = (
    "advisory-artifact-write",
    "credential-access",
    "destructive-action",
    "egress-network-call",
    "evidence-record-append",
    "fan-in-mutation",
    "outward-effect",
    "owned-worktree-file-write",
    "permission-change",
    "repository-read",
    "subagent-dispatch",
)
TOOL_CLASSES = (
    "advisory-artifact-writer",
    "file-reader",
    "file-writer",
    "gate-runner",
    "network-fetch",
    "repository-search",
    "shell-command",
    "subagent-spawner",
    "version-control-read",
    "version-control-write",
)

#: Which change kinds each always-stop condition names, re-expressed so the behavioral partition below
#: has something independent to compare against. Seven rules name the twelve widenings between them.
STOP_RULE_KIND_SURFACE = {
    "ambiguous-ownership": ("custody-boundary",),
    "authority-expansion": ("approval", "authority", "stop-rule"),
    "budget-exhaustion": ("budget",),
    "corrupted-evidence": ("artifact",),
    "credential-or-security-boundary-change": ("route-constraint",),
    "expired-validity": (),
    "failed-drift-classification": (),
    "lost-attribution": (),
    "missing-transition-receipt": (),
    "new-destructive-or-outward-effect": ("egress", "removed-edge", "removed-node"),
    "partial-or-unknown-prior-effect": (),
    "publication-push-pr-merge-deployment": ("gate", "terminal-criterion"),
}

TRANSITION_BODY_KEYS = (
    "bound_envelope",
    "claimed_authority_class",
    "claimed_effect_class",
    "declared_egress",
    "declared_tool",
    "kind",
    "proposed_deltas",
    "schema",
    "stated_at",
    "transition_id",
)
RECEIPT_BODY_KEYS = ("at", "envelope_digest", "reasons", "schema", "transition_digest", "verdict")


def sealed_envelope(**overrides: Any) -> dict[str, Any]:
    """The control envelope, SEALED with this module's own derivation rather than by a subprocess.

    Sealing here is what makes the binding tests independent: the tool is later asked whether it agrees
    with the family's published derivation, not whether it agrees with its own earlier output.
    """
    return seal(envelope_body(**overrides))


def transition_body(envelope: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """One complete, valid autonomous-transition@1 body bound to `envelope`: the control to mutate."""
    body: dict[str, Any] = {
        "schema": TRANSITION_SCHEMA,
        "transition_id": "transition-slice-6-t8",
        "stated_at": TRANSITION_STATED_AT,
        "bound_envelope": {
            "envelope_digest": envelope["digest"],
            "envelope_id": envelope["envelope_id"],
        },
        "kind": "added-node",
        "claimed_authority_class": "owned-worktree-write",
        "claimed_effect_class": "owned-worktree-file-write",
        "declared_tool": "file-writer",
        "declared_egress": {"data_classes": [], "destinations": [], "posture": "none"},
        "proposed_deltas": {
            "attempts_for_node_after": 2,
            "concurrent_nodes_after": 2,
            "recursion_generations_after": 0,
            "total_retries_after": 3,
        },
    }
    body.update(overrides)
    return body


class TransitionCase(EnvelopeCase):
    """One admission spawn, and the two assertions every transition class is built out of."""

    def pair(self, **envelope_overrides: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        """The control pair: one sealed envelope and one transition bound to exactly that envelope."""
        envelope = sealed_envelope(**envelope_overrides)
        return envelope, transition_body(envelope)

    def admit(
        self,
        envelope: dict[str, Any],
        transition: Any,
        *,
        at: str = AT,
        out: Path | None = None,
    ) -> dict[str, Any]:
        argv = [
            "admit-transition",
            "--envelope",
            str(self.write(envelope, name="envelope.json")),
            "--transition",
            str(self.write(transition, name="transition.json")),
            "--at",
            at,
        ]
        if out is not None:
            argv += ["--out", str(out)]
        done = self.run_tool(argv)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        result = json.loads(done.stdout.decode("utf-8"))
        self.assertEqual(result["schema"], TRANSITION_RESULT_SCHEMA)
        return result

    def assert_admitted(self, envelope: dict[str, Any], transition: Any, *, at: str = AT) -> dict[str, Any]:
        """The positive control. NO reasons are tolerated, and the receipt must say `admitted`."""
        result = self.admit(envelope, transition, at=at)
        self.assertEqual(result["reasons"], [], result["reasons"])
        self.assertEqual(result["verdict"], ADMITTED)
        self.assertEqual(result["receipt"]["verdict"], ADMITTED)
        return result

    def assert_transition_refused(
        self,
        envelope: dict[str, Any],
        transition: Any,
        *,
        group: str,
        fragments: tuple[str, ...] = (),
        at: str = AT,
    ) -> dict[str, Any]:
        """One refusal, in the group that owns the property, naming every fragment asked for.

        A refusal still SEALS a receipt, and the receipt's own verdict and reasons must agree with the
        result document: two records of one refusal that disagreed would be worse than one.
        """
        result = self.admit(envelope, transition, at=at)
        self.assertEqual(result["verdict"], REFUSED)
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertFalse(groups[group]["met"], f"{group} reported met: {result['reasons']}")
        joined = " ".join(groups[group]["reasons"])
        for fragment in fragments:
            self.assertIn(fragment, joined)
        self.assertEqual(result["receipt"]["verdict"], REFUSED)
        self.assertEqual(result["receipt"]["reasons"], result["reasons"])
        return result


class TestTransitionControlAndReceipt(TransitionCase):
    """The positive control, what the receipt binds, and what it deliberately does not restate."""

    def test_the_control_pair_is_admitted_with_no_reasons(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition)

    def test_the_receipt_carries_exactly_its_six_facts_and_one_derived_digest(self) -> None:
        envelope, transition = self.pair()
        receipt = self.assert_admitted(envelope, transition)["receipt"]
        self.assertEqual(tuple(sorted(receipt)), tuple(sorted(RECEIPT_BODY_KEYS + ("digest",))))
        self.assertEqual(receipt["schema"], RECEIPT_SCHEMA)
        self.assertEqual(receipt["at"], AT)
        self.assertEqual(receipt["reasons"], [])

    def test_the_receipt_digest_is_the_familys_derivation_over_its_own_body(self) -> None:
        envelope, transition = self.pair()
        result = self.assert_admitted(envelope, transition)
        self.assertEqual(result["receipt"]["digest"], expected_digest(result["receipt"]))
        self.assertEqual(result["receipt_digest"], result["receipt"]["digest"])

    def test_the_receipt_binds_the_supplied_envelope_and_the_supplied_proposal(self) -> None:
        envelope, transition = self.pair()
        result = self.assert_admitted(envelope, transition)
        self.assertEqual(result["receipt"]["envelope_digest"], expected_digest(envelope))
        self.assertEqual(result["receipt"]["transition_digest"], expected_digest(transition))
        self.assertEqual(result["envelope_digest"], result["receipt"]["envelope_digest"])
        self.assertEqual(result["transition_digest"], result["receipt"]["transition_digest"])

    def test_the_receipt_restates_nothing_the_two_digests_already_bind(self) -> None:
        """The kind, the claimed classes, and both ids would each be a second origin in the receipt."""
        envelope, transition = self.pair()
        receipt = self.assert_admitted(envelope, transition)["receipt"]
        payload = canonical(receipt).decode("ascii")
        for restated in ("added-node", "owned-worktree-write", "file-writer", transition["transition_id"]):
            self.assertNotIn(restated, payload)
        self.assertIn(ADMITTED, payload)  # the positive control: this search really does find a member

    def test_a_refusal_is_recorded_in_a_sealed_receipt_too(self) -> None:
        envelope, transition = self.pair()
        transition["kind"] = "budget"
        result = self.assert_transition_refused(envelope, transition, group="transition-kind")
        receipt = result["receipt"]
        self.assertEqual(receipt["digest"], expected_digest(receipt))
        self.assertEqual(receipt["at"], AT)
        self.assertEqual(receipt["transition_digest"], expected_digest(transition))
        self.assertNotEqual(receipt["reasons"], [])

    def test_the_consequence_says_an_admitted_transition_authorizes_nothing(self) -> None:
        envelope, transition = self.pair()
        consequence = self.assert_admitted(envelope, transition)["consequence"]
        for fragment in ("authorizes no dispatch", "no outward effect"):
            self.assertIn(fragment, consequence)

    def test_the_residuals_name_the_plan_relative_gap_and_the_receipt_envelope_choice(self) -> None:
        envelope, transition = self.pair()
        residuals = " ".join(self.assert_admitted(envelope, transition)["residuals"])
        for fragment in (
            "ENVELOPE-relative",
            "receipt-envelope@1",
            "T4's extension",
            "missing-transition-receipt",
            "--at",
        ):
            self.assertIn(fragment, residuals)


class TestTransitionClosedShape(TransitionCase):
    """Default-off in the proposal: an absent field refuses, and every refusal names the field."""

    def test_the_control_is_admitted_before_any_field_is_removed(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition)

    def test_removing_any_single_field_refuses_and_names_it(self) -> None:
        envelope, control = self.pair()
        self.assertEqual(tuple(sorted(control)), TRANSITION_BODY_KEYS)
        for field in TRANSITION_BODY_KEYS:
            with self.subTest(field=field):
                transition = {key: value for key, value in control.items() if key != field}
                self.assert_transition_refused(
                    envelope, transition, group="closed-key-set", fragments=(f"carries no {field}",)
                )

    def test_an_unknown_field_is_refused_rather_than_ignored(self) -> None:
        envelope, transition = self.pair()
        transition["urgency"] = "high"
        self.assert_transition_refused(
            envelope, transition, group="closed-key-set", fragments=("unknown field 'urgency'",)
        )

    def test_a_proposal_that_already_carries_a_digest_is_refused_by_name(self) -> None:
        envelope, transition = self.pair()
        self.assert_transition_refused(
            envelope, seal(transition), group="closed-key-set", fragments=("second origin",)
        )

    def test_a_wrong_schema_string_is_refused(self) -> None:
        envelope, transition = self.pair()
        transition["schema"] = "agentic-sdlc/autonomous-transition@2"
        self.assert_transition_refused(
            envelope, transition, group="closed-key-set", fragments=("declares schema",)
        )

    def test_removing_any_nested_field_refuses_and_names_the_closed_key_set(self) -> None:
        envelope, control = self.pair()
        cases = {
            "bound_envelope": ("envelope_digest", "envelope_id"),
            "declared_egress": ("data_classes", "destinations", "posture"),
            "proposed_deltas": (
                "attempts_for_node_after",
                "concurrent_nodes_after",
                "recursion_generations_after",
                "total_retries_after",
            ),
        }
        groups = {
            "bound_envelope": "envelope-digest-binding",
            "declared_egress": "declared-egress",
            "proposed_deltas": "proposed-deltas",
        }
        for field, keys in cases.items():
            for key in keys:
                with self.subTest(field=field, key=key):
                    transition = dict(control)
                    inner = dict(control[field])
                    del inner[key]
                    transition[field] = inner
                    self.assert_transition_refused(
                        envelope,
                        transition,
                        group=groups[field],
                        fragments=(f"missing ['{key}']",),
                    )

    def test_an_unknown_nested_field_is_refused(self) -> None:
        envelope, control = self.pair()
        transition = dict(control)
        transition["proposed_deltas"] = dict(control["proposed_deltas"], nodes_after=9)
        self.assert_transition_refused(
            envelope, transition, group="proposed-deltas", fragments=("unexpected ['nodes_after']",)
        )

    def test_the_transition_names_no_provider_and_no_model_anywhere(self) -> None:
        """Route identity is the RuntimeAssignment's; a proposal that pinned one would be a second origin."""
        envelope, transition = self.pair()
        payload = canonical(transition).decode("ascii").lower()
        for forbidden in ("provider", "model", "claude", "gpt", "anthropic"):
            self.assertNotIn(forbidden, payload)
        self.assertIn("kind", payload)  # the positive control: this search really does find a key


class TestEnvelopeAdmissibility(TransitionCase):
    """An allowlist read out of an inadmissible envelope is not an allowlist."""

    def test_the_control_envelope_is_admissible(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition)

    def test_an_envelope_that_verify_would_refuse_refuses_the_admission_too(self) -> None:
        envelope, transition = self.pair(
            concurrency_limits={"max_concurrent_nodes": 2, "max_recursion_generations": 1}
        )
        self.assert_transition_refused(
            envelope,
            transition,
            group="envelope-admissibility",
            fragments=("concurrency-and-recursion", "SEPARATE capability"),
        )

    def test_an_envelope_edited_after_sealing_refuses(self) -> None:
        envelope, transition = self.pair()
        envelope["envelope_id"] = "auto-slice-6-edited"
        self.assert_transition_refused(
            envelope, transition, group="envelope-admissibility", fragments=("does not re-derive",)
        )

    def test_an_unreadable_allowlist_silences_the_membership_check_it_would_have_fed(self) -> None:
        """One mistake, one reason: the tool group stays MET rather than comparing against a bad field."""
        envelope, transition = self.pair(tool_allowlist="file-writer")
        result = self.assert_transition_refused(
            envelope, transition, group="envelope-admissibility", fragments=("tool-allowlist",)
        )
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertTrue(groups["declared-tool"]["met"], groups["declared-tool"]["reasons"])

    def test_an_unsealed_envelope_body_is_refused_rather_than_admitted_on_trust(self) -> None:
        """`admit-transition` reads a SEALED envelope; an unsealed body carries no digest to bind."""
        body = envelope_body()
        transition = transition_body(seal(body))
        self.assert_transition_refused(
            body, transition, group="envelope-admissibility", fragments=("carries no digest",)
        )

    def test_every_envelope_check_group_can_reach_the_folded_group(self) -> None:
        """The positive control for the fold: the envelope's own slug is preserved in the sentence."""
        envelope, transition = self.pair(stop_rules=list(STOP_RULE_KINDS[:-1]))
        self.assert_transition_refused(
            envelope, transition, group="envelope-admissibility", fragments=("stop-rules", "omits")
        )


class TestEnvelopeDigestBinding(TransitionCase):
    """The check that makes the pair a PAIR rather than two documents that arrived together."""

    def test_the_control_binding_is_admitted(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition)

    def test_a_transition_bound_to_another_envelope_is_refused(self) -> None:
        envelope, transition = self.pair()
        other = sealed_envelope(envelope_id="auto-slice-6-other")
        self.assertNotEqual(other["digest"], envelope["digest"])  # the control: the two really differ
        transition["bound_envelope"] = dict(transition["bound_envelope"], envelope_digest=other["digest"])
        self.assert_transition_refused(
            envelope,
            transition,
            group="envelope-digest-binding",
            fragments=(other["digest"], envelope["digest"], "written against a different envelope"),
        )

    def test_a_bound_id_that_names_another_envelope_is_refused(self) -> None:
        envelope, transition = self.pair()
        transition["bound_envelope"] = dict(transition["bound_envelope"], envelope_id="auto-slice-6-other")
        self.assert_transition_refused(
            envelope,
            transition,
            group="envelope-digest-binding",
            fragments=("names the wrong envelope",),
        )

    def test_a_bound_digest_of_the_wrong_shape_is_refused(self) -> None:
        envelope, transition = self.pair()
        for value in ("", "not-a-digest", "A" * 64, 7, None):
            with self.subTest(value=value):
                transition["bound_envelope"] = dict(transition["bound_envelope"], envelope_digest=value)
                self.assert_transition_refused(
                    envelope,
                    transition,
                    group="envelope-digest-binding",
                    fragments=("64 lowercase hexadecimal",),
                )


class TestAdmissionWindow(TransitionCase):
    """`--at` must be STRICTLY inside the window, and both edges are tested from both sides."""

    def test_an_instant_well_inside_the_window_is_admitted(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition, at=AT)

    def test_the_opening_edge_itself_is_refused(self) -> None:
        envelope, transition = self.pair()
        self.assert_transition_refused(
            envelope,
            transition,
            group="admission-window",
            fragments=("not strictly after", NOT_BEFORE),
            at=NOT_BEFORE,
        )

    def test_one_second_inside_the_opening_edge_is_admitted(self) -> None:
        """The positive control for the edge above: the bound has not quietly moved inward."""
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition, at="2026-08-20T01:00:01Z")

    def test_the_closing_edge_itself_is_refused_as_the_expired_validity_stop(self) -> None:
        envelope, transition = self.pair()
        self.assert_transition_refused(
            envelope,
            transition,
            group="admission-window",
            fragments=("not strictly before", NOT_AFTER, "expired-validity"),
            at=NOT_AFTER,
        )

    def test_one_second_inside_the_closing_edge_is_admitted(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition, at="2026-08-20T08:59:59Z")

    def test_an_instant_before_the_window_and_one_after_are_each_refused(self) -> None:
        envelope, transition = self.pair()
        for at, fragment in (
            ("2026-08-20T00:59:59Z", "not strictly after"),
            ("2026-08-20T09:00:01Z", "not strictly before"),
        ):
            with self.subTest(at=at):
                self.assert_transition_refused(
                    envelope, transition, group="admission-window", fragments=(fragment,), at=at
                )


class TestTransitionIdentity(TransitionCase):
    """The proposal's own id and instant, and the one ordering `--at` makes checkable."""

    def test_the_control_identity_is_admitted(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition)

    def test_a_proposal_stated_after_the_admission_instant_is_refused(self) -> None:
        envelope, transition = self.pair()
        transition["stated_at"] = "2026-08-20T04:00:00Z"
        self.assert_transition_refused(
            envelope,
            transition,
            group="transition-identity",
            fragments=("after the admission instant", AT),
        )

    def test_a_proposal_stated_at_exactly_the_admission_instant_is_admitted(self) -> None:
        """The positive control for the ordering above: equal is not after."""
        envelope, transition = self.pair()
        transition["stated_at"] = AT
        self.assert_admitted(envelope, transition)

    def test_the_transition_id_refuses_a_non_identifier(self) -> None:
        envelope, transition = self.pair()
        transition["transition_id"] = "transition slice 6"
        self.assert_transition_refused(
            envelope, transition, group="transition-identity", fragments=("unreserved characters",)
        )

    def test_the_stated_at_refuses_a_non_ascii_digit_instant(self) -> None:
        """The guard is `[0-9]`, not `\\d`; `TestInstantCharacterClass` holds the positive control."""
        envelope, transition = self.pair()
        transition["stated_at"] = TestInstantCharacterClass.ARABIC_INDIC
        self.assert_transition_refused(
            envelope, transition, group="transition-identity", fragments=("YYYY-MM-DDTHH:MM:SSZ",)
        )


class TestKindAndStopRules(TransitionCase):
    """The kind against the envelope's allowlist, and against the stop rules the envelope carries."""

    def test_each_autonomous_kind_is_admitted(self) -> None:
        envelope, control = self.pair()
        for kind in AUTONOMOUS_CHANGE_KINDS:
            with self.subTest(kind=kind):
                self.assert_admitted(envelope, dict(control, kind=kind))

    def test_all_sixteen_kinds_partition_into_four_admitted_and_twelve_refused_twice(self) -> None:
        """Behavioral: each kind is offered to the tool, and BOTH groups are read for each verdict.

        The stop-rule group exists to survive a widening of the allowlist group, so counting verdicts
        alone would not notice it disappearing. Every refused kind must be refused in both.
        """
        envelope, control = self.pair()
        admitted: list[str] = []
        refused: list[str] = []
        for kind in CHANGE_KINDS:
            with self.subTest(kind=kind):
                result = self.admit(envelope, dict(control, kind=kind))
                groups = {entry["slug"]: entry for entry in result["checks"]}
                if result["verdict"] == ADMITTED:
                    admitted.append(kind)
                    self.assertTrue(groups["stop-rules"]["met"])
                    continue
                refused.append(kind)
                self.assertFalse(groups["transition-kind"]["met"], kind)
                self.assertFalse(groups["stop-rules"]["met"], kind)
        self.assertEqual(tuple(admitted), AUTONOMOUS_CHANGE_KINDS)
        self.assertEqual(len(refused), 12)

    def test_each_refused_kind_is_named_by_the_stop_rule_that_governs_it(self) -> None:
        envelope, control = self.pair()
        for rule, kinds in STOP_RULE_KIND_SURFACE.items():
            for kind in kinds:
                with self.subTest(rule=rule, kind=kind):
                    self.assert_transition_refused(
                        envelope, dict(control, kind=kind), group="stop-rules", fragments=(rule, kind)
                    )

    def test_a_kind_the_envelope_narrowed_away_is_refused_while_the_wider_envelope_admits_it(self) -> None:
        wide, control = self.pair()
        self.assert_admitted(wide, dict(control, kind="added-node"))
        narrow = sealed_envelope(graph_change_allowlist=["retry"])
        narrow_transition = transition_body(narrow, kind="added-node")
        self.assert_transition_refused(
            narrow,
            narrow_transition,
            group="transition-kind",
            fragments=("is not in the envelope's graph_change_allowlist", "['retry']"),
        )

    def test_an_envelope_that_allows_no_graph_change_admits_no_transition(self) -> None:
        empty = sealed_envelope(graph_change_allowlist=[], retry_policy=dict(NO_RETRY_POLICY))
        transition = transition_body(
            empty,
            proposed_deltas={
                "attempts_for_node_after": 1,
                "concurrent_nodes_after": 2,
                "recursion_generations_after": 0,
                "total_retries_after": 0,
            },
        )
        self.assert_transition_refused(
            empty, transition, group="transition-kind", fragments=("admits no transition at all",)
        )

    def test_an_unknown_kind_is_refused_against_the_closed_vocabulary(self) -> None:
        envelope, transition = self.pair()
        transition["kind"] = "added-worktree"
        self.assert_transition_refused(
            envelope, transition, group="transition-kind", fragments=("is not one of",)
        )


def read_only_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """A sealed read-only envelope and a transition that claims only what that envelope admits.

    This is the OTHER half of every authority, effect, and tool control below: the class the write
    envelope admits must be refused here, so a membership check that stopped discriminating fails.
    """
    envelope = seal(read_only_body())
    transition = transition_body(
        envelope,
        claimed_authority_class="read-only-advisory",
        claimed_effect_class="repository-read",
        declared_tool="file-reader",
    )
    return envelope, transition


class TestClaimedAuthority(TransitionCase):
    """The claimed authority class, against the envelope's approved ladder prefix."""

    def test_both_controls_are_admitted(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition)
        self.assert_admitted(*read_only_pair())

    def test_a_rung_the_read_only_envelope_withheld_is_refused(self) -> None:
        """The write ladder admits this exact claim, so the refusal is about the envelope, not the value."""
        envelope, transition = read_only_pair()
        transition["claimed_authority_class"] = "owned-worktree-write"
        self.assert_transition_refused(
            envelope,
            transition,
            group="claimed-authority",
            fragments=("cannot add or widen authority", "['read-only-advisory']"),
        )

    def test_each_rung_above_the_envelopes_prefix_is_refused(self) -> None:
        envelope, control = self.pair()
        for rung in AUTHORITY_CLASSES[2:]:
            with self.subTest(rung=rung):
                self.assert_transition_refused(
                    envelope,
                    dict(control, claimed_authority_class=rung),
                    group="claimed-authority",
                    fragments=("does not admit",),
                )

    def test_an_unknown_rung_is_refused_against_the_closed_vocabulary(self) -> None:
        envelope, transition = self.pair()
        transition["claimed_authority_class"] = "worktree-write"
        self.assert_transition_refused(
            envelope, transition, group="claimed-authority", fragments=("is not one of",)
        )


class TestClaimedEffect(TransitionCase):
    """The claimed effect class, against the envelope's effect allowlist and against doctrine."""

    def test_each_effect_the_control_envelope_lists_is_admitted(self) -> None:
        envelope, control = self.pair()
        for effect in envelope_body()["allowed_effect_classes"]:
            with self.subTest(effect=effect):
                self.assert_admitted(envelope, dict(control, claimed_effect_class=effect))

    def test_every_non_delegable_effect_is_refused_with_the_doctrine_sentence(self) -> None:
        envelope, control = self.pair()
        for effect in NON_DELEGABLE_EFFECTS:
            with self.subTest(effect=effect):
                self.assert_transition_refused(
                    envelope,
                    dict(control, claimed_effect_class=effect),
                    group="claimed-effect",
                    fragments=("non-delegable", "independently of any allowlist"),
                )

    def test_an_in_vocabulary_effect_the_envelope_did_not_list_is_refused(self) -> None:
        envelope, transition = read_only_pair()
        transition["claimed_effect_class"] = "owned-worktree-file-write"
        self.assert_transition_refused(
            envelope, transition, group="claimed-effect", fragments=("an unlisted effect is refused",)
        )

    def test_an_unknown_effect_is_refused_against_the_closed_vocabulary(self) -> None:
        envelope, transition = self.pair()
        transition["claimed_effect_class"] = "worktree-write"
        self.assert_transition_refused(
            envelope, transition, group="claimed-effect", fragments=("is not one of",)
        )


class TestDeclaredTool(TransitionCase):
    """Exactly one declared tool class, against the envelope's tool allowlist."""

    def test_each_tool_the_control_envelope_lists_is_admitted(self) -> None:
        envelope, control = self.pair()
        for tool in envelope_body()["tool_allowlist"]:
            with self.subTest(tool=tool):
                self.assert_admitted(envelope, dict(control, declared_tool=tool))

    def test_every_tool_class_the_envelope_omitted_is_refused(self) -> None:
        envelope, control = self.pair()
        listed = set(envelope_body()["tool_allowlist"])
        omitted = [tool for tool in TOOL_CLASSES if tool not in listed]
        self.assertNotEqual(omitted, [])  # the control: there really are omitted classes to test
        for tool in omitted:
            with self.subTest(tool=tool):
                self.assert_transition_refused(
                    envelope,
                    dict(control, declared_tool=tool),
                    group="declared-tool",
                    fragments=("an unlisted capability is refused",),
                )

    def test_a_write_tool_the_read_only_envelope_withheld_is_refused(self) -> None:
        envelope, transition = read_only_pair()
        transition["declared_tool"] = "file-writer"
        self.assert_transition_refused(
            envelope, transition, group="declared-tool", fragments=("does not admit",)
        )

    def test_an_envelope_that_lists_no_tool_class_admits_no_transition(self) -> None:
        envelope = sealed_envelope(tool_allowlist=[])
        self.assert_transition_refused(
            envelope,
            transition_body(envelope),
            group="declared-tool",
            fragments=("admits no transition, because every proposal declares exactly one",),
        )

    def test_an_unknown_tool_class_is_refused_against_the_closed_vocabulary(self) -> None:
        envelope, transition = self.pair()
        transition["declared_tool"] = "Edit"
        self.assert_transition_refused(
            envelope, transition, group="declared-tool", fragments=("is not one of",)
        )


class TestDeclaredEgress(TransitionCase):
    """The declared egress, against the envelope's posture and its two empty lists."""

    def test_the_two_empty_lists_under_the_none_posture_are_admitted(self) -> None:
        envelope, transition = self.pair()
        self.assert_admitted(envelope, transition)

    def test_a_named_destination_or_data_class_is_outside_the_envelopes_empty_lists(self) -> None:
        envelope, control = self.pair()
        for field, value in (("destinations", "cache.example.invalid"), ("data_classes", "repository-content")):
            with self.subTest(field=field):
                egress = dict(control["declared_egress"])
                egress[field] = [value]
                self.assert_transition_refused(
                    envelope,
                    dict(control, declared_egress=egress),
                    group="declared-egress",
                    fragments=(value, "cannot add or widen egress"),
                )

    def test_any_posture_other_than_none_is_outside_the_vocabulary(self) -> None:
        envelope, control = self.pair()
        for posture in ("allowlisted", "any", "none-ish", ""):
            with self.subTest(posture=posture):
                egress = dict(control["declared_egress"], posture=posture)
                self.assert_transition_refused(
                    envelope, dict(control, declared_egress=egress), group="declared-egress"
                )

    def test_an_unsorted_or_repeated_declared_list_is_refused(self) -> None:
        envelope, control = self.pair()
        egress = dict(control["declared_egress"], destinations=["b.invalid", "a.invalid"])
        self.assert_transition_refused(
            envelope,
            dict(control, declared_egress=egress),
            group="declared-egress",
            fragments=("strictly ascending set",),
        )


class TestProposedDeltas(TransitionCase):
    """Four proposed after-counts, each against the envelope's own ceiling for it."""

    #: The control envelope's four limits, in the order the deltas name them.
    LIMITS = (
        ("attempts_for_node_after", 2),
        ("concurrent_nodes_after", 2),
        ("recursion_generations_after", 0),
        ("total_retries_after", 4),
    )

    def test_a_delta_sitting_exactly_on_every_limit_is_admitted(self) -> None:
        """The positive control ON the boundary: at the limit is inside it, one past is not."""
        envelope, control = self.pair()
        self.assert_admitted(
            envelope, dict(control, proposed_deltas={key: limit for key, limit in self.LIMITS})
        )

    def test_one_past_each_limit_is_refused_and_names_that_limit(self) -> None:
        envelope, control = self.pair()
        where = {
            "attempts_for_node_after": "retry_policy.max_attempts_per_node",
            "concurrent_nodes_after": "concurrency_limits.max_concurrent_nodes",
            "recursion_generations_after": "concurrency_limits.max_recursion_generations",
            "total_retries_after": "retry_policy.max_total_retries",
        }
        for key, limit in self.LIMITS:
            with self.subTest(key=key):
                deltas = dict(control["proposed_deltas"])
                deltas[key] = limit + 1
                self.assert_transition_refused(
                    envelope,
                    dict(control, proposed_deltas=deltas),
                    group="proposed-deltas",
                    fragments=(f"proposed_deltas.{key} is {limit + 1}", where[key], "cannot add or widen"),
                )

    def test_a_raised_recursion_count_earns_the_separate_capability_sentence(self) -> None:
        envelope, control = self.pair()
        deltas = dict(control["proposed_deltas"], recursion_generations_after=1)
        self.assert_transition_refused(
            envelope,
            dict(control, proposed_deltas=deltas),
            group="proposed-deltas",
            fragments=("SEPARATE capability",),
        )

    def test_four_raised_counts_earn_four_reasons_rather_than_the_first_one(self) -> None:
        envelope, control = self.pair()
        deltas = {key: limit + 1 for key, limit in self.LIMITS}
        result = self.assert_transition_refused(
            envelope, dict(control, proposed_deltas=deltas), group="proposed-deltas"
        )
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertEqual(len(groups["proposed-deltas"]["reasons"]), 4)

    def test_a_negative_count_is_a_range_error_rather_than_a_limit_error(self) -> None:
        """A number below the floor has no limit to exceed, so the range still owns that side."""
        envelope, control = self.pair()
        deltas = dict(control["proposed_deltas"], concurrent_nodes_after=-1)
        result = self.assert_transition_refused(
            envelope,
            dict(control, proposed_deltas=deltas),
            group="proposed-deltas",
            fragments=("outside the admitted range",),
        )
        self.assertNotIn("exceeds the envelope", " ".join(result["reasons"]))

    def test_a_boolean_is_not_a_count(self) -> None:
        envelope, control = self.pair()
        deltas = dict(control["proposed_deltas"], concurrent_nodes_after=True)
        self.assert_transition_refused(
            envelope,
            dict(control, proposed_deltas=deltas),
            group="proposed-deltas",
            fragments=("is not an integer",),
        )

    def test_a_narrowed_envelope_refuses_a_count_the_wider_envelope_admits(self) -> None:
        wide, control = self.pair()
        at_the_wider_limit = dict(control["proposed_deltas"], concurrent_nodes_after=2)
        self.assert_admitted(wide, dict(control, proposed_deltas=at_the_wider_limit))
        narrow = sealed_envelope(
            concurrency_limits={"max_concurrent_nodes": 1, "max_recursion_generations": 0}
        )
        self.assert_transition_refused(
            narrow,
            transition_body(narrow),
            group="proposed-deltas",
            fragments=("exceeds the envelope's concurrency_limits.max_concurrent_nodes 1",),
        )


class TestReceiptOutputPath(TransitionCase):
    """`--out` is a second copy of the same bytes, and it overwrites nothing."""

    def test_the_out_file_is_byte_identical_to_the_receipt_in_the_result(self) -> None:
        envelope, transition = self.pair()
        target = self.scratch() / "receipt.json"
        result = self.admit(envelope, transition, out=target)
        self.assertEqual(result["verdict"], ADMITTED, result["reasons"])
        self.assertEqual(target.read_bytes(), canonical(result["receipt"]))
        self.assertEqual(result["wrote"], str(target))

    def test_without_out_nothing_is_written_and_wrote_is_null(self) -> None:
        envelope, transition = self.pair()
        directory = self.scratch()
        envelope_path = directory / "envelope.json"
        envelope_path.write_bytes(canonical(envelope))
        transition_path = directory / "transition.json"
        transition_path.write_bytes(canonical(transition))
        before = sorted(entry.name for entry in directory.iterdir())
        done = self.run_tool(
            [
                "admit-transition",
                "--envelope", str(envelope_path),
                "--transition", str(transition_path),
                "--at", AT,
            ]
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        self.assertIsNone(json.loads(done.stdout.decode("utf-8"))["wrote"])
        self.assertEqual(sorted(entry.name for entry in directory.iterdir()), before)

    def test_an_occupied_out_path_refuses_the_transition_and_leaves_the_file_alone(self) -> None:
        """A receipt that cannot be recorded is the missing-transition-receipt stop, so admission stops."""
        envelope, transition = self.pair()
        target = self.scratch() / "receipt.json"
        target.write_bytes(b"prior evidence\n")
        # The positive control is the test above: the SAME pair and an unoccupied path are admitted.
        result = self.admit(envelope, transition, out=target)
        self.assertEqual(result["verdict"], REFUSED, result["reasons"])
        groups = {entry["slug"]: entry for entry in result["checks"]}
        joined = " ".join(groups["output-path"]["reasons"])
        for fragment in ("already exists", "missing-transition-receipt"):
            self.assertIn(fragment, joined)
        self.assertEqual(result["receipt"]["verdict"], REFUSED)
        self.assertIsNone(result["wrote"])
        self.assertEqual(target.read_bytes(), b"prior evidence\n")

    def test_an_out_path_with_no_parent_directory_is_refused(self) -> None:
        envelope, transition = self.pair()
        target = self.scratch() / "absent" / "receipt.json"
        result = self.admit(envelope, transition, out=target)
        self.assertEqual(result["verdict"], REFUSED)
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertIn("nowhere to land", " ".join(groups["output-path"]["reasons"]))
        self.assertFalse(target.parent.exists())

    def test_a_refused_transitions_receipt_is_written_too(self) -> None:
        envelope, transition = self.pair()
        transition["kind"] = "authority"
        target = self.scratch() / "receipt.json"
        result = self.admit(envelope, transition, out=target)
        self.assertEqual(result["verdict"], REFUSED)
        recorded = json.loads(target.read_bytes().decode("utf-8"))
        self.assertEqual(recorded["verdict"], REFUSED)
        self.assertEqual(recorded, result["receipt"])
        self.assertNotEqual(recorded["reasons"], [])


def receipt_body(**overrides: Any) -> dict[str, Any]:
    """One valid autonomous-transition-receipt@1 body, hand-built by this module rather than by the tool."""
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "at": AT,
        "envelope_digest": fake_digest("some envelope"),
        "transition_digest": fake_digest("some transition"),
        "verdict": ADMITTED,
        "reasons": [],
    }
    body.update(overrides)
    return body


class TestReceiptDigestRoundTrip(TransitionCase):
    """The receipt the tool sealed, re-derived; and a receipt this module sealed, accepted."""

    def verify_receipt(self, document: Any, *, expect: str | None = None) -> dict[str, Any]:
        argv = ["verify-receipt", "--receipt", str(self.write(document, name="receipt.json"))]
        if expect is not None:
            argv += ["--expect-digest", expect]
        done = self.run_tool(argv)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        result = json.loads(done.stdout.decode("utf-8"))
        self.assertEqual(result["schema"], TRANSITION_RESULT_SCHEMA)
        return result

    def test_admit_then_verify_receipt_agree_on_the_one_digest(self) -> None:
        envelope, transition = self.pair()
        admitted = self.assert_admitted(envelope, transition)
        verified = self.verify_receipt(admitted["receipt"], expect=admitted["receipt_digest"])
        self.assertEqual(verified["reasons"], [], verified["reasons"])
        self.assertEqual(verified["verdict"], VERIFIED)
        self.assertEqual(verified["receipt_digest"], admitted["receipt_digest"])
        self.assertEqual(verified["envelope_digest"], admitted["envelope_digest"])
        self.assertEqual(verified["transition_digest"], admitted["transition_digest"])

    def test_a_receipt_sealed_by_this_module_verifies(self) -> None:
        """The tool is proved to agree with the family's published derivation, not with itself."""
        result = self.verify_receipt(seal(receipt_body()))
        self.assertEqual(result["verdict"], VERIFIED, result["reasons"])

    def test_an_edited_receipt_refuses(self) -> None:
        sealed = seal(receipt_body())
        sealed["at"] = "2026-08-20T04:00:00Z"
        result = self.verify_receipt(sealed)
        self.assertEqual(result["verdict"], REFUSED)
        groups = {entry["slug"]: entry for entry in result["checks"]}
        self.assertIn("does not re-derive", " ".join(groups["digest"]["reasons"]))
        self.assertIsNone(result["receipt"])
        self.assertIsNone(result["receipt_digest"])

    def test_expect_digest_admits_the_match_and_refuses_a_mismatch(self) -> None:
        sealed = seal(receipt_body())
        self.assertEqual(self.verify_receipt(sealed, expect=sealed["digest"])["verdict"], VERIFIED)
        other = fake_digest("some other receipt")
        result = self.verify_receipt(sealed, expect=other)
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn(other, " ".join(result["reasons"]))

    def test_a_verdict_and_a_reason_set_that_disagree_are_two_outcomes_at_once(self) -> None:
        for body, fragment in (
            (receipt_body(verdict=ADMITTED, reasons=["something was wrong"]), "two outcomes recorded at once"),
            (receipt_body(verdict=REFUSED, reasons=[]), "names nothing"),
        ):
            with self.subTest(verdict=body["verdict"]):
                result = self.verify_receipt(seal(body))
                self.assertEqual(result["verdict"], REFUSED)
                self.assertIn(fragment, " ".join(result["reasons"]))

    def test_the_coherent_pair_in_both_directions_is_verified(self) -> None:
        """The positive control for the check above: both coherent combinations are accepted."""
        for body in (
            receipt_body(verdict=ADMITTED, reasons=[]),
            receipt_body(verdict=REFUSED, reasons=["the transition's kind 'budget' is not admitted"]),
        ):
            with self.subTest(verdict=body["verdict"]):
                self.assertEqual(self.verify_receipt(seal(body))["verdict"], VERIFIED)

    def test_a_verdict_outside_the_two_is_refused(self) -> None:
        result = self.verify_receipt(seal(receipt_body(verdict="defined")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("is not one of", " ".join(result["reasons"]))

    def test_removing_any_receipt_field_refuses_and_names_it(self) -> None:
        control = seal(receipt_body())
        for field in RECEIPT_BODY_KEYS + ("digest",):
            with self.subTest(field=field):
                document = {key: value for key, value in control.items() if key != field}
                result = self.verify_receipt(document)
                self.assertEqual(result["verdict"], REFUSED)
                self.assertIn(f"carries no {field}", " ".join(result["reasons"]))

    def test_an_unknown_receipt_field_is_refused(self) -> None:
        body = receipt_body()
        body["kind"] = "added-node"
        result = self.verify_receipt(seal(body))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("unknown field 'kind'", " ".join(result["reasons"]))

    def test_a_wrong_receipt_schema_is_refused(self) -> None:
        result = self.verify_receipt(seal(receipt_body(schema="agentic-sdlc/receipt-envelope@1")))
        self.assertEqual(result["verdict"], REFUSED)
        self.assertIn("declares schema", " ".join(result["reasons"]))

    def test_a_malformed_expect_digest_is_unusable_input_before_any_file_is_read(self) -> None:
        done = self.run_tool(["verify-receipt", "--receipt", "/nonexistent", "--expect-digest", "abc"])
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertEqual(done.stdout, b"")


class TestAdmissionUnusableInput(TransitionCase):
    """Exit 2 is the QUESTION being unusable, never the answer being 'refused'."""

    def argv(self, *, at: str) -> list[str]:
        envelope, transition = self.pair()
        return [
            "admit-transition",
            "--envelope", str(self.write(envelope, name="envelope.json")),
            "--transition", str(self.write(transition, name="transition.json")),
            "--at", at,
        ]

    def test_the_positive_control_is_that_the_same_argv_shape_exits_zero(self) -> None:
        done = self.run_tool(self.argv(at=AT))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)

    def test_an_at_that_is_not_this_familys_instant_is_exit_two(self) -> None:
        for at in ("2026-08-20", "2026-08-20T03:00:00", "now", "", TestInstantCharacterClass.ARABIC_INDIC):
            with self.subTest(at=at):
                done = self.run_tool(self.argv(at=at))
                self.assertEqual(done.returncode, EXIT_INPUT, done.stdout)
                self.assertEqual(done.stdout, b"")

    def test_an_at_with_the_right_shape_and_no_calendar_moment_is_exit_two(self) -> None:
        done = self.run_tool(self.argv(at="2026-13-45T99:00:00Z"))
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout)

    def test_a_missing_at_is_a_grammar_error(self) -> None:
        envelope, transition = self.pair()
        done = self.run_tool(
            [
                "admit-transition",
                "--envelope", str(self.write(envelope, name="envelope.json")),
                "--transition", str(self.write(transition, name="transition.json")),
            ]
        )
        self.assertEqual(done.returncode, EXIT_INPUT)

    def test_a_non_finite_number_in_the_transition_is_refused_by_the_post_parse_walk(self) -> None:
        envelope, transition = self.pair()
        directory = self.scratch()
        path = directory / "transition.json"
        path.write_text(
            json.dumps(transition).replace('"total_retries_after": 3', '"total_retries_after": 1e400'),
            encoding="utf-8",
        )
        done = self.run_tool(
            [
                "admit-transition",
                "--envelope", str(self.write(envelope, name="envelope.json")),
                "--transition", str(path),
                "--at", AT,
            ]
        )
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout)
        self.assertIn(b"non-finite", done.stderr)

    def test_an_absent_document_is_refused_without_a_traceback(self) -> None:
        envelope, transition = self.pair()
        for missing in ("--envelope", "--transition"):
            with self.subTest(missing=missing):
                argv = [
                    "admit-transition",
                    "--envelope", str(self.write(envelope, name="envelope.json")),
                    "--transition", str(self.write(transition, name="transition.json")),
                    "--at", AT,
                ]
                argv[argv.index(missing) + 1] = str(self.scratch() / "absent.json")
                done = self.run_tool(argv)
                self.assertEqual(done.returncode, EXIT_INPUT)
                self.assertNotIn(b"Traceback", done.stderr)


class TestAdmissionDeterminism(TransitionCase):
    """The receipt's bytes depend on the two documents and `--at`, and on nothing ambient."""

    def test_two_hash_seeds_produce_identical_receipt_bytes(self) -> None:
        envelope, transition = self.pair()
        argv = [
            "admit-transition",
            "--envelope", str(self.write(envelope, name="envelope.json")),
            "--transition", str(self.write(transition, name="transition.json")),
            "--at", AT,
        ]
        first = self.run_tool(argv, extra={"PYTHONHASHSEED": "0"})
        second = self.run_tool(argv, extra={"PYTHONHASHSEED": "1"})
        self.assertEqual(first.returncode, EXIT_OK, first.stderr)
        self.assertEqual(first.stdout, second.stdout)


class TestAdmissionAgainstRealSiblingDigests(TransitionCase):
    """One admission against an envelope bound to digests the REAL siblings produced.

    Every other class here uses well-formed stand-in digests, because their subject is the admission's
    own logic. This one exists so the pair is exercised once against values `wave-plan-compiler.py` and
    `planning-snapshot.py` actually sealed, rather than against 64 hex characters this module invented.
    """

    def require_siblings(self) -> None:
        if "plan_digest" not in FIXTURES:
            self.skipTest(NO_GIT)

    def bound_envelope(self) -> dict[str, Any]:
        return sealed_envelope(
            bound_plan={
                "plan_digest": FIXTURES["plan_digest"],
                "plan_revision": FIXTURES["plan_revision"],
                "snapshot_digest": FIXTURES["snapshot_digest"],
            }
        )

    def test_a_transition_is_admitted_against_the_real_bound_digests(self) -> None:
        self.require_siblings()
        envelope = self.bound_envelope()
        result = self.assert_admitted(envelope, transition_body(envelope))
        self.assertEqual(result["receipt"]["envelope_digest"], expected_digest(envelope))

    def test_the_receipt_binds_the_envelope_and_never_restates_the_plan_it_binds(self) -> None:
        """The plan is two hops away: the receipt binds the envelope, and the envelope binds the plan."""
        self.require_siblings()
        envelope = self.bound_envelope()
        receipt = self.assert_admitted(envelope, transition_body(envelope))["receipt"]
        payload = canonical(receipt).decode("ascii")
        self.assertNotIn(FIXTURES["plan_digest"], payload)
        self.assertNotIn(FIXTURES["snapshot_digest"], payload)
        self.assertIn(receipt["envelope_digest"], payload)  # the control: this search does find a digest
