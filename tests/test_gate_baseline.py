"""Tests for the baseline comparison: is the candidate's failing set a SUBSET of the baseline's?

"Baselined" means a stored gate receipt carrying the SET of named failing tests, and "exact
non-worsening" means the new run's failing set is a subset of the baseline's (operator decision,
2026-08-17). The headline test here is the SWAP: one failure fixed, a different one broken. A
status-only or count-based comparison reads that as non-worsening, which is exactly what the word
"exact" in Implementation Decision 17 exists to prevent, so it is asserted first and by name.

Nothing here authorizes anything. A non-worsening verdict is evidence about two receipts; push,
release, merge, and deployment remain blocked until the repository is write-ready.
"""

from __future__ import annotations

import contextlib
import errno
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import gate_baseline, gate_receipt


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "gate_baseline.py"
LOCK_BYTES = b'[tools.fake]\nversion = "1.2.3"\n'
DRIFTED_LOCK_BYTES = b'[tools.fake]\nversion = "1.2.4"\n'
GATE = "mise run check"
POSIX = os.name == "posix"
#: The comparison's whole exit space. Anything else — 120 above all — is a broken contract.
DECLARED_EXITS = frozenset(
    {
        gate_baseline.EXIT_OK,
        gate_baseline.EXIT_INTERNAL,
        gate_baseline.EXIT_USAGE,
        gate_baseline.EXIT_REFUSED,
        gate_baseline.EXIT_PARTIAL,
        gate_baseline.EXIT_WORSENED,
    }
)


def _make_receipt(
    names: tuple[str, ...],
    *,
    status: int | None = None,
    gate: str = GATE,
    lock_bytes: bytes = LOCK_BYTES,
    state: str = gate_receipt.FAILURES_IDENTIFIED,
    with_failures: bool = True,
    argv: list[str] | None = None,
    cwd: str = "/tmp/fixture",
) -> dict[str, object]:
    """A verifiable receipt whose failing set is exactly `names`."""
    if status is None:
        status = 1 if names else 0
    failures = (
        {"harness": gate_receipt.HARNESS_UNITTEST, "state": state, "names": list(names)}
        if with_failures
        else None
    )
    return gate_receipt.build_receipt(
        gate=gate,
        argv=["mise", "run", "check"] if argv is None else argv,
        status=status,
        log_bytes=b"",
        lock_bytes=lock_bytes,
        cwd=cwd,
        failures=failures,
    )


