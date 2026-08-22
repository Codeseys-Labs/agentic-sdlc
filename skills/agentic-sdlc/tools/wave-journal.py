#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""The append-only wave journal: what each node in one wave actually did.

Issue 07 says "a wave journal records each node's inputs, outputs, assignment, timestamps, result,
and evidence", that a wave is complete only when "every required node has an admitted success,
approved skip, or explicit blocked disposition", and that "budgets, retries, plan revisions, and
approvals" are traceable. This module owns that record and nothing else: it does not decide whether
a wave is complete, it does not spawn, it does not gate, and it authorizes no outward effect.

THE JOURNAL IS THE EVIDENCE, THE PROJECTION IS NOT A VERDICT. `project` publishes facts -- the
required-node set declared at `init`, each node's single disposition with the entry that established
it, every budget, retry, plan revision, and approval -- and deliberately publishes no `complete`,
`accepted`, or `condition_1` field. The downstream verdict tool DERIVES completion from those facts.
A summary boolean here would become the thing that gets trusted, and then the journal would only
have to be self-consistent rather than true.

ON-DISK FORM. One canonical JSON object per line, in append order, and the file only ever grows:

    line 0  {"kind":"wave-opened", "seq":0, "at":<caller time>, "record":{...}, "schema":...}
    line N  {"kind":<entry kind>, "seq":N, "at":<caller time>, "prev_digest":<sha256 of line N-1>,
             "record":{...}, "schema":...}

Every line is `sort_keys=True, separators=(",",":"), ensure_ascii=True` with exactly one trailing
newline, so the file's bytes are a function of its contents alone and any two producers agree. Each
line carries the schema tag, so one extracted line is self-describing. `prev_digest` chains the
lines, and `read` recomputes the whole chain plus each line's canonical form: a line edited in place,
reordered, or removed is a refusal rather than a projection. The caller's payload is NESTED under
`record` rather than flattened into the envelope, so no future payload field can collide with `seq`,
`at`, `kind`, `prev_digest`, or `schema`.

