"""Tests for the four wave submissions' producer, its digest, and the consumer that reads them.

Six kinds of test live here and they check different things.

The CROSS-TOOL ROUND-TRIP tests are the point of this module and of the phase it belongs to. Seed
agentic-sdlc-4e5a's whole complaint is that `wave-verdict.py` validated four schemas nothing emitted,
so proving `define` emits documents that tool's OWN validators accept is the only assertion that
closes it. They build a real wave journal by RUNNING `wave-journal.py`, seal each submission by
RUNNING `wave-submission.py`, then run the REAL `wave-verdict.py` over the pair and assert the
condition that consumes the document is MET -- not merely that the run survived. A shape complaint
there is exit 2 with no result document at all, and a digest complaint is a named reason inside
condition 3, 4, or 8, so both failure modes are visible in what is asserted.

The ROUND-TRIP tests seal a body with `define`, then hand the sealed document straight back to
`verify`, so the two commands are proved to agree about the one digest rather than each being proved
against a constant this module chose. `verify --expect-digest` closes the loop a conductor uses.

The NEGATIVE cases each carry a POSITIVE CONTROL in the same test: the unmutated body is asserted to
reach `defined` (or the unmutated sealed document `verified`) FIRST, so a test that stopped exercising
its guard would also have to stop reaching that verdict.

The CANONICAL-FORM tests assert BYTES, not parsed values, and one of them carries a non-ASCII
evidence line, because `ensure_ascii=True` is the half of the canonical form that a JSON round-trip
cannot detect.

The HOSTILE-DESCRIPTOR cases run the tool with a stderr or a stdout it cannot write to -- `2>&-` and
a real pipe whose reader is already gone -- because a display channel must cost the display line and
never the classified exit code, and because the one result document is the evidence: a submission
sealed and not delivered is not a success.

The SOURCE tests read the tool with `ast` rather than by substring, because its own docstring
contains the words "subprocess-free" and "clock", and a substring assertion would fail on the promise
itself.
"""

from __future__ import annotations

import ast
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-submission.py"
#: The two real siblings this module runs. Neither is imported: both names carry a hyphen, so no
#: `import` statement can name them, and running them is what makes the round trip real.
VERDICT_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-verdict.py"
JOURNAL_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-journal.py"

RESULT_SCHEMA = "agentic-sdlc/wave-submission-result@1"
VERDICT_RESULT_SCHEMA = "agentic-sdlc/wave-terminal-verdict@1"
PROJECTION_SCHEMA = "agentic-sdlc/wave-journal-projection@1"

MANIFEST_SCHEMA = "agentic-sdlc/wave-artifact-manifest@1"
REVIEW_SCHEMA = "agentic-sdlc/wave-review-submission@1"
CRITIC_SCHEMA = "agentic-sdlc/wave-critic-findings@1"
CONDUCTOR_RECORD_SCHEMA = "agentic-sdlc/wave-verdict-conductor-record@1"

KIND_MANIFEST = "artifact-manifest"
KIND_REVIEW = "review"
KIND_CRITIC = "critic-findings"
KIND_CONDUCTOR = "conductor-record"

SCHEMA_OF_KIND = {
    KIND_MANIFEST: MANIFEST_SCHEMA,
    KIND_REVIEW: REVIEW_SCHEMA,
    KIND_CRITIC: CRITIC_SCHEMA,
    KIND_CONDUCTOR: CONDUCTOR_RECORD_SCHEMA,
}

DEFINED = "defined"
VERIFIED = "verified"
REFUSED = "refused"

EXIT_OK = 0
#: The undelivered-document code. A result this tool derived but could not put on stdout is neither a
#: success nor an input error, and 120 is not in the module's exit space at all.
EXIT_INTERNAL = 1
EXIT_INPUT = 2

BLOCKED = "blocked"

ENDED_STATES = ("aborted", "completed", "failed", "unknown-effect")

T0 = "2026-08-19T02:00:00Z"
T1 = "2026-08-19T02:01:00Z"
T2 = "2026-08-19T02:02:00Z"
T3 = "2026-08-19T02:03:00Z"
T4 = "2026-08-19T02:04:00Z"
T5 = "2026-08-19T02:05:00Z"
T6 = "2026-08-19T02:06:00Z"

WAVE_ID = "wave-1"
MISSION_ID = "mission-slice-5"
PLAN_DIGEST = "a" * 64
IMPLEMENTER = "implement-a"
REVIEWER = "review-a"
INTEGRATOR = "fan-in"
FAN_IN_APPROVAL = "approval-fan-in"

#: One output per admitted-success node, because the verdict tool's condition 3 requires the manifest
#: to cover every output an admitted-success node declared.
OUTPUTS = {
    IMPLEMENTER: "src/feature.py",
    REVIEWER: "reviews/review-a.json",
    INTEGRATOR: "integration/merge-log.txt",
}

#: The tool under test reads no environment variable at all, and `wave-journal.py` reads exactly one
#: (its fault seam). Every spawn still CONSTRUCTS its environment from this allowlist rather than
#: passing `os.environ` through, so neither a control variable a future version began reading nor a
#: fault variable a developer exported can reach a child from a shell.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")

# `WaveFixtureCase` builds its journal fixture by RUNNING `wave-journal.py init`/`record-*` first, and
# that publish refuses (by name, at exit 3) on a host that lacks this syscall -- so `WaveFixtureCase`
# itself is skipped there rather than every fixture-building test failing downstream. On POSIX this is
# a pure SYMBOL probe, never `sys.platform`, so it can only be false on a host that genuinely lacks the
# syscall; glibc 2.28+ always exports it, so this is never false on the Linux CI runner this suite must
# stay green on. The `os.name` term answers the strictly earlier question of whether
# `ctypes.CDLL(None)` may be CALLED at all: on native Windows it may not (3.12's `CDLL.__init__` takes
# its `_os.name == "nt"` branch and evaluates `'/' in name` with `name=None`, a TypeError), and at
# module scope that would be a loader traceback for this whole file on the windows CI leg instead of a
# named skip. `RenameAt2CapabilityTests` below is this constant's own positive control.
_HAS_RENAMEAT2 = os.name == "posix" and getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None) is not None


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
    """The digest contract, re-expressed so a drifted tool fails rather than agrees with itself.

    sha256 over `canonical(sealed minus the digest key)`. Re-expressed rather than imported: the tool
    has a hyphen in its name, so a plain `import` statement cannot name it, and a shared
    implementation would make this assertion vacuous.
    """
    body = {key: value for key, value in sealed.items() if key != "digest"}
    return hashlib.sha256(canonical(body)).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---- bodies: one valid document per kind, the positive control every negative case starts from ----


