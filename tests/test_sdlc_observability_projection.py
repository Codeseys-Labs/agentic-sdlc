"""Tests for the read-only observability projection (slice 6's exit artifact).

ALL FOUR of the original artifact kinds have their fixtures built by RUNNING the real sibling tool
that emits them -- `wave-journal.py` for the ledger, `runtime-assignment.py` for both report shapes,
`activation-result.py` for the activation result, and `gate_receipt.py` plus `gate_baseline.py` for
the two halves of the gate kind -- in a scratch directory, never by hand-writing a guess of their
format. Three kinds of exception exist, each named at its use rather than left to be inferred:

  * `ActivationResultTests`'s write-ready and remediation-ready fixtures are HAND-WRITTEN, because
    assembling activation-result.py's own full five-artifact upstream chain (a classification result,
    a contract write result, an activation plan, an activation apply result, and a matching gate
    receipt/baseline, each itself the output of a further multi-artifact chain) is out of this
    ticket's bounded scope. That is two FIXTURES of one kind, not a whole kind: the same class's
    `refused` fixture is the real tool's own output. activation-result.py's document carries no
    digest, so a hand-written one is not forging anything sealed.
  * A receipt or sealed document that a producer REFUSES to emit -- a bool `status`, an `outcome`
    its own `status` does not derive, a third transition verdict -- is edited and then RE-SEALED with
    that family's own derivation (`reseal_gate_receipt`, `seal`), so the tool under test sees a
    genuinely sealed document rather than one whose digest is merely claimed. Every such test says so
    on the spot, and each carries a positive control over the untouched fixture.
  * `WaveJournalSiblingContractTests` COPIES the tool under test beside a STUB `wave-journal.py`,
    because the one input this module re-derives by invoking a sibling is the one input whose
    stdout contract no real sibling can be made to break.

The EIGHT SEALED SLICE-6 KINDS are likewise built by running the real producers, as one chain in a
module-scoped temp directory: `mission-contract.py define`, `planning-snapshot.py capture` over a
really-initialised git repository, `wave-plan-compiler.py compile` (which seals the wave plan AND its
plan diff in one run), `wave-plan-admission.py admit` against a freshly captured snapshot,
`drift-classifier.py classify`, `auto-envelope.py define`, and `auto-envelope.py admit-transition`.
Every document is bound to the one before it by the digest that producer derived, so a fixture cannot
be a plausible-looking guess: the chain would refuse.

`SealedInjectionTests` RE-SEALS a real document after poisoning one field with a bare control
character, because every producer in this family validates its input and none of them will seal a
forged line for us; the re-seal uses this module's own `seal`, which is the same three lines the
producers use, so the document is genuinely sealed rather than merely claimed to be.

Every subprocess spawn in this module -- for the tool under test AND for every sibling fixture
producer -- goes through ONE constructed environment: an ALLOWLIST, not the ambient shell, mirroring
`test_mission_contract.py`'s `constructed_environment` (itself the same pattern
`test_wave_journal.py` establishes: never hand a spawned tool the developer's own shell).
"""

from __future__ import annotations

import ast
import ctypes
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

# `make_wave_journal` builds its fixture by RUNNING `wave-journal.py init`/`record-node`, and that
# publish refuses (by name, at exit 3) on a host that lacks this syscall -- so every test method that
# calls it is individually skipped there rather than failing downstream on the fixture it never got.
# On POSIX this is a pure SYMBOL probe, never `sys.platform`, so it can only be false on a host that
# genuinely lacks the syscall; glibc 2.28+ always exports it, so this is never false on the Linux CI
# runner this suite must stay green on. The `os.name` term answers the strictly earlier question of
# whether `ctypes.CDLL(None)` may be CALLED at all: on native Windows it may not (3.12's
# `CDLL.__init__` takes its `_os.name == "nt"` branch and evaluates `'/' in name` with `name=None`, a
# TypeError), and at module scope that would be a loader traceback for this whole file on the windows
# CI leg instead of a named skip. `RenameAt2CapabilityTests` below is this constant's own positive
# control.
_HAS_RENAMEAT2 = os.name == "posix" and getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None) is not None
_NEEDS_RENAMEAT2 = unittest.skipUnless(_HAS_RENAMEAT2, "Linux renameat2 is unavailable")

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


