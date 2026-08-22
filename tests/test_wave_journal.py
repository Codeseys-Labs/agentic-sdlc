"""Tests for the append-only wave journal (issue 07: state, continuation, and completion).

Everything here drives the real tool as a subprocess, with ONE named exception below. The tool's
filename has a hyphen in it, so it cannot be imported, and that is deliberate for this family: the
journal's whole value is what it writes to disk and what it prints, so a test that reached inside it
would stop testing the artifact.

Four properties get the most attention, because each one is a defect class this repository has
already paid for:

1. EFFECT ADMISSION. A failure after ANY admitted effect must exit 4 and name what happened. The
   injection sweep drives every point in the append path and asserts 4 at each one, and asserts the
   requested code survives at the one point before any effect.
2. NO CLOCK. Every timestamp is a caller input. The source is checked for clock reads, with a
   positive control proving the detector fires.
3. HOSTILE STDERR. A closed or broken fd 2 costs the display channel and nothing else; 120 must be
   unreachable rather than unlikely.
4. AN INTERLEAVED WRITER IS DETECTED, NOT OVERWRITTEN. `InterleavedWriterTests` is the exception to
   the subprocess rule: writer A runs in this process so its read can be wrapped, because the window
   between A's read and A's publish has no honest subprocess seam and the alternatives are a forked
   racer and a sleep. Writer B stays a real separate invocation, so its record is a committed one.

Every test's environment is CONSTRUCTED, never inherited: the tool's own fault variable is stripped
from the copy, because a suite that reads its own injector out of the developer's shell is testing
the shell. `EnvironmentIsolationTests` holds that, and holds the stripped set against the source.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
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
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "wave-journal.py"

JOURNAL_SCHEMA = "agentic-sdlc/wave-journal@1"
RESULT_SCHEMA = "agentic-sdlc/wave-journal-result@1"
PROJECTION_SCHEMA = "agentic-sdlc/wave-journal-projection@1"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2
EXIT_REFUSED = 3
EXIT_PARTIAL = 4
DECLARED_EXITS = frozenset({EXIT_OK, EXIT_INTERNAL, EXIT_INPUT, EXIT_REFUSED, EXIT_PARTIAL})

POSIX = os.name == "posix"

FAULT_ENV = "AGENTIC_SDLC_WAVE_JOURNAL_FAULT"
# Every variable the tool itself reads, and therefore every variable each test's environment is
# CONSTRUCTED without rather than inheriting. A developer debugging this very tool exports
# FAULT_ENV, and an inherited one turns most of this module red for a reason that has nothing to do
# with the code under test. `EnvironmentIsolationTests` keeps this set honest against the source.
TOOL_CONTROL_ENV = frozenset({FAULT_ENV})

T0 = "2026-08-19T02:00:00Z"


def constructed_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment every spawn in this module hands the tool: inherited, MINUS the tool's controls.

    There are four spawn sites here -- `run_tool` and the two hostile-fd helpers -- and every one goes
    through this, because a scrub that only covers the ordinary path leaves the same defect at the
    other three. PATH, HOME, and locale are inherited deliberately: the tool is a subprocess and needs
    a usable interpreter environment. What is never inherited is a variable the tool READS; those are
    supplied by the test that wants them, or not at all.
    """
    environment = {key: value for key, value in os.environ.items() if key not in TOOL_CONTROL_ENV}
    if extra:
        environment.update(extra)
    return environment
T1 = "2026-08-19T02:01:00Z"
T2 = "2026-08-19T02:02:00Z"
T3 = "2026-08-19T02:03:00Z"
T4 = "2026-08-19T02:04:00Z"
T5 = "2026-08-19T02:05:00Z"

#: The two exact sha256 values an approval may BIND itself to. Deliberately distinguishable from each
#: other and from the header's `plan_digest`, so a test that compared the wrong pair would fail rather
#: than pass on a coincidence of repeated characters.
PRESTATE_DIGEST = "b" * 64
CANDIDATE_DIGEST = "c" * 64