def manifest_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "wave_id": WAVE_ID,
        "target": "/repo/checkout",
        "artifacts": [{"path": "src/feature.py", "sha256": "b" * 64}],
    }
    body.update(overrides)
    return body


def review_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": REVIEW_SCHEMA,
        "wave_id": WAVE_ID,
        "subject_node_id": IMPLEMENTER,
        "reviewer_node_id": REVIEWER,
        "verdict": "accepted",
        "evidence": [f"read {IMPLEMENTER}'s immutable diff", "re-ran the focused gate"],
        "reasons": [],
    }
    body.update(overrides)
    return body


def finding(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "finding_id": "finding-1",
        "kind": "complexity",
        "severity": "minor",
        "rationale": "the composer's predicate list could be table-driven",
        "recommended_disposition": "queue a Seed",
        "affected_artifact": "skills/agentic-sdlc/tools/wave-verdict.py",
        "evidence": ["read assess_gate end to end"],
        "resolved": False,
        "resolution": None,
    }
    entry.update(overrides)
    return entry


def critic_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": CRITIC_SCHEMA,
        "wave_id": WAVE_ID,
        "findings": [finding()],
    }
    body.update(overrides)
    return body


def conductor_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": CONDUCTOR_RECORD_SCHEMA,
        "wave_id": WAVE_ID,
        "journal_digest": "c" * 64,
        "recorded_by": "conductor",
        "recorded_at": T6,
        "verdict_destination": "the mission's wave receipt at receipts/wave-1.json",
        "ended_state": "completed",
        "ended_reasons": [],
        "last_proven_stage": None,
    }
    body.update(overrides)
    return body


BODY_OF_KIND = {
    KIND_MANIFEST: manifest_body,
    KIND_REVIEW: review_body,
    KIND_CRITIC: critic_body,
    KIND_CONDUCTOR: conductor_body,
}


# ---- journal records, re-expressed rather than imported across test modules -----------------------


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


