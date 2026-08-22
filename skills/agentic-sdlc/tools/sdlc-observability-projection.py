#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Read-only observability projection over already-recorded agentic-SDLC evidence.

This is the slice-6 exit artifact itself: "read-only projections rendering the recorded journals
and receipts" (product-spec, Slice 6). It is a PROJECTION, not a validator, a compiler, or a gate:
it assembles one derived status document purely from artifact files that already exist on disk
today, and it never writes anything anywhere. It prints one document to stdout and nothing else.

THIRTEEN OPTIONAL INPUTS, each independent of the others:

    --wave-journal PATH        the append-only file `wave-journal.py`'s `init`/`record-*` verbs
                                EMIT and its `project` verb READS. Because that format is a
                                hash-chained ledger, not a self-contained document, this module
                                re-derives its facts by INVOKING `wave-journal.py project` over it
                                (by absolute sibling path, stdout captured, never imported) rather
                                than re-parsing the ledger itself -- duplicating that parser would
                                drag its hash-chain and cross-check logic into a module whose whole
                                value is that it carries none of that.
    --runtime-assignment PATH  one document `runtime-assignment.py` EMITS: an admission report
                                (`agentic-sdlc/runtime-assignment-admission@1`) or a classification
                                report (`agentic-sdlc/runtime-substitution-classification@1`).
                                Already a terminal document, so it is read directly.
    --activation-result PATH   one document `activation-result.py` EMITS
                                (`agentic-sdlc/activation-terminal-state@1`). Read directly.
    --gate-receipt PATH        one self-hashing receipt `gate_receipt.py record` EMITS. Read
                                directly; its self_digest is RE-DERIVED inline (re-expressed from
                                `gate_receipt.canonical_json`, never imported) exactly as
                                `activation-result.py`'s own `load_gate_receipt` already does.
    --gate-baseline PATH       one `gate-baseline-comparison/v1` document `gate_baseline.py
                                compare` EMITS, comparing that receipt against a prior one. Read
                                directly, exactly as `activation-result.py` reads its own
                                `--baseline-comparison`.

    --mission-contract PATH       `agentic-sdlc/mission-contract@1`, from `mission-contract.py define`
    --planning-snapshot PATH      `agentic-sdlc/planning-snapshot@1`, from `planning-snapshot.py capture`
    --wave-plan PATH              `agentic-sdlc/wave-plan@1`, from `wave-plan-compiler.py compile --out`
    --plan-diff PATH              `agentic-sdlc/plan-diff@1`, from that same run's `--diff-out`
    --wave-plan-admission PATH    `agentic-sdlc/wave-plan-admission@1`, from `wave-plan-admission.py admit`
    --drift-classification PATH   `agentic-sdlc/drift-classification@1`, from `drift-classifier.py classify`
    --auto-envelope PATH          `agentic-sdlc/auto-envelope@1`, from `auto-envelope.py define`
    --transition-receipt PATH     `agentic-sdlc/autonomous-transition-receipt@1`, from
                                   `auto-envelope.py admit-transition`

                                Those eight are the sealed slice-6 planning documents (T1/T2/T5/T6/
                                T7/T8 in the slice-6 cartography), and all eight are read the SAME way
                                because all eight are the same shape of thing: one self-contained
                                document that declares its own schema and carries one `digest` over its
                                own body. Each seal is RE-DERIVED here from this family's single
                                canonical form -- sha256 over the canonical bytes of the document minus
                                `digest`, the key excluded BY NAME -- re-expressed, never imported, so a
                                truncated or edited document is `unreadable` rather than believed. None
                                of them is a hash-chained ledger, so none needs `--wave-journal`'s
                                invoke-the-sibling treatment.

NEVER MANUFACTURE SUCCESS. Three outcomes, and only three, for every one of the thirteen inputs:

    absent       no path was supplied, or the supplied path does not exist. Named as absent.
    unreadable   the path exists but could not be read as the document it claims to be -- not a
                 regular file, not UTF-8, not JSON, nested deeper than `MAX_JSON_DEPTH`, not the
                 right schema, a digest that does not re-derive, a set its own neighbouring fields
                 do not derive, or a shape this module does not recognise. Named as unreadable,
                 WITH the reason, and every other input keeps its own independent outcome. That
                 independence is why the nesting ceiling exists: `json.loads` recurses once per
                 level, so without it ONE deeply nested input raised `RecursionError`, was caught as
                 an internal failure, and took every other input's outcome down with it at exit 1.
    present      the document was read and validated; its own fields are projected VERBATIM in its
                 own vocabulary. This module never upgrades a "failed" into a "passed", never
                 infers a wave completed because its evidence is silent, and never states an
                 artifact's fact in different words than the artifact itself used.

An absent or unreadable input is never an error for this module: the projection always succeeds
(exit 0) and simply says, by name, what it could not use. That is the whole point of an
observability surface over evidence that arrives piecemeal, wave by wave.

TWO VIEWS OF ONE DOCUMENT. The default view is a human BLUF-first read: the single most
decision-relevant line first (one artifact's own top fact, in the fixed priority order `BLUF_ORDER`
records -- the verdict-carrying kinds widest-consequence first, then the five descriptive ones in the
family's own chain order -- because that is the order in which each fact subsumes the ones after it),
then one section per artifact. `--json` emits the identical underlying document as canonical JSON
(`agentic-sdlc/observability-projection@2`). Both views carry, verbatim, the sentence "this view is
evidence, not authorization": nothing this module derives may be read as a grant to write, push,
publish, mutate a PR, merge, or deploy.

TWO VIEWS, ONE FIELD SET. Every field a projector records reaches BOTH views: the human view renders
each one as `field=value` under its own section, spelled with the SAME name the `--json` document
uses, so a reader can grep one name in either view. Only a handful are rendered as prose instead --
an objective, a consequence, and the per-item `reason:`, `blocker:`, and `assessment:` lines -- and
those are enumerated in this module's tests rather than left to a renderer's discretion. A field that
is projected into `--json` and dropped from the human view is a defect, not a style choice: a human
reading the default view would have to know to re-run with `--json` to see, say, that a comparison
recorded `toolchain_drifted`.

WHY @2 RATHER THAN @1. Adding the eight sealed kinds was not a purely additive change, so keeping
`@1` would have been a lie in a field a consumer reads. ONE fact moves for EVERY document, including
one produced by a caller who supplied none of the new flags: `artifacts` grows from four keys to
twelve (each kind's section is always present, carrying `absent` when its flag was not supplied --
that uniformity is the existing design, and making the new eight conditional instead would have
created two classes of section and a `_leaf_sections` that counts differently depending on which
flags were passed). That fact alone is a consumer-visible shape change, and it alone justifies the
bump. A SECOND fact moves only for a caller who supplies one of the new flags: the BLUF priority order
this docstring publishes has two kinds inserted ABOVE `gate`, so the same gate receipt that headlined
under `@1` can be headlined over by an admission or drift-classification line now. That one is NOT a
fact about every document, which is why it is stated second and carries no weight of its own: supply
none of the new flags and every new rung answers `None`, so adding the eight kinds left `.bluf`
byte-identical for exactly the inputs `@1` accepted. (The gate rung's own sentence has since changed
for an unrelated reason -- see the gate-BLUF residual below -- which is a change in DERIVED PROSE.
`bluf` is one English line assembled per run from whichever artifact won the rung; it is not a stable
enum, and a consumer matching its exact wording is coupled to prose that moves whenever a rung's
rationale is corrected.) Every `@1` FIELD that survives is unchanged in name, type, and meaning:
`schema`, `command`, `status`, `exit_code`, `evidence_notice`, `bluf`, and the four original
`artifacts` sections field-for-field.

NEVER RE-DERIVE A VERDICT THE ARTIFACT DOES NOT CARRY. Each of the eight is projected in its own
vocabulary: the admission report's own `disposition`, the drift classification's own
`overall_outcome`, the receipt's own `verdict`, the envelope's own recorded `validity_window`. This
module does not decide whether that window is open (it reads no clock), does not rank one drift
outcome against another (`drift-classifier.py` owns that ladder), does not turn a `blocked` report
into a blocker-free one, and does not read a met check as an approval -- `admitted` is not
`approved`, exactly as the report itself says. Counting what a document listed (how many checks it
recorded met, how many changes it recorded semantic) restates the document; it does not add a
verdict to it.

FAIL CLOSED ON THE TOOL ITSELF, NOT ON THE EVIDENCE. Every predicate above only ever downgrades an
input from "present" to "unreadable"; nothing here can upgrade an input, and nothing here can turn
a well-formed refusal recorded by another tool into anything but the refusal it already is.

EXITS. Implementation Decision 9 reserves 0 for a valid query, 1 for an unexpected internal
failure, 2 for a grammar/argument error, 3 for a clean refusal before effect, and 4 after an
admitted partial or unknown effect. This module's exit space is 0, 2, and 1 only, for the same
reason `mission-contract.py` and `activation-result.py` give: **a tool that can cause no effect can
neither refuse before one nor admit one.** Every one of the thirteen inputs is optional, and an absent
or unreadable one is folded into the exit-0 document rather than raised as a refusal. Exit 2 is
reserved for the arguments themselves being unusable (an unknown flag, a missing option value, or one
artifact flag given twice, which would silently drop a path the caller named); exit 1 additionally
covers a stdout that cannot receive the one result document, because a projection derived and not
delivered is not a success.

RESIDUALS, STATED EXACTLY.

  * The eight sealed slice-6 kinds ARE projected now (this was the T4 row's reserved extension, and it
    landed as eight more rows in the reader registry below rather than a rewrite of it). The wave
    SUBMISSION schemas -- `agentic-sdlc/advisory-submission@1`, `worktree-submission@1`,
    `fan-in-submission@1`, `outward-effect-submission@1`, which a wave plan node names in its
    `output_schema` -- are still not kinds this module knows; they are a later increment once merged,
    and until then a submission is invisible here even though the plan that expects it is not.
  * T3's two schemas -- `receipt-envelope@1` and `receipt-envelope-result@1`, from `receipt-envelope.py`
    -- are NOT among the eight projected kinds above. The eight come from the SIX producer tools named
    in the flag list at the top of this docstring: `mission-contract.py`, `planning-snapshot.py`,
    `wave-plan-compiler.py` (a plan AND its diff, in one run), `wave-plan-admission.py`,
    `drift-classifier.py`, and `auto-envelope.py` (an envelope AND a transition receipt) -- and
    `receipt-envelope.py` is not one of them. That count is stated as PRODUCERS rather than as slice-6
    ticket numbers on purpose: the ticket numbering lives in a cartography artifact this repository does
    not carry, so a ticket count written here could go stale with no test able to notice, while the
    producer list is checkable against the tree and against `SEALED_READERS` below.
    `auto-envelope.py`'s own transition-receipt residual records that its receipt "does not adopt the
    merged receipt-envelope@1 ancestor form" yet and names folding the two as "T4's extension to make"
    once it does; until that adoption lands, a caller reading a `receipt-envelope@1` document today gets
    no section here.
  * Only the FIELDS each projector records are projected, not every field the sealed document carries:
    node bodies, per-change evidence and consequence prose, deferred-dimension reasons, per-assessment
    grounds, checkpoint lists, and repository/host detail stay in the artifacts themselves. This is a
    BLUF-first status surface, not a re-serialization; a consumer that needs a document's full body
    must read that document.
  * A closed vocabulary is enforced for four fields -- the admission `disposition`, the drift
    classification's own `overall_outcome`, each drift assessment's own `outcome`, and the receipt
    `verdict` -- mirroring `ACTIVATION_STATES`. A future tool that adds a fifth drift outcome will
    therefore read as `unreadable` here until this table learns it, which is the intended failure
    direction: an unrecognised verdict must not be projected as if this module understood it.
  * The wave journal's own `journal_digest` anchor (a rewrite-or-truncation detector across
    repeated reads over TIME) is not retained across invocations here: each run is independent, and
    a caller polling this module repeatedly must keep that anchor itself if it wants to detect a
    rewritten tail between polls.
  * Every digest re-derivation here is TAMPER DETECTION BY RE-DERIVATION, not a security boundary
    against a same-OS-user forger -- the same posture every sibling tool in this family states.
  * `--gate-baseline` is read as an ALREADY-COMPUTED comparison document; this module does not
    itself invoke `gate_baseline.py` or re-implement its subset-comparison algorithm, mirroring
    `activation-result.py`'s own `--baseline-comparison` precedent exactly. It DOES check the
    comparison against itself -- `newly_failing`, `fixed`, `still_failing`, and `non_worsening` are
    pure arithmetic over the document's own two failing sets -- because a subset claim its own listed
    names deny is not a fact worth projecting. That is the same posture the gate receipt already has,
    where `outcome` must derive from `status`, and it is still not a comparison of two receipts.
  * The gate rung names an UNREADABLE receipt before a PRESENT comparison, and leads a present
    comparison with the candidate's own recorded outcome. Both corrections are in `_bluf_gate`, which
    states why: the ladder's own rule is that an unreadable leaf outranks a present one, and
    `non_worsening` answers "did this change break something NEW", never "did the gate pass".
  * Each artifact flag may be given at most ONCE (`_OnceOnly`); a repeat is exit 2 rather than
    argparse's silent last-wins, which would have dropped the first path without a word. `--json`
    takes no value and stays repeatable.
  * JSON nesting is bounded by `MAX_JSON_DEPTH` before any parser is entered, so one hostile input
    is `unreadable` by name instead of a `RecursionError` that ends the whole run at exit 1. The
    ceiling is a parse bound, not a schema claim: no producer in this family nests anywhere near it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