def canonical(value: Any) -> bytes:
    """The activation family's canonical form: sorted, tight, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def header_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "wave_id": "wave-1",
        "mission_id": "mission-slice-5",
        "mode": "static-dag",
        "plan_digest": "a" * 64,
        "approval": "operator approved the wave graph at review",
        "required_nodes": ["implement-a", "implement-b", "review-a"],
        "limits": {"max_concurrent_nodes": 4, "max_nodes": 64, "max_recursive_generations": 0},
    }
    record.update(overrides)
    return record


def assignment(**overrides: Any) -> dict[str, Any]:
    record = {
        "provider": "anthropic",
        "model_id": "us.anthropic.claude-sonnet-5",
        "effort": "high",
        "context": "1m",
        "resolution_state": "resolved",
    }
    record.update(overrides)
    return record


def node_record(node_id: str, disposition: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "node_id": node_id,
        "role": "implementer",
        "disposition": disposition,
        "inputs": ["plan/wave-1.json"],
        "outputs": ["worktrees/a/diff"],
        "assignment": assignment(),
        "started_at": T1,
        "ended_at": T2,
        "evidence": ["gate receipt 9f"],
        "attempt": 1,
        "reasons": [],
        "approval": None,
    }
    record.update(overrides)
    return record


def approval_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "approval_id": "approval-skip-b",
        "subject": "skip implement-b: its workstream is out of scope for this wave",
        "scope": ["implement-b"],
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
        "consumed": 3,
        "reasons": [],
    }
    record.update(overrides)
    return record


def retry_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "node_id": "review-a",
        "attempt": 2,
        "capability": "read-only",
        "prior_effect": "none",
        "evidence": ["attempt 1 transcript"],
        "reason": "the first attempt lost its transport before reading any artifact",
    }
    record.update(overrides)
    return record


def plan_revision_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "revision_id": "revision-1",
        "from_plan_digest": "a" * 64,
        "to_plan_digest": "b" * 64,
        "approval": "approval-revision-1",
        "reasons": ["the reviewer found the graph missing a fan-in node"],
    }
    record.update(overrides)
    return record


class _JournalTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.journal = self.tmp / "wave-1.journal"

    def run_tool(
        self, args: list[str], *, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-B", str(TOOL), *args],
            capture_output=True,
            cwd=str(self.tmp),
            env=constructed_environment(env),
            check=False,
        )

    def document(self, proc: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
        """Parse stdout AND assert it is byte-exactly the canonical form of what it parsed."""
        parsed = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(proc.stdout, canonical(parsed), "stdout is not canonical")
        return parsed

    def init(self, *, at: str = T0, record: dict[str, Any] | None = None) -> dict[str, Any]:
        proc = self.run_tool(
            ["init", "--journal", str(self.journal), "--at", at, "--record", json.dumps(record if record is not None else header_record())]
        )
        return self.document(proc) | {"__code": proc.returncode}

    def append(
        self, verb: str, record: dict[str, Any], *, at: str, env: dict[str, str] | None = None
    ) -> tuple[dict[str, Any], int]:
        proc = self.run_tool(
            [verb, "--journal", str(self.journal), "--at", at, "--record", json.dumps(record)], env=env
        )
        return self.document(proc), proc.returncode

    def project(self) -> tuple[dict[str, Any], int]:
        proc = self.run_tool(["project", "--journal", str(self.journal)])
        return self.document(proc), proc.returncode

    def lines(self) -> list[bytes]:
        return self.journal.read_bytes().splitlines(keepends=True)


class LifecycleTests(_JournalTestCase):
    """One three-node wave reaching each of the three dispositions exactly once."""

    def test_a_three_node_wave_records_success_approved_skip_and_blocked(self) -> None:
        opened = self.init()
        self.assertEqual(opened["__code"], EXIT_OK)
        self.assertEqual(opened["status"], "initialized")
        self.assertEqual(opened["effect"], f"created the wave journal at {self.journal}")
        self.assertEqual(opened["schema"], RESULT_SCHEMA)
        self.assertEqual(opened["seq"], 0)

        success, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(success["status"], "appended")
        self.assertEqual(success["seq"], 1)
        self.assertEqual(success["effect"], f"appended entry 1 to {self.journal}")

        # An approved skip has to point at an approval THIS journal already carries, so the word
        # "approved" is derivable from the record rather than asserted by the caller.
        approved, code = self.append("record-approval", approval_record(), at=T2)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(approved["seq"], 2)

        skipped, code = self.append(
            "record-node",
            node_record(
                "implement-b",
                "approved-skip",
                approval="approval-skip-b",
                assignment=assignment(provider=None, model_id=None, effort=None, context=None, resolution_state="unresolved"),
                outputs=[],
                evidence=[],
            ),
            at=T3,
        )
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(skipped["seq"], 3)

        # The retry precedes the disposition it led to, because a disposition is terminal: a retry
        # recorded after one would describe work that could not have happened.
        retry, code = self.append("record-retry", retry_record(), at=T3)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(retry["seq"], 4)

        blocked, code = self.append(
            "record-node",
            node_record(
                "review-a",
                "blocked",
                role="reviewer",
                outputs=[],
                evidence=[],
                attempt=2,
                reasons=["the workstream's dependency artifact failed admission"],
            ),
            at=T4,
        )
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(blocked["seq"], 5)

        budget, code = self.append("record-budget", budget_record(), at=T4)
        self.assertEqual(code, EXIT_OK)
        revision_approval, code = self.append(
            "record-approval",
            approval_record(approval_id="approval-revision-1", subject="revise the wave graph", scope=["wave-1"]),
            at=T5,
        )
        self.assertEqual(code, EXIT_OK)
        revision, code = self.append("record-plan-revision", plan_revision_record(), at=T5)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(revision["seq"], 8)

        projection, code = self.project()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(projection["schema"], PROJECTION_SCHEMA)
        self.assertEqual(projection["status"], "projected")
        self.assertEqual(projection["wave_id"], "wave-1")
        self.assertEqual(projection["entry_count"], 8)
        self.assertEqual(projection["required_nodes"], ["implement-a", "implement-b", "review-a"])
        self.assertEqual(
            projection["dispositions"],
            {
                "implement-a": {"at": T2, "disposition": "admitted-success", "role": "implementer", "seq": 1},
                "implement-b": {"at": T3, "disposition": "approved-skip", "role": "implementer", "seq": 3},
                "review-a": {"at": T4, "disposition": "blocked", "role": "reviewer", "seq": 5},
            },
        )
        self.assertEqual(projection["required_nodes_without_disposition"], [])
        self.assertEqual(projection["nodes_not_required"], [])
        self.assertEqual([item["budget_id"] for item in projection["budgets"]], ["budget-nodes"])
        self.assertEqual(projection["budgets"][0]["remaining"], 61)
        self.assertEqual([item["node_id"] for item in projection["retries"]], ["review-a"])
        self.assertEqual([item["revision_id"] for item in projection["plan_revisions"]], ["revision-1"])
        self.assertEqual(
            [item["approval_id"] for item in projection["approvals"]],
            ["approval-skip-b", "approval-revision-1"],
        )
        self.assertEqual(projection["journal_digest"], sha256_hex(self.journal.read_bytes()))
        self.assertEqual(projection["last_at"], T5)
        # The projection states FACTS and no verdict: completion is the verdict tool's derivation,
        # so no summary field here may pre-empt it.
        for forbidden in ("complete", "completion", "verdict", "accepted", "condition_1", "traceable"):
            self.assertNotIn(forbidden, projection, f"the projection must not summarise: {forbidden}")

    def test_an_unrecorded_required_node_is_visible_as_a_fact(self) -> None:
        """Condition 1 is DERIVABLE: the required set and the disposed set are both published."""
        self.init()
        _, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)
        projection, code = self.project()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(projection["required_nodes_without_disposition"], ["implement-b", "review-a"])
        # POSITIVE CONTROL: the same field is empty once the two remaining nodes are disposed, so it
        # tracks the journal rather than being a constant.
        self.append("record-approval", approval_record(), at=T2)
        self.append(
            "record-node",
            node_record("implement-b", "approved-skip", approval="approval-skip-b", outputs=[], evidence=[]),
            at=T3,
        )
        self.append(
            "record-node",
            node_record("review-a", "blocked", outputs=[], evidence=[], reasons=["dependency failed admission"]),
            at=T3,
        )
        projection, code = self.project()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(projection["required_nodes_without_disposition"], [])

    def test_a_node_outside_the_required_set_is_reported_separately(self) -> None:
        self.init()
        _, code = self.append("record-node", node_record("extra-node", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)
        projection, _ = self.project()
        self.assertEqual(projection["nodes_not_required"], ["extra-node"])
        self.assertEqual(projection["required_nodes_without_disposition"], ["implement-a", "implement-b", "review-a"])


class OnDiskFormTests(_JournalTestCase):
    """The file is line-per-record canonical JSON, chained, and only ever grows."""

    def test_every_line_is_canonical_and_carries_the_schema_tag(self) -> None:
        self.init()
        self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        lines = self.lines()
        self.assertEqual(len(lines), 2)
        for index, line in enumerate(lines):
            parsed = json.loads(line.decode("utf-8"))
            self.assertEqual(line, canonical(parsed), f"line {index} is not canonical")
            self.assertEqual(parsed["schema"], JOURNAL_SCHEMA)
            self.assertEqual(parsed["seq"], index)
        self.assertEqual(json.loads(lines[0])["kind"], "wave-opened")
        entry = json.loads(lines[1])
        self.assertEqual(entry["kind"], "node")
        self.assertEqual(entry["prev_digest"], sha256_hex(lines[0]))
        self.assertEqual(entry["at"], T2)
        self.assertTrue(self.journal.read_bytes().endswith(b"}\n"))
        self.assertFalse(self.journal.read_bytes().endswith(b"\n\n"))

    def test_an_append_only_ever_adds_bytes_after_the_existing_prefix(self) -> None:
        self.init()
        before = self.journal.read_bytes()
        self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        after = self.journal.read_bytes()
        self.assertTrue(after.startswith(before))
        self.assertGreater(len(after), len(before))
        # POSITIVE CONTROL for the prefix assertion: a DIFFERENT first line is not a prefix, so the
        # check above can actually fail.
        self.assertFalse(after.startswith(b"{" + before))

    def test_initialising_over_an_existing_journal_is_a_clean_refusal(self) -> None:
        self.init()
        before = self.journal.read_bytes()
        result = self.init()
        self.assertEqual(result["__code"], EXIT_REFUSED)
        self.assertEqual(result["effect"], "none")
        self.assertEqual(result["admitted_effects"], [])
        self.assertIn("already exists", result["reasons"][0])
        self.assertEqual(self.journal.read_bytes(), before)

    def test_appending_to_an_absent_journal_is_a_clean_refusal(self) -> None:
        result, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_REFUSED)
        self.assertEqual(result["effect"], "none")
        self.assertEqual(result["admitted_effects"], [])
        self.assertFalse(self.journal.exists())


class RecordSchemaTests(_JournalTestCase):
    """A record's own internal consistency is a SCHEMA verdict (2): no journal state is consulted."""

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.init()["__code"], EXIT_OK)

    def test_a_fourth_disposition_value_is_refused_by_name(self) -> None:
        result, code = self.append("record-node", node_record("implement-a", "partial"), at=T2)
        self.assertEqual(code, EXIT_INPUT)
        self.assertEqual(result["effect"], "none")
        self.assertEqual(result["admitted_effects"], [])
        reason = result["reasons"][0]
        self.assertIn("partial", reason)
        for legal in ("admitted-success", "approved-skip", "blocked"):
            self.assertIn(legal, reason)
        self.assertEqual(len(self.lines()), 1)  # nothing was appended
        # POSITIVE CONTROL: all three legal values ARE accepted through the same argument, so the
        # refusal above is about the value and not about the record or the verb.
        # The approval's scope must name the node THIS test skips, "n-skip", rather than the fixture's
        # own default scope: an approval only authorizes the node(s) it names (see
        # `test_an_approved_skip_must_be_named_in_its_approvals_scope`), and this test is about legal
        # disposition VALUES, not about that check, so it supplies a scope that satisfies it.
        self.append("record-approval", approval_record(scope=["n-skip"]), at=T2)
        accepted = [
            node_record("n-success", "admitted-success"),
            node_record("n-skip", "approved-skip", approval="approval-skip-b", outputs=[], evidence=[]),
            node_record("n-blocked", "blocked", outputs=[], evidence=[], reasons=["dependency failed admission"]),
        ]
        for record in accepted:
            with self.subTest(disposition=record["disposition"]):
                _, code = self.append("record-node", record, at=T3)
                self.assertEqual(code, EXIT_OK)

    def test_a_node_record_missing_any_required_field_is_refused_by_name(self) -> None:
        complete = node_record("implement-a", "admitted-success")
        for field in sorted(complete):
            with self.subTest(missing=field):
                partial = {key: value for key, value in complete.items() if key != field}
                result, code = self.append("record-node", partial, at=T2)
                self.assertEqual(code, EXIT_INPUT)
                self.assertIn(field, result["reasons"][0])
                self.assertIn("missing", result["reasons"][0])
                self.assertEqual(result["admitted_effects"], [])
                self.assertEqual(len(self.lines()), 1)
        # POSITIVE CONTROL: the complete record is accepted, so the sweep above is not passing
        # because every node record is refused.
        _, code = self.append("record-node", complete, at=T2)
        self.assertEqual(code, EXIT_OK)

    def test_an_unrecognised_field_in_a_node_record_is_refused_by_name(self) -> None:
        record = node_record("implement-a", "admitted-success") | {"verdict": "accepted"}
        result, code = self.append("record-node", record, at=T2)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("verdict", result["reasons"][0])
        self.assertIn("unrecognised", result["reasons"][0])

    def test_an_admitted_success_must_carry_a_resolved_assignment_and_evidence(self) -> None:
        unresolved, code = self.append(
            "record-node",
            node_record("implement-a", "admitted-success", assignment=assignment(resolution_state="unresolved")),
            at=T2,
        )
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("resolution_state", unresolved["reasons"][0])
        blank, code = self.append("record-node", node_record("implement-a", "admitted-success", evidence=[]), at=T2)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("evidence", blank["reasons"][0])
        # POSITIVE CONTROLS: the resolved-and-evidenced success is accepted, and an unresolved
        # assignment is fine for a node that never ran -- so the refusals track the disposition.
        _, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)
        self.append("record-approval", approval_record(), at=T2)
        _, code = self.append(
            "record-node",
            node_record(
                "implement-b",
                "approved-skip",
                approval="approval-skip-b",
                assignment=assignment(provider=None, model_id=None, effort=None, context=None, resolution_state="unresolved"),
                outputs=[],
                evidence=[],
            ),
            at=T3,
        )
        self.assertEqual(code, EXIT_OK)

    def test_a_blocked_node_must_state_reasons(self) -> None:
        result, code = self.append("record-node", node_record("review-a", "blocked", outputs=[], evidence=[]), at=T2)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("reasons", result["reasons"][0])
        # POSITIVE CONTROL: the same record WITH a reason is accepted.
        _, code = self.append(
            "record-node",
            node_record("review-a", "blocked", outputs=[], evidence=[], reasons=["dependency failed admission"]),
            at=T2,
        )
        self.assertEqual(code, EXIT_OK)

    def test_a_node_record_may_not_end_before_it_started_or_after_it_was_recorded(self) -> None:
        backwards, code = self.append(
            "record-node", node_record("implement-a", "admitted-success", started_at=T3, ended_at=T1), at=T4
        )
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("started_at", backwards["reasons"][0])
        later, code = self.append(
            "record-node", node_record("implement-a", "admitted-success", started_at=T1, ended_at=T4), at=T2
        )
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("ended_at", later["reasons"][0])
        # POSITIVE CONTROL: started <= ended <= recorded is accepted.
        _, code = self.append(
            "record-node", node_record("implement-a", "admitted-success", started_at=T1, ended_at=T2), at=T3
        )
        self.assertEqual(code, EXIT_OK)

    def test_a_malformed_timestamp_is_a_schema_verdict_not_a_state_refusal(self) -> None:
        for stamp in ("2026-08-19 02:00:00", "2026-08-19T02:00:00+00:00", "yesterday", "2026-08-19T02:00:00"):
            with self.subTest(stamp=stamp):
                result, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=stamp)
                self.assertEqual(code, EXIT_INPUT)
                self.assertIn("--at", result["reasons"][0])
                self.assertIn("exact YYYY-MM-DDTHH:MM:SSZ", result["reasons"][0])

    def test_a_well_shaped_timestamp_that_is_not_a_real_instant_is_refused_as_one(self) -> None:
        """The regex admits 2026-13-40T25:61:61Z; the calendar does not, and the message must say so.

        This case is why the check needs its own assertion rather than sharing the one above: with the
        calendar check removed, such a stamp parsed as a 1970 instant and the record was still refused
        -- by the unrelated `ended_at is after --at` rule, at the same exit code. A mutation run caught
        that accidental pass, so the reason is now asserted as well as the code.
        """
        result, code = self.append("record-node", node_record("implement-a", "admitted-success"), at="2026-13-40T25:61:61Z")
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("not a real instant", result["reasons"][0])
        # POSITIVE CONTROL: a real instant of the identical shape is accepted.
        _, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)

    def test_a_retry_may_not_be_recorded_over_an_unknown_prior_effect(self) -> None:
        """Issue 07: an unknown effect STOPS the workstream, so the honest record is `blocked`."""
        result, code = self.append("record-retry", retry_record(prior_effect="effect_unknown"), at=T2)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("effect_unknown", result["reasons"][0])
        self.assertIn("blocked", result["reasons"][0])
        # POSITIVE CONTROL: a proven-no-effect retry of the SAME capability is accepted.
        _, code = self.append("record-retry", retry_record(capability="write-capable"), at=T2)
        self.assertEqual(code, EXIT_OK)

    def test_a_write_capable_retry_must_carry_the_evidence_of_no_effect(self) -> None:
        result, code = self.append("record-retry", retry_record(capability="write-capable", evidence=[]), at=T2)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("evidence", result["reasons"][0])
        # POSITIVE CONTROL: a read-only retry needs no such evidence, so the rule is the capability's.
        _, code = self.append("record-retry", retry_record(capability="read-only", evidence=[]), at=T2)
        self.assertEqual(code, EXIT_OK)

    def test_an_approval_record_may_not_claim_to_be_authenticated(self) -> None:
        result, code = self.append("record-approval", approval_record(authenticated=True), at=T2)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("authenticated", result["reasons"][0])
        self.assertIn("stamps it false", result["reasons"][0])
        # POSITIVE CONTROL: the tool stamps the field itself, and stamps it false.
        _, code = self.append("record-approval", approval_record(), at=T2)
        self.assertEqual(code, EXIT_OK)
        self.assertIs(json.loads(self.lines()[1])["record"]["authenticated"], False)

    def test_a_static_dag_wave_may_not_declare_a_recursive_generation(self) -> None:
        fresh = self.tmp / "other.journal"
        record = header_record(limits={"max_concurrent_nodes": 4, "max_nodes": 64, "max_recursive_generations": 1})
        proc = self.run_tool(["init", "--journal", str(fresh), "--at", T0, "--record", json.dumps(record)])
        document = self.document(proc)
        self.assertEqual(proc.returncode, EXIT_INPUT)
        self.assertIn("static-dag", document["reasons"][0])
        self.assertFalse(fresh.exists())
        # POSITIVE CONTROL: the same limits under the recursive mode ARE accepted.
        proc = self.run_tool(
            ["init", "--journal", str(fresh), "--at", T0, "--record", json.dumps(header_record(mode="recursive", limits=record["limits"]))]
        )
        self.assertEqual(proc.returncode, EXIT_OK)

    def test_a_node_id_must_look_like_an_identifier(self) -> None:
        result, code = self.append("record-node", node_record("../escape", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("node_id", result["reasons"][0])

    def test_a_record_with_a_duplicate_json_key_is_refused(self) -> None:
        raw = '{"node_id":"a","node_id":"b"}'
        proc = self.run_tool(["record-node", "--journal", str(self.journal), "--at", T2, "--record", raw])
        document = self.document(proc)
        self.assertEqual(proc.returncode, EXIT_INPUT)
        self.assertIn("duplicate", document["reasons"][0])


class ApprovalBindingTests(_JournalTestCase):
    """An approval may name the exact prestate and candidate it authorizes; the shape is validated here.

    This tool observes no tree, so it can only prove such a digest is WELL FORMED. Comparing it against
    what a fan-in was really applied to is `wave-verdict.py`'s condition 5. What these tests pin is the
    three-way partition this surface admits -- a bound field is 64 lowercase hex, an unbound one is
    ABSENT, and everything else is a schema verdict -- plus the compatibility half: a journal written
    before the fields existed carries neither and is accepted exactly as it always was.
    """

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.init()["__code"], EXIT_OK)

    def test_an_approval_may_bind_the_prestate_and_candidate_it_authorizes(self) -> None:
        record = approval_record(prestate_digest=PRESTATE_DIGEST, candidate_digest=CANDIDATE_DIGEST)
        document, code = self.append("record-approval", record, at=T2)
        self.assertEqual(code, EXIT_OK)
        stored = json.loads(self.lines()[1])["record"]
        self.assertEqual(stored["prestate_digest"], PRESTATE_DIGEST)
        self.assertEqual(stored["candidate_digest"], CANDIDATE_DIGEST)
        # Binding narrows what the grant claims; it authenticates nothing, and the tool's own stamp is
        # unchanged by it.
        self.assertIs(stored["authenticated"], False)
        self.assertEqual(document["status"], "appended")
        # The projection republishes both, because the verdict tool reads the projection and not the
        # journal file: a binding the projection dropped would be a binding nobody could check.
        projection, code = self.project()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(
            [(item["prestate_digest"], item["candidate_digest"]) for item in projection["approvals"]],
            [(PRESTATE_DIGEST, CANDIDATE_DIGEST)],
        )

    def test_an_approval_that_binds_neither_digest_is_accepted_unchanged(self) -> None:
        """The compatibility half, asserted rather than assumed: absent stays legal and stays absent.

        Every other test in this module records this same unbound approval, so the regression control
        for the whole surface is the rest of the file; what this adds is that the stored line and the
        projection carry NO digest key at all, rather than a null one the verdict tool would then have
        to tell apart from a real binding.
        """
        _, code = self.append("record-approval", approval_record(), at=T2)
        self.assertEqual(code, EXIT_OK)
        stored = json.loads(self.lines()[1])["record"]
        self.assertNotIn("prestate_digest", stored)
        self.assertNotIn("candidate_digest", stored)
        projection, code = self.project()
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("prestate_digest", projection["approvals"][0])
        self.assertNotIn("candidate_digest", projection["approvals"][0])

    def test_either_binding_may_be_supplied_without_the_other(self) -> None:
        """The two fields are independent: a grant may bind its candidate and leave its prestate open.

        The alternative -- requiring them as a pair -- would forbid the honest middle case, and this
        module has no way to tell a caller which half they ought to have observed.
        """
        for field, value in (("prestate_digest", PRESTATE_DIGEST), ("candidate_digest", CANDIDATE_DIGEST)):
            with self.subTest(bound=field):
                fresh = self.tmp / f"only-{field}.journal"
                proc = self.run_tool(
                    ["init", "--journal", str(fresh), "--at", T0, "--record", json.dumps(header_record())]
                )
                self.assertEqual(proc.returncode, EXIT_OK)
                proc = self.run_tool(
                    [
                        "record-approval",
                        "--journal",
                        str(fresh),
                        "--at",
                        T2,
                        "--record",
                        json.dumps(approval_record(**{field: value})),
                    ]
                )
                self.assertEqual(proc.returncode, EXIT_OK, self.document(proc)["reasons"])
                stored = json.loads(fresh.read_bytes().splitlines()[1])["record"]
                self.assertEqual(stored[field], value)
                self.assertEqual(sorted(set(stored) & {"prestate_digest", "candidate_digest"}), [field])

    def test_a_binding_that_is_not_an_exact_sha256_is_a_schema_verdict(self) -> None:
        """Empty string, null, uppercase, short, long, and a number are each refused BY NAME.

        The empty string is the one that matters most and it is why this is not written as
        `if value and not _HEX64.match(value)`: an empty digest would then be admitted as though the
        grant bound nothing, so a grant that LOOKS bound to a reader would silently skip the
        comparison condition 5 exists to perform. Null is refused for the same reason -- absent is the
        one spelling of unbound, because a second spelling means two canonical forms and two entry
        digests for one fact.
        """
        rejected: list[Any] = ["", None, PRESTATE_DIGEST.upper(), "b" * 63, "b" * 65, 123, ["b" * 64], True]
        for field in ("prestate_digest", "candidate_digest"):
            for value in rejected:
                with self.subTest(field=field, value=value):
                    result, code = self.append(
                        "record-approval", approval_record(**{field: value}), at=T2
                    )
                    self.assertEqual(code, EXIT_INPUT)
                    self.assertEqual(result["effect"], "none")
                    self.assertEqual(result["admitted_effects"], [])
                    reason = result["reasons"][0]
                    self.assertIn(field, reason)
                    self.assertIn("64 lowercase hex", reason)
                    # The refusal must say how an unbound grant IS spelled, or a caller reaches for
                    # the empty string this test just refused.
                    self.assertIn("OMITS", reason)
                    self.assertEqual(len(self.lines()), 1)  # nothing was appended
        # POSITIVE CONTROL: an exact sha256 in the same field of the same record is accepted, so the
        # refusals above are about the VALUE and not about the field, the verb, or the fixture.
        for field, value in (("prestate_digest", PRESTATE_DIGEST), ("candidate_digest", CANDIDATE_DIGEST)):
            with self.subTest(accepted=field):
                _, code = self.append(
                    "record-approval",
                    approval_record(approval_id=f"approval-{field.replace('_', '-')}", **{field: value}),
                    at=T2,
                )
                self.assertEqual(code, EXIT_OK)

    def test_an_unrecognised_neighbour_field_is_still_refused(self) -> None:
        """The optional key set widened by exactly two names, and by no more than two.

        `_exact`'s extra-key half is what keeps a typo from becoming a silently dropped fact, and
        adding an `optional` parameter to it is exactly the change that could have opened the record to
        anything. So a third field -- including a plausible near-miss of one of the two -- is still a
        named refusal.
        """
        for field in ("prestate_sha256", "candidate", "prestatedigest", "target_digest"):
            with self.subTest(field=field):
                result, code = self.append("record-approval", approval_record(**{field: PRESTATE_DIGEST}), at=T2)
                self.assertEqual(code, EXIT_INPUT)
                self.assertIn("unrecognised", result["reasons"][0])
                self.assertIn(field, result["reasons"][0])
        # POSITIVE CONTROL: the two names that ARE optional pass through the same check.
        _, code = self.append(
            "record-approval",
            approval_record(prestate_digest=PRESTATE_DIGEST, candidate_digest=CANDIDATE_DIGEST),
            at=T2,
        )
        self.assertEqual(code, EXIT_OK)

    def test_a_required_approval_field_is_still_required(self) -> None:
        """The optional widening may not have made anything else optional."""
        complete = approval_record(prestate_digest=PRESTATE_DIGEST)
        for field in ("approval_id", "subject", "scope", "authority", "evidence"):
            with self.subTest(missing=field):
                partial = {key: value for key, value in complete.items() if key != field}
                result, code = self.append("record-approval", partial, at=T2)
                self.assertEqual(code, EXIT_INPUT)
                self.assertIn("missing required field(s)", result["reasons"][0])
                self.assertIn(field, result["reasons"][0])
        # POSITIVE CONTROL: the complete record, bindings and all, is accepted.
        _, code = self.append("record-approval", complete, at=T2)
        self.assertEqual(code, EXIT_OK)


class JournalStateTests(_JournalTestCase):
    """A refusal that depends on what the journal ALREADY says is a state refusal (3), not a schema one."""

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.init()["__code"], EXIT_OK)

    def test_a_timestamp_that_goes_backwards_is_refused_by_name(self) -> None:
        _, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T3)
        self.assertEqual(code, EXIT_OK)
        result, code = self.append(
            "record-budget", budget_record(), at=T2
        )
        self.assertEqual(code, EXIT_REFUSED)
        self.assertEqual(result["effect"], "none")
        self.assertEqual(result["admitted_effects"], [])
        reason = result["reasons"][0]
        self.assertIn("backwards", reason)
        self.assertIn(T2, reason)
        self.assertIn(T3, reason)
        self.assertEqual(len(self.lines()), 2)
        # POSITIVE CONTROL, and the reason this tool takes its time as an input at all: this host
        # steps CLOCK_REALTIME backwards, so the SAME instant and a later one must both be accepted.
        for label, at in (("same-instant", T3), ("later", T4)):
            with self.subTest(at=label):
                _, code = self.append("record-budget", budget_record(budget_id=f"budget-{label}"), at=at)
                self.assertEqual(code, EXIT_OK)

    def test_a_second_disposition_for_one_node_is_refused(self) -> None:
        _, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)
        result, code = self.append(
            "record-node",
            node_record("implement-a", "blocked", outputs=[], evidence=[], reasons=["changed my mind"]),
            at=T3,
        )
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("implement-a", result["reasons"][0])
        self.assertIn("exactly one", result["reasons"][0])
        self.assertEqual(len(self.lines()), 2)
        # POSITIVE CONTROL: a DIFFERENT node's disposition is accepted at the same instant, so the
        # refusal is about the node and not about the second append.
        _, code = self.append(
            "record-node",
            node_record("implement-b", "blocked", outputs=[], evidence=[], reasons=["dependency failed admission"]),
            at=T3,
        )
        self.assertEqual(code, EXIT_OK)

    def test_an_approved_skip_must_reference_an_approval_the_journal_carries(self) -> None:
        result, code = self.append(
            "record-node",
            node_record("implement-b", "approved-skip", approval="approval-skip-b", outputs=[], evidence=[]),
            at=T2,
        )
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("approval-skip-b", result["reasons"][0])
        self.assertEqual(len(self.lines()), 1)
        # POSITIVE CONTROL: recording the approval first makes the identical record acceptable, so
        # "approved" is derivable from the journal rather than asserted by the caller.
        _, code = self.append("record-approval", approval_record(), at=T2)
        self.assertEqual(code, EXIT_OK)
        _, code = self.append(
            "record-node",
            node_record("implement-b", "approved-skip", approval="approval-skip-b", outputs=[], evidence=[]),
            at=T2,
        )
        self.assertEqual(code, EXIT_OK)

    def test_an_approved_skip_must_be_named_in_its_approvals_scope(self) -> None:
        """Recorded is not authorized: the approval must actually name THIS node.

        Without this, any recorded approval -- even one scoped to a completely different node --
        would let an unrelated node claim `approved-skip`, which makes `approved` a fact about
        proximity in the journal rather than a fact the journal actually derives.
        """
        _, code = self.append("record-approval", approval_record(scope=["implement-c"]), at=T2)
        self.assertEqual(code, EXIT_OK)
        result, code = self.append(
            "record-node",
            node_record("implement-b", "approved-skip", approval="approval-skip-b", outputs=[], evidence=[]),
            at=T2,
        )
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("implement-b", result["reasons"][0])
        self.assertIn("implement-c", result["reasons"][0])
        self.assertEqual(len(self.lines()), 2)  # nothing beyond the recorded approval was appended
        # scope=["implement-c"] alone cannot distinguish exact membership from substring
        # containment, because "implement-b" is not a substring of "implement-c" either. This case
        # is the one that does: "implement-b" IS a substring of "implement-b-followup", so a check
        # weakened to substring containment would wrongly accept this as authorization. It must
        # refuse too.
        _, code = self.append(
            "record-approval",
            approval_record(approval_id="approval-skip-b-followup", scope=["implement-b-followup"]),
            at=T2,
        )
        self.assertEqual(code, EXIT_OK)
        result, code = self.append(
            "record-node",
            node_record("implement-b", "approved-skip", approval="approval-skip-b-followup", outputs=[], evidence=[]),
            at=T2,
        )
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("implement-b", result["reasons"][0])
        self.assertIn("implement-b-followup", result["reasons"][0])
        # POSITIVE CONTROL: the identical record is accepted once an approval scoped to implement-b
        # ALSO exists in the journal, so this is about scope membership and not about the node_id,
        # the disposition, or the approval_id shape.
        _, code = self.append("record-approval", approval_record(approval_id="approval-skip-b2", scope=["implement-b"]), at=T2)
        self.assertEqual(code, EXIT_OK)
        _, code = self.append(
            "record-node",
            node_record("implement-b", "approved-skip", approval="approval-skip-b2", outputs=[], evidence=[]),
            at=T2,
        )
        self.assertEqual(code, EXIT_OK)

    def test_a_plan_revision_must_reference_an_approval_the_journal_carries(self) -> None:
        result, code = self.append("record-plan-revision", plan_revision_record(), at=T2)
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("approval-revision-1", result["reasons"][0])
        self.append("record-approval", approval_record(approval_id="approval-revision-1", scope=["wave-1"]), at=T2)
        _, code = self.append("record-plan-revision", plan_revision_record(), at=T2)
        self.assertEqual(code, EXIT_OK)

    def test_one_approval_id_may_not_be_recorded_twice(self) -> None:
        _, code = self.append("record-approval", approval_record(), at=T2)
        self.assertEqual(code, EXIT_OK)
        result, code = self.append("record-approval", approval_record(subject="something else"), at=T2)
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("approval-skip-b", result["reasons"][0])
        # POSITIVE CONTROL: a different id is accepted.
        _, code = self.append("record-approval", approval_record(approval_id="approval-two"), at=T2)
        self.assertEqual(code, EXIT_OK)

    def test_a_retry_may_not_be_recorded_after_the_node_reached_its_disposition(self) -> None:
        _, code = self.append("record-node", node_record("review-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)
        result, code = self.append("record-retry", retry_record(), at=T3)
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("review-a", result["reasons"][0])
        # POSITIVE CONTROL: the retry of a node with no disposition yet is accepted.
        _, code = self.append("record-retry", retry_record(node_id="implement-a"), at=T3)
        self.assertEqual(code, EXIT_OK)


class TamperTests(_JournalTestCase):
    """A journal is only projectable while its own chain re-derives."""

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.init()["__code"], EXIT_OK)
        for node in ("implement-a", "implement-b"):
            _, code = self.append("record-node", node_record(node, "admitted-success"), at=T2)
            self.assertEqual(code, EXIT_OK)
        self.pristine = self.journal.read_bytes()

    def rewrite(self, lines: list[bytes]) -> None:
        self.journal.write_bytes(b"".join(lines))

    def project_result(self) -> tuple[dict[str, Any], int]:
        return self.project()

    def test_the_pristine_journal_projects(self) -> None:
        """POSITIVE CONTROL for every tamper below: this fixture is projectable before editing."""
        projection, code = self.project_result()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(projection["entry_count"], 2)

    def test_an_edited_line_breaks_the_chain(self) -> None:
        lines = self.pristine.splitlines(keepends=True)
        entry = json.loads(lines[1])
        entry["record"]["outputs"] = ["something else entirely"]
        lines[1] = canonical(entry)  # still canonical, still valid JSON, still seq 1
        self.rewrite(lines)
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("prev_digest", result["reasons"][0])
        self.assertEqual(result["effect"], "none")

    def test_a_reformatted_line_is_refused_even_though_it_parses(self) -> None:
        lines = self.pristine.splitlines(keepends=True)
        lines[0] = json.dumps(json.loads(lines[0]), sort_keys=True, indent=None).encode("utf-8") + b"\n"
        self.assertNotEqual(lines[0], self.pristine.splitlines(keepends=True)[0])  # the fixture differs
        self.rewrite(lines)
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("canonical", result["reasons"][0])

    def test_a_removed_middle_line_is_refused(self) -> None:
        lines = self.pristine.splitlines(keepends=True)
        del lines[1]
        self.rewrite(lines)
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("seq", result["reasons"][0])

    def test_a_second_wave_header_line_is_refused_by_name(self) -> None:
        """A perfectly chained second header, so nothing but the one-header rule can catch it."""
        lines = self.pristine.splitlines(keepends=True)
        header = json.loads(lines[0])
        header["seq"] = len(lines)
        header["prev_digest"] = sha256_hex(lines[-1])
        header["at"] = T5
        lines.append(canonical(header))
        self.rewrite(lines)
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("only line 0", result["reasons"][0])

    def test_a_stored_approval_may_not_be_edited_into_an_authenticated_one(self) -> None:
        """The last line is the one the chain cannot see, so the stored-shape check is the only guard.

        That is exactly why it exists: `authenticated` is the field an editor would want to flip, and
        flipping it on the final line leaves a self-consistent chain.
        """
        _, code = self.append("record-approval", approval_record(), at=T3)
        self.assertEqual(code, EXIT_OK)
        lines = self.journal.read_bytes().splitlines(keepends=True)
        entry = json.loads(lines[-1])
        self.assertIs(entry["record"]["authenticated"], False)  # the fixture starts honest
        entry["record"]["authenticated"] = True
        lines[-1] = canonical(entry)
        self.rewrite(lines)
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("authenticated", result["reasons"][0])

    def test_a_stored_approvals_binding_may_not_be_edited_into_an_empty_string(self) -> None:
        """The last line is the chain's blind spot, so the stored-shape check is the only guard.

        An editor who wants a bound grant to stop being compared does not need to delete the field --
        emptying it would do, if an empty string read as "binds nothing". It does not: the read path
        runs the same validator the write path did, so the projection is refused (3) rather than
        published with a grant that looks bound and checks nothing.
        """
        _, code = self.append("record-approval", approval_record(prestate_digest=PRESTATE_DIGEST), at=T3)
        self.assertEqual(code, EXIT_OK)
        lines = self.journal.read_bytes().splitlines(keepends=True)
        entry = json.loads(lines[-1])
        self.assertEqual(entry["record"]["prestate_digest"], PRESTATE_DIGEST)  # the fixture starts bound
        entry["record"]["prestate_digest"] = ""
        lines[-1] = canonical(entry)
        self.rewrite(lines)
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("prestate_digest", result["reasons"][0])
        self.assertIn("64 lowercase hex", result["reasons"][0])
        self.assertEqual(result["effect"], "none")
        # POSITIVE CONTROL: restoring the exact digest makes the same last line projectable again, so
        # the refusal is about the emptied value and not about having rewritten the line at all.
        entry["record"]["prestate_digest"] = PRESTATE_DIGEST
        lines[-1] = canonical(entry)
        self.rewrite(lines)
        _, code = self.project_result()
        self.assertEqual(code, EXIT_OK)

    def test_a_last_line_edited_to_go_backwards_in_time_is_still_refused(self) -> None:
        """The read path checks monotonicity too, which is what narrows the last-line blind spot.

        An editor of the final line cannot be caught by the chain, but they can be caught by the
        journal's own ordering: a record that claims to have happened before the one above it is
        refused on the way out as well as on the way in.
        """
        lines = self.pristine.splitlines(keepends=True)
        entry = json.loads(lines[-1])
        entry["at"] = T0
        lines[-1] = canonical(entry)
        self.rewrite(lines)
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("backwards", result["reasons"][0])
        # POSITIVE CONTROL: the same rewrite forward in time projects, so the refusal is the ordering.
        entry["at"] = T5
        lines[-1] = canonical(entry)
        self.rewrite(lines)
        _, code = self.project_result()
        self.assertEqual(code, EXIT_OK)

    def test_a_journal_path_that_is_not_a_regular_file_is_refused(self) -> None:
        directory = self.tmp / "as-a-directory.journal"
        directory.mkdir()
        proc = self.run_tool(["project", "--journal", str(directory)])
        self.assertEqual(proc.returncode, EXIT_REFUSED)
        self.assertIn("not a regular file", self.document(proc)["reasons"][0])

    def test_a_journal_whose_first_line_is_not_the_wave_header_is_refused(self) -> None:
        lines = self.pristine.splitlines(keepends=True)
        self.rewrite(lines[1:])
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertIn("wave-opened", result["reasons"][0])

    def test_a_truncated_last_line_is_refused(self) -> None:
        self.journal.write_bytes(self.pristine[:-8])
        result, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertEqual(result["effect"], "none")
        self.assertIn("truncated", result["reasons"][0])

    def test_the_last_line_is_the_one_edit_the_chain_cannot_see(self) -> None:
        """The documented limit, asserted so it stays documented rather than discovered.

        Nothing in the file anchors its head, so rewriting the FINAL line leaves a self-consistent
        chain. The projection therefore accepts it -- and the append results' `journal_digest` is the
        anchor a consumer has to retain to catch it. The positive control is the line BELOW: the same
        edit one line earlier IS caught, so this is a boundary and not a broken check.
        """
        lines = self.pristine.splitlines(keepends=True)
        entry = json.loads(lines[2])
        entry["record"]["outputs"] = ["a claim nobody made"]
        lines[2] = canonical(entry)
        self.rewrite(lines)
        projection, code = self.project_result()
        self.assertEqual(code, EXIT_OK)
        self.assertNotEqual(projection["journal_digest"], sha256_hex(self.pristine))

        lines = self.pristine.splitlines(keepends=True)
        entry = json.loads(lines[1])
        entry["record"]["outputs"] = ["a claim nobody made"]
        lines[1] = canonical(entry)
        self.rewrite(lines)
        _, code = self.project_result()
        self.assertEqual(code, EXIT_REFUSED)

    def test_a_tampered_journal_cannot_be_appended_to_either(self) -> None:
        lines = self.pristine.splitlines(keepends=True)
        entry = json.loads(lines[1])
        entry["at"] = T5
        lines[1] = canonical(entry)
        self.rewrite(lines)
        before = self.journal.read_bytes()
        result, code = self.append("record-budget", budget_record(), at=T5)
        self.assertEqual(code, EXIT_REFUSED)
        self.assertEqual(result["admitted_effects"], [])
        self.assertEqual(self.journal.read_bytes(), before)


# Every point in the append path, in the order the code reaches them. Only the first is before any
# effect; the rest each sit after a specific admitted one.
PRE_EFFECT_POINT = "before-staging-open"
STAGED_POINTS = ("after-staging-open", "after-staging-write", "after-staging-readback")
PUBLISHED_POINTS = ("after-rename", "after-publish-readback")


class InjectionSweepTests(_JournalTestCase):
    """A failure after ANY admitted effect is 4 and names what happened. Never 1, 2, or 3.

    This is the defect class this project has produced six instances of, and the only way to prove it
    is closed is to fail on purpose at every point in the mutating path and read the exit code back.
    The requested code is swept too: a site asking for 1 (internal), 2 (schema), or 3 (clean refusal)
    must be escalated once an effect exists, and the SAME request before any effect must survive
    unchanged -- which is what proves the escalation is derived from the ledger rather than hardcoded.
    """

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.init()["__code"], EXIT_OK)
        self.before = self.journal.read_bytes()

    def inject(self, point: str, code: int) -> tuple[dict[str, Any], int]:
        return self.append(
            "record-node",
            node_record("implement-a", "admitted-success"),
            at=T2,
            env={FAULT_ENV: f"{point}:{code}"},
        )

    def staging(self) -> Path:
        return self.journal.with_name(self.journal.name + ".next")

    def test_the_injector_can_produce_each_unescalated_code_before_any_effect(self) -> None:
        """POSITIVE CONTROL for the whole sweep: 1, 2, and 3 are reachable through this mechanism.

        Without this, every `assertEqual(code, 4)` below would also pass if the injector could only
        ever produce 4, or if it silently did nothing at all.
        """
        for requested in (EXIT_INTERNAL, EXIT_INPUT, EXIT_REFUSED):
            with self.subTest(requested=requested):
                result, code = self.inject(PRE_EFFECT_POINT, requested)
                self.assertEqual(code, requested)
                self.assertEqual(result["effect"], "none")
                self.assertEqual(result["admitted_effects"], [])
                self.assertEqual(self.journal.read_bytes(), self.before)
                self.assertFalse(self.staging().exists())

    def test_no_fault_point_leaves_the_append_unclassified(self) -> None:
        for point in STAGED_POINTS + PUBLISHED_POINTS:
            for requested in (EXIT_INTERNAL, EXIT_INPUT, EXIT_REFUSED):
                with self.subTest(point=point, requested=requested):
                    self.journal.write_bytes(self.before)
                    result, code = self.inject(point, requested)
                    self.assertEqual(code, EXIT_PARTIAL, f"{point} asked for {requested}")
                    self.assertIn(code, DECLARED_EXITS)
                    self.assertEqual(result["status"], "effect-unknown")
                    self.assertEqual(result["effect"], "effect_unknown")
                    self.assertTrue(result["admitted_effects"], "exit 4 with an empty ledger says nothing")
                    self.assertIn(point, result["reasons"][0])

    def test_the_ledger_names_the_staging_phase_and_leaves_the_journal_alone(self) -> None:
        for point in STAGED_POINTS:
            with self.subTest(point=point):
                self.journal.write_bytes(self.before)
                result, code = self.inject(point, EXIT_REFUSED)
                self.assertEqual(code, EXIT_PARTIAL)
                ledger = result["admitted_effects"]
                self.assertEqual(len(ledger), 1)
                self.assertIn("staging successor", ledger[0])
                self.assertIn("removed", ledger[0])
                self.assertNotIn("published", ledger[0])
                # The journal itself never moved, and the exit still says 4 rather than 3: an effect
                # this run cleaned up is still an effect it had.
                self.assertEqual(self.journal.read_bytes(), self.before)
                self.assertFalse(self.staging().exists())

    def test_the_ledger_names_the_publication_and_the_journal_really_moved(self) -> None:
        for point in PUBLISHED_POINTS:
            with self.subTest(point=point):
                self.journal.write_bytes(self.before)
                result, code = self.inject(point, EXIT_REFUSED)
                self.assertEqual(code, EXIT_PARTIAL)
                ledger = result["admitted_effects"]
                self.assertEqual(len(ledger), 2)
                self.assertIn("staging successor", ledger[0])
                self.assertNotIn("removed", ledger[0])  # a renamed file is not a removed one
                self.assertIn("published", ledger[1])
                # This is the case a clean refusal would have LIED about: the record is on disk.
                after = self.journal.read_bytes()
                self.assertTrue(after.startswith(self.before))
                self.assertEqual(json.loads(after.splitlines()[1])["record"]["node_id"], "implement-a")
                self.assertFalse(self.staging().exists())

    def test_the_same_append_with_no_fault_injected_succeeds(self) -> None:
        """The other half of the control: the sweep's command is a WORKING command."""
        self.journal.write_bytes(self.before)
        result, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["seq"], 1)
        self.assertEqual(len(self.lines()), 2)

    def test_init_escalates_the_same_way(self) -> None:
        """The append path is not the only mutating one; `init` publishes through it too."""
        for point in STAGED_POINTS + PUBLISHED_POINTS:
            with self.subTest(point=point):
                fresh = self.tmp / f"init-{point}.journal"
                proc = self.run_tool(
                    ["init", "--journal", str(fresh), "--at", T0, "--record", json.dumps(header_record())],
                    env={FAULT_ENV: f"{point}:{EXIT_REFUSED}"},
                )
                document = self.document(proc)
                self.assertEqual(proc.returncode, EXIT_PARTIAL)
                self.assertTrue(document["admitted_effects"])
                self.assertEqual(fresh.exists(), point in PUBLISHED_POINTS)

    def test_a_stale_staging_successor_is_refused_rather_than_reused(self) -> None:
        """It is somebody else's incomplete write, so it is neither clobbered nor trusted."""
        self.staging().write_bytes(b"leftover from a crashed run\n")
        result, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_REFUSED)
        self.assertEqual(result["admitted_effects"], [])
        self.assertEqual(result["effect"], "none")
        self.assertEqual(self.staging().read_bytes(), b"leftover from a crashed run\n")
        self.assertEqual(self.journal.read_bytes(), self.before)
        # POSITIVE CONTROL: removing the leftover makes the identical append succeed.
        self.staging().unlink()
        _, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)


