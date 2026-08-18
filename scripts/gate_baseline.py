#!/usr/bin/env python3
"""Exact non-worsening baseline comparison over two gate receipts. Stdlib only.

A repository is **remediation-ready** when its exact known gate failures are *baselined* and a
remediation wave "does not worsen the global failure set" (product-spec Implementation Decision 17,
issues/09:112-119, ADR-0022, CONTEXT.md's readiness vocabulary). Neither term was defined anywhere
in this repository, and under Implementation Decision 54 a required property that cannot be enforced
or observed makes its feature unsupported. This module is that definition, as the operator decided
it on 2026-08-17:

    baselined              a stored gate receipt carrying the SET of named failing tests
    exact non-worsening    the new run's failing set is a SUBSET of the baseline's

Why a subset, and not the two cheaper readings. A status-only comparison ("was it red before and
red now?") and a count-based comparison ("were there 15 failures before and 15 now?") cannot see
WHICH tests changed, so a wave that fixes one failure and breaks a different one reads as
non-worsening under both. That is precisely what the word "exact" in Decision 17 exists to prevent,
and it is the case `tests/test_gate_baseline.py` asserts first.

The answer is a SET OF NAMES, not a boolean, because the caller's question is "what got worse" and a
boolean cannot answer it. `fixed` is reported for the same reason from the other side:
`remediation-progress` has to be able to state exact improvement.

Every way this comparison could be VACUOUSLY true is a refusal rather than a green verdict:

    * a receipt that carries no failing set at all — it was never baselined;
    * a failing set recorded as `unparsed` — identification was attempted and failed, which is not
      an empty set and must never be compared as one;
    * a gate that produced no verdict (`outcome: unobserved`) on either side;
    * a red gate whose failing set is empty, or a passing gate that names failures — the set does
      not explain the verdict, so a subset over it proves nothing;
    * two different gate labels — different gates run different tests, so a subset across them is
      meaningless.

Exit codes follow the repository's effect-aware contract (Implementation Decision 9), and the
comparison's own success is kept separate from the verdict it reports:

    0  the comparison ran; the candidate's failing set is a subset (non-worsening)
    1  an unexpected internal failure, before any report byte was written
    2  unusable input: a missing, unreadable, non-JSON, non-receipt, unverifiable, or pre-taxonomy
       receipt, or a bad command line
    3  a clean refusal BEFORE any output: the receipts are valid but the question is unanswerable
    4  an unknown prefix of the report may already have reached stdout, so the result is partial
    5  the comparison ran and the candidate WORSENED the failing set

5 is deliberately outside the reserved 0-4 block, exactly as the producer's own "the gate ran and
failed" is: a worsened comparison is a SUCCESSFUL query reporting a bad verdict, and conflating it
with "the comparison failed" would let a broken query pass for a clean wave. Both 0 and 5 print the
full report, so the names are always available.

That set is CLOSED, so the human summary on stderr must be unable to add to it. It is advisory —
`--quiet` switches it off — and it is written after the report has already been flushed, so a stderr
that cannot be written may cost the summary and nothing else. Every line here therefore goes through
`gate_receipt.advisory_stderr`, and a failed report write abandons stdout as well: a stream left
holding unflushed bytes is flushed again during interpreter finalization, and that second failure
replaces this command's exit code with 120.

    python scripts/gate_baseline.py compare --baseline <receipt> --candidate <receipt> [--quiet]

This module reads two receipts and writes one report to stdout. It creates no file, so it never
takes a position on WHERE a receipt belongs. Tamper detection is by re-derivation, not a security
boundary against the same OS user: a non-worsening verdict is evidence about two receipts and
authorizes nothing — not push, publication, PR mutation, merge, or deployment, all of which stay
blocked until the repository is write-ready.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import gate_receipt  # noqa: E402 - resolved against the repository root above

#: The report payload's own version, independent of the receipt schema it reads.
SCHEMA_VERSION = "gate-baseline-comparison/v1"

#: The candidate's failing set is a subset of the baseline's.
EXIT_OK = 0
#: An unexpected internal failure, with no report byte written.
EXIT_INTERNAL = 1
#: Unusable input or an unusable command line.
EXIT_USAGE = 2
#: A named clean refusal BEFORE any output: valid receipts, unanswerable question.
EXIT_REFUSED = 3
#: An unknown prefix of the report may already have reached stdout.
EXIT_PARTIAL = 4
#: The comparison ran and names at least one newly-failing test. Never inside the reserved block.
EXIT_WORSENED = 5


class ComparisonError(Exception):
    """A refusal or an input error, never a verdict about the wave.

    `code` is required at every raise site, because whether an input was unusable (2) or the
    question was unanswerable (3) is exactly the distinction a caller acts on.
    """

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def _load_receipt(raw: str, side: str) -> dict[str, Any]:
    """Read one verified receipt from a path. Every failure here is unusable input (2)."""
    if raw == "-":
        raise ComparisonError(
            f"--{side} takes a receipt path; `-` is not a receipt source, and reading it as a file "
            "named `-` would compare something nobody asked for",
            EXIT_USAGE,
        )
    try:
        data = Path(raw).read_bytes()
    except OSError as exc:
        raise ComparisonError(f"cannot read the {side} receipt {raw}: {exc}", EXIT_USAGE) from exc
    try:
        receipt = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ComparisonError(f"the {side} receipt {raw} is not JSON: {exc}", EXIT_USAGE) from exc
    if not isinstance(receipt, dict):
        raise ComparisonError(
            f"the {side} receipt {raw} is not a receipt object", EXIT_USAGE
        )
    if not gate_receipt.verify_receipt(receipt):
        raise ComparisonError(
            f"the {side} receipt {raw} does not verify: its self_digest does not re-derive, or its "
            "recorded state is not one this producer could have written",
            EXIT_USAGE,
        )
    if "outcome" not in receipt:
        raise ComparisonError(
            f"the {side} receipt {raw} predates the outcome taxonomy, so what its failing set means "
            "cannot be established; re-record it",
            EXIT_USAGE,
        )
    return receipt


def failing_set(receipt: dict[str, Any], side: str) -> list[str]:
    """The exact failing set a receipt was baselined with, or a refusal saying why there is none.

    Each refusal below is a way the subset comparison would otherwise be vacuously true, which is
    strictly worse than no answer: it would certify a wave that broke something.
    """
    outcome = receipt.get("outcome")
    if outcome == gate_receipt.OUTCOME_UNOBSERVED:
        raise ComparisonError(
            f"the {side} gate produced no verdict (outcome unobserved), so it can neither be a "
            "baseline nor be compared against one",
            EXIT_REFUSED,
        )
    failures = receipt.get("failures")
    if failures is None:
        raise ComparisonError(
            f"the {side} receipt records no failing set, so it was never baselined: re-record the "
            "gate with --harness unittest",
            EXIT_REFUSED,
        )
    if failures["state"] != gate_receipt.FAILURES_IDENTIFIED:
        raise ComparisonError(
            f"the {side} receipt's failing set is {failures['state']}: identification was attempted "
            "and failed, which is not an empty failing set and cannot be compared as one",
            EXIT_REFUSED,
        )
    names = list(failures["names"])
    if outcome == gate_receipt.OUTCOME_FAILED and not names:
        raise ComparisonError(
            f"the {side} gate failed yet its failing set names no test, so the set does not explain "
            "the verdict and no subset over it would mean anything",
            EXIT_REFUSED,
        )
    if outcome == gate_receipt.OUTCOME_PASSED and names:
        raise ComparisonError(
            f"the {side} gate passed yet its failing set names {len(names)} failing test(s), so the "
            "set contradicts the verdict",
            EXIT_REFUSED,
        )
    return names


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare two baselined receipts, reporting the newly-failing and fixed sets BY NAME.

    Raises ComparisonError for an unanswerable question. A returned report is a fact about two
    receipts; it authorizes nothing.
    """
    if baseline.get("gate") != candidate.get("gate"):
        raise ComparisonError(
            "the two receipts are about different gates "
            f"({baseline.get('gate')!r} and {candidate.get('gate')!r}): different gates run "
            "different tests, so a subset across them says nothing about worsening",
            EXIT_REFUSED,
        )
    before = set(failing_set(baseline, "baseline"))
    after = set(failing_set(candidate, "candidate"))
    newly_failing = sorted(after - before)
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": baseline.get("gate"),
        "baseline_outcome": baseline.get("outcome"),
        "candidate_outcome": candidate.get("outcome"),
        "baseline_failing": sorted(before),
        "candidate_failing": sorted(after),
        "newly_failing": newly_failing,
        "fixed": sorted(before - after),
        "still_failing": sorted(before & after),
        # Exact non-worsening, verbatim: the candidate's failing set is a subset of the baseline's.
        "non_worsening": not newly_failing,
        # Advisory, and reported rather than refused: two receipts bound to different pinned
        # toolchains can be compared honestly, but "green on drifted pins" is a real reading and the
        # binding catches nothing unless somebody looks at it.
        "toolchain_drifted": baseline.get("toolchain_digest") != candidate.get("toolchain_digest"),
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - exercised via subprocess
        # Through the shared guarded sink, argparse's own `print_usage` included: argparse swallows
        # a failed write, but the bytes it leaves pending are enough for the interpreter's shutdown
        # flush to replace this usage error's 2 with 120.
        note = gate_receipt.advisory_stderr()
        note(self.format_usage())
        note(f"{self.prog}: error: {message}\n")
        raise SystemExit(EXIT_USAGE)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="gate_baseline.py",
        description=(
            "Compare two gate receipts as failing SETS: is the candidate's set a subset of the "
            "baseline's? A verdict here authorizes nothing."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    compare_parser = sub.add_parser(
        "compare",
        help="report the newly-failing and fixed sets between two baselined receipts",
        description=(
            "`baselined` means a receipt carrying the SET of named failing tests; `exact "
            "non-worsening` means the candidate's set is a SUBSET of the baseline's. The report "
            "names what got worse and what got fixed, because a boolean cannot answer either."
        ),
        epilog=(
            "Exit codes: 0 the candidate's failing set is a subset (non-worsening); 1 unexpected "
            "internal failure before any output; 2 unusable input or command line; 3 clean refusal "
            "before any output, because the question is unanswerable (no failing set, an unparsed "
            "set, no verdict, a set that contradicts its verdict, or two different gates); 4 an "
            "unknown prefix of the report may already have reached stdout; 5 the comparison ran and "
            "the candidate WORSENED the failing set. 0 and 5 are both successful queries and both "
            "print the report. A non-worsening verdict is evidence about two receipts and "
            "authorizes nothing — push, publication, PR mutation, merge, and deployment stay "
            "blocked until the repository is write-ready."
        ),
    )
    compare_parser.add_argument("--baseline", required=True, help="path to the baseline receipt")
    compare_parser.add_argument("--candidate", required=True, help="path to the candidate receipt")
    compare_parser.add_argument(
        "--quiet", action="store_true", help="do not summarize the verdict on stderr"
    )
    return parser


def _summarize(report: dict[str, Any]) -> None:
    """Restate the verdict for a human. Display only: `--quiet` switches it off, and so does a
    stderr that cannot be written, because the REPORT on stdout is the answer and this exit code is
    the verdict. It runs after the report has been flushed, so every line here is by construction
    unable to change either — which it could not honour while writing through a raw
    `sys.stderr.write` that raises.
    """
    note = gate_receipt.advisory_stderr()
    verdict = "NON-WORSENING" if report["non_worsening"] else "WORSENED"
    note(
        f"gate_baseline.py: {verdict}: {len(report['newly_failing'])} newly failing, "
        f"{len(report['fixed'])} fixed, {len(report['still_failing'])} still failing\n"
    )
    for name in report["newly_failing"]:
        note(f"gate_baseline.py:   newly failing: {name}\n")
    for name in report["fixed"]:
        note(f"gate_baseline.py:   fixed: {name}\n")
    if report["toolchain_drifted"]:
        note(
            "gate_baseline.py: the two runs are bound to DIFFERENT pinned toolchains, so this "
            "comparison spans a toolchain change\n"
        )
    note(
        "gate_baseline.py: this is evidence about two receipts; it authorizes no push, "
        "publication, PR mutation, merge, or deployment\n"
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    emitted = False
    try:
        baseline = _load_receipt(args.baseline, "baseline")
        candidate = _load_receipt(args.candidate, "candidate")
        report = compare(baseline, candidate)
        payload = gate_receipt.canonical_json(report) + b"\n"
        try:
            sys.stdout.buffer.write(payload)
            sys.stdout.buffer.flush()
        except OSError as exc:
            # Bytes may already have reached the consumer and how many is unknowable from here, so
            # the effect is admitted AT the failure, where the doubt begins — not before the write,
            # which would claim an effect that had not happened, and not after a successful return,
            # which would classify this very failure as though nothing had happened.
            emitted = True
            # Admitted first, then abandoned: escalating to 4 below is worthless if the
            # interpreter's shutdown flush of the same broken stream overwrites the exit code with
            # 120, which is outside this command's declared 0-5 space entirely.
            gate_receipt.abandon_broken_stream("stdout", sys.stdout)
            raise ComparisonError(f"cannot write the report to stdout: {exc}", EXIT_INTERNAL) from exc
        if not args.quiet:
            _summarize(report)
    except ComparisonError as exc:
        return _report_failure(str(exc), exc.code, emitted=emitted)
    except Exception as exc:  # an unexpected failure must still classify its own effects
        return _report_failure(f"unexpected {type(exc).__name__}: {exc}", EXIT_INTERNAL, emitted=emitted)
    return EXIT_OK if report["non_worsening"] else EXIT_WORSENED


def _report_failure(message: str, code: int, *, emitted: bool) -> int:
    """Print the failure and return its effect-aware exit code.

    The single escalation point: once report bytes may have reached stdout, no failure may exit as a
    clean refusal or an effect-free internal failure, because what the consumer read is unknown.

    The sink is settled before the first line, because this function used to OPEN with a bare
    `sys.stderr.write` and was therefore the one place a broken stderr could not be reported from:
    the write raised on its way out of `except Exception`, the escalation below never ran, and a
    COMPLETE report on stdout exited 1 — "before any report byte was written" — or 120.
    """
    note = gate_receipt.advisory_stderr()
    note(f"gate_baseline.py: {message}\n")
    if emitted:
        note(
            "gate_baseline.py: this is a PARTIAL result, not a clean refusal:\n"
            "gate_baseline.py:   already happened: an unknown prefix of the report may have "
            "reached stdout\n"
        )
        return EXIT_PARTIAL
    return code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(main())