RESULT_SCHEMA = "agentic-sdlc/observability-projection@2"
EVIDENCE_NOTICE = "this view is evidence, not authorization"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

PRESENCE_ABSENT = "absent"
PRESENCE_UNREADABLE = "unreadable"
PRESENCE_PRESENT = "present"

#: The sibling tool this module invokes for exactly one input kind. Resolved from this file, never
#: from the caller's cwd or PATH.
WAVE_JOURNAL_TOOL = Path(__file__).resolve().parent / "wave-journal.py"
WAVE_JOURNAL_PROJECTION_SCHEMA = "agentic-sdlc/wave-journal-projection@1"

RUNTIME_ADMISSION_SCHEMA = "agentic-sdlc/runtime-assignment-admission@1"
RUNTIME_CLASSIFICATION_SCHEMA = "agentic-sdlc/runtime-substitution-classification@1"

ACTIVATION_TERMINAL_SCHEMA = "agentic-sdlc/activation-terminal-state@1"
ACTIVATION_STATES = ("write-ready", "remediation-ready", "refused")

GATE_BASELINE_SCHEMA = "gate-baseline-comparison/v1"
#: Exactly `gate_receipt.build_receipt`'s keys, with `failures` and the agentic-sdlc-5ee7 `head`
#: stamp as the two optional additions -- re-expressed from `activation-result.py`'s own
#: `GATE_RECEIPT_KEYS`/`GATE_RECEIPT_OPTIONAL_KEYS`, never imported. This projection reads neither
#: optional field; it must only keep RECOGNISING a receipt that carries them.
GATE_RECEIPT_OPTIONAL_KEYS = frozenset({"failures", "head"})
GATE_RECEIPT_KEYS = frozenset(
    {"gate", "argv", "status", "signal", "outcome", "log_digest", "toolchain_digest", "cwd", "self_digest"}
)
FAILURE_RECORD_KEYS = frozenset({"harness", "state", "names"})

#: Bounded, so a wedged child process cannot hang a read-only query forever.
SUBPROCESS_TIMEOUT_SECONDS = 30

#: An allowlist, not an inheritance: the one subprocess this module spawns gets exactly this much
#: ambient environment, so an unrelated variable in the caller's shell (including the sibling's own
#: fault-injection hook) cannot silently reach it.
PASSTHROUGH_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def constructed_environment() -> dict[str, str]:
    return {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}


class InputError(Exception):
    """Raised only within this module's own JSON reading helpers and its sealed-document projectors;
    never escapes them -- each catch site turns it into one `unreadable` reason naming the input."""


def canonical_bytes(value: Any) -> bytes:
    """This family's canonical form: sorted keys, tight separators, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def _gate_receipt_canonical_json(value: Any) -> bytes:
    """`gate_receipt.canonical_json`, re-expressed: the same form with NO trailing newline."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _reject_nonfinite(token: str) -> Any:
    """`json.loads`'s `parse_constant` hook: catches the literal tokens `NaN`/`Infinity`/`-Infinity`."""
    raise InputError(f"carries the non-finite JSON constant {token}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InputError(f"repeats the JSON key {key!r}, so it has two meanings")
        seen[key] = value
    return seen


#: A CEILING on JSON container nesting, checked before any parser is entered. `json.loads` recurses
#: once per nesting level, so a 2000-level document raised `RecursionError` out of the parser, `main`'s
#: catch-all classified that as an internal failure, and ONE hostile input took the whole run to exit 1
#: -- destroying the independent outcome every other input is promised. The ceiling is generous: the
#: deepest document any producer in this family seals nests about five containers, and the ledger
#: projection `wave-journal.py` prints is flatter still. It also bounds `_walk_reject_nonfinite`'s own
#: recursion, which runs only over an already-parsed value that passed this check.
MAX_JSON_DEPTH = 100


def _reject_excessive_nesting(raw: bytes) -> None:
    """An ITERATIVE depth scan, so nothing recursive is ever entered on bytes deep enough to exhaust
    the interpreter's stack. It reads BYTES rather than decoded text because every ASCII byte it looks
    for is unreachable inside a UTF-8 multibyte sequence, and it tracks string state because a brace
    inside a JSON string is data, not a container. A malformed document may drive the depth negative
    or leave a string unterminated; that is `json.loads`'s refusal to make, not this scan's."""
    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:  # a backslash escapes the next byte, including a quote
                escaped = True
            elif byte == 0x22:  # the closing quote
                in_string = False
            continue
        if byte == 0x22:  # the opening quote
            in_string = True
        elif byte in (0x7B, 0x5B):  # { [
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise InputError(
                    f"nests JSON containers deeper than the {MAX_JSON_DEPTH}-level ceiling this module reads"
                )
        elif byte in (0x7D, 0x5D):  # } ]
            depth -= 1


def _walk_reject_nonfinite(value: Any) -> None:
    """A post-parse walk, because a huge literal like `1e400` overflows to `inf` in `float()`
    WITHOUT ever passing through `parse_constant` -- that hook only sees the exact tokens `NaN` /
    `Infinity` / `-Infinity`, not an ordinary-looking numeral that silently overflows."""
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            raise InputError("carries a numeral that is not a finite floating point value")
    elif isinstance(value, dict):
        for item in value.values():
            _walk_reject_nonfinite(item)
    elif isinstance(value, list):
        for item in value:
            _walk_reject_nonfinite(item)


def _stat_mode(path: str) -> tuple[str, int | None, OSError | None]:
    """`Path.stat()` follows a symlink to its target: the question is "is what I would read a
    regular file", never "is the path itself one"."""
    try:
        mode = Path(path).stat().st_mode
    except FileNotFoundError:
        return "absent", None, None
    except OSError as exc:
        return "error", None, exc
    return "ok", mode, None


def _read_json_object(path: str, label: str) -> tuple[str, dict[str, Any] | None, str | None]:
    """Read one document as a single JSON object. Every failure here is `unreadable`, never raised."""
    kind, mode, exc = _stat_mode(path)
    if kind == "absent":
        return PRESENCE_ABSENT, None, None
    if kind == "error" or mode is None:
        return PRESENCE_UNREADABLE, None, f"cannot read the {label} {path}: {exc}"
    if not stat.S_ISREG(mode):
        return PRESENCE_UNREADABLE, None, f"the {label} {path} is not a regular file, so it cannot be read"
    try:
        raw = Path(path).read_bytes()
    except OSError as read_exc:
        return PRESENCE_UNREADABLE, None, f"cannot read the {label} {path}: {read_exc}"
    try:
        _reject_excessive_nesting(raw)
    except InputError as depth_exc:
        return PRESENCE_UNREADABLE, None, f"the {label} {path} {depth_exc}"
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_nonfinite
        )
    except (UnicodeDecodeError, ValueError, InputError) as parse_exc:
        return PRESENCE_UNREADABLE, None, f"the {label} {path} is not JSON: {parse_exc}"
    if not isinstance(value, dict):
        return PRESENCE_UNREADABLE, None, f"the {label} {path} is not a JSON object"
    try:
        _walk_reject_nonfinite(value)
    except InputError as walk_exc:
        return PRESENCE_UNREADABLE, None, f"the {label} {path} {walk_exc}"
    return PRESENCE_PRESENT, value, None


# ---- wave journal (the one invoked artifact kind) -------------------------------------------------


def _parse_wave_journal_stdout(data: bytes) -> tuple[dict[str, Any] | None, str | None]:
    try:
        _reject_excessive_nesting(data)
    except InputError as depth_exc:
        return None, f"wave-journal.py project's stdout {depth_exc}"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"wave-journal.py project's stdout is not UTF-8: {exc}"
    if not text.strip():
        return None, "wave-journal.py project produced no output"
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_nonfinite)
    except (ValueError, InputError) as exc:
        return None, f"wave-journal.py project's stdout is not JSON: {exc}"
    if not isinstance(value, dict):
        return None, "wave-journal.py project's stdout is not a JSON object"
    try:
        _walk_reject_nonfinite(value)
    except InputError as exc:
        return None, f"wave-journal.py project's stdout {exc}"
    return value, None


