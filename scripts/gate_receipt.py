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

Every receipt also stamps the REPOSITORY HEAD its `cwd` was sitting on, as `head`. A receipt used
to be anchored to a path and a toolchain but to no point in the repository's history, so a
composer reading it beside another artifact could not tell whether the two were derived against the
same tree: `activation-result.py` recorded exactly that as a named residual, and
`agentic-sdlc-5ee7` is the seed that closed it. The anchor is head identity rather than a clock
because this host's clock legitimately steps backwards (agentic-sdlc-184b) while head identity is
deterministic. `head` is `{commit, tree}` or `null`, and `null` is a first-class answer: the `cwd`
is not a readable Git worktree, `git` is unavailable, or the head MOVED while the gate ran, in
which case no single head is the one this receipt measured and saying so is the honest record. The
tree comes from ONE `rev-parse <commit>^{tree}` derivation against the commit just read, never from
a second independent `rev-parse HEAD^{tree}`, so the pair cannot straddle a head that moved between
the two calls — the same atomic idiom `planning-snapshot.py` uses. Like `failures`, the field is
inside `self_digest`, so a stamp cannot be edited afterwards, and a receipt written before the
stamp existed carries no such key and still verifies.

`--harness unittest` additionally records WHICH tests failed, as the optional `failures` field. That
field is what makes a receipt a *baseline*: "exact non-worsening" is defined over the SET of named
failing tests (operator decision, 2026-08-17), and `scripts/gate_baseline.py` compares two of them.
A status or a count cannot express it — a wave that fixes one failure and breaks a different one
holds the count and flips the set, which is precisely what "exact" exists to catch. The field is
additive and absent unless requested, so receipts written before it existed keep verifying, and it
is inside `self_digest` like every other field, so a failure cannot be edited out afterwards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_UNOBSERVED = "unobserved"

