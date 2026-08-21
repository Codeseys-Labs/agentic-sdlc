"""Tests for the terminal wave verdict composer.

Three kinds of test live here and they check different things.

The two JOURNEY tests drive the real producers over their real command lines -- `wave-journal.py`
init/record/project, `runtime-assignment.py classify`, and `scripts/gate_baseline.py compare` -- and
build only the gate receipts by hand, because a real receipt requires a gate to actually run. One
journey reaches `accepted` and one reaches `remediation-progress`. They are what keeps the composer's
re-expressed canonical form and receipt digest honest: a drifted form surfaces as a `journal_digest`
that will not re-derive or a `self_digest` that will not verify, not as a silent pass.

The NEGATIVE cases each carry a POSITIVE CONTROL in the same test: the unmutated artifact set is
asserted to reach its ready state FIRST, so a test that stopped exercising its guard would also have
to stop reaching that state. Several of them mutate a document the real producers wrote, which is the
only way to reach a shape no honest producer emits on demand.

The HOSTILE-DESCRIPTOR cases run the tool with a stderr or a stdout it cannot write to, because a
display channel must cost the display line and never the classified exit code, and because the one
result document is the evidence: a verdict derived and not delivered is not a success.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-verdict.py"
JOURNAL_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-journal.py"
#: The producer of the four submissions this tool consumes. `SealedSubmissionRoundTripTests` runs it.
SUBMISSION_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-submission.py"
RUNTIME_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "runtime-assignment.py"
BASELINE_TOOL = ROOT / "scripts" / "gate_baseline.py"
RUNTIME_POLICY = ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"

RESULT_SCHEMA = "agentic-sdlc/wave-terminal-verdict@1"
PROJECTION_SCHEMA = "agentic-sdlc/wave-journal-projection@1"
CLASSIFICATION_SCHEMA = "agentic-sdlc/runtime-substitution-classification@1"
MANIFEST_SCHEMA = "agentic-sdlc/wave-artifact-manifest@1"
REVIEW_SCHEMA = "agentic-sdlc/wave-review-submission@1"
CRITIC_SCHEMA = "agentic-sdlc/wave-critic-findings@1"
CONDUCTOR_RECORD_SCHEMA = "agentic-sdlc/wave-verdict-conductor-record@1"
SERVED_SCHEMA = "agentic-sdlc/runtime-served-record@1"

#: `wave-submission.py`'s `--kind` values for the four schemas above, in the same order.
ARTIFACT_MANIFEST_KIND = "artifact-manifest"
REVIEW_KIND = "review"
CRITIC_KIND = "critic-findings"
CONDUCTOR_RECORD_KIND = "conductor-record"

ACCEPTED = "accepted"
REMEDIATION_PROGRESS = "remediation-progress"
BLOCKED = "blocked"
#: Implementation Decision 61's other three, derived from how the execution ENDED.
ABORTED = "aborted"
FAILED = "failed"
UNKNOWN_EFFECT = "unknown-effect"

EXIT_OK = 0
#: The undelivered-document code. A state this tool derived but could not put on stdout is neither a
#: success nor an input error, and 120 is not in the module's exit space at all.
EXIT_INTERNAL = 1
EXIT_INPUT = 2

AUTHORITATIVE_GATE = "mise run check"
FOCUSED_GATE = "mise run test -- tests.test_wave_verdict"

#: The only variable any tool spawned here reads (`wave-journal.py`'s fault seam). Every spawn
#: CONSTRUCTS its environment without it rather than inheriting: a developer debugging that tool
#: exports it, and an inherited one would turn this module red for a reason unrelated to the code
#: under test. `EnvironmentTests` keeps this set honest against the sources.
TOOL_CONTROL_ENV = frozenset({"AGENTIC_SDLC_WAVE_JOURNAL_FAULT"})

T0 = "2026-08-19T02:00:00Z"
T1 = "2026-08-19T02:01:00Z"
T2 = "2026-08-19T02:02:00Z"
T3 = "2026-08-19T02:03:00Z"
T4 = "2026-08-19T02:04:00Z"
T5 = "2026-08-19T02:05:00Z"
T6 = "2026-08-19T02:06:00Z"

PLAN_DIGEST = "a" * 64
MODEL = "claude-sonnet-5"
PROVIDER = "anthropic"

WAVE_ID = "wave-1"
MISSION_ID = "mission-slice-5"

IMPLEMENTER = "implement-a"
REVIEWER = "review-a"
INTEGRATOR = "fan-in"
FAN_IN_APPROVAL = "approval-fan-in"

#: One output per admitted-success node, because condition 3 requires the manifest to cover them all.
OUTPUTS = {
    IMPLEMENTER: "src/feature.py",
    REVIEWER: "reviews/review-a.json",
    INTEGRATOR: "integration/merge-log.txt",
}

BASELINE_FAILURES = ["tests.test_legacy.Case.test_one", "tests.test_legacy.Case.test_two"]
#: A strict subset of the baseline: one test fixed, nothing new broken.
CANDIDATE_FAILURES = ["tests.test_legacy.Case.test_one"]


def constructed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment every spawn in this module hands a tool: inherited, MINUS the tool controls.

    PATH, HOME, and locale are inherited deliberately -- the tool is a subprocess and needs a usable
    interpreter environment. What is never inherited is a variable a spawned tool READS.
    """
    environment = {key: value for key, value in os.environ.items() if key not in TOOL_CONTROL_ENV}
    if extra:
        environment.update(extra)
    return environment


def canonical(value: Any) -> bytes:
    """The family's canonical form: sorted, tight, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def receipt_digest(body: dict[str, Any]) -> str:
    """`gate_receipt.canonical_digest`: the same canonical form with NO trailing newline."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gate_receipt(
    *,
    gate: str,
    status: int | None,
    cwd: str,
    failures: dict[str, Any] | None = None,
    argv: list[str] | None = ("mise", "run", "check"),
    signal: int | None = None,
    toolchain: bytes = b"mise.lock bytes",
    log: bytes = b"gate log bytes",
) -> dict[str, Any]:
    """One receipt built exactly as `gate_receipt.build_receipt` builds it.

    Constructed rather than recorded because a real receipt requires a gate to actually run, and this
    module may not run one. The construction is validated by the tool's own re-derivation: a wrong
    field order, a wrong digest form, or a state the producer could not have written is refused as
    malformed input, so a drifted re-expression on either side fails rather than passes.
    """
    body: dict[str, Any] = {
        "gate": gate,
        "argv": None if argv is None else list(argv),
        "status": None if status is None else int(status),
        "signal": signal,
        "outcome": "unobserved" if status is None else ("passed" if status == 0 else "failed"),
        "log_digest": sha256_hex(log),
        "toolchain_digest": sha256_hex(toolchain),
        "cwd": cwd,
    }
    if failures is not None:
        body["failures"] = failures
    receipt = dict(body)
    receipt["self_digest"] = receipt_digest(body)
    return receipt


def failing_set(names: list[str], state: str = "identified") -> dict[str, Any]:
    return {"harness": "unittest", "names": sorted(set(names)), "state": state}


def header_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "wave_id": WAVE_ID,
        "mission_id": MISSION_ID,
        "mode": "static-dag",
        "plan_digest": PLAN_DIGEST,
        "approval": "operator approved the wave graph, routes, budgets, and limits at review",
        "required_nodes": [IMPLEMENTER, REVIEWER, INTEGRATOR],
        "limits": {"max_concurrent_nodes": 4, "max_nodes": 64, "max_recursive_generations": 0},
    }
    record.update(overrides)
    return record


def assignment(**overrides: Any) -> dict[str, Any]:
    record = {
        "provider": PROVIDER,
        "model_id": MODEL,
        "effort": "high",
        "context": "base",
        "resolution_state": "resolved",
    }
    record.update(overrides)
    return record


def node_record(node_id: str, role: str, disposition: str, ended_at: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "node_id": node_id,
        "role": role,
        "disposition": disposition,
        "inputs": ["plan/wave-1.json"],
        "outputs": [OUTPUTS[node_id]] if node_id in OUTPUTS else [],
        "assignment": assignment(),
        "started_at": T0,
        "ended_at": ended_at,
        "evidence": [f"{node_id} transcript and artifact digest"],
        "attempt": 1,
        "reasons": [],
        "approval": None,
    }
    record.update(overrides)
    return record


def approval_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "approval_id": FAN_IN_APPROVAL,
        "subject": "authorize the integrator to fan the accepted workstream in",
        "scope": [INTEGRATOR],
        "authority": "operator",
        "evidence": ["conversation turn 41"],
    }
    record.update(overrides)
    return record


def budget_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "budget_id": "budget-nodes",
        "scope": "wave",
        "node_id": None,
        "unit": "nodes",
        "limit": 64,
        "consumed": 4,
        "reasons": [],
    }
    record.update(overrides)
    return record


def served_record(node: str, **overrides: Any) -> dict[str, Any]:
    """The happy-path served record: the exact requested route, read back independently."""
    served = {
        "identity_status": "verified",
        "identity_source": "adapter_response_readback",
        "identity_basis": "independent_readback",
        "request_injection_status": "verified",
        "provider": PROVIDER,
        "model_id": MODEL,
        "effort_readback_status": "unavailable",
        "context_readback_status": "unavailable",
    }
    served.update(overrides.pop("served", {}))
    record = {
        "schema": SERVED_SCHEMA,
        "node": node,
        "requested": {"model_id": MODEL, "effort": "high", "context_form": "base"},
        "served": served,
    }
    record.update(overrides)
    return record


def run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Re-expressed from the fixture `tests.test_runtime_assignment` uses for the identical rule, not
    imported across test modules. Two shapes, kept separate because they produce DIFFERENT wrong exit
    codes and neither is exotic:

        closed  `2>&-`. CPython then starts with `sys.stderr is None`, so the FIRST
                `sys.stderr.write` raises `AttributeError` and the classified code becomes 1.
        epipe   fd 2 is the write end of a pipe whose reader is already closed, so every write raises
                EPIPE and leaves bytes pending that CPython flushes again while finalizing, which
                replaces the exit code with 120.

    Stderr is deliberately NOT captured: capturing it would hand the child a writable stream and test
    nothing.
    """
    if mode == "closed":
        done = subprocess.run(
            ["sh", "-c", 'exec 2>&-; exec "$@"', "sh", *argv],
            stdout=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
            env=constructed_environment(),
        )
        return done.returncode, done.stdout
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stderr mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the reader is gone BEFORE the child starts, so no write can succeed
    try:
        child = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd), env=constructed_environment()
        )
    finally:
        os.close(write_fd)
    assert child.stdout is not None
    with child.stdout as stream:
        out = stream.read()
    return child.wait(), out


def run_with_hostile_stdout(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stdout this process CANNOT write to. Returns (exit code, stderr bytes).

    The mirror of `run_with_hostile_stderr`, and a DIFFERENT contract: stdout carries the one result
    document, so the tool may not deliver it and may not pretend it did.
    """
    if mode == "closed":
        done = subprocess.run(
            ["sh", "-c", 'exec 1>&-; exec "$@"', "sh", *argv],
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
            env=constructed_environment(),
        )
        return done.returncode, done.stderr
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stdout mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    try:
        child = subprocess.Popen(
            argv, stdout=write_fd, stderr=subprocess.PIPE, cwd=str(cwd), env=constructed_environment()
        )
    finally:
        os.close(write_fd)
    assert child.stderr is not None
    with child.stderr as stream:
        err = stream.read()
    return child.wait(), err