NO CLOCK. Every timestamp is a caller input (`--at`, and each node's own `started_at`/`ended_at`).
This is not a style choice. Seed agentic-sdlc-184b measured this project's WSL2 host stepping
CLOCK_REALTIME BACKWARDS by 0.22-0.53s, which already broke one monotonicity check elsewhere in the
repository; a journal that read its own clock would refuse its own honest sequence at random and
would be untestable besides. The tool instead refuses a supplied sequence that goes backwards, by
name. The value is that the CALLER owns the sequence and this module owns only its consistency.

EFFECT ADMISSION, which is the part this project has got wrong six times. An effect is recorded at
the instant it becomes true, never once the operation that caused it has returned successfully. So
admission lives inside the primitives that mutate -- `_write_new_at`'s own `os.open`, and
`_renameat2_at`'s syscall -- and never at the call sites that use them; `_report_failure` is the one
place any refusal's status, code, and effect are settled, by reading the ledger; and no raise site
may state an effect, because `_result` has no default for it. A partial append (the journal moved,
or a staging file created and then abandoned) is exit 4 with the effect named, never a clean refusal.
Removing an abandoned staging file launders nothing: the creation stays admitted, so the exit is 4
either way, and a removal that itself fails is named rather than hidden.

EXIT CONTRACT (Implementation Decision 9), per verb rather than in the abstract:

    0  success, or an exact no-effect
    1  an internal failure before any effect
    2  the invocation's grammar, or the supplied record's schema, is invalid
    3  a clean refusal before any effect -- the journal's state does not admit this record
    4  an admitted partial or unknown effect

`init` and the five `record-*` verbs can reach all five. `project` opens nothing for writing, creates
no file, renames nothing and removes nothing, so it cannot reach 4 through a durable effect at all;
its ONLY route to 4 is a stdout write that fails part-way, which is an admitted effect on the
caller's own stream (an unknown prefix may already have been consumed) and is reported as such
rather than as a clean read. 3 stays reachable for `project` because a journal it will not project --
absent, not a regular file, chain-broken -- is a refusal it makes before writing anything.

A DISPLAY CHANNEL MAY NOT COST A VERDICT. `sys.stderr` here is advisory: `2>&-` leaves CPython with
`sys.stderr is None` so the first write raises `AttributeError`, and a reader that goes away makes
every write EPIPE *and* leaves bytes pending that the interpreter flushes again while finalizing --
replacing the honest exit code with 120, which is outside the closed set above. The sink is therefore
settled once, guarded, and retired on its first failure, and the failed stream is dropped so the
shutdown flush cannot retry it. `scripts/gate_receipt.py` and `scripts/release_candidate_acquisition.py`
landed this same rule; it is RE-EXPRESSED here rather than imported, because these tools are
standalone scripts loaded by absolute path (this one's name has a hyphen in it and cannot be
imported at all), and importing across them to reach a display helper would drag one tool's side
conditions into another's.

WHAT AN APPROVAL MAY BIND, AND WHAT BINDING BUYS. An approval entry may name the exact
`prestate_digest` and `candidate_digest` it authorizes -- sha256 over the target prestate the grant
was reviewed against and over the candidate it authorizes -- and this module validates their SHAPE
and nothing else: 64 lowercase hex, or the field left out entirely. It observes no tree and hashes
no candidate, so it cannot know whether either digest describes anything real; what it does is make
the claim EXACT, so `wave-verdict.py`'s condition 5 can compare it against the prestate and
candidate a caller actually observed and refuse a grant that names different bytes. Both fields are
OPTIONAL and independent: a journal written before they existed carries neither, keeps exactly the
free-form authority this module has always recorded, and stays readable, because this journal is
append-only evidence and a rule that made old lines inadmissible would destroy the record it exists
to keep. Absent is the one spelling of "this grant binds nothing": an explicitly null or empty
`prestate_digest` is refused by name rather than read as unbound, because two spellings of one fact
are two canonical forms and two digests of the same grant.

WHAT THIS IS NOT. A recorded approval is a same-user assertion, not an authenticated one: every
approval entry is stamped `"authenticated":false` by this module, and a caller may not supply that
field. A digest-bound approval is the same assertion made exact -- binding narrows what a grant can
later be claimed to have authorized, and authenticates nobody. A recorded budget, retry, or plan
revision is bookkeeping the conductor must choose to obey;
nothing here can stop a dispatch. Concurrent appends to one journal from two processes are
unsupported, and this is exactly what unsupported is allowed to mean here: the live file's identity
(device, inode, size, content digest) is bound by the read the successor was built from and
RE-COMPARED immediately before the rename that would replace it, so another writer's COMMITTED append
is refused at exit 4 rather than silently overwritten. That is detection, not prevention: nothing
locks, and a writer that commits inside the gap between that comparison and the rename is still lost.
The comparison is deliberately not on mtime -- see `_read_regular_at`.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

JOURNAL_SCHEMA = "agentic-sdlc/wave-journal@1"
RESULT_SCHEMA = "agentic-sdlc/wave-journal-result@1"
PROJECTION_SCHEMA = "agentic-sdlc/wave-journal-projection@1"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2
EXIT_REFUSED = 3
EXIT_PARTIAL = 4

EFFECT_NONE = "none"
EFFECT_UNKNOWN = "effect_unknown"

KIND_OPENED = "wave-opened"
KIND_NODE = "node"
KIND_BUDGET = "budget"
KIND_RETRY = "retry"
KIND_PLAN_REVISION = "plan-revision"
KIND_APPROVAL = "approval"

# Issue 07's three, and only three, terminal node states. Spelled as the issue spells them so the
# journal's vocabulary is greppable against the contract that produced it.
DISPOSITIONS = ("admitted-success", "approved-skip", "blocked")
# Issue 07's roles. A closed set, because an unrecognised role in a journal is either a typo or a
# role nobody agreed to, and both are worth a refusal.
ROLES = ("cartographer", "conductor", "critic", "implementer", "integrator", "planner", "researcher", "reviewer")
MODES = ("static-dag", "recursive", "auto")
CAPABILITIES = ("read-only", "write-capable")
PRIOR_EFFECTS = (EFFECT_NONE, EFFECT_UNKNOWN)
BUDGET_SCOPES = ("mission", "node", "wave")
BUDGET_UNITS = ("nodes", "retries", "seconds", "tokens", "usd")
RESOLUTION_STATES = ("inherited", "requested", "resolved", "unresolved")

STAGING_SUFFIX = ".next"
_RENAME_NOREPLACE = 1

_TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

_LIBC = ctypes.CDLL(None, use_errno=True)

# One bounded test seam. It can only make the tool FAIL at a named point; it cannot skip a check,
# widen authority, or write anything the ordinary path would not have written. It exists because the
# effect-admission rule is only worth anything if a failure AFTER each admitted effect can actually
# be driven, and no mock can reach a subprocess.
FAULT_ENV = "AGENTIC_SDLC_WAVE_JOURNAL_FAULT"
FAULT_POINTS = (
    "before-staging-open",
    "after-staging-open",
    "after-staging-write",
    "after-staging-readback",
    "after-rename",
    "after-publish-readback",
)


class JournalError(Exception):
    """A refusal or failure of this tool. `code` is required; the effect is NEVER a parameter.

    A raise site states what went wrong and how severe the CAUSE is. What it may not state is what
    already happened on disk, because that is what the site cannot know and what every previous
    instance of this defect got wrong. `_report_failure` derives the effect from the ledger.
    """

    def __init__(self, status: str, reason: str, code: int) -> None:
        super().__init__(reason)
        self.status, self.reason, self.code = status, reason, code


class _Effects:
    """What THIS invocation has already done, so no refusal can be reported as no effect.

    Decision 9 separates "I refused before touching anything" (3) from "something happened and the
    result is partial or unknown" (4). Those are indistinguishable to an operator unless the tool
    tracks its own effects, so it records each one and escalates any later refusal.

    WHERE each effect is recorded is the whole contract. A staging file exists from its `os.open`
    onward, so admitting its creation after the write completes leaves the failing case -- created,
    not written -- classified as though nothing had happened. The journal has MOVED from the instant
    `renameat2` returns 0, so admitting publication after the readback that follows it classifies a
    failed readback as though the record were still private. Admission therefore lives in
    `_write_new_at` and `_renameat2_at`, not in the append flow that calls them, which is what makes
    the next mutating step admit its effect for free instead of relying on somebody remembering.
    """

    def __init__(self) -> None:
        self.admitted: list[str] = []

    def admit(self, effect: str) -> int:
        """Record an effect at the moment it happens; the token allows only re-describing it."""
        self.admitted.append(effect)
        return len(self.admitted) - 1

    def revise(self, token: int, effect: str) -> None:
        """Sharpen an admitted effect's description. It can be re-described, never withdrawn."""
        self.admitted[token] = effect

    def any(self) -> bool:
        return bool(self.admitted)


_EFFECTS = _Effects()


@contextlib.contextmanager
def _effect_ledger() -> Iterator[_Effects]:
    """Install one fresh ledger for one command invocation, then restore the previous one.

    Module-scoped rather than threaded through every helper, for the same reason the planner's is:
    effects are admitted several frames below the handler, and a parameter is exactly the
    bookkeeping a future helper forgets. Restoring rather than clearing keeps a test that drives two
    commands in one process from erasing the outer command's admitted effects.
    """
    global _EFFECTS
    previous = _EFFECTS
    _EFFECTS = _Effects()
    try:
        yield _EFFECTS
    finally:
        _EFFECTS = previous


def _admit(effect: str) -> int:
    return _EFFECTS.admit(effect)


def _revise(token: int, effect: str) -> None:
    _EFFECTS.revise(token, effect)


def canonical_bytes(value: Any) -> bytes:
    """Sorted, tight, ASCII, exactly one trailing newline. One line of the journal, or one result."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fault(point: str) -> None:
    """Fail at `point` when the environment names it, as `<point>` or `<point>:<code>`.

    The requested code is what proves the escalation is real: a site asking for 3 (a clean refusal)
    or 2 (a schema verdict) after an effect has been admitted must still come out as 4, and the same
    request BEFORE any effect must come out unchanged. One mechanism, both directions.
    """
    raw = os.environ.get(FAULT_ENV)
    if not raw:
        return
    name, _, requested = raw.partition(":")
    if name != point:
        return
    if name not in FAULT_POINTS:
        raise JournalError("invalid", f"unknown fault point {name!r}", EXIT_INPUT)
    code = int(requested) if requested else EXIT_INTERNAL
    raise JournalError("injected-fault", f"injected fault at {point}", code)


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter from retrying a write this process has ALREADY reported as failed.

    Catching the write is not enough. A failed write leaves those bytes PENDING in the stream's
    buffer, and CPython flushes `sys.stdout`/`sys.stderr` again while finalizing; that second failure
    replaces the process's exit code with 120 -- outside this module's closed exit set, so the honest
    code never reaches the caller. Dropping the module attribute is how CPython itself represents a
    stream this process does not have (`2>&-` starts the interpreter with `sys.stderr is None`), and
    it loses no byte that was not already lost with the write that failed. The identity check is
    load-bearing: only the stream that actually failed may be dropped.
    """
    if getattr(sys, name, None) is stream:
        setattr(sys, name, None)


def _flush_of(stream: object) -> Callable[[], Any]:
    """The stream's own `flush`, or a no-op when it has none.

    Flushing is what makes a broken channel announce itself HERE, where its failure can still be
    contained, instead of during finalization where it becomes exit 120.
    """
    flush = getattr(stream, "flush", None)
    return flush if callable(flush) else (lambda: None)


def _guarded_sink(stream: object, name: str, write: Callable[[Any], Any], flush: Callable[[], Any]) -> Callable[[Any], None]:
    """Wrap an already-settled display sink so a failed write costs the channel, never the verdict.

    The first failure retires the channel -- silently, because there is by definition nowhere left to
    report it -- and every later line is a no-op.
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
            abandon_broken_stream(name, stream)

    return emit


def advisory_stderr() -> Callable[[str], None]:
    """Settle the display-only sink for this module's own lines, and drop it if a write fails."""
    stream = sys.stderr
    if stream is None:  # `2>&-`: this process was handed no stderr to be advisory on
        return lambda line: None
    return _guarded_sink(stream, "stderr", stream.write, _flush_of(stream))


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - exercised via subprocess
        # Through the guarded sink rather than argparse's own `print_usage`: argparse swallows the
        # failed write, but the bytes it leaves pending are enough for the shutdown flush to replace
        # this usage error's 2 with 120.
        note = advisory_stderr()
        note(self.format_usage())
        note(f"{self.prog}: error: {message}\n")
        raise SystemExit(EXIT_INPUT)


def _emit(payload: dict[str, Any], *, mandatory: bool) -> None:
    """Write one canonical document to stdout.

    `mandatory` separates the two callers. On the success path the document IS the answer, so a
    part-written one is an admitted effect on the caller's stream and must be classified. On the
    failure path the exit code is already the answer and the document is display, so a failed write
    retires the channel and changes nothing -- reporting the loss of a report has nowhere to go.
    """
    stream = sys.stdout
    if stream is None:  # `1>&-`: there is nothing to write to
        return
    data = canonical_bytes(payload)
    buffer = getattr(stream, "buffer", None)
    if not mandatory:
        sink = (
            _guarded_sink(stream, "stdout", lambda chunk: stream.write(chunk.decode("utf-8")), _flush_of(stream))
            if buffer is None
            else _guarded_sink(stream, "stdout", buffer.write, _flush_of(buffer))
        )
        sink(data)
        return
    try:
        if buffer is None:
            stream.write(data.decode("utf-8"))
            stream.flush()
        else:
            buffer.write(data)
            buffer.flush()
    except (OSError, ValueError) as exc:
        # How many bytes reached the consumer is unknowable from here, so this is an admitted effect
        # on somebody else's stream. Admitted at the failure, where the doubt begins -- admitting it
        # before the write would claim an effect that had not happened yet.
        _admit("an unknown prefix of the result document may already have reached stdout")
        # Admitted first, then abandoned: the classification is worthless if the shutdown flush of
        # the same broken stream overwrites the exit code with 120.
        abandon_broken_stream("stdout", stream)
        raise JournalError("effect-unknown", f"cannot write the result to stdout: {exc}", EXIT_PARTIAL) from exc


def _no_float(_: str) -> None:
    raise ValueError("JSON floats are not admitted")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    answer: dict[str, Any] = {}
    for key, value in pairs:
        if key in answer:
            raise ValueError(f"duplicate JSON key {key!r}")
        answer[key] = value
    return answer


def load_record(raw: str) -> dict[str, Any]:
    """Parse `--record`: literal JSON, or `@path` to a file holding it.

    Duplicate keys and floats are rejected rather than resolved. A duplicate key has two readings
    and canonical output would silently pick one; a float would not survive a round trip through the
    canonical form byte-for-byte, and every digest in this family is over those bytes.
    """
    if raw.startswith("@"):
        path = raw[1:]
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise JournalError("invalid", f"cannot read --record file {path}: {exc}", EXIT_INPUT) from exc
    else:
        text = raw
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_float=_no_float, parse_constant=_no_float)
    except (ValueError, RecursionError) as exc:
        raise JournalError("invalid", f"--record is not valid canonical-compatible JSON: {exc}", EXIT_INPUT) from exc
    if not isinstance(value, dict):
        raise JournalError("invalid", "--record must be a JSON object", EXIT_INPUT)
    return value