def node_record(node_id: str, role: str, ended_at: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "node_id": node_id,
        "role": role,
        "disposition": "admitted-success",
        "inputs": ["plan/wave-1.json"],
        "outputs": [OUTPUTS[node_id]] if node_id in OUTPUTS else [],
        "assignment": {
            "provider": "anthropic",
            "model_id": "claude-sonnet-5",
            "effort": "high",
            "context": "base",
            "resolution_state": "resolved",
        },
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


def run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Re-expressed from the fixture `tests.test_mission_contract` uses for the identical rule, not
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


def imports_and_calls(path: Path) -> tuple[set[str], set[str]]:
    """The module's top-level import names and every called name, read with `ast`.

    A substring search would be fooled by prose: this tool's own docstring contains the word
    "subprocess-free", and an `assertNotIn("subprocess", source)` would fail on the promise itself.
    """
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


class SubmissionCase(unittest.TestCase):
    """The plumbing every test here shares: a scratch tree, and one spawn helper per verb."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.work = self.root / "artifacts"
        self.work.mkdir()

    # ---- plumbing -------------------------------------------------------------------------------

    def store(self, name: str, value: Any) -> Path:
        """Write one document with INDENTED, unsorted JSON.

        Deliberately not canonical: the digest must come from the parsed document re-encoded in the
        canonical form, so a fixture written in the canonical form already would hide a tool that
        digested the file's bytes.
        """
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

    def result(self, *argv: str) -> dict[str, Any]:
        done = self.run_tool(*argv)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        document = json.loads(done.stdout)
        self.assertEqual(document["schema"], RESULT_SCHEMA)
        self.assertEqual(document["exit_code"], EXIT_OK)
        return document

    def define(self, kind: str, body: dict[str, Any], name: str = "body") -> dict[str, Any]:
        return self.result("define", "--kind", kind, "--submission", str(self.store(name, body)))

    def verify(self, kind: str, sealed: dict[str, Any], *extra: str, name: str = "sealed") -> dict[str, Any]:
        return self.result("verify", "--kind", kind, "--submission", str(self.store(name, sealed)), *extra)

    def seal(self, kind: str, body: dict[str, Any], name: str = "sealed-body") -> dict[str, Any]:
        """`define` one body and return the sealed document, asserting it was admitted."""
        document = self.define(kind, body, name=name)
        self.assertEqual(document["verdict"], DEFINED, self.reasons(document))
        self.assertIsNotNone(document["submission"])
        return document["submission"]

    def seal_to_file(self, kind: str, body: dict[str, Any], name: str) -> Path:
        """Seal one body and write it to disk in the CANONICAL form, as a conductor files it."""
        path = self.work / f"{name}.json"
        path.write_bytes(canonical(self.seal(kind, body, name=f"{name}-body")))
        return path

    def refusal(self, kind: str, body: dict[str, Any], command: str = "define", *extra: str) -> dict[str, Any]:
        document = self.result(command, "--kind", kind, "--submission", str(self.store("refused", body)), *extra)
        self.assertEqual(document["verdict"], REFUSED)
        self.assertIsNone(document["submission"], "a refusal must publish no sealed submission")
        self.assertIsNone(document["digest"], "a refusal must publish no digest")
        self.assertTrue(document["reasons"], "a refusal must name at least one reason")
        return document

    @staticmethod
    def reasons(document: dict[str, Any]) -> str:
        return " || ".join(document["reasons"])

    def check(self, document: dict[str, Any], slug: str) -> dict[str, Any]:
        found = [item for item in document["checks"] if item["slug"] == slug]
        self.assertEqual(len(found), 1, f"exactly one check {slug} must be reported")
        return found[0]


@unittest.skipUnless(_HAS_RENAMEAT2, "Linux renameat2 is unavailable")
class WaveFixtureCase(SubmissionCase):
    """A real wave journal, built by RUNNING `wave-journal.py`, plus the real verdict tool over it."""

    def setUp(self) -> None:
        super().setUp()
        self.target = self.root / "repo"
        self.target.mkdir()
        self.journal = self.work / "journal.jsonl"

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

    def build_journal(self) -> Path:
        """The accepted wave: an approval, one workstream, its review, and the fan-in."""
        steps = [
            ("init", header_record(), T0),
            ("record-approval", approval_record(), T1),
            ("record-node", node_record(IMPLEMENTER, "implementer", T2), T2),
            ("record-node", node_record(REVIEWER, "reviewer", T3), T3),
            ("record-node", node_record(INTEGRATOR, "integrator", T4), T4),
        ]
        for verb, record, at in steps:
            self.journal_run(verb, "--at", at, "--record", json.dumps(record))
        projection = self.journal_run("project")
        self.assertEqual(projection["schema"], PROJECTION_SCHEMA)
        self.journal_digest = projection["journal_digest"]
        return self.store("projection", projection)

    def write_target_artifacts(self) -> list[dict[str, str]]:
        """Create every declared output inside the target and measure it, as a conductor does."""
        entries = []
        for relative in sorted(OUTPUTS.values()):
            destination = self.target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = f"the content of {relative}\n".encode("utf-8")
            destination.write_bytes(data)
            entries.append({"path": relative, "sha256": sha256_hex(data)})
        return entries

    def derive(self, **flags: Any) -> dict[str, Any]:
        """Run the REAL `wave-verdict.py derive` and return its one result document at exit 0."""
        argv = ["derive"]
        for flag, value in flags.items():
            if value is None:
                continue
            for item in value if isinstance(value, list) else [value]:
                argv.extend([f"--{flag.replace('_', '-')}", str(item)])
        done = subprocess.run(
            [sys.executable, "-B", str(VERDICT_TOOL), *argv],
            capture_output=True,
            cwd=str(self.root),
            check=False,
            env=constructed_environment(),
        )
        self.assertEqual(
            done.returncode,
            EXIT_OK,
            "the verdict tool refused a sealed submission as malformed input: "
            + done.stderr.decode("utf-8", "replace"),
        )
        document = json.loads(done.stdout)
        self.assertEqual(document["schema"], VERDICT_RESULT_SCHEMA)
        return document

    def condition(self, document: dict[str, Any], number: int) -> dict[str, Any]:
        found = [item for item in document["conditions"] if item["number"] == number]
        self.assertEqual(len(found), 1, f"exactly one condition {number} must be reported")
        return found[0]


class CrossToolRoundTripTests(WaveFixtureCase):
    """The seam Seed agentic-sdlc-4e5a opened: what this tool seals, `wave-verdict.py` consumes.

    Each test asserts the CONSUMING CONDITION IS MET rather than merely that the verdict tool ran. A
    shape complaint would be exit 2 with no result document, which `derive` fails on by name; a
    digest or coverage complaint would be a named reason inside the condition, which `met` catches.
    """

    def test_a_sealed_manifest_meets_condition_3(self) -> None:
        projection = self.build_journal()
        manifest = self.seal_to_file(
            KIND_MANIFEST,
            manifest_body(target=str(self.target), artifacts=self.write_target_artifacts()),
            "manifest",
        )
        document = self.derive(journal_projection=projection, artifact_manifest=manifest)
        condition = self.condition(document, 3)
        self.assertTrue(condition["met"], condition["reasons"])
        self.assertEqual(document["evidence"]["declared_artifacts"], sorted(OUTPUTS.values()))

    def test_a_sealed_review_meets_condition_4(self) -> None:
        projection = self.build_journal()
        review = self.seal_to_file(KIND_REVIEW, review_body(), "review")
        document = self.derive(journal_projection=projection, review=review)
        condition = self.condition(document, 4)
        self.assertTrue(condition["met"], condition["reasons"])
        self.assertEqual(document["evidence"]["reviewed_workstreams"], [IMPLEMENTER])

    def test_a_sealed_conductor_record_meets_condition_8(self) -> None:
        projection = self.build_journal()
        record = self.seal_to_file(
            KIND_CONDUCTOR, conductor_body(journal_digest=self.journal_digest), "conductor-record"
        )
        document = self.derive(journal_projection=projection, conductor_record=record)
        condition = self.condition(document, 8)
        self.assertTrue(condition["met"], condition["reasons"])
        self.assertEqual(document["evidence"]["conductor_recorded_at"], T6)

    def test_sealed_critic_findings_are_classified_with_no_blocking_reason(self) -> None:
        projection = self.build_journal()
        findings = self.seal_to_file(KIND_CRITIC, critic_body(), "critic-findings")
        document = self.derive(journal_projection=projection, critic_findings=findings)
        self.assertTrue(document["critic"]["supplied"])
        self.assertEqual(document["critic"]["reasons"], [])
        self.assertEqual([item["finding_id"] for item in document["critic"]["seed_worthy_findings"]], ["finding-1"])

    def test_a_sealed_blocking_finding_resolved_by_a_real_node_carries_no_reason(self) -> None:
        """The one finding shape whose admission depends on the journal: `resolution` names a node.

        `define` requires a resolved blocking finding to name a remediation node, and the verdict tool
        requires that node to have reached an admitted success in the journal. Sealing one and deriving
        over the real projection is the only way to prove the two requirements are the same one.
        """
        projection = self.build_journal()
        findings = self.seal_to_file(
            KIND_CRITIC,
            critic_body(
                findings=[
                    finding(
                        kind="safety-regression",
                        severity="blocker",
                        resolved=True,
                        resolution=IMPLEMENTER,
                    )
                ]
            ),
            "critic-findings",
        )
        document = self.derive(journal_projection=projection, critic_findings=findings)
        self.assertEqual(document["critic"]["reasons"], [])
        self.assertEqual(document["critic"]["seed_worthy_findings"], [])
        self.assertEqual([item["finding_id"] for item in document["critic"]["blocking_findings"]], ["finding-1"])

    def test_all_four_sealed_submissions_compose_over_one_wave(self) -> None:
        """Every consuming condition met at once, from four sealed documents and one real journal.

        The state is `blocked` because no gate receipt is supplied -- conditions 5, 6, and 7 are unmet
        and say so -- and that is the honest positive control: the four conditions these submissions
        feed are met, and the ones nothing here feeds are not.
        """
        projection = self.build_journal()
        manifest = self.seal_to_file(
            KIND_MANIFEST,
            manifest_body(target=str(self.target), artifacts=self.write_target_artifacts()),
            "manifest",
        )
        review = self.seal_to_file(KIND_REVIEW, review_body(), "review")
        record = self.seal_to_file(
            KIND_CONDUCTOR, conductor_body(journal_digest=self.journal_digest), "conductor-record"
        )
        findings = self.seal_to_file(KIND_CRITIC, critic_body(), "critic-findings")
        document = self.derive(
            journal_projection=projection,
            artifact_manifest=manifest,
            review=review,
            conductor_record=record,
            critic_findings=findings,
        )
        for number in (3, 4, 8):
            condition = self.condition(document, number)
            self.assertTrue(condition["met"], f"condition {number}: {condition['reasons']}")
        self.assertEqual(document["state"], BLOCKED)
        self.assertEqual(document["wave_id"], WAVE_ID)
        self.assertEqual(document["target"], str(self.target))
        self.assertFalse(self.condition(document, 6)["met"], "no gate receipt was supplied")

    def test_the_verdict_tool_reads_the_seal_as_an_ordinary_extra_field(self) -> None:
        """The digest is additive: the same body with and without the seal derives the same condition.

        This is the claim that let Phase A add three ended-state keys and one digest without touching
        the consumer, so it is asserted rather than assumed.
        """
        projection = self.build_journal()
        entries = self.write_target_artifacts()
        body = manifest_body(target=str(self.target), artifacts=entries)
        unsealed = self.work / "manifest-unsealed.json"
        unsealed.write_bytes(canonical(body))
        sealed = self.seal_to_file(KIND_MANIFEST, body, "manifest")
        self.assertIn(b'"digest"', sealed.read_bytes())
        self.assertNotIn(b'"digest"', unsealed.read_bytes())
        for path in (unsealed, sealed):
            document = self.derive(journal_projection=projection, artifact_manifest=path)
            self.assertTrue(self.condition(document, 3)["met"], f"{path.name}: not met")


class RoundTripTests(SubmissionCase):
    """define -> verify, for every kind, with the digest re-expressed independently of the tool."""

    def test_every_kind_round_trips_through_verify(self) -> None:
        for kind in (KIND_MANIFEST, KIND_REVIEW, KIND_CRITIC, KIND_CONDUCTOR):
            with self.subTest(kind=kind):
                sealed = self.seal(kind, BODY_OF_KIND[kind]())
                digest = expected_digest(sealed)
                self.assertEqual(sealed["digest"], digest)
                document = self.verify(kind, sealed, "--expect-digest", digest)
                self.assertEqual(document["verdict"], VERIFIED, self.reasons(document))
                self.assertEqual(document["digest"], digest)
                self.assertEqual(document["submission"], sealed)
                self.assertEqual(document["submission_schema"], SCHEMA_OF_KIND[kind])

    def test_the_sealed_document_differs_from_the_body_by_exactly_the_digest(self) -> None:
        for kind in (KIND_MANIFEST, KIND_REVIEW, KIND_CRITIC, KIND_CONDUCTOR):
            with self.subTest(kind=kind):
                body = BODY_OF_KIND[kind]()
                sealed = self.seal(kind, body)
                self.assertEqual(set(sealed) - set(body), {"digest"})
                self.assertEqual({key: sealed[key] for key in body}, body)

    def test_define_republishes_only_the_facts_its_kind_carries(self) -> None:
        manifest = self.define(KIND_MANIFEST, manifest_body())
        self.assertEqual(manifest["declared_artifacts"], ["src/feature.py"])
        self.assertIsNone(manifest["ended_state"])
        self.assertIsNone(manifest["review_verdict"])
        review = self.define(KIND_REVIEW, review_body(verdict="rejected", reasons=["the diff repairs nothing"]))
        self.assertEqual(review["review_verdict"], "rejected")
        self.assertIsNone(review["declared_artifacts"])
        record = self.define(
            KIND_CONDUCTOR,
            conductor_body(
                ended_state="aborted",
                ended_reasons=["the operator withdrew the wave"],
                last_proven_stage="the reviewer's acceptance",
            ),
        )
        self.assertEqual(record["ended_state"], "aborted")
        self.assertEqual(record["wave_id"], WAVE_ID)

    def test_a_refused_body_publishes_none_of_its_fields(self) -> None:
        control = self.define(KIND_REVIEW, review_body())
        self.assertEqual(control["verdict"], DEFINED)
        self.assertEqual(control["review_verdict"], "accepted")
        document = self.refusal(KIND_REVIEW, review_body(verdict="looks-fine"))
        self.assertIsNone(document["review_verdict"])
        self.assertIsNone(document["wave_id"])
        self.assertIn("looks-fine", self.reasons(document))


class ClosedSchemaTests(SubmissionCase):
    """Every kind's key set is closed, and `define` and `verify` differ by exactly `digest`."""

    def test_an_unknown_field_is_refused_for_every_kind(self) -> None:
        for kind in (KIND_MANIFEST, KIND_REVIEW, KIND_CRITIC, KIND_CONDUCTOR):
            with self.subTest(kind=kind):
                self.assertEqual(self.define(kind, BODY_OF_KIND[kind]())["verdict"], DEFINED)
                document = self.refusal(kind, BODY_OF_KIND[kind](reviewed_by="a human"))
                self.assertIn("reviewed_by", self.reasons(document))
                self.assertIn("closed", self.reasons(document))

    def test_a_missing_required_field_is_refused_by_name_for_every_kind(self) -> None:
        for kind, key in (
            (KIND_MANIFEST, "target"),
            (KIND_REVIEW, "reasons"),
            (KIND_CRITIC, "findings"),
            (KIND_CONDUCTOR, "ended_state"),
        ):
            with self.subTest(kind=kind, key=key):
                body = BODY_OF_KIND[kind]()
                self.assertEqual(self.define(kind, body)["verdict"], DEFINED)
                del body[key]
                self.assertIn(key, self.reasons(self.refusal(kind, body)))

    def test_the_declared_schema_must_match_the_selected_kind(self) -> None:
        self.assertEqual(self.define(KIND_REVIEW, review_body())["verdict"], DEFINED)
        document = self.refusal(KIND_REVIEW, review_body(schema=CRITIC_SCHEMA))
        self.assertIn(CRITIC_SCHEMA, self.reasons(document))
        self.assertIn(REVIEW_SCHEMA, self.reasons(document))

    def test_a_body_carrying_a_digest_is_refused_by_define(self) -> None:
        sealed = self.seal(KIND_CONDUCTOR, conductor_body())
        document = self.refusal(KIND_CONDUCTOR, sealed)
        self.assertIn("already carries a digest", self.reasons(document))

    def test_a_sealed_document_with_no_digest_is_refused_by_verify(self) -> None:
        sealed = self.seal(KIND_CONDUCTOR, conductor_body())
        self.assertEqual(self.verify(KIND_CONDUCTOR, sealed)["verdict"], VERIFIED)
        body = {key: value for key, value in sealed.items() if key != "digest"}
        document = self.refusal(KIND_CONDUCTOR, body, "verify")
        self.assertIn("digest", self.reasons(document))

    def test_a_nested_entry_is_closed_too(self) -> None:
        self.assertEqual(self.define(KIND_CRITIC, critic_body())["verdict"], DEFINED)
        document = self.refusal(KIND_CRITIC, critic_body(findings=[finding(owner="the critic")]))
        self.assertIn("owner", self.reasons(document))
        manifest = self.refusal(
            KIND_MANIFEST, manifest_body(artifacts=[{"path": "src/feature.py", "sha256": "b" * 64, "size": 12}])
        )
        self.assertIn("size", self.reasons(manifest))

    def test_an_identifier_outside_the_journals_own_shape_is_refused(self) -> None:
        for kind, key, value in (
            (KIND_MANIFEST, "wave_id", "wave 1"),
            (KIND_REVIEW, "reviewer_node_id", "-leading-dash"),
            (KIND_CONDUCTOR, "recorded_by", "conductor/one"),
        ):
            with self.subTest(kind=kind, key=key):
                self.assertEqual(self.define(kind, BODY_OF_KIND[kind]())["verdict"], DEFINED)
                document = self.refusal(kind, BODY_OF_KIND[kind](**{key: value}))
                self.assertIn(key, self.reasons(document))
                self.assertIn("wave-journal.py", self.reasons(document))


class ManifestTests(SubmissionCase):
    """Condition 3's declaration, refused in every shape the verdict tool could not validate."""

    def test_a_manifest_declaring_nothing_is_refused(self) -> None:
        self.assertEqual(self.define(KIND_MANIFEST, manifest_body())["verdict"], DEFINED)
        document = self.refusal(KIND_MANIFEST, manifest_body(artifacts=[]))
        self.assertIn("declares no artifact", self.reasons(document))

    def test_a_path_that_escapes_the_target_is_refused(self) -> None:
        for path in ("/etc/passwd", "../outside/secret", "src/../../up", "src\\feature.py", "", ".", ".."):
            with self.subTest(path=path):
                self.assertEqual(self.define(KIND_MANIFEST, manifest_body())["verdict"], DEFINED)
                document = self.refusal(
                    KIND_MANIFEST, manifest_body(artifacts=[{"path": path, "sha256": "b" * 64}])
                )
                self.assertIn("path", self.reasons(document))

    def test_a_leading_dot_slash_collapses_exactly_as_the_verdict_tool_collapses_it(self) -> None:
        """`PurePosixPath` drops every single-dot component, and both tools apply that same collapse.

        Pinned rather than assumed: this is the one spelling where the producer's containment check and
        the consumer's disagree with a naive reading, and they must not disagree with each other. The
        sealed document keeps the caller's spelling -- nothing is normalized -- while the republished
        declared path is the collapsed form the verdict tool would hash.
        """
        for spelling in ("./src/feature.py", "src/./feature.py"):
            with self.subTest(spelling=spelling):
                entries = [{"path": spelling, "sha256": "b" * 64}]
                document = self.define(KIND_MANIFEST, manifest_body(artifacts=entries))
                self.assertEqual(document["verdict"], DEFINED, self.reasons(document))
                self.assertEqual(document["declared_artifacts"], ["src/feature.py"])
                self.assertEqual(document["submission"]["artifacts"], entries)

    def test_one_path_declared_twice_is_refused(self) -> None:
        entries = [{"path": "src/feature.py", "sha256": "b" * 64}, {"path": "src/feature.py", "sha256": "c" * 64}]
        self.assertEqual(self.define(KIND_MANIFEST, manifest_body())["verdict"], DEFINED)
        document = self.refusal(KIND_MANIFEST, manifest_body(artifacts=entries))
        self.assertIn("already declares", self.reasons(document))

    def test_a_sha256_that_is_not_64_lowercase_hex_is_refused(self) -> None:
        for digest in ("B" * 64, "b" * 63, "b" * 65, "not-a-digest", 42, None):
            with self.subTest(digest=digest):
                document = self.refusal(
                    KIND_MANIFEST, manifest_body(artifacts=[{"path": "src/feature.py", "sha256": digest}])
                )
                self.assertIn("sha256", self.reasons(document))

    def test_a_non_object_artifact_entry_is_refused(self) -> None:
        document = self.refusal(KIND_MANIFEST, manifest_body(artifacts=["src/feature.py"]))
        self.assertIn("not a JSON object", self.reasons(document))


class ReviewTests(SubmissionCase):
    """Condition 4's acceptance, refused in every shape that could never be an acceptance."""

    def test_a_self_review_is_refused(self) -> None:
        self.assertEqual(self.define(KIND_REVIEW, review_body())["verdict"], DEFINED)
        document = self.refusal(KIND_REVIEW, review_body(reviewer_node_id=IMPLEMENTER))
        self.assertIn("self-review", self.reasons(document))

    def test_an_unrecognised_verdict_is_refused(self) -> None:
        document = self.refusal(KIND_REVIEW, review_body(verdict="approved-with-nits"))
        self.assertIn("approved-with-nits", self.reasons(document))

    def test_an_acceptance_carrying_reasons_is_refused(self) -> None:
        self.assertEqual(self.define(KIND_REVIEW, review_body())["verdict"], DEFINED)
        document = self.refusal(KIND_REVIEW, review_body(reasons=["one nit remains"]))
        self.assertIn("accepted and carries reasons", self.reasons(document))

    def test_a_rejection_with_no_reason_is_refused_and_one_with_a_reason_is_sealed(self) -> None:
        document = self.refusal(KIND_REVIEW, review_body(verdict="changes-requested"))
        self.assertIn("carries no reason", self.reasons(document))
        sealed = self.seal(
            KIND_REVIEW, review_body(verdict="changes-requested", reasons=["the focused gate was never run"])
        )
        self.assertEqual(sealed["verdict"], "changes-requested")

    def test_an_evidence_free_review_is_refused(self) -> None:
        self.assertEqual(self.define(KIND_REVIEW, review_body())["verdict"], DEFINED)
        document = self.refusal(KIND_REVIEW, review_body(evidence=[]))
        self.assertIn("no evidence", self.reasons(document))
        empty = self.refusal(KIND_REVIEW, review_body(evidence=[""]))
        self.assertIn("evidence", self.reasons(empty))


class CriticTests(SubmissionCase):
    """The critic's classification: only the eight kinds, and `resolved` tied to `resolution`."""

    def test_every_named_kind_seals_and_an_unnamed_one_is_refused(self) -> None:
        for kind in (
            "acceptance-criteria-violation",
            "corrupted-evidence",
            "failed-authoritative-gate",
            "safety-regression",
            "complexity",
            "documentation",
            "enhancement",
            "maintainability",
        ):
            with self.subTest(kind=kind):
                sealed = self.seal(KIND_CRITIC, critic_body(findings=[finding(kind=kind)]))
                self.assertEqual(sealed["findings"][0]["kind"], kind)
        document = self.refusal(KIND_CRITIC, critic_body(findings=[finding(kind="nitpick")]))
        self.assertIn("nitpick", self.reasons(document))

    def test_an_empty_findings_list_is_refused(self) -> None:
        self.assertEqual(self.define(KIND_CRITIC, critic_body())["verdict"], DEFINED)
        document = self.refusal(KIND_CRITIC, critic_body(findings=[]))
        self.assertIn("no finding at all", self.reasons(document))

    def test_one_finding_id_used_twice_is_refused(self) -> None:
        document = self.refusal(KIND_CRITIC, critic_body(findings=[finding(), finding(kind="documentation")]))
        self.assertIn("already", self.reasons(document))

    def test_resolved_and_resolution_must_agree(self) -> None:
        self.assertEqual(self.define(KIND_CRITIC, critic_body())["verdict"], DEFINED)
        claimed = self.refusal(KIND_CRITIC, critic_body(findings=[finding(resolved=True)]))
        self.assertIn("resolution", self.reasons(claimed))
        dangling = self.refusal(KIND_CRITIC, critic_body(findings=[finding(resolution="remediate-a")]))
        self.assertIn("unresolved and still names resolution", self.reasons(dangling))
        sealed = self.seal(KIND_CRITIC, critic_body(findings=[finding(resolved=True, resolution="remediate-a")]))
        self.assertEqual(sealed["findings"][0]["resolution"], "remediate-a")

    def test_a_non_boolean_resolved_is_refused(self) -> None:
        for value in ("true", 1, None):
            with self.subTest(value=value):
                document = self.refusal(KIND_CRITIC, critic_body(findings=[finding(resolved=value)]))
                self.assertIn("resolved", self.reasons(document))

    def test_a_finding_missing_the_evidence_issue_07_requires_is_refused(self) -> None:
        document = self.refusal(KIND_CRITIC, critic_body(findings=[finding(evidence=[])]))
        self.assertIn("issue 07", self.reasons(document))


class EndedStateTests(SubmissionCase):
    """Implementation Decision 61's ended-state half, which is why this phase exists.

    The four tokens are closed, and the two dependent fields are tied to the token in BOTH
    directions, so neither an aborted wave with no stated reason nor a completed one carrying failure
    prose is representable.
    """

    def test_each_of_the_four_ended_states_seals(self) -> None:
        for state in ENDED_STATES:
            with self.subTest(state=state):
                body = (
                    conductor_body()
                    if state == "completed"
                    else conductor_body(
                        ended_state=state,
                        ended_reasons=[f"the execution ended {state} after the reviewer's acceptance"],
                        last_proven_stage="the reviewer's acceptance",
                    )
                )
                sealed = self.seal(KIND_CONDUCTOR, body)
                self.assertEqual(sealed["ended_state"], state)

    def test_a_fifth_ended_state_is_refused(self) -> None:
        self.assertEqual(self.define(KIND_CONDUCTOR, conductor_body())["verdict"], DEFINED)
        for state in ("accepted", "blocked", "remediation-progress", "cancelled", "", None):
            with self.subTest(state=state):
                document = self.refusal(KIND_CONDUCTOR, conductor_body(ended_state=state))
                self.assertIn("ended_state", self.reasons(document))

    def test_an_unfinished_state_must_name_its_reasons_and_its_last_proven_stage(self) -> None:
        control = self.seal(
            KIND_CONDUCTOR,
            conductor_body(
                ended_state="unknown-effect",
                ended_reasons=["the fan-in subprocess was killed after the merge began"],
                last_proven_stage="the integrator's pre-merge snapshot",
            ),
        )
        self.assertEqual(control["ended_state"], "unknown-effect")
        silent = self.refusal(
            KIND_CONDUCTOR,
            conductor_body(ended_state="failed", ended_reasons=[], last_proven_stage="the gate run"),
        )
        self.assertIn("names no reason", self.reasons(silent))
        stageless = self.refusal(
            KIND_CONDUCTOR, conductor_body(ended_state="failed", ended_reasons=["the gate failed"])
        )
        self.assertIn("last_proven_stage", self.reasons(stageless))

    def test_a_completed_state_may_not_carry_ending_prose(self) -> None:
        self.assertEqual(self.define(KIND_CONDUCTOR, conductor_body())["verdict"], DEFINED)
        noisy = self.refusal(KIND_CONDUCTOR, conductor_body(ended_reasons=["mostly fine"]))
        self.assertIn("completed", self.reasons(noisy))
        staged = self.refusal(KIND_CONDUCTOR, conductor_body(last_proven_stage="the gate run"))
        self.assertIn("last_proven_stage", self.reasons(staged))

    def test_the_journal_anchor_must_be_a_sha256(self) -> None:
        self.assertEqual(self.define(KIND_CONDUCTOR, conductor_body())["verdict"], DEFINED)
        for anchor in ("C" * 64, "c" * 63, "not-a-digest", None):
            with self.subTest(anchor=anchor):
                document = self.refusal(KIND_CONDUCTOR, conductor_body(journal_digest=anchor))
                self.assertIn("journal_digest", self.reasons(document))

    def test_recorded_at_must_be_the_familys_instant(self) -> None:
        for value in ("2026-08-19T02:06:00.000Z", "2026-08-19 02:06:00Z", "2026-08-19T02:06Z", 1755561960):
            with self.subTest(value=value):
                document = self.refusal(KIND_CONDUCTOR, conductor_body(recorded_at=value))
                self.assertIn("recorded_at", self.reasons(document))
                self.assertIn("no clock", self.reasons(document))


class VerifyTests(SubmissionCase):
    """The binding a conductor uses: the digest re-derives, and it is the one that was recorded."""

    def test_an_edited_sealed_document_is_refused(self) -> None:
        sealed = self.seal(KIND_REVIEW, review_body())
        self.assertEqual(self.verify(KIND_REVIEW, sealed)["verdict"], VERIFIED)
        edited = dict(sealed, evidence=["read a different diff"])
        document = self.refusal(KIND_REVIEW, edited, "verify")
        self.assertIn("edited since it was sealed", self.reasons(document))

    def test_a_digest_the_caller_did_not_record_is_refused(self) -> None:
        sealed = self.seal(KIND_CONDUCTOR, conductor_body())
        self.assertEqual(
            self.verify(KIND_CONDUCTOR, sealed, "--expect-digest", sealed["digest"])["verdict"], VERIFIED
        )
        document = self.refusal(KIND_CONDUCTOR, sealed, "verify", "--expect-digest", "d" * 64)
        self.assertIn("is not the", self.reasons(document))

    def test_a_malformed_expect_digest_is_a_grammar_error(self) -> None:
        sealed = self.seal(KIND_CONDUCTOR, conductor_body())
        path = str(self.store("sealed", sealed))
        done = self.run_tool("verify", "--kind", KIND_CONDUCTOR, "--submission", path, "--expect-digest", "nope")
        self.assertEqual(done.returncode, EXIT_INPUT)
        self.assertEqual(done.stdout, b"", "a grammar error must emit no result document")
        self.assertIn(b"--expect-digest", done.stderr)

    def test_verify_re_checks_the_whole_schema_and_not_only_the_digest(self) -> None:
        """A sealed document edited AND re-digested is still refused, by the field that is wrong.

        This is the guard against a `verify` that had degenerated into a digest comparison: the
        digest here is correct for the bytes, and the document must still be refused.
        """
        sealed = self.seal(KIND_REVIEW, review_body())
        forged = dict(sealed, verdict="looks-fine")
        forged["digest"] = expected_digest(forged)
        document = self.refusal(KIND_REVIEW, forged, "verify")
        self.assertIn("looks-fine", self.reasons(document))
        self.assertTrue(self.check(document, "digest")["met"], "the forged digest itself re-derives")


class MalformedInputTests(SubmissionCase):
    """Unusable input is exit 2 with no result document: the question could not be asked."""

    def path_failure(self, path: str, *, kind: str = KIND_REVIEW) -> bytes:
        done = self.run_tool("define", "--kind", kind, "--submission", path)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stdout.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, b"", "an input error must emit no result document")
        return done.stderr

    def test_a_control_body_at_a_real_path_is_defined(self) -> None:
        self.assertEqual(self.define(KIND_REVIEW, review_body())["verdict"], DEFINED)

    def test_an_absent_path_a_directory_and_a_non_object_are_input_errors(self) -> None:
        self.assertIn(b"cannot read", self.path_failure(str(self.work / "missing.json")))
        self.assertIn(b"not a regular file", self.path_failure(str(self.work)))
        listed = self.work / "listed.json"
        listed.write_text("[]", encoding="utf-8")
        self.assertIn(b"not a JSON object", self.path_failure(str(listed)))

    def test_unparseable_and_ambiguous_documents_are_input_errors(self) -> None:
        broken = self.work / "broken.json"
        broken.write_text('{"schema": ', encoding="utf-8")
        self.assertIn(b"not JSON", self.path_failure(str(broken)))
        repeated = self.work / "repeated.json"
        repeated.write_text('{"verdict": "accepted", "verdict": "rejected"}', encoding="utf-8")
        self.assertIn(b"two meanings", self.path_failure(str(repeated)))

    def test_a_non_finite_number_is_an_input_error_in_both_of_its_spellings(self) -> None:
        constant = self.work / "constant.json"
        constant.write_text('{"schema": "x", "limit": NaN}', encoding="utf-8")
        self.assertIn(b"non-finite JSON constant", self.path_failure(str(constant)))
        # `1e400` is an ordinary number token: `parse_constant` never sees it and `float()` overflows
        # it to `inf`, which only the post-parse walk can catch.
        overflowed = self.work / "overflowed.json"
        overflowed.write_text('{"schema": "x", "artifacts": [{"size": 1e400}]}', encoding="utf-8")
        self.assertIn(b"non-finite number", self.path_failure(str(overflowed)))

    def test_a_deeply_nested_document_is_refused_and_not_a_crash(self) -> None:
        """The non-finite walk is iterative, so depth costs a named refusal and never the stack.

        Depth 2000 is comfortably below where `json`'s own C scanner overflows its stack (that
        threshold is per-host and per-build, not a fixed count), so this case alone never reaches
        the failure the next test targets; it stays here as the cheap moderate-depth regression
        check, not as proof against the seed's own 100,000-level scenario.
        """
        nested = self.work / "nested.json"
        depth = 2000
        nested.write_text("{\"a\":" * depth + "1" + "}" * depth, encoding="utf-8")
        done = self.run_tool("define", "--kind", KIND_REVIEW, "--submission", str(nested))
        self.assertIn(done.returncode, (EXIT_OK, EXIT_INPUT), done.stderr.decode("utf-8", "replace"))
        self.assertNotIn(b"RecursionError", done.stderr)

    def test_a_hundred_thousand_deep_document_is_classified_not_a_crash(self) -> None:
        """The seed's own scenario: `json`'s C scanner recurses once per nesting level independent of
        `sys.setrecursionlimit`, and overflows its OWN C stack at a depth this interpreter's build
        accommodates. The positive control proves THIS build actually raises `RecursionError` on a
        bare `json.loads` at this depth -- the moderate-depth case above never reaches that failure
        at all, which is exactly how it survived an earlier review.
        """
        depth = 100_000
        text = "{\"a\":" * depth + "1" + "}" * depth
        try:
            json.loads(text)
        except RecursionError:
            pass
        else:
            self.skipTest("this interpreter's build did not raise RecursionError at 100,000 levels")
        nested = self.work / "nested-deep.json"
        nested.write_text(text, encoding="utf-8")
        done = self.run_tool("define", "--kind", KIND_REVIEW, "--submission", str(nested))
        self.assertEqual(done.returncode, EXIT_INPUT, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, b"", "an unusable document still produced a result document")
        self.assertIn(b"nests too deeply", done.stderr)
        self.assertNotIn(b"Traceback", done.stderr)


