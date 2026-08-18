"""Tests for the terminal activation state derivation (ADR-0022 decision 7).

Two kinds of test live here and they check different things.

The unit cases CONSTRUCT artifacts. That is the only way to reach a combination the real tools
cannot produce on demand -- a forged gate receipt, a stale plan, a projection naming the manifest --
and it is the only way the decision matrix can be driven exhaustively. They compute the two
canonical forms the tool re-expresses (the activation family's trailing-newline form and
`gate_receipt.canonical_json`'s newline-free form) the same way the tool does, so a shared
misreading of either form would pass both sides.

The two JOURNEY cases are what close that hole: they drive the four real tools over real fixture
repositories through their real command lines, so every constructed artifact above is cross-checked
against a byte the producers actually wrote. If the re-expressed canonical form were wrong, the
journeys' `plan_digest` binding and `self_digest` re-derivation would both fail.
"""

from __future__ import annotations

import base64
import datetime
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
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "activation-result.py"
CLASSIFIER = ROOT / "skills" / "agentic-sdlc" / "tools" / "repository-classifier.py"
CONTRACT_WRITER = ROOT / "skills" / "agentic-sdlc" / "tools" / "repository-contract-writer.py"
PLANNER = ROOT / "skills" / "agentic-sdlc" / "tools" / "activation-planner.py"
GATE_RECEIPT = ROOT / "scripts" / "gate_receipt.py"
GATE_BASELINE = ROOT / "scripts" / "gate_baseline.py"

RESULT_SCHEMA = "agentic-sdlc/activation-terminal-state@1"
WRITE_READY = "write-ready"
REMEDIATION_READY = "remediation-ready"
REFUSED = "refused"
STATES = (WRITE_READY, REMEDIATION_READY, REFUSED)

WRITE_READY_CONSEQUENCE = "normal waves may write"
REMEDIATION_CONSEQUENCE = (
    "only named hygiene waves may write; this result never claims the repository gate passes"
)

MANIFEST_PATH = ".agentic-sdlc/repo.toml"
GATE_LABEL = "mise run check"

EXIT_OK = 0
EXIT_INPUT = 2


def canonical(value: Any) -> bytes:
    """The activation family's canonical form: sorted, tight, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def receipt_self_digest(body: dict[str, Any]) -> str:
    """`gate_receipt.canonical_digest`, re-expressed: the same form WITHOUT a trailing newline."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def porcelain(*records: bytes) -> tuple[str, str]:
    """A porcelain-v2 -z projection as the plan stores it: base64 plus its sha256."""
    raw = b"".join(item + b"\0" for item in records)
    return base64.b64encode(raw).decode("ascii"), hashlib.sha256(raw).hexdigest()


def untracked_record(path: str) -> bytes:
    return b"? " + path.encode("utf-8")


def modified_record(path: str) -> bytes:
    return b"1 .M N... 100644 100644 100644 " + b"a" * 40 + b" " + b"b" * 40 + b" " + path.encode("utf-8")


def renamed_record(path: str, origin: str) -> bytes:
    head = b"2 R. N... 100644 100644 100644 " + b"a" * 40 + b" " + b"b" * 40 + b" R100 "
    return head + path.encode("utf-8") + b"\0" + origin.encode("utf-8")


def unmerged_record(path: str) -> bytes:
    return (
        b"u UU N... 100644 100644 100644 100644 "
        + b"a" * 40
        + b" "
        + b"b" * 40
        + b" "
        + b"c" * 40
        + b" "
        + path.encode("utf-8")
    )


def classification(
    target: Path,
    *,
    verdict: str | None = "greenfield",
    status: str = "classified",
    reasons: tuple[str, ...] = (),
    ambiguities: tuple[dict[str, str], ...] = (),
    occupied: tuple[dict[str, str], ...] = (),
) -> dict[str, Any]:
    return {
        "schema": "agentic-sdlc/repository-class-result@1",
        "command": "classify",
        "status": status,
        "exit_code": 0,
        "target": str(target),
        "verdict": verdict,
        "occupied": list(occupied),
        "ambiguities": list(ambiguities),
        "reasons": list(reasons),
    }


def contract_write(
    target: Path,
    *,
    status: str = "written",
    path: str = MANIFEST_PATH,
    sha256: str | None = "c" * 64,
    reasons: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "schema": "agentic-sdlc/repository-contract-write-result@1",
        "command": "write",
        "status": status,
        "effect": "manifest-written" if status == "written" else "none",
        "exit_code": 0 if status == "written" else 3,
        "target": str(target),
        "path": path,
        "manifest_sha256": sha256,
        "contract": None,
        "reasons": list(reasons),
    }


def plan_document(target: Path, *, selected_path: str = "AGENTS.md", records: tuple[bytes, ...] = ()) -> dict[str, Any]:
    encoded, digest = porcelain(*records)
    return {
        "schema": "agentic-sdlc/activation-plan@2",
        "target": {"path": str(target), "parent": {}, "root": {}},
        "tool": {},
        "manifest_sha256": "d" * 64,
        "selected_path": selected_path,
        "read_inputs": [],
        "git": {
            "toplevel": str(target),
            "git_dir": str(target / ".git"),
            "git_dir_identity": {},
            "head": "0" * 40,
            "tree": "1" * 40,
            "index": {},
            "porcelain_v2_z_base64": encoded,
            "porcelain_sha256": digest,
            "filtered_internal": [],
        },
        "entries": [],
        "verified_outputs": [],
    }


def activation_result(
    target: Path,
    plan: dict[str, Any] | None,
    *,
    command: str = "apply",
    status: str = "committed",
    effect: str = "committed",
    exit_code: int = 0,
    reasons: tuple[str, ...] = (),
    admitted_effects: tuple[str, ...] = (),
    legal_recovery: tuple[str, ...] = (),
    plan_digest: str | None = "unset",
) -> dict[str, Any]:
    if plan_digest == "unset":
        plan_digest = None if plan is None else hashlib.sha256(canonical(plan)).hexdigest()
    return {
        "schema": "agentic-sdlc/activation-result@3",
        "command": command,
        "status": status,
        "effect": effect,
        "exit_code": exit_code,
        "target": str(target),
        "plan_digest": plan_digest,
        "operation_id": "e" * 32,
        "operation_digest": "f" * 64,
        "receipt_digest": "0" * 64,
        "legal_recovery": list(legal_recovery),
        "reasons": list(reasons),
        "admitted_effects": list(admitted_effects),
        "approval_authenticated": False,
    }


def gate_receipt(
    target: Path,
    *,
    outcome: str = "passed",
    names: tuple[str, ...] = (),
    failures_state: str | None = "identified",
    gate: str = GATE_LABEL,
    argv: list[str] | None | str = "default",
    signal: int | None = None,
    drop_outcome: bool = False,
    resign: bool = True,
) -> dict[str, Any]:
    status = {"passed": 0, "failed": 1, "unobserved": None}[outcome] if outcome in {"passed", "failed", "unobserved"} else 1
    if argv == "default":
        argv = None if outcome == "unobserved" else ["python3", "-c", "pass"]
    body: dict[str, Any] = {
        "gate": gate,
        "argv": argv,
        "status": status,
        "signal": signal,
        "outcome": outcome,
        "log_digest": "a" * 64,
        "toolchain_digest": "b" * 64,
        "cwd": str(target),
    }
    if failures_state is not None:
        body["failures"] = {"harness": "unittest", "names": list(names), "state": failures_state}
    if drop_outcome:
        del body["outcome"]
    receipt = dict(body)
    receipt["self_digest"] = receipt_self_digest(body) if resign else "9" * 64
    return receipt