def _time(value: Any, label: str) -> datetime:
    """An exact `YYYY-MM-DDTHH:MM:SSZ` instant. The format is closed so the bytes are comparable."""
    if not isinstance(value, str) or not _TIME.match(value):
        raise JournalError("invalid", f"{label} must be an exact YYYY-MM-DDTHH:MM:SSZ timestamp, got {value!r}", EXIT_INPUT)
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:  # the regex admits 2026-13-40T25:61:61Z; the calendar does not
        raise JournalError("invalid", f"{label} is not a real instant: {value!r} ({exc})", EXIT_INPUT) from exc


def _exact(value: Any, keys: set[str], label: str, *, optional: set[str] | None = None) -> dict[str, Any]:
    """An EXACT key set: nothing missing, nothing extra, no defaults applied.

    Defaults are how a record ends up meaning something the caller never said. A missing field is
    named as missing so the caller learns which one, and an unrecognised field is named too rather
    than dropped, because a typo silently ignored is a fact silently lost.

    `optional` is the one narrow widening, and it widens ONLY the extra-key half: a name in it may be
    absent or present, and every name in `keys` stays required. It exists because this journal is
    append-only evidence -- a field added after a journal was written must leave that journal's lines
    admissible, or the tool would refuse the record it exists to keep. It is not a defaulting
    mechanism: an admitted optional key is still validated by the caller that named it, and an absent
    one is left absent rather than filled in.
    """
    if not isinstance(value, dict):
        raise JournalError("invalid", f"{label} must be a JSON object, got {type(value).__name__}", EXIT_INPUT)
    missing = sorted(keys - set(value))
    if missing:
        raise JournalError("invalid", f"{label} is missing required field(s): {', '.join(missing)}", EXIT_INPUT)
    extra = sorted(set(value) - keys - (optional or set()))
    if extra:
        raise JournalError("invalid", f"{label} carries unrecognised field(s): {', '.join(extra)}", EXIT_INPUT)
    return value


