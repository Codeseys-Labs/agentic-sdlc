#!/usr/bin/env python3
"""Tier-1 self-hashing canonical-JSON gate receipts, and the producer that emits them.

A gate receipt records, in reproducible form, WHETHER a specific gate command ran in a specific
worktree against a specific pinned toolchain, and what its exit code was — a receipt for a gate
that never ran is a first-class outcome, not a missing receipt. It is *tamper detection by
re-derivation*, not a security boundary against the same OS user (the same honesty posture as
scripts/validate_bundle.py's runtime-receipt validation). Stdlib only.

Canonical serialization matches the precedent in scripts/validate_bundle.py:412-413 —
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) then sha256 of the utf-8
bytes — so any consumer re-derives the digest byte-for-byte.

Three outcomes, not two. An exit code alone cannot separate "the gate never ran" from "the gate
ran and failed", and a consumer that conflates them reads an absent gate as a failing one — or,
worse, a never-run gate as satisfiable. Every receipt therefore carries an `outcome` derived from
`status`: `status: null` is `unobserved`, `0` is `passed`, and any other exit code is `failed`.
No exit code can spell `unobserved`.

`outcome` — not the process exit code — is the evidence, and the receipt makes each dishonest
combination unrepresentable rather than merely discouraged. Exactly four states verify, in any
receipt that CARRIES `outcome` (pre-`outcome` receipts predate these invariants and are exempt —
see `verify_receipt`):

    passed              status 0        argv [...]  signal null
    failed              status nonzero  argv [...]  signal null
    unobserved, no run  status null     argv null   signal null
    unobserved, killed  status null     argv [...]  signal N

`argv` is null exactly when nothing was executed. `unobserved` therefore means "no verdict was
observed", which is not the same as "nothing ran": it covers both the never-run and the killed
state, and those two are told apart by `argv` and `signal`, never by `outcome` alone. The fourth
state is the only way a populated `argv` may sit beside `outcome: unobserved`, and it has to say
WHY by carrying a signal — so no receipt can name a command it ran while claiming nothing ran at
all. The intended command stays on record as `gate` either way. A signal-killed gate DID run but
produced no exit code, so it carries the signal number and a null `status` instead of a negative
one — a negative `status` is not an exit code and reading it as a verdict would invent one.
`verify_receipt` rejects any other combination.

The producer's own exit code describes the PRODUCER, in one closed set that never passes a gate's
exit code through (`EXIT_*` below). A gate exiting 3 would otherwise be byte-identical to the
producer's own clean-refusal 3 — and 3 is this repository's canonical clean-refusal code, so that
collision is likely, not theoretical. The exact gate code lives in `status`, where it cannot be
confused with the producer's report.

Run the producer as:

    python scripts/gate_receipt.py record --gate "mise run check" --out <path|-> \\
        [--lock <mise.lock>] [--log <path>] [--cwd <dir>] [--unobserved] [--quiet] \\
        -- mise run check

`--out` is required and has no default: WHERE a receipt belongs (machine-local state, the ccodex
XDG state plane, or target-local) is a pending operator decision, so the producer takes the
destination from its caller rather than picking a side. A receipt is evidence of whether a gate ran
and what it returned; it authorizes nothing — not push, publication, PR mutation, merge, or
deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_UNOBSERVED = "unobserved"

# The producer's exit codes follow the repository's effect-aware exit contract (product-spec
# Implementation Decision 9): 0 success or exact no-effect, 1 unexpected internal failure before
# any admitted effect, 2 grammar/schema/input error, 3 clean refusal before any effect, 4 admitted
# partial or unknown effect. 5 and 6 sit outside that reserved block because the producer must
# also report a verdict it merely observed, and a gate's own exit code is never passed through:
# mirroring it would make a gate that exits 3 indistinguishable from the producer's refusal.

#: The gate ran and passed, and its receipt was written.
EXIT_OK = 0
#: An unexpected internal failure, with no admitted effect.
EXIT_INTERNAL = 1
#: The producer's own arguments or option values were unusable.
EXIT_USAGE = 2
#: A named clean refusal BEFORE the gate ran and before any destination was created.
EXIT_REFUSED = 3
#: An effect was already admitted — the gate ran, a destination was created (whether or not its
#: bytes made it), and/or receipt bytes reached stdout — and then something failed, so the result
#: is partial or unknown. Never reported as a clean refusal or as an effect-free failure.
EXIT_PARTIAL = 4
#: The gate ran and returned a nonzero exit code; the exact code is the receipt's `status`.
EXIT_GATE_FAILED = 5
#: A receipt was written, but no gate verdict was observed. Deliberately never 0.
EXIT_UNOBSERVED = 6


def canonical_json(obj: Any) -> bytes:
    """Canonical, reproducible JSON encoding of obj (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def canonical_digest(obj: Any) -> str:
    """sha256 hex of the canonical JSON of obj."""
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derive_outcome(status: int | None) -> str:
    """Closed outcome taxonomy for a gate run.

    None means the gate was never observed to run, which is a different fact from any exit code.
    Because the value is derived here, "unobserved" is unrepresentable as a nonzero exit code.
    """
    if status is None:
        return OUTCOME_UNOBSERVED
    return OUTCOME_PASSED if int(status) == 0 else OUTCOME_FAILED


def build_receipt(
    *,
    gate: str,
    argv: list[str] | None,
    status: int | None,
    log_bytes: bytes,
    lock_bytes: bytes,
    cwd: str,
    signal: int | None = None,
) -> dict[str, Any]:
    """Construct a self-hashing gate receipt.

    Fields (spec G2.6). Each is a RECORD made by this producer, re-derivable by any consumer; none
    of them is proof against a same-OS-user forger, which is the module's stated posture:
    - gate: the exact task string, e.g. "mise run check". Recorded whether or not anything ran, so
      an unobserved receipt still says which gate it is about.
    - argv: the exact argv list EXECUTED, so the receipt names which command ran rather than a
      paraphrase of it — or null when nothing was executed. A populated argv claims that this
      command ran, so it may sit beside `outcome: unobserved` only in the killed state, where
      `signal` says why no verdict exists.
    - status: the integer exit code, or null when no exit code was observed (nothing ran, or the
      gate was killed by a signal before it could return one).
    - signal: the signal number that killed the gate, or null. A killed gate ran but produced no
      verdict, which is neither an exit code nor "never ran"; a negative `status` would misreport
      it as a failing verdict.
    - outcome: passed | failed | unobserved, derived from status. "The gate never ran" and "the
      gate ran and failed" are distinct states here; status alone cannot tell them apart.
      `unobserved` says no verdict was observed, not that nothing ran (see the module docstring).
    - log_digest: sha256 of the captured combined stdout+stderr bytes — every byte captured, which
      for a killed gate is what it emitted before the kill and for an unobserved run is nothing at
      all (the digest of b""). It makes a stored log tamper-evident; it does not prove completeness.
    - toolchain_digest: sha256 of the mise.lock bytes READ FOR THIS RECEIPT (for an observed gate,
      read just before it ran). It binds the receipt to the exact pinned toolchain, so a consumer
      that compares two receipts can catch "green on drifted pins"; the binding alone catches
      nothing.
    - cwd: absolute path the gate ran in — for an unobserved receipt, the path it WOULD have run
      in, since nothing ran there. Either way it ties the receipt to per-path worktree trust.
    - self_digest: sha256 of the canonical JSON of every other field.
    """
    body = {
        "gate": gate,
        "argv": None if argv is None else list(argv),
        "status": None if status is None else int(status),
        "signal": None if signal is None else int(signal),
        "outcome": derive_outcome(status),
        "log_digest": _sha256_hex(log_bytes),
        "toolchain_digest": _sha256_hex(lock_bytes),
        "cwd": cwd,
    }
    receipt = dict(body)
    receipt["self_digest"] = canonical_digest(body)
    return receipt


def _states_are_consistent(body: dict[str, Any]) -> bool:
    """True iff argv/status/signal spell one of the four honest states (see the module docstring)."""
    status = body.get("status")
    argv = body.get("argv")
    signal = body.get("signal")
    if isinstance(status, bool) or not (status is None or isinstance(status, int)):
        return False
    if status is not None and status < 0:
        return False  # a negative value encodes a signal, not an exit code (see `signal`)
    if argv is not None and not (isinstance(argv, list) and all(isinstance(a, str) for a in argv)):
        return False
    if isinstance(signal, bool) or not (signal is None or (isinstance(signal, int) and signal > 0)):
        return False
    if argv is None and status is not None:
        return False  # nothing executed, yet a verdict is claimed
    if signal is not None and (status is not None or argv is None):
        return False  # killed, so there is no exit code — and something must have run to be killed
    if status is None and argv is not None and signal is None:
        return False  # names an executed command AND claims nothing was observed
    return True


def verify_receipt(receipt: dict[str, Any]) -> bool:
    """True iff self_digest re-derives, outcome agrees with status, and the state is honest.

    Receipts written before `outcome` existed carry no such field and still verify: the digest is
    re-derived over whatever non-self_digest fields are present, so the added fields change the
    digest of NEW receipts only, and the state invariants apply only where `outcome` is present.
    """
    stored = receipt.get("self_digest")
    if not isinstance(stored, str):
        return False
    body = {k: v for k, v in receipt.items() if k != "self_digest"}
    if canonical_digest(body) != stored:
        return False
    if "outcome" in body:
        if not _states_are_consistent(body):
            return False
        if body["outcome"] != derive_outcome(body.get("status")):
            return False
    return True


def verify_toolchain_binding(receipt: dict[str, Any], lock_bytes: bytes) -> bool:
    """True iff the receipt's toolchain_digest matches the given mise.lock bytes."""
    return receipt.get("toolchain_digest") == _sha256_hex(lock_bytes)


# --------------------------------------------------------------------------------------------
# Producer: invoke a gate, capture its combined output, emit a receipt through build_receipt.
# --------------------------------------------------------------------------------------------


class _ProducerError(Exception):
    """A failure of the producer itself, never a verdict about the gate.

    `code` is deliberately required: every raise site must state whether it is an input error, a
    clean pre-effect refusal, or an unexpected failure, because a wrong default is exactly how a
    post-effect failure gets reported as a clean refusal.
    """

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


class _Effects:
    """What the producer has already done, so no failure can be reported as a clean refusal.

    Decision 9 separates "I refused before touching anything" (3) from "something happened and the
    result is partial or unknown" (4). Those are indistinguishable to an operator unless the
    producer tracks its own effects, so it records each one and escalates any later failure to
    EXIT_PARTIAL.

    WHERE each effect is recorded is the whole contract: at the instant it becomes true, never once
    the operation that caused it has returned successfully. A file exists from its `open` onward,
    so admitting its creation after the write completes leaves the failing case — created, not
    written — classified as though nothing had happened at all. A gate has RUN from its `Popen`
    onward, so admitting the run only once `wait` has returned classifies every failure while its
    output is still streaming the same way, on top of side effects already in the worktree.
    """

    def __init__(self) -> None:
        self.admitted: list[str] = []

    def admit(self, effect: str) -> int:
        """Record an effect at the moment it happens; the token allows only re-describing it."""
        self.admitted.append(effect)
        return len(self.admitted) - 1

    def revise(self, token: int, effect: str) -> None:
        """Sharpen an admitted effect's description. An effect can be re-described, never withdrawn.

        A file's creation must be admitted before its bytes exist, so its description has to be
        corrected once the outcome is known — fully written, removed, or still sitting there. What
        cannot change is THAT it happened: this rewrites one line and never removes one.
        """
        self.admitted[token] = effect

    def any(self) -> bool:
        return bool(self.admitted)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - exercised via subprocess
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise SystemExit(EXIT_USAGE)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="gate_receipt.py",
        description=(
            "Run a gate, capture its combined stdout+stderr, and write a self-hashing receipt. "
            "The receipt is evidence of whether a gate ran and what it returned; it authorizes "
            "nothing."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser(
        "record",
        help="run the gate argv after `--` and write one receipt",
        description=(
            "Run the gate argv given after `--`, then write one receipt. Tamper detection is by "
            "re-derivation, not a security boundary against the same OS user."
        ),
        epilog=(
            "Exit codes describe the PRODUCER, never the gate's own exit code (which lives in the "
            "receipt's `status`): 0 the gate passed and its receipt was written; 1 unexpected "
            "internal failure with no effect; 2 unusable arguments; 3 clean refusal before the "
            "gate ran and before any destination was created; 4 the gate ran, a destination was "
            "created, and/or bytes reached stdout, and then something failed, so the result is "
            "partial or unknown (a half-written file the producer created is removed, or named "
            "in the reason if it could not be); 5 the gate ran and "
            "failed; 6 a receipt was written but no verdict was observed. Read `outcome` in the "
            "receipt for the evidence. A receipt authorizes nothing."
        ),
    )
    record.add_argument("--gate", required=True, help='exact gate label, e.g. "mise run check"')
    record.add_argument(
        "--out",
        required=True,
        help="receipt destination path, or - for stdout. Required: there is no default destination.",
    )
    record.add_argument("--lock", default=None, help="mise.lock to bind (default: <cwd>/mise.lock)")
    record.add_argument(
        "--log",
        default=None,
        help="also persist the captured log bytes to this file path (`-` is not accepted)",
    )
    record.add_argument("--cwd", default=None, help="directory to run the gate in (default: current)")
    record.add_argument(
        "--unobserved",
        action="store_true",
        help="record that this gate was NOT run (status null, outcome unobserved); runs nothing",
    )
    record.add_argument("--quiet", action="store_true", help="do not mirror the gate's output to stderr")
    return parser


def _split_gate_argv(raw: list[str]) -> tuple[list[str], list[str]]:
    """Split the producer's own options from the gate argv at the first bare `--`."""
    if "--" not in raw:
        return raw, []
    index = raw.index("--")
    return raw[:index], raw[index + 1 :]


def _read_lock(cwd: Path, lock: str | None) -> bytes:
    path = Path(lock) if lock is not None else cwd / "mise.lock"
    try:
        return path.read_bytes()
    except OSError as exc:
        raise _ProducerError(
            f"cannot read toolchain lock {path}: {exc}", EXIT_REFUSED
        ) from exc


def _refuse_if_occupied(target: str | None) -> None:
    if target is None or target == "-":
        return
    if os.path.lexists(target):
        raise _ProducerError(f"refusing to overwrite existing evidence at {target}", EXIT_REFUSED)


def _refuse_if_one_destination_for_two_artifacts(out: str, log: str | None) -> None:
    """A receipt and a raw log cannot share one path; whichever landed second would be lost.

    Checked BEFORE the gate runs. Without it the producer creates the log itself, then refuses its
    own file with a message claiming pre-existing evidence — a false statement about a post-effect
    state, with raw log bytes left at the receipt's destination.
    """
    if log is None or out == "-" or log == "-":
        return
    resolved = os.path.realpath(out)
    if resolved == os.path.realpath(log):
        raise _ProducerError(
            f"--out and --log both resolve to {resolved}: one path cannot hold both the receipt "
            "and the raw log",
            EXIT_REFUSED,
        )


def _refuse_unless_creatable(target: str | None) -> None:
    """Refuse an uncreatable destination BEFORE the gate runs, so the receipt is not lost after it.

    A missing or unwritable parent directory is knowable up front. Discovering it after the gate
    has run turns a clean refusal into a lost receipt for work that already happened.
    """
    if target is None or target == "-":
        return
    parent = Path(target).parent
    if not parent.is_dir():
        raise _ProducerError(
            f"cannot create {target}: its parent directory {parent} does not exist", EXIT_REFUSED
        )
    if not os.access(parent, os.W_OK | os.X_OK):
        raise _ProducerError(
            f"cannot create {target}: its parent directory {parent} is not writable", EXIT_REFUSED
        )


def _discard_incomplete_file(target: str) -> bool:
    """Remove the producer's own half-written file. True iff the path is gone afterwards.

    Deleting it rather than keeping it as evidence, deliberately. The file is this run's aborted
    product, created moments earlier — not the third-party evidence `_refuse_if_occupied` protects,
    and there is no other writer whose bytes could be lost. Its content cannot verify either: a
    truncated canonical receipt has no re-derivable `self_digest`, and everything it would have said
    is already on stderr with the failure. Keeping it does active harm, because the destination is
    exclusive-create: a stray non-receipt blocks its own path permanently and the NEXT run refuses
    it as "existing evidence". Removal launders nothing — the creation stays an admitted effect, so
    the exit is EXIT_PARTIAL either way, and a removal that itself fails is named, not hidden.
    """
    try:
        os.unlink(target)
    except OSError:
        return not os.path.lexists(target)
    return True


def _write_new_file(target: str, data: bytes, *, effects: _Effects, what: str) -> None:
    """Create target exclusively and write data; an existing path is preserved, never clobbered.

    `effects` is required rather than optional because the destination EXISTS from the `os.open`
    onward: a write that fails after it is an admitted PARTIAL effect (Decision 9's 4), never an
    effect-free internal failure (1). The creation is therefore admitted HERE, where it happens,
    not by the caller once this returns — admitting it late is exactly how a truncated non-receipt
    ends up on disk under an exit code that promises nothing happened.

    Raises EXIT_INTERNAL, which `_report_failure` escalates to EXIT_PARTIAL through the effects it
    finds admitted. A pre-creation failure admits nothing and so stays a pre-effect failure.
    """
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise _ProducerError(
            f"{target} was created by something else after the pre-run check; preserving it",
            EXIT_INTERNAL,
        ) from exc
    except OSError as exc:
        raise _ProducerError(f"cannot create {target}: {exc}", EXIT_INTERNAL) from exc
    token = effects.admit(f"{target} was created for the {what}")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        disposition = (
            "the incomplete file was removed"
            if _discard_incomplete_file(target)
            else f"an INCOMPLETE file REMAINS at {target}"
        )
        effects.revise(token, f"{target} was created for the {what}, then {disposition}")
        raise _ProducerError(f"cannot write {target}: {exc}; {disposition}", EXIT_INTERNAL) from exc
    effects.revise(token, f"the {what} was written to {target}")


def _stderr_mirror(*, quiet: bool) -> Callable[[bytes], None]:
    """Resolve the display-only sink for the gate's captured bytes, BEFORE the gate starts.

    The mirror is a convenience `--quiet` switches off, never the evidence: every captured byte is
    hashed whether or not it is displayed. `main` is an importable entrypoint, so a caller whose
    `sys.stderr` is a TEXT stream is ordinary rather than exotic — `unittest --buffer` and
    `contextlib.redirect_stderr(io.StringIO())` each install one, and such a stream has no
    `.buffer`. Reaching for `.buffer` mid-run raised `AttributeError` after the gate had already
    run, so the shape of the sink is settled here, once, before anything runs, and a text stream is
    written as decoded text rather than made to fail.

    Undecodable bytes become replacement characters, and a read boundary can split a multi-byte
    sequence, so a text mirror may DISPLAY a character the byte mirror would not. Nothing is
    dropped, and `log_digest` is over the raw captured bytes either way, so no mirror — byte, text,
    or suppressed — can change what the receipt says.
    """
    if quiet:
        return lambda chunk: None
    stream = sys.stderr
    buffer = getattr(stream, "buffer", None)
    if buffer is None:

        def mirror_text(chunk: bytes) -> None:
            stream.write(chunk.decode("utf-8", "replace"))
            stream.flush()

        return mirror_text

    def mirror_bytes(chunk: bytes) -> None:
        buffer.write(chunk)
        buffer.flush()

    return mirror_bytes


def _run_gate(argv: list[str], cwd: Path, *, quiet: bool, effects: _Effects) -> tuple[int, bytes]:
    """Run the gate, streaming its merged output while capturing the exact bytes hashed.

    `effects` is required rather than optional because the gate HAS RUN from the moment `Popen`
    returns, not from the moment `wait` does: its side effects are already in the worktree while its
    output is still streaming. Every step in between can raise — the mirror, the read, `wait`
    itself — and admitting the run only once this function has returned classifies all of them as
    "nothing happened", which loses the receipt for work that provably occurred. The run is
    therefore admitted HERE, where it becomes true; guarding each raise site instead would leave
    the next one added to reintroduce the same defect.

    A gate that could not be STARTED never ran, so the failure below admits nothing and stays a
    pre-effect refusal.
    """
    mirror = _stderr_mirror(quiet=quiet)
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        raise FileNotFoundError(str(exc)) from exc
    # Nothing above this line has run the gate; nothing below it has not.
    effects.admit(f"the gate ran in {cwd}: {' '.join(argv)}")
    chunks: list[bytes] = []
    assert proc.stdout is not None
    with proc.stdout as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
            mirror(chunk)
    return proc.wait(), b"".join(chunks)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    own, gate_argv = _split_gate_argv(raw)
    parser = _build_parser()
    args = parser.parse_args(own)
    effects = _Effects()
    status: int | None = None
    try:
        if not gate_argv:
            raise _ProducerError(
                "the gate argv is required after `--`, e.g. `-- mise run check`", EXIT_USAGE
            )
        if args.log == "-":
            raise _ProducerError(
                "--log takes a file path, not `-`: the captured log is already mirrored to stderr "
                "unless --quiet, and interleaving raw log bytes with a receipt on stdout would "
                "corrupt both",
                EXIT_USAGE,
            )
        cwd = Path(args.cwd) if args.cwd is not None else Path.cwd()
        if not cwd.is_dir():
            raise _ProducerError(f"gate cwd is not a directory: {cwd}", EXIT_USAGE)
        cwd = cwd.resolve()
        lock_bytes = _read_lock(cwd, args.lock)
        _refuse_if_one_destination_for_two_artifacts(args.out, args.log)
        _refuse_if_occupied(args.out)
        _refuse_if_occupied(args.log)
        _refuse_unless_creatable(args.out)
        _refuse_unless_creatable(args.log)
        executed_argv: list[str] | None = None
        signal_number: int | None = None
        if args.unobserved:
            log_bytes = b""
            sys.stderr.write("gate not run: recording an unobserved receipt\n")
        else:
            try:
                raw_status, log_bytes = _run_gate(gate_argv, cwd, quiet=args.quiet, effects=effects)
            except FileNotFoundError as exc:
                # The gate could not be started, so it never ran: no argv is recorded as executed,
                # and recording an exit code would assert a verdict nobody observed.
                log_bytes = b""
                sys.stderr.write(f"gate could not be started ({exc}): recording an unobserved receipt\n")
            else:
                # The run itself was admitted inside `_run_gate`, at the `Popen` that made it true —
                # admitting it here instead would miss every failure while the output streamed.
                executed_argv = list(gate_argv)
                if raw_status < 0:
                    # Killed before it could return an exit code. It ran, but produced no verdict.
                    signal_number = -raw_status
                    sys.stderr.write(
                        f"gate was killed by signal {signal_number}: it produced no exit code, so "
                        "the receipt records no verdict\n"
                    )
                else:
                    status = raw_status
        receipt = build_receipt(
            gate=args.gate,
            argv=executed_argv,
            status=status,
            log_bytes=log_bytes,
            lock_bytes=lock_bytes,
            cwd=str(cwd),
            signal=signal_number,
        )
        payload = canonical_json(receipt) + b"\n"
        if args.log is not None:
            _write_new_file(args.log, log_bytes, effects=effects, what="captured gate log")
        if args.out == "-":
            try:
                sys.stdout.buffer.write(payload)
                sys.stdout.buffer.flush()
            except OSError as exc:
                # Bytes may already have reached the consumer, and how many is unknowable from
                # here, so this is an admitted effect on somebody else's stream — not a clean
                # internal failure. Admitting it before the write would claim an effect that had
                # not happened yet, so it is admitted at the failure, where the doubt begins.
                effects.admit("an unknown prefix of the receipt may already have reached stdout")
                raise _ProducerError(
                    f"cannot write the receipt to stdout: {exc}", EXIT_INTERNAL
                ) from exc
        else:
            _write_new_file(args.out, payload, effects=effects, what="receipt")
    except _ProducerError as exc:
        return _report_failure(str(exc), exc.code, effects)
    except Exception as exc:  # an unexpected failure must still classify its own effects
        return _report_failure(f"unexpected {type(exc).__name__}: {exc}", EXIT_INTERNAL, effects)
    if status is None:
        return EXIT_UNOBSERVED
    return EXIT_OK if status == 0 else EXIT_GATE_FAILED


def _report_failure(message: str, code: int, effects: _Effects) -> int:
    """Print the failure and return its effect-aware exit code.

    The single escalation point: once ANY effect is admitted, no failure may exit as a clean
    refusal or a pre-effect internal failure, because on disk the result is partial or unknown.
    """
    sys.stderr.write(f"gate_receipt.py: {message}\n")
    if effects.any():
        code = EXIT_PARTIAL
        sys.stderr.write("gate_receipt.py: this is a PARTIAL result, not a clean refusal:\n")
        for effect in effects.admitted:
            sys.stderr.write(f"gate_receipt.py:   already happened: {effect}\n")
    return code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(main())