def build_wave_journal_section(path: str | None) -> dict[str, Any]:
    if path is None:
        return {"presence": PRESENCE_ABSENT, "path": None, "reason": None}
    kind, mode, exc = _stat_mode(path)
    if kind == "absent":
        return {"presence": PRESENCE_ABSENT, "path": path, "reason": None}
    if kind == "error" or mode is None:
        return {"presence": PRESENCE_UNREADABLE, "path": path, "reason": f"cannot read the wave journal {path}: {exc}"}
    if not stat.S_ISREG(mode):
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": f"the wave journal {path} is not a regular file, so it cannot be read",
        }
    argv = [sys.executable, "-B", str(WAVE_JOURNAL_TOOL), "project", "--journal", str(Path(path).resolve())]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            env=constructed_environment(),
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as run_exc:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": f"wave-journal.py project could not be run over {path}: {run_exc}",
        }
    projection, reason = _parse_wave_journal_stdout(completed.stdout)
    if projection is None:
        stderr_text = completed.stderr.decode("utf-8", "replace").strip()
        detail = reason or stderr_text or f"wave-journal.py project exited {completed.returncode}"
        return {"presence": PRESENCE_UNREADABLE, "path": path, "reason": detail}
    if completed.returncode != EXIT_OK:
        own_status = projection.get("status")
        own_reasons = projection.get("reasons") or []
        detail = f"wave-journal.py project reported {own_status!r}: " + "; ".join(str(r) for r in own_reasons)
        return {"presence": PRESENCE_UNREADABLE, "path": path, "reason": detail}
    if projection.get("schema") != WAVE_JOURNAL_PROJECTION_SCHEMA:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": (
                f"wave-journal.py project emitted schema {projection.get('schema')!r}, not "
                f"{WAVE_JOURNAL_PROJECTION_SCHEMA!r}"
            ),
        }
    required = projection.get("required_nodes")
    missing = projection.get("required_nodes_without_disposition")
    if not isinstance(required, list) or not isinstance(missing, list):
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": "wave-journal.py project's own required-node fields are not lists",
        }
    return {
        "presence": PRESENCE_PRESENT,
        "path": path,
        "reason": None,
        "wave_id": projection.get("wave_id"),
        "mode": projection.get("mode"),
        "plan_digest": projection.get("plan_digest"),
        "required_node_count": len(required),
        "required_nodes_without_disposition": list(missing),
        "complete": len(missing) == 0,
        "entry_count": projection.get("entry_count"),
        "opened_at": projection.get("opened_at"),
        "last_at": projection.get("last_at"),
        "plan_revision_count": len(projection.get("plan_revisions") or []),
        "approval_count": len(projection.get("approvals") or []),
        "retry_count": len(projection.get("retries") or []),
        "budget_count": len(projection.get("budgets") or []),
    }


# ---- runtime assignment ---------------------------------------------------------------------------


def build_runtime_assignment_section(path: str | None) -> dict[str, Any]:
    if path is None:
        return {"presence": PRESENCE_ABSENT, "path": None, "reason": None}
    presence, doc, reason = _read_json_object(path, "runtime-assignment report")
    if presence != PRESENCE_PRESENT or doc is None:
        return {"presence": presence, "path": path, "reason": reason}
    schema = doc.get("schema")
    if schema == RUNTIME_ADMISSION_SCHEMA:
        command = "admit"
    elif schema == RUNTIME_CLASSIFICATION_SCHEMA:
        command = "classify"
    else:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": (
                f"the runtime-assignment report {path} declares schema {schema!r}, which is neither "
                f"{RUNTIME_ADMISSION_SCHEMA!r} nor {RUNTIME_CLASSIFICATION_SCHEMA!r}"
            ),
        }
    verdict = doc.get("verdict")
    if not isinstance(verdict, str) or not verdict:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": f"the runtime-assignment report {path} carries no verdict",
        }
    consequence = doc.get("consequence")
    reasons = doc.get("reasons")
    evidence = doc.get("evidence")
    node = evidence.get("node") if isinstance(evidence, dict) else None
    return {
        "presence": PRESENCE_PRESENT,
        "path": path,
        "reason": None,
        "command": command,
        "verdict": verdict,
        "consequence": consequence if isinstance(consequence, str) else None,
        "may_spawn": doc.get("may_spawn") if command == "admit" else None,
        "blocks_wave_completion": doc.get("blocks_wave_completion") if command == "classify" else None,
        "reasons": list(reasons) if isinstance(reasons, list) else [],
        "node": node if isinstance(node, str) else None,
    }


# ---- activation result -----------------------------------------------------------------------------


def build_activation_result_section(path: str | None) -> dict[str, Any]:
    if path is None:
        return {"presence": PRESENCE_ABSENT, "path": None, "reason": None}
    presence, doc, reason = _read_json_object(path, "activation result document")
    if presence != PRESENCE_PRESENT or doc is None:
        return {"presence": presence, "path": path, "reason": reason}
    if doc.get("schema") != ACTIVATION_TERMINAL_SCHEMA:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": (
                f"the activation result document {path} declares schema {doc.get('schema')!r}, not "
                f"{ACTIVATION_TERMINAL_SCHEMA!r}"
            ),
        }
    state = doc.get("state")
    if state not in ACTIVATION_STATES:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": (
                f"the activation result document {path} carries state {state!r}, which is not one of "
                f"the closed activation states {list(ACTIVATION_STATES)}"
            ),
        }
    consequence = doc.get("consequence")
    target = doc.get("target")
    reasons = doc.get("reasons")
    return {
        "presence": PRESENCE_PRESENT,
        "path": path,
        "reason": None,
        "state": state,
        "consequence": consequence if isinstance(consequence, str) else None,
        "target": target if isinstance(target, str) else None,
        "gate_outcome": doc.get("gate_outcome"),
        "gate_passes": doc.get("gate_passes"),
        "reasons": list(reasons) if isinstance(reasons, list) else [],
    }


# ---- gate receipt / baseline pair ------------------------------------------------------------------


def _derive_gate_outcome(status: Any) -> str:
    if status is None:
        return "unobserved"
    return "passed" if status == 0 else "failed"


def _validate_gate_receipt_shape(receipt: dict[str, Any], path: str) -> str | None:
    """Re-expressed from `activation-result.py`'s `load_gate_receipt`: the exact key set, the
    self_digest re-derivation, and the two consistency clauses that verdict rests on. Not the full
    four-state `argv`/`status`/`signal` rule -- `activation-result.py` does not re-express that
    either, and this module inherits the same stated residual."""
    keys = set(receipt)
    if not GATE_RECEIPT_KEYS <= keys or not keys <= GATE_RECEIPT_KEYS | GATE_RECEIPT_OPTIONAL_KEYS:
        return f"the gate receipt {path} does not carry exactly a gate receipt's fields: {sorted(keys)}"
    body = {key: value for key, value in receipt.items() if key != "self_digest"}
    self_digest = receipt.get("self_digest")
    if not isinstance(self_digest, str):
        return f"the gate receipt {path} carries a self_digest that is not a string"
    if hashlib.sha256(_gate_receipt_canonical_json(body)).hexdigest() != self_digest:
        return f"the gate receipt {path} does not verify: its self_digest does not re-derive"
    status = receipt.get("status")
    if isinstance(status, bool) or not (status is None or isinstance(status, int)):
        return f"the gate receipt {path} carries a status that is neither an integer nor null"
    outcome = receipt.get("outcome")
    if outcome != _derive_gate_outcome(status):
        return (
            f"the gate receipt {path} records outcome {outcome!r}, which its status {status!r} does not "
            "derive"
        )
    if receipt.get("argv") is None and status is not None:
        return f"the gate receipt {path} claims a verdict although nothing was executed"
    failures = receipt.get("failures")
    if failures is not None:
        if not isinstance(failures, dict) or set(failures) != FAILURE_RECORD_KEYS:
            return f"the gate receipt {path} carries a failing set that is not exactly {{harness, names, state}}"
        names = failures.get("names")
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            return f"the gate receipt {path} carries a failing set whose names are not a list of strings"
    return None


def build_gate_receipt_section(path: str | None) -> dict[str, Any]:
    if path is None:
        return {"presence": PRESENCE_ABSENT, "path": None, "reason": None}
    presence, doc, reason = _read_json_object(path, "gate receipt")
    if presence != PRESENCE_PRESENT or doc is None:
        return {"presence": presence, "path": path, "reason": reason}
    problem = _validate_gate_receipt_shape(doc, path)
    if problem is not None:
        return {"presence": PRESENCE_UNREADABLE, "path": path, "reason": problem}
    failures = doc.get("failures")
    failing_state = failures.get("state") if isinstance(failures, dict) else None
    names = failures.get("names") if isinstance(failures, dict) else None
    failing_count = len(names) if isinstance(names, list) else None
    return {
        "presence": PRESENCE_PRESENT,
        "path": path,
        "reason": None,
        "gate": doc.get("gate"),
        "outcome": doc.get("outcome"),
        "gate_status": doc.get("status"),
        "ran": doc.get("argv") is not None,
        "failing_set_state": failing_state,
        "failing_test_count": failing_count,
    }


def _validate_gate_baseline_shape(doc: dict[str, Any], path: str) -> str | None:
    if doc.get("schema_version") != GATE_BASELINE_SCHEMA:
        return (
            f"the gate baseline comparison {path} declares schema_version "
            f"{doc.get('schema_version')!r}, not {GATE_BASELINE_SCHEMA!r}"
        )
    for key in ("gate", "baseline_outcome", "candidate_outcome"):
        if key not in doc:
            return f"the gate baseline comparison {path} carries no {key}"
    for key in ("baseline_failing", "candidate_failing", "newly_failing", "fixed", "still_failing"):
        value = doc.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return f"the gate baseline comparison {path} carries a {key} that is not a list of strings"
    if not isinstance(doc.get("non_worsening"), bool):
        return f"the gate baseline comparison {path} carries a non_worsening that is not a boolean"
    if not isinstance(doc.get("toolchain_drifted"), bool):
        return f"the gate baseline comparison {path} carries a toolchain_drifted that is not a boolean"
    return _gate_baseline_inconsistency(doc, path)


#: The three derived sets `gate_baseline.py compare` writes, each as the exact set expression that tool
#: computes it from -- `sorted(after - before)`, `sorted(before - after)`, `sorted(before & after)` over
#: its own `baseline_failing`/`candidate_failing`. Named here so the clause below reads as arithmetic
#: rather than as three copies of the same three lines.
GATE_BASELINE_DERIVED_SETS = (
    ("newly_failing", "candidate_failing", "baseline_failing"),
    ("fixed", "baseline_failing", "candidate_failing"),
)


def _gate_baseline_inconsistency(doc: dict[str, Any], path: str) -> str | None:
    """The comparison's own CROSS-FIELD consistency, mirroring the two clauses the gate receipt already
    gets: a document may not be believed about a fact its own neighbouring fields contradict.

    Every clause here is arithmetic `gate_baseline.py compare` performs itself, so a document that fails
    one is a document that tool did not write. `newly_failing` is `candidate_failing - baseline_failing`
    sorted, `fixed` is the reverse difference, `still_failing` is the intersection, and `non_worsening`
    is exactly "`newly_failing` is empty". Comparing the SORTED list rather than a set also catches an
    unsorted or duplicate-bearing set, which that tool cannot emit either. This is not re-implementing
    the comparison -- the module still reads the verdict it was given and never computes one over two
    receipts -- it is refusing to project a subset claim the document's own listed names deny.
    """
    baseline_failing = set(doc["baseline_failing"])
    candidate_failing = set(doc["candidate_failing"])
    for derived, left, right in GATE_BASELINE_DERIVED_SETS:
        expected = sorted(set(doc[left]) - set(doc[right]))
        if doc[derived] != expected:
            return (
                f"the gate baseline comparison {path} records a {derived} its own {left} and {right} do "
                f"not derive"
            )
    if doc["still_failing"] != sorted(baseline_failing & candidate_failing):
        return (
            f"the gate baseline comparison {path} records a still_failing its own baseline_failing and "
            "candidate_failing do not derive"
        )
    if doc["non_worsening"] != (not doc["newly_failing"]):
        return (
            f"the gate baseline comparison {path} records non_worsening {doc['non_worsening']!r} beside "
            f"{len(doc['newly_failing'])} newly failing test(s), which does not derive it"
        )
    return None