def _text(value: Any, label: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise JournalError("invalid", f"{label} must be a non-empty string, got {value!r}", EXIT_INPUT)
    if pattern is not None and not pattern.match(value):
        raise JournalError("invalid", f"{label} must match {pattern.pattern}, got {value!r}", EXIT_INPUT)
    return value


def _optional_text(value: Any, label: str, *, pattern: re.Pattern[str] | None = None) -> str | None:
    return None if value is None else _text(value, label, pattern=pattern)


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise JournalError("invalid", f"{label} must be a list of non-empty strings, got {value!r}", EXIT_INPUT)
    return list(value)


def _integer(value: Any, label: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise JournalError("invalid", f"{label} must be an integer, got {value!r}", EXIT_INPUT)
    if value < minimum:
        raise JournalError("invalid", f"{label} must be at least {minimum}, got {value}", EXIT_INPUT)
    return value


def _choice(value: Any, options: tuple[str, ...], label: str) -> str:
    if value not in options:
        raise JournalError("invalid", f"{label} must be one of {', '.join(options)}, got {value!r}", EXIT_INPUT)
    return str(value)


ASSIGNMENT_FIELDS = {"provider", "model_id", "effort", "context", "resolution_state"}
HEADER_FIELDS = {"wave_id", "mission_id", "mode", "plan_digest", "approval", "required_nodes", "limits"}
LIMIT_FIELDS = {"max_concurrent_nodes", "max_nodes", "max_recursive_generations"}
NODE_FIELDS = {"node_id", "role", "disposition", "inputs", "outputs", "assignment", "started_at", "ended_at", "evidence", "attempt", "reasons", "approval"}
BUDGET_FIELDS = {"budget_id", "scope", "node_id", "unit", "limit", "consumed", "reasons"}
RETRY_FIELDS = {"node_id", "attempt", "capability", "prior_effect", "evidence", "reason"}
PLAN_REVISION_FIELDS = {"revision_id", "from_plan_digest", "to_plan_digest", "approval", "reasons"}
APPROVAL_FIELDS = {"approval_id", "subject", "scope", "authority", "evidence"}
#: What an approval may bind itself to, each admissible ONLY as an exact sha256 or not at all. They
#: are optional because this journal is append-only and every line written before they existed must
#: stay admissible; they are independent of each other because a grant that binds its candidate and
#: not its prestate is narrower than a free-form grant and wider than a fully bound one, and
#: collapsing those three into two would either forbid the middle or admit it silently as the last.
APPROVAL_DIGEST_FIELDS = ("candidate_digest", "prestate_digest")


def _validate_assignment(value: Any) -> dict[str, Any]:
    """The node's RuntimeAssignment as the journal records it, never as proof of anything.

    Issue 07 keeps the semantic tier and the exact provider/model ID separate facts and requires a
    resolved assignment before spawn. This records what was requested and what `resolution_state` the
    conductor reached; it cannot verify a route, and nothing here should be read as readback.
    """
    record = _exact(value, ASSIGNMENT_FIELDS, "a node record assignment")
    _choice(record["resolution_state"], RESOLUTION_STATES, "assignment resolution_state")
    for field in ("provider", "model_id", "effort", "context"):
        _optional_text(record[field], f"assignment {field}")
    return record


def _validate_header(value: Any) -> dict[str, Any]:
    record = _exact(value, HEADER_FIELDS, "a wave header record")
    _text(record["wave_id"], "wave header wave_id", pattern=_ID)
    _text(record["mission_id"], "wave header mission_id", pattern=_ID)
    mode = _choice(record["mode"], MODES, "wave header mode")
    _text(record["plan_digest"], "wave header plan_digest", pattern=_HEX64)
    # Issue 07: "Before wave launch, the user approves the objective, graph, authority, routes,
    # egress, budgets, fallbacks, and limits." The journal records that the approval was claimed; it
    # cannot authenticate it, and `record-approval` stamps the same honesty on every approval entry.
    _text(record["approval"], "wave header approval")
    required = _string_list(record["required_nodes"], "wave header required_nodes")
    if not required:
        raise JournalError("invalid", "wave header required_nodes must name at least one node", EXIT_INPUT)
    for node in required:
        _text(node, "wave header required_nodes entry", pattern=_ID)
    if len(set(required)) != len(required):
        raise JournalError("invalid", "wave header required_nodes must not repeat a node id", EXIT_INPUT)
    limits = _exact(record["limits"], LIMIT_FIELDS, "wave header limits")
    concurrent = _integer(limits["max_concurrent_nodes"], "limits max_concurrent_nodes", 1)
    total = _integer(limits["max_nodes"], "limits max_nodes", 1)
    generations = _integer(limits["max_recursive_generations"], "limits max_recursive_generations", 0)
    if concurrent > total:
        raise JournalError("invalid", f"limits max_concurrent_nodes {concurrent} exceeds max_nodes {total}", EXIT_INPUT)
    # Issue 07 ships recursive execution "separately default-off even when numeric limits are
    # raised", so a static-dag wave carrying a recursive generation is a contradiction rather than a
    # narrowing, and the journal refuses to record both claims at once.
    if mode == "static-dag" and generations:
        raise JournalError("invalid", f"a static-dag wave may not declare {generations} recursive generation(s): recursive execution is separately default-off", EXIT_INPUT)
    if mode == "recursive" and not generations:
        raise JournalError("invalid", "a recursive wave must declare at least one recursive generation", EXIT_INPUT)
    return record


def _validate_node(value: Any, at: str) -> dict[str, Any]:
    """One node's terminal disposition, with the evidence that makes the word mean something.

    Issue 07's completion condition 1 admits exactly three states, and each carries its own
    obligation: an ADMITTED success has evidence and a resolved assignment (nothing was admitted
    otherwise), an APPROVED skip names its approval, and an EXPLICIT blocked disposition states why.
    Enforcing those here is what lets the verdict tool count dispositions instead of trusting them.
    """
    record = _exact(value, NODE_FIELDS, "a node record")
    _text(record["node_id"], "node record node_id", pattern=_ID)
    _choice(record["role"], ROLES, "node record role")
    disposition = _choice(record["disposition"], DISPOSITIONS, "node record disposition")
    _string_list(record["inputs"], "node record inputs")
    _string_list(record["outputs"], "node record outputs")
    assignment = _validate_assignment(record["assignment"])
    started = _time(record["started_at"], "node record started_at")
    ended = _time(record["ended_at"], "node record ended_at")
    evidence = _string_list(record["evidence"], "node record evidence")
    _integer(record["attempt"], "node record attempt", 1)
    reasons = _string_list(record["reasons"], "node record reasons")
    approval = _optional_text(record["approval"], "node record approval", pattern=_ID)
    if started > ended:
        raise JournalError("invalid", f"node record started_at {record['started_at']} is after its ended_at {record['ended_at']}", EXIT_INPUT)
    if ended > _time(at, "--at"):
        raise JournalError("invalid", f"node record ended_at {record['ended_at']} is after the instant it is being recorded at (--at {at})", EXIT_INPUT)
    if disposition == "admitted-success":
        if assignment["resolution_state"] != "resolved":
            raise JournalError("invalid", f"an admitted-success node record requires assignment resolution_state `resolved`, got {assignment['resolution_state']!r}: an unresolved assignment stops before spawn", EXIT_INPUT)
        if not evidence:
            raise JournalError("invalid", "an admitted-success node record must carry evidence: `admitted` is what the evidence establishes, not a word the caller may assert", EXIT_INPUT)
        if approval is not None:
            raise JournalError("invalid", "an admitted-success node record must leave `approval` null: an approval is what an approved skip needs, not a success", EXIT_INPUT)
    elif disposition == "approved-skip":
        if approval is None:
            raise JournalError("invalid", "an approved-skip node record must name its approval in `approval`: otherwise `approved` is asserted rather than recorded", EXIT_INPUT)
    else:
        if not reasons:
            raise JournalError("invalid", "a blocked node record must state its reasons: issue 07 requires an EXPLICIT blocked disposition", EXIT_INPUT)
        if approval is not None:
            raise JournalError("invalid", "a blocked node record must leave `approval` null", EXIT_INPUT)
    return record


def _validate_budget(value: Any, at: str) -> dict[str, Any]:
    record = _exact(value, BUDGET_FIELDS, "a budget record")
    _text(record["budget_id"], "budget record budget_id", pattern=_ID)
    scope = _choice(record["scope"], BUDGET_SCOPES, "budget record scope")
    node = _optional_text(record["node_id"], "budget record node_id", pattern=_ID)
    _choice(record["unit"], BUDGET_UNITS, "budget record unit")
    _integer(record["limit"], "budget record limit", 0)
    # `consumed` may EXCEED `limit`: an exhausted or overrun budget is a fact issue 07 needs
    # recorded, and the projection publishes `remaining` (which may be negative) rather than a
    # verdict about it.
    _integer(record["consumed"], "budget record consumed", 0)
    _string_list(record["reasons"], "budget record reasons")
    if scope == "node" and node is None:
        raise JournalError("invalid", "a node-scoped budget record must name its node_id", EXIT_INPUT)
    if scope != "node" and node is not None:
        raise JournalError("invalid", f"a {scope}-scoped budget record must leave node_id null", EXIT_INPUT)
    return record


def _validate_retry(value: Any, at: str) -> dict[str, Any]:
    record = _exact(value, RETRY_FIELDS, "a retry record")
    _text(record["node_id"], "retry record node_id", pattern=_ID)
    _integer(record["attempt"], "retry record attempt", 2)
    capability = _choice(record["capability"], CAPABILITIES, "retry record capability")
    prior = _choice(record["prior_effect"], PRIOR_EFFECTS, "retry record prior_effect")
    evidence = _string_list(record["evidence"], "retry record evidence")
    _text(record["reason"], "retry record reason")
    if prior == EFFECT_UNKNOWN:
        raise JournalError(
            "invalid",
            f"a retry may not be recorded over a prior attempt whose effect is {EFFECT_UNKNOWN}: issue 07 stops the workstream on an unknown effect, so the honest record is a blocked node record",
            EXIT_INPUT,
        )
    if capability == "write-capable" and not evidence:
        raise JournalError(
            "invalid",
            "a write-capable retry must carry the evidence that the prior attempt had no effect: issue 07 permits it on that evidence alone",
            EXIT_INPUT,
        )
    return record


def _validate_plan_revision(value: Any, at: str) -> dict[str, Any]:
    record = _exact(value, PLAN_REVISION_FIELDS, "a plan-revision record")
    _text(record["revision_id"], "plan-revision record revision_id", pattern=_ID)
    before = _optional_text(record["from_plan_digest"], "plan-revision record from_plan_digest", pattern=_HEX64)
    after = _text(record["to_plan_digest"], "plan-revision record to_plan_digest", pattern=_HEX64)
    _text(record["approval"], "plan-revision record approval", pattern=_ID)
    reasons = _string_list(record["reasons"], "plan-revision record reasons")
    if not reasons:
        raise JournalError("invalid", "a plan-revision record must state its reasons", EXIT_INPUT)
    if before == after:
        raise JournalError("invalid", "a plan-revision record must change the plan digest", EXIT_INPUT)
    return record


def _validate_approval(value: Any, at: str, *, stored: bool = False) -> dict[str, Any]:
    """One recorded approval. `authenticated` is this module's word, never the caller's.

    A same-user record of an approval is not an authenticated approval, and the one way to keep that
    honest is to make the field unforgeable through this surface: a caller may not supply it, and
    every stored entry carries `false`.

    THE TWO OPTIONAL BINDINGS ARE SHAPE-CHECKED HERE AND COMPARED NOWHERE. `prestate_digest` and
    `candidate_digest` are admitted as exactly 64 lowercase hex characters, or left out; this module
    observes no tree and hashes no candidate, so it can prove a digest is well-formed and never that
    it describes anything. `wave-verdict.py`'s condition 5 is what compares a named digest against an
    observed one. Present-but-not-a-digest is refused by name -- `null`, `""`, an uppercase or
    short hex string, a number -- and the refusal says that absent is how an unbound grant is
    spelled, because the alternative is a caller inventing a second spelling for "nothing here" whose
    canonical bytes, and therefore whose entry digest, differ from the unbound grant it means.
    """
    if not stored and isinstance(value, dict) and "authenticated" in value:
        raise JournalError(
            "invalid",
            "an approval record may not supply `authenticated`: this tool stamps it false, because a recorded approval is a same-user assertion and nothing here can authenticate one",
            EXIT_INPUT,
        )
    record = _exact(
        value,
        APPROVAL_FIELDS | ({"authenticated"} if stored else set()),
        "an approval record",
        optional=set(APPROVAL_DIGEST_FIELDS),
    )
    _text(record["approval_id"], "approval record approval_id", pattern=_ID)
    _text(record["subject"], "approval record subject")
    _text(record["authority"], "approval record authority")
    scope = _string_list(record["scope"], "approval record scope")
    _string_list(record["evidence"], "approval record evidence")
    if not scope:
        raise JournalError("invalid", "an approval record must state its scope", EXIT_INPUT)
    for field in APPROVAL_DIGEST_FIELDS:
        if field not in record:
            continue
        supplied = record[field]
        if not isinstance(supplied, str) or not _HEX64.match(supplied):
            raise JournalError(
                "invalid",
                f"an approval record's {field} must be exactly 64 lowercase hex characters, got {supplied!r}: "
                f"a grant that binds nothing OMITS {field} entirely, and an empty or null one is neither a "
                "binding nor the absence of one",
                EXIT_INPUT,
            )
    if stored and record["authenticated"] is not False:
        raise JournalError("invalid", "a stored approval record must carry authenticated=false", EXIT_INPUT)
    return record


_VALIDATORS: dict[str, Callable[..., dict[str, Any]]] = {
    KIND_NODE: _validate_node,
    KIND_BUDGET: _validate_budget,
    KIND_RETRY: _validate_retry,
    KIND_PLAN_REVISION: _validate_plan_revision,
    KIND_APPROVAL: _validate_approval,
}


def _validate_entry_record(kind: str, record: Any, at: str, *, stored: bool = False) -> dict[str, Any]:
    validator = _VALIDATORS.get(kind)
    if validator is None:
        raise JournalError("invalid", f"unknown entry kind {kind!r}", EXIT_INPUT)
    if kind == KIND_APPROVAL:
        return _validate_approval(record, at, stored=stored)
    return validator(record, at)


def _open_parent(path: Path) -> tuple[int, str]:
    """A dirfd for the journal's directory plus the journal's own name.

    Every file operation below goes through this dirfd with `O_NOFOLLOW`, so the journal itself and
    its staging successor can never be a symlink to somewhere else. The directory PREFIX is resolved
    normally: the caller chose the path, and refusing an operator's symlinked scratch directory would
    buy nothing here.
    """
    name = path.name
    if not name or name in (".", "..") or "/" in name:
        raise JournalError("invalid", f"--journal must name a file, got {path}", EXIT_INPUT)
    if name.endswith(STAGING_SUFFIX):
        raise JournalError("invalid", f"--journal must not end with {STAGING_SUFFIX}: that name is this tool's staging successor", EXIT_INPUT)
    parent = path.parent if str(path.parent) else Path(".")
    try:
        return os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC), name
    except OSError as exc:
        raise JournalError("refused", f"journal directory is unusable: {parent}: {exc}", EXIT_REFUSED) from exc


def _read_regular_at(parent_fd: int, name: str, label: str) -> tuple[bytes, dict[str, Any]]:
    """Read one regular file through a dirfd and bind its identity, or refuse by name.

    The identity is exactly the four facts `_unchanged_since_read` compares, and no more: a fifth
    field nobody compares is dead weight that reads as a check. `mtime_ns` is deliberately NOT among
    them -- a same-second, same-size edit has already defeated one staleness check in this repository,
    so the content digest is what carries this one, and a timestamp would only add false refusals on a
    host whose clock steps backwards (which this one does). `nlink` is out on its own account: a hard
    link appearing next to the file changes no byte a reader would see.
    """
    try:
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent_fd)
    except FileNotFoundError as exc:
        raise JournalError("absent", f"{label} does not exist: {name}", EXIT_REFUSED) from exc
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise JournalError("refused", f"{label} is a symbolic link: {name}", EXIT_REFUSED) from exc
        raise JournalError("refused", f"cannot read {label} {name}: {exc}", EXIT_REFUSED) from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise JournalError("refused", f"{label} is not a regular file: {name}", EXIT_REFUSED)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) != info.st_size:
        raise JournalError("refused", f"{label} changed size while it was being read: {name}", EXIT_REFUSED)
    identity = {
        "dev": info.st_dev,
        "ino": info.st_ino,
        "sha256": digest(data),
        "size": info.st_size,
    }
    return data, identity