def baseline_report(
    *,
    gate: str = GATE_LABEL,
    baseline_failing: tuple[str, ...] = ("fixture.Case.test_alpha", "fixture.Case.test_beta"),
    candidate_failing: tuple[str, ...] = ("fixture.Case.test_alpha",),
    candidate_outcome: str = "failed",
    non_worsening: bool | None = None,
    newly_failing: tuple[str, ...] | None = None,
    toolchain_drifted: bool = False,
    omit_non_worsening: bool = False,
    non_worsening_value: Any = "unset",
) -> dict[str, Any]:
    before, after = set(baseline_failing), set(candidate_failing)
    computed = sorted(after - before) if newly_failing is None else list(newly_failing)
    report = {
        "schema_version": "gate-baseline-comparison/v1",
        "gate": gate,
        "baseline_outcome": "failed",
        "candidate_outcome": candidate_outcome,
        "baseline_failing": sorted(before),
        "candidate_failing": sorted(after),
        "newly_failing": computed,
        "fixed": sorted(before - after),
        "still_failing": sorted(before & after),
        "non_worsening": (not computed) if non_worsening is None else non_worsening,
        "toolchain_drifted": toolchain_drifted,
    }
    if non_worsening_value != "unset":
        report["non_worsening"] = non_worsening_value
    if omit_non_worsening:
        del report["non_worsening"]
    return report


POSIX = os.name == "posix"


def _run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Re-expressed from the fixture `tests.test_gate_receipt_producer` uses for the identical rule
    (finding F5a), not imported across test modules. Two shapes, kept separate because they produce
    DIFFERENT wrong exit codes and neither is exotic:

        closed  `2>&-`. CPython then starts with `sys.stderr is None`, so the FIRST
                `sys.stderr.write` raises `AttributeError`.
        epipe   fd 2 is the write end of a pipe whose reader is already closed, so every write
                raises `EPIPE` and leaves bytes pending that CPython flushes again while
                finalizing, which is what replaces the exit code with 120.

    Stderr is deliberately NOT captured: capturing it would give the child a writable stream and
    test nothing.
    """
    if mode == "closed":
        proc = subprocess.run(
            ["sh", "-c", 'exec 2>&-; exec "$@"', "sh", *argv],
            stdout=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
        )
        return proc.returncode, proc.stdout
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stderr mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the reader is gone BEFORE the child starts, so no write can succeed
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd))
    finally:
        os.close(write_fd)
    assert child.stdout is not None
    with child.stdout as stream:
        out = stream.read()
    return child.wait(), out


class DerivationCase(unittest.TestCase):
    """Assembles a complete write-ready evidence set that each test mutates one field of.

    Every negative assertion below therefore carries its positive control in the same test: the
    unmutated set is asserted write-ready first, so a test that stopped exercising its guard would
    have to also stop reaching the ready state.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.target = self.root / "repo"

    def store(self, name: str, value: Any) -> Path:
        path = self.artifacts / f"{name}.json"
        path.write_bytes(canonical(value))
        return path

    def evidence(self, **overrides: Any) -> dict[str, Any]:
        """The full write-ready evidence set as plain documents, before any file is written."""
        plan = overrides.pop("plan", "unset")
        if plan == "unset":
            plan = plan_document(self.target)
        pieces = {
            "classification": classification(self.target),
            "contract": contract_write(self.target),
            "plan": plan,
            "activation": activation_result(self.target, plan),
            "gate-receipt": gate_receipt(self.target),
            "baseline-comparison": None,
        }
        pieces.update(overrides)
        return pieces

    def derive(self, pieces: dict[str, Any] | None = None, *, extra: tuple[str, ...] = ()) -> tuple[dict[str, Any], int]:
        if pieces is None:
            pieces = self.evidence()
        argv = [sys.executable, "-B", str(TOOL), "derive"]
        for name, value in pieces.items():
            if value is None:
                continue
            path = value if isinstance(value, Path) else self.store(name.replace("-", "_"), value)
            argv.extend([f"--{name}", str(path)])
        argv.extend(extra)
        done = subprocess.run(argv, capture_output=True)
        if done.returncode not in {EXIT_OK}:
            return ({"stdout": done.stdout, "stderr": done.stderr.decode("utf-8", "replace")}, done.returncode)
        self.assertEqual(done.stdout, canonical(json.loads(done.stdout)), "result is not canonical bytes")
        result = json.loads(done.stdout)
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        self.assertIn(result["state"], STATES)
        self.assertEqual(result["exit_code"], done.returncode)
        return result, done.returncode

    def assert_refused(self, result: dict[str, Any], fragment: str) -> None:
        self.assertEqual(result["state"], REFUSED, result)
        joined = " || ".join(result["reasons"])
        self.assertIn(fragment, joined, f"no reason named {fragment!r}: {joined}")


class WriteReadyTests(DerivationCase):
    def test_full_greenfield_evidence_derives_write_ready(self) -> None:
        result, code = self.derive()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["state"], WRITE_READY)
        self.assertEqual(result["consequence"], WRITE_READY_CONSEQUENCE)
        self.assertEqual(result["classification"], "greenfield")
        self.assertEqual(result["gate_outcome"], "passed")
        self.assertIs(result["gate_passes"], True)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["target"], str(self.target))

    def test_full_brownfield_evidence_derives_write_ready(self) -> None:
        occupied = ({"kind": "directory", "path": ".github/workflows", "surface": "ci"},)
        pieces = self.evidence(classification=classification(self.target, verdict="brownfield", occupied=occupied))
        result, code = self.derive(pieces)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["state"], WRITE_READY)
        self.assertEqual(result["classification"], "brownfield")

    def test_write_ready_needs_no_baseline_comparison(self) -> None:
        # Positive control for the remediation-only requirement: a passing gate must not be made
        # to depend on a baseline that only a failing gate can have.
        without, code = self.derive()
        self.assertEqual((without["state"], code), (WRITE_READY, EXIT_OK))
        with_report, _ = self.derive(self.evidence(**{"baseline-comparison": baseline_report()}))
        self.assertEqual(with_report["state"], WRITE_READY)

    def test_write_ready_carries_no_recovery_evidence(self) -> None:
        result, _ = self.derive()
        self.assertEqual(result["state"], WRITE_READY)
        self.assertEqual(
            result["recovery"], {"admitted_effects": [], "activation_reasons": [], "recover_verbs": []}
        )