class WaveCase(unittest.TestCase):
    """Builds one complete wave's artifacts with the real producers, then derives states over them.

    Every test starts from the SAME accepted set and changes exactly one thing, so each negative case
    states its own positive control by construction.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        # The repository the wave wrote into, kept separate from the artifact scratch so a declared
        # path that escapes the target has somewhere to escape TO.
        self.target = self.root / "repo"
        self.work = self.root / "artifacts"
        self.target.mkdir()
        self.work.mkdir()
        self.journal = self.work / "journal.jsonl"

    # ---- plumbing -------------------------------------------------------------------------------

    def store(self, name: str, value: Any) -> Path:
        path = self.work / f"{name}.json"
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        return path

    def run_tool(self, *argv: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-B", str(TOOL), *argv],
            capture_output=True,
            cwd=str(self.root),
            check=False,
            env=constructed_environment(),
        )

    def derive(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run `derive` over one argument map and return the one result document at exit 0."""
        done = self.run_tool(*self.argv(args))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        document = json.loads(done.stdout)
        self.assertEqual(document["schema"], RESULT_SCHEMA)
        self.assertEqual(document["exit_code"], EXIT_OK)
        return document

    def derive_failure(self, args: dict[str, Any]) -> subprocess.CompletedProcess[bytes]:
        """Run `derive` expecting NO result document: a malformed input artifact (exit 2)."""
        done = self.run_tool(*self.argv(args))
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, b"", "an input error must emit no result document")
        return done

    @staticmethod
    def argv(args: dict[str, Any]) -> list[str]:
        argv = ["derive"]
        for flag, value in args.items():
            if value is None:
                continue
            for item in value if isinstance(value, list) else [value]:
                argv.extend([flag, str(item)])
        return argv

    def reasons(self, document: dict[str, Any]) -> str:
        return " || ".join(document["reasons"])

    def condition(self, document: dict[str, Any], number: int) -> dict[str, Any]:
        found = [item for item in document["conditions"] if item["number"] == number]
        self.assertEqual(len(found), 1, f"exactly one condition {number} must be reported")
        return found[0]

    # ---- the real producers ---------------------------------------------------------------------

    def journal_run(self, verb: str, *extra: str) -> dict[str, Any]:
        done = subprocess.run(
            [sys.executable, "-B", str(JOURNAL_TOOL), verb, "--journal", str(self.journal), *extra],
            capture_output=True,
            cwd=str(self.root),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stdout.decode("utf-8", "replace"))
        return json.loads(done.stdout)

    def build_journal(self, steps: list[tuple[str, dict[str, Any], str]] | None = None) -> Path:
        """Write one real journal with the real tool, then project it. Returns the projection path."""
        for verb, record, at in steps if steps is not None else self.journal_steps():
            self.journal_run(verb, "--at", at, "--record", json.dumps(record))
        projection = self.journal_run("project")
        self.assertEqual(projection["schema"], PROJECTION_SCHEMA)
        self.projection = projection
        self.journal_digest = projection["journal_digest"]
        return self.store("projection", projection)

    def journal_steps(self) -> list[tuple[str, dict[str, Any], str]]:
        """The accepted wave: an approval, one workstream, its review, the fan-in, and a budget.

        The order is load-bearing and the composer checks it: the approval precedes the fan-in it
        authorizes, and the review follows the work it inspected.
        """
        return [
            ("init", header_record(), T0),
            ("record-approval", approval_record(), T1),
            ("record-node", node_record(IMPLEMENTER, "implementer", "admitted-success", T2), T2),
            ("record-node", node_record(REVIEWER, "reviewer", "admitted-success", T3), T3),
            ("record-node", node_record(INTEGRATOR, "integrator", "admitted-success", T4), T4),
            ("record-budget", budget_record(), T5),
        ]

    def classify(self, node: str, record: dict[str, Any] | None = None) -> Path:
        """One real `runtime-assignment.py classify` result for one node."""
        served = self.store(f"served-{node}", record if record is not None else served_record(node))
        done = subprocess.run(
            [
                sys.executable,
                "-B",
                str(RUNTIME_TOOL),
                "classify",
                "--served",
                str(served),
                "--policy",
                str(RUNTIME_POLICY),
            ],
            capture_output=True,
            cwd=str(self.root),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        document = json.loads(done.stdout)
        self.assertEqual(document["schema"], CLASSIFICATION_SCHEMA)
        return self.store(f"classification-{node}", document)

    def compare_baseline(self, baseline: Path, candidate: Path) -> Path:
        """One real `scripts/gate_baseline.py compare` report."""
        done = subprocess.run(
            [
                sys.executable,
                "-B",
                str(BASELINE_TOOL),
                "compare",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--quiet",
            ],
            capture_output=True,
            cwd=str(self.root),
            check=False,
            env=constructed_environment(),
        )
        self.assertIn(done.returncode, (0, 5), done.stderr.decode("utf-8", "replace"))
        report = json.loads(done.stdout)
        self.assertEqual(report["schema_version"], "gate-baseline-comparison/v1")
        self.baseline_exit = done.returncode
        return self.store("baseline-report", report)

    # ---- the conductor-and-critic-side documents ------------------------------------------------

    def write_artifacts(self, mapping: dict[str, bytes] | None = None) -> Path:
        """Create the wave's declared artifacts in the target, then declare them by digest."""
        contents = mapping if mapping is not None else {
            path: f"the content of {path}\n".encode("utf-8") for path in OUTPUTS.values()
        }
        entries = []
        for relative, data in contents.items():
            destination = self.target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            entries.append({"path": relative, "sha256": sha256_hex(data)})
        return self.store(
            "manifest",
            {
                "schema": MANIFEST_SCHEMA,
                "wave_id": WAVE_ID,
                "target": str(self.target),
                "artifacts": sorted(entries, key=lambda item: item["path"]),
            },
        )

    def write_review(
        self,
        *,
        subject: str = IMPLEMENTER,
        reviewer: str = REVIEWER,
        verdict: str = "accepted",
        evidence: list[str] | None = None,
        reasons: list[str] | None = None,
        wave_id: str = WAVE_ID,
        name: str = "review",
    ) -> Path:
        return self.store(
            name,
            {
                "schema": REVIEW_SCHEMA,
                "wave_id": wave_id,
                "subject_node_id": subject,
                "reviewer_node_id": reviewer,
                "verdict": verdict,
                "evidence": evidence if evidence is not None else [f"read {subject}'s immutable diff"],
                "reasons": reasons or [],
            },
        )

    def write_conductor_record(self, name: str = "conductor-record", **overrides: Any) -> Path:
        """The record a conductor files for an execution that COMPLETED, unless a test says otherwise.

        The three ended-state keys are part of the default because an absent `ended_state` is its own
        named reason: leaving them out of the shared fixture would make every test in this module
        exercise that reason instead of the condition it is about.
        """
        record = {
            "schema": CONDUCTOR_RECORD_SCHEMA,
            "wave_id": WAVE_ID,
            "journal_digest": self.journal_digest,
            "recorded_by": "conductor",
            "recorded_at": T6,
            "verdict_destination": "the mission's wave receipt at receipts/wave-1.json",
            "ended_state": "completed",
            "ended_reasons": [],
            "last_proven_stage": None,
        }
        record.update(overrides)
        return self.store(name, record)

    def write_ended_record(self, ended: str, name: str, **overrides: Any) -> Path:
        """A record for an execution that did NOT complete, substantiated the way the schema requires."""
        ending = {
            "ended_state": ended,
            "ended_reasons": [f"the wave's execution ended {ended} while the integrator was merging"],
            "last_proven_stage": "the reviewer's acceptance of implement-a",
        }
        ending.update(overrides)
        return self.write_conductor_record(name=name, **ending)

    def write_findings(self, findings: list[dict[str, Any]] | None = None, wave_id: str = WAVE_ID) -> Path:
        return self.store(
            "critic-findings",
            {
                "schema": CRITIC_SCHEMA,
                "wave_id": wave_id,
                "findings": findings if findings is not None else [self.seed_worthy_finding()],
            },
        )

    @staticmethod
    def seed_worthy_finding(**overrides: Any) -> dict[str, Any]:
        finding = {
            "finding_id": "finding-1",
            "kind": "maintainability",
            "severity": "low",
            "evidence": ["the composer's assess_* functions repeat their absent-journal branch"],
            "affected_artifact": "skills/agentic-sdlc/tools/wave-verdict.py",
            "recommended_disposition": "seed",
            "rationale": "a future reader pays for the repetition; nothing in this wave is wrong",
            "resolved": False,
            "resolution": None,
        }
        finding.update(overrides)
        return finding

    @staticmethod
    def blocking_finding(**overrides: Any) -> dict[str, Any]:
        finding = {
            "finding_id": "finding-blocker",
            "kind": "safety-regression",
            "severity": "high",
            "evidence": ["the fan-in dropped the containment check at src/feature.py:12"],
            "affected_artifact": "src/feature.py",
            "recommended_disposition": "remediation workstream",
            "resolved": False,
            "resolution": None,
            "rationale": "a path that escapes the target is read, which the wave's own criteria forbid",
        }
        finding.update(overrides)
        return finding

    def forge_projection(self, extra: list[dict[str, Any]], **summary: Any) -> dict[str, Any]:
        """A projection the real tool did NOT write, made SELF-CONSISTENT on purpose.

        This is the same-OS-user forger the composer's residuals name: the chain is recomputed, the
        `journal_digest` re-derives, and the published summary fields are updated to agree. It exists
        because a few of the composer's guards defend against contents `wave-journal.py` refuses to
        record in the first place, and a guard that no input can reach is indistinguishable from a
        guard that does not work. Forging is the distinguishing input that tells them apart.

        The conductor's anchor is regenerated from the forged digest too, so condition 8 does not
        answer for condition 7.
        """
        projection = json.loads((self.work / "projection.json").read_text(encoding="utf-8"))
        rebuilt: list[dict[str, Any]] = []
        lines: list[bytes] = []
        for index, entry in enumerate([*projection["entries"], *extra]):
            entry = {key: value for key, value in entry.items() if key != "prev_digest"}
            entry["seq"] = index
            if index:
                entry["prev_digest"] = sha256_hex(lines[-1])
            line = canonical(entry)
            lines.append(line)
            rebuilt.append(entry)
        projection["entries"] = rebuilt
        projection["journal_digest"] = sha256_hex(b"".join(lines))
        projection.update(summary)
        self.journal_digest = projection["journal_digest"]
        return projection

    # ---- the two complete argument sets ---------------------------------------------------------

    def accepted_args_over(self, steps: list[tuple[str, dict[str, Any], str]]) -> dict[str, Any]:
        """The accepted argument set over a MODIFIED journal, rebuilt from the given steps."""
        projection = self.build_journal(steps)
        receipt = self.store(
            "gate-receipt",
            gate_receipt(gate=AUTHORITATIVE_GATE, status=0, cwd=str(self.target), failures=failing_set([])),
        )
        spawned = sorted(
            node_id
            for node_id, node in self.projection["dispositions"].items()
            if node["disposition"] == "admitted-success"
        )
        return {
            "--journal-projection": str(projection),
            "--runtime-classification": [str(self.classify(node)) for node in spawned],
            "--artifact-manifest": str(self.write_artifacts()),
            "--review": [str(self.write_review())],
            "--fan-in-approval": FAN_IN_APPROVAL,
            "--gate-receipt": str(receipt),
            "--authoritative-gate": AUTHORITATIVE_GATE,
            "--conductor-record": str(self.write_conductor_record()),
            "--critic-findings": str(self.write_findings()),
        }


    def accepted_args(self) -> dict[str, Any]:
        """Every artifact of one honest delivery wave, with the authoritative gate passing."""
        projection = self.build_journal()
        receipt = self.store(
            "gate-receipt",
            gate_receipt(gate=AUTHORITATIVE_GATE, status=0, cwd=str(self.target), failures=failing_set([])),
        )
        return {
            "--journal-projection": str(projection),
            "--runtime-classification": [str(self.classify(node)) for node in sorted(OUTPUTS)],
            "--artifact-manifest": str(self.write_artifacts()),
            "--review": [str(self.write_review())],
            "--fan-in-approval": FAN_IN_APPROVAL,
            "--gate-receipt": str(receipt),
            "--authoritative-gate": AUTHORITATIVE_GATE,
            "--conductor-record": str(self.write_conductor_record()),
            "--critic-findings": str(self.write_findings()),
        }

    def remediation_args(self, *, candidate_failures: list[str] | None = None, **receipt_kwargs: Any) -> dict[str, Any]:
        """The same wave with a RED authoritative gate, passing focused gates, and a real comparison."""
        args = self.accepted_args()
        names = CANDIDATE_FAILURES if candidate_failures is None else candidate_failures
        candidate = self.store(
            "gate-receipt",
            gate_receipt(
                gate=AUTHORITATIVE_GATE,
                status=1,
                cwd=str(self.target),
                failures=failing_set(names, **({"state": receipt_kwargs.pop("state")} if "state" in receipt_kwargs else {})),
                **receipt_kwargs,
            ),
        )
        baseline = self.store(
            "gate-baseline-receipt",
            gate_receipt(
                gate=AUTHORITATIVE_GATE, status=1, cwd=str(self.target), failures=failing_set(BASELINE_FAILURES)
            ),
        )
        focused = self.store(
            "focused-receipt",
            gate_receipt(
                gate=FOCUSED_GATE,
                status=0,
                cwd=str(self.target),
                argv=["mise", "run", "test", "--", "tests.test_wave_verdict"],
                failures=failing_set([]),
            ),
        )
        args["--gate-receipt"] = str(candidate)
        args["--focused-gate-receipt"] = [str(focused)]
        args["--baseline-comparison"] = str(self.compare_baseline(baseline, candidate))
        return args


class JourneyTests(WaveCase):
    """Two end-to-end journeys, driving the real producers by subprocess with no mocks."""

    def test_an_accepted_wave_is_derived_from_the_real_tools_end_to_end(self) -> None:
        document = self.derive(self.accepted_args())
        self.assertEqual(document["state"], ACCEPTED, self.reasons(document))
        self.assertEqual(document["reasons"], [])
        self.assertTrue(all(item["met"] for item in document["conditions"]))
        self.assertEqual(len(document["conditions"]), 8)
        self.assertTrue(document["repository_gate_passes"])
        self.assertTrue(document["permits_normal_delivery"])
        self.assertEqual(document["wave_id"], WAVE_ID)
        self.assertEqual(document["mission_id"], MISSION_ID)
        self.assertEqual(document["target"], str(self.target))
        self.assertEqual(document["gate"]["outcome"], "passed")
        self.assertEqual(document["gate"]["authoritative_gate"], AUTHORITATIVE_GATE)
        # The journal's own digest, re-derived from the projection's entries and matched against the
        # anchor the conductor retained.
        self.assertEqual(document["evidence"]["journal_digest"], self.journal_digest)
        self.assertEqual(document["evidence"]["plan_digest"], PLAN_DIGEST)
        self.assertEqual(document["evidence"]["required_nodes_without_disposition"], [])
        self.assertEqual(document["evidence"]["runtime_classified_nodes"], sorted(OUTPUTS))
        self.assertEqual(document["evidence"]["reviewed_workstreams"], [IMPLEMENTER])
        self.assertEqual(document["evidence"]["integrator_nodes"], [INTEGRATOR])
        self.assertEqual(document["evidence"]["declared_artifacts"], sorted(OUTPUTS.values()))
        # A wave MAY complete carrying Seeds: the seed-worthy finding is published, not suppressed.
        self.assertEqual([item["finding_id"] for item in document["critic"]["seed_worthy_findings"]], ["finding-1"])
        self.assertEqual(document["critic"]["blocking_findings"], [])
        self.assertTrue(document["critic"]["supplied"])

    def test_a_remediation_wave_reaches_remediation_progress_and_never_claims_the_gate_passes(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.baseline_exit, 0, "the real comparison must report non-worsening")
        document = self.derive(args)
        self.assertEqual(document["state"], REMEDIATION_PROGRESS, self.reasons(document))
        self.assertEqual(document["reasons"], [])
        self.assertTrue(all(item["met"] for item in document["conditions"]))
        # The machine-checkable denials, both derived rather than stated in prose.
        self.assertIs(document["repository_gate_passes"], False)
        self.assertIs(document["permits_normal_delivery"], False)
        self.assertEqual(document["gate"]["outcome"], "failed")
        self.assertEqual(document["gate"]["failing_tests"], CANDIDATE_FAILURES)
        self.assertIs(document["gate"]["baseline_non_worsening"], True)
        self.assertIs(document["gate"]["baseline_toolchain_drifted"], False)
        self.assertEqual(document["gate"]["focused_gates"], [{"gate": FOCUSED_GATE, "outcome": "passed"}])
        # The denial is machine-checkable through the two booleans above; this checks the prose cannot
        # contradict them. A blunt `assertNotIn("write-ready")` would fail on the consequence's own
        # DENIAL, so what is asserted is that every occurrence of the phrase is inside that denial.
        rendered = json.dumps(document)
        denial = "it does not claim the repository is write-ready"
        self.assertIn(denial, document["consequence"])
        self.assertEqual(rendered.count("write-ready"), rendered.count(denial))
        self.assertNotIn("write_ready", rendered, "no field may be named for a readiness this verdict lacks")
        self.assertNotIn("write-ready", json.dumps(document["evidence"]) + json.dumps(document["gate"]))


class GateTests(WaveCase):
    """Condition 6: the admitted gate contract, and the exact line between the two ready states."""

    def test_an_unobserved_gate_reaches_neither_ready_state(self) -> None:
        args = self.accepted_args()
        # POSITIVE CONTROL: the same wave with the observed passing receipt is accepted, so this test
        # cannot pass by failing to assemble a wave at all.
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--gate-receipt"] = str(
            self.store(
                "gate-receipt-unobserved",
                gate_receipt(gate=AUTHORITATIVE_GATE, status=None, cwd=str(self.target), argv=None),
            )
        )
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("produced no verdict (outcome unobserved)", self.reasons(document))
        self.assertFalse(document["permits_normal_delivery"])
        self.assertFalse(self.condition(document, 6)["met"])
        # `repository_gate_passes` answers "did the authoritative gate pass", so an unobserved gate is
        # False -- it did not -- and `gate.outcome` carries the distinction from a gate that ran and
        # failed. `None` is reserved for the one case where the question was never asked: no receipt.
        self.assertIs(document["repository_gate_passes"], False)
        self.assertEqual(document["gate"]["outcome"], "unobserved")
        args.pop("--gate-receipt")
        absent = self.derive(args)
        self.assertIsNone(absent["repository_gate_passes"])
        self.assertIsNone(absent["gate"]["outcome"])

    def test_an_unobserved_gate_cannot_reach_remediation_progress_either(self) -> None:
        args = self.remediation_args()
        # POSITIVE CONTROL: the failing-but-baselined receipt reaches remediation-progress.
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args["--gate-receipt"] = str(
            self.store(
                "gate-receipt-unobserved",
                gate_receipt(gate=AUTHORITATIVE_GATE, status=None, cwd=str(self.target), argv=None),
            )
        )
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("outcome unobserved", self.reasons(document))

    def test_an_unparsed_failing_set_can_never_reach_remediation_progress(self) -> None:
        args = self.remediation_args()
        # POSITIVE CONTROL: the identified failing set reaches remediation-progress.
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args["--gate-receipt"] = str(
            self.store(
                "gate-receipt-unparsed",
                gate_receipt(
                    gate=AUTHORITATIVE_GATE,
                    status=1,
                    cwd=str(self.target),
                    failures=failing_set([], state="unparsed"),
                ),
            )
        )
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("failing set is unparsed", self.reasons(document))
        self.assertIn("not an exact set of names", self.reasons(document))

    def test_a_failed_gate_with_no_failing_set_at_all_was_never_baselined(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args["--gate-receipt"] = str(
            self.store("gate-receipt-bare", gate_receipt(gate=AUTHORITATIVE_GATE, status=1, cwd=str(self.target)))
        )
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("was never baselined", self.reasons(document))

    def test_a_worsened_baseline_blocks(self) -> None:
        # POSITIVE CONTROL: the subset candidate reaches remediation-progress. The journal is
        # append-only and never re-initialised, so a second wave needs a fresh fixture.
        self.assertEqual(self.derive(self.remediation_args())["state"], REMEDIATION_PROGRESS)
        self.setUp()
        args = self.remediation_args(candidate_failures=[*BASELINE_FAILURES, "tests.test_new.Case.test_broken"])
        self.assertEqual(self.baseline_exit, 5, "the real comparison must report the worsened set")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("worsens the global failure baseline", self.reasons(document))
        self.assertIn("tests.test_new.Case.test_broken", self.reasons(document))
        self.assertIs(document["gate"]["baseline_non_worsening"], False)

    def test_a_focused_receipt_for_the_authoritative_gate_cannot_stand_in_for_a_focused_gate(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args["--focused-gate-receipt"] = [
            str(
                self.store(
                    "focused-is-authoritative",
                    gate_receipt(gate=AUTHORITATIVE_GATE, status=0, cwd=str(self.target), failures=failing_set([])),
                )
            )
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is about the authoritative gate", self.reasons(document))

    def test_a_focused_gate_that_did_not_pass_blocks(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args["--focused-gate-receipt"] = [
            str(
                self.store(
                    "focused-red",
                    gate_receipt(
                        gate=FOCUSED_GATE,
                        status=1,
                        cwd=str(self.target),
                        argv=["mise", "run", "test"],
                        failures=failing_set(["tests.test_focused.Case.test_x"]),
                    ),
                )
            )
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("did not pass", self.reasons(document))

    def test_a_failed_gate_with_no_focused_gate_has_no_remediation_evidence(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args.pop("--focused-gate-receipt")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("no focused gate receipt was supplied", self.reasons(document))

    def test_a_focused_gate_from_another_snapshot_blocks(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        elsewhere = self.root / "other-tree"
        elsewhere.mkdir()
        args["--focused-gate-receipt"] = [
            str(
                self.store(
                    "focused-elsewhere",
                    gate_receipt(
                        gate=FOCUSED_GATE,
                        status=0,
                        cwd=str(elsewhere),
                        argv=["mise", "run", "test"],
                        failures=failing_set([]),
                    ),
                )
            )
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("not the integrated snapshot", self.reasons(document))

    def test_a_focused_gate_under_a_different_pinned_toolchain_blocks(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args["--focused-gate-receipt"] = [
            str(
                self.store(
                    "focused-drifted",
                    gate_receipt(
                        gate=FOCUSED_GATE,
                        status=0,
                        cwd=str(self.target),
                        argv=["mise", "run", "test"],
                        failures=failing_set([]),
                        toolchain=b"a different mise.lock",
                    ),
                )
            )
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("different pinned toolchain", self.reasons(document))

    def test_a_receipt_for_a_gate_other_than_the_named_authoritative_one_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--gate-receipt"] = str(
            self.store(
                "hook-receipt",
                gate_receipt(gate="lefthook pre-commit", status=0, cwd=str(self.target), failures=failing_set([])),
            )
        )
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("not the named authoritative gate", self.reasons(document))

    def test_an_unnamed_authoritative_gate_blocks_even_with_a_passing_receipt(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args.pop("--authoritative-gate")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("no authoritative gate was named", self.reasons(document))

    def test_a_passing_gate_supplied_beside_focused_gates_is_ambiguous(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--focused-gate-receipt"] = [
            str(
                self.store(
                    "focused-beside-green",
                    gate_receipt(
                        gate=FOCUSED_GATE,
                        status=0,
                        cwd=str(self.target),
                        argv=["mise", "run", "test"],
                        failures=failing_set([]),
                    ),
                )
            )
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("leaves which verdict is being claimed ambiguous", self.reasons(document))

    def test_a_baseline_comparison_about_another_receipt_blocks(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        other = self.store(
            "other-candidate",
            gate_receipt(
                gate=AUTHORITATIVE_GATE,
                status=1,
                cwd=str(self.target),
                failures=failing_set(["tests.test_legacy.Case.test_two"]),
            ),
        )
        baseline = self.work / "gate-baseline-receipt.json"
        args["--baseline-comparison"] = str(self.compare_baseline(baseline, other))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("does not compare this gate receipt", self.reasons(document))

    def test_a_red_gate_with_no_baseline_comparison_is_not_proven_non_worsening(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args.pop("--baseline-comparison")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("no baseline comparison was supplied", self.reasons(document))
        self.assertIsNone(document["gate"]["baseline_non_worsening"])

    def test_a_baseline_comparison_about_a_different_gate_blocks(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        # Hand-edited, because `gate_baseline.py` refuses to COMPARE two different gates at all: the
        # composer must not take a report's own gate on trust just because a producer usually agrees.
        report = json.loads((self.work / "baseline-report.json").read_text(encoding="utf-8"))
        report["gate"] = "mise run test"
        args["--baseline-comparison"] = str(self.store("baseline-other-gate", report))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is about a different gate", self.reasons(document))

    def test_a_baseline_measured_under_a_drifted_toolchain_blocks(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        drifted = self.store(
            "drifted-baseline-receipt",
            gate_receipt(
                gate=AUTHORITATIVE_GATE,
                status=1,
                cwd=str(self.target),
                failures=failing_set(BASELINE_FAILURES),
                toolchain=b"the previous mise.lock",
            ),
        )
        args["--baseline-comparison"] = str(
            self.compare_baseline(drifted, self.work / "gate-receipt.json")
        )
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("different pinned toolchain", self.reasons(document))
        self.assertIs(document["gate"]["baseline_toolchain_drifted"], True)

    def test_a_comparison_that_states_no_boolean_non_worsening_blocks(self) -> None:
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        report = json.loads((self.work / "baseline-report.json").read_text(encoding="utf-8"))
        report["non_worsening"] = "yes"
        args["--baseline-comparison"] = str(self.store("baseline-report-mistyped", report))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("does not state non_worsening as a boolean", self.reasons(document))


class DispositionTests(WaveCase):
    """Condition 1: every required node reaches one of issue 07's three dispositions."""

    def test_a_required_node_without_a_disposition_blocks(self) -> None:
        # POSITIVE CONTROL: with every required node recorded, the same wave is accepted.
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [step for step in self.journal_steps() if step[1].get("node_id") != REVIEWER]
        args = self.accepted_args_over(steps)
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn(f"required node(s) reached no disposition at all: {REVIEWER}", self.reasons(document))
        self.assertFalse(self.condition(document, 1)["met"])
        self.assertEqual(document["evidence"]["required_nodes_without_disposition"], [REVIEWER])

    def test_an_explicitly_blocked_required_node_blocks_the_wave(self) -> None:
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = []
        for verb, record, at in self.journal_steps():
            if record.get("node_id") == INTEGRATOR:
                record = node_record(
                    INTEGRATOR,
                    "integrator",
                    "blocked",
                    at,
                    reasons=["the merge-base footprint check found a conflicting hunk"],
                    outputs=[],
                )
            steps.append((verb, record, at))
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("reached the explicit blocked disposition", self.reasons(document))
        # Issue 07 admits `blocked` AS a disposition, so condition 1 is about completeness: it is
        # unmet here only because a blocked required node may not be carried into completion, and the
        # reason says exactly that rather than claiming the node has no disposition.
        self.assertNotIn("reached no disposition at all", self.reasons(document))
        self.assertEqual(document["evidence"]["required_nodes_blocked"], [INTEGRATOR])
        self.assertEqual(document["evidence"]["required_nodes_without_disposition"], [])
        # A blocked integrator also means no fan-in HAPPENED, which is condition 5's own fact rather
        # than a restatement of condition 1's.
        self.assertIn("reached no admitted-success, so no authorized fan-in happened", self.reasons(document))
        self.assertFalse(self.condition(document, 5)["met"])


class SubstitutionTests(WaveCase):
    """Condition 2: runtime receipts contain no unexplained substitution, and every node is covered."""

    def test_an_unexplained_substitution_blocks(self) -> None:
        args = self.accepted_args()
        # POSITIVE CONTROL: with the exact-match classifications the same wave is accepted.
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        substituted = self.classify(
            IMPLEMENTER, served_record(IMPLEMENTER, served={"model_id": "claude-haiku-4-5"})
        )
        document = json.loads(substituted.read_text(encoding="utf-8"))
        self.assertEqual(document["verdict"], "unexplained-substitution", "the real classifier must so verdict")
        args["--runtime-classification"] = [
            str(substituted),
            *[str(self.classify(node)) for node in sorted(OUTPUTS) if node != IMPLEMENTER],
        ]
        derived = self.derive(args)
        self.assertEqual(derived["state"], BLOCKED)
        self.assertIn(f"node {IMPLEMENTER} was served an unexplained substitution", self.reasons(derived))
        self.assertFalse(self.condition(derived, 2)["met"])

    def test_a_spawned_node_with_no_classification_is_uncovered_rather_than_clean(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--runtime-classification"] = [
            str(self.classify(node)) for node in sorted(OUTPUTS) if node != INTEGRATOR
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("reached admitted-success with no runtime substitution classification", self.reasons(document))
        self.assertIn(INTEGRATOR, self.reasons(document))

    def test_no_classification_at_all_leaves_the_condition_unproven(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args.pop("--runtime-classification")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("no runtime substitution classification was supplied for any node", self.reasons(document))

    def test_an_unrecognised_classification_verdict_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        classification = json.loads(Path(args["--runtime-classification"][0]).read_text(encoding="utf-8"))
        classification["verdict"] = "probably-fine"
        classification["blocks_wave_completion"] = False
        args["--runtime-classification"] = [str(self.store("classification-odd", classification))]
        done = self.derive_failure(args)
        self.assertIn(b"which is not one of", done.stderr)

    def test_a_classification_naming_no_node_is_malformed_input(self) -> None:
        args = self.accepted_args()
        classification = json.loads(Path(args["--runtime-classification"][0]).read_text(encoding="utf-8"))
        classification["evidence"]["node"] = None
        args["--runtime-classification"] = [str(self.store("classification-nodeless", classification))]
        done = self.derive_failure(args)
        self.assertIn(b"names no node in evidence.node", done.stderr)

    def test_two_classifications_about_one_node_are_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        first = args["--runtime-classification"][0]
        args["--runtime-classification"] = [*args["--runtime-classification"], first]
        done = self.derive_failure(args)
        self.assertIn(b"two runtime substitution classifications are about node", done.stderr)

    def test_a_classification_about_a_foreign_node_is_not_evidence_about_this_wave(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--runtime-classification"] = [
            *args["--runtime-classification"],
            str(self.classify("another-wave-node")),
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("this journal does not carry", self.reasons(document))
        self.assertIn("another-wave-node", self.reasons(document))


class ReviewTests(WaveCase):
    """Condition 4: workstream reviews are accepted, by an independent reviewer, after the work."""

    def test_an_unreviewed_workstream_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args.pop("--review")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn(f"reached admitted-success with no accepted review: {IMPLEMENTER}", self.reasons(document))
        self.assertFalse(self.condition(document, 4)["met"])

    def test_a_rejected_review_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--review"] = [
            str(self.write_review(verdict="rejected", reasons=["the containment check is missing"], name="review-red"))
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is rejected, not accepted", self.reasons(document))
        self.assertIn("the containment check is missing", self.reasons(document))

    def test_an_unrecognised_review_verdict_is_not_an_acceptance(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--review"] = [str(self.write_review(verdict="looks-fine-to-me", name="review-odd"))]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("an unrecognised verdict is not an acceptance", self.reasons(document))

    def test_a_self_review_is_not_an_acceptance(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--review"] = [str(self.write_review(reviewer=IMPLEMENTER, name="review-self"))]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("accepted its own workstream", self.reasons(document))

    def test_a_review_from_a_node_that_is_not_a_reviewer_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--review"] = [str(self.write_review(reviewer=INTEGRATOR, name="review-by-integrator"))]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("whose role in this journal is integrator", self.reasons(document))

    def test_a_review_recorded_before_the_work_it_reviews_blocks(self) -> None:
        # The reviewer node is recorded BEFORE the implementer, so its acceptance cannot have
        # inspected that result. POSITIVE CONTROL: the ordinary order is accepted.
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [
            ("init", header_record(), T0),
            ("record-approval", approval_record(), T1),
            ("record-node", node_record(REVIEWER, "reviewer", "admitted-success", T2), T2),
            ("record-node", node_record(IMPLEMENTER, "implementer", "admitted-success", T3), T3),
            ("record-node", node_record(INTEGRATOR, "integrator", "admitted-success", T4), T4),
            ("record-budget", budget_record(), T5),
        ]
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("before the work it reviews", self.reasons(document))

    def test_a_review_naming_a_node_the_journal_does_not_carry_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--review"] = [str(self.write_review(subject="a-workstream-nobody-ran", name="review-ghost"))]
        subject = self.derive(args)
        self.assertEqual(subject["state"], BLOCKED)
        self.assertIn("names subject node a-workstream-nobody-ran, which this journal does not carry", self.reasons(subject))
        args["--review"] = [str(self.write_review(reviewer="a-reviewer-nobody-ran", name="review-ghost-reviewer"))]
        reviewer = self.derive(args)
        self.assertEqual(reviewer["state"], BLOCKED)
        self.assertIn("names reviewer node a-reviewer-nobody-ran", self.reasons(reviewer))

    def test_a_wave_whose_workstream_was_skipped_has_no_reviewed_result(self) -> None:
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [
            ("init", header_record(), T0),
            ("record-approval", approval_record(), T1),
            (
                "record-approval",
                approval_record(
                    approval_id="approval-skip-a", subject="skip the workstream", scope=[IMPLEMENTER]
                ),
                T1,
            ),
            (
                "record-node",
                node_record(
                    IMPLEMENTER, "implementer", "approved-skip", T2, approval="approval-skip-a", outputs=[]
                ),
                T2,
            ),
            ("record-node", node_record(REVIEWER, "reviewer", "admitted-success", T3), T3),
            ("record-node", node_record(INTEGRATOR, "integrator", "admitted-success", T4), T4),
            ("record-budget", budget_record(), T5),
        ]
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("no implementer node that reached admitted-success", self.reasons(document))
        self.assertFalse(self.condition(document, 4)["met"])

    def test_an_accepted_review_with_no_evidence_asserts_rather_than_records(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--review"] = [str(self.write_review(evidence=[], name="review-bare"))]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("carries no evidence", self.reasons(document))


class FanInTests(WaveCase):
    """Condition 5: fan-in was authorized, by an approval this journal carries, before the merge."""

    def test_a_missing_fan_in_authorization_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args.pop("--fan-in-approval")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("no fan-in approval was named", self.reasons(document))
        self.assertFalse(self.condition(document, 5)["met"])

    def test_a_named_approval_the_journal_does_not_carry_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--fan-in-approval"] = "approval-that-was-never-recorded"
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is not recorded in this journal", self.reasons(document))

    def test_an_approval_whose_scope_does_not_name_the_integrator_blocks(self) -> None:
        # The hole this closes: any approval id would satisfy a mere existence test, including a skip
        # approval for an unrelated workstream. POSITIVE CONTROL: the in-scope approval is accepted.
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = []
        for verb, record, at in self.journal_steps():
            if record.get("approval_id") == FAN_IN_APPROVAL:
                record = approval_record(scope=["some-other-workstream"])
            steps.append((verb, record, at))
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("does not name the integrator node", self.reasons(document))

    def test_a_fan_in_recorded_before_its_approval_blocks(self) -> None:
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [
            ("init", header_record(), T0),
            ("record-node", node_record(IMPLEMENTER, "implementer", "admitted-success", T1), T1),
            ("record-node", node_record(REVIEWER, "reviewer", "admitted-success", T2), T2),
            ("record-node", node_record(INTEGRATOR, "integrator", "admitted-success", T3), T3),
            ("record-approval", approval_record(), T4),
            ("record-budget", budget_record(), T5),
        ]
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("an authorization recorded after the mutation is not one", self.reasons(document))

    def test_a_wave_with_no_integrator_node_cannot_meet_the_condition(self) -> None:
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [
            step
            for step in self.journal_steps()
            if step[1].get("node_id") != INTEGRATOR
        ]
        steps[0] = ("init", header_record(required_nodes=[IMPLEMENTER, REVIEWER]), T0)
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("carries no integrator node", self.reasons(document))


class ArtifactTests(WaveCase):
    """Condition 3: declared artifacts validate and match the recorded repository state."""

    def test_a_declared_artifact_whose_digest_does_not_re_derive_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        (self.target / OUTPUTS[IMPLEMENTER]).write_bytes(b"an edit nobody declared\n")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("does not match its recorded sha256", self.reasons(document))
        self.assertFalse(self.condition(document, 3)["met"])

    def test_a_declared_artifact_that_is_absent_from_the_target_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        (self.target / OUTPUTS[REVIEWER]).unlink()
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("cannot be read in the target", self.reasons(document))

    def test_an_output_absent_from_the_manifest_was_never_validated(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        manifest = json.loads((self.work / "manifest.json").read_text(encoding="utf-8"))
        manifest["artifacts"] = [
            item for item in manifest["artifacts"] if item["path"] != OUTPUTS[INTEGRATOR]
        ]
        args["--artifact-manifest"] = str(self.store("manifest-short", manifest))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("absent from the artifact manifest", self.reasons(document))
        self.assertIn(OUTPUTS[INTEGRATOR], self.reasons(document))

    def test_an_escaping_declared_path_is_named_rather_than_read(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        outside = self.root / "outside.txt"
        outside.write_bytes(b"not in the target\n")
        manifest = json.loads((self.work / "manifest.json").read_text(encoding="utf-8"))
        manifest["artifacts"].append({"path": "../outside.txt", "sha256": sha256_hex(b"not in the target\n")})
        args["--artifact-manifest"] = str(self.store("manifest-escape", manifest))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("not a contained repository-relative path", self.reasons(document))
        # The escaping path's own digest MATCHES the file outside the target, so a tool that read it
        # would have found nothing wrong; the reason has to come from containment, not from hashing.
        self.assertNotIn("does not match its recorded sha256", self.reasons(document))

    def test_an_absolute_declared_path_is_named_rather_than_read(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        manifest = json.loads((self.work / "manifest.json").read_text(encoding="utf-8"))
        manifest["artifacts"].append({"path": "/etc/hostname", "sha256": "0" * 64})
        args["--artifact-manifest"] = str(self.store("manifest-absolute", manifest))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("not a contained repository-relative path", self.reasons(document))

    def test_a_symlinked_declared_artifact_is_named_rather_than_followed(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        outside = self.root / "secret.txt"
        outside.write_bytes(b"the content of src/feature.py\n")
        target_file = self.target / OUTPUTS[IMPLEMENTER]
        target_file.unlink()
        target_file.symlink_to(outside)
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is a symlink", self.reasons(document))

    def test_a_recorded_digest_that_is_not_a_sha256_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        manifest = json.loads((self.work / "manifest.json").read_text(encoding="utf-8"))
        manifest["artifacts"][0]["sha256"] = "NOTADIGEST"
        args["--artifact-manifest"] = str(self.store("manifest-bad-digest", manifest))
        done = self.derive_failure(args)
        self.assertIn(b"64 lowercase hex characters", done.stderr)

    def test_a_directory_declared_as_an_artifact_is_not_a_regular_file(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        (self.target / "generated").mkdir()
        manifest = json.loads((self.work / "manifest.json").read_text(encoding="utf-8"))
        manifest["artifacts"].append({"path": "generated", "sha256": "0" * 64})
        args["--artifact-manifest"] = str(self.store("manifest-directory", manifest))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is not a regular file in the target", self.reasons(document))

    def test_a_manifest_that_declares_nothing_validates_nothing(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        manifest = json.loads((self.work / "manifest.json").read_text(encoding="utf-8"))
        manifest["artifacts"] = []
        args["--artifact-manifest"] = str(self.store("manifest-empty", manifest))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("declares no artifact at all", self.reasons(document))


class TraceabilityTests(WaveCase):
    """Condition 7: budgets, retries, plan revisions, and approvals lead back to something."""

    def test_an_overrun_budget_with_no_reason_blocks(self) -> None:
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = []
        for verb, record, at in self.journal_steps():
            if record.get("budget_id"):
                record = budget_record(limit=2, consumed=5, reasons=[])
            steps.append((verb, record, at))
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is overrun by 3 nodes and states no reason", self.reasons(document))
        self.assertFalse(self.condition(document, 7)["met"])

    def test_an_overrun_budget_that_states_its_reason_is_traceable(self) -> None:
        # The positive half of the same guard: an overrun is a FACT the journal must be able to carry,
        # so the reason is what makes it traceable, not the overrun that makes it fatal.
        self.setUp()
        steps = []
        for verb, record, at in self.journal_steps():
            if record.get("budget_id"):
                record = budget_record(
                    limit=2, consumed=5, reasons=["the operator raised the node budget mid-wave at turn 52"]
                )
            steps.append((verb, record, at))
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], ACCEPTED, self.reasons(document))
        self.assertTrue(self.condition(document, 7)["met"])

    def test_a_wave_with_no_budget_record_has_not_tracked_consumption(self) -> None:
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [step for step in self.journal_steps() if not step[1].get("budget_id")]
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("records no budget at all", self.reasons(document))

    def test_a_plan_revision_chain_that_does_not_lead_back_to_the_approved_plan_blocks(self) -> None:
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [
            *self.journal_steps(),
            (
                "record-approval",
                approval_record(approval_id="approval-revision-1", subject="approve the revised graph", scope=["plan"]),
                T5,
            ),
            (
                "record-plan-revision",
                {
                    "revision_id": "revision-1",
                    "from_plan_digest": "c" * 64,
                    "to_plan_digest": "b" * 64,
                    "approval": "approval-revision-1",
                    "reasons": ["the reviewer found the graph missing a fan-in node"],
                },
                T5,
            ),
        ]
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("which is neither the plan the wave opened with", self.reasons(document))

    def test_a_plan_revision_that_leads_back_to_the_approved_plan_is_traceable(self) -> None:
        self.setUp()
        steps = [
            *self.journal_steps(),
            (
                "record-approval",
                approval_record(approval_id="approval-revision-1", subject="approve the revised graph", scope=["plan"]),
                T5,
            ),
            (
                "record-plan-revision",
                {
                    "revision_id": "revision-1",
                    "from_plan_digest": PLAN_DIGEST,
                    "to_plan_digest": "b" * 64,
                    "approval": "approval-revision-1",
                    "reasons": ["the reviewer found the graph missing a fan-in node"],
                },
                T5,
            ),
        ]
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], ACCEPTED, self.reasons(document))

    def test_a_plan_revision_that_states_no_origin_digest_breaks_the_chain(self) -> None:
        # `from_plan_digest` is OPTIONAL to `wave-journal.py`, so a real journal can carry a revision
        # with no origin at all. That is a different fact from an origin that disagrees, and it needs
        # its own reason. POSITIVE CONTROL: the same wave with the chained origin is accepted.
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [
            *self.journal_steps(),
            (
                "record-approval",
                approval_record(approval_id="approval-revision-1", subject="approve the revised graph", scope=["plan"]),
                T5,
            ),
            (
                "record-plan-revision",
                {
                    "revision_id": "revision-1",
                    "from_plan_digest": None,
                    "to_plan_digest": "b" * 64,
                    "approval": "approval-revision-1",
                    "reasons": ["the graph gained a fan-in node"],
                },
                T5,
            ),
        ]
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("states no from_plan_digest, so the chain back to the approved plan is broken", self.reasons(document))

    def test_a_retry_over_a_node_that_reached_no_disposition_is_untraceable(self) -> None:
        self.assertEqual(self.derive(self.accepted_args())["state"], ACCEPTED)
        self.setUp()
        steps = [
            ("init", header_record(), T0),
            ("record-approval", approval_record(), T1),
            (
                "record-retry",
                {
                    "node_id": "cartograph-a",
                    "attempt": 2,
                    "capability": "read-only",
                    "prior_effect": "none",
                    "evidence": ["attempt 1 transcript"],
                    "reason": "the first attempt lost its transport before reading any artifact",
                },
                T1,
            ),
            ("record-node", node_record(IMPLEMENTER, "implementer", "admitted-success", T2), T2),
            ("record-node", node_record(REVIEWER, "reviewer", "admitted-success", T3), T3),
            ("record-node", node_record(INTEGRATOR, "integrator", "admitted-success", T4), T4),
            ("record-budget", budget_record(), T5),
        ]
        document = self.derive(self.accepted_args_over(steps))
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("which reached no disposition in this journal", self.reasons(document))


class ConductorRecordTests(WaveCase):
    """Condition 8: the conductor's record of the verdict, anchored to the exact journal it read."""

    def test_a_truncated_journal_tail_fails_the_conductors_head_anchor(self) -> None:
        """The one thing the journal's own chain cannot catch, caught here.

        Removing the LAST line leaves a self-consistent chain and a projection that re-derives its own
        digest perfectly, so nothing inside the file objects. The conductor's retained anchor is the
        only value that came from outside it, and it is what refuses.
        """
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        lines = self.journal.read_bytes().splitlines(keepends=True)
        self.journal.write_bytes(b"".join(lines[:-1]))
        truncated = self.journal_run("project")
        self.assertNotEqual(truncated["journal_digest"], self.journal_digest)
        args["--journal-projection"] = str(self.store("projection-truncated", truncated))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is not this projection's", self.reasons(document))
        self.assertIn("truncated at its tail", self.reasons(document))
        self.assertFalse(self.condition(document, 8)["met"])

    def test_a_missing_conductor_record_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args.pop("--conductor-record")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("no conductor record was supplied", self.reasons(document))

    def test_a_conductor_record_stamped_before_the_last_entry_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_conductor_record(recorded_at=T1))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("before the journal's last entry", self.reasons(document))

    def test_an_anchor_that_is_not_a_sha256_is_malformed_input(self) -> None:
        # Separate from a MISMATCHED anchor: a value that cannot be a digest means the record is not
        # the document it claims to be, which is exit 2 rather than a reason about the wave.
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_conductor_record(journal_digest="not-a-digest"))
        done = self.derive_failure(args)
        self.assertIn(b"journal_digest that is not 64 lowercase hex characters", done.stderr)

    def test_a_conductor_record_about_another_wave_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_conductor_record(wave_id="wave-2"))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("names wave 'wave-2'", self.reasons(document))

    def test_a_recorded_at_with_an_arabic_indic_digit_is_malformed_input(self) -> None:
        """Python's `re` `\\d` matches every Unicode `Nd` digit, not only ASCII 0-9.

        `wave-submission.py`'s instant grammar is anchored on `[0-9]` and refuses this exact string;
        this module's `_TIME` must refuse it too rather than silently admitting it. T6, the ASCII form
        of the same instant and `write_conductor_record`'s default, is this test's own positive
        control: the only change below is one character's script, never its value.
        """
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        arabic_indic_recorded_at = "٢" + T6[1:]
        args["--conductor-record"] = str(self.write_conductor_record(recorded_at=arabic_indic_recorded_at))
        done = self.derive_failure(args)
        self.assertIn(b"recorded_at", done.stderr)
        self.assertIn(b"is not a YYYY-MM-DDTHH:MM:SSZ instant", done.stderr)


class EndedStateCase(WaveCase):
    """Shared assertions for Implementation Decision 61's three ended states.

    Every test here starts from the SAME complete, gate-passing, `accepted` argument set and changes
    only how the conductor's record says the execution ended, so the positive control is the control
    every test asserts first: if the ended state stopped overriding, these tests would derive
    `accepted` and fail.
    """

    def assert_ending_overrides(self, document: dict[str, Any], state: str, ended: str) -> None:
        self.assertEqual(document["state"], state, self.reasons(document))
        # The eight conditions are untouched: the completion evidence IS all there, and what the ended
        # state overrides is the conclusion drawn from it, never a condition's own finding.
        self.assertTrue(all(item["met"] for item in document["conditions"]), document["conditions"])
        self.assertFalse(document["permits_normal_delivery"])
        # The receipt's fact survives in `gate`; the top-level CLAIM does not, because an execution
        # that did not reach its end never proved that snapshot is this wave's result.
        self.assertIsNone(document["repository_gate_passes"])
        self.assertEqual(document["gate"]["outcome"], "passed")
        self.assertEqual(document["evidence"]["ended_state"], ended)
        self.assertEqual(
            document["evidence"]["last_proven_stage"], "the reviewer's acceptance of implement-a"
        )
        self.assertEqual(
            document["evidence"]["ended_reasons"],
            [f"the wave's execution ended {ended} while the integrator was merging"],
        )
        self.assertEqual(
            [account["ended_state"] for account in document["evidence"]["ended_accounts"]], [ended]
        )
        self.assertIn(f"says the execution ended {ended}", self.reasons(document))
        self.assertIn("last proven stage", self.reasons(document))


class AbortedOutcomeTests(EndedStateCase):
    """`aborted`: the execution was stopped before it completed."""

    def test_an_aborted_execution_overrides_a_complete_gate_passing_evidence_set(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_ended_record(ABORTED, "record-aborted"))
        document = self.derive(args)
        self.assert_ending_overrides(document, ABORTED, ABORTED)
        self.assertIn("stopped before it completed", document["consequence"])
        self.assertIn("never that the wave delivered", document["consequence"])

    def test_an_aborted_execution_with_no_reason_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        # POSITIVE CONTROL: the substantiated record derives `aborted`, so the refusal below is about
        # the missing reason and not about the state.
        args["--conductor-record"] = str(self.write_ended_record(ABORTED, "record-aborted"))
        self.assertEqual(self.derive(args)["state"], ABORTED)
        args["--conductor-record"] = str(
            self.write_conductor_record(
                name="record-unstated",
                ended_state=ABORTED,
                ended_reasons=[],
                last_proven_stage="the reviewer's acceptance of implement-a",
            )
        )
        done = self.derive_failure(args)
        self.assertIn(b"ended aborted and names no reason", done.stderr)

    def test_an_aborted_execution_with_no_last_proven_stage_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_ended_record(ABORTED, "record-aborted"))
        self.assertEqual(self.derive(args)["state"], ABORTED)
        args["--conductor-record"] = str(
            self.write_ended_record(ABORTED, "record-stageless", last_proven_stage=None)
        )
        done = self.derive_failure(args)
        self.assertIn(b"last_proven_stage is None rather than a non-empty string", done.stderr)


class FailedOutcomeTests(EndedStateCase):
    """`failed`: the execution ran and ended failed."""

    def test_a_failed_execution_overrides_a_complete_gate_passing_evidence_set(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_ended_record(FAILED, "record-failed"))
        document = self.derive(args)
        self.assert_ending_overrides(document, FAILED, FAILED)
        self.assertIn("ran and ended failed", document["consequence"])
        self.assertIn("not a completed wave", document["consequence"])

    def test_a_failed_execution_still_derives_failed_when_the_gate_receipt_is_red(self) -> None:
        """A red gate would be `blocked` on its own; the ending is what the state comes from."""
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)
        args["--conductor-record"] = str(self.write_ended_record(FAILED, "record-failed"))
        document = self.derive(args)
        self.assertEqual(document["state"], FAILED, self.reasons(document))
        self.assertIsNone(document["repository_gate_passes"])
        self.assertEqual(document["gate"]["outcome"], "failed")
        self.assertFalse(document["permits_normal_delivery"])

    def test_an_ended_state_outside_the_four_tokens_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_ended_record(FAILED, "record-failed"))
        self.assertEqual(self.derive(args)["state"], FAILED)
        args["--conductor-record"] = str(self.write_ended_record("mostly-failed", "record-vague"))
        done = self.derive_failure(args)
        self.assertIn(b"declares ended_state 'mostly-failed'", done.stderr)
        self.assertIn(b"not an ending this module may rank", done.stderr)


class UnknownEffectOutcomeTests(EndedStateCase):
    """`unknown-effect`: the execution ended leaving an effect of unknown extent."""

    def test_an_unknown_effect_overrides_a_complete_gate_passing_evidence_set(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_ended_record(UNKNOWN_EFFECT, "record-unknown"))
        document = self.derive(args)
        self.assert_ending_overrides(document, UNKNOWN_EFFECT, UNKNOWN_EFFECT)
        self.assertIn("effect of unknown extent", document["consequence"])
        self.assertIn("recovery, not completion", document["consequence"])
        self.assertIn("no later record may talk this state down", document["consequence"])

    def test_the_unknown_effect_residual_says_the_effect_is_named_and_never_bounded(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(self.write_ended_record(UNKNOWN_EFFECT, "record-unknown"))
        document = self.derive(args)
        self.assertEqual(document["state"], UNKNOWN_EFFECT)
        self.assertTrue(
            any("never bounded" in residual for residual in document["residuals"]),
            document["residuals"],
        )
        # POSITIVE CONTROL over the same assertion shape: the residual that WAS there before this
        # state existed is still published, so the check above is about an addition and not about a
        # rewritten list.
        self.assertTrue(
            any("freshness is underivable" in residual for residual in document["residuals"]),
            document["residuals"],
        )


class EndedStatePrecedenceTests(WaveCase):
    """The fold itself: dominance, the peer refusal, and what `completed` does not do."""

    def test_an_unknown_effect_outranks_a_failed_account_recorded_beside_it(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = [
            str(self.write_ended_record(FAILED, "record-failed")),
            str(self.write_ended_record(UNKNOWN_EFFECT, "record-unknown")),
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], UNKNOWN_EFFECT, self.reasons(document))
        self.assertEqual(document["evidence"]["ended_state"], UNKNOWN_EFFECT)
        self.assertIn("an unknown effect outranks every other recorded ending (failed)", self.reasons(document))
        # Both accounts are published; the outranked one is never dropped.
        self.assertEqual(
            sorted(account["ended_state"] for account in document["evidence"]["ended_accounts"]),
            [FAILED, UNKNOWN_EFFECT],
        )

    def test_the_order_of_the_two_accounts_does_not_change_the_dominant_ending(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        first = str(self.write_ended_record(UNKNOWN_EFFECT, "record-unknown"))
        second = str(self.write_ended_record(ABORTED, "record-aborted"))
        args["--conductor-record"] = [first, second]
        self.assertEqual(self.derive(args)["state"], UNKNOWN_EFFECT)
        args["--conductor-record"] = [second, first]
        self.assertEqual(self.derive(args)["state"], UNKNOWN_EFFECT)

    def test_a_later_completed_account_never_talks_down_a_recorded_ending(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = [
            str(self.write_ended_record(UNKNOWN_EFFECT, "record-unknown")),
            str(self.write_conductor_record(name="record-completed")),
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], UNKNOWN_EFFECT, self.reasons(document))
        self.assertIn("never talks down a recorded ending", self.reasons(document))

    def test_two_disagreeing_peer_endings_are_refused_rather_than_picked(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = [
            str(self.write_ended_record(FAILED, "record-failed")),
            str(self.write_ended_record(ABORTED, "record-aborted")),
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED, self.reasons(document))
        self.assertIn("state different endings", self.reasons(document))
        self.assertIn("no ended state is picked", self.reasons(document))
        # NOTHING is published as the ending, because publishing one would be the pick this refuses.
        self.assertIsNone(document["evidence"]["ended_state"])
        self.assertIsNone(document["evidence"]["last_proven_stage"])
        self.assertEqual(document["evidence"]["ended_reasons"], [])
        self.assertEqual(
            sorted(account["ended_state"] for account in document["evidence"]["ended_accounts"]),
            [ABORTED, FAILED],
        )

    def test_an_ending_outranks_the_named_reasons_that_would_otherwise_block(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        # An unreviewed workstream is `blocked` on its own; the recorded ending is what this derives.
        args.pop("--review")
        args["--conductor-record"] = str(self.write_ended_record(ABORTED, "record-aborted"))
        document = self.derive(args)
        self.assertEqual(document["state"], ABORTED, self.reasons(document))
        self.assertFalse(self.condition(document, 4)["met"])
        self.assertIn("with no accepted review", self.reasons(document))

    def test_a_completed_account_falls_through_to_the_evidence_derived_states(self) -> None:
        """`completed` overrides nothing: all three older derivations must still be reachable."""
        args = self.accepted_args()
        accepted = self.derive(args)
        self.assertEqual(accepted["state"], ACCEPTED)
        self.assertIsNone(accepted["evidence"]["ended_state"])
        self.assertEqual(accepted["evidence"]["ended_accounts"], [
            {
                "ended_reasons": [],
                "ended_state": "completed",
                "last_proven_stage": None,
                "record": args["--conductor-record"],
            }
        ])
        self.assertTrue(accepted["repository_gate_passes"])
        self.assertTrue(accepted["permits_normal_delivery"])
        args.pop("--review")
        blocked = self.derive(args)
        self.assertEqual(blocked["state"], BLOCKED)
        self.setUp()
        remediation = self.derive(self.remediation_args())
        self.assertEqual(remediation["state"], REMEDIATION_PROGRESS)

    def test_two_completed_accounts_publish_the_latest_stamp_and_no_ending(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = [
            str(self.write_conductor_record(name="record-early", recorded_at=T5)),
            str(self.write_conductor_record(name="record-late", recorded_at=T6)),
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], ACCEPTED, self.reasons(document))
        self.assertEqual(document["evidence"]["conductor_recorded_at"], T6)
        self.assertIsNone(document["evidence"]["ended_state"])

    def test_a_second_record_is_validated_rather_than_overwritten_by_the_last_one(self) -> None:
        """The reason `--conductor-record` repeats at all: argparse would have kept only the last."""
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = [
            str(self.write_conductor_record(name="record-stale", journal_digest="b" * 64)),
            str(self.write_conductor_record(name="record-good")),
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED, self.reasons(document))
        self.assertIn(f"retained journal_digest {'b' * 64} is not this projection's", self.reasons(document))
        self.assertFalse(self.condition(document, 8)["met"])

    def test_two_accounts_of_the_same_ending_publish_no_single_last_proven_stage(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = [
            str(self.write_ended_record(FAILED, "record-failed-one")),
            str(
                self.write_ended_record(
                    FAILED, "record-failed-two", last_proven_stage="the implementer's second attempt"
                )
            ),
        ]
        document = self.derive(args)
        self.assertEqual(document["state"], FAILED, self.reasons(document))
        # Two stages, so neither is published as THE stage; both stay in the accounts.
        self.assertIsNone(document["evidence"]["last_proven_stage"])
        self.assertEqual(
            sorted(account["last_proven_stage"] for account in document["evidence"]["ended_accounts"]),
            ["the implementer's second attempt", "the reviewer's acceptance of implement-a"],
        )


class EndedFactsInputTests(WaveCase):
    """The three ended keys are present or absent AS A GROUP, and contradictions are exit 2."""

    def test_a_record_with_no_ended_state_at_all_is_a_named_reason_rather_than_a_completed_one(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        record = json.loads(Path(args["--conductor-record"]).read_text(encoding="utf-8"))
        for key in ("ended_state", "ended_reasons", "last_proven_stage"):
            del record[key]
        args["--conductor-record"] = str(self.store("record-silent", record))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED, self.reasons(document))
        self.assertIn("records no ended_state", self.reasons(document))
        self.assertIn("how the execution ended is unrecorded", self.reasons(document))
        self.assertFalse(self.condition(document, 8)["met"])
        self.assertIsNone(document["evidence"]["ended_state"])
        self.assertEqual(document["evidence"]["ended_accounts"], [])

    def test_ended_facts_carried_without_the_state_they_belong_to_are_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        record = json.loads(Path(args["--conductor-record"]).read_text(encoding="utf-8"))
        del record["ended_state"]
        record["ended_reasons"] = ["the integrator's merge stopped part-way"]
        args["--conductor-record"] = str(self.store("record-orphan", record))
        done = self.derive_failure(args)
        self.assertIn(b"present or absent AS A GROUP", done.stderr)

    def test_partial_ended_key_group_membership_is_malformed_input(self) -> None:
        """The exact gap: a record carrying two of the three ended keys must never derive silently.

        POSITIVE CONTROLS bracket the negative cases: the all-three form (the shared fixture's default)
        derives normally, and the zero-of-three legacy form still takes the named condition-8 path --
        the group rule refuses only the two shapes in between.
        """
        args = self.accepted_args()
        # POSITIVE CONTROL: all three keys present derives normally.
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        base = json.loads(Path(args["--conductor-record"]).read_text(encoding="utf-8"))

        # POSITIVE CONTROL: zero of three keys present still takes the named condition-8 path.
        silent = dict(base)
        for key in ("ended_state", "ended_reasons", "last_proven_stage"):
            del silent[key]
        args["--conductor-record"] = str(self.store("record-partial-silent", silent))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED, self.reasons(document))
        self.assertIn("records no ended_state", self.reasons(document))
        self.assertIn("how the execution ended is unrecorded", self.reasons(document))
        self.assertFalse(self.condition(document, 8)["met"])
        self.assertIsNone(document["evidence"]["ended_state"])
        self.assertEqual(document["evidence"]["ended_accounts"], [])

        # NEGATIVE: exactly two of three present, the third key entirely ABSENT (not null).
        shapes = {
            "ended_state and ended_reasons present, last_proven_stage absent": ("last_proven_stage",),
            "ended_state and last_proven_stage present, ended_reasons absent": ("ended_reasons",),
        }
        for description, drop_keys in shapes.items():
            with self.subTest(description):
                record = dict(base)
                for key in drop_keys:
                    del record[key]
                args["--conductor-record"] = str(
                    self.store(f"record-partial-{'-'.join(drop_keys)}", record)
                )
                done = self.derive_failure(args)
                self.assertIn(b"present or absent AS A GROUP", done.stderr)

    def test_a_completed_record_that_names_an_ending_reason_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(
            self.write_conductor_record(
                name="record-arguing", ended_reasons=["the integrator's merge stopped part-way"]
            )
        )
        done = self.derive_failure(args)
        self.assertIn(b"says the execution completed and still names ended_reasons", done.stderr)

    def test_a_completed_record_that_names_a_last_proven_stage_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(
            self.write_conductor_record(name="record-staged", last_proven_stage="the fan-in")
        )
        done = self.derive_failure(args)
        self.assertIn(b"says the execution completed and names last_proven_stage", done.stderr)

    def test_ended_reasons_that_are_not_a_list_of_strings_are_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--conductor-record"] = str(
            self.write_ended_record(FAILED, "record-prose", ended_reasons="the merge stopped")
        )
        done = self.derive_failure(args)
        self.assertIn(b"carries ended_reasons 'the merge stopped'", done.stderr)


class CriticTests(WaveCase):
    """The conductor's own classification of the critic's advice."""

    def test_an_unresolved_blocking_finding_blocks_while_a_seed_worthy_one_does_not(self) -> None:
        args = self.accepted_args()
        # POSITIVE CONTROL: the seed-worthy finding alone is accepted, and is published as a Seed.
        control = self.derive(args)
        self.assertEqual(control["state"], ACCEPTED)
        self.assertEqual([item["finding_id"] for item in control["critic"]["seed_worthy_findings"]], ["finding-1"])
        args["--critic-findings"] = str(self.write_findings([self.seed_worthy_finding(), self.blocking_finding()]))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is an unresolved safety-regression", self.reasons(document))
        # The Seed survives the blocker: the conductor still has something to queue.
        self.assertEqual([item["finding_id"] for item in document["critic"]["seed_worthy_findings"]], ["finding-1"])
        self.assertEqual([item["finding_id"] for item in document["critic"]["blocking_findings"]], ["finding-blocker"])

    def test_every_named_blocking_kind_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        for kind in (
            "acceptance-criteria-violation",
            "corrupted-evidence",
            "failed-authoritative-gate",
            "safety-regression",
        ):
            with self.subTest(kind=kind):
                args["--critic-findings"] = str(self.write_findings([self.blocking_finding(kind=kind)]))
                document = self.derive(args)
                self.assertEqual(document["state"], BLOCKED)
                self.assertIn(f"is an unresolved {kind}", self.reasons(document))

    def test_every_named_seed_worthy_kind_completes(self) -> None:
        args = self.accepted_args()
        for kind in ("complexity", "documentation", "enhancement", "maintainability"):
            with self.subTest(kind=kind):
                args["--critic-findings"] = str(self.write_findings([self.seed_worthy_finding(kind=kind)]))
                document = self.derive(args)
                self.assertEqual(document["state"], ACCEPTED, self.reasons(document))
                self.assertEqual(document["critic"]["seed_worthy_findings"][0]["kind"], kind)

    def test_an_unclassifiable_finding_kind_blocks_rather_than_being_assumed_harmless(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--critic-findings"] = str(self.write_findings([self.seed_worthy_finding(kind="vibes")]))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("is neither a named blocking kind", self.reasons(document))
        self.assertIn("blocks rather than being assumed non-blocking", self.reasons(document))

    def test_a_resolved_blocker_must_name_a_remediation_node_the_journal_admits(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--critic-findings"] = str(
            self.write_findings([self.blocking_finding(resolved=True, resolution=None)])
        )
        bare = self.derive(args)
        self.assertEqual(bare["state"], BLOCKED)
        self.assertIn("names no remediation node", self.reasons(bare))
        args["--critic-findings"] = str(
            self.write_findings([self.blocking_finding(resolved=True, resolution="a-node-nobody-recorded")])
        )
        unknown = self.derive(args)
        self.assertEqual(unknown["state"], BLOCKED)
        self.assertIn("reached no disposition in this journal", self.reasons(unknown))
        # POSITIVE CONTROL for the same channel: a blocker resolved by a node that DID reach an
        # admitted success completes, so `resolved` is not simply ignored.
        args["--critic-findings"] = str(
            self.write_findings([self.blocking_finding(resolved=True, resolution=IMPLEMENTER)])
        )
        resolved = self.derive(args)
        self.assertEqual(resolved["state"], ACCEPTED, self.reasons(resolved))

    def test_a_wave_with_no_critic_findings_has_no_adversarial_disposition(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args.pop("--critic-findings")
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("has no adversarial disposition", self.reasons(document))
        self.assertFalse(document["critic"]["supplied"])

    def test_findings_about_another_wave_block(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--critic-findings"] = str(self.write_findings(wave_id="wave-9"))
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("names wave 'wave-9'", self.reasons(document))


class BindingTests(WaveCase):
    """One verdict is about ONE wave in ONE tree; honest documents from two of either do not compose."""

    def test_a_manifest_and_receipt_from_two_targets_block(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        elsewhere = self.root / "other-tree"
        elsewhere.mkdir()
        args["--gate-receipt"] = str(
            self.store(
                "receipt-elsewhere",
                gate_receipt(gate=AUTHORITATIVE_GATE, status=0, cwd=str(elsewhere), failures=failing_set([])),
            )
        )
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("names a different target", self.reasons(document))

    def test_a_review_about_another_wave_blocks(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--review"] = [str(self.write_review(wave_id="wave-7", name="review-foreign"))]
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("names wave 'wave-7'", self.reasons(document))


class MalformedInputTests(WaveCase):
    """Exit 2: the question could not be asked. No result document is written at all."""

    def test_a_projection_whose_entries_do_not_derive_its_digest_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        projection = json.loads((self.work / "projection.json").read_text(encoding="utf-8"))
        projection["journal_digest"] = "f" * 64
        args["--journal-projection"] = str(self.store("projection-bad-digest", projection))
        done = self.derive_failure(args)
        self.assertIn(b"which its own entries do not re-derive", done.stderr)

    def test_a_projection_whose_entry_chain_was_edited_is_malformed_input(self) -> None:
        args = self.accepted_args()
        projection = json.loads((self.work / "projection.json").read_text(encoding="utf-8"))
        projection["entries"][2]["record"]["disposition"] = "blocked"
        args["--journal-projection"] = str(self.store("projection-edited", projection))
        done = self.derive_failure(args)
        self.assertIn(b"prev_digest does not re-derive", done.stderr)

    def test_a_projection_whose_summary_field_disagrees_with_its_entries_is_malformed_input(self) -> None:
        args = self.accepted_args()
        projection = json.loads((self.work / "projection.json").read_text(encoding="utf-8"))
        projection["required_nodes_without_disposition"] = ["a-node-nobody-required"]
        args["--journal-projection"] = str(self.store("projection-lying-summary", projection))
        done = self.derive_failure(args)
        self.assertIn(b"required_nodes_without_disposition", done.stderr)

    def test_a_classification_whose_summary_contradicts_its_verdict_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        classification = json.loads(Path(args["--runtime-classification"][0]).read_text(encoding="utf-8"))
        self.assertEqual(classification["verdict"], "exact-match")
        classification["blocks_wave_completion"] = True
        args["--runtime-classification"] = [str(self.store("classification-lying", classification))]
        done = self.derive_failure(args)
        self.assertIn(b"blocks_wave_completion", done.stderr)

    def test_a_receipt_whose_self_digest_does_not_re_derive_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        receipt = json.loads((self.work / "gate-receipt.json").read_text(encoding="utf-8"))
        receipt["status"] = 1
        args["--gate-receipt"] = str(self.store("receipt-forged", receipt))
        done = self.derive_failure(args)
        self.assertIn(b"self_digest does not re-derive", done.stderr)

    def test_a_receipt_whose_outcome_its_status_does_not_derive_is_malformed_input(self) -> None:
        args = self.accepted_args()
        receipt = gate_receipt(gate=AUTHORITATIVE_GATE, status=1, cwd=str(self.target), failures=failing_set([]))
        receipt["outcome"] = "passed"
        receipt["self_digest"] = receipt_digest({k: v for k, v in receipt.items() if k != "self_digest"})
        args["--gate-receipt"] = str(self.store("receipt-relabelled", receipt))
        done = self.derive_failure(args)
        self.assertIn(b"which its status", done.stderr)

    def test_a_duplicate_json_key_is_refused_rather_than_silently_resolved(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        path = self.work / "conductor-duplicate.json"
        path.write_text(
            '{"schema":"' + CONDUCTOR_RECORD_SCHEMA + '","wave_id":"' + WAVE_ID + '",'
            '"journal_digest":"' + self.journal_digest + '","recorded_by":"conductor",'
            '"recorded_at":"' + T6 + '","verdict_destination":"a","verdict_destination":"b"}',
            encoding="utf-8",
        )
        args["--conductor-record"] = str(path)
        done = self.derive_failure(args)
        self.assertIn(b"repeats the JSON key", done.stderr)

    def test_an_entry_declaring_the_wrong_seq_is_malformed_input(self) -> None:
        """The LAST entry's seq, because that is the one no later line's digest depends on.

        Editing any earlier entry's seq breaks the chain and is refused by the digest check instead, so
        this is the only input that reaches the sequence check on its own.
        """
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        projection = json.loads((self.work / "projection.json").read_text(encoding="utf-8"))
        projection["entries"][-1] = dict(projection["entries"][-1], seq=99)
        projection["journal_digest"] = sha256_hex(b"".join(canonical(item) for item in projection["entries"]))
        args["--journal-projection"] = str(self.store("projection-misnumbered", projection))
        done = self.derive_failure(args)
        self.assertIn(b"the entries were reordered or a gap was left", done.stderr)

    def test_a_receipt_carrying_an_unknown_field_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        receipt = json.loads((self.work / "gate-receipt.json").read_text(encoding="utf-8"))
        del receipt["self_digest"]
        receipt["reviewed_by"] = "somebody"
        receipt["self_digest"] = receipt_digest(receipt)
        args["--gate-receipt"] = str(self.store("receipt-extra-field", receipt))
        done = self.derive_failure(args)
        self.assertIn(b"does not carry exactly a gate receipt's fields", done.stderr)

    def test_a_projection_that_is_not_a_projected_result_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        projection = json.loads((self.work / "projection.json").read_text(encoding="utf-8"))
        projection["status"] = "refused"
        args["--journal-projection"] = str(self.store("projection-refused", projection))
        done = self.derive_failure(args)
        self.assertIn(b"is not a projected result", done.stderr)

    def test_a_wrong_schema_tag_is_malformed_input(self) -> None:
        args = self.accepted_args()
        projection = json.loads((self.work / "projection.json").read_text(encoding="utf-8"))
        projection["schema"] = "agentic-sdlc/wave-journal-projection@2"
        args["--journal-projection"] = str(self.store("projection-future", projection))
        self.derive_failure(args)

    def test_an_absent_artifact_path_is_malformed_input_rather_than_a_reason(self) -> None:
        args = self.accepted_args()
        args["--conductor-record"] = str(self.work / "no-such-file.json")
        done = self.derive_failure(args)
        self.assertIn(b"cannot read the conductor record", done.stderr)

    def test_a_directory_supplied_as_an_artifact_is_malformed_input(self) -> None:
        args = self.accepted_args()
        args["--critic-findings"] = str(self.work)
        done = self.derive_failure(args)
        self.assertIn(b"is not a regular file", done.stderr)

    def test_a_finding_with_no_evidence_is_malformed_input(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        args["--critic-findings"] = str(self.write_findings([self.seed_worthy_finding(evidence=[])]))
        done = self.derive_failure(args)
        self.assertIn(b"carries no evidence", done.stderr)

    def test_a_hundred_thousand_deep_conductor_record_is_classified_not_a_crash(self) -> None:
        """The seed's own scenario: `json`'s C scanner overflows its OWN C stack once per nesting
        level, independent of `sys.setrecursionlimit`. The positive control proves THIS
        interpreter's build actually raises `RecursionError` on a bare `json.loads` at this depth --
        asserting a classified refusal at a depth that never trips the underlying bug (as the
        pre-existing weaker check elsewhere in this family used depth 2000, which never reaches the
        failure at all) would prove nothing.
        """
        depth = 100_000
        text = '{"a":' * depth + "1" + "}" * depth
        try:
            json.loads(text)
        except RecursionError:
            pass
        else:
            self.skipTest("this interpreter's build did not raise RecursionError at 100,000 levels")
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)  # positive control
        nested = self.work / "conductor-nested.json"
        nested.write_text(text, encoding="utf-8")
        args["--conductor-record"] = str(nested)
        done = self.derive_failure(args)
        self.assertIn(b"nests too deeply", done.stderr)
        self.assertNotIn(b"Traceback", done.stderr)

    def test_a_non_finite_number_in_a_field_this_module_never_reads_is_refused(self) -> None:
        """This module imposes no closed key set on the critic-findings, review, artifact-manifest,
        or conductor-record schemas -- `wave-submission.py` seals those four and this module never
        reads the seal -- so an extra top-level field none of `assess_critic` ever looks at is a
        genuinely IGNORED field. Before the document-wide walk, a non-finite `1e400` there was
        admitted completely silently: nothing ever touched the value to notice."""
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)  # positive control
        raw = Path(args["--critic-findings"]).read_text(encoding="utf-8").rstrip()
        self.assertTrue(raw.endswith("}"), "the fixture is not a JSON object")
        injected = raw[:-1] + ', "extra_metric": 1e400}\n'
        nonfinite = self.work / "findings-nonfinite.json"
        nonfinite.write_text(injected, encoding="utf-8")
        args["--critic-findings"] = str(nonfinite)
        done = self.derive_failure(args)
        self.assertIn(b"non-finite number", done.stderr)

    def test_a_non_finite_number_inside_an_array_element_is_refused_too(self) -> None:
        """The walk's list arm, isolated: both prior injections sit at a dict-value position, so a
        walk that never descended into arrays would still pass them while `[1e400]` slid through."""
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)  # positive control
        raw = Path(args["--critic-findings"]).read_text(encoding="utf-8").rstrip()
        self.assertTrue(raw.endswith("}"), "the fixture is not a JSON object")
        injected = raw[:-1] + ', "extra_metrics": [1, 1e400]}\n'
        nonfinite = self.work / "findings-nonfinite-array.json"
        nonfinite.write_text(injected, encoding="utf-8")
        args["--critic-findings"] = str(nonfinite)
        done = self.derive_failure(args)
        self.assertIn(b"non-finite number", done.stderr)
        self.assertNotIn(b"Traceback", done.stderr)

    def test_a_non_finite_number_in_a_published_field_no_longer_crashes_to_exit_one(self) -> None:
        """`assess_gate` publishes `baseline.get("toolchain_drifted")` into `assessment.gate`
        UNCHECKED and UNCONDITIONALLY, and `assessment.gate` is embedded verbatim in the result
        document under `"gate"`. Before the document-wide walk, a non-finite `1e400` there survived
        every check this module runs and only failed once the result document tried to serialize
        itself with `allow_nan=False` -- an uncaught `ValueError` (exit 1), not a classified input
        error (exit 2). The walk in `load_artifact` now catches it before any of that runs."""
        args = self.remediation_args()
        self.assertEqual(self.derive(args)["state"], REMEDIATION_PROGRESS)  # positive control
        raw = Path(args["--baseline-comparison"]).read_text(encoding="utf-8")
        injected, count = re.subn(r'"toolchain_drifted"\s*:\s*(?:true|false)', '"toolchain_drifted": 1e400', raw)
        self.assertEqual(count, 1, "the fixture does not carry exactly one toolchain_drifted field")
        nonfinite = self.work / "baseline-nonfinite.json"
        nonfinite.write_text(injected, encoding="utf-8")
        args["--baseline-comparison"] = str(nonfinite)
        done = self.derive_failure(args)
        self.assertIn(b"non-finite number", done.stderr)
        self.assertNotIn(b"Traceback", done.stderr)


class ForgedProjectionTests(WaveCase):
    """The guards that defend against contents `wave-journal.py` will not record at all.

    `wave-journal.py` cross-checks an approval's existence when it appends a plan revision or an
    approved skip, so no real journal can carry either dangling reference. The composer checks anyway,
    and these tests prove those checks are live rather than decorative by supplying the one input that
    can reach them: a projection whose chain and digest were recomputed after the fact.
    """

    def test_a_plan_revision_naming_an_absent_approval_is_untraceable(self) -> None:
        args = self.accepted_args()
        # POSITIVE CONTROL: the unforged projection is accepted, and the forged one below differs from
        # it by exactly one appended entry.
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        forged = self.forge_projection(
            [
                {
                    "at": T5,
                    "kind": "plan-revision",
                    "record": {
                        "revision_id": "revision-1",
                        "from_plan_digest": PLAN_DIGEST,
                        "to_plan_digest": "b" * 64,
                        "approval": "approval-nobody-recorded",
                        "reasons": ["the graph gained a node"],
                    },
                    "schema": "agentic-sdlc/wave-journal@1",
                }
            ]
        )
        args["--journal-projection"] = str(self.store("projection-forged-revision", forged))
        args["--conductor-record"] = str(self.write_conductor_record())
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("names approval 'approval-nobody-recorded', which this journal does not carry", self.reasons(document))
        self.assertFalse(self.condition(document, 7)["met"])

    def test_an_approved_skip_naming_an_absent_approval_is_untraceable(self) -> None:
        args = self.accepted_args()
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        skipped = node_record("extra-node", "researcher", "approved-skip", T5, approval="approval-absent", outputs=[])
        forged = self.forge_projection(
            [{"at": T5, "kind": "node", "record": skipped, "schema": "agentic-sdlc/wave-journal@1"}],
            dispositions={
                **json.loads((self.work / "projection.json").read_text(encoding="utf-8"))["dispositions"],
                "extra-node": {"at": T5, "disposition": "approved-skip", "role": "researcher", "seq": 6},
            },
        )
        args["--journal-projection"] = str(self.store("projection-forged-skip", forged))
        args["--conductor-record"] = str(self.write_conductor_record())
        document = self.derive(args)
        self.assertEqual(document["state"], BLOCKED)
        self.assertIn("was skipped under approval 'approval-absent'", self.reasons(document))

    def test_a_forged_projection_that_is_consistent_still_derives_its_state(self) -> None:
        """The control for the forging mechanism itself.

        Re-chaining the SAME entries must reproduce the real projection's digest exactly, so a forged
        projection that changed nothing is accepted. Without this, the two tests above could be passing
        because forging breaks every projection rather than because their added entry is the problem.
        """
        args = self.accepted_args()
        real = self.journal_digest
        forged = self.forge_projection([])
        self.assertEqual(forged["journal_digest"], real, "re-chaining unchanged entries must be a no-op")
        args["--journal-projection"] = str(self.store("projection-forged-identity", forged))
        self.assertEqual(self.derive(args)["state"], ACCEPTED)


class ShapeTests(WaveCase):
    """The document's own contract: one fixed key set, canonical bytes, and a closed exit space."""

    def test_every_state_carries_the_same_key_set(self) -> None:
        accepted = self.derive(self.accepted_args())
        self.setUp()
        remediation = self.derive(self.remediation_args())
        self.setUp()
        blocked = self.derive({})
        # Decision 61's other three, over one wave each: adding three states to the vocabulary must
        # not have added a key to the document or moved a fact out of `evidence`.
        endings = []
        for ended in (ABORTED, FAILED, UNKNOWN_EFFECT):
            self.setUp()
            args = self.accepted_args()
            args["--conductor-record"] = str(self.write_ended_record(ended, f"record-{ended}"))
            document = self.derive(args)
            self.assertEqual(document["state"], ended, self.reasons(document))
            endings.append(document)
        self.assertEqual(accepted["state"], ACCEPTED)
        self.assertEqual(remediation["state"], REMEDIATION_PROGRESS)
        self.assertEqual(blocked["state"], BLOCKED)
        for other in (remediation, blocked, *endings):
            self.assertEqual(sorted(accepted), sorted(other))
            self.assertEqual(sorted(accepted["critic"]), sorted(other["critic"]))
            self.assertEqual(sorted(accepted["gate"]), sorted(other["gate"]))
            self.assertEqual(sorted(accepted["evidence"]), sorted(other["evidence"]))
            self.assertEqual(
                [item["number"] for item in accepted["conditions"]],
                [item["number"] for item in other["conditions"]],
            )
            self.assertEqual(sorted(accepted["conditions"][0]), sorted(other["conditions"][0]))

    def test_the_document_is_canonical_bytes_with_one_trailing_newline(self) -> None:
        done = self.run_tool(*self.argv(self.accepted_args()))
        self.assertEqual(done.returncode, EXIT_OK)
        self.assertEqual(done.stdout, canonical(json.loads(done.stdout)))
        self.assertTrue(done.stdout.endswith(b"}\n"))
        self.assertEqual(done.stdout.count(b"\n"), 1)
        self.assertEqual(done.stdout, done.stdout.decode("ascii").encode("ascii"))

    def test_deriving_blocked_with_no_artifacts_is_success_and_names_every_condition(self) -> None:
        document = self.derive({})
        self.assertEqual(document["state"], BLOCKED)
        self.assertEqual([item["met"] for item in document["conditions"]], [False] * 8)
        self.assertEqual(
            [item["slug"] for item in document["conditions"]],
            [
                "required-node-dispositions",
                "no-unexplained-substitution",
                "declared-artifacts-validate",
                "workstream-reviews-accepted",
                "fan-in-authorized",
                "gate-contract-passes",
                "budgets-retries-revisions-approvals-traceable",
                "conductor-records-verdict",
            ],
        )
        # Every reason names what was missing: none of them is a bare "cannot determine".
        for reason in document["reasons"]:
            self.assertNotIn("cannot determine", reason)
            self.assertGreater(len(reason), 40, reason)

    def test_the_reasons_list_is_exactly_the_conditions_reasons_plus_the_critics(self) -> None:
        document = self.derive({})
        flat = [reason for item in document["conditions"] for reason in item["reasons"]]
        self.assertEqual(document["reasons"], flat + document["critic"]["reasons"])

    def test_a_grammar_error_is_exit_two_and_writes_no_result_document(self) -> None:
        done = self.run_tool("derive", "--not-a-flag")
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertEqual(done.stdout, b"")
        done = self.run_tool()
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertEqual(done.stdout, b"")

    def test_the_module_declares_why_three_and_four_are_absent(self) -> None:
        # The claim is checkable, so it is checked: the exit space is stated in the module docstring
        # AND on the command line a caller actually reads.
        collapsed = " ".join(TOOL.read_text(encoding="utf-8").split())
        self.assertIn("a tool that can cause no effect can neither refuse before one nor admit one", collapsed)
        done = self.run_tool("derive", "--help")
        self.assertEqual(done.returncode, EXIT_OK)
        help_text = " ".join(done.stdout.decode("utf-8").split())
        self.assertIn("3 and 4 do not apply", help_text)
        self.assertIn("Exit codes: 0 a terminal state was derived, blocked included", help_text)


class HostileDescriptorTests(WaveCase):
    """A display channel may cost its line; the result document may not be silently lost."""

    def test_a_closed_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        args = self.accepted_args()
        args["--conductor-record"] = str(self.work / "no-such-file.json")
        # POSITIVE CONTROL: with an ordinary stderr the same run exits 2 and says so.
        control = self.run_tool(*self.argv(args))
        self.assertEqual(control.returncode, EXIT_INPUT)
        self.assertIn(b"cannot read the conductor record", control.stderr)
        code, out = run_with_hostile_stderr(
            [sys.executable, "-B", str(TOOL), *self.argv(args)], mode="closed", cwd=self.root
        )
        self.assertEqual(code, EXIT_INPUT)
        self.assertEqual(out, b"", "an input error must emit no result document, even with no stderr")

    def test_an_epipe_stderr_costs_the_diagnostic_and_not_the_exit_code(self) -> None:
        args = self.accepted_args()
        args["--conductor-record"] = str(self.work / "no-such-file.json")
        code, out = run_with_hostile_stderr(
            [sys.executable, "-B", str(TOOL), *self.argv(args)], mode="epipe", cwd=self.root
        )
        self.assertEqual(code, EXIT_INPUT, "a broken stderr must not become exit 120")
        self.assertEqual(out, b"")

    def test_a_grammar_error_with_no_stderr_puts_no_usage_on_stdout(self) -> None:
        code, out = run_with_hostile_stderr(
            [sys.executable, "-B", str(TOOL), "derive", "--not-a-flag"], mode="closed", cwd=self.root
        )
        self.assertEqual(code, EXIT_INPUT)
        self.assertEqual(out, b"", "argparse must not fall back to stdout, where the document lives")

    def test_a_closed_stdout_reports_an_undelivered_document(self) -> None:
        args = self.accepted_args()
        # POSITIVE CONTROL: with an ordinary stdout the same run delivers an accepted document.
        self.assertEqual(self.derive(args)["state"], ACCEPTED)
        code, err = run_with_hostile_stdout(
            [sys.executable, "-B", str(TOOL), *self.argv(args)], mode="closed", cwd=self.root
        )
        self.assertEqual(code, EXIT_INTERNAL)
        self.assertIn(b"handed no stdout", err)

    def test_an_epipe_stdout_reports_an_undelivered_document(self) -> None:
        args = self.accepted_args()
        code, err = run_with_hostile_stdout(
            [sys.executable, "-B", str(TOOL), *self.argv(args)], mode="epipe", cwd=self.root
        )
        self.assertEqual(code, EXIT_INTERNAL, "a broken stdout must not become exit 120")
        self.assertIn(b"not delivered", err)

    def test_help_with_no_stdout_exits_cleanly_instead_of_crashing(self) -> None:
        """`--help` is where argparse writes to STDOUT, so it is where the routing override earns its
        keep. argparse resolves `sys.stdout` itself and then writes to it unguarded: under `1>&-` that
        is `None.write` (an AttributeError traceback, exit 1), and behind a dead reader it is EPIPE
        bytes left pending for the shutdown flush (exit 120). Help was asked for and there is nowhere
        to print it, which is not a failure of this command.
        """
        # POSITIVE CONTROL: with an ordinary stdout, help is printed and exits 0.
        control = self.run_tool("derive", "--help")
        self.assertEqual(control.returncode, EXIT_OK)
        self.assertIn(b"--journal-projection", control.stdout)
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, _ = run_with_hostile_stdout(
                    [sys.executable, "-B", str(TOOL), "derive", "--help"], mode=mode, cwd=self.root
                )
                self.assertEqual(code, EXIT_OK)

    def test_both_streams_hostile_at_once_still_classifies(self) -> None:
        args = self.accepted_args()
        done = subprocess.run(
            ["sh", "-c", 'exec 1>&- 2>&-; exec "$@"', "sh", sys.executable, "-B", str(TOOL), *self.argv(args)],
            cwd=str(self.root),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(done.returncode, EXIT_INTERNAL)


class SealedSubmissionRoundTripTests(WaveCase):
    """The other half of Seed agentic-sdlc-4e5a: the four submissions now have a producer.

    `skills/agentic-sdlc/tools/wave-submission.py` seals all four documents this module validates, so
    the pairing is asserted from THIS side too: a change here that closed a key set, required a
    different field, or rejected the added `digest` would fail here rather than in the producer's own
    module, where it would look like someone else's problem.
    """

    def seal(self, kind: str, body: dict[str, Any], name: str) -> Path:
        """Run the REAL producer over one body and file the sealed document in the canonical form."""
        source = self.store(f"{name}-body", body)
        done = subprocess.run(
            [sys.executable, "-B", str(SUBMISSION_TOOL), "define", "--kind", kind, "--submission", str(source)],
            capture_output=True,
            cwd=str(self.root),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        result = json.loads(done.stdout)
        self.assertEqual(result["verdict"], "defined", " || ".join(result["reasons"]))
        path = self.work / f"{name}-sealed.json"
        path.write_bytes(canonical(result["submission"]))
        return path

    def read(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def sealed_args(self, **record_overrides: Any) -> dict[str, Any]:
        """The accepted argument set with all four same-user assertions replaced by sealed ones."""
        args = self.accepted_args()
        args["--artifact-manifest"] = str(
            self.seal(ARTIFACT_MANIFEST_KIND, self.read(Path(args["--artifact-manifest"])), "manifest")
        )
        args["--review"] = [str(self.seal(REVIEW_KIND, self.read(Path(args["--review"][0])), "review"))]
        args["--critic-findings"] = str(
            self.seal(CRITIC_KIND, self.read(Path(args["--critic-findings"])), "findings")
        )
        record = self.read(Path(args["--conductor-record"]))
        # Asserted rather than assumed: the producer's closed key set requires all three ended keys,
        # so a fixture that stopped carrying them would refuse to seal instead of deriving anything.
        self.assertEqual(record["ended_state"], "completed")
        record.update(record_overrides)
        args["--conductor-record"] = str(self.seal(CONDUCTOR_RECORD_KIND, record, "conductor-record"))
        return args

    def test_an_accepted_wave_is_derived_from_four_sealed_submissions(self) -> None:
        args = self.sealed_args()
        for flag in ("--artifact-manifest", "--conductor-record", "--critic-findings"):
            self.assertIn(b'"digest"', Path(args[flag]).read_bytes(), f"{flag} was not sealed")
        document = self.derive(args)
        self.assertEqual(document["state"], ACCEPTED, self.reasons(document))
        self.assertTrue(all(item["met"] for item in document["conditions"]))
        self.assertEqual(document["evidence"]["declared_artifacts"], sorted(OUTPUTS.values()))
        self.assertEqual(document["evidence"]["reviewed_workstreams"], [IMPLEMENTER])
        self.assertEqual(document["evidence"]["conductor_recorded_at"], T6)

    def reseal_ending(self, args: dict[str, Any], ended: str, name: str) -> None:
        """Re-seal the wave's conductor record with a different ending, through the REAL producer.

        ONE wave, then ONE field changed: `accepted_args` initialises a journal and cannot be called
        twice in a test, and re-sealing only the record is also the tighter comparison.
        """
        record = self.read(Path(args["--conductor-record"]))
        del record["digest"]  # the producer refuses a body that already carries one
        record.update(
            ended_state=ended,
            ended_reasons=[f"the integrator's merge ended {ended} after the second workstream landed"],
            last_proven_stage="the reviewer's acceptance of implement-a",
        )
        args["--conductor-record"] = str(self.seal(CONDUCTOR_RECORD_KIND, record, name))
        self.assertEqual(self.read(Path(args["--conductor-record"]))["ended_state"], ended)

    def test_each_ended_state_the_producer_seals_derives_its_own_outcome(self) -> None:
        """Implementation Decision 61's six values, closed across the producer/consumer seam.

        The record is sealed by the real `wave-submission.py` for each ending, so the tokens this
        module ranks are exactly the tokens that producer will emit: a vocabulary that drifted on
        either side would derive the wrong state here rather than pass quietly on both.
        """
        args = self.sealed_args()
        control = self.derive(args)
        self.assertEqual(control["state"], ACCEPTED, self.reasons(control))
        self.assertIsNone(control["evidence"]["ended_state"])
        for ended, state in ((ABORTED, ABORTED), (FAILED, FAILED), (UNKNOWN_EFFECT, UNKNOWN_EFFECT)):
            with self.subTest(ended=ended):
                self.reseal_ending(args, ended, f"conductor-record-{ended}")
                document = self.derive(args)
                self.assertEqual(document["state"], state, self.reasons(document))
                self.assertEqual(document["evidence"]["ended_state"], ended)
                self.assertFalse(document["permits_normal_delivery"])
                self.assertIsNone(document["repository_gate_passes"])
                # POSITIVE CONTROL: the completion evidence is still complete, so the state came from
                # the ending and not from something the reseal broke.
                self.assertTrue(all(item["met"] for item in document["conditions"]), document["conditions"])

    def test_the_residuals_say_an_ending_nobody_recorded_is_unobservable(self) -> None:
        """The gap that REPLACED the old one: this module reads records, never executions."""
        args = self.sealed_args()
        self.reseal_ending(args, UNKNOWN_EFFECT, "conductor-record-unknown")
        document = self.derive(args)
        self.assertEqual(document["state"], UNKNOWN_EFFECT, self.reasons(document))
        self.assertTrue(
            any(
                "ended_state" in residual and "conductor's own account" in residual
                for residual in document["residuals"]
            ),
            document["residuals"],
        )
        # NEGATIVE: the residual that pinned the old gap is gone, because it is no longer true.
        self.assertFalse(
            any("NOT READ" in residual for residual in document["residuals"]), document["residuals"]
        )
        # POSITIVE CONTROL for that same absence check: a phrase that IS still published is found.
        self.assertTrue(
            any("re-derivation" in residual for residual in document["residuals"]), document["residuals"]
        )


class EnvironmentTests(WaveCase):
    """The tool reads no environment variable, and this module's scrub set is honest about that."""

    def test_the_tool_reads_no_environment_variable(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv", source)
        # POSITIVE CONTROL: the same grep over a tool that DOES read one finds it, so this assertion
        # is about the source rather than about a spelling that never appears anywhere.
        self.assertIn("os.environ", JOURNAL_TOOL.read_text(encoding="utf-8"))

    def test_the_scrub_set_names_every_control_the_spawned_tools_read(self) -> None:
        found = set()
        for tool in (TOOL, JOURNAL_TOOL, RUNTIME_TOOL, BASELINE_TOOL):
            for line in tool.read_text(encoding="utf-8").splitlines():
                if "os.environ.get(" in line and "FAULT_ENV" in line:
                    found.add("AGENTIC_SDLC_WAVE_JOURNAL_FAULT")
        self.assertEqual(found, set(TOOL_CONTROL_ENV))

    def test_a_verdict_does_not_change_when_an_unrelated_variable_is_set(self) -> None:
        args = self.accepted_args()
        first = self.derive(args)
        done = subprocess.run(
            [sys.executable, "-B", str(TOOL), *self.argv(args)],
            capture_output=True,
            cwd=str(self.root),
            check=False,
            env=constructed_environment({"AGENTIC_SDLC_WAVE_VERDICT": "accepted", "TZ": "Pacific/Kiritimati"}),
        )
        self.assertEqual(done.returncode, EXIT_OK)
        self.assertEqual(json.loads(done.stdout), first)


if __name__ == "__main__":
    unittest.main()