def build_gate_baseline_section(path: str | None) -> dict[str, Any]:
    if path is None:
        return {"presence": PRESENCE_ABSENT, "path": None, "reason": None}
    presence, doc, reason = _read_json_object(path, "gate baseline comparison")
    if presence != PRESENCE_PRESENT or doc is None:
        return {"presence": presence, "path": path, "reason": reason}
    problem = _validate_gate_baseline_shape(doc, path)
    if problem is not None:
        return {"presence": PRESENCE_UNREADABLE, "path": path, "reason": problem}
    return {
        "presence": PRESENCE_PRESENT,
        "path": path,
        "reason": None,
        "gate": doc.get("gate"),
        "baseline_outcome": doc.get("baseline_outcome"),
        "candidate_outcome": doc.get("candidate_outcome"),
        "non_worsening": doc.get("non_worsening"),
        "newly_failing": list(doc.get("newly_failing") or []),
        "fixed": list(doc.get("fixed") or []),
        "still_failing": list(doc.get("still_failing") or []),
        "candidate_failing": list(doc.get("candidate_failing") or []),
        "toolchain_drifted": doc.get("toolchain_drifted"),
    }


def build_gate_section(receipt_path: str | None, baseline_path: str | None) -> dict[str, Any]:
    receipt = build_gate_receipt_section(receipt_path)
    baseline = build_gate_baseline_section(baseline_path)
    cross_check: dict[str, Any] | None = None
    if receipt["presence"] == PRESENCE_PRESENT and baseline["presence"] == PRESENCE_PRESENT:
        cross_check = {"same_gate": receipt["gate"] == baseline["gate"]}
    return {"receipt": receipt, "baseline": baseline, "cross_check": cross_check}


# ---- the eight sealed slice-6 documents -------------------------------------------------------------
#: Every one of these eight is a SELF-CONTAINED sealed document: it declares its own schema and carries
#: its own `digest` over its own body, so it is read directly and its seal is re-derived here. None of
#: them is a hash-chained ledger, so none needs the invoke-the-sibling treatment `--wave-journal` gets.

MISSION_CONTRACT_SCHEMA = "agentic-sdlc/mission-contract@1"
PLANNING_SNAPSHOT_SCHEMA = "agentic-sdlc/planning-snapshot@1"
WAVE_PLAN_SCHEMA = "agentic-sdlc/wave-plan@1"
PLAN_DIFF_SCHEMA = "agentic-sdlc/plan-diff@1"
WAVE_PLAN_ADMISSION_SCHEMA = "agentic-sdlc/wave-plan-admission@1"
DRIFT_CLASSIFICATION_SCHEMA = "agentic-sdlc/drift-classification@1"
AUTO_ENVELOPE_SCHEMA = "agentic-sdlc/auto-envelope@1"
TRANSITION_RECEIPT_SCHEMA = "agentic-sdlc/autonomous-transition-receipt@1"

#: The one key every sealed document in this family adds to its own body, and the one this module
#: excludes BY NAME when it re-derives that document's seal.
DIGEST_KEY = "digest"

#: Three CLOSED vocabularies, each copied from the tool that owns it: `wave-plan-admission.py`'s
#: report disposition, `drift-classifier.py`'s outcome ladder, and `auto-envelope.py`'s receipt
#: verdict. A value outside one of these is `unreadable`, exactly as an unknown activation state
#: already is -- this module does not know what a fourth drift outcome would mean, and guessing would
#: be manufacturing a verdict. It never RANKS them either: the ladder order is the owning tool's, and
#: this module reports whichever value the document wrote.
#:
#: `overall_outcome` is additionally NULLABLE, and that null is load-bearing rather than missing data:
#: `drift-classifier.py` seals `overall_outcome: null` beside a `no_drift_reason` sentence for an
#: observation that names no change at all, and its own sentence says that is "not the same statement as
#: a compatible classification of a change and not a claim that nothing changed". So a null outcome is
#: projected AS null with that sentence beside it. Turning it into `compatible` here would be inventing
#: the exact verdict the producer refused to write -- and `compatible`, while inside the closed set the
#: schema allows, is unreachable from that tool's taxonomy table, so no real classification carries it.
ADMISSION_DISPOSITIONS = ("admitted", "blocked")
DRIFT_OUTCOMES = ("compatible", "revalidation-required", "replan-required", "hard-stop")
RECEIPT_VERDICTS = ("admitted", "refused")


def sealed_digest(document: dict[str, Any]) -> str:
    """This family's ONE sealed-document derivation, re-expressed and never imported: sha256 over the
    canonical bytes of the document minus `digest`, the key excluded BY NAME rather than by position.

    All eight kinds below seal themselves with exactly this function -- `mission-contract.py`'s
    `contract_digest`, `planning-snapshot.py`'s `snapshot_digest`, and the `document_digest` in
    `wave-plan-compiler.py`, `wave-plan-admission.py`, `drift-classifier.py`, and `auto-envelope.py`
    are the same three lines over the same canonical form -- so one re-derivation here covers all
    eight. Like every other digest check in this module it is TAMPER DETECTION BY RE-DERIVATION, not a
    security boundary against a same-OS-user forger.
    """
    body = {key: value for key, value in document.items() if key != DIGEST_KEY}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _need_text(value: Any, named: str) -> str:
    if not isinstance(value, str) or not value:
        raise InputError(f"carries no {named}")
    return value