class CanonicalFormTests(SubmissionCase):
    """The bytes, not the parsed values: this is the half a JSON round-trip cannot detect."""

    def test_the_result_document_is_canonical_and_ends_with_one_newline(self) -> None:
        done = self.run_tool("define", "--kind", KIND_REVIEW, "--submission", str(self.store("body", review_body())))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, canonical(json.loads(done.stdout)))
        self.assertTrue(done.stdout.endswith(b"}\n"))
        self.assertNotIn(b"\n\n", done.stdout)
        # The tight separators, asserted against a key rather than against `", "`: the residual prose
        # contains ordinary commas followed by spaces, and asserting on those would fail on English.
        self.assertNotIn(b'"verdict": ', done.stdout)

    def test_non_ascii_prose_is_escaped_and_does_not_move_the_digest(self) -> None:
        body = review_body(evidence=["read the reviewer's note: “the diff is minimal”"])
        done = self.run_tool("define", "--kind", KIND_REVIEW, "--submission", str(self.store("body", body)))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertIn(b"\\u201c", done.stdout, "ensure_ascii=True escapes the quotation mark")
        self.assertNotIn("“".encode("utf-8"), done.stdout, "and never emits its UTF-8 bytes")
        sealed = json.loads(done.stdout)["submission"]
        self.assertEqual(sealed["digest"], expected_digest(sealed))

    def test_input_key_order_and_whitespace_do_not_move_the_digest(self) -> None:
        body = review_body()
        one = self.work / "one.json"
        one.write_text(json.dumps(body, indent=4, sort_keys=True), encoding="utf-8")
        two = self.work / "two.json"
        two.write_text(json.dumps(dict(reversed(list(body.items()))), separators=(",", ":")), encoding="utf-8")
        digests = set()
        for path in (one, two):
            document = self.result("define", "--kind", KIND_REVIEW, "--submission", str(path))
            self.assertEqual(document["verdict"], DEFINED, self.reasons(document))
            digests.add(document["digest"])
        self.assertEqual(len(digests), 1, "the digest is over the parsed document, not the file's bytes")

    def test_the_sealed_file_a_conductor_files_re_derives_its_own_digest(self) -> None:
        path = self.seal_to_file(KIND_CRITIC, critic_body(), "critic-findings")
        sealed = json.loads(path.read_bytes())
        self.assertEqual(path.read_bytes(), canonical(sealed))
        self.assertEqual(sealed["digest"], expected_digest(sealed))