class RemediationReadyTests(DerivationCase):
    def remediation(self, **overrides: Any) -> dict[str, Any]:
        names = ("fixture.Case.test_alpha",)
        pieces = self.evidence(
            **{
                "gate-receipt": gate_receipt(self.target, outcome="failed", names=names),
                "baseline-comparison": baseline_report(candidate_failing=names),
            }
        )
        pieces.update(overrides)
        return pieces

    def test_failed_gate_with_identified_failures_and_baseline_derives_remediation_ready(self) -> None:
        result, code = self.derive(self.remediation())
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["state"], REMEDIATION_READY)
        self.assertEqual(result["consequence"], REMEDIATION_CONSEQUENCE)
        self.assertEqual(result["gate_outcome"], "failed")
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["evidence"]["gate_failing_tests"], ["fixture.Case.test_alpha"])
        self.assertIs(result["evidence"]["baseline_non_worsening"], True)

    def test_remediation_ready_never_claims_the_gate_passes(self) -> None:
        remediation, _ = self.derive(self.remediation())
        self.assertEqual(remediation["state"], REMEDIATION_READY)
        self.assertIs(remediation["gate_passes"], False)
        self.assertIn("never claims the repository gate passes", remediation["consequence"])
        # Positive control: the same field does claim a pass when the gate actually passed.
        passing, _ = self.derive()
        self.assertIs(passing["gate_passes"], True)

    def test_unparsed_failing_set_can_never_reach_remediation_ready(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        # The baseline is made to AGREE with the unparsed receipt -- same (empty) candidate set,
        # same candidate outcome -- so the exactness guard is the only thing left standing between
        # this evidence and remediation-ready.
        unparsed = self.remediation(
            **{
                "gate-receipt": gate_receipt(self.target, outcome="failed", failures_state="unparsed"),
                "baseline-comparison": baseline_report(candidate_failing=()),
            }
        )
        result, code = self.derive(unparsed)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused(result, "failing set is unparsed")

    def test_failed_gate_with_no_failing_set_at_all_refuses(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        pieces = self.remediation(
            **{"gate-receipt": gate_receipt(self.target, outcome="failed", failures_state=None)}
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "records no failing set")

    def test_failed_gate_without_a_baseline_comparison_refuses(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        pieces = self.remediation(**{"baseline-comparison": None})
        result, _ = self.derive(pieces)
        self.assert_refused(result, "no baseline comparison was supplied")

    def test_baseline_for_another_gate_refuses(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        pieces = self.remediation(
            **{"baseline-comparison": baseline_report(gate="just the hooks", candidate_failing=("fixture.Case.test_alpha",))}
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "different gate")

    def test_baseline_whose_candidate_set_disagrees_with_the_receipt_refuses(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        pieces = self.remediation(
            **{"baseline-comparison": baseline_report(candidate_failing=("fixture.Case.test_gamma",))}
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "does not compare this gate receipt")

    def test_baseline_whose_candidate_outcome_disagrees_with_the_receipt_refuses(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        pieces = self.remediation(
            **{
                "baseline-comparison": baseline_report(
                    candidate_failing=("fixture.Case.test_alpha",), candidate_outcome="passed"
                )
            }
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "does not compare this gate receipt")

    def test_worsened_baseline_refuses(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        names = ("fixture.Case.test_alpha", "fixture.Case.test_delta")
        pieces = self.remediation(
            **{
                "gate-receipt": gate_receipt(self.target, outcome="failed", names=names),
                "baseline-comparison": baseline_report(candidate_failing=names),
            }
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "worsens the baseline")

    def test_drifted_baseline_toolchain_refuses(self) -> None:
        names = ("fixture.Case.test_alpha",)
        pieces = self.remediation(
            **{"baseline-comparison": baseline_report(candidate_failing=names, toolchain_drifted=True)}
        )
        result, code = self.derive(pieces)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused(result, "different pinned toolchain")
        self.assertIs(result["evidence"]["baseline_toolchain_drifted"], True)
        # Positive control: the identical comparison, undrifted, still reaches remediation-ready,
        # and carries the same evidence flag as False rather than omitting it.
        undrifted, _ = self.derive(self.remediation())
        self.assertEqual(undrifted["state"], REMEDIATION_READY)
        self.assertIs(undrifted["evidence"]["baseline_toolchain_drifted"], False)

    def test_baseline_missing_non_worsening_refuses_by_name(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        names = ("fixture.Case.test_alpha",)
        pieces = self.remediation(
            **{
                "baseline-comparison": baseline_report(
                    candidate_failing=names, omit_non_worsening=True
                )
            }
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "does not state non_worsening as a boolean")

    def test_baseline_with_non_boolean_non_worsening_refuses_by_name(self) -> None:
        identified, _ = self.derive(self.remediation())
        self.assertEqual(identified["state"], REMEDIATION_READY)
        names = ("fixture.Case.test_alpha",)
        pieces = self.remediation(
            **{
                "baseline-comparison": baseline_report(
                    candidate_failing=names, non_worsening_value="yes"
                )
            }
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "does not state non_worsening as a boolean")


class GateRefusalTests(DerivationCase):
    def test_unobserved_gate_reaches_neither_ready_state(self) -> None:
        passing, _ = self.derive()
        self.assertEqual(passing["state"], WRITE_READY)
        # Twice: bare, and then with a baseline comparison built to agree with the receipt in every
        # field a comparison binds. The second form is the one that matters -- every OTHER predicate
        # is satisfied, so only the unobserved guard keeps this out of remediation-ready.
        for baseline in (None, baseline_report(candidate_failing=(), candidate_outcome="unobserved")):
            with self.subTest(baseline=baseline is not None):
                pieces = self.evidence(
                    **{
                        "gate-receipt": gate_receipt(self.target, outcome="unobserved"),
                        "baseline-comparison": baseline,
                    }
                )
                result, code = self.derive(pieces)
                self.assertEqual(code, EXIT_OK)
                self.assert_refused(result, "produced no verdict")
                self.assertEqual(result["gate_outcome"], "unobserved")
                self.assertIs(result["gate_passes"], False)

    def test_missing_gate_receipt_refuses_by_name(self) -> None:
        passing, _ = self.derive()
        self.assertEqual(passing["state"], WRITE_READY)
        result, _ = self.derive(self.evidence(**{"gate-receipt": None}))
        self.assert_refused(result, "no gate receipt was supplied")
        self.assertIsNone(result["gate_outcome"])
        self.assertIsNone(result["gate_passes"])


class ClassificationRefusalTests(DerivationCase):
    def test_refuse_and_ask_classification_refuses(self) -> None:
        admitted, _ = self.derive()
        self.assertEqual(admitted["state"], WRITE_READY)
        ambiguities = ({"detail": "3 entries: build, src, vendor", "kind": "unclassified-content"},)
        pieces = self.evidence(
            classification=classification(self.target, verdict="refuse-and-ask", ambiguities=ambiguities)
        )
        result, code = self.derive(pieces)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused(result, "refuse-and-ask")
        self.assert_refused(result, "3 entries: build, src, vendor")
        self.assertEqual(result["classification"], "refuse-and-ask")

    def test_classifier_refusal_refuses_and_carries_its_reason(self) -> None:
        admitted, _ = self.derive()
        self.assertEqual(admitted["state"], WRITE_READY)
        pieces = self.evidence(
            classification=classification(
                self.target, status="refused", verdict=None, reasons=("target is not a Git repository: .git is absent",)
            )
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, ".git is absent")
        self.assertIsNone(result["classification"])

    def test_missing_classification_refuses_by_name(self) -> None:
        admitted, _ = self.derive()
        self.assertEqual(admitted["state"], WRITE_READY)
        result, _ = self.derive(self.evidence(classification=None))
        self.assert_refused(result, "no classification result was supplied")

    def test_unknown_verdict_refuses(self) -> None:
        admitted, _ = self.derive()
        self.assertEqual(admitted["state"], WRITE_READY)
        pieces = self.evidence(classification=classification(self.target, verdict="probably-fine"))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "probably-fine")


class ActivationRefusalTests(DerivationCase):
    def test_recovery_required_activation_refuses_with_effects_and_verbs(self) -> None:
        committed, _ = self.derive()
        self.assertEqual(committed["state"], WRITE_READY)
        plan = plan_document(self.target)
        pieces = self.evidence(
            plan=plan,
            activation=activation_result(
                self.target,
                plan,
                command="status",
                status="recovery-required",
                effect="product_partial",
                exit_code=3,
                reasons=("recovery required",),
                admitted_effects=("renamed 0000.payload onto AGENTS.md (flags 1)",),
                legal_recovery=("finish", "rollback"),
                plan_digest=None,
            ),
        )
        result, code = self.derive(pieces)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused(result, "recovery-required")
        self.assertEqual(result["recovery"]["activation_reasons"], ["recovery required"])
        self.assertEqual(
            result["recovery"]["admitted_effects"], ["renamed 0000.payload onto AGENTS.md (flags 1)"]
        )
        self.assertEqual(result["recovery"]["recover_verbs"], ["finish", "rollback"])

    def test_effect_unknown_activation_refuses_with_its_effects(self) -> None:
        committed, _ = self.derive()
        self.assertEqual(committed["state"], WRITE_READY)
        plan = plan_document(self.target)
        pieces = self.evidence(
            plan=plan,
            activation=activation_result(
                self.target,
                plan,
                status="effect-unknown",
                effect="effect_unknown",
                exit_code=4,
                reasons=("multiple committed operations manage one path",),
                admitted_effects=("wrote private metadata progress.json",),
            ),
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "effect-unknown")
        self.assertEqual(result["recovery"]["admitted_effects"], ["wrote private metadata progress.json"])
        self.assertEqual(result["recovery"]["recover_verbs"], ["recover inspect"])

    def test_inactive_activation_refuses(self) -> None:
        committed, _ = self.derive()
        self.assertEqual(committed["state"], WRITE_READY)
        plan = plan_document(self.target)
        pieces = self.evidence(
            plan=plan,
            activation=activation_result(
                self.target, plan, command="status", status="inactive", effect="none", plan_digest=None
            ),
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "inactive")

    def test_committed_activation_with_nonzero_exit_refuses(self) -> None:
        committed, _ = self.derive()
        self.assertEqual(committed["state"], WRITE_READY)
        plan = plan_document(self.target)
        pieces = self.evidence(
            plan=plan, activation=activation_result(self.target, plan, exit_code=3)
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "exit 3")

    def test_activation_without_a_plan_digest_refuses(self) -> None:
        committed, _ = self.derive()
        self.assertEqual(committed["state"], WRITE_READY)
        plan = plan_document(self.target)
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan, plan_digest=None))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "carries no plan_digest")

    def test_plan_digest_mismatch_refuses(self) -> None:
        committed, _ = self.derive()
        self.assertEqual(committed["state"], WRITE_READY)
        plan = plan_document(self.target)
        stale = plan_document(self.target, selected_path="CLAUDE.md")
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, stale))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "does not bind the supplied plan")

    def test_missing_activation_refuses_by_name(self) -> None:
        committed, _ = self.derive()
        self.assertEqual(committed["state"], WRITE_READY)
        result, _ = self.derive(self.evidence(activation=None))
        self.assert_refused(result, "no activation result was supplied")


class ManifestRefusalTests(DerivationCase):
    def test_missing_contract_result_refuses_by_name(self) -> None:
        present, _ = self.derive()
        self.assertEqual(present["state"], WRITE_READY)
        result, _ = self.derive(self.evidence(contract=None))
        self.assert_refused(result, "no repository contract write result was supplied")

    def test_unwritten_manifest_refuses(self) -> None:
        present, _ = self.derive()
        self.assertEqual(present["state"], WRITE_READY)
        pieces = self.evidence(
            contract=contract_write(self.target, status="refused", reasons=("manifest already exists",))
        )
        result, _ = self.derive(pieces)
        self.assert_refused(result, "manifest already exists")

    def test_manifest_at_another_path_refuses(self) -> None:
        present, _ = self.derive()
        self.assertEqual(present["state"], WRITE_READY)
        pieces = self.evidence(contract=contract_write(self.target, path="docs/repo.toml"))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "docs/repo.toml")

    def test_missing_plan_refuses_by_name(self) -> None:
        present, _ = self.derive()
        self.assertEqual(present["state"], WRITE_READY)
        pieces = self.evidence(plan=None)
        pieces["activation"] = activation_result(self.target, plan_document(self.target))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "no activation plan was supplied")

    def test_untracked_manifest_in_the_projection_refuses(self) -> None:
        clean, _ = self.derive()
        self.assertEqual(clean["state"], WRITE_READY)
        plan = plan_document(self.target, records=(untracked_record(MANIFEST_PATH),))
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
        result, code = self.derive(pieces)
        self.assertEqual(code, EXIT_OK)
        self.assert_refused(result, "pending Git record")

    def test_modified_manifest_in_the_projection_refuses(self) -> None:
        clean, _ = self.derive()
        self.assertEqual(clean["state"], WRITE_READY)
        plan = plan_document(self.target, records=(modified_record(MANIFEST_PATH),))
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "pending Git record")

    def test_renamed_manifest_in_the_projection_refuses_on_either_side(self) -> None:
        clean, _ = self.derive()
        self.assertEqual(clean["state"], WRITE_READY)
        for records in (
            (renamed_record(MANIFEST_PATH, "old/repo.toml"),),
            (renamed_record("docs/repo.toml", MANIFEST_PATH),),
        ):
            with self.subTest(records=records):
                plan = plan_document(self.target, records=records)
                pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
                result, _ = self.derive(pieces)
                self.assert_refused(result, "pending Git record")

    def test_unmerged_manifest_in_the_projection_refuses(self) -> None:
        clean, _ = self.derive()
        self.assertEqual(clean["state"], WRITE_READY)
        plan = plan_document(self.target, records=(unmerged_record(MANIFEST_PATH),))
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "pending Git record")

    def test_a_record_for_another_path_does_not_refuse(self) -> None:
        # The negative control for the guard above: the projection is read for the manifest path
        # alone, because the planner already refuses a plan whose tree is dirty elsewhere.
        plan = plan_document(self.target, records=(untracked_record("AGENTS.md"),))
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
        result, _ = self.derive(pieces)
        self.assertEqual(result["state"], WRITE_READY)

    def test_manifest_as_the_activation_selected_path_refuses(self) -> None:
        clean, _ = self.derive()
        self.assertEqual(clean["state"], WRITE_READY)
        plan = plan_document(self.target, selected_path=MANIFEST_PATH)
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "exempts the manifest")


