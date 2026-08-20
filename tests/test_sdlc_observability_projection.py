"""Tests for the read-only observability projection (slice 6's exit artifact).

Fixtures for three of the four artifact kinds are built by RUNNING the real sibling tool that emits
them (`wave-journal.py`, `runtime-assignment.py`, `gate_receipt.py`, `gate_baseline.py`,
`activation-result.py`) in a scratch directory, never by hand-writing a guess of their format. The
two exceptions are named at their use: `ActivationResultPresentTests`'s write-ready and
remediation-ready fixtures are HAND-WRITTEN, because assembling activation-result.py's own full
five-artifact upstream chain (a classification result, a contract write result, an activation plan,
an activation apply result, and a matching gate receipt/baseline, each itself the output of a
further multi-artifact chain) is out of this ticket's bounded scope; activation-result.py's own
document carries no digest, so a hand-written one is not forging anything sealed.

The EIGHT SEALED SLICE-6 KINDS are likewise built by running the real producers, as one chain in a
module-scoped temp directory: `mission-contract.py define`, `planning-snapshot.py capture` over a
really-initialised git repository, `wave-plan-compiler.py compile` (which seals the wave plan AND its
plan diff in one run), `wave-plan-admission.py admit` against a freshly captured snapshot,
`drift-classifier.py classify`, `auto-envelope.py define`, and `auto-envelope.py admit-transition`.
Every document is bound to the one before it by the digest that producer derived, so a fixture cannot
be a plausible-looking guess: the chain would refuse.

Two things are deliberately NOT produced by a tool, each stated at its use. `SealedInjectionTests`
RE-SEALS a real document after poisoning one field with a bare control character, because every
producer in this family validates its input and none of them will seal a forged line for us; the
re-seal uses this module's own `seal`, which is the same three lines the producers use, so the
document is genuinely sealed rather than merely claimed to be. `ActivationResultTests`'s write-ready
and remediation-ready fixtures stay hand-written for the bounded-scope reason stated above.

Every subprocess spawn in this module -- for the tool under test AND for every sibling fixture
producer -- goes through ONE constructed environment: an ALLOWLIST, not the ambient shell, mirroring
`test_mission_contract.py`'s `constructed_environment` (itself the same pattern
`test_wave_journal.py` establishes: never hand a spawned tool the developer's own shell).
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "sdlc-observability-projection.py"
WAVE_JOURNAL_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-journal.py"
RUNTIME_ASSIGNMENT_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "runtime-assignment.py"
ACTIVATION_RESULT_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "activation-result.py"
GATE_RECEIPT_TOOL = ROOT / "scripts" / "gate_receipt.py"
GATE_BASELINE_TOOL = ROOT / "scripts" / "gate_baseline.py"
MISSION_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "mission-contract.py"
SNAPSHOT_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "planning-snapshot.py"
COMPILER_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-plan-compiler.py"
ADMISSION_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-plan-admission.py"
DRIFT_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "drift-classifier.py"
ENVELOPE_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "auto-envelope.py"
MISE_LOCK = ROOT / "mise.lock"

RESULT_SCHEMA = "agentic-sdlc/observability-projection@2"
EVIDENCE_NOTICE = "this view is evidence, not authorization"

#: The `@1` consumer surface, frozen here so a later edit cannot quietly rename or drop one of these
#: while the schema string still claims a version that promised them. Additions are allowed at `@2`;
#: a removal or a rename is what this set exists to catch.
V1_TOP_LEVEL_KEYS = frozenset({"schema", "command", "status", "exit_code", "evidence_notice", "bluf", "artifacts"})
V1_ARTIFACT_KINDS = ("wave_journal", "runtime_assignment", "activation_result", "gate")

#: The eight sealed slice-6 document kinds, each `(artifacts key, flag, declared schema, label)`. The
#: label is the exact name the tool uses for the kind in every refusal and section heading, which is
#: what "unreadable BY NAME" means for a per-input outcome.
SEALED_KINDS: tuple[tuple[str, str, str, str], ...] = (
    ("mission_contract", "--mission-contract", "agentic-sdlc/mission-contract@1", "mission contract"),
    ("planning_snapshot", "--planning-snapshot", "agentic-sdlc/planning-snapshot@1", "planning snapshot"),
    ("wave_plan", "--wave-plan", "agentic-sdlc/wave-plan@1", "wave plan"),
    ("plan_diff", "--plan-diff", "agentic-sdlc/plan-diff@1", "plan diff"),
    (
        "wave_plan_admission",
        "--wave-plan-admission",
        "agentic-sdlc/wave-plan-admission@1",
        "wave plan admission report",
    ),
    ("drift_classification", "--drift-classification", "agentic-sdlc/drift-classification@1", "drift classification"),
    ("auto_envelope", "--auto-envelope", "agentic-sdlc/auto-envelope@1", "auto envelope"),
    (
        "transition_receipt",
        "--transition-receipt",
        "agentic-sdlc/autonomous-transition-receipt@1",
        "autonomous transition receipt",
    ),
)

#: Which fixture each sealed kind's flag is fed from, for the loop-shaped tests.
FIXTURE_FOR_KIND = {
    "mission_contract": "mission",
    "planning_snapshot": "compiled_snapshot",
    "wave_plan": "plan",
    "plan_diff": "diff",
    "wave_plan_admission": "admission",
    "drift_classification": "classification",
    "auto_envelope": "envelope",
    "transition_receipt": "receipt",
}

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

ABSENT = "absent"
UNREADABLE = "unreadable"
PRESENT = "present"

#: The allowlist every spawn in this module constructs its environment from -- mirroring
#: `test_mission_contract.py`'s `PASSTHROUGH_ENV`/`constructed_environment` exactly, because this
#: module also spawns wave-journal.py, runtime-assignment.py, activation-result.py, gate_receipt.py,
#: and gate_baseline.py as fixture producers, and every one of THOSE spawns must be constructed too.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def constructed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    environment = {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}
    if extra:
        environment.update(extra)
    return environment


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def run(argv: list[str], *, cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv, capture_output=True, cwd=str(cwd), check=False, env=constructed_environment(extra_env)
    )


def run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Mirrors `test_mission_contract.py`'s helper of the same name and the same two hostile shapes."""
    if mode == "closed":
        done = subprocess.run(
            ["sh", "-c", 'exec 2>&-; exec "$@"', "sh", *argv],
            stdout=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
            env=constructed_environment(),
        )
        return done.returncode, done.stdout
    assert mode == "epipe"
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd), env=constructed_environment())
    finally:
        os.close(write_fd)
    assert child.stdout is not None
    with child.stdout as stream:
        out = stream.read()
    return child.wait(), out