def _need_int(value: Any, named: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputError(f"carries a {named} that is not an integer")
    return value


def _need_bool(value: Any, named: str) -> bool:
    if not isinstance(value, bool):
        raise InputError(f"carries a {named} that is not a boolean")
    return value


def _need_object(value: Any, named: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"carries a {named} that is not a JSON object")
    return value


def _need_entry(value: Any, named: str) -> dict[str, Any]:
    """A member of a list, named by the list it came from, so the refusal reads as a sentence."""
    if not isinstance(value, dict):
        raise InputError(f"carries an entry in {named} that is not a JSON object")
    return value


def _need_list(value: Any, named: str) -> list[Any]:
    if not isinstance(value, list):
        raise InputError(f"carries a {named} that is not a list")
    return value


def _need_texts(value: Any, named: str) -> list[str]:
    items = _need_list(value, named)
    if any(not isinstance(item, str) or not item for item in items):
        raise InputError(f"carries a {named} that is not a list of non-empty strings")
    return list(items)


def _need_member(value: Any, named: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise InputError(f"carries {named} {value!r}, which is not one of the closed set {list(allowed)}")
    return str(value)


def _optional_text(value: Any) -> str | None:
    """A field the owning schema itself declares nullable (`supersedes`, `no_delta_reason`,
    `no_drift_reason`, a detached head's `branch`): absent and null are the same answer here."""
    return value if isinstance(value, str) and value else None


def _project_mission_contract(document: dict[str, Any]) -> dict[str, Any]:
    authority = _need_object(document.get("authority"), "authority")
    scope = _need_object(document.get("scope"), "scope")
    completion = _need_object(document.get("completion_contract"), "completion_contract")
    return {
        "mission_id": _need_text(document.get("mission_id"), "mission_id"),
        "objective": _need_text(document.get("objective"), "objective"),
        "revision": _need_int(document.get("revision"), "revision"),
        "stated_at": _need_text(document.get("stated_at"), "stated_at"),
        "authority_ceiling": _need_text(authority.get("ceiling"), "authority.ceiling"),
        "admitted_authority_classes": _need_texts(authority.get("admitted_classes"), "authority.admitted_classes"),
        "stop_conditions": _need_texts(document.get("stop_conditions"), "stop_conditions"),
        "in_scope": _need_texts(scope.get("in_scope"), "scope.in_scope"),
        "non_goals": _need_texts(scope.get("non_goals"), "scope.non_goals"),
        "success_criteria": _need_texts(completion.get("success_criteria"), "completion_contract.success_criteria"),
        "terminal_criteria": _need_texts(completion.get("terminal_criteria"), "completion_contract.terminal_criteria"),
        "supersedes": _optional_text(document.get("supersedes")),
    }


def _bluf_mission_contract(section: dict[str, Any]) -> str:
    return (
        f"mission {_flat(section['mission_id'])} revision {section['revision']}: "
        f"{_flat(section['objective'])}"
    )


def _detail_mission_contract(section: dict[str, Any]) -> list[str]:
    return [
        f"  mission_id={_flat(section['mission_id'])} revision={section['revision']} "
        f"stated_at={_flat(section['stated_at'])}",
        f"  objective: {_flat(section['objective'])}",
        f"  authority_ceiling={_flat(section['authority_ceiling'])} "
        f"admitted_authority_classes={_flat(section['admitted_authority_classes'])}",
        f"  stop_conditions={_flat(section['stop_conditions'])}",
        f"  in_scope={_flat(section['in_scope'])} non_goals={_flat(section['non_goals'])}",
        f"  success_criteria={_flat(section['success_criteria'])}",
        f"  terminal_criteria={_flat(section['terminal_criteria'])}",
        f"  supersedes={_flat(section['supersedes'])}",
    ]


def _project_planning_snapshot(document: dict[str, Any]) -> dict[str, Any]:
    head = _need_object(document.get("head"), "head")
    dirty = _need_object(document.get("dirty_state"), "dirty_state")
    queue = _need_object(document.get("queue"), "queue")
    dimensions: list[str] = []
    for entry in _need_list(document.get("unknowns"), "unknowns"):
        dimensions.append(_need_text(_need_entry(entry, "unknowns").get("dimension"), "an unknown's dimension"))
    return {
        "stated_at": _need_text(document.get("stated_at"), "stated_at"),
        "branch": _optional_text(head.get("branch")),
        "commit_sha": _need_text(head.get("commit_sha"), "head.commit_sha"),
        "tree_sha": _need_text(head.get("tree_sha"), "head.tree_sha"),
        "dirty_state": {
            key: _need_int(dirty.get(key), f"dirty_state.{key}")
            for key in ("staged", "unstaged", "untracked", "unmerged")
        },
        "worktree_count": len(_need_list(document.get("worktrees"), "worktrees")),
        "wave_artifact_count": len(_need_list(document.get("wave_artifacts"), "wave_artifacts")),
        "policy_digest_count": len(_need_list(document.get("policy_digests"), "policy_digests")),
        "queue_state": _need_text(queue.get("state"), "queue.state"),
        "unknown_dimensions": dimensions,
    }


def _bluf_planning_snapshot(section: dict[str, Any]) -> str:
    return (
        f"planning snapshot stated at {_flat(section['stated_at'])}: head {_flat(section['branch'])} "
        f"{_flat(section['commit_sha'])}, {len(section['unknown_dimensions'])} unknown dimension(s) recorded"
    )


def _detail_planning_snapshot(section: dict[str, Any]) -> list[str]:
    dirty = section["dirty_state"]
    return [
        f"  stated_at={_flat(section['stated_at'])} branch={_flat(section['branch'])} "
        f"commit_sha={_flat(section['commit_sha'])} tree_sha={_flat(section['tree_sha'])}",
        f"  dirty_state staged={dirty['staged']} unstaged={dirty['unstaged']} untracked={dirty['untracked']} "
        f"unmerged={dirty['unmerged']}",
        f"  worktree_count={section['worktree_count']} wave_artifact_count={section['wave_artifact_count']} "
        f"policy_digest_count={section['policy_digest_count']} queue_state={_flat(section['queue_state'])}",
        f"  unknown_dimensions={_flat(section['unknown_dimensions'])}",
    ]


def _project_wave_plan(document: dict[str, Any]) -> dict[str, Any]:
    inputs = _need_object(document.get("inputs"), "inputs")
    head = _need_object(document.get("head"), "head")
    limits = _need_object(document.get("limits"), "limits")
    node_ids: list[str] = []
    for entry in _need_list(document.get("nodes"), "nodes"):
        node_ids.append(_need_text(_need_entry(entry, "nodes").get("node_id"), "a node's node_id"))
    return {
        "mission_id": _need_text(document.get("mission_id"), "mission_id"),
        "revision": _need_int(document.get("revision"), "revision"),
        "compiled_at": _need_text(document.get("compiled_at"), "compiled_at"),
        "declared_concurrency": _need_int(document.get("declared_concurrency"), "declared_concurrency"),
        "node_ids": node_ids,
        "edge_count": len(_need_list(document.get("edges"), "edges")),
        "mission_digest": _need_text(inputs.get("mission_digest"), "inputs.mission_digest"),
        "snapshot_digest": _need_text(inputs.get("snapshot_digest"), "inputs.snapshot_digest"),
        "head_commit_sha": _need_text(head.get("commit_sha"), "head.commit_sha"),
        "max_concurrent_nodes": _need_int(limits.get("max_concurrent_nodes"), "limits.max_concurrent_nodes"),
        "max_total_nodes": _need_int(limits.get("max_total_nodes"), "limits.max_total_nodes"),
        "supersedes": _optional_text(document.get("supersedes")),
    }


def _bluf_wave_plan(section: dict[str, Any]) -> str:
    return (
        f"wave plan revision {section['revision']} for mission {_flat(section['mission_id'])}: "
        f"{len(section['node_ids'])} node(s), {section['edge_count']} edge(s), declared concurrency "
        f"{section['declared_concurrency']}"
    )


def _detail_wave_plan(section: dict[str, Any]) -> list[str]:
    return [
        f"  mission_id={_flat(section['mission_id'])} revision={section['revision']} "
        f"compiled_at={_flat(section['compiled_at'])} supersedes={_flat(section['supersedes'])}",
        f"  node_ids={_flat(section['node_ids'])} edge_count={section['edge_count']}",
        f"  declared_concurrency={section['declared_concurrency']} "
        f"max_concurrent_nodes={section['max_concurrent_nodes']} "
        f"max_total_nodes={section['max_total_nodes']}",
        f"  mission_digest={_flat(section['mission_digest'])} "
        f"snapshot_digest={_flat(section['snapshot_digest'])}",
        f"  head_commit_sha={_flat(section['head_commit_sha'])}",
    ]


def _project_plan_diff(document: dict[str, Any]) -> dict[str, Any]:
    kinds: list[str] = []
    semantic = 0
    changes = _need_list(document.get("changes"), "changes")
    for entry in changes:
        change = _need_entry(entry, "changes")
        kinds.append(_need_text(change.get("kind"), "a change's kind"))
        if _need_bool(change.get("semantic"), "a change's semantic"):
            semantic += 1
    return {
        "mission_id": _need_text(document.get("mission_id"), "mission_id"),
        "compiled_at": _need_text(document.get("compiled_at"), "compiled_at"),
        "plan_digest": _need_text(document.get("plan_digest"), "plan_digest"),
        "prior_plan_digest": _optional_text(document.get("prior_plan_digest")),
        "change_count": len(changes),
        "semantic_change_count": semantic,
        "change_kinds": sorted(set(kinds)),
        "no_delta_reason": _optional_text(document.get("no_delta_reason")),
    }


def _bluf_plan_diff(section: dict[str, Any]) -> str:
    if section["no_delta_reason"] is not None:
        return f"plan diff: {_flat(section['no_delta_reason'])}"
    return (
        f"plan diff for plan {_flat(section['plan_digest'])}: {section['change_count']} change(s), "
        f"{section['semantic_change_count']} semantic, kinds {_flat(section['change_kinds'])}"
    )


def _detail_plan_diff(section: dict[str, Any]) -> list[str]:
    return [
        f"  mission_id={_flat(section['mission_id'])} compiled_at={_flat(section['compiled_at'])}",
        f"  plan_digest={_flat(section['plan_digest'])} prior_plan_digest={_flat(section['prior_plan_digest'])}",
        f"  change_count={section['change_count']} semantic_change_count={section['semantic_change_count']} "
        f"change_kinds={_flat(section['change_kinds'])}",
        f"  no_delta_reason={_flat(section['no_delta_reason'])}",
    ]


def _project_wave_plan_admission(document: dict[str, Any]) -> dict[str, Any]:
    inputs = _need_object(document.get("inputs"), "inputs")
    observed = _need_object(document.get("observed"), "observed")
    observed_head = _need_object(observed.get("head"), "observed.head")
    met: list[str] = []
    unmet: list[str] = []
    blockers: list[str] = []
    for entry in _need_list(document.get("checks"), "checks"):
        check = _need_entry(entry, "checks")
        slug = _need_text(check.get("slug"), "a check's slug")
        (met if _need_bool(check.get("met"), f"the {slug} check's met") else unmet).append(slug)
        blockers.extend(_need_texts(check.get("blockers"), f"the {slug} check's blockers"))
    deferred: list[str] = []
    for entry in _need_list(document.get("deferred_dimensions"), "deferred_dimensions"):
        dimension = _need_entry(entry, "deferred_dimensions")
        deferred.append(_need_text(dimension.get("dimension"), "a deferred dimension's name"))
    return {
        "disposition": _need_member(document.get("disposition"), "disposition", ADMISSION_DISPOSITIONS),
        "admitted_at": _need_text(document.get("admitted_at"), "admitted_at"),
        "mission_id": _need_text(document.get("mission_id"), "mission_id"),
        "plan_revision": _need_int(document.get("plan_revision"), "plan_revision"),
        "plan_digest": _need_text(inputs.get("plan_digest"), "inputs.plan_digest"),
        "snapshot_digest": _need_text(inputs.get("snapshot_digest"), "inputs.snapshot_digest"),
        "observed_commit_sha": _need_text(observed_head.get("commit_sha"), "observed.head.commit_sha"),
        "observed_snapshot_stated_at": _need_text(
            observed.get("snapshot_stated_at"), "observed.snapshot_stated_at"
        ),
        "checks_met": met,
        "checks_not_met": unmet,
        "blockers": blockers,
        "deferred_dimensions": deferred,
    }


def _bluf_wave_plan_admission(section: dict[str, Any]) -> str:
    return (
        f"wave plan admission disposition: {_flat(section['disposition'])} -- "
        f"{len(section['checks_met'])} check(s) met, {len(section['checks_not_met'])} not met, "
        f"{len(section['blockers'])} blocker(s), {len(section['deferred_dimensions'])} deferred dimension(s)"
    )


def _detail_wave_plan_admission(section: dict[str, Any]) -> list[str]:
    lines = [
        f"  disposition={_flat(section['disposition'])} admitted_at={_flat(section['admitted_at'])} "
        f"mission_id={_flat(section['mission_id'])} plan_revision={section['plan_revision']}",
        f"  checks_met={_flat(section['checks_met'])}",
        f"  checks_not_met={_flat(section['checks_not_met'])}",
        f"  plan_digest={_flat(section['plan_digest'])} snapshot_digest={_flat(section['snapshot_digest'])}",
        f"  observed_commit_sha={_flat(section['observed_commit_sha'])} "
        f"observed_snapshot_stated_at={_flat(section['observed_snapshot_stated_at'])}",
        f"  deferred_dimensions={_flat(section['deferred_dimensions'])}",
    ]
    lines.extend(f"  blocker: {_flat(blocker)}" for blocker in section["blockers"])
    return lines


def _project_drift_classification(document: dict[str, Any]) -> dict[str, Any]:
    binding = _need_object(document.get("binding"), "binding")
    assessments: list[dict[str, Any]] = []
    for entry in _need_list(document.get("assessments"), "assessments"):
        assessment = _need_entry(entry, "assessments")
        assessments.append(
            {
                "kind": _need_text(assessment.get("kind"), "an assessment's kind"),
                "subject": _need_text(assessment.get("subject"), "an assessment's subject"),
                "outcome": _need_member(assessment.get("outcome"), "an assessment's outcome", DRIFT_OUTCOMES),
            }
        )
    no_drift_reason = _optional_text(document.get("no_drift_reason"))
    recorded_outcome = document.get("overall_outcome")
    if recorded_outcome is None and no_drift_reason is None:
        raise InputError("records neither an overall_outcome nor a no_drift_reason, so it says nothing at all")
    outcome = None if recorded_outcome is None else _need_member(recorded_outcome, "overall_outcome", DRIFT_OUTCOMES)
    return {
        "overall_outcome": outcome,
        "classified_at": _need_text(document.get("classified_at"), "classified_at"),
        "mission_id": _need_text(document.get("mission_id"), "mission_id"),
        "plan_digest": _need_text(document.get("plan_digest"), "plan_digest"),
        "plan_revision": _need_int(document.get("plan_revision"), "plan_revision"),
        "observation_id": _need_text(document.get("observation_id"), "observation_id"),
        "observed_at": _need_text(document.get("observed_at"), "observed_at"),
        "bound": _need_bool(binding.get("bound"), "binding.bound"),
        "binding_ground": _optional_text(binding.get("ground")),
        "assessments": assessments,
        "no_drift_reason": no_drift_reason,
    }


def _bluf_drift_classification(section: dict[str, Any]) -> str:
    """A null outcome gets the document's OWN no-drift sentence, never a substituted verdict."""
    if section["overall_outcome"] is None:
        return (
            f"drift classification of plan revision {section['plan_revision']} records NO overall "
            f"outcome: {_flat(section['no_drift_reason'])}"
        )
    return (
        f"drift classification overall outcome: {_flat(section['overall_outcome'])} over "
        f"{len(section['assessments'])} assessment(s) of plan revision {section['plan_revision']}"
    )


def _detail_drift_classification(section: dict[str, Any]) -> list[str]:
    lines = [
        f"  overall_outcome={_flat(section['overall_outcome'])} classified_at={_flat(section['classified_at'])} "
        f"mission_id={_flat(section['mission_id'])}",
        f"  plan_digest={_flat(section['plan_digest'])} plan_revision={section['plan_revision']}",
        f"  observation_id={_flat(section['observation_id'])} observed_at={_flat(section['observed_at'])} "
        f"bound={section['bound']}",
        f"  binding_ground={_flat(section['binding_ground'])} no_drift_reason={_flat(section['no_drift_reason'])}",
    ]
    lines.extend(
        f"  assessment: kind={_flat(entry['kind'])} subject={_flat(entry['subject'])} "
        f"outcome={_flat(entry['outcome'])}"
        for entry in section["assessments"]
    )
    return lines


def _project_auto_envelope(document: dict[str, Any]) -> dict[str, Any]:
    bound = _need_object(document.get("bound_plan"), "bound_plan")
    window = _need_object(document.get("validity_window"), "validity_window")
    concurrency = _need_object(document.get("concurrency_limits"), "concurrency_limits")
    retry = _need_object(document.get("retry_policy"), "retry_policy")
    egress = _need_object(document.get("egress_allowlist"), "egress_allowlist")
    gated: list[str] = []
    for entry in _need_list(document.get("checkpoints"), "checkpoints"):
        checkpoint = _need_entry(entry, "checkpoints")
        kind = _need_text(checkpoint.get("kind"), "a checkpoint's kind")
        if _need_bool(checkpoint.get("requires_human_disposition"), f"the {kind} checkpoint's requirement"):
            gated.append(kind)
    return {
        "envelope_id": _need_text(document.get("envelope_id"), "envelope_id"),
        "stated_at": _need_text(document.get("stated_at"), "stated_at"),
        "bound_plan_digest": _need_text(bound.get("plan_digest"), "bound_plan.plan_digest"),
        "bound_plan_revision": _need_int(bound.get("plan_revision"), "bound_plan.plan_revision"),
        "bound_snapshot_digest": _need_text(bound.get("snapshot_digest"), "bound_plan.snapshot_digest"),
        "not_before": _need_text(window.get("not_before"), "validity_window.not_before"),
        "not_after": _need_text(window.get("not_after"), "validity_window.not_after"),
        "allowed_authority_classes": _need_texts(
            document.get("allowed_authority_classes"), "allowed_authority_classes"
        ),
        "allowed_effect_classes": _need_texts(document.get("allowed_effect_classes"), "allowed_effect_classes"),
        "tool_allowlist": _need_texts(document.get("tool_allowlist"), "tool_allowlist"),
        "graph_change_allowlist": _need_texts(document.get("graph_change_allowlist"), "graph_change_allowlist"),
        "egress_posture": _need_text(egress.get("posture"), "egress_allowlist.posture"),
        "egress_destinations": _need_texts(egress.get("destinations"), "egress_allowlist.destinations"),
        "max_concurrent_nodes": _need_int(
            concurrency.get("max_concurrent_nodes"), "concurrency_limits.max_concurrent_nodes"
        ),
        "max_recursion_generations": _need_int(
            concurrency.get("max_recursion_generations"), "concurrency_limits.max_recursion_generations"
        ),
        "max_attempts_per_node": _need_int(retry.get("max_attempts_per_node"), "retry_policy.max_attempts_per_node"),
        "max_total_retries": _need_int(retry.get("max_total_retries"), "retry_policy.max_total_retries"),
        "stop_rules": _need_texts(document.get("stop_rules"), "stop_rules"),
        "checkpoints_requiring_human_disposition": gated,
    }


def _bluf_auto_envelope(section: dict[str, Any]) -> str:
    """The window is stated, never evaluated: this module reads no clock, so it can say what
    `validity_window` records and must not say the window is open."""
    return (
        f"auto envelope {_flat(section['envelope_id'])}: validity window "
        f"{_flat(section['not_before'])} .. {_flat(section['not_after'])}, bound to plan revision "
        f"{section['bound_plan_revision']}"
    )


def _detail_auto_envelope(section: dict[str, Any]) -> list[str]:
    return [
        f"  envelope_id={_flat(section['envelope_id'])} stated_at={_flat(section['stated_at'])}",
        f"  not_before={_flat(section['not_before'])} not_after={_flat(section['not_after'])}",
        f"  bound_plan_digest={_flat(section['bound_plan_digest'])} "
        f"bound_plan_revision={section['bound_plan_revision']} "
        f"bound_snapshot_digest={_flat(section['bound_snapshot_digest'])}",
        f"  allowed_authority_classes={_flat(section['allowed_authority_classes'])}",
        f"  allowed_effect_classes={_flat(section['allowed_effect_classes'])}",
        f"  tool_allowlist={_flat(section['tool_allowlist'])} "
        f"graph_change_allowlist={_flat(section['graph_change_allowlist'])}",
        f"  egress_posture={_flat(section['egress_posture'])} "
        f"egress_destinations={_flat(section['egress_destinations'])}",
        f"  max_concurrent_nodes={section['max_concurrent_nodes']} "
        f"max_recursion_generations={section['max_recursion_generations']}",
        f"  max_attempts_per_node={section['max_attempts_per_node']} "
        f"max_total_retries={section['max_total_retries']}",
        f"  stop_rules={_flat(section['stop_rules'])}",
        f"  checkpoints_requiring_human_disposition="
        f"{_flat(section['checkpoints_requiring_human_disposition'])}",
    ]


def _project_transition_receipt(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": _need_member(document.get("verdict"), "verdict", RECEIPT_VERDICTS),
        "at": _need_text(document.get("at"), "at"),
        "envelope_digest": _need_text(document.get("envelope_digest"), "envelope_digest"),
        "transition_digest": _need_text(document.get("transition_digest"), "transition_digest"),
        "reasons": _need_texts(document.get("reasons"), "reasons"),
    }


def _bluf_transition_receipt(section: dict[str, Any]) -> str:
    return (
        f"autonomous transition receipt verdict: {_flat(section['verdict'])} at {_flat(section['at'])} "
        f"({len(section['reasons'])} reason(s))"
    )


def _detail_transition_receipt(section: dict[str, Any]) -> list[str]:
    lines = [
        f"  verdict={_flat(section['verdict'])} at={_flat(section['at'])}",
        f"  envelope_digest={_flat(section['envelope_digest'])} "
        f"transition_digest={_flat(section['transition_digest'])}",
    ]
    lines.extend(f"  reason: {_flat(reason)}" for reason in section["reasons"])
    return lines


class SealedReader(NamedTuple):
    """One row of the sealed-document half of the reader registry.

    `kind` is simultaneously the `artifacts` key, the argparse dest, and (with underscores turned into
    hyphens) the flag name, so a row cannot drift from its own flag. `schema` is the MATCHER -- the
    exact string the document must declare -- and `sealed_digest` is the parser's one check beyond
    JSON well-formedness. `project` states the document's own fields in its own vocabulary; `headline`
    and `detail` render those already-projected fields and read no document themselves, so neither can
    smuggle in a fact the projector did not record.
    """

    kind: str
    label: str
    schema: str
    help: str
    project: Any
    headline: Any
    detail: Any


SEALED_READERS: tuple[SealedReader, ...] = (
    SealedReader(
        kind="mission_contract",
        label="mission contract",
        schema=MISSION_CONTRACT_SCHEMA,
        help="path to a sealed mission-contract.py contract",
        project=_project_mission_contract,
        headline=_bluf_mission_contract,
        detail=_detail_mission_contract,
    ),
    SealedReader(
        kind="planning_snapshot",
        label="planning snapshot",
        schema=PLANNING_SNAPSHOT_SCHEMA,
        help="path to a sealed planning-snapshot.py capture",
        project=_project_planning_snapshot,
        headline=_bluf_planning_snapshot,
        detail=_detail_planning_snapshot,
    ),
    SealedReader(
        kind="wave_plan",
        label="wave plan",
        schema=WAVE_PLAN_SCHEMA,
        help="path to a sealed wave-plan-compiler.py compiled plan",
        project=_project_wave_plan,
        headline=_bluf_wave_plan,
        detail=_detail_wave_plan,
    ),
    SealedReader(
        kind="plan_diff",
        label="plan diff",
        schema=PLAN_DIFF_SCHEMA,
        help="path to a sealed wave-plan-compiler.py plan diff",
        project=_project_plan_diff,
        headline=_bluf_plan_diff,
        detail=_detail_plan_diff,
    ),
    SealedReader(
        kind="wave_plan_admission",
        label="wave plan admission report",
        schema=WAVE_PLAN_ADMISSION_SCHEMA,
        help="path to a sealed wave-plan-admission.py report",
        project=_project_wave_plan_admission,
        headline=_bluf_wave_plan_admission,
        detail=_detail_wave_plan_admission,
    ),
    SealedReader(
        kind="drift_classification",
        label="drift classification",
        schema=DRIFT_CLASSIFICATION_SCHEMA,
        help="path to a sealed drift-classifier.py classification",
        project=_project_drift_classification,
        headline=_bluf_drift_classification,
        detail=_detail_drift_classification,
    ),
    SealedReader(
        kind="auto_envelope",
        label="auto envelope",
        schema=AUTO_ENVELOPE_SCHEMA,
        help="path to a sealed auto-envelope.py envelope",
        project=_project_auto_envelope,
        headline=_bluf_auto_envelope,
        detail=_detail_auto_envelope,
    ),
    SealedReader(
        kind="transition_receipt",
        label="autonomous transition receipt",
        schema=TRANSITION_RECEIPT_SCHEMA,
        help="path to a sealed auto-envelope.py autonomous-transition receipt",
        project=_project_transition_receipt,
        headline=_bluf_transition_receipt,
        detail=_detail_transition_receipt,
    ),
)

SEALED_READERS_BY_KIND: dict[str, SealedReader] = {reader.kind: reader for reader in SEALED_READERS}


def flag_for(kind: str) -> str:
    return "--" + kind.replace("_", "-")


def build_sealed_section(path: str | None, reader: SealedReader) -> dict[str, Any]:
    """The one path every sealed kind takes: read, match the schema, re-derive the seal, project.

    Each step can only downgrade the input to `unreadable` WITH a reason naming this kind, and every
    other input keeps its own independent outcome.
    """
    if path is None:
        return {"presence": PRESENCE_ABSENT, "path": None, "reason": None}
    presence, doc, reason = _read_json_object(path, reader.label)
    if presence != PRESENCE_PRESENT or doc is None:
        return {"presence": presence, "path": path, "reason": reason}
    declared = doc.get("schema")
    if declared != reader.schema:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": f"the {reader.label} {path} declares schema {declared!r}, not {reader.schema!r}",
        }
    recorded = doc.get(DIGEST_KEY)
    if not isinstance(recorded, str) or not recorded:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": f"the {reader.label} {path} carries no digest, so its seal cannot be re-derived",
        }
    if sealed_digest(doc) != recorded:
        return {
            "presence": PRESENCE_UNREADABLE,
            "path": path,
            "reason": f"the {reader.label} {path} does not verify: its digest does not re-derive",
        }
    try:
        fields = reader.project(doc)
    except InputError as exc:
        return {"presence": PRESENCE_UNREADABLE, "path": path, "reason": f"the {reader.label} {path} {exc}"}
    return {"presence": PRESENCE_PRESENT, "path": path, "reason": None, **fields}