#: The wall-clock ceiling for one tool invocation in this module. It exists so a regressed guard
#: FAILS instead of HANGING: the two regular-file checks stand in front of a `read_bytes` and a
#: sibling spawn, and a FIFO with no writer blocks either one forever, so a test that just called
#: `subprocess.run` would wedge the whole suite rather than report the regression. Generous enough
#: that a loaded host is not a false failure -- one invocation takes well under a second and the whole
#: module runs in about 30s -- and short enough that a wedged guard reports quickly rather than looking
#: like a slow suite.
TOOL_TIMEOUT_SECONDS = 30


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def run(argv: list[str], *, cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    """Every spawn in this module is BOUNDED. An unbounded `subprocess.run` turns a regressed
    blocking-read guard into a hung suite -- no failure, no diagnostic, just a test run that never
    ends -- so `TOOL_TIMEOUT_SECONDS` is passed here rather than at individual call sites, and
    `subprocess.run` kills the child before re-raising."""
    return subprocess.run(
        argv,
        capture_output=True,
        cwd=str(cwd),
        check=False,
        env=constructed_environment(extra_env),
        timeout=TOOL_TIMEOUT_SECONDS,
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


def gate_receipt_canonical(value: Any) -> bytes:
    """`gate_receipt.canonical_json`, re-expressed (never imported), exactly as the tool under test
    re-expresses it: this family's canonical form with NO trailing newline."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def reseal_gate_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Re-derive a gate receipt's `self_digest` over an edited body.

    Used ONLY where `gate_receipt.py record` cannot be made to write the shape under test -- a bool
    `status`, an `outcome` its own `status` does not derive, an `argv` of null beside a verdict, a
    malformed failing set. Without the re-seal every such test would stop at the digest check and
    prove nothing about the clause it means to exercise; `test_the_reseal_helper_reproduces_a_real_
    receipts_own_digest` is the positive control that this really is the producer's derivation.
    """
    body = {key: value for key, value in receipt.items() if key != "self_digest"}
    resealed = dict(body)
    resealed["self_digest"] = hashlib.sha256(gate_receipt_canonical(body)).hexdigest()
    return resealed


def nested_json_document(depth: int) -> bytes:
    """One JSON document nesting `depth` containers, built ITERATIVELY -- a recursive builder would
    hit the same interpreter limit the tool under test is being asked to survive."""
    return ("[" * depth + "]" * depth).encode("utf-8")


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

    def run_without_wedging(self, guard: str, *argv: str) -> subprocess.CompletedProcess[bytes]:
        """Run the tool and turn a WEDGE into a named failure about the guard that should have
        prevented it. A blocking-read guard is the one kind whose regression a plain assertion cannot
        catch: there is no wrong answer to assert against, only an answer that never comes."""
        try:
            return self.run_tool(*argv)
        except subprocess.TimeoutExpired:
            self.fail(
                f"the tool produced no result within {TOOL_TIMEOUT_SECONDS}s: {guard} did not stop a "
                f"blocking read of {argv!r}"
            )

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
#: A green run that a HARNESS can be identified from: `gate_receipt.py` reads a unittest summary line
#: and records `state: exact` with an EMPTY failing set, which is what makes a passing receipt
#: baselinable at all. `PASSING_SCRIPT` prints nothing, so its failing set is `unparsed` -- and
#: `gate_baseline.py` refuses an unparsed set rather than treating it as empty, which is the whole
#: point of that state.
PASSING_UNITTEST_SCRIPT = (
    "import sys\n"
    "print('Ran 1 test in 0.001s')\n"
    "print('OK')\n"
    "sys.exit(0)\n"
)
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
    @_NEEDS_RENAMEAT2
    def test_a_complete_wave_journal_is_projected_and_reported_complete(self) -> None:
        journal = self.make_wave_journal(complete=True)
        document = self.document("--wave-journal", str(journal))
        section = document["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertEqual(section["wave_id"], "wave-1")
        self.assertTrue(section["complete"])
        self.assertEqual(section["required_nodes_without_disposition"], [])
        self.assertEqual(document["bluf"], "wave wave-1: every required node carries a disposition")

    @_NEEDS_RENAMEAT2
    def test_an_incomplete_wave_journal_names_the_missing_node(self) -> None:
        journal = self.make_wave_journal(complete=False)
        document = self.document("--wave-journal", str(journal))
        section = document["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertFalse(section["complete"])
        self.assertEqual(section["required_nodes_without_disposition"], ["implement-b"])
        self.assertIn("implement-b", document["bluf"])
        self.assertIn("1 required node(s) missing a disposition", document["bluf"])

    @_NEEDS_RENAMEAT2
    def test_a_directory_supplied_as_the_wave_journal_is_unreadable(self) -> None:
        # POSITIVE CONTROL: a real journal at a sibling path projects fine.
        journal = self.make_wave_journal(complete=True)
        self.assertEqual(self.document("--wave-journal", str(journal))["artifacts"]["wave_journal"]["presence"], PRESENT)
        adir = self.work / "adir"
        adir.mkdir()
        section = self.document("--wave-journal", str(adir))["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not a regular file", section["reason"])

    @_NEEDS_RENAMEAT2
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

    @_NEEDS_RENAMEAT2
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
        writer shows up, which here would be never, so a wrong-shape path must be named `unreadable`
        in an exit-0 document promptly rather than hang this read-only query forever.

        The spawn is BOUNDED (`run`'s `TOOL_TIMEOUT_SECONDS`) and the timeout is turned into a named
        failure here. Before that, this test proved less than it looked: delete the regular-file check
        and it did not fail, it HUNG -- the tool blocked forever on `read_bytes` and took the suite
        with it, so the guard's regression produced no verdict at all instead of a red test.
        """
        fifo = self.work / "fifo"
        os.mkfifo(fifo)
        done = self.run_without_wedging(
            "the regular-file check in _read_json_object",
            "--gate-receipt",
            str(fifo),
            "--json",
        )
        self.assertEqual(done.returncode, EXIT_OK)
        section = json.loads(done.stdout)["artifacts"]["gate"]["receipt"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not a regular file", section["reason"])
        # POSITIVE CONTROL: the same flag over a REGULAR file at the same shape gets past the check
        # and is judged on its contents instead, so the assertion above is about the file's KIND.
        regular = self.work / "regular.json"
        regular.write_text("{}", encoding="utf-8")
        control = self.document("--gate-receipt", str(regular))["artifacts"]["gate"]["receipt"]
        self.assertEqual(control["presence"], UNREADABLE)
        self.assertNotIn("not a regular file", control["reason"])

    @unittest.skipUnless(os.name == "posix", "os.mkfifo is POSIX-only")
    def test_a_fifo_supplied_as_the_wave_journal_is_unreadable_and_does_not_hang(self) -> None:
        """The SECOND regular-file check, in front of the one sibling spawn. Without it the FIFO path
        is handed to `wave-journal.py project`, which opens it and blocks on a writer that never
        arrives -- and this module's own 30-second subprocess timeout would then be the only thing
        between a read-only query and a wedged caller."""
        fifo = self.work / "journal-fifo"
        os.mkfifo(fifo)
        done = self.run_without_wedging(
            "the regular-file check in build_wave_journal_section",
            "--wave-journal",
            str(fifo),
            "--json",
        )
        self.assertEqual(done.returncode, EXIT_OK)
        section = json.loads(done.stdout)["artifacts"]["wave_journal"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not a regular file", section["reason"])
        # POSITIVE CONTROL: a REGULAR file at the same flag reaches the sibling and is judged on its
        # contents, so the refusal above is about the path's kind and not about the flag itself.
        regular = self.work / "regular-journal.ndjson"
        regular.write_text("not a ledger\n", encoding="utf-8")
        control = self.document("--wave-journal", str(regular))["artifacts"]["wave_journal"]
        self.assertEqual(control["presence"], UNREADABLE)
        self.assertNotIn("not a regular file", control["reason"])

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

    @_NEEDS_RENAMEAT2
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

    @_NEEDS_RENAMEAT2
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

    @_NEEDS_RENAMEAT2
    def test_gate_outranks_runtime_assignment_and_wave_journal(self) -> None:
        journal = self.make_wave_journal(complete=False)
        report = self.make_classification(served_model="claude-opus-4-8")
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        document = self.document(
            "--wave-journal", str(journal), "--runtime-assignment", str(report), "--gate-receipt", str(receipt),
        )
        self.assertIn("gate smoke", document["bluf"])

    @_NEEDS_RENAMEAT2
    def test_runtime_assignment_outranks_wave_journal(self) -> None:
        journal = self.make_wave_journal(complete=False)
        report = self.make_classification(served_model="claude-opus-4-8")
        document = self.document("--wave-journal", str(journal), "--runtime-assignment", str(report))
        self.assertIn("runtime-assignment", document["bluf"])

    @_NEEDS_RENAMEAT2
    def test_wave_journal_is_the_bluf_when_it_is_the_only_input(self) -> None:
        journal = self.make_wave_journal(complete=False)
        document = self.document("--wave-journal", str(journal))
        self.assertIn("wave wave-1", document["bluf"])

    @_NEEDS_RENAMEAT2
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

    @_NEEDS_RENAMEAT2
    def test_the_whole_ladder_is_walked_once_from_the_bottom_up(self) -> None:
        argv: list[str] = []
        for kind, flags, fragment in self._ladder():
            argv += flags
            with self.subTest(newly_added=kind):
                document = self.document(*argv)
                self.assertIn(fragment, document["bluf"], f"{kind} did not take over the headline")

    def test_a_blocked_admission_report_outranks_the_gate_and_the_drift_classification(self) -> None:
        """The high admission rung, and the only case the published rationale justifies: "this wave may
        not start" subsumes what its plan then drifted into and whether the repository's gate passed."""
        document = self.document(
            "--gate-receipt", str(self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)),
            "--drift-classification", str(self.fixture("classification")),
            "--wave-plan-admission", str(self.fixture("admission_blocked")),
        )
        self.assertIn("wave plan admission disposition: blocked", document["bluf"])

    def test_an_admitted_admission_report_does_not_headline_over_a_drift_classification(self) -> None:
        """The rung the review reconsidered. `admitted` PERMITS this wave to start; the report itself
        says `admitted` is not `approved`, so it subsumes neither a replan-required drift classification
        (the plan the wave is running is no longer that plan) nor the repository's own gate. Under the
        original single rung the projection headlined "admission disposition: admitted" and left a
        hard-stop-class drift outcome to be discovered further down the page."""
        document = self.document(
            "--drift-classification", str(self.fixture("classification")),
            "--wave-plan-admission", str(self.fixture("admission")),
        )
        self.assertIn("drift classification overall outcome: replan-required", document["bluf"])
        self.assertNotIn("admission", document["bluf"])
        # POSITIVE CONTROL for the direction of the split: the SAME two flags with the BLOCKED report
        # do headline the admission, so this is about the disposition and not about the flag's rank.
        blocked = self.document(
            "--drift-classification", str(self.fixture("classification")),
            "--wave-plan-admission", str(self.fixture("admission_blocked")),
        )
        self.assertIn("wave plan admission disposition: blocked", blocked["bluf"])

    def test_an_admitted_admission_report_does_not_headline_over_the_gate_either(self) -> None:
        document = self.document(
            "--gate-receipt", str(self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)),
            "--wave-plan-admission", str(self.fixture("admission")),
        )
        self.assertIn("gate smoke", document["bluf"])

    def test_an_admitted_admission_report_still_outranks_a_runtime_assignment(self) -> None:
        """The low rung is a rung, not a deletion: admitting a whole wave plan is still wider than one
        node's spawn, so `admitted` headlines over everything below `gate`."""
        document = self.document(
            "--runtime-assignment", str(self.make_classification(served_model="claude-opus-4-8")),
            "--wave-plan-admission", str(self.fixture("admission")),
        )
        self.assertIn("wave plan admission disposition: admitted", document["bluf"])

    def test_an_admitted_admission_report_headlines_when_it_is_the_only_input(self) -> None:
        """POSITIVE CONTROL that the low rung really is reachable: dropping `admitted` out of the high
        rung must not make it unable to headline at all."""
        document = self.document("--wave-plan-admission", str(self.fixture("admission")))
        self.assertIn("wave plan admission disposition: admitted", document["bluf"])

    def test_an_unreadable_admission_report_keeps_the_high_rung(self) -> None:
        """An unreadable report has no disposition to read, so it cannot be sorted by one: it stays at
        the rung its kind earns, exactly like every other unreadable input."""
        broken = self.work / "broken-disposition.json"
        document = self.read(self.copy_of("admission", as_name="src.json"))
        document["disposition"] = "deferred"
        broken.write_bytes(canonical(seal(document)))
        projected = self.document(
            "--drift-classification", str(self.fixture("classification")), "--wave-plan-admission", str(broken)
        )
        self.assertIn("the wave plan admission report is unreadable", projected["bluf"])

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

    @_NEEDS_RENAMEAT2
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
        # argparse RE-WRAPS the epilog to the terminal width it infers, so a multi-word phrase is
        # asserted against whitespace-normalised help: a sentence that reads correctly must not fail
        # this test because a wrap landed mid-phrase, and must not pass it by being absent either.
        flowed = " ".join(text.split())
        self.assertIn("--wave-journal", text)
        self.assertIn("3 and 4 do not apply", flowed)
        self.assertIn("INCLUDING one artifact flag given more than once", flowed)
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

    @_NEEDS_RENAMEAT2
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

    @_NEEDS_RENAMEAT2
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

    @_NEEDS_RENAMEAT2
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

    def test_a_newline_in_an_unvalidated_pass_through_field_cannot_forge_a_line(self) -> None:
        """The fields this module carries through WITHOUT validating -- an assignment's `may_spawn` and
        `blocks_wave_completion`, an activation result's `gate_passes` -- are normally a bool or null, so
        a renderer can look safe while interpolating them bare. They are read off a document, so they
        can be a string with a control character in it, and the human view renders them on the same
        line as fields a reader trusts."""
        report = self.make_admission()
        document = json.loads(report.read_text(encoding="utf-8"))
        document["may_spawn"] = "true\ninjected: forged permission line"
        report.write_text(json.dumps(document), encoding="utf-8")
        # POSITIVE CONTROL: the raw control character really does reach the projection.
        projected = self.document("--runtime-assignment", str(report))
        self.assertEqual(projected["artifacts"]["runtime_assignment"]["may_spawn"], document["may_spawn"])
        text = self.human("--runtime-assignment", str(report))
        for line in text.splitlines():
            self.assertFalse(line.startswith("injected:"), f"a forged line leaked: {line!r}")
        self.assertIn("may_spawn=true\\ninjected: forged permission line", text)

    def test_a_newline_in_an_activation_gate_pass_count_cannot_forge_a_line(self) -> None:
        body = {
            "schema": "agentic-sdlc/activation-terminal-state@1",
            "state": "refused",
            "consequence": "no wave may write",
            "target": "/repo",
            "gate_outcome": None,
            "gate_passes": "2\ninjected: forged pass count",
            "reasons": [],
        }
        path = self.work / "hostile-gate-passes.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        self.assertEqual(
            self.document("--activation-result", str(path))["artifacts"]["activation_result"]["gate_passes"],
            body["gate_passes"],
        )
        text = self.human("--activation-result", str(path))
        for line in text.splitlines():
            self.assertFalse(line.startswith("injected:"), f"a forged line leaked: {line!r}")
        self.assertIn("gate_passes=2\\ninjected: forged pass count", text)

    def test_a_newline_in_an_activation_reason_cannot_forge_a_line_either(self) -> None:
        """The same hazard through a different artifact kind and a different render_human branch
        (the per-reason loop), using a HAND-WRITTEN activation result for the same bounded-scope
        reason `ActivationResultTests` states."""
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


class GateBlufOrderingTests(ProjectionCase):
    """The gate rung's own two-leaf order, and what its headline actually claims.

    Two defects lived here. An UNREADABLE receipt beside a PRESENT comparison was silently dropped from
    the headline -- the comparison won, so the one input the module could not verify went unmentioned in
    the only line a reader is guaranteed to read. And a FAILED gate whose every failure is pre-existing
    headlined as "non-worsening" with no word about the failure, because `non_worsening` answers "did
    this change break something NEW", never "did the gate pass".
    """

    def _failing_pair(self, *, worse: bool = False) -> tuple[Path, Path]:
        baseline_receipt = self.make_gate_receipt(
            name="baseline.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        candidate_receipt = self.make_gate_receipt(
            name="candidate.json",
            gate="fake gate",
            script=FAILING_UNITTEST_SCRIPT_TWO if worse else FAILING_UNITTEST_SCRIPT,
            harness_unittest=True,
        )
        comparison = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=candidate_receipt)
        return candidate_receipt, comparison

    def test_an_unreadable_receipt_is_named_ahead_of_a_present_comparison(self) -> None:
        _candidate, comparison = self._failing_pair()
        broken = self.work / "broken-receipt.json"
        broken.write_text("{not json", encoding="utf-8")
        document = self.document("--gate-receipt", str(broken), "--gate-baseline", str(comparison))
        self.assertIn("the gate receipt is unreadable", document["bluf"])
        # The comparison is still projected in full below the headline: the rung's order decides which
        # fact leads, never which facts are recorded.
        self.assertEqual(document["artifacts"]["gate"]["baseline"]["presence"], PRESENT)

    def test_a_readable_receipt_lets_the_comparison_headline(self) -> None:
        """POSITIVE CONTROL: the receipt does not always win. With a receipt this module CAN read, the
        richer comparison line is the headline, which is what makes the assertion above about
        `unreadable` rather than about the leaf order alone."""
        candidate, comparison = self._failing_pair()
        document = self.document("--gate-receipt", str(candidate), "--gate-baseline", str(comparison))
        self.assertIn("non-worsening against its baseline", document["bluf"])
        self.assertNotIn("unreadable", document["bluf"])

    def test_an_unreadable_comparison_is_still_named_when_the_receipt_reads(self) -> None:
        candidate, _comparison = self._failing_pair()
        broken = self.work / "broken-comparison.json"
        broken.write_text("{not json", encoding="utf-8")
        document = self.document("--gate-receipt", str(candidate), "--gate-baseline", str(broken))
        self.assertIn("the gate baseline comparison is unreadable", document["bluf"])

    def test_a_failed_gate_with_only_pre_existing_failures_says_it_failed(self) -> None:
        """The honesty defect. Both receipts are real `gate_receipt.py` records of a really-failing
        harness naming the SAME one test, so `newly_failing` is empty and `non_worsening` is true --
        while `candidate_outcome` is `failed`. The headline has to carry both."""
        candidate, comparison = self._failing_pair()
        document = self.document("--gate-receipt", str(candidate), "--gate-baseline", str(comparison))
        baseline = document["artifacts"]["gate"]["baseline"]
        # POSITIVE CONTROL: this fixture really is the awkward case -- failed AND non-worsening.
        self.assertEqual(baseline["candidate_outcome"], "failed")
        self.assertTrue(baseline["non_worsening"])
        self.assertEqual(baseline["newly_failing"], [])
        self.assertIn("candidate outcome failed", document["bluf"])
        self.assertIn("non-worsening", document["bluf"])

    def test_a_passing_pair_headlines_as_passed(self) -> None:
        """POSITIVE CONTROL for the word above: a comparison over two PASSING receipts says `passed`, so
        `candidate outcome failed` is read off the document rather than printed unconditionally.

        Both receipts are recorded with `--harness unittest`: `gate_baseline.py` refuses a receipt that
        records no failing set at all ("it was never baselined"), and a passing run under that harness
        records an EMPTY one, which is a different thing from an absent one.
        """
        baseline_receipt = self.make_gate_receipt(
            name="b.json", gate="smoke", script=PASSING_UNITTEST_SCRIPT, harness_unittest=True
        )
        candidate_receipt = self.make_gate_receipt(
            name="c.json", gate="smoke", script=PASSING_UNITTEST_SCRIPT, harness_unittest=True
        )
        comparison = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=candidate_receipt)
        document = self.document("--gate-receipt", str(candidate_receipt), "--gate-baseline", str(comparison))
        self.assertIn("candidate outcome passed", document["bluf"])

    def test_a_worsened_pair_still_names_the_worsening(self) -> None:
        candidate, comparison = self._failing_pair(worse=True)
        document = self.document("--gate-receipt", str(candidate), "--gate-baseline", str(comparison))
        self.assertIn("WORSENED against its baseline", document["bluf"])
        self.assertIn("1 newly failing", document["bluf"])