class TargetAgreementTests(DerivationCase):
    def test_each_artifact_naming_another_target_refuses(self) -> None:
        agreeing, _ = self.derive()
        self.assertEqual(agreeing["state"], WRITE_READY)
        other = self.root / "elsewhere"
        cases = {
            "contract": contract_write(other),
            "gate-receipt": gate_receipt(other),
        }
        for name, artifact in cases.items():
            with self.subTest(artifact=name):
                result, _ = self.derive(self.evidence(**{name: artifact}))
                self.assert_refused(result, "names a different target")

    def test_plan_and_activation_naming_another_target_refuses(self) -> None:
        agreeing, _ = self.derive()
        self.assertEqual(agreeing["state"], WRITE_READY)
        other = self.root / "elsewhere"
        plan = plan_document(other)
        pieces = self.evidence(plan=plan, activation=activation_result(other, plan))
        result, _ = self.derive(pieces)
        self.assert_refused(result, "names a different target")


class ExhaustiveMatrixTests(DerivationCase):
    """The matrix has to be total and disjoint, and that is asserted rather than argued."""

    def combinations(self) -> list[tuple[str, dict[str, Any]]]:
        plan = plan_document(self.target)
        dirty = plan_document(self.target, records=(untracked_record(MANIFEST_PATH),))
        cases: list[tuple[str, dict[str, Any]]] = []
        for verdict in ("greenfield", "brownfield", "refuse-and-ask"):
            for outcome, failures_state, names in (
                ("passed", "identified", ()),
                ("failed", "identified", ("fixture.Case.test_alpha",)),
                ("failed", "unparsed", ()),
                ("failed", None, ()),
                ("unobserved", None, ()),
            ):
                for with_baseline in (False, True):
                    for activation_status in ("committed", "inactive"):
                        for plan_document_choice in ("clean", "dirty"):
                            chosen = plan if plan_document_choice == "clean" else dirty
                            label = f"{verdict}/{outcome}/{failures_state}/{with_baseline}/{activation_status}/{plan_document_choice}"
                            pieces = self.evidence(
                                classification=classification(self.target, verdict=verdict),
                                plan=chosen,
                                activation=activation_result(
                                    self.target,
                                    chosen,
                                    status=activation_status,
                                    effect="committed" if activation_status == "committed" else "none",
                                ),
                                **{
                                    "gate-receipt": gate_receipt(
                                        self.target, outcome=outcome, names=names, failures_state=failures_state
                                    ),
                                    "baseline-comparison": baseline_report(candidate_failing=names)
                                    if with_baseline
                                    else None,
                                },
                            )
                            cases.append((label, pieces))
        return cases

    def test_every_combination_yields_exactly_one_terminal_state(self) -> None:
        seen: set[str] = set()
        for label, pieces in self.combinations():
            with self.subTest(case=label):
                result, code = self.derive(pieces)
                self.assertEqual(code, EXIT_OK)
                self.assertIn(result["state"], STATES)
                self.assertEqual([result["state"]], [s for s in STATES if s == result["state"]])
                if result["state"] == REFUSED:
                    self.assertTrue(result["reasons"], "a refusal must name at least one reason")
                else:
                    self.assertEqual(result["reasons"], [], "a ready state must carry no reason")
                seen.add(result["state"])
        self.assertEqual(seen, set(STATES), f"the matrix never reached every state: {seen}")

    def test_only_a_passing_gate_reaches_write_ready(self) -> None:
        for label, pieces in self.combinations():
            with self.subTest(case=label):
                result, _ = self.derive(pieces)
                if result["state"] == WRITE_READY:
                    self.assertEqual(result["gate_outcome"], "passed")
                if result["state"] == REMEDIATION_READY:
                    self.assertEqual(result["gate_outcome"], "failed")

    def test_supplying_nothing_refuses_and_names_every_absence(self) -> None:
        result, code = self.derive(
            {"classification": None, "contract": None, "plan": None, "activation": None, "gate-receipt": None}
        )
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["state"], REFUSED)
        joined = " || ".join(result["reasons"])
        for fragment in (
            "no classification result was supplied",
            "no repository contract write result was supplied",
            "no activation plan was supplied",
            "no activation result was supplied",
            "no gate receipt was supplied",
        ):
            self.assertIn(fragment, joined)