@contextlib.contextmanager
def constructed_control_environment() -> Any:
    """Drop the tool's control variables from THIS process, for the one test that runs it in-process.

    `run_tool` constructs a subprocess environment, but a writer running in this process reads this
    process's own, so the same scrub has to apply here or an exported fault variable reaches it.
    """
    removed = {key: os.environ.pop(key) for key in sorted(TOOL_CONTROL_ENV) if key in os.environ}
    try:
        yield
    finally:
        os.environ.update(removed)


def load_tool_in_process() -> Any:
    """Load the tool as a module, so ONE test can order two writers without a clock.

    Every other test here drives the real subprocess, and that stays the rule for this family. This
    one needs writer B's whole append to land BETWEEN writer A's read and writer A's publish, and a
    subprocess offers no honest place to stand inside that window: the alternatives are a forked
    racer and a sleep, which is exactly the timing-dependent test this repository forbids. So writer
    A runs in THIS process, where its own `read_journal` can be wrapped, while writer B stays a real
    separate invocation -- which is what makes B's entry a committed record rather than a fixture.
    The tool's name has a hyphen in it and cannot be imported, hence the explicit spec.
    """
    spec = importlib.util.spec_from_file_location("wave_journal_under_test", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InterleavedWriterTests(_JournalTestCase):
    """A successor built from a stale read may not be published over another writer's record.

    Two processes appending to one journal is unsupported, and this is what "unsupported" is allowed
    to mean: DETECTED, not silently destructive. Without the pre-publish re-comparison, writer A
    reads a two-line journal, writer B appends and COMMITS a third line, and A then publishes its own
    successor built from the two-line prefix. Both writers exit 0, the chain A leaves behind is
    self-consistent, B's committed record is gone, and `project` cannot see that anything was lost --
    the last-line limit in `read_journal`'s docstring is exactly why the file alone cannot tell.
    """

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.init()["__code"], EXIT_OK)
        first, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK)
        # The two lines writer A reads, and the prefix its successor would be built from.
        self.stale = self.journal.read_bytes()
        self.assertEqual(len(self.stale.splitlines()), 2)

    def staging(self) -> Path:
        return self.journal.with_name(self.journal.name + ".next")

    def writer_a(self, interleave: Any) -> tuple[dict[str, Any], int]:
        """Run writer A here, calling `interleave` at the instant its read returns.

        The seam is one wrapper around the tool's own `read_journal`, so the ordering is a program
        order rather than a race: A has read, `interleave` runs to completion, and only then does A
        stage, re-check, and publish.
        """
        module = load_tool_in_process()
        original, reads = module.read_journal, []

        def read_journal(parent_fd: int, name: str) -> Any:
            answer = original(parent_fd, name)
            reads.append(name)
            interleave()
            return answer

        module.read_journal = read_journal
        out, err = io.StringIO(), io.StringIO()
        with constructed_control_environment(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = module.main(
                [
                    "record-node",
                    "--journal",
                    str(self.journal),
                    "--at",
                    T4,
                    "--record",
                    json.dumps(node_record("review-a", "admitted-success", role="reviewer")),
                ]
            )
        self.assertEqual(len(reads), 1, "writer A never reached the read this seam stands on")
        document = json.loads(out.getvalue())
        self.assertEqual(out.getvalue().encode("utf-8"), canonical(document), "stdout is not canonical")
        return document, code

    def writer_b(self) -> None:
        """Writer B's whole append, as a separate committed invocation."""
        _, code = self.append("record-node", node_record("implement-b", "admitted-success"), at=T3)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(len(self.lines()), 3)

    def test_an_interleaved_committed_append_is_detected_instead_of_overwritten(self) -> None:
        document, code = self.writer_a(self.writer_b)
        self.assertEqual(code, EXIT_PARTIAL, "a stale successor must not be published at exit 0")
        self.assertIn(code, DECLARED_EXITS)
        self.assertEqual(document["status"], "effect-unknown")
        self.assertEqual(document["effect"], "effect_unknown")
        # The staging bytes really existed, so this is 4 rather than 3, and the ledger names it.
        self.assertTrue(document["admitted_effects"], "exit 4 with an empty ledger says nothing")
        self.assertIn("staging successor", document["admitted_effects"][0])
        self.assertNotIn("published", " ".join(document["admitted_effects"]))
        self.assertIn("another writer", document["reasons"][0])
        # B's record SURVIVES, which is the whole point: the journal is B's three lines, not A's.
        after = self.journal.read_bytes()
        self.assertTrue(after.startswith(self.stale))
        self.assertEqual(len(after.splitlines()), 3)
        self.assertEqual(json.loads(after.splitlines()[2])["record"]["node_id"], "implement-b")
        self.assertFalse(self.staging().exists())
        projection, code = self.project()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(sorted(projection["dispositions"]), ["implement-a", "implement-b"])

    def test_the_same_sequence_without_the_interleaved_commit_appends(self) -> None:
        """POSITIVE CONTROL: the seam itself refuses nothing -- only the changed journal does."""
        document, code = self.writer_a(lambda: None)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(document["status"], "appended")
        self.assertEqual(document["seq"], 2)
        # A success names its own effects too, and the last of them IS the publication -- so this
        # control proves the seam reaches the rename rather than stopping short of it.
        self.assertIn("published", document["admitted_effects"][-1])
        after = self.journal.read_bytes()
        self.assertTrue(after.startswith(self.stale))
        self.assertEqual(json.loads(after.splitlines()[2])["record"]["node_id"], "review-a")
        self.assertFalse(self.staging().exists())


class InterleavedInitTests(_JournalTestCase):
    """`_publish`'s RENAME_NOREPLACE guard, killed by the same ordering seam without a forked racer.

    Its docstring used to say this guard was the one thing here no test kills, because the only race
    it defends against is two concurrent `init`s for the SAME journal path, and forking a racer to hit
    that window would be exactly the timing-dependent test this repository forbids. It is drivable
    anyway: writer A's `_publish` is wrapped so a real, separately committed writer B's WHOLE `init`
    runs to completion in PROGRAM ORDER between A's absence pre-check and A's rename, the same
    generalisation `InterleavedWriterTests` already uses for the append path's own race.
    """

    def staging(self) -> Path:
        return self.journal.with_name(self.journal.name + ".next")

    def writer_a(self, interleave: Any, *, header: dict[str, Any] | None = None) -> tuple[dict[str, Any], int]:
        """Run writer A's `init` here, calling `interleave` at the instant its own publish begins.

        Wrapping `_publish` rather than a lower primitive is what places the seam exactly where the
        docstring's race window starts: `init_command` calls `_publish` immediately after its `os.stat`
        pre-check finds the journal absent, and immediately before that call is staging, write, and
        rename.
        """
        module = load_tool_in_process()
        original, calls = module._publish, []

        def _publish(parent_fd: int, name: str, data: bytes, *, replace: bool, bound: Any) -> None:
            calls.append(name)
            interleave()
            return original(parent_fd, name, data, replace=replace, bound=bound)

        module._publish = _publish
        out, err = io.StringIO(), io.StringIO()
        with constructed_control_environment(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = module.main(
                [
                    "init",
                    "--journal",
                    str(self.journal),
                    "--at",
                    T1,
                    "--record",
                    json.dumps(header if header is not None else header_record(wave_id="wave-a-loses")),
                ]
            )
        self.assertEqual(len(calls), 1, "writer A never reached the publish this seam stands on")
        document = json.loads(out.getvalue())
        self.assertEqual(out.getvalue().encode("utf-8"), canonical(document), "stdout is not canonical")
        return document, code

    def writer_b(self) -> None:
        """Writer B's WHOLE `init`, as a separate committed invocation that wins the race."""
        result = self.init()
        self.assertEqual(result["__code"], EXIT_OK)

    def test_a_second_committed_init_is_refused_at_exit_4_not_silently_overwritten(self) -> None:
        self.assertFalse(self.journal.exists(), "writer A must start the race against an absent journal")
        document, code = self.writer_a(self.writer_b)
        self.assertEqual(code, EXIT_PARTIAL, "the loser of the race must not silently clobber the winner")
        self.assertIn(code, DECLARED_EXITS)
        self.assertEqual(document["status"], "effect-unknown")
        self.assertEqual(document["effect"], "effect_unknown")
        # The staging bytes really existed, so this is 4 rather than 3, and the ledger names it.
        self.assertTrue(document["admitted_effects"], "exit 4 with an empty ledger says nothing")
        self.assertIn("staging successor", document["admitted_effects"][0])
        self.assertNotIn("published", " ".join(document["admitted_effects"]))
        self.assertIn("appeared after this run checked for it", document["reasons"][0])
        self.assertFalse(self.staging().exists(), "writer A's own abandoned staging file must be removed")
        # B's journal SURVIVES, which is the whole point: the file on disk is B's opening line, not A's.
        opened = json.loads(self.journal.read_bytes())
        self.assertEqual(opened["record"]["wave_id"], "wave-1")  # writer_b()/self.init()'s default
        self.assertEqual(len(self.lines()), 1)

    def test_the_same_sequence_without_the_interleaved_init_succeeds(self) -> None:
        """POSITIVE CONTROL: the seam itself refuses nothing -- only the raced file does."""
        document, code = self.writer_a(lambda: None)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(document["status"], "initialized")
        self.assertEqual(document["seq"], 0)
        self.assertTrue(self.journal.exists())
        self.assertEqual(json.loads(self.journal.read_bytes())["record"]["wave_id"], "wave-a-loses")
        self.assertFalse(self.staging().exists())


class EffectLedgerNestingTests(_JournalTestCase):
    """`_effect_ledger`'s own stated rationale, actually driven.

    Its docstring claims restoring rather than clearing "keeps a test that drives two commands in one
    process from erasing the outer command's admitted effects" -- a claim nothing here exercised
    before this class: every other in-process test (`InterleavedWriterTests`, `InterleavedInitTests`)
    calls `module.main` exactly once. This holds an OUTER ledger open by hand, runs a WHOLE nested
    `init` invocation (which enters and exits its own fresh ledger internally), and proves the outer
    one survives byte-for-byte and by identity.
    """

    def test_a_nested_command_does_not_erase_the_outer_ledgers_admitted_effects(self) -> None:
        module = load_tool_in_process()
        with module._effect_ledger() as outer:
            outer.admit("an effect the OUTER context admitted before any nested command ran")
            out = io.StringIO()
            with constructed_control_environment(), contextlib.redirect_stdout(out):
                code = module.main(
                    ["init", "--journal", str(self.journal), "--at", T0, "--record", json.dumps(header_record())]
                )
            # The nested command ran its own complete lifecycle, admitting its OWN effects...
            self.assertEqual(code, EXIT_OK)
            nested = json.loads(out.getvalue())
            self.assertTrue(nested["admitted_effects"])
            # ...and yet the module-global ledger is once again THIS SAME outer object, not the
            # nested command's fresh one left behind: it was RESTORED, not merely replaced or cleared.
            self.assertIs(module._EFFECTS, outer)
            self.assertEqual(
                outer.admitted, ["an effect the OUTER context admitted before any nested command ran"]
            )
        # POSITIVE CONTROL: a second, independent outer context starts empty and accumulates its own
        # effect -- proving the assertions above exercise real accumulation, not a vacuously-true
        # comparison of two ledgers that both happen to be empty.
        with module._effect_ledger() as outer2:
            self.assertEqual(outer2.admitted, [])
            outer2.admit("a second, independent outer context's own effect")
            self.assertEqual(outer2.admitted, ["a second, independent outer context's own effect"])


class NoClockTests(unittest.TestCase):
    """Timestamps are inputs. A clock read inside the tool would make the journal untestable.

    Seed agentic-sdlc-184b measured this host stepping CLOCK_REALTIME BACKWARDS by 0.22-0.53s, which
    already broke one monotonicity check elsewhere in this repository. A journal that read its own
    clock would therefore refuse its own honest sequence at random.

    PATTERNS is a per-attribute substring list, and it is only ever as complete as whoever last
    enumerated the clock module's attributes: it used to be missing `time.time_ns`,
    `time.perf_counter`, and `os.times`, none of which is a style variant of an already-listed
    pattern. `NO_TIME_IMPORT` is the STRONGER check that does not need that enumeration kept current:
    `time` is not imported anywhere in this module at all, so every one of `time.time`,
    `time.time_ns`, `time.monotonic`, `time.monotonic_ns`, `time.perf_counter`,
    `time.perf_counter_ns`, and `time.clock_gettime` -- named individually above or not -- is
    unreachable in one move. `os` stays a PATTERN-only check because `os` genuinely is imported here
    for non-clock reasons, so "os is never imported" is not a check this module could pass.
    """

    PATTERNS = (
        "datetime.now",
        "datetime.utcnow",
        "utcnow(",
        "time.time(",
        "time.time_ns(",
        "time.monotonic(",
        "time.perf_counter(",
        "time.clock_gettime",
        "date.today(",
        "fromtimestamp(",
        "os.times(",
    )
    NO_TIME_IMPORT = re.compile(r"^\s*(import time\b|from time import)", re.MULTILINE)

    def test_the_source_reads_no_clock(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        hits = [pattern for pattern in self.PATTERNS if pattern in source]
        self.assertEqual(hits, [])
        self.assertIsNone(
            self.NO_TIME_IMPORT.search(source),
            "the time module must never be imported here: every clock-reading attribute it exposes "
            "becomes reachable in one move, not only the ones PATTERNS happens to name",
        )

    def test_the_clock_detector_actually_detects_a_clock(self) -> None:
        """POSITIVE CONTROL: without this, the assertion above passes on an empty pattern list."""
        planted = "stamp = datetime.now(UTC).isoformat()\nelapsed = time.time()\nspent = os.times()\n"
        hits = [pattern for pattern in self.PATTERNS if pattern in planted]
        self.assertEqual(sorted(hits), ["datetime.now", "os.times(", "time.time("])

    def test_the_time_import_detector_actually_detects_an_import(self) -> None:
        """POSITIVE CONTROL for `NO_TIME_IMPORT`: a bare `import time` catches every one of its
        clock-reading attributes at once, which is the whole point of asserting on the import
        rather than enumerating the module's attributes one PATTERNS entry at a time.
        """
        planted = "import time\nelapsed = time.perf_counter_ns()\n"
        self.assertIsNotNone(self.NO_TIME_IMPORT.search(planted))
        # None of the enumerated PATTERNS would have caught THIS particular attribute on its own --
        # that gap is exactly why the module-level guard exists.
        self.assertEqual([pattern for pattern in self.PATTERNS if pattern in planted], [])


_ENV_TOUCH = re.compile(r"os\.(?:environ|getenv)\b")
_ENV_READ = re.compile(r"os\.(?:environ\.get\(|getenv\(|environ\[)\s*(\"[^\"]*\"|[A-Za-z_][A-Za-z0-9_]*)")
_STRING_CONSTANT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*) = \"([^\"]*)\"$", re.MULTILINE)


def environment_names_read(source: str) -> tuple[list[str], list[str]]:
    """Every variable `source` reads by name, and every access this cannot resolve to a name.

    The unresolved list is the half that matters: a read this cannot name (`dict(os.environ)`, a
    computed key) must NOT pass silently, because the scrub can only remove names it knows.
    """
    constants = dict(_STRING_CONSTANT.findall(source))
    names: list[str] = []
    unresolved: list[str] = []
    for touch in _ENV_TOUCH.finditer(source):
        read = _ENV_READ.match(source, touch.start())
        if read is None:
            unresolved.append(source[touch.start() : touch.start() + 32])
            continue
        token = read.group(1)
        if token.startswith('"'):
            names.append(token.strip('"'))
        elif token in constants:
            names.append(constants[token])
        else:
            unresolved.append(token)
    return sorted(set(names)), unresolved


class EnvironmentIsolationTests(_JournalTestCase):
    """Each test's environment is CONSTRUCTED. The suite may not read its own injector out of the shell.

    A copied environment made the tool's one fault variable a suite-wide switch: exporting
    `AGENTIC_SDLC_WAVE_JOURNAL_FAULT=after-rename:3` -- which is what a developer debugging this very
    tool does -- turned most of this module red at points unrelated to the code under test, and a
    reddened gate that blames the wrong line is worse than no gate.
    """

    def export(self, name: str, value: str) -> None:
        """Export `name` for this test as the ambient environment would, and restore it after."""
        previous = os.environ.get(name)

        def restore() -> None:
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous

        self.addCleanup(restore)
        os.environ[name] = value

    def test_an_ambient_fault_variable_cannot_reach_the_tool(self) -> None:
        self.export(FAULT_ENV, f"after-rename:{EXIT_REFUSED}")
        # Both mutating verbs, because both publish and both would have been hit by the inherited one.
        self.assertEqual(self.init()["__code"], EXIT_OK)
        result, code = self.append("record-node", node_record("implement-a", "admitted-success"), at=T2)
        self.assertEqual(code, EXIT_OK, "the ambient fault variable reached the tool")
        self.assertEqual(result["status"], "appended")
        self.assertEqual(len(self.lines()), 2)
        # POSITIVE CONTROL: the SAME fault, supplied by the test instead of the shell, still fires --
        # so the exit 0 above is the scrub working rather than the seam being dead or the point wrong.
        result, code = self.append(
            "record-node",
            node_record("review-a", "admitted-success", role="reviewer"),
            at=T3,
            env={FAULT_ENV: f"after-rename:{EXIT_REFUSED}"},
        )
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertIn("after-rename", result["reasons"][0])

    @unittest.skipUnless(POSIX, "the hostile-fd helpers are POSIX-only")
    def test_the_hostile_fd_helpers_do_not_inherit_it_either(self) -> None:
        """`run_tool` is not the only spawn point, and a scrub on one path is not a scrub.

        Each helper is checked through the observable that would actually change: the exit code where
        an injected fault would move it, and the REPORTED EFFECT where it would not -- a broken stdout
        is exit 4 either way, so only the reason distinguishes an honest stdout failure from an
        inherited fault wearing its exit code.
        """
        self.export(FAULT_ENV, f"after-rename:{EXIT_REFUSED}")
        code, _ = _run_with_hostile_stderr(
            [sys.executable, "-B", str(TOOL), "init", "--journal", str(self.journal), "--at", T0, "--record", json.dumps(header_record())],
            mode="closed",
            cwd=self.tmp,
        )
        self.assertEqual(code, EXIT_OK, "the hostile-stderr helper inherited the fault variable")
        code, err = _run_with_hostile_stdout(
            [
                sys.executable, "-B", str(TOOL), "record-node",
                "--journal", str(self.journal), "--at", T2,
                "--record", json.dumps(node_record("implement-a", "admitted-success")),
            ],
            cwd=self.tmp,
        )
        self.assertEqual(code, EXIT_PARTIAL)  # a broken stdout is 4 on its own merits
        self.assertNotIn(b"injected fault", err, "the hostile-stdout helper inherited the fault variable")
        self.assertIn(b"prefix of the result document", err)

    def test_the_scrub_names_every_control_variable_the_tool_reads(self) -> None:
        """The scrub set is derived from the tool's source, so a second control variable cannot slip in."""
        names, unresolved = environment_names_read(TOOL.read_text(encoding="utf-8"))
        self.assertEqual(unresolved, [])
        self.assertEqual(names, sorted(TOOL_CONTROL_ENV))

    def test_the_control_variable_detector_actually_detects_one(self) -> None:
        """POSITIVE CONTROL: without this, the assertion above passes on a detector that finds nothing."""
        planted = 'TRACE = "AGENTIC_SDLC_WAVE_JOURNAL_TRACE"\nx = os.environ.get(TRACE)\ny = os.getenv("PLAIN")\n'
        self.assertEqual(environment_names_read(planted), (["AGENTIC_SDLC_WAVE_JOURNAL_TRACE", "PLAIN"], []))
        # And a read it cannot name is reported as unresolved rather than as no read at all.
        self.assertTrue(environment_names_read("copy = dict(os.environ)\n")[1])


def _run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Two shapes, kept apart because they fail differently and neither is exotic:

        closed  `exec 2>&-`, so the interpreter starts with `sys.stderr is None` and the first
                `sys.stderr.write` raises `AttributeError`, not `OSError`.
        epipe   fd 2 is a pipe whose reader is already gone, so every write raises EPIPE and leaves
                bytes pending that the interpreter flushes AGAIN while finalizing -- which is how
                an honest exit code gets replaced by 120.

    Stderr is deliberately not captured: capturing it would hand the child a writable stream and
    prove nothing.
    """
    if mode == "closed":
        proc = subprocess.run(
            ["sh", "-c", 'exec 2>&-; exec "$@"', "sh", *argv],
            stdout=subprocess.PIPE,
            cwd=str(cwd),
            env=constructed_environment(),
            check=False,
        )
        return proc.returncode, proc.stdout
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stderr mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the reader is gone BEFORE the child starts, so no write can succeed
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd), env=constructed_environment())
    finally:
        os.close(write_fd)
    assert child.stdout is not None
    with child.stdout as stream:
        out = stream.read()
    return child.wait(), out


def _stderr_is_really_hostile(mode: str, cwd: Path) -> str:
    """What a canary child OBSERVES about its own stderr under `mode`, reported over stdout."""
    canary = (
        "import sys\n"
        "if sys.stderr is None:\n"
        "    print('none')\n"
        "else:\n"
        "    try:\n"
        "        sys.stderr.write('x')\n"
        "        sys.stderr.flush()\n"
        "        print('writable')\n"
        "    except OSError as exc:\n"
        "        print(type(exc).__name__)\n"
    )
    code, out = _run_with_hostile_stderr([sys.executable, "-B", "-c", canary], mode=mode, cwd=cwd)
    return f"{code}:{out.decode('utf-8', 'replace').strip()}"


@unittest.skipUnless(POSIX, "fd-level stderr hostility is POSIX-only")
class HostileStderrTests(_JournalTestCase):
    """A stderr that cannot be written costs the display channel, never the record or the code."""

    def test_the_hostile_stderr_fixture_is_actually_hostile(self) -> None:
        """The control for every assertion below: the child really has no usable stderr."""
        self.assertEqual(_stderr_is_really_hostile("closed", self.tmp), "0:none")
        self.assertEqual(_stderr_is_really_hostile("epipe", self.tmp), "120:BrokenPipeError")

    def test_a_hostile_stderr_cannot_cost_an_append_its_record_or_its_exit_code(self) -> None:
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                journal = self.tmp / f"hostile-{mode}.journal"
                init = _run_with_hostile_stderr(
                    [
                        sys.executable, "-B", str(TOOL), "init",
                        "--journal", str(journal), "--at", T0,
                        "--record", json.dumps(header_record()),
                    ],
                    mode=mode,
                    cwd=self.tmp,
                )
                self.assertEqual(init[0], EXIT_OK)
                code, stdout = _run_with_hostile_stderr(
                    [
                        sys.executable, "-B", str(TOOL), "record-node",
                        "--journal", str(journal), "--at", T2,
                        "--record", json.dumps(node_record("implement-a", "admitted-success")),
                    ],
                    mode=mode,
                    cwd=self.tmp,
                )
                self.assertEqual(code, EXIT_OK)
                self.assertIn(code, DECLARED_EXITS)  # 120 and 1 are both wrong answers here
                self.assertEqual(len(journal.read_bytes().splitlines()), 2)
                document = json.loads(stdout.decode("utf-8"))
                self.assertEqual(document["seq"], 1)

    def test_a_hostile_stderr_cannot_demote_a_clean_refusal(self) -> None:
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                journal = self.tmp / f"missing-{mode}.journal"
                code, stdout = _run_with_hostile_stderr(
                    [
                        sys.executable, "-B", str(TOOL), "record-node",
                        "--journal", str(journal), "--at", T2,
                        "--record", json.dumps(node_record("implement-a", "admitted-success")),
                    ],
                    mode=mode,
                    cwd=self.tmp,
                )
                self.assertEqual(code, EXIT_REFUSED)
                self.assertIn(code, DECLARED_EXITS)
                self.assertFalse(journal.exists())
                self.assertEqual(json.loads(stdout.decode("utf-8"))["effect"], "none")

    def test_a_hostile_stderr_cannot_demote_a_usage_error(self) -> None:
        """argparse writes usage to stderr, and a swallowed write there used to become 120."""
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, _ = _run_with_hostile_stderr(
                    [sys.executable, "-B", str(TOOL), "record-node", "--not-an-option"],
                    mode=mode,
                    cwd=self.tmp,
                )
                self.assertEqual(code, EXIT_INPUT)
                self.assertIn(code, DECLARED_EXITS)


def _run_with_hostile_stdout(argv: list[str], *, cwd: Path) -> tuple[int, bytes]:
    """Run argv with fd 1 pointed at a pipe whose reader is already gone. Returns (code, stderr)."""
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


@unittest.skipUnless(POSIX, "fd-level stdout hostility is POSIX-only")
class HostileStdoutTests(_JournalTestCase):
    """stdout carries the RESULT, so its failure is an admitted effect -- and still never a 120.

    This is the one route by which the read-only `project` verb can reach exit 4, and the module
    docstring says so: an unknown prefix of the document may already have been consumed, which is an
    effect on the caller's stream even though nothing on disk moved.
    """

    def test_a_broken_stdout_really_costs_an_ordinary_process_its_exit_code(self) -> None:
        """POSITIVE CONTROL: this fixture really breaks fd 1, and an unguarded program pays for it.

        MEASURED on the pinned interpreter (CPython 3.12.11, the uv-supplied build) rather than
        assumed, because the two display channels do NOT behave alike here:

            stderr, bytes pending at finalization -> 120  (asserted in `HostileStderrTests`)
            stdout, bare `print`                  ->   1  with an uncaught BrokenPipeError
            stdout, caught write + `sys.exit(3)`  ->   3  (the buffer is dropped, so no second flush)

        So on this interpreter the stdout channel's danger is the uncaught exception, not 120: an
        unguarded `_emit` would have reported 1 over a durable append. Both wrong answers are checked
        for below; the assertion here is only that the fixture is hostile at all.

        RE-MEASUREMENT PIN: this is CPython 3.12.11's own broken-pipe/finalization behaviour, not this
        tool's. A future bump of the pinned interpreter (`mise.toml` / `mise.lock`) can change which of
        1, 120, or something else a bare hostile write costs an unguarded program, which would silently
        invalidate the three-way table above without failing any assertion by itself. Re-measure this
        test's own fixture on the new interpreter before trusting it again.
        """
        if sys.version_info[:3] != (3, 12, 11):
            self.skipTest("this fixture's measured exit codes are pinned to CPython 3.12.11; re-measure before trusting it on another interpreter")
        code, err = _run_with_hostile_stdout(
            [sys.executable, "-B", "-c", "print('x' * 100000)"], cwd=self.tmp
        )
        self.assertIn(b"BrokenPipeError", err)
        self.assertNotEqual(code, EXIT_OK)
        self.assertIn(code, (EXIT_INTERNAL, 120))

    def test_a_broken_stdout_cannot_hide_an_append_that_happened(self) -> None:
        self.init()
        before = self.journal.read_bytes()
        code, err = _run_with_hostile_stdout(
            [
                sys.executable, "-B", str(TOOL), "record-node",
                "--journal", str(self.journal), "--at", T2,
                "--record", json.dumps(node_record("implement-a", "admitted-success")),
            ],
            cwd=self.tmp,
        )
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertIn(code, DECLARED_EXITS)  # 1 (uncaught) and 120 are both wrong answers here
        self.assertTrue(self.journal.read_bytes().startswith(before))
        self.assertEqual(len(self.lines()), 2)  # the record IS durable
        self.assertIn(b"already happened", err)
        self.assertIn(b"stdout", err)

    def test_a_broken_stdout_is_the_only_way_project_reaches_four(self) -> None:
        self.init()
        before = self.journal.read_bytes()
        code, err = _run_with_hostile_stdout(
            [sys.executable, "-B", str(TOOL), "project", "--journal", str(self.journal)], cwd=self.tmp
        )
        self.assertEqual(code, EXIT_PARTIAL)
        self.assertEqual(self.journal.read_bytes(), before)  # a read verb wrote nothing
        # 4 with an empty ledger would say nothing: the one effect there IS must be named.
        self.assertIn(b"already happened", err)
        self.assertIn(b"prefix of the result document", err)
        # POSITIVE CONTROL: over a working stdout the same command is a clean 0.
        projection, ok = self.project()
        self.assertEqual(ok, EXIT_OK)
        self.assertEqual(projection["effect"], "none")


class SurfaceTests(_JournalTestCase):
    def test_a_record_may_be_supplied_as_a_file(self) -> None:
        path = self.tmp / "header.json"
        path.write_text(json.dumps(header_record()), encoding="utf-8")
        proc = self.run_tool(["init", "--journal", str(self.journal), "--at", T0, "--record", f"@{path}"])
        self.assertEqual(proc.returncode, EXIT_OK)
        # POSITIVE CONTROL: an unreadable path is a schema verdict rather than a silent empty record.
        proc = self.run_tool(
            ["record-node", "--journal", str(self.journal), "--at", T2, "--record", f"@{self.tmp / 'nope.json'}"]
        )
        self.assertEqual(proc.returncode, EXIT_INPUT)
        self.assertIn("cannot read --record file", self.document(proc)["reasons"][0])

    def test_projecting_an_absent_journal_is_a_clean_refusal(self) -> None:
        result, code = self.project()
        self.assertEqual(code, EXIT_REFUSED)
        self.assertEqual(result["effect"], "none")
        self.assertEqual(result["admitted_effects"], [])

    def test_the_journal_argument_may_not_name_the_staging_successor(self) -> None:
        proc = self.run_tool(
            ["init", "--journal", str(self.journal) + ".next", "--at", T0, "--record", json.dumps(header_record())]
        )
        self.assertEqual(proc.returncode, EXIT_INPUT)
        self.assertIn(".next", self.document(proc)["reasons"][0])

    def test_a_symlinked_journal_is_refused_rather_than_followed(self) -> None:
        """The refusal must be THIS TOOL'S classification, not the kernel's ELOOP strerror in disguise.

        On Linux, `os.strerror(errno.ELOOP)` is "Too many levels of symbolic links", which itself
        contains the substring "symbolic link" -- so an `assertIn("symbolic link", ...)` here would
        ALSO pass on the tool's GENERIC `cannot read {label} {name}: {exc}` fallback branch, which
        stringifies that same OSError, if the errno-specific branch that actually names the symlink
        were ever removed. Asserting the EXACT message this tool's own `errno in (ELOOP, EMLINK)`
        branch produces is what makes this test about the tool's classification rather than about
        a coincidence of English wording in the C library.
        """
        target = self.tmp / "elsewhere.journal"
        target.write_bytes(b"{}\n")
        link = self.tmp / "link.journal"
        link.symlink_to(target)
        proc = self.run_tool(["project", "--journal", str(link)])
        self.assertEqual(proc.returncode, EXIT_REFUSED)
        self.assertEqual(self.document(proc)["reasons"][0], f"wave journal is a symbolic link: {link.name}")
        # POSITIVE CONTROL: the same bytes at a real path are read (and refused on their content),
        # so the refusal above is about the link and not about the target's own content.
        proc = self.run_tool(["project", "--journal", str(target)])
        self.assertEqual(proc.returncode, EXIT_REFUSED)
        self.assertIn("wave-opened", self.document(proc)["reasons"][0])

    def test_every_verb_names_itself_in_its_result(self) -> None:
        self.init()
        for verb, record in (
            ("record-approval", approval_record()),
            ("record-budget", budget_record()),
        ):
            with self.subTest(verb=verb):
                document, code = self.append(verb, record, at=T2)
                self.assertEqual(code, EXIT_OK)
                self.assertEqual(document["command"], verb)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