class GateReceiptShapeTests(ProjectionCase):
    """Every clause of `_validate_gate_receipt_shape` that no other test reached.

    `gate_receipt.py record` will not WRITE most of these shapes -- that is the point of validating them
    -- so each row edits a real receipt and RE-SEALS it with the producer's own derivation. Without the
    re-seal every row would stop at the digest clause and prove nothing about the clause it names.
    """

    def receipt(self) -> dict[str, Any]:
        """One real receipt per TEST, re-parsed per call. `gate_receipt.py record` refuses to overwrite
        existing evidence -- correctly -- so a row that re-ran the producer under the same name would
        fail on that refusal instead of on the clause it means to exercise."""
        if getattr(self, "_receipt_text", None) is None:
            path = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
            self._receipt_text = path.read_text(encoding="utf-8")
        return json.loads(self._receipt_text)

    def project(self, receipt: dict[str, Any], *, name: str = "edited.json") -> dict[str, Any]:
        path = self.work / name
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return self.document("--gate-receipt", str(path))["artifacts"]["gate"]["receipt"]

    def test_the_reseal_helper_reproduces_a_real_receipts_own_digest(self) -> None:
        """POSITIVE CONTROL for the helper every row below depends on: re-sealing an UNEDITED receipt
        must reproduce the digest `gate_receipt.py record` itself wrote. If it did not, every row below
        would be testing this module's arithmetic instead of the tool's clause."""
        original = self.receipt()
        self.assertEqual(reseal_gate_receipt(original)["self_digest"], original["self_digest"])
        self.assertEqual(self.project(original, name="unedited.json")["presence"], PRESENT)

    def test_an_extra_key_is_unreadable(self) -> None:
        receipt = self.receipt()
        receipt["extra_field"] = "not a gate receipt's field"
        section = self.project(reseal_gate_receipt(receipt))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("does not carry exactly a gate receipt's fields", section["reason"])

    def test_a_non_string_self_digest_is_unreadable(self) -> None:
        receipt = self.receipt()
        receipt["self_digest"] = 12345
        section = self.project(receipt)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("self_digest that is not a string", section["reason"])

    def test_a_boolean_status_is_unreadable_rather_than_read_as_one(self) -> None:
        """`True == 1` in Python, so a bool `status` would sail through the outcome-derives clause and be
        projected as a real exit status. `isinstance(status, bool)` is the only thing between a receipt
        that says `true` and a projection that says the gate ran and failed."""
        receipt = self.receipt()
        receipt["status"] = True
        receipt["outcome"] = "failed"
        section = self.project(reseal_gate_receipt(receipt))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("status that is neither an integer nor null", section["reason"])
        # POSITIVE CONTROL: the same receipt with the INTEGER 1 is read, so the refusal is about the
        # bool and not about the value 1 or about the word `failed`.
        receipt["status"] = 1
        allowed = self.project(reseal_gate_receipt(receipt), name="int-status.json")
        self.assertEqual(allowed["presence"], PRESENT, allowed.get("reason"))
        self.assertEqual(allowed["gate_status"], 1)
        self.assertEqual(allowed["outcome"], "failed")

    def test_an_outcome_its_own_status_does_not_derive_is_unreadable(self) -> None:
        receipt = self.receipt()
        self.assertEqual(receipt["status"], 0)  # POSITIVE CONTROL: the fixture really passed
        receipt["outcome"] = "failed"
        section = self.project(reseal_gate_receipt(receipt))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("does not derive", section["reason"])

    def test_an_unobserved_gate_is_projected_as_unobserved_not_as_failed(self) -> None:
        """`_derive_gate_outcome(None)` is `unobserved`, and that is a THIRD answer, not a synonym for
        failure: nothing ran, so nothing failed. Drop the null branch and this same receipt reads as a
        receipt whose `outcome` its `status` does not derive."""
        receipt = self.receipt()
        receipt["argv"] = None
        receipt["status"] = None
        receipt["signal"] = None
        receipt["outcome"] = "unobserved"
        section = self.project(reseal_gate_receipt(receipt))
        self.assertEqual(section["presence"], PRESENT, section.get("reason"))
        self.assertEqual(section["outcome"], "unobserved")
        self.assertFalse(section["ran"])
        self.assertIsNone(section["gate_status"])

    def test_a_verdict_with_nothing_executed_is_unreadable(self) -> None:
        receipt = self.receipt()
        receipt["argv"] = None
        section = self.project(reseal_gate_receipt(receipt))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("claims a verdict although nothing was executed", section["reason"])

    def test_a_failing_set_with_the_wrong_keys_is_unreadable(self) -> None:
        receipt = self.receipt()
        receipt["failures"] = {"harness": "unittest", "names": ["a"]}
        section = self.project(reseal_gate_receipt(receipt))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("failing set that is not exactly", section["reason"])

    def test_a_failing_set_whose_names_are_not_strings_is_unreadable(self) -> None:
        receipt = self.receipt()
        receipt["failures"] = {"harness": "unittest", "state": "exact", "names": ["a", 7]}
        section = self.project(reseal_gate_receipt(receipt))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("names are not a list of strings", section["reason"])
        # POSITIVE CONTROL: the same failing set with STRING names is read, and its count is projected.
        receipt["failures"] = {"harness": "unittest", "state": "exact", "names": ["a", "b"]}
        allowed = self.project(reseal_gate_receipt(receipt), name="string-names.json")
        self.assertEqual(allowed["presence"], PRESENT, allowed.get("reason"))
        self.assertEqual(allowed["failing_test_count"], 2)
        self.assertEqual(allowed["failing_set_state"], "exact")


