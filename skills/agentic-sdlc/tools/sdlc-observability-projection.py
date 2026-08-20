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

FOUR OPTIONAL INPUTS, each independent of the others:

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

NEVER MANUFACTURE SUCCESS. Three outcomes, and only three, for every one of the four inputs:

    absent       no path was supplied, or the supplied path does not exist. Named as absent.
    unreadable   the path exists but could not be read as the document it claims to be -- not a
                 regular file, not UTF-8, not JSON, not the right schema, a digest that does not
                 re-derive, or a shape this module does not recognise. Named as unreadable, WITH
                 the reason, and every other input keeps its own independent outcome.
    present      the document was read and validated; its own fields are projected VERBATIM in its
                 own vocabulary. This module never upgrades a "failed" into a "passed", never
                 infers a wave completed because its evidence is silent, and never states an
                 artifact's fact in different words than the artifact itself used.

An absent or unreadable input is never an error for this module: the projection always succeeds
(exit 0) and simply says, by name, what it could not use. That is the whole point of an
observability surface over evidence that arrives piecemeal, wave by wave.

TWO VIEWS OF ONE DOCUMENT. The default view is a human BLUF-first read: the single most
decision-relevant line first (one artifact's own top fact, in a fixed priority order --
activation result, then the gate, then runtime assignment, then the wave journal -- because that
is the order in which each fact subsumes the ones after it), then one section per artifact.
`--json` emits the identical underlying document as canonical JSON
(`agentic-sdlc/observability-projection@1`). Both views carry, verbatim, the sentence "this view is
evidence, not authorization": nothing this module derives may be read as a grant to write, push,
publish, mutate a PR, merge, or deploy.

FAIL CLOSED ON THE TOOL ITSELF, NOT ON THE EVIDENCE. Every predicate above only ever downgrades an
input from "present" to "unreadable"; nothing here can upgrade an input, and nothing here can turn
a well-formed refusal recorded by another tool into anything but the refusal it already is.

EXITS. Implementation Decision 9 reserves 0 for a valid query, 1 for an unexpected internal
failure, 2 for a grammar/argument error, 3 for a clean refusal before effect, and 4 after an
admitted partial or unknown effect. This module's exit space is 0, 2, and 1 only, for the same
reason `mission-contract.py` and `activation-result.py` give: **a tool that can cause no effect can
neither refuse before one nor admit one.** Every one of the four inputs is optional, and an absent
or unreadable one is folded into the exit-0 document rather than raised as a refusal. Exit 2 is
reserved for the arguments themselves being unusable (an unknown flag, a missing option value);
exit 1 additionally covers a stdout that cannot receive the one result document, because a
projection derived and not delivered is not a success.

RESIDUALS, STATED EXACTLY.

  * This first cut projects only what already exists today: the wave journal, a runtime-assignment
    report, an activation result, and a gate receipt/baseline pair. MissionContract, PlanningSnapshot,
    WavePlan, PlanDiff, AutoEnvelope, and the shared receipt envelope (T1/T2/T3/T5/T6/T7/T8 in the
    slice-6 cartography) are not yet artifact kinds this module knows; adding one is an additive
    extension of the reader registry below, never a rewrite of it.
  * The wave journal's own `journal_digest` anchor (a rewrite-or-truncation detector across
    repeated reads over TIME) is not retained across invocations here: each run is independent, and
    a caller polling this module repeatedly must keep that anchor itself if it wants to detect a
    rewritten tail between polls.
  * Every digest re-derivation here is TAMPER DETECTION BY RE-DERIVATION, not a security boundary
    against a same-OS-user forger -- the same posture every sibling tool in this family states.
  * `--gate-baseline` is read as an ALREADY-COMPUTED comparison document; this module does not
    itself invoke `gate_baseline.py` or re-implement its subset-comparison algorithm, mirroring
    `activation-result.py`'s own `--baseline-comparison` precedent exactly.
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
from typing import Any

RESULT_SCHEMA = "agentic-sdlc/observability-projection@1"
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
#: Exactly `gate_receipt.build_receipt`'s keys, `failures` the one optional addition -- re-expressed
#: from `activation-result.py`'s own `GATE_RECEIPT_KEYS`, never imported.
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
    """Raised only within this module's own JSON reading helpers; never escapes them."""


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
    if not GATE_RECEIPT_KEYS <= keys or not keys <= GATE_RECEIPT_KEYS | {"failures"}:
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