def _sealed_builder(reader: SealedReader) -> Any:
    """A factory, not an inline lambda: a lambda closing over the loop variable would bind the LAST
    reader for every row."""
    return lambda args: build_sealed_section(getattr(args, reader.kind), reader)


def sealed_bluf(reader: SealedReader, section: dict[str, Any]) -> str | None:
    """Absent and unreadable are worded identically for all eight kinds; only the present line differs,
    which is why a row supplies `headline` alone."""
    if section["presence"] == PRESENCE_ABSENT:
        return None
    if section["presence"] == PRESENCE_UNREADABLE:
        return f"the {reader.label} is unreadable: {_flat(section['reason'])}"
    return reader.headline(section)


def _sealed_bluf_row(kind: str) -> tuple[str, Any]:
    reader = SEALED_READERS_BY_KIND[kind]
    return kind, lambda section: sealed_bluf(reader, section)


def render_sealed_section(reader: SealedReader, section: dict[str, Any]) -> list[str]:
    lines = [f"== {reader.label} ==", _presence_line(reader.label, section)]
    if section["presence"] == PRESENCE_PRESENT:
        lines.extend(reader.detail(section))
    lines.append("")
    return lines


# ---- the table-driven reader registry --------------------------------------------------------------
#: One entry per artifact kind: how to build its section from the parsed CLI arguments. Iterated in
#: this fixed order both to assemble `artifacts` and, separately, to pick the BLUF line -- adding a
#: kind is one more row here, never a rewrite of this loop. The eight sealed slice-6 kinds are
#: appended from `SEALED_READERS` rather than spelled out twice.
ARTIFACT_KINDS: tuple[tuple[str, Any], ...] = (
    ("wave_journal", lambda args: build_wave_journal_section(args.wave_journal)),
    ("runtime_assignment", lambda args: build_runtime_assignment_section(args.runtime_assignment)),
    ("activation_result", lambda args: build_activation_result_section(args.activation_result)),
    ("gate", lambda args: build_gate_section(args.gate_receipt, args.gate_baseline)),
) + tuple((reader.kind, _sealed_builder(reader)) for reader in SEALED_READERS)