class GateBaselineShapeTests(ProjectionCase):
    """Every clause of `_validate_gate_baseline_shape`. A comparison document carries no digest of its
    own, so these rows are plain edits of a real `gate_baseline.py compare` report."""

    def comparison(self) -> dict[str, Any]:
        """One real comparison per TEST, re-parsed per call -- see `GateReceiptShapeTests.receipt`."""
        if getattr(self, "_comparison_text", None) is None:
            baseline_receipt = self.make_gate_receipt(
                name="baseline.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
            )
            candidate_receipt = self.make_gate_receipt(
                name="candidate.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT_TWO, harness_unittest=True
            )
            path = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=candidate_receipt)
            self._comparison_text = path.read_text(encoding="utf-8")
        return json.loads(self._comparison_text)

    def project(self, comparison: dict[str, Any], *, name: str = "edited.json") -> dict[str, Any]:
        path = self.work / name
        path.write_text(json.dumps(comparison), encoding="utf-8")
        return self.document("--gate-baseline", str(path))["artifacts"]["gate"]["baseline"]

    def test_the_untouched_comparison_is_present(self) -> None:
        """POSITIVE CONTROL for every row below."""
        section = self.project(self.comparison(), name="unedited.json")
        self.assertEqual(section["presence"], PRESENT, section.get("reason"))

    def test_a_missing_required_field_is_unreadable_by_name(self) -> None:
        for key in ("gate", "baseline_outcome", "candidate_outcome"):
            with self.subTest(missing=key):
                comparison = self.comparison()
                del comparison[key]
                section = self.project(comparison, name=f"no-{key}.json")
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn(f"carries no {key}", section["reason"])

    def test_a_set_field_that_is_not_a_list_of_strings_is_unreadable_by_name(self) -> None:
        for key in ("baseline_failing", "candidate_failing", "newly_failing", "fixed", "still_failing"):
            for bad, description in ((["a", 7], "a non-string member"), ("a", "a bare string")):
                with self.subTest(field=key, bad=description):
                    comparison = self.comparison()
                    comparison[key] = bad
                    section = self.project(comparison, name=f"bad-{key}.json")
                    self.assertEqual(section["presence"], UNREADABLE)
                    self.assertIn(f"carries a {key} that is not a list of strings", section["reason"])

    def test_a_non_boolean_verdict_field_is_unreadable_by_name(self) -> None:
        for key in ("non_worsening", "toolchain_drifted"):
            for bad in ("true", 1, None):
                with self.subTest(field=key, bad=bad):
                    comparison = self.comparison()
                    comparison[key] = bad
                    section = self.project(comparison, name=f"bad-{key}.json")
                    self.assertEqual(section["presence"], UNREADABLE)
                    self.assertIn(f"carries a {key} that is not a boolean", section["reason"])

    def test_toolchain_drift_is_projected_in_both_views_rather_than_dropped(self) -> None:
        """`toolchain_drifted` is the field a reader most needs and the one the human view used to
        omit: "green on drifted pins" is a real reading, and it cannot be read off a page that does not
        print it."""
        comparison = self.comparison()
        comparison["toolchain_drifted"] = True
        path = self.work / "drifted.json"
        path.write_text(json.dumps(comparison), encoding="utf-8")
        document = self.document("--gate-baseline", str(path))
        self.assertTrue(document["artifacts"]["gate"]["baseline"]["toolchain_drifted"])
        self.assertIn("toolchain_drifted=True", self.human("--gate-baseline", str(path)))