class _BaselineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _write(self, name: str, receipt: object) -> Path:
        path = self.tmp / name
        path.write_bytes(gate_receipt.canonical_json(receipt) + b"\n")
        return path

    def _compare(self, baseline: object, candidate: object) -> subprocess.CompletedProcess[str]:
        return self._run(
            [
                "compare",
                "--baseline",
                str(self._write("baseline.json", baseline)),
                "--candidate",
                str(self._write("candidate.json", candidate)),
            ]
        )

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=str(self.tmp),
            check=False,
        )

    def _report(self, proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertTrue(proc.stdout, f"no report on stdout; stderr was: {proc.stderr}")
        return json.loads(proc.stdout)


class SubsetComparisonTests(_BaselineTestCase):
    """The whole reason a subset was chosen over a count or a status."""

    def test_a_swapped_failure_is_worsened_and_the_new_failure_is_named(self) -> None:
        baseline = _make_receipt(("m.A.test_one", "m.A.test_two"))
        candidate = _make_receipt(("m.A.test_one", "m.B.test_three"))
        proc = self._compare(baseline, candidate)
        report = self._report(proc)
        # The caller's question is "what got worse", so the answer is a NAME, not a boolean.
        self.assertEqual(report["newly_failing"], ["m.B.test_three"])
        self.assertEqual(report["fixed"], ["m.A.test_two"])
        self.assertEqual(report["still_failing"], ["m.A.test_one"])
        self.assertFalse(report["non_worsening"])
        self.assertEqual(proc.returncode, gate_baseline.EXIT_WORSENED, proc.stderr)
        self.assertIn("m.B.test_three", proc.stderr)  # named on the human channel too
        # The count is IDENTICAL on both sides, so a count-based comparison would have called this
        # non-worsening. That is the defect this definition exists to prevent.
        self.assertEqual(len(report["baseline_failing"]), len(report["candidate_failing"]))
        # POSITIVE CONTROL: dropping the new failure from the same candidate is non-worsening, so
        # the verdict above is about the swap and not about the fixture or the comparison refusing
        # everything.
        subset = self._compare(baseline, _make_receipt(("m.A.test_one",)))
        subset_report = self._report(subset)
        self.assertEqual(subset_report["newly_failing"], [])
        self.assertTrue(subset_report["non_worsening"])
        self.assertEqual(subset.returncode, gate_baseline.EXIT_OK, subset.stderr)

    def test_an_identical_failing_set_is_non_worsening_with_no_progress(self) -> None:
        names = ("m.A.test_one", "m.A.test_two")
        proc = self._compare(_make_receipt(names), _make_receipt(names))
        report = self._report(proc)
        self.assertEqual(proc.returncode, gate_baseline.EXIT_OK, proc.stderr)
        self.assertTrue(report["non_worsening"])
        self.assertEqual(report["fixed"], [])
        self.assertEqual(report["still_failing"], list(names))

    def test_a_green_candidate_reports_every_baseline_failure_as_fixed(self) -> None:
        proc = self._compare(_make_receipt(("m.A.test_one", "m.A.test_two")), _make_receipt(()))
        report = self._report(proc)
        self.assertEqual(proc.returncode, gate_baseline.EXIT_OK, proc.stderr)
        self.assertEqual(report["fixed"], ["m.A.test_one", "m.A.test_two"])
        self.assertEqual(report["newly_failing"], [])
        self.assertEqual(report["still_failing"], [])
        self.assertEqual(report["candidate_outcome"], "passed")

    def test_an_added_failure_alongside_the_old_ones_is_worsened(self) -> None:
        proc = self._compare(
            _make_receipt(("m.A.test_one",)), _make_receipt(("m.A.test_one", "m.A.test_two"))
        )
        self.assertEqual(proc.returncode, gate_baseline.EXIT_WORSENED, proc.stderr)
        self.assertEqual(self._report(proc)["newly_failing"], ["m.A.test_two"])

    def test_a_shorter_candidate_can_still_be_worsened(self) -> None:
        """Three failures become two — a count says improved, the set says a new break."""
        baseline = _make_receipt(("m.A.test_one", "m.A.test_two", "m.A.test_three"))
        candidate = _make_receipt(("m.A.test_one", "m.Z.test_new"))
        proc = self._compare(baseline, candidate)
        report = self._report(proc)
        self.assertLess(len(report["candidate_failing"]), len(report["baseline_failing"]))
        self.assertEqual(report["newly_failing"], ["m.Z.test_new"])
        self.assertFalse(report["non_worsening"])
        self.assertEqual(proc.returncode, gate_baseline.EXIT_WORSENED, proc.stderr)

    def test_the_python_api_returns_the_named_sets(self) -> None:
        report = gate_baseline.compare(
            _make_receipt(("m.A.test_one", "m.A.test_two")),
            _make_receipt(("m.A.test_two", "m.C.test_new")),
        )
        self.assertEqual(report["newly_failing"], ["m.C.test_new"])
        self.assertEqual(report["fixed"], ["m.A.test_one"])
        self.assertEqual(report["still_failing"], ["m.A.test_two"])
        self.assertIs(report["non_worsening"], False)
        self.assertEqual(report["gate"], GATE)


class UnanswerableComparisonTests(_BaselineTestCase):
    """Every way a subset comparison could be vacuously true is a refusal, not a green verdict."""

    def test_a_receipt_without_failure_identities_is_refused(self) -> None:
        plain = _make_receipt(("m.A.test_one",), with_failures=False)
        for label, pair in (
            ("baseline", (plain, _make_receipt(("m.A.test_one",)))),
            ("candidate", (_make_receipt(("m.A.test_one",)), plain)),
        ):
            with self.subTest(side=label):
                proc = self._compare(*pair)
                self.assertEqual(proc.returncode, gate_baseline.EXIT_REFUSED, proc.stderr)
                self.assertIn("records no failing set", proc.stderr)
                self.assertEqual(proc.stdout, "")  # no report: the question was not answered
        # POSITIVE CONTROL: both sides carrying the field compare cleanly, so the refusals above
        # are about the missing field and not about the comparison rejecting everything.
        ok = self._compare(_make_receipt(("m.A.test_one",)), _make_receipt(("m.A.test_one",)))
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)

    def test_an_unparsed_failing_set_is_refused_rather_than_read_as_empty(self) -> None:
        """The anti-vacuity control: `unparsed` must never behave like "no failures"."""
        unparsed = _make_receipt((), status=1, state=gate_receipt.FAILURES_UNPARSED)
        self.assertTrue(gate_receipt.verify_receipt(unparsed))  # it is a valid receipt...
        for label, pair in (
            ("baseline", (unparsed, _make_receipt(("m.A.test_one",)))),
            ("candidate", (_make_receipt(("m.A.test_one",)), unparsed)),
        ):
            with self.subTest(side=label):
                proc = self._compare(*pair)
                self.assertEqual(proc.returncode, gate_baseline.EXIT_REFUSED, proc.stderr)
                self.assertIn("unparsed", proc.stderr)
                self.assertEqual(proc.stdout, "")
        # And the vacuous reading is not merely absent, it is unreachable: an `unparsed` candidate
        # against ANY baseline would be a subset if it were read as an empty set.
        self.assertNotEqual(
            self._compare(_make_receipt(("m.A.test_one",)), unparsed).returncode,
            gate_baseline.EXIT_OK,
        )

    def test_a_gate_that_produced_no_verdict_can_neither_baseline_nor_be_compared(self) -> None:
        unobserved = gate_receipt.build_receipt(
            gate=GATE,
            argv=None,
            status=None,
            log_bytes=b"",
            lock_bytes=LOCK_BYTES,
            cwd="/tmp/fixture",
            failures={
                "harness": gate_receipt.HARNESS_UNITTEST,
                "state": gate_receipt.FAILURES_UNPARSED,
                "names": [],
            },
        )
        self.assertEqual(unobserved["outcome"], "unobserved")
        proc = self._compare(unobserved, _make_receipt(("m.A.test_one",)))
        self.assertEqual(proc.returncode, gate_baseline.EXIT_REFUSED, proc.stderr)
        self.assertIn("no verdict", proc.stderr)

    def test_a_red_gate_that_names_no_failure_is_refused(self) -> None:
        """A red gate with an empty failing set makes every later comparison vacuously clean."""
        incoherent = _make_receipt((), status=1)
        self.assertTrue(gate_receipt.verify_receipt(incoherent))
        for label, pair in (
            ("baseline", (incoherent, _make_receipt(("m.A.test_one",)))),
            ("candidate", (_make_receipt(("m.A.test_one",)), incoherent)),
        ):
            with self.subTest(side=label):
                proc = self._compare(*pair)
                self.assertEqual(proc.returncode, gate_baseline.EXIT_REFUSED, proc.stderr)
                self.assertIn("does not explain", proc.stderr)
        # POSITIVE CONTROL: the same empty set beside a PASSING gate is coherent and compares.
        ok = self._compare(_make_receipt(("m.A.test_one",)), _make_receipt((), status=0))
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)

    def test_a_passing_gate_that_names_failures_is_refused(self) -> None:
        incoherent = _make_receipt(("m.A.test_one",), status=0)
        self.assertTrue(gate_receipt.verify_receipt(incoherent))
        proc = self._compare(_make_receipt(("m.A.test_one",)), incoherent)
        self.assertEqual(proc.returncode, gate_baseline.EXIT_REFUSED, proc.stderr)
        self.assertIn("passed", proc.stderr)

    def test_two_different_gates_are_refused(self) -> None:
        """Two gates run different tests, so a subset across them means nothing."""
        proc = self._compare(
            _make_receipt(("m.A.test_one", "m.A.test_two")),
            _make_receipt(("m.A.test_one",), gate="mise run test"),
        )
        self.assertEqual(proc.returncode, gate_baseline.EXIT_REFUSED, proc.stderr)
        self.assertIn("mise run test", proc.stderr)
        # POSITIVE CONTROL: the same candidate under the same gate label is a clean subset.
        ok = self._compare(_make_receipt(("m.A.test_one", "m.A.test_two")), _make_receipt(("m.A.test_one",)))
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)

    def test_refusals_are_raised_as_a_typed_error_through_the_api(self) -> None:
        with self.assertRaises(gate_baseline.ComparisonError) as raised:
            gate_baseline.compare(
                _make_receipt(("m.A.test_one",), with_failures=False),
                _make_receipt(("m.A.test_one",)),
            )
        self.assertEqual(raised.exception.code, gate_baseline.EXIT_REFUSED)