class MalformedArtifactTests(DerivationCase):
    def assert_input_error(self, pieces: dict[str, Any], fragment: str) -> None:
        result, code = self.derive(pieces)
        self.assertEqual(code, EXIT_INPUT, result)
        self.assertIn(fragment, result["stderr"])
        self.assertEqual(result["stdout"], b"", "an input error must emit no result document")

    def test_untouched_evidence_is_not_an_input_error(self) -> None:
        result, code = self.derive()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(result["state"], WRITE_READY)

    def test_absent_artifact_path_is_an_input_error(self) -> None:
        pieces = self.evidence()
        pieces["classification"] = self.artifacts / "does-not-exist.json"
        self.assert_input_error(pieces, "cannot read")

    def test_non_json_artifact_is_an_input_error(self) -> None:
        path = self.artifacts / "garbage.json"
        path.write_bytes(b"not json at all\n")
        pieces = self.evidence()
        pieces["classification"] = path
        self.assert_input_error(pieces, "is not JSON")

    def test_non_object_artifact_is_an_input_error(self) -> None:
        path = self.artifacts / "list.json"
        path.write_bytes(b"[]\n")
        pieces = self.evidence()
        pieces["contract"] = path
        self.assert_input_error(pieces, "is not a JSON object")

    def test_nonfinite_json_constant_is_an_input_error(self) -> None:
        path = self.artifacts / "nan.json"
        path.write_bytes(b'{"schema":"agentic-sdlc/repository-class-result@1","exit_code":NaN}\n')
        pieces = self.evidence()
        pieces["classification"] = path
        self.assert_input_error(pieces, "non-finite")

    def test_wrong_schema_artifact_is_an_input_error(self) -> None:
        pieces = self.evidence()
        wrong = classification(self.target)
        wrong["schema"] = "agentic-sdlc/repository-class-result@99"
        pieces["classification"] = wrong
        self.assert_input_error(pieces, "repository-class-result@1")

    def test_plan_of_the_wrong_schema_is_an_input_error(self) -> None:
        pieces = self.evidence()
        wrong = plan_document(self.target)
        wrong["schema"] = "agentic-sdlc/activation-plan@1"
        pieces["plan"] = wrong
        self.assert_input_error(pieces, "activation-plan@2")

    def test_activation_result_of_the_wrong_schema_is_an_input_error(self) -> None:
        plan = plan_document(self.target)
        wrong = activation_result(self.target, plan)
        wrong["schema"] = "agentic-sdlc/activation-result@2"
        self.assert_input_error(self.evidence(plan=plan, activation=wrong), "activation-result@3")

    def test_baseline_report_of_the_wrong_schema_is_an_input_error(self) -> None:
        wrong = baseline_report()
        wrong["schema_version"] = "gate-baseline-comparison/v2"
        self.assert_input_error(self.evidence(**{"baseline-comparison": wrong}), "gate-baseline-comparison/v1")

    def test_unverifiable_gate_receipt_is_an_input_error(self) -> None:
        pieces = self.evidence(**{"gate-receipt": gate_receipt(self.target, resign=False)})
        self.assert_input_error(pieces, "self_digest")

    def test_pretaxonomy_gate_receipt_is_an_input_error(self) -> None:
        pieces = self.evidence(**{"gate-receipt": gate_receipt(self.target, drop_outcome=True)})
        self.assert_input_error(pieces, "outcome")

    def test_forged_outcome_that_status_cannot_derive_is_an_input_error(self) -> None:
        forged = gate_receipt(self.target)
        body = {key: value for key, value in forged.items() if key != "self_digest"}
        body["outcome"] = "probably-passed"
        body["self_digest"] = receipt_self_digest({k: v for k, v in body.items() if k != "self_digest"})
        self.assert_input_error(self.evidence(**{"gate-receipt": body}), "does not derive")

    def test_receipt_claiming_a_verdict_with_no_argv_is_an_input_error(self) -> None:
        body = gate_receipt(self.target, argv=None)
        rest = {key: value for key, value in body.items() if key != "self_digest"}
        body["self_digest"] = receipt_self_digest(rest)
        self.assert_input_error(self.evidence(**{"gate-receipt": body}), "nothing was executed")

    def test_tampered_porcelain_digest_is_an_input_error(self) -> None:
        plan = plan_document(self.target, records=(untracked_record(MANIFEST_PATH),))
        plan["git"]["porcelain_sha256"] = "0" * 64
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
        self.assert_input_error(pieces, "porcelain")

    def test_malformed_porcelain_record_is_an_input_error(self) -> None:
        raw = b"1 too few fields\0"
        plan = plan_document(self.target)
        plan["git"]["porcelain_v2_z_base64"] = base64.b64encode(raw).decode("ascii")
        plan["git"]["porcelain_sha256"] = hashlib.sha256(raw).hexdigest()
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
        self.assert_input_error(pieces, "porcelain")

    def test_undecodable_porcelain_encoding_is_an_input_error(self) -> None:
        plan = plan_document(self.target)
        plan["git"]["porcelain_v2_z_base64"] = "not base64!!"
        pieces = self.evidence(plan=plan, activation=activation_result(self.target, plan))
        self.assert_input_error(pieces, "porcelain")


@unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO artifacts are POSIX-only")
class FifoArtifactTests(DerivationCase):
    """A FIFO artifact path must refuse promptly, not hang forever on open (finding F4)."""

    def _argv_for(self, pieces: dict[str, Any]) -> list[str]:
        argv = [sys.executable, "-B", str(TOOL), "derive"]
        for name, value in pieces.items():
            if value is None:
                continue
            path = value if isinstance(value, Path) else self.store(name.replace("-", "_"), value)
            argv.extend([f"--{name}", str(path)])
        return argv

    def test_fifo_artifact_path_exits_2_promptly_instead_of_hanging(self) -> None:
        fifo_path = self.artifacts / "classification.fifo"
        os.mkfifo(fifo_path)
        pieces = self.evidence()
        pieces["classification"] = fifo_path
        argv = self._argv_for(pieces)
        # Bound with a timeout so a regression that reintroduces the hang fails THIS test rather
        # than blocking the whole suite (or this whole process) forever.
        try:
            done = subprocess.run(argv, capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            self.fail("the tool hung opening a FIFO artifact instead of refusing it by name")
        self.assertEqual(done.returncode, EXIT_INPUT, done.stderr)
        self.assertIn(b"not a regular file", done.stderr)
        self.assertEqual(done.stdout, b"")

    def test_a_regular_file_at_the_same_path_shape_derives_normally(self) -> None:
        # Positive control: swapping the FIFO for an ordinary file at the same artifact slot still
        # reaches the ordinary write-ready result, so the guard above is about the file TYPE and
        # not some unrelated break in the evidence set.
        pieces = self.evidence()
        pieces["classification"] = self.store("classification", classification(self.target))
        argv = self._argv_for(pieces)
        done = subprocess.run(argv, capture_output=True, timeout=10)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        self.assertEqual(json.loads(done.stdout)["state"], WRITE_READY)


class ResultContractTests(DerivationCase):
    def test_result_is_canonical_and_escapes_non_ascii(self) -> None:
        reason = "cannot inspect .git: café"
        pieces = self.evidence(
            classification=classification(self.target, status="refused", verdict=None, reasons=(reason,))
        )
        argv = [sys.executable, "-B", str(TOOL), "derive"]
        for name, value in pieces.items():
            if value is None:
                continue
            argv.extend([f"--{name}", str(self.store(name.replace('-', '_'), value))])
        done = subprocess.run(argv, capture_output=True)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr)
        self.assertNotIn("café".encode("utf-8"), done.stdout, "non-ASCII bytes must be escaped")
        self.assertIn(b"caf\\u00e9", done.stdout)
        self.assertTrue(done.stdout.endswith(b"\n"))
        self.assertEqual(done.stdout.count(b"\n"), 1)
        parsed = json.loads(done.stdout)
        self.assertEqual(done.stdout, canonical(parsed))
        self.assertIn(reason, " || ".join(parsed["reasons"]))

    def test_result_key_set_is_fixed_across_states(self) -> None:
        names = ("fixture.Case.test_alpha",)
        ready, _ = self.derive()
        remediation, _ = self.derive(
            self.evidence(
                **{
                    "gate-receipt": gate_receipt(self.target, outcome="failed", names=names),
                    "baseline-comparison": baseline_report(candidate_failing=names),
                }
            )
        )
        refused, _ = self.derive(self.evidence(classification=None))
        self.assertEqual(ready["state"], WRITE_READY)
        self.assertEqual(remediation["state"], REMEDIATION_READY)
        self.assertEqual(refused["state"], REFUSED)
        self.assertEqual(set(ready), set(remediation))
        self.assertEqual(set(ready), set(refused))
        for result in (ready, remediation, refused):
            self.assertEqual(set(result["recovery"]), {"admitted_effects", "activation_reasons", "recover_verbs"})
            self.assertEqual(
                set(result["evidence"]),
                {
                    "activation_command",
                    "activation_operation_id",
                    "activation_receipt_digest",
                    "activation_status",
                    "baseline_non_worsening",
                    "baseline_toolchain_drifted",
                    "gate",
                    "gate_failing_tests",
                    "manifest_path",
                    "manifest_sha256",
                    "plan_digest",
                    "plan_selected_path",
                },
            )

    def test_refused_consequence_points_at_the_recovery_evidence(self) -> None:
        result, _ = self.derive(self.evidence(classification=None))
        self.assertEqual(result["state"], REFUSED)
        self.assertIn("no wave may write", result["consequence"])

    def test_help_is_read_only_and_exits_zero(self) -> None:
        done = subprocess.run([sys.executable, "-B", str(TOOL), "derive", "--help"], capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(b"--gate-receipt", done.stdout)

    def test_derivation_writes_nothing_anywhere_under_the_case_tree(self) -> None:
        def snapshot() -> dict[str, tuple[int, str]]:
            found: dict[str, tuple[int, str]] = {}
            for path in sorted(self.root.rglob("*")):
                if path.is_file():
                    data = path.read_bytes()
                    found[str(path.relative_to(self.root))] = (len(data), hashlib.sha256(data).hexdigest())
            return found

        result, _ = self.derive()
        self.assertEqual(result["state"], WRITE_READY)
        before = snapshot()
        self.assertTrue(before, "the snapshot must see the artifacts it is guarding")
        again, _ = self.derive()
        self.assertEqual(again, result, "the derivation is not deterministic")
        self.assertEqual(snapshot(), before, "the derivation touched the filesystem")

    def test_module_is_offline_and_subprocess_free(self) -> None:
        forbidden = ("subprocess", "socket", "urllib", "http.client", "ctypes")

        def imported(path: Path) -> set[str]:
            source = path.read_text(encoding="utf-8")
            return {name for name in forbidden if f"import {name}" in source}

        self.assertEqual(imported(TOOL), set(), "the derivation must admit no effect and no network")
        # Positive control: the same check finds the producer that really does run subprocesses,
        # so an empty answer above is evidence rather than a broken predicate.
        self.assertIn("subprocess", imported(GATE_RECEIPT))

    def test_module_docstring_states_the_exit_space_and_why_exit_four_cannot_apply(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        docstring = source.split('"""')[1]
        self.assertIn("4", docstring)
        for fragment in ("exit", "effect"):
            self.assertIn(fragment, docstring.lower())
        self.assertIn("Decision 9", docstring)

    def test_module_docstring_states_the_plan_apply_pair_is_not_proven_current(self) -> None:
        # Finding F3: the plan_digest binding proves the apply consumed exactly the supplied plan,
        # never that the pair is CURRENT -- a stale matched plan+apply pair from an earlier, cleaner
        # tree, paired with a fresh passing receipt, derives write-ready by construction.
        docstring = TOOL.read_text(encoding="utf-8").split('"""')[1]
        squeezed = " ".join(docstring.split())
        self.assertIn("NOT that the pair is current", squeezed)
        self.assertIn("freshness is underivable from these artifacts", squeezed)


@unittest.skipUnless(POSIX, "fd-level stderr hostility is POSIX-only")
class HostileStderrTests(DerivationCase):
    """A stderr this process cannot write to must cost the display line, never the exit code
    (finding F5a). Both hostile shapes used to demote a correctly classified exit 2: `2>&-` to an
    uncaught `AttributeError` (bare exit 1), and a broken pipe to exit 120 once CPython's shutdown
    flush replayed the failed write.
    """

    def _argv_for(self, pieces: dict[str, Any]) -> list[str]:
        argv = [sys.executable, "-B", str(TOOL), "derive"]
        for name, value in pieces.items():
            if value is None:
                continue
            path = value if isinstance(value, Path) else self.store(name.replace("-", "_"), value)
            argv.extend([f"--{name}", str(path)])
        return argv

    def test_the_hostile_stderr_fixture_is_actually_hostile(self) -> None:
        """The control for every assertion below: the child really has no usable stderr."""
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
        code, out = _run_with_hostile_stderr([sys.executable, "-B", "-c", canary], mode="closed", cwd=self.root)
        self.assertEqual(f"{code}:{out.decode('utf-8', 'replace').strip()}", "0:none")
        code, out = _run_with_hostile_stderr([sys.executable, "-B", "-c", canary], mode="epipe", cwd=self.root)
        self.assertEqual(f"{code}:{out.decode('utf-8', 'replace').strip()}", "120:BrokenPipeError")

    def test_a_hostile_stderr_cannot_reclassify_a_well_classified_input_error(self) -> None:
        pieces = self.evidence()
        pieces["classification"] = self.artifacts / "does-not-exist.json"
        argv = self._argv_for(pieces)
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, out = _run_with_hostile_stderr(argv, mode=mode, cwd=self.root)
                self.assertEqual(code, EXIT_INPUT)
                self.assertNotIn(code, (1, 120))  # 120 and 1-for-2 are both wrong answers here
                self.assertEqual(out, b"", "an input error must emit no result document")
        # POSITIVE CONTROL: the identical argv over a WORKING stderr still exits 2 and carries the
        # diagnostic line the hostile runs necessarily lost -- so those runs lost the display
        # channel and nothing else.
        done = subprocess.run(argv, capture_output=True)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stderr)
        self.assertIn(b"cannot read", done.stderr)

    def test_a_hostile_stderr_cannot_cost_a_ready_derivation_its_exit_code(self) -> None:
        argv = self._argv_for(self.evidence())
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, out = _run_with_hostile_stderr(argv, mode=mode, cwd=self.root)
                self.assertEqual(code, EXIT_OK)
                self.assertNotIn(code, (1, 120))
                self.assertEqual(json.loads(out)["state"], WRITE_READY)


def git(target: Path, *args: str) -> None:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "LC_ALL": "C",
            "LANG": "C",
        }
    )
    subprocess.run(["git", "-C", str(target), *args], check=True, capture_output=True, env=environment)