class GateBaselineConsistencyTests(ProjectionCase):
    """The comparison's own CROSS-FIELD arithmetic. `gate_baseline.py compare` derives `newly_failing`,
    `fixed`, `still_failing`, and `non_worsening` from its two failing sets, so a document whose derived
    fields its own listed names deny is a document that tool did not write -- and a subset claim is
    exactly the kind of fact that must not be projected on trust."""

    def comparison(self) -> dict[str, Any]:
        """One real comparison per TEST, re-parsed per call -- see `GateReceiptShapeTests.receipt`."""
        if getattr(self, "_comparison_text", None) is None:
            baseline_receipt = self.make_gate_receipt(
                name="baseline.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
            )
            candidate_receipt = self.make_gate_receipt(
                name="candidate.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT_TWO, harness_unittest=True
            )
            path = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=candidate_receipt)
            self._comparison_text = path.read_text(encoding="utf-8")
        return json.loads(self._comparison_text)

    def project(self, comparison: dict[str, Any], *, name: str = "edited.json") -> dict[str, Any]:
        path = self.work / name
        path.write_text(json.dumps(comparison), encoding="utf-8")
        return self.document("--gate-baseline", str(path))["artifacts"]["gate"]["baseline"]

    def test_a_real_comparison_satisfies_every_clause(self) -> None:
        """POSITIVE CONTROL: the producer's own output passes, so these clauses re-express its
        arithmetic rather than inventing a stricter document than it writes."""
        comparison = self.comparison()
        section = self.project(comparison, name="unedited.json")
        self.assertEqual(section["presence"], PRESENT, section.get("reason"))
        self.assertEqual(comparison["newly_failing"], ["mypkg.test_mod.MyCase.test_two"])

    def test_an_emptied_newly_failing_set_is_unreadable(self) -> None:
        """The dangerous edit, and the reason this clause exists: blanking `newly_failing` on a
        WORSENED comparison is how a document would claim a regression away."""
        comparison = self.comparison()
        comparison["newly_failing"] = []
        comparison["non_worsening"] = True
        section = self.project(comparison)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("records a newly_failing its own candidate_failing and baseline_failing", section["reason"])

    def test_a_fixed_set_its_own_failing_sets_do_not_derive_is_unreadable(self) -> None:
        comparison = self.comparison()
        comparison["fixed"] = ["mypkg.test_mod.MyCase.test_one"]
        section = self.project(comparison)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("records a fixed its own baseline_failing and candidate_failing", section["reason"])

    def test_a_still_failing_set_its_own_failing_sets_do_not_derive_is_unreadable(self) -> None:
        comparison = self.comparison()
        comparison["still_failing"] = []
        section = self.project(comparison)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("records a still_failing", section["reason"])

    def test_a_non_worsening_flag_its_own_newly_failing_set_denies_is_unreadable(self) -> None:
        comparison = self.comparison()
        comparison["non_worsening"] = True
        section = self.project(comparison)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("records non_worsening True beside 1 newly failing test(s)", section["reason"])

    def test_a_worsening_flag_over_an_empty_newly_failing_set_is_also_unreadable(self) -> None:
        """The other direction, so the clause is an equality and not a one-way check: a comparison may
        not claim worsening its own empty set denies either."""
        baseline_receipt = self.make_gate_receipt(
            name="b.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        candidate_receipt = self.make_gate_receipt(
            name="c.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        path = self.make_gate_baseline(name="same.json", baseline=baseline_receipt, candidate=candidate_receipt)
        comparison = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(comparison["newly_failing"], [])  # POSITIVE CONTROL: really non-worsening
        comparison["non_worsening"] = False
        section = self.project(comparison, name="claims-worsening.json")
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("records non_worsening False beside 0 newly failing test(s)", section["reason"])

    def test_a_reordered_derived_set_is_unreadable(self) -> None:
        """`compare` emits `sorted(...)`, so ORDER is part of the arithmetic: comparing the derived LIST
        rather than a set catches a reordered or duplicate-bearing document too. The comparison here is
        against a PASSING baseline, so `newly_failing` has two names and can be reordered at all."""
        baseline_receipt = self.make_gate_receipt(
            name="pass-baseline.json", gate="fake gate", script=PASSING_UNITTEST_SCRIPT, harness_unittest=True
        )
        candidate_receipt = self.make_gate_receipt(
            name="two-failures.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT_TWO, harness_unittest=True
        )
        path = self.make_gate_baseline(name="two.json", baseline=baseline_receipt, candidate=candidate_receipt)
        comparison = json.loads(path.read_text(encoding="utf-8"))
        # POSITIVE CONTROL: the untouched two-name comparison is present and sorted.
        self.assertEqual(
            comparison["newly_failing"], ["mypkg.test_mod.MyCase.test_one", "mypkg.test_mod.MyCase.test_two"]
        )
        self.assertEqual(self.project(comparison, name="sorted.json")["presence"], PRESENT)
        comparison["newly_failing"] = list(reversed(comparison["newly_failing"]))
        section = self.project(comparison, name="reordered.json")
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("do not derive", section["reason"])

    def test_a_duplicated_name_in_a_derived_set_is_unreadable(self) -> None:
        """The same clause from the other side: `sorted(set(...))` cannot emit a repeat, so a repeat is
        a document `compare` did not write."""
        comparison = self.comparison()
        comparison["newly_failing"] = comparison["newly_failing"] * 2
        section = self.project(comparison, name="duplicated.json")
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("do not derive", section["reason"])


class WaveJournalSiblingContractTests(ProjectionCase):
    """The ONE input this module re-derives by INVOKING a sibling, and every clause it checks that
    sibling's stdout against.

    No real `wave-journal.py` can be made to emit a wrong schema, an empty stdout, or non-UTF-8 bytes --
    which is exactly why those clauses exist and exactly why no test reached them. So the tool under test
    is COPIED into a scratch directory beside a STUB `wave-journal.py`, because it resolves that sibling
    from its own file's directory (`Path(__file__).resolve().parent`), never from PATH or the caller's
    cwd. The copy is byte-identical -- `test_the_copy_is_byte_identical_to_the_shipped_tool` is the
    positive control -- so what is under test is still the shipped module.
    """

    def install_stub(self, body: str) -> Path:
        tools = self.work / "tools"
        tools.mkdir(exist_ok=True)
        copied = tools / TOOL.name
        copied.write_bytes(TOOL.read_bytes())
        (tools / "wave-journal.py").write_text(body, encoding="utf-8")
        return copied

    def project_with_stub(self, body: str) -> dict[str, Any]:
        copied = self.install_stub(body)
        journal = self.work / "journal.ndjson"
        journal.write_text('{"any": "bytes"}\n', encoding="utf-8")
        done = run([sys.executable, "-B", str(copied), "--wave-journal", str(journal), "--json"], cwd=self.work)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        return json.loads(done.stdout)["artifacts"]["wave_journal"]

    def test_the_copy_is_byte_identical_to_the_shipped_tool(self) -> None:
        copied = self.install_stub("import sys\nsys.exit(0)\n")
        self.assertEqual(copied.read_bytes(), TOOL.read_bytes())

    def test_a_wrong_projection_schema_is_unreadable(self) -> None:
        section = self.project_with_stub(
            "import json, sys\n"
            "print(json.dumps({'schema': 'agentic-sdlc/wave-journal-projection@2', 'status': 'ok',\n"
            "                  'required_nodes': [], 'required_nodes_without_disposition': []}))\n"
            "sys.exit(0)\n"
        )
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("emitted schema 'agentic-sdlc/wave-journal-projection@2'", section["reason"])

    def test_the_expected_projection_schema_is_accepted(self) -> None:
        """POSITIVE CONTROL for the row above AND for the whole stub technique: with the DECLARED schema
        the same stub is projected as present, so every refusal in this class is about the clause it
        names and not about the substitution itself."""
        section = self.project_with_stub(
            "import json, sys\n"
            "print(json.dumps({'schema': 'agentic-sdlc/wave-journal-projection@1', 'wave_id': 'wave-stub',\n"
            "                  'required_nodes': ['a'], 'required_nodes_without_disposition': []}))\n"
            "sys.exit(0)\n"
        )
        self.assertEqual(section["presence"], PRESENT, section.get("reason"))
        self.assertEqual(section["wave_id"], "wave-stub")
        self.assertTrue(section["complete"])

    def test_an_empty_stdout_is_unreadable(self) -> None:
        section = self.project_with_stub("import sys\nsys.exit(0)\n")
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("produced no output", section["reason"])

    def test_a_whitespace_only_stdout_is_unreadable(self) -> None:
        """`strip()` and not `if not text`: a stdout of one newline is as empty as no stdout at all."""
        section = self.project_with_stub("import sys\nsys.stdout.write('\\n   \\n')\nsys.exit(0)\n")
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("produced no output", section["reason"])

    def test_a_non_utf8_stdout_is_unreadable(self) -> None:
        section = self.project_with_stub(
            "import sys\nsys.stdout.buffer.write(b'\\xff\\xfe not utf-8')\nsys.exit(0)\n"
        )
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not UTF-8", section["reason"])

    def test_a_non_json_stdout_is_unreadable(self) -> None:
        section = self.project_with_stub("import sys\nprint('not json at all')\nsys.exit(0)\n")
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("is not JSON", section["reason"])

    def test_a_json_array_stdout_is_unreadable(self) -> None:
        section = self.project_with_stub("import sys\nprint('[]')\nsys.exit(0)\n")
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("not a JSON object", section["reason"])

    def test_required_node_fields_that_are_not_lists_are_unreadable(self) -> None:
        """`len()` over whatever arrived would happily count a string's characters, so "how many required
        nodes" would become "how many letters" -- a projected number with no meaning."""
        section = self.project_with_stub(
            "import json, sys\n"
            "print(json.dumps({'schema': 'agentic-sdlc/wave-journal-projection@1',\n"
            "                  'required_nodes': 'abc', 'required_nodes_without_disposition': 'de'}))\n"
            "sys.exit(0)\n"
        )
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("own required-node fields are not lists", section["reason"])

    def test_a_nonzero_exit_is_reported_with_the_siblings_own_reasons(self) -> None:
        section = self.project_with_stub(
            "import json, sys\n"
            "print(json.dumps({'schema': 'agentic-sdlc/wave-journal-projection@1', 'status': 'refused',\n"
            "                  'reasons': ['the ledger chain broke at entry 4'],\n"
            "                  'required_nodes': [], 'required_nodes_without_disposition': []}))\n"
            "sys.exit(5)\n"
        )
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("reported 'refused'", section["reason"])
        self.assertIn("the ledger chain broke at entry 4", section["reason"])

    def test_a_deeply_nested_stdout_is_unreadable_rather_than_a_crash(self) -> None:
        """The nesting ceiling guards the SIBLING's stdout too: this module parses that stream, so a
        sibling emitting 2000 nested containers must cost its own section and nothing more."""
        section = self.project_with_stub(
            "import sys\nprint('[' * 2000 + ']' * 2000)\nsys.exit(0)\n"
        )
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("nests JSON containers deeper than", section["reason"])


class RuntimeAssignmentFieldTests(ProjectionCase):
    """The two `build_runtime_assignment_section` clauses no other test reached: a `consequence` that is
    not a string, and the command split that decides which of `may_spawn` / `blocks_wave_completion`
    belongs to which report shape. Runtime-assignment reports carry no digest, so these are plain
    edits of a real report."""

    def test_a_non_string_consequence_is_projected_as_null(self) -> None:
        report = self.make_classification()
        document = json.loads(report.read_text(encoding="utf-8"))
        # POSITIVE CONTROL: the real report's consequence IS a string, and it is projected verbatim.
        self.assertIsInstance(document["consequence"], str)
        self.assertEqual(
            self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]["consequence"],
            document["consequence"],
        )
        document["consequence"] = {"not": "a sentence"}
        report.write_text(json.dumps(document), encoding="utf-8")
        section = self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], PRESENT)
        self.assertIsNone(section["consequence"], "a consequence that is not a sentence must not be projected as one")

    def test_a_classification_never_projects_a_may_spawn_it_carries(self) -> None:
        """`may_spawn` is the ADMIT verb's answer. A classification report that carries the key anyway
        must not have it projected: "this node may spawn" is a permission, and reading one off the wrong
        report shape is manufacturing it."""
        # An UNEXPLAINED substitution, so the report's own `blocks_wave_completion` is `true` and the
        # assertion below distinguishes "the classify field was projected" from "every field is null".
        report = self.make_classification(served_model="claude-opus-4-8")
        document = json.loads(report.read_text(encoding="utf-8"))
        document["may_spawn"] = True
        report.write_text(json.dumps(document), encoding="utf-8")
        section = self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["command"], "classify")
        self.assertIsNone(section["may_spawn"])
        self.assertTrue(section["blocks_wave_completion"])

    def test_an_admission_never_projects_a_blocks_wave_completion_it_carries(self) -> None:
        """The mirror image, so the split is checked in both directions."""
        report = self.make_admission()
        document = json.loads(report.read_text(encoding="utf-8"))
        document["blocks_wave_completion"] = True
        report.write_text(json.dumps(document), encoding="utf-8")
        section = self.document("--runtime-assignment", str(report))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["command"], "admit")
        self.assertIsNone(section["blocks_wave_completion"])
        self.assertIsNotNone(section["may_spawn"])