class InvalidInputTests(_BaselineTestCase):
    """A receipt that does not verify is unusable input, which is a different failure from a verdict."""

    def test_a_tampered_receipt_is_a_schema_error_not_a_verdict(self) -> None:
        tampered = dict(_make_receipt(("m.A.test_one", "m.A.test_two")))
        tampered["failures"] = {
            "harness": gate_receipt.HARNESS_UNITTEST,
            "state": gate_receipt.FAILURES_IDENTIFIED,
            "names": ["m.A.test_one"],  # a failure edited out AFTER the digest was taken
        }
        self.assertFalse(gate_receipt.verify_receipt(tampered))
        proc = self._compare(tampered, _make_receipt(("m.A.test_one",)))
        self.assertEqual(proc.returncode, gate_baseline.EXIT_USAGE, proc.stderr)
        self.assertIn("does not verify", proc.stderr)
        self.assertEqual(proc.stdout, "")
        # POSITIVE CONTROL: the untampered receipt with the very same shape is accepted, so the
        # rejection is the re-derivation and not the field.
        ok = self._compare(_make_receipt(("m.A.test_one", "m.A.test_two")), _make_receipt(("m.A.test_one",)))
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)

    def test_unreadable_and_non_receipt_inputs_are_schema_errors(self) -> None:
        good = self._write("good.json", _make_receipt(("m.A.test_one",)))
        cases = {
            "missing file": self.tmp / "absent.json",
            "not json": self._write_text("garbage.json", "not json at all\n"),
            "a json list": self._write_text("list.json", "[1, 2, 3]\n"),
            "a json string": self._write_text("string.json", '"receipt"\n'),
            "an empty file": self._write_text("empty.json", ""),
            "a directory": self.tmp,
        }
        for label, path in cases.items():
            with self.subTest(label=label):
                proc = self._run(["compare", "--baseline", str(path), "--candidate", str(good)])
                self.assertEqual(proc.returncode, gate_baseline.EXIT_USAGE, proc.stderr)
                self.assertEqual(proc.stdout, "")
        # POSITIVE CONTROL: the same `good` receipt on both sides is accepted.
        ok = self._run(["compare", "--baseline", str(good), "--candidate", str(good)])
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)

    def _write_text(self, name: str, text: str) -> Path:
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_stdin_is_not_a_receipt_source(self) -> None:
        """`-` is refused as a stream name, not merely missing as a file.

        Asserting the refusal against an ABSENT `./-` would prove nothing: the same exit code comes
        from ENOENT, so the guard could be deleted with the test still green. A readable receipt is
        therefore PLANTED at `./-` first, and the positive control reads that very file through an
        explicit `./-` path.
        """
        good = self._write("good.json", _make_receipt(("m.A.test_one",)))
        decoy = self._write("-", _make_receipt(("m.A.test_one",)))
        self.assertTrue(decoy.exists())
        proc = self._run(["compare", "--baseline", "-", "--candidate", str(good)])
        self.assertEqual(proc.returncode, gate_baseline.EXIT_USAGE, proc.stderr)
        self.assertIn("not a receipt source", proc.stderr)
        self.assertEqual(proc.stdout, "")
        # POSITIVE CONTROL: the planted file IS a usable receipt when named as a path, so the
        # refusal above is the `-` guard and not an unreadable or invalid file.
        ok = self._run(["compare", "--baseline", "./-", "--candidate", str(good)])
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)

    def test_a_verifying_receipt_with_no_outcome_is_refused_not_given_a_verdict(self) -> None:
        """A receipt that carries a failing set but NO `outcome` must not be compared.

        It VERIFIES: `verify_receipt` deliberately scopes its outcome invariants to receipts that
        carry the field, so re-sealing a body without one is a legitimately verifiable receipt. That
        is what makes the pre-taxonomy check load-bearing rather than redundant with verification —
        without it every outcome branch in `failing_set` misses, none of the vacuous-truth refusals
        fire, and the comparison prints a subset verdict whose `baseline_outcome` is null: a claim
        about worsening over a gate whose result was never recorded.
        """
        full = _make_receipt(("m.A.test_one",))
        body = {k: v for k, v in full.items() if k not in ("self_digest", "outcome")}
        resealed = dict(body)
        resealed["self_digest"] = gate_receipt.canonical_digest(body)
        self.assertNotIn("outcome", resealed)
        self.assertIn("failures", resealed)
        # Not a tamper case: this receipt re-derives, so exit 2 below cannot come from verification.
        self.assertTrue(gate_receipt.verify_receipt(resealed))
        proc = self._compare(resealed, _make_receipt(("m.A.test_one",)))
        self.assertEqual(proc.returncode, gate_baseline.EXIT_USAGE, proc.stderr)
        self.assertIn("predates the outcome taxonomy", proc.stderr)
        self.assertEqual(proc.stdout, "")
        # POSITIVE CONTROL: the identical receipt WITH its outcome compares cleanly, so the refusal
        # is the absent verdict and not the resealing, the failing set, or the fixture.
        ok = self._compare(full, _make_receipt(("m.A.test_one",)))
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)
        self.assertEqual(self._report(ok)["baseline_outcome"], gate_receipt.OUTCOME_FAILED)

    def test_a_verifying_baseline_receipt_with_no_cwd_is_refused_not_stamped_null(self) -> None:
        """agentic-sdlc-de3a (D1): a receipt admitted with no `cwd` would stamp `baseline_cwd: null`
        onto the report -- naming no baseline location at all -- rather than being refused. Mirrors
        `test_a_verifying_receipt_with_no_outcome_is_refused_not_given_a_verdict` exactly: dropping a
        field and re-sealing the digest is a legitimately VERIFIABLE receipt (`verify_receipt`
        re-derives over whatever non-self_digest fields are present), so this is what makes the
        presence check load-bearing rather than redundant with verification.
        """
        full = _make_receipt(("m.A.test_one",), cwd="/tmp/repo-with-a-cwd")
        body = {k: v for k, v in full.items() if k not in ("self_digest", "cwd")}
        resealed = dict(body)
        resealed["self_digest"] = gate_receipt.canonical_digest(body)
        self.assertNotIn("cwd", resealed)
        self.assertIn("failures", resealed)
        # Not a tamper case: this receipt re-derives, so exit 2 below cannot come from verification.
        self.assertTrue(gate_receipt.verify_receipt(resealed))
        for label, pair in (
            ("baseline", (resealed, _make_receipt(("m.A.test_one",)))),
            ("candidate", (_make_receipt(("m.A.test_one",)), resealed)),
        ):
            with self.subTest(side=label):
                proc = self._compare(*pair)
                self.assertEqual(proc.returncode, gate_baseline.EXIT_USAGE, proc.stderr)
                self.assertIn("carries no cwd", proc.stderr)
                self.assertEqual(proc.stdout, "")
        # POSITIVE CONTROL: the identical receipt WITH its cwd compares cleanly and stamps the
        # report with it, so the refusal above is the absent cwd and not the resealing, the failing
        # set, or the fixture.
        ok = self._compare(full, _make_receipt(("m.A.test_one",)))
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)
        self.assertEqual(self._report(ok)["baseline_cwd"], "/tmp/repo-with-a-cwd")

    def test_both_receipt_paths_are_required(self) -> None:
        good = self._write("good.json", _make_receipt(("m.A.test_one",)))
        for args in (["compare"], ["compare", "--baseline", str(good)], ["compare", "--candidate", str(good)]):
            with self.subTest(args=args):
                proc = self._run(args)
                self.assertEqual(proc.returncode, gate_baseline.EXIT_USAGE, proc.stderr)