CONTRACT_FIELDS = (
    ("schema", "agentic-sdlc/repository-contract@1"),
    ("canonical-guidance", "AGENTS.md"),
    ("queue-adapter", "seeds"),
    ("adr-location", "docs/adr"),
    ("glossary-location", "docs/glossary.md"),
    ("authoritative-gate", GATE_LABEL),
    ("worktree-policy", "one worktree per seed"),
    ("integration-policy", "conductor fan-in"),
    ("ci-expectation", "gate parity"),
    ("writing-profile", "normal waves"),
)

PASSING_GATE = "print('OK')"
BASELINE_GATE = (
    "print('FAIL: test_alpha (fixture.Case.test_alpha)');"
    "print('FAIL: test_beta (fixture.Case.test_beta)');"
    "print('FAILED (failures=2)');"
    "raise SystemExit(1)"
)
CANDIDATE_GATE = (
    "print('FAIL: test_alpha (fixture.Case.test_alpha)');"
    "print('FAILED (failures=1)');"
    "raise SystemExit(1)"
)


@unittest.skipUnless(shutil.which("git"), "git is required to build the journey fixtures")
class JourneyTests(unittest.TestCase):
    """Slice 4's exit criterion: one full greenfield and one full brownfield chain, real tools only.

    Each journey drives the four operands through their real command lines, so the derivation is
    asserted against bytes the producers wrote rather than bytes this test invented.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.target = self.root / "repo"
        self.target.mkdir()
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.lock = self.artifacts / "mise.lock"
        self.lock.write_bytes(b"synthetic pinned toolchain\n")
        # The activation plane is a write destination: never inherit the operator's own.
        self.environment = dict(os.environ, XDG_STATE_HOME=str(self.root / "state"))
        self.environment.pop("AGENTIC_SDLC_ACTIVATION_PLANE", None)
        git(self.target, "init", "-b", "main")
        git(self.target, "config", "user.name", "test")
        git(self.target, "config", "user.email", "test@example.invalid")

    def run_tool(self, *argv: str, expect: int | None = None) -> subprocess.CompletedProcess[bytes]:
        done = subprocess.run([sys.executable, "-B", *argv], capture_output=True, env=self.environment)
        if expect is not None:
            self.assertEqual(done.returncode, expect, done.stderr.decode("utf-8", "replace"))
        return done

    def store(self, name: str, payload: bytes) -> Path:
        path = self.artifacts / name
        path.write_bytes(payload)
        return path

    def classify(self) -> dict[str, Any]:
        done = self.run_tool(str(CLASSIFIER), "classify", "--target", str(self.target), expect=0)
        self.store("classification.json", done.stdout)
        return json.loads(done.stdout)

    def write_contract(self) -> dict[str, Any]:
        argv = [str(CONTRACT_WRITER), "write", "--target", str(self.target)]
        for name, value in CONTRACT_FIELDS:
            argv.extend([f"--{name}", value])
        done = self.run_tool(*argv, expect=0)
        self.store("contract.json", done.stdout)
        return json.loads(done.stdout)

    def activate(self) -> tuple[dict[str, Any], dict[str, Any]]:
        manifest = self.store(
            "instruction-manifest.json",
            canonical(
                {
                    "schema": "agentic-sdlc/instruction-manifest@2",
                    "marker": {"start": "<!-- agentic-sdlc:start -->", "end": "<!-- agentic-sdlc:end -->"},
                    "doctrine_pointer": "literal only",
                    "outputs": [
                        {
                            "path": "AGENTS.md",
                            "kind": "root_agents",
                            "prefix": "",
                            "sections": [{"key": "intent", "body": "exact"}],
                        }
                    ],
                }
            ),
        )
        planned = self.run_tool(
            str(PLANNER), "plan", "--target", str(self.target), "--manifest", str(manifest), "--entry", "AGENTS.md",
            expect=0,
        )
        plan = json.loads(planned.stdout)["plan"]
        plan_path = self.store("plan.json", canonical(plan))
        # The grant is the operator's own document, built here with the same canonical form the
        # engine uses. A mismatch would surface as a refused `plan_digest`, not a silent pass.
        instant = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
        stamp = "%Y-%m-%dT%H:%M:%SZ"
        info = self.target.stat()
        grant = self.store(
            "grant.json",
            canonical(
                {
                    "schema": "agentic-sdlc/procedural-grant@1",
                    "grant_id": "1" * 32,
                    "operation": "apply",
                    "target": {"path": str(self.target), "root_dev": info.st_dev, "root_ino": info.st_ino},
                    "plan_digest": hashlib.sha256(canonical(plan)).hexdigest(),
                    "operation_id": None,
                    "operation_digest": None,
                    "decision": None,
                    "issued_at": instant.strftime(stamp),
                    "expires_at": (instant + datetime.timedelta(minutes=5)).strftime(stamp),
                }
            ),
        )
        applied = self.run_tool(
            str(PLANNER), "apply", "--plan", str(plan_path), "--manifest", str(manifest), "--grant", str(grant),
            expect=0,
        )
        self.store("activation.json", applied.stdout)
        return plan, json.loads(applied.stdout)

    def record_gate(self, name: str, script: str, *, expect: int) -> Path:
        out = self.artifacts / name
        self.run_tool(
            str(GATE_RECEIPT), "record", "--gate", GATE_LABEL, "--out", str(out), "--lock", str(self.lock),
            "--cwd", str(self.target), "--harness", "unittest", "--quiet", "--", sys.executable, "-c", script,
            expect=expect,
        )
        return out

    def derive(self, *, baseline: Path | None = None) -> dict[str, Any]:
        argv = [
            str(TOOL), "derive",
            "--classification", str(self.artifacts / "classification.json"),
            "--contract", str(self.artifacts / "contract.json"),
            "--plan", str(self.artifacts / "plan.json"),
            "--activation", str(self.artifacts / "activation.json"),
            "--gate-receipt", str(self.artifacts / "gate.json"),
        ]
        if baseline is not None:
            argv.extend(["--baseline-comparison", str(baseline)])
        done = self.run_tool(*argv, expect=0)
        self.assertEqual(done.stdout, canonical(json.loads(done.stdout)))
        return json.loads(done.stdout)

    def track_manifest(self) -> None:
        # Tracked on purpose (ADR-0022 decision 2), and the planner refuses a plan whose worktree
        # is dirty outside the selected path, so this commit is part of the journey, not setup.
        git(self.target, "add", MANIFEST_PATH)
        git(self.target, "commit", "-m", "track the repository contract manifest")

    def test_greenfield_journey_reaches_write_ready(self) -> None:
        git(self.target, "commit", "--allow-empty", "-m", "initial")
        classified = self.classify()
        self.assertEqual(classified["verdict"], "greenfield", classified)
        contract = self.write_contract()
        self.assertEqual(contract["status"], "written")
        self.assertEqual(contract["path"], MANIFEST_PATH)
        self.track_manifest()
        plan, applied = self.activate()
        self.assertEqual(applied["status"], "committed", applied)
        self.assertEqual(applied["plan_digest"], hashlib.sha256(canonical(plan)).hexdigest())
        self.assertTrue((self.target / "AGENTS.md").is_file())
        receipt = json.loads(self.record_gate("gate.json", PASSING_GATE, expect=0).read_bytes())
        self.assertEqual(receipt["outcome"], "passed")
        result = self.derive()
        self.assertEqual(result["state"], WRITE_READY, result)
        self.assertEqual(result["classification"], "greenfield")
        self.assertEqual(result["consequence"], WRITE_READY_CONSEQUENCE)
        self.assertEqual(result["gate_outcome"], "passed")
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["target"], str(self.target))
        self.assertEqual(result["evidence"]["manifest_sha256"], contract["manifest_sha256"])
        self.assertEqual(result["evidence"]["activation_receipt_digest"], applied["receipt_digest"])

    def test_brownfield_journey_reaches_remediation_ready(self) -> None:
        workflows = self.target / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: ci\non: push\njobs: {}\n", encoding="utf-8")
        git(self.target, "add", ".github")
        git(self.target, "commit", "-m", "existing CI")
        classified = self.classify()
        self.assertEqual(classified["verdict"], "brownfield", classified)
        self.assertIn(
            {"kind": "directory", "path": ".github/workflows", "surface": "ci"}, classified["occupied"]
        )
        self.write_contract()
        self.track_manifest()
        plan, applied = self.activate()
        self.assertEqual(applied["status"], "committed", applied)
        baseline_path = self.record_gate("gate-baseline.json", BASELINE_GATE, expect=5)
        candidate_path = self.record_gate("gate.json", CANDIDATE_GATE, expect=5)
        candidate = json.loads(candidate_path.read_bytes())
        self.assertEqual(candidate["outcome"], "failed")
        self.assertEqual(candidate["failures"]["state"], "identified")
        compared = self.run_tool(
            str(GATE_BASELINE), "compare", "--baseline", str(baseline_path), "--candidate", str(candidate_path),
            "--quiet", expect=0,
        )
        report_path = self.store("baseline.json", compared.stdout)
        report = json.loads(compared.stdout)
        self.assertIs(report["non_worsening"], True)
        self.assertEqual(report["fixed"], ["fixture.Case.test_beta"])
        result = self.derive(baseline=report_path)
        self.assertEqual(result["state"], REMEDIATION_READY, result)
        self.assertEqual(result["classification"], "brownfield")
        self.assertEqual(result["consequence"], REMEDIATION_CONSEQUENCE)
        self.assertEqual(result["gate_outcome"], "failed")
        self.assertIs(result["gate_passes"], False)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["evidence"]["gate_failing_tests"], ["fixture.Case.test_alpha"])
        self.assertIs(result["evidence"]["baseline_non_worsening"], True)
        # The same chain WITHOUT the baseline is the positive control for the baseline requirement.
        without = self.derive()
        self.assertEqual(without["state"], REFUSED)
        self.assertIn("no baseline comparison was supplied", " || ".join(without["reasons"]))


if __name__ == "__main__":
    unittest.main()