def build_artifacts(args: argparse.Namespace) -> dict[str, Any]:
    return {kind: builder(args) for kind, builder in ARTIFACT_KINDS}


# ---- BLUF selection ---------------------------------------------------------------------------------


def _flat(value: Any) -> str:
    """Render one ARTIFACT-DERIVED value for a single-line view. A string is passed through
    `json.dumps` and de-quoted, which escapes every C0 control character -- `\\n`, `\\r`, and the
    rest -- so a gate label or reason string that itself carries a newline can never fold a forged
    line into `render_human` or a BLUF line, above or below the evidence notice. A non-string value
    (bool, int, None, or a list/dict of them) has no bare-newline hazard of its own -- Python's
    `str()` of a container already renders its string elements via `repr`, which escapes the same
    characters -- so it is rendered with plain `str()`. Field names and literals this module itself
    writes are never passed through here: only a value read from an artifact is."""
    if isinstance(value, str):
        return json.dumps(value)[1:-1]
    return str(value)


def _bluf_activation_result(section: dict[str, Any]) -> str | None:
    if section["presence"] == PRESENCE_ABSENT:
        return None
    if section["presence"] == PRESENCE_UNREADABLE:
        return f"the activation result document is unreadable: {_flat(section['reason'])}"
    return f"activation state: {_flat(section['state'])} -- {_flat(section['consequence'])}"


def _bluf_gate(section: dict[str, Any]) -> str | None:
    """The gate rung's own two-leaf order, and the one rule the whole ladder already follows: an
    UNREADABLE leaf outranks a PRESENT one, because "I could not read this" is the most
    decision-relevant thing that leaf has to say. The RECEIPT is named first of the two: it is the
    primary evidence, and a comparison is a document derived from it, so a present comparison beside an
    unreadable receipt is a comparison whose own candidate this module could not verify.

    A present comparison then leads with the candidate's OWN recorded outcome before the subset
    verdict, because `non_worsening` answers "did this change break something new", never "did the gate
    pass": a failed gate whose every failure is pre-existing is honestly non-worsening AND honestly
    failed, and a BLUF that printed only the second word would read as a pass."""
    receipt, baseline = section["receipt"], section["baseline"]
    if receipt["presence"] == PRESENCE_ABSENT and baseline["presence"] == PRESENCE_ABSENT:
        return None
    if receipt["presence"] == PRESENCE_UNREADABLE:
        return f"the gate receipt is unreadable: {_flat(receipt['reason'])}"
    if baseline["presence"] == PRESENCE_UNREADABLE:
        return f"the gate baseline comparison is unreadable: {_flat(baseline['reason'])}"
    if baseline["presence"] == PRESENCE_PRESENT:
        verdict_word = "non-worsening" if baseline["non_worsening"] else "WORSENED"
        return (
            f"gate {_flat(baseline['gate'])}: candidate outcome {_flat(baseline['candidate_outcome'])}, "
            f"{verdict_word} against its baseline ({len(baseline['newly_failing'])} newly failing)"
        )
    return f"gate {_flat(receipt['gate'])}: outcome {_flat(receipt['outcome'])}"


def _bluf_runtime_assignment(section: dict[str, Any]) -> str | None:
    if section["presence"] == PRESENCE_ABSENT:
        return None
    if section["presence"] == PRESENCE_UNREADABLE:
        return f"the runtime-assignment report is unreadable: {_flat(section['reason'])}"
    return (
        f"runtime-assignment {_flat(section['command'])} verdict: {_flat(section['verdict'])} -- "
        f"{_flat(section['consequence'])}"
    )


def _bluf_wave_journal(section: dict[str, Any]) -> str | None:
    if section["presence"] == PRESENCE_ABSENT:
        return None
    if section["presence"] == PRESENCE_UNREADABLE:
        return f"the wave journal is unreadable: {_flat(section['reason'])}"
    if section["complete"]:
        return f"wave {_flat(section['wave_id'])}: every required node carries a disposition"
    missing = section["required_nodes_without_disposition"]
    return f"wave {_flat(section['wave_id'])}: {len(missing)} required node(s) missing a disposition: {_flat(missing)}"


#: The one admission disposition that STOPS this wave. Split out by name rather than written inline,
#: because it is the whole reason the admission kind occupies two rungs below.
ADMISSION_STOPPING_DISPOSITIONS = ("blocked",)


def _bluf_admission_stop(section: dict[str, Any]) -> str | None:
    """The admission's HIGH rung: a report this module could not read at all, or one whose own
    disposition stops this wave. Nothing else claims this rung."""
    if section["presence"] == PRESENCE_ABSENT:
        return None
    reader = SEALED_READERS_BY_KIND["wave_plan_admission"]
    if section["presence"] == PRESENCE_UNREADABLE:
        return sealed_bluf(reader, section)
    if section["disposition"] in ADMISSION_STOPPING_DISPOSITIONS:
        return reader.headline(section)
    return None


def _bluf_admission_permission(section: dict[str, Any]) -> str | None:
    """The admission's LOW rung. `admitted` is a permission for THIS wave to start, and the report
    itself says `admitted` is not `approved`, so it subsumes NEITHER whether the plan the wave is
    running is still that plan (the drift classification) NOR whether the repository's own gate passed
    -- it is only reachable here for a present report the high rung did not claim, which the closed
    two-value vocabulary makes `admitted` and an unrecognised third value makes `unreadable` up
    there. This rung still outranks a runtime assignment and everything below it, because admitting a
    whole wave plan is wider than one node's spawn."""
    if section["presence"] != PRESENCE_PRESENT:
        return None
    return SEALED_READERS_BY_KIND["wave_plan_admission"].headline(section)


#: Priority order for the single most decision-relevant line: each fact subsumes the ones after it, so
#: the FIRST rung that has anything to say wins and the rest are read from the per-artifact sections
#: below it. An unreadable input is something to say, so it outranks every PRESENT kind below it.
#:
#: The verdict-carrying kinds come first, widest consequence first: a refused activation means no wave
#: may write at all; a blocked admission report means THIS wave may not start, which subsumes what its
#: plan then drifted into; a hard-stop drift classification means the plan the wave is running is no
#: longer the plan; the gate is the repository's own pass/fail; a runtime assignment decides one node's
#: spawn; a transition receipt decides one proposed autonomous step inside a wave; and a missing node
#: disposition in the journal is the narrowest of them. The five descriptive kinds follow in the
#: family's own chain order -- MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff ->
#: AutoEnvelope -- because none of them carries a verdict at all: they say what was intended, observed,
#: compiled, changed, and bounded, and any of them can still headline when it is all the caller has.
#:
#: ONE kind holds TWO rungs, and the subsumption sentence above is exactly why. "A blocked admission
#: report means this wave may not start" justifies the high rung and says nothing about `admitted`: a
#: report that PERMITS the wave to start does not subsume a hard-stop drift classification saying the
#: plan is no longer the plan, nor a failed gate. So the stopping disposition keeps the rung its
#: consequence earns and the permitting one drops below both, to just above the runtime assignment.
#: That is not this module ranking one document's verdict against another's: the drift ladder stays
#: `drift-classifier.py`'s (whichever outcome it wrote is projected verbatim, and no outcome is ranked
#: against another here), and the only value read is the admission's own closed two-value disposition,
#: from the report that itself says `admitted` is not `approved`.
BLUF_ORDER: tuple[tuple[str, Any], ...] = (
    ("activation_result", _bluf_activation_result),
    ("wave_plan_admission", _bluf_admission_stop),
    _sealed_bluf_row("drift_classification"),
    ("gate", _bluf_gate),
    ("wave_plan_admission", _bluf_admission_permission),
    ("runtime_assignment", _bluf_runtime_assignment),
    _sealed_bluf_row("transition_receipt"),
    ("wave_journal", _bluf_wave_journal),
    _sealed_bluf_row("mission_contract"),
    _sealed_bluf_row("planning_snapshot"),
    _sealed_bluf_row("wave_plan"),
    _sealed_bluf_row("plan_diff"),
    _sealed_bluf_row("auto_envelope"),
)