class ReportAndEffectTests(_BaselineTestCase):
    """The comparison is a read-only query: canonical bytes out, nothing written anywhere."""

    def test_the_report_is_canonical_json_on_stdout(self) -> None:
        proc = self._compare(_make_receipt(("m.A.test_one",)), _make_receipt(("m.A.test_one",)))
        self.assertEqual(proc.returncode, gate_baseline.EXIT_OK, proc.stderr)
        reparsed = json.loads(proc.stdout)
        self.assertEqual(proc.stdout.encode("utf-8"), gate_receipt.canonical_json(reparsed) + b"\n")
        self.assertEqual(reparsed["schema_version"], gate_baseline.SCHEMA_VERSION)

    def test_the_report_stamps_the_baseline_receipts_cwd_and_self_digest(self) -> None:
        """agentic-sdlc-de3a: the report names WHICH receipt it baselines, not just which tests it
        failed with, so a consumer can independently check the stamp against a receipt it holds."""
        baseline = _make_receipt(("m.A.test_one", "m.A.test_two"), cwd="/tmp/repo-one")
        proc = self._compare(baseline, _make_receipt(("m.A.test_one",)))
        self.assertEqual(proc.returncode, gate_baseline.EXIT_OK, proc.stderr)
        report = self._report(proc)
        self.assertEqual(report["baseline_cwd"], "/tmp/repo-one")
        self.assertEqual(report["baseline_cwd"], baseline["cwd"])
        self.assertEqual(report["baseline_self_digest"], baseline["self_digest"])
        # Only the BASELINE side is stamped: the candidate side is already bound by value (the gate
        # label plus its exact failing set and outcome), so a digest there would be redundant.
        self.assertNotIn("candidate_cwd", report)
        self.assertNotIn("candidate_self_digest", report)
        # POSITIVE CONTROL: a baseline receipt from a DIFFERENT cwd, with a necessarily different
        # self_digest, stamps DIFFERENT values -- so the equalities above are reading the receipt
        # this comparison actually loaded, not a hardcoded fixture constant that happens to match.
        other_baseline = _make_receipt(("m.A.test_one", "m.A.test_two"), cwd="/tmp/repo-two")
        other_proc = self._compare(other_baseline, _make_receipt(("m.A.test_one",)))
        other_report = self._report(other_proc)
        self.assertEqual(other_report["baseline_cwd"], "/tmp/repo-two")
        self.assertNotEqual(other_report["baseline_cwd"], report["baseline_cwd"])
        self.assertNotEqual(other_report["baseline_self_digest"], report["baseline_self_digest"])

    def test_the_report_key_set_includes_exactly_the_baseline_identity_stamp(self) -> None:
        proc = self._compare(_make_receipt(("m.A.test_one",)), _make_receipt(("m.A.test_one",)))
        self.assertEqual(proc.returncode, gate_baseline.EXIT_OK, proc.stderr)
        self.assertEqual(
            set(self._report(proc)),
            {
                "schema_version",
                "gate",
                "baseline_outcome",
                "candidate_outcome",
                "baseline_cwd",
                "baseline_self_digest",
                "baseline_failing",
                "candidate_failing",
                "newly_failing",
                "fixed",
                "still_failing",
                "non_worsening",
                "toolchain_drifted",
            },
        )

    def test_the_comparison_writes_nothing(self) -> None:
        baseline = self._write("baseline.json", _make_receipt(("m.A.test_one", "m.A.test_two")))
        candidate = self._write("candidate.json", _make_receipt(("m.B.test_new",)))
        before = {p.name: p.read_bytes() for p in sorted(self.tmp.iterdir())}
        proc = self._run(["compare", "--baseline", str(baseline), "--candidate", str(candidate)])
        self.assertEqual(proc.returncode, gate_baseline.EXIT_WORSENED, proc.stderr)
        after = {p.name: p.read_bytes() for p in sorted(self.tmp.iterdir())}
        self.assertEqual(before, after)  # no report file, no journal, no rewritten receipt

    def test_a_toolchain_drift_between_the_two_runs_is_reported_not_hidden(self) -> None:
        drifted = self._compare(
            _make_receipt(("m.A.test_one",)),
            _make_receipt(("m.A.test_one",), lock_bytes=DRIFTED_LOCK_BYTES),
        )
        self.assertEqual(drifted.returncode, gate_baseline.EXIT_OK, drifted.stderr)
        self.assertTrue(self._report(drifted)["toolchain_drifted"])
        self.assertIn("toolchain", drifted.stderr)
        # POSITIVE CONTROL: the same pins report no drift, so the flag tracks the receipts.
        same = self._compare(_make_receipt(("m.A.test_one",)), _make_receipt(("m.A.test_one",)))
        self.assertFalse(self._report(same)["toolchain_drifted"])

    def test_quiet_suppresses_the_human_line_but_never_the_report(self) -> None:
        baseline = self._write("baseline.json", _make_receipt(("m.A.test_one",)))
        candidate = self._write("candidate.json", _make_receipt(("m.B.test_new",)))
        args = ["compare", "--baseline", str(baseline), "--candidate", str(candidate)]
        loud = self._run(args)
        quiet = self._run([*args, "--quiet"])
        self.assertEqual(loud.returncode, gate_baseline.EXIT_WORSENED, loud.stderr)
        self.assertEqual(quiet.returncode, gate_baseline.EXIT_WORSENED, quiet.stderr)
        self.assertIn("m.B.test_new", loud.stderr)
        self.assertEqual(quiet.stderr, "")
        self.assertEqual(loud.stdout, quiet.stdout)

    def test_a_failed_report_write_is_partial_never_a_clean_refusal(self) -> None:
        """Bytes may already have reached the consumer, so the result is unknown, not effect-free."""
        baseline = self._write("baseline.json", _make_receipt(("m.A.test_one",)))
        candidate = self._write("candidate.json", _make_receipt(("m.A.test_one",)))
        args = ["compare", "--baseline", str(baseline), "--candidate", str(candidate)]
        broken = mock.Mock()
        broken.write.side_effect = OSError(errno.EPIPE, "broken pipe")
        with mock.patch.object(sys, "stdout", mock.Mock(buffer=broken)):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = gate_baseline.main(args)
        text = err.getvalue()
        self.assertEqual(code, gate_baseline.EXIT_PARTIAL, text)
        self.assertNotEqual(code, gate_baseline.EXIT_INTERNAL)
        self.assertNotEqual(code, gate_baseline.EXIT_REFUSED)
        self.assertIn("already happened", text)
        # POSITIVE CONTROL: over a working stream the identical call emits one report and exits 0.
        buffer = io.BytesIO()
        with contextlib.redirect_stderr(io.StringIO()):
            with mock.patch.object(sys, "stdout", mock.Mock(buffer=buffer)):
                ok_code = gate_baseline.main(args)
        self.assertEqual(ok_code, gate_baseline.EXIT_OK)
        self.assertEqual(json.loads(buffer.getvalue())["non_worsening"], True)

    def test_an_unexpected_internal_failure_before_any_output_is_not_partial(self) -> None:
        baseline = self._write("baseline.json", _make_receipt(("m.A.test_one",)))
        candidate = self._write("candidate.json", _make_receipt(("m.A.test_one",)))
        args = ["compare", "--baseline", str(baseline), "--candidate", str(candidate)]
        with mock.patch.object(gate_baseline, "compare", side_effect=RuntimeError("boom")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = gate_baseline.main(args)
        self.assertEqual(code, gate_baseline.EXIT_INTERNAL, err.getvalue())
        self.assertIn("unexpected RuntimeError", err.getvalue())

    def test_the_exit_codes_are_pairwise_distinct_and_worsened_sits_outside_the_contract(self) -> None:
        codes = [
            gate_baseline.EXIT_OK,
            gate_baseline.EXIT_INTERNAL,
            gate_baseline.EXIT_USAGE,
            gate_baseline.EXIT_REFUSED,
            gate_baseline.EXIT_PARTIAL,
            gate_baseline.EXIT_WORSENED,
        ]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(codes[:5], [0, 1, 2, 3, 4])  # the effect-aware contract, verbatim
        # A worsened comparison is a successful QUERY reporting a bad verdict, so it must not
        # borrow any of the producer-failure codes — the same reason the producer's own
        # "gate ran and failed" sits at 5 rather than at 1, 2, 3, or 4.
        self.assertNotIn(gate_baseline.EXIT_WORSENED, {0, 1, 2, 3, 4})
        self.assertEqual(gate_baseline.EXIT_WORSENED, gate_receipt.EXIT_GATE_FAILED)

    def test_the_help_text_states_that_a_verdict_authorizes_nothing(self) -> None:
        proc = self._run(["compare", "--help"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # argparse re-wraps the epilog, so the claim is checked against unwrapped text.
        unwrapped = " ".join(proc.stdout.split())
        self.assertIn("authorizes nothing", unwrapped)
        self.assertIn("blocked until the repository is write-ready", unwrapped)


def _run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Two shapes, because they produced two DIFFERENT wrong codes over the same complete report:

        closed  `2>&-`. CPython starts with `sys.stderr is None`, so the first write raises
                `AttributeError` and the comparison exited 1 — documented as "before any report
                byte was written", with all 409 bytes of the report already on stdout.
        epipe   fd 2 is a pipe whose reader is already gone: every write raises `EPIPE` and leaves
                bytes pending, which the interpreter flushes again while finalizing and turns into
                exit 120 — outside the declared space entirely.

    Stderr is deliberately not captured; capturing it hands the child a writable stream and tests
    nothing. `_stderr_is_really_hostile` proves each mode reaches the child.
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
    os.close(read_fd)
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd))
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
class HostileStderrTests(_BaselineTestCase):
    """The human summary is ADVISORY. Losing it may cost the summary and nothing else.

    Every case here was live. The report was written and flushed to stdout FIRST, then `_summarize`
    wrote to stderr; when that failed, `_report_failure` opened with another `sys.stderr.write` and
    raised on its way out, so a complete report exited 1 — the code documented as "before any report
    byte was written" — or 120. `--quiet` returning the right code over the same receipts is what
    localized the fault to the advisory channel, so it is the control used throughout.
    """

    def _pair(self, baseline_names: tuple[str, ...], candidate_names: tuple[str, ...]) -> list[str]:
        return [
            "compare",
            "--baseline",
            str(self._write("baseline.json", _make_receipt(baseline_names))),
            "--candidate",
            str(self._write("candidate.json", _make_receipt(candidate_names))),
        ]

    def test_the_hostile_stderr_fixture_is_actually_hostile(self) -> None:
        """The control for every negative assertion below.

        The canary's exit codes are the second half of it: under `2>&-` it sees `sys.stderr is None`
        and exits 0, while under a broken pipe it CATCHES the error and still exits 120, because the
        bytes it left pending are flushed again during finalization. Swallowing the write is
        therefore not sufficient on its own.
        """
        self.assertEqual(_stderr_is_really_hostile("closed", self.tmp), "0:none")
        self.assertEqual(_stderr_is_really_hostile("epipe", self.tmp), "120:BrokenPipeError")

    def test_a_hostile_stderr_changes_neither_the_verdict_nor_the_report(self) -> None:
        cases = {
            # (baseline, candidate): the verdict this pair must return on every stderr
            gate_baseline.EXIT_WORSENED: (("m.A.test_one",), ("m.A.test_one", "m.B.test_new")),
            gate_baseline.EXIT_OK: (("m.A.test_one", "m.A.test_two"), ("m.A.test_one",)),
        }
        for expected, (before, after) in cases.items():
            args = self._pair(before, after)
            control = self._run(args)
            quiet = self._run([*args, "--quiet"])
            # The two controls: the loud run genuinely writes the summary this test takes away, and
            # `--quiet` — the same comparison with the channel switched off — already returns the
            # right code. Without the first, "the code is right" would prove nothing.
            self.assertEqual(control.returncode, expected, control.stderr)
            self.assertNotEqual(control.stderr, "")
            self.assertIn("authorizes no push", control.stderr)
            self.assertEqual(quiet.returncode, expected, quiet.stderr)
            self.assertEqual(quiet.stderr, "")
            for mode in ("closed", "epipe"):
                with self.subTest(expected=expected, mode=mode):
                    code, stdout = _run_with_hostile_stderr(
                        [sys.executable, "-B", str(SCRIPT), *args], mode=mode, cwd=self.tmp
                    )
                    self.assertEqual(code, expected)
                    self.assertIn(code, DECLARED_EXITS)  # never 1, and never 120
                    # The report is COMPLETE and byte-identical to the working-stderr run, which is
                    # what makes exit 1 — "before any report byte was written" — a false statement.
                    self.assertEqual(stdout.decode("utf-8"), control.stdout)
                    self.assertEqual(json.loads(stdout)["non_worsening"], expected == gate_baseline.EXIT_OK)

    def test_a_hostile_stderr_cannot_reclassify_a_refusal_or_a_usage_error(self) -> None:
        """Neither writes a report byte, so both must keep their own codes rather than collapse to 1."""
        refusal = [
            "compare",
            "--baseline",
            str(self._write("baseline.json", _make_receipt(("m.A.test_one",)))),
            "--candidate",
            str(self._write("candidate.json", _make_receipt(("m.A.test_one",), gate="other gate"))),
        ]
        usage = ["compare", "--baseline", "only-one-side-given"]
        for args, expected in ((refusal, gate_baseline.EXIT_REFUSED), (usage, gate_baseline.EXIT_USAGE)):
            control = self._run(args)
            # CONTROL: the code comes from the named refusal/usage path on a working stderr, not
            # from an interpreter that failed for some unrelated reason.
            self.assertEqual(control.returncode, expected, control.stderr)
            self.assertNotEqual(control.stderr, "")
            for mode in ("closed", "epipe"):
                with self.subTest(expected=expected, mode=mode):
                    code, stdout = _run_with_hostile_stderr(
                        [sys.executable, "-B", str(SCRIPT), *args], mode=mode, cwd=self.tmp
                    )
                    self.assertEqual(code, expected)
                    self.assertIn(code, DECLARED_EXITS)
                    self.assertEqual(stdout, b"")  # neither path may emit a report

    def test_a_broken_stdout_reports_partial_and_the_interpreter_cannot_overwrite_it(self) -> None:
        """The ARTIFACT channel's own failure: 4 was already correct, and 120 used to replace it."""
        argv = [
            sys.executable,
            "-B",
            str(SCRIPT),
            *self._pair(("m.A.test_one",), ("m.A.test_one",)),
            "--quiet",
        ]
        read_fd, write_fd = os.pipe()
        os.close(read_fd)  # nobody will ever read the report
        try:
            child = subprocess.Popen(argv, stdout=write_fd, stderr=subprocess.PIPE, cwd=str(self.tmp))
        finally:
            os.close(write_fd)
        assert child.stderr is not None
        with child.stderr as stream:
            err = stream.read().decode("utf-8", "replace")
        code = child.wait()
        self.assertEqual(code, gate_baseline.EXIT_PARTIAL, err)
        self.assertIn(code, DECLARED_EXITS)
        self.assertNotEqual(code, 120)
        self.assertIn("already happened", err)
        self.assertNotIn("Exception ignored", err)  # no stream left for finalization to retry
        # POSITIVE CONTROL: over a working stdout the same argv emits one report and exits 0.
        ok = subprocess.run(argv, capture_output=True, text=True, cwd=str(self.tmp), check=False)
        self.assertEqual(ok.returncode, gate_baseline.EXIT_OK, ok.stderr)
        self.assertTrue(json.loads(ok.stdout)["non_worsening"])


class EndToEndBaselineTests(unittest.TestCase):
    """A real gate, a real baseline receipt, a real swap — through both command-line surfaces."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.tmp / "mise.lock").write_bytes(LOCK_BYTES)

    def _suite(self, failing: tuple[str, ...], passing: tuple[str, ...]) -> list[str]:
        lines = ["import unittest", "", "", "class Suite(unittest.TestCase):"]
        for name in failing:
            lines += [f"    def {name}(self):", "        self.fail('injected')"]
        for name in passing:
            lines += [f"    def {name}(self):", "        pass"]
        (self.tmp / "wave_suite.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return [sys.executable, "-B", "-m", "unittest", "wave_suite"]

    def _record(self, argv: list[str], out: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "gate_receipt.py"),
                "record",
                "--gate",
                "fake check",
                "--out",
                str(out),
                "--harness",
                "unittest",
                "--quiet",
                "--",
                *argv,
            ],
            capture_output=True,
            text=True,
            cwd=str(self.tmp),
            check=False,
        )

    def test_a_wave_that_fixes_one_test_and_breaks_another_is_reported_as_worsened(self) -> None:
        baseline_out = self.tmp / "baseline.json"
        first = self._record(
            self._suite(failing=("test_alpha", "test_beta"), passing=("test_gamma",)), baseline_out
        )
        self.assertEqual(first.returncode, gate_receipt.EXIT_GATE_FAILED, first.stderr)
        candidate_out = self.tmp / "candidate.json"
        second = self._record(
            # test_beta was fixed and test_gamma was broken: the COUNT is unchanged.
            self._suite(failing=("test_alpha", "test_gamma"), passing=("test_beta",)),
            candidate_out,
        )
        self.assertEqual(second.returncode, gate_receipt.EXIT_GATE_FAILED, second.stderr)
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "compare",
                "--baseline",
                str(baseline_out),
                "--candidate",
                str(candidate_out),
            ],
            capture_output=True,
            text=True,
            cwd=str(self.tmp),
            check=False,
        )
        report = json.loads(proc.stdout)
        self.assertEqual(report["baseline_failing"], ["wave_suite.Suite.test_alpha", "wave_suite.Suite.test_beta"])
        self.assertEqual(report["candidate_failing"], ["wave_suite.Suite.test_alpha", "wave_suite.Suite.test_gamma"])
        self.assertEqual(report["newly_failing"], ["wave_suite.Suite.test_gamma"])
        self.assertEqual(report["fixed"], ["wave_suite.Suite.test_beta"])
        self.assertFalse(report["non_worsening"])
        self.assertEqual(proc.returncode, gate_baseline.EXIT_WORSENED, proc.stderr)
        # POSITIVE CONTROL: a genuine remediation of the same baseline is non-worsening, so the
        # verdict above is the swap and not two receipts that can never agree.
        progress_out = self.tmp / "progress.json"
        third = self._record(
            self._suite(failing=("test_alpha",), passing=("test_beta", "test_gamma")), progress_out
        )
        self.assertEqual(third.returncode, gate_receipt.EXIT_GATE_FAILED, third.stderr)
        progress = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "compare",
                "--baseline",
                str(baseline_out),
                "--candidate",
                str(progress_out),
            ],
            capture_output=True,
            text=True,
            cwd=str(self.tmp),
            check=False,
        )
        self.assertEqual(progress.returncode, gate_baseline.EXIT_OK, progress.stderr)
        progress_report = json.loads(progress.stdout)
        self.assertTrue(progress_report["non_worsening"])
        self.assertEqual(progress_report["fixed"], ["wave_suite.Suite.test_beta"])
        self.assertEqual(progress_report["still_failing"], ["wave_suite.Suite.test_alpha"])
        # Still not write-ready: the candidate gate is red, and non-worsening says nothing else.
        self.assertEqual(progress_report["candidate_outcome"], "failed")


if __name__ == "__main__":
    unittest.main()