def _unchanged_since_read(parent_fd: int, name: str, bound: dict[str, Any]) -> None:
    """Refuse when the live journal is no longer the file this successor was built from.

    DETECTION, NOT PREVENTION, and the difference is worth stating precisely. Nothing here locks, and
    the gap between this comparison and the rename that follows it is still a gap: a writer that
    commits inside it is still lost. What this closes is the case that needs no race at all -- another
    writer's append COMMITTED while this run was assembling its successor, whose publication would
    replace the live file with a chain built from a prefix that is no longer the whole journal. That
    loss is undetectable afterwards (the successor is self-consistent, and `read_journal` cannot see a
    rewritten tail), so it has to be refused here or not at all.

    THE COST IS A SECOND FULL READ PER APPEND, MEASURED AND DEFERRED RATHER THAN CUT: this re-reads
    the whole live journal a second time on top of the read that built the successor, an O(size)
    doubling this module accepted as bounded by one wave's append-only growth instead of optimizing
    away toward a cheaper device/inode/size/mtime-only comparison, which `_read_regular_at` already
    names as unsafe against a same-second same-size edit.
    """
    _, live = _read_regular_at(parent_fd, name, "wave journal")
    changed = sorted(field for field in bound if live[field] != bound[field])
    if changed:
        raise JournalError(
            "stale",
            f"wave journal {name} changed ({', '.join(changed)}) between the read this successor was built from and this publish: "
            "another writer appended to it, and publishing this successor would destroy that record",
            EXIT_REFUSED,
        )


def _write_new_at(parent_fd: int, name: str, data: bytes) -> None:
    """Create `name` exclusively, write `data`, fsync it and its directory, and read it back.

    The destination EXISTS from the `os.open` onward, which is why the creation is admitted HERE
    rather than by the caller once this returns: admitting it late is exactly how a truncated file
    ends up on disk under an exit code that promises nothing happened. A failure BEFORE the open
    admits nothing and stays the pre-effect refusal it is.
    """
    _fault("before-staging-open")
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
    except FileExistsError as exc:
        raise JournalError(
            "refused",
            f"a staging successor already exists at {name}: an earlier run left it behind, and this run will not reuse or clobber it",
            EXIT_REFUSED,
        ) from exc
    except OSError as exc:
        raise JournalError("refused", f"cannot create {name}: {exc}", EXIT_REFUSED) from exc
    token = _admit(f"created the staging successor {name}")
    _fault("after-staging-open")
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise JournalError("effect-unknown", f"cannot write {name}: the write returned {written}", EXIT_PARTIAL)
            offset += written
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    except OSError as exc:
        raise JournalError("effect-unknown", f"cannot write {name}: {exc}", EXIT_PARTIAL) from exc
    finally:
        os.close(fd)
    os.fsync(parent_fd)
    _revise(token, f"wrote the staging successor {name}")
    _fault("after-staging-write")
    raw, _ = _read_regular_at(parent_fd, name, f"staging successor {name}")
    if raw != data:
        raise JournalError("effect-unknown", f"staging successor {name} lost custody: its bytes are not what was written", EXIT_PARTIAL)
    _fault("after-staging-readback")