def _leaf_sections(artifacts: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """The thirteen independently-supplied paths, gate's receipt/baseline split out of its section --
    the same granularity `--gate-receipt`/`--gate-baseline` are supplied at."""
    gate = artifacts["gate"]
    return (
        artifacts["wave_journal"],
        artifacts["runtime_assignment"],
        artifacts["activation_result"],
        gate["receipt"],
        gate["baseline"],
    ) + tuple(artifacts[reader.kind] for reader in SEALED_READERS)


def compute_bluf(artifacts: dict[str, Any]) -> str:
    for kind, line_for in BLUF_ORDER:
        line = line_for(artifacts[kind])
        if line is not None:
            return line
    # Every leaf reachable here is PRESENCE_ABSENT (any PRESENT or UNREADABLE one would already
    # have produced a line above) -- so "supplied" and "missing" coincide, and the only question
    # left is whether the caller supplied a path at all.
    supplied = sum(1 for section in _leaf_sections(artifacts) if section["path"] is not None)
    if supplied == 0:
        return "no observability artifact was supplied: nothing to project"
    return f"every supplied artifact path is missing ({supplied} path(s) supplied): nothing to project"


def build_document(args: argparse.Namespace) -> dict[str, Any]:
    artifacts = build_artifacts(args)
    return {
        "schema": RESULT_SCHEMA,
        "command": "project",
        "status": "projected",
        "exit_code": EXIT_OK,
        "evidence_notice": EVIDENCE_NOTICE,
        "bluf": compute_bluf(artifacts),
        "artifacts": artifacts,
    }


# ---- human rendering --------------------------------------------------------------------------------


def _presence_line(label: str, section: dict[str, Any]) -> str:
    presence = section["presence"]
    path = section["path"]
    if presence == PRESENCE_ABSENT:
        if path is None:
            return f"{label}: not supplied"
        return f"{label}: MISSING ({_flat(path)}): the supplied path does not exist"
    if presence == PRESENCE_UNREADABLE:
        return f"{label}: UNREADABLE ({_flat(path)}): {_flat(section['reason'])}"
    return f"{label}: present ({_flat(path)})"


def render_human(document: dict[str, Any]) -> str:
    artifacts = document["artifacts"]
    lines = [f"BLUF: {document['bluf']}", "", document["evidence_notice"], ""]

    wave_journal = artifacts["wave_journal"]
    lines.append("== wave journal ==")
    lines.append(_presence_line("wave journal", wave_journal))
    if wave_journal["presence"] == PRESENCE_PRESENT:
        lines.append(
            f"  wave_id={_flat(wave_journal['wave_id'])} mode={_flat(wave_journal['mode'])} "
            f"complete={wave_journal['complete']}"
        )
        lines.append(f"  plan_digest={_flat(wave_journal['plan_digest'])}")
        lines.append(
            f"  required_node_count={wave_journal['required_node_count']} "
            f"required_nodes_without_disposition={_flat(wave_journal['required_nodes_without_disposition'])}"
        )
        lines.append(
            f"  entry_count={_flat(wave_journal['entry_count'])} "
            f"plan_revision_count={wave_journal['plan_revision_count']} "
            f"approval_count={wave_journal['approval_count']} retry_count={wave_journal['retry_count']} "
            f"budget_count={wave_journal['budget_count']}"
        )
        lines.append(
            f"  opened_at={_flat(wave_journal['opened_at'])} last_at={_flat(wave_journal['last_at'])}"
        )
    lines.append("")

    runtime_assignment = artifacts["runtime_assignment"]
    lines.append("== runtime assignment ==")
    lines.append(_presence_line("runtime assignment", runtime_assignment))
    if runtime_assignment["presence"] == PRESENCE_PRESENT:
        lines.append(f"  command={_flat(runtime_assignment['command'])} verdict={_flat(runtime_assignment['verdict'])}")
        # `may_spawn` and `blocks_wave_completion` are carried through from the report UNVALIDATED --
        # this module reports whichever value the report wrote -- so both go through `_flat`, which is
        # a no-op for the bool or null they normally are and an escape for the hostile string they
        # could be. A bare interpolation here would forge a line out of a report's own field.
        lines.append(
            f"  node={_flat(runtime_assignment['node'])} may_spawn={_flat(runtime_assignment['may_spawn'])} "
            f"blocks_wave_completion={_flat(runtime_assignment['blocks_wave_completion'])}"
        )
        lines.append(f"  consequence: {_flat(runtime_assignment['consequence'])}")
        for reason in runtime_assignment["reasons"]:
            lines.append(f"  reason: {_flat(reason)}")
    lines.append("")

    activation_result = artifacts["activation_result"]
    lines.append("== activation result ==")
    lines.append(_presence_line("activation result", activation_result))
    if activation_result["presence"] == PRESENCE_PRESENT:
        lines.append(f"  state={_flat(activation_result['state'])} target={_flat(activation_result['target'])}")
        # Both are carried through UNVALIDATED, so both are escaped -- see the runtime-assignment note.
        lines.append(
            f"  gate_outcome={_flat(activation_result['gate_outcome'])} "
            f"gate_passes={_flat(activation_result['gate_passes'])}"
        )
        lines.append(f"  consequence: {_flat(activation_result['consequence'])}")
        for reason in activation_result["reasons"]:
            lines.append(f"  reason: {_flat(reason)}")
    lines.append("")

    gate = artifacts["gate"]
    lines.append("== gate ==")
    lines.append(_presence_line("gate receipt", gate["receipt"]))
    if gate["receipt"]["presence"] == PRESENCE_PRESENT:
        receipt = gate["receipt"]
        lines.append(
            f"  gate={_flat(receipt['gate'])} outcome={_flat(receipt['outcome'])} "
            f"gate_status={receipt['gate_status']} ran={receipt['ran']}"
        )
        lines.append(
            f"  failing_set_state={_flat(receipt['failing_set_state'])} "
            f"failing_test_count={receipt['failing_test_count']}"
        )
    lines.append(_presence_line("gate baseline", gate["baseline"]))
    if gate["baseline"]["presence"] == PRESENCE_PRESENT:
        baseline = gate["baseline"]
        lines.append(
            f"  gate={_flat(baseline['gate'])} baseline_outcome={_flat(baseline['baseline_outcome'])} "
            f"candidate_outcome={_flat(baseline['candidate_outcome'])}"
        )
        lines.append(
            f"  non_worsening={baseline['non_worsening']} toolchain_drifted={baseline['toolchain_drifted']}"
        )
        lines.append(
            f"  newly_failing={_flat(baseline['newly_failing'])} fixed={_flat(baseline['fixed'])} "
            f"still_failing={_flat(baseline['still_failing'])} "
            f"candidate_failing={_flat(baseline['candidate_failing'])}"
        )
    if gate["cross_check"] is not None:
        lines.append(f"  cross_check same_gate={gate['cross_check']['same_gate']}")
    lines.append("")

    # The eight sealed kinds in the family's own chain order, one section each, from the same table
    # `artifacts` was assembled from -- so a new row cannot be projected into `--json` and forgotten
    # in the human view.
    for reader in SEALED_READERS:
        lines.extend(render_sealed_section(reader, artifacts[reader.kind]))

    return "\n".join(lines) + "\n"


# ---- hostile-stream-safe delivery, re-expressed from mission-contract.py's own pattern -------------


def abandon_broken_stream(name: str, stream: object) -> None:
    if getattr(sys, name, None) is stream:
        setattr(sys, name, None)


def guarded_sink(name: str, stream: object) -> Any:
    if stream is None:
        return lambda data: None
    write = getattr(stream, "write", None)
    if not callable(write):
        return lambda data: None
    flush = getattr(stream, "flush", None)
    live = [True]

    def emit(data: Any) -> None:
        if not live[0]:
            return
        try:
            write(data)
            if callable(flush):
                flush()
        except (OSError, ValueError):
            live[0] = False
            abandon_broken_stream(name, stream)

    return emit


def advisory_stderr() -> Any:
    return guarded_sink("stderr", sys.stderr)


def report_internal_error(message: str) -> None:
    advisory_stderr()(f"sdlc-observability-projection.py: {message}\n")


def emit_payload(payload: bytes) -> int:
    """Deliver the one result document, or classify the failure instead of inheriting 1 or 120."""
    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    emit_to: Any = None
    flush: Any = None
    body: Any = payload
    if buffer is not None and callable(getattr(buffer, "write", None)):
        emit_to, flush = buffer.write, getattr(buffer, "flush", None)
    elif stream is not None and callable(getattr(stream, "write", None)):
        emit_to, flush, body = stream.write, getattr(stream, "flush", None), payload.decode("utf-8")
    if emit_to is None:
        report_internal_error(
            "this process was handed no stdout to write its one result document to, so the derived "
            "projection could not be delivered"
        )
        return EXIT_INTERNAL
    try:
        emit_to(body)
        if callable(flush):
            flush()
    except (OSError, ValueError) as exc:
        abandon_broken_stream("stdout", stream)
        report_internal_error(
            f"cannot write the projection to stdout: {exc}; an unknown prefix of it may already have "
            "reached the consumer"
        )
        return EXIT_INTERNAL
    return EXIT_OK


class _OnceOnly(argparse.Action):
    """One artifact path flag, at most ONCE.

    argparse's default for a repeated option is silent last-wins: `--gate-receipt a --gate-receipt b`
    projects `b` and never mentions that `a` was asked for and dropped. For a read-only projection whose
    whole value is naming exactly which evidence it read, silently reading a different file than the
    caller listed is worse than refusing, so a repeat is a grammar error (exit 2) that names the flag.
    The message names the OPTION only, never either path: a path is caller data, and the refusal has to
    be printable in a log beside a document that deliberately does not echo one.

    `--json` is deliberately NOT once-only: it takes no value, so repeating it drops nothing.
    """

    def __call__(self, parser: Any, namespace: Any, values: Any, option_string: str | None = None) -> None:
        if getattr(namespace, self.dest, None) is not None:
            parser.error(
                f"{option_string or flag_for(self.dest)} was given more than once; each artifact path may "
                "be supplied at most once, and a repeat would silently drop the first one"
            )
        setattr(namespace, self.dest, values)


class _Parser(argparse.ArgumentParser):
    """argparse, taught this module's two stream rules (re-expressed from mission-contract.py)."""

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        if file is None:
            return
        if file is sys.stdout or file is sys.__stdout__:
            guarded_sink("stdout", file)(message)
            return
        guarded_sink("stderr", file)(message)

    def error(self, message: str) -> Any:
        note = advisory_stderr()
        note(self.format_usage())
        note(f"{self.prog}: error: {message}\n")
        raise SystemExit(EXIT_INPUT)


EPILOG = (
    "Exit codes: 0 a projection was derived, an absent or unreadable input included by name; 2 the "
    "arguments themselves are unusable, INCLUDING one artifact flag given more than once; 1 an "
    "unexpected internal failure, among them a stdout that "
    "cannot receive the one result document. Implementation Decision 9's 3 and 4 do not apply: a "
    "command that causes no effect can neither refuse before one nor admit one. This projection is "
    "evidence, not authorization."
)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="sdlc-observability-projection.py",
        description=(
            "Read-only observability projection over already-recorded agentic-SDLC evidence: a "
            "wave journal, a runtime-assignment report, an activation result, a gate "
            "receipt/baseline pair, and the eight sealed slice-6 planning documents (mission "
            "contract, planning snapshot, wave plan, plan diff, wave-plan admission report, drift "
            "classification, auto envelope, autonomous-transition receipt), each optional. Never "
            "writes anything; it is evidence, not authorization."
        ),
        epilog=EPILOG,
    )
    parser.add_argument(
        "--wave-journal",
        dest="wave_journal",
        default=None,
        action=_OnceOnly,
        help="path to a wave-journal.py ledger",
    )
    parser.add_argument(
        "--runtime-assignment",
        dest="runtime_assignment",
        default=None,
        action=_OnceOnly,
        help="path to a runtime-assignment.py admit or classify report",
    )
    parser.add_argument(
        "--activation-result",
        dest="activation_result",
        default=None,
        action=_OnceOnly,
        help="path to an activation-result.py document",
    )
    parser.add_argument(
        "--gate-receipt",
        dest="gate_receipt",
        default=None,
        action=_OnceOnly,
        help="path to a gate_receipt.py receipt",
    )
    parser.add_argument(
        "--gate-baseline",
        dest="gate_baseline",
        default=None,
        action=_OnceOnly,
        help="path to a gate_baseline.py compare report for the same --gate-receipt",
    )
    for reader in SEALED_READERS:
        parser.add_argument(
            flag_for(reader.kind), dest=reader.kind, default=None, action=_OnceOnly, help=reader.help
        )
    parser.add_argument("--json", dest="json_output", action="store_true", help="emit the machine document instead")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        document = build_document(args)
        payload = canonical_bytes(document) if args.json_output else render_human(document).encode("utf-8")
    except Exception as exc:  # an unexpected failure must still classify itself rather than crash
        report_internal_error(f"unexpected {type(exc).__name__}: {exc}")
        return EXIT_INTERNAL
    return emit_payload(payload)


if __name__ == "__main__":
    raise SystemExit(main())