class ActivationSchemaTests(ProjectionCase):
    """`build_activation_result_section`'s schema matcher. A document can carry a valid `state` and still
    not be an activation result -- the state vocabulary is not the schema."""

    def test_a_document_with_a_valid_state_but_a_wrong_schema_is_unreadable(self) -> None:
        body = {
            "schema": "agentic-sdlc/activation-terminal-state@2",
            "state": "refused",
            "consequence": "no wave may write",
            "target": "/repo",
            "reasons": [],
        }
        path = self.work / "wrong-schema.json"
        path.write_text(json.dumps(body), encoding="utf-8")
        section = self.document("--activation-result", str(path))["artifacts"]["activation_result"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("declares schema 'agentic-sdlc/activation-terminal-state@2'", section["reason"])
        # POSITIVE CONTROL: the SAME body under the declared schema is projected, so the refusal is
        # about the schema string and not about the rest of the document.
        body["schema"] = "agentic-sdlc/activation-terminal-state@1"
        accepted = self.work / "right-schema.json"
        accepted.write_text(json.dumps(body), encoding="utf-8")
        good = self.document("--activation-result", str(accepted))["artifacts"]["activation_result"]
        self.assertEqual(good["presence"], PRESENT, good.get("reason"))
        self.assertEqual(good["state"], "refused")


class SealedFieldStrictnessTests(SealedKindCase):
    """The typed-field helpers every sealed projector is built from -- `_need_bool`, `_need_int`,
    `_need_object`, `_need_entry`, `_need_list`, `_need_texts`, `_optional_text`, `_need_member`.

    Each row edits ONE field of a real sealed document and RE-SEALS it: no producer in this family will
    seal a bool where an integer belongs or a third verdict outside its own vocabulary, which is why
    these clauses had no test. `seal` is the same derivation the producers use, so the tool under test
    reads a genuinely sealed document and reaches the clause rather than stopping at the digest.
    """

    def edited(self, fixture: str, mutate: Any, *, name: str) -> Path:
        path = self.copy_of(fixture, as_name=name)
        document = self.read(path)
        mutate(document)
        return self.write(path, seal(document))

    def test_a_non_boolean_check_met_is_unreadable_and_never_counted_as_met(self) -> None:
        """The `_need_bool` clause, on the field where laxity would INVERT a verdict: a blocked report's
        unmet check carrying the truthy string "false" would, under `bool(value)`, be counted into
        `checks_met` -- turning a check the admission tool recorded as NOT met into one it recorded as
        met, in a report whose own disposition says the wave may not start."""
        blocked = self.read(self.copy_of("admission_blocked", as_name="blocked-source.json"))
        unmet = [check["slug"] for check in blocked["checks"] if not check["met"]]
        # POSITIVE CONTROL: the untouched blocked report really does record an unmet check, and this
        # module projects it as not met.
        self.assertTrue(unmet, "the blocked fixture must carry at least one unmet check")
        untouched = self.project_kind("wave_plan_admission", self.copy_of("admission_blocked", as_name="clean.json"))
        self.assertEqual(untouched["presence"], PRESENT)
        self.assertEqual(sorted(untouched["checks_not_met"]), sorted(unmet))

        def poison(document: dict[str, Any]) -> None:
            for check in document["checks"]:
                if not check["met"]:
                    check["met"] = "false"

        path = self.edited("admission_blocked", poison, name="string-met.json")
        section = self.project_kind("wave_plan_admission", path)
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("met that is not a boolean", section["reason"])
        self.assertNotIn("checks_met", section, "an unreadable report projects no check lists at all")

    def test_a_non_boolean_semantic_flag_in_a_plan_diff_is_unreadable(self) -> None:
        """The same helper on a COUNTING field: `bool("no")` is `True`, so laxity here would inflate
        `semantic_change_count` -- a number a reader treats as "how much of this plan really moved"."""
        untouched = self.project_kind("plan_diff", self.copy_of("diff", as_name="clean-diff.json"))
        self.assertEqual(untouched["presence"], PRESENT)  # POSITIVE CONTROL

        def poison(document: dict[str, Any]) -> None:
            document["changes"][0]["semantic"] = "no"

        if not self.read(self.copy_of("diff", as_name="probe.json"))["changes"]:
            self.skipTest("the plan diff fixture records no change to poison")
        section = self.project_kind("plan_diff", self.edited("diff", poison, name="string-semantic.json"))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("semantic that is not a boolean", section["reason"])

    def test_a_boolean_where_an_integer_belongs_is_unreadable(self) -> None:
        """`_need_int`'s bool clause. `True` IS an `int` in Python, so without it a `revision` of `true`
        would be projected as revision 1 -- a plan revision number invented out of a flag."""
        def poison(document: dict[str, Any]) -> None:
            document["revision"] = True

        section = self.project_kind("wave_plan", self.edited("plan", poison, name="bool-revision.json"))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("revision that is not an integer", section["reason"])
        # POSITIVE CONTROL: the integer 1 in the same field is read as revision 1.
        self.assertEqual(self.project_kind("wave_plan", self.fixture("plan"))["revision"], 1)

    def test_an_object_field_that_is_not_an_object_is_unreadable(self) -> None:
        """`_need_object`. `.get()` on a non-dict would raise `AttributeError`, which `main` would
        classify as an internal failure at exit 1 -- one input taking the whole run down."""
        def poison(document: dict[str, Any]) -> None:
            document["authority"] = ["read-only-advisory"]

        section = self.project_kind("mission_contract", self.edited("mission", poison, name="list-authority.json"))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("authority that is not a JSON object", section["reason"])

    def test_a_list_entry_that_is_not_an_object_is_unreadable(self) -> None:
        """`_need_entry`, named by the list it came from so the refusal reads as a sentence."""
        def poison(document: dict[str, Any]) -> None:
            document["nodes"][0] = "ws-b-projection"

        section = self.project_kind("wave_plan", self.edited("plan", poison, name="string-node.json"))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("carries an entry in nodes that is not a JSON object", section["reason"])

    def test_a_field_that_should_be_a_list_is_unreadable(self) -> None:
        """`_need_list`. `len()` of a string counts characters, so a `nodes` of `"abc"` would be
        projected as a plan with three nodes."""
        def poison(document: dict[str, Any]) -> None:
            document["edges"] = "ws-a-cartography->ws-b-projection"

        section = self.project_kind("wave_plan", self.edited("plan", poison, name="string-edges.json"))
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("edges that is not a list", section["reason"])

    def test_a_list_of_strings_with_a_non_string_or_empty_member_is_unreadable(self) -> None:
        """`_need_texts`, both halves: a non-string member and an EMPTY string. An empty stop condition
        is not a stop condition, and projecting it would show a mission with a nameless rule."""
        for bad, description in ((["", "hard-stop-drift"], "an empty member"), ([7], "a non-string member")):
            with self.subTest(bad=description):
                def poison(document: dict[str, Any], value: Any = bad) -> None:
                    document["stop_conditions"] = value

                section = self.project_kind(
                    "mission_contract", self.edited("mission", poison, name=f"stop-{description[3:9]}.json")
                )
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn("stop_conditions that is not a list of non-empty strings", section["reason"])

    def test_a_nullable_field_carrying_a_non_string_is_projected_as_null(self) -> None:
        """`_optional_text` is a COERCION, not a refusal, and this pins which: a `supersedes` of `5` is
        projected as `null` rather than as the number 5. Absent, null, empty, and not-a-string are one
        answer here -- "this document names no predecessor" -- and a reader must never see an integer in
        a field the schema declares as a digest or nothing."""
        def poison(document: dict[str, Any]) -> None:
            document["supersedes"] = 5

        section = self.project_kind("mission_contract", self.edited("mission", poison, name="int-supersedes.json"))
        self.assertEqual(section["presence"], PRESENT, section.get("reason"))
        self.assertIsNone(section["supersedes"])
        self.assertIn("supersedes=None", self.human("--mission-contract", str(self.work / "int-supersedes.json")))
        # POSITIVE CONTROL: a real digest-shaped string in the same field IS carried through.
        def name_a_predecessor(document: dict[str, Any]) -> None:
            document["supersedes"] = "b" * 64

        carried = self.project_kind(
            "mission_contract", self.edited("mission", name_a_predecessor, name="real-supersedes.json")
        )
        self.assertEqual(carried["supersedes"], "b" * 64)

    def test_a_third_transition_receipt_verdict_is_unreadable(self) -> None:
        """`RECEIPT_VERDICTS` is CLOSED at `admitted` / `refused`. A third value must be `unreadable`
        rather than projected as if this module understood it: a verdict is the one field a reader acts
        on, and `auto-envelope.py` owns what its receipt's verdicts mean."""
        for third in ("deferred", "admitted-with-conditions", "ADMITTED", ""):
            with self.subTest(verdict=third):
                def poison(document: dict[str, Any], value: str = third) -> None:
                    document["verdict"] = value

                path = self.edited("receipt", poison, name="third-verdict.json")
                section = self.project_kind("transition_receipt", path)
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn("which is not one of the closed set", section["reason"])
                self.assertIn("verdict", section["reason"])
        # POSITIVE CONTROL: both real verdicts ARE projected, so the closed set is not simply refusing
        # everything.
        self.assertEqual(self.project_kind("transition_receipt", self.fixture("receipt"))["verdict"], "admitted")
        self.assertEqual(
            self.project_kind("transition_receipt", self.fixture("receipt_refused"))["verdict"], "refused"
        )

    def test_a_third_admission_disposition_is_unreadable(self) -> None:
        """The same closed-vocabulary rule on the kind whose disposition now decides a BLUF rung: an
        unrecognised third disposition must not be sorted as if it were `admitted`."""
        def poison(document: dict[str, Any]) -> None:
            document["disposition"] = "admitted-with-blockers"

        section = self.project_kind(
            "wave_plan_admission", self.edited("admission", poison, name="third-disposition.json")
        )
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("which is not one of the closed set", section["reason"])


#: Fields the human view renders as PROSE rather than as `field=value`, with the exact prefix each is
#: rendered under. Every other projected field must appear literally as `field=<flattened value>` in its
#: own section, which is what makes `HumanViewCompletenessTests` mechanical rather than a list somebody
#: has to remember to extend.
PROSE_RENDERED: dict[tuple[str, str], str] = {
    ("mission_contract", "objective"): "  objective: ",
    ("runtime_assignment", "consequence"): "  consequence: ",
    ("activation_result", "consequence"): "  consequence: ",
}

#: Fields rendered as ONE LINE PER ITEM, with that line's prefix.
ITEM_RENDERED: dict[tuple[str, str], str] = {
    ("runtime_assignment", "reasons"): "  reason: ",
    ("activation_result", "reasons"): "  reason: ",
    ("transition_receipt", "reasons"): "  reason: ",
    ("wave_plan_admission", "blockers"): "  blocker: ",
}

#: Fields whose value is itself structured, checked field-by-field inside the section instead.
STRUCTURED_RENDERED: frozenset[tuple[str, str]] = frozenset(
    {("planning_snapshot", "dirty_state"), ("drift_classification", "assessments")}
)

#: The three bookkeeping keys every section carries; the presence LINE covers them, not a detail line.
PRESENCE_KEYS = frozenset({"presence", "path", "reason"})


class HumanViewCompletenessTests(SealedKindCase):
    """EVERY projected field reaches the human view.

    The two views are one document, and the default view is the one a person reads. Before this, 25
    fields were projected into `--json` and never rendered, among them: a wave plan's `head_commit_sha`, an
    admission report's bound `plan_digest` and `snapshot_digest`, a receipt's `gate_status` and
    `failing_set_state`, a mission's scope and completion criteria, a journal's `opened_at` / `last_at` /
    `budget_count`, an assignment's `node` / `may_spawn` / `blocks_wave_completion`, an activation's
    `gate_outcome` / `gate_passes`, and -- most materially -- a comparison's `toolchain_drifted`,
    `baseline_outcome`, `candidate_outcome`, `still_failing`, and `candidate_failing`. A reader of the
    default view could not see them at all.

    This is written as ONE mechanical test over the tool's own projected key set rather than as a
    hand-kept list of field names, because a hand-kept list is exactly what let the gap open: a new
    field added to a projector would be absent from the list and nothing would fail.
    """

    def gate_leaf_sections(self, text: str) -> dict[str, str]:
        """The gate section holds TWO leaves, so it is sliced at its two presence lines rather than
        searched as one block: a token found anywhere in the section would not prove the leaf that
        projects it rendered it."""
        lines = text.splitlines()
        receipt_at = next(index for index, line in enumerate(lines) if line.startswith("gate receipt: "))
        baseline_at = next(index for index, line in enumerate(lines) if line.startswith("gate baseline: "))
        end = next((index for index in range(baseline_at + 1, len(lines)) if not lines[index]), len(lines))
        return {
            "receipt": "\n".join(lines[receipt_at:baseline_at]),
            "baseline": "\n".join(lines[baseline_at:end]),
        }

    def assert_every_field_rendered(self, kind: str, section: dict[str, Any], body: str) -> None:
        for field, value in section.items():
            if field in PRESENCE_KEYS:
                continue
            with self.subTest(kind=kind, field=field):
                if (kind, field) in STRUCTURED_RENDERED:
                    self.assert_structured_rendered(field, value, body)
                    continue
                if (kind, field) in ITEM_RENDERED:
                    for item in value:
                        self.assertIn(f"{ITEM_RENDERED[(kind, field)]}{escaped(item)}", body)
                    continue
                if (kind, field) in PROSE_RENDERED:
                    self.assertIn(f"{PROSE_RENDERED[(kind, field)]}{escaped(value)}", body)
                    continue
                rendered = escaped(value) if isinstance(value, str) else str(value)
                self.assertIn(
                    f"{field}={rendered}",
                    body,
                    f"{kind}.{field} is projected into --json but never rendered in the human view",
                )

    def assert_structured_rendered(self, field: str, value: Any, body: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                self.assertIn(f"{key}={item}", body, f"{field}.{key} is projected but never rendered")
            return
        for entry in value:
            for key, item in entry.items():
                rendered = escaped(item) if isinstance(item, str) else str(item)
                self.assertIn(f"{key}={rendered}", body, f"an entry's {field}.{key} is never rendered")

    def test_every_projected_field_of_every_sealed_kind_reaches_the_human_view(self) -> None:
        argv = self.every_flag()
        document = self.document(*argv)
        text = self.human(*argv)
        for kind, _flag, _schema, label in SEALED_KINDS:
            section = document["artifacts"][kind]
            self.assertEqual(section["presence"], PRESENT, section.get("reason"))
            self.assert_every_field_rendered(kind, section, self.section_text(text, label))

    @_NEEDS_RENAMEAT2
    def test_every_projected_field_of_the_four_original_kinds_reaches_the_human_view(self) -> None:
        journal = self.make_wave_journal(complete=False)
        report = self.make_admission()
        activation = self.make_activation_refused()
        baseline_receipt = self.make_gate_receipt(
            name="baseline.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT, harness_unittest=True
        )
        candidate_receipt = self.make_gate_receipt(
            name="candidate.json", gate="fake gate", script=FAILING_UNITTEST_SCRIPT_TWO, harness_unittest=True
        )
        comparison = self.make_gate_baseline(name="cmp.json", baseline=baseline_receipt, candidate=candidate_receipt)
        argv = [
            "--wave-journal", str(journal), "--runtime-assignment", str(report),
            "--activation-result", str(activation), "--gate-receipt", str(candidate_receipt),
            "--gate-baseline", str(comparison),
        ]
        document = self.document(*argv)
        text = self.human(*argv)
        artifacts = document["artifacts"]
        for kind, label in (
            ("wave_journal", "wave journal"),
            ("runtime_assignment", "runtime assignment"),
            ("activation_result", "activation result"),
        ):
            section = artifacts[kind]
            self.assertEqual(section["presence"], PRESENT, section.get("reason"))
            self.assert_every_field_rendered(kind, section, self.section_text(text, label))
        leaves = self.gate_leaf_sections(text)
        for leaf in ("receipt", "baseline"):
            section = artifacts["gate"][leaf]
            self.assertEqual(section["presence"], PRESENT, section.get("reason"))
            self.assert_every_field_rendered(f"gate.{leaf}", section, leaves[leaf])

    def test_the_human_view_field_names_are_the_json_documents_own_names(self) -> None:
        """The rule that makes the test above mechanical, stated as its own assertion: a reader greps
        one name in either view. Checked on the two fields whose absence was most material."""
        argv = self.every_flag()
        text = self.human(*argv)
        self.assertIn("head_commit_sha=", self.section_text(text, "wave plan"))
        self.assertIn("plan_digest=", self.section_text(text, "wave plan admission report"))
        self.assertIn("snapshot_digest=", self.section_text(text, "wave plan admission report"))


class DocumentShapeTests(ProjectionCase):
    """The shape checks in `_read_json_object` that no other test reached: a JSON document that parses
    but is not an OBJECT, and a document nested deeper than the parser will go."""

    def test_a_json_array_is_unreadable_rather_than_projected(self) -> None:
        for flag, kind in (
            ("--runtime-assignment", "runtime_assignment"),
            ("--activation-result", "activation_result"),
            ("--gate-receipt", "gate"),
        ):
            with self.subTest(flag=flag):
                path = self.work / f"array{flag}.json"
                path.write_text('["not", "an", "object"]', encoding="utf-8")
                document = self.document(flag, str(path))
                section = document["artifacts"][kind]
                if kind == "gate":
                    section = section["receipt"]
                self.assertEqual(section["presence"], UNREADABLE)
                self.assertIn("is not a JSON object", section["reason"])

    def test_a_json_object_gets_past_the_object_check(self) -> None:
        """POSITIVE CONTROL for the test above: an OBJECT is refused for what it says, never for its
        container type, so the assertion above is about the array and not about the flag."""
        path = self.work / "empty-object.json"
        path.write_text("{}", encoding="utf-8")
        section = self.document("--runtime-assignment", str(path))["artifacts"]["runtime_assignment"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertNotIn("is not a JSON object", section["reason"])
        self.assertIn("declares schema None", section["reason"])


class NestingCeilingTests(ProjectionCase):
    """A deeply nested document must be ONE `unreadable` input, never an exit-1 `RecursionError`.

    `json.loads` recurses once per nesting level. Before the ceiling, a 2000-level document raised
    `RecursionError` out of the parser, `main`'s catch-all classified it as an unexpected internal
    failure, and the whole run exited 1 with NO document at all -- so one hostile input destroyed the
    independent outcome every other input is promised.
    """

    #: Deep enough to overflow the interpreter's stack in a recursive parser by a wide margin, so
    #: this is not a test of one exact limit.
    DEEP = 2000

    def test_a_deeply_nested_document_is_one_unreadable_input_at_exit_zero(self) -> None:
        path = self.work / "deep.json"
        path.write_bytes(nested_json_document(self.DEEP))
        done = self.run_tool("--gate-receipt", str(path), "--json")
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        section = json.loads(done.stdout)["artifacts"]["gate"]["receipt"]
        self.assertEqual(section["presence"], UNREADABLE)
        self.assertIn("nests JSON containers deeper than", section["reason"])

    @_NEEDS_RENAMEAT2
    def test_the_other_twelve_inputs_keep_their_own_outcomes_beside_a_deeply_nested_one(self) -> None:
        """The independence claim itself, stated as an assertion: a hostile input costs its OWN
        section and nothing else's."""
        deep = self.work / "deep.json"
        deep.write_bytes(nested_json_document(self.DEEP))
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        journal = self.make_wave_journal(complete=True)
        document = self.document(
            "--activation-result", str(deep), "--gate-receipt", str(receipt), "--wave-journal", str(journal)
        )
        artifacts = document["artifacts"]
        self.assertEqual(artifacts["activation_result"]["presence"], UNREADABLE)
        self.assertEqual(artifacts["gate"]["receipt"]["presence"], PRESENT)
        self.assertEqual(artifacts["wave_journal"]["presence"], PRESENT)
        self.assertEqual(artifacts["gate"]["receipt"]["gate"], "smoke")

    def test_an_ordinary_document_is_nowhere_near_the_ceiling(self) -> None:
        """POSITIVE CONTROL: the ceiling refuses only depth. Every real fixture this module builds is
        projected normally, so the scan cannot be passing by refusing everything."""
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        section = self.document("--gate-receipt", str(receipt))["artifacts"]["gate"]["receipt"]
        self.assertEqual(section["presence"], PRESENT)

    def test_a_brace_inside_a_string_is_data_and_not_a_container(self) -> None:
        """The scan tracks string state, so a receipt whose own `gate` label is full of braces is not
        mistaken for a deeply nested document. `gate_receipt.py` seals the label it was given, so this
        is a real receipt with a hostile-looking label rather than an edited one."""
        label = "{" * 200 + "[" * 200
        receipt = self.make_gate_receipt(name="braces.json", gate=label, script=PASSING_SCRIPT)
        section = self.document("--gate-receipt", str(receipt))["artifacts"]["gate"]["receipt"]
        self.assertEqual(section["presence"], PRESENT, section.get("reason"))
        self.assertEqual(section["gate"], label)


class RepeatedFlagTests(ProjectionCase):
    """A repeated artifact flag is a GRAMMAR ERROR, not a silent last-wins.

    argparse's default would have projected the second path and never mentioned the first, which for a
    surface whose whole value is naming exactly which evidence it read is a wrong answer rather than a
    lenient one.
    """

    def _flags(self) -> list[str]:
        return [
            "--wave-journal", "--runtime-assignment", "--activation-result", "--gate-receipt",
            "--gate-baseline", *[flag for _kind, flag, _schema, _label in SEALED_KINDS],
        ]

    def test_every_artifact_flag_refuses_a_second_occurrence_at_exit_two(self) -> None:
        first = self.work / "first.json"
        second = self.work / "second.json"
        for path in (first, second):
            path.write_text("{}", encoding="utf-8")
        for flag in self._flags():
            with self.subTest(flag=flag):
                done = self.run_tool(flag, str(first), flag, str(second))
                self.assertEqual(done.returncode, EXIT_INPUT)
                self.assertEqual(done.stdout, b"")
                message = done.stderr.decode("utf-8")
                self.assertIn(f"{flag} was given more than once", message)
                # The refusal names the OPTION and neither path: a path is caller data.
                self.assertNotIn(str(first), message)
                self.assertNotIn(str(second), message)
            with self.subTest(flag=flag, repeat="same path"):
                # The SAME path twice is still a repeat: the guard counts occurrences, never
                # deduplicates values, so an equal second value cannot slip through.
                done = self.run_tool(flag, str(first), flag, str(first))
                self.assertEqual(done.returncode, EXIT_INPUT)
                self.assertIn(f"{flag} was given more than once", done.stderr.decode("utf-8"))

    def test_one_occurrence_of_every_flag_is_still_accepted(self) -> None:
        """POSITIVE CONTROL: the once-only action must not refuse a single occurrence -- the refusal
        above is about the REPEAT."""
        for flag in self._flags():
            with self.subTest(flag=flag):
                done = self.run_tool(flag, str(self.work / "absent.json"), "--json")
                self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))

    def test_the_repeated_path_is_never_silently_projected(self) -> None:
        """The exact defect: the SECOND path must not become the projection's answer."""
        receipt = self.make_gate_receipt(name="r.json", gate="smoke", script=PASSING_SCRIPT)
        other = self.make_gate_receipt(name="other.json", gate="other gate", script=PASSING_SCRIPT)
        done = self.run_tool("--gate-receipt", str(receipt), "--gate-receipt", str(other), "--json")
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertEqual(done.stdout, b"")

    def test_json_stays_repeatable_because_it_drops_nothing(self) -> None:
        """POSITIVE CONTROL for the boundary of the rule: `--json` takes no value, so a repeat cannot
        drop a path and is not an error."""
        done = self.run_tool("--json", "--json")
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(json.loads(done.stdout)["schema"], RESULT_SCHEMA)


class DocstringClaimTests(unittest.TestCase):
    """The claims these two docstrings make about THEMSELVES, checked instead of trusted.

    Both files carried a count that had drifted: the tool's residual paragraph attributed the eight
    sealed kinds to a ticket numbering this repository does not contain, and this module's own opening
    paragraph said "three of the four artifact kinds" have real producers (all four do) while naming a
    class -- `ActivationResultPresentTests` -- that does not exist. Neither could fail a test, so
    neither did. Every claim below is one a test can actually check.
    """

    #: The six producer tools the eight sealed kinds come from. Derived from the tool's own reader
    #: registry order, and the reason the residual paragraph counts PRODUCERS rather than tickets: this
    #: list is checkable against the tree, a ticket number is not.
    SEALED_PRODUCERS = (
        "mission-contract.py",
        "planning-snapshot.py",
        "wave-plan-compiler.py",
        "wave-plan-admission.py",
        "drift-classifier.py",
        "auto-envelope.py",
    )

    def test_every_producer_the_residual_paragraph_names_exists_in_the_tree(self) -> None:
        for producer in self.SEALED_PRODUCERS:
            with self.subTest(producer=producer):
                self.assertTrue((TOOL.parent / producer).is_file(), f"{producer} is named but not in the tree")

    def test_the_residual_paragraph_counts_producers_and_not_tickets(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn("The eight come from the SIX producer tools", source)
        for producer in self.SEALED_PRODUCERS:
            self.assertIn(f"`{producer}`", source)
        # The count word and the list must agree, and the retired ticket-count claim must be gone.
        self.assertEqual(len(self.SEALED_PRODUCERS), 6)
        self.assertNotIn("come from six tickets", source)
        self.assertNotIn("T5 twice", source)

    def test_the_eight_sealed_kinds_are_still_eight(self) -> None:
        """The number the paragraph above says those six producers account for, read off the tool's own
        flag surface rather than off the prose."""
        self.assertEqual(len(SEALED_KINDS), 8)
        source = TOOL.read_text(encoding="utf-8")
        for _kind, flag, schema, _label in SEALED_KINDS:
            self.assertIn(flag.lstrip("-"), source)
            self.assertIn(schema, source)

    def test_every_test_class_this_modules_docstring_names_exists(self) -> None:
        """A stale class name in a docstring sends the next reader looking for a test that is not there.
        The names are read out of the docstring itself, so adding a reference to a class that does not
        exist fails here."""
        module = sys.modules[__name__]
        docstring = module.__doc__ or ""
        # Backticked spans are the ODD segments of a split on the backtick, so a possessive or a comma
        # outside the quotes cannot end up inside the name.
        named = {span for index, span in enumerate(docstring.split("`")) if index % 2 == 1 and span.endswith("Tests")}
        self.assertTrue(named, "the docstring must name at least one test class for this to check anything")
        for name in named:
            with self.subTest(referenced=name):
                self.assertTrue(
                    isinstance(getattr(module, name, None), type),
                    f"the module docstring names {name}, which is not a class in this module",
                )
        # POSITIVE CONTROL: the extraction really does find the names, and a name that is NOT a class
        # would be rejected -- checked against a deliberately absent one rather than assumed.
        self.assertIn("ActivationResultTests", named)
        self.assertFalse(isinstance(getattr(module, "ActivationResultPresentTests", None), type))

    def test_the_docstring_claim_that_all_four_original_kinds_have_real_producers_holds(self) -> None:
        """The corrected count, checked against the producers this module actually runs."""
        docstring = sys.modules[__name__].__doc__ or ""
        self.assertIn("ALL FOUR of the original artifact kinds", docstring)
        self.assertNotIn("three of the four", docstring)
        for producer in (
            WAVE_JOURNAL_TOOL, RUNTIME_ASSIGNMENT_TOOL, ACTIVATION_RESULT_TOOL, GATE_RECEIPT_TOOL, GATE_BASELINE_TOOL
        ):
            with self.subTest(producer=producer.name):
                self.assertTrue(producer.is_file())
        self.assertEqual(len(V1_ARTIFACT_KINDS), 4)


class NoRegexBackslashDTests(unittest.TestCase):
    """`\\d` matches every Unicode decimal digit, not only ASCII 0-9, which has already bitten this
    repository once (mission-contract.py's `stated_at`). This module is checked for the same defect
    even though it has no timestamp field of its own, because a future edit could add one."""

    def test_no_backslash_d_appears_in_the_module_source(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("\\d", source)


class RenameAt2CapabilityTests(unittest.TestCase):
    """The capability probe every `@_NEEDS_RENAMEAT2` test above is skipped by. Deliberately its own
    plain `unittest.TestCase`: this class's whole point is to run even when `_HAS_RENAMEAT2` is false
    and every decorated test here is skipped. `wave-journal.py`'s own refusal at the missing syscall
    is covered directly by `tests/test_wave_journal.py`'s `RenameAt2CapabilityTests`; this is only the
    probe this module reuses to decide whether to build a journal fixture with it at all.
    """

    @unittest.skipUnless(sys.platform.startswith("linux"), "the probe's truth is only guaranteed on Linux (glibc 2.28+)")
    def test_the_probe_returns_non_none_on_this_linux_host(self) -> None:
        """POSITIVE CONTROL: without this, `_HAS_RENAMEAT2` gating every `@_NEEDS_RENAMEAT2` test
        above would be silently vacuous -- true on every host, including the ubuntu CI runner this
        suite must stay green on -- and nothing would ever fail to reveal it.

        The platform condition is the assertion's own scope, not a capability the probe is excused
        from: the claim is precisely "ON LINUX this symbol must exist", so it RUNS on the ubuntu runner
        (where a vacuous skip would otherwise hide) and skips by name on macOS rather than failing
        there for lacking a syscall macOS has never had."""
        self.assertTrue(_HAS_RENAMEAT2, "glibc 2.28+ always exports renameat2; this host is unexpected")


if __name__ == "__main__":
    unittest.main()
