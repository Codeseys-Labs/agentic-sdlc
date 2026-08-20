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

Every subprocess spawn in this module -- for the tool under test AND for every sibling fixture
producer -- goes through ONE constructed environment: an ALLOWLIST, not the ambient shell, mirroring
`test_mission_contract.py`'s `constructed_environment` (itself the same pattern
`test_wave_journal.py` establishes: never hand a spawned tool the developer's own shell).
"""

from __future__ import annotations

import ast
import json
import math
import os
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
MISE_LOCK = ROOT / "mise.lock"

RESULT_SCHEMA = "agentic-sdlc/observability-projection@1"
EVIDENCE_NOTICE = "this view is evidence, not authorization"

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


class BlufPriorityTests(ProjectionCase):
    """activation_result > gate > runtime_assignment > wave_journal, and each unreadable input also
    outranks the kinds below it -- checked by construction, one pair at a time."""

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