# ---- the table-driven reader registry --------------------------------------------------------------
#: One entry per artifact kind: how to build its section from the parsed CLI arguments. Iterated in
#: this fixed order both to assemble `artifacts` and, separately, to pick the BLUF line -- adding a
#: kind later (T1/T2/T5/T6/T7/T8's artifacts) is one more row here, never a rewrite of this loop.
ARTIFACT_KINDS: tuple[tuple[str, Any], ...] = (
    ("wave_journal", lambda args: build_wave_journal_section(args.wave_journal)),
    ("runtime_assignment", lambda args: build_runtime_assignment_section(args.runtime_assignment)),
    ("activation_result", lambda args: build_activation_result_section(args.activation_result)),
    ("gate", lambda args: build_gate_section(args.gate_receipt, args.gate_baseline)),
)


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
    receipt, baseline = section["receipt"], section["baseline"]
    if receipt["presence"] == PRESENCE_ABSENT and baseline["presence"] == PRESENCE_ABSENT:
        return None
    if baseline["presence"] == PRESENCE_UNREADABLE:
        return f"the gate baseline comparison is unreadable: {_flat(baseline['reason'])}"
    if baseline["presence"] == PRESENCE_PRESENT:
        verdict_word = "non-worsening" if baseline["non_worsening"] else "WORSENED"
        return f"gate {_flat(baseline['gate'])}: {verdict_word} ({len(baseline['newly_failing'])} newly failing)"
    if receipt["presence"] == PRESENCE_UNREADABLE:
        return f"the gate receipt is unreadable: {_flat(receipt['reason'])}"
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


#: Priority order for the single most decision-relevant line: each fact subsumes the ones after it
#: (an activation refusal matters more than one node's missing disposition), so the FIRST kind that
#: has anything to say wins, and the rest are read from the per-artifact sections below it.
BLUF_ORDER: tuple[tuple[str, Any], ...] = (
    ("activation_result", _bluf_activation_result),
    ("gate", _bluf_gate),
    ("runtime_assignment", _bluf_runtime_assignment),
    ("wave_journal", _bluf_wave_journal),
)


def _leaf_sections(artifacts: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """The five independently-supplied paths, gate's receipt/baseline split out of its section --
    the same granularity `--gate-receipt`/`--gate-baseline` are supplied at."""
    gate = artifacts["gate"]
    return (
        artifacts["wave_journal"],
        artifacts["runtime_assignment"],
        artifacts["activation_result"],
        gate["receipt"],
        gate["baseline"],
    )


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
        lines.append(
            f"  required_nodes_without_disposition={_flat(wave_journal['required_nodes_without_disposition'])}"
        )
        lines.append(
            f"  entry_count={wave_journal['entry_count']} plan_revisions={wave_journal['plan_revision_count']} "
            f"approvals={wave_journal['approval_count']} retries={wave_journal['retry_count']}"
        )
    lines.append("")

    runtime_assignment = artifacts["runtime_assignment"]
    lines.append("== runtime assignment ==")
    lines.append(_presence_line("runtime assignment", runtime_assignment))
    if runtime_assignment["presence"] == PRESENCE_PRESENT:
        lines.append(f"  command={_flat(runtime_assignment['command'])} verdict={_flat(runtime_assignment['verdict'])}")
        lines.append(f"  consequence: {_flat(runtime_assignment['consequence'])}")
        for reason in runtime_assignment["reasons"]:
            lines.append(f"  reason: {_flat(reason)}")
    lines.append("")

    activation_result = artifacts["activation_result"]
    lines.append("== activation result ==")
    lines.append(_presence_line("activation result", activation_result))
    if activation_result["presence"] == PRESENCE_PRESENT:
        lines.append(f"  state={_flat(activation_result['state'])} target={_flat(activation_result['target'])}")
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
            f"  gate={_flat(receipt['gate'])} outcome={_flat(receipt['outcome'])} ran={receipt['ran']} "
            f"failing_test_count={receipt['failing_test_count']}"
        )
    lines.append(_presence_line("gate baseline", gate["baseline"]))
    if gate["baseline"]["presence"] == PRESENCE_PRESENT:
        baseline = gate["baseline"]
        lines.append(
            f"  non_worsening={baseline['non_worsening']} newly_failing={_flat(baseline['newly_failing'])} "
            f"fixed={_flat(baseline['fixed'])}"
        )
    if gate["cross_check"] is not None:
        lines.append(f"  cross_check same_gate={gate['cross_check']['same_gate']}")
    lines.append("")

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
    "arguments themselves are unusable; 1 an unexpected internal failure, INCLUDING a stdout that "
    "cannot receive the one result document. Implementation Decision 9's 3 and 4 do not apply: a "
    "command that causes no effect can neither refuse before one nor admit one. This projection is "
    "evidence, not authorization."
)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="sdlc-observability-projection.py",
        description=(
            "Read-only observability projection over already-recorded agentic-SDLC evidence: a "
            "wave journal, a runtime-assignment report, an activation result, and a gate "
            "receipt/baseline pair, each optional. Never writes anything; it is evidence, not "
            "authorization."
        ),
        epilog=EPILOG,
    )
    parser.add_argument("--wave-journal", dest="wave_journal", default=None, help="path to a wave-journal.py ledger")
    parser.add_argument(
        "--runtime-assignment",
        dest="runtime_assignment",
        default=None,
        help="path to a runtime-assignment.py admit or classify report",
    )
    parser.add_argument(
        "--activation-result", dest="activation_result", default=None, help="path to an activation-result.py document"
    )
    parser.add_argument("--gate-receipt", dest="gate_receipt", default=None, help="path to a gate_receipt.py receipt")
    parser.add_argument(
        "--gate-baseline",
        dest="gate_baseline",
        default=None,
        help="path to a gate_baseline.py compare report for the same --gate-receipt",
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