class HostileDescriptorTests(SubmissionCase):
    """A display channel costs the display line; the result document costs the exit code."""

    def argv(self, kind: str, body: dict[str, Any]) -> list[str]:
        return [
            sys.executable,
            "-B",
            str(TOOL),
            "define",
            "--kind",
            kind,
            "--submission",
            str(self.store("body", body)),
        ]

    def test_an_unwritable_stderr_costs_no_exit_code_and_still_delivers_the_document(self) -> None:
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, out = run_with_hostile_stderr(self.argv(KIND_REVIEW, review_body()), mode=mode, cwd=self.root)
                self.assertEqual(code, EXIT_OK)
                self.assertEqual(json.loads(out)["verdict"], DEFINED)

    def test_an_unwritable_stderr_keeps_the_grammar_error_code(self) -> None:
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                argv = [sys.executable, "-B", str(TOOL), "define", "--kind", "not-a-kind"]
                code, out = run_with_hostile_stderr(argv, mode=mode, cwd=self.root)
                self.assertEqual(code, EXIT_INPUT)
                self.assertEqual(out, b"", "usage must never be redirected onto the result channel")

    def test_an_unwritable_stdout_is_an_undelivered_document(self) -> None:
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, err = run_with_hostile_stdout(self.argv(KIND_REVIEW, review_body()), mode=mode, cwd=self.root)
                self.assertEqual(code, EXIT_INTERNAL)
                # The two shapes report differently -- no stream at all versus a stream that broke
                # mid-write -- and both must say the document did not arrive.
                self.assertIn(b"deliver", err)
                self.assertIn(b"result document", err)