#: The only harness whose output this producer can identify failures in.
HARNESS_UNITTEST = "unittest"
#: No failure identification was requested, so the receipt carries no `failures` field at all.
HARNESS_NONE = "none"
#: The failing set was read out of the harness's own report and is exact.
FAILURES_IDENTIFIED = "identified"
#: Identification was attempted and FAILED. Deliberately not spelled as an empty identified set: a
#: red gate whose failing set reads as empty makes every later subset comparison vacuously
#: non-worsening, which is the worst available outcome, so the receipt says "unknown" out loud.
FAILURES_UNPARSED = "unparsed"
FAILURE_STATES = (FAILURES_IDENTIFIED, FAILURES_UNPARSED)
#: The three keys a `failures` record carries — exactly these, always.
FAILURE_RECORD_KEYS = frozenset({"harness", "state", "names"})
#: The two keys a `head` stamp carries — exactly these, always.
HEAD_RECORD_KEYS = frozenset({"commit", "tree"})
#: A Git object name, in either of the two hash lengths Git writes (sha1 and sha256 repositories).
#: `[0-9a-f]` is spelled out rather than `\d`, which would also match every Unicode decimal digit.
_OBJECT_NAME = re.compile(r"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
#: Bounded, so a wedged `git` cannot hang the producer before its gate has even started.
_HEAD_TIMEOUT_SECONDS = 30

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


# --------------------------------------------------------------------------------------------
# Failure identities: WHICH tests failed, named stably enough to compare two runs as sets.
#
# A failing test is identified by its fully-qualified dotted test id — `module.Class.method` — and
# by nothing else. Three constraints pick that identity:
#
#   * A method name alone is ambiguous: two modules may both define `test_install`, and a set built
#     from bare names would silently merge them, so a fix in one would mask a break in the other.
#   * It must be stable across runs on the same tree. The dotted id is; a file path, a line number,
#     a duration, and a traceback are not.
#   * It must embed no mutable absolute path. This is not hypothetical: unittest prints subtest
#     parameters in the header, and a real one in this repository reads
#     `FAIL: test_many (m.C.test_many) (label='/tmp/moves/every/run')`. Those parameters are
#     therefore STRIPPED, which deliberately coarsens the identity to the test method: two subtests
#     of one method collapse to one name, so a wave that breaks one subtest while fixing another
#     *inside the same method* reads as non-worsening. That is a named limit of this identity, taken
#     because the alternative embeds temp paths and object addresses that change every run and would
#     make the same tree produce a different baseline each time.
#
# What is scraped is cross-checked against the harness's own tally, because a scrape that silently
# under-reports is indistinguishable from a green run. Anything the two disagree about is
# `unparsed`, never a shortened set. Two limits remain: a harness killed before it printed its
# summary contributes no headers and no tally, so its absence cannot be detected from its own
# missing output; and a task runner that prefixes each line makes the whole log unparseable rather
# than wrong. In both cases the gate's own `status` and `outcome` stay authoritative for redness.
# --------------------------------------------------------------------------------------------

#: `FAIL: test_a (m.C.test_a)`, `ERROR: setUpClass (m.C)`, `UNEXPECTED SUCCESS: test_a (m.C.test_a)`,
#: each optionally followed by subtest parameters in a second parenthesis.
_HEADER_PREFIXES = ("FAIL: ", "ERROR: ", "UNEXPECTED SUCCESS: ")
_HEADER = re.compile(r"^(?:FAIL|ERROR|UNEXPECTED SUCCESS): (\S+) \(([^()]*)\)(?: \(.*\))?$")
#: `OK`, `OK (skipped=13)`, `FAILED (failures=2, errors=1)`.
_SUMMARY = re.compile(r"^(?:OK|FAILED)(?: \((?P<tally>[^()]*)\))?$")
_TALLY_ITEM = re.compile(r"^(?P<key>[a-z][a-z ]*)=(?P<count>\d+)$")
#: An unexpected success is a non-pass that turns the run red, and unittest prints its name, so it
#: is counted here exactly like a failure or an error. `skipped` and `expected failures` are not
#: non-passes; note that a naive `failures=(\d+)` search would read `expected failures=1` as one.
_TALLY_NONPASS = frozenset({"failures", "errors", "unexpected successes"})
_TALLY_IGNORED = frozenset({"skipped", "expected failures"})
#: A dotted test id: at least two segments, each a Python identifier. Rejects paths, `::` selectors,
#: subtest parameters, and bare method names in one pattern.
_TEST_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")


def _header_identity(line: str) -> str | None:
    """The dotted test id a unittest failure header names, or None if it names none.

    Older CPython printed `FAIL: test_a (m.C)`; 3.11+ prints `FAIL: test_a (m.C.test_a)`; a class or
    module fixture prints `ERROR: setUpClass (m.C)`. One rule covers all three: append the leading
    word unless the parenthesised id already ends with it.
    """
    match = _HEADER.match(line)
    if match is None:
        return None
    leading, dotted = match.group(1), match.group(2)
    if not dotted:
        return None
    if dotted.split(".")[-1] != leading:
        dotted = f"{dotted}.{leading}"
    return dotted if _TEST_ID.match(dotted) else None


def _summary_nonpass_count(tally: str | None) -> int | None:
    """How many non-passes a summary line declares, or None if the line cannot be read exactly."""
    if not tally:
        return 0
    total = 0
    for item in tally.split(", "):
        match = _TALLY_ITEM.match(item)
        if match is None:
            return None
        key = match.group("key")
        if key in _TALLY_NONPASS:
            total += int(match.group("count"))
        elif key not in _TALLY_IGNORED:
            return None  # an unrecognised key may or may not be a non-pass: do not guess
    return total


def extract_unittest_failures(log_bytes: bytes) -> dict[str, Any]:
    """Read the failing set out of captured unittest output. A pure function of the bytes.

    Returns a ready-to-store `failures` record. `identified` means the scraped headers and the
    harness's own tally agree exactly — including on zero, which is what a green run looks like.
    Everything else is `unparsed` with an empty `names`, and the two are told apart by `state`, never
    by an empty list. Undecodable bytes are replaced rather than raised: the run still owes a
    receipt.
    """
    text = log_bytes.decode("utf-8", "replace")
    headers = 0
    declared = 0
    summaries = 0
    names: list[str] = []
    identifiable = True
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(_HEADER_PREFIXES):
            headers += 1
            identity = _header_identity(line)
            if identity is None:
                identifiable = False  # counted by the harness, nameable by nobody
            else:
                names.append(identity)
            continue
        summary = _SUMMARY.match(line)
        if summary is None:
            continue
        count = _summary_nonpass_count(summary.group("tally"))
        if count is None:
            identifiable = False
            continue
        summaries += 1
        declared += count
    if not identifiable or summaries == 0 or declared != headers:
        return {"harness": HARNESS_UNITTEST, "state": FAILURES_UNPARSED, "names": []}
    return {
        "harness": HARNESS_UNITTEST,
        "state": FAILURES_IDENTIFIED,
        "names": sorted(set(names)),
    }


def _normalized_failures(failures: dict[str, Any], argv: list[str] | None) -> dict[str, Any]:
    """Validate and canonicalize a `failures` record for storage, or raise ValueError.

    Order and duplicates are normalized the way `status` is coerced with `int()`: a caller mistake
    about presentation must not produce a receipt that fails its own verification. A mistake about
    CONTENT — an unknown state, a path-shaped identity, names beside `unparsed`, names with nothing
    executed — is raised instead, because silently storing it would produce exactly that
    unverifiable receipt.
    """
    if not isinstance(failures, dict) or set(failures) != FAILURE_RECORD_KEYS:
        raise ValueError(f"failures must carry exactly {sorted(FAILURE_RECORD_KEYS)}")
    harness = failures["harness"]
    state = failures["state"]
    raw_names = failures["names"]
    if not isinstance(harness, str) or not harness:
        raise ValueError("failures.harness must be a non-empty string")
    if state not in FAILURE_STATES:
        raise ValueError(f"failures.state must be one of {list(FAILURE_STATES)}")
    if isinstance(raw_names, str) or not isinstance(raw_names, Sequence):
        raise ValueError("failures.names must be a list of dotted test ids")
    names = sorted({str(name) for name in raw_names} if raw_names else set())
    for name in raw_names:
        if not isinstance(name, str) or not _TEST_ID.match(name):
            raise ValueError(f"failures.names holds a value that is not a dotted test id: {name!r}")
    if names and state != FAILURES_IDENTIFIED:
        raise ValueError("failures.names must be empty unless the failing set was identified")
    if names and argv is None:
        raise ValueError("failures.names cannot name a test when nothing was executed")
    return {"harness": harness, "state": state, "names": names}


#: An allowlist, not an inheritance: the head observation gets exactly this much ambient
#: environment. It matters more here than politeness
#: — an inherited `GIT_DIR` or `GIT_WORK_TREE` would silently re-point `rev-parse` at ANOTHER
#: repository while the receipt went on naming this `cwd`, which is the one way this stamp could lie
#: without anybody editing it.
_HEAD_PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def _git_object_name(cwd: Path, *arguments: str) -> str | None:
    """One bounded `git rev-parse` in `cwd`, or None when it did not yield one object name.

    Every failure is the same answer — None, "no head was observed" — because the alternatives are
    worse: raising would let a gate's own honest receipt be lost to a missing `git`, and inventing a
    value would stamp a head nothing read. A non-repository `cwd`, an unborn branch, an absent
    `git`, a wedged `git`, and non-UTF-8 output all land here.
    """
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell, bounded, allowlisted environment
            ["git", *arguments],
            cwd=str(cwd),
            capture_output=True,
            timeout=_HEAD_TIMEOUT_SECONDS,
            env={key: os.environ[key] for key in _HEAD_PASSTHROUGH_ENV if key in os.environ},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        text = done.stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    return text if _OBJECT_NAME.match(text) else None


def observe_repository_head(cwd: Path) -> dict[str, str] | None:
    """The `{commit, tree}` head identity of `cwd`, or None when no head could be observed.

    ONE derivation, not two: the tree is resolved from the commit this same call just read
    (`rev-parse <commit>^{tree}`) rather than by a second independent `rev-parse HEAD^{tree}`, so a
    head that moves between the two calls cannot produce a commit and a tree from different
    histories. A commit object names exactly one tree, so the pair is atomic by construction. This
    is `planning-snapshot.py`'s idiom, re-expressed rather than imported.
    """
    commit = _git_object_name(cwd, "rev-parse", "HEAD")
    if commit is None:
        return None
    tree = _git_object_name(cwd, "rev-parse", f"{commit}^{{tree}}")
    if tree is None:
        return None
    return {"commit": commit, "tree": tree}


def stable_repository_head(cwd: Path, observed: dict[str, str] | None) -> dict[str, str] | None:
    """Re-read the head and keep it only if it did not move; otherwise None.

    `observed` is the head read BEFORE the gate started. If the second read disagrees, the gate
    straddled a head change and no single head is the one it measured, so the receipt records
    `null` rather than picking the earlier or the later value. This is the same rule
    `planning-snapshot.py`'s seal applies, with the one difference the evidence posture forces: a
    snapshot may refuse, while this producer must still write the receipt for a gate that really
    ran.
    """
    if observed is None:
        return None
    return observed if observe_repository_head(cwd) == observed else None


def build_receipt(
    *,
    gate: str,
    argv: list[str] | None,
    status: int | None,
    log_bytes: bytes,
    lock_bytes: bytes,
    cwd: str,
    signal: int | None = None,
    failures: dict[str, Any] | None = None,
    head: dict[str, str] | None = None,
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
    - head: `{commit, tree}` for the repository head `cwd` was on, or null when no head was
      observed. It is what lets a composer refuse a receipt that was derived against a different
      tree from the artifacts beside it (agentic-sdlc-5ee7); `cwd` anchors WHERE, `toolchain_digest`
      anchors WHICH PINS, and this anchors WHEN in the repository's own history. Null is honest and
      not an error: a non-repository cwd, an absent `git`, or a head that moved during the run all
      record null, and a consumer that needs the anchor refuses the null rather than guessing.
    - failures: OPTIONAL, and ABSENT unless a caller asked for failure identification. When present
      it is `{harness, state, names}`: `state: identified` with the exact set of dotted test ids
      (empty for a green run), or `state: unparsed` with no names when the harness's output could
      not be read exactly. This is the field that makes a receipt a baseline; `unparsed` is not an
      empty failing set and must never be compared as one.
    - self_digest: sha256 of the canonical JSON of every other field — including `failures`, so a
      recorded failure cannot be edited out of a baseline afterwards.
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
        # Always present, unlike `failures`: an absent key means "written before this producer
        # stamped heads at all", while a present null means "this producer looked and observed
        # none". A consumer that needs the anchor has to tell those two apart to say anything
        # useful, so the shape says which one it is instead of collapsing both into absence.
        "head": None if head is None else {"commit": head["commit"], "tree": head["tree"]},
    }
    if failures is not None:
        # Absent unless requested: adding a key changes the digest of NEW receipts only, so every
        # receipt written before this field existed still re-derives.
        body["failures"] = _normalized_failures(failures, body["argv"])
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


def _failures_are_consistent(body: dict[str, Any]) -> bool:
    """True iff a stored `failures` record is one this producer could honestly have written.

    A set is only comparable if it is well-formed, so the invariants are the comparison's floor:
    exactly the three keys, a known state, canonically ordered unique dotted ids, no names beside
    `unparsed`, and no names at all when `argv` says nothing was executed.
    """
    failures = body.get("failures")
    if not isinstance(failures, dict) or set(failures) != FAILURE_RECORD_KEYS:
        return False
    harness, state, names = failures["harness"], failures["state"], failures["names"]
    if not isinstance(harness, str) or not harness:
        return False
    if state not in FAILURE_STATES:
        return False
    if not isinstance(names, list):
        return False
    if not all(isinstance(name, str) and _TEST_ID.match(name) for name in names):
        return False
    if names != sorted(set(names)):
        return False  # canonical order and uniqueness: a set, stored deterministically
    if names and state != FAILURES_IDENTIFIED:
        return False  # `unparsed` is not a short failing set
    if names and body.get("argv") is None:
        return False  # nothing executed, yet a failing test is named
    return True


def _head_is_consistent(body: dict[str, Any]) -> bool:
    """True iff a stored `head` stamp is one this producer could honestly have written.

    Null is valid — it is how "no head was observed" is said. Anything else must be exactly
    `{commit, tree}` with both values Git object names, because a consumer that refuses on
    disagreement has to be able to rely on the shape it is comparing: a stamp of `{"commit": true}`
    would otherwise compare unequal to every honest stamp and be reported as a moved head rather
    than as a malformed one.
    """
    head = body.get("head")
    if head is None:
        return True
    if not isinstance(head, dict) or set(head) != HEAD_RECORD_KEYS:
        return False
    return all(isinstance(head[key], str) and _OBJECT_NAME.match(head[key]) for key in sorted(HEAD_RECORD_KEYS))


def verify_receipt(receipt: dict[str, Any]) -> bool:
    """True iff self_digest re-derives, outcome agrees with status, and the state is honest.

    Receipts written before `outcome` existed carry no such field and still verify: the digest is
    re-derived over whatever non-self_digest fields are present, so the added fields change the
    digest of NEW receipts only, and the state invariants apply only where `outcome` is present.
    `failures` is scoped the same way — its invariants bind receipts that CARRY it, and its absence
    is an honest receipt that simply is not a baseline. `head` is scoped the same way again: its
    absence is a receipt written before heads were stamped, and a consumer that needs the anchor
    refuses it by name rather than reading the absence as agreement.
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
    if "failures" in body and not _failures_are_consistent(body):
        return False
    if "head" in body and not _head_is_consistent(body):
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
        # The usage goes through the guarded sink too, rather than through argparse's own
        # `print_usage`: argparse swallows the failed write, but the bytes it leaves pending are
        # enough for the interpreter's shutdown flush to replace this usage error's 2 with 120.
        note = advisory_stderr()
        note(self.format_usage())
        note(f"{self.prog}: error: {message}\n")
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
        "--harness",
        choices=(HARNESS_NONE, HARNESS_UNITTEST),
        default=HARNESS_NONE,
        help=(
            "identify WHICH tests failed from the captured output and record them as `failures`, "
            "making this receipt a baseline for scripts/gate_baseline.py. Default `none` records no "
            "such field. An output that cannot be read exactly is recorded as `unparsed`, never as "
            "an empty failing set."
        ),
    )
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


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter from retrying a write this process has ALREADY reported as failed.

    Catching the write is not enough by itself. A failed `write`/`flush` leaves those bytes PENDING
    in the stream's buffer, and CPython flushes `sys.stdout` and `sys.stderr` once more while
    finalizing; that second failure replaces the process's exit code with 120 — outside this
    module's closed exit set entirely, so the honest code the caller computed never reaches the
    shell. Measured on CPython 3.12.11: a receipt written to a broken pipe printed the correct
    PARTIAL classification and exited 4, and the shell still saw 120.

    Dropping the module attribute is how CPython itself represents a stream this process does not
    have — `2>&-` starts the interpreter with `sys.stderr is None` — and it loses no byte that was
    not already lost, because the write that would have carried them is the one that failed. The
    identity check is load-bearing: `main` is importable, so the current `sys.stdout`/`sys.stderr`
    may belong to a caller who swapped it, and only the stream that actually failed may be dropped.
    `sys.__stdout__`/`sys.__stderr__` still reference it either way.
    """
    if getattr(sys, name, None) is stream:
        setattr(sys, name, None)


def _flush_of(stream: object) -> Callable[[], Any]:
    """The stream's own `flush`, or a no-op when it has none.

    Flushing is what makes a broken channel announce itself HERE, while its failure can still be
    contained, instead of during finalization where it becomes exit 120 — so it is not optional
    where it exists. But `write` without `flush` is a shape a caller may hand an importable `main`,
    and it worked before these lines were guarded, so its absence must not become a new way to lose
    a receipt: that would trade one display-channel defect for another.
    """
    flush = getattr(stream, "flush", None)
    return flush if callable(flush) else (lambda: None)


def _guarded_stderr_sink(
    stream: object, write: Callable[[Any], Any], flush: Callable[[], Any]
) -> Callable[[Any], None]:
    """Wrap an ALREADY-SETTLED display sink so a failed write costs the channel, never the verdict.

    A display channel is allowed to fail. What it may not do is destroy the mandatory artifact or
    corrupt the exit signal, so the first failure retires the channel — silently, because there is
    by definition nowhere left to report it — and every later line is a no-op.
    """
    live = [True]

    def emit(payload: Any) -> None:
        if not live[0]:
            return
        try:
            write(payload)
            flush()
        except (OSError, ValueError):  # EPIPE/ENOSPC, or a stream closed underneath us
            live[0] = False
            abandon_broken_stream("stderr", stream)

    return emit


def advisory_stderr() -> Callable[[str], None]:
    """Settle the display-only sink for this module's own LINES, and drop it if a write fails.

    The rule `_stderr_mirror` states, applied to every advisory line these entrypoints write — the
    running notes and the failure report itself: the channel is a convenience, never the evidence,
    so it may neither destroy the mandatory artifact nor change the exit code. Two hostile shapes
    exist and neither is exotic. `2>&-` leaves CPython with `sys.stderr is None`, so the very first
    `sys.stderr.write` raises `AttributeError`; a reader that goes away makes every write `EPIPE`.
    Both used to land in `main`'s `except Exception`, whose reporter OPENED with another
    `sys.stderr.write` and raised again — so `record` against a red gate that HAD RUN exited 1 with
    no receipt at all, and the same run down a broken pipe exited 120.

    `scripts/gate_baseline.py` shares this sink rather than growing a second copy of the rule.
    """
    stream = sys.stderr
    if stream is None:  # `2>&-`: this process was handed no stderr to be advisory on
        return lambda line: None
    return _guarded_stderr_sink(stream, stream.write, _flush_of(stream))


def _stderr_mirror(*, quiet: bool) -> Callable[[bytes], None]:
    """Resolve the display-only sink for the gate's captured bytes, BEFORE the gate starts.

    The mirror is a convenience `--quiet` switches off, never the evidence: every captured byte is
    hashed whether or not it is displayed. `main` is an importable entrypoint, so a caller whose
    `sys.stderr` is a TEXT stream is ordinary rather than exotic — `unittest --buffer` and
    `contextlib.redirect_stderr(io.StringIO())` each install one, and such a stream has no
    `.buffer`. Reaching for `.buffer` mid-run raised `AttributeError` after the gate had already
    run, so the shape of the sink is settled here, once, before anything runs, and a text stream is
    written as decoded text rather than made to fail.

    Settling the SHAPE is not enough on its own, because the write can fail for reasons no shape
    check can see: the mirror runs inside the window where the gate has already run, so an `EPIPE`
    there used to strand the receipt for work that provably happened. The writes are therefore
    guarded as well — a mirror that dies is dropped and the run continues to its receipt.

    Undecodable bytes become replacement characters, and a read boundary can split a multi-byte
    sequence, so a text mirror may DISPLAY a character the byte mirror would not. Nothing is
    dropped, and `log_digest` is over the raw captured bytes either way, so no mirror — byte, text,
    suppressed, or retired mid-run — can change what the receipt says.
    """
    if quiet:
        return lambda chunk: None
    stream = sys.stderr
    if stream is None:  # `2>&-`: there is nothing to mirror to, which is not a failure
        return lambda chunk: None
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return _guarded_stderr_sink(
            stream, lambda chunk: stream.write(chunk.decode("utf-8", "replace")), _flush_of(stream)
        )
    return _guarded_stderr_sink(stream, buffer.write, _flush_of(buffer))


_REAP_GRACE_SECONDS = 5.0


def _reap_abandoned_gate(
    proc: subprocess.Popen[bytes], *, ran: str, token: int, effects: _Effects
) -> None:
    """Reap a gate child abandoned by an exception, in BOUNDED time, changing no verdict.

    THE DECISION, because the obvious fix is the wrong one. An unreaped child costs a file handle
    and a `ResourceWarning: subprocess N is still running` raised from `__del__` — which no test can
    fail on and which changes no exit code and no receipt field. An UNBOUNDED `proc.wait()` in a
    `finally` costs something worse: this producer wraps an eleven-minute gate, so a gate that
    ignores `SIGPIPE` and keeps writing after we closed its pipe would park the failure report here
    for as long as it likes, and a hung producer is indistinguishable from a slow gate. The leak is
    visible and bounded; the hang is invisible and unbounded. So the wait is bounded and escalates.

    Three stages, each capped at `_REAP_GRACE_SECONDS`, for a ceiling of 15s added to a failure that
    is already unwinding: poll (the usual case — closing the pipe already ended it), then `SIGTERM`,
    then `SIGKILL`. `SIGKILL` cannot be ignored, so the last wait is bounded in practice and capped
    anyway for the uninterruptible-sleep case; if even that times out the child is reported as
    possibly still running, which is the leak we started with plus an honest sentence about it.

    WHAT THIS DOES NOT DO, and the comment exists so nobody reads more into it: it signals the direct
    child only. A gate like `mise run check` is a process tree, and killing its root can orphan
    grandchildren that keep running. Signalling the group is NOT an option here — the child is not
    put in its own session or process group, so `killpg` would hit this process and the operator's
    own shell with it. Bounding OUR wait is the whole claim.

    WHAT HAPPENS TO THE RECEIPT: nothing, and that is deliberate. This runs only while an exception
    is already propagating out of `_run_gate`, so `_run_gate` never returns a status and no receipt
    is written at all; `main` classifies the run as an admitted effect and exits `EXIT_PARTIAL`. The
    module's killed-gate receipt shape (`status: null`, `signal: N`, `outcome: unobserved`) is NOT
    reused for a signal WE sent: that shape records a negative `wait` status observed for the gate's
    own death, and writing our own `SIGKILL` into it would forge an observation. What the operator
    gets instead is the already-admitted effect, re-described through `effects.revise`, so the
    exit-4 report says the gate ran AND how it was ended. Reaping is cleanup: it may not raise, may
    not replace the in-flight exception, and may not change the exit code, so every failure here —
    including a second `KeyboardInterrupt` landing inside a bounded wait — is swallowed.
    """
    if proc.returncode is not None:  # `wait` already returned: there is nothing left to reap
        return
    try:
        if proc.poll() is not None:
            # It had already exited and this poll reaped it. No signal was sent, so there is no new
            # effect to describe: the admitted "the gate ran" line is still exactly true.
            return
        for send, sent in ((None, ""), (proc.terminate, "SIGTERM"), (proc.kill, "SIGKILL")):
            if send is not None:
                send()
            try:
                proc.wait(timeout=_REAP_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                continue
            if sent:
                effects.revise(
                    token,
                    f"{ran}; it was still running when this producer failed, so it was ended with "
                    f"{sent} and its verdict was never observed",
                )
            return
        effects.revise(
            token,
            f"{ran}; it was still running when this producer failed and survived SIGKILL for "
            f"{_REAP_GRACE_SECONDS:g}s, so it MAY STILL BE RUNNING",
        )
    except BaseException:  # cleanup may not become the failure it was cleaning up after
        return


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

    Every one of those raise sites also abandons a RUNNING child, so the child is reaped in a
    `finally` — bounded, and never able to raise. `_reap_abandoned_gate` argues that choice against
    the hang it would be if the wait were unbounded.
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
    ran = f"the gate ran in {cwd}: {' '.join(argv)}"
    token = effects.admit(ran)
    try:
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
    finally:
        _reap_abandoned_gate(proc, ran=ran, token=token, effects=effects)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    own, gate_argv = _split_gate_argv(raw)
    parser = _build_parser()
    args = parser.parse_args(own)
    effects = _Effects()
    # Settled once, before anything runs, and never able to fail afterwards: these notes are
    # display, and the receipt below is the evidence. See `advisory_stderr`.
    note = advisory_stderr()
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
        # Read here, beside the toolchain pin and BEFORE the gate starts, because both answer the
        # same question about the same moment: what this gate is about to be run against.
        head_before = observe_repository_head(cwd)
        _refuse_if_one_destination_for_two_artifacts(args.out, args.log)
        _refuse_if_occupied(args.out)
        _refuse_if_occupied(args.log)
        _refuse_unless_creatable(args.out)
        _refuse_unless_creatable(args.log)
        executed_argv: list[str] | None = None
        signal_number: int | None = None
        if args.unobserved:
            log_bytes = b""
            note("gate not run: recording an unobserved receipt\n")
        else:
            try:
                raw_status, log_bytes = _run_gate(gate_argv, cwd, quiet=args.quiet, effects=effects)
            except FileNotFoundError as exc:
                # The gate could not be started, so it never ran: no argv is recorded as executed,
                # and recording an exit code would assert a verdict nobody observed.
                log_bytes = b""
                note(f"gate could not be started ({exc}): recording an unobserved receipt\n")
            else:
                # The run itself was admitted inside `_run_gate`, at the `Popen` that made it true —
                # admitting it here instead would miss every failure while the output streamed.
                executed_argv = list(gate_argv)
                if raw_status < 0:
                    # Killed before it could return an exit code. It ran, but produced no verdict.
                    signal_number = -raw_status
                    note(
                        f"gate was killed by signal {signal_number}: it produced no exit code, so "
                        "the receipt records no verdict\n"
                    )
                else:
                    status = raw_status
        failures: dict[str, Any] | None = None
        if args.harness == HARNESS_UNITTEST:
            failures = extract_unittest_failures(log_bytes)
            if failures["state"] != FAILURES_IDENTIFIED:
                # Said at record time, where it is still cheap to fix, rather than left for the
                # comparison to discover. The receipt is still written: it is honest evidence that
                # this gate ran and that its failing set is unknown.
                note(
                    "no failing test could be identified in the captured unittest output: "
                    "recording an unparsed failing set, which no baseline comparison will accept\n"
                )
        # THE ANCHOR, re-read last: a head that moved while the gate ran leaves no single head this
        # receipt measured, so the stamp becomes null and the note says so out loud rather than
        # letting a consumer bind this verdict to a tree it did not run against.
        head = stable_repository_head(cwd, head_before)
        if head_before is not None and head is None:
            note(
                "the repository head moved while the gate ran, so no single head is the one this "
                "receipt measured: recording a null head stamp\n"
            )
        receipt = build_receipt(
            gate=args.gate,
            argv=executed_argv,
            status=status,
            log_bytes=log_bytes,
            lock_bytes=lock_bytes,
            cwd=str(cwd),
            signal=signal_number,
            failures=failures,
            head=head,
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
                # Admitted first, then abandoned: the classification below is worthless if the
                # interpreter's shutdown flush of the same broken stream overwrites its exit code.
                abandon_broken_stream("stdout", sys.stdout)
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

    Reporting is a display act and the returned code is the evidence, so the sink is settled before
    the first line rather than reached for per write. This function used to OPEN with a bare
    `sys.stderr.write`, which made it the one place a broken stderr could not be reported from: the
    write raised on its way out of `except Exception`, nothing below ran, and the classification it
    exists to produce never reached the caller.
    """
    note = advisory_stderr()
    note(f"gate_receipt.py: {message}\n")
    if effects.any():
        code = EXIT_PARTIAL
        note("gate_receipt.py: this is a PARTIAL result, not a clean refusal:\n")
        for effect in effects.admitted:
            note(f"gate_receipt.py:   already happened: {effect}\n")
    return code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(main())