def _renameat2_at(parent_fd: int, source: str, destination: str, flags: int) -> None:
    """Publish `source` onto `destination` within one directory. The namespace changes HERE."""
    call = getattr(_LIBC, "renameat2", None)
    if call is None:
        raise JournalError("unsupported", "Linux renameat2 is unavailable", EXIT_REFUSED)
    result = call(parent_fd, os.fsencode(source), parent_fd, os.fsencode(destination), flags)
    if result:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise JournalError("stale", f"{destination} appeared after this run checked for it; nothing was published over it", EXIT_REFUSED)
        raise JournalError("effect-unknown", f"cannot publish {source} onto {destination}: {os.strerror(error)}", EXIT_PARTIAL)
    # The journal MOVED the instant this returned 0 -- before the fsync, before any readback. A
    # publication is exactly this call, so admitting it later would let a failed post-publication
    # readback report a clean pre-effect refusal over live bytes.
    _admit(f"published {source} onto {destination}")
    os.fsync(parent_fd)
    _fault("after-rename")


def _discard_staging(parent_fd: int, name: str) -> str | None:
    """Remove this run's abandoned staging successor, or say nothing when there is none.

    `None` means the name does not exist, which is either "never created" or "already renamed onto
    the journal" -- in both cases there is nothing to describe and the ledger already says what
    happened. Removing this run's own aborted bytes launders nothing: the creation stays admitted, so
    the exit is 4 either way, and a removal that itself fails is named rather than hidden. It is
    worth doing because the staging name is exclusive-create: a stray leftover would refuse every
    later append until an operator removed it by hand.
    """
    try:
        os.unlink(name, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    except OSError:
        return f"an INCOMPLETE staging successor REMAINS at {name}"
    with contextlib.suppress(OSError):
        os.fsync(parent_fd)
    return f"the incomplete staging successor {name} was removed"


def _publish(parent_fd: int, name: str, data: bytes, *, replace: bool, bound: dict[str, Any] | None) -> None:
    """Stage, fsync, publish, and read back one whole journal successor.

    Append-only means the file's CONTENT only grows; the inode is replaced every time, because a
    rename is the only single step that cannot leave a reader a torn line. `replace=False` is the
    `init` case and uses RENAME_NOREPLACE, so a journal that appears between the pre-check and the
    publish is a refusal rather than a silent clobber.

    `bound` is the identity of the file this successor was built FROM, re-compared as late as this
    code can stand -- immediately before the rename -- and it has no default: an append states the
    file it read, and `init` states that it read none. It is deliberately checked AFTER the staging
    write rather than before it, because the point is to shrink the window rather than to buy a
    tidier exit code; a mismatch found here is therefore exit 4 over this run's own staged bytes,
    which `_report_failure` derives and `_discard_staging` then describes.

    THAT FLAG'S GUARD IS KILLED BY A DETERMINISTIC ORDERING SEAM, not by a forked racer. Its only
    distinguishing input is a second creator arriving inside the window between `init`'s `os.stat`
    pre-check and this rename, and this bundle declares concurrent external mutation of managed paths
    unsupported; a test that forked a racer to hit that window would still be timing-dependent, which
    is the host-coupled test this repository forbids. `tests/test_wave_journal.py`'s
    `InterleavedInitTests` drives it anyway, the same way `InterleavedWriterTests` drives the append
    path's own race: it wraps this function itself, so a second, REALLY COMMITTED `init` (a separate
    subprocess) runs to completion in PROGRAM ORDER between writer A's pre-check and writer A's rename,
    rather than by timing. What the flag buys is the difference between the loser of that race silently
    destroying the winner's journal (flags 0) and refusing at exit 4 with the effect named, and the
    test kills exactly that guard: drop `_RENAME_NOREPLACE` to `0` here and the same sequence silently
    overwrites the winner's journal instead of refusing.
    """
    staging = name + STAGING_SUFFIX
    admitted_before = len(_EFFECTS.admitted)
    try:
        _write_new_at(parent_fd, staging, data)
        if bound is not None:
            _unchanged_since_read(parent_fd, name, bound)
        _renameat2_at(parent_fd, staging, name, 0 if replace else _RENAME_NOREPLACE)
    except BaseException:
        # ONLY this run's own staging bytes are ever removed. The ledger is what proves whose they
        # are: `_write_new_at` admits the creation immediately after its exclusive `open`, so a grown
        # ledger means this run created the file and an ungrown one means the exclusive create is
        # what failed -- a leftover from a crashed run, whose bytes belong to that run and not to
        # this one. Removing it would have destroyed third-party evidence while reporting a CLEAN
        # refusal; a test drove exactly that and caught it here.
        if len(_EFFECTS.admitted) > admitted_before:
            # Once the rename has happened the staging name no longer exists, so this reports nothing
            # and the published effect stands unrevised. Otherwise the most recent admitted effect IS
            # the staging creation, and that is the one whose description gets the disposition.
            disposition = _discard_staging(parent_fd, staging)
            if disposition is not None:
                token = len(_EFFECTS.admitted) - 1
                _revise(token, f"{_EFFECTS.admitted[token]}, then {disposition}")
        raise
    raw, _ = _read_regular_at(parent_fd, name, f"published journal {name}")
    if raw != data:
        raise JournalError("effect-unknown", f"published journal {name} is not the bytes that were staged", EXIT_PARTIAL)
    _fault("after-publish-readback")


ENVELOPE_FIELDS = {"at", "kind", "record", "schema", "seq"}


def read_journal(parent_fd: int, name: str) -> tuple[list[bytes], list[dict[str, Any]], dict[str, Any]]:
    """Load one journal and RE-DERIVE it. Returns (lines, entries, identity).

    Every line must be exactly the canonical form of what it parses to, declare its own index as
    `seq`, and (past line 0) carry the sha256 of the line before it. So an edited line, a reordered
    pair, a removed middle line, a reformatted line, and a line whose payload no longer satisfies its
    kind's schema are each a refusal rather than a projection.

    THE LIMIT, stated because a chain invites more confidence than it earns: nothing in the file
    anchors its HEAD, so a rewrite of the LAST line, or the removal of a trailing group of lines,
    cannot be detected from the file alone -- both leave a self-consistent chain. Detecting those
    needs an anchor kept outside the file, which is why every `init` and `record-*` result returns
    `journal_digest`: a consumer that retains the last one it saw can compare. This tool refuses what
    it can prove and does not pretend the rest.

    A content failure here is exit 3, not 2: the bytes are not this caller's grammar, they are the
    journal's state, and the honest answer is that this journal does not admit the operation.
    """
    data, identity = _read_regular_at(parent_fd, name, "wave journal")
    if not data:
        raise JournalError("refused", f"wave journal {name} is empty", EXIT_REFUSED)
    if not data.endswith(b"\n"):
        raise JournalError("refused", f"wave journal {name} does not end in a newline: its last line is truncated", EXIT_REFUSED)
    lines = data.splitlines(keepends=True)
    entries: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        try:
            entry = json.loads(line.decode("utf-8"), object_pairs_hook=_pairs, parse_float=_no_float, parse_constant=_no_float)
        except (ValueError, UnicodeError) as exc:
            raise JournalError("refused", f"wave journal line {index} is not valid JSON: {exc}", EXIT_REFUSED) from exc
        if not isinstance(entry, dict):
            raise JournalError("refused", f"wave journal line {index} is not a JSON object", EXIT_REFUSED)
        try:
            _admissible_line(entry, index, line, lines)
        except JournalError as exc:
            # Re-raised at 3 whatever the validator said: a schema verdict (2) is about what this
            # invocation was handed, and this content was on disk before it started.
            raise JournalError("refused", f"wave journal line {index} is not admissible: {exc.reason}", EXIT_REFUSED) from exc
        entries.append(entry)
    return lines, entries, identity


def _admissible_line(entry: dict[str, Any], index: int, line: bytes, lines: list[bytes]) -> None:
    kind = entry.get("kind")
    # Checked before the envelope's key set, so a journal whose header line was removed is reported
    # as the missing header it is rather than as a node record with one field too many.
    if index == 0 and kind != KIND_OPENED:
        raise JournalError("refused", f"line 0 must be a {KIND_OPENED} record, got {kind!r}", EXIT_REFUSED)
    if index and kind == KIND_OPENED:
        raise JournalError("refused", f"only line 0 may be a {KIND_OPENED} record", EXIT_REFUSED)
    _exact(entry, ENVELOPE_FIELDS if index == 0 else ENVELOPE_FIELDS | {"prev_digest"}, "the entry envelope")
    if canonical_bytes(entry) != line:
        raise JournalError("refused", "the line is not in canonical form", EXIT_REFUSED)
    if entry["schema"] != JOURNAL_SCHEMA:
        raise JournalError("refused", f"the line declares schema {entry['schema']!r}, not {JOURNAL_SCHEMA}", EXIT_REFUSED)
    if entry["seq"] != index:
        raise JournalError("refused", f"the line declares seq {entry['seq']!r} at index {index}: the sequence has a gap, or the lines were reordered", EXIT_REFUSED)
    at = _time(entry["at"], "the entry's at")
    if index == 0:
        _validate_header(entry["record"])
        return
    if entry["prev_digest"] != digest(lines[index - 1]):
        raise JournalError("refused", f"the line's prev_digest does not match line {index - 1}: a line was edited", EXIT_REFUSED)
    previous_at = json.loads(lines[index - 1].decode("utf-8"))["at"]
    if at < _time(previous_at, f"line {index - 1}'s at"):
        raise JournalError("refused", f"the line's at {entry['at']} goes backwards from line {index - 1}'s {previous_at}", EXIT_REFUSED)
    _validate_entry_record(entry["kind"], entry["record"], entry["at"], stored=True)


def _cross_check(kind: str, record: dict[str, Any], at: str, entries: list[dict[str, Any]]) -> None:
    """Refuse what the journal's own contents do not admit. State, so exit 3 rather than 2.

    Nothing here has touched the filesystem yet: this runs before the staging file is created, so
    every refusal it raises is a genuine pre-effect refusal and the ledger is empty when
    `_report_failure` reads it.
    """
    last = entries[-1]
    if _time(at, "--at") < _time(last["at"], "the journal's last entry"):
        raise JournalError(
            "refused",
            f"--at {at} goes backwards: the journal's last entry (seq {last['seq']}) is at {last['at']}, and an append may not precede it",
            EXIT_REFUSED,
        )
    dispositions = {
        entry["record"]["node_id"]: entry for entry in entries[1:] if entry["kind"] == KIND_NODE
    }
    approval_records = {
        entry["record"]["approval_id"]: entry["record"] for entry in entries[1:] if entry["kind"] == KIND_APPROVAL
    }
    approvals = set(approval_records)
    if kind == KIND_NODE:
        prior = dispositions.get(record["node_id"])
        if prior is not None:
            raise JournalError(
                "refused",
                f"node {record['node_id']} already reached the {prior['record']['disposition']} disposition at seq {prior['seq']}: a node reaches exactly one disposition",
                EXIT_REFUSED,
            )
        if record["disposition"] == "approved-skip":
            approval = approval_records.get(record["approval"])
            if approval is None:
                raise JournalError(
                    "refused",
                    f"node record approval {record['approval']!r} names an approval this journal does not carry: record the approval first, so `approved` is derivable from the journal",
                    EXIT_REFUSED,
                )
            # Existence alone is not authorization: this bundle's OWN downstream verdict tool checks a
            # fan-in approval's scope against the node it authorizes (Condition 5), and a recorded
            # approval whose scope names a DIFFERENT node is not evidence that THIS node was approved
            # to skip -- it is a true, recorded, irrelevant fact. Requiring scope membership here is
            # what makes `approved` derivable rather than merely "some approval exists somewhere".
            if record["node_id"] not in approval["scope"]:
                raise JournalError(
                    "refused",
                    f"node {record['node_id']}'s approved-skip cites approval {record['approval']!r}, "
                    f"whose scope {approval['scope']!r} does not name it: an approval authorizes only "
                    "the node(s) its own scope lists",
                    EXIT_REFUSED,
                )
    elif kind == KIND_APPROVAL:
        if record["approval_id"] in approvals:
            raise JournalError("refused", f"approval {record['approval_id']} is already recorded in this journal", EXIT_REFUSED)
    elif kind == KIND_PLAN_REVISION:
        if record["approval"] not in approvals:
            raise JournalError(
                "refused",
                f"plan-revision approval {record['approval']!r} names an approval this journal does not carry: issue 07 has a human approve every materially revised plan",
                EXIT_REFUSED,
            )
    elif kind == KIND_RETRY:
        prior = dispositions.get(record["node_id"])
        if prior is not None:
            raise JournalError(
                "refused",
                f"node {record['node_id']} already reached the {prior['record']['disposition']} disposition at seq {prior['seq']}, so a retry cannot be recorded after it",
                EXIT_REFUSED,
            )


def _entry(kind: str, seq: int, at: str, record: dict[str, Any], prev_digest: str | None) -> dict[str, Any]:
    entry = {"at": at, "kind": kind, "record": record, "schema": JOURNAL_SCHEMA, "seq": seq}
    if prev_digest is not None:
        entry["prev_digest"] = prev_digest
    return entry


def _result(command: str, status: str, code: int, journal: Path, *, effect: str, **extra: Any) -> dict[str, Any]:
    """Render one result. `effect` is REQUIRED, and that is the structural half of the rule.

    There is no default to fall back on: a success states the effect it completed, and a refusal
    gets its effect from `_report_failure`, which reads the ledger. A defaulted effect is how every
    previous instance of this defect claimed `none` over bytes on disk.
    """
    document = {
        "admitted_effects": list(_EFFECTS.admitted),
        "command": command,
        "effect": effect,
        "exit_code": code,
        "journal": str(journal),
        "reasons": [],
        "schema": RESULT_SCHEMA,
        "status": status,
    }
    document.update(extra)
    return document


def _report_failure(command: str, exc: JournalError, journal: Path) -> tuple[dict[str, Any], int]:
    """THE single escalation choke point: every refusal's effect is DERIVED here, by every verb.

    Two inputs and one direction:

    1. THE LEDGER IS THE FLOOR. Once this invocation has admitted any effect, no refusal may exit as
       a clean pre-effect refusal (3), a pre-effect internal failure (1), or a schema verdict (2),
       because on disk the result is partial or unknown. 4 is the only honest answer and
       `admitted_effects` names what already happened.
    2. A RAISE SITE MAY ONLY ESCALATE. `exc.code == 4` reports an unknown effect this invocation
       merely OBSERVED, which the ledger cannot know about because this process did not cause it. So
       a site can widen an empty ledger to `effect_unknown`; what it cannot do is claim `none` over
       something that happened. That direction is the whole defect, and it is unreachable here
       because the effect is not a parameter of any raise.
    """
    status, code, effect = exc.status, exc.code, EFFECT_NONE
    if _EFFECTS.any():
        status, code, effect = "effect-unknown", EXIT_PARTIAL, EFFECT_UNKNOWN
    elif code == EXIT_PARTIAL:
        effect = EFFECT_UNKNOWN
    return _result(command, status, code, journal, effect=effect, reasons=[exc.reason]), code


def init_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    journal = Path(args.journal)
    record = load_record(args.record)
    at = args.at
    _time(at, "--at")
    _validate_header(record)
    parent_fd, name = _open_parent(journal)
    try:
        try:
            os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise JournalError("refused", f"a wave journal already exists at {journal}; this tool never re-initialises one", EXIT_REFUSED)
        entry = _entry(KIND_OPENED, 0, at, record, None)
        data = canonical_bytes(entry)
        # No prior journal was read, so there is no identity to re-compare; RENAME_NOREPLACE is what
        # keeps a journal that appeared in the meantime from being clobbered.
        _publish(parent_fd, name, data, replace=False, bound=None)
    finally:
        os.close(parent_fd)
    return (
        _result(
            "init",
            "initialized",
            EXIT_OK,
            journal,
            effect=f"created the wave journal at {journal}",
            seq=0,
            entry_digest=digest(data),
            journal_digest=digest(data),
        ),
        EXIT_OK,
    )


def _append(command: str, kind: str, args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    journal = Path(args.journal)
    record = load_record(args.record)
    at = args.at
    _time(at, "--at")
    # The record's OWN schema first, before any journal state is read, so a malformed record is a
    # schema verdict (2) whether or not the journal exists, and a state refusal (3) is only ever
    # about a well-formed record this journal will not take.
    record = _validate_entry_record(kind, record, at)
    if kind == KIND_APPROVAL:
        record = dict(record, authenticated=False)
    parent_fd, name = _open_parent(journal)
    try:
        lines, entries, bound = read_journal(parent_fd, name)
        _cross_check(kind, record, at, entries)
        seq = len(lines)
        entry = _entry(kind, seq, at, record, digest(lines[-1]))
        data = b"".join(lines) + canonical_bytes(entry)
        # `bound` travels from the read to the publish, where it is re-compared: this successor is
        # only admissible over the exact file its prefix came from.
        _publish(parent_fd, name, data, replace=True, bound=bound)
    finally:
        os.close(parent_fd)
    return (
        _result(
            command,
            "appended",
            EXIT_OK,
            journal,
            effect=f"appended entry {seq} to {journal}",
            seq=seq,
            entry_digest=digest(canonical_bytes(entry)),
            journal_digest=digest(data),
        ),
        EXIT_OK,
    )


def project_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Publish the journal's facts. Nothing here is a verdict; see the module docstring.

    THE BOUND IDENTITY IS DISCARDED HERE ON PURPOSE. `read_journal` returns the file's identity
    alongside its entries, and `_append` carries that identity forward into `_publish`'s `bound`,
    re-compared immediately before ITS OWN rename. `project` never mutates, so it has no later rename
    of its own to bind that identity against, and the identity return value below is thrown away (see
    the `_` in the unpacking).

    That makes the published `journal_digest` describe THE READ this invocation performed, not the
    file at whatever later instant the caller acts on this projection. Nothing here re-reads the file
    to confirm it is still that exact state, and nothing stops another writer from appending between
    this read and the caller's use of the result. A caller that needs the two instants to coincide
    must re-project immediately before acting, or must be the one holding `journal_digest` as an
    anchor kept OUTSIDE this file's own read -- which is exactly what `wave-verdict.py`'s conductor
    record and its `--wave-journal-digest` anchor both bind against.
    """
    journal = Path(args.journal)
    parent_fd, name = _open_parent(journal)
    try:
        lines, entries, _ = read_journal(parent_fd, name)
    finally:
        os.close(parent_fd)
    header = entries[0]["record"]
    required = list(header.get("required_nodes", []))
    dispositions: dict[str, Any] = {}
    budgets: list[dict[str, Any]] = []
    retries: list[dict[str, Any]] = []
    revisions: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    for entry in entries[1:]:
        record, kind, seq, at = entry["record"], entry["kind"], entry["seq"], entry["at"]
        if kind == KIND_NODE:
            dispositions[record["node_id"]] = {
                "at": at,
                "disposition": record["disposition"],
                "role": record["role"],
                "seq": seq,
            }
        elif kind == KIND_BUDGET:
            budgets.append(dict(record, seq=seq, at=at, remaining=record["limit"] - record["consumed"]))
        elif kind == KIND_RETRY:
            retries.append(dict(record, seq=seq, at=at))
        elif kind == KIND_PLAN_REVISION:
            revisions.append(dict(record, seq=seq, at=at))
        elif kind == KIND_APPROVAL:
            approvals.append(dict(record, seq=seq, at=at))
    projection = {
        "admitted_effects": list(_EFFECTS.admitted),
        "approvals": approvals,
        "budgets": budgets,
        "command": "project",
        "dispositions": dispositions,
        "effect": EFFECT_NONE,
        "entries": entries,
        "entry_count": len(entries) - 1,
        "exit_code": EXIT_OK,
        "journal": str(journal),
        "journal_digest": digest(b"".join(lines)),
        "last_at": entries[-1]["at"],
        "limits": header.get("limits"),
        "mission_id": header.get("mission_id"),
        "mode": header.get("mode"),
        "nodes_not_required": sorted(set(dispositions) - set(required)),
        "opened_at": entries[0]["at"],
        "plan_digest": header.get("plan_digest"),
        "plan_revisions": revisions,
        "reasons": [],
        "required_nodes": required,
        "required_nodes_without_disposition": sorted(set(required) - set(dispositions)),
        "retries": retries,
        "schema": PROJECTION_SCHEMA,
        "status": "projected",
        "wave_id": header.get("wave_id"),
    }
    return projection, EXIT_OK


_RECORD_VERBS = {
    "record-node": KIND_NODE,
    "record-budget": KIND_BUDGET,
    "record-retry": KIND_RETRY,
    "record-plan-revision": KIND_PLAN_REVISION,
    "record-approval": KIND_APPROVAL,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="wave-journal.py",
        description=(
            "Append-only wave journal. Records what each node in one wave did, plus the budgets, "
            "retries, plan revisions, and approvals that make a wave's completion derivable. It "
            "records evidence and authorizes nothing."
        ),
    )
    verbs = parser.add_subparsers(dest="command", required=True)
    opened = verbs.add_parser("init", help="create the journal for one wave (refuses an existing one)")
    opened.add_argument("--journal", required=True, help="path to the journal file to create")
    opened.add_argument("--at", required=True, help="caller-supplied YYYY-MM-DDTHH:MM:SSZ instant; this tool reads no clock")
    opened.add_argument("--record", required=True, help="the wave header as JSON, or @path to a file holding it")
    for verb in _RECORD_VERBS:
        appended = verbs.add_parser(verb, help=f"append one {verb.removeprefix('record-')} record")
        appended.add_argument("--journal", required=True, help="path to the existing journal file")
        appended.add_argument("--at", required=True, help="caller-supplied YYYY-MM-DDTHH:MM:SSZ instant; must not go backwards")
        appended.add_argument("--record", required=True, help="the record as JSON, or @path to a file holding it")
    projected = verbs.add_parser("project", help="read back a validated projection of the journal's facts")
    projected.add_argument("--journal", required=True, help="path to the existing journal file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    command = args.command
    journal = Path(args.journal)
    note = advisory_stderr()
    with _effect_ledger():
        try:
            if command == "init":
                result, code = init_command(args)
            elif command == "project":
                result, code = project_command(args)
            else:
                result, code = _append(command, _RECORD_VERBS[command], args)
            _emit(result, mandatory=True)
            return code
        except JournalError as exc:
            result, code = _report_failure(command, exc, journal)
        except Exception as exc:  # an unexpected failure must still classify its own effects
            result, code = _report_failure(command, JournalError("internal", f"unexpected {type(exc).__name__}: {exc}", EXIT_INTERNAL), journal)
        note(f"wave-journal.py: {result['status']}: {result['reasons'][0]}\n")
        if _EFFECTS.any():
            note("wave-journal.py: this is a PARTIAL result, not a clean refusal:\n")
            for effect in _EFFECTS.admitted:
                note(f"wave-journal.py:   already happened: {effect}\n")
        _emit(result, mandatory=False)
        return code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(main())