class SourceTests(unittest.TestCase):
    """What the tool may not do, read with `ast` rather than by substring."""

    def test_the_tool_reads_no_clock_no_environment_and_spawns_nothing(self) -> None:
        modules, calls = imports_and_calls(TOOL)
        for forbidden in ("subprocess", "os", "time", "datetime", "socket", "urllib", "shutil"):
            self.assertNotIn(forbidden, modules, f"{forbidden} has no place in an effect-free reader")
        self.assertNotIn("environ", calls)
        self.assertNotIn("getenv", calls)
        # The positive control: `wave-journal.py` DOES read its environment, so a walk that found
        # nothing anywhere would be a broken walk rather than a clean tool.
        journal_modules, journal_calls = imports_and_calls(JOURNAL_TOOL)
        self.assertIn("os", journal_modules)
        self.assertTrue({"environ", "getenv"} & journal_calls or "os" in journal_modules)

    def test_the_tool_never_opens_a_file_for_writing(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        for forbidden in ('open("w', "'w'", '"w"', "write_text", "write_bytes", "mkdir", "unlink"):
            self.assertNotIn(forbidden, source, f"{forbidden} would make this tool cause an effect")

    def test_every_schema_the_verdict_tool_consumes_is_a_kind_this_tool_seals(self) -> None:
        """The four names are the contract between the two tools, so drift on either side fails here."""
        producer = TOOL.read_text(encoding="utf-8")
        consumer = VERDICT_TOOL.read_text(encoding="utf-8")
        for schema in SCHEMA_OF_KIND.values():
            self.assertIn(f'"{schema}"', producer, f"{schema} is not sealed by the producer")
            self.assertIn(f'"{schema}"', consumer, f"{schema} is not consumed by the verdict tool")


class RenameAt2CapabilityTests(unittest.TestCase):
    """The capability probe `WaveFixtureCase` is skipped on. Deliberately NOT a `WaveFixtureCase`:
    this class's whole point is to run even when `_HAS_RENAMEAT2` is false and every
    `WaveFixtureCase` here is skipped. `wave-journal.py`'s own refusal at the missing syscall is
    covered directly by `tests/test_wave_journal.py`'s `RenameAt2CapabilityTests`; this is only the
    probe this module reuses to decide whether to build a journal fixture with it at all.
    """

    @unittest.skipUnless(sys.platform.startswith("linux"), "the probe's truth is only guaranteed on Linux (glibc 2.28+)")
    def test_the_probe_returns_non_none_on_this_linux_host(self) -> None:
        """POSITIVE CONTROL: without this, `_HAS_RENAMEAT2` gating `WaveFixtureCase` above would be
        silently vacuous -- true on every host, including the ubuntu CI runner this suite must stay
        green on -- and nothing would ever fail to reveal it.

        The platform condition is the assertion's own scope, not a capability the probe is excused
        from: the claim is precisely "ON LINUX this symbol must exist", so it RUNS on the ubuntu runner
        (where a vacuous skip would otherwise hide) and skips by name on macOS rather than failing
        there for lacking a syscall macOS has never had."""
        self.assertTrue(_HAS_RENAMEAT2, "glibc 2.28+ always exports renameat2; this host is unexpected")


if __name__ == "__main__":
    unittest.main()