def run_with_hostile_stdout(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    if mode == "closed":
        done = subprocess.run(
            ["sh", "-c", 'exec 1>&-; exec "$@"', "sh", *argv],
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
            env=constructed_environment(),
        )
        return done.returncode, done.stderr
    assert mode == "epipe"
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    try:
        child = subprocess.Popen(argv, stdout=write_fd, stderr=subprocess.PIPE, cwd=str(cwd), env=constructed_environment())
    finally:
        os.close(write_fd)
    assert child.stderr is not None
    with child.stderr as stream:
        err = stream.read()
    return child.wait(), err


def imports_and_calls(path: Path) -> tuple[set[str], set[str]]:
    """Re-expressed from `test_mission_contract.py`'s helper of the same name: read with `ast`, not a
    substring search, because this module's own docstring contains prose like "never imported"."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return modules, calls


def sealed_digest(document: dict[str, Any]) -> str:
    """The family's ONE sealed-document derivation, re-expressed here for the same reason the tool
    re-expresses it: sha256 over the canonical bytes of the document minus `digest`, excluded BY NAME.
    """
    return hashlib.sha256(canonical({key: value for key, value in document.items() if key != "digest"})).hexdigest()


def seal(document: dict[str, Any]) -> dict[str, Any]:
    """Re-seal a document a test has edited, so the tool sees a genuinely sealed document rather than
    one whose digest is stale. Used ONLY where a real producer refuses to seal what a test needs."""
    resealed = dict(document)
    resealed["digest"] = sealed_digest(document)
    return resealed


# ---- the sealed slice-6 chain, built ONCE by running the real producers --------------------------

FIXTURES: dict[str, Path] = {}
_SCRATCH: tempfile.TemporaryDirectory[str] | None = None

NO_GIT = "a real git is required to capture a real PlanningSnapshot and compile a real WavePlan"
GIT_ENVIRONMENT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

MISSION_ID = "mission-slice-6"
AT_MISSION = "2026-08-20T03:00:00Z"
AT_COMPILE_SNAPSHOT = "2026-08-20T03:30:00Z"
AT_SUBMISSIONS = "2026-08-20T03:45:00Z"
AT_COMPILE = "2026-08-20T04:00:00Z"
AT_FRESH = "2026-08-20T04:30:00Z"
AT_ADMIT = "2026-08-20T04:35:00Z"
AT_DIRTY = "2026-08-20T04:40:00Z"
AT_BLOCKED = "2026-08-20T04:45:00Z"
AT_OBSERVED = "2026-08-20T05:00:00Z"
AT_CLASSIFY = "2026-08-20T05:05:00Z"
AT_ENVELOPE = "2026-08-20T06:00:00Z"
AT_NOT_BEFORE = "2026-08-20T06:30:00Z"
AT_NOT_AFTER = "2026-08-20T09:00:00Z"
AT_TRANSITION = "2026-08-20T06:45:00Z"
AT_ADMIT_TRANSITION = "2026-08-20T07:00:00Z"


def _producer(argv: list[str], scratch: Path, expected: str, label: str) -> dict[str, Any]:
    """Run one real producer and demand its OWN success verdict. A failure here is raised, never
    skipped: a sibling that cannot seal a valid input is a real regression, and swallowing it would
    silently delete this module's coverage of that kind."""
    done = run([sys.executable, "-B", *argv], cwd=scratch)
    if done.returncode != EXIT_OK:
        raise AssertionError(f"{label} failed: exit {done.returncode} {done.stderr!r}")
    result = json.loads(done.stdout.decode("utf-8"))
    if result["verdict"] != expected:
        raise AssertionError(f"{label} refused a valid input: {result.get('reasons')}")
    return result


def _git(repository: Path, *args: str) -> None:
    step = run(["git", *args], cwd=repository, extra_env=GIT_ENVIRONMENT)
    if step.returncode != 0:
        raise AssertionError(f"git {args} in {repository} failed: {step.stderr!r}")


def _mission_body() -> dict[str, Any]:
    return {
        "schema": "agentic-sdlc/mission-contract@1",
        "mission_id": MISSION_ID,
        "objective": "project the eight sealed slice-6 artifact kinds in one read-only observability view",
        "scope": {
            "in_scope": ["skills/agentic-sdlc/tools/sdlc-observability-projection.py"],
            "non_goals": ["the wave submission schemas"],
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
        "stop_conditions": sorted(
            (
                "authority-expansion-required",
                "hard-stop-drift",
                "scope-change-required",
                "unknown-or-partial-effect",
            )
        ),
        "stated_at": AT_MISSION,
        "revision": 1,
        "supersedes": None,
    }


def _submissions_body() -> dict[str, Any]:
    return {
        "schema": "agentic-sdlc/workstream-submissions@1",
        "submission_id": "submissions-slice-6-t4",
        "mission_id": MISSION_ID,
        "stated_at": AT_SUBMISSIONS,
        "declared_concurrency": 2,
        "workstreams": [
            {
                "id": "ws-a-cartography",
                "objective": "map the eight sealed slice-6 document kinds and their digests",
                "authority_class": "read-only-advisory",
                "capability_demands": ["repository-read"],
                "dependencies": [],
                "file_custody": [],
                "worktree_custody": None,
            },
            {
                "id": "ws-b-projection",
                "objective": "extend the observability projection over those eight kinds",
                "authority_class": "owned-worktree-write",
                "capability_demands": ["git-worktree-write", "python-execution"],
                "dependencies": ["ws-a-cartography"],
                "file_custody": ["skills/agentic-sdlc/tools/sdlc-observability-projection.py"],
                "worktree_custody": ".worktrees/projection",
            },
        ],
    }


def _envelope_body(plan_digest: str, plan_revision: int, snapshot_digest: str) -> dict[str, Any]:
    return {
        "schema": "agentic-sdlc/auto-envelope@1",
        "envelope_id": "auto-slice-6-t4",
        "stated_at": AT_ENVELOPE,
        "bound_plan": {
            "plan_digest": plan_digest,
            "plan_revision": plan_revision,
            "snapshot_digest": snapshot_digest,
        },
        "allowed_authority_classes": ["read-only-advisory", "owned-worktree-write"],
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
        "validity_window": {"not_after": AT_NOT_AFTER, "not_before": AT_NOT_BEFORE},
        "checkpoints": [
            {"kind": "authority-inheritance", "requires_human_disposition": False},
            {"kind": "budget-remaining", "requires_human_disposition": False},
            {"kind": "drift-recheck", "requires_human_disposition": True},
            {"kind": "evidence-recheck", "requires_human_disposition": False},
        ],
        "stop_rules": [
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
        ],
    }


def _transition_body(envelope: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "schema": "agentic-sdlc/autonomous-transition@1",
        "transition_id": f"transition-slice-6-t4-{kind}",
        "stated_at": AT_TRANSITION,
        "bound_envelope": {"envelope_digest": envelope["digest"], "envelope_id": envelope["envelope_id"]},
        "kind": kind,
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


def setUpModule() -> None:
    """Build the whole sealed chain ONCE. The order is the chain's own order, and each link is bound
    to the previous one by the digest its producer derived, so nothing here is a hand-written guess."""
    global _SCRATCH
    _SCRATCH = tempfile.TemporaryDirectory(prefix="observability-projection-fixtures-")
    scratch = Path(_SCRATCH.name).resolve()

    body = scratch / "mission-body.json"
    body.write_text(json.dumps(_mission_body(), indent=2), encoding="utf-8")
    result = _producer(
        [str(MISSION_TOOL), "define", "--contract", str(body)], scratch, "defined", "mission-contract.py define"
    )
    mission = scratch / "mission.json"
    mission.write_bytes(canonical(result["contract"]))
    FIXTURES["mission"] = mission

    if shutil.which("git") is None:
        return
    repository = scratch / "repo"
    repository.mkdir()
    (repository / "tracked.txt").write_text("one\n", encoding="utf-8")
    (repository / ".gitignore").write_text(".worktrees/\n.sdlc/\n", encoding="utf-8")
    _git(repository, "init", "--quiet", "-b", "trunk", ".")
    _git(repository, "add", "tracked.txt", ".gitignore")
    _git(
        repository, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "--quiet", "-m", "one"
    )

    compiled_snapshot = scratch / "compiled-snapshot.json"
    snapshot = _producer(
        [str(SNAPSHOT_TOOL), "capture", "--repository", str(repository), "--at", AT_COMPILE_SNAPSHOT,
         "--out", str(compiled_snapshot)],
        scratch, "captured", "planning-snapshot.py capture (compiled)",
    )
    FIXTURES["compiled_snapshot"] = compiled_snapshot

    submissions = scratch / "submissions.json"
    submissions.write_bytes(canonical(seal(_submissions_body())))
    plan, diff = scratch / "plan.json", scratch / "diff.json"
    compiled = _producer(
        [str(COMPILER_TOOL), "compile", "--mission", str(mission), "--snapshot", str(compiled_snapshot),
         "--submissions", str(submissions), "--at", AT_COMPILE, "--out", str(plan), "--diff-out", str(diff)],
        scratch, "compiled", "wave-plan-compiler.py compile",
    )
    FIXTURES["plan"] = plan
    FIXTURES["diff"] = diff

    fresh_snapshot = scratch / "fresh-snapshot.json"
    _producer(
        [str(SNAPSHOT_TOOL), "capture", "--repository", str(repository), "--at", AT_FRESH,
         "--out", str(fresh_snapshot)],
        scratch, "captured", "planning-snapshot.py capture (fresh)",
    )
    FIXTURES["fresh_snapshot"] = fresh_snapshot

    admission = scratch / "admission.json"
    _producer(
        [str(ADMISSION_TOOL), "admit", "--plan", str(plan), "--fresh-snapshot", str(fresh_snapshot),
         "--compiled-snapshot", str(compiled_snapshot), "--mission", str(mission), "--at", AT_ADMIT,
         "--out", str(admission)],
        scratch, "admitted", "wave-plan-admission.py admit",
    )
    FIXTURES["admission"] = admission

    # A really-dirty tree, so the BLOCKED report is the admission tool's own answer rather than a
    # hand-edited `disposition` -- the projection must carry a "no" as faithfully as a "yes".
    untracked = repository / "someone-elses-work.txt"
    untracked.write_text("uncommitted\n", encoding="utf-8")
    dirty_snapshot = scratch / "dirty-snapshot.json"
    _producer(
        [str(SNAPSHOT_TOOL), "capture", "--repository", str(repository), "--at", AT_DIRTY,
         "--out", str(dirty_snapshot)],
        scratch, "captured", "planning-snapshot.py capture (dirty)",
    )
    untracked.unlink()
    blocked = scratch / "admission-blocked.json"
    # `refused` is the RESULT's verdict for an admissible input set whose sealed report says `blocked`
    # -- the tool's own two-level vocabulary, not a typo: `inputs_admitted` is true and the report is
    # written, and it is the report's `disposition` this module projects.
    _producer(
        [str(ADMISSION_TOOL), "admit", "--plan", str(plan), "--fresh-snapshot", str(dirty_snapshot),
         "--compiled-snapshot", str(compiled_snapshot), "--mission", str(mission), "--at", AT_BLOCKED,
         "--out", str(blocked)],
        scratch, "refused", "wave-plan-admission.py admit (dirty)",
    )
    FIXTURES["admission_blocked"] = blocked

    plan_digest = compiled["plan_digest"]
    observed = scratch / "observed.json"
    observed.write_bytes(canonical(seal({
        "schema": "agentic-sdlc/observed-drift@1",
        "observation_id": "obs-slice-6-t4",
        "observed_at": AT_OBSERVED,
        "plan_digest": plan_digest,
        "changes": [{"kind": "retry", "subject": "ws-b-projection",
                     "observation": "a fresh bounded observation found one node retried once"}],
    })))
    classification = scratch / "classification.json"
    _producer(
        [str(DRIFT_TOOL), "classify", "--plan", str(plan), "--observed", str(observed), "--at", AT_CLASSIFY,
         "--out", str(classification)],
        scratch, "classified", "drift-classifier.py classify",
    )
    FIXTURES["classification"] = classification

    # An EMPTY observation. `drift-classifier.py` answers `no-drift` and seals a null `overall_outcome`
    # beside a `no_drift_reason`, because "nothing was observed" is not the verdict `compatible`.
    quiet = scratch / "observed-empty.json"
    quiet.write_bytes(canonical(seal({
        "schema": "agentic-sdlc/observed-drift@1",
        "observation_id": "obs-slice-6-t4-quiet",
        "observed_at": AT_OBSERVED,
        "plan_digest": plan_digest,
        "changes": [],
    })))
    no_drift = scratch / "classification-no-drift.json"
    _producer(
        [str(DRIFT_TOOL), "classify", "--plan", str(plan), "--observed", str(quiet), "--at", AT_CLASSIFY,
         "--out", str(no_drift)],
        scratch, "no-drift", "drift-classifier.py classify (no drift)",
    )
    FIXTURES["classification_no_drift"] = no_drift

    # A SECOND real outcome, so "the projection reports the document's own outcome" is checked against
    # two different values rather than one. `compatible` is deliberately not among the choices: it is
    # representable in the schema and unreachable from that tool's taxonomy table, so no real
    # classification carries it and a fixture claiming one would be a forgery.
    approval = scratch / "observed-approval.json"
    approval.write_bytes(canonical(seal({
        "schema": "agentic-sdlc/observed-drift@1",
        "observation_id": "obs-slice-6-t4-approval",
        "observed_at": AT_OBSERVED,
        "plan_digest": plan_digest,
        "changes": [{"kind": "approval", "subject": "ws-b-projection",
                     "observation": "a fresh bounded observation found this node's approval no longer current"}],
    })))
    revalidation = scratch / "classification-revalidation.json"
    _producer(
        [str(DRIFT_TOOL), "classify", "--plan", str(plan), "--observed", str(approval), "--at", AT_CLASSIFY,
         "--out", str(revalidation)],
        scratch, "classified", "drift-classifier.py classify (approval)",
    )
    FIXTURES["classification_revalidation"] = revalidation

    envelope_body = scratch / "envelope-body.json"
    envelope_body.write_bytes(canonical(_envelope_body(plan_digest, 1, snapshot["digest"])))
    defined = _producer(
        [str(ENVELOPE_TOOL), "define", "--body", str(envelope_body)], scratch, "defined", "auto-envelope.py define"
    )
    envelope = scratch / "envelope.json"
    envelope.write_bytes(canonical(defined["envelope"]))
    FIXTURES["envelope"] = envelope

    for name, kind, verdict in (
        ("receipt", "added-node", "admitted"),
        ("receipt_refused", "removed-node", "refused"),
    ):
        transition = scratch / f"{name}-transition.json"
        transition.write_bytes(canonical(_transition_body(defined["envelope"], kind)))
        target = scratch / f"{name}.json"
        _producer(
            [str(ENVELOPE_TOOL), "admit-transition", "--envelope", str(envelope), "--transition", str(transition),
             "--at", AT_ADMIT_TRANSITION, "--out", str(target)],
            scratch, verdict, f"auto-envelope.py admit-transition ({kind})",
        )
        FIXTURES[name] = target


def tearDownModule() -> None:
    if _SCRATCH is not None:
        _SCRATCH.cleanup()


class ProjectionCase(unittest.TestCase):
    """Every fixture is built by running the real sibling producer in `self.work`."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = Path(self._tmp.name).resolve()

    # ---- the tool under test ------------------------------------------------------------------

    def run_tool(self, *argv: str) -> subprocess.CompletedProcess[bytes]:
        return run([sys.executable, "-B", str(TOOL), *argv], cwd=self.work)

    def human(self, *argv: str) -> str:
        done = self.run_tool(*argv)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        return done.stdout.decode("utf-8")

    def document(self, *argv: str) -> dict[str, Any]:
        done = self.run_tool(*argv, "--json")
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        return json.loads(done.stdout)

    # ---- wave-journal fixtures, built by running wave-journal.py --------------------------------

    def make_wave_journal(self, *, name: str = "journal.ndjson", complete: bool) -> Path:
        journal = self.work / name
        header = {
            "wave_id": "wave-1",
            "mission_id": "mission-slice-6",
            "mode": "static-dag",
            "plan_digest": "a" * 64,
            "approval": "operator approved the wave graph at review",
            "required_nodes": ["implement-a", "implement-b"],
            "limits": {"max_concurrent_nodes": 2, "max_nodes": 8, "max_recursive_generations": 0},
        }
        header_path = self.work / f"{name}.header.json"
        header_path.write_text(json.dumps(header), encoding="utf-8")
        done = run(
            [sys.executable, "-B", str(WAVE_JOURNAL_TOOL), "init", "--journal", str(journal), "--at",
             "2026-08-20T00:00:00Z", "--record", f"@{header_path}"],
            cwd=self.work,
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self._record_node(journal, "implement-a", "2026-08-20T00:05:00Z")
        if complete:
            self._record_node(journal, "implement-b", "2026-08-20T00:09:00Z")
        return journal

    def _record_node(self, journal: Path, node_id: str, at: str) -> None:
        record = {
            "node_id": node_id,
            "role": "implementer",
            "disposition": "admitted-success",
            "inputs": ["plan/wave-1.json"],
            "outputs": [f"worktrees/{node_id}/diff"],
            "assignment": {
                "provider": "anthropic", "model_id": "claude-sonnet-5", "effort": "high", "context": "base",
                "resolution_state": "resolved",
            },
            "started_at": "2026-08-20T00:01:00Z",
            "ended_at": at,
            "evidence": ["gate receipt 9f"],
            "attempt": 1,
            "reasons": [],
            "approval": None,
        }
        record_path = self.work / f"{node_id}.node.json"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        done = run(
            [sys.executable, "-B", str(WAVE_JOURNAL_TOOL), "record-node", "--journal", str(journal), "--at", at,
             "--record", f"@{record_path}"],
            cwd=self.work,
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))

    # ---- runtime-assignment fixtures, built by running runtime-assignment.py --------------------

    def make_classification(self, *, name: str = "classify.json", served_model: str = "claude-sonnet-5") -> Path:
        served = {
            "schema": "agentic-sdlc/runtime-served-record@1",
            "node": "implementer-a",
            "requested": {"model_id": "claude-sonnet-5", "effort": "high", "context_form": "base"},
            "served": {
                "identity_status": "verified",
                "identity_source": "adapter_response_readback",
                "identity_basis": "independent_readback",
                "request_injection_status": "verified",
                "provider": "anthropic",
                "model_id": served_model,
                "effort_readback_status": "unavailable",
                "context_readback_status": "unavailable",
            },
        }
        served_path = self.work / f"{name}.served.json"
        served_path.write_text(json.dumps(served), encoding="utf-8")
        out = self.work / name
        done = run(
            [sys.executable, "-B", str(RUNTIME_ASSIGNMENT_TOOL), "classify", "--served", str(served_path)],
            cwd=self.work,
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        out.write_bytes(done.stdout)
        return out

    def make_admission(self, *, name: str = "admit.json") -> Path:
        request = {
            "schema": "agentic-sdlc/runtime-admission-request@1",
            "node": "implementer-a",
            "requested_tier": "capable-volume",
            "host_injection": {
                "host": "claude-code", "surface": "workflow_agent_call", "injects_model": True, "injects_effort": True,
            },
            "assignment": {
                "schema_version": "runtime-assignment-receipt/v1",
                "provider": "anthropic",
                "model_id": "claude-sonnet-5",
                "effort": "high",
                "context": "base",
                "resolution_state": "resolved",
            },
        }
        request_path = self.work / f"{name}.request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        out = self.work / name
        done = run(
            [sys.executable, "-B", str(RUNTIME_ASSIGNMENT_TOOL), "admit", "--request", str(request_path)],
            cwd=self.work,
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        out.write_bytes(done.stdout)
        return out

    # ---- gate receipt / baseline fixtures, built by running gate_receipt.py / gate_baseline.py ---

    def make_gate_receipt(
        self, *, name: str, gate: str, script: str, harness_unittest: bool = False
    ) -> Path:
        out = self.work / name
        script_path = self.work / f"{name}.script.py"
        script_path.write_text(script, encoding="utf-8")
        argv = [
            sys.executable, "-B", str(GATE_RECEIPT_TOOL), "record", "--gate", gate, "--out", str(out),
            "--lock", str(MISE_LOCK),
        ]
        if harness_unittest:
            argv += ["--harness", "unittest"]
        argv += ["--", sys.executable, "-B", str(script_path)]
        done = run(argv, cwd=self.work)
        self.assertIn(done.returncode, (0, 5, 6), done.stderr.decode("utf-8", "replace"))
        return out

    def make_gate_baseline(self, *, name: str, baseline: Path, candidate: Path) -> Path:
        out = self.work / name
        done = run(
            [sys.executable, "-B", str(GATE_BASELINE_TOOL), "compare", "--baseline", str(baseline),
             "--candidate", str(candidate), "--quiet"],
            cwd=self.work,
        )
        self.assertIn(done.returncode, (0, 5), done.stderr.decode("utf-8", "replace"))
        out.write_bytes(done.stdout)
        return out

    # ---- activation-result fixture, built by running activation-result.py -----------------------

    def make_activation_refused(self, *, name: str = "activation.json", gate_receipt: Path | None = None) -> Path:
        out = self.work / name
        argv = [sys.executable, "-B", str(ACTIVATION_RESULT_TOOL), "derive"]
        if gate_receipt is not None:
            argv += ["--gate-receipt", str(gate_receipt)]
        done = run(argv, cwd=self.work)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        out.write_bytes(done.stdout)
        return out


PASSING_SCRIPT = "import sys\nsys.exit(0)\n"
FAILING_UNITTEST_SCRIPT = (
    "import sys\n"
    "print('FAILED (failures=1)')\n"
    "print('=' * 70)\n"
    "print('FAIL: test_one (mypkg.test_mod.MyCase)')\n"
    "sys.exit(1)\n"
)
FAILING_UNITTEST_SCRIPT_TWO = (
    "import sys\n"
    "print('FAILED (failures=2)')\n"
    "print('=' * 70)\n"
    "print('FAIL: test_one (mypkg.test_mod.MyCase)')\n"
    "print('=' * 70)\n"
    "print('FAIL: test_two (mypkg.test_mod.MyCase)')\n"
    "sys.exit(1)\n"
)


class AbsenceTests(ProjectionCase):
    """No path supplied at all: every kind is absent by name, and the projection still succeeds."""

    def test_no_arguments_reports_every_kind_absent_and_succeeds(self) -> None:
        document = self.document()
        self.assertEqual(document["schema"], RESULT_SCHEMA)
        self.assertEqual(document["exit_code"], EXIT_OK)
        artifacts = document["artifacts"]
        self.assertEqual(artifacts["wave_journal"]["presence"], ABSENT)
        self.assertEqual(artifacts["runtime_assignment"]["presence"], ABSENT)
        self.assertEqual(artifacts["activation_result"]["presence"], ABSENT)
        self.assertEqual(artifacts["gate"]["receipt"]["presence"], ABSENT)
        self.assertEqual(artifacts["gate"]["baseline"]["presence"], ABSENT)
        self.assertIsNone(artifacts["gate"]["cross_check"])
        self.assertEqual(document["bluf"], "no observability artifact was supplied: nothing to project")

    def test_an_absent_path_is_named_absent_not_unreadable(self) -> None:
        missing = str(self.work / "does-not-exist.ndjson")
        document = self.document("--wave-journal", missing)
        section = document["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], ABSENT)
        self.assertEqual(section["path"], missing)
        self.assertIsNone(section["reason"])

    def test_the_evidence_notice_is_verbatim_in_both_views_even_with_no_inputs(self) -> None:
        self.assertIn(EVIDENCE_NOTICE, self.human())
        self.assertEqual(self.document()["evidence_notice"], EVIDENCE_NOTICE)


class WaveJournalTests(ProjectionCase):
    def test_a_complete_wave_journal_is_projected_and_reported_complete(self) -> None:
        journal = self.make_wave_journal(complete=True)
        document = self.document("--wave-journal", str(journal))
        section = document["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["wave_id"], "wave-1")
        self.assertTrue(section["complete"])
        self.assertEqual(section["required_nodes_without_disposition"], [])
        self.assertEqual(document["bluf"], "wave wave-1: every required node carries a disposition")

    def test_an_incomplete_wave_journal_names_the_missing_node(self) -> None:
        journal = self.make_wave_journal(complete=False)
        document = self.document("--wave-journal", str(journal))
        section = document["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertFalse(section["complete"])
        self.assertEqual(section["required_nodes_without_disposition"], ["implement-b"])
        self.assertIn("implement-b", document["bluf"])
        self.assertIn("1 required node(s) missing a disposition", document["bluf"])

    def test_a_directory_supplied_as_the_wave_journal_is_unreadable(self) -> None:
        # POSITIVE CONTROL: a real journal at a sibling path projects fine.
        journal = self.make_wave_journal(complete=True)
        self.assertEqual(self.document("--wave-journal", str(journal))["artifacts"]["wave_journal"]["presence"], PRESENT)
        adir = self.work / "adir"
        adir.mkdir()
        section = self.document("--wave-journal", str(adir))["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not a regular file", section["reason"])

    def test_a_journal_that_is_not_json_lines_is_unreadable_not_a_crash(self) -> None:
        journal = self.make_wave_journal(complete=True)
        # POSITIVE CONTROL: the untouched journal projects fine.
        self.assertEqual(self.document("--wave-journal", str(journal))["artifacts"]["wave_journal"]["presence"], PRESENT)
        journal.write_bytes(b"not a journal at all\n")
        document = self.document("--wave-journal", str(journal))
        section = document["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not valid JSON", section["reason"])
        self.assertIn("unreadable", document["bluf"])
        self.assertEqual(document["exit_code"], EXIT_OK)

    def test_an_absent_journal_path_is_absent_without_invoking_the_sibling(self) -> None:
        missing = self.work / "no-such-journal.ndjson"
        section = self.document("--wave-journal", str(missing))["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], ABSENT)
        self.assertIsNone(section["reason"])

    def test_wave_journal_json_and_human_views_agree(self) -> None:
        journal = self.make_wave_journal(complete=False)
        document = self.document("--wave-journal", str(journal))
        text = self.human("--wave-journal", str(journal))
        self.assertIn(document["bluf"], text)
        self.assertIn("implement-b", text)


class RuntimeAssignmentTests(ProjectionCase):
    def test_an_exact_match_classification_is_projected(self) -> None:
        report = self.make_classification(served_model="claude-sonnet-5")
        document = self.document("--runtime-assignment", str(report))
        section = document["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["command"], "classify")
        self.assertEqual(section["verdict"], "exact-match")
        self.assertFalse(section["blocks_wave_completion"])
        self.assertIsNone(section["may_spawn"])
        self.assertIn("exact-match", document["bluf"])

    def test_an_unexplained_substitution_classification_is_projected_and_blocks(self) -> None:
        report = self.make_classification(served_model="claude-opus-4-8")
        document = self.document("--runtime-assignment", str(report))
        section = document["artifacts"]["runtime_assignment"]
        self.assertEqual(section["verdict"], "unexplained-substitution")
        self.assertTrue(section["blocks_wave_completion"])
        self.assertIn("blocks wave completion", document["bluf"])

    def test_an_admission_report_is_projected_on_the_admit_branch(self) -> None:
        report = self.make_admission()
        document = self.document("--runtime-assignment", str(report))
        section = document["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["command"], "admit")
        self.assertEqual(section["verdict"], "refuse-dispatch")
        self.assertFalse(section["may_spawn"])
        self.assertIsNone(section["blocks_wave_completion"])

    def test_a_wrong_schema_report_is_unreadable(self) -> None:
        report = self.make_classification()
        # POSITIVE CONTROL: the untouched report is present.
        self.assertEqual(
            self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]["presence"], PRESENT
        )
        doc = json.loads(report.read_text(encoding="utf-8"))
        doc["schema"] = "agentic-sdlc/something-else@1"
        report.write_text(json.dumps(doc), encoding="utf-8")
        section = self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("something-else", section["reason"])

    def test_a_report_with_no_verdict_is_unreadable(self) -> None:
        report = self.make_classification()
        doc = json.loads(report.read_text(encoding="utf-8"))
        del doc["verdict"]
        report.write_text(json.dumps(doc), encoding="utf-8")
        section = self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("carries no verdict", section["reason"])


class ActivationResultTests(ProjectionCase):
    def test_a_real_refused_activation_result_is_projected(self) -> None:
        activation = self.make_activation_refused()
        document = self.document("--activation-result", str(activation))
        section = document["artifacts"]["activation_result"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["state"], "refused")
        self.assertTrue(section["reasons"])
        self.assertIn("activation state: refused", document["bluf"])

    def test_a_refused_activation_result_paired_with_a_passing_gate_still_refuses(self) -> None:
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        activation = self.make_activation_refused(gate_receipt=receipt)
        section = self.document("--activation-result", str(activation))["artifacts"]["activation_result"]
        self.assertEqual(section["state"], "refused")
        self.assertEqual(section["gate_outcome"], "passed")
        self.assertTrue(section["gate_passes"])

    def test_a_hand_written_write_ready_activation_result_is_projected(self) -> None:
        """HAND-WRITTEN: activation-result.py's write-ready state needs a full five-artifact upstream
        chain (classification, contract, plan, activation, matching gate) that is out of this
        ticket's bounded scope; the document carries no digest, so nothing sealed is forged here."""
        document = {
            "schema": "agentic-sdlc/activation-terminal-state@1",
            "command": "derive",
            "state": "write-ready",
            "exit_code": 0,
            "consequence": "normal waves may write",
            "classification": "greenfield",
            "gate_outcome": "passed",
            "gate_passes": True,
            "target": "/repo",
            "reasons": [],
            "recovery": {"admitted_effects": [], "activation_reasons": [], "recover_verbs": []},
            "evidence": {},
        }
        path = self.work / "write-ready.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        section = self.document("--activation-result", str(path))["artifacts"]["activation_result"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["state"], "write-ready")
        self.assertEqual(section["reasons"], [])
        bluf = self.document("--activation-result", str(path))["bluf"]
        self.assertIn("write-ready", bluf)
        self.assertIn("normal waves may write", bluf)

    def test_a_hand_written_remediation_ready_activation_result_is_projected(self) -> None:
        """HAND-WRITTEN for the same reason as write-ready, above."""
        document = {
            "schema": "agentic-sdlc/activation-terminal-state@1",
            "command": "derive",
            "state": "remediation-ready",
            "exit_code": 0,
            "consequence": "only named hygiene waves may write; this result never claims the repository gate passes",
            "classification": "brownfield",
            "gate_outcome": "failed",
            "gate_passes": False,
            "target": "/repo",
            "reasons": [],
            "recovery": {"admitted_effects": [], "activation_reasons": [], "recover_verbs": []},
            "evidence": {},
        }
        path = self.work / "remediation-ready.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        section = self.document("--activation-result", str(path))["artifacts"]["activation_result"]
        self.assertEqual(section["state"], "remediation-ready")
        self.assertFalse(section["gate_passes"])

    def test_an_unknown_state_is_unreadable(self) -> None:
        activation = self.make_activation_refused()
        doc = json.loads(activation.read_text(encoding="utf-8"))
        doc["state"] = "definitely-ready"
        activation.write_text(json.dumps(doc), encoding="utf-8")
        section = self.document("--activation-result", str(activation))["artifacts"]["activation_result"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("closed activation states", section["reason"])

    def test_never_manufacture_success_a_refused_activation_result_never_becomes_write_ready(self) -> None:
        """The load-bearing property, stated as a direct assertion: this module never upgrades one
        artifact's own verdict into a different one."""
        activation = self.make_activation_refused()
        section = self.document("--activation-result", str(activation))["artifacts"]["activation_result"]
        self.assertNotEqual(section["state"], "write-ready")
        self.assertEqual(section["state"], "refused")


class GateTests(ProjectionCase):
    def test_a_lone_passing_receipt_is_projected_with_no_baseline(self) -> None:
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        document = self.document("--gate-receipt", str(receipt))
        gate = document["artifacts"]["gate"]
        self.assertEqual(gate["receipt"]["presence"], PRESENT)
        self.assertEqual(gate["receipt"]["outcome"], "passed")
        self.assertEqual(gate["baseline"]["presence"], ABSENT)
        self.assertIsNone(gate["cross_check"])
        self.assertIn("outcome passed", document["bluf"])

    def test_a_non_worsening_pair_is_projected(self) -> None:
        baseline_receipt = self.make_gate_receipt(
            name="baseline.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        candidate_receipt = self.make_gate_receipt(
            name="candidate.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        comparison = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=candidate_receipt)
        document = self.document("--gate-receipt", str(candidate_receipt), "--gate-baseline", str(comparison))
        gate = document["artifacts"]["gate"]
        self.assertTrue(gate["baseline"]["non_worsening"])
        self.assertEqual(gate["baseline"]["newly_failing"], [])
        self.assertEqual(gate["cross_check"], {"same_gate": True})
        self.assertIn("non-worsening", document["bluf"])

    def test_a_worsened_pair_is_projected_and_named_worsened(self) -> None:
        baseline_receipt = self.make_gate_receipt(
            name="baseline.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        worse_receipt = self.make_gate_receipt(
            name="worse.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT_TWO, harness_unittest=True
        )
        comparison = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=worse_receipt)
        document = self.document("--gate-receipt", str(worse_receipt), "--gate-baseline", str(comparison))
        gate = document["artifacts"]["gate"]
        self.assertFalse(gate["baseline"]["non_worsening"])
        self.assertEqual(gate["baseline"]["newly_failing"], ["mypkg.test_mod.MyCase.test_two"])
        self.assertIn("WORSENED", document["bluf"])
        self.assertIn("1 newly failing", document["bluf"])

    def test_a_tampered_receipt_self_digest_is_unreadable(self) -> None:
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        # POSITIVE CONTROL: the untouched receipt is present and verifies.
        self.assertEqual(self.document("--gate-receipt", str(receipt))["artifacts"]["gate"]["receipt"]["presence"], PRESENT)
        doc = json.loads(receipt.read_text(encoding="utf-8"))
        doc["gate"] = "tampered gate label"
        receipt.write_text(json.dumps(doc), encoding="utf-8")
        section = self.document("--gate-receipt", str(receipt))["artifacts"]["gate"]["receipt"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("does not verify", section["reason"])
        self.assertIn("self_digest does not re-derive", section["reason"])

    @unittest.skipUnless(os.name == "posix", "os.mkfifo is POSIX-only")
    def test_a_fifo_supplied_as_a_gate_receipt_is_unreadable_and_does_not_hang(self) -> None:
        """The regular-file check must run BEFORE any read: opening a FIFO for reading blocks until a
        writer shows up, which here would be never, so a wrong-shape path must exit 2 promptly rather
        than hang this read-only query forever."""
        fifo = self.work / "fifo"
        os.mkfifo(fifo)
        done = self.run_tool("--gate-receipt", str(fifo), "--json")
        self.assertEqual(done.returncode, EXIT_OK)
        section = json.loads(done.stdout)["artifacts"]["gate"]["receipt"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not a regular file", section["reason"])

    def test_a_gate_receipt_missing_a_required_key_is_unreadable(self) -> None:
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        doc = json.loads(receipt.read_text(encoding="utf-8"))
        del doc["outcome"]
        receipt.write_text(json.dumps(doc), encoding="utf-8")
        section = self.document("--gate-receipt", str(receipt))["artifacts"]["gate"]["receipt"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("does not carry exactly a gate receipt's fields", section["reason"])

    def test_a_baseline_with_the_wrong_schema_version_is_unreadable(self) -> None:
        baseline_receipt = self.make_gate_receipt(
            name="baseline.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        candidate_receipt = self.make_gate_receipt(
            name="candidate.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        comparison = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=candidate_receipt)
        # POSITIVE CONTROL: the untouched comparison is present.
        self.assertEqual(
            self.document("--gate-baseline", str(comparison))["artifacts"]["gate"]["baseline"]["presence"], PRESENT
        )
        doc = json.loads(comparison.read_text(encoding="utf-8"))
        doc["schema_version"] = "gate-baseline-comparison/v2"
        comparison.write_text(json.dumps(doc), encoding="utf-8")
        section = self.document("--gate-baseline", str(comparison))["artifacts"]["gate"]["baseline"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("schema_version", section["reason"])

    def test_a_baseline_about_a_different_gate_fails_the_cross_check(self) -> None:
        smoke_receipt = self.make_gate_receipt(name="smoke.json", gate="smoke", script=PASSING_SCRIPT)
        baseline_receipt = self.make_gate_receipt(
            name="baseline.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        candidate_receipt = self.make_gate_receipt(
            name="candidate.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        comparison = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=candidate_receipt)
        # POSITIVE CONTROL: paired with its OWN candidate, the cross-check agrees.
        matched = self.document("--gate-receipt", str(candidate_receipt), "--gate-baseline", str(comparison))
        self.assertEqual(matched["artifacts"]["gate"]["cross_check"], {"same_gate": True})
        mismatched = self.document("--gate-receipt", str(smoke_receipt), "--gate-baseline", str(comparison))
        self.assertEqual(mismatched["artifacts"]["gate"]["cross_check"], {"same_gate": False})


FLAG_FOR_KIND = {kind: flag for kind, flag, _schema, _label in SEALED_KINDS}

#: Per kind, the projected fields the HUMAN view must actually render, so "the two views agree" is
#: checked against named fields rather than against whatever the renderer happens to emit.
HUMAN_FIELDS = {
    "mission_contract": ("mission_id", "objective", "authority_ceiling"),
    "planning_snapshot": ("stated_at", "commit_sha", "tree_sha", "queue_state"),
    "wave_plan": ("mission_id", "compiled_at", "mission_digest", "snapshot_digest"),
    "plan_diff": ("mission_id", "compiled_at", "plan_digest"),
    "wave_plan_admission": ("disposition", "admitted_at", "mission_id", "observed_commit_sha"),
    "drift_classification": ("overall_outcome", "classified_at", "plan_digest", "observation_id"),
    "auto_envelope": ("envelope_id", "stated_at", "not_before", "not_after", "egress_posture"),
    "transition_receipt": ("verdict", "at", "envelope_digest", "transition_digest"),
}


def escaped(value: str) -> str:
    """The exact form the tool's `_flat` produces for a string: `json.dumps` minus its quotes."""
    return json.dumps(value)[1:-1]


class SealedKindCase(ProjectionCase):
    """Shared helpers for the eight sealed slice-6 kinds, all read from the module-scoped chain."""

    def fixture(self, name: str) -> Path:
        path = FIXTURES.get(name)
        if path is None:
            self.skipTest(NO_GIT)
        return path

    def copy_of(self, name: str, *, as_name: str | None = None) -> Path:
        """A per-test COPY in `self.work`: a corruption test must never damage the shared chain."""
        source = self.fixture(name)
        target = self.work / (as_name or source.name)
        target.write_bytes(source.read_bytes())
        return target

    def read(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, path: Path, document: dict[str, Any]) -> Path:
        path.write_bytes(canonical(document))
        return path

    def project_kind(self, kind: str, path: Path) -> dict[str, Any]:
        return self.document(FLAG_FOR_KIND[kind], str(path))["artifacts"][kind]

    def every_flag(self) -> list[str]:
        argv: list[str] = []
        for kind, flag, _schema, _label in SEALED_KINDS:
            argv += [flag, str(self.fixture(FIXTURE_FOR_KIND[kind]))]
        return argv

    def section_text(self, text: str, label: str) -> str:
        """The human view's one section for `label`: from its heading to the next blank line."""
        lines = text.splitlines()
        start = lines.index(f"== {label} ==")
        end = next((index for index in range(start + 1, len(lines)) if not lines[index]), len(lines))
        return "\n".join(lines[start:end])


class SealedMissionContractTests(SealedKindCase):
    def test_the_sealed_mission_contract_is_projected_in_its_own_vocabulary(self) -> None:
        path = self.fixture("mission")
        document = self.read(path)
        section = self.project_kind("mission_contract", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["mission_id"], document["mission_id"])
        self.assertEqual(section["objective"], document["objective"])
        self.assertEqual(section["revision"], document["revision"])
        self.assertEqual(section["stated_at"], document["stated_at"])
        self.assertEqual(section["authority_ceiling"], document["authority"]["ceiling"])
        self.assertEqual(section["admitted_authority_classes"], document["authority"]["admitted_classes"])
        self.assertEqual(section["stop_conditions"], document["stop_conditions"])
        self.assertEqual(section["in_scope"], document["scope"]["in_scope"])
        self.assertIsNone(section["supersedes"])

    def test_a_contract_missing_its_authority_ceiling_is_unreadable_by_name(self) -> None:
        path = self.copy_of("mission")
        # POSITIVE CONTROL: the untouched copy projects.
        self.assertEqual(self.project_kind("mission_contract", path)["presence"], PRESENT)
        document = self.read(path)
        del document["authority"]["ceiling"]
        self.write(path, seal(document))
        section = self.project_kind("mission_contract", path)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("mission contract", section["reason"])
        self.assertIn("carries no authority.ceiling", section["reason"])


class SealedPlanningSnapshotTests(SealedKindCase):
    def test_the_sealed_planning_snapshot_is_projected(self) -> None:
        path = self.fixture("compiled_snapshot")
        document = self.read(path)
        section = self.project_kind("planning_snapshot", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["stated_at"], document["stated_at"])
        self.assertEqual(section["branch"], document["head"]["branch"])
        self.assertEqual(section["commit_sha"], document["head"]["commit_sha"])
        self.assertEqual(section["tree_sha"], document["head"]["tree_sha"])
        self.assertEqual(section["dirty_state"], document["dirty_state"])
        self.assertEqual(section["worktree_count"], len(document["worktrees"]))
        self.assertEqual(section["queue_state"], document["queue"]["state"])
        self.assertEqual(
            section["unknown_dimensions"], [entry["dimension"] for entry in document["unknowns"]]
        )

    def test_the_snapshots_own_named_unknowns_are_carried_rather_than_resolved(self) -> None:
        """A snapshot's `unknowns` are its honest statement that it did NOT observe a dimension. The
        projection must repeat them, never quietly drop them into a clean-looking summary."""
        section = self.project_kind("planning_snapshot", self.fixture("compiled_snapshot"))
        self.assertIn("activation_receipts", section["unknown_dimensions"])
        self.assertIn("route_and_rightsizing_evidence", section["unknown_dimensions"])


class SealedWavePlanTests(SealedKindCase):
    def test_the_sealed_wave_plan_is_projected(self) -> None:
        path = self.fixture("plan")
        document = self.read(path)
        section = self.project_kind("wave_plan", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["mission_id"], document["mission_id"])
        self.assertEqual(section["revision"], document["revision"])
        self.assertEqual(section["compiled_at"], document["compiled_at"])
        self.assertEqual(section["declared_concurrency"], document["declared_concurrency"])
        self.assertEqual(section["node_ids"], [node["node_id"] for node in document["nodes"]])
        self.assertEqual(section["edge_count"], len(document["edges"]))
        self.assertEqual(section["mission_digest"], document["inputs"]["mission_digest"])
        self.assertEqual(section["snapshot_digest"], document["inputs"]["snapshot_digest"])
        self.assertEqual(section["head_commit_sha"], document["head"]["commit_sha"])

    def test_the_plans_bound_mission_digest_is_the_digest_the_mission_fixture_carries(self) -> None:
        """The chain is real: the plan's `inputs.mission_digest` is the digest `mission-contract.py`
        derived for the very contract this module also projects."""
        plan = self.project_kind("wave_plan", self.fixture("plan"))
        self.assertEqual(plan["mission_digest"], self.read(self.fixture("mission"))["digest"])


class SealedPlanDiffTests(SealedKindCase):
    def test_the_first_plan_diff_is_projected_with_a_null_prior_plan_digest(self) -> None:
        path = self.fixture("diff")
        document = self.read(path)
        section = self.project_kind("plan_diff", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["plan_digest"], document["plan_digest"])
        self.assertIsNone(section["prior_plan_digest"])
        self.assertEqual(section["change_count"], len(document["changes"]))
        self.assertEqual(
            section["semantic_change_count"], sum(1 for change in document["changes"] if change["semantic"])
        )
        self.assertEqual(section["change_kinds"], sorted({change["kind"] for change in document["changes"]}))
        self.assertIsNone(section["no_delta_reason"])

    def test_the_diffs_plan_digest_is_the_digest_the_plan_fixture_carries(self) -> None:
        diff = self.project_kind("plan_diff", self.fixture("diff"))
        self.assertEqual(diff["plan_digest"], self.read(self.fixture("plan"))["digest"])


class SealedAdmissionReportTests(SealedKindCase):
    def test_the_admitted_report_is_projected_with_its_own_disposition(self) -> None:
        path = self.fixture("admission")
        document = self.read(path)
        section = self.project_kind("wave_plan_admission", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["disposition"], "admitted")
        self.assertEqual(section["admitted_at"], document["admitted_at"])
        self.assertEqual(section["plan_revision"], document["plan_revision"])
        self.assertEqual(section["plan_digest"], document["inputs"]["plan_digest"])
        self.assertEqual(section["checks_met"], [check["slug"] for check in document["checks"] if check["met"]])
        self.assertEqual(section["checks_not_met"], [])
        self.assertEqual(section["blockers"], [])
        self.assertEqual(
            section["deferred_dimensions"], [entry["dimension"] for entry in document["deferred_dimensions"]]
        )

    def test_the_blocked_report_is_projected_as_blocked_with_every_blocker_it_named(self) -> None:
        path = self.fixture("admission_blocked")
        document = self.read(path)
        section = self.project_kind("wave_plan_admission", path)
        self.assertEqual(section["disposition"], "blocked")
        self.assertEqual(section["checks_not_met"], [check["slug"] for check in document["checks"] if not check["met"]])
        self.assertTrue(section["blockers"])
        self.assertEqual(
            section["blockers"],
            [blocker for check in document["checks"] for blocker in check["blockers"]],
        )

    def test_never_manufacture_success_a_blocked_report_never_becomes_admitted(self) -> None:
        section = self.project_kind("wave_plan_admission", self.fixture("admission_blocked"))
        self.assertNotEqual(section["disposition"], "admitted")
        # POSITIVE CONTROL: the admitted fixture really does read `admitted`, so the assertion above
        # is discriminating rather than vacuous.
        self.assertEqual(self.project_kind("wave_plan_admission", self.fixture("admission"))["disposition"], "admitted")

    def test_a_disposition_outside_the_closed_set_is_unreadable_rather_than_projected(self) -> None:
        path = self.copy_of("admission")
        self.assertEqual(self.project_kind("wave_plan_admission", path)["presence"], PRESENT)
        document = self.read(path)
        document["disposition"] = "approved"
        self.write(path, seal(document))
        section = self.project_kind("wave_plan_admission", path)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("'approved'", section["reason"])
        self.assertIn("closed set", section["reason"])

    def test_the_admission_disposition_headlines_the_bluf(self) -> None:
        document = self.document(FLAG_FOR_KIND["wave_plan_admission"], str(self.fixture("admission_blocked")))
        self.assertIn("wave plan admission disposition: blocked", document["bluf"])


class SealedDriftClassificationTests(SealedKindCase):
    def test_the_classification_is_projected_with_its_own_overall_outcome(self) -> None:
        path = self.fixture("classification")
        document = self.read(path)
        section = self.project_kind("drift_classification", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["overall_outcome"], document["overall_outcome"])
        self.assertEqual(section["overall_outcome"], "replan-required")
        self.assertEqual(section["classified_at"], document["classified_at"])
        self.assertEqual(section["plan_digest"], document["plan_digest"])
        self.assertEqual(section["observation_id"], document["observation_id"])
        self.assertTrue(section["bound"])
        self.assertEqual(
            section["assessments"],
            [
                {"kind": entry["kind"], "subject": entry["subject"], "outcome": entry["outcome"]}
                for entry in document["assessments"]
            ],
        )
        self.assertIsNone(section["no_drift_reason"])

    def test_a_no_drift_classification_keeps_its_null_outcome_and_its_own_sentence(self) -> None:
        """The sharpest never-manufacture-a-verdict case in this whole extension: `drift-classifier.py`
        seals `overall_outcome: null` beside a `no_drift_reason` for an empty observation, and says in
        that very sentence that it is "not the same statement as a compatible classification". A
        projection that helpfully filled in `compatible` would be writing the verdict the producer
        refused to write."""
        path = self.fixture("classification_no_drift")
        document = self.read(path)
        self.assertIsNone(document["overall_outcome"])  # POSITIVE CONTROL: the document really is null
        section = self.project_kind("drift_classification", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertIsNone(section["overall_outcome"])
        self.assertEqual(section["assessments"], [])
        self.assertEqual(section["no_drift_reason"], document["no_drift_reason"])
        bluf = self.document(FLAG_FOR_KIND["drift_classification"], str(path))["bluf"]
        self.assertIn("records NO overall outcome", bluf)
        self.assertIn(document["no_drift_reason"], bluf)
        self.assertNotIn("compatible classification", bluf.split(":", 1)[0])

    def test_a_second_real_outcome_is_reported_as_the_document_wrote_it(self) -> None:
        path = self.fixture("classification_revalidation")
        section = self.project_kind("drift_classification", path)
        self.assertEqual(section["overall_outcome"], "revalidation-required")
        self.assertEqual(section["overall_outcome"], self.read(path)["overall_outcome"])
        self.assertEqual([entry["kind"] for entry in section["assessments"]], ["approval"])

    def test_a_classification_with_neither_an_outcome_nor_a_no_drift_reason_is_unreadable(self) -> None:
        path = self.copy_of("classification")
        self.assertEqual(self.project_kind("drift_classification", path)["presence"], PRESENT)
        document = self.read(path)
        document["overall_outcome"] = None
        self.write(path, seal(document))
        section = self.project_kind("drift_classification", path)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("neither an overall_outcome nor a no_drift_reason", section["reason"])

    def test_an_outcome_outside_the_closed_ladder_is_unreadable(self) -> None:
        path = self.copy_of("classification")
        self.assertEqual(self.project_kind("drift_classification", path)["presence"], PRESENT)
        document = self.read(path)
        document["overall_outcome"] = "fine-actually"
        self.write(path, seal(document))
        section = self.project_kind("drift_classification", path)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("'fine-actually'", section["reason"])

    def test_an_assessment_outcome_outside_the_closed_ladder_is_unreadable(self) -> None:
        """The closed vocabulary is enforced on EACH assessment's own `outcome`, not only on
        `overall_outcome`: a fourth call site (`_need_member` over `DRIFT_OUTCOMES`) guards this field
        and has no other isolating test."""
        path = self.copy_of("classification")
        # POSITIVE CONTROL: the legal form projects present before the poison lands.
        self.assertEqual(self.project_kind("drift_classification", path)["presence"], PRESENT)
        document = self.read(path)
        document["assessments"][0]["outcome"] = "fine-actually"
        self.write(path, seal(document))
        section = self.project_kind("drift_classification", path)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("'fine-actually'", section["reason"])
        self.assertIn("an assessment's outcome", section["reason"])

    def test_never_manufacture_success_a_replan_required_outcome_is_never_softened(self) -> None:
        section = self.project_kind("drift_classification", self.fixture("classification"))
        self.assertEqual(section["overall_outcome"], "replan-required")
        for softer in ("compatible", "revalidation-required"):
            self.assertNotEqual(section["overall_outcome"], softer)
        # POSITIVE CONTROL: a DIFFERENT real classification reads a different value, so the assertion
        # above is reading the document rather than a constant this module always emits.
        self.assertEqual(
            self.project_kind("drift_classification", self.fixture("classification_revalidation"))["overall_outcome"],
            "revalidation-required",
        )


class SealedAutoEnvelopeTests(SealedKindCase):
    def test_the_envelope_is_projected_including_the_bounds_it_wrote_down(self) -> None:
        path = self.fixture("envelope")
        document = self.read(path)
        section = self.project_kind("auto_envelope", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["envelope_id"], document["envelope_id"])
        self.assertEqual(section["not_before"], document["validity_window"]["not_before"])
        self.assertEqual(section["not_after"], document["validity_window"]["not_after"])
        self.assertEqual(section["bound_plan_digest"], document["bound_plan"]["plan_digest"])
        self.assertEqual(section["bound_plan_revision"], document["bound_plan"]["plan_revision"])
        self.assertEqual(section["allowed_authority_classes"], document["allowed_authority_classes"])
        self.assertEqual(section["tool_allowlist"], document["tool_allowlist"])
        self.assertEqual(section["egress_posture"], document["egress_allowlist"]["posture"])
        self.assertEqual(section["max_total_retries"], document["retry_policy"]["max_total_retries"])
        self.assertEqual(section["checkpoints_requiring_human_disposition"], ["drift-recheck"])

    def test_the_window_is_stated_never_evaluated(self) -> None:
        """This module reads no clock, so it may say what the envelope recorded and must not say the
        window is open, valid, or expired. The projected fields are the two instants and nothing else."""
        path = self.fixture("envelope")
        section = self.project_kind("auto_envelope", path)
        self.assertNotIn("window_open", section)
        self.assertNotIn("expired", section)
        bluf = self.document(FLAG_FOR_KIND["auto_envelope"], str(path))["bluf"]
        self.assertIn("validity window", bluf)
        for forbidden in ("is open", "expired", "still valid", "in force"):
            self.assertNotIn(forbidden, bluf)
        # POSITIVE CONTROL: the two recorded instants really are in the line.
        self.assertIn(section["not_before"], bluf)
        self.assertIn(section["not_after"], bluf)

    def test_the_envelope_binds_the_plan_this_module_also_projects(self) -> None:
        envelope = self.project_kind("auto_envelope", self.fixture("envelope"))
        self.assertEqual(envelope["bound_plan_digest"], self.read(self.fixture("plan"))["digest"])


class SealedTransitionReceiptTests(SealedKindCase):
    def test_the_admitted_receipt_is_projected(self) -> None:
        path = self.fixture("receipt")
        document = self.read(path)
        section = self.project_kind("transition_receipt", path)
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["verdict"], "admitted")
        self.assertEqual(section["at"], document["at"])
        self.assertEqual(section["envelope_digest"], document["envelope_digest"])
        self.assertEqual(section["transition_digest"], document["transition_digest"])
        self.assertEqual(section["reasons"], [])

    def test_the_refused_receipt_is_projected_as_refused_with_its_own_reasons(self) -> None:
        path = self.fixture("receipt_refused")
        document = self.read(path)
        section = self.project_kind("transition_receipt", path)
        self.assertEqual(section["verdict"], "refused")
        self.assertEqual(section["reasons"], document["reasons"])
        self.assertTrue(section["reasons"])
        text = self.human(FLAG_FOR_KIND["transition_receipt"], str(path))
        self.assertIn(f"  reason: {escaped(document['reasons'][0])}", text)

    def test_never_manufacture_success_a_refused_receipt_never_becomes_admitted(self) -> None:
        self.assertEqual(self.project_kind("transition_receipt", self.fixture("receipt_refused"))["verdict"], "refused")
        # POSITIVE CONTROL: the admitted fixture reads `admitted`.
        self.assertEqual(self.project_kind("transition_receipt", self.fixture("receipt"))["verdict"], "admitted")

    def test_a_receipt_binding_the_envelope_this_module_projects_carries_its_digest(self) -> None:
        receipt = self.project_kind("transition_receipt", self.fixture("receipt"))
        self.assertEqual(receipt["envelope_digest"], self.read(self.fixture("envelope"))["digest"])


class SealedKindAbsenceTests(SealedKindCase):
    def test_with_no_sealed_flag_every_sealed_kind_is_absent_by_name(self) -> None:
        artifacts = self.document()["artifacts"]
        for kind, _flag, _schema, _label in SEALED_KINDS:
            with self.subTest(kind=kind):
                self.assertIn(kind, artifacts)
                self.assertEqual(artifacts[kind]["presence"], ABSENT)
                self.assertIsNone(artifacts[kind]["path"])
                self.assertIsNone(artifacts[kind]["reason"])

    def test_a_supplied_nonexistent_path_is_absent_with_its_path_for_every_sealed_kind(self) -> None:
        for kind, flag, _schema, label in SEALED_KINDS:
            with self.subTest(kind=kind):
                missing = str(self.work / f"no-such-{kind}.json")
                section = self.document(flag, missing)["artifacts"][kind]
                self.assertEqual(section["presence"], ABSENT)
                self.assertEqual(section["path"], missing)
                self.assertIsNone(section["reason"])
                self.assertIn(f"{label}: MISSING ({missing})", self.human(flag, missing))

    def test_a_directory_supplied_for_a_sealed_kind_is_unreadable_not_a_crash(self) -> None:
        adir = self.work / "adir"
        adir.mkdir()
        for kind, flag, _schema, label in SEALED_KINDS:
            with self.subTest(kind=kind):
                section = self.document(flag, str(adir))["artifacts"][kind]
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn(label, section["reason"])
                self.assertIn("not a regular file", section["reason"])


class SealedKindCorruptionTests(SealedKindCase):
    """Per-input, per-kind: every corruption is `unreadable` NAMING that kind, and nothing else moves."""

    def test_a_truncated_document_is_unreadable_by_name_for_every_sealed_kind(self) -> None:
        for kind, _flag, _schema, label in SEALED_KINDS:
            with self.subTest(kind=kind):
                path = self.copy_of(FIXTURE_FOR_KIND[kind], as_name=f"truncated-{kind}.json")
                # POSITIVE CONTROL: the untouched copy projects.
                self.assertEqual(self.project_kind(kind, path)["presence"], PRESENT)
                raw = path.read_bytes()
                path.write_bytes(raw[: len(raw) // 2])
                section = self.project_kind(kind, path)
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn(label, section["reason"])
                self.assertIn("is not JSON", section["reason"])

    def test_a_flipped_schema_string_is_unreadable_by_name_for_every_sealed_kind(self) -> None:
        """RE-SEALED after the flip, so the digest still re-derives: what refuses here is the row's
        MATCHER, not the seal check that would otherwise mask it."""
        for kind, _flag, schema, label in SEALED_KINDS:
            with self.subTest(kind=kind):
                path = self.copy_of(FIXTURE_FOR_KIND[kind], as_name=f"reschemed-{kind}.json")
                self.assertEqual(self.project_kind(kind, path)["presence"], PRESENT)
                document = self.read(path)
                document["schema"] = "agentic-sdlc/not-this-kind@1"
                resealed = seal(document)
                self.write(path, resealed)
                self.assertEqual(sealed_digest(resealed), resealed["digest"])  # POSITIVE CONTROL
                section = self.project_kind(kind, path)
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn(label, section["reason"])
                self.assertIn("'agentic-sdlc/not-this-kind@1'", section["reason"])
                self.assertIn(repr(schema), section["reason"])

    def test_a_tampered_body_fails_digest_re_derivation_for_every_sealed_kind(self) -> None:
        """The added key is one NO projector reads, so if the seal check were gone the document would
        project as `present` -- which is exactly what makes this a test of the re-derivation itself."""
        for kind, _flag, _schema, label in SEALED_KINDS:
            with self.subTest(kind=kind):
                path = self.copy_of(FIXTURE_FOR_KIND[kind], as_name=f"tampered-{kind}.json")
                self.assertEqual(self.project_kind(kind, path)["presence"], PRESENT)
                document = self.read(path)
                document["an_unrecorded_field"] = "added after sealing"
                self.write(path, document)
                section = self.project_kind(kind, path)
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn(label, section["reason"])
                self.assertIn("does not verify: its digest does not re-derive", section["reason"])

    def test_a_document_with_no_digest_at_all_is_unreadable_for_every_sealed_kind(self) -> None:
        for kind, _flag, _schema, label in SEALED_KINDS:
            with self.subTest(kind=kind):
                path = self.copy_of(FIXTURE_FOR_KIND[kind], as_name=f"unsealed-{kind}.json")
                document = self.read(path)
                del document["digest"]
                self.write(path, document)
                section = self.project_kind(kind, path)
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn(label, section["reason"])
                self.assertIn("carries no digest", section["reason"])

    def test_corrupting_one_input_leaves_the_other_seven_present(self) -> None:
        for kind, _flag, _schema, _label in SEALED_KINDS:
            with self.subTest(corrupted=kind):
                argv = self.every_flag()
                broken = self.copy_of(FIXTURE_FOR_KIND[kind], as_name=f"broken-{kind}.json")
                broken.write_text("{not json at all", encoding="utf-8")
                argv[argv.index(FLAG_FOR_KIND[kind]) + 1] = str(broken)
                artifacts = self.document(*argv)["artifacts"]
                self.assertEqual(artifacts[kind]["presence"], UNREADABLE)
                for other, _f, _s, _l in SEALED_KINDS:
                    if other != kind:
                        self.assertEqual(artifacts[other]["presence"], PRESENT, f"{other} lost its own outcome")

    def test_all_eight_project_together_and_the_document_still_succeeds(self) -> None:
        document = self.document(*self.every_flag())
        self.assertEqual(document["exit_code"], EXIT_OK)
        for kind, _flag, _schema, _label in SEALED_KINDS:
            self.assertEqual(document["artifacts"][kind]["presence"], PRESENT, kind)


class SealedKindHumanViewTests(SealedKindCase):
    def test_each_sealed_kinds_two_views_agree(self) -> None:
        for kind, flag, _schema, label in SEALED_KINDS:
            with self.subTest(kind=kind):
                path = self.fixture(FIXTURE_FOR_KIND[kind])
                document = self.document(flag, str(path))
                text = self.human(flag, str(path))
                section = document["artifacts"][kind]
                self.assertEqual(text.splitlines()[0], f"BLUF: {document['bluf']}")
                self.assertIn(f"{label}: present ({path})", text)
                body = self.section_text(text, label)
                for field in HUMAN_FIELDS[kind]:
                    value = section[field]
                    rendered = escaped(value) if isinstance(value, str) else str(value)
                    self.assertIn(rendered, body, f"{kind}.{field} is projected but never rendered")

    def test_every_sealed_kind_has_its_own_section_even_when_nothing_is_supplied(self) -> None:
        text = self.human()
        for kind, _flag, _schema, label in SEALED_KINDS:
            with self.subTest(kind=kind):
                self.assertIn(f"== {label} ==", text)
                self.assertIn(f"{label}: not supplied", text)

    def test_the_evidence_notice_still_sits_above_every_new_section(self) -> None:
        text = self.human(*self.every_flag())
        lines = text.splitlines()
        notice = lines.index(EVIDENCE_NOTICE)
        for kind, _flag, _schema, label in SEALED_KINDS:
            self.assertGreater(lines.index(f"== {label} =="), notice, kind)


class SealedInjectionTests(SealedKindCase):
    """The `_flat` escaping hazard, once per new kind. Every producer in this family validates its
    input, so a control character cannot be got into a real document through one of them -- the
    document is therefore poisoned and RE-SEALED here with the same derivation the producers use, which
    is what makes the projection accept it as sealed and the hazard reachable at all."""

    #: Per kind: how to poison one string field the human view renders, and how to read that same
    #: poisoned value back out of the `--json` section (the positive control that the RAW control
    #: character really did reach the projection rather than being lost on the way in).
    POISON = {
        "mission_contract": (lambda doc, bad: doc.__setitem__("objective", bad), lambda s: s["objective"]),
        "planning_snapshot": (lambda doc, bad: doc["head"].__setitem__("branch", bad), lambda s: s["branch"]),
        "wave_plan": (lambda doc, bad: doc["nodes"][0].__setitem__("node_id", bad), lambda s: s["node_ids"][0]),
        "plan_diff": (lambda doc, bad: doc.__setitem__("no_delta_reason", bad), lambda s: s["no_delta_reason"]),
        "wave_plan_admission": (
            lambda doc, bad: doc["checks"][0].__setitem__("blockers", [bad]),
            lambda s: s["blockers"][0],
        ),
        "drift_classification": (
            lambda doc, bad: doc["assessments"][0].__setitem__("subject", bad),
            lambda s: s["assessments"][0]["subject"],
        ),
        "auto_envelope": (lambda doc, bad: doc.__setitem__("envelope_id", bad), lambda s: s["envelope_id"]),
        "transition_receipt": (lambda doc, bad: doc.__setitem__("reasons", [bad]), lambda s: s["reasons"][0]),
    }

    def test_a_control_character_in_any_new_kind_cannot_forge_a_line(self) -> None:
        for kind, flag, _schema, label in SEALED_KINDS:
            for control_char, escape, name in ((chr(10), "\\n", "newline"), (chr(13), "\\r", "carriage-return")):
                with self.subTest(kind=kind, control=name):
                    poison, extract = self.POISON[kind]
                    bad = f"real{control_char}injected: forged line"
                    path = self.copy_of(FIXTURE_FOR_KIND[kind], as_name=f"poisoned-{kind}-{name}.json")
                    document = self.read(path)
                    poison(document, bad)
                    self.write(path, seal(document))
                    projected = self.document(flag, str(path))
                    section = projected["artifacts"][kind]
                    self.assertEqual(section["presence"], PRESENT, section.get("reason"))
                    # POSITIVE CONTROL: the raw control character really is in the projected value,
                    # round-tripped through real JSON escaping rather than this module's own.
                    self.assertEqual(extract(section), bad)
                    text = self.human(flag, str(path))
                    for line in text.splitlines():
                        self.assertFalse(
                            line.startswith("injected:"), f"a forged line leaked into {kind}: {line!r}"
                        )
                    self.assertIn(f"real{escape}injected: forged line", text)
                    self.assertIn(f"real{escape}injected: forged line", self.section_text(text, label))

    def test_a_control_character_in_a_new_kinds_bluf_cannot_forge_a_line_above_the_notice(self) -> None:
        """The BLUF is the one line ABOVE the evidence notice, so a forged line there is the worst
        case: it would read as a fact of its own before the reader ever sees the notice."""
        bad = f"real{chr(10)}injected: forged headline"
        path = self.copy_of("admission", as_name="poisoned-bluf.json")
        document = self.read(path)
        document["checks"][0]["blockers"] = [bad]
        self.write(path, seal(document))
        flag = FLAG_FOR_KIND["wave_plan_admission"]
        projected = self.document(flag, str(path))
        text = self.human(flag, str(path))
        self.assertEqual(text.splitlines()[0], f"BLUF: {projected['bluf']}")
        self.assertLess(text.splitlines().index(EVIDENCE_NOTICE), 4)
        for line in text.splitlines():
            self.assertFalse(line.startswith("injected:"), f"a forged line leaked: {line!r}")


class SchemaVersionTests(SealedKindCase):
    """The bump to `@2` and the promise that came with it: nothing `@1` published was removed."""

    def test_the_result_schema_is_at_version_two(self) -> None:
        self.assertEqual(self.document()["schema"], "agentic-sdlc/observability-projection@2")

    def test_every_v1_top_level_field_survives_unchanged(self) -> None:
        document = self.document()
        self.assertEqual(set(document), set(V1_TOP_LEVEL_KEYS))
        self.assertEqual(document["command"], "project")
        self.assertEqual(document["status"], "projected")
        self.assertEqual(document["exit_code"], EXIT_OK)

    def test_every_v1_artifact_section_survives_with_its_own_v1_fields(self) -> None:
        """The four original kinds are checked FIELD-FOR-FIELD on a fully populated run, because a
        rename inside one of them would be invisible to a key-set check over an all-absent document."""
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        journal = self.make_wave_journal(complete=True)
        report = self.make_classification()
        activation = self.make_activation_refused()
        document = self.document(
            "--wave-journal", str(journal), "--runtime-assignment", str(report),
            "--activation-result", str(activation), "--gate-receipt", str(receipt),
        )
        artifacts = document["artifacts"]
        for kind in V1_ARTIFACT_KINDS:
            self.assertIn(kind, artifacts)
        self.assertEqual(
            set(artifacts["wave_journal"]),
            {"presence", "path", "reason", "wave_id", "mode", "plan_digest", "required_node_count",
             "required_nodes_without_disposition", "complete", "entry_count", "opened_at", "last_at",
             "plan_revision_count", "approval_count", "retry_count", "budget_count"},
        )
        self.assertEqual(
            set(artifacts["runtime_assignment"]),
            {"presence", "path", "reason", "command", "verdict", "consequence", "may_spawn",
             "blocks_wave_completion", "reasons", "node"},
        )
        self.assertEqual(
            set(artifacts["activation_result"]),
            {"presence", "path", "reason", "state", "consequence", "target", "gate_outcome", "gate_passes",
             "reasons"},
        )
        self.assertEqual(set(artifacts["gate"]), {"receipt", "baseline", "cross_check"})
        self.assertEqual(
            set(artifacts["gate"]["receipt"]),
            {"presence", "path", "reason", "gate", "outcome", "gate_status", "ran", "failing_set_state",
             "failing_test_count"},
        )

    def test_the_artifacts_object_carries_exactly_the_twelve_known_kinds(self) -> None:
        artifacts = self.document()["artifacts"]
        self.assertEqual(
            set(artifacts), set(V1_ARTIFACT_KINDS) | {kind for kind, _f, _s, _l in SEALED_KINDS}
        )

    def test_the_module_docstring_names_the_version_it_actually_emits(self) -> None:
        """Cheap, and it catches the one drift that matters here: a bumped constant whose docstring
        still advertises the old version to a consumer reading `--help`'s neighbourhood."""
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn("agentic-sdlc/observability-projection@2", source)
        self.assertNotIn("agentic-sdlc/observability-projection@1", source)


class BlufPriorityTests(SealedKindCase):
    """The full ladder, widest consequence first, each rung checked by construction:

    activation_result > wave_plan_admission > drift_classification > gate > runtime_assignment >
    transition_receipt > wave_journal > mission_contract > planning_snapshot > wave_plan > plan_diff >
    auto_envelope

    -- and an UNREADABLE input at any rung still outranks every PRESENT kind below it, because "I could
    not read this" is itself the most decision-relevant thing that rung has to say."""

    def test_activation_result_outranks_everything_else(self) -> None:
        activation = self.make_activation_refused()
        journal = self.make_wave_journal(complete=False)
        report = self.make_classification(served_model="claude-opus-4-8")
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        document = self.document(
            "--activation-result", str(activation), "--wave-journal", str(journal),
            "--runtime-assignment", str(report), "--gate-receipt", str(receipt),
        )
        self.assertIn("activation state", document["bluf"])

    def test_gate_outranks_runtime_assignment_and_wave_journal(self) -> None:
        journal = self.make_wave_journal(complete=False)
        report = self.make_classification(served_model="claude-opus-4-8")
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        document = self.document(
            "--wave-journal", str(journal), "--runtime-assignment", str(report), "--gate-receipt", str(receipt),
        )
        self.assertIn("gate smoke", document["bluf"])

    def test_runtime_assignment_outranks_wave_journal(self) -> None:
        journal = self.make_wave_journal(complete=False)
        report = self.make_classification(served_model="claude-opus-4-8")
        document = self.document("--wave-journal", str(journal), "--runtime-assignment", str(report))
        self.assertIn("runtime-assignment", document["bluf"])

    def test_wave_journal_is_the_bluf_when_it_is_the_only_input(self) -> None:
        journal = self.make_wave_journal(complete=False)
        document = self.document("--wave-journal", str(journal))
        self.assertIn("wave wave-1", document["bluf"])

    def test_an_unreadable_higher_priority_kind_still_outranks_a_present_lower_one(self) -> None:
        journal = self.make_wave_journal(complete=True)
        broken_activation = self.work / "broken-activation.json"
        broken_activation.write_text("{not json", encoding="utf-8")
        document = self.document("--activation-result", str(broken_activation), "--wave-journal", str(journal))
        self.assertIn("activation result document is unreadable", document["bluf"])

    #: The ladder from LOWEST priority to highest, each rung as the flags that produce it plus the
    #: fragment its own BLUF line must carry. `test_the_whole_ladder_is_walked_once` adds one rung at a
    #: time and demands the newly added rung take over the headline every single time -- so a row moved,
    #: duplicated, or dropped in `BLUF_ORDER` fails here rather than passing quietly.
    def _ladder(self) -> list[tuple[str, list[str], str]]:
        return [
            ("auto_envelope", ["--auto-envelope", str(self.fixture("envelope"))], "auto envelope auto-slice-6-t4"),
            ("plan_diff", ["--plan-diff", str(self.fixture("diff"))], "plan diff for plan"),
            ("wave_plan", ["--wave-plan", str(self.fixture("plan"))], "wave plan revision 1 for mission"),
            (
                "planning_snapshot",
                ["--planning-snapshot", str(self.fixture("compiled_snapshot"))],
                "planning snapshot stated at",
            ),
            ("mission_contract", ["--mission-contract", str(self.fixture("mission"))], "mission mission-slice-6"),
            ("wave_journal", ["--wave-journal", str(self.make_wave_journal(complete=False))], "wave wave-1"),
            (
                "transition_receipt",
                ["--transition-receipt", str(self.fixture("receipt_refused"))],
                "autonomous transition receipt verdict: refused",
            ),
            (
                "runtime_assignment",
                ["--runtime-assignment", str(self.make_classification(served_model="claude-opus-4-8"))],
                "runtime-assignment classify verdict",
            ),
            (
                "gate",
                ["--gate-receipt", str(self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT))],
                "gate smoke",
            ),
            (
                "drift_classification",
                ["--drift-classification", str(self.fixture("classification"))],
                "drift classification overall outcome: replan-required",
            ),
            (
                "wave_plan_admission",
                ["--wave-plan-admission", str(self.fixture("admission_blocked"))],
                "wave plan admission disposition: blocked",
            ),
            (
                "activation_result",
                ["--activation-result", str(self.make_activation_refused())],
                "activation state: refused",
            ),
        ]

    def test_the_whole_ladder_is_walked_once_from_the_bottom_up(self) -> None:
        argv: list[str] = []
        for kind, flags, fragment in self._ladder():
            argv += flags
            with self.subTest(newly_added=kind):
                document = self.document(*argv)
                self.assertIn(fragment, document["bluf"], f"{kind} did not take over the headline")

    def test_the_admission_disposition_outranks_the_gate_and_the_drift_classification(self) -> None:
        document = self.document(
            "--gate-receipt", str(self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)),
            "--drift-classification", str(self.fixture("classification")),
            "--wave-plan-admission", str(self.fixture("admission")),
        )
        self.assertIn("wave plan admission disposition: admitted", document["bluf"])

    def test_an_activation_refusal_still_outranks_the_admission_disposition(self) -> None:
        """The pre-existing top rung keeps its place: no wave may write at all, which subsumes whether
        one particular wave plan was admitted."""
        document = self.document(
            "--wave-plan-admission", str(self.fixture("admission")),
            "--activation-result", str(self.make_activation_refused()),
        )
        self.assertIn("activation state: refused", document["bluf"])

    def test_the_drift_classification_outranks_the_gate(self) -> None:
        document = self.document(
            "--gate-receipt", str(self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)),
            "--drift-classification", str(self.fixture("classification")),
        )
        self.assertIn("drift classification overall outcome", document["bluf"])

    def test_an_unreadable_admission_report_outranks_a_present_gate_and_drift_classification(self) -> None:
        broken = self.work / "broken-admission.json"
        broken.write_text("{not json", encoding="utf-8")
        document = self.document(
            "--gate-receipt", str(self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)),
            "--drift-classification", str(self.fixture("classification")),
            "--wave-plan-admission", str(broken),
        )
        self.assertIn("the wave plan admission report is unreadable", document["bluf"])

    def test_an_unreadable_descriptive_kind_outranks_only_the_kinds_below_it(self) -> None:
        """POSITIVE CONTROL for the direction of the rule: an unreadable LOW rung must NOT climb over a
        present higher one."""
        broken = self.work / "broken-envelope.json"
        broken.write_text("{not json", encoding="utf-8")
        document = self.document(
            "--auto-envelope", str(broken), "--wave-plan", str(self.fixture("plan")),
        )
        self.assertIn("wave plan revision 1", document["bluf"])
        self.assertNotIn("auto envelope", document["bluf"])
        # ... and with nothing above it, the same unreadable input does headline.
        alone = self.document("--auto-envelope", str(broken))
        self.assertIn("the auto envelope is unreadable", alone["bluf"])

    def test_a_supplied_but_missing_sealed_path_counts_toward_the_nothing_to_project_bluf(self) -> None:
        first = str(self.work / "no-envelope.json")
        second = str(self.work / "no-mission.json")
        document = self.document("--auto-envelope", first, "--mission-contract", second)
        self.assertEqual(
            document["bluf"], "every supplied artifact path is missing (2 path(s) supplied): nothing to project"
        )


class CanonicalFormTests(ProjectionCase):
    def test_the_json_view_is_canonical_bytes_with_one_trailing_newline(self) -> None:
        done = self.run_tool("--json")
        self.assertEqual(done.returncode, EXIT_OK)
        self.assertEqual(done.stdout, canonical(json.loads(done.stdout)))
        self.assertTrue(done.stdout.endswith(b"}\n"))
        self.assertEqual(done.stdout.count(b"\n"), 1)
        self.assertEqual(done.stdout, done.stdout.decode("ascii").encode("ascii"))

    def test_a_non_ascii_value_carried_verbatim_from_an_artifact_is_escaped(self) -> None:
        """`ensure_ascii=True` is the half of the canonical form a JSON round-trip cannot detect. The
        non-ASCII text here is carried VERBATIM from a real gate receipt's own `gate` label -- this
        module never translates it, only re-serializes it faithfully."""
        receipt = self.make_gate_receipt(name="r.json", gate="portée réelle — π", script=PASSING_SCRIPT)
        done = self.run_tool("--gate-receipt", str(receipt), "--json")
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, done.stdout.decode("ascii").encode("ascii"))
        self.assertIn(b"port\\u00e9e r\\u00e9elle", done.stdout)
        self.assertIn(b"\\u03c0", done.stdout)
        document = json.loads(done.stdout)
        self.assertEqual(document["artifacts"]["gate"]["receipt"]["gate"], "portée réelle — π")

    def test_human_and_json_views_derive_from_the_same_bluf(self) -> None:
        journal = self.make_wave_journal(complete=False)
        text = self.human("--wave-journal", str(journal))
        document = self.document("--wave-journal", str(journal))
        self.assertEqual(text.splitlines()[0], f"BLUF: {document['bluf']}")


class NonFiniteJsonTests(ProjectionCase):
    """Both layers the hard rule requires: `parse_constant` for the literal tokens, and a post-parse
    walk for a numeral like `1e400` that silently overflows to `inf` without ever reaching it."""

    def test_a_literal_nan_token_is_unreadable(self) -> None:
        report = self.make_classification()
        # POSITIVE CONTROL: valid JSON is present.
        self.assertEqual(self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]["presence"], PRESENT)
        report.write_bytes(b'{"schema": "agentic-sdlc/runtime-substitution-classification@1", "verdict": NaN}')
        section = self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("non-finite", section["reason"])

    def test_an_overflowing_numeral_that_parse_constant_never_sees_is_still_rejected(self) -> None:
        """`1e400` is an ordinary-looking JSON numeral, not the literal token `Infinity`:
        `parse_constant` never fires for it (that hook only sees the exact tokens `NaN` /
        `Infinity` / `-Infinity`), so only the POST-PARSE WALK can catch the `inf` `float()` silently
        produces. `json.dumps` of a Python `inf` would itself write the literal token `Infinity` and
        short-circuit through `parse_constant` instead -- so this writes the raw numeral by hand."""
        self.assertTrue(math.isinf(float("1e400")))  # POSITIVE CONTROL: this is the exact failure mode
        report = self.make_classification()
        raw = report.read_text(encoding="utf-8")
        self.assertNotIn("Infinity", raw)  # POSITIVE CONTROL: the untouched fixture has no such token
        self.assertTrue(raw.rstrip("\n").endswith("}"))
        mutated = raw.rstrip("\n")[:-1] + ',"bogus_score":1e400}\n'
        report.write_text(mutated, encoding="utf-8")
        section = self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not a finite floating point value", section["reason"])

    def test_a_duplicate_json_key_is_unreadable_rather_than_silently_resolved(self) -> None:
        report = self.make_classification()
        raw = report.read_text(encoding="utf-8")
        self.assertIn('"verdict"', raw)
        # Append a second `verdict` key rather than relying on a particular separator style.
        doc = json.loads(raw)
        body = json.dumps(doc)
        duplicated = body[:-1] + ',"verdict":"forged"}'
        report.write_text(duplicated, encoding="utf-8")
        section = self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("repeats the JSON key", section["reason"])


class ExitSpaceAndGrammarTests(ProjectionCase):
    def test_an_unknown_flag_is_a_grammar_error_at_exit_two_with_no_stdout(self) -> None:
        done = self.run_tool("--not-a-real-flag")
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertEqual(done.stdout, b"")
        self.assertIn(b"error", done.stderr)

    def test_help_exits_zero_and_documents_the_exit_space(self) -> None:
        done = self.run_tool("--help")
        self.assertEqual(done.returncode, EXIT_OK)
        text = done.stdout.decode("utf-8")
        self.assertIn("--wave-journal", text)
        self.assertIn("3 and 4 do not apply", text)
        for _kind, flag, _schema, _label in SEALED_KINDS:
            self.assertIn(flag, text, f"{flag} is a real input and must be documented in --help")

    def test_the_module_never_causes_an_effect(self) -> None:
        """Checked with `ast`, not prose: this module's docstring says "never writes anything", and a
        substring search over the source would find the promise rather than test it."""
        modules, calls = imports_and_calls(TOOL)
        self.assertNotIn("shutil", modules)
        forbidden = {"open", "write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir", "rename",
                     "symlink_to", "hardlink_to", "chmod", "system", "popen", "fdopen", "fsync"}
        self.assertEqual(calls & forbidden, set(), "a read-only projection calls nothing that can write")
        # POSITIVE CONTROL: the same walk over a tool that DOES write finds the forbidden set.
        other_modules, other_calls = imports_and_calls(WAVE_JOURNAL_TOOL)
        self.assertIn("os", other_modules)
        self.assertTrue(other_calls & forbidden, "the control tool must exercise the forbidden set")

    def test_the_module_imports_no_sibling_tool(self) -> None:
        """No `import` of another tool in this family, hyphenated or not -- consuming their OUTPUT
        documents is the whole point, never their code."""
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("import wave_journal", source)
        self.assertNotIn("import runtime_assignment", source)
        self.assertNotIn("import activation_result", source)
        self.assertNotIn("import gate_receipt", source)
        self.assertNotIn("import gate_baseline", source)
        for sibling in (
            "mission_contract", "planning_snapshot", "wave_plan_compiler", "wave_plan_admission",
            "drift_classifier", "auto_envelope",
        ):
            self.assertNotIn(f"import {sibling}", source)
        modules, _ = imports_and_calls(TOOL)
        self.assertEqual(
            modules,
            {"__future__", "argparse", "hashlib", "json", "math", "os", "pathlib", "stat", "subprocess", "sys", "typing"},
            "an unexpected import means a sibling tool was reached for by code rather than by document",
        )


class HostileDescriptorTests(ProjectionCase):
    def test_a_closed_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        argv = ["--not-a-real-flag"]
        control = self.run_tool(*argv)
        self.assertEqual(control.returncode, EXIT_INPUT)
        code, out = run_with_hostile_stderr([sys.executable, "-B", str(TOOL), *argv], mode="closed", cwd=self.work)
        self.assertEqual(code, EXIT_INPUT, "a missing stderr must not become exit 1")
        self.assertEqual(out, b"")

    def test_an_epipe_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        argv = ["--not-a-real-flag"]
        code, out = run_with_hostile_stderr([sys.executable, "-B", str(TOOL), *argv], mode="epipe", cwd=self.work)
        self.assertEqual(code, EXIT_INPUT, "a broken stderr must not become exit 120")
        self.assertEqual(out, b"")

    def test_a_closed_stdout_reports_an_undelivered_document(self) -> None:
        control = self.run_tool("--json")
        self.assertEqual(control.returncode, EXIT_OK)
        code, err = run_with_hostile_stdout([sys.executable, "-B", str(TOOL), "--json"], mode="closed", cwd=self.work)
        self.assertEqual(code, EXIT_INTERNAL)
        self.assertIn(b"handed no stdout", err)

    def test_an_epipe_stdout_reports_an_undelivered_document(self) -> None:
        code, err = run_with_hostile_stdout([sys.executable, "-B", str(TOOL), "--json"], mode="epipe", cwd=self.work)
        self.assertEqual(code, EXIT_INTERNAL, "a broken stdout must not become exit 120")
        self.assertIn(b"reached the consumer", err)

    def test_a_closed_stdout_in_the_default_human_view_also_reports_undelivered(self) -> None:
        code, err = run_with_hostile_stdout([sys.executable, "-B", str(TOOL)], mode="closed", cwd=self.work)
        self.assertEqual(code, EXIT_INTERNAL)
        self.assertIn(b"handed no stdout", err)

    def test_both_streams_hostile_at_once_still_classifies(self) -> None:
        done = subprocess.run(
            ["sh", "-c", 'exec 1>&- 2>&-; exec "$@"', "sh", sys.executable, "-B", str(TOOL), "--json"],
            cwd=str(self.work),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(done.returncode, EXIT_INTERNAL)


class EnvironmentAndHostCouplingTests(ProjectionCase):
    def test_the_wave_journal_subprocess_call_constructs_its_environment_from_an_allowlist(self) -> None:
        """A structural guard, mutation-checked: the ONE `subprocess.run` call site in this module
        must pass `env=constructed_environment()`, never `os.environ` and never an implicit
        inheritance, so an ambient variable (including the sibling's OWN fault-injection hook) cannot
        silently reach the spawned process."""
        tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        run_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        self.assertEqual(len(run_calls), 1, "expected exactly one subprocess.run call site in this module")
        env_kw = next((kw for kw in run_calls[0].keywords if kw.arg == "env"), None)
        self.assertIsNotNone(env_kw, "subprocess.run must pass env= explicitly")
        self.assertIsInstance(env_kw.value, ast.Call)
        self.assertIsInstance(env_kw.value.func, ast.Name)
        self.assertEqual(env_kw.value.func.id, "constructed_environment")

    def test_an_unrelated_ambient_variable_does_not_change_the_projection(self) -> None:
        journal = self.make_wave_journal(complete=True)
        first = run([sys.executable, "-B", str(TOOL), "--wave-journal", str(journal), "--json"], cwd=self.work)
        second = run(
            [sys.executable, "-B", str(TOOL), "--wave-journal", str(journal), "--json"],
            cwd=self.work,
            extra_env={"AGENTIC_SDLC_OBSERVABILITY_PROJECTION": "ignored", "SOURCE_DATE_EPOCH": "0"},
        )
        self.assertEqual(first.returncode, EXIT_OK)
        self.assertEqual(second.stdout, first.stdout)

    def test_the_module_reads_no_environment_variable_of_its_own(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        occurrences = source.count("os.environ")
        # Exactly the two reads inside `constructed_environment` itself (the allowlist membership
        # test and the value lookup); no OTHER function may read `os.environ` directly.
        self.assertEqual(occurrences, 2, "an unexpected os.environ read means a control variable crept in")

    def test_the_projection_does_not_depend_on_the_callers_working_directory(self) -> None:
        journal = self.make_wave_journal(complete=True)
        other_cwd = self.work / "elsewhere"
        other_cwd.mkdir()
        from_work = run([sys.executable, "-B", str(TOOL), "--wave-journal", str(journal), "--json"], cwd=self.work)
        from_elsewhere = run(
            [sys.executable, "-B", str(TOOL), "--wave-journal", str(journal), "--json"], cwd=other_cwd
        )
        self.assertEqual(from_work.returncode, EXIT_OK)
        self.assertEqual(from_elsewhere.stdout, from_work.stdout)

    def test_a_deeply_nested_tmpdir_is_tolerated(self) -> None:
        deep = self.work
        for index in range(12):
            deep = deep / f"level-{index}-of-a-deliberately-long-directory-component-name"
        deep.mkdir(parents=True)
        journal = deep / "journal.ndjson"
        header = {
            "wave_id": "wave-deep", "mission_id": "mission-slice-6", "mode": "static-dag", "plan_digest": "b" * 64,
            "approval": "approved", "required_nodes": ["only-node"],
            "limits": {"max_concurrent_nodes": 1, "max_nodes": 1, "max_recursive_generations": 0},
        }
        header_path = deep / "header.json"
        header_path.write_text(json.dumps(header), encoding="utf-8")
        init = run(
            [sys.executable, "-B", str(WAVE_JOURNAL_TOOL), "init", "--journal", str(journal), "--at",
             "2026-08-20T00:00:00Z", "--record", f"@{header_path}"],
            cwd=deep,
        )
        self.assertEqual(init.returncode, EXIT_OK, init.stderr.decode("utf-8", "replace"))
        document = self.document("--wave-journal", str(journal))
        section = document["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["wave_id"], "wave-deep")


class HumanViewInjectionSafetyTests(ProjectionCase):
    """Blocker 1: `gate_receipt.py record` happily seals a `--gate` label containing a bare control
    character (its self_digest re-derives over whatever bytes it was given), so an artifact-derived
    string can carry a raw `\\n` or `\\r`. Before the fix, `render_human` and the four `_bluf_*`
    builders interpolated that string bare, so the label forged a whole extra line into the human
    view -- including into the BLUF line itself, which sits ABOVE the evidence notice. `\\r` alone is
    enough (`str.splitlines()` treats it as a line break too), so splitting on `\\n` is not a fix."""

    def test_a_control_character_in_a_gate_label_cannot_forge_a_line_into_the_human_view(self) -> None:
        for control_char, escaped, name in ((chr(10), "\\n", "newline"), (chr(13), "\\r", "carriage-return")):
            with self.subTest(control=name):
                label = f"smoke{control_char}injected: line"
                receipt = self.make_gate_receipt(name=f"r-{name}.json", gate=label, script=PASSING_SCRIPT)

                # POSITIVE CONTROL: the receipt really carries the RAW control character, and the
                # JSON view (real JSON escaping, never this module's own interpolation) round-trips
                # it back to the exact original label.
                document = self.document("--gate-receipt", str(receipt))
                self.assertEqual(document["artifacts"]["gate"]["receipt"]["gate"], label)

                text = self.human("--gate-receipt", str(receipt))
                for line in text.splitlines():
                    self.assertFalse(
                        line.startswith("injected:"),
                        f"a forged line leaked into the human view: {line!r}",
                    )
                # The escaped form appears literally, on one line, in place of the raw label.
                self.assertIn(f"smoke{escaped}injected: line", text)
                # The BLUF line -- the one line that sits above the evidence notice -- is itself
                # exactly one line and carries the same escaped form, never the raw control char.
                first_line = text.splitlines()[0]
                self.assertEqual(first_line, f"BLUF: {document['bluf']}")
                self.assertIn(f"smoke{escaped}injected: line", first_line)

    def test_a_newline_in_an_activation_reason_cannot_forge_a_line_either(self) -> None:
        """The same hazard through a different artifact kind and a different render_human branch
        (the per-reason loop), using a HAND-WRITTEN activation result for the same bounded-scope
        reason `ActivationResultPresentTests` states."""
        document_body = {
            "schema": "agentic-sdlc/activation-terminal-state@1",
            "command": "derive",
            "state": "refused",
            "exit_code": 0,
            "consequence": "no wave may write; the reasons and recovery evidence below name what is missing",
            "classification": "brownfield",
            "gate_outcome": None,
            "gate_passes": None,
            "target": "/repo",
            "reasons": ["smoke\ninjected: reason line"],
            "recovery": {"admitted_effects": [], "activation_reasons": [], "recover_verbs": []},
            "evidence": {},
        }
        path = self.work / "refused-with-newline-reason.json"
        path.write_text(json.dumps(document_body), encoding="utf-8")
        text = self.human("--activation-result", str(path))
        for line in text.splitlines():
            self.assertFalse(line.startswith("injected:"), f"a forged line leaked into the human view: {line!r}")
        self.assertIn("reason: smoke\\ninjected: reason line", text)


class SuppliedButMissingPathTests(ProjectionCase):
    """Blocker 2: `_presence_line` rendered PRESENCE_ABSENT as "not supplied" without consulting
    `path`, so a supplied path that does not exist looked identical to a kind that was never asked
    for -- and `compute_bluf`'s fallback made the same conflation, contradicting the per-artifact
    `--json` view which does record the path. The fix distinguishes "not supplied" (`path is None`)
    from "MISSING" (`path` is set but does not exist), in both views."""

    def test_a_supplied_nonexistent_gate_receipt_path_is_named_missing_not_not_supplied(self) -> None:
        missing = str(self.work / "does-not-exist" / "receipt.json")
        text = self.human("--gate-receipt", missing)
        self.assertIn(f"gate receipt: MISSING ({missing}): the supplied path does not exist", text)
        self.assertNotIn("gate receipt: not supplied", text)
        document = self.document("--gate-receipt", missing)
        self.assertEqual(document["artifacts"]["gate"]["receipt"]["path"], missing)
        self.assertEqual(
            document["bluf"], "every supplied artifact path is missing (1 path(s) supplied): nothing to project"
        )

    def test_multiple_supplied_missing_paths_are_all_named_missing_and_the_bluf_counts_them(self) -> None:
        missing_journal = str(self.work / "no-journal.ndjson")
        missing_receipt = str(self.work / "no-receipt.json")
        document = self.document("--wave-journal", missing_journal, "--gate-receipt", missing_receipt)
        self.assertEqual(
            document["bluf"], "every supplied artifact path is missing (2 path(s) supplied): nothing to project"
        )
        text = self.human("--wave-journal", missing_journal, "--gate-receipt", missing_receipt)
        self.assertIn(f"wave journal: MISSING ({missing_journal}): the supplied path does not exist", text)
        self.assertIn(f"gate receipt: MISSING ({missing_receipt}): the supplied path does not exist", text)

    def test_zero_flags_still_renders_the_original_not_supplied_wording(self) -> None:
        """POSITIVE CONTROL: with nothing supplied at all, the ORIGINAL "not supplied" wording and
        the ORIGINAL zero-input BLUF stay exactly as they were -- the fix distinguishes the two
        cases rather than always naming a count."""
        document = self.document()
        self.assertEqual(document["bluf"], "no observability artifact was supplied: nothing to project")
        text = self.human()
        self.assertIn("gate receipt: not supplied", text)
        self.assertIn("wave journal: not supplied", text)
        self.assertNotIn("MISSING", text)


class NoRegexBackslashDTests(unittest.TestCase):
    """`\\d` matches every Unicode decimal digit, not only ASCII 0-9, which has already bitten this
    repository once (mission-contract.py's `stated_at`). This module is checked for the same defect
    even though it has no timestamp field of its own, because a future edit could add one."""

    def test_no_backslash_d_appears_in_the_module_source(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("\\d", source)


if __name__ == "__main__":
    unittest.main()
